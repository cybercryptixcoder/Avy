"""Reflection: Avy going back over what she knows, at quiet times. Three jobs:

  Connect   For new knowledge, code finds candidate partners anywhere in memory (close in meaning,
            sharing neighbors, or whose connections have similar reasons) and DeepSeek judges each
            pair: connect or not, what kind, and why. This is what lets week 1 meet week 10.
  Think     Code picks a focus (the newest episode with the older material closest to it, a hub that
            has grown, or a quiet corner to wander through) and DeepSeek works out what isn't said
            but follows: patterns, unnamed things several nodes are about, shared ideas, conclusions.
            Every inference rests on the nodes it comes from.
  Check     Something an inference rests on changed, or a connection's ends have new versions:
            DeepSeek says whether each still holds, needs revising, or should go.

DeepSeek proposes; the one door (memory/ops.py) decides. Every run is recorded.
"""

import random
from datetime import datetime

from memory import NAME, SHAPES, KINDS, node_ref, edge_ref, when, day
from memory.recall import hub_discount  # noqa: F401  (kept for readers: the same discount applies in search)

from . import llm
from .jobs import Job, Plan

PAIRS_PER_NODE = 8      # candidate partners judged for each new node
PAIRS_PER_RUN = 36      # pairs per Connect call
THINK_VIEW = 36         # nodes in view for one Think
MIN_CANDIDATE = 0.55    # how close (meaning) a candidate must be, at least


def brief(mem, n):
    out = f"{mem.handle(n['chain'])} [{n['shape']}" + (f" · {n['label']}" if n["label"] else "") + f"; {mem.standing(n)}"
    if n["about"]:
        out += f"; {n['about']}"
    out += f"] \"{n['title']}\": {n['text']}"
    said = mem.evidence_of(n["id"])
    if said:
        out += f"  ({day(said[0]['at'])})"
    return out


# ---------------------------------------------------------------------------
# Connect
# ---------------------------------------------------------------------------

def candidates(mem, chains, per_node=PAIRS_PER_NODE):
    """Pairs worth asking about: for each node, partners from anywhere in memory that it isn't
    connected to yet. Returns [(a, b, why)] with a < b, most promising first."""
    pairs = {}
    for c in chains:
        n = mem.current(c)
        if not n:
            continue
        linked = {l["other"] for l in mem.links(c, live_only=False)} | {o for o, how in mem.implicit(c) if how != "same episode"}
        scores, why = {}, {}

        def offer(other, score, reason):
            if other != c and other not in linked and score > scores.get(other, 0):
                scores[other], why[other] = score, reason

        vec = mem.vector(f"v{n['id']}")
        text = mem.node_words(n)
        for chain, hit in mem.land([(text, 1.0, vec)], k=30).items():          # close in meaning or words
            offer(chain, hit["score"], "close in meaning" if hit["how"] != "words" else "shares words")
        neighbors = {l["other"] for l in mem.links(c)}
        shared = {}
        for x in neighbors:                                                     # share neighbors
            for l in mem.links(x):
                shared[l["other"]] = shared.get(l["other"], 0) + 1
        for other, k in shared.items():
            if k >= 2:
                offer(other, 0.6 + 0.05 * k, f"shares {k} neighbors")
        if vec is not None:                                                     # connections with similar reasons
            for item, sim in mem.closest(vec, "c", 8):
                e = mem.edge(int(item[1:]))
                if e:
                    for end in (e["a"], e["b"]):
                        offer(end, sim - 0.05, "its connections have a similar reason")
        floor = MIN_CANDIDATE if vec is not None else 0.08          # keyword search alone scores much lower
        ranked = [o for o in sorted(scores, key=lambda o: -scores[o])
                  if scores[o] >= floor and mem.current(o) and not mem.was_judged(c, o)]
        for o in ranked[:per_node]:
            key = (min(c, o), max(c, o))
            if key not in pairs or scores[o] > pairs[key][0]:
                pairs[key] = (scores[o], why[o])
    return [(a, b, why) for (a, b), (score, why) in sorted(pairs.items(), key=lambda kv: -kv[1][0])]


CONNECT_INSTRUCTIONS = f"""You maintain the connections in Avy's memory of her conversations with {NAME}.
Below are pairs of nodes that might be connected. For each pair, decide whether someone who knows both
would connect them in their mind, and if so how:
  part_of     one belongs to the other, or is a piece or an instance of it
  builds_on   one uses, depends on, follows from, or was inspired by the other
  like        they're alike in a way that matters: the same shape of problem, the same principle, a real
              analogy. These are the most valuable connections, especially across very different topics.
  against     they're in tension: one contradicts, undermines or is an alternative to the other
  related     connected some other way that would be worth following
Don't connect things just because they share a word, a date or a broad area ("both are about work",
"both are things he told you"). Most pairs shown are not connected: they were picked because they look a
little alike, and that's usually all it is. Connect only when following the connection would genuinely
help someone thinking about one to recall the other. When unsure, don't connect.
For part_of and builds_on, say which node the connection goes "from": the part, or the one that builds on
the other. Every connection needs a reason: one short sentence that says what the connection is, specific
enough that someone who sees only the two titles understands it.
Answer every pair, by calling judge_connections."""

CONNECT_TOOL = llm.tool("judge_connections", "Say which pairs are connected, how, and why.", {
    "verdicts": {"type": "array", "items": llm.obj({
        "pair": {"type": "string", "description": "p1, p2, ..."},
        "connect": {"type": "boolean"},
        "kind": llm.nullable({"type": "string", "enum": list(KINDS)}),
        "from": llm.nullable({"type": "string", "description": "For part_of and builds_on: which handle it goes from."}),
        "reason": {"type": "string", "description": "One short sentence (empty if not connected)."},
    })},
})


class Connect(Job):
    name = "connect"
    tool = CONNECT_TOOL

    def __init__(self, mem, pairs):
        self.mem, self.pairs = mem, pairs[:PAIRS_PER_RUN]
        self.focus = f"{len(self.pairs)} pairs"

    def prompt(self):
        mem, lines = self.mem, []
        for i, (a, b, why) in enumerate(self.pairs, 1):
            lines.append(f"p{i}  ({why})\n    {brief(mem, mem.current(a))}\n    {brief(mem, mem.current(b))}")
        return [{"role": "system", "content": CONNECT_INSTRUCTIONS},
                {"role": "user", "content": "The pairs:\n\n" + "\n\n".join(lines)}]

    def check(self, answer):
        mem, plan = self.mem, Plan()
        verdicts = answer.get("verdicts") if isinstance(answer, dict) and isinstance(answer.get("verdicts"), list) else None
        if verdicts is None:
            plan.problems.append("The answer must have a list of verdicts, one per pair.")
            return plan
        seen = set()
        for v in verdicts:
            v = v if isinstance(v, dict) else {}
            p = self.pair_name(v.get("pair"))
            if not p:
                plan.problems.append(f"{v.get('pair')!r} isn't one of the pairs (p1 to p{len(self.pairs)}).")
                continue
            if p in seen:
                continue
            seen.add(p)
            a, b, _ = self.pairs[int(p[1:]) - 1]
            if not v.get("connect"):
                continue
            kind = v.get("kind")
            reason = " ".join(str(v.get("reason") or "").split())
            if kind not in KINDS:
                plan.problems.append(f"{p}: connected, so it needs a kind ({', '.join(KINDS)}).")
                continue
            if len(reason.split()) < 3:
                plan.problems.append(f"{p}: connected, so it needs a reason: one short sentence.")
                continue
            if kind in ("part_of", "builds_on"):
                start = node_ref(v.get("from"), mem.letter)
                if start == b:
                    a, b = b, a
                elif start != a:
                    plan.notes.append(f"{p}: no clear 'from' for {kind}; took the pair's first node.")
            plan.ops.append({"op": "connect", "a": a, "b": b, "kind": kind, "reason": reason, "support": {"kind": "inferred"}})
        missing = len(self.pairs) - len(seen)
        if missing:
            plan.notes.append(f"{missing} pairs had no verdict; counted as not connected.")
        plan.extra["judged"] = [(a, b, any(op["a"] in (a, b) and op["b"] in (a, b) for op in plan.ops)) for a, b, _ in self.pairs]
        return plan

    def pair_name(self, value):
        """'p3' -> 'p3'. Also accepts the pair's two handles ('k4, k5'), in either order. Else None."""
        v = str(value or "").strip().lower()
        if v.startswith("p") and v[1:].isdigit() and 1 <= int(v[1:]) <= len(self.pairs):
            return v
        ends = {node_ref(x, self.mem.letter) for x in v.replace("&", ",").replace(" and ", ",").split(",")}
        for i, (a, b, _) in enumerate(self.pairs, 1):
            if ends == {a, b}:
                return f"p{i}"
        return None

    def after(self, run_id, plan, results, refs):
        self.mem.record_judged(plan.extra.get("judged", []), run_id)
        return {"pairs": len(self.pairs), "connected": sum(1 for r in results if r["applied"])}


# ---------------------------------------------------------------------------
# Think
# ---------------------------------------------------------------------------

def think_focus(mem, rng=None):
    """What to think about next, or None: (kind, [chains], in words).
      episode   the newest episode not thought about yet, with the older nodes closest to each of its own
      hub       a thing that has gained 3+ connections since it was last thought about
      wander    a quiet corner: a node not visited in a while, its neighborhood, and a few distant relatives"""
    rng = rng or random.Random()
    done = int(mem.mark("think.episode", 0))
    ep = mem.row("SELECT * FROM episodes WHERE id > ? AND EXISTS (SELECT 1 FROM current WHERE episode = episodes.id) "
                 "ORDER BY id LIMIT 1", done)
    if ep:
        own = [n["chain"] for n in mem.rows("SELECT chain FROM current WHERE episode = ?", ep["id"])]
        view = list(own)
        for c in own:
            n = mem.current(c)
            for other, hit in sorted(mem.land([(mem.node_words(n), 1.0, mem.vector(f"v{n['id']}"))], k=12).items(),
                                     key=lambda kv: -kv[1]["score"])[:4]:
                if other not in view:
                    view.append(other)
            for l in mem.links(c)[:4]:
                if l["other"] not in view:
                    view.append(l["other"])
        return "episode", view[:THINK_VIEW], f"ep{ep['id']}: {ep['headline']}", {"think.episode": ep["id"]}

    degree = {}
    for e in mem.live_edges():
        degree[e["a"]] = degree.get(e["a"], 0) + 1
        degree[e["b"]] = degree.get(e["b"], 0) + 1
    grown = [(degree.get(n["chain"], 0) - int(mem.mark(f"think.hub.{n['chain']}", 0)), n) for n in mem.things()]
    grown = [(g, n) for g, n in grown if g >= 3]
    if grown:
        g, hub = max(grown, key=lambda x: x[0])
        view = [hub["chain"]] + [l["other"] for l in mem.links(hub["chain"], limit=THINK_VIEW)]
        view += [r["chain"] for r in mem.rows("""SELECT DISTINCT c.chain FROM current c JOIN basis b ON b.node = c.id
                                                  WHERE b.rests_on = ?""", hub["chain"])]
        return "hub", list(dict.fromkeys(view))[:THINK_VIEW], f"{mem.handle(hub['chain'])} {hub['title']} (+{g} connections)", \
            {f"think.hub.{hub['chain']}": degree.get(hub["chain"], 0)}

    nodes = [n for n in mem.current_nodes() if n["origin"] != "inferred"]
    quiet = [n for n in nodes if not mem.mark(f"think.node.{n['chain']}")]
    if len(nodes) >= 12 and quiet:
        start = rng.choice(quiet)
        view = [start["chain"]] + [l["other"] for l in mem.links(start["chain"])[:6]]
        hits = mem.land([(mem.node_words(start), 1.0, mem.vector(f"v{start['id']}"))], k=30)
        distant = [c for c, h in sorted(hits.items(), key=lambda kv: -kv[1]["score"]) if c not in view][6:12]
        view += distant
        return "wander", view[:THINK_VIEW], f"wandering from {mem.handle(start['chain'])} {start['title']}", \
            {f"think.node.{start['chain']}": 1}
    return None


THINK_INSTRUCTIONS = f"""You are Avy's reflection. Quietly, you look over part of her memory of {NAME} and work
out what isn't said anywhere but follows from what is. You write inferences: new nodes that rest on the
nodes they come from.

Look for:
- patterns across several things he said: habits, tendencies, what usually happens ("slept 8, then 7,
  then 8 hours" gives "usually sleeps about 8 hours")
- a thing that several nodes are clearly about but which has no node of its own: an unnamed project, an
  ongoing effort, a recurring theme. Create it (shape thing, named descriptively) and connect its parts
  to it (part_of, from each part to it).
- an idea several specific nodes share: a principle, a value, the same shape of problem in different
  places. Create it (shape idea) and connect the specific nodes to it.
- conclusions that follow from putting nodes together (a plan that clashes with something he said; a
  deadline that now can't be met)
- possibilities worth keeping in mind, marked possible

Rules:
1. Every inference rests on the nodes it comes from (basis: their handles). At least one of them must be
   something actually said (not inferred). "likely" needs at least two.
2. Don't restate a single node, and don't summarize. Don't infer health conditions, diagnoses or
   personality traits, and don't speculate about other people's private lives.
3. If an existing inference (marked inferred) should change because of what's in view, write a new
   version of it (replaces: its handle) instead of a second one. An inference can't replace something
   that was said.
4. Edges: connect your inferences to related nodes beyond their basis when it helps, each with a kind
   (part_of, builds_on, like, against, related) and a reason: one short sentence.
5. It's fine to infer nothing. A few inferences that would really help Avy understand him are worth more
   than many obvious ones.

Answer only by calling write_inferences."""

THINK_TOOL = llm.tool("write_inferences", "Save what follows from this part of memory.", {
    "inferences": {"type": "array", "items": llm.obj({
        "ref": {"type": "string", "description": "n1, n2, ..."},
        "replaces": llm.nullable({"type": "string", "description": "An existing inference this is a new version of (k12)."}),
        "shape": {"type": "string", "enum": list(SHAPES)},
        "label": {"type": "string", "description": "A word or two: pattern, project, principle, conclusion..."},
        "title": {"type": "string"},
        "text": {"type": "string", "description": "One or two sentences."},
        "certainty": {"type": "string", "enum": ["likely", "possible"]},
        "basis": {"type": "array", "items": {"type": "string"}, "description": "The handles it rests on (k12)."},
    })},
    "edges": {"type": "array", "items": llm.obj({
        "from": {"type": "string"}, "to": {"type": "string"},
        "kind": {"type": "string", "enum": list(KINDS)},
        "reason": {"type": "string"},
    })},
})


class Think(Job):
    name = "think"
    tool = THINK_TOOL

    def __init__(self, mem, kind, view, focus, marks):
        self.mem, self.kind, self.view, self.focus, self.marks = mem, kind, view, focus, marks

    def prompt(self):
        mem = self.mem
        nodes = [mem.current(c) for c in self.view if mem.current(c)]
        chains = {n["chain"] for n in nodes}
        lines = [brief(mem, n) + (self.rests(n) if n["origin"] == "inferred" else "") for n in nodes]
        conns, seen = [], set()
        for n in nodes:
            for l in mem.links(n["chain"]):
                if l["other"] in chains and l["edge"] not in seen:
                    seen.add(l["edge"])
                    conns.append(f"{mem.handle(l['a'])} {l['kind']} {mem.handle(l['b'])}: {l['reason']}")
        body = [f"Focus: {self.focus}", "Nodes in view:\n" + "\n".join(lines)]
        if conns:
            body.append("Connections among them:\n" + "\n".join(conns))
        return [{"role": "system", "content": THINK_INSTRUCTIONS}, {"role": "user", "content": "\n\n".join(body)}]

    def rests(self, n):
        return "  (rests on " + ", ".join(self.mem.handle(b["chain"]) for b in self.mem.basis_of(n["id"])) + ")"

    def check(self, answer):
        mem, plan = self.mem, Plan()
        if not isinstance(answer, dict):
            plan.problems.append("The answer must be an object with inferences and edges.")
            return plan
        refs, taken = set(), set()
        for i, x in enumerate(answer.get("inferences") if isinstance(answer.get("inferences"), list) else [], 1):
            x = x if isinstance(x, dict) else {}
            ref = str(x.get("ref") or "").strip()
            title = " ".join(str(x.get("title") or "").split())
            name = f'{ref or f"inference {i}"} "{title}"'
            if not ref.startswith("n") or not ref[1:].isdigit() or ref in taken:
                plan.problems.append(f"{name}: needs its own ref (n1, n2, ...).")
                ref = next(f"n{k}" for k in range(i, 10_000) if f"n{k}" not in taken)
            taken.add(ref)
            basis = []
            for b in x.get("basis") if isinstance(x.get("basis"), list) else []:
                c = node_ref(b, mem.letter)
                if c is None or not mem.current(c):
                    plan.problems.append(f"{name}: rests on {b}, which isn't a current node. Use handles from the nodes in view.")
                else:
                    basis.append(c)
            replaces = node_ref(x.get("replaces"), mem.letter) if x.get("replaces") not in (None, "", "null") else None
            if x.get("replaces") not in (None, "", "null") and (replaces is None or not mem.head(replaces)):
                plan.problems.append(f"{name}: replaces {x.get('replaces')}, which isn't a node.")
                replaces = None
            op = {"op": "add_node", "ref": ref, "shape": x.get("shape"), "label": x.get("label"), "title": title,
                  "text": x.get("text"), "certainty": x.get("certainty"), "basis": basis, "replaces": replaces,
                  "why": f"inferred while thinking about {self.focus}"}
            from memory.rules import check_node
            why, _ = check_node(mem, op)
            if why:
                plan.problems.append(f"{name}: {why}")
                continue
            refs.add(ref)
            plan.ops.append(op)
        for e in answer.get("edges") if isinstance(answer.get("edges"), list) else []:
            e = e if isinstance(e, dict) else {}
            ends = []
            for v in (e.get("from"), e.get("to")):
                v = str(v or "").strip()
                ends.append(v if v in refs else node_ref(v, mem.letter))
            label = f"edge {e.get('from')} -> {e.get('to')}"
            if any(x is None or (isinstance(x, int) and not mem.current(x)) for x in ends):
                plan.problems.append(f"{label}: both ends must be your new refs or handles of nodes in view.")
                continue
            if e.get("kind") not in KINDS or len(str(e.get("reason") or "").split()) < 3:
                plan.problems.append(f"{label}: needs a kind ({', '.join(KINDS)}) and a reason (one short sentence).")
                continue
            plan.ops.append({"op": "connect", "a": ends[0], "b": ends[1], "kind": e["kind"],
                             "reason": " ".join(str(e["reason"]).split()), "support": {"kind": "inferred"}})
        things = {op["ref"] for op in plan.ops if op["op"] == "add_node" and op["shape"] == "thing" and not op["replaces"]}
        for t in things:
            if not any(op["op"] == "connect" and t in (op["a"], op["b"]) for op in plan.ops):
                plan.problems.append(f"{t}: a new thing needs its parts connected to it (part_of, from each part to {t}).")
        return plan

    def after(self, run_id, plan, results, refs):
        for key, value in self.marks.items():
            self.mem.set_mark(key, value)
        made = [r for r in results if r["op"] == "add_node" and r["applied"]]
        return {"kind": self.kind, "inferred": len(made), "new_chains": sorted({r["chain"] for r in made})}


# ---------------------------------------------------------------------------
# Check
# ---------------------------------------------------------------------------

CHECK_INSTRUCTIONS = f"""You keep Avy's memory of {NAME} honest. Some of what she worked out rests on things
that have since changed, and some connections join nodes that have new versions. For each item, compare
what it was based on then with what's true now, and give a verdict:
  holds     still right as it is
  revise    still has something to it, but needs rewording (give the new text; for a connection, the new
            kind and reason)
  retract   no longer true or no longer connected (say why)
Answer every item, by calling recheck."""

CHECK_TOOL = llm.tool("recheck", "Say whether each item still holds.", {
    "verdicts": {"type": "array", "items": llm.obj({
        "item": {"type": "string", "description": "The handle: k12 for an inference, c7 for a connection."},
        "verdict": {"type": "string", "enum": ["holds", "revise", "retract"]},
        "title": llm.nullable({"type": "string", "description": "revise, inference: a new title if it needs one."}),
        "text": llm.nullable({"type": "string", "description": "revise, inference: the new text."}),
        "certainty": llm.nullable({"type": "string", "enum": ["likely", "possible"]}),
        "kind": llm.nullable({"type": "string", "enum": list(KINDS)}),
        "reason": llm.nullable({"type": "string", "description": "revise, connection: the new reason."}),
        "why": {"type": "string", "description": "One short sentence."},
    })},
})


def check_items(mem, limit=16):
    """What needs a re-check: inferences whose basis moved on, connections whose ends did (not part_of:
    belonging to something rarely changes with a new version)."""
    items = [("node", n) for n in mem.stale_inferences()]
    items += [("edge", e) for e in mem.stale_edges() if e["kind"] != "part_of"]
    return items[:limit]


class Check(Job):
    name = "check"
    tool = CHECK_TOOL

    def __init__(self, mem, items):
        self.mem, self.items = mem, items
        self.focus = f"{len(items)} items"

    def prompt(self):
        mem, blocks = self.mem, []
        for kind, x in self.items:
            if kind == "node":
                lines = [f"{mem.handle(x['chain'])} inferred ({x['certainty']}): \"{x['title']}\": {x['text']}", "  rests on:"]
                for b in mem.basis_of(x["id"]):
                    seen = mem.node(b["seen"])
                    now = b["now"]
                    if not b["stale"]:
                        lines.append(f"    {mem.handle(b['chain'])} (unchanged) \"{now['title']}\": {now['text']}")
                    elif now is None or now["state"] != "active":
                        lines.append(f"    {mem.handle(b['chain'])} was \"{seen['title']}\": {seen['text']}\n      now: retracted"
                                     + (f" ({now['why']})" if now and now.get("why") else ""))
                    else:
                        lines.append(f"    {mem.handle(b['chain'])} was: {seen['text']}\n      now (version {now['version']}, {when(now['at'])}): {now['text']}")
                blocks.append("\n".join(lines))
            else:
                a_then, b_then = mem.node(x["a_seen"]), mem.node(x["b_seen"])
                a_now, b_now = mem.head(x["a"]), mem.head(x["b"])
                lines = [f"c{x['id']} {mem.handle(x['a'])} {x['kind']} {mem.handle(x['b'])}: {x['reason']}"]
                for then, now in ((a_then, a_now), (b_then, b_now)):
                    if then["id"] == now["id"]:
                        lines.append(f"  {mem.handle(now['chain'])} (unchanged) \"{now['title']}\": {now['text']}")
                    else:
                        lines.append(f"  {mem.handle(now['chain'])} was: {then['text']}\n    now: {now['text']}")
                blocks.append("\n".join(lines))
        return [{"role": "system", "content": CHECK_INSTRUCTIONS}, {"role": "user", "content": "\n\n".join(blocks)}]

    def check(self, answer):
        mem, plan = self.mem, Plan()
        verdicts = answer.get("verdicts") if isinstance(answer, dict) and isinstance(answer.get("verdicts"), list) else None
        if verdicts is None:
            plan.problems.append("The answer must have a list of verdicts, one per item.")
            return plan
        wanted = {(mem.handle(x["chain"]) if k == "node" else f"c{x['id']}"): (k, x) for k, x in self.items}
        for v in verdicts:
            v = v if isinstance(v, dict) else {}
            key = str(v.get("item") or "").strip().lower()
            if key not in wanted:
                plan.problems.append(f"{v.get('item')!r} isn't one of the items.")
                continue
            kind, x = wanted.pop(key)
            verdict, why = v.get("verdict"), " ".join(str(v.get("why") or "").split()) or "re-checked"
            if kind == "node":
                if verdict == "holds":
                    plan.ops.append({"op": "reaffirm", "chain": x["chain"]})
                elif verdict == "retract":
                    plan.ops.append({"op": "retract_node", "chain": x["chain"], "why": why})
                elif verdict == "revise":
                    text = " ".join(str(v.get("text") or "").split())
                    if not text:
                        plan.problems.append(f"{key}: revise needs the new text.")
                        continue
                    basis = [b["chain"] for b in mem.basis_of(x["id"]) if b["now"] and b["now"]["state"] == "active"]
                    plan.ops.append({"op": "add_node", "shape": x["shape"], "label": x["label"], "title": v.get("title") or x["title"],
                                     "text": text, "certainty": v.get("certainty") or x["certainty"], "basis": basis,
                                     "replaces": x["chain"], "why": why})
            else:
                if verdict == "holds":
                    plan.ops.append({"op": "reaffirm", "edge": x["id"]})
                elif verdict == "retract":
                    plan.ops += [{"op": "oppose", "edge": x["id"], "support": {"kind": "inferred", "note": why}},
                                 {"op": "reaffirm", "edge": x["id"]}]
                elif verdict == "revise":
                    plan.ops.append({"op": "revise_edge", "edge": x["id"], "kind": v.get("kind") or x["kind"],
                                     "reason": v.get("reason") or x["reason"], "why": why})
        if wanted:
            plan.problems.append("No verdict for: " + ", ".join(wanted) + ".")
        return plan

    def after(self, run_id, plan, results, refs):
        made = [r for r in results if r["op"] == "add_node" and r["applied"]]
        return {"items": len(self.items), "new_chains": sorted({r["chain"] for r in made}),
                "retracted": sum(1 for r in results if r["op"] in ("retract_node", "oppose") and r["applied"])}
