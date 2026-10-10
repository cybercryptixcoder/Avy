"""The shape of the network, in numbers, so changes to how memory is built can be compared.

What a healthy network looks like (a "small world", like Wikipedia's links or a brain's wiring):
    islands         few separate pieces: from anywhere you can reach almost everything
    clustering      high: the neighbors of a node tend to be connected to each other (related things group)
    average path    short: a few steps between any two things
    fragile         few nodes held on by a single connection
    hub share       hubs exist, but no handful of nodes holds most of the connections
The random-graph numbers alongside are what the same number of nodes and connections would give if
they were wired at random: clustering well above random and paths about as short is a small world.
"""

import math
import random
from collections import deque


def graph(mem):
    """The network as {chain: set(neighbor chains)}: live edges, plus inferences and what they rest on."""
    adj = {n["chain"]: set() for n in mem.current_nodes()}
    for e in mem.live_edges():
        adj[e["a"]].add(e["b"])
        adj[e["b"]].add(e["a"])
    for r in mem.rows("""SELECT c.chain, b.rests_on FROM current c JOIN basis b ON b.node = c.id
                         WHERE c.origin = 'inferred'"""):
        if r["rests_on"] in adj:
            adj[r["chain"]].add(r["rests_on"])
            adj[r["rests_on"]].add(r["chain"])
    return adj


def distances(adj, start):
    seen, queue = {start: 0}, deque([start])
    while queue:
        v = queue.popleft()
        for w in adj[v]:
            if w not in seen:
                seen[w] = seen[v] + 1
                queue.append(w)
    return seen


def measure(mem, sample=40):
    adj = graph(mem)
    nodes = list(adj)
    n = len(nodes)
    m = sum(len(s) for s in adj.values()) // 2
    nodes_now = mem.current_nodes()
    out = {
        "nodes": n, "connections": m,
        "said_by_you": sum(1 for x in nodes_now if x["origin"] == "user"),
        "said_by_avy": sum(1 for x in nodes_now if x["origin"] == "avy"),
        "inferred": sum(1 for x in nodes_now if x["origin"] == "inferred"),
        "things": sum(1 for x in nodes_now if x["shape"] == "thing"),
        "information": sum(1 for x in nodes_now if x["shape"] == "information"),
        "ideas": sum(1 for x in nodes_now if x["shape"] == "idea"),
        "stale": len(mem.stale_inferences()) + len(mem.stale_edges()),
        "edges_all": mem.value("SELECT COUNT(*) FROM edges"),
    }
    if not n:
        return out
    degree = {v: len(adj[v]) for v in nodes}
    avg_degree = 2 * m / n

    # islands: the separate pieces of the network
    pieces, seen = [], set()
    for v in nodes:
        if v not in seen:
            piece = set(distances(adj, v))
            seen |= piece
            pieces.append(piece)
    largest = max(pieces, key=len)

    # clustering: how often two neighbors of a node are neighbors of each other
    local = []
    for v in nodes:
        k = degree[v]
        if k >= 2:
            nb = list(adj[v])
            links = sum(1 for i in range(k) for j in range(i + 1, k) if nb[j] in adj[nb[i]])
            local.append(links / (k * (k - 1) / 2))

    # average path, sampled inside the largest piece
    rng = random.Random(0)
    starts = rng.sample(sorted(largest), min(sample, len(largest)))
    lengths = [d for s in starts for t, d in distances(adj, s).items() if t != s]

    top = sorted(degree.values(), reverse=True)[:5]
    out.update({
        "islands": len(pieces),
        "largest_share": round(len(largest) / n, 3),
        "isolated": sum(1 for v in nodes if degree[v] == 0),
        "fragile": round(sum(1 for v in nodes if degree[v] == 1) / n, 3),
        "average_degree": round(avg_degree, 2),
        "max_degree": max(degree.values()),
        "hub_share": round(sum(top) / (2 * m), 3) if m else 0,
        "clustering": round(sum(local) / len(local), 3) if local else 0,
        "average_path": round(sum(lengths) / len(lengths), 2) if lengths else 0,
        "random_clustering": round(avg_degree / n, 3) if n else 0,
        "random_path": round(math.log(n) / math.log(avg_degree), 2) if avg_degree > 1 and n > 1 else None,
    })
    return out


def record(mem, run=None):
    import json
    from .common import stamp
    metrics = measure(mem)
    with mem.tx() as db:
        db.execute("INSERT INTO health (at, run, metrics) VALUES (?, ?, ?)", (stamp(), run, json.dumps(metrics)))
    return metrics
