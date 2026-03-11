# Codebase Structure

**Analysis Date:** 2026-03-05

## Directory Layout

```
PolyTool/                            # Project root
├── polytool/                        # Installable package; CLI dispatcher only
│   ├── __main__.py                  # Entry point: routes commands to tools/cli/
│   ├── __init__.py                  # Version + package metadata
│   └── user_context.py              # Handle/wallet → slug resolution
├── tools/                           # CLI handler layer
│   └── cli/                         # One file per top-level command
│       ├── simtrader.py             # Largest CLI file; all simtrader subcommands
│       ├── scan.py
│       ├── llm_bundle.py
│       ├── rag_index.py
│       ├── rag_query.py
│       ├── rag_run.py
│       ├── rag_eval.py
│       ├── export_dossier.py
│       ├── export_clickhouse.py
│       ├── batch_run.py
│       ├── agent_run.py
│       ├── llm_save.py
│       ├── audit_coverage.py
│       ├── mcp_server.py
│       └── ...
├── packages/                        # Domain library code
│   └── polymarket/                  # All Polymarket-specific logic
│       ├── http_client.py           # Shared HTTP client (retries, backoff)
│       ├── data_api.py              # Polymarket Data API client
│       ├── gamma.py                 # Gamma API client
│       ├── resolution.py            # Resolution provider chain (Protocol + CachedResolutionProvider)
│       ├── on_chain_ctf.py          # Raw JSON-RPC on-chain resolution
│       ├── subgraph.py              # The Graph GraphQL resolution
│       ├── pnl.py                   # PnL computation
│       ├── clv.py                   # CLV computation
│       ├── clob.py                  # CLOB order book helpers
│       ├── opportunities.py         # Opportunity detection
│       ├── normalization.py         # Data normalization utilities
│       ├── llm_research_packets.py  # LLM evidence bundle assembly
│       ├── rag/                     # RAG stack (optional dep: sentence-transformers, chromadb)
│       │   ├── index.py             # Build/rebuild Chroma index
│       │   ├── query.py             # Hybrid search + reranking
│       │   ├── embedder.py
│       │   ├── chunker.py
│       │   ├── reranker.py
│       │   ├── eval.py
│       │   ├── manifest.py
│       │   ├── metadata.py
│       │   ├── lexical.py
│       │   └── defaults.py
│       └── simtrader/               # Full simulation sub-system
│           ├── tape/                # WS tape record + schema
│           │   ├── recorder.py      # TapeRecorder (writes raw_ws.jsonl + events.jsonl)
│           │   └── schema.py        # EVENT_TYPE_* constants + PARSER_VERSION
│           ├── orderbook/           # L2 book state machine
│           │   └── l2book.py        # L2Book class
│           ├── broker/              # Simulated order lifecycle
│           │   ├── sim_broker.py    # SimBroker
│           │   ├── fill_engine.py   # Price-crossing fill logic
│           │   ├── latency.py       # LatencyConfig dataclass
│           │   └── rules.py         # Order/FillRecord/Side dataclasses
│           ├── strategy/            # Strategy interface + runner
│           │   ├── base.py          # Strategy base class + OrderIntent
│           │   ├── runner.py        # StrategyRunner (main replay loop)
│           │   └── facade.py        # run_strategy() + STRATEGY_REGISTRY
│           ├── strategies/          # Concrete strategy implementations
│           │   ├── binary_complement_arb.py
│           │   └── copy_wallet_replay.py
│           ├── portfolio/           # Portfolio accounting
│           │   ├── ledger.py        # PortfolioLedger (FIFO PnL, equity curve)
│           │   ├── fees.py          # Fee curve calculation
│           │   └── mark.py          # Mark-to-market methods (bid / midpoint)
│           ├── shadow/              # Live WS shadow mode
│           │   └── runner.py        # ShadowRunner
│           ├── sweeps/              # Parameter sweep orchestration
│           │   └── runner.py        # SweepRunner
│           ├── batch/               # Multi-market batch orchestration
│           │   └── runner.py        # BatchRunner
│           ├── studio/              # SimTrader Studio UI (FastAPI, optional dep)
│           │   ├── app.py           # create_app() factory
│           │   ├── ondemand.py      # On-demand session management
│           │   └── static/          # Frontend HTML/JS/CSS
│           ├── config_loader.py     # JSON strategy config loading (BOM-safe)
│           ├── market_picker.py     # MarketPicker + ResolvedMarket
│           ├── activeness_probe.py  # ActivenessProbe (WS event counting)
│           ├── studio_sessions.py   # StudioSessionManager (subprocess + SSE)
│           ├── strategy_presets.py  # STRATEGY_PRESET_CHOICES + preset builders
│           ├── artifact_ids.py      # Timestamped/deterministic ID generation
│           ├── display_name.py      # Human-readable artifact name builders
│           └── report.py            # Run report generation
├── tests/                           # All tests (co-located by convention)
│   ├── conftest.py                  # Shared fixtures
│   ├── test_simtrader_*.py          # SimTrader-specific test modules
│   └── test_*.py                    # Other domain tests
├── infra/                           # Docker infrastructure
│   ├── clickhouse/
│   │   └── initdb/                  # SQL migration scripts (numbered prefix)
│   └── grafana/
│       ├── dashboards/              # Dashboard JSON files
│       └── provisioning/            # Grafana datasource/dashboard provisioning
├── services/                        # Long-running service processes
│   ├── api/
│   │   └── main.py                  # FastAPI service (Docker Compose only)
│   └── worker/                      # Background worker skeleton
├── artifacts/                       # Runtime output (gitignored)
│   └── simtrader/
│       ├── tapes/                   # Recorded WS tapes
│       ├── runs/                    # Single strategy run outputs
│       ├── sweeps/                  # Sweep outputs
│       ├── batches/                 # Batch outputs
│       └── shadow_runs/             # Shadow mode outputs
├── docs/                            # Documentation
│   ├── specs/                       # Codex specification files (READ-ONLY)
│   ├── features/                    # Feature documentation
│   └── dev_logs/                    # Development log entries
├── scripts/                         # One-off utility scripts
├── kb/                              # Private knowledge base (gitignored)
├── pyproject.toml                   # Package metadata, deps, pytest config
├── docker-compose.yml               # ClickHouse + Grafana + services
└── CLAUDE.md                        # Project-level Claude Code instructions
```

## Directory Purposes

**`polytool/`:**
- Purpose: Thin installable package; entry point dispatch only
- Contains: `__main__.py` (router), `__init__.py` (version), `user_context.py`
- Key files: `polytool/__main__.py` — the only file that wires commands to handlers

**`tools/cli/`:**
- Purpose: One `main(argv) -> int` function per CLI command
- Contains: Argument parsing (`argparse`), input validation, calls into `packages/polymarket/`
- Key files: `tools/cli/simtrader.py` (largest, ~1500+ lines covering all simtrader subcommands)

**`packages/polymarket/`:**
- Purpose: All domain business logic; designed to be imported by CLI handlers and tests
- Contains: HTTP clients, data models (dataclasses), provider chains, algorithms
- Key files: `packages/polymarket/resolution.py`, `packages/polymarket/data_api.py`, `packages/polymarket/http_client.py`

**`packages/polymarket/simtrader/`:**
- Purpose: Complete market simulation toolkit: tape I/O, L2 book, broker simulation, strategy framework, portfolio accounting, live shadow mode, parameter sweeps, batch runs, Studio UI
- Contains: Eight sub-packages plus top-level utilities
- Key files: `strategy/base.py` (Strategy interface), `strategy/runner.py` (main loop), `broker/sim_broker.py`, `orderbook/l2book.py`

**`packages/polymarket/rag/`:**
- Purpose: Local RAG index (Chroma) for knowledge base retrieval
- Contains: Chunker, embedder, lexical index, reranker, eval utilities
- Key files: `packages/polymarket/rag/index.py`, `packages/polymarket/rag/query.py`

**`tests/`:**
- Purpose: All automated tests; flat directory (no sub-directories for different domains)
- Contains: `test_*.py` files per feature area; shared fixtures in `conftest.py`
- Key files: `tests/conftest.py`, `tests/test_simtrader_*.py` (majority of test volume)

**`infra/`:**
- Purpose: Docker-managed infrastructure configuration
- Contains: ClickHouse init SQL (numbered prefix for ordering), Grafana JSON dashboards, Docker provisioning YAML
- Key files: `infra/clickhouse/initdb/` (migration scripts), `infra/grafana/dashboards/`

**`artifacts/`:**
- Purpose: Runtime output directory; all CLI tools write here
- Generated: Yes, at runtime
- Committed: No (gitignored)

**`docs/specs/`:**
- Purpose: Codex specification files — source of truth for feature contracts
- Generated: No
- Committed: Yes
- **IMPORTANT: Do not modify files in this directory**

## Key File Locations

**Entry Points:**
- `polytool/__main__.py`: Primary CLI entry point and command router
- `packages/polymarket/simtrader/studio/app.py`: Studio HTTP app factory (`create_app()`)
- `tools/cli/mcp_server.py`: MCP server entry point

**Configuration:**
- `pyproject.toml`: Package deps, optional dep groups, pytest settings
- `docker-compose.yml`: Infrastructure service definitions
- `.env` / `.env.example`: Environment variable definitions (secrets gitignored)

**Core Domain Logic:**
- `packages/polymarket/resolution.py`: Market resolution provider chain
- `packages/polymarket/data_api.py`: Polymarket trade history client
- `packages/polymarket/simtrader/strategy/runner.py`: SimTrader replay loop
- `packages/polymarket/simtrader/broker/sim_broker.py`: Simulated broker
- `packages/polymarket/simtrader/orderbook/l2book.py`: L2 order book

**Strategy Interface:**
- `packages/polymarket/simtrader/strategy/base.py`: `Strategy` base class + `OrderIntent`
- `packages/polymarket/simtrader/strategy/facade.py`: `STRATEGY_REGISTRY` + `run_strategy()`
- `packages/polymarket/simtrader/strategies/`: Concrete strategy implementations

**Testing:**
- `tests/conftest.py`: Shared pytest fixtures

## Naming Conventions

**Files:**
- Python modules: `snake_case.py`
- Test files: `test_<module_or_feature>.py` (e.g. `test_simtrader_broker.py`)
- Artifact files: `snake_case.jsonl` or `snake_case.json` (e.g. `run_manifest.json`, `equity_curve.jsonl`)
- Tape directories: `<YYYYMMDDTHHMMSSZ>_<id_prefix>/` (e.g. `20260305T120000Z_abc12345/`)

**Directories:**
- Sub-packages: `snake_case/` with `__init__.py`
- Artifact output dirs: `<timestamp>_<hash>` format for deterministic sort

**Classes:**
- Domain models: PascalCase dataclasses (e.g. `Trade`, `Resolution`, `ResolvedMarket`)
- Service classes: PascalCase with noun prefix (e.g. `SimBroker`, `TapeRecorder`, `StrategyRunner`)
- Errors: PascalCase + `Error` suffix (e.g. `L2BookError`, `MarketPickerError`, `ConfigLoadError`)

**Functions:**
- Public: `snake_case`
- Module-private: `_snake_case` prefix (e.g. `_build_quick_sweep_config`, `_quickrun`)
- CLI handlers: `main(argv: list[str]) -> int`

## Where to Add New Code

**New CLI command:**
1. Create handler: `tools/cli/<command_name>.py` with `main(argv: list[str]) -> int`
2. Register in: `polytool/__main__.py` (add routing if-block + import)
3. Tests: `tests/test_<command_name>.py`

**New Strategy:**
1. Implementation: `packages/polymarket/simtrader/strategies/<strategy_name>.py` — subclass `Strategy` from `strategy/base.py`
2. Register in: `packages/polymarket/simtrader/strategy/facade.py` → `STRATEGY_REGISTRY` dict
3. Tests: `tests/test_simtrader_strategy.py` or new `tests/test_simtrader_<strategy_name>.py`

**New Domain Feature (not SimTrader):**
1. Implementation: `packages/polymarket/<feature>.py`
2. CLI handler: `tools/cli/<feature>.py`
3. Tests: `tests/test_<feature>.py`

**New SimTrader Sub-system:**
1. Create sub-package: `packages/polymarket/simtrader/<subsystem>/`
2. Wire into: `tools/cli/simtrader.py` new subcommand handler
3. Tests: `tests/test_simtrader_<subsystem>.py`

**New ClickHouse Migration:**
1. Add SQL file to: `infra/clickhouse/initdb/` with numeric prefix for ordering (e.g. `04_new_table.sql`)

**New Grafana Dashboard:**
1. Add JSON to: `infra/grafana/dashboards/`

**Shared Utilities:**
- HTTP clients: `packages/polymarket/http_client.py`
- Normalization: `packages/polymarket/normalization.py`
- SimTrader artifact IDs: `packages/polymarket/simtrader/artifact_ids.py`
- SimTrader display names: `packages/polymarket/simtrader/display_name.py`

## Special Directories

**`artifacts/`:**
- Purpose: All runtime output (tapes, runs, sweeps, batches, shadow runs)
- Generated: Yes
- Committed: No

**`kb/`:**
- Purpose: Private knowledge base for RAG indexing
- Generated: Partially (some dirs created at runtime)
- Committed: No

**`docs/specs/`:**
- Purpose: Immutable Codex specification files
- Generated: No
- Committed: Yes — never modify

**`polytool.egg-info/`:**
- Purpose: Setuptools build metadata
- Generated: Yes (`pip install -e .`)
- Committed: No

---

*Structure analysis: 2026-03-05*
