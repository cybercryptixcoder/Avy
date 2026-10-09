# Avy

A personal agent built from scratch, one small piece at a time, so every line is understood.

## Rules

- **One brain:** DeepSeek. No other model does the thinking.
- **Small steps:** each change is something you can try right away (does it talk, does it remember, does it do things).
- **Keys stay local:** API keys are entered in the app and saved to a local `.env`, which is never committed.

## Running it

From this folder, every time (it pulls updates and installs anything new; already-installed packages are skipped):

```
git pull && python3 -m pip install -q -r requirements-voice.txt && python3 app.py
```

Your browser opens http://localhost:8000. Paste your DeepSeek key in the Keys panel once; it's saved to `.env`.
Needs Python 3.10–3.13 (Kokoro doesn't support 3.14 yet).

## Using it

- **Type** at the prompt, Enter to send.
- **Dictate:** hold Space and talk; let go and your words appear in the text box, to edit and send yourself.
  Tap Space twice (on an empty box) to lock it on for long stretches; press Space again to finish, or Esc to
  throw it away. With text already in the box, a tap still types a space and a hold dictates more.
- **Live conversation:** `/live: on`. Then Space talks to Avy and she answers out loud; tap Space while she
  talks to cut her off. Only what you heard is saved.
- **One endless conversation.** There's no new chat: every message gets its own memory, fetched fresh.
  Reloading brings the conversation back; `[ load earlier ]` goes further back.
- **How much context Avy gets**, two dials:
  - `/window:` how many recent messages she reads word for word: 0, 5, 10, 20 (default), 40, 80, or all.
    At 0 everything comes from memory; at all it's an ordinary chat.
  - `/recall:` how far memory search reaches: off, light, normal (default), deep, max.
- **Incognito:** `/incognito` starts a separate conversation. Avy can still use her memory, but nothing
  said there is kept: it has its own temporary memory, deleted when you end it (`/incognito` again, or
  `[ end incognito ]`), or when app.py stops.
- **Under the hood:** a dim `↳ recalled 3 entries` under a reply shows what memory brought for it. Click it to
  see each entry, how it was reached, and the exact note DeepSeek got. Click any entry to read it like a wiki
  page (where it was said, its links, what links to it, earlier versions); click any `#41` to see that exact
  spot in the log with the words highlighted. `[ back ]` retraces your steps.
- **Commands:** type `/` and a panel opens on the right. Keep typing to narrow it, Tab to complete, ↑↓ to pick,
  Enter to run. `/memory` (or `/memory: words` to search it), `/index`, `/incognito`, `/window:`, `/recall:`,
  `/live:`, `/model:`, `/thinking:`, `/voice:`, `/speed:`, `/whisper:`, `/clear` (the screen only; memory keeps
  everything), `/keys`, `/where`, `/retry`, `/help`.
- **System card** (left): the same settings, as dropdowns, plus memory numbers.

## How memory works

Two layers, described properly in [MEMORY.md](MEMORY.md):

- **The log:** every message, word for word, numbered. Never edited or deleted.
- **The index:** pages (one per ~20 messages) of entries: people, facts, plans, decisions. Every entry points
  at the exact words it came from, and links to the entries it's about or builds on, so it grows into a
  network. A correction is a new version that replaces the old one; the history stays walkable.

DeepSeek writes the index in the background and code checks every pointer before anything is saved.
On each message, Avy searches the index and the log, follows links outward, and takes what's relevant.

## Where things live

Everything stays in this folder:

- `.env`: your keys.
- `data/memory.db`: everything ever said, and the index into it.
- `data/settings.json`: your choices from the system card or `/` commands.
- `data/models/`: the speech models (about 0.7 GB) and the meaning-search model (about 65 MB), downloaded on the first run.
- `data/recordings/`: a backup of everything you say, written as you talk, with its transcript next to it.
  The newest 50 (up to 300 MB) are kept; older ones are deleted. `/retry` re-transcribes the newest one.
- `data/incognito/`: an incognito conversation's memory and recordings, only while it's going.

`data/` and `.env` are never committed.

## What's here

- `app.py`: the server. The page, keys, settings, and every exchange with DeepSeek (typed or spoken).
- `memory.py`: the log, the index, search, and what each message brings back.
- `indexer.py`: writes the index with DeepSeek, and checks everything it writes.
- `voice.py`: push-to-talk. faster-whisper writes down what you said; in live mode Kokoro speaks the
  answer sentence by sentence. Started by app.py when the voice packages are installed.
- `index.html`: the page.
- `tests/test_memory.py`: memory checks that run offline (`python3 tests/test_memory.py`).
- `tests/live_memory.py`: a week of conversation replayed against the real DeepSeek, then questions
  about it (`python3 tests/live_memory.py`; a few cents; uses a throwaway memory, never yours).
- `requirements.txt` / `requirements-voice.txt`: packages. Add new ones here and the run command installs them.
