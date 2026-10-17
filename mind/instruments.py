"""Her hands on the desk's instruments, during a reply: the calendar (timeline) and her threads.

The instruments are always in view (memory/desk.py builds their face for every message); these tools are how she
writes to them while she talks, the way you'd jot something on the calendar mid-conversation. A call goes through the
one door like everything else, and what comes back tells her plainly what happened (or what to fix), so she can say it
in a few words or try again. The keeper (mind/persona.py) catches dated things she didn't write down.
"""

from memory.desk import say_when

MAX_ROUNDS = 3       # tool rounds in one reply, at most; after that she answers with what she has

TOOLS = [
    {"type": "function", "function": {
        "name": "timeline",
        "description": ("Your calendar. Add something dated he mentions (an appointment, a deadline, a trip, a reminder he "
                        "wants) or a task he means to do; change one that's on it when it moves, gets done or is cancelled. "
                        "Use it whenever a date or a time comes up that he'd want kept, without asking first. Dates: "
                        "YYYY-MM-DD, or YYYY-MM-DDTHH:MM with a time, in his time zone; work them out from the two weeks "
                        "spelled out on your desk."),
        "parameters": {"type": "object", "properties": {
            "action": {"type": "string", "enum": ["add", "change"]},
            "id": {"type": "string", "description": "for change: the item, like t12"},
            "title": {"type": "string", "description": "a few words, like 'Dentist' or 'Thesis draft due'"},
            "kind": {"type": "string", "enum": ["event", "deadline", "reminder", "task"]},
            "start": {"type": "string"},
            "end": {"type": "string"},
            "status": {"type": "string", "enum": ["planned", "done", "cancelled", "missed"]},
            "notes": {"type": "string", "description": "anything worth keeping with it (where, with whom, what to bring)"},
            "thread": {"type": "string", "description": "the thread it belongs to, like th3, if any"},
        }, "required": ["action"]}}},
    {"type": "function", "function": {
        "name": "thread",
        "description": ("Your threads: work in flight that you'll need to pick up later (a project, a bug hunt, a plan with "
                        "steps, something waiting on a result). Open one when such work starts; update it when it moves: "
                        "where it stands, the next step, what it's waiting on, and insights worth carrying (why it's set up "
                        "this way, what a result would mean, what was ruled out and why). Its plan is a tree of steps: add "
                        "steps (under a parent step for sub-steps or options), mark them doing or done, drop dead ends with "
                        "why. Close it when it's finished. Small talk and one-off questions never need a thread."),
        "parameters": {"type": "object", "properties": {
            "action": {"type": "string", "enum": ["open", "update", "close"]},
            "id": {"type": "string", "description": "for update or close: the thread, like th3"},
            "title": {"type": "string"},
            "goal": {"type": "string"},
            "state": {"type": "string", "description": "where it stands now"},
            "next": {"type": "string", "description": "the next step"},
            "waiting": {"type": "string", "description": "what it's waiting on, if anything"},
            "status": {"type": "string", "enum": ["active", "waiting", "paused", "done", "dropped"]},
            "add_insights": {"type": "array", "items": {"type": "string"}},
            "steps": {"type": "array", "items": {"type": "object", "properties": {
                "id": {"type": "string", "description": "an existing step to change, like s3; leave out to add one"},
                "text": {"type": "string"},
                "parent": {"type": "string", "description": "the step this one sits under, like s1"},
                "status": {"type": "string", "enum": ["todo", "doing", "done", "dropped"]},
                "why": {"type": "string", "description": "for dropped: why it's a dead end"}}}},
        }, "required": ["action"]}}},
]

NAMES = {t["function"]["name"] for t in TOOLS}


def use(mem, name, args, source=None):
    """Carry out one tool call. Returns (what to tell her, a short line for the page or None)."""
    if not isinstance(args, dict):
        return "That call's arguments weren't an object; nothing changed.", None
    if name == "timeline":
        op = {"op": "timeline", "by": "avy", "source": source, "why": "she wrote it down in conversation",
              **{k: args.get(k) for k in ("title", "kind", "start", "end", "status", "notes", "thread")}}
        if args.get("action") == "change":
            if not args.get("id"):
                return "To change an item, give its id (like t12). Nothing changed.", None
            op["chain"] = args["id"]
        result = mem.apply(op)
        if not result["applied"]:
            return f"Not saved: {result['why']}. Fix it and call again, or leave it.", None
        item = mem.timeline_item(result["chain"])
        when = say_when(item["start"]) if item["start"] else "no date"
        verb = "already there, updated" if result.get("merged") else ("added" if result.get("changed") == "added" else
                                                                      "unchanged" if result.get("unchanged") else "updated")
        line = f"{item['title']}, {when}" + (f" [{item['status']}]" if item["status"] != "planned" else "")
        return f"t{item['chain']} {verb}: {line}.", f"calendar · {verb}: {line}"
    if name == "thread":
        action = args.get("action")
        op = {"op": "thread", "by": "avy", "source": source, "why": f"she {action}ed it in conversation" if action else "",
              **{k: args.get(k) for k in ("title", "goal", "state", "next", "waiting", "status")},
              "add_insights": args.get("add_insights") or [], "steps": args.get("steps") or []}
        if action in ("update", "close"):
            if not args.get("id"):
                return "To update or close a thread, give its id (like th3). Nothing changed.", None
            op["chain"] = args["id"]
        if action == "close":
            op["status"] = args.get("status") if args.get("status") in ("done", "dropped") else "done"
        result = mem.apply(op)
        if not result["applied"]:
            return f"Not saved: {result['why']}. Fix it and call again, or leave it.", None
        th = mem.thread(result["chain"])
        verb = {"open": "opened", "close": "closed"}.get(action, "updated")
        if result.get("unchanged"):
            verb = "unchanged"
        return (f"th{th['chain']} {verb}. Now:\n" + mem.thread_frontier(th),
                f"thread · {verb}: {th['title']}" + (f" ({th['status']})" if th["status"] != "active" else ""))
    return f"There's no tool called {name}.", None
