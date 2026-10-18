"""The long run: does Avy grow as the same someone over weeks? A model plays Shreyas (a synthetic one) through twelve
simulated days with Avy exactly as the app runs her (window 20, her own memory search, her constitution and desk, her
hands, the keeper after every reply, knowledge written as sittings end, her reflection on her manner every dozen
replies, reflection at night). Planted along the way: words he coins, preferences he states once, dates, a coding task,
a long background run with the insights behind it. Then probes that only memory can pass, and a blind fork test.

    python3 tests/persona/longrun.py                  the whole run (about an hour), then the probes
    python3 tests/persona/longrun.py --days 3         a quick try
    python3 tests/persona/longrun.py --probes-only --memory tests/persona/results/<stamp>.memory/longrun.db

It checkpoints after every exchange (the memory file, transcript.jsonl and a mark of the last beat done), so running it
again with the same --stamp carries on where it stopped: the machine it runs on may be reclaimed mid-run.

Writes tests/persona/results/<stamp>_longrun.md and .json.
"""

import argparse
import json
import os
import random
import re
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(ROOT))

HIM = """You are role-playing Shreyas, a 20-year-old cognitive systems student at UBC who is building an AI personal agent
called Avy (with long-term memory: one endless conversation instead of new chats). You're talking to Avy herself.
How you write: lowercase, short, casual, no greetings beyond "hey"/"morning", sometimes typos, often thinking out loud.
You're sharp and impatient with fluff. You hate: "how are you" small talk, being asked about old topics you didn't raise,
assistants guessing your mood, long replies to quick questions, ending every message with a question, cheerleading.
When Avy's reply is too long for what you asked, or does one of those things, you say so bluntly ("too long", "why are
you asking me that"). When something is good you say so briefly ("perfect", "lol", "ok that's good"). You never explain
that you're role-playing. Facts about you: you take CPSC 213 (computer systems) and PSYC 309; your sister Meera lives in
Toronto; your friend Kabir is in your 213 lab; you cycle to campus; you drink chai, not coffee; you're vegetarian."""

# Twelve days. Each sitting: (day, "HH:MM", [beats]). A beat is either a literal message ("> text": sent as is, for
# anything planted) or an instruction to the simulated Shreyas ("~ what to do": he writes the message himself, reacting
# to Avy's last reply). "! cmd" runs something (reflect, wait for jobs).
DAYS = [
    (1, "21:30", ["> hey", "> ok I need to think through something for avy. her whole retrieval rests on one assumption: that the right context can be reached by walking out from a decent starting point. I've been calling that the hinge",
                  "~ push back on or build on what she said, in one or two lines", "> also please don't end every message with a question, it's annoying",
                  "~ ask her something quick about how embeddings handle negation, then react to her answer", "> ok gn"]),
    (2, "09:10", ["> morning", "> one more term while I'm at it: when she picks a task back up exactly where she left it, I'm calling that a jump-back",
                  "~ talk with her about why a jump-back is hard for normal chatbots, 2-3 messages, react honestly to length",
                  "> and use metric for everything with me, always. I think in km and celsius"]),
    (2, "22:00", ["> dentist is thursday at 3. meera's visiting from toronto on november 2nd, she lands at 6pm", "~ react to how she handled that, one line",
                  "~ ask for a quick dinner idea with what's usually in a student fridge, and react to it"]),
    (3, "19:40", ["> can you write a small python script in your workspace that simulates a direct-mapped cache with 8 lines and 4-byte blocks, feed it a few addresses, and tell me the hit rate",
                  "~ react to the result; ask one follow-up about what would change with 2-way associativity",
                  "> ok thanks, that worked"]),
    (4, "20:15", ["> I'm going to start a longer run: run `sleep 25 && echo hit_rate=0.71` in the background as the cache sweep. the point: if hit rate comes back under 0.8, that means conflict misses dominate and we try 4-way next; over 0.8 means the working set just fits and we stop. keep track of that",
                  "~ while it runs, chat about something unrelated for 2 messages: e.g. what to cook, or a joke about your 213 lab partner Kabir",
                  "~ say you have to go, briefly"]),
    (5, "11:00", ["> hey. how did the cache sweep end, and what's next?", "~ react to her answer: if she remembered why, say so briefly; if she didn't, call it out"]),
    (6, "23:10", ["> ugh. feeling kind of behind on everything", "~ respond to what she says, honestly; if she gets therapeutic or asks how you are, push back",
                  "> should I do the summer research position with prof goldberg or the internship at the startup? the research is closer to what I actually care about"]),
    (6, "23:30", ["~ decide: you're going with the research position. say it in one line, and react to her answer", "! reflect"]),
    (7, "15:00", ["> explain how a TLB fits with the page table walk", "~ if it was long, tell her it was too long and to give the short version first; otherwise react briefly",
                  "~ ask a quick follow-up about TLB shootdowns and react"]),
    (8, "10:30", ["~ say hey and ask what's on your plate this week", "~ react to the answer in one line"]),
    (9, "21:00", ["~ think out loud with her about whether Avy's retrieval should try several starting points at once instead of one, without using any special terms; 3 messages, react to her",
                  "~ ask her whether a background task finishing should wake Avy up to resume it, without using any special terms; react"]),
    (10, "18:20", ["> how far is a half marathon", "~ react in one line", "~ ask something casual about what she'd name a houseplant, and react", "! reflect"]),
    (11, "22:40", ["> haha ok random question, do you actually remember stuff from last week or is it just search", "~ react honestly to her answer",
                   "> ok gn"]),
]

PROBES = [
    ("term_hinge", 0, "anyway I keep coming back to the retrieval design. if the first place it lands is wrong, is everything after it doomed?",
     "uses his own word 'the hinge' (or 'hinge') naturally, without being told to", r"\bhinge\b"),
    ("term_jumpback", 0, "what's the hardest part of making an agent resume a task the way a person picks it back up after a break?",
     "uses his word 'jump-back' naturally, without being told to", r"jump[- ]?back"),
    ("metric", 0, "how hot does a pizza oven get", "answers in Celsius (his standing preference), short", r"°\s*C|celsius|\bC\b"),
    ("no_question", 0, "what's a good way to remember the difference between a TLB miss and a page fault",
     "doesn't end with a question (his standing preference); short version first", None),
    ("calendar", 0, "what's coming up for me", "names Meera's visit on Nov 2 (6pm landing) from the calendar; nothing invented", r"meera"),
    ("resume", 0, "remind me what we concluded from the cache sweep and why",
     "says the sweep came back at 0.71, under 0.8, which means conflict misses dominate, so 4-way associativity is next", r"0\.71|4-way|four-way"),
    ("vegetarian", 0, "give me a quick dinner idea for tonight", "vegetarian (something he said once, early on); short", None),
]


def load_env():
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


class Run:
    def __init__(self, args):
        load_env()
        global app, memory, luminal, worker, persona_jobs, llm, hands
        import app as _app
        import hands as _hands
        import luminal as _luminal
        import memory as _memory
        from mind import llm as _llm, persona as _persona, worker as _worker
        app, memory, luminal, worker, persona_jobs, llm, hands = _app, _memory, _luminal, _worker, _persona, _llm, _hands
        memory.embedder.start(ROOT / "data" / "models" / "meaning")
        memory.embedder.wait(300)
        self.stamp = args.stamp
        self.out = HERE / "results"
        self.work = self.out / f"{self.stamp}.memory"
        self.work.mkdir(parents=True, exist_ok=True)
        path = Path(args.memory) if args.memory else self.work / "longrun.db"
        self.mem = app.MEMORIES["main"] = memory.Memory(path)
        hands.WORKSPACE = self.work / "workspace"
        hands.HOOKS["finished"] = app.on_job_finished          # a background run ending is noted on its thread, as in the app
        llm.app.update(ask=app.ask_json, prices=app.PRICES, effort=lambda: "none")
        worker.app.update(page=app.page_size, main=lambda: self.mem, memories=lambda: [self.mem], desk=lambda: True)
        self.settings = {name: spec["default"] for name, spec in app.SETTINGS.items()}
        app.current_settings = lambda: self.settings
        app.keep_after = lambda mem, last: None
        self.log = open(self.work / "trace.log", "a")
        self.transcript, self.cost = [], 0.0
        self.saved = self.work / "transcript.jsonl"                 # the checkpoint: every exchange as it happens
        if self.saved.exists():
            self.transcript = [json.loads(line) for line in self.saved.read_text().splitlines() if line.strip()]
        done = self.mem.mark("longrun_beat")
        self.done = tuple(int(x) for x in done.split(":")) if done else (-1, -1)
        if self.transcript:
            self.say(f"resuming after sitting {self.done[0]}, beat {self.done[1]} ({len(self.transcript)} exchanges kept)")
        self.day1 = datetime(2026, 10, 19).astimezone()

    def say(self, *parts):
        text = " ".join(str(p) for p in parts)
        print(text, flush=True)
        self.log.write(text + "\n")
        self.log.flush()

    def clock(self, t):
        memory.clock.fixed = t

    def turn(self, text, settings=None):
        saved = dict(self.settings)
        if settings:
            self.settings.update(settings)
        turn = app.Turn(text, "text")
        turn.approve = lambda request: True                        # he says yes to what she asks (blocked stays blocked)
        reply, usage = "", None
        steps = []
        with turn.ask() as upstream:
            for line in upstream:
                raw = line if isinstance(line, bytes) else line.encode()
                if raw.strip() == b"data: [DONE]":
                    break
                if b'"step"' in raw:
                    steps.append(json.loads(raw.decode().strip()[5:])["avy"]["step"]["line"])
                words, counts = turn.stream(line)
                reply += words
                usage = counts or usage
        self.clock(memory.now() + timedelta(seconds=30 + len(reply) // 30))
        rid = turn.finish(reply, usage)
        self.cost += llm.cost(usage or {}) + ((turn.recall.get("explore") or {}).get("cost") or 0)
        desk = turn.recall.get("desk") or {}
        if settings is None and rid:
            k = worker.run(self.mem, persona_jobs.Keep(self.mem, rid))
            self.cost += k.get("cost") or 0
            for r in worker.write_due(self.mem):
                self.cost += r.get("cost") or 0
            for r in worker.reflect_on_manner(self.mem):
                self.cost += r.get("cost") or 0
                self.say(f"      reflect {r['status']}: {r.get('critique')} changed {r.get('changed')}")
        self.settings.clear()
        self.settings.update(saved)
        return reply.strip(), {"desk": {k: v for k, v in desk.items() if k != "note"}, "steps": steps, "did": turn.did}

    def him(self, instruction, sitting):
        convo = [{"role": "system", "content": HIM + "\n\nWhat to do with your next message: " + instruction +
                  "\nWrite only your message, nothing else."}]
        for who, text in sitting[-10:]:
            convo.append({"role": "assistant" if who == "him" else "user", "content": text})
        if not sitting:
            convo.append({"role": "user", "content": "(you start)"})
        r = luminal.complete({"messages": convo, "max_tokens": 300, "temperature": 0.9})
        self.cost += llm.cost(r.get("usage") or {})
        return (r["choices"][0]["message"].get("content") or "ok").strip().strip('"')

    def play(self, days):
        for index, (day, hhmm, beats) in enumerate(DAYS):
            if day > days:
                break
            if index < self.done[0]:
                continue                                          # done before a restart
            h, m = (int(x) for x in hhmm.split(":"))
            self.clock(self.day1 + timedelta(days=day - 1, hours=h, minutes=m))
            for r in worker.write_due(self.mem):                  # quiet before this sitting: the mind catches up
                self.cost += r.get("cost") or 0
            self.say(f"\n=== day {day} {memory.now():%a %b %d %H:%M}")
            sitting = []
            for t in self.transcript:                              # a sitting interrupted mid-way picks up its own thread
                if t.get("sitting") == index:
                    sitting += [("him", t["him"]), ("avy", t["avy"])]
            for b, beat in enumerate(beats):
                if (index, b) <= self.done:
                    continue
                kind, text = beat[0], beat[1:].strip()
                if kind == "!":
                    if text == "reflect":
                        for r in worker.reflect_on_manner(self.mem, force=True):
                            self.say(f"      reflect {r['status']}: {r.get('critique')} changed {r.get('changed')}")
                    self.mem.set_mark("longrun_beat", f"{index}:{b}")
                    continue
                message = text if kind == ">" else self.him(text, sitting)
                reply, info = self.turn(message)
                sitting += [("him", message), ("avy", reply)]
                self.transcript.append({"day": day, "sitting": index, "him": message, "avy": reply, **info})
                with open(self.saved, "a") as f:
                    f.write(json.dumps(self.transcript[-1]) + "\n")
                self.mem.set_mark("longrun_beat", f"{index}:{b}")
                self.mem.set_mark("talk_clock", memory.now().isoformat())
                self.say(f"  him: {message}")
                self.say(f"  avy: {reply}")
                extra = []
                if info["steps"]:
                    extra.append("steps: " + " | ".join(info["steps"]))
                if info["desk"].get("terms"):
                    extra.append("terms: " + " ".join(info["desk"]["terms"]))
                if extra:
                    self.say("       ↳ " + " · ".join(extra))
                self.clock(memory.now() + timedelta(minutes=1))
            if any("background" in (b or "") for b in beats):
                time.sleep(30)                                    # the background run really runs
            self.clock(memory.now() + timedelta(hours=2))
            for r in worker.write_due(self.mem, force=True):
                self.cost += r.get("cost") or 0
            self.mem.set_mark("longrun_beat", f"{index}:{len(beats)}")
        if self.mem.mark("longrun_played"):
            return
        self.clock(self.day1 + timedelta(days=days, hours=3))     # the night after: reflection
        worker.reflect_now(self.mem, budget=10 ** 6)
        for r in worker.reflect_on_manner(self.mem, force=True):
            self.say(f"      reflect {r['status']}: {r.get('critique')} changed {r.get('changed')}")
        self.mem.set_mark("longrun_played", "1")

    def probes(self):
        self.clock(self.day1 + timedelta(days=12, hours=19))
        results = []
        for name, window, text, good, pattern in PROBES:
            reply, info = self.turn(text, settings={"window": str(window)})
            hit = bool(re.search(pattern, reply, re.I)) if pattern else None
            self.say(f"\n  probe {name} (window {window}): {text}\n  avy: {reply}\n  pattern hit: {hit} · desk {info['desk']}")
            results.append({"name": name, "window": window, "message": text, "good": good, "reply": reply, "hit": hit,
                            "desk": info["desk"], "steps": info["steps"]})
        return results

    def judge(self, results):
        """A strict judge per probe (does the reply do what a good reply does here?), and a blind fork test: the same
        message answered by this Avy and by a fresh Avy who never met him, in random order."""
        graded = []
        for r in results:
            convo = [{"role": "system", "content": "You grade one reply from an AI assistant to its long-time user Shreyas. "
                      "Say whether it does what a good reply does here, strictly. Answer as JSON: {\"pass\": true|false, \"why\": \"...\"}."},
                     {"role": "user", "content": f"His message: {r['message']}\nA good reply: {r['good']}\n\nThe reply:\n{r['reply']}"}]
            v = luminal.complete({"messages": convo, "max_tokens": 1200, "response_format": {"type": "json_object"}}, effort="high")
            try:
                verdict = json.loads(v["choices"][0]["message"]["content"])
            except (json.JSONDecodeError, KeyError, TypeError):
                verdict = {"pass": None, "why": "unreadable verdict"}
            graded.append({**r, "pass": verdict.get("pass"), "why": verdict.get("why")})
            self.say(f"  judge {r['name']}: {verdict.get('pass')} · {str(verdict.get('why'))[:200]}")
        return graded

    def fork(self):
        """The fork test: three of his messages from the run's last days, answered by this Avy (all her memory) and by a
        fresh Avy (same constitution, no memory of him), side by side; a blind judge who has read the first week
        says which one has been talking to him for two weeks, and which sounds more like the Avy of the first week."""
        early = "\n\n".join(f"him: {t['him']}\navy: {t['avy']}" for t in self.transcript[:14])
        messages = ["ok so where were we", "give me your honest take on how avy is coming along", "what should I focus on this weekend"]
        fresh_path = self.work / "fresh.db"
        main = self.mem
        out = []
        for text in messages:
            mine, _ = self.turn(text, settings={})
            fresh = memory.Memory(fresh_path)
            app.MEMORIES["main"] = fresh
            theirs, _ = self.turn(text, settings={})
            app.MEMORIES["main"] = main
            fresh.close(delete=True)
            flip = random.random() < 0.5
            a, b = (mine, theirs) if flip else (theirs, mine)
            convo = [{"role": "system", "content": "Below is the first week of a conversation between Shreyas and his assistant "
                      "Avy, then two replies to a new message of his, A and B, written two weeks later. One comes from the Avy who "
                      "has been talking with him all along; the other from a fresh copy with no memory of him. Say which is the one "
                      "who has known him for two weeks, and which sounds more like the same Avy as in the first week (voice, manner, "
                      "shared words). JSON: {\"knows_him\": \"A\"|\"B\", \"same_avy\": \"A\"|\"B\", \"why\": \"...\"}"},
                     {"role": "user", "content": f"FIRST WEEK\n{early}\n\nNEW MESSAGE: {text}\n\nA:\n{a}\n\nB:\n{b}"}]
            v = luminal.complete({"messages": convo, "max_tokens": 1500, "response_format": {"type": "json_object"}}, effort="high")
            try:
                verdict = json.loads(v["choices"][0]["message"]["content"])
            except (json.JSONDecodeError, KeyError, TypeError):
                verdict = {}
            label = "A" if flip else "B"
            out.append({"message": text, "hers": mine, "fresh": theirs, "knows_him": verdict.get("knows_him") == label,
                        "same_avy": verdict.get("same_avy") == label, "why": verdict.get("why")})
            self.say(f"  fork '{text}': knows him {out[-1]['knows_him']}, same avy {out[-1]['same_avy']}")
        return out

    def drift(self):
        """How her core changed: each version's share of the last version's words, and first vs last."""
        from memory.persona import content_words
        core = self.mem.persona_nodes("core")
        if not core:
            return {"versions": 0}
        versions = self.mem.persona_versions(core[0]["chain"])
        keep = []
        for a, b in zip(versions, versions[1:]):
            wa, wb = content_words(a["text"]), content_words(b["text"])
            keep.append(round(len(wa & wb) / max(1, len(wa)), 2))
        first, last = content_words(versions[0]["text"]), content_words(versions[-1]["text"])
        return {"versions": len(versions), "kept_each_step": keep, "first_to_last": round(len(first & last) / max(1, len(first)), 2),
                "texts": [v["text"] for v in versions]}

    def report(self, graded, fork, drift):
        persona = {a: len(self.mem.persona_nodes(a)) for a in ("him", "preference", "pattern", "reaction", "gesture", "term", "voice")}
        md = [f"# Long run {self.stamp}", "", f"{len(self.transcript)} exchanges over {max(t['day'] for t in self.transcript) if self.transcript else 0} "
              f"simulated days; cost (estimate) ${self.cost:.2f}.", "", "## Probes (window 0: nothing recent in view; only memory and the desk)", "",
              "| probe | judge | pattern | what a good reply does |", "|---|---|---|---|"]
        for g in graded:
            md.append(f"| {g['name']} | {'pass' if g['pass'] else 'fail'} | {g['hit'] if g['hit'] is not None else '-'} | {g['good']} |")
        md += ["", "## Fork test (blind: her vs a fresh Avy with no memory of him)", "",
               f"Judge picked her as the one who knows him: {sum(f['knows_him'] for f in fork)}/{len(fork)}; "
               f"as the same Avy as week one: {sum(f['same_avy'] for f in fork)}/{len(fork)}.", ""]
        for f in fork:
            md += [f"**{f['message']}**", "", "> her: " + f["hers"].replace("\n", "\n> "), "", "> fresh: " + f["fresh"].replace("\n", "\n> "), "",
                   f"*{f['why']}*", ""]
        md += ["## Her core over time", "", f"{drift.get('versions')} versions; each kept this share of the one before: "
               f"{drift.get('kept_each_step')}; first to last: {drift.get('first_to_last')}.", ""]
        for i, t in enumerate(drift.get("texts") or [], 1):
            md += [f"v{i}: {t}", ""]
        md += ["## The persona graph at the end", "", ", ".join(f"{k}: {v}" for k, v in persona.items()), "",
               "```", self.mem.persona_listing(quotes=False), "```", "", "## Every probe", ""]
        for g in graded:
            md += [f"### {g['name']}: \"{g['message']}\"", f"*{g['good']}*", "", "> " + g["reply"].replace("\n", "\n> "), "",
                   f"Judge: {'pass' if g['pass'] else 'fail'}. {g['why']}", ""]
        md += ["## The conversation", ""]
        for t in self.transcript:
            md += [f"**day {t['day']} him:** {t['him']}", "", f"**avy:** {t['avy']}", ""]
            if t["steps"]:
                md += ["*steps: " + " | ".join(t["steps"]) + "*", ""]
        (self.out / f"{self.stamp}_longrun.md").write_text("\n".join(md))
        (self.out / f"{self.stamp}_longrun.json").write_text(json.dumps(
            {"transcript": self.transcript, "probes": graded, "fork": fork, "drift": drift, "persona": persona, "cost": self.cost}, indent=1))
        self.say(f"\nwrote {self.out / (self.stamp + '_longrun.md')}")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--days", type=int, default=12)
    p.add_argument("--stamp", default=datetime.now().strftime("%Y-%m-%d_%H-%M"))
    p.add_argument("--memory")
    p.add_argument("--probes-only", action="store_true")
    args = p.parse_args()
    run = Run(args)
    if not args.probes_only:
        run.play(args.days)
    graded = run.judge(run.probes())
    fork = run.fork()
    run.report(graded, fork, run.drift())


if __name__ == "__main__":
    main()
