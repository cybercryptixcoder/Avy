"""Offline checks of dreaming (mind/dream.py) with a scripted model: it sweeps the whole memory, judges distant
pairs, thinks about wandering, hub and bridge focuses, all at its own thinking level (max by default) instead of
the /mind: setting, stays within its time and money, can be woken, and leaves a record.

    python3 tests/test_dream.py
"""

import json
import re
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import memory  # noqa: E402
from mind import dream, llm, worker  # noqa: E402

fails = []


def ok(name, condition, detail=""):
    print(("ok    " if condition else "FAIL  ") + name + ("" if condition else f"   ({str(detail)[:400]})"))
    if not condition:
        fails.append(name)


asked = []
expensive = {"on": False}


def scripted(payload):
    """Answers every job the way a cautious model might: connects the first pair, infers one thing per Think."""
    asked.append(payload)
    name = payload["tools"][0]["function"]["name"]
    text = payload["messages"][-1]["content"]
    if name == "judge_connections":
        pairs = re.findall(r"^(p\d+) ", text, re.M)
        args = {"verdicts": [{"pair": p, "connect": i == 0, "kind": "like" if i == 0 else None, "from": None,
                              "reason": "the same idea in two places" if i == 0 else ""} for i, p in enumerate(pairs)]}
    elif name == "write_inferences":
        handles = re.findall(r"^(k\d+) ", text, re.M)
        args = {"inferences": [], "edges": []}
    elif name == "recheck":
        items = re.findall(r"^((?:k|c)\d+) ", text, re.M)
        args = {"verdicts": [{"item": i, "verdict": "holds", "title": None, "text": None, "certainty": None, "kind": None,
                              "reason": None, "why": "still holds"} for i in items]}
    else:
        args = {}
    time.sleep(0.02)
    return {"choices": [{"finish_reason": "tool_calls", "message": {"role": "assistant", "content": "",
            "tool_calls": [{"id": "c", "type": "function", "function": {"name": name, "arguments": json.dumps(args)}}]}}],
            "usage": {"prompt_tokens": 4000, "completion_tokens": 30000 if expensive["on"] else 3000}}


llm.app.update(ask=scripted, prices={"cache_hit": 0.006, "cache_miss": 0.30, "output": 1.20}, effort=lambda: "none")
mem = memory.Memory(Path(tempfile.mkdtemp()) / "mem.db")
lines = ["ants leave scent trails that fade when nobody uses them", "campus lawns get worn trails where students actually walk",
         "cities pave desire trails where people actually walk", "my sourdough starter is called Bubbles",
         "Bubbles the starter needs feeding twice a day", "my thesis is about graph search",
         "graph search explores the frontier first", "I'm training for a half marathon", "I hate running honestly"]
applied = 0
for i, t in enumerate(lines, 1):                     # each in its own sitting, so nothing is "nearby" by default
    mem.add("user", t)
    rs, _ = mem.apply_all([{"op": "add_episode", "first": i, "last": i, "headline": t[:30]},
                           {"op": "add_node", "ref": "n1", "shape": "information", "label": "note", "title": t[:40], "text": t + ".",
                            "evidence": [(i, 0, len(t), 1)], "episode": "@episode"}])
    applied += sum(r["applied"] for r in rs)
rs, refs = mem.apply_all([{"op": "add_node", "ref": "n1", "shape": "thing", "label": "project", "title": "The thesis",
                           "text": "His thesis.", "evidence": [(6, 3, 9, 1)]},
                          {"op": "connect", "a": 6, "b": "n1", "kind": "part_of", "reason": "it is what the thesis is about",
                           "support": {"kind": "inferred"}},
                          {"op": "connect", "a": 7, "b": "n1", "kind": "part_of", "reason": "it is part of the thesis work",
                           "support": {"kind": "inferred"}}])
ok("a small memory to dream about", applied == 2 * len(lines) and all(r["applied"] for r in rs), [r["why"] for r in rs])

d = dream.Dream(main=lambda: mem)
events = []
d.tell = events.append
ok("waking someone who isn't asleep says so", d.stop() is not None)
problem = d.start(hours=0.004, max_dollars=5, effort="max")         # about 15 seconds
ok("dreaming starts", problem is None, problem)
ok("...and won't start twice", d.start() is not None)
end = time.time() + 60
while d.thread.is_alive() and time.time() < end:
    time.sleep(0.2)
s = d.status()
ok("it wakes by itself when its time is up, or when a whole lap round memory finds nothing new",
   s["state"] == "awake" and s["last"] and "runs" in s["last"]["summary"] and s["runs"] < 200, s)
efforts = {p["reasoning_effort"] for p in asked}
ok("every dream job thinks at the dream's level (max), not the /mind: setting (none)", efforts == {"max"}, efforts)
ok("...so the tool is offered, not forced (Luminal refuses a forced call while thinking)",
   all(p["tool_choice"] == "auto" for p in asked))
jobs = {p["tools"][0]["function"]["name"] for p in asked}
ok("it sweeps for distant pairs and thinks", {"judge_connections", "write_inferences"} <= jobs, jobs)
ok("...and the sweep goes round the memory, longest-undreamt first", s["swept"] >= 6
   and sum(1 for n in mem.current_nodes() if mem.mark(f"dream.node.{n['chain']}")) >= 6, s)
ok("connections it judged worth making were made, through the one door", s["connected"] >= 1
   and mem.value("SELECT COUNT(*) FROM journal WHERE op = 'connect' AND result = 'applied'") >= 3, s)
thinks = [p["messages"][-1]["content"] for p in asked if p["tools"][0]["function"]["name"] == "write_inferences"]
ok("its focuses: wandering from a node, a hub, two hubs side by side", any("dreaming from" in t for t in thinks)
   and (any("dreaming about" in t for t in thinks) or len(mem.hubs()) == 0), [t[:60] for t in thinks])
rec = mem.row("SELECT * FROM runs WHERE job = 'dream'")
ok("a dream leaves a record: what it did, what it cost", rec and "runs" in rec["focus"] and rec["cost"] > 0, rec)
ok("the network's health is measured at the end", mem.value("SELECT COUNT(*) FROM health") >= 1)
ok("the looking glass hears about it as it goes", any("dream" in e for e in events) and len(events) > 3)

asked.clear()
expensive["on"] = True
for n in mem.current_nodes():                        # a fresh night: everything is due a sweep again
    mem.set_mark(f"dream.node.{n['chain']}", "")
d.start(hours=1, max_dollars=0.02, effort="high")
end = time.time() + 60
while d.thread.is_alive() and time.time() < end:
    time.sleep(0.2)
ok("it stops when the money runs out", d.status()["state"] == "awake" and d.status()["spent"] >= 0.02, d.status())
ok("...at the level it was given (high)", {p["reasoning_effort"] for p in asked} == {"high"})
expensive["on"] = False

d.start(hours=1, max_dollars=10)
time.sleep(0.05)
ok("it can be woken", d.stop() is None)
end = time.time() + 30
while d.thread.is_alive() and time.time() < end:
    time.sleep(0.2)
ok("...and wakes properly, with its record", d.status()["state"] == "awake" and mem.value("SELECT COUNT(*) FROM runs WHERE job = 'dream'") == 3,
   (d.status()["state"], mem.value("SELECT COUNT(*) FROM runs WHERE job = 'dream'")))

print(f"\n{len(fails)} failed" + (": " + ", ".join(fails) if fails else ""))
sys.exit(1 if fails else 0)
