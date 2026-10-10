"""Turns a benchmark result (run.py's JSON) into a readable markdown report.

    python3 tests/bench/report.py tests/bench/results/<time>.json      (rewrites the .md next to it)
"""

import json
import sys
from pathlib import Path


def pct(x):
    return "–" if x is None else f"{round(100 * x)}%"


def markdown(r):
    configs = r["configs"]
    names = list(configs)
    out = [f"# Benchmark {r['stamp']}", ""]
    total = sum((a.get("cost") or 0) + ((a.get("grade") or {}).get("cost") or 0) for p in r["probes"] for a in p["answers"])
    mind = sum((x.get("cost") or 0) for x in r.get("runs", []))
    out += [f"A month of conversation replayed through Avy, then {len(r['probes'])} questions answered at /window: 0 "
            f"under {len(names)} search setups, graded by a separate judge. "
            f"Took {r.get('seconds', 0) // 60} minutes; cost about ${mind + total + r.get('replies_cost', 0):.2f} "
            f"(mind ${mind:.3f}, conversation ${r.get('replies_cost', 0):.3f}, questions and grading ${total:.3f}).", ""]

    out += ["## Scores", "", "Judge score (share of the points a good answer makes), and in brackets how much of what the "
            "question needed memory actually brought.", ""]
    out.append("| question | " + " | ".join(configs[n]["label"] for n in names) + " |")
    out.append("|---|" + "---|" * len(names))
    sums = {n: [] for n in names}
    for p in r["probes"]:
        cells = []
        for n in names:
            a = next((x for x in p["answers"] if x["config"] == n), None)
            if not a:
                cells.append("")
                continue
            s = (a.get("grade") or {}).get("score")
            cov = (a.get("retrieval") or {}).get("coverage")
            if s is not None:
                sums[n].append(s)
            flag = " ⚠" if (a.get("grade") or {}).get("invented") else ""
            cells.append(f"{pct(s)}" + (f" ({pct(cov)})" if cov is not None and n != "none" else "") + flag)
        out.append(f"| {p['id']} | " + " | ".join(cells) + " |")
    out.append("| **average** | " + " | ".join(f"**{pct(sum(v) / len(v))}**" if v else "" for v in sums.values()) + " |")
    out += ["", "⚠ = the judge found something stated as fact that the conversations don't support.", ""]

    out += ["## The network", ""]
    for p in r["probes"]:
        for k, v in (p.get("graph") or {}).items():
            mark = "" if "pass" not in v else ("✓ " if v["pass"] else "✗ ")
            detail = {kk: vv for kk, vv in v.items() if kk != "pass"}
            out.append(f"- {mark}**{k}** (at the {p['id']} question): " + "; ".join(
                f"{kk}: {', '.join(map(str, vv)) if isinstance(vv, list) else vv}" for kk, vv in detail.items()))
    h = r.get("final_health") or {}
    if h:
        out += ["", f"At the end: {h.get('nodes')} nodes ({h.get('said_by_you')} said by Shreyas, {h.get('said_by_avy')} by Avy, "
                f"{h.get('inferred')} inferred; {h.get('things')} things, {h.get('information')} information, {h.get('ideas')} ideas), "
                f"{h.get('connections')} connections, {h.get('islands')} islands (largest holds {pct(h.get('largest_share'))}), "
                f"clustering {h.get('clustering')} (random: {h.get('random_clustering')}), average path {h.get('average_path')} "
                f"(random: {h.get('random_path')}), {pct(h.get('fragile'))} hanging by one connection, top five hubs hold "
                f"{pct(h.get('hub_share'))} of connection ends."]
    if r.get("health"):
        out += ["", "| night | nodes | connections | islands | clustering | average path | inferred |", "|---|---|---|---|---|---|---|"]
        for x in r["health"]:
            out.append(f"| {x['day']} | {x['nodes']} | {x['connections']} | {x.get('islands')} | {x.get('clustering')} | "
                       f"{x.get('average_path')} | {x['inferred']} |")
    if r.get("runs"):
        out += ["", "Mind activity: " + ", ".join(f"{x['job']} ×{x['n']} (${(x['cost'] or 0):.3f}"
                                                  + (f", {x['failed']} failed" if x["failed"] else "") + ")" for x in r["runs"])]
    if r.get("refused"):
        out += ["", "Proposals the rules refused (most common):"]
        out += [f"- {x['n']}× {x['op']}: {x['why']}" for x in r["refused"][:10]]

    out += ["", "## Each question", ""]
    for p in r["probes"]:
        out += [f"### {p['id']} (day {p['day']})", "", f"> {p['ask']}", "",
                "Needs: " + (", ".join(p["needs"]) or "nothing (never said)") + ". A good answer: " +
                " · ".join(f"({i}) {x}" for i, x in enumerate(p["points"], 1)), ""]
        for a in p["answers"]:
            g = a.get("grade") or {}
            marks = " ".join({"met": "●", "partly": "◐", "missed": "○"}.get(m["verdict"], "?") for m in g.get("marks", []))
            ret = a.get("retrieval") or {}
            out.append(f"**{configs[a['config']]['label']}**: {pct(g.get('score'))} {marks}"
                       + (f" · brought {ret.get('items')} items, covered {', '.join(ret.get('covered') or []) or 'nothing it needed'}"
                          f", {ret.get('noise')} unrelated" if a["config"] != "none" else "")
                       + (f" · searched for: *{a['task']}*" if a.get("task") else ""))
            out.append("")
            out.append("> " + a["answer"].replace("\n", "\n> ")[:1200])
            if g.get("invented"):
                out.append(f"\n⚠ made up: {g.get('invented_what')}")
            missed = [f"({i}) {m['why']}" for i, m in enumerate(g.get("marks", []), 1) if m["verdict"] != "met"]
            if missed:
                out.append("\nJudge: " + " ".join(missed)[:600])
            out.append("")
    return "\n".join(out)


if __name__ == "__main__":
    path = Path(sys.argv[1])
    path.with_suffix(".md").write_text(markdown(json.loads(path.read_text())))
    print(path.with_suffix(".md"))
