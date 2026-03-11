# FEATURE: SimTrader — One-shot Replay, Shadow Mode, and Local UI Reports

## Summary

SimTrader graduated from a replay-only prototype into a complete local-first research loop:
- One-shot experiment execution (`quickrun`)
- Live simulated trading gate (`shadow`)
- Robust sweeps/batches for distributions
- Self-contained HTML reports (`report`) and artifact browser (`browse`)

All outputs are evidence and are written under `artifacts/simtrader/` (gitignored).

## Why this exists

Replay-first is the cheapest way to falsify ideas. Shadow mode is the realism gate that prevents replay-only optimism. A local UI makes results readable without building a full web app.

## What shipped

### One-shot workflow

`simtrader quickrun` resolves/validates a binary market, records a tape, and runs a strategy or sweep with a single command. It supports:
- Liquidity preset (`--liquidity strict`)
- Candidate listing (`--dry-run --list-candidates N`)
- Market exclusions (`--exclude-market`)
- Presets/config-json/path for strategy config

### Shadow mode (live simulated)

`simtrader shadow` runs the full strategy loop on live WS events, writing the same audited artifacts as replay, optionally recording a tape concurrently. It includes:
- Reconnect + keepalive
- Stall kill-switch (`--max-ws-stalls-seconds`)
- Run metrics and `exit_reason` in manifests/meta

### Sweeps and batch

- Sweep presets (`quick`, `quick_small`)
- Sweep summary aggregates: totals + dominant rejection counts
- Batch runner with deterministic seed, idempotent skip, leaderboard outputs
- Time-bounded batch execution (`--time-budget-seconds`)

### Local UI

- `simtrader report` generates a self-contained `report.html` for run/sweep/batch/shadow artifacts
- `simtrader browse` lists recent artifacts and opens newest report (`--open`), reusing existing reports unless `--force`

### Activeness probe

`--activeness-probe-seconds N` on `quickrun` subscribes to the WS for N seconds and counts live `price_change`/`last_trade_price` updates per token before recording begins. Use `--require-active` to skip markets that don't reach the threshold. Output shown in `--list-candidates` results.

### Artifact management

- `simtrader clean`: safe dry-run deletion of artifact folders (`--runs`, `--tapes`, `--sweeps`, `--batches`, `--shadow`). Requires explicit `--yes` to delete; prints byte counts in dry-run mode.
- `simtrader diff`: compares two run directories; prints counts (decisions/orders/fills), net PnL delta, and dominant rejection count changes; writes `diff_summary.json` to `artifacts/simtrader/diffs/`.

## Artifact contract

All runs produce audited JSONL artifacts and manifests:
- `best_bid_ask`, `decisions`, `orders`, `fills`, `ledger`, `equity_curve`, `summary`, `run_manifest`, `meta`

Tapes include raw WS frames and normalized events:
- `raw_ws.jsonl`, `events.jsonl`, `meta.json`

## Operational notes

- Many markets are one-sided and quiet; shadow mode may stall even when books exist.
- "No trades" is valid; interpret via `strategy_debug.rejection_counts`.

## Next steps

- Improve report headers (`created_at`, `exit_reason`, `run_metrics` display)
- Evidence memo ingestion (RAG) and ClickHouse/Grafana export stage
