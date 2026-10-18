# Avy's hands, her instruments, and her toolboxes

What Avy can do, not just say. Three kinds of things, split by who keeps the books:

| | what | who keeps it | where |
|---|---|---|---|
| **instruments** | the clock, the calendar (timeline), threads with plan trees, background jobs, the length gauge, the persona | code: always on her desk, every message | `memory/desk.py`, `memory/persona.py` |
| **hands** | terminal, files, Python, web search and fetch, background jobs, playbooks | she calls them when a task needs them | `hands.py`, `playbooks/` |
| **toolboxes** | packaged tools others built (a real browser by default; git, GitHub, calendars…) | she opens one when needed | `connectors.py`, `docs/CONNECTORS.md` |

His principle (Oct 16): *instruments, not tools*. "Having a calendar with that tracked is better than expecting an LLM
to track things over time." Anything code can keep the books on, code keeps the books on.

## What was learned from Hermes Agent and OpenClaw (Oct 17)

Concepts only, no code (the house rule). Read from Hermes Agent's source (tool schemas in `tools/`, prompt blocks in
`agent/prompt_builder.py`) and an architecture walkthrough of OpenClaw.

- **Tool descriptions do most of the steering.** Hermes's terminal description says what persists (the working
  directory), what to use instead (its file tools rather than cat/grep/sed), and when to background a command; its
  web_extract says snippets aren't the page. Avy's tools follow the same shape: what it does, when to use it, what
  not to use it for.
- **Models like DeepSeek describe instead of doing.** Hermes adds execution guidance for exactly these model families:
  act now instead of promising, never answer arithmetic, dates, current facts or system state from memory, keep going
  until it's checked, never fabricate output, report blockers honestly, batch independent calls. Avy's "Your hands"
  section carries this, in her voice.
- **Progressive disclosure.** Hermes loads skills on demand; OpenClaw puts a skills list in the prompt. Avy's
  playbooks (coding, research, long runs, files and data) are listed in a line each and read when needed; toolboxes
  open the same way.
- **Long output is cut to head and tail, the whole saved to a file** she can page through.
- **Two safety tiers.** Hermes and OpenClaw block a small set outright and ask approval for risky commands. Avy:
  *blocked* (wiping a disk or home, formatting, fork bombs, shutdown) never runs; *ask* (sudo, installs, pushing,
  deleting outside her workspace, touching keys or shell settings, sending data out) waits for his OK on a card in the
  conversation. Secrets aren't read. `/hands: ask | trusted | off`.
- **Background jobs with notification on exit.** Avy's go further: a job tied to a thread writes its end onto the
  thread, and she picks the thread up herself (an interrupt), which is the long-horizon multitasking case (VISION §10).

No packaged "toolbox" exists for Hermes's tools (they live inside Hermes). The packaged-toolbox idea is what MCP is,
so Avy became an MCP client: see docs/CONNECTORS.md.

## Her hands, in detail

| tool | does | notes |
|---|---|---|
| terminal | bash in her workspace (`data/workspace`) | cwd carries over; `background=true` starts a job (j3), optionally tied to a thread |
| jobs | list, status, wait, stop | reading a finished job marks it seen (no interrupt) |
| read_file, write_file, edit_file, find_files | files, PDFs as text, folder listings | writing outside the workspace asks; Python and JSON checked for syntax |
| python | runs a short program | for any arithmetic, dates, data |
| web_search | titles, addresses, snippets | ddgs (no key); `AVY_SEARXNG` or `BRAVE_API_KEY` if set |
| web_fetch | a page or PDF as text | head and tail when long |
| playbook | reads `playbooks/<name>.md` | coding, research, long-runs, files-and-data |
| timeline, thread | her instruments | `mind/instruments.py` |
| open_toolbox | a connector's tools for the rest of the reply | `connectors.py` |

A reply can take up to 30 tool rounds; every call is kept (the `actions` table) and shown folded above the reply.

## Speaking first

`/proactive: on` (the default): when a background job tied to a thread ends, she picks the thread up and says what the
result means (unless she already read it); a reminder speaks at its time, a timed event an hour before, a deadline at
9 AM on its day. The event is her prompt, never saved as his words; her reply is saved with what woke her.
