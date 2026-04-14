---
phase: quick-260414-q9s
plan: 01
subsystem: gate2-corpus-visibility
tags: [gate2, corpus, scoring, tape-manifest, visibility]
dependency_graph:
  requires: []
  provides: [gate2-rank-score-events-passthrough, corpus-quality-breakdown, silver-tape-explanation]
  affects: [scan_gate2_candidates, tape_manifest, scorer]
tech_stack:
  added: []
  patterns: [optional-dataclass-fields, stdout-breakdown-table]
key_files:
  created:
    - docs/dev_logs/2026-04-14_gate2_corpus_visibility_and_ranking.md
  modified:
    - packages/polymarket/market_selection/scorer.py
    - tools/cli/scan_gate2_candidates.py
    - tools/cli/tape_manifest.py
    - tests/test_gate2_corpus_visibility.py
decisions:
  - "Optional fields with None defaults added at end of Gate2RankScore frozen dataclass to preserve backward compatibility with all existing callers"
  - "Silver/Bronze structural warning suppressed when eligible tapes exist to avoid noise"
  - "print_corpus_quality_breakdown called from main() rather than embedded in print_manifest_table to keep separation of concerns"
metrics:
  duration: "~15 minutes"
  completed_date: "2026-04-14"
  tasks_completed: 3
  files_changed: 5
---

# Quick Task 260414-q9s: Gate 2 Actionable Corpus Visibility — Summary

**One-liner:** Threaded `events_scanned`/`confidence_class` through `Gate2RankScore`, added aggregate `print_corpus_quality_breakdown()` to `tape_manifest`, and explained Silver tape structural unusability in corpus notes.

---

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Thread events_scanned/confidence_class + add corpus quality breakdown | b66f4cc | scorer.py, scan_gate2_candidates.py, tape_manifest.py |
| 2 | Add deterministic tests for new behavior | b608621 | tests/test_gate2_corpus_visibility.py |
| 3 | Write mandatory dev log | a7a1eec | docs/dev_logs/2026-04-14_gate2_corpus_visibility_and_ranking.md |

---

## What Changed

### scorer.py
- `Gate2RankScore` frozen dataclass gains `events_scanned: Optional[int] = None` and `confidence_class: Optional[str] = None` at the end (after `source: str`) — fully backward compatible.
- `score_gate2_candidate()` accepts `events_scanned` and `confidence_class` as new keyword-only parameters and passes them through to the constructor.

### scan_gate2_candidates.py
- `score_and_rank_candidates()` loop now passes `r.events_scanned` and `r.confidence_class` from each `CandidateResult` to `score_gate2_candidate()`. The existing `print_ranked_table()` already used `getattr` with fallback defaults — it now gets real values for tape-mode results.

### tape_manifest.py
- New function `print_corpus_quality_breakdown(records, summary)` prints: (1) reject-code distribution table, (2) confidence-tier distribution table, (3) Silver/Bronze structural warning when corpus is blocked and such tapes exist, (4) operator next-action guidance.
- `_corpus_note()` updated to explain Silver tape structural limitation (no L2 book data → fill engine always rejects with `book_not_initialized`).
- `main()` calls `print_corpus_quality_breakdown()` after `print_manifest_table()`.

### tests/test_gate2_corpus_visibility.py
- Added `CorpusSummary` and `print_corpus_quality_breakdown` to imports.
- Added `TestGate2RankScorePassthrough` (3 tests): passthrough of fields, defaults to None.
- Added `TestCorpusQualityBreakdown` (5 tests): reject distribution, confidence distribution, Silver warning, no-warning-when-eligible, next-action guidance.

---

## Test Results

```
tests/test_gate2_corpus_visibility.py: 38 passed in 0.35s
Full suite: 2460 passed, 1 pre-existing failure, 3 deselected, 19 warnings
```

Pre-existing failure: `test_ris_phase2_cloud_provider_routing.py::test_gemini_provider_success` — confirmed pre-existing (AttributeError on `providers._post_json`, unrelated to this work).

---

## Deviations from Plan

None — plan executed exactly as written. All three changes were surgical and non-breaking.

---

## Known Stubs

None. All new behavior is wired end-to-end. The `print_corpus_quality_breakdown()` function reads real diagnostic data from `TapeRecord.diagnostics` (falling back to `enrich_tape_diagnostics()` when not pre-populated).

---

## Threat Flags

None. All changes are local CLI stdout formatting and Optional dataclass field additions. No new network endpoints, auth paths, or trust boundaries introduced.

---

## Self-Check: PASSED

- `packages/polymarket/market_selection/scorer.py` — FOUND, `events_scanned` in `Gate2RankScore.__dataclass_fields__` confirmed
- `tools/cli/tape_manifest.py` — FOUND, `print_corpus_quality_breakdown` importable confirmed
- `tools/cli/scan_gate2_candidates.py` — FOUND, passthrough wired confirmed
- `tests/test_gate2_corpus_visibility.py` — FOUND, 38 tests pass confirmed
- `docs/dev_logs/2026-04-14_gate2_corpus_visibility_and_ranking.md` — FOUND
- Commits b66f4cc, b608621, a7a1eec — all present in git log
