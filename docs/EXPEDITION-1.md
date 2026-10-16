# Expedition 1: what came back, and what holds

The explorer (DeepSeek-V4.1-Flash on Luminal, briefed by [EXPLORER-BRIEF.md](EXPLORER-BRIEF.md) and
[WORKING-WELL.md](WORKING-WELL.md)) ran on Oct 16 from 02:21 to 12:35 EDT, about ten hours and $10–12 of
experiment calls. It handed back a report, the open decisions with evidence, eight workstream briefs, a pain
map, a census of memory systems, a run-integrity ledger, a ledger of 1,752 sourced claims, five experiments
and five gap checks (an archive of 879 files). The archive is Shreyas's and isn't in this repo; the ids below
(C0015, E01, G05, W7) point into it.

Claude checked it on Oct 16 by going under the prose: every claim's quote re-found in its saved source by
code; every report sentence that cites a claim read against that claim's quote (23 of them); each experiment
re-read from its raw rows and inputs, not from its RESULT file; the W7 numbers recomputed from the run logs
together with runs 1–3 in this repo.

## What to trust

| Part | Trust | Why |
|---|---|---|
| Claims ledger (1,752) | high | 1,685 quotes found verbatim in their sources on a fresh check; the explorer's own check passed 1,625 |
| W7: Avy's own suite at volume | high | 31 live runs and 8 bench runs; the cells match when recomputed from the logs (below, and in [tests/live/RESULTS.md](../tests/live/RESULTS.md)) |
| Run-integrity ledger | high | every 429 storm, kill and restart recorded with evidence; it caught its own logging bug |
| E03 / E03b (keeping the feel) | honest | inconclusive, said so, and stopped the claims it couldn't support |
| Pain map (359 quotes, 15 themes) | good as a map | counts are how often a pain is voiced in forums and posts, not a survey |
| Gap checks G01–G05 | fair | each "nobody does X" is a narrow combination; all five came back *partial* (the nearest systems do parts of it). Read as "this exact combination is unclaimed", not "this ground is empty" |
| Census of systems | useful, one bad row | Supermemory's row carries Agent Zero's numbers (below) |
| REPORT.md | low as a source | use it as a map back into the ledger, not as findings (below) |
| E01, E02, E04 | re-read | their verdicts don't follow from their data (below) |

**The census row.** It gives Supermemory "95.60% LongMemEval-S / 93.60% LoCoMo". That claim (C0015) is from
the Agent Zero paper. Supermemory's own figures in the archive are retrieval recall (95% Recall@15, 97%
Recall@20 with aggregation), not answer accuracy. Their published answer accuracy stays where
[LANDSCAPE.md](LANDSCAPE.md) has it: 81.6–85.2%.

**The report's citations.** Of the 23 sentences citing a claim, 4 say something their quote doesn't, and about
5 more cite something only loosely related:
- "two different systems each claim the best-ever LongMemEval score … 94.87 and 84.23": both quotes are
  Mastra, one system on two models.
- "the bottleneck [is] downstream of retrieval": the quote says the bottleneck *is* retrieval.
- "preferences … get re-asked or ignored": the quotes are Supermemory's description of a plugin that
  remembers them.
- "provenance should be visible on the page": the quote is about causal structure.

Experiment ids are cited the same way: [E04] 22 times, for lines about W7 and the decisions it didn't touch;
the gap files are listed among "ideas that survived a real test". The report passed its own check because the
check counted that every sentence had ids, not that the ids said the sentence.

## The experiments, re-read

**E01, interleaved jobs** (does a per-task state note beat a plain transcript as jobs interleave?). Verdict
given: not supported. **Read it as inconclusive: the test never reached long horizon.** At its largest (eight
interleaved jobs) the transcript shown was a median of 4,632 characters, about 1,150 tokens; the compaction
arm only compacts past 6,000 characters, which happened in 5 of 24 eight-job scenarios and never with two or
four jobs. The plain
transcript got *better* as jobs were added (0.533, 0.554, 0.614), the reverse of what losing the thread looks
like. And the score didn't depend on the insight it was meant to test: in the transcript arm, answers that used
the insight were right 0.561 of the time and answers that didn't, 0.609. The VISION §10 hypothesis is untested,
not refuted. DECISIONS.md §8 and REPORT §6 call it falsified; that reading shouldn't be used.

**E02, hidden rules** (do evidence-backed lessons beat raw history at learning from experience?). Verdict
given: not supported. The lessons arm was broken: superseded versions stayed in the pool and were retrieved
next to the current one (one seed: 24 rows, 3 distinct lessons); retrieval was keyed on the goal text, the same
every episode, so the agent was shown five versions of one lesson; and the outcome and evidence the design is
about were never shown to it. It scored 0.267, near no memory at all (0.178). What does hold: raw recent
history (0.667, and 0.656 even trimmed to the same 2,500 characters) beat a distilled playbook (0.411) and a
notepad (0.333). Simple history is a strong baseline, as CL-Bench also found.

**E03 and E03b, the fork test** (does a fresh copy of Avy, given her memory, continue a conversation like the
real one?). Inconclusive, honestly: the control (her own words from a different moment) was meant to be hard
to tell apart, and the judge spotted it 87.5% of the time, so the judge measures fit to the moment, not voice;
the explorer stopped there, as its rules said. One suggestive line: a copy given her memory bundle passed for
the real one (the judge picked the real continuation only 25% of the time); without her past replies in the
bundle it was spotted 65% of the time; with facts alone, 75–78%. Her own replies that landed seem to carry the
voice. Needs a rater from another model family, or a person.

**E04, an always-in-view note vs recall today.** Verdict given: supported (dinner 0.693→0.943, race 0.89→1.0,
pooled 0.917→0.989). But the note was written by hand and held exactly the facts the probes ask about, with 3
answers per probe. **It shows the ceiling for slots, not that a slot mechanism gets there.** The "invented"
flags it reports as a side effect (5 of 15 cells) are the harness: one note mixed facts from two scenarios, so
answers in one saw the other's (the satay, the dinner rules).

## What it changes for Avy

- **Slots first (VISION §16.4): stronger.** The preference fade is the most reproduced failure at volume, and
  E04 shows how far an always-in-view note can lift it. Build the slots for real, then rerun E04 with the
  mechanism instead of the hand-written note.
- **What Avy is best at (§16.8, §10): unchanged.** Long-horizon multitasking still needs a test that reaches it:
  contexts long enough that compaction actually fires, and a score that moves only if the insight was kept.
- **New:** plans and what's coming up behave as one class (chronic in 3 to 5 of 5 runs). See RESULTS.md.
- **Facts about him himself:** intermittent, not a live failure (1 of 5 runs, the oldest build). Still a
  reason for the core-of-him slot.
- **Thinking at low for the mind:** about 4× the cost per job, cleaner first-try writes, no measured effect on
  answers yet (those runs died in a 429 storm before their probes).

## What changes in the procedure

Added to WORKING-WELL.md: a support check (does each cited claim say the sentence), an attribution check (is
the claim about the system the sentence names), and validity checks before any verdict: does the test reach
the regime the hypothesis is about, does the score depend on the thing being varied, what each arm actually
showed the model, a hand-written input is a ceiling, nothing leaks between scenarios. A test that fails one is
*inconclusive*, never *not supported*. Also: record a command's exit status before anything else can overwrite
it, and score infrastructure failures as infrastructure, never as 0.

## If there's a second expedition

1. E01 again at real lengths: tens of thousands of tokens between the insight and the result, compaction
   firing in most items, and a decision that's only right if the insight from hours earlier was kept.
2. E02 again with the lessons arm fixed (replace, don't append; retrieve by situation; show outcome and evidence).
3. E04 with real slots instead of a hand-written note, one scenario per memory.
4. The coined-term probe (ARCHITECTURE §7.4) and a rater from another model family for the feel.
