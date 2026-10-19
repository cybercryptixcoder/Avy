# Rules for this work (from Shreyas, Oct 19 2026)

Short, non-negotiable. If a decision conflicts with these, these win.

## Integrity (the most important one)
1. **No invented problems.** Every issue in a report must point at a real transcript line, a real
   metric, or a real failing check. If I can't cite it, it isn't a finding.
1b. **A fast harness is trusted only after it reproduces two known results from the full run.** A
   harness that silently fails to set itself up reports a tooling failure as a capability failure;
   `probe.py` did exactly that twice (shown_from=None, embedder never started).
2. **Never wreck, weaken, or special-case a test to make a number look better.** No editing a
   benchmark's expectations after seeing results, no tuning to the probe questions, no retrying a
   failing item until it passes and reporting only that run.
3. **A number is not evidence until the code that made it has been checked on one item.** If a
   batch of scores comes back uniformly terrible or uniformly perfect, suspect the grader before
   believing it: open one answer and read it. A grader bug wears the costume of a result — LoCoMo,
   2026-10-19, a dict/str mismatch reported a fabricated 0.0% where the truth was 3/4 (§14).
4. **No poisoned tests.** The system under test never sees the probe questions, the expected answers,
   the scoring rules, or the solutions beforehand. Probes live outside the repo's code path that
   Avy can read.
5. **Real runs only.** Every capability/continuity measurement is a real API call through the real
   Avy turn path (`app.Turn`). No mocks for the numbers I report. (Offline suites stay as
   regression gates — labelled as such, never counted as capability.)
6. **Report the honest number, including when it's bad, and including variance.** Same setup, repeat
   runs, report spread not best-of.
7. **Baseline before and after, same harness.** "Improved 10x" is meaningless without the before.

## What not to do
8. **Do not dumb Avy down into a conventional agent.** No "just use a bigger window", no compaction,
   no summarization-instead-of-memory. The point is constant-size context with the *right* content.
9. **Context must not grow with conversation length.** This is the core claim to protect and measure:
   prompt tokens per turn stay ~flat as the log grows into thousands of messages.
10. **Don't touch `data/`.** Never delete it. Back it up before anything risky.
11. **Never push.** Work on `improve/continuity-and-horizon`; commit locally. Shreyas pushes.
12. **Don't touch files owned by Avy's own uncommitted work** (the logo stash) — leave it restorable.

## What to do
13. **Understand intent first.** Read the docs; the design intent (graph memory, infinite context,
    per-message appended context, constant size) constrains every fix.
14. **Ground truth over my own opinion.** Benchmarks and transcripts decide. If I think something is
    better and the numbers don't agree, the numbers win.
15. **Independent sessions.** The simulator (the "user") and the system under test must be separate
    API contexts that never share state, and the simulator must not know what the system remembers.
16. **Test the specific failure modes he named**:
    - lobotomy / "can't keep up" — refer to something said 1–3 messages ago and see if it's there
    - abandoned work it doesn't remember starting ("oh, someone added this code")
    - stopping mid-task then being clueless about why
    - long-horizon: a task carried across many sittings and interruptions
17. **Iterate until solid, then report** — with a full transcript the user can read himself.
