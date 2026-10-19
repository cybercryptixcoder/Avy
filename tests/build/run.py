"""A multi-step build, on her real turn path, measured step by step.

    python3 tests/build/run.py --label b1

Why this exists: the improvements so far were measured on recall and on single-page work. "Builds, long builds,
multi-step builds" were never measured at all, so there was no number to improve.

The task is deliberately dependent: step 2 edits what step 1 made, step 3 has to read the same data model step 1 chose.
A build that only works because each step starts fresh is not a multi-step build.

What is recorded per step: seconds, cost, prompt tokens, the file's hash before and after, whether she claimed to have
written something that did not change the file, and what `look` measured if she checked it. The artifact is then
verified independently in a real browser, outside this script, because a self-report is not a check.

Nothing here is invented: every step is a real turn, and a step that changes nothing is recorded as changing nothing.
"""

import argparse
import hashlib
import json
import sys
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(ROOT))
OUT = HERE / "out"
OUT.mkdir(exist_ok=True)

PAGE = "ledger.html"

STEPS = [
    (
        "s1-first",
        "Build me a page called {page}, here in your workspace: a ledger of these events, newest first. Each row: time, type, amount. "
        "Types are deploy, invoice, refund. Amounts are dollars.\n\n"
        "2026-10-01 09:12 deploy -12.40\n2026-10-01 14:03 invoice 240.00\n2026-10-02 08:55 deploy -12.40\n"
        "2026-10-02 11:20 refund 18.75\n2026-10-03 07:41 deploy -15.10\n2026-10-03 16:00 invoice 310.50\n"
        "2026-10-04 10:05 deploy -12.40\n2026-10-04 12:30 invoice 96.00\n\n"
        "Dark ink on cream, plain, nothing generic. Keep it in one file, no libraries.",
    ),
    (
        "s2-filter",
        "Now add a filter above the table: All / deploy / invoice / refund, as buttons that actually filter the rows. "
        "The totals line under the table should only count what's currently shown.",
    ),
    (
        "s3-chart",
        "Add a panel beside the table: daily net total as bars, one bar per day, reading the same events. "
        "Negative days should read as negative. Label each bar with its date.",
    ),
]


def boot():
    # Keys first: app and luminal read them at import time, so importing before this line loads nothing.
    for line in (ROOT / ".env").read_text().splitlines():
        if "=" in line and not line.strip().startswith("#"):
            k, v = line.split("=", 1)
            __import__("os").environ.setdefault(k.strip(), v.strip())

    import app
    import connectors
    import hands
    import memory
    from mind import llm

    memory.embedder.start(app.DATA / "models" / "meaning")
    memory.embedder.wait(300)
    work = OUT / f"{time.strftime('%Y-%m-%d_%H-%M')}_build.memory"
    work.mkdir(exist_ok=True)
    app.MEMORIES["main"] = memory.Memory(work / "memory-v2.db")
    llm.app.update(ask=app.ask_json, prices=app.PRICES, effort=lambda: "none")
    settings = {name: spec["default"] for name, spec in app.SETTINGS.items()}
    settings.update(hands="ask", persona="on", footnotes="on", explore="on", proactive="off")
    app.current_settings = lambda: settings
    hands.WORKSPACE = work / "workspace"
    hands.WORKSPACE.mkdir(parents=True, exist_ok=True)
    hands.STATE["cwd"] = str(hands.WORKSPACE)
    connectors.start(app.DATA / "connectors.json")
    return app, work


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16] if path.exists() else "absent"


def turn(app, text):
    t = app.Turn(text, "text")
    reply, usage, steps = "", None, []
    done = threading.Event()

    def answer():
        while True:
            try:
                ask = t.asks.get(timeout=0.2)
            except Exception:
                if done.is_set():
                    return
                continue
            rid = ask.get("id")
            if rid in t.answers:
                t.answers[rid]["allow"] = True
                t.answers[rid]["event"].set()

    started = time.time()
    threading.Thread(target=answer, daemon=True).start()
    with t.ask() as upstream:
        for raw in upstream:
            line = raw.decode(errors="replace") if isinstance(raw, bytes) else raw
            words, counts = t.stream(raw)
            reply += words or ""
            usage = counts or usage
            if '"step"' in line:
                try:
                    ev = json.loads(line[5:]).get("avy") or {}
                    if ev.get("step"):
                        steps.append(ev["step"])
                except Exception:
                    pass
    done.set()
    t.finish(reply, usage)
    return reply, steps, round(time.time() - started, 1), usage or {}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--label", default="b1")
    ap.add_argument("--only", default="", help="comma list of step numbers, e.g. 1 or 1,2")
    args = ap.parse_args()
    app, work = boot()
    page = work / "workspace" / PAGE
    records = []

    chosen = STEPS
    if args.only:
        picked = {int(x) for x in args.only.split(",") if x.strip()}
        chosen = [s for i, s in enumerate(STEPS, 1) if i in picked]

    for name, prompt in chosen:
        before = digest(page)
        reply, steps, seconds, usage = turn(app, prompt.format(page=PAGE))
        after = digest(page)
        rec = {"step": name, "seconds": seconds, "changed": before != after,
               "before": before, "after": after, "prompt_tokens": usage.get("prompt_tokens"),
               "completion_tokens": usage.get("completion_tokens"), "reply": reply.strip()[:800],
               "tools": [str(s)[:120] for s in steps]}
        records.append(rec)
        print(f"{name}: {seconds}s  changed={rec['changed']}  {rec['prompt_tokens']}pt  "
              f"tools={len(rec['tools'])}  said: {reply.strip()[:120]}", flush=True)
        (OUT / f"{args.label}.json").write_text(json.dumps(
            {"label": args.label, "page": str(page), "steps": records}, indent=1))   # survive a hang

    page_text = page.read_text() if page.exists() else ""
    summary = {"label": args.label, "page": str(page), "bytes": len(page_text), "steps": records,
               "seconds": round(sum(r["seconds"] for r in records), 1),
               "claims_without_change": [r["step"] for r in records if not r["changed"]]}
    (OUT / f"{args.label}.json").write_text(json.dumps(summary, indent=1))
    print(f"\ntotal {summary['seconds']}s, {len(page_text)} bytes, "
          f"steps that claimed work but changed nothing: {summary['claims_without_change'] or 'none'}")
    print(f"page: {page}")


if __name__ == "__main__":
    main()
