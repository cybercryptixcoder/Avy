# Herself: one graph, and her own code

## Everything she knows is one graph (atlas.py)

Each kind of knowledge keeps the shape that suits it: memory's knowledge is a network, the persona is a graph of three
hubs, the calendar is a timeline, each thread holds a plan tree, the conversation is a log, and her code is a graph of
files and functions. The atlas copies none of them. It gives every node a handle and asks the store that node lives in
for its neighbours, so `graph_look` can start at the root and walk anywhere:

    avy → self | persona (him, her, us) | knowledge | calendar | threads | log | library
    k12  memory    pa7  persona    t3  calendar    th4  thread    m120  message    c:app.py:Turn.ask  code

Code builds every edge. The model only chooses where to look.

## Her code as a graph (selfcode.py)

The graph is built from the files as they are now, and rebuilt whenever one of them changes:

- **Nodes:** files, classes, functions and methods (Python, via `ast`), the page's script functions (index.html),
  the server's endpoints (`/api/...`), and documents with their headings.
- **Edges:** contains, imports, calls (resolved by name), calls_api (from a page function to an endpoint),
  serves (from an endpoint to app.py), and mentions (from a document to the files it names).

Her tools (when `/hands` isn't off):

| tool | what it does |
|---|---|
| `self_look` | Shows the architecture at a glance, one node and everything it connects to, or a search. |
| `self_read` | Reads a node's source (a whole function or class) or a file's lines. |
| `self_edit` | Makes an exact replacement or writes a whole file, always with a reason. Python and JSON are checked *before* writing, and each change is its own git commit (`Avy: <why>`). |
| `self_ops` | `check` (everything compiles, `app.py` imports, offline tests pass), `status`, `history`, `diff`, `revert`, `restart`. |

`restart` runs `check` first, then replaces the server with a fresh copy once the current reply ends. The page
reconnects on its own. A change to index.html shows on the next page reload.

Safety:

- She asks him on the page before every edit, revert and restart. With `/hands: trusted` she doesn't ask.
- CONSTITUTION.md always asks, whatever the setting.
- `.env`, `data/` and `.git` are never hers to edit.
- She commits locally and never pushes on her own. Pushing goes through the terminal, which asks.

So to change something about Avy, ask her. She finds where it lives, makes the smallest change, checks it, and restarts.

# Plain chat (chats.py, /mode: chat)

The **Avy | Chat** toggle at the top switches modes; `/mode: chat` does the same. In chat mode Avy is an ordinary
chatbot. Her memory, persona, desk and tools are all off.

- Each conversation stands alone. Conversations live in `data/chats.db` and are listed on the left: **+ new** starts one,
  double-click renames, ✕ deletes.
- The model reads only the newest messages that fit `/chatwindow` (8k to 128k tokens; 32k by default). The page notes
  when older messages fall out of the window.

# Running on a server

| variable | what it sets |
|---|---|
| `AVY_PASSWORD` | When set, the page asks for this password first. Set it whenever Avy is reachable from outside the machine, because her hands run commands there. |
| `AVY_PORT` | The port (8000 by default). |
| `AVY_HOST` | The address to listen on (127.0.0.1 by default; a tunnel such as cloudflared reaches it there). |
| `AVY_NO_BROWSER=1` | Doesn't try to open a browser. |

All four can go in the environment, and `AVY_PASSWORD` can also go in `.env`. Requests coming through a tunnel are
accepted when their Origin matches the Host they were sent to. Requests from other websites are refused.
