"""Intake: anything Shreyas adds becomes part of memory's library, whatever its format.

A file attached in the chat, a folder dropped on the page, a codebase, a paper, a spreadsheet, a recording,
a chat export from Claude or ChatGPT, a WhatsApp export, a transcript pasted into a .txt: each is read into
**passages** (memory/library.py), kept word for word and in order, and becomes searchable by words and by
meaning. Nothing needs to be in a particular format: the readers below recognize what they can (conversations
in any of the common shapes, code, documents, data) and anything else with words in it is still read as a
document. Recognizing is code's job; no model is involved in intake.

    INTAKE = Intake(tell=...)                       # one background worker, one job at a time
    INTAKE.add_file(mem, path, name, came="f2026...")
    INTAKE.add_tree(mem, folder, "my-project")      # a folder or an unpacked archive
    INTAKE.status()                                 # what the looking glass shows: every job, progress, ETA

A job goes: queued -> reading -> storing -> embedding -> stored (or problem, or duplicate when the same
words are already in the library). Embedding (the meaning-search vectors) is the slow part; its rate is
measured as it goes, so the ETA is real. Writing *knowledge* from passages is a separate, later step
(ARCHITECTURE.md, "The library").
"""

import io
import json
import re
import shutil
import tarfile
import tempfile
import threading
import time
import zipfile
from pathlib import Path

import files

PASSAGE = 1200            # characters a passage aims for
MAX_PASSAGE = 2400        # and never goes past
CODE_LINES = 60           # a code passage: at most this many lines
DATA_ROWS = 30            # a data passage: this many rows, with the header repeated
MAX_TREE_FILE = 3_000_000 # in a folder or archive, text files bigger than this are skipped (data dumps, bundles)
MAX_TREE_FILES = 20_000

SKIP_DIRS = {".git", ".hg", ".svn", "node_modules", "__pycache__", ".venv", "venv", "env", ".env", "dist", "build",
             ".next", ".nuxt", "target", ".idea", ".gradle", ".pytest_cache", ".mypy_cache", ".tox", "vendor",
             "bower_components", ".cache", "coverage", ".DS_Store", "__MACOSX", "Pods", "DerivedData"}
SKIP_FILES = re.compile(r"(package-lock\.json|yarn\.lock|pnpm-lock\.yaml|poetry\.lock|Cargo\.lock|Gemfile\.lock|composer\.lock|"
                        r"\.min\.(js|css)|\.map|\.lock|\.pyc|\.DS_Store)$", re.I)
CODE_EXT = {"py", "js", "jsx", "ts", "tsx", "mjs", "cjs", "java", "kt", "kts", "scala", "go", "rs", "c", "h", "cc", "cpp", "hpp",
            "cs", "swift", "m", "mm", "rb", "php", "pl", "lua", "r", "jl", "sh", "bash", "zsh", "fish", "ps1", "sql", "html",
            "htm", "css", "scss", "sass", "less", "vue", "svelte", "dart", "ex", "exs", "erl", "hs", "ml", "clj", "elm",
            "toml", "yaml", "yml", "ini", "cfg", "conf", "json", "xml", "gradle", "proto", "graphql", "dockerfile", "make",
            "cmake", "tf", "nix", "zig", "v", "sol", "ipynb"}
DATA_EXT = {"csv", "tsv"}

USER_NAMES = {"shreyas", "shrey", "me", "you", "user", "human", "i", "self"}
ASSISTANT_NAMES = {"assistant", "claude", "chatgpt", "gpt", "ai", "bot", "avy", "model", "gemini", "copilot", "bard", "system"}


# =====================================================================================================
# Reading: a file (or a folder) -> (kind, [passages], meta)
# =====================================================================================================

def read_any(path, name=None, record=None, home=None):
    """What a file holds, as passages. record: its files.py record if it was attached in the chat (its text
    and transcript are reused rather than read again). Returns (kind, passages, meta)."""
    path = Path(path)
    name = name or path.name
    if path.is_dir():
        return read_tree(path, name)
    head = open(path, "rb").read(65536)
    ext = path.suffix.lower().lstrip(".")
    kind = (record or {}).get("kind") or files.sniff(head, ext, (record or {}).get("mime") or "", path)
    if kind == "claude-export":
        return read_claude_export(path)
    if kind == "archive":
        return read_archive(path, name)
    if kind in ("image",):
        described = describe_picture(path, home)
        if described:
            return "picture", [{"text": described, "part": "what's in the picture (described when it was added)"}], \
                {"format": "picture", "described": True}
        return "picture", [], {"format": "picture", "note": "a picture has no words to keep: Avy saw it when it was attached"}
    if kind == "binary":
        return "binary", [], {"format": "binary", "note": "kept as a file, but there are no words in it to read"}
    if kind in ("audio", "video"):
        text = reused_text(record, home)
        if not text and files.hooks.get("transcribe"):
            text, _ = files.hooks["transcribe"](path)
        return "recording", chunk_transcript(text), {"format": kind}
    if kind == "text":
        return read_text_kinds(full_text(path), name, ext)
    text = reused_text(record, home, full_needed=True)
    if not text:
        reader = files.READERS.get(kind)
        tmp = Path(tempfile.mkdtemp(prefix="avy-intake-"))
        try:
            found = reader(path, tmp, head) if reader else {}
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        if found.get("problem"):
            raise ValueError(found["problem"])
        text = found.get("text") or ""
    if kind == "xlsx" or (kind == "odf" and "## sheet:" in text):
        return "data", chunk_sheets(text), {"format": kind}
    return "document", chunk_document(text), {"format": kind}


HOOKS = {"describe": None}    # set by app.py: describe(jpeg path) -> a few sentences, from the model (it can see pictures)


def describe_picture(path, home=None):
    """A picture has no words of its own, so the model looks at it once and says what's in it; that description
    is what memory can search. Uses the shrunk copy files.py made (home/view/1.jpg) when there is one."""
    if not HOOKS.get("describe"):
        return ""
    shown = Path(home) / "view" / "1.jpg" if home and (Path(home) / "view" / "1.jpg").exists() else None
    tmp = None
    try:
        if not shown:
            tmp = Path(tempfile.mkdtemp(prefix="avy-pic-"))
            files.picture(path, tmp / "1.jpg", files.PICTURE_SIDE)
            shown = tmp / "1.jpg"
        return (HOOKS["describe"](shown) or "").strip()
    except Exception:
        return ""
    finally:
        if tmp:
            shutil.rmtree(tmp, ignore_errors=True)


def reused_text(record, home, full_needed=False):
    """The text files.py already read from an attached file (so a recording isn't transcribed twice), unless it
    was cut short at files.STORED_CHARS and the whole is needed."""
    if not record or not home or not (Path(home) / "text.txt").exists():
        return ""
    if full_needed and (record.get("chars") or 0) >= files.STORED_CHARS:
        return ""
    return (Path(home) / "text.txt").read_text(errors="replace")


def full_text(path):
    with open(path, "rb") as f:
        return files.decode(f.read())


def read_text_kinds(text, name, ext):
    """Plain text of any kind: a conversation in some shape, code, data, or a document."""
    if ext == "json" or text.lstrip()[:1] in ("[", "{"):
        try:
            data = json.loads(text)
        except (json.JSONDecodeError, RecursionError):
            data = None
        if data is not None:
            convs = conversations_in_json(data)
            if convs:
                return "conversations", conversation_passages(convs), {"format": convs[0].get("format", "json"), "conversations": len(convs),
                                                                         "messages": sum(len(c["messages"]) for c in convs)}
    if ext not in CODE_EXT:
        conv = transcript_in_text(text)
        if conv:
            return "conversations", conversation_passages([conv]), {"format": conv["format"], "conversations": 1,
                                                                    "messages": len(conv["messages"]), "speakers": conv["speakers"]}
    if ext in DATA_EXT:
        return "data", chunk_table(text, "\t" if ext == "tsv" else ","), {"format": ext}
    if ext in CODE_EXT or name.lower() in ("dockerfile", "makefile", "procfile"):
        return "code", chunk_code(text, name), {"format": ext or name.lower()}
    return "document", chunk_document(text), {"format": ext or "text"}


# --- folders and archives: every file in it, each read by its own kind ------------------------------

def read_archive(path, name):
    tmp = Path(tempfile.mkdtemp(prefix="avy-intake-"))
    try:
        unpack(path, tmp)
        kind, passages, meta = read_tree(tmp, name)
        meta["archive"] = True
        return kind, passages, meta
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def unpack(path, into):
    """Unpack a zip or tar safely: nothing outside `into`, no links, at most MAX_TREE_FILES files."""
    into = Path(into).resolve()
    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as z:
            for i, zi in enumerate(z.infolist()):
                if i >= MAX_TREE_FILES:
                    break
                target = (into / zi.filename).resolve()
                if zi.is_dir() or not str(target).startswith(str(into) + "/"):
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                with z.open(zi) as src, open(target, "wb") as out:
                    shutil.copyfileobj(src, out)
        return
    with tarfile.open(path) as t:
        for i, ti in enumerate(t):
            if i >= MAX_TREE_FILES:
                break
            target = (into / ti.name).resolve()
            if not ti.isfile() or not str(target).startswith(str(into) + "/"):
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with t.extractfile(ti) as src, open(target, "wb") as out:
                shutil.copyfileobj(src, out)


def read_tree(folder, name):
    """Every readable file in a folder, in path order, each read by its kind. Folders like node_modules and .git,
    lockfiles and minified bundles are left out (counted)."""
    folder = Path(folder)
    roots = [p for p in folder.iterdir() if p.name not in SKIP_DIRS]
    if len(roots) == 1 and roots[0].is_dir():          # an archive of one folder: paths start inside it
        folder = roots[0]
    passages, kinds, skipped, problems, count = [], {}, {"folders": 0, "files": 0, "big": 0}, [], 0
    for path in sorted(p for p in folder.rglob("*") if p.is_file()):
        rel = path.relative_to(folder).as_posix()
        if any(part in SKIP_DIRS for part in path.relative_to(folder).parts[:-1]):
            skipped["folders"] += 1
            continue
        if SKIP_FILES.search(path.name) or path.name.startswith("."):
            skipped["files"] += 1
            continue
        count += 1
        if count > MAX_TREE_FILES:
            break
        head = open(path, "rb").read(65536)
        ext = path.suffix.lower().lstrip(".")
        kind = files.sniff(head, ext, "", path)
        try:
            if kind == "text":
                if path.stat().st_size > MAX_TREE_FILE:
                    skipped["big"] += 1
                    continue
                k, ps, _ = read_text_kinds(full_text(path), rel, ext)
            elif kind in ("image", "binary", "audio", "video", "archive"):
                skipped["files"] += 1
                continue
            else:
                k, ps, _ = read_any(path, rel)
        except Exception as e:
            problems.append(f"{rel}: {type(e).__name__}: {str(e)[:120]}")
            continue
        kinds[k] = kinds.get(k, 0) + 1
        for p in ps:                                       # every passage says which file it came from
            p["part"] = p.get("part") if (p.get("part") or "").startswith(rel) else f"{rel}" + (f" · {p['part']}" if p.get("part") else "")
        passages += ps
    main = max(kinds, key=kinds.get) if kinds else "document"
    kind = main if len(kinds) <= 1 or kinds[main] >= 0.7 * sum(kinds.values()) else "mixed"
    return kind, passages, {"format": "folder", "files": sum(kinds.values()), "by_kind": kinds, "skipped": skipped,
                            "problems": problems[:20]}


# --- conversations, in whatever shape they come --------------------------------------------------------

def read_claude_export(path):
    import sys
    sys.path.insert(0, str(Path(__file__).parent / "tools"))
    import claude_export
    convs = []
    for item in claude_export.read(path):
        if isinstance(item, claude_export.Conversation) and item.messages:
            convs.append({"name": item.name or "untitled", "format": "claude export",
                          "messages": [{"speaker": "Shreyas" if m.role == "user" else "Claude", "role": m.role, "at": m.at,
                                        "text": m.text + ("".join(f"\n[attached: {a['name']}]" for a in m.attachments)
                                                          + "".join(f"\n[attached: {f}]" for f in m.files))} for m in item.messages]})
    convs.sort(key=lambda c: c["messages"][0]["at"] or "")
    return "conversations", conversation_passages(convs), {"format": "claude export", "conversations": len(convs),
                                                          "messages": sum(len(c["messages"]) for c in convs)}


def role_of(speaker):
    s = str(speaker or "").strip().lower()
    if s in USER_NAMES or s.startswith("shreyas"):
        return "user"
    if s in ASSISTANT_NAMES or any(s.startswith(a) for a in ("claude", "chatgpt", "gpt-", "assistant")):
        return "assistant"
    return "other"


def text_of_content(c):
    """Message content in the many shapes exports use: a string, a list of parts, {"parts": [...]}, {"text": ...}."""
    if c is None:
        return ""
    if isinstance(c, str):
        return c
    if isinstance(c, list):
        return "\n".join(t for t in (text_of_content(x) for x in c) if t)
    if isinstance(c, dict):
        for key in ("text", "parts", "content", "value", "body", "message"):
            if key in c and not (key == "content" and isinstance(c[key], dict) and c[key] is c):
                t = text_of_content(c[key])
                if t:
                    return t
    return ""


SPEAKER_KEYS = ("role", "author", "sender", "from", "speaker", "user", "name")
TEXT_KEYS = ("content", "text", "message", "body", "value", "parts")
TIME_KEYS = ("create_time", "created_at", "timestamp", "time", "date", "ts", "sent_at")


def message_of(d):
    """{"speaker", "role", "at", "text"} from one message-like object, or None."""
    if not isinstance(d, dict):
        return None
    speaker = next((d[k] for k in SPEAKER_KEYS if k in d and d[k]), None)
    if isinstance(speaker, dict):
        speaker = speaker.get("role") or speaker.get("name") or speaker.get("display_name")
    text = next((text_of_content(d[k]) for k in TEXT_KEYS if k in d and text_of_content(d[k])), "")
    if speaker is None or not str(text).strip():
        return None
    at = next((d[k] for k in TIME_KEYS if k in d and d[k]), None)
    return {"speaker": str(speaker), "role": role_of(speaker), "at": iso_time(at), "text": str(text)}


def iso_time(value):
    from datetime import datetime, timezone
    if value is None:
        return None
    try:
        if isinstance(value, (int, float)):
            value = value / 1000 if value > 1e12 else value
            return datetime.fromtimestamp(value, timezone.utc).astimezone().isoformat(timespec="seconds")
        t = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return (t if t.tzinfo else t.astimezone()).astimezone().isoformat(timespec="seconds")
    except (ValueError, OverflowError, OSError):
        return None


def chatgpt_messages(conv):
    """A ChatGPT export conversation: a tree of messages ("mapping"); keep the branch it ended on."""
    mapping, node = conv.get("mapping") or {}, conv.get("current_node")
    if not node:
        leaves = [k for k, v in mapping.items() if not v.get("children")]
        node = leaves[-1] if leaves else None
    chain = []
    while node and node in mapping:
        chain.append(mapping[node])
        node = mapping[node].get("parent")
    out = []
    for item in reversed(chain):
        m = item.get("message") or {}
        role = (m.get("author") or {}).get("role")
        if role not in ("user", "assistant"):
            continue
        text = text_of_content((m.get("content") or {}).get("parts"))
        if text.strip():
            out.append({"speaker": "Shreyas" if role == "user" else "ChatGPT", "role": role, "at": iso_time(m.get("create_time")), "text": text})
    return out


def conversations_in_json(data, depth=0):
    """Every conversation in a JSON document, whatever its shape: [{"name", "format", "messages"}]."""
    if depth > 5:
        return []
    if isinstance(data, list) and data and all(isinstance(x, dict) for x in data[:50]):
        if sum(1 for x in data[:50] if "mapping" in x) >= min(3, len(data[:50])):            # ChatGPT
            convs = [{"name": c.get("title") or "untitled", "format": "chatgpt export", "messages": chatgpt_messages(c)} for c in data]
            return [c for c in convs if c["messages"]]
        msgs = [message_of(x) for x in data]
        good = [m for m in msgs if m]
        if len(good) >= 2 and len(good) >= 0.6 * len(data):                                 # a list of messages
            return [{"name": "conversation", "format": "json messages", "messages": good}]
        convs = []
        for x in data:                                                                       # a list of conversations
            for key in ("messages", "chat_messages", "turns", "conversation", "dialogue", "items"):
                if isinstance(x.get(key), list):
                    inner = conversations_in_json(x[key], depth + 1)
                    for c in inner:
                        c["name"] = str(x.get("name") or x.get("title") or c["name"])
                    convs += inner
                    break
        return convs
    if isinstance(data, dict):
        if "mapping" in data:
            msgs = chatgpt_messages(data)
            return [{"name": data.get("title") or "untitled", "format": "chatgpt export", "messages": msgs}] if msgs else []
        for key in ("messages", "chat_messages", "turns", "conversations", "conversation", "dialogue", "chats", "data", "items"):
            if key in data and isinstance(data[key], (list, dict)):
                found = conversations_in_json(data[key], depth + 1)
                if found:
                    if len(found) == 1 and (data.get("title") or data.get("name")):
                        found[0]["name"] = str(data.get("title") or data.get("name"))
                    return found
    return []


WHATSAPP = re.compile(r"^\[?(\d{1,4}[/.-]\d{1,2}[/.-]\d{1,4}),?\s+(\d{1,2}:\d{2}(?::\d{2})?(?:\s?[APap]\.?[Mm]\.?)?)\]?\s*(?:-\s)?([^:\n]{1,40}):\s(.*)$")
LABELED = re.compile(r"^\s*(?:\*\*|__)?\[?([A-Za-z][\w .'@-]{0,29}?)\]?(?:\*\*|__)?\s*:(?:\*\*|__)?\s+(.+)$")
HEADED = re.compile(r"^\s*#{1,4}\s*([A-Za-z][\w .'-]{0,29})\s*:?\s*$")


def transcript_in_text(text):
    """A conversation written as text: WhatsApp-style ("[12/03/24, 10:15] Name: ..."), labeled lines ("Me: ...",
    "**Claude:** ..."), or a heading per speaker ("## User"). Returns {"name", "format", "messages", "speakers"} or
    None. It only counts as a conversation if the turns cover nearly all of the text and the speakers come back
    again and again (a document's headings, or prose with a colon in it, don't)."""
    lines = text.splitlines()
    nonblank = sum(1 for l in lines if l.strip())
    if nonblank < 3:
        return None
    for fmt, pattern in (("whatsapp", WHATSAPP), ("labeled lines", LABELED), ("speaker headings", HEADED)):
        turns, current, before, matched = [], None, 0, 0
        for line in lines:
            m = pattern.match(line)
            if m:
                matched += 1
                if fmt == "whatsapp":
                    speaker, said, at = m.group(3), m.group(4), f"{m.group(1)} {m.group(2)}"
                elif fmt == "labeled lines":
                    speaker, said, at = m.group(1), m.group(2), None
                else:
                    speaker, said, at = m.group(1), "", None
                current = {"speaker": speaker.strip(), "text": said, "at": at}
                turns.append(current)
            elif current is not None:
                current["text"] += "\n" + line
            elif line.strip():
                before += 1
        speakers = {}
        for t in turns:
            speakers[t["speaker"]] = speakers.get(t["speaker"], 0) + 1
        top = sorted(speakers.values(), reverse=True)
        if len(turns) < 3 or before > 0.1 * nonblank or len(top) < 2:
            continue
        if fmt != "whatsapp":
            known = any(role_of(name) != "other" for name in speakers)
            if len(speakers) > 8 or top[1] < 2 or sum(top[:4]) < 0.9 * len(turns):
                continue                               # a conversation's speakers come back, again and again
            if fmt == "speaker headings" and not known:
                continue                               # a document's headings aren't speakers
            if fmt == "labeled lines" and matched < 0.3 * nonblank and not known:
                continue
        msgs = [{"speaker": t["speaker"], "role": role_of(t["speaker"]), "at": parse_loose_time(t["at"]), "text": t["text"].strip()}
                for t in turns if t["text"].strip()]
        return {"name": "conversation", "format": fmt, "messages": msgs, "speakers": sorted(speakers)}
    return None


def parse_loose_time(value):
    if not value:
        return None
    from datetime import datetime
    for f in ("%d/%m/%Y %H:%M", "%d/%m/%y %H:%M", "%m/%d/%y %I:%M %p", "%m/%d/%Y %I:%M %p", "%d/%m/%Y %H:%M:%S",
              "%d/%m/%y %H:%M:%S", "%Y-%m-%d %H:%M", "%d.%m.%y %H:%M", "%d.%m.%Y %H:%M"):
        try:
            return datetime.strptime(value.replace(".", "/") if "/" in f else value, f).astimezone().isoformat(timespec="seconds")
        except ValueError:
            continue
    return None


def conversation_passages(convs):
    """One passage per message (long ones split), each saying which conversation and which message it is."""
    out = []
    for ci, c in enumerate(convs, 1):
        for mi, m in enumerate(c["messages"], 1):
            pieces = split_long(m["text"])
            for k, piece in enumerate(pieces, 1):
                part = f"{c['name']} · message {mi}" + (f" (part {k} of {len(pieces)})" if len(pieces) > 1 else "")
                out.append({"text": piece, "part": part, "speaker": m["speaker"], "role": m["role"], "at": m.get("at")})
    return out


# --- documents, code, data, recordings -----------------------------------------------------------------

MARKER = re.compile(r"^--- (page|slide|cell) (\d+)(?: \(\w+\))? ---$|^## sheet: (.+?)(?: \(|$)")
HEADING = re.compile(r"^(#{1,6})\s+(.+)$")


def chunk_document(text):
    """Paragraphs gathered into passages of about PASSAGE characters, each labeled with where it is: the page
    (PDFs), slide, cell or sheet, and the headings it sits under ("Design › Retries"). A new section starts a
    new passage, so a passage is usually one section (or a piece of a long one)."""
    out, buf, where, path, label = [], [], None, [], None
    text = headings_apart(text)

    def flush():
        if buf:
            body = "\n\n".join(buf).strip()
            for piece in split_long(body):
                out.append({"text": piece, "part": label})
            buf.clear()

    for para in re.split(r"\n\s*\n", text):
        para = para.strip("\n")
        if not para.strip():
            continue
        first = para.strip().splitlines()[0]
        m = MARKER.match(first.strip())
        if m:
            flush()
            where = f"{m.group(1)} {m.group(2)}" if m.group(1) else f"sheet {m.group(3)}"
            para = "\n".join(para.strip().splitlines()[1:])
            if not para.strip():
                continue
            first = para.strip().splitlines()[0]
        h = HEADING.match(first.strip()) if len(para.strip().splitlines()) == 1 else None
        body = [b for b in buf if not HEADING.match(b.strip())]
        if h:
            if body:                                   # a new section: the last one is done
                flush()
            level = len(h.group(1))
            path = [x for x in path if x[0] < level] + [(level, h.group(2).strip()[:60])]
        elif body and sum(len(b) for b in buf) + len(para) > PASSAGE:
            flush()                                    # long section: carry on in a new passage, same label
        if not buf:
            label = ", ".join(x for x in (where, " › ".join(t for _, t in path)) if x) or None
        buf.append(para)
    flush()
    return out


def headings_apart(text):
    """Give every heading line (outside code fences) a paragraph of its own, so a reader that puts a heading
    directly above its text (Word documents do) still gets its sections labeled."""
    out, fenced = [], False
    for line in text.splitlines():
        if line.strip().startswith("```"):
            fenced = not fenced
        if not fenced and HEADING.match(line.strip()):
            out += ["", line, ""]
        else:
            out.append(line)
    return "\n".join(out)


def split_long(text, limit=MAX_PASSAGE):
    """Split text longer than limit at paragraph, then sentence, then word boundaries."""
    text = text.strip()
    if len(text) <= limit:
        return [text] if text else []
    out, rest = [], text
    while len(rest) > limit:
        cut = rest.rfind("\n\n", 0, limit)
        if cut < limit // 2:
            cut = max(rest.rfind(". ", 0, limit), rest.rfind("\n", 0, limit))
        if cut < limit // 2:
            cut = rest.rfind(" ", 0, limit)
        if cut < limit // 2:
            cut = limit
        out.append(rest[:cut + 1].strip())
        rest = rest[cut + 1:]
    if rest.strip():
        out.append(rest.strip())
    return out


def chunk_code(text, path):
    """Code in passages of up to CODE_LINES lines, cut at a blank line or a top-level line where possible, each
    labeled path:first-last."""
    lines = text.splitlines()
    out, start = [], 0
    while start < len(lines):
        end = min(len(lines), start + CODE_LINES)
        if end < len(lines):
            for cut in range(end, start + CODE_LINES // 2, -1):           # prefer to end before a top-level line
                if not lines[cut].strip() or (lines[cut][:1].strip() and not lines[cut - 1].rstrip().endswith((",", "(", "[", "{", "\\"))):
                    end = cut
                    break
        body = "\n".join(lines[start:end])
        while len(body) > MAX_PASSAGE and end - start > 5:                # long lines: fewer of them
            end = start + (end - start) * 2 // 3
            body = "\n".join(lines[start:end])
        if body.strip():
            out.append({"text": body[:MAX_PASSAGE * 2], "part": f"{path}:{start + 1}-{end}"})
        start = end
    return out


def chunk_table(text, sep):
    rows = text.splitlines()
    if not rows:
        return []
    header, body = rows[0], rows[1:]
    out = []
    for i in range(0, len(body), DATA_ROWS):
        chunk = body[i:i + DATA_ROWS]
        out.append({"text": header + "\n" + "\n".join(chunk), "part": f"rows {i + 1}-{i + len(chunk)}"})
    return out or [{"text": header, "part": "header"}]


def chunk_sheets(text):
    out = []
    for block in re.split(r"(?m)^## sheet: ", text):
        if not block.strip():
            continue
        name, _, rest = block.partition("\n")
        name = re.sub(r" \(.*\)$", "", name.strip())
        for p in chunk_table(rest.strip(), "\t"):
            p["part"] = f"sheet {name}, {p['part']}"
            out.append(p)
    return out


def chunk_transcript(text):
    """A recording's transcript (lines with times) in passages of about PASSAGE characters."""
    out, buf, first = [], [], None
    for line in (text or "").splitlines():
        m = re.match(r"^\[?(\d+:\d{2}(?::\d{2})?)", line.strip())
        if m and first is None:
            first = m.group(1)
        buf.append(line)
        if sum(len(b) for b in buf) > PASSAGE:
            out.append({"text": "\n".join(buf), "part": f"from {first}" if first else None})
            buf, first = [], None
    if buf:
        out.append({"text": "\n".join(buf), "part": f"from {first}" if first else None})
    return out


# =====================================================================================================
# The queue: one job at a time, in the background, watched by the looking glass
# =====================================================================================================

class Intake:
    def __init__(self, tell=lambda event: None):
        self.jobs, self.tell = [], tell
        self.lock, self.wake = threading.Lock(), threading.Event()
        self.paused = False
        self.thread = None
        self.next_id = 1

    def start(self):
        if not self.thread:
            self.thread = threading.Thread(target=self.loop, daemon=True)
            self.thread.start()

    # --- adding ---------------------------------------------------------------------------------
    def add_file(self, mem, path, name, came=None, record=None, home=None):
        return self.queue({"what": "file", "path": str(path), "name": name, "came": came, "record": record,
                           "home": str(home) if home else None}, mem)

    def add_tree(self, mem, folder, name, came=None, cleanup=False):
        return self.queue({"what": "folder", "path": str(folder), "name": name, "came": came, "cleanup": cleanup}, mem)

    def queue(self, job, mem):
        with self.lock:
            job.update(id=self.next_id, mem=mem, memory=mem.name, state="queued", queued=time.time(), done=0, total=0,
                       passages=0, rate=None, eta=None, problem=None, source=None, kind=None, steps=[])
            self.next_id += 1
            self.jobs.append(job)
        self.start()
        self.wake.set()
        self.announce(job)
        return self.public(job)

    # --- control --------------------------------------------------------------------------------
    def pause(self, on=True):
        self.paused = bool(on)
        self.wake.set()
        self.tell({"intake": {"paused": self.paused}})

    def cancel(self, jid):
        for j in self.jobs:
            if j["id"] == jid and j["state"] == "queued":
                j["state"] = "cancelled"
                self.announce(j)
                return True
        return False

    def busy(self):
        return any(j["state"] in ("queued", "reading", "storing", "embedding") for j in self.jobs)

    # --- what the looking glass sees -------------------------------------------------------------
    def public(self, j):
        return {k: v for k, v in j.items() if k not in ("mem", "record", "home", "path", "cleanup")}

    def status(self):
        return {"paused": self.paused, "busy": self.busy(), "jobs": [self.public(j) for j in reversed(self.jobs[-60:])]}

    def announce(self, job):
        try:
            self.tell({"intake": self.public(job)})
        except Exception:
            pass

    # --- doing ------------------------------------------------------------------------------------
    def loop(self):
        while True:
            self.wake.wait(timeout=5)
            self.wake.clear()
            while not self.paused:
                job = next((j for j in self.jobs if j["state"] == "queued"), None)
                if not job:
                    break
                self.run(job)

    def run(self, job):
        mem = job["mem"]
        started = time.time()
        try:
            if mem.closed:
                raise ValueError("that memory was closed (an incognito conversation ended)")
            job["state"] = "reading"
            self.announce(job)
            if job["what"] == "folder":
                kind, passages, meta = read_tree(Path(job["path"]), job["name"])
            else:
                kind, passages, meta = read_any(job["path"], job["name"], job.get("record"), job.get("home"))
            job.update(kind=kind, total=len(passages), meta={k: v for k, v in meta.items() if k != "problems"},
                       read_seconds=round(time.time() - started, 1))
            job["steps"].append(f"read as {kind} ({meta.get('format')}): {len(passages):,} passages in {job['read_seconds']}s")
            if not passages:
                job.update(state="problem" if kind not in ("picture",) else "nothing", problem=meta.get("note") or "nothing in it to read")
                return
            from memory import digest_of
            digest = digest_of(passages)
            same = mem.source_with_digest(digest)
            if same:
                job.update(state="duplicate", source=same["id"], problem=f"already in the library as s{same['id']} ({same['name']})")
                return
            sid = mem.add_source(job["name"], kind, came=job.get("came"), digest=digest, meta=meta)
            job.update(source=sid, state="storing")
            self.announce(job)
            ids = []
            for i in range(0, len(passages), 200):
                ids += mem.add_passages(sid, passages[i:i + 200])
                job["done"] = len(ids)
            job.update(passages=len(ids), state="embedding", done=0, total=len(ids))
            job["steps"].append(f"stored {len(ids):,} passages as s{sid}: searchable by words now")
            self.announce(job)
            from memory import embedder
            if embedder.ready:
                t0, last = time.time(), [0.0]

                def progress(done):
                    elapsed = time.time() - t0
                    job["done"] = done
                    job["rate"] = round(done / elapsed, 2) if elapsed > 0 else None
                    job["eta"] = round((len(ids) - done) / job["rate"]) if job["rate"] else None
                    if time.time() - last[0] > 1.0 or done == len(ids):
                        last[0] = time.time()
                        self.announce(job)
                    if mem.closed:
                        raise ValueError("that memory was closed partway")
                mem.embed_passages(ids, progress=progress)
                job["steps"].append(f"meaning vectors for {len(ids):,} passages in {time.time() - t0:.0f}s")
            else:
                job["steps"].append("search by meaning isn't on yet: vectors are added when it is")
            mem.finish_source(sid, "stored", {"seconds": round(time.time() - started, 1)})
            job.update(state="stored", eta=0)
        except Exception as e:
            job.update(state="problem", problem=f"{type(e).__name__}: {str(e)[:300]}")
            if job.get("source") and not mem.closed:
                try:
                    mem.finish_source(job["source"], "problem", {"problem": job["problem"]})
                except Exception:
                    pass
        finally:
            job["seconds"] = round(time.time() - started, 1)
            if job.get("cleanup"):
                shutil.rmtree(job["path"], ignore_errors=True)
            self.announce(job)
