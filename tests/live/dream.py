"""A short dream through the real model, on a copy of a memory a live scenario left behind (so nothing real is
touched), then what it changed: the network's health before and after, every run, and the inferences and
connections it wrote. Dreaming is meant to run for hours on his memory; this is the minutes-long version that
shows it works end to end against Luminal at max thinking.

    python3 tests/live/dream.py tests/live/results/2026-10-15_run3_life.memory --minutes 12 --dollars 1

Writes results/<stamp>_dream.md next to the scenarios' reports.
"""

import argparse
import json
import os
import shutil
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(ROOT))


def load_keys(path):
    for line in Path(path).read_text().splitlines():
        if "=" in line and not line.strip().startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("memory", help="a scenario's .memory folder (it's copied; the copy is what dreams)")
    parser.add_argument("--minutes", type=float, default=12)
    parser.add_argument("--dollars", type=float, default=1.0)
    parser.add_argument("--effort", default="max")
    parser.add_argument("--key", default=str(ROOT / ".env"))
    parser.add_argument("--models", default=str(ROOT / "data" / "models" / "meaning"))
    parser.add_argument("--out", default=str(HERE / "results"))
    parser.add_argument("--stamp", default=datetime.now().strftime("%Y-%m-%d_%H-%M"))
    args = parser.parse_args()
    load_keys(args.key)

    import app
    import memory
    from mind import dream, llm, worker

    work = Path(tempfile.mkdtemp(prefix="avy-dream-"))
    source = next(Path(args.memory).glob("*.db"))
    shutil.copy(source, work / source.name)
    memory.embedder.start(Path(args.models))
    memory.embedder.wait(300)
    mem = memory.Memory(work / source.name)
    llm.app.update(ask=app.ask_json, prices=app.PRICES, effort=lambda: "none")
    worker.app.update(page=app.page_size, main=lambda: mem, memories=lambda: [mem])

    before = memory.health(mem)
    nodes0 = {n["chain"] for n in mem.current_nodes()}
    edges0 = {e["id"] for e in mem.live_edges()}
    runs0 = mem.value("SELECT COALESCE(MAX(id), 0) FROM runs")
    heard = []
    d = dream.Dream(main=lambda: mem, tell=lambda event: heard.append(event))
    started = time.time()
    problem = d.start(hours=args.minutes / 60, max_dollars=args.dollars, effort=args.effort)
    if problem:
        raise SystemExit(problem)
    print(f"dreaming on a copy of {source} for up to {args.minutes} min, ${args.dollars}, thinking {args.effort}", flush=True)
    shown = 0
    while d.thread.is_alive():
        time.sleep(5)
        log = d.state.get("log", [])
        for line in log[shown:]:
            print("   ", line, flush=True)
        shown = len(log)
    status = d.status()
    after = memory.health(mem)
    runs = mem.rows("SELECT * FROM runs WHERE id > ? ORDER BY id", runs0)
    new_nodes = [n for n in mem.current_nodes() if n["chain"] not in nodes0]
    new_edges = [e for e in mem.live_edges() if e["id"] not in edges0]
    revised = mem.rows("SELECT * FROM journal WHERE run > ? AND result = 'applied' AND op IN ('revise_edge', 'retract_node', 'oppose')", runs0)
    refused = mem.rows("SELECT why, COUNT(*) n FROM journal WHERE run > ? AND result = 'rejected' GROUP BY why ORDER BY n DESC", runs0)
    by_job = {}
    for r in runs:
        j = by_job.setdefault(r["job"], {"runs": 0, "failed": 0, "cost": 0.0, "seconds": 0.0})
        j["runs"] += 1
        j["failed"] += r["status"] in ("failed", "error")
        j["cost"] += r["cost"] or 0
        j["seconds"] += r["seconds"] or 0

    lines = [f"# A short dream ({args.stamp})", "",
             f"On a copy of `{source.relative_to(ROOT) if source.is_relative_to(ROOT) else source}`, through the real model "
             f"thinking at {args.effort}, for up to {args.minutes:g} minutes and ${args.dollars:g}.", "",
             f"{round((time.time() - started) / 60, 1)} min · {(status.get('last') or {}).get('summary', status.get('state'))} · "
             f"spent ${status.get('spent', 0):.3f} · {status.get('runs', 0)} runs · swept {status.get('swept', 0)} of {status.get('of', 0)} nodes", "",
             "| job | runs | failed | seconds | cost |", "|---|---|---|---|---|"]
    lines += [f"| {k} | {v['runs']} | {v['failed']} | {v['seconds']:.0f} | ${v['cost']:.3f} |" for k, v in by_job.items()]
    lines += ["", "## The network before and after", "", "| measure | before | after |", "|---|---|---|"]
    for k in sorted(set(before) | set(after)):
        if isinstance(before.get(k), (int, float)) or isinstance(after.get(k), (int, float)):
            lines.append(f"| {k} | {before.get(k)} | {after.get(k)} |")
    lines += ["", f"## New connections ({len(new_edges)})", ""]
    for e in new_edges[:40]:
        a, b = mem.current(e["a"]), mem.current(e["b"])
        lines.append(f"- {e['kind']}: {a['title'] if a else e['a']} ↔ {b['title'] if b else e['b']} — {e['reason']}")
    lines += ["", f"## New nodes ({len(new_nodes)})", ""]
    for n in new_nodes[:40]:
        lines.append(f"- k{n['chain']} ({n['shape']}, {n['origin']}{', ' + n['certainty'] if n['certainty'] else ''}): **{n['title']}** — {n['text']}")
    lines += ["", f"## Revised or retracted ({len(revised)})", ""]
    lines += [f"- {r['op']} {r['target']}: {json.loads(r['args']).get('why') or ''}" for r in revised[:30]]
    if refused:
        lines += ["", "## Refused", ""] + [f"- {r['n']}× {r['why']}" for r in refused[:10]]
    lines += ["", "## Its own log", ""] + [f"    {l}" for l in d.state.get("log", [])]
    out = Path(args.out) / f"{args.stamp}_dream.md"
    out.write_text("\n".join(lines) + "\n")
    print(f"\ndone: {out}")
    shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    main()
