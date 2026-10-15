"""Dreaming: a long, slow reflection, thinking as hard as the model can (/thinking max), for hours.

Ordinary reflection (worker.py) is short and cheap: when it's quiet it re-checks what went stale, thinks about
the newest conversation, and connects what's new, within a small daily budget. Dreaming is the other end: Avy
goes over *everything* she knows, at full depth, with no question to answer, to reorganize it, the way sleep
consolidates memory. It's started by hand (the looking glass, or /dream), runs for as long as it's given
(8 hours by default) within a money budget, and can be woken any time.

One dream, round after round until time or money runs out:
  1. Re-check: every inference whose ground moved, every connection whose ends changed (Check).
  2. Sweep: the next few nodes in sweep order (the ones dreamt about longest ago first), each looking for
     partners anywhere in memory that it isn't connected to yet: Connect judges the pairs. Over a night the
     sweep goes round the whole memory, so a week-1 memory gets its chance to meet week 10.
  3. Think, alternating three kinds of focus:
       wander   a node from the sweep, its neighborhood, and distant relatives (what's implied but unsaid)
       hub      one of the big things, everything attached to it (patterns, where it really stands)
       bridge   two big things far apart in the network, side by side (a principle they share, a tension)
  4. Every half hour, the network's health is measured, so the looking glass can show how it's changing.
Everything goes through the ordinary jobs and the one door (rules, journal), one job at a time with the rest
of the mind, so a message from Shreyas is written as usual while she dreams. Each dream ends with a record
(a run of job "dream") saying what it did.

What's deliberately not here yet (ARCHITECTURE.md, "Dreaming"): re-reading old conversations to write what
the first pass missed, merging near-duplicate nodes, and dreaming over the thought graph.
"""

import random
import threading
import time
from datetime import datetime

from memory import health as measure_health, record_health
from memory.common import stamp

from . import reflect, worker

SWEEP = 6                 # nodes swept per round
HEALTH_EVERY = 30 * 60    # seconds between health measurements


class Dream:
    def __init__(self, main, tell=lambda event: None):
        """main(): the main memory (dreaming is only for the memory that's kept)."""
        self.main, self.tell = main, tell
        self.stop_flag = threading.Event()
        self.thread = None
        self.state = {"state": "awake", "last": None}

    # --- control ------------------------------------------------------------------------------------
    def start(self, hours=8, max_dollars=10.0, effort="max"):
        if self.thread and self.thread.is_alive():
            return "She's already dreaming."
        mem = self.main()
        if not mem or mem.closed:
            return "There's no memory to dream about."
        if not mem.current_nodes():
            return "Memory is empty: there's nothing to dream about yet."
        self.stop_flag.clear()
        self.state = {"state": "dreaming", "started": stamp(), "hours": float(hours), "budget": float(max_dollars),
                      "effort": effort, "phase": "falling asleep", "elapsed": 0, "spent": 0.0, "runs": 0, "swept": 0,
                      "of": len(mem.current_nodes()), "connected": 0, "inferred": 0, "revised": 0, "failed": 0,
                      "last": self.state.get("last"), "log": []}
        self.thread = threading.Thread(target=self.run, args=(mem,), daemon=True)
        self.thread.start()
        self.announce()
        return None

    def stop(self):
        if not (self.thread and self.thread.is_alive()):
            return "She isn't dreaming."
        self.stop_flag.set()
        self.state["state"] = "waking"
        self.announce()
        return None

    def status(self):
        s = {k: v for k, v in self.state.items() if k != "log"}
        if s.get("started") and s["state"] in ("dreaming", "waking"):
            s["elapsed"] = round((datetime.now().astimezone() - datetime.fromisoformat(s["started"])).total_seconds())
        s["log"] = self.state.get("log", [])[-12:]
        return s

    def announce(self):
        try:
            self.tell({"dream": self.status()})
        except Exception:
            pass

    def note(self, text):
        self.state.setdefault("log", []).append(f"{datetime.now():%H:%M} {text}")
        self.state["log"] = self.state["log"][-60:]

    # --- the dream ----------------------------------------------------------------------------------
    def run(self, mem):
        s = self.state
        started = time.time()
        deadline = started + s["hours"] * 3600
        rng = random.Random()
        last_health, last_check, kinds = started, 0.0, ["wander", "hub", "bridge"]
        turn, seen, lap, empty_laps = 0, set(), {"swept": 0, "found": 0}, 0
        try:
            self.note(f"asleep: up to {s['hours']}h, ${s['budget']:.2f}, thinking {s['effort']}")
            while not self.stop_flag.is_set() and time.time() < deadline and s["spent"] < s["budget"] and not mem.closed:
                if time.time() - last_check > 3600 or turn == 0:          # 1. re-check what went stale
                    s["phase"] = "re-checking what changed"
                    while (items := reflect.check_items(mem)) and not self.stopping(deadline):
                        r = self.job(mem, reflect.Check(mem, items))
                        s["revised"] += r.get("retracted", 0) + r.get("applied", 0)
                        if r["status"] in ("failed", "error"):
                            break
                    last_check = time.time()
                if self.stopping(deadline):
                    break
                chains = self.next_sweep(mem)                              # 2. sweep for distant partners
                s["phase"] = "sweeping: " + ", ".join(f"{mem.handle(c)} {mem.current(c)['title'][:30]}" for c in chains[:3] if mem.current(c))
                pairs = reflect.candidates(mem, chains)
                for i in range(0, len(pairs), reflect.PAIRS_PER_RUN):
                    if self.stopping(deadline):
                        break
                    r = self.job(mem, reflect.Connect(mem, pairs[i:i + reflect.PAIRS_PER_RUN]))
                    s["connected"] += r.get("connected", 0)
                for c in chains:
                    mem.set_mark(f"dream.node.{c}", stamp())
                s["swept"] += len(chains)
                if self.stopping(deadline):
                    break
                focus = None                                               # 3. think (never the same view twice)
                for k in range(3):
                    candidate = self.focus(mem, kinds[(turn + k) % 3], chains, rng)
                    if candidate and frozenset(candidate[1]) not in seen:
                        focus = candidate
                        seen.add(frozenset(candidate[1]))
                        break
                if focus:
                    s["phase"] = f"thinking: {focus[2][:80]}"
                    r = self.job(mem, reflect.Think(mem, *focus))
                    s["inferred"] += r.get("inferred", 0)
                    if r.get("new_chains"):
                        for i, pairs in enumerate([reflect.candidates(mem, r["new_chains"])]):
                            for k in range(0, len(pairs), reflect.PAIRS_PER_RUN):
                                if self.stopping(deadline):
                                    break
                                s["connected"] += self.job(mem, reflect.Connect(mem, pairs[k:k + reflect.PAIRS_PER_RUN])).get("connected", 0)
                turn += 1
                lap["swept"] += len(chains)                                # a whole lap round memory with nothing new: done
                if lap["swept"] >= len(mem.current_nodes()):
                    found = s["connected"] + s["inferred"] + s["revised"]
                    empty_laps = empty_laps + 1 if found == lap["found"] else 0
                    lap = {"swept": 0, "found": found}
                    if empty_laps >= 2:
                        self.note("went round all of memory twice and found nothing new: waking early")
                        break
                if time.time() - last_health > HEALTH_EVERY:               # 4. how the network is changing
                    with worker.RUN_LOCK:
                        record_health(mem, None)
                    last_health = time.time()
                if s["failed"] >= 8 and s["failed"] > s["runs"] // 2:
                    self.note("too many failures in a row: waking up")
                    break
        except Exception as e:
            self.note(f"woke up with a problem: {type(e).__name__}: {e}")
            s["problem"] = str(e)[:300]
        finally:
            self.finish(mem, started)

    def stopping(self, deadline):
        s = self.state
        return self.stop_flag.is_set() or time.time() >= deadline or s["spent"] >= s["budget"]

    def job(self, mem, job):
        """One job, at the dream's thinking level, through the ordinary engine (one at a time with the rest of the mind)."""
        job.effort = self.state["effort"]
        with worker.RUN_LOCK:
            if mem.closed:
                return {"status": "error", "applied": 0}
            r = worker.run(mem, job)
        s = self.state
        s["runs"] += 1
        s["spent"] = round(s["spent"] + (r.get("cost") or 0), 5)
        if r["status"] in ("failed", "error"):
            s["failed"] += 1
            self.note(f"{job.name} {r['status']}: {str(r.get('problem') or '')[:100]}")
        else:
            self.note(f"{job.name} {r['status']}: {job.focus[:60]} (+{r.get('applied', 0)})")
        self.announce()
        return r

    def next_sweep(self, mem):
        """The nodes dreamt about longest ago (never, first), oldest first."""
        nodes = [n for n in mem.current_nodes() if n["origin"] != "inferred"] or mem.current_nodes()
        nodes.sort(key=lambda n: (mem.mark(f"dream.node.{n['chain']}", "") or "", n["chain"]))
        return [n["chain"] for n in nodes[:SWEEP]]

    def focus(self, mem, kind, chains, rng):
        """(kind, view, focus in words, marks) for Think, or None."""
        view_cap = reflect.THINK_VIEW
        hubs = [n for n, _ in mem.hubs(12)]
        if kind == "hub" and hubs:
            hub = rng.choice(hubs[:6])
            view = [hub["chain"]] + [l["other"] for l in mem.links(hub["chain"], limit=view_cap)]
            return "hub", list(dict.fromkeys(view))[:view_cap], f"dreaming about {mem.handle(hub['chain'])} {hub['title']}", {}
        if kind == "bridge" and len(hubs) >= 2:
            a, b = rng.sample(hubs[:8], 2)
            view = [a["chain"]] + [l["other"] for l in mem.links(a["chain"], limit=view_cap // 2 - 1)]
            view += [b["chain"]] + [l["other"] for l in mem.links(b["chain"], limit=view_cap // 2 - 1)]
            return "bridge", list(dict.fromkeys(view))[:view_cap], \
                f"dreaming between {mem.handle(a['chain'])} {a['title']} and {mem.handle(b['chain'])} {b['title']}", {}
        start = mem.current(chains[0]) if chains else None
        if not start:
            return None
        view = [start["chain"]] + [l["other"] for l in mem.links(start["chain"])[:6]]
        hits = mem.land([(mem.node_words(start), 1.0, mem.vector(f"v{start['id']}"))], k=30)
        view += [c for c, h in sorted(hits.items(), key=lambda kv: -kv[1]["score"]) if c not in view][4:14]
        return "wander", view[:view_cap], f"dreaming from {mem.handle(start['chain'])} {start['title']}", {}

    def finish(self, mem, started):
        s = self.state
        seconds = round(time.time() - started)
        summary = (f"{seconds // 3600}h {(seconds % 3600) // 60}m, {s['runs']} runs, swept {s['swept']} nodes, "
                   f"{s['connected']} new connections, {s['inferred']} new thoughts, {s['revised']} revised, ${s['spent']:.2f}")
        try:
            if not mem.closed:
                with worker.RUN_LOCK:
                    metrics = record_health(mem, None)
                mem.save_run(job="dream", status="ok" if not s.get("problem") else "partial", attempts=s["runs"],
                             seconds=seconds, cost=s["spent"], focus=f"dream ({s['effort']}): {summary}",
                             problems=[s.get("log", [])[-40:]])
                s["health_after"] = metrics
        except Exception as e:
            self.note(f"couldn't record the dream ({e})")
        self.note(f"awake: {summary}")
        s.update(state="awake", phase=None, last={"ended": stamp(), "summary": summary})
        self.announce()
