"""Talk to Avy from the command line: her real turn (the same code the page uses), against a memory of your choice.
For trying her out and for testing her persona over long, multi-day conversations without the page.

    python3 tools/talk.py --memory /tmp/try.db "what's on my plate this week?"
    python3 tools/talk.py --memory /tmp/try.db --at "2026-10-20 09:15" "morning"     set the clock first
    python3 tools/talk.py --memory /tmp/try.db --after 3h "back"                      move the clock on
    python3 tools/talk.py --memory /tmp/try.db --script day1.txt                      a whole conversation
    python3 tools/talk.py --memory /tmp/try.db --show persona|desk|calendar|threads   look at the desk
    python3 tools/talk.py --memory /tmp/try.db --reflect                              her reflection on her manner, now

A script is lines like:
    @ 2026-10-20 09:15        the clock (or @ +40m, @ +2d)
    > the message             his message; she answers
    ! reflect                 her reflection on her manner      ! write    write the log into knowledge now
    ! show persona            print the desk (persona, desk, calendar, threads)

The clock is kept in the memory (a mark), so separate runs carry on from where the last one left it. After every
reply, the keeper runs (and waits, here, so what it learned is there for the next message), and the mind writes
what's due, as the app would. Never point it at data/memory-v2.db: use a memory of its own.
"""

import argparse
import os
import re
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def load_env():
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


def delta(text):
    m = re.fullmatch(r"\+?(\d+(?:\.\d+)?)\s*([smhd])", text.strip())
    if not m:
        raise SystemExit(f"Can't read {text!r} as a time step (like +40m, +3h, +2d).")
    n, unit = float(m.group(1)), m.group(2)
    return timedelta(**{{"s": "seconds", "m": "minutes", "h": "hours", "d": "days"}[unit]: n})


class Talk:
    def __init__(self, args):
        load_env()
        if Path(args.memory).resolve() == (ROOT / "data" / "memory-v2.db").resolve() and not args.yes_my_memory:
            raise SystemExit("That's your real memory. Use a memory of its own (or --yes-my-memory if you mean it).")
        global app, memory, worker, persona_jobs, llm
        import app as _app
        import memory as _memory
        from mind import llm as _llm, persona as _persona, worker as _worker
        app, memory, worker, persona_jobs, llm = _app, _memory, _worker, _persona, _llm
        if not args.no_meaning:
            memory.embedder.start(ROOT / "data" / "models" / "meaning")
            memory.embedder.wait(300)
        self.mem = app.MEMORIES["main"] = memory.Memory(args.memory)
        llm.app.update(ask=app.ask_json, prices=app.PRICES, effort=lambda: args.mind)
        worker.app.update(page=app.page_size, main=lambda: self.mem, memories=lambda: [self.mem], desk=lambda: True)
        self.settings = {name: spec["default"] for name, spec in app.SETTINGS.items()}
        for pair in args.set or []:
            k, v = pair.split("=", 1)
            self.settings[k] = v
        app.current_settings = lambda: self.settings
        app.keep_after = lambda mem, last: None            # the keeper runs here, in line, after each reply (below)
        saved = self.mem.mark("talk_clock")
        memory.clock.fixed = datetime.fromisoformat(saved) if saved else datetime.now().astimezone().replace(microsecond=0)
        self.quiet, self.cost = args.quiet, 0.0

    def set_clock(self, when):
        when = when.strip()
        if when.startswith("+"):
            t = memory.clock.fixed + delta(when)
        else:
            t = datetime.fromisoformat(when.replace(" ", "T")).astimezone()
        memory.clock.fixed = t
        self.mem.set_mark("talk_clock", t.isoformat())

    def tick(self, seconds):
        memory.clock.fixed = memory.clock.fixed + timedelta(seconds=seconds)
        self.mem.set_mark("talk_clock", memory.clock.fixed.isoformat())

    def say(self, text):
        print(f"\n[{memory.clock.fixed:%a %b %d %H:%M}] Shreyas: {text}", flush=True)
        started = time.time()
        turn = app.Turn(text, "text")
        reply, usage = "", None
        with turn.ask() as upstream:
            for line in upstream:
                if (line.strip() if isinstance(line, bytes) else line.encode().strip()) == b"data: [DONE]":
                    break
                words, counts = turn.stream(line)
                reply += words
                usage = counts or usage
        self.tick(20 + len(reply) // 40)
        rid = turn.finish(reply, usage)
        self.cost += llm.cost(usage or {}) + ((turn.recall.get("explore") or {}).get("cost") or 0)
        desk = turn.recall.get("desk") or {}
        print(f"Avy: {reply.strip()}", flush=True)
        if not self.quiet:
            bits = [f"{time.time() - started:.1f}s"]
            if desk.get("situation"):
                bits.append(f"situation: {desk['situation']}")
            if desk.get("persona"):
                bits.append("persona: " + " ".join(desk["persona"]))
            if desk.get("terms"):
                bits.append("terms: " + " ".join(desk["terms"]))
            if desk.get("thread"):
                bits.append(f"thread: th{desk['thread']}")
            if turn.did:
                bits.append("did: " + " | ".join(turn.did))
            print("   ↳ " + " · ".join(bits), flush=True)
        if rid:
            result = worker.run(self.mem, persona_jobs.Keep(self.mem, rid))
            self.cost += result.get("cost") or 0
            if result.get("changed") and not self.quiet:
                print("   ↳ keeper: " + ", ".join(self.describe(t) for t in result["changed"]), flush=True)
            elif result.get("status") in ("failed", "error") and not self.quiet:
                print(f"   ↳ keeper {result['status']}: {result.get('problem')}", flush=True)
        for r in worker.write_due(self.mem):
            self.cost += r.get("cost") or 0
        self.tick(40)
        return reply

    def describe(self, target):
        if target.startswith("pa"):
            n = self.mem.persona_node(int(target[2:]))
            return f"{target} {n['aspect']} \"{n['title']}\" v{n['version']}" + (" (retired)" if n["state"] == "retired" else "")
        if target.startswith("th"):
            return f"{target} {self.mem.thread(int(target[2:]))['title']}"
        if target.startswith("t"):
            return f"{target} {self.mem.timeline_item(int(target[1:]))['title']}"
        return target

    def reflect(self):
        runs = worker.reflect_on_manner(self.mem, force=True)
        for r in runs:
            self.cost += r.get("cost") or 0
            print(f"   ↳ reflect {r['status']}: critique {r.get('critique')} changed "
                  + ", ".join(self.describe(t) for t in r.get("changed") or []) + (f" problem: {r.get('problem')}" if r.get("problem") else "")
                  + (f" refused: {r.get('rejections')}" if r.get("rejections") else ""), flush=True)

    def show(self, what):
        if what == "persona":
            print(self.mem.persona_listing(quotes=False))
        elif what == "always":
            print(self.mem.persona_always())
        elif what == "calendar":
            print(self.mem.calendar_text())
        elif what == "threads":
            for th in self.mem.thread_heads():
                print(self.mem.thread_frontier(th))
        else:
            print(self.mem.desk_note("")[0])

    def script(self, path):
        for raw in Path(path).read_text().splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("@"):
                self.set_clock(line[1:])
            elif line.startswith(">"):
                self.say(line[1:].strip())
            elif line.startswith("!"):
                cmd = line[1:].split()
                if cmd[0] == "reflect":
                    self.reflect()
                elif cmd[0] == "write":
                    worker.write_due(self.mem, force=True)
                elif cmd[0] == "show":
                    self.show(cmd[1] if len(cmd) > 1 else "desk")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("message", nargs="*")
    p.add_argument("--memory", required=True)
    p.add_argument("--at", help="set the clock first: 2026-10-20 09:15")
    p.add_argument("--after", help="move the clock on first: 40m, 3h, 2d")
    p.add_argument("--script")
    p.add_argument("--show")
    p.add_argument("--reflect", action="store_true")
    p.add_argument("--set", action="append", help="a setting for this run: thinking=low, window=0, desk=off")
    p.add_argument("--mind", default="none")
    p.add_argument("--quiet", action="store_true")
    p.add_argument("--no-meaning", action="store_true", help="don't load the meaning model (faster start; word search only)")
    p.add_argument("--yes-my-memory", action="store_true")
    args = p.parse_args()
    talk = Talk(args)
    if args.at:
        talk.set_clock(args.at)
    if args.after:
        talk.set_clock("+" + args.after.lstrip("+"))
    if args.script:
        talk.script(args.script)
    if args.message:
        talk.say(" ".join(args.message))
    if args.reflect:
        talk.reflect()
    if args.show:
        talk.show(args.show)
    print(f"\n(cost estimate this run: ${talk.cost:.4f})")


if __name__ == "__main__":
    main()
