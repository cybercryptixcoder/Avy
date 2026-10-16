# The landscape (what exists, what's open)

Researched Oct 15–16, 2026, at Shreyas's request, because he wants to build the best agent memory there is
and needs to know what "best" is measured against. Everything here is what the sources say, with links;
where it's my reading rather than theirs, it says so. Vendor numbers are vendor numbers. Re-check anything
before relying on it: this field moves monthly.

## Supermemory

**The company.** Founded by Dhravya Shah (19 when he raised, from Mumbai, ex-Cloudflare). A $2.6–3M seed in
Oct 2025 (Susa Ventures, Browder Capital, SF1.vc; angels include Jeff Dean, Logan Kilpatrick, Dane Knecht,
David Cramer). ~31k GitHub stars. On Sep 10, 2026 it shut down its company-brain Slack bot and the Nova app to
go "all in on the memory engine"; the company brain was open-sourced on Sep 25.
[TechCrunch](https://techcrunch.com/2025/10/06/a-19-year-old-nabs-backing-from-google-execs-for-his-ai-memory-startup-supermemory/),
[the update](https://supermemory.ai/blog/an-update-to-supermemory/), [GitHub](https://github.com/supermemoryai/supermemory).

**How it works** ([how it works](https://supermemory.ai/docs/concepts/how-it-works),
[graph memory](https://supermemory.ai/docs/concepts/graph-memory),
[profiles](https://supermemory.ai/docs/concepts/user-profiles)):
- Documents (anything) → chunks (kept as evidence) → memories (facts) in a "temporal vector-graph engine"
  (vector, full-text and graph indexes).
- Relations between memories: **updates** (a new fact wins; history kept; `isLatest`), **extends** (adds
  detail), **derives** (an inference from patterns, which must trace to source memories).
- Memory types: facts persist until updated, preferences "strengthen with repetition", episodes decay unless
  significant. Temporary facts expire ("exam tomorrow").
- Two dates per memory: `documentDate` (when written) and `eventDate` (when it happens).
- **Profiles**: static (stable facts) and dynamic (recent context), sorted into topic buckets, attached to
  every prompt without a search.
- **Dreaming** (["Dynamic Dreaming"](https://supermemory.ai/blog/introducing-dynamic-dreaming-supermemory-now-connects-the-dots-for-you/),
  May 25, 2026): runs when the user goes quiet; merges fragments, resolves contradictions, writes derivations,
  updates the profile; no published measurements.
- Search: hybrid (meaning + words), with the matched memory's source chunk injected alongside it.
- **ASMR** (Mar 2026), an experimental agentic search: reader agents extract findings, search agents look
  through them; ~98.6% on LongMemEval-S counting a question right if any of eight prompt variants gets it,
  97.2% with 12 agents and a majority vote; "not our main production engine (yet)"
  ([Aihola](https://aihola.com/article/supermemory-99-longmemeval-agentic-memory)).
- **SMFS** (May 2026), memory as a filesystem for coding agents: semantic search lands on a path, then the
  agent greps around it; on their xAFS benchmark, 81% vs 69% accuracy at 10,000 files and 55% cheaper
  ([post](https://supermemory.ai/blog/smfs-making-agentic-retrieval-55-cheaper-and-more-accurate/)).
- **Learner-1** (Sep 7, 2026), sold as continual learning: "helps any model continuously improve by
  extracting and dreaming on the context of any user, task, or tenant", injected into context. No mechanism
  or numbers published at launch ([Runtimewire](https://runtimewire.com/article/supermemory-launches-learner-1-continual-learning-ai-agents),
  [homepage](https://supermemory.ai/index.md)).

**Their numbers.** On LongMemEval-S the production engine's answer accuracy is 81.6% (gpt-4o), 84.6%
(gpt-5), 85.2% (gemini-3-pro); the 97% headline on their [research page](https://supermemory.ai/research/longmembench)
is a retrieval recall figure. They also claim #1 on LoCoMo and ConvoMem without published figures there.

**Coding agents and long-running work.** Their Claude Code plugin saves structured compaction summaries
(the literal request, the goal, files touched, remaining work, "negative constraints") and extracted facts,
and injects profile, project memories and search results at session start
([post](https://supermemory.ai/blog/infinitely-running-stateful-coding-agents/),
[plugin dissected](https://blog.devgenius.io/dissecting-the-claude-supermemory-plugin-d2bea6a94c25),
[docs](https://supermemory.ai/docs/integrations/claude-code)). Nothing describes per-task state, concurrent
tasks or background jobs, and no measurement is published. My reading: it carries facts and summaries
across sessions; it doesn't hold the reasoning behind a piece of work as that work's own state.

## Others, on the same benchmarks

LongMemEval-S answer accuracy (500 questions): Agent Zero 95.6% ([arXiv 2608.29606](https://arxiv.org/pdf/2608.29606),
provenance on every item, citation-locked answers), OMEGA 95.4%, Mastra Observational Memory 94.87% with
gpt-5-mini ([Mastra](https://mastra.ai/research/observational-memory): two background agents keep a
compressed, dated observation log; no retrieval), Hindsight 91.4%, Supermemory 85.2%, Zep 71.2%. Mastra
measured about 9 points between gpt-4o and gemini-3-pro as the answering model: the reader matters.
LoCoMo: Agent Zero 93.6%, Mem0 92.5%. Both benchmarks are described as near saturated.

## Benchmarks where the field is open

- **CL-Bench** ([arXiv 2606.05661](https://arxiv.org/abs/2606.05661), Berkeley/Snorkel, June 2026):
  continual learning as getting better at real tasks with experience. Best gain ~25% (full context with
  Claude Sonnet 4.6); Mem0 and ACE didn't beat that; agents overfit to recent experience, fail to reuse older
  knowledge, keep stale beliefs after drift; accumulated state sometimes hurts. Supermemory not tested.
- **MemoryArena** ([arXiv 2602.16313](https://arxiv.org/abs/2602.16313), Stanford): interdependent
  multi-session agent tasks. Memory systems (Letta, Mem0, ReasoningBank...) don't consistently beat long
  context; success falls with dependency depth; near zero on group travel planning.
- **AMA-Bench** ([arXiv 2602.22769](https://arxiv.org/html/2602.22769v4)): memory over agent trajectories
  (actions, tool outputs). Many memory systems underperform plain long context: lossy compression drops dense
  state and causal detail; similarity search misses causally linked evidence. Their causality graph mattered
  (0.57 → 0.43 without it).
- **Mem2ActBench** ([arXiv 2601.19935](https://arxiv.org/html/2601.19935)): using memory to fill in tool
  arguments. Retrieval is the bottleneck (oracle 53.8 F1 vs ~30.7); models invent plausible defaults.
- **GoodAI LTM benchmark** ([arXiv 2409.20222](https://arxiv.org/abs/2409.20222v2)): tasks interleaved in
  one long conversation; models handle single tasks well and worse when the same tasks are interleaved.
- **BEAM** ([arXiv 2510.27246](https://arxiv.org/abs/2510.27246), ICLR 2026): conversations up to 10M tokens;
  best reported 68% at 10M (Exabase, a vendor claim).
- **ConvoMem** ([arXiv 2511.10523](https://arxiv.org/html/2511.10523v1), Salesforce): on implicit
  connections (relevance nobody asked for), Mem0 25–45% vs 63–82% for full context.
- **Context rot** ([Chroma](https://trychroma.com/research/context-rot)): all 18 models tested degrade as
  input grows; on LongMemEval every model did much better with ~300 focused tokens than the full ~113k.
- **Identity drift** ([arXiv 2412.00804](https://tldr.takara.ai/p/2412.00804)): larger models drift more;
  assigning a persona may not help.

## Learning from experience: what has worked

- **ACE** ([arXiv 2510.04618](https://arxiv.org/html/2510.04618v2)): an evolving playbook (generator,
  reflector, curator; small itemized updates, never full rewrites). With DeepSeek-V3.1 in every role it
  matched IBM's GPT-4.1-based production agent on AppWorld (59.4 vs 60.3). Rewriting the whole context each
  step collapsed it (18,282 tokens to 122) and fell below no adaptation.
- **ReasoningBank** ([Google](https://research.google/blog/reasoningbank-enabling-agents-to-learn-from-experience/)):
  lessons distilled from successes and failures; +8.3% on WebArena; memories matured on their own from
  checklists into preventative checks.

## Obsidian and the "LLM Wiki"

Obsidian is a local markdown notes app; MCP servers let agents read and write a vault. Karpathy's "LLM
Wiki" pattern (spring 2026) has an agent maintain interlinked markdown pages over raw sources
([AAIF](https://aaif.io/blog/karpathys-llm-wiki-as-agent-memory)). A convention for human-readable memory,
not a system that's measured.
