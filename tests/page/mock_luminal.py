# Fake Luminal for interface tests (memory v2), shaped like the real one: everything streamed, reasoning_effort
# decides thinking, a balance route, image parts accepted. Streams canned replies in the real SSE format (citing a
# remembered node as a footnote), and answers the mind's tool calls deterministically:
#   write_episode      one information node per message of Shreyas's; capitalized names become things
#   judge_connections  connects the first pair only
#   write_inferences   infers nothing
#   recheck            everything holds
#   explore_memory     round 1 reads the first node at the frontier; the last round keeps the first two, and two library passages
import json, re, sys, time
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
LOG = sys.argv[1]                  # every request, one JSON line each (the tests read it)
REPLY = ("Sure. I'm a fake Luminal, so I say the same thing every time. "
         "Ask me anything and I'll keep it short.")
MD_REPLY = '## Quick plan\nHere is **the important bit**: run `python3 app.py` first.\n- one\n- two, see [docs](https://example.com)\n\n```python\ndef hello():\n    return "<b>not html</b>"\n```\nDone.'
NOT_NAMES = {"I", "I'm", "Avy", "Okay", "Ok", "Yes", "No", "Hey", "Sure", "Also", "And", "The", "My", "So", "Wait", "Remember", "Fake"}


def write_episode(text):
    existing = {m.group(2).lower(): m.group(1) for m in re.finditer(r'^(k\d+) thing[^"]*"([^"]+)"', text, re.M)}
    stretch = text.split("The stretch to write", 1)[1]
    nodes, edges, things = [], [], {}
    for m in re.finditer(r"^#(\d+) .*?  (Shreyas|Avy): (.*)$", stretch, re.M):
        mid, who, said = int(m.group(1)), m.group(2), m.group(3)
        if who != "Shreyas":
            continue
        words = said.split()
        ref = f"n{len(nodes) + 1}"
        nodes.append({"ref": ref, "replaces": None, "shape": "information", "label": "note", "title": " ".join(words[:5]),
                      "text": said[:200], "when": None, "evidence": [{"message": mid, "quote": " ".join(words[:6])}]})
        for name in re.findall(r"\b([A-Z][a-z]{2,})\b", said):
            if name in NOT_NAMES or name == words[0]:
                continue
            if name.lower() in existing:
                target = existing[name.lower()]
            else:
                if name not in things:
                    things[name] = f"n{len(nodes) + 1}"
                    nodes.append({"ref": things[name], "replaces": None, "shape": "thing", "label": "person", "title": name,
                                  "text": "Someone Shreyas mentioned.", "when": None, "evidence": [{"message": mid, "quote": name}]})
                target = things[name]
            edges.append({"from": ref, "to": target, "kind": "part_of", "reason": f"it's about {name}", "said": None})
    first_user = re.search(r"Shreyas: (.*)", stretch)
    return {"headline": (first_user.group(1)[:50] if first_user else "Chat"), "nodes": nodes, "edges": edges}


def answer(body):
    name = body["tools"][0]["function"]["name"]
    text = body["messages"][-1]["content"] if body["messages"][-1]["role"] != "tool" else body["messages"][1]["content"]
    if name == "write_episode":
        return name, write_episode(body["messages"][1]["content"])
    if name == "judge_connections":
        pairs = re.findall(r"^(p\d+) ", text, re.M)
        return name, {"verdicts": [{"pair": p, "connect": i == 0, "kind": "related" if i == 0 else None, "from": None,
                                    "reason": "the mock connects the first pair it sees" if i == 0 else ""} for i, p in enumerate(pairs)]}
    if name == "write_inferences":
        return name, {"inferences": [], "edges": []}
    if name == "recheck":
        items = re.findall(r"^((?:k|c)\d+) ", text, re.M)
        return name, {"verdicts": [{"item": i, "verdict": "holds", "title": None, "text": None, "certainty": None, "kind": None,
                                    "reason": None, "why": "the mock says it holds"} for i in items]}
    if name == "explore_memory":
        frontier = re.findall(r"^([kx]\d+) \[", text, re.M)
        last = "This is the last round" in text
        time.sleep(0.4)
        shelf = re.findall(r"^\[(p\d+)\]", text, re.M)          # library passages its searches turned up
        if last:
            return name, {"task": "what the message needs (mock)", "questions": [], "open": [], "follow": [], "search": [],
                          "keep": [{"item": h, "why": "mock keeps it"} for h in frontier[:2] + shelf[:2]], "done": True}
        return name, {"task": "what the message needs (mock)", "questions": ["what else is there?"], "open": frontier[:1],
                      "follow": frontier[:1], "search": ["something related"], "keep": [], "done": False}
    return name, {}




def text_of(content):
    """A message's text, whether a string or a list of parts (text and image_url)."""
    if isinstance(content, list):
        return " ".join(p.get("text", "") for p in content if p.get("type") == "text")
    return content or ""


def images_in(messages):
    return sum(1 for m in messages if isinstance(m.get("content"), list) for p in m["content"] if p.get("type") == "image_url")


class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def send(self, code, data):
        out = json.dumps(data).encode()
        self.send_response(code); self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(out))); self.end_headers(); self.wfile.write(out)

    def do_GET(self):
        if self.headers.get("Authorization") == "Bearer lum_bad":
            return self.send(401, {"error": {"message": "invalid api key"}})
        if self.path.endswith("/balance"):
            return self.send(200, {"available_units": 9_939_000_000_000, "units_per_usd": 10_000_000_000})
        if self.path.endswith("/models"):
            return self.send(200, {"object": "list", "data": [{"id": "deepseek-ai/DeepSeek-V4.1-Flash", "object": "model"}]})
        self.send(404, {"error": {"message": "not found"}})

    def chunk(self, body, delta, finish=None, usage=None):
        c = {"id": "x", "object": "chat.completion.chunk", "created": 1, "model": body["model"],
             "choices": [] if delta is None else [{"index": 0, "delta": delta, "finish_reason": finish}]}
        if usage:
            c["usage"] = usage
        self.wfile.write(f"data: {json.dumps(c)}\n\n".encode()); self.wfile.flush()

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        open(LOG, "a").write(json.dumps({"path": self.path, "auth": self.headers.get("Authorization"), "body": body,
                                         "images": images_in(body.get("messages", []))}) + "\n")
        if self.headers.get("Authorization") == "Bearer lum_bad":
            return self.send(401, {"error": {"message": "invalid api key"}})
        if not body.get("stream") or "reasoning_effort" not in body or "max_tokens" not in body:
            return self.send(400, {"error": {"message": "mock: Avy must always stream and send reasoning_effort and max_tokens"}})
        if body["reasoning_effort"] != "none" and isinstance(body.get("tool_choice"), dict):
            return self.send(400, {"error": {"message": "Thinking mode does not support this tool_choice"}})
        self.send_response(200); self.send_header("Content-Type", "text/event-stream"); self.end_headers()
        self.wfile.write(b": ping\n\n"); self.wfile.flush()
        thinking = body["reasoning_effort"] != "none"
        if thinking:
            for w in ["Let", " me", " think", " about", " this."]:
                self.chunk(body, {"reasoning_content": w}); time.sleep(0.15)
        if body.get("tools"):
            for m in body["messages"]:
                m["content"] = text_of(m.get("content"))
            name, args = answer(body)
            time.sleep(0.2)
            raw = json.dumps(args)
            self.chunk(body, {"role": "assistant", "tool_calls": [{"index": 0, "id": "call_1", "type": "function",
                                                                   "function": {"name": name, "arguments": raw[:len(raw) // 2]}}]})
            self.chunk(body, {"tool_calls": [{"index": 0, "function": {"arguments": raw[len(raw) // 2:]}}]}, finish="tool_calls")
            self.chunk(body, None, usage={"prompt_tokens": 1500, "completion_tokens": 300, "total_tokens": 1800,
                                          "prompt_tokens_details": {"cached_tokens": 1024}})
            self.wfile.write(b"data: [DONE]\n\n"); self.wfile.flush()
            return
        last = text_of(body["messages"][-1]["content"])
        note = text_of(body["messages"][-2]["content"]) if len(body["messages"]) > 1 and body["messages"][-2]["role"] == "system" else ""
        seen = images_in(body["messages"])
        recalled = re.search(r"^\[([kx]\d+)\] (.+?) \(", note, re.M)
        reply = MD_REPLY if "markdown" in last else (f"From memory: {recalled.group(2)}[{recalled.group(1)}]. " + REPLY) if recalled else REPLY
        if seen:
            reply = f"I can see {seen} image{'s' if seen > 1 else ''}. " + reply
        if "miscite" in last:                    # a footnote to something that wasn't in the note (the page marks it)
            reply += " And this one too[k999]."
        files = re.findall(r'<file name="([^"]+)"', "\n".join(text_of(m.get("content")) for m in body["messages"][-1:]))
        if files:
            reply = f"I read {', '.join(sorted(set(files)))}. " + reply
        words = reply.split(" ")
        if "long" in last or "remind" in last.lower():
            words = words * 8
        for i, w in enumerate(words):
            self.chunk(body, {"content": (w if i == 0 else " " + w)}); time.sleep(0.03)
        self.chunk(body, {}, finish="stop")
        usage = {"prompt_tokens": 180, "completion_tokens": 48, "total_tokens": 228, "prompt_tokens_details": {"cached_tokens": 128}}
        self.chunk(body, None, usage=usage)
        self.wfile.write(b": ping\n\ndata: [DONE]\n\n"); self.wfile.flush()


ThreadingHTTPServer(("127.0.0.1", 9999), H).serve_forever()
