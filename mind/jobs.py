"""The engine every model job runs through. A job is one question to DeepSeek with a strict answer shape:

    1. job.prompt()        what DeepSeek is shown, with short handles (#41 message, k12 node, p3 pair)
    2. llm.call()          one structured answer (a tool call whose shape a schema fixes)
    3. job.check(answer)   code checks every part of it and turns what passes into proposals
    4. repair              what failed goes back to DeepSeek in plain words, up to twice
    5. memory.apply_all()  the best answer's proposals go through the one door (rules + journal)
    6. a run record        the prompt, every reply, every problem, the cost: all inspectable

If DeepSeek can't be reached, nothing is lost and nothing half-written: the run says why.
"""

import json
import time
from dataclasses import dataclass, field

from . import llm

REPAIRS = 2    # how many times DeepSeek may fix its answer


@dataclass
class Plan:
    ops: list = field(default_factory=list)        # proposals for memory.apply_all
    problems: list = field(default_factory=list)   # what's wrong, in plain words, for DeepSeek to fix
    notes: list = field(default_factory=list)      # what code fixed by itself (kept in the run's record)
    extra: dict = field(default_factory=dict)      # anything the job wants back in after()


class Job:
    name = "job"
    tool = None
    model = llm.MODEL
    max_tokens = 8000
    focus = ""

    def prompt(self):
        raise NotImplementedError

    def check(self, answer):
        raise NotImplementedError

    def after(self, run_id, plan, results, refs):
        return {}


def run(mem, job):
    """Run one job on one memory. Returns a summary: {id, job, status, attempts, applied, rejected, ...}."""
    started = time.time()
    convo = job.prompt()
    asked = list(convo)
    replies, problem_log, best = [], [], None
    used = {"prompt_tokens": 0, "completion_tokens": 0, "prompt_cache_hit_tokens": 0, "prompt_cache_miss_tokens": 0}
    name = job.tool["function"]["name"]

    for attempt in range(1, REPAIRS + 2):
        try:
            reply = llm.call(convo, job.tool, job.model, job.max_tokens)
        except Exception as e:
            run_id = save(mem, job, "error", attempt, started, asked, replies,
                          problem_log + [[f"couldn't reach DeepSeek: {getattr(e, 'message', e)}"]], used)
            return {"id": run_id, "job": job.name, "status": "error", "attempts": attempt, "applied": 0, "rejected": 0,
                    "focus": job.focus, "problem": str(getattr(e, "message", e))}
        replies.append(reply)
        for k in used:
            used[k] += (reply.get("usage") or {}).get(k, 0)
        answer, problem = llm.read_call(reply, name)
        plan = None if problem else job.check(answer)
        problems = [problem] if problem else plan.problems
        problem_log.append(problems + [f"(fixed by code) {n}" for n in (plan.notes if plan else [])])
        if plan and (best is None or len(plan.problems) <= len(best.problems)):
            best = plan
        if not problems or attempt == REPAIRS + 1:
            break
        feedback = ("Some of that can't be saved yet. Fix these and call " + name + " again with the complete answer "
                    "(everything, not only the fixes):\n- " + "\n- ".join(problems))
        msg = (reply.get("choices") or [{}])[0].get("message") or {}
        calls = msg.get("tool_calls") or []
        if calls:
            convo = convo + [{"role": "assistant", "content": msg.get("content") or "", "tool_calls": calls[:1]},
                             {"role": "tool", "tool_call_id": calls[0].get("id", "call"), "content": feedback}]
        else:
            convo = convo + [{"role": "assistant", "content": msg.get("content") or ""}, {"role": "user", "content": feedback}]

    if best is None:
        status = "failed"
    else:
        fixed = any(any(not p.startswith("(") for p in found) for found in problem_log[:-1])
        status = "partial" if best.problems else "repaired" if fixed else "ok"
    run_id = save(mem, job, status, attempt, started, asked, replies, problem_log, used)
    if best is None:
        return {"id": run_id, "job": job.name, "status": status, "attempts": attempt, "applied": 0, "rejected": 0,
                "focus": job.focus, "problem": (problem_log[-1] or ["?"])[0]}
    results, refs = mem.apply_all(best.ops, run_id)
    summary = job.after(run_id, best, results, refs) or {}
    return {"id": run_id, "job": job.name, "status": status, "attempts": attempt, "focus": job.focus,
            "applied": sum(1 for r in results if r["applied"]), "rejected": sum(1 for r in results if not r["applied"]),
            "rejections": [f"{r['op']} {r.get('target') or r.get('ref') or ''}: {r['why']}" for r in results if not r["applied"]],
            "cost": round(llm.cost(used, job.model), 6), **summary}


def save(mem, job, status, attempts, started, asked, replies, problems, used):
    return mem.save_run(job=job.name, status=status, attempts=attempts, model=job.model, focus=job.focus,
                        seconds=round(time.time() - started, 1), tokens_in=used["prompt_tokens"],
                        tokens_out=used["completion_tokens"], cost=round(llm.cost(used, job.model), 6),
                        prompt=asked, replies=replies, problems=problems)


def as_text(value):
    return json.dumps(value, ensure_ascii=False)
