"""The file: one SQLite database per memory, one connection, one lock (every read and write takes turns)."""

import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path

from .embed import embedder

SCHEMA = (Path(__file__).parent / "schema.sql").read_text()
VERSION = 2


class Store:
    def __init__(self, path, name="main", letter="k"):
        """path: the .db file (created if missing). name: 'main' or 'incognito'.
        letter: how this memory's nodes are written (k12 in the main memory, x12 in an incognito one)."""
        self.path, self.name, self.letter = Path(path), name, letter
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.db = sqlite3.connect(self.path, check_same_thread=False, timeout=30)
        self.db.row_factory = sqlite3.Row
        tables = {r[0] for r in self.db.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
        if "entries" in tables:
            self.db.close()
            raise ValueError(f"{self.path} is a version 1 memory (log + index). Version 2 keeps its own file "
                             "and copies the log from it instead (Memory.copy_log_from).")
        self.db.execute("PRAGMA foreign_keys = ON")
        self.db.executescript(SCHEMA)
        self.db.execute(f"PRAGMA user_version = {VERSION}")
        self.shelves = {}            # meaning-search vectors, filled in once the model is ready
        self.closed = False
        embedder.attach(self)

    def close(self, delete=False):
        """Close the file. delete=True removes it from the disk too (an incognito conversation ending)."""
        embedder.detach(self)
        with self.lock:
            if not self.closed:
                self.closed = True
                self.db.close()
        if delete:
            for f in self.path.parent.glob(self.path.name + "*"):
                f.unlink(missing_ok=True)

    def rows(self, sql, *args):
        with self.lock:
            return [dict(r) for r in self.db.execute(sql, args).fetchall()]

    def row(self, sql, *args):
        found = self.rows(sql, *args)
        return found[0] if found else None

    def value(self, sql, *args):
        with self.lock:
            r = self.db.execute(sql, args).fetchone()
            return r[0] if r else None

    @contextmanager
    def tx(self):
        """One transaction: everything inside is saved together, or not at all."""
        with self.lock, self.db:
            yield self.db

    # --- marks: small bits of state (what reflection last looked at, and when) ----------------

    def mark(self, key, default=None):
        v = self.value("SELECT value FROM marks WHERE key = ?", key)
        return default if v is None else v

    def set_mark(self, key, value):
        with self.tx() as db:
            db.execute("INSERT OR REPLACE INTO marks (key, value) VALUES (?, ?)", (key, str(value)))

    def handle(self, chain):
        """k12 (or x12 in an incognito memory)."""
        return f"{self.letter}{chain}"
