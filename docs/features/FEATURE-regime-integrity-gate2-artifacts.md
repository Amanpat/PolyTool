# Feature: Regime Integrity for Gate 2 Artifacts

**Spec**: `docs/specs/SPEC-0016-regime-integrity-for-gate2-artifacts.md`
**Status**: Shipped
**Date**: 2026-03-08
**Branch**: simtrader

---

## What this feature does

Makes regime classification evidence-backed and machine-derived across Gate 2
tape acquisition artifacts so that mixed-regime corpus coverage cannot drift
from operator-entered labels that go unchecked.

### Key changes

1. **Shared regime classifier integrated into tape manifest**:
   `tape-manifest` now calls `regime_policy.classify_market_regime()` on each
   tape's market metadata (slug, title, question, tags where available) to
   produce a `derived_regime` alongside the operator-entered `operator_regime`.

2. **Regime provenance fields in manifest tape entries**:
   - `derived_regime` — machine-classified regime from available metadata
   - `operator_regime` — raw operator label from tape metadata
   - `final_regime` — authoritative regime (derived wins if named, else operator)
   - `regime_source` — `"derived"` | `"operator"` | `"fallback_unknown"`
   - `regime_mismatch` — True when derived and operator disagree (both named)

3. **Mixed-regime coverage uses shared helper**:
   `build_corpus_summary` now calls `coverage_from_classified_regimes()`
   (from `regime_policy`) rather than ad hoc label counting. Coverage
   definition is canonical and cannot diverge.

4. **Schema version bumped**: `gate2_tape_manifest_v1` -> `gate2_tape_manifest_v2`

---

## New manifest fields

### Per-tape entry (new)

```json
{
  "regime": "politics",        // = final_regime; backward compat
  "derived_regime": "politics",
  "operator_regime": "sports", // operator made a mistake
  "final_regime": "politics",  // derived wins
  "regime_source": "derived",
  "regime_mismatch": true
}
```

### Corpus summary (new field)

```json
"regime_coverage": {
    "satisfies_policy": false,
    "covered_regimes": ["sports"],
    "missing_regimes": ["politics", "new_market"],
    "regime_counts": {"politics": 0, "sports": 1, "new_market": 0}
}
```

---

## New code

| Location | What was added |
|----------|---------------|
| `regime_policy.py` | `TapeRegimeIntegrity` dataclass, `derive_tape_regime()`, `_tape_metadata_to_market_dict()`, `coverage_from_classified_regimes()` |
| `tape_manifest.py` | `TapeRecord` new fields, `_read_tape_market_metadata()`, updated `scan_one_tape()` / `build_corpus_summary()` / `manifest_to_dict()` |
| `tests/test_regime_policy.py` | `TestDeriveTapeRegime`, `TestCoverageFromClassifiedRegimes` |
| `tests/test_gate2_eligible_tape_acquisition.py` | `TestRegimeIntegrityFields`, `TestMixedRegimeCoverageViaSharedHelper`, `TestManifestRegimeIntegrityFields` |

---

## Backward compatibility

- Old `regime` field retained in `TapeRecord` and manifest JSON = `final_regime`
- Legacy tape records without new fields serialize using `rec.regime` as fallback
- `gate2_tape_manifest_v1` readers see `regime` unchanged; new fields are additive

## What this does NOT do

- Does not change Gate 2 pass criteria
- Does not change strategy entry logic or preset sizing
- Does not auto-correct operator labels (human review still required for mismatches)
- Does not guarantee correct classification for ambiguous market slugs
