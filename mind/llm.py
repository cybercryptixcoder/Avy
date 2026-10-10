"""How the mind calls DeepSeek: one strict tool call at a time, with the cost counted."""

import json
import time

MODEL = "deepseek-flash"
app = {"ask": None,       # filled in by app.py (or a test): sends one request, returns DeepSeek's reply as a dict
       "prices": {}}      # dollars per million tokens, per model


def call(convo, tool, model=MODEL, max_tokens=8000):
    """Ask for exactly one call to `tool`. Thinking is off: DeepSeek only allows a forced tool call without it."""
    payload = {"model": model, "messages": convo, "tools": [tool], "max_tokens": max_tokens,
               "thinking": {"type": "disabled"},
               "tool_choice": {"type": "function", "function": {"name": tool["function"]["name"]}}}
    try:
        return app["ask"](payload)
    except Exception as e:                 # one retry: connections through proxies sometimes drop mid-request
        if getattr(e, "status", 502) not in (502, 503, 504, 429) or "rejected the key" in str(e):
            raise
        time.sleep(2)
        return app["ask"](payload)


def read_call(reply, name):
    """Pull the tool call's arguments out of DeepSeek's reply. Returns (answer, problem)."""
    choice = (reply.get("choices") or [{}])[0]
    msg = choice.get("message") or {}
    calls = [c for c in msg.get("tool_calls") or [] if (c.get("function") or {}).get("name") == name]
    if choice.get("finish_reason") == "length":
        return None, "Your answer was cut off because it was too long. Keep it shorter."
    if not calls:
        return None, f"You didn't call {name}. Answer only by calling it."
    try:
        return json.loads(calls[0]["function"]["arguments"]), None
    except (json.JSONDecodeError, TypeError) as e:
        return None, f"The {name} arguments weren't valid JSON ({e})."


def cost(usage, model=MODEL):
    price = app["prices"].get(model, {})
    hit = usage.get("prompt_cache_hit_tokens", 0)
    miss = usage.get("prompt_cache_miss_tokens", usage.get("prompt_tokens", 0) - hit)
    return (hit * price.get("cache_hit", 0) + miss * price.get("cache_miss", 0)
            + usage.get("completion_tokens", 0) * price.get("output", 0)) / 1e6


def tool(name, description, properties, required=None):
    """A strict tool definition (the shape DeepSeek's answer must take)."""
    return {"type": "function", "function": {
        "name": name, "description": description, "strict": True,
        "parameters": {"type": "object", "properties": properties,
                       "required": required or list(properties), "additionalProperties": False}}}


def obj(properties, required=None):
    return {"type": "object", "properties": properties, "required": required or list(properties), "additionalProperties": False}


def nullable(schema):
    return {"anyOf": [schema, {"type": "null"}]}
