"""Connectors: toolboxes other people built and tuned, plugged into Avy over the Model Context Protocol (MCP).

An MCP server is a packaged set of tools with their own descriptions (written and tuned by the people who made them):
a real browser (Microsoft's Playwright server), git, GitHub, a calendar, a database, hundreds more. Avy speaks the
protocol as a client, so any of them can be added with one entry in data/connectors.json, in the same format Claude
Desktop and other MCP clients use:

    {"mcpServers": {
        "browser": {"command": "npx", "args": ["-y", "@playwright/mcp@latest", "--headless", "--isolated"]},
        "git":     {"command": "uvx", "args": ["mcp-server-git"]},
        "calendar":{"command": "npx", "args": ["-y", "@cocal/google-calendar-mcp"], "env": {"GOOGLE_OAUTH_CREDENTIALS": "..."},
                    "about": "his Google Calendar", "ask": ["create-event", "delete-event"]}
    }}

Toolboxes open on demand (progressive disclosure): her instructions list each toolbox in a line, and one tool,
open_toolbox, puts a toolbox's own tools in front of her for the rest of the reply. So twenty browser tools cost
nothing until she needs the browser. Each server starts the first time it's opened and stays up.

Safety: a toolbox's "ask" list names tools that wait for his OK on the page (like the terminal's risky commands); the
browser's form-filling, typing, uploads, dialogs and script running ask by default. /hands: trusted asks nothing;
/hands: off turns connectors off too.

Runs MCP's asyncio client in one background thread; everything else calls it synchronously.
"""

import asyncio
import json
import os
import shutil
import sys
import threading
from pathlib import Path

HERE = Path(__file__).parent
CONFIG = HERE / "data" / "connectors.json"       # app.py points it into data/
CALL_TIMEOUT = 120                                # seconds for one tool call
START_TIMEOUT = 90                                # seconds for a server to start (npx may download it the first time)
OUTPUT_CHARS = 14_000

BROWSER_ASK = ["browser_fill_form", "browser_type", "browser_file_upload", "browser_handle_dialog", "browser_evaluate",
               "browser_run_code_unsafe", "browser_install"]


def browser_flags():
    """Playwright's way to launch *the Chromium actually on this machine*, as argv flags.

    Order: AVY_BROWSER (a binary path) or AVY_BROWSER_CHANNEL (a Playwright channel name) if set; otherwise the newest
    chrome in ~/.cache/ms-playwright; otherwise nothing, and Playwright uses its default. This is deliberately
    self-discovering: the browser is the one toolbox that depends on the host, and a hard-coded path in .env breaks
    silently on a rebuilt VM in the worst way — the toolbox still "starts", then every open fails with
    "Chromium distribution 'chrome' is not found", which she reads as a browser that's missing and stops trying."""
    if os.environ.get("AVY_BROWSER_CHANNEL"):
        return ["--browser", os.environ["AVY_BROWSER_CHANNEL"]]
    path = os.environ.get("AVY_BROWSER")
    if not path:
        found = []
        for cache in (Path.home() / ".cache" / "ms-playwright",):
            for d in cache.glob("chromium-*"):
                for sub in ("chrome-linux-arm64/chrome", "chrome-linux/chrome", "chrome-mac/Chromium.app/Contents/MacOS/Chromium"):
                    if (d / sub).is_file():
                        found.append((d.stat().st_mtime, str(d / sub)))
        if found:
            path = max(found)[1]                 # newest install wins, so a `playwright install` upgrade is picked up
    return ["--executable-path", path] if path else []


DEFAULTS = {
    # The browser is the one toolbox with a host dependency, so it is self-discovering rather than configured: an
    # explicit AVY_BROWSER/AVY_BROWSER_CHANNEL wins, else the newest Chromium in the Playwright cache is used, else
    # Playwright's own default. Without this, a rebuilt VM silently hands her a toolbox that opens to
    # "Chromium distribution 'chrome' is not found" — a failure she then has to interpret, badly (IMPROVE-NOTES §11).
    "browser": {"command": "npx", "args": ["-y", "@playwright/mcp@latest", "--headless", "--isolated", "--no-sandbox",
                                           *browser_flags()],
                "about": "a real web browser: open pages, read them as an accessibility snapshot, click, type, fill forms, "
                         "take screenshots (for pages web_fetch can't read: logins, apps, anything that needs clicking)",
                "ask": BROWSER_ASK},
}


def load_config():
    """The toolboxes: data/connectors.json if it exists, else the defaults (the browser, when npx is installed)."""
    if CONFIG.exists():
        try:
            servers = json.loads(CONFIG.read_text()).get("mcpServers") or {}
        except json.JSONDecodeError as e:
            print(f"connectors.json isn't valid JSON ({e}); no connectors.")
            return {}
    else:
        servers = {k: dict(v, args=list(v["args"])) for k, v in DEFAULTS.items() if shutil.which(v["command"])}
        if "browser" in servers and hasattr(os, "geteuid") and os.geteuid() == 0:
            servers["browser"]["args"].append("--no-sandbox")      # Chromium refuses its sandbox as root (containers)
    return {name: spec for name, spec in servers.items() if not spec.get("disabled")}


class Toolbox:
    def __init__(self, name, spec):
        self.name, self.spec = name, spec
        self.session, self.tools, self.problem, self.ready = None, [], None, threading.Event()
        self.stop = None

    def about(self):
        return self.spec.get("about") or f"the {self.name} toolbox"


class Connectors:
    def __init__(self):
        self.boxes = {name: Toolbox(name, spec) for name, spec in load_config().items()}
        self.loop = None
        self.lock = threading.Lock()

    # --- the background loop -------------------------------------------------------------------------------------
    def _ensure_loop(self):
        with self.lock:
            if self.loop:
                return
            self.loop = asyncio.new_event_loop()
            threading.Thread(target=self.loop.run_forever, daemon=True, name="connectors").start()

    def _run(self, coro, timeout):
        self._ensure_loop()
        return asyncio.run_coroutine_threadsafe(coro, self.loop).result(timeout)

    async def _serve(self, box):
        """Start one server and keep its session open until stopped."""
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
        spec = box.spec
        params = StdioServerParameters(command=spec["command"], args=[str(a) for a in spec.get("args") or []],
                                       env={**os.environ, **{k: str(v) for k, v in (spec.get("env") or {}).items()}})
        box.stop = asyncio.Event()
        try:
            async with stdio_client(params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    listed = await session.list_tools()
                    # The MCP SDK renamed Tool.inputSchema to input_schema (and outputSchema/annotations alike). Read
                    # whichever this SDK has, so a version bump can't quietly empty the browser toolbox again.
                    def _schema(t):
                        for attr in ("inputSchema", "input_schema"):
                            if getattr(t, attr, None):
                                return getattr(t, attr)
                        return {"type": "object", "properties": {}}
                    box.tools = [{"name": t.name, "description": t.description or "", "schema": _schema(t)}
                                 for t in listed.tools]
                    box.session, box.problem = session, None
                    box.ready.set()
                    await box.stop.wait()
        except BaseException as e:
            # An anyio TaskGroup wraps real failures in ExceptionGroup, whose str() hides the cause ("1 sub-exception").
            # Walk down to the actual error so a broken toolbox says *why* instead of looking merely mysterious.
            def _why(x):
                for sub in getattr(x, "exceptions", None) or []:
                    found = _why(sub)
                    if found:
                        return found
                return f"{type(x).__name__}: {str(x)[:300]}" if str(x) else ""
            box.problem = "it failed: " + (_why(e) or type(e).__name__)
        finally:
            box.session = None
            box.ready.set()

    def open(self, name):
        """Start a toolbox if it isn't running. Returns (its tools, or None, and a problem)."""
        box = self.boxes.get(name)
        if not box:
            return None, f"there's no toolbox called {name!r}"
        if box.session:
            return box.tools, None
        box.ready.clear()
        self._ensure_loop()
        asyncio.run_coroutine_threadsafe(self._serve(box), self.loop)
        box.ready.wait(START_TIMEOUT)
        if not box.session:
            return None, box.problem or "it didn't start in time"
        return box.tools, None

    def call(self, name, tool, args):
        box = self.boxes.get(name)
        if not box or not box.session:
            tools, problem = self.open(name)
            if problem:
                return f"The {name} toolbox isn't available ({problem})."
        try:
            result = self._run(box.session.call_tool(tool, args or {}), CALL_TIMEOUT)
        except Exception as e:
            return f"The {name} toolbox's {tool} failed ({type(e).__name__}: {str(e)[:300]})."
        parts = []
        for c in result.content or []:
            if getattr(c, "type", "") == "text":
                parts.append(c.text)
            elif getattr(c, "type", "") == "image":
                parts.append("[an image came back: a screenshot or picture]")
            else:
                parts.append(f"[{getattr(c, 'type', 'something')} came back]")
        text = "\n".join(parts) or "(nothing came back)"
        if getattr(result, "isError", False):
            text = "Error: " + text
        import hands
        return hands.keep_output(text, OUTPUT_CHARS, label=f"{name}-{tool}")

    def close(self):
        for box in self.boxes.values():
            if box.stop and self.loop:
                self.loop.call_soon_threadsafe(box.stop.set)

    # --- what she sees -------------------------------------------------------------------------------------------
    def index(self):
        """One line per toolbox, for her instructions."""
        return "\n".join(f"- {name}: {box.about()}" + (f" (unavailable: {box.problem})" if box.problem and not box.session else "")
                         for name, box in self.boxes.items())

    def open_tool(self):
        if not self.boxes:
            return None
        return {"type": "function", "function": {
            "name": "open_toolbox",
            "description": "Open one of your toolboxes (connectors), so its tools are yours for the rest of this reply. Your toolboxes:\n"
                           + self.index() + "\nOpen one when the task needs it (for example the browser for a page web_fetch can't read, "
                           "a site that needs clicking or a login he's given you), then use its tools.",
            "parameters": {"type": "object", "properties": {"name": {"type": "string", "enum": list(self.boxes)}}, "required": ["name"]}}}

    def tools_of(self, name):
        """A toolbox's tools in the model's format, named toolbox__tool so they can't clash with hers."""
        box = self.boxes.get(name)
        out = []
        for t in (box.tools if box else []):
            schema = dict(t["schema"]) if isinstance(t["schema"], dict) else {"type": "object", "properties": {}}
            schema.setdefault("type", "object")
            schema.setdefault("properties", {})
            out.append({"type": "function", "function": {"name": f"{name}__{t['name']}", "description": t["description"][:1500],
                                                          "parameters": schema}})
        return out

    def needs_ok(self, name, tool):
        box = self.boxes.get(name)
        return bool(box) and tool in (box.spec.get("ask") or [])

    def status(self):
        return [{"name": n, "about": b.about(), "running": bool(b.session), "tools": len(b.tools), "problem": b.problem,
                 "command": " ".join([b.spec["command"], *[str(a) for a in b.spec.get("args") or []]])} for n, b in self.boxes.items()]


HUB = None          # the one Connectors, made by app.py at start (None: no connectors)


def start(config_path=None):
    global HUB, CONFIG
    if config_path:
        CONFIG = Path(config_path)
    try:
        import mcp  # noqa: F401
    except ImportError:
        print("Connectors need the mcp package: python3 -m pip install mcp")
        HUB = None
        return None
    HUB = Connectors()
    return HUB


if __name__ == "__main__":          # python3 connectors.py: start each toolbox and list its tools
    hub = start(sys.argv[1] if len(sys.argv) > 1 else None)
    for name in (hub.boxes if hub else {}):
        tools, problem = hub.open(name)
        print(f"{name}: " + (problem or f"{len(tools)} tools: " + ", ".join(t["name"] for t in tools)))
    if hub:
        hub.close()
