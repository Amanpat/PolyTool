# Gate 2 Sweep Failure Diagnosis (2026-03-06)

## Run under diagnosis
- Gate artifact: `artifacts/gates/sweep_gate/gate_failed.json`
- Gate timestamp: `2026-03-06T00:36:25.247783+00:00`
- Sweep dir: `artifacts/simtrader/sweeps/20260306T003627Z_sweep_bitboy-convicted_quick_8dfc0f9e`
- Market: `bitboy-convicted`
- Strategy: `binary_complement_arb` preset `sane`
- Result: `0/24` profitable scenarios (`0.0%`, threshold `70%`)

## Files inspected
- `tools/gates/close_sweep_gate.py`
- `artifacts/gates/sweep_gate/gate_failed.json`
- `artifacts/simtrader/sweeps/20260306T003627Z_sweep_bitboy-convicted_quick_8dfc0f9e/sweep_manifest.json`
- `artifacts/simtrader/sweeps/20260306T003627Z_sweep_bitboy-convicted_quick_8dfc0f9e/sweep_summary.json`
- `artifacts/simtrader/sweeps/20260306T003627Z_sweep_bitboy-convicted_quick_8dfc0f9e/runs/*/{summary.json,run_manifest.json,decisions.jsonl,orders.jsonl,fills.jsonl,ledger.jsonl,equity_curve.jsonl,best_bid_ask.jsonl}`
- `artifacts/simtrader/tapes/20260306T003627Z_tape_bitboy-convicted_64fd7c95/{meta.json,events.jsonl,raw_ws.jsonl}`
- `tools/cli/simtrader.py` (quickrun and quick sweep preset path)
- `packages/polymarket/simtrader/sweeps/runner.py`
- `packages/polymarket/simtrader/strategies/binary_complement_arb.py`
- `packages/polymarket/simtrader/strategy_presets.py`
- `packages/polymarket/simtrader/market_picker.py`
- `packages/polymarket/simtrader/strategy/runner.py`
- `packages/polymarket/simtrader/broker/{sim_broker.py,fill_engine.py,latency.py,rules.py}`
- `packages/polymarket/simtrader/orderbook/l2book.py`
- `packages/polymarket/simtrader/portfolio/{ledger.py,fees.py,mark.py}`
- Validation tests checked and run:
  - `tests/test_simtrader_sweep.py::test_sweep_fee_override_changes_fees_and_net_profit`
  - `tests/test_simtrader_strategy.py::test_no_trade_ledger_has_initial_final_snapshots`
  - `tests/test_simtrader_strategy.py::test_end_to_end_buy_fills_at_ask`

## Scenario summary
- Sweep matrix is correct: `4 fee rates x 3 cancel latencies x 2 mark methods = 24`.
- All 24 scenarios produced:
  - `decisions_count = 0`
  - `orders = 0`
  - `fills = 0`
  - `net_profit = 0`
- Aggregate rejections:
  - `insufficient_depth_no = 144`
  - `insufficient_depth_yes = 120`
  - `no_bbo = 24`
  - `stale_or_missing_snapshot = 24`
- Per-scenario rejection pattern is identical:
  - `no_bbo=1`, `stale_or_missing_snapshot=1`, `insufficient_depth_yes=5`, `insufficient_depth_no=6`

## Failure buckets (24 scenarios)
| Primary reason | Count | Scenarios |
|---|---:|---|
| No-fill due depth gate before order submission | 24 | `fee{0,50,100,200}-cancel{0,2,5}-{bid,midpoint}` |
| Fee/slippage assumption killed EV | 0 | None |
| Latency degradation | 0 | None |
| Inventory/risk gate (`min/max_notional`) | 0 | None |
| Harness/accounting bug | 0 | None found |

## Why all 24 fail
1. Strategy config (`sane`) requires `max_size=50` shares per leg.
2. Tape top-of-book liquidity is below that on both sides:
   - YES best ask: `0.175` with size `1.88`
   - NO best ask: `0.84` with size `15`
3. Entry logic checks best-ask size before edge/fee checks; it returns early on insufficient depth, so no orders are ever submitted.
4. Because no orders were submitted, scenario knobs (`fee_rate_bps`, `cancel_latency_ticks`, `mark_method`) never become operative.

Secondary observation:
- Even without depth gating, the observed top-of-book asks imply negative edge:
  - `yes_ask + no_ask = 1.015`
  - Threshold for entry with buffer `0.01` is `< 0.99`
  - So this tape does not show executable arb edge at top-of-book anyway.

## Assumptions in this sweep path
- Fees: scenario override `fee_rate_bps` in `{0,50,100,200}`; fee model is Decimal deterministic (`compute_fill_fee`) with conservative default only when unspecified.
- Fill/slippage model: walk-the-book on actual visible levels only; no synthetic price improvement or extra slippage model.
- Queue model: none (no queue-position simulation); fills happen when levels are available and limit is marketable.
- Latency model: event-tick based; submit latency fixed `0`, cancel latency per scenario `{0,2,5}`.
- Inventory/risk: strategy-level gates (`max_size`, min/max notional, legging policy). In this run only `max_size` interacted (via depth gating); min/max notional gates did not trigger.

## Net PnL accounting verdict
Net PnL accounting looks correct for this run.

Evidence:
- No broker lifecycle events were generated (`orders/fills=0`), so ledger emitted expected synthetic `initial` and `final` snapshots with unchanged cash/equity.
- `summary.json` values are internally consistent: `realized=0`, `unrealized=0`, `fees=0`, `net=0`.
- Targeted regression tests for sweep fee sensitivity, no-trade ledger behavior, and end-to-end fill accounting all passed (`3 passed`).

## Gate 2 verdict
Current strategy genuinely fails Gate 2 on this recorded tape.  
`0/24` is explained by non-executable top-of-book depth (primary) with no positive top-of-book edge (secondary), not by a sweep harness or PnL accounting defect.

## Recommended next step
Do not soften Gate 2 thresholds.  
Run Gate 2 on a tape/market that is executable for this strategy's configured size, and add a quick pre-sweep eligibility check (diagnostic only) that requires:
- both YES/NO best-ask sizes at or above strategy `max_size`, and
- at least one tick where `yes_ask + no_ask < 1 - buffer`.

This keeps the gate strict while preventing non-actionable 24-scenario sweeps.
