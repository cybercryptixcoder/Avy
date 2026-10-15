# Later

Ideas we've decided to build, but not yet. Each one says when it makes sense to pick it up.

## Your whole Claude history: the mind's run

*Yours to start.* The reader and the import are built and the import is done (503 conversations, 6,561
messages, in `data/memory-claude.db` on whichever machine ran it; docs/IMPORT.md). What's left is the
long run that turns it into knowledge, which costs real tokens, so it's started by hand:
`python3 tools/claude_import.py plan`, a trial with `run --max-stretches 20`, then `run --max-dollars N`.
Then the judging:
- the biggest hubs (are they your real interests and projects?)
- the ideas that formed
- bridges between distant areas
- the network's health numbers at scale

After that: whether to bring Avy's own log in after it (`tools/copy_log.py`) and live on that memory.

## What's coming up

*Found by the benchmark (see tests/bench/RESULTS.md, "Still weak").*

Avy always knows the big things in your world (the hubs), but not what's ahead: a race in six weeks, a
trip at the end of the year. Questions about your time ("a routine for the next couple of months",
"anything before I leave?") need exactly that, and today they only get it if a search happens to land
there. Nodes have a "when", but the writer uses it loosely (for the race, it's the day you signed up,
not race day). What it needs:
- the writer records when a thing will happen, separately from when it was said
- a "coming up" list (the next few months of what you've said is ahead), always in view like the hubs,
  for Avy's answers and her search
- dates that pass quietly turn into history (done, or an open question: did it happen?)

## What files say, into memory

*Next after the history run.* Today the log keeps which files went with a message and the writer sees their
names, so memory knows a file was shared and what was said about it, but not what the file itself says.
A document he shares is often the thing he wants remembered. What it needs: the writer reads a file's
text (within a budget) and writes knowledge from it, with evidence pointing into the file (a page, a
line, a time in a recording) the way it points into messages.

## Proactivity

*The next pillar, once memory has met real use.* From the conversation that started it all
(docs/IDEAS.md, "Proactivity"): structured wake-ups (plan, schedule, stop; wake on triggers or every few
hours), every task a scheduled job, fixed rules plus rules the model writes for itself that he approves,
reaching out with what he could do right now. Memory is the model of his life it would use; a simple
view of tasks, calendar and what Avy plans would come with it.

## Smaller ones

- **Explore and depth as two dials.** He described separate settings for looking around and digging
  deep; today one dial (`/recall:`) sets the rounds and Avy chooses each round.

- **"Keep this" from incognito.** Before ending an incognito conversation, promote chosen messages
  into the main memory, so nothing is lost by accident.
- **Beliefs over time.** Nothing is deleted, and connection strength can be read as it stood on any
  date, so "what did you believe about my sleep a month ago?" and "how has your picture of this project
  changed?" are answerable. They need a view: a time slider on the graph, and a "then vs now" page.
- **Ask to confirm.** When an inference matters to an answer and is only "possible", Avy could ask you
  in passing, and turn your answer into evidence.
- **Recall depth decided per message.** With Avy searching herself, `/recall:` could become the most she
  may dig, with her deciding how much each message needs ("what time is it?" shouldn't trigger a deep
  search).
- **Graph filters.** Show only ideas, only what you said, only what's changed this week; the path a
  particular answer took.

## Parked ideas

The idle game, the swipe cards, the narrator who keeps you company while agents work, and Ava's card
interface are kept in docs/IDEAS.md, in case any of them comes back.

## Done (moved here from this list)

- **Your Claude export, imported** (the reader, the import, the page's `[ import ]`, the run's tooling).
- **Files**: attach anything, read it, download, export.
- **A US provider**: Luminal.

- **The living graph** (built in memory v2): the corner miniature, the full-page 3D view, light
  labels, hover and click, and Avy's search lighting up the nodes she looks at.
