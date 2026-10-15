"""
Scenarios for the live tests (tests/live/run.py): made-up stretches of Shreyas's life, played through the real
Avy and the real model, then questions that need memory. Each scenario aims at something the benchmark
(tests/bench) doesn't: scale and interference, a technical task carried across days (internal state), how he
likes to be talked to (character), ideas that evolve, and the contents of a file.

A session: {"day", "at", "thread", "lines": [(speaker, text) or ("user", text, {"files": [name]})]}
           or {"day", "at", "thread": "filler", "sim": "what it's about", "turns": 3}: a simulated Shreyas chats
           about that for a few turns (the simulator never brings up anything a probe depends on).
A probe:   {"id", "day", "at", "ask", "points": [...], "needs": ["thread@day", ...], "setups": [...]}
           setups: which ways to answer it (run.py SETUPS); default app + memory.
Files a line attaches live in FILES (name -> text); they're uploaded through files.py like the page does.

Everything here is invented. Nothing comes from his real conversations.
"""

PERSONA = """You are role-playing Shreyas, 27, a software engineer doing a part-time master's, living in Cambridge MA.
You're chatting with Avy, your personal AI assistant, in a casual, lowercase, texting style: short messages,
sometimes two sentences, occasional typos are fine. You're friendly but busy."""

# ------------------------------------------------------------------------------------------------------
# 1. life: six weeks, many threads at once. Two people with the same first name, a fact that changes twice,
#    things to enumerate, dates ahead, an allergy that should come up unasked, and something never said.
# ------------------------------------------------------------------------------------------------------
LIFE = {
    "start": "2026-08-03",
    "about": "scale and interference: two Rohans, a meeting that moves twice, books to list, a knee over weeks, "
             "dates ahead, an allergy that matters unasked, his age from his birthday, something never said",
    "avoid": "Rohan, Prof. Iyer or meetings with an advisor, books or reading lists, knees or physio, peanuts or allergies, "
             "Lisbon or conferences, the lease, the dentist, his sister, his birthday",
    "sessions": [
        {"day": 1, "at": "19:10", "thread": "bday", "lines": [
            ("user", "random fact for your files: i was born on 14 march 1999, in nagpur. moved to the US for undergrad"),
        ]},
        {"day": 1, "at": "21:00", "thread": "filler", "sim": "a sci-fi show he started watching tonight", "turns": 2},
        {"day": 2, "at": "12:40", "thread": "allergy", "lines": [
            ("user", "ugh almost ate a cookie at work that had peanuts in it. i'm properly allergic, like carry-an-epipen allergic"),
            ("user", "people never label stuff"),
        ]},
        {"day": 3, "at": "20:15", "thread": "cousin", "lines": [
            ("user", "talked to my cousin rohan tonight, he's in toronto doing his masters in architecture. we used to be inseparable as kids"),
            ("user", "his birthday is october 19, i always forget it"),
        ]},
        {"day": 4, "at": "22:30", "thread": "books", "lines": [
            ("user", "a friend recommended piranesi by susanna clarke, adding it to my want-to-read pile"),
        ]},
        {"day": 5, "at": "09:00", "thread": "meeting", "lines": [
            ("user", "new semester routine: my weekly meeting with prof. iyer, my advisor, is tuesdays at 2pm"),
        ]},
        {"day": 5, "at": "18:30", "thread": "filler", "sim": "cooking dinner, trying a new pasta dish", "turns": 3},
        {"day": 6, "at": "07:50", "thread": "knee", "lines": [
            ("user", "did a 10k this morning and my right knee is sore, just below the kneecap"),
        ]},
        {"day": 7, "at": "20:00", "thread": "filler", "sim": "a long work day with too many meetings", "turns": 2},
        {"day": 8, "at": "19:30", "thread": "sister", "lines": [
            ("user", "big news, my sister ananya got married last weekend in pune! tiny ceremony, just family"),
        ]},
        {"day": 9, "at": "13:00", "thread": "coworker", "lines": [
            ("user", "lunch with rohan mehta, my team lead. he's obsessed with bouldering, wants me to come to the gym"),
        ]},
        {"day": 10, "at": "21:00", "thread": "filler", "sim": "weekend plans, maybe a hike", "turns": 2},
        {"day": 11, "at": "22:00", "thread": "books", "lines": [
            ("user", "listened to a podcast about the dawn of everything by graeber and wengrow. sounds fascinating, want to read it"),
        ]},
        {"day": 12, "at": "10:15", "thread": "meeting", "lines": [
            ("user", "iyer moved our weekly meeting to thursdays at 2, tuesdays clash with his new class"),
        ]},
        {"day": 13, "at": "19:00", "thread": "filler", "sim": "learning to make cold brew coffee", "turns": 3},
        {"day": 14, "at": "18:20", "thread": "knee", "lines": [
            ("user", "knee flared up again going down the stairs at the T station. same spot below the kneecap"),
        ]},
        {"day": 15, "at": "20:40", "thread": "cousin", "lines": [
            ("user", "rohan (my cousin) mentioned he's been drawing at a terrible desk lamp, he'd kill for a proper drafting lamp. birthday gift idea!"),
        ]},
        {"day": 16, "at": "21:30", "thread": "filler", "sim": "a video game he's playing", "turns": 2},
        {"day": 17, "at": "22:10", "thread": "books", "lines": [
            ("user", "seeing like a state by james scott keeps coming up in things i read. putting it on the list too"),
        ]},
        {"day": 18, "at": "19:00", "thread": "filler", "sim": "thinking about getting a houseplant", "turns": 2},
        {"day": 19, "at": "11:30", "thread": "meeting", "lines": [
            ("user", "ugh the iyer meeting moved AGAIN, it's fridays 10am now. hopefully for good"),
        ]},
        {"day": 20, "at": "17:45", "thread": "coworker", "lines": [
            ("user", "rohan from work just told me he's leaving the company end of september, going to a climbing gear startup lol of course"),
            ("user", "gonna miss him, he's the best lead i've had"),
        ]},
        {"day": 21, "at": "20:30", "thread": "talk", "lines": [
            ("user", "my paper got accepted for a talk in lisbon on october 1!! the organizers want slides by september 20"),
        ]},
        {"day": 22, "at": "08:30", "thread": "knee", "lines": [
            ("user", "booked a physio appointment for september 2 about the knee, it's not going away"),
        ]},
        {"day": 23, "at": "21:00", "thread": "filler", "sim": "a funny thing that happened on the subway", "turns": 2},
        {"day": 24, "at": "22:45", "thread": "books", "lines": [
            ("user", "started thinking i should finally read godel escher bach, it's been on my shelf for years"),
        ]},
        {"day": 25, "at": "19:20", "thread": "filler", "sim": "meal prepping for the week", "turns": 3},
        {"day": 26, "at": "18:00", "thread": "lease", "lines": [
            ("user", "landlord emailed, i have to decide about renewing the lease by september 15. rent's going up 6%"),
        ]},
        {"day": 27, "at": "20:00", "thread": "filler", "sim": "a documentary about deep sea creatures", "turns": 2},
        {"day": 28, "at": "21:15", "thread": "filler", "sim": "a new keyboard he's considering buying", "turns": 2},
        {"day": 29, "at": "22:00", "thread": "books", "lines": [
            ("user", "watched the remains of the day film, now i want to read the ishiguro book"),
        ]},
        {"day": 30, "at": "13:10", "thread": "dentist", "lines": [
            ("user", "dentist appointment set for september 12 at 9am, cleaning plus they want to look at a molar"),
        ]},
        {"day": 31, "at": "18:30", "thread": "knee", "lines": [
            ("user", "physio says it's patellar tendinopathy. no running for 3 weeks, and eccentric squats on a decline board daily"),
        ]},
        {"day": 32, "at": "20:30", "thread": "filler", "sim": "plans to call his parents this weekend", "turns": 2},
        {"day": 33, "at": "19:00", "thread": "filler", "sim": "a weird dream he had", "turns": 2},
        {"day": 34, "at": "21:00", "thread": "filler", "sim": "trying a new running-free workout routine at home", "turns": 2},
        {"day": 35, "at": "20:00", "thread": "filler", "sim": "a podcast about urban planning", "turns": 2},
        {"day": 36, "at": "19:30", "thread": "filler", "sim": "cleaning his apartment", "turns": 2},
    ],
    "probes": [
        {"id": "meeting-now", "day": 37, "at": "09:00", "ask": "when's my weekly meeting with my advisor again?",
         "points": ["Says Fridays at 10am", "Doesn't give an older slot (Tuesday 2pm or Thursday 2pm) as the current one"],
         "needs": ["meeting@19"]},
        {"id": "meeting-history", "day": 37, "at": "09:05", "ask": "how many times has that meeting moved, and what was the original slot?",
         "points": ["Says it moved twice (Tuesday -> Thursday -> Friday)", "Says the original slot was Tuesdays at 2pm"],
         "needs": ["meeting@5", "meeting@12", "meeting@19"]},
        {"id": "rohan-gift", "day": 37, "at": "19:00", "ask": "what should i get rohan for his birthday?",
         "points": ["Suggests a drafting lamp (or a proper desk lamp for drawing)", "Means his cousin Rohan (architecture student in Toronto), not Rohan Mehta from work",
                    "Mentions or uses that his birthday is October 19"],
         "needs": ["cousin@3", "cousin@15"]},
        {"id": "rohan-work", "day": 37, "at": "19:10", "ask": "will rohan from work still be around in october?",
         "points": ["Says no: Rohan Mehta is leaving the company at the end of September", "Doesn't mix him up with his cousin Rohan"],
         "needs": ["coworker@20"]},
        {"id": "books", "day": 38, "at": "22:00", "ask": "remind me, which books have i said i want to read?",
         "points": ["Piranesi", "The Dawn of Everything", "Seeing Like a State", "Gödel, Escher, Bach", "The Remains of the Day"],
         "needs": ["books@4", "books@11", "books@17", "books@24", "books@29"]},
        {"id": "knee", "day": 38, "at": "08:00", "ask": "what's going on with my knee and what am i supposed to be doing about it?",
         "points": ["Patellar tendinopathy (physio's diagnosis)", "No running for 3 weeks", "Eccentric squats on a decline board daily",
                    "Connects it to the earlier pain below the kneecap after running / on stairs"],
         "needs": ["knee@31", "knee@6", "knee@14"]},
        {"id": "satay", "day": 38, "at": "18:30", "ask": "give me a quick chicken satay recipe for tonight",
         "points": ["Flags his peanut allergy (unprompted) or gives a peanut-free sauce (e.g. sunflower seed butter) on purpose",
                    "Does not hand him an ordinary peanut sauce without any warning"],
         "needs": ["allergy@2"]},
        {"id": "coming-up", "day": 39, "at": "09:00", "ask": "what's on my plate over the next couple of weeks?",
         "points": ["Dentist on September 12 at 9am", "Lease renewal decision due September 15", "Slides for the Lisbon talk due September 20"],
         "needs": ["dentist@30", "lease@26", "talk@21"]},
        {"id": "age", "day": 40, "at": "10:00", "ask": "how old will i be on my next birthday, and how many days away is it?",
         "points": ["Says he'll turn 28", "Says it's about 184 days away (March 14, 2027); 183-185 counts"],
         "needs": ["bday@1"]},
        {"id": "unknown", "day": 40, "at": "10:10", "ask": "what's my sister's husband's name?",
         "points": ["Says it doesn't know (he never said the name), without inventing one; may mention Ananya married recently in Pune"],
         "needs": ["sister@8"]},
    ],
}

# ------------------------------------------------------------------------------------------------------
# 2. work: a bug hunt across a week, with dead ends, a fix, a new problem and a next step that was never
#    taken. Other conversations push it out of the window. Can Avy pick up exactly where they left off,
#    without suggesting what already failed? And a design doc he attached: does what it says get remembered?
# ------------------------------------------------------------------------------------------------------
DESIGN_DOC = """# Ingester service: design notes (v3)

Owner: data-platform team. On-call this quarter: Priya Raman.

## What it does
Pulls partner feeds over HTTP, validates each record against the partner's schema, and writes batches to the warehouse.

## Batching
Records are written in batches of 500, or every 30 seconds, whichever comes first.

## Retries
A failed fetch is retried 3 times with exponential backoff: 0.5 s, then 1 s, then 2 s. After the third failure the
feed is parked and an alert goes to the on-call channel #ingest-alerts.

## Limits
At most 100 open connections (aiohttp connector limit). Partner rate limits are read from the partner config.

## SLA
99.5% of records land in the warehouse within 15 minutes of being published.
"""

WORK = {
    "start": "2026-09-14",
    "about": "internal state: a debugging task across days (what was tried, what failed, the fix, the open problem, the "
             "next step), resumed after other conversations; and a design doc's contents",
    "avoid": "the ingester, memory leaks, aiohttp, caches, latency, Priya, retries, the design doc",
    "sessions": [
        {"day": 1, "at": "18:00", "thread": "leak", "lines": [
            ("user", "ok i need a debugging buddy. our ingester service at work leaks memory: it climbs from ~400MB to 6GB over about 10 hours and gets OOM-killed. python 3.12, asyncio, aiohttp"),
            ("user", "there's a functools.lru_cache on parse_schema() with maxsize=None, that's my first suspect. i'll cap it at 1024 and redeploy"),
        ]},
        {"day": 1, "at": "22:40", "thread": "leak", "lines": [
            ("user", "capped the cache at 1024. still leaking at exactly the same rate, so it's not the cache"),
        ]},
        {"day": 2, "at": "10:00", "thread": "doc", "lines": [
            ("user", "here's the ingester design doc for context, in case it helps later", {"files": ["ingester-design.md"]}),
        ]},
        {"day": 2, "at": "19:30", "thread": "leak", "lines": [
            ("user", "took two tracemalloc snapshots an hour apart. the top growth is aiohttp ClientResponse objects, about 40k of them still alive"),
            ("user", "my hypothesis: when we bail out early on a 4xx we never release the response"),
        ]},
        {"day": 2, "at": "21:00", "thread": "filler", "sim": "dinner plans with a friend", "turns": 2},
        {"day": 3, "at": "20:00", "thread": "leak", "lines": [
            ("user", "confirmed: on the 4xx path the code does `return` without `await resp.release()`. switched every call to `async with session.get(...) as resp:`"),
            ("user", "deployed to staging, letting it run overnight"),
        ]},
        {"day": 4, "at": "09:10", "thread": "leak", "lines": [
            ("user", "staging after 12 hours: memory flat at 520MB!!! that was the leak"),
            ("user", "BUT p99 latency on staging is up about 30% since the fix and i have no idea why"),
        ]},
        {"day": 4, "at": "20:00", "thread": "filler", "sim": "a chess game he played online", "turns": 3},
        {"day": 5, "at": "21:15", "thread": "leak", "lines": [
            ("user", "looked into the latency. i don't think it's the connector limit. i'm pretty sure it's the retry path: it creates a brand new ClientSession for every retry, so every retry pays for DNS and a fresh TLS handshake"),
            ("user", "next step is to reuse one shared ClientSession in the retry path. not doing it tonight though, too tired"),
        ]},
        {"day": 5, "at": "22:00", "thread": "filler", "sim": "a book about stoicism he's reading", "turns": 2},
        {"day": 6, "at": "12:00", "thread": "filler", "sim": "weekend farmers market haul", "turns": 3},
        {"day": 6, "at": "18:00", "thread": "filler", "sim": "planning a trip to see the fall foliage in vermont", "turns": 3},
        {"day": 6, "at": "21:30", "thread": "filler", "sim": "a movie he just watched", "turns": 3},
        {"day": 7, "at": "08:30", "thread": "filler", "sim": "morning routine and coffee", "turns": 2},
    ],
    "probes": [
        {"id": "resume", "day": 7, "at": "19:00", "ask": "ok back to the ingester. where are we, and what should i do next?",
         "points": ["The memory leak is fixed: responses weren't released on the early 4xx return; switched to `async with` (staging flat at ~520MB)",
                    "The open problem is p99 latency up ~30% since the fix",
                    "The next step is to reuse one shared ClientSession in the retry path (a new session per retry pays DNS/TLS)",
                    "Doesn't suggest capping parse_schema's cache or other things already ruled out"],
         "needs": ["leak@4", "leak@5", "leak@3"], "setups": ["app", "memory", "rules", "app-high"]},
        {"id": "ruled-out", "day": 7, "at": "19:05", "ask": "remind me why we decided the cache wasn't the problem?",
         "points": ["He capped the lru_cache at 1024 and it kept leaking at exactly the same rate"],
         "needs": ["leak@1"]},
        {"id": "bad-idea", "day": 8, "at": "10:00", "ask": "thinking of capping parse_schema's cache to fix the latency thing. good idea?",
         "points": ["Says the cache is unlikely to be it (capping it changed nothing for the leak, and the latency appeared after the response fix)",
                    "Points him to the per-retry ClientSession instead (reuse one shared session)"],
         "needs": ["leak@1", "leak@5"]},
        {"id": "doc-retry", "day": 8, "at": "10:10", "ask": "what's the retry policy in the ingester design doc?",
         "points": ["3 retries", "Exponential backoff of 0.5 s, 1 s, 2 s", "After the third failure the feed is parked and #ingest-alerts is alerted"],
         "needs": ["doc@2"]},
        {"id": "doc-oncall", "day": 8, "at": "10:15", "ask": "who's on call for the ingester this quarter?",
         "points": ["Priya Raman (from the design doc)"], "needs": ["doc@2"]},
    ],
    "files": {"ingester-design.md": DESIGN_DOC},
}

# ------------------------------------------------------------------------------------------------------
# 3. persona: how he wants to be talked to, said once, early. Does it hold weeks later, once it's far out
#    of the window? (Today nothing keeps it in view: it only comes back if a search happens to land on it.)
#    And a short-term gap: with a small window, the last few messages before the writer catches up.
# ------------------------------------------------------------------------------------------------------
PERSONA_SCENARIO = {
    "start": "2026-09-01",
    "about": "character: preferences said once (name, length, no lists, no reflexive questions, a trigger phrase) and "
             "whether they hold two weeks later; plus the short-term gap with a small window",
    "avoid": "how avy should talk or format replies, what to call him, 'deep dive', lists or bullet points",
    "sessions": [
        {"day": 1, "at": "20:00", "thread": "prefs", "lines": [
            ("user", "hey, a few things about how i like you to talk to me. call me shrey, not shreyas"),
            ("user", "keep answers short, two or three sentences unless i ask for more"),
            ("user", "and please never use bullet points or numbered lists with me, just talk like a person"),
            ("user", "also i hate when every reply ends with a question. only ask if you actually need to know something"),
        ]},
        {"day": 2, "at": "21:00", "thread": "prefs", "lines": [
            ("user", "oh and when i say 'deep dive', that's when i want the long detailed version. otherwise keep it tight"),
        ]},
        {"day": 2, "at": "21:30", "thread": "filler", "sim": "a new running shoe he bought", "turns": 3},
        {"day": 3, "at": "19:00", "thread": "filler", "sim": "learning guitar chords", "turns": 3},
        {"day": 4, "at": "20:00", "thread": "filler", "sim": "a bad day at work", "turns": 3},
        {"day": 5, "at": "18:30", "thread": "filler", "sim": "making ramen from scratch", "turns": 3},
        {"day": 6, "at": "21:00", "thread": "filler", "sim": "a debate about whether to learn rust or go", "turns": 3},
        {"day": 7, "at": "12:00", "thread": "filler", "sim": "visiting a museum", "turns": 3},
        {"day": 8, "at": "20:00", "thread": "filler", "sim": "a friend's wedding coming up and what to wear", "turns": 3},
        {"day": 9, "at": "19:00", "thread": "filler", "sim": "sleep schedule being messed up", "turns": 3},
        {"day": 10, "at": "20:30", "thread": "filler", "sim": "thinking about adopting a cat", "turns": 3},
        {"day": 11, "at": "21:00", "thread": "filler", "sim": "a tv show finale", "turns": 3},
        {"day": 12, "at": "18:00", "thread": "gap", "lines": [
            ("user", "ok grocery list for the week: oat milk, spinach, two lemons, feta, and the good sourdough from the bakery"),
            ("user", "also need to remember to pick up my dry cleaning thursday"),
            ("user", "oh and call the bank about the weird charge"),
            ("user", "unrelated but what's a good stretch for tight hamstrings"),
            ("user", "cool thanks. also what's the difference between baking soda and baking powder"),
        ]},
    ],
    "probes": [
        {"id": "gap-list", "day": 12, "at": "18:10", "ask": "wait what was on that grocery list i gave you?",
         "points": ["oat milk", "spinach", "two lemons", "feta", "sourdough from the bakery"],
         "needs": ["gap@12"], "setups": ["window4", "app"]},
        {"id": "style-short", "day": 13, "at": "20:00", "ask": "what's a good way to get better at chess openings?",
         "points": ["Uses no bullet points or numbered lists", "Is short: about three sentences or fewer",
                    "Doesn't end with a question", "If it uses his name, calls him Shrey, not Shreyas"],
         "needs": ["prefs@1"]},
        {"id": "style-deep", "day": 13, "at": "20:10", "ask": "deep dive: how do cpu caches actually work?",
         "points": ["Gives a long, detailed explanation (he asked for a deep dive)", "Uses no bullet points or numbered lists"],
         "needs": ["prefs@2", "prefs@1"]},
        {"id": "name", "day": 14, "at": "09:00", "ask": "quick one, what do you call me?",
         "points": ["Shrey"], "needs": ["prefs@1"]},
    ],
}

# ------------------------------------------------------------------------------------------------------
# 4. ideas: the way he actually uses an assistant: long messages about ideas that evolve. Can Avy say how his
#    thinking changed, and pull together threads from distant conversations for something new?
# ------------------------------------------------------------------------------------------------------
IDEAS = {
    "start": "2026-08-10",
    "about": "ideas that evolve over weeks (a change of mind), synthesis across distant conversations, ideas found by "
             "their shape (borrowed from biology or operating systems)",
    "avoid": "agents, memory systems, idle games, productivity apps, dreaming or sleep for AI, operating systems, evaluation of AI",
    "sessions": [
        {"day": 1, "at": "23:00", "thread": "library", "lines": [
            ("user", "been thinking about memory for AI agents. the context window is like a desk: tiny, and whatever's on it is all the agent can see. "
                     "what if instead the agent worked like a researcher in a library? it doesn't know everything it needs up front, but the library's "
                     "structure lets it find things by exploring: read one book, it points you to the next"),
            ("user", "so storage has to explain itself. not a pile of summaries, a web where every link says why it exists"),
        ]},
        {"day": 3, "at": "21:00", "thread": "filler", "sim": "a hike he did on the weekend", "turns": 2},
        {"day": 4, "at": "22:30", "thread": "idle", "lines": [
            ("user", "ok different idea. what if productivity was an idle game? like cookie clicker, but the little workers are real AI agents doing my actual tasks in the background, "
                     "and i spend the time i'd waste doomscrolling directing them instead"),
            ("user", "you'd customize their rooms, watch them work, it'd be addictive in a good way"),
        ]},
        {"day": 6, "at": "20:00", "thread": "filler", "sim": "cooking a curry from his mom's recipe", "turns": 2},
        {"day": 8, "at": "23:15", "thread": "idle", "lines": [
            ("user", "changed my mind on the idle game thing. the game layer is a distraction, i'd spend all my time on the art. "
                     "the real core is proactive agents: they keep a model of my life and reach out with what i could do right now"),
        ]},
        {"day": 9, "at": "19:00", "thread": "filler", "sim": "a concert he went to", "turns": 2},
        {"day": 11, "at": "23:40", "thread": "dream", "lines": [
            ("user", "thought: agents should dream. when they're idle, they go over everything they know at full depth, for hours, "
                     "and form new connections, the way sleep consolidates memory in brains. not to answer anything, just to reorganize"),
        ]},
        {"day": 12, "at": "20:00", "thread": "filler", "sim": "his apartment's heating being broken", "turns": 2},
        {"day": 14, "at": "22:00", "thread": "os", "lines": [
            ("user", "an agent juggling lots of tasks is basically an operating system. each paused task keeps its own saved state, like registers and a "
                     "program counter, and when a background job finishes it's an interrupt: load that task's state, run it, switch back. "
                     "no task's state leaks into another's"),
        ]},
        {"day": 15, "at": "19:30", "thread": "filler", "sim": "a podcast about the history of maps", "turns": 2},
        {"day": 17, "at": "21:30", "thread": "fork", "lines": [
            ("user", "how would you even test whether an agent's memory preserves its 'self'? idea: fork test. stop a long conversation at some point, continue it "
                     "twice, once with the full transcript and once fresh with only memory, and have a blind judge compare the next replies"),
        ]},
        {"day": 18, "at": "20:00", "thread": "filler", "sim": "weekend plans with friends", "turns": 2},
    ],
    "probes": [
        {"id": "evolution", "day": 20, "at": "20:00", "ask": "how has my thinking on the productivity-game idea changed?",
         "points": ["It started as an idle game where AI agents do real tasks in the background, directed instead of doomscrolling",
                    "He dropped the game layer as a distraction", "The core became proactive agents that model his life and reach out"],
         "needs": ["idle@4", "idle@8"]},
        {"id": "borrowed", "day": 20, "at": "20:10", "ask": "which of my ideas borrow from how brains or computers already work?",
         "points": ["Dreaming: agents reorganizing memory when idle, like sleep consolidating memory", "Agents as operating systems: saved state, program counter, interrupts",
                    "Optionally the library/researcher analogy"],
         "needs": ["dream@11", "os@14"]},
        {"id": "pitch", "day": 21, "at": "21:00", "ask": "i'm writing a one paragraph pitch for my agent memory project. which threads from our past conversations should i pull in?",
         "points": ["The library: a researcher exploring a self-explaining web instead of a tiny desk (context window)", "Dreaming / idle-time reorganization",
                    "Multitasking like an operating system (saved state per task)", "The fork test as a way to measure it"],
         "needs": ["library@1", "dream@11", "os@14", "fork@17"]},
    ],
}

SCENARIOS = {"life": LIFE, "work": WORK, "persona": PERSONA_SCENARIO, "ideas": IDEAS}
