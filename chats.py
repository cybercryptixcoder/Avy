"""Plain chat: Avy as an ordinary chatbot (/mode: chat, or the toggle at the top of the page).

Nothing of Avy's is in it: no memory, no persona, no desk, no tools. Each conversation stands alone, the model reads
only that conversation, and only as much of it as fits the context window (/chatwindow: the newest messages that fit;
older ones fall out of view, the way a normal chatbot works). Conversations are kept in data/chats.db, apart from her
memory, and can be started, renamed and deleted from the page.
"""

import sqlite3
import threading
from datetime import datetime

SYSTEM = ("You are a helpful, honest assistant. Answer clearly and directly; use Markdown when it helps. "
          "Today is {today}.")
CHARS_PER_TOKEN = 4          # a rough count, good enough to keep inside the window
REPLY_ROOM = 8000            # tokens kept free for the reply


class Chats:
    def __init__(self, path):
        self.path = str(path)
        self.lock = threading.Lock()
        with self.db() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS conversations (id INTEGER PRIMARY KEY, title TEXT NOT NULL DEFAULT 'New chat',
                    created TEXT NOT NULL, updated TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY, conversation INTEGER NOT NULL
                    REFERENCES conversations(id) ON DELETE CASCADE, role TEXT NOT NULL, text TEXT NOT NULL,
                    reasoning TEXT, at TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS messages_by_conversation ON messages(conversation, id);""")

    def db(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys = ON")
        return db

    def now(self):
        return datetime.now().astimezone().isoformat(timespec="seconds")

    def list(self):
        with self.db() as db:
            return [dict(r) for r in db.execute(
                """SELECT c.*, (SELECT COUNT(*) FROM messages m WHERE m.conversation = c.id) AS messages
                   FROM conversations c ORDER BY updated DESC, id DESC""")]

    def new(self, title="New chat"):
        with self.lock, self.db() as db:
            at = self.now()
            cid = db.execute("INSERT INTO conversations (title, created, updated) VALUES (?, ?, ?)", (title, at, at)).lastrowid
        return self.get(cid)

    def get(self, cid):
        with self.db() as db:
            c = db.execute("SELECT * FROM conversations WHERE id = ?", (cid,)).fetchone()
            if not c:
                return None
            msgs = [dict(r) for r in db.execute("SELECT * FROM messages WHERE conversation = ? ORDER BY id", (cid,))]
        return {**dict(c), "messages": msgs}

    def rename(self, cid, title):
        with self.lock, self.db() as db:
            db.execute("UPDATE conversations SET title = ? WHERE id = ?", (str(title).strip()[:80] or "New chat", cid))

    def delete(self, cid):
        with self.lock, self.db() as db:
            db.execute("DELETE FROM messages WHERE conversation = ?", (cid,))
            db.execute("DELETE FROM conversations WHERE id = ?", (cid,))

    def add(self, cid, role, text, reasoning=None):
        with self.lock, self.db() as db:
            at = self.now()
            mid = db.execute("INSERT INTO messages (conversation, role, text, reasoning, at) VALUES (?, ?, ?, ?, ?)",
                             (cid, role, text, reasoning, at)).lastrowid
            db.execute("UPDATE conversations SET updated = ? WHERE id = ?", (at, cid))
            if role == "user":
                c = db.execute("SELECT title, (SELECT COUNT(*) FROM messages WHERE conversation = ?) n FROM conversations WHERE id = ?",
                               (cid, cid)).fetchone()
                if c and c["title"] == "New chat" and c["n"] == 1:
                    words = " ".join(text.split()[:7])
                    db.execute("UPDATE conversations SET title = ? WHERE id = ?", ((words[:60] + ("…" if len(words) > 60 else "")) or "New chat", cid))
        return mid

    def context(self, cid, window_tokens):
        """The messages the model reads: the system line, then the newest messages that fit the window (oldest dropped)."""
        msgs = self.get(cid)["messages"]
        room = max(1000, window_tokens - REPLY_ROOM) * CHARS_PER_TOKEN
        shown = []
        for m in reversed(msgs):
            room -= len(m["text"]) + 20
            if room < 0 and shown:
                break
            shown.append({"role": m["role"], "content": m["text"]})
        shown.reverse()
        dropped = len(msgs) - len(shown)
        system = SYSTEM.format(today=datetime.now().astimezone().strftime("%A, %B %d, %Y"))
        return [{"role": "system", "content": system}] + shown, dropped
