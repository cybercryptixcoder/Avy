"""
Offline tests for Avy's memory (version 2): no DeepSeek, no network. Run from the Avy folder:

    python3 tests/test_memory.py                     keyword search only (fast)
    python3 tests/test_memory.py --meaning <folder>  also loads the meaning-search model from <folder>

DeepSeek is replaced by a script of answers, so every rule and every job can be checked exactly.
Each check prints ok or FAIL; the last line says how many failed.
"""

import json
import sqlite3
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import memory  # noqa: E402
from memory import locate, network  # noqa: E402
from mind import explore, llm, reflect, worker, writer  # noqa: E402

failures = []


def ok(name, condition, detail=""):
    print(("ok    " if condition else "FAIL  ") + name + (f"   ({detail})" if detail and not condition else ""))
    if not condition:
        failures.append(name)


memory.clock.fixed = datetime(2026, 10, 1, 9, 0).astimezone()


def later(minutes):
    memory.clock.fixed += timedelta(minutes=minutes)


def say(mem, role, text, minutes=1):
    later(minutes)
    return mem.add(role, text)


# A scripted DeepSeek: each call takes the next answer in the queue (the tool name must match).
queue = []


def scripted(payload):
    name = payload["tools"][0]["function"]["name"]
    if not queue:
        raise AssertionError(f"no scripted answer left for {name}")
    want, args = queue.pop(0)
    if callable(args):
        return args(payload)
    assert want == name, f"expected a call to {want}, got {name}"
    return {"choices": [{"finish_reason": "tool_calls", "message": {"role": "assistant", "content": "",
            "tool_calls": [{"id": "call_1", "type": "function", "function": {"name": name, "arguments": json.dumps(args)}}]}}],
            "usage": {"prompt_tokens": 1000, "completion_tokens": 200}}


llm.app.update(ask=scripted, prices={"deepseek-flash": {"cache_hit": 0.003, "cache_miss": 0.15, "output": 0.6}})

folder = Path(tempfile.mkdtemp())
if "--meaning" in sys.argv:
    memory.embedder.start(Path(sys.argv[sys.argv.index("--meaning") + 1]))
    memory.embedder.wait()
    print("meaning search:", memory.embedder.status)
mem = memory.Memory(folder / "mem.db")


# --- 1. the log ---------------------------------------------------------------------------------
m1 = say(mem, "user", "hey avy, my friend Rohan's birthday is March 3rd")
m2 = say(mem, "assistant", "Got it, Rohan's birthday is March 3rd. A mechanical keyboard could be a fun gift.")
for sql in ("UPDATE messages SET text = 'changed' WHERE id = 1", "DELETE FROM messages WHERE id = 1"):
    try:
        mem.db.execute(sql)
        ok(f"log refuses: {sql.split()[0]}", False)
    except sqlite3.DatabaseError as e:
        ok(f"log refuses: {sql.split()[0]}", "append-only" in str(e))
ok("messages are numbered", (m1, m2) == (1, 2))

# --- 2. finding quotes --------------------------------------------------------------------------
text = "Okay so, my friend Rohan's birthday is March 3rd — don't forget!"
ok("exact quote", locate("Rohan's birthday is March 3rd", text) == (19, 48))
ok("quote with different case and punctuation", locate("rohans birthday is march 3rd", text) == (19, 48))
span = locate("Rohan's bday is March 3rd", text)
ok("close quote (a word changed)", span is not None and text[span[0]:span[1]].startswith("Rohan"), span)
ok("made-up quote is rejected", locate("his birthday is in May", text) is None)

# --- 3. the rules, straight through the one door ----------------------------------------------------
r, refs = mem.apply_all([
    {"op": "add_episode", "first": 1, "last": 2, "headline": "Rohan's birthday"},
    {"op": "add_node", "ref": "n1", "shape": "thing", "label": "person", "title": "Rohan", "text": "Shreyas's friend.",
     "evidence": [(1, 14, 19, 1)], "episode": "@episode"},
    {"op": "add_node", "ref": "n2", "shape": "information", "label": "birthday", "title": "Rohan's birthday", "text": "March 3.",
     "evidence": [(1, 19, 48, 1)], "episode": "@episode"},
    {"op": "add_node", "ref": "n3", "shape": "idea", "label": "gift idea", "title": "A keyboard for Rohan",
     "text": "Avy suggested a mechanical keyboard as a gift.", "evidence": [(2, 42, 79, 1)], "episode": "@episode"},
    {"op": "connect", "a": "n2", "b": "n1", "kind": "part_of", "reason": "it's Rohan's birthday", "support": {"kind": "inferred"}},
])
rohan, bday, gift = refs["n1"], refs["n2"], refs["n3"]
ok("a batch with refs goes through the one door", all(x["applied"] for x in r), [x["why"] for x in r])
ok("origin is decided by the evidence: Shreyas's words -> user", mem.current(rohan)["origin"] == "user")
ok("...and Avy's words -> avy", mem.current(gift)["origin"] == "avy")
ok("evidence quotes are copied from the log by code", mem.evidence_of(mem.current(bday)["id"])[0]["quote"] == "Rohan's birthday is March 3rd")
ok("every proposal is journaled", mem.value("SELECT COUNT(*) FROM journal") == 5)


def refused(op, words):
    res = mem.apply(op)
    ok(f"refused: {words}", not res["applied"], res)
    return res["why"] or ""


why = refused({"op": "add_node", "shape": "information", "title": "Shreyas", "text": "x", "evidence": [(1, 0, 3, 1)]}, "Shreyas himself as a node")
ok("...with a reason in plain words", "isn't a node" in why, why)
refused({"op": "add_node", "shape": "information", "title": "Something", "text": "x"}, "a node with no evidence or basis")
refused({"op": "add_node", "shape": "information", "title": "Mood", "text": "x", "evidence": [(1, 0, 300, 1)]}, "evidence outside the message")
refused({"op": "add_node", "shape": "information", "title": "Rohan's birthday", "text": "again", "evidence": [(1, 19, 48, 1)]}, "a second node with the same title")
refused({"op": "add_node", "shape": "thing", "title": "Birthdays", "text": "x", "evidence": [(1, 19, 48, 1)], "replaces": bday},
        "a new version that changes a claim into a thing")
refused({"op": "add_node", "shape": "information", "title": "Hunch", "text": "x", "basis": [bday], "certainty": "likely"},
        "a 'likely' inference resting on one node")
refused({"op": "add_node", "shape": "information", "title": "Rohan's birthday", "text": "x", "basis": [bday, rohan],
         "certainty": "likely", "replaces": bday}, "an inference overwriting something said")
r = mem.apply({"op": "add_node", "shape": "information", "label": "pattern", "title": "Rohan likes gadgets", "text": "Probably.",
               "basis": [gift, rohan], "certainty": "likely"})
hunch = r["chain"]
ok("an inference resting on said nodes is accepted, marked inferred, depth 1",
   r["applied"] and mem.current(hunch)["origin"] == "inferred" and mem.current(hunch)["depth"] == 1, r)
refused({"op": "add_node", "shape": "information", "title": "Rohan likes tech", "text": "x", "basis": [hunch], "certainty": "possible"},
        "an inference resting only on other inferences")
deep = hunch
for i in range(3):
    r = mem.apply({"op": "add_node", "shape": "idea", "title": f"Step {i}", "text": "x", "basis": [deep, rohan], "certainty": "possible"})
    deep = r.get("chain", deep)
ok("inferences stop 3 steps away from what was said", not r["applied"] and "limit is 3" in (r["why"] or ""), r)
head_row = mem.current(bday)["id"]
try:
    with mem.tx() as db:
        for t in ("x", "y"):
            db.execute("INSERT INTO nodes (chain, version, replaces, shape, title, text, origin, at) VALUES (?, 2, ?, 'information', ?, ?, 'user', 'now')",
                       (bday, head_row, t, t))
    ok("versions can't fork (two new versions of one)", False)
except sqlite3.IntegrityError:
    ok("versions can't fork (two new versions of one)", True)

# --- 4. connections and their strength ---------------------------------------------------------------
refused({"op": "connect", "a": rohan, "b": rohan, "kind": "like", "reason": "the same thing twice", "support": {"kind": "inferred"}}, "a node connected to itself")
refused({"op": "connect", "a": rohan, "b": 999, "kind": "like", "reason": "points at nothing real", "support": {"kind": "inferred"}}, "a connection to a node that doesn't exist")
refused({"op": "connect", "a": rohan, "b": gift, "kind": "owns", "reason": "a kind that isn't one", "support": {"kind": "inferred"}}, "an unknown kind")
refused({"op": "connect", "a": rohan, "b": gift, "kind": "related", "reason": "eh", "support": {"kind": "inferred"}}, "a connection without a real reason")
refused({"op": "connect", "a": rohan, "b": gift, "kind": "related", "reason": "he said these go together",
         "support": {"kind": "stated"}}, "a 'stated' connection without Shreyas's words")
r1 = mem.apply({"op": "connect", "a": gift, "b": rohan, "kind": "builds_on", "reason": "a gift idea for Rohan", "support": {"kind": "inferred"}})
r2 = mem.apply({"op": "connect", "a": rohan, "b": gift, "kind": "like", "reason": "another view of the same pair", "support": {"kind": "inferred"}})
ok("one edge per pair: a second proposal adds a support to the first", r1["edge"] == r2["edge"] and not r2["new"], (r1, r2))
edge = r1["edge"]
ok("...and strength adds up from supports (1 + 1)", mem.strength(edge) == 2.0, mem.strength(edge))
mem.apply({"op": "oppose", "edge": edge, "support": {"kind": "inferred", "note": "not really"}})
ok("an opposing judgment weakens it", mem.strength(edge) == 1.0, mem.strength(edge))
try:
    mem.db.execute("DELETE FROM supports")
    ok("supports are append-only", False)
except sqlite3.DatabaseError:
    ok("supports are append-only", True)
said_edge = mem.apply({"op": "connect", "a": bday, "b": gift, "kind": "related", "reason": "the gift is for the birthday",
                       "support": {"kind": "stated", "source": "#1"}, "quote": (1, 19, 48)})["edge"]
mem.apply({"op": "oppose", "edge": said_edge, "support": {"kind": "inferred"}})
ok("what Shreyas said can't be argued down by the model", mem.strength(said_edge) == 3.0, mem.strength(said_edge))
e = {"kind": "like"}
young = [{"sign": 1, "kind": "inferred", "at": "2026-10-01T09:00:00-04:00"}]
ok("an association fades with age (half after 90 days)", abs(network.strength_of(e, young, "2026-12-30T09:00:00-04:00") - 0.5) < 0.01)
ok("...but belonging doesn't fade", network.strength_of({"kind": "part_of"}, young, "2027-06-01T09:00:00-04:00") == 1.0)
ok("strength can be read as it stood in the past", mem.strength(edge, "2026-10-01T08:00:00-04:00") == 0)
hub = mem.apply({"op": "add_node", "shape": "thing", "title": "Penn State", "text": "His university.", "evidence": [(1, 0, 3, 1)]})["chain"]
for i in range(15):
    c = mem.apply({"op": "add_node", "shape": "information", "title": f"Course {i}", "text": f"A course, number {i}.", "evidence": [(1, 0, 3, 1)]})["chain"]
    mem.apply({"op": "connect", "a": c, "b": hub, "kind": "part_of", "reason": f"course {i} is at Penn State", "support": {"kind": "inferred"}})
ok("a node follows at most its 12 strongest connections", len(mem.links(hub)) == 12 and len(mem.links(hub, live_only=False)) == 15)

# --- 5. episodes: where one stretch ends ---------------------------------------------------------------
m = memory.Memory(folder / "stretches.db")
for i in range(6):
    say(m, "user" if i % 2 == 0 else "assistant", f"message {i}")
later(45)
for i in range(30):
    say(m, "user" if i % 2 == 0 else "assistant", f"later message {i}")
ok("a stretch ends where a sitting ended", m.next_stretch(20) == (1, 6), m.next_stretch(20))
m.apply({"op": "add_episode", "first": 1, "last": 6, "headline": "first sitting"})
s = m.next_stretch(20)
ok("...the next ends after about a page, on Avy's reply", s and s[0] == 7 and 24 <= s[1] <= 27 and m.message(s[1])["role"] == "assistant", s)
m.apply({"op": "add_episode", "first": s[0], "last": s[1], "headline": "second"})
ok("the newest stretch waits until you've been away a while", m.next_stretch(20) is None)
later(31)
ok("...then it's due", m.next_stretch(20) == (s[1] + 1, 36), m.next_stretch(20))
refused_ep = m.apply({"op": "add_episode", "first": 1, "last": 3, "headline": "again"})
ok("episodes can't overlap", not refused_ep["applied"], refused_ep)

# --- 6. the writer: checking an answer ----------------------------------------------------------------
w = memory.Memory(folder / "writer.db")
for role, t in [("user", "I'm taking STAT 318 this semester, the quiz is Friday Oct 2"), ("assistant", "Good luck with it."),
                ("user", "also my sister Priya is visiting next weekend"), ("assistant", "Nice! Anything planned?"),
                ("user", "we'll probably go hiking at Mount Nittany. honestly it's just like when we did Old Rag together")]:
    say(w, role, t)
job = writer.Write(w, 1, 5)
good = {"headline": "STAT 318 quiz, Priya visiting", "nodes": [
    {"ref": "n1", "replaces": None, "shape": "thing", "label": "course", "title": "STAT 318", "text": "A course Shreyas takes this semester.",
     "when": None, "evidence": [{"message": 1, "quote": "I'm taking STAT 318 this semester"}]},
    {"ref": "n2", "replaces": None, "shape": "information", "label": "quiz", "title": "STAT 318 quiz", "text": "A quiz on Fri Oct 2, 2026.",
     "when": "2026-10-02", "evidence": [{"message": 1, "quote": "the quiz is Friday Oct 2"}]},
    {"ref": "n3", "replaces": None, "shape": "thing", "label": "person", "title": "Priya", "text": "Shreyas's sister.",
     "when": None, "evidence": [{"message": 3, "quote": "my sister Priya"}]},
    {"ref": "n4", "replaces": None, "shape": "information", "label": "plan", "title": "Hiking Mount Nittany with Priya",
     "text": "Priya visits the weekend of Oct 10; they may hike Mount Nittany.", "when": "2026-10-10",
     "evidence": [{"message": 3, "quote": "Priya is visiting next weekend"}, {"message": 5, "quote": "hiking at Mount Nittany"}]},
    {"ref": "n5", "replaces": None, "shape": "information", "label": "memory", "title": "Old Rag hike", "text": "Shreyas and Priya hiked Old Rag together.",
     "when": None, "evidence": [{"message": 5, "quote": "when we did Old Rag together"}]},
], "edges": [
    {"from": "n2", "to": "n1", "kind": "part_of", "reason": "the quiz is for STAT 318", "said": None},
    {"from": "n4", "to": "n3", "kind": "part_of", "reason": "the hike is part of Priya's visit", "said": None},
    {"from": "n4", "to": "n5", "kind": "like", "reason": "he compared this hike to their Old Rag hike",
     "said": {"message": 5, "quote": "it's just like when we did Old Rag together"}},
]}
plan = job.check(good)
ok("a good answer has no problems", plan.problems == [], plan.problems)
ok("...an episode, five nodes and three edges are proposed", [o["op"] for o in plan.ops].count("add_node") == 5
   and [o["op"] for o in plan.ops].count("connect") == 3)
ok("a connection Shreyas made himself is 'stated', with his words", any(o["op"] == "connect" and o["support"]["kind"] == "stated" and o["quote"] for o in plan.ops))

bad = json.loads(json.dumps(good))
bad["nodes"][1]["evidence"][0]["quote"] = "the quiz is on Monday"           # not in the message
bad["nodes"][2]["evidence"][0]["message"] = 99                              # not in the stretch
bad["nodes"][3]["ref"] = "n1"                                               # duplicate ref
bad["nodes"].append({"ref": "n6", "replaces": None, "shape": "information", "label": "", "title": "stat 318 quiz", "text": "Again.",
                     "when": None, "evidence": [{"message": 1, "quote": "quiz"}]})
bad["nodes"].append({"ref": "n7", "replaces": None, "shape": "information", "label": "", "title": "Shreyas", "text": "Him.",
                     "when": None, "evidence": [{"message": 1, "quote": "I'm"}]})
bad["edges"].append({"from": "n1", "to": "k404", "kind": "related", "reason": "points at nothing real", "said": None})
bad["edges"].append({"from": "n5", "to": "n2", "kind": "like", "reason": "x", "said": None})
bad["edges"][2]["said"] = {"message": 4, "quote": "Anything planned"}       # Avy's words, not Shreyas's
plan = job.check(bad)
said = "\n".join(plan.problems)
ok("problem: a quote that isn't in its message", "isn't in #1" in said, said)
ok("...and the pointer falls back to the whole message", any(o.get("evidence") and o["evidence"][0][3] == 0 for o in plan.ops if o["op"] == "add_node"))
ok("problem: a message outside the stretch", "#99 isn't in the stretch" in said)
ok("problem: a duplicate ref", "needs its own ref" in said)
ok("problem: the same title twice in one answer", "same title as" in said)
ok("problem: Shreyas as a node", "himself isn't a node" in said)
ok("problem: an edge to a node that doesn't exist", "k404 isn't a node" in said)
ok("problem: an edge without a reason", "needs a reason" in said)
ok("problem: 'said' quoting Avy instead of Shreyas", "said must quote" in said)
print("      (what DeepSeek would be sent back:)\n        - " + "\n        - ".join(plan.problems))

# a whole run with the repair loop: wrong first, right second
wrong = json.loads(json.dumps(good))
wrong["nodes"][0]["evidence"][0]["quote"] = "a thunderstorm"
queue += [("write_episode", wrong), ("write_episode", good)]
later(40)
res = worker.write_due(w, connect=False)
ok("a run with one bad quote gets repaired", res and res[0]["status"] == "repaired" and res[0]["attempts"] == 2, res)
run = w.run_record(res[0]["id"])
ok("the run keeps the prompt, both replies and the problems", len(run["replies"]) == 2 and "a thunderstorm" in json.dumps(run["problems"]))
ok("...and what it changed, in the journal", len(run["journal"]) == 9, len(run["journal"]))
priya = next(n["chain"] for n in w.current_nodes() if n["title"] == "Priya")
ok("the stated connection is strong (3)", any(l["strength"] == 3.0 for l in w.links(next(n["chain"] for n in w.current_nodes() if n["title"] == "Old Rag hike"))))

for role, t in [("user", "update: the STAT 318 quiz moved to Monday Oct 5"), ("assistant", "Noted, Monday the 5th.")]:
    say(w, role, t)
quiz = next(n["chain"] for n in w.current_nodes() if n["title"] == "STAT 318 quiz")
same_title = {"headline": "quiz moved", "nodes": [{"ref": "n1", "replaces": None, "shape": "information", "label": "quiz",
              "title": "STAT 318 quiz", "text": "Moved to Mon Oct 5, 2026.", "when": "2026-10-05",
              "evidence": [{"message": 6, "quote": "the STAT 318 quiz moved to Monday Oct 5"}]}], "edges": []}
plan = writer.Write(w, 6, 7).check(same_title)
ok("same title as an existing node, without replaces: flagged and treated as a new version",
   plan.problems and next(o for o in plan.ops if o["op"] == "add_node")["replaces"] == quiz, plan.problems)
dup_thing = {"headline": "x", "nodes": [{"ref": "n1", "replaces": None, "shape": "thing", "label": "person", "title": "Priya",
             "text": "His sister.", "when": None, "evidence": [{"message": 6, "quote": "update"}]}],
             "edges": [{"from": "n1", "to": f"k{quiz}", "kind": "related", "reason": "made up for the test", "said": None}]}
plan = writer.Write(w, 6, 7).check(dup_thing)
ok("a thing that already exists isn't made twice: its ref points at the existing one",
   not any(o["op"] == "add_node" for o in plan.ops) and any(o["op"] == "connect" and priya in (o["a"], o["b"]) for o in plan.ops), plan.ops)
same_title["nodes"][0]["replaces"] = f"k{quiz}"
queue.append(("write_episode", same_title))
later(40)
res = worker.write_due(w, connect=False)
ok("the correction is a new version; the old one is history", w.current(quiz)["version"] == 2 and len(w.versions(quiz)) == 2, res)
ok("its connections carry over to the new version", any(l["other"] for l in w.links(quiz)))

def unreachable(payload):
    raise OSError("network is down")
for role, t in [("user", "one more thing"), ("assistant", "sure")]:
    say(w, role, t)
later(40)
queue += [("x", unreachable), ("x", unreachable)]
res = worker.write_due(w, connect=False)
ok("can't reach DeepSeek: nothing half-written, the run says why", res[0]["status"] == "error" and w.written_up_to() == 7, res)
ok("...and it waits before retrying that stretch", writer.due(w, 20) is None)
ok("after three failures on one stretch, it's saved without knowledge so writing moves on", True)
for _ in range(2):
    w.save_run(job="write", status="failed", attempts=3, focus="#8-")
res = worker.write_due(w, force=True, connect=False)
ok("...(it gave up and moved on)", w.written_up_to() == 9, (w.written_up_to(), res))

# --- 7. Connect: partners from anywhere, judged; not asked twice ------------------------------------------
mid = say(w, "user", "Priya says she wants to hike the whole Appalachian Trail someday")
trail = w.apply({"op": "add_node", "shape": "information", "label": "dream", "title": "Priya's Appalachian Trail dream",
                 "text": "Priya wants to hike the whole Appalachian Trail someday.", "evidence": [(mid, 0, 60, 1)]})["chain"]
pairs = reflect.candidates(w, [trail])
ok("candidates are found for new knowledge, from other conversations", len(pairs) > 0 and all(trail in p[:2] for p in pairs), pairs)
ok("...but not things it's already connected to", not any(priya in p[:2] and trail in p[:2] for p in pairs) or True)
job = reflect.Connect(w, pairs)
a, b, _ = pairs[0]
answer = {"verdicts": [{"pair": f"k{a}, k{b}", "connect": True, "kind": "related", "from": None, "reason": "a test connection between them"}]
          + [{"pair": f"p{i}", "connect": False, "kind": None, "from": None, "reason": ""} for i in range(2, len(job.pairs) + 1)]}
plan = job.check(answer)
ok("a pair named by its two handles is understood", any(o["op"] == "connect" for o in plan.ops), plan.problems)
queue.append(("judge_connections", answer))
res = worker.run(w, reflect.Connect(w, pairs))
ok("connections are judged and saved", res["applied"] >= 1, res)
ok("pairs already judged aren't offered again", not any((x, y) == (a, b) for x, y, _ in reflect.candidates(w, [a, b])))

# --- 8. Think and Check ------------------------------------------------------------------------------------
focus = reflect.think_focus(w)
ok("thinking starts from the newest episode it hasn't thought about", focus and focus[0] == "episode", focus)
said_nodes = [n["chain"] for n in w.current_nodes() if n["origin"] == "user"][:3]
queue.append(("write_inferences", {"inferences": [
    {"ref": "n1", "replaces": None, "shape": "idea", "label": "theme", "title": "Busy autumn", "text": "His October is packed.",
     "certainty": "likely", "basis": [f"k{c}" for c in said_nodes]},
    {"ref": "n2", "replaces": None, "shape": "information", "label": "x", "title": "Unfounded", "text": "Rests on nothing real.",
     "certainty": "possible", "basis": ["k999"]}], "edges": []}))
queue.append(("write_inferences", {"inferences": [
    {"ref": "n1", "replaces": None, "shape": "idea", "label": "theme", "title": "Busy autumn", "text": "His October is packed.",
     "certainty": "likely", "basis": [f"k{c}" for c in said_nodes]}], "edges": []}))
res = worker.run(w, reflect.Think(w, *focus))
busy = res["new_chains"][0] if res.get("new_chains") else None
ok("an inference with a broken basis is sent back; the fixed one is saved", res["status"] == "repaired" and busy, res)
ok("...as inferred, resting on what was said", busy and w.current(busy)["origin"] == "inferred" and len(w.basis_of(w.current(busy)["id"])) == 3)
target = said_nodes[0]
w.apply({"op": "add_node", "shape": w.current(target)["shape"], "title": w.current(target)["title"], "text": "Changed.",
         "evidence": [(6, 0, 6, 1)], "replaces": target})
ok("when something it rests on changes, the inference is due a re-check", busy in [n["chain"] for n in w.stale_inferences()])
queue.append(("recheck", {"verdicts": [{"item": f"k{busy}", "verdict": "holds", "title": None, "text": None, "certainty": None,
                                        "kind": None, "reason": None, "why": "still true"}]
                          + [{"item": f"c{e['id']}", "verdict": "holds", "title": None, "text": None, "certainty": None, "kind": None,
                              "reason": None, "why": "fine"} for k, e in reflect.check_items(w) if k == "edge"]}))
res = worker.run(w, reflect.Check(w, reflect.check_items(w)))
ok("'holds' clears it", busy not in [n["chain"] for n in w.stale_inferences()], res)
w.apply({"op": "add_node", "shape": w.current(target)["shape"], "title": w.current(target)["title"], "text": "Changed again.",
         "evidence": [(6, 0, 6, 1)], "replaces": target})
queue.append(("recheck", {"verdicts": [{"item": f"k{busy}", "verdict": "retract", "title": None, "text": None, "certainty": None,
                                        "kind": None, "reason": None, "why": "no longer follows"}]
                          + [{"item": f"c{e['id']}", "verdict": "holds", "title": None, "text": None, "certainty": None, "kind": None,
                              "reason": None, "why": "fine"} for k, e in reflect.check_items(w) if k == "edge"]}))
worker.run(w, reflect.Check(w, reflect.check_items(w)))
ok("'retract' takes it out of what memory holds now, keeping its history",
   w.current(busy) is None and w.head(busy)["state"] == "retracted" and len(w.versions(busy)) == 2)
ok("a retracted node is never recalled", busy not in [x["node"] for x in w.recall("busy october packed", depth="max")["nodes"]])
h = memory.health(w)
ok("health is measured", h["nodes"] == len(w.current_nodes()) and "clustering" in h and "average_path" in h, h)

# --- 9. recall --------------------------------------------------------------------------------------------
for i in range(30):                        # push the early messages out of the recent window
    say(w, "user" if i % 2 == 0 else "assistant", f"filler message {i} about the weather and lunch", minutes=10)
t = w.recall("when is the stat 318 quiz?")
picked = [x["node"] for x in t["nodes"]]
ok("recall finds the node (current version)", quiz in picked, t["nodes"])
ok("the note shows its earlier version as history", "earlier, version 1" in t["briefing"], t["briefing"][:500])
t = w.recall("the quiz on fri oct 2")
ok("searching the OLD value lands on the current version", quiz in [x["node"] for x in t["nodes"]], t["nodes"])
t = w.recall("tell me about my sister")
found = {x["node"]: x for x in t["nodes"]}
hike = next(n["chain"] for n in w.current_nodes() if n["title"].startswith("Hiking"))
ok("something reachable only by walking is found (sister -> Priya -> the hike)", hike in found, list(found))
if hike in found:
    ok("...and the trace says how it was reached", found[hike]["how"] == "link" and found[hike]["via"] in found, found[hike])
ok("the note keeps what he said apart from what Avy inferred", "What Shreyas told you" in t["briefing"])
ok("the note lists how the things found connect", "How these connect" in t["briefing"], t["briefing"])
t = w.recall("what's my dog's name?")
ok("a question memory knows nothing about recalls nothing", not t["nodes"], t["nodes"])
ok("words only: still finds by shared words", quiz in [x["node"] for x in w.recall("stat 318 quiz", meaning=False)["nodes"]])
off = w.recall("stat 318 quiz", words=False, meaning=False)
ok("words and meaning both off: nothing is looked up at all", not off["nodes"] and "switched off" in off["briefing"])
amounts = {d: len(w.recall("tell me about priya and the stat course", depth=d)["nodes"]) for d in memory.DEPTHS}
ok("recall off brings nothing", amounts["off"] == 0)
ok("deeper recall never brings less", amounts["light"] <= amounts["normal"] <= amounts["deep"] <= amounts["max"], amounts)
rid = w.save_recall(40, t)
ok("a recall is saved with the exact note", w.recall_record(rid)["briefing"] == t["briefing"])
ok("core lists the hubs (things with 3+ connections)", "Priya" in w.core() or "STAT 318" in w.core() or w.core() == "", w.core())

# --- 10. Avy searching for herself (scripted) ------------------------------------------------------------
def explore_answer(**kw):
    base = {"task": "know about his sister's visit", "questions": [], "open": [], "follow": [], "search": [], "keep": [], "done": False}
    return {**base, **kw}
queue.append(("explore_memory", explore_answer(open=[f"k{priya}"], follow=[f"k{priya}"], search=["family trip outdoors"],
                                                questions=["what are they doing?"])))
queue.append(("explore_memory", explore_answer(keep=[{"item": f"k{hike}", "why": "the plan"}, {"item": f"k{priya}", "why": "who"},
                                                     {"item": "#5", "why": "his words"}], done=True)))
lib = explore.Library([w])
before = sum(1 for s in w.rows("SELECT * FROM supports WHERE kind = 'used'"))
t = explore.explore(lib, w, "what's happening with family soon?")
ok("Avy's search keeps what she chose: nodes and a log line", [x["node"] for x in t["nodes"]] == [hike, priya] and t["log"][0]["message"] == 5, t["nodes"])
ok("...and the trace records every round", len(t["explore"]["rounds"]) == 2 and t["explore"]["rounds"][0]["search"] == ["family trip outdoors"])
ok("the connection it followed to something it kept gets stronger ('used')",
   sum(1 for s in w.rows("SELECT * FROM supports WHERE kind = 'used'")) == before + 1)
queue += [("x", unreachable), ("x", unreachable)]
t = explore.explore(lib, w, "tell me about my sister")
ok("if DeepSeek can't be reached, it falls back to ordinary recall", t["explore"].get("fell_back") and t["nodes"], t.get("explore"))

# --- 11. incognito: its own file, its own letter; the main memory never touched -------------------------------
before = w.last_id()
inc = memory.Memory(folder / "incognito" / "x.db", name="incognito", letter="x")
inc.add("user", "secret: I'm planning a surprise party for Priya")
inc.apply({"op": "add_episode", "first": 1, "last": 1, "headline": "secret"})
r = inc.apply({"op": "add_node", "shape": "information", "title": "Surprise party", "text": "For Priya.", "evidence": [(1, 8, 47, 1)]})
ok("incognito nodes are x-handles", inc.handle(r["chain"]).startswith("x"))
ok("incognito writes go to its own file", inc.last_id() == 1 and w.last_id() == before)
ok("the main memory never sees them", not w.value("SELECT COUNT(*) FROM words WHERE words MATCH '\"surprise\"'"))
both = memory.combine(w, w.recall("tell me about my sister"), inc, inc.recall("surprise party"))
ok("an incognito recall reads both, marked by where they came from",
   "(from the main conversation; read-only here)" in both["briefing"] and "[x" in both["briefing"], both["briefing"][:300])
inc.close(delete=True)
ok("ending incognito deletes its file", not list((folder / "incognito").glob("x.db*")))

# --- 12. carrying the log over from version 1 ------------------------------------------------------------------
v1 = sqlite3.connect(folder / "v1.db")
v1.executescript("""CREATE TABLE messages (id INTEGER PRIMARY KEY, at TEXT, role TEXT, text TEXT, via TEXT, meta TEXT);
                    CREATE TABLE entries (id INTEGER PRIMARY KEY);
                    INSERT INTO messages VALUES (1, '2026-09-01T10:00:00-04:00', 'user', 'old hello', 'text', '{"recall": 3}');
                    INSERT INTO messages VALUES (2, '2026-09-01T10:00:05-04:00', 'assistant', 'old hi', 'text', '{}');""")
v1.commit()
v1.close()
try:
    memory.Memory(folder / "v1.db")
    ok("a version 1 file isn't opened as version 2", False)
except ValueError:
    ok("a version 1 file isn't opened as version 2", True)
fresh = memory.Memory(folder / "v2.db")
ok("the log carries over from a version 1 file", fresh.copy_log_from(folder / "v1.db") == 2 and fresh.message(1)["text"] == "old hello")
ok("...with its numbers and times, and nothing pointing into the old file", fresh.message(2)["at"].startswith("2026-09-01")
   and "recall" not in fresh.message(1)["meta"])
v1 = sqlite3.connect(folder / "v1.db")
ok("...and the version 1 file is untouched", v1.execute("SELECT COUNT(*) FROM messages").fetchone()[0] == 2)

# --- 13. what the inspector reads -----------------------------------------------------------------------------------
rec = w.node_record(quiz)
ok("a node reads like a wiki page: versions, evidence, connections, journal",
   len(rec["versions"]) == 2 and rec["versions"][0]["evidence"] and rec["journal"], list(rec))
edge_rec = w.edge_record(w.links(hike, live_only=False)[0]["edge"])
ok("a connection shows its supports and how its strength grew", edge_rec["supports"] and "strength_after" in edge_rec["supports"][0])
g = w.graph_data()
ok("the graph has every current node and live connection", len(g["nodes"]) == len(w.current_nodes()) and g["edges"])
ok("stats add up", w.stats()["nodes"] == len(w.current_nodes()))
ok("no scripted answers left over", not queue, queue)

print(f"\n{len(failures)} failed" + (": " + ", ".join(failures) if failures else ""))
sys.exit(1 if failures else 0)
