# 2026-03-10 Track A MarketMakerV1 Default Wiring

## Goal
Ensure Track A operator entry points resolve to `market_maker_v1` when `--strategy` is omitted, while keeping explicit `--strategy market_maker_v0` support.

## Scope
- Default-resolution wiring only.
- Focused CLI/help/quickrun path updates.
- Focused regression tests for default selection and explicit v0 fallback.

## Non-goals
- No `MarketMakerV1` quote math changes.
- No risk manager changes.
- No watcher/session-pack changes.

## Changes
- `tools/cli/simtrader.py`
  - Added `DEFAULT_TRACK_A_STRATEGY = "market_maker_v1"`.
  - `simtrader run --strategy` now defaults to `market_maker_v1` (no longer required).
  - `simtrader sweep --strategy` now defaults to `market_maker_v1` (no longer required).
  - `simtrader shadow --strategy` default changed to `market_maker_v1`.
  - `simtrader quickrun` now exposes `--strategy` and defaults to `market_maker_v1`.
  - Quickrun internals now route `strategy_name` dynamically (including sweep/single-run artifact IDs and runner params).
  - Binary-arb preset injection remains conditional on `strategy_name == "binary_complement_arb"`.
  - Reproduce-command output now includes `--strategy` only when non-default and only prints `--strategy-preset` for `binary_complement_arb`.
- `polytool/__main__.py`
  - Updated SimTrader example to `market_maker_v1`.
- Tests
  - Updated/default-coverage wiring tests in:
    - `tests/test_simtrader_strategy.py`
    - `tests/test_simtrader_quickrun.py`
    - `tests/test_simtrader_shadow.py`

## Verification commands
```bash
pytest -q tests/test_simtrader_strategy.py tests/test_simtrader_quickrun.py tests/test_simtrader_shadow.py
```
