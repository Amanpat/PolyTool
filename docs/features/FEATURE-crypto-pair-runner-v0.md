# Summary

Track 2 / Phase 1A now has a runtime shell for the crypto-pair bot:

- `python -m polytool crypto-pair-run`
- paper mode by default
- JSONL-first artifact bundles
- live scaffold behind `--live` with explicit safety gates

This packet uses the existing market discovery, opportunity scanner, paper
ledger, reference-feed contract, and accumulation engine. It does **not**
activate production order wiring or ClickHouse persistence.

# What Shipped

## Paper Runtime

Paper mode is the default runner path.

It:

- discovers BTC/ETH/SOL 5m/15m crypto pair markets
- scans YES/NO best asks
- converts quote snapshots into `PaperOpportunityObservation`
- evaluates feed safety through the accumulation engine
- generates paper intents under the Phase 1A caps
- records deterministic fills, exposure state, market rollups, and run summary

On Binance disconnect or stale feed:

- new intents are frozen
- existing state is preserved
- observations continue
- the state transition is written to `runtime_events.jsonl`

## Live Scaffold

Live mode is opt-in:

- `--live` is required
- `--confirm CONFIRM` is required at startup

The scaffold enforces:

- kill switch checked every cycle
- post-only only
- limit-only only
- no market-order path
- disconnect cancels all tracked working orders
- reconnect must become visibly healthy before new intents resume

The scaffold can run without a production client wired. In that case, order
attempts are still validated and logged with explicit reasons such as
`live_client_unconfigured`.

## JSONL Artifact Contract

Paper bundles are written under:

`artifacts/tapes/crypto/paper_runs/<YYYY-MM-DD>/<run_id>/`

Primary files:

- `run_manifest.json`
- `config_snapshot.json`
- `runtime_events.jsonl`
- `observations.jsonl`
- `order_intents.jsonl`
- `fills.jsonl`
- `exposures.jsonl`
- `settlements.jsonl`
- `market_rollups.jsonl`
- `run_summary.json`

The manifest is deterministic JSON with sorted keys and includes:

- artifact paths
- record counts
- stopped reason
- final open-pair state
- disabled ClickHouse sink contract metadata

## ClickHouse Contract

`packages/polymarket/crypto_pairs/position_store.py` defines a future
`CryptoPairClickHouseSink.write_rows(...)` protocol plus an explicit disabled
v0 contract.

v0 behavior:

- JSONL artifacts are the source of truth
- no ClickHouse writes are activated
- later writer wiring can be added without changing runner/store call sites

# Tests

Offline coverage was added for:

- paper default path
- JSONL artifact bundle creation
- live rejection without `CONFIRM`
- kill switch checks
- limit-only / no market-order path
- disconnect cancellation and reconnect resume logging

The crypto-pair slice passes:

- `tests/test_crypto_pair_scan.py`
- `tests/test_crypto_pair_paper_ledger.py`
- `tests/test_crypto_pair_run.py`
- `tests/test_crypto_pair_live_safety.py`
