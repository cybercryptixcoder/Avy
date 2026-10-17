"""Avy's hands: what she can do, not just say. A terminal, files, Python, the web, and jobs that keep running.

    terminal     run a shell command in her workspace (data/workspace by default). The working directory carries over
                 between commands; long output is cut to its head and tail, with the whole of it saved to a file.
                 background=true starts a job (j3) that keeps running; when it ends, code notes it on the thread it
                 belongs to and tells the page, so a long run is picked up exactly where it was left (VISION §10).
    jobs         look at, read, wait for or stop background jobs
    read_file, write_file, edit_file, find_files
    python       run a short Python program (for anything that's arithmetic, data, or a quick check)
    web_search   search the web (no key needed: the ddgs package; a SearXNG address or Brave key can be set instead)
    web_fetch    read a web page or PDF as text; long pages come back as head and tail, the whole saved to a file
    playbook     read one of her playbooks: how she goes about a kind of work (playbooks/*.md)

Safety, in two tiers (the shape of it comes from open-source agents that run commands on people's machines):
    blocked   never runs, whatever anyone says: wiping a disk or home, formatting, fork bombs, shutting down
    ask       runs only once he says yes on the page (or in the terminal for tools/talk.py): deleting outside the
              workspace, sudo, installs, pushing, killing processes, touching keys and shell config, sending files out
    the rest  runs. Files are written freely inside the workspace; anywhere else asks first. Secrets aren't read.
The /hands: setting: off (no hands), ask (the default: the tiers above), trusted (no asking; blocked still blocks).

Every action is recorded (memory's actions table) with what it was, what came back, and the message it served.
"""

import html
import json
import os
import re
import shlex
import signal
import subprocess
import sys
import threading
import time
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

HERE = Path(__file__).parent
PLAYBOOKS = HERE / "playbooks"
WORKSPACE = HERE / "data" / "workspace"       # app.py sets it (data/workspace); her own folder to work in
OUTPUT_CHARS = 12_000                         # tool output sent back to her, at most (the head and tail of anything longer)
FETCH_CHARS = 15_000                          # a fetched page sent back, at most
DEFAULT_TIMEOUT, MAX_TIMEOUT = 120, 600       # seconds for a foreground command
STATE = {"cwd": None, "job": 0, "out": 0}
JOBS = {}                                     # j3 -> {"id", "command", "started", "proc", "log", "thread", "done", "code"}
HOOKS = {"approve": None,                     # (request dict) -> True / False; set for each turn by whoever runs it
         "finished": None}                    # (job dict) -> None: a background job ended (app.py: thread + page)


# ---------------------------------------------------------------------------------------------------------------
# Safety
# ---------------------------------------------------------------------------------------------------------------

BLOCKED = [
    (r"\brm\s+(-[a-zA-Z]*\s+)*(-[a-zA-Z]*[rR][a-zA-Z]*|--recursive)\s+(-[a-zA-Z]*\s+)*(/|~/?|\$HOME/?|\$\{HOME\}/?|/\*|~/\*)(\s|$|;|&|\|)",
     "deleting the whole disk or home folder"),
    (r"(^|[;&|\s])mkfs(\.\w+)?\b", "formatting a disk"),
    (r"\bdd\b[^;&|]*\bof=/dev/", "writing raw to a disk"),
    (r">\s*/dev/(sd|disk|nvme|hd)\w*", "writing raw to a disk"),
    (r":\(\)\s*\{\s*:\s*\|\s*:\s*&\s*\}\s*;\s*:", "a fork bomb"),
    (r"(^|[;&|\s])(shutdown|reboot|halt|poweroff)\b", "shutting the computer down"),
    (r"\bchmod\s+(-[a-zA-Z]*\s+)*-?R?\s*[0-7]*\s+/(\s|$)", "changing permissions on the whole disk"),
]
ASK = [
    (r"(^|[;&|\s(])sudo\b|(^|[;&|\s])su\s", "runs as administrator"),
    (r"\bgit\s+push\b", "pushes to a remote"),
    (r"\bgit\s+(reset\s+--hard|clean\s+-[a-zA-Z]*f)", "throws away uncommitted work"),
    (r"(curl|wget)[^|;&]*\|\s*(ba|z)?sh\b", "runs a script straight from the internet"),
    (r"(^|[;&|\s])(pip3?|python3?\s+-m\s+pip)\s+install\b|\bnpm\s+(i|install)\s+(-g|--global)\b|\bbrew\s+install\b|\b(apt|apt-get|dnf|yum|pacman)\s+(install|remove)\b",
     "installs software"),
    (r"(^|[;&|\s])(kill|pkill|killall)\b", "stops processes"),
    (r"(^|[;&|\s])(crontab|launchctl|systemctl|osascript)\b", "changes how the computer runs things"),
    (r"(~|\$HOME|\$\{HOME\})/\.(ssh|aws|gnupg|config/gh)\b|\.env\b|\.(bashrc|zshrc|profile|bash_profile|zprofile)\b",
     "touches keys or shell settings"),
    (r"\b(scp|rsync|sftp)\b[^;&|]*\S+:|\bcurl\b[^;&|]*\s(-d|--data\S*|-F|--form|-T|--upload-file)\s", "sends files or data out"),
    (r"\bssh\s+\S+@?\S+", "connects to another machine"),
]
SECRET_PATHS = re.compile(r"(^|/)(\.env(\.\w+)?|\.ssh(/|$)|\.aws(/|$)|\.gnupg(/|$)|id_(rsa|ed25519|ecdsa)\b|\.netrc|\.pgpass|credentials(\.json)?)", re.I)


def judge(command):
    """('blocked', why) | ('ask', why) | ('ok', None) for a shell command."""
    flat = re.sub(r"\\\n", " ", command or "")
    for pattern, why in BLOCKED:
        if re.search(pattern, flat):
            return "blocked", why
    for pattern, why in ASK:
        if re.search(pattern, flat):
            return "ask", why
    for m in re.finditer(r"(^|[;&|\s])rm\s+((?:-\S+\s+)*)(.+?)(?=$|[;&|])", flat):
        if "r" in m.group(2).lower() or "f" in m.group(2):
            targets = shlex.split(m.group(3)) if m.group(3) else []
            if any(t.startswith(("/", "~", "$")) or ".." in t for t in targets):
                return "ask", "deletes outside the workspace"
    return "ok", None


def inside_workspace(path):
    try:
        Path(path).resolve().relative_to(WORKSPACE.resolve())
        return True
    except ValueError:
        return False


def resolve(path):
    """A path she gave, relative to where the terminal is (her workspace by default)."""
    p = Path(os.path.expanduser(str(path or "")))
    return p if p.is_absolute() else Path(cwd()) / p


def cwd():
    if not STATE["cwd"] or not Path(STATE["cwd"]).is_dir():
        WORKSPACE.mkdir(parents=True, exist_ok=True)
        STATE["cwd"] = str(WORKSPACE)
    return STATE["cwd"]


def permitted(kind, detail, why, mode):
    """Ask him, when the tier says to. Returns None if it may go ahead, or what to tell her if not."""
    if mode == "trusted":
        return None
    approve = HOOKS["approve"]
    allowed = approve({"kind": kind, "detail": detail, "why": why}) if approve else False
    return None if allowed else f"Not done: {NAME_HIM} didn't approve it ({why}). Say what you wanted to do and why, and let him decide."


NAME_HIM = "he"


# ---------------------------------------------------------------------------------------------------------------
# Output: the head and tail of anything long, the whole of it kept in a file
# ---------------------------------------------------------------------------------------------------------------

def keep_output(text, limit=OUTPUT_CHARS, label="output"):
    """Text for her: whole if it fits, else head and tail with the middle saved to a file she can read_file."""
    text = text or ""
    if len(text) <= limit:
        return text
    folder = WORKSPACE / ".avy" / "output"
    folder.mkdir(parents=True, exist_ok=True)
    STATE["out"] += 1
    path = folder / f"{label}-{int(time.time())}-{STATE['out']}.txt"
    path.write_text(text)
    half = limit // 2
    return (text[:half] + f"\n\n[... {len(text) - limit:,} characters cut; the whole {label} is in {path} (read_file with offset to page) ...]\n\n"
            + text[-half:])


# ---------------------------------------------------------------------------------------------------------------
# The terminal
# ---------------------------------------------------------------------------------------------------------------

MARK = "__AVY_CWD__"


def terminal(command, timeout=None, background=False, thread=None, mode="ask"):
    command = (command or "").strip()
    if not command:
        return "Give a command to run."
    verdict, why = judge(command)
    if verdict == "blocked":
        return f"Blocked: this would mean {why}. That never runs. Find another way, or tell him why it's needed."
    if verdict == "ask":
        refused = permitted("command", command, why, mode)
        if refused:
            return refused
    if background:
        return start_job(command, thread)
    timeout = max(1, min(int(timeout or DEFAULT_TIMEOUT), MAX_TIMEOUT))
    wrapped = f"{command}\n__avy=$?\nprintf '\\n{MARK}%s\\n' \"$PWD\"\nexit $__avy"
    started = time.time()
    try:
        done = subprocess.run(["bash", "-c", wrapped], cwd=cwd(), capture_output=True, text=True, timeout=timeout,
                              env={**os.environ, "PAGER": "cat", "GIT_PAGER": "cat", "TERM": "dumb"})
    except subprocess.TimeoutExpired as e:
        out = (e.stdout or b"").decode(errors="replace") if isinstance(e.stdout, bytes) else (e.stdout or "")
        return (f"Stopped after {timeout}s without finishing.\n" + keep_output(out) +
                "\nIf it needs longer, run it with background=true and check on it with the jobs tool.")
    out, err = done.stdout, done.stderr
    m = re.search(rf"\n?{MARK}(.*)\n?$", out)
    if m:
        STATE["cwd"] = m.group(1).strip() or STATE["cwd"]
        out = out[:m.start()]
    body = out + (("\n[stderr]\n" + err) if err.strip() else "")
    return (f"exit {done.returncode} · {time.time() - started:.1f}s · cwd {cwd()}\n" + keep_output(body.strip() or "(no output)"))


def start_job(command, thread=None):
    STATE["job"] += 1
    jid = f"j{STATE['job']}"
    folder = WORKSPACE / ".avy" / "jobs"
    folder.mkdir(parents=True, exist_ok=True)
    log = folder / f"{jid}.log"
    handle = open(log, "w")
    proc = subprocess.Popen(["bash", "-c", command], cwd=cwd(), stdout=handle, stderr=subprocess.STDOUT,
                            start_new_session=True, env={**os.environ, "PAGER": "cat", "TERM": "dumb"})
    JOBS[jid] = {"id": jid, "command": command, "started": time.time(), "proc": proc, "log": str(log), "cwd": cwd(),
                 "thread": thread, "done": False, "code": None}
    threading.Thread(target=watch_job, args=(jid, handle), daemon=True).start()
    return (f"Started {jid} in the background ({command[:120]}). Its output goes to {log}. You'll see it on your desk when it "
            "ends; check on it any time with the jobs tool. Note on the thread it belongs to what you expect from it.")


def watch_job(jid, handle):
    job = JOBS[jid]
    job["code"] = job["proc"].wait()
    handle.close()
    job["done"], job["ended"] = True, time.time()
    if HOOKS["finished"]:
        try:
            HOOKS["finished"](job_view(job))
        except Exception as e:
            print(f"A finished job's note failed ({e}).")


def job_view(job, tail=0):
    out = {k: job[k] for k in ("id", "command", "log", "thread", "done", "code", "cwd")}
    out["seconds"] = round((job.get("ended") or time.time()) - job["started"], 1)
    if tail:
        try:
            text = Path(job["log"]).read_text(errors="replace")
            out["output"] = text[-tail:]
        except OSError:
            out["output"] = ""
    return out


def jobs(action="list", job=None, seconds=None, mode="ask"):
    if action == "list" or not job:
        if not JOBS:
            return "No background jobs."
        return "\n".join(f"{j['id']} [{'exit ' + str(j['code']) if j['done'] else 'running'}] {round((j.get('ended') or time.time()) - j['started'])}s: "
                         f"{j['command'][:100]}" for j in JOBS.values())
    j = JOBS.get(job)
    if not j:
        return f"There's no job {job}."
    if action == "wait":
        end = time.time() + max(1, min(int(seconds or 60), MAX_TIMEOUT))
        while not j["done"] and time.time() < end:
            time.sleep(0.5)
    if action == "stop":
        if not j["done"]:
            try:
                os.killpg(j["proc"].pid, signal.SIGTERM)
            except OSError:
                j["proc"].terminate()
            time.sleep(0.5)
        return f"Stopped {job}."
    view = job_view(j, tail=OUTPUT_CHARS // 2)
    state = f"exit {view['code']}" if view["done"] else "still running"
    return f"{job} {state} after {view['seconds']}s ({j['command'][:120]})\nlast output:\n{view['output'] or '(none yet)'}"


# ---------------------------------------------------------------------------------------------------------------
# Files
# ---------------------------------------------------------------------------------------------------------------

def read_file(path, offset=1, limit=400):
    p = resolve(path)
    if SECRET_PATHS.search(str(p)):
        return "That file holds secrets (keys, passwords); it isn't read."
    if not p.exists():
        near = sorted(x.name for x in p.parent.glob("*"))[:30] if p.parent.exists() else []
        return f"There's no file {p}." + (f" In {p.parent}: {', '.join(near)}" if near else "")
    if p.is_dir():
        items = sorted(p.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower()))
        return f"{p} is a folder:\n" + "\n".join(f"{x.name}/" if x.is_dir() else f"{x.name} ({x.stat().st_size:,} bytes)" for x in items[:200])
    if p.suffix.lower() == ".pdf":
        try:
            from pypdf import PdfReader
            text = "\n\n".join(page.extract_text() or "" for page in PdfReader(str(p)).pages)
        except Exception as e:
            return f"Couldn't read the PDF ({e})."
        lines = text.splitlines()
    else:
        try:
            lines = p.read_text(errors="replace").splitlines()
        except OSError as e:
            return f"Couldn't read it ({e})."
    offset, limit = max(1, int(offset or 1)), max(1, min(int(limit or 400), 2000))
    chunk = lines[offset - 1:offset - 1 + limit]
    body = "\n".join(f"{i}|{line}" for i, line in enumerate(chunk, offset))
    more = f"\n[lines {offset}-{offset + len(chunk) - 1} of {len(lines)}; read on with offset={offset + len(chunk)}]" if offset - 1 + limit < len(lines) else ""
    return keep_output(body, label="file") + more


def write_file(path, content, mode="ask"):
    p = resolve(path)
    if SECRET_PATHS.search(str(p)):
        return "That's a secrets file; it isn't written."
    if not inside_workspace(p):
        refused = permitted("write", str(p), "writes a file outside her workspace", mode)
        if refused:
            return refused
    p.parent.mkdir(parents=True, exist_ok=True)
    existed = p.exists()
    p.write_text(content or "")
    note = check_syntax(p)
    return f"{'Rewrote' if existed else 'Wrote'} {p} ({len(content or ''):,} characters)." + (f"\n{note}" if note else "")


def edit_file(path, old, new, replace_all=False, mode="ask"):
    p = resolve(path)
    if not p.is_file():
        return f"There's no file {p} to edit (write_file creates one)."
    if not inside_workspace(p):
        refused = permitted("write", str(p), "edits a file outside her workspace", mode)
        if refused:
            return refused
    text = p.read_text(errors="replace")
    n = text.count(old or "")
    if not old or n == 0:
        return "The text to replace isn't in the file exactly as given. read_file it and copy the lines exactly."
    if n > 1 and not replace_all:
        return f"That text appears {n} times; include more surrounding lines so it's unique, or set replace_all."
    p.write_text(text.replace(old, new or "") if replace_all else text.replace(old, new or "", 1))
    note = check_syntax(p)
    return f"Edited {p} ({n if replace_all else 1} place{'s' if replace_all and n > 1 else ''})." + (f"\n{note}" if note else "")


def check_syntax(p):
    """A quick check after writing code, so a broken file is noticed at once."""
    try:
        if p.suffix == ".py":
            compile(p.read_text(), str(p), "exec")
        elif p.suffix == ".json":
            json.loads(p.read_text())
    except SyntaxError as e:
        return f"Syntax error at line {e.lineno}: {e.msg}"
    except json.JSONDecodeError as e:
        return f"Invalid JSON at line {e.lineno}: {e.msg}"
    return ""


def find_files(pattern="*", contains=None, path=None, limit=200):
    root = resolve(path or ".")
    if not root.exists():
        return f"There's no folder {root}."
    skip = {".git", "node_modules", "__pycache__", ".venv", "venv", ".avy"}
    found = []
    for p in sorted(root.rglob(pattern or "*")):
        if any(part in skip for part in p.relative_to(root).parts) or not p.is_file() or SECRET_PATHS.search(str(p)):
            continue
        if contains:
            try:
                lines = [f"{p.relative_to(root)}:{i}: {line.strip()[:160]}" for i, line in
                         enumerate(p.read_text(errors="replace").splitlines(), 1) if re.search(contains, line)]
            except (OSError, re.error):
                continue
            found += lines
        else:
            found.append(str(p.relative_to(root)))
        if len(found) >= limit:
            found.append(f"(stopped at {limit})")
            break
    return f"In {root}:\n" + ("\n".join(found) if found else "nothing matched")


# ---------------------------------------------------------------------------------------------------------------
# Python
# ---------------------------------------------------------------------------------------------------------------

def python(code, timeout=None):
    WORKSPACE.mkdir(parents=True, exist_ok=True)
    started = time.time()
    try:
        done = subprocess.run([sys.executable, "-c", code or ""], cwd=cwd(), capture_output=True, text=True,
                              timeout=max(1, min(int(timeout or 60), MAX_TIMEOUT)))
    except subprocess.TimeoutExpired:
        return "Stopped: it ran past its time limit."
    body = done.stdout + (("\n[stderr]\n" + done.stderr) if done.stderr.strip() else "")
    return f"exit {done.returncode} · {time.time() - started:.1f}s\n" + keep_output(body.strip() or "(no output: print what you want to see)")


# ---------------------------------------------------------------------------------------------------------------
# The web
# ---------------------------------------------------------------------------------------------------------------

def web_search(query, limit=5):
    query = (query or "").strip()
    if not query:
        return "Give a search query."
    limit = max(1, min(int(limit or 5), 10))
    try:
        results = search_backend(query, limit)
    except Exception as e:
        return f"The search didn't work ({type(e).__name__}: {str(e)[:200]}). Try different words, or web_fetch a page you know."
    if not results:
        return "No results. Try different or fewer words."
    return "\n\n".join(f"{i}. {r['title']}\n   {r['url']}\n   {r['snippet']}" for i, r in enumerate(results, 1))


def search_backend(query, limit):
    """SearXNG if AVY_SEARXNG is set; Brave if BRAVE_API_KEY is; otherwise the ddgs package (no key)."""
    if os.environ.get("AVY_SEARXNG"):
        url = os.environ["AVY_SEARXNG"].rstrip("/") + "/search?" + urllib.parse.urlencode({"q": query, "format": "json"})
        data = json.loads(fetch_bytes(url)[0])
        return [{"title": r.get("title", ""), "url": r.get("url", ""), "snippet": r.get("content", "")} for r in data.get("results", [])[:limit]]
    if os.environ.get("BRAVE_API_KEY"):
        req = urllib.request.Request("https://api.search.brave.com/res/v1/web/search?" + urllib.parse.urlencode({"q": query, "count": limit}),
                                     headers={"Accept": "application/json", "X-Subscription-Token": os.environ["BRAVE_API_KEY"]})
        with urllib.request.urlopen(req, timeout=20) as r:
            data = json.loads(r.read())
        return [{"title": x.get("title", ""), "url": x.get("url", ""), "snippet": html.unescape(re.sub("<[^>]+>", "", x.get("description", "")))}
                for x in (data.get("web") or {}).get("results", [])[:limit]]
    from ddgs import DDGS
    return [{"title": r.get("title", ""), "url": r.get("href", ""), "snippet": r.get("body", "")} for r in DDGS().text(query, max_results=limit)]


def fetch_bytes(url, timeout=25):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Avy; personal assistant)", "Accept": "text/html,application/pdf,*/*"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read(8_000_000), r.headers.get("Content-Type", ""), r.geturl()


class Text(HTMLParser):
    """A page's readable text: no scripts, styles, menus or footers; headings and list items on their own lines."""
    SKIP = {"script", "style", "noscript", "svg", "nav", "footer", "header", "aside", "form", "iframe"}
    BLOCK = {"p", "div", "br", "li", "tr", "section", "article", "h1", "h2", "h3", "h4", "h5", "h6", "pre", "blockquote", "table"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out, self.skipping, self.title, self.in_title = [], 0, "", False

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self.skipping += 1
        elif tag == "title":
            self.in_title = True
        elif tag in self.BLOCK:
            self.out.append("\n" + ("# " if tag in ("h1", "h2") else "## " if tag[:1] == "h" and len(tag) == 2 else "- " if tag == "li" else ""))

    def handle_endtag(self, tag):
        if tag in self.SKIP and self.skipping:
            self.skipping -= 1
        elif tag == "title":
            self.in_title = False

    def handle_data(self, data):
        if self.in_title:
            self.title += data
        elif not self.skipping:
            self.out.append(data)

    def text(self):
        raw = "".join(self.out)
        lines = [re.sub(r"[ \t]+", " ", line).strip() for line in raw.splitlines()]
        return re.sub(r"\n{3,}", "\n\n", "\n".join(line for line in lines if line not in ("", "-", "#", "##")))


def web_fetch(url, max_chars=None):
    url = (url or "").strip()
    if not re.match(r"https?://", url):
        return "Give a full address, starting with https://"
    try:
        body, kind, final = fetch_bytes(url)
    except Exception as e:
        return f"Couldn't fetch it ({type(e).__name__}: {str(e)[:200]})."
    if "pdf" in kind.lower() or url.lower().endswith(".pdf"):
        import io
        try:
            from pypdf import PdfReader
            text, title = "\n\n".join(p.extract_text() or "" for p in PdfReader(io.BytesIO(body)).pages), "PDF"
        except Exception as e:
            return f"Fetched a PDF but couldn't read it ({e})."
    elif "html" in kind.lower() or body[:200].lstrip().lower().startswith((b"<!doctype", b"<html")):
        parser = Text()
        parser.feed(body.decode("utf-8", errors="replace"))
        text, title = parser.text(), parser.title.strip()
    else:
        text, title = body.decode("utf-8", errors="replace"), ""
    limit = max(2000, min(int(max_chars or FETCH_CHARS), 60_000))
    return f"{title}\n{final}\n\n" + keep_output(text, limit, label="page")


# ---------------------------------------------------------------------------------------------------------------
# Playbooks: how she goes about a kind of work, read when she needs it
# ---------------------------------------------------------------------------------------------------------------

def playbook_index():
    """'name: one line' for each playbook (the first line of the file after its title)."""
    out = []
    for p in sorted(PLAYBOOKS.glob("*.md")):
        lines = [x.strip() for x in p.read_text().splitlines() if x.strip()]
        about = next((x for x in lines if not x.startswith("#")), "")
        out.append(f"- {p.stem}: {about}")
    return "\n".join(out)


def playbook(name):
    p = PLAYBOOKS / f"{re.sub(r'[^a-z0-9_-]', '', (name or '').lower())}.md"
    if not p.exists():
        return "There's no playbook by that name. The playbooks:\n" + playbook_index()
    return p.read_text()


# ---------------------------------------------------------------------------------------------------------------
# The tools, as she sees them
# ---------------------------------------------------------------------------------------------------------------

def tool(name, description, properties, required):
    return {"type": "function", "function": {"name": name, "description": description,
                                             "parameters": {"type": "object", "properties": properties, "required": required}}}


TOOLS = [
    tool("terminal",
         "Run a shell command (bash) in your workspace. The working directory carries over between calls (each result says "
         "where you are); environment variables don't, so set them in the same command. Use read_file, write_file, "
         "edit_file and find_files instead of cat, echo > file, sed or grep. Long output comes back as its head and tail, "
         "with the whole saved to a file you can read_file. Anything that may take longer than a couple of minutes "
         "(a training run, a big build, a server) goes in the background (background=true): you get a job id, it keeps "
         "running while you talk, and you see it on your desk when it ends. Risky commands (sudo, installs, deleting "
         "outside the workspace, pushing) wait for his OK on the page.",
         {"command": {"type": "string"},
          "timeout": {"type": "integer", "description": f"seconds, default {DEFAULT_TIMEOUT}, at most {MAX_TIMEOUT}"},
          "background": {"type": "boolean"},
          "thread": {"type": "string", "description": "with background: the thread (th3) waiting on this job"}},
         ["command"]),
    tool("jobs", "Background jobs: list them, read one's latest output (status), wait for one to end (up to 'seconds'), or stop one.",
         {"action": {"type": "string", "enum": ["list", "status", "wait", "stop"]}, "job": {"type": "string"},
          "seconds": {"type": "integer"}}, ["action"]),
    tool("read_file", "Read a file with line numbers (also a folder's listing, and PDFs as text). Big files: use offset and limit.",
         {"path": {"type": "string"}, "offset": {"type": "integer"}, "limit": {"type": "integer"}}, ["path"]),
    tool("write_file", "Write a whole file (creates folders; replaces what was there). For a small change to an existing file, "
                       "use edit_file. Python and JSON are checked for syntax at once.",
         {"path": {"type": "string"}, "content": {"type": "string"}}, ["path", "content"]),
    tool("edit_file", "Replace an exact piece of text in a file with new text. The old text must appear exactly once (copy it "
                      "from read_file, with enough surrounding lines to be unique), unless replace_all.",
         {"path": {"type": "string"}, "old": {"type": "string"}, "new": {"type": "string"}, "replace_all": {"type": "boolean"}},
         ["path", "old", "new"]),
    tool("find_files", "Find files by name (a glob like '*.py') under a folder, or, with contains, the lines that match a regex.",
         {"pattern": {"type": "string"}, "contains": {"type": "string"}, "path": {"type": "string"}}, []),
    tool("python", "Run a short Python program and get what it prints. Use it for any arithmetic, dates, data or a quick "
                   "check, instead of working it out in your head.",
         {"code": {"type": "string"}, "timeout": {"type": "integer"}}, ["code"]),
    tool("web_search", "Search the web. Returns titles, addresses and snippets. Search before stating anything current "
                       "(versions, prices, news, who holds a role), and for anything you're not sure of. Short queries; try "
                       "several angles for anything that matters.",
         {"query": {"type": "string"}, "limit": {"type": "integer", "description": "1-10, default 5"}}, ["query"]),
    tool("web_fetch", "Read a web page or a PDF by its address, as text. Snippets aren't enough to rely on: fetch the source "
                      "before you quote or depend on it.",
         {"url": {"type": "string"}, "max_chars": {"type": "integer"}}, ["url"]),
    tool("playbook", "Read one of your playbooks: how you go about a kind of work. Read the matching one before starting work of "
                     "that kind.", {"name": {"type": "string"}}, ["name"]),
]
NAMES = {t["function"]["name"] for t in TOOLS}


def use(name, args, mode="ask"):
    """Carry out one of her hands' tools. Returns (what to tell her, a short line for the page)."""
    a = args if isinstance(args, dict) else {}
    try:
        if name == "terminal":
            thread = a.get("thread")
            out = terminal(a.get("command"), a.get("timeout"), bool(a.get("background")),
                           int(str(thread).lower().lstrip("th")) if thread and str(thread).lower().lstrip("th").isdigit() else None, mode)
            first = (out.splitlines()[0] if out else "").split(" · cwd")[0]
            return out, f"ran `{clip_line(a.get('command'))}` · {first[:40]}"
        if name == "jobs":
            out = jobs(a.get("action") or "list", a.get("job"), a.get("seconds"), mode)
            return out, f"jobs · {a.get('action') or 'list'} {a.get('job') or ''}".strip()
        if name == "read_file":
            return read_file(a.get("path"), a.get("offset"), a.get("limit")), f"read {clip_line(a.get('path'))}"
        if name == "write_file":
            out = write_file(a.get("path"), a.get("content"), mode)
            return out, clip_line(out.splitlines()[0], 90)
        if name == "edit_file":
            out = edit_file(a.get("path"), a.get("old"), a.get("new"), bool(a.get("replace_all")), mode)
            return out, clip_line(out.splitlines()[0], 90)
        if name == "find_files":
            return find_files(a.get("pattern") or "*", a.get("contains"), a.get("path")), f"looked for {a.get('pattern') or a.get('contains') or 'files'}"
        if name == "python":
            out = python(a.get("code"), a.get("timeout"))
            return out, f"ran python · {out.splitlines()[0][:50] if out else ''}"
        if name == "web_search":
            return web_search(a.get("query"), a.get("limit")), f"searched “{clip_line(a.get('query'), 70)}”"
        if name == "web_fetch":
            out = web_fetch(a.get("url"), a.get("max_chars"))
            return out, f"read {clip_line(a.get('url'), 80)}"
        if name == "playbook":
            return playbook(a.get("name")), f"opened the {a.get('name')} playbook"
    except Exception as e:
        return f"That failed ({type(e).__name__}: {str(e)[:300]}).", f"{name} failed"
    return f"There's no tool called {name}.", None


def clip_line(text, n=60):
    text = short_paths(" ".join(str(text or "").split()))
    return text if len(text) <= n else text[:n - 1] + "…"


def short_paths(text):
    """Paths inside her workspace, written from the workspace (what the page shows)."""
    root = str(WORKSPACE.resolve())
    return (text or "").replace(root + "/", "").replace(root, "~workspace")
