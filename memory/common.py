"""Small helpers every part of memory uses: the clock, words, handles, finding a quote in a message."""

import difflib
import re
from datetime import datetime

NAME = "Shreyas"        # who Avy is talking to

STOPWORDS = set("""a an and are as at be been but by can could did do does doing for from had has have
he her hers him his how i i'm if in into is it it's its just me my of on or our so than that the their them
then there these they this to too up us very was we were what when where which who whom why will with would
you your yours yeah yes no not ok okay hey hi hello oh um uh like also about any some get got going gonna
want know think tell said say actually really thing things""".split())

REFERS_BACK = set("he him his she her hers they them their it its that this those these there one".split())


class Clock:
    """The current time. Tests and the benchmark set clock.fixed to replay a conversation that spans weeks."""
    fixed = None

    def now(self):
        return self.fixed or datetime.now().astimezone()


clock = Clock()


def now():
    return clock.now()


def stamp():
    return now().isoformat(timespec="seconds")


def when(iso):
    """'2026-10-09T02:10:00-04:00' -> 'Thu Oct 9, 2:10 AM'"""
    t = datetime.fromisoformat(iso)
    return f"{t:%a %b} {t.day}, {t:%I:%M %p}".replace(" 0", " ")


def day(iso):
    """'2026-10-09T02:10:00-04:00' -> 'Oct 9'"""
    t = datetime.fromisoformat(iso)
    return f"{t:%b} {t.day}"


def minutes_between(a, b):
    return (datetime.fromisoformat(b) - datetime.fromisoformat(a)).total_seconds() / 60


def age_days(iso):
    return max(0.0, (now() - datetime.fromisoformat(iso)).total_seconds() / 86400)


def tokens(text):
    return len(text) // 4 + 1   # a rough count: about four characters per token


def who(role):
    return NAME if role == "user" else "Avy"


def clip(text, around, limit):
    """Shorten a long message to `limit` characters, keeping the part near `around`."""
    if len(text) <= limit:
        return text
    start = max(0, min(around - limit // 3, len(text) - limit))
    return ("…" if start else "") + text[start:start + limit] + ("…" if start + limit < len(text) else "")


def terms(text):
    """The words worth searching for: no filler words, no single letters."""
    found = []
    for w in re.findall(r"[a-z0-9]+", text.lower()):
        if len(w) > 1 and w not in STOPWORDS and w not in found:
            found.append(w)
    return found[:24]


def refers_back(text):
    """Does this message lean on the one before it? ("what about him?", "why?")"""
    return len(terms(text)) <= 1 or any(w in REFERS_BACK for w in re.findall(r"[a-z]+", text.lower()))


def same_title(a, b):
    norm = lambda t: re.sub(r"^the ", "", " ".join(re.findall(r"[a-z0-9]+", t.lower())))
    return norm(a) == norm(b)


# --- handles ------------------------------------------------------------------------------------
# A node's handle is its chain: k12 is node 12, whichever version is current. An incognito
# memory's nodes are x12, so a note that mixes both memories can never confuse them.

def node_ref(value, letter="k"):
    """'k12', 'K12', 12 or '12' -> 12 (for the given letter). Anything else -> None."""
    if value is None:
        return None
    m = re.fullmatch(rf"[{letter}{letter.upper()}]?(\d+)", str(value).strip().strip("[]"))
    return int(m.group(1)) if m else None


def edge_ref(value):
    m = re.fullmatch(r"[cC]?(\d+)", str(value).strip()) if value is not None else None
    return int(m.group(1)) if m else None


def message_ref(value):
    m = re.fullmatch(r"#?(\d+)", str(value).strip()) if value is not None else None
    return int(m.group(1)) if m else None


# --- finding a quote in a message -------------------------------------------------------------------

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
