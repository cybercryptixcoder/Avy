"""Avy's model provider: Luminal (https://flash.luminal.cloud/v1), a US-hosted, OpenAI-style endpoint
serving one model, DeepSeek-V4.1-Flash. Every model call Avy makes goes through here: her replies,
her search, and the background mind.

The rules, from probing Luminal (docs/LUMINAL.md has the evidence):
  - Always send reasoning_effort. Left out, the model thinks by default and the hidden thinking eats
    the output budget. "none" = no thinking (fast); low, medium, high, xhigh, ultra, max = more.
  - Always send max_tokens. Left out, there's a silent 8,192-token cap. With thinking on, it has to
    cover the thinking too.
  - Stream. Non-streamed generations longer than about 20 seconds can be cut off.
  - Retry 429 (too many at once), 503 (temporarily unavailable), dropped connections and empty
    bodies, with backoff. Keep parallel calls at 8 or fewer.
  - A forced tool call (tool_choice naming a tool) only works with thinking off; with thinking on it
    has to be tool_choice "auto". JSON-schema output isn't available; tool calls and json_object are.
  - The context is 163,840 tokens; the endpoint doesn't say so, so it's declared here.
  - Images work (image_url parts). There's no published price per token: the wallet
    (GET /v1/balance) is the truth, and costs shown in Avy are estimates.

Configuration (environment, or .env): LUMINAL_API_KEY (required), LUMINAL_BASE_URL and
HELIX_FLASH_MODEL (both have defaults). The key is entered once in the Keys panel, saved to .env, and
never committed.
"""

import json
import os
import random
import socket
import ssl
import threading
import time
import urllib.error
import urllib.request

DEFAULT_BASE = "https://flash.luminal.cloud/v1"
DEFAULT_MODEL = "deepseek-ai/DeepSeek-V4.1-Flash"
KEY_NAME = "LUMINAL_API_KEY"
CONTEXT_TOKENS = 163_840
MAX_OUTPUT = 393_216
EFFORTS = ["none", "low", "medium", "high", "xhigh", "ultra", "max"]
THINKING_ROOM = 24_000          # extra output tokens allowed for thinking when it's on
MAX_PARALLEL = 8                # Luminal starts refusing somewhere past 8 calls at once
RETRIES = 4
UNITS_PER_USD = 1e10

# Luminal publishes no per-token price. These are DeepSeek's own list prices for V4.1-Flash (dollars per
# million tokens), used only to estimate; GET /v1/balance shows what was really spent.
PRICES = {"cache_hit": 0.006, "cache_miss": 0.30, "output": 1.20}

_slots = threading.BoundedSemaphore(MAX_PARALLEL)


def base_url():
    return (os.environ.get("LUMINAL_BASE_URL") or DEFAULT_BASE).rstrip("/")


def model():
    return os.environ.get("HELIX_FLASH_MODEL") or DEFAULT_MODEL


def key():
    return os.environ.get(KEY_NAME, "").strip()


def make_ssl_context():
    """How Python checks it's really talking to Luminal. Some Python installs (python.org on a Mac)
    ship without certificates; truststore uses your computer's own store, certifi its own list."""
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


class LuminalError(Exception):
    """A failure with a message that's safe and useful to show on the page."""
    def __init__(self, status, message, retryable=False):
        super().__init__(message)
        self.status, self.message, self.retryable = status, message, retryable


def prepare(payload, effort=None):
    """Fill in what Luminal needs on every request: the model, an explicit max_tokens and reasoning_effort.
    effort overrides whatever the payload says. With thinking on, a forced tool call becomes "auto"
    (Luminal refuses a forced one while thinking) and max_tokens grows to leave room for the thinking."""
    p = dict(payload)
    p["model"] = model()
    p.pop("thinking", None)                      # DeepSeek's own switch; Luminal goes by reasoning_effort
    p["reasoning_effort"] = effort or p.get("reasoning_effort") or "none"
    if p["reasoning_effort"] not in EFFORTS:
        p["reasoning_effort"] = "none"
    p["max_tokens"] = int(p.get("max_tokens") or 8000)
    if p["reasoning_effort"] != "none":
        if isinstance(p.get("tool_choice"), dict):
            p["tool_choice"] = "auto"
        p["max_tokens"] += THINKING_ROOM
    p["max_tokens"] = max(1, min(MAX_OUTPUT, p["max_tokens"]))
    return p


def _open(path, body=None, timeout=180):
    """One HTTP request to Luminal. Returns the open response; raises LuminalError."""
    if not key():
        raise LuminalError(400, "Add your Luminal key first: click the orange key button at the top right.")
    request = urllib.request.Request(
        base_url() + path, data=json.dumps(body).encode() if body is not None else None,
        headers={"Authorization": f"Bearer {key()}", "Content-Type": "application/json"})
    try:
        return urllib.request.urlopen(request, timeout=timeout, context=SSL_CONTEXT)
    except urllib.error.HTTPError as e:
        raw = e.read().decode(errors="replace")
        try:
            detail = (json.loads(raw).get("error") or {}).get("message") or raw
        except (json.JSONDecodeError, AttributeError):
            detail = raw or e.headers.get("x-reject-reason") or ""
        detail = str(detail)[:300]
        if e.code in (401, 403):
            raise LuminalError(e.code, "Luminal rejected the key. Paste a fresh one in Keys.")
        if e.code == 402:
            raise LuminalError(402, "Your Luminal balance is empty. Top it up, then send again.")
        retry = e.code in (429, 500, 502, 503, 504)
        raise LuminalError(e.code, f"Luminal returned an error ({e.code}): {detail}", retryable=retry)
    except urllib.error.URLError as e:
        if isinstance(e.reason, ssl.SSLCertVerificationError):
            raise LuminalError(502, "Python can't check Luminal's security certificate on this computer. "
                                    "Run  python3 -m pip install truststore  once, then restart app.py.")
        raise LuminalError(502, f"Can't reach Luminal ({e.reason}). Check your internet connection.", retryable=True)
    except (socket.timeout, TimeoutError, ConnectionError, OSError) as e:
        raise LuminalError(502, f"The connection to Luminal failed ({e}).", retryable=True)


def _with_retries(attempt):
    """Run attempt() until it works, retrying what Luminal says is temporary (backoff with jitter)."""
    for i in range(RETRIES):
        try:
            return attempt()
        except LuminalError as e:
            if not e.retryable or i == RETRIES - 1:
                raise
            time.sleep(min(20, 2 * 2 ** i) + random.random())


def open_stream(payload, effort=None):
    """Start a streamed reply (for Avy's answers: the words go to the page as they come).
    Returns the open response; iterate it for SSE lines. Retries happen before the first byte."""
    p = prepare({**payload, "stream": True, "stream_options": {"include_usage": True}}, effort)

    def attempt():
        with _slots:
            return _open("/chat/completions", p)
    return _with_retries(attempt)


def complete(payload, effort=None, timeout=240):
    """One whole answer (for the mind and the search): streamed underneath, because long non-streamed
    answers get cut off, then put back together in the usual non-streamed shape:
    {"choices": [{"message": {"content", "reasoning_content", "tool_calls"}, "finish_reason"}], "usage"}.
    Dropped streams, errors inside the stream and empty answers are retried."""
    p = prepare({**payload, "stream": True, "stream_options": {"include_usage": True}}, effort)

    def attempt():
        with _slots:
            response = _open("/chat/completions", p, timeout=timeout)
            try:
                with response:
                    return assemble(response)
            except (socket.timeout, TimeoutError, ConnectionError, OSError) as e:
                raise LuminalError(502, f"The stream from Luminal dropped ({e}).", retryable=True)
    return _with_retries(attempt)


def assemble(lines):
    """Put a streamed answer back together. lines: SSE lines (bytes or str)."""
    content, reasoning, calls, usage, finish, seen = [], [], {}, None, None, False
    for line in lines:
        line = line.decode(errors="replace") if isinstance(line, bytes) else line
        line = line.strip()
        if not line.startswith("data:"):
            continue                                  # blank lines and ": ping" keep-alives
        data = line[5:].strip()
        if data == "[DONE]":
            break
        try:
            chunk = json.loads(data)
        except json.JSONDecodeError:
            continue
        if chunk.get("error"):
            raise LuminalError(502, f"Luminal sent an error mid-answer: {str(chunk['error'])[:200]}", retryable=True)
        seen = True
        usage = chunk.get("usage") or usage
        for choice in chunk.get("choices") or []:
            finish = choice.get("finish_reason") or finish
            delta = choice.get("delta") or {}
            content.append(delta.get("content") or "")
            reasoning.append(delta.get("reasoning_content") or "")
            for tc in delta.get("tool_calls") or []:
                call = calls.setdefault(tc.get("index", 0), {"id": "", "type": "function", "function": {"name": "", "arguments": ""}})
                call["id"] = tc.get("id") or call["id"]
                fn = tc.get("function") or {}
                call["function"]["name"] += fn.get("name") or ""
                call["function"]["arguments"] += fn.get("arguments") or ""
    if not seen:
        raise LuminalError(502, "Luminal sent an empty answer.", retryable=True)
    message = {"role": "assistant", "content": "".join(content), "reasoning_content": "".join(reasoning)}
    if calls:
        message["tool_calls"] = [calls[i] for i in sorted(calls)]
    return {"choices": [{"index": 0, "message": message, "finish_reason": finish}], "usage": usage or {}}


def stream_text(line):
    """The answer's words and the token counts in one line of a streamed reply: (text, usage or None).
    Thinking (reasoning_content) isn't part of the answer."""
    line = line.decode(errors="replace").strip() if isinstance(line, bytes) else line.strip()
    if not line.startswith("data:") or line == "data: [DONE]":
        return "", None
    try:
        chunk = json.loads(line[5:])
    except json.JSONDecodeError:
        return "", None
    text = "".join((c.get("delta") or {}).get("content") or "" for c in chunk.get("choices") or [])
    return text, chunk.get("usage")


def cost(usage):
    """Estimated dollars for one call's usage (see PRICES)."""
    usage = usage or {}
    details = usage.get("prompt_tokens_details") or {}
    hit = usage.get("prompt_cache_hit_tokens", details.get("cached_tokens", 0)) or 0
    miss = usage.get("prompt_cache_miss_tokens", (usage.get("prompt_tokens") or 0) - hit)
    return (hit * PRICES["cache_hit"] + miss * PRICES["cache_miss"]
            + (usage.get("completion_tokens") or 0) * PRICES["output"]) / 1e6


def balance():
    """What's left in the Luminal wallet, in dollars, or None if it can't be read. Luminal settles
    asynchronously, so short-window changes aren't a precise meter."""
    try:
        with _open("/balance", timeout=20) as r:
            data = json.loads(r.read())
        return round(data.get("available_units", 0) / data.get("units_per_usd", UNITS_PER_USD), 3)
    except (LuminalError, json.JSONDecodeError, OSError):
        return None


def check():
    """A tiny request to see that the key and the model work. Returns (ok, message)."""
    try:
        started = time.time()
        reply = complete({"messages": [{"role": "user", "content": "Reply with exactly: pong"}], "max_tokens": 8})
        text = (reply["choices"][0]["message"].get("content") or "").strip()
        return True, f"Luminal answered \"{text}\" in {time.time() - started:.1f}s ({model()})."
    except LuminalError as e:
        return False, e.message


if __name__ == "__main__":       # python3 luminal.py: does the key work?
    from pathlib import Path
    env = Path(__file__).parent / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())
    ok, message = check()
    print(message)
    if ok:
        print(f"Balance: ${balance()}")
