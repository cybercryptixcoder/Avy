"""Bring your Claude history into Avy: every conversation from a Claude data export becomes Avy's log,
and Avy's mind turns it into knowledge and a network, the same way it does with her own conversations.

    python3 tools/claude_import.py inspect EXPORT        what's in the export (counts only, no text)
    python3 tools/claude_import.py import EXPORT         copy the conversations into a memory file (no model calls)
    python3 tools/claude_import.py plan                  how big the mind's run will be, and roughly what it costs
    python3 tools/claude_import.py run [--max-dollars 5] the mind's run: write it all into knowledge, reflecting as it goes
    python3 tools/claude_import.py status                how far the run has got

EXPORT is the zip claude.ai emails you, the JSON inside it, or a combined JSON of the export.
The memory file is data/memory-claude.db unless you pass --memory <file>. Open it in Avy with
    python3 app.py --memory data/memory-claude.db

What happens, and what doesn't:
  - import never calls a model. The file is streamed, never loaded whole.
  - Each conversation stays in one piece in the log, in the order they started. Your words are yours,
    Claude's replies are marked as Claude's (never Avy's). Edited or regenerated conversations keep only
    the branch they ended on. Thinking, tool calls, tool results (web pages) and attached file contents
    are left out (attachment names are kept). Projects and Claude's own memories are skipped: memory is
    rebuilt from scratch, from the conversations.
  - Avy's background mind never writes imported conversations by itself. Only `run` does, when you start
    it: it's the big job (thousands of model calls), so it's yours to start, stop and budget.
  - run goes in time order, with the clock set to when each stretch happened, so knowledge is dated
    like the conversation, and it reflects once per day of conversation, as Avy would at night.
    Stop it any time (Ctrl+C); the same command carries on where it stopped.
  - Running import again with a newer export adds only what's new.

Details and costs: docs/IMPORT.md.
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

import claude_export  # noqa: E402

DEFAULT_MEMORY = ROOT / "data" / "memory-claude.db"
MODELS = ROOT / "data" / "models" / "meaning"


def load_env():
    """Settings and keys from Avy's .env (without overriding what's already set)."""
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


def open_memory(path, embed=True):
    import memory
    if embed:
        memory.embedder.start(MODELS)
        if not memory.embedder.wait(600):
            print(f"  (search by meaning is off: {memory.embedder.status}. Vectors are filled in later, when it's on.)")
    return memory.Memory(Path(path))


# --- inspect -------------------------------------------------------------------------------------

def read_all(export, progress=True):
    convs, skipped = [], None
    started = time.time()
    for item in claude_export.read(export):
        if isinstance(item, claude_export.Skipped):
            skipped = item
        else:
            convs.append(item)
            if progress and len(convs) % 100 == 0:
                print(f"  read {len(convs)} conversations ({time.time() - started:.0f}s)", flush=True)
    return convs, skipped


def cmd_inspect(args):
    convs, skipped = read_all(args.export)
    kept = [c for c in convs if c.messages]
    msgs = [m for c in kept for m in c.messages]
    you = [m for m in msgs if m.role == "user"]
    print(f"\n{len(convs)} conversations ({len(kept)} with something said), {len(msgs):,} messages: "
          f"{len(you):,} yours, {len(msgs) - len(you):,} Claude's")
    if kept:
        print(f"from {min(c.started for c in kept)[:10]} to {max(m.at for m in msgs)[:10]}")
    print(f"words: {sum(len(m.text) for m in you) / 1e6:.2f}M characters yours, "
          f"{sum(len(m.text) for m in msgs if m.role != 'user') / 1e6:.2f}M Claude's")
    print(f"left out: {sum(c.off_branch for c in convs):,} messages on branches a conversation didn't end on, "
          f"{sum(c.empty for c in convs):,} empty ones")
    print(f"attachments named (contents left out): {sum(len(m.attachments) + len(m.files) for m in msgs):,}")
    print(f"skipped: {skipped.projects} projects ({skipped.project_docs} documents), {skipped.memories} Claude memory "
          f"files, {skipped.users} account records, {skipped.other} other entries")


# --- import --------------------------------------------------------------------------------------

def import_conversations(mem, convs, say=print, progress=None):
    """Append the conversations to mem's log, oldest conversation first, each in one piece. Messages already
    imported (by their Claude id) are skipped, so a newer export only adds what's new. Returns counts.
    progress(done, of, messages added), if given, hears after every conversation (the page's import)."""
    from memory.common import IMPORTED
    have = {r["u"] for r in mem.rows("SELECT json_extract(meta, '$.claude') AS u FROM messages WHERE via = ?", IMPORTED)}
    convs = sorted((c for c in convs if c.messages), key=lambda c: c.started)
    added_convs = added_msgs = 0
    started = time.time()
    for i, c in enumerate(convs, 1):
        new = [m for m in c.messages if m.uuid not in have]
        if not new:
            continue
        items = []
        with mem.tx() as db:
            for m in new:
                meta = {"conversation": c.uuid, "conversation_name": c.name, "source": c.source, "claude": m.uuid}
                if c.project:
                    meta["project"] = c.project
                if m.attachments:
                    meta["attachments"] = m.attachments
                if m.files:
                    meta["files"] = m.files
                mid = db.execute("INSERT INTO messages (at, role, text, via, meta) VALUES (?, ?, ?, ?, ?)",
                                 (m.at, m.role, m.text, IMPORTED, json.dumps(meta))).lastrowid
                db.execute("INSERT INTO words (text, item) VALUES (?, ?)", (m.text, f"m{mid}"))
                items.append((f"m{mid}", m.text))
        for k in range(0, len(items), 64):                      # search by meaning (local, no model calls)
            mem.remember_meaning(items[k:k + 64])
        added_convs += 1
        added_msgs += len(new)
        if progress:
            progress(i, len(convs), added_msgs)
        if i % 25 == 0 or i == len(convs):
            say(f"  {i}/{len(convs)} conversations, {added_msgs:,} messages added ({time.time() - started:.0f}s)")
    return {"conversations": added_convs, "messages": added_msgs}


def cmd_import(args):
    print(f"Reading {args.export} ...")
    convs, skipped = read_all(args.export)
    mem = open_memory(args.memory)
    from memory.common import IMPORTED
    others = mem.value("SELECT COUNT(*) FROM messages WHERE via != ?", IMPORTED)
    if others:
        print(f"Note: {args.memory} already has {others:,} messages of its own; the imported history goes after them.")
    print(f"Importing into {args.memory} ...")
    done = import_conversations(mem, convs)
    print(f"\nDone: {done['conversations']} conversations, {done['messages']:,} messages added. "
          f"{mem.waiting_import():,} imported messages wait for the mind's run.\nNext: python3 tools/claude_import.py plan"
          + (f" --memory {args.memory}" if Path(args.memory) != DEFAULT_MEMORY else ""))


# --- plan ----------------------------------------------------------------------------------------

def stretches(mem, page):
    """Every stretch the run will write, from where writing stands: [(first, last)]."""
    out, start, last = [], mem.written_up_to() + 1, mem.last_id()
    while start <= last:
        s = mem.stretch_from(start, page, force=True)
        if not s:
            break
        out.append(s)
        start = s[1] + 1
    return out


# Measured on the benchmark (tests/bench): model calls per written stretch and tokens per call.
PER_STRETCH = {"connect_calls": 3.36, "connect_in": 3545, "connect_out": 593, "write_attempts": 1.41, "write_out": 855}
PER_DAY = {"think_calls": 5.9, "think_in": 3874, "think_out": 359, "check_calls": 0.65, "check_in": 4205, "check_out": 1187}
SHOWN_NODES_TOKENS = 3500          # what memory already holds, shown with each stretch once memory has grown
THINKING_OUT = {"none": 0, "low": 400, "high": 1500, "max": 3500}     # DeepSeek's levels (luminal.EFFORTS)
SECONDS_PER_CALL = {"none": 6, "low": 12, "high": 18, "max": 24}


def estimate(mem, effort="none"):
    """Rough size, cost and time of the run from here."""
    import luminal
    from mind import writer
    todo = stretches(mem, writer.PAGE)
    instructions = len(writer.INSTRUCTIONS) // 4
    write_in = 0
    days = set()
    for first, last in todo:
        msgs = mem.messages_between(first, last)
        text = sum(len(writer.as_line(m, 4000 if m["role"] == "user" else 1500)) for m in msgs)
        write_in += instructions + SHOWN_NODES_TOKENS + text // 4 + 400
        days.add(msgs[-1]["at"][:10])
    n, d, think = len(todo), len(days), THINKING_OUT.get(effort, 0)
    tokens_in = (write_in * PER_STRETCH["write_attempts"] + n * PER_STRETCH["connect_calls"] * PER_STRETCH["connect_in"]
                 + d * (PER_DAY["think_calls"] * PER_DAY["think_in"] + PER_DAY["check_calls"] * PER_DAY["check_in"]))
    calls = n * (PER_STRETCH["write_attempts"] + PER_STRETCH["connect_calls"]) + d * (PER_DAY["think_calls"] + PER_DAY["check_calls"])
    tokens_out = (n * (PER_STRETCH["write_attempts"] * PER_STRETCH["write_out"] + PER_STRETCH["connect_calls"] * PER_STRETCH["connect_out"])
                  + d * (PER_DAY["think_calls"] * PER_DAY["think_out"] + PER_DAY["check_calls"] * PER_DAY["check_out"])
                  + calls * think)
    p = luminal.PRICES
    cached = 0.4                     # share of input the prompt cache usually covers (the instructions repeat)
    dollars = (tokens_in * cached * p["cache_hit"] + tokens_in * (1 - cached) * p["cache_miss"] + tokens_out * p["output"]) / 1e6
    hours = calls * SECONDS_PER_CALL.get(effort, 10) / 3600
    return {"stretches": n, "days": d, "calls": round(calls), "tokens_in": round(tokens_in), "tokens_out": round(tokens_out),
            "dollars": dollars, "hours": hours}


def cmd_plan(args):
    mem = open_memory(args.memory, embed=False)
    if not mem.waiting_import():
        print("Nothing imported is waiting to be written. Run import first (or the run has finished).")
        return
    print(f"{mem.waiting_import():,} imported messages wait to be written in {args.memory}.")
    print("\nEstimate per /mind: thinking level (Luminal publishes no per-token price: dollars use DeepSeek's own list\n"
          "price for V4.1-Flash, so treat them as a rough guide and watch the Luminal balance):\n")
    print(f"{'thinking':<9} {'stretches':>9} {'days':>5} {'calls':>7} {'tokens in':>11} {'tokens out':>11} {'dollars':>8} {'hours':>6}")
    for effort in ("none", "low", "high", "max"):
        e = estimate(mem, effort)
        print(f"{effort:<9} {e['stretches']:>9,} {e['days']:>5,} {e['calls']:>7,} {e['tokens_in']:>11,} {e['tokens_out']:>11,} "
              f"{e['dollars']:>8.2f} {e['hours']:>6.1f}")
    print("\nHours assume one call at a time (Luminal is happiest under 8 at once; the run is sequential).\n"
          "Start it with: python3 tools/claude_import.py run --effort none --max-dollars 20")


# --- run -----------------------------------------------------------------------------------------

def cmd_run(args):
    import luminal
    import memory
    from memory.common import IMPORTED
    from mind import llm, worker, writer
    if not luminal.key():
        sys.exit("No Luminal key: add LUMINAL_API_KEY to .env (or once in Avy's Keys panel).")
    ok, message = luminal.check()
    if not ok:
        sys.exit(message)
    print(message)
    mem = open_memory(args.memory)
    llm.app.update(ask=luminal.complete, prices=luminal.PRICES, effort=lambda: args.effort)
    worker.app.update(page=lambda: writer.PAGE, main=lambda: mem, memories=lambda: [mem])
    first_run_id = mem.value("SELECT MAX(id) FROM runs") or 0
    spent = lambda: mem.value("SELECT COALESCE(SUM(cost), 0) FROM runs WHERE id > ?", first_run_id) or 0.0
    total = len(stretches(mem, writer.PAGE))
    print(f"{total:,} stretches to write, thinking: {args.effort}, budget: "
          + (f"${args.max_dollars:.2f}" if args.max_dollars else "none") + ". Ctrl+C stops; run again to carry on.\n")
    started, done, day = time.time(), 0, None
    try:
        while True:
            s = mem.next_stretch(writer.PAGE, force=True)
            if not s or mem.message(s[0])["via"] != IMPORTED:
                break
            if args.max_dollars and spent() >= args.max_dollars:
                print(f"\nBudget reached (${spent():.2f}). Run again with a higher --max-dollars to carry on.")
                break
            if args.max_stretches and done >= args.max_stretches:
                print(f"\nStopped after {done} stretches (--max-stretches).")
                break
            msgs = mem.messages_between(*s)
            when_ = datetime.fromisoformat(msgs[-1]["at"])
            if args.until and when_.date().isoformat() > args.until:
                print(f"\nReached {args.until} (--until).")
                break
            if day and when_.date() != day and not args.no_reflect:      # a new day: reflect on the last one first
                memory.clock.fixed = last_at + timedelta(minutes=31)
                runs = worker.reflect_now(mem)
                if runs:
                    print(f"         {day} night: reflected ({len(runs)} runs)")
            memory.clock.fixed = when_ + timedelta(minutes=1)
            for r in worker.write_due(mem, force=True, limit=1, imported=True):
                if r["job"] == "write":
                    print(f"  [{done + 1:>5}/{total}] {when_:%Y-%m-%d}  #{s[0]}-{s[1]}  {r['status']:<8} "
                          f"{(r.get('headline') or '')[:70]}  +{r.get('applied', 0)}", flush=True)
            done += 1
            day, last_at = when_.date(), when_
            if done % 10 == 0:
                rate = (time.time() - started) / done
                print(f"         ${spent():.2f} spent so far, about {rate * (total - done) / 3600:.1f} h to go", flush=True)
        if day and not args.no_reflect and not mem.waiting_import():
            memory.clock.fixed = last_at + timedelta(minutes=31)
            worker.reflect_now(mem)
    except KeyboardInterrupt:
        print("\nStopped. Run the same command to carry on where it stopped.")
    finally:
        memory.clock.fixed = None
    print(f"\n{done} stretches written this time, ${spent():.2f} spent (an estimate; the Luminal balance is the truth: "
          f"${luminal.balance()}). {mem.waiting_import():,} imported messages still wait.")
    st = mem.stats()
    print(f"Memory now: {st['nodes']:,} nodes, {st['connections']:,} connections, {st['inferred']:,} inferred.")


def cmd_status(args):
    mem = open_memory(args.memory, embed=False)
    from mind import writer
    st = mem.stats()
    cost = mem.value("SELECT COALESCE(SUM(cost), 0) FROM runs") or 0
    print(f"{args.memory}: {st['messages']:,} messages, written up to #{st['written_to']:,}; "
          f"{mem.waiting_import():,} imported messages still wait ({len(stretches(mem, writer.PAGE)):,} stretches).")
    print(f"Knowledge: {st['nodes']:,} nodes ({st['inferred']:,} inferred, {st['ideas']:,} ideas), {st['connections']:,} connections. "
          f"Spent so far: ${cost:.2f} (estimate).")


def main(argv=None):
    load_env()
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("inspect", help="what's in an export (counts only)")
    p.add_argument("export")
    p = sub.add_parser("import", help="copy the conversations into a memory file (no model calls)")
    p.add_argument("export")
    p.add_argument("--memory", default=str(DEFAULT_MEMORY))
    p = sub.add_parser("plan", help="how big and how costly the mind's run will be")
    p.add_argument("--memory", default=str(DEFAULT_MEMORY))
    p = sub.add_parser("run", help="the mind's run: write the imported conversations into knowledge")
    p.add_argument("--memory", default=str(DEFAULT_MEMORY))
    p.add_argument("--effort", default="none", choices=["none", "low", "high", "max"],
                   help="how hard the mind thinks (none is fastest and cheapest; low, high, max are DeepSeek's levels)")
    p.add_argument("--max-dollars", type=float, default=0, help="stop once this much (estimated) is spent")
    p.add_argument("--max-stretches", type=int, default=0, help="stop after this many stretches (a trial run)")
    p.add_argument("--until", default="", help="stop at conversations after this date (YYYY-MM-DD)")
    p.add_argument("--no-reflect", action="store_true", help="only write; reflect later")
    p = sub.add_parser("status", help="how far the run has got")
    p.add_argument("--memory", default=str(DEFAULT_MEMORY))
    args = parser.parse_args(argv)
    {"inspect": cmd_inspect, "import": cmd_import, "plan": cmd_plan, "run": cmd_run, "status": cmd_status}[args.command](args)


if __name__ == "__main__":
    main()
