"""
The same month, through version 1 (the fork point), for comparison.

Version 1's code is used exactly as it is on the memory-v1 branch. It indexes the same log a v2
benchmark run produced (same messages, same times), and answers the same questions at the same
moments, at /window: 0 and /recall: normal. Then the answers are graded by the same judge.

    git worktree add ../avy-v1 memory-v1                       # version 1's code, beside this one
    python3 tests/bench/v1_replay.py --v1 ../avy-v1 --run tests/bench/results/<stamp>.json --key .env

It writes <stamp>.v1.json next to the run, and adds a column to its report.
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

# ------------------------------------------------------------------------------------------------
# Part 1 runs inside version 1's code (a separate Python process, so the two versions never mix).
# ------------------------------------------------------------------------------------------------
V1_SIDE = r'''
import json, sys, os
from datetime import datetime, timedelta
sys.path.insert(0, sys.argv[1])
os.environ["DEEPSEEK_API_KEY"] = sys.argv[4]
os.environ["AVY_NO_BROWSER"] = "1"
import app, indexer, memory
plan = json.loads(open(sys.argv[2]).read())
memory.embedder.start(sys.argv[5]);
import time
while memory.embedder.status != "on" and not memory.embedder.status.startswith("off"):
    time.sleep(0.3)
clock = {"t": None}
memory.now = lambda: clock["t"]
mem = app.MEMORIES["main"] = memory.Memory(sys.argv[3])
indexer.app.update(ask=app.ask_json, prices=app.PRICES, page=lambda: 20, memories=lambda: [mem])
app.current_settings = lambda: {name: spec["default"] for name, spec in app.SETTINGS.items()}
out = {"answers": [], "runs": 0}
for ev in plan["events"]:
    clock["t"] = datetime.fromisoformat(ev["at"])
    if ev["kind"] == "message":
        mem.add(ev["role"], ev["text"], at=ev["at"])
    elif ev["kind"] == "index":
        out["runs"] += len(indexer.index_now(mem))
    else:
        t = mem.recall(ev["ask"], "", None, "normal")
        messages = app.briefing([], t["briefing"], ev["ask"])
        with app.deepseek({"model": "deepseek-flash", "messages": messages, "thinking": {"type": "disabled"}}) as r:
            reply = json.loads(r.read())
        out["answers"].append({"id": ev["id"], "answer": reply["choices"][0]["message"]["content"],
                               "cited": t["messages"], "items": len(t["entries"]) + len(t["log"]),
                               "entries": [e["messages"] for e in t["entries"]], "log": [l["message"] for l in t["log"]],
                               "tokens": t["tokens"], "briefing": t["briefing"]})
        print("answered", ev["id"], flush=True)
out["entries"] = mem.value("SELECT COUNT(*) FROM current")
out["links"] = mem.value("SELECT COUNT(*) FROM links")
out["cost"] = mem.value("SELECT SUM(cost) FROM runs") or 0
print(json.dumps(out))
'''


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--v1", required=True, help="a checkout of the memory-v1 branch")
    parser.add_argument("--run", required=True, help="a v2 benchmark result (.json); its .memory folder holds the log")
    parser.add_argument("--key", default=str(HERE.parent.parent / ".env"))
    parser.add_argument("--models", default=str(HERE.parent.parent / "data" / "models" / "meaning"))
    parser.add_argument("--python", default=sys.executable)
    args = parser.parse_args()
    key = next(l.split("=", 1)[1].strip() for l in Path(args.key).read_text().splitlines() if l.startswith("DEEPSEEK_API_KEY="))
    os.environ["DEEPSEEK_API_KEY"] = key

    run_file = Path(args.run)
    result = json.loads(run_file.read_text())
    sys.path.insert(0, str(HERE))
    sys.path.insert(0, str(HERE.parent.parent))
    import sqlite3
    import world
    from datetime import datetime, timedelta

    # The log the v2 run produced, with the moments the probes were asked and the sittings ended.
    v2db = run_file.with_suffix(".memory") / "memory-v2.db"
    log = sqlite3.connect(f"file:{v2db}?mode=ro", uri=True).execute("SELECT at, role, text FROM messages ORDER BY id").fetchall()
    day1 = datetime.fromisoformat(world.START + "T00:00").astimezone()
    moment = lambda d, hm: day1 + timedelta(days=d - 1, hours=int(hm[:2]), minutes=int(hm[3:]))
    events = [{"kind": "message", "at": at, "role": role, "text": text} for at, role, text in log]
    for i, (at, _, _) in enumerate(log):                 # a sitting ends: index 31 minutes later
        nxt = log[i + 1][0] if i + 1 < len(log) else None
        if not nxt or (datetime.fromisoformat(nxt) - datetime.fromisoformat(at)).total_seconds() > 30 * 60:
            events.append({"kind": "index", "at": (datetime.fromisoformat(at) + timedelta(minutes=31)).isoformat()})
    for p in world.PROBES:
        events.append({"kind": "probe", "at": moment(p["day"], p["at"]).isoformat(), "id": p["id"], "ask": p["ask"]})
    events.sort(key=lambda e: (datetime.fromisoformat(e["at"]), {"message": 0, "index": 1, "probe": 2}[e["kind"]]))

    work = run_file.with_suffix(".v1")
    work.mkdir(exist_ok=True)
    (work / "plan.json").write_text(json.dumps({"events": events}))
    (work / "v1_side.py").write_text(V1_SIDE)
    db = work / "memory.db"
    db.unlink(missing_ok=True)
    proc = subprocess.run([args.python, "-I", str(work / "v1_side.py"), str(Path(args.v1).resolve()), str(work / "plan.json"),
                           str(db), key, args.models], capture_output=True, text=True, cwd=str(work))
    if proc.returncode:
        sys.exit(proc.stderr[-3000:])
    v1 = json.loads(proc.stdout.strip().splitlines()[-1])

    # Tag every message with its thread, the way the v2 run did, to score what v1's recall brought.
    tags, current = {}, None
    lines = {text: (s["thread"], s["day"]) for s in world.SESSIONS for who, text in s["lines"]}
    for mid, (at, role, text) in enumerate(log, 1):
        if role == "user" or text in lines:
            current = lines.get(text, current)
        tags[mid] = current
    import judge
    from mind import llm
    llm.app.update(ask=ask_json(key), prices={"deepseek-v4-pro": {"cache_hit": 0.022, "cache_miss": 0.66, "output": 1.98}})
    probes = {p["id"]: p for p in world.PROBES}
    for a in v1["answers"]:
        p = probes[a["id"]]
        items = [{tags[m] for m in ms if tags.get(m)} for ms in a["entries"]] + [{tags[m]} if tags.get(m) else set() for m in a["log"]]
        a["retrieval"] = judge.retrieval(p, items, a["tokens"])
        a["grade"] = judge.grade(p, a["answer"], log=log)
        print(f"{a['id']:<14} v1 score {a['grade']['score']}  covered {a['retrieval']['covered']}  items {a['retrieval']['items']} "
              f"noise {a['retrieval']['noise']}" + ("  INVENTED" if a["grade"]["invented"] else ""), flush=True)
    out = run_file.with_name(run_file.stem + ".v1.json")
    out.write_text(json.dumps(v1, indent=1))
    result["v1"] = {a["id"]: a for a in v1["answers"]}
    result["v1_stats"] = {k: v1[k] for k in ("entries", "links", "cost", "runs")}
    run_file.write_text(json.dumps(result, indent=1, default=str))
    import report
    run_file.with_suffix(".md").write_text(report.markdown(result))
    print(f"version 1: {v1['entries']} entries, {v1['links']} links, indexing ${v1['cost']:.4f}. report: {run_file.with_suffix('.md')}")


def ask_json(key):
    """One structured request to DeepSeek (the judge), without importing app.py."""
    import ssl
    import urllib.request
    try:
        import truststore
        ctx = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    except ImportError:
        ctx = ssl.create_default_context()
    def ask(payload):
        req = urllib.request.Request("https://api.deepseek.com/beta/chat/completions", data=json.dumps(payload).encode(),
                                     headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
        return json.loads(urllib.request.urlopen(req, timeout=120, context=ctx).read())
    return ask


if __name__ == "__main__":
    main()
