# Dev Log: Phase 1A Crypto Pair Backtest Harness v0

**Date:** 2026-03-23
**Scope:** GSD quick-019 — add deterministic backtest harness for the crypto-pair bot

## Objective

Add a deterministic offline evaluation harness for the Phase 1A crypto-pair
strategy.  The harness should allow replay of historical or synthetic quote
observations through the existing fair-value and accumulation logic, producing
skip/intent count metrics and cost statistics.  This is the pre-requisite
evaluation artifact before committing to a 24-48h paper soak.

## What Was Built

Four new files plus one update:

### packages/polymarket/crypto_pairs/backtest_harness.py

Pure-function replay engine.  No network calls, no filesystem writes, no imports
from the live-execution layer.

Key types:
- `BacktestObservation` — frozen dataclass, one quote snapshot record
- `BacktestResult` — mutable aggregation of skip/intent/cost metrics + `to_dict()`
- `BacktestHarness` — stateless replay loop, `run(list[BacktestObservation]) -> BacktestResult`

The harness builds synthetic `ReferencePriceSnapshot` objects for the feed gate,
calls `estimate_fair_value()` when all three fair-value parameters are present, and
routes each `AccumulationIntent` to the appropriate skip counter or intent counter.

### tests/test_crypto_pair_backtest.py

22 deterministic offline tests.  Written RED before implementation (TDD).

Covers all skip categories: feed_stale_skips, quote_skips, hard_rule_skips,
soft_rule_skips.  Also covers intents_generated, partial_leg_intents,
completed_pairs_simulated, avg_completed_pair_cost, est_profit_per_completed_pair,
determinism, JSON serializability, and config snapshot presence.

### tools/cli/crypto_pair_backtest.py

CLI entrypoint with `build_parser()` and `main(argv)`.  Arguments:
- `--input PATH` (required) — JSONL observation file
- `--output PATH` — artifact base dir (default: `artifacts/crypto_pairs/backtests`)
- `--symbol BTC|ETH|SOL` (append) — filter by symbol
- `--market-duration 5|15` (append) — filter by duration
- `--run-id STR` — optional explicit run ID override

Writes `manifest.json`, `summary.json`, and `report.md` to
`<output>/<YYYY-MM-DD>/<run_id>/`.

### polytool/__main__.py (updated)

Registered `crypto-pair-backtest` command:
- Added `crypto_pair_backtest_main = _command_entrypoint("tools.cli.crypto_pair_backtest")`
- Added `"crypto-pair-backtest": "crypto_pair_backtest_main"` to `_COMMAND_HANDLER_NAMES`
- Added usage line under the Crypto Pair Bot section in `print_usage()`

### docs/features/FEATURE-crypto-pair-backtest-v0.md

Feature doc with full input contract, output artifact schema, metrics definitions,
gate hierarchy, soft_rule_skips reachability note, constraints, CLI examples,
programmatic API, and v0 limitations.

## Design Decisions

### BacktestObservation includes yes_accumulated_size / no_accumulated_size

The accumulation engine's `_select_legs()` uses partial-pair state to focus on the
missing leg.  The `soft_rule_blocked_all_legs` skip reason is only reachable when
the engine is in a partial state (e.g., `yes_only`) and the remaining leg fails the
soft rule.

Without accumulated size fields, `soft_rule_blocked_all_legs` is mathematically
unreachable in stateless replay: the complement constraint (`fair_yes + fair_no = 1`)
means blocking both legs requires `yes_ask + no_ask > 1.0`, which always triggers
the hard rule first.

Adding `yes_accumulated_size` and `no_accumulated_size` (default 0.0) to
`BacktestObservation` allows test authors and real replay scenarios to simulate
partial-pair states explicitly.

### Fresh feed snapshot uses sentinel price=1.0 when underlying_price is None

The feed gate only cares about `is_stale` and `connection_state`.  The price field
is not used by the freeze-gate logic — it is only used by `estimate_fair_value()`,
which is called separately.  Using `price=1.0` as a safe non-None sentinel ensures
the feed gate passes while avoiding special-casing `None` in the snapshot.

### Soft fair-value filter disabled when any of the three fair-value params are absent

All three are required: `underlying_price`, `threshold`, `remaining_seconds`.  If
any is missing, `_compute_fair_values()` returns `(None, None)` and the soft rule
vacuously passes both legs.

### Artifact directory layout mirrors position_store pattern

`<output>/<YYYY-MM-DD>/<run_id>/` matches the existing `artifacts/crypto_pairs/`
directory conventions from `position_store.py`.

## Test Results

```
cd "D:/Coding Projects/Polymarket/PolyTool"
python -m pytest tests/test_crypto_pair_backtest.py tests/test_crypto_pair_accumulation_engine.py tests/test_crypto_pair_fair_value.py -q --tb=short
```

22 + existing crypto-pair tests — all passing, 0 failures.

Full suite (excluding known pre-existing failures in test_gate2_eligible_tape_acquisition.py
and test_new_market_capture.py):

```
python -m pytest tests/ -q --tb=short
2496 passed, 8 pre-existing failures (unrelated to this change), 25 warnings
```

## Spot-Check: Synthetic JSONL Run

```bash
python -m polytool crypto-pair-backtest --input test_obs.jsonl --output /tmp/bt_test
```

Input: 3 observations — one clean (0.47+0.48=0.95), one hard skip (0.51+0.51=1.02),
one stale feed.

Output:
```
[crypto-pair-backtest] run_id        : dbaa2b10f6a6
[crypto-pair-backtest] observations  : 3
[crypto-pair-backtest] intents        : 1
[crypto-pair-backtest] completed_pairs: 1
[crypto-pair-backtest] artifact_dir  : /tmp/bt_test/2026-03-23/dbaa2b10f6a6
```

summary.json confirmed: feed_stale_skips=1, hard_rule_skips=1, intents_generated=1,
completed_pairs_simulated=1, avg_completed_pair_cost=0.95,
est_profit_per_completed_pair=0.05.  Artifacts: manifest.json, summary.json, report.md.

## Open Questions / Next Steps

1. **Feed real scanner output**: The scanner (`crypto-pair-scan`) currently emits
   human-readable table output, not JSONL.  To feed historical scanner output into
   the backtest harness, we need a JSONL emit mode on `crypto-pair-scan`.

2. **Historical quote data**: The harness is ready to process historical observations
   but no automated pipeline exists to extract quote snapshots from ClickHouse into
   JSONL format.  This would be a natural follow-on once the paper run is in progress.

3. **Fee-adjusted metrics**: v0 pair cost metrics are raw ask sums.  A future
   improvement could apply `maker_rebate_bps` from the config to estimate
   fee-adjusted breakeven cost.

4. **Pre-paper-soak validation**: Before the first paper soak, run the harness
   against at least one full day of synthetic observations covering all three symbols
   and both durations.  Target: `intents_generated / observations_total >= 5%` with
   `avg_completed_pair_cost <= 0.95`.
