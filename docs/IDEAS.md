# Every idea, and every consideration

Everything Shreyas has proposed, asked for, or reasoned about in the conversation that led to Avy, and
the considerations Claude added that he accepted, grouped by theme. Each item says where it stands:

- **built**: in Avy now
- **later**: decided, not built yet ([../LATER.md](../LATER.md))
- **open**: discussed, not decided
- **parked**: belonged to an earlier concept (the game, Ava, the narrator); kept here because it may
  come back
- **dropped**: decided against, with why

The story of when each came up is in [HISTORY.md](HISTORY.md).

---

## The motivation

- **Turn doom-scrolling into productivity.** Time spent scrolling could be time spent directing agents,
  and something would get done in the background. *(the origin; parked as a product, alive as a value)*
- **Learn what you like and adapt.** What makes social media addictive is that it knows eerily well what
  to show next; the system should learn him the same way. *(open: Avy's memory is the base for it)*
- **Take the overwhelm out of his head.** Lists of everything are overwhelming; the agent should hold the
  overwhelm and hand him what he needs. *(open: the reason behind cards, hierarchy and proactivity)*
- **Built for him, not to sell.** *(rule)*
- **Enjoy talking to it.** Tone, length, framing, the occasional "good job" or "we got this", and how easy
  that is to overdo. Only testable by talking to it. *(open: Avy's prompt is short and plain; the real
  tuning needs his use)*
- **Entertained by agents.** He's quitting YouTube and Instagram and wants the agent to fill that space
  productively: something playing while he eats, that he can jump into. *(parked: the narrator, below)*

- **Beat the best, with one cheap model** *(Oct 15–16)*: build better agent memory than what's out there
  (docs/LANDSCAPE.md), measured on others' benchmarks, with DeepSeek Flash as the only model. *"Intelligence
  is capped for a given model... but the extent to which that intelligence is leveraged is still up for
  grabs."* *(open: the direction; VISION §17)*
- **An agent that gets better the longer you know it** *(Oct 16)*: quality rising with months of use, where
  today's agents stay flat or decline. *(open: VISION §17)*
- **Emergent behavior and an artificial mind** *(Oct 15)*: the hope that the structure produces behavior
  nobody wrote, the way ReasoningBank's lessons matured on their own. *(open)*

## How it's built

- **From scratch, one file at a time, written directly, tried after every step.** After Hermes and Ava,
  both built by delegated pipelines nobody understood. *(built: the whole of Avy)*
- **Plans before builds, in clean English, not 20 pages.** He stays in the loop on the architecture.
  *(rule)*
- **Don't freeze structure too early; the build should be intentional.** *(rule)*
- **Not endless small versions either.** Build big coherent pieces, but not one-shot everything.
  *(rule)*
- **Independent changes together, tested; dependent ones not stacked untested.** Two breakages at once
  compound. *(rule)*
- **Concepts from Hermes are fine; no Hermes code.** *(rule)*
- **Never bring up competitors or existing products unless asked.** It kills his interest. *(rule)*
- **Research means real research.** He asked twice whether research had actually been done; findings must
  be tied back to what we change. *(rule)*
- **Version control as forks of ideas.** Keep a version he can return to and rebuild memory differently
  from. *(built: branch `memory-v1`, VERSIONS.md)*
- **Docs that keep the concept**, because conversations get compacted and lose detail: a concept doc,
  a technical spec, and now this. *(built)*
- **The system handles robustness; the model fills in the blanks.** Structure is enforced by code, not by
  hoping the model follows instructions. *(built: the one door, rules, repair loops)*
- **Test against the real model, because the failures that matter are behavioral.** *(built: the
  benchmark)*
- **A test suite decides what "good" is**, including subjective things (tone, length, feel), run many
  times, evaluated as a whole, then fixed; never "find problems" open-ended, which never ends.
  *(built for memory: the benchmark and its judge; tone and feel: open)*
- **Cheap to run: a few cents a day.** DeepSeek V4.1 Flash; local voice. *(built; through Luminal now)*
- **Stay inside Claude's usage limits**: the cheap agent does heavy context work, Claude Code patches.
  *(parked: the Ava workflow)*

## The interface

- **Pretty, his way.** A supplied inspiration; neo-brutalist side panels; the chat bland, off-white,
  terminal-like, a block cursor, a little industrial. Not SaaS slop. *(built)*
- **Markdown the terminal way:** no big headers; code boxes; bold and links lightly. *(built)*
- **A small fun animation**, like a spinning donut but not a donut. *(built: the dot-matrix scope, now
  the living graph's corner)*
- **No useless text**: no flower, no landing-page copy; a dense system card instead. *(built)*
- **Settings in the UI**: the card's dropdowns, and slash commands. *(built)*
- **Slash commands like Claude Code**: a split-terminal panel on the right that narrows as you type, Tab
  completes (with the colon), options the same way, a few words under each name, a line between rows,
  never left in the conversation. *(built)*
- **Look under the hood**: "recalled N" under each reply; click to see what was found and how; click
  through to the exact words. *(built: the inspector, footnotes)*
- **The living graph**: the corner becomes a tiny version of memory; click for a full-page 3D network that
  fits the page's look (textured, not neon), nodes bobbing like something alive, light labels, hover and
  click through to thoughts and the log, Avy's searches lighting up as they happen. *(built)*
- **A UI surprise each round.** *(built: footnotes, chapters, the live "mind" line, the searching line)*
- **Cards, one at a time, priority ordered**, with hierarchy and layers of abstraction; one page, white
  space, a mic and a chat bar; other views (calendar, everything) available but not primary.
  *(parked: from Ava; the natural shape for proactivity in Avy)*
- **Tasks, calendar, and what the agent plans**, with checkboxes, not only a text box. *(later, with
  proactivity)*
- **Show which agent is talking** and let him follow along visually (like Synapse did). *(parked: the
  narrator)*
- **Everything Avy saves stays in her folder.** *(built: data/)*
- **One command to pull, install new requirements and run.** *(built: README)*
- **Dark mode, well executed**: the same paper-and-ink aesthetic in the dark (warm near-black paper,
  cream ink), no contrast failures anywhere, hover states included; follows the system or a toggle.
  *(built Oct 15: `/theme:`, the moon button; the page tests audit every visible text's contrast in both)*
- **Sound effects**: a message sent, a button clicked, a node touched, a swish when the graph turns, a
  reply or notification arriving. *(built Oct 15: synthesized in the page, no audio files; `/sounds:`
  on, soft or off)*
- **See her thinking**: the chain of thought behind each reply, collapsible, kept with the message.
  *(built Oct 15: "thought for Ns" above the reply; saved in its own append-only table; in exports)*
- **New features for Avy's page as she grows** *(Oct 16)*: part of the exploration he wants run. *(open)*
- **A looking glass**: one place to watch everything loading into memory and the mind working: progress,
  how many done, ETA, errors, the state of memory. *(built Oct 15: the Glass button, `/glass`)*

## Voice

- **Voice in and out, as human as possible**, cheap, local where possible. *(built: faster-whisper and
  Kokoro)*
- **Push-to-talk, not a VAD**: hold Space, let go when done; press again to cut in; double-tap to lock for
  long talks. *(built)*
- **Never lose a recording**: kept on disk as it's spoken, temporary, surviving a crash, retranscribable.
  *(built: data/recordings, `/retry`)*
- **Dictation by default; live conversation as a toggle.** *(built: `/live:`)*
- **Voice never constrains memory design.** Thinking and deep search are allowed even if replies are
  slower. *(rule)*
- **Pipecat**: tried at his request, dropped for a smaller custom pipeline. *(dropped: too many moving
  parts, slower)*
- **Wispr for input, a commercial voice for output**: from the Ava plan. *(dropped: local models instead,
  for cost)*

## Memory: the core

- **Infinite context.** No "new chat": every message starts fresh with the right context appended,
  pulled from the complete record. The constraint is not flooding the context window, not cost.
  *(built)*
- **The log is ground truth**: every message, both sides, never edited or deleted. *(built)*
- **Not summaries: pointers.** Every piece of knowledge points at the exact words it came from, so
  there's never drift; to get the verbatim around something, find it, follow the pointer. *(built:
  evidence, checked by code)*
- **Corrections chain, never overwrite**: the newest version surfaces, the old ones stay reachable. *(built)*
- **A network by reference, like Wikipedia**: entries link to related entries, not just the log; new
  things reference old ones instead of restating them; a chain of concepts, not only accountability.
  *(built: v1 links, then v2's network)*
- **Three layers**: log, knowledge, network. *(built)*
- **Organic and self-organizing**: related things densely connected, unrelated things sparsely; hubs;
  long-range bridges; the model builds it, repeatedly, not once at birth. *(built: Write plus Connect and
  Think at quiet times)*
- **Self-explaining**: follow every link and you read all of it; the starting point decides what you
  learn about, the radius how much. *(built: the network has no islands by design; measured in health)*
- **Recall by association**, one thing reminding of another. *(built: walking the network)*
- **Thinking, not only transcribing**: patterns, ideas as knowledge, her own conclusions. *(built: Think)*
- **Light classification by reliability, not types**: fact vs inference, inference upgradable to fact,
  ideas as their own thing. *(built: shapes and origins)*
- **Hubs form naturally**, including unnamed projects, many of them, never rewarded. *(built: a thing
  node is easy to make; hubs are discounted in search)*
- **The network is the entity**: what it knows today and how it fits together. *(the idea behind v2)*
- **Connections have reasons and strength, from many sources, strengthening with use and fading
  without it; history kept.** (From the other agent's analysis, which he passed on.) *(built: supports)*
- **Inferences rest on things he actually said**, never on inferences alone, the way Hermes never
  summarized summaries. *(built: the basis rules)*
- **Incognito**: a separate conversation that reads all memory, writes none, has its own temporary
  memory, and is deleted afterward. *(built)*
- **Dials for how much context**: recent messages 0 to all; recall depth. *(built: `/window:`,
  `/recall:`)*
- **Switches for each kind of search**, so keyword matching can't hide what structure does; both off
  means no memory. *(built: `/words:`, `/meaning:`, `/explore:`)*
- **Internal and external memory; active and passive storage.** What she was told and what she thought
  privately, kept apart; what's held in mind versus what sits on the shelf until something calls it.
  *(open: his to design, iteratively; the library is the first passive shelf, and her saved thinking the
  first record of internal thought, but neither is wired into the network yet. VISION.md §16)*
- **The feel of a long conversation, kept** *(Oct 16)*: the reason you don't want to start a new chat:
  surface, stance, a shared world of coined names, anticipation, momentum. Ideas: replies that landed as
  examples, a shared lexicon, his corrections as lessons about manner; measured by the fork test.
  *(open: VISION §8)*
- **Learning from what happened** *(Oct 16)*: continual learning as getting better at things, not just
  remembering: lessons from her own outcomes, with evidence. Measured by CL-Bench's gain. *(open: VISION §17)*
- **Dreaming**: long, quiet stretches (about 8 hours, thinking at max) spent forming connections and
  re-indexing, not answering. *(built Oct 15: `/dream`, from the looking glass; sweeps, wanders, checks
  health, wakes when nothing's left or the budget's spent; its real behavior on a big memory is still to
  be watched)*

## Memory: retrieval

- **The two questions**: how a system with no context knows how much it needs; whether it can pull
  everything a task needs without knowing the task. Answer: not reliably at question time; make the
  structure smarter so the "this matters to that" judgments are already there. *(built: reflection)*
- **Search as thinking**: explore (look around) and dig (go deep, branch), the query only a proxy for
  the task, the goal as much relevant context as possible with as little irrelevant explored; the
  AlphaEvolve parallel. *(built: `/explore:`)*
- **Explore and depth as separate dials.** *(open: today one dial, `/recall:`, sets the rounds; each
  round she chooses broad or deep)*
- **Retrieval trains the structure**: connections that led to something used get stronger. *(built:
  `used` supports)*
- **Recall depth decided per message** ("what time is it?" shouldn't dig). *(later)*
- **What's coming up**: dates ahead always in view. *(later)*
- **Ask to confirm** an inference that matters. *(later)*
- **Beliefs over time**: what Avy believed a month ago. *(half built Oct 15: the graph's time slider;
  a "then vs now" page and Avy answering it herself are later)*
- **Graph filters**: only ideas, only what he said, only what changed this week; the path one answer
  took. *(built Oct 15)*
- **Search driven by her thinking chain**: the reasoning she does before answering decides what to look
  up next, instead of one search before she starts. *(later: he said not now; the thinking is saved and
  shown, which is the first piece)*
- **DeepSeek's real thinking levels**: only off, low, high and max exist; the interface offers only those,
  and anything else is routed to the nearest. *(built Oct 15)*

## Memory: real data

- **His whole Claude history as the real-scale test**: do his ideas form distinct hubs? *(built: the
  import; the mind's run is his to start)*
- **Conversations only, not Claude's memories**: memory is built from scratch. *(built)*
- **Chat exports as a source of a rich user model** generally (ChatGPT too). *(built Oct 15 as library
  input: Claude exports, ChatGPT exports, WhatsApp and labeled transcripts are read as conversations with
  who said what; building knowledge from them is his decision, VISION.md §16)*
- **Claude conversations go the same route as everything else**: one door for anything he adds.
  *(built Oct 15: a Claude export dropped in the looking glass goes into the library like any file; the
  older import into the log is still there, his to run)*
- **A US provider for the data's safety**: Luminal. *(built)*
- **Probe big files only through code**: shapes and counts, never the text. *(rule, followed)*

## Files

- **Upload anything**: JSON, Markdown, documents, video, photos; no type limits. *(built)*
- **Read anything**: text of every kind, documents, spreadsheets, slides, PDFs (scanned ones by eye),
  pictures (the model sees them), audio and video (transcribed, frames shown). *(built)*
- **Export and downloads**: files as they came, what Avy read from them, the conversation, memory,
  code blocks as files. *(built)*
- **Upload the Claude export in the page** instead of the command line. *(built)*
- **Memory of what files said**, not just their names. *(half built Oct 15: every file's words are
  passages in the library, searchable by words and meaning and footnoted [p41]; turning them into
  knowledge nodes is held until he decides how, VISION.md §16)*
- **Upload anything, no schema**: conversations, papers, codebases, whole projects, archives, pictures;
  each read by what it is. *(built Oct 15: folders and zips in the looking glass; code by function-sized
  pieces, documents by heading, tables by rows, pictures described)*

## Proactivity (the next pillar)

- **Long-horizon multitasking** *(Oct 16)*: his example of a training run started in the background whose
  insights are lost to compaction or haze by the time it finishes; the hypothesis that Avy can be the best
  at this, because each task keeps its own state and resumes from it. *(open: VISION §10, ARCHITECTURE §9;
  a candidate for what Avy is best at, §16.8)*
- **Avy as an agent of her own** *(Oct 16)*: web search, a terminal, acting. *(later: VISION §13, §16.9)*

- **Proactive, reaching out with what he could do now.** *(later)*
- **Structured awakening**: plan, schedule, stop; wake on triggers or every few hours; no model running
  constantly, dreaming. *(later; dreaming itself is built, started by hand)*
- **Every task is a cron**; the system triggers and executes, maybe with fresh sub-agents. *(later)*
- **Fixed rules plus model-written rules he approves.** *(later)*
- **Planning ahead beats acting on the spot.** *(the principle for it)*
- **Calendar and other connectors for context.** *(later)*

## The five pillars (from earlier conversations)

Unlimited context and verifiability come first (Avy has both); persistence, proactivity and a model of
the user follow. *(two built, three later)*

## Earlier concepts, kept

### The idle game *(parked)*
- An idle game that runs in the background and does real work; you customize your corner over time; no
  levels; one number to grow, machines that do the clicking.
- Agents as cute characters; rooms as corners (tasks, builds, personal, ideation, a pitch room).
- A floating room or house in 3D, seen from above with the near walls and roof open, rotatable; the
  bottom transparent from below.
- Cheap models for the always-on work, smart ones for the interesting parts.
- Good game first, productivity second.

### Swipes and layers *(parked; layers live on)*
- Swipe to approve, reject, go deeper; one line and an image first, details one at a time.
- Agents that research and pitch things to do (a professor, an email to draft, a job).

### The narrator *(parked)*
- A commentator separate from the builder, who understands what the builder is doing.
- Periodic keep-ups from the builder's diff and reasoning, not literally live.
- Pauses when nothing's happening; talks with him in the gaps; "here's an update" when there is one.
- Two voices (what it's doing / why it's doing it); a recap episode for later; "catch me up" and "work
  with me" both; a case board; "before reveal".
- Context via the same infinite-context memory.

### Ava *(parked)*
- The full agent: voice, proactivity, cards, calendar, memory; built by delegation.
- Testing by a cheap agent with a real browser; a test suite written by Claude Code.
