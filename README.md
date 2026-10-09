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
Voice needs Python 3.10–3.13. Text chat works even if the voice packages aren't installed.

## Using it

- **Type** at the prompt, Enter to send.
- **Talk:** hold Space (with the prompt empty) and let go to send. Tap Space twice to lock it on for long
  stretches; press Space again to send, or Esc to throw it away. Tap Space while Avy talks to cut her off.
- **Commands:** type `/` and a panel opens on the right. Keep typing to narrow it, Tab to complete, ↑↓ to pick,
  Enter to run. `/model:`, `/thinking:`, `/voice:`, `/speed:`, `/whisper:`, `/speak:`, `/clear`, `/keys`,
  `/where`, `/retry`, `/help`.
- **System card** (left): the same settings, as dropdowns.

## Where things live

Everything stays in this folder:

- `.env`: your keys.
- `data/settings.json`: your choices from the system card or `/` commands.
- `data/models/`: the speech models (about 0.7 GB, downloaded on the first run).
- `data/recordings/`: a backup of everything you say, written as you talk, with its transcript next to it.
  The newest 50 (up to 300 MB) are kept; older ones are deleted. `/retry` re-transcribes the newest one.

`data/` and `.env` are never committed. The conversation itself lives in the browser tab for now.

## What's here

- `app.py`: the server. The page, keys, settings, and DeepSeek requests (text and voice both go through it).
- `voice.py`: push-to-talk. faster-whisper writes down what you said, DeepSeek answers, Kokoro speaks it
  sentence by sentence. Started by app.py when the voice packages are installed.
- `index.html`: the page.
- `requirements.txt` / `requirements-voice.txt`: packages. Add new ones here and the run command installs them.
