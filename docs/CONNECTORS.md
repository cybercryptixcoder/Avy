# Connectors: toolboxes others built

Avy speaks the **Model Context Protocol** (MCP) as a client (`connectors.py`), so any MCP server is a toolbox she can
use: its tools come with the descriptions their makers wrote and tuned, which is most of the work of getting a model
to pick and use tools well. One is on by default:

| toolbox | what she gets | needs |
|---|---|---|
| `browser` (Microsoft's `@playwright/mcp`) | a real browser: navigate, read a page as an accessibility snapshot, find, click, type, fill forms, tabs, screenshots | Node.js (`npx`) |

**Adding one**: create `data/connectors.json` (it replaces the defaults, so keep `browser` in it if you want it):

```json
{"mcpServers": {
  "browser": {"command": "npx", "args": ["-y", "@playwright/mcp@latest", "--headless", "--isolated"],
              "about": "a real web browser", "ask": ["browser_fill_form", "browser_type", "browser_file_upload"]},
  "git":     {"command": "uvx", "args": ["mcp-server-git"], "about": "git in his repositories"},
  "github":  {"command": "npx", "args": ["-y", "@modelcontextprotocol/server-github"],
              "env": {"GITHUB_PERSONAL_ACCESS_TOKEN": "..."}, "about": "his GitHub: issues, pull requests, code"},
  "calendar": {"command": "npx", "args": ["-y", "@cocal/google-calendar-mcp"],
               "env": {"GOOGLE_OAUTH_CREDENTIALS": "/path/to/gcp-oauth.keys.json"},
               "about": "his Google Calendar", "ask": ["create-event", "update-event", "delete-event"]}
}}
```

- `about`: the one line she sees for it in her instructions (until she opens it).
- `ask`: tools that wait for your OK in the page before running (like the terminal's risky commands).
- `disabled: true` keeps an entry without starting it.
- Without `--headless` the browser opens a window you can watch.

The format is the one Claude Desktop and other MCP clients use, so a server's own README usually has the entry ready
to paste. Lists of servers: https://github.com/modelcontextprotocol/servers.

**How she uses them**: her instructions list each toolbox in one line; a single tool, `open_toolbox`, puts a
toolbox's own tools in front of her for the rest of that reply (so a 25-tool browser costs nothing until she needs it).
Each server starts the first time it's opened and stays up. Every call is kept with the reply, like her other steps.
`/hands: off` turns connectors off; incognito has none. `python3 connectors.py` starts each one and lists its tools.
