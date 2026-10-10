"""Ask a finished run's questions again, on its finished memory, with some setting changed: a cheap way
to see what one change does, with everything else held still. (The memory is the end-of-month one, so
questions asked earlier in the month see later things too; compare the variants with each other, not
with the run itself.)

    python3 tests/bench/ask_again.py tests/bench/results/<stamp>.json --variant cap12 nodes=12 --variant cap30 nodes=30
        [--configs both,explore] [--key .env] [--models data/models/meaning]

A variant sets recall's numbers for the normal depth (nodes, tokens, keep, hops, fanout...).
Writes <stamp>.again.json and prints a table.
"""

import argparse
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))

parser = argparse.ArgumentParser()
parser.add_argument("run")
parser.add_argument("--variant", nargs="+", action="append", required=True, help="name key=value ...")
parser.add_argument("--configs", default="both,explore")
parser.add_argument("--key", default=str(ROOT / ".env"))
parser.add_argument("--models", default=str(ROOT / "data" / "models" / "meaning"))
args = parser.parse_args()
for line in Path(args.key).read_text().splitlines():
    if line.startswith("DEEPSEEK_API_KEY="):
        os.environ["DEEPSEEK_API_KEY"] = line.split("=", 1)[1].strip()

import app      # noqa: E402
import judge    # noqa: E402
import memory   # noqa: E402
import world    # noqa: E402
from memory import recall as recall_module  # noqa: E402
from mind import explore, llm  # noqa: E402

run_file = Path(args.run)
memory.embedder.start(Path(args.models))
memory.embedder.wait(300)
db = run_file.with_suffix(".memory") / "memory-v2.db"
mem = app.MEMORIES["main"] = memory.Memory(db)
llm.app.update(ask=app.ask_json, prices=app.PRICES)
settings = {name: spec["default"] for name, spec in app.SETTINGS.items()}
settings.update(footnotes="off", window="0")
app.current_settings = lambda: settings
log = [(m["at"], m["role"], m["text"]) for m in mem.messages_between(1, mem.last_id())]
memory.clock.fixed = memory.common.datetime.fromisoformat(log[-1][0]) if hasattr(memory.common, "datetime") else None

# messages -> (thread, day), the way run.py tags them
lines = {text: (s["thread"], s["day"]) for s in world.SESSIONS for who, text in s["lines"]}
tags, current = {}, None
for mid, (at, role, text) in enumerate(log, 1):
    if role == "user" or text in lines:
        current = lines.get(text, current)
    tags[mid] = current


def node_tags(chain, depth=0):
    n = mem.head(chain)
    found = {tags[e["message"]] for e in mem.evidence_of(n["id"]) if tags.get(e["message"])} if n else set()
    if n and n["origin"] == "inferred" and depth < 3:
        for b in mem.basis_of(n["id"]):
            found |= node_tags(b["chain"], depth + 1)
    return found


original = dict(recall_module.DEPTHS["normal"])
out = {"run": str(run_file), "variants": {}}
for variant in args.variant:
    name, changes = variant[0], dict(kv.split("=", 1) for kv in variant[1:])
    recall_module.DEPTHS["normal"] = {**original, **{k: type(original[k])(float(v)) if isinstance(original[k], float) else int(v)
                                                     for k, v in changes.items()}}
    rows = []
    for p in world.PROBES:
        for cfg in args.configs.split(","):
            if cfg == "explore":
                trace = explore.explore(explore.Library([mem]), mem, p["ask"], "", None, "normal", True, True, learn=False)
            else:
                c = world.CONFIGS[cfg]
                trace = mem.recall(p["ask"], "", None, "normal", c["words"], c["meaning"])
            messages = app.briefing([], trace["briefing"], p["ask"], core=True)
            with app.deepseek({"model": "deepseek-flash", "messages": messages, "thinking": {"type": "disabled"}}) as r:
                text = json.loads(r.read())["choices"][0]["message"]["content"]
            items = [node_tags(x["node"]) for x in trace["nodes"]] + [{tags[l["message"]]} if tags.get(l["message"]) else set() for l in trace["log"]]
            ret = judge.retrieval(p, items, trace["tokens"])
            g = judge.grade(p, text, log=log)
            rows.append({"probe": p["id"], "config": cfg, "score": g["score"], "coverage": ret["coverage"], "items": ret["items"],
                         "noise": ret["noise"], "answer": text})
            print(f"{name:<8} {p['id']:<14} {cfg:<8} score {g['score']}  coverage {ret['coverage']}  items {ret['items']} noise {ret['noise']}", flush=True)
    out["variants"][name] = {"changes": changes, "rows": rows}
    run_file.with_suffix(".again.json").write_text(json.dumps(out, indent=1))

print("\naverages:")
for name, v in out["variants"].items():
    for cfg in args.configs.split(","):
        s = [r["score"] for r in v["rows"] if r["config"] == cfg and r["score"] is not None]
        it = [r["items"] for r in v["rows"] if r["config"] == cfg]
        print(f"  {name:<8} {cfg:<8} {round(100 * sum(s) / len(s))}%  ({sum(it) / len(it):.1f} items on average)")
