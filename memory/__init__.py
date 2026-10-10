"""
Avy's memory, version 2. It stores and searches; it never calls the model.

    THE LOG        every message, word for word, numbered. Never edited, never deleted.
    KNOWLEDGE      nodes: things, information and ideas, each pointing at the exact words it came
                   from (or, if Avy inferred it, at the nodes it rests on). Changes are new versions.
    THE NETWORK    edges between nodes, each with a kind and a reason, and a strength computed from
                   every reason anyone had to believe it. This layer is alive: connections form,
                   strengthen, fade and get rewired, with all the history kept.

The mind (mind/) is where DeepSeek comes in: it writes knowledge from the log, connects it, and
thinks about it. It only ever proposes; every change comes through Memory.apply (ops.py), which
checks it against the rules (rules.py) and journals it.

A Memory is one file. The parts of the class live in their own files:
    store.py      the file itself          log.py        messages and episodes
    knowledge.py  nodes and versions       network.py    edges, supports, strength
    ops.py        the one door for changes rules.py      what every change must pass
    search.py     meaning + words          recall.py     what each message brings back
    health.py     the network's shape      inspect.py    what the inspector reads
"""

from .common import NAME, clock, now, stamp, when, day, tokens, who, clip, terms, locate, same_title, node_ref, edge_ref, message_ref
from .embed import embedder, EMBED_MODEL
from .health import measure as health, record as record_health
from .inspect import Inspect
from .knowledge import Knowledge, SHAPES, ORIGINS, SAID_BY
from .log import Log, WINDOW, SITTING_GAP
from .network import Network, KINDS, LIVE, MAX_LIVE
from .ops import Ops
from .recall import Recall, DEPTHS, briefing, combine
from .search import Search, top_score, ECHO
from .store import Store


class Memory(Store, Log, Knowledge, Network, Ops, Search, Recall, Inspect):
    """One memory: Memory("data/memory-v2.db"), or Memory(path, name="incognito", letter="x")."""
