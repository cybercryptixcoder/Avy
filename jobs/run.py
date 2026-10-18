"""Run Avy's test jobs and keep a record of everything, for someone else to read and answer questions about later.
No judgment needed to run it: pick jobs, press go, push the results.

    python3 jobs/run.py all                       every job, in order (about 3 hours; cents to a few dollars)
    python3 jobs/run.py offline persona hands     just these
    python3 jobs/run.py --list                    what each job is
    python3 jobs/run.py longrun --stamp 2026-10-18_run1     carry on a run that was interrupted (same stamp)

Every run writes jobs/results/<stamp>/:
    RUN.md            what ran, how long, pass/fail, and where every result file is
    summary.json      the same, for machines
    <job>.log         everything each job printed
and each job's own results stay where it writes them (tests/persona/results, tests/hands/results, ...), listed in RUN.md.
Then whoever ran it answers jobs/QUESTIONS.md into jobs/results/<stamp>/ANSWERS.md, and commits and pushes it all.

Needs: a Luminal key in .env (LUMINAL_API_KEY=...), Python 3.10-3.13, `pip install -r requirements.txt`; the page job
also needs Playwright's Chromium (`python3 -m pip install playwright && python3 -m playwright install chromium`).
A job interrupted (the machine slept, a network drop) can be rerun with the same --stamp: the long ones resume.
"""

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY = sys.executable

# name: (what it is, [commands], timeout in minutes, [result files or folders, with {stamp}])
JOBS = {
    "offline": ("every offline check with a scripted model: memory, Luminal's rules, files, intake, import, dreaming, the desk "
                "and persona, the live runner (a few minutes, free)",
                [[PY, "tests/test_memory.py"], [PY, "tests/test_luminal.py"], [PY, "tests/test_files.py"], [PY, "tests/test_intake.py"],
                 [PY, "tests/test_import.py"], [PY, "tests/test_dream.py"], [PY, "tests/test_desk.py"], [PY, "tests/live/test_runner.py"]],
                30, []),
    "page": ("the page in a real browser against a fake Luminal: basics, commands, inspector, graph, files, look (contrast in "
             "light and dark), the glass (about 15 minutes, free)",
             [[PY, "tests/page/run.py"]], 60, ["tests/page/"]),
    "hands": ("her hands: 11 tasks that need her to act (compute, search, read, write and run code, a background job picked "
              "up later, the calendar, asking before risky things, refusing destructive ones), graded by what she actually did "
              "(about 10 minutes)",
              [[PY, "tests/hands/run.py", "--stamp", "{stamp}"]], 40, ["tests/hands/results/{stamp}.md", "tests/hands/results/{stamp}.json"]),
    "persona": ("the persona eval, three times for variance: the old plain prompt against her constitution and persona on 14 "
                "messages, tics counted by code, a blind judge (about 15 minutes)",
                [[PY, "tests/persona/run.py", "--stamp", "{stamp}_a"], [PY, "tests/persona/run.py", "--stamp", "{stamp}_b"],
                 [PY, "tests/persona/run.py", "--stamp", "{stamp}_c"]], 75,
                ["tests/persona/results/{stamp}_a.md", "tests/persona/results/{stamp}_b.md", "tests/persona/results/{stamp}_c.md",
                 "tests/persona/results/{stamp}_a.json", "tests/persona/results/{stamp}_b.json", "tests/persona/results/{stamp}_c.json"]),
    "longrun": ("twelve simulated days with a simulated Shreyas (coined words, preferences said once, dates, a coding task, a "
                "background run and its decision), then probes with nothing recent in view, a blind fork test, and how her "
                "core changed (about an hour; resumes if interrupted)",
                [[PY, "tests/persona/longrun.py", "--stamp", "{stamp}_longrun"]], 180,
                ["tests/persona/results/{stamp}_longrun_longrun.md", "tests/persona/results/{stamp}_longrun_longrun.json",
                 "tests/persona/results/{stamp}_longrun.memory/transcript.jsonl"]),
    "live": ("the memory scenarios from before the persona work (interference, corrections, files, preferences, whose idea, a "
             "plan, an old Claude history), to see nothing regressed (about 30 minutes, side by side)",
             [[PY, "tests/live/run.py", "--all", "--stamp", "{stamp}"]], 120, ["tests/live/results/"]),
    "bench": ("the memory benchmark: a scripted month, questions that need memory, five search setups, a judge (about an hour)",
              [[PY, "tests/bench/run.py"]], 120, ["tests/bench/results/"]),
}
ORDER = ["offline", "page", "hands", "persona", "longrun", "live", "bench"]


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("jobs", nargs="*")
    p.add_argument("--stamp", default=datetime.now().strftime("%Y-%m-%d_%H-%M"))
    p.add_argument("--list", action="store_true")
    args = p.parse_args()
    if args.list or not args.jobs:
        for name in ORDER:
            print(f"{name:<9} {JOBS[name][0]}")
        return
    names = ORDER if "all" in args.jobs else [j for j in args.jobs if j in JOBS]
    unknown = [j for j in args.jobs if j not in JOBS and j != "all"]
    if unknown:
        raise SystemExit(f"Unknown job(s): {', '.join(unknown)}. Try --list.")
    if not (ROOT / ".env").exists() and not os.environ.get("LUMINAL_API_KEY") and any(n != "offline" and n != "page" for n in names):
        raise SystemExit("These jobs talk to the real model: put LUMINAL_API_KEY=... in .env (or the environment) first.")
    out = ROOT / "jobs" / "results" / args.stamp
    out.mkdir(parents=True, exist_ok=True)
    summary_path = out / "summary.json"
    summary = json.loads(summary_path.read_text()) if summary_path.exists() else {"stamp": args.stamp, "commit": git_commit(), "jobs": {}}
    for name in names:
        about, commands, minutes, files = JOBS[name]
        if summary["jobs"].get(name, {}).get("status") == "passed":
            print(f"{name}: already passed in this run, skipping")
            continue
        print(f"\n=== {name}: {about}", flush=True)
        started, log = time.time(), out / f"{name}.log"
        status, codes = "passed", []
        with open(log, "a") as f:
            f.write(f"\n=== {datetime.now().isoformat(timespec='seconds')} {name}\n")
            for cmd in commands:
                cmd = [c.replace("{stamp}", args.stamp) for c in cmd]
                f.write(f"$ {' '.join(cmd)}\n")
                f.flush()
                try:
                    done = subprocess.run(cmd, cwd=ROOT, stdout=f, stderr=subprocess.STDOUT, timeout=minutes * 60)
                    codes.append(done.returncode)
                    if done.returncode != 0:
                        status = "failed"
                except subprocess.TimeoutExpired:
                    codes.append("timeout")
                    status = "timed out"
                f.flush()
        tail = log.read_text(errors="replace").strip().splitlines()[-12:]
        produced = []
        for pattern in files:
            path = ROOT / pattern.replace("{stamp}", args.stamp)
            if path.exists():
                produced.append(str(path.relative_to(ROOT)))
        summary["jobs"][name] = {"about": about, "status": status, "exit_codes": codes, "minutes": round((time.time() - started) / 60, 1),
                                 "log": str(log.relative_to(ROOT)), "results": produced, "last_lines": tail}
        summary_path.write_text(json.dumps(summary, indent=1))
        write_run_md(out, summary)
        print(f"=== {name}: {status} in {summary['jobs'][name]['minutes']} min", flush=True)
    print(f"\nRecords in {out.relative_to(ROOT)}: RUN.md, summary.json, one log per job.")
    print("Next: answer jobs/QUESTIONS.md into", (out / "ANSWERS.md").relative_to(ROOT), "and commit and push everything.")


def write_run_md(out, summary):
    lines = [f"# Job run {summary['stamp']}", "", f"Code at commit `{summary['commit']}`.", "",
             "| job | status | minutes | log | results |", "|---|---|---|---|---|"]
    for name in ORDER:
        j = summary["jobs"].get(name)
        if j:
            lines.append(f"| {name} | {j['status']} | {j['minutes']} | `{j['log']}` | " + "<br>".join(f"`{r}`" for r in j["results"]) + " |")
    lines += ["", "Each job's last lines:", ""]
    for name in ORDER:
        j = summary["jobs"].get(name)
        if j:
            lines += [f"**{name}** ({j['status']})", "```", *j["last_lines"], "```", ""]
    (out / "RUN.md").write_text("\n".join(lines))


def git_commit():
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    except OSError:
        return "?"


if __name__ == "__main__":
    main()
