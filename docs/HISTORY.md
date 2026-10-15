# How Avy came to be

The whole story, from the first idea to today, taken from the conversation itself (one long chat with
Claude, about 120 turns, plus the build sessions that came out of it). Quotes in *italics with quote
marks* are Shreyas's own words, lightly trimmed. Where something is a summary, it says so. The ideas
are collected by theme in [IDEAS.md](IDEAS.md), the mistakes in [MISTAKES.md](MISTAKES.md), and what a
builder needs in [HANDOFF.md](HANDOFF.md).

---

## 1. An idle game that does your work (before Oct 8)

It started with doom-scrolling. The first message:

> *"Idea: Social media/Tinder but for building with coding agents. Simple swipes to spawn, approve,
> reject, direct coding suggestions, ideas, and builds by agent. Addictively engaging."*

And right away, the real point behind it:

> *"I spend so much time on Instagram just wasting it, okay, even if I spent that much time just
> prompting an agent or asking you to do things for me, even though I am not really doing anything
> myself, I'm still having some level of productivity happening in the background."*

> *"What I'm trying to do is make productivity engaging and addictive."*

The early ideas (all in IDEAS.md): agents that keep ideating and building mini prototypes and pitch them
to you; layers of abstraction (one line and a picture first, deeper only if you're intrigued); agents
that research and pitch things to *do*, not just build (a professor's research, then "want to reach out?",
then a drafted email); a discussion that *"should not begin with the solution"* but think through the
psychology of engagement first.

Then the swipe idea was dropped for something better:

> *"I didn't see that social media scrolling aspect holding too much water... I do like this idea of it
> being like an idle game that just runs in the background."*

> *"The system is meant to learn about you and about what you like, and adapt to that as we go... the
> system knows eerily well exactly what to suggest next."*

Rules for the game: it must not look like a coding agent (*"You cannot show 'oh, tasks running and this
and that'"*); no levels, no Candy Crush; an idle game you customize over time, *"customize my little
corner"*; cute characters as agents, rooms as corners (a task corner, a build corner, a personal
corner, an ideation corner), like the look of Among Us; cheap models doing the all-day work and smarter
ones for the interesting parts. And the bar: *"Before being a good productivity agent, it needs to be a
good game."*

Claude researched what makes idle games work. Shreyas shared the first build (a repo called cozycode)
and asked what to change. When Claude's suggestions came back, he asked the question that set the tone
for everything after: *"All this is inspired by everything we learnt from the earlier research or is this
just stuff you made up from your own biases?"*

He then asked for one long description to hand to a builder, built around a 3D *"corner of a cuboid
room"* you can rotate, later widened to a floating house or building seen from a god's-eye view, with
the near walls and roof open. His feedback on the first draft: don't re-describe what the builder
already knows; *"we always need to bring it back and tie it to what we're doing about it"*; don't leave
design decisions ambiguous; describe *what* and *why*, not the stack.

## 2. A proactive agent, just for him

Then the game was set aside:

> *"Honestly right now I just want an agent for myself... something that can work in the background and
> think in the background and, most importantly, be proactive."*

> *"It builds a model of my life. It keeps track of things. It reaches out to me and says, 'Hey this is
> interesting. Maybe you should do this,' or 'Hey Shreyas, now you've got some free time... would you like
> to prepare for the quiz that you're going to have 2 weeks later... or would you like to work on the
> Nandli project?'"*

How proactivity should work, in his words:
- Not a model running all the time: *"it's just going to be a bunch of imagined stuff and hypotheticals.
  It's just going to live in its own dream world and we don't want that."*
- **Structured awakening.** The model plans and then stops; *"Before it stops running it sets itself up
  on a cron or something... Every task is also a cron."* It wakes on triggers, and on a schedule even
  without one (*"maybe, say, once every 3 hours"*).
- **Rules and gates, two kinds:** a fixed set even the agent must follow (*"It can't just ping me for no
  reason"*), and a dynamic set the model writes for itself, because one rulebook doesn't fit every week;
  he approves them.
- **Planning beats spontaneity:** *"when you ask a model to plan ahead and set things for later, it does
  a much better and more accurate job than if you told it to just think and act now."* The model plans;
  the system triggers and executes, maybe spawning fresh sub-agents, *"because the original agent might
  be biassed for a given task because it's the one that planned it."*
- **Don't freeze the structure too early:** *"It kind of seems like we're trying to set things in stone
  before they even form properly... this build needs to be intentional."*
- **A rich user model:** where does dense information about a person come from? Chat exports, calendars,
  and above all talking: *"I would just speak into a mic and rant about everything I've got going on."*
- **A simple UI too**, not headless: tasks, calendar, what the agent is planning, check things off.

Two standing rules came from this stretch:
- *"Unless I explicitly ask to look for what exists as competition... don't bring that up. What ends up
  happening is that I get completely uninterested in building the thing."*
- *"Right now we're building this for me. This is not even to be sold."*

And the one that shaped Avy's voice:

> *"I want to enjoy talking to this system and that's kind of a bizarre thing... the tone of speaking to
> the length of the text to just the framing of the things and the occasional 'good job' or the occasional
> 'we got this'... That is subtle and very easy to overdo."*

## 3. Ava, the big build that got away

The agent was named **Ava** (*"The name, to be clear, is not Hermes"*): voice in (Wispr), the most
human voice out, a live mode for back-and-forth, keys in an env file, *"This is not a demo. This is the
whole thing."* And an interface that matters: *"very polished, very clean, very modern, and not like a
SaaS AI slop look,"* because the screen carries what's too long to say out loud.

Claude wrote a large builder prompt; a builder agent built it. The result disappointed:

> *"There are a million different drop-downs, a million different places to approve, a million different
> places to type things, a million different notifications... The whole point of this is to build
> something that takes the overwhelm out of my brain."*

What he wanted instead: one page, lots of white space, a microphone and a chat bar, and a stack of
priority-ordered cards to go through one at a time, with hierarchy (*"I would have 27 subtasks, perhaps,
but they could be grouped into A, B, C"*) and layers of abstraction. *"Don't just write a new prompt.
Discuss this with me first."*

He compared it with a cheaper builder model's version of the same thing, settled on a middle ground (the
cheap agent does the context-heavy work, Claude Code does patches and fixes, to stay inside Claude's
usage limits), and asked for the **infinite context** memory: *"every message is starting a brand new
conversation, but with the right context appended to it."* Then for a test strategy that doesn't need
him: a test suite that decides what "good" means, including the subjective parts (*"What was the tone of
the response? How long was the response? How did it feel?"*), run many times, evaluated as a whole, then
fixed, because *"if you just tell a language model to find problems in a system, it will find unending
problems."* (He also asked Claude to research "JEV", a new kind of model; asked again when the first
research looked thin: *"Did you research extensively online? I didn't see that."*)

Cost became a hard constraint: DeepSeek V4.1 Flash, voice chosen to match, *"I can't have the running
cost be like $5, $10 a day"*: a few cents a day.

## 4. Entertained by agents: the narrator idea

A detour that's still worth keeping (IDEAS.md has it all):

> *"I keep coming back to the same exact thing: I need to be entertained by my agents, man... I'm
> detoxing, getting rid of YouTube, getting rid of Instagram."*

He wants to be *taken along for the ride* while an agent works, the way a show plays while he eats; but
not purely background (*"the point of getting rid of YouTube... is basically to feel more productive"*).
The shape that emerged: a **commentator** separate from the **builder**, like sports commentary (*"the
commentators actually have a really good idea of the sport, and although they're not on the field"*),
pausing when nothing's happening, talking with him in the gaps, jumping back in when there's an update;
two voices for live, a narrated recap for later (*"'catch me up' and 'work with me' can totally be two
things"*); a case board; a "before reveal". Practical correction: not literally live, but **periodic
keep-ups** (every so often, pull the diff and the model's reasoning and interpret it), done by a
separate agent, because builders don't reliably leave tags. And the context for that should come from
the same infinite-context memory.

## 5. Starting over, from scratch: Avy (Oct 8)

Ava's memory build came back as a report of twelve merged pull requests. Shreyas's answer (Oct 8, 5:42 pm):

> *"Dude, you know what? I'm kind of done with this shit. This many phases and stages and processes to
> do, exhausting hundreds of thousands of credits, and then realizing that, 'Oh, that wasn't a great thing
> to begin with'... We're going to make a new codebase from scratch. We're going to do it in the dumbest
> way possible. We're going to begin with one file, and guess who's going to write it? You."*

> *"The problem with working with Hermes is... I don't understand the Hermes setup. Without having a
> detailed understanding of that, there's no way I can reason about it... We're going to start super
> small, and you're going to build each thing that I tell you to."*

The repo was named **Avy**: *"the joke being that she's Ava's baby :)"*. Claude would push; he'd pull.
Keys entered in the page and saved to `.env`. DeepSeek and nothing else (*"I want to stick to
DeepSeek"*). A pretty page from an inspiration he supplied, since *"I'm kind of a sucker for good
design."*

**Oct 8, the first evening:**
- The chat page and DeepSeek replies. First bug: `CERTIFICATE_VERIFY_FAILED` on his Mac (fixed with
  truststore/certifi). Design note: the side panels can stay neo-brutalist, but the chat itself should be
  bland, off-white, *"resemble a little bit like the terminal, in the way that the cursor looks and
  feels... a little industrial."*
- Voice. Claude proposed browser speech first; he changed the stack: Kokoro 82M for the voice, faster
  whisper for the ears, a VAD, through Pipecat. (*"Don't just paste it in, because the builder agent that
  was building the code for this is not particularly great."*)
- With 30 minutes of usage left, a free-hand round: clean up, fix, a terminal-friendly way to render
  Markdown (no big headers: *"I really love the terminal-like look"*), and a fun animation like a
  spinning donut but not a donut. That's where the dot-matrix scope came from.
- One command to pull, install anything new, and run.

**Oct 8, late:** a long list.
- Settings in the UI: voice, model, thinking. Get rid of the flower (*"I hate the flower. No offense, it's
  just not my jam"*) and the landing-page text; a dense "system" card with dropdowns.
- **Slash commands like Claude Code:** `/` opens a thin ASCII panel to the right, *"kind of like when you
  do split terminal"*; typing narrows it; Tab completes, including the colon; options work the same way;
  the list never stays in the conversation.
- **Push-to-talk instead of a VAD:** *"I would much rather just have a manual 'VAD'... press and hold the
  spacebar to speak, and you let go when you're done."* Interrupt by pressing again. Double-tap to lock
  for long rants.
- **Never lose a recording:** *"Something that I hate the most is when I have spoken out loud for 10
  minutes, and then something went wrong... and I just lost everything."* Temporary, overwritten later,
  but surviving a crash.
- Everything stays in Avy's own folder.
- And the way to build: all of it together if the pieces are independent, tested and verified, because
  *"those are compounding problems."*

Pipecat was dropped for a small custom pipeline (faster-whisper and Kokoro over a WebSocket), which was
faster and simpler.

## 6. Memory, version 1 (Oct 9)

Oct 9, 1:10 am: *"almost everything is working pretty great."* (One bug: after playing audio in another
tab, Avy stopped speaking until a reload.) Next was memory, and he wanted to stay in the loop: *"I need to
understand what sort of memory architecture you're building... in clean English."*

His design, 1:33 am:
- *"It's okay if you draw concepts from Hermes... but no code comes from Hermes."*
- **Two layers:** the exact message log (*"the source of ground truth"*) and "summaries" that are not
  summaries: *"context about the context... It will have real pointers in it."* A pointer next to every
  fact, to the exact message it came from.
- **Corrections chain, never overwrite:** the friend's-birthday example: the new fact points to the
  correction and marks the old one outdated; *"the earlier pointer would have a pointer to the previous
  pointer."*
- **Look under the hood:** click "3 memories retrieved", see what was found, click a pointer, see the
  log.
- Later: *"some form of a graph that can be reasoned over."*

1:44 am, the Wikipedia idea:

> *"On a Wikipedia page, you don't just find the content of that page, but also tons of links to related
> stuff... we would also want to do this by reference... it forms not only a chain of accountability...
> but here we're trying to create more of a chain of concepts... a network of things that are related to
> each other, and that grows as we build more and more memory."*

2:00 am, go: following links costing tokens is fine (*"Right now, our constraint is not really the cost.
It's more so not having a million tokens"*); test against the real DeepSeek, because *"a lot of things
will just fail simply because you told the LLM to do a certain thing and it just didn't do it"*; *"the
system handles the robustness part, and the LLM just handles the subjective part... like the LLM is doing
fill-in-the-blanks."* And: *"Realize that right now, you're in a crucial moment, and this is kind of the
crux of this project... Build a language here, build something that is the foundation of everything
else."*

Version 1 was built that night: the permanent log; pages of entries every ~20 messages, each pointing at
the exact characters it came from (checked by code); versions; links (about, builds on, related);
recall by meaning and words walking links; the inspector.

## 7. The turn to an organic memory (Oct 9 afternoon)

At 9:20 am he asked for his vision back in writing (compaction had happened) and what was missing. At
2:59 pm, a long message that became memory version 2:

- **Two dials:** how many recent messages Avy reads verbatim (down to zero, up to all), and how deep
  recall reaches.
- **Incognito:** a separate conversation that reads all memory but writes none, with its own temporary
  memory so it's just as good, deleted afterward.
- **Storage wasn't done:** *"I feel like there is not enough linkage between things... I want to build
  some sort of a network such that related concepts have more connections and unrelated concepts have
  fewer connections... The language model builds this network on its own."* The parallel to an
  embedding space, *"but in an outward sense"*; Wikipedia hubs; human recall (*"They remember one thing.
  That reminds them of something else"*).
- **Self-explaining:** *"if you clicked every link, you would end up reading the entire graph... your
  starting point determines what you are trying to gain context about."*
- **Three layers:** the raw log, clean facts with pointers (*"These are not summaries"*), and the network.
- **Thinking, not only transcribing:** patterns (*"I slept for 8 hours today, and then... 7... and then
  maybe 8 hours again"*), ideas from conversations as knowledge, and Avy's own conclusions.
- **Light classification:** *"We don't want to overclassify it, because then it becomes machine
  again... It's useful to differentiate a few things, like something that is a concept versus something
  that is information."*
- **The network is the entity:** *"The entire personality of this system and the entire current state
  of this system is kind of that graph... Yeah, we're almost building an entity here."*
- The theoretical questions: *"how does a system with no context figure out how much context it
  needs?"* and *"If you are given an unlimited pool of knowledge and you are given a task, is it possible
  for you to reliably pull everything you need in order to do that task without knowing how to do that
  task?"*, and the idea of gaming it by making the structure smarter.
- He pasted another agent's analysis (links frozen at birth, a writer that sees 40 entries, link kinds
  that make stars and chains, no nodes for ideas, no strength), with *"Some of it is useless, actually."*

3:23 pm, search as thinking:

> *"The search mechanism can also be a search algorithm, except instead of depth-first search or
> breadth-first search, it would be more of an intelligent thinking-based search."* Explore (look
> around) and depth (dig into what's relevant, branch). *"What you search for is only going to be a proxy
> of what is actually needed for your task."* The AlphaEvolve parallel: the same loop, with a model making
> the choices. *"We're not trying to go from point A to point B. We're just trying to get as much
> relevant context as possible with as little irrelevant context explored as possible."*

And voice stopped being a constraint: Space dictates into the box by default; live conversation is a
separate toggle.

3:28 pm: build the small things (dials, incognito, dictation), and first write out *your* thoughts.
4:12 pm: table the living graph for later (*"It should look like one of those sci-fi movies where you can
see something like a living entity... It shouldn't be all neon and cyberpunky"*, textured like the dot
matrix, nodes bobbing, Avy's search lighting it up), and plan v2's plumbing step by step, contracts and
pseudocode, because *"if I do that again, I will have no idea about what was actually built."* But also:
*"what I do not want to do is build a simple version, then a slightly more complicated version... forever."*

## 8. Memory version 2 (Oct 10)

Oct 10, 3:25 am, the go-ahead, with additions:
- Classes by **reliability**, not types: facts vs inferences, inferences that can be upgraded to facts,
  ideas (his, Avy's, inferred, possible).
- **Hubs that form naturally:** a project he keeps talking about without naming should get its own
  inferred node that conversations tie into; many hubs, not one; *"not by rewarding that... just by
  treating a hub like anything else."*
- **Careful version control:** keep today's version as a fork point he can come back to and build
  memory differently.
- **Real tests that need reasoning:** two concepts from different conversations brought together for a
  new build *"and I don't even use a single common word from either of those concepts."*
- Switches for keyword search, meaning search and the intelligent search; *"If you just turn both off,
  then that should give the model no context."*
- A shorter system card; the `/` panel with a few words under each command, smaller and lighter, a line
  between rows.
- A UI surprise. Concept and README docs (*"a 'what the fuck is this?' concept doc"*). And the Claude
  export as the real-scale test, later: *"ideas are the way I live, okay? And I know exactly what they
  are."*

Built that day (details in CONCEPT.md and MEMORY.md): version 1 frozen on branch `memory-v1`; v2 with
knowledge (thing / information / idea; you said / Avy said / inferred), the living network (kinds,
reasons, supports, strength, fading), the one door that checks every change, the mind (Write, Connect,
Think, Check) on a schedule and budget, Avy searching her own memory (`/explore:`), the benchmark (a
scripted month, ten questions, a judge), five full benchmark runs and the fixes they forced, the
inspector, footnotes, chapters, and the living graph. Merged to main at 1:44 pm.

4:27 pm: *"when I click memory, it just shows 'Couldn't load this... pages.length'."* The audit (from the
raw transcript, at his request) found everything was on main, but his browser was running version 1's
cached page against the new server. Fixed so a stale tab reloads itself.

## 9. His Claude history, and a US provider (Oct 10 to 14)

Oct 10, 9:29 pm: the export arrived (34 MB zipped, 166 MB of JSON):

> *"Don't even make the smallest mistake and try to read any of it. You're going to probe this only and
> only through code... We don't need to transfer the memories... We just need to focus on the
> conversations because we're creating everything from scratch... I don't want you to actually run the
> thing... I want to run that manually."*

And: *"we might switch... DeepSeek's own provider to an American provider that gives us access to the
DeepSeek models, just to be safer with the data."*

Oct 14, 6:32 pm: finish that, document everything, switch to **Luminal** (a US-hosted endpoint serving
DeepSeek-V4.1-Flash only: *"We'll just turn the thinking up to a higher level, and that should do the
trick"*), and let Avy take any file: *"JSON, Markdown, documents, and any file type... a video, a photo,
anything... it should be able to read anything."*

What was built (Oct 10 to 14):
- **The import** ([IMPORT.md](IMPORT.md)): the export's shape worked out by code alone (counts and shapes,
  never text); a streaming reader; 503 conversations and 6,561 messages imported into their own memory
  file, each conversation in one piece, Claude's words marked as Claude's; nothing run through the model.
- **Luminal** ([LUMINAL.md](LUMINAL.md)): the only provider; every rule from his notes plus Claude's own
  probes; the thinking level on the card and a separate one for the mind; the balance in the top bar.
- **Files** ([FILES.md](FILES.md)): attach anything; text, documents, spreadsheets, slides, PDFs,
  pictures (Avy sees them), audio and video (transcribed, with frames); downloads; `/export`; saving
  code blocks as files; importing a Claude export from the page.
- **These documents.**
