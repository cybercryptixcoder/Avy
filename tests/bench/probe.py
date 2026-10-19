"""Answer the benchmark's probes against a memory that already exists, and grade them.

Why this exists: a full benchmark replays a whole simulated month (28 minutes, $0.39) before it can ask a single
question. Most changes worth testing touch only *how a question is answered* — the prompt, the retrieval config, the
instruction that says whether tools exist — and none of that needs the month replayed. Reusing a finished month's
memory turns a 28-minute experiment into a ~2-minute one, so the fix loop can actually iterate.

It is deliberately the same code path as tests/bench/run.py::answer (same briefing, same configs, same judge, same
frozen clock), reading the probes and the saved memory from a finished run. If the two ever disagree, that is a bug
here, not a finding.

    python3 tests/bench/probe.py --memory tests/bench/results/2026-10-19_11-59_baseline-fixed.memory \\
        --configs meaning,both,explore --tag after-textcall-fix
"""

import argparse
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(ROOT))

import app  # noqa: E402
import memory  # noqa: E402
from mind import explore, llm  # noqa: E402
from tests.bench import judge, world  # noqa: E402

parser = argparse.ArgumentParser()
parser.add_argument("--memory", required=True, help="a finished run's .memory directory")
parser.add_argument("--configs", default="none,words,meaning,both,explore")
parser.add_argument("--tag", default="")
parser.add_argument("--thinking", default="none")
parser.add_argument("--judge-effort", default="high")
parser.add_argument("--only", default="", help="comma-separated probe ids")
parser.add_argument("--no-judge", action="store_true", help="collect answers without grading (cheap look)")
args = parser.parse_args()

OUT = HERE / "out"
OUT.mkdir(exist_ok=True)

work = Path(args.memory).resolve()
mem = app.MEMORIES["main"] = memory.Memory(work / "memory-v2.db")
# The meaning half of search needs the embedding model loaded. The full run starts it at line 74; without it every
# "meaning" probe reports that search is off and scores 0 for a reason that has nothing to do with the change under test.
memory.embedder.start(ROOT / "data" / "models" / "meaning")
for _ in range(120):
    if memory.embedder.ready:
        break
    time.sleep(0.5)
llm.app.update(ask=app.ask_json, prices=app.PRICES, effort=lambda: args.thinking)

defaults = {name: spec["default"] for name, spec in app.SETTINGS.items()}
settings = dict(defaults, explore="off", footnotes="on", thinking=args.thinking)
app.current_settings = lambda: settings

wanted = [c for c in args.configs.split(",") if c]
only = {s.strip() for s in args.only.split(",") if s.strip()}


def ask(probe, name, cfg):
    """One probe under one config — the same body as run.py::answer.

    shown_from matters: at window: 0 nothing is in front of her word for word, so recall must not skip anything.
    Passing None instead makes recall skip nearly the whole log, which silently scored a probe 0 that the real run
    scored 1.00 — the fast tool looked broken when it was measuring the wrong thing.
    """
    settings.update(words="on" if cfg["words"] else "off", meaning="on" if cfg["meaning"] else "off",
                    recall=cfg["depth"], footnotes="off", window="0")
    searching = cfg["depth"] != "off" and (cfg["words"] or cfg["meaning"])
    shown = mem.window(app.window_size())
    shown_from = shown[0]["id"] if shown else mem.last_id() + 1
    if cfg["explore"] and searching:
        trace = explore.explore(explore.Library([mem]), mem, probe["ask"], "", shown_from,
                                cfg["depth"], cfg["words"], cfg["meaning"], learn=False)
    else:
        trace = mem.recall(probe["ask"], "", shown_from, cfg["depth"], cfg["words"], cfg["meaning"])
    # tools=False matters: this request carries no tool schemas, and the prompt must not promise any.
    messages = app.briefing([], trace["briefing"], probe["ask"], core=searching, tools=False)
    reply = app.luminal.complete({"messages": messages, "max_tokens": app.REPLY_TOKENS}, effort=args.thinking)
    return {"answer": reply["choices"][0]["message"]["content"], "explored": trace.get("explore") or {},
            "retrieval": trace}


rows = []
for probe in world.PROBES:
    if only and probe["id"] not in only:
        continue
    memory.clock.fixed = judge.moment(probe["day"], probe["at"])
    for name in wanted:
        cfg = world.CONFIGS[name]
        started = time.time()
        got = ask(probe, name, cfg)
        took = round(time.time() - started, 1)
        row = {"probe": probe["id"], "day": probe["day"], "config": name, "answer": got["answer"], "seconds": took}
        if not args.no_judge:
            log = [(m["at"], m["role"], m["text"]) for m in mem.messages_between(1, mem.last_id())]
            row["judge"] = judge.grade(probe, got["answer"], args.judge_effort, print, log)
        rows.append(row)
        score = (row.get("judge") or {}).get("score")
        shown = "  --" if score is None else f"{score:.2f}"
        print(f"{probe['id']:16s} {name:8s} {shown}  {took}s", flush=True)

out = OUT / f"probe-{time.strftime('%Y-%m-%d_%H-%M')}{'-' + args.tag if args.tag else ''}.json"
out.write_text(json.dumps(rows, indent=1))

print("\n=== averages ===")
for name in wanted:
    got = [(r.get("judge") or {}).get("score") for r in rows if r["config"] == name]
    got = [g for g in got if g is not None]
    if got:
        print(f"{name:8s} {sum(got) / len(got):.3f}  over {len(got)}")
print(f"\nwritten to {out}")
