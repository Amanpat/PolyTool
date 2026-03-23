# Dev Log: new-market capture MarketPicker constructor fix

**Date:** 2026-03-21
**Branch:** phase-1
**Scope:** narrow wiring fix — no logic changes

---

## Root Cause

`tools/cli/capture_new_market_tapes.py::resolve_both_token_ids()` called `MarketPicker()` with
zero arguments when no `_picker_factory` override was injected. `MarketPicker.__init__` requires
two positional arguments (`gamma_client`, `clob_client`), so every production call raised:

```
TypeError: MarketPicker.__init__() missing 2 required positional arguments: 'gamma_client' and 'clob_client'
```

This caused all 300 targets in the 2026-03-21 closure attempt to be skipped with
`reason=resolve_slug failed` and `tapes_created=0`. Evidence in
`docs/dev_logs/2026-03-21_phase1_new_market_closure_attempt.md`.

---

## Files Changed

### `tools/cli/capture_new_market_tapes.py`

**Before** (`else` branch inside `resolve_both_token_ids`, ~line 136):

```python
else:
    if MarketPicker is None:
        return "", "", "MarketPicker not available (missing dependency)"
    picker = MarketPicker()
```

**After:**

```python
else:
    if MarketPicker is None:
        return "", "", "MarketPicker not available (missing dependency)"
    try:
        from packages.polymarket.gamma import GammaClient
        from packages.polymarket.clob import ClobClient
    except ImportError as ie:
        return "", "", f"GammaClient/ClobClient not available (missing dependency): {ie}"
    picker = MarketPicker(GammaClient(), ClobClient())
```

Pattern matches every other CLI entrypoint that uses `MarketPicker`:
`prepare_gate2.py`, `simtrader.py`, `watch_arb_candidates.py` — all call
`MarketPicker(GammaClient(), ClobClient())`. Lazy local imports follow the
`simtrader.py` pattern (lines 1529-1530) to avoid module-level import overhead.

### `tests/test_capture_new_market_tapes.py`

Added `test_default_path_constructs_picker_with_clients` to `TestResolveBothTokenIds`.

Regression guard: patches `sys.modules` to intercept the lazy
`from packages.polymarket.gamma import GammaClient` / `from packages.polymarket.clob import ClobClient`
imports at runtime and uses a `_CapturingPicker` spy to assert that `MarketPicker.__init__`
receives actual client instances — not a zero-arg call.

### `docs/CURRENT_STATE.md`

Updated "New-market capture execution" section to document the fix and remove it as a
Gate 2 blocker.

---

## Commands Run + Output

```
python -m pytest tests/test_capture_new_market_tapes.py -v --tb=short
# 46 passed in 0.51s

python -m pytest tests/ -x -q --tb=short
# 1 failed, 643 passed
# 1 failure: test_gate2_eligible_tape_acquisition.py::TestResolvedWatchRegime::test_default_regime_is_unknown
# Confirmed pre-existing via git stash + rerun on prior commit — not caused by this change.
```

---

## Next Manual Command

Rerun the full Phase 1 closure attempt with the fix in place:

```bash
python -m polytool capture-new-market-tapes \
  --targets config/benchmark_v1_new_market_capture.targets.json \
  --out-dir artifacts/tapes/new_market \
  --dry-run
```

Remove `--dry-run` once the dry run confirms targets resolve correctly (non-zero
`tapes_would_create` count). Expected: 5 new-market tapes created, closing the
last tape shortage category for benchmark_v1.

After tapes are created, proceed to benchmark closure:

```bash
python -m polytool close-benchmark-v1 \
  --manifest config/benchmark_v1.gap_report.json \
  --silver-dir artifacts/tapes/silver \
  --out config/benchmark_v1.tape_manifest
```
