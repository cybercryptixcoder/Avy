"""
Offline tests for Avy's memory: no DeepSeek, no network. Run from the Avy folder:

    python3 tests/test_memory.py            keyword search only (fast)
    python3 tests/test_memory.py --meaning  also loads the meaning-search model

Each check prints ok or FAIL; the last line says how many failed.
"""

import json
import sqlite3
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import indexer
import memory

failures = []


def ok(name, condition, detail=""):
    print(("ok    " if condition else "FAIL  ") + name + (f"   ({detail})" if detail and not condition else ""))
    if not condition:
        failures.append(name)


# A clock we control, so the conversation can span days.
clock = {"t": datetime(2026, 10, 1, 9, 0).astimezone()}
memory.now = lambda: clock["t"]


def later(minutes):
    clock["t"] += timedelta(minutes=minutes)


def say(role, text, minutes=1):
    later(minutes)
    return memory.add(role, text)


folder = Path(tempfile.mkdtemp())
memory.open_memory(folder / "memory.db", models=Path(sys.argv[sys.argv.index("--meaning") + 1]) if "--meaning" in sys.argv else None)
if "--meaning" in sys.argv:
    import time
    while memory.meaning.status not in ("on",) and not memory.meaning.status.startswith("off"):
        time.sleep(0.5)
    print("meaning search:", memory.meaning.status)


# --- 1. the log ----------------------------------------------------------------
m1 = say("user", "hey avy, my friend Rohan's birthday is March 3rd")
m2 = say("assistant", "Got it, Rohan's birthday is March 3rd.")
for sql in ("UPDATE messages SET text = 'changed' WHERE id = 1", "DELETE FROM messages WHERE id = 1"):
    try:
        memory.DB.execute(sql)
        ok(f"log refuses: {sql.split()[0]}", False)
    except sqlite3.DatabaseError as e:
        ok(f"log refuses: {sql.split()[0]}", "append-only" in str(e))
ok("messages are numbered", (m1, m2) == (1, 2))


# --- 2. finding quotes -----------------------------------------------------------
text = "Okay so, my friend Rohan's birthday is March 3rd — don't forget!"
ok("exact quote", indexer.locate("Rohan's birthday is March 3rd", text) == (19, 48))
ok("quote with different case and punctuation", indexer.locate("rohans birthday is march 3rd", text) == (19, 48))
span = indexer.locate("Rohan's bday is March 3rd", text)
ok("close quote (a word changed)", span is not None and text[span[0]:span[1]].startswith("Rohan"), span)
ok("made-up quote is rejected", indexer.locate("his birthday is in May", text) is None)
ok("empty quote is rejected", indexer.locate("  ", text) is None)


# --- 3. checking an answer --------------------------------------------------------
for t in ["I'm taking STAT 318 this semester, the quiz is Friday Oct 10",
          "ok, noted",
          "also my sister Priya is visiting next weekend",
          "Nice! Anything planned?",
          "we'll probably go hiking at Mount Nittany"]:
    say("user" if not t.startswith(("ok", "Nice")) else "assistant", t)
stretch = {m["id"]: m for m in memory.messages_between(1, 7)}

good = {"headline": "Rohan's birthday, STAT 318 quiz, Priya visiting", "entries": [
    {"handle": "n1", "kind": "person", "title": "Rohan", "text": "Shreyas's friend.",
     "evidence": [{"message": 1, "quote": "my friend Rohan"}], "replaces": None, "links": []},
    {"handle": "n2", "kind": "event", "title": "Rohan's birthday", "text": "[n1]'s birthday is March 3.",
     "evidence": [{"message": 1, "quote": "Rohan's birthday is March 3rd"}], "replaces": None,
     "links": [{"to": "n1", "kind": "about"}]},
    {"handle": "n3", "kind": "topic", "title": "STAT 318", "text": "A course Shreyas is taking this semester.",
     "evidence": [{"message": 3, "quote": "I'm taking STAT 318 this semester"}], "replaces": None, "links": []},
    {"handle": "n4", "kind": "event", "title": "STAT 318 quiz", "text": "Quiz on Fri Oct 10, 2026.",
     "evidence": [{"message": 3, "quote": "the quiz is Friday Oct 10"}], "replaces": None,
     "links": [{"to": "n3", "kind": "about"}]},
    {"handle": "n5", "kind": "person", "title": "Priya", "text": "Shreyas's sister.",
     "evidence": [{"message": 5, "quote": "my sister Priya"}], "replaces": None, "links": []},
    {"handle": "n6", "kind": "event", "title": "Priya's visit", "text": "Priya visits the weekend of Oct 10-11; they may hike Mount Nittany.",
     "evidence": [{"message": 5, "quote": "Priya is visiting next weekend"}, {"message": 7, "quote": "hiking at Mount Nittany"}],
     "replaces": None, "links": [{"to": "n5", "kind": "about"}]},
]}
headline, clean, problems, notes, asks = indexer.check(good, stretch, {})
ok("a good answer has no problems", problems == [], problems)
ok("mention [n1] in text became a link", ("n1", "about", "model") in clean[1]["links"])
ok("auto link: an entry naming a hub belongs to it", any(l[0] == "n5" for l in clean[5]["links"]), clean[5]["links"])

bad = json.loads(json.dumps(good))
bad["entries"][1]["evidence"][0]["quote"] = "his birthday is in early March"      # not in the message
bad["entries"][2]["evidence"][0]["message"] = 99                                    # not in the stretch
bad["entries"][3]["links"] = [{"to": "e404", "kind": "about"}, {"to": "n2", "kind": "about"}]   # missing; not a hub
bad["entries"][4]["handle"] = "n1"                                                  # duplicate handle
bad["entries"].append({"handle": "n7", "kind": "person", "title": "rohan", "text": "Again.",
                       "evidence": [{"message": 1, "quote": "Rohan"}], "replaces": None, "links": []})
bad["entries"].append({"handle": "n8", "kind": "fact", "title": "Mood", "text": "Happy.",
                       "evidence": [], "replaces": "e77", "links": []})
headline, clean, problems, notes, asks = indexer.check(bad, stretch, {})
said = "\n".join(problems)
ok("problem: quote not in message", "isn't in #1" in said)
ok("...and the pointer falls back to the whole message", any(v[3] == 0 for v in clean[1]["evidence"]))
ok("problem: message outside the stretch", "#99 isn't in the stretch" in said)
ok("...and an entry with no evidence left is dropped", all(e["title"] != "STAT 318" for e in clean))
ok("problem: link to an entry that doesn't exist", "e404" in said)
ok("problem: 'about' to something that isn't a hub", "'about' links go to a person or topic" in said)
ok("problem: duplicate handle", "needs its own handle" in said)
ok("problem: same title twice in one answer", "same title as n1" in said)
ok("problem: no evidence", "n8 \"Mood\": needs evidence" in said)
print("      (problems DeepSeek would be sent back:)\n        - " + "\n        - ".join(problems))


# --- 4. saving, versions, links -----------------------------------------------------------
headline, clean, problems, notes, asks = indexer.check(good, stretch, {})
run_id = memory.save_run(first=1, last=7, status="ok", attempts=1)
page, made = memory.save_page(1, 7, headline, clean, run_id)
rohan, bday = made["n1"], made["n2"]
ok("page saved with six entries", len(made) == 6)
e = memory.entry(bday)
ok("mention [n1] was rewritten to the real entry", f"[e{rohan}]" in e["text"], e["text"])
ok("readable() spells mentions out", memory.readable(e["text"]).startswith("Rohan's birthday"), memory.readable(e["text"]))
ev = memory.evidence_of(bday)[0]
ok("evidence quote is copied from the log by code", ev["quote"] == "Rohan's birthday is March 3rd" and ev["exact"] == 1, ev)

# a correction, a few messages later
for t in ["wait, I messed up. Rohan's birthday is actually May 3rd, not March", "Thanks, updated: May 3rd."]:
    say("user" if t.startswith("wait") else "assistant", t, minutes=60 * 24)
stretch2 = {m["id"]: m for m in memory.messages_between(8, 9)}
shown = indexer.entries_to_show(stretch2.values())
ok("the indexer is shown the existing birthday entry", bday in shown)
fix = {"headline": "Rohan's birthday corrected", "entries": [
    {"handle": "n1", "kind": "event", "title": "Rohan's birthday", "text": f"[e{rohan}]'s birthday is May 3 (corrected from March 3).",
     "evidence": [{"message": 8, "quote": "Rohan's birthday is actually May 3rd"}], "replaces": f"e{bday}", "links": []}]}
headline, clean, problems, notes, asks = indexer.check(fix, stretch2, shown)
ok("a correction checks out", problems == [], problems)
page2, made2 = memory.save_page(8, 9, headline, clean, None)
v2 = made2["n1"]
ok("the new version is current, the old one isn't", memory.is_current(v2) and not memory.is_current(bday))
ok("head() of the old version is the new one", memory.head(bday) == v2)
ok("chain is newest first", [x["version"] for x in memory.chain(bday)] == [2, 1])
out, _ = memory.links_of(v2)
ok("the new version kept the old one's link to Rohan", any(l["to"] == rohan for l in out), out)
try:
    with memory.DB:
        memory.DB.execute("INSERT INTO entries (page, kind, title, text, replaces, first, version, at) VALUES (1, 'event', 'x', 'x', ?, ?, 2, 'now')", (bday, bday))
    ok("a chain can't fork (two replacements of one version)", False)
except sqlite3.IntegrityError:
    ok("a chain can't fork (two replacements of one version)", True)

dup = {"headline": "x", "entries": [
    {"handle": "n1", "kind": "event", "title": "Rohan's birthday", "text": "It's in May.",
     "evidence": [{"message": 8, "quote": "May 3rd"}], "replaces": f"e{bday}", "links": []}]}
headline, clean, problems, notes, asks = indexer.check(dup, stretch2, shown)
ok("replacing an old version is pointed at the current one", clean[0]["replaces"] == v2 and any("older version" in n for n in notes), notes)
dup["entries"][0]["replaces"] = None
headline, clean, problems, notes, asks = indexer.check(dup, stretch2, shown)
ok("same title as an existing entry, no replaces: flagged, and treated as an update", clean[0]["replaces"] == v2 and problems, problems)
hubdup = {"headline": "x", "entries": [
    {"handle": "n1", "kind": "person", "title": "Rohan", "text": "Friend.", "evidence": [{"message": 8, "quote": "Rohan"}], "replaces": None, "links": []},
    {"handle": "n2", "kind": "fact", "title": "Rohan likes cake", "text": "[n1] likes cake.", "evidence": [{"message": 8, "quote": "Rohan's birthday"}],
     "replaces": None, "links": [{"to": "n1", "kind": "about"}]}]}
headline, clean, problems, notes, asks = indexer.check(hubdup, stretch2, shown)
ok("a duplicate hub is dropped and its handle points at the existing hub",
   len(clean) == 1 and (rohan, "about", "model") in clean[0]["links"] and f"[e{rohan}]" in clean[0]["text"], clean)


labels = {"headline": "x", "entries": [
    {"handle": "n1", "kind": "fact", "title": "Rohan likes tea", "text": "He likes tea. [about e%d] [builds_on e%d, e%d]" % (rohan, v2, rohan),
     "evidence": [{"message": 8, "quote": "Rohan's birthday"}], "replaces": None, "links": []}]}
headline, clean, problems, notes, asks = indexer.check(labels, stretch2, shown)
ok("link labels written into the text become real links", "[" not in clean[0]["text"] and
   (rohan, "about", "system") in clean[0]["links"] and (v2, "builds_on", "system") in clean[0]["links"], clean[0])

# an update makes code ask about entries that may repeat the old information
stale = {"headline": "x", "entries": [
    {"handle": "n1", "kind": "event", "title": "Rohan's birthday", "text": "June 3.",
     "evidence": [{"message": 8, "quote": "Rohan's birthday"}], "replaces": f"e{v2}", "links": []}]}
headline, clean, problems, notes, asks = indexer.check(stale, stretch2, shown)
ok("an update asks about the hub written from the same message", rohan in asks and "same message" in asks[rohan], asks)


# --- 5. recall ----------------------------------------------------------------------------
for i in range(30):                        # push the early messages out of the recent window
    say("user" if i % 2 == 0 else "assistant", f"filler message {i} about the weather and lunch", minutes=10)
t = memory.recall("when is rohan's birthday?")
picked = [x["entry"] for x in t["entries"]]
ok("recall finds the current birthday entry", v2 in picked, t["entries"])
ok("recall never shows the old version on its own", bday not in picked)
ok("the briefing shows the earlier version as history", "earlier version 1" in t["briefing"], t["briefing"][:600])
t = memory.recall("what was in March?")
ok("searching the OLD value lands on the current version", v2 in [x["entry"] for x in t["entries"]], t["entries"])
t = memory.recall("tell me about my sister")
found = {x["entry"]: x for x in t["entries"]}
visit = made["n6"]
ok("a fact reachable only through a link is found (sister -> Priya -> her visit)", visit in found, t["entries"])
if visit in found:
    ok("...and the trace says how it was reached", found[visit]["how"] == "link" and found[visit]["via"] == made["n5"], found[visit])
t = memory.recall("what's my dog's name?")
ok("a question memory knows nothing about recalls nothing", not t["entries"] and not t["log"], t["entries"])
t = memory.recall("mount nittany")
ok("the raw log is searched too (safety net)", any(x["message"] == 7 for x in t["log"]) or visit in [x["entry"] for x in t["entries"]], t)
recent = memory.recall("filler message 29 weather")
ok("messages already on screen aren't recalled again", all(x["message"] < memory.first_shown() for x in recent["log"]))
rid = memory.save_recall(40, t)
ok("a recall is saved with the exact briefing", memory.recall_record(rid)["briefing"] == t["briefing"])
ok("core lists the hubs", "Rohan" in memory.core() and "Priya" in memory.core(), memory.core())


# --- 6. a whole run, with a scripted DeepSeek that gets it wrong first --------------------
def scripted(*answers):
    replies = iter(answers)
    def ask(payload):
        args = next(replies)
        return {"choices": [{"finish_reason": "tool_calls", "message": {"role": "assistant", "content": "",
                "tool_calls": [{"id": "call_1", "type": "function", "function": {"name": "write_index", "arguments": json.dumps(args)}}]}}],
                "usage": {"prompt_tokens": 1000, "completion_tokens": 200}}
    return ask

start = memory.indexed_up_to() + 1
last = memory.last_id()
wrong = {"headline": "Small talk about weather", "entries": [
    {"handle": "n1", "kind": "fact", "title": "Weather chat", "text": "They talked about the weather.",
     "evidence": [{"message": start, "quote": "a thunderstorm"}], "replaces": None, "links": []}]}
right = json.loads(json.dumps(wrong))
right["entries"][0]["evidence"][0]["quote"] = "about the weather"
indexer.app.update(ask=scripted(wrong, right), prices={"deepseek-flash": {"cache_hit": 0.003, "cache_miss": 0.15, "output": 0.6}})
ok("not due yet: not enough messages and not idle", indexer.due() is None or indexer.due()[1] - indexer.due()[0] + 1 >= indexer.PAGE)
results = indexer.index_now(force=True)
r = results[0] if results else {}
ok("a run with one bad quote gets repaired", r.get("status") == "repaired" and r.get("attempts") == 2, r)
saved = memory.row("SELECT * FROM runs WHERE id = ?", r.get("id"))
ok("the run's audit keeps the prompt, both replies, and the problems",
   saved and len(json.loads(saved["replies"])) == 2 and "a thunderstorm" in saved["problems"], saved and saved["problems"])
ok("the run's cost was counted", saved and saved["cost"] > 0)

bare = {"headline": "", "entries": "nope"}
say("user", "one more thing", minutes=5); say("assistant", "sure", minutes=1)
indexer.app["ask"] = scripted(bare, bare, bare)
r = indexer.index_now(force=True)[0]
ok("an answer that never becomes usable still saves what it can (headline from the log)", r["status"] == "partial", r)

def unreachable(payload):
    raise OSError("network is down")
say("user", "and another", minutes=5); say("assistant", "ok", minutes=1)
indexer.app["ask"] = unreachable
before = memory.indexed_up_to()
r = indexer.index_now(force=True)[0]
ok("can't reach DeepSeek: nothing is saved to the index, the run says why", r["status"] == "error" and memory.indexed_up_to() == before)
ok("...and it backs off before retrying that stretch", indexer.due() is None)

stats = memory.stats()
ok("stats add up", stats["messages"] == memory.last_id() and stats["entries"] >= 7, stats)

print(f"\n{len(failures)} failed" + (": " + ", ".join(failures) if failures else ""))
sys.exit(1 if failures else 0)
