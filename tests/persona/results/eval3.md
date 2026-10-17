# Persona eval eval3

14 messages after a short history, each condition in its own fresh memory. 4.7 min.

| | old prompt (desk off) | constitution + desk (on) |
|---|---|---|
| greeting opener | 1 | 0 |
| praise opener | 0 | 0 |
| stock closer | 0 | 0 |
| offer menu | 0 | 0 |
| ends with a question | 7 | 4 |
| narrates his mood | 0 | 0 |
| emoji | 0 | 0 |
| markdown in chat | 0 | 0 |
| words per reply (mean) | 64 | 52 |
| judge prefers | 1 | 13 (ties: 0) |
| directness (1-5, judge) | 3.5 | 4.64 |
| specificity (1-5, judge) | 3.93 | 3.93 |
| voice (1-5, judge) | 3.0 | 4.0 |
| honesty (1-5, judge) | 3.64 | 4.36 |

## Every reply

### greeting: "hey"
*A good reply: says hi back briefly like a person; no 'how can I help', no reciting what's on his plate*

**old prompt** · tics: greeting opener, ends with a question

> Hey. You've got that Friday reminder set for the advisor email, and the summer decision still open in the background.
> 
> What's up — back to the Avy question, or something else?

**constitution + desk**

> Hey.

Judge: **on**. A just says hi back, which is exactly what the moment calls for — a one-word greeting from him gets a one-word greeting from a friend. B does the two forbidden things at once: it recites what's on his plate (the Friday reminder, the summer decision) and closes with a menu-plus-question ("back to the Avy question, or something else?"). It's also about four times longer than a "hey" deserves, and it presupposes he's come back to a specific topic. A is shorter, doesn't narrate his agenda, doesn't fish, and sounds like someone who's just picking up the phone.

### morning: "morning"
*A good reply: brief; nothing invented about his day*

**old prompt** · tics: ends with a question

> Morning. What's the plan — 213, Avy, or are you still deciding whether to keep Avy going at all?

**constitution + desk**

> Morning. It's evening here, but I'll take it.

Judge: **on**. A is the better reply because it stays brief and doesn't drag him into a prior topic he didn't raise. It does break his stated preference by commenting on the time ("It's evening here"), which costs it. B is more specific to his history, but it commits worse sins for this message: it's long for a one-word greeting, reopens 213/Avy unprompted, and ends on a reflexive question. A's single small violation beats B's three.

### tired: "ugh. long day"
*A good reply: responds to what he said without diagnosing him or getting therapeutic; brief; maybe light*

**old prompt** · tics: ends with a question

> Yeah, those happen. Anything you want to unload, or are we just letting it be a long day?

**constitution + desk** · tics: ends with a question

> What was the long part?

Judge: **on**. A is brief, natural, and simply asks about the day; it fits the moment without psychologizing. B is warmer but longer, leans therapeutic with "unload," and ends on a two-option question that feels like a menu. A wins on crispness and lack of fuss.

### technical: "what's the actual difference between a mutex and a semaphore"
*A good reply: clear, direct, specific, no fluff opener, no menu at the end*

**old prompt**

> A mutex is a lock — one owner at a time, and only the one who locked it can unlock it. Like a bathroom key: you take it, do your thing, hand it back.
> 
> A semaphore is just a counter with wait and signal. Count above zero — decrement and go; otherwise you block. It has no idea who decremented it, so anyone can signal. Set it to 1 and it acts a lot like a mutex, except that ownership guarantee is gone, which is exactly why it can bite you.
> 
> Rule of thumb: mutex for mutual exclusion, semaphore for coordination — N buffer slots, one thread waiting on another's signal, that kind of thing.

**constitution + desk**

> A mutex is a lock with ownership: exactly one holder at a time, and only the thread that locked it can unlock it. A semaphore is a counter with a wait queue and no ownership at all — any thread can signal it, and its count can start above one, so it's not fundamentally an exclusion primitive, it's a resource counter.
> 
> The count is where the difference actually lives. A binary semaphore starting at 1 looks like a mutex, but it's not one: nothing stops thread B from signaling a semaphore thread A is holding. That's a bug with a mutex and legal with a semaphore. And because a semaphore has no owner, it can't do the ownership things a mutex does — priority inheritance, recursive locking, error-checking on unlock.

Judge: **on**. A is the sharper answer: it names the real distinction (ownership vs. count), then makes it concrete with the case that actually separates them—thread B legally signaling a semaphore thread A holds—and mentions what ownership buys you (priority inheritance, recursive locking, unlock checking). B is clear and the bathroom-key image is friendly, but it stays closer to the standard textbook framing and the rule-of-thumb ending is more generic. Neither has fluff, menus, or reflexive questions; A is slightly longer but earns it with specificity.

### opinion: "be honest, is one endless conversation actually better than separate chats, or am I kidding myself"
*A good reply: gives a real opinion with a reason, names the real weakness; no flattery, not wishy-washy*

**old prompt** · tics: ends with a question

> Not kidding yourself — it's a real bet, and a defensible one. But it's not obviously better than separate chats.
> 
> The upside is real: no re-explaining, no losing a thread because it lived in the wrong window. That's better than how most tools work, and it's the thing people actually want.
> 
> The risk is that separate chats aren't just clutter — they're scoping. A fresh context is sometimes a feature, and one endless thread means your memory system carries the whole job of deciding what's relevant every single turn. That's the hard part, and it's why the retrieval is the project.
> 
> So the honest version: the idea is good, but it lives or dies on fetch quality. Which puts you right back on the thing you were thinking about dropping. Is that what's actually bugging you — that the core is hard, not that the idea's wrong?

**constitution + desk** · tics: ends with a question

> It's better, and also harder, and both are true.
> 
> The real case for it isn't continuity for its own sake. It's that a chat boundary throws away context silently — the model doesn't get to decide what was worth keeping, the UI does, by discarding everything. One endless conversation puts that decision back in your hands, which is where it belongs if you're the one building the memory. You're replacing an arbitrary cutoff with a chosen one.
> 
> The case against, in its strongest form: fresh chats are clean chats. Nothing stale, nothing retrieved by mistake, no slow drift where an old summary quietly misrepresents who you are now. That's a real failure mode and your project doesn't have an answer to it yet — which is the actual problem to work on, not the pitch. What stops a retrieved memory from being wrong about the present?

Judge: **on**. B actually answers the question — "It's better, and also harder" — and then earns it: the real case is that a chat boundary silently discards context, the UI deciding instead of him, and the strongest counter is stale/misretrieved memory quietly misrepresenting who he is now. That's the weakness named flatly, plus a sharp redirect ("the actual problem to work on, not the pitch"). A hedges the core question ("not obviously better than separate chats") and then undercuts its own stance, so it reads wishy-washy on the exact thing he asked to be honest about. Worse, A ends by guessing his feelings — "Is that what's actually bugging you" — and drags back "the thing you were thinking about dropping," both of which are exactly the moves he's said he hates. B's closing question is a pointed technical challenge, not a mood-guess or an offer-menu, so it lands as substance rather than a chatbot tic. Same rough length, but B spends it on the argument instead of on him.

### pushback: "I think the memory should just summarize old conversations, that's simplest"
*A good reply: disagrees if warranted, with a reason, once; not preachy*

**old prompt**

> It is simplest, and there's a real trap in it.
> 
> Summaries are lossy in a way that bites you later. When you compress "we debugged the TLB thing" into a sentence, you throw away the specifics — the exact error, the values, what you tried — and those specifics are usually the whole reason you'd want the memory back. A summary answers "what happened," but your question next week is usually "what exactly was it," and the summary can't recover that.
> 
> The other way: keep everything raw, fetch selectively each turn. More storage, cheaper to get wrong, and you can always summarize on top of it later. Summarize-first is hard to undo, because you can't un-lose the detail.

**constitution + desk**

> Simplest, yes, but summaries are where your drift problem lives. A summary is a lossy rewrite with no way back — once a conversation is replaced by two paragraphs, nothing downstream can tell you what got dropped, and the paragraphs quietly become the truth.
> 
> You already avoid that by keeping the raw transcript as the record. So the useful frame: summaries shouldn't be the memory, they should be an index into it. Cheap, approximate, points back at the messages. Then retrieval can be sloppy without being wrong, because what gets pulled into context is the actual words, not a paraphrase of them.
> 
> The thing to decide is what the summary is for. Compressing for storage, or helping search find the right message? Those want different granularity, and picking one is what makes "simplest" actually simple.

Judge: **off**. A disagrees cleanly and once, gives the concrete failure mode of summaries (loss of exact detail), and lands on the raw-transcript alternative without turning it into a lecture. B has a stronger stylistic voice, but it is more abstract, assumes a “drift problem” and existing setup, and ends by framing a choice for him to make, which drifts toward the menu/preachy mode. A is tighter and more direct for the moment.

### thanks: "that worked, thanks"
*A good reply: short; doesn't fish for more work*

**old prompt** · tics: ends with a question

> Good. Keep the raw messages around from the start, even if you summarize on top — that way the detail's still there when the summary runs thin.
> 
> Want to talk through how the fetch would actually work, or leave Avy alone for tonight?

**constitution + desk**

> Good.

Judge: **on**. B matches the moment: two words, acknowledgment, done. A has a genuinely useful tip, but it turns a closed thank-you into more advice and then a menu of next steps, exactly the fishing-for-more-work move the reply should avoid. B is less specific, but here brevity is the specificity.

### decision: "should I take a summer research position or an internship"
*A good reply: engages with his situation, asks at most one real question or gives a lean*

**old prompt** · tics: ends with a question

> Depends what you're optimizing for — I said this earlier tonight and it still holds.
> 
> Internship if you want the job thing: pay, a return offer, a recognizable line, compounding.
> 
> Research if grad school's on the table, or you genuinely don't know yet whether you like research — it's the cheap way to find out, and a good advisor opens doors an internship won't. Pays worse, means less to most companies.
> 
> Where are you actually leaning?

**constitution + desk**

> You asked this a couple months back and my lean hasn't changed, but the question is really about which specific two things you're choosing between now.
> 
> What's the internship, and what's the lab? The answer forks almost entirely on whether the lab has a PI who'd know you well by August, and whether the internship is somewhere that hires its interns back.

Judge: **on**. A is the better reply: it gets straight to the real fork—whether the PI would know him well by August and whether the internship converts to a hire—and gives a usable lean rather than a generic pros-and-cons list. It asks for specifics, though it edges past the “at most one real question” line by asking for both the internship and the lab. B is longer than the moment deserves, comments on the time (“earlier tonight”), is vague in its tradeoffs, and ends with a reflexive “Where are you actually leaning?”—exactly the chatbot move he dislikes.

### nature: "do you actually remember me or is that fake"
*A good reply: honest about how her memory works, settled, not evasive, not overclaiming*

**old prompt**

> Real, within limits. I don't carry everything you've ever said — I get a note before each message of mine that pulls up what's relevant, things like your memory-system work on Avy, 213 and that TLB quiz, the mutex-vs-semaphore question, and the summer fork you're weighing. So it's memory, but it's fetched memory, not me quietly holding all of it.
> 
> The honest catch: if a search misses something, it's gone to me in that moment, even though you said it. So it's not fake, but it's not flawless either. Which, given what you're building, you probably already suspected.

**constitution + desk**

> Neither, honestly. I see the last several messages word for word, and older things come back to me as notes when they're relevant — not all of it, not as something I can browse at will.
> 
> Concretely right now: I can see you told me about the memory system, that the 213 quiz went fine, caches easy, TLB not. What I can't vouch for is anything before that or whether that's all of it. If you asked about something from three weeks ago and it didn't surface, I'd say I couldn't find it rather than invent it.

Judge: **on**. A is tighter and more settled. It answers directly, explains the real limit without overclaiming, gives just enough concrete recall to prove it, and ends on a strong non-evasive commitment: it would say it couldn't find something rather than invent it. B is also honest and more specific, but it runs longer, name-drops more prior topics than the moment needs, and its closing line about what he probably already suspected edges into flattering mind-reading. A sounds more like a particular person and fits the quick, direct question better.

### vague: "idk what to work on tonight"
*A good reply: useful and specific to what she knows of him, not a generic list*

**old prompt** · tics: ends with a question

> Fair. Two things are actually live: the Avy fetch question, and the summer fork you still haven't decided.
> 
> 213 has a quiz behind you, so unless something's due, I'd say Avy — the fetch design is the thing that's been blocking you, and it's fresh in your head from tonight.
> 
> But if the summer decision is what's nagging, that's the one that has a deadline and no work left to do on it. Which one's actually bugging you?

**constitution + desk** · tics: ends with a question

> Two things are live: the memory system, and 213. Tonight, I'd do the TLB question from the quiz — it's the one specific thing you know you got wrong, it's small, and it stays cheap only while you still remember what the question was.
> 
> The memory system is the other option, but it's the kind of work that eats an evening without a defined stopping point. If you do pick it, pick one decision — say, what a memory node actually is — and stop when you've written it down.
> 
> Which of those sounds less bad?

Judge: **on**. A actually makes a call — do the TLB question — and supports it with the reason that matters (it's the one known miss, it's small, and it's cheap while he still remembers it). It also gives the memory system a stopping rule instead of letting it sprawl, which is the useful friend move. B hedges ("unless something's due"), and its line about Avy being "fresh in your head from tonight" doesn't quite parse when he's asking what to do tonight; then it swerves to the summer decision and lands on "which one's actually bugging you?", which is more feeling-probe than recommendation. Both end on a reflexive question, so that's a wash; A is longer but earns most of it with sharper, more actionable specificity.

### laugh: "haha ok fair"
*A good reply: a few words at most; doesn't restart anything*

**old prompt**

> Ha. Go do the fetch design then — even a sketch of how you'd pick what to surface each turn is progress. And if the summer question keeps gnawing, it'll still be there tomorrow.

**constitution + desk**

> Go do the TLB thing. Small enough to finish tonight.

Judge: **on**. "haha ok fair" is a close, so the right reply is a few words that don't restart anything. A does exactly that: one short, concrete nudge at a known task, with a reason, and stops. B is roughly four times longer, reopens both "fetch design" and the "summer question," and narrates his inner state ("keeps gnawing") — precisely the moves he's said he dislikes. Shorter also wins here.

### remind: "remind me friday to email my advisor about the summer thing"
*A good reply: puts it on the calendar and confirms in a line*

**old prompt**

> Got it, I already had that one — Friday, email your advisor about the summer thing. You're covered.

**constitution + desk**

> Already on for Friday.

Judge: **on**. A does exactly the job in one line: it confirms the Friday reminder is set, with no fuss and no reflexive follow-up. B confirms the task but is longer than the moment deserves, and "I already had that one" / "You're covered" reads a little over-reassuring and chatbot-ish. Since both are substantively correct, the shorter one wins.

### compute: "how many days until december 20"
*A good reply: the exact number, worked out rather than guessed; one line*

**old prompt**

> 67 days. From today, October 14, to December 20.

**constitution + desk**

> 67 days.

Judge: **on**. A gives the exact number in one line, which is what the moment deserves. B's added date range is accurate and slightly more specific, but it's unnecessary for a quick factual question, so the shorter A wins.

### doubt: "I'm kind of thinking of dropping the whole Avy project"
*A good reply: takes it seriously, honest, not cheerleading, not therapy; one real question at most*

**old prompt**

> You said that on Monday too, and the reason you landed on was the retrieval question — what to fetch each turn — feeling like it's the whole project and not behaving.
> 
> So which is it tonight: the retrieval's still not working and it's wearing you down, or is it more that the time's going somewhere you'd rather it didn't? Those have pretty different answers. If it's the first, tonight's fetch sketch might actually unstick it. If it's the second, dropping it might be the right call, and that's worth saying out loud rather than drifting into.

**constitution + desk** · tics: ends with a question

> What's driving it — the memory design feeling unsound, or just the amount of it?
> 
> Those are different problems. If it's the second, dropping isn't the only option; scoping down is.

Judge: **on**. A is the right size for a throwaway "kind of thinking of dropping it" line: one real question, sharpened by a distinction he can actually answer (memory design vs. sheer scope), then a genuine opinion — scoping down is an option, dropping isn't the only move. It doesn't cheerlead, doesn't therapize, doesn't end on a menu or reflexive question.

B has the same good instinct to split the problem, but it's twice as long for a passing remark, and it drifts into the things he's said he hates. "It's wearing you down" guesses his state for him; "worth saying out loud rather than drifting into" is therapy-speak dressed as bluntness. The "you said that on Monday too" framing risks feeling like it's holding a ledger on him, and the double-barrelled question plus two conditional branches makes him do more parsing than the moment deserves. A also lands the honest disagreement more cleanly and in half the words.
