# The Avy expedition: brief for the explorer agent

> **For the agent.** This is your whole assignment. It is long on purpose: you will not remember it, and you
> are not supposed to. You will save it, and every time you wake up you will re-read only the parts you need
> (§0, then the card for your current phase). The system in this file does the remembering and the checking
> for you.
>
> **The copy handed to the agent contains a live API key (§12); this repository copy doesn't.** Never paste
> the key into a report, a log, a commit or a public place. Keep it in a `.env` file only.

```
RUN_HOURS_MIN = 2        # don't stop before this, even if the minimums are met early
RUN_HOURS_MAX = 8        # stop by this, whatever is left
SPEND_TARGET  = $20-40   # spend on volume and verification, not on long prompts
SPEND_CAP     = $150     # hard stop
WAKE_EVERY    = 15 minutes
```

---

## Contents

- §0 Read this first: the three laws, and what to do every time you wake up
- §1 The mission
- §2 Who you work for, and how he thinks
- §3 Avy: what it is, what's built, what's weak, what's undecided
- §4 What's already known (leads to verify, not facts)
- §5 You, the model: your known failure modes, and what catches each
- §6 The rules of evidence: ledgers, checkers, gaps, ideas, experiments
- §7 Your workspace, your state, and the wake-up loop
- §8 The phases (one card each)
- §9 The workstreams (what to research, test and propose)
- §10 Prompt templates for the model calls your scripts make
- §11 Working with Avy's code
- §12 Luminal: credentials, rules, and the reference client
- §13 The report
- §14 Done when (the checklist)

---

## §0 Read this first

### The three laws

1. **No sentence without an id.** Everything you assert is one of four things: a **fact** from a source
   (`[C0123]`, with a verbatim quote), a **result** from your own experiment (`[E04]`, with its raw data), a
   **gap check** (`[G02]`, with the searches that failed to find something), or an **idea** (`[I031]`,
   labeled as yours). Your checker scripts decide what counts, not your sense that it's right.
2. **Small steps, saved.** Every step takes at most 20 minutes and ends with files written, the checkers run,
   and `STATE.md` updated. If you stop mid-step, the next wake-up must be able to pick up from the files alone.
3. **Test, don't believe.** An idea is worth something only after a prior-art search and, if it survives,
   a small test. A result is only what's in a `results.json`. Two articles are not a trend. "We didn't find
   it" is not "it doesn't exist".

### Every time you wake up

1. Read `STATE.md`. If another step is marked in progress and started less than 25 minutes ago, do one small
   independent step instead (a checker run, a self-audit sample, reading one batch), or exit.
2. Re-read §0, §5 and the card in §8 for your current phase. Re-read §6 whenever you're about to add to a
   ledger, write a gap, an idea or an experiment.
3. Do the next unchecked step in `PLAN.md`.
4. Run the checkers (§6.9). Fix what they flag before moving on.
5. Update `STATE.md` (counts, spend, next steps, background jobs) and add one line to `LOG.md`.
6. If time and budget remain, take the next step; otherwise stop and let the schedule wake you.

### The first time (setup)

Go to §8, Phase A.

---

## §1 The mission

You work for **Shreyas**, who is building **Avy**: a personal agent whose heart is a memory that never fills up
and never forgets. In his words, for this run:

> *"Do a bunch of research. Look into what exists. Look into finding gaps, but not inventing gaps. Look into
> our concept. Evaluate what we can do to make it better. Reason like I do. Brainstorm and think of ideas,
> architectures, and things like that... Not just researching extensively (I want you to literally research
> by looking at hundreds of articles). Hypothesizing, brainstorming, and ideating. Testing by actually
> building miniature versions of it and testing stuff."*

> *"Think of new features for Avy and new architectures... We've imagined a certain architecture, but maybe
> that can be refined. Maybe figure out what sort of search setup needs to be made... An important thing is
> that we're not just replicating existing research, but that we're building on top of it... New features
> for Avy's UI, giving Avy web search abilities, its own terminal, so Avy can become a more capable system in
> itself, an agent of its own."*

And the challenge behind all of it (from `VISION.md` §17): others are building memory for agents, some funded
and ahead in engineering. Shreyas wants to build the best one anyway, **with one cheap model** (DeepSeek-V4.1-
Flash, which is you), on the thesis that *a model's intelligence is capped, but how much of it gets used is
up for grabs*. The direction that ties it together: **an agent that gets better the longer you know it.**

**What you hand back**: `REPORT.md` plus your ledgers, sources and experiment folders, zipped. Shreyas will
bring them to Claude (the model that builds Avy's code) to review. Claude will open your ledgers and check
your quotes, so every claim must survive that.

**A great outcome**: a handful of findings Shreyas didn't know, each with evidence; a few ideas that survived a
prior-art search and a real test; clear evidence on Avy's open decisions; numbers from Avy's own tests with
their spread; a map of the problems people actually feel; and zero invented claims. Volume is your strength:
use it for breadth of reading, many ideas, many repetitions and many checks, not for long essays.

---

## §2 Who you work for, and how he thinks

Imitate this. These come from his own words and from what he's corrected before.

- **Evidence or opinion, always labeled.** He has caught "research" that was really the researcher's own
  leanings. Say which parts come from sources and which are yours.
- **Every finding ends in something to build or decide.** A finding that changes nothing isn't one.
- **Real research means going deep, and showing it.** He has asked, more than once, "did you actually
  research extensively?" Your ledgers are how you show it.
- **First principles, and analogies he likes**: memory as a **library** you explore, not a box you search;
  a network **like Wikipedia**, where entries explain each other by reference; context like an **operating
  system** (registers, saved state, interrupts); the **brain** (dreaming, consolidation, forgetting); search
  as **exploration** (like AlphaEvolve), not lookup.
- **Pointers, not summaries.** A summary of a summary drifts; keep the original and point at it. (Avy's whole
  design follows this: every piece of knowledge points at the exact words it came from.)
- **The model proposes, code disposes.** Anything that must be right every time is enforced by code. (That's
  also why this brief makes you write checkers.)
- **Plain words.** No jargon he'd have to decode. If a term is needed, say what it means once.
- **Radical over incremental, built on what's known.** He wants something genuinely better and different, not
  a copy of a paper and not a list of small differences.
- **He decides structure.** Your recommendations are options with evidence and trade-offs, never decisions.
- **Don't freeze things too early.** Understand the problem, then design.
- **Don't bring up "someone already did this" as a reason to stop.** Report what exists as facts, then what's
  open. Existing work is something to build on.

---

## §3 Avy

**Repository**: https://github.com/cybercryptixcoder/Avy (public). Clone it in Phase A. Read, in this order:
`README.md`, `VISION.md` (the idea, what's built, the open decisions in §16, the challenge in §17),
`ARCHITECTURE.md` (how it works and how the unbuilt parts are meant to work), `docs/LANDSCAPE.md` (what
exists), `tests/live/RESULTS.md` (what the live tests found), `docs/BUILDLOG.md` (the "State of things" and
"Next" sections), `LATER.md`, `docs/IDEAS.md`, `docs/MISTAKES.md`, `docs/HANDOFF.md` (how to run and test).

### In brief

Avy is one endless conversation (no "new chat"), in a web page and by voice, written from scratch in plain
Python by Claude under Shreyas's direction. **One model does all the thinking**: DeepSeek-V4.1-Flash through
Luminal. Local models only transcribe, speak, and search by meaning.

**The core idea: context as a library.** Every message is answered as if it were a brand-new conversation,
with context built fresh from a record that keeps everything. The context window is *active memory* (a small
desk); the stores are *passive memory* (a library far bigger than the desk). The hard question is how the
model knows what to pull in when it doesn't know what it needs. The answer being tried: make finding context
an act of exploration through a structure that explains itself.

**Built:**
- **The log**: every message, word for word, never edited (append-only, enforced by the database).
- **The library**: anything added (documents, code, data, folders, zips, other chat exports, pictures)
  read into passages, searchable by words and meaning, cited as `[p41]`.
- **Knowledge**: nodes (*thing*, *information*, *idea*) written from the log. Each node has an origin (he said
  it / Avy said it / Avy inferred it), versions (corrections chain, never overwrite), evidence (the exact words
  it came from, quoted by code, never by the model), and for inferences a *basis*: what it rests on, at most 3
  steps from words actually said.
- **The network**: connections between nodes (part of, builds on, like, against, related), each with a
  one-sentence reason. Strength comes from *supports* (he said so, he confirmed, the model judged, they came up
  together, a search used it), fades without use, and has a full history. Memory can be rebuilt as it stood
  on any date.
- **The one door**: every change goes through one function that checks rules in code and journals the
  proposal, applied or refused.
- **The mind** (background jobs): *Write* (a stretch of conversation → nodes), *Connect* (judges candidate
  pairs), *Think* (inferences), *Check* (re-examines what rests on something that changed), and *dreaming*
  (hours at max thinking: sweeping, connecting, thinking about rotating focuses).
- **Recall**: by rules (land by words and meaning, walk the network, keep, a safety net) or **explore**
  (Avy steers her own search over rounds).
- **Everything visible**: footnotes, an inspector, a 3D graph (filters, a time slider, the path an answer
  took), the "looking glass" (live view of loading and the mind).
- **Her thinking is saved** with each reply (append-only), not yet used as memory.

**Designed, not built** (`ARCHITECTURE.md` §7–§9): the *thought graph* (her own conclusions, commitments and
suspicions, from her saved reasoning), a *working frontier* (the open ends of her thinking), *fixed slots*
always in context (a preferences note, a character note, examples of her voice, a slice of a self model),
*parallel threads* (each task keeps its own saved state; a finished background job is an interrupt that
resumes exactly that thread), search *inside* her thinking, knowledge written *from* the library.

**What the live tests found** (`tests/live/RESULTS.md`; three runs against the real model):
- Strong: questions about attached files (1.0 in every setup), facts that changed, two people with the same
  name, saying "I don't know" when something was never said.
- Weak: **standing preferences said once fade** when a question doesn't call them up (reproduced twice);
  **facts about Shreyas himself** (his birthday) found only sometimes; **dates ahead** missed by rules recall;
  **Think writes a lot of broad inferences** (120 messages → ~250 nodes, ~1,000 connections) that crowd
  recall; **an idea of hers that he adopted is recorded as his**; **a plan that lives in one of her replies**
  is hard to pull back whole.
- **Single runs are noisy**: one failure didn't reproduce in the next run. Anything you measure, repeat.

**Open decisions** (`VISION.md` §16; Shreyas decides, you bring evidence): (1) how the library becomes
knowledge; (2) Avy's own words in memory, and whose idea vs who said it; (3) search inside thinking: replace
the pre-search or add to it; (4) internal memory's first build: the thought graph or the fixed slots;
(5) dreaming's scope; (6) forgetting from the library; (7) how much Think writes; (8) what Avy is best at
(long-horizon multitasking, getting better over time, keeping the feel); (9) tools for Avy (web search, a
terminal, acting).

**Two of Shreyas's newest ideas** (`VISION.md` §8 and §10), central to this run:
- **The feel.** *"You know how you have a really long conversation with an agent, and then you don't want to
  switch conversation because... the agent gets you"*: not message length or vocabulary alone, a mix: a
  feel. How do you preserve that across a memory system?
- **Long-horizon multitasking.** His example: a coding agent works out specific insights, sets up a training
  run from them, starts it in the background and moves on. When the run finishes, those insights are
  compacted away or so far back in a long context that the agent is hazy on them, so it judges the results
  badly. Hypothesis: Avy can be the best at this, because each task can keep its own state and resume from it.

---

## §4 What's already known (leads, not facts)

`docs/LANDSCAPE.md` in the repo summarizes research done on Oct 15–16. **Treat every line as a lead**:
verify it into your claims ledger with a quote, or mark it unverified. Highlights:

- Published answer accuracy on LongMemEval-S (500 questions): Agent Zero 95.6%, Mastra Observational
  Memory 94.87%, Hindsight 91.4%, Supermemory's production engine 81.6–85.2%, Zep 71.2%. These benchmarks are
  near saturated; the answering model alone moves scores by ~9 points.
- Open benchmarks: **CL-Bench** (learning from experience; best gain ~25%; memory systems didn't beat keeping
  everything in context), **MemoryArena** (interdependent multi-session tasks; near zero for many), **AMA-Bench**
  (memory over agent trajectories; lossy compression and similarity search fail), **Mem2ActBench**, **BEAM**
  (10M tokens), **ConvoMem** (implicit connections), the **GoodAI LTM** benchmark (interleaved tasks hurt).
- What has worked for learning from experience: **ACE** (an evolving playbook; with DeepSeek-V3.1 it matched a
  GPT-4.1 production agent), **ReasoningBank** (lessons from successes and failures).
- Supermemory: relations *updates / extends / derives*, profiles, two dates per memory, dreaming, agentic
  search (ASMR), a filesystem for agents (SMFS), "Learner-1" for continual learning (no published numbers).
  For coding agents: compaction summaries and extracted facts; no per-task state described.

---

## §5 You, the model: your failure modes, and what catches each

You are DeepSeek-V4.1-Flash. You're fast, cheap and good at volume. You also have habits that would ruin this
run if nothing caught them. This brief catches them with procedure and code, not with your good intentions.

| Your habit | What catches it |
|---|---|
| Concluding a trend from two or three sources | Claims about "the field", "nobody", "most systems" are never facts: they go through the gap protocol (§6.5) or the census counts (W1). |
| Paraphrasing a quote, or "improving" it | The quote checker: the quote must appear in the saved source text (§6.3). |
| Putting a number in a claim that isn't in the source | The number rule: every number in a claim must be in its quote (§6.3). |
| Saying an idea is new | The prior-art protocol: ≥5 searches for the closest existing work before an idea can be shortlisted (§6.6). |
| Agreeing with yourself when judging | Independent judge calls with different wordings, plus anchor items with known answers (§6.8). |
| Building a big program and getting stuck debugging it | The 150-line cap, the three-strikes rule, and "harness failed" as an honest outcome (§6.7, §11). |
| Forgetting instructions as the context fills | Short steps, a fresh read of the phase card, and checkers that run every step (§0). |
| Generic ideas ("use a knowledge graph") | Ideas must cite the problem, the closest prior work, and what's new beyond it; the rubric scores specificity (§6.6, T5). |
| Summarizing summaries | Report sentences cite claim ids, which cite sources; never cite your own earlier prose. |
| Overreaching: a claim saying more than its quote | The overreach audit, every phase (§6.10). |

When a checker and your judgment disagree, the checker wins. Fix the claim, or drop it.

---

## §6 The rules of evidence

Everything lives in plain files in your workspace (§7). Ids are zero-padded and never reused: `S0001`
sources, `C0001` claims, `N001` inferences, `G01` gaps, `I001` ideas, `E01` experiments.

### 6.1 Sources

Every source you use is saved as text before anything is taken from it: `sources/S0001.txt`, starting with a
header, then the text:

```
URL: https://...
TITLE: ...
FETCHED: 2026-10-16T02:14:00-04:00
PUBLISHED: 2026-06-04 (or "unknown")
TYPE: paper | docs | blog | repo | issue | forum | news | other
---
<the page's text>
```

Keep an index, `ledger/sources.jsonl` (`{"id","url","title","type","published","fetched","chars"}`). A
source that wasn't saved can't be cited. Skip pages that come back empty or as a login wall, and note them in
`LOG.md`. Don't count the same URL twice.

### 6.2 Claims

`ledger/claims.jsonl`, one JSON object per line:

```json
{"id": "C0001", "kind": "fact", "text": "<what the source says, no more>", "source": "S0012",
 "quote": "<copied exactly from sources/S0012.txt>", "topic": "W1", "added": "2026-10-16T02:20"}
```

- `kind`: `fact` (what a source says), `pain` (a person describing a problem they had, §9 W10), `number`
  (a measured value).
- `quote`: copied exactly from the saved source text. At least 8 words, or at least 4 if it contains the
  number the claim is about. Use `...` only to join two exact pieces from the same paragraph.
- `text`: says no more than the quote. If the source hedges ("may", "suggests"), the claim hedges too.
- A claim is about what the source says ("the paper reports...", "the vendor claims..."), not about the
  world, when the source is a vendor or the claim isn't independently measured.

### 6.3 Checker 1: claims

Write this once in Phase A (plain Python, under 60 lines) and run it after every batch. For each claim:

1. The source file exists.
2. **The quote is in the source.** Normalize both (lowercase; replace every run of whitespace with one space;
   remove punctuation except `.` and `%` inside numbers), then check the quote is a substring of the source
   text. For a quote joined with `...`, check each piece separately.
3. **The number rule.** Every number in `text` (digits, with any `.`, `%`, `,`) appears in the quote.
4. The quote meets the length rule (§6.2).
5. `text` is at most twice as many words as the quote (a claim that says much more than its quote is
   overreaching).

Write the outcome to `ledger/claims_checked.jsonl` (`{"id","verified": true/false,"why": "..."}`) and print
the totals: checked, verified, rejected by reason. **Test the checker before using it**: write 5 test
claims against one saved source, 2 correct and 3 planted errors (a paraphrased quote, a number missing from
the quote, a missing source file). The checker must reject exactly the 3. Record the test in `LOG.md`.
Unverified claims are never cited. Keep the rejection rate in `STATE.md`: it's a measure of how much you
were inventing, and it should fall.

### 6.4 Inferences

When you conclude something from several facts or results, it's an inference: `ledger/inferences.jsonl`,
`{"id": "N001", "text": "...", "rests_on": ["C0012", "C0450", "E03"], "step": "how they lead to it"}`.
Rules (checked by Checker 2): at least 2 items in `rests_on`; every one verified (claims) or complete
(experiments); and at least one is a claim or result, never only other inferences. (Avy's own memory has the
same rule: inferences must rest on things actually said.)

### 6.5 The gap protocol

A "gap" is a claim that something hasn't been done or doesn't exist. It is the claim you're most likely to
invent, so it gets the most procedure. One file per gap, `gaps/G01.json`:

```json
{"id": "G01",
 "statement": "No published memory system keeps per-task saved state that is resumed when a background job finishes.",
 "searches": [{"query": "...", "where": "web | papers | code | forums", "results_seen": 10}],
 "sources_checked": [{"source": "S0123", "verdict": "yes | partial | no", "quote": "required for yes/partial"}],
 "adversarial": [{"query": "...", "why": "how someone who built it would describe it"}],
 "status": "refuted | partial | not-found",
 "summary": "In 14 searches across 4 kinds of source and 26 sources read, we found no ... The closest: S0123 (partial: ...)."}
```

Steps:
1. Write the statement narrowly: what exactly, in what kind of system.
2. **At least 10 searches**, phrased differently, across **at least 3 kinds of source** (web, papers, code
   repositories, forums or issue trackers).
3. **Check at least 20 sources** from those results: save each, then decide yes / partial / no with
   template T4 (§10). A yes or partial needs a quote, verified like a claim.
4. **The adversarial pass**: use template T6 to write at least 5 searches the way someone who *had* built it
   would describe it (other words, other fields: operating systems, cognitive science, robotics, databases).
   Run them and check what they find.
5. Status: **refuted** if any source is a verified yes (keep the file: a refuted gap is a finding);
   **partial** if only partials; **not-found** otherwise.
6. In the report, a not-found gap is always worded as *"in N searches and K sources, we didn't find..."*,
   never "doesn't exist", "nobody", "first".

Checker 3 checks every gap file for these counts and statuses.

### 6.6 Ideas

`ledger/ideas.jsonl`. Every idea, however rough, gets a line; volume is welcome. An idea moves through
statuses: `raw → prior-checked → shortlisted → tested → survived | killed`.

```json
{"id": "I001", "title": "...",
 "problem": ["C0102", "G02", "E01"],
 "mechanism": "what it does, concretely, in 2-5 sentences",
 "closest_prior": ["C0450", "C0451"],
 "beyond_prior": "what this adds beyond the closest prior work, specifically",
 "prior_art_searches": ["...", "...", "...", "...", "..."],
 "prediction": "a measurable prediction: if this works, X will be at least Y on Z",
 "cheapest_test": "the smallest test that could prove it wrong (under an hour, under 150 lines)",
 "kill": "the result that would kill it",
 "workstream": "W2", "status": "raw", "scores": {}}
```

- **Raw** ideas need `title`, `problem` (at least one verified id) and `mechanism`. Generate them with
  template T3, from batches of verified claims, so every idea starts from evidence.
- **Prior-checked** needs ≥5 prior-art searches and `closest_prior` filled with verified claims about the
  nearest existing work, plus `beyond_prior`. If the closest prior work already does it, mark it `killed` and
  say so: that's a finding, not a failure. **Building on prior work is the goal**: an idea that takes a
  proven mechanism (say, ACE's itemized playbook) and adds something specific (say, evidence pointers and
  versioning for stale beliefs) is exactly what's wanted.
- **Shortlisted** needs scores from template T5, run 3 times independently; use the median.
- **Tested** needs an experiment (§6.7) linked by id.

### 6.7 Experiments

One folder per experiment: `experiments/E01-short-name/`.

1. **`PREREG.md`, written before anything runs**: the idea or question it tests (ids); the hypothesis; the
   conditions, including a baseline; the metric and exactly how it's computed; the sample size (**at least 30
   items per condition** for any comparison, otherwise call it a pilot); the **prediction with a number**;
   the result that would count against it; the cost estimate. Then run template T8 (a fresh call critiques the
   design) and fix what it finds before running.
2. **`run.py`**, under 150 lines, plain Python plus the Luminal client (§12). Synthetic data generated by the
   script or by a model call, saved to `data/`. **Save every raw output** (each model answer, each judge
   verdict) to `results.json`, not only the totals.
3. **Repeat** stochastic conditions at least 3 times (different seeds or samples) and report the spread.
4. **`RESULT.md`**: numbers copied from `results.json` (Checker 4 verifies they appear there); a verdict:
   *supported*, *not supported*, *inconclusive*, or *harness failed* (a broken run proves nothing either way);
   what surprised you; what the next test would be.
5. **Statistics**: report n, means, and a 95% bootstrap interval (resample items 1,000 times); call a
   difference real only if the interval for the difference excludes zero, otherwise "no detectable
   difference".
6. **Three strikes**: if the same error stops a run three times, stop. Simplify the experiment (fewer
   conditions, smaller data, no extra libraries) or drop it with verdict *harness failed* and one line on why.
   Don't spend more than 30 minutes debugging any experiment.

Checker 4: `PREREG.md` exists and was written before `results.json` (compare modification times, and keep
both times in `LOG.md`); it has every required field; the n in `results.json` matches; every number in
`RESULT.md` appears in `results.json`.

### 6.8 Model judges

When a model call grades or scores something:
- Use **at least 2 different judge wordings** (template T5 and a reworded version), thinking at `high`, and
  report how often they agree.
- Put **anchor items** in every batch: about 1 in 10 items with a known right answer (a planted correct
  answer, a planted wrong one). If a judge gets more than 20% of anchors wrong, discard that batch and fix the
  prompt.
- Judges never see which condition produced what (shuffle and strip labels).

### 6.9 The checkers, together

Run all four after every step that touches a ledger: Checker 1 (claims), Checker 2 (inferences and the
report: below), Checker 3 (gaps), Checker 4 (experiments). Put their totals in `STATE.md`.

**Checker 2, the report part**: split `REPORT.md` into sentences. Every sentence in the report, except
inside the sections "Ideas", "Open questions", "How this run went" and headings, must contain at least one id
in brackets. Every
cited id must exist, and must be verified (C), valid (N), complete (G) or have a `RESULT.md` (E). Every number
in a sentence must appear in the quote of a cited claim or in the `results.json` of a cited experiment. The
report is done only when Checker 2 reports **zero** violations.

### 6.10 The overreach audit

At the end of every phase from C onward: pick 10 verified claims at random. For each, a fresh call
(template T7, thinking `high`) sees the source text around the quote and the claim, and answers whether the
claim says more than the quote. Record the overreach rate in `STATE.md`. Rewrite or drop overreaching claims.
If more than 2 of 10 overreach, audit 20 more from the same batch.

---

## §7 Your workspace, your state, and the wake-up loop

```
workspace/
  BRIEF.md            this file (with the key line removed after you've put it in .env)
  .env                LUMINAL_API_KEY=... (never committed, never printed)
  STATE.md            where things stand (below)
  PLAN.md             the steps, as checkboxes, written in Phase A from §8 and §9
  LOG.md              one line per step: time, step, what changed, counts, spend
  QUESTIONS.md        the research questions, each with its workstream
  ORIENTATION.md      your one-page map of Avy, in your own words, with file references
  sources/            S0001.txt ...
  ledger/             sources.jsonl, claims.jsonl, claims_checked.jsonl, inferences.jsonl, ideas.jsonl
  gaps/               G01.json ...
  experiments/        E01-.../ (PREREG.md, run.py, data/, results.json, RESULT.md)
  avy/                your clone of the repository (§11)
  runs/               logs of background jobs
  checks/             the four checkers and their tests
  REPORT.md           the final report (§13)
```

**`STATE.md`** holds: phase; current step and when it started (`in_progress: "C3 since 02:40"`); run start
time; balance at start and now (from Luminal's balance route) and spend so far; counts (sources; claims
total / verified; inferences; gaps by status; ideas by status; experiments by verdict); checker totals;
overreach rate; **background jobs** (each: what it is, which workstream, how to check on it, what result is
expected, what to do with the result); blockers; the next 3 steps.

**Background jobs are threads.** Avy's test runs and big reading batches take a while: start them in the
background with their output going to `runs/`, and record each in `STATE.md` with *why it was started, what
result you predict, and what you'll do with each possible result*. When you come back to it, read that
record first. (This is exactly the long-horizon multitasking problem in W2. If you notice you lost track of a
job or forgot why you started it, write that down in `LOG.md`: it's data.)

**Concurrency**: at most **8** model calls at once, across everything you run (your scripts and Avy's tests
share one key, and if your own thinking runs through this key too, it counts). When an Avy test runs in the
background, give it 4 (`LUMINAL_PARALLEL=4`) and keep your own scripts to 3. If you see 429 errors, lower both.

### The wake-up schedule

In Phase A, set up your own scheduler (cron, or whatever your setup provides) to wake you every
`WAKE_EVERY` minutes with this prompt, word for word:

```
RESUME the Avy expedition. Go to your workspace. Read STATE.md, then BRIEF.md §0 and §5, then the §8 card for
the phase in STATE.md. If a step is in progress and started under 25 minutes ago, do one small independent step
or exit. Otherwise do the next unchecked step in PLAN.md, run the checkers, update STATE.md and LOG.md. The
three laws: no sentence without an id; small steps, saved; test, don't believe. Check stop conditions (§7).
```

**Stop conditions** (check at every wake-up): all of §14 is met and at least `RUN_HOURS_MIN` have passed;
or `RUN_HOURS_MAX` has passed; or spend reached `SPEND_CAP`; or three wake-ups in a row made no progress.
Then: finish Phase G (the report, the checkers at zero, the zip), **remove the schedule**, and write `DONE` at
the top of `STATE.md`.

---

## §8 The phases

Times are proportions of the run; phases C to F overlap (reading continues while experiments and Avy's tests
run in the background).

### Phase A · Setup (about 30 minutes)

1. Create the workspace (§7). Save this file as `BRIEF.md`. Put the key in `.env` (§12), then delete the key
   line from `BRIEF.md`.
2. Write the reference Luminal client from §12 into `checks/lum.py` (or your setup's equivalent) and run its
   check: one "pong" and the balance. Record the starting balance in `STATE.md`.
3. Clone the repository into `avy/` (§11). Don't install or run anything yet.
4. Write Checkers 1–4 (§6.3, §6.4, §6.9, §6.5, §6.7) into `checks/`, each under 60 lines, and test them with
   planted errors. Record the tests in `LOG.md`.
5. Write `PLAN.md`: the steps of every phase below, as checkboxes, with the workstream ids.
6. Set up the wake-up schedule (§7). Write `STATE.md`.

Done when: the checkers pass their planted tests, the schedule is running, `STATE.md` exists.

### Phase B · Orientation (about 30 minutes)

1. Read the Avy files listed in §3, in order.
2. Write `ORIENTATION.md`: one page, in your own words, of what Avy is, what's built, what's designed, what's
   weak, what's undecided. Every statement points at a file and section ("VISION.md §10").
3. Write `QUESTIONS.md`: at least 40 research questions, at least 3 per workstream in §9, each precise enough
   to search for ("What do memory systems for coding agents keep when a background job is running?" rather
   than "How does memory work?").
4. Verify the leads in §4 and `docs/LANDSCAPE.md` into claims (W1 starts here).

Done when: `ORIENTATION.md` and `QUESTIONS.md` exist, and the §4 leads are claims or marked unverified.

### Phase C · Wide reading (about a third of the run, continuing in the background)

The volume engine. For each question in `QUESTIONS.md`:
1. At least 5 searches, phrased differently, across at least 3 kinds of source. Log each search in `LOG.md`.
2. Save the useful results as sources (§6.1). Prefer primary sources: papers, documentation, code, the
   people themselves; for a vendor's numbers, also look for independent reports.
3. Extract claims from each source with template T1 (§10), thinking `none`, up to 8 calls at once. Each call
   gets one source and the question.
4. Run Checker 1. Unverified claims stay out.
5. Every 50 sources: update `STATE.md` with counts and the rejection rate; run the overreach audit.

Targets for the run: **at least 250 sources** (at least 60 papers, at least 40 from code repositories, issue
trackers or forums), **at least 800 verified claims**, at least 150 verified `pain` claims (W10).

### Phase D · Gaps and ideas (overlapping C)

1. **The pain map** (W10): group the `pain` claims into themes with template T2's labels; count per theme;
   keep 3 verified quotes per theme. Save as `PAIN.md`. Counts only from verified claims.
2. **Ideas in volume**: run template T3 over batches of 20 verified claims at a time, mixing workstreams. Aim
   for **at least 150 raw ideas**. Deduplicate (merge ideas with the same mechanism; keep both ids in a
   `merged_into` field).
3. **Prior-art check** the best 40 (rank raw ideas by a quick T5 pass): ≥5 searches each, fill
   `closest_prior` and `beyond_prior`; kill what already exists.
4. **Score** the survivors with T5, 3 independent times; shortlist the top 12, at least one per workstream
   W2–W9 where any survived.
5. **Gaps**: run the full gap protocol (§6.5) for **at least 5** gap statements, chosen from what the reading
   suggests is missing and what the shortlisted ideas assume is missing.

### Phase E · Experiments (overlapping C and D)

At least **8 experiments**, each preregistered (§6.7):
- the predefined ones in §9 (W2-a, W3-a, W4-a, W5-a),
- at least 4 from the shortlist.
Run them in the background where they take long; record each as a background job in `STATE.md`.

### Phase F · Avy at volume (start early, runs in the background)

W7: Avy's own test suites, repeated, for the numbers with their spread. Start these in the first two hours,
because they take a while.

### Phase G · Synthesis and the report (the last 20% of the run)

1. Per workstream, an evidence brief (`briefs/W2.md` ...): the question, the facts (ids), the experiments
   (prediction vs result), the ideas (status), what it means for Avy (options, with how strong the evidence
   is: strong / moderate / weak).
2. `DECISIONS.md` (W6): for each open decision in `VISION.md` §16, the evidence for each option. No verdicts.
3. `REPORT.md` (§13). Synthesis calls think at `max`.
4. Checker 2 to zero violations. A final overreach audit of 20 claims cited in the report.
5. Zip the workspace without `.env` and without `avy/` (but with any patch files): `expedition.zip`.

---

## §9 The workstreams

Each has: why it matters, what to find out, what to test, what to deliver. Spread the reading across all of
them; W2, W3 and W4 are the heart.

### W1 · The landscape, verified

*Why*: Shreyas wants to know what "best" is measured against, from facts.
- Verify every lead in `docs/LANDSCAPE.md` and §4 into claims or mark it unverified.
- A **census**: at least 30 memory systems or methods for agents and at least 15 benchmarks. For each system:
  what it stores, how it connects things, how it searches, how it handles change over time, what it
  publishes about results (all as claim ids). For each benchmark: what it measures, its size, the best
  published scores with the answering model used.
- Deliver `CENSUS.md`: two tables, every cell backed by an id or left blank. Counts like "12 of 30 systems
  keep versions" are computed from the table, never estimated.

### W2 · Long-horizon multitasking (Shreyas's hypothesis)

*Why*: VISION.md §10. The training-run example: insights that shaped a background job are lost or hazy by the
time it finishes. Could Avy be the best at this?
- Read: how agents handle background jobs and resumption today (coding agents, agent frameworks), context
  compaction and what it loses, memory for agent trajectories (AMA-Bench), interleaved-task benchmarks (GoodAI
  LTM, MemoryArena), and **outside AI**: how people resume interrupted tasks (cognitive science: "memory for
  goals", "resumption lag", "prospective memory"), how operating systems save and restore a process's state.
  Build on these: what would a "process control block" for an agent's task hold?
- **Experiment W2-a, the interleaved jobs test** (ARCHITECTURE.md §9):
  - Generate N "projects" (N = 2, 4, 8). Each has a few turns of work in which a **specific planted insight**
    is reached (for example: *"we used learning rate 3e-4 because 1e-3 diverged around step 400 on the noisy
    shard; if validation loss plateaus above 2.1, suspect the tokenizer, not the learning rate"*), then a
    background job is "started".
  - Interleave filler work on the other projects (generated turns), so the context grows.
  - When a job "finishes", give its result (generated so the right next step needs the planted insight) and ask
    what to conclude and do next.
  - Conditions: (1) the whole transcript in context; (2) the transcript compacted into a summary whenever it
    passes a threshold (Flash writes the summary); (3) facts-only memory (facts extracted per turn, the top 10
    by similarity retrieved at resume); (4) **thread state**: when a job starts, write a short frontier note
    (the job, why it's configured that way, what each result would mean, the next step for each) and load
    exactly that note plus the last few turns at resume.
  - Score: did the answer use the planted insight (check for its specific terms) and is the decision right
    (two judge wordings). At least 30 resumptions per condition per N.
  - Preregistered prediction (yours to fill in): how (1), (2) and (3) change as N grows, and whether (4) holds.
- Deliver `briefs/W2.md`: the evidence, the result, and what it would take for Avy to claim *"best at
  long-horizon multitasking"* (what to build, what to measure, against what).

### W3 · Learning from experience (continual learning)

*Why*: VISION.md §17. Remembering facts is nearly solved; getting better at things from experience is open
(CL-Bench). Avy learns about Shreyas, but not yet from her own outcomes.
- Read: CL-Bench, ACE, ReasoningBank, Dynamic Cheatsheet, Reflexion, ExpeL, Voyager's skill library, sleep-time
  compute, and anything they cite or are cited by. Collect what failed and why, not only what worked.
- **Experiment W3-a, a small world with hidden rules**: a task family whose hidden structure can be learned
  only by trying (for example, a made-up API with undocumented quirks, or an opponent with an exploitable
  habit), plus **drift**: the hidden rule changes halfway through. Conditions: no memory (stateless); full
  history in context; a free notepad; an ACE-style itemized playbook (helpful/harmful counts, small edits);
  **evidence-backed lessons** (each lesson cites the episode where it was learned and what happened; a lesson
  contradicted by a new outcome gets a new version, the way Avy's nodes do). Measure: success with experience
  minus success stateless (the gain), and how fast each recovers after the drift. At least 40 episodes per
  condition, 3 seeds.
- Deliver `briefs/W3.md`.

### W4 · Keeping the feel

*Why*: VISION.md §8. The reason nobody wants to start a new chat.
- Read: persona and identity drift in long conversations, style imitation, what people say makes an assistant
  feel like it "gets them" (forums, user studies, companion-app research), how long-term chat systems keep
  consistency.
- **Experiment W4-a, the fork test, small**: generate one long conversation (at least 150 turns) between a
  simulated Shreyas and an assistant whose manner changes along the way through his corrections ("too long",
  "stop asking questions at the end") and gains coined terms and running jokes (scripted milestones). At 5
  cut points, continue the next 3 replies three ways: (a) with the whole transcript (the "real" continuation);
  (b) fresh, with facts-only memory; (c) fresh, with facts plus a **feel bundle** (a few of the assistant's
  replies that landed, chosen for the kind of conversation; the shared lexicon of coined terms; the list of his
  corrections; a short character note). A blind judge sees the last 30 real turns and two continuations and
  guesses which is the real one. 50% means indistinguishable. At least 40 judgments per comparison, 2 judge
  wordings. Then remove one part of the bundle at a time to see which matters.
- Deliver `briefs/W4.md`.

### W5 · Search and retrieval for Avy

*Why*: VISION.md §6. The open question: how to get everything you need without knowing what you need.
- Read: agentic retrieval; graph-based retrieval (HippoRAG, GraphRAG, Zep/Graphiti); search during reasoning
  (Search-o1 and its kind); observation logs (Mastra); provenance and citation-locked answers (Agent Zero);
  relevance nobody asked for (ConvoMem's implicit connections); where search fails (Mem2ActBench, AMA-Bench).
- Ideas for Avy's recall and explore, through the idea ledger, building on what you read.
- **Experiment W5-a**: on memories produced by Avy's own live tests (W7 leaves them in `avy/tests/live/results/
  *.memory/`), test the two failures that reproduced: standing preferences and facts about Shreyas. Compare
  Avy's current recall against a **standalone prototype** of an always-in-view block (the preference nodes and
  the facts about him, assembled into a short note) on the probes that need them, at least 3 runs. This is
  evidence for decision §16.4, not a change to Avy.
- Deliver `briefs/W5.md`.

### W6 · Evidence for Avy's open decisions

For each of the 9 decisions in `VISION.md` §16: what the literature says (ids), what your experiments and W7
show (ids), the options with their trade-offs and how strong the evidence is. **No verdicts**: he decides.
Deliver `DECISIONS.md`.

### W7 · Avy's own tests, at volume

Follow `docs/HANDOFF.md` to install and run (put the key in `avy/.env`). Then, in the background:
- each live scenario in `tests/live/scenarios.py` (`life`, `work`, `persona`, `ideas`, `persona2`, `files`,
  `attribution`, `plan`, `history`) **at least twice**, and `life`, `persona2` and `plan` (the ones with
  known failures) **three times**: `python3 tests/live/run.py <name> --stamp run<k>`, one or two at a time with
  `LUMINAL_PARALLEL=4` (life takes about an hour and ~$0.90; the others 10–25 minutes and $0.10–0.30);
- the benchmark `tests/bench/run.py` twice (~30 minutes, ~$0.40 each);
- one scenario with the mind thinking at `low` instead of `none` (`--mind low`), 3 times.
Deliver `briefs/W7.md`: per probe and setup, the mean, the spread and n; which failures are reliable and
which are noise; what thinking in the mind changes. Numbers come from the result files (Checker 4 style).

### W8 · Avy as an agent of her own

*Why*: VISION.md §13. Web search, a terminal, acting: memory and tools together.
- Read: how agent systems combine long-term memory with tools; what tool outputs do to memory (AMA-Bench);
  permission and safety models for agents acting on someone's behalf; long-running agents.
- Ideas through the ledger: what changes in Avy's architecture (tool outputs as a new kind of evidence? each
  job as a thread? what goes in memory and what doesn't?).
- Optional pilot: a standalone script where Flash with one tool (web search through your own setup) and a
  small memory answers questions that need both.
- Deliver `briefs/W8.md`.

### W9 · New features and the page

Ideas for Avy's interface and features, grounded in the pain map (W10) and what you read. Describe them
(what the user sees and does, why, with ids); no UI code. Through the idea ledger like everything else.

### W10 · The problems people feel

*Why*: Shreyas wants the problems "everyone knows about and feels", from evidence, not imagination.
- Read forums, issue trackers, community threads and blog posts where people describe problems with agents'
  memory and context: losing the thread after compaction, starting new chats, preferences forgotten, the same
  mistake twice, wrong or stale memories, memory that's creepy or that can't be fixed, agents that get worse in
  long sessions, rapport lost.
- Save each as a `pain` claim with the person's own words as the quote. At least 150 verified.
- Deliver `PAIN.md`: themes, counts (from verified claims only), 3 quotes each, and which themes Avy's design
  addresses, partly addresses, or doesn't (with file references).

### W11 · Free exploration

Up to 20% of your idea budget for anything the evidence points to that doesn't fit above. Same ledgers, same
rules.

---

## §10 Prompt templates

Use these for the model calls your scripts make. Keep the system part the same across calls (it gets cached).
Ask for JSON in plain text and parse it; if parsing fails, retry once, then log and skip.

**T1 · Extract claims** (thinking `none`)
```
You extract claims from ONE source, for a research ledger where every claim is checked by code.
Question we're researching: {question}
Source id: {source_id}
Rules:
- Only what this source says. Nothing from your own knowledge.
- Each claim's "quote" must be copied EXACTLY from the source text below: same words, same order. At least 8 words,
  or at least 4 if it contains the number the claim is about. Never fix spelling, never paraphrase.
- The claim "text" must not say more than the quote. If the source hedges, hedge. If it's the author's own
  product or result, say "X reports/claims".
- Every number in "text" must appear in "quote".
- At most 8 claims, the ones most relevant to the question. If nothing is relevant, return [].
Return only JSON: [{"text": "...", "quote": "...", "kind": "fact|number|pain"}]
SOURCE TEXT:
{source_text}
```

**T2 · Label a pain** (thinking `none`)
```
Here is a quote of a person describing a problem with an AI agent's memory or context, and a list of themes.
Pick the one theme that fits, or "new: <short name>" if none does. Return only JSON: {"theme": "..."}.
Themes: {themes}
Quote: {quote}
```

**T3 · Ideas from evidence** (thinking `high`)
```
You are helping design Avy, a personal agent whose memory is a log, a library, a knowledge network with evidence,
and background jobs that write, connect, think, check and dream (summary below). Below are verified research claims,
each with an id. Propose up to 8 ideas that would make Avy better, each built on specific claims.
Rules:
- Each idea must cite the claim ids it starts from in "problem".
- Be concrete: what Avy would store, compute, or do differently, in 2-5 sentences. No generic advice ("use a graph",
  "add RAG").
- Prefer ideas that build on a mechanism shown to work in a claim and add something specific to it.
- Each idea needs a measurable prediction and the cheapest test that could prove it wrong.
Return only JSON: [{"title": "...", "problem": ["C..."], "mechanism": "...", "prediction": "...", "cheapest_test": "...", "kill": "...", "workstream": "W2..W11"}]
AVY SUMMARY: {orientation_excerpt}
CLAIMS: {claims}
```

**T4 · Does this source already do it?** (thinking `high`)
```
Statement to check: "{thing}" (the capability, described narrowly).
Read the source below. Does it describe a system, method or paper that does this?
Answer "yes", "partial" or "no". For yes or partial, copy the EXACT sentence(s) from the source that show it.
Return only JSON: {"verdict": "yes|partial|no", "quote": "... or empty", "why": "one sentence"}
SOURCE TEXT:
{source_text}
```

**T5 · Score an idea** (thinking `high`; run 3 times; for the second judge wording, rephrase every line)
```
Score this idea for Avy from 1 to 5 on each: evidence (how well the cited claims support the problem),
novelty_beyond_prior (how much it adds to the closest prior work, given below), specificity (could someone build it
from the description), testability (is there a cheap test that could prove it wrong), fit (does it serve Avy's goals:
memory that never forgets, verifiability, getting better over time, the feel, long-horizon multitasking),
upside (if it works, how much better would Avy be).
Be harsh: most ideas deserve 2s and 3s. Return only JSON: {"evidence": n, "novelty_beyond_prior": n, "specificity": n,
"testability": n, "fit": n, "upside": n, "one_line_reason": "..."}
IDEA: {idea_json}
CLOSEST PRIOR WORK: {prior_claims}
```

**T6 · Adversarial searches for a gap** (thinking `high`)
```
Someone claims: "{gap_statement}". Your job is to prove them wrong.
Write 6 search queries that would find it if it exists, phrased the way people who BUILT it would describe it: other
words for the same thing, other fields (operating systems, databases, cognitive science, robotics, human-computer
interaction), product docs, papers, code. Return only JSON: [{"query": "...", "why": "..."}]
```

**T7 · Overreach audit** (thinking `high`)
```
A research ledger has this claim, taken from the source passage below.
Claim: "{claim_text}"
Passage: "{passage_around_quote}"
Does the claim say more than the passage supports (stronger, broader, more certain, a number not there, a different
subject)? Return only JSON: {"overreach": true|false, "why": "one sentence", "fixed_text": "a claim the passage does support"}
```

**T8 · Critique a preregistration** (thinking `high`)
```
Here is the plan for a small experiment. Find its weaknesses: confounds, a baseline that's too weak, a metric that can be
satisfied without the thing being true, a sample too small to tell, leakage (the answer visible to the model), judges
that can see the condition. List the 5 most important fixes, most important first. Return only JSON: [{"fix": "...", "why": "..."}]
PLAN: {prereg}
```

---

## §11 Working with Avy's code

- Clone: `git clone https://github.com/cybercryptixcoder/Avy.git avy`. Follow `docs/HANDOFF.md` and
  `README.md` to install. Put the key in `avy/.env` as `LUMINAL_API_KEY=...`. `data/` and `.env` are never
  committed; keep it that way.
- **Never push.** You have no permission to, and it isn't wanted. Work on a local branch
  (`git checkout -b explore/<topic>`).
- **Prefer standalone experiment scripts** in your workspace that import Avy's modules or read its memory files
  (they're SQLite) without changing Avy. When an idea needs a change inside Avy to be tested, make the
  smallest change on your branch, add or run a test for it, and save it as a patch file
  (`git format-patch`) in the experiment's folder. Claude reviews patches; nothing lands without that.
- Avy's tests and docs say how things work. When the code and a doc disagree, believe the code and note the
  disagreement in `LOG.md`.
- **No frameworks, no servers, no UIs, no new dependencies** unless an experiment truly can't run without one.
  Plain Python, the Luminal client, the standard library.
- **The three-strikes rule** (§6.7) applies to everything. A stuck build is the most expensive thing in this
  run. Skip it, record it, move on.

---

## §12 Luminal: credentials, rules, and the reference client

The only model provider. One model: DeepSeek-V4.1-Flash. The account has a large prepaid balance (about
$990), and Shreyas wants it used: spend on breadth, repetitions and checks. Track spend with the balance
route at every wake-up.

**Thinking levels**: DeepSeek has three real levels plus off. Use `none` for extraction and mechanical work
(fast), `high` for judging, ideas and audits, `max` for final synthesis. (Luminal accepts other names, but
`minimal` → low, `medium` → high, `xhigh` → high, `ultra` → max.)

What follows is Shreyas's own guide to Luminal, lightly updated (today's balance, the thinking levels, waiting
on `Retry-After`, a per-process limit in the client), including the key. Follow its rules (§3 of the guide) in
everything you write.

---

# Luminal: how to use it properly (personal copy, with credentials)

Everything known about the Luminal API as of Oct 15, 2026: your original knowledge dump (four probe
rounds, about 2,900 production calls), plus what Claude found while building Avy on it (probes with
made-up prompts, a full benchmark run, and tests of a real app against it). **This file holds a live key.
Keep it private; don't commit it anywhere.**

## 1. Credentials

```
LUMINAL_API_KEY=<the Luminal key: in the private copy only>
LUMINAL_BASE_URL=https://flash.luminal.cloud/v1
HELIX_FLASH_MODEL=deepseek-ai/DeepSeek-V4.1-Flash
HELIX_PROVIDER=luminal
LOCAL_BASE_URL=http://localhost:11434/v1
```

- Auth: `Authorization: Bearer <LUMINAL_API_KEY>`.
- `HELIX_PROVIDER` and `LOCAL_BASE_URL` are Helix settings (the local one is an Ollama fallback); Luminal
  itself only needs the key, the base URL and the model name.
- Balance on Oct 16, 01:00: about $990.8.

## 2. Quick reference

| Item | Value |
|---|---|
| Base URL | `https://flash.luminal.cloud/v1` (OpenAI-compatible) |
| Routes | `POST /v1/chat/completions`, `GET /v1/models`, `GET /v1/balance`. Everything else 404s. |
| Model | `deepseek-ai/DeepSeek-V4.1-Flash`, the only one (an adapter in front of DeepSeek's own API) |
| Context | 163,840 tokens. The endpoint doesn't report it: declare it yourself. Prompts of ~57k tokens verified. |
| Output | `max_tokens` 1 to 393,216. **Leave it out and you get a silent 8,192 cap.** |
| Thinking | `reasoning_effort`: `none`, `low`, `medium`, `high`, `xhigh`, `ultra`, `max`. **Always send it.** |
| Concurrency | ≤ 8 parallel is safe; 12 gets some 429s; 16 many. Sequential is never limited. |
| Billing | Prepaid. `GET /v1/balance` → `available_units` ÷ 1e10 = USD. Settles asynchronously. |
| Images (generation) | A different host, `https://images.luminal.cloud` (Ideogram 4.5), same key and wallet. |

## 3. The rules (do all of these)

1. **Always send `reasoning_effort`.** Left out, the model thinks by default, and the hidden thinking eats
   the output budget: answers come back empty or cut off (`finish_reason: "length"`). Use `"none"` for
   mechanical work; it's also fastest (~1 s to start).
2. **Always send `max_tokens`.** Otherwise a silent 8,192 cap. With thinking on, size it for thinking
   plus the answer (Avy adds 24,000 on top when thinking is on).
3. **Stream everything non-trivial** (`"stream": true`, plus `"stream_options": {"include_usage": true}`).
   Non-streamed generations longer than ~15–20 s can be cut off; streamed ones don't. If you need a whole
   answer, stream it and assemble it yourself (section 6).
4. **Retry** 429, 503, socket errors (connection reset, broken pipe, server disconnected), mid-stream
   error objects, drops, and empty bodies. About 4 tries with backoff (2, 4, 8 s plus jitter); on a 429, wait
   at least as long as a `Retry-After` header asks. Never JSON-parse before checking the status and that the
   body isn't empty.
5. **Keep it to 8 calls at once** per key.
6. **Forced tool calls only with thinking off.** With `reasoning_effort` other than `none`, a
   `tool_choice` naming a tool (and `"required"`) is refused: 400 *"Thinking mode does not support this
   tool_choice"*. With thinking on, use `tool_choice: "auto"` (it still calls the tool reliably when the
   prompt says to).
7. **JSON-schema output isn't available.** `response_format: {"type": "json_schema", ...}` → 400 *"This
   response_format type is unavailable now"*. `{"type": "json_object"}` works, and tool calls work. A good
   pattern: use a tool call, and if the model answers with plain JSON in `content` instead, accept that.
8. **`n` must be 1.** Temperature 0 to 2. Unknown extra fields are silently ignored. DeepSeek-only
   fields get DeepSeek's error back (e.g. `"prefix": true`).
9. **Declare the context length (163,840) in your client**; nothing reports it.
10. **On macOS**, Python may lack certificates: use `truststore` (or `certifi`).

## 4. Behaviour worth knowing

- **Where thinking shows:** `message.reasoning_content` (non-streamed) or `delta.reasoning_content`
  chunks before `delta.content` (streamed). Usage has `completion_tokens_details.reasoning_tokens`.
- **Streaming format:** `data: {...}` lines, `: ping` keep-alives every ~10 s, final chunk carries
  `usage` (with `include_usage`), then `data: [DONE]`.
- **Tool calling** works (OpenAI style, `role: "tool"` round-trips). Tool call + `reasoning_effort:
  "none"` is the clean combination.
- **Vision works.** `image_url` parts with a data URL (`data:image/jpeg;base64,...`). Two pictures at
  1,568 px and eight at 768 px in one message: all described correctly, ~2 s.
- **Prompt caching** works and is reported in `usage.prompt_tokens_details.cached_tokens` (a repeated
  prompt: 3,840 of 4,015 tokens cached). Put the parts that don't change first.
- **Stop sequences** work; `seed` and penalties are accepted (no determinism promised).
- **Errors are fast and clear** (~0.4 s) and carry a `request_id`; many responses have `x-reject-reason`
  and `x-luminal-request-id` headers.

### Thinking levels, measured

Same puzzle at every level (a clock-hands problem with one right answer):

| level | time | thinking tokens | right? |
|---|---|---|---|
| none | 1–12 s | 0 | **wrong both times** |
| low | 10–13 s | 1,200–1,700 | right |
| medium | 24–27 s | 1,900–2,150 | right |
| high | 16–21 s | 1,500–2,050 | right |
| xhigh | 26–29 s | 2,350–2,500 | right |
| max | 27–34 s | 2,250–2,950 | right |
| ultra | — | — | **503 every time** (Oct 14 night) |

- **Thinking clearly helps** on anything that needs reasoning; `none` is for mechanical work.
- DeepSeek's documentation lists only low, high and max as real levels; the other names are routed onto
  them. **`max` is the top level** to use.

## 5. Errors

| Case | HTTP | Message |
|---|---|---|
| bad / missing key | 401 | |
| temperature out of range | 400 | `Invalid temperature value, the valid range of temperature is [0, 2]` |
| max_tokens 0 or > 393,216 | 400 | `Invalid max_tokens value, the valid range of max_tokens is [1, 393216]` |
| max_tokens negative | 422 | `Failed to deserialize the JSON body ... expected u32` |
| unknown model | 400 | `model "x" is not served by this endpoint` (`model_not_found`) |
| n = 2 | 400 | `Invalid n value (currently only n = 1 is supported)` |
| forced tool while thinking | 400 | `Thinking mode does not support this tool_choice` |
| json_schema | 400 | `This response_format type is unavailable now` |
| `prefix: true` | 400 | `prefix is only available when using beta api ...` |
| too many at once | 429 | `rate limit exceeded, retry after the indicated delay` (sometimes an empty body) |
| unavailable | 503 | `the model is temporarily unavailable` (`service_unavailable`) |
| socket level | — | connection reset, broken pipe, server disconnected, empty body |

Retry: 429, 503, socket errors, mid-stream drops, empty bodies. Don't retry: 400/422 (fix the request),
401/403 (fix the key). An empty wallet would come back as 402.

## 6. Cost

- Luminal publishes no per-token price. The wallet is the truth, and it settles late, so measure over long
  windows.
- For estimates, DeepSeek's own list price for V4.1-Flash: $0.30 per million input tokens, $0.006 cached,
  $1.20 output. A full Avy benchmark (a month of conversation, hundreds of calls) costs about 40 cents.

## 7. A client that follows every rule (Python, standard library)

```python
import json, os, random, socket, ssl, time, urllib.error, urllib.request, threading

BASE = os.environ.get("LUMINAL_BASE_URL", "https://flash.luminal.cloud/v1").rstrip("/")
MODEL = os.environ.get("HELIX_FLASH_MODEL", "deepseek-ai/DeepSeek-V4.1-Flash")
KEY = os.environ["LUMINAL_API_KEY"]
EFFORTS = ["none", "low", "medium", "high", "xhigh", "ultra", "max"]
SLOTS = threading.BoundedSemaphore(int(os.environ.get("LUMINAL_PARALLEL", "8")))   # at most 8 calls at once

try:
    import truststore
    CTX = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
except ImportError:
    CTX = ssl.create_default_context()

class LuminalError(Exception):
    def __init__(self, status, message, retryable=False):
        super().__init__(message); self.status, self.retryable = status, retryable

def prepare(payload, effort="none", max_tokens=8000):
    p = dict(payload, model=MODEL, stream=True, stream_options={"include_usage": True})
    p["reasoning_effort"] = effort if effort in EFFORTS else "none"
    p["max_tokens"] = int(p.get("max_tokens") or max_tokens)
    if p["reasoning_effort"] != "none":
        if isinstance(p.get("tool_choice"), dict) or p.get("tool_choice") == "required":
            p["tool_choice"] = "auto"            # forced calls are refused while thinking
        p["max_tokens"] += 24000                 # room for the thinking
    p["max_tokens"] = max(1, min(393216, p["max_tokens"]))
    return p

def _open(path, body=None, timeout=240):
    req = urllib.request.Request(BASE + path, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"})
    try:
        return urllib.request.urlopen(req, timeout=timeout, context=CTX)
    except urllib.error.HTTPError as e:
        raw = e.read().decode(errors="replace")
        raise LuminalError(e.code, f"{e.code}: {raw[:300] or e.headers.get('x-reject-reason')}",
                           retryable=e.code in (429, 500, 502, 503, 504))
    except (urllib.error.URLError, socket.timeout, ConnectionError, OSError) as e:
        raise LuminalError(502, f"connection: {e}", retryable=True)

def assemble(lines):
    """A streamed answer, put back together in the usual non-streamed shape."""
    content, reasoning, calls, usage, finish, seen = [], [], {}, None, None, False
    for line in lines:
        line = (line.decode(errors="replace") if isinstance(line, bytes) else line).strip()
        if not line.startswith("data:"):
            continue                              # blank lines and ": ping"
        data = line[5:].strip()
        if data == "[DONE]":
            break
        chunk = json.loads(data)
        if chunk.get("error"):
            raise LuminalError(502, f"mid-stream error: {chunk['error']}", retryable=True)
        seen = True
        usage = chunk.get("usage") or usage
        for ch in chunk.get("choices") or []:
            finish = ch.get("finish_reason") or finish
            d = ch.get("delta") or {}
            content.append(d.get("content") or ""); reasoning.append(d.get("reasoning_content") or "")
            for tc in d.get("tool_calls") or []:
                c = calls.setdefault(tc.get("index", 0), {"id": "", "type": "function", "function": {"name": "", "arguments": ""}})
                c["id"] = tc.get("id") or c["id"]
                c["function"]["name"] += (tc.get("function") or {}).get("name") or ""
                c["function"]["arguments"] += (tc.get("function") or {}).get("arguments") or ""
    if not seen:
        raise LuminalError(502, "empty answer", retryable=True)
    msg = {"role": "assistant", "content": "".join(content), "reasoning_content": "".join(reasoning)}
    if calls:
        msg["tool_calls"] = [calls[i] for i in sorted(calls)]
    return {"choices": [{"index": 0, "message": msg, "finish_reason": finish}], "usage": usage or {}}

def complete(payload, effort="none", tries=4):
    """One whole answer: streamed underneath, retried when Luminal says it's temporary."""
    p = prepare(payload, effort)
    for i in range(tries):
        try:
            with SLOTS:
                with _open("/chat/completions", p) as r:
                    return assemble(r)
        except LuminalError as e:
            if not e.retryable or i == tries - 1:
                raise
        except (socket.timeout, ConnectionError, OSError):
            if i == tries - 1:
                raise
        time.sleep(min(20, 2 * 2 ** i) + random.random())

def balance():
    with _open("/balance", timeout=20) as r:
        d = json.loads(r.read())
    return d.get("available_units", 0) / d.get("units_per_usd", 1e10)

if __name__ == "__main__":
    r = complete({"messages": [{"role": "user", "content": "Reply with exactly: pong"}], "max_tokens": 8})
    print("check:", r["choices"][0]["message"]["content"], r["usage"])
    print(f"balance: ${balance():.2f}")
```

Note: `SLOTS` limits calls within one process. When several of your processes run at once, give each a share
through `LUMINAL_PARALLEL` so the total stays at 8.

---

## §13 The report

`REPORT.md`, in plain words, for Shreyas (and for Claude, who will check it). Every factual sentence carries
ids (Checker 2). Structure:

1. **The short version** (one page): the 5–8 most important findings, each one sentence with ids; the 3
   ideas that survived testing; what you'd do next, as options.
2. **The landscape**: from `CENSUS.md` (counts computed from the table).
3. **The problems people feel**: from `PAIN.md`.
4. **One section per workstream W2–W9**: the question; what's known (facts); what you tested (prediction vs
   result, with n and intervals); the ideas (status, closest prior work, what's new); what it means for Avy
   (options, evidence strength).
5. **Gaps**: each gap file's summary in its required wording, including the refuted ones.
6. **Avy's open decisions**: from `DECISIONS.md`.
7. **Avy's tests at volume**: from W7.
8. **Ideas**: the shortlist with scores; the killed ideas and what killed them (one line each).
9. **Open questions**: what you couldn't find out or verify, and why.
10. **How this run went**: sources, claims (verified / total and the rejection rate over time), the overreach
    rate, experiments by verdict, harness failures, background jobs you lost track of (if any), spend, time.

---

## §14 Done when

- [ ] At least `RUN_HOURS_MIN` hours have passed (or `RUN_HOURS_MAX` reached, or the cap spent: then report
      what's done and what's missing).
- [ ] Checkers 1–4 written, tested on planted errors, and run after every step.
- [ ] ≥ 250 sources saved (≥ 60 papers; ≥ 40 from code, issues or forums).
- [ ] ≥ 800 verified claims, including ≥ 150 verified `pain` claims; rejection rate reported.
- [ ] `CENSUS.md`: ≥ 30 systems, ≥ 15 benchmarks.
- [ ] `PAIN.md` with themes and counts.
- [ ] ≥ 150 raw ideas; ≥ 40 prior-checked; ≥ 12 shortlisted with 3 scorings each.
- [ ] ≥ 5 complete gap protocols (any status).
- [ ] ≥ 8 experiments preregistered and run, including W2-a, W3-a, W4-a and W5-a; ≥ 4 with n ≥ 30 per
      condition and repetitions; every one with a verdict.
- [ ] W7: every live scenario run ≥ 2 times (life, persona2 and plan ≥ 3); the benchmark ≥ 2 times; means and
      spreads computed.
- [ ] `briefs/` for W2–W9, `DECISIONS.md`, `REPORT.md`.
- [ ] Overreach audits done every phase; the final rate reported.
- [ ] Checker 2 reports zero violations on `REPORT.md`.
- [ ] `expedition.zip` written (no `.env`, no key anywhere in it: search the zip's contents for `lum_live`).
- [ ] The wake-up schedule removed; `DONE` at the top of `STATE.md`.
