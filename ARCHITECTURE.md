# Avy: the architecture

How Avy works, and how the parts that aren't built yet are meant to work. Not the stack and not pseudocode:
the structures (what kind of graph, what each store holds and promises), the moves (how a turn is answered,
how memory is written, reflected on, searched, dreamt about), and the numbers that tune them. What we're
building and why is [VISION.md](VISION.md); the exact rules and contracts of what's built are
[MEMORY.md](MEMORY.md) and [docs/HANDOFF.md](docs/HANDOFF.md). Each section says **built** or **planned**.

---

## 0. The shape of the whole

```
                      ┌──────────────────────── one turn (app.Turn) ────────────────────────┐
  his message ──────► │ slots (fixed size, always shown)     stores (grow; searched, not shown) │
                      │   system prompt + core hubs        ◄── knowledge graph (hubs)           │
                      │   [planned] preferences, character ◄── self model                       │
                      │   [planned] working frontier       ◄── thought graph                    │
                      │   memory note                      ◄── recall / explore over:           │
                      │                                         knowledge graph, library, log    │
                      │   recent messages (window)         ◄── the log                          │
                      │   the message (+ its files)                                             │
                      └───────────────┬─────────────────────────────────────────────────────────┘
                                      ▼
                           DeepSeek-V4.1-Flash via Luminal (thinking: none/low/high/max)
                                      │  streams reasoning, then the answer
                                      ▼
                 the log (his message, her reply)   +   reasoning (what she thought)
                                      │
             the mind, in the background (mind/worker.py, one job at a time):
               Write ─► Connect        when a sitting ends or a page of messages waits
               Check ─► Think ─► Connect   when it's quiet (daily budget)
               Dream                   when he starts it (hours, max thinking, its own budget)
             intake (intake.py), in the background: anything added ─► library passages ─► vectors
```

Everything is one SQLite file per memory (`memory/schema.sql`): the main memory, an incognito one while it
lasts, the imported Claude history's own. The model never writes to it directly: it **proposes**, and every
change goes through **the one door** (`Memory.apply`), which checks it against the rules and journals it,
applied or refused.

---

## 1. The stores

Every store is either **permanent** (append-only, enforced by database triggers) or **versioned** (changes
are new rows; old ones stay). Nothing is deleted. Handles are short and used everywhere (database,
inspector, what the model sees): `#41` message, `k12` node, `c7` connection, `ep4` episode, `p41` passage,
`s3` source.

| Store | Holds | Shape | Changes | Built |
|---|---|---|---|---|
| **log** (`messages`) | every message, both sides, word for word, with time, typed or spoken, and meta (files, usage, cut off) | a sequence | never | built |
| **reasoning** | what she thought before each reply (the model's reasoning), its effort, how long, tokens | a sequence, each row pointing at the reply and the message it answered | never | built (Oct 15) |
| **library** (`sources`, `passages`) | everything added from outside the conversation, as passages in order, each labeled with where it is (page, heading path, `file:lines`, `conversation · message 12`), and for conversations who said it and when | sources, each a sequence of passages | passages never; a source's status/meta as intake progresses | built (Oct 15) |
| **episodes** | stretches of the log (a sitting), each with a headline | contiguous, non-overlapping ranges | added in order | built |
| **knowledge** (`nodes`, `evidence`, `basis`) | one thing or one claim per node: shape, label, title, text, the date it's about, origin, certainty, depth | **version chains**: each node (`chain`) is a list of versions, `replaces` is UNIQUE so a chain never forks | new versions only | built |
| **the network** (`edges`, `supports`) | connections between nodes: kind, reason, and every support anyone gave it | a graph (below) whose edge weights are computed from an append-only support log | kind/reason revisable (journaled); supports never | built |
| **search** (`words`, `vectors`) | FTS5 rows and 384-number meaning vectors for messages, node versions, episode headlines, connection reasons, passages | inverted index + flat vector shelves in memory | rows added | built |
| **what happened** (`runs`, `journal`, `recalls`, `health`, `marks`) | every model job (prompt, replies, problems, cost), every proposed change, what each recall brought, the network's shape over time, small cursors | logs | written once (marks: updated) | built |
| **thought graph** | her reasoning, as linked thought nodes | a DAG per session (§7) | new nodes and versions | planned |
| **slots** (preferences, character) | fixed-size notes always in view | single versioned documents with a hard budget | overwritten as a new version | planned |
| **self model** | situational behaviors | a small graph keyed by kinds of conversation | versioned, like knowledge | planned |

---

## 2. The knowledge graph: what kind of graph it is

A **typed, versioned property graph** with **evidence-backed nodes** and **support-weighted edges**.

**Nodes** have one structural type, the *shape*:
- **thing**: an identity other knowledge gathers around (a person, a project, a course). Its text only
  says what it is; how it's going is information connected to it. Hubs are things many nodes belong to.
- **information**: one claim (fact, event, plan, decision, preference, problem, result).
- **idea**: a concept, principle, proposal, hypothesis, analogy, open question. First-class: a conversation
  about an idea leaves the idea, not a note that it was discussed.

A free *label* is for reading only. The *origin* is decided by code from the evidence: **user** (his words),
**avy** (her words in conversation; "Claude said" for imported conversations, same tier), **inferred**
(worked out by reflection, with *certainty* likely/possible, resting on a *basis* of other nodes, at most
3 steps (*depth*) from said words). Only his words can change what he said; when he confirms an inference
it becomes his in a new version, and the history shows who said it first.

**Evidence** points each said node at exact character spans of exact messages, quotes copied by code
(the model's quote is located in the message; if it can't be found it's sent back). This is what makes
"no drift" true: any node can be traced to the words.

**Edges** connect node *chains* (so an edge survives new versions of its ends). Five kinds:

| kind | direction | meaning | step weight out / in (recall) |
|---|---|---|---|
| part_of | a → b | a belongs to b, is a piece or instance of it | 0.75 / 0.6 |
| builds_on | a → b | a uses, depends on, follows from, was inspired by b | 0.8 / 0.6 |
| like | both | alike in a way that matters (the most valuable: same principle, different topics) | 0.7 |
| against | both | in tension: contradicts, undermines, is an alternative | 0.7 |
| related | both | connected some other worthwhile way | 0.5 |

Every edge has a **reason**: one sentence saying why, like the sentence around a link on a wiki page. The
reason is searchable (`c7` vectors) and is what a searcher reads to decide whether to follow it.

**Strength is computed, never picked**, from the edge's append-only supports:

```
strength(edge, as_of) = Σ over supports up to as_of:  sign × weight(kind) × fade(support)
  weight: stated 3 (he made the connection, quoted), confirmed 3, inferred 1 (the model judged it),
          observed 0.5 (came up together again), used 0.5 (a search followed it to something kept)
  fade:   1 for stated/confirmed, and for everything on part_of / builds_on / against edges;
          for like/related, model supports halve every 90 days
  the model can't argue down an edge he stated
live (followed by search) when strength ≥ 0.5; each node follows at most its 12 strongest
```

Because supports are timestamped and never deleted, the network **as it stood on any date** can be
reconstructed: "what did you believe a month ago?" is answerable. Built (Oct 15) as the graph's time slider
(`graph_data(as_of)`): each node's newest version written by then (unless retracted by then), the edges that
existed then with their strength recomputed from the supports up to then (fading measured to then), and each
edge's kind and reason as they were then, replayed from the journal. A "then vs now" page is still planned.

**Implicit neighbors** (never stored): an inference ↔ what it rests on; nodes written from the same
message; nodes from the same episode. They let search move between things that belong together without
anyone writing an edge.

**Target shape: a small world.** Dense local clusters (the writer connects what was said together),
sparse long-range bridges (Connect only judges pairs ≥ 3 steps apart), hubs that emerge but are discounted
in search (`hub_discount(d) = 1` up to 2 connections, `log2 4 / log2(2+d)` beyond, ≈ 0.5 at 12), no
islands. Measured after every reflection (`memory/health.py`): clustering vs a random graph of the same
size, average path length, islands, the share of connection ends held by the top 5 hubs.

---

## 3. Writing: the log becomes knowledge (built)

**When**: the worker writes a stretch when a sitting ends (30 quiet minutes) or about a page of messages
(20; fewer with a small `/window:`) is waiting, ending on one of her replies. Imported conversations are
only written by their own run.

**The Write job** (`mind/writer.py`): the model sees up to 50 current nodes from the *whole* memory (the
biggest hubs, the newest, and what each message brings up in search), 4 earlier messages for context, and
the stretch; it answers one tool call, `write_episode {headline, nodes[], edges[]}`. Code then checks every
part (evidence quotes located, versions only of real nodes, same-title duplicates turned into versions,
things' text kept to a sentence, her questions refused as knowledge, his nodes never changed by her words,
edges between real nodes with a kind and a reason), sends problems back in plain words up to twice, keeps
the attempt with the fewest problems, and applies it through the one door. Edges between things that came
up together again get an `observed` support.

**Every job** has the same engine (`mind/jobs.py`): prompt → one strict tool call (forced when thinking is
off; offered with `auto` when it's on, because Luminal refuses forced calls while thinking) → checks →
repair → apply → a run record (prompt, every reply, every problem, tokens, cost).

---

## 4. Reflection (built)

Quiet spells (30 minutes without a message), main memory only, within 60 model calls a day:

- **Check** (`reflect.Check`): inferences whose basis has a newer version or was retracted; non-part_of
  edges whose ends changed. Verdicts: holds (reaffirm, recording the versions checked), revise (new
  version), retract, or a negative support.
- **Think** (`reflect.Think`) over one focus: the newest unthought episode plus the older nodes closest to
  each of its nodes; or a hub that gained 3+ connections; or a quiet corner and its distant relatives. At
  most 2 inferences per run, no near-repeats (meaning ≥ 0.84 to an existing inference), no "He…" traits, a
  new thing needs 2+ parts, nested under an existing thing when it gathers the same parts.
- **Connect** (`reflect.Connect`): for each new node, candidate partners from anywhere in memory that are
  ≥ 3 steps away: close in meaning or words, sharing ≥ 2 neighbors, or whose edges have similar reasons.
  Pairs are judged 36 at a time; at most 3 new edges per node per run; judged pairs are remembered with the
  versions seen, so they aren't asked again until something changes.

## 5. Dreaming (first version built Oct 15)

`mind/dream.py`. Started by hand (the looking glass, or `/dream`), on the main memory, with a duration
(default 8 h), a money budget (default $10) and a thinking level (default **max**). It runs in a thread,
taking turns with the rest of the mind (one job at a time, so a sitting still gets written while she
dreams). Each job carries its own effort (`Job.effort`), overriding `/mind:`.

```
until time is up, the budget is spent, or he wakes her:
  every hour:   Check everything stale (all of it, 16 at a time)
  each round:   sweep    the next 6 nodes in sweep order (longest-undreamt first, a mark per node)
                         → candidate partners anywhere ≥ 3 steps away → Connect (36 pairs a call)
                think    one focus, rotating:  wander (a swept node, its neighborhood, distant relatives)
                                               hub    (a big thing and everything attached)
                                               bridge (two big things far apart, side by side)
                         never the same view twice in one dream; new inferences are connected at once
  every 30 min: measure the network's health
  a whole lap round memory that finds nothing new, twice: wake early (nothing left to find)
at the end: health measured, and a run record (job "dream") with what it did and cost
```

Measured live (tests/live/dream.py, Oct 15): at max thinking a job takes 6–9 minutes and about $0.10, so an
8-hour dream is roughly 60 jobs and $5–8; a job already thinking finishes past the deadline.

**Planned for dreaming** (decision 5 in VISION.md): *re-reading* old episodes with everything memory holds
now in view, to write what the first pass missed (a Write variant that adds nodes to an existing episode
instead of creating one); *merging* near-duplicate nodes (two chains that are the same thing: a new
version of one, the other retracted with a pointer); *dreaming over the thought graph* (promoting
conclusions; closing stale commitments); writing knowledge from the library (§8).

---

## 6. Retrieval (built), and search inside the thinking chain (planned)

### 6.1 Recall by rules (`memory/recall.py`)

For `/recall:` depth light/normal/deep/max:

1. **Land**: score every node version and episode headline against the message (and the previous message
   when this one refers back): `score = meaning + 0.15 × share of the message's words found (rare words
   weigh more)`; a hit on an old version counts for the node; a 5% nudge for today, fading over a month.
   Seeds are those above `max(found, best − near)` (echoes of the same question don't set the bar).
2. **Walk** outward along live edges and implicit neighbors for `hops` steps:
   `step = STEP[kind, direction] × (0.6 + 0.4 × min(1, strength/3)) × hub_discount(degree) × closeness to the message`.
3. **Keep** what scores ≥ `keep × best`, strongest first, within a node cap (5/12/24/50) and a token budget.
4. **Safety nets**: older messages that match by themselves (not on screen, not next to a kept node's
   evidence), and **library passages that match by themselves** (Oct 15).
5. **The note**, in tiers from most to least reliable: what he told you (quotes; full messages for the top
   three) · what you said before · what Claude said (imported) · what you worked out (with certainty and
   basis) · how these connect (edge reasons) · older messages · **from his library** (passages with source
   and place). A thing lists its newest parts like a wiki page's contents. The system prompt carries the
   *core*: the biggest hubs that were said.

### 6.2 Avy searching for herself (`mind/explore.py`, `/explore:` on by default)

The message is only a clue to the task. Rounds (light 1 … max 4); each round the model sees the message,
its notes (task, open questions), the map of the 10 biggest hubs, what it has read in full, previews of the
frontier (each node with its first connections and their reasons), raw log lines and **library passages**
its searches matched, and what it has kept; it answers `explore_memory {task, questions, open (dig),
follow (explore), search (re-land in its own words), keep [k12 | #41 | p41], done}`. Code carries out the
moves. What's kept becomes the note (same tiers). Connections followed to something kept get a `used`
support: **retrieval trains the structure**. Falls back to recall by rules if the model can't be reached.

### 6.3 Search inside the thinking chain (planned: next)

Today the search runs *before* the answer. The plan is for it to run *during* her reasoning:

```
turn:
  context = slots + a small starting note (the core, maybe a quick landing)        ← decision 3
  ask the model with thinking on and memory tools offered (tool_choice auto):
      look(query) · open(k12) · follow(k12) · read(p41 / #41) · done
  stream: reasoning … → a tool call → code runs it → result appended as a tool message
          → reasoning continues (the reasoning so far stays in the request) → … → the answer
  everything it opened and kept is recorded like explore's rounds (trace, used supports, the recall view)
```

Constraints that shape it (Luminal): forced tool calls are refused while thinking, so tools are offered
(`auto`) and the instructions make clear when to use them; reasoning and tool calls arrive in the stream
(`delta.reasoning_content`, `delta.tool_calls`), so the page can show her thinking *and* her lookups live,
interleaved, in the folded thinking block. Each tool round is a new request carrying the conversation so
far, so the prompt cache matters (the slots go first and don't change). A cap on rounds and on tokens per
result keeps a turn bounded. The saved reasoning (§1) then contains the real chain: thought → lookup →
what came back → thought, which is exactly what the thought graph (§7) is built from.

---

## 7. Internal memory (planned)

### 7.1 The thought graph

Built from the saved reasoning (`reasoning` table) after each turn, by a small job (`Reflect-on-turn`):

```
thought node:  kind (attempt | finding | conclusion | commitment | suspicion | dead_end | question),
               text (one line), status (open | done | dropped | superseded), session, turn,
               evidence: a span of the reasoning it came from (like a node's quote in a message),
               cites: knowledge nodes it relies on (k12)
thought edge:  rests_on (dependency, not order) · rejects (a dead end, with its reason) · revises
frontier:      the open nodes of the session: unchecked suspicions, open commitments, the latest conclusion
```

Rules (code-enforced, like knowledge): every thought points to a real span of real reasoning; a
commitment closes only by pointing at the thought or turn where it was done; a correction marks everything
that rested on the corrected thought for re-checking (the Check move); depth-limited trace-back.

**Each turn starts at the frontier** (a handful of nodes, fixed budget) plus the knowledge found for the
message. "How did I get here?" is a trace back along `rests_on`. The working state *is* the frontier; a
checklist is the commitments, with status and evidence.

**Session memory**: a sitting's thought graph is its scratch space, searched within the sitting. At the
sitting's end, Write decides what gets **promoted** to long-term knowledge (conclusions worth keeping, with
the thought graph kept as their basis, so a node can answer "how did you work that out?").

**The catch** (from the concept): search is triggered by the message, not by what she's about to do. So
the frontier keeps short pointers to what's been ruled out, or she checks her plan against session memory
before acting; with search inside thinking (§6.3) she can do that herself.

### 7.2 Fixed slots

| slot | budget | updated | evidence |
|---|---|---|---|
| system prompt | fixed text | by hand | — |
| preferences note | ~150 words, a list of short rules | when he states or changes a preference (detected by Write), not every turn | each rule cites the message |
| character note | ~150 words | by reflection, slowly | cites her replies |
| voice examples | 2–3 of her recent replies, word for word | rotated | they are the evidence |
| self-model slice | core + up to ~6 situational rules | per message | each rule has an origin (said / inferred) |
| working frontier | ~8 open thoughts | per turn | each points into reasoning |

Every slot update is a new version (old kept); what no longer fits moves to external memory as a node with
evidence. Code enforces the budgets.

### 7.3 The self model

A small graph of **situational behaviors**: `(kind of conversation) → behavior`, e.g. *technical work →
precise, concise, code first*; *life, philosophy → warmer, deeper*. Each turn first classifies the kind of
conversation (cheaply, or as part of the thinking-chain search), then retrieves the matching behaviors into
the slot. Origins carry over: what he said vs what she inferred (labeled as her impression until confirmed).

### 7.4 How to test it: the fork test

Stop a long conversation at a message; continue it twice, once with the full transcript and once fresh with
only memory plus the internal state; have a blind judge compare the next several replies (same plan? avoids
what failed? sounds the same? can the judge tell which is which?). Shrink the slots' budgets until the fresh
one stops matching: that's the floor. The live-test harness (`tests/live/`) and the benchmark's judge are
the pieces this reuses.

**The coined-term probe** (Shreyas, Oct 16): the sharpest single test of whether the feel is emergent. Plant a
few terms he invents in passing early in a long scripted history; much later, raise a related topic without the
term; ask nothing about it. Measure how often she uses the term unprompted, and whether a blind judge finds the
use natural rather than forced. Three conditions: no memory, a dictionary of his terms injected every turn (the
"cheat" baseline: high use, much of it forced), and Avy's memory as it is (no instruction to use them). The
interesting result is natural use without being told.

---

## 8. The library (storage built Oct 15; writing knowledge from it planned)

**Intake** (`intake.py`) reads anything into passages, with no model involved:

| what arrives | recognized by | passages |
|---|---|---|
| documents (text, Markdown, Word, PDF, slides, web pages, EPUB, notebooks) | files.py's readers | a section each (split at ~1,200 chars), labeled with the page/slide/cell and heading path |
| code | extension | ≤ 60 lines, cut at blank or top-level lines, labeled `path:first-last` |
| data (CSV, TSV, spreadsheets) | extension / sheets | 30 rows each, header repeated, labeled `rows 31-60` |
| conversations: Claude export, ChatGPT export, any JSON with speaker+text keys, WhatsApp exports, labeled transcripts, speaker headings | shape detectors (a conversation only if a few speakers come back again and again and turns cover nearly all the text) | one per message (long ones split), with speaker, role (user/assistant/other) and time |
| recordings | the speech model (reused from the attachment) | transcript chunks labeled `from 3:12` |
| folders and archives (codebases) | unpacked safely (no paths outside, no links, ≤ 20,000 files) | every file by its own kind; node_modules, .git, build folders, lockfiles, minified bundles, binaries skipped and counted |

A job goes queued → reading → storing (FTS rows: searchable by words at once) → embedding (meaning vectors,
the slow part; rate measured, so the ETA is real) → stored. Identical content is recognized by a digest and
not added twice. Files attached in the chat join the library automatically, in the memory they were
attached in (incognito's own, deleted with it). Recall and explore bring passages back (§6).

**Writing knowledge from the library** (planned; decision 1 in VISION.md): a **Read** job, the Write job's
sibling, over a run of passages instead of messages:
- evidence becomes *message span or passage span* (a second evidence kind, located the same way);
- origin needs a value for "a source said it": either a new origin `source` (with the source named, its
  own tier in the note: "from what he's read / shared"), with his own documents counting as *user*; or the
  existing mapping (avy-tier, labeled with the source), as the Claude import does today;
- conversations from elsewhere: their passages already carry speaker and role, so his lines are his words;
- when: on demand per source (the looking glass gets a [ write into knowledge ] action with an estimate),
  or during dreaming.
Until then, the library is the log's sibling: raw, permanent, searchable, cited as `p41`.

---

## 9. Parallel work (planned)

Each task is a **thread**: its own session thought graph and frontier (saved state), sharing the one
knowledge graph. A completion ping or scheduled wake-up is an **interrupt**: load that thread's frontier,
run, switch back; no thread's state leaks into another's. **Stale assumptions**: on resuming, list the
knowledge nodes the thread's open thoughts cite (via `cites`/`rests_on`), and check which got new versions
or were retracted since the thread paused (the same query Check uses); show that short list in the
frontier. Concurrent writes already go through one checkpoint (`apply` under one lock); scheduling reads a
view of every thread's open commitments.

**Test**: interleave several tasks that each wait on a slow background job; measure how accurately each is
picked back up as the number of tasks grows, against a conventional single-transcript agent.

**The case it's built for** (Shreyas, Oct 16): a task works out specific insights, starts a long background
job configured by them, and the agent moves on. When the job finishes, a single-transcript agent has either
compacted those insights away or holds them far back in a long context. A thread instead keeps, in its
frontier: the job and how to check it; the insights behind its configuration (pointing into her saved
reasoning); the prediction (what result would mean what); and the next step for each outcome. The interrupt
loads exactly that, plus the stale-assumption list. A small version of the test: N tasks (2, 4, 8), each with
a few planted, specific insights that matter only when its job "finishes"; filler work in between; at each
completion, ask for the decision that needs those insights. Score: correct decisions, and whether the
planted insight was used (checkable by its exact wording). Baselines: one growing transcript; the same with
compaction (summaries); facts-only memory. The field's nearest benchmarks are in docs/LANDSCAPE.md.

---

## 10. Turn assembly and budgets (built parts)

```
system   : instructions + footnote rule (+ incognito note) + core (the 10 biggest said hubs)   ~1.5k tokens, cached
window   : the newest /window: messages (default 20, ≤ 48k chars; files attached to them while room)
system   : the memory note (recall or explore), ≤ the depth's token budget (normal: 7k)
user     : the message + its files in <file> tags (≤ 150k chars a file, 240k in all) + pictures (≤ 16)
model    : DeepSeek-V4.1-Flash, reasoning_effort = /thinking:, max_tokens 8000 (+24k when thinking), streamed
saved    : his message (meta.files), the recall, her reply (meta: model, recall, usage, cut, thought), her reasoning
```

Context is 163,840 tokens; the log the writer sees at once is capped at 480,000 characters.

---

## 11. Seeing it all (built)

| view | shows |
|---|---|
| footnotes `[k12]`, `[p41]` | what a sentence leaned on: hover for the node or passage, click to open it |
| `↳ searched memory, kept 3 nodes · 2 passages` | the recall for that reply: everything brought, how it was reached, explore's rounds (with her thinking per round), the exact note |
| `▸ thought for 12.4s` | her reasoning before that reply |
| inspector (`/memory`) | nodes as wiki pages, connections and their support history, episodes, runs (prompt, replies, problems), the journal, health, **the library** (sources, passages) |
| the living graph (`/graph`) | the whole network in 3D; what she's looking at lights up; show only one kind (ideas, his words, hers, inferred, new or changed that week; the rest stays faint so the shape doesn't jump); a time slider for memory as it stood on any date; the path one reply's search took (where it started, what it looked at, what it brought, the connections followed) |
| **the looking glass** (`/glass`) | intake jobs (progress, rate, ETA, problems), memory's numbers, the mind now / by job / latest runs / failures, the Claude history's build (plan, build, stop, progress), dreaming (start, wake, progress), costs |

---

## 12. Testing

| level | what | where |
|---|---|---|
| offline, scripted model | every rule, every job, recall, explore, incognito, Luminal's rules, imports, files, the library, dreaming | `tests/test_*.py` |
| browser, fake Luminal | the page: basics, commands, inspector, graph, dials, incognito, voice, files, light/dark contrast audit, thinking, sounds, library, looking glass, dreaming | `tests/page/` |
| the benchmark, real model | a scripted month, 10 probes × 5 search setups, a judge | `tests/bench/` |
| live scenarios, real model | interference, corrections, enumeration, dates, implicit relevance, a multi-day task, files, preferences (with and against the defaults), the short-term gap, evolving ideas, whose idea was whose, a plan that lives in her replies, an old Claude history through the library; a simulated user for filler who knows what he's said | `tests/live/` (findings: `tests/live/RESULTS.md`) |
| planned | the fork test (§7.4), interleaved tasks (§9), the real-scale Claude-history build | |

---

## 13. Where it lives

| part | code |
|---|---|
| the turn, settings, endpoints, the looking glass's data, the history build's control | `app.py` |
| the model client and its rules | `luminal.py` |
| files attached in the chat | `files.py` |
| the library's intake | `intake.py` |
| stores, rules, the one door, search, recall, the inspector's reads, the library | `memory/` |
| the mind: jobs engine, Write, Connect/Think/Check, explore, worker, dreaming | `mind/` |
| the page (one file: styles, markup, script, numbered sections) | `index.html` |
| tools: Claude export reader and import/run, log copy | `tools/` |
