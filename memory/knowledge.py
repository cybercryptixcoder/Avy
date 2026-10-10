"""Knowledge: nodes, their versions, and what each one rests on (your words, or other nodes).

A node is one thing worth knowing. Three shapes:
    thing         something with an identity that other knowledge gathers around: a person, a place,
                  a project, a course, an ongoing effort. Its text says only what it is.
    information   one claim: a fact, an event, a plan, a decision, a preference, a number.
    idea          a concept, a principle, a proposal, a hypothesis, an analogy, a way of seeing things.
Three origins, from most to least reliable:
    user          Shreyas said it: evidence points at his exact words
    avy           Avy said it in the conversation (her suggestions, her ideas): evidence points at hers
    inferred      Avy worked it out quietly: its basis is the nodes it rests on, with a certainty
An inferred node becomes a 'user' one only by a new version whose evidence is Shreyas's own words
(he confirmed it). Code decides the origin from the evidence; the model never just claims it.
"""

import re

from .common import NAME

SHAPES = ("thing", "information", "idea")
ORIGINS = ("user", "avy", "inferred")
SAID_BY = {"user": "you said", "avy": "Avy said", "inferred": "inferred"}


class Knowledge:

    def node(self, nid):
        """One version of a node, by its row id."""
        return self.row("SELECT * FROM nodes WHERE id = ?", nid)

    def head(self, chain):
        """The newest version of a node (k12 -> chain 12), active or retracted. None if there's no such node."""
        return self.row("SELECT * FROM heads WHERE chain = ?", chain)

    def current(self, chain):
        """The newest version, if the node hasn't been retracted."""
        h = self.head(chain)
        return h if h and h["state"] == "active" else None

    def versions(self, chain):
        """Every version of a node, newest first."""
        return self.rows("SELECT * FROM nodes WHERE chain = ? ORDER BY version DESC", chain)

    def current_nodes(self):
        return self.rows("SELECT * FROM current ORDER BY chain")

    def evidence_of(self, nid):
        """The exact words a node version came from (version row id)."""
        return self.rows("""SELECT v.*, m.at, m.role FROM evidence v JOIN messages m ON m.id = v.message
                            WHERE v.node = ? ORDER BY v.message, v.start""", nid)

    def basis_of(self, nid):
        """What an inferred node version rests on: each node, the version it saw, and whether that's
        still the newest one (if not, the inference is due a re-check)."""
        found = []
        for b in self.rows("SELECT * FROM basis WHERE node = ? ORDER BY rests_on", nid):
            h = self.head(b["rests_on"])
            found.append({"chain": b["rests_on"], "seen": b["seen"], "now": h,
                          "stale": h is None or h["id"] != b["seen"] or h["state"] != "active"})
        return found

    def dependents(self, chain):
        """Current inferred nodes that rest on this node."""
        return self.rows("""SELECT c.* FROM current c JOIN basis b ON b.node = c.id
                            WHERE b.rests_on = ? AND c.origin = 'inferred'""", chain)

    def stale_inferences(self):
        """Current inferred nodes whose ground has moved: something they rest on has a newer version
        than the one they saw, or was retracted."""
        return self.rows("""SELECT DISTINCT c.* FROM current c JOIN basis b ON b.node = c.id
                            JOIN heads h ON h.chain = b.rests_on
                            WHERE c.origin = 'inferred' AND (h.id != b.seen OR h.state != 'active')
                            ORDER BY c.chain""")

    def node_words(self, n):
        """What search sees for a node version: its title and text (and label). Shreyas's name is left
        out: nearly every node mentions him, so it says nothing about what a node is about, and in
        meaning search it would make everything look a little alike."""
        text = f"{n['title']}: {n['text']}" + (f" ({n['label']})" if n.get("label") else "")
        return re.sub(rf"\b{NAME}'s\b", "his", re.sub(rf"\b{NAME}\b", "he", text))

    def standing(self, n):
        """How reliable a node is, in words: 'you said', 'Avy said', 'inferred, likely'."""
        if n["origin"] == "inferred":
            return f"inferred, {n['certainty'] or 'possible'}"
        return SAID_BY[n["origin"]]

    def things(self):
        """Current thing nodes, for matching names in text."""
        return self.rows("SELECT * FROM current WHERE shape = 'thing'")
