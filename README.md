# PolyTool

**A local-first Polymarket research, simulation, and execution toolchain.**

PolyTool is a Python-based operator environment for discovering, validating, and
deploying prediction-market trading strategies on Polymarket. It combines a
research intelligence pipeline, a full-featured replay/simulation engine
(SimTrader), a crypto pair bot, and a gated live-execution layer.

**What PolyTool is NOT:**
- Not a hosted service. Everything runs on your machine.
- Not a signal provider. You generate and validate your own signals.
- Not live-ready without passing validation gates. Gate 2 is currently FAILED (see below).
- Not a complete automated trading platform. Live deployment requires passing all gates, operator review, and explicit capital authorization.

---

## What Is Shipped Today

| Component | Status | Notes |
|-----------|--------|-------|
| Research pipeline (Track B) | Shipped | Wallet scanning, alpha distillation, hypothesis registry, RAG, dossier/bundle exports |
| SimTrader (Track A) | Shipped, gated | Tape recording, replay, shadow mode, sweeps, batch, strategies, Studio browser UI |
| Market selection engine | Shipped | Seven-factor scorer, `market-scan` CLI |
| Crypto pair bot (Track 2 / Phase 1A) | Shipped, standalone | Scanning, paper runs, backtesting, reporting, market watching; not yet live-deployed |
| Research Intelligence System (RIS) | Shipped | Evaluation, ingestion, prechecking, claims extraction, scheduling, reporting, health |
| Data import | Shipped | DuckDB historical reads, Silver tape reconstruction, benchmark manifest |
| Execution layer | Shipped, dry-run by default | Kill switch, rate limiter, risk manager, live executor -- gated behind all gates passing |
| Infrastructure | Shipped | ClickHouse, Grafana dashboards, Docker Compose stack |
| Discord alerting | Shipped (optional) | Set DISCORD_WEBHOOK_URL in .env |
| n8n RIS pilot | Shipped (opt-in) | `--profile ris-n8n`; scoped to RIS ingestion only (ADR 0013) |

### Validation Gate Status

| Gate | Status | Detail |
|------|--------|--------|
| Gate 1 (Replay) | PASSED | |
| Gate 2 (Sweep) | **FAILED** | 7/50 positive tapes (14%); threshold is 70% |
| Gate 3 (Shadow) | **BLOCKED** | Gate 2 must pass first |
| Gate 4 (Dry-Run Live) | PASSED | |

**For the live gate status:** `python tools/gates/gate_status.py`

Gate 2 failure is a strategy profitability issue on low-frequency politics/sports tapes.
Crypto-only tapes (10) scored 7/10 positive; the full corpus of 50 did not pass.
Path-forward options are documented in `docs/dev_logs/2026-03-29_crypto_watch_and_capture.md`.

### Experimental / Gated (do not use for live capital)

- **Live execution** (`simtrader live`, `crypto-pair-run --live`): Requires Gate 2 + Gate 3 + Stage 0 paper-live completion. Gate 2 currently FAILED.
- **Stage 0 / Stage 1 live capital**: Blocked behind all gates passing plus operator authorization.
- **Crypto pair bot live deployment**: Blocked (no active BTC/ETH/SOL 5m/15m markets as of 2026-03-29, pending new market availability).

---

## Prerequisites

- **Python 3.10+**
- **Docker Desktop** (for ClickHouse and Grafana)
- **Git**

```bash
python --version      # Must be 3.10 or higher
docker --version
docker compose version
git --version
```

---

## Installation

```bash
# Clone the repo
git clone https://github.com/Amanpat/PolyTool.git
cd PolyTool

# Create and activate a virtual environment
python -m venv .venv

# Windows:
.venv\Scripts\activate
# Mac/Linux:
source .venv/bin/activate

# Install everything (recommended for full feature access)
pip install -e ".[all]"

# Or install core + tests only
pip install -e ".[dev]"
```

### Optional dependency groups

| Group | Contents | Install command |
|-------|----------|----------------|
| `rag` | RAG index (sentence-transformers, chromadb) | `pip install -e ".[rag]"` |
| `mcp` | MCP server for Claude Desktop | `pip install -e ".[mcp]"` |
| `simtrader` | WebSocket tape recording | `pip install -e ".[simtrader]"` |
| `studio` | SimTrader Studio browser UI (FastAPI) | `pip install -e ".[studio]"` |
| `dev` | Pytest + coverage | `pip install -e ".[dev]"` |
| `historical` | DuckDB historical reads | `pip install -e ".[historical]"` |
| `historical-import` | PyArrow for Parquet import | `pip install -e ".[historical-import]"` |
| `live` | py-clob-client for live order placement | `pip install -e ".[live]"` |
| `ris` | APScheduler for RIS background jobs | `pip install -e ".[ris]"` |
| `all` | Everything above | `pip install -e ".[all]"` |

Verify the install:

```bash
python -m polytool --help
```

---

## Configuration

### 1. Set up environment variables

```bash
# Windows:
copy .env.example .env
# Mac/Linux:
cp .env.example .env
```

Edit `.env`. At minimum, set `CLICKHOUSE_PASSWORD` before starting Docker:

```
CLICKHOUSE_PASSWORD=your_password_here
```

Never commit `.env`. It is gitignored.

### 2. Start infrastructure services

```bash
docker compose up -d
docker compose ps   # All services should show "Up" or "running"
```

Default services started:
- **ClickHouse** on port 8123 (analytics database)
- **Grafana** on port 3000 (dashboards -- login: admin / admin)
- **API** on port 8000 (internal service; health: http://localhost:8000/health)
- **RIS scheduler** (background ingestion, APScheduler-based)

### 3. Optional Docker Compose profiles

| Profile | Command | Starts |
|---------|---------|--------|
| Default | `docker compose up -d` | clickhouse, grafana, api, ris-scheduler |
| Pair bot | `docker compose --profile pair-bot up -d` | + pair-bot-paper, pair-bot-live |
| RIS n8n pilot | `docker compose --profile ris-n8n up -d` | + n8n (scoped RIS ingestion only) |
| CLI only | `docker compose --profile cli up -d` | clickhouse only |

Note: `pair-bot-live` is blocked for live capital deployment until gates pass.

### 4. Bootstrap private directories

```bash
# Windows:
powershell -ExecutionPolicy Bypass -File tools\bootstrap_kb.ps1
# Mac/Linux:
bash tools/bootstrap_kb.sh
```

Creates `kb/` and `artifacts/` directories (both gitignored; data stays local).

### 5. Run tests

```bash
python -m pytest -q --tb=short
# Expected: 3695 passed (as of 2026-04-07), 0 failures.
```

---

## Quick Workflows

### Research loop

```bash
# Batch wallet scan
python -m polytool wallet-scan --input wallets.txt --profile lite

# Distill edge candidates (no LLM)
python -m polytool alpha-distill \
  --wallet-scan-run artifacts/research/wallet_scan/YYYY-MM-DD/<run_id>

# Register a hypothesis
python -m polytool hypothesis-register \
  --candidate-file artifacts/research/wallet_scan/YYYY-MM-DD/<run_id>/alpha_candidates.json \
  --rank 1 \
  --registry artifacts/research/hypothesis_registry/registry.jsonl
```

### Single user examination

```bash
python -m polytool scan --user "@TraderHandle"
python -m polytool llm-bundle --user "@TraderHandle"
python -m polytool llm-save --user "@TraderHandle"
```

### RAG (local knowledge base)

```bash
# Rebuild index after any scan or ingest
python -m polytool rag-refresh

# Query the index
python -m polytool rag-query --question "crypto pair momentum patterns" --hybrid --rerank
```

### Market scanning

```bash
python -m polytool market-scan --top 20
```

### SimTrader development loop

```bash
# Shadow mode (live market, simulated fills)
python -m polytool simtrader shadow --market <slug> --strategy market_maker_v1 --duration 300

# Quick replay
python -m polytool simtrader quickrun --market <slug> --strategy market_maker_v1

# Open the Studio browser UI
python -m polytool simtrader studio --open
```

### RIS pre-build precheck (run before any new feature or strategy work)

```bash
python -m polytool research-precheck run --idea "description of planned work" --no-ledger
# GO = proceed, CAUTION = note concerns, STOP = do not proceed without operator discussion
```

### Crypto pair bot (standalone -- does not require gates to pass)

```bash
# Check if eligible BTC/ETH/SOL markets exist
python -m polytool crypto-pair-watch --one-shot

# Scan for pair opportunities
python -m polytool crypto-pair-scan

# Paper run
python -m polytool crypto-pair-run

# Backtest and report
python -m polytool crypto-pair-backtest
python -m polytool crypto-pair-report --run-dir artifacts/tapes/crypto/paper_runs/<run_id>
```

---

## Complete CLI Command Reference

All commands: `python -m polytool <command> [options]`

### Research Loop (Track B)

| Command | Description |
|---------|-------------|
| `wallet-scan` | Batch-scan many wallets/handles -> ranked leaderboard |
| `alpha-distill` | Distill wallet-scan data -> ranked edge candidates (no LLM) |
| `hypothesis-register` | Register a candidate in the offline hypothesis registry |
| `hypothesis-status` | Update lifecycle status for a registered hypothesis |
| `hypothesis-diff` | Compare two saved hypothesis.json artifacts |
| `hypothesis-summary` | Extract a deterministic summary from hypothesis.json |
| `experiment-init` | Create an experiment.json skeleton for a hypothesis |
| `experiment-run` | Create a generated experiment attempt for a hypothesis |
| `hypothesis-validate` | Validate a hypothesis JSON file against schema_v1 |

### Analysis and Evidence

| Command | Description |
|---------|-------------|
| `scan` | Run a one-shot scan via the PolyTool API |
| `batch-run` | Batch-run scans and aggregate a hypothesis leaderboard |
| `audit-coverage` | Offline accuracy + trust sanity check from scan artifacts |
| `export-dossier` | Export an LLM Research Packet dossier + memo |
| `export-clickhouse` | Export ClickHouse datasets for a user |

### RAG and Knowledge

| Command | Description |
|---------|-------------|
| `rag-refresh` | Rebuild the local RAG index (one-command; use this after any scan) |
| `rag-index` | Build or rebuild the RAG index (full control) |
| `rag-query` | Query the local RAG index |
| `rag-run` | Re-execute bundle rag_queries.json and write results back |
| `rag-eval` | Evaluate retrieval quality |
| `cache-source` | Cache a trusted web source for RAG indexing |
| `llm-bundle` | Build an LLM evidence bundle from dossier + RAG excerpts |
| `llm-save` | Save an LLM report run into the private KB |

### Research Intelligence (RIS)

| Command | Description |
|---------|-------------|
| `research-eval` | Evaluate a document through the RIS quality gate |
| `research-precheck` | Pre-development check: GO / CAUTION / STOP recommendation |
| `research-ingest` | Ingest a document into the RIS knowledge store |
| `research-seed` | Seed the RIS knowledge store from a manifest |
| `research-benchmark` | Compare extractor outputs on a fixture set |
| `research-calibration` | Inspect precheck calibration health over the ledger |
| `research-extract-claims` | Extract structured claims from ingested documents (no LLM) |
| `research-acquire` | Acquire a source from URL and ingest into knowledge store |
| `research-report` | Save, list, search reports and generate weekly digests |
| `research-scheduler` | Manage the RIS background ingestion scheduler |
| `research-stats` | Operator metrics snapshot and local-first export for RIS pipeline |
| `research-health` | Print RIS health status summary from stored run data |
| `research-dossier-extract` | Parse dossier artifacts -> KnowledgeStore |
| `research-register-hypothesis` | Register a research hypothesis candidate in the JSONL registry |
| `research-record-outcome` | Record a validation outcome for KnowledgeStore claims |

### Crypto Pair Bot (Track 2 / Phase 1A -- standalone)

| Command | Description |
|---------|-------------|
| `crypto-pair-scan` | Dry-run: discover BTC/ETH/SOL 5m/15m pair markets, compute edge |
| `crypto-pair-run` | Paper by default; live scaffold behind --live with explicit safety gates |
| `crypto-pair-backtest` | Replay historical/synthetic pair observations, emit eval artifacts |
| `crypto-pair-report` | Summarize one completed paper run into rubric-backed markdown + JSON |
| `crypto-pair-watch` | Check whether eligible BTC/ETH/SOL 5m/15m markets exist; poll with --watch |
| `crypto-pair-await-soak` | Wait for eligible markets, then launch the standard Coinbase paper smoke soak |
| `crypto-pair-seed-demo-events` | Seed dev-only synthetic Track 2 rows into ClickHouse for dashboard checks |

Note: Track 2 is standalone and does NOT wait for Gate 2 or Gate 3 to pass.
Live deployment is currently blocked: no active BTC/ETH/SOL 5m/15m markets on
Polymarket as of 2026-03-29. Use `crypto-pair-watch --one-shot` to check current availability.

### SimTrader / Execution (Track A, gated)

| Command | Description |
|---------|-------------|
| `simtrader` | Record/replay/shadow/live trading. Run `simtrader --help` for subcommands |
| `market-scan` | Rank active Polymarket markets by reward/spread/fill quality |
| `scan-gate2-candidates` | Rank markets by Gate 2 binary_complement_arb executability |
| `prepare-gate2` | Scan -> record -> check eligibility for Gate 2 (orchestrator) |
| `watch-arb-candidates` | Watch a market list and auto-record on near-edge dislocation |
| `tape-manifest` | Scan tape corpus, check eligibility, emit acquisition manifest |
| `gate2-preflight` | Check whether Gate 2 sweep is ready and why it may be blocked |
| `make-session-pack` | Create exact watchlist + watcher-compatible session plan for a capture session |

SimTrader subcommands (via `python -m polytool simtrader <subcommand>`):

| Subcommand | Description |
|------------|-------------|
| `quickrun` | Interactive replay with auto market pick |
| `shadow` | Live shadow mode (live market, simulated fills) |
| `run` | Replay a tape with a strategy |
| `sweep` | Parameter sweep over a tape |
| `batch` | Batch replay over multiple tapes |
| `record` | Record a live tape from WebSocket feed |
| `tape-info` | Print tape metadata |
| `replay` | Replay a tape (alias) |
| `report` | Print replay run report |
| `browse` | List recorded tapes |
| `clean` | Remove old run artifacts |
| `diff` | Diff two replay run manifests |
| `live` | Live trading (gated; requires all gates + operator auth) |
| `kill` | Trigger the kill switch to halt all live activity |
| `studio` | Start the SimTrader Studio browser UI |

### Data Import

| Command | Description |
|---------|-------------|
| `import-historical` | Validate and document local historical dataset layout |
| `smoke-historical` | DuckDB smoke -- validate pmxt/Jon raw files directly (no ClickHouse) |
| `fetch-price-2min` | Fetch 2-min price history from CLOB API -> polytool.price_2min (ClickHouse) |
| `reconstruct-silver` | Reconstruct a Silver tape (pmxt anchor + Jon fills + price_2min midpoint guide) |
| `batch-reconstruct-silver` | Batch-reconstruct Silver tapes for multiple tokens over one window |
| `benchmark-manifest` | Build or validate the frozen benchmark_v1 tape manifest contract |
| `new-market-capture` | Discover newly listed markets (<48h) and plan Gold tape capture |
| `capture-new-market-tapes` | Record Gold tapes for benchmark_v1 new_market targets (batch) |
| `close-benchmark-v1` | End-to-end benchmark closure: preflight + Silver + new-market + manifest |
| `summarize-gap-fill` | Read-only diagnostic summary for gap_fill_run.json artifacts |

### Integrations and Utilities

| Command | Description |
|---------|-------------|
| `mcp` | Start the MCP server for Claude Desktop integration (requires `[mcp]` extra) |
| `examine` | Legacy examination orchestrator (scan -> bundle -> prompt) |
| `agent-run` | Run an agent task (internal) |

---

## Operator Surfaces

| Surface | Access | Notes |
|---------|--------|-------|
| CLI | `python -m polytool <command>` | Primary interface |
| Grafana | http://localhost:3000 | Analytics dashboards; requires data ingest first |
| SimTrader Studio | `python -m polytool simtrader studio --open` | Browser UI for sessions, tapes, reports, OnDemand replay |
| MCP | `python -m polytool mcp` | Claude Desktop integration; optional |
| n8n (opt-in) | `docker compose --profile ris-n8n up -d` | Scoped RIS ingestion only; see ADR 0013 |

---

## Project Structure

```
polytool/               Package root and CLI entry (__main__.py)
packages/polymarket/    Core analytics, SimTrader, execution, strategies, RAG
packages/research/      Research Intelligence System (RIS)
tools/cli/              CLI command implementations
tools/gates/            Gate scripts (gate_status.py, run_recovery_corpus_sweep.py)
services/api/           FastAPI service
infra/                  ClickHouse schemas, Grafana provisioning, n8n workflows
docs/                   All documentation
tests/                  Test suite (3695 passing as of 2026-04-07)
config/                 Benchmark manifests and strategy config (benchmark_v1 finalized)
artifacts/              Private local data (gitignored)
kb/                     Private knowledge base (gitignored)
```

Key artifact paths (all gitignored):
- `artifacts/tapes/gold/` -- live tape recorder output (Gold tier)
- `artifacts/tapes/silver/` -- reconstructed Silver tapes
- `artifacts/tapes/shadow/` -- shadow run tapes
- `artifacts/tapes/crypto/` -- crypto pair tapes
- `artifacts/gates/` -- gate sweep results and manifests
- `artifacts/market_selection/` -- market selection artifacts
- `artifacts/debug/` -- probe outputs and debug files

---

## Deeper Documentation

| Document | What it covers |
|----------|---------------|
| [`docs/OPERATOR_QUICKSTART.md`](docs/OPERATOR_QUICKSTART.md) | End-to-end operator guide: research loop, RAG, SimTrader, Grafana, gates |
| [`docs/CURRENT_STATE.md`](docs/CURRENT_STATE.md) | Detailed current state: what is shipped, gate status, blockers |
| [`docs/README_SIMTRADER.md`](docs/README_SIMTRADER.md) | SimTrader operator guide: quickrun, shadow, sweep, Studio, strategies |
| [`docs/INDEX.md`](docs/INDEX.md) | Full documentation index |
| [`docs/PLAN_OF_RECORD.md`](docs/PLAN_OF_RECORD.md) | Mission, constraints, data gaps, roadmap framing |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | Components and data flow |
| [`docs/STRATEGY_PLAYBOOK.md`](docs/STRATEGY_PLAYBOOK.md) | Strategy descriptions and deployment criteria |

---

## Security

- Never commit `.env`, `kb/`, or `artifacts/`. All three are gitignored.
- Use a dedicated trading wallet. Never reuse a personal wallet.
- Live execution kill switch: `python -m polytool simtrader kill`
- No live capital before Gate 2 passes, Gate 3 passes, and Stage 0 (paper-live) completes.
- CLICKHOUSE_PASSWORD must be set via environment variable. Do not hardcode it.

---

## License

MIT. See `pyproject.toml` for project metadata.
