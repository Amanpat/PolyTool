# Feature: Crypto Pair Backtest Harness v0

## Purpose and Scope

The backtest harness is a deterministic offline evaluation tool for the Phase 1A
crypto-pair bot strategy.  It replays historical or synthetic quote observations
through the same fair-value and accumulation logic used by the live bot, producing
skip/intent counts and cost metrics without any network calls or live-execution
dependencies.

Primary use: pre-paper-soak evaluation.  Before committing to a 24-48h paper run,
use the harness to confirm the strategy behaves as expected on a set of historical
or synthetic observations.  The harness can also validate that operator-tuned config
thresholds produce the intended skip/intent balance.

## Input Contract

Each record in the JSONL input file is a JSON object with the following fields.

| Field | Type | Required | Default | Description |
| ----- | ---- | -------- | ------- | ----------- |
| `symbol` | string | yes | — | Asset symbol: "BTC", "ETH", or "SOL" |
| `duration_min` | int | yes | — | Market expiry duration in minutes: 5 or 15 |
| `market_id` | string | yes | — | Unique market identifier (slug or condition_id) |
| `yes_ask` | float or null | no | null | Best ask price for YES leg.  Null triggers a quote_skip. |
| `no_ask` | float or null | no | null | Best ask price for NO leg.  Null triggers a quote_skip. |
| `underlying_price` | float or null | no | null | Spot price for fair-value computation.  Null disables the soft fair-value filter. |
| `threshold` | float or null | no | null | Market resolution threshold.  Null disables the soft fair-value filter. |
| `remaining_seconds` | float or null | no | null | Time to expiry in seconds.  Null disables the soft fair-value filter. |
| `feed_is_stale` | bool | no | false | When true, injects a stale feed snapshot, forcing ACTION_FREEZE (feed_stale_skip). |
| `yes_accumulated_size` | float | no | 0.0 | Simulated already-accumulated YES size.  Set to a positive value to enter yes_only partial state, where the engine focuses only on the NO leg. |
| `no_accumulated_size` | float | no | 0.0 | Simulated already-accumulated NO size.  Analogous to yes_accumulated_size. |
| `timestamp_iso` | string or null | no | null | ISO timestamp string, preserved in manifest but not used for logic. |

Example record:
```json
{"symbol":"BTC","duration_min":5,"market_id":"mkt-btc-5m","yes_ask":0.47,"no_ask":0.48,"underlying_price":60000,"threshold":62000,"remaining_seconds":300,"feed_is_stale":false}
```

## Output Artifacts

Artifacts are written to `<output_base>/<YYYY-MM-DD>/<run_id>/` where
`output_base` defaults to `artifacts/crypto_pairs/backtests/`.

### manifest.json

Full context record.  Contains:
- `run_id`, `input_path`, `observations_total`, `filters_applied`, `generated_at`
- `artifact_dir` — absolute path to artifact directory
- `result` — full `BacktestResult.to_dict()` payload

### summary.json

Machine-readable result only (`BacktestResult.to_dict()`).  Suitable for
programmatic parsing by dashboards or follow-on analysis tools.

### report.md

Human-readable Markdown report.  Contains a run metadata header, a metrics table,
the config parameters used, and a footer note on fill assumptions.

## Metrics Definitions

| Metric | What it counts |
| ------ | -------------- |
| `observations_total` | All records processed (after filter) |
| `feed_stale_skips` | Records where `feed_is_stale=true` caused ACTION_FREEZE |
| `safety_skips` | Reserved for future safety gate (always 0 in v0) |
| `quote_skips` | Records missing YES or NO ask price |
| `hard_rule_skips` | Records where YES_ask + NO_ask > `target_pair_cost_threshold` |
| `soft_rule_skips` | Records that passed the hard rule but soft fair-value filter blocked all eligible legs |
| `intents_generated` | Records that produced ACTION_ACCUMULATE |
| `partial_leg_intents` | Intents where only one leg was selected (partial pair) |
| `completed_pairs_simulated` | Intents where both YES and NO legs were selected |
| `avg_completed_pair_cost` | Mean (YES_ask + NO_ask) for completed-pair intents; null if zero |
| `est_profit_per_completed_pair` | Mean (1.0 - pair_cost) for completed-pair intents; null if zero |

### Skip priority (gate hierarchy)

When an observation triggers multiple conditions, only the first gate applies:

1. Feed gate (feed_stale) → `feed_stale_skips`
2. Quote gate (missing ask) → `quote_skips`
3. Hard pair-cost rule (pair > threshold) → `hard_rule_skips`
4. Soft fair-value rule (both eligible legs blocked) → `soft_rule_skips`
5. All gates pass → `intents_generated`

### Note on soft_rule_skips reachability

In the default stateless configuration (zero accumulated sizes), `soft_rule_skips`
requires `yes_ask > fair_yes AND no_ask > fair_no`.  Because the lognormal model
enforces `fair_yes + fair_no = 1.0`, this implies `yes_ask + no_ask > 1.0`, which
exceeds the default 0.97 hard threshold.  Consequently `soft_rule_skips` will
typically be 0 in stateless replays.

To exercise soft_rule_skips, set `yes_accumulated_size > 0` (yes_only partial state)
and set `no_ask > fair_no` with `yes_ask + no_ask <= 0.97`.

## Constraints

- No network calls of any kind.
- No ClickHouse or database reads.
- No imports from `live_runner`, `live_execution`, or any execution layer.
- Fill assumptions are paper-style: assumes posted maker orders fill at ask price.
- The harness does not simulate order books, partial fills, or timing effects.
- All config uses `build_default_paper_mode_config()` unless a custom config is
  passed to `BacktestHarness()` directly (programmatic use only).

## CLI Invocation

```bash
# Run all observations
python -m polytool crypto-pair-backtest --input observations.jsonl

# Filter to BTC 5-minute markets only
python -m polytool crypto-pair-backtest \
  --input observations.jsonl \
  --symbol BTC \
  --market-duration 5

# Custom output directory and explicit run_id
python -m polytool crypto-pair-backtest \
  --input observations.jsonl \
  --output /data/backtests \
  --run-id my-run-001
```

## Programmatic Use

```python
from packages.polymarket.crypto_pairs.backtest_harness import (
    BacktestHarness, BacktestObservation,
)

observations = [
    BacktestObservation(
        symbol="BTC", duration_min=5, market_id="mkt-1",
        yes_ask=0.47, no_ask=0.48,
    ),
]
result = BacktestHarness().run(observations)
print(result.to_dict())
```

## Known Limitations (v0)

- No real-fill simulation: each observation is evaluated independently.  The harness
  does not carry accumulated positions across observations (use `yes_accumulated_size`
  / `no_accumulated_size` per observation to simulate partial state explicitly).
- No time-series dependency: observations are treated as independent snapshots.
- No fee modelling: pair cost metrics are raw ask sums without rebate adjustment.
- No market-level filtering: all observations with valid `symbol` and `duration_min`
  fields are processed regardless of which market they belong to.
- Historical JSONL input must be prepared externally (e.g., from scanner output or
  a manual export).  No automatic data-fetch integration exists in v0.
