# Roadmap

Master Roadmap v5 (`docs/reference/POLYTOOL_MASTER_ROADMAP_v5.md`) is the
governing roadmap document as of 2026-03-21 and supersedes v4.2.

This file is retained as the legacy implementation ledger for the numbered
Roadmap 0-10 milestones and Track A/Track B checkpoints. Treat `COMPLETE` in
this file as evidence that a pre-v4 milestone shipped, not as proof that the
corresponding v4.2 phase is complete.

## Authority Notes / Material Deltas vs v5

| Area | Master Roadmap v5 | Current ledger meaning |
|------|-------------------|------------------------|
| Phase 1A / crypto pair bot | Fastest path to first dollar; standalone, not blocked on SimTrader gates. | Substantially built as of 2026-03-29: accumulation_engine, paper_runner, live_runner, backtest_harness, and full CLI surface shipped (quick-019 through quick-052). Strategy pivoted twice: per-leg target_bid gate (quick-046), then directional momentum from gabagool22 analysis (quick-049). Paper soak BLOCKED — no active BTC/ETH/SOL 5m/15m markets as of 2026-03-29. Live deployment BLOCKED pending full soak, oracle validation (Coinbase vs Chainlink), and EU VPS confirmation. Track 2 remains STANDALONE — does not wait for Gate 2 or Gate 3. |
| Phase 1B / live bot | Includes Gate 2 scenario sweep, Gate 3 shadow, Stage 0 paper-live, and Stage 1 capital. | Current Track A entries only prove execution primitives and gating harness work shipped. Gate 2, Gate 3, Stage 0, and Stage 1 remain open. benchmark_v1 manifest is CLOSED (2026-03-21). |
| Database split | DuckDB = historical Parquet reads. ClickHouse = live streaming writes. | Rule adopted and in force. ClickHouse bulk import (SPEC-0018) is off the critical path; pmxt and Jon-Becker raw files exist locally for DuckDB. |
| Phase 2 / discovery + scraper | Includes `candidate-scan`, research scraper, news/signals ingest, and automation workflows. | Track B `COMPLETE` here covers wallet-scan, alpha-distill, RAG hardening, hypothesis registry foundation, and Hypothesis Validation Loop v0 only. Wallet Discovery v1 spec frozen (2026-04-09): Loop A leaderboard discovery, ClickHouse watchlist/leaderboard/queue contracts, unified scan --quick, MVF computation. Full four-loop system (B/C/D, insider scoring, cloud LLM hypotheses, auto-promotion, n8n) remains future intent with explicit blockers listed in SPEC-wallet-discovery-v1.md. |
| Phase 3+ / Studio rebuild | Calls for a new unified Next.js Studio in later phases. | Current UI-related items in this file describe the existing operator surfaces. No custom frontend before profit. |

---

## Legacy Milestone Checklist (pre-v4 ledger)

### Roadmap 0 - Foundation [COMPLETE]

- [x] ClickHouse schema with ReplacingMergeTree tables
- [x] API ingest endpoints (trades, activity, positions, markets)
- [x] Grafana dashboards (User Trades, Strategy Detectors, PnL, Arb Feasibility)
- [x] `scan` CLI command with env-driven and flag-driven configuration
- [x] Strategy detectors (HOLDING_STYLE, DCA_LADDERING, MARKET_SELECTION_BIAS, COMPLETE_SET_ARBISH)
- [x] PnL computation (FIFO realized + MTM)
- [x] Arb feasibility analysis (dynamic fees + slippage)

**Acceptance**: All API endpoints return 200, Grafana dashboards render, scan
produces data in ClickHouse.

---

### Roadmap 1 - Examination Pipeline [COMPLETE]

- [x] `export-dossier` with resolution outcomes (WIN/LOSS/PROFIT_EXIT/LOSS_EXIT/PENDING/UNKNOWN_RESOLUTION)
- [x] `llm-bundle` generates evidence bundle + prompt template
- [x] `llm-save` stores report + manifest + auto-generates LLM_note
- [x] `examine` orchestrator (scan -> dossier -> bundle -> prompt)
- [x] User identity resolution (`polytool/user_context.py`: handle-first, strict mapping)
- [x] RAG index + query (vector via Chroma, lexical via FTS5, hybrid via RRF, rerank via cross-encoder)
- [x] `rag-eval` retrieval quality harness
- [x] `cache-source` with allowlist + TTL + robots.txt
- [x] MCP server (stdio, official `mcp` SDK)
- [x] Hypothesis schema v1 (`docs/specs/hypothesis_schema_v1.json`)
- [x] Strategy playbook v0 (`docs/STRATEGY_PLAYBOOK.md`)
- [x] Plan of Record documentation (`docs/PLAN_OF_RECORD.md`)

**Acceptance**: Roadmap 1 is complete when ALL of the following are true:

1. `python -m polytool scan --user "@handle"` resolves identity and completes
   end-to-end via the canonical CLI path.
2. A real examination run has produced a dossier, bundle, and prompt under the
   correct canonical paths (confirmed; does NOT need to be re-run).
3. `python -m polytool rag-query --hybrid --rerank` returns relevant results
   from the local index.
4. `python -m polytool llm-save` stores a report + manifest and writes an
   LLM_note.
5. The MCP server starts without protocol errors (`python -m polytool mcp`).
6. `pytest` passes with no regressions (known pre-existing failures excepted).
7. Pre-push guard passes (`python tools/guard/pre_push_guard.py`).
8. Plan of Record and supporting docs are committed and reviewed.

**Stop condition**: Do not proceed to Roadmap 2 until all 8 criteria are met.

---

### Roadmap 2 - Trust Artifacts & Scan Canonicalization [COMPLETE]

- [x] Canonical trust artifact emission from `python -m polytool scan`
- [x] `coverage_reconciliation_report.json` emitted with split UID metrics:
  `deterministic_trade_uid_coverage` and `fallback_uid_coverage`
- [x] `run_manifest.json` emitted with canonical `command_name = "scan"`
- [x] Empty-export diagnostics documented (`--debug-export`) and warnings surfaced
  when `positions_total = 0`
- [x] Docs updated to treat `scan` as canonical and `examine` as legacy

**Acceptance**: Scan runs consistently emit trust artifacts in the run root under
`artifacts/dossiers/users/.../<run_id>/`, and docs clearly describe interpretation
and troubleshooting.

**Handoff**: Reducing `UNKNOWN_RESOLUTION`, improving outcome coverage quality,
and closing missing PnL/fees gaps are owned by Roadmap 3.

---

### Roadmap 3 - Resolution Coverage [COMPLETE]

- [x] OnChainCTFProvider reading CTF payout state from Polygon RPC
- [x] SubgraphResolutionProvider as fallback via The Graph
- [x] 4-stage CachedResolutionProvider chain (ClickHouse -> OnChainCTF -> Subgraph -> Gamma)
- [x] Resolution dataclass with explicit `reason` field for traceability
- [x] Unit tests for all resolution providers with mocked RPC/subgraph
- [x] Reduce `UNKNOWN_RESOLUTION` rate for resolved markets to near-zero
- [x] Enrichment parity: `--enrich-resolutions` without explicit knobs achieves
  comparable coverage, or dataset mismatch is detected via `resolution_parity_debug.json`

**Acceptance**: `UNKNOWN_RESOLUTION` rate for markets that are objectively resolved
on-chain drops to < 5%. All resolution sources carry explicit `resolution_source`
and `reason` fields. Unit tests pass with mocked providers. No-knob enrichment
runs produce identical payloads to knobbed runs (or mismatch is reported).

**Evidence**: See `docs/roadmap3_completion.md` and trust-artifact run
`dd32ff26-b751-41a3-9aae-e9f59645040f` (2026-02-12).

**Kill condition**: If Gamma API coverage is already sufficient (>95% resolved
markets covered), defer on-chain provider to a future milestone.

---

### Roadmap 4 - Segment Analysis, Fees & Audit Hardening [COMPLETE]

- [x] Segment analysis with breakdowns by `entry_price_tier`, `market_type`, `league`, `sport`, `category`
- [x] `segment_analysis.json` artifact emitted alongside coverage report (Spec-0003, ADR-0006)
- [x] YAML-configurable entry price tiers (`polytool.yaml` `segment_config.entry_price_tiers`)
- [x] Fee estimation: 2 % on gross profit, configurable via `fee_config.profit_fee_rate` (ADR-0007)
- [x] Market metadata backfill (self-referential, no network call) with `market_metadata_coverage` in report
- [x] Category segmentation: Polymarket `category` field verbatim; absent â†’ `"Unknown"` (ADR-0009)
- [x] Category ingestion fix: LEFT JOIN `polymarket_tokens` in lifecycle query (was reporting 0 % coverage)
- [x] `audit-coverage` CLI: offline trust sanity, reads latest run artifacts, no ClickHouse/network (Spec-0007)
- [x] Scan auto-audit: every `scan` emits `audit_coverage_report.md` unconditionally (Spec-0008)
- [x] Audit default: all positions, not a fixed sample (ADR-0011)
- [x] History position-count fallback: use body rows when history row reports 0 (ADR-0010)
- [x] Root `README.md` with canonical quickstart runbook

**Acceptance**: All scan runs emit `segment_analysis.json` and `audit_coverage_report.md`.
`audit-coverage` runs fully offline. Category coverage is non-zero after the market
backfill pipeline has run. Schema version `1.4.0`.

**Evidence**: See `docs/pdr/PDR-ROADMAP4-WRAPUP.md` and ADRs 0006â€“0011.

---

### Roadmap 5 - CLV & Time/Price Context Signals [COMPLETE]

#### 5.0 Prerequisites

- [x] Confirm category coverage > 0 % post-backfill (regression from 4.6 confirmed fixed)
- [x] Default `market_type` moneyline rule for team-vs-team markets
- [x] Surface notional/size end-to-end (USDC position size in dossier and audit report)

#### 5.1 CLV Capture

- [x] Add `scan --compute-clv` enrichment stage (cache-first; explicit missingness)
- [x] Capture closing-line price snapshot per market before resolution
- [x] Compute CLV per position: `closing_price âˆ’ entry_price` (binary markets)
- [x] Store price snapshots in ClickHouse; populate at scan time when markets close
- [x] Report CLV coverage rate in `coverage_reconciliation_report`
- [x] Surface CLV in `segment_analysis.by_entry_price_tier` breakdown

#### 5.2 Time/Price Context

- [ ] Track price trajectory over hold period (from ClickHouse snapshot cadence)
- [ ] Minimal snapshot caching (TTL-based; no crawl depth)

#### 5.5 Batch-Run Harness + Hypothesis Leaderboard [COMPLETE]

- [x] `python -m polytool batch-run` command with multi-user input file support
- [x] Deterministic leaderboard artifacts: JSON + Markdown
- [x] Batch trust artifact: `batch_manifest.json` with output path/run-root traceability
- [x] Offline-safe tests via injected scan callable (no network / no ClickHouse)

**Acceptance**: `segment_analysis.json` includes `clv` for positions where snapshot
data is available. Coverage report includes CLV coverage rate. Positions without
closing-line data report `clv: null`, not missing.

**Kill condition**: If snapshot capture rate is < 30 % after 3 scan runs, document
the gap and defer CLV computation.

**Evidence**: See `docs/pdr/PDR-ROADMAP5-WRAPUP.md` and associated PDRs for CLV verification and prerequisite checks.

---

### Track B - Research Loop Foundation [COMPLETE]

This track runs parallel to the numbered Roadmaps and covers the research
analysis pipeline that sits on top of the scan/dossier infrastructure.
Track B foundation is complete: wallet-scan v0, alpha-distill v0, RAG
reliability hardening, and offline hypothesis tracking.

#### Done: Track B Foundation (completed 2026-03-05)

- [x] `wallet-scan` v0: batch scan for a list of handles/wallets; deterministic leaderboard by net PnL
- [x] `alpha-distill` v0: cross-user segment aggregation → ranked edge hypothesis candidates
- [x] RAG default collection centralized (`polytool_rag`) across all CLI tools
- [x] `rag-index` progress logging + binary/oversized file filters + `--max-bytes` flag
- [x] `rag-run` CLI: re-execute stored `rag_queries.json` against the current index
- [x] LLM bundle excerpt de-noising: circular bundle artifacts excluded from RAG selection
- [x] LLM bundle report stub: blank `reports/<date>/<run_id>_report.md` written per bundle run
- [x] `rag_queries.json` execution status fields (`executed`/`not_executed`/`error`)

**Acceptance criteria**:

1. `python -m polytool wallet-scan --input wallets.txt` completes without error and emits `leaderboard.json` + `per_user_results.jsonl`.
2. `python -m polytool alpha-distill --wallet-scan-run <path>` reads the wallet-scan output and emits `alpha_candidates.json` with at least a `summary` block.
3. `python -m polytool rag-index` emits progress lines and a final summary with skip counters.
4. `python -m polytool rag-run --rag-queries <path>` re-executes queries and writes updated `rag_queries.json`.
5. `python -m polytool llm-bundle` writes a report stub at `kb/users/<slug>/reports/…`.
6. `pytest -q` passes with no regressions (known pre-existing failures excepted).

**Done artifacts**:

- `tools/cli/wallet_scan.py`, `tools/cli/alpha_distill.py`, `tools/cli/rag_run.py`
- `packages/polymarket/rag/defaults.py`
- `docs/specs/SPEC-wallet-scan-v0.md`, `docs/specs/SPEC-alpha-distill-v0.md`, `docs/specs/LLM_BUNDLE_CONTRACT.md`
- `tests/test_wallet_scan.py`, `tests/test_alpha_distill.py`, `tests/test_rag_run.py`, `tests/test_rag_index_progress_filters.py`, `tests/test_rag_collection_defaults.py`

---

#### Done: Usability Pass (completed 2026-03-07)

Operator-facing improvements only. No strategy logic, gate thresholds, or test files changed.

- [x] `rag-refresh` command added: thin alias for `rag-index --rebuild`, listed prominently as the one-command RAG rebuild path
- [x] `python -m polytool --help` reorganized into 5 workflow groups (Research Loop, Analysis & Evidence, RAG & Knowledge, SimTrader / Execution, Integrations & Utilities)
- [x] `docs/OPERATOR_QUICKSTART.md` rewritten as a 10-section end-to-end guide covering research loop, single-user examination, RAG, market scanner, gates, daily dev loop, Studio, Grafana, and Stage 0 → Stage 1
- [x] SimTrader Studio Dashboard tab: Grafana deep-link cards for all key dashboards
- [x] `docs/LOCAL_RAG_WORKFLOW.md`: `rag-refresh` one-command section added at top
- [x] `docs/INDEX.md`: `OPERATOR_QUICKSTART.md` promoted to "Start here" in Getting Started table

---

#### Done: Hypothesis Registry v0 + experiment skeleton (`experiment-init` + `experiment-run`) (completed 2026-03-05)

Research-only. Tracks hypothesis lifecycle from candidate -> tested ->
validated/rejected/parked.

- [x] `hypothesis-register`: persist a candidate from `alpha_candidates.json` into a local registry with a stable `hypothesis_id`
- [x] Registry format: append-only JSONL at `artifacts/research/hypothesis_registry/registry.jsonl`; each event carries `schema_version="hypothesis_registry_v0"`, source provenance, lifecycle `status` (`proposed`/`testing`/`validated`/`rejected`/`parked`), timestamps, and notes
- [x] `hypothesis-status`: append a status change event with a required human-readable `reason`
- [x] `experiment-init`: write `experiment.json` at `artifacts/research/experiments/<hypothesis_id>/<experiment_id>/`
- [x] `experiment-run`: create a generated experiment attempt directory under `artifacts/research/experiments/<hypothesis_id>/`
- [x] Focused CLI coverage for register -> status -> experiment skeleton round trips

**Acceptance criteria**:

1. `python -m polytool hypothesis-register --candidate-file alpha_candidates.json --rank 1 --registry artifacts/research/hypothesis_registry/registry.jsonl` appends a `registered` event and prints the new `hypothesis_id`.
2. `python -m polytool hypothesis-status --id <id> --status testing --reason "manual review" --registry artifacts/research/hypothesis_registry/registry.jsonl` appends a full-snapshot status change event.
3. `python -m polytool experiment-init --id <id> --registry artifacts/research/hypothesis_registry/registry.jsonl --outdir artifacts/research/experiments/<hypothesis_id>/<experiment_id>` writes `experiment.json` with `schema_version="experiment_init_v0"` and a registry snapshot.
4. `python -m polytool experiment-run --id <id> --registry artifacts/research/hypothesis_registry/registry.jsonl --outdir artifacts/research/experiments/<hypothesis_id>` creates a generated attempt directory and writes the same `experiment.json` payload there.
5. `pytest -q tests/test_hypothesis_registry.py tests/test_experiment_init.py tests/test_experiment_run.py tests/test_hypotheses_cli.py` passes.

**Done artifacts**:

- `packages/research/hypotheses/registry.py`, `tools/cli/hypotheses.py`, `polytool/__main__.py`
- `docs/specs/SPEC-hypothesis-registry-v0.md`, `docs/features/FEATURE-hypothesis-registry-v0.md`
- `tests/test_hypothesis_registry.py`, `tests/test_experiment_init.py`, `tests/test_hypotheses_cli.py`

**Status**: Hypothesis Validation Loop v0 is complete [CLOSED 2026-03-12].
Gate 2 scenario sweep against `config/benchmark_v1.tape_manifest` is the Phase 2 starting point (Phase 1B).

---

### Track A - Optional Execution Layer [IN SCOPE, GATED]

Track A is optional. It is not required for Track B research workflows and is
never enabled by default.

#### Current Track A status (2026-03-21)

- Gate 1: PASSED
- Gate 2: not passed yet, but tooling and tape manifest are ready
- Gate 3: blocked behind Gate 2
- Gate 4: PASSED
- **Phase 1 benchmark CLOSED (2026-03-21)**: `config/benchmark_v1.tape_manifest`
  exists (50 tapes: `politics=10, sports=15, crypto=10, near_resolution=10,
  new_market=5`). Lock and audit artifacts also exist.
- Current next step (Phase 2): Gate 2 scenario sweep against the benchmark
  manifest. DuckDB + Silver reconstruction infrastructure is in place.
  See `docs/dev_logs/2026-03-21_phase1_docs_closeout.md`.
- ClickHouse bulk import (SPEC-0018): off the critical path under v4.2.
  `docs/runbooks/BULK_HISTORICAL_IMPORT_V0.md` is retained as
  legacy/optional cache-index tooling.
- Fallback trigger (live path): bounded live dislocation capture remains
  an option when a catalyst window fires; see
  `docs/dev_logs/2026-03-07_bounded_dislocation_capture_trial.md`
- Opportunity Radar remains deferred

#### Done: Track A Week 1 - Execution primitives (completed 2026-03-05)

- [x] `FileBasedKillSwitch` + `KillSwitch` interface
- [x] `TokenBucketRateLimiter` with injectable clock/sleep for offline tests
- [x] `RiskManager` with conservative Stage-0 order, position, loss, and inventory caps
- [x] `LiveExecutor` wrapper with kill-switch-first, dry-run-first behavior
- [x] `LiveRunner` orchestrator and `simtrader live` CLI surface (`--live` is now the explicit live submission path)

**Acceptance criteria**:

1. `python -m polytool simtrader live` runs a single Stage-0 tick in dry-run mode and prints a JSON summary.
2. `python -m polytool simtrader live --help` documents `--live`, `--kill-switch`, `--rate-limit`, and the four USD risk-cap flags.
3. Dry-run still checks the kill switch and never calls the client; live mode enforces `kill switch -> rate limiter -> client` order.
4. `pytest -q tests/test_live_execution.py` passes.

**Done artifacts**:

- `packages/polymarket/simtrader/execution/__init__.py`, `packages/polymarket/simtrader/execution/kill_switch.py`, `packages/polymarket/simtrader/execution/rate_limiter.py`, `packages/polymarket/simtrader/execution/risk_manager.py`, `packages/polymarket/simtrader/execution/live_executor.py`, `packages/polymarket/simtrader/execution/live_runner.py`
- `tools/cli/simtrader.py`
- `docs/specs/SPEC-0011-live-execution-layer.md`, `docs/features/FEATURE-trackA-week1-execution-primitives.md`
- `tests/test_live_execution.py`

Track A code is complete, but promotion remains blocked until the gate checklist
below is fully closed.

- [x] Replay gate: PASSED (artifact: `artifacts/gates/replay_gate/gate_passed.json`)
- [ ] Scenario sweep gate: NOT PASSED. Tooling is ready.
  `config/benchmark_v1.tape_manifest` now exists (50 tapes, 5 buckets) —
  Phase 1 complete as of 2026-03-21. Gate 2 sweep against this manifest is
  the Phase 2 starting point.
- [ ] Shadow gate: BLOCKED behind Gate 2; follow
  `tools/gates/shadow_gate_checklist.md` after Gate 2 passes
- [x] Dry-run live gate: PASSED (artifact: `artifacts/gates/dry_run_gate/gate_passed.json`)
- [ ] Stage 0 paper-live: BLOCKED until Gates 1-4 pass, then run 72 hours with zero capital
- [ ] Stage 1 capital: BLOCKED until Stage 0 completes cleanly

### Validation Pipeline (Canonical)

The canonical operator validation pipeline is:

1. Replay Validation -> Gate 1
2. Sweep Validation -> Gate 2
3. Shadow Validation -> Gate 3
4. Dry Run -> Gate 4
5. Stage 0 -> 72 hour paper-live run
6. Stage 1 -> live trading with capital

Historical note: older planning language may refer to a "30-day shadow
validation." That wording is retired. Gate 3 shadow validation plus Gate 4
dry-run live plus the 72 hour Stage 0 paper-live run now define the
pre-capital path.

**Hard promotion order**:
`replay -> scenario sweeps -> shadow -> dry-run live -> Stage 0 paper-live -> Stage 1 capital`.
No live capital is allowed before all four gates pass and Stage 0 completes cleanly.

**Execution policy**:

1. Research outputs are not signals.
2. Execution runs only operator-supplied strategies.
3. A strategy must pass all prior gates and risk controls before any capital stage.

**Spec**: `docs/specs/SPEC-0011-live-execution-layer.md`.

#### Gate Evidence

Gate artifacts are written to `artifacts/gates/<gate_name>/` and contain
`gate_passed.json` (or `gate_failed.json`) with commit hash, timestamp, and
details.

| Gate | Script | Artifact directory |
|------|--------|--------------------|
| Gate 1 — Replay Determinism | `tools/gates/close_replay_gate.py` | `artifacts/gates/replay_gate/` |
| Gate 2 — Scenario Sweep | `tools/gates/close_sweep_gate.py` | `artifacts/gates/sweep_gate/` |
| Gate 3 — Shadow Mode (manual) | `tools/gates/shadow_gate_checklist.md` | `artifacts/gates/shadow_gate/` |
| Gate 4 — Dry-Run Live | `tools/gates/run_dry_run_gate.py` | `artifacts/gates/dry_run_gate/` |

As of 2026-03-07, Gate 1 and Gate 4 have passing artifacts. Gate 2 is not yet
passed because no eligible tape has been captured, and Gate 3 has no artifact
because it remains blocked behind Gate 2.

**Check all gate statuses:**

```bash
python tools/gates/gate_status.py
```

Returns exit code 0 when every gate shows a `gate_passed.json`; exit code 1
otherwise. Do not start Stage 0 paper-live until this command exits 0, and do
not promote to Stage 1 capital until Stage 0 is clean.

Gates 1, 2, 3 require a live Polymarket connection.  Gate 4 runs fully offline.
Gate 3 is manual — follow `tools/gates/shadow_gate_checklist.md` and write the
artifact by hand after operator sign-off.

---

#### Done: Track A Week 2 — OrderManager + MarketMaker v0 (completed 2026-03-05)

Order lifecycle management and a first concrete strategy for replay, shadow, dry-run live, and gated live deployment.

- [x] `OrderManager` reconciliation loop: diffs desired quotes vs. open orders; enforces min-lifetime, cancel-rate, and place-rate caps; returns an `ActionPlan` (no side effects)
- [x] `MarketMakerV0` Avellaneda-Stoikov quoting strategy: microprice input, rolling sigma estimate, resolution guard, bounded spreads, and binary-market quote clamps
- [x] `market_maker_v0` registered in `STRATEGY_REGISTRY` (`strategy/facade.py`) — usable in `simtrader run`, `simtrader quickrun`, and `simtrader shadow` via `--strategy market_maker_v0`
- [x] `simtrader live` CLI extended: `--strategy`, `--asset-id`, `--live`, `--max-position-usd`, `--daily-loss-cap-usd`, `--max-order-usd`, `--inventory-skew-limit-usd`
- [x] Dry-run default preserved: `simtrader live --strategy market_maker_v0` prints `WOULD PLACE` lines, runs risk checks, and makes no client call unless `--live` is passed
- [x] Kill switch checked before every place/cancel even in dry-run mode
- [x] Sprint-end validation: 1188 tests passing total, including 12 wallet integration tests, 30 `MarketMakerV0` tests, and passing market selection coverage

**Done artifacts**:

- `packages/polymarket/simtrader/execution/wallet.py`
- `packages/polymarket/simtrader/strategies/market_maker_v0.py`
- `packages/polymarket/simtrader/execution/order_manager.py`
- `packages/polymarket/simtrader/execution/live_executor.py`
- `packages/polymarket/simtrader/execution/risk_manager.py`
- `tools/cli/simtrader.py` (updated live subparser)
- `packages/polymarket/market_selection/`
- `tools/gates/`
- `docs/runbooks/LIVE_DEPLOYMENT_STAGE1.md`
- `tests/test_market_maker_v0.py`, `tests/test_order_manager.py`, `tests/test_wallet_integration.py`, `tests/test_market_selection.py`
- `docs/features/FEATURE-trackA-week2-market-maker-v0.md`
- `docs/features/FEATURE-trackA-live-clob-wiring.md`
- `docs/dev_logs/2026-03-05_trackA_week2_market_maker_v0.md`

The same Track A gate checklist above remains in force. Week 2 does not change
the gate order; it adds a concrete strategy that can now be validated through
each gate.

---

#### Track A Code Complete (2026-03-05)

- `packages/polymarket/simtrader/execution/wallet.py`: real `ClobClient` builder and credential bootstrap helper.
- `packages/polymarket/simtrader/execution/live_executor.py`: live create/cancel calls route through an injected real client.
- `packages/polymarket/simtrader/execution/risk_manager.py`: inventory skew cap, last-fill tracking, and net inventory notional checks.
- `packages/polymarket/simtrader/strategies/market_maker_v0.py`: Avellaneda-Stoikov market maker with bounded quotes and a resolution guard.
- `packages/polymarket/market_selection/__init__.py`: package entrypoint for market selection helpers.
- `packages/polymarket/market_selection/scorer.py`: market scoring model and `MarketScore`.
- `packages/polymarket/market_selection/filters.py`: market pre-filter rules.
- `packages/polymarket/market_selection/api_client.py`: Gamma and orderbook fetch helpers for candidate selection.
- `tools/cli/market_scan.py`: CLI entrypoint for `python -m polytool market-scan`.
- `tools/gates/close_replay_gate.py`: Gate 1 closure script.
- `tools/gates/close_sweep_gate.py`: Gate 2 closure script.
- `tools/gates/run_dry_run_gate.py`: Gate 4 closure script.
- `tools/gates/gate_status.py`: consolidated gate artifact reporter.
- `tools/gates/shadow_gate_checklist.md`: manual Gate 3 operator procedure.
- `tools/cli/simtrader.py`: `--live`, gate artifact checks, wallet loading, `CONFIRM`, kill switch command, and USD risk flags.
- `docs/runbooks/LIVE_DEPLOYMENT_STAGE1.md`: one-page Stage 1 operator runbook.

### Roadmap: Market Selection Engine [COMPLETE]

- [x] `packages/polymarket/market_selection/` package created
- [x] Scorer, filters, API client implemented
- [x] `python -m polytool market-scan` CLI registered
- [x] Tests passing

---

### Roadmap 6 - Source Caching & Crawl [NOT STARTED]

- [ ] Full robots.txt parsing (currently basic)
- [ ] Crawl depth support (follow links within domain)
- [ ] PDF/DOCX support for cached sources
- [ ] Automatic TTL-based refresh
- [ ] Cache eviction for expired content

**Acceptance**: `cache-source` can crawl 2 levels deep with full robots.txt
compliance. Expired content is automatically pruned.

**Kill condition**: If `cache-source` is sufficient for current research needs,
defer this milestone.

---

### Roadmap 7 - MCP Hardening [NOT STARTED]

- [ ] HTTP transport (currently stdio only)
- [ ] Authentication for multi-user scenarios
- [ ] Resource endpoints for direct file access
- [ ] Streaming for large responses

**Acceptance**: MCP works via HTTP transport with Claude Desktop. Auth prevents
unauthorized access when exposed on network.

**Kill condition**: If manual workflow remains sufficient, defer indefinitely.

---

### Roadmap 8 - Multi-User & Comparison [NOT STARTED]

- [ ] Compare users side-by-side
- [ ] Portfolio-level aggregation
- [ ] User clustering by strategy similarity

**Acceptance**: Two users can be compared in a single Grafana dashboard or CLI
report.

**Kill condition**: Single-user analysis is sufficient for research needs.

---

### Roadmap 9 - CLI & Dashboard Polish [NOT STARTED]

- [ ] Progress bars for long operations
- [ ] JSON output mode for all commands
- [ ] Tab completion for bash/zsh
- [ ] User comparison dashboard
- [ ] Category breakdown panel
- [ ] Win rate trend over time
- [ ] Position lifecycle visualization

**Acceptance**: All CLI commands support `--json` output. Grafana has category
breakdown and lifecycle panels.

**Kill condition**: Current UX is sufficient for research workflows.

---

### Roadmap 10 - CI & Testing [NOT STARTED]

- [ ] Integration tests for scan-first workflow (legacy examine smoke kept separate)
- [ ] Mock ClickHouse for CI (no Docker dependency)
- [ ] Property-based tests for fee calculation
- [ ] RAG index load testing

**Acceptance**: CI pipeline runs full test suite without Docker. Fee property
tests cover edge cases.

**Kill condition**: Test suite is comprehensive enough for current codebase size.

---

### Wallet Discovery v1 [SHIPPED]

- [x] Loop A: leaderboard fetcher + churn detection + scan queue
- [x] ClickHouse tables: watchlist, leaderboard_snapshots, scan_queue
- [x] Unified `polytool scan <address>` with `--quick` (no-LLM guarantee)
- [x] MVF computation (11-dim, Python math only)

**Shipped**: 2026-04-10. 118 discovery-area tests passing. 3908 full suite.

**Spec**: docs/specs/SPEC-wallet-discovery-v1.md
**Acceptance**: All 7 deterministic acceptance tests pass.

**Deferred (explicit blockers in spec)**:
- Loop B, C, D, insider scoring, cloud LLM wallet analysis, auto-promotion, n8n

---

## Deferred Backlog

Items below are explicitly deferred. They have a named trigger condition.
Do not start implementing them until the trigger is met.

---

### DEFERRED: Opportunity Radar

**Status**: Deferred — not started, not scoped.

**What it is**: A continuous or scheduled monitoring layer that watches live
Polymarket markets for Gate 2 conditions (complement edge + depth), surfaces
candidates automatically, and may trigger tape capture or alerting.

**Why deferred**: The current bottleneck is not market intelligence — it is
having a clean Gate 2 -> Gate 3 tape with `executable_ticks > 0`. Building a
monitoring layer before that tape exists adds infrastructure without unblocking
anything.

**Trigger**: Start planning Opportunity Radar only after the first clean
Gate 2 -> Gate 3 progression is completed (i.e., a tape passes the sweep gate
and shadow gate in sequence with no manual workarounds).

**Scope when ready** (do not start implementation now):
- Periodic live scan (`scan-gate2-candidates`) with scheduling (cron / daemon)
- Threshold alerts when a market exceeds a configurable edge + depth score
- Optional auto-trigger of `prepare-gate2` for top-ranked candidates
- Persisted scan history for trend analysis

**Prerequisite reading** (when trigger fires):
- `docs/dev_logs/2026-03-06_gate2_market_scanner.md`
- `docs/dev_logs/2026-03-06_gate2_prep_orchestrator.md`
- `tools/cli/scan_gate2_candidates.py` (scoring logic to extend)
- `tools/cli/prepare_gate2.py` (orchestration glue to wrap)

---

## Kill / Stop Conditions (Global)

These guard against feature creep. Do NOT start the next milestone until the
current one is fully shipped.

- **No backtesting** until Roadmap 5 CLV and context signal capture is shipped.
- **No real-time monitoring** (out of scope entirely; see TODO.md).
- **No external LLM API calls** (remains local-only forever).
- **No mobile app / web UI** (out of scope entirely).
- **No multi-tenant hosting** (local-first only).
- **No live capital** before Track A gates and Stage 0 are complete
  (`replay -> scenario sweeps -> shadow -> dry-run live -> Stage 0 paper-live`).
- If a milestone is blocked by an external dependency (API change, SDK bug),
  park it and document the blocker in TODO.md rather than working around it.

---

## Deprecation: polytool shim

The `polytool` backward-compatibility shim (double-t typo) will be removed
after version 0.2.0. Until then, `python -m polytool` still works but prints
a deprecation warning. All new docs and scripts must use `python -m polytool`.
See [ADR-0001](adr/ADR-0001-cli-and-module-rename.md) for details.

