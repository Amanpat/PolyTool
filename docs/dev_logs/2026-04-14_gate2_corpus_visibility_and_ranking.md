# Gate 2 Corpus Visibility and Ranking Improvements

**Date:** 2026-04-14
**Stream:** quick-260414-q9s
**Scope:** scorer.py, scan_gate2_candidates.py, tape_manifest.py, tests/test_gate2_corpus_visibility.py

---

## Summary

Three surgical changes to make Gate 2 corpus status immediately readable for the operator.
The tooling already computed confidence tiers, reject codes, and diagnostic enrichment —
but three gaps caused the useful data to be silently dropped before it reached the CLI output.

---

## Problem Statement

### Gap 1 — Gate2RankScore dropped events_scanned and confidence_class

`CandidateResult` already carried `events_scanned: int` and `confidence_class: str` from
tape scanning, but `score_gate2_candidate()` never accepted those fields as parameters.
`print_ranked_table()` used `getattr(s, "events_scanned", 0)` and
`getattr(s, "confidence_class", "")` defensively — meaning it always returned the fallback
defaults. The ranked output always showed `-` for Events and Conf columns on tape-mode results.

### Gap 2 — tape-manifest had no aggregate corpus quality breakdown

`print_manifest_table()` printed one row per tape with per-tape diagnostics, but no summary
showed the distribution of reject reasons or confidence tiers across the corpus. An operator
looking at 20+ blocked tapes had to manually count reject codes to understand the corpus shape.

### Gap 3 — Corpus note didn't explain Silver tape structural limitation

`_corpus_note()` said "Run 'prepare-gate2' or 'watch-arb-candidates'" without explaining
WHY existing tapes were blocked. The key insight — Silver tapes contain only `price_2min_guide`
events and have no L2 book data — was nowhere in the operator-facing output.

---

## Changes Made

### packages/polymarket/market_selection/scorer.py

- `Gate2RankScore` frozen dataclass gains two Optional fields at the end (after `source: str`):
  ```python
  events_scanned: Optional[int] = None
  confidence_class: Optional[str] = None
  ```
  Optional with defaults so all existing callers continue to work without modification.

- `score_gate2_candidate()` gains two new keyword parameters:
  ```python
  events_scanned: Optional[int] = None,
  confidence_class: Optional[str] = None,
  ```
  Both are passed through to the `Gate2RankScore(...)` constructor at the return statement.

### tools/cli/scan_gate2_candidates.py

- `score_and_rank_candidates()` loop now passes the two new kwargs from `CandidateResult`:
  ```python
  events_scanned=r.events_scanned if r.events_scanned else None,
  confidence_class=r.confidence_class if r.confidence_class else None,
  ```
  This makes `print_ranked_table()` show real values instead of fallback defaults.

### tools/cli/tape_manifest.py

- Added `print_corpus_quality_breakdown(records, summary)` function that prints:
  1. Reject-code distribution table (ELIGIBLE, NO_OVERLAP, DEPTH_ONLY, EDGE_ONLY,
     NO_DEPTH_NO_EDGE, NO_EVENTS, NO_ASSETS, UNKNOWN)
  2. Confidence-tier distribution table (GOLD, SILVER, BRONZE, UNKNOWN)
  3. Silver/Bronze structural warning block — only shown when eligible_count == 0
     and Silver/Bronze tapes exist in the corpus
  4. Operator next-action line (context-appropriate: capture Gold, fill missing regimes,
     or run sweep)

- `_corpus_note()` updated to explicitly mention the Silver tape structural limitation
  when `eligible_count == 0`: Silver/Bronze tapes lack L2 book data, so `L2Book` never
  initializes and the fill engine always rejects with `book_not_initialized`.

- `main()` calls `print_corpus_quality_breakdown(records, summary)` after
  `print_manifest_table(records, summary)`.

### tests/test_gate2_corpus_visibility.py

- Added `CorpusSummary` and `print_corpus_quality_breakdown` to imports.
- Added `TestGate2RankScorePassthrough` (3 tests):
  - `test_events_scanned_on_gate2_rank_score`: score carries events_scanned=150 and confidence_class="GOLD"
  - `test_defaults_none_when_not_passed`: score.events_scanned and .confidence_class default to None
  - `test_score_and_rank_passes_through`: events_scanned=200, confidence_class="SILVER" flow end-to-end
- Added `TestCorpusQualityBreakdown` (5 tests):
  - `test_reject_code_distribution_printed`: DEPTH_ONLY, EDGE_ONLY, NO_EVENTS appear in output
  - `test_confidence_tier_distribution_printed`: GOLD and SILV/SILVER appear in output
  - `test_silver_warning_when_blocked`: structural warning shown when eligible=0 and Silver tapes exist
  - `test_no_silver_warning_when_eligible_exists`: warning suppressed when eligible tapes present
  - `test_next_action_capture_gold`: NEXT action guidance appears when corpus blocked

---

## Key Insight: Why Silver Tapes Cannot Produce Executable Ticks

Silver tapes are reconstructed from `price_2min_guide` events — 2-minute OHLC price samples.
These events have no L2 book data (no bid/ask sizes). When the replay engine processes a
Silver tape:

1. `L2Book` never receives a `book` event, so it stays uninitialized.
2. The fill engine checks for an initialized L2 book before accepting any order.
3. Every tick rejects with `book_not_initialized`.
4. Result: `executable_ticks = 0`, tape is ineligible, no Gate 2 signal.

Only Gold-tier tapes — live WebSocket recordings from `watch-arb-candidates` or
`simtrader-shadow` — emit proper `book` and `price_change` events that initialize
L2Book and allow fill simulation.

**Capture path for Gold tapes:**
```bash
python -m polytool scan-gate2-candidates --enrich --top 10
python -m polytool watch-arb-candidates --slugs <top-candidates>
```

---

## Test Results

```
tests/test_gate2_corpus_visibility.py::TestClassifyTapeConfidence ... 10 passed
tests/test_gate2_corpus_visibility.py::TestClassifyRejectCode ....... 9 passed
tests/test_gate2_corpus_visibility.py::TestEnrichTapeDiagnostics .... 5 passed
tests/test_gate2_corpus_visibility.py::TestPrintTableHeaders ........ 6 passed
tests/test_gate2_corpus_visibility.py::TestGate2RankScorePassthrough  3 passed
tests/test_gate2_corpus_visibility.py::TestCorpusQualityBreakdown ... 5 passed

38 passed in 0.35s
```

Full regression suite: **2460 passed, 1 pre-existing failure, 3 deselected, 19 warnings**.
The pre-existing failure (`test_ris_phase2_cloud_provider_routing.py::test_gemini_provider_success`)
is an unrelated AttributeError in the research provider module — confirmed pre-existing by
verifying it fails identically on the commit immediately before this work.

---

## What Was NOT Changed (Scope Discipline)

- No fill-model changes
- No new CLI commands
- No wallet discovery
- No policy or roadmap changes
- No changes to gate thresholds or pass criteria
- No changes to benchmark_v1 manifests or lock files
- No changes to Gate 2 eligibility invariants

---

## Codex Review

Tier: Skip (formatting/output helpers, no execution paths or order placement logic).
