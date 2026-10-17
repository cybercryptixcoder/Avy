"""The desk: what's always in view, every message. Small, fixed-size, never searched (ARCHITECTURE.md §7.2).

    slots      her character note, him, his preferences, her voice examples. Each change is a new version of
               the whole note (old versions kept); every item cites the messages it rests on.
    timeline   dated things (events, deadlines, reminders) and tasks: t12. Versioned like knowledge.
    threads    work in flight, each with its frontier (goal, where it stands, next step, what it waits on, the
               insights behind it): th3. Versioned.

Like the rest of memory, this never calls the model. Changes come through the one door (Memory.apply) as ops:

    {"op": "set_slot", "name", "items": [{id?, text, cites, ...}], "why", "by"}
    {"op": "timeline", "chain"?, "title", "kind", "start", "end", "status", "notes", "thread", "source", "quote", "by", "why"}
    {"op": "thread", "chain"?, "title", "status", "goal", "state", "next", "waiting", "insights" | "add_insights",
     "source", "by", "why"}

and the desk is read back as text for the model (slots_text, desk_note) and as data for the page (desk_data).
"""

import json
import re
from datetime import datetime, timedelta

from .common import NAME, clip, now, stamp, when
from .embed import embedder

# Each slot's fixed size. The budget is the point: the desk can't grow like a context window. What no longer
# fits has to be merged or dropped (it's still in the old versions, and in the log).
SLOTS = {
    "character":   {"items": 8,  "words": 220, "prefix": "ch", "title": "her character note"},
    "him":         {"items": 14, "words": 180, "prefix": "hm", "title": "him"},
    "preferences": {"items": 12, "words": 200, "prefix": "pr", "title": "his preferences"},
    "voice":       {"items": 6,  "words": None, "prefix": "vo", "title": "her voice"},
}
KINDS = ("event", "deadline", "reminder", "task")
STATUSES = ("planned", "done", "cancelled", "missed")
THREAD_STATUSES = ("active", "waiting", "paused", "done", "dropped")
OPEN_THREADS = ("active", "waiting", "paused")
VOICE_KINDS = ("technical", "planning", "ideas", "casual", "life", "other")
WHEN = re.compile(r"^\d{4}-\d{2}-\d{2}(T\d{2}:\d{2})?$")
AHEAD_DAYS = 14          # how far ahead "coming up" looks
OVERDUE_DAYS = 14        # planned things this far in the past still show, as overdue
MAX_INSIGHTS = 8


def words_in(text):
    return len(re.findall(r"\S+", text or ""))


def parse_when(value):
    """'2026-10-20' or '2026-10-20T15:00' -> (datetime at local midnight or that time, has_time). None if invalid."""
    value = (value or "").strip()
    if not WHEN.match(value):
        return None
    try:
        t = datetime.fromisoformat(value)
    except ValueError:
        return None
    return t.replace(tzinfo=now().tzinfo), "T" in value


def say_when(value, with_weekday=True):
    """'2026-10-20T15:00' -> 'Tue Oct 20, 3:00 PM'; '2026-10-20' -> 'Tue Oct 20'."""
    found = parse_when(value)
    if not found:
        return value or "no date"
    t, timed = found
    out = f"{t:%a %b} {t.day}" if with_weekday else f"{t:%b} {t.day}"
    if t.year != now().year:
        out += f" {t.year}"
    if timed:
        out += f", {t:%I:%M %p}".replace(", 0", ", ")
    return out


def ago(iso):
    """How long ago, in words: 'just now', '40 minutes ago', '3 hours ago', '2 days ago'."""
    minutes = (now() - datetime.fromisoformat(iso)).total_seconds() / 60
    if minutes < 2:
        return "just now"
    if minutes < 90:
        return f"{round(minutes)} minutes ago"
    if minutes < 36 * 60:
        return f"{round(minutes / 60)} hours ago"
    return f"{round(minutes / 1440)} days ago"


def similar_titles(a, b):
    """Two timeline titles that name the same thing ('dentist' / 'Dentist appointment')."""
    wa = set(re.findall(r"[a-z0-9]+", a.lower())) - {"the", "a", "an", "with", "to", "for", "of", "at", "my", "his"}
    wb = set(re.findall(r"[a-z0-9]+", b.lower())) - {"the", "a", "an", "with", "to", "for", "of", "at", "my", "his"}
    if not wa or not wb:
        return False
    return len(wa & wb) / min(len(wa), len(wb)) >= 0.6


class Desk:

    # --- slots ---------------------------------------------------------------------------------------

    def slot(self, name):
        """The current version of a slot: {name, version, items, why, by, at} (version 0: empty)."""
        row = self.row("SELECT * FROM slots WHERE name = ? ORDER BY version DESC LIMIT 1", name)
        if not row:
            return {"name": name, "version": 0, "items": [], "why": None, "by": None, "at": None}
        row["items"] = json.loads(row["items"])
        return row

    def slot_versions(self, name, limit=50):
        found = self.rows("SELECT * FROM slots WHERE name = ? ORDER BY version DESC LIMIT ?", name, limit)
        for r in found:
            r["items"] = json.loads(r["items"])
        return found

    def _op_set_slot(self, op, run):
        name = op.get("name")
        if name not in SLOTS:
            return self._journal(run, op, None, f"there's no slot called {name!r}")
        spec = SLOTS[name]
        items, problems = [], []
        current = self.slot(name)
        known = {i["id"] for v in self.slot_versions(name, 1000) for i in v["items"]}
        next_n = 1 + max([int(re.sub(r"\D", "", i)) for i in known if re.sub(r"\D", "", i)] or [0])
        for raw in op.get("items") or []:
            item, problem = self._slot_item(name, raw)
            if problem:
                problems.append(problem)
                continue
            if not item.get("id") or not re.fullmatch(rf"{spec['prefix']}\d+", item["id"]) or item["id"] in {i["id"] for i in items}:
                item["id"] = f"{spec['prefix']}{next_n}"
                next_n += 1
            items.append(item)
        if problems:
            return self._journal(run, op, name, "; ".join(problems))
        if len(items) > spec["items"]:
            return self._journal(run, op, name, f"{spec['title']} holds at most {spec['items']} items (got {len(items)}): merge or drop some")
        total = sum(words_in(i.get("text", "")) for i in items)
        if spec["words"] and total > spec["words"]:
            return self._journal(run, op, name, f"{spec['title']} holds at most {spec['words']} words (got {total}): say it shorter, merge, or drop")
        same = lambda xs: [(i.get("text"), i.get("message"), tuple(i.get("cites") or [])) for i in xs]
        if same(items) == same(current["items"]):
            result = self._journal(run, dict(op, unchanged=True), name, None)
            return {**result, "version": current["version"], "unchanged": True}
        version = current["version"] + 1
        with self.tx() as db:
            db.execute("INSERT INTO slots (name, version, items, why, by, run, at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                       (name, version, json.dumps(items, ensure_ascii=False), (op.get("why") or "")[:300],
                        op.get("by") or "mind", run, stamp()))
            self._journal(run, {**op, "items": items}, f"{name} v{version}", None, db)
        return {"op": "set_slot", "applied": True, "target": f"{name} v{version}", "version": version, "why": None}

    def _slot_item(self, name, raw):
        """One item, checked: (item, None) or (None, problem). Evidence is the rule: every item cites real messages,
        and what's said to be his (him, preferences) must rest on at least one of his own messages."""
        if not isinstance(raw, dict):
            return None, "an item wasn't an object"
        cites = []
        for c in raw.get("cites") or []:
            try:
                cites.append(int(str(c).strip().lstrip("#")))
            except ValueError:
                return None, f"{c!r} isn't a message number"
        cites = list(dict.fromkeys(cites))
        if name == "voice":
            try:
                mid = int(str(raw.get("message")).lstrip("#"))
            except (TypeError, ValueError):
                return None, "a voice example needs the number of her reply"
            m = self.row("SELECT role FROM messages WHERE id = ?", mid)
            if not m or m["role"] != "assistant":
                return None, f"#{mid} isn't one of her replies"
            kind = raw.get("kind") if raw.get("kind") in VOICE_KINDS else "other"
            return {"id": raw.get("id"), "message": mid, "kind": kind, "why": str(raw.get("why") or "")[:200],
                    "cites": cites or [mid]}, None
        text = " ".join(str(raw.get("text") or "").split())
        if not text:
            return None, "an item has no text"
        if not cites:
            return None, f"\"{clip(text, 0, 60)}\" cites no message: every line needs its evidence"
        roles = {r["id"]: r["role"] for r in self.rows(
            f"SELECT id, role FROM messages WHERE id IN ({','.join('?' * len(cites))})", *cites)}
        missing = [c for c in cites if c not in roles]
        if missing:
            return None, f"\"{clip(text, 0, 60)}\" cites #{missing[0]}, which doesn't exist"
        if name in ("him", "preferences") and "user" not in roles.values():
            return None, f"\"{clip(text, 0, 60)}\" must rest on something {NAME} said (it cites only Avy's replies)"
        item = {"id": raw.get("id"), "text": text, "cites": cites}
        for extra in ("scope", "quote"):
            if raw.get(extra):
                item[extra] = " ".join(str(raw[extra]).split())[:200]
        return item, None

    # --- the timeline -------------------------------------------------------------------------------

    def timeline_item(self, chain):
        return self.row("SELECT * FROM timeline WHERE chain = ? ORDER BY version DESC LIMIT 1", chain)

    def timeline_heads(self):
        """The newest version of every timeline item."""
        return self.rows("SELECT * FROM timeline t WHERE NOT EXISTS (SELECT 1 FROM timeline x WHERE x.replaces = t.id) "
                         "ORDER BY COALESCE(start, '9999'), chain")

    def timeline_versions(self, chain):
        return self.rows("SELECT * FROM timeline WHERE chain = ? ORDER BY version", chain)

    def same_timeline_item(self, title, start):
        """An item already on the timeline that's the same thing (same day, a similar title): adding it again
        would be a duplicate, so it becomes an update instead."""
        day = (start or "")[:10]
        for t in self.timeline_heads():
            if t["status"] != "cancelled" and (t["start"] or "")[:10] == day and similar_titles(t["title"], title):
                return t
        return None

    def _op_timeline(self, op, run):
        chain = op.get("chain")
        head = None
        if chain is not None:
            try:
                chain = int(str(chain).lstrip("tT"))
            except ValueError:
                return self._journal(run, op, None, f"{op.get('chain')!r} isn't a timeline item (they look like t12)")
            head = self.timeline_item(chain)
            if not head:
                return self._journal(run, op, f"t{chain}", f"there's no timeline item t{chain}")
        elif op.get("title") and op.get("start"):
            head = self.same_timeline_item(op["title"], op["start"])      # already there: update it instead
            chain = head["chain"] if head else None
        fields = {k: (head or {}).get(k) for k in ("title", "kind", "start", "end", "status", "notes", "thread", "source", "quote")}
        for k in fields:
            if op.get(k) not in (None, ""):
                fields[k] = op[k]
        if op.get("clear_end"):
            fields["end"] = None
        fields["title"] = " ".join(str(fields["title"] or "").split())[:140]
        fields["kind"] = fields["kind"] or "event"
        fields["status"] = fields["status"] or "planned"
        fields["notes"] = " ".join(str(fields["notes"] or "").split())[:500]
        target = f"t{chain}" if chain else None
        if not fields["title"]:
            return self._journal(run, op, target, "it needs a title")
        if fields["kind"] not in KINDS:
            return self._journal(run, op, target, f"kind must be one of {', '.join(KINDS)}")
        if fields["status"] not in STATUSES:
            return self._journal(run, op, target, f"status must be one of {', '.join(STATUSES)}")
        for k in ("start", "end"):
            if fields[k] and not parse_when(fields[k]):
                return self._journal(run, op, target, f"{k} must look like 2026-10-20 or 2026-10-20T15:00 (got {fields[k]!r})")
        if not fields["start"] and fields["kind"] != "task":
            return self._journal(run, op, target, "only a task can have no date")
        if fields["thread"] is not None:
            try:
                fields["thread"] = int(str(fields["thread"]).lower().lstrip("th"))
            except ValueError:
                return self._journal(run, op, target, f"{fields['thread']!r} isn't a thread (they look like th3)")
            if not self.thread(fields["thread"]):
                return self._journal(run, op, target, f"there's no thread th{fields['thread']}")
        if fields["source"] is not None and not self.row("SELECT id FROM messages WHERE id = ?", fields["source"]):
            fields["source"] = None
        if head and all(head.get(k) == v for k, v in fields.items()):
            return {**self._journal(run, dict(op, unchanged=True), target, None), "chain": chain, "unchanged": True}
        with self.tx() as db:
            row = db.execute("SELECT COALESCE(MAX(id), 0) + 1 FROM timeline").fetchone()[0]
            chain = chain or row          # a new item's handle is its first version's id (rows can't be updated later)
            db.execute("""INSERT INTO timeline (id, chain, version, replaces, title, kind, start, end, status, notes, thread,
                          source, quote, by, why, run, at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                       (row, chain, (head or {}).get("version", 0) + 1, (head or {}).get("id"), fields["title"], fields["kind"],
                        fields["start"], fields["end"], fields["status"], fields["notes"], fields["thread"],
                        fields["source"], fields["quote"], op.get("by") or "avy", (op.get("why") or "")[:300], run, stamp()))
            self._journal(run, op, f"t{chain}", None, db)
        return {"op": "timeline", "applied": True, "target": f"t{chain}", "chain": chain, "why": None,
                "merged": bool(head and op.get("chain") is None)}

    # --- threads ---------------------------------------------------------------------------------------

    def thread(self, chain):
        row = self.row("SELECT * FROM threads WHERE chain = ? ORDER BY version DESC LIMIT 1", chain)
        if row:
            row["insights"] = json.loads(row["insights"])
        return row

    def thread_heads(self, open_only=False):
        found = self.rows("SELECT * FROM threads t WHERE NOT EXISTS (SELECT 1 FROM threads x WHERE x.replaces = t.id) "
                          "ORDER BY at DESC")
        for r in found:
            r["insights"] = json.loads(r["insights"])
        return [r for r in found if r["status"] in OPEN_THREADS] if open_only else found

    def thread_versions(self, chain):
        found = self.rows("SELECT * FROM threads WHERE chain = ? ORDER BY version", chain)
        for r in found:
            r["insights"] = json.loads(r["insights"])
        return found

    def _op_thread(self, op, run):
        chain, head = op.get("chain"), None
        if chain is not None:
            try:
                chain = int(str(chain).lower().lstrip("th"))
            except ValueError:
                return self._journal(run, op, None, f"{op.get('chain')!r} isn't a thread (they look like th3)")
            head = self.thread(chain)
            if not head:
                return self._journal(run, op, f"th{chain}", f"there's no thread th{chain}")
        fields = {k: (head or {}).get(k) for k in ("title", "status", "goal", "state", "next", "waiting", "source")}
        for k in fields:
            if op.get(k) is not None and (op.get(k) != "" or k in ("waiting", "next")):
                fields[k] = op[k]
        fields["title"] = " ".join(str(fields["title"] or "").split())[:120]
        fields["status"] = fields["status"] or "active"
        for k in ("goal", "state", "next", "waiting"):
            fields[k] = " ".join(str(fields[k] or "").split())[:600]
        target = f"th{chain}" if chain else None
        if not fields["title"]:
            return self._journal(run, op, target, "a thread needs a title")
        if fields["status"] not in THREAD_STATUSES:
            return self._journal(run, op, target, f"status must be one of {', '.join(THREAD_STATUSES)}")
        insights = list((head or {}).get("insights") or [])
        if isinstance(op.get("insights"), list):
            insights = op["insights"]
        for line in op.get("add_insights") or []:
            insights.append(line)
        insights = [" ".join(str(x).split())[:240] for x in insights if str(x).strip()]
        insights = list(dict.fromkeys(insights))[-MAX_INSIGHTS:]
        if fields["source"] is not None and not self.row("SELECT id FROM messages WHERE id = ?", fields["source"]):
            fields["source"] = None
        if head and all(head.get(k) == v for k, v in fields.items()) and head["insights"] == insights:
            return {**self._journal(run, dict(op, unchanged=True), target, None), "chain": chain, "unchanged": True}
        with self.tx() as db:
            row = db.execute("SELECT COALESCE(MAX(id), 0) + 1 FROM threads").fetchone()[0]
            chain = chain or row
            db.execute("""INSERT INTO threads (id, chain, version, replaces, title, status, goal, state, next, waiting,
                          insights, source, by, why, run, at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                       (row, chain, (head or {}).get("version", 0) + 1, (head or {}).get("id"), fields["title"],
                        fields["status"], fields["goal"], fields["state"], fields["next"], fields["waiting"],
                        json.dumps(insights, ensure_ascii=False), fields["source"], op.get("by") or "avy",
                        (op.get("why") or "")[:300], run, stamp()))
            self._journal(run, op, f"th{chain}", None, db)
        return {"op": "thread", "applied": True, "target": f"th{chain}", "chain": chain, "why": None}

    # --- reading the desk back ----------------------------------------------------------------------

    def coming_up(self, days=AHEAD_DAYS):
        """What's ahead and what's overdue: {"overdue", "ahead", "undated", "later"} of timeline heads (planned only)."""
        today = now().replace(hour=0, minute=0, second=0, microsecond=0)
        horizon, back = today + timedelta(days=days + 1), today - timedelta(days=OVERDUE_DAYS)
        out = {"overdue": [], "ahead": [], "undated": [], "later": []}
        for t in self.timeline_heads():
            if t["status"] != "planned":
                continue
            if not t["start"]:
                out["undated"].append(t)
                continue
            at, timed = parse_when(t["start"])
            end = parse_when(t["end"])[0] if t["end"] and parse_when(t["end"]) else None
            over = (end or at) if timed or end else at + timedelta(days=1)
            if over <= now():
                if at >= back:
                    out["overdue"].append(t)
            elif at < horizon:
                out["ahead"].append(t)
            else:
                out["later"].append(t)
        return out

    def recent_past(self, days=3):
        """Timeline items that happened (or were due) in the last few days, any status: so 'how did it go?' has a hook."""
        since = (now() - timedelta(days=days)).strftime("%Y-%m-%d")
        today = now().strftime("%Y-%m-%d")
        return [t for t in self.timeline_heads() if t["start"] and since <= t["start"][:10] < today and t["status"] != "planned"]

    def slots_text(self):
        """The slots as they go into her instructions (the cached part of every request). Empty slots are left out."""
        parts = []
        character = self.slot("character")["items"]
        if character:
            parts.append("Your character note: how you are with him, in your own words, revised as you learn what works:\n"
                         + "\n".join(f"- {i['text']}" for i in character))
        him = self.slot("him")["items"]
        if him:
            parts.append(f"{NAME}: what's always true about him (his own words are the evidence for each):\n"
                         + "\n".join(f"- {i['text']}" for i in him))
        prefs = self.slot("preferences")["items"]
        if prefs:
            parts.append("His standing preferences. These are his rules for you, said in his own words; where one is more "
                         "specific than your defaults, it wins, every time, even when nothing in the message reminds you of it:\n"
                         + "\n".join(f"- {i['text']}" + (f" (when: {i['scope']})" if i.get("scope") else "") for i in prefs))
        return "\n\n".join(parts)

    def slot_lines(self, name, with_quotes=True):
        """A slot for the mind's jobs: each item with its id and evidence, so a job can keep, revise or drop it by id."""
        items = self.slot(name)["items"]
        if not items:
            return "(empty)"
        lines = []
        for i in items:
            cites = ", ".join(f"#{c}" for c in i.get("cites") or [])
            if name == "voice":
                lines.append(f"{i['id']} [{i['kind']}] her reply #{i['message']}: {i.get('why') or ''}")
            else:
                lines.append(f"{i['id']} {i['text']}" + (f" (when: {i['scope']})" if i.get("scope") else "")
                             + f"  [{cites}]" + (f" \"{i['quote']}\"" if with_quotes and i.get("quote") else ""))
        return "\n".join(lines)

    def clock_text(self):
        """Now, in words, with the next two weeks spelled out (a model's date arithmetic is the weak spot)."""
        t = now()
        last = self.row("SELECT at FROM messages WHERE role = 'user' ORDER BY id DESC LIMIT 1")
        days = [t + timedelta(days=d) for d in range(0, 15)]
        strip = ", ".join(f"{d:%a} {d:%b} {d.day}" if d.day == 1 or i == 0 else f"{d:%a} {d.day}" for i, d in enumerate(days))
        line = f"Now: {t:%A, %B} {t.day}, {t.year}, {t:%I:%M %p}".replace(" 0", " ") + f" {t.tzname() or ''}".rstrip() + "."
        if last:
            line += f" His last message before this one: {ago(last['at'])} ({when(last['at'])})."
        return line + f"\nThe next two weeks: {strip}."

    def timeline_line(self, t):
        bits = [f"t{t['chain']}", say_when(t["start"]) if t["start"] else "no date"]
        if t["end"]:
            bits[-1] += f" to {say_when(t['end'])}"
        line = f"{bits[0]} {bits[1]}: {t['title']}" + (f" ({t['kind']})" if t["kind"] != "event" else "")
        if t["status"] != "planned":
            line += f" [{t['status']}]"
        if t["notes"]:
            line += f". {clip(t['notes'], 0, 160)}"
        if t["thread"]:
            line += f" (th{t['thread']})"
        return line

    def thread_line(self, th):
        line = f"th{th['chain']} {th['title']} [{th['status']}]"
        if th["next"]:
            line += f" next: {clip(th['next'], 0, 140)}"
        if th["waiting"]:
            line += f"; waiting on: {clip(th['waiting'], 0, 100)}"
        return line

    def thread_frontier(self, th):
        lines = [f"th{th['chain']} {th['title']} [{th['status']}], updated {ago(th['at'])}"]
        for label, key in (("goal", "goal"), ("where it stands", "state"), ("next step", "next"), ("waiting on", "waiting")):
            if th[key]:
                lines.append(f"  {label}: {th[key]}")
        if th["insights"]:
            lines.append("  carried forward (why it's this way, what results would mean):")
            lines += [f"   - {x}" for x in th["insights"]]
        return "\n".join(lines)

    def related_thread(self, text):
        """The open thread this message is most likely about, or None: by meaning when the model is loaded, else by
        shared words. Only a clear match counts, so an unrelated thread isn't dragged into the conversation."""
        open_threads = self.thread_heads(open_only=True)
        if not open_threads or not (text or "").strip():
            return None
        about = lambda th: f"{th['title']}. {th['goal']} {th['state']} {th['next']}"
        if embedder.ready:
            q = embedder.query(text)
            vecs = embedder.passages([about(th) for th in open_threads])
            np = embedder.np
            scores = [float(np.dot(q, v) / (np.linalg.norm(q) * np.linalg.norm(v) + 1e-9)) for v in vecs]
            best = max(range(len(scores)), key=lambda i: scores[i])
            return open_threads[best] if scores[best] >= 0.72 else None
        words = lambda s: set(re.findall(r"[a-z0-9]{4,}", s.lower()))
        mine = words(text)
        scored = [(len(mine & words(about(th))), th) for th in open_threads]
        n, th = max(scored, key=lambda x: x[0])
        return th if n >= 2 else None

    def voice_examples(self, text, k=2):
        """Up to k of her replies kept as examples of her voice, the ones closest to this kind of message.
        Each: (what he'd said, what she said)."""
        items = self.slot("voice")["items"]
        if not items:
            return []
        picked = []
        for i in items:
            reply = self.message(i["message"])
            asked = self.row("SELECT text FROM messages WHERE id < ? AND role = 'user' ORDER BY id DESC LIMIT 1", i["message"])
            if reply:
                picked.append({"item": i, "reply": reply["text"], "asked": asked["text"] if asked else ""})
        if embedder.ready and text and len(picked) > k:
            q = embedder.query(text)
            vecs = embedder.passages([p["asked"] or p["reply"] for p in picked])
            np = embedder.np
            for p, v in zip(picked, vecs):
                p["score"] = float(np.dot(q, v) / (np.linalg.norm(q) * np.linalg.norm(v) + 1e-9))
            picked.sort(key=lambda p: -p["score"])
        return picked[:k]

    def desk_note(self, text=""):
        """The live half of the desk, built fresh for each message: the clock, what's coming up, the threads in
        flight (and the one this message is about, in full), and a couple of her own replies for her voice."""
        parts = [self.clock_text()]
        up = self.coming_up()
        cal = []
        if up["overdue"]:
            cal.append("Past due and not marked done (ask how it went, or mark it, only if it comes up):")
            cal += [f"- {self.timeline_line(t)}" for t in up["overdue"]]
        if up["ahead"]:
            cal.append(f"Coming up in the next {AHEAD_DAYS} days:")
            cal += [f"- {self.timeline_line(t)}" for t in up["ahead"]]
        if up["undated"]:
            cal.append("To do, no date:")
            cal += [f"- {self.timeline_line(t)}" for t in up["undated"][:8]]
        if up["later"]:
            cal.append("Further out: " + "; ".join(f"t{t['chain']} {say_when(t['start'], False)}: {t['title']}" for t in up["later"][:6]))
        past = self.recent_past()
        if past:
            cal.append("Just happened: " + "; ".join(self.timeline_line(t) for t in past[:5]))
        parts.append("Your calendar (the timeline; you keep it with the timeline tool):\n" + ("\n".join(cal) if cal else "Nothing on it yet."))
        threads = self.thread_heads(open_only=True)
        if threads:
            here = self.related_thread(text)
            block = "Threads in flight (work you're carrying; you keep these with the thread tool):\n" + "\n".join(
                f"- {self.thread_line(th)}" for th in threads[:10])
            if here:
                block += "\n\nThis message looks like it's about this one; here's exactly where you left it:\n" + self.thread_frontier(here)
            parts.append(block)
        voice = self.voice_examples(text)
        if voice:
            parts.append(("One of your own earlier replies" if len(voice) == 1 else "Some of your own earlier replies")
                         + " to him that landed, for your voice and manner only (never repeat their content):\n"
                         + "\n".join(f"- he said: \"{clip(v['asked'], 0, 160)}\"\n  you said: \"{clip(v['reply'], 0, 520)}\"" for v in voice))
        return "\n\n".join(parts)

    def desk_data(self):
        """Everything the page's desk panel shows."""
        def slot_view(name):
            s = self.slot(name)
            if name == "voice":
                for i in s["items"]:
                    m = self.message(i["message"])
                    i["text"] = clip(m["text"], 0, 400) if m else "(missing)"
                    i["at"] = m["at"] if m else None
            return {**s, "versions": self.value("SELECT COUNT(*) FROM slots WHERE name = ?", name) or 0}
        return {
            "now": stamp(),
            "slots": {name: slot_view(name) for name in SLOTS},
            "timeline": self.timeline_heads(),
            "coming": {k: [t["chain"] for t in v] for k, v in self.coming_up().items()},
            "threads": self.thread_heads(),
        }
