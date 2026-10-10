"""Recall: what memory brings to each message, by rules (no model involved).

    1. Search every version of every node, and episode headlines, by meaning and/or shared words.
       A hit on an old version counts for the node (asking about "March 3" still finds Rohan's
       birthday after it moved to May 3).
    2. Walk the network outward from the best matches: along live edges, strongest first, and along
       the links nobody had to write (an inference and what it rests on; things said in the same
       message or the same stretch). Each step carries less relevance; stepping out of a big hub
       carries less still, so one hub can't drag everything in.
    3. Keep the strongest, within the /recall: budget.
    4. Safety net: older messages that match by themselves, in case knowledge missed something.
    5. Brief: what was said, what Avy said, and what Avy inferred go in separate sections, from most to
       least reliable, followed by how the things found connect to each other.

When Avy searches for herself (/explore: on, mind/explore.py) she uses the same pieces: search to
land, links to move, node_block to read, and brief() to lay out what she kept.
"""

import math
import time

from .common import age_days, clip, now, refers_back, tokens, when, who
from .embed import embedder
from .search import top_score

# /recall: how far memory search reaches on each message.
#   seeds        nodes found by search that the walk starts from
#   hops         how many steps out the walk goes
#   fanout       at most this many steps taken out of any one node
#   found        how close (0 to 1) something must be to count as found (words_found: with meaning search off)
#   near         ...and how close to the best match (a strong match makes weak ones noise)
#   keep         nodes reached by walking are kept down to this fraction of the best match
#   log          older messages recalled directly, as a safety net
#   tokens       how much memory one message can bring in
#   rounds       when Avy searches for herself: how many rounds of looking she gets
DEPTHS = {
    "off":    None,
    "light":  {"seeds": 4,  "hops": 1, "fanout": 4,  "found": 0.60, "words_found": 0.40, "near": 0.10, "keep": 0.45, "log": 2,  "tokens": 2_500,  "rounds": 1},
    "normal": {"seeds": 8,  "hops": 2, "fanout": 6,  "found": 0.58, "words_found": 0.30, "near": 0.15, "keep": 0.30, "log": 4,  "tokens": 7_000,  "rounds": 2},
    "deep":   {"seeds": 12, "hops": 3, "fanout": 8,  "found": 0.56, "words_found": 0.25, "near": 0.20, "keep": 0.20, "log": 8,  "tokens": 16_000, "rounds": 3},
    "max":    {"seeds": 24, "hops": 4, "fanout": 12, "found": 0.54, "words_found": 0.20, "near": 0.30, "keep": 0.10, "log": 12, "tokens": 40_000, "rounds": 4},
}

# How strongly one step carries relevance, by kind of connection and direction.
# "out" follows a part_of / builds_on edge as written (a birthday -> Rohan); "in" goes backwards (Rohan -> his birthday).
STEP = {
    ("part_of", "out"): 0.75, ("part_of", "in"): 0.6,
    ("builds_on", "out"): 0.8, ("builds_on", "in"): 0.6,
    ("like", ""): 0.7, ("against", ""): 0.7, ("related", ""): 0.5,
    ("rests on", ""): 0.7,        # from an inference to what it rests on
    ("supports", ""): 0.75,       # from something said to what Avy inferred from it
    ("same message", ""): 0.35, ("same episode", ""): 0.25,
}

TIERS = [   # how the memory note is laid out, most reliable first
    ("user", "What Shreyas told you (his exact words are quoted; #41 is message 41):"),
    ("avy", "What you said to him before (your own suggestions and ideas: not facts about him unless he agreed):"),
    ("inferred", "What you worked out yourself (inferred, never said by anyone; how sure you are, and what it rests on):"),
]


def hub_discount(degree):
    """Stepping out of a node with many connections says less about each one (like a Wikipedia link
    to "United States"). 1.0 up to 2 connections, about 0.5 at 12, about 0.4 at 30."""
    return 1.0 if degree <= 2 else math.log2(4) / math.log2(2 + degree)


def briefing(sections, note=None):
    """The memory note DeepSeek gets right before your newest message.
    sections: [(heading, [blocks])]; empty ones are left out."""
    parts = [f"Memory for this message. It is now {now():%A, %B %d, %Y, %I:%M %p %Z}."]
    parts += [f"{heading}\n" + "\n".join(blocks) for heading, blocks in sections if blocks]
    if len(parts) == 1:
        parts.append(note or "Nothing older in memory matched this message.")
    return "\n\n".join(parts)


class Recall:

    def recall(self, text, previous="", shown_from=None, depth="normal", words=True, meaning=True):
        """What this memory knows that's relevant to the message.
          previous    your message before this one, used only when this one refers back to it
          shown_from  the first message already in front of DeepSeek word for word (not recalled again)
          depth       off, light, normal, deep, max (see DEPTHS)
          words       use shared words to search (/words:)
          meaning     use meaning to search (/meaning:)
        Returns a trace: what was found and how, the blocks for the note, and the note itself."""
        started = time.time()
        level = DEPTHS.get(depth) if depth != "off" else None
        use_meaning = bool(meaning and embedder.ready)
        shown_from = shown_from or self.last_id() + 1
        trace = self.empty_trace(text, depth, words, meaning)
        if level is None or not (words or use_meaning):
            trace["briefing"] = briefing([], "Memory recall is off for this message." if level is None else
                                         "Memory search is switched off (no words, no meaning), so nothing was looked up.")
            return trace

        q = embedder.query(text) if use_meaning else None
        queries = [(text, 1.0, q)]
        if previous and refers_back(text):
            context = f"{previous[-300:]}\n{text}"
            queries.append((context, 0.85, embedder.query(context) if use_meaning else None))

        # 1. Land: search nodes (every version) and episode headlines.
        found = self.land(queries, words, use_meaning)
        best = top_score(found.values())
        floor = level["found"] if use_meaning else level["words_found"]
        bar = max(floor, best - level["near"])
        seeds = sorted((c for c in found if found[c]["score"] >= bar), key=lambda c: -found[c]["score"])[:level["seeds"]]

        # 2. Walk outward.
        reached = {c: {**found[c], "hop": 0} for c in seeds}
        frontier = list(seeds)
        for hop in range(1, level["hops"] + 1):
            steps = []
            for c in frontier:
                for step in self.steps_from(c, q):
                    steps.append((reached[c]["score"] * step["weight"], step, c))
            frontier, taken = [], {}
            for score, step, via in sorted(steps, key=lambda s: -s[0]):
                other = step["other"]
                taken[via] = taken.get(via, 0) + 1
                if taken[via] > level["fanout"] or other in seeds or score <= reached.get(other, {}).get("score", 0):
                    continue
                reached[other] = {"score": score, "how": "link", "via": via, "kind": step["kind"],
                                  "direction": step["direction"], "edge": step["edge"], "hop": hop}
                frontier.append(other)

        # 3. Keep the strongest within the budget.
        ranked = [c for c in sorted(reached, key=lambda c: -reached[c]["score"]) if reached[c]["score"] >= level["keep"] * best]
        picked, used, skipped, cited = [], 0, 0, set()
        for i, c in enumerate(ranked):
            block, msgs = self.node_block(c, full=i < 3, shown_from=shown_from)
            if used + tokens(block) > level["tokens"]:
                skipped += 1
                continue
            used += tokens(block)
            cited |= msgs
            picked.append(self.trace_item(c, reached[c], block, msgs))

        # 4. The safety net: older messages that match by themselves.
        log_lines, used, skipped2, log_hits = self.log_net(queries, picked, shown_from, level, words, use_meaning, floor, used)

        trace.update({
            "nodes": picked, "log": log_lines, "skipped": skipped + skipped2, "tokens": used,
            "searched": {"nodes": len(found), "log": log_hits}, "walked": len(reached) - len(seeds),
            "best": round(best, 3), "bar": round(bar, 3), "seconds": round(time.time() - started, 3),
        })
        self.finish_trace(trace, cited)
        return trace

    # --- the pieces (explore.py uses them too) -------------------------------------------------

    def empty_trace(self, text, depth, words, meaning):
        return {"query": text, "depth": depth, "memory": self.name, "letter": self.letter, "words": bool(words),
                "meaning": bool(meaning), "meaning_model": embedder.status, "explore": None,
                "nodes": [], "log": [], "connections": [], "edges_used": [], "skipped": 0, "tokens": 0,
                "searched": {"nodes": 0, "log": 0}, "walked": 0, "best": 0, "bar": 0, "seconds": 0, "messages": []}

    def land(self, queries, words=True, meaning=True, k=40):
        """Search nodes (every version) and episode headlines. Returns {chain: hit}."""
        found = {}
        for item, hit in self.relevance(queries, "v", k, words, meaning).items():
            n = self.node(int(item[1:]))
            h = self.current(n["chain"]) if n else None
            if h and hit["score"] > found.get(h["chain"], {}).get("score", -1):
                found[h["chain"]] = {**hit, "matched": n["version"] if n["id"] != h["id"] else None}
        for item, hit in self.relevance(queries, "e", 12, words, meaning).items():
            for n in self.rows("SELECT chain FROM current WHERE episode = ?", int(item[1:])):
                score = hit["score"] * 0.9
                if score > found.get(n["chain"], {}).get("score", -1):
                    found[n["chain"]] = {**hit, "score": score, "how": "episode", "episode": int(item[1:])}
        for c, hit in found.items():      # a nudge for recent things: up to 5% for today, fading over a month
            hit["score"] *= 1 + 0.05 * math.exp(-age_days(self.current(c)["at"]) / 30)
        return found

    def steps_from(self, chain, q=None):
        """Every step out of a node, with how much relevance it carries: [{other, weight, kind, direction, edge}]."""
        links = self.links(chain)
        discount = hub_discount(len(links))
        steps = []
        for l in links:
            w = STEP[(l["kind"], l["direction"])] * (0.6 + 0.4 * min(1.0, l["strength"] / 3)) * discount
            steps.append({"other": l["other"], "weight": w, "kind": l["kind"], "direction": l["direction"],
                          "edge": l["edge"], "reason": l["reason"], "strength": l["strength"]})
        for other, how in self.implicit(chain):
            steps.append({"other": other, "weight": STEP[(how, "")] * discount, "kind": how, "direction": "", "edge": None})
        if q is not None:
            for s in steps:
                s["weight"] *= 0.5 + 0.5 * self.closeness(f"v{self.current(s['other'])['id']}", q)
        else:
            for s in steps:
                s["weight"] *= 0.8
        return steps

    def trace_item(self, chain, hit, block, msgs):
        n = self.current(chain)
        return {"node": chain, "handle": self.handle(chain), "memory": self.name, "title": n["title"], "shape": n["shape"],
                "label": n["label"], "origin": n["origin"], "certainty": n["certainty"], "version": n["version"],
                "score": round(hit["score"], 3), "how": hit["how"], "matched": hit.get("matched"), "via": hit.get("via"),
                "kind": hit.get("kind"), "direction": hit.get("direction"), "edge": hit.get("edge"),
                "messages": sorted(msgs), "block": block}

    def log_net(self, queries, picked, shown_from, level, words, meaning, floor, used):
        """Older messages that match by themselves, skipping what's on screen or next to what a node cites."""
        covered = set()
        for x in picked:
            for v in self.versions(x["node"]):
                covered |= {m + d for m in (e["message"] for e in self.evidence_of(v["id"])) for d in (-1, 0, 1)}
        hits = {int(item[1:]): hit for item, hit in self.relevance(queries, "m", 40, words, meaning).items()
                if int(item[1:]) < shown_from and int(item[1:]) not in covered}
        log_best = top_score(hits.values())
        log_bar = max(floor, log_best - level["near"], floor + (0.02 if meaning else 0.1))
        lines, skipped = [], 0
        for mid in sorted(hits, key=lambda m: -hits[m]["score"]):
            if hits[mid]["score"] < log_bar or len(lines) >= level["log"]:
                break
            block = self.message_block(self.message(mid))
            if used + tokens(block) > level["tokens"]:
                skipped += 1
                continue
            used += tokens(block)
            lines.append({"message": mid, "memory": self.name, "how": hits[mid]["how"], "score": round(hits[mid]["score"], 3), "block": block})
        return lines, used, skipped, len(hits)

    def finish_trace(self, trace, cited=None):
        """Fill in the connections between what was kept, the messages it cites, and the note."""
        chains = {x["node"] for x in trace["nodes"]}
        conns, seen = [], set()
        for x in trace["nodes"]:
            for l in self.links(x["node"]):
                if l["other"] in chains and l["edge"] not in seen:
                    seen.add(l["edge"])
                    conns.append({"edge": l["edge"], "a": l["a"], "b": l["b"], "kind": l["kind"], "reason": l["reason"],
                                  "strength": l["strength"]})
        trace["connections"] = conns[:20]
        trace["edges_used"] = sorted({x["edge"] for x in trace["nodes"] if x.get("edge")} | {c["edge"] for c in conns})
        cited = cited if cited is not None else {m for x in trace["nodes"] for m in x["messages"]}
        trace["messages"] = sorted(set(cited) | {l["message"] for l in trace["log"]})
        trace["briefing"] = briefing(self.sections(trace))
        return trace

    def sections(self, trace, label=""):
        """The memory note's sections for one memory's trace. label: added to headings (incognito)."""
        out = []
        for origin, heading in TIERS:
            blocks = [x["block"] for x in trace["nodes"] if x["origin"] == origin]
            out.append((heading.replace(":", f"{label}:", 1) if label else heading, blocks))
        lines = []
        for c in trace["connections"]:
            a, b = self.head(c["a"]), self.head(c["b"])
            arrow = {"part_of": "is part of", "builds_on": "builds on", "like": "is like", "against": "is in tension with",
                     "related": "relates to"}[c["kind"]]
            lines.append(f"[{self.handle(c['a'])}] {a['title']} {arrow} [{self.handle(c['b'])}] {b['title']}: {c['reason']}")
        out.append((f"How these connect{label}:", lines))
        out.append((f"From older parts of the conversation{label}:", [l["block"] for l in trace["log"]]))
        return out

    def node_block(self, chain, full=False, shown_from=None):
        """One node, the way DeepSeek sees it. full=True shows the whole message each quote came from.
        Messages from shown_from on are already in the recent conversation, so they're only pointed to."""
        n = self.current(chain)
        bits = [n["shape"] + (f", {n['label']}" if n["label"] and n["label"] != n["shape"] else ""), self.standing(n)]
        if n["about"]:
            bits.append(f"about {n['about']}")
        if n["version"] > 1:
            bits.append(f"version {n['version']}, updated {when(n['at'])}")
        lines = [f"[{self.handle(chain)}] {n['title']} ({'; '.join(bits)}): {n['text']}"]
        msgs = set()
        for v in self.evidence_of(n["id"]):
            msgs.add(v["message"])
            if shown_from and v["message"] >= shown_from:
                lines.append(f"   #{v['message']} (in the recent messages)")
            elif full:
                m = self.message(v["message"])
                text = m["text"][:v["start"]] + "«" + m["text"][v["start"]:v["end"]] + "»" + m["text"][v["end"]:]
                lines.append(f"   #{m['id']} {when(m['at'])}, {who(m['role'])}: {clip(text, v['start'], 600)}")
            else:
                lines.append(f"   #{v['message']} {when(v['at'])}, {who(v['role'])}: \"{v['quote']}\"")
        if n["origin"] == "inferred":
            rests = []
            for b in self.basis_of(n["id"]):
                if b["now"]:
                    rests.append(f"[{self.handle(b['chain'])}] {b['now']['title']} ({self.standing(b['now'])})")
            lines.append("   rests on: " + "; ".join(rests))
        for old in self.versions(chain)[1:4]:
            quotes = " ".join(f"#{v['message']}" for v in self.evidence_of(old["id"]))
            lines.append(f"   earlier, version {old['version']}: {old['text']}" + (f" ({quotes})" if quotes else ""))
        return "\n".join(lines), msgs

    def message_block(self, m):
        return f"#{m['id']} {when(m['at'])}, {who(m['role'])}: {clip(m['text'], 0, 700)}"

    def core(self, limit=10):
        """The biggest hubs, sent with every message so Avy always knows the big things in Shreyas's
        world. It only changes when the network does, so DeepSeek can cache it."""
        degree = {}
        for e in self.live_edges():
            degree[e["a"]] = degree.get(e["a"], 0) + 1
            degree[e["b"]] = degree.get(e["b"], 0) + 1
        hubs = [n for n in self.things() if degree.get(n["chain"], 0) >= 3]
        hubs.sort(key=lambda n: (-degree[n["chain"]], n["chain"]))
        if not hubs:
            return ""
        lines = [f"[{self.handle(n['chain'])}] {n['title']}" + (f" ({n['label']})" if n["label"] else "") + f": {n['text']}"
                 for n in hubs[:limit]]
        return "The big things in his world (the hubs of your memory):\n" + "\n".join(lines)

    def save_recall(self, mid, trace):
        kept = {k: v for k, v in trace.items() if k not in ("briefing",)}
        kept["nodes"] = [{k: v for k, v in x.items() if k != "block"} for x in trace["nodes"]]
        kept["log"] = [{k: v for k, v in x.items() if k != "block"} for x in trace["log"]]
        with self.tx() as db:
            return db.execute("INSERT INTO recalls (message, at, trace, briefing) VALUES (?, ?, ?, ?)",
                              (mid, now().isoformat(timespec="seconds"), json_dumps(kept), trace["briefing"])).lastrowid


def json_dumps(value):
    import json
    return json.dumps(value, default=str)


def combine(main_mem, main, own_mem, own):
    """An incognito turn's recall: from the main memory (read-only) and from this conversation's own.
    main and own are traces from Memory.recall, each from its own memory."""
    trace = {**own,
             "nodes": own["nodes"] + main["nodes"], "log": own["log"] + main["log"],
             "connections": own["connections"] + main["connections"],
             "edges_used": own["edges_used"], "main_edges_used": main["edges_used"],
             "tokens": own["tokens"] + main["tokens"], "skipped": own["skipped"] + main["skipped"],
             "searched": {k: own["searched"].get(k, 0) + main["searched"].get(k, 0) for k in ("nodes", "log")},
             "walked": own["walked"] + main["walked"], "seconds": round(own["seconds"] + main["seconds"], 3),
             "main_messages": main["messages"]}
    sections = main_mem.sections(main, " (from the main conversation; read-only here)") + \
        own_mem.sections(own, " (from earlier in this incognito conversation)")
    trace["briefing"] = briefing(sections) if trace["nodes"] or trace["log"] else own["briefing"]
    return trace
