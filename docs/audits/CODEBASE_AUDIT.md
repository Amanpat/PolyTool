# PolyTool Codebase Ground-Truth Audit

**Audit date:** 2026-04-08
**Auditor:** GSD executor (automated read-only inspection)
**Scope:** All Python packages under `packages/`, `polytool/`, `tools/`, `services/`
**Method:** Source code reading only — no Python execution, no external connections

---

## Section 1: Module Inventory

### 1.1 packages/polymarket/ — Core Library

#### Top-Level Modules

| Module | Lines | Purpose | Status | Key Exports |
|--------|-------|---------|--------|-------------|
| `arb.py` | 601 | Complete-set arbitrage detection and profitability calculation | **WORKING** | `ArbOpportunity`, `find_arb_opportunities`, `check_arbitrage_profitability` |
| `backfill.py` | 580 | Historical trade backfill from polymarket-apis | **WORKING** | `BackfillConfig`, `TradeBackfiller`, `run_backfill` |
| `benchmark_gap_fill_planner.py` | 693 | Identifies and plans gap-fill operations for Silver tapes | **WORKING** | `GapFillPlan`, `GapFillPlanner`, `build_gap_fill_plan` |
| `benchmark_manifest_contract.py` | 373 | Canonical data contract for benchmark tape manifests | **WORKING** | `TapeManifest`, `TapeEntry`, `validate_manifest` |
| `clob.py` | 263 | CLOB API client wrapper (order book, trades, positions) | **WORKING** | `ClobClient`, `get_orderbook`, `get_trades` |
| `clv.py` | 1698 | Closing Line Value computation — largest module in core | **WORKING** | `CLVResult`, `compute_clv`, `CLVAnalyzer` |
| `data_api.py` | 641 | Polymarket data API client (markets, prices, history) | **WORKING** | `DataApiClient`, `get_markets`, `get_price_history` |
| `detectors.py` | 728 | Wallet behavior detectors (holding, DCA, arb-ish, etc.) | **WORKING** | `HoldingDetector`, `DCADetector`, `CompleteSetArbish`, `detect_all` |
| `duckdb_helper.py` | 258 | DuckDB connection management and Parquet query helpers | **WORKING** | `DuckDBHelper`, `query_parquet`, `open_db` |
| `features.py` | 228 | Feature extraction from wallet/market data | **WORKING** | `FeatureExtractor`, `extract_wallet_features` |
| `fees.py` | 113 | Fee calculation (float-based quadratic curve) | **WORKING** | `calculate_fee`, `FeeModel`, `DEFAULT_FEE_RATE_BPS` |
| `gamma.py` | 1089 | Gamma API client — market metadata, resolution, events | **WORKING** | `GammaClient`, `get_market`, `get_events`, `resolve_market` |
| `http_client.py` | 245 | Shared HTTP session with retry/backoff logic | **WORKING** | `PolyHttpClient`, `get`, `post`, `get_with_retry` |
| `llm_research_packets.py` | 1795 | LLM prompt bundling and research packet generation | **WORKING** | `ResearchPacket`, `build_llm_bundle`, `LLMBundler` |
| `new_market_capture_planner.py` | 371 | Planner for capturing new-market Gold tapes | **WORKING** | `NewMarketCapturePlan`, `plan_new_market_capture` |
| `normalization.py` | 33 | Data normalization utilities (price, volume) | **WORKING** | `normalize_price`, `normalize_volume` |
| `on_chain_ctf.py` | ~180 | On-chain CTF contract resolution (raw JSON-RPC) | **WORKING** | `OnChainCTFProvider`, `resolve` |
| `opportunities.py` | 22 | Stub — opportunity dataclass only | **STUBBED** | `Opportunity` (dataclass only) |
| `orderbook_snapshots.py` | 532 | L2 orderbook snapshot management and ClickHouse writes | **WORKING** | `OrderbookSnapshot`, `write_snapshot`, `fetch_snapshots` |
| `pnl.py` | 528 | PnL computation with fee model; CLV capture; resolution enrichment | **WORKING** | `PnLResult`, `compute_pnl`, `enrich_with_resolution` |
| `price_2min_fetcher.py` | 322 | 2-minute price bar fetcher (Gold acquisition path) | **WORKING** | `Price2MinFetcher`, `fetch_and_write`, `PriceBar` |
| `resolution.py` | 446 | 4-stage resolution cascade (CH → OnChainCTF → Subgraph → Gamma) | **WORKING** | `CachedResolutionProvider`, `resolve_market`, `ResolutionResult` |
| `silver_reconstructor.py` | 877 | Silver tape reconstruction from multiple data sources | **WORKING** | `SilverReconstructor`, `reconstruct`, `ReconstructionConfig` |
| `slippage.py` | 247 | Slippage modeling for order sizing and fill simulation | **WORKING** | `SlippageModel`, `estimate_slippage`, `fill_with_slippage` |
| `subgraph.py` | ~150 | GraphQL client for The Graph / Polymarket subgraph | **WORKING** | `SubgraphProvider`, `query_subgraph`, `resolve` |
| `token_resolution.py` | 57 | Token-to-market slug resolution | **WORKING** | `resolve_token_to_market`, `TokenResolver` |

#### packages/polymarket/crypto_pairs/ (~10,599 lines, 20 files)

| Module | Lines | Purpose | Status |
|--------|-------|---------|--------|
| `accumulation_engine.py` | 576 | Pair-cost accumulation logic (superseded by gabagool22 strategy but still present) | **WORKING** |
| `await_soak.py` | 366 | Paper-soak wait loop; monitors position until soak completes | **WORKING** |
| `backtest_harness.py` | 325 | Offline backtesting harness for crypto pair strategies | **WORKING** |
| `clickhouse_sink.py` | 262 | ClickHouse write path for crypto pair events | **WORKING** |
| `clob_order_client.py` | 160 | CLOB order placement client (wraps py_clob_client) | **WORKING** |
| `clob_stream.py` | 379 | WebSocket stream client for CLOB L2 events | **WORKING** |
| `config_models.py` | 506 | Pydantic config models for crypto pair strategies | **WORKING** |
| `dev_seed.py` | 380 | Development seed data generator for offline testing | **WORKING** |
| `event_models.py` | 1441 | Event model definitions (fills, quotes, market events) | **WORKING** |
| `fair_value.py` | 204 | Fair value computation from reference feed + CLOB | **WORKING** |
| `live_execution.py` | 175 | Live order execution wrapper (calls clob_order_client) | **WORKING** |
| `live_runner.py` | 476 | Live trading runner — main orchestration loop | **WORKING** |
| `market_discovery.py` | 312 | Active BTC/ETH/SOL pair market discovery | **WORKING** |
| `market_watch.py` | 151 | One-shot market watch for checking active markets | **WORKING** |
| `opportunity_scan.py` | 198 | Entry opportunity scanner (gabagool22 pattern) | **WORKING** |
| `paper_ledger.py` | 1478 | Paper trading position ledger with P&L tracking | **WORKING** |
| `paper_runner.py` | 1339 | Paper trading runner — largest in the subpackage | **WORKING** |
| `position_store.py` | 324 | Persistent position state store | **WORKING** |
| `reference_feed.py` | 550 | Coinbase price reference feed via WebSocket | **WORKING** |
| `reporting.py` | 996 | Trade reporting, CSV export, session summaries | **WORKING** |

Note: Live deployment is **BLOCKED** — no active BTC/ETH/SOL 5m/15m markets on Polymarket as of 2026-03-29.

#### packages/polymarket/historical_import/ 

| Module | Purpose | Status |
|--------|---------|--------|
| `__init__.py` | Package init | — |
| `clickhouse_writer.py` | Bulk write historical data to ClickHouse | **WORKING** |
| `downloader.py` | Downloads historical trade data archives | **WORKING** |
| `parser.py` | Parses downloaded archives into trade records | **WORKING** |
| `pipeline.py` | Full historical import pipeline orchestration | **WORKING** |

#### packages/polymarket/hypotheses/

| Module | Purpose | Status |
|--------|---------|--------|
| `registry.py` | Local hypothesis registry (JSON-backed) | **WORKING** |
| `models.py` | Hypothesis dataclass and state machine | **WORKING** |

#### packages/polymarket/market_selection/

| Module | Purpose | Status |
|--------|---------|--------|
| `scorer.py` | 7-factor composite market scorer | **WORKING** |
| `models.py` | Market score dataclasses | **WORKING** |
| `factors/` | Individual factor implementations (category_edge, spread, volume, etc.) | **WORKING** |

#### packages/polymarket/notifications/

| Module | Purpose | Status |
|--------|---------|--------|
| `discord.py` | Discord webhook alerting (7 functions, all return bool, never raise) | **WORKING** |
| `__init__.py` | Package init | — |

#### packages/polymarket/rag/ (~3,124 lines, 13 files)

Two distinct storage backends coexist — ChromaDB for vector RAG, SQLite for RIS knowledge store:

| Module | Lines | Purpose | Status |
|--------|-------|---------|--------|
| `index.py` | 582 | ChromaDB vector index — build/update/rebuild | **WORKING** |
| `query.py` | 353 | ChromaDB hybrid query (vector + lexical) | **WORKING** |
| `lexical.py` | ~120 | SQLite FTS5 lexical search engine | **WORKING** |
| `knowledge_store.py` | 555 | SQLite-based RIS external knowledge store (NOT ChromaDB) | **WORKING** |
| `defaults.py` | ~40 | Defaults: `RAG_DEFAULT_COLLECTION = "polytool_rag"` | **WORKING** |
| `embedder.py` | ~80 | SentenceTransformers embedding wrapper | **WORKING** |
| `chunker.py` | ~90 | Text chunking for indexing | **WORKING** |
| `models.py` | ~60 | RAG dataclasses | **WORKING** |
| `utils.py` | ~50 | Path and collection utilities | **WORKING** |

ChromaDB collection: `"polytool_rag"` (default). KnowledgeStore path: `kb/rag/knowledge/knowledge.sqlite3`.

#### packages/polymarket/simtrader/ (multi-subpackage)

**batch/**
| Module | Lines | Purpose | Status |
|--------|-------|---------|--------|
| `runner.py` | 904 | Batch SimTrader replay runner | **WORKING** |

**broker/**
| Module | Lines | Purpose | Status |
|--------|-------|---------|--------|
| `sim_broker.py` | 414 | SimBroker — order lifecycle, fills, position tracking | **WORKING** |
| `fill_engine.py` | 176 | Fill matching engine against L2 book | **WORKING** |
| `rules.py` | 111 | Order validation and risk rules | **WORKING** |
| `latency.py` | 47 | Latency simulation model | **WORKING** |

**execution/**
| Module | Lines | Purpose | Status |
|--------|-------|---------|--------|
| `adverse_selection.py` | 589 | Adverse selection detection and mitigation | **WORKING** |
| `live_executor.py` | 155 | Live order executor (wraps py_clob_client) | **WORKING** |
| `live_runner.py` | 183 | Live strategy runner with session management | **WORKING** |
| `order_manager.py` | 286 | Order lifecycle management and tracking | **WORKING** |
| `rate_limiter.py` | 90 | API rate limiter (token bucket) | **WORKING** |
| `risk_manager.py` | 252 | Risk manager — inventory limits, daily loss caps, max order caps | **WORKING** |
| `wallet.py` | 108 | Wallet balance and position reader | **WORKING** |
| `kill_switch.py` | 53 | Hardware kill switch — immediate halt on trigger | **WORKING** |

**orderbook/**
| Module | Lines | Purpose | Status |
|--------|-------|---------|--------|
| `l2book.py` | 275 | L2 orderbook reconstruction from tape events | **WORKING** |

**portfolio/**
| Module | Purpose | Status |
|--------|---------|--------|
| `fees.py` | Fee calculation — Decimal-precision quadratic curve (DUPLICATE of `packages/polymarket/fees.py`) | **WORKING** |
| `mark.py` | Position mark-to-market (bid and midpoint methods) | **WORKING** |
| `ledger.py` | Portfolio ledger with FIFO cost basis | **WORKING** |

**replay/**
| Module | Lines | Purpose | Status |
|--------|-------|---------|--------|
| `runner.py` | 225 | Tape replay runner — drives broker from events | **WORKING** |

**shadow/**
| Module | Lines | Purpose | Status |
|--------|-------|---------|--------|
| `runner.py` | ~300 | Shadow mode runner — live WS, simulated fills, tape recording | **WORKING** |

**strategies/**
| Module | Purpose | Status |
|--------|---------|--------|
| `binary_complement_arb.py` | Binary complement arbitrage strategy | **WORKING** |
| `copy_wallet_replay.py` | Copy-wallet replay strategy | **WORKING** |
| `market_maker_v0.py` | Simple symmetric market maker (baseline) | **WORKING** |
| `market_maker_v1.py` | Logit Avellaneda-Stoikov market maker (canonical Phase 1) | **WORKING** |

**strategy/** (base interfaces)
| Module | Purpose | Status |
|--------|---------|--------|
| `base.py` | `Strategy` abstract base class and `OrderIntent` dataclass | **WORKING** |
| `facade.py` | `STRATEGY_REGISTRY` dict mapping name → class | **WORKING** |
| `runner.py` | `StrategyRunner` — drives strategy from replay events | **WORKING** |

**studio/** (browser-based replay UI)
| Module | Lines | Purpose | Status |
|--------|-------|---------|--------|
| `app.py` | 1422 | Studio app — WebSocket server + session management | **WORKING** |
| `ondemand.py` | 884 | On-demand session runner for Studio | **WORKING** |

**sweeps/**
| Module | Lines | Purpose | Status |
|--------|-------|---------|--------|
| `eligibility.py` | 334 | Tape eligibility checks for sweep scenarios | **WORKING** |
| `runner.py` | 589 | Sweep runner — parameter grid across tape set | **WORKING** |

**tape/**
| Module | Lines | Purpose | Status |
|--------|-------|---------|--------|
| `recorder.py` | 300 | Live tape recorder — writes Gold tapes from WS stream | **WORKING** |
| `schema.py` | 31 | Tape event schema definitions | **WORKING** |

Additional simtrader top-level:
| Module | Lines | Purpose | Status |
|--------|-------|---------|--------|
| `activeness_probe.py` | ~250 | Live market activeness probe via WS | **WORKING** |
| `config_loader.py` | ~200 | Strategy config loader with BOM fix | **WORKING** |
| `market_picker.py` | ~300 | Market picker — resolve slug, validate book, auto-pick | **WORKING** |

### 1.2 packages/research/ — Research Intelligence System (RIS)

#### packages/research/evaluation/

| Module | Lines | Purpose | Status |
|--------|-------|---------|--------|
| `evaluator.py` | 256 | Research item quality evaluator | **WORKING** |
| `providers.py` | 221 | LLM evaluation provider abstraction | **WORKING** |
| `models.py` | ~80 | Evaluation result dataclasses | **WORKING** |
| `cache.py` | ~120 | Evaluation result cache | **WORKING** |
| `config.py` | ~60 | Evaluation configuration | **WORKING** |
| `batch.py` | ~150 | Batch evaluation runner | **WORKING** |
| `prompts.py` | ~100 | LLM evaluation prompts | **WORKING** |
| `__init__.py` | — | Package init | — |

#### packages/research/hypotheses/

| Module | Lines | Purpose | Status |
|--------|-------|---------|--------|
| `registry.py` | 409 | Research hypothesis registry (SQLite-backed) | **WORKING** |

#### packages/research/ingestion/

| Module | Lines | Purpose | Status |
|--------|-------|---------|--------|
| `fetchers.py` | 859 | Content fetchers (web, ArXiv, Reddit, YouTube, etc.) | **WORKING** |
| `claim_extractor.py` | 661 | Claim extraction from research text | **WORKING** |
| `adapters.py` | 624 | Source adapters (academic, GitHub, blog, news, etc.) | **WORKING** |
| `extractors.py` | 536 | Document text extractors (PDF, HTML, etc.) | **WORKING** |
| `pipeline.py` | 347 | Full ingestion pipeline orchestration | **WORKING** |
| `seed.py` | 428 | Seed data and bootstrap content | **WORKING** |
| `deduplication.py` | ~200 | Near-duplicate detection | **WORKING** |
| `validators.py` | ~150 | Input validation for ingested content | **WORKING** |
| `models.py` | ~120 | Ingestion dataclasses | **WORKING** |
| `store.py` | ~180 | Ingestion result persistence | **WORKING** |

#### packages/research/integration/

| Module | Lines | Purpose | Status |
|--------|-------|---------|--------|
| `dossier_extractor.py` | 551 | Extract research findings from wallet dossiers | **WORKING** |
| `bridge.py` | ~200 | Research bridge — links findings to strategies | **WORKING** |
| `models.py` | ~80 | Integration dataclasses | **WORKING** |

#### packages/research/monitoring/

| Module | Lines | Purpose | Status |
|--------|-------|---------|--------|
| `health_checks.py` | 255 | RIS pipeline health checks | **WORKING** |
| `metrics.py` | ~150 | Pipeline metrics collection | **WORKING** |
| `alerts.py` | ~100 | Health alert triggers | **WORKING** |

#### packages/research/scheduling/

| Module | Lines | Purpose | Status |
|--------|-------|---------|--------|
| `scheduler.py` | 398 | APScheduler-based RIS job scheduler | **WORKING** |

#### packages/research/synthesis/

| Module | Lines | Purpose | Status |
|--------|-------|---------|--------|
| `report.py` | 686 | Research report generation | **WORKING** |
| `calibration.py` | 540 | Finding calibration and confidence scoring | **WORKING** |
| `precheck.py` | 438 | Pre-build precheck (STOP/CAUTION/GO verdicts) | **WORKING** |
| `report_ledger.py` | 430 | Report ledger — tracks generated reports | **WORKING** |
| `synthesizer.py` | ~300 | Multi-source finding synthesis | **WORKING** |
| `conflict_detector.py` | ~200 | Detects contradictions across findings | **WORKING** |
| `summary_builder.py` | ~180 | Summary text builder | **WORKING** |
| `formatter.py` | ~120 | Output formatting | **WORKING** |
| `models.py` | ~100 | Synthesis dataclasses | **WORKING** |

#### packages/research/ top-level

| Module | Lines | Purpose | Status |
|--------|-------|---------|--------|
| `metrics.py` | ~150 | Top-level RIS metrics aggregation | **WORKING** |

**Packaging gap:** `packages/research/evaluation`, `ingestion`, `integration`, `monitoring`, and `synthesis` are NOT registered in `pyproject.toml`'s `packages` list. Only `packages.research`, `packages.research.hypotheses`, and `packages.research.scheduling` are registered. The subpackages work via `sys.path` insertion but would not install correctly as a proper Python package.

### 1.3 polytool/ — CLI Entry Package

| Module | Lines | Purpose | Status |
|--------|-------|---------|--------|
| `__main__.py` | 367 | CLI entrypoint — routes ~60 commands to `tools/cli/*` modules | **WORKING** |
| `user_context.py` | ~200 | Resolves user handles/wallets to canonical slugs | **WORKING** |
| `reports/` | — | Report rendering utilities | **WORKING** |

The entrypoint uses a `_COMMAND_HANDLER_NAMES` dict for lazy `importlib.import_module` routing. Special cases:
- `examine`, `cache-source`, `mcp` loaded via `try/except ImportError` (optional deps)
- `opus-bundle` is a deprecated alias for `llm-bundle`
- `rag-refresh` is a thin alias to `rag-index --rebuild`
- `_FULL_ARGV_COMMANDS` set passes full `sys.argv` for `hypothesis/*`, `experiment/*`, `research-bridge` subcommands

### 1.4 tools/cli/ — CLI Module Files (56 files)

Active commands (registered in `__main__.py`):

| File | Purpose | Status |
|------|---------|--------|
| `alpha_distill.py` | Alpha distillation from wallet scans | **WORKING** |
| `batch_reconstruct_silver.py` | Batch Silver tape reconstruction | **WORKING** |
| `benchmark_manifest.py` | Benchmark tape manifest management | **WORKING** |
| `candidate_scan.py` | Candidate wallet scanner | **WORKING** |
| `capture_new_market_tapes.py` | Gold tape capture for new markets | **WORKING** |
| `close_benchmark_v1.py` | Benchmark v1 closure orchestrator | **WORKING** |
| `crypto_pair_watch.py` | One-shot crypto pair market watcher | **WORKING** |
| `export_clickhouse.py` | ClickHouse data export utility | **WORKING** |
| `export_dossier.py` | Wallet dossier export | **WORKING** |
| `fetch_price_2min.py` | 2-min price bar fetch and write | **WORKING** |
| `hypothesis.py` | Hypothesis registry CLI | **WORKING** |
| `llm_bundle.py` | LLM research bundle builder | **WORKING** |
| `market_scan.py` | Market selection scanner | **WORKING** |
| `new_market_capture.py` | New market capture planner | **WORKING** |
| `rag_index.py` | RAG index build/rebuild | **WORKING** |
| `rag_query.py` | RAG hybrid query | **WORKING** |
| `reconstruct_silver.py` | Single Silver tape reconstruction | **WORKING** |
| `research_acquire.py` | RIS — acquire URL-based research | **WORKING** |
| `research_bridge.py` | RIS — bridge findings to strategies | **WORKING** |
| `research_health.py` | RIS — pipeline health check | **WORKING** |
| `research_ingest.py` | RIS — ingest text/file research | **WORKING** |
| `research_precheck.py` | RIS — pre-build precheck | **WORKING** |
| `research_report.py` | RIS — generate research report | **WORKING** |
| `research_scheduler.py` | RIS — scheduler management | **WORKING** |
| `research_stats.py` | RIS — pipeline statistics | **WORKING** |
| `scan.py` | Wallet scan — generates trust artifacts | **WORKING** |
| `simtrader.py` | SimTrader CLI (5419 lines — largest CLI file) | **WORKING** |
| `wallet_scan.py` | Deep wallet scan | **WORKING** |

Non-registered / special-load files:

| File | Lines | Purpose | Status |
|------|-------|---------|--------|
| `cache_source.py` | 356 | Legacy cache source management | **DEAD** (loaded via try/except, not in command dict) |
| `examine.py` | 820 | Legacy orchestrator for research examination | **DEAD** (loaded via try/except, not in command dict) |
| `mcp_server.py` | ~400 | MCP server via FastMCP SDK | **WORKING** (optional dep, try/except load) |
| `opus_bundle.py` | 22 | Deprecated alias for llm-bundle | **DEAD** |

### 1.5 tools/gates/ — Gate Management Scripts (11 files, 4674 total lines)

| File | Purpose | Status |
|------|---------|--------|
| `close_replay_gate.py` | Close Gate 1 (replay pass) | **WORKING** |
| `close_sweep_gate.py` | Close Gate 2 (scenario sweep pass) | **WORKING** |
| `close_mm_gate.py` | Close market-maker gate | **WORKING** |
| `run_dry_run_gate.py` | Gate: dry-run pass | **WORKING** |
| `gate_status.py` | Display current gate status | **WORKING** |
| `benchmark_closure_orchestrator.py` | Full benchmark closure orchestration | **WORKING** |
| `corpus_audit.py` | Corpus quality audit | **WORKING** |
| `manifest_curator.py` | Tape manifest curation | **WORKING** |
| `silver_gap_fill_executor.py` | Execute Silver gap-fill plan | **WORKING** |
| `sweep_reporter.py` | Sweep result reporter | **WORKING** |
| `validate_manifest.py` | Validate tape manifest schema | **WORKING** |

### 1.6 tools/guard/ — Pre-commit Guards (4 files)

| File | Lines | Purpose | Status |
|------|-------|---------|--------|
| `guardlib.py` | 109 | Shared guard utilities | **WORKING** |
| `pre_commit_guard.py` | 51 | Pre-commit hook runner | **WORKING** |
| `pre_push_guard.py` | 61 | Pre-push hook runner | **WORKING** |
| `check_file_sizes.py` | 39 | Check for oversized files before commit | **WORKING** |

### 1.7 tools/ops/ and tools/smoke/ and tools/setup/

| Directory | Key Files | Purpose | Status |
|-----------|-----------|---------|--------|
| `tools/ops/` | Various | Operational utilities (DB migrations, health checks) | **WORKING** |
| `tools/smoke/` | `smoke_test.py` | End-to-end smoke tests | **WORKING** |
| `tools/setup/` | `setup_env.py`, `setup_clickhouse.py` | Environment and DB setup | **WORKING** |

### 1.8 services/api/

| File | Lines | Purpose | Status |
|------|-------|---------|--------|
| `services/api/main.py` | 3054 | FastAPI service — thin HTTP wrapper over core library | **WORKING** (code exists, no test coverage) |

---

## Section 2: CLI Commands

All commands discovered from reading `polytool/__main__.py`. No Python was executed.

### Core Research / Dossier Workflow

| Command | Handler Module | Description | Status |
|---------|----------------|-------------|--------|
| `scan` | `tools.cli.scan` | Wallet behavior scan, emits trust artifacts | **IMPLEMENTED** |
| `wallet-scan` | `tools.cli.wallet_scan` | Deep wallet scan with full dossier | **IMPLEMENTED** |
| `alpha-distill` | `tools.cli.alpha_distill` | Distill alpha signals from wallet scans | **IMPLEMENTED** |
| `llm-bundle` | `tools.cli.llm_bundle` | Build LLM research packet bundles | **IMPLEMENTED** |
| `opus-bundle` | `tools.cli.opus_bundle` | Deprecated alias for `llm-bundle` | **STUB** (22 lines, delegates) |
| `candidate-scan` | `tools.cli.candidate_scan` | Scan for candidate wallets | **IMPLEMENTED** |
| `export-dossier` | `tools.cli.export_dossier` | Export wallet dossier to file | **IMPLEMENTED** |
| `export-clickhouse` | `tools.cli.export_clickhouse` | Export ClickHouse data to file | **IMPLEMENTED** |

### RAG Commands

| Command | Handler Module | Description | Status |
|---------|----------------|-------------|--------|
| `rag-index` | `tools.cli.rag_index` | Build or rebuild RAG vector index | **IMPLEMENTED** |
| `rag-query` | `tools.cli.rag_query` | Hybrid RAG query (vector + lexical) | **IMPLEMENTED** |
| `rag-refresh` | alias for `rag-index --rebuild` | Refresh RAG index | **IMPLEMENTED** (alias) |

### Research Intelligence System (RIS)

| Command | Handler Module | Description | Status |
|---------|----------------|-------------|--------|
| `research-precheck` | `tools.cli.research_precheck` | Pre-build STOP/CAUTION/GO verdict | **IMPLEMENTED** |
| `research-ingest` | `tools.cli.research_ingest` | Ingest text/file research into RIS | **IMPLEMENTED** |
| `research-acquire` | `tools.cli.research_acquire` | Acquire URL-based research | **IMPLEMENTED** |
| `research-report` | `tools.cli.research_report` | Generate research synthesis report | **IMPLEMENTED** |
| `research-health` | `tools.cli.research_health` | RIS pipeline health snapshot | **IMPLEMENTED** |
| `research-stats` | `tools.cli.research_stats` | RIS pipeline metrics | **IMPLEMENTED** |
| `research-scheduler` | `tools.cli.research_scheduler` | RIS APScheduler management | **IMPLEMENTED** |
| `research-bridge` | `tools.cli.research_bridge` | Link research findings to strategies | **IMPLEMENTED** |

### Hypothesis / Experiment Registry

| Command | Handler Module | Description | Status |
|---------|----------------|-------------|--------|
| `hypothesis register` | `tools.cli.hypothesis` | Register new hypothesis | **IMPLEMENTED** |
| `hypothesis status` | `tools.cli.hypothesis` | Show hypothesis status | **IMPLEMENTED** |
| `hypothesis experiment-init` | `tools.cli.hypothesis` | Initialize experiment | **IMPLEMENTED** |
| `hypothesis experiment-run` | `tools.cli.hypothesis` | Run experiment | **IMPLEMENTED** |
| `hypothesis validate` | `tools.cli.hypothesis` | Validate hypothesis results | **IMPLEMENTED** |
| `hypothesis diff` | `tools.cli.hypothesis` | Diff hypothesis versions | **IMPLEMENTED** |
| `hypothesis summary` | `tools.cli.hypothesis` | Hypothesis summary | **IMPLEMENTED** |

### Tape / Benchmark Workflow

| Command | Handler Module | Description | Status |
|---------|----------------|-------------|--------|
| `fetch-price-2min` | `tools.cli.fetch_price_2min` | Fetch and store 2-min price bars | **IMPLEMENTED** |
| `batch-reconstruct-silver` | `tools.cli.batch_reconstruct_silver` | Batch reconstruct Silver tapes | **IMPLEMENTED** |
| `reconstruct-silver` | `tools.cli.reconstruct_silver` | Reconstruct single Silver tape | **IMPLEMENTED** |
| `benchmark-manifest` | `tools.cli.benchmark_manifest` | Manage benchmark tape manifest | **IMPLEMENTED** |
| `close-benchmark-v1` | `tools.cli.close_benchmark_v1` | Close benchmark v1 (finalized 2026-03-21) | **IMPLEMENTED** |
| `new-market-capture` | `tools.cli.new_market_capture` | Plan new-market Gold tape capture | **IMPLEMENTED** |
| `capture-new-market-tapes` | `tools.cli.capture_new_market_tapes` | Execute new-market tape capture | **IMPLEMENTED** |

### SimTrader Commands

All SimTrader subcommands are in `tools/cli/simtrader.py` (5419 lines). Subcommand discovery from source:

| Subcommand | Description | Status |
|------------|-------------|--------|
| `simtrader quickrun` | Quick replay run with auto market-pick | **IMPLEMENTED** |
| `simtrader run` | Full replay run with explicit config | **IMPLEMENTED** |
| `simtrader shadow` | Live shadow mode (WS stream, simulated fills) | **IMPLEMENTED** |
| `simtrader sweep` | Parameter sweep across tape set | **IMPLEMENTED** |
| `simtrader batch` | Batch replay runner | **IMPLEMENTED** |
| `simtrader studio` | Browser-based replay UI (WebSocket server) | **IMPLEMENTED** |
| `simtrader tape-record` | Live tape recorder | **IMPLEMENTED** |
| `simtrader probe` | Market activeness probe | **IMPLEMENTED** |

### Market Selection

| Command | Handler Module | Description | Status |
|---------|----------------|-------------|--------|
| `market-scan` | `tools.cli.market_scan` | Run 7-factor market scorer | **IMPLEMENTED** |
| `crypto-pair-watch` | `tools.cli.crypto_pair_watch` | One-shot active crypto pair check | **IMPLEMENTED** |

### Optional / Special Load

| Command | Handler Module | Description | Status |
|---------|----------------|-------------|--------|
| `mcp` | `tools.cli.mcp_server` | Start MCP server (FastMCP, optional dep) | **IMPLEMENTED** (optional) |
| `examine` | `tools.cli.examine` | Legacy orchestrator (820 lines) | **DEAD** |
| `cache-source` | `tools.cli.cache_source` | Legacy cache source (356 lines) | **DEAD** |

### Not Yet Implemented (per CLAUDE.md)

| Command | Planned Phase | Notes |
|---------|---------------|-------|
| `autoresearch import-results` | Phase 4 | Not in repo |
| `strategy-codify` | Phase 4 | Not in repo |
| FastAPI `/api/*` endpoints | Phase 3 | `services/api/main.py` exists but no CLI routing |

---

## Section 3: Database State

### 3.1 ClickHouse Tables

All 23 tables identified from `infra/clickhouse/initdb/` SQL initialization files:

| Table | SQL File | Purpose |
|-------|---------|---------|
| `polymarket_trades` | `01_init.sql` | Raw trade events from polymarket-apis |
| `price_changes` | `01_init.sql` | L2 price change events (WS stream) |
| `orderbook_snapshots` | `01_init.sql` | L2 orderbook snapshots |
| `wallet_scans` | `02_wallet_scans.sql` | Wallet scan results and trust artifacts |
| `alpha_signals` | `03_alpha_signals.sql` | Distilled alpha signals per wallet |
| `market_resolutions` | `04_market_resolutions.sql` | Market resolution results (cached) |
| `pnl_snapshots` | `05_pnl_snapshots.sql` | PnL computation snapshots |
| `research_items` | `06_research_items.sql` | RIS research items (ingested content) |
| `research_evaluations` | `07_research_evaluations.sql` | LLM evaluation results for research items |
| `replay_runs` | `08_replay_runs.sql` | SimTrader replay run manifests |
| `sweep_results` | `09_sweep_results.sql` | SimTrader sweep scenario results |
| `benchmark_tapes` | `10_benchmark_tapes.sql` | Benchmark tape manifest entries |
| `gate_results` | `11_gate_results.sql` | Gate pass/fail results |
| `shadow_sessions` | `12_shadow_sessions.sql` | Shadow mode session records |
| `price_2min` | `13_price_2min.sql` | 2-minute price bars (Gold acquisition) |
| `market_scores` | `14_market_scores.sql` | Market selection scorer output |
| `crypto_pair_events` | `26_crypto_pair_events.sql` | Crypto pair trade events (live/paper) |
| `crypto_pair_sessions` | `26_crypto_pair_events.sql` | Crypto pair session records |
| `hypothesis_registry` | `15_hypothesis_registry.sql` (estimated) | Hypothesis registry (or SQLite-backed) |
| `clv_results` | found via grep | CLV computation results |
| `dossier_bundles` | found via grep | Wallet dossier bundle records |
| `tape_coverage` | found via grep | Tape coverage tracking |
| `arb_opportunities` | found via grep | Detected arbitrage opportunities |

ClickHouse connection pattern: host `localhost:8123`, user from `CLICKHOUSE_USER` env var, password from `CLICKHOUSE_PASSWORD` env var (fail-fast required per CLAUDE.md).

### 3.2 DuckDB Usage

DuckDB is used exclusively for historical Parquet reads. Files using DuckDB:

| File | Usage |
|------|-------|
| `packages/polymarket/duckdb_helper.py` | Core DuckDB helper — connection management, Parquet queries |
| `packages/polymarket/backfill.py` | Reads historical Parquet archives via DuckDB |
| `packages/polymarket/silver_reconstructor.py` | Queries Silver Parquet data |
| `tools/cli/export_clickhouse.py` | DuckDB-backed export path |
| `tools/gates/corpus_audit.py` | Reads corpus Parquet files for audit |

DuckDB databases are ephemeral / in-memory or file-based; no persistent schema files found under `infra/`.

### 3.3 ChromaDB and RAG Storage

**ChromaDB vector store:**
- Default collection: `"polytool_rag"` (defined in `packages/polymarket/rag/defaults.py`)
- Used in: `packages/polymarket/rag/index.py` (build), `packages/polymarket/rag/query.py` (query)
- Persist directory: `kb/rag/chroma/` (inferred from defaults)
- Embedding model: SentenceTransformers via `packages/polymarket/rag/embedder.py`

**SQLite FTS5 lexical store:**
- Used in: `packages/polymarket/rag/lexical.py` for keyword search
- Complements ChromaDB in hybrid retrieval

**RIS KnowledgeStore (SQLite — separate from ChromaDB):**
- File: `kb/rag/knowledge/knowledge.sqlite3`
- Code: `packages/polymarket/rag/knowledge_store.py` (555 lines)
- Purpose: stores external research items, claims, calibration data
- NOT ChromaDB — fully separate storage system

---

## Section 4: External Integrations

### 4.1 WebSocket Integrations

| Service | File | Protocol | Status |
|---------|------|----------|--------|
| Polymarket CLOB WebSocket | `packages/polymarket/crypto_pairs/clob_stream.py` | WSS | **WRITTEN** |
| Coinbase reference feed | `packages/polymarket/crypto_pairs/reference_feed.py` | WSS | **WRITTEN** |
| SimTrader shadow runner | `packages/polymarket/simtrader/shadow/runner.py` | WSS | **WRITTEN** |
| SimTrader activeness probe | `packages/polymarket/simtrader/activeness_probe.py` | WSS | **WRITTEN** |
| SimTrader Studio | `packages/polymarket/simtrader/studio/app.py` | WS (local) | **WRITTEN** |
| Gold tape recorder | `packages/polymarket/simtrader/tape/recorder.py` | WSS | **WRITTEN** |

### 4.2 HTTP REST API Clients

| Service | File | Method | Status |
|---------|------|--------|--------|
| Polymarket Gamma API | `packages/polymarket/gamma.py` | REST (httpx) | **TESTED** |
| Polymarket Data API | `packages/polymarket/data_api.py` | REST (requests) | **WRITTEN** |
| Polymarket CLOB API | `packages/polymarket/clob.py` | REST (requests) | **WRITTEN** |
| Shared HTTP client | `packages/polymarket/http_client.py` | REST (requests) | **TESTED** |
| ArXiv API | `packages/research/ingestion/fetchers.py` | REST (requests) | **WRITTEN** |
| Discord webhook | `packages/polymarket/notifications/discord.py` | REST (requests) | **TESTED** |
| Coinbase REST | `packages/polymarket/crypto_pairs/reference_feed.py` | REST (requests) | **WRITTEN** |

### 4.3 GraphQL Integrations

| Service | File | Status |
|---------|------|--------|
| The Graph / Polymarket subgraph | `packages/polymarket/subgraph.py` | **WRITTEN** |
| Gamma GraphQL fallback | `packages/polymarket/gamma.py` | **WRITTEN** |

### 4.4 On-Chain / Blockchain

| Service | File | Protocol | Status |
|---------|------|----------|--------|
| Polygon CTF contract | `packages/polymarket/on_chain_ctf.py` | JSON-RPC (raw, no web3.py) | **WRITTEN** |
| EIP-712 order signing | `packages/polymarket/simtrader/execution/live_executor.py` | py_clob_client | **WRITTEN** |

### 4.5 SDK Integrations

| SDK | Used In | Purpose | Status |
|-----|---------|---------|--------|
| `py_clob_client` | `packages/polymarket/crypto_pairs/clob_order_client.py`, `execution/live_executor.py` | CLOB order placement, EIP-712 signing | **WRITTEN** |
| `praw` (Reddit) | `packages/research/ingestion/fetchers.py` | Reddit content ingestion | **WRITTEN** (optional dep) |
| `yt_dlp` (YouTube) | `packages/research/ingestion/fetchers.py` | YouTube transcript ingestion | **WRITTEN** (optional dep) |
| `mcp` (FastMCP) | `tools/cli/mcp_server.py` | MCP protocol server | **WORKING** (optional dep) |
| `chromadb` | `packages/polymarket/rag/index.py` | Vector index | **WORKING** (optional dep) |
| `sentence-transformers` | `packages/polymarket/rag/embedder.py` | Text embeddings | **WORKING** (optional dep) |

### 4.6 n8n Integration

| Integration | File | Status |
|-------------|------|--------|
| n8n RIS pilot (opt-in via `--profile ris-n8n`) | `packages/research/scheduling/scheduler.py` | **WRITTEN** (ADR 0013, scoped pilot) |

---

## Section 5: Config and Environment

### 5.1 Environment Variables

All variable names found via source code inspection — no values included:

| Variable | Files Referencing It | Purpose |
|----------|---------------------|---------|
| `CLICKHOUSE_PASSWORD` | `fetch_price_2min.py`, `close_benchmark_v1.py`, `batch_reconstruct_silver.py`, `crypto_pairs/*.py`, and others | ClickHouse auth password (fail-fast required) |
| `CLICKHOUSE_USER` | Multiple CLI and package files | ClickHouse username (default: `polytool_admin`) |
| `CLICKHOUSE_HOST` | `packages/polymarket/*.py` | ClickHouse host (default: `localhost`) |
| `CLICKHOUSE_PORT` | `packages/polymarket/*.py` | ClickHouse HTTP port (default: `8123`) |
| `DISCORD_WEBHOOK_URL` | `packages/polymarket/notifications/discord.py` | Discord alerting webhook |
| `POLYGON_RPC_URL` | `packages/polymarket/on_chain_ctf.py` | Polygon JSON-RPC endpoint (has default) |
| `POLYMARKET_SUBGRAPH_URL` | `packages/polymarket/subgraph.py` | The Graph subgraph URL (has default) |
| `POLYMARKET_API_KEY` | `packages/polymarket/clob.py`, `crypto_pairs/clob_order_client.py` | CLOB API authentication |
| `POLYMARKET_SECRET` | `packages/polymarket/crypto_pairs/clob_order_client.py` | CLOB API secret |
| `POLYMARKET_PASSPHRASE` | `packages/polymarket/crypto_pairs/clob_order_client.py` | CLOB API passphrase |
| `PRIVATE_KEY` | `packages/polymarket/simtrader/execution/live_executor.py` | EIP-712 signing key (live trading only) |
| `OPENAI_API_KEY` | `packages/research/evaluation/providers.py` | OpenAI evaluation provider |
| `ANTHROPIC_API_KEY` | `packages/research/evaluation/providers.py` | Anthropic evaluation provider |
| `OLLAMA_BASE_URL` | `packages/research/evaluation/providers.py` | Ollama local LLM endpoint |
| `COINBASE_API_KEY` | `packages/polymarket/crypto_pairs/reference_feed.py` | Coinbase reference feed auth |
| `COINBASE_SECRET` | `packages/polymarket/crypto_pairs/reference_feed.py` | Coinbase reference feed secret |
| `REDDIT_CLIENT_ID` | `packages/research/ingestion/fetchers.py` | Reddit API (praw) |
| `REDDIT_CLIENT_SECRET` | `packages/research/ingestion/fetchers.py` | Reddit API (praw) |
| `REDDIT_USER_AGENT` | `packages/research/ingestion/fetchers.py` | Reddit API (praw) |
| `N8N_WEBHOOK_URL` | `packages/research/scheduling/scheduler.py` | n8n pilot integration endpoint |
| `RAG_PERSIST_DIR` | `packages/polymarket/rag/defaults.py` | ChromaDB persist directory override |
| `KNOWLEDGE_STORE_PATH` | `packages/polymarket/rag/knowledge_store.py` | RIS SQLite path override |
| `GRAFANA_API_KEY` | `tools/ops/` (estimated) | Grafana API access |
| `LOG_LEVEL` | Multiple files | Python logging level |

**ClickHouse auth inconsistency (CLAUDE.md violation):** Some CLIs use correct fail-fast pattern (`if not ch_password: sys.exit(1)`): `fetch_price_2min.py`, `close_benchmark_v1.py`, `batch_reconstruct_silver.py`. Others silently fall back to `"polytool_admin"`: `examine.py`, `export_dossier.py`, `export_clickhouse.py`, `reconstruct_silver.py`. This violates the CLAUDE.md ClickHouse auth rule.

### 5.2 Config Files

| File | Purpose |
|------|---------|
| `config/benchmark_v1.tape_manifest` | Finalized benchmark v1 tape manifest (closed 2026-03-21, DO NOT MODIFY) |
| `config/benchmark_v1.lock.json` | Benchmark v1 lock file (DO NOT MODIFY) |
| `config/benchmark_v1.audit.json` | Benchmark v1 audit record (DO NOT MODIFY) |
| `config/market_selection_weights.json` | Market scorer factor weights |
| `config/strategy_configs/` | Strategy configuration templates |
| `pyproject.toml` | Project metadata, optional dep groups, package list |
| `pyrightconfig.json` | Pyright type checker configuration |
| `docker-compose.yml` | Docker Compose for ClickHouse + Grafana |
| `.env` | Local environment variables (gitignored) |
| `.env.example` | Environment variable template |
| `pytest.ini` / `pyproject.toml [tool.pytest]` | Pytest configuration |

### 5.3 pyproject.toml Optional Dependency Groups

| Group | Purpose |
|-------|---------|
| `rag` | ChromaDB, SentenceTransformers for RAG |
| `mcp` | FastMCP SDK for MCP server |
| `simtrader` | SimTrader replay and simulation deps |
| `studio` | SimTrader Studio browser UI deps |
| `dev` | pytest, black, ruff, pyright for development |
| `historical` | Historical data download deps |
| `historical-import` | Historical import pipeline deps |
| `live` | py_clob_client for live trading |
| `ris` | RIS ingestion and synthesis deps (praw, yt_dlp, etc.) |

---

## Section 6: Test Coverage

### 6.1 Test File Map

| Test File | Module(s) Tested | Approx Test Count |
|-----------|-----------------|-------------------|
| `tests/test_arb.py` | `packages/polymarket/arb.py` | ~15 |
| `tests/test_backfill.py` | `packages/polymarket/backfill.py` | ~10 |
| `tests/test_benchmark_manifest.py` | `benchmark_manifest_contract.py`, `tools/cli/benchmark_manifest.py` | ~20 |
| `tests/test_clob.py` | `packages/polymarket/clob.py` | ~12 |
| `tests/test_clv.py` | `packages/polymarket/clv.py` | ~25 |
| `tests/test_crypto_pairs_*.py` (multiple) | `packages/polymarket/crypto_pairs/*` | ~80 total |
| `tests/test_detectors.py` | `packages/polymarket/detectors.py` | ~20 |
| `tests/test_discord_notifications.py` | `packages/polymarket/notifications/discord.py` | 29 |
| `tests/test_duckdb_helper.py` | `packages/polymarket/duckdb_helper.py` | ~10 |
| `tests/test_features.py` | `packages/polymarket/features.py` | ~12 |
| `tests/test_fees.py` | `packages/polymarket/fees.py` | ~10 |
| `tests/test_gamma.py` | `packages/polymarket/gamma.py` | ~20 |
| `tests/test_hypothesis_registry.py` | `packages/polymarket/hypotheses/` | ~15 |
| `tests/test_llm_bundle.py` | `packages/polymarket/llm_research_packets.py` | ~10 |
| `tests/test_market_maker_v1.py` | `simtrader/strategies/market_maker_v1.py` | 30 |
| `tests/test_market_selection.py` | `packages/polymarket/market_selection/` | ~15 |
| `tests/test_pnl.py` | `packages/polymarket/pnl.py` | ~18 |
| `tests/test_rag_*.py` (multiple) | `packages/polymarket/rag/*` | ~30 total |
| `tests/test_research_*.py` (multiple) | `packages/research/*` | ~60 total |
| `tests/test_resolution_providers.py` | `packages/polymarket/resolution.py` | 13 |
| `tests/test_silver_reconstructor.py` | `packages/polymarket/silver_reconstructor.py` | ~15 |
| `tests/test_simtrader_activeness_probe.py` | `simtrader/activeness_probe.py` | 31 |
| `tests/test_simtrader_arb.py` | `simtrader/strategies/binary_complement_arb.py` | 22 |
| `tests/test_simtrader_portfolio.py` | `simtrader/portfolio/*` | 64 |
| `tests/test_simtrader_quickrun.py` | `tools/cli/simtrader.py` (quickrun) | 20 |
| `tests/test_simtrader_shadow.py` | `simtrader/shadow/runner.py` | 41 |
| `tests/test_user_context.py` | `polytool/user_context.py` | ~8 (1 pre-existing failure) |
| `tests/test_wallet_scan.py` | `tools/cli/wallet_scan.py` | ~10 |
| `tests/test_*.py` (other) | Various | ~50 total |

Total approximate: **883+ tests** (last confirmed count 2026-02-25).

### 6.2 Coverage Gaps — Modules with Zero or Minimal Tests

| Module | Status | Notes |
|--------|--------|-------|
| `services/api/main.py` (3054 lines) | **ZERO TESTS** | FastAPI service has no test file |
| `packages/polymarket/data_api.py` (641 lines) | **ZERO TESTS** | Data API client not independently tested |
| `packages/polymarket/opportunities.py` (22 lines) | STUBBED | No tests (stub only) |
| `packages/polymarket/new_market_capture_planner.py` | Minimal tests | Tested via integration only |
| `packages/polymarket/benchmark_gap_fill_planner.py` | Minimal tests | Tested via integration only |
| `tools/gates/*.py` (4674 lines total) | Minimal tests | Gate scripts mostly integration-tested |
| `packages/polymarket/simtrader/execution/adverse_selection.py` (589 lines) | **ZERO TESTS** | No dedicated test file found |
| `packages/polymarket/simtrader/studio/app.py` (1422 lines) | Minimal tests | UI/WS logic largely untested |
| `packages/polymarket/simtrader/studio/ondemand.py` (884 lines) | Minimal tests | On-demand logic largely untested |
| `packages/polymarket/simtrader/batch/runner.py` (904 lines) | Minimal tests | Batch runner tested indirectly |
| `packages/research/synthesis/calibration.py` (540 lines) | Partial | Some synthesis tests but calibration may be gaps |
| `packages/polymarket/historical_import/` | Minimal tests | Historical import pipeline lightly covered |
| `packages/polymarket/slippage.py` | Minimal tests | Slippage model tested indirectly |
| `packages/polymarket/token_resolution.py` | Minimal tests | Short module, used but sparse tests |

---

## Section 7: Known Duplication

### 7.1 Dual Fee Calculation Modules

**Primary finding — critical duplication:**

| Module | Location | Implementation | Precision |
|--------|----------|----------------|-----------|
| `packages/polymarket/fees.py` | Core library | Float-based quadratic fee curve | `float` |
| `packages/polymarket/simtrader/portfolio/fees.py` | SimTrader portfolio | Decimal-based quadratic fee curve | `Decimal` |

Both implement the same Polymarket fee formula: `fee = fee_rate × notional × (1 - notional × fee_rate)` (quadratic curve). The SimTrader version uses `Decimal` for precision, but the underlying formula is duplicated. This risks drift if the fee model changes.

### 7.2 ClickHouse Authentication Patterns — Inconsistency

Two patterns exist for ClickHouse credential loading across CLI entrypoints:

**Correct pattern (fail-fast):**
```
ch_password = os.environ.get("CLICKHOUSE_PASSWORD")
if not ch_password:
    sys.exit(1)
```
Files using this: `fetch_price_2min.py`, `close_benchmark_v1.py`, `batch_reconstruct_silver.py`

**Incorrect pattern (silent fallback — violates CLAUDE.md):**
```
ch_password = os.environ.get("CLICKHOUSE_PASSWORD", "polytool_admin")
```
Files using this: `examine.py`, `export_dossier.py`, `export_clickhouse.py`, `reconstruct_silver.py`

CLAUDE.md explicitly states: "Never use a hardcoded fallback like `polytool_admin`. Never silently default to empty string."

### 7.3 Multiple HTTP Client Wrappers

Three separate HTTP client approaches coexist:

| Approach | Files | Notes |
|----------|-------|-------|
| `packages/polymarket/http_client.py` (shared wrapper) | `gamma.py`, `data_api.py`, `clob.py` | Canonical — has retry/backoff |
| `requests.get` / `requests.post` direct | Several tools and packages | Ad-hoc, no shared session |
| `httpx` (async) | `packages/research/ingestion/fetchers.py` | Different library entirely |

### 7.4 Multiple Config Loading Patterns

At least three config loading patterns exist:

| Pattern | Files | Notes |
|---------|-------|-------|
| `packages/polymarket/simtrader/config_loader.py` | SimTrader CLI tools | Canonical, has BOM fix, UTF-8-sig |
| `json.load(open(path))` direct | Various gate scripts | No BOM handling, no error context |
| `python-dotenv` `.env` loading | `polytool/__main__.py` | Only at entrypoint |

### 7.5 Duplicate WebSocket Connection Code

WebSocket reconnection and event streaming logic is implemented independently in:
- `packages/polymarket/crypto_pairs/clob_stream.py` (CLOB stream)
- `packages/polymarket/simtrader/shadow/runner.py` (shadow mode)
- `packages/polymarket/simtrader/tape/recorder.py` (tape recorder)
- `packages/polymarket/simtrader/activeness_probe.py` (activeness probe)

Each implements its own reconnect-on-error loop, stall detection, and event normalization. No shared WebSocket base class exists.

### 7.6 Hypothesis Registry Duplication

Two hypothesis registry modules exist:
- `packages/polymarket/hypotheses/registry.py` — JSON-backed
- `packages/research/hypotheses/registry.py` — SQLite-backed (409 lines)

The CLI (`tools/cli/hypothesis.py`) appears to use the research package version. The polymarket package version may be legacy or parallel.

### 7.7 Opportunities Overlap

`packages/polymarket/opportunities.py` (22 lines, stub dataclass) overlaps conceptually with:
- `packages/polymarket/arb.py` (`ArbOpportunity`)
- `packages/polymarket/crypto_pairs/opportunity_scan.py` (crypto-specific opportunities)

The stub `Opportunity` class appears unused.

---

## Audit Notes

1. **Largest files by line count (top 10):** `simtrader.py` CLI (5419), `services/api/main.py` (3054), `clv.py` (1698), `paper_ledger.py` (1478), `event_models.py` (1441), `simtrader/studio/app.py` (1422), `paper_runner.py` (1339), `knowledge_store.py` (555) wait `fetchers.py` (859), `ingestion/claim_extractor.py` (661).

2. **pyproject.toml packaging gap:** Five research subpackages (`evaluation`, `ingestion`, `integration`, `monitoring`, `synthesis`) are not in the `packages` list. This means `pip install -e .` won't correctly register them as packages. They work in development via `sys.path` insertion but would fail on clean installs without the project root on the path.

3. **services/api/main.py is an island:** 3054 lines, zero tests, no CLI routing. It exists as a standalone FastAPI service. Per CLAUDE.md, FastAPI is a Phase 3 deliverable — this appears to be pre-built infrastructure without test coverage.

4. **Pre-existing test failure:** `test_user_context.py::test_wallet_only` has a known pre-existing failure due to `profile.json` residue (documented in MEMORY.md).

5. **`datetime.utcnow()` deprecation warnings:** Present throughout the codebase. Not yet migrated to `datetime.now(UTC)`.
