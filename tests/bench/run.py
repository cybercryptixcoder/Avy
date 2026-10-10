"""
The benchmark: a month of conversation (world.py) replayed through the real Avy and DeepSeek, then
questions that need memory, answered under several search setups and graded.

    python3 tests/bench/run.py                          uses the key in .env
    python3 tests/bench/run.py --key path/.env          another key file
    python3 tests/bench/run.py --models <folder>        where the meaning-search model is (default data/models/meaning)
    python3 tests/bench/run.py --configs both,explore   only some setups

What happens:
  1. A fresh, throwaway memory (never yours). The clock is set to each moment of the world.
  2. Every sitting is played for real: Shreyas's lines go through the same Turn the app uses (window 20,
     recall normal) and Avy answers; when the sitting ends the mind writes it and connects it; every night
     it reflects (check, think, connect), as it would in a quiet spell.
  3. On each probe's day, the question is answered under every setup in world.CONFIGS at /window: 0, so
     everything has to come through memory. Nothing from the probes is saved.
  4. A separate judge (deepseek-v4-pro) grades each answer against the points a good answer makes, with
     the true conversation in front of it, and flags anything made up.
  5. Retrieval is scored too: did memory bring the sittings the question needed, and how much else?
  6. The network's shape is checked: did a hub form for the unnamed project, did the habit get inferred
     and then revised, how close did the two concepts end up, is the tension recorded?
Writes tests/bench/results/<time>.json and .md, and keeps the memory file for the inspector.
Costs roughly ten to thirty cents and takes about an hour.
"""

import argparse
import json
import os
import shutil
import sys
import time
from collections import deque
from datetime import datetime, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))

parser = argparse.ArgumentParser()
parser.add_argument("--key", default=str(ROOT / ".env"))
parser.add_argument("--models", default=str(ROOT / "data" / "models" / "meaning"))
parser.add_argument("--configs", default="none,words,meaning,both,explore")
parser.add_argument("--out", default=str(HERE / "results"))
parser.add_argument("--judge", default="deepseek-v4-pro")
parser.add_argument("--name", default="")
parser.add_argument("--until", type=int, default=99, help="only play the world up to this day (a quick try)")
args = parser.parse_args()
for line in Path(args.key).read_text().splitlines():
    if line.startswith("DEEPSEEK_API_KEY="):
        os.environ["DEEPSEEK_API_KEY"] = line.split("=", 1)[1].strip()

import app        # noqa: E402  (the key has to be in place first)
import memory     # noqa: E402
import judge      # noqa: E402
import world      # noqa: E402
from mind import explore, llm, worker  # noqa: E402

OUT = Path(args.out)
OUT.mkdir(parents=True, exist_ok=True)
STAMP = datetime.now().strftime("%Y-%m-%d_%H-%M") + (f"_{args.name}" if args.name else "")
LOG = open(OUT / f"{STAMP}.log", "w")


def say(*parts):
    text = " ".join(str(p) for p in parts)
    print(text, flush=True)
    LOG.write(text + "\n")
    LOG.flush()


# --- setting up -----------------------------------------------------------------------------------
memory.embedder.start(Path(args.models))
memory.embedder.wait(300)
work = Path(OUT / f"{STAMP}.memory")
work.mkdir(exist_ok=True)
mem = app.MEMORIES["main"] = memory.Memory(work / "memory-v2.db")
llm.app.update(ask=app.ask_json, prices=app.PRICES)
defaults = {name: spec["default"] for name, spec in app.SETTINGS.items()}
settings = dict(defaults, explore="off", footnotes="on")
app.current_settings = lambda: settings
say(f"benchmark {STAMP}: memory in {work}, meaning search {memory.embedder.status}")

moment = judge.moment


def set_clock(t):
    memory.clock.fixed = t


tags = {}          # message id -> (thread, day)
spent = {"replies": 0.0}


def play(session):
    t = moment(session["day"], session["at"])
    set_clock(t)
    lines = list(session["lines"])
    i = 0
    while i < len(lines):
        speaker, text = lines[i]
        nxt = lines[i + 1] if i + 1 < len(lines) else None
        if nxt and nxt[0] == "avy":                      # Avy's reply is scripted: save both as they are
            for who, words in (("user", text), ("assistant", nxt[1])):
                tags[mem.add(who, words)] = (session["thread"], session["day"])
                set_clock(memory.now() + timedelta(seconds=30))
            i += 2
        else:
            turn = app.Turn(text, "text")
            reply, usage = "", None
            with turn.ask() as upstream:
                for raw in upstream:
                    words, counts = app.stream_text(raw)
                    reply += words
                    usage = counts or usage
            tags[turn.user_id] = (session["thread"], session["day"])
            set_clock(memory.now() + timedelta(seconds=25))
            tags[turn.finish(reply, usage)] = (session["thread"], session["day"])
            spent["replies"] += llm.cost(usage or {})
            i += 1
        set_clock(memory.now() + timedelta(seconds=70))
    set_clock(memory.now() + timedelta(minutes=31))     # the sitting ends; the mind writes it
    for r in worker.write_due(mem):
        say(f"     {r['job']:<8} {r['status']:<9} {r.get('headline') or r.get('focus') or ''}"
            f"  +{r.get('applied', 0)}" + (f" ({r['rejected']} refused)" if r.get("rejected") else ""))


def reflect(day):
    set_clock(moment(day + 1, "03:00"))
    for r in worker.reflect_now(mem, thinks=3, budget=10**6):
        bits = f"     {r['job']:<8} {r['status']:<9} {r.get('focus', '')[:70]}  +{r.get('applied', 0)}"
        if r.get("rejected"):
            bits += f" ({r['rejected']} refused)"
        say(bits)


# --- what retrieval brought -------------------------------------------------------------------------

def node_tags(chain, depth=0):
    n = mem.head(chain)
    if not n:
        return set()
    found = {tags[e["message"]] for e in mem.evidence_of(n["id"]) if e["message"] in tags}
    if n["origin"] == "inferred" and depth < 3:
        for b in mem.basis_of(n["id"]):
            found |= node_tags(b["chain"], depth + 1)
    return found


def score_retrieval(probe, trace):
    items = [node_tags(x["node"]) for x in trace["nodes"]] + [{tags[l["message"]]} if l["message"] in tags else set()
                                                               for l in trace["log"]]
    return judge.retrieval(probe, items, trace["tokens"])


# --- answering a probe under one setup (nothing saved) ------------------------------------------------

def answer(probe, name, cfg):
    started = time.time()
    settings.update(words="on" if cfg["words"] else "off", meaning="on" if cfg["meaning"] else "off",
                    recall=cfg["depth"], footnotes="off", window="0")
    searching = cfg["depth"] != "off" and (cfg["words"] or cfg["meaning"])
    if cfg["explore"] and searching:
        trace = explore.explore(explore.Library([mem]), mem, probe["ask"], "", None, cfg["depth"], cfg["words"], cfg["meaning"], learn=False)
    else:
        trace = mem.recall(probe["ask"], "", None, cfg["depth"], cfg["words"], cfg["meaning"])
    messages = app.briefing([], trace["briefing"], probe["ask"], core=searching)
    with app.deepseek({"model": "deepseek-flash", "messages": messages, "thinking": {"type": "disabled"}}) as r:
        reply = json.loads(r.read())
    text = reply["choices"][0]["message"]["content"]
    explored = trace.get("explore") or {}
    return {"config": name, "answer": text, "seconds": round(time.time() - started, 1),
            "cost": round(llm.cost(reply.get("usage") or {}) + explored.get("cost", 0), 5),
            "retrieval": score_retrieval(probe, trace),
            "kept": [f"{x['handle']} {x['title']}" for x in trace["nodes"]] + [f"#{l['message']}" for l in trace["log"]],
            "task": explored.get("task"), "rounds": len(explored.get("rounds", [])), "briefing": trace["briefing"]}


# --- grading (judge.py, shared with the version 1 replay) -------------------------------------------

def grade(probe, a):
    log = [(m["at"], m["role"], m["text"]) for m in mem.messages_between(1, mem.last_id())]
    return judge.grade(probe, a["answer"], args.judge, say, log)


# --- the network's shape ------------------------------------------------------------------------------

def adjacency():
    adj = {n["chain"]: set() for n in mem.current_nodes()}
    for e in mem.live_edges():
        adj[e["a"]].add((e["b"], e["kind"]))
        adj[e["b"]].add((e["a"], e["kind"]))
    for r in mem.rows("SELECT c.chain, b.rests_on FROM current c JOIN basis b ON b.node = c.id WHERE c.origin = 'inferred'"):
        if r["rests_on"] in adj:
            adj[r["chain"]].add((r["rests_on"], "rests on"))
            adj[r["rests_on"]].add((r["chain"], "rests on"))
    return adj


def path(starts, goals, adj):
    """The shortest path from any start to any goal: [(chain, kind of the step into it)], or None."""
    queue, seen = deque([(s, [(s, "")]) for s in starts]), set(starts)
    while queue:
        v, p = queue.popleft()
        if v in goals:
            return p
        for w, kind in adj.get(v, ()):
            if w not in seen:
                seen.add(w)
                queue.append((w, p + [(w, kind)]))
    return None


def said_in(thread, day=None):
    return [n["chain"] for n in mem.current_nodes() if n["origin"] != "inferred"
            and any(tags.get(e["message"], ("", 0))[0] == thread and (day is None or tags[e["message"]][1] == day)
                    for e in mem.evidence_of(n["id"]))]


def describe_path(p):
    return " -> ".join(f"{'(' + k + ') ' if k else ''}{mem.head(c)['title']}" for c, k in p) if p else "no path"


def check_graph(moment_name):
    adj = adjacency()
    out = {}
    if moment_name == "habit":
        writing = set(said_in("writing"))
        found = [n for n in mem.current_nodes() if n["origin"] == "inferred"
                 and len({b["chain"] for b in mem.basis_of(n["id"])} & writing) >= 3]
        out["pattern"] = {"pass": bool(found), "found": [f"{x['title']}: {x['text']} ({x['certainty']})" for x in found]}
    if moment_name == "habit-changed":
        writing = set(said_in("writing"))
        night = set(said_in("writing", 18)) | set(said_in("writing", 19))
        found = [n for n in mem.current_nodes() if n["origin"] == "inferred" and {b["chain"] for b in mem.basis_of(n["id"])} & night
                 and len({b["chain"] for b in mem.basis_of(n["id"])} & writing) >= 2]
        revised = [n for n in mem.current_nodes() if n["origin"] == "inferred" and n["version"] > 1
                   and {b["chain"] for b in mem.basis_of(n["id"])} & writing]
        out["revision"] = {"pass": bool(found), "revised_versions": [f"{x['title']} (v{x['version']}): {x['text']}" for x in revised],
                           "found": [f"{x['title']}: {x['text']}" for x in found]}
    if moment_name == "synthesis":
        p = path(said_in("ants"), set(said_in("desire")), adj)
        out["bridge"] = {"pass": bool(p) and len(p) - 1 <= 2, "steps": len(p) - 1 if p else None, "path": describe_path(p)}
    if moment_name == "multi-hop":
        best = None
        for n in mem.things():
            days = {d for other, _ in adj.get(n["chain"], ()) for t, d in node_tags(other) if t == "basil"}
            days |= {d for t, d in node_tags(n["chain"]) if t == "basil"}
            if not best or len(days) > best[1]:
                best = (n, len(days))
        out["hub"] = {"pass": bool(best and best[1] >= 4),
                      "hub": f"{best[0]['title']} ({mem.standing(best[0])}, {best[1]} of 7 sittings)" if best else None}
        p = path(said_in("basil", 4), set(said_in("basil", 14)) | set(said_in("basil", 17)), adj)
        out["travel_to_open_problems"] = {"steps": len(p) - 1 if p else None, "path": describe_path(p)}
    if moment_name == "tension":
        p = path(said_in("running", 5), set(said_in("running", 22)), adj)
        out["tension"] = {"pass": bool(p) and any(k == "against" for _, k in p) and len(p) - 1 <= 2,
                          "path": describe_path(p)}
    if moment_name == "ideas":
        ideas = [n for n in mem.current_nodes() if n["shape"] == "idea" and n["chain"] in set(said_in("ideas"))]
        out["ideas"] = {"pass": len(ideas) >= 4, "count": len(ideas), "titles": [x["title"] for x in ideas]}
    if moment_name == "origin":
        captain = [n for n in mem.current_nodes() if "captain" in (n["title"] + n["text"]).lower()]
        out["origin"] = {"nodes": [f"{x['title']}: origins " + " -> ".join(v["origin"] for v in reversed(mem.versions(x["chain"])))
                                   for x in captain]}
    return out


# --- the run --------------------------------------------------------------------------------------

configs = {k: world.CONFIGS[k] for k in args.configs.split(",")}
events = [(moment(s["day"], s["at"]), "session", s) for s in world.SESSIONS]
events += [(moment(p["day"], p["at"]), "probe", p) for p in world.PROBES]
days = sorted({s["day"] for s in world.SESSIONS})
events += [(moment(d + 1, "03:00"), "night", d) for d in days]
events.sort(key=lambda e: (e[0], {"night": 0, "probe": 1, "session": 2}[e[1]]))
events = [e for e in events if e[0] < moment(args.until + 1, "00:00")]

started = time.time()
results = {"stamp": STAMP, "configs": configs, "probes": [], "graph": {}, "health": [], "world": world.START}
for when_, kind, what in events:
    if kind == "session":
        say(f"day {what['day']:>2} {what['at']}  {what['thread']:<8} {what['lines'][0][1][:70]}")
        play(what)
    elif kind == "night":
        say(f"day {what:>2} night: reflecting")
        reflect(what)
        h = memory.health(mem)
        results["health"].append({"day": what, **h})
        say(f"     health: {h['nodes']} nodes, {h['connections']} connections, {h.get('islands')} islands, "
            f"clustering {h.get('clustering')}, path {h.get('average_path')}, inferred {h['inferred']}")
    else:
        set_clock(when_)
        say(f"day {what['day']:>2} {what['at']}  PROBE {what['id']}: {what['ask'][:80]}")
        record = {**{k: what[k] for k in ("id", "day", "ask", "needs", "points")}, "answers": []}
        for name, cfg in configs.items():
            try:
                a = answer(what, name, cfg)
            except Exception as e:
                a = {"config": name, "answer": f"(failed: {e})", "retrieval": {}, "kept": [], "seconds": 0, "cost": 0}
            a["grade"] = grade(what, a)
            r = a["retrieval"]
            say(f"     {name:<8} score {a['grade']['score']}  covered {r.get('covered')} of {what['needs']}  "
                f"items {r.get('items')} noise {r.get('noise')}  {a['seconds']}s" + ("  INVENTED" if a["grade"]["invented"] else ""))
            record["answers"].append(a)
        record["graph"] = check_graph(what["id"])
        for k, v in record["graph"].items():
            say(f"     graph {k}: {json.dumps(v)[:300]}")
        results["probes"].append(record)
        (OUT / f"{STAMP}.json").write_text(json.dumps(results, indent=1, default=str))

results["seconds"] = round(time.time() - started)
results["final_health"] = memory.health(mem)
results["runs"] = mem.rows("SELECT job, COUNT(*) AS n, SUM(cost) AS cost, SUM(CASE WHEN status IN ('failed','error') THEN 1 ELSE 0 END) AS failed "
                           "FROM runs GROUP BY job")
results["refused"] = mem.rows("SELECT op, why, COUNT(*) AS n FROM journal WHERE result = 'rejected' GROUP BY op, why ORDER BY n DESC LIMIT 20")
results["replies_cost"] = round(spent["replies"], 4)
(OUT / f"{STAMP}.json").write_text(json.dumps(results, indent=1, default=str))

# --- the report -----------------------------------------------------------------------------------
import report  # noqa: E402
(OUT / f"{STAMP}.md").write_text(report.markdown(results))
say(f"\ndone in {results['seconds'] // 60} min. report: {OUT / (STAMP + '.md')}")
