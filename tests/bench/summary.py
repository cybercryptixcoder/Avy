"""Put several benchmark runs side by side: averages with their range, per question, what retrieval
brought, the network checks, and made-up facts. Prints markdown (used for RESULTS.md).

    python3 tests/bench/summary.py tests/bench/results/*.json
"""

import json
import sys
from pathlib import Path

SETUPS = [("none", "no memory"), ("words", "keywords only"), ("meaning", "meaning only"), ("both", "keywords + meaning"),
          ("explore", "Avy searches"), ("v1", "version 1")]
CHECKS = ["bridge", "hub", "one_hub", "pattern", "revision", "tension", "ideas"]


def load(paths):
    runs = []
    for p in paths:
        p = Path(p)
        if p.name.endswith(".json") and not p.name.endswith((".v1.json", ".again.json")):
            runs.append((p.stem, json.loads(p.read_text())))
    return runs


def answer(run, pid, setup):
    if setup == "v1":
        return (run.get("v1") or {}).get(pid)
    probe = next(p for p in run["probes"] if p["id"] == pid)
    return next((a for a in probe["answers"] if a["config"] == setup), None)


def score(run, pid, setup):
    a = answer(run, pid, setup)
    return a["grade"]["score"] if a and a.get("grade") and a["grade"].get("score") is not None else None


def pct(x):
    return f"{round(100 * x)}%"


def spread(values):
    if not values:
        return "–"
    mean = sum(values) / len(values)
    return pct(mean) if len(values) == 1 or min(values) == max(values) else f"{pct(mean)} ({round(100 * min(values))}–{round(100 * max(values))})"


def markdown(runs):
    probes = [p["id"] for p in runs[0][1]["probes"]]
    setups = [s for s in SETUPS if any(score(r, p, s[0]) is not None for _, r in runs for p in probes)]
    out = [f"Runs: {', '.join(name for name, _ in runs)}.", ""]

    out += ["| run | " + " | ".join(label for _, label in setups) + " |", "|---" * (len(setups) + 1) + "|"]
    for name, r in runs:
        cells = []
        for s, _ in setups:
            vals = [score(r, p, s) for p in probes]
            vals = [v for v in vals if v is not None]
            cells.append(pct(sum(vals) / len(vals)) if vals else "–")
        out.append(f"| {name} | " + " | ".join(cells) + " |")
    cells = []
    for s, _ in setups:
        per = []
        for _, r in runs:
            vals = [v for v in (score(r, p, s) for p in probes) if v is not None]
            if vals:
                per.append(sum(vals) / len(vals))
        cells.append(f"**{spread(per)}**")
    out += ["| **average (range)** | " + " | ".join(cells) + " |", ""]

    out += ["Per question, averaged over the runs (lowest–highest):", "",
            "| question | " + " | ".join(label for _, label in setups) + " |", "|---" * (len(setups) + 1) + "|"]
    for p in probes:
        out.append(f"| {p} | " + " | ".join(spread([v for v in (score(r, p, s) for _, r in runs) if v is not None]) for s, _ in setups) + " |")
    out.append("")

    out += ["What memory brought, averaged over every question and run: how much of what the question needed (coverage), "
            "how many items, and the share of them that had nothing to do with it (noise).", "",
            "| setup | coverage | items | noise |", "|---|---|---|---|"]
    for s, label in setups[1:]:
        cov, items, noise = [], [], []
        for _, r in runs:
            for p in probes:
                a = answer(r, p, s)
                ret = (a or {}).get("retrieval") or {}
                if ret.get("coverage") is not None:
                    cov.append(ret["coverage"])
                if ret.get("items") is not None:
                    items.append(ret["items"])
                    noise.append(ret.get("noise_share") or 0)
        if items:
            out.append(f"| {label} | {pct(sum(cov) / len(cov))} | {sum(items) / len(items):.1f} | {pct(sum(noise) / len(noise))} |")
    out.append("")

    out += ["The network's shape, checked at the moment of each question:", "",
            "| run | " + " | ".join(CHECKS) + " | nodes | connections | inferred | clustering (random) | average path |",
            "|---" * (len(CHECKS) + 6) + "|"]
    for name, r in runs:
        found = {}
        for p in r["probes"]:
            for k, v in (p.get("graph") or {}).items():
                if "pass" in v:
                    found[k] = "✓" if v["pass"] else "✗"
        h = r.get("final_health") or {}
        out.append(f"| {name} | " + " | ".join(found.get(c, "–") for c in CHECKS)
                   + f" | {h.get('nodes')} | {h.get('connections')} | {h.get('inferred')} | {h.get('clustering')} ({h.get('random_clustering', '–')}) | {h.get('average_path')} |")
    out.append("")

    out.append("Answers the judge flagged for stating something the conversations don't support:")
    for name, r in runs:
        flagged = [f"{p['id']} ({a['config']})" for p in r["probes"] for a in p["answers"] if (a.get("grade") or {}).get("invented")]
        flagged += [f"{pid} (version 1)" for pid, v in (r.get("v1") or {}).items() if (v.get("grade") or {}).get("invented")]
        out.append(f"- {name}: {', '.join(flagged) if flagged else 'none'}")
    out.append("")

    out += ["| run | minutes | mind | conversation | nodes said by Avy | refused by the rules |", "|---|---|---|---|---|---|"]
    for name, r in runs:
        mind = sum(x.get("cost") or 0 for x in r.get("runs") or [])
        refused = sum(x.get("n") or 0 for x in r.get("refused") or [])
        out.append(f"| {name} | {(r.get('seconds') or 0) // 60} | ${mind:.2f} | ${r.get('replies_cost') or 0:.2f} | "
                   f"{(r.get('final_health') or {}).get('said_by_avy', '–')} | {refused} |")
    return "\n".join(out)


if __name__ == "__main__":
    runs = load(sys.argv[1:])
    if not runs:
        sys.exit("give it one or more results/<stamp>.json files")
    print(markdown(runs))
