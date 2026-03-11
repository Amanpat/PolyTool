# Dev Log: Adverse-Selection Operator Truth Surface

Date: 2026-03-10

## Summary

Tight Track A operator-truth patch only. The default `market_maker_v1` path now
surfaces whether adverse-selection protection is using the OFI proxy, a true
VPIN request, an unavailable true-VPIN sentinel, or a disabled configuration.
No adverse-selection thresholds or quote logic changed.

## What changed

- `packages/polymarket/simtrader/execution/adverse_selection.py`
  - Added a small operator truth-surface helper for `disabled`, `proxy`,
    `true_vpin`, and `unavailable` modes.
  - Added `UnavailableVPINSignal`, a no-trigger sentinel that reports
    `true_vpin_unavailable` instead of pretending true VPIN is active.

- `packages/polymarket/simtrader/strategy/facade.py`
  - Normalizes `adverse_selection.order_flow_signal` with default `"proxy"`.
  - Attaches resolved `adverse_selection_surface` metadata to `market_maker_v1`
    strategies.
  - Preserves disabled state as explicit metadata instead of dropping it.

- `packages/polymarket/simtrader/strategy/runner.py`
  - Writes `adverse_selection` truth metadata into `summary.json` and
    `run_manifest.json`, including failed-fast manifests.

- `packages/polymarket/simtrader/shadow/runner.py`
  - Writes the same `adverse_selection` truth metadata into shadow summaries
    and manifests.

- `tools/cli/simtrader.py`
  - Default Track A config now injects `order_flow_signal="proxy"`.
  - `run`, `sweep`, `quickrun`, and `shadow` print an explicit adverse-selection
    status line.
  - CLI help now states that the default is an OFI VPIN proxy and that
    `order_flow_signal="true_vpin"` surfaces the unavailable sentinel.

## Operator-visible behavior

- Default `market_maker_v1`: reports `proxy signal active (OFI VPIN proxy)`.
- Disabled config: reports `disabled`.
- `order_flow_signal="true_vpin"`: reports an unavailable sentinel and keeps the
  competing-MM withdrawal signal honest/unchanged.

## Tests

Focused tests cover:

- truth-surface mode classification
- `market_maker_v1` builder wiring for proxy, disabled, and unavailable sentinel
- CLI truth surface for `run`, `quickrun`, and `shadow`
- run-manifest truth metadata emission

## Explicit non-goals

- no signal math changes
- no `MarketMakerV1` quote logic changes
- no watcher/session-pack work
- no broad cleanup
