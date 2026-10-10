"""The writer: turns a stretch of the log (an episode) into knowledge, in the background.

DeepSeek does the judgment: what's worth knowing, how to say it, what it connects to.
Code does everything that has to be right every time:
  1. picks the stretch, and what memory already holds that it may touch (from the whole memory)
  2. asks for one structured answer (write_episode)
  3. checks every part: messages in the stretch, every quote really in its message, versions of
     nodes that exist, no duplicates, edges between real nodes with a kind and a reason
  4. sends problems back (up to twice), then saves what passes through the one door
After a write, the new nodes go to the connector (reflect.Connect), which looks for connections
across the whole memory, not just this stretch.
"""

import re

from memory import NAME, SHAPES, KINDS, embedder, locate, node_ref, message_ref, when, who, same_title
from memory.rules import SELF

from . import llm
from .jobs import Job, Plan

PAGE = 20              # messages per episode, at most
MIN_STRETCH = 4        # the smallest page, when the /window: is tiny
CONTEXT_BEFORE = 4     # earlier messages shown for context (not to be cited)
SHOW_NODES = 50        # existing nodes shown, to connect to or update
MAX_EDGES = 6          # edges per node in one answer
RETRY_MINUTES = 10     # after a failed run, wait this long before trying the same stretch again
GIVE_UP_AFTER = 3      # after this many unusable answers, save a bare episode and move on

INSTRUCTIONS = f"""You keep the memory of Avy, a personal assistant in one endless conversation with {NAME}.
The conversation log is permanent and never changes. You don't summarize it: you turn what's worth
knowing into knowledge, and every piece of knowledge points at the exact words it came from.

You're given one stretch of the conversation, and what memory already holds that it may touch. Write:
- a headline for the stretch
- nodes: what's worth knowing later, one thing or one claim per node
- edges: how the nodes connect, to each other and to what memory already holds

Nodes have one of three shapes:
  thing        something with an identity that other knowledge gathers around: a person, a pet, a place,
               an organization, a course, a project, an ongoing effort, a book, a topic. Its text says only
               what it is, in one sentence; facts that change get their own nodes, connected to it.
  information  one claim: a fact, an event, a plan, a decision and why, a preference, a problem, a result.
  idea         a concept, a principle, an insight, a proposal, a hypothesis, an analogy, an open question,
               whether {NAME} came up with it, read about it, or Avy suggested it.
Give each node a label: a word or two saying what it is, freely chosen ("person", "plan", "sleep log",
"principle", "bug", "gift idea").

What deserves a node: the people, places and things in {NAME}'s life; facts about him and his world;
plans, dates, decisions; preferences; problems he's working on and how they turned out; and the ideas
and concepts he talks about, his own most of all. A conversation about an interesting concept should
leave nodes for the concepts themselves (what they are, how they work), not a note that it happened.
Avy's suggestions deserve a node when he takes them up, or when they're ideas in their own right.
Skip greetings and small talk, passing moments that show nothing lasting, his questions about things
memory already holds and Avy's answers to them (her recalling or repeating something isn't new knowledge),
Avy's generic advice, and anything only implied. Never write a node saying something is unknown,
unanswered, or was never mentioned: memory holds what is known.

Things: when the conversation is about something with an identity that has no node yet, create it, even
if it was never named: name it yourself, descriptively ("the plant-watering gadget {NAME} is building").
Connect what belongs to it with part_of. {NAME} himself is never a node: facts about him are information,
connected to what they concern (his sleep, his course, his job).

Rules:
1. Evidence. Every node cites the message(s) it came from, with the exact words copied character for
   character: a short span that shows the point. Only cite messages from the stretch to write. Code
   checks every quote, and decides from it who said it ({NAME} or Avy).
2. Write for someone who wasn't there. Titles are short names, like wiki page titles, that make sense on
   their own ("Maya's move to Toronto", not "The move"). Text: one or two plain sentences, with absolute
   dates worked out from the message times ("Friday", said on Thu Oct 9 2026, is Fri Oct 10, 2026). Put
   the date a node is about in "when" (YYYY-MM-DD), or null.
3. Versions. If something updates, corrects or completes a node memory already holds (a changed plan, a
   task now done, a corrected fact, a concept refined), write a new version: set replaces to its handle
   (k12) and keep its title. Never create a second node with the same title as an existing one. If {NAME}
   confirms something Avy had only inferred or suggested, write a new version with his words as evidence.
4. Edges. Connect each node to what it belongs with, by handle: k12 for what memory holds, n1 for your new
   nodes. At most {MAX_EDGES} per node. Kinds ("from" -> "to"):
     part_of     from belongs to to, or is a piece or an instance of it
     builds_on   from uses, depends on, follows from, or was inspired by to
     like        they're alike in a way that matters, even across very different topics
     against     they're in tension: one contradicts, undermines or is an alternative to the other
     related     connected some other way
   Every edge needs a reason: one short sentence that explains the connection to someone who only sees
   the two titles. If {NAME} made the connection himself ("this is just like..."), add his words in said.
5. If nothing in the stretch is worth keeping, return no nodes, but still write a headline.

Answer only by calling write_episode."""

TOOL = llm.tool("write_episode", "Save what this stretch of the conversation holds that's worth knowing.", {
    "headline": {"type": "string", "description": "What this stretch was about, in under 12 words."},
    "nodes": {"type": "array", "items": llm.obj({
        "ref": {"type": "string", "description": "n1, n2, ... in order. Edges refer to new nodes by these."},
        "replaces": llm.nullable({"type": "string", "description": "The node this is a new version of, like \"k12\"."}),
        "shape": {"type": "string", "enum": list(SHAPES)},
        "label": {"type": "string", "description": "A word or two saying what it is."},
        "title": {"type": "string", "description": "A short name, like a wiki page title."},
        "text": {"type": "string", "description": "One or two sentences."},
        "when": llm.nullable({"type": "string", "description": "The date it's about, YYYY-MM-DD."}),
        "evidence": {"type": "array", "items": llm.obj({
            "message": {"type": "integer", "description": "The message number: 41 for #41."},
            "quote": {"type": "string", "description": "The exact words from that message, copied character for character."},
        })},
    })},
    "edges": {"type": "array", "items": llm.obj({
        "from": {"type": "string", "description": "A node: n1 (new) or k12 (in memory)."},
        "to": {"type": "string"},
        "kind": {"type": "string", "enum": list(KINDS)},
        "reason": {"type": "string", "description": "Why, in one short sentence."},
        "said": llm.nullable(llm.obj({
            "message": {"type": "integer"},
            "quote": {"type": "string", "description": f"{NAME}'s exact words making this connection."},
        })),
    })},
})


def due(mem, page, force=False):
    """The next stretch to write as (first, last), or None if it isn't time yet."""
    stretch = mem.next_stretch(page, force=force)
    if not stretch or force:
        return stretch
    last_run = mem.row("SELECT * FROM runs WHERE job = 'write' AND focus = ? ORDER BY id DESC LIMIT 1", f"#{stretch[0]}-")
    if last_run and last_run["status"] in ("failed", "error"):
        from memory.common import minutes_between, stamp
        if minutes_between(last_run["at"], stamp()) < RETRY_MINUTES:
            return None
    return stretch


def describe(mem, n, degree=None):
    line = f"{mem.handle(n['chain'])} {n['shape']}" + (f" · {n['label']}" if n["label"] else "") + f" \"{n['title']}\": {n['text']}"
    bits = [mem.standing(n)]
    if n["about"]:
        bits.append(n["about"])
    if n["version"] > 1:
        bits.append(f"version {n['version']}")
    if degree:
        bits.append(f"{degree} connections")
    return line + f"  [{'; '.join(bits)}]"


def as_line(m, limit):
    text = m["text"] if len(m["text"]) <= limit else m["text"][:limit] + " …(cut here)"
    return f"#{m['id']} {when(m['at'])}  {who(m['role'])}: {text}"


class Write(Job):
    name = "write"
    tool = TOOL

    def __init__(self, mem, first, last):
        self.mem, self.first, self.last = mem, first, last
        self.stretch = {m["id"]: m for m in mem.messages_between(first, last)}
        self.focus = f"#{first}-"          # how a retry of the same stretch is recognized
        self.shown = self.nodes_to_show()

    def nodes_to_show(self):
        """What memory already holds that this stretch may touch: the biggest hubs, the newest nodes, and
        whatever each message brings up in search (from the whole memory). Current versions only."""
        mem = self.mem
        current = {n["chain"]: n for n in mem.current_nodes()}
        degree = {}
        for e in mem.live_edges():
            degree[e["a"]] = degree.get(e["a"], 0) + 1
            degree[e["b"]] = degree.get(e["b"], 0) + 1
        self.degree = degree
        picks = sorted((n for n in current.values() if n["shape"] == "thing"), key=lambda n: -degree.get(n["chain"], 0))[:12]
        picks += sorted(current.values(), key=lambda n: -n["id"])[:10]
        for m in self.stretch.values():
            text = m["text"][:1500]
            hits = mem.land([(text, 1.0, embedder.query(text))], k=12)
            picks += [current[c] for c in sorted(hits, key=lambda c: -hits[c]["score"])[:6] if c in current]
        seen, shown = set(), []
        for n in picks:
            if n["chain"] not in seen:
                seen.add(n["chain"])
                shown.append(n)
        return {n["chain"]: n for n in shown[:SHOW_NODES]}

    def prompt(self):
        mem = self.mem
        parts = []
        if self.shown:
            parts.append("What memory already holds that this may touch (current versions):\n"
                         + "\n".join(describe(mem, n, self.degree.get(n["chain"])) for n in self.shown.values()))
        else:
            parts.append("Memory is empty: this is the start.")
        before = mem.messages_between(max(1, self.first - CONTEXT_BEFORE), self.first - 1)
        if before:
            parts.append("Just before, for context only (already written; don't cite these):\n"
                         + "\n".join(as_line(m, 600) for m in before))
        parts.append(f"The stretch to write, #{self.first} to #{self.last}:\n"
                     + "\n".join(as_line(m, 4000 if m["role"] == "user" else 1500) for m in self.stretch.values()))
        return [{"role": "system", "content": INSTRUCTIONS}, {"role": "user", "content": "\n\n".join(parts)}]

    # --- checking the answer -----------------------------------------------------------------

    def check(self, answer):
        mem, plan = self.mem, Plan()
        problems, notes = plan.problems, plan.notes
        if not isinstance(answer, dict):
            plan.problems.append("The answer must be an object with a headline, nodes and edges.")
            return plan
        headline = " ".join(str(answer.get("headline") or "").split())
        if not headline:
            problems.append("The headline is empty.")
            headline = next((m["text"][:80] for m in self.stretch.values() if m["role"] == "user"), "(no headline)")
        elif len(headline) > 120:
            problems.append("The headline is too long; keep it under 12 words.")
            headline = headline[:120]
        current = {n["chain"]: n for n in mem.current_nodes()}

        # A. each node on its own
        kept, taken = [], set()
        raw = answer.get("nodes") if isinstance(answer.get("nodes"), list) else []
        for i, n in enumerate(raw, 1):
            n = n if isinstance(n, dict) else {}
            ref = str(n.get("ref") or "").strip()
            title = " ".join(str(n.get("title") or "").split())
            name = f'{ref or f"node {i}"} "{title}"'
            if not re.fullmatch(r"n\d+", ref) or ref in taken:
                problems.append(f"{name}: needs its own ref (n1, n2, ...), different from every other node's.")
                ref = next(f"n{k}" for k in range(i, 10_000) if f"n{k}" not in taken)
            taken.add(ref)
            shape = str(n.get("shape") or "").strip().lower()
            if shape not in SHAPES:
                problems.append(f"{name}: shape must be thing, information or idea.")
                continue
            if not title:
                problems.append(f"{ref}: the title is empty.")
                continue
            if " ".join(re.findall(r"[a-z]+", title.lower())) in SELF:
                problems.append(f"{name}: {NAME} himself isn't a node. Write what you know as information about what it concerns.")
                continue
            if len(title) > 80:
                problems.append(f"{name}: the title is too long; make it a short name.")
                title = title[:80]
            text = " ".join(str(n.get("text") or "").split()) or title
            if len(text) > 600:
                problems.append(f"{name}: the text is too long; one or two sentences.")
                text = text[:600]
            about = n.get("when")
            if about and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(about)):
                problems.append(f"{name}: when must be a date written YYYY-MM-DD, or null.")
                about = None
            evidence = []
            for c in n.get("evidence") if isinstance(n.get("evidence"), list) else []:
                c = c if isinstance(c, dict) else {}
                mid = message_ref(c.get("message"))
                if mid not in self.stretch:
                    problems.append(f"{name}: #{c.get('message')} isn't in the stretch you were given (#{self.first} to #{self.last}).")
                    continue
                span = locate(c.get("quote") or "", self.stretch[mid]["text"])
                if span:
                    evidence.append((mid, span[0], span[1], 1))
                else:
                    problems.append(f'{name}: the quote "{str(c.get("quote"))[:80]}" isn\'t in #{mid}. Copy the words exactly as they appear there.')
                    evidence.append((mid, 0, len(self.stretch[mid]["text"]), 0))   # if it stays wrong: the whole message
            evidence = list(dict.fromkeys(evidence))
            if any(v[3] for v in evidence):
                evidence = [v for v in evidence if v[3]]
            if not evidence:
                problems.append(f"{name}: needs evidence: the message number and the exact words it came from.")
                continue
            replaces = None
            if n.get("replaces") not in (None, "", "null"):
                replaces = node_ref(n["replaces"], mem.letter)
                if replaces is None or not mem.head(replaces):
                    problems.append(f"{name}: replaces {n['replaces']}, which isn't a node. Use a handle from the list, or null.")
                    replaces = None
            kept.append({"ref": ref, "name": name, "shape": shape, "label": " ".join(str(n.get("label") or "").split())[:40],
                         "title": title, "text": text, "about": about, "evidence": evidence, "replaces": replaces})

        # B. versions and duplicates
        remap, replacing, final = {}, {}, []
        for n in kept:
            if n["replaces"]:
                old = mem.head(n["replaces"])
                if (old["shape"] == "thing") != (n["shape"] == "thing"):
                    problems.append(f"{n['name']}: is a {n['shape']} but replaces {mem.handle(old['chain'])}, a {old['shape']}. "
                                    "A new version keeps the same sort of thing; otherwise connect to it instead.")
                    n["replaces"] = None
                elif old["chain"] in replacing:
                    problems.append(f"{n['name']}: {mem.handle(old['chain'])} is already getting a new version ({replacing[old['chain']]}). One per node.")
                    remap[n["ref"]] = replacing[old["chain"]]
                    continue
            if not n["replaces"]:
                twin = next((x for x in final if same_title(x["title"], n["title"]) and (x["shape"] == "thing") == (n["shape"] == "thing")), None)
                if twin:
                    problems.append(f"{n['name']}: has the same title as {twin['ref']}. Make it one node.")
                    remap[n["ref"]] = twin["ref"]
                    continue
                old = next((c for c in current.values() if same_title(c["title"], n["title"]) and c["shape"] == n["shape"]
                            and c["chain"] not in replacing), None)
                if old and old["shape"] == "thing":
                    notes.append(f"{n['name']}: {mem.handle(old['chain'])} already is this thing; used it instead of a copy.")
                    remap[n["ref"]] = old["chain"]
                    continue
                if old:
                    if same_title(old["text"], n["text"]):
                        notes.append(f"{n['name']}: repeats {mem.handle(old['chain'])} word for word; left out.")
                        remap[n["ref"]] = old["chain"]
                        continue
                    problems.append(f"{n['name']}: {mem.handle(old['chain'])} \"{old['title']}\" already exists. If this changes it, "
                                    f"set replaces: {mem.handle(old['chain'])}; if it's something else, give it a different title.")
                    n["replaces"] = old["chain"]          # if it stays this way: treat it as the new version
            if n["replaces"]:
                replacing[n["replaces"]] = n["ref"]
            final.append(n)

        # C. edges, now that every ref is settled
        refs = {n["ref"] for n in final}

        def resolve(value):
            """'n2' -> 'n2' (or what it was merged into); 'k12' -> 12. None if it isn't a node."""
            v = str(value or "").strip()
            if v in remap:
                return remap[v]
            if v in refs:
                return v
            c = node_ref(v, mem.letter)
            return c if c is not None and mem.current(c) else None

        edges, pairs, per_node = [], set(), {}
        for e in answer.get("edges") if isinstance(answer.get("edges"), list) else []:
            e = e if isinstance(e, dict) else {}
            a, b = resolve(e.get("from")), resolve(e.get("to"))
            label = f"edge {e.get('from')} -> {e.get('to')}"
            if a is None or b is None:
                problems.append(f"{label}: {e.get('from') if a is None else e.get('to')} isn't a node. Use n-refs from your answer or handles from the list.")
                continue
            if a == b or frozenset((a, b)) in pairs:
                continue
            kind = str(e.get("kind") or "")
            if kind not in KINDS:
                problems.append(f"{label}: kind must be one of {', '.join(KINDS)}.")
                kind = "related"
            reason = " ".join(str(e.get("reason") or "").split())
            if len(reason.split()) < 3:
                problems.append(f"{label}: needs a reason, one short sentence saying why they connect.")
                continue
            support, quote = {"kind": "inferred"}, None
            said = e.get("said") if isinstance(e.get("said"), dict) else None
            if said:
                mid = message_ref(said.get("message"))
                span = locate(said.get("quote") or "", self.stretch[mid]["text"]) if mid in self.stretch else None
                if span and self.stretch[mid]["role"] == "user":
                    support, quote = {"kind": "stated", "source": f"#{mid}"}, (mid, span[0], span[1])
                else:
                    problems.append(f"{label}: said must quote {NAME}'s exact words from one of his messages in the stretch.")
            for end in (a, b):
                per_node[end] = per_node.get(end, 0) + 1
            if per_node[a] > MAX_EDGES + 2 or per_node[b] > MAX_EDGES + 2:
                notes.append(f"{label}: over {MAX_EDGES} edges for one node; left out.")
                continue
            pairs.add(frozenset((a, b)))
            edges.append({"op": "connect", "a": a, "b": b, "kind": kind, "reason": reason, "support": support, "quote": quote})

        plan.ops = [{"op": "add_episode", "first": self.first, "last": self.last, "headline": headline}]
        for n in final:
            plan.ops.append({"op": "add_node", "ref": n["ref"], "shape": n["shape"], "label": n["label"], "title": n["title"],
                             "text": n["text"], "about": n["about"], "evidence": n["evidence"], "replaces": n["replaces"],
                             "episode": "@episode"})
        plan.ops += edges
        plan.extra["headline"] = headline
        return plan

    def after(self, run_id, plan, results, refs):
        """Things that came up together again: the edges already between them get a little stronger."""
        mem = self.mem
        made = [r for r in results if r["op"] == "add_node" and r["applied"]]
        touched = {r["chain"] for r in made}
        new_edges = {r.get("edge") for r in results if r["op"] == "connect" and r["applied"] and r.get("new")}
        touched |= {x for r in results if r["op"] == "connect" and r["applied"] for x in (mem.edge(r["edge"])["a"], mem.edge(r["edge"])["b"])}
        observed = 0
        for c in touched:
            for l in mem.links(c, live_only=False):
                if l["other"] in touched and l["edge"] not in new_edges and c < l["other"]:
                    mem.apply({"op": "connect", "a": l["a"], "b": l["b"], "kind": l["kind"], "reason": l["reason"],
                               "support": {"kind": "observed", "source": f"ep{refs.get('@episode')}",
                                           "note": "came up together again"}}, run_id)
                    observed += 1
        return {"episode": refs.get("@episode"), "first": self.first, "last": self.last,
                "nodes": len(made), "new_chains": sorted({r["chain"] for r in made}), "observed": observed,
                "headline": plan.extra.get("headline")}


def bare_episode(mem, first, last, why):
    """When writing keeps failing on a stretch: save an episode with no knowledge, so writing moves on.
    The messages are still in the log, and recall still searches them directly."""
    stretch = mem.messages_between(first, last)
    headline = next((m["text"][:80] for m in stretch if m["role"] == "user"), "(no headline)")
    run_id = mem.save_run(job="write", status="failed", attempts=0, focus=f"#{first}-", problems=[[why]])
    mem.apply({"op": "add_episode", "first": first, "last": last, "headline": headline}, run_id)
    return run_id
