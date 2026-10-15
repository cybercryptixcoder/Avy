"""Offline checks of the library intake (intake.py, memory/library.py): anything added is read into passages,
whatever its format, kept word for word, searchable, and brought back by recall and by Avy's own search.
No model, no network (search by meaning only if you pass --meaning <model folder>).

    python3 tests/test_intake.py
"""

import io
import json
import sqlite3
import sys
import tempfile
import time
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import intake  # noqa: E402
import memory  # noqa: E402
from mind import explore, llm  # noqa: E402

fails = []


def ok(name, condition, detail=""):
    print(("ok    " if condition else "FAIL  ") + name + ("" if condition else f"   ({str(detail)[:400]})"))
    if not condition:
        fails.append(name)


if "--meaning" in sys.argv:
    memory.embedder.start(Path(sys.argv[sys.argv.index("--meaning") + 1]))
    memory.embedder.wait(300)

tmp = Path(tempfile.mkdtemp(prefix="avy-intake-test-"))


def write(name, content):
    p = tmp / name
    p.parent.mkdir(parents=True, exist_ok=True)
    (p.write_bytes if isinstance(content, bytes) else p.write_text)(content)
    return p


# --- 1. reading, format by format --------------------------------------------------------------------
doc = write("design.md", "# Ingester\n\nPulls partner feeds.\n\n## Retries\n\nA failed fetch is retried 3 times with backoff "
                         "of 0.5 s, 1 s and 2 s.\n\n## Batching\n\n" + ("Records go in batches of 500. " * 60))
kind, ps, meta = intake.read_any(doc)
ok("a Markdown document: passages under their headings", kind == "document" and any(p["part"] == "Ingester › Retries" and "3 times" in p["text"] for p in ps), ps[:3])
ok("...no passage runs past the limit", all(len(p["text"]) <= intake.MAX_PASSAGE for p in ps), [len(p["text"]) for p in ps])

chatgpt = [{"title": "Trip ideas", "create_time": 1700000000, "current_node": "c", "mapping": {
    "root": {"id": "root", "message": None, "parent": None, "children": ["a"]},
    "a": {"id": "a", "parent": "root", "children": ["b", "x"], "message": {"author": {"role": "user"}, "create_time": 1700000000,
                                                                          "content": {"content_type": "text", "parts": ["where should i go in march?"]}}},
    "x": {"id": "x", "parent": "a", "children": [], "message": {"author": {"role": "assistant"}, "content": {"parts": ["ABANDONED"]}}},
    "b": {"id": "b", "parent": "a", "children": ["c"], "message": {"author": {"role": "assistant"}, "create_time": 1700000060,
                                                                  "content": {"parts": ["Lisbon is lovely in March."]}}},
    "c": {"id": "c", "parent": "b", "children": [], "message": {"author": {"role": "user"}, "content": {"parts": ["book it"]}}}}}] * 3
kind, ps, meta = intake.read_any(write("chatgpt/conversations.json", json.dumps(chatgpt)))
ok("a ChatGPT export: conversations, the branch it ended on, who said what",
   kind == "conversations" and meta["format"] == "chatgpt export" and meta["conversations"] == 3
   and [p["role"] for p in ps[:3]] == ["user", "assistant", "user"] and not any("ABANDONED" in p["text"] for p in ps)
   and ps[1]["speaker"] == "ChatGPT" and ps[0]["at"] and ps[0]["part"].startswith("Trip ideas"), (meta, ps[:3]))

generic = {"title": "Standup", "messages": [{"sender": "me", "text": "shipped the parser", "timestamp": "2026-03-02T10:00:00Z"},
                                            {"sender": "Priya", "text": "nice, i'll review it"},
                                            {"sender": "me", "text": "thanks!"}]}
kind, ps, meta = intake.read_any(write("standup.json", json.dumps(generic)))
ok("any JSON shaped like messages: sender and text, whatever the keys", kind == "conversations" and len(ps) == 3
   and ps[0]["role"] == "user" and ps[1]["role"] == "other" and ps[1]["speaker"] == "Priya" and ps[0]["part"].startswith("Standup"), ps)

whatsapp = "\n".join(["[12/03/2024, 10:15:02] Ananya: are you coming home for diwali?",
                      "[12/03/2024, 10:16:40] Shreyas: yes! flying in on the 28th",
                      "and leaving the 5th", "[12/03/2024, 10:17:00] Ananya: yay", "[12/03/2024, 10:18:00] Shreyas: :)"])
kind, ps, meta = intake.read_any(write("WhatsApp Chat with Ananya.txt", whatsapp))
ok("a WhatsApp export: each message, with its time; a message's next lines stay with it",
   kind == "conversations" and meta["format"] == "whatsapp" and len(ps) == 4 and ps[1]["role"] == "user"
   and "leaving the 5th" in ps[1]["text"] and ps[0]["at"], ps)

labeled = "Me: what's the plan for the thesis?\nClaude: Start with the related work.\nMe: ok, and then?\nClaude: Then the method.\n"
kind, ps, meta = intake.read_any(write("chat.txt", labeled))
ok("a transcript with speaker labels: who's who", kind == "conversations" and [p["role"] for p in ps] == ["user", "assistant"] * 2, ps)

prose = ("This is a normal essay. Note: it has a colon in it.\nAnother line here.\n\nA second paragraph about colons: "
         "they introduce things.\nAnd more text that is not a conversation at all.\n")
kind, ps, meta = intake.read_any(write("essay.txt", prose))
ok("prose with a few colons isn't mistaken for a conversation", kind == "document", (kind, meta))

kind, ps, meta = intake.read_any(write("people.csv", "name,city\n" + "\n".join(f"person{i},city{i}" for i in range(70))))
ok("a CSV: rows in chunks, with the header repeated", kind == "data" and len(ps) == 3 and all(p["text"].startswith("name,city") for p in ps)
   and ps[1]["part"] == "rows 31-60", [p["part"] for p in ps])

code = "\n".join([f"def f{i}(x):\n    return x + {i}\n" for i in range(50)])
kind, ps, meta = intake.read_any(write("src/util.py", code))
ok("code: passages of whole lines, labeled file:lines", kind == "code" and ps[0]["part"].startswith("util.py:1-")
   and all(len(p["text"].splitlines()) <= intake.CODE_LINES for p in ps), [p["part"] for p in ps])

# a codebase, zipped: node_modules, .git and lockfiles left out; a doc inside read as a document
buf = io.BytesIO()
with zipfile.ZipFile(buf, "w") as z:
    z.writestr("proj/README.md", "# Proj\n\nThe retry policy lives in client.py.")
    z.writestr("proj/src/client.py", "RETRIES = 3\nBACKOFF = [0.5, 1, 2]\n\ndef fetch(url):\n    return url\n")
    z.writestr("proj/node_modules/left-pad/index.js", "module.exports = 1")
    z.writestr("proj/.git/HEAD", "ref: refs/heads/main")
    z.writestr("proj/package-lock.json", "{}")
    z.writestr("proj/logo.png", b"\x89PNG\r\n\x1a\n" + b"\0" * 100)
kind, ps, meta = intake.read_any(write("proj.zip", buf.getvalue()))
parts = [p["part"] for p in ps]
ok("a zipped codebase: every file by its own kind, paths kept", meta.get("archive") and any(x.startswith("src/client.py:1-") for x in parts)
   and any(x.startswith("README.md") for x in parts), parts)
ok("...node_modules, .git, lockfiles and pictures left out (and counted)", not any("node_modules" in x or ".git" in x or "lock" in x for x in parts)
   and meta["skipped"]["folders"] >= 2, meta)
ok("...a codebase is called code", kind in ("code", "mixed"), kind)

hostile = io.BytesIO()
with zipfile.ZipFile(hostile, "w") as z:
    z.writestr("../../escaped.txt", "nope")
    z.writestr("ok.txt", "fine words here")
intake.read_any(write("hostile.zip", hostile.getvalue()))
ok("an archive can't write outside where it's unpacked", not (tmp.parent / "escaped.txt").exists() and not Path("/escaped.txt").exists())

# a Claude export, through the same door (the shape claude.ai emails: conversations.json in a zip)
ROOT_PARENT = "00000000-0000-4000-8000-000000000000"
def cmsg(uuid, sender, at, parent, blocks):
    return {"uuid": uuid, "sender": sender, "created_at": at, "updated_at": at, "parent_message_uuid": parent,
            "text": " ".join(b.get("text", "") for b in blocks), "content": blocks, "attachments": [], "files": []}
gadget = {"uuid": "11111111-1111-4111-8111-111111111111", "name": "Plant waterer", "created_at": "2025-03-01T10:00:00Z", "chat_messages": [
    cmsg("m1", "human", "2025-03-01T10:00:00Z", ROOT_PARENT, [{"type": "text", "text": "I want a self-watering pot for my basil."}]),
    cmsg("m2", "assistant", "2025-03-01T10:00:30Z", "m1", [{"type": "thinking", "thinking": "THINKING-XYZ"},
                                                          {"type": "text", "text": "A capacitive sensor and a small pump would do it."}]),
    cmsg("m3", "human", "2025-03-01T10:02:00Z", "m2", [{"type": "text", "text": "ABANDONED-BRANCH-XYZ"}]),
    cmsg("m4", "human", "2025-03-01T10:03:00Z", "m2", [{"type": "text", "text": "What pump should I get?"}])]}
early = {"uuid": "22222222-2222-4222-8222-222222222222", "name": "Ant colonies", "created_at": "2024-07-01T20:00:00Z", "chat_messages": [
    cmsg("e1", "human", "2024-07-01T20:00:00Z", ROOT_PARENT, [{"type": "text", "text": "Ant colonies find food with no leader."}]),
    cmsg("e2", "assistant", "2024-07-01T20:00:20Z", "e1", [{"type": "text", "text": "Yes: pheromone trails that evaporate."}])]}
buf = io.BytesIO()
with zipfile.ZipFile(buf, "w") as z:
    z.writestr("conversations.json", json.dumps([gadget, early]))
    z.writestr("users.json", json.dumps([{"uuid": "u", "full_name": "Someone"}]))
kind, ps, meta = intake.read_any(write("claude.zip", buf.getvalue()))
ok("a Claude export through the same door: conversations, Shreyas's words as his, Claude's as Claude's",
   kind == "conversations" and meta["format"] == "claude export" and meta["conversations"] == 2
   and any(p["speaker"] == "Claude" and p["role"] == "assistant" for p in ps) and any(p["role"] == "user" for p in ps)
   and not any("THINKING-XYZ" in p["text"] or "ABANDONED-BRANCH-XYZ" in p["text"] for p in ps), meta)
ok("...oldest conversation first", ps[0]["part"].startswith("Ant colonies"), ps[0]["part"])

# documents read by files.py's readers: a PDF (pages), a Word file (headings)
def pdf(lines):
    """A small real PDF with a line of text per page (the same maker test_files.py uses)."""
    objects = ["<< /Type /Catalog /Pages 2 0 R >>", None, "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    kids = []
    for line in lines:
        stream = f"BT /F1 18 Tf 72 720 Td ({line}) Tj ET".encode()
        objects.append(f"<< /Length {len(stream)} >>\nstream\n{stream.decode()}\nendstream")
        objects.append(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 3 0 R >> >> "
                       f"/Contents {len(objects)} 0 R >>")
        kids.append(f"{len(objects)} 0 R")
    objects[1] = f"<< /Type /Pages /Kids [{' '.join(kids)}] /Count {len(kids)} >>"
    out, offsets = io.BytesIO(), []
    out.write(b"%PDF-1.4\n")
    for i, body in enumerate(objects, 1):
        offsets.append(out.tell())
        out.write(f"{i} 0 obj\n{body}\nendobj\n".encode())
    xref = out.tell()
    out.write(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode())
    for o in offsets:
        out.write(f"{o:010} 00000 n \n".encode())
    out.write(f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode())
    return out.getvalue()


try:
    import pypdf  # noqa: F401
    kind, ps, meta = intake.read_any(write("paper.pdf", pdf(["Abstract: graphs as memory for agents.", "Results: 85 percent with exploration."])))
    ok("a PDF: a passage per page, labeled with its page", kind == "document" and [p["part"] for p in ps] == ["page 1", "page 2"]
       and "85 percent" in ps[1]["text"], ps)
except ImportError:
    print("skip  a PDF (pypdf isn't installed)")
W = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
docx = io.BytesIO()
with zipfile.ZipFile(docx, "w") as z:
    z.writestr("[Content_Types].xml", "<Types/>")
    z.writestr("word/document.xml", f'<w:document {W}><w:body>'
               '<w:p><w:pPr><w:pStyle w:val="Heading1"/></w:pPr><w:r><w:t>Pump plan</w:t></w:r></w:p>'
               '<w:p><w:r><w:t>Use a peristaltic pump so it never siphons.</w:t></w:r></w:p></w:body></w:document>')
kind, ps, meta = intake.read_any(write("plan.docx", docx.getvalue()))
ok("a Word file: its text, under its headings", kind == "document" and ps[0]["part"] == "Pump plan" and "peristaltic" in ps[0]["text"], ps)

# a picture: described once by the model (a scripted one here), so it can be found by what's in it
try:
    from PIL import Image
    img = io.BytesIO()
    Image.new("RGB", (64, 48), "white").save(img, "PNG")
    kind, ps, meta = intake.read_any(write("whiteboard.png", img.getvalue()))
    ok("a picture with no one to describe it: nothing to keep, and it says so", kind == "picture" and not ps and meta.get("note"), meta)
    seen = []
    intake.HOOKS["describe"] = lambda jpeg: seen.append(jpeg) or "A whiteboard that says 'ship it friday' in red marker."
    kind, ps, meta = intake.read_any(write("whiteboard.png", img.getvalue()))
    ok("a picture: the model's description becomes its passage", kind == "picture" and "ship it friday" in ps[0]["text"]
       and meta.get("described") and str(seen[0]).endswith(".jpg"), (ps, meta))
    intake.HOOKS["describe"] = None
except ImportError:
    print("skip  pictures (Pillow isn't installed)")

# --- 2. the queue: stored, searchable, duplicates refused --------------------------------------------
mem = memory.Memory(tmp / "mem.db")
events = []
q = intake.Intake(tell=events.append)
jobs = [q.add_file(mem, doc, "design.md", came="f-test"), q.add_file(mem, tmp / "chatgpt" / "conversations.json", "conversations.json"),
        q.add_file(mem, tmp / "proj.zip", "proj.zip"), q.add_file(mem, doc, "design copy.md")]
end = time.time() + 60
while q.busy() and time.time() < end:
    time.sleep(0.1)
st = {j["id"]: j for j in q.status()["jobs"]}
ok("every job finishes: stored, or a duplicate of something already in the library",
   [st[j["id"]]["state"] for j in jobs] == ["stored", "stored", "stored", "duplicate"], [st[j["id"]]["state"] for j in jobs])
ok("...and says what happened, step by step", st[jobs[0]["id"]]["steps"] and "read as document" in st[jobs[0]["id"]]["steps"][0], st[jobs[0]["id"]]["steps"])
ok("the looking glass hears about each job as it goes", any("intake" in e for e in events))
sources = mem.sources_list()
ok("three sources in the library, with their passages", len(sources) == 3 and all(s["passages"] > 0 for s in sources), sources)
pid = mem.rows("SELECT id FROM passages LIMIT 1")[0]["id"]
for sql in (f"UPDATE passages SET text = 'x' WHERE id = {pid}", f"DELETE FROM passages WHERE id = {pid}", "DELETE FROM sources WHERE id = 1"):
    try:
        mem.db.execute(sql)
        ok(f"the library refuses: {sql.split()[0]} {sql.split()[2 if sql.startswith('UPDATE') else 2]}", False)
    except sqlite3.DatabaseError:
        ok(f"the library refuses: {sql.split()[0]} {sql.split()[1 if sql.startswith('UPDATE') else 2]}", True)
hits = mem.library_hits([("how many times is a failed fetch retried", 1.0, None)], meaning=False)
best = mem.passage(max(hits, key=lambda h: hits[h]["score"])) if hits else None
ok("passages are searchable by their words", best and "3 times" in best["text"], best)

# --- 3. recall and Avy's own search bring them back -------------------------------------------------
mem.add("user", "what's the backoff in the ingester when a fetch fails?")
trace = mem.recall("what's the backoff in the ingester when a fetch fails?", "", None, "normal", True, False)
ok("recall brings library passages, in their own section of the note", trace["library"] and "From his library" in trace["briefing"]
   and "0.5 s, 1 s and 2 s" in trace["briefing"], trace["briefing"][:800])
ok("...each with its handle, its source and where in it", '[p' in trace["briefing"] and 'from "design.md"; Ingester › Retries' in trace["briefing"], trace["briefing"][-700:])
mem.save_recall(1, trace)
ok("...and the recall record keeps them (without the text)", "library" in json.loads(mem.row("SELECT trace FROM recalls")["trace"]))

shown = []
def scripted(payload):
    text = payload["messages"][-1]["content"]
    shown.append(text)
    keep = [{"item": f"p{m}", "why": "it has the policy"} for m in __import__("re").findall(r"\[p(\d+)\]", text)[:1]]
    args = {"task": "find the retry policy", "questions": [], "open": [], "follow": [], "search": ["retry backoff policy"],
            "keep": keep, "done": bool(keep)}
    return {"choices": [{"message": {"tool_calls": [{"id": "1", "function": {"name": "explore_memory", "arguments": json.dumps(args)}}]},
                         "finish_reason": "tool_calls"}], "usage": {}}
llm.app.update(ask=scripted, prices={}, effort=lambda: "none")
t = explore.explore(explore.Library([mem]), mem, "what's the backoff when a fetch fails?", "", None, "normal", True, False, learn=False)
ok("Avy's own search sees library passages and can keep them (p41)", any("From his library" in s for s in shown) and t["library"]
   and "From his library" in t["briefing"], t["briefing"][:500])

# --- 4. an incognito memory has its own library -----------------------------------------------------
inc = memory.Memory(tmp / "inc" / "x.db", name="incognito", letter="x")
q.add_file(inc, tmp / "standup.json", "standup.json")
end = time.time() + 30
while q.busy() and time.time() < end:
    time.sleep(0.1)
ok("a file added in incognito goes to that memory's library, not the main one",
   inc.library_stats()["sources"] == 1 and mem.library_stats()["sources"] == 3)
lib = explore.Library([mem, inc])
m_, p_ = lib.passage(f"p{inc.rows('SELECT id FROM passages')[0]['id']}", inc)
ok("...and Avy's search can still read the main library from there", m_ is inc and lib.passage(f"p{pid}", inc)[0] is not None)

print(f"\n{len(fails)} failed" + (": " + ", ".join(fails) if fails else ""))
sys.exit(1 if fails else 0)
