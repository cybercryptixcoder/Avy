# Handover — read this first

You are picking up work on **Avy**, a personal agent that runs on this machine. This file is the entry point; it tells
you what to read, in what order, and what state everything is in.

## The five-minute version

Avy is a graph-memory agent in `/home/ubuntu/Avy`, running as `avy.service` on `127.0.0.1:8000` behind a cloudflared
tunnel. She has her own memory of a human, an append-only event log, a graph she builds nightly, a "desk" that appends
what a message needs immediately before that message, and tool use over a browser and a shell.

The human asked for a great deal more capability than she has. The work so far is on branch
**`improve/continuity-and-horizon`**; `main` is untouched and there is a safety tag on it. Read `docs/REQUESTS.md` for
what was asked and the status of every item — that file is the requirement; everything else is my attempt at it.

**What is solid:** the harnesses are trustworthy (each was validated before use), the published bars are sourced, the
measured numbers are real, and two harness bugs that produced false *zeros* on her behalf were found and fixed — she is
better than my first reports said.

**What is not:** 10×, parity with a good model, and improvement across all benchmarks were not achieved. Three score
defects are open and named at the bottom of `docs/REQUESTS.md`.

## Read in this order

| file | why |
|---|---|
| `docs/REQUESTS.md` | every request the human made, verbatim where it matters, with status and the number for each |
| `docs/RESULTS.md` | what the eight-item list returned, and the instrument bugs found before any number was trusted |
| `docs/GUARDRAIL.md` | the eight to-do items and the rules I work under |
| `docs/IMPROVE-RULES.md` | the three rules, each learned by breaking it |
| `docs/IMPROVE-NOTES.md` | the long reasoning record: her intent, the code, findings, decisions, the Hermes study |
| `CONCEPT.md`, `ARCHITECTURE.md` | **hers**, not mine — the design intent. Read them; do not skim |
| `docs/HANDS.md`, `docs/CONNECTORS.md` | her tool layer |
| `docs/HISTORY.md` | what was built before I arrived (hers) |

## What exists in the tree, and what each thing is for

| path | what it is |
|---|---|
| `tests/harness/converse.py` | two independent model sessions talk to each other for simulated days; writes a readable `.md` transcript and an event `.jsonl`; continuity probes are scored by keyword against facts planted in the plan |
| `tests/harness/plans/long-a.json`, `long-b.json` | the two day-long plans (86 and 82 exchanges) |
| `tests/bench/` | her own bench: 10 probes × 5 configs, plus `probe.py`, a fast harness that only became trustworthy after calibration against a full run |
| `tests/locomo/run.py` | LoCoMo, external: ingest through her own writer, ask through her real turn path, LLM judge |
| `tests/swe/run.py` | SWE-bench Verified, one instance at a time, graded against a clean base |
| `tests/build/run.py` | three dependent build steps against one memory, checked in a browser |
| `tests/perf/report.py` | latency, tokens, dollars over any run artifacts |
| `tests/test_*.py` | her own offline suites; plain scripts, not pytest. All must pass |

## How to run things

```bash
cd /home/ubuntu/Avy
V=/home/ubuntu/avy-venv/bin/python3

# her own suites — do this before and after any change
for t in tests/test_*.py; do $V "$t" || echo "FAIL $t"; done

# the quick score probe (minutes), after any change to recall or the desk
$V tests/bench/probe.py --configs none,words,meaning,both,explore --tag after-change

# a simulated day, two sessions in parallel
$V tests/harness/converse.py --plan tests/harness/plans/long-a.json --label long-a --max-minutes 240
$V tests/harness/converse.py --plan tests/harness/plans/long-b.json --label long-b --max-minutes 240

# external recall, one conversation
$V tests/locomo/run.py --conv conv-26 --questions 40 --tag full

# software engineering, one instance
$V tests/swe/run.py --instance sympy__sympy-23950

# a multi-step build
$V tests/build/run.py --label b1

# performance over whatever ran
$V tests/perf/report.py tests/harness/out/*.jsonl
```

Datasets are **not** in git (too large). Re-download:

```bash
curl -L -o tests/locomo/data/locomo10.json \
  https://raw.githubusercontent.com/snap-research/locomo/main/data/locomo10.json
# SWE-bench Verified: the 500-row test split of princeton-nlp/SWE-bench_Verified → tests/swe/data/swe_verified.parquet
```

## Traps that will waste your afternoon

- **Import order matters in harnesses.** `app` and `luminal` read the API key at import time. Load `.env` *before*
  importing them, or nothing works and the error is obscure.
- **`app.MEMORIES["main"]` must be populated** before constructing `app.Turn`, or `app.py:589` raises
  `AttributeError: 'NoneType' object has no attribute 'window'`.
- **`hands.WORKSPACE` and `hands.STATE["cwd"]` are separate.** Setting the first does not set the second; the second is
  what `cwd()` and relative paths resolve against.
- **`connectors.start()` must be called** in any harness, or there is no browser and no MCP toolbox.
- **Settings:** `hands="ask"`, `persona="on"`, `footnotes="on"`, `proactive="off"`, `explore` accepts only `on`/`off`
  (`"auto"` is silently dropped).
- **`Rounds.__iter__`:** every `yield` must be at loop top level. Never yield from inside `with self.upstream`, and
  never buffer the whole stream to work around it. Streaming to the page is not negotiable.
- **`luminal.complete()` returns a dict**, not a string. `startswith` on it is always false. This made a grader report
  0/4 when the truth was 3/4.
- **Old checkouts need an old Python.** 2017 sympy does `from collections import Mapping`; on 3.12 pytest exits 4
  without collecting. The SWE grader retries on 3.9. Do not read exit 4 as a failed fix.
- **`FAIL_TO_PASS` carries bare test names**, not node ids. They must be resolved to files first.
- **Reset test files to base** before applying the official test patch, as the official harness does, or a model that
  edited tests shadows them.
- **Do not grade against a tree the subject has committed into.** That is how a correct fix once went ungraded.
- **`pgrep -f` self-matching** in `avy-run.sh` — bracket patterns are load-bearing.
- **Chromium** is at `/home/ubuntu/.cache/ms-playwright/chromium-1243/chrome-linux-arm64/chrome`, needs `--no-sandbox`,
  and `connectors.browser_flags()` self-discovers it. `AVY_BROWSER` overrides.
- **`browser_exec` screenshot capture can hang** on this box; calling Chromium directly with `--headless --screenshot`
  works.

## Where the score defects are, and what to do first

1. **Confirm or kill the temporal hypothesis.** Inspect one node written from session 12 of conv-41 and check whether it
   carries that session's `date_time`. One query. Everything about temporal (0.235 vs 0.60) depends on the answer.
2. **`words` 0.36 → 0.229.** Unexplained regression; nothing in the notes accounts for it. Diff the config against
   `meaning` and find what it stops sending.
3. **`both` scores 0.00 on `tension`** while `meaning` and `explore` score 0.75. Reproduce, read her actual reply, fix
   the cause rather than the prompt string.
4. **Make her open threads.** She never did in 346 messages, so `thread_lines: 0→2` and the desk's in-flight block have
   never been exercised. Fix the behaviour first, then measure the block.
5. **A random SWE sample**, not the three smallest patches. Even 20 instances would be worth more than 3 easy ones.

## How to work here

The rules in `docs/IMPROVE-RULES.md` are short and were each learned by breaking them:

1. **No invented problems.** Findings come from runs. If nothing reproduces, report nothing.
2. **Self-check the instrument before believing its number.** A fast harness is trustworthy only after it agrees with a
   full run on a known item. If a batch of scores is uniformly terrible or perfect, suspect the harness.
3. **A number is not evidence until the code that made it has been checked on one item.** The gold patch must pass
   before a subject's zero means anything.

Plus the human's standing rules: `main` stays clean; `~/Avy/data/` is never deleted and is backed up before risky work;
Avy commits locally but is never pushed; and verification happens from the user side — real browser, real navigation,
screenshots actually looked at, not headless assertions alone.

## Git

```bash
cd /home/ubuntu/Avy
git log --oneline main..improve/continuity-and-horizon    # what I changed
git diff main..improve/continuity-and-horizon --stat      # its shape
```

`main` is the revert point and carries the safety tag. Nothing of hers was force-pushed, and her own uncommitted edits
from before this work were preserved in a stash rather than discarded.
