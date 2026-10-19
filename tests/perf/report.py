"""Performance as a first-class number: latency, tokens, dollars.

    python3 tests/perf/report.py tests/harness/out/*.jsonl tests/locomo/out/*.json tests/swe/out/*.json

Why: latency, throughput and cost were previously only visible as incidental lines in logs. The user asked for them
measured deliberately, so they are computed here from the same records the capability numbers come from — no synthetic
benchmark, no separate apparatus that could drift from real behaviour.
"""

import json
import statistics
import sys
from pathlib import Path


def turns_from_jsonl(path):
    for line in Path(path).read_text().splitlines():
        try:
            e = json.loads(line)
        except Exception:
            continue
        if e.get("kind") == "exchange" and e.get("who") == "avy":
            d = e.get("detail") or {}
            yield {"seconds": d.get("seconds"), "prompt": d.get("prompt_tokens"),
                   "completion": d.get("completion_tokens"), "cost": d.get("cost")}


def turns_from_json(path):
    d = json.loads(Path(path).read_text())
    for r in d.get("steps") or []:
        if not isinstance(r, dict):
            continue                       # some artifacts carry lists of strings (tool logs), not turns
        yield {"seconds": r.get("seconds"), "prompt": r.get("prompt_tokens"),
               "completion": r.get("completion_tokens"), "cost": None}
    for r in d.get("results") or []:
        if not isinstance(r, dict):
            continue
        det = r.get("detail") or {}
        yield {"seconds": det.get("seconds"), "prompt": det.get("prompt_tokens"),
               "completion": det.get("completion_tokens"), "cost": det.get("cost")}


def pct(values, q):
    if not values:
        return None
    values = sorted(values)
    k = max(0, min(len(values) - 1, int(round((len(values) - 1) * q))))
    return values[k]


def report(paths):
    rows = []
    for p in paths:
        p = Path(p)
        if p.suffix == ".jsonl":
            got = list(turns_from_jsonl(p))
        elif p.suffix == ".json":
            got = list(turns_from_json(p))
        else:
            continue
        got = [g for g in got if g.get("seconds")]
        if got:
            rows.append((p.name, got))

    print(f"{'run':56} {'n':>5} {'p50':>7} {'p95':>7} {'mean':>7} {'in-pt':>8} {'out-pt':>7} {'$':>8}")
    for name, got in rows:
        s = [g["seconds"] for g in got]
        pin = [g["prompt"] for g in got if g.get("prompt")]
        pout = [g["completion"] for g in got if g.get("completion")]
        money = sum(g["cost"] or 0 for g in got)
        print(f"{name[:56]:56} {len(s):>5} {pct(s,.5):>7} {pct(s,.95):>7} {statistics.mean(s):>7.1f} "
              f"{(statistics.mean(pin) if pin else 0):>8.0f} {(statistics.mean(pout) if pout else 0):>7.0f} "
              f"{money:>8.2f}")

    every = [g for _, got in rows for g in got]
    if every:
        s = [g["seconds"] for g in every]
        money = sum(g["cost"] or 0 for g in every)
        tok = sum((g["prompt"] or 0) + (g["completion"] or 0) for g in every)
        print(f"\nall runs: {len(every)} turns, p50 {pct(s,.5)}s, p95 {pct(s,.95)}s, "
              f"{tok/1e6:.2f}M tokens, ${money:.2f}, ${money/max(1,len(every)):.4f}/turn")


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        sys.exit(__doc__)
    report(args)
