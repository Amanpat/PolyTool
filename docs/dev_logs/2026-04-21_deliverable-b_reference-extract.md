# 2026-04-21 Deliverable B Reference Extract

## Scope

Read-only extraction for PMXT Deliverable B from the upstream repository
`evan-kolberg/prediction-market-backtesting`, with attention limited to:

- `strategies/final_period_momentum.py`
- `strategies/late_favorite_limit_hold.py`
- `strategies/vwap_reversion.py`

Supporting files inspected for behavior and licensing context:

- `strategies/core.py`
- `NOTICE`
- `README.md`

## Repo / Branch Inspected

- Repository: `https://github.com/evan-kolberg/prediction-market-backtesting`
- Branch requested: `v2`
- Branch reality: `v2` exists and was inspected directly

## Commands Run

### Local workspace safety checks

Command:

```powershell
git status --short
```

Output:

```text
(no output)
```

Command:

```powershell
git log --oneline -5
```

Output:

```text
504e7b7 Fee Model Overhaul
42d9985 docs: add AGENTS.md and CURRENT_DEVELOPMENT.md for workflow refresh
2dc03a7 docs(quick-260415-rdy): complete Loop D feasibility -- add plan artifact and update STATE.md
b01c80a docs(quick-260415-rdp): complete Loop B phase 0 feasibility -- add plan artifact and update STATE.md
9f09690 docs(quick-260415-rdy): complete Loop D feasibility plan -- add SUMMARY and update STATE.md
```

Command:

```powershell
python -m polytool --help
```

Output:

```text
PolyTool - Polymarket analysis toolchain

Usage: polytool <command> [options]
       python -m polytool <command> [options]

--- Research Loop (Track B) -------------------------------------------
  wallet-scan           Batch-scan many wallets/handles -> ranked leaderboard
  alpha-distill         Distill wallet-scan data -> ranked edge candidates (no LLM)
  hypothesis-register   Register a candidate in the offline hypothesis registry
  hypothesis-status     Update lifecycle status for a registered hypothesis
  hypothesis-diff       Compare two saved hypothesis.json artifacts
  hypothesis-summary    Extract a deterministic summary from hypothesis.json
  experiment-init       Create an experiment.json skeleton for a hypothesis
  experiment-run        Create a generated experiment attempt for a hypothesis
  hypothesis-validate   Validate a hypothesis JSON file against schema_v1

--- Analysis & Evidence -----------------------------------------------
  scan                  Run a one-shot scan via the PolyTool API
  batch-run             Batch-run scans and aggregate a hypothesis leaderboard
  audit-coverage        Offline accuracy + trust sanity check from scan artifacts
  export-dossier        Export an LLM Research Packet dossier + memo
  export-clickhouse     Export ClickHouse datasets for a user

--- RAG & Knowledge ---------------------------------------------------
  rag-refresh           Rebuild the local RAG index (one-command, use this first)
  rag-index             Build or rebuild the RAG index (full control)
  rag-query             Query the local RAG index
  rag-run               Re-execute bundle rag_queries.json and write results back
  rag-eval              Evaluate retrieval quality
  cache-source          Cache a trusted web source for RAG indexing
  llm-bundle            Build an LLM evidence bundle from dossier + RAG excerpts
  llm-save              Save an LLM report run into the private KB

--- Research Intelligence (RIS v1/v2) -----------------------------------
  research-eval             Evaluate a document through the RIS quality gate
  research-precheck         Pre-development check: GO / CAUTION / STOP recommendation
  research-ingest           Ingest a document into the RIS knowledge store
  research-seed             Seed the RIS knowledge store from a manifest
  research-benchmark        Compare extractor outputs on a fixture set
  research-calibration      Inspect precheck calibration health over the ledger
  research-extract-claims   Extract structured claims from ingested documents (no LLM)
  research-acquire          Acquire a source from URL and ingest into knowledge store
  research-report           Save, list, search reports and generate weekly digests
  research-scheduler        Manage the RIS background ingestion scheduler
  research-stats            Operator metrics snapshot and local-first export for RIS pipeline
  research-health           Print RIS health status summary from stored run data
  research-review           Inspect and resolve RIS review-queue items
  research-dossier-extract  Parse dossier artifacts -> KnowledgeStore (source_family=dossier_report)
  research-register-hypothesis  Register a research hypothesis candidate in the JSONL registry
  research-record-outcome       Record a validation outcome for KnowledgeStore claims

--- Crypto Pair Bot (Track 2 / Phase 1A — standalone) -----------------
  crypto-pair-scan      Dry-run: discover BTC/ETH/SOL 5m/15m pair markets, compute edge
  crypto-pair-run       Paper by default; live scaffold behind --live with explicit safety gates
  crypto-pair-backtest  Replay historical/synthetic pair observations, emit eval artifacts
  crypto-pair-report    Summarize one completed paper run into rubric-backed markdown + JSON
  crypto-pair-review    One-screen post-soak review: verdict, metrics, risk controls, promote-band fit
  crypto-pair-watch     Check whether eligible BTC/ETH/SOL 5m/15m markets exist; poll with --watch
  crypto-pair-await-soak Wait for eligible markets, then launch the standard Coinbase paper smoke soak
  crypto-pair-seed-demo-events Seed dev-only synthetic Track 2 rows into ClickHouse for dashboard checks

--- SimTrader / Execution (Track A, gated) ----------------------------
  simtrader             Record/replay/shadow/live trading - run 'simtrader --help'
  market-scan           Rank active Polymarket markets by reward/spread/fill quality
  scan-gate2-candidates Rank markets by Gate 2 binary_complement_arb executability
  prepare-gate2         Scan -> record -> check eligibility for Gate 2 (orchestrator)
  watch-arb-candidates  Watch a market list and auto-record on near-edge dislocation
  tape-manifest         Scan tape corpus, check eligibility, emit acquisition manifest
  gate2-preflight       Check whether Gate 2 sweep is ready and why it may be blocked
  make-session-pack     Create exact watchlist + watcher-compatible session plan for a capture session

--- Data Import (Phase 1 / Bulk Historical Foundation) ----------------
  import-historical     Validate and document local historical dataset layout
  smoke-historical      DuckDB smoke - validate pmxt/Jon raw files directly (no ClickHouse)
  fetch-price-2min      Fetch 2-min price history from CLOB API -> polytool.price_2min (ClickHouse)
  reconstruct-silver    Reconstruct a Silver tape (pmxt anchor + Jon fills + price_2min midpoint guide)
  batch-reconstruct-silver Batch-reconstruct Silver tapes for multiple tokens over one window
  benchmark-manifest    Build or validate the frozen benchmark_v1 tape manifest contract
  new-market-capture    Discover newly listed markets (<48h) and plan Gold tape capture
  capture-new-market-tapes  Record Gold tapes for benchmark_v1 new_market targets (batch)
  close-benchmark-v1        End-to-end benchmark closure: preflight + Silver + new-market + manifest
  summarize-gap-fill        Read-only diagnostic summary for gap_fill_run.json artifacts

--- Wallet Discovery (v1 / Loop A) ------------------------------------
  discovery             Wallet discovery commands — run 'discovery --help'
    run-loop-a          Fetch leaderboard -> churn detection -> enqueue new wallets

--- Integrations & Utilities ------------------------------------------
  mcp                   Start the MCP server for Claude Desktop integration
  examine               Legacy examination orchestrator (scan -> bundle -> prompt)
  agent-run             Run an agent task (internal)

Options:
  -h, --help        Show this help message
  --version         Show version information

Common workflows:
  # Research loop
  polytool wallet-scan --input wallets.txt --profile lite
  polytool alpha-distill --wallet-scan-run artifacts/research/wallet_scan/YYYY-MM-DD/<id>
  polytool rag-refresh              # rebuild RAG index (one command)
  polytool rag-query --question "strategy patterns" --hybrid --rerank

  # Single user examination
  polytool scan --user "@DrPufferfish"
  polytool llm-bundle --user "@DrPufferfish"

  # SimTrader (gated)
  polytool market-scan --top 5
  polytool simtrader shadow --market <slug> --strategy market_maker_v1 --duration 300

For more information, see:
  docs/runbooks/OPERATOR_QUICKSTART.md   (end-to-end guide)
  docs/runbooks/LOCAL_RAG_WORKFLOW.md    (RAG details)
  docs/runbooks/README_SIMTRADER.md      (SimTrader operator guide)
```

### Remote inspection commands

Remote file contents were fetched read-only for analysis and are not reproduced
verbatim here because the target strategy files are listed as LGPL-covered in
the upstream `NOTICE`.

- `https://raw.githubusercontent.com/evan-kolberg/prediction-market-backtesting/v2/strategies/final_period_momentum.py`
- `https://raw.githubusercontent.com/evan-kolberg/prediction-market-backtesting/v2/strategies/late_favorite_limit_hold.py`
- `https://raw.githubusercontent.com/evan-kolberg/prediction-market-backtesting/v2/strategies/vwap_reversion.py`
- `https://raw.githubusercontent.com/evan-kolberg/prediction-market-backtesting/v2/strategies/core.py`
- `https://raw.githubusercontent.com/evan-kolberg/prediction-market-backtesting/v2/NOTICE`
- `https://github.com/evan-kolberg/prediction-market-backtesting/tree/v2`
- `https://github.com/evan-kolberg/prediction-market-backtesting/blob/v2/README.md`

## Files Inspected

- `strategies/final_period_momentum.py`
- `strategies/late_favorite_limit_hold.py`
- `strategies/vwap_reversion.py`
- `strategies/core.py`
- `NOTICE`
- `README.md`

## Parameter Tables

### final_period_momentum

| Variant | Required fields | Default fields |
| --- | --- | --- |
| `BarFinalPeriodMomentumConfig` | `instrument_id`, `bar_type` | `trade_size=1`, `market_close_time_ns=0`, `final_period_minutes=30`, `entry_price=0.80`, `take_profit_price=0.92`, `stop_loss_price=0.50` |
| `TradeTickFinalPeriodMomentumConfig` | `instrument_id` | `trade_size=100`, `market_close_time_ns=0`, `final_period_minutes=30`, `entry_price=0.80`, `take_profit_price=0.92`, `stop_loss_price=0.50` |
| `QuoteTickFinalPeriodMomentumConfig` | `instrument_id` | `trade_size=100`, `market_close_time_ns=0`, `final_period_minutes=30`, `entry_price=0.80`, `take_profit_price=0.92`, `stop_loss_price=0.50` |

### late_favorite_limit_hold

| Variant | Required fields | Default fields |
| --- | --- | --- |
| `TradeTickLateFavoriteLimitHoldConfig` | `instrument_id` | `trade_size=25`, `activation_start_time_ns=0`, `market_close_time_ns=0`, `entry_price=0.90` |
| `QuoteTickLateFavoriteLimitHoldConfig` | `instrument_id` | `trade_size=25`, `activation_start_time_ns=0`, `market_close_time_ns=0`, `entry_price=0.90` |

### vwap_reversion

| Variant | Required fields | Default fields |
| --- | --- | --- |
| `TradeTickVWAPReversionConfig` | `instrument_id` | `trade_size=1`, `vwap_window=80`, `entry_threshold=0.008`, `exit_threshold=0.002`, `min_tick_size=0.0`, `take_profit=0.015`, `stop_loss=0.02` |
| `QuoteTickVWAPReversionConfig` | `instrument_id` | `trade_size=1`, `vwap_window=80`, `entry_threshold=0.008`, `exit_threshold=0.002`, `min_tick_size=0.0`, `take_profit=0.015`, `stop_loss=0.02` |

## Signal Summaries

### final_period_momentum

- Activation window starts at `max(0, market_close_time_ns - final_period_minutes * 60 * 1e9)` and ends at `market_close_time_ns`.
- If `market_close_time_ns <= 0`, the strategy never activates.
- Entry requires a below-to-above threshold cross: previous observed price must be below `entry_price`, and current observed price must be at or above it.
- Signal source depends on variant:
  - bar variant uses bar close
  - trade variant uses trade price
  - quote variant uses midpoint for the signal, ask for entry sizing/execution reference
- Exit while in position occurs at or after market close, or sooner if observed price reaches `take_profit_price` or falls to `stop_loss_price`.
- Entry is one-time only after a buy fill; no re-entry after an exit.

### late_favorite_limit_hold

- Activation window is optional:
  - if `activation_start_time_ns > 0`, ignore signals before that timestamp
  - if `market_close_time_ns > 0`, ignore signals after that timestamp
- A signal qualifies whenever observed `signal_price >= entry_price`; no crossing logic is required.
- Trade variant uses trade price for both signal and order price.
- Quote variant uses midpoint as signal and ask as order price.
- Entry submits one GTC limit buy and then holds the position through strategy stop.
- There is no in-strategy profit target, stop loss, or timed exit. Filled positions are intentionally left open for the runner to mark to settlement.

### vwap_reversion

- There is no clock-based activation window.
- The strategy becomes eligible only after it has accumulated `vwap_window` accepted observations and the weighted size sum is positive.
- Ticks smaller than `min_tick_size` are ignored and do not enter the VWAP window.
- VWAP is computed from the rolling window of `(price, size)` points.
- Entry occurs when current observed price is at least `entry_threshold` below rolling VWAP.
- While in position, exit first checks absolute take-profit / stop-loss offsets relative to the filled entry price, then falls back to a VWAP reversion exit when price recovers to `vwap - exit_threshold`.
- Quote variant uses midpoint price and average top-of-book size as a proxy, then uses ask / ask_size for entry reference and visible-liquidity capping.

## Position Sizing Behavior

These three strategies depend on shared logic in `strategies/core.py`.

- `trade_size` is a desired quantity, not a dollar notional.
- Quantity is capped by visible liquidity when `visible_size` is available.
- Quantity is capped by available quote balance using an affordability model with a `0.97` cash buffer and the instrument taker fee.
- If there is no visible ask size, the affordability reference price is treated as worst-case `1.0` on the binary market scale rather than the last print.
- Quantity is rounded down to valid lot sizing and rejected if it falls below instrument lot-size or minimum-quantity requirements.
- `final_period_momentum` and `vwap_reversion` use market IOC entries through the shared helper.
- `late_favorite_limit_hold` uses the same quantity calculation but submits a limit GTC buy instead of a market IOC buy.

## Licensing / Attribution Notes

- The repository is mixed-license, not uniformly MIT.
- Upstream `NOTICE` explicitly lists:
  - `strategies/final_period_momentum.py`
  - `strategies/late_favorite_limit_hold.py`
  - `strategies/vwap_reversion.py`
  - `strategies/core.py`
  as LGPL-covered files with Nautilus-derived provenance.
- The extraction in this log therefore records behavior, parameter names, and implementation-neutral strategy ideas only.
- Reimplementation should avoid copying source expression, helper layout, comments, or class structure from the inspected files.

## Local Repo Change Summary

- Added this dev log only.
- No local code files changed.
- No config files changed.
- No tests were modified.
- A separate untracked file appeared during the session and was not modified:
  `docs/dev_logs/2026-04-21_deliverable-b_context-fetch.md`

## Open Questions / Blockers

- Confirm whether PolyTool wants to preserve the upstream variant split
  (`bar`, `trade`, `quote`) as separate config objects, or only preserve the
  field semantics in a unified internal schema.
- Confirm whether the worst-case `1.0` affordability assumption used when no
  visible ask is present should be preserved exactly or replaced with a
  PolyTool-native risk rule.
- Confirm whether the late-favorite strategy in PolyTool should intentionally
  depend on external settlement marking, or whether Deliverable B should define
  an explicit end-of-market exit for replay consistency.
