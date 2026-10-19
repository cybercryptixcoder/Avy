"""LoCoMo, run through her. The external benchmark, not the house one.

    python3 tests/locomo/run.py --conv conv-26 --questions 40 --tag first

Why this exists: the in-repo bench (tests/bench) is 10 house-designed probes over a synthetic month. It can tell me
whether a change broke something. It cannot tell me whether she is good, because I wrote both the month and the probes.
LoCoMo (Maharana et al., ACL 2024) was written by other people, about other people, and its published numbers are the
ones the field compares against: human 87.9%, best memory systems 74.0%, full-context (paste everything) 72.9%, best
RAG 61.0%. If she can't beat pasting the conversation in, the graph isn't earning its complexity.

How it works, and why this shape:

1. INGEST through her real path. Each session of the conversation is written into her log as messages (role=user for
   the speaker's turns, labelled), then `worker.write_due(imported=True)` runs her own writer: it reads the stretch,
   proposes nodes citing the exact messages, and connects them. That is the system under test doing the work. Nothing
   here hand-builds her memory.
2. ASK through her real path: `app.Turn(...).ask(); stream(); finish()` — the same code that answers Shreyas.
3. GRADE with LoCoMo's own rule: an LLM judge that sees the question, the gold answer and her answer, and says
   correct/incorrect. The judge never sees her memory or the retrieval, only the answer, so it can't be gamed by a
   compelling-looking context.

What this deliberately does NOT do: the original LoCoMo paper reports F1 and BLEU over short phrases, where "7 May
2023" and "May 7, 2023" score 0 while a human would call both right. The published tables everyone quotes (Mem0's
paper, the HF leaderboards) use LLM-as-judge for exactly this reason, and so does this. It is the same protocol as
the numbers in IMPROVE-NOTES §12, so the comparison is like-for-like.
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(ROOT))

for line in (ROOT / ".env").read_text().splitlines():       # the key and the browser, as app.py reads them
    line = line.strip()
    if line and not line.startswith("#") and "=" in line:
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())

import app          # noqa: E402
import connectors   # noqa: E402
import hands        # noqa: E402
import memory       # noqa: E402
import luminal      # noqa: E402
from mind import worker  # noqa: E402

DATA = HERE / "data" / "locomo10.json"
OUT = HERE / "out"
OUT.mkdir(exist_ok=True)

JUDGE = """You are grading a memory system. You get a question about a long conversation, the gold answer, and the
system's answer. Say whether the system's answer is correct.

Correct means: it agrees with the gold answer on the thing being asked. Extra words are fine. A different phrasing of
the same fact is fine. A more precise answer than the gold one is fine.
Incorrect means: it contradicts the gold answer, gives a different fact, says it doesn't know, or answers a different
question. If the answer is vague enough that a person couldn't tell whether it's right, that's incorrect.

Answer with one word: correct or incorrect, then a full stop and at most fifteen words of reason."""


def judge(question, gold, got):
    """LoCoMo's own metric: an LLM decides. Returns (correct, why).

    One guard learned the expensive way: `luminal.complete` returns the API's response dict, not a string. Calling
    `.strip()` on the dict raised nothing and compared nothing, so every answer graded "incorrect" and the run
    reported 0.0% — a fabricated result I would have blamed on her. Unwrap first, then read the words.
    """
    reply = luminal.complete({"messages": [
        {"role": "system", "content": JUDGE},
        {"role": "user", "content": f"Question: {question}\nGold answer: {gold}\nSystem's answer: {got}"}],
        "max_tokens": 120})
    if isinstance(reply, dict):
        try:
            reply = reply["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            reply = ""
    reply = (reply if isinstance(reply, str) else "").strip()
    ok = reply.lower().startswith("correct")
    return ok, reply[:180]


def sessions_of(conv):
    """[(session number, date string, [turns])] in order, from LoCoMo's flat session_N keys."""
    out, n = [], 1
    while f"session_{n}" in conv:
        out.append((n, conv.get(f"session_{n}_date_time") or "", conv[f"session_{n}"]))
        n += 1
    return out


def ingest(mem, conv, speaker_a, speaker_b, upto=None):
    """Put the conversation into her log, session by session, letting her writer make knowledge after each one.

    Roles: LoCoMo has two speakers talking *to each other*, neither of them Shreyas. Both are written as the user
    side (who actually said it goes in `speaker`), because her memory's job is "what happened in this conversation"
    and marking one of them as her own words would make the writer treat their sentences as things she said.
    """
    done = 0
    for n, date, turns in sessions_of(conv):
        if upto and n > upto:
            break
        at = None
        try:                                   # "1:56 pm on 8 May, 2023" -> a timezone-aware stamp, like her own log's
            at = datetime.strptime(date, "%I:%M %p on %d %B, %Y").replace(tzinfo=TZ).isoformat(timespec="seconds")
        except Exception:
            at = datetime(2023, 5, 1, tzinfo=TZ).isoformat(timespec="seconds")
        for t in turns:
            text = (t.get("text") or "").strip()
            if not text:
                continue
            who = t.get("speaker") or "?"
            mem.add("user", f"[{who}] {text}", via="text", at=at,
                    meta={"locomo": t.get("dia_id"), "session": n, "date": date})
        # her writer, on the stretch that just landed: nodes citing the exact messages, then edges between them
        for _ in range(6):
            runs = worker.write_due(mem, connect=True, limit=3, imported=True)
            if not runs:
                break
        done += 1
        print(f"    session {n} ingested ({len(turns)} turns)", flush=True)
    return done


def ask(question):
    """Her real answer path: a Turn, streamed to the end, the words she says."""
    turn = app.Turn(question, "text")
    reply, usage = "", None
    with turn.ask() as upstream:
        for raw in upstream:
            words, counts = app.stream_text(raw)
            reply += words
            usage = counts or usage
    turn.finish(reply, usage)
    return (reply or "").strip()


CATEGORIES = {1: "multi-hop", 2: "temporal", 3: "open-domain", 4: "single-hop", 5: "adversarial"}
TZ = memory.now().tzinfo            # her log writes "-04:00" stamps; these must match or stretch maths explodes


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--conv", default="conv-26", help="conv-26 … conv-30, conv-41 … conv-50, or 'first'")
    ap.add_argument("--questions", type=int, default=40)
    ap.add_argument("--sessions", type=int, default=0, help="ingest only the first N sessions (0: all)")
    ap.add_argument("--tag", default="run")
    ap.add_argument("--reuse", default="", help="an existing memory folder to ask against (skips ingest)")
    args = ap.parse_args()

    data = json.loads(DATA.read_text())
    pick = next((d for d in data if args.conv == "first" or d["sample_id"] == args.conv), None)
    if pick is None:
        sys.exit(f"no conversation {args.conv}; have {[d['sample_id'] for d in data]}")
    conv = pick["conversation"]
    speaker_a, speaker_b = conv.get("speaker_a"), conv.get("speaker_b")

    started = time.time()
    if args.reuse:
        work = Path(args.reuse).resolve()
    else:
        work = OUT / f"{datetime.now():%Y-%m-%d_%H-%M}_{args.tag}.memory"
    work.mkdir(parents=True, exist_ok=True)

    memory.embedder.start(ROOT / "data" / "models" / "meaning")
    memory.embedder.wait(300)                 # meaning search is dead until the model is loaded
    mem = app.MEMORIES["main"] = memory.Memory(work / "memory-v2.db")
    from mind import llm
    llm.app.update(ask=app.ask_json, prices=app.PRICES, effort=lambda: "none")

    if not args.reuse:
        print(f"ingesting {pick['sample_id']} ({speaker_a} & {speaker_b})", flush=True)
        n = ingest(mem, conv, speaker_a, speaker_b, upto=args.sessions or None)
        print(f"  {n} sessions, {mem.last_id()} messages, {len(mem.current_nodes())} nodes, "
              f"{len(mem.live_edges())} edges", flush=True)

    # Questions: stratified, so every category is represented rather than the single-hop flood (841 of 1,986).
    qas = [q for q in pick["qa"] if q.get("answer") and not str(q.get("answer")).startswith("No answer")]
    by_cat = {}
    for q in qas:
        by_cat.setdefault(q.get("category"), []).append(q)
    chosen, i = [], 0
    while len(chosen) < args.questions and any(len(v) > i for v in by_cat.values()):
        for cat in sorted(by_cat):
            if len(by_cat[cat]) > i:
                chosen.append(by_cat[cat][i])
                if len(chosen) >= args.questions:
                    break
        i += 1

    results, t0 = [], time.time()
    for k, q in enumerate(chosen, 1):
        got = ask(q["question"])
        ok, why = judge(q["question"], str(q["answer"]), got)
        results.append({"category": CATEGORIES.get(q.get("category"), "?"), "question": q["question"],
                        "gold": q["answer"], "got": got, "correct": ok, "why": why})
        print(f"  [{k:>3}/{len(chosen)}] {CATEGORIES.get(q.get('category'),'?'):<11} {'OK ' if ok else 'MISS'} "
              f"{q['question'][:62]}", flush=True)

    per = {}
    for r in results:
        per.setdefault(r["category"], []).append(r["correct"])
    summary = {c: round(sum(v) / len(v), 3) for c, v in per.items()}
    overall = round(sum(r["correct"] for r in results) / max(1, len(results)), 3)
    report = {"conv": pick["sample_id"], "sessions": len(sessions_of(conv)), "questions": len(results),
              "overall": overall, "per_category": summary,
              "nodes": len(mem.current_nodes()), "edges": len(mem.live_edges()), "messages": mem.last_id(),
              "minutes": round((time.time() - started) / 60, 1), "results": results}
    dest = OUT / f"{datetime.now():%Y-%m-%d_%H-%M}_{args.tag}.json"
    dest.write_text(json.dumps(report, indent=1))
    print(f"\nOVERALL {overall:.1%} over {len(results)}   per category: {summary}")
    print(f"written to {dest}")


if __name__ == "__main__":
    main()
