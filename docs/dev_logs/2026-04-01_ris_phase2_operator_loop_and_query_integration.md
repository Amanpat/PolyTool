# Dev Log: RIS Phase 2 — Operator Feedback Loop and Richer Query Integration

**Date:** 2026-04-01
**Quick task:** 260401-o1q
**Branch:** feat/ws-clob-feed
**Commit:** 9c61c08

## Objective

Extend the RIS v1 precheck system with:
1. Lifecycle event recording (override, outcome) in the ledger
2. Enriched query output with provenance, contradiction summaries, staleness notes, and lifecycle
3. CLI subcommands for operator feedback and knowledge store inspection

## Files Changed

### Modified
- `packages/research/synthesis/precheck_ledger.py` — schema bump to v2, four new functions
- `packages/research/synthesis/precheck.py` — four lifecycle fields added to `PrecheckResult`
- `packages/research/ingestion/retriever.py` — two new functions: `query_knowledge_store_enriched`, `format_enriched_report`
- `tools/cli/research_precheck.py` — full refactor to argparse subparsers
- `tests/test_ris_precheck_wiring.py` — updated 2 tests for schema version bump (v1 -> v2)
- `tests/test_ris_precheck.py` — updated 1 test for CLI subcommand refactor behavior

### Created
- `tests/test_ris_phase2_operator_loop.py` — 26 new offline tests

## Task 1: Ledger Schema v2

**Changes to `precheck_ledger.py`:**
- `LEDGER_SCHEMA_VERSION` bumped from `"precheck_ledger_v1"` to `"precheck_ledger_v2"`
- `append_override(precheck_id, override_reason, ledger_path)` — writes `event_type="override"` with `was_overridden=True`; raises `ValueError` on empty precheck_id
- `append_outcome(precheck_id, outcome_label, outcome_date, ledger_path)` — writes `event_type="outcome"`; validates label against `{"successful","failed","partial","not_tried"}`; defaults `outcome_date` to UTC ISO now
- `get_precheck_history(precheck_id, ledger_path)` — returns all events matching precheck_id, sorted by `written_at` ascending
- `list_prechecks_by_window(start_iso, end_iso, ledger_path)` — ISO string comparison for time-range filtering

**Changes to `precheck.py`:**
Added four fields to `PrecheckResult` with defaults:
```python
was_overridden: bool = False
override_reason: str = ""
outcome_label: str = ""
outcome_date: str = ""
```
These are populated only by downstream code hydrating from ledger history, NOT by `run_precheck()`.

## Task 2: Enriched Query Output

**Changes to `retriever.py`:**

`query_knowledge_store_enriched()`:
- Calls `store.query_claims(apply_freshness=True)`, applies source_family and min_freshness filters
- For each claim: fetches `get_provenance(claim_id)` → `provenance_docs`
- Fetches `get_relations(claim_id, relation_type="CONTRADICTS")` → resolves other_id (source or target) → fetches `get_claim(other_id)` → `contradiction_summary` list of texts
- Computes `staleness_note`: "STALE" if freshness_modifier < 0.5, "AGING" if < 0.7, "" otherwise
- `include_contradicted` flag is a documentation hook only (no filtering effect)

`format_enriched_report()`:
- Formats one section per claim with Claim/Confidence/Freshness/Score/Lifecycle/Status/Staleness/Contradictions/Provenance lines
- Sections separated by `---`

## Task 3: CLI Subcommands

Refactored `main(argv)` in `tools/cli/research_precheck.py` to use `argparse.subparsers`.

Subcommands:
- **`run`**: unchanged behavior, now also accepts as explicit subcommand
- **`override`**: `--precheck-id` (req), `--reason` (req), `--ledger`, `--json`
- **`outcome`**: `--precheck-id` (req), `--label` (req), `--date`, `--ledger`, `--json`
- **`history`**: `--precheck-id` OR `--start`+`--end`, `--ledger`, `--json`
- **`inspect`**: `--source-family`, `--min-freshness`, `--top-k`, `--db`, `--include-contradicted`, `--json`

Backward compat: if `argv[0]` is not a known subcommand and `--idea` is in argv, routes to `run`.

## Task 4: Tests

Test file: `tests/test_ris_phase2_operator_loop.py` — 26 tests, all offline.

Test classes:
- `TestAppendOverride` (3 tests): event content, empty id raises, schema_version
- `TestAppendOutcome` (4 tests): event content, invalid label raises, all valid labels, auto-date
- `TestGetPrecheckHistory` (3 tests): single run, run+override ordering, multi-id filtering
- `TestListPrechecksByWindow` (2 tests): includes matching, excludes outside
- `TestPrecheckResultLifecycleFields` (2 tests): defaults, explicit values
- `TestEnrichedQuery` (6 tests): provenance, contradiction summary, staleness note, lifecycle field, report structure, empty list
- `TestCLI` (6 tests): backward compat run, explicit run, override, outcome, history, help

## Test Results

```
tests/test_ris_phase2_operator_loop.py — 26 passed
tests/test_ris_precheck_wiring.py — 35 passed
tests/test_ris_ingestion_integration.py — 12 passed
tests/test_ris_precheck.py — 25 passed

Full suite: 3012 passed, 0 failed, 25 warnings
```

## Deviations from Plan

### Auto-fixed: Existing tests asserting schema version v1

Three existing tests in `test_ris_precheck_wiring.py` and `test_ris_precheck.py` asserted
the old schema version (`"precheck_ledger_v1"`) or old CLI behavior (`main([])` raises SystemExit).
These were updated to reflect the v2 schema and subcommand-aware return behavior.

**Files modified:** `tests/test_ris_precheck_wiring.py`, `tests/test_ris_precheck.py`

## Decisions Made

1. **`include_contradicted` flag is a no-op by design.** Contradicted claims appear in results
   regardless (already downweighted via KnowledgeStore's 0.5x effective_score penalty). The flag
   exists as a documentation/extensibility hook in case future policy wants hard filtering.

2. **`main([])` returns 1 (not SystemExit) with subparsers.** argparse subparsers don't error
   when no subcommand is given — the behavior prints help and returns 1. Old `test_main_returns_1_without_idea`
   updated accordingly.

3. **Backward compat detection on first token only.** If `argv[0]` is not a known subcommand
   AND `--idea` is in argv, treat as `run`. This covers `--idea "..." --no-ledger` style calls.

## Open Questions

1. **`inspect` subcommand requires on-disk KnowledgeStore.** No default DB exists in most dev
   environments. A future task could add a `--create-empty` flag or auto-bootstrap for testing.

2. **Contradiction detection in `query_knowledge_store_enriched` is bidirectional.** A relation
   from B→A (B CONTRADICTS A) will appear in A's contradiction_summary as B's text. The relation
   from A→B (A CONTRADICTS B) would appear in B's summary. Current behavior: both directions
   are included when looking up by claim_id (since `get_relations` queries both source and target
   roles). This is correct but worth documenting for future claim modeling.

## Codex Review

Tier: Recommended (retriever.py strategy-adjacent). Review deferred; no execution-layer or
order-placement code changed. No mandatory-tier files modified.
