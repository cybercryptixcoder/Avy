"""Offline checks for her self-model (selfcode.py), the atlas, and plain chat's store. python3 tests/test_self.py"""
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import chats      # noqa: E402
import selfcode   # noqa: E402

g = selfcode.graph()
assert "c:app.py:Turn.ask" in g["nodes"] and "c:/api/desk" in g["nodes"] and "c:index.html:send" in g["nodes"]
out, inn = selfcode.neighbours("c:app.py:Turn.ask")
assert ("contains", "c:app.py:Turn") in inn
assert "calls_api" in selfcode.look("index.html:send")
assert "def ask(self)" in selfcode.read("Turn.ask")
assert "isn't yours" in selfcode.read(path=".env") or "no file" in selfcode.read(path=".env")
assert selfcode.checked("x.py", "def f(:\n") and not selfcode.checked("x.py", "x = 1\n")
assert "isn't one of your code files" in selfcode.edit(".env", "a", "b", why="test")
assert "Say why" in selfcode.edit("chats.py", "a", "b")
print("✓ the code graph:", len(g["nodes"]), "nodes,", len(g["edges"]), "edges")

with tempfile.TemporaryDirectory() as d:
    c = chats.Chats(Path(d) / "chats.db")
    a = c.new()
    c.add(a["id"], "user", "hello there, how are you today friend")
    c.add(a["id"], "assistant", "x" * 200_000)
    c.add(a["id"], "user", "and now?")
    msgs, dropped = c.context(a["id"], 32_000)
    assert msgs[0]["role"] == "system" and msgs[-1]["content"] == "and now?" and dropped == 2, (len(msgs), dropped)
    assert c.get(a["id"])["title"].startswith("hello there")
    c.delete(a["id"])
    assert not c.list()
print("✓ plain chat: conversations, titles, the context window")
print("all self checks passed")
