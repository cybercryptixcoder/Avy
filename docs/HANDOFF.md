# Handoff: everything a builder needs

For whoever picks Avy up next, person or agent. Read in this order:
1. [../VISION.md](../VISION.md): what we're building and why, what's built, and the open decisions. The idea
   comes first; code serves it. Then [../ARCHITECTURE.md](../ARCHITECTURE.md) for how it all works.
   [BUILDLOG.md](BUILDLOG.md) is the running record: read its newest session's *State of things* first.
2. This file: how it's put together, the contracts, how to run and test it, and the rules of the house.
3. [../MEMORY.md](../MEMORY.md): memory's technical spec (storage, rules, the mind's jobs, recall,
   search).
4. [LUMINAL.md](LUMINAL.md), [FILES.md](FILES.md), [IMPORT.md](IMPORT.md): the provider, attachments,
   the Claude history.
5. [HISTORY.md](HISTORY.md), [IDEAS.md](IDEAS.md), [MISTAKES.md](MISTAKES.md): how it got here, every
   idea (built or not), and what went wrong before.

---

## The rules of the house

These come from Shreyas, and they're not negotiable without asking him.

- **He must understand what's built.** Plans before builds, in clean English (what, why, the contracts),
  then build. No long delegated pipelines that produce code nobody has read. Big coherent pieces, not
  endless tiny versions, and not one giant shot either.
- **One brain.** DeepSeek-V4.1-Flash through Luminal is the only model that decides anything. Local
  models are allowed for senses only (speech-to-text, text-to-speech, meaning search), never for
  judgment.
- **The system handles robustness; the model fills in the blanks.** Anything that must be right every
  time is enforced by code. Model output is a proposal, checked, repaired or refused.
- **Never lose the original.** The log is permanent. Knowledge changes by versions. Connections keep
  their history. Recordings are kept until they rotate out.
- **Test against the real thing.** The failures that matter are behavioral; test with the real model
  (synthetic data), and test the page in a real browser.
- **Keys stay local**: entered in the page, saved to `.env`, never committed. `data/` is never
  committed. The repo is **public**.
- **Concepts from Hermes are fine; no Hermes code.**
- **Never bring up competitors or existing products** unless he asks.
- **Everything Avy saves stays in her folder** (`data/`).
- **He loves a good interface**: terminal-like chat, neo-brutalist side, textured not neon, small
  delightful touches. A UI surprise is always welcome; clutter never is.
- **Cheap to run**: cents a day, not dollars.
- **Private data is probed by code, never read**: counts and shapes, not values.

## Running it

Python 3.10 to 3.13 (Kokoro doesn't support 3.14 yet). From the folder:

```
git checkout -q main && git fetch origin --prune && git reset --keep origin/main && python3 -m pip install -q -r requirements-voice.txt && python3 app.py
```

That installs everything (requirements-voice.txt includes requirements.txt) and opens
http://localhost:8000. The first run downloads the speech models (~0.7 GB) and the meaning model (~65 MB)
into `data/models/`. Paste the Luminal key in the Keys panel once.

| Option | What it does |
|---|---|
| `python3 app.py --memory data/memory-claude.db` (or `AVY_MEMORY=...`) | open another memory file (the imported history) |
| `AVY_NO_BROWSER=1` | don't open a browser tab |
| `LUMINAL_BASE_URL`, `HELIX_FLASH_MODEL` | point at another endpoint or model name (tests use a fake Luminal) |
| `LUMINAL_PARALLEL` | calls at once to Luminal from this process (default 8; the live runner splits 8 between its processes) |
| `python3 luminal.py` | check the key and show the balance |

Ports: 8000 (the page and API, this computer only), 8001 (voice WebSocket).

## The map

```
app.py            the server: page, keys, settings, the Turn (one exchange), endpoints, exports, the page's import
luminal.py        the only model client (rules in docs/LUMINAL.md)
files.py          attached files: kept, read into text and pictures, given to the model
intake.py         the library's intake: anything (files, folders, archives, chat exports) read into passages; one queue
voice.py          push-to-talk: faster-whisper (ears), Kokoro (mouth), a WebSocket on 8001; transcribing attached recordings
index.html        the whole page (HTML, CSS, JS in one file, sections numbered)
CONSTITUTION.md   who she is: the fixed core of her instructions (docs/PERSONA.md)
hands.py          her hands: terminal, files, python, web, jobs, playbooks; safety tiers (docs/HANDS.md)
connectors.py     toolboxes over MCP: data/connectors.json, the browser by default (docs/CONNECTORS.md)
playbooks/        how she goes about kinds of work, read on demand
memory/           stores and searches; never calls the model (MEMORY.md); persona.py (the persona graph),
                  desk.py (the clock, timeline, threads, length gauge, the desk note and its formats)
mind/             persona.py (Keep after each exchange, Reflect on her manner), instruments.py (calendar and thread
                  tools mid-reply); where the model works on memory: llm (one strict tool call), jobs (the engine), writer,
                  reflect (Connect, Think, Check), explore (Avy's own search), worker (when things run),
                  dream (hours of max-thinking reflection, by hand)
tools/            claude_export.py (reads an export), claude_import.py (inspect/import/plan/run/status),
                  copy_log.py (carry a log between memory files)
jobs/             every test packaged to run elsewhere: run.py, facts.py, QUESTIONS.md (jobs/README.md)
tests/            test_memory, test_luminal, test_import, test_files, test_desk (offline); persona/ (the persona eval, the
                  long run), hands/ (the hands eval); bench/ (the benchmark);
                  page/ (browser tests against a fake Luminal)
docs/             these documents
data/             everything Avy saves (gitignored)
```

### One exchange (a typed message)

```
page  POST /api/chat {text, files: [ids]}
app   waits for any attached file still being read
      Turn(text, "text", attached=records):
        window  = the newest /window: messages, word for word
        memory  = explore() if /explore: on (the model steers, /thinking: effort) else recall() by rules
                  (+ the main memory, read-only, while incognito)
        messages = [system: instructions + footnote rule + core (the biggest said hubs)]
                 + window (files attached to those messages, while there's room)
                 + [system: the memory note]
                 + [user: the message + its files in <file> tags + pictures as image parts]
      turn.ask(): opens the stream (luminal.open_stream, /thinking: effort); saves your message (meta.files)
      streams the model's chunks straight to the page; saves the reply (meta: model, recall, usage, cut,
      thought, unseen = footnotes to handles that weren't in anything she was shown; the page marks them)
      worker.nudge(): the mind writes once a sitting's worth is waiting
```

Spoken (live mode) is the same Turn, from `voice.py`, with sentences sent to Kokoro as they finish.

### The mind

`mind/worker.py` runs in a thread. After each reply, and every so often, it writes what's due (a sitting
ended: 30 quiet minutes; or a page's worth waiting), then Connect; in quiet spells it reflects (Check,
Think, Connect) within a daily budget. Every job: prompt → one tool call (`/mind:` effort) → code checks →
problems sent back (up to twice) → `mem.apply_all` → recorded. Imported Claude conversations are never
written by the worker, only by `tools/claude_import.py run`.

## Contracts

### HTTP (all on 127.0.0.1:8000; POSTs only from Avy's own page)

| Route | What |
|---|---|
| `GET /` | the page (no-store, stamped with the server's page version) |
| `GET /api/status` | keys (last 4 characters only), voice status, incognito, page version |
| `GET /api/settings`, `POST /api/settings {name, value}` | the settings schema, values, prices, brain (model, provider, balance, context), files, memory stats |
| `POST /api/keys {LUMINAL_API_KEY}` | save to `.env` |
| `POST /api/chat {text, files}` | SSE: `{"avy": {"searching": ...}}` rounds, `{"avy": {"turn": summary}}`, the model's own chunks, `{"avy": {"saved": id}}`, `[DONE]`; or `{"avy": {"error": msg}}` |
| `GET /api/events` | SSE: `{"hello": true, "page": version}`, then `{"mind": {...}}` for every run, `{"intake": job}`, `{"dream": status}`, `{"history": progress}` |
| `POST /api/files` | the file as the body; `X-File-Name` (URL-encoded); returns its record (`status: reading`) |
| `GET /api/files` | every file's record, newest first |
| `GET /api/files/<id>` | one record: `{id, name, size, mime, kind, status (reading/ready/problem), what, chars, pictures, details}` |
| `GET /api/files/<id>/download[?inline=1]` | the file as it came |
| `GET /api/files/<id>/text` | what Avy read from it |
| `POST /api/files/<id>/import` | import a Claude export (into `data/memory-claude.db`); `GET /api/import` for progress |
| `GET /api/export?what=conversation&format=md\|json` or `what=memory` | downloads |
| `GET /api/library`, `/api/source?id=&after=`, `/api/passage?id=` | the library: sources, a source's passages, one passage (`?memory=`) |
| `POST /api/library/upload` | one file of a folder: the body; `X-Batch` (b + letters) and `X-File-Path` (URL-encoded) |
| `POST /api/library/folder {batch, name}` | the folder has arrived: read it into the library |
| `POST /api/library/add {file}` | an attached file, added to the library by hand |
| `POST /api/intake {pause}` or `{cancel: job}` | control the intake queue |
| `GET /api/glass` | everything the looking glass shows, in one answer |
| `POST /api/history {action: plan\|run\|stop, effort, max_dollars, max_stretches}` | the Claude history's build, as a separate process |
| `POST /api/dream {action: start\|stop, hours, max_dollars, effort}` | dreaming |
| `GET /api/log, /api/memory, /api/node, /api/edge, /api/episode, /api/run, /api/recall, /api/search, /api/graph, /api/journal, /api/health` | the inspector and the graph (`?memory=main\|incognito`) |
| `GET /api/graph?as_of=2026-09-14T10:00:00-04:00` | memory as it stood then (the graph's time slider): versions, connections, strengths, kinds and reasons as of that moment |
| `POST /api/index`, `POST /api/reflect` | write now / reflect now (409 while imported messages wait) |
| `POST /api/incognito {on}` | start or end an incognito conversation |

### Voice (WebSocket on 8001)

From the page: `{"type": "start"}`, binary 16 kHz 16-bit mono PCM while Space is held, `{"type": "stop"}`
(transcribe), `{"type": "cancel"}`, `{"type": "reply", "text"}` (live mode), `{"type": "heard",
"sentences", "cut"}`, `{"type": "retry"}`. To the page: `transcribing`, `transcript {text, file}`,
`recall {...}`, `thinking`, `say {text, silent}` then 24 kHz 16-bit audio, `done {text, usage}`,
`error {text}`. Only the sentences actually heard are saved.

### The model

Every request: `model`, `reasoning_effort`, `max_tokens`, `stream: true` with usage. The mind: one tool,
forced when effort is none, offered otherwise. Contracts of each job's tool (Write, Connect, Think, Check,
explore): MEMORY.md.

### Memory

`Memory` (memory/__init__.py) is one SQLite file. Writes only through `mem.apply(op)` /
`mem.apply_all(ops, run)` (the one door), except `mem.add()` for log messages. Ops and rules: MEMORY.md.
A message is `{id, at, role (user/assistant), text, via (text/voice/claude), meta}`; `meta` may hold
`files` (attachments), `cut`, `usage`, `recall`, and for imported messages `conversation`,
`conversation_name`, `source`, `claude`, `project`, `attachments`.

## Testing

Offline, seconds to a minute each (use the Python that has the packages):

```
python3 tests/test_memory.py      # every memory rule and job with a scripted model
python3 tests/test_luminal.py     # the provider rules: request shape, streams, retries, costs
python3 tests/test_import.py      # a made-up Claude export in every shape, end to end
python3 tests/test_files.py       # every kind of file, made and read; what the model gets
python3 tests/test_intake.py      # the library: every format into passages, the queue, recall and explore finding them
python3 tests/test_dream.py       # dreaming with a scripted model: sweeps, focuses, its own thinking level, budget, waking
python3 tests/live/test_runner.py # the live runner itself: a failed call is recorded, never graded as 0
```

In a browser, against a fake Luminal (`tests/page/README.md`): the page's basics, memory views and the
graph, the errands (dials, incognito, dictation and live voice), files, the look (light and dark with a
contrast audit of every visible text, hovers and menus included; her thinking; sounds), and the glass (the
library, a dropped folder, the looking glass, dreaming). `run.py` first checks that the page's script parses.

With the real model (costs money; synthetic data only):

```
python3 tests/bench/run.py --key .env            # the benchmark: a scripted month, ~30-60 min, see RESULTS.md
python3 tests/bench/run.py --until 2             # a quick try
python3 tests/live/run.py --all                  # live scenarios (tests/live/scenarios.py), side by side, graded
python3 tests/live/run.py files --until 2 --probe-anyway   # a quick try of one
```

## Where things stand

Built: chat, voice, memory v2 (log, knowledge, living network, the mind, Avy's own search), the
inspector, footnotes, chapters, the living graph, incognito, dials, Luminal, files, exports, the Claude
import; and (Oct 15) her thinking kept and shown, the library (anything added becomes searchable passages),
the looking glass, dreaming, dark mode, sounds. Measured: RESULTS.md, tests/live/results.

Waiting on Shreyas: the import's mind run (`tools/claude_import.py run`), which is his to start.

Next: VISION.md §15–16 (the open decisions first), then LATER.md.

## Gotchas

- An old tab against a new server breaks views; the page now reloads itself, but if anything looks like
  an old version, reload.
- The voice models load in the background on start; "voice is loading" for a minute (longer the first
  time, while downloading) is normal.
- The background mind works only when a sitting ends or it's quiet: right after talking, memory looks
  empty. `/index` and `/reflect` force it.
- faster-whisper's own audio decoder breaks on PyAV 19; Avy decodes attached recordings herself
  (`voice.load_audio`). Keep it that way.
- Luminal refuses a forced tool call while thinking; `luminal.prepare()` handles it. Don't "fix" it back.
- Everything under `data/` is private and big; never commit it, never paste it into a prompt for an
  agent.

**Also:** [LANDSCAPE.md](LANDSCAPE.md) (the field), [EXPLORER-BRIEF.md](EXPLORER-BRIEF.md) (the research agent's brief),
[WORKING-WELL.md](WORKING-WELL.md) (its manual), [EXPEDITION-1.md](EXPEDITION-1.md) (what its first run found).
