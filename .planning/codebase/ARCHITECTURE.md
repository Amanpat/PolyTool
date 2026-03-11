# Architecture

**Analysis Date:** 2026-03-05

## Pattern Overview

**Overall:** Monorepo CLI toolchain with layered domain packages

**Key Characteristics:**
- Single Python package `polytool` acts as the CLI dispatcher; all logic lives in `tools/cli/` handlers or `packages/polymarket/` domain modules
- No web framework for the main CLI; SimTrader Studio is the only HTTP surface (FastAPI, optional dep)
- Domain packages are separated from CLI wiring: `packages/polymarket/` contains reusable business logic; `tools/cli/` contains only argument parsing and orchestration
- Infrastructure (ClickHouse, Grafana) is Docker Compose-only — not imported by Python code directly (accessed via `clickhouse-connect`)
- Optional dependency groups (`rag`, `mcp`, `simtrader`, `studio`) gate feature availability at import time; missing deps produce clear error messages

## Layers

**CLI Dispatcher:**
- Purpose: Route `python -m polytool <command>` to the correct handler
- Location: `polytool/__main__.py`
- Contains: Argument routing only; zero business logic
- Depends on: `tools/cli/*.py` handlers (imported at module load or lazily for optional commands)
- Used by: End users, MCP server, Studio session manager (subprocess)

**CLI Handlers (`tools/cli/`):**
- Purpose: Parse argv, validate inputs, call domain packages, print results
- Location: `tools/cli/*.py`
- Contains: `argparse` setup + handler functions; each file exposes `main(argv: list[str]) -> int`
- Depends on: `packages/polymarket/*` domain modules
- Used by: `polytool/__main__.py`

**Domain Packages (`packages/polymarket/`):**
- Purpose: All business logic — data fetching, analysis, simulation, RAG
- Location: `packages/polymarket/*.py` and sub-packages
- Contains: Dataclasses, protocol classes, provider chains, algorithms
- Depends on: External HTTP APIs (Polymarket Data API, Gamma API, on-chain JSON-RPC), ClickHouse, WS feeds
- Used by: `tools/cli/` handlers and Studio session manager

**SimTrader Sub-system (`packages/polymarket/simtrader/`):**
- Purpose: Full market simulation: tape recording, replay, strategy execution, portfolio accounting, batch orchestration, live UI
- Location: `packages/polymarket/simtrader/`
- Contains: Six sub-packages (tape, orderbook, broker, strategy, portfolio, shadow) plus studio UI, sweep/batch runners
- Depends on: Core domain packages for market resolution; optional `websocket-client` for live recording/shadow; optional `fastapi`/`uvicorn` for Studio
- Used by: `tools/cli/simtrader.py`

**Infrastructure Layer:**
- Purpose: Persistent storage and visualization
- Location: `infra/clickhouse/`, `infra/grafana/`
- Contains: ClickHouse initdb SQL migrations, Grafana dashboard JSON, Docker provisioning configs
- Depends on: Docker Compose (`docker-compose.yml`)
- Used by: `packages/polymarket/` modules via `clickhouse-connect`

**Services (`services/`):**
- Purpose: Long-running processes (API server, background worker)
- Location: `services/api/main.py`, `services/worker/`
- Contains: Lightweight FastAPI app and worker skeleton
- Depends on: `packages/polymarket/`
- Used by: Docker Compose (not yet wired into main CLI)

## Data Flow

**Scan / Analysis Flow:**
1. `polytool scan` → `tools/cli/scan.py`
2. `scan.py` resolves user handle/wallet via `polytool/user_context.py`
3. Fetches trades from `packages/polymarket/data_api.py` (Polymarket Data API)
4. Resolves market outcomes via `packages/polymarket/resolution.py` (CachedResolutionProvider: ClickHouse → OnChainCTF → Subgraph → Gamma)
5. Computes PnL/CLV via `packages/polymarket/pnl.py` / `packages/polymarket/clv.py`
6. Writes artifacts to `artifacts/` directory

**SimTrader Replay Flow:**
1. `polytool simtrader record` → `packages/polymarket/simtrader/tape/recorder.py` subscribes to WS `wss://ws-subscriptions-clob.polymarket.com/ws/market`, writes `raw_ws.jsonl` + `events.jsonl`
2. `polytool simtrader run` → `tools/cli/simtrader.py` → `packages/polymarket/simtrader/strategy/facade.py` → `StrategyRunner`
3. `StrategyRunner` processes events: `L2Book.apply()` → `Strategy.on_event()` → `SimBroker.step()` → `Strategy.on_fill()`
4. `PortfolioLedger.process()` computes PnL, fees, equity curve
5. Artifacts written to `artifacts/simtrader/runs/<run_id>/`: `orders.jsonl`, `fills.jsonl`, `ledger.jsonl`, `equity_curve.jsonl`, `summary.json`, `decisions.jsonl`, `run_manifest.json`, `meta.json`

**SimTrader Shadow Flow (live, no pre-recorded tape):**
1. `polytool simtrader shadow` → `packages/polymarket/simtrader/shadow/runner.py`
2. WS events processed inline (same normalization as `TapeRecorder`)
3. Optionally writes `raw_ws.jsonl` + `events.jsonl` concurrently
4. Calls same `Strategy` / `SimBroker` / `PortfolioLedger` chain as replay
5. Writes identical artifact set with additional `mode="shadow"` and `run_metrics` in manifest

**Sweep / Batch Flow:**
1. CLI builds N scenario configs from presets → `packages/polymarket/simtrader/sweeps/runner.py`
2. Each scenario calls `facade.run_strategy()` (same path as single run)
3. Results aggregated into `sweep_summary.json` + leaderboard
4. Batch runner (`packages/polymarket/simtrader/batch/runner.py`) iterates over M markets, runs sweep per market

**RAG Flow:**
1. `polytool rag-index` → `packages/polymarket/rag/index.py` chunks + embeds docs into Chroma
2. `polytool llm-bundle` → `tools/cli/llm_bundle.py` assembles dossier + RAG excerpts into an LLM evidence bundle
3. `polytool rag-run` re-executes `rag_queries.json` from a prior bundle and writes results back

**State Management:**
- Simulation state (L2Book prices, broker orders, open positions) is in-process Python objects; not persisted between runs
- Analysis artifacts are write-once directories on local filesystem
- ClickHouse is used as a read-through cache for market resolution data
- SimTrader Studio persists workspace state in browser `localStorage` (key: `simtrader_studio_state`, schema v1)

## Key Abstractions

**`Strategy` (base class):**
- Purpose: Interface that all trading strategies implement
- Examples: `packages/polymarket/simtrader/strategies/binary_complement_arb.py`, `packages/polymarket/simtrader/strategies/copy_wallet_replay.py`
- Pattern: Lifecycle hooks — `on_start()`, `on_event() -> list[OrderIntent]`, `on_fill()`, `on_finish()`; duck-typed extension via `.opportunities`, `.rejection_counts`, `.modeled_arb_summary`

**`OrderIntent` (dataclass):**
- Purpose: Instruction from a Strategy to the StrategyRunner for submit/cancel actions
- Examples: Returned from `Strategy.on_event()`; consumed by `StrategyRunner._execute_intent()`
- Pattern: Immutable command object; `action="submit"` or `action="cancel"` with optional `reason`/`meta` for audit log

**`SimBroker`:**
- Purpose: Simulated order lifecycle — PENDING → ACTIVE → PARTIAL/FULL/CANCELLED
- Location: `packages/polymarket/simtrader/broker/sim_broker.py`
- Pattern: Deterministic step function; activate → fill → cancel within each tape event; "no perfect cancels" guarantee

**`L2Book`:**
- Purpose: Level-2 order book driven by normalized tape events
- Location: `packages/polymarket/simtrader/orderbook/l2book.py`
- Pattern: Initialized by `book` snapshot events; updated by `price_change` deltas; handles both legacy single-asset and modern batched `price_changes[]` schema

**`ResolutionProvider` (Protocol):**
- Purpose: Abstract interface for market outcome resolution
- Location: `packages/polymarket/resolution.py`
- Pattern: Protocol class; `CachedResolutionProvider` implements a 4-stage cascade: ClickHouse → OnChainCTF → Subgraph → Gamma

**`PortfolioLedger`:**
- Purpose: FIFO cost-basis PnL, fee calculation, equity curve generation
- Location: `packages/polymarket/simtrader/portfolio/ledger.py`
- Pattern: Processes broker `order_events` + BBO `timeline` in one pass; always emits at least `initial` + `final` snapshots

**`StudioSessionManager`:**
- Purpose: Tracks concurrent SimTrader CLI processes launched from Studio UI
- Location: `packages/polymarket/simtrader/studio_sessions.py`
- Pattern: Launches `polytool simtrader <cmd>` as a subprocess; streams stdout to SSE; parses output lines for artifact paths and PnL metrics

## Entry Points

**Primary CLI:**
- Location: `polytool/__main__.py`
- Triggers: `python -m polytool <command>` or installed `polytool` script (via `pyproject.toml` entry point)
- Responsibilities: Dispatch to `tools/cli/*.py` handlers; provide top-level help and version

**SimTrader Studio (HTTP):**
- Location: `packages/polymarket/simtrader/studio/app.py` (FastAPI factory `create_app()`)
- Triggers: `polytool simtrader studio` or Docker via `infra/studio_docker.sh`
- Responsibilities: Serve static UI; expose browse/artifact APIs; manage Studio sessions via SSE

**MCP Server:**
- Location: `tools/cli/mcp_server.py`
- Triggers: `polytool mcp` (or Claude Desktop config)
- Responsibilities: Expose PolyTool tools over the MCP protocol using `FastMCP` from the `mcp` SDK

**Services API:**
- Location: `services/api/main.py`
- Triggers: Docker Compose (`docker compose up`)
- Responsibilities: Lightweight REST API for external orchestration (not yet fully wired)

## Error Handling

**Strategy:** Return empty `list[OrderIntent]` on any unrecoverable signal; `StrategyRunner` logs warnings and continues
**L2Book:** `strict=True` raises `L2BookError`; `strict=False` logs and skips — controlled per-run
**Resolution cascade:** Each provider returns `None` on failure; cascade falls through to next; final fallback is `None` with logged reason
**CLI handlers:** All `main(argv) -> int` functions return non-zero exit codes on failure; errors printed to `stderr`
**Optional deps:** Import-time `ImportError` is caught by CLI dispatcher; user sees actionable install message

## Cross-Cutting Concerns

**Logging:** `logging.getLogger(__name__)` used throughout; level controlled by caller; no global configuration imposed by library code
**Validation:** Input validation at CLI layer (argparse); domain-level validation via dataclass fields and explicit `ValueError` raises
**Authentication:** No auth in the main CLI; services API has no auth (local-only per CLAUDE.md); MCP uses stdio transport (no network auth needed)
**Artifact IDs:** Timestamped IDs generated by `packages/polymarket/simtrader/artifact_ids.py`; all run/sweep/batch dirs are `<timestamp>_<hash>` format for deterministic sorting

---

*Architecture analysis: 2026-03-05*
