# What the user asked for — the whole record, with status

This is the human's own words, session by session, with what came of each. It exists so that a new agent inherits the
*requirement*, not my summary of it. Where I got something wrong, the correction is here too, because a transfer that
hides its mistakes just reproduces them.

Status words: **DONE** (measured, verified), **PARTIAL**, **NOT DONE**, **N/A** (superseded).

---

## Request 1 — 2026-10-18: install and run Avy on this machine

> Run `https://github.com/cybercryptixcoder/Avy.git` on the existing Ubuntu box. Make Python work, password-protect it,
> tunnel it with Cloudflare, keep it alive like Aether. Skip `requirements-voice.txt`. I don't want you to touch files in
> Avy. `~/Avy/data/` is her memory — never delete it; back it up before anything risky. She commits locally and never
> pushes — don't push her commits unless I ask. If the link changes, send me the new one.

**DONE.** Dedicated venv at `/home/ubuntu/avy-venv`, app on `127.0.0.1:8000`, `AVY_PASSWORD` in `.env`, cloudflared
quick tunnel, `avy.service` (systemd, `Restart=always`) driving `/home/ubuntu/avy-run.sh`, which keeps both the app and
the tunnel up and rewrites the public URL. Cron job `avy-tunnel-watch` messages the human when the URL rotates.

Traps that cost time and are still true:
- `read_env()` strips whitespace but **not quotes**, so `AVY_PASSWORD` must be unquoted in `.env`.
- Login is `hmac.compare_digest(given, password())` against the raw value.
- `AVY_NO_BROWSER=1` only stops her opening a local tab; her toolbox still works.
- `pgrep -f` patterns in the supervisor must use bracket tricks (`[a]pp\.py`) or they match their own wrapper.

---

## Request 2 — 2026-10-19 11:00: make a separate branch and improve her, recursively

> Create a completely separate branch on GitHub so I can always revert to this point and continue from there. Work on
> your own branch because the main branch needs to stay clean. Recursively improve AVY: test it, evaluate it, improve
> it, fix it, and so on.

**DONE.** `main` untouched. Safety tag on `main` before any work. All work on `improve/continuity-and-horizon`.

> Run really long simulated conversations as two independent sessions, like a day where we just talk to the agent for
> about 5 hours. This is not in real time. You will have a complete transcript.

**DONE, with a caveat:** two independent sessions, separate memory and workspace, simulated full days — but **23 and 17
minutes of wall clock**, not five hours. Transcripts exist (`tests/harness/out/*long-a.md`, `*long-b.md`).

> These are not supposed to be invented problems or issues. They are meant to be just the things you find.

**HONOURED.** Two of my own findings were retracted publicly when the evidence didn't hold: the checkbox bug
(`.click()` doesn't fire `change`) and the "clock two hours off" claim (the page was right; my reading was wrong).

> Test continuity — whether the agent seems like it has had a lobotomy... Test the capabilities — ask it to build an
> interface or small project, not simple Fibonacci code; watch for stopping midway through thinking and then being
> clueless about having started.

**DONE.** Continuity: 12 probes across the two long sessions, 11/12 by literal keyword, 12/12 on substance. Capability:
several pages built and verified in a real browser. The lobotomy failure was reproduced exactly once (`look-fix3`): she
described a page in the first person without ever looking at it, then admitted it.

> Understand build intent: represent information as a graph, have an infinite context, create a setup where everything
> needed for a given message is appended to that message, have this really interesting storage system.

**DONE (understood and documented).** `CONCEPT.md` and `ARCHITECTURE.md` read in full; the understanding is in
`docs/IMPROVE-NOTES.md` §1. What the desk actually does: a fixed-share note appended immediately before the message,
built the same way every time from the same state.

> Benchmarks will be things from the internet... software engineering, performance and continuity, long-term tasks.

**PARTIAL.** LoCoMo and SWE-bench Verified are external. Performance is now measured (`tests/perf/report.py`).
"Long-term tasks" beyond a simulated day is not measured.

---

## Request 3 — 2026-10-19 11:02: document everything, and test what she builds

> Keep documenting everything: what you learn, discover, and research. Research extensively online. Document not just
> what you are doing, but why. Document what you learned about the intent. Keep documenting what you understand so that
> understanding is available as a reference later on, and keep referring to that reference.

**DONE.** `docs/IMPROVE-NOTES.md` (~700 lines, §1–§16), `docs/IMPROVE-RULES.md`, `docs/RESULTS.md`,
`docs/GUARDRAIL.md`, this file, and the reason-for-the-change comments in the code itself. Published bars are recorded
with sources so a successor can re-check them rather than trust them.

> Once Avy builds something, open it in a browser, take screenshots, evaluate how it looks and feels, and whether it
> has errors. Have a back-and-forth conversation with it, telling it to improve and seeing whether it follows through.

**DONE.** Every page she built was verified from the user side in a real browser. `iterate1`: she found and fixed all
three measured defects in 39.3 s. Screenshots: `avy-build-b2.png`, `avy-plan-fixed.png`, `avy-training-plan.png`.

---

## Request 4 — 2026-10-19 11:59: "I told you to run benchmarks and stuff. Did you do that?"

**NO, and that was true when asked.** Only correctness suites had run. The full in-repo benchmark was launched
immediately after; it had not been running hours earlier as it should have been.

---

## Request 5 — 2026-10-19 12:14: improve further, study Hermes, keep going

> Show me improvements in scores, performance, software engineering, builds, long builds, multi-step builds. I want
> this to be a fully capable system and to function as an agent in itself. Look at your own code as well, since you are
> running on the Hermes agent. See how it is implemented in Hermes, and use that as guidance. Obviously we're using a
> different memory architecture and context architecture, but figure out how we can use the tools, processes, and
> related items to keep track of progress. Use all of that information to inform what changes you make, then keep going
> and keep updating until you see a very significant improvement in all benchmarks. These should be major benchmarks
> that are widely regarded.

**Scores:** PARTIAL. explore 0.69→0.849, meaning 0.74→0.785, both 0.68→0.738, none flat, **words 0.36→0.229 (worse)**.
**Performance:** DONE — p50 1.8 s, p95 4.2 s, $0.0044/turn.
**Software engineering:** DONE — 3/3 sympy, on a deliberately easy sample.
**Builds:** multi-step DONE (3 dependent steps, 382.7 s, zero false claims). **Long builds NOT DONE.**
**Hermes study:** DONE. Two mechanisms adopted — a revisioned task list re-injected after compression (`thread_lines:
0→2`, still unmeasured), and `_verify_on_stop_nudge` → her stop gate (`unchecked_work()`), verified firing in `gate1`.
**"Fully capable agent in itself":** NOT DONE.
**"Significant improvement in all benchmarks":** NOT DONE.
**10×:** NOT DONE.

---

## Request 6 — 2026-10-19 14:46: the eight-item list as a guardrail

> Turn this into a list of things you need to do and a list of rules you need to follow. This is essentially your
> guardrail... For all the tests you want to run on the system, first do a self-check of what you've done. A lot of
> times you told me you tried to test something, but your test itself was broken because you did a bad job coding it.
> Always double-check that first, then actually do it.

The eight items in the human's numbering, with final status:

| # | item | status | the honest number |
|---|---|---|---|
| 1 | long simulated conversations, two independent sessions, full transcript | **DONE (caveat)** | 86 + 82 exchanges; 23 and 17 min, not 5 hours |
| 2 | a second external benchmark category | **DONE** | SWE-bench Verified added to LoCoMo |
| 3 | software-engineering measurement | **DONE** | 3/3 sympy; easy sample, not a benchmark score |
| 4 | builds, long builds, multi-step builds | **PARTIAL** | 3 steps / 382.7 s done; long build not done |
| 5 | 10× improvement | **NOT DONE** | best gain +23% on one config; words regressed |
| 6 | comparable to a really good model online | **NOT DONE** | LoCoMo 71.7–77.5% vs 72.9–87.5% band |
| 7 | keep going until significant improvement in all benchmarks | **NOT DONE** | words, tension, conv-41 temporal all open |
| 8 | performance as an axis | **DONE** | p50 1.8 s, p95 4.2 s, $0.0044/turn |

**The self-check rule earned its place — it caught nine broken instruments**, each of which would have produced a
confident lie. They are listed in `docs/RESULTS.md`, and the two that matter most are repeated here:

- **pytest was not installed**, so every SWE instance would have scored a false zero.
- **Both SWE "failures" were my interpreter**: 2017 checkouts do `from collections import Mapping`, which Python 3.12
  removed, so pytest exited 4 without collecting anything. I reported 1/3; the truth was 3/3. The harness now keeps
  stderr and retries exit-4 on Python 3.9.

---

## Standing rules from the human, still in force

1. `main` stays clean; all work on a branch.
2. `~/Avy/data/` is her memory — never delete it; back it up before anything risky.
3. She commits locally and never pushes; do not push her commits unless asked.
4. Do not invent problems. Worksheet findings come from runs, not from plausibility.
5. Self-check the instrument before believing its number. If a batch of scores is uniformly terrible or perfect, suspect
   the harness first.
6. A number is not evidence until the code that made it has been checked on one item.
7. Verify from the user side: real browser, real navigation, screenshots actually looked at.
8. Keep documenting why, not just what.

---

## Known broken or unmeasured — where the next agent should start

1. **`words` regressed 0.36 → 0.229.** Unexplained. Nothing in the notes accounts for it.
2. **`both` scores 0.00 on `tension`** while `meaning` and `explore` score 0.75. She asks a clarifying question instead
   of sketching; the constitution was changed to say "produce it, don't ask", and it did not fix this config.
3. **conv-41 temporal 0.235 vs conv-26 0.60.** Hypothesis: the writer does not carry each session's `date_time` onto
   its nodes, so "when did X happen" is unanswerable. **Not yet confirmed by inspecting a node.** Do that first — it is
   one query, and everything else about temporal depends on the answer.
4. **`thread_lines: 0→2` was never exercised.** Across 346 messages in the long runs, she used a tool on 7 turns and
   never opened a thread, so the in-flight block never rendered. Fix: she should open a thread when multi-step work is
   agreed; then re-measure.
5. **No long build** (hours). **No random SWE sample.** **No third benchmark.**
6. **`desk_thread` is `None` on every turn** — a consequence of (4), not a separate bug.
7. **Harness outputs are not in git** (~37 MB of runs). The summarised numbers are; raw runs are not. Regenerate with
   the commands in `docs/HANDOVER.md`.
