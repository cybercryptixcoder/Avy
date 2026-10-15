"""Offline checks of the Luminal client (luminal.py) and the mind's calls (mind/llm.py): the shape of every
request, putting a streamed answer back together, retries, and costs. No network.

    python3 tests/test_luminal.py
"""

import os
import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import luminal  # noqa: E402
from mind import llm  # noqa: E402

fails = []


def ok(name, condition, detail=""):
    print(("ok    " if condition else "FAIL  ") + name + ("" if condition else f"   ({detail})"))
    if not condition:
        fails.append(name)


# --- 1. what every request carries ---------------------------------------------------------------
p = luminal.prepare({"messages": [], "thinking": {"type": "disabled"}})
ok("every request names the model, an explicit max_tokens and reasoning_effort (DeepSeek's own switch is dropped)",
   p["model"] == luminal.model() and p["max_tokens"] == 8000 and p["reasoning_effort"] == "none" and "thinking" not in p, p)
forced = {"type": "function", "function": {"name": "f"}}
p = luminal.prepare({"messages": [], "max_tokens": 2000, "tool_choice": forced}, effort="high")
ok("thinking on: a forced tool call becomes auto (Luminal refuses a forced one while thinking), with room to think",
   p["tool_choice"] == "auto" and p["max_tokens"] == 2000 + luminal.THINKING_ROOM, p)
ok("thinking off: the tool stays forced", luminal.prepare({"messages": [], "tool_choice": forced})["tool_choice"] == forced)
ok("an unknown thinking level falls back to none", luminal.prepare({"messages": []}, effort="huge")["reasoning_effort"] == "none")
ok("max_tokens stays inside Luminal's range", luminal.prepare({"messages": [], "max_tokens": 10 ** 7})["max_tokens"] == luminal.MAX_OUTPUT)
ok("the model and address can be changed in .env", (os.environ.update(HELIX_FLASH_MODEL="x/y") or luminal.model()) == "x/y")
os.environ.pop("HELIX_FLASH_MODEL")

# --- 2. a streamed answer, put back together -------------------------------------------------------
LINES = [b": ping", b"",
         b'data: {"choices":[{"index":0,"delta":{"role":"assistant","reasoning_content":"hmm "}}]}',
         b'data: {"choices":[{"index":0,"delta":{"content":"Hel"}}]}',
         b'data: {"choices":[{"index":0,"delta":{"content":"lo"}}]}',
         b'data: {"choices":[{"index":0,"delta":{"tool_calls":[{"index":0,"id":"call_1","type":"function","function":{"name":"save","arguments":"{\\"a\\""}}]}}]}',
         b'data: {"choices":[{"index":0,"delta":{"tool_calls":[{"index":0,"function":{"arguments":": 1}"}}]},"finish_reason":"tool_calls"}]}',
         b'data: {"choices":[],"usage":{"prompt_tokens":10,"completion_tokens":5,"prompt_tokens_details":{"cached_tokens":4}}}',
         b"data: [DONE]"]
r = luminal.assemble(LINES)
m = r["choices"][0]["message"]
ok("a stream is put back together: words, thinking, the tool call, how it finished, and usage",
   m["content"] == "Hello" and m["reasoning_content"] == "hmm " and m["tool_calls"][0]["function"] == {"name": "save", "arguments": '{"a": 1}'}
   and r["choices"][0]["finish_reason"] == "tool_calls" and r["usage"]["prompt_tokens"] == 10, r)
try:
    luminal.assemble([b'data: {"error": {"message": "the model is temporarily unavailable"}}'])
    ok("an error inside the stream is retried", False)
except luminal.LuminalError as e:
    ok("an error inside the stream is retried", e.retryable)
try:
    luminal.assemble([b": ping", b"data: [DONE]"])
    ok("an empty answer is retried", False)
except luminal.LuminalError as e:
    ok("an empty answer is retried", e.retryable)
ok("a reply's words skip keep-alives and thinking",
   luminal.stream_text(b": ping") == ("", None)
   and luminal.stream_text(b'data: {"choices":[{"delta":{"reasoning_content":"x"}}]}')[0] == ""
   and luminal.stream_text(b'data: {"choices":[{"delta":{"content":"hi"}}]}')[0] == "hi")


# --- 3. retries -------------------------------------------------------------------------------------
class FakeResponse:
    def __init__(self, lines):
        self.lines = lines

    def __iter__(self):
        return iter(self.lines)

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


real_open, real_time = luminal._open, luminal.time
luminal.time = types.SimpleNamespace(sleep=lambda s: None, time=real_time.time)
calls = []


def flaky(path, body=None, timeout=180):
    calls.append(body)
    if len(calls) < 3:
        raise luminal.LuminalError(429, "rate limit exceeded, retry after the indicated delay", retryable=True)
    return FakeResponse(LINES)


luminal._open = flaky
r = luminal.complete({"messages": [{"role": "user", "content": "hi"}]})
ok("429s are retried until it works", len(calls) == 3 and r["choices"][0]["message"]["content"] == "Hello", len(calls))
ok("...and the request was streamed, with usage, effort and max_tokens", calls[0]["stream"] is True and calls[0]["stream_options"]
   == {"include_usage": True} and calls[0]["reasoning_effort"] == "none" and calls[0]["max_tokens"] == 8000)
calls.clear()


def dropped(path, body=None, timeout=180):
    calls.append(1)

    class Broken(FakeResponse):
        def __iter__(self):
            yield LINES[2]
            raise ConnectionResetError("Connection reset by peer")
    return Broken([]) if len(calls) == 1 else FakeResponse(LINES)


luminal._open = dropped
ok("a stream that drops partway is asked again", luminal.complete({"messages": []})["choices"][0]["message"]["content"] == "Hello" and len(calls) == 2)
calls.clear()


def refused(path, body=None, timeout=180):
    calls.append(1)
    raise luminal.LuminalError(401, "Luminal rejected the key. Paste a fresh one in Keys.")


luminal._open = refused
try:
    luminal.complete({"messages": []})
    ok("a rejected key isn't retried", False)
except luminal.LuminalError as e:
    ok("a rejected key isn't retried", len(calls) == 1 and "Keys" in e.message)
luminal._open, luminal.time = real_open, real_time
saved_key = os.environ.pop(luminal.KEY_NAME, None)
try:
    luminal._open("/chat/completions", {})
    ok("without a key, it says where to add one", False)
except luminal.LuminalError as e:
    ok("without a key, it says where to add one", "key" in e.message and not e.retryable)
if saved_key:
    os.environ[luminal.KEY_NAME] = saved_key

# --- 4. cost ---------------------------------------------------------------------------------------
ok("cached input is priced at the cache price",
   abs(luminal.cost({"prompt_tokens": 1_000_000, "completion_tokens": 0, "prompt_tokens_details": {"cached_tokens": 1_000_000}})
       - luminal.PRICES["cache_hit"]) < 1e-9)
ok("the rest at the normal price", abs(luminal.cost({"prompt_tokens": 1_000_000, "completion_tokens": 1_000_000})
                                        - luminal.PRICES["cache_miss"] - luminal.PRICES["output"]) < 1e-9)

# --- 5. the mind's calls --------------------------------------------------------------------------
tool = llm.tool("save", "save it", {"a": {"type": "integer"}})
llm.app.update(ask=lambda payload: payload, prices=luminal.PRICES, effort=lambda: "none")
p = llm.call([{"role": "user", "content": "x"}], tool)
ok("the mind, thinking off: the tool is forced", p["tool_choice"] == {"type": "function", "function": {"name": "save"}} and p["reasoning_effort"] == "none")
llm.app.update(effort=lambda: "high")
p = llm.call([{"role": "user", "content": "x"}], tool)
ok("the mind, thinking on (/mind: high): the tool is offered, not forced", p["tool_choice"] == "auto" and p["reasoning_effort"] == "high")
ok("an answer given as JSON instead of the call is still taken",
   llm.read_call({"choices": [{"message": {"content": '{"a": 1}'}, "finish_reason": "stop"}]}, "save") == ({"a": 1}, None))
ok("...but no answer at all is sent back", llm.read_call({"choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}]}, "save")[1]
   == "You didn't call save. Answer only by calling it.")
ok("the mind's cost uses the same prices", abs(llm.cost({"prompt_tokens": 1_000_000, "completion_tokens": 0}) - luminal.PRICES["cache_miss"]) < 1e-9)

print(f"\n{len(fails)} failed" + (": " + ", ".join(fails) if fails else ""))
sys.exit(1 if fails else 0)
