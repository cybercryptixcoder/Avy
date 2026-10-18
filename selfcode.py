"""Avy's model of herself: her own code as a graph, and her hands on it.

The graph is built by code, never by the model, from the files as they are now (rebuilt when any of them changes):

    c:app.py                      a file (its docstring's first line, its size)
    c:app.py:Turn                 a class          c:app.py:Turn.ask     a method or function
    c:index.html:send             a function in the page's script
    c:/api/desk                   an endpoint the server answers (and the page functions that call it)
    c:docs/PERSONA.md             a document, with its headings

    edges: contains (file -> class -> method), imports (file -> file), calls (function -> function, by name),
           calls_api (page function -> endpoint), serves (endpoint -> the file that answers it),
           mentions (document -> the files and names it talks about)

Her tools (TOOLS, carried out by use()):
    self_look   the architecture at a glance, one node and its neighbours, or a search over names, docstrings and lines
    self_read   the source of a node (a function, a class) or a file's lines
    self_edit   change a file of her own (exact replace, or a whole new file), always with a reason. Python and JSON are
                checked BEFORE anything is written, so a broken file never lands; each change is its own git commit
                ("Avy: <why>"), so any of them can be looked at and undone
    self_ops    check (compile everything, run the offline tests), history, diff, revert a change, restart herself

Safety: every self_edit, revert and restart asks him on the page first unless /hands: trusted; her constitution
(CONSTITUTION.md) asks him always, whatever the setting. Keys (.env) and data/ are never hers to edit here.
"""

import ast
import json
import os
import re
import subprocess
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SKIP_DIRS = {".git", "data", "__pycache__", "node_modules", ".venv", "venv", "jobs/results", ".github"}
KINDS = (".py", ".html", ".md", ".txt", ".json", ".yml", ".sql", ".toml")
ALWAYS_ASK = {"CONSTITUTION.md"}
NEVER = re.compile(r"(^|/)(\.env\b|data/|\.git/)")
READ_LINES = 260
HOOKS = {"approve": None, "restart": None}    # app.py sets these (the turn's approval; restarting the server)
_LOCK = threading.Lock()
_CACHE = {"key": None, "graph": None}


# ---------------------------------------------------------------------------------------------------------------
# The graph
# ---------------------------------------------------------------------------------------------------------------

def files():
    out = []
    for p in sorted(ROOT.rglob("*")):
        rel = p.relative_to(ROOT).as_posix()
        if not p.is_file() or p.suffix not in KINDS or rel.split("/")[0].startswith(".") or any(rel == d or rel.startswith(d + "/") or f"/{d}/" in f"/{rel}" for d in SKIP_DIRS):
            continue
        out.append(rel)
    return out


def graph():
    """{"nodes": {id: {...}}, "edges": [(a, kind, b)]}, rebuilt only when a file changed."""
    paths = files()
    key = tuple((p, (ROOT / p).stat().st_mtime_ns) for p in paths)
    with _LOCK:
        if _CACHE["key"] != key:
            _CACHE["graph"], _CACHE["key"] = build(paths), key
        return _CACHE["graph"]


def build(paths):
    nodes, edges, defs = {}, [], {}            # defs: short name -> [node ids], for resolving calls
    calls_of = {}

    def add(nid, **kw):
        nodes[nid] = {"id": nid, **kw}

    modules = {p[:-3].replace("/", "."): p for p in paths if p.endswith(".py")}
    for mod, p in list(modules.items()):
        if mod.endswith(".__init__"):
            modules[mod[:-9]] = p
    for p in paths:
        text = (ROOT / p).read_text(errors="replace")
        lines = text.count("\n") + 1
        fid = f"c:{p}"
        if p.endswith(".py"):
            try:
                tree = ast.parse(text)
            except SyntaxError as e:
                add(fid, kind="file", path=p, lines=lines, about=f"(doesn't parse: line {e.lineno}: {e.msg})")
                continue
            add(fid, kind="file", path=p, lines=lines, about=first_line(ast.get_docstring(tree)))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for a in node.names:
                        target = resolve_module(a.name, modules)
                        target and edges.append((fid, "imports", f"c:{target}"))
                elif isinstance(node, ast.ImportFrom) and node.module:
                    base = node.module if not node.level else ".".join(p.split("/")[:-node.level] + [node.module])
                    target = resolve_module(base, modules)
                    target and edges.append((fid, "imports", f"c:{target}"))
                    for a in node.names:
                        sub = resolve_module(f"{base}.{a.name}", modules)
                        sub and edges.append((fid, "imports", f"c:{sub}"))

            def walk(body, parent, prefix):
                for n in body:
                    if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                        q = f"{prefix}{n.name}"
                        nid = f"c:{p}:{q}"
                        kind = "class" if isinstance(n, ast.ClassDef) else "function"
                        add(nid, kind=kind, path=p, name=q, start=n.lineno, end=n.end_lineno,
                            sig=signature(n), about=first_line(ast.get_docstring(n)))
                        edges.append((parent, "contains", nid))
                        defs.setdefault(n.name, []).append(nid)
                        if kind == "function":
                            calls_of[nid] = called_names(n)
                        walk(n.body, nid, q + ".")
            walk(tree.body, fid, "")
            if p == "app.py":
                for api in sorted(set(re.findall(r'"(/api/[a-z_/-]+)"', text))):
                    add(f"c:{api}", kind="endpoint", path=p, name=api, about="answered by app.py's Handler")
                    edges.append((f"c:{api}", "serves", fid))
        elif p.endswith(".html"):
            add(fid, kind="file", path=p, lines=lines, about="the page: everything you see, its styles and its script")
            starts = [(m.start(), m.group(1)) for m in re.finditer(r"^(?:async\s+)?function\s+(\w+)\s*\(", text, re.M)]
            for i, (pos, name) in enumerate(starts):
                end = starts[i + 1][0] if i + 1 < len(starts) else len(text)
                body = text[pos:end]
                line = text.count("\n", 0, pos) + 1
                nid = f"c:{p}:{name}"
                comment = re.search(r"((?:^//[^\n]*\n)+)\Z", text[max(0, pos - 600):pos], re.M)
                add(nid, kind="function", path=p, name=name, start=line, end=line + body.count("\n") - 1,
                    sig=f"function {name}(...)", about=first_line((comment.group(1).replace("//", " ") if comment else "")))
                edges.append((fid, "contains", nid))
                defs.setdefault(name, []).append(nid)
                calls_of[nid] = set(re.findall(r"(?<![.\w])([A-Za-z_]\w*)\s*\(", body)) - {name}
                for api in set(re.findall(r'["`](/api/[a-z_/-]+)', body)):
                    edges.append((nid, "calls_api", f"c:{api}"))
        else:
            heads = [(i + 1, l.lstrip("#").strip()) for i, l in enumerate(text.splitlines()) if p.endswith(".md") and l.startswith("#")]
            add(fid, kind="doc" if p.endswith(".md") else "file", path=p, lines=lines,
                about=heads[0][1] if heads else first_line(text), heads=heads[:60])
    # calls, resolved by name: same file first, else a name defined only once anywhere
    for nid, names in calls_of.items():
        path = nodes[nid]["path"]
        for name in names:
            found = defs.get(name) or []
            here = [d for d in found if nodes[d]["path"] == path]
            for target in (here or (found if len(found) == 1 else [])):
                if target != nid:
                    edges.append((nid, "calls", target))
    # documents mention files and well-known names
    names = {nodes[n]["path"].rsplit("/", 1)[-1]: f"c:{nodes[n]['path']}" for n in nodes if nodes[n]["kind"] == "file"}
    for nid, n in list(nodes.items()):
        if n["kind"] == "doc":
            text = (ROOT / n["path"]).read_text(errors="replace")
            for word in set(re.findall(r"[\w/.-]+\.(?:py|html|md|json)", text)):
                target = f"c:{word}" if f"c:{word}" in nodes else names.get(word.rsplit("/", 1)[-1])
                if target and target != nid:
                    edges.append((nid, "mentions", target))
    return {"nodes": nodes, "edges": sorted(set(edges)), "built": time.time()}


def resolve_module(name, modules):
    while name:
        if name in modules:
            return modules[name]
        name = name.rpartition(".")[0]
    return None


def called_names(fn):
    out = set()
    for n in ast.walk(fn):
        if isinstance(n, ast.Call):
            f = n.func
            out.add(f.id if isinstance(f, ast.Name) else f.attr if isinstance(f, ast.Attribute) else None)
    out.discard(None)
    return out


def signature(n):
    if isinstance(n, ast.ClassDef):
        return f"class {n.name}"
    try:
        return f"def {n.name}({ast.unparse(n.args)})"
    except Exception:
        return f"def {n.name}(...)"


def first_line(text):
    for line in (text or "").strip().splitlines():
        line = line.strip(" #/*-")
        if line:
            return line[:160]
    return ""


def neighbours(nid):
    g = graph()
    out, inn = [], []
    for a, kind, b in g["edges"]:
        if a == nid and b in g["nodes"]:
            out.append((kind, b))
        elif b == nid and a in g["nodes"]:
            inn.append((kind, a))
    return out, inn


def find_node(ref):
    """A node from what she wrote: c:app.py:Turn.ask, app.py:Turn.ask, Turn.ask, ask, /api/desk, app.py."""
    g = graph()["nodes"]
    ref = str(ref or "").strip()
    for cand in (ref, "c:" + ref, "c:" + ref.lstrip("/") if not ref.startswith("/api") else "c:" + ref):
        if cand in g:
            return g[cand], []
    short = ref.removeprefix("c:")
    found = [n for n in g.values() if n.get("name") and (n["name"] == short or n["name"].endswith("." + short))]
    return (found[0], []) if len(found) == 1 else (None, found[:12])


# ---------------------------------------------------------------------------------------------------------------
# Looking
# ---------------------------------------------------------------------------------------------------------------

def overview():
    """The architecture at a glance: every file of hers with what it is, grouped by folder."""
    g = graph()
    counts = {}
    for n in g["nodes"].values():
        counts[n["kind"]] = counts.get(n["kind"], 0) + 1
    groups = {}
    for n in g["nodes"].values():
        if n["kind"] in ("file", "doc"):
            folder = n["path"].rsplit("/", 1)[0] if "/" in n["path"] else "."
            groups.setdefault(folder, []).append(n)
    lines = [f"Your code ({ROOT}), as a graph: {counts.get('file', 0)} code files, {counts.get('function', 0)} functions, "
             f"{counts.get('class', 0)} classes, {counts.get('endpoint', 0)} endpoints, {counts.get('doc', 0)} documents, "
             f"{len(g['edges'])} connections. Look at any node with self_look(node=...)."]
    for folder in sorted(groups, key=lambda f: (f != ".", f)):
        lines.append(f"\n{folder}/")
        for n in sorted(groups[folder], key=lambda n: n["path"]):
            lines.append(f"  {n['path'].rsplit('/', 1)[-1]} ({n['lines']} lines): {n.get('about') or ''}"[:200])
    return "\n".join(lines)


def look(node=None, search=None):
    if search:
        return search_code(search)
    if not node:
        return overview()
    n, maybe = find_node(node)
    if not n:
        if maybe:
            return "Several match; pick one:\n" + "\n".join(f"- {m['id']} ({m['kind']}) {m.get('about', '')}"[:180] for m in maybe)
        return f"No node {node!r}. self_look() lists the files; self_look(search=...) finds names and lines."
    out, inn = neighbours(n["id"])
    g = graph()["nodes"]
    head = [f"{n['id']} — {n['kind']}" + (f", lines {n['start']}-{n['end']}" if n.get("start") else f", {n.get('lines')} lines" if n.get("lines") else "")]
    if n.get("sig"):
        head.append(n["sig"])
    if n.get("about"):
        head.append(n["about"])
    if n.get("heads"):
        head.append("headings: " + " · ".join(f"{h} (l{i})" for i, h in n["heads"][:30]))

    def group(pairs, arrow):
        by = {}
        for kind, other in pairs:
            by.setdefault(kind, []).append(other)
        return [f"{arrow} {kind} ({len(v)}): " + ", ".join(x.removeprefix("c:") + (f" — {g[x]['about'][:60]}" if kind == "contains" and g[x].get("about") else "") for x in v[:40])
                + (" …" if len(v) > 40 else "") for kind, v in sorted(by.items())]
    return "\n".join(head + group(out, "→") + group(inn, "←"))


def search_code(query, limit=40):
    g = graph()["nodes"]
    q = query.lower()
    hits = [n for n in g.values() if q in (n.get("name") or n.get("path", "")).lower() or q in (n.get("about") or "").lower()]
    lines = [f"Nodes ({len(hits)}):"] + [f"- {n['id']} ({n['kind']}) {n.get('about', '')}"[:170] for n in hits[:20]]
    try:
        rx = re.compile(query, re.I)
    except re.error:
        rx = re.compile(re.escape(query), re.I)
    found = []
    for p in files():
        for i, line in enumerate((ROOT / p).read_text(errors="replace").splitlines(), 1):
            if rx.search(line):
                found.append(f"{p}:{i}: {line.strip()[:150]}")
                if len(found) >= limit:
                    break
        if len(found) >= limit:
            break
    return "\n".join(lines + [f"\nLines ({len(found)}{'+' if len(found) >= limit else ''}):"] + found)


def read(node=None, path=None, offset=None, limit=None):
    if node:
        n, maybe = find_node(node)
        if not n:
            return look(node)
        path = n["path"]
        if n.get("start") and not offset:
            offset, limit = n["start"], (n["end"] - n["start"] + 1) if not limit else limit
    if not path:
        return "Name a node or a path."
    p = (ROOT / path).resolve()
    if not str(p).startswith(str(ROOT)) or not p.is_file():
        return f"There's no file {path} in your code."
    if NEVER.search(p.relative_to(ROOT).as_posix()):
        return "That isn't yours to read here (keys and data stay out)."
    lines = p.read_text(errors="replace").splitlines()
    start = max(1, int(offset or 1))
    take = min(int(limit or READ_LINES), 600)
    chunk = lines[start - 1:start - 1 + take]
    more = f"\n… {len(lines) - (start - 1 + take)} more lines (offset={start + take})" if start - 1 + take < len(lines) else ""
    return f"{path} ({len(lines)} lines)\n" + "\n".join(f"{i:>5}  {l}" for i, l in enumerate(chunk, start)) + more


# ---------------------------------------------------------------------------------------------------------------
# Changing
# ---------------------------------------------------------------------------------------------------------------

def git(*args, timeout=60):
    r = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, timeout=timeout)
    return r.returncode, (r.stdout + r.stderr).strip()


def ask(kind, detail, why, mode, always=False):
    if mode == "trusted" and not always:
        return None
    approve = HOOKS["approve"]
    if approve and approve({"kind": kind, "detail": detail, "why": why}):
        return None
    return "Not done: he didn't approve it. Say what you wanted to change and why, and let him decide."


def checked(path, text):
    """None if the new text is fine to write, else what's wrong with it (checked before writing)."""
    try:
        if path.endswith(".py"):
            compile(text, path, "exec")
        elif path.endswith(".json"):
            json.loads(text)
    except SyntaxError as e:
        return f"Not written: that would break {path} (syntax error at line {e.lineno}: {e.msg}). Fix it and try again."
    except json.JSONDecodeError as e:
        return f"Not written: invalid JSON at line {e.lineno}: {e.msg}."
    return None


def edit(path, old=None, new=None, content=None, why="", replace_all=False, mode="ask"):
    path = str(path or "").strip().lstrip("/").removeprefix("c:")
    p = (ROOT / path).resolve()
    if not path or not str(p).startswith(str(ROOT)) or NEVER.search(path):
        return f"{path or 'That'} isn't one of your code files (keys, data and .git aren't edited here)."
    if not why:
        return "Say why (why=...): every change to yourself is recorded with its reason."
    if content is None:
        if not p.is_file():
            return f"There's no {path} (give content= to create it)."
        text = p.read_text()
        n = text.count(old or "")
        if not old or n == 0:
            return "The old text isn't in the file exactly as given. self_read it and copy the lines exactly."
        if n > 1 and not replace_all:
            return f"That text appears {n} times; include more lines so it's unique, or set replace_all."
        after = text.replace(old, new or "") if replace_all else text.replace(old, new or "", 1)
    else:
        after = content
    problem = checked(path, after)
    if problem:
        return problem
    before = p.read_text() if p.is_file() else ""
    added = sum(1 for _ in after.splitlines()) - sum(1 for _ in before.splitlines())
    refused = ask("change her own code", f"{path}: {why}" + (f"\n− {old[:200]}\n+ {(new or '')[:200]}" if content is None else f" (whole file, {len(after):,} chars)"),
                  "she changes her own code" + (" — her constitution" if path in ALWAYS_ASK else ""), mode, always=path in ALWAYS_ASK)
    if refused:
        return refused
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(after)
    commit = commit_change([path], why)
    when = ("a page reload (index.html)" if path.endswith(".html") else
            "the next message (it's read fresh)" if path.endswith(".md") and not path.startswith("docs/") else
            "self_ops(restart) after self_ops(check)" if path.endswith(".py") else "whatever reads it next")
    return (f"Changed {path} ({'+' if added >= 0 else ''}{added} lines){', ' + commit if commit else ''}. "
            f"Takes effect after {when}.")


def commit_change(paths, why):
    if git("rev-parse", "--git-dir")[0] != 0:
        return ""
    name = git("config", "user.name")[1] or "cybercryptixcoder"
    email = git("config", "user.email")[1] or "official.shreyas28@gmail.com"
    git("add", "--", *paths)
    code, out = git("-c", f"user.name={name}", "-c", f"user.email={email}", "commit", "-q", "-m", f"Avy: {why}", "--", *paths)
    if code:
        return f"not committed ({out[:120]})"
    return "commit " + git("rev-parse", "--short", "HEAD")[1]


def check():
    """Everything compiles, the offline tests pass, and the server module imports: what she runs before restarting."""
    lines, ok = [], True
    for p in files():
        if p.endswith(".py"):
            try:
                compile((ROOT / p).read_text(), p, "exec")
            except SyntaxError as e:
                ok = False
                lines.append(f"✗ {p}:{e.lineno}: {e.msg}")
    lines.append("✓ every Python file compiles" if ok else "✗ some files don't compile")
    r = subprocess.run([sys.executable, "-c", "import app"], cwd=ROOT, capture_output=True, text=True, timeout=120,
                       env={**os.environ, "AVY_NO_BROWSER": "1"})
    if r.returncode:
        ok = False
        lines.append("✗ app.py doesn't import:\n" + r.stderr.strip()[-1500:])
    else:
        lines.append("✓ app.py imports")
    for test in ("tests/test_desk.py", "tests/test_self.py"):
        if (ROOT / test).exists():
            try:
                r = subprocess.run([sys.executable, test], cwd=ROOT, capture_output=True, text=True, timeout=300)
                tail = (r.stdout + r.stderr).strip().splitlines()[-6:]
                ok = ok and r.returncode == 0
                lines.append(("✓ " if r.returncode == 0 else "✗ ") + test + ": " + " | ".join(tail)[-600:])
            except subprocess.TimeoutExpired:
                ok = False
                lines.append(f"✗ {test}: took longer than 5 minutes")
    return ("All good: safe to restart." if ok else "Not safe to restart yet.") + "\n" + "\n".join(lines), ok


def ops(action, commit=None, mode="ask"):
    if action == "check":
        return check()[0]
    if action == "history":
        return git("log", "--oneline", "-25", "--", ".")[1] or "No history (this isn't a git checkout)."
    if action == "diff":
        target = commit or "HEAD"
        return git("show", "--stat", "--patch", "--format=%h %s (%ar)", target)[1][:12000]
    if action == "status":
        return git("status", "--short")[1] or "Nothing changed since the last commit."
    if action == "revert":
        if not commit:
            return "Name the commit to undo (self_ops(history) lists them)."
        refused = ask("undo a change to herself", f"git revert {commit}", "she undoes a change to her own code", mode)
        if refused:
            return refused
        code, out = git("revert", "--no-edit", commit)
        return (f"Undid {commit}: " if code == 0 else "Couldn't undo it: ") + out[:800]
    if action == "restart":
        text, ok = check()
        if not ok:
            return text + "\nNot restarting: fix what's broken first (or revert the change)."
        refused = ask("restart herself", "restart the server to run her changed code", "the page reconnects in a few seconds", mode)
        if refused:
            return refused
        if HOOKS["restart"]:
            HOOKS["restart"]()
            return "Restarting as soon as this reply ends (the page reconnects by itself). " + text.splitlines()[0]
        return "There's no server to restart here."
    return f"Unknown action {action}."


# ---------------------------------------------------------------------------------------------------------------
# Her tools
# ---------------------------------------------------------------------------------------------------------------

def tool(name, description, properties, required):
    return {"type": "function", "function": {"name": name, "description": description,
                                             "parameters": {"type": "object", "properties": properties, "required": required}}}


TOOLS = [
    tool("self_look", "Your own code, as a graph: with nothing, every file of yours and what it is (the architecture); with "
                      "node (like app.py:Turn.ask, Turn, index.html:send, /api/desk, memory/desk.py), that node, its signature "
                      "and docstring, and everything it connects to (contains, calls, called by, imports, endpoints); with "
                      "search, names, docstrings and lines matching it. Look before you change anything.",
         {"node": {"type": "string"}, "search": {"type": "string"}}, []),
    tool("self_read", "Read your own source: a node (a function or class, whole) or a file's lines (offset, limit).",
         {"node": {"type": "string"}, "path": {"type": "string"}, "offset": {"type": "integer"}, "limit": {"type": "integer"}}, []),
    tool("self_edit", "Change your own code: replace an exact piece of a file (old -> new; copy old from self_read, with enough "
                      "lines to be unique) or write a whole file (content). Always say why. Python and JSON are checked before "
                      "writing, so a broken file never lands; each change is its own commit you can undo. He approves each "
                      "change on the page. Keep changes small and in the style of the code around them.",
         {"path": {"type": "string"}, "old": {"type": "string"}, "new": {"type": "string"}, "content": {"type": "string"},
          "why": {"type": "string"}, "replace_all": {"type": "boolean"}}, ["path", "why"]),
    tool("self_ops", "After changing yourself: check (everything compiles, the server imports, the offline tests pass), "
                     "status, history (your recent changes), diff (one change), revert (undo a commit), restart (run your "
                     "changed server code: checks first, then restarts once this reply ends; the page reconnects).",
         {"action": {"type": "string", "enum": ["check", "status", "history", "diff", "revert", "restart"]},
          "commit": {"type": "string"}}, ["action"]),
]
NAMES = {t["function"]["name"] for t in TOOLS}


def use(name, args, mode="ask"):
    a = args if isinstance(args, dict) else {}
    try:
        if name == "self_look":
            out = look(a.get("node"), a.get("search"))
            return out, f"looked at {a.get('node') or ('“' + a['search'] + '”' if a.get('search') else 'her architecture')}"
        if name == "self_read":
            return read(a.get("node"), a.get("path"), a.get("offset"), a.get("limit")), f"read her {a.get('node') or a.get('path')}"
        if name == "self_edit":
            out = edit(a.get("path"), a.get("old"), a.get("new"), a.get("content"), a.get("why") or "", bool(a.get("replace_all")), mode)
            return out, ("changed " if out.startswith("Changed") else "tried to change ") + f"{a.get('path')} · {str(a.get('why') or '')[:60]}"
        if name == "self_ops":
            out = ops(a.get("action") or "status", a.get("commit"), mode)
            return out, f"self · {a.get('action')}" + (f" {a.get('commit')}" if a.get("commit") else "") + f" · {out.splitlines()[0][:50]}"
    except Exception as e:
        return f"That failed ({type(e).__name__}: {str(e)[:300]}).", f"{name} failed"
    return f"There's no tool called {name}.", None


if __name__ == "__main__":
    print(look(sys.argv[1]) if len(sys.argv) > 1 else overview())
