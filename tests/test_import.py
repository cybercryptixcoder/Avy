"""Offline checks of the Claude export import (tools/claude_export.py, tools/claude_import.py) and what
Avy does with imported conversations. A small made-up export, in every shape the reader accepts. No
network, no model (the writer gets a scripted answer).

    python3 tests/test_import.py
"""

import io
import json
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

import claude_export  # noqa: E402
import claude_import  # noqa: E402
import memory  # noqa: E402
from memory.common import IMPORTED  # noqa: E402
from mind import llm, worker, writer  # noqa: E402

fails = []


def ok(name, condition, detail=""):
    print(("ok    " if condition else "FAIL  ") + name + ("" if condition else f"   ({detail})"))
    if not condition:
        fails.append(name)


ROOT_PARENT = claude_export.ROOT_PARENT
U = lambda n: f"0000000{n}-aaaa-4bbb-8ccc-dddddddddddd"
# What must never reach the log: Claude's thinking, tool calls and results, attachment contents, injected
# prompts, project documents, Claude's own memories, and the branch a conversation didn't end on.
SECRETS = ["THINKING-XYZ", "WEB-PAGE-XYZ", "TOOL-INPUT-XYZ", "ATTACHED-CONTENT-XYZ", "INJECTED-XYZ", "PROJECT-DOC-XYZ",
           "MEMORY-XYZ", "ABANDONED-BRANCH-XYZ", "PROMPT-TEMPLATE-XYZ"]


def msg(uuid, sender, at, parent, blocks, text=None, attachments=(), files=()):
    return {"uuid": uuid, "sender": sender, "created_at": at, "updated_at": at, "parent_message_uuid": parent,
            "text": text if text is not None else " ".join(b.get("text", "") for b in blocks), "content": blocks,
            "attachments": list(attachments), "files": list(files)}


gadget = {"uuid": U(1), "name": "Plant waterer", "created_at": "2025-03-01T10:00:00Z", "summary": "a summary", "chat_messages": [
    msg("m1", "human", "2025-03-01T10:00:00.000000Z", ROOT_PARENT,
        [{"type": "text", "text": "I want to build a self-watering pot for my basil."}, {"type": "injected_prompt_block", "text": "INJECTED-XYZ"}],
        attachments=[{"file_name": "notes.txt", "file_size": 20, "file_type": "txt", "extracted_content": "ATTACHED-CONTENT-XYZ"}],
        files=[{"file_uuid": U(9), "file_name": "basil.jpg"}]),
    msg("m2", "assistant", "2025-03-01T10:00:30.000000Z", "m1",
        [{"type": "thinking", "thinking": "THINKING-XYZ"}, {"type": "tool_use", "name": "web_search", "input": {"query": "TOOL-INPUT-XYZ"}},
         {"type": "tool_result", "content": [{"type": "knowledge", "text": "WEB-PAGE-XYZ"}]},
         {"type": "text", "text": "A capacitive soil sensor and a small pump would do it."}]),
    msg("m3", "human", "2025-03-01T10:02:00.000000Z", "m2", [{"type": "text", "text": "ABANDONED-BRANCH-XYZ"}]),
    msg("m4", "human", "2025-03-01T10:03:00.000000Z", "m2", [{"type": "text", "text": "What pump should I get?"}]),
    msg("m5", "assistant", "2025-03-01T10:03:30.000000Z", "m4", [{"type": "text", "text": "Do you want it quiet?"},
                                                                   {"type": "voice_note", "text": "A peristaltic pump won't siphon."}]),
    msg("m6", "human", "2025-03-01T10:05:00.000000Z", "m5", [], text=""),
]}
early = {"uuid": U(2), "name": "Ant colonies", "created_at": "2024-07-01T20:00:00Z", "chat_messages": [
    msg("e1", "human", "2024-07-01T20:00:00Z", ROOT_PARENT, [{"type": "text", "text": "Ant colonies find food with no leader."}]),
    msg("e2", "assistant", "2024-07-01T20:00:20Z", "e1", [{"type": "text", "text": "Yes: pheromone trails that evaporate."}]),
    msg("e3", "human", "2024-07-01T20:01:00Z", "e2", [{"type": "text", "text": "Such an elegant kind of memory."}]),
]}
empty = {"uuid": U(3), "name": "Nothing", "created_at": "2025-01-01T00:00:00Z", "chat_messages": []}
project_chat = {"uuid": U(4), "title": "Chat", "project": {"uuid": U(5), "name": "Design"}, "created_at": "2025-02-01T09:00:00.000000",
                "messages": [
                    {"uuid": "p1", "role": "user", "created_at": "2025-02-01T09:00:00.000000",
                     "content": {"role": "user", "content": "Make me a logo for the studio.", "timestamp": "2025-02-01T09:00:00.000Z"}},
                    {"uuid": "p2", "role": "assistant", "created_at": "2025-02-01T09:00:40.000000",
                     "content": {"role": "assistant", "content": "Here's a concept: a single bold monogram.",
                                 "contentBlocks": [{"type": "thinking", "text": "THINKING-XYZ"}]}}]}
project = {"uuid": U(6), "name": "Proj", "description": "d", "prompt_template": "PROMPT-TEMPLATE-XYZ", "is_private": True,
           "docs": [{"uuid": U(7), "filename": "doc.md", "content": "PROJECT-DOC-XYZ"}]}
memories = {"conversations_memory": "MEMORY-XYZ", "project_memories": {U(8): "MEMORY-XYZ"},
            "memory_files": [{"path": "/x.md", "content": "MEMORY-XYZ"}], "account_uuid": U(9)}
users = [{"uuid": U(9), "full_name": "Someone", "email_address": "someone@example.com"}]
combined = {f"{U(6)}.json": project, "conversations.json": [gadget, early, empty], f"{U(4)}.json": project_chat,
            "users.json": users, "login_history.json": {"entries": []}, f"{U(8)}.json": memories}

tmp = Path(tempfile.mkdtemp())
(tmp / "combined.json").write_text(json.dumps(combined))
with zipfile.ZipFile(tmp / "combined.zip", "w") as z:
    z.write(tmp / "combined.json", "combined_master_export.json")
with zipfile.ZipFile(tmp / "standard.zip", "w") as z:           # the zip claude.ai emails
    z.writestr("conversations.json", json.dumps([gadget, early, empty]))
    z.writestr("users.json", json.dumps(users))
    z.writestr("projects.json", json.dumps([project]))
    z.writestr("memories.json", json.dumps([memories]))
(tmp / "conversations.json").write_text(json.dumps([gadget, early, empty]))


def read(path):
    convs, skipped = claude_import.read_all(path, progress=False)
    return {c.uuid: c for c in convs}, skipped


# --- 1. reading ------------------------------------------------------------------------------------
convs, skipped = read(tmp / "combined.json")
g = convs[U(1)]
ok("every conversation is found, the project chat too", set(convs) == {U(1), U(2), U(3), U(4)}, list(convs))
ok("an edited conversation keeps the branch it ended on", [m.uuid for m in g.messages] == ["m1", "m2", "m4", "m5"] and g.off_branch == 1,
   [m.uuid for m in g.messages])
ok("...and an empty message is left out", g.empty == 1)
ok("your words are what you typed; Claude's are its replies (a voice note too)",
   g.messages[0].text == "I want to build a self-watering pot for my basil." and g.messages[1].text == "A capacitive soil sensor and a small pump would do it."
   and g.messages[3].text == "Do you want it quiet?\n\nA peristaltic pump won't siphon.", [m.text for m in g.messages])
ok("roles: you and Claude", [m.role for m in g.messages] == ["user", "assistant", "user", "assistant"])
ok("attachments and files are named, with sizes, never their contents",
   g.messages[0].attachments == [{"name": "notes.txt", "chars": len("ATTACHED-CONTENT-XYZ")}] and g.messages[0].files == ["basil.jpg"])
everything = json.dumps([[m.__dict__ for m in c.messages] for c in convs.values()])
ok("nothing that should be left out got in (thinking, tools, web pages, attachments, injected prompts, the abandoned branch)",
   not any(s in everything for s in SECRETS), [s for s in SECRETS if s in everything])
ok("times are local, with their offset", g.messages[0].at[19:] in ("+00:00", "-04:00", "-05:00") or len(g.messages[0].at) == 25, g.messages[0].at)
pc = convs[U(4)]
ok("a project chat reads as a conversation, with its project", pc.source == "project chat" and pc.project == "Design"
   and [m.role for m in pc.messages] == ["user", "assistant"] and pc.messages[1].text == "Here's a concept: a single bold monogram.")
ok("projects, Claude's memories and account records are skipped and counted",
   (skipped.projects, skipped.project_docs, skipped.memories, skipped.users) == (1, 1, 1, 2), skipped)
for name in ("combined.zip", "standard.zip", "conversations.json"):
    other, _ = read(tmp / name)
    same = all([m.text for m in other[k].messages] == [m.text for m in convs[k].messages] for k in other)
    ok(f"the same from {name}", same and U(1) in other and U(2) in other, list(other))
saved = claude_export.ijson
claude_export.ijson = None
other, _ = read(tmp / "combined.json")
claude_export.ijson = saved
ok("the same without ijson (the whole file loaded instead)", [m.text for m in other[U(1)].messages] == [m.text for m in g.messages])

# --- 2. importing ----------------------------------------------------------------------------------
mem = memory.Memory(tmp / "memory-claude.db")
done = claude_import.import_conversations(mem, list(convs.values()), say=lambda *a: None)
rows = mem.messages_between(1, mem.last_id())
ok("conversations go in, oldest first, each in one piece", done == {"conversations": 3, "messages": 9}
   and [r["meta"]["conversation"] for r in rows] == [U(2)] * 3 + [U(4)] * 2 + [U(1)] * 4, [r["meta"]["conversation"][:8] for r in rows])
ok("...marked as imported, with Claude as the assistant", all(r["via"] == IMPORTED for r in rows) and memory.who("assistant", IMPORTED) == "Claude"
   and memory.who("assistant", "text") == "Avy")
ok("...with the conversation's name and Claude's message id kept", rows[0]["meta"]["conversation_name"] == "Ant colonies" and rows[0]["meta"]["claude"] == "e1")
ok("importing again adds nothing", claude_import.import_conversations(mem, list(convs.values()), say=lambda *a: None)["messages"] == 0
   and mem.last_id() == 9)
ok("everything imported waits for the import's own run", mem.waiting_import() == 9 and mem.stats()["waiting_import"] == 9)
ok("a stretch never runs from one conversation into the next", claude_import.stretches(mem, writer.PAGE) == [(1, 3), (4, 5), (6, 9)],
   claude_import.stretches(mem, writer.PAGE))

# --- 3. the background mind leaves it alone ---------------------------------------------------------
asked = []
llm.app.update(ask=lambda payload: asked.append(payload) or {}, prices={}, effort=lambda: "none")
worker.app.update(page=lambda: writer.PAGE, main=lambda: mem, memories=lambda: [mem])
ok("the background mind doesn't write imported conversations by itself", worker.write_due(mem) == [] and not asked)
ok("...nor reflect while they wait", worker.due_for_reflection(mem) is False)

# --- 4. the writer, on an imported stretch ---------------------------------------------------------
job = writer.Write(mem, 6, 9)
prompt = job.prompt()[1]["content"]
ok("the writer is told it's an earlier conversation with Claude, and its title",
   "earlier conversations with Claude" in prompt and '"Plant waterer"' in prompt and "Claude: A capacitive soil sensor" in prompt, prompt[:600])
ok("...it sees what was attached, by name", "[attached: notes.txt (20 characters), basil.jpg]" in prompt)
ok("...and no context from another conversation", "Just before" not in prompt and "Make me a logo" not in prompt)
answer = {"headline": "Planning a self-watering basil pot", "nodes": [
    {"ref": "n1", "replaces": None, "shape": "thing", "label": "project", "title": "Self-watering basil pot", "text": "A pot Shreyas wants to build.",
     "when": None, "evidence": [{"message": 6, "quote": "I want to build a self-watering pot for my basil."}]},
    {"ref": "n2", "replaces": None, "shape": "idea", "label": "suggestion", "title": "Capacitive sensor and pump",
     "text": "Claude suggested a capacitive soil sensor and a small pump.", "when": None,
     "evidence": [{"message": 7, "quote": "A capacitive soil sensor and a small pump would do it."}]},
    {"ref": "n3", "replaces": None, "shape": "idea", "label": "question", "title": "Quiet pump question", "text": "Claude asked about noise.",
     "when": None, "evidence": [{"message": 9, "quote": "Do you want it quiet?"}]}],
    "edges": [{"from": "n2", "to": "n1", "kind": "part_of", "reason": "the parts it would be built from", "said": None}]}
plan = job.check(answer)
ok("Claude's questions aren't knowledge either", any("question" in p for p in plan.problems), plan.problems)
answer["nodes"].pop()


def answers(a):
    llm.app.update(ask=lambda payload: {"choices": [{"finish_reason": "tool_calls", "message": {"tool_calls": [
        {"id": "c1", "type": "function", "function": {"name": "write_episode", "arguments": json.dumps(a)}}]}}],
        "usage": {"prompt_tokens": 100, "completion_tokens": 20}})


answers({"headline": "Ants and memory", "nodes": [], "edges": []})
runs = worker.write_due(mem, force=True, limit=1, imported=True, connect=False)
ok("the import's run writes one stretch at a time, in order", runs and runs[0]["status"] == "ok" and (runs[0]["first"], runs[0]["last"]) == (1, 3)
   and mem.written_up_to() == 3, runs)
worker.write_due(mem, force=True, limit=1, imported=True, connect=False)
answers(answer)
runs = worker.write_due(mem, force=True, limit=1, imported=True, connect=False)
ok("...and writes what was said", runs and runs[0]["status"] == "ok" and (runs[0]["first"], runs[0]["last"]) == (6, 9) and runs[0]["nodes"] == 2, runs)
pot = next(n for n in mem.current_nodes() if n["title"] == "Self-watering basil pot")
sensor = next(n for n in mem.current_nodes() if n["title"] == "Capacitive sensor and pump")
ok("what you said is yours; what Claude said is Claude's (not Avy's)", mem.standing(pot) == "you said" and mem.standing(sensor) == "Claude said"
   and mem.speaker(sensor) == "claude", (mem.standing(pot), mem.standing(sensor)))
trace = mem.recall("capacitive sensor pump basil pot", depth="deep", words=True, meaning=False)
ok("Avy's memory note puts Claude's words in their own section", "What Claude, the assistant he talked to before you existed" in trace["briefing"]
   and "Claude:" in trace["briefing"], trace["briefing"][:500])
ok("once everything's written, nothing waits", mem.waiting_import() == 0)

# --- 5. the plan ------------------------------------------------------------------------------------
mem2 = memory.Memory(tmp / "plan.db")
claude_import.import_conversations(mem2, list(convs.values()), say=lambda *a: None)
e = claude_import.estimate(mem2, "none")
ok("the plan counts stretches, days, calls and a cost", e["stretches"] == 3 and e["days"] == 3 and e["calls"] > 0 and e["dollars"] > 0, e)
ok("...and thinking costs more", claude_import.estimate(mem2, "high")["dollars"] > e["dollars"])

print(f"\n{len(fails)} failed" + (": " + ", ".join(fails) if fails else ""))
sys.exit(1 if fails else 0)
