# Dev Log — 2026-04-15: Track 2 Risk Controls for Crypto-Pair Runner

## Summary

Added a fourth operator-level risk control to the crypto-pair paper runner:
`max_capital_per_window_usdc`. This completes the four-control safety envelope
for Track 2 alongside the existing kill switch, open-pairs cap, and daily-loss
cap. All controls are now surfaced in `--dry-run` preflight output.

## Motivation

The runner previously lacked a session-level capital budget ceiling. An operator
could inadvertently deploy more capital than intended across multiple settled
and open pairs within a single run. The new control enforces a hard ceiling
(operator maximum: 50 USDC) over the full session, counting both settled and
currently open intents.

## Changes Made

### `packages/polymarket/crypto_pairs/paper_runner.py`

- Added `_OPERATOR_MAX_CAPITAL_PER_WINDOW_USDC = Decimal("50")` operator ceiling
  constant alongside the existing operator caps.
- Added `max_capital_per_window_usdc: Decimal` field to `CryptoPairRunnerSettings`
  frozen dataclass with default equal to the operator ceiling.
- Added coercion and dual validation in `__post_init__`:
  - Rejects `<= 0`
  - Rejects `> _OPERATOR_MAX_CAPITAL_PER_WINDOW_USDC`
- Propagated the field through `with_artifact_base_dir()` and `to_dict()`.
- Updated `build_runner_settings()` factory to pull `max_capital_per_window_usdc`
  from the config payload.
- Added enforcement gate in `_process_opportunity()` after the daily-loss-cap
  check: records `order_intent_blocked` runtime event with
  `block_reason="capital_window_exceeded"` when
  `cumulative_committed_notional_usdc() >= max_capital_per_window_usdc`.

### `packages/polymarket/crypto_pairs/position_store.py`

- Added `cumulative_committed_notional_usdc()` method to
  `CryptoPairPositionStore`. Unlike `current_open_paired_notional_usdc()` (which
  excludes settled intents), this method sums `paired_net_cash_outflow_usdc +
  unpaired_net_cash_outflow_usdc` across ALL intents regardless of settled status.
  This is the correct measure for a session-level budget ceiling.

### `tools/cli/crypto_pair_run.py`

- Added `--max-capital-window-usdc` CLI argument (float, optional, operator
  ceiling enforced by settings validation).
- Wired the argument through both the `--dry-run` preflight path and the normal
  `main()` execution path.
- Updated `format_preflight_summary()` to display the configured capital window
  alongside the other three risk controls.

### `tests/test_crypto_pair_risk_controls.py` (new)

Nine deterministic offline tests:

1. `test_kill_switch_stops_paper_runner_before_first_intent` — verifies the
   kill switch gate fires before any intent is emitted.
2. `test_open_pairs_cap_blocks_new_intents` — verifies
   `block_reason="open_pairs_cap_reached"` when at the pair cap.
3. `test_daily_loss_cap_blocks_new_intents` — verifies
   `block_reason="daily_loss_cap_reached"` when at the loss cap.
4. `test_capital_window_exceeded_blocks_new_intents` — verifies
   `block_reason="capital_window_exceeded"` when cumulative committed notional
   reaches the window cap.
5. `test_capital_window_zero_raises_on_construction` — `ValueError` on zero cap.
6. `test_capital_window_above_ceiling_raises_on_construction` — `ValueError`
   when cap exceeds operator ceiling.
7. `test_cumulative_committed_notional_includes_settled_intents` — confirms
   cumulative method counts settled intents; open-only method does not.
8. `test_preflight_summary_shows_capital_window` — default settings show "50 USDC"
   in preflight output.
9. `test_preflight_summary_shows_configured_capital_window` — custom 25 USDC cap
   shown correctly.

## Test Results

```
tests/test_crypto_pair_risk_controls.py  9 passed
tests/test_crypto_pair_run.py            23 passed
tests/test_crypto_pair_live_safety.py    4 passed
tests/test_crypto_pair_soak_workflow.py  2 passed
```

No regressions. Total: 38 passing across the crypto-pair test surface.

## Codex Review

Tier: Recommended (strategy/execution-adjacent risk controls).
Issues found: none. Issues addressed: n/a.

## Risk Envelope — Current State

| Control                    | Mechanism                          | Block reason                 |
| -------------------------- | ---------------------------------- | ---------------------------- |
| Kill switch                | `kill_switch.txt` file             | `kill_switch`                |
| Open pairs cap             | `max_open_pairs` setting           | `open_pairs_cap_reached`     |
| Daily loss cap             | `daily_loss_cap_usdc` setting      | `daily_loss_cap_reached`     |
| Capital window (new)       | `max_capital_per_window_usdc`      | `capital_window_exceeded`    |

## Open Questions / Follow-ups

- The capital window ceiling is hard-coded to 50 USDC for v0. When real BTC/ETH/SOL
  5m/15m markets are live and a paper soak has been completed, consider whether
  this ceiling should be made configurable at the operator level (beyond the
  existing per-run CLI override).
- `cumulative_committed_notional_usdc` counts only the latest exposure snapshot per
  intent. If an intent has multiple exposure snapshots (re-hedging), only the most
  recent is counted. Verify this is the intended semantics before live deployment.
