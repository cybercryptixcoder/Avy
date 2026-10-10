# Avy

A personal agent built from scratch, one small piece at a time, so every line is understood. Her heart is
a memory that never forgets and never summarizes anything away: one endless conversation, turned into a
living network of knowledge that she thinks about when it's quiet.

- **[CONCEPT.md](CONCEPT.md)**: what Avy is and why, in plain words. Start here.
- **[MEMORY.md](MEMORY.md)**: how memory is built: storage, rules, the mind's jobs, the algorithms.
- **[VERSIONS.md](VERSIONS.md)**: the versions kept side by side, and how to go back or fork.
- **[LATER.md](LATER.md)**: what's decided but not built yet.
- **[tests/bench/RESULTS.md](tests/bench/RESULTS.md)**: how well it works, measured.

## Rules

- **One brain:** DeepSeek. No other model does the thinking.
- **Small steps:** each change is something you can try right away.
- **Keys stay local:** API keys are entered in the app and saved to a local `.env`, which is never committed.

## Running it

From this folder, every time (it pulls updates and installs anything new; already-installed packages are skipped):

```
git pull && python3 -m pip install -q -r requirements-voice.txt && python3 app.py
```

Your browser opens http://localhost:8000. Paste your DeepSeek key in the Keys panel once; it's saved to `.env`.
Needs Python 3.10–3.13 (Kokoro doesn't support 3.14 yet).

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
- **Incognito:** `/incognito` starts a separate conversation. Avy can still use her memory, but nothing
  said there is kept: it has its own temporary memory, deleted when you end it.
- **Memory's own work:** it writes each sitting into knowledge when the sitting ends, and reflects when
  it's quiet (finding connections, patterns, and things that changed), within a small daily budget.
  `/index` writes now; `/reflect` reflects now. The system card's "mind" line shows what it's doing.
- **Under the hood:** `/memory` opens the inspector:
  - every node like a wiki page: where it was said, what it rests on, its connections, its versions
  - every connection with why it exists and how strong it is
  - every conversation, and every run of the mind with exactly what DeepSeek was shown and answered
  - the journal of every change, and the network's health

  `↳ recalled 3 nodes` under a reply shows what memory brought for it, and how.
- **The graph:** the little network in the corner is Avy's memory. Click it (or `/graph`) to open it
  full page: drag to turn it, scroll to zoom, hover or click a node.
- **Commands:** type `/` and the panel opens on the right, each command with a few words saying what it
  does. Keep typing to narrow it, Tab to complete, ↑↓ to pick, Enter to run.
- **System card** (left): the main settings as dropdowns, and memory's numbers.

## Where things live

Everything stays in this folder:

- `.env`: your keys.
- `data/memory-v2.db`: everything ever said, and the knowledge and network built from it.
- `data/memory.db`: version 1's memory, if you used it (left as it was).
- `data/settings.json`: your choices from the system card or `/` commands.
- `data/models/`: the speech models (about 0.7 GB) and the meaning-search model (about 65 MB), downloaded on the first run.
- `data/recordings/`: a backup of everything you say, written as you talk, with its transcript next to it.
  The newest 50 (up to 300 MB) are kept; older ones are deleted. `/retry` re-transcribes the newest one.
- `data/incognito/`: an incognito conversation's memory and recordings, only while it's going.

`data/` and `.env` are never committed.

## What's here

- `app.py`: the server: the page, keys, settings, and every exchange with DeepSeek (typed or spoken).
- `memory/`: the log, knowledge, the network, the rules, search, recall. Never calls the model.
- `mind/`: where DeepSeek works on memory: writing, connecting, thinking, re-checking, and searching.
- `voice.py`: push-to-talk. faster-whisper writes down what you said; in live mode Kokoro speaks the
  answer sentence by sentence. Started by app.py when the voice packages are installed.
- `index.html`: the page.
- `tools/copy_log.py`: carry the log from one memory file to another (see VERSIONS.md).
- `tests/test_memory.py`: memory checks that run offline (`python3 tests/test_memory.py`).
- `tests/bench/`: the benchmark: a month of conversation replayed through the real Avy, questions that need
  memory, a judge. `python3 tests/bench/run.py` (about half an hour and 40 cents; a throwaway memory, never yours).
- `requirements.txt` / `requirements-voice.txt`: packages. Add new ones here and the run command installs them.
