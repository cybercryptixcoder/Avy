"""Read a Claude data export as conversations, one at a time, without loading the whole file.

Accepts any of:
  - the zip claude.ai emails you (conversations.json, users.json, projects.json, memories.json inside)
  - a combined JSON of an export: one object whose keys are the export's file names
    ("conversations.json": [...], "users.json": [...], "<uuid>.json": a project, a project chat, memories)
  - either of those zipped, or a bare conversations.json

What comes out (Conversation, Message below) is only what was said in conversations:
  - your words: the text you typed (not files you attached; their names are kept)
  - Claude's words: its replies (not its thinking, its tool calls or what tools returned, like web pages)
  - when a conversation branched (you edited a message, or regenerated a reply), only the branch it
    ended on: the path from its newest message back to the start
Projects, project documents and Claude's own memories are skipped and counted (memory is rebuilt from
the conversations themselves).

The file is streamed with ijson (pip install ijson). Without ijson it falls back to loading the whole
file, which needs a few GB of memory for a big export.
"""

import io
import json
import re
import zipfile
from dataclasses import dataclass, field
from datetime import datetime, timezone

try:
    import ijson
    from ijson.common import ObjectBuilder
except ImportError:          # pragma: no cover - the fallback is tested by hand
    ijson = None

ROOT_PARENT = "00000000-0000-4000-8000-000000000000"   # what a conversation's first message points back to
UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")


@dataclass
class Message:
    uuid: str
    at: str                        # when it was sent, as local time with its offset (like Avy's own stamps)
    role: str                      # "user" or "assistant" (Claude)
    text: str
    attachments: list = field(default_factory=list)   # [{"name", "chars"}]: files whose text Claude was given
    files: list = field(default_factory=list)         # names of uploaded files (images, PDFs...)


@dataclass
class Conversation:
    uuid: str
    name: str
    source: str                    # "claude.ai" or "project chat"
    project: str | None
    messages: list                 # [Message], in order, the branch it ended on
    off_branch: int = 0            # messages on branches it didn't end on (left out)
    empty: int = 0                 # messages with no words and no files (left out)

    @property
    def started(self):
        return self.messages[0].at if self.messages else ""


@dataclass
class Skipped:
    """What the export held besides conversations, counted (never imported)."""
    projects: int = 0
    project_docs: int = 0
    memories: int = 0
    users: int = 0
    other: int = 0


# --- reading the file ----------------------------------------------------------------------------

def read(path):
    """Yield every conversation in the export at `path` (Conversation), then a Skipped as the last item."""
    skipped = Skipped()
    for name, opener in _json_files(path):
        with opener() as f:
            for key, value in _entries(f, name):
                conv = _conversation(key, value, skipped)
                if conv is not None:
                    yield conv
    yield skipped


def _json_files(path):
    """[(name, opener)] for the JSON in the export: the file itself, or the .json members of a zip."""
    path = str(path)
    if zipfile.is_zipfile(path):
        z = zipfile.ZipFile(path)
        names = [n for n in z.namelist() if n.lower().endswith(".json") and not n.startswith("__MACOSX")]
        return [(n.rsplit("/", 1)[-1], (lambda n=n: z.open(n))) for n in names]
    return [(path.rsplit("/", 1)[-1], lambda: open(path, "rb"))]


def _entries(f, filename):
    """(key, value) pairs from one JSON file, where key says what the value is:
       - a conversations.json array: ("conversations.json", one conversation) per item, built one at a time
       - an object of export files: (its key, its value) for each, with conversations.json streamed
       - anything else: (filename, the whole value)"""
    if ijson is None:
        data = json.load(io.TextIOWrapper(f, encoding="utf-8"))
        yield from _entries_loaded(data, filename)
        return
    events = ijson.parse(f, use_float=True)
    try:
        _, event, value = next(events)
    except StopIteration:
        return
    if event == "start_array":
        for item in _array_items(events):
            yield filename, item
        return
    if event != "start_map":
        return
    key = None
    for prefix, event, value in events:
        if prefix == "" and event == "map_key":
            key = value
        elif prefix == "" and event == "end_map":
            return
        elif event == "start_array" and _is_conversations(key):
            for item in _array_items(events):
                yield key, item
        else:
            yield key, _build(events, event, value)


def _entries_loaded(data, filename):
    if isinstance(data, list):
        for item in data:
            yield filename, item
    elif isinstance(data, dict):
        for key, value in data.items():
            if isinstance(value, list) and _is_conversations(key):
                for item in value:
                    yield key, item
            else:
                yield key, value
    else:
        yield filename, data


def _is_conversations(name):
    return bool(name) and name.rsplit("/", 1)[-1] == "conversations.json"


def _build(events, event, value):
    """Build one JSON value whose first event has just been read; the rest is read from `events`."""
    if event not in ("start_map", "start_array"):
        return value
    builder, depth = ObjectBuilder(), 1
    builder.event(event, value)
    for _, event, value in events:
        builder.event(event, value)
        if event in ("start_map", "start_array"):
            depth += 1
        elif event in ("end_map", "end_array"):
            depth -= 1
            if depth == 0:
                return builder.value
    return builder.value


def _array_items(events):
    """Right after a start_array: build and yield each element, one at a time."""
    for _, event, value in events:
        if event == "end_array":
            return
        yield _build(events, event, value)


# --- making sense of each entry ------------------------------------------------------------------

def _conversation(key, value, skipped):
    """A Conversation from one export entry, or None (counted in skipped) if it isn't one."""
    if key and key.endswith("login_history.json"):
        skipped.users += 1                       # account records: sign-in history
        return None
    if not isinstance(value, dict):
        if isinstance(value, list) and key and key.endswith("users.json"):
            skipped.users += len(value)
        else:
            skipped.other += 1
        return None
    if "chat_messages" in value:
        return _claude_ai(value)
    if isinstance(value.get("messages"), list) and "project" in value:
        return _project_chat(key, value)
    if "prompt_template" in value or "docs" in value:
        skipped.projects += 1
        skipped.project_docs += len(value.get("docs") or [])
    elif "memory_files" in value or "conversations_memory" in value or "project_memories" in value:
        skipped.memories += 1
    elif "email_address" in value:
        skipped.users += 1
    else:
        skipped.other += 1
    return None


def _claude_ai(c):
    """A conversation from claude.ai (conversations.json)."""
    msgs = c.get("chat_messages") or []
    ordered, off_branch = _final_branch(msgs)
    out, empty = [], 0
    for m in ordered:
        role = "user" if m.get("sender") == "human" else "assistant"
        text = _words(m, role)
        attachments = [{"name": a.get("file_name") or "file", "chars": len(a.get("extracted_content") or "")}
                       for a in m.get("attachments") or []]
        files = [x.get("file_name") or "file" for x in m.get("files") or []]
        if not text.strip() and not attachments and not files:
            empty += 1
            continue
        out.append(Message(uuid=m.get("uuid") or "", at=local_time(m.get("created_at")), role=role, text=text,
                           attachments=attachments, files=files))
    return Conversation(uuid=c.get("uuid") or "", name=c.get("name") or "", source="claude.ai", project=None,
                        messages=out, off_branch=off_branch, empty=empty)


def _words(m, role):
    """What was actually said in a claude.ai message. For you: what you typed. For Claude: its replies,
    without its thinking, tool calls, tool results or internal blocks."""
    blocks = m.get("content") or []
    if not blocks:
        return (m.get("text") or "").strip()
    keep = ("text",) if role == "user" else ("text", "voice_note")
    parts = [(b.get("text") or "").strip() for b in blocks if b.get("type") in keep]
    return "\n\n".join(p for p in parts if p)


def _final_branch(msgs):
    """(the messages on the branch the conversation ended on, in order; how many were left out).
    Without branches (every message has at most one reply), that's simply all of them, by time."""
    by_time = sorted(msgs, key=lambda m: m.get("created_at") or "")
    children = {}
    for m in msgs:
        children.setdefault(m.get("parent_message_uuid"), []).append(m)
    if all(len(v) <= 1 for v in children.values()):
        return by_time, 0
    by_id = {m.get("uuid"): m for m in msgs}
    path, seen, u = [], set(), by_time[-1].get("uuid")
    while u in by_id and u not in seen:
        seen.add(u)
        path.append(by_id[u])
        u = by_id[u].get("parent_message_uuid")
    path.reverse()
    if len(path) < 2:                     # broken links: keep everything rather than lose the conversation
        return by_time, 0
    return path, len(msgs) - len(path)


def _project_chat(key, c):
    """A chat inside a project (the export's <uuid>.json files with "messages")."""
    out, empty = [], 0
    for m in c.get("messages") or []:
        content = m.get("content") or {}
        role = "user" if (m.get("role") or content.get("role")) == "user" else "assistant"
        text = (content.get("content") or "").strip() if isinstance(content, dict) else str(content).strip()
        attachments = [{"name": a.get("name") or "file", "chars": len(a.get("content") or "")}
                       for a in (content.get("attachments") or []) if isinstance(a, dict) and not a.get("hidden")]
        if not text and not attachments:
            empty += 1
            continue
        at = content.get("timestamp") if isinstance(content, dict) and str(content.get("timestamp", "")).endswith("Z") else m.get("created_at")
        out.append(Message(uuid=m.get("uuid") or content.get("id") or "", at=local_time(at), role=role, text=text,
                           attachments=attachments))
    out.sort(key=lambda m: m.at)
    project = (c.get("project") or {}).get("name")
    uuid = c.get("uuid") or (UUID.search(key or "") or [None])[0] or ""
    return Conversation(uuid=uuid, name=c.get("title") or "Chat", source="project chat", project=project,
                        messages=out, empty=empty)


def local_time(value):
    """An export timestamp (UTC, with or without 'Z') as local time with its offset, to the second."""
    if not value:
        return ""
    t = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if t.tzinfo is None:
        t = t.replace(tzinfo=timezone.utc)
    return t.astimezone().isoformat(timespec="seconds")
