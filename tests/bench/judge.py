"""Grading for the benchmark, shared by run.py (version 2) and v1_replay.py (version 1).

  grade()      a separate DeepSeek judge scores an answer against the points a good answer makes, with
               the true conversations in front of it, and flags anything stated that they don't support
  retrieval()  what memory brought, scored: which sittings the question needed were covered, and how
               many items were about something else entirely
"""

import time
from datetime import datetime, timedelta

import world
from mind import llm

TOOL = llm.tool("grade", "Grade the answer.", {
    "points": {"type": "array", "items": llm.obj({
        "point": {"type": "integer"},
        "verdict": {"type": "string", "enum": ["met", "partly", "missed"]},
        "why": {"type": "string"},
    })},
    "invented": {"type": "boolean", "description": "Does the answer state, as fact, something about Shreyas's life that the conversations don't support?"},
    "invented_what": {"type": "string"},
})

DAY1 = datetime.fromisoformat(world.START + "T00:00").astimezone()


def moment(day, hhmm):
    h, m = (int(x) for x in hhmm.split(":"))
    return DAY1 + timedelta(days=day - 1, hours=h, minutes=m)


def truth(probe, log=None):
    """Everything said before the probe was asked: the real log when there is one ([(at, role, text)],
    Avy's replies included, since she may rightly remember what she said), else the scripted lines."""
    asked = moment(probe["day"], probe["at"])
    if log:
        lines = [f"[{datetime.fromisoformat(at):%b %d, %I:%M %p}] {'Shreyas' if role == 'user' else 'Avy'}: {text}"
                 for at, role, text in log if datetime.fromisoformat(at) < asked]
    else:
        lines = [f"[{moment(s['day'], s['at']):%b %d, %I:%M %p}] " + " / ".join(f"{'Shreyas' if w == 'user' else 'Avy'}: {t}" for w, t in s["lines"])
                 for s in world.SESSIONS if moment(s["day"], s["at"]) < asked]
    return "\n".join(lines) or "(nothing yet)"


def grade(probe, answer, model="deepseek-v4-pro", say=print, log=None, passes=2):
    """Graded `passes` times independently: scores are averaged, and something counts as made up only
    if every pass says so (a single judge is noisy; the same answer can get 0 and 1)."""
    results = [one_grade(probe, answer, model, say, log) for _ in range(passes)]
    good = [r for r in results if r["score"] is not None]
    if not good:
        return results[0]
    score = round(sum(r["score"] for r in good) / len(good), 2)
    marks = []
    for i in range(len(probe["points"])):
        verdicts = [r["marks"][i]["verdict"] for r in good if i < len(r["marks"])]
        value = sum({"met": 1, "partly": 0.5}.get(v, 0) for v in verdicts) / max(1, len(verdicts))
        verdict = "met" if value >= 0.75 else "partly" if value >= 0.25 else "missed"
        marks.append({"verdict": verdict, "why": " / ".join(dict.fromkeys(r["marks"][i]["why"] for r in good if i < len(r["marks"])))})
    invented = all(r["invented"] for r in good)
    return {"score": score, "marks": marks, "invented": invented,
            "invented_what": " / ".join(r["invented_what"] for r in good if r["invented"]) if invented else "",
            "passes": [r["score"] for r in good], "cost": round(sum(r["cost"] for r in results), 5)}


def one_grade(probe, answer, model, say, log):
    convo = [{"role": "system", "content": "You grade answers from Avy, a personal assistant with a memory of her past "
              "conversations with Shreyas. Be strict but fair: a point is met only if the answer actually makes it "
              "(in any words), partly if it gestures at it, missed otherwise. Then say whether the answer states as "
              "fact anything about Shreyas's life that nothing in the conversations below supports (things he or Avy "
              "said anywhere count as supported; presenting a guess as fact doesn't). Examples inside a point are only "
              "examples. Answer by calling grade."},
             {"role": "user", "content": f"Everything said in their conversations before this question, in order:\n{truth(probe, log)}\n\n"
              f"The question, asked on {moment(probe['day'], probe['at']):%b %d}: {probe['ask']}\n\nAvy's answer:\n{answer}\n\n"
              "Points a good answer makes:\n" + "\n".join(f"{i}. {p}" for i, p in enumerate(probe["points"], 1))}]
    for attempt in range(3):
        try:
            reply = llm.call(convo, TOOL, model=model, max_tokens=2000)
            g, problem = llm.read_call(reply, "grade")
            if g and isinstance(g.get("points"), list):
                verdicts = {int(p.get("point", 0)): p for p in g["points"]}
                marks = [verdicts.get(i, {"verdict": "missed", "why": "not graded"}) for i in range(1, len(probe["points"]) + 1)]
                score = sum({"met": 1, "partly": 0.5}.get(m["verdict"], 0) for m in marks) / len(marks)
                return {"score": round(score, 2), "marks": [{"verdict": m["verdict"], "why": m.get("why", "")} for m in marks],
                        "invented": bool(g.get("invented")), "invented_what": g.get("invented_what") or "",
                        "cost": round(llm.cost(reply.get("usage") or {}, model), 5)}
        except Exception as e:
            say(f"     (judge retry: {e})")
            time.sleep(3)
    return {"score": None, "marks": [], "invented": None, "invented_what": "", "cost": 0}


def needed(probe, found):
    """Which of the probe's needs ("basil", or one sitting: "basil@14") the found tags cover."""
    covered = []
    for need in probe["needs"]:
        thread, _, day = need.partition("@")
        if any(t == thread and (not day or d == int(day)) for t, d in found):
            covered.append(need)
    return covered


def retrieval(probe, items, tokens=0):
    """items: for each thing memory brought, the set of (thread, day) tags of the words it rests on."""
    found = set().union(*items) if items else set()
    threads = {n.partition("@")[0] for n in probe["needs"]}
    noise = sum(1 for tg in items if not any(t in threads for t, _ in tg))
    covered = needed(probe, found)
    return {"items": len(items), "covered": covered, "coverage": round(len(covered) / len(probe["needs"]), 2) if probe["needs"] else None,
            "noise": noise, "noise_share": round(noise / len(items), 2) if items else 0.0, "tokens": tokens}
