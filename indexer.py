"""
The indexer: turns a stretch of the log into a page of entries, in the background.

DeepSeek does the judgment: what's worth remembering, how to say it, what it connects to.
This file does everything that has to be right every time:
  1. picks the stretch (about 20 messages) and the existing entries DeepSeek may link to,
     each with a short handle (#41 is a message, e12 is an entry)
  2. asks for one structured answer: a call to write_index, whose shape a schema fixes
  3. checks every part of it: the messages and entries exist, every quote is really in its
     message, corrections point at current entries, nothing is created twice, links are capped
  4. sends the problems back to be fixed (up to twice), then keeps whatever passed
  5. saves it all at once, with a record of the whole exchange (a "run") you can inspect
If DeepSeek can't be reached, nothing is lost: the log is already saved, and it tries again later.
"""

import difflib
import json
import re
import threading
import time
from datetime import datetime

import memory
from memory import HUBS, KINDS, LINK_KINDS, NAME


# ---------------------------------------------------------------------------
# 1. Settings
# ---------------------------------------------------------------------------

PAGE = 20              # messages per page
IDLE_MINUTES = 30      # after you've been away this long, index what's waiting...
MIN_STRETCH = 4        # ...if it's at least this many messages
CONTEXT_BEFORE = 4     # earlier messages shown for context (not to be cited)
SHOW_ENTRIES = 40      # existing entries shown, to link to or update
MAX_LINKS = 6          # links per entry, so the network stays meaningful
REPAIRS = 2            # how many times DeepSeek may fix its answer
RETRY_MINUTES = 10     # after a failed run, wait this long before trying the same stretch again
GIVE_UP_AFTER = 3      # after this many unusable answers, save a bare page and move on
MODEL = "deepseek-flash"

app = {"ask": None, "prices": {}}      # filled in by start(): how to call DeepSeek, and its prices
RUN_LOCK = threading.Lock()            # one run at a time
WAKE = threading.Event()


# ---------------------------------------------------------------------------
# 2. When to index
# ---------------------------------------------------------------------------

def due(force=False):
    """The next stretch to index as (first, last), or None if it's not time yet."""
    start, last = memory.indexed_up_to() + 1, memory.last_id()
    if last < start:
        return None
    if not force and backing_off(start):
        return None
    if last - start + 1 >= PAGE:
        return start, page_end(start)
    if force:
        return start, last
    idle = (memory.now() - datetime.fromisoformat(memory.message(last)["at"])).total_seconds() / 60
    if last - start + 1 >= MIN_STRETCH and idle >= IDLE_MINUTES:
        return start, last
    return None


def page_end(start):
    """End a full page on one of Avy's replies, so an exchange isn't split across two pages."""
    end = start + PAGE - 1
    for m in reversed(memory.messages_between(end - 2, end + 1)):
        if m["role"] == "assistant":
            return m["id"]
    return end


def backing_off(start):
    last_run = memory.row("SELECT * FROM runs WHERE first = ? ORDER BY id DESC LIMIT 1", start)
    if not last_run or last_run["status"] not in ("failed", "error"):
        return False
    minutes = (memory.now() - datetime.fromisoformat(last_run["at"])).total_seconds() / 60
    return minutes < RETRY_MINUTES


# ---------------------------------------------------------------------------
# 3. What DeepSeek is shown, and the shape its answer must take
# ---------------------------------------------------------------------------

INSTRUCTIONS = f"""You keep the memory index for Avy, a personal assistant in one endless conversation with {NAME}.
The conversation log is permanent and never changes. You don't summarize it: you write an index into it.
For each stretch of messages you write a page: a headline, plus entries. An entry is one thing worth finding
later, with pointers to the exact words it came from, and links to the other entries it connects to.

What deserves an entry: the people in {NAME}'s life and who they are to him; facts about him and his world;
plans, dates and deadlines; decisions and why; his preferences; tasks; and the projects, courses, places
and subjects he talks about. Skip small talk and passing moments (a meal, the weather, a show, a slow
laptop) unless they show something lasting: a habit, a preference, a plan, a problem that keeps coming
back. Skip what only Avy said, unless {NAME} agreed or acted on it. Skip questions he asks about things
already in memory, and Avy's answers to them, unless they add something new. Never write an entry
saying something is unknown or was never mentioned.

Kinds:
  person      someone in {NAME}'s life. A hub: other entries link to it.
  topic       a project, course, place, organisation, thing or subject. A hub.
  fact        something true about {NAME} or his world
  event       something with a date or time: a plan, deadline, appointment, or something that happened
  decision    a choice that was made, and why
  preference  what he likes or dislikes, or how he wants things done
  task        something to do (say whether it's done)

Rules:
1. Evidence. Every entry cites the message(s) it came from, with the exact words copied character for
   character from that message: a short span that shows the point, not the whole message. Only cite
   messages from the stretch to index.
2. One idea per entry. The title is a short name, like a wiki page title ("Rohan", "Rohan's birthday").
   The text is one or two plain sentences.
3. Dates: write absolute dates, worked out from the message times ("Friday" said on Thu Oct 9 2026
   means Fri Oct 10, 2026).
4. Updates. If something changes an existing entry (a corrected date, a task now done, a new plan),
   write the new version as a new entry and set "replaces" to that entry's handle. Keep its title.
   Never create a second entry with the same title as an existing one. If another existing entry repeats
   the information that changed, write a new version of that one too.
5. By reference. When an entry depends on or belongs to existing entries, link to them instead of
   repeating what they say. You may also mention one in the text as [e12] (just the handle in the
   brackets) where its title reads naturally in the sentence, like a person or a place: "Party at
   [e3]'s place". Link kinds go in links, never in the text. Link kinds:
     about      it belongs to that person or topic (a hub)
     builds_on  it uses or depends on what that entry says
     related    a real but looser connection
   Only link what's truly connected; at most {MAX_LINKS} links per entry. New entries in your answer
   can link to and mention each other by their handles (n1, n2, ...).
6. Hubs. When a person or topic matters and has no entry yet, create one (kind person or topic) and link
   the entries that belong to it with "about". A hub's text says only who or what it is, in one sentence
   ("Shreyas's friend from CMPSC 465"). Every other fact about it gets its own entry linked to the hub,
   so that a correction only ever changes one entry.
7. If nothing in the stretch is worth remembering, return no entries, but still write a headline.

Answer only by calling write_index."""

TOOL = {"type": "function", "function": {
    "name": "write_index",
    "description": "Save the index page for this stretch of the conversation.",
    "strict": True,
    "parameters": {
        "type": "object",
        "properties": {
            "headline": {"type": "string", "description": "What this stretch was about, in under 12 words."},
            "entries": {"type": "array", "items": {
                "type": "object",
                "properties": {
                    "handle": {"type": "string", "description": "n1, n2, ... in order. New entries link to each other with these."},
                    "kind": {"type": "string", "enum": KINDS},
                    "title": {"type": "string", "description": "A short name, like a wiki page title."},
                    "text": {"type": "string", "description": "One or two sentences. Mention other entries as [e12] or [n2] instead of repeating them."},
                    "evidence": {"type": "array", "items": {
                        "type": "object",
                        "properties": {
                            "message": {"type": "integer", "description": "The message number: 41 for #41."},
                            "quote": {"type": "string", "description": "The exact words from that message, copied character for character."},
                        },
                        "required": ["message", "quote"], "additionalProperties": False}},
                    "replaces": {"anyOf": [{"type": "string"}, {"type": "null"}],
                                 "description": "The existing entry this corrects or updates, like \"e12\". null if it's new."},
                    "links": {"type": "array", "items": {
                        "type": "object",
                        "properties": {
                            "to": {"type": "string", "description": "An existing entry (e12) or a new one (n2)."},
                            "kind": {"type": "string", "enum": LINK_KINDS},
                        },
                        "required": ["to", "kind"], "additionalProperties": False}},
                },
                "required": ["handle", "kind", "title", "text", "evidence", "replaces", "links"],
                "additionalProperties": False}},
        },
        "required": ["headline", "entries"],
        "additionalProperties": False,
    },
}}


def entries_to_show(stretch):
    """The existing entries DeepSeek may link to or update: the biggest hubs, the newest entries,
    and whatever each message in the stretch brings up in search. Current versions only."""
    counts = memory.backlink_counts()
    current = {e["id"]: e for e in memory.rows("SELECT * FROM current")}
    picks = sorted((e for e in current.values() if e["kind"] in HUBS), key=lambda e: -counts.get(e["first"], 0))[:15]
    picks += sorted(current.values(), key=lambda e: -e["id"])[:10]
    for m in stretch:
        text = m["text"][:1500]
        hits = memory.relevance([(text, 1.0, memory.meaning.query(text))], "e", 12)
        for item in sorted(hits, key=lambda i: -hits[i]["score"])[:6]:
            h = memory.head(int(item[1:]))
            if h in current:
                picks.append(current[h])
    shown, seen = [], set()
    for e in picks:
        if e["id"] not in seen:
            seen.add(e["id"])
            shown.append(e)
    return {e["id"]: e for e in shown[:SHOW_ENTRIES]}


def describe(e, counts):
    out, _ = memory.links_of(e["id"])
    links = " ".join(f"{l['kind']} e{l['to']}" for l in out[:4])
    line = f"e{e['id']} {e['kind']} \"{e['title']}\": {e['text']}"
    if e["version"] > 1:
        line += f" (version {e['version']})"
    if links:
        line += f" [{links}]"
    if e["kind"] in HUBS and counts.get(e["first"]):
        line += f" ({counts[e['first']]} entries link here)"
    return line


def as_line(m, limit):
    text = m["text"] if len(m["text"]) <= limit else m["text"][:limit] + " …(cut here)"
    return f"#{m['id']} {memory.when(m['at'])}  {memory.who(m['role'])}: {text}"


def prompt(first, last, stretch, shown):
    counts = memory.backlink_counts()
    parts = []
    if shown:
        parts.append("Existing entries you can link to, mention, or update (current versions):\n"
                     + "\n".join(describe(e, counts) for e in shown.values()))
    else:
        parts.append("There are no entries yet: this is the start of the memory.")
    before = memory.messages_between(max(1, first - CONTEXT_BEFORE), first - 1)
    if before:
        parts.append("Just before, for context only (already indexed; don't cite these):\n"
                     + "\n".join(as_line(m, 600) for m in before))
    parts.append(f"The stretch to index, #{first} to #{last}:\n"
                 + "\n".join(as_line(m, 4000 if m["role"] == "user" else 1500) for m in stretch))
    return [{"role": "system", "content": INSTRUCTIONS}, {"role": "user", "content": "\n\n".join(parts)}]


# ---------------------------------------------------------------------------
# 4. Checking the answer. Returns what can be saved, and a list of problems in
#    plain words for DeepSeek to fix. Anything code can't safely fix is left out.
# ---------------------------------------------------------------------------

def loose(text):
    """Lowercase letters and digits with single spaces, plus where each character came from."""
    out, where, gap = [], [], False
    for i, ch in enumerate(text):
        if ch.isalnum():
            if gap and out:
                out.append(" ")
                where.append(i)
            out.append(ch.lower())
            where.append(i)
            gap = False
        else:
            gap = True
    return "".join(out), where


def locate(quote, text):
    """Where the quoted words are in the message, as (start, end), or None if they aren't there.
    Tries exact, then ignoring case, spacing and punctuation, then a close match (85% of the
    quote's letters, in order, in a span not much longer than the quote)."""
    q = str(quote).strip().strip("\"'“”‘’").strip()
    if len(q) < 2:
        return None
    i = text.find(q)
    if i >= 0:
        return i, i + len(q)
    norm, where = loose(text)
    nq, _ = loose(q)
    if len(nq) < 2:
        return None
    i = norm.find(nq)
    if i >= 0:
        return widen(text, where[i], where[i + len(nq) - 1] + 1)
    blocks = [b for b in difflib.SequenceMatcher(None, norm, nq, autojunk=False).get_matching_blocks() if b.size >= 3]
    if not blocks:
        return None
    start, end = blocks[0].a, blocks[-1].a + blocks[-1].size
    if sum(b.size for b in blocks) >= 0.85 * len(nq) and end - start <= 1.3 * len(nq) + 5:
        return widen(text, where[start], where[end - 1] + 1)
    return None


def widen(text, start, end):
    """Grow a span to whole words."""
    while start > 0 and text[start - 1].isalnum():
        start -= 1
    while end < len(text) and text[end].isalnum():
        end += 1
    return start, end


def same_title(a, b):
    norm = lambda t: re.sub(r"^the ", "", " ".join(re.findall(r"[a-z0-9]+", t.lower())))
    return norm(a) == norm(b)


def entry_ref(value):
    """'e12', 'E12', 12 or '12' -> 12. Anything else -> None."""
    m = re.fullmatch(r"[eE]?(\d+)", str(value).strip()) if value is not None else None
    return int(m.group(1)) if m else None


def check(answer, stretch, shown):
    """answer: what DeepSeek sent. stretch: {message id: message}. shown: {entry id: entry}.
    Returns (headline, entries ready for memory.save_page, problems, notes, asks):
      problems  what's wrong, in plain words, for DeepSeek to fix
      notes     what code fixed by itself (kept in the run's record)
      asks      questions worth asking once: entries that may have gone stale because of an update"""
    problems, notes, asks = [], [], {}
    first, last = min(stretch), max(stretch)
    if not isinstance(answer, dict):
        return None, [], ["The answer must be an object with a headline and a list of entries."], notes, asks

    headline = " ".join(str(answer.get("headline") or "").split())
    if not headline:
        problems.append("The headline is empty.")
        headline = next((m["text"][:80] for m in stretch.values() if m["role"] == "user"), "(no headline)")
    elif len(headline) > 120:
        problems.append("The headline is too long; keep it under 12 words.")
        headline = headline[:120]

    raw = answer.get("entries")
    if not isinstance(raw, list):
        problems.append("entries must be a list (it can be empty).")
        raw = []
    current = {e["id"]: e for e in memory.rows("SELECT * FROM current")}

    # --- A. each entry on its own: handle, kind, title, text, evidence ---
    kept, taken = [], set()
    for i, e in enumerate(raw, 1):
        if not isinstance(e, dict):
            problems.append(f"Entry {i} isn't an object.")
            continue
        handle = str(e.get("handle") or "").strip()
        title = " ".join(str(e.get("title") or "").split())
        name = f'{handle or f"entry {i}"} "{title}"'
        if not re.fullmatch(r"n\d+", handle) or handle in taken:
            problems.append(f"{name}: needs its own handle (n1, n2, ...), different from every other entry's.")
            handle = next(f"n{k}" for k in range(i, 10_000) if f"n{k}" not in taken)
        taken.add(handle)
        kind = str(e.get("kind") or "").strip().lower()
        if kind not in KINDS:
            problems.append(f"{name}: kind must be one of {', '.join(KINDS)}.")
            continue
        if not title:
            problems.append(f"Entry {handle}: the title is empty.")
            continue
        if len(title) > 80:
            problems.append(f"{name}: the title is too long; make it a short name.")
            title = title[:80]
        text = " ".join(str(e.get("text") or "").split())
        if not text:
            problems.append(f"{name}: the text is empty.")
            text = title
        if len(text) > 600:
            problems.append(f"{name}: the text is too long; one or two sentences.")
            text = text[:600]

        evidence = []
        cites = e.get("evidence") if isinstance(e.get("evidence"), list) else []
        for c in cites:
            c = c if isinstance(c, dict) else {}
            mid = entry_ref(str(c.get("message", "")).lstrip("#"))
            quote = str(c.get("quote") or "")
            if mid not in stretch:
                problems.append(f"{name}: #{c.get('message')} isn't in the stretch you were given (#{first} to #{last}).")
                continue
            span = locate(quote, stretch[mid]["text"])
            if span:
                evidence.append((mid, span[0], span[1], 1))
            else:
                problems.append(f'{name}: the quote "{quote[:80]}" isn\'t in #{mid}. Copy the words exactly as they appear there.')
                evidence.append((mid, 0, len(stretch[mid]["text"]), 0))   # if it stays wrong: the whole message
        evidence = list(dict.fromkeys(evidence))
        if any(v[3] for v in evidence):            # found the exact words: drop whole-message fallbacks
            evidence = [v for v in evidence if v[3]]
        if not evidence:
            problems.append(f"{name}: needs evidence: the message number and the exact words it came from.")
            continue
        kept.append({"handle": handle, "name": name, "kind": kind, "title": title, "text": text,
                     "evidence": evidence, "raw_replaces": e.get("replaces"),
                     "raw_links": e.get("links") if isinstance(e.get("links"), list) else []})

    # --- B. updates and duplicates ---
    remap = {}                         # handle of a dropped duplicate -> the entry it duplicates
    replaced = {}
    final = []
    for e in kept:
        hub = e["kind"] in HUBS
        target = None
        if e["raw_replaces"] not in (None, "", "null"):
            ref = entry_ref(e["raw_replaces"])
            if ref is None or not memory.entry(ref):
                problems.append(f"{e['name']}: replaces {e['raw_replaces']}, which doesn't exist. Use an existing entry's handle, or null.")
            else:
                h = memory.head(ref)
                if h != ref:
                    notes.append(f"{e['name']}: replaces e{ref}, an older version; pointed it at the current one, e{h}.")
                if (memory.entry(h)["kind"] in HUBS) != hub:
                    problems.append(f"{e['name']}: is a {e['kind']} but replaces e{h}, a {memory.entry(h)['kind']}. "
                                    "An update keeps the same sort of thing; otherwise link to it instead.")
                elif h in replaced:
                    problems.append(f"{e['name']}: e{h} is already being replaced by {replaced[h]}. Only one new version per entry.")
                else:
                    target = h
        if target is None:
            twin = next((x for x in final if same_title(x["title"], e["title"]) and (x["kind"] in HUBS) == hub), None)
            if twin:
                problems.append(f"{e['name']}: has the same title as {twin['handle']}. Make it one entry.")
                remap[e["handle"]] = twin["handle"]
                continue
            old = next((c for c in current.values() if same_title(c["title"], e["title"]) and (c["kind"] in HUBS) == hub
                        and c["id"] not in replaced), None)
            if old and hub:
                problems.append(f"{e['name']}: e{old['id']} \"{old['title']}\" already exists. Link to e{old['id']} instead "
                                f"of creating it again, or set replaces: e{old['id']} if this changes it.")
                remap[e["handle"]] = old["id"]
                continue
            if old:
                if same_title(old["text"], e["text"]):
                    notes.append(f"{e['name']}: repeats e{old['id']} word for word; left out.")
                    remap[e["handle"]] = old["id"]
                    continue
                problems.append(f"{e['name']}: e{old['id']} \"{old['title']}\" already exists. If this changes it, set "
                                f"replaces: e{old['id']}; if it's something else, give it a different title.")
                target = old["id"]            # if it stays this way: treat it as the new version
        if target:
            replaced[target] = e["handle"]
        e["replaces"] = target
        final.append(e)

    # --- C. links and mentions, now that every handle is settled ---
    handles = {e["handle"] for e in final}

    def resolve(ref):
        """'e12' -> 12 (current version), 'n2' -> 'n2'; a dropped duplicate -> what it duplicated; else None."""
        ref = str(ref).strip()
        if ref in remap:
            return remap[ref]
        if ref in handles:
            return ref
        n = entry_ref(ref)
        return memory.head(n) if n and memory.entry(n) else None

    def label(target):
        return target if isinstance(target, str) else f"e{target}"

    def is_hub(target):
        if isinstance(target, str):
            return next(x for x in final if x["handle"] == target)["kind"] in HUBS
        return memory.entry(target)["kind"] in HUBS

    # hubs an entry can belong to just by naming them: existing ones (unless being replaced) and new ones
    hubs = [(x["id"], x["title"]) for x in current.values() if x["kind"] in HUBS and x["id"] not in replaced]
    hubs += [(x["handle"], x["title"]) for x in final if x["kind"] in HUBS]
    hubs = [(target, title) for target, title in hubs if len(title) >= 3]

    for e in final:
        links, seen = [], set()
        for l in e.pop("raw_links"):
            l = l if isinstance(l, dict) else {}
            target, kind = resolve(l.get("to", "")), str(l.get("kind") or "")
            if target is None:
                problems.append(f"{e['name']}: links to {l.get('to')}, which isn't an entry. Link only to entries listed, or to n-handles in your answer.")
                continue
            if target in (e["handle"], e["replaces"]) or target in seen:
                continue
            if kind not in LINK_KINDS:
                problems.append(f"{e['name']}: link kind '{kind}' should be about, builds_on or related.")
                kind = "related"
            if kind == "about" and not is_hub(target):
                problems.append(f"{e['name']}: 'about' links go to a person or topic; {label(target)} isn't one. Use builds_on or related.")
                kind = "related"
            seen.add(target)
            links.append((target, kind, "model"))
        if len(links) > MAX_LINKS:
            problems.append(f"{e['name']}: has {len(links)} links; keep the {MAX_LINKS} that matter most.")
            links = links[:MAX_LINKS]

        def bracket(m):
            kind, refs = m.group(1), re.findall(r"[en]\d+", m.group(2))
            targets = [(r, resolve(r)) for r in refs]
            for r, target in targets:
                if target is None:
                    problems.append(f"{e['name']}: mentions [{r}], which isn't an entry.")
                elif target not in seen and target not in (e["handle"], e["replaces"]):
                    seen.add(target)       # a mention is a link: the entry depends on what it mentions
                    link = kind.replace(" ", "_") if kind else "builds_on"
                    if link == "about" and not is_hub(target):
                        link = "related"
                    links.append((target, link, "system"))
            if kind or len(refs) > 1:      # "[about e1]" written into the text: it's a link, not words
                notes.append(f"{e['name']}: moved [{m.group(0)[1:-1]}] from the text into its links.")
                return ""
            target = targets[0][1]
            if target is None:
                return ""
            return f"[{target}]" if isinstance(target, str) else f"[e{target}]"
        pattern = r"\[(?:(about|builds_on|builds on|related)\s*:?\s*)?((?:[en]\d+)(?:\s*,\s*[en]\d+)*)\]"
        e["text"] = " ".join(re.sub(pattern, bracket, e["text"]).split()).replace(" .", ".")

        # --- D. a link nobody wrote: the entry names a hub that exists, so it belongs to it ---
        added = 0
        for target, title in hubs:
            if target in seen or target in (e["handle"], e["replaces"]) or added >= 3:
                continue
            if re.search(rf"\b{re.escape(title)}\b", f"{e['title']} {e['text']}", re.I):
                seen.add(target)
                links.append((target, "related" if e["kind"] in HUBS else "about", "system"))
                added += 1
        e["links"] = links

    # --- E. updates can leave other entries stale: ask once about the likely ones ---
    #     (entries written from the same messages as the old version, or built on it)
    updating = {e["replaces"]: e for e in final if e["replaces"]}
    for target, e in updating.items():
        old = [v["id"] for v in memory.chain(target)]
        marks = ",".join("?" * len(old))
        said = memory.rows(f"SELECT DISTINCT entry FROM evidence WHERE message IN "
                           f"(SELECT message FROM evidence WHERE entry IN ({marks}))", *old)
        built = memory.rows(f"SELECT DISTINCT src AS entry FROM links WHERE dst IN ({marks}) AND kind != 'about'", *old)
        for r in said + built:
            other = r["entry"]
            if other in old or other in updating or not memory.is_current(other):
                continue
            o = memory.entry(other)
            reason = "builds on it" if r in built else "was written from the same message"
            asks[other] = (f"{e['name']} updates e{target}. e{other} \"{o['title']}\" {reason} and says: "
                           f"\"{memory.readable(o['text'])}\" If that repeats what changed, also write a new version of e{other} "
                           f"(replaces: e{other}); if not, leave it out of your answer.")

    clean = [{k: e[k] for k in ("handle", "kind", "title", "text", "evidence", "replaces", "links")} for e in final]
    return headline, clean, problems, notes, asks


# ---------------------------------------------------------------------------
# 5. One run: ask, check, repair, save
# ---------------------------------------------------------------------------

def ask(convo):
    payload = {"model": MODEL, "messages": convo, "tools": [TOOL], "max_tokens": 8000,
               "thinking": {"type": "disabled"},
               "tool_choice": {"type": "function", "function": {"name": "write_index"}}}
    return app["ask"](payload)


def read_answer(reply):
    """Pull the write_index arguments out of DeepSeek's reply. Returns (answer, problem)."""
    choice = (reply.get("choices") or [{}])[0]
    msg = choice.get("message") or {}
    calls = [c for c in msg.get("tool_calls") or [] if (c.get("function") or {}).get("name") == "write_index"]
    if choice.get("finish_reason") == "length":
        return None, "Your answer was cut off because it was too long. Write fewer, shorter entries."
    if not calls:
        return None, "You didn't call write_index. Answer only by calling it."
    try:
        return json.loads(calls[0]["function"]["arguments"]), None
    except (json.JSONDecodeError, TypeError) as e:
        return None, f"The write_index arguments weren't valid JSON ({e})."


def cost(usage):
    price = app["prices"].get(MODEL, {})
    hit = usage.get("prompt_cache_hit_tokens", 0)
    miss = usage.get("prompt_cache_miss_tokens", usage.get("prompt_tokens", 0) - hit)
    return (hit * price.get("cache_hit", 0) + miss * price.get("cache_miss", 0)
            + usage.get("completion_tokens", 0) * price.get("output", 0)) / 1e6


def run(first, last):
    """Index messages #first to #last. Returns the run's record (status, page, problems...)."""
    started = time.time()
    stretch = {m["id"]: m for m in memory.messages_between(first, last)}
    shown = entries_to_show(stretch.values())
    convo = prompt(first, last, stretch.values(), shown)
    asked = list(convo)
    replies, problem_log, best, asked_about = [], [], None, set()
    used = {"prompt_tokens": 0, "completion_tokens": 0}

    for attempt in range(1, REPAIRS + 2):
        try:
            reply = ask(convo)
        except Exception as e:
            return record(first, last, "error", attempt, started, asked, replies,
                          problem_log + [[f"couldn't reach DeepSeek: {getattr(e, 'message', e)}"]], used)
        replies.append(reply)
        for k in used:
            used[k] += (reply.get("usage") or {}).get(k, 0)
        answer, problem = read_answer(reply)
        if problem:
            problems, notes, asks, result = [problem], [], {}, None
        else:
            headline, clean, problems, notes, asks = check(answer, stretch, shown)
            result = (headline, clean) if headline is not None else None
        new_asks = [q for other, q in asks.items() if other not in asked_about]
        asked_about |= set(asks)
        problem_log.append(problems + [f"(fixed by code) {n}" for n in notes] + [f"(asked) {q}" for q in new_asks])
        if result and (best is None or len(problems) <= best[2]):
            best = (*result, len(problems))
        if not problems and not new_asks:
            break
        if attempt == REPAIRS + 1:
            break
        msg = (reply.get("choices") or [{}])[0].get("message") or {}
        feedback = ("Some of that can't be saved yet. Fix these and call write_index again with the complete answer "
                    "(everything, not only the fixes):\n- " + "\n- ".join(problems)) if problems else (
                    "That's all valid. One more check, then call write_index again with the complete answer "
                    "(everything, plus any new versions):")
        if new_asks:
            feedback += ("\n\nAlso:\n- " if problems else "\n- ") + "\n- ".join(new_asks)
        calls = msg.get("tool_calls") or []
        if calls:
            convo = convo + [{"role": "assistant", "content": msg.get("content") or "", "tool_calls": calls[:1]},
                             {"role": "tool", "tool_call_id": calls[0].get("id", "call"), "content": feedback}]
        else:
            convo = convo + [{"role": "assistant", "content": msg.get("content") or ""}, {"role": "user", "content": feedback}]

    if best is None:
        status = "failed"
        failures = memory.value("SELECT COUNT(*) FROM runs WHERE first = ? AND status = 'failed'", first) + 1
        if failures < GIVE_UP_AFTER:
            return record(first, last, status, attempt, started, asked, replies, problem_log, used)
        # It keeps failing on this stretch: save a page with no entries so indexing moves on.
        # The messages are still in the log, and recall still searches them directly.
        best = (next((m["text"][:80] for m in stretch.values() if m["role"] == "user"), "(no headline)"), [], 0)
        problem_log.append([f"gave up after {failures} unusable answers; saved the page without entries"])
    else:
        fixed = any(p for p in problem_log[:-1] if any(not x.startswith("(") for x in p))
        status = "partial" if best[2] else "repaired" if fixed else "ok"
    result = record(first, last, status, attempt, started, asked, replies, problem_log, used)
    page_id, made = memory.save_page(first, last, best[0], best[1], result["id"])
    memory.set_run_page(result["id"], page_id)
    return {**result, "page": page_id, "entries": len(made)}


def record(first, last, status, attempts, started, asked, replies, problems, used):
    run_id = memory.save_run(first=first, last=last, status=status, attempts=attempts, model=MODEL,
                             seconds=round(time.time() - started, 1), tokens_in=used["prompt_tokens"],
                             tokens_out=used["completion_tokens"], cost=round(cost(used), 6),
                             prompt=asked, replies=replies, problems=problems)
    if status in ("failed", "error"):
        print(f"Memory: indexing #{first}-#{last} {status}: {problems[-1][:1] if problems else ''}")
    return {"id": run_id, "status": status, "attempts": attempts, "first": first, "last": last,
            "problems": problems, "page": None, "entries": 0}


# ---------------------------------------------------------------------------
# 6. In the background: wake up after each reply (and once a minute), index what's due
# ---------------------------------------------------------------------------

def index_now(force=False):
    """Index everything that's due. force=True also indexes a short stretch right away.
    Returns the runs that happened."""
    results = []
    with RUN_LOCK:
        while (stretch := due(force)) and len(results) < 50:
            result = run(*stretch)
            results.append(result)
            if result["status"] in ("failed", "error"):
                break
    return results


def nudge():
    WAKE.set()


def worker():
    while True:
        WAKE.wait(timeout=60)
        WAKE.clear()
        try:
            index_now()
        except Exception as e:      # never let a bug here take the memory down with it
            print(f"Memory: the indexer hit a problem ({e}); it will try again.")


def start(ask, prices):
    app.update(ask=ask, prices=prices)
    threading.Thread(target=worker, daemon=True).start()
    nudge()
