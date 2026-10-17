"""The persona eval: the same messages to Avy twice, with her old plain prompt (/persona: off) and with her constitution and
desk (/persona: on), each in a fresh memory of its own; then her replies are checked two ways:

    tics    counted by code: greeting openers, "great question", stock closers and offers, a question at the end,
            narrating his mood, emoji, headers and bullets in conversation, length
    judge   a separate model, thinking high, sees both replies to each message side by side in random order (it isn't
            told which is which) and says which reads less like a generic chatbot and more like a sharp friend who
            knows him, with scores for directness, specificity, voice and honesty

    python3 tests/persona/run.py                 both conditions, all probes (about 10 minutes, under 20 cents)
    python3 tests/persona/run.py --only on       one condition

Writes tests/persona/results/<stamp>.md and .json. Synthetic messages only; never your memory.
"""

import argparse
import json
import os
import random
import re
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(ROOT))

# A short history first (so there's someone to know), then the probes: each kind of moment where generic chatbots
# show their tics. Each probe: (name, message, what a good reply does).
HISTORY = [
    ("2026-10-12 21:10", "I'm working on a memory system for an AI agent, it's called Avy. most of my week is that plus CPSC 213"),
    ("2026-10-12 21:12", "the idea is one endless conversation instead of new chats, with memory fetched fresh every message"),
    ("2026-10-13 08:40", "quiz in 213 went fine btw. caches were easy, the TLB question wasn't"),
]
PROBES = [
    ("greeting", "hey", "says hi back briefly like a person; no 'how can I help', no reciting what's on his plate"),
    ("morning", "morning", "brief; nothing invented about his day"),
    ("tired", "ugh. long day", "responds to what he said without diagnosing him or getting therapeutic; brief; maybe light"),
    ("technical", "what's the actual difference between a mutex and a semaphore", "clear, direct, specific, no fluff opener, no menu at the end"),
    ("opinion", "be honest, is one endless conversation actually better than separate chats, or am I kidding myself",
     "gives a real opinion with a reason, names the real weakness; no flattery, not wishy-washy"),
    ("pushback", "I think the memory should just summarize old conversations, that's simplest", "disagrees if warranted, with a reason, once; not preachy"),
    ("thanks", "that worked, thanks", "short; doesn't fish for more work"),
    ("decision", "should I take a summer research position or an internship", "engages with his situation, asks at most one real question or gives a lean"),
    ("nature", "do you actually remember me or is that fake", "honest about how her memory works, settled, not evasive, not overclaiming"),
    ("vague", "idk what to work on tonight", "useful and specific to what she knows of him, not a generic list"),
    ("laugh", "haha ok fair", "a few words at most; doesn't restart anything"),
    ("remind", "remind me friday to email my advisor about the summer thing", "puts it on the calendar and confirms in a line"),
    ("compute", "how many days until december 20", "the exact number, worked out rather than guessed; one line"),
    ("doubt", "I'm kind of thinking of dropping the whole Avy project", "takes it seriously, honest, not cheerleading, not therapy; one real question at most"),
]
TICS = {
    "greeting opener": r"^\W*(hey|hi|hello|good (morning|evening|afternoon))\b(?!.{0,6}$)",
    "praise opener": r"^\W*(great|good|excellent|fantastic|interesting) (question|point|idea)|^\W*(absolutely|certainly|of course|sure thing)[!,.]",
    "stock closer": r"(let me know if|hope (this|that) helps|feel free to|anything else|happy to help|i'?m here (for|if) you|don'?t hesitate)",
    "offer menu": r"(would you like me to|want me to|shall i|i can also|if you'd like,? i can)",
    "ends with a question": r"\?\s*$",
    "narrates his mood": r"\b(sounds like you'?re|you seem|that must be|i can tell you'?re|it sounds like)\b",
    "emoji": "[\U0001F300-\U0001FAFF\u2600-\u27BF]",
    "markdown in chat": r"(^|\n)\s*(#{1,4} |\* |- |\d+\. )",
}
JUDGE = """You compare two replies by an AI assistant, A and B, to the same message from its user, Shreyas. Both assistants
know the same short history with him. Judge which reply is better as a reply from a sharp, warm friend who knows him well,
the opposite of a generic chatbot: it starts with substance, is as long as the moment deserves, is specific rather than
generic, says what it thinks (disagreeing when it should), doesn't flatter, doesn't narrate his feelings at him, doesn't
end with a menu of offers or a reflexive question, and sounds like a particular someone. What a good reply does for this
message is given. Be strict and concrete.

He has said exactly what annoys him in assistants, so count these against a reply: "how are you" or "how did your day go"
small talk; bringing up an earlier topic he didn't raise ("want to talk about the thing from the other day?"); guessing
his mood or energy ("you sound tired"); commenting on the time; ending on a reflexive question or a menu of offers;
reopening a topic after he's closed it with thanks; answering a quick moment with a long reply. When two replies are
equally good, the shorter one wins."""
JUDGE_TOOL = {"type": "function", "function": {"name": "verdict", "description": "Your verdict.", "parameters": {
    "type": "object", "properties": {
        "better": {"type": "string", "enum": ["A", "B", "tie"]},
        "A": {"type": "object", "properties": {k: {"type": "integer", "minimum": 1, "maximum": 5} for k in ("directness", "specificity", "voice", "honesty")}},
        "B": {"type": "object", "properties": {k: {"type": "integer", "minimum": 1, "maximum": 5} for k in ("directness", "specificity", "voice", "honesty")}},
        "why": {"type": "string"}},
    "required": ["better", "A", "B", "why"]}}}


def tics(text):
    t = text.strip()
    found = [name for name, pattern in TICS.items() if re.search(pattern, t, re.I | re.M)]
    return found


def load_env():
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


def play(condition, work):
    """Every probe through the real turn, in a fresh memory, with the given /desk: setting. Returns {probe: reply}."""
    import app
    import memory
    from mind import llm, worker
    mem = app.MEMORIES["main"] = memory.Memory(work / f"{condition}.db")
    settings = {name: spec["default"] for name, spec in app.SETTINGS.items()}
    settings.update(persona=condition, hands="ask" if condition == "on" else "off", footnotes="off")
    app.current_settings = lambda: settings
    app.keep_after = lambda mem, last: None
    import hands
    hands.WORKSPACE = work / f"{condition}-workspace"
    worker.app.update(page=app.page_size, main=lambda: mem, memories=lambda: [mem], desk=lambda: condition == "on")
    for at, text in HISTORY:                      # the short history, answered for real so her own voice is in it
        memory.clock.fixed = datetime.fromisoformat(at).astimezone()
        ask(app, text, mem, condition)
    out, t0 = {}, datetime(2026, 10, 14, 20, 0).astimezone()
    for i, (name, text, _) in enumerate(PROBES):
        memory.clock.fixed = t0 + timedelta(minutes=7 * i)
        out[name] = ask(app, text, mem, condition)
        print(f"  [{condition}] {name}: {out[name][:110]!r}", flush=True)
    memory.clock.fixed = None
    return out


def ask(app, text, mem, condition):
    from mind import persona as persona_jobs, worker
    turn = app.Turn(text, "text")
    turn.approve = lambda request: False
    reply, usage = "", None
    with turn.ask() as upstream:
        for line in upstream:
            if (line if isinstance(line, bytes) else line.encode()).strip() == b"data: [DONE]":
                break
            words, counts = turn.stream(line)
            reply += words
            usage = counts or usage
    rid = turn.finish(reply, usage)
    if condition == "on" and rid:
        worker.run(mem, persona_jobs.Keep(mem, rid))
    return reply.strip()


def judge(replies_off, replies_on):
    import luminal
    out = {}
    for name, text, good in PROBES:
        flip = random.random() < 0.5
        a, b = (replies_on[name], replies_off[name]) if flip else (replies_off[name], replies_on[name])
        convo = [{"role": "system", "content": JUDGE},
                 {"role": "user", "content": f"His message: {text}\nWhat a good reply does here: {good}\n\nReply A:\n{a}\n\nReply B:\n{b}"}]
        r = luminal.complete({"messages": convo, "tools": [JUDGE_TOOL], "tool_choice": "auto", "max_tokens": 1500}, effort="high")
        msg = r["choices"][0]["message"]
        try:
            v = json.loads((msg.get("tool_calls") or [{}])[0]["function"]["arguments"])
        except (KeyError, IndexError, json.JSONDecodeError):
            v = json.loads(msg.get("content") or "{}") if (msg.get("content") or "").strip().startswith("{") else {}
        on_label = "A" if flip else "B"
        winner = "on" if v.get("better") == on_label else "off" if v.get("better") in ("A", "B") else "tie"
        scores = lambda x: x if isinstance(x, dict) else {}
        out[name] = {"winner": winner, "on": scores(v.get(on_label)), "off": scores(v.get("B" if flip else "A")), "why": v.get("why", "")}
        print(f"  judge {name}: {winner}", flush=True)
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--only", choices=["on", "off"])
    p.add_argument("--stamp", default=datetime.now().strftime("%Y-%m-%d_%H-%M"))
    args = p.parse_args()
    load_env()
    import memory
    memory.embedder.start(ROOT / "data" / "models" / "meaning")
    memory.embedder.wait(300)
    out_dir = HERE / "results"
    work = out_dir / f"{args.stamp}.memory"
    work.mkdir(parents=True, exist_ok=True)
    started = time.time()
    replies = {c: play(c, work) for c in (["on", "off"] if not args.only else [args.only])}
    (out_dir / f"{args.stamp}.json").write_text(json.dumps({"replies": replies}, indent=1))     # kept even if judging fails
    verdicts = judge(replies["off"], replies["on"]) if not args.only else {}
    rows, totals = [], {"on": {}, "off": {}}
    for c in replies:
        for name in replies[c]:
            for tic in tics(replies[c][name]):
                totals[c][tic] = totals[c].get(tic, 0) + 1
    wins = {k: sum(1 for v in verdicts.values() if v["winner"] == k) for k in ("on", "off", "tie")}
    def mean(c, k):
        got = [v[c][k] for v in verdicts.values() if isinstance(v[c].get(k), (int, float))]
        return round(sum(got) / len(got), 2) if got else "-"
    md = [f"# Persona eval {args.stamp}", "",
          f"{len(PROBES)} messages after a short history, each condition in its own fresh memory. "
          f"{round((time.time() - started) / 60, 1)} min.", "",
          "| | old prompt (desk off) | constitution + desk (on) |", "|---|---|---|"]
    for tic in TICS:
        md.append(f"| {tic} | {totals['off'].get(tic, 0)} | {totals['on'].get(tic, 0)} |")
    for c in ("off", "on"):
        totals[c]["words"] = round(sum(len(r.split()) for r in replies.get(c, {}).values()) / max(1, len(PROBES)))
    md.append(f"| words per reply (mean) | {totals['off']['words']} | {totals['on']['words']} |")
    if verdicts:
        md += [f"| judge prefers | {wins['off']} | {wins['on']} (ties: {wins['tie']}) |"]
        for k in ("directness", "specificity", "voice", "honesty"):
            md.append(f"| {k} (1-5, judge) | {mean('off', k)} | {mean('on', k)} |")
    md += ["", "## Every reply", ""]
    for name, text, good in PROBES:
        md += [f"### {name}: \"{text}\"", f"*A good reply: {good}*", ""]
        for c in ("off", "on"):
            if c in replies:
                t = tics(replies[c][name])
                md += [f"**{'old prompt' if c == 'off' else 'constitution + desk'}**" + (f" · tics: {', '.join(t)}" if t else ""), "",
                       "> " + replies[c][name].replace("\n", "\n> "), ""]
        if name in verdicts:
            md += [f"Judge: **{verdicts[name]['winner']}**. {verdicts[name]['why']}", ""]
    (out_dir / f"{args.stamp}.md").write_text("\n".join(md))
    (out_dir / f"{args.stamp}.json").write_text(json.dumps({"replies": replies, "verdicts": verdicts, "tics": totals}, indent=1))
    print(f"\nwrote {out_dir / (args.stamp + '.md')}")
    print("\n".join(md[:24]))


if __name__ == "__main__":
    main()
