# Later

Ideas we've decided to build, but not yet. Each one says when it makes sense to pick it up.

## Your whole Claude history, as a real-scale test

*Next.*

Export every Claude conversation (years of them, many long and involved) and run Avy's mind over it,
to see memory at real scale. Ideas are how you live, and you know exactly what yours are. If they show
up as distinct hubs, with the right things around them and sensible bridges between them, that's strong
evidence the network works.

What it needs:
- **A parser for the export**, written against its schema. The file is far too big to read through, so
  the parser works from the structure: a list of conversations, each with messages, their speaker,
  time and text.
- **The conversations as their own log.** Each conversation becomes its own stretch, so episodes never
  span two conversations. Claude's side is a different speaker than Avy, so it's marked as such.
- **Its own memory file**, so it can be explored (inspector, graph) and compared with your live memory
  without mixing into it. Merging can come after.
- **A long, budgeted run of the mind**: write everything, then reflect. It costs real tokens, with
  progress saved so it can stop and resume.
- **Ways to judge it**:
  - the biggest hubs (are they your real interests and projects?)
  - the ideas that formed
  - bridges between distant areas
  - the network's health numbers at scale

## Smaller ones

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

## Done (moved here from this list)

- **The living graph** (built in memory v2): the corner miniature, the full-page 3D view, light
  labels, hover and click, and Avy's search lighting up the nodes she looks at.
