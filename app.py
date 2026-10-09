"""
Avy's whole server.

Run it:   python3 app.py
Then go:  http://localhost:8000

Text chat only needs Python's standard library. Voice is optional (voice.py).
Everything Avy writes to disk goes in the data/ folder next to this file.
"""

import json
import os
import ssl
import urllib.error
import urllib.request
import webbrowser
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


# ---------------------------------------------------------------------------
# 1. Where things live
# ---------------------------------------------------------------------------

HERE = Path(__file__).parent
ENV_FILE = HERE / ".env"                    # your keys; .gitignore keeps it off GitHub
DATA = HERE / "data"                        # everything else Avy saves (also kept off GitHub)
SETTINGS_FILE = DATA / "settings.json"      #   your choices from the system card or / commands
                                            #   data/models      speech models (voice)
                                            #   data/recordings  backups of what you said (voice)
PORT = 8000

# Every key the Keys panel asks for. Add a line here to add a field.
KEYS = {
    "DEEPSEEK_API_KEY": "DeepSeek API key",
}

SYSTEM_PROMPT = """You are Avy, Shreyas's personal assistant.
Talk like a sharp, warm friend: plain words, short answers, no filler.
Reply in plain text with no markdown, because your replies may be read aloud.
Keep it to a few sentences unless he asks for more.
Right now it is {now}."""


def system_prompt():
    """The prompt with today's date and time filled in. Text and voice both use this."""
    now = datetime.now().astimezone().strftime("%A, %B %d, %Y, %I:%M %p %Z")
    return SYSTEM_PROMPT.format(now=now)


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

SETTINGS = {
    "model":    {"about": "which DeepSeek model answers",
                 "options": ["deepseek-flash", "deepseek-v4-pro"], "default": "deepseek-flash"},
    "thinking": {"about": "think before answering (slower, costs more)",
                 "options": ["off", "low", "high", "max"], "default": "off"},
    "voice":    {"about": "Avy's voice (Kokoro). a = American, b = British, f/m = female/male",
                 "options": ENGLISH_VOICES, "default": "af_heart"},
    "speed":    {"about": "how fast Avy talks",
                 "options": ["0.8", "0.9", "1.0", "1.1", "1.2", "1.3"], "default": "1.0"},
    "whisper":  {"about": "speech-to-text model: top is fastest, bottom is most accurate",
                 "options": ["tiny.en", "base.en", "distil-small.en", "small.en", "distil-medium.en", "large-v3-turbo"],
                 "default": "distil-small.en"},
    "speak":    {"about": "say replies out loud when you talk to Avy",
                 "options": ["on", "off"], "default": "on"},
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


def folder_size(folder):
    # skip shortcuts (the Whisper download uses them), or files get counted twice
    return sum(f.stat().st_size for f in folder.rglob("*") if f.is_file() and not f.is_symlink()) if folder.exists() else 0


def settings_payload():
    """Everything the system card and / commands need."""
    recordings = sorted((DATA / "recordings").glob("*.wav")) if (DATA / "recordings").exists() else []
    return {
        "values": current_settings(),
        "schema": {name: {"about": s["about"], "options": s["options"]} for name, s in SETTINGS.items()},
        "prices": PRICES,
        "files": {
            "data": str(DATA.resolve()),
            "models_mb": round(folder_size(DATA / "models") / 1e6),
            "recordings": len(recordings),
            "recordings_mb": round(folder_size(DATA / "recordings") / 1e6, 1),
        },
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

API_URL = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com") + "/chat/completions"


def key_status():
    """What the page is allowed to know about the keys: only the last 4 characters."""
    keys = []
    for name, label in KEYS.items():
        value = os.environ.get(name, "")
        keys.append({"name": name, "label": label, "hint": value[-4:] if value else None})
    return {"keys": keys, "voice": voice_status()}


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


def ask_deepseek(raw_messages):
    """Start a streaming request. Returns the open response, or raises a friendly error."""
    key = os.environ.get("DEEPSEEK_API_KEY")
    if not key:
        raise FriendlyError(400, "Add your DeepSeek key first. Click the orange key button at the top right.")

    choice = current_settings()
    payload = {
        "model": choice["model"],
        "messages": [{"role": "system", "content": system_prompt()}] + clean_messages(raw_messages),
        "stream": True,                              # send words as they're written
        "stream_options": {"include_usage": True},   # token counts arrive at the end
    }
    if choice["thinking"] == "off":
        payload["thinking"] = {"type": "disabled"}   # DeepSeek thinks by default; off is faster
    else:
        payload["thinking"] = {"type": "enabled"}
        payload["reasoning_effort"] = choice["thinking"]   # low, high or max

    request = urllib.request.Request(
        API_URL,
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


def clean_messages(raw):
    """Only pass along user/assistant turns with text in them."""
    return [
        {"role": m["role"], "content": m["content"]}
        for m in raw if isinstance(m, dict)
        and m.get("role") in ("user", "assistant")
        and isinstance(m.get("content"), str)
    ]


# ---------------------------------------------------------------------------
# 5. The web server: one page, a few small endpoints
# ---------------------------------------------------------------------------

class Handler(BaseHTTPRequestHandler):

    def do_GET(self):
        if self.path == "/":
            self.send_file(HERE / "index.html", "text/html; charset=utf-8")
        elif self.path == "/api/status":
            self.send_json(200, key_status())
        elif self.path == "/api/settings":
            self.send_json(200, settings_payload())
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
        try:
            upstream = ask_deepseek(self.read_json().get("messages", []))
        except FriendlyError as e:
            return self.send_json(e.status, {"error": e.message})

        # Pass DeepSeek's stream straight through to the page, line by line.
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        with upstream:
            try:
                for line in upstream:
                    self.wfile.write(line)
                    self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                pass  # you pressed Stop or closed the tab

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

    def send_json(self, status, data):
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
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
# 6. Start
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    DATA.mkdir(exist_ok=True)
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)  # this computer only
    url = f"http://localhost:{PORT}"
    print(f"Avy is up at {url}  (Ctrl+C to stop)")
    print(f"Files go in {DATA.resolve()}")
    print(f"Checking HTTPS certificates with {SSL_SOURCE}.")
    if voice:
        voice.start(ask=ask_deepseek, settings=current_settings, data=DATA, page_port=PORT, ssl_context=SSL_CONTEXT)
    else:
        print(VOICE_PROBLEM)
    if not os.environ.get("AVY_NO_BROWSER"):
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nBye.")
