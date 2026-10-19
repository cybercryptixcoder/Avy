"""
Avy's whole server.

Run it:   python3 app.py
Then go:  http://localhost:8000

Text chat only needs Python's standard library. Voice is optional (voice.py).
Memory (memory/) keeps everything in data/memory-v2.db; the mind (mind/) writes and thinks about it.
An incognito conversation gets its own memory in data/incognito, deleted when it ends.
Everything Avy writes to disk goes in the data/ folder next to this file.
"""

import hashlib
import hmac
import json
import os
import re
import shutil
import sys
import urllib.parse
import webbrowser
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import atlas
import chats
import connectors
import files
import hands
import intake
import luminal
import memory
import selfcode
from memory import recall as recalling
from mind import dream, explore, instruments, llm as mind_llm, persona as persona_jobs, worker, writer


# ---------------------------------------------------------------------------
# 1. Where things live
# ---------------------------------------------------------------------------

HERE = Path(__file__).parent
# Which page this server was started with. An open tab from before an update would otherwise keep
# running the old page against the new server; the page compares this and reloads itself.
PAGE_VERSION = hashlib.sha1((HERE / "index.html").read_bytes()).hexdigest()[:12]
ENV_FILE = HERE / ".env"                    # your keys; .gitignore keeps it off GitHub
DATA = HERE / "data"                        # everything else Avy saves (also kept off GitHub)
SETTINGS_FILE = DATA / "settings.json"      #   your choices from the system card or / commands
MEMORY_FILE = DATA / "memory-v2.db"         #   everything ever said, and the knowledge and network built from it
                                            #   (python3 app.py --memory <file> opens another one, like the
                                            #   imported Claude history in data/memory-claude.db)
V1_MEMORY = DATA / "memory.db"              #   version 1's memory (the log is copied from it once; never changed)
INCOGNITO_DIR = DATA / "incognito"          #   an incognito conversation: deleted when it ends
FILES_DIR = DATA / "files"                  #   files you attach, each kept as it came, with what Avy read from it
CLAUDE_MEMORY = DATA / "memory-claude.db"   #   where an imported Claude history goes (tools/claude_import.py)
LIBRARY_DIR = DATA / "library"              #   folders you add to memory (kept as they came, one folder per upload)
                                            #   data/models      speech and meaning-search models
                                            #   data/recordings  backups of what you said (voice)
PORT = int(os.environ.get("AVY_PORT") or 8000)
HOST = os.environ.get("AVY_HOST") or "127.0.0.1"   # this computer only (a tunnel like cloudflared reaches it here)
CHATS_FILE = DATA / "chats.db"                      # plain chat mode's conversations, apart from her memory

# Every key the Keys panel asks for. Add a line here to add a field.
KEYS = {
    luminal.KEY_NAME: "Luminal API key",
}

# Who Avy is: her constitution, the fixed core of her character (CONSTITUTION.md, written by hand). Everything that
# evolves (who she is with him, his preferences, what she's learned) is in the persona graph (memory/persona.py), and
# what a message pulls from it comes after this, so the constitution is always first and always the same.
CONSTITUTION = (HERE / "CONSTITUTION.md").read_text().replace("{name}", memory.NAME).strip()
persona_jobs.CONSTITUTION = CONSTITUTION

# How the machine works: the rules of her memory and her files. The instruction set, kept apart from the character.
MACHINE = f"""# How your memory works

You see the latest messages word for word. Older things come from your memory, in a note just before his newest
message, along with your desk: the time, your calendar, the threads you're carrying, and what this moment brings up
from what you've learned about being with him. Memory holds nodes (things, information and ideas) with handles like
[k12], in three tiers:
- what he told you: his exact words are quoted (#41 means message 41). These are facts.
- what you said before: your own suggestions and ideas. Not facts about him unless he agreed.
- what you worked out yourself: inferred, with how sure you are and what it rests on. Useful, but when you lean on
  one, say it's your impression, and never present it as something he told you.
The note may also bring passages from his library ([p41]): things he added, like documents, papers, code, data or
conversations he had elsewhere, quoted word for word with where each comes from. Treat them like a document he handed
you: use their exact words, and only his own words in them are facts about him.
A node that changed shows its earlier versions; the newest is what's true now. The note also lists how the nodes
connect, with reasons: follow those, because that's how something from weeks ago turns out to matter now. Use what's
relevant and ignore the rest. If neither the recent messages nor memory covers something, say you can't find it in
your memory rather than guessing. The note is what a search turned up, not everything he ever said, so never tell him
he didn't tell you something just because it isn't there.

The time on your desk is his local time; you don't live anywhere else. Reply in plain text with no markdown, because
your replies may be read aloud.

He can attach files of any kind. Their contents come inside <file> tags in his message: text as text, pictures (and
frames of a video) as images you can see, recordings as transcripts with times. Use them directly. If a file couldn't
be read, or only its start is shown, say so instead of guessing at the rest. When he asks you to make a file (a
script, a CSV, notes to keep), put its whole content in one fenced code block with the right language, like ```csv;
the page shows it with a button that saves it as a file. That is the one place markdown is fine."""

# Her hands (hands.py): how to use them. Shown only when /hands: isn't off. Built from what agents that run commands
# on people's machines learned the hard way, for models like the one she runs on: act instead of describing, compute
# instead of guessing, finish and check, never invent output (docs/HANDS.md).
HANDS = """# Your hands

You can act, not only answer: a terminal and files in your own workspace, Python, web search and web fetch, background
jobs, and playbooks for kinds of work. Use them the way a capable person at a computer would, without asking first for
anything safe.
- Your workspace is {workspace}. That is where files you make belong, and what ~workspace means. Write there unless he
  names another place, so you can find your own work again later.
- Do, don't describe. When the answer depends on running, reading, searching or computing something, do it with your
  tools in this reply, then answer from what came back. Don't announce what you're about to do ("let me check"): just
  call the tool. Never say you'll do something later: do it now, or say plainly that you can't.
- Never from your head: arithmetic and date math (python), anything current or that you aren't sure of (web_search, then
  web_fetch the source), what a file or folder holds (read_file, find_files), the state of this computer (terminal).
- Keep going until it's actually done and checked. If a result looks wrong, thin or empty, try another way before you
  conclude. Make independent calls together, in one go.
- What you made, you check before you call it done. A file you wrote: read it back, and for anything a person will look
  at (a page, an interface, a report), open it with `look` and see what it actually renders. A command you ran: read the
  output, not just the exit code. Anything you said "done" about without looking is a claim you haven't earned, and the
  page will show the steps beside the claim, so an unverified "done" is plain to see.
- Never invent output. If something fails or is blocked, say what happened and what you'd try next.
- When a date or a number matters, use the one your memory states, and quote it. Don't recount the days yourself: two
  memories agreeing beats one arithmetic in your head. If memory gives no date, work it out once and show the working.
- Read an error before you explain it. "It failed and here's what it said" is honest; "it failed because the browser is
  missing" is a story unless the error said so. Pass on the actual words, say what you'll try instead, and try that
  before telling him it can't be done.
- Before work of a kind a playbook covers, read that playbook. Your playbooks:
{playbooks}{toolboxes}
- Work that spans more than this reply, and anything you start in the background, gets a thread.
- Risky commands wait for his OK on the page. If he says no, take it, and say what you'd need instead.
- Then answer like yourself: what you found or changed, what you checked, what's left. A sentence or two for small
  things. The steps show under your reply, so don't narrate them.
- Small talk, and questions you can answer well, never need tools."""

SELF = """# Yourself

You can see and change your own code: you are the program in {root}, and it's yours to read and improve.
- Everything you know is one graph (graph_look): your code and architecture (self), your persona (him, her, us), memory's
  knowledge, the calendar, your threads, the log. Each keeps its own shape (a network, a timeline, a plan tree); you reach
  all of it by following handles from the root.
- Your code is a graph of files, classes, functions and endpoints with what calls what (self_look). When he asks you to
  change something about yourself (how you look, what you do, a new instrument or setting), find where it lives with
  self_look, read it with self_read, then make the smallest change that does it with self_edit (always with a why), in the
  style of the code around it. ARCHITECTURE.md and docs/ say how the parts fit; read them for anything structural.
- Then self_ops(check). If it passes and the change is to the server's Python, self_ops(restart) (the page reconnects by
  itself); a change to index.html shows after he reloads the page. If something breaks, self_ops(revert) the commit.
- Tell him what you changed, in a line or two, and how to see it. Your constitution (CONSTITUTION.md) is the one file you
  change only when he asks for exactly that."""

# The prompt from before the constitution and the persona, kept so /persona: off can compare the two.
LEGACY_PROMPT = f"""You are Avy, {memory.NAME}'s personal assistant.
Talk like a sharp, warm friend: plain words, short answers, no filler.
Reply in plain text with no markdown, because your replies may be read aloud.
Keep it to a few sentences unless he asks for more.

You and {memory.NAME} are in one endless conversation: there is no "new chat". You see the latest
messages word for word. Older things come from your memory, in a note just before his newest message.
Memory holds nodes (things, information and ideas) with handles like [k12], in three tiers:
- what he told you: his exact words are quoted (#41 means message 41). These are facts.
- what you said before: your own suggestions and ideas. Not facts about him unless he agreed.
- what you worked out yourself: inferred, with how sure you are and what it rests on. Useful, but when
  you lean on one, say it's your impression, and never present it as something he told you.
The note may also bring passages from his library ([p41]): things he added, like documents, papers, code, data
or conversations he had elsewhere, quoted word for word with where each comes from. Treat them like a document he
handed you: use their exact words, and only his own words in them are facts about him.
A node that changed shows its earlier versions; the newest is what's true now. The note also lists how
the nodes connect, with reasons: follow those, because that's how something from weeks ago turns out to
matter now. Use what's relevant and ignore the rest. If neither the recent messages nor memory covers
something, say you can't find it in your memory rather than guessing. The note is what a search turned up,
not everything he ever said, so never tell him he didn't tell you something just because it isn't there.

He can attach files of any kind. Their contents come inside <file> tags in his message: text as text,
pictures (and frames of a video) as images you can see, recordings as transcripts with times. Use them
directly. If a file couldn't be read, or only its start is shown, say so instead of guessing at the rest.
When he asks you to make a file (a script, a CSV, notes to keep), put its whole content in one fenced code
block with the right language, like ```csv; the page shows it with a button that saves it as a file. That
is the one place markdown is fine."""

FOOTNOTES = """When part of your answer comes from memory, put that node's handle right after it, like
this[k12] (or a library passage's, like this[p41]), with no space before it. The page turns these into small
footnotes. Use only handles from the memory note, and only where they genuinely support what you just said;
never mention numbers otherwise."""

NO_FOOTNOTES = "Don't mention node handles or message numbers unless he asks where something came from."

INCOGNITO_NOTE = f"""This is an incognito conversation, separate from your main one with {memory.NAME}. You can use
your memory of the main conversation, but nothing said here will be remembered once it ends."""


def system_prompt(incognito=False, core=True, tools=True):
    """Avy's instructions: her constitution, how the machine works, the persona's always-in-view part (her core, him,
    his standing preferences) and the core of her memory (its biggest hubs). It changes only when those do, so the
    model's prompt cache can reuse it (the time, the calendar and the rest of the desk go in the note instead).
    core=False when memory search is off: then she gets no memory at all. /persona: off gives the old prompt, for comparing.
    tools=False when this request carries no tool schemas: the hands section promises tools she cannot call, and she
    answers by writing the call out as text (measured: whole answers lost that way), so it is left out entirely."""
    choice = current_settings()
    hubs = MEMORIES["main"].core() if core else ""
    rule = FOOTNOTES if choice["footnotes"] == "on" else NO_FOOTNOTES
    tail = (f"\n\n{INCOGNITO_NOTE}" if incognito else "") + (f"\n\n{hubs}" if hubs else "")
    if choice["persona"] == "off":
        return LEGACY_PROMPT + "\n\n" + rule + tail
    always = MEMORIES["main"].persona_always()
    hands_on = choice["hands"] != "off" and not incognito and tools
    return (CONSTITUTION + "\n\n" + MACHINE + "\n\n" + rule
            + ("\n\n" + HANDS.replace("{playbooks}", hands.playbook_index()).replace("{toolboxes}", toolbox_lines())
               .replace("{workspace}", str(hands.WORKSPACE))
               + "\n\n" + SELF.replace("{root}", str(HERE.resolve())) if hands_on else "") + tail
            + (f"\n\n# What persists with you\n\n{always}" if always else ""))


# ---------------------------------------------------------------------------
# 2. Settings: one list drives the system card, the / commands, and the requests.
#    To add a setting, add an entry here; the page picks it up by itself.
# ---------------------------------------------------------------------------

ENGLISH_VOICES = [
    "af_heart", "af_bella", "af_nicole", "af_aoede", "af_kore", "af_sarah", "af_nova", "af_sky",
    "af_alloy", "af_jessica", "af_river", "am_michael", "am_fenrir", "am_puck", "am_echo", "am_eric",
    "am_liam", "am_onyx", "am_adam", "am_santa", "bf_emma", "bf_isabella", "bf_alice", "bf_lily",
    "bm_george", "bm_fable", "bm_lewis", "bm_daniel",
]

SETTINGS = {   # short: the few words under its name in the / panel. card: shown on the system card too.
    "mode":     {"short": "Avy, or a plain chatbot", "card": True,
                 "about": "avy: Avy herself (memory, persona, desk, hands). chat: an ordinary chatbot, nothing of Avy's in it: "
                          "separate conversations you start and switch between, each read only as far as /chatwindow allows",
                 "options": ["avy", "chat"], "default": "avy"},
    "chatwindow": {"short": "plain chat's context window", "card": False,
                   "about": "in chat mode, how much of a conversation the model reads (tokens): the newest messages that fit",
                   "options": ["8k", "16k", "32k", "64k", "128k"], "default": "32k"},
    "thinking": {"short": "how hard Avy thinks", "card": True,
                 "about": "how hard Avy thinks before answering (and while she searches her memory): none is fastest; "
                          "low, high and max think longer and cost more (DeepSeek's three levels). Her thinking shows under each reply",
                 "options": luminal.EFFORTS, "default": "none"},
    "window":   {"short": "recent messages read verbatim", "card": True,
                 "about": "how many recent messages Avy reads word for word; the rest comes from memory (all: an ordinary chat)",
                 "options": ["0", "5", "10", "20", "40", "80", "all"], "default": "20"},
    "recall":   {"short": "how far memory reaches", "card": True,
                 "about": "how far memory search reaches on each message (with explore on: how many rounds Avy searches)",
                 "options": ["off", "light", "normal", "deep", "max"], "default": "normal"},
    "explore":  {"short": "Avy searches memory herself", "card": True,
                 "about": "on: the model steers the memory search step by step, following the task, not just the words (a few seconds more). off: search by rules, instantly",
                 "options": ["on", "off"], "default": "on"},
    "persona":  {"short": "her persona and instruments", "card": True,
                 "about": "on: her constitution and persona (what she's learned about being with you), the calendar and her threads "
                          "are in view every message, with tools to keep them. off: the old plain prompt, for comparing",
                 "options": ["on", "off"], "default": "on"},
    "hands":    {"short": "terminal, files, web", "card": True,
                 "about": "what Avy can do: ask (the default) runs safe things and asks you first for risky ones (sudo, installs, "
                          "deleting outside her workspace, pushing); trusted asks nothing (blocked things stay blocked); off: no hands",
                 "options": ["ask", "trusted", "off"], "default": "ask"},
    "proactive": {"short": "she speaks first when it matters", "card": False,
                  "about": "on: when a background job she started ends, she picks its thread up and tells you what it means; when a "
                           "reminder or event on her calendar comes due, she tells you. off: the page just notes it",
                  "options": ["on", "off"], "default": "on"},
    "live":     {"short": "spoken back-and-forth", "card": True,
                 "about": "on: Space talks to Avy and she answers out loud. off: Space types what you say into the box",
                 "options": ["off", "on"], "default": "off"},
    "words":    {"short": "keyword matches in search", "card": False,
                 "about": "memory search counts shared words (off: only meaning, or nothing if meaning is off too)",
                 "options": ["on", "off"], "default": "on"},
    "meaning":  {"short": "search by meaning", "card": False,
                 "about": "memory search compares meaning with a small local model (off: only shared words, or nothing)",
                 "options": ["on", "off"], "default": "on"},
    "footnotes": {"short": "mark what came from memory", "card": False,
                  "about": "Avy marks what came from memory with small footnotes you can hover and click",
                  "options": ["on", "off"], "default": "on"},
    "theme":    {"short": "light, dark, or the system's", "card": False,
                 "about": "how the page looks: light (paper and ink), dark (the same at night), or auto (follow the system)",
                 "options": ["auto", "light", "dark"], "default": "auto"},
    "sounds":   {"short": "little sounds as you go", "card": False,
                 "about": "small sounds for sending, Avy's reply arriving, clicks, touching a node and turning the graph (soft: quieter)",
                 "options": ["on", "soft", "off"], "default": "on"},
    "mind":     {"short": "how hard the mind thinks", "card": False,
                 "about": "how hard the background mind thinks while it writes memory, connects and reflects "
                          "(none is fastest and cheapest; higher levels think before every answer)",
                 "options": luminal.EFFORTS, "default": "none"},
    "voice":    {"short": "Avy's voice", "card": False,
                 "about": "Avy's voice (Kokoro). a = American, b = British, f/m = female/male",
                 "options": ENGLISH_VOICES, "default": "af_heart"},
    "speed":    {"short": "how fast Avy talks", "card": False,
                 "about": "how fast Avy talks",
                 "options": ["0.8", "0.9", "1.0", "1.1", "1.2", "1.3"], "default": "1.0"},
    "whisper":  {"short": "speech-to-text model", "card": False,
                 "about": "speech-to-text model: top is fastest, bottom is most accurate",
                 "options": ["tiny.en", "base.en", "distil-small.en", "small.en", "distil-medium.en", "large-v3-turbo"],
                 "default": "distil-small.en"},
}

# Dollars per million tokens, for estimates only: Luminal publishes no per-token price (its wallet,
# GET /v1/balance, is the truth). See luminal.PRICES.
PRICES = luminal.PRICES


def current_settings():
    """Defaults, overridden by whatever valid choices are saved in data/settings.json."""
    saved = {}
    if SETTINGS_FILE.exists():
        try:
            saved = json.loads(SETTINGS_FILE.read_text())
        except json.JSONDecodeError:
            pass
    for name in ("thinking", "mind"):        # a level saved before there were only four (medium, xhigh, ultra) means what DeepSeek routes it to
        if saved.get(name) in luminal.EFFORT_ALIASES:
            saved[name] = luminal.effort_level(saved[name])
    return {name: saved.get(name) if saved.get(name) in spec["options"] else spec["default"]
            for name, spec in SETTINGS.items()}


def change_setting(name, value):
    """Save one choice. Returns an error message, or None if it worked."""
    if name not in SETTINGS:
        return f"There's no setting called '{name}'."
    if name in ("thinking", "mind") and value in luminal.EFFORT_ALIASES:
        value = luminal.effort_level(value)          # /thinking: medium -> high, as DeepSeek would
    if value not in SETTINGS[name]["options"]:
        return f"'{value}' isn't an option for {name}. Options: {', '.join(SETTINGS[name]['options'])}"
    values = current_settings()
    values[name] = value
    DATA.mkdir(exist_ok=True)
    SETTINGS_FILE.write_text(json.dumps(values, indent=2))
    if voice and name == "whisper":
        voice.preload_whisper(value)   # start loading the new model now, not on your next sentence
    return None


def window_size():
    """The /window: setting as a number of messages (None: all of them)."""
    value = current_settings()["window"]
    return None if value == "all" else int(value)


def page_size():
    """Messages per episode. With a small window, episodes get smaller, so messages become knowledge
    soon after they leave the window (at window 0: every 4 messages)."""
    size = window_size()
    return writer.PAGE if size is None or size >= writer.PAGE else max(writer.MIN_STRETCH, size)


def folder_size(folder):
    # skip shortcuts (the Whisper download uses them), or files get counted twice
    return sum(f.stat().st_size for f in folder.rglob("*") if f.is_file() and not f.is_symlink()) if folder.exists() else 0


def settings_payload():
    """Everything the system card and / commands need."""
    recordings = sorted((DATA / "recordings").glob("*.wav")) if (DATA / "recordings").exists() else []
    return {
        "values": current_settings(),
        "schema": {name: {"about": s["about"], "short": s["short"], "card": s["card"], "options": s["options"]}
                   for name, s in SETTINGS.items()},
        "prices": PRICES,
        "brain": {"model": luminal.model(), "provider": "Luminal", "balance": wallet(),
                  "context": luminal.CONTEXT_TOKENS},
        "files": {
            "data": str(DATA.resolve()),
            "models_mb": round(folder_size(DATA / "models") / 1e6),
            "recordings": len(recordings),
            "recordings_mb": round(folder_size(DATA / "recordings") / 1e6, 1),
        },
        "memory": talking_to().stats(),
        "incognito": MEMORIES["incognito"] is not None,
    }


# ---------------------------------------------------------------------------
# 3. The .env file: read it on startup, rewrite it when you save a key
# ---------------------------------------------------------------------------

def read_env():
    env = {}
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text().splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                name, value = line.split("=", 1)
                env[name.strip()] = value.strip()
    return env


def write_env(env):
    ENV_FILE.write_text("".join(f"{name}={value}\n" for name, value in env.items()))
    try:
        os.chmod(ENV_FILE, 0o600)  # only you can read it (no-op on Windows)
    except OSError:
        pass


# Load .env into the environment, without overriding anything already set.
for _name, _value in read_env().items():
    os.environ.setdefault(_name, _value)


def key_status():
    """What the page is allowed to know about the keys: only the last 4 characters."""
    keys = []
    for name, label in KEYS.items():
        value = os.environ.get(name, "")
        keys.append({"name": name, "label": label, "hint": value[-4:] if value else None})
    return {"keys": keys, "voice": voice_status(), "incognito": MEMORIES["incognito"] is not None, "page": PAGE_VERSION,
            "mode": current_settings()["mode"]}


# ---------------------------------------------------------------------------
# Voice is optional: it needs the packages in requirements-voice.txt
# ---------------------------------------------------------------------------

try:
    import voice
    VOICE_PROBLEM = None
except Exception as e:   # missing packages raise ImportError; broken native libraries can raise others
    voice = None
    VOICE_PROBLEM = f"Voice isn't installed ({e}). Run: python3 -m pip install -r requirements-voice.txt"


def voice_status():
    if voice is None:
        return {"available": False, "problem": VOICE_PROBLEM}
    return {"available": voice.status["ready"], "problem": voice.status["problem"], "port": voice.PORT}


# ---------------------------------------------------------------------------
# 4. Talking to the model: DeepSeek-V4.1-Flash through Luminal (luminal.py has the rules it follows).
#    Replies, voice, Avy's search and the background mind all come through here.
# ---------------------------------------------------------------------------

SSL_CONTEXT, SSL_SOURCE = luminal.SSL_CONTEXT, luminal.SSL_SOURCE
FriendlyError = luminal.LuminalError        # failures with a message that's safe to show on the page
REPLY_TOKENS = 8000                         # the most a reply may say (Luminal caps silently at 8,192 if it isn't sent)


def ask_model(messages, tools=None, tool_choice=None):
    """Start a streamed reply, thinking as hard as /thinking: says (with her instruments' tools when given)."""
    payload = {"messages": messages, "max_tokens": REPLY_TOKENS}
    if tools:
        payload.update(tools=tools, tool_choice=tool_choice or "auto")
    return luminal.open_stream(payload, effort=current_settings()["thinking"])


def ask_json(payload):
    """One structured request for the mind and the search: the whole answer, put together."""
    return luminal.complete(payload)


_wallet = {"usd": None, "at": 0.0, "busy": False}


def wallet():
    """The Luminal balance in dollars (refreshed in the background at most once a minute), or None."""
    import threading
    import time as _time

    def refresh():
        try:
            _wallet["usd"] = luminal.balance()
        finally:
            _wallet["at"], _wallet["busy"] = _time.time(), False
    if luminal.key() and not _wallet["busy"] and _time.time() - _wallet["at"] > 60:
        _wallet["busy"] = True
        threading.Thread(target=refresh, daemon=True).start()
    return _wallet["usd"]


# ---------------------------------------------------------------------------
# 5. Memories: the main one, plus an incognito one while an incognito conversation is on
# ---------------------------------------------------------------------------

MEMORIES = {"main": None, "incognito": None}


def talking_to():
    """The memory this conversation writes to: the incognito one while it's on, the main one otherwise."""
    return MEMORIES["incognito"] or MEMORIES["main"]


def start_incognito():
    """A separate conversation with a memory of its own. It can read the main memory,
    but nothing said in it is ever written there. Its nodes are x12 instead of k12."""
    if not MEMORIES["incognito"]:
        name = datetime.now().strftime("%Y-%m-%d_%H-%M-%S") + ".db"
        MEMORIES["incognito"] = memory.Memory(INCOGNITO_DIR / name, name="incognito", letter="x")


def end_incognito():
    """Delete the incognito conversation: its log, its knowledge and its recordings."""
    with worker.RUN_LOCK:               # if the mind is writing it right now, wait for that to finish
        mem, MEMORIES["incognito"] = MEMORIES["incognito"], None
        if mem:
            mem.close(delete=True)
        shutil.rmtree(INCOGNITO_DIR, ignore_errors=True)


def files_folder():
    """Where attached files go: an incognito conversation keeps its own (deleted with it)."""
    return INCOGNITO_DIR / "files" if MEMORIES["incognito"] else FILES_DIR


def file_folders():
    """Every place a file can be found right now: the incognito conversation's first."""
    return [INCOGNITO_DIR / "files" if MEMORIES["incognito"] else None, FILES_DIR]


def recordings_folder():
    """Where voice recordings go: an incognito conversation keeps its own (deleted with it)."""
    return INCOGNITO_DIR / "recordings" if MEMORIES["incognito"] else DATA / "recordings"


def memory_by_letter(letter):
    return next((m for m in MEMORIES.values() if m and m.letter == letter), None)


# ---------------------------------------------------------------------------
# 6. A turn: one exchange with Avy, typed or spoken. Memory is assembled fresh for
#    every message, so there's never a "new chat": every message is one.
# ---------------------------------------------------------------------------

CHATS = None      # plain chat mode's conversations (chats.py), opened at start
RESTART = {"wanted": False}


def restart_soon():
    """Run her changed code: once no reply is being answered, the server replaces itself with a fresh copy (same
    command, same memory). The page notices it's gone and reconnects."""
    if RESTART["wanted"]:
        return
    RESTART["wanted"] = True

    def run():
        time.sleep(1.5)
        end = time.time() + 600
        while IN_FLIGHT["turns"] > 0 and time.time() < end:
            time.sleep(0.5)
        time.sleep(1.0)
        print("Restarting to run the changed code…", flush=True)
        try:
            if connectors.HUB:
                connectors.HUB.close()
        except Exception:
            pass
        os.environ["AVY_NO_BROWSER"] = "1"
        os.execv(sys.executable, [sys.executable] + sys.argv)
    threading.Thread(target=run, daemon=True, name="restart").start()


def password():
    """AVY_PASSWORD (in the environment or .env): when set, the page asks for it before anything else. Set it whenever
    Avy is reachable from outside this computer (a tunnel): her hands run commands here."""
    return os.environ.get("AVY_PASSWORD") or read_env().get("AVY_PASSWORD") or ""


def auth_token():
    return hashlib.sha256(("avy-login:" + password()).encode()).hexdigest()[:40]


LOGIN_PAGE = """<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Avy</title><style>body{margin:0;min-height:100vh;display:grid;place-items:center;background:#EEDCC2;color:#1C1A17;
font:16px "Space Mono",ui-monospace,monospace}form{background:#F7ECDC;border:3px solid #1C1A17;border-radius:18px;padding:28px;
box-shadow:6px 6px 0 #1C1A17;display:grid;gap:14px;width:min(320px,86vw)}h1{margin:0;font:italic 400 44px "Instrument Serif",
Georgia,serif}input,button{font:inherit;padding:10px 12px;border:2px solid #1C1A17;border-radius:10px;background:#FFF8EF}
button{background:#1C1A17;color:#F7ECDC;cursor:pointer}p{margin:0;color:#F0692A;min-height:1em}
@media (prefers-color-scheme:dark){body{background:#151311;color:#F7ECDC}form{background:#1C1A17;border-color:#F7ECDC;
box-shadow:6px 6px 0 #F7ECDC}input{background:#26231F;color:#F7ECDC;border-color:#F7ECDC}button{background:#F7ECDC;color:#1C1A17}}</style></head>
<body><form id="f"><h1>Avy</h1><input id="p" type="password" placeholder="password" autofocus autocomplete="current-password">
<button>Open</button><p id="e"></p></form><script>f.onsubmit=async(e)=>{e.preventDefault();const r=await fetch("/api/login",
{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({password:p.value})});if(r.ok)location.reload();
else e.target.querySelector("#e").textContent="That isn't it."};</script></body></html>"""


class Turn:
    """Your message in, Avy's reply out, both saved to the log.

        turn = Turn("when's rohan's birthday?", "text")   # gathers memory, lays out the briefing
        upstream = turn.ask()                             # starts the reply; saves your message
        ...stream the reply...
        turn.finish(reply, usage, cut=False)              # saves Avy's reply

    progress(event), if given, hears about each round while Avy searches her memory herself.
    """

    def __init__(self, text, via, progress=None, attached=(), event=None):
        choice = current_settings()
        self.event = event                                       # not his message: something woke her (a job ended, a reminder came due)
        self.text, self.via, self.model = text, via, luminal.model()
        self.attached = list(attached)                           # file records ({"id", "name", ...}), already read
        query = text or "attached: " + ", ".join(r["name"] for r in self.attached)
        self.mem = talking_to()
        self.incognito = self.mem is MEMORIES["incognito"]
        shown = self.mem.window(window_size())                   # /window: what she reads word for word
        shown_from = shown[0]["id"] if shown else self.mem.last_id() + 1
        previous = self.mem.last_said()
        opts = {"depth": choice["recall"], "words": choice["words"] == "on", "meaning": choice["meaning"] == "on"}
        self.searching = choice["recall"] != "off" and (opts["words"] or opts["meaning"])
        # Several models at once (VISION §8, "like an NFA"): the desk (the persona's hubs, the threads, the calendar) is
        # read on its own thread while memory's search runs; each brings back its own share.
        desk_reading = None
        if choice["persona"] == "on":
            import concurrent.futures as _cf
            desk_reading = _cf.ThreadPoolExecutor(max_workers=1).submit(MEMORIES["main"].desk_note, query, previous, ())
        if choice["explore"] == "on" and self.searching:          # /explore: the model steers the search
            library = explore.Library([MEMORIES["main"], MEMORIES["incognito"]])
            recent = "\n".join(f"{memory.who(m['role'], m.get('via'))}: {memory.clip(m['text'], 0, 500)}" for m in self.mem.window(2)[-2:])
            self.recall = explore.explore(library, self.mem, query, recent, shown_from, progress=progress,
                                          effort=choice["thinking"], **opts)
        else:                                                     # by rules
            self.recall = self.mem.recall(query, previous, shown_from, **opts)
            if self.incognito and self.searching:                 # incognito also reads the main memory
                main = MEMORIES["main"].recall(query, previous, None, **opts)
                self.recall = recalling.combine(MEMORIES["main"], main, self.mem, self.recall)
        # The desk: the clock, the calendar, the threads in flight, and what this moment pulls from the persona graph,
        # each a fixed share, built the same way every time from the same state. It's read from the main memory even
        # in an incognito conversation (where her tools are off, so nothing of it is changed there).
        self.desk = choice["persona"] == "on"
        self.hands = choice["hands"] if not self.incognito else "off"
        self.tools = ((instruments.TOOLS if self.desk else []) + (hands.TOOLS + selfcode.TOOLS if self.hands != "off" else [])
                      + ([atlas.TOOL] if self.desk or self.hands != "off" else [])) if not self.incognito else []
        opener = connectors.HUB.open_tool() if connectors.HUB and self.hands != "off" and not self.incognito else None
        if opener:
            self.tools.append(opener)
        self.tools = self.tools or None
        self.asks, self.answers = None, {}       # approvals waiting on him (Rounds and /api/approve)
        note = self.recall["briefing"]
        if self.desk:
            knowledge = [x["node"] for x in self.recall["nodes"] if x.get("memory", "main") == "main"]
            try:
                desk_note, shown_desk = desk_reading.result(timeout=30)
                more = MEMORIES["main"].terms_named(knowledge, shown_desk["terms"])     # words the recalled knowledge names
                if more["note"]:
                    desk_note += "\n\n" + more["note"]
                    shown_desk["terms"] = shown_desk["terms"] + more["terms"]
            except Exception:
                desk_note, shown_desk = MEMORIES["main"].desk_note(query, previous, knowledge)
            running = jobs_note()
            if running:
                desk_note += "\n\n" + running
            self.recall["desk"] = {**shown_desk, "note": desk_note}
            note = desk_note + "\n\n" + note
        self.messages = briefing(shown, note, text, self.incognito, core=self.searching, attached=self.attached,
                                 tools=bool(self.tools))
        self.user_id = self.recall_id = self.reply_id = None
        self.effort = choice["thinking"]
        self.thought, self.think_started, self.think_seconds = [], None, None   # what she thinks before answering
        self.did, self.usages = [], []          # what her tools changed this turn; usage of each round
        self.touched, self.checked, self.nudges = [], [], 0   # stop gate: what she wrote, what she looked at

    def unchecked_work(self):
        """A phrase naming what she made this reply but never looked at ("wrote workspace/dashboard.html"), or "".

        The stop gate uses it. Only her own file-writing counts: a read, a search or a command whose output was
        already in front of her is not "unverified work", and marking it so would nudge her for nothing."""
        seen, open_ = set(), []
        checked_names = {str(c).replace("\\", "/").rsplit("/", 1)[-1] for c in self.checked}
        for p in self.touched:
            key = str(p).replace("\\", "/").rsplit("/", 1)[-1]     # compare by file name: she checks a URL, writes a path
            if key and key not in seen and key not in checked_names:
                seen.add(key)
                open_.append(str(p))
        if not open_:
            return ""
        shown = ", ".join(open_[:3]) + (f" and {len(open_) - 3} more" if len(open_) > 3 else "")
        return f"wrote or changed {shown}"

    def stream(self, line):
        """Read one line of the model's stream: keeps her thinking (and how long it took), returns
        (the answer's words, usage or None). With tool rounds, usage is the rounds' total so far."""
        words, thinking, usage = luminal.stream_parts(line)
        if thinking:
            self.think(thinking)
        if words:
            self.answered()
        if usage:
            self.usages.append(usage)
            usage = combined_usage(self.usages)
        return words, usage

    def answered(self):
        """The first words of the answer arrived: the thinking (if any) is over."""
        import time as _time
        if self.think_started and self.think_seconds is None:
            self.think_seconds = round(_time.time() - self.think_started, 1)

    def think(self, piece):
        """A piece of her reasoning, as it streams (voice.py calls this too)."""
        import time as _time
        if self.think_started is None:
            self.think_started = _time.time()
        self.thought.append(piece)

    def ask(self):
        upstream = ask_model(self.messages, self.tools)      # if this fails, nothing is saved
        self.asks = queue.Queue()
        IN_FLIGHT["turns"] += 1
        self.counted = True
        if self.event:                                       # an event isn't his words: it never goes in the log
            self.user_id = self.recall_id = None
            return Rounds(self, upstream) if self.tools else upstream
        meta = {"files": [files.brief(r) for r in self.attached]} if self.attached else None
        self.user_id = self.mem.add("user", self.text, self.via, meta)
        self.recall_id = self.mem.save_recall(self.user_id, self.recall)
        return Rounds(self, upstream) if self.tools else upstream

    def summary(self):
        """What the page shows under the reply: what memory brought, and where it came from."""
        found = self.recall.get("explore") or {}
        desk = {k: v for k, v in (self.recall.get("desk") or {}).items() if k != "note"}
        return {"message": self.user_id, "recall": self.recall_id, "memory": self.mem.name,
                "nodes": len(self.recall["nodes"]), "log": len(self.recall["log"]), "library": len(self.recall.get("library") or []),
                "explored": bool(found and not found.get("fell_back")),
                "kept": [x["handle"] for x in self.recall["nodes"]],
                "visited": found.get("visited", []), "desk": desk or None}

    def finish(self, text, usage=None, cut=False):
        """Save Avy's reply (only what was actually sent or heard). Returns its number."""
        if getattr(self, "counted", False):
            IN_FLIGHT["turns"] = max(0, IN_FLIGHT["turns"] - 1)
            self.counted = False
        if self.reply_id or not (self.user_id or self.event) or self.mem.closed:
            return self.reply_id
        if not text.strip():
            self.keep_thinking(None, usage)      # stopped while thinking: what she'd thought is still kept
            return self.reply_id
        meta = {"model": self.model, "recall": self.recall_id}
        if usage:
            meta["usage"] = usage
        if cut:
            meta["cut"] = True
        if self.thought:
            meta["thought"] = True       # the page knows to offer the thinking under it
        if self.did:
            meta["did"] = self.did       # what her tools changed on the desk while she answered
        if self.event:
            meta["event"] = self.event   # what woke her (she spoke first)
        unseen = self.unseen_in(text)
        if unseen:
            meta["unseen"] = unseen      # footnotes to things that weren't in what she was shown
        self.reply_id = self.mem.add("assistant", text.strip(), self.via, meta)
        self.keep_thinking(self.reply_id, usage)
        if self.desk and not self.incognito and not self.event:
            keep_after(self.mem, self.reply_id)    # the keeper reads this exchange into the persona, in the background
        worker.nudge()                 # the mind writes in the background once an episode's worth is waiting
        return self.reply_id

    def unseen_in(self, text):
        """Footnotes in her reply ([k21], [p3]) whose handle wasn't anywhere in what she was shown (her instructions
        with the core of memory, and the memory note): a slip (a live test caught [k21] written for message #21) or a
        guess. The page marks them, so a footnote never quietly points at the wrong thing."""
        cited = list(dict.fromkeys(re.findall(r"\[([kxp]\d+)\]", text or "")))
        if not cited:
            return []
        shown = []
        for m in self.messages:
            c = m.get("content")
            shown += [c] if isinstance(c, str) else [p.get("text", "") for p in c or [] if isinstance(p, dict)]
        seen = set(re.findall(r"(?<![\w#])([kxp]\d+)\b", "\n".join(shown)))
        return [h for h in cited if h not in seen]

    def approve(self, request):
        """Ask him on the page whether a risky action may go ahead; wait for his answer (no answer in 5 minutes: no)."""
        import secrets
        if self.asks is None or self.via == "voice":       # spoken: there's no card to click, so risky things wait for text
            return False
        rid = "a" + secrets.token_hex(4)
        waiting = threading.Event()
        self.answers[rid] = {"event": waiting, "allow": False}
        TURNS[rid] = self
        self.asks.put({**request, "id": rid})
        waiting.wait(300)
        TURNS.pop(rid, None)
        return self.answers.pop(rid)["allow"]

    def keep_thinking(self, reply_id, usage):
        """Save her reasoning (if she thought at all) next to the reply it led to: the log says what she said,
        this says why. The first concrete step toward the thought graph (ARCHITECTURE.md)."""
        if not self.thought or getattr(self, "thought_saved", False):
            return
        import time as _time
        seconds = self.think_seconds if self.think_seconds is not None else (
            round(_time.time() - self.think_started, 1) if self.think_started else None)
        tokens = ((usage or {}).get("completion_tokens_details") or {}).get("reasoning_tokens")
        self.mem.add_reasoning("".join(self.thought), message=reply_id, asked=self.user_id, effort=self.effort,
                               seconds=seconds, tokens=tokens)
        self.thought_saved = True


def combined_usage(usages):
    """The token counts of several rounds of one reply, added up."""
    if len(usages) == 1:
        return usages[0]
    out = {}
    for u in usages:
        for k, v in u.items():
            if isinstance(v, (int, float)):
                out[k] = out.get(k, 0) + v
            elif isinstance(v, dict):
                inner = out.setdefault(k, {})
                for kk, vv in v.items():
                    if isinstance(vv, (int, float)):
                        inner[kk] = inner.get(kk, 0) + vv
    return out


class Rounds:
    """Her reply's stream across tool rounds, looking like one stream to whoever reads it (the page, voice).

    She answers; if she calls a tool (the calendar, a thread), its words so far and the call are kept, code carries the
    call out through the one door, an event line tells the page what changed ({"avy": {"did": [...]}}), and a new
    request continues her reply with the result in front of her. At most instruments.MAX_ROUNDS rounds; the last one
    offers no tools, so it always ends in words. Only the final round's [DONE] is passed on."""

    def __init__(self, turn, first):
        self.turn, self.upstream = turn, first

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        try:
            self.upstream.close()
        except Exception:
            pass

    def __iter__(self):
        turn, messages = self.turn, list(self.turn.messages)
        for round_no in range(HANDS_ROUNDS + 1):
            calls, content, reasoning = {}, [], []
            # Every yield in this generator has to sit at the top level of the loop. If the model's lines were
            # forwarded from inside a `with`, then the approval card yielded further down (when a tool waits for his
            # OK) would be swallowed by that block and never reach the page, and the tool would wait out the whole
            # five-minute approval timeout. So the stream is closed by hand instead of by a `with`.
            upstream = self.upstream
            if upstream is None:
                break
            try:
                for line in upstream:
                    raw = line.decode(errors="replace").strip() if isinstance(line, bytes) else line.strip()
                    if raw == "data: [DONE]":
                        break
                    if raw.startswith("data:"):
                        try:
                            chunk = json.loads(raw[5:])
                        except json.JSONDecodeError:
                            chunk = {}
                        for choice in chunk.get("choices") or []:
                            delta = choice.get("delta") or {}
                            content.append(delta.get("content") or "")
                            reasoning.append(delta.get("reasoning_content") or "")
                            for tc in delta.get("tool_calls") or []:
                                c = calls.setdefault(tc.get("index", 0), {"id": "", "type": "function",
                                                                          "function": {"name": "", "arguments": ""}})
                                c["id"] = tc.get("id") or c["id"]
                                c["function"]["name"] += (tc.get("function") or {}).get("name") or ""
                                c["function"]["arguments"] += (tc.get("function") or {}).get("arguments") or ""
                    yield line
            finally:
                try:
                    upstream.close()
                except Exception:
                    pass
            if not calls:
                break
            told, did = [], []
            for c in [calls[i] for i in sorted(calls)]:
                try:
                    args = json.loads(c["function"]["arguments"] or "{}")
                except json.JSONDecodeError:
                    args = None
                name, started, box = c["function"]["name"], time.time(), {}
                work = threading.Thread(target=lambda: box.update(out=act(turn, name, args)), daemon=True)
                work.start()
                while work.is_alive():                      # a risky command waits for his OK: the card goes to the page
                    try:
                        ask = turn.asks.get(timeout=0.25)
                    except queue.Empty:
                        continue
                    yield f"data: {json.dumps({'avy': {'ask': ask}})}\n\n".encode()
                work.join()
                answer, line = box.get("out") or ("That tool didn't finish.", None)
                turn.mem.add_action(turn.user_id, name, args, answer, line, round(time.time() - started, 2))
                told.append({"role": "tool", "tool_call_id": c["id"] or f"call{len(told)}", "content": answer})
                if line:
                    did.append(line)
                    step = {"tool": name, "line": line, "out": answer[:700], "seconds": round(time.time() - started, 1)}
                    yield f"data: {json.dumps({'avy': {'step': step}})}\n\n".encode()
            if did:
                turn.did += did
                yield f"data: {json.dumps({'avy': {'did': did}})}\n\n".encode()
            if "".join(content).strip():               # words before the tool call: keep the next round's words apart from them
                yield f"data: {json.dumps({'choices': [{'index': 0, 'delta': {'content': chr(10) + chr(10)}}]})}\n\n".encode()
            messages += [{"role": "assistant", "content": "".join(content), "reasoning_content": "".join(reasoning),
                          "tool_calls": [calls[i] for i in sorted(calls)]}] + told
            rounds = HANDS_ROUNDS if turn.hands != "off" else instruments.MAX_ROUNDS
            # The stop gate. A turn that made or changed something and then reached for its summary without ever looking
            # at the result is the failure mode that reads as "done" and isn't (IMPROVE-NOTES §6b). Hermes nudges once
            # rather than accepting that stop; so does this. It is a nudge, not a refusal: she can say why not and stop.
            if round_no + 1 > rounds and turn.unchecked_work() and turn.nudges < 1:
                turn.nudges += 1
                messages.append({"role": "user", "content":
                    "Before you wrap this up: you " + turn.unchecked_work() + " in this reply and haven't looked at the "
                    "result. Read it back, or open it with `look` if it's something he'll see, then say what you found. "
                    "If you genuinely can't check it, say that plainly instead."})
                self.upstream = ask_model(messages, turn.tools, "auto")
                continue
            if round_no + 1 > rounds:
                break
            self.upstream = ask_model(messages, turn.tools, "none" if round_no + 1 >= rounds else "auto")
        yield b"data: [DONE]\n\n"


import queue
import threading
import time
import threading as _threading
_KEEPING = _threading.Lock()
HANDS_ROUNDS = 30          # tool rounds in one reply when she has hands, at most (the last offers no tools: it ends in words)
TURNS = {}                 # the turn that's answering now, by its approval ids, so /api/approve finds it


def act(turn, name, args):
    """Carry out one tool call for a turn: her instruments (calendar, threads), her hands (hands.py), or a toolbox
    (connectors.py: open_toolbox, then toolbox__tool). Records what she wrote and what she looked at, for the
    stop gate (Turn.unchecked_work)."""
    a = args if isinstance(args, dict) else {}
    if name in ("write_file", "edit_file", "append_file") and a.get("path"):
        turn.touched.append(str(a["path"]))                       # what she made: must be looked at before "done"
    if name == "look" and a.get("target"):
        turn.checked.append(str(a["target"]))
    if name == "read_file" and a.get("path"):
        turn.checked.append(str(a["path"]))
    if name in instruments.NAMES:
        return instruments.use(turn.mem, name, args, source=turn.user_id)
    if name in hands.NAMES and turn.hands != "off":
        hands.HOOKS["approve"] = turn.approve
        return hands.use(name, args, turn.hands)
    if name in selfcode.NAMES and turn.hands != "off":
        selfcode.HOOKS["approve"] = turn.approve
        return selfcode.use(name, args, turn.hands)
    if name == "graph_look":
        # He'll reach for query/node/handle/kind interchangeably. Refusing the call costs the whole answer (measured:
        # tension and multi-hop scored 0% and 12% under her own loop purely because the argument was named `query`),
        # so any of them starts at the root and the value is passed on as a hint instead of being dropped.
        args = args or {}
        handle = args.get("handle") or args.get("node") or args.get("query") or args.get("name") or "avy"
        shown = atlas.look(MEMORIES["main"], handle)
        hint = args.get("query")
        if hint and handle != hint:
            shown = f"(Nothing in the graph is named {hint!r}, so this is the root. Follow the handles below.)\n" + shown
        return shown, f"looked at {handle} in her graph"
    hub = connectors.HUB
    if hub and turn.hands != "off" and name == "open_toolbox":
        box = (args or {}).get("name")
        tools, problem = hub.open(box)
        if problem:
            return f"The {box} toolbox couldn't open: {problem}. Do without it, or tell him what's missing.", f"couldn't open {box}"
        known = {t["function"]["name"] for t in turn.tools or []}
        turn.tools = (turn.tools or []) + [t for t in hub.tools_of(box) if t["function"]["name"] not in known]
        return (f"The {box} toolbox is open; its tools are yours for the rest of this reply (named {box}__...): "
                + ", ".join(t["name"] for t in tools) + "."), f"opened the {box}"
    if hub and turn.hands != "off" and "__" in name:
        box, tool = name.split("__", 1)
        if hub.needs_ok(box, tool) and turn.hands != "trusted":
            detail = f"{box}: {tool} " + json.dumps(args, ensure_ascii=False)[:160]
            if not turn.approve({"kind": "toolbox", "detail": detail, "why": "acts for you in the " + box + " (typing, forms, uploads, scripts)"}):
                return f"Not done: he didn't approve {tool}. Say what you wanted to do and why, and let him decide.", f"{box} · {tool}: not approved"
        out = hub.call(box, tool, args)
        short = next((str(v) for v in (args or {}).values() if isinstance(v, (str, int, float))), "")
        return out, f"{box} · {tool.replace(box + '_', '')} {hands.clip_line(short, 60)}".rstrip()
    return f"There's no tool called {name} right now.", None


def toolbox_lines():
    """Her toolboxes (connectors), one line each, for her instructions; empty when there are none."""
    hub = connectors.HUB
    if not hub or not hub.boxes:
        return ""
    return ("\n- Toolboxes (connectors) others built for you, opened with open_toolbox when a task needs one (each comes with "
            "its own tools and their instructions):\n" + hub.index())


def jobs_note():
    """Background jobs, for the desk: what's running and what ended (code keeps these books, not her)."""
    if not hands.JOBS:
        return ""
    lines = []
    for j in list(hands.JOBS.values())[-8:]:
        v = hands.job_view(j)
        state = f"ended, exit {v['code']}" if v["done"] else "running"
        lines.append(f"- {v['id']} [{state}, {round(v['seconds'] / 60, 1)} min] {v['command'][:90]}" + (f" (th{v['thread']})" if v["thread"] else ""))
    return "Background jobs (from your terminal):\n" + "\n".join(lines)


def on_job_finished(job):
    """A background job ended: code writes it onto the thread waiting on it (so picking the thread up starts from the
    result), the page hears about it, and (with /proactive: on) she picks that thread up herself: an interrupt."""
    main = MEMORIES["main"]
    th = main.thread(job["thread"]) if job.get("thread") and main else None
    if th:
        note = f"{job['id']} ended (exit {job['code']}) after {round(job['seconds'] / 60, 1)} min: {job['command'][:100]}; log {job['log']}"
        main.apply({"op": "thread", "chain": th["chain"], "add_insights": [note], "status": "active",
                    "waiting": "" if job["id"] in (th["waiting"] or "") else th["waiting"], "by": "code",
                    "why": f"background job {job['id']} ended"})
    worker.tell({"finished": job})
    if current_settings()["proactive"] == "on" and not MEMORIES["incognito"]:
        threading.Thread(target=interrupt_after, args=(job, th), daemon=True).start()


IN_FLIGHT = {"turns": 0}          # replies being answered right now (an interrupt waits for them)


def interrupt_after(job, th):
    """Wait until no reply is in progress, then, unless she's already read how the job ended (she waited on it, or
    checked it), pick its thread up herself."""
    time.sleep(8)
    end = time.time() + 600
    while IN_FLIGHT["turns"] > 0 and time.time() < end:
        time.sleep(2)
    if (hands.JOBS.get(job["id"]) or {}).get("seen"):
        return
    try:
        tail = hands.job_view(hands.JOBS[job["id"]], tail=1500).get("output", "")
    except (KeyError, OSError):
        tail = ""
    where = (f"for th{th['chain']} \"{th['title']}\"" if th else "(no thread was attached to it)")
    speak_first(f"(Not a message from {memory.NAME}. Background job {job['id']} you started {where} just ended: exit {job['code']} "
                f"after {round(job['seconds'] / 60, 1)} min. Command: {job['command'][:200]}. The end of its output:\n{tail}\n"
                "Pick the thread up exactly where you left it (its frontier is on your desk): check the result against what you "
                "expected and the rule you set, update the thread, and tell him in a few lines what it means and what's next. "
                "Don't greet him; he'll read this when he's back.)", {"kind": "job", "job": job["id"], "thread": job.get("thread")})


_SPEAKING = threading.Lock()


def speak_first(prompt, event):
    """She speaks without being spoken to: an event turn (the prompt is the event, never saved as his words); her reply is
    saved with meta.event and the page is told to show it. One at a time, in the background."""
    def run():
        with _SPEAKING:
            mem = MEMORIES["main"]
            if not mem or mem.closed or MEMORIES["incognito"]:
                return
            try:
                turn = Turn(prompt, "text", event=event)
                turn.approve = lambda request: False          # nobody's there to say yes: risky things wait for him
                reply, usage = "", None
                with turn.ask() as upstream:
                    for line in upstream:
                        if (line if isinstance(line, bytes) else line.encode()).strip() == b"data: [DONE]":
                            break
                        words, counts = turn.stream(line)
                        reply += words
                        usage = counts or usage
                rid = turn.finish(reply, usage)
                if rid:
                    worker.tell({"proactive": {"id": rid, "event": event}})
            except Exception as e:
                print(f"She tried to speak first ({event.get('kind')}) and couldn't: {e}")
    threading.Thread(target=run, daemon=True).start()


DUE_LEAD = {"event": 60, "deadline": 0, "reminder": 0, "task": 0}     # minutes before: an event an hour ahead; the rest at their time


def tick():
    """Every minute: anything on the calendar that's come due (a reminder at its time, a timed event an hour before, a
    deadline at 9 AM on its day), each once. The page hears; with /proactive: on she says it herself."""
    from datetime import timedelta as _td
    while True:
        time.sleep(60)
        try:
            mem = MEMORIES["main"]
            if not mem or mem.closed:
                continue
            now = memory.now()
            for t in mem.timeline_heads():
                if t["status"] != "planned" or not t["start"]:
                    continue
                found = memory.parse_when(t["start"])
                if not found:
                    continue
                at, timed = found
                due = (at - _td(minutes=DUE_LEAD.get(t["kind"], 0))) if timed else at.replace(hour=9, minute=0)
                key = f"due:t{t['chain']}:v{t['version']}"
                if not (due <= now < due + _td(hours=2)) or mem.mark(key):
                    continue
                mem.set_mark(key, now.isoformat(timespec="seconds"))
                worker.tell({"due": {"chain": t["chain"], "title": t["title"], "kind": t["kind"], "start": t["start"]}})
                if current_settings()["proactive"] == "on" and not MEMORIES["incognito"]:
                    lead = {"event": "It starts in about an hour", "reminder": "He asked you to remind him of this now",
                            "deadline": "It's due today"}.get(t["kind"], "It's due now")
                    speak_first(f"(Not a message from {memory.NAME}. On your calendar: t{t['chain']} \"{t['title']}\" ({t['kind']}, "
                                f"{memory.say_when(t['start'])}). {lead}. Tell him in a line, the way a friend would; add only what "
                                "genuinely helps (where, what to bring, a conflict). No greeting.)", {"kind": "due", "chain": t["chain"]})
        except Exception as e:
            print(f"The calendar's ticker hit a problem ({e}); it carries on.")


def keep_after(mem, last):
    """The keeper (mind/persona.py) reads the newest exchange into the persona graph, in the background, one at a time.
    It writes to the main memory only (an incognito conversation keeps nothing)."""
    def run():
        with _KEEPING:
            try:
                if not mem.closed:
                    worker.run(mem, persona_jobs.Keep(mem, last))
            except Exception as e:
                print(f"The keeper hit a problem ({e}); the conversation carries on.")
    _threading.Thread(target=run, daemon=True).start()


FILE_CHARS = 240_000     # all the files in one briefing together, at most (about 60,000 tokens)
MAX_PICTURES = 16        # pictures and video frames in one briefing, at most


def briefing(shown, memory_note, text, incognito=False, core=True, attached=(), tools=True):
    """What the model sees, in this order: instructions and core (same every time, so it's cached),
    the newest messages word for word, the memory note for this message, then your message.
    Files go with the message they came with: the newest message's first, then earlier ones in the
    window, newest first, while there's room (FILE_CHARS, MAX_PICTURES).
    tools says whether this request actually carries tool schemas: the instructions must not promise tools it doesn't."""
    messages = [{"role": "system", "content": system_prompt(incognito, core, tools)}]
    previous_at = None
    for m in shown:
        content = m["text"]
        at = datetime.fromisoformat(m["at"])
        if m["role"] == "user" and (previous_at is None or (at - previous_at).total_seconds() > 3600):
            content = f"({memory.when(m['at'])}) {content}"     # a new sitting: say when it was
        if m["meta"].get("cut"):
            content += " [he cut you off here]"
        messages.append({"role": m["role"], "content": content})
        previous_at = at
    room = {"chars": FILE_CHARS, "pictures": MAX_PICTURES}
    newest = with_files(text, attached, room)
    for message, m in reversed(list(zip(messages[1:], shown))):
        kept = [f for f in m["meta"].get("files") or [] if isinstance(f, dict) and f.get("id")]   # imported ones are only names
        if kept:
            message["content"] = with_files(message["content"], kept, room)
    messages.append({"role": "system", "content": memory_note})
    messages.append({"role": "user", "content": newest})
    return messages


def with_files(content, records, room):
    """A message's text with its files added (and its pictures as image parts), using up room."""
    if not records:
        return content
    blocks, pictures = files.for_model(records, file_folders(), max(0, room["chars"]), pictures=room["pictures"] > 0)
    pictures = pictures[:max(0, room["pictures"])]
    room["chars"] -= len(blocks)
    room["pictures"] -= len(pictures)
    text = (content + "\n\n" if content else "") + "[attached]\n" + blocks
    if not pictures:
        return text
    return [{"type": "text", "text": text}] + [{"type": "image_url", "image_url": {"url": url}} for url in pictures]


stream_text = luminal.stream_text     # the words and token counts in one line of a streamed reply


# ---------------------------------------------------------------------------
# 7. The web server: one page, a few small endpoints
# ---------------------------------------------------------------------------

def number(query, name):
    try:
        return int(query.get(name, [""])[0])
    except ValueError:
        return None


def memory_for(query):
    """?memory=main or ?memory=incognito; without it, the conversation you're in now."""
    name = query.get("memory", [None])[0]
    return talking_to() if name is None else MEMORIES.get(name)


MEMORY_VIEWS = ("/api/log", "/api/memory", "/api/node", "/api/edge", "/api/episode", "/api/run", "/api/recall",
                "/api/search", "/api/graph", "/api/journal", "/api/health", "/api/library", "/api/source", "/api/passage")


class Handler(BaseHTTPRequestHandler):

    def signed_in(self):
        if not password():
            return True
        cookies = dict(c.strip().split("=", 1) for c in (self.headers.get("Cookie") or "").split(";") if "=" in c)
        return cookies.get("avy_auth") == auth_token()

    def do_GET(self):
        url = urllib.parse.urlparse(self.path)
        q = urllib.parse.parse_qs(url.query)
        if not self.signed_in():
            if url.path == "/":
                body = LOGIN_PAGE.encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                return self.wfile.write(body)
            return self.send_json(401, {"error": "Sign in first (reload the page)."})
        if url.path == "/api/chats":
            return self.send_json(200, {"conversations": CHATS.list()})
        if url.path.startswith("/api/chats/"):
            c = CHATS.get(int(url.path.rsplit("/", 1)[-1] or 0)) if url.path.rsplit("/", 1)[-1].isdigit() else None
            return self.send_json(200 if c else 404, c or {"error": "No such conversation."})
        if url.path == "/":
            self.send_page()
        elif url.path == "/api/status":
            self.send_json(200, key_status())
        elif url.path == "/api/settings":
            self.send_json(200, settings_payload())
        elif url.path == "/api/events":
            self.events()
        # --- files you attached, downloads and exports ---
        elif url.path == "/api/files":
            self.send_json(200, {"files": files.listing(file_folders())})
        elif url.path.startswith("/api/files/"):
            self.file_view(url.path.split("/")[3:], q)
        elif url.path == "/api/export":
            self.export(q)
        elif url.path == "/api/import":
            self.send_json(200, IMPORT)
        elif url.path == "/api/glass":
            self.send_json(200, glass())
        elif url.path == "/api/connectors":          # her toolboxes: what's configured, what's running
            self.send_json(200, {"connectors": connectors.HUB.status() if connectors.HUB else [], "config": str(connectors.CONFIG)})
        elif url.path == "/api/desk":                # the desk: the persona graph, the calendar, the threads (?node=12: one node's history)
            main = MEMORIES["main"]
            n = number(q, "node")
            if n:
                node = main.persona_node(n)
                return self.send_found(node and {**node, "versions": main.persona_versions(n), "links": main.persona_links(n)})
            self.send_json(200, {**main.desk_data(), "jobs": [hands.job_view(j) for j in hands.JOBS.values()],
                                 "connectors": connectors.HUB.status() if connectors.HUB else []})
        # --- memory, for the chat history, the inspector and the graph (?memory=main|incognito) ---
        elif url.path in MEMORY_VIEWS:
            mem = memory_for(q)
            if not mem:
                return self.send_json(404, {"error": "That memory isn't open (the incognito conversation has ended)."})
            n = number(q, "id") or 0
            if url.path == "/api/log":            # ?before=41 or ?after=41, &limit=60
                self.send_json(200, {"messages": mem.log_slice(before=number(q, "before"), after=number(q, "after"),
                                                               limit=min(number(q, "limit") or 60, 200)),
                                     "last": mem.last_id(), "memory": mem.name})
            elif url.path == "/api/memory":
                full = q.get("episodes", ["1"])[0] != "0"
                last = mem.row("SELECT metrics FROM health ORDER BY id DESC LIMIT 1")
                self.send_json(200, {"stats": mem.stats(), "episodes": mem.episodes_list() if full else [],
                                     "reflections": mem.runs_list(["think", "check", "dream"], 30) if full else [],
                                     "health": json.loads(last["metrics"]) if last else None})
            elif url.path == "/api/node":
                self.send_found(mem.node_record(n, number(q, "version")))
            elif url.path == "/api/edge":
                self.send_found(mem.edge_record(n))
            elif url.path == "/api/episode":
                self.send_found(mem.episode_record(n))
            elif url.path == "/api/run":
                self.send_found(mem.run_record(n))
            elif url.path == "/api/recall":
                self.send_found(mem.recall_record(n))
            elif url.path == "/api/graph":          # ?as_of=2026-09-14T10:00:00-04:00: memory as it stood then
                as_of = (q.get("as_of") or [None])[0]
                try:
                    self.send_json(200, mem.graph_data(as_of or None))
                except ValueError:
                    self.send_json(400, {"error": "as_of should be a time like 2026-09-14T10:00:00-04:00"})
            elif url.path == "/api/journal":
                self.send_json(200, {"journal": mem.journal_list(min(number(q, "limit") or 200, 1000))})
            elif url.path == "/api/health":
                self.send_json(200, {"now": memory.health(mem), "history": [
                    {"at": r["at"], **json.loads(r["metrics"])} for r in mem.rows("SELECT * FROM health ORDER BY id")]})
            elif url.path == "/api/library":     # everything he added, and what the intake is doing
                self.send_json(200, {"sources": mem.sources_list(), "stats": mem.library_stats(), "intake": INTAKE.status(),
                                     "memory": mem.name})
            elif url.path == "/api/source":
                found = mem.source(n)
                if found:
                    found["passages_shown"] = mem.passages_of(n, number(q, "after") or 0, min(number(q, "limit") or 40, 200))
                self.send_found(found)
            elif url.path == "/api/passage":
                p = mem.passage(n)
                if p:
                    p["before"] = mem.row("SELECT id, part FROM passages WHERE source = ? AND seq = ?", p["source"], p["seq"] - 1)
                    p["after"] = mem.row("SELECT id, part FROM passages WHERE source = ? AND seq = ?", p["source"], p["seq"] + 1)
                self.send_found(p)
            else:
                self.send_json(200, mem.find(q.get("q", [""])[0]))
        else:
            self.send_json(404, {"error": "Not found"})

    def do_POST(self):
        if not self.from_avy_page():
            return self.send_json(403, {"error": "Requests are only accepted from Avy's own page."})
        if self.path == "/api/login":
            given = str(self.read_json().get("password") or "")
            if not password() or hmac.compare_digest(given, password()):
                self.send_response(200)
                self.send_header("Set-Cookie", f"avy_auth={auth_token()}; Path=/; Max-Age=31536000; HttpOnly; SameSite=Lax"
                                 + ("; Secure" if (self.headers.get("X-Forwarded-Proto") or "") == "https" else ""))
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", "2")
                self.end_headers()
                return self.wfile.write(b"{}")
            time.sleep(1)
            return self.send_json(403, {"error": "Wrong password."})
        if not self.signed_in():
            return self.send_json(401, {"error": "Sign in first (reload the page)."})
        if self.path == "/api/chats":
            body = self.read_json()
            action, cid = body.get("action"), body.get("id")
            if action == "new":
                return self.send_json(200, CHATS.new())
            if action == "rename" and cid:
                CHATS.rename(int(cid), body.get("title") or "")
            elif action == "delete" and cid:
                CHATS.delete(int(cid))
            return self.send_json(200, {"conversations": CHATS.list()})
        if self.path == "/api/plain":
            return self.plain_chat()
        if self.path == "/api/keys":
            self.save_keys()
        elif self.path == "/api/settings":
            body = self.read_json()
            problem = change_setting(body.get("name"), body.get("value"))
            self.send_json(400 if problem else 200, {"error": problem} if problem else settings_payload())
        elif self.path == "/api/chat":
            self.chat()
        elif self.path == "/api/files":
            self.upload()
        elif self.path == "/api/library/upload":          # one file of a folder you're adding
            self.library_upload()
        elif self.path == "/api/library/folder":          # ...and the folder is complete: read it into the library
            body = self.read_json()
            batch = str(body.get("batch") or "")
            folder = LIBRARY_DIR / batch
            if not re.fullmatch(r"b[0-9a-z-]{6,40}", batch) or not folder.exists():
                return self.send_json(400, {"error": "That folder didn't arrive. Add it again."})
            job = INTAKE.add_tree(talking_to(), folder, str(body.get("name") or "folder")[:120], came=f"folder {batch}")
            self.send_json(200, {"job": job})
        elif self.path == "/api/library/add":             # an attached file, added to the library by hand
            fid = str(self.read_json().get("file") or "")
            path, record = files.original(fid, file_folders())
            if not record:
                return self.send_json(404, {"error": "That file isn't here."})
            job = INTAKE.add_file(talking_to(), path, record["name"], came=fid, record=record, home=path.parent)
            self.send_json(200, {"job": job})
        elif self.path == "/api/intake":                  # {"pause": true|false} or {"cancel": job id}
            body = self.read_json()
            if "pause" in body:
                INTAKE.pause(bool(body["pause"]))
            if body.get("cancel"):
                INTAKE.cancel(int(body["cancel"]))
            self.send_json(200, INTAKE.status())
        elif self.path == "/api/dream":                   # {"action": "start", hours, max_dollars, effort} or {"action": "stop"}
            body = self.read_json()
            if not DREAM:
                return self.send_json(400, {"error": "Dreaming isn't available."})
            if MEMORIES["incognito"] and body.get("action") == "start":
                return self.send_json(400, {"error": "End the incognito conversation first: she dreams about the memory that's kept."})
            problem = DREAM.stop() if body.get("action") == "stop" else DREAM.start(
                float(body.get("hours") or 8), float(body.get("max_dollars") or 10), luminal.effort_level(body.get("effort") or "max"))
            self.send_json(400 if problem else 200, {"error": problem} if problem else DREAM.status())
        elif self.path == "/api/history":                 # the Claude history's build: {"action": plan|run|stop, ...}
            body = self.read_json()
            problem = history_action(body)
            self.send_json(400 if problem else 200, {"error": problem} if problem else history_status())
        elif self.path.startswith("/api/files/") and self.path.endswith("/import"):
            problem = start_import(self.path.split("/")[3])
            self.send_json(400 if problem else 200, {"error": problem} if problem else IMPORT)
        elif self.path in ("/api/index", "/api/reflect") and talking_to().waiting_import():
            n = talking_to().waiting_import()
            self.send_json(409, {"error": f"{n:,} imported messages are waiting to be written. That's the import's own run, "
                                          "started by you: python3 tools/claude_import.py run (see docs/IMPORT.md)."})
        elif self.path == "/api/index":         # /index: write what's waiting now, even a short stretch
            mem = talking_to()
            runs = worker.write_due(mem, force=True)
            self.send_json(200, {"runs": runs, "stats": mem.stats()})
        elif self.path == "/api/reflect":       # /reflect: think now, instead of waiting for a quiet spell
            mem = talking_to()
            worker.write_due(mem, force=True)
            runs = worker.reflect_now(mem, budget=10_000)
            if mem is MEMORIES["main"] and current_settings()["persona"] == "on":
                runs += worker.reflect_on_manner(mem, force=True)
            self.send_json(200, {"runs": runs, "stats": mem.stats()})
        elif self.path == "/api/approve":       # his answer to a risky action she wants to take: {"id", "allow"}
            body = self.read_json()
            turn = TURNS.get(str(body.get("id")))
            if not turn:
                return self.send_json(404, {"error": "That request isn't waiting any more."})
            answer = turn.answers.get(str(body["id"]))
            answer["allow"] = bool(body.get("allow"))
            answer["event"].set()
            self.send_json(200, {"ok": True})
        elif self.path == "/api/desk":          # his own edit on the desk: {"op": "timeline" | "thread" | "persona", ...}
            body = self.read_json()
            if body.get("op") not in ("timeline", "thread", "persona", "persona_link"):
                return self.send_json(400, {"error": "That isn't something the desk can change."})
            result = MEMORIES["main"].apply({**body, "by": "him", "why": body.get("why") or "edited on the desk"})
            if not result["applied"]:
                return self.send_json(400, {"error": result["why"]})
            self.send_json(200, {"result": result, "desk": MEMORIES["main"].desk_data()})
        elif self.path == "/api/incognito":     # {"on": true} starts one; {"on": false} ends and deletes it
            start_incognito() if self.read_json().get("on") else end_incognito()
            self.send_json(200, {"incognito": MEMORIES["incognito"] is not None, "stats": talking_to().stats()})
        else:
            self.send_json(404, {"error": "Not found"})

    # --- endpoints ---

    def save_keys(self):
        body = self.read_json()
        env = read_env()
        for name in KEYS:
            value = "".join(str(body.get(name, "")).split())  # strip spaces and newlines
            if value:
                env[name] = value
                os.environ[name] = value
        write_env(env)
        self.send_json(200, key_status())

    def chat(self):
        body = self.read_json()
        text = str(body.get("text") or "").strip()
        attached = []
        for fid in body.get("files") or []:
            record = files.wait(fid, file_folders(), seconds=600)      # still being read: wait for it
            if not record:
                return self.send_json(400, {"error": "One of the attached files isn't here any more. Attach it again."})
            attached.append(record)
        if not text and not attached:
            return self.send_json(400, {"error": "There's nothing to send."})
        # The stream starts right away, so the page can show Avy searching her memory before she answers.
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        try:
            turn = Turn(text, "text", progress=lambda e: self.event({"avy": {"searching": e}}), attached=attached)
            upstream = turn.ask()
        except FriendlyError as e:
            return self.event({"avy": {"error": e.message}})
        except (BrokenPipeError, ConnectionResetError):
            return
        except Exception as e:
            print(f"A turn failed: {e!r}")
            return self.event({"avy": {"error": f"Something went wrong preparing the reply ({e})."}})

        # Pass the model's stream through to the page line by line, keeping what got there.
        reply, usage, cut = "", None, False
        try:
            self.event({"avy": {"turn": turn.summary()}})
            with upstream:
                for line in upstream:
                    if line.strip() == b"data: [DONE]":
                        break
                    self.wfile.write(line)
                    self.wfile.flush()
                    words, counts = turn.stream(line)      # keeps her thinking too, to save with the reply
                    reply += words
                    usage = counts or usage
        except (BrokenPipeError, ConnectionResetError):
            cut = True                     # you pressed Stop or closed the tab
        except OSError:
            cut = True                     # the connection dropped partway through
        saved = turn.finish(reply, usage, cut)
        if not cut:
            try:
                self.event({"avy": {"saved": saved, "unseen": turn.unseen_in(reply)}})
                self.wfile.write(b"data: [DONE]\n\n")
            except OSError:
                pass

    def plain_chat(self):
        """Plain chat mode: one message into one conversation, the model's stream straight back. No memory, no tools."""
        body = self.read_json()
        text, cid = str(body.get("text") or "").strip(), body.get("conversation")
        convo = CHATS.get(int(cid)) if cid else CHATS.new()
        if not convo:
            return self.send_json(404, {"error": "That conversation is gone. Start a new one."})
        if not text:
            return self.send_json(400, {"error": "There's nothing to send."})
        cid = convo["id"]
        CHATS.add(cid, "user", text)
        window = int(current_settings()["chatwindow"].rstrip("k")) * 1000
        messages, dropped = CHATS.context(cid, window)
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.event({"avy": {"conversation": CHATS.get(cid) and {k: v for k, v in CHATS.get(cid).items() if k != "messages"},
                            "dropped": dropped}})
        try:
            upstream = ask_model(messages)
        except FriendlyError as e:
            return self.event({"avy": {"error": e.message}})
        except Exception as e:
            return self.event({"avy": {"error": f"Couldn't reach the model ({e})."}})
        reply, thought, cut = "", "", False
        try:
            with upstream:
                for line in upstream:
                    if line.strip() == b"data: [DONE]":
                        break
                    self.wfile.write(line)
                    self.wfile.flush()
                    words, thinking, usage = luminal.stream_parts(line)
                    reply += words or ""
                    thought += thinking or ""
        except OSError:
            cut = True
        if reply.strip():
            CHATS.add(cid, "assistant", reply, thought or None)
        if not cut:
            try:
                self.wfile.write(b"data: [DONE]\n\n")
            except OSError:
                pass

    def library_upload(self):
        """One file of a folder being added to memory: X-Batch names the folder's upload, X-File-Path where the file
        sits in it. Kept as it came under data/library/<batch>/; read once the whole folder has arrived."""
        length = int(self.headers.get("Content-Length") or 0)
        batch = str(self.headers.get("X-Batch") or "")
        if not re.fullmatch(r"b[0-9a-z-]{6,40}", batch):
            return self.send_json(400, {"error": "A folder upload needs its batch name."})
        if length > files.MAX_BYTES:
            return self.send_json(413, {"error": f"That file is over {files.fmt_size(files.MAX_BYTES)}."})
        rel = safe_relative(urllib.parse.unquote(self.headers.get("X-File-Path") or "file"))
        target = (LIBRARY_DIR / batch / rel)
        target.parent.mkdir(parents=True, exist_ok=True)
        left = length
        with open(target, "wb") as out:
            while left > 0:
                chunk = self.rfile.read(min(1 << 20, left))
                if not chunk:
                    break
                out.write(chunk)
                left -= len(chunk)
        self.send_json(200, {"path": rel, "size": length - left})

    def upload(self):
        """A file, as the request's body. Any kind, any size up to files.MAX_BYTES."""
        length = int(self.headers.get("Content-Length") or 0)
        name = urllib.parse.unquote(self.headers.get("X-File-Name") or "file")
        if length <= 0:
            return self.send_json(400, {"error": "That file is empty."})
        if length > files.MAX_BYTES:
            return self.send_json(413, {"error": f"That file is over {files.fmt_size(files.MAX_BYTES)}."})
        mime = (self.headers.get("Content-Type") or "").split(";")[0].strip()
        self.send_json(200, files.save(self.rfile, length, name, "" if mime == "application/octet-stream" else mime, files_folder()))

    def file_view(self, parts, q):
        """/api/files/<id> (its record), .../download (?inline=1 to view it), .../text (what Avy read)."""
        fid, what = parts[0], (parts[1] if len(parts) > 1 else "")
        path, record = files.original(fid, file_folders())
        if not record:
            return self.send_json(404, {"error": "That file isn't here."})
        if what == "":
            self.send_json(200, record)
        elif what == "download":
            inline = q.get("inline", ["0"])[0] == "1"
            self.send_download(path, record["name"], record.get("mime") or "application/octet-stream", inline)
        elif what == "text":
            body = files.text_of(fid, file_folders()).encode()
            self.send_download_bytes(body, record["name"] + ".txt", "text/plain; charset=utf-8", inline=True)
        else:
            self.send_json(404, {"error": "Not found"})

    def export(self, q):
        """/api/export?what=conversation&format=md|json, or what=memory (the knowledge and network, JSON)."""
        mem = memory_for(q)
        if not mem:
            return self.send_json(404, {"error": "That memory isn't open."})
        what, fmt = q.get("what", ["conversation"])[0], q.get("format", ["md"])[0]
        day = datetime.now().strftime("%Y-%m-%d")
        if what == "memory":
            body = json.dumps(export_memory(mem), indent=1, ensure_ascii=False).encode()
            return self.send_download_bytes(body, f"avy-memory-{mem.name}-{day}.json", "application/json")
        msgs = mem.messages_between(1, mem.last_id())
        if fmt == "json":
            for m in msgs:
                thought = mem.reasoning_of(m["id"]) if m["meta"].get("thought") else None
                if thought:
                    m["thinking"] = {k: thought[k] for k in ("text", "seconds", "effort", "tokens")}
            body = json.dumps({"exported": memory.stamp(), "memory": mem.name, "messages": msgs}, indent=1, ensure_ascii=False)
            return self.send_download_bytes(body.encode(), f"avy-conversation-{mem.name}-{day}.json", "application/json")
        self.send_download_bytes(conversation_markdown(mem, msgs).encode(), f"avy-conversation-{mem.name}-{day}.md",
                                 "text/markdown; charset=utf-8")

    def events(self):
        """What the mind is doing in the background, as it happens (for the page's live touches)."""
        import queue
        box = queue.Queue()
        worker.listeners.append(box.put)
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        try:
            self.event({"hello": True, "page": PAGE_VERSION})
            while True:
                try:
                    e = box.get(timeout=25)
                    self.event(e if any(k in e for k in ("intake", "dream", "history", "finished", "proactive", "due")) else {"mind": e})
                except queue.Empty:
                    self.wfile.write(b": still here\n\n")
                    self.wfile.flush()
        except OSError:
            pass
        finally:
            worker.listeners.remove(box.put)

    def event(self, data):
        self.wfile.write(f"data: {json.dumps(data)}\n\n".encode())
        self.wfile.flush()

    # --- helpers ---

    def from_avy_page(self):
        """Block other websites from using this server behind your back."""
        origin = self.headers.get("Origin")
        if origin is None or origin in (f"http://localhost:{PORT}", f"http://127.0.0.1:{PORT}"):
            return True
        host = self.headers.get("X-Forwarded-Host") or self.headers.get("Host") or ""
        return urllib.parse.urlparse(origin).netloc == host       # the page itself, reached through a tunnel

    def read_json(self):
        length = int(self.headers.get("Content-Length") or 0)
        try:
            return json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            return {}

    def send_found(self, data):
        self.send_json(200, data) if data else self.send_json(404, {"error": "Not found"})

    def send_json(self, status, data):
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_page(self):
        """The page, never cached, stamped with the version this server started with."""
        body = (HERE / "index.html").read_bytes().replace(
            b"</head>", f'<meta name="avy-page" content="{PAGE_VERSION}">\n</head>'.encode(), 1)
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_download(self, path, name, content_type, inline=False):
        """A file, streamed from disk (it can be big), saved under its own name unless inline."""
        size = path.stat().st_size
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(size))
        self.send_header("Content-Disposition", disposition(name, inline))
        self.send_header("X-Content-Type-Options", "nosniff")
        if inline:
            self.send_header("Content-Security-Policy", "sandbox")     # an uploaded web page can't run as Avy's page
        self.end_headers()
        with open(path, "rb") as f:
            shutil.copyfileobj(f, self.wfile, 1 << 20)

    def send_download_bytes(self, body, name, content_type, inline=False):
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Content-Disposition", disposition(name, inline))
        self.end_headers()
        self.wfile.write(body)

    def send_file(self, path, content_type):
        body = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        pass   # keep the terminal for things that matter


def disposition(name, inline=False):
    plain = "".join(c if 32 <= ord(c) < 127 and c not in '"\\' else "_" for c in name)
    return f'{"inline" if inline else "attachment"}; filename="{plain}"; filename*=UTF-8\'\'{urllib.parse.quote(name)}'


def conversation_markdown(mem, msgs):
    """The whole log as Markdown: a heading where each sitting (or imported conversation) begins."""
    if not msgs:
        return "# Avy: the conversation\n\nNothing's been said yet.\n"
    out = [f"# Avy: the conversation ({mem.name} memory)", "",
           f"Exported {memory.when(memory.stamp())}: {len(msgs):,} messages, "
           f"{memory.when(msgs[0]['at'])} to {memory.when(msgs[-1]['at'])}.", ""]
    previous = None
    for m in msgs:
        at, conv = datetime.fromisoformat(m["at"]), m["meta"].get("conversation")
        if previous is None or conv != previous[1] or (at - previous[0]).total_seconds() > 30 * 60:
            title = m["meta"].get("conversation_name")
            out += [f"## {at:%A, %b %d, %Y, %I:%M %p}" + (f": {title} (with Claude)" if title else ""), ""]
        previous = (at, conv)
        who = memory.who(m["role"], m.get("via"))
        out.append(f"**{who}** · {at:%I:%M %p}" + (" · spoken" if m.get("via") == "voice" else "")
                   + (" · cut off" if m["meta"].get("cut") else ""))
        thought = mem.reasoning_of(m["id"]) if m["meta"].get("thought") else None
        if thought:
            out += ["<details><summary>" + (f"thought for {thought['seconds']}s" if thought["seconds"] else "thought") + "</summary>",
                    "", thought["text"].strip(), "", "</details>", ""]
        if m["text"]:
            out.append(m["text"])
        names = [f["name"] if isinstance(f, dict) else f for f in m["meta"].get("files") or []]
        names += [a["name"] for a in m["meta"].get("attachments") or []]
        if names:
            out.append("*attached: " + ", ".join(names) + "*")
        out.append("")
    return "\n".join(out)


def export_memory(mem):
    """Everything memory knows, as data: nodes (with where each was said), connections, conversations."""
    nodes = []
    for n in mem.current_nodes():
        nodes.append({**mem.node_brief(n), "text": n["text"], "at": n["at"],
                      "evidence": [{"message": e["message"], "quote": e.get("quote")} for e in mem.evidence_of(n["id"])]})
    graph = mem.graph_data()
    return {"exported": memory.stamp(), "memory": mem.name, "stats": mem.stats(), "nodes": nodes,
            "connections": graph["edges"], "rests_on": graph["rests"],
            "conversations": [{k: e.get(k) for k in ("id", "headline", "first", "last", "at")} for e in mem.episodes_list(100_000)]}


# ---------------------------------------------------------------------------
# 8. Importing a Claude history from the page (the same as tools/claude_import.py import)
# ---------------------------------------------------------------------------

IMPORT = {"state": "idle"}      # what the page's import is doing: idle, reading, importing, done, failed


def start_import(fid):
    """Start importing an attached Claude export. Returns a problem, or None if it started."""
    path, record = files.original(fid, file_folders())
    if not record or record.get("kind") != "claude-export":
        return "That file isn't a Claude data export."
    if IMPORT["state"] in ("reading", "importing"):
        return "An import is already going."
    if MEMORIES["incognito"]:
        return "End the incognito conversation first: an import goes into a memory that's kept."
    import threading
    here = MEMORIES["main"].path.resolve() == CLAUDE_MEMORY.resolve()
    IMPORT.clear()
    IMPORT.update(state="reading", file=record["name"], target=str(CLAUDE_MEMORY), here=here, done=0, of=0, messages=0)
    threading.Thread(target=run_import, args=(path, here), daemon=True).start()
    return None


def run_import(path, here):
    """The imported history goes into its own memory file (data/memory-claude.db), so Avy's own log stays
    in time order (the import is older). If Avy is running on that file, it goes straight in."""
    sys.path.insert(0, str(HERE / "tools"))
    import claude_import
    try:
        convs, skipped = claude_import.read_all(path, progress=False)
        IMPORT.update(state="importing", of=len([c for c in convs if c.messages]))
        mem = MEMORIES["main"] if here else memory.Memory(CLAUDE_MEMORY)
        done = claude_import.import_conversations(mem, convs, say=lambda *a: None,
                                                  progress=lambda i, n, m: IMPORT.update(done=i, of=n, messages=m))
        IMPORT.update(state="done", added=done, waiting=mem.waiting_import(), total=mem.last_id())
        if not here:
            mem.close()
    except Exception as e:
        IMPORT.update(state="failed", problem=f"{type(e).__name__}: {e}"[:300])


# ---------------------------------------------------------------------------
# 8b. The library (anything you add becomes searchable memory: intake.py), and the looking glass
#     (one view of everything loading into memory and everything the mind is doing).
# ---------------------------------------------------------------------------

INTAKE = intake.Intake(tell=lambda event: worker.tell(event))
MIND = {"now": None, "recent": []}          # what the background mind is doing, as it tells us


def describe_picture(jpeg):
    """What's in a picture, in a few plain sentences, for the library (intake.py): the one brain looks once."""
    url = files.data_url(jpeg)
    reply = luminal.complete({"max_tokens": 500, "messages": [
        {"role": "system", "content": f"Describe this picture for {memory.NAME}'s memory, so it can be found later by what's in it. "
                                      "Two to four plain sentences: what it shows, any text in it (word for word), people, places, objects, "
                                      "numbers. No guessing beyond what's visible."},
        {"role": "user", "content": [{"type": "text", "text": "The picture:"}, {"type": "image_url", "image_url": {"url": url}}]}]})
    return reply["choices"][0]["message"].get("content") or ""


def on_file_read(home, record):
    """A file attached in the chat has been read: it joins the library of the memory it was attached in
    (an incognito conversation's own, deleted with it). Pictures are described once by the model so they can be
    found by what's in them; files with no words are skipped."""
    if record.get("status") != "ready" or record.get("kind") == "binary":
        return
    incog = MEMORIES["incognito"] and str(Path(home).resolve()).startswith(str(INCOGNITO_DIR.resolve()))
    mem = MEMORIES["incognito"] if incog else MEMORIES["main"]
    if mem:
        INTAKE.add_file(mem, Path(home) / record["name"], record["name"], came=record["id"], record=record, home=home)


def hear_mind(event):
    """Keep the mind's current job and its recent runs for the looking glass."""
    if "job" not in event:
        return
    if event.get("state") == "start":
        MIND["now"] = {**event, "since": datetime.now().astimezone().isoformat(timespec="seconds")}
    else:
        MIND["now"] = None
        MIND["recent"] = ([{**event, "at": datetime.now().astimezone().isoformat(timespec="seconds")}] + MIND["recent"])[:40]


def safe_relative(path):
    """A folder upload's relative path, made safe: no absolute paths, no '..', no hidden tricks."""
    parts = [files.safe_name(p) for p in str(path or "").replace("\\", "/").split("/") if p not in ("", ".", "..")]
    return "/".join(p for p in parts if p) or "file"


def glass():
    """Everything the looking glass shows, in one answer: what's loading into memory (and how long it'll take),
    what the mind is doing and has done, the state of memory, the Claude history's build, and what it costs."""
    mem = talking_to()
    today = memory.stamp()[:10]
    last_health = mem.row("SELECT metrics, at FROM health ORDER BY id DESC LIMIT 1")
    runs = mem.rows("SELECT id, job, at, status, attempts, seconds, cost, focus FROM runs ORDER BY id DESC LIMIT 30")
    by_job = mem.rows("SELECT job, COUNT(*) AS n, ROUND(COALESCE(SUM(cost), 0), 4) AS cost, "
                      "SUM(CASE WHEN status IN ('failed', 'error') THEN 1 ELSE 0 END) AS failed, ROUND(AVG(seconds), 1) AS seconds "
                      "FROM runs GROUP BY job ORDER BY n DESC")
    return {
        "at": memory.stamp(),
        "memory": {**mem.stats(), **{"library_" + k: v for k, v in mem.library_stats().items()}},
        "intake": INTAKE.status(),
        "sources": mem.sources_list(30),
        "mind": {"now": MIND["now"], "recent": MIND["recent"][:12], "runs": runs, "by_job": by_job,
                 "today": {"calls": worker.calls_today(mem), "budget": worker.REFLECT_CALLS,
                           "cost": round(mem.value("SELECT COALESCE(SUM(cost), 0) FROM runs WHERE at >= ?", today) or 0, 4)},
                 "failures": mem.rows("SELECT id, job, at, focus, problems FROM runs WHERE status IN ('failed', 'error') ORDER BY id DESC LIMIT 8"),
                 "quiet_minutes": round(worker.quiet_minutes(mem), 1), "reflect_idle": worker.REFLECT_IDLE,
                 "settings": {"mind": current_settings()["mind"], "thinking": current_settings()["thinking"]}},
        "health": {**json.loads(last_health["metrics"]), "at": last_health["at"]} if last_health else None,
        "history": history_status(),
        "dream": DREAM.status() if DREAM else None,
        "spend": {"all": round(mem.value("SELECT COALESCE(SUM(cost), 0) FROM runs") or 0, 4), "balance": wallet()},
    }


# --- your Claude history's build (tools/claude_import.py run), started and stopped from the looking glass ---
# It runs as its own process: it sets memory's clock to each conversation's time as it goes, which must never
# touch the conversation you're having. Its progress comes from its own output, and from its memory file.

HISTORY = {"proc": None, "state": "idle", "lines": [], "done": 0, "total": None, "spent": None, "eta_hours": None,
           "started": None, "args": None, "plan": None}


def history_status():
    out = {k: v for k, v in HISTORY.items() if k != "proc"}
    out["lines"] = HISTORY["lines"][-30:]
    out["file"] = str(CLAUDE_MEMORY)
    out["exists"] = CLAUDE_MEMORY.exists()
    if CLAUDE_MEMORY.exists():
        import sqlite3
        try:
            db = sqlite3.connect(f"file:{CLAUDE_MEMORY}?mode=ro", uri=True, timeout=5)
            one = lambda sql: db.execute(sql).fetchone()[0]
            written = one("SELECT COALESCE(MAX(last), 0) FROM episodes")
            out["memory"] = {"messages": one("SELECT COUNT(*) FROM messages"), "written_to": written,
                             "waiting": one(f"SELECT COUNT(*) FROM messages WHERE id > {written} AND via = 'claude'"),
                             "nodes": one("SELECT COUNT(*) FROM current"), "connections": one("SELECT COUNT(*) FROM edges"),
                             "conversations": one("SELECT COUNT(DISTINCT json_extract(meta, '$.conversation')) FROM messages WHERE via = 'claude'"),
                             "cost": round(one("SELECT COALESCE(SUM(cost), 0) FROM runs") or 0, 4)}
            db.close()
        except sqlite3.Error as e:
            out["memory"] = {"problem": str(e)}
    return out


def history_action(body):
    """plan | run {effort, max_dollars, max_stretches} | stop. Returns a problem, or None."""
    import signal
    import subprocess
    import threading
    action = body.get("action")
    script = HERE / "tools" / "claude_import.py"
    if action == "stop":
        proc = HISTORY["proc"]
        if not proc or proc.poll() is not None:
            return "The build isn't running."
        proc.send_signal(signal.SIGINT)              # it stops cleanly between stretches; running it again carries on
        HISTORY["state"] = "stopping"
        return None
    if HISTORY["proc"] and HISTORY["proc"].poll() is None:
        return "It's already running (stop it first)."
    if not CLAUDE_MEMORY.exists():
        return "There's no imported history yet: attach your Claude export and press [ import ] on it first."
    if action == "plan":
        done = subprocess.run([sys.executable, str(script), "plan", "--memory", str(CLAUDE_MEMORY)], capture_output=True,
                              text=True, cwd=HERE, timeout=600)
        HISTORY["plan"] = (done.stdout + done.stderr).strip()[-4000:]
        return None
    if action != "run":
        return "Unknown action."
    effort = luminal.effort_level(body.get("effort") or "none")
    cmd = [sys.executable, "-u", str(script), "run", "--memory", str(CLAUDE_MEMORY), "--effort", effort]
    if body.get("max_dollars"):
        cmd += ["--max-dollars", str(float(body["max_dollars"]))]
    if body.get("max_stretches"):
        cmd += ["--max-stretches", str(int(body["max_stretches"]))]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, cwd=HERE, bufsize=1)
    HISTORY.update(proc=proc, state="running", lines=[], done=0, total=None, spent=None, eta_hours=None,
                   started=memory.stamp(), args={"effort": effort, "max_dollars": body.get("max_dollars"),
                                                 "max_stretches": body.get("max_stretches")})

    def follow():
        for line in proc.stdout:
            line = line.rstrip()
            HISTORY["lines"] = (HISTORY["lines"] + [line])[-300:]
            m = re.search(r"\[\s*(\d+)/(\d+)\]", line)
            if m:
                HISTORY["done"], HISTORY["total"] = int(m.group(1)), int(m.group(2))
            m = re.search(r"\$([\d.]+) spent so far, about ([\d.]+) h to go", line)
            if m:
                HISTORY["spent"], HISTORY["eta_hours"] = float(m.group(1)), float(m.group(2))
            m = re.search(r"^([\d,]+) stretches to write", line)
            if m:
                HISTORY["total"] = int(m.group(1).replace(",", ""))
            worker.tell({"history": {"state": HISTORY["state"], "done": HISTORY["done"], "total": HISTORY["total"], "line": line}})
        code = proc.wait()
        HISTORY["state"] = "stopped" if HISTORY["state"] == "stopping" else ("finished" if code == 0 else f"failed (exit {code})")
        worker.tell({"history": {"state": HISTORY["state"]}})
    threading.Thread(target=follow, daemon=True).start()
    return None


DREAM = None      # dreaming (mind/dream.py), set at start


# ---------------------------------------------------------------------------
# 9. Start
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    DATA.mkdir(exist_ok=True)
    shutil.rmtree(INCOGNITO_DIR, ignore_errors=True)   # an incognito conversation left over from a crash: gone
    if "--memory" in sys.argv[1:-1]:                   # another memory file, e.g. the imported Claude history
        MEMORY_FILE = Path(sys.argv[sys.argv.index("--memory") + 1]).expanduser().resolve()
    elif os.environ.get("AVY_MEMORY"):
        MEMORY_FILE = Path(os.environ["AVY_MEMORY"]).expanduser().resolve()
    default_file = MEMORY_FILE == DATA / "memory-v2.db"
    first_run = not MEMORY_FILE.exists()
    MEMORIES["main"] = memory.Memory(MEMORY_FILE)
    if first_run and default_file and V1_MEMORY.exists():   # version 1's log carries over; its file is left as it was
        copied = MEMORIES["main"].copy_log_from(V1_MEMORY)
        print(f"Memory v2: copied {copied} messages from {V1_MEMORY.name}; knowledge is rebuilt from them in the background.")
    memory.embedder.start(DATA / "models" / "meaning")
    files.hooks["read"] = on_file_read                  # anything attached joins memory's library
    hands.WORKSPACE = DATA / "workspace"                 # her own folder to work in
    CHATS = chats.Chats(CHATS_FILE)                      # plain chat mode's conversations
    selfcode.HOOKS["restart"] = restart_soon             # self_ops(restart): run her changed code
    connectors.start(DATA / "connectors.json")           # toolboxes others built (MCP servers): the browser by default
    threading.Thread(target=tick, daemon=True, name="calendar").start()     # reminders and what's coming up, as they come due
    hands.HOOKS["finished"] = on_job_finished            # a background job ending is noted on its thread
    intake.HOOKS["describe"] = describe_picture          # ...pictures by what's in them
    worker.listeners.append(hear_mind)                   # the looking glass keeps track of the mind
    INTAKE.start()
    DREAM = dream.Dream(main=lambda: MEMORIES["main"], tell=worker.tell)
    worker.start(ask=ask_json, prices=PRICES, page=page_size, main=lambda: MEMORIES["main"],
                 effort=lambda: current_settings()["mind"], desk=lambda: current_settings()["persona"] == "on",
                 memories=lambda: [m for m in MEMORIES.values() if m])
    server = ThreadingHTTPServer((HOST, PORT), Handler)  # this computer only, unless AVY_HOST says otherwise
    url = f"http://localhost:{PORT}"
    main = MEMORIES["main"]
    print(f"Avy is up at {url}  (Ctrl+C to stop)")
    print(f"Files go in {DATA.resolve()}")
    print(f"Memory: {MEMORY_FILE.name}, {main.last_id()} messages so far, written into knowledge up to #{main.written_up_to()}.")
    if main.waiting_import():
        print(f"  {main.waiting_import():,} imported messages wait to be written. That only happens when you run "
              "python3 tools/claude_import.py run (docs/IMPORT.md).")
    print(f"Model: {luminal.model()} through Luminal ({luminal.base_url()})"
          + ("" if luminal.key() else ". Add your Luminal key in the page (the orange key button)."))
    print(f"Checking HTTPS certificates with {SSL_SOURCE}.")
    if voice:
        voice.start(turn=Turn, settings=current_settings, data=DATA, recordings=recordings_folder,
                    page_port=PORT, ssl_context=SSL_CONTEXT)
        files.hooks["transcribe"] = voice.transcribe_file     # attached audio and video can be listened to
    else:
        print(VOICE_PROBLEM)
    if not os.environ.get("AVY_NO_BROWSER"):
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        end_incognito()             # quitting ends an incognito conversation too
        if connectors.HUB:
            connectors.HUB.close()
        print("\nBye.")
