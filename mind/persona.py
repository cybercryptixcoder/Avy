"""Where the model works on the persona (memory/persona.py): two jobs, both through the jobs engine.

    Keep      after every exchange (fast, thinking off). Reads his newest message against her reply before it and
              records what it shows: a preference he stated, something always true about him, how he reacted to what
              she did, a word he coined, a pattern he named; and anything dated he mentioned that isn't on the
              calendar. Most exchanges change nothing, and an empty answer is the right one then.
    Reflect   every dozen or so of her replies, and in quiet spells (thinking low). Constitutional-AI style: critique
              her recent replies against her constitution and his reactions, then rewrite her core a little (code
              refuses a rewrite that keeps too little of the last one), record what's working (gestures), keep the
              replies that landed as voice examples, and infer patterns that show up across sittings.

Both propose; code disposes. Every node must quote the messages it rests on (located by code, like Write's
evidence) and stay within its size. The graph grows; what any one message pulls from it is fixed (memory/persona.py).
"""

import re

from memory import NAME, ASPECTS, locate, when, who, clip
from memory.desk import parse_when

from . import llm
from .jobs import Job, Plan

KEEP_CONTEXT = 6          # messages shown to the keeper (the exchange, and what came just before it)
REFLECT_EVERY = 12        # her replies between reflections on her manner
REFLECT_SPAN = 40         # messages a reflection reads, at most
CONSTITUTION = None       # set by app.py: the text of CONSTITUTION.md, so reflection critiques against the real thing


def quote_schema():
    return {"type": "array", "items": llm.obj({"message": {"type": "integer"}, "quote": {"type": "string"}})}


def node_schema(aspects):
    return llm.obj({
        "id": llm.nullable({"type": "string"}),
        "aspect": {"type": "string", "enum": list(aspects)},
        "title": {"type": "string"},
        "text": {"type": "string"},
        "scope": llm.nullable({"type": "string"}),
        "origin": {"type": "string", "enum": ["user", "avy", "inferred"]},
        "certainty": llm.nullable({"type": "string", "enum": ["likely", "possible"]}),
        "message": llm.nullable({"type": "integer"}),
        "quotes": quote_schema(),
        "retire": {"type": "boolean"},
        "why": {"type": "string"},
    })


LINK_SCHEMA = llm.obj({"a": {"type": "string"}, "b": {"type": "string"},
                       "kind": {"type": "string", "enum": ["supports", "undercuts", "refines", "example_of", "related"]},
                       "reason": {"type": "string"}})


def shown_messages(mem, first, last):
    msgs = mem.messages_between(first, last)
    return {m["id"]: m for m in msgs}, "\n".join(
        f"#{m['id']} {when(m['at'])}, {who(m['role'], m.get('via'))}: {clip(m['text'], 0, 1600)}" for m in msgs)


def node_ops(mem, nodes, shown, aspects, by, plan):
    """Check proposed persona nodes and turn what passes into ops (plan.ops), problems into plan.problems.
    Returns {title: ref} for nodes new in this answer, so links can point at them."""
    refs, active = {}, {n["chain"]: n for n in mem.persona_nodes(state=None)}
    for i, n in enumerate(nodes or []):
        name = f"node {i + 1} ({str(n.get('title') or '?')[:40]})"
        aspect = n.get("aspect")
        if aspect not in aspects:
            plan.problems.append(f"{name}: aspect must be one of {', '.join(aspects)}")
            continue
        chain = None
        if n.get("id"):
            m = re.fullmatch(r"pa(\d+)", str(n["id"]).strip().lower())
            if not m or int(m.group(1)) not in active:
                plan.problems.append(f"{name}: {n['id']} isn't a persona node; use an id from the list, or null for a new one")
                continue
            chain = int(m.group(1))
            if active[chain]["aspect"] != aspect:
                plan.problems.append(f"{name}: {n['id']} is a {active[chain]['aspect']}, not a {aspect}")
                continue
        spans, bad = [], False
        for q in n.get("quotes") or []:
            mid = q.get("message")
            if mid not in shown:
                plan.problems.append(f"{name}: #{mid} isn't one of the messages you were shown")
                bad = True
                continue
            span = locate(q.get("quote") or "", shown[mid]["text"])
            if not span:
                plan.problems.append(f"{name}: \"{str(q.get('quote'))[:70]}\" isn't in #{mid}; copy the words exactly")
                bad = True
                continue
            spans.append((mid, *span))
        if bad:
            continue
        if n.get("retire"):
            if not chain:
                plan.problems.append(f"{name}: only an existing node (an id) can be retired")
                continue
            plan.ops.append({"op": "persona", "chain": chain, "aspect": aspect, "retire": True, "by": by,
                             "why": n.get("why") or "retired"})
            continue
        if not spans and not chain:
            plan.problems.append(f"{name}: quote the message(s) it rests on: the message number and the exact words")
            continue
        words = len(re.findall(r"\S+", n.get("text") or ""))
        if words > ASPECTS[aspect]["words"]:
            plan.problems.append(f"{name}: at most {ASPECTS[aspect]['words']} words for a {aspect} (it has {words}); say it shorter")
            continue
        if ASPECTS[aspect]["said"] and not chain and not any(shown[s[0]]["role"] == "user" for s in spans):
            plan.problems.append(f"{name}: a {aspect} rests on {NAME}'s own words: quote his message")
            continue
        origin = n.get("origin") or "avy"
        if origin == "user" and not any(shown[s[0]]["role"] == "user" for s in spans) and not chain:
            origin = "avy"
            plan.notes.append(f"{name}: origin set to avy (no words of his quoted)")
        op = {"op": "persona", "chain": chain, "aspect": aspect, "title": n.get("title"), "text": n.get("text"),
              "scope": n.get("scope"), "origin": origin, "certainty": n.get("certainty"), "message": n.get("message"),
              "evidence": spans, "by": by, "why": n.get("why") or "", "ref": f"n{i + 1}"}
        plan.ops.append(op)
        refs[str(n.get("title") or "").strip().lower()] = f"n{i + 1}"
    return refs


def link_ops(links, refs, by, plan):
    for i, l in enumerate(links or []):
        ends = []
        for end in (l.get("a"), l.get("b")):
            end = str(end or "").strip()
            if re.fullmatch(r"pa\d+", end.lower()):
                ends.append(end.lower())
            elif end.lower() in refs:
                ends.append(refs[end.lower()])
            else:
                plan.problems.append(f"link {i + 1}: {end!r} is neither a persona node (pa12) nor the title of a node in this answer")
                break
        if len(ends) == 2:
            plan.ops.append({"op": "persona_link", "a": ends[0], "b": ends[1], "kind": l.get("kind"),
                             "reason": l.get("reason") or "", "by": by})


# --------------------------------------------------------------------------------------------------------------
# Keep: after every exchange
# --------------------------------------------------------------------------------------------------------------

KEEP_ASPECTS = ("him", "preference", "reaction", "gesture", "term", "situation")   # patterns are reflection's: across sittings

KEEP = f"""You keep Avy's persona: her model of the relationship with {NAME}, a small graph that persists through every
message so that she stays the same Avy and keeps getting better with him, instead of meeting a stranger each time.
You look at the newest exchange and record only what it actually shows. Most exchanges show nothing new: then answer
with empty lists. That's the usual, correct answer. Never invent, never pad.

What you can record (each is a node: a short title, one sentence of text, and his exact words as evidence):
- preference: a rule he states (or clearly agrees to) for how Avy should work with him: length, format, tone, units,
  what to do or never do. Scope: "always", or one of the situations if it only holds there. If it's an exception to
  a general rule, link it (kind refines, from the specific one to the general one).
- him: something lasting about who he is: name, where he lives, what he studies or works on, the people who matter,
  constraints (an allergy, a schedule). Not passing states or moods.
- reaction: how he responded to something specific she did in her reply just before his message, when his message
  clearly judges it: a correction ("too long", "don't do that"), irritation, a laugh at something she said, "perfect",
  thanks, repeating himself because she missed it, ignoring a question she asked. Quote his reaction AND the part of
  her reply it was about. Corrections matter most. Not reactions: moving to another topic, "ok", "hm yeah", simply
  answering her question, or anything that doesn't tell you how her move landed.
- gesture: a small move of hers that clearly worked, with his reaction as the evidence (link reaction supports gesture).
  When a reaction undercuts a gesture already recorded, link it (undercuts).
- term: a word or phrase with a meaning private to the two of them (he coins it, or she does and he picks it up).
  Quote the message where it was born; set message to that message's number.
Patterns in how he works or talks are not yours to record: they need several conversations, and reflection does that.
- situation: a new kind of conversation they keep having that none of the existing ones fits. Rarely needed.
Also say which kind of conversation his newest message is (situation: one of the situation titles, or null if it's no
particular kind); it becomes an example, so Avy learns how he talks in each kind.

Rules:
1. Revise before you add. If an existing node already covers it, give its id (pa12) and the updated text, with the new
   quote: it becomes a new version and gets stronger. Add a new node only for something genuinely new. If he takes
   something back, retire that node (retire: true) or revise it.
2. Evidence: every node quotes the messages it rests on, copied exactly, with the message number. Only messages shown.
   A preference, him, or reaction must quote {NAME}'s own words.
3. Text is about the relationship, written plainly ("Keep replies to a few lines unless he asks for depth"), never a
   transcript of the exchange.
4. Calendar: if he mentioned something with a date or time (an appointment, a deadline, a trip, a reminder he wants),
   or a task he means to do, and it isn't on the calendar, add it; if something on it moved, finished or was
   cancelled, update it by id. Dates: YYYY-MM-DD, or YYYY-MM-DDTHH:MM with a time, worked out from the clock and the
   two weeks spelled out below. Quote his words. Leave the calendar alone if Avy already handled it."""

KEEP_TOOL = llm.tool("keep", "What this exchange shows about the relationship, and the calendar. Empty lists when nothing.", {
    "situation": llm.nullable({"type": "string"}),
    "nodes": {"type": "array", "items": node_schema(KEEP_ASPECTS)},
    "links": {"type": "array", "items": LINK_SCHEMA},
    "calendar": {"type": "array", "items": llm.obj({
        "id": llm.nullable({"type": "string"}), "title": {"type": "string"},
        "kind": {"type": "string", "enum": ["event", "deadline", "reminder", "task"]},
        "start": llm.nullable({"type": "string"}), "end": llm.nullable({"type": "string"}),
        "status": {"type": "string", "enum": ["planned", "done", "cancelled", "missed"]},
        "notes": {"type": "string"}, "quote": llm.nullable(llm.obj({"message": {"type": "integer"}, "quote": {"type": "string"}}))})},
})


class Keep(Job):
    """One exchange: his newest message (and her reply to it), read against what came just before."""
    name = "keep"
    tool = KEEP_TOOL
    max_tokens = 3000
    effort = "none"

    def __init__(self, mem, last):
        self.mem, self.last = mem, last
        self.first = max(1, last - KEEP_CONTEXT + 1)
        self.shown, self.text = shown_messages(mem, self.first, last)
        self.focus = f"#{self.first}-#{last}"

    def prompt(self):
        mem = self.mem
        calendar = "\n".join(mem.timeline_line(t) for t in mem.timeline_heads() if t["status"] == "planned") or "(empty)"
        newest = max((i for i, m in self.shown.items() if m["role"] == "user"), default=self.last)
        return [{"role": "system", "content": KEEP},
                {"role": "user", "content": f"{mem.clock_text()}\n\nThe persona now:\n{mem.persona_listing(KEEP_ASPECTS, focus=self.text)}\n\n"
                                            f"The calendar (planned):\n{calendar}\n\nThe conversation (the exchange to look at "
                                            f"is #{newest} and after; earlier messages are what it responds to):\n{self.text}"}]

    def check(self, answer):
        plan = Plan()
        if not isinstance(answer, dict):
            plan.problems.append("Answer with nodes, links and calendar (empty lists are fine).")
            return plan
        refs = node_ops(self.mem, answer.get("nodes"), self.shown, KEEP_ASPECTS, "keeper", plan)
        link_ops(answer.get("links"), refs, "keeper", plan)
        if answer.get("situation"):
            if self.mem.situation_named(answer["situation"]):
                plan.extra["situation"] = answer["situation"]
            else:
                plan.notes.append(f"situation {answer['situation']!r} isn't one of the situations; not labeled")
        for i, c in enumerate(answer.get("calendar") or []):
            name = f"calendar {i + 1} ({str(c.get('title'))[:40]})"
            for k in ("start", "end"):
                if c.get(k) and not parse_when(c[k]):
                    plan.problems.append(f"{name}: {k} must look like 2026-10-20 or 2026-10-20T15:00")
            q, source, quote = c.get("quote") or {}, None, None
            if q:
                if q.get("message") not in self.shown or not locate(q.get("quote") or "", self.shown[q["message"]]["text"]):
                    plan.problems.append(f"{name}: the quote isn't in #{q.get('message')}; copy his words exactly")
                    continue
                source, quote = q["message"], q["quote"]
            elif not c.get("id"):
                plan.problems.append(f"{name}: quote the words he used for it")
                continue
            plan.ops.append({"op": "timeline", "chain": c.get("id"), "title": c.get("title"), "kind": c.get("kind"),
                             "start": c.get("start"), "end": c.get("end"), "status": c.get("status"), "notes": c.get("notes"),
                             "source": source, "quote": quote, "by": "keeper", "why": "from the conversation"})
        return plan

    def after(self, run_id, plan, results, refs):
        newest = max((i for i, m in self.shown.items() if m["role"] == "user"), default=None)
        if plan.extra.get("situation") and newest:
            self.mem.label_situation(newest, plan.extra["situation"], run_id)
        self.mem.set_mark("kept_through", self.last)
        return {"changed": [r["target"] for r in results if r["applied"] and not r.get("unchanged")],
                "situation": plan.extra.get("situation")}


# --------------------------------------------------------------------------------------------------------------
# Reflect: on her own manner, Constitutional-AI style
# --------------------------------------------------------------------------------------------------------------

REFLECT_ASPECTS = ("core", "gesture", "pattern", "voice")

REFLECT = f"""You are Avy, looking back over your recent replies to {NAME}, the way a thoughtful person reviews how a
conversation went. Your constitution, which you hold yourself to, is below; so is your persona, the graph of what
you've learned about being with him. The point is growth that keeps you yourself: you become more specifically his
Avy over time, a little at a time, never a different person and never a generic assistant.

Do this:
1. Critique each of your replies shown, against your constitution and against him. Did it land? The evidence is what
   he said next: he built on it, laughed, said "perfect", used your words; or he corrected you, repeated himself, said
   it was too long, ignored your question, changed the subject. Name any break of your manner plainly: a greeting or
   "great question" opener, a stock closer or menu of offers, a reflexive question, guessing his mood, an unasked
   callback to the past, padding, a list where talk would do, flattery, hedging to avoid a straight answer.
2. Your core: who you are with him, in the first person, at most 150 words. It's not your constitution restated;
   it's what's specific to you two: the register that works, the shared ground, the lessons from what you got wrong.
   If you have one, write its next version: keep what still holds and change a few things the evidence supports
   (code refuses a version that keeps too little of the last one). If there isn't one yet, write the first, short.
   Quote the messages behind what you changed. If nothing should change, leave core null.
3. Gestures: record or revise at most 3 small moves of yours that clearly worked with him, each quoting his
   reaction. Retire one his reactions keep undercutting.
4. Voice: at most 2 of your replies here that are most you and landed with him: aspect voice, message = your reply,
   scope = the kind of conversation (one of the situations), title a few words, text why it worked. Retire a voice
   example that no longer sounds like you.
5. Patterns: if you see how he tends to work or talk across at least two different sittings, record it (origin
   inferred, certainty likely or possible), quoting both. Not traits, not judgments: what he does.
Revise before you add (give the id). Everything quotes exact words with the message number."""

REFLECT_TOOL = llm.tool("reflect_on_manner", "Your critique of your recent replies, and what changes in your persona.", {
    "critique": {"type": "array", "items": llm.obj({"message": {"type": "integer"},
                                                    "verdict": {"type": "string", "enum": ["landed", "flat", "missed", "corrected"]},
                                                    "note": {"type": "string"}})},
    "core": llm.nullable(llm.obj({"text": {"type": "string"}, "quotes": quote_schema(), "why": {"type": "string"}})),
    "nodes": {"type": "array", "items": node_schema(("gesture", "pattern", "voice"))},
    "links": {"type": "array", "items": LINK_SCHEMA},
})


class Reflect(Job):
    name = "reflect"
    tool = REFLECT_TOOL
    max_tokens = 6000
    effort = "low"

    def __init__(self, mem, first, last):
        self.mem, self.first, self.last = mem, first, last
        self.shown, self.text = shown_messages(mem, first, last)
        self.focus = f"#{first}-#{last}"

    def prompt(self):
        return [{"role": "system", "content": REFLECT + "\n\nYOUR CONSTITUTION\n" + (CONSTITUTION or "(missing)")},
                {"role": "user", "content": f"{self.mem.clock_text()}\n\nYour persona now:\n{self.mem.persona_listing(focus=self.text)}\n\n"
                                            f"The conversation to review:\n{self.text}"}]

    def check(self, answer):
        plan = Plan()
        if not isinstance(answer, dict):
            plan.problems.append("Answer with critique, core, nodes and links.")
            return plan
        for c in answer.get("critique") or []:
            if c.get("message") not in self.shown or self.shown[c["message"]]["role"] != "assistant":
                plan.problems.append(f"critique: #{c.get('message')} isn't one of your replies shown")
        core = answer.get("core")
        if core and core.get("text"):
            nodes = [{"id": None, "aspect": "core", "title": f"Avy with {NAME}", "text": core["text"], "scope": None,
                      "origin": "avy", "certainty": None, "message": None, "quotes": core.get("quotes") or [],
                      "retire": False, "why": core.get("why") or ""}]
            node_ops(self.mem, nodes, self.shown, ("core",), "reflect", plan)
        for n in answer.get("nodes") or []:
            if n.get("aspect") == "voice":
                if n.get("message") not in self.shown or self.shown[n["message"]]["role"] != "assistant":
                    if not n.get("retire"):
                        plan.problems.append(f"voice \"{str(n.get('title'))[:40]}\": message must be one of your replies shown")
                        continue
                if not n.get("quotes") and n.get("message") in self.shown:
                    text = self.shown[n["message"]]["text"]
                    n["quotes"] = [{"message": n["message"], "quote": text[:120]}]
        refs = node_ops(self.mem, answer.get("nodes"), self.shown, REFLECT_ASPECTS, "reflect", plan)
        for op in plan.ops:                                  # a voice example belongs to its kind of conversation
            if op.get("aspect") == "voice" and op.get("scope"):
                situation = self.mem.situation_named(op["scope"])
                if situation:
                    op["link_situation"] = situation["chain"]
        link_ops(answer.get("links"), refs, "reflect", plan)
        plan.extra["critique"] = answer.get("critique") or []
        return plan

    def after(self, run_id, plan, results, refs):
        mem = self.mem
        for op in plan.ops:
            if op.get("link_situation") and op.get("ref") in refs:
                mem.apply({"op": "persona_link", "a": refs[op["ref"]], "b": op["link_situation"], "kind": "example_of",
                           "reason": "her reply that landed in this kind of conversation"}, run_id)
        mem.set_mark("reflected_manner_through", self.last)
        verdicts = [c.get("verdict") for c in plan.extra.get("critique") or []]
        return {"critique": {v: verdicts.count(v) for v in set(verdicts)},
                "changed": [r["target"] for r in results if r["applied"] and not r.get("unchanged")]}


def reflect_due(mem, force=False):
    """The stretch her next reflection on manner should read, or None: once REFLECT_EVERY of her replies have come
    since the last one (or any, when forced)."""
    done = int(mem.mark("reflected_manner_through", 0) or 0)
    last = mem.last_id()
    replies = mem.value("SELECT COUNT(*) FROM messages WHERE id > ? AND role = 'assistant' AND via != 'claude'", done) or 0
    if replies == 0 or (replies < REFLECT_EVERY and not force):
        return None
    return max(done + 1, last - REFLECT_SPAN + 1), last
