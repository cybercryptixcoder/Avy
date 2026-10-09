# How Avy remembers

One endless conversation. Nothing is ever summarized away; instead, an index is written into it.
DeepSeek does the judgment (what matters, how to say it, what connects). Code does everything that
has to be right every time, and refuses anything it can't check.

## The vocabulary

| Name | What it is | Written by |
|---|---|---|
| `#41` | **Message** 41 in the log: who, when, typed or spoken, the exact words. | The log, as it happens |
| `p4` | **Page** 4: one stretch of the log (about 20 messages) with a headline and its entries. | DeepSeek, checked by code |
| `e12` | **Entry** 12: one thing worth finding later. A kind, a title, a sentence or two. | DeepSeek, checked by code |
| evidence | A pointer from an entry to the exact words in a message (`#41`, characters 10–38). | Code copies the words |
| link | A pointer from an entry to another entry, with a kind. | DeepSeek, plus code |
| version | A correction or update: a new entry that **replaces** an earlier one. | DeepSeek, checked by code |

**Entry kinds:** `person` and `topic` are hubs (other entries gather around them); `fact`, `event`,
`decision`, `preference`, `task` are notes.

**Link kinds:**
- `about`: this note belongs to that hub ("Rohan's birthday" is about "Rohan").
- `builds_on`: this uses what that entry says ("gift idea" builds on "Rohan's birthday").
- `related`: a looser connection.

Entries can mention each other in their text as `[e12]` ("party at [e3]'s place"). That's writing by
reference: the place lives in one entry, so a change to it reaches everything that mentions it.

## The rules code enforces

1. **The log is permanent.** The database refuses to edit or delete a message.
2. **Every entry has evidence.** Each quote must really appear in the message it points to (exactly, or
   near enough after ignoring case and punctuation). The stored quote is copied from the log by code,
   never from DeepSeek. If a quote can't be found, it's sent back to be fixed; if it still can't, the
   pointer falls back to the whole message and is marked as such.
3. **Every link points at something real.** Unknown entries are rejected, `about` only goes to hubs,
   DeepSeek gets at most 6 links per entry, and links written into the text are moved into the links.
4. **Versions never fork.** An entry can be replaced once; a new version must replace the current one.
   Search always lands on the current version, and the old ones stay reachable as history. A new version
   keeps its predecessor's links.
5. **Nothing is created twice.** A second hub with an existing title is merged into the first; a second
   note with an existing title becomes a new version of it.
6. **Updates can't leave stale copies unnoticed.** When an entry is updated, code finds entries written
   from the same messages, or built on it, and asks DeepSeek once whether they need a new version too.
7. **Some links are free.** An entry that names an existing hub belongs to it; two entries citing the same
   message are neighbors. Code adds these; DeepSeek doesn't have to.
8. **Every indexing run is recorded:** what DeepSeek was shown, every answer, every problem found and how
   it was fixed, tokens and cost. Problems go back to DeepSeek in plain words, up to twice; then whatever
   passed is saved. If DeepSeek can't be reached, nothing is lost and it tries again later.

## What happens on every message

1. **Search.** Your message is compared with every entry (every version) and every older message,
   by meaning (a small local model) and by shared words (rarer words count more). The score is on a
   fixed scale, so "nothing matches" is a real answer.
2. **Walk.** From the entries that matched, links are followed one and two steps out (from a hub to what
   belongs to it, from a note to what it builds on), so things that never mention your words can still
   come back. A strong match makes weak ones noise: what's far below the best match is dropped.
3. **Brief.** DeepSeek gets, in order: Avy's instructions and the biggest hubs (they rarely change, so
   DeepSeek's cache makes them cheap), the newest 20–29 messages word for word, a memory note with the entries it found (their
   evidence, earlier versions and links) and a few older messages, then your message.
4. **Record.** What was found, how each thing was reached, and the exact note DeepSeek got are saved with
   the reply. That's what `↳ recalled …` opens.
5. **Index.** Once a page's worth of messages has built up (or you've been away 30 minutes), DeepSeek
   writes the next page in the background. `/index` does it now.

## Testing it

- `python3 tests/test_memory.py` runs offline in seconds: every rule above, recall through links, the
  repair loop with a scripted DeepSeek.
- `python3 tests/live_memory.py` replays a week of conversation through the real DeepSeek: facts on day 1,
  a correction on day 3, details only reachable through links, a question that was never answered, and a
  deliberately broken answer the indexer has to repair. It prints every answer, what memory brought for
  it, and the whole index. A few cents; it uses a throwaway memory, never yours.

## Next

Letting DeepSeek walk the network itself: open an entry, follow its links, check older versions, search
again, until it has what it needs.
