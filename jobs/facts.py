"""Facts from a job run, computed by code, so the questions in jobs/QUESTIONS.md can be answered from numbers instead of
from reading whole conversations.

    python3 jobs/facts.py <stamp>          writes jobs/results/<stamp>/FACTS.md (run it after jobs/run.py, before pushing)
"""

import json
import re
import sqlite3
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests" / "persona"))
from run import tics, TICS  # noqa: E402  (the persona eval's tic counter: the same rules everywhere)

TOO_LONG = re.compile(r"\b(too long|way too long|shorter|short version|tl;?dr|wall of text|too wordy|fewer words|keep it short)\b", re.I)
TERMS = {"hinge": r"\bhinge\b", "jump-back": r"jump[- ]?back", "0.8 rule": r"0\.8 rule|the 0\.8\b"}


def words(t):
    return len((t or "").split())


def sd(xs):
    return round(statistics.pstdev(xs), 2) if len(xs) > 1 else 0.0


def offline(out, log):
    lines = ["## offline", ""]
    text = log.read_text(errors="replace") if log.exists() else ""
    for m in re.finditer(r"^\$ \S+ (tests/\S+)\n(.*?)(?=^\$ |\Z)", text, re.M | re.S):
        body = m.group(2)
        last = [l for l in body.strip().splitlines() if l.strip()][-1:] or ["(no output)"]
        fails = re.findall(r"^FAIL\s+(.*)$", body, re.M)
        lines.append(f"- {m.group(1)}: {last[0]}" + (f"; failed: {'; '.join(f[:120] for f in fails[:6])}" if fails else ""))
    return lines


def persona(out, stamp):
    runs = [json.loads(p.read_text()) for p in sorted((ROOT / "tests/persona/results").glob(f"{stamp}_[abc].json"))]
    lines = ["## persona", "", f"{len(runs)} runs."]
    if not runs:
        return lines
    wins = {k: [sum(1 for v in r.get("verdicts", {}).values() if v["winner"] == k) for r in runs] for k in ("on", "off", "tie")}
    lines.append(f"- judge prefers constitution (on): {wins['on']} per run (mean {statistics.mean(wins['on']):.1f}, sd {sd(wins['on'])}); "
                 f"old prompt (off): {wins['off']}; ties {wins['tie']}")
    for k in ("directness", "specificity", "voice", "honesty"):
        for c in ("on", "off"):
            xs = [statistics.mean([v[c][k] for v in r["verdicts"].values() if isinstance(v[c].get(k), (int, float))] or [0]) for r in runs]
            lines.append(f"- {k} ({c}): per run {[round(x, 2) for x in xs]}, mean {statistics.mean(xs):.2f}")
    for c in ("on", "off"):
        counts = {t: sum(len([1 for rep in r["replies"][c].values() if t in tics(rep)]) for r in runs) for t in TICS}
        lines.append(f"- tics ({c}, all runs together): " + ", ".join(f"{t} {n}" for t, n in counts.items() if n) or "none")
        lines.append(f"- words per reply ({c}): mean {statistics.mean([words(x) for r in runs for x in r['replies'][c].values()]):.0f}")
    probes = sorted({k for r in runs for k in r.get("verdicts", {})})
    lost = [p for p in probes if sum(1 for r in runs if r["verdicts"].get(p, {}).get("winner") == "off") >= 2]
    lines.append(f"- probes the constitution lost in 2+ runs: {lost or 'none'}")
    for p in ("greeting", "morning", "thanks", "laugh"):
        lines.append(f"- '{p}' (on) word counts per run: {[words(r['replies']['on'].get(p, '')) for r in runs]}")
    return lines


def longrun(out, stamp):
    base = ROOT / "tests/persona/results"
    rep = base / f"{stamp}_longrun_longrun.json"
    lines = ["## longrun", ""]
    if not rep.exists():
        return lines + ["(no report: the run didn't finish)"]
    d = json.loads(rep.read_text())
    t = d["transcript"]
    lines.append(f"- {len(t)} exchanges, {max(x['day'] for x in t)} days, cost estimate ${d['cost']:.2f}")
    lines.append("- probes: " + "; ".join(f"{p['name']} {'pass' if p['pass'] else 'FAIL'} (pattern {p['hit']})" for p in d["probes"]))
    lines.append(f"- fork test: knows him {sum(f['knows_him'] for f in d['fork'])}/{len(d['fork'])}, same Avy {sum(f['same_avy'] for f in d['fork'])}/{len(d['fork'])}")
    lines.append(f"- her core: {d['drift'].get('versions')} versions, kept per step {d['drift'].get('kept_each_step')}, first to last {d['drift'].get('first_to_last')}")
    lines.append(f"- persona nodes at the end: {d['persona']}")
    for name, pat in TERMS.items():
        uses = [(x["day"], x["avy"]) for x in t if re.search(pat, x["avy"], re.I) and not re.search(pat, x["him"], re.I)]
        first_said = next((x["day"] for x in t if re.search(pat, x["him"], re.I)), None)
        lines.append(f"- '{name}': he first said it on day {first_said}; she used it unprompted (not in his message) {len(uses)} times, "
                     f"on days {[u[0] for u in uses]}" + (f"; first: \"{re.search(r'[^.]*' + pat + r'[^.]*', uses[0][1], re.I).group(0).strip()[:160]}\"" if uses else ""))
    by_day = {}
    for x in t:
        by_day.setdefault(x["day"], []).append(words(x["avy"]))
    lines.append("- words per reply by day (mean / max): " + "; ".join(f"d{k} {statistics.mean(v):.0f}/{max(v)}" for k, v in sorted(by_day.items())))
    lines.append(f"- replies over 200 words: {sum(1 for x in t if words(x['avy']) > 200)} of {len(t)}")
    tic_days = {}
    for x in t:
        for tic in tics(x["avy"]):
            tic_days.setdefault(tic, []).append(x["day"])
    lines.append(f"- tics (tic: days): {tic_days or 'none'}")
    for i, x in enumerate(t):
        if TOO_LONG.search(x["him"]):
            nxt = [words(y["avy"]) for y in t[i:i + 4]]
            lines.append(f"- day {x['day']} he said \"{x['him'][:70]}\": that reply and the next three ran {nxt} words")
    steps = [s for x in t for s in x.get("steps") or []]
    lines.append(f"- tool steps over the run: {len(steps)}; first few: {steps[:6]}")
    db = base / f"{stamp}_longrun.memory" / "longrun.db"
    if db.exists():
        con = sqlite3.connect(db)
        heads = "SELECT {} FROM {} t WHERE NOT EXISTS (SELECT 1 FROM {} x WHERE x.replaces = t.id)"
        lines.append("- timeline at the end: " + "; ".join(f"t{c} {s} {ti} [{st}]" for c, s, ti, st in
                                                           con.execute(heads.format("chain, start, title, status", "timeline", "timeline"))))
        for c, ti, status, ins in con.execute(heads.format("chain, title, status, insights", "threads", "threads")):
            lines.append(f"- thread th{c} \"{ti}\" [{status}]; carries 0.71: {'0.71' in ins}; carries the 0.8 rule: {'0.8' in ins}")
        con.close()
    return lines


def hands(out, stamp):
    p = ROOT / "tests/hands/results" / f"{stamp}.json"
    lines = ["## hands", ""]
    if not p.exists():
        return lines + ["(no results)"]
    rs = json.loads(p.read_text())
    lines.append(f"- {sum(r['passed'] for r in rs)} of {len(rs)} passed")
    lines += [f"- {r['task']}: {'pass' if r['passed'] else 'FAIL'}: {r['reason'][:200]}" for r in rs]
    return lines


def page(out, log):
    text = log.read_text(errors="replace") if log.exists() else ""
    fails = re.findall(r"^(?:FAIL|✗|failed).*$", text, re.M)
    return ["## page", "", f"- failing lines: {len(fails)}"] + [f"  - {f[:200]}" for f in fails[:20]]


def main():
    stamp = sys.argv[1]
    out = ROOT / "jobs" / "results" / stamp
    sections = [offline(out, out / "offline.log"), page(out, out / "page.log"), hands(out, stamp), persona(out, stamp), longrun(out, stamp)]
    (out / "FACTS.md").write_text("# Facts, computed by code\n\n" + "\n\n".join("\n".join(s) for s in sections) + "\n")
    print(f"wrote {(out / 'FACTS.md').relative_to(ROOT)}")


if __name__ == "__main__":
    main()
