"""The one door: every change to knowledge and the network goes through apply().

Each proposal is checked against the rules (rules.py) at the moment of writing, then saved in one
transaction, or refused. Either way it goes in the journal, with the rule it broke if it was refused.
DeepSeek never writes to memory directly: the jobs in mind/ turn its answers into proposals.

Proposals (plain dicts):
    {"op": "add_node", "shape", "label", "title", "text", "about", "evidence": [(message, start, end, exact)],
     "basis": [chain], "certainty", "replaces": chain or None, "episode", "why", "ref": "n1"}
    {"op": "retract_node", "chain", "why", "evidence": [...] (needed for what was said)}
    {"op": "connect", "a", "b", "kind", "reason", "support": {"kind", "sign", "source", "note"}, "quote": (message, start, end)}
    {"op": "oppose", "edge", "support": {"kind", "source", "note"}}
    {"op": "revise_edge", "edge", "kind", "reason", "why"}
    {"op": "reaffirm", "chain"} or {"op": "reaffirm", "edge"}      (checked again: still holds)
    {"op": "add_episode", "first", "last", "headline"}
In apply_all, a proposal can refer to a node made earlier in the same batch by its ref ("n1").
"""

import json
import re

from . import rules
from .common import stamp


class Ops:

    def apply_all(self, ops, run=None):
        """Apply proposals in order. Returns (results, refs): refs maps "n1" to the node it became."""
        refs, results = {}, []
        for op in ops:
            op, missing = self._resolve(op, refs)
            if missing:
                results.append(self._journal(run, op, None, f"{missing} wasn't saved, so this can't refer to it."))
                continue
            result = self.apply(op, run)
            if result["applied"] and op.get("ref") and result.get("chain"):
                refs[op["ref"]] = result["chain"]
            if result["applied"] and result.get("episode"):
                refs["@episode"] = result["episode"]
            results.append(result)
        return results, refs

    def _resolve(self, op, refs):
        def one(v):
            if isinstance(v, str) and (re.fullmatch(r"n\d+", v) or v.startswith("@")):
                if v not in refs:
                    raise KeyError("the episode" if v.startswith("@") else v)
                return refs[v]
            return v
        try:
            op = dict(op)
            for key in ("a", "b", "replaces", "chain", "episode"):
                if key in op:
                    op[key] = one(op[key])
            if op.get("basis"):
                op["basis"] = [one(v) for v in op["basis"]]
            return op, None
        except KeyError as e:
            return op, e.args[0]

    def apply(self, op, run=None):
        """Check one proposal against the rules and save it, or refuse it. Always journaled."""
        kind = op.get("op")
        try:
            handler = getattr(self, f"_op_{kind}")
        except AttributeError:
            return self._journal(run, op, None, f"unknown operation {kind!r}")
        with self.lock:
            return handler(op, run)

    def _journal(self, run, op, target, why, db=None):
        args = {k: v for k, v in op.items() if k not in ("op",)}
        row = (stamp(), run, op.get("op", "?"), target, json.dumps(args, default=str), "rejected" if why else "applied", why)
        sql = "INSERT INTO journal (at, run, op, target, args, result, why) VALUES (?, ?, ?, ?, ?, ?, ?)"
        if db is not None:
            db.execute(sql, row)
        else:
            with self.tx() as d:
                d.execute(sql, row)
        return {"applied": not why, "why": why, "op": op.get("op"), "target": target, "ref": op.get("ref")}

    # --- knowledge --------------------------------------------------------------------------

    def _op_add_node(self, op, run):
        why, d = rules.check_node(self, op)
        if why:
            return self._journal(run, op, self.handle(op["replaces"]) if op.get("replaces") else op.get("ref"), why)
        at = stamp()
        with self.tx() as db:
            nid = db.execute(
                """INSERT INTO nodes (chain, version, replaces, state, shape, label, title, text, about, origin,
                                      certainty, depth, why, episode, run, at)
                   VALUES (0, ?, ?, 'active', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (d["version"], d["replaces_row"], op["shape"], str(op.get("label") or "")[:40].strip(), d["title"], d["text"],
                 op.get("about"), d["origin"], d["certainty"], d["depth"], op.get("why"), op.get("episode"), run, at)).lastrowid
            chain = d["chain"] or nid
            db.execute("UPDATE nodes SET chain = ? WHERE id = ?", (chain, nid))
            for mid, start, end, exact in op.get("evidence") or []:
                quote = db.execute("SELECT substr(text, ?, ?) FROM messages WHERE id = ?", (start + 1, end - start, mid)).fetchone()[0]
                db.execute("INSERT OR IGNORE INTO evidence (node, message, start, end, quote, exact) VALUES (?, ?, ?, ?, ?, ?)",
                           (nid, mid, start, end, quote, int(exact)))
            for h in d.get("heads") or []:
                db.execute("INSERT OR IGNORE INTO basis (node, rests_on, seen) VALUES (?, ?, ?)", (nid, h["chain"], h["id"]))
            n = dict(db.execute("SELECT * FROM nodes WHERE id = ?", (nid,)).fetchone())
            db.execute("INSERT INTO words (text, item) VALUES (?, ?)", (self.node_words(n), f"v{nid}"))
            result = self._journal(run, {**op, "title": d["title"]}, self.handle(chain), None, db)
        self.remember_meaning([(f"v{nid}", self.node_words(n))])
        return {**result, "chain": chain, "id": nid, "version": d["version"], "origin": d["origin"]}

    def _op_retract_node(self, op, run):
        why = rules.check_retract(self, op)
        if why:
            return self._journal(run, op, self.handle(op.get("chain")), why)
        h = self.head(op["chain"])
        with self.tx() as db:
            nid = db.execute(
                """INSERT INTO nodes (chain, version, replaces, state, shape, label, title, text, about, origin,
                                      certainty, depth, why, episode, run, at)
                   VALUES (?, ?, ?, 'retracted', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (h["chain"], h["version"] + 1, h["id"], h["shape"], h["label"], h["title"], h["text"], h["about"],
                 h["origin"], h["certainty"], h["depth"], op["why"], op.get("episode"), run, stamp())).lastrowid
            for mid, start, end, exact in op.get("evidence") or []:
                quote = db.execute("SELECT substr(text, ?, ?) FROM messages WHERE id = ?", (start + 1, end - start, mid)).fetchone()[0]
                db.execute("INSERT OR IGNORE INTO evidence (node, message, start, end, quote, exact) VALUES (?, ?, ?, ?, ?, ?)",
                           (nid, mid, start, end, quote, int(exact)))
            result = self._journal(run, op, self.handle(h["chain"]), None, db)
        return {**result, "chain": h["chain"], "id": nid}

    # --- the network ------------------------------------------------------------------------

    def _op_connect(self, op, run):
        why, existing = rules.check_connect(self, op)
        a, b = op.get("a"), op.get("b")
        if why:
            return self._journal(run, op, None, why)
        support = {"sign": 1, "source": f"run {run}" if run else None, "note": None, **op["support"]}
        reason = " ".join(str(op["reason"]).split())
        if op["kind"] not in ("part_of", "builds_on") and a > b:
            a, b = b, a                                   # goes both ways: stored in one order
        at = stamp()
        with self.tx() as db:
            ha, hb = self.head(a)["id"], self.head(b)["id"]
            if existing:
                eid = existing["id"]
                if support["kind"] in ("stated", "confirmed") and (existing["kind"], existing["reason"]) != (op["kind"], reason):
                    db.execute("UPDATE edges SET kind = ?, reason = ?, a = ?, b = ? WHERE id = ?", (op["kind"], reason, a, b, eid))
                    self._index_reason(db, eid, reason)
            else:
                eid = db.execute("INSERT INTO edges (a, b, kind, reason, a_seen, b_seen, run, at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                                 (a, b, op["kind"], reason, ha, hb, run, at)).lastrowid
                self._index_reason(db, eid, reason)
            db.execute("INSERT INTO supports (edge, sign, kind, source, note, run, at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                       (eid, support["sign"], support["kind"], support["source"], support["note"], run, at))
            result = self._journal(run, {**op, "a": a, "b": b}, f"c{eid}", None, db)
        if not existing:
            self.remember_meaning([(f"c{eid}", reason)])
        return {**result, "edge": eid, "new": not existing}

    def _op_oppose(self, op, run):
        why = rules.check_edge(self, op)
        support = op.get("support") or {}
        if not why and support.get("kind") not in ("stated", "confirmed", "inferred", "observed", "used"):
            why = f"unknown support {support!r}."
        if why:
            return self._journal(run, op, f"c{op.get('edge')}", why)
        with self.tx() as db:
            db.execute("INSERT INTO supports (edge, sign, kind, source, note, run, at) VALUES (?, -1, ?, ?, ?, ?, ?)",
                       (op["edge"], support["kind"], support.get("source") or (f"run {run}" if run else None),
                        support.get("note"), run, stamp()))
            return self._journal(run, op, f"c{op['edge']}", None, db)

    def _op_revise_edge(self, op, run):
        why = rules.check_edge(self, op)
        if why:
            return self._journal(run, op, f"c{op.get('edge')}", why)
        e = self.edge(op["edge"])
        kind = op.get("kind") or e["kind"]
        reason = " ".join(str(op.get("reason") or e["reason"]).split())
        with self.tx() as db:
            db.execute("UPDATE edges SET kind = ?, reason = ?, a_seen = ?, b_seen = ? WHERE id = ?",
                       (kind, reason, self.head(e["a"])["id"], self.head(e["b"])["id"], e["id"]))
            self._index_reason(db, e["id"], reason)
            result = self._journal(run, {**op, "was": {"kind": e["kind"], "reason": e["reason"]}}, f"c{e['id']}", None, db)
        self.remember_meaning([(f"c{e['id']}", reason)])
        return result

    def _op_reaffirm(self, op, run):
        """Checked again and still holds: record that it's been checked against the newest versions."""
        if op.get("edge") is not None:
            why = rules.check_edge(self, op)
            if why:
                return self._journal(run, op, f"c{op.get('edge')}", why)
            e = self.edge(op["edge"])
            with self.tx() as db:
                db.execute("UPDATE edges SET a_seen = ?, b_seen = ? WHERE id = ?",
                           (self.head(e["a"])["id"], self.head(e["b"])["id"], e["id"]))
                return self._journal(run, {**op, "was": [e["a_seen"], e["b_seen"]]}, f"c{e['id']}", None, db)
        h = self.current(op.get("chain"))
        if not h:
            return self._journal(run, op, self.handle(op.get("chain")), "isn't a current node.")
        with self.tx() as db:
            was = [dict(r) for r in db.execute("SELECT rests_on, seen FROM basis WHERE node = ?", (h["id"],))]
            for b in was:
                now_head = self.head(b["rests_on"])
                if now_head and now_head["state"] == "active":
                    db.execute("UPDATE basis SET seen = ? WHERE node = ? AND rests_on = ?", (now_head["id"], h["id"], b["rests_on"]))
            return self._journal(run, {**op, "was": was}, self.handle(h["chain"]), None, db)

    def _index_reason(self, db, eid, reason):
        db.execute("DELETE FROM words WHERE item = ?", (f"c{eid}",))
        db.execute("INSERT INTO words (text, item) VALUES (?, ?)", (reason, f"c{eid}"))

    # --- episodes ---------------------------------------------------------------------------

    def _op_add_episode(self, op, run):
        why = rules.check_episode(self, op)
        if why:
            return self._journal(run, op, None, why)
        headline = " ".join(str(op["headline"]).split())[:160]
        with self.tx() as db:
            eid = db.execute("INSERT INTO episodes (first, last, headline, at, run) VALUES (?, ?, ?, ?, ?)",
                             (op["first"], op["last"], headline, stamp(), run)).lastrowid
            db.execute("INSERT INTO words (text, item) VALUES (?, ?)", (headline, f"e{eid}"))
            result = self._journal(run, op, f"ep{eid}", None, db)
        self.remember_meaning([(f"e{eid}", headline)])
        return {**result, "episode": eid}

    # --- bookkeeping (not knowledge, so not journaled) ----------------------------------------

    def save_run(self, **run):
        """Record one model job: what it was shown, what it answered, what the checks found."""
        run.setdefault("at", stamp())
        for name in ("prompt", "replies", "problems"):
            run[name] = json.dumps(run.get(name), default=str)
        names = ", ".join(run)
        with self.tx() as db:
            return db.execute(f"INSERT INTO runs ({names}) VALUES ({', '.join('?' * len(run))})", tuple(run.values())).lastrowid

    def record_judged(self, pairs, run):
        """Remember which pairs the model looked at, so they aren't asked about again
        (unless one of them gets a new version). pairs: [(a, b, connect)]."""
        at = stamp()
        with self.tx() as db:
            for a, b, connect in pairs:
                a, b = min(a, b), max(a, b)
                ha, hb = self.head(a), self.head(b)
                if ha and hb:
                    db.execute("INSERT OR REPLACE INTO judged (a, b, a_seen, b_seen, connect, run, at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                               (a, b, ha["id"], hb["id"], int(connect), run, at))

    def was_judged(self, a, b):
        a, b = min(a, b), max(a, b)
        j = self.row("SELECT * FROM judged WHERE a = ? AND b = ?", a, b)
        if not j:
            return False
        ha, hb = self.head(a), self.head(b)
        return bool(ha and hb and ha["id"] == j["a_seen"] and hb["id"] == j["b_seen"])
