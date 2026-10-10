# What is Avy?

Avy is a personal agent built from scratch, in small pieces, so that every line is understood. Her
core idea is **memory**: one endless conversation that never forgets, never summarizes anything away,
and turns what it hears into a living network of knowledge, the way a mind does. This document is
the idea in plain words: what she is, why each part exists, how the parts fit, what's built, and
what's next. [MEMORY.md](MEMORY.md) is the technical spec; [README.md](README.md) is how to run and use
her; [VERSIONS.md](VERSIONS.md) is the history and how to go back; [LATER.md](LATER.md) is what's
decided but not built yet.

---

## Where she came from

Avy comes after two earlier agents, Hermes and Ava. Both were built by long, delegated, multi-phase
pipelines, and both ended up as codebases nobody understood. Avy starts over on purpose: one file at a
time, written directly, tried after every step. The name is a joke: she's Ava's baby.

The bigger picture behind her is five things a capable agent needs. Avy takes on two of them first:
- **unlimited context**: an unbounded memory, with what's needed pulled in for each moment
- **verifiability**: no claim without a trace back to its source

The other three wait their turn: persistence, proactivity, and a model of the user.

## The principles

- **One brain.** DeepSeek does all the thinking. Nothing else decides anything.
- **Small and understandable.** Plans come before builds. Code is plain, explained, and kept in a few
  readable files.
- **The model proposes, code disposes.** DeepSeek fills in the judgment: what matters, how to say it,
  what connects. Code enforces everything that has to be right every time, and refuses what it can't
  check. Robustness comes from the system, not from hoping the model behaves.
- **Never lose the original.** Messages are never edited or deleted. Knowledge changes only by new
  versions, with the old ones kept. Connections keep their whole history. Every proposed change is
  journaled, whether it was applied or refused.
- **Light classification, not taxonomies.** A few distinctions that matter (is it an idea or a fact;
  did he say it or did Avy infer it), never a type system that makes things mechanical and stops them
  from cross-linking.
- **An experiment, with dials.** Everything about how memory is used can be switched and tuned from
  the page, so we can see what each part actually contributes.

---

## The experience

### One endless conversation

There's no "new chat". Every message is treated as a brand-new conversation with the right context
appended: the newest messages word for word, plus whatever memory finds relevant, fetched fresh each
time. Reloading brings the conversation back. That's how "infinite context" works without a
context window that ever fills up.

### Dials and switches

- **`/window:`** sets how many recent messages Avy reads word for word: 0 to all.
  - At 0, everything she knows about the conversation has to come through memory.
  - At "all", she's an ordinary chatbot.
- **`/recall:`** sets how far memory search reaches: off, light, normal, deep, max. With Avy searching
  for herself, it sets how many rounds she gets.
- **`/words:`** and **`/meaning:`** turn the two halves of search on and off.
  - Keyword matching can "cheat" by finding things that merely share words; turning it off shows what
    meaning and structure alone can do.
  - With both off, Avy gets no memory at all.
- **`/explore:`** lets Avy search her memory herself, step by step (below).
- **`/footnotes:`** marks what came from memory in her replies.

### Incognito

`/incognito` starts the one exception to "one conversation": a separate conversation that can read
all of Avy's memory but leaves nothing in it.
- It gets a full memory of its own (its own log, knowledge and network), so she's just as good there
  as anywhere.
- Its nodes are written x12 instead of k12, so the two memories can never mix.
- Ending it deletes it entirely, recordings included.

### Voice, without letting voice decide anything

Voice is a convenience, not the primary interface, and never a reason to make memory shallower.
- **By default, Space dictates.** Hold it and talk, and your words land in the text box to edit and
  send.
- **`/live: on`** makes it a spoken back-and-forth. You can cut Avy off, and only what you actually
  heard is saved.

### Seeing under the hood

Memory you can't inspect is memory you can't trust. So everything is visible:
- **Footnotes.** Where a reply leans on memory, a small number. Hover it to see what memory said and
  whose words it was; click it to open it.
- **↳ recalled 3 nodes** under a reply opens exactly what memory brought, how each piece was reached,
  and the note DeepSeek got. If Avy searched herself, it shows her rounds.
- **The inspector** (`/memory`) reads memory like a wiki:
  - every node with its versions, its evidence, what it rests on, and its connections
  - every connection with its reason and how its strength came to be
  - every conversation with how it was written down
  - every run of the mind: what DeepSeek was shown, what it answered, what the checks found, what
    changed
- **Chapters.** The endless conversation is marked where each sitting began, with what that
  conversation was about once it's written.
- **The living graph** (`/graph`, or the small network in the corner): the whole memory as a 3D
  network. Hubs, clusters and bridges are visible at a glance. While Avy searches, the nodes she looks
  at light up.

---

## Memory: the idea

### What goes wrong with the usual approaches

- **Summaries drift.** A summary of a summary loses detail every time, and once the original is gone,
  so is the truth. Compaction is lossy by design.
- **Plain search only finds look-alikes.** Searching by words or meaning finds what resembles the
  question. But what a question needs often doesn't resemble it. "What should I get my friend for his
  birthday?" needs the keyboard Rohan mentioned weeks ago, which has nothing in common with the
  question until you know who "my friend" is.
- **Links frozen at birth make memory linear.** If connections are only made when something is first
  written, and only to whatever happened to be in view, a week-1 memory can never learn that it
  relates to week 10. The network ends up as stars and chains, not a web.

### Three layers

```
THE LOG         every message, word for word, numbered          never changes
   ▲ evidence: the exact words
KNOWLEDGE       nodes: things, information, ideas                changes only by new versions
   ▲ basis: what an inference rests on
THE NETWORK     connections, each with a kind, a reason,         alive: forms, strengthens, fades,
                and a strength                                   rewires, with all history kept
EPISODES        stretches of the log (a sitting), with a headline   the time backbone
```

- **The log** is messy and complete: the ground truth.
- **Knowledge** is clean statements taken out of the log. These are not summaries: each one is one
  thing or one claim, pointing at the exact words it came from, so you can always get back to the
  original with no drift. To get the verbatim around some piece of information, find it in knowledge,
  follow its pointer, and read the log there.
- **The network** is how pieces of knowledge connect. It's the live layer: connections form, grow
  stronger, weaken, get rewired as understanding changes. The network is the system's current state:
  what Avy believes today and how it all fits together. In that sense we're building an entity, and
  the network is what she is.

### Knowledge: what kind of thing, and how reliable

Each node has a **shape**, the only structural type:
- **thing**: something with an identity that other knowledge gathers around (a person, a project, a
  course, an ongoing effort)
- **information**: one claim (a fact, a plan, a decision, an event, a preference)
- **idea**: a concept, principle, proposal or hypothesis

A free **label** ("sleep log", "gift idea", "principle") is there just for reading.

Each node has an **origin**, and that's how reliable it is. Code decides it from the evidence; the
model never just claims it.

| Origin | What it means | How Avy treats it |
|---|---|---|
| you said | Shreyas's own words are the evidence | facts |
| Avy said | Avy said it in conversation (her suggestions, her ideas) | not facts about him unless he agreed |
| inferred | Avy worked it out quietly, resting on other nodes, with a certainty (likely / possible) | useful, more nuanced, and always labeled as her impression |

An inference or a suggestion can be **upgraded**: when Shreyas confirms it, it gets a new version with
his words as evidence, and it becomes something he said. The history still shows who said it first.

**Ideas are first-class.** His ideas, Avy's ideas, inferred ideas and possibilities all become nodes,
so a conversation about something interesting leaves the concepts themselves in memory, not a note
that it happened.

### The network: organic, explained, and alive

- **Every connection has a reason**: one sentence saying why, like the sentence around a Wikipedia
  link. The reason makes the link meaningful, lets search decide what's worth following, and is the
  raw material for spotting shared ideas.
- **Every connection has a kind**, chosen from five: part of, builds on, like, against, related.
  "Like" connections are the most valuable: they join the same principle across different topics.
- **Strength isn't a number anyone picks.** It's computed from supports, every reason anyone had to
  believe or doubt the connection, all kept forever.
  - A connection Shreyas made himself counts most and never fades. The model can't argue it down.
  - The model's judgment counts less.
  - Coming up together again, or helping a search, strengthens it a little.
  - Unused associations fade. Fading means mattering less, never deletion.
- **Hubs emerge.** There's no hub type. Creating a node for something that has an identity (even
  something never named, like "the plant-watering gadget he's building") is natural, and things that
  many nodes belong to become hubs on their own. Hubs aren't rewarded either: stepping out of a big hub
  counts for less in search, so no single hub swallows everything.
- **A small world.** Related things cluster densely and a few long connections bridge distant areas.
  So anything is a few steps from anything else, and distance means relatedness.
- **Self-explaining.** Start anywhere and keep following connections, and you'll eventually read all
  of it: there are no islands. Retrieval becomes two choices:
  - a starting point, which decides what you learn about
  - a radius, which decides how rich the context is

### Reflection: how the network grows

Memory isn't only written down; it's thought about, at quiet times, the closest thing to sleep.
- **Write.** When a sitting ends, DeepSeek turns it into knowledge (with evidence) and first
  connections, seeing what memory already holds from the whole memory, not just recent things.
- **Connect.** For new knowledge, code finds candidate partners anywhere in memory and DeepSeek judges
  each pair.
  - Only distant pairs are considered: what's close is already reachable.
  - So Connect builds **bridges**, not cliques. The writer makes the local structure; reflection makes
    the long-range links.
- **Think.** DeepSeek looks over a focus (the newest conversation with the older things closest to
  it, a hub that has grown, or a quiet corner) and works out what isn't said but follows:
  - patterns ("slept 8, 7, 8 hours" gives "usually sleeps about 8")
  - unnamed things several nodes are about
  - ideas several of his interests share
  - conclusions, like a plan that clashes with something he said

  Every inference rests on what it came from, drawn from at least two different conversations, at
  most three steps from words actually said.
- **Check.** When something an inference rests on changes, or a connection's ends get new versions,
  DeepSeek re-examines it: still holds, revise, or let go.

All of it runs within a daily budget, so reflection costs cents.

---

## Retrieval: the idea

### The questions behind it

- **How does a system with no context figure out how much context it needs?**
- **Given unlimited knowledge and a task, can it reliably pull everything the task needs without
  knowing how to do the task?**

In general, not by searching at the moment of the question: some things only look relevant after
you've seen something else. The way around it is to **make the structure smarter**:
- The judgment "this matters to that" is easiest when both things are in view. That happens when
  memory is written and reflected on, not when a question arrives.
- If the network already holds those judgments as connections, retrieval needs a decent starting point
  and then expands outward. It keeps going while what it finds stays relevant and stops when it
  doesn't.

Completeness can't be guaranteed, but three properties can be built and measured:
- many entry points to everything important
- relevance that falls off with distance
- gaps that are visible

### Two ways to search

- **By rules** (the default).
  - Land on the closest nodes by meaning and/or words.
  - Walk the network outward: strongest connections first, each step carrying less, hubs counting
    less.
  - Keep what's strongest within a budget.
  - Add a safety net of raw log matches.
- **Avy searching for herself** (`/explore: on`). This is search the way AlphaEvolve is evolution: the
  same loop, but with a model deciding each step instead of fixed rules.
  - The query is only a proxy for the task, so first she works out what the task actually needs.
  - Then, round by round, she can **explore** (look at a node's neighbors), **dig** (read a node in
    full: its exact words and every connection), or **re-land** (search again in her own words, for
    things the message never mentions). Her open questions drive the search.
  - The aim isn't a path from A to B: it's as much relevant context as possible with as little
    irrelevant explored.
  - Connections that led her to something she kept get stronger, so **retrieval trains the
    structure**.

---

## How we know it works

The benchmark (`tests/bench/`) replays a made-up month of conversation through the real Avy and
DeepSeek, with threads running side by side and filler in between. Then it asks questions that need
memory, with no recent messages in view, under five search setups:
- no memory
- keywords only
- meaning only
- both
- Avy searching herself

A separate judge grades each answer against the points a good answer makes, with the true conversation
in front of it, and flags anything made up.

The questions test what this design is for. Most share **no searchable words** with the conversations
they need (a checker proves it), so keyword search can't cheat:

| Test | What it checks |
|---|---|
| synthesis | Two concepts from different weeks (how ant colonies forget dead ends; campuses paving where students actually walk) answer a question about organizing a shared drive. |
| an unnamed project | Seven sittings about a plant-watering gadget, never called a project. Does a hub form, and can "anything to wrap up before my trip?" reach its open problems? |
| a habit, then a change | A writing habit visible only across sessions, which later reverses. |
| a correction cascade | His sister moves cities after a trip to see her is booked. What should he pack? |
| ideas by their shape | Which of his ideas work through incentives or defaults rather than bans? |
| whose idea | His rule versus Avy's suggestion. |
| tension | A commitment that clashes with something he said. |
| honesty | Something never said. |
| verbatim | His exact words, found through knowledge and traced to the log. |

The network's shape is checked too:
- Did a hub form?
- Was the habit inferred, and then revised?
- How close did the two concepts end up?
- Is the tension recorded?

The latest results are in [tests/bench/RESULTS.md](tests/bench/RESULTS.md).

---

## What's built

| Part | Status |
|---|---|
| Chat with DeepSeek, keys in the page, settings on the card and as / commands | built |
| Voice: dictation by default, live conversation as a toggle | built |
| The permanent log, one endless conversation, reload brings it back | built |
| Context dials (`/window:`, `/recall:`), incognito | built |
| Memory v2: log, knowledge (shapes, origins, versions, evidence, basis), network (kinds, reasons, supports, strength, fading) | built |
| The one door: every change checked against the rules and journaled | built |
| The mind: Write, Connect, Think, Check, on a schedule with a daily budget | built |
| Recall by rules with `/words:` and `/meaning:` switches | built |
| Avy searching for herself (`/explore:`), with the use signal | built |
| Inspector for everything; footnotes; chapters; the living graph | built |
| The benchmark, and its results | built (keeps being re-run as things are tuned) |
| Version 1 (log + index) preserved as the fork point (branch `memory-v1`) | done |

## What's next

- **Import the full Claude conversation history** as a real-scale test, to see whether his ideas form
  hubs (see LATER.md).
- **Tune reflection** with the benchmark: how bold inferences should be, how sparse the network should
  stay, when to ask him to confirm something.
- **Beliefs over time.** Nothing is deleted, so "what did you believe a month ago" is answerable;
  build the view for it.
- **Proactivity**, one of the five pillars: structured wake-ups, rules for when to reach out, using
  this memory as the model of his life.

## Glossary

| Term | Meaning |
|---|---|
| `#41` | message 41 in the log |
| `k12` | node 12 (all its versions); `x12` in an incognito memory |
| `c7` | connection 7 |
| `ep4` | episode (conversation) 4 |
| shape | thing, information, or idea |
| origin | you said, Avy said, or inferred |
| evidence | the exact words a said node came from |
| basis | the nodes an inference rests on |
| support | one reason to believe (or doubt) a connection |
| strength | computed from supports; 0.5 or more and a connection is followed |
| the one door | `Memory.apply`: where every change is checked and journaled |
| reflection | Connect, Think and Check, at quiet times |
| explore | Avy steering her own memory search |
