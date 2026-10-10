"""The rules every change to memory must pass, whoever proposed it.

Each check returns None (fine) or the reason it's refused, in plain words. The same words go back
to DeepSeek when one of its proposals breaks a rule, so it can fix it. ops.py runs these checks
again at the moment of writing, so nothing gets in around them.

    1. The log is permanent.                        (the database itself refuses edits and deletes)
    2. What was said has evidence: exact words in a real message, copied by code.
    3. What was inferred has a basis: real, current nodes, resting on things Shreyas said in at least two
       different conversations, no more than 3 steps from words actually said.
    4. An inference can't overwrite what was said. Only Shreyas's own words can.
    5. Versions never fork: a new version follows the newest one.
    6. Shreyas himself is never a node: he's the one all of it is about.
    7. One node per thing: no two current nodes of the same shape with the same title.
    8. Edges join two real, current, different nodes, with an allowed kind and a reason.
       A connection Shreyas made himself needs his words.
    9. Strength only comes from supports, and supports are never changed or deleted.
"""

import re

from .common import NAME, same_title
from .knowledge import SHAPES
from .network import KINDS, SUPPORTS

MAX_DEPTH = 3
SELF = {"me", "myself", "i", "you", "user", "the user", NAME.lower(), f"{NAME.lower()} himself", "about me"}


def node_name(mem, chain):
    h = mem.head(chain)
    return f'{mem.handle(chain)} "{h["title"]}"' if h else mem.handle(chain)


def check_node(mem, op):
    """A new node, or a new version of one. Returns (why, derived): derived holds what code decides:
    origin, depth, the chain it continues, and the evidence as (message, start, end, exact)."""
    title = " ".join(str(op.get("title") or "").split())
    text = " ".join(str(op.get("text") or "").split())
    if op.get("shape") not in SHAPES:
        return f"shape must be thing, information or idea (not {op.get('shape')!r}).", None
    if not title:
        return "the title is empty.", None
    if len(title) > 90:
        return "the title is too long; make it a short name.", None
    if not text:
        return "the text is empty.", None
    if len(text) > 800:
        return "the text is too long; one or two sentences.", None
    if " ".join(re.findall(r"[a-z]+", title.lower())) in SELF:
        return (f"{NAME} himself isn't a node: everything in memory is about him already. Write what you "
                f"know as information about the thing it concerns (his sleep, his job, his course).", None)
    if op.get("about") and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(op["about"])):
        return "'when' must be a date written YYYY-MM-DD, or null.", None

    evidence, basis = op.get("evidence") or [], op.get("basis") or []
    if evidence and basis:
        return "a node rests either on words that were said (evidence) or on other nodes (basis), not both.", None
    if not evidence and not basis:
        return "needs evidence: the message number and the exact words it came from.", None

    replaced = None
    if op.get("replaces") is not None:
        replaced = mem.head(op["replaces"])
        if not replaced:
            return f"replaces {mem.handle(op['replaces'])}, which doesn't exist.", None
        if (replaced["shape"] == "thing") != (op["shape"] == "thing"):
            return (f"replaces {node_name(mem, replaced['chain'])}, a {replaced['shape']}, with a {op['shape']}. "
                    "A new version keeps the same sort of thing; otherwise connect to it instead.", None)

    derived = {"chain": replaced["chain"] if replaced else None, "version": replaced["version"] + 1 if replaced else 1,
               "replaces_row": replaced["id"] if replaced else None}

    if evidence:                                         # said: by whom is decided by the messages
        roles = []
        for mid, start, end, exact in evidence:
            m = mem.row("SELECT id, role, length(text) AS n FROM messages WHERE id = ?", mid)
            if not m:
                return f"#{mid} isn't a message.", None
            if not (0 <= start < end <= m["n"]):
                return f"the words pointed at in #{mid} are outside the message.", None
            roles.append(m["role"])
        derived.update(origin="user" if "user" in roles else "avy", depth=0, certainty=None)
    else:                                                # inferred: rests on other nodes
        if op.get("certainty") not in ("likely", "possible"):
            return "an inference needs a certainty: likely or possible.", None
        heads = []
        for chain in dict.fromkeys(basis):
            h = mem.current(chain)
            if not h:
                return f"rests on {mem.handle(chain)}, which isn't a current node.", None
            if replaced and chain == replaced["chain"]:
                return "an inference can't rest on itself.", None
            heads.append(h)
        if not any(h["origin"] != "inferred" for h in heads):
            return ("rests only on other inferences. Every inference must rest at least partly on something "
                    "that was actually said, so it can always be traced back to real words.", None)
        if op["certainty"] == "likely" and len(heads) < 2:
            return "a 'likely' inference needs at least two nodes to rest on; with one, it's 'possible'.", None
        if len(conversations(mem, heads)) < 2:
            return (f"rests on what {NAME} said in fewer than two conversations. Inferences connect what he said across time "
                    "(within one conversation, what was said is already written down as it is), and Avy's own suggestions "
                    "can't be the ground for one.", None)
        depth = 1 + max(h["depth"] for h in heads)
        if depth > MAX_DEPTH:
            return f"is {depth} steps from anything actually said; the limit is {MAX_DEPTH}.", None
        if replaced and replaced["origin"] != "inferred":
            return (f"would overwrite {node_name(mem, replaced['chain'])}, which was said in the conversation. "
                    "An inference can't replace what was said; only Shreyas's own words can.", None)
        derived.update(origin="inferred", depth=depth, certainty=op["certainty"], heads=heads)

    for c in mem.rows("SELECT * FROM current WHERE shape = ?", op["shape"]):
        if same_title(c["title"], title) and (not replaced or c["chain"] != replaced["chain"]):
            return (f"{node_name(mem, c['chain'])} already exists with this title. If this changes it, make it a "
                    f"new version (replaces: {mem.handle(c['chain'])}); if it's something else, give it a different title.", None)
    derived.update(title=title, text=text)
    return None, derived


def conversations(mem, heads, depth=0):
    """The conversations (episodes) in which Shreyas said the things under these nodes. Avy's own
    suggestions don't count: an inference must rest on what he said."""
    found = set()
    for h in heads:
        if h["origin"] == "user":
            if h["episode"]:
                found.add(h["episode"])
        elif depth < 3:
            found |= conversations(mem, [b["now"] for b in mem.basis_of(h["id"]) if b["now"]], depth + 1)
    return found


def check_retract(mem, op):
    h = mem.head(op.get("chain"))
    if not h:
        return f"{mem.handle(op.get('chain'))} doesn't exist."
    if h["state"] != "active":
        return f"{node_name(mem, h['chain'])} is already retracted."
    if h["origin"] != "inferred" and not op.get("evidence"):
        return (f"{node_name(mem, h['chain'])} was said in the conversation; only Shreyas's own words can take it back. "
                "If something changed, write a new version instead.")
    if not str(op.get("why") or "").strip():
        return "a retraction needs a reason."
    return None


def check_connect(mem, op):
    """A connection (or one more support for an existing one). Returns (why, existing edge or None)."""
    a, b, kind = op.get("a"), op.get("b"), op.get("kind")
    support = op.get("support") or {}
    if a == b:
        return "connects a node to itself.", None
    for end in (a, b):
        if not isinstance(end, int) or not mem.current(end):
            return f"connects {mem.handle(end) if isinstance(end, int) else end}, which isn't a current node.", None
    if kind not in KINDS:
        return f"connection kind must be one of {', '.join(KINDS)} (not {kind!r}).", None
    reason = " ".join(str(op.get("reason") or "").split())
    if len(reason.split()) < 3:
        return "a connection needs a reason: one short sentence saying why these two belong together.", None
    if len(reason) > 300:
        return "the reason is too long; one short sentence.", None
    if support.get("kind") not in SUPPORTS or support.get("sign", 1) not in (1, -1):
        return f"unknown support {support!r}.", None
    if support["kind"] == "stated":
        quote = op.get("quote")
        m = mem.row("SELECT role, length(text) AS n FROM messages WHERE id = ?", quote[0]) if quote else None
        if not m or m["role"] != "user" or not (0 <= quote[1] < quote[2] <= m["n"]):
            return f"a connection {NAME} made himself needs his exact words, from one of his messages.", None
    return None, mem.edge_between(a, b)


def check_edge(mem, op):
    e = mem.edge(op.get("edge"))
    if not e:
        return f"c{op.get('edge')} isn't a connection."
    if op.get("kind") is not None and op["kind"] not in KINDS:
        return f"connection kind must be one of {', '.join(KINDS)}."
    if op.get("op") == "revise_edge" and op.get("reason") is not None and len(str(op["reason"]).split()) < 3:
        return "a connection needs a reason: one short sentence."
    return None


def check_episode(mem, op):
    start = mem.written_up_to() + 1
    if op.get("first") != start:
        return f"episodes follow each other: the next one starts at #{start}."
    if not (op["first"] <= op.get("last", 0) <= mem.last_id()):
        return "the episode's last message isn't in the log."
    if not str(op.get("headline") or "").strip():
        return "the headline is empty."
    return None
