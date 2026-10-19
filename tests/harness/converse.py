"""
The conversation harness: a day of real conversation, in simulated time, between two independent
sessions through the real API.

  - the SIMULATOR is one API session threading its own context. It plays Shreyas: it has a life
    (a plan of the day), its own notes of what it said, and no access to Avy's memory, state or
    system prompt. It never sees the probe questions or the rubric.
  - the SUBJECT is real Avy: the same `app.Turn` the page uses, the same memory, the same mind.

Nothing is mocked. Every line in a transcript came back from the model.

  python3 tests/harness/converse.py --plan plan.json --out out/ --label baseline

A plan is JSON:
  {
    "persona": "...optional extra flavour for the simulated user...",
    "avoid": "...things the simulator must never invent...",
    "days": [
      {"day": 1, "sittings": [
         {"at": "09:10", "thread": "work", "turns": 14, "about": "...", "kind": "chat|task"},
         {"at": "11:00", "probe": {"id": "ref-1", "ask": "...", "checks": [...]}}   # a probe, asked of Avy
      ]}
    ]
  }

Probes are asked of the SUBJECT with the real turn path; their answers are recorded for grading and
are not shown to the simulator. The simulator also gets "planted referents": facts it will casually
mention and then refer back to later ("the thing I said about X"), so continuity can be measured on
things it actually said.

Everything is written as it happens to <out>/<label>.jsonl (one event per line) so a crash loses
nothing, and a readable <out>/<label>.md transcript at the end.
"""

import argparse
import json
import os
import sys
import time
import traceback
from datetime import datetime, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(ROOT))


# ---------------------------------------------------------------------------------------------
# keys first (app reads them at import)
# ---------------------------------------------------------------------------------------------

def load_keys(path):
    env = {}
    for line in Path(path).read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip().strip('"').strip("'")
    for k in ("LUMINAL_API_KEY", "LUMINAL_BASE_URL", "HELIX_FLASH_MODEL"):
        if env.get(k):
            os.environ[k] = env[k]
    return env


# ---------------------------------------------------------------------------------------------
# the two independent sessions
# ---------------------------------------------------------------------------------------------

SIM_SYSTEM = """You are Shreyas, a 24-year-old who runs his own projects and talks to his personal agent, Avy, \
many times a day. You are NOT an assistant. You are the person. Write only your message — no quotes, no \
narration, never mention that this is a simulation.

How you talk: short, casual, lowercase, like texting. One or two sentences usually. You interrupt, change \
subject, refer back to things you said earlier in the day, and sometimes you get impatient. You have a plan \
for the day and you pursue it across many messages, sometimes abandoning it and coming back hours later.

You DO NOT know what Avy remembers. Never explain what you want her to recall; just refer to it.

Never invent people, dates, numbers or facts that aren't in your notes. Reuse your own wording when you \
refer back to something."""

SIM_NOTE_AFTER = """Your private notes (only you can see these): what you've said so far today and what you still mean to say.
{notes}
{planted}
Write your next message to Avy now. Just the message."""


def sim_turn(history, notes, planted, extra=""):
    """One message from the simulated Shreyas: its own context, its own notes, no access to the subject."""
    import luminal
    system = SIM_SYSTEM + (("\n\n" + extra) if extra else "")
    msgs = [{"role": "system", "content": system}]
    msgs += history[-40:]
    msgs.append({"role": "user", "content": SIM_NOTE_AFTER.format(notes=notes, planted=planted)})
    r = luminal.complete({"messages": msgs, "max_tokens": 400}, effort="none")
    text = (r["choices"][0]["message"]["content"] or "").strip()
    text = text.strip('"').strip()
    from mind import llm
    return text, llm.cost(r.get("usage") or {})


# ---------------------------------------------------------------------------------------------
# the subject: one real Avy turn
# ---------------------------------------------------------------------------------------------

def subject_turn(text, memo, approve=True):
    """A real Avy turn through the app's own path. Returns (reply, detail).

    approve: behave like a user who is sitting there — answer her approval cards at once. (In a headless
    run nobody clicks, and the turn then blocks for the app's full 300 s approval timeout: that is what
    made the first smoke test's opening turn take 306.8 s.)"""
    import json as _json
    import threading
    import app
    from mind import llm, worker
    turn = app.Turn(text, "text")
    reply, usage, tools, steps, asks_seen = "", None, [], [], []
    started = time.time()

    def answer_asks():
        while True:
            try:
                ask = turn.asks.get(timeout=0.2)
            except Exception:
                if done.is_set():
                    return
                continue
            asks_seen.append(ask)
            rid = ask.get("id")
            if rid in turn.answers:
                turn.answers[rid]["allow"] = approve
                turn.answers[rid]["event"].set()

    done = threading.Event()
    watcher = threading.Thread(target=answer_asks, daemon=True)
    watcher.start()
    with turn.ask() as upstream:
        for raw in upstream:
            line = raw.decode(errors="replace") if isinstance(raw, bytes) else raw
            words, counts = turn.stream(raw)
            reply += words or ""
            usage = counts or usage
            if '"step"' in line or '"did"' in line:      # what her tools did, as the page hears it
                try:
                    ev = _json.loads(line[5:]).get("avy") or {}
                    if ev.get("step"):
                        steps.append(ev["step"])
                except Exception:
                    pass
    done.set()
    user_id = turn.user_id
    turn.finish(reply, usage)
    cost = llm.cost(usage or {}) + ((turn.recall.get("explore") or {}).get("cost") or 0)
    detail = {
        "seconds": round(time.time() - started, 1),
        "cost": round(cost, 5),
        "prompt_tokens": (usage or {}).get("prompt_tokens"),
        "completion_tokens": (usage or {}).get("completion_tokens"),
        "window_messages": len(turn.messages),
        "recall": {
            "nodes": [(x.get("handle"), x.get("title")) for x in turn.recall.get("nodes", [])],
            "planned": (turn.recall.get("explore") or {}).get("task"),
            "desk_thread": (turn.recall.get("desk") or {}).get("thread"),
            "desk_situation": (turn.recall.get("desk") or {}).get("situation"),
            "briefing_chars": len(turn.recall.get("briefing") or ""),
        },
        "thought": bool(turn.thought),
        "tools": tools,
        "did": turn.did,
        "steps": steps,
        "approvals_asked": len(asks_seen),
    }
    # the mind catches up as the app nudges it after every reply
    wrote = worker.write_due(app.MEMORIES["main"])
    detail["mind"] = [{"job": r["job"], "status": r["status"], "applied": r.get("applied")} for r in wrote]
    return reply, detail, user_id


# ---------------------------------------------------------------------------------------------
# bookkeeping
# ---------------------------------------------------------------------------------------------

class Log:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.f = open(self.path, "a", encoding="utf-8")

    def write(self, kind, **kw):
        row = {"kind": kind, "at": datetime.now().isoformat(timespec="seconds"), **kw}
        self.f.write(json.dumps(row, default=str) + "\n")
        self.f.flush()
        return row

    def close(self):
        self.f.close()


def show(*parts):
    print(" ".join(str(p) for p in parts), flush=True)


# ---------------------------------------------------------------------------------------------
# the run
# ---------------------------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", required=True)
    ap.add_argument("--out", default=str(HERE / "out"))
    ap.add_argument("--label", default="")
    ap.add_argument("--key", default=str(ROOT / ".env"))
    ap.add_argument("--models", default=str(ROOT / "data" / "models" / "meaning"))
    ap.add_argument("--max-minutes", type=float, default=600, help="hard wall-clock stop")
    ap.add_argument("--thinking", default="none")
    ap.add_argument("--mind-effort", default="none")
    args = ap.parse_args()

    load_keys(args.key)
    plan = json.loads(Path(args.plan).read_text())
    label = args.label or Path(args.plan).stem
    stamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    work = out / f"{stamp}_{label}.memory"
    work.mkdir(exist_ok=True)

    import app
    import memory
    from mind import llm, worker

    memory.embedder.start(Path(args.models))
    memory.embedder.wait(300)
    app.MEMORIES["main"] = memory.Memory(work / "memory-v2.db")
    app.FILES_DIR = work / "files"
    app.INTAKE.start()
    llm.app.update(ask=app.ask_json, prices=app.PRICES, effort=lambda: args.mind_effort)
    worker.app.update(page=app.page_size, main=lambda: app.MEMORIES["main"],
                      memories=lambda: [app.MEMORIES["main"]])
    defaults = {name: spec["default"] for name, spec in app.SETTINGS.items()}
    settings = dict(defaults, thinking=args.thinking, mind=args.mind_effort, footnotes="on")
    app.current_settings = lambda: settings
    # The real app does this in its __main__ block, which the harness bypasses: her hands need a workspace,
    # or ~workspace points at a path that doesn't exist and every file lookup she makes is against nothing.
    import hands
    hands.WORKSPACE = app.DATA / "workspace"
    hands.WORKSPACE.mkdir(parents=True, exist_ok=True)
    # The real app does this in its __main__ block, which the harness bypasses. Without it her toolboxes are
    # never started and look() answers "your browser toolbox isn't started" — a harness fault, not hers.
    import connectors
    connectors.start(app.DATA / "connectors.json")

    log = Log(out / f"{stamp}_{label}.jsonl")
    log.write("start", label=label, plan=str(args.plan), settings={k: str(v) for k, v in settings.items()},
              model=os.environ.get("HELIX_FLASH_MODEL"))
    show(f"harness {stamp}_{label}: memory in {work}")

    sim_history = []          # the simulator's own conversation with itself
    notes = []                # what it has said
    planted = []              # things it will need to refer back to
    spent = {"subject": 0.0, "sim": 0.0}
    inbox = {}                # day -> notes it means to bring up
    start = time.time()
    day1 = None

    def set_clock(t):
        memory.clock.fixed = t

    def subject(text, thread, day, tag):
        if time.time() - start > args.max_minutes * 60:
            raise SystemExit("wall clock")
        reply, detail, uid = subject_turn(text, None)
        spent["subject"] += detail["cost"]
        log.write("exchange", thread=thread, day=day, who="user", text=text, tag=tag)
        log.write("exchange", thread=thread, day=day, who="avy", text=reply, detail=detail, tag=tag)
        show(f"  [d{day} {thread}] SHREYAS: {text[:120]}")
        show(f"  [d{day} {thread}] AVY:     {reply[:200].replace(chr(10), ' ')}  "
             f"({detail['seconds']}s {detail['prompt_tokens']}pt desk={detail['recall']['desk_thread']})")
        return reply, detail

    for day_plan in plan["days"]:
        day = day_plan["day"]
        if day1 is None:
            day1 = datetime.fromisoformat(day_plan.get("date") or "2026-10-05T00:00").astimezone()
        for sitting in day_plan["sittings"]:
            at = sitting.get("at", "09:00")
            h, m = (int(x) for x in at.split(":"))
            set_clock(day1 + timedelta(days=day - 1, hours=h, minutes=m))
            log.write("sitting", day=day, at=at, thread=sitting.get("thread"), about=sitting.get("about"))

            # the mind catches up on a quiet spell before this sitting
            for r in worker.write_due(app.MEMORIES["main"]):
                log.write("mind", job=r["job"], status=r["status"], applied=r.get("applied"))

            if sitting.get("probe"):
                p = sitting["probe"]
                reply, detail = subject(p["ask"], "probe", day, tag=f"probe:{p['id']}")
                log.write("probe_answer", id=p["id"], ask=p["ask"], answer=reply, detail=detail,
                          checks=p.get("checks"))
                sim_history.append({"role": "assistant", "content": f"(you asked Avy: {p['ask']} — she answered)"})
                continue

            turns = sitting.get("turns", 4)
            thread = sitting.get("thread") or "chat"
            about = sitting.get("about") or ""
            kind = sitting.get("kind") or "chat"
            for i in range(turns):
                set_clock(memory.now() + timedelta(minutes=2, seconds=30))
                guide = (f"Right now you're talking about: {about}. " if about else "")
                if kind == "task":
                    guide += ("You're working on this WITH Avy over several messages: ask her to build or plan "
                              "something concrete, respond to what she says, push it further, and at some point "
                              "abandon it mid-way without saying why. ")
                if i < len(planted):
                    guide += f"You still mean to bring up: {planted[i]}. "
                text, simcost = sim_turn(sim_history, " ".join(f"({n})" for n in notes[-12:]),
                                         "\n".join(planted[:6]) or "(nothing planted)", extra=guide)
                spent["sim"] += simcost
                if not text:
                    continue
                log.write("sim_message", thread=thread, day=day, text=text)
                reply, detail = subject(text, thread, day, tag=f"{thread}:{i}")
                notes.append(text)
                sim_history.append({"role": "user", "content": text})
                sim_history.append({"role": "assistant", "content": reply[:900]})
            set_clock(memory.now() + timedelta(minutes=31))
            for r in worker.write_due(app.MEMORIES["main"]):
                log.write("mind", job=r["job"], status=r["status"], applied=r.get("applied"))

    # the mind reflects at night, as it does when it's quiet
    for k in range(plan.get("nights", 2)):
        set_clock(memory.now() + timedelta(hours=10))
        for r in worker.reflect_now(app.MEMORIES["main"], thinks=3, budget=400):
            log.write("mind", job=r["job"], status=r["status"], applied=r.get("applied"))
            show(f"  [night] {r['job']} {r['status']} +{r.get('applied', 0)}")

    log.write("done", spent=spent, hours=round((time.time() - start) / 3600, 2))
    show(f"\ndone: {spent['subject']:.2f} subject, {spent['sim']:.2f} simulator, "
         f"{(time.time() - start) / 60:.0f} min")
    log.close()


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception:
        traceback.print_exc()
        sys.exit(1)
