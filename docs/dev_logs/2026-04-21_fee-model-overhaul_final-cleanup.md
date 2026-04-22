# Fee Model Overhaul — Final Cleanup (Deliverable A Merge-Ready)

**Date:** 2026-04-21
**Branch:** main
**Scope:** Close the three Codex final-review blockers; no new fee semantics added.

---

## Codex Blockers Closed

### Blocker 1 — `_shadow()` CLI propagation not directly tested

**Problem:** `TestShadowFeeCategory` only instantiated `ShadowRunner` directly. A regression
where `_shadow()` stopped calling `load_fee_config()` or stopped forwarding `fee_category`/
`fee_role` to `ShadowRunner` would pass all existing tests.

**Fix:** Added `TestShadowCLIPropagation.test_shadow_cli_propagates_fee_category_and_role` in
`tests/test_simtrader_shadow.py`. The test calls `main(["shadow", ...])` with a strategy config
containing `fees.market_category = "sports"`, mocks all network-touching layers (TargetResolver,
MarketPicker, ClobClient, GammaClient, `_build_strategy`), replaces `ShadowRunner` with a
capturing stub, and asserts the stub received `fee_category="sports"` and `fee_role="taker"`.

### Blocker 2 — `_write_failure_artifacts()` not directly tested

**Problem:** The success-path manifest tests exercised `_write_artifacts()` only. The failure
artifact writer was patched (null instead of "default(200)", fee_category/fee_role added) but
no test exercised it.

**Fix:** Added `test_failure_manifest_truthfulness` in `tests/test_simtrader_strategy.py`.
Triggers the `_RUN_QUALITY_INVALID` path by passing a `BinaryComplementArb` strategy that
requires both YES and NO asset events, but only a single-asset tape. Asserts the resulting
`run_manifest.json` has `fee_rate_bps: null`, `fee_category: "sports"`, `fee_role: "taker"`,
`run_quality: "invalid"`, and no `"default(200)"` string.

### Blocker 3 — `simtrader trade` emitted misleading `"default(200)"` metadata

**Problem:** `_trade()` wrote `"fee_rate_bps": "default(200)"` to `run_manifest.json` and
printed `"default (200)"` to stderr when `fee_rate_bps` was not explicitly provided. The `trade`
subcommand is a standalone scripted-order runner (no strategy config, no market category), so
it had no path to derive a fee category — but the legacy string was still misleading about what
fee was actually applied.

**Fix:** Changed `run_manifest.json` to write `"fee_rate_bps": null` (not the misleading string)
and added `"fee_category": null, "fee_role": null` to `portfolio_config` for schema consistency.
Changed the stderr print from `"default (200)"` to `"null (ledger default)"`. The ledger's
internal default (200 bps) still applies at runtime; the manifest now truthfully signals that
no explicit bps was configured by the operator.

---

## Files Changed

| File | Change |
|---|---|
| `tools/cli/simtrader.py` | `_trade()`: manifest `fee_rate_bps` → null; add `fee_category/fee_role: null`; stderr print fixed |
| `tests/test_simtrader_shadow.py` | Added `TestShadowCLIPropagation` (1 test) — CLI-level shadow propagation proof |
| `tests/test_simtrader_strategy.py` | Added `test_failure_manifest_truthfulness` (1 test) — failure artifact truthfulness proof |

---

## Commands Run

```
python -m polytool --help
→ exit 0; CLI renders cleanly

python -m pytest tests/test_simtrader_portfolio.py tests/test_simtrader_strategy.py \
    tests/test_simtrader_shadow.py tests/test_simtrader_shadow_probe.py -q --tb=short
→ 202 passed in 2.24s
```

---

## Scoped Exclusions

- `simtrader trade` does not pass `fee_category` to `PortfolioLedger` — this is intentional.
  `trade` is a scripted single-order tool with no strategy config; there is no market context
  to derive a category from. The manifest now records `null` for both `fee_category` and
  `fee_role` (truthful), and the ledger's internal default (200 bps taker) applies.
- `fee_role="taker"` is hardcoded at all CLI sites — Deliverable B will make this dynamic.
- Studio UI does not expose `fee_category`/`fee_role` inputs — deferred.

---

## Merge-Ready Statement

**Deliverable A is merge-ready pending a final Codex pass.**

All three blockers from the Codex final-review are now closed:
1. CLI shadow propagation — proven by `TestShadowCLIPropagation`.
2. Failure manifest truthfulness — proven by `test_failure_manifest_truthfulness`.
3. `simtrader trade` operator-facing metadata — no longer misleading (`null`, not `"default(200)"`).

Targeted suite: **202 passed, 0 failed**.
CLI smoke test: **exit 0**.
Not pushed to main.
