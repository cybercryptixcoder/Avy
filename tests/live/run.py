"""
Live tests: scenarios (scenarios.py) played through the real Avy and the real model (through Luminal), the way
Shreyas uses her (window 20, Avy searching her memory herself, the mind writing as sittings end and reflecting
at night), then questions that need memory, answered several ways and graded by a separate judge.

    python3 tests/live/run.py life                 one scenario (life, work, persona, ideas)
    python3 tests/live/run.py --all                every scenario, each in its own process, side by side
    python3 tests/live/run.py work --until 4       only the first days (a quick try)

Each scenario gets a fresh, throwaway memory in tests/live/results/<stamp>_<name>.memory (never yours).
Writes <stamp>_<name>.json (everything: answers, what memory brought, grades, costs, the mind's runs) and .md.

Setups a probe can be answered under (SETUPS): app (window 20, Avy searches, thinking none: what he gets),
app-high (the same with thinking high), memory (window 0, Avy searches: memory alone), rules (window 0,
recall by rules), window4 (window 4, Avy searches: the short-term gap). Nothing a probe does is saved.
"""

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))

import scenarios  # noqa: E402

SETUPS = {
    "app":      {"window": 20, "explore": True,  "thinking": "none", "recent": True},
    "app-high": {"window": 20, "explore": True,  "thinking": "high", "recent": True},
    "memory":   {"window": 0,  "explore": True,  "thinking": "none", "recent": False},
    "rules":    {"window": 0,  "explore": False, "thinking": "none", "recent": False},
    "window4":  {"window": 4,  "explore": True,  "thinking": "none", "recent": True},
}
DEFAULT_SETUPS = ["app", "memory", "rules"]
JUDGE_EFFORT = "high"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("scenario", nargs="?", default="")
    parser.add_argument("--all", action="store_true", help="every scenario, side by side in separate processes")
    parser.add_argument("--key", default=str(ROOT / ".env"))
    parser.add_argument("--models", default=str(ROOT / "data" / "models" / "meaning"))
    parser.add_argument("--out", default=str(HERE / "results"))
    parser.add_argument("--mind", default="none", help="how hard the mind thinks (/mind:)")
    parser.add_argument("--until", type=int, default=999, help="only play up to this day")
    parser.add_argument("--stamp", default="")
    parser.add_argument("--no-explore-play", action="store_true", help="answer the played conversation by rules (faster)")
    parser.add_argument("--probe-anyway", action="store_true", help="with --until: still ask the probes at the end (a smoke test)")
    args = parser.parse_args()
    stamp = args.stamp or datetime.now().strftime("%Y-%m-%d_%H-%M")
    if args.all:
        procs = []
        for name in scenarios.SCENARIOS:
            cmd = [sys.executable, "-u", __file__, name, "--stamp", stamp, "--mind", args.mind, "--until", str(args.until),
                   "--key", args.key, "--models", args.models, "--out", args.out] + (["--no-explore-play"] if args.no_explore_play else [])
            Path(args.out).mkdir(parents=True, exist_ok=True)
            procs.append((name, subprocess.Popen(cmd, stdout=open(Path(args.out) / f"{stamp}_{name}.log", "w"), stderr=subprocess.STDOUT)))
            time.sleep(2)
        for name, p in procs:
            print(f"{name}: exit {p.wait()}", flush=True)
        return
    if args.scenario not in scenarios.SCENARIOS:
        parser.error(f"which scenario? one of {', '.join(scenarios.SCENARIOS)}, or --all")
    Live(args, stamp).run()


class Live:
    def __init__(self, args, stamp):
        self.args, self.name = args, args.scenario
        self.sc = scenarios.SCENARIOS[self.name]
        load_keys(args.key)
        global app, memory, files, explore, llm, worker, luminal
        import app as _app
        import files as _files
        import luminal as _luminal
        import memory as _memory
        from mind import explore as _explore, llm as _llm, worker as _worker
        app, files, luminal, memory, explore, llm, worker = _app, _files, _luminal, _memory, _explore, _llm, _worker
        self.out = Path(args.out)
        self.out.mkdir(parents=True, exist_ok=True)
        self.stamp = f"{stamp}_{self.name}"
        self.work = self.out / f"{self.stamp}.memory"
        self.work.mkdir(exist_ok=True)
        memory.embedder.start(Path(args.models))
        memory.embedder.wait(300)
        self.mem = app.MEMORIES["main"] = memory.Memory(self.work / "memory-v2.db")
        app.FILES_DIR = self.work / "files"
        llm.app.update(ask=app.ask_json, prices=app.PRICES, effort=lambda: args.mind)
        worker.app.update(page=app.page_size, main=lambda: self.mem, memories=lambda: [self.mem])
        defaults = {name: spec["default"] for name, spec in app.SETTINGS.items()}
        self.settings = dict(defaults, footnotes="on", mind=args.mind,
                             explore="off" if args.no_explore_play else "on")
        app.current_settings = lambda: self.settings
        self.tags, self.cost, self.started = {}, {"replies": 0.0, "sim": 0.0, "probes": 0.0, "judge": 0.0}, time.time()
        self.logf = open(self.out / f"{self.stamp}.trace.log", "w")
        self.day1 = datetime.fromisoformat(self.sc["start"] + "T00:00").astimezone()
        self.say(f"live {self.stamp}: memory in {self.work}, meaning search {memory.embedder.status}")

    # --- small things ---------------------------------------------------------------------------
    def say(self, *parts):
        text = " ".join(str(p) for p in parts)
        print(text, flush=True)
        self.logf.write(text + "\n")
        self.logf.flush()

    def moment(self, day, hhmm):
        h, m = (int(x) for x in hhmm.split(":"))
        return self.day1 + timedelta(days=day - 1, hours=h, minutes=m)

    def clock(self, t):
        memory.clock.fixed = t

    def write_due(self):
        """What the app's background mind does when nudged or when it's quiet: write whatever's due."""
        for r in worker.write_due(self.mem):
            self.say(f"     {r['job']:<8} {r['status']:<9} {(r.get('headline') or r.get('focus') or '')[:70]}"
                     f"  +{r.get('applied', 0)}" + (f" ({r['rejected']} refused)" if r.get("rejected") else ""))

    # --- playing the conversation ---------------------------------------------------------------
    def turn(self, text, thread, day, attached=()):
        turn = app.Turn(text, "text", attached=attached)
        reply, usage = "", None
        with turn.ask() as upstream:
            for raw in upstream:
                words, counts = turn.stream(raw)
                reply += words
                usage = counts or usage
        self.tags[turn.user_id] = (thread, day)
        self.clock(memory.now() + timedelta(seconds=25))
        rid = turn.finish(reply, usage)
        self.tags[rid] = (thread, day)
        self.cost["replies"] += llm.cost(usage or {}) + ((turn.recall.get("explore") or {}).get("cost") or 0)
        self.clock(memory.now() + timedelta(seconds=70))
        self.write_due()                       # the app nudges the mind after every reply
        return reply

    def attach(self, name):
        import io
        data = self.sc["files"][name].encode()
        record = files.save(io.BytesIO(data), len(data), name, "text/markdown", app.FILES_DIR)
        return files.wait(record["id"], [app.FILES_DIR], 60)

    def play(self, s):
        self.clock(self.moment(s["day"], s["at"]))
        self.write_due()                       # a quiet spell before this: the mind catches up
        if s.get("sim"):
            return self.simulate(s)
        for line in s["lines"]:
            speaker, text = line[0], line[1]
            extra = line[2] if len(line) > 2 else {}
            attached = [self.attach(n) for n in extra.get("files", [])]
            self.turn(text, s["thread"], s["day"], attached)

    def simulate(self, s):
        """A simulated Shreyas chats about something for a few turns (filler, like real life)."""
        history = []
        for i in range(s.get("turns", 2)):
            system = (scenarios.PERSONA + f"\n\nRight now you're chatting about: {s['sim']}. "
                      + ("Start the conversation with one message." if not history else "Write your next message: react to what Avy said, or add something about the topic.")
                      + f"\nNever bring up any of these: {self.sc['avoid']}. Don't invent new people, dates or plans beyond the topic."
                      " One or two short sentences. Write only the message itself.")
            convo = [{"role": "system", "content": system}]
            convo += [{"role": "assistant" if who == "user" else "user", "content": t} for who, t in history]
            if not history:
                convo.append({"role": "user", "content": "(you start)"})
            r = luminal.complete({"messages": convo, "max_tokens": 200, "temperature": 1.0})
            self.cost["sim"] += llm.cost(r.get("usage") or {})
            text = (r["choices"][0]["message"].get("content") or "").strip().strip('"') or "ok"
            reply = self.turn(text, "filler", s["day"])
            history += [("user", text), ("assistant", reply)]

    def reflect(self, day):
        self.clock(self.moment(day + 1, "03:00"))
        self.write_due()
        for r in worker.reflect_now(self.mem, thinks=3, budget=10 ** 6):
            self.say(f"     {r['job']:<8} {r['status']:<9} {(r.get('focus') or '')[:70]}  +{r.get('applied', 0)}"
                     + (f" ({r['rejected']} refused)" if r.get("rejected") else ""))

    # --- probes ----------------------------------------------------------------------------------
    def node_tags(self, chain, depth=0, parts=False):
        n = self.mem.head(chain)
        if not n:
            return set()
        found = {self.tags[e["message"]] for e in self.mem.evidence_of(n["id"]) if e["message"] in self.tags}
        if n["origin"] == "inferred" and depth < 3:
            for b in self.mem.basis_of(n["id"]):
                found |= self.node_tags(b["chain"], depth + 1)
        if parts and n["shape"] == "thing" and depth == 0:
            for p in self.mem.parts(chain)[:memory.recall.PARTS_SHOWN]:
                found |= self.node_tags(p["chain"], depth + 1)
        return found

    def coverage(self, probe, trace):
        items = [self.node_tags(x["node"], parts=True) for x in trace["nodes"] if x.get("memory", self.mem.name) == self.mem.name]
        items += [{self.tags[l["message"]]} if l["message"] in self.tags else set() for l in trace["log"]]
        found = set().union(*items) if items else set()
        covered = [n for n in probe["needs"] if any(t == n.split("@")[0] and str(d) == n.split("@")[1] for t, d in found)]
        threads = {n.split("@")[0] for n in probe["needs"]}
        noise = sum(1 for tg in items if not any(t in threads for t, _ in tg))
        return {"items": len(items), "covered": covered, "coverage": round(len(covered) / len(probe["needs"]), 2) if probe["needs"] else None,
                "noise": noise}

    def answer(self, probe, setup):
        cfg = SETUPS[setup]
        started = time.time()
        shown = self.mem.window(cfg["window"])
        shown_from = shown[0]["id"] if shown else None
        recent = ("\n".join(f"{memory.who(m['role'], m.get('via'))}: {memory.clip(m['text'], 0, 500)}" for m in self.mem.window(2)[-2:])
                  if cfg["recent"] else "")
        if cfg["explore"]:
            trace = explore.explore(explore.Library([self.mem]), self.mem, probe["ask"], recent, shown_from, "normal",
                                    True, True, learn=False, effort=cfg["thinking"])
        else:
            trace = self.mem.recall(probe["ask"], self.mem.last_said(), shown_from, "normal", True, True)
        self.settings["footnotes"] = "off"
        messages = app.briefing(shown, trace["briefing"], probe["ask"], core=True)
        self.settings["footnotes"] = "on"
        reply = luminal.complete({"messages": messages, "max_tokens": app.REPLY_TOKENS}, effort=cfg["thinking"])
        msg = reply["choices"][0]["message"]
        explored = trace.get("explore") or {}
        cost = llm.cost(reply.get("usage") or {}) + (explored.get("cost") or 0)
        self.cost["probes"] += cost
        return {"setup": setup, "answer": msg.get("content") or "", "thinking": (msg.get("reasoning_content") or "")[:4000],
                "seconds": round(time.time() - started, 1), "cost": round(cost, 5), "retrieval": self.coverage(probe, trace),
                "kept": [f"{x['handle']} {x['title']}" for x in trace["nodes"]] + [f"#{l['message']}" for l in trace["log"]],
                "task": explored.get("task"), "rounds": len(explored.get("rounds", [])), "briefing": trace["briefing"],
                "in_window": [m["id"] for m in shown]}

    def truth(self, before):
        lines = []
        for m in self.mem.messages_between(1, self.mem.last_id()):
            if datetime.fromisoformat(m["at"]) >= before:
                break
            files_ = [f.get("name") for f in m["meta"].get("files") or [] if isinstance(f, dict)]
            lines.append(f"[{datetime.fromisoformat(m['at']):%b %d, %I:%M %p}] {memory.who(m['role'], m.get('via'))}: {m['text']}"
                         + "".join(f"\n  (he attached {n}; its contents:\n{self.sc['files'][n]}\n  )" for n in files_ if n in self.sc.get("files", {})))
        return "\n".join(lines) or "(nothing yet)"

    def grade(self, probe, answer, passes=2):
        tool = llm.tool("grade", "Grade the answer.", {
            "points": {"type": "array", "items": llm.obj({"point": {"type": "integer"},
                                                          "verdict": {"type": "string", "enum": ["met", "partly", "missed"]},
                                                          "why": {"type": "string"}})},
            "invented": {"type": "boolean", "description": "Does the answer state as fact something about Shreyas's life that the conversations don't support?"},
            "invented_what": {"type": "string"}})
        asked = self.moment(probe["day"], probe["at"])
        convo = [{"role": "system", "content": "You grade answers from Avy, a personal assistant with a memory of her past conversations "
                  "with Shreyas. Be strict but fair: a point is met only if the answer actually makes it (in any words), partly if it "
                  "gestures at it, missed otherwise. Points about style (length, lists, how she addresses him) are judged on the answer's "
                  "form. Then say whether the answer states as fact anything about Shreyas's life that nothing in the conversations "
                  "supports (things he or Avy said anywhere count as supported; presenting a guess as fact doesn't). Answer by calling grade."},
                 {"role": "user", "content": f"Everything said before this question, in order:\n{self.truth(asked)}\n\n"
                  f"The question, asked {asked:%A %b %d %Y, %I:%M %p}: {probe['ask']}\n\nAvy's answer:\n{answer}\n\n"
                  "Points a good answer makes:\n" + "\n".join(f"{i}. {p}" for i, p in enumerate(probe["points"], 1))}]
        results = []
        for _ in range(passes):
            for attempt in range(3):
                try:
                    reply = llm.call(convo, tool, max_tokens=3000, effort=JUDGE_EFFORT)
                    self.cost["judge"] += llm.cost(reply.get("usage") or {})
                    g, problem = llm.read_call(reply, "grade")
                    if g and isinstance(g.get("points"), list):
                        verdicts = {int(p.get("point", 0)): p for p in g["points"] if isinstance(p, dict)}
                        marks = [verdicts.get(i, {"verdict": "missed", "why": "not graded"}) for i in range(1, len(probe["points"]) + 1)]
                        results.append({"score": sum({"met": 1, "partly": 0.5}.get(m.get("verdict"), 0) for m in marks) / len(marks),
                                        "marks": [{"verdict": m.get("verdict"), "why": m.get("why", "")} for m in marks],
                                        "invented": bool(g.get("invented")), "invented_what": g.get("invented_what") or ""})
                        break
                except Exception as e:
                    self.say(f"     (judge retry: {e})")
                    time.sleep(3)
        if not results:
            return {"score": None, "marks": [], "invented": None}
        marks = []
        for i in range(len(probe["points"])):
            vs = [r["marks"][i]["verdict"] for r in results]
            v = sum({"met": 1, "partly": 0.5}.get(x, 0) for x in vs) / len(vs)
            marks.append({"point": probe["points"][i], "verdict": "met" if v >= 0.75 else "partly" if v >= 0.25 else "missed",
                          "why": " / ".join(dict.fromkeys(r["marks"][i]["why"] for r in results))})
        invented = all(r["invented"] for r in results)
        return {"score": round(sum(r["score"] for r in results) / len(results), 2), "marks": marks, "invented": invented,
                "invented_what": " / ".join(r["invented_what"] for r in results) if invented else ""}

    def probe(self, p):
        self.clock(self.moment(p["day"], p["at"]))
        self.write_due()
        self.say(f"day {p['day']:>2} {p['at']}  PROBE {p['id']}: {p['ask'][:90]}")
        record = {k: p.get(k) for k in ("id", "day", "at", "ask", "points", "needs")}
        record["answers"] = []
        for setup in p.get("setups") or DEFAULT_SETUPS:
            try:
                a = self.answer(p, setup)
            except Exception as e:
                a = {"setup": setup, "answer": f"(failed: {e})", "retrieval": {}, "kept": []}
            a["grade"] = self.grade(p, a["answer"])
            r = a.get("retrieval") or {}
            self.say(f"     {setup:<9} score {a['grade']['score']}  covered {r.get('covered')} of {p['needs']}  items {r.get('items')}"
                     f"  {a.get('seconds')}s" + ("  INVENTED" if a["grade"].get("invented") else ""))
            for m in a["grade"].get("marks", []):
                if m["verdict"] != "met":
                    self.say(f"         {m['verdict']:<7} {m['point'][:90]}")
            record["answers"].append(a)
        return record

    # --- the run ---------------------------------------------------------------------------------
    def run(self):
        sc = self.sc
        events = [(self.moment(s["day"], s["at"]), 2, "session", s) for s in sc["sessions"] if s["day"] <= self.args.until]
        events += [(self.moment(p["day"], p["at"]), 1, "probe", p) for p in sc["probes"] if p["day"] <= self.args.until]
        if self.args.probe_anyway and self.args.until < 999:          # a smoke test: the first probe, right after what was played
            last = self.moment(self.args.until + 1, "12:00")
            events += [(last, 1, "probe", {**sc["probes"][0], "setups": ["app", "rules"]})]
        days = sorted({s["day"] for s in sc["sessions"] if s["day"] <= self.args.until})
        events += [(self.moment(d + 1, "03:00"), 0, "night", d) for d in days]
        events.sort(key=lambda e: (e[0], e[1]))
        results = {"stamp": self.stamp, "scenario": self.name, "about": sc["about"], "mind": self.args.mind,
                   "explore_play": not self.args.no_explore_play, "probes": [], "health": []}
        path = self.out / f"{self.stamp}.json"
        for when_, _, kind, what in events:
            if kind == "session":
                first = what.get("sim") or what["lines"][0][1]
                self.say(f"day {what['day']:>2} {what['at']}  {what['thread']:<8} {first[:80]}")
                self.play(what)
            elif kind == "night":
                self.say(f"day {what:>2} night: reflecting")
                self.reflect(what)
            else:
                results["probes"].append(self.probe(what))
                path.write_text(json.dumps(results, indent=1, default=str))
        memory.clock.fixed = None
        results["seconds"] = round(time.time() - self.started)
        results["cost"] = {k: round(v, 4) for k, v in self.cost.items()}
        results["cost"]["mind"] = round(self.mem.value("SELECT COALESCE(SUM(cost), 0) FROM runs") or 0, 4)
        results["final"] = {"stats": self.mem.stats(), "health": memory.health(self.mem)}
        results["runs"] = self.mem.rows("SELECT job, COUNT(*) AS n, ROUND(SUM(cost), 4) AS cost, "
                                        "SUM(CASE WHEN status IN ('failed','error') THEN 1 ELSE 0 END) AS failed, "
                                        "SUM(CASE WHEN status = 'repaired' THEN 1 ELSE 0 END) AS repaired FROM runs GROUP BY job")
        results["refused"] = self.mem.rows("SELECT op, why, COUNT(*) AS n FROM journal WHERE result = 'rejected' "
                                           "GROUP BY op, why ORDER BY n DESC LIMIT 25")
        results["nodes"] = [f"{self.mem.handle(n['chain'])} [{n['shape']}/{self.mem.standing(n)}] {n['title']}: {n['text']}"
                            for n in self.mem.current_nodes()]
        results["tags"] = {str(k): v for k, v in self.tags.items()}
        path.write_text(json.dumps(results, indent=1, default=str))
        (self.out / f"{self.stamp}.md").write_text(report(results))
        self.say(f"\ndone in {results['seconds'] // 60} min, ${sum(results['cost'].values()):.2f}. report: {self.out / (self.stamp + '.md')}")


def report(r):
    out = [f"# Live test: {r['scenario']} ({r['stamp']})", "", r["about"], "",
           f"{r['seconds'] // 60} min · cost (estimate) " + ", ".join(f"{k} ${v:.3f}" for k, v in r["cost"].items()), ""]
    setups = []
    for p in r["probes"]:
        for a in p["answers"]:
            if a["setup"] not in setups:
                setups.append(a["setup"])
    out += ["| probe | " + " | ".join(setups) + " |", "|---|" + "---|" * len(setups)]
    for p in r["probes"]:
        cells = []
        for s in setups:
            a = next((a for a in p["answers"] if a["setup"] == s), None)
            g = (a or {}).get("grade") or {}
            cells.append("" if a is None else f"{g.get('score')}" + (" ⚠" if g.get("invented") else ""))
        out.append(f"| {p['id']} | " + " | ".join(cells) + " |")
    out.append("")
    for p in r["probes"]:
        out += [f"## {p['id']}: {p['ask']}", ""]
        for a in p["answers"]:
            g, ret = a.get("grade") or {}, a.get("retrieval") or {}
            out += [f"**{a['setup']}**: score {g.get('score')} · covered {ret.get('covered')} of {p['needs']} · "
                    f"{ret.get('items')} items · task: {a.get('task') or '-'}", "",
                    "> " + (a.get("answer") or "").replace("\n", "\n> "), ""]
            for m in g.get("marks", []):
                out.append(f"- {m['verdict']}: {m['point']} ({m['why'][:200]})")
            out += ["", f"kept: {', '.join(a.get('kept') or [])}", ""]
    st = r["final"]["stats"]
    out += ["## Memory at the end", "", f"{st['messages']} messages, {st['episodes']} episodes, {st['nodes']} nodes "
            f"({st['inferred']} inferred, {st['ideas']} ideas), {st['connections']} connections", "",
            "| job | runs | failed | repaired | cost |", "|---|---|---|---|---|"]
    out += [f"| {x['job']} | {x['n']} | {x['failed']} | {x['repaired']} | {x['cost']} |" for x in r["runs"]]
    out += ["", "Refused proposals (most common):", ""] + [f"- {x['n']}× {x['op']}: {x['why']}" for x in r["refused"]]
    return "\n".join(out) + "\n"


def load_keys(path):
    for line in Path(path).read_text().splitlines():
        name, _, value = line.partition("=")
        if name.strip() in ("LUMINAL_API_KEY", "LUMINAL_BASE_URL", "HELIX_FLASH_MODEL") and value.strip():
            os.environ[name.strip()] = value.strip()
    if not os.environ.get("LUMINAL_API_KEY"):
        raise SystemExit(f"No LUMINAL_API_KEY in {path}.")


if __name__ == "__main__":
    main()
