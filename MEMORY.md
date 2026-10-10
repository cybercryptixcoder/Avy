# How Avy remembers (version 2): the technical spec

[CONCEPT.md](CONCEPT.md) explains the idea and why. This is how it's built, for whoever reads or changes
the code. Version 1 (a log plus an index of entries) is preserved on the `memory-v1` branch; see
[VERSIONS.md](VERSIONS.md).

## The parts

```
memory/                   stores and searches; never calls the model
  schema.sql              every table, readable on its own
  store.py                the file: one SQLite database, one connection, one lock
  log.py                  messages (permanent) and episodes (stretches of the log)
  knowledge.py            nodes, versions, evidence, basis
  network.py              edges, supports, strength, links, implicit neighbors
  rules.py                what every change must pass
  ops.py                  the one door: apply() checks against the rules, writes, journals
  search.py               meaning (local model) + words (SQLite FTS5)
  recall.py               what each message brings back, by rules; the memory note
  health.py               the network's shape in numbers
  inspect.py              what the inspector and the graph read
  embed.py                the meaning-search model (bge-small, 384 numbers per text, on the CPU)
mind/                     where DeepSeek comes in; only ever proposes
  llm.py                  one strict tool call; cost; one retry when a connection drops
  jobs.py                 the engine: prompt, call, check, repair (up to 2), apply, record
  writer.py               Write: an episode of the log becomes knowledge
  reflect.py              Connect, Think, Check, and how their inputs are chosen
  explore.py              Avy steering her own memory search
  worker.py               when everything runs; the daily budget; live events for the page
app.py                    the server; the Turn (one exchange); settings; endpoints
```

`Memory` (in `memory/__init__.py`) is one class assembled from the parts above. One memory is one
file:
- The main memory is `data/memory-v2.db`.
- An incognito conversation gets its own in `data/incognito/`, with nodes lettered `x` instead of `k`.

On first run, v2 copies the log (only the log) from version 1's `data/memory.db`, and never changes
that file. The knowledge is then rebuilt from the log by the writer, in the background.

## Storage

| Table | What it holds | Changes? |
|---|---|---|
| `messages` | `#41`: id, time, role, text, typed or spoken, meta | never (database triggers refuse) |
| `episodes` | `ep4`: first and last message, headline, the run that wrote it | added in order, never changed |
| `nodes` | one row per **version**; `chain` is the node (`k12` = chain 12). shape, label, title, text, about (date), origin, certainty, depth, state (active / retracted), why, episode, run | new versions only; `replaces` is UNIQUE, so a chain never forks |
| `evidence` | node version → message, character span, quote (copied by code), exact | written with the node |
| `basis` | inferred node version → the chains it rests on, and the version of each it last saw | `seen` updated when re-checked |
| `edges` | `c7`: a, b (chains), kind, reason, the versions of each end it last saw | kind and reason can be revised (journaled); one edge per pair |
| `supports` | edge, sign (±1), kind, source, note, time | never (triggers refuse) |
| `judged` | pairs Connect has asked about, and the versions it saw | so pairs aren't asked twice |
| `runs` | every model job: prompt, replies, problems, tokens, cost | written once |
| `journal` | every proposed change: op, target, arguments, applied or refused, why | written once |
| `recalls` | for each message: the trace and the exact memory note | written once |
| `health` | the network's numbers after each reflection | written once |
| `marks` | small state: what reflection last looked at | updated |
| `words`, `vectors` | search: FTS5 rows and 384-number vectors for messages (`m41`), node versions (`v77`), episode headlines (`e4`), edge reasons (`c7`) | rows added (an edge's reason row is replaced when revised) |

Views:
- `heads` is the newest version of each node.
- `current` is the heads that aren't retracted: what memory holds now.

## The rules (`memory/rules.py`)

Every proposal is checked when it's applied, whoever made it. A refusal comes with a reason in plain
words, and the same words go back to DeepSeek when one of its proposals breaks a rule.

1. **The log is permanent.**
2. **Said knowledge has evidence**: real messages, spans inside them. **Origin** is decided by the
   evidence: `user` if any of it is Shreyas's words, otherwise `avy`.
3. **Inferred knowledge has a basis**:
   - current nodes, resting on things Shreyas said in **at least two different conversations**
   - "likely" needs at least two basis nodes
   - depth (steps from said words) at most 3
4. **An inference can't replace what was said.** Only new evidence (his words) can.
5. **A new version keeps the sort of thing**: a thing stays a thing.
6. **Shreyas is never a node.**
7. **One node per thing**: no two current nodes of the same shape with the same title.
8. **Edges**:
   - two different current nodes
   - one of five kinds
   - a reason of at least three words
   - a `stated` support needs a quote from one of his messages
9. **Retracting something said needs his words.** A retraction needs a reason.
10. **Episodes follow each other** with no gaps or overlaps.

## The one door (`memory/ops.py`)

`mem.apply(op)` and `mem.apply_all(ops, run)`. Operations:

| op | does |
|---|---|
| `add_node` | a new node or a new version (evidence or basis, never both) |
| `retract_node` | a new version with state `retracted` and a reason |
| `connect` | creates the edge, or adds a support to the existing one (a stated or confirmed support may also set its kind and reason) |
| `oppose` | a negative support |
| `revise_edge` | a new kind or reason (the old one is kept in the journal) |
| `reaffirm` | re-checked and still holds: records the versions it was checked against |
| `add_episode` | the next stretch of the log, with its headline |

Inside a batch, ops can refer to nodes made earlier in it by ref (`n1`), and to the episode as
`@episode`.

## Strength (`memory/network.py`)

```
strength = sum over supports of  sign × weight × fade
  weight:  stated 3, confirmed 3, inferred 1, observed 0.5, used 0.5
  fade:    1 for stated and confirmed, and for every support on part_of, builds_on and against edges;
           for 'like' and 'related' edges, the other supports halve every 90 days
  the model's negative supports are ignored when Shreyas stated or confirmed the edge
live (followed) when strength ≥ 0.5; each node follows at most its 12 strongest
```

Because supports are append-only and timestamped, `strength(edge, as_of)` gives the network as it stood
at any moment.

Implicit neighbors are never stored:
- an inference and what it rests on
- nodes written from the same message
- nodes from the same episode

## The mind's jobs (`mind/`)

Every job goes through `jobs.run(mem, job)`:
1. `job.prompt()`
2. one forced tool call (thinking off, as DeepSeek requires for forced calls)
3. `job.check(answer)` returns proposals, problems and notes
4. problems go back in plain words, up to twice; the attempt with the fewest problems wins
5. `mem.apply_all`
6. the run is recorded

| Job | When | Shown | Answers (contract) | Code then |
|---|---|---|---|---|
| **Write** | a sitting ends (30 quiet minutes) or ~20 messages are waiting (fewer when `/window:` is small) | up to 50 nodes from the whole memory (hubs, newest, and what each message brings up in search), 4 messages of context, the stretch | `write_episode {headline, nodes[{ref, replaces, shape, label, title, text, when, evidence[{message, quote}]}], edges[{from, to, kind, reason, said}]}` | locates every quote; turns same-title duplicates into versions; reuses an existing thing instead of copying it; downgrades a `said` that isn't his words; caps edges; strengthens edges between things that came up together again (`observed`) |
| **Connect** | after every Write and Think | pairs: each new node with partners from anywhere in memory that are **at least 3 steps away** (close in meaning or words, sharing neighbors, or whose edges have similar reasons) | `judge_connections {verdicts[{pair, connect, kind, from, reason}]}` | at most 3 new edges per node per run; records the pairs judged |
| **Think** | quiet times (30 minutes without a message), within the daily budget | a focus: the newest unthought episode plus the older nodes closest to each of its nodes, or a said hub that gained 3+ connections, or a quiet corner and its distant relatives; plus the existing inferences closest to it all | `write_inferences {inferences[{ref, replaces, shape, label, title, text, certainty, basis[]}], edges[]}` | the rules above; at most 2; no near-repeats of an existing inference (meaning ≥ 0.84) or thing; no "He…" traits; a new thing needs 2+ parts |
| **Check** | quiet times, before Think | inferences whose basis has newer versions or was retracted; non-part_of edges whose ends have new versions (16 at a time) | `recheck {verdicts[{item, verdict: holds/revise/retract, title, text, certainty, kind, reason, why}]}` | reaffirm, new version, retract, or a negative support |

The budget: reflection makes at most 60 model calls a day (`worker.REFLECT_CALLS`), plus up to 3 Think
runs per quiet spell. `/index` writes now; `/reflect` reflects now.

## Recall by rules (`memory/recall.py`)

For each message, at the `/recall:` depth (off, light, normal, deep, max):

1. **Land.** Search every node version and every episode headline with the message (and, when it
   refers back, with the previous one too).
   - score = meaning + 0.15 × the share of its words found (rare words count more); without meaning
     search, the word share alone
   - a hit on an old version counts for the node
   - a slight nudge for recent things
   - seeds are what clear `max(found, best − near)`, with echoes (an earlier copy of the same question)
     not setting the bar
2. **Walk.** From the seeds, along live edges and implicit neighbors, for `hops` steps:
   ```
   step = STEP[kind, direction] × (0.6 + 0.4 × min(1, strength / 3)) × hub_discount(degree) × closeness to the message
   hub_discount = 1 up to 2 connections, log2(4) / log2(2 + degree) beyond (about 0.5 at 12)
   ```
   STEP: part_of 0.75 out / 0.6 in, builds_on 0.8 / 0.6, like 0.7, against 0.7, related 0.5, rests on
   0.7, supports 0.75, same message 0.35, same episode 0.25.
3. **Keep** what scores at least `keep × best`, within the token budget.
4. **Safety net**: older messages that match by themselves (not on screen, not next to a message a kept
   node cites).
5. **The note**, in tiers:
   - what Shreyas told you (quotes, the full message for the top three)
   - what you said before
   - what you worked out yourself (with certainty and what it rests on)
   - how these connect (edge reasons)
   - older messages

   A node that changed hands says who said it first. Versions show their earlier texts.

`/words:` and `/meaning:` switch the halves of search. With both off, nothing is looked up and the
always-on hub list is left out too.

## Avy searching herself (`mind/explore.py`, `/explore: on`)

Rounds as set by `/recall:` (light 1, normal 2, deep 3, max 4):
- **Round 0 (code).** Ordinary recall plus a plain search give the landing frontier: up to 14
  previews, each with its first four connections (kind, reason).
- **Each round**, DeepSeek answers `explore_memory {task, questions[], open[], follow[], search[], keep[{item, why}], done}`:
  - `open` reads up to 5 nodes in full: the exact words and every connection
  - `follow` adds up to 4 nodes' neighbors to the frontier
  - `search` runs up to 3 new searches in its own words (nodes, plus raw log lines it can keep as `#41`)
  - `keep` is its current answer
- **The last round** only decides what to keep.

What's kept becomes the note (same tiers), followed by the task it took the message to need. Edges
followed to something kept get a `used` support (only in the memory being talked to, never from
incognito into the main memory, never in benchmark probes). If DeepSeek can't be reached, it falls back
to recall by rules.

## The Turn (`app.py`)

```
window   = the newest /window: messages, word for word
memory   = explore() if /explore: on, else recall()   (+ the main memory, read-only, in incognito)
messages = [system: instructions + footnote rule + the core (the biggest said hubs)]
         + window + [system: the memory note] + [user: the message]
stream the reply; save both messages; save the recall; nudge the mind
```

The reply cites memory as `[k12]` right after what it supports. The page turns those into footnotes,
and voice strips them before speaking.

## Settings

model, window, recall, explore and live are on the system card. Everything else is also a `/`
command: words, meaning, footnotes, thinking, voice, speed, whisper.

## Testing

- `python3 tests/test_memory.py [--meaning <model folder>]`: every rule, every job with a scripted
  DeepSeek (repair loops, failures, give-ups), recall in all modes, explore, incognito, carrying the v1
  log, the inspector's views. Offline, in seconds.
- `python3 tests/bench/run.py`: the benchmark (see CONCEPT.md, and `tests/bench/RESULTS.md`). Real
  DeepSeek, about an hour and well under a dollar. `tests/bench/check_words.py` proves its questions
  share no searchable words with what they need.
