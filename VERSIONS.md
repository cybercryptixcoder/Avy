# Versions and forks

Avy's memory is an experiment, so its designs are kept side by side: any of them can be picked up again,
or used as the starting point for a different idea. Git branches hold the code. The **log** (every
message, word for word) is the one thing that matters most, and every design can rebuild its knowledge
from it.

## The line so far

| Version | Branch | What memory is | Data file |
|---|---|---|---|
| v1 | `memory-v1` | **The fork point.** The permanent log, plus an index: pages of entries (people, topics, facts, events, decisions, preferences, tasks), each pointing at its exact words, with versions and links (about, builds on, related). Recall by meaning and words, walking links. Context dials, incognito, dictation and live voice. | `data/memory.db` |
| v2 | `memory-v2`, then `main` | Log, knowledge (things, information, ideas; said by you, said by Avy, or inferred) and a living network (connections with kinds, reasons and strength built from supports). A mind that writes, connects, thinks and re-checks. Rule-based recall with search switches, and Avy searching her own memory. Footnotes, chapters, the living graph. | `data/memory-v2.db` |

## Going back to v1

```
git fetch
git checkout memory-v1
python3 app.py
```

v1 reads `data/memory.db`, which v2 never touches, so it opens exactly as you left it. Messages you sent
while on v2 aren't in it; to bring them across, see below.

To return to the newest: `git checkout main`.

## Starting a different memory design from the fork

```
git checkout memory-v1
git checkout -b memory-<name>        # your new line
```

Then build the new design. Two habits keep forks independent:
- **Its own data file** (like v2's `memory-v2.db`), so every design can still be run, and none of them
  damages another's.
- **The log comes first.** Copy it in on first run (`Memory.copy_log_from` in v2 shows how) and
  rebuild knowledge from it, so no conversation is ever lost by switching.

## Carrying the log between designs

Every version so far has the same `messages` table. `python3 tools/copy_log.py <from.db> <to.db>`
appends whatever messages the second file doesn't have yet, in order, with their times. Knowledge isn't
copied; the destination's own mind writes it from the log.

## Branches

- `main`: what you run normally.
- `memory-v1`: frozen at the fork point. Never committed to again.
- `memory-v2`: where v2 was built; merged into `main` when finished.
