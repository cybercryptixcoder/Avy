"""Carry the log from one memory file to another (any version: they share the same messages table).

    python3 tools/copy_log.py data/memory-v2.db data/memory.db

Appends every message the destination doesn't have yet (same time, speaker and words), in order,
with its time and words, and nothing else: knowledge isn't copied, the destination's own mind writes
it from the log. The source is only read. Stop app.py first, so nothing writes to the files meanwhile.
"""

import json
import sqlite3
import sys
from pathlib import Path


def copy_log(source, destination):
    src = sqlite3.connect(f"file:{source}?mode=ro", uri=True)
    dst = sqlite3.connect(destination)
    have = {(r[0], r[1], r[2]) for r in dst.execute("SELECT at, role, text FROM messages")}
    added = 0
    with dst:
        for at, role, text, via, meta in src.execute("SELECT at, role, text, via, meta FROM messages ORDER BY id"):
            if (at, role, text) in have:
                continue
            meta = json.loads(meta or "{}")
            meta.pop("recall", None)                      # pointed into the other file's recalls
            meta["copied_from"] = Path(source).name
            mid = dst.execute("INSERT INTO messages (at, role, text, via, meta) VALUES (?, ?, ?, ?, ?)",
                              (at, role, text, via, json.dumps(meta))).lastrowid
            dst.execute("INSERT INTO words (text, item) VALUES (?, ?)", (text, f"m{mid}"))
            added += 1
    return added


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    print(f"copied {copy_log(sys.argv[1], sys.argv[2])} messages from {sys.argv[1]} to {sys.argv[2]}")
