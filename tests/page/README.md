# Page tests

The page, driven in a real browser (Chromium through Playwright), against a fake Luminal, so nothing costs
anything and the answers are predictable. Each test gets a fresh copy of Avy with an empty memory in a
work folder; your own `data/` is never touched.

```
python3 -m pip install playwright && python3 -m playwright install chromium     # once
python3 tests/page/run.py                     # all four (about 10 minutes)
python3 tests/page/run.py files               # one
python3 tests/page/run.py --keep files        # and leave that Avy running at http://localhost:8000
```

| Test | What it checks |
|---|---|
| `t_basics.py` | Markdown in replies (and that HTML in them is escaped), the keys panel, the card's menus, phone width |
| `t_ui.py` | the `/` panel (descriptions, a line between rows, narrowing), `/index`, footnotes (hover, click), the inspector's pages, explore's rounds, the graph (corner, full page, hover, click), incognito citing main memory |
| `t_errands.py` | `/window:` and `/recall:` reaching the model, incognito end to end (its own memory, deleted after), dictation (hold, lock, typing a space), live voice (Avy answers out loud; both sides saved as spoken) |
| `t_files.py` | attaching (button, drop, paste), the tray, what reaches the model (`<file>` tags, pictures as images), files with no words, a real recording transcribed, chips after a reload, opening and "read", `[ save ]` on code, `/export` (Markdown, JSON, memory), `/files`, importing a Claude export, phone width |

- `run.py` starts `mock_luminal.py` (port 9999) and Avy (port 8000) for each test, and borrows the speech
  and meaning models from `data/models` (`--models` to point elsewhere) so nothing downloads twice.
- `mock_luminal.py` behaves like the real endpoint where it matters: it refuses a request that isn't
  streamed or lacks `reasoning_effort` or `max_tokens`, refuses a forced tool call while thinking,
  streams thinking when asked, answers the mind's tools deterministically, has a balance, and says how
  many pictures and which files it saw. Every request is logged to `<work>/requests.jsonl`.
- `assets/`: a synthetic spoken question for the fake microphone (`fakemic.wav`) and a short synthetic
  recording to attach (`speech16k.wav`).
- Screenshots land in `<work>/shots`.
- The live-voice check waits for Avy to finish talking; on a machine busy with something else it can run
  out of time.
