"""
Avy's memory: one endless conversation, remembered in two layers.

  THE LOG    Every message, word for word, numbered #1, #2, ... Nothing in it is ever edited
             or deleted (the database itself refuses). It is the ground truth.

  THE INDEX  Context about the context. It never replaces the log; it points into it.
               page    one per stretch of about 20 messages: a headline, plus the entries
                       written from that stretch
               entry   one thing worth finding later: a person, a fact, a plan, ...
                         evidence  pointers to the exact words in the log it came from
                         links     pointers to other entries it's about or builds on, so the
                                   index grows into a network, like links between wiki pages
                         versions  a correction is a new entry that replaces the old one.
                                   The old one is kept, so the history can be walked back.

The names used everywhere (database, page, and what DeepSeek sees):
    #41 = message 41      p4 = page 4      e12 = entry 12

recall() runs on every message: it searches the index and the log, walks links outward from
what it found, and keeps what fits. briefing() lays that out for DeepSeek. indexer.py writes
the index in the background. Everything lives in one file, data/memory.db (SQLite, which is
built into Python).
"""

import json
import math
import re
import sqlite3
import threading
import time
from datetime import datetime
from pathlib import Path


# ---------------------------------------------------------------------------
# 1. Settings
# ---------------------------------------------------------------------------

NAME = "Shreyas"        # who Avy is talking to
WINDOW = 20             # the newest messages always go to DeepSeek word for word (20 to 29 of them)
WINDOW_CHARS = 48_000   # ...but no more than this much text (about 12k tokens)
RECALL_TOKENS = 6_000   # how much recalled memory one message can bring in
SEEDS = 8               # how many entries found by search the walk starts from
HOPS = 2                # how many links away the walk goes
FANOUT = 6              # at most this many links followed from any one entry (hubs have lots)
FOUND = 0.58            # how close (0 to 1) an entry must be to the question to count as found...
NEAR_BEST = 0.15        # ...and how close to the best match (a strong match makes weak ones noise)
KEEP = 0.3              # entries reached by links are kept down to this fraction of the best match
LOG_HITS = 4            # raw log messages recalled directly, as a safety net under the index

KINDS = ["person", "topic", "fact", "event", "decision", "preference", "task"]
HUBS = ["person", "topic"]                    # the kinds other entries gather around
LINK_KINDS = ["about", "builds_on", "related"]

# How strongly a link carries relevance from one entry to the next, by kind and direction.
# "out" follows the link as written (a birthday -> Rohan); "in" follows it backwards (Rohan -> his birthday).
STEP = {
    ("builds_on", "out"): 0.8, ("builds_on", "in"): 0.6,
    ("about", "out"): 0.7,     ("about", "in"): 0.6,    # "in": from a hub to what belongs to it
    ("related", "out"): 0.5,   ("related", "in"): 0.5,
    ("same message", ""): 0.35, # two entries that cite the same message: a link nobody had to write
}

EMBED_MODEL = "BAAI/bge-small-en-v1.5"   # 384 numbers per text, about 65 MB, runs on the CPU

STOPWORDS = set("""a an and are as at be been but by can could did do does doing for from had has have
he her hers him his how i i'm if in into is it it's its just me my of on or our so than that the their them
then there these they this to too up us very was we were what when where which who whom why will with would
you your yours yeah yes no not ok okay hey hi hello oh um uh like also about any some get got going gonna
want know think tell said say actually really thing things""".split())


def now():
    """The current time. Tests replace this to replay a conversation that spans days."""
    return datetime.now().astimezone()


def when(iso):
    """'2026-10-09T02:10:00-04:00' -> 'Thu Oct 9, 2:10 AM'"""
    t = datetime.fromisoformat(iso)
    return f"{t:%a %b} {t.day}, {t:%I:%M %p}".replace(" 0", " ")


def tokens(text):
    return len(text) // 4 + 1   # a rough count: about four characters per token


# ---------------------------------------------------------------------------
# 2. The database. One connection, one lock: every read and write takes turns.
# ---------------------------------------------------------------------------

SCHEMA = """
PRAGMA journal_mode = WAL;

-- THE LOG ----------------------------------------------------------------
CREATE TABLE IF NOT EXISTS messages (
  id    INTEGER PRIMARY KEY,                  -- the message number: #1, #2, ...
  at    TEXT NOT NULL,                        -- when, with time zone
  role  TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
  text  TEXT NOT NULL,
  via   TEXT NOT NULL DEFAULT 'text',         -- typed ('text') or spoken ('voice')
  meta  TEXT NOT NULL DEFAULT '{}'            -- model, tokens, cut off, which recall it used
);
CREATE TRIGGER IF NOT EXISTS log_is_permanent_1 BEFORE UPDATE ON messages
  BEGIN SELECT RAISE(ABORT, 'the log is append-only'); END;
CREATE TRIGGER IF NOT EXISTS log_is_permanent_2 BEFORE DELETE ON messages
  BEGIN SELECT RAISE(ABORT, 'the log is append-only'); END;

-- THE INDEX ----------------------------------------------------------------
CREATE TABLE IF NOT EXISTS pages (
  id        INTEGER PRIMARY KEY,              -- p1, p2, ...
  first     INTEGER NOT NULL,                 -- the stretch of the log it covers: #first to #last
  last      INTEGER NOT NULL,
  headline  TEXT NOT NULL,
  at        TEXT NOT NULL,
  run       INTEGER                           -- the indexing run that wrote it (runs.id)
);

CREATE TABLE IF NOT EXISTS entries (
  id        INTEGER PRIMARY KEY,              -- e1, e2, ... every version is its own entry
  page      INTEGER NOT NULL REFERENCES pages(id),
  kind      TEXT NOT NULL CHECK (kind IN ('person','topic','fact','event','decision','preference','task')),
  title     TEXT NOT NULL,
  text      TEXT NOT NULL,                    -- may mention other entries by reference: [e3]
  replaces  INTEGER REFERENCES entries(id),   -- the earlier version this one corrects or updates
  first     INTEGER NOT NULL,                 -- the first version's id: names the whole chain
  version   INTEGER NOT NULL DEFAULT 1,
  at        TEXT NOT NULL
);
-- each version is replaced at most once, so a chain never forks
CREATE UNIQUE INDEX IF NOT EXISTS chain_never_forks ON entries(replaces);
CREATE INDEX IF NOT EXISTS entries_by_chain ON entries(first);
-- the current version of every chain: nothing replaces it
CREATE VIEW IF NOT EXISTS current AS
  SELECT * FROM entries e WHERE NOT EXISTS (SELECT 1 FROM entries n WHERE n.replaces = e.id);

CREATE TABLE IF NOT EXISTS evidence (       -- entry -> the exact words in the log
  entry    INTEGER NOT NULL REFERENCES entries(id),
  message  INTEGER NOT NULL REFERENCES messages(id),
  start    INTEGER NOT NULL,                  -- where the words are in that message (characters)
  end      INTEGER NOT NULL,
  quote    TEXT NOT NULL,                     -- copied from the message by code, never by the model
  exact    INTEGER NOT NULL DEFAULT 1,        -- 0: the quote wasn't found, so this points at the whole message
  PRIMARY KEY (entry, message, start)
);
CREATE INDEX IF NOT EXISTS evidence_by_message ON evidence(message);

CREATE TABLE IF NOT EXISTS links (          -- entry -> entry
  src   INTEGER NOT NULL REFERENCES entries(id),
  dst   INTEGER NOT NULL REFERENCES entries(id),   -- the exact version that was linked to
  kind  TEXT NOT NULL CHECK (kind IN ('about','builds_on','related')),
  made_by TEXT NOT NULL DEFAULT 'model',    -- 'model' (DeepSeek wrote it) or 'system' (code added it)
  PRIMARY KEY (src, dst)
);
CREATE INDEX IF NOT EXISTS links_by_dst ON links(dst);

-- WHAT HAPPENED (so you can look under the hood) --------------------------------
CREATE TABLE IF NOT EXISTS runs (            -- every indexing run, start to finish
  id INTEGER PRIMARY KEY, at TEXT NOT NULL, first INTEGER NOT NULL, last INTEGER NOT NULL,
  status TEXT NOT NULL,                      -- ok, repaired, partial, failed
  attempts INTEGER NOT NULL, model TEXT, seconds REAL,
  tokens_in INTEGER, tokens_out INTEGER, cost REAL,
  prompt TEXT, replies TEXT, problems TEXT,  -- what DeepSeek saw, said, and what the checks found
  page INTEGER
);

CREATE TABLE IF NOT EXISTS recalls (         -- what memory brought to each of your messages
  id INTEGER PRIMARY KEY,
  message INTEGER NOT NULL,                  -- your message
  at TEXT NOT NULL,
  trace TEXT NOT NULL,                       -- what was found, and how it was reached
  briefing TEXT NOT NULL                     -- the exact memory text DeepSeek was given
);

-- SEARCH ------------------------------------------------------------------------------
-- words: keyword search over messages (m41), entries (e12) and page headlines (p4)
CREATE VIRTUAL TABLE IF NOT EXISTS words USING fts5(text, item UNINDEXED, tokenize = 'porter unicode61');
-- vectors: the same items as meaning-search numbers
CREATE TABLE IF NOT EXISTS vectors (item TEXT PRIMARY KEY, model TEXT NOT NULL, vec BLOB NOT NULL);
"""

LOCK = threading.RLock()
DB = None
PATH = None


def open_memory(path, models=None):
    """Open (or create) the memory file, and start loading the meaning-search model."""
    global DB, PATH
    PATH = Path(path)
    PATH.parent.mkdir(parents=True, exist_ok=True)
    DB = sqlite3.connect(PATH, check_same_thread=False, timeout=30)
    DB.row_factory = sqlite3.Row
    DB.execute("PRAGMA foreign_keys = ON")
    DB.executescript(SCHEMA)
    if models is not None:
        threading.Thread(target=meaning.load, args=(Path(models),), daemon=True).start()


def rows(sql, *args):
    with LOCK:
        return [dict(r) for r in DB.execute(sql, args).fetchall()]


def row(sql, *args):
    found = rows(sql, *args)
    return found[0] if found else None


def value(sql, *args):
    with LOCK:
        r = DB.execute(sql, args).fetchone()
        return r[0] if r else None


# ---------------------------------------------------------------------------
# 3. The log
# ---------------------------------------------------------------------------

def add(role, text, via="text", meta=None, at=None):
    """Append a message to the log. Returns its number."""
    at = at or now().isoformat(timespec="seconds")
    with LOCK, DB:
        mid = DB.execute("INSERT INTO messages (at, role, text, via, meta) VALUES (?, ?, ?, ?, ?)",
                         (at, role, text, via, json.dumps(meta or {}))).lastrowid
        DB.execute("INSERT INTO words (text, item) VALUES (?, ?)", (text, f"m{mid}"))
    meaning.add(f"m{mid}", text)
    return mid


def message(mid):
    m = row("SELECT * FROM messages WHERE id = ?", mid)
    if m:
        m["meta"] = json.loads(m["meta"])
    return m


def messages_between(first, last):
    found = rows("SELECT * FROM messages WHERE id BETWEEN ? AND ? ORDER BY id", first, last)
    for m in found:
        m["meta"] = json.loads(m["meta"])
    return found


def last_id():
    return value("SELECT MAX(id) FROM messages") or 0


def window():
    """The newest messages, word for word. It starts on a multiple of 10, so the start stays
    put for five exchanges at a time and DeepSeek can reuse its cached copy of the beginning."""
    last = last_id()
    start = max(1, ((last - WINDOW) // 10) * 10 + 1)
    shown = messages_between(start, last)
    while sum(len(m["text"]) for m in shown) > WINDOW_CHARS and len(shown) > 4:
        shown.pop(0)   # a few huge messages: drop the oldest; recall can still bring them back
    return shown


def first_shown():
    shown = window()
    return shown[0]["id"] if shown else last_id() + 1


# ---------------------------------------------------------------------------
# 4. Meaning search: a small local model turns text into 384 numbers, so that
#    "my exam" lands near "the probability quiz". It runs on this computer and
#    only ever searches; DeepSeek is still the only brain. Optional: without it,
#    keyword search still works.
# ---------------------------------------------------------------------------

class Shelf:
    """Rows of vectors that can grow, for one kind of item (messages, entries or pages)."""
    def __init__(self, np, dims=384):
        self.np, self.items, self.where = np, [], {}
        self.data = np.zeros((1024, dims), np.float32)

    def put(self, item, vec):
        if item in self.where:
            self.data[self.where[item]] = vec
            return
        if len(self.items) == len(self.data):
            self.data = self.np.concatenate([self.data, self.np.zeros_like(self.data)])
        self.where[item] = len(self.items)
        self.data[len(self.items)] = vec
        self.items.append(item)

    def closest(self, query, k):
        if not self.items:
            return []
        sims = self.data[:len(self.items)] @ query
        top = self.np.argsort(-sims)[:k]
        return [(self.items[i], float(sims[i])) for i in top]


class Meaning:
    def __init__(self):
        self.model, self.np, self.shelves = None, None, {}
        self.status = "starting"
        self.model_lock = threading.Lock()

    @property
    def ready(self):
        return self.model is not None

    def load(self, folder):
        try:
            import numpy as np
            from fastembed import TextEmbedding
        except ImportError:
            self.status = "off: install fastembed for search by meaning (keyword search still works)"
            return
        try:
            self.status = "loading the meaning-search model (first run downloads about 65 MB)"
            self.np = np
            model = TextEmbedding(EMBED_MODEL, cache_dir=str(folder))
            self.shelves = {kind: Shelf(np) for kind in "mep"}
            for r in rows("SELECT item, vec FROM vectors WHERE model = ?", EMBED_MODEL):
                self.shelves[r["item"][0]].put(r["item"], np.frombuffer(r["vec"], np.float32))
            self.model = model
            self.status = "on"
            self.catch_up()
        except Exception as e:
            self.model, self.status = None, f"off: the meaning-search model failed to load ({e})"

    def catch_up(self):
        """Embed anything saved while the model wasn't ready yet."""
        have = set(r["item"] for r in rows("SELECT item FROM vectors WHERE model = ?", EMBED_MODEL))
        todo = [(f"m{r['id']}", r["text"]) for r in rows("SELECT id, text FROM messages")]
        todo += [(f"e{r['id']}", entry_words(r)) for r in rows("SELECT * FROM entries")]
        todo += [(f"p{r['id']}", r["headline"]) for r in rows("SELECT id, headline FROM pages")]
        todo = [(item, text) for item, text in todo if item not in have]
        for i in range(0, len(todo), 64):
            self.add_many(todo[i:i + 64])

    def add(self, item, text):
        if self.ready:
            self.add_many([(item, text)])

    def add_many(self, items):
        if not self.ready or not items:
            return
        with self.model_lock:
            vecs = list(self.model.passage_embed([text[:2000] for _, text in items]))
        with LOCK, DB:
            for (item, _), vec in zip(items, vecs):
                vec = self.np.asarray(vec, self.np.float32)
                self.shelves[item[0]].put(item, vec)
                DB.execute("INSERT OR REPLACE INTO vectors (item, model, vec) VALUES (?, ?, ?)",
                           (item, EMBED_MODEL, vec.tobytes()))

    def query(self, text):
        if not self.ready or not text.strip():
            return None
        with self.model_lock:
            return self.np.asarray(next(iter(self.model.query_embed([text[:2000]]))), self.np.float32)

    def closest(self, query, kind, k=30):
        return self.shelves[kind].closest(query, k) if query is not None else []

    def closeness(self, item, query):
        """0 to 1. Unknown (no model, or not embedded yet) counts as middling."""
        shelf = self.shelves.get(item[0]) if query is not None else None
        if not shelf or item not in shelf.where:
            return 0.5
        return max(0.0, float(shelf.data[shelf.where[item]] @ query))


meaning = Meaning()


# ---------------------------------------------------------------------------
# 5. Search: how close each item is to the question, on a fixed scale from 0 to 1,
#    so that "nothing matches" is a possible answer (a ranking alone can't say that).
#      meaning  the meaning-search similarity (unrelated things land around 0.4 to 0.55)
#      words    the share of the question's words the item contains, rare words counting more
#    score = meaning + a bonus for shared words. Without the meaning model: words alone.
# ---------------------------------------------------------------------------

def terms(text):
    """The words worth searching for: no filler words, no single letters."""
    found = []
    for w in re.findall(r"[a-z0-9]+", text.lower()):
        if len(w) > 1 and w not in STOPWORDS and w not in found:
            found.append(w)
    return found[:24]


def word_scores(text, kind):
    """{item: share of the text's words it contains}, rare words weighted up (IDF), for one kind
    of item ('m', 'e' or 'p'). Only items sharing at least one word are listed."""
    words = terms(text)
    if not words:
        return {}
    total = value("SELECT COUNT(*) FROM words WHERE item GLOB ?", f"{kind}*") or 1
    weight, has = {}, {}
    for w in words:
        items = [r["item"] for r in rows("SELECT item FROM words WHERE words MATCH ? AND item GLOB ?", f'"{w}"', f"{kind}*")]
        weight[w] = max(0.0, math.log((total + 1) / (len(items) + 0.5)))
        for item in items:
            has.setdefault(item, set()).add(w)
    whole = sum(weight.values()) or 1
    return {item: sum(weight[w] for w in ws) / whole for item, ws in has.items()}


def relevance(queries, kind, k=40):
    """How close items of one kind are to the question. queries: [(text, weight, vector or None)].
    Returns {item: {"score", "meaning", "words", "how"}}, best match per item across the queries."""
    found = {}
    for text, weight, vec in queries:
        closeness = dict(meaning.closest(vec, kind, k)) if vec is not None else {}
        shared = word_scores(text, kind)
        for item in set(closeness) | set(shared):
            sim = closeness.get(item)
            if sim is None and vec is not None:
                sim = meaning.closeness(item, vec)      # shares words but wasn't in the top k by meaning
            words = shared.get(item, 0.0)
            score = weight * ((sim + 0.15 * words) if vec is not None else words)
            if score > found.get(item, {}).get("score", -1):
                how = "both" if words and (sim or 0) >= FOUND else "words" if words else "meaning"
                found[item] = {"score": score, "meaning": sim, "words": words, "how": how}
    return found


def found_threshold(best):
    """What counts as found: close enough in absolute terms, and not far behind the best match."""
    floor = FOUND if meaning.ready else 0.3
    return max(floor, best - NEAR_BEST)


# ---------------------------------------------------------------------------
# 6. Entries: versions, links, and reading them back
# ---------------------------------------------------------------------------

def entry(eid):
    return row("SELECT * FROM entries WHERE id = ?", eid)


def head(eid):
    """The current version of the chain that this entry belongs to."""
    return value("SELECT id FROM current WHERE first = (SELECT first FROM entries WHERE id = ?)", eid)


def is_current(eid):
    return value("SELECT 1 FROM current WHERE id = ?", eid) is not None


def chain(eid):
    """Every version of this entry, newest first."""
    return rows("SELECT * FROM entries WHERE first = (SELECT first FROM entries WHERE id = ?) ORDER BY version DESC", eid)


def evidence_of(eid):
    return rows("""SELECT v.*, m.at, m.role FROM evidence v JOIN messages m ON m.id = v.message
                   WHERE v.entry = ? ORDER BY v.message, v.start""", eid)


def mentions(text):
    return [int(n) for n in re.findall(r"\[e(\d+)\]", text)]


def readable(text):
    """Replace mentions like [e3] with the current title of what they point to."""
    def title(match):
        h = head(int(match.group(1)))
        return entry(h)["title"] if h else match.group(0)
    return re.sub(r"\[e(\d+)\]", title, text)


def entry_words(e):
    """What search sees for an entry: its title and its text, with mentions spelled out."""
    return f"{e['title']}: {readable(e['text'])}"


def neighbors(eid):
    """Every current entry one step away: links either way (made to any of its versions),
    and entries that cite the same message. Returns [(entry, link kind, direction)]."""
    versions = [e["id"] for e in chain(eid)]
    marks = ",".join("?" * len(versions))
    found = []
    for r in rows(f"SELECT dst, kind FROM links WHERE src IN ({marks})", *versions):
        found.append((head(r["dst"]), r["kind"], "out"))
    for r in rows(f"SELECT src, kind FROM links WHERE dst IN ({marks}) AND src IN (SELECT id FROM current)", *versions):
        found.append((r["src"], r["kind"], "in"))
    for r in rows("""SELECT DISTINCT b.entry FROM evidence a JOIN evidence b ON a.message = b.message
                     WHERE a.entry = ? AND b.entry != ?""", eid, eid):
        h = head(r["entry"])
        if h and h != eid:
            found.append((h, "same message", ""))
    seen, unique = set(), []
    for n in found:
        if n[0] and n[0] != eid and n[0] not in seen:
            seen.add(n[0])
            unique.append(n)
    return unique


def links_of(eid):
    """For the inspector: where this entry points, and what points here (from current entries)."""
    versions = [e["id"] for e in chain(eid)]
    marks = ",".join("?" * len(versions))
    out = []
    for r in rows("SELECT dst, kind, made_by FROM links WHERE src = ?", eid):
        h = head(r["dst"])
        out.append({"to": h, "linked": r["dst"], "kind": r["kind"], "by": r["made_by"],
                    "title": entry(h)["title"], "entry_kind": entry(h)["kind"], "moved_on": h != r["dst"]})
    back = []
    for r in rows(f"""SELECT l.src, l.dst, l.kind, l.made_by FROM links l JOIN current c ON c.id = l.src
                      WHERE l.dst IN ({marks}) ORDER BY l.src DESC""", *versions):
        e = entry(r["src"])
        back.append({"from": r["src"], "kind": r["kind"], "by": r["made_by"], "title": e["title"],
                     "entry_kind": e["kind"], "linked": r["dst"]})
    return out, back


def backlink_counts():
    """How many current entries point at each chain: the hubs of the network."""
    found = rows("""SELECT h.first, COUNT(DISTINCT l.src) AS n FROM links l
                    JOIN entries h ON h.id = l.dst JOIN current c ON c.id = l.src
                    GROUP BY h.first""")
    return {r["first"]: r["n"] for r in found}


def core(limit=12):
    """The biggest hubs, sent with every message so Avy always knows who and what matters most.
    It only changes when the index does, so DeepSeek can cache it."""
    counts = backlink_counts()
    hubs = [e for e in rows("SELECT * FROM current WHERE kind IN ('person', 'topic')") if counts.get(e["first"], 0) >= 1]
    hubs.sort(key=lambda e: (-counts.get(e["first"], 0), e["id"]))
    if not hubs:
        return ""
    lines = [f"[e{e['id']}] {e['title']} ({e['kind']}): {readable(e['text'])}" for e in hubs[:limit]]
    return "Who and what matters most (the hubs of your memory):\n" + "\n".join(lines)


# ---------------------------------------------------------------------------
# 7. Recall: what does memory know that's relevant to this message?
#    1. search the index (every version) and the log, by keyword and by meaning
#    2. walk links outward from the best entries, one and two steps
#    3. keep the strongest, up to the token budget
# ---------------------------------------------------------------------------

REFERS_BACK = set("he him his she her hers they them their it its that this those these there one".split())


def refers_back(text):
    """Does this message lean on the one before it? ("what about him?", "why?")"""
    return len(terms(text)) <= 1 or any(w in REFERS_BACK for w in re.findall(r"[a-z]+", text.lower()))


def recall(text, previous=""):
    """What memory knows that's relevant to this message. previous: your message before this one,
    used only when this one refers back to it. Returns a trace: what was found and how, plus the
    briefing text DeepSeek will see."""
    started = time.time()
    shown_from = first_shown()
    q1 = meaning.query(text)
    queries = [(text, 1.0, q1)]
    if previous and refers_back(text):
        context = f"{previous[-300:]}\n{text}"
        queries.append((context, 0.85, meaning.query(context)))

    # 1. Search every version of every entry. A hit on an old version counts for the current
    #    one (searching for "March 3" still finds Rohan's birthday after it moved to May 3).
    found = {}
    for item, hit in relevance(queries, "e").items():
        eid = int(item[1:])
        h = head(eid)
        if h and hit["score"] > found.get(h, {}).get("score", -1):
            found[h] = {**hit, "matched": eid if eid != h else None}
    for eid, hit in found.items():      # a nudge for recent things: up to 5% for today, fading over a month
        hit["score"] *= 1 + 0.05 * math.exp(-age_days(entry(eid)["at"]) / 30)
    best = max([h["score"] for h in found.values()] + [0])
    bar = found_threshold(best)
    seeds = sorted((e for e in found if found[e]["score"] >= bar), key=lambda e: -found[e]["score"])[:SEEDS]

    # 2. Walk the links outward from what was found: one step, then two.
    reached = {e: found[e] for e in seeds}
    frontier = list(seeds)
    for hop in range(1, HOPS + 1):
        steps = []
        for eid in frontier:
            for nid, kind, direction in neighbors(eid):
                score = reached[eid]["score"] * STEP[(kind, direction)] * (0.5 + 0.5 * meaning.closeness(f"e{nid}", q1))
                steps.append((score, nid, eid, kind, direction))
        frontier, taken = [], {}
        for score, nid, eid, kind, direction in sorted(steps, reverse=True):
            taken[eid] = taken.get(eid, 0) + 1
            if taken[eid] > FANOUT or nid in seeds or score <= reached.get(nid, {}).get("score", 0):
                continue
            reached[nid] = {"score": score, "how": "link", "via": eid, "link": kind, "direction": direction, "hop": hop}
            frontier.append(nid)

    # 3. Keep the strongest within the budget. Link finds far weaker than the best match are dropped.
    ranked = [e for e in sorted(reached, key=lambda e: -reached[e]["score"]) if reached[e]["score"] >= KEEP * best]
    picked, blocks, used, skipped, cited = [], [], 0, 0, set()
    for i, eid in enumerate(ranked):
        block, msgs = entry_block(eid, full=i < 3, shown_from=shown_from)
        if used + tokens(block) > RECALL_TOKENS:
            skipped += 1
            continue
        used += tokens(block)
        blocks.append(block)
        cited |= msgs
        hit = reached[eid]
        e = entry(eid)
        picked.append({"entry": eid, "title": e["title"], "kind": e["kind"], "version": e["version"],
                       "score": round(hit["score"], 3), "how": hit["how"], "matched": hit.get("matched"),
                       "via": hit.get("via"), "link": hit.get("link"), "direction": hit.get("direction"),
                       "messages": sorted(msgs)})

    # 4. The safety net: older messages that match by themselves, in case the index missed something.
    #    Skipped if already on screen, or next to a message an entry already cites.
    covered = set()
    for eid in reached:
        for v in chain(eid):
            covered |= {m + d for m in (x["message"] for x in evidence_of(v["id"])) for d in (-1, 0, 1)}
    hits = {int(item[1:]): hit for item, hit in relevance(queries, "m").items()
            if int(item[1:]) < shown_from and int(item[1:]) not in covered}
    log_best = max([h["score"] for h in hits.values()] + [0])
    log_bar = max(found_threshold(log_best), FOUND + 0.02 if meaning.ready else 0.4)
    log_lines, log_blocks = [], []
    for mid in sorted(hits, key=lambda m: -hits[m]["score"]):
        if hits[mid]["score"] < log_bar or len(log_lines) >= LOG_HITS:
            break
        block = message_block(message(mid))
        if used + tokens(block) > RECALL_TOKENS:
            skipped += 1
            continue
        used += tokens(block)
        log_blocks.append(block)
        log_lines.append({"message": mid, "how": hits[mid]["how"], "score": round(hits[mid]["score"], 3)})

    trace = {
        "query": text, "entries": picked, "log": log_lines, "skipped": skipped, "tokens": used,
        "searched": {"entries": len(found), "log": len(hits)}, "walked": len(reached) - len(seeds),
        "best": round(best, 3), "bar": round(bar, 3),
        "meaning": meaning.status, "seconds": round(time.time() - started, 3),
        "messages": sorted(cited | {m["message"] for m in log_lines}),
    }
    trace["briefing"] = briefing(blocks, log_blocks)
    return trace


def age_days(iso):
    return max(0.0, (now() - datetime.fromisoformat(iso)).total_seconds() / 86400)


def who(role):
    return NAME if role == "user" else "Avy"


def entry_block(eid, full=False, shown_from=None):
    """One entry, the way DeepSeek sees it. full=True shows the whole message each quote came from.
    Messages from shown_from on are already in the recent conversation, so they're only pointed to."""
    e = entry(eid)
    head_line = f"[e{eid}] {e['title']} ({e['kind']}"
    if e["version"] > 1:
        head_line += f", version {e['version']}, updated {when(e['at'])}"
    lines = [head_line + f"): {readable(e['text'])}"]
    msgs = set()
    for v in evidence_of(eid):
        msgs.add(v["message"])
        if shown_from and v["message"] >= shown_from:
            lines.append(f"   #{v['message']} (in the recent messages)")
        elif full:
            m = message(v["message"])
            text = m["text"]
            text = text[:v["start"]] + "«" + text[v["start"]:v["end"]] + "»" + text[v["end"]:]
            lines.append(f"   #{m['id']} {when(m['at'])}, {who(m['role'])}: {clip(text, v['start'], 600)}")
        else:
            lines.append(f"   #{v['message']} {when(v['at'])}, {who(v['role'])}: \"{v['quote']}\"")
    older = chain(eid)[1:]
    for old in older[:3]:
        quotes = "; ".join(f"#{v['message']}" for v in evidence_of(old["id"]))
        lines.append(f"   earlier version {old['version']} [e{old['id']}]: {readable(old['text'])} ({quotes})")
    out, _ = links_of(eid)
    if out:
        lines.append("   links: " + ", ".join(f"{l['kind'].replace('_', ' ')} {l['title']} [e{l['to']}]" for l in out[:5]))
    return "\n".join(lines), msgs


def clip(text, around, limit):
    """Shorten a long message to `limit` characters, keeping the part near `around`."""
    if len(text) <= limit:
        return text
    start = max(0, min(around - limit // 3, len(text) - limit))
    return ("…" if start else "") + text[start:start + limit] + ("…" if start + limit < len(text) else "")


def message_block(m):
    return f"#{m['id']} {when(m['at'])}, {who(m['role'])}: {clip(m['text'], 0, 700)}"


def briefing(entry_blocks, log_blocks):
    """The memory note DeepSeek gets right before your newest message."""
    parts = [f"Memory for this message. It is now {now():%A, %B %d, %Y, %I:%M %p %Z}."]
    if entry_blocks:
        parts.append("From your memory index (newest versions; quotes are the exact words, #n is message n):\n"
                     + "\n".join(entry_blocks))
    if log_blocks:
        parts.append("From older parts of the conversation:\n" + "\n".join(log_blocks))
    if not entry_blocks and not log_blocks:
        parts.append("Nothing older in memory matched this message.")
    return "\n\n".join(parts)


def save_recall(mid, trace):
    with LOCK, DB:
        return DB.execute("INSERT INTO recalls (message, at, trace, briefing) VALUES (?, ?, ?, ?)",
                          (mid, now().isoformat(timespec="seconds"), json.dumps(trace), trace["briefing"])).lastrowid


# ---------------------------------------------------------------------------
# 8. Writing the index. indexer.py checks everything first; this just saves it,
#    all or nothing, in one transaction.
# ---------------------------------------------------------------------------

def save_page(first, last, headline, new_entries, run_id):
    """new_entries: checked entries from indexer.py, each with
         handle    'n1', 'n2', ... (how they refer to each other)
         kind, title, text     text may mention [e12] or [n2]
         evidence  [(message, start, end, exact)]
         replaces  an existing current entry id, or None
         links     [(target, kind, by)]  target is an entry id or a handle
    Returns (page id, {handle: new entry id})."""
    at = now().isoformat(timespec="seconds")
    made = {}
    with LOCK, DB:
        page_id = DB.execute("INSERT INTO pages (first, last, headline, at, run) VALUES (?, ?, ?, ?, ?)",
                             (first, last, headline, at, run_id)).lastrowid
        for e in new_entries:                         # first pass: create every entry
            old = entry(e["replaces"]) if e["replaces"] else None
            eid = DB.execute(
                "INSERT INTO entries (page, kind, title, text, replaces, first, version, at) VALUES (?, ?, ?, ?, ?, 0, ?, ?)",
                (page_id, e["kind"], e["title"], e["text"], e["replaces"], old["version"] + 1 if old else 1, at)).lastrowid
            DB.execute("UPDATE entries SET first = ? WHERE id = ?", (old["first"] if old else eid, eid))
            made[e["handle"]] = eid
        resolve = lambda target: made[target] if isinstance(target, str) else target
        for e in new_entries:                         # second pass: text, evidence and links
            eid = made[e["handle"]]
            text = re.sub(r"\[(n\d+)\]", lambda m: f"[e{made[m.group(1)]}]" if m.group(1) in made else m.group(0), e["text"])
            DB.execute("UPDATE entries SET text = ? WHERE id = ?", (text, eid))
            for mid, start, end, exact in e["evidence"]:
                quote = DB.execute("SELECT substr(text, ?, ?) FROM messages WHERE id = ?", (start + 1, end - start, mid)).fetchone()[0]
                DB.execute("INSERT OR IGNORE INTO evidence (entry, message, start, end, quote, exact) VALUES (?, ?, ?, ?, ?, ?)",
                           (eid, mid, start, end, quote, exact))
            linked = set()
            for target, kind, by in e["links"]:
                dst = resolve(target)
                if dst != eid and dst not in linked:
                    linked.add(dst)
                    DB.execute("INSERT OR IGNORE INTO links (src, dst, kind, made_by) VALUES (?, ?, ?, ?)", (eid, dst, kind, by))
            if e["replaces"]:                         # a new version keeps the old one's links
                for r in DB.execute("SELECT dst, kind FROM links WHERE src = ?", (e["replaces"],)).fetchall():
                    if r["dst"] != eid and r["dst"] not in linked:
                        linked.add(r["dst"])
                        DB.execute("INSERT OR IGNORE INTO links (src, dst, kind, made_by) VALUES (?, ?, ?, 'system')", (eid, r["dst"], r["kind"]))
        DB.execute("INSERT INTO words (text, item) VALUES (?, ?)", (headline, f"p{page_id}"))
        for eid in made.values():
            DB.execute("INSERT INTO words (text, item) VALUES (?, ?)", (entry_words(entry(eid)), f"e{eid}"))
    meaning.add_many([(f"e{eid}", entry_words(entry(eid))) for eid in made.values()] + [(f"p{page_id}", headline)])
    return page_id, made


def save_run(**run):
    run.setdefault("at", now().isoformat(timespec="seconds"))
    for name in ("prompt", "replies", "problems"):
        run[name] = json.dumps(run.get(name))
    names = ", ".join(run)
    with LOCK, DB:
        return DB.execute(f"INSERT INTO runs ({names}) VALUES ({', '.join('?' * len(run))})", tuple(run.values())).lastrowid


def set_run_page(run_id, page_id):
    with LOCK, DB:
        DB.execute("UPDATE runs SET page = ? WHERE id = ?", (page_id, run_id))


def indexed_up_to():
    return value("SELECT MAX(last) FROM pages") or 0


# ---------------------------------------------------------------------------
# 9. Looking under the hood: what the page's inspector asks for
# ---------------------------------------------------------------------------

def stats():
    return {
        "messages": last_id(),
        "pages": value("SELECT COUNT(*) FROM pages"),
        "entries": value("SELECT COUNT(*) FROM current"),
        "versions": value("SELECT COUNT(*) FROM entries"),
        "links": value("SELECT COUNT(*) FROM links"),
        "indexed_to": indexed_up_to(),
        "waiting": last_id() - indexed_up_to(),
        "failed_runs": value("SELECT COUNT(*) FROM runs WHERE status = 'failed'"),
        "mb": round(sum(p.stat().st_size for p in PATH.parent.glob(PATH.name + "*")) / 1e6, 2) if PATH else 0,
        "meaning": meaning.status,
        "file": str(PATH.resolve()) if PATH else "",
    }


def log_slice(before=None, after=None, limit=60):
    """Messages for the chat history and the inspector's log view, oldest first."""
    if after is not None:
        found = rows("SELECT * FROM messages WHERE id > ? ORDER BY id LIMIT ?", after, limit)
    else:
        found = rows("SELECT * FROM messages WHERE id < ? ORDER BY id DESC LIMIT ?", before or last_id() + 1, limit)[::-1]
    for m in found:
        m["meta"] = json.loads(m["meta"])
        if m["meta"].get("recall"):
            r = row("SELECT trace FROM recalls WHERE id = ?", m["meta"]["recall"])
            t = json.loads(r["trace"]) if r else {}
            m["recalled"] = {"id": m["meta"]["recall"], "entries": len(t.get("entries", [])), "log": len(t.get("log", []))}
        m["page"] = value("SELECT id FROM pages WHERE ? BETWEEN first AND last", m["id"])
        m["cited_by"] = [r["entry"] for r in rows("SELECT DISTINCT entry FROM evidence WHERE message = ?", m["id"])]
    return found


def article(eid):
    """An entry as a wiki page: its text, evidence, links both ways, and every version."""
    e = entry(eid)
    if not e:
        return None
    out, back = links_of(eid)
    versions = []
    for v in chain(eid):
        successor = row("SELECT id, at FROM entries WHERE replaces = ?", v["id"])
        versions.append({**v, "readable": readable(v["text"]), "evidence": evidence_of(v["id"]),
                         "replaced_by": successor["id"] if successor else None,
                         "replaced_at": successor["at"] if successor else None})
    page = row("SELECT * FROM pages WHERE id = ?", e["page"])
    mentioned = {n: entry(head(n))["title"] for n in mentions(e["text"]) if head(n)}
    return {"entry": {**e, "readable": readable(e["text"])}, "current": head(eid), "evidence": evidence_of(eid),
            "links": out, "backlinks": back, "versions": versions, "page": page, "mentions": mentioned}


def page_record(pid):
    p = row("SELECT * FROM pages WHERE id = ?", pid)
    if not p:
        return None
    entries_here = rows("SELECT * FROM entries WHERE page = ? ORDER BY id", pid)
    for e in entries_here:
        e["current"] = is_current(e["id"])
        e["readable"] = readable(e["text"])
    run = row("SELECT * FROM runs WHERE id = ?", p["run"]) if p["run"] else None
    if run:
        for name in ("prompt", "replies", "problems"):
            run[name] = json.loads(run[name]) if run[name] else None
    return {"page": p, "entries": entries_here, "run": run}


def pages_list(limit=400):
    found = rows("""SELECT p.*, (SELECT COUNT(*) FROM entries WHERE page = p.id) AS n,
                           r.status, r.attempts FROM pages p LEFT JOIN runs r ON r.id = p.run
                    ORDER BY p.id DESC LIMIT ?""", limit)
    return found


def recall_record(rid):
    r = row("SELECT * FROM recalls WHERE id = ?", rid)
    if r:
        r["trace"] = json.loads(r["trace"])
    return r


def find(text):
    """The inspector's search: current entries and log messages, closest first."""
    queries = [(text, 1.0, meaning.query(text))]
    hits = {}
    for item, hit in relevance(queries, "e").items():
        h = head(int(item[1:]))
        if h and hit["score"] > hits.get(h, {}).get("score", -1):
            hits[h] = hit
    floor = 0.5 if meaning.ready else 0.01
    found_entries = []
    for eid in sorted(hits, key=lambda e: -hits[e]["score"])[:20]:
        if hits[eid]["score"] < floor:
            break
        e = entry(eid)
        found_entries.append({"id": eid, "kind": e["kind"], "title": e["title"], "text": readable(e["text"]),
                              "version": e["version"], "how": hits[eid]["how"], "score": round(hits[eid]["score"], 3)})
    msgs = relevance(queries, "m")
    found_msgs = []
    for item in sorted(msgs, key=lambda i: -msgs[i]["score"])[:20]:
        if msgs[item]["score"] < floor:
            break
        m = message(int(item[1:]))
        found_msgs.append({"id": m["id"], "at": m["at"], "role": m["role"], "text": clip(m["text"], 0, 300),
                           "how": msgs[item]["how"], "score": round(msgs[item]["score"], 3)})
    return {"entries": found_entries, "messages": found_msgs}
