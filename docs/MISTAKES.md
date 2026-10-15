# Mistakes

Every mistake Claude made along the way that is known, in order: what happened, what fixed it, and
the lesson kept. Some were caught by Shreyas, some by tests, some by the benchmark. This is here so the
same ones aren't made twice. (When a cause was outside Claude's control, it says so.)

## While shaping the concept

1. **Suggestions not clearly grounded in the research.** After researching idle games, Claude's
   recommendations mixed research with its own leanings, and Shreyas had to ask: *"All this is inspired
   by everything we learnt from the earlier research or is this just stuff you made up from your own
   biases?"* Lesson: say which parts come from evidence and which are opinion.
2. **Describing research instead of applying it.** The first builder description re-explained the
   project the builder already knew, stated what users like without saying what to change, and left
   design decisions open. Lesson: every finding ends in a decision about what we build.
3. **Bringing up existing products.** Claude mentioned similar things that already exist; it kills his
   interest. Now a standing rule: never, unless he asks.
4. **Fixing a structure too early.** Claude laid out an exact lifecycle and architecture for the
   proactive agent one message after the idea came up. *"We're trying to set things in stone before they
   even form properly."* Lesson: understand the intent first; designs come after.
5. **Research that wasn't extensive.** Asked to research a new kind of model ("JEV") and evaluation, the
   first pass was thin: *"Did you research extensively online? I didn't see that."* Lesson: when asked to
   research, actually go deep, and show it.

## Ava

6. **A builder prompt that produced clutter.** Claude's long prompt for Ava led to an interface with
   *"a million different drop-downs... a million different notifications"*, the opposite of taking the
   overwhelm out. The prompt described features, not restraint.
7. **Process so long nobody understood the result.** Phases, delegated builders, pull requests, and at
   the end code Shreyas couldn't reason about, after a large spend. That's why Avy exists: built
   directly, small, explained.

## Avy, the first days

8. **HTTPS failed on his Mac.** The first version used Python's default certificates, which python.org's
   Mac install doesn't have: `CERTIFICATE_VERIFY_FAILED`. Fixed with truststore and certifi. Lesson: test
   on the setup he actually runs.
9. **Overdone design in the chat.** Colors and styling went into the conversation area; he wanted it bland,
   off-white, terminal-like. Fixed.
10. **Useless decoration and landing-page text** (a flower, taglines, "Ava's baby") on what is his own
    tool. Removed; replaced with the dense system card.
11. **A slow voice pipeline that cut him off.** The automatic voice detection decided he'd finished
    mid-sentence, and the pipeline lagged. Replaced by push-to-talk, and Pipecat by a small custom
    pipeline.
12. **Spoken replies died after switching tabs** (the browser suspends audio). Fixed by recreating the
    audio output when it's stuck.
13. **Losing track after context compaction.** More than once, Claude's picture of his vision went fuzzy
    after a compaction, and he had to ask it to reread the real transcript. Lesson: go back to his actual
    words, not a summary of them, before saying what he wants.
14. **Jargon.** "The trade-off of link quality depends on the indexing step" meant nothing to him.
    Lesson: plain words.

## Memory, version 1

15. **Recall missed things just under a cutoff.** "What should I get my friend for his birthday?" scored
    the right entries just below the relevance threshold; the answer was right only because the raw log
    search caught it. The cutoff had been tuned on the same test it was judged by.
16. **The indexer wrote entries for questions** ("Rohan's birthday re-confirmed").
17. **Saying storage was settled when it wasn't.** *"I shouldn't have let it sound that way."* The
    network between entries was the weakest part.
18. **Reframing without thinking.** Claude restated his long messages well but gave little of its own
    view: *"I see less of your thoughts on all of it."* Lesson: a discussion needs opinions, not only
    summaries.

## Memory, version 2 (found by the benchmark, Oct 10)

19. **The judge marked true facts as made up.** It only saw his side of the conversation. Fixed: the
    judge sees the whole log, grades twice, and only counts something as invented if both passes agree.
20. **Avy's small talk stored as ideas** ("did the popcorn smell clear?"). Fixed: her questions aren't
    knowledge; his answers are.
21. **His own trip relabeled "said by Avy"** after she commented on it. Fixed: only his words can change
    what he said; her additions are her own node, connected to his.
22. **Hubs showed only their name.** A project came up as a title with nothing about where it stood.
    Fixed: a thing lists its newest parts, like a wiki page's contents.
23. **One project split into parallel hubs** (runs 3 and 4). Fixed by a rule: one hub, with pieces
    nested inside it.
24. **Search couldn't find a project the question didn't name** ("anything to wrap up before my trip?").
    Fixed: Avy's search always sees a map of the biggest hubs.
25. **Two gaps in incognito** (the fallback search and the safety net didn't read both memories). Fixed.
26. **A guess about the node cap was wrong.** Claude expected more nodes per answer to help; measured,
    it only added noise and answers got worse. The cap stayed at 12 (RESULTS.md).
27. **A scoring bug inflated the hub check**: counting a hub's listed parts made retrieval look better
    than it was. Fixed: parts count only where they're actually shown.
28. **The usage limit killed a benchmark run partway** (outside Claude's control). Re-run.
29. **A git tag couldn't be pushed** (the proxy refused it; outside Claude's control). The fork point is
    the branch `memory-v1`.
30. **His browser ran version 1's page against version 2's server.** The page was cached, so after the
    update the memory view failed with *"pages.length"*, the old card and the old command list showed,
    and it looked like nothing had been built. Claude hadn't foreseen a stale tab. Fixed: the page is never
    cached, and an open tab reloads itself when the server has a newer page.
31. **One dial instead of two.** He described separate explore and depth settings; Claude built one
    (`/recall:` sets the rounds, and each round she chooses broad or deep). Said so in the audit; still
    open.

## The Claude export and Luminal (Oct 10 to 14)

32. **A probe printed a fragment of his text.** While working out the export's shape by code (counts and
    shapes only, as he insisted), one probe matched a timestamp-like pattern too loosely and printed a
    short piece of a message along with it. Caught at once; the probe was changed to print only the first
    26 characters of such values, and every later probe printed only counts and key names. Lesson: when
    probing private data, print types and lengths, never values.
33. **The import hit the 10-minute tool limit** while computing search vectors for 6,561 messages. It was
    built to be safe to run twice, so it was resumed in the background and finished.
34. **Assumptions about Luminal that didn't hold**, found by probing before building on them: a forced
    tool call is refused while thinking (so the mind offers the tool instead of forcing it), and JSON-schema
    output isn't available (so an answer given as plain JSON is accepted).
35. **Small slips caught by tests or review:** a merge command form git doesn't support; a page test run
    with the wrong Python; a test that hard-coded a folder; a find-and-replace that left "and The model"
    capitalized.

## This round (Oct 14)

36. **Tests that tested the wrong thing.** The new import test fed the writer an answer quoting messages
    from another stretch; the file reader counted a final newline as an extra line ("3 lines" for 2); the
    fake Luminal looked for file tags in escaped JSON; files uploaded in the same second listed in random
    order. All fixed; each was a bug in the test or a real off-by-one.
37. **faster-whisper's own audio loader breaks on the newest PyAV** (a library mismatch, found by the
    page test with a real recording). Avy now decodes attached audio and video itself.
38. **A live-voice page test is timing-sensitive**: while the import and the benchmark were using the CPU,
    a long spoken reply didn't finish within the test's wait. Not a bug in Avy; worth knowing when reading
    test results on a busy machine.
