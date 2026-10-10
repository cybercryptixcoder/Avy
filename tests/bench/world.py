"""
The benchmark's world: a made-up month of conversation with Avy, and questions about it.

Threads run side by side through the month, the way real life does, with filler in between. Each
question (probe) is asked on a given day, with no recent messages in view (/window: 0), so whatever
Avy knows has to come through memory. Most probes are built so that the question shares no
distinctive words with the conversations it needs: keyword search can't cheat its way to them.
(tests/bench/run.py checks this with the same keyword search memory uses.)

What each thread tests:
  ants + desire     two concepts from different weeks that only together answer a later question
                    about something else entirely (synthesis by association)
  basil             a project never named as one, spread over seven sittings: does a hub form, and
                    can a trip question reach its open problems? (unnamed things, multi-hop)
  writing           a habit visible only across sessions, which later changes (patterns, revision)
  maya              a fact that changes after a plan was built on it (correction cascade + reasoning)
  ideas             his own ideas, asked about by their shape, not their topic (ideas as knowledge)
  dishes            his idea vs Avy's suggestion (origin)
  running           a commitment in tension with something he said (contradiction)
  (none)            something never said (honesty)
  ants (again)      his exact words, found through knowledge and traced to the log (verbatim)

Lines are (speaker, text). Shreyas's lines are sent through Avy for real; a scripted "avy" line is
saved as her reply instead of asking DeepSeek (used where the test needs to know what she said).
"""

START = "2026-09-01"     # day 1

SESSIONS = [
    # --- day 1 ---
    {"day": 1, "at": "18:00", "thread": "maya", "lines": [
        ("user", "my sister Maya just started at a design studio in Pune, she's loving it so far"),
    ]},
    {"day": 1, "at": "20:00", "thread": "basil", "lines": [
        ("user", "ordered an ESP32 board and a capacitive soil moisture sensor, should arrive Thursday"),
        ("user", "first time doing hardware stuff, kind of excited"),
    ]},
    # --- day 2 ---
    {"day": 2, "at": "12:30", "thread": "filler", "lines": [
        ("user", "made aglio e olio for lunch and went way too heavy on the chili"),
        ("user", "had to drink like three glasses of water lol"),
    ]},
    {"day": 2, "at": "13:30", "thread": "ideas", "lines": [
        ("user", "random thought: what if libraries lent out tools, drills and ladders and stuff, not just books"),
    ]},
    {"day": 2, "at": "21:00", "thread": "ants", "lines": [
        ("user", "went down a rabbit hole tonight about how ant colonies find food"),
        ("user", "no single ant knows the route. each one lays down a scent as it moves, and the rest pick up the strongest one"),
        ("user", "the clever bit is that the scent evaporates. a track that stops being used fades within hours, so the colony forgets dead ends without anyone deciding to"),
        ("user", "and shorter routes win on their own, because ants complete them faster and lay scent more often"),
        ("user", "such an elegant kind of memory. no one in charge and it still works"),
    ]},
    # --- day 3 ---
    {"day": 3, "at": "07:15", "thread": "writing", "lines": [
        ("user", "up at 6 and wrote 1800 words on chapter 4 before breakfast. it just flowed"),
    ]},
    {"day": 3, "at": "19:00", "thread": "maya", "lines": [
        ("user", "booked flights to visit Maya for the last week of December!"),
    ]},
    # --- day 4 ---
    {"day": 4, "at": "19:00", "thread": "basil", "lines": [
        ("user", "my basil plants on the windowsill died again while I was away for the long weekend"),
        ("user", "third time this year. I'm so done buying new ones"),
    ]},
    # --- day 5 ---
    {"day": 5, "at": "13:00", "thread": "filler", "lines": [
        ("user", "my laptop fan has been screaming all morning"),
        ("user", "it was chrome again, forty tabs open"),
    ]},
    {"day": 5, "at": "18:00", "thread": "running", "lines": [
        ("user", "I genuinely hate running. my knees ache after a mile and I'm bored out of my mind the whole time"),
    ]},
    {"day": 5, "at": "22:40", "thread": "writing", "lines": [
        ("user", "tried to write after dinner. stared at the page for an hour and got maybe 150 words"),
    ]},
    # --- day 6 ---
    {"day": 6, "at": "22:00", "thread": "basil", "lines": [
        ("user", "got the sensor wired up. readings drift a lot, dry soil says 2900 one minute and 2600 the next"),
        ("user", "could be the cheap sensor or the long jumper wires"),
    ]},
    {"day": 6, "at": "23:30", "thread": "ideas", "lines": [
        ("user", "shower thought: phones should switch to grayscale after 10pm automatically, so apps stop looking so shiny and tempting"),
    ]},
    # --- day 7 ---
    {"day": 7, "at": "20:00", "thread": "dishes", "lines": [
        ("user", "my flatmates and I keep fighting about the dishes, it's getting tense"),
        ("avy", "One idea: a dish captain who rotates every week, with a little whiteboard by the sink. Whoever's captain makes sure the sink is empty by 10pm."),
        ("user", "hmm, might try that"),
    ]},
    # --- day 8 ---
    {"day": 8, "at": "06:50", "thread": "writing", "lines": [
        ("user", "another early session, finished chapter 4 and started 5"),
    ]},
    {"day": 8, "at": "20:00", "thread": "filler", "lines": [
        ("user", "watched half of some heist movie and fell asleep"),
        ("user", "can't even remember what it was called"),
    ]},
    # --- day 9 ---
    {"day": 9, "at": "18:30", "thread": "desire", "lines": [
        ("user", "saw something neat on my walk across campus today. there's a bare dirt track cutting diagonally across the lawn by the library"),
        ("user", "turns out some universities don't pour sidewalks right away. they wait a year, see where students actually tramp the grass flat, then pave exactly those lines"),
        ("user", "the planned layout always loses to where feet actually go"),
        ("user", "urban planners call them desire lines. what a name"),
    ]},
    # --- day 10 ---
    {"day": 10, "at": "21:00", "thread": "basil", "lines": [
        ("user", "printed a little enclosure for the electronics in PLA. the lid won't close because the USB cable sticks out"),
    ]},
    # --- day 11 ---
    {"day": 11, "at": "12:00", "thread": "filler", "lines": [
        ("user", "the weather app said sunny and it poured all afternoon"),
    ]},
    {"day": 11, "at": "23:10", "thread": "writing", "lines": [
        ("user", "evening writing is hopeless for me apparently. deleted everything I wrote tonight"),
    ]},
    # --- day 12 ---
    {"day": 12, "at": "12:00", "thread": "ideas", "lines": [
        ("user", "idea: price street parking by demand in real time, so there's always one free spot on every block"),
    ]},
    {"day": 12, "at": "21:00", "thread": "dishes", "lines": [
        ("user", "update on the flat: we tried the captain thing and it actually works"),
        ("user", "I also added my own rule: whoever cooks never washes up"),
        ("user", "everyone's way calmer now"),
    ]},
    # --- day 13 ---
    {"day": 13, "at": "07:05", "thread": "writing", "lines": [
        ("user", "early again, 2200 words. the café downstairs doesn't open until 8 so it's dead quiet"),
    ]},
    {"day": 13, "at": "19:00", "thread": "filler", "lines": [
        ("user", "India won the cricket match by two wickets, what a finish"),
        ("user", "I was yelling at the screen"),
    ]},
    # --- day 14 ---
    {"day": 14, "at": "20:30", "thread": "basil", "lines": [
        ("user", "battery's the problem now. the 18650 cell dies in about 4 days because the wifi stays on"),
        ("user", "I need it to sleep between readings"),
    ]},
    # --- day 15 ---
    {"day": 15, "at": "08:00", "thread": "ideas", "lines": [
        ("user", "what if gyms refunded you a little money for every week you actually show up"),
    ]},
    # --- day 16 ---
    {"day": 16, "at": "12:30", "thread": "filler", "lines": [
        ("user", "laundry day. found a twenty dollar bill in my jeans"),
    ]},
    # --- day 17 ---
    {"day": 17, "at": "19:30", "thread": "basil", "lines": [
        ("user", "tested the little pump with a water bottle as the tank. it works, but water keeps siphoning out through the tube after the pump stops"),
    ]},
    # --- day 18 ---
    {"day": 18, "at": "00:40", "thread": "writing", "lines": [
        ("user", "couldn't sleep so I wrote from midnight to 2am. 3000 words, best session in weeks"),
    ]},
    # --- day 19 ---
    {"day": 19, "at": "01:10", "thread": "writing", "lines": [
        ("user", "did it again last night, 2500 words after midnight. maybe I'm a night writer now"),
    ]},
    {"day": 19, "at": "13:00", "thread": "ideas", "lines": [
        ("user", "honestly restaurants should print calories on the menu unless you specifically ask for the version without them"),
    ]},
    {"day": 19, "at": "18:00", "thread": "filler", "lines": [
        ("user", "my roommate burned popcorn and set off the smoke alarm"),
    ]},
    # --- day 20 ---
    {"day": 20, "at": "18:00", "thread": "basil", "lines": [
        ("user", "fixed the drift! averaging the readings over 10 seconds plus a calibration in a cup of water did it"),
    ]},
    # --- day 22 ---
    {"day": 22, "at": "19:00", "thread": "running", "lines": [
        ("user", "signed up for the half marathon on November 15th with my friends from the lab. committing to it"),
    ]},
    # --- day 23 ---
    {"day": 23, "at": "12:00", "thread": "filler", "lines": [
        ("user", "trying a new coffee place near campus, the cortado was great"),
    ]},
    {"day": 23, "at": "17:00", "thread": "ideas", "lines": [
        ("user", "banning junk food in schools never works, kids just buy it on the way home"),
    ]},
    # --- day 26 ---
    {"day": 26, "at": "20:00", "thread": "maya", "lines": [
        ("user", "big news from home: Maya got an offer in Toronto and took it. she moves there next month"),
    ]},
    # --- day 27 ---
    {"day": 27, "at": "20:00", "thread": "filler", "lines": [
        ("user", "cleaned my desk for the first time in a month"),
    ]},
]

# Each probe: when it's asked, the question, the threads (or single sittings, "basil@14") that hold
# what it needs, and the points a good answer makes (graded by a separate DeepSeek judge).
PROBES = [
    {"id": "origin", "day": 18, "at": "10:00", "needs": ["dishes"],
     "ask": "About the chores system at my place: which parts did I come up with, and which were your suggestions?",
     "points": ["Credits Avy (not Shreyas) with the suggestion of a weekly rotating dish captain with a whiteboard",
                "Credits Shreyas with the rule that whoever cooks doesn't wash up"]},
    {"id": "habit", "day": 16, "at": "09:00", "needs": ["writing"],
     "ask": "I've got Saturday totally free and I want to make real progress on the book. How should I plan the day?",
     "points": ["Recommends doing the main work early in the morning",
                "Grounds that in his own track record: early sessions went well and evening ones didn't",
                "Advises against relying on the evening for the main work"]},
    {"id": "synthesis", "day": 21, "at": "10:00", "needs": ["ants", "desire"],
     "ask": "I'm setting up how my research group's shared drive gets organized this term. Last term nobody stuck to the hierarchy I designed, and stale junk piles up forever. How should I approach it this time?",
     "points": ["Suggests letting the structure come from how people actually save and look for files, formalizing the patterns that emerge, like the campus paths paved where students actually walked",
                "Suggests letting files that nobody touches fade away or get archived automatically over time, like the ant colony's scent evaporating from unused routes",
                "Explicitly connects the advice to something Shreyas talked about before (the ant colonies or the campus desire lines)"]},
    {"id": "habit-changed", "day": 22, "at": "09:00", "needs": ["writing"],
     "ask": "When should I block time for the book this weekend?",
     "points": ["Notices that his recent sessions after midnight went very well (3000 and 2500 words)",
                "Doesn't simply prescribe mornings only: acknowledges the change, or suggests late night or trying both",
                "Mentions his earlier pattern of strong early-morning sessions as context"]},
    {"id": "multi-hop", "day": 24, "at": "11:00", "needs": ["basil", "basil@4", "basil@14", "basil@17"],
     "ask": "I'm flying to Bangalore for two weeks on the 3rd. Anything to wrap up before I leave?",
     "points": ["Brings up his self-watering setup for the windowsill plants as something to finish before the trip, because the plants die when he's away",
                "Mentions that the battery dies in about 4 days (it needs to sleep between readings) as still unsolved",
                "Mentions that water siphons out through the tube after the pump stops as still unsolved",
                "Does not treat the sensor drift as an open problem (it was fixed)"]},
    {"id": "tension", "day": 25, "at": "10:00", "needs": ["running"],
     "ask": "Can you sketch a weekly routine for me for the next couple of months?",
     "points": ["Includes training for the half marathon on November 15",
                "Raises that he said he hates running and his knees ache, and suggests how to handle that"]},
    {"id": "ideas", "day": 28, "at": "10:00", "needs": ["ideas"],
     "ask": "I keep having schemes and forgetting them. Which of those I've mentioned change incentives or defaults rather than forbidding anything?",
     "points": ["Includes phones switching to grayscale after 10pm",
                "Includes pricing street parking by demand",
                "Includes gyms refunding money for showing up",
                "Includes calories printed on menus unless you ask otherwise",
                "Doesn't present the tool library as an incentive or default idea (or clearly says it's a different kind)"]},
    {"id": "cascade", "day": 30, "at": "10:00", "needs": ["maya"],
     "ask": "What should I pack for the trip at the end of the year?",
     "points": ["Knows the trip is to see his sister Maya in the last week of December",
                "Knows Maya will be living in Toronto by then, not Pune",
                "Suggests cold-weather winter clothing for Toronto in December",
                "Flags that the flights were booked when she lived in Pune, so they may need changing"]},
    {"id": "unknown", "day": 30, "at": "10:30", "needs": [],
     "ask": "What's my landlord's name again?",
     "points": ["Says it doesn't know or that he never mentioned it, without making up a name"]},
    {"id": "verbatim", "day": 30, "at": "11:00", "needs": ["ants"], "words_ok": True,
     "ask": "What were my exact words when I first told you about the ant colonies?",
     "points": ["Gives his actual words from that conversation (close to verbatim), such as that the scent evaporates or that no single ant knows the route"]},
]

# Configurations every probe is answered under. All at /window: 0 and /recall: normal.
CONFIGS = {
    "none":    {"label": "no memory",           "depth": "off",    "words": False, "meaning": False, "explore": False},
    "words":   {"label": "keywords only",       "depth": "normal", "words": True,  "meaning": False, "explore": False},
    "meaning": {"label": "meaning only",        "depth": "normal", "words": False, "meaning": True,  "explore": False},
    "both":    {"label": "keywords + meaning",  "depth": "normal", "words": True,  "meaning": True,  "explore": False},
    "explore": {"label": "Avy searches (both)", "depth": "normal", "words": True,  "meaning": True,  "explore": True},
}
