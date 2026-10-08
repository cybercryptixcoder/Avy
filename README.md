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

## What's here

- `app.py`: the server. Serves the page, saves keys to `.env`, streams replies from DeepSeek (`deepseek-flash`, thinking off).
- `index.html`: the page. A terminal-style chat, the keys panel, and a running count of tokens and dollars spent.
- `requirements.txt`: one optional package, `truststore`, so Python trusts the same HTTPS certificates your computer does.

The conversation lives in the browser tab for now. Refresh and it's gone.
