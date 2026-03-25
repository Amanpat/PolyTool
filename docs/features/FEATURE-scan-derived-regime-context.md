# Feature: Scan Derived Regime Context

**Spec**: `docs/specs/SPEC-0017-phase1-gate2-candidate-ranking.md`
**Status**: Shipped
**Date**: 2026-03-08
**Branch**: simtrader

---

## What this feature does

Makes `scan-gate2-candidates` treat regime and new-market context as
metadata-derived signals first, with operator labels used only as a fallback
when the classifier is weak.

### Key changes

1. `score_gate2_candidate()` now calls
   `regime_policy.classify_market_regime()` when scan metadata contains a
   usable slug/question/title/category/tag signal.
2. `scan_gate2_candidates.py` now carries local scan metadata into scoring:
   live scans pass `slug` + `question`; tape scans read `prep_meta.json`,
   `watch_meta.json`, and `meta.json` when present.
3. Ranked output now shows:
   - `Age` (`NEW <Nh>`, `<Nh>`, or `UNKNOWN`)
   - `Regime` (derived regime, operator fallback, or `UNKNOWN`)
   - `RegSrc` (`derived`, `operator`, or `UNKNOWN`)
4. Explanation output now spells out regime provenance explicitly:
   `source=<...>; derived=<...>; operator=<...>`.

---

## Changed files

| File | Change |
|------|--------|
| `packages/polymarket/market_selection/scorer.py` | Derive regime provenance from `regime_policy`; support explicit operator fallback; report age/regime unknowns honestly |
| `tools/cli/scan_gate2_candidates.py` | Thread scan metadata into scoring; show `Age` and `RegSrc` in ranked output |
| `tests/test_gate2_candidate_ranking.py` | Added coverage for derived regime, operator provenance fallback, candidate metadata pass-through, and explicit `UNKNOWN` table output |

---

## Invariants preserved

- Gate 2 pass criteria unchanged
- Gate 2 ranking weights unchanged
- Missing age/regime metadata still contributes zero positive evidence
- Manual `regime` labels are no longer implied to be the primary truth in scan output
