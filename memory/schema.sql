-- Avy's memory, version 2. One SQLite file per memory: data/memory-v2.db for the main one,
-- one in data/incognito/ while an incognito conversation is going.
--
--   THE LOG        messages     every message, word for word. Never edited, never deleted.
--                  episodes     stretches of the log (within one sitting), each with a headline.
--   KNOWLEDGE      nodes        what's worth knowing, one claim or one thing per node. A change is a new
--                               version of the node; the old versions stay.
--                  evidence     for what was said: the exact words in the log (copied by code).
--                  basis        for what Avy inferred: the nodes the inference rests on.
--   THE NETWORK    edges        connections between nodes, each with a kind and a reason.
--                  supports     every reason to believe (or doubt) a connection. Its strength is
--                               computed from these; nothing is ever deleted.
--   WHAT HAPPENED  runs, journal, recalls, health, judged, marks
--   SEARCH         words, vectors
--
-- Handles, everywhere (database, inspector, what DeepSeek sees):
--   #41  message 41     k12  node 12 (its chain: every version)     c7  connection 7     ep4  episode 4
-- In an incognito memory, nodes are x12 instead of k12, so the two can never be confused.

PRAGMA journal_mode = WAL;

-- THE LOG ------------------------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS messages (
  id    INTEGER PRIMARY KEY,                    -- #1, #2, ...
  at    TEXT NOT NULL,                          -- when, with time zone
  role  TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
  text  TEXT NOT NULL,
  via   TEXT NOT NULL DEFAULT 'text',           -- typed ('text') or spoken ('voice')
  meta  TEXT NOT NULL DEFAULT '{}'              -- model, tokens, cut off, which recall it used
);
CREATE TRIGGER IF NOT EXISTS log_is_permanent_1 BEFORE UPDATE ON messages
  BEGIN SELECT RAISE(ABORT, 'the log is append-only'); END;
CREATE TRIGGER IF NOT EXISTS log_is_permanent_2 BEFORE DELETE ON messages
  BEGIN SELECT RAISE(ABORT, 'the log is append-only'); END;

-- What Avy thought before she answered (the model's reasoning, when /thinking: isn't none). Permanent, like
-- the log: the log records what she said, this records why. It's the raw material of the thought graph
-- (ARCHITECTURE.md): later, conclusions will be written from it with pointers to the exact span they came from.
-- It is never sent back to the model as-is: what carries forward is what she concluded, not the thinking.
CREATE TABLE IF NOT EXISTS reasoning (
  id       INTEGER PRIMARY KEY,
  message  INTEGER REFERENCES messages(id),     -- the reply it led to (null: stopped before any reply came)
  asked    INTEGER REFERENCES messages(id),     -- the message she was answering
  at       TEXT NOT NULL,
  source   TEXT NOT NULL DEFAULT 'reply',       -- reply (her answer); later: search, mind
  effort   TEXT,                                -- the /thinking: level it ran at
  seconds  REAL,                                -- how long she thought before the first word of the answer
  tokens   INTEGER,                             -- reasoning tokens, when Luminal reports them
  text     TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS reasoning_by_message ON reasoning(message);
CREATE TRIGGER IF NOT EXISTS reasoning_is_permanent_1 BEFORE UPDATE ON reasoning
  BEGIN SELECT RAISE(ABORT, 'reasoning is append-only'); END;
CREATE TRIGGER IF NOT EXISTS reasoning_is_permanent_2 BEFORE DELETE ON reasoning
  BEGIN SELECT RAISE(ABORT, 'reasoning is append-only'); END;

CREATE TABLE IF NOT EXISTS episodes (
  id        INTEGER PRIMARY KEY,                -- ep1, ep2, ...
  first     INTEGER NOT NULL,                   -- the stretch of the log: #first to #last
  last      INTEGER NOT NULL,
  headline  TEXT NOT NULL,
  at        TEXT NOT NULL,
  run       INTEGER                             -- the run that wrote it
);

-- THE LIBRARY ----------------------------------------------------------------------------------------
-- What he added that wasn't said in this conversation: documents, papers, code, spreadsheets, recordings,
-- conversations he had elsewhere (with Claude, with people). Any format: intake.py reads it into passages,
-- kept word for word in order, like the log. Passages are searchable at once (words and meaning), so memory
-- can bring them back before any knowledge is written from them. Writing knowledge from them is a later step
-- (ARCHITECTURE.md, "The library").
CREATE TABLE IF NOT EXISTS sources (
  id      INTEGER PRIMARY KEY,                  -- s3
  name    TEXT NOT NULL,                        -- what he called it (the file or folder name)
  kind    TEXT NOT NULL,                        -- document, code, conversations, data, recording, mixed
  added   TEXT NOT NULL,
  came    TEXT,                                 -- where it came from: an attached file (f2026...), a folder, a path
  digest  TEXT,                                 -- a hash of what was read, so the same thing isn't added twice
  status  TEXT NOT NULL DEFAULT 'reading',      -- reading, stored (searchable), problem
  meta    TEXT NOT NULL DEFAULT '{}'            -- what the reader found: format, pages, files, conversations, speakers
);
CREATE TRIGGER IF NOT EXISTS sources_are_kept BEFORE DELETE ON sources
  BEGIN SELECT RAISE(ABORT, 'the library keeps what it was given'); END;

CREATE TABLE IF NOT EXISTS passages (
  id       INTEGER PRIMARY KEY,                 -- p41
  source   INTEGER NOT NULL REFERENCES sources(id),
  seq      INTEGER NOT NULL,                    -- its place in the source
  part     TEXT,                                -- where in it: "page 3", "src/app.py:120-180", "Trip planning · #12"
  speaker  TEXT,                                -- conversations: who said it, as the source names them
  role     TEXT,                                -- conversations: user (Shreyas), assistant, or other
  at       TEXT,                                -- when, if the source says
  text     TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS passages_by_source ON passages(source, seq);
CREATE TRIGGER IF NOT EXISTS passages_are_permanent_1 BEFORE UPDATE ON passages
  BEGIN SELECT RAISE(ABORT, 'passages are append-only'); END;
CREATE TRIGGER IF NOT EXISTS passages_are_permanent_2 BEFORE DELETE ON passages
  BEGIN SELECT RAISE(ABORT, 'passages are append-only'); END;

-- KNOWLEDGE ----------------------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS nodes (
  id        INTEGER PRIMARY KEY,                -- this version (a row)
  chain     INTEGER NOT NULL,                   -- the node itself: the id of its first version. k12 = chain 12
  version   INTEGER NOT NULL,                   -- 1, 2, 3 ...
  replaces  INTEGER UNIQUE REFERENCES nodes(id),-- the version this one follows. UNIQUE: a chain never forks
  state     TEXT NOT NULL DEFAULT 'active' CHECK (state IN ('active', 'retracted')),
  shape     TEXT NOT NULL CHECK (shape IN ('thing', 'information', 'idea')),
  label     TEXT NOT NULL DEFAULT '',           -- a free word or two, just for reading: "person", "plan"
  title     TEXT NOT NULL,
  text      TEXT NOT NULL,
  about     TEXT,                               -- the date it's about (YYYY-MM-DD), when there is one
  origin    TEXT NOT NULL CHECK (origin IN ('user', 'avy', 'inferred')),
                                                -- user: Shreyas said it. avy: Avy said it in conversation.
                                                -- inferred: Avy worked it out quietly. Decided by code.
  certainty TEXT CHECK (certainty IN ('likely', 'possible')),   -- inferred only
  depth     INTEGER NOT NULL DEFAULT 0,         -- steps from words actually said (said: 0)
  why       TEXT,                               -- for a new version or a retraction: what changed
  episode   INTEGER REFERENCES episodes(id),    -- the episode it was written from, if any
  run       INTEGER,
  at        TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS nodes_by_chain ON nodes(chain);
-- the newest version of every node (active or retracted)
CREATE VIEW IF NOT EXISTS heads AS
  SELECT * FROM nodes n WHERE NOT EXISTS (SELECT 1 FROM nodes x WHERE x.replaces = n.id);
-- what memory holds now: the newest version of every node that hasn't been retracted
CREATE VIEW IF NOT EXISTS current AS SELECT * FROM heads WHERE state = 'active';

CREATE TABLE IF NOT EXISTS evidence (           -- a node version -> the exact words in the log
  node     INTEGER NOT NULL REFERENCES nodes(id),
  message  INTEGER NOT NULL REFERENCES messages(id),
  start    INTEGER NOT NULL,                    -- where the words are in that message (characters)
  end      INTEGER NOT NULL,
  quote    TEXT NOT NULL,                       -- copied from the message by code, never by the model
  exact    INTEGER NOT NULL DEFAULT 1,          -- 0: the quote wasn't found, so this is the whole message
  PRIMARY KEY (node, message, start)
);
CREATE INDEX IF NOT EXISTS evidence_by_message ON evidence(message);

CREATE TABLE IF NOT EXISTS basis (              -- an inferred node version -> what it rests on
  node      INTEGER NOT NULL REFERENCES nodes(id),
  rests_on  INTEGER NOT NULL,                   -- a node (chain)
  seen      INTEGER NOT NULL REFERENCES nodes(id), -- the version of it that was checked last
  PRIMARY KEY (node, rests_on)
);
CREATE INDEX IF NOT EXISTS basis_by_rests_on ON basis(rests_on);

-- THE NETWORK --------------------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS edges (
  id      INTEGER PRIMARY KEY,                  -- c1, c2, ...
  a       INTEGER NOT NULL,                     -- node chains. part_of and builds_on point a -> b;
  b       INTEGER NOT NULL,                     --   like, against and related go both ways
  kind    TEXT NOT NULL CHECK (kind IN ('part_of', 'builds_on', 'like', 'against', 'related')),
  reason  TEXT NOT NULL,                        -- why, in one short sentence
  a_seen  INTEGER NOT NULL,                     -- the versions of each end it was last checked against
  b_seen  INTEGER NOT NULL,
  run     INTEGER,
  at      TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS one_edge_per_pair ON edges(min(a, b), max(a, b));
CREATE INDEX IF NOT EXISTS edges_by_a ON edges(a);
CREATE INDEX IF NOT EXISTS edges_by_b ON edges(b);

CREATE TABLE IF NOT EXISTS supports (           -- append-only: the history of every connection
  id      INTEGER PRIMARY KEY,
  edge    INTEGER NOT NULL REFERENCES edges(id),
  sign    INTEGER NOT NULL CHECK (sign IN (1, -1)),
  kind    TEXT NOT NULL CHECK (kind IN ('stated', 'confirmed', 'inferred', 'observed', 'used')),
                                                -- stated: Shreyas made the connection himself (quoted)
                                                -- confirmed: he agreed when it came up
                                                -- inferred: the model judged it
                                                -- observed: the two came up together again
                                                -- used: a search followed it and kept what it found
  source  TEXT,                                 -- '#41', 'run 12', 'recall 30'
  note    TEXT,
  run     INTEGER,
  at      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS supports_by_edge ON supports(edge);
CREATE TRIGGER IF NOT EXISTS supports_are_permanent_1 BEFORE UPDATE ON supports
  BEGIN SELECT RAISE(ABORT, 'supports are append-only'); END;
CREATE TRIGGER IF NOT EXISTS supports_are_permanent_2 BEFORE DELETE ON supports
  BEGIN SELECT RAISE(ABORT, 'supports are append-only'); END;

CREATE TABLE IF NOT EXISTS judged (             -- pairs the model was asked about, so it isn't asked twice
  a INTEGER NOT NULL, b INTEGER NOT NULL,       -- node chains, a < b
  a_seen INTEGER NOT NULL, b_seen INTEGER NOT NULL,  -- the versions it saw
  connect INTEGER NOT NULL, run INTEGER, at TEXT NOT NULL,
  PRIMARY KEY (a, b)
);

-- WHAT HAPPENED (so you can look under the hood) ----------------------------------------------------

CREATE TABLE IF NOT EXISTS runs (               -- every model job, start to finish
  id INTEGER PRIMARY KEY,
  job TEXT NOT NULL,                            -- write, connect, think, check, explore
  at TEXT NOT NULL,
  status TEXT NOT NULL,                         -- ok, repaired, partial, failed, error
  attempts INTEGER NOT NULL DEFAULT 0, model TEXT, seconds REAL,
  tokens_in INTEGER, tokens_out INTEGER, cost REAL,
  focus TEXT,                                   -- what it worked on, in words
  prompt TEXT, replies TEXT, problems TEXT      -- what the model saw, said, and what the checks found
);

CREATE TABLE IF NOT EXISTS journal (            -- every change anyone proposed, and what happened to it
  id INTEGER PRIMARY KEY,
  at TEXT NOT NULL,
  run INTEGER,
  op TEXT NOT NULL,                             -- add_node, retract_node, connect, oppose, revise_edge, reaffirm, ...
  target TEXT,                                  -- what it touched: 'k12', 'c7', 'ep4'
  args TEXT NOT NULL,                           -- the proposal, as JSON
  result TEXT NOT NULL,                         -- applied or rejected
  why TEXT                                      -- for a rejection: the rule it broke
);
CREATE INDEX IF NOT EXISTS journal_by_run ON journal(run);
CREATE INDEX IF NOT EXISTS journal_by_target ON journal(target);

CREATE TABLE IF NOT EXISTS recalls (            -- what memory brought to each of your messages
  id INTEGER PRIMARY KEY,
  message INTEGER NOT NULL,
  at TEXT NOT NULL,
  trace TEXT NOT NULL,                          -- what was found, and how it was reached
  briefing TEXT NOT NULL                        -- the exact memory note DeepSeek was given
);

CREATE TABLE IF NOT EXISTS health (             -- the shape of the network, measured after reflection
  id INTEGER PRIMARY KEY, at TEXT NOT NULL, run INTEGER, metrics TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS marks (              -- small bits of state: what reflection last looked at
  key TEXT PRIMARY KEY, value TEXT
);

-- THE PERSONA ---------------------------------------------------------------------------------------
-- Avy's model of the relationship: who she is with him, and what she's learned about how to be with him. A graph
-- of its own, next to the world's (knowledge): the same principles (versions, evidence, connections with reasons),
-- a different job. Searched by the kind of conversation and the topic, not shown whole; its strongest parts are
-- always in view (ARCHITECTURE.md §7).
--
--   persona            nodes, by aspect: core (who she is with him: one node that evolves), him (always true about
--                      him), preference (his rules for her), pattern (how he tends to work and talk), reaction (how he
--                      responds to specific things she does), gesture (her small moves that land with him), term (words
--                      the two of them coined, pointing at the message each was born in), situation (a kind of
--                      conversation), voice (a reply of hers that landed). Versioned chains: pa12 is a node.
--                      Each aspect has a fixed capacity and each node a fixed size: the persona grows in form, not size.
--   persona_evidence   the exact words each version rests on (copied by code, like knowledge's evidence)
--   persona_edges      connections with a kind and a reason: applies_in (a behavior and the situation it's for),
--                      supports / undercuts (his reaction and the gesture it bears on), refines (a specific rule and
--                      the general one), about (a term and the world-knowledge node it's about: k12), example_of
--   persona_seen       every time a connection was seen again (append-only): its strength is counted from these
--   persona_labels     which kind of conversation each of his messages was (a situation learns from its examples)

CREATE TABLE IF NOT EXISTS persona (
  id        INTEGER PRIMARY KEY,
  chain     INTEGER NOT NULL,                   -- pa12
  version   INTEGER NOT NULL,
  replaces  INTEGER UNIQUE REFERENCES persona(id),
  state     TEXT NOT NULL DEFAULT 'active' CHECK (state IN ('active', 'retired')),
  aspect    TEXT NOT NULL CHECK (aspect IN ('core', 'him', 'preference', 'pattern', 'reaction', 'gesture', 'term', 'situation', 'voice')),
  title     TEXT NOT NULL,                      -- a few words: "metric units", "the hinge", "late-night idea dumps"
  text      TEXT NOT NULL,                      -- one sentence (the core: a short paragraph)
  scope     TEXT,                               -- when it applies: 'always', or a situation's title
  origin    TEXT NOT NULL CHECK (origin IN ('user', 'avy', 'inferred', 'seed')),
                                                -- user: rests on his words. avy: her own judgment of her replies.
                                                -- inferred: a pattern worked out across sittings. seed: built in (situations)
  certainty TEXT CHECK (certainty IN ('likely', 'possible')),
  message   INTEGER REFERENCES messages(id),    -- voice: her reply. term: the message it was born in
  why       TEXT,
  by        TEXT NOT NULL DEFAULT 'mind',       -- keeper, character, seed, him (edited on the page)
  run       INTEGER,
  at        TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS persona_by_chain ON persona(chain);
CREATE TRIGGER IF NOT EXISTS persona_is_kept_1 BEFORE UPDATE ON persona
  BEGIN SELECT RAISE(ABORT, 'persona versions are append-only'); END;
CREATE TRIGGER IF NOT EXISTS persona_is_kept_2 BEFORE DELETE ON persona
  BEGIN SELECT RAISE(ABORT, 'persona versions are append-only'); END;

CREATE TABLE IF NOT EXISTS persona_evidence (
  node     INTEGER NOT NULL REFERENCES persona(id),
  message  INTEGER NOT NULL REFERENCES messages(id),
  start    INTEGER NOT NULL,
  end      INTEGER NOT NULL,
  quote    TEXT NOT NULL,                       -- copied from the message by code
  PRIMARY KEY (node, message, start)
);
CREATE INDEX IF NOT EXISTS persona_evidence_by_message ON persona_evidence(message);

CREATE TABLE IF NOT EXISTS persona_edges (
  id      INTEGER PRIMARY KEY,
  a       INTEGER NOT NULL,                     -- a persona chain
  b       INTEGER NOT NULL,                     -- a persona chain (for 'about': a knowledge chain, k12)
  kind    TEXT NOT NULL CHECK (kind IN ('applies_in', 'supports', 'undercuts', 'refines', 'about', 'example_of', 'related')),
  reason  TEXT NOT NULL,
  run     INTEGER,
  at      TEXT NOT NULL,
  UNIQUE (a, b, kind)
);
CREATE INDEX IF NOT EXISTS persona_edges_by_a ON persona_edges(a);
CREATE INDEX IF NOT EXISTS persona_edges_by_b ON persona_edges(b);

CREATE TABLE IF NOT EXISTS persona_seen (
  id       INTEGER PRIMARY KEY,
  edge     INTEGER NOT NULL REFERENCES persona_edges(id),
  message  INTEGER,
  note     TEXT,
  run      INTEGER,
  at       TEXT NOT NULL
);
CREATE TRIGGER IF NOT EXISTS persona_seen_is_kept_1 BEFORE UPDATE ON persona_seen
  BEGIN SELECT RAISE(ABORT, 'persona_seen is append-only'); END;
CREATE TRIGGER IF NOT EXISTS persona_seen_is_kept_2 BEFORE DELETE ON persona_seen
  BEGIN SELECT RAISE(ABORT, 'persona_seen is append-only'); END;

CREATE TABLE IF NOT EXISTS persona_labels (    -- which kind of conversation each of his messages was: how a situation learns his
  id        INTEGER PRIMARY KEY,                -- way of talking about it (the next message is classified by the closest examples)
  message   INTEGER NOT NULL REFERENCES messages(id),
  situation INTEGER NOT NULL,                   -- a situation chain (pa3)
  by        TEXT NOT NULL DEFAULT 'keeper',
  run       INTEGER,
  at        TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS persona_labels_by_situation ON persona_labels(situation);
CREATE TRIGGER IF NOT EXISTS persona_labels_are_kept_1 BEFORE UPDATE ON persona_labels
  BEGIN SELECT RAISE(ABORT, 'persona_labels is append-only'); END;
CREATE TRIGGER IF NOT EXISTS persona_labels_are_kept_2 BEFORE DELETE ON persona_labels
  BEGIN SELECT RAISE(ABORT, 'persona_labels is append-only'); END;

-- THE DESK'S INSTRUMENTS -----------------------------------------------------------------------------
--   timeline   dated things: events, deadlines, reminders, and tasks. Versioned like knowledge (t12 = its chain).
--   threads    work in flight, one row per version: the goal, where it stands, the next step, what it waits on,
--              the insights behind it, and a plan tree (steps and options; dead ends kept with their reasons), so a
--              task can be picked up exactly where it was left (th3).

CREATE TABLE IF NOT EXISTS timeline (
  id       INTEGER PRIMARY KEY,                 -- this version
  chain    INTEGER NOT NULL,                    -- the item itself: t12
  version  INTEGER NOT NULL,
  replaces INTEGER UNIQUE REFERENCES timeline(id),
  title    TEXT NOT NULL,
  kind     TEXT NOT NULL CHECK (kind IN ('event', 'deadline', 'reminder', 'task')),
  start    TEXT,                                -- YYYY-MM-DD, or YYYY-MM-DDTHH:MM (his local time); none for an undated task
  end      TEXT,
  status   TEXT NOT NULL DEFAULT 'planned' CHECK (status IN ('planned', 'done', 'cancelled', 'missed')),
  notes    TEXT NOT NULL DEFAULT '',
  thread   INTEGER,                             -- the thread it belongs to (th3), if any
  source   INTEGER REFERENCES messages(id),      -- the message it came from
  quote    TEXT,                                -- his words there, copied by code
  by       TEXT NOT NULL DEFAULT 'avy',
  why      TEXT,
  run      INTEGER,
  at       TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS timeline_by_chain ON timeline(chain);
CREATE TRIGGER IF NOT EXISTS timeline_is_kept_1 BEFORE UPDATE ON timeline
  BEGIN SELECT RAISE(ABORT, 'timeline versions are append-only'); END;
CREATE TRIGGER IF NOT EXISTS timeline_is_kept_2 BEFORE DELETE ON timeline
  BEGIN SELECT RAISE(ABORT, 'timeline versions are append-only'); END;

CREATE TABLE IF NOT EXISTS threads (
  id       INTEGER PRIMARY KEY,
  chain    INTEGER NOT NULL,                    -- th3
  version  INTEGER NOT NULL,
  replaces INTEGER UNIQUE REFERENCES threads(id),
  title    TEXT NOT NULL,
  status   TEXT NOT NULL CHECK (status IN ('active', 'waiting', 'paused', 'done', 'dropped')),
  goal     TEXT NOT NULL DEFAULT '',
  state    TEXT NOT NULL DEFAULT '',            -- where it stands now
  next     TEXT NOT NULL DEFAULT '',            -- the next step
  waiting  TEXT NOT NULL DEFAULT '',            -- what it's waiting on (a run finishing, his answer, a date)
  insights TEXT NOT NULL DEFAULT '[]',          -- JSON: short lines worth carrying (why it's set up this way, what a result would mean)
  steps    TEXT NOT NULL DEFAULT '[]',          -- JSON: the plan tree [{id: s1, text, parent, status: todo|doing|done|dropped, why}]
  source   INTEGER REFERENCES messages(id),
  by       TEXT NOT NULL DEFAULT 'avy',
  why      TEXT,
  run      INTEGER,
  at       TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS threads_by_chain ON threads(chain);
CREATE TRIGGER IF NOT EXISTS threads_are_kept_1 BEFORE UPDATE ON threads
  BEGIN SELECT RAISE(ABORT, 'thread versions are append-only'); END;
CREATE TRIGGER IF NOT EXISTS threads_are_kept_2 BEFORE DELETE ON threads
  BEGIN SELECT RAISE(ABORT, 'thread versions are append-only'); END;

-- WHAT SHE DID -----------------------------------------------------------------------------------------
-- Every action her hands took (hands.py: the terminal, files, Python, the web) and her instruments' changes, with what
-- came back. Permanent, like the log: the log says what she said, this says what she did.
CREATE TABLE IF NOT EXISTS actions (
  id       INTEGER PRIMARY KEY,
  asked    INTEGER REFERENCES messages(id),      -- the message she was answering
  tool     TEXT NOT NULL,
  args     TEXT NOT NULL,                        -- JSON
  result   TEXT NOT NULL,                        -- what came back (as she saw it)
  line     TEXT,                                 -- the one line the page shows
  seconds  REAL,
  at       TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS actions_by_asked ON actions(asked);
CREATE TRIGGER IF NOT EXISTS actions_are_kept_1 BEFORE UPDATE ON actions
  BEGIN SELECT RAISE(ABORT, 'actions are append-only'); END;
CREATE TRIGGER IF NOT EXISTS actions_are_kept_2 BEFORE DELETE ON actions
  BEGIN SELECT RAISE(ABORT, 'actions are append-only'); END;

-- SEARCH -------------------------------------------------------------------------------------------
-- items: m41 (a message), v77 (a node version), e4 (an episode headline), c7 (a connection's reason)
CREATE VIRTUAL TABLE IF NOT EXISTS words USING fts5(text, item UNINDEXED, tokenize = 'porter unicode61');
CREATE TABLE IF NOT EXISTS vectors (item TEXT PRIMARY KEY, model TEXT NOT NULL, vec BLOB NOT NULL);
