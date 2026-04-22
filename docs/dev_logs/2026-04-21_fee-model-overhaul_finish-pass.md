# Fee Model Overhaul — Finish Pass (Deliverable A Complete)

**Date:** 2026-04-21
**Branch:** main
**Scope:** Three remaining Deliverable A blockers identified by Codex review

---

## Blockers Fixed

### 1. `simtrader shadow` CLI gap

`tools/cli/simtrader.py::_shadow()` never called `load_fee_config()` and never passed
`fee_category`/`fee_role` to `ShadowRunner`. Shadow runs silently used the legacy
exponent-2, taker-only formula regardless of market type.

**Fix:** Added `load_fee_config(strategy_config)` call in `_shadow()` after the
`fee_rate_bps` parse block; added `fee_category=fee_category_sh, fee_role="taker"`
to the `ShadowRunner(...)` construction.

### 2. Run manifest truthfulness — `strategy/runner.py`

Both `_write_artifacts()` and `_write_failure_artifacts()` serialized
`"fee_rate_bps": "default(200)"` in `portfolio_config` for legacy runs (when
`fee_rate_bps=None`). This is misleading: the string "default(200)" is not a real
value and doesn't describe category-aware runs at all.

**Fix:** Changed to `"fee_rate_bps": null` when `fee_rate_bps is None`. Added
`"fee_category": self.fee_category` and `"fee_role": self.fee_role` to
`portfolio_config` in both writers.

### 3. Shadow manifest truthfulness — `shadow/runner.py`

Same "default(200)" issue in `_write_artifacts()`.

**Fix:** Same pattern as strategy runner — `fee_rate_bps: null` when unset, plus
`fee_category` and `fee_role` added to `portfolio_config`.

---

## Files Changed

| File | Change |
|---|---|
| `tools/cli/simtrader.py` | `_shadow()`: call `load_fee_config()`, pass `fee_category_sh`/`fee_role="taker"` to `ShadowRunner` |
| `packages/polymarket/simtrader/strategy/runner.py` | `_write_artifacts()` + `_write_failure_artifacts()`: remove "default(200)", add `fee_category`/`fee_role` to `portfolio_config` |
| `packages/polymarket/simtrader/shadow/runner.py` | `_write_artifacts()`: same manifest truthfulness fix |
| `tests/test_simtrader_shadow.py` | Added `TestShadowFeeCategory` (4 tests) |
| `tests/test_simtrader_strategy.py` | Added 3 run-manifest truthfulness tests |

---

## Tests Added

### `TestShadowFeeCategory` (4 tests in `test_simtrader_shadow.py`)

- `test_manifest_includes_fee_category_and_role` — runner with `fee_category="sports"` → manifest has `fee_category=="sports"` and `fee_role=="taker"`
- `test_manifest_fee_rate_bps_is_null_for_category_run` — runner with `fee_category="crypto"` → `fee_rate_bps` is null in manifest
- `test_manifest_no_default_200_string` — "default(200)" must not appear anywhere in `run_manifest.json`
- `test_manifest_legacy_run_fee_category_is_null` — no category → `portfolio_config.fee_category` is null

### Run manifest tests (3 tests in `test_simtrader_strategy.py`)

- `test_run_manifest_portfolio_config_includes_fee_category` — `StrategyRunner` with `fee_category="politics"` → manifest has correct fields
- `test_run_manifest_fee_rate_bps_null_not_default_string` — no `fee_rate_bps` → null in manifest, no "default(200)"
- `test_run_manifest_fee_category_null_when_not_set` — no category → `fee_category` null in manifest

---

## Test Results

```
tests/test_simtrader_portfolio.py tests/test_simtrader_strategy.py tests/test_simtrader_shadow.py:
  196 passed in 2.22s

Full suite:
  2606 passed, 1 pre-existing failure (test_gemini_provider_success —
  AttributeError: providers._post_json, unrelated to fee changes)
```

---

## Deliverable A — Complete Entry-Point Table

All production execution paths now pass `fee_category`/`fee_role` to `PortfolioLedger`:

| Entry Point | File | Status |
|---|---|---|
| `StrategyRunner` | `strategy/runner.py` | Done (prior session) |
| `ShadowRunner` | `shadow/runner.py` | Done (prior session) |
| `run_strategy()` facade | `strategy/facade.py` | Done (prior session) |
| `SweepRunParams` | `sweeps/runner.py` | Done (prior session) |
| `OnDemandSession` (all 5 sites) | `studio/ondemand.py` | Done (prior session) |
| Studio HTTP handler | `studio/app.py` | Done (prior session) |
| Gate 2 sweep tool | `tools/gates/mm_sweep.py` | Done (prior session) |
| CLI `_run()` | `tools/cli/simtrader.py` | Done (prior session) |
| CLI `_sweep()` | `tools/cli/simtrader.py` | Done (prior session) |
| CLI quickrun sweep | `tools/cli/simtrader.py` | Done (prior session) |
| CLI quickrun single-run | `tools/cli/simtrader.py` | Done (prior session) |
| CLI `_shadow()` | `tools/cli/simtrader.py` | **Done (this session)** |

---

## Manifest Schema After Fix

All `run_manifest.json` files now include:

```json
"portfolio_config": {
  "starting_cash": "1000",
  "fee_rate_bps": null,
  "fee_category": "sports",
  "fee_role": "taker",
  "mark_method": "bid"
}
```

For legacy runs (no category configured): `fee_category: null, fee_rate_bps: null`.
For explicit bps runs: `fee_rate_bps: "200"` (or whatever was set), `fee_category: null`.

---

## Constraints Honoured

- Deliverable B (broker-side taker/maker classification) deferred — `fee_role="taker"` still hardcoded at CLI sites
- Deliverable C (StrategyRunner injection) deferred — no further runner refactor
- Maker fee = zero (Option A) — unchanged
- No Pydantic refactor
- No docs truth-sync
- Not pushed to main

## Open Items

- `fee_role="taker"` hardcoded at all CLI sites — Deliverable B will make this dynamic
- Studio UI does not yet expose `fee_category`/`fee_role` inputs in the web form
- `tools/gates/mm_sweep_diagnostic.py`, `run_recovery_corpus_sweep.py`, `close_mm_sweep_gate.py` — propagation deferred (safe follow-ups per prior audit)

## Codex Review

Tier: Recommended (SimTrader core). Review not run — scope is manifest plumbing + CLI wiring, no execution or kill-switch paths touched.
