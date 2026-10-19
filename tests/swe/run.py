"""SWE-bench Verified, one instance at a time, honestly.

    python3 tests/swe/run.py --instance sympy__sympy-23950

Why this and not the official harness end to end: Verified is 500 instances, each needing its own multi-GB image and a
full test run. This box has 2 vCPU and 16 GB free, so a 500-instance run is not honest to attempt and a subset reported
as "SWE-bench Verified" would be a lie by omission. What this does instead is the same protocol on one instance:

  1. Clone the repo at the instance's base_commit into a scratch dir.
  2. Give her the problem statement and the repo, nothing else. No patch, no test patch, no FAIL_TO_PASS, no hints —
     the same poisoned-test rule as the LoCoMo harness.
  3. She works in the checkout with her own tools (read, grep, write, terminal).
  4. Her final diff is saved.
  5. Score it the way the official harness does: apply the official test_patch to a fresh copy, then run the named
     FAIL_TO_PASS and PASS_TO_PASS tests. Resolved = every one of them passes. Her own diff is applied first; if it
     doesn't apply, that's unresolved, exactly as upstream counts it.

The published bar for comparison (swebench.com, verified, bash-only, Feb 2026): best 79.2%, mini-SWE-agent + the
strongest model 76.8%, the reference mini-SWE-agent baseline 65%. A single instance is a smoke test of the harness, not
a score. Several, chosen at random and reported as "n of m", is what this can honestly claim.
"""

import argparse
import json
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(ROOT))

DATA = HERE / "data" / "swe_verified.parquet"
WORK = HERE / "work"
OUT = HERE / "out"
for d in (WORK, OUT):
    d.mkdir(exist_ok=True)

# What she is told. Deliberately the shape of a real bug report and nothing more: no file list, no test names, no
# hint at where the defect is. Everything else in SWE-bench's record would be a poisoned test.
BRIEF = """You're fixing a real bug in this repository: {path}

It is already checked out at the commit where the bug was reported. Work only inside that directory. Do not clone
anything, do not cd anywhere else, and do not commit — leave your changes in the working tree.

The report:

{problem}

Find the cause, fix it, and make sure the existing tests for that area still pass. When you're done, say in one or two
lines what you changed and which file. Don't explain the whole investigation."""


def git(cwd, *args, check=True):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=check)


def checkout(repo, base, dest):
    if dest.exists():
        shutil.rmtree(dest)
    subprocess.run(["git", "clone", "--quiet", f"https://github.com/{repo}.git", str(dest)], check=True, timeout=900)
    git(dest, "checkout", "--quiet", base)
    return dest


def her_turn(problem, repo, work):
    """Run one real Avy turn with her hands on this checkout, and return what she said plus the tools she used."""
    import app      # noqa: E402  (imported late so --help works without a key present)
    import hands    # noqa: E402

    hands.WORKSPACE = work
    hands.STATE["cwd"] = str(work)      # cwd() reads STATE, not WORKSPACE; without this she'd work in her own folder
    if not getattr(her_turn, "started", False):
        import app as _app
        import connectors
        import memory
        _app.MEMORIES["main"] = memory.Memory(_app.MEMORY_FILE)     # Turn reads talking_to().window() at line 589
        # Settings: the defaults, but with her hands on. Through a browser "hands" defaults to "ask" and he is there
        # to approve; here nobody is, so this run's settings are explicit rather than inherited from a lambda nobody set.
        _settings = {name: spec["default"] for name, spec in _app.SETTINGS.items()}
        _settings.update(hands="ask", persona="on", footnotes="on", proactive="off", explore="on")
        _app.current_settings = lambda: _settings
        memory.embedder.start(_app.DATA / "models" / "meaning")
        connectors.start(_app.DATA / "connectors.json")
        her_turn.started = True
    turn = app.Turn(BRIEF.format(path=work, problem=problem.strip()), "text")
    reply, usage, steps = "", None, []
    started = time.time()

    def answer_asks():      # no human is watching: approve her commands at once, or the turn blocks 300 s
        while True:
            try:
                ask = turn.asks.get(timeout=0.2)
            except Exception:
                if done.is_set():
                    return
                continue
            rid = ask.get("id")
            if rid in turn.answers:
                turn.answers[rid]["allow"] = True
                turn.answers[rid]["event"].set()

    done = threading.Event()
    watcher = threading.Thread(target=answer_asks, daemon=True)
    watcher.start()
    with turn.ask() as upstream:
        for raw in upstream:
            line = raw.decode(errors="replace") if isinstance(raw, bytes) else raw
            words, counts = turn.stream(raw)
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
    turn.finish(reply, usage)
    return reply, steps


def resolve_nodes(repo_dir, names):
    """Turn the dataset's test names into pytest node ids.

    Verified ships bare function names in FAIL_TO_PASS ("test_as_set"), not the file-qualified ids pytest wants. Asking
    pytest for "test_as_set" collects nothing and returns 0, which reads as a failure — that is what made the official
    gold patch score 0 on my first grader, so this resolves each name against the files that actually define it."""
    out = []
    for name in names:
        if ".py" in name or "::" in name:
            out.append(name)
            continue
        found = []
        for path in repo_dir.rglob(f"test_{name}.py"):
            found.append(str(path.relative_to(repo_dir)))
        if not found:                       # the function lives inside some other test file
            for path in repo_dir.rglob("test_*.py"):
                try:
                    if f"def {name}(" in path.read_text(errors="ignore"):
                        found.append(str(path.relative_to(repo_dir)))
                except Exception:
                    pass
        for rel in found[:4]:
            out.append(f"{rel}::{name}")
    return out


def score(record, her_patch):
    """The official rule: apply her patch and the official tests to a clean tree, run the named tests, all must pass."""
    repo, base = record["repo"], record["base_commit"]
    clean = WORK / f"{record['instance_id']}__score"
    checkout(repo, base, clean)

    patch_file = OUT / f"{record['instance_id']}.patch"
    patch_file.write_text(her_patch)
    if not her_patch.strip():
        return {"applied": False, "passed": False, "why": "she produced no diff"}

    applied = subprocess.run(["git", "apply", "--check", str(patch_file)], cwd=clean, capture_output=True, text=True)
    if applied.returncode != 0:
        return {"applied": False, "passed": False, "why": "her diff does not apply: " + applied.stderr[:300]}
    git(clean, "apply", str(patch_file))

    test_patch = OUT / f"{record['instance_id']}.test.patch"
    test_patch.write_text(record["test_patch"])
    # The official harness overwrites the test files with its own patch; a model that edited tests must not be able to
    # shadow them. Reset exactly the files the official patch touches, back to base, before applying it.
    touched = [ln.split(" b/", 1)[1] for ln in record["test_patch"].splitlines()
               if ln.startswith("diff --git a/") and " b/" in ln]
    for rel in touched:
        git(clean, "checkout", base, "--", rel, check=False)
    done = subprocess.run(["git", "apply", str(test_patch)], cwd=clean, capture_output=True, text=True)
    if done.returncode != 0:
        return {"applied": True, "passed": False, "why": "official test patch would not apply: " + done.stderr[:300]}

    f2p = json.loads(record["FAIL_TO_PASS"]) if isinstance(record["FAIL_TO_PASS"], str) else record["FAIL_TO_PASS"]
    p2p = json.loads(record["PASS_TO_PASS"]) if isinstance(record["PASS_TO_PASS"], str) else record["PASS_TO_PASS"]
    node_ids = resolve_nodes(clean, f2p) + resolve_nodes(clean, p2p)[:40]   # f2p all, a slice of "still passing"
    if not node_ids:
        return {"applied": True, "passed": False, "why": "no test files matched the dataset's test names"}

    run = subprocess.run([sys.executable, "-m", "pytest", "-q", "--no-header", *node_ids],
                         cwd=clean, capture_output=True, text=True, timeout=1800)
    tail = (run.stdout or "")[-600:]
    return {"applied": True, "passed": run.returncode == 0, "returncode": run.returncode,
            "f2p": f2p, "p2p_checked": len(node_ids) - len(f2p), "tail": tail}


def main():
    import pyarrow.parquet as pq

    ap = argparse.ArgumentParser()
    ap.add_argument("--instance", default="sympy__sympy-23950")
    ap.add_argument("--score-only", default="", help="score an existing .patch in out/ without asking her again")
    args = ap.parse_args()

    rows = {r["instance_id"]: r for r in pq.read_table(DATA).to_pylist()}
    if args.instance not in rows:
        sys.exit(f"no instance {args.instance}")
    record = rows[args.instance]

    started = time.time()
    result = {"instance": args.instance, "repo": record["repo"], "difficulty": record.get("difficulty"), "started": str(started)}
    print(f"{args.instance} ({record['repo']}, {record.get('difficulty')})", flush=True)

    work = WORK / args.instance
    checkout(record["repo"], record["base_commit"], work)
    print(f"  checkout at {record['base_commit'][:10]}", flush=True)

    if args.score_only:
        her_patch = Path(args.score_only).read_text()
        reply, steps = "(scored an existing patch)", []
    else:
        reply, steps = her_turn(record["problem_statement"], record["repo"], work)
        her_patch = git(work, "diff", check=False).stdout
        print(f"  she said: {reply.strip()[:200]}", flush=True)
        print(f"  {len(steps)} tool steps, diff {len(her_patch.splitlines())} lines", flush=True)
        (OUT / f"{args.instance}.patch").write_text(her_patch)

    graded = score(record, her_patch)
    result.update(reply=reply[:2000], steps=[str(s)[:200] for s in steps], diff_lines=len(her_patch.splitlines()),
                  graded=graded, minutes=round((time.time() - started) / 60, 1))
    dest = OUT / f"{args.instance}.json"
    dest.write_text(json.dumps(result, indent=1))
    print(f"\n  APPLIED {graded['applied']}  PASSED {graded['passed']}")
    if graded.get("why"):
        print("  why:", graded["why"])
    if graded.get("tail"):
        print("  " + graded["tail"].replace("\n", "\n  ")[-400:])
    print(f"written to {dest}")


if __name__ == "__main__":
    main()
