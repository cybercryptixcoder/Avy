"""The desk's instruments: what code keeps the books on, so she doesn't have to (VISION.md §9, "Instruments, not tools").

    the clock      now, how long since he last wrote, and the next two weeks spelled out
    the timeline   dated things (events, deadlines, reminders) and tasks: t12. Versioned like knowledge. Code decides
                   what's coming up, what's overdue and what just happened; the model only writes entries.
    threads        work in flight (th3), each with its frontier (the goal, where it stands, the next step, what it waits
                   on, the insights behind it) and a plan tree: a goal split into steps and options, with dead ends
                   kept as pruned branches and their reasons. Several threads are in flight at once, each in its own
                   state; a message moves the one it's about.

Anything code can keep the books on, code keeps the books on: dates, what's due, what's open, what's next. The model
interprets; it doesn't do bookkeeping. Each instrument is the visible end of a store: a fixed-size face that's always
shown (the next two weeks, one line per thread, the current thread's frontier), with the store behind it searched.

Never calls the model. Changes come through the one door (Memory.apply):
    {"op": "timeline", "chain"?, "title", "kind", "start", "end", "status", "notes", "thread", "source", "quote", "by", "why"}
    {"op": "thread", "chain"?, "title", "status", "goal", "state", "next", "waiting", "insights" | "add_insights",
     "steps": [{id?, text?, parent?, status?, why?}], "source", "by", "why"}
"""

import json
import re
from datetime import datetime, timedelta

from .common import clip, now, stamp, when

KINDS = ("event", "deadline", "reminder", "task")
STATUSES = ("planned", "done", "cancelled", "missed")
THREAD_STATUSES = ("active", "waiting", "paused", "done", "dropped")
OPEN_THREADS = ("active", "waiting", "paused")
STEP_STATUSES = ("todo", "doing", "done", "dropped")
WHEN = re.compile(r"^\d{4}-\d{2}-\d{2}(T\d{2}:\d{2})?$")

# The fixed size of each instrument's face on the desk.
AHEAD_DAYS = 14          # how far ahead "coming up" looks
OVERDUE_DAYS = 14        # planned things this far in the past still show, as past due
CALENDAR_LINES = 14      # the calendar shows at most this many lines (the rest: a count, and the store behind it)
THREAD_LINES = 8         # one line per open thread, at most this many
MAX_INSIGHTS = 8         # what a thread carries forward
MAX_STEPS = 24           # a thread's plan tree


def parse_when(value):
    """'2026-10-20' or '2026-10-20T15:00' -> (datetime in his time zone, has a time). None if it isn't one."""
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
    skip = {"the", "a", "an", "with", "to", "for", "of", "at", "my", "his", "on", "in"}
    wa = set(re.findall(r"[a-z0-9]+", a.lower())) - skip
    wb = set(re.findall(r"[a-z0-9]+", b.lower())) - skip
    if not wa or not wb:
        return False
    return len(wa & wb) / min(len(wa), len(wb)) >= 0.6


def step_order(steps):
    """A plan tree's steps in reading order (each parent before its children), with their depth."""
    kids = {}
    for s in steps:
        kids.setdefault(s.get("parent"), []).append(s)
    out = []

    def walk(parent, depth):
        for s in kids.get(parent, []):
            out.append((s, depth))
            walk(s["id"], depth + 1)
    walk(None, 0)
    return out


def next_step(steps):
    """The plan's next step, worked out by code: the first step, in reading order, that isn't done or dropped, whose
    children (if any) are all finished, and that doesn't sit under a dropped branch."""
    dropped = set()
    for s, _ in step_order(steps):
        if s["status"] == "dropped" or s.get("parent") in dropped:
            dropped.add(s["id"])
    for s, _ in step_order(steps):
        if s["id"] in dropped or s["status"] in ("done", "dropped"):
            continue
        open_kids = [k for k in steps if k.get("parent") == s["id"] and k["status"] not in ("done", "dropped")]
        if not open_kids:
            return s
    return None


class Desk:

    # --- the timeline --------------------------------------------------------------------------------

    def timeline_item(self, chain):
        return self.row("SELECT * FROM timeline WHERE chain = ? ORDER BY version DESC LIMIT 1", chain)

    def timeline_heads(self):
        """The newest version of every timeline item, by date (undated tasks last)."""
        return self.rows("SELECT * FROM timeline t WHERE NOT EXISTS (SELECT 1 FROM timeline x WHERE x.replaces = t.id) "
                         "ORDER BY COALESCE(start, '9999'), chain")

    def timeline_versions(self, chain):
        return self.rows("SELECT * FROM timeline WHERE chain = ? ORDER BY version", chain)

    def same_timeline_item(self, title, start):
        """An item already on the timeline that's the same thing (the same day, a similar title): adding it again would
        be a duplicate, so it becomes an update instead (moving a time, adding a note)."""
        day = (start or "")[:10]
        for t in self.timeline_heads():
            if t["status"] != "cancelled" and (t["start"] or "")[:10] == day and similar_titles(t["title"], title):
                return t
        return None

    def _op_timeline(self, op, run):
        chain, head = op.get("chain"), None
        if chain is not None:
            try:
                chain = int(str(chain).lower().lstrip("t"))
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
        if fields["end"] and fields["start"] and fields["end"] < fields["start"]:
            return self._journal(run, op, target, "it can't end before it starts")
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
                "merged": bool(head and op.get("chain") is None), "changed": "added" if not head else "updated"}

    def coming_up(self, days=AHEAD_DAYS):
        """What's ahead and what's past due, worked out by code from the dates: {"overdue", "ahead", "undated", "later"}
        of planned timeline items. Something that has passed without being marked is past due, not done: whether it
        happened is a question, not something to assume."""
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
            over = end or (at if timed else at + timedelta(days=1))
            if t["kind"] == "deadline":
                over = at if timed else at + timedelta(days=1)
            if over <= now():
                if at >= back:
                    out["overdue"].append(t)
            elif at < horizon:
                out["ahead"].append(t)
            else:
                out["later"].append(t)
        return out

    def recent_past(self, days=3):
        """Timeline items from the last few days that were marked (done, cancelled, missed)."""
        since = (now() - timedelta(days=days)).strftime("%Y-%m-%d")
        today = now().strftime("%Y-%m-%d")
        return [t for t in self.timeline_heads() if t["start"] and since <= t["start"][:10] <= today and t["status"] != "planned"]

    # --- threads -------------------------------------------------------------------------------------

    def thread(self, chain):
        row = self.row("SELECT * FROM threads WHERE chain = ? ORDER BY version DESC LIMIT 1", chain)
        return self._thread_row(row) if row else None

    def _thread_row(self, row):
        row["insights"] = json.loads(row["insights"])
        row["steps"] = json.loads(row.get("steps") or "[]")
        return row

    def thread_heads(self, open_only=False):
        found = [self._thread_row(r) for r in self.rows(
            "SELECT * FROM threads t WHERE NOT EXISTS (SELECT 1 FROM threads x WHERE x.replaces = t.id) ORDER BY at DESC, chain DESC")]
        return [r for r in found if r["status"] in OPEN_THREADS] if open_only else found

    def thread_versions(self, chain):
        return [self._thread_row(r) for r in self.rows("SELECT * FROM threads WHERE chain = ? ORDER BY version", chain)]

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
        insights += list(op.get("add_insights") or [])
        insights = [" ".join(str(x).split())[:240] for x in insights if str(x).strip()]
        insights = list(dict.fromkeys(insights))[-MAX_INSIGHTS:]
        steps, problem = self._plan(head, op.get("steps") or [])
        if problem:
            return self._journal(run, op, target, problem)
        if fields["source"] is not None and not self.row("SELECT id FROM messages WHERE id = ?", fields["source"]):
            fields["source"] = None
        if head and all(head.get(k) == v for k, v in fields.items()) and head["insights"] == insights and head["steps"] == steps:
            return {**self._journal(run, dict(op, unchanged=True), target, None), "chain": chain, "unchanged": True}
        with self.tx() as db:
            row = db.execute("SELECT COALESCE(MAX(id), 0) + 1 FROM threads").fetchone()[0]
            chain = chain or row
            db.execute("""INSERT INTO threads (id, chain, version, replaces, title, status, goal, state, next, waiting,
                          insights, steps, source, by, why, run, at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                       (row, chain, (head or {}).get("version", 0) + 1, (head or {}).get("id"), fields["title"],
                        fields["status"], fields["goal"], fields["state"], fields["next"], fields["waiting"],
                        json.dumps(insights, ensure_ascii=False), json.dumps(steps, ensure_ascii=False), fields["source"],
                        op.get("by") or "avy", (op.get("why") or "")[:300], run, stamp()))
            self._journal(run, op, f"th{chain}", None, db)
        return {"op": "thread", "applied": True, "target": f"th{chain}", "chain": chain, "why": None,
                "changed": "opened" if not head else "updated"}

    def _plan(self, head, changes):
        """A thread's plan tree after some changes: [{id, text, parent, status, why}]. A change names a step by id to
        update it (status, text, why, parent), or has no id to add one. Code keeps the tree a tree (no step under
        itself) and keeps dropped branches, with why they were dropped. Returns (steps, problem)."""
        steps = [dict(s) for s in (head or {}).get("steps") or []]
        by_id = {s["id"]: s for s in steps}
        n = 1 + max([int(s["id"][1:]) for s in steps if re.fullmatch(r"s\d+", s["id"])] or [0])
        for c in changes:
            if not isinstance(c, dict):
                return None, "each step change is an object"
            sid = str(c.get("id") or "").strip().lower() or None
            if sid and sid not in by_id:
                return None, f"there's no step {sid} in this thread's plan"
            step = by_id.get(sid) if sid else {"id": f"s{n}", "text": "", "parent": None, "status": "todo", "why": ""}
            if not sid:
                n += 1
            for k in ("text", "why"):
                if c.get(k):
                    step[k] = " ".join(str(c[k]).split())[:200]
            if c.get("status"):
                if c["status"] not in STEP_STATUSES:
                    return None, f"a step's status is one of {', '.join(STEP_STATUSES)}"
                step["status"] = c["status"]
            if "parent" in c:
                parent = str(c["parent"] or "").strip().lower() or None
                if parent and parent not in by_id and parent != step["id"]:
                    return None, f"there's no step {parent} to put this under"
                step["parent"] = parent
            if not step["text"]:
                return None, "a new step needs its text"
            if step["status"] == "dropped" and not step.get("why"):
                return None, f"say why {step['id']} was dropped (a dead end keeps its reason, so it isn't tried again)"
            if not sid:
                steps.append(step)
                by_id[step["id"]] = step
        for s in steps:                                   # a tree: following parents never comes back round
            seen, p = {s["id"]}, s.get("parent")
            while p:
                if p in seen:
                    return None, f"step {s['id']} ends up under itself"
                seen.add(p)
                p = by_id[p].get("parent") if p in by_id else None
        if len(steps) > MAX_STEPS:
            return None, f"a plan holds at most {MAX_STEPS} steps: fold finished ones into their parent"
        return steps, None

    # --- reading the instruments back ----------------------------------------------------------------

    def clock_text(self):
        """Now, in words, with the next two weeks spelled out (a model's date arithmetic is the weak spot)."""
        t = now()
        last = self.row("SELECT at FROM messages WHERE role = 'user' ORDER BY id DESC LIMIT 1")
        days = [t + timedelta(days=d) for d in range(0, 15)]
        strip = ", ".join(f"{d:%a} {d:%b} {d.day}" if d.day == 1 or i == 0 else f"{d:%a} {d.day}" for i, d in enumerate(days))
        line = f"Now: {t:%A, %B} {t.day}, {t.year}, {t:%I:%M %p}".replace(", 0", ", ") + (f" {t.tzname()}" if t.tzname() else "") + "."
        if last:
            line += f" His previous message was {ago(last['at'])} ({when(last['at'])})."
        return line + f"\nThe next two weeks: {strip}."

    def timeline_line(self, t):
        line = f"t{t['chain']} {say_when(t['start']) if t['start'] else 'no date'}"
        if t["end"]:
            line += f" to {say_when(t['end'])}"
        line += f": {t['title']}" + (f" ({t['kind']})" if t["kind"] != "event" else "")
        if t["status"] != "planned":
            line += f" [{t['status']}]"
        if t["notes"]:
            line += f". {clip(t['notes'], 0, 140)}"
        if t["thread"]:
            line += f" (th{t['thread']})"
        return line

    def calendar_text(self):
        """The calendar's face: past due, the next two weeks, undated tasks, a glimpse further out; at most CALENDAR_LINES."""
        up, lines = self.coming_up(), []
        groups = [("Past due, not marked (it may or may not have happened):", up["overdue"]),
                  (f"Coming up in the next {AHEAD_DAYS} days:", up["ahead"]),
                  ("To do, no date:", up["undated"])]
        room = CALENDAR_LINES
        for heading, items in groups:
            if items and room > 0:
                lines.append(heading)
                lines += [f"- {self.timeline_line(t)}" for t in items[:room]]
                if len(items) > room:
                    lines.append(f"- (and {len(items) - room} more)")
                room -= len(items)
        if up["later"]:
            lines.append("Further out: " + "; ".join(f"t{t['chain']} {say_when(t['start'], False)}: {t['title']}" for t in up["later"][:4])
                         + (f" (+{len(up['later']) - 4} more)" if len(up["later"]) > 4 else ""))
        past = self.recent_past()
        if past:
            lines.append("Just happened: " + "; ".join(self.timeline_line(t) for t in past[:4]))
        return "\n".join(lines) if lines else "Nothing on it yet."

    def thread_line(self, th):
        step = next_step(th["steps"])
        line = f"th{th['chain']} {th['title']} [{th['status']}]"
        nxt = th["next"] or (step["text"] if step else "")
        if nxt:
            line += f" next: {clip(nxt, 0, 120)}"
        if th["waiting"]:
            line += f"; waiting on: {clip(th['waiting'], 0, 90)}"
        return line

    def thread_frontier(self, th):
        """Where a thread was left, in full: the frontier and the plan tree (finished branches folded)."""
        lines = [f"th{th['chain']} {th['title']} [{th['status']}], last touched {ago(th['at'])}"]
        for label, key in (("goal", "goal"), ("where it stands", "state"), ("next", "next"), ("waiting on", "waiting")):
            if th[key]:
                lines.append(f"  {label}: {th[key]}")
        if th["steps"]:
            step = next_step(th["steps"])
            lines.append("  the plan (s-steps; ✓ done, ✗ dropped with why, → next by the plan):")
            for s, depth in step_order(th["steps"]):
                mark = {"done": "✓", "dropped": "✗", "doing": "…", "todo": "·"}[s["status"]]
                if step and s["id"] == step["id"]:
                    mark = "→"
                line = f"   {'  ' * depth}{mark} {s['id']} {s['text']}"
                if s["status"] == "dropped" and s.get("why"):
                    line += f" (dropped: {s['why']})"
                lines.append(line)
        if th["insights"]:
            lines.append("  carried forward (why it's this way, what a result would mean):")
            lines += [f"   - {x}" for x in th["insights"]]
        return "\n".join(lines)

    def related_thread(self, text, previous=""):
        """The open thread this message is about, or None. By meaning when the model is loaded, else by shared words.
        Only a clear match counts, so an unrelated thread isn't dragged into the conversation."""
        from .embed import embedder
        open_threads = self.thread_heads(open_only=True)
        if not open_threads or not (text or "").strip():
            return None
        probe = f"{previous[-300:]}\n{text}" if previous and len(text) < 60 else text
        about = lambda th: f"{th['title']}. {th['goal']} {th['state']} {th['next']}"
        mentioned = [th for th in open_threads if f"th{th['chain']}" in probe.lower() or th["title"].lower() in probe.lower()]
        if mentioned:
            return mentioned[0]
        if embedder.ready:
            np, q = embedder.np, embedder.query(probe)
            vecs = embedder.passages([about(th) for th in open_threads])
            scores = [float(np.dot(q, v) / (np.linalg.norm(q) * np.linalg.norm(v) + 1e-9)) for v in vecs]
            best = max(range(len(scores)), key=lambda i: scores[i])
            return open_threads[best] if scores[best] >= 0.74 else None
        words = lambda s: set(re.findall(r"[a-z0-9]{4,}", s.lower()))
        n, th = max(((len(words(probe) & words(about(th))), th) for th in open_threads), key=lambda x: x[0])
        return th if n >= 2 else None

    def desk_note(self, text="", previous="", knowledge=()):
        """The live half of the desk, built fresh for each message, the same way every time from the same state: the
        clock, the calendar, the threads in flight (and the one this message is about, in full), and the part of the
        persona this moment calls up. Returns (note, what was put on it) so the turn can record it."""
        parts = ["Your desk, for you to know where things stand. Bring something up from it only when it bears on what he just "
                 "said; never recite it, and never mention that something on it is empty.",
                 self.clock_text(), "Your calendar (the timeline; you keep it with the timeline tool):\n" + self.calendar_text()]
        threads, here = self.thread_heads(open_only=True), None
        if threads:
            here = self.related_thread(text, previous)
            block = ("Threads in flight (work you're carrying, each where you left it; you keep them with the thread tool):\n"
                     + "\n".join(f"- {self.thread_line(th)}" for th in threads[:THREAD_LINES])
                     + (f"\n- (and {len(threads) - THREAD_LINES} more, paused longest)" if len(threads) > THREAD_LINES else ""))
            if here:
                block += "\n\nThis message is about this one. Exactly where you left it:\n" + self.thread_frontier(here)
            parts.append(block)
        moment = self.persona_moment(text, previous, knowledge)
        if moment["note"]:
            parts.append(moment["note"])
        shown = {"situation": moment["situation"], "persona": moment["lines"], "terms": moment["terms"],
                 "voice": moment["voice"], "thread": here["chain"] if here else None}
        return "\n\n".join(parts), shown

    def desk_data(self):
        """Everything the page's desk panel shows."""
        up = self.coming_up()
        threads = self.thread_heads()
        for th in threads:
            nxt = next_step(th["steps"])
            th["next_step"] = nxt["id"] if nxt else None
        return {"now": stamp(), "timeline": self.timeline_heads(),
                "coming": {k: [t["chain"] for t in v] for k, v in up.items()},
                "threads": threads, "persona": self.persona_data()}
