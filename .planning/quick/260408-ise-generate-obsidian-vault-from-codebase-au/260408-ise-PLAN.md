---
phase: 260408-ise
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - docs/obsidian-vault/00-Index/Dashboard.md
  - docs/obsidian-vault/00-Index/Done.md
  - docs/obsidian-vault/00-Index/Todo.md
  - docs/obsidian-vault/00-Index/Issues.md
  - docs/obsidian-vault/01-Architecture/System-Overview.md
  - docs/obsidian-vault/01-Architecture/Database-Rules.md
  - docs/obsidian-vault/01-Architecture/Data-Stack.md
  - docs/obsidian-vault/01-Architecture/Tape-Tiers.md
  - docs/obsidian-vault/01-Architecture/Risk-Framework.md
  - docs/obsidian-vault/01-Architecture/LLM-Policy.md
  - docs/obsidian-vault/02-Modules/Core-Library.md
  - docs/obsidian-vault/02-Modules/Crypto-Pairs.md
  - docs/obsidian-vault/02-Modules/SimTrader.md
  - docs/obsidian-vault/02-Modules/RAG.md
  - docs/obsidian-vault/02-Modules/RIS.md
  - docs/obsidian-vault/02-Modules/Market-Selection.md
  - docs/obsidian-vault/02-Modules/Historical-Import.md
  - docs/obsidian-vault/02-Modules/Hypothesis-Registry.md
  - docs/obsidian-vault/02-Modules/Notifications.md
  - docs/obsidian-vault/02-Modules/Gates.md
  - docs/obsidian-vault/02-Modules/FastAPI-Service.md
  - docs/obsidian-vault/03-Strategies/Track-1A-Crypto-Pair-Bot.md
  - docs/obsidian-vault/03-Strategies/Track-1B-Market-Maker.md
  - docs/obsidian-vault/03-Strategies/Track-1C-Sports-Directional.md
  - docs/obsidian-vault/04-CLI/CLI-Reference.md
  - docs/obsidian-vault/05-Roadmap/Phase-0-Accounts-Setup.md
  - docs/obsidian-vault/05-Roadmap/Phase-1A-Crypto-Pair-Bot.md
  - docs/obsidian-vault/05-Roadmap/Phase-1B-Market-Maker-Gates.md
  - docs/obsidian-vault/05-Roadmap/Phase-1C-Sports-Model.md
  - docs/obsidian-vault/05-Roadmap/Phase-2-Discovery-Engine.md
  - docs/obsidian-vault/05-Roadmap/Phase-3-Hybrid-RAG-Kalshi-n8n.md
  - docs/obsidian-vault/05-Roadmap/Phase-4-Autoresearch.md
  - docs/obsidian-vault/05-Roadmap/Phase-5-Advanced-Strategies.md
  - docs/obsidian-vault/05-Roadmap/Phase-6-Closed-Loop.md
  - docs/obsidian-vault/05-Roadmap/Phase-7-Unified-UI.md
  - docs/obsidian-vault/05-Roadmap/Phase-8-Scale-Platform.md
  - docs/obsidian-vault/06-Dev-Log/README.md
  - docs/obsidian-vault/07-Issues/Issue-Dual-Fee-Modules.md
  - docs/obsidian-vault/07-Issues/Issue-CH-Auth-Violations.md
  - docs/obsidian-vault/07-Issues/Issue-Multiple-HTTP-Clients.md
  - docs/obsidian-vault/07-Issues/Issue-Multiple-Config-Loaders.md
  - docs/obsidian-vault/07-Issues/Issue-Duplicate-WebSocket-Code.md
  - docs/obsidian-vault/07-Issues/Issue-Duplicate-Hypothesis-Registry.md
  - docs/obsidian-vault/07-Issues/Issue-Dead-Opportunities-Stub.md
  - docs/obsidian-vault/07-Issues/Issue-Pyproject-Packaging-Gap.md
  - docs/obsidian-vault/07-Issues/Issue-FastAPI-Island.md
autonomous: true
requirements: []

must_haves:
  truths:
    - "Opening docs/obsidian-vault/ in Obsidian shows a navigable graph with wiki-link connections"
    - "Dashboard.md contains working Dataview queries that enumerate Done, Todo, Blocked, and Issues"
    - "Every module note has YAML frontmatter with status tag and links to related architecture and strategy notes"
    - "All 23 ClickHouse tables appear in Database-Rules.md with their SQL file and purpose"
    - "All ~60 CLI commands appear in CLI-Reference.md organized by category"
    - "All 9 issue notes in 07-Issues/ map 1:1 to audit Section 7 findings"
    - "No placeholder text or invented facts exist — every claim traces to audit, roadmap, or CLAUDE.md"
  artifacts:
    - path: "docs/obsidian-vault/00-Index/Dashboard.md"
      provides: "Master MOC with Dataview queries"
      contains: "dataview"
    - path: "docs/obsidian-vault/01-Architecture/Database-Rules.md"
      provides: "All 23 ClickHouse tables"
      contains: "polymarket_trades"
    - path: "docs/obsidian-vault/04-CLI/CLI-Reference.md"
      provides: "Full CLI command reference"
      contains: "simtrader quickrun"
    - path: "docs/obsidian-vault/07-Issues/Issue-Dual-Fee-Modules.md"
      provides: "Fee duplication issue note"
      contains: "packages/polymarket/fees.py"
  key_links:
    - from: "docs/obsidian-vault/00-Index/Dashboard.md"
      to: "all vault notes"
      via: "Dataview queries over frontmatter tags"
      pattern: "dataview"
    - from: "docs/obsidian-vault/02-Modules/*.md"
      to: "docs/obsidian-vault/01-Architecture/*.md"
      via: "wiki-links in body text"
      pattern: "\\[\\["
---

<objective>
Generate a complete Obsidian-compatible markdown vault under `docs/obsidian-vault/` populated entirely from four source documents: `docs/CODEBASE_AUDIT.md` (primary ground truth), `docs/reference/POLYTOOL_MASTER_ROADMAP_v5_1.md`, `CLAUDE.md`, and `docs/CURRENT_STATE.md`.

Purpose: Provide an interconnected, navigable knowledge base of the PolyTool codebase that can be browsed in Obsidian with graph view, backlinks, and Dataview queries.

Output: ~45 markdown files across 7 directories, all with YAML frontmatter, wiki-links, and status tags.
</objective>

<execution_context>
@D:/Coding Projects/Polymarket/PolyTool/.claude/get-shit-done/workflows/execute-plan.md
@D:/Coding Projects/Polymarket/PolyTool/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@docs/CODEBASE_AUDIT.md — PRIMARY ground truth. All module inventories, CLI commands, database tables, integrations, config, test coverage, and known issues come from here.
@docs/reference/POLYTOOL_MASTER_ROADMAP_v5_1.md — Phase checklists, triple-track strategy detail, architecture vision, risk framework, LLM policy, tape tiers, capital progression.
@CLAUDE.md — Development principles, non-negotiable rules, artifact layout, repo conventions, ClickHouse auth rules, don't-do list.
@docs/CURRENT_STATE.md — Current state snapshot for status tags and progress context.
</context>

<tasks>

<task type="auto">
  <name>Task 1: Create architecture, index, and strategy vault files</name>
  <files>
    docs/obsidian-vault/00-Index/Dashboard.md
    docs/obsidian-vault/00-Index/Done.md
    docs/obsidian-vault/00-Index/Todo.md
    docs/obsidian-vault/00-Index/Issues.md
    docs/obsidian-vault/01-Architecture/System-Overview.md
    docs/obsidian-vault/01-Architecture/Database-Rules.md
    docs/obsidian-vault/01-Architecture/Data-Stack.md
    docs/obsidian-vault/01-Architecture/Tape-Tiers.md
    docs/obsidian-vault/01-Architecture/Risk-Framework.md
    docs/obsidian-vault/01-Architecture/LLM-Policy.md
    docs/obsidian-vault/03-Strategies/Track-1A-Crypto-Pair-Bot.md
    docs/obsidian-vault/03-Strategies/Track-1B-Market-Maker.md
    docs/obsidian-vault/03-Strategies/Track-1C-Sports-Directional.md
  </files>
  <action>
Read all four source documents in full before writing any files. Create directories `docs/obsidian-vault/{00-Index,01-Architecture,03-Strategies}`.

**Source mapping (which source feeds which file):**

**00-Index/Dashboard.md** — Master Map of Content (MOC). YAML frontmatter: `type: moc`, `tags: [index]`. Body contains:
- Section "Architecture" with wiki-links to every file in 01-Architecture/
- Section "Modules" with wiki-links to every file in 02-Modules/
- Section "Strategies" with wiki-links to every file in 03-Strategies/
- Section "CLI" with wiki-link to CLI-Reference
- Section "Roadmap" with wiki-links to every Phase note
- Section "Issues" with wiki-link to Issues index
- Dataview query block for all Done items: ` ```dataview LIST FROM "" WHERE contains(tags, "status/done") ``` `
- Dataview query block for all Todo items: ` ```dataview LIST FROM "" WHERE contains(tags, "status/todo") ``` `
- Dataview query block for all Blocked items: ` ```dataview LIST FROM "" WHERE contains(tags, "status/blocked") ``` `
- Dataview query block for all Issues: ` ```dataview TABLE severity, affected-modules FROM "07-Issues" ``` `

**00-Index/Done.md** — Frontmatter: `type: index`, `tags: [index, status/done]`. Dataview query listing all notes tagged `#status/done`. Plus a manually curated list of completed milestones from the roadmap (Phase 0 items that are checked, benchmark_v1 closure, SimTrader core, RIS v1, etc.).

**00-Index/Todo.md** — Frontmatter: `type: index`, `tags: [index, status/todo]`. Dataview query listing all notes tagged `#status/todo`. Plus manually curated list of pending work items from the roadmap (Gate 2 sweep, gold capture, crypto pair live deployment, etc.).

**00-Index/Issues.md** — Frontmatter: `type: index`, `tags: [index, issues]`. Dataview table listing all notes from `07-Issues/` folder with severity and affected-modules columns. Plus a brief summary paragraph.

**01-Architecture/System-Overview.md** — Source: CLAUDE.md "What PolyTool Is" section + roadmap North Star Architecture section + audit Section 1 module inventory. Frontmatter: `type: architecture`, `tags: [architecture, status/done]`. Body: purpose statement, layer roles (Python core, CLI, FastAPI, Scheduling, Visualization), package structure overview (packages/polymarket/ with 30+ modules, packages/research/ with 6 subpackages, polytool/ CLI entry, tools/cli/ with 56 files, tools/gates/ with 11 scripts, services/api/). Include wiki-links to [[Database-Rules]], [[Data-Stack]], [[Tape-Tiers]], [[Risk-Framework]], and all module notes.

**01-Architecture/Database-Rules.md** — Source: audit Section 3 (all 23 ClickHouse tables) + CLAUDE.md database one-sentence rule + audit Section 3.2 DuckDB. Frontmatter: `type: architecture`, `tags: [architecture, database, status/done]`. Body:
- One-sentence rule from CLAUDE.md: "ClickHouse handles all live streaming writes. DuckDB handles all historical Parquet reads. They do not replace each other."
- ClickHouse auth rule from CLAUDE.md (fail-fast, no hardcoded fallback).
- Full table of all 23 ClickHouse tables exactly as in audit Section 3.1 (table name, SQL file, purpose).
- ClickHouse connection pattern: host localhost:8123, user from CLICKHOUSE_USER, password from CLICKHOUSE_PASSWORD.
- DuckDB section: list of 5 files using DuckDB from audit Section 3.2.
- ChromaDB section: collection "polytool_rag", persist directory, embedding model.
- RIS KnowledgeStore section: kb/rag/knowledge/knowledge.sqlite3, separate from ChromaDB.
- Wiki-links to [[System-Overview]], [[Issue-CH-Auth-Violations]].

**01-Architecture/Data-Stack.md** — Source: roadmap "Multi-Layer Data Stack" section (5 free layers). Frontmatter: `type: architecture`, `tags: [architecture, data, status/done]`. Body: the 5 data layers from the roadmap (ClickHouse, DuckDB, Grafana, Python core, LLM bundles). Wiki-links to [[Database-Rules]], [[System-Overview]].

**01-Architecture/Tape-Tiers.md** — Source: roadmap "Tape Library Tiers" + CLAUDE.md tape tier definitions. Frontmatter: `type: architecture`, `tags: [architecture, tapes, status/done]`. Body: Gold (live tape recorder, tick-level/ms), Silver (reconstructed from pmxt + Jon-Becker + polymarket-apis), Bronze (Jon-Becker trade-level only). Artifacts directory layout from CLAUDE.md. Wiki-links to [[SimTrader]], [[Database-Rules]].

**01-Architecture/Risk-Framework.md** — Source: roadmap "Risk Framework" + CLAUDE.md "Risk, Fees, and Live-Trading Guardrails" + roadmap "Capital Progression". Frontmatter: `type: architecture`, `tags: [architecture, risk, status/done]`. Body: validation ladder (L1/L2/L3), gate definitions (Gate 1 replay, Gate 2 sweep 70%, Gate 3 shadow 25%), capital stages (Stage 0-4 from roadmap), fee realism rules, kill-switch model, rate limiter, inventory limits. Wiki-links to [[Gates]], [[Track-1B-Market-Maker]], [[System-Overview]].

**01-Architecture/LLM-Policy.md** — Source: roadmap "LLM Policy" section. Frontmatter: `type: architecture`, `tags: [architecture, llm, status/done]`. Body: Tier 1 (Ollama local, primary offline path), Tier 1b (DeepSeek-R1 when reasoning needed), Tier 2 (Claude/GPT for complex synthesis, human approval), Tier 3 (scheduled batch). Offline-first principle. Wiki-links to [[RAG]], [[RIS]], [[System-Overview]].

**03-Strategies/Track-1A-Crypto-Pair-Bot.md** — Source: CLAUDE.md Track 2/Phase 1A section + audit Section 1 crypto_pairs inventory + roadmap Phase 1A checklist. Frontmatter: `type: strategy`, `tags: [strategy, crypto, status/blocked]`, `track: 1A`. Body: purpose (fastest path to first dollar), strategy description (directional momentum, gabagool22 pattern), 20 modules from audit (list with line counts and purposes), blockers (no active BTC/ETH/SOL 5m/15m markets, paper soak not run, oracle mismatch concern, EU VPS needed). Key files: `paper_runner.py` (1339 lines), `event_models.py` (1441 lines). Wiki-links to [[SimTrader]], [[Risk-Framework]], [[Phase-1A-Crypto-Pair-Bot]].

**03-Strategies/Track-1B-Market-Maker.md** — Source: CLAUDE.md Track 1 section + roadmap Phase 1B + audit SimTrader strategies. Frontmatter: `type: strategy`, `tags: [strategy, market-maker, status/todo]`, `track: 1B`. Body: purpose (long-term revenue engine), Avellaneda-Stoikov logit quoting (MarketMakerV1), validation path (Gate 2 sweep -> Gate 3 shadow -> Stage 0), current status (Gate 2 NOT_RUN, 10/50 qualifying tapes, WAIT_FOR_CRYPTO policy), benchmark_v1 closed 2026-03-21. Key files: `market_maker_v0.py`, `market_maker_v1.py`. Wiki-links to [[Risk-Framework]], [[Gates]], [[Phase-1B-Market-Maker-Gates]], [[SimTrader]].

**03-Strategies/Track-1C-Sports-Directional.md** — Source: CLAUDE.md Track 3 section + roadmap Phase 1C. Frontmatter: `type: strategy`, `tags: [strategy, sports, status/todo]`, `track: 1C`. Body: purpose (medium-term model-driven), freely available sports data, needs paper prediction track record. No modules built yet. Wiki-links to [[Risk-Framework]], [[Phase-1C-Sports-Model]].

**Obsidian conventions (apply to ALL files):**
- Every file starts with YAML frontmatter block (---).
- Use `[[wiki-links]]` for all internal cross-references (NOT markdown links).
- Tags use #status/done, #status/todo, #status/blocked, #status/partial as appropriate.
- No placeholders, no "TBD", no invented facts. If information is not in the source documents, omit it.
- Dataview query blocks use triple-backtick fenced blocks with `dataview` language identifier.
  </action>
  <verify>
    <automated>bash -c "cd 'D:/Coding Projects/Polymarket/PolyTool' && find docs/obsidian-vault/00-Index -name '*.md' | wc -l && find docs/obsidian-vault/01-Architecture -name '*.md' | wc -l && find docs/obsidian-vault/03-Strategies -name '*.md' | wc -l && echo '--- frontmatter check ---' && grep -l '^---' docs/obsidian-vault/00-Index/*.md docs/obsidian-vault/01-Architecture/*.md docs/obsidian-vault/03-Strategies/*.md | wc -l && echo '--- wiki-link check ---' && grep -l '\\[\\[' docs/obsidian-vault/01-Architecture/System-Overview.md docs/obsidian-vault/01-Architecture/Database-Rules.md docs/obsidian-vault/03-Strategies/Track-1A-Crypto-Pair-Bot.md | wc -l && echo '--- dataview check ---' && grep -l 'dataview' docs/obsidian-vault/00-Index/Dashboard.md | wc -l"</automated>
  </verify>
  <done>
    - 4 files in 00-Index/ (Dashboard, Done, Todo, Issues), all with YAML frontmatter and Dataview queries
    - 6 files in 01-Architecture/ (System-Overview, Database-Rules, Data-Stack, Tape-Tiers, Risk-Framework, LLM-Policy), all with YAML frontmatter, wiki-links, and status tags
    - 3 files in 03-Strategies/ (Track-1A, Track-1B, Track-1C), all with YAML frontmatter, track field, status tags, and wiki-links
    - Dashboard.md contains 4+ Dataview query blocks
    - Database-Rules.md lists all 23 ClickHouse tables
    - All content sourced from the four source documents with zero placeholders
  </done>
</task>

<task type="auto">
  <name>Task 2: Create module notes, CLI reference, roadmap phases, dev-log, and issue notes</name>
  <files>
    docs/obsidian-vault/02-Modules/Core-Library.md
    docs/obsidian-vault/02-Modules/Crypto-Pairs.md
    docs/obsidian-vault/02-Modules/SimTrader.md
    docs/obsidian-vault/02-Modules/RAG.md
    docs/obsidian-vault/02-Modules/RIS.md
    docs/obsidian-vault/02-Modules/Market-Selection.md
    docs/obsidian-vault/02-Modules/Historical-Import.md
    docs/obsidian-vault/02-Modules/Hypothesis-Registry.md
    docs/obsidian-vault/02-Modules/Notifications.md
    docs/obsidian-vault/02-Modules/Gates.md
    docs/obsidian-vault/02-Modules/FastAPI-Service.md
    docs/obsidian-vault/04-CLI/CLI-Reference.md
    docs/obsidian-vault/05-Roadmap/Phase-0-Accounts-Setup.md
    docs/obsidian-vault/05-Roadmap/Phase-1A-Crypto-Pair-Bot.md
    docs/obsidian-vault/05-Roadmap/Phase-1B-Market-Maker-Gates.md
    docs/obsidian-vault/05-Roadmap/Phase-1C-Sports-Model.md
    docs/obsidian-vault/05-Roadmap/Phase-2-Discovery-Engine.md
    docs/obsidian-vault/05-Roadmap/Phase-3-Hybrid-RAG-Kalshi-n8n.md
    docs/obsidian-vault/05-Roadmap/Phase-4-Autoresearch.md
    docs/obsidian-vault/05-Roadmap/Phase-5-Advanced-Strategies.md
    docs/obsidian-vault/05-Roadmap/Phase-6-Closed-Loop.md
    docs/obsidian-vault/05-Roadmap/Phase-7-Unified-UI.md
    docs/obsidian-vault/05-Roadmap/Phase-8-Scale-Platform.md
    docs/obsidian-vault/06-Dev-Log/README.md
    docs/obsidian-vault/07-Issues/Issue-Dual-Fee-Modules.md
    docs/obsidian-vault/07-Issues/Issue-CH-Auth-Violations.md
    docs/obsidian-vault/07-Issues/Issue-Multiple-HTTP-Clients.md
    docs/obsidian-vault/07-Issues/Issue-Multiple-Config-Loaders.md
    docs/obsidian-vault/07-Issues/Issue-Duplicate-WebSocket-Code.md
    docs/obsidian-vault/07-Issues/Issue-Duplicate-Hypothesis-Registry.md
    docs/obsidian-vault/07-Issues/Issue-Dead-Opportunities-Stub.md
    docs/obsidian-vault/07-Issues/Issue-Pyproject-Packaging-Gap.md
    docs/obsidian-vault/07-Issues/Issue-FastAPI-Island.md
  </files>
  <action>
Read all four source documents in full before writing any files. Create directories `docs/obsidian-vault/{02-Modules,04-CLI,05-Roadmap,06-Dev-Log,07-Issues}`.

**02-Modules/ — One note per major subsystem. Source: audit Section 1 module inventories.**

Each module note has frontmatter: `type: module`, `status: done|partial|blocked`, `tags: [module, status/{status}, {domain-tag}]`, `lines: {total}`, `test-coverage: {high|partial|none}`.

**02-Modules/Core-Library.md** — Source: audit Section 1.1 "Top-Level Modules" table (30+ modules). Body: table of all top-level packages/polymarket/ modules (module name, lines, purpose, status, key exports) reproduced from audit. Highlight the largest: clv.py (1698), llm_research_packets.py (1795), gamma.py (1089). Note the two storage backends in rag/ (ChromaDB vs SQLite). Wiki-links to [[System-Overview]], [[Database-Rules]], [[RAG]].

**02-Modules/Crypto-Pairs.md** — Source: audit Section 1.1 crypto_pairs table (20 files, ~10,599 lines). Body: full module table from audit. Note BLOCKED status (no active markets). Highlight largest: paper_ledger.py (1478), paper_runner.py (1339), event_models.py (1441). Strategy: gabagool22 directional momentum. Wiki-links to [[Track-1A-Crypto-Pair-Bot]], [[System-Overview]].

**02-Modules/SimTrader.md** — Source: audit Section 1.1 simtrader multi-subpackage. Body: list every subpackage (batch, broker, execution, orderbook, portfolio, replay, shadow, strategies, strategy, studio, sweeps, tape) with their modules from audit. Highlight execution/ safety modules: kill_switch.py, risk_manager.py, rate_limiter.py. Note strategies: MarketMakerV0, MarketMakerV1 (logit A-S), BinaryComplementArb, CopyWalletReplay. Studio: browser-based replay UI (app.py 1422 lines, ondemand.py 884 lines). Wiki-links to [[Track-1B-Market-Maker]], [[Risk-Framework]], [[Tape-Tiers]].

**02-Modules/RAG.md** — Source: audit Section 1.1 rag/ table (13 files, ~3,124 lines). Body: two storage backends (ChromaDB vector, SQLite FTS5 lexical). Module table from audit. ChromaDB collection: "polytool_rag". KnowledgeStore: kb/rag/knowledge/knowledge.sqlite3. Wiki-links to [[Database-Rules]], [[LLM-Policy]], [[RIS]].

**02-Modules/RIS.md** — Source: audit Section 1.2 (all 6 RIS subpackages). Body: list every subpackage (evaluation, hypotheses, ingestion, integration, monitoring, scheduling, synthesis) with their modules from audit. Highlight: ingestion/fetchers.py (859 lines) supports web/ArXiv/Reddit/YouTube; synthesis/report.py (686 lines); precheck STOP/CAUTION/GO verdicts. Note packaging gap. Wiki-links to [[RAG]], [[LLM-Policy]], [[Issue-Pyproject-Packaging-Gap]].

**02-Modules/Market-Selection.md** — Source: audit Section 1.1 market_selection. Body: 7-factor composite scorer (category_edge, spread_opportunity, volume, competition, reward_apr, adverse_selection, time_gaussian). NegRisk penalty, longshot bonus. CLI: `market-scan --top 20`. Wiki-links to [[System-Overview]], [[CLI-Reference]].

**02-Modules/Historical-Import.md** — Source: audit Section 1.1 historical_import. Body: 4 modules (clickhouse_writer, downloader, parser, pipeline). Purpose: bulk historical trade data import. Wiki-links to [[Database-Rules]], [[System-Overview]].

**02-Modules/Hypothesis-Registry.md** — Source: audit Section 1.1 hypotheses + Section 1.2 research/hypotheses. Body: two registries exist (JSON-backed in packages/polymarket/, SQLite-backed in packages/research/ at 409 lines). CLI uses the research version. The polymarket version may be legacy. Wiki-links to [[RIS]], [[Issue-Duplicate-Hypothesis-Registry]], [[CLI-Reference]].

**02-Modules/Notifications.md** — Source: audit Section 1.1 notifications. Body: discord.py (7 functions, all return bool, never raise). Functions: post_message, notify_gate_result, notify_session_start/stop/error, notify_kill_switch, notify_risk_halt. Env var: DISCORD_WEBHOOK_URL. 29 tests. Wiki-links to [[Risk-Framework]], [[Gates]].

**02-Modules/Gates.md** — Source: audit Section 1.5 tools/gates/ (11 files, 4674 total lines). Body: table of all 11 gate scripts from audit. Gate definitions: Gate 1 (replay), Gate 2 (sweep, 70% threshold), Gate 3 (shadow, 25% prediction deviation). Current status: Gate 2 NOT_RUN. Wiki-links to [[Risk-Framework]], [[Track-1B-Market-Maker]], [[SimTrader]].

**02-Modules/FastAPI-Service.md** — Source: audit Section 1.8 + audit note 3. Frontmatter tags include `status/partial`. Body: services/api/main.py (3054 lines), zero tests, no CLI routing. Per CLAUDE.md, FastAPI is Phase 3 deliverable — pre-built infrastructure without coverage. Wiki-links to [[System-Overview]], [[Issue-FastAPI-Island]], [[Phase-3-Hybrid-RAG-Kalshi-n8n]].

**04-CLI/CLI-Reference.md** — Source: audit Section 2 (all ~60 commands). Frontmatter: `type: reference`, `tags: [cli, reference, status/done]`. Body: reproduce every command table from audit Section 2 organized by category:
- Core Research / Dossier Workflow (scan, wallet-scan, alpha-distill, llm-bundle, opus-bundle, candidate-scan, export-dossier, export-clickhouse)
- RAG Commands (rag-index, rag-query, rag-refresh)
- RIS Commands (research-precheck, research-ingest, research-acquire, research-report, research-health, research-stats, research-scheduler, research-bridge)
- Hypothesis / Experiment Registry (hypothesis register/status/experiment-init/experiment-run/validate/diff/summary)
- Tape / Benchmark Workflow (fetch-price-2min, batch-reconstruct-silver, reconstruct-silver, benchmark-manifest, close-benchmark-v1, new-market-capture, capture-new-market-tapes)
- SimTrader Commands (quickrun, run, shadow, sweep, batch, studio, tape-record, probe)
- Market Selection (market-scan, crypto-pair-watch)
- Optional / Special Load (mcp, examine, cache-source)
- Not Yet Implemented (autoresearch import-results, strategy-codify, FastAPI endpoints)
Each row: Command, Handler Module, Description, Status. Wiki-links to relevant module notes where applicable.

**05-Roadmap/ — One note per phase. Source: roadmap Phase checklists.**

Each phase note has frontmatter: `type: roadmap`, `phase: N`, `tags: [roadmap, status/{status}]`.

**Phase-0-Accounts-Setup.md** — Status: `#status/done`. Checklist items from roadmap Phase 0 (accounts, setup, operator workflow). Wiki-links to [[System-Overview]].

**Phase-1A-Crypto-Pair-Bot.md** — Status: `#status/blocked`. Checklist from roadmap Phase 1A. Note blockers. Wiki-links to [[Track-1A-Crypto-Pair-Bot]], [[Crypto-Pairs]].

**Phase-1B-Market-Maker-Gates.md** — Status: `#status/todo`. Checklist from roadmap Phase 1B (Gate 2 sweep, Gate 3 shadow, staged live). Wiki-links to [[Track-1B-Market-Maker]], [[Gates]], [[Risk-Framework]].

**Phase-1C-Sports-Model.md** — Status: `#status/todo`. Checklist from roadmap Phase 1C. Wiki-links to [[Track-1C-Sports-Directional]].

**Phase-2-Discovery-Engine.md** — Status: `#status/partial`. Checklist from roadmap Phase 2 (discovery engine, research scraper). Wiki-links to [[RIS]], [[RAG]].

**Phase-3-Hybrid-RAG-Kalshi-n8n.md** — Status: `#status/todo`. Checklist from roadmap Phase 3. Wiki-links to [[RAG]], [[FastAPI-Service]].

**Phase-4-Autoresearch.md** — Status: `#status/todo`. Checklist from roadmap Phase 4. Wiki-links to [[RIS]].

**Phase-5-Advanced-Strategies.md** — Status: `#status/todo`. Checklist from roadmap Phase 5. Wiki-links to [[SimTrader]].

**Phase-6-Closed-Loop.md** — Status: `#status/todo`. Checklist from roadmap Phase 6. Wiki-links to [[RIS]], [[SimTrader]].

**Phase-7-Unified-UI.md** — Status: `#status/todo`. Checklist from roadmap Phase 7. Wiki-links to [[SimTrader]].

**Phase-8-Scale-Platform.md** — Status: `#status/todo`. Checklist from roadmap Phase 8.

**06-Dev-Log/README.md** — Frontmatter: `type: guide`, `tags: [dev-log]`. Body: explain the dev log convention from CLAUDE.md: "docs/dev_logs/YYYY-MM-DD_<slug>.md is mandatory for every meaningful work unit." Note that actual dev logs live in `docs/dev_logs/` in the main repo, not duplicated here. This folder is for any vault-specific development notes.

**07-Issues/ — One note per audit Section 7 finding. Source: audit Section 7.**

Each issue note has frontmatter: `type: issue`, `severity: high|medium|low`, `affected-modules: [list]`, `tags: [issue, status/todo]`.

**Issue-Dual-Fee-Modules.md** — Source: audit 7.1. Severity: medium. Affected: `packages/polymarket/fees.py`, `packages/polymarket/simtrader/portfolio/fees.py`. Body: float vs Decimal duplication of quadratic fee curve. Risk of drift. Wiki-links to [[Core-Library]], [[SimTrader]].

**Issue-CH-Auth-Violations.md** — Source: audit 7.2. Severity: high. Affected: `examine.py`, `export_dossier.py`, `export_clickhouse.py`, `reconstruct_silver.py`. Body: silent fallback to "polytool_admin" violates CLAUDE.md. Correct pattern: fail-fast. Files with correct pattern: fetch_price_2min.py, close_benchmark_v1.py, batch_reconstruct_silver.py. Wiki-links to [[Database-Rules]], [[CLI-Reference]].

**Issue-Multiple-HTTP-Clients.md** — Source: audit 7.3. Severity: low. Affected: `http_client.py`, various tools, `research/ingestion/fetchers.py`. Body: three approaches (shared wrapper, requests direct, httpx async). Wiki-links to [[Core-Library]], [[RIS]].

**Issue-Multiple-Config-Loaders.md** — Source: audit 7.4. Severity: low. Affected: `simtrader/config_loader.py`, various gate scripts, `polytool/__main__.py`. Body: three patterns (BOM-safe config_loader, raw json.load, python-dotenv). Wiki-links to [[SimTrader]], [[Gates]].

**Issue-Duplicate-WebSocket-Code.md** — Source: audit 7.5. Severity: medium. Affected: `clob_stream.py`, `shadow/runner.py`, `tape/recorder.py`, `activeness_probe.py`. Body: each implements own reconnect loop, stall detection, event normalization. No shared WS base class. Wiki-links to [[SimTrader]], [[Crypto-Pairs]].

**Issue-Duplicate-Hypothesis-Registry.md** — Source: audit 7.6. Severity: medium. Affected: `packages/polymarket/hypotheses/registry.py`, `packages/research/hypotheses/registry.py`. Body: JSON-backed vs SQLite-backed. CLI uses research version. Polymarket version may be legacy. Wiki-links to [[Hypothesis-Registry]], [[RIS]].

**Issue-Dead-Opportunities-Stub.md** — Source: audit 7.7. Severity: low. Affected: `packages/polymarket/opportunities.py`. Body: 22-line stub, unused dataclass. Overlaps with arb.py and crypto_pairs/opportunity_scan.py. Wiki-links to [[Core-Library]].

**Issue-Pyproject-Packaging-Gap.md** — Source: audit note 2. Severity: medium. Affected: `packages/research/evaluation`, `ingestion`, `integration`, `monitoring`, `synthesis`. Body: 5 subpackages not in pyproject.toml packages list. Work via sys.path but fail on clean install. Wiki-links to [[RIS]].

**Issue-FastAPI-Island.md** — Source: audit note 3. Severity: low. Affected: `services/api/main.py`. Body: 3054 lines, zero tests, no CLI routing. Phase 3 deliverable pre-built without coverage. Wiki-links to [[FastAPI-Service]], [[Phase-3-Hybrid-RAG-Kalshi-n8n]].

**Obsidian conventions (same as Task 1 — apply to ALL files):**
- Every file starts with YAML frontmatter block (---).
- Use `[[wiki-links]]` for all internal cross-references.
- Tags use #status/done, #status/todo, #status/blocked, #status/partial.
- No placeholders, no invented facts.
  </action>
  <verify>
    <automated>bash -c "cd 'D:/Coding Projects/Polymarket/PolyTool' && echo '=== File counts ===' && for d in 02-Modules 04-CLI 05-Roadmap 06-Dev-Log 07-Issues; do echo \"$d: $(find docs/obsidian-vault/$d -name '*.md' 2>/dev/null | wc -l)\"; done && echo '=== Total vault files ===' && find docs/obsidian-vault -name '*.md' | wc -l && echo '=== Frontmatter check ===' && find docs/obsidian-vault -name '*.md' -exec grep -l '^---' {} + | wc -l && echo '=== Wiki-link sampling ===' && grep -c '\\[\\[' docs/obsidian-vault/02-Modules/SimTrader.md && grep -c '\\[\\[' docs/obsidian-vault/04-CLI/CLI-Reference.md && echo '=== CLI commands in reference ===' && grep -c '|' docs/obsidian-vault/04-CLI/CLI-Reference.md && echo '=== Issue notes ===' && find docs/obsidian-vault/07-Issues -name '*.md' | wc -l && echo '=== Phase notes ===' && find docs/obsidian-vault/05-Roadmap -name '*.md' | wc -l"</automated>
  </verify>
  <done>
    - 11 module notes in 02-Modules/ with full module inventories from audit
    - 1 CLI-Reference.md in 04-CLI/ with all ~60 commands organized by category
    - 11 phase notes in 05-Roadmap/ (Phase 0 through Phase 8) with checklist items
    - 1 README.md in 06-Dev-Log/ explaining convention
    - 9 issue notes in 07-Issues/ mapping 1:1 to audit Section 7 findings
    - Total vault: ~45 markdown files
    - All files have YAML frontmatter with type, status tags, and wiki-links
    - Zero placeholders — all content sourced from audit, roadmap, CLAUDE.md, or CURRENT_STATE.md
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

No trust boundaries apply. This is a documentation-only task generating static markdown files from existing repo documents. No code execution, no external connections, no user input processing.

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-ise-01 | I (Information Disclosure) | Vault files | accept | Vault contains only public repo information already in docs/. No secrets, credentials, or private keys are sourced. |
</threat_model>

<verification>
1. `find docs/obsidian-vault -name '*.md' | wc -l` returns ~45
2. Every .md file contains YAML frontmatter (starts with `---`)
3. `grep -r '\[\[' docs/obsidian-vault/ | wc -l` shows substantial wiki-link usage (50+ links minimum)
4. `grep -r 'dataview' docs/obsidian-vault/00-Index/` shows Dataview queries in index files
5. `grep 'polymarket_trades' docs/obsidian-vault/01-Architecture/Database-Rules.md` confirms ClickHouse tables present
6. All 9 issue files exist in 07-Issues/
7. All 11 phase files exist in 05-Roadmap/
8. No file contains "TBD", "placeholder", or "TODO" (except in content describing actual project TODOs)
</verification>

<success_criteria>
- Complete Obsidian vault with ~45 markdown files across 7 directories
- Every file has YAML frontmatter with type and tags fields
- Wiki-links connect notes across directories (modules link to architecture, strategies link to modules, issues link to affected modules)
- Dashboard.md has working Dataview queries for Done/Todo/Blocked/Issues
- Database-Rules.md lists all 23 ClickHouse tables from audit
- CLI-Reference.md lists all ~60 commands from audit Section 2
- 9 issue notes correspond exactly to audit Section 7 findings
- Zero invented content — every fact traceable to one of the four source documents
</success_criteria>

<output>
After completion, create `.planning/quick/260408-ise-generate-obsidian-vault-from-codebase-au/260408-ise-SUMMARY.md`
</output>
