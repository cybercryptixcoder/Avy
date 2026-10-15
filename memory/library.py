"""The library: what Shreyas added that wasn't said in this conversation (documents, papers, code, data,
recordings, conversations from elsewhere), kept word for word as passages, in order, like the log.

    sid = mem.add_source("ingester-design.md", "document", came="f20261015-...")
    mem.add_passages(sid, [{"text": "...", "part": "## Retries"}, ...])     # searchable by words at once
    mem.finish_source(sid, meta={...})                                       # stored; meaning vectors follow
    mem.library_hits(queries, ...)                                           # recall's and explore's way in

Passages are handled like the log: append-only, searchable by words (FTS5) and by meaning (vectors, item
p41), and recall brings back the ones that match by themselves, in their own section of the memory note.
Writing knowledge from them (nodes citing passages, the way nodes cite messages) is the next step, and it
waits on a decision of Shreyas's (ARCHITECTURE.md, "The library").
"""

import hashlib
import json

from .common import clip, stamp, tokens, when
from .search import top_score

PASSAGE_SHOWN = 900       # how much of one passage the memory note shows


class Sources:

    # --- adding ------------------------------------------------------------------------------------
    def add_source(self, name, kind, came=None, digest=None, meta=None):
        with self.tx() as db:
            return db.execute("INSERT INTO sources (name, kind, added, came, digest, status, meta) VALUES (?, ?, ?, ?, ?, 'reading', ?)",
                              (name, kind, stamp(), came, digest, json.dumps(meta or {}))).lastrowid

    def add_passages(self, sid, passages):
        """Append passages (dicts with text, and maybe part, speaker, role, at) in order. Returns their ids.
        Searchable by words at once; meaning vectors are added by embed_passages (slow, so it's separate)."""
        ids = []
        with self.tx() as db:
            seq = db.execute("SELECT COALESCE(MAX(seq), 0) FROM passages WHERE source = ?", (sid,)).fetchone()[0]
            for p in passages:
                text = (p.get("text") or "").strip()
                if not text:
                    continue
                seq += 1
                pid = db.execute("INSERT INTO passages (source, seq, part, speaker, role, at, text) VALUES (?, ?, ?, ?, ?, ?, ?)",
                                 (sid, seq, p.get("part"), p.get("speaker"), p.get("role"), p.get("at"), text)).lastrowid
                db.execute("INSERT INTO words (text, item) VALUES (?, ?)", (self.passage_words(p, text), f"p{pid}"))
                ids.append(pid)
        return ids

    def passage_words(self, p, text):
        """What search sees for a passage: where it is in its source, then the words."""
        return (f"{p.get('part')}: " if p.get("part") else "") + text

    def embed_passages(self, ids, batch=32, progress=None):
        """Meaning vectors for passages (the slow part of adding a big source). progress(done) after each batch."""
        done = 0
        for i in range(0, len(ids), batch):
            chunk = ids[i:i + batch]
            rows = self.rows(f"SELECT * FROM passages WHERE id IN ({','.join('?' * len(chunk))})", *chunk)
            self.remember_meaning([(f"p{r['id']}", self.passage_words(r, r["text"])) for r in rows])
            done += len(chunk)
            if progress:
                progress(done)
        return done

    def finish_source(self, sid, status="stored", meta=None):
        with self.tx() as db:
            if meta is not None:
                old = json.loads(db.execute("SELECT meta FROM sources WHERE id = ?", (sid,)).fetchone()[0] or "{}")
                db.execute("UPDATE sources SET meta = ? WHERE id = ?", (json.dumps({**old, **meta}), sid))
            db.execute("UPDATE sources SET status = ? WHERE id = ?", (status, sid))

    def source_with_digest(self, digest):
        return self.row("SELECT * FROM sources WHERE digest = ? AND status != 'problem'", digest) if digest else None

    # --- reading -------------------------------------------------------------------------------------
    def source(self, sid):
        s = self.row("SELECT * FROM sources WHERE id = ?", sid)
        if s:
            s["meta"] = json.loads(s["meta"] or "{}")
            s["passages"] = self.value("SELECT COUNT(*) FROM passages WHERE source = ?", sid) or 0
            s["chars"] = self.value("SELECT COALESCE(SUM(LENGTH(text)), 0) FROM passages WHERE source = ?", sid) or 0
        return s

    def sources_list(self, limit=200):
        found = self.rows("""SELECT s.*, COUNT(p.id) AS passages, COALESCE(SUM(LENGTH(p.text)), 0) AS chars
                             FROM sources s LEFT JOIN passages p ON p.source = s.id GROUP BY s.id ORDER BY s.id DESC LIMIT ?""", limit)
        for s in found:
            s["meta"] = json.loads(s["meta"] or "{}")
            s["embedded"] = sum(1 for pid in self.passage_ids(s["id"]) if f"p{pid}" in (self.shelves.get("p").where if self.shelves.get("p") else {}))
        return found

    def passage_ids(self, sid):
        return [r["id"] for r in self.rows("SELECT id FROM passages WHERE source = ? ORDER BY seq", sid)]

    def passage(self, pid):
        p = self.row("SELECT p.*, s.name AS source_name, s.kind AS source_kind FROM passages p JOIN sources s ON s.id = p.source WHERE p.id = ?", pid)
        return p

    def passages_of(self, sid, after=0, limit=40):
        return self.rows("SELECT * FROM passages WHERE source = ? AND seq > ? ORDER BY seq LIMIT ?", sid, after, limit)

    def library_stats(self):
        return {"sources": self.value("SELECT COUNT(*) FROM sources") or 0,
                "passages": self.value("SELECT COUNT(*) FROM passages") or 0,
                "reading": self.value("SELECT COUNT(*) FROM sources WHERE status = 'reading'") or 0}

    # --- what memory brings back ----------------------------------------------------------------------
    def passage_block(self, p):
        """One passage, the way the model sees it: its handle, its source and where in it, then its words."""
        bits = [f'from "{p["source_name"]}"']
        if p.get("part"):
            bits.append(p["part"])
        if p.get("speaker"):
            who_ = "Shreyas" if p.get("role") == "user" else p["speaker"]
            bits.append(f"{who_} said" + (f", {when(p['at'])}" if p.get("at") else ""))
        elif p.get("at"):
            bits.append(when(p["at"]))
        return f"[p{p['id']}] ({'; '.join(bits)}): {clip(p['text'], 0, PASSAGE_SHOWN)}"

    def library_hits(self, queries, words=True, meaning=True, k=30):
        """Passages close to the text: {pid: hit}."""
        return {int(item[1:]): hit for item, hit in self.relevance(queries, "p", k, words, meaning).items()}

    def library_net(self, queries, level, words, meaning, floor, used):
        """Passages that match by themselves (the library's safety net, like older messages). Returns (lines, used, skipped, hits)."""
        if not self.value("SELECT 1 FROM passages LIMIT 1"):
            return [], used, 0, 0
        hits = self.library_hits(queries, words, meaning)
        best = top_score(hits.values())
        bar = max(floor, best - level["near"], floor + (0.02 if meaning else 0.1))
        lines, skipped = [], 0
        for pid in sorted(hits, key=lambda x: -hits[x]["score"]):
            if hits[pid]["score"] < bar or len(lines) >= level["log"]:
                break
            block = self.passage_block(self.passage(pid))
            if used + tokens(block) > level["tokens"]:
                skipped += 1
                continue
            used += tokens(block)
            lines.append({"passage": pid, "memory": self.name, "how": hits[pid]["how"], "score": round(hits[pid]["score"], 3), "block": block})
        return lines, used, skipped, len(hits)


def digest_of(chunks):
    """A short hash of what a source holds (its passages' words, in order)."""
    h = hashlib.sha256()
    for c in chunks:
        h.update((c.get("text") or "").encode("utf-8", "replace"))
        h.update(b"\x00")
    return h.hexdigest()[:24]
