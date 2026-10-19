# Guardrail

Written 2026-10-19 14:46 at the user's direction: "Turn this into a list of things you need to do and a list of rules
you need to follow. This is essentially your guardrail."

This document is the primary reference for the improvement work. When it disagrees with anything else in `docs/`, this
wins. It exists because the previous phase drifted: the harness, the probes, the notes and the fixes were all real, but
they were the things *around* the list rather than the list.

---

## The rules I work under

1. **Self-check the instrument before believing the measurement.** The user's instruction, verbatim: "a lot of times,
   you told me you try to test something, but you realize your test itself was broken because you did a bad job coding
   it. Always double-check that first, then actually do it." Every harness gets a cheap end-to-end smoke run whose
   *artifacts* I inspect (files exist, transcript has both sides, numbers reconcile) before a long run is launched on
   it. A green exit code is not a passing self-check.
2. **A number is not evidence until the code that made it has been checked on one item.** Already in
   `IMPROVE-RULES.md`, restated here because it is the rule I have broken most often.
3. **No invented problems.** Every defect reported must be reproducible from a transcript, a diff, a test failure, or a
   benchmark record. Retractions are kept in the notes, not deleted.
4. **Do the list, not the surroundings of the list.** If a task on the list is blocked, say which one and why, in the
   same turn, rather than substituting adjacent work.
5. **Report deltas, not adjectives.** Before/after with the same instrument, same items, same configs. "Significant"
   without two numbers is not a result.
6. **Never mutate her memory to make a number look better.** `~/Avy/data/` is not a test fixture. Benchmarks get their
   own memory dirs.
7. **A subset is never reported as the full benchmark.** "n of m, selected how" is the only honest form.
8. **Push through, don't narrate.** Keep working until the item is measured. Report at the end of the batch.

---

## The list — eight items, each a to-do

| # | Item | Done means |
|---|------|-----------|
| 1 | **Long simulated conversations** — hours-long, two independent sessions, full transcript | Two separate memory dirs, each a multi-sitting day of 60+ exchanges, a readable `.md` transcript per session, and a continuity probe set asked inside each. Evidence: transcript files and per-session stats. |
| 2 | **A second external benchmark category** | A benchmark outside memory/recall that is widely used for coding agents, wired to her real turn path, with a published bar named and sourced. |
| 3 | **Software-engineering measurement** — a real number | At least one SWE-bench Verified instance run end-to-end and graded by the official rule (her patch + official test patch + named FAIL_TO_PASS/PASS_TO_PASS). Score reported as "n of m". |
| 4 | **Builds, long builds, multi-step builds** — measured | A build task with 3+ dependent steps, built by her, verified by reopening the artifact in a browser, with time, cost, and defect count recorded. |
| 5 | **10× improvement** | Two numbers from the same instrument, edge → now, on the same items. If it isn't 10×, say the multiple. |
| 6 | **"Comparable to a really good model online"** | Her number placed against a published number from the same benchmark, with the gap stated in points. |
| 7 | **Keep going until significant improvement in all benchmarks** | No benchmark left unmeasured, and no regression left unexplained at the end of the batch. |
| 8 | **Performance as an axis** — speed, throughput, cost, measured deliberately | Per-turn latency (p50/p95), tokens per turn, and dollars per benchmark run, recorded as first-class numbers rather than incidental log lines. |

---

## How the work is sequenced

1. Instrument self-check (rule 1) for anything about to be trusted.
2. The long conversations launch first, because they are the longest clock and can run while other work happens.
3. SWE-bench while the conversations run.
4. The multi-step build after that.
5. Performance measurement is taken *from* the runs above rather than as a separate synthetic exercise, so the numbers
   describe work that actually happened.
6. Every accepted change gets: note in `IMPROVE-NOTES.md` (what, why, measured effect), and a local commit on
   `improve/continuity-and-horizon`. `main` stays clean.

## What "significant" is allowed to mean here

The honest bar, fixed in advance so it cannot be moved afterwards:

- LoCoMo: **+8 points or more** on the same conversations and questions (from 71.7–77.5%).
- Her own bench (`explore`, the config that reflects how she actually runs): **0.849 → 0.90+**.
- SWE-bench: any resolved instance is the floor; the target is **2 of 3** on the same three instances, chosen before
  the fixes.
- Builds: a 3+ step build completed and verified with **zero browser-visible defects** on first delivery.
- Performance: no more than **+10%** latency for any capability gained.

If a change cannot clear its bar, it is reverted and the number is recorded as unchanged.

## Status after this turn

See `docs/RESULTS.md` for every number and how each was verified. Summary: 1 DONE, 2 DONE, 3 DONE (1 of 3 resolved),
4 DONE for multi-step, 5 NOT ACHIEVED, 6 PARTLY, 7 PARTLY, 8 DONE.
