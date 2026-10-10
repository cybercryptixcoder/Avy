"""The network: connections between nodes, and how strong each one is.

An edge connects two nodes (their chains, so it survives new versions of either end). It has a kind
and a reason. Its strength isn't a number anyone picks: it's computed from its supports, every
reason anyone had to believe or doubt it, all kept forever.

    kind        part_of     a belongs to b, or is an instance of it    (Rohan's birthday -> Rohan)
                builds_on   a uses, depends on, or follows from b      (gift idea -> what he wants)
                like        alike in a way that matters, even across very different topics
                against     in tension: contradicts, or is an alternative to
                related     connected some other way
    support     stated 3    Shreyas made the connection himself (his words are quoted)
                confirmed 3 he agreed when it came up
                inferred 1  the model judged it
                observed .5 the two came up together again later
                used .5     a search followed it and kept what it found
"""

from datetime import datetime

from .common import now

KINDS = ("part_of", "builds_on", "like", "against", "related")
DIRECTED = ("part_of", "builds_on")
SUPPORTS = ("stated", "confirmed", "inferred", "observed", "used")
WEIGHT = {"stated": 3.0, "confirmed": 3.0, "inferred": 1.0, "observed": 0.5, "used": 0.5}
LASTING = ("stated", "confirmed")      # what Shreyas said never fades, and the model can't argue it down
FADES = ("like", "related")            # associations fade unless they're used or come up again;
HALF_LIFE = 90                         #   their weaker supports count half after this many days
LIVE = 0.5                             # an edge this strong or stronger is followed; weaker ones are dormant
MAX_LIVE = 12                          # a node follows at most its 12 strongest edges


def strength_of(edge, supports, as_of=None):
    """The strength of one edge from its supports, as it stood at `as_of` (default: now)."""
    as_of = datetime.fromisoformat(as_of) if isinstance(as_of, str) else (as_of or now())
    supports = [s for s in supports if datetime.fromisoformat(s["at"]) <= as_of]
    said_so = any(s["sign"] > 0 and s["kind"] in LASTING for s in supports)
    total = 0.0
    for s in supports:
        w = WEIGHT[s["kind"]]
        if s["sign"] < 0 and said_so and s["kind"] not in LASTING:
            continue                    # the model can't overrule what Shreyas said
        if edge["kind"] in FADES and s["kind"] not in LASTING:
            days = max(0.0, (as_of - datetime.fromisoformat(s["at"])).total_seconds() / 86400)
            w *= 0.5 ** (days / HALF_LIFE)
        total += s["sign"] * w
    return round(total, 3)


class Network:

    def edge(self, eid):
        return self.row("SELECT * FROM edges WHERE id = ?", eid)

    def edge_between(self, a, b):
        return self.row("SELECT * FROM edges WHERE min(a, b) = min(?, ?) AND max(a, b) = max(?, ?)", a, b, a, b)

    def supports_of(self, eid):
        return self.rows("SELECT * FROM supports WHERE edge = ? ORDER BY id", eid)

    def strength(self, eid, as_of=None):
        return strength_of(self.edge(eid), self.supports_of(eid), as_of)

    def _with_strength(self, edges, as_of=None):
        if not edges:
            return []
        ids = [e["id"] for e in edges]
        by_edge = {}
        for s in self.rows(f"SELECT * FROM supports WHERE edge IN ({','.join('?' * len(ids))})", *ids):
            by_edge.setdefault(s["edge"], []).append(s)
        for e in edges:
            e["supports"] = by_edge.get(e["id"], [])
            e["strength"] = strength_of(e, e["supports"], as_of)
        return edges

    def links(self, chain, live_only=True, limit=MAX_LIVE):
        """The connections of one node, strongest first: [{edge, other, kind, direction, reason, strength, ...}].
        direction: 'out' (this node -> other, as written), 'in' (other -> this node), '' (goes both ways).
        live_only: only edges strong enough to follow, to nodes that still exist, at most `limit`."""
        edges = self._with_strength(self.rows("SELECT * FROM edges WHERE a = ? OR b = ?", chain, chain))
        found = []
        for e in edges:
            other = e["b"] if e["a"] == chain else e["a"]
            if live_only and (e["strength"] < LIVE or not self.current(other)):
                continue
            direction = "" if e["kind"] not in DIRECTED else "out" if e["a"] == chain else "in"
            found.append({**e, "edge": e["id"], "other": other, "direction": direction})
        found.sort(key=lambda x: -x["strength"])
        return found[:limit] if live_only else found

    def degree(self, chain):
        return len(self.links(chain))

    def parts(self, chain):
        """What belongs to a thing (live part_of connections into it), newest first: current node rows.
        Not capped by the strongest-12 limit on following: a hub's newest parts are often its weakest yet."""
        found = []
        for e in self._with_strength(self.rows("SELECT * FROM edges WHERE b = ? AND kind = 'part_of'", chain)):
            n = self.current(e["a"]) if e["strength"] >= LIVE else None
            if n:
                found.append(n)
        return sorted(found, key=lambda n: (n["at"], n["id"]), reverse=True)

    def live_edges(self, as_of=None):
        """Every edge strong enough to follow, between nodes that exist now (for health and the graph)."""
        alive = {r["chain"] for r in self.rows("SELECT chain FROM current")}
        edges = self._with_strength(self.rows("SELECT * FROM edges"), as_of)
        return [e for e in edges if e["strength"] >= LIVE and e["a"] in alive and e["b"] in alive]

    def stale_edges(self):
        """Edges whose ends have new versions since the edge was last checked."""
        return self.rows("""SELECT e.* FROM edges e JOIN heads ha ON ha.chain = e.a JOIN heads hb ON hb.chain = e.b
                            WHERE (ha.id != e.a_seen OR hb.id != e.b_seen)
                              AND ha.state = 'active' AND hb.state = 'active' ORDER BY e.id""")

    def implicit(self, chain):
        """Neighbors nobody had to write down: [(other chain, how)].
          rests on / supports   an inference and the nodes it rests on, both ways
          same message          both were written from the same message
          same episode          both were written from the same stretch of conversation"""
        h = self.current(chain)
        if not h:
            return []
        found = []
        for b in self.rows("SELECT rests_on FROM basis WHERE node = ?", h["id"]):
            found.append((b["rests_on"], "rests on"))
        for r in self.dependents(chain):
            found.append((r["chain"], "supports"))
        for r in self.rows("""SELECT DISTINCT c.chain FROM evidence a JOIN evidence b ON a.message = b.message
                              JOIN current c ON c.id = b.node WHERE a.node = ? AND c.chain != ?""", h["id"], chain):
            found.append((r["chain"], "same message"))
        if h["episode"]:
            for r in self.rows("SELECT chain FROM current WHERE episode = ? AND chain != ? LIMIT 8", h["episode"], chain):
                found.append((r["chain"], "same episode"))
        seen, unique = set(), []
        for other, how in found:
            if other != chain and other not in seen and self.current(other):
                seen.add(other)
                unique.append((other, how))
        return unique
