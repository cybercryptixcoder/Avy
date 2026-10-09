# Avy

Ava's baby.

A personal agent built from scratch, one small piece at a time, so every line is understood.

## Rules

- **One brain:** DeepSeek. No other model does the thinking.
- **Small steps:** each change is something you can try right away (does it talk, does it remember, does it do things).
- **Keys stay local:** API keys are entered in the app and saved to a local `.env`, which is never committed.

## Running it

Needs Python 3.10 or newer. One-time setup, so HTTPS works on every computer:

```
python3 -m pip install -r requirements.txt
```

Then, every time:

```
python3 app.py
```

Your browser opens http://localhost:8000. Paste your DeepSeek key in the Keys panel once; it's saved to `.env`.

## Voice (optional)

Avy can listen and talk back. Everything except DeepSeek runs on your computer:
Silero VAD and Smart Turn hear when you start and stop, faster-whisper writes down
what you said, Kokoro speaks the reply. Pipecat ties them together and handles
interruptions. Needs Python 3.11–3.13.

```
python3 -m pip install -r requirements-voice.txt
python3 app.py
```

The first start downloads the speech models (about 1 GB). Then click `[ talk ]`.
Use headphones at first: if your speakers leak into the mic, Avy may hear herself.

## What's here

- `app.py`: the server. Serves the page, saves keys to `.env`, streams replies from DeepSeek (`deepseek-flash`, thinking off).
- `index.html`: the page. A terminal-style chat, the keys panel, and a running count of tokens and dollars spent.
- `voice.py`: the voice pipeline. app.py starts it automatically when the voice packages are installed.
- `requirements-voice.txt`: the voice packages.
- `requirements.txt`: one optional package, `truststore`, so Python trusts the same HTTPS certificates your computer does.

The conversation lives in the browser tab for now. Refresh and it's gone.
