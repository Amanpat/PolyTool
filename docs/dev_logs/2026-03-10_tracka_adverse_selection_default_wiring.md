# Dev Log: Track A Adverse-Selection Default Wiring

**Date:** 2026-03-10
**Branch:** codex/tracka-adverse-selection-default-wiring

## Summary

Wired the adverse-selection guard into the normal Track A `market_maker_v1`
operator path so omitted-strategy V1 flows now construct the guard by default
instead of leaving it as a library-only feature.

## What changed

### `packages/polymarket/simtrader/strategy/facade.py`

- Added a small strategy wrapper for `market_maker_v1` that:
  - builds `AdverseSelectionGuard` from top-level `strategy_config.adverse_selection`
  - defaults the guard to enabled when the key is omitted
  - suppresses only `submit` intents when the guard blocks
  - preserves `cancel` intents
  - exposes `rejection_counts["adverse_selection"]` for existing run/shadow artifacts
- Added explicit config handling:
  - `adverse_selection=False` or `{"enabled": false}` disables the wrapper
  - `adverse_selection` on non-`market_maker_v1` strategies raises a config error

### `tools/cli/simtrader.py`

- Added one helper that injects an explicit top-level
  `{"adverse_selection": {"enabled": true}}` block into default
  `market_maker_v1` operator configs for:
  - `simtrader run`
  - `simtrader sweep`
  - `simtrader quickrun`
  - `simtrader shadow`
- Updated help text on the strategy-config flags to document the explicit disable path:
  `adverse_selection.enabled=false`

### Tests

- Extended run/sweep/quickrun/shadow default tests to assert the default guard config is present.
- Extended explicit `market_maker_v0` tests to assert no adverse-selection config is injected.
- Added facade-level regression tests proving:
  - `market_maker_v1` builds with the guard by default
  - the guard can be explicitly disabled
  - non-V1 strategies reject `adverse_selection` config
  - a constructed guarded `market_maker_v1` actually suppresses submit intents after OFI trigger

## Scope notes

- No adverse-selection signal math changed.
- No `MarketMakerV1` quote logic changed.
- No watcher/session-pack work was touched.

## Tests run

```bash
pytest -q tests/test_adverse_selection.py tests/test_simtrader_strategy.py tests/test_simtrader_quickrun.py tests/test_simtrader_shadow.py
```
