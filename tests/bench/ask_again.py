"""Ask a finished run's questions again, on its finished memory, with one setting changed: a cheap way to
see what that change does with everything else held still. The memory is the end-of-month one, so a
question asked on day 8 now sees later things too; compare the variants with each other, not with the run.

    python3 tests/bench/ask_again.py tests/bench/results/<stamp>.json --variant cap12 nodes=12 --variant cap20 nodes=20
        [--configs both,explore] [--key .env] [--models data/models/meaning]

A variant changes recall's numbers for the normal depth (nodes, tokens, keep, hops, fanout... see
memory/recall.py DEPTHS), or a module setting written module.NAME=value (explore.HUBS_SHOWN=0). Explore is not bound by the node cap (it keeps what it judges useful within
the token budget), so it shows up as a fixed reference unless tokens change.
Writes <stamp>.again.json and prints a table.
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))

parser = argparse.ArgumentParser()
parser.add_argument("run")
parser.add_argument("--variant", nargs="+", action="append", required=True, help="name key=value ...")
parser.add_argument("--configs", default="both,explore")
parser.add_argument("--probes", default="", help="only these probes (comma-separated ids)")
parser.add_argument("--judge", default="deepseek-v4-pro")
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
mem = app.MEMORIES["main"] = memory.Memory(run_file.with_suffix(".memory") / "memory-v2.db")
llm.app.update(ask=app.ask_json, prices=app.PRICES)
settings = {name: spec["default"] for name, spec in app.SETTINGS.items()}
app.current_settings = lambda: settings
rows_ = mem.messages_between(1, mem.last_id())
log = [(m["at"], m["role"], m["text"]) for m in rows_]
memory.clock.fixed = datetime.fromisoformat(log[-1][0])


def tag_log():
    """message id -> (thread, day). Walks the sittings in the order run.py played them and matches each of
    Shreyas's lines to the next expected one, so a repeated line ("ok") can't land in the wrong sitting.
    Avy's replies take the tag of the line they answer."""
    sittings = sorted(world.SESSIONS, key=lambda s: judge.moment(s["day"], s["at"]))
    expected = [(text, (s["thread"], s["day"])) for s in sittings for who, text in s["lines"] if who != "avy"]
    tags, i, current = {}, 0, None
    for m in rows_:
        if m["role"] == "user":
            for j in range(i, min(i + 6, len(expected))):
                if expected[j][0] == m["text"]:
                    current, i = expected[j][1], j + 1
                    break
        tags[m["id"]] = current
    return tags


saved = json.loads(run_file.read_text()).get("tags")
tags = {int(k): tuple(v) for k, v in saved.items()} if saved else tag_log()


def node_tags(chain, depth=0, parts=False):
    """The (thread, day) tags of the words a node rests on. parts: also a thing's newest parts, which the
    briefing lists under it (for scoring what a search brought; not for the network checks)."""
    n = mem.head(chain)
    if not n:
        return set()
    found = {tags[e["message"]] for e in mem.evidence_of(n["id"]) if tags.get(e["message"])}
    if n["origin"] == "inferred" and depth < 3:
        for b in mem.basis_of(n["id"]):
            found |= node_tags(b["chain"], depth + 1)
    if parts and n["shape"] == "thing" and depth == 0:        # a thing's newest parts are listed under it in the briefing
        for p in mem.parts(chain)[:memory.recall.PARTS_SHOWN]:
            found |= node_tags(p["chain"], depth + 1)
    return found


def ask(probe, cfg_name):
    cfg = world.CONFIGS[cfg_name]
    settings.update(words="on" if cfg["words"] else "off", meaning="on" if cfg["meaning"] else "off",
                    recall=cfg["depth"], footnotes="off", window="0")
    if cfg["explore"]:
        trace = explore.explore(explore.Library([mem]), mem, probe["ask"], "", None, cfg["depth"], cfg["words"], cfg["meaning"], learn=False)
    else:
        trace = mem.recall(probe["ask"], "", None, cfg["depth"], cfg["words"], cfg["meaning"])
    messages = app.briefing([], trace["briefing"], probe["ask"], core=True)
    with app.deepseek({"model": "deepseek-flash", "messages": messages, "thinking": {"type": "disabled"}}) as r:
        text = json.loads(r.read())["choices"][0]["message"]["content"]
    items = [node_tags(x["node"], parts=True) for x in trace["nodes"]] + [{tags[l["message"]]} if tags.get(l["message"]) else set()
                                                               for l in trace["log"]]
    return text, judge.retrieval(probe, items, trace["tokens"])


original = dict(recall_module.DEPTHS["normal"])
out = {"run": str(run_file), "variants": {}}
configs = args.configs.split(",")
for variant in args.variant:
    name, changes = variant[0], dict(kv.split("=", 1) for kv in variant[1:])
    recall_module.DEPTHS["normal"] = {**original, **{k: float(v) if isinstance(original[k], float) else int(v)
                                                     for k, v in changes.items() if "." not in k}}
    for k, v in changes.items():                  # module.SETTING=value, e.g. explore.HUBS_SHOWN=0
        if "." in k:
            module, attr = k.split(".", 1)
            target = {"explore": explore, "recall": recall_module}[module]
            setattr(target, attr, type(getattr(target, attr))(v))
    rows = []
    for p in [p for p in world.PROBES if not args.probes or p["id"] in args.probes.split(",")]:
        for cfg in configs:
            text, ret = ask(p, cfg)
            g = judge.grade(p, text, args.judge, lambda *a: None, log)
            rows.append({"probe": p["id"], "config": cfg, "score": g["score"], "invented": g["invented"],
                         "coverage": ret["coverage"], "items": ret["items"], "noise": ret["noise"], "answer": text})
            print(f"{name:<8} {p['id']:<14} {cfg:<8} score {g['score']}  coverage {ret['coverage']}  "
                  f"items {ret['items']} noise {ret['noise']}", flush=True)
    out["variants"][name] = {"changes": changes, "rows": rows}
    run_file.with_suffix(".again.json").write_text(json.dumps(out, indent=1))
recall_module.DEPTHS["normal"] = original

print("\naverages:")
for name, v in out["variants"].items():
    for cfg in configs:
        mine = [r for r in v["rows"] if r["config"] == cfg]
        s = [r["score"] for r in mine if r["score"] is not None]
        print(f"  {name:<8} {cfg:<8} score {round(100 * sum(s) / max(len(s), 1))}%  "
              f"coverage {round(100 * sum(r['coverage'] or 0 for r in mine) / len(mine))}%  "
              f"items {sum(r['items'] or 0 for r in mine) / len(mine):.1f}  noise {sum(r['noise'] or 0 for r in mine) / len(mine):.1f}")
