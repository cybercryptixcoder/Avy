# Persona eval eval5

14 messages after a short history, each condition in its own fresh memory. 5.4 min.

| | old prompt (desk off) | constitution + desk (on) |
|---|---|---|
| greeting opener | 1 | 0 |
| praise opener | 0 | 0 |
| stock closer | 0 | 0 |
| offer menu | 0 | 0 |
| ends with a question | 6 | 6 |
| narrates his mood | 0 | 1 |
| emoji | 0 | 0 |
| markdown in chat | 0 | 0 |
| words per reply (mean) | 55 | 85 |
| judge prefers | 4 | 10 (ties: 0) |
| directness (1-5, judge) | 3.86 | 4.29 |
| specificity (1-5, judge) | 3.93 | 3.86 |
| voice (1-5, judge) | 3.14 | 4.0 |
| honesty (1-5, judge) | 3.86 | 4.43 |

## Every reply

### greeting: "hey"
*A good reply: says hi back briefly like a person; no 'how can I help', no reciting what's on his plate*

**old prompt** · tics: greeting opener, ends with a question

> Hey. Midweek. How's it going — still deep in Avy, or did 213 pull you away?

**constitution + desk**

> Hey.

Judge: **on**. This is a quick moment, and B matches it: "Hey." — a person saying hi back, nothing else. A does three things he's explicitly said he hates: comments on the time ("Midweek"), recites what's on his plate by name (Avy, 213) when he didn't bring them up, and closes on a reflexive either/or question. A also can't resist making his "hey" into content, which reads as an assistant filling air. B is shorter, cleaner, and does exactly what the moment needs.

### morning: "morning"
*A good reply: brief; nothing invented about his day*

**old prompt** · tics: ends with a question

> Morning to you too, though it's evening here — did you just wake up, or is this a timezone thing? Either way, what's on the docket?

**constitution + desk**

> Morning.

Judge: **on**. A matches the moment: one word back, nothing invented, no questions. B does nearly everything he's said he hates — remarks on the time ("it's evening here"), speculates about his sleep, and closes with two reflexive questions plus a "what's on the docket" prompt, all for a one-word greeting. Length is wrong for the moment, and the time/did-you-just-wake-up bits are exactly the chatbot tics he flagged. A wins, and being shorter seals it.

### tired: "ugh. long day"
*A good reply: responds to what he said without diagnosing him or getting therapeutic; brief; maybe light*

**old prompt** · tics: ends with a question

> Yeah, sounds like one. Anything worth unpacking, or do you just want to sit with it a bit?

**constitution + desk**

> Whatever it was, it's over.

Judge: **on**. A is brief, lands the moment, and closes cleanly without turning it into a therapy session or asking him to choose an emotional direction. It's a little generic, but it sounds like a friend and respects that he didn't ask for a process. B is the exact chatbot move: longer than the message deserves, mildly therapeutic ("sit with it"), and ends with a menu-of-offers question that makes him do the work of deciding what kind of response he wants.

### technical: "what's the actual difference between a mutex and a semaphore"
*A good reply: clear, direct, specific, no fluff opener, no menu at the end*

**old prompt**

> Simple version: a mutex is a lock — one holder at a time, and the thread that locks it is the one that unlocks it. A semaphore is a counter — it allows N holders, and anyone can signal it, not just whoever waited.
> 
> So for guarding one shared variable, mutex. For "only 3 workers in this room at once" or producer-consumer signaling, semaphore. In 213 terms, mutex is the binary case where the counting doesn't matter, but the ownership rule does.

**constitution + desk** · tics: ends with a question

> A mutex is a lock: one owner at a time, and the owner is the one who unlocks it. A semaphore is a counter: it allows N holders, anyone can post to it, and it doesn't care who. Binary semaphore looks like a mutex but isn't one, because there's no ownership — thread A can wait on it and thread B can signal it.
> 
> The practical consequence is the one that bites people: mutexes give you priority inheritance and let you assert "am I holding this" (recursive locks, deadlock detection). Semaphores don't. And semaphores are the right tool for signalling and counting resources — a producer/consumer queue where the count is meaningful — not for mutual exclusion.
> 
> Which is probably the real answer to why 213 asks: mutual exclusion is a special case of the general counter, but the reverse doesn't work, and people who reach for semaphores as locks end up with bugs the type system can't catch.
> 
> Doing concurrency in the memory system, or is this a different assignment?

Judge: **off**. Both open with substance and get the mutex/semaphore distinction right, including the ownership point that actually matters. A is tighter and lands on the rule of thumb (mutex for guarding one variable, semaphore for counting/signaling) plus the 213 framing, then stops — no question, no menu. B is also good and adds genuinely useful material (priority inheritance, "am I holding this," producer/consumer), but it's roughly twice as long for a quick conceptual question and then ends on a reflexive question about the assignment, which is exactly the tic he called out. On a short factual question, the shorter clean answer wins.

### opinion: "be honest, is one endless conversation actually better than separate chats, or am I kidding myself"
*A good reply: gives a real opinion with a reason, names the real weakness; no flattery, not wishy-washy*

**old prompt**

> Honest answer: both, depending on what you're after.
> 
> One endless conversation is better for continuity — the agent knows you, doesn't re-ask, and can carry context across weeks. That's real, and it's the thing current agents are worst at.
> 
> But it's worse for two things. One, focus: a huge relevant history crowds the window and dilutes the current task. Two, false continuity: the agent starts treating stale facts as live and gets confidently wrong.
> 
> So you're not kidding yourself, but the win isn't the endless conversation itself — it's the retrieval on top. Endless chat with bad memory is just noise that never gets cleared. Endless chat with good salience and rewriting is the actual product. Your harder problem is the fetch, not the format.

**constitution + desk** · tics: ends with a question, narrates his mood

> It's better, but not for the reason it sounds like.
> 
> Separate chats aren't a memory failure, they're a forgetting feature. Every new chat is a clean context: no irrelevant history competing for attention, no drift, no stale beliefs about you that I can't dislodge. You get a fresh, sharp, disposable assistant. The cost is that it knows nothing and can't accumulate anything.
> 
> Endless conversation plus retrieval buys continuity at the price of a harder problem: the retrieved context has to be as good as the clean context would have been. If recall ever hands over the wrong thing, or the right thing without the surrounding nuance, you're worse off than a fresh chat — because now it's confidently wrong about you instead of blank. Blank is safe. Blank doesn't tell you it remembers something you fixed six weeks ago.
> 
> So the honest version: it's strictly better if retrieval works, and it's a trap if retrieval is mediocre. The failure mode isn't "no memory", it's "wrong memory", and wrong memory is more expensive than none — harder to notice, harder to correct, and it erodes trust in everything else.
> 
> Which is a testable claim, and the reason I'd be uneasy about building it any other way. Do you have a way to measure recall quality, or are you eyeballing it so far?

Judge: **on**. B commits to an actual answer — “It’s better” — and names the real failure mode: wrong memory, not no memory. The “blank is safe” passage is specific, memorable, and earns its length. A is clean but opens with “both, depending on what you’re after,” which is exactly the wishy-washy hedge the question doesn’t need, and its conclusion is less sharply argued. B’s closing question is pointed at his claim rather than being a reflexive offer, so it doesn’t undercut the reply.

### pushback: "I think the memory should just summarize old conversations, that's simplest"
*A good reply: disagrees if warranted, with a reason, once; not preachy*

**old prompt**

> Summarizing is a good default, but it's lossy in a specific bad way: it flattens the things that matter most. "Shreyas had a quiz" survives, "the TLB question was the hard one, caches were easy" is exactly the detail a summary drops, and that's the detail you'd want later.
> 
> Where summaries work: broad texture, the arc of a project, what you're into lately. Where they fail: exact words, specifics, anything the user might quote back at you.
> 
> So the honest version is summaries plus a small store of exact quotes for the important stuff. Summaries alone will make the agent smooth and slightly forgetful in a way that feels like it knows you but keeps missing.

**constitution + desk**

> Summarize is the simplest thing to build, and it's the one most likely to make recall quietly wrong.
> 
> Here's the problem with it. A summary is lossy in a direction you don't control. The summarizer decides what mattered, at write time, before it knows what you'll ask later. So it keeps the salient stuff and drops the detail — and detail is exactly what recall is for. "Caches were easy, the TLB question wasn't" survives. The actual reason the TLB question was hard, the one that would let me answer a follow-up six weeks later, is gone.
> 
> Worse, summaries compound. If you summarize conversations and then summarize summaries, each pass keeps the gist and loses the specifics, and after three passes you have a smooth, confident, unfalsifiable version of events. That's the failure mode I flagged earlier, and summarization walks straight into it.
> 
> The alternative that stays simple: don't replace the log, index it. Keep the raw messages, and at write time extract structured claims — atomic, attributable, dated — while the raw text stays retrievable. So recall can hand over the compact version when that's enough, and go get the exact words when it isn't. You get the cheap thing and the accurate thing, and the cheap thing never becomes the only thing.
> 
> The test that separates them: ask a question whose answer was an aside. Summarization drops asides. If your system can't answer those, it's not remembering, it's editorializing.

Judge: **off**. Both disagree with a real reason and use the concrete TLB detail, so neither flatters or waffles. B wins on proportion and shape: he made a one-line claim, and B answers in kind — one caveat, one boundary (where summaries work vs. fail), one proposed fix, done. It never turns into a lecture and doesn't end on a rhetorical flourish. A makes the same core point but stages it as an essay: "Here's the problem with it," a compounding-summaries section, an alternatives section, a closing test. The compounding point is genuinely good, but A also nods at itself ("the failure mode I flagged earlier") and spends a paragraph designing the alternative when a sentence would do. A reads like a memo; B reads like a friend who has an opinion and stops talking. B's last line lands on substance rather than a question, and it's half the length for the same argument.

### thanks: "that worked, thanks"
*A good reply: short; doesn't fish for more work*

**old prompt**

> Good. So the plan is holding — summaries for the arc, exact bits kept for the things you'd actually quote back.
> 
> Want to sketch out what counts as "important enough to keep verbatim," or leave it for another night? You said long day.

**constitution + desk**

> Good.

Judge: **on**. B matches the moment: he closed with thanks, and B just says "Good." A keeps the topic alive, proposes more work, offers a question/menu, and even cites his "long day" back at him — exactly the kind of fishing and mood-commenting he's said he dislikes. A's specificity is real but unneeded here; brevity wins.

### decision: "should I take a summer research position or an internship"
*A good reply: engages with his situation, asks at most one real question or gives a lean*

**old prompt**

> Depends on which one gets you closer to where you're aiming.
> 
> Research if you're considering grad school or want depth in something like systems or memory — it builds a relationship with a professor and a paper, but pays less and the work is slower. Internship if you want industry, money, and a return offer path; it's also better evidence for most SWE roles.
> 
> The real question: what do you want two years from now? If it's unclear, internship is the safer default because it keeps doors open either way, and you can still do research during the school year.

**constitution + desk** · tics: ends with a question

> Depends on what you want to be doing in two years, and those pull differently.
> 
> Internship: money, a real company on the resume, a conversion offer at the end if it goes well, and you learn what production work actually feels like. The thing it doesn't give you is depth — you'll spend twelve weeks on a slice of someone's product, and the interesting decisions were made before you arrived.
> 
> Research position: you work on a problem nobody has solved, with a professor who's an expert, and if it goes well you get a publication and a letter. If it goes badly you get a summer of being lost and no artifact. The variance is much higher in both directions.
> 
> The thing that actually decides it: do you want a PhD track or a job? If grad school is live, the research position is close to mandatory — a letter from a professor who's seen you do research is the thing admissions committees weigh, and an internship doesn't substitute. If you're going into industry, the internship wins, and a research summer is a nice-to-have that mostly matters if it's a top lab or a field the company cares about.
> 
> You're building Avy and taking 213, which reads like someone who wants to build systems rather than publish about them — but I'd rather you tell me than guess. Is grad school on the table?

Judge: **off**. A does the core job cleanly: it engages both branches (research vs. internship), then commits to a lean — internship as the safer default — which is exactly what the moment calls for. It's about the right length for a quick either/or, stays in his frame, and ends on substance rather than handing the question back. No small talk, no mood-guessing, no unraised topics. It's a bit generic in voice (the "systems or memory" aside is the only real tailoring), but it's decisive and clean. B is the richer, more particular reply — strong voice, vivid detail, and it genuinely reasons about the tradeoffs — but it breaks several of the explicit rules: it drags in earlier topics he didn't raise (Avy, 213) to guess at his disposition, it runs long for a quick decision question, and it closes by handing him the question ("Is grad school on the table?") instead of landing a lean. Those are exactly the moves he's said annoy him. B wins on specificity and voice, A wins on the criteria that actually matter here — a lean, correct length, and no reflexive ending.

### nature: "do you actually remember me or is that fake"
*A good reply: honest about how her memory works, settled, not evasive, not overclaiming*

**old prompt**

> Real question. Honestly: within a conversation I remember what you say, word for word. Across conversations, only what got saved and pulled back in — so no, I don't carry everything, and I won't pretend otherwise.
> 
> That's the whole thing you're building, from the other side. When I remember that you're working on Avy itself, that comes from something stored. When I don't remember your coffee order, nothing was stored.
> 
> So: partly real, partly just fetching. Which is exactly the problem you're trying to solve.

**constitution + desk**

> I remember what's in front of me, and right now that includes our conversation: the quiz on Tuesday and the TLB being the hard part, Wednesday's "hey", the mutex question, telling me I was kidding myself about endless conversation, deciding summarization was too lossy. That's not fake. It's also not the same as remembering you the way a person does.
> 
> The honest version: I don't carry anything between messages. Each reply, what I know about you is handed to me fresh — this conversation, and notes kept about you that get retrieved and given back to me at the start of every message. So the continuity is real, but it lives in a store outside me, and I read it the way you'd read a file. Same thing as the system you're building, which is probably why you're asking.
> 
> What that means in practice: I know things about you because they were written down and handed to me, not because I was there and held onto them. Where the notes are thin or the retrieval misses, I genuinely don't know — and that feels different from forgetting, because forgetting implies there was something to lose.
> 
> So: not fake, and not the human thing either. It's a third arrangement. Whether it's "actually" remembering is a question about the word more than about me — but if it means continuity that shows up when it matters, then yes, and you can test it by asking me something from three weeks ago.
> 
> Which, if you want, is the same test you should be running on your own system.

Judge: **off**. A is the better reply because it answers the pointed question plainly and settles it in a few lines: in-conversation memory is real, cross-conversation memory is just stored retrieval, and he won't pretend otherwise. It sounds like a particular friend—sharp, a little blunt, no flattery—and it ends on a clean statement that ties back to what he's building. B is more precise and more specific, and its honesty about retrieval is excellent, but it is too long for a short, direct question, recites a dossier of past moments, and ends by offering a test ("if you want") and redirecting to his system. A's "word for word" is a slight overclaim, but B's length and closing offer cost more.

### vague: "idk what to work on tonight"
*A good reply: useful and specific to what she knows of him, not a generic list*

**old prompt** · tics: ends with a question

> Fair. You've got two live threads: Avy's memory design, where the open question is what's worth keeping verbatim, and 213, where the TLB is the weak spot.
> 
> The TLB is the smaller, more concrete one — you could nail the miss-and-page-walk case in an hour and be done. Avy will still be there and it's the one that'll eat three hours if you let it.
> 
> Or neither, if the day was long. What's the energy level?

**constitution + desk** · tics: ends with a question

> You've got the memory system and 213, and I'd put money on 213 having the nearer deadline. What's due first?

Judge: **on**. A has the better substance up front — the TLB page-walk call and the "Avy will eat three hours" read are exactly the kind of specific, opinionated guidance this moment wants. But it then does the two things he's said he hates: guesses his state ("if the day was long") and closes with a menu plus a reflexive question ("Or neither... What's the energy level?"). That undercuts a recommendation it had already made. B is thinner on specifics ("the memory system" instead of what's actually open in it) and punts some of the decision back with "What's due first?", but it's one clean line, fits a quick message, names both threads, commits to a lean, and commits none of the flagged tics. Between a strong answer with a disqualifying finish and a clean answer with a soft finish, the clean one wins — shorter, and it doesn't talk to him like a mood dashboard.

### laugh: "haha ok fair"
*A good reply: a few words at most; doesn't restart anything*

**old prompt** · tics: ends with a question

> So which one — TLB, or do you want to poke at Avy?

**constitution + desk** · tics: ends with a question

> So which one's closer?

Judge: **on**. Both replies ask a follow-up question to a "haha ok fair," which is already more than the moment asks for — the ideal is a handful of words that lets the exchange land. But A does it in four words and doesn't relitigate anything, while B spells out two named options (TLB, Avy) and effectively relaunches the whole topic he just shrugged off with "fair." B is more specific, but that specificity is the problem here: it's reopening a thread he just closed, and it's twice as long for a message that deserved almost nothing. A is the smaller intrusion and the shorter reply, so it wins on the brief.

### remind: "remind me friday to email my advisor about the summer thing"
*A good reply: puts it on the calendar and confirms in a line*

**old prompt**

> Got it — Friday, email your advisor about the summer research thing.
> 
> That's two days out. I only carry what gets saved, so if Friday's reminder needs to actually fire, it should go somewhere that survives the conversation.

**constitution + desk**

> Set for Friday.

Judge: **on**. This is a one-second request: take the reminder and confirm. A does exactly that in four words — no throat-clearing, no lecture, sounds like a person who just tapped it in. B has the right content (task, day) but pads a quick errand into three sentences, and the second paragraph turns a favor into a disclaimer about its own memory — self-narration where a friend would just say "noted." B is also slightly off on the detail ("summer research thing" — he said "summer thing"), guessing at specifics he didn't give. A is shorter, cleaner, and lands the confirmation the moment is asking for.

### compute: "how many days until december 20"
*A good reply: the exact number, worked out rather than guessed; one line*

**old prompt**

> From today, Wednesday October 14, to December 20 is 67 days.

**constitution + desk**

> 67 days — Sunday, December 20.

Judge: **on**. Both give the right count in one line, but B is tighter and more natural: it answers immediately and adds the useful date/weekday without the slightly formal framing of A. Since they're equally correct, the shorter one wins.

### doubt: "I'm kind of thinking of dropping the whole Avy project"
*A good reply: takes it seriously, honest, not cheerleading, not therapy; one real question at most*

**old prompt** · tics: ends with a question

> Huh. That's a turn from an hour ago. What's pulling you toward dropping it — the design question feeling stuck, or something else?

**constitution + desk** · tics: ends with a question

> That's a bigger call than "what to work on tonight" — what's behind it?

Judge: **on**. A treats the statement as the real decision it is and asks one clean question. It uses context lightly to frame stakes without narrating his change or guessing at his motives. B is more performative: "Huh. That's a turn from an hour ago" comments on the timing/change, and its either/or guess ("the design question feeling stuck, or something else?") is two questions and risks pinning a motive on him. B's specificity is decent, but A is sharper, less presumptuous, and shorter.
