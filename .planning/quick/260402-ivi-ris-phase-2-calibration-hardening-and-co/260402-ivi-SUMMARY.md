---
phase: quick-260402-ivi
plan: 260402-ivi
subsystem: research
tags: [ris, calibration, seed-manifest, precheck-ledger, family-drift, analytics, python]

# Dependency graph
requires:
  - phase: quick-260401-nzz
    provides: corpus seeding infrastructure (research_seed, seed.py, SeedEntry, SeedManifest, precheck_ledger)
  - phase: quick-260401-o1q
    provides: precheck lifecycle events (precheck_run, override, outcome) in ledger

provides:
  - seed manifest v2 schema with evidence_tier and notes fields
  - accurate source_type reclassification for all 11 corpus entries
  - CalibrationSummary dataclass with 8 aggregate health metrics
  - FamilyDriftReport dataclass with per-domain recommendation breakdown
  - compute_calibration_summary() and compute_family_drift() core analytics functions
  - format_calibration_report() human-readable text formatter
  - research-calibration CLI surface with summary subcommand
  - book_foundational SOURCE_FAMILY_GUIDANCE entry

affects: [ris-phase-3, research-autoresearch, corpus-refresh]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Optional dataclass fields with None defaults for backward-compatible schema extension"
    - "keyword-heuristic domain assignment on free-text idea fields (first-match wins)"
    - "TDD RED-GREEN cycle for analytics module"

key-files:
  created:
    - packages/research/synthesis/calibration.py
    - tools/cli/research_calibration.py
    - tests/test_ris_calibration.py
    - docs/features/FEATURE-ris-calibration-and-metadata.md
    - docs/dev_logs/2026-04-02_ris_phase2_calibration_and_metadata_hardening.md
  modified:
    - config/seed_manifest.json
    - packages/research/ingestion/seed.py
    - packages/research/evaluation/types.py
    - polytool/__main__.py

key-decisions:
  - "Retained source_family=book_foundational for all reclassified entries — null half-life in freshness_decay.json makes these timeless docs regardless of source_type"
  - "evidence_tier values: tier_1_internal (active/authoritative) vs tier_2_superseded (historical reference only)"
  - "Domain assignment uses keyword heuristic on idea text rather than source_family from events — documented as best-effort, Phase 3 should add source_family to precheck events"
  - "override_rate defined as override_count / total_prechecks (not outcome events) — measures operator disagreement with precheck recommendations"
  - "overrepresented_in_stop threshold: STOP count > 50% of domain total (strict majority)"

requirements-completed: []

# Metrics
duration: 45min
completed: 2026-04-02
---

# Quick 260402-ivi: RIS Phase 2 Calibration Hardening and Corpus Metadata Hygiene Summary

**Seed manifest v2 with accurate source_type reclassification (reference_doc/roadmap) and evidence_tier provenance; calibration analytics module exposing 8 precheck health metrics and per-domain STOP drift via research-calibration CLI**

## Performance

- **Duration:** ~45 min
- **Started:** 2026-04-02T00:00:00Z
- **Completed:** 2026-04-02
- **Tasks:** 3 completed
- **Files modified:** 8 (4 created, 4 modified)

## Accomplishments

- Reclassified all 11 seed manifest entries from `source_type: "book"` to accurate types (`reference_doc` x8, `roadmap` x3); added `evidence_tier` and `notes` to every entry; bumped manifest to v2
- Built `packages/research/synthesis/calibration.py` with `CalibrationSummary`, `FamilyDriftReport`, `compute_calibration_summary()`, `compute_family_drift()`, and `format_calibration_report()` — TDD RED+GREEN cycle, 31 tests passing
- Registered `research-calibration summary` CLI with `--window` (all/Nd/Nh), `--ledger`, `--manifest`, and `--json` flags; smoke test produces valid zero-count JSON output on empty ledger

## Task Commits

1. **Task 1: Seed manifest metadata hygiene** — `85d5c2d` (feat)
2. **Task 2 RED: TDD failing tests for calibration analytics** — `bd0a12f` (test)
3. **Task 2 GREEN: Calibration analytics module + CLI** — `4c84c9e` (feat)
4. **Deviation fix: book_foundational guidance** — `0a234d7` (fix)
5. **Task 3: Feature doc + dev log** — `ed55937` (feat)

## Files Created/Modified

- `config/seed_manifest.json` — bumped to v2; reclassified 11 entries with accurate source_type, evidence_tier, notes
- `packages/research/ingestion/seed.py` — extended SeedEntry with optional evidence_tier and notes fields; updated load_seed_manifest()
- `packages/research/evaluation/types.py` — added reference_doc and roadmap to SOURCE_FAMILIES; added book_foundational to SOURCE_FAMILY_GUIDANCE
- `packages/research/synthesis/calibration.py` — new analytics module: CalibrationSummary, FamilyDriftReport, compute_calibration_summary(), compute_family_drift(), format_calibration_report()
- `tools/cli/research_calibration.py` — new CLI entrypoint for research-calibration summary subcommand
- `polytool/__main__.py` — registered research_calibration_main; added research-calibration to command table and help text
- `tests/test_ris_calibration.py` — 31 tests; 6 test classes covering calibration module, CLI, manifest hygiene, and backward compatibility
- `docs/features/FEATURE-ris-calibration-and-metadata.md` — full feature documentation
- `docs/dev_logs/2026-04-02_ris_phase2_calibration_and_metadata_hardening.md` — before/after reclassification table, metric definitions, commands run, exact test counts, Phase 3 open questions

## Decisions Made

- Retained `source_family: "book_foundational"` for all reclassified entries. The `source_type` fix corrects the classification metadata but the foundational document status (null half-life) is unchanged.
- `evidence_tier` values: `tier_1_internal` for active authoritative docs; `tier_2_superseded` for v4.2 roadmap only.
- Domain assignment in `compute_family_drift()` uses keyword heuristic on the `idea` field. This is explicitly documented as best-effort until Phase 3 adds `source_family` to precheck_run events.
- `override_rate = override_count / total_prechecks` measures operator disagreement with precheck recommendations specifically (not outcome events).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Added book_foundational entry to SOURCE_FAMILY_GUIDANCE**
- **Found during:** Task 1 (seed manifest metadata hygiene)
- **Issue:** Adding `"reference_doc": "book_foundational"` and `"roadmap": "book_foundational"` to `SOURCE_FAMILIES` caused `book_foundational` to appear as a mapped value without a corresponding `SOURCE_FAMILY_GUIDANCE` entry. The existing test `test_all_families_have_guidance` checks the invariant that every value in SOURCE_FAMILIES has guidance. Without this fix, Task 1 would break that test.
- **Fix:** Added `book_foundational` guidance entry to `SOURCE_FAMILY_GUIDANCE` in `packages/research/evaluation/types.py`
- **Files modified:** `packages/research/evaluation/types.py`
- **Verification:** `tests/test_ris_evaluation.py::TestSourceFamilyGuidance::test_all_families_have_guidance` passes; full regression 3039 passed
- **Committed in:** `0a234d7`

---

**Total deviations:** 1 auto-fixed (Rule 2 — missing critical functionality)
**Impact on plan:** Required to satisfy pre-existing invariant test. No scope creep. The guidance content itself is substantive and correct for book_foundational scoring behavior.

## Issues Encountered

- Worktree was behind main and feat/ws-clob-feed at session start. Required `git stash`, `git merge main`, `git merge feat/ws-clob-feed` to get all RIS code before beginning. Not a bug; resolved cleanly.

## Known Stubs

None — all calibration functions return live computed values from ledger events. The zero-count output on an empty ledger is correct behavior, not a stub.

## User Setup Required

None — no external service configuration required. The ledger at `artifacts/research/prechecks/precheck_ledger.jsonl` is created automatically when prechecks are run. The CLI reads from it with graceful empty-ledger handling.

## Next Phase Readiness

- `research-calibration summary` is usable immediately; will produce meaningful data once the ledger accumulates precheck_run, override, and outcome events from real operator sessions.
- For meaningful family drift analysis, Phase 3 should add `source_family` to `precheck_run` ledger events to replace the keyword heuristic.
- `evidence_tier` field on SeedEntry is available but not yet surfaced in precheck synthesis logic — Phase 3 could use tier to weight evidence retrieval.

---
*Phase: quick-260402-ivi*
*Completed: 2026-04-02*
