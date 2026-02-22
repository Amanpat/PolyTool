---
phase: quick-6
plan: "01"
subsystem: clv-enrichment
tags:
  - clv
  - dual-variants
  - settlement
  - pre-event
  - hypothesis-ranking
  - coverage-report
dependency_graph:
  requires:
    - packages/polymarket/clv.py (existing CLV pipeline)
    - polytool/reports/coverage.py (segment analysis + hypothesis ranking)
    - tools/cli/scan.py (CLV enrichment integration)
  provides:
    - enrich_position_with_dual_clv (12 new per-position fields)
    - _build_clv_variant_coverage (settlement + pre_event sub-dicts)
    - _build_hypothesis_candidates with clv_variant_used field
  affects:
    - dossier.json (gains 12 new variant CLV fields per position)
    - coverage_reconciliation_report.json (clv_coverage gains settlement/pre_event sub-dicts)
    - hypothesis_candidates.json (gains clv_variant_used field)
tech_stack:
  added: []
  patterns:
    - Parameterized ladder: _resolve_close_ts_from_ladder accepts explicit ladder sequence
    - Variant suffix convention: closing_price_{variant}, clv_pct_{variant}, etc.
    - Pre-event preference cascade for hypothesis ranking
key_files:
  created:
    - docs/features/FEATURE-dual-clv-variants.md
  modified:
    - packages/polymarket/clv.py
    - polytool/reports/coverage.py
    - tools/cli/scan.py
    - tools/cli/audit_coverage.py
    - tests/test_clv.py
    - tests/test_coverage_report.py
    - tests/test_scan_trust_artifacts.py
decisions:
  - Settlement sub-ladder uses only _CLOSE_TS_LADDER[0] (onchain_resolved_at); pre-event uses _CLOSE_TS_LADDER[1:] (gamma stages)
  - enrich_position_with_dual_clv calls existing enrich_position_with_clv first to preserve all base fields
  - Hypothesis ranking prefers pre_event notional-weighted CLV when weight > 0, else settlement, else combined, else count-weighted fallback
  - clv_variant_used field added to each hypothesis candidate dict for traceability
metrics:
  duration: "~9 minutes"
  completed: "2026-02-20T23:16:30Z"
  tasks_completed: 3
  files_changed: 7
---

# Phase quick-6 Plan 01: Dual CLV Variants (clv_settlement + clv_pre_event) Summary

**One-liner:** Dual CLV enrichment splitting onchain settlement anchor from gamma pre-event anchor, with hypothesis ranking preferring pre-event notional-weighted CLV.

## What Was Built

Added two named CLV variants per position to separate market-close signal from on-chain
settlement signal:

- **clv_settlement** uses only `onchain_resolved_at` as the close_ts anchor (single-stage sub-ladder)
- **clv_pre_event** uses the gamma closedTime → endDate → umaEndDate ladder (skips resolution stage)

Each position gains 12 new fields (6 per variant): `closing_price_*`, `closing_ts_*`,
`clv_pct_*`, `beat_close_*`, `clv_source_*`, `clv_missing_reason_*`.

Coverage report now renders two named CLV sub-sections ("CLV Settlement", "CLV Pre-Event").
Hypothesis candidates include `clv_variant_used` and prefer pre_event notional-weighted CLV
when available.

## Task Summary

| Task | Name | Commit | Key Files |
|---|---|---|---|
| 1 | Add dual CLV resolver functions + enrich_position_with_dual_clv | dd4e721 | packages/polymarket/clv.py |
| 2 | Wire dual CLV into scan.py, audit_coverage.py, coverage.py | 37f404a | polytool/reports/coverage.py, tools/cli/scan.py, tools/cli/audit_coverage.py, tests/test_scan_trust_artifacts.py |
| 3 | Unit tests + feature doc | 0407007 | tests/test_clv.py, tests/test_coverage_report.py, docs/features/FEATURE-dual-clv-variants.md |

## Decisions Made

1. **Settlement sub-ladder** is `_CLOSE_TS_LADDER[0]` only (onchain_resolved_at). Pre-event is `_CLOSE_TS_LADDER[1:]` (gamma stages). This clean slice avoids any code duplication.

2. **Backward compat preserved** by calling `enrich_position_with_clv` first inside `enrich_position_with_dual_clv`. All existing base CLV fields remain untouched.

3. **Hypothesis ranking cascade:** pre_event notional-weighted → settlement notional-weighted → combined notional-weighted → count-weighted fallbacks. `clv_variant_used` field records which was selected.

4. **Missing reason codes** `NO_SETTLEMENT_CLOSE_TS` and `NO_PRE_EVENT_CLOSE_TS` are distinct from the base `NO_CLOSE_TS` to enable targeted coverage debugging.

## Deviations from Plan

**Auto-fixed Issues**

**1. [Rule 3 - Blocking] test_scan_trust_artifacts.py patched old function name**
- **Found during:** Task 2
- **Issue:** Existing test `test_run_scan_compute_clv_persists_fields_into_dossier` patched `scan.enrich_positions_with_clv` which no longer exists on the module after renaming to `enrich_positions_with_dual_clv`
- **Fix:** Updated test to patch `enrich_positions_with_dual_clv` with a fake that also sets the 12 dual-variant fields and returns the expanded summary dict
- **Files modified:** tests/test_scan_trust_artifacts.py
- **Commit:** 37f404a

## Test Coverage

- **Before:** 453 tests
- **After:** 463 tests (10 new tests added: 7 in test_clv.py, 3 in test_coverage_report.py)
- **Regressions:** 0

## Self-Check: PASSED

Files verified:
- packages/polymarket/clv.py: FOUND
- polytool/reports/coverage.py: FOUND
- tools/cli/scan.py: FOUND
- tools/cli/audit_coverage.py: FOUND
- tests/test_clv.py: FOUND
- tests/test_coverage_report.py: FOUND
- docs/features/FEATURE-dual-clv-variants.md: FOUND

Commits verified:
- dd4e721: FOUND (feat(quick-6): add dual CLV resolver functions and enrich_position_with_dual_clv)
- 37f404a: FOUND (feat(quick-6): wire dual CLV into scan.py, audit_coverage.py, and coverage.py)
- 0407007: FOUND (test(quick-6): add dual CLV variant unit tests + feature doc)
