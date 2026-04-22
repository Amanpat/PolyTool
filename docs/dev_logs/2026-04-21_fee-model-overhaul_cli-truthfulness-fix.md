# Fee Model Overhaul — CLI Truthfulness Fix (run + sweep)

**Date:** 2026-04-21
**Branch:** main
**Scope:** Close the final two Codex merge-gate blockers for Deliverable A.

---

## Codex Blockers Closed

### Blocker 1 — `simtrader run` printed `default (200)` while category-aware fees were in effect

**Problem:** The `load_fee_config()` call in `_run()` was positioned *after* the operator-facing
stderr print. The print used only `fee_rate_bps`, so it always fell through to `'default (200)'`
even when a strategy config contained `fees.market_category` and category-aware ledger routing
would actually be used.

**Fix:** Moved the `load_fee_config()` block to before the fee-rate-bps print. Replaced the
single ternary with a three-way label:
- `fee_category` set → `"category-aware ({fee_category}/taker)"`
- `fee_rate_bps` explicitly set (no category) → the bps value as a string
- neither set → `"null (ledger default)"`

File: `tools/cli/simtrader.py` — `_run()`, around line 1172.

### Blocker 2 — `simtrader sweep` had the same operator-facing contradiction

**Problem:** Identical structure: `load_fee_config()` was called after the misleading print
in `_sweep()`.

**Fix:** Same reorder + three-way label applied to `_sweep()`.

File: `tools/cli/simtrader.py` — `_sweep()`, around line 1341.

---

## Files Changed

| File | Change |
|---|---|
| `tools/cli/simtrader.py` | `_run()`: move `load_fee_config()` before print; truthful three-way `_fee_label` |
| `tools/cli/simtrader.py` | `_sweep()`: same reorder + three-way `_fee_label` |
| `tests/test_simtrader_strategy.py` | Added `test_cli_run_fee_label_category_aware` |
| `tests/test_simtrader_strategy.py` | Added `test_cli_sweep_fee_label_category_aware` |

---

## Commands Run

```
python -m pytest tests/test_simtrader_strategy.py tests/test_simtrader_shadow.py \
    tests/test_simtrader_portfolio.py -q --tb=short
→ 200 passed, 0 failed in 2.17s
```

---

## Scoped Exclusions

- No fee-model semantics changed. The actual ledger routing is unchanged; only the
  operator-facing stderr label was fixed to reflect the real execution path.
- `fee_role="taker"` is still hardcoded at all CLI sites — Deliverable B will make this dynamic.
- Studio UI does not expose `fee_category`/`fee_role` inputs — deferred.

---

## Deliverable A Merge-Ready Statement

All five Codex blockers across both cleanup passes are now closed:

1. CLI shadow propagation — `TestShadowCLIPropagation` (previous pass)
2. Failure manifest truthfulness — `test_failure_manifest_truthfulness` (previous pass)
3. `simtrader trade` operator metadata — `null`, not `"default(200)"` (previous pass)
4. `simtrader run` operator stderr — `"category-aware (…)"` when category in effect (this pass)
5. `simtrader sweep` operator stderr — `"category-aware (…)"` when category in effect (this pass)

Targeted suite: **200 passed, 0 failed**.
Not pushed to main.

---

## Codex Review Summary

- Tier: skip (CLI formatting / operator output only; no execution logic changed)
- Blocking issues found: 0
- Files changed are in the "Skip" category per CLAUDE.md Codex review policy.
