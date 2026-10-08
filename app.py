"""
Avy's whole server.

Run it:   python app.py
Then go:  http://localhost:8000

No installs needed. It only uses Python's standard library.
"""

import json
import os
import urllib.error
import urllib.request
import webbrowser
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


# ---------------------------------------------------------------------------
# 1. Settings
# ---------------------------------------------------------------------------

HERE = Path(__file__).parent
ENV_FILE = HERE / ".env"   # your keys live here; .gitignore keeps it off GitHub
PORT = 8000

# Every key the settings panel should ask for. Add a line here to add a field.
KEYS = {
    "DEEPSEEK_API_KEY": "DeepSeek API key",
}

SYSTEM_PROMPT = """You are Avy, Shreyas's personal assistant.
Talk like a sharp, warm friend: plain words, short answers, no filler.
Reply in plain text with no markdown, because your replies may be read aloud.
Keep it to a few sentences unless he asks for more.
Right now it is {now}."""


# ---------------------------------------------------------------------------
# 2. The .env file: read it on startup, rewrite it when you save a key
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

# Which DeepSeek model and where to reach it. Both can be changed in .env.
MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-flash")  # = DeepSeek V4.1 Flash
API_URL = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com") + "/chat/completions"


def key_status():
    """What the page is allowed to know about the keys: only the last 4 characters."""
    keys = []
    for name, label in KEYS.items():
        value = os.environ.get(name, "")
        keys.append({"name": name, "label": label, "hint": value[-4:] if value else None})
    return {"model": MODEL, "keys": keys}


# ---------------------------------------------------------------------------
# 3. Talking to DeepSeek
# ---------------------------------------------------------------------------

class FriendlyError(Exception):
    """An error with a message that's safe and useful to show on the page."""
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status
        self.message = message


def ask_deepseek(messages):
    """Start a streaming request. Returns the open response, or raises a friendly error."""
    key = os.environ.get("DEEPSEEK_API_KEY")
    if not key:
        raise FriendlyError(400, "Add your DeepSeek key first. Click the orange key button at the top right.")

    now = datetime.now().astimezone().strftime("%A, %B %d, %Y, %I:%M %p %Z")
    payload = {
        "model": MODEL,
        "messages": [{"role": "system", "content": SYSTEM_PROMPT.format(now=now)}] + messages,
        "stream": True,                              # send words as they're written
        "stream_options": {"include_usage": True},   # token counts arrive at the end
        "thinking": {"type": "disabled"},            # fast replies; thinking mode is the default otherwise
    }
    request = urllib.request.Request(
        API_URL,
        data=json.dumps(payload).encode(),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
    )
    try:
        return urllib.request.urlopen(request, timeout=60)
    except urllib.error.HTTPError as e:
        if e.code == 401:
            raise FriendlyError(401, "DeepSeek rejected the key. Paste a fresh one in Keys.")
        if e.code == 402:
            raise FriendlyError(402, "Your DeepSeek balance is empty. Top up at platform.deepseek.com, then send again.")
        detail = e.read().decode(errors="replace")[:300]
        raise FriendlyError(e.code, f"DeepSeek returned an error ({e.code}): {detail}")
    except urllib.error.URLError as e:
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
# 4. The web server: one page, three small endpoints
# ---------------------------------------------------------------------------

class Handler(BaseHTTPRequestHandler):

    def do_GET(self):
        if self.path == "/":
            self.send_file(HERE / "index.html", "text/html; charset=utf-8")
        elif self.path == "/api/status":
            self.send_json(200, key_status())
        else:
            self.send_json(404, {"error": "Not found"})

    def do_POST(self):
        if not self.from_avy_page():
            return self.send_json(403, {"error": "Requests are only accepted from Avy's own page."})
        if self.path == "/api/keys":
            self.save_keys()
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
        messages = clean_messages(self.read_json().get("messages", []))
        try:
            upstream = ask_deepseek(messages)
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


# ---------------------------------------------------------------------------
# 5. Start
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)  # this computer only
    url = f"http://localhost:{PORT}"
    print(f"Avy is up at {url}  (Ctrl+C to stop)")
    if not os.environ.get("AVY_NO_BROWSER"):
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nBye.")
