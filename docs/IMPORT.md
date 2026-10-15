# Importing your Claude history

Your Claude conversations, years of them, become Avy's log, and her mind turns them into knowledge
and a network the same way it does with her own conversations. It's the real-scale test of memory v2:
ideas are how you live, and you know exactly what yours are, so if they show up as distinct hubs with
sensible bridges between them, the network works.

Two steps, deliberately separate:
1. **Import**: copy the conversations into a memory file. No model calls, nothing leaves your computer.
2. **The mind's run**: write it all into knowledge. Thousands of model calls and real money, so only you
   start it, and you can stop and resume it.

## In short

```
python3 tools/claude_import.py inspect ~/Downloads/data-export.zip     # what's in it (counts only)
python3 tools/claude_import.py import  ~/Downloads/data-export.zip     # into data/memory-claude.db
python3 tools/claude_import.py plan                                     # how big the run is, roughly what it costs
python3 tools/claude_import.py run --max-stretches 20                   # a small trial
python3 tools/claude_import.py run --max-dollars 20                     # the real thing (Ctrl+C stops; run again to resume)
python3 tools/claude_import.py status                                   # how far it's got
python3 app.py --memory data/memory-claude.db                           # talk to Avy with that history
```

Or in the page: attach the export (the zip or the JSON) with `[ attach ]`, and press `[ import ]` on it.
That does step 1. Step 2 can be started from the page too: the looking glass (`/glass`) has a "your claude
history" panel with [ plan ] (the table below), [ build ] (with how hard the mind thinks, a dollar budget
and an optional trial number of stretches) and [ stop ], and shows the build's progress, cost and time left.
It runs `tools/claude_import.py run` as its own process (it sets memory's clock to each conversation's time,
which must never touch the conversation you're having).

Attaching the export also puts it in the main memory's **library** (docs/FILES.md): every message becomes a
passage, searchable at once, without writing any knowledge. So questions about your old conversations get
their words back right away; the build above is what turns them into knowledge, hubs and a network.

## What the export looks like

Worked out by code alone: the file was never read by eye, and the probes printed only counts, types and
key names, never text. (Your export: 34 MB zipped, 166 MB of JSON.)

The reader accepts:
- the zip claude.ai emails you (`conversations.json`, `users.json`, `projects.json`, `memories.json`)
- a combined JSON of an export: one object whose keys are the export's file names (`"conversations.json":
  [...]`, `"users.json"`, and `<uuid>.json` entries for projects, project chats and memories)
- either of those zipped, or a bare `conversations.json`

What's in yours:

| Part | Count | What happens to it |
|---|---|---|
| claude.ai conversations (`conversations.json`) | 524, with 8,287 messages | imported (see below) |
| project chats (`<uuid>.json` with `title: "Chat"`) | 13 | imported, with their project's name |
| projects (instructions and documents) | 8 | skipped, counted |
| Claude's own memories | 1 file | skipped: memory is rebuilt from scratch |
| account records (`users.json`, `login_history.json`) | | skipped |

A claude.ai message has `sender` (human or assistant), `created_at`, `parent_message_uuid` (so edits and
regenerations form branches), `content` blocks, `attachments` (files whose text Claude was given) and
`files` (uploads). Content blocks are `text`, `thinking`, `tool_use`, `tool_result` (web pages and other
tool output), `voice_note`, `image`, `token_budget` and `injected_prompt_block`.

## What's kept and what's left out

Kept: what was **said**.
- your words: the text you typed
- Claude's words: its replies (text and voice notes)
- for a conversation that branched (you edited a message or regenerated a reply), only the branch it
  ended on: the path from its newest message back to the start
- the names (and sizes) of attached files, never their contents

Left out:
- Claude's thinking, its tool calls and what tools returned (web pages): about 63 million characters
- attached file contents (5.4 million characters)
- empty messages and the branches a conversation didn't end on
- projects, project documents, Claude's memories, account records

Your import: **503 conversations with messages, 6,561 messages** (3,300 yours, 2.6 million characters;
3,261 Claude's, 8.2 million), from June 26, 2024 to October 10, 2026. 1,635 messages on abandoned
branches and 126 empty ones were left out.

## How it goes into memory

- **Its own memory file**, `data/memory-claude.db`. Your history is older than anything Avy has heard,
  and the log has to stay in time order, so it doesn't go into `data/memory-v2.db`. To bring Avy's own
  conversations after it: `python3 tools/copy_log.py data/memory-v2.db data/memory-claude.db` (it
  appends only what's missing, in order). Open it with `python3 app.py --memory data/memory-claude.db`
  (or `AVY_MEMORY=data/memory-claude.db`).
- **Oldest conversation first, each in one piece.** Every message keeps its time (converted to your local
  time) and says which conversation it came from, its name, its project, and its Claude message id.
- **Claude is Claude, never Avy.** Imported messages are marked (`via = "claude"`). Claude's replies are
  shown as "Claude", their knowledge as "Claude said" (its own tier in Avy's memory note: *"What Claude,
  the assistant he talked to before you existed, said to him"*), and the writer is told each stretch is
  an earlier conversation with Claude, so every rule about Avy's words applies to Claude's (its
  suggestions get their own nodes, its questions and general explanations aren't memory about you, its
  guesses never go into nodes about what you said).
- **A stretch never runs across two conversations**, and the writer never sees context from another one.
- **Running import again** with a newer export adds only what's new (by Claude's message ids).
- **Search by meaning** is computed during import (locally; it took about an hour for 6,561 messages on a
  small cloud machine, much less on a laptop). If the model isn't there yet, the vectors are filled in
  later.

## The mind's run

- **Nothing writes the import by itself.** Avy's background mind skips imported messages, and `/index`
  and `/reflect` refuse while any are waiting. Only `run` writes them.
- **In time order, with the clock set to each stretch's own time**, so knowledge is dated like the
  conversation. After each day of conversation it reflects once (Connect, Think, Check), the way Avy
  would at night.
- **Stop any time** (Ctrl+C); the same command carries on. `--max-dollars`, `--max-stretches`,
  `--until YYYY-MM-DD` and `--no-reflect` limit it. `--effort` sets how hard the mind thinks (default
  none; see LUMINAL.md).
- **Through Luminal**, one call at a time.

`plan` on your import, from the benchmark's per-call averages (Luminal publishes no per-token price, so
dollars use DeepSeek's own list price as a guide; the Luminal balance is the truth):

| thinking | stretches | days | calls | tokens in | tokens out | dollars | hours |
|---|---|---|---|---|---|---|---|
| none | 1,131 | 332 | 7,569 | 32.4 M | 4.6 M | ~11 | ~13 |
| low | 1,131 | 332 | 7,569 | 32.4 M | 7.6 M | ~15 | ~25 |
| medium | 1,131 | 332 | 7,569 | 32.4 M | 11.4 M | ~20 | ~32 |
| high | 1,131 | 332 | 7,569 | 32.4 M | 15.9 M | ~25 | ~38 |

Suggested: a trial of 20 stretches first (`--max-stretches 20`), look at what it wrote in the inspector,
then the whole run with a budget.

## Judging it

- `/memory` in the page (on the claude memory): the biggest hubs. Are they your real interests, projects
  and ideas?
- `/graph`: clusters, and the bridges between distant areas.
- The ideas that formed (Think's inferences), and whether they're yours.
- The health numbers at scale (islands, clustering, path length).

## Privacy

- The export and the imported memory live only in `data/`, which is never committed.
- Imported conversations go to the model only during `run` (and when Avy recalls them), through Luminal.
- While building this, the export was probed only by code that printed counts and shapes. One probe
  briefly printed a short fragment of a message (MISTAKES.md, #32); it was fixed at once.

## Files

- `tools/claude_export.py`: the reader. Streams the JSON with ijson (falls back to loading it whole).
- `tools/claude_import.py`: inspect, import, plan, run, status.
- `tests/test_import.py`: a made-up export in every shape, checked end to end without a model.
