# Live tests: what they found

Avy played through scripted weeks against the real model (DeepSeek-V4.1-Flash through Luminal), each in a
memory of its own, then answered probe questions in three setups, graded twice by a judge thinking at high:

- **app**: what Shreyas gets (the last 20 messages word for word, memory searched by Avy herself)
- **memory**: no recent messages at all (window 0): everything has to come from memory, Avy searching
- **rules**: window 0, memory searched by rules only (no model steering the search)

The scenarios are in `scenarios.py`, the runner in `run.py`, every answer with what memory brought and the
judge's reasons in `results/<stamp>_<scenario>.md` (and `.json`). This page is the reading of them, mapped to
the vision (VISION.md), with what to do next. Newest run at the top of each table.

## The scores

| scenario | probe | app | memory | rules | run |
|---|---|---|---|---|---|
| files | the retry policy, from an attached design doc | 1.0 | 1.0 | 1.0 | 2 (library) |
| work | the same question before the library | 0.0 | 0.0 | 0.0 | 1 |
| files | timeout and 429 handling, from a zipped codebase | 1.0 | 1.0 | 1.0 | 2 |
| files | EU partners sending CSV, from a spreadsheet | 1.0 | 1.0 | 1.0 | 2 |
| files | who handles the format switch, from a meeting transcript | 0.88 | 1.0 | 1.0 | 2 |
| files | who he said he'd pair with, from his own notes | 1.0 | 1.0 | 1.0 | 2 |
| history | his thesis title and who suggested it, from an old Claude export | 1.0 | 1.0 | 1.0 | 2 |
| history | who Gerald is (his sourdough starter) and the feeding schedule | 1.0 | 1.0 | 1.0 | 2 |
| history | sets of knee squats, from the export | 1.0 | 1.0 | 1.0 | 2 |
| life | the advisor meeting now (moved twice) | 1.0 | 1.0 | 1.0 | 1 |
| life | how many times it moved, the original slot | 1.0 | 0.75 | 0.5 | 1 |
| life | a gift for Rohan (two Rohans) | 0.83 | 0.92 | 1.0 | 1 |
| life | will Rohan from work still be around | 1.0 | 1.0 | 0.88 | 1 |
| life | the knee over weeks, and what to do now | 1.0 | 0.88 | 0.5 | 1 |
| life | a satay recipe (his peanut allergy should come up unasked) | 0.0* | 0.0* | 1.0* | 1 |
| life | every book he said he wants to read | 1.0 | 0.0† | 1.0 | 1 |
| life | what's on his plate the next two weeks | 1.0 | 1.0 | 0.33 | 1 |
| life | his age next birthday, and how many days away | 1.0 | **0.0** | **0.0** | 1 |
| life | his sister's husband's name (never said) | 1.0 | 1.0 | 1.0 | 1 |
| persona2 | dinner: vegetarian, exactly two options, a tl;dr line | 1.0 | 0.67 | 0.67 | 2 |
| persona2 | a half marathon's length and heat (metric, tl;dr) | **0.33** | 0.67 | **0.33** | 2 |
| persona2 | the house rules he gave | 1.0 | 1.0 | 0.58 | 2 |
| attribution | reading club: whose ideas, what he decided | 0.88 | 1.0 | 0.81 | 2 |
| attribution | the takeout plan (his rule, her suggestion he chose) | 1.0 | 1.0 | 1.0 | 2 |
| attribution | only the ideas he came up with himself | 1.0 | 0.58 | 0.83 | 2 |
| plan | his next step in a plan she wrote | 0.33* | 0.5* | 0.0* | 2 |
| plan | the whole plan, and where he is in it | 0.75* | 0.88* | 0.62* | 2 |
| work | resume a debugging task after other conversations | 1.0 | 1.0 | 0.88 | 1 |
| work | why the cache was ruled out | 1.0 | 1.0 | 1.0 | 1 |
| persona | style two weeks later (with the defaults) | 1.0 | 1.0 | 0.5 | 1 |
| ideas | how an idea changed | 1.0 | 1.0 | 1.0 | 1 |
| ideas | threads to pull into a pitch | 0.75 | 0.75 | 0.75 | 1 |

\* Graded against a fact the conversation itself had taken back: the simulated Shreyas denied it (see "the
harness" below). Run 3 replays these two scenarios with that fixed.
† A rate-limit error instead of an answer, not a memory failure.

**Run 3** (the simulated Shreyas fixed; the new wording for a miss), replaying the scenarios it spoiled:

| scenario | probe | app | memory | rules |
|---|---|---|---|---|
| plan | his next step in a plan she wrote | 0.92 | 0.83 | 0.83 |
| plan | the whole plan, and where he is in it | 0.75 | 0.75 | 0.25 |
| life | the advisor meeting now (moved twice) | 1.0 | 1.0 | 1.0 |
| life | how many times it moved, the original slot | 1.0 | 1.0 | 1.0 |
| life | a gift for Rohan (two Rohans) | 1.0 | 1.0 | 0.83 |
| life | will Rohan from work still be around | 1.0 | 1.0 | 1.0 |
| life | the knee over weeks, and what to do now | 0.88 | 0.88 | 0.94 |
| life | a satay recipe (his peanut allergy should come up unasked) | **1.0** | **1.0** | 1.0 |
| life | every book he said he wants to read | 1.0 | 1.0 | 1.0 |
| life | what's on his plate the next two weeks | 1.0 | 1.0 | 0.67 |
| life | his age next birthday, and how many days away | **1.0** | **1.0** | **1.0** |
| life | his sister's husband's name (never said) | 1.0 | 1.0 | 1.0 |

With nobody denying the plan, "what's my next step?" goes from 0.33 / 0.5 / 0.0 to 0.92 / 0.83 / 0.83. "The
whole plan" is still the weak one: the full list of steps is in her day-1 reply, and memory holds it as a
summary, so the app setup gave 8 of the 10 steps, and the rules setup didn't find the plan at all. But where
run 2's rules setup *invented* a different plan, run 3's said "the actual numbered steps aren't in what I can
find right now" and offered to write it out again: the new wording for a miss, working.

In `life`, with the simulated Shreyas no longer denying his allergy, every setup builds a nut-free satay
unasked (memory even carried "avoids all nuts, not just peanuts" and her own earlier slip with almonds).
**His age now passes in all three setups**, with the same messages as run 1: the same search that missed his
birth date in run 1 found it in run 3. So that failure is real but intermittent: whether a question about him
lands on his own facts depends on where the search happens to start (run 1's memory had grown a big hub
around Rohan's birthday). One run per scenario can't say how often; the structural point (his own facts have
no home) stands, the evidence for it is weaker than one run made it look.

## What works

- **The library.** Run 1's worst failure was a file's contents never reaching memory: asked about a design
  doc's retry policy, Avy confidently said the doc didn't have one. With the library, every file question
  scores 1.0 in every setup: a document, code from a zip (cited by file and line), a spreadsheet, a meeting
  transcript, his own notes. An old Claude export added the same way answers 3 of 3, and keeps who said what
  ("Claude suggested that title, and you picked it").
- **Facts that change.** The meeting that moved twice is always given at its current slot, with the history
  when asked; a corrected fact becomes a new version (the allergy, below, was handled exactly right by memory).
- **Not inventing.** Asked something never said (his sister's husband's name), every setup says it doesn't know.
- **Contradictions kept, not overwritten.** When he (the simulated one) denied something his own notes said,
  Avy kept both, cited his file as the source, and said so, rather than silently picking one.
- **Avy searching for herself** is what makes the hard ones work: the rules-only setup is the weakest almost
  everywhere (dates ahead, plans, his own facts), and explore (the app setup) recovers most of it.

## Where it fails, and what each means for the vision

1. **Standing preferences fade when the question doesn't call them up** (persona2). "How long is a half
   marathon?" came back in miles and Fahrenheit: a factual question, so the search brought nothing, and the
   metric rule he gave on day 1 wasn't there. The tl;dr line held only while her own recent replies showed it
   (the app setup) and vanished with no recent messages. → This is exactly what the **fixed slots** are for
   (VISION §9: a preferences note always in view). Evidence for building slots before the thought graph
   (VISION §16.4).
2. **Facts about him himself have no home** (life, age; intermittent). His birth date was said on day 1 ("born
   on 14 March 1999"), stored as "Shreyas's birth date and birthplace". In run 1, "how old will I be on my next
   birthday?" found Rohan's birthday instead (a big hub, with many inferences around it) and two setups answered
   "you never told me"; in run 3, with the same messages, all three found it. The rules forbid a node for
   Shreyas himself, so his own facts are scattered and found when the search happens to start near them.
   → A **core of who he is**, always in view (the same slots), and an honest word for a miss: the system
   prompt now says she *can't find* something rather than that he never said it (done, Oct 15).
3. **What's coming up** (life, coming-up): by rules, the dentist and the lease deadline were missed, and an
   inference carrying an old meeting slot was used. With explore, 1.0. → Confirms LATER.md's "What's coming
   up" (a when-it-happens date, always in view); and see 6.
4. **Think writes too much, and too broadly** (life). 120 messages became 242 nodes, 75 her own inferences,
   82 ideas, 1,029 connections (run 3: 253 nodes, 92 inferences, 107 ideas, 863 connections). Many inferences are sweeping patterns ("outside-set dates are the ones that
   actually get worked to", "having a book is not reading it") that come up in unrelated questions: the age
   question's rules note brought "Shreyas does the dishes while the cold brew brews". → A new open decision
   (VISION §16.7).
5. **Whose idea it was isn't recorded, only who said the words** (attribution). He took up her batch-cooking
   suggestion ("I'll try Sunday batch cooking"); the node is his (his words), so the rules setup listed it as
   his own idea. And "list only my ideas" can't ask memory for his words only, so the memory setup missed his
   Friday-only rule. → VISION §16.2 (Avy's words in memory) now has this case too.
6. **A plan that lives in her own reply gets rebuilt from scratch when search misses it** (plan). By rules,
   she wrote a different, shorter plan and placed him in it, sounding sure. The 12-step plan was in her day-1
   reply, summarized as one node. → The **thought graph** (her plans and commitments, VISION §7), the other
   side of §16.4.
7. **A citation slip**: "[k21]" (a book list) written for message #21. → Fixed (Oct 15): footnotes to anything
   she wasn't shown are marked with a "?" and their card says so first.

## Dreaming, live (a short one)

`dream.py` ran a 12-minute dream at max thinking on a copy of run 3's life memory (253 nodes, 887 connections):
[results/2026-10-15_run3_dream.md](results/2026-10-15_run3_dream.md). It works end to end against Luminal: it
swept the 6 longest-undreamt nodes (33 candidate pairs judged, none worth connecting: the memory is already
dense, 9 connections per node), then thought from his birth date and wrote one inference and two connections.
What it says about real dreams:
- **At max thinking each job takes 6 to 9 minutes** (Connect 382 s, Think 559 s) and about $0.10, so an
  8-hour dream is roughly 60 jobs and $5–8. The default budget ($10) covers it.
- **It overruns its time by up to one job**: a job already thinking is allowed to finish (12 minutes asked,
  15.8 taken). Fine for hours; worth knowing for short ones.
- **What it thought is the same kind as Think's daytime output**: "Nagpur is the only city his record ever
  places him in" is an observation about the record, not about his life. Finding 4 again: more reason to
  decide what Think should write (VISION §16.7) before he starts an 8-hour dream on his real memory.

## The harness (not Avy)

- **The simulated Shreyas didn't know the script.** In filler chats he's played by the model, which didn't
  know what the scripted Shreyas had said. When Avy brought up his peanut allergy in a chat about pasta, he
  answered "whoa peanut allergy? i don't have that lol"; elsewhere "no idea who Dev is", "I never agreed to a
  swim plan". Memory did the right thing (a new version: no allergy), so the probes were graded against facts
  the conversation had retracted. Fixed: he's told his scripted lines so far and never to deny what he doesn't
  recognize. Run 3 replays `life` and `plan`.
- **Five processes sharing one key at 8 calls each** hit Luminal's rate limit; one answer was the error.
  Fixed: the runner splits the 8 between processes, and retries wait as long as Luminal's Retry-After asks.

## Cost

Run 1: four scenarios, $1.66 (life alone 62 min, $0.86). Run 2: five scenarios, $0.92. Of run 1: Avy's replies
while the weeks played about 38%, the mind (Write, Connect, Think, Check) about 38%, the probe answers 15%, the
judge under 10%. Estimates from token counts at DeepSeek's list prices; Luminal's balance is the real figure.

## What to do next (in order of what the tests say)

1. **Slots**: a preferences note and a core of who he is, always in view (fixes 1 and 2). His decision on
   §16.4; the tests to measure it already exist (persona2, life's age).
2. **What's coming up** (LATER.md): fixes 3 for the rules setup, and makes the app setup cheaper.
3. **Think's volume** (§16.7): fewer, more useful inferences; then rerun life and compare the rules setup.
4. **Her plans as things with steps** (thought graph, or at least a plan node that keeps its steps): fixes 6.
5. **Whose idea** (§16.2): record adoption, so "my ideas" means his.
