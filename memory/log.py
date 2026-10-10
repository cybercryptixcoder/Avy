"""The log (every message, word for word) and episodes (stretches of it, each with a headline)."""

import json
import sqlite3

from .common import minutes_between, stamp

WINDOW = 20             # the newest messages go to DeepSeek word for word (the /window: setting)
WINDOW_CHARS = 48_000   # ...but no more than this much text for a window of 20 (about 12k tokens)
ALL_CHARS = 3_000_000   # /window: all ... up to about 750k tokens, under DeepSeek's 1M limit
SITTING_GAP = 30        # minutes of quiet that end a sitting (and so an episode)


class Log:

    def add(self, role, text, via="text", meta=None, at=None):
        """Append a message to the log. Returns its number."""
        at = at or stamp()
        with self.tx() as db:
            mid = db.execute("INSERT INTO messages (at, role, text, via, meta) VALUES (?, ?, ?, ?, ?)",
                             (at, role, text, via, json.dumps(meta or {}))).lastrowid
            db.execute("INSERT INTO words (text, item) VALUES (?, ?)", (text, f"m{mid}"))
        self.remember_meaning([(f"m{mid}", text)])
        return mid

    def message(self, mid):
        m = self.row("SELECT * FROM messages WHERE id = ?", mid)
        if m:
            m["meta"] = json.loads(m["meta"])
        return m

    def messages_between(self, first, last):
        found = self.rows("SELECT * FROM messages WHERE id BETWEEN ? AND ? ORDER BY id", first, last)
        for m in found:
            m["meta"] = json.loads(m["meta"])
        return found

    def last_id(self):
        return self.value("SELECT MAX(id) FROM messages") or 0

    def last_said(self):
        """Your most recent message (whether or not it's on screen)."""
        return self.value("SELECT text FROM messages WHERE role = 'user' ORDER BY id DESC LIMIT 1") or ""

    def window(self, size=WINDOW):
        """The newest `size` messages, word for word (size None: all of them; 0: none).
        The start moves in steps of half the size, so it stays put for a few exchanges and
        DeepSeek can reuse its cached copy of the beginning."""
        last = self.last_id()
        if size == 0 or last == 0:
            return []
        if size is None:
            start, limit = 1, ALL_CHARS
        else:
            step = max(1, size // 2)
            start = max(1, ((last - size) // step) * step + 1)
            limit = max(WINDOW_CHARS, size * 2_400)
        shown = self.messages_between(start, last)
        while sum(len(m["text"]) for m in shown) > limit and len(shown) > 1:
            shown.pop(0)   # too much text: drop the oldest; recall can still bring them back
        return shown

    def copy_log_from(self, path):
        """Start this memory from another memory's log (version 1 or 2): every message, with its
        number, time and words, appended in order. The other file is only read. Returns how many."""
        if self.last_id():
            return 0
        source = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        try:
            found = source.execute("SELECT id, at, role, text, via, meta FROM messages ORDER BY id").fetchall()
        except sqlite3.OperationalError:
            return 0                                     # no log in that file
        finally:
            source.close()
        with self.tx() as db:
            for mid, at, role, text, via, meta in found:
                meta = json.loads(meta or "{}")
                meta.pop("recall", None)                 # pointed into the old file's recalls
                meta["copied_from"] = str(path.name if hasattr(path, "name") else path)
                db.execute("INSERT INTO messages (id, at, role, text, via, meta) VALUES (?, ?, ?, ?, ?, ?)",
                           (mid, at, role, text, via, json.dumps(meta)))
                db.execute("INSERT INTO words (text, item) VALUES (?, ?)", (text, f"m{mid}"))
        if self.shelves:
            self.load_vectors()
        return len(found)

    # --- episodes ----------------------------------------------------------------------------

    def written_up_to(self):
        """The last message that's been turned into knowledge (or looked at and found to hold none)."""
        return self.value("SELECT MAX(last) FROM episodes") or 0

    def episode(self, eid):
        return self.row("SELECT * FROM episodes WHERE id = ?", eid)

    def episode_of(self, mid):
        return self.value("SELECT id FROM episodes WHERE ? BETWEEN first AND last", mid)

    def next_stretch(self, page, force=False, idle_minutes=SITTING_GAP, now_iso=None):
        """The next stretch of the log to write, as (first, last), or None if it isn't time yet.
        A stretch ends at a sitting break (SITTING_GAP minutes of quiet), or after about `page`
        messages (on one of Avy's replies, so an exchange isn't split), or, for the newest one,
        once you've been away idle_minutes. force=True takes whatever is waiting."""
        start, last = self.written_up_to() + 1, self.last_id()
        if last < start:
            return None
        msgs = self.messages_between(start, min(last, start + page + 2))
        for i in range(1, len(msgs)):
            if minutes_between(msgs[i - 1]["at"], msgs[i]["at"]) >= SITTING_GAP:
                return start, msgs[i - 1]["id"]                     # a sitting ended here
            if i + 1 >= page:                                       # a page's worth: end on Avy's reply nearby
                near = msgs[max(0, i - 2):i + 1]
                if i + 1 < len(msgs) and minutes_between(msgs[i]["at"], msgs[i + 1]["at"]) < SITTING_GAP:
                    near.append(msgs[i + 1])
                replies = [x["id"] for x in near if x["role"] == "assistant"]
                return start, replies[-1] if replies else msgs[i]["id"]
        if force:
            return start, last
        if minutes_between(msgs[-1]["at"], now_iso or stamp()) >= idle_minutes:
            return start, last
        return None
