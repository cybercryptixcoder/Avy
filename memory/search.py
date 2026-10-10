"""Search: how close each item is to some text, by meaning and by shared words.

The score is on a fixed scale from 0 to 1, so "nothing matches" is a possible answer (a ranking
alone can't say that):
    meaning   the meaning-search similarity (unrelated things land around 0.4 to 0.55)
    words     the share of the text's words an item contains, rare words counting more
    score     meaning + a small bonus for shared words; with meaning search off: words alone

Either half can be switched off (/meaning: and /words:), to see what each one contributes.

Items: m41 a message, v77 a node version, e4 an episode headline, c7 a connection's reason.
"""

import math

from .common import terms
from .embed import EMBED_MODEL, KINDS, Shelf, embedder

ECHO = 0.93     # closer than this, it's the same thing said again (a question asked before), not an answer


class Search:

    def load_vectors(self):
        """Once the model is ready: load saved vectors, and embed anything saved before it was."""
        np = embedder.np
        shelves = {kind: Shelf(np) for kind in KINDS}
        for r in self.rows("SELECT item, vec FROM vectors WHERE model = ?", EMBED_MODEL):
            if r["item"][0] in shelves:
                shelves[r["item"][0]].put(r["item"], np.frombuffer(r["vec"], np.float32))
        self.shelves = shelves
        todo = [(f"m{r['id']}", r["text"]) for r in self.rows("SELECT id, text FROM messages")]
        todo += [(f"v{r['id']}", self.node_words(r)) for r in self.rows("SELECT * FROM nodes")]
        todo += [(f"e{r['id']}", r["headline"]) for r in self.rows("SELECT id, headline FROM episodes")]
        todo += [(f"c{r['id']}", r["reason"]) for r in self.rows("SELECT id, reason FROM edges")]
        todo = [(item, text) for item, text in todo if item not in shelves[item[0]].where]
        for i in range(0, len(todo), 64):
            self.remember_meaning(todo[i:i + 64])

    def remember_meaning(self, items):
        """Embed [(item, text)] and keep the vectors (no-op until the model is ready)."""
        if not embedder.ready or not self.shelves or not items or self.closed:
            return
        vecs = embedder.passages([text for _, text in items])
        with self.lock, self.db:
            if self.closed:
                return
            for (item, _), vec in zip(items, vecs):
                self.shelves[item[0]].put(item, vec)
                self.db.execute("INSERT OR REPLACE INTO vectors (item, model, vec) VALUES (?, ?, ?)",
                                (item, EMBED_MODEL, vec.tobytes()))

    def closest(self, vec, kind, k=30):
        shelf = self.shelves.get(kind)
        return shelf.closest(vec, k) if shelf and vec is not None else []

    def closeness(self, item, vec):
        """0 to 1. Unknown (no model, or not embedded yet) counts as middling."""
        shelf = self.shelves.get(item[0]) if vec is not None else None
        if not shelf or item not in shelf.where:
            return 0.5
        return max(0.0, float(shelf.data[shelf.where[item]] @ vec))

    def vector(self, item):
        shelf = self.shelves.get(item[0])
        return shelf.vector(item) if shelf else None

    def similarity(self, item_a, item_b):
        """How alike two stored items are in meaning (None without the model)."""
        va, vb = self.vector(item_a), self.vector(item_b)
        return None if va is None or vb is None else float(va @ vb)

    def word_scores(self, text, kind):
        """{item: share of the text's words it contains}, rare words weighted up (IDF), for one kind
        of item. Only items sharing at least one word are listed."""
        words = terms(text)
        if not words:
            return {}
        total = self.value("SELECT COUNT(*) FROM words WHERE item GLOB ?", f"{kind}*") or 1
        weight, has = {}, {}
        for w in words:
            items = [r["item"] for r in self.rows("SELECT item FROM words WHERE words MATCH ? AND item GLOB ?", f'"{w}"', f"{kind}*")]
            weight[w] = max(0.0, math.log((total + 1) / (len(items) + 0.5)))
            for item in items:
                has.setdefault(item, set()).add(w)
        whole = sum(weight.values()) or 1
        return {item: sum(weight[w] for w in ws) / whole for item, ws in has.items()}

    def relevance(self, queries, kind, k=40, words=True, meaning=True):
        """How close items of one kind are to the text. queries: [(text, weight, vector or None)].
        words / meaning: which halves of search to use. Returns {item: {"score", "meaning", "words", "how"}},
        the best match per item across the queries."""
        found = {}
        for text, weight, vec in queries:
            vec = vec if meaning else None
            closeness = dict(self.closest(vec, kind, k)) if vec is not None else {}
            shared = self.word_scores(text, kind) if words else {}
            for item in set(closeness) | set(shared):
                sim = closeness.get(item)
                if sim is None and vec is not None:
                    sim = self.closeness(item, vec)      # shares words but wasn't in the top k by meaning
                share = shared.get(item, 0.0)
                score = weight * ((sim + 0.15 * share) if vec is not None else share)
                if score > found.get(item, {}).get("score", -1):
                    how = "both" if share and closeness.get(item) else "words" if share else "meaning"
                    found[item] = {"score": score, "meaning": sim, "words": share, "how": how}
        return found


def top_score(hits):
    """The best match, ignoring echoes: an earlier copy of the same question is the closest thing to
    it, but it isn't an answer, so it mustn't raise the bar the real answers have to clear."""
    scores = [h["score"] for h in hits if (h.get("meaning") or 0) < ECHO and (h.get("meaning") is not None or h.get("words", 0) < 0.95)]
    return max(scores or [h["score"] for h in hits] or [0])
