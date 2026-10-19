# Results — 2026-10-19, the eight-item list

Every number here came from a run whose instrument was checked first. Where the instrument was wrong, the fix is
recorded before the number.

## 1. Long simulated conversations — DONE

Two independent sessions, separate memory, separate workspace, run in parallel.

| | long-a | long-b |
|---|---|---|
| day | work day 08:40 → 21:30, then 09:05 next morning | Saturday 08:15 → 21:40 |
| exchanges | 86 | 82 |
| wall clock | 23 min | 17 min |
| cost | $0.43 | $0.31 |
| transcript | `tests/harness/out/*long-a.md` | `tests/harness/out/*long-b.md` |

168 exchanges, both sides recorded, 11/12 continuity probes hit their planted fact by literal keyword. The miss
(`a5`) is a false negative of the checker: she wrote "nothing renumbers" instead of the literal "old ids". On
substance it is 12/12. A keyword check is a crude instrument and is labelled as such.

## 2. Second external benchmark category — DONE

SWE-bench Verified. 500 instances downloaded; grader validated against the official **gold patch** before any
score was believed.

## 3. Software-engineering measurement — DONE, and it is 3 of 3

| instance | diff | time | result |
|---|---|---|---|
| sympy__sympy-23950 | 39 lines | 8.3 min | **resolved** — 8 passed |
| sympy__sympy-13757 | 27 lines | 5.1 min | **resolved** — 39 passed, 2 skipped |
| sympy__sympy-12096 | 19 lines | 3.6 min | **resolved** — 37 passed, 4 skipped |

**3/3**, every patch applying cleanly to its base commit and passing both the official FAIL_TO_PASS and a slice of
PASS_TO_PASS.

**This sample is not comparable to the published 79.2%.** Those three are the *smallest patches in sympy*, picked on
purpose so the harness could be debugged cheaply. Selecting easy instances and reporting the result as a benchmark
score would be exactly the dishonesty this file exists to prevent. It says she can close a small, well-specified bug
in a large unfamiliar codebase in under ten minutes — not that she solves a third of SWE-bench Verified.

Three harness bugs had to be fixed before that number meant anything, and the third one inverted the result:
1. `pytest` was not installed in the venv, so every instance would have scored a false zero.
2. `FAIL_TO_PASS` ships bare names (`test_as_set`), not node ids — pytest collected nothing. The gold patch
   failed, which is how this was caught.
3. She edited the test file, so the official test patch would not apply. The official harness resets test files
   to base before applying its own; mine now does too.
4. **Scored on Python 3.12 against 2017 checkouts, pytest exited 4 (could not collect) because those trees do
   `from collections import Mapping`. That was recorded as "failed" and reported as 1/3.** The harness now treats
   exit 4 as an interpreter mismatch and re-runs on Python 3.9 with mpmath. Corrected: 3/3. The failure was mine,
   not hers, and the first number I gave the user was wrong.

## 4. Builds, long builds, multi-step builds — DONE for multi-step

Three dependent steps against one memory: build the page → add a working filter → add a chart reading the same
data. Each step measured.

- step 1: 20.0 s, 6 tools, file written
- step 2: 20.6 s, 9 tools, file changed
- step 3: ~342 s, file changed
- total 382.7 s (6.4 min), 12,608 bytes, **zero claims without a corresponding change**
- verified by me in a real browser: filters present and active-stated, table totals correct, chart per-day values
  match the ledger, no overflow or placeholder text

A "long build" in the hours sense was not run. The longest single step was 5.7 min.

## 5. 10× improvement — NOT ACHIEVED

- explore 0.69 → 0.849 (+23%)
- meaning 0.74 → 0.785 (+6%)
- both 0.68 → 0.738 (+9%)
- none 0.26 → 0.287 (flat)
- words 0.36 → 0.229 (**regression**)

The largest honest gain is 23% on one config of her own bench. That is not 10×, and two of five configs are flat
or worse.

## 6. Comparable to a really good model — PARTLY

- LoCoMo: 71.7% and 77.5% on two conversations, against a full-context band of 72.9–87.5%. Bottom of the band.
- SWE-bench Verified: 3 of 3 on the three smallest sympy patches. Resolved, but the sample is deliberately easy and
  is **not** a benchmark score; it does not support a claim of parity.
- No third benchmark, no sample large enough to claim parity.

## 7. Keep going until significant improvement in all benchmarks — PARTLY

This turn was one continuous push through all eight items with no reporting break. `words` and `tension` remain
open defects; the temporal hole on conv-41 (0.235) is still unexplained at ingest.

## 8. Performance as an axis — DONE

`tests/perf/report.py`, over 171 turns:

| run | n | p50 | p95 | mean | in-tokens | $ |
|---|---|---|---|---|---|---|
| long-a | 86 | 2.0 s | 4.2 s | 3.1 s | 12,974 | 0.43 |
| long-b | 82 | 1.6 s | 2.3 s | 1.7 s | 10,454 | 0.31 |
| b2 build | 3 | 20.6 s | 342.1 s | 127.6 s | 180,657 | — |

**p50 1.8 s, p95 4.2 s, $0.0044 per turn, 2.54M tokens, $0.75 total.**

## Instrument defects found by the self-check, before any number was trusted

1. The harness promised a readable transcript and never wrote one. It does now.
2. `planted` was declared and never populated, so continuity had no oracle. Now read from the plan.
3. Both long sessions shared one workspace — not independent. Now per-run.
4. `pytest` missing → false zeros.
5. Bare test names → zero tests collected. Gold patch proved it.
6. Test file edited by her → official patch rejected. Now reset to base first.
7. `app` imported before `.env` loaded → no API key.
8. Perf script crashed on a list of strings.
9. Her prompt never said where her workspace was, so she wrote to the repo root. Now stated in her instructions.
