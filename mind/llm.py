"""How the mind calls the model (DeepSeek-V4.1-Flash, through Luminal): one strict tool call at a time,
with the cost counted.

How hard the model thinks is the "effort" (Luminal's reasoning_effort: none, or DeepSeek's three levels
low, high, max). With "none" the call names the tool it must use. With thinking on, Luminal doesn't allow
that, so the tool is offered ("auto") and the instructions, plus the repair loop in jobs.py, make sure
it's used.
"""

import json
import time

MODEL = "deepseek-ai/DeepSeek-V4.1-Flash"     # the only model Luminal serves
app = {"ask": None,                 # filled in by app.py (or a test): sends one request, returns the reply as a dict
       "prices": {},                # dollars per million tokens: cache_hit, cache_miss, output
       "effort": lambda: "none"}    # how hard the background mind thinks (the /mind: setting)


def call(convo, tool, model=MODEL, max_tokens=8000, effort=None):
    """Ask for exactly one call to `tool`. effort: how hard to think (default: the /mind: setting)."""
    import luminal
    effort = luminal.effort_level(effort or app["effort"]() or "none")
    payload = {"model": model, "messages": convo, "tools": [tool], "max_tokens": max_tokens,
               "reasoning_effort": effort,
               "tool_choice": ({"type": "function", "function": {"name": tool["function"]["name"]}}
                               if effort == "none" else "auto")}
    try:
        return app["ask"](payload)
    except Exception as e:                 # one more try on top of the client's own retries
        if getattr(e, "status", 502) not in (502, 503, 504, 429) or "rejected the key" in str(e):
            raise
        time.sleep(2)
        return app["ask"](payload)


def read_call(reply, name):
    """Pull the tool call's arguments out of the reply. Returns (answer, problem)."""
    choice = (reply.get("choices") or [{}])[0]
    msg = choice.get("message") or {}
    calls = [c for c in msg.get("tool_calls") or [] if (c.get("function") or {}).get("name") == name]
    if choice.get("finish_reason") == "length" and not calls:
        return None, "Your answer was cut off because it was too long. Keep it shorter."
    if not calls:
        content = (msg.get("content") or "").strip()
        if content.startswith("{"):        # thinking on, it answered with the JSON itself instead of the call
            try:
                return json.loads(content), None
            except json.JSONDecodeError:
                pass
        return None, f"You didn't call {name}. Answer only by calling it."
    try:
        return json.loads(calls[0]["function"]["arguments"]), None
    except (json.JSONDecodeError, TypeError) as e:
        return None, f"The {name} arguments weren't valid JSON ({e})."


def cost(usage, model=MODEL):
    """Estimated dollars for one call (Luminal publishes no per-token price; see luminal.PRICES)."""
    price = app["prices"].get(model, app["prices"]) if isinstance(app["prices"].get(model), dict) else app["prices"]
    usage = usage or {}
    details = usage.get("prompt_tokens_details") or {}
    hit = usage.get("prompt_cache_hit_tokens", details.get("cached_tokens", 0)) or 0
    miss = usage.get("prompt_cache_miss_tokens", (usage.get("prompt_tokens") or 0) - hit)
    return (hit * price.get("cache_hit", 0) + miss * price.get("cache_miss", 0)
            + (usage.get("completion_tokens") or 0) * price.get("output", 0)) / 1e6


def tool(name, description, properties, required=None):
    """A strict tool definition (the shape the answer must take)."""
    return {"type": "function", "function": {
        "name": name, "description": description, "strict": True,
        "parameters": {"type": "object", "properties": properties,
                       "required": required or list(properties), "additionalProperties": False}}}


def obj(properties, required=None):
    return {"type": "object", "properties": properties, "required": required or list(properties), "additionalProperties": False}


def nullable(schema):
    return {"anyOf": [schema, {"type": "null"}]}
