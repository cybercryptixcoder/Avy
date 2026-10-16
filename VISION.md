# Avy: the vision

What we're building, and why. This is the living statement of the idea: it grows as Shreyas adds ideas,
features and principles, and it says plainly what's built, what's next and what's still his to decide.
How each part works (or would work) is in [ARCHITECTURE.md](ARCHITECTURE.md). The story of how it got here
is in [docs/HISTORY.md](docs/HISTORY.md); the running record of the build is [docs/BUILDLOG.md](docs/BUILDLOG.md).

Source: Shreyas's concept document *Context as a library: Avy and its memory architecture* (Oct 15, 2026),
and everything he has said since, in his words where it matters.

---

## 1. The one idea

**A memory that never fills up and never forgets.** Every message is answered as if it were a brand-new
conversation, with the right context fetched fresh from a record that keeps everything.

A model can only work with what fits in its context window, and it doesn't keep learning from anything
outside it. Today, the whole conversation is sent with every message, and when the window fills up it gets
compacted, and compaction always loses information. Avy stops doing that:

- The **context window is active memory**: a small, fixed desk.
- The **stored record is passive memory**: a library that keeps growing far past what the desk could hold.
- Every message gets the right context attached, built at the moment it's needed from only what's relevant.

The effect is close to unlimited context: everything Avy has been told or has learned stays available,
while she only ever sees what she needs.

**The real question** is how the model knows what to pull from passive into active memory, when it doesn't
know everything that's stored or everything the task will need. That's why the storage and the search are
built the way they are: *finding context becomes exploration*. Someone solving a problem in a library
doesn't know everything they'll need; reading one thing shows them what else they need, and the library's
structure is what makes that possible. Avy's memory is meant to be that structure.

## 2. Two problems and one question

- **Context**: the window is limited, and squeezing more into it loses information.
- **Learning that continues**: what a model picks up lives in the context, and nothing carries on past it.
- **The interesting question**: is it possible to get everything you need *without knowing what you need*?

Completeness can't be guaranteed, but three properties can be built and measured: many entry points to
everything important, relevance that falls off with distance, and gaps that are visible.

## 3. Why the usual fixes fail

- **Summaries drift.** A summary of a summary loses detail every time; once the original is gone, so is the
  truth.
- **Plain search only finds look-alikes.** What a question needs often doesn't resemble it ("what should I
  get my friend for his birthday?" needs a gift idea mentioned weeks earlier).
- **Links frozen at birth make memory linear.** If connections are made only when something is first
  written, a week-1 memory can never learn that it relates to week 10: stars and chains, not a web.

## 4. External memory: a library that explains itself

Everything Avy knows about the world (Shreyas, his life, his work, ideas) is **external memory**: it faces
outward. It has layers, each built from the one below, and nothing is ever lost:

1. **The log**: every word said, kept word for word, numbered, never edited. Messy and complete: the
   ground truth.
2. **The library** *(added Oct 15)*: everything he adds that wasn't said in the conversation (documents,
   papers, code, data, recordings, conversations he had elsewhere) kept word for word as passages, like the
   log. **Anything, in any format**: there is no required schema. It's read, kept and searchable at once.
3. **Knowledge**: clean, individual facts and ideas pulled out of the log (and later the library), each
   pointing at the exact words it came from. Not summaries: one thing or one claim per node. Versioned:
   facts change by new versions, old ones kept.
4. **The network**: knowledge linked into a web where every link is a relationship with a reason. Related
   things cluster, hubs form around what matters, a few long links bridge distant concepts.

**The example.** The node *Shreyas* links to his attributes (birthday, hometown, citizenship). Those nodes
also link to other people: the birthday node holds `person : birthday` entries. The structure gives
different doors for different topics, the way a library does.

**Light classification, not taxonomies.** Only distinctions that matter: a node is a *thing*, *information*
or an *idea*; it was *said by him*, *said by Avy*, or *inferred* (with how sure). Inferences can be upgraded
when he confirms them; only his words change what he said.

**A living network.** Connections form, strengthen with use, fade without it, and get rewired, with all
history kept. Strength is computed from every reason anyone had to believe a connection, never picked.
Hubs emerge; they aren't rewarded. Start anywhere and keep following connections and you'll eventually read
all of it: there are no islands.

## 5. Reflection: memory that's thought about

Memory isn't only written down; it's thought about at quiet times, the closest thing to sleep:
- **Write**: when a sitting ends, it becomes knowledge, with evidence and first connections.
- **Connect**: new knowledge is judged against partners from anywhere in memory; only distant pairs, so it
  builds bridges, not cliques.
- **Think**: what isn't said but follows (patterns, unnamed things, shared ideas, tensions), with a high
  bar: resting on things he said in at least two conversations, at most three steps from words actually
  said, describing what happens, never who he is.
- **Check**: when what an inference rests on changes, it's re-examined: holds, revised, or let go.

### Dreaming *(Shreyas, Oct 15)*

> "Dreaming is essentially forming connections and finding new things, and that happens over a long
> duration. It's done with thinking mode set to max... left for literally an 8-hour stretch... to form
> these connections and form this kind of almost living thought over a long duration. It's meant to index
> everything else again, just go over things."

Ordinary reflection is short and cheap and reacts to what's new. **Dreaming is the other end**: hours of
reflection at the deepest thinking, with no question to answer, sweeping the *whole* memory to reorganize
it: re-checking, connecting things that have never been compared, thinking about hubs and about pairs of
distant hubs side by side, measuring how the network changes. It's what makes week 1 meet week 10 without
anyone asking. It's started on purpose (e.g. overnight), within a money budget, and can be woken.

## 6. Search: finding what you need without knowing what you need

In a library you don't read every book until you find the right one: you read something, decide what you
need next, and keep going. Avy's search works the same way: it works out what the task is asking for and
where to start, moves through the network node by node (at each node it sees what's reachable from there),
and links that led somewhere useful get stronger, so search gets better the more it's used.

**The example.** "How old am I?" → look up his name → see what's stored about him → move to his birthday →
do the math.

**The bigger point**: searching only at the moment of the question can't find everything, because some things
only look relevant after you've seen something else. So the structure itself must be smart: judging that
one thing matters to another is easiest when both are in view, which happens when memory is written and
reflected on. If the network already holds those judgments as connections, retrieval needs only a decent
starting point, then expands while what it finds stays relevant.

### Search driven by the thinking chain *(Shreyas, Oct 15; next)*

Today, memory is searched *before* Avy answers: a static step that hands the model a note. The vision is
for search to happen **inside her thinking**: as she reasons about the message, she realizes she needs
something ("wait, which Rohan?"), looks it up, reads what comes back, and carries on thinking, as many times
as the task needs. The thinking chain decides what to search for, so the search follows the task, not the
words of the message. (The first piece is in place: her thinking is now kept and visible.)

## 7. Internal memory: the agent's own state

Retrieval gives good context about everything Avy needs to *know*, but on its own she loses a sense of
self: not in a metaphysical sense, in the sense of her own reasoning and progress. In a long task, an agent
keeps track of what it tried, what failed, what it suspects, what it'll do next. If every message discards
that, the agent loses something.

- **External memory** faces outward: a model of everything known about the world. (Sections 4–6.)
- **Internal memory** tracks the system itself: its thoughts, its state, what it's working on and trying
  to achieve.

**The reframe.** Since every message is like a new conversation: what would you have to drop into a
brand-new conversation to make the agent in it feel exactly like it did in a long one? A model carries no
hidden state between messages; the character of a long conversation comes entirely from the transcript,
mostly from the agent's own earlier replies. So the question is concrete: **what is the smallest text that
makes a fresh conversation behave like the long one?**

**Two parts, kept apart:**

| Part | Holds | Changes | Belongs to |
|---|---|---|---|
| Working state | the goal, the plan, what's been tried and how it went, the current hypothesis, the next step | every turn | one task |
| Character | tone, shared shorthand, what he already knows, agreements about how to work together | slowly | the relationship |

**It must not grow like a context window.** What's in view is a snapshot of where things stand now, with a
fixed shape and a hard budget; each update is a new version, not an addition; what no longer fits moves to
external memory with evidence pointing at the exact turns. External memory grows without limit because it's
searched, not shown; internal memory stays a fixed size because it's shown, not searched. **The real risk
is drift, not size**: every item points to its evidence, and code refuses an item that has none.

### The thought graph

Carry forward what was *concluded*, not the thinking itself. A turn's thinking leaves three kinds of things:

| Kind | Example | Where it goes |
|---|---|---|
| Conclusion | "X is impossible" | learned: session memory, discoverable when needed |
| Commitment | "next I'll try Y" | unfinished: stays in view in the working state |
| Open suspicion | "I think it's Z, but I haven't checked" | unfinished: stays in view in the working state |

Thoughts form a network of their own: each turn starts at the **frontier** (the open ends: the main
conclusion, an unchecked suspicion, a next step), and traces back only when it needs to ("how did I get
here?"). Thoughts link **by dependency, not by order**, so a dead end stays as a rejected branch with its
reason, and a correction spreads to exactly what rested on it. The pointer to where the last turn left off
works like a program counter: only what's at the frontier is in view, everything behind it stays reachable.

**The working state is the thought graph's frontier**: one source of truth. A checklist is a view too: a
task is a commitment node with a status, and closing it requires pointing at the thought or turn where it
was done, so a checkmark is a claim with evidence.

**Two graphs, one network**: the world (knowledge, long-lived, searched by topic) and her own thinking
(scoped to a session, entered at the frontier). Thoughts cite knowledge; conclusions worth keeping get
promoted into knowledge at the end of a sitting. Each turn starts at both entry points.

*Built so far:* her reasoning is saved next to every reply (the "first concrete step"), and shown folded
under it.

## 8. Character and the self model

The character persists through every message, so it can't keep being appended to. It's one of the places
where things are **overwritten within fixed amounts of space**, like registers:

- **The system prompt** carries most of the character.
- **A preferences note** ("keep it short", "don't explain so much"), fixed size, overwritten when she
  decides to update it, each preference citing the message where he said it.
- **A character note**: her own voice, tone, how she sees herself. Fixed size, overwritten, versioned.
- Possibly two or three of her own recent replies kept word for word as examples of her voice.

**The self model** grows: a web of how to behave in different situations (precise and concise when he's
doing something technical; warmer and deeper when it's about life). Each message searches it **by the kind
of conversation, not the topic**, giving, in effect, a dynamic system prompt per message. A fixed core is
always in view; situational behavior is retrieved. The origin tiers carry over: "keep it short" is something
he said; "wants depth when talking about life" is her inference until he confirms it.

### The feel *(Shreyas, Oct 16)*

*"You know how you have a really long conversation with an agent, and then you don't want to switch
conversation because you've spoken to it for so long? Now the agent gets you... Not just in terms of how long
a message is or what vocabulary is used, but it's a mix of those. It's more so a feel. How do we preserve
that?"*

What a long conversation builds, roughly in layers, and what a new chat loses:
1. **Surface**: length, vocabulary, rhythm.
2. **Stance**: how she pushes back, how dry or warm she is, and when.
3. **A shared world**: names coined together, callbacks, running jokes ("Gerald", "the hinge").
4. **Anticipation**: her model of what he'll want before he says it.
5. **Momentum**: the threads still in the air.

A preferences note covers part of the first layer. The rest lives only in the transcript, which is why
leaving it hurts. Ideas for holding it (his to decide): her own replies that *landed* kept as examples,
chosen for the kind of conversation rather than just the latest; **a shared lexicon**, every coined term with
a pointer to the message where it was born; **his corrections as the strongest signal** ("too long", "don't
do that"), lessons about manner rather than facts; and the character note written from that evidence.
**The measure is the fork test** (ARCHITECTURE §7.4): continue a long conversation twice, once with the
whole transcript and once from memory alone; if a blind judge can't tell which is which, the feel survived.
Nobody publishes that number yet.

**Emergent, not scripted** *(Shreyas, Oct 16)*: *"Maybe four months ago I said a certain term in the middle of
something, maybe I just invented it. It would be really cool if, while working on something else, the LLM
described it using that term... You could cheat that: just create a dictionary. If it's an emergent response
through our setup, that's a lot more interesting. And that's not limited to vocabulary: that's the entire feel
of it, the entire behavior."* The distinction matters for the design: a dictionary injected every turn forces
the words in (and overuses them); the interesting version is when nothing tells her to use them and she does,
because memory brought the moment he coined the term to the table at the right time. Avy's structure already
points that way: his exact words are kept, a term he coins becomes a thing in memory pointing at the message it
was born in, and connections lead from related topics to it. The test: plant coined terms early, raise a related
topic months later without the term, and measure whether she uses it unprompted and appropriately, against
no memory and against a dictionary (ARCHITECTURE §7.4).

## 9. Putting it together: one turn's context

Each turn's context is built like allocated memory: **fixed slots that are always shown**, filled partly by
searching **stores that are never shown whole**.

```
ACTIVE MEMORY (fixed slots, every turn)          PASSIVE MEMORY (stores: searched, not shown)
  system prompt ........ most of the character
  preferences note ..... fixed size
  character note ....... fixed size
  self-model slice ..... core + what fits this   <-- self model (the web of how to behave)
  working frontier ..... open ends of thinking   <-- thought graph (her reasoning, linked)
  retrieved knowledge .. found for this message  <-- knowledge graph + library (passages)
  recent messages ...... as many as the window   <-- the log (every word, never edited)
  the new message
```

The slots stay the same size however long Avy runs. Everything that grows lives in the stores.

### Fixed slots, like an instruction format *(Shreyas, Oct 16)*

His parallel, from the hardware design he was learning: in a computer there's a fixed amount of space, and an
instruction format (R-type, I-type) allocates exactly so many bits to this field, so many to that. Nothing to
replicate, just the shape of it: the context window is active memory, and it gets a fixed layout too, with a
set allocation for the persona, a set allocation for internal memory, and so on. Not the whole window, and as
little of it as possible, but each part with its own fixed space.

### Everything is a model of something *(Shreyas, Oct 16)*

Internal memory has an active and a passive side too: the active side is what's in its slots; the passive side
is "just another model". *"This aspect of models keeps coming up... the system builds a model of everything."*
An entity can be a person, a project, Avy herself, or anything else, and the system forms a model of each: the
world, everything it knows. One of those models is her own state. So the architecture is, by nature, a
collection of models of entities, each with a small active part kept in fixed slots and a passive part
searched when needed.

### Seen by time *(Oct 16)*

The same system, sorted by time:
- **The past**: the log, the library and knowledge. Built, and the strongest part.
- **What's always true**: habits and identity (the preferences note, character, the core of who he is).
  Designed.
- **The present**: her working state (the thought frontier, threads). Designed.
- **The future**: intentions waiting for a cue, and what's coming up. Not designed yet.

Every failure the live tests reproduce sits outside the past: preferences (always), plans and what's coming
up (the future), a plan that lived only in her own reply (the present). Human memory has a separate system
for each of these, which is where the parallels in docs/IDEAS.md ("Human memory, and what it suggests") come
from.

## 10. A side effect: parallelism and multitasking

Because every message starts like a new conversation, Avy doesn't depend on one trail of context. When a
background job finishes or a scheduled task fires, she can jump straight to that task's frontier and pick
up exactly where it was, unclouded by newer work: **like an operating system**, where each paused task keeps
its own registers and program counter, and a completion ping is an interrupt. Separate in thinking, shared
in knowledge: every thread writes into the same knowledge graph. The catch is stale assumptions; the fix is
to check, on resuming, what changed among the nodes that thread's thoughts depend on (the Check step's move).
Writes at the same time go through the one checkpoint; scheduling uses a view of every thread's open
commitments.

### Long-horizon multitasking: the hypothesis *(Shreyas, Oct 16)*

His example: a coding agent sets up a training run after working out a set of very specific insights, starts
it in the background, and moves on to other work. The context grows; by the time the run finishes, the
insights that shaped it are either compacted away or so far back that the model is hazy on them, so it judges
the results and continues the work worse than it would have at the time.

**The hypothesis: Avy can be the best at long-horizon multitasking**, because nothing she needs has to
survive in one growing context. Each task keeps its own state; when the run finishes, she resumes *that*
thread with its insights, not the last hour of unrelated work. What has to be true for it to work: the
insights must be captured as the thread's state (why the run was configured that way, what result would
mean what, what to do next), not only as facts; that's the thought graph and the frontier (§7), plus her
saved reasoning (built). What the field shows (docs/LANDSCAPE.md): agents do well on single tasks and worse
when the same tasks are interleaved; on interdependent multi-session tasks every tested memory system scores
near zero; memory built for chat loses the dense state and causal detail of agent work. Supermemory's agent
memory saves structured compaction summaries and extracted facts, with no per-task state and no published
measurement of this. **Open ground, and measurable**: the interleaved-tasks test (ARCHITECTURE §9).

*Oct 16:* the first expedition tried a version of that test (its E01) and reported the idea "not supported".
The test never reached long horizon: with eight interleaved jobs the whole transcript was about 1,150 tokens,
compaction almost never fired, and the plain transcript got better as jobs were added. So the hypothesis is
still untested, not refuted; the next attempt needs real lengths and a decision that's only right if the old
insight survived (docs/EXPEDITION-1.md).

## 11. Everything is visible

**Memory you can't inspect is memory you can't trust.** Footnotes on replies, what memory brought for each
reply and how, the inspector (every node, version, connection, run, the journal), chapters, the living
graph, the library, her thinking under each reply, and **the looking glass** *(Oct 15)*: one live view of
everything loading into memory (with real rates and how long it'll take), what the mind is doing and has
done, failures, the state of memory, the Claude history's build, dreaming, and what it all costs.

## 12. The experience

One endless conversation: no "new chat". Dials for everything about memory (`/window:`, `/recall:`,
`/words:`, `/meaning:`, `/explore:`), so what each part contributes can be seen. How hard she thinks:
**none, low, high or max** (DeepSeek's three levels, plus off). Incognito. Voice that never makes memory
shallower. Files of any kind. A page that's beautiful to use: terminal-quiet chat, neo-brutalist panels,
textured not neon, **a dark mode that's done properly**, and small sounds for what happens (sending, a reply
landing, clicking, touching a node, the swish of the graph turning).

**One entity, not a new chat** *(Shreyas, Oct 16)*: people are used to opening a new chat and getting a fresh
agent every time. Avy is one conversation that keeps growing, so she grows more accustomed to you and you to
her: less "let's open a new chat", more "let's go back and talk to Avy". A persona that evolves, learns and
grows into what this person wants it to be, from the relationship rather than from settings, is what would make
it something people come back to.

## 13. The bigger picture

Five things a capable agent needs. Avy takes on two first:
- **Unlimited context**: an unbounded memory, with what's needed pulled in for each moment.
- **Verifiability**: no claim without a trace back to its source.

Then: **persistence** (internal memory: the thought graph, character, self model), **proactivity**
(structured wake-ups, rules for reaching out, using memory as the model of his life), and **a model of the
user**.

**Avy as an agent of her own** *(Shreyas, Oct 16)*: web search, a terminal, the ability to act, so she
doesn't only remember and talk but does things; and new features in her page as she grows. Long-horizon
multitasking (§10) is where memory and acting meet.

## 14. Principles

- **He decides.** Every detail of the concept comes from Shreyas's reasoning; the code is written by Claude.
  Plans before builds; structural decisions are his. Build what's straightforward, write down what needs a
  decision.
- **One brain.** DeepSeek-V4.1-Flash through Luminal does all the thinking; local models only hear, speak
  and search by meaning.
- **The model proposes, code disposes.** Judgment from the model; everything that must be right every time
  enforced by code, which refuses what it can't check.
- **Never lose the original.** The log, the library and her reasoning are permanent; knowledge changes by
  versions; connections keep their history; every proposed change is journaled.
- **Small and understandable.** Plain code, explained, in a few readable files. Tested after every step,
  against the real model where behavior matters. Documented as it's built.
- **An experiment, with dials.** Everything about how memory is used can be switched and measured.
- **Built for him**, private, cheap to run (cents a day, except when he chooses to spend: dreaming, the
  history build).

## 15. What's built, what's next

| Part | State |
|---|---|
| The log, one endless conversation, context dials, incognito, voice | built |
| Knowledge (shapes, origins, versions, evidence, basis) and the living network | built |
| Write, Connect, Think, Check; the one door and its journal | built |
| Recall by rules; Avy searching for herself (explore) | built |
| Inspector, footnotes, chapters, the living graph | built |
| Thinking levels none/low/high/max; her thinking kept and shown | built (Oct 15) |
| **The library**: anything added, any format, read into searchable passages | built (Oct 15) |
| **The looking glass** | built (Oct 15) |
| **Dreaming**, first version (sweeps, connects, thinks at max for hours) | built (Oct 15) |
| Dark mode, sounds | built (Oct 15) |
| Knowledge written *from* the library (nodes citing passages) | next; needs his decisions (§16) |
| Search inside the thinking chain | next |
| The thought graph, working frontier, session memory, promotion at sitting's end | designed |
| Preferences note, character note, self model | designed |
| Parallel threads (frontiers as saved state, interrupts, stale-assumption check) | designed |
| Fork test, interleaved-tasks test | designed |
| Live scenario tests, a live dream test; findings in tests/live/RESULTS.md | built (Oct 15) |
| Benchmarks against others: LongMemEval-S, CL-Bench, the fork test, interleaved tasks (Flash only) | next (§17) |
| Avy as an agent: web search, a terminal, acting | later (§13) |
| The real-scale test: years of Claude conversations built into memory | ready to run (his to start) |
| Proactivity | later |

## 16. Open decisions (his to make)

Each of these blocks something in §15. The trade-offs are in ARCHITECTURE.md.

1. **How the library becomes knowledge.** Passages are searchable now. Writing knowledge from them needs:
   - *Who said it*: a node from a paper's words isn't "said by him" or "said by Avy". A new origin ("from a
     source", with the source named)? Or his own documents count as his words, others' as a source's?
   - *Evidence*: nodes would cite passage spans the way they cite message spans (a second kind of evidence).
   - *When*: written as soon as a source is added (cost grows with size), on demand, or by dreaming?
   - *Conversations from elsewhere*: today the Claude history builds into **its own memory file** (time
     order), and also sits in the main library as passages. Should it instead be written into the main
     memory as a source, so there's one memory?
2. **Avy's own words in memory.** In idea-heavy conversations her elaborations outnumber his ideas (live
   tests: 29 "Avy said" nodes to 25 of his), crowd retrieval, and her ideas can come back phrased as his
   threads. Options: cap her nodes per stretch, keep only what he engaged with, weigh them down in recall, or
   keep them as they are and fix it at answer time. *Also from the live tests:* an idea of hers that he
   took up is stored as his ("Shreyas will try Sunday batch cooking", because he said those words), so "which
   ideas were mine?" can list it as his. Who *said* something and whose *idea* it was are different, and
   only the first is recorded.
3. **Search in thinking**: replace the pre-search entirely, or keep a quick pre-search as a starting point
   and let thinking search further?
4. **Internal memory's first build**: the thought graph first (conclusions/commitments/suspicions from her
   saved reasoning), or the fixed slots first (preferences and character notes)? *Evidence from the live
   tests (tests/live/RESULTS.md):* standing preferences said once (a tl;dr line, metric units) were lost on
   questions whose search didn't bring them up, and his own birth date wasn't found for "how old will I be?"
   in one of two runs (two of three setups said he'd never told her). Both are what always-shown slots (a preferences note, and
   a core of who he is) are for. On the other side, a plan that lived only in her own reply was rebuilt
   wrongly when search missed it, which is what the thought graph (her plans and commitments) is for.
5. **Dreaming's scope**: also re-read old conversations to write what the first pass missed, and merge
   near-duplicate nodes? (Changes existing knowledge more aggressively.)
6. **Forgetting from the library**: the library keeps what it's given. Should he be able to take a source
   back out (something added by mistake), against "never lose the original"?
7. **How much Think writes.** Six weeks of conversation (120 messages) became 242 nodes, 75 of them her own
   inferences, and 1,029 connections. Many inferences are broad patterns ("outside-set dates are the ones
   that actually get worked to") that turn up in unrelated questions and crowd the note when search is by
   rules. Options: Think writes less and only what's useful for something coming up; inferences count for less
   in recall unless asked for; dreaming merges and retires them; or keep them and let explore filter.
8. **What Avy is best at.** Candidates from Oct 16: long-horizon multitasking (§10), getting better the
   longer you know her (§17), keeping the feel (§8). One of them could become the thing she's built around.
   *His leaning (Oct 16):* long-horizon multitasking is "the door we want to knock on", the one to target and
   call ours; and the evolving persona, a single entity that grows into what you'd want, as what makes it
   sticky.
9. **Tools for Avy**: web search, a terminal, acting on his behalf. When, and with what limits.

## 17. The challenge *(Shreyas, Oct 15–16)*

*"I want to build it better... I want to beat it on a benchmark, but I want to beat it, period."*

Others are building memory for agents, some funded, some ahead in engineering (docs/LANDSCAPE.md). The
challenge Shreyas set: build the best one anyway, **with one cheap model** (DeepSeek-V4.1-Flash), on the
thesis that intelligence is capped by the model but **how much of it gets used is up for grabs**: a modest
model in the right contraption can outperform its size. Building on what's known, not repeating it.

**The direction that ties it together: an agent that gets better the longer you know it.** Plot quality
against months of use: for today's agents the line is flat or falling (long contexts rot, beliefs go stale,
rapport is lost on every new chat). Make Avy's go up. It has measurable parts:
- **Facts**: beat the published memory systems on their own benchmark (LongMemEval-S; Supermemory's engine
  scores 81.6–85.2%, the best published systems 91–95.6%), with Flash as the only model.
- **Learning from experience**: a positive gain on CL-Bench (Berkeley/Snorkel, June 2026), where the best
  system improved about 25% with experience and dedicated memory systems did worse than keeping everything
  in context. That's continual learning as getting better at things, not just remembering them: lessons
  from her own outcomes (what she tried, what happened, what she'd do differently), with evidence.
- **The feel**: a fork test a blind judge can't pass (§8).
- **Many things at once**: the interleaved-tasks test (§10).
- **Unasked relevance**: bringing up what matters without being asked (the allergy test in tests/live).

