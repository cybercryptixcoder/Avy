# Avy

A personal agent built from scratch, one small piece at a time, so every line is understood. Her heart is
a memory that never forgets and never summarizes anything away: one endless conversation, turned into a
living network of knowledge that she thinks about when it's quiet.

- **[VISION.md](VISION.md)**: what we're building: the whole idea, what's built, what's next, and the open
  decisions. Start here.
- **[ARCHITECTURE.md](ARCHITECTURE.md)**: how it works and how the unbuilt parts are meant to work: what kind of
  graph, every store, the jobs, search, dreaming, internal memory.
- **[CONCEPT.md](CONCEPT.md)**: what Avy is today, in plain words: the experience.
- **[MEMORY.md](MEMORY.md)**: how memory is built: storage, rules, the mind's jobs, the algorithms.
- **[docs/HANDOFF.md](docs/HANDOFF.md)**: everything a builder needs: the map, the contracts, running and testing.
- **[docs/BUILDLOG.md](docs/BUILDLOG.md)**: the running record of the build: what was done, learned and tried, the
  state of the code, what's next. A new session picks up from here.
- **[docs/LUMINAL.md](docs/LUMINAL.md)**: the model provider and its rules.
- **[docs/FILES.md](docs/FILES.md)**: attaching files of any kind, and getting things out.
- **[docs/IMPORT.md](docs/IMPORT.md)**: bringing in your Claude history.
- **[docs/HISTORY.md](docs/HISTORY.md)**: how Avy came to be, from the conversation itself.
- **[docs/IDEAS.md](docs/IDEAS.md)**: every idea and consideration so far, and where each stands.
- **[docs/MISTAKES.md](docs/MISTAKES.md)**: what went wrong along the way, and what was learned.
- **[VERSIONS.md](VERSIONS.md)**: the versions kept side by side, and how to go back or fork.
- **[LATER.md](LATER.md)**: what's decided but not built yet.
- **[tests/bench/RESULTS.md](tests/bench/RESULTS.md)**: how well it works, measured.

## Rules

- **One brain:** DeepSeek-V4.1-Flash, through Luminal (a US-hosted provider). No other model does the
  thinking; local models only hear, speak, and search by meaning.
- **Small steps:** each change is something you can try right away.
- **Keys stay local:** API keys are entered in the app and saved to a local `.env`, which is never committed.

## Running it

From this folder, every time (it brings the code up to date with GitHub, installs anything new, and runs;
already-installed packages are skipped):

```
git checkout -q main && git fetch origin --prune && git reset --keep origin/main && python3 -m pip install -q -r requirements-voice.txt && python3 app.py
```

`reset --keep` moves the code to what's on GitHub even if the history was rewritten (it was, once, on Oct 15,
so every commit is in Shreyas's name). It never touches `data/` (memory, files, recordings) or `.env` (keys),
which git doesn't track, and if a code file was edited locally it stops with a message instead of overwriting.

If a plain `git pull` once said "divergent branches" (a copy cloned before Oct 15), this fixes it, once:

```
cp -R data "../Avy-data-backup-$(date +%Y%m%d-%H%M)"; cp .env "../Avy-env-backup-$(date +%Y%m%d-%H%M)" 2>/dev/null
git branch -f old-claude-history
git stash push -m "local edits before the history rewrite"
git fetch origin --prune
git checkout -q main && git reset --hard origin/main
git config pull.ff only
```

Your browser opens http://localhost:8000. Paste your Luminal key in the Keys panel once (the orange key
button); it's saved to `.env` and you're set. Needs Python 3.10–3.13 (Kokoro doesn't support 3.14 yet).
`python3 luminal.py` checks the key and shows your balance.

The first time version 2 runs, it copies your conversation (the log) from version 1's `data/memory.db`
into its own `data/memory-v2.db`, and rebuilds memory from it in the background over a few minutes. The
old file is left exactly as it was.

## Using it

- **Type** at the prompt, Enter to send.
- **Dictate:** hold Space and talk; let go and your words appear in the text box, to edit and send yourself.
  Tap Space twice (on an empty box) to lock it on for long stretches; press Space again to finish, or Esc to
  throw it away. With text already in the box, a tap still types a space and a hold dictates more.
- **Live conversation:** `/live: on`. Then Space talks to Avy and she answers out loud; tap Space while she
  talks to cut her off. Only what you heard is saved.
- **One endless conversation.** There's no new chat: every message gets its own memory, fetched fresh.
  Reloading brings the conversation back; `[ load earlier ]` goes further back. Each sitting is marked
  with when it was and, once memory has written it, what it was about (click that to see what was kept).
- **Footnotes.** Where a reply uses memory there's a small number: hover it to see what memory said and
  whose words it was, click it to open it.
- **How much context Avy gets:**
  - `/window:` how many recent messages she reads word for word: 0, 5, 10, 20 (default), 40, 80, or all.
  - `/recall:` how far memory reaches: off, light, normal (default), deep, max.
  - `/words:` and `/meaning:` switch the two halves of memory search; both off means no memory at all.
  - `/explore:` on (the default) lets Avy search her memory herself, step by step: a few seconds slower,
    and much better at finding what a message really needs. You'll see what she's looking at while she
    does. Off searches by rules, instantly.
- **How hard Avy thinks:** `/thinking:` none (the default, fastest), low, high or max (DeepSeek's three
  levels), for her answers and her search; `/mind:` the same for the background mind. When she thinks, her
  thinking shows folded above her reply (`▸ thought for 12.4s`: click to read it); it's kept with the reply.
  The top bar shows your Luminal balance; the "spent" tile is an estimate.
- **Files:** `[ attach ]`, drop, or paste anything: documents, spreadsheets, slides, PDFs, code, pictures
  (she sees them), audio and video (she hears them, and sees frames). Ask her for a file and `[ save ]`
  on it downloads it. `/files` lists what you've attached; `/export` downloads the conversation
  (`/export: json`, `/export: memory`). See docs/FILES.md.
- **The library: anything you add becomes memory.** Every file you attach also joins memory's library, read
  into passages that memory can search from then on (so "what did that doc say about retries?" works days
  later). Drop whole folders (a codebase, a project) or more files in the looking glass. Any format: documents,
  code, data, recordings, pictures (described once), and conversations from anywhere (Claude or ChatGPT
  exports, WhatsApp, transcripts). `/library` shows what's in it. See docs/FILES.md.
- **The looking glass:** `/glass` (or the Glass button) shows everything loading into memory (with how long
  it'll take), memory's numbers, what the mind is doing and what went wrong, your Claude history's build
  (plan, build with a budget, stop), dreaming, and what it costs.
- **Dreaming:** `/dream` opens the looking glass, where you start a dream: hours of reflection at max
  thinking over all of memory, within a budget (8 hours and $10 by default). Wake her any time.
- **Look and sound:** `/theme:` auto, light or dark (or the sun/moon button), `/sounds:` on, soft or off.
- **Your Claude history:** attach the export and press `[ import ]`, or `python3 tools/claude_import.py`
  (docs/IMPORT.md). It goes into its own memory, `data/memory-claude.db`; open it with
  `python3 app.py --memory data/memory-claude.db`. Turning it into knowledge is a separate, longer run
  that only you start.
- **Incognito:** `/incognito` starts a separate conversation. Avy can still use her memory, but nothing
  said there is kept: it has its own temporary memory, deleted when you end it.
- **Memory's own work:** it writes each sitting into knowledge when the sitting ends, and reflects when
  it's quiet (finding connections, patterns, and things that changed), within a small daily budget.
  `/index` writes now; `/reflect` reflects now. The system card's "mind" line shows what it's doing.
- **Under the hood:** `/memory` opens the inspector:
  - every node like a wiki page: where it was said, what it rests on, its connections, its versions
  - every connection with why it exists and how strong it is
  - every conversation, and every run of the mind with exactly what the model was shown and answered
  - the journal of every change, and the network's health

  `↳ recalled 3 nodes` under a reply shows what memory brought for it, and how.
- **The graph:** the little network in the corner is Avy's memory. Click it (or `/graph`) to open it
  full page: drag to turn it, scroll to zoom, hover or click a node.
- **Commands:** type `/` and the panel opens on the right, each command with a few words saying what it
  does. Keep typing to narrow it, Tab to complete, ↑↓ to pick, Enter to run.
- **System card** (left): the main settings as dropdowns, and memory's numbers.

## Where things live

Everything stays in this folder:

- `.env`: your keys (see `.env.example`).
- `data/memory-v2.db`: everything ever said, and the knowledge and network built from it.
- `data/memory.db`: version 1's memory, if you used it (left as it was).
- `data/settings.json`: your choices from the system card or `/` commands.
- `data/models/`: the speech models (about 0.7 GB) and the meaning-search model (about 65 MB), downloaded on the first run.
- `data/recordings/`: a backup of everything you say, written as you talk, with its transcript next to it.
  The newest 50 (up to 300 MB) are kept; older ones are deleted. `/retry` re-transcribes the newest one.
- `data/files/`: files you attached, each as it came, with what Avy read from it.
- `data/memory-claude.db`: your imported Claude history, if you imported it.
- `data/library/`: folders you added to memory, kept as they came (files attached in the chat stay in `data/files/`).
- `data/incognito/`: an incognito conversation's memory, recordings and files, only while it's going.

`data/` and `.env` are never committed.

## What's here

- `app.py`: the server: the page, keys, settings, files, exports, and every exchange with the model (typed or spoken).
- `luminal.py`: the only model client, and the rules it follows (docs/LUMINAL.md).
- `files.py`: attached files: kept as they came, read into text and pictures for the model.
- `intake.py`: the library's intake: anything (files, folders, codebases, chat exports) read into passages.
- `memory/`: the log, knowledge, the network, the rules, search, recall. Never calls the model.
- `mind/`: where the model works on memory: writing, connecting, thinking, re-checking, searching, dreaming.
- `voice.py`: push-to-talk. faster-whisper writes down what you said; in live mode Kokoro speaks the
  answer sentence by sentence. Started by app.py when the voice packages are installed.
- `index.html`: the page.
- `tools/copy_log.py`: carry the log from one memory file to another (see VERSIONS.md).
- `tools/claude_export.py`, `tools/claude_import.py`: read a Claude export; import it and run the mind over it.
- `tests/test_memory.py`, `test_luminal.py`, `test_import.py`, `test_files.py`, `test_intake.py`, `test_dream.py`:
  offline checks (`python3 tests/test_memory.py`, and so on); `tests/live/test_runner.py` checks the live runner.
- `tests/page/`: the page in a real browser against a fake Luminal (`python3 tests/page/run.py`).
- `tests/bench/`: the benchmark: a month of conversation replayed through the real Avy, questions that need
  memory, a judge. `python3 tests/bench/run.py` (under an hour and well under a dollar; a throwaway memory, never yours).
- `tests/live/`: live scenarios (interference, corrections, files, preferences, whose idea, a plan, an old
  Claude history...) played through the real Avy with a simulated you, graded by a judge:
  `python3 tests/live/run.py --all` (about 20 minutes and 30 cents a scenario, side by side).
- `requirements.txt` / `requirements-voice.txt`: packages. Add new ones here and the run command installs them.
