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

CREATE TABLE IF NOT EXISTS episodes (
  id        INTEGER PRIMARY KEY,                -- ep1, ep2, ...
  first     INTEGER NOT NULL,                   -- the stretch of the log: #first to #last
  last      INTEGER NOT NULL,
  headline  TEXT NOT NULL,
  at        TEXT NOT NULL,
  run       INTEGER                             -- the run that wrote it
);

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

-- SEARCH -------------------------------------------------------------------------------------------
-- items: m41 (a message), v77 (a node version), e4 (an episode headline), c7 (a connection's reason)
CREATE VIRTUAL TABLE IF NOT EXISTS words USING fts5(text, item UNINDEXED, tokenize = 'porter unicode61');
CREATE TABLE IF NOT EXISTS vectors (item TEXT PRIMARY KEY, model TEXT NOT NULL, vec BLOB NOT NULL);
