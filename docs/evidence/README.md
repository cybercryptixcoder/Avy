# Evidence

The raw artifacts behind the numbers in `docs/RESULTS.md` and `docs/REQUESTS.md`. Small enough to keep; anything
larger is regenerated rather than committed.

| file | what it is |
|---|---|
| `2026-10-19_14-50_long-a.md` | full transcript, work day 08:40→21:30 + next morning, 86 exchanges |
| `2026-10-19_14-50_long-b.md` | full transcript, Saturday 08:15→21:40, 82 exchanges |
| `b2.json` | the three-step build: per-step seconds, tokens, tool calls, whether each step changed the file |
| `sympy__sympy-23950.json`, `-13757`, `-12096` | SWE-bench grading: patch applied, pytest output, which interpreter |
| `2026-10-19_13-46_full.json` | LoCoMo conv-26, 77.5%, per-category breakdown, node/edge counts |
| `2026-10-19_14-21_conv41.json` | LoCoMo conv-41, 71.7%, temporal 0.235 — the open defect |
| `probe-2026-10-19_13-02-after-textcall.json` | the fast probe across all five configs after the TextCall fix |

Not committed, because they are megabytes and regenerate in minutes: `tests/harness/out/*.memory`,
`tests/locomo/out/*.memory`, `tests/swe/work/` checkouts, `tests/bench/results/`. The commands to rebuild each are in
`docs/HANDOVER.md`.
