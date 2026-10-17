"""The persona: Avy's model of the relationship, as a graph of its own (schema.sql, "THE PERSONA").

The world's knowledge graph holds what she knows. This one holds how she is with him, in three hubs kept a little
apart, each navigated on its own:

    him    what's lasting about him, his preferences (a cascade: general rules, and specific ones that refine them
           for a kind of conversation), and his patterns
    her    her core (who she is with him, in her own words: one node that evolves), her gestures (small moves that
           land with him), and her voice (replies of hers that landed)
    us     his reactions to the things she does (micro-reactions), the words the two of them coined, and the kinds of
           conversation they have (situations: what behaviors hang from)

The graph grows, in size and in form: new things are added, and what's there evolves by versions, each resting on
the exact messages behind it. What's fixed is what one message pulls from it. Every message lands in the graph from
where it is (what it says, what kind of conversation it is, what world knowledge it called up), walks a step along
the connections, and brings back a fixed share per hub. Some of it is always in view: her core, the strongest
things about him, his standing preferences, each with a fixed allocation. Each node has a fixed size too, and her
core evolves a little at a time: code refuses a version that rewrites too much at once, because drift (a stranger in
every message) is exactly what this is here to stop.

Never calls the model. Changes come through the one door (Memory.apply):
    {"op": "persona", "chain"?, "aspect", "title", "text", "scope", "origin", "certainty", "message",
     "evidence": [(message, start, end)], "retire": bool, "why", "by", "ref"}
    {"op": "persona_link", "a", "b", "kind", "reason", "message"}        (seeing it again strengthens it)
"""

import math
import re

from .common import NAME, clip, stamp
from .embed import embedder

# Each aspect: which hub it belongs to, how many words one node may say, whether it must rest on his own words.
ASPECTS = {
    "core":       {"hub": "her", "words": 150, "said": False, "about": "who Avy is with him, in her own words (one node, evolving)"},
    "gesture":    {"hub": "her", "words": 32,  "said": False, "about": "her small moves that land with him"},
    "voice":      {"hub": "her", "words": 30,  "said": False, "about": "a reply of hers that landed, and why"},
    "him":        {"hub": "him", "words": 28,  "said": True,  "about": "what's lasting about him"},
    "preference": {"hub": "him", "words": 30,  "said": True,  "about": "his rules for how she works with him"},
    "pattern":    {"hub": "him", "words": 32,  "said": False, "about": "how he tends to work, think and talk"},
    "reaction":   {"hub": "us",  "words": 32,  "said": True,  "about": "how he responds to specific things she does"},
    "term":       {"hub": "us",  "words": 32,  "said": False, "about": "words the two of them coined"},
    "situation":  {"hub": "us",  "words": 30,  "said": False, "about": "a kind of conversation they have"},
}
HUBS = {"him": ("him", "preference", "pattern"), "her": ("gesture", "voice"), "us": ("reaction", "term")}
LINK_KINDS = ("applies_in", "supports", "undercuts", "refines", "about", "example_of", "related")
CORE_KEEPS = 0.35        # a new version of her core keeps at least this share of the old one's words: evolve, don't jump

# What one message pulls from the persona: a fixed allocation, however big the graph gets.
ALWAYS = {"him": 10, "preference": 14}     # always in view: the strongest things about him, his standing preferences
DRAW = {"him": 4, "her": 3, "us": 4}       # navigated for this message: lines per hub
TERMS_SHOWN = 2          # coined words brought back for one message, at most (inside the "us" draw)
VOICE_SHOWN = 2          # her replies shown as examples of her voice
LAND = 0.70              # how close in meaning a node must be to the message to be landed on
TERM_CLOSE = 0.78        # coined words need a closer match: they should come back only when they truly fit

# Kinds of conversation, to start with: what they are, not how to behave in them (that's learned), and a few example
# messages each. A message is classified by its closest examples; as the keeper labels his messages, a situation's
# examples become his own words, so it learns how he talks when it's that kind of conversation.
SEED_SITUATIONS = [
    ("technical work", "Code, debugging, building something, how a system works, numbers and specifics.",
     ["the function returns None when the list is empty", "why is this query so slow", "how does a TLB miss get handled",
      "can you fix this bug in my code", "what's the difference between a process and a thread",
      "the build fails with an import error", "how should I structure the database for this"]),
    ("planning", "Schedules, plans, errands, logistics, what's next and when.",
     ["I have the dentist on Tuesday at 3", "what's on my plate this week", "remind me to email the professor on Friday",
      "when should I start packing for the trip", "can we plan out my week", "the meeting moved to Thursday",
      "what do I need to get done before the deadline"]),
    ("ideas", "Thinking through an idea, a concept, an architecture, a what-if; working out how something should be.",
     ["what if memory worked like a library", "should the persona be one graph or several",
      "I've been thinking about how agents should remember things", "is a tree better than a graph for plans",
      "here's an idea for the project", "what breaks if this assumption is wrong", "how should the architecture handle this"]),
    ("casual", "Small talk, jokes, quick check-ins, passing remarks.",
     ["hey", "lol", "ok I'm going to sleep", "morning", "haha that's fair", "what's up", "nice", "ok cool"]),
    ("life", "How he's doing, decisions about his life, people, the harder moments.",
     ["my sister isn't talking to me", "I'm stressed about everything right now", "should I take the co-op offer or stay for research",
      "rough day", "I don't know what I want to do after graduating", "my friend is going through a hard time",
      "I feel like I'm falling behind"]),
]
SEED_EXAMPLES = {title: examples for title, _, examples in SEED_SITUATIONS}
SITUATION_FLOOR = 0.60   # a message is a kind of conversation when its closest examples are at least this close...
SITUATION_MARGIN = 0.02  # ...and closer than any other kind's by this much; otherwise it's no particular kind
LABELED_EXAMPLES = 40    # his own labeled messages kept per situation as examples (the newest)


def content_words(text):
    stop = {"the", "a", "an", "and", "or", "but", "to", "of", "in", "on", "for", "with", "is", "it", "i", "he", "him",
            "his", "my", "me", "that", "this", "be", "as", "at", "by", "when", "not", "so", "if", "are", "was", "you"}
    return {w for w in re.findall(r"[a-z0-9']+", (text or "").lower()) if w not in stop and len(w) > 2}


def cosine(np, a, b):
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-9))


class Persona:

    # --- reading ---------------------------------------------------------------------------------------

    def persona_node(self, chain):
        """The newest version of a persona node (active or retired), with its evidence, or None."""
        n = self.row("SELECT * FROM persona WHERE chain = ? ORDER BY version DESC LIMIT 1", chain)
        if n:
            n["evidence"] = self.persona_evidence(n["chain"])
        return n

    def persona_evidence(self, chain):
        """Every quote any version of the node rests on, oldest first: a node's evidence accumulates."""
        return self.rows("""SELECT e.message, e.start, e.end, MIN(e.quote) AS quote, m.role, m.at FROM persona_evidence e
                            JOIN persona p ON p.id = e.node JOIN messages m ON m.id = e.message
                            WHERE p.chain = ? GROUP BY e.message, e.start, e.end ORDER BY e.message""", chain)

    def persona_nodes(self, aspect=None, state="active"):
        """The newest version of every node (of one aspect), strongest first."""
        sql = ("SELECT * FROM persona p WHERE NOT EXISTS (SELECT 1 FROM persona x WHERE x.replaces = p.id)"
               + (" AND state = ?" if state else "") + (" AND aspect = ?" if aspect else ""))
        found = self.rows(sql, *[v for v in (state, aspect) if v])
        strengths = self._persona_strengths()
        for n in found:
            n["strength"] = strengths.get(n["chain"], 0) + (2 if n["origin"] == "user" else 0)
        return sorted(found, key=lambda n: (-n["strength"], -n["chain"]))

    def _persona_strengths(self):
        """How much each node rests on: each distinct message behind it counts once (his own words twice), each time a
        connection from it was seen again counts once, and each reaction that undercuts it takes two away. Computed,
        never picked; nothing the model says about a node adds to it."""
        out = {}
        for r in self.rows("""SELECT p.chain, e.message, m.role FROM persona_evidence e JOIN persona p ON p.id = e.node
                              JOIN messages m ON m.id = e.message GROUP BY p.chain, e.message"""):
            out[r["chain"]] = out.get(r["chain"], 0) + (2 if r["role"] == "user" else 1)
        for r in self.rows("""SELECT e.a, e.b, e.kind, COUNT(s.id) AS n FROM persona_edges e LEFT JOIN persona_seen s
                              ON s.edge = e.id GROUP BY e.id"""):
            if r["kind"] in ("supports", "example_of"):
                out[r["a"]] = out.get(r["a"], 0) + r["n"]
                if r["kind"] == "supports":
                    out[r["b"]] = out.get(r["b"], 0) + 1 + r["n"]
            if r["kind"] == "undercuts":
                out[r["b"]] = out.get(r["b"], 0) - 2 * (1 + r["n"])
        return out

    def persona_versions(self, chain):
        return self.rows("SELECT * FROM persona WHERE chain = ? ORDER BY version", chain)

    def persona_links(self, chain=None):
        found = self.rows("SELECT e.*, (SELECT COUNT(*) FROM persona_seen s WHERE s.edge = e.id) AS again FROM persona_edges e"
                          + (" WHERE a = ? OR b = ?" if chain else "") + " ORDER BY id", *([chain, chain] if chain else []))
        for e in found:
            e["seen"] = 1 + e.pop("again")
        return found

    def situation_named(self, title):
        t = " ".join(str(title or "").lower().split())
        return next((s for s in self.persona_nodes("situation") if s["title"].lower() == t), None)

    # --- the one door ----------------------------------------------------------------------------------

    def seed_persona(self):
        """Kinds of conversation to start with, so behaviors have somewhere to hang from day one."""
        if self.value("SELECT COUNT(*) FROM persona WHERE aspect = 'situation'"):
            return
        for title, text, _ in SEED_SITUATIONS:
            self.apply({"op": "persona", "aspect": "situation", "title": title, "text": text, "origin": "seed",
                        "by": "seed", "why": "a kind of conversation to start with"})

    def _op_persona(self, op, run):
        aspect, chain, head = op.get("aspect"), op.get("chain"), None
        by_him = op.get("by") == "him"                      # he edited it on the page: his edit is the evidence
        if chain is not None:
            try:
                chain = int(str(chain).lower().lstrip("pa"))
            except ValueError:
                return self._journal(run, op, None, f"{op.get('chain')!r} isn't a persona node (they look like pa12)")
            head = self.persona_node(chain)
            if not head:
                return self._journal(run, op, f"pa{chain}", f"there's no persona node pa{chain}")
            aspect = aspect or head["aspect"]
            if aspect != head["aspect"]:
                return self._journal(run, op, f"pa{chain}", f"pa{chain} is a {head['aspect']}, not a {aspect}")
        target = f"pa{chain}" if chain else op.get("ref")
        if aspect not in ASPECTS:
            return self._journal(run, op, target, f"aspect must be one of {', '.join(ASPECTS)}")
        spec = ASPECTS[aspect]
        if aspect == "core" and not head:
            existing = self.persona_nodes("core")
            if existing:                                  # there's one core: a "new" one is its next version
                head, chain = self.persona_node(existing[0]["chain"]), existing[0]["chain"]
                target = f"pa{chain}"
        if op.get("retire"):
            if not head:
                return self._journal(run, op, target, "only an existing node can be retired")
            if aspect == "core":
                return self._journal(run, op, target, "her core can be revised, never retired")
            return self._persona_version(run, op, head, {**head, "state": "retired"}, [])
        title = " ".join(str(op.get("title") or (head or {}).get("title") or "").split())[:80]
        text = " ".join(str(op.get("text") or (head or {}).get("text") or "").split())
        if not title or not text:
            return self._journal(run, op, target, "a persona node needs a title and a text")
        n = len(re.findall(r"\S+", text))
        if n > spec["words"]:
            return self._journal(run, op, target, f"a {aspect} says at most {spec['words']} words (this one has {n}): say it shorter")
        origin = "user" if by_him else (op.get("origin") or (head or {}).get("origin") or "avy")
        if origin not in ("user", "avy", "inferred", "seed") or (origin == "seed" and op.get("by") != "seed"):
            return self._journal(run, op, target, "origin must be user (his words), avy (her judgment) or inferred")
        certainty = op.get("certainty") if origin == "inferred" else None
        if origin == "inferred" and certainty not in ("likely", "possible"):
            return self._journal(run, op, target, "an inferred node needs a certainty: likely or possible")
        evidence, problem = self._persona_quotes(op.get("evidence") or [])
        if problem:
            return self._journal(run, op, target, problem)
        roles = {e["role"] for e in evidence} | {e["role"] for e in (head or {}).get("evidence", [])}
        if not by_him and origin != "seed":
            if not evidence and not (head and head.get("evidence")):
                return self._journal(run, op, target, f"\"{clip(text, 0, 50)}\" rests on no message: every node needs its evidence")
            if (spec["said"] or origin == "user") and "user" not in roles:
                return self._journal(run, op, target, f"a {aspect} must rest on something {NAME} said: quote his words")
        message = op.get("message") or (head or {}).get("message")
        if aspect == "voice":
            m = self.row("SELECT role FROM messages WHERE id = ?", message) if message else None
            if not m or m["role"] != "assistant":
                return self._journal(run, op, target, "a voice node points at one of her replies (message)")
        if aspect == "term" and not message:
            message = min(e["message"] for e in evidence) if evidence else (head or {}).get("message")
        scope = " ".join(str(op.get("scope") or (head or {}).get("scope") or "").split()) or None
        situation = None
        if scope and scope.lower() != "always" and aspect not in ("situation", "core", "him", "term"):
            situation = self.situation_named(scope)
            if not situation:
                names = ", ".join(s["title"] for s in self.persona_nodes("situation"))
                return self._journal(run, op, target, f"scope must be 'always' or one of the situations ({names}), not {scope!r}")
        if aspect == "core" and head and head["state"] == "active" and not by_him:
            before, after = content_words(head["text"]), content_words(text)
            kept = len(before & after) / max(1, len(before))
            if kept < CORE_KEEPS:
                return self._journal(run, op, target, f"this rewrites her core too much at once (keeps {kept:.0%} of it; at least "
                                                      f"{CORE_KEEPS:.0%}): change a few things per version, so she evolves instead of jumping")
        if not head:                                      # the same title again is the same node: a new version of it
            same = next((x for x in self.persona_nodes(aspect) if x["title"].lower() == title.lower()), None)
            if same:
                head, chain = self.persona_node(same["chain"]), same["chain"]
        fields = {"state": "active", "aspect": aspect, "title": title, "text": text, "scope": scope, "origin": origin,
                  "certainty": certainty, "message": message}
        known = {(e["message"], e["start"]) for e in (head or {}).get("evidence", [])}
        if head and all(head.get(k) == v for k, v in fields.items()) and all((e["message"], e["start"]) in known for e in evidence):
            return {**self._journal(run, dict(op, unchanged=True), f"pa{head['chain']}", None), "chain": head["chain"], "unchanged": True}
        result = self._persona_version(run, op, head, fields, evidence)
        if result["applied"] and situation:
            self._persona_link(run, result["chain"], situation["chain"], "applies_in", f"applies when it's {situation['title']}")
        return result

    def _persona_quotes(self, spans):
        """[(message, start, end)] -> evidence rows with the quote copied by code, or a problem."""
        out = []
        for span in spans:
            try:
                mid, start, end = (int(x) for x in span)
            except (TypeError, ValueError):
                return None, f"{span!r} isn't (message, start, end)"
            m = self.row("SELECT id, role, text, at FROM messages WHERE id = ?", mid)
            if not m or not (0 <= start < end <= len(m["text"])):
                return None, f"there's no such span in #{mid}"
            out.append({"message": mid, "start": start, "end": end, "quote": m["text"][start:end], "role": m["role"], "at": m["at"]})
        return out, None

    def _persona_version(self, run, op, head, fields, evidence):
        with self.tx() as db:
            row = db.execute("SELECT COALESCE(MAX(id), 0) + 1 FROM persona").fetchone()[0]
            chain = head["chain"] if head else row
            version = (head or {}).get("version", 0) + 1
            db.execute("""INSERT INTO persona (id, chain, version, replaces, state, aspect, title, text, scope, origin, certainty,
                          message, why, by, run, at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                       (row, chain, version, (head or {}).get("id"), fields["state"], fields["aspect"], fields["title"],
                        fields["text"], fields["scope"], fields["origin"], fields["certainty"], fields["message"],
                        (op.get("why") or "")[:300], op.get("by") or "mind", run, stamp()))
            for e in evidence:
                db.execute("INSERT OR IGNORE INTO persona_evidence (node, message, start, end, quote) VALUES (?, ?, ?, ?, ?)",
                           (row, e["message"], e["start"], e["end"], e["quote"]))
            result = self._journal(run, {**op, "evidence": [[e["message"], e["start"], e["end"]] for e in evidence]},
                                   f"pa{chain}", None, db)
        return {**result, "chain": chain, "id": row, "version": version,
                "changed": "added" if not head else ("retired" if fields["state"] == "retired" else "revised")}

    def _op_persona_link(self, op, run):
        kind = op.get("kind")
        if kind not in LINK_KINDS:
            return self._journal(run, op, None, f"kind must be one of {', '.join(LINK_KINDS)}")
        try:
            a = int(str(op.get("a")).lower().lstrip("pa"))
            b = int(str(op.get("b")).lower().lstrip("pak") if kind == "about" else str(op.get("b")).lower().lstrip("pa"))
        except ValueError:
            return self._journal(run, op, None, "a and b must be persona nodes (pa12); for 'about', b is a knowledge node (k12)")
        if not self.persona_node(a):
            return self._journal(run, op, None, f"there's no persona node pa{a}")
        if kind == "about":
            if not self.current(b):
                return self._journal(run, op, None, f"there's no knowledge node k{b}")
        elif not self.persona_node(b) or a == b:
            return self._journal(run, op, None, f"there's no persona node pa{b} to connect to")
        if kind == "refines" and self._refines_path(b, a):
            return self._journal(run, op, None, f"pa{b} already refines pa{a}: a cascade can't loop")
        reason = " ".join(str(op.get("reason") or "").split())[:240]
        if not reason:
            return self._journal(run, op, None, "a connection needs a reason")
        return self._persona_link(run, a, b, kind, reason, op.get("message"), op)

    def _refines_path(self, start, goal):
        """Does start already refine goal, directly or through a chain of refinements? (A loop would make 'the most
        specific rule wins' meaningless, the way circular evidence is circular reasoning.)"""
        seen, todo = set(), [start]
        while todo:
            x = todo.pop()
            if x == goal:
                return True
            if x in seen:
                continue
            seen.add(x)
            todo += [r["b"] for r in self.rows("SELECT b FROM persona_edges WHERE a = ? AND kind = 'refines'", x)]
        return False

    def _persona_link(self, run, a, b, kind, reason, message=None, op=None):
        """Connect two nodes, or, if they're already connected that way, count it as seen again (stronger)."""
        op = op or {"op": "persona_link", "a": a, "b": b, "kind": kind, "reason": reason}
        with self.tx() as db:
            found = db.execute("SELECT id FROM persona_edges WHERE a = ? AND b = ? AND kind = ?", (a, b, kind)).fetchone()
            if found:
                db.execute("INSERT INTO persona_seen (edge, message, note, run, at) VALUES (?, ?, ?, ?, ?)",
                           (found[0], message, reason, run, stamp()))
                edge = found[0]
            else:
                edge = db.execute("INSERT INTO persona_edges (a, b, kind, reason, run, at) VALUES (?, ?, ?, ?, ?, ?)",
                                  (a, b, kind, reason, run, stamp())).lastrowid
            result = self._journal(run, op, f"pe{edge}", None, db)
        return {**result, "edge": edge, "again": bool(found)}

    # --- what one message pulls from it ------------------------------------------------------------------

    def persona_always(self):
        """What's always in view (it goes in her instructions, which are cached), each part a fixed allocation: her core,
        the strongest things about him, and his standing preferences. The rest of the graph is reached by navigating."""
        parts = []
        core = self.persona_nodes("core")
        if core:
            parts.append("Who you are with him, in your own words (this evolves as you learn him):\n" + core[0]["text"])
        him = self.persona_nodes("him")[:ALWAYS["him"]]
        if him:
            parts.append(f"What's lasting about {NAME}:\n" + "\n".join(f"- {n['text']}" for n in him))
        prefs = [n for n in self.persona_nodes("preference") if not n["scope"] or n["scope"].lower() == "always"][:ALWAYS["preference"]]
        if prefs:
            parts.append("His standing preferences: his rules for you, in force every time, even when nothing in the "
                         "message reminds you of them. Where one is more specific than your defaults, it wins:\n"
                         + "\n".join(f"- {n['text']}" for n in prefs))
        return "\n\n".join(parts)

    def always_chains(self):
        """The chains persona_always() shows, so navigation doesn't pull them twice."""
        core = self.persona_nodes("core")[:1]
        him = self.persona_nodes("him")[:ALWAYS["him"]]
        prefs = [n for n in self.persona_nodes("preference") if not n["scope"] or n["scope"].lower() == "always"][:ALWAYS["preference"]]
        return {n["chain"] for n in core + him + prefs}

    def _vectors(self, nodes):
        """Meaning vectors for persona nodes (title and text), cached by version: the graph can be big, so each version
        is embedded once."""
        cache = self.__dict__.setdefault("_persona_vecs", {})
        todo = [n for n in nodes if n["id"] not in cache]
        if todo:
            for n, v in zip(todo, embedder.passages([f"{n['title']}: {n['text']}" for n in todo])):
                cache[n["id"]] = v
        return [cache[n["id"]] for n in nodes]

    def situation_for(self, text, previous=""):
        """The kind of conversation this message is (a situation node), or None when it's no particular kind. Each
        situation is known by its examples: the seed sentences it started with, then his own messages the keeper
        labeled as that kind (the newest LABELED_EXAMPLES). A situation's score is the mean of its two closest examples;
        the best counts if it's close enough and clearly ahead of the next."""
        situations = self.persona_nodes("situation")
        if not situations or not (text or "").strip():
            return None
        probe = f"{previous[-200:]}\n{text}" if previous and len(text.split()) <= 3 and text.strip().lower() not in ("hey", "hi", "lol") else text
        if not embedder.ready:
            words = content_words(probe)
            scored = sorted(((len(words & content_words(s["title"] + " " + s["text"])), s) for s in situations), key=lambda x: -x[0])
            return scored[0][1] if scored[0][0] >= 1 else None
        np, q = embedder.np, embedder.query(probe)
        cache = self.__dict__.setdefault("_example_vecs", {})
        scored = []
        for s in situations:
            examples = [("seed", x) for x in SEED_EXAMPLES.get(s["title"], [])]
            examples += [(f"m{r['message']}", r["text"]) for r in self.rows(
                """SELECT l.message, m.text FROM persona_labels l JOIN messages m ON m.id = l.message
                   WHERE l.situation = ? ORDER BY l.message DESC LIMIT ?""", s["chain"], LABELED_EXAMPLES)]
            examples = examples or [("about", f"{s['title']}: {s['text']}")]
            sims = []
            for key, example in examples:
                k = (key, example[:200])
                if k not in cache:
                    cache[k] = embedder.query(example[:600])
                sims.append(cosine(np, q, cache[k]))
            sims.sort()
            scored.append((float(np.mean(sims[-2:])), s))
        scored.sort(key=lambda x: -x[0])
        best, second = scored[0][0], (scored[1][0] if len(scored) > 1 else 0)
        return scored[0][1] if best >= SITUATION_FLOOR and best - second >= SITUATION_MARGIN else None

    def label_situation(self, message, situation, run=None, by="keeper"):
        """Record which kind of conversation one of his messages was (it becomes an example of that kind)."""
        s = situation if isinstance(situation, dict) else self.situation_named(situation)
        if not s:
            return None
        with self.tx() as db:
            db.execute("INSERT INTO persona_labels (message, situation, by, run, at) VALUES (?, ?, ?, ?, ?)",
                       (message, s["chain"], by, run, stamp()))
        return s["chain"]

    def navigate_persona(self, text, previous="", knowledge=()):
        """What this message pulls from the persona graph: a fixed share per hub, however big the graph is.

            1. Situation: which kind of conversation this is.
            2. Land: every node scored by how close it is in meaning to the message, plus a lift for nodes that hang from
               this situation, for coined words about the world knowledge this message called up (knowledge chains),
               and a little for strength (what rests on more counts for a bit more).
            3. Walk: one step along connections from what landed: a specific rule brings the general one it refines
               (so the cascade is read whole), a reaction brings the gesture it supports.
            4. Keep: the best of each hub, within its draw (DRAW), coined words only above their own bar.
        Deterministic: the same graph and message give the same result. Returns
        {situation, picked: {hub: [nodes]}, terms, voice, scores}."""
        situation = self.situation_for(text, previous)
        here = situation["chain"] if situation else None
        links = self.persona_links()
        tied = {e["a"] for e in links if e["kind"] == "applies_in" and e["b"] == here} if here else set()
        about = {}
        for e in links:
            if e["kind"] == "about":
                about.setdefault(e["a"], set()).add(e["b"])
        shown = self.always_chains()
        nodes = [n for n in self.persona_nodes() if n["aspect"] in ("him", "preference", "pattern", "reaction", "gesture", "term")
                 and n["chain"] not in shown]
        scores = {}
        if nodes and (text or "").strip():
            if embedder.ready:
                np, q = embedder.np, embedder.query(f"{previous[-200:]}\n{text}" if previous and len(text) < 60 else text)
                close = [cosine(np, q, v) for v in self._vectors(nodes)]
            else:
                words = content_words(text)
                close = [0.66 + 0.06 * len(words & content_words(n["title"] + " " + n["text"])) for n in nodes]
            for n, c in zip(nodes, close):
                score = c + (0.08 if n["chain"] in tied else 0) + (0.08 if about.get(n["chain"], set()) & set(knowledge or ()) else 0)
                score += 0.01 * math.log1p(max(0, n["strength"]))
                if n["aspect"] == "preference" and n["chain"] in tied:
                    score = max(score, 1.0)               # a rule for exactly this kind of conversation always comes
                scores[n["chain"]] = score
        by_chain = {n["chain"]: n for n in nodes}
        for e in links:                                   # one step out: the cascade, and what reactions support
            if e["kind"] == "refines" and scores.get(e["a"], 0) >= LAND and e["b"] in by_chain:
                scores[e["b"]] = max(scores.get(e["b"], 0), scores[e["a"]] - 0.02)
            if e["kind"] in ("supports", "undercuts") and scores.get(e["a"], 0) >= LAND and e["b"] in by_chain:
                scores[e["b"]] = max(scores.get(e["b"], 0), scores[e["a"]] - 0.04)
        picked = {hub: [] for hub in HUBS}
        terms = []
        for chain in sorted(scores, key=lambda c: -scores[c]):
            n = by_chain[chain]
            hub = ASPECTS[n["aspect"]]["hub"]
            if n["aspect"] == "term":
                if scores[chain] >= TERM_CLOSE and len(terms) < TERMS_SHOWN:
                    terms.append(n)
                continue
            if scores[chain] >= LAND and len(picked[hub]) < DRAW[hub] - (len(terms) if hub == "us" else 0):
                picked[hub].append(n)
        refines = {e["a"]: e["b"] for e in links if e["kind"] == "refines"}
        for hub in picked:
            for n in picked[hub]:
                general = refines.get(n["chain"])
                n["overrides"] = (self.persona_node(general) or {}).get("title") if general else None
        voice = self.voice_for(text, here)
        return {"situation": situation, "picked": picked, "terms": terms, "voice": voice,
                "scores": {f"pa{c}": round(s, 3) for c, s in scores.items()}}

    def persona_moment(self, text, previous="", knowledge=()):
        """navigate_persona() as text for the desk, plus what was shown (for the record)."""
        found = self.navigate_persona(text, previous, knowledge)
        parts = []
        if found["situation"]:
            s = found["situation"]
            parts.append(f"This looks like {s['title']} ({s['text'].rstrip('.').lower()}).")
        label = {"preference": "his rule here", "him": "about him", "pattern": "his pattern", "reaction": "how he reacts",
                 "gesture": "what works"}
        lines = []
        for hub in ("him", "us", "her"):
            for n in found["picked"][hub]:
                line = f"- ({label[n['aspect']]}) {n['text']}"
                if n.get("overrides"):
                    line += f" (here this overrides \"{n['overrides']}\")"
                if n["origin"] == "inferred":
                    line += " (your impression)"
                lines.append(line)
        if lines:
            parts.append("What this moment brings up from what you've learned about being with him:\n" + "\n".join(lines))
        if found["terms"]:
            out = []
            for t in found["terms"]:
                ev = self.persona_evidence(t["chain"])
                born = next((e for e in ev if e["message"] == t["message"]), ev[0] if ev else None)
                out.append(f"- \"{t['title']}\": {t['text']}" + (f" (born #{born['message']}, {born['at'][:10]}: \"{clip(born['quote'], 0, 150)}\")" if born else ""))
            parts.append("Words of your own that this brings back, with the moment each was born. Use one only if it's the "
                         "natural word here, the way he'd use it:\n" + "\n".join(out))
        if found["voice"]:
            parts.append(("One of your own replies to him" if len(found["voice"]) == 1 else "Some of your own replies to him")
                         + " that landed, for your manner only (never repeat their content):\n" + "\n".join(
                f"- he'd said: \"{clip(v['asked'], 0, 160)}\"\n  you said: \"{clip(v['reply'], 0, 480)}\"" for v in found["voice"]))
        return {"situation": found["situation"]["title"] if found["situation"] else None,
                "lines": [f"pa{n['chain']}" for hub in found["picked"].values() for n in hub],
                "terms": [f"pa{t['chain']}" for t in found["terms"]], "voice": [v["message"] for v in found["voice"]],
                "note": "\n\n".join(parts)}

    def voice_for(self, text, situation=None, k=VOICE_SHOWN):
        """Her replies kept as examples of her voice: the ones for this kind of conversation first, then the closest."""
        nodes = self.persona_nodes("voice")
        if not nodes:
            return []
        tied = {e["a"] for e in self.persona_links() if e["kind"] == "example_of" and e["b"] == situation} if situation else set()
        picked = []
        for n in nodes:
            reply = self.row("SELECT text FROM messages WHERE id = ?", n["message"])
            asked = self.row("SELECT text FROM messages WHERE id < ? AND role = 'user' ORDER BY id DESC LIMIT 1", n["message"])
            if reply:
                picked.append({"chain": n["chain"], "message": n["message"], "reply": reply["text"],
                               "asked": asked["text"] if asked else "", "tied": n["chain"] in tied, "score": 0.0})
        if embedder.ready and text and len(picked) > k:
            np, q = embedder.np, embedder.query(text)
            for p, v in zip(picked, embedder.passages([p["asked"] or p["reply"] for p in picked])):
                p["score"] = cosine(np, q, v)
        picked.sort(key=lambda p: (not p["tied"], -p["score"]))
        return picked[:k]

    def persona_listing(self, aspects=None, focus="", per_aspect=24, quotes=True):
        """The persona for the mind's jobs, by aspect: every node with its handle, strength and evidence. A big graph is
        shown by what's closest to `focus` (the exchange being looked at) and what's strongest, per_aspect of each."""
        out = []
        vecs = None
        if focus and embedder.ready:
            np, q = embedder.np, embedder.query(focus[-2000:])
        for aspect in aspects or ASPECTS:
            nodes = self.persona_nodes(aspect)
            if len(nodes) > per_aspect and focus and embedder.ready:
                close = sorted(zip([cosine(np, q, v) for v in self._vectors(nodes)], range(len(nodes))), reverse=True)
                keep = {i for _, i in close[:per_aspect // 2]} | set(range(per_aspect // 2))
                nodes = [n for i, n in enumerate(nodes) if i in keep]
            hidden = max(0, len(self.persona_nodes(aspect)) - per_aspect) if len(nodes) >= per_aspect else 0
            nodes = nodes[:per_aspect]
            out.append(f"{aspect.upper()} ({ASPECTS[aspect]['about']}; at most {ASPECTS[aspect]['words']} words each"
                       + (f"; {hidden} more not shown" if hidden else "") + "):")
            if not nodes:
                out.append("  (none yet)")
            for n in nodes:
                line = f"  pa{n['chain']} \"{n['title']}\": {n['text']}"
                if n["scope"]:
                    line += f" [scope: {n['scope']}]"
                line += f" [{n['origin']}{', ' + n['certainty'] if n['certainty'] else ''}; strength {n['strength']}]"
                if n["message"]:
                    line += f" [#{n['message']}]"
                if quotes and aspect != "situation":
                    ev = self.persona_evidence(n["chain"])[-3:]
                    if ev:
                        line += " evidence: " + "; ".join(f"#{e['message']} \"{clip(e['quote'], 0, 80)}\"" for e in ev)
                out.append(line)
        return "\n".join(out)

    def persona_data(self):
        """The persona graph for the page: nodes (with evidence and versions), connections, and the hubs."""
        nodes = self.persona_nodes(state=None)
        for n in nodes:
            n["evidence"] = self.persona_evidence(n["chain"])
            n["versions"] = self.value("SELECT COUNT(*) FROM persona WHERE chain = ?", n["chain"])
            n["hub"] = ASPECTS[n["aspect"]]["hub"]
        return {"nodes": nodes, "links": self.persona_links(), "hubs": {h: list(a) for h, a in HUBS.items()},
                "aspects": {a: {"hub": s["hub"], "words": s["words"], "about": s["about"],
                                "active": sum(1 for n in nodes if n["aspect"] == a and n["state"] == "active")}
                            for a, s in ASPECTS.items()}}
