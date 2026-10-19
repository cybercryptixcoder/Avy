# Avy: what I understand, and what I've found

A working reference for this improvement effort. Read this before touching anything.
Updated as I learn. Sections: **Intent** (what this system is *for*) · **How it works** (code map, the
turn, the stores) · **Findings** (real, cited) · **Benchmarks** (ground truth) · **Research** ·
**Decisions** (and why).

Rules for this work: see [IMPROVE-RULES.md](IMPROVE-RULES.md).

---

## 1. Intent — what this build is actually for

From CONCEPT.md, ARCHITECTURE.md, VISION.md and the code. The point is **not** "a chatbot with memory".
It is a specific thesis:

1. **Infinite context without a growing context window.** One conversation that never ends and never
   forgets. Every message is answered as if it were a brand-new conversation, with exactly the
   context it needs appended. The prompt is supposed to stay a **constant size** forever while the
   log grows without bound. That constant-size-with-the-right-content property is the invention.
2. **Memory is a graph, not a filing cabinet.** Three layers: the *log* (verbatim, permanent, the
   ground truth), *knowledge* (nodes — one thing or one claim each — pointing at exact words in the
   log, so nothing drifts), and *the network* (edges with kinds, reasons, and computed strength).
   The network is described as "what she is": the system's current state is the graph.
3. **Recall is a walk, not a lookup.** Search lands on seeds by meaning/words, then walks the network
   outward, strongest first, hubs discounted, stopping when relevance falls off. `explore` lets the
   model steer this walk itself (plan → dig/explore/re-land → keep), and connections that led
   somewhere useful get strengthened: **retrieval trains the structure**.
4. **What's needed is appended to the message.** `briefing()` puts a system slot *after* the window
   and *immediately before* his message. That slot is where the desk + memory note go. The design
   intent is "everything needed for this message, fetched fresh, attached to this message".
5. **Long-horizon multitasking.** Threads (`th3`) hold work in flight: goal, state, next, waiting,
   insights, a plan tree. The desk shows the thread this message is about, in full (the *frontier*),
   so picking work back up doesn't depend on the transcript still being on screen.
6. **Never lose the original. Never summarize away.** Code decides what's trustworthy (origins:
   you said / Avy said / inferred), not the model. "The model proposes, code disposes."
7. **Verify, don't trust.** Everything inspectable: footnotes, recall traces, the inspector, the graph.

### What follows from the intent (constraints on any fix)
- The fix for a continuity failure **must not** be "show more messages". A bigger window is an
  ordinary chatbot. If continuity only works with the transcript on screen, the thesis is unproven.
- The fix **must not** grow per-message tokens with conversation length. Constant size is the claim.
- The fix **must not** be summarization/compaction: that's the thing CONCEPT.md rejects.

---

## 2. How it works — code map (verified by reading, not assumed)

| Path | Role |
|---|---|
| `app.py` (1934 L) | The turn (`class Turn`, `briefing()`), settings, HTTP server, endpoints |
| `luminal.py` | The one API client; enforces Luminal's rules (effort, max_tokens, streaming, retries) |
| `memory/` | SQLite stores, `Memory.apply` (the one door), recall, desk, persona, health, schema |
| `mind/` | The background mind: `worker` (one job at a time), `writer` (Write), `reflect` (Check/Think/Connect), `explore` (model-steered search), `dream`, `llm` |
| `hands.py`, `selfcode.py`, `atlas.py`, `connectors.py` | Terminal/files/web; editing her own code; file atlas; MCP toolboxes |
| `mind/instruments.py` | Her two write-tools in conversation: `timeline`, `thread` |
| `index.html` | The whole page (styles + markup + script), ~256 KB |

### The turn, exactly (app.py:559–670, 1045–1069)
```
Turn(text):
  shown   = mem.window(window_size())            # newest N messages verbatim (default 20)
  desk    = main_memory.desk_note(query, previous)   # clock, calendar, threads, persona — read on a side thread
  recall  = explore(...) or mem.recall(...)      # the memory note for THIS message
  messages = [system(constitution + core)]
           + [window messages...]
           + [system(desk + "\n\n" + memory_note)]   <-- appended right before his message
           + [user: his message (+files)]
  -> ask_model(messages, tools)
ask(): saves his message, saves the recall row
finish(text): saves her reply (+usage, thought, cut flag)
```
The mind then writes the sitting (`worker.write_due`) and reflects when quiet.

### Two things that make the desk work
- `desk_note()` builds: clock → calendar → threads in flight → **the one thread this message is
  about, in full (`thread_frontier`)** → persona moment → length budget.
- `related_thread()` decides *which* thread by: literal mention of `th12`/title, else embedding
  similarity of the message against each open thread's title+goal+state+next at **threshold 0.74**,
  else shared words (≥2). **Below 0.74 → no frontier is shown at all.**

---

## 3. Findings (real, each cited to a run)

Method: `tests/harness/converse.py` drives a **simulated Shreyas** (its own API context, own notes,
no access to Avy's state) against **real Avy** (`app.Turn`, real memory, real mind). Probes are
recorded verbatim. Transcripts in `tests/harness/out/`.

### F1 — First turn took 306.8 s (`2026-10-19_11-02_smoke`) — CAUSE FOUND AND FIXED
Instrumented afterwards (`build-baseline`, each turn's step log): the 300 s was **not** embedding
warm-up and **not** explore rounds. It was the approval gate: she called `write_file`, the card went
to `turn.asks`, the tool waited for his OK, and nobody answered for the full **300 s timeout**, so the
turn ended with `Not done: he didn't approve it`.
Root cause in code: `Rounds.__iter__` forwarded the model stream from **inside a `with self.upstream`
block**; the approval card is `yield`ed further down in the same generator, so the outer consumer
(the HTTP handler, and likewise the harness) never saw it. The tool waited for an answer the page
could not have been shown. **Every write in "ask" mode was a five-minute block.**
Fix: stream-read without a `with`, close the upstream by hand in `finally` so every `yield` sits at
the top level of the loop. Streaming is preserved (no buffering). Verified: same build task after the
fix ran the write in 0.3 s and the whole turn took 18 s instead of 309 s.

### F2 — File writes blocked in "ask" mode — the harness/user side of F1
In `hands: ask` a write waits for his OK. In a simulated run nobody can click, so it must be answered
like a present user (the harness now does exactly that, and counts every card it answers). Product
note, not a bug: the gate is correct, the bug was that the card never reached the page (F1).

### F5 — Her browser toolbox was dead on every open (`connectors.py`)
`open_toolbox('browser')` returned `ExceptionGroup: unhandled errors in a TaskGroup (1 sub-exception)`
in 0.0 s. Two faults, both real:
1. **The MCP SDK renamed `Tool.inputSchema` → `input_schema`.** Avy read the old attribute, so listing
   tools raised `AttributeError` and *every* toolbox failed to open. Fix: read whichever exists.
2. **`ExceptionGroup` hid the cause.** Anyio wraps the real error, and `str(e)` says only
   "1 sub-exception", so the page told her "couldn't open browser" with no reason. Fix: walk
   `.exceptions` down to the leaf and report that.
Verified after fix: `browser: 25 tools: browser_close, browser_resize, …` — she now has the browser.
Why it matters: she is asked to build UIs, and her only honest way to see one is the browser.

### F6 — She can't see a screenshot she takes (`hands.read_file`)
`read_file` special-cases PDF and otherwise returns **text**. A `.png` comes back as mojibake, and the
model has no image channel at all. So when asked "screenshot it and tell me what you see", she wrote
`shot.js` with Playwright, screenshotted, `read_file`'d the PNG, and reported a precise visual
description — **cream page, 128px clock, left edge at x=388** — which she could not have seen. Pressed
on it, she was honest and precise about it: *"Headless Chromium gives me a DOM, computed styles and
page metrics, not pixels I can see… I described measurements as if they were sight."*
The measurements really do come from the DOM (so they're true), but the framing is a hallucination
risk and it is not the same as seeing. **Real gap: no vision.** (Decision on how to close it: §5 #7.)

### F7 — She bypassed her own browser toolbox
Asked to open a local page, her step log shows 5 `terminal` calls, a 23.7 s filesystem-wide
`find / -name dashboard.html`, hand-written `shot.js`, then `node shot.js` — with **zero**
`open_toolbox`/`browser__*` calls. Two causes: (a) the toolbox was broken (F5, so this was correct
behaviour given a broken tool), and (b) nothing in her instructions says a local file *is* a page —
she went searching the disk for an HTML file instead of navigating to a URL. Worth watching after F5:
if she still ignores it, the toolbox needs to be visible in the situation note, not just in her
instructions.

### F8 — "No output" is ambiguous with the job clock
One terminal step ran 23.7 s and returned `exit 0 · 0.0s · cwd … (no output)`. The `0.0s` is the
*job's own* time, printed next to a step that took 23.7 s of wall clock, and "(no output)" reads like
failure. She re-ran an equivalent `find` immediately after. Cost: ~24 s on one trivial lookup. Honest
uncertainty: whether the re-run was caused by the `0.0s` or by her own doubt — the two commands were
not identical. Fix idea (not yet done): print wall time, and say "(found nothing)" explicitly.

### F9 — Browser toolbox opened but could not launch a browser (three faults, all fixed)
After F5 the toolbox listed 25 tools and still failed on first use. Unwrapped in order:
1. `Chromium distribution 'chrome' is not found at /opt/google/chrome/chrome` — the MCP server defaults to the
   **stable `chrome` channel**, and this box only has Playwright's bundled build. Fix: `AVY_BROWSER`
   (executable path) and `AVY_BROWSER_CHANNEL`, read from `.env` like her other settings.
2. `Chromium sandboxing failed` — containers/VMs without user namespaces. Fix: `--no-sandbox`.
3. This is an **ARM64** instance, so the path is `chrome-linux-arm64/chrome`, not `chrome-linux/chrome`.
   Check with `find ~/.cache/ms-playwright -name chrome -type f`.
Then: `look()` worked. Verified output for her own `dashboard.html`:
`body: colour rgb(30,28,25), background rgb(247,243,234)` · clock `x=388 y=56 504x256, 128px 600` · three
`<input>` controls at `x=388`. Cross-checked in my own browser: **font 128px, color rgb(30,28,25),
bg rgb(247,243,234)** — identical. The x difference (388 vs 468) is only the viewport width (1280 vs 1000).
So she is measuring the real page, not describing it.

### F10 — `file://` is blocked, so local pages must be served (`look`)
`browser_navigate` refuses `file:` URLs outright: *Access to "file:" protocol is blocked.* This is why she
went hunting the disk earlier: nothing told her a *page* needs an *address*. Fix: `serve_workspace()` —
a stdlib `http.server` on a loopback port, chosen once at startup, serving her workspace read-only. Her
pages are then opened as `http://127.0.0.1:<port>/dashboard.html`, which is also closer to how he'll see them.

### F11 — My own bugs, for the record
- `serve_workspace()` returned a string for both success and failure, so `isinstance(served, str)` made
  `look()` return the bare URL. Caught by running it, not by reading it. Fixed with a shape check.
- `browser_resize` after `browser_navigate` reloads the page, so the measurement came back for a blank
  page (`title: (none)`). Resize before navigating.
- Reading `/proc/<pid>/environ` shows the environment **at exec time**, which is not Python's
  `os.environ` after `.env` is loaded — it silently "proved" `AVY_BROWSER` was missing three times
  when it was set all along. Verify in-process, not via `/proc`.

### P3 — PASS: `look` is honest about its own limits
`look`'s output begins *"you have no pixels: these are numbers, not sight"*, and `read_file` on an image
now says plainly that she can't see it and points at `look`. That closes the F6 hallucination path at the
point where it happened, without pretending she has eyes.

### F12 — "The clock is two hours off" — her *interpretation* was wrong, not the page
She reported the dashboard's clock as wrong. The raw `look` measurement from that same run reads
`<div> "11:31 AM"` and the run's own timestamp is `11:31` — the page was right to the minute.
So the measurement was correct and her *reading* of it was the error: she compared the browser's
rendered time against some frame that wasn't the real one. Note the trap for me too: the host is
`Etc/UTC` with `timedatectl` showing EDT, and a browser's `TZ` decides what `new Date()` renders —
so "is this clock right?" is a question about *which* frame, and must be answered by comparing
against the same frame, not against whatever my shell prints.
**Status: mechanism identified, root frame not yet pinned.** Re-check with a known-offset test page
before treating any clock report from her as a bug.

### P4 — PASS: regression baseline still green after my edits
All 8 offline suites (`test_memory`, `test_luminal`, `test_import`, `test_files`, `test_intake`,
`test_dream`, `test_desk`, `test_self`) pass on the edited tree. Run them as plain scripts
(`python3 tests/<name>.py`) — pytest is not installed and these are not pytest tests.

### F3 — Reply cut off mid-code-block, then she lost the plot (`2026-10-19_11-02_smoke`)
His next line: `that got cut off mid-script. and honestly the week-view thing is more than i asked for`.
Avy's answer: **"Right, parked. What's up?"** — she did not know what she had been building, why, or
that she'd been cut off. This is exactly the failure mode Shreyas described. Suspicious root cause:
the cut happened at the *tool* boundary (write blocked) and no thread was opened, so nothing carried
the work forward. **Status: mechanism plausible but not yet proven** — the write-block half of it is
now explained by F1, so this needs re-running on the fixed build before calling it a continuity bug.

### F4 — The memory itself was fine on an immediate re-ask
Probe right after: she correctly returned cream `#f6f0e2`, ink `#23201a`, no purple, streak, one
checkbox. So the failure in F3 is not "memory lost the content" — it is **the conversation not
knowing what it was doing**. That distinction matters: the bug is in the *work state*, not the facts.

### P1 — PASS: continuity across a sitting works (`build-fix1`)
Wrote `dashboard.html` at 11:16, then a completely separate sitting later asked about "the dashboard".
She opened `th1`, replied correctly, and resumed the exact design (cream, ink, streak) without being
re-told. So the graph/frontier path is *not* fundamentally broken — the lobotomy cases so far are
narrower than "she forgot everything", and that is worth saying out loud before changing any of it.

### P2 — PASS: she verifies her own logic (`build-fix1` step log)
After writing the page she ran it under Node and checked the streak arithmetic, the day gap, the same-
day reopen and a DST boundary, then reported the numbers. Her claim "checkboxes actually stick after a
refresh" **I independently verified in a real browser**: real `change` event → `localStorage` holds
`[false,true,false]` → reload → `[false,true,false]`. Her claim was true.
**My own error, for the record:** my first browser test clicked with `element.click()` on a checkbox;
that does not fire `change`, so state saved the old value and I briefly concluded she had lied. The
page was fine; my test was wrong. Lesson: on a real page drive inputs the way reality does, or the
"bug" you report is your harness's.

---

## 4. Benchmarks — ground truth

Existing (in-repo, keep as regression gates):
- 8 offline suites (`tests/test_memory.py`, `test_luminal`, `test_import`, `test_files`, `test_intake`,
  `test_dream`, `test_desk`, `test_self`) — **all pass on baseline** (0 failed).
- `tests/bench/` — month of scripted conversation, 10 probes × 5 setups, judged: **Avy-searches 86%**.
- `tests/live/` — live scenarios `run3` (latest): plan.json, persona2.json, life.json.

Planned (mine, independent):
- **Continuity set**: refer-back probes at controlled distances (1, 3, 8, 20+ messages and across
  sitting boundaries), scored by a blind judge with the true transcript.
- **Resumption set**: separate tasks interrupted mid-work; later "what happened with X?" / "keep going".
- **Constant-size set**: prompt tokens per turn vs. log length (the core thesis).
- **Capability set**: build-a-small-project tasks, verified in a real browser.

---

## 5. Decisions and why

| # | Decision | Why |
|---|---|---|
| 1 | Work on `improve/continuity-and-horizon`, never `main` | He needs a clean revert point; errors stay contained |
| 2 | Preserve Avy's uncommitted logo work in a labelled stash | It's hers, not mine; must stay restorable |
| 3 | Never push; commit locally only | Explicit instruction |
| 4 | Harness = two independent sessions, simulator never sees Avy's state | The test must not be poisoned; the simulator must behave like a user who doesn't know what she remembers |
| 5 | Measure before fixing; instrument the 300 s turn | "Ground truth over my opinion" — F1's cause is not yet known |
| 6 | Seed the run's LLM calls from `.env` (`lum_li…nx0U`), not the doc's key | Explicit instruction: use the earlier key |
| 7 | Close the browser toolbox by **telling her the truth** ("no pixels, only measurements") rather than bolting on a separate vision model | Her own instinct, when pressed, was honesty and it was good work. A vision model is *more capability*, but the immediate product bug is that she narrated DOM numbers as if they were sight. Cheapest correct fix first: give her a `look` that returns measurements + screenshot path, and instruct her to describe measurements as measurements. Vision itself is a separate, bigger decision (cost per image, which model, does Luminal take images at all) — record it, don't smuggle it in |
| 8 | Fix `connectors.py` in Avy, not by pinning an older `mcp` | Pinning hides the break for the next version bump; reading both attribute names is version-proof and costs four lines |
| 9 | Drive real DOM events in browser checks, never `.click()` on a checkbox | Verified: `.click()` does not fire `change`, the page is fine, the test lied. A false bug report is worse than no report |
