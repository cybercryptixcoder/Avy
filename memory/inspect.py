"""Looking under the hood: what the page's inspector (and the graph view) ask for."""

import json
from datetime import datetime

from .common import clip, now
from .embed import embedder
from .network import LIVE


def _when(at):
    """A time (ISO; a stored one has its offset, a given one may end in Z or have none) as something comparable
    across offsets. One with no offset is taken as local time."""
    t = datetime.fromisoformat(str(at).strip().replace("Z", "+00:00"))
    return t if t.tzinfo else t.astimezone()


class Inspect:

    def stats(self):
        written = self.written_up_to()
        return {
            "memory": self.name,
            "letter": self.letter,
            "messages": self.last_id(),
            "episodes": self.value("SELECT COUNT(*) FROM episodes"),
            "nodes": self.value("SELECT COUNT(*) FROM current"),
            "inferred": self.value("SELECT COUNT(*) FROM current WHERE origin = 'inferred'"),
            "ideas": self.value("SELECT COUNT(*) FROM current WHERE shape = 'idea'"),
            "versions": self.value("SELECT COUNT(*) FROM nodes"),
            "connections": len(self.live_edges()),
            "written_to": written,
            "waiting_import": self.waiting_import(),
            "waiting": self.last_id() - written,
            "failed_runs": self.value("SELECT COUNT(*) FROM (SELECT status FROM runs ORDER BY id DESC LIMIT 20) "
                                      "WHERE status IN ('failed', 'error')"),
            "reflections": self.value("SELECT COUNT(*) FROM runs WHERE job IN ('connect', 'think', 'check')"),
            "thoughts": self.value("SELECT COUNT(*) FROM reasoning"),
            "mb": round(sum(p.stat().st_size for p in self.path.parent.glob(self.path.name + "*")) / 1e6, 2),
            "meaning": embedder.status,
            "file": str(self.path.resolve()),
        }

    def log_slice(self, before=None, after=None, limit=60):
        """Messages for the chat history and the inspector's log view, oldest first."""
        if after is not None:
            found = self.rows("SELECT * FROM messages WHERE id > ? ORDER BY id LIMIT ?", after, limit)
        else:
            found = self.rows("SELECT * FROM messages WHERE id < ? ORDER BY id DESC LIMIT ?", before or self.last_id() + 1, limit)[::-1]
        for m in found:
            m["meta"] = json.loads(m["meta"])
            if m["meta"].get("recall"):
                r = self.row("SELECT trace FROM recalls WHERE id = ?", m["meta"]["recall"])
                t = json.loads(r["trace"]) if r else {}
                m["recalled"] = {"id": m["meta"]["recall"], "memory": self.name, "nodes": len(t.get("nodes", [])),
                                 "log": len(t.get("log", [])), "explored": bool(t.get("explore"))}
            if m["role"] == "assistant" and m["meta"].get("thought"):     # what she thought before this reply
                r = self.reasoning_of(m["id"])
                if r:
                    m["thinking"] = {"text": r["text"], "seconds": r["seconds"], "effort": r["effort"], "tokens": r["tokens"]}
            if m["role"] == "assistant":                                   # what her tools did while she answered
                asked = self.value("SELECT MAX(id) FROM messages WHERE id < ? AND role = 'user'", m["id"])
                done = self.rows("SELECT tool, line, seconds, substr(result, 1, 700) AS out FROM actions WHERE asked = ? ORDER BY id", asked) if asked else []
                if done:
                    m["steps"] = done
            ep = self.row("SELECT id, headline FROM episodes WHERE ? BETWEEN first AND last", m["id"])
            m["episode"] = ep["id"] if ep else None
            m["headline"] = ep["headline"] if ep else None
            m["cited_by"] = [self.handle(r["chain"]) for r in self.rows(
                "SELECT DISTINCT n.chain FROM evidence v JOIN nodes n ON n.id = v.node WHERE v.message = ?", m["id"])]
        return found

    def node_brief(self, n):
        return {"chain": n["chain"], "handle": self.handle(n["chain"]), "title": n["title"], "shape": n["shape"],
                "label": n["label"], "origin": n["origin"], "speaker": self.speaker(n), "certainty": n["certainty"],
                "version": n["version"], "state": n["state"]}

    def node_record(self, chain, version=None):
        """A node as a wiki page: what it says, where it came from, what it connects to, every version."""
        h = self.head(chain)
        if not h:
            return None
        versions = []
        for v in self.versions(chain):
            versions.append({**v, "speaker": self.speaker(v), "evidence": self.evidence_of(v["id"]), "basis": [
                {"handle": self.handle(b["chain"]), "chain": b["chain"], "title": b["now"]["title"] if b["now"] else "?",
                 "standing": self.standing(b["now"]) if b["now"] else "", "stale": b["stale"]} for b in self.basis_of(v["id"])]})
        shown = next((v for v in versions if v["version"] == version), versions[0]) if version else versions[0]
        links = []
        for l in self.links(chain, live_only=False):
            o = self.head(l["other"])
            links.append({"edge": l["edge"], "kind": l["kind"], "direction": l["direction"], "reason": l["reason"],
                          "strength": l["strength"], "live": l["strength"] >= LIVE and o["state"] == "active",
                          "other": self.node_brief(o), "supports": len(l["supports"]),
                          "stated": any(s["kind"] in ("stated", "confirmed") and s["sign"] > 0 for s in l["supports"])})
        links.sort(key=lambda l: (not l["live"], -l["strength"]))
        rests = [self.node_brief(r) for r in self.dependents(chain)]
        episode = self.episode(h["episode"]) if h["episode"] else None
        changes = self.rows("SELECT * FROM journal WHERE target = ? ORDER BY id DESC LIMIT 30", self.handle(chain))
        for c in changes:
            c["args"] = json.loads(c["args"])
        return {"node": {**shown, "handle": self.handle(chain), "standing": self.standing(shown)}, "head": h["id"],
                "versions": versions, "links": links, "inferred_from_this": rests, "episode": episode,
                "journal": changes, "memory": self.name}

    def edge_record(self, eid):
        e = self.edge(eid)
        if not e:
            return None
        supports = self.supports_of(eid)
        history, running = [], []
        for s in supports:
            running.append(s)
            from .network import strength_of
            history.append({**s, "strength_after": strength_of(e, running, s["at"])})
        changes = self.rows("SELECT * FROM journal WHERE target = ? ORDER BY id", f"c{eid}")
        for c in changes:
            c["args"] = json.loads(c["args"])
        return {"edge": {**e, "strength": self.strength(eid)}, "a": self.node_brief(self.head(e["a"])),
                "b": self.node_brief(self.head(e["b"])), "supports": history, "journal": changes, "live_at": LIVE,
                "memory": self.name}

    def episodes_list(self, limit=400):
        return self.rows("""SELECT p.*, (SELECT COUNT(*) FROM nodes WHERE episode = p.id) AS n,
                                   r.status, r.attempts FROM episodes p LEFT JOIN runs r ON r.id = p.run
                            ORDER BY p.id DESC LIMIT ?""", limit)

    def episode_record(self, eid):
        p = self.episode(eid)
        if not p:
            return None
        made = self.rows("SELECT * FROM nodes WHERE episode = ? ORDER BY id", eid)
        heads = {r["chain"]: r["id"] for r in self.rows("SELECT chain, id FROM heads")}
        made = [{**self.node_brief(n), "current": heads.get(n["chain"]) == n["id"]} for n in made]
        return {"episode": p, "nodes": made, "run": self.run_record(p["run"]) if p["run"] else None, "memory": self.name}

    def runs_list(self, jobs=None, limit=100):
        if jobs:
            return self.rows(f"SELECT id, job, at, status, attempts, cost, focus FROM runs WHERE job IN ({','.join('?' * len(jobs))}) "
                             "ORDER BY id DESC LIMIT ?", *jobs, limit)
        return self.rows("SELECT id, job, at, status, attempts, cost, focus FROM runs ORDER BY id DESC LIMIT ?", limit)

    def run_record(self, rid):
        run = self.row("SELECT * FROM runs WHERE id = ?", rid)
        if not run:
            return None
        for name in ("prompt", "replies", "problems"):
            run[name] = json.loads(run[name]) if run[name] else None
        changes = self.rows("SELECT * FROM journal WHERE run = ? ORDER BY id", rid)
        for c in changes:
            c["args"] = json.loads(c["args"])
        return {**run, "journal": changes}

    def recall_record(self, rid):
        r = self.row("SELECT * FROM recalls WHERE id = ?", rid)
        if r:
            r["trace"] = json.loads(r["trace"])
        return r

    def find(self, text):
        """The inspector's search: current nodes and log messages, closest first (both halves of search)."""
        queries = [(text, 1.0, embedder.query(text))]
        hits = self.land(queries)
        floor = 0.5 if embedder.ready else 0.01
        nodes = []
        for c in sorted(hits, key=lambda c: -hits[c]["score"])[:25]:
            if hits[c]["score"] < floor:
                break
            n = self.current(c)
            nodes.append({**self.node_brief(n), "text": n["text"], "how": hits[c]["how"], "score": round(hits[c]["score"], 3)})
        msgs = self.relevance(queries, "m")
        found_msgs = []
        for item in sorted(msgs, key=lambda i: -msgs[i]["score"])[:20]:
            if msgs[item]["score"] < floor:
                break
            m = self.message(int(item[1:]))
            found_msgs.append({"id": m["id"], "at": m["at"], "role": m["role"], "text": clip(m["text"], 0, 300),
                               "how": msgs[item]["how"], "score": round(msgs[item]["score"], 3)})
        return {"nodes": nodes, "messages": found_msgs}

    def graph_data(self, as_of=None):
        """Every current node and live connection, for the graph view.

        as_of (an ISO time): memory as it stood then, built from what's kept (nothing is ever deleted): each
        node's newest version written by that time, unless it had been retracted by then; the connections that
        existed and were strong enough then (strength recomputed from the supports up to then, with the fading
        measured to then), with the kind and reason they had then (replayed from the journal)."""
        when = _when(as_of) if as_of else None
        if when:
            heads = {}
            for n in self.rows("SELECT * FROM nodes ORDER BY chain, version"):
                if _when(n["at"]) <= when:
                    heads[n["chain"]] = n
            nodes = [n for n in heads.values() if n["state"] == "active"]
            alive = {n["chain"] for n in nodes}
            edges = [e for e in self.rows("SELECT * FROM edges") if _when(e["at"]) <= when and e["a"] in alive and e["b"] in alive]
            edges = [e for e in self._with_strength(edges, when) if e["strength"] >= LIVE]
            self._edges_as_of(edges, when)
            ids = [n["id"] for n in nodes]
            basis = self.rows(f"""SELECT n.chain, b.rests_on FROM basis b JOIN nodes n ON n.id = b.node
                                  WHERE b.node IN ({",".join("?" * len(ids))}) AND n.origin = 'inferred'""", *ids) if ids else []
            basis = [b for b in basis if b["rests_on"] in alive]
        else:
            nodes = self.current_nodes()
            edges = self.live_edges()
            basis = self.rows("""SELECT c.chain, b.rests_on FROM current c JOIN basis b ON b.node = c.id WHERE c.origin = 'inferred'""")
        degree = {}
        for e in edges:
            degree[e["a"]] = degree.get(e["a"], 0) + 1
            degree[e["b"]] = degree.get(e["b"], 0) + 1
        born = {r["chain"]: r["at"] for r in self.rows("SELECT chain, at FROM nodes WHERE version = 1")}
        times = [r["at"] for r in self.rows("SELECT at FROM nodes UNION ALL SELECT at FROM supports")]
        first = min(times, key=_when) if times else None
        last = max(times, key=_when) if times else None
        return {
            "memory": self.name, "letter": self.letter, "as_of": as_of,
            "span": {"first": first, "last": last, "now": now().isoformat(timespec="seconds")},
            "nodes": [{**self.node_brief(n), "text": n["text"][:240], "degree": degree.get(n["chain"], 0), "at": n["at"],
                       "born": born.get(n["chain"], n["at"])} for n in nodes],
            "edges": [{"id": e["id"], "a": e["a"], "b": e["b"], "kind": e["kind"], "reason": e["reason"],
                       "strength": e["strength"]} for e in edges],
            "rests": [{"a": r["chain"], "b": r["rests_on"]} for r in basis],
        }

    def _edges_as_of(self, edges, when):
        """Give each edge the kind and reason it had at `when`. An edge's kind and reason can be rewritten later
        (Check revises them; something he says outright overrides the model), and the journal keeps every
        applied change with its arguments, so replaying it up to `when` gives what it said then."""
        if not edges:
            return
        targets = [f"c{e['id']}" for e in edges]
        said = {}
        for j in self.rows(f"""SELECT * FROM journal WHERE result = 'applied' AND op IN ('connect', 'revise_edge')
                               AND target IN ({",".join("?" * len(targets))}) ORDER BY id""", *targets):
            if _when(j["at"]) > when:
                continue
            a = json.loads(j["args"])
            eid = int(j["target"][1:])
            was = said.get(eid)
            if j["op"] == "connect" and (was is None or (a.get("support") or {}).get("kind") in ("stated", "confirmed")):
                said[eid] = (a.get("kind") or (was or ("related", ""))[0], " ".join(str(a.get("reason") or "").split()) or (was or ("", ""))[1])
            elif j["op"] == "revise_edge" and was is not None:
                said[eid] = (a.get("kind") or was[0], " ".join(str(a.get("reason") or "").split()) or was[1])
        for e in edges:
            if e["id"] in said:
                e["kind"], e["reason"] = said[e["id"]]

    def journal_list(self, limit=200):
        found = self.rows("SELECT * FROM journal ORDER BY id DESC LIMIT ?", limit)
        for c in found:
            c["args"] = json.loads(c["args"])
        return found
