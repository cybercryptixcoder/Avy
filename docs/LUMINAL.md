# Luminal: Avy's only model provider

Every model call Avy makes (her replies, her memory search, the background mind, the judge in the
benchmark, the import's run) goes to **Luminal**, a US-hosted endpoint serving one model,
**DeepSeek-V4.1-Flash**. DeepSeek's own API isn't used anywhere any more (the switch was made for the
data's safety). There's no other provider connected, and nothing to fall back to: one brain, one door.

The client is `luminal.py`. Everything below is either from Shreyas's notes on Luminal (four probe rounds
and about 2,900 production calls, Oct 14) or from Claude's own probes with synthetic prompts, and every
rule is enforced in code.

## Setting it up

Paste the key once in the page (the orange key button, top right). It's saved to `.env` next to
`app.py`, which is never committed. That's all.

`.env` can also be written by hand (see `.env.example`):

```
LUMINAL_API_KEY=lum_live_...
LUMINAL_BASE_URL=https://flash.luminal.cloud/v1        # optional, the default
HELIX_FLASH_MODEL=deepseek-ai/DeepSeek-V4.1-Flash      # optional, the default
```

`HELIX_PROVIDER` and `LOCAL_BASE_URL`, if present, are ignored: Luminal is the only provider.

`python3 luminal.py` checks the key: it asks for one word back and prints the balance.

## The rules, and what Avy does about each

| What Luminal does | What Avy does (`luminal.py`) |
|---|---|
| **Thinks by default.** Leave out `reasoning_effort` and hidden thinking eats the output budget (answers come back empty, cut off). | Every request carries `reasoning_effort`. `none` unless a setting says otherwise. |
| **A silent 8,192-token cap** when `max_tokens` is left out. Valid range 1 to 393,216. | Every request carries `max_tokens` (8,000 by default), clamped to the range. With thinking on, 24,000 more is added so the thinking can't eat the answer. |
| **Long non-streamed answers can die** after about 20 seconds. | Everything is streamed. The mind's calls are streamed too and put back together (`complete()`), so they look like ordinary answers. |
| **Rate limits are about concurrency.** 8 at once is safe; 12 brings some 429s; 16 many. Sequential calls are never refused. | At most 8 calls at once (a semaphore). 429s are retried. |
| **Transient failures**: 503 "the model is temporarily unavailable", dropped connections, an empty body, an error inside the stream. | All retried, 4 tries, backing off (2, 4, 8 seconds plus jitter). A replying stream is only retried before its first byte. |
| **A forced tool call is refused while thinking** (400: "Thinking mode does not support this tool_choice"; found by Claude's probe). | With thinking off, the mind forces its tool; with thinking on, it offers the tool (`auto`). |
| **JSON-schema output isn't available** ("This response_format type is unavailable now"); `json_object` and tool calls work. | The mind uses tool calls. If the model answers with plain JSON instead of the call, it's accepted. |
| **Context is 163,840 tokens**, and the endpoint doesn't say so. | Declared in code (`CONTEXT_TOKENS`). Avy's writer never sends more than about 120,000 tokens of log. |
| **Thinking shows up as `reasoning_content`**; usage arrives in the last streamed chunk with `include_usage`; `: ping` keep-alives. | Both are read; keep-alives skipped; the page shows "thinking…" while it thinks. |
| **Only `n = 1`**, temperature 0 to 2, unknown fields ignored. | Not used. |
| **Pictures work** (`image_url` with a data URL; Claude's probe: two at 1,568 px and eight at 768 px in one message, all described correctly). | Attached pictures and video frames go to the model this way (FILES.md). |
| **Prompt caching** shows in `prompt_tokens_details.cached_tokens` (3,840 of 4,015 cached on a repeat). | Costs count cached tokens at the cache price. Avy's prompts put what doesn't change first. |
| **401/403** for a bad key, **402** for an empty wallet. | Said plainly on the page: paste a fresh key / top up. |
| **No published price per token.** The wallet (`GET /v1/balance`, units ÷ 10¹⁰ = dollars) is the truth, and it settles asynchronously. | Costs on the page are estimates at DeepSeek's own list price for V4.1-Flash ($0.30 per million input, $0.006 cached, $1.20 output). The top bar shows the real balance, checked once a minute. |
| **macOS Python may lack certificates.** | truststore (your computer's certificate store), else certifi, else Python's default. |

## Thinking, now that Flash is the only model

DeepSeek's Pro model isn't on Luminal, so where Avy used to pick Flash or Pro, she now picks how hard
Flash thinks: `none`, `low`, `medium`, `high`, `xhigh`, `ultra`, `max`.

- **`/thinking:`** (on the system card): how hard Avy thinks before answering, and while she searches her
  memory. Default none: fast (about a second to start). Higher levels think for several seconds first.
- **`/mind:`** (a command): how hard the background mind thinks while it writes memory, connects and
  reflects. Default none. Its tool calls stay forced with none; with thinking on they're offered instead.
- **The benchmark's judge** thinks at `high` (it used to be Pro).
- **The import's run**: `--effort`, default none.

What thinking costs, roughly (Shreyas's measurements): for a ~200-word answer, none takes about 3.4
seconds and every thinking level about 10 to 12; thinking adds output tokens.

## Files

- `luminal.py`: the client. `prepare()` fills in the rules; `open_stream()` for replies; `complete()` for
  everything else; `balance()`; `check()`.
- `mind/llm.py`: the mind's one strict tool call, on top of it.
- `tests/test_luminal.py`: every rule above, offline (the request's shape, putting a stream back together,
  retries, costs, the mind's tool choice).
