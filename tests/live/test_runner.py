"""Offline checks of the live runner itself (no model calls): python3 tests/live/test_runner.py"""
import importlib.util
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("liverun", HERE / "run.py")
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)

# A call that fails (a rate limit, a timeout) is recorded as failed and never graded as a 0.
o = m.Live.__new__(m.Live)
said = []; graded = []
o.say = said.append; o.clock = lambda *a: None; o.moment = lambda *a: None; o.write_due = lambda: None
def answer(p, setup):
    if setup == "rules": raise RuntimeError("Luminal 429: client-request-rate-limit")
    return {"setup": setup, "answer": "fine", "retrieval": {"covered": [], "items": 1}, "kept": [], "seconds": 1}
o.answer = answer
o.grade = lambda p, ans: graded.append(ans) or {"score": 1.0, "marks": [], "invented": False}
rec = o.probe({"id": "x", "day": 1, "at": "09:00", "ask": "q?", "needs": [], "setups": ["app", "rules"]})
by = {a["setup"]: a for a in rec["answers"]}
assert by["app"]["grade"]["score"] == 1.0
assert by["rules"]["grade"]["score"] is None and by["rules"]["grade"]["failed"], by["rules"]
assert "429" in by["rules"]["failed"]
assert graded == ["fine"], graded           # the judge never saw the error
assert any("FAILED (not graded)" in s for s in said), said
md = m.report({"scenario": "s", "stamp": "t", "about": "", "seconds": 60, "cost": {}, "probes": [rec],
               "final": {"stats": {"messages": 0, "episodes": 0, "nodes": 0, "inferred": 0, "ideas": 0, "connections": 0}}, "runs": [], "refused": []})
assert "| x | 1.0 | failed |" in md, md[:400]
print("ok: failed call recorded, not graded; report shows 'failed'")
