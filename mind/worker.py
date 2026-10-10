"""When the mind works, in the background.

    after each reply   if an episode's worth is waiting (or a sitting has ended): Write it, then
                       Connect the new knowledge to the rest of memory
    when it's quiet    (no message for REFLECT_IDLE minutes, the main memory only): Check what's gone
                       stale, Think about one or two focuses, Connect what Think made, measure health
    /index, /reflect   do it now

Reflection has a daily cap (REFLECT_CALLS model calls), so it costs cents, not dollars.
An incognito memory only gets Write and Connect: it's short-lived.
"""

import threading
from datetime import datetime

from memory import health as measure_health, record_health
from memory.common import minutes_between, stamp

from . import jobs, reflect, writer

REFLECT_IDLE = 30        # minutes of quiet before reflecting
REFLECT_CALLS = 60       # reflection model calls a day, at most
THINKS_PER_SITTING = 3   # Think runs per quiet spell

app = {"memories": lambda: [], "main": lambda: None, "page": lambda: writer.PAGE}
RUN_LOCK = threading.Lock()      # one job at a time
WAKE = threading.Event()
listeners = []                   # functions told about every run (the page's live updates)


def tell(event):
    for fn in list(listeners):
        try:
            fn(event)
        except Exception:
            pass


def run(mem, job):
    tell({"memory": mem.name, "job": job.name, "state": "start", "focus": job.focus})
    result = jobs.run(mem, job)
    tell({"memory": mem.name, "job": job.name, "state": "done", **{k: v for k, v in result.items() if k in
          ("id", "status", "applied", "new_chains", "focus", "episode", "headline")}})
    return result


def write_due(mem, force=False, connect=True, limit=50):
    """Write every stretch that's due, then connect what was written. Returns the runs."""
    results = []
    with RUN_LOCK:
        while not mem.closed and len(results) < limit and (stretch := writer.due(mem, app["page"](), force)):
            failures = mem.value("SELECT COUNT(*) FROM runs WHERE job = 'write' AND focus = ? AND status IN ('failed', 'error')",
                                 f"#{stretch[0]}-")
            if failures >= writer.GIVE_UP_AFTER:
                writer.bare_episode(mem, *stretch, f"gave up after {failures} unusable answers; saved the episode without knowledge")
                continue
            result = run(mem, writer.Write(mem, *stretch))
            results.append(result)
            if result["status"] in ("failed", "error"):
                break
            if connect and result.get("new_chains"):
                results += connect_new(mem, result["new_chains"])
    return results


def connect_new(mem, chains):
    results, pairs = [], reflect.candidates(mem, chains)
    while pairs and not mem.closed:
        batch, pairs = pairs[:reflect.PAIRS_PER_RUN], pairs[reflect.PAIRS_PER_RUN:]
        results.append(run(mem, reflect.Connect(mem, batch)))
        if results[-1]["status"] in ("failed", "error"):
            break
    return results


def calls_today(mem):
    today = stamp()[:10]
    return mem.value("SELECT COALESCE(SUM(attempts), 0) FROM runs WHERE job IN ('connect', 'think', 'check') AND at >= ?", today) or 0


def reflect_now(mem, thinks=THINKS_PER_SITTING, budget=None, rng=None):
    """One quiet spell of reflection: check what's stale, think, connect what thinking made, measure.
    Returns the runs (and the health numbers as the last item's 'health')."""
    results = []
    budget = REFLECT_CALLS if budget is None else budget
    with RUN_LOCK:
        if mem.closed:
            return results
        items = reflect.check_items(mem)
        if items and calls_today(mem) < budget:
            results.append(run(mem, reflect.Check(mem, items)))
        for _ in range(thinks):
            if calls_today(mem) >= budget:
                break
            focus = reflect.think_focus(mem, rng)
            if not focus:
                break
            result = run(mem, reflect.Think(mem, *focus))
            results.append(result)
            if result["status"] in ("failed", "error"):
                break
            if result.get("new_chains"):
                results += connect_new(mem, result["new_chains"])
        if results:
            metrics = record_health(mem, results[-1]["id"])
            results[-1]["health"] = metrics
        mem.set_mark("reflected_at", stamp())
    return results


def quiet_minutes(mem):
    last = mem.row("SELECT at FROM messages ORDER BY id DESC LIMIT 1")
    return minutes_between(last["at"], stamp()) if last else 0


def due_for_reflection(mem):
    """Quiet long enough, something new since the last reflection, and budget left today."""
    if quiet_minutes(mem) < REFLECT_IDLE or calls_today(mem) >= REFLECT_CALLS:
        return False
    since = mem.mark("reflected_at", "")
    newer = mem.value("SELECT COUNT(*) FROM runs WHERE job = 'write' AND at > ?", since)
    return bool(newer) or bool(reflect.check_items(mem, 1))


def nudge():
    WAKE.set()


def loop():
    while True:
        WAKE.wait(timeout=60)
        WAKE.clear()
        for mem in app["memories"]():
            try:
                write_due(mem)
                if mem is app["main"]() and due_for_reflection(mem):
                    reflect_now(mem)
            except Exception as e:      # never let a bug here take the memory down with it
                print(f"Memory ({mem.name}): the background mind hit a problem ({e}); it will try again.")


def start(ask, prices, memories, main, page):
    """ask: sends one request to DeepSeek. memories: the memories to keep written. main: the main one.
    page: how many messages make an episode right now."""
    from . import llm
    llm.app.update(ask=ask, prices=prices)
    app.update(memories=memories, main=main, page=page)
    threading.Thread(target=loop, daemon=True).start()
    nudge()
