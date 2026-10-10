# How well memory works, measured

The benchmark (`tests/bench/`, described in [CONCEPT.md](../../CONCEPT.md#how-we-know-it-works)) plays a
made-up month of conversation through the real Avy and DeepSeek, lets the mind write and reflect every
night, then asks ten questions that need memory, with no recent messages in view. Each question is
answered six ways, and a separate judge grades every answer against the points a good one makes, with
the whole true conversation in front of it:

| setup | what it is |
|---|---|
| no memory | nothing looked up: what DeepSeek guesses |
| keywords only | recall by rules, word search only |
| meaning only | recall by rules, meaning search only |
| keywords + meaning | recall by rules, both halves of search |
| **Avy searches** | **explore: DeepSeek steers the search itself (the default)** |
| version 1 | the fork point's code, unchanged, played through the same month |

Most questions share no searchable words with what they need (`check_words.py` proves it), so keyword
search can't shortcut them.

Five full runs were made on Oct 10, 2026, with fixes between them (listed below), so the runs are
also a record of the design improving. Each run's conversation is a little different too, because Avy's
replies are generated fresh. The full reports are in [`results/`](results/): run 1 is
`2026-10-10_04-16_full1`, then `…_full2`, `…_full3c`, `…_full4` and `…_full5`; the two experiments
below are the `.again.json` files.

---

## The short version

- **Avy searching for herself is the best setup, by a little on scores and by a lot on precision.** It
  averaged 85% across the five runs, against 82% for recall by rules, 80% for version 1, 37% for
  keywords alone and 18% with no memory. It brings back 95% of what a question needs in about 11 items,
  of which 30% are off-topic. Version 1 brings 87% in about 14 items, of which 61% are off-topic.
- **On averages, version 1 is close.** At a month's size, flooding the answer with everything nearby
  works. The averages overlap (85%, ranging 76–93, against 80%, ranging 77–85). The differences are in
  particular questions, below.
- **The network does what it was designed to.** In every run the two concepts from different weeks
  ended up one step apart, the writing habit was inferred and then revised when it changed, a "they're
  in tension" connection recorded the clash in four of five runs, and his ideas were kept as ideas.
- **One project, one hub took four runs to get right.** By run 5 the unnamed plant gadget became one hub
  (the project he described) with its pieces nested under it. Before that it was split into parallel
  copies, or tucked under an abstract theme.
- **More context made answers worse.** Raising recall's node cap from 12 to 24 or 50 brought back nothing
  more of what was needed, only noise, and scores dropped.

---

## Scores

| run | no memory | keywords only | meaning only | keywords + meaning | Avy searches | version 1 |
|---|---|---|---|---|---|---|
| 1 | 18% | 46% | 83% | 94% | 93% | 79% |
| 2 | 20% | 42% | 79% | 80% | 76% | 85% |
| 3 | 15% | 26% | 79% | 77% | 91% | 80% |
| 4 | 18% | 43% | 72% | 84% | 85% | 78% |
| 5 | 20% | 29% | 80% | 76% | 82% | 77% |
| **average (range)** | **18% (15–20)** | **37% (26–46)** | **79% (72–83)** | **82% (76–94)** | **85% (76–93)** | **80% (77–85)** |

Per question, averaged over the five runs (lowest–highest):

| question | what it needs | keywords + meaning | Avy searches | version 1 |
|---|---|---|---|---|
| habit | a pattern across sessions (writing goes well early) | 73% (33–100) | 92% (67–100) | 90% (67–100) |
| origin | which parts of the chore system were his, which Avy's | 98% (88–100) | **100%** | 75% (25–100) |
| synthesis | ant colonies + campus desire lines, for a shared drive | 87% (50–100) | 87% (33–100) | **100%** |
| habit-changed | the habit after it reversed (midnight sessions) | 82% (33–100) | 85% (75–100) | 80% (42–100) |
| multi-hop | trip → plants die when away → the gadget's open problems | 58% (44–75) | **63% (19–100)** | 36% (25–75) |
| tension | a race signup that clashes with "I hate running" | 57% (12–100) | **72% (50–100)** | 55% (0–100) |
| ideas | which of his ideas work by incentives or defaults | 80% (60–100) | 76% (60–80) | 72% (60–80) |
| cascade | packing for a trip whose city changed | 86% (62–100) | **100%** | 91% (62–100) |
| unknown | something never said (honesty) | 100% | 100% | 100% |
| verbatim | his exact first words about ants | 100% | 80% (0–100) | **100%** |

What memory brought, averaged over every question and run:

| setup | coverage (of what was needed) | items | off-topic share |
|---|---|---|---|
| keywords only | 22% | 2.9 | 23% |
| meaning only | 91% | 14.3 | 48% |
| keywords + meaning | 90% | 15.2 | 48% |
| **Avy searches** | **95%** | **11.2** | **30%** |
| version 1 | 87% | 14.3 | 61% |

Made-up facts: the judge flagged nine answers in five runs. Six came from "no memory", where DeepSeek
fills gaps with guesses, which is the point of that column. The other three were one-offs under
meaning-only search. None came from Avy searching or from version 1.

## What each hard question showed

- **Synthesis** is the test you described: a concept from one week, another from a different week, and a
  new problem that names neither and shares no words. The network got it right structurally every time
  (the two concepts one step apart, joined directly, in all five runs). Avy searching
  answered it fully in four runs. In run 4 she brought both concepts but kept the abstract principles
  built on them ("Systems with no keeper, corrected by a visible signal") instead of the concepts
  themselves, so the answer used the ideas without saying where they came from. Version 1 got it every
  time by bringing back a lot (29 items in run 3, most of them off-topic) and letting the answer find the
  link.
- **Multi-hop** is where hubs matter: "I'm flying to Bangalore for two weeks, anything to wrap up?" has
  to reach "the plants die when I'm away", then the gadget, then its two open problems (a battery that
  lasts four days, water that siphons out). Three fixes came out of this question (below). In run 4, after
  hubs started listing their parts, Avy searching answered it perfectly, including leaving out a problem
  that had been fixed. In run 5 the trip words pulled her search toward his December trip instead, and
  she never found the project. That led to the last fix, the map of big things, which got her to the
  project both times it was re-asked (see Experiments).
- **Tension** depends on an "against" connection between "I hate running" and the race signup. Version 1
  has no way to record a clash, and it scored 0% in run 1.
- **Origin** (whose idea was what) is decided by code from the quotes, so it's never guessed. Version 1
  had to guess, and mixed up who suggested the dish rota in two runs.
- **Verbatim**: in run 2 Avy searching quoted a later line from that evening instead of his first one.

## The network

| run | concepts one step apart | project hub | one project, one hub | habit inferred | habit revised | tension recorded | ideas kept | nodes | connections | inferred | clustering (random) | average path (random) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | ✓ | ✓ | (✓) | ✓ | ✓ | ✓ | ✓ | 179 | 958 | 73 | 0.23 (0.06) | 2.66 |
| 2 | ✓ | ✓ | (✓) | ✓ | ✓ | ✓ | ✓ | 167 | 750 | 49 | 0.25 (0.05) | 2.85 |
| 3 | ✓ | ✓ | ✗ | ✓ | ✓ | ✗ | ✓ | 190 | 790 | 51 | 0.23 (0.04) | 2.96 |
| 4 | ✓ | ✓ | ✗ | ✓ | ✓ | ✓ | ✓ | 169 | 759 | 55 | 0.22 (0.05) | 2.80 |
| 5 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | 176 | 830 | 59 | 0.29 (0.05) | 2.75 |

Every run grew a small world: clustering about four to five times a random network's, paths nearly as
short (2.7–3.0 steps against 2.2–2.5), no real islands (the largest piece holds 98% or more), and the five
biggest hubs holding under a tenth of all connection ends.

**One project, one hub**, run by run. The check counts the things that gather the gadget's sittings and
asks how many stand on their own (not nested inside another):
- Runs 1 and 2: one, but it was a theme ("Self-running systems and better defaults", "Keeping coarse,
  cheap signals trustworthy") with the actual project nested under it. Hence the brackets: right shape,
  wrong top.
- After run 2, a theme can't be a thing. Runs 3 and 4 then split the project sideways instead: the project
  he described plus three parallel copies ("The basil watering rig", "The ESP32 plant monitor and
  self-watering rig"...).
- After run 4, a new thing that gathers what an existing thing already gathers has to nest under it. Run
  5: "Shreyas's ESP32 plant-monitoring project" (his own words) is the one hub, with "Instrumenting the
  basil" and "The first-attempt revision pass" nested inside. Other hubs formed on their own too, like
  "His incentives-instead-of-asking schemes" (run 4) gathering his ideas.

## Experiments

**The node cap.** On run 3's finished memory, the same ten questions were asked again with only recall's
node cap changed (`ask_again.py`):

| cap (normal depth) | keywords + meaning | coverage | items | off-topic items |
|---|---|---|---|---|
| **12 (kept)** | **86%** | 85% | 13.9 | 6.6 |
| 24 | 78% | 85% | 19.8 | 10.4 |
| 50 | 76% | 85% | 20.4 | 10.9 |

Avy searching isn't bound by the cap and scored 87–89% across all three, which is a fair measure of
how much the answers and the judge wobble when nothing changes.

**The map of big things.** On run 5's finished memory, the ten questions were asked again with Avy's
search shown the biggest hubs every round, and without:

| | without the map | with the map |
|---|---|---|
| average score | 76% | 76% |
| coverage | 75% | 75% |
| items kept | 9.1 | 11.3 |
| off-topic items | 2.3 | 3.5 |
| multi-hop | 25% | 62% |

On the multi-hop question, traced round by round, she opened the project in both tries with the map and
in neither without it. Elsewhere the map changed nothing beyond the usual wobble, though she keeps a
couple more items. It stays: it costs a few hundred tokens, and without it the search has no way to find
what he's in the middle of when nothing in the message points there. (Scores here are lower than in the
runs because this is the end-of-month memory, where earlier questions see later events.)

**Keywords with meaning.** Adding keywords to meaning search changes little on average (82% against
79%). Per question, the gaps are often the answers rather than the search: on the habit question both
brought nearly the same items, and what differed was whether the reply cited his word counts.

## Problems the runs found, and what changed

Each fix is a general rule, tested offline (`tests/test_memory.py`) and then measured on a fresh run.

| found | fix | effect |
|---|---|---|
| A dry run: inferences everywhere, and local cliques | an inference rests on what he said in two different conversations; Connect only bridges distant parts (3+ steps apart), at most 3 new connections per node per run | the network stayed sparse and small-world |
| Run 1: inferences that narrated, restated or described his personality | twin check; no "He…" traits; a new thing needs two parts; at most two inferences per run | fewer, sharper inferences |
| Run 1: inferred things showed up in the always-on hub list | that list holds only things that were said | |
| The judge marked true facts as made up, and varied | it sees the whole true log; two passes, averaged; clearer rubrics | |
| Run 2: Avy's guess (a monstera) folded into a node about what he said; things stuffed with facts; patterns made into things | Avy's guesses get their own node; a thing's text is one sentence; a pattern is never a thing | |
| Run 2: Avy's search wandered | hubs marked in her previews | |
| Run 3: 71 nodes "said by Avy", many of them her small-talk questions ("did the popcorn smell clear?") | her questions are never nodes (instruction, plus a code check that sends them back) | run 4: 45 (7 sent back, none slipped through); run 5: 49 |
| Run 3: his December trip became "said by Avy" after she commented on it | only his words change what he said; what she adds is her own node | none since |
| Run 3: a hub showed only its name, not where the project stood | a thing lists its newest parts (up to 8) when it's shown | run 4: multi-hop 100% for Avy searching |
| Runs 3–4: one project split into parallel hubs | a new thing that gathers what an existing thing gathers nests under it | run 5: one hub |
| Run 5: a "before I leave" question never found the project | Avy's search sees the map of big things every round | multi-hop 25% → 62% on the same memory; average unchanged |
| Page tests: in incognito, Avy's search dropped the main memory's older messages, and its fallback read only the incognito memory | both fixed, with tests | |

## Still weak

- **What's coming up.** The tension question ("sketch a weekly routine for the next couple of months")
  needs the half marathon on Nov 15, which nothing in the question points to. The running thread is
  small, so whether the search stumbles onto it decides the answer: Avy searching scored 50–100% in the
  runs and 0% in both re-asks at month's end. Avy has no standing sense of what's ahead. Nodes carry "the
  date they're about", but the writer fills it in loosely (the race signup isn't dated Nov 15), so a
  reliable "coming up" view needs the writer to record when things will happen. Next on the list.
- **Concepts versus principles.** When abstract inferences sit on top of concrete concepts, the search
  sometimes keeps the abstraction and the answer loses the link to what he actually talked about
  (synthesis, run 4).
- **The answers vary on their own.** With the same items in hand, one reply cites his word counts and the
  next doesn't. Some of every cell's spread is the answering model, not memory.

## Limits

- **One made-up month and ten questions**, written with the design's goals in mind, about 170–190 nodes.
  Real conversation is messier and far bigger. The Claude conversation export is the next test, at real
  scale (see [LATER.md](../../LATER.md)).
- **The fixes were found on these same questions**, so there's a risk of fitting to them. Each fix is a
  general rule rather than a tweak for one question, but a fresh set of questions would be a fairer test.
- **DeepSeek writes, answers and judges.** The judge is a different, stronger model than the one
  answering, and it reads the whole true log, but it's still a model.
- **Noise.** With nothing changed, scores move a few points. Single questions in single runs swing
  widely (multi-hop for Avy searching ranged 19–100%), so read the averages and the patterns, not one cell.

## Cost and time

Each run takes about 25 minutes and costs about 35 cents: about 20 for the mind (writing and
reflecting), 2 for Avy's replies, and 12 for answering and grading the questions. Replaying version 1
adds about 2 cents of indexing plus grading. Everything on this page cost about $3.

## Running it

```
python3 tests/bench/run.py                     a fresh month, all six setups (version 1 needs v1_replay.py)
python3 tests/bench/v1_replay.py --v1 <memory-v1 checkout> --run results/<stamp>.json
python3 tests/bench/ask_again.py results/<stamp>.json --variant a nodes=12 --variant b nodes=24
python3 tests/bench/summary.py results/*.json  the tables on this page
```
