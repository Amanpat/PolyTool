# Dev Log: Capture Metadata Snapshot Hardening

**Date:** 2026-03-08
**Branch:** simtrader
**Author:** PolyTool Contributors

---

## What was built

Added additive capture-time market metadata snapshots to Gate 2 watch/prep
artifacts and made `tape-manifest` prefer those snapshots when deriving
regime/new-market context.

### Problem

`watch_meta.json` and `prep_meta.json` only persisted slug, token IDs, and the
operator regime label. That meant later derivation often had only a weak slug
signal or had to lean on other local context instead of the evidence available
when the tape was captured.

### Solution

- `watch-arb-candidates` now writes `market_snapshot` into `watch_meta.json`
  with the best available capture-time market metadata.
- `prepare-gate2` now writes the same additive snapshot into `prep_meta.json`,
  using candidate metadata already in memory and any extra resolve-time market
  metadata available from Gamma.
- `tape-manifest` now prefers `market_snapshot` for regime/new-market
  derivation and passes snapshot `captured_at` into `derive_tape_regime()`.
- Legacy top-level metadata and `meta.json` remain fallback paths for older
  tapes with no snapshot.

---

## Files changed

| File | What changed |
|------|-------------|
| `tools/cli/watch_arb_candidates.py` | Added additive `market_snapshot` persistence in `watch_meta.json` |
| `tools/cli/prepare_gate2.py` | Added additive `market_snapshot` persistence in `prep_meta.json` |
| `tools/cli/tape_manifest.py` | Prefer artifact-local snapshot metadata for derivation; preserve legacy fallback |
| `tests/test_gate2_eligible_tape_acquisition.py` | Added tests for watch/prep snapshot persistence, legacy fallback, and manifest preference |
| `docs/specs/SPEC-0014-gate2-eligible-tape-acquisition.md` | Documented additive `market_snapshot` artifact contract |
| `docs/specs/SPEC-0016-regime-integrity-for-gate2-artifacts.md` | Documented snapshot precedence for derivation |
| `docs/runbooks/GATE2_ELIGIBLE_TAPE_ACQUISITION.md` | Added operator note about snapshot persistence |
| `docs/features/FEATURE-capture-metadata-snapshot-hardening.md` | Feature note |
| `docs/dev_logs/2026-03-08_capture_metadata_snapshot_hardening.md` | This file |
| `docs/INDEX.md` | Added feature and dev-log entries |

---

## Test results

```bash
pytest -q tests/test_regime_policy.py tests/test_gate2_eligible_tape_acquisition.py
```

Result: 75 passed.
