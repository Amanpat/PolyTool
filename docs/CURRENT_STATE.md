# Current State / What We Built

This repo is a local-first toolchain for Polymarket analysis: data ingestion,
ClickHouse analytics, Grafana dashboards, private evidence exports, and a local
RAG workflow that never calls external LLM APIs.

Master Roadmap v4.2 (`docs/reference/POLYTOOL_MASTER_ROADMAP_v4.2.md`) is the
governing roadmap document as of 2026-03-16 and supersedes v4.1. This file
records implemented repo truth; do not infer v4.2 phase completion from strategic
roadmap language alone.

## Roadmap v4 Items Not Yet Implemented

- The v4 control plane is not shipped: no n8n orchestration layer, no broad
  FastAPI wrapper surface, no Discord approval system, and no automated
  feedback loop.
- The v4 research expansion is not shipped: `candidate-scan`, research
  scraper, news/signals ingest, and signal-linked market workflows are not
  current repo features.
- The v4 UI rebuild is not shipped: existing Studio/Grafana surfaces remain
  the current operator UI, not the Phase 7 Next.js rebuild.
- The v4 live-bot path remains incomplete: Gate 2 is not passed, Gate 3 is
  blocked, and Stage 0/Stage 1 live promotion are not complete.

## Status as of 2026-03-16

Track A / SimTrader plumbing is implemented. The repo's current execution
status is:

- Gate 1: PASSED
- Gate 2: not passed yet; tooling is implemented and working
- Gate 3: blocked behind Gate 2
- Gate 4: PASSED
- **Primary Gate 2 path (v4.2)**: DuckDB reads pmxt and Jon-Becker Parquet
  files directly — no ClickHouse import step required. Silver tape reconstruction
  from those files + 2-min price history → Gate 2 scenario sweep. ClickHouse
  bulk import (SPEC-0018) is off the critical path; see
  `docs/runbooks/BULK_HISTORICAL_IMPORT_V0.md` (now legacy/optional).
- **pmxt raw files**: exist locally. Full ClickHouse import (78,264,878 rows,
  2026-03-15) is complete but is legacy under v4.2. DuckDB reads the Parquet
  files directly. Artifact: `artifacts/imports/pmxt_full_batch1.json`
- **Jon-Becker raw files**: exist locally. Sample ClickHouse import confirmed
  (1,000 rows, 2026-03-16); full ClickHouse import is not required under v4.2.
  DuckDB reads the Parquet files directly.
  Artifacts: `artifacts/imports/jon_dry_run.json`, `artifacts/imports/jon_sample_run.json`
- **price_2min** (canonical live-updating ClickHouse series): table created
  (`infra/clickhouse/initdb/24_price_2min.sql`), `fetch-price-2min` CLI
  shipped. Naming conflict resolved: `price_2min` = live CH series (this path);
  `price_history_2min` = legacy local-file bulk import (SPEC-0018, off critical
  path). See dev log `docs/dev_logs/2026-03-16_price_2min_clickhouse_v0.md`.
  CLI: `python -m polytool fetch-price-2min --token-id <ID> [--dry-run]`.
- **Silver tape reconstruction**: not yet started. Blocked on DuckDB setup and
  integration, not on further ClickHouse bulk import work.
- Gate 2 is not closed. Current next step: DuckDB setup and integration →
  price_history_2min fetch → Silver tape reconstruction → Gate 2 scenario sweep
- Opportunity Radar: deferred until after the first clean Gate 2 -> Gate 3
  progression

## Historical checkpoint: 2026-03-05 Track A code complete

Track A code is shipped and tested. Sprint-end validation was 1188 passing
tests with no reported regressions, but Stage 1 live capital remains blocked
until the remaining gates are closed and Stage 0 paper-live completes cleanly.

- `packages/polymarket/simtrader/execution/wallet.py`: new wallet helper that reads `PK`, builds a real `ClobClient`, and supports one-time credential derivation.
- `packages/polymarket/simtrader/execution/live_executor.py`: upgraded executor that routes create/cancel calls to an injected real client when `dry_run=False`.
- `packages/polymarket/simtrader/execution/risk_manager.py`: patched risk layer with `inventory_skew_limit_usd`, fill-price tracking, and net inventory notional checks.
- `packages/polymarket/simtrader/strategies/market_maker_v0.py`: upgraded strategy with Avellaneda-Stoikov quotes, microprice inputs, volatility estimation, and bounded spread guards.
- `packages/polymarket/market_selection/`: new market selection package with scorer, filters, Gamma API client, and `python -m polytool market-scan`.
- `tools/gates/close_replay_gate.py`: Gate 1 replay determinism closure script.
- `tools/gates/close_sweep_gate.py`: Gate 2 scenario sweep closure script.
- `tools/gates/run_dry_run_gate.py`: Gate 4 dry-run live closure script.
- `tools/gates/gate_status.py`: gate status reporter that exits 0 only when all four gate artifacts pass.
- `tools/gates/shadow_gate_checklist.md`: Gate 3 manual operator checklist and artifact contract.
- `tools/cli/simtrader.py`: live CLI upgrade with `--live`, gate checks, wallet loading, USD risk flags, and `simtrader kill`.
- `docs/runbooks/LIVE_DEPLOYMENT_STAGE1.md`: one-page operator runbook for Stage 1 live deployment.

## What exists today

- A local CLI (`polytool`) that drives ingestion and exports.
- A data pipeline that writes to ClickHouse and visualizes in Grafana.
- Private dossier exports with resolution outcomes and PnL enrichment.
- Local RAG indexing + retrieval over private content (`kb/` + `artifacts/`).
- `rag-refresh` command (alias for `rag-index --rebuild`): one-command path to rebuild the full index.
- Evidence bundle generation with standardized prompt templates.
- LLM report retention with automatic LLM_notes for RAG surfacing.
- MCP server integration for Claude Desktop.
- Batch wallet scan with deterministic leaderboard (`wallet-scan`).
- Cross-user segment edge distillation into ranked candidates (`alpha-distill`).
- Offline hypothesis registry + experiment skeleton (`hypothesis-register`, `hypothesis-status`, `experiment-init`, `experiment-run`).
- Offline hypothesis registry + experiment skeleton plus Hypothesis Validation Loop v0 (`hypothesis-register`, `hypothesis-status`, `experiment-init`, `experiment-run`, `hypothesis-validate`, `hypothesis-diff`, `hypothesis-summary`).
- Track A gate harness under `tools/gates/`, with Gate 1 and Gate 4 passed,
  Gate 2 tooling shipped, and Gate 3 blocked behind Gate 2.
- Bounded Gate 2 capture tooling: `scan-gate2-candidates`, `prepare-gate2`,
  presweep eligibility checks, `watch-arb-candidates`, and `--watchlist-file`
  ingest.
- Gated execution surface via `simtrader live` (dry-run default; `--live` exists but is still gate-blocked).
- Grouped CLI help: `python -m polytool --help` now presents commands in 5 categories (Research Loop, Analysis & Evidence, RAG & Knowledge, SimTrader / Execution, Integrations & Utilities).
- SimTrader Studio Dashboard tab includes Grafana deep-link cards (User Trades, PnL, Strategy Detectors, Arb Feasibility, and others); requires `docker compose up -d`.

---

## Validation Pipeline (Canonical)

The canonical operator validation pipeline is:

1. Replay Validation -> Gate 1
2. Sweep Validation -> Gate 2
3. Shadow Validation -> Gate 3
4. Dry Run -> Gate 4
5. Stage 0 -> 72 hour paper-live run
6. Stage 1 -> live trading with capital

Historical note: older planning language may refer to a "30-day shadow
validation." That wording is obsolete. The current process is Gate 3 shadow
validation, then Gate 4 dry-run live, then a separate 72 hour Stage 0
paper-live run before Stage 1 capital is allowed.

---

## Recently completed (Track B foundation + registry + validation loop)

Status (2026-03-12): Track B foundation, hypothesis registry v0, and
Hypothesis Validation Loop v0 are complete. This does not mean Master Roadmap
v4.1 Phase 2 is complete.

### Wallet-Scan v0

A research-only batch scan workflow.

- **CLI**: `python -m polytool wallet-scan --input wallets.txt [--profile lite|full]`
- **Input**: plain-text file with one Polymarket handle (`@name`) or wallet address (`0x...`) per line
- **Output**: `artifacts/research/wallet_scan/<YYYY-MM-DD>/<run_id>/`
  - `wallet_scan_manifest.json` - run metadata
  - `per_user_results.jsonl` - per-entry scan outcome, PnL, CLV coverage, outcome counts
  - `leaderboard.json` - deterministic ranking by net PnL (desc), tiebreak by slug (asc)
  - `leaderboard.md` - human-readable top-20 table
- Failures are isolated per entry; batch continues on error by default.
- Spec: [docs/specs/SPEC-wallet-scan-v0.md](specs/SPEC-wallet-scan-v0.md)
- Feature doc: [docs/features/wallet-scan-v0.md](features/wallet-scan-v0.md)

### Alpha-Distill v0

Cross-user segment edge distillation into ranked hypothesis candidates. No LLM,
no black-box scores.

- **CLI**: `python -m polytool alpha-distill --wallet-scan-run <path> [--min-sample 30] [--fee-adj 0.02]`
- **Input**: a `wallet-scan` run root + each user's `segment_analysis.json`
- **Output**: `alpha_candidates.json` - ranked candidates with persistence metrics, friction flags, `next_test`, `stop_condition`
- Ranking prioritizes **multi-user persistence** (~1000x weight) over count or raw edge.
- Every candidate includes a `stop_condition` to guard against over-fitting.
- Spec: [docs/specs/SPEC-alpha-distill-v0.md](specs/SPEC-alpha-distill-v0.md)
- Feature doc: [docs/features/alpha-distill-v0.md](features/alpha-distill-v0.md)

### RAG reliability improvements

- **Centralized default collection**: all CLI tools (`rag-index`, `rag-query`, `llm-bundle`, `rag-run`) default to `polytool_rag` via a shared `packages/polymarket/rag/defaults.py`; fixes legacy `polyttool_rag` double-t mismatches.
- **`rag-index` progress + file filters**: progress callbacks with file/chunk counters; binary/oversized file skip list; `--max-bytes`, `--progress-every-files`, `--progress-every-chunks` CLI flags; improved `--rebuild` on Windows.
- **`rag-run` CLI**: re-executes stored `rag_queries.json` queries against the current index without rebuilding the bundle; writes results back in place.
- **LLM bundle excerpt de-noising**: prior bundle artifacts (`rag_queries.json`, `bundle.md`, `prompt.txt`) are filtered from RAG results before selection to prevent circular evidence.
- **LLM bundle report stub**: `llm-bundle` now writes a blank `kb/users/<slug>/reports/<date>/<run_id>_report.md` with pre-formatted section headings; operator pastes the LLM's output there.
- **`rag_queries.json` execution status**: every entry carries `execution_status` (`executed`/`not_executed`/`error`) and `execution_reason`; no more silent empty-list behavior.

### Hypothesis Registry v0 + Experiment Skeleton

Offline-only lifecycle tracking for post-`alpha-distill` candidates.

- **CLI**: `python -m polytool hypothesis-register --candidate-file alpha_candidates.json --rank 1 --registry artifacts/research/hypothesis_registry/registry.jsonl`
- **CLI**: `python -m polytool hypothesis-status --id <hypothesis_id> --status testing --reason "manual review" --registry artifacts/research/hypothesis_registry/registry.jsonl`
- **CLI**: `python -m polytool experiment-init --id <hypothesis_id> --registry artifacts/research/hypothesis_registry/registry.jsonl --outdir artifacts/research/experiments/<hypothesis_id>/<experiment_id>`
- **CLI**: `python -m polytool experiment-run --id <hypothesis_id> --registry artifacts/research/hypothesis_registry/registry.jsonl --outdir artifacts/research/experiments/<hypothesis_id>`
- **Registry**: append-only JSONL with deterministic `hypothesis_id` and lifecycle statuses `proposed | testing | validated | rejected | parked`
- **Experiment artifact**: `experiment.json` skeleton with registry snapshot, candidate provenance, and planned execution placeholders
- Spec: [docs/specs/SPEC-hypothesis-registry-v0.md](specs/SPEC-hypothesis-registry-v0.md)
- Feature doc: [docs/features/FEATURE-hypothesis-registry-v0.md](features/FEATURE-hypothesis-registry-v0.md)

---

## Primary research loop (today)

```text
wallets.txt (handles + wallet addresses)
  -> python -m polytool wallet-scan --input wallets.txt
  -> artifacts/research/wallet_scan/<date>/<run_id>/
      leaderboard.json + per_user_results.jsonl

  -> python -m polytool alpha-distill --wallet-scan-run <path>
  -> alpha_candidates.json (ranked edge hypothesis candidates)

  -> python -m polytool hypothesis-register --candidate-file <path>/alpha_candidates.json --rank 1 --registry artifacts/research/hypothesis_registry/registry.jsonl
  -> registry.jsonl append + printed hypothesis_id

  -> python -m polytool experiment-run --id <hypothesis_id> --registry artifacts/research/hypothesis_registry/registry.jsonl --outdir artifacts/research/experiments/<hypothesis_id>
  -> exp-YYYYMMDDTHHMMSSZ/experiment.json skeleton for manual validation
     (use experiment-init for an explicit directory name)

  -> manual review / evidence gathering
     python -m polytool hypothesis-status --id <hypothesis_id> --status testing --reason "manual review"
     python -m polytool llm-bundle -> paste into LLM UI -> python -m polytool llm-save --hypothesis-path hypothesis.json
```

### Optional execution path (gated, Track A)

```text
  -> python -m polytool market-scan --top 5
     (rank active markets before any live-session candidate is chosen)

  -> python -m polytool simtrader run --tape <events.jsonl> --strategy market_maker_v0
     (replay: deterministic strategy evaluation on recorded tape)

  -> python -m polytool simtrader quickrun --sweep quick --strategy market_maker_v0
     (scenario sweeps: friction + latency stress)

  -> python -m polytool simtrader shadow --market <slug> --strategy market_maker_v0
     (shadow: live WS feed, simulated fills, no real orders)

  -> python -m polytool simtrader live --strategy market_maker_v0 --asset-id <TOKEN_ID>
     (dry-run live: default; prints WOULD PLACE lines, no submission)

  -> Stage 0 paper-live
     (72 hour zero-capital soak after all four gates pass)

  -> Stage 1 live capital
     (only after Stage 0 completes cleanly)
```

Validation order is fixed:
`replay -> scenario sweeps -> shadow -> dry-run live -> Stage 0 paper-live -> Stage 1 capital`.
No live capital is allowed before all four gates are complete and Stage 0 is clean.

---

## Known limitations (as of 2026-03-05)

- **Category coverage**: depends on market metadata backfill having run; newly ingested markets may show `"Unknown"`.
- **Liquidity snapshots**: CLV data is only available for markets that had a snapshot taken before resolution; coverage varies by run timing.
- **Multi-window persistence**: `alpha-distill` cross-user aggregation covers a single wallet-scan run; no time-series comparison across multiple scan dates yet.
- **Sequential execution**: `wallet-scan` scans identifiers one at a time (no parallelism).
- **Fee estimates only**: all fee adjustments are quadratic-curve estimates; actual per-trade fees may differ.
- **Track A promotion remains blocked**: Gate 2 still lacks an eligible tape,
  Gate 3 is blocked behind Gate 2, and Stage 0 cannot start until all four
  gates pass.

## Track A execution layer (optional, gated)

Track A code is complete as of 2026-03-05. Gate 2 plumbing is implemented and
working. Under v4.2, the Gate 2 path no longer requires ClickHouse bulk import.
DuckDB reads pmxt and Jon-Becker Parquet files directly from `/data/raw/`,
producing Silver-tier reconstructed tapes for the scenario sweep. Silver tapes
are sufficient for Gate 2; Gate 3 requires Gold tapes from live recording.
See `docs/reference/POLYTOOL_MASTER_ROADMAP_v4.2.md` (Database Architecture).

### Current operator focus (2026-03-16)

Gate 2 path reframed under v4.2 (DuckDB-first). Gate 1 and Gate 4 remain passed.

**Completed (ClickHouse import — now legacy under v4.2)**:
- `import-historical` subcommands (validate-layout, show-manifest, import) are
  shipped and operational (Packet 1 + Packet 2); these are off the critical
  path under v4.2.
- pmxt archive: full batch 1 (78,264,878 rows, 2026-03-15) imported to CH.
  Raw Parquet files exist locally and are the primary v4.2 source via DuckDB.
- Jon-Becker dataset: dry-run (68,646 files discovered, 2026-03-15) and sample
  (1,000 rows, 40,454 files, 2026-03-16) complete. Full ClickHouse import is
  not required under v4.2; DuckDB reads the Parquet files directly.

**Pending (v4.2 primary path)**:
- DuckDB setup and integration (next immediate step)
- price_2min population: run `fetch-price-2min` for target token IDs before Silver reconstruction
- Silver tape reconstruction (DuckDB-based; blocked on DuckDB setup)
- Gate 2 scenario sweep (blocked on Silver tapes existing)

**Not in scope for current work**:
- Opportunity Radar: deferred until after first clean Gate 2 → Gate 3 progression
- Live dislocation capture remains a fallback path only; no qualifying tapes
  produced from prior live watcher runs

### Current shipped surfaces

- `wallet.py` now exists under `packages/polymarket/simtrader/execution/` and enables real CLOB client injection through `LiveExecutor`.
- `market_maker_v0.py` now uses an Avellaneda-Stoikov quoting model with microprice, rolling variance, resolution guard, and spread/quote clamps.
- `packages/polymarket/market_selection/` now provides the market scoring, filters, and Gamma API client used by `python -m polytool market-scan`.
- `tools/gates/` now holds the replay, sweep, shadow, and dry-run gate harness;
  Gate 1 and Gate 4 are currently PASSED.
- `tools/cli/scan_gate2_candidates.py`, `tools/cli/prepare_gate2.py`, and
  `tools/cli/watch_arb_candidates.py` provide the current Gate 2 scouting,
  capture, and bounded watch loop.
- `tools/cli/simtrader.py` now exposes `simtrader live --live`, loads wallet credentials, enforces all gate artifacts, requires `CONFIRM`, and includes `simtrader kill`.

### Gate status (2026-03-16)

- Gate 1 (Replay Determinism): **PASSED** - artifact at
  `artifacts/gates/replay_gate/gate_passed.json`.
- Gate 2 (Scenario Sweep >=70%): **NOT PASSED**.
  - Tooling is implemented and working: `scan-gate2-candidates`,
    `prepare-gate2`, presweep eligibility checks, `watch-arb-candidates`, and
    `--watchlist-file` ingest.
  - Under v4.2: pmxt and Jon-Becker raw Parquet files exist locally; DuckDB
    reads them directly (no further ClickHouse import required).
  - price_history_2min not yet fetched. Silver tape reconstruction not yet
    started (blocked on DuckDB setup). No Silver-tier tape exists.
- Gate 3 (Shadow Mode): Blocked behind Gate 2.
- Gate 4 (Dry-Run Live): **PASSED** - artifact at
  `artifacts/gates/dry_run_gate/gate_passed.json`.

### Historical gate status snapshot (2026-03-06)

Archive note: this snapshot is retained for history only. Use the 2026-03-16
gate status block above for current operator guidance.

- Gate 1 (Replay Determinism): **PASSED** - artifact at `artifacts/gates/replay_gate/gate_passed.json`.
- Gate 2 (Scenario Sweep >=70%): In progress — tooling complete; needs a live tape with `executable_ticks > 0`.
  - `scan-gate2-candidates`: ranks live markets by Gate 2 executability.
  - `prepare-gate2`: scan -> record -> check eligibility orchestrator (30 tests, all passing).
  - `sweeps/eligibility.py`: pre-sweep fast-fail guard (29 tests, all passing).
- Gate 3 (Shadow Mode): Blocked — waiting on Gate 2 clean progression.
- Gate 4 (Dry-Run Live): **PASSED** - artifact at `artifacts/gates/dry_run_gate/gate_passed.json`.

### Safety defaults

- **Dry-run default**: `simtrader live` never submits orders unless `--live` is passed.
- **Kill switch checked always**: checked before every place/cancel action even in dry-run mode.
- **No market orders**: limit orders only.
- **USD risk caps**: order, position, daily-loss, and inventory skew limits are enforced by `RiskManager`.
- **Spec**: [docs/specs/SPEC-0011-live-execution-layer.md](specs/SPEC-0011-live-execution-layer.md)
- **Feature doc**: [docs/features/FEATURE-trackA-live-clob-wiring.md](features/FEATURE-trackA-live-clob-wiring.md)

## SimTrader (replay-first + shadow mode)

SimTrader is a realism-first simulated trader for Polymarket CLOB markets. It
records the Market Channel WS into deterministic tapes and supports both offline
replay and live simulated shadow runs.

What exists today:
- One-shot runner: `simtrader quickrun` (auto market pick/validate -> record -> run or sweep)
- Scenario sweeps (`--sweep quick` / `quick_small`) and batch leaderboard (`simtrader batch`)
- Shadow mode: `simtrader shadow` (live WS -> strategy -> BrokerSim fills; optional tape recording)
- Activeness probe: `--activeness-probe-seconds` / `--require-active` on `quickrun` measures live WS update rate before committing to a market
- Artifact management: `simtrader clean` (safe dry-run deletion of artifact folders) and `simtrader diff` (side-by-side comparison of two run directories, writes `diff_summary.json`)
- Local UI: `simtrader report` generates self-contained `report.html` for run/sweep/batch/shadow artifacts; `simtrader browse --open` opens newest results
- Explainability: `strategy_debug.rejection_counts`, sweep/batch aggregates, and audited JSONL artifacts

Start here:
- `docs/README_SIMTRADER.md`
- `docs/specs/SPEC-0010-simtrader-vision-and-roadmap.md`

---

## Pipeline (text)

```text
scan -> canonical workflow entrypoint:
  -> ClickHouse + Grafana refresh
  -> trust artifacts in artifacts/dossiers/.../coverage_reconciliation_report.* + run_manifest.json

Individual steps:
  export-dossier -> artifacts/dossiers/.../memo.md + dossier.json + manifest.json
  export-clickhouse -> kb/users/<slug>/exports/<YYYY-MM-DD>/
  llm-bundle -> kb/users/<slug>/llm_bundles/<YYYY-MM-DD>/<run_id>/bundle.md + prompt.txt
  llm-save -> kb/users/<slug>/llm_reports/ + kb/users/<slug>/notes/LLM_notes/
  rag-index -> kb/rag/*
  rag-query -> evidence snippets
  market-scan -> ranked active market candidates
  simtrader -> replay, sweeps, shadow, and gated live execution
  cache-source -> kb/sources/
  examine -> legacy orchestrator wrapper (non-canonical)
  mcp -> Claude Desktop integration
```

## CLI commands (plain language)

- `scan`: run a one-shot ingestion via the local API to pull user data into ClickHouse (with optional activity, positions, and PnL flags), and emit trust artifacts (`coverage_reconciliation_report.*`, `run_manifest.json`) per run.
- `examine`: legacy orchestrator (scan -> dossier -> bundle -> prompt) kept for compatibility and golden-case operations.
- `export-dossier`: build a private, point-in-time evidence package for one user (memo + JSON + manifest) under `artifacts/`. Now includes resolution outcomes and position lifecycle data.
- `export-clickhouse`: export recent ClickHouse datasets for one user into the private KB under `kb/users/<slug>/exports/<YYYY-MM-DD>/`.
- `rag-refresh`: one-command alias for `rag-index --rebuild`. Use this after any scan, wallet-scan, or llm-save to make new content immediately searchable.
- `rag-index`: build or rebuild the local RAG index over `kb/` + `artifacts/`. Outputs live in `kb/rag/`. Use `rag-refresh` for the simple path; `rag-index` for incremental or advanced options.
- `rag-query`: retrieve relevant evidence snippets from the local index with optional scoping by user, doc type, or date.
- `rag-eval`: run retrieval quality checks and write reports to `kb/rag/eval/reports/<timestamp>/`.
- `llm-bundle`: assemble a short evidence bundle from dossier data and curated RAG excerpts into `bundle.md` for offline reporting.
- `llm-save`: store LLM report runs (report + manifest) into `llm_reports/` and write a summary note to `notes/LLM_notes/` for RAG surfacing.
- `market-scan`: score and filter active markets for operator review before any Track A live candidate is chosen.
- `scan-gate2-candidates`: rank live markets (or local tapes) by Gate 2 binary_complement_arb executability (depth + complement edge).
- `prepare-gate2`: Gate 2 prep orchestrator — scan candidates, record tapes, check eligibility, print verdict in one command.
- `watch-arb-candidates`: run a bounded live dislocation watch and auto-record
  near-edge tapes from `--markets` or `--watchlist-file`.
- `simtrader`: replay, sweep, shadow, dry-run live, and gated `--live` execution surfaces.
- `cache-source`: cache trusted web sources for RAG indexing (allowlist enforced).
- `mcp`: start the MCP server for Claude Desktop integration.

## User identity routing

User identity is resolved canonically via `polytool/user_context.py`:

- **Handle-first (strict)**: `--user "@DrPufferfish"` always routes to `drpufferfish/` folders
- **Strict mapping**: in `--user` mode, wallet must resolve; no fallback to `unknown/` or wallet-prefix slugs
- **Wallet-to-slug mapping**: when wallet is known with a handle, the mapping is persisted to `kb/users/<slug>/profile.json`
- **Wallet mode**: wallet-first flows can use `--wallet`; when no mapping exists, fallback is `wallet_<first8>`
- **Consistent paths**: all CLI commands and MCP tools use the same resolver

This ensures outputs like dossiers, bundles, and reports always land in the
same user folder for handle-first workflows.

## Resolution outcomes

Each position now includes a `resolution_outcome` field:
- `WIN` / `LOSS`: held to resolution
- `PROFIT_EXIT` / `LOSS_EXIT`: exited before resolution
- `PENDING`: market not yet resolved
- `UNKNOWN_RESOLUTION`: resolution data unavailable

## Common pitfalls

- **User scoping**: quote `--user "@name"` in PowerShell and keep user vs wallet inputs consistent across commands.
- **Private-only defaults**: `rag-query` searches private content by default; public docs are excluded unless `--public-only` is set.
- **Model downloads/caching**: the first vector or rerank run downloads models into `kb/rag/models/`.
- **FTS5 availability**: lexical or hybrid search requires SQLite with FTS5; if missing, use vector-only retrieval.
- **Index freshness**: after adding dossiers or LLM reports, rerun `rag-index` so the new files are searchable.
- **CLI**: use `python -m polytool` for canonical docs and scripts.

## Developer Notes

- **Canonical commands**: always use `python -m polytool <command>` in docs, scripts, and runbooks. The `polytool` console script also works.
- **Manual workflow is default**: the manual examination workflow (scan -> export/bundle -> paste -> llm-save) is the primary path. See `docs/RUNBOOK_MANUAL_EXAMINE.md`.
- **MCP is optional**: the MCP server (`python -m polytool mcp`) provides Claude Desktop integration but is not required for the core workflow. It is tracked separately in the roadmap.
- **double-t shim removed**: the old `polyttool` backward-compatibility shim has been removed. See [ADR-0001](adr/ADR-0001-cli-and-module-rename.md).
