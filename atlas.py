"""The atlas: everything Avy knows, reached as one graph.

Each kind of knowledge keeps the shape that suits it (memory's knowledge is a network, the persona a graph of hubs, the
calendar a timeline, a thread a plan tree, the conversation a log, her code a graph of files and functions). The atlas
doesn't copy any of them: it gives every node one handle and asks the store it lives in for its neighbours, so she can
start anywhere and walk anywhere.

    avy                           the root: one edge to each hub, with what's under it
    self | persona | him | her | us | knowledge | calendar | threads | log | library      the hubs
    k12  memory's knowledge         pa7  the persona            t3  the calendar (timeline)
    th4  a thread (and its plan tree, step by step)            m120  a message in the log
    c:app.py:Turn.ask  her code (selfcode.py)

Edges are named for what they mean (part_of, supports, applies_in, next, belongs_to, step, evidence, calls, ...), and
point both ways where the store keeps them so: what comes back is "→ kind: handle title" and "← kind: handle title".
Built by code from the stores as they are now; the model only chooses where to look.
"""

import re

import selfcode

HUBS = ("self", "persona", "him", "her", "us", "knowledge", "calendar", "threads", "log", "library")


def short(text, n=80):
    text = " ".join(str(text or "").split())
    return text if len(text) <= n else text[:n - 1] + "…"


def look(mem, handle=None):
    h = str(handle or "avy").strip()
    try:
        if h in ("avy", "root", ""):
            return root(mem)
        if h == "self" or h.startswith("c:") or "/" in h or h.endswith((".py", ".html", ".md")):
            return selfcode.look(None if h == "self" else h)
        if h in ("persona", "him", "her", "us"):
            return persona_hub(mem, h)
        if h == "knowledge":
            return mem.core() or "Memory's knowledge is empty so far."
        if h == "calendar":
            return mem.calendar_text()
        if h == "threads":
            return "\n".join(f"- {mem.thread_line(th)}" for th in mem.thread_heads()) or "No threads yet."
        if h == "log":
            last = mem.last_id()
            recent = mem.window(6)
            return (f"The log: {last} messages, oldest m1, newest m{last}. Each message → next / ← previous; persona and "
                    "knowledge nodes rest on them as evidence.\n" + "\n".join(f"- m{m['id']} {m['role']}: {short(m['text'])}" for m in recent))
        if h == "library":
            rows = mem.sources_list(30)
            return ("The library:\n" + "\n".join(f"- {r['name']} ({r['kind']})" for r in rows)) if rows else "The library is empty (or only searchable: use your memory's search)."
        m = re.fullmatch(r"(pa|th|t|m|[a-z])(\d+)", h)
        if not m:
            if selfcode.find_node(h)[0] or selfcode.find_node(h)[1]:
                return selfcode.look(h)
            return f"No node {h!r}. Start at graph_look() (the root) and follow the handles."
        kind, n = m.group(1), int(m.group(2))
        if kind == "pa":
            return persona_node(mem, n)
        if kind == "th":
            return thread(mem, n)
        if kind == "t":
            return timeline(mem, n)
        if kind == "m":
            return message(mem, n)
        return knowledge(mem, n)
    except Exception as e:
        return f"Couldn't look at {h} ({type(e).__name__}: {str(e)[:200]})."


def table(mem, name):
    return bool(mem.rows("SELECT name FROM sqlite_master WHERE type='table' AND name = ?", name))


def root(mem):
    code = selfcode.graph()
    kinds = {}
    for n in code["nodes"].values():
        kinds[n["kind"]] = kinds.get(n["kind"], 0) + 1
    persona = mem.persona_nodes()
    aspects = {}
    for p in persona:
        aspects[p["aspect"]] = aspects.get(p["aspect"], 0) + 1
    threads = mem.thread_heads()
    open_threads = mem.thread_heads(open_only=True)
    coming = [t for t in mem.timeline_heads() if t["status"] == "planned"]
    stats = mem.stats()
    lines = ["avy — everything you know, as one graph. Follow any handle with graph_look(handle).",
             f"→ self: your code and architecture — {kinds.get('file', 0)} files, {kinds.get('function', 0)} functions, "
             f"{kinds.get('endpoint', 0)} endpoints, {kinds.get('doc', 0)} documents (a graph: contains, calls, imports, serves)",
             f"→ persona: who you are with him — {len(persona)} nodes (" + ", ".join(f"{v} {k}" for k, v in sorted(aspects.items())) + "); hubs him, her, us (a graph)",
             f"→ knowledge: what memory knows — {stats.get('nodes', '?')} nodes, {stats.get('connections', '?')} connections (a network)",
             f"→ calendar: {len(coming)} things planned (a timeline: each item → next, → its thread)",
             f"→ threads: {len(open_threads)} open of {len(threads)} (each a plan tree of steps)",
             f"→ log: {mem.last_id()} messages (a timeline: each → next; the evidence everything else rests on)",
             "→ library: what he's added (documents, code, data), searchable from memory"]
    return "\n".join(lines)


def persona_hub(mem, hub):
    if hub == "persona":
        return mem.persona_listing(quotes=False)
    from memory.persona import ASPECTS
    found = [p for p in mem.persona_nodes() if ASPECTS.get(p["aspect"], {}).get("hub") == hub]
    return f"{hub}: {len(found)} nodes\n" + "\n".join(f"→ pa{p['chain']} [{p['aspect']}] {short(p['title'])}" for p in found[:60])


def persona_node(mem, chain):
    n = mem.persona_node(chain)
    if not n:
        return f"No persona node pa{chain}."
    lines = [f"pa{chain} [{n['aspect']}] {n['title']} (v{n['version']}, {n['state']})", short(n.get("text") or "", 600)]
    for e in mem.persona_links(chain):
        other = e["b"] if e["a"] == chain else e["a"]
        o = mem.persona_node(other)
        arrow = "→" if e["a"] == chain else "←"
        lines.append(f"{arrow} {e['kind']}: pa{other} {short(o['title'] if o else '?', 60)} (seen {e['seen']}×)")
    for ev in n.get("evidence", [])[-6:]:
        lines.append(f"← evidence: m{ev['message']} “{short(ev['quote'], 90)}”")
    return "\n".join(lines)


def thread(mem, chain):
    th = mem.thread(chain)
    if not th:
        return f"No thread th{chain}."
    lines = [mem.thread_frontier(th)]
    for t in mem.timeline_heads():
        if t.get("thread") == chain:
            lines.append(f"← belongs_to: t{t['chain']} {t['title']} {t.get('start') or ''}")
    if th.get("source"):
        lines.append(f"← came_from: m{th['source']}")
    return "\n".join(lines)


def timeline(mem, chain):
    t = mem.timeline_item(chain)
    if not t:
        return f"No calendar item t{chain}."
    lines = [mem.timeline_line(t)]
    if t.get("notes"):
        lines.append(t["notes"])
    if t.get("thread"):
        th = mem.thread(t["thread"])
        lines.append(f"→ belongs_to: th{t['thread']} {th['title'] if th else ''}")
    dated = sorted([x for x in mem.timeline_heads() if x.get("start")], key=lambda x: x["start"])
    keys = [x["chain"] for x in dated]
    if chain in keys:
        i = keys.index(chain)
        if i > 0:
            lines.append(f"← previous: t{dated[i - 1]['chain']} {dated[i - 1]['title']} {dated[i - 1]['start']}")
        if i + 1 < len(dated):
            lines.append(f"→ next: t{dated[i + 1]['chain']} {dated[i + 1]['title']} {dated[i + 1]['start']}")
    if t.get("source"):
        lines.append(f"← came_from: m{t['source']} “{short(t.get('quote'), 80)}”")
    return "\n".join(lines)


def message(mem, mid):
    m = mem.message(mid)
    if not m:
        return f"No message m{mid}."
    lines = [f"m{mid} {m['role']} at {m['at']}: {short(m['text'], 1200)}"]
    if mid > 1:
        lines.append(f"← previous: m{mid - 1}")
    if mid < mem.last_id():
        lines.append(f"→ next: m{mid + 1}")
    for r in mem.rows("SELECT DISTINCT p.chain, p.title FROM persona_evidence e JOIN persona p ON p.id = e.node WHERE e.message = ?", mid):
        lines.append(f"→ evidence_for: pa{r['chain']} {short(r['title'], 60)}")
    return "\n".join(lines)


def knowledge(mem, chain):
    rec = mem.node_record(chain)
    if not rec:
        return f"No knowledge node {mem.handle(chain)}."
    n = rec["node"]
    lines = [f"{n['handle']} {n['title']} ({n.get('shape')}, {n.get('standing')})", short(n.get("text") or n.get("body") or "", 600)]
    for l in rec["links"][:24]:
        arrow = "→" if l["direction"] == "out" else "←" if l["direction"] == "in" else "↔"
        lines.append(f"{arrow} {l['kind']}: {l['other']['handle']} {short(l['other']['title'], 60)}" + ("" if l["live"] else " (faded)"))
    for e in (rec["versions"][0].get("evidence") or [])[:6]:
        lines.append(f"← evidence: m{e.get('message')} “{short(e.get('quote'), 80)}”")
    return "\n".join(lines)


TOOL = {"type": "function", "function": {
    "name": "graph_look",
    "description": ("Everything you know is one graph: start at the root (no handle) and follow handles. Hubs: self (your own "
                    "code and architecture), persona, him, her, us, knowledge, calendar, threads, log, library. Nodes: k12 "
                    "(memory), pa7 (persona), t3 (calendar), th4 (thread and its plan tree), m120 (a message), "
                    "c:app.py:Turn (your code). Each look shows the node and its edges (→ out, ← in) to follow next."),
    "parameters": {"type": "object", "properties": {"handle": {"type": "string"}}, "required": []}}}
