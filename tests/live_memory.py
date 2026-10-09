"""
Live test of Avy's memory against the real DeepSeek. It costs a few cents.

    python3 tests/live_mem.py                 uses the key in .env
    python3 tests/live_mem.py path/to/.env    uses another key file

It replays a week of conversation into a fresh, throwaway memory (your real one is never
touched): facts planted on day 1, a correction on day 3, details that are only reachable by
following links, lots of filler in between, and a question whose answer was never given.
The real indexer writes the pages; on day 7, real questions go through the full pipeline.
At the end it prints what Avy answered, what memory brought her, and the whole index.
"""

import json
import os
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
key_file = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / ".env"
for line in key_file.read_text().splitlines():
    if line.startswith("DEEPSEEK_API_KEY="):
        os.environ["DEEPSEEK_API_KEY"] = line.split("=", 1)[1].strip()

import app        # noqa: E402  (the key has to be in place first)
import indexer    # noqa: E402
import memory     # noqa: E402

clock = {"t": datetime(2026, 10, 1, 19, 0).astimezone()}
memory.now = lambda: clock["t"]
folder = Path(tempfile.mkdtemp(prefix="avy-live-"))
models = Path(os.environ.get("AVY_MODELS", HERE / "data" / "models")) / "meaning"
memory.embedder.start(models)
mem = app.MEMORIES["main"] = memory.Memory(folder / "mem.db")
indexer.app.update(ask=app.ask_json, prices=app.PRICES)
app.current_settings = lambda: {name: spec["default"] for name, spec in app.SETTINGS.items()}   # your own choices don't change the test
while memory.embedder.status != "on" and not memory.embedder.status.startswith("off"):
    import time
    time.sleep(0.5)
print(f"throwaway memory in {folder}; meaning search {memory.embedder.status}\n")


def turn(text, minutes=2):
    """One real exchange through the same Turn the app uses. Returns (reply, recall trace)."""
    clock["t"] += timedelta(minutes=minutes)
    t = app.Turn(text, "text")
    reply, usage = "", None
    with t.ask() as upstream:
        for line in upstream:
            words, counts = app.stream_text(line)
            reply += words
            usage = counts or usage
    clock["t"] += timedelta(seconds=20)
    t.finish(reply, usage)
    for r in indexer.index_now(mem):      # what the background indexer would do after this reply
        print(f"   [indexed #{r['first']}-#{r['last']}: {r['status']}, {r['entries']} entries, {r['attempts']} tries]")
    return reply, t.recall


def canned(user, avy, minutes=3):
    """Filler: saved straight to the log (no reply call), but indexed by the real indexer."""
    clock["t"] += timedelta(minutes=minutes)
    mem.add("user", user)
    clock["t"] += timedelta(seconds=30)
    mem.add("assistant", avy)
    for r in indexer.index_now(mem):
        print(f"   [indexed #{r['first']}-#{r['last']}: {r['status']}, {r['entries']} entries, {r['attempts']} tries]")


FILLER = [
    ("made pasta tonight, the garlic kind", "Nice, aglio e olio is hard to beat. Did you go heavy on the chili?"),
    ("yeah a lot of chili lol", "Respect. Water nearby, I hope."),
    ("listening to some old Coldplay while coding", "Good coding music. Parachutes or later stuff?"),
    ("Parachutes, always", "Classic choice."),
    ("my laptop fan is so loud today", "Might be dust, or something stuck at full CPU. Check Activity Monitor."),
    ("it was chrome, as usual", "Of course it was."),
    ("thinking of going for a run tomorrow morning", "Do it. Early runs feel great once you're out the door."),
    ("ok going to sleep now", "Night!"),
    ("morning. couldn't run, it was raining", "Rain's a fair excuse. Maybe this evening?"),
    ("maybe. coffee first", "Coffee first, always."),
    ("the weather app said sunny though", "Weather apps are optimists."),
    ("lol true", "Anything on today?"),
    ("just classes and some reading", "Sounds manageable."),
    ("my roommate is cooking something weird", "Weird good or weird bad?"),
    ("smells like burnt popcorn", "Weird bad, then. Open a window."),
    ("watched half a movie and fell asleep", "Happens to the best of us. Which one?"),
    ("some heist movie, can't remember the name", "If you can't remember it, it probably wasn't that good."),
    ("fair point", "Anything else on your mind?"),
]


# ---- Day 1: the facts ----
print("day 1")
turn("hey avy! quick thing to remember: my friend Rohan's birthday is March 3rd")
turn("he and I took CMPSC 465 together last spring, that's how we met")
turn("also I'm taking STAT 318 this semester, probability. the first quiz is next Friday")
turn("and my sister Priya lives in Pittsburgh, she's a nurse there")
turn("one more: I like short answers, no bullet points please")
for u, a in FILLER[:9]:
    canned(u, a)

# ---- Day 3: a correction and a decision ----
clock["t"] += timedelta(days=2)
print("day 3")
turn("wait, I messed up earlier. Rohan's birthday is actually May 3rd, not March 3rd. I mixed it up with someone else")
turn("also for Avy's memory, I decided we're going with SQLite instead of Postgres, mostly because it's one file and needs no server")
for u, a in FILLER[9:]:
    canned(u, a)

# ---- Day 5: details that hang off existing people ----
clock["t"] += timedelta(days=2)
print("day 5")
turn("Rohan mentioned he really wants a mechanical keyboard, the clicky kind")
turn("oh and Priya is coming to visit on October 18th, staying the weekend")
for u, a in FILLER[:12]:
    canned(u, a)

# ---- Day 7: questions ----
clock["t"] += timedelta(days=2)
print("day 7: questions\n")
PROBES = [   # (question, words the answer must have, words it must not have)
    ("When is Rohan's birthday?", ["may 3"], []),
    ("What did I first tell you his birthday was?", ["march 3"], []),
    ("What should I get my friend for his birthday?", ["keyboard"], []),
    ("When's my sister visiting?", ["18"], []),
    ("What did we pick for the memory database, and why?", ["sqlite"], []),
    ("Which class did Rohan and I take together?", ["465"], []),
    ("What's the nurse in my family up to these days?", ["18"], []),             # only through links: nurse -> Priya -> her visit
    ("Anything coming up with the guy I met in CMPSC 465?", ["may"], []),      # course -> Rohan -> his birthday
    ("What's my dog's name?", [], ["max", "buddy", "charlie"]),                # never said
]
results = []
for question, must, must_not in PROBES:
    reply, trace = turn(question, minutes=5)
    low = reply.lower()
    passed = all(w in low for w in must) and not any(w in low for w in must_not)
    if not must:      # the unknown: it should say it doesn't know
        passed = passed and any(w in low for w in ["don't", "not sure", "haven't", "no idea", "didn't", "never"])
    results.append(passed)
    print(f"{'PASS' if passed else 'FAIL'}  {question}\n      avy: {reply}\n      "
          f"memory: {len(trace['entries'])} entries, {len(trace['log'])} log lines, ~{trace['tokens']} tokens (best match {trace['best']})")
    for x in trace["entries"]:
        how = f"via e{x['via']} ({x['link']}, {x['direction']})" if x["how"] == "link" else x["how"]
        print(f"      e{x['entry']:<3} {x['score']:.2f} {x['kind']:<10} {x['title']}  [{how}]")
    for x in trace["log"]:
        print(f"      #{x['message']} from the log [{x['how']}]")
    print()

# ---- The repair loop, live: break DeepSeek's first answer on purpose; it should fix it ----
clock["t"] += timedelta(days=1)
print("repair loop: the next indexing answer gets broken on purpose")
original, broken = indexer.app["ask"], {"done": False}


def tamper(payload):
    reply = original(payload)
    if not broken["done"]:
        broken["done"] = True
        call = reply["choices"][0]["message"]["tool_calls"][0]["function"]
        args = json.loads(call["arguments"])
        if args.get("entries"):
            args["entries"][0]["evidence"][0]["quote"] = "words that were never said"
            args["entries"][0]["links"].append({"to": "e999", "kind": "about"})
        call["arguments"] = json.dumps(args)
    return reply


indexer.app["ask"] = tamper
before = mem.value("SELECT MAX(id) FROM runs")
turn("my dentist appointment got moved to October 22nd, 3pm")
turn("also I finished the STAT 318 homework that was due Friday")
for u, a in FILLER[12:]:
    canned(u, a)
if not broken["done"]:
    indexer.index_now(mem, force=True)
indexer.app["ask"] = original
run = mem.row("SELECT * FROM runs WHERE id > ? ORDER BY id LIMIT 1", before)
repaired = bool(run) and run["status"] == "repaired" and run["attempts"] >= 2
print(f"{'PASS' if repaired else 'FAIL'}  broken answer repaired by the real model: "
      + (f"{run['status']} after {run['attempts']} tries" if run else "no run"))
for attempt, found in enumerate(json.loads(run["problems"]) if run else [], 1):
    for p in found:
        print(f"      try {attempt}: {p[:200]}")
results.append(repaired)
reply, trace = turn("when's my dentist appointment again?", minutes=60 * 5)
results.append("22" in reply)
print(f"{'PASS' if '22' in reply else 'FAIL'}  when's my dentist appointment again?\n      avy: {reply}\n")

# ---- The index DeepSeek wrote ----
print("=" * 70)
print("the index")
for p in mem.rows("SELECT * FROM pages ORDER BY id"):
    run = mem.row("SELECT * FROM runs WHERE id = ?", p["run"])
    print(f"\np{p['id']}  #{p['first']}-#{p['last']}  {p['headline']}   [{run['status']}, {run['attempts']} tries, ${run['cost']:.4f}]")
    for e in mem.rows("SELECT * FROM entries WHERE page = ? ORDER BY id", p["id"]):
        out, _ = mem.links_of(e["id"])
        ev = ", ".join(f"#{v['message']}{'' if v['exact'] else '(whole)'}" for v in mem.evidence_of(e["id"]))
        links = ", ".join(f"{l['kind']}->e{l['linked']}{'*' if l['by'] == 'system' else ''}" for l in out)
        tag = f" v{e['version']} replaces e{e['replaces']}" if e["replaces"] else ""
        print(f"  e{e['id']:<3} {e['kind']:<10} {e['title']}{tag}: {mem.readable(e['text'])}  [{ev}] {links}")
print("\nwhat the checks found, run by run:")
for r in mem.rows("SELECT id, first, last, status, attempts, problems FROM runs ORDER BY id"):
    found = [p for attempt in json.loads(r["problems"] or "[]") for p in attempt]
    print(f"  run {r['id']} #{r['first']}-#{r['last']}: {r['status']}, {r['attempts']} tries" + ("" if found else ", nothing to fix"))
    for p in found:
        print(f"      {p[:300]}")
rohan = mem.row("SELECT * FROM current WHERE kind = 'person' AND title LIKE 'Rohan%'")
if rohan:
    print(f"\nthe Rohan hub now says: {mem.readable(rohan['text'])}")
total = mem.value("SELECT SUM(cost) FROM runs") or 0
print(f"\n{sum(results)}/{len(results)} checks passed · {mem.stats()['entries']} entries · "
      f"{mem.stats()['links']} links · indexing cost ${total:.4f} (off-peak prices; peak hours are 2x)")
