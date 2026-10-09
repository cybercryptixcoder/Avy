# Later

Ideas we've decided to build, but not yet. Each one says when it makes sense to pick it up.

## The living graph

*After memory v2 (the network) exists.*

The corner ASCII scope becomes a tiny view of Avy's memory network: zoomed out, floating, its nodes
drifting gently up and down like something breathing. It doesn't have to be accurate at that size;
if it is, it's just the real graph seen from very far away.

Click it and it opens into a full-page 3D view of the whole network:

- **Real nodes and edges,** not ASCII. Hubs are where many things meet; clusters are related things;
  long edges reach distant parts.
- **Light labels only.** Enough to tell things apart; hover a node to see what it holds (its title,
  a one-line preview, whether you said it or Avy inferred it), hover an edge to see why it exists.
- **Click to go deeper:** a node opens like a wiki page (the inspector), and from there to the exact
  words in the log.
- **Watch it think.** When Avy searches memory, or reflects in the background, the nodes and edges it
  visits light up as it goes: the path it explored, the branches it dug into, where it stopped.
- **Watch it change.** New connections forming, weak ones fading, ideas crystallizing from the things
  they connect.

The look matters as much as the function. It should feel like a living thing in a quiet sci-fi film,
not a Python plot with labels and not neon cyberpunk. Same palette, texture and grain as the rest of
the page: the cream paper, the ink, the printed feel of the ASCII scope, made of real geometry.

It's also a tool: the most intuitive way to see whether the network Avy builds is any good, spot an
island or a hub that swallows everything, and explore what she knows.

## Smaller ones

- **"Keep this" from incognito.** Before ending an incognito conversation, promote chosen messages
  into the main memory, so nothing is lost by accident.
- **Recall depth as a ceiling.** Once Avy searches memory herself, `/recall:` becomes the most she may
  dig, and she decides how much each message needs ("what time is it?" shouldn't trigger a deep dig).
- **Beliefs over time.** Nothing is ever deleted, so the network at any past moment can be rebuilt:
  "what did you believe about my sleep a month ago?", "how has your picture of this project changed?"
