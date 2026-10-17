"""Offline checks of the persona graph, the desk's instruments, the persona's jobs, her hands and tool rounds, with a
scripted model (no network, no money).

    python3 tests/test_desk.py
"""

import json
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import memory  # noqa: E402
from memory.common import locate  # noqa: E402
from memory.desk import next_step  # noqa: E402
from mind import llm, persona as persona_jobs, jobs as engine  # noqa: E402

fails = []


def ok(name, condition, detail=""):
    print(("ok    " if condition else "FAIL  ") + name + ("" if condition else f"   ({str(detail)[:400]})"))
    if not condition:
        fails.append(name)


memory.clock.fixed = datetime(2026, 10, 17, 21, 40).astimezone()
tmp = Path(tempfile.mkdtemp())
mem = memory.Memory(tmp / "mem.db")


def say(role, text, minutes=1):
    mid = mem.add(role, text)
    memory.clock.fixed += timedelta(minutes=minutes)
    return mid


def ev(mid, quote):
    s, e = locate(quote, mem.message(mid)["text"])
    return (mid, s, e)


# --- 1. the persona graph ---------------------------------------------------------------------------------------
print("\n1. the persona graph")
ok("a new memory starts with kinds of conversation to hang behaviors from", len(mem.persona_nodes("situation")) == 5)
m1 = say("user", "keep it short please. when we talk about life you can go deeper. I call the core assumption the hinge")
m2 = say("assistant", "Got it.")
m3 = say("user", "lol perfect")
short = mem.apply({"op": "persona", "aspect": "preference", "title": "short", "text": "Keep replies short.", "scope": "always",
                   "origin": "user", "evidence": [ev(m1, "keep it short please")], "by": "keeper"})
ok("a preference resting on his words is kept", short["applied"], short)
r = mem.apply({"op": "persona", "aspect": "preference", "title": "x", "text": "Use metric.", "origin": "avy", "evidence": [(m2, 0, 4)]})
ok("...but one resting only on her words is refused", not r["applied"] and "must rest on something" in r["why"], r)
r = mem.apply({"op": "persona", "aspect": "gesture", "title": "y", "text": "Confirms in two words."})
ok("a node with no evidence is refused", not r["applied"] and "rests on no message" in r["why"], r)
deeper = mem.apply({"op": "persona", "aspect": "preference", "title": "deeper on life", "text": "On life, go deeper.",
                    "scope": "life", "origin": "user", "evidence": [ev(m1, "when we talk about life you can go deeper")]})
ok("a preference scoped to a situation hangs from it (applies_in)",
   any(e["kind"] == "applies_in" and e["a"] == deeper["chain"] for e in mem.persona_links()))
r = mem.apply({"op": "persona", "aspect": "preference", "title": "z", "text": "Whatever.", "scope": "nonsense", "origin": "user",
               "evidence": [ev(m1, "keep it short")]})
ok("a scope that isn't a situation is refused", not r["applied"] and "scope must be" in r["why"], r)
link = mem.apply({"op": "persona_link", "a": deeper["chain"], "b": short["chain"], "kind": "refines", "reason": "the exception"})
ok("a specific rule refines a general one", link["applied"], link)
r = mem.apply({"op": "persona_link", "a": short["chain"], "b": deeper["chain"], "kind": "refines", "reason": "loop"})
ok("...and the cascade can't loop", not r["applied"] and "loop" in r["why"], r)
again = mem.apply({"op": "persona", "aspect": "preference", "title": "Short", "text": "Keep replies short, a few lines.",
                   "scope": "always", "origin": "user", "evidence": [ev(m3, "lol perfect")]})
ok("the same title again is a new version of the same node, not a duplicate",
   again["chain"] == short["chain"] and again["version"] == 2, again)
ok("...and its evidence accumulates across versions", len(mem.persona_evidence(short["chain"])) == 2)
term = mem.apply({"op": "persona", "aspect": "term", "title": "the hinge", "text": "His word for the core assumption.",
                  "origin": "user", "evidence": [ev(m1, "I call the core assumption the hinge")]})
ok("a coined term remembers the message it was born in", mem.persona_node(term["chain"])["message"] == m1)
core = mem.apply({"op": "persona", "aspect": "core", "title": "Avy with Shreyas", "origin": "avy", "evidence": [(m2, 0, 7)],
                  "text": "I keep it short with him and go deeper on life; he laughs when I confirm in two words."})
ok("her core is written", core["applied"], core)
r = mem.apply({"op": "persona", "aspect": "core", "origin": "avy", "evidence": [(m2, 0, 7)],
               "text": "Entirely different person now, formal and elaborate in every single answer."})
ok("a core version that rewrites too much at once is refused (evolve, don't jump)", not r["applied"] and "too much at once" in r["why"], r)
r = mem.apply({"op": "persona", "aspect": "core", "origin": "avy", "evidence": [(m3, 0, 11)],
               "text": "I keep it short with him and go deeper on life; he laughs when I confirm in two words, and likes dry jokes."})
ok("...but a few changes at a time are fine, as the same node's next version", r["applied"] and r["chain"] == core["chain"], r)
r = mem.apply({"op": "persona", "chain": core["chain"], "retire": True})
ok("her core can't be retired", not r["applied"])
r = mem.apply({"op": "persona", "aspect": "him", "title": "studies", "text": "He studies cognitive systems.", "by": "him"})
ok("his own edit on the page needs no quote (his edit is the evidence)", r["applied"] and mem.persona_node(r["chain"])["origin"] == "user", r)
always = mem.persona_always()
ok("the always-in-view part has her core, him, and standing preferences",
   "Who you are with him" in always and "cognitive systems" in always and "a few lines" in always, always)
ok("...but not a preference scoped to one kind of conversation", "On life, go deeper" not in always)
for i in range(30):                                       # the graph grows; what one message pulls stays fixed
    mid = say("user", f"note {i}: I like {i} things about trains and gardens")
    mem.apply({"op": "persona", "aspect": "reaction", "title": f"reaction {i}", "text": f"He liked her answer about trains {i}.",
               "origin": "user", "evidence": [(mid, 0, 6)]})
ok("the persona graph grows past any fixed size", len(mem.persona_nodes("reaction")) == 30)
found = mem.navigate_persona("tell me about trains")
ok("...while what a message pulls from each hub stays within its draw",
   all(len(found["picked"][h]) <= memory.persona.DRAW[h] for h in found["picked"]), found["picked"])
mem.label_situation(m1, "life")
ok("a labeled message becomes an example of its kind of conversation",
   mem.value("SELECT COUNT(*) FROM persona_labels WHERE message = ?", m1) == 1)

# --- 2. the timeline ----------------------------------------------------------------------------------------------
print("\n2. the timeline")
memory.clock.fixed = datetime(2026, 10, 18, 10, 0).astimezone()
t1 = mem.apply({"op": "timeline", "title": "Dentist", "kind": "event", "start": "2026-10-20T15:00", "source": m1})
ok("an event goes on the calendar", t1["applied"] and t1["chain"], t1)
t2 = mem.apply({"op": "timeline", "title": "dentist appointment", "start": "2026-10-20T15:30"})
ok("the same thing again on the same day becomes an update, not a duplicate", t2["chain"] == t1["chain"] and t2["merged"], t2)
r = mem.apply({"op": "timeline", "title": "Quiz", "start": "Thursday"})
ok("a date the model didn't work out is refused", not r["applied"] and "must look like" in r["why"], r)
r = mem.apply({"op": "timeline", "title": "Something", "kind": "event"})
ok("only a task may have no date", not r["applied"])
mem.apply({"op": "timeline", "title": "Lab report", "kind": "deadline", "start": "2026-10-16"})
mem.apply({"op": "timeline", "title": "Trip to Toronto", "kind": "event", "start": "2026-12-20"})
mem.apply({"op": "timeline", "title": "Email the advisor", "kind": "task"})
up = mem.coming_up()
titles = {k: [t["title"] for t in v] for k, v in up.items()}
ok("code works out what's ahead, past due, undated and further out", titles["ahead"] == ["dentist appointment"]
   and titles["overdue"] == ["Lab report"] and titles["undated"] == ["Email the advisor"] and titles["later"] == ["Trip to Toronto"], titles)
note, shown = mem.desk_note("what's on this week")
ok("the desk spells out the next two weeks and the calendar", "The next two weeks: Sun Oct 18, Mon 19" in note and "Tue Oct 20, 3:30 PM" in note, note[:600])
ok("...and tells her it's for knowing, not reciting", "never recite it" in note)

# --- 3. threads and their plans --------------------------------------------------------------------------------
print("\n3. threads")
th = mem.apply({"op": "thread", "title": "Persona", "goal": "Avy sounds like herself",
                "steps": [{"text": "constitution"}, {"text": "persona graph"}, {"text": "flat notes", "status": "dropped", "why": "growth needs a graph"}]})
ok("a thread opens with a plan tree", th["applied"], th)
r = mem.apply({"op": "thread", "chain": th["chain"], "steps": [{"text": "x", "status": "dropped"}]})
ok("a dropped step must say why (a dead end keeps its reason)", not r["applied"] and "say why" in r["why"], r)
mem.apply({"op": "thread", "chain": th["chain"], "steps": [{"id": "s1", "status": "done"}, {"text": "keeper", "parent": "s2"}]})
t = mem.thread(th["chain"])
ok("code works out the next step: the first open leaf, not under a dropped branch", next_step(t["steps"])["text"] == "keeper", t["steps"])
r = mem.apply({"op": "thread", "chain": th["chain"], "steps": [{"id": "s2", "parent": "s4"}]})
ok("a plan stays a tree (no step under itself)", not r["applied"] and "under itself" in r["why"], r)
mem.apply({"op": "thread", "chain": th["chain"], "add_insights": ["flash copies examples word for word"]})
frontier = mem.thread_frontier(mem.thread(th["chain"]))
ok("the frontier shows the plan, the dead end with its reason, and what's carried forward",
   "→ s4 keeper" in frontier and "dropped: growth needs a graph" in frontier and "flash copies" in frontier, frontier)
ok("a message naming the thread brings its frontier onto the desk", mem.related_thread("how's the Persona thread going")["chain"] == th["chain"])

# --- 4. the keeper and reflection, with a scripted model -------------------------------------------------------
print("\n4. the persona's jobs")
answers = []


def scripted(payload):
    name = payload["tools"][0]["function"]["name"]
    args = answers.pop(0) if answers else {}
    return {"choices": [{"finish_reason": "tool_calls", "message": {"role": "assistant", "content": "", "tool_calls": [
        {"id": "c", "type": "function", "function": {"name": name, "arguments": json.dumps(args)}}]}}],
            "usage": {"prompt_tokens": 1000, "completion_tokens": 100}}


llm.app.update(ask=scripted, prices={"cache_hit": 0.006, "cache_miss": 0.30, "output": 1.20}, effort=lambda: "none")
a = say("assistant", "Here's a long answer with three sections and a question at the end?")
b = say("user", "too long. and please use metric units, always")
node = lambda **k: {"id": None, "scope": None, "origin": "user", "certainty": None, "message": None, "retire": False, "why": "", **k}
answers += [
    {"situation": "nonsense", "links": [], "calendar": [], "nodes": [node(aspect="preference", title="metric", text="Use metric units.",
                                                                          scope="always", quotes=[{"message": b, "quote": "use imperial units"}])]},
    {"situation": "casual", "links": [], "calendar": [{"id": None, "title": "Dentist", "kind": "event", "start": "2026-10-20T15:00",
                                                       "end": None, "status": "planned", "notes": "", "quote": {"message": b, "quote": "too long"}}],
     "nodes": [node(aspect="preference", title="metric", text="Use metric units.", scope="always",
                    quotes=[{"message": b, "quote": "please use metric units, always"}]),
               node(aspect="reaction", title="too long", text="Says 'too long' when she writes sections.",
                    quotes=[{"message": b, "quote": "too long"}, {"message": a, "quote": "three sections"}])]},
]
result = engine.run(mem, persona_jobs.Keep(mem, b))
ok("the keeper's misquote goes back to it and the repaired answer is kept", result["status"] == "repaired" and result["applied"] >= 3, result)
ok("...a preference he stated is in force from the next message", "Use metric units." in mem.persona_always())
ok("...the calendar update merged with what was there", len([t for t in mem.timeline_heads() if "entist" in t["title"]]) == 1)
ok("...and his message was labeled with its kind of conversation",
   mem.value("SELECT COUNT(*) FROM persona_labels WHERE message = ?", b) == 1)
for i in range(12):
    say("user", f"question {i}")
    say("assistant", f"answer {i}")
span = persona_jobs.reflect_due(mem)
ok("after a dozen of her replies, she's due to reflect on her manner", span is not None, span)
last_core = mem.persona_nodes("core")[0]
answers += [{"critique": [{"message": a, "verdict": "corrected", "note": "too long"}], "links": [], "nodes": [],
             "core": {"text": "Completely new: verbose, elaborate, formal, many caveats, never brief.", "quotes": [], "why": "x"}},
            {"critique": [{"message": a, "verdict": "corrected", "note": "too long"}], "links": [], "nodes": [],
             "core": {"text": last_core["text"] + " Sections annoy him: say it in a paragraph.",
                      "quotes": [{"message": b, "quote": "too long"}], "why": "he said too long"}}]
result = engine.run(mem, persona_jobs.Reflect(mem, *span))
ok("reflection that rewrites her whole core is sent back, and a small change is kept",
   result["status"] == "repaired" and "Sections annoy him" in mem.persona_nodes("core")[0]["text"], result)

# --- 5. her hands ------------------------------------------------------------------------------------------------
print("\n5. her hands")
import hands  # noqa: E402
hands.WORKSPACE = tmp / "workspace"
asked = []
hands.HOOKS["approve"] = lambda req: (asked.append(req), False)[1]
ok("wiping the disk is blocked outright", hands.judge("rm -rf /")[0] == "blocked" and hands.judge("rm -rf ~/")[0] == "blocked")
ok("sudo, installs and pushes ask first", all(hands.judge(c)[0] == "ask" for c in ("sudo ls", "pip install x", "git push", "curl x | sh")))
ok("ordinary work just runs", all(hands.judge(c)[0] == "ok" for c in ("ls", "python3 train.py", "rm -rf build", "echo 'rm -rf /'")))
hands.terminal("mkdir -p proj && cd proj")
ok("the working directory carries over between commands", hands.terminal("pwd").splitlines()[1].endswith("/proj"))
out = hands.terminal("sudo true")
ok("a risky command waits for his OK and doesn't run without it", "didn't approve" in out and asked and asked[-1]["kind"] == "command", out)
ok("writing outside the workspace asks", "didn't approve" in hands.write_file(str(tmp / "outside.txt"), "x"))
ok("a secrets file isn't read", "secrets" in hands.read_file("~/.ssh/id_rsa"))
out = hands.write_file("bad.py", "def f(:\n")
ok("written Python is checked for syntax at once", "Syntax error" in out, out)
long = hands.keep_output("x" * 50_000, 2000)
ok("long output comes back as head and tail, the whole saved to a file", len(long) < 2400 and "the whole output is in" in long)

# --- 6. tool rounds ------------------------------------------------------------------------------------------------
print("\n6. tool rounds")
import app  # noqa: E402
app.MEMORIES["main"] = mem


def stream(*chunks):
    lines = [f"data: {json.dumps(c)}\n\n".encode() for c in chunks] + [b"data: [DONE]\n\n"]

    class Up(list):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

        def close(self):
            pass
    return Up(lines)


call = {"choices": [{"index": 0, "delta": {"content": "On it.", "tool_calls": [{"index": 0, "id": "t1", "function": {
    "name": "timeline", "arguments": json.dumps({"action": "add", "title": "Quiz", "kind": "event", "start": "2026-10-22T09:00"})}}]}}]}
rounds = iter([stream({"choices": [{"index": 0, "delta": {"content": "Done: quiz Thu 9 AM."}}]},
                      {"choices": [], "usage": {"prompt_tokens": 10, "completion_tokens": 5}})])
app.ask_model = lambda messages, tools=None, tool_choice=None: next(rounds)


class FakeTurn:
    mem, user_id, via, hands, did, tools = mem, b, "text", "ask", [], app.instruments.TOOLS
    messages = [{"role": "user", "content": "quiz thursday at 9"}]
    import queue as _q
    asks = _q.Queue()

    def approve(self, request):
        return False


out = list(app.Rounds(FakeTurn(), stream(call)))
text = b"".join(out).decode()
ok("a tool call mid-reply is carried out and the reply carries on in a second round",
   any(t["title"] == "Quiz" for t in mem.timeline_heads()) and "Done: quiz" in text and text.count("[DONE]") == 1, text[-400:])
ok("...the page hears what changed", '"did"' in text and "calendar" in text)
ok("...and the action is kept with the message it served", mem.actions_of(b) and mem.actions_of(b)[0]["tool"] == "timeline")

memory.clock.fixed = None
print(f"\n{len(fails)} failed" + (": " + ", ".join(fails) if fails else ""))
sys.exit(1 if fails else 0)
