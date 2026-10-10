"""Does any question share searchable words with the conversations it needs? (It shouldn't: then
keyword search can't find the answer just by matching words.) Uses the same tokenizer and filler-word
list as memory's keyword search.

    python3 tests/bench/check_words.py
"""

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from memory.common import terms  # noqa: E402
import world  # noqa: E402

db = sqlite3.connect(":memory:")
db.execute("CREATE VIRTUAL TABLE words USING fts5(text, thread UNINDEXED, tokenize = 'porter unicode61')")
for s in world.SESSIONS:
    for who, text in s["lines"]:
        db.execute("INSERT INTO words VALUES (?, ?)", (text, s["thread"]))

clean = True
for p in world.PROBES:
    threads = {n.partition("@")[0] for n in p["needs"]}
    shared = {}
    for w in terms(p["ask"]):
        hits = {r[0] for r in db.execute("SELECT thread FROM words WHERE words MATCH ?", (f'"{w}"',))}
        if hits & threads:
            shared[w] = sorted(hits & threads)
    ok = bool(not shared or p.get("words_ok"))
    clean &= ok
    print(f"{'ok  ' if ok else 'WORD'}  {p['id']:<14} " + (", ".join(f"'{w}' in {t}" for w, t in shared.items()) if shared else "no shared words")
          + ("  (allowed: this one is about his exact words)" if shared and p.get("words_ok") else ""))
sys.exit(0 if clean else 1)
