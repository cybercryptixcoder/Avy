"""Avy searching her own memory, step by step (/explore: on).

Rule-based recall (memory/recall.py) lands near the words of a message and walks outward in rings.
But what a message needs is often nowhere near its words: "how should I organize the shared drive?"
may need what Shreyas once said about ant trails and footpaths on a campus, which share no words with
it. The message is only a proxy for the task. So here DeepSeek steers the search, the way AlphaEvolve
puts a model where an evolutionary algorithm had fixed rules:

  0. Land: code runs ordinary recall and a plain search, and shows the closest nodes as previews, each
     with its connections (kind and reason): the signposts.
  1. Each round, DeepSeek sees what it has read, what's at the frontier, and its own notes, and decides:
       task       what the message actually needs
       questions  what it still needs to know (the open questions drive the search)
       open       nodes to read in full: their exact words, everything they connect to   (dig)
       follow     nodes whose neighbors to look at                                      (explore)
       search     new searches in its own words, for what the message never mentions    (re-land)
       keep       what Avy should have in mind for the reply (nodes and log lines)
       done       when the questions are answered, or nothing more is likely to help
  2. Code carries out the moves, shows what they turned up, and repeats. /recall: sets the rounds.
  3. What was kept becomes the memory note, laid out like recall's (said, Avy said, inferred).

Connections it followed to things it kept get a 'used' support: retrieval strengthens the paths
that actually help (not in incognito, and not in benchmark probes).
Everything it did is in the trace, so the inspector (and the graph view) can replay the path.
"""

import time

from memory import NAME, embedder, node_ref, message_ref, tokens, clip, when, who
from memory.recall import DEPTHS, briefing

from . import llm

PREVIEWS = 14           # nodes shown at the frontier each round
MAX_OPEN, MAX_FOLLOW, MAX_SEARCH = 5, 4, 3

INSTRUCTIONS = f"""You are the part of Avy that searches her memory before she answers {NAME}.
Memory is a network: nodes (things, information and ideas) with handles like k12, joined by connections
that each have a kind and a reason. Some nodes are things he said, some things Avy said, some Avy inferred.

The message is only a clue to what he needs. Find everything Avy should have in mind to answer it well:
not just what matches its words, but what bears on the task behind it: his related experiences, ideas
and principles of his that apply (even from very different topics), plans or people it affects, things
in tension with it, and how earlier attempts turned out. Work out what the task is and what would help,
then go and look for that.

Each round you can:
  open     read nodes in full: their exact words and all their connections
  follow   look at the neighbors of nodes (one step along their connections)
  search   search memory in your own words, for things the message doesn't mention but the task needs
  keep     the nodes (k12) and log lines (#41) Avy should have; this replaces your previous keep list
  done     true when your questions are answered, or nothing more is likely to help
Keep what genuinely helps; leave out what only sounds similar. If memory has nothing useful, keep
nothing and say so in your questions. Answer only by calling explore_memory."""

TOOL = llm.tool("explore_memory", "Decide the next moves in the search, and what to keep.", {
    "task": {"type": "string", "description": "What the message actually needs, in one sentence."},
    "questions": {"type": "array", "items": {"type": "string"}, "description": "What you still need to know."},
    "open": {"type": "array", "items": {"type": "string"}, "description": f"Node handles to read in full (at most {MAX_OPEN})."},
    "follow": {"type": "array", "items": {"type": "string"}, "description": f"Node handles whose neighbors to look at (at most {MAX_FOLLOW})."},
    "search": {"type": "array", "items": {"type": "string"}, "description": f"New searches, in your own words (at most {MAX_SEARCH})."},
    "keep": {"type": "array", "items": llm.obj({
        "item": {"type": "string", "description": "A node handle (k12) or a log line (#41)."},
        "why": {"type": "string", "description": "How it helps, in a few words."},
    })},
    "done": {"type": "boolean"},
})


class Library:
    """The memories a search may read: the main one, plus an incognito one while it's going.
    Their node handles start with different letters (k12, x12), so they never mix up."""

    def __init__(self, mems):
        self.mems = [m for m in mems if m]
        self.by_letter = {m.letter: m for m in self.mems}

    def node(self, handle):
        """'k12' -> (memory, 12), or (None, None)."""
        h = str(handle or "").strip().strip("[]")
        mem = self.by_letter.get(h[:1].lower())
        c = node_ref(h, mem.letter) if mem else None
        return (mem, c) if mem and c is not None and mem.current(c) else (None, None)

    def message(self, ref, default):
        """'#41' -> (memory, 41). Log lines are read from the memory being talked to."""
        mid = message_ref(ref)
        return (default, mid) if mid and default.message(mid) else (None, None)


def preview(mem, chain, links=4):
    n = mem.current(chain)
    out = f"{mem.handle(chain)} [{n['shape']}" + (f" · {n['label']}" if n["label"] else "") + f"; {mem.standing(n)}] {n['title']}: {clip(n['text'], 0, 220)}"
    ls = mem.links(chain)
    if ls:
        bits = [f"{mem.handle(l['other'])} {mem.current(l['other'])['title']} ({l['kind'].replace('_', ' ')}: {clip(l['reason'], 0, 90)})"
                for l in ls[:links]]
        out += "\n      connects to: " + "; ".join(bits) + (f"; +{len(ls) - links} more" if len(ls) > links else "")
    if n["origin"] == "inferred":
        out += "\n      rests on: " + ", ".join(mem.handle(b["chain"]) for b in mem.basis_of(n["id"]))
    return out


def search(library, text, words=True, meaning=True, k=8):
    """A plain search across every memory in the library: [(memory, chain, score)], best first."""
    vec = embedder.query(text) if meaning and embedder.ready else None
    found = []
    for mem in library.mems:
        for chain, hit in mem.land([(text, 1.0, vec)], words, bool(vec is not None)).items():
            found.append((mem, chain, hit["score"]))
    found.sort(key=lambda x: -x[2])
    return found[:k]


def explore(library, home, text, recent="", shown_from=None, depth="normal", words=True, meaning=True,
            learn=True, progress=None):
    """Search memory with DeepSeek steering. library: the memories to read; home: the one being talked to
    (log lines come from it). recent: the last message or two, for context. learn: strengthen connections
    that led to what was kept. progress(event): told about each round as it happens.
    Returns a trace shaped like Memory.recall's, plus trace["explore"] with every round."""
    started = time.time()
    level = DEPTHS.get(depth)
    trace = home.empty_trace(text, depth, words, meaning)
    if level is None or not (words or (meaning and embedder.ready)):
        trace["briefing"] = briefing([], "Memory recall is off for this message." if level is None else
                                     "Memory search is switched off (no words, no meaning), so nothing was looked up.")
        return trace
    shown_from = shown_from or home.last_id() + 1
    rounds_allowed = level["rounds"]
    rec = {"rounds": [], "visited": [], "usage": {"prompt_tokens": 0, "completion_tokens": 0}, "cost": 0.0}

    # 0. Land: what ordinary recall would bring, plus a plain search for the message.
    frontier, came_by = [], {}           # came_by[(letter, chain)] = (edge id, from handle) for nodes reached by following

    def add(mem, chain):
        h = mem.handle(chain)
        if h not in frontier:
            frontier.append(h)

    landing = []
    for mem in library.mems:
        r = mem.recall(text, "", shown_from if mem is home else None, depth, words, meaning)
        landing += [(mem, x["node"], x["score"]) for x in r["nodes"]]
    landing += search(library, text, words, meaning, PREVIEWS)
    for mem, chain, _ in sorted(landing, key=lambda x: -x[2])[:PREVIEWS]:
        add(mem, chain)
    rec["landing"] = list(frontier)

    opened, kept, notes, searches = {}, [], {"task": "", "questions": []}, []
    log_hits = {}
    convo_answer = None
    for rnd in range(1, rounds_allowed + 1):
        prompt = make_prompt(library, home, text, recent, frontier, opened, kept, notes, searches, log_hits,
                             rnd, rounds_allowed)
        convo = [{"role": "system", "content": INSTRUCTIONS}, {"role": "user", "content": prompt}]
        try:
            reply = llm.call(convo, TOOL, max_tokens=2000)
        except Exception as e:
            rec["error"] = str(getattr(e, "message", e))
            break
        for k in rec["usage"]:
            rec["usage"][k] += (reply.get("usage") or {}).get(k, 0)
        rec["cost"] += llm.cost(reply.get("usage") or {})
        answer, problem = llm.read_call(reply, "explore_memory")
        if problem:
            rec["rounds"].append({"round": rnd, "problem": problem})
            continue
        convo_answer = answer
        notes = {"task": str(answer.get("task") or ""), "questions": [str(q) for q in answer.get("questions") or []][:6]}
        kept = []
        for k in answer.get("keep") or []:
            item = str((k or {}).get("item") or "").strip()
            mem, chain = library.node(item)
            if mem:
                kept.append({"item": mem.handle(chain), "why": str(k.get("why") or "")})
            else:
                m, mid = library.message(item, home)
                if m:
                    kept.append({"item": f"#{mid}", "why": str(k.get("why") or "")})
        step = {"round": rnd, "task": notes["task"], "questions": notes["questions"], "open": [], "follow": [],
                "search": [], "keep": [k["item"] for k in kept], "done": bool(answer.get("done"))}
        if answer.get("done") or rnd == rounds_allowed:
            rec["rounds"].append(step)
            if progress:
                progress({"round": rnd, "done": True, "keep": step["keep"]})
            break
        for h in (answer.get("open") or [])[:MAX_OPEN]:              # dig
            mem, chain = library.node(h)
            if mem and mem.handle(chain) not in opened:
                block, _ = mem.node_block(chain, full=True, shown_from=shown_from if mem is home else None)
                links = mem.links(chain, limit=20)
                block += "\n   connections:\n" + "\n".join(
                    f"     {l['kind'].replace('_', ' ')} {mem.handle(l['other'])} {mem.current(l['other'])['title']}: {l['reason']}"
                    for l in links) if links else ""
                opened[mem.handle(chain)] = block
                step["open"].append(mem.handle(chain))
                for l in links:
                    came_by.setdefault((mem.letter, l["other"]), (l["edge"], mem.handle(chain)))
        for h in (answer.get("follow") or [])[:MAX_FOLLOW]:          # explore
            mem, chain = library.node(h)
            if mem:
                step["follow"].append(mem.handle(chain))
                for l in mem.links(chain, limit=8):
                    came_by.setdefault((mem.letter, l["other"]), (l["edge"], mem.handle(chain)))
                    add(mem, l["other"])
                for other, how in mem.implicit(chain)[:3]:
                    add(mem, other)
        for q in [str(s) for s in (answer.get("search") or [])[:MAX_SEARCH] if str(s).strip()]:   # re-land
            hits = search(library, q, words, meaning, 6)
            searches.append((q, [m.handle(c) for m, c, _ in hits]))
            for mem, chain, _ in hits:
                add(mem, chain)
            vec = embedder.query(q) if meaning and embedder.ready else None
            for item, hit in home.relevance([(q, 1.0, vec)], "m", 6, words, vec is not None).items():
                mid = int(item[1:])
                if mid < shown_from and hit["score"] >= (0.6 if vec is not None else 0.3):
                    log_hits[mid] = max(log_hits.get(mid, 0), hit["score"])
            step["search"].append(q)
        rec["rounds"].append(step)
        if progress:
            progress({"round": rnd, "open": step["open"], "follow": step["follow"], "search": step["search"],
                      "questions": notes["questions"]})
        frontier = frontier[-60:]

    rec["visited"] = list(dict.fromkeys(rec["landing"] + [h for s in rec["rounds"] for h in s.get("open", []) + s.get("follow", [])]))
    rec["task"] = notes["task"]
    trace["explore"] = rec
    if convo_answer is None and not kept:
        # the model couldn't be reached or never answered properly: fall back to ordinary recall
        fallback = home.recall(text, "", shown_from, depth, words, meaning)
        fallback["explore"] = {**rec, "fell_back": True}
        return fallback

    # 3. What was kept becomes the note, laid out like recall's.
    used, picked, log_lines, cited = 0, [], [], set()
    by_mem = {}
    for k in kept:
        if k["item"].startswith("#"):
            mid = int(k["item"][1:])
            m = home.message(mid)
            block = home.message_block(m)
            if used + tokens(block) > level["tokens"]:
                continue
            used += tokens(block)
            log_lines.append({"message": mid, "memory": home.name, "how": "explored", "score": 1.0, "block": block, "why": k["why"]})
            continue
        mem, chain = library.node(k["item"])
        block, msgs = mem.node_block(chain, full=len(picked) < 3, shown_from=shown_from if mem is home else None)
        if used + tokens(block) > level["tokens"]:
            continue
        used += tokens(block)
        edge, via = came_by.get((mem.letter, chain), (None, None))
        item = mem.trace_item(chain, {"score": 1.0, "how": "explored", "via": node_ref(via, mem.letter) if via else None,
                                      "edge": edge}, block, msgs)
        item["why"] = k["why"]
        picked.append(item)
        by_mem.setdefault(mem.name, []).append(item)
        cited |= msgs if mem is home else set()

    if learn:          # the connections that led somewhere useful get stronger (only in the memory being talked to)
        for item in picked:
            mem = next(m for m in library.mems if m.name == item["memory"])
            if item.get("edge") and mem is home:
                mem.apply({"op": "connect", **{k: mem.edge(item["edge"])[k] for k in ("a", "b", "kind", "reason")},
                           "support": {"kind": "used", "source": "explore", "note": f"led to {item['handle']} for: {clip(text, 0, 80)}"}})

    trace.update({"nodes": picked, "log": log_lines, "tokens": used, "seconds": round(time.time() - started, 2),
                  "searched": {"nodes": len(rec["visited"]), "log": len(log_hits)}, "walked": len(came_by)})
    if len(library.mems) > 1:
        sections = []
        for mem in library.mems:
            part = {**trace, "nodes": by_mem.get(mem.name, []), "log": log_lines if mem is home else [], "connections": []}
            mem.finish_trace(part)
            trace["connections"] += part["connections"]
            label = " (from the main conversation; read-only here)" if mem is not home else " (from earlier in this incognito conversation)"
            sections += mem.sections(part, label)
        trace["messages"] = sorted(cited | {l["message"] for l in log_lines})
        trace["briefing"] = briefing(sections) if picked or log_lines else briefing([], "Avy searched her memory and found nothing that helps with this.")
    else:
        home.finish_trace(trace, cited)
        if not picked and not log_lines:
            trace["briefing"] = briefing([], "Avy searched her memory and found nothing that helps with this.")
    if notes["task"]:
        trace["briefing"] += f"\n\n(What the search took this message to need: {notes['task']})"
    return trace


def make_prompt(library, home, text, recent, frontier, opened, kept, notes, searches, log_hits, rnd, rounds):
    parts = [f"The message: {text}"]
    if recent:
        parts.append(f"Just before it:\n{recent}")
    parts.append(f"Round {rnd} of {rounds}." + (" This is the last round: decide what to keep, and set done." if rnd == rounds else ""))
    if notes["task"]:
        parts.append(f"Your notes so far. Task: {notes['task']}\nOpen questions: " + ("; ".join(notes["questions"]) or "none"))
    if opened:
        parts.append("Read in full:\n" + "\n\n".join(opened.values()))
    previews = []
    for h in frontier:
        if h in opened:
            continue
        mem, chain = library.node(h)
        if mem:
            previews.append(preview(mem, chain))
        if len(previews) >= PREVIEWS:
            break
    parts.append("At the frontier (previews):\n" + ("\n".join(previews) if previews else "nothing found yet"))
    if searches:
        parts.append("Your searches: " + "; ".join(f'"{q}" -> {", ".join(hs) or "nothing"}' for q, hs in searches[-6:]))
    if log_hits:
        lines = [home.message_block(home.message(mid)) for mid in sorted(log_hits, key=lambda m: -log_hits[m])[:6]]
        parts.append("From the log (raw messages your searches matched; keep as #41 if useful):\n" + "\n".join(lines))
    if kept:
        parts.append("Kept so far: " + ", ".join(f"{k['item']} ({k['why']})" for k in kept))
    return "\n\n".join(parts)
