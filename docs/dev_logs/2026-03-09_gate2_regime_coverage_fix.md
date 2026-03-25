# 2026-03-09 Gate 2 regime coverage fix

## Summary

Fixed a Gate 2 reporting bug where `corpus_summary.by_regime` counted classified tapes
correctly, but `corpus_summary.regime_coverage` only counted eligible tapes. That let
the manifest and preflight disagree about which regimes were actually present in the
classified corpus.

## Root cause

`tools/cli/tape_manifest.py` built `by_regime` from every scanned tape, but passed only
eligible tapes into `coverage_from_classified_regimes()`. As a result:

- `by_regime.sports.total` could be non-zero
- `regime_coverage.regime_counts.sports` could still be `0`
- `covered_regimes` and `missing_regimes` could describe the eligible subset instead of
  the classified corpus

## Fix

- Build `regime_coverage` from every tape's authoritative `final_regime`
- Keep `eligible_count` and `gate2_eligible_tapes` unchanged
- Keep `mixed_regime_eligible` gate-oriented by requiring at least one eligible tape
  plus at least two named regimes in the classified corpus
- Align `corpus_note` wording with classified-corpus coverage so it no longer claims
  missing "eligible tapes" when the corpus is already classified in that regime

## Tests

Validated with:

```powershell
pytest -q tests/test_gate2_eligible_tape_acquisition.py
```

Result: `59 passed`
