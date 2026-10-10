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
import json
import os
import shutil
import ssl
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import memory
from memory import recall as recalling
from mind import explore, llm as mind_llm, worker, writer


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
V1_MEMORY = DATA / "memory.db"              #   version 1's memory (the log is copied from it once; never changed)
INCOGNITO_DIR = DATA / "incognito"          #   an incognito conversation: deleted when it ends
                                            #   data/models      speech and meaning-search models
                                            #   data/recordings  backups of what you said (voice)
PORT = 8000

# Every key the Keys panel asks for. Add a line here to add a field.
KEYS = {
    "DEEPSEEK_API_KEY": "DeepSeek API key",
}

SYSTEM_PROMPT = f"""You are Avy, {memory.NAME}'s personal assistant.
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
A node that changed shows its earlier versions; the newest is what's true now. The note also lists how
the nodes connect, with reasons: follow those, because that's how something from weeks ago turns out to
matter now. Use what's relevant and ignore the rest. If neither the recent messages nor memory covers
something, say you don't remember it rather than guessing."""

FOOTNOTES = """When part of your answer comes from memory, put that node's handle right after it, like
this[k12], with no space before it. The page turns these into small footnotes. Use only handles from the
memory note, and only where they genuinely support what you just said; never mention numbers otherwise."""

NO_FOOTNOTES = "Don't mention node handles or message numbers unless he asks where something came from."

INCOGNITO_NOTE = f"""This is an incognito conversation, separate from your main one with {memory.NAME}. You can use
your memory of the main conversation, but nothing said here will be remembered once it ends."""


def system_prompt(incognito=False, core=True):
    """Avy's instructions plus the core of her memory (its biggest hubs). It only changes when the network
    does, so DeepSeek can reuse its cached copy (the time goes in the memory note instead).
    core=False when memory search is off: then she gets no memory at all."""
    choice = current_settings()
    hubs = MEMORIES["main"].core() if core else ""
    return (SYSTEM_PROMPT + "\n\n" + (FOOTNOTES if choice["footnotes"] == "on" else NO_FOOTNOTES)
            + (f"\n\n{INCOGNITO_NOTE}" if incognito else "") + (f"\n\n{hubs}" if hubs else ""))


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
    "model":    {"short": "which DeepSeek model answers", "card": True,
                 "about": "which DeepSeek model answers",
                 "options": ["deepseek-flash", "deepseek-v4-pro"], "default": "deepseek-flash"},
    "window":   {"short": "recent messages read verbatim", "card": True,
                 "about": "how many recent messages Avy reads word for word; the rest comes from memory (all: an ordinary chat)",
                 "options": ["0", "5", "10", "20", "40", "80", "all"], "default": "20"},
    "recall":   {"short": "how far memory reaches", "card": True,
                 "about": "how far memory search reaches on each message (with explore on: how many rounds Avy searches)",
                 "options": ["off", "light", "normal", "deep", "max"], "default": "normal"},
    "explore":  {"short": "Avy searches memory herself", "card": True,
                 "about": "on: DeepSeek steers the memory search step by step, following the task, not just the words (a few seconds more). off: search by rules, instantly",
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
    "thinking": {"short": "think before answering", "card": False,
                 "about": "think before answering (slower, costs more)",
                 "options": ["off", "low", "high", "max"], "default": "off"},
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

# Dollars per million tokens at off-peak rates (peak hours cost double), from DeepSeek's pricing page.
PRICES = {
    "deepseek-flash":  {"cache_hit": 0.003, "cache_miss": 0.15, "output": 0.60},
    "deepseek-v4-pro": {"cache_hit": 0.022, "cache_miss": 0.66, "output": 1.98},
}


def current_settings():
    """Defaults, overridden by whatever valid choices are saved in data/settings.json."""
    saved = {}
    if SETTINGS_FILE.exists():
        try:
            saved = json.loads(SETTINGS_FILE.read_text())
        except json.JSONDecodeError:
            pass
    return {name: saved.get(name) if saved.get(name) in spec["options"] else spec["default"]
            for name, spec in SETTINGS.items()}


def change_setting(name, value):
    """Save one choice. Returns an error message, or None if it worked."""
    if name not in SETTINGS:
        return f"There's no setting called '{name}'."
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

API_BASE = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")


def key_status():
    """What the page is allowed to know about the keys: only the last 4 characters."""
    keys = []
    for name, label in KEYS.items():
        value = os.environ.get(name, "")
        keys.append({"name": name, "label": label, "hint": value[-4:] if value else None})
    return {"keys": keys, "voice": voice_status(), "incognito": MEMORIES["incognito"] is not None, "page": PAGE_VERSION}


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
# 4. Talking to DeepSeek (text chat and voice both come through here)
# ---------------------------------------------------------------------------

def make_ssl_context():
    """How Python checks that it's really talking to DeepSeek (HTTPS certificates).

    Some Python installs (python.org on Mac is the usual one) ship without a
    certificate list, so every HTTPS request fails. If `truststore` is installed
    we use your computer's own certificate store, which always works; otherwise
    `certifi`'s list if that's around; otherwise Python's default.
    """
    try:
        import truststore
        return truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT), "your computer's certificate store"
    except ImportError:
        pass
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where()), "certifi"
    except ImportError:
        return ssl.create_default_context(), "Python's default"


SSL_CONTEXT, SSL_SOURCE = make_ssl_context()


class FriendlyError(Exception):
    """An error with a message that's safe and useful to show on the page."""
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status
        self.message = message


def deepseek(payload, beta=False):
    """Send one request to DeepSeek. Returns the open response, or raises a friendly error.
    beta=True uses DeepSeek's beta address, where tool calls can be marked strict."""
    key = os.environ.get("DEEPSEEK_API_KEY")
    if not key:
        raise FriendlyError(400, "Add your DeepSeek key first. Click the orange key button at the top right.")
    request = urllib.request.Request(
        API_BASE + ("/beta" if beta else "") + "/chat/completions",
        data=json.dumps(payload).encode(),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
    )
    try:
        return urllib.request.urlopen(request, timeout=120, context=SSL_CONTEXT)
    except urllib.error.HTTPError as e:
        if e.code == 401:
            raise FriendlyError(401, "DeepSeek rejected the key. Paste a fresh one in Keys.")
        if e.code == 402:
            raise FriendlyError(402, "Your DeepSeek balance is empty. Top up at platform.deepseek.com, then send again.")
        detail = e.read().decode(errors="replace")[:300]
        raise FriendlyError(e.code, f"DeepSeek returned an error ({e.code}): {detail}")
    except urllib.error.URLError as e:
        if isinstance(e.reason, ssl.SSLCertVerificationError):
            raise FriendlyError(502, "Python can't check DeepSeek's security certificate on this computer. "
                                     "Run  python3 -m pip install truststore  once, then restart app.py.")
        raise FriendlyError(502, f"Can't reach DeepSeek ({e.reason}). Check your internet connection, then send again.")


def ask_deepseek(messages, model):
    """Start a streaming reply."""
    choice = current_settings()
    payload = {
        "model": model,
        "messages": messages,
        "stream": True,                              # send words as they're written
        "stream_options": {"include_usage": True},   # token counts arrive at the end
    }
    if choice["thinking"] == "off":
        payload["thinking"] = {"type": "disabled"}   # DeepSeek thinks by default; off is faster
    else:
        payload["thinking"] = {"type": "enabled"}
        payload["reasoning_effort"] = choice["thinking"]   # low, high or max
    return deepseek(payload)


def ask_json(payload):
    """One structured request for the mind (writing, reflecting, searching): the whole answer at once."""
    with deepseek(payload, beta=True) as response:
        return json.loads(response.read())


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


def recordings_folder():
    """Where voice recordings go: an incognito conversation keeps its own (deleted with it)."""
    return INCOGNITO_DIR / "recordings" if MEMORIES["incognito"] else DATA / "recordings"


def memory_by_letter(letter):
    return next((m for m in MEMORIES.values() if m and m.letter == letter), None)


# ---------------------------------------------------------------------------
# 6. A turn: one exchange with Avy, typed or spoken. Memory is assembled fresh for
#    every message, so there's never a "new chat": every message is one.
# ---------------------------------------------------------------------------

class Turn:
    """Your message in, Avy's reply out, both saved to the log.

        turn = Turn("when's rohan's birthday?", "text")   # gathers memory, lays out the briefing
        upstream = turn.ask()                             # starts DeepSeek; saves your message
        ...stream the reply...
        turn.finish(reply, usage, cut=False)              # saves Avy's reply

    progress(event), if given, hears about each round while Avy searches her memory herself.
    """

    def __init__(self, text, via, progress=None):
        choice = current_settings()
        self.text, self.via, self.model = text, via, choice["model"]
        self.mem = talking_to()
        self.incognito = self.mem is MEMORIES["incognito"]
        shown = self.mem.window(window_size())                   # /window: what she reads word for word
        shown_from = shown[0]["id"] if shown else self.mem.last_id() + 1
        previous = self.mem.last_said()
        opts = {"depth": choice["recall"], "words": choice["words"] == "on", "meaning": choice["meaning"] == "on"}
        self.searching = choice["recall"] != "off" and (opts["words"] or opts["meaning"])
        if choice["explore"] == "on" and self.searching:          # /explore: DeepSeek steers the search
            library = explore.Library([MEMORIES["main"], MEMORIES["incognito"]])
            recent = "\n".join(f"{memory.who(m['role'])}: {memory.clip(m['text'], 0, 500)}" for m in self.mem.window(2)[-2:])
            self.recall = explore.explore(library, self.mem, text, recent, shown_from, progress=progress, **opts)
        else:                                                     # by rules
            self.recall = self.mem.recall(text, previous, shown_from, **opts)
            if self.incognito and self.searching:                 # incognito also reads the main memory
                main = MEMORIES["main"].recall(text, previous, None, **opts)
                self.recall = recalling.combine(MEMORIES["main"], main, self.mem, self.recall)
        self.messages = briefing(shown, self.recall["briefing"], text, self.incognito, core=self.searching)
        self.user_id = self.recall_id = self.reply_id = None

    def ask(self):
        upstream = ask_deepseek(self.messages, self.model)   # if this fails, nothing is saved
        self.user_id = self.mem.add("user", self.text, self.via)
        self.recall_id = self.mem.save_recall(self.user_id, self.recall)
        return upstream

    def summary(self):
        """What the page shows under the reply: what memory brought, and where it came from."""
        found = self.recall.get("explore") or {}
        return {"message": self.user_id, "recall": self.recall_id, "memory": self.mem.name,
                "nodes": len(self.recall["nodes"]), "log": len(self.recall["log"]),
                "explored": bool(found and not found.get("fell_back")),
                "kept": [x["handle"] for x in self.recall["nodes"]],
                "visited": found.get("visited", [])}

    def finish(self, text, usage=None, cut=False):
        """Save Avy's reply (only what was actually sent or heard). Returns its number."""
        if self.reply_id or not self.user_id or not text.strip() or self.mem.closed:
            return self.reply_id
        meta = {"model": self.model, "recall": self.recall_id}
        if usage:
            meta["usage"] = usage
        if cut:
            meta["cut"] = True
        self.reply_id = self.mem.add("assistant", text.strip(), self.via, meta)
        worker.nudge()                 # the mind writes in the background once an episode's worth is waiting
        return self.reply_id


def briefing(shown, memory_note, text, incognito=False, core=True):
    """What DeepSeek sees, in this order: instructions and core (same every time, so it's cached),
    the newest messages word for word, the memory note for this message, then your message."""
    messages = [{"role": "system", "content": system_prompt(incognito, core)}]
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
    messages.append({"role": "system", "content": memory_note})
    messages.append({"role": "user", "content": text})
    return messages


def stream_text(line):
    """The words and token counts in one line of DeepSeek's stream: (text, usage or None)."""
    line = line.decode(errors="replace").strip() if isinstance(line, bytes) else line.strip()
    if not line.startswith("data:") or line == "data: [DONE]":
        return "", None
    try:
        chunk = json.loads(line[5:])
    except json.JSONDecodeError:
        return "", None
    text = "".join((c.get("delta") or {}).get("content") or "" for c in chunk.get("choices") or [])
    return text, chunk.get("usage")


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
                "/api/search", "/api/graph", "/api/journal", "/api/health")


class Handler(BaseHTTPRequestHandler):

    def do_GET(self):
        url = urllib.parse.urlparse(self.path)
        q = urllib.parse.parse_qs(url.query)
        if url.path == "/":
            self.send_page()
        elif url.path == "/api/status":
            self.send_json(200, key_status())
        elif url.path == "/api/settings":
            self.send_json(200, settings_payload())
        elif url.path == "/api/events":
            self.events()
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
                                     "reflections": mem.runs_list(["think", "check"], 30) if full else [],
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
            elif url.path == "/api/graph":
                self.send_json(200, mem.graph_data())
            elif url.path == "/api/journal":
                self.send_json(200, {"journal": mem.journal_list(min(number(q, "limit") or 200, 1000))})
            elif url.path == "/api/health":
                self.send_json(200, {"now": memory.health(mem), "history": [
                    {"at": r["at"], **json.loads(r["metrics"])} for r in mem.rows("SELECT * FROM health ORDER BY id")]})
            else:
                self.send_json(200, mem.find(q.get("q", [""])[0]))
        else:
            self.send_json(404, {"error": "Not found"})

    def do_POST(self):
        if not self.from_avy_page():
            return self.send_json(403, {"error": "Requests are only accepted from Avy's own page."})
        if self.path == "/api/keys":
            self.save_keys()
        elif self.path == "/api/settings":
            body = self.read_json()
            problem = change_setting(body.get("name"), body.get("value"))
            self.send_json(400 if problem else 200, {"error": problem} if problem else settings_payload())
        elif self.path == "/api/chat":
            self.chat()
        elif self.path == "/api/index":         # /index: write what's waiting now, even a short stretch
            mem = talking_to()
            runs = worker.write_due(mem, force=True)
            self.send_json(200, {"runs": runs, "stats": mem.stats()})
        elif self.path == "/api/reflect":       # /reflect: think now, instead of waiting for a quiet spell
            mem = talking_to()
            worker.write_due(mem, force=True)
            runs = worker.reflect_now(mem, budget=10_000)
            self.send_json(200, {"runs": runs, "stats": mem.stats()})
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
        text = str(self.read_json().get("text") or "").strip()
        if not text:
            return self.send_json(400, {"error": "There's nothing to send."})
        # The stream starts right away, so the page can show Avy searching her memory before she answers.
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        try:
            turn = Turn(text, "text", progress=lambda e: self.event({"avy": {"searching": e}}))
            upstream = turn.ask()
        except FriendlyError as e:
            return self.event({"avy": {"error": e.message}})
        except (BrokenPipeError, ConnectionResetError):
            return
        except Exception as e:
            print(f"A turn failed: {e!r}")
            return self.event({"avy": {"error": f"Something went wrong preparing the reply ({e})."}})

        # Pass DeepSeek's stream through to the page line by line, keeping what got there.
        reply, usage, cut = "", None, False
        try:
            self.event({"avy": {"turn": turn.summary()}})
            with upstream:
                for line in upstream:
                    if line.strip() == b"data: [DONE]":
                        break
                    self.wfile.write(line)
                    self.wfile.flush()
                    words, counts = stream_text(line)
                    reply += words
                    usage = counts or usage
        except (BrokenPipeError, ConnectionResetError):
            cut = True                     # you pressed Stop or closed the tab
        except OSError:
            cut = True                     # DeepSeek dropped the connection partway through
        saved = turn.finish(reply, usage, cut)
        if not cut:
            try:
                self.event({"avy": {"saved": saved}})
                self.wfile.write(b"data: [DONE]\n\n")
            except OSError:
                pass

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
                    self.event({"mind": box.get(timeout=25)})
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
        return origin is None or origin in (f"http://localhost:{PORT}", f"http://127.0.0.1:{PORT}")

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

    def send_file(self, path, content_type):
        body = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        pass   # keep the terminal for things that matter


# ---------------------------------------------------------------------------
# 8. Start
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    DATA.mkdir(exist_ok=True)
    shutil.rmtree(INCOGNITO_DIR, ignore_errors=True)   # an incognito conversation left over from a crash: gone
    first_run = not MEMORY_FILE.exists()
    MEMORIES["main"] = memory.Memory(MEMORY_FILE)
    if first_run and V1_MEMORY.exists():                # version 1's log carries over; its file is left as it was
        copied = MEMORIES["main"].copy_log_from(V1_MEMORY)
        print(f"Memory v2: copied {copied} messages from {V1_MEMORY.name}; knowledge is rebuilt from them in the background.")
    memory.embedder.start(DATA / "models" / "meaning")
    worker.start(ask=ask_json, prices=PRICES, page=page_size, main=lambda: MEMORIES["main"],
                 memories=lambda: [m for m in MEMORIES.values() if m])
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)  # this computer only
    url = f"http://localhost:{PORT}"
    main = MEMORIES["main"]
    print(f"Avy is up at {url}  (Ctrl+C to stop)")
    print(f"Files go in {DATA.resolve()}")
    print(f"Memory: {main.last_id()} messages so far, written into knowledge up to #{main.written_up_to()}.")
    print(f"Checking HTTPS certificates with {SSL_SOURCE}.")
    if voice:
        voice.start(turn=Turn, settings=current_settings, data=DATA, recordings=recordings_folder,
                    page_port=PORT, ssl_context=SSL_CONTEXT)
    else:
        print(VOICE_PROBLEM)
    if not os.environ.get("AVY_NO_BROWSER"):
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        end_incognito()             # quitting ends an incognito conversation too
        print("\nBye.")
