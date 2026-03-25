# Dev Log: Scan Derived Regime Context

**Date:** 2026-03-08
**Branch:** simtrader
**Author:** PolyTool Contributors

---

## What was built

Adjusted the Gate 2 candidate scan path so regime/new-market context is derived
from available metadata when possible, instead of presenting manual labels as
the default truth.

### Problem

`scan-gate2-candidates` only surfaced `market["_regime"]` / `market["regime"]`
when present. That made manual labels look authoritative even when the scan
already had enough metadata to derive a stronger machine classification.

### Solution

- `scorer.py` now uses `classify_market_regime()` as the canonical regime source
  when the market metadata has a clear signal.
- Operator labels remain supported, but only as a fallback when the classifier
  returns no named regime.
- Age/new-market output is now explicit: `<Nh>`, `NEW <Nh>`, or `UNKNOWN`.
- Ranked table output now includes `RegSrc`, and explanation lines include
  `source`, `derived`, and `operator` values for the regime factor.

---

## Files changed

| File | What changed |
|------|-------------|
| `packages/polymarket/market_selection/scorer.py` | Added regime provenance fields to `Gate2RankScore`; derive regime from `regime_policy`; keep operator fallback explicit |
| `tools/cli/scan_gate2_candidates.py` | Carry live/tape metadata into scoring; add `Age` / `RegSrc` output columns; print explicit `UNKNOWN` values |
| `tests/test_gate2_candidate_ranking.py` | Added/adjusted tests for derived regime, provenance fallback, candidate metadata pass-through, and output formatting |
| `docs/specs/SPEC-0017-phase1-gate2-candidate-ranking.md` | Synced output columns and regime provenance behavior |
| `docs/features/FEATURE-scan-derived-regime-context.md` | Feature note |
| `docs/dev_logs/2026-03-08_scan_derived_regime_context.md` | This file |
| `docs/INDEX.md` | Added feature/dev-log index entries |

---

## Test results

```bash
pytest -q tests/test_market_selection.py tests/test_gate2_candidate_ranking.py
```

Result: 27 passed.
