# Feature: Scan Metadata Enrichment

**Spec**: `docs/specs/SPEC-0017-phase1-gate2-candidate-ranking.md`
**Status**: Shipped
**Date**: 2026-03-08
**Branch**: simtrader

---

## What this feature does

Adds an optional `--enrich` mode to `scan-gate2-candidates` so live operators
can reduce `UNKNOWN` ranking fields during candidate discovery without changing
the default scan path.

When enabled in live mode, the scanner now tries to enrich ranked candidates
with:
- reward config
- 24h volume
- created-at / age context
- richer regime metadata (category, tags, event context)
- combined live bids for the competition factor

Any missing field or fetch failure remains non-fatal and stays explicitly
`UNKNOWN`.

---

## Changed files

| File | Change |
|------|--------|
| `tools/cli/scan_gate2_candidates.py` | Added `--enrich`, live-only metadata fetch helper, and opt-in live orderbook carry-through for competition scoring |
| `tests/test_gate2_candidate_ranking.py` | Added enrichment success/failure coverage and an honest-`UNKNOWN` guard for missing 24h volume |
| `docs/specs/SPEC-0017-phase1-gate2-candidate-ranking.md` | Documented the shipped `--enrich` CLI path and non-fatal fallback contract |

---

## Invariants preserved

- Default `scan-gate2-candidates` behavior is unchanged when `--enrich` is absent
- Gate 2 pass criteria and ranking weights are unchanged
- Missing metadata is still zero evidence, not positive evidence
- If Gamma/reward enrichment fails, the scan still completes and affected fields remain `UNKNOWN`
