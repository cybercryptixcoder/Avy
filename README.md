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
- **Talk:** hold Space (with the prompt empty) and let go to send. Tap Space twice to lock it on for long
  stretches; press Space again to send, or Esc to throw it away. Tap Space while Avy talks to cut her off.
- **One endless conversation.** There's no new chat: every message gets its own memory, fetched fresh.
  Reloading brings the conversation back; `[ load earlier ]` goes further back.
- **Under the hood:** a dim `↳ recalled 3 entries` under a reply shows what memory brought for it. Click it to
  see each entry, how it was reached, and the exact note DeepSeek got. Click any entry to read it like a wiki
  page (where it was said, its links, what links to it, earlier versions); click any `#41` to see that exact
  spot in the log with the words highlighted. `[ back ]` retraces your steps.
- **Commands:** type `/` and a panel opens on the right. Keep typing to narrow it, Tab to complete, ↑↓ to pick,
  Enter to run. `/memory` (or `/memory: words` to search it), `/index`, `/model:`, `/thinking:`, `/voice:`,
  `/speed:`, `/whisper:`, `/speak:`, `/clear` (the screen only; memory keeps everything), `/keys`, `/where`,
  `/retry`, `/help`.
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

`data/` and `.env` are never committed.

## What's here

- `app.py`: the server. The page, keys, settings, and every exchange with DeepSeek (typed or spoken).
- `memory.py`: the log, the index, search, and what each message brings back.
- `indexer.py`: writes the index with DeepSeek, and checks everything it writes.
- `voice.py`: push-to-talk. faster-whisper writes down what you said, Kokoro speaks the answer
  sentence by sentence. Started by app.py when the voice packages are installed.
- `index.html`: the page.
- `tests/test_memory.py`: memory checks that run offline (`python3 tests/test_memory.py`).
- `tests/live_memory.py`: a week of conversation replayed against the real DeepSeek, then questions
  about it (`python3 tests/live_memory.py`; a few cents; uses a throwaway memory, never yours).
- `requirements.txt` / `requirements-voice.txt`: packages. Add new ones here and the run command installs them.
