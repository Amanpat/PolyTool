# Dev Log: Regime Integrity for Gate 2 Artifacts

**Date**: 2026-03-08
**Branch**: simtrader

---

## Problem

`tape-manifest` computed `mixed_regime_eligible` by counting operator-entered
regime labels from `watch_meta.json` / `prep_meta.json` without any
cross-check against market metadata.  An operator who accidentally labeled
a politics market as `sports` would silently skew the coverage summary.
Conversely, an operator who forgot `--regime` on eligible tapes would show
`mixed_regime_eligible: false` even if the markets were clearly diverse.

The `regime_policy.py` classifier already existed but was not used by the
tape manifest toolchain.

---

## Solution

Integrated `regime_policy.classify_market_regime()` into `tape_manifest.scan_one_tape()`:
- Each tape record now carries `derived_regime` (machine-classified from slug/metadata),
  `operator_regime` (raw operator label), `final_regime` (authoritative), `regime_source`,
  and `regime_mismatch`.
- `build_corpus_summary()` now uses `coverage_from_classified_regimes()` (new shared helper)
  instead of ad hoc set counting.

---

## Files changed

| File | Change |
|------|--------|
| `packages/polymarket/market_selection/regime_policy.py` | +`TapeRegimeIntegrity`, `derive_tape_regime()`, `_tape_metadata_to_market_dict()`, `coverage_from_classified_regimes()` |
| `tools/cli/tape_manifest.py` | `TapeRecord` +5 fields, `_read_tape_market_metadata()`, updated `scan_one_tape()` / `build_corpus_summary()` / `manifest_to_dict()`, schema v2 |
| `tests/test_regime_policy.py` | +`TestDeriveTapeRegime` (9 tests), +`TestCoverageFromClassifiedRegimes` (7 tests) |
| `tests/test_gate2_eligible_tape_acquisition.py` | +`TestRegimeIntegrityFields` (7 tests), +`TestMixedRegimeCoverageViaSharedHelper` (5 tests), +`TestManifestRegimeIntegrityFields` (3 tests) |
| `docs/specs/SPEC-0016-regime-integrity-for-gate2-artifacts.md` | New |
| `docs/features/FEATURE-regime-integrity-gate2-artifacts.md` | New |
| `docs/runbooks/GATE2_ELIGIBLE_TAPE_ACQUISITION.md` | Updated Phase 3 section for new fields |
| `docs/INDEX.md` | Links for SPEC-0016, FEATURE, dev log |

---

## Artifact fields added/changed

### `gate2_tape_manifest_v2` tape entry (new fields)

```
derived_regime    string   "politics"|"sports"|"new_market"|"other"
operator_regime   string   raw operator label; "unknown" if absent
final_regime      string   authoritative regime for corpus counting
regime_source     string   "derived"|"operator"|"fallback_unknown"
regime_mismatch   bool     True when derived and operator disagree (both named)
```

### `corpus_summary` (new field)

```
regime_coverage   object   {satisfies_policy, covered_regimes, missing_regimes, regime_counts}
```

---

## Backward compatibility

- `regime` field in tape entries = `final_regime` (unchanged for tapes with
  correct operator labels or no mismatches)
- Schema version bump v1 -> v2 is additive; v1 readers see `regime` unchanged
- `build_corpus_summary` produces identical `mixed_regime_eligible` for corpora
  where all tapes have correct operator labels
- Legacy `TapeRecord` objects (no new fields) serialize using `rec.regime`
  as fallback in `manifest_to_dict`

---

## Remaining backward-compatibility risk

- Tapes with generic slugs (e.g., `will-btc-close-above-100k`) will have
  `derived_regime = "other"` and fall back to `operator_regime`.  This is
  correct conservative behavior but means slug-only derivation is weak.
  Future improvement: store richer market metadata (title, tags) in
  watch_meta.json at capture time.
- Any external code reading manifest v1 JSON directly will see new fields as
  unexpected.  Recommend checking `schema_version` before parsing.
