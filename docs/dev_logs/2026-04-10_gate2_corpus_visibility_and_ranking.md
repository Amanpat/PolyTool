# Dev Log: Gate 2 Actionable Corpus Visibility and Ranking

**Date:** 2026-04-10
**Task ID:** 260410-izh
**Scope:** `tools/cli/tape_manifest.py`, `tools/cli/scan_gate2_candidates.py`, `tests/test_gate2_corpus_visibility.py`

## Problem

The tape-manifest CLI table and the scan-gate2-candidates tape scanner both lacked enough information for the operator to triage WHY tapes fail Gate 2 eligibility. The manifest table showed only Slug | Regime | Status | ExecTicks | Detail, with no density signal or structured reject classification. This made it impossible to quickly answer: "Is this tape thin Silver reconstruction or a dense Gold live tape? Is it failing on depth or edge or both?"

## Changes

### `tools/cli/tape_manifest.py`

**New helpers (3 functions + constants):**

- `_GOLD_SOURCES`, `_SILVER_SOURCES` — frozensets classifying source tools
- `classify_tape_confidence(recorded_by, events_scanned, ticks_with_both_bbo) -> str`
  Returns GOLD / SILVER / BRONZE / UNKNOWN based on source tool and event density.
  - GOLD: gold source (watch-arb-candidates, simtrader-shadow) AND ≥50 events AND ≥20 BBO ticks
  - SILVER: ≥50 events (any source) OR silver source (prepare-gate2, simtrader-quickrun) with ≥20 events
  - BRONZE: has some events and BBO ticks but below Silver threshold
  - UNKNOWN: no events
- `classify_reject_code(evidence, reject_reason) -> str`
  Maps eligibility stats to ELIGIBLE / NO_OVERLAP / DEPTH_ONLY / EDGE_ONLY / NO_DEPTH_NO_EDGE / NO_EVENTS / NO_ASSETS / UNKNOWN.
- `enrich_tape_diagnostics(record) -> dict`
  Reads evidence dict and record fields, returns: confidence_class, reject_code, events_scanned, ticks_with_bbo, best_edge_gap, max_depth_yes, max_depth_no.

**`TapeRecord` dataclass:** Added `diagnostics: dict[str, Any]` field (default empty).

**`scan_one_tape()`:** Calls `enrich_tape_diagnostics(record)` on the returned record.

**`print_manifest_table()`:** Replaced with enriched version. New columns:
`Tape/Slug | Regime | Conf | Status | Code | Events | BBO | ExecTicks | BestEdge | MaxDepth | Detail`

**`manifest_to_dict()`:** Each tape entry now includes a `"diagnostics"` key with the full enriched dict.

### `tools/cli/scan_gate2_candidates.py`

**`CandidateResult` dataclass:** Added 3 optional fields:
- `events_scanned: int = 0`
- `confidence_class: str = ""`
- `recorded_by: str = ""`

**`scan_tapes()`:** Imports `_read_recorded_by` and `classify_tape_confidence` from `tools.cli.tape_manifest` at call time. Computes and stores all 3 new fields per tape.

**Column constants:** Added `_COL_EVENTS = 7`, `_COL_CONF = 5`, `_CONF_ABBREV` dict.

**`_header_line()` / `print_table()`:** Now renders `Events | Conf` columns between Market and Exec.

**`_ranked_header_line()` / `print_ranked_table()`:** Same — `Events | Conf` columns added after Market. Uses `getattr` with fallback for forward-compat with Gate2RankScore objects that don't carry these fields.

## Tests

**`tests/test_gate2_corpus_visibility.py`** — 30 tests, all offline/deterministic:
- `TestClassifyTapeConfidence` (10 cases): all tier branches including edge cases
- `TestClassifyRejectCode` (9 cases): all code paths from evidence and reason strings
- `TestEnrichTapeDiagnostics` (5 cases): field population, edge gap math, empty evidence
- `TestPrintTableHeaders` (6 cases): column header presence and abbreviation rendering

## Test Results

```
30 passed in 0.33s (new test file)
3941 passed, 8 failed (pre-existing test_ris_phase2_cloud_provider_routing.py failures)
```

Pre-existing failures are all `AttributeError: _post_json` in research evaluation providers — unrelated to this change.

## Codex Review

Tier: Skip (docs, config, CLI formatting helpers — no execution-path code changed).

## Open Questions / Blockers

None. This is a pure visibility improvement. Gate 2 eligibility criteria and thresholds are unchanged.

## Operator Path Forward

After this change, `python -m polytool tape-manifest --scan-dir artifacts/tapes/gold` (or silver) shows the Conf and Code columns, making it immediately visible which tapes are:
- GOLD/ELIGIBLE → ready for Gate 2 sweep
- SILVER/DEPTH_ONLY → need more liquid markets (improve fill size)
- GOLD/EDGE_ONLY → spread too tight, need wider markets
- BRONZE/UNKNOWN → thin tape, recapture or discard
