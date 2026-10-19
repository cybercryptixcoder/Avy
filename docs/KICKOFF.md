# Kickoff prompt for a fresh conversation

Copy everything below the line into a new conversation with a capable coding agent that has shell and browser access
to this machine.

---

You are taking over work on **Avy**, a personal agent that lives at `/home/ubuntu/Avy` and runs as a systemd service on
this machine. A previous agent (me) did a first round of improvement work. Your job is to continue it. Do not start
from scratch and do not re-derive what is already written down.

## Catch up in this order — this is the required reading

1. **`/home/ubuntu/Avy/docs/REQUESTS.md`** — every request the human made, in their words, with the status of each and
   the actual number attached. This is the requirement. It contains a table of eight to-do items with what is done,
   what is not, and how much.
2. **`/home/ubuntu/Avy/docs/HANDOVER.md`** — how to run everything, every trap that will cost you an afternoon, and the
   five score defects to attack first.
3. **`/home/ubuntu/Avy/docs/RESULTS.md`** — what the last measurement round returned, plus the nine broken instruments
   that were caught before their numbers were believed.
4. **`/home/ubuntu/Avy/docs/IMPROVE-RULES.md`** and **`docs/GUARDRAIL.md`** — the rules you work under and why.
5. **`/home/ubuntu/Avy/docs/IMPROVE-NOTES.md`** — the long record: her design intent, what the code does, findings,
   decisions, and the study of Hermes (the agent framework the previous agent runs on) that informed two changes.
6. **`/home/ubuntu/Avy/CONCEPT.md`** and **`ARCHITECTURE.md`** — written by Avy's creator, not by me. They are the
   intent. Read them properly.

Only after those six should you form an opinion about what to change next.

## What the human actually wants

They said it directly and repeatedly:

- **10× improvement**, measured. Not achieved. Best so far is +23% on one config of her own bench, and one config
  regressed by 13%.
- **Comparable to a really good model online.** Not demonstrated. Her LoCoMo numbers sit at the bottom of the published
  full-context band; the software-engineering sample is three deliberately easy instances, which proves she can close a
  small bug fast but says nothing about parity.
- **A fully capable system that functions as an agent in itself.** Not achieved.
- **Keep going until every benchmark improves significantly.** Not done — that is your job.
- **Long builds and multi-step builds.** Multi-step is measured (three dependent steps, 382.7 s, no false claims). A
  build that runs for hours is not.
- **Real evidence only.** They were explicit: do not invent problems, and self-check your instrument before believing
  its output, because the previous agent twice reported a broken harness as a subject failure.

## The five things wrong right now

Start here; they are ordered by how cheap they are to settle:

1. **Temporal recall collapses on some conversations** (0.235 vs 0.60). Hypothesis: nodes are not stamped with the
   session's `date_time` at ingest. **Confirm it with one query** — inspect a node written from session 12 of conv-41.
   Do not act before confirming; the previous agent already retracted one confident temporal hypothesis.
2. **The `words` config regressed 0.36 → 0.229** and nothing in the notes explains it. Diff it against `meaning`.
3. **`both` scores 0.00 on `tension`** while two other configs score 0.75 on the same probe.
4. **She never opens threads.** Across 346 messages she used a tool on 7 turns and opened no thread, so the desk's
   in-flight block and the `thread_lines: 0→2` change have never been exercised. Fix the behaviour, then measure.
5. **No random SWE-bench sample and no third benchmark.** Twenty random instances would be worth more than the three
   easy ones already done.

## Rules you must work under

- `main` stays clean. Work on `improve/continuity-and-horizon` (or a branch off it). `main` carries a safety tag.
- `~/Avy/data/` is her memory. Never delete it. Back it up before anything risky.
- Avy commits locally and is never pushed. Do not push her commits.
- **Self-check every instrument with a known-good case before trusting a single number.** The gold patch must pass
  before her zero means anything. If a batch of scores comes back uniformly terrible or uniformly perfect, suspect the
  harness.
- **Verify from the user side.** Real browser, real navigation, screenshots actually looked at. Headless assertions on
  their own are not verification.
- Keep documenting *why*, in `docs/`, as you go — the human asked for this explicitly and it is how the next handover
  will work.

## How to begin

Before changing anything, establish the baseline yourself so you are not trusting my numbers:

```bash
cd /home/ubuntu/Avy
for t in tests/test_*.py; do /home/ubuntu/avy-venv/bin/python3 "$t" || echo "FAIL $t"; done
/home/ubuntu/avy-venv/bin/python3 tests/bench/probe.py --configs none,words,meaning,both,explore --tag takeover
```

If those disagree with `docs/RESULTS.md`, say so plainly and investigate before proceeding — a disagreement is
information, and the last agent found two of their own reports wrong this way.

Then reply with: what you read, what you verified yourself, where you think you should start and why, and your claim
about which of the five defects you can settle first. Do not begin large changes until you have said that.
