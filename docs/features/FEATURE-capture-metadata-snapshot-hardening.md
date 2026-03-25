# Feature: Capture Metadata Snapshot Hardening

**Spec**: `docs/specs/SPEC-0014-gate2-eligible-tape-acquisition.md`
**Status**: Shipped
**Date**: 2026-03-08
**Branch**: simtrader

---

## What this feature does

Hardens Gate 2 capture artifacts by persisting an additive `market_snapshot`
block into `watch_meta.json` and `prep_meta.json` whenever capture-time market
metadata is available.

The snapshot stores the best available local evidence used later for
regime/new-market derivation, including fields like `question`, `category`,
`tags`, `event_slug`, `created_at`, `age_hours`, and `captured_at`.

---

## Why it exists

Before this patch, later `tape-manifest` runs had to derive regime/new-market
context from whatever slug or metadata happened to remain available in local
artifacts. That was backward-compatible, but weak: newer derivations could end
up depending on sparse metadata or context outside the original capture
artifact.

With the snapshot in place:
- capture artifacts retain the evidence available at capture time
- tape-manifest prefers that local snapshot over `meta.json` when deriving
  regime/new-market context
- missing fields remain absent instead of being invented later

---

## Changed files

| File | Change |
|------|--------|
| `tools/cli/watch_arb_candidates.py` | Writes `market_snapshot` into `watch_meta.json` when capture-time metadata is available |
| `tools/cli/prepare_gate2.py` | Writes `market_snapshot` into `prep_meta.json` using candidate metadata plus resolve-time metadata |
| `tools/cli/tape_manifest.py` | Prefers artifact-local `market_snapshot` for regime/new-market derivation; keeps legacy fallback |
| `tests/test_gate2_eligible_tape_acquisition.py` | Added tests for snapshot persistence, manifest preference, and legacy fallback |

---

## Compatibility

- Schema is additive: existing top-level `market_slug`, asset IDs, and `regime`
  fields remain unchanged
- Older tapes without `market_snapshot` still work through legacy top-level and
  `meta.json` fallback paths
- Eligibility logic is unchanged
