# RIS Phase 4 Claim Extraction Hardening

**Date:** 2026-04-02
**Quick ID:** 260402-qud
**Branch:** feat/ws-clob-feed

## Summary

Codex review of the RIS Phase 4 claim extraction pipeline (quick-260402-ogq) flagged three risk areas: (1) a broad `except Exception: pass` in `build_intra_doc_relations` that silently swallowed all DB errors including real programming bugs, (2) relation tests that only asserted non-negative counts rather than checking exact SUPPORTS/CONTRADICTS row types and counts, and (3) zero CLI test coverage for `research-extract-claims`. This plan addressed all three without changing any production behavior.

## Changes Made

### `packages/research/ingestion/claim_extractor.py`

- Added `import sqlite3` and `import logging` at the module top.
- Added `_log = logging.getLogger(__name__)` module-level constant.
- Replaced bare `except Exception: pass` in `build_intra_doc_relations` with `except sqlite3.IntegrityError` plus a `_log.debug(...)` line.
- The narrowed catch means programming errors (TypeError, AttributeError), connection errors (OperationalError), and all other unexpected exceptions now propagate naturally instead of being silently swallowed.
- No change to function signature, return type, or happy-path behavior.

### `tests/test_ris_claim_extraction.py`

Added three module-level fixture constants:
- `RELATION_SUPPORTS_DOC` — two sentences with 8+ shared key terms, no negation, produces exactly 2 claims.
- `RELATION_CONTRADICTS_DOC` — two sentences with 8+ shared key terms where one contains "does not", produces exactly 2 claims.
- `RELATION_NO_MATCH_DOC` — two sentences from disjoint domains (crypto exchange vs. weather), fewer than 3 shared terms.

Replaced/added in `TestBuildIntraDocRelations`:
- `test_supports_relation_between_shared_term_claims`: asserts `len(claim_ids) == 2`, `count == 1`, fetches via `store.get_relations`, asserts exactly 1 relation with `relation_type == "SUPPORTS"`.
- `test_contradicts_relation_for_negation_pair`: asserts `len(claim_ids) == 2`, `count == 1`, fetches via `store.get_relations(claim_ids[0], relation_type="CONTRADICTS")`, asserts exactly 1 CONTRADICTS row.
- `test_no_relation_when_insufficient_shared_terms`: uses RELATION_NO_MATCH_DOC, asserts `count == 0`.
- `test_relation_idempotent_on_rerun`: documents the known no-UNIQUE-constraint behavior — each call inserts 1 new row; after 2 calls, total rows == 2.

Strengthened in `TestExtractClaimsFromDocument`:
- `test_evidence_has_excerpt_and_location`: added assertions for `loc["section_heading"]` is a string, `loc["document_id"] == doc_id`, `0 < len(row["excerpt"]) <= 500`.
- Added `test_idempotent_extraction_evidence_not_doubled`: extracts twice, counts evidence rows before and after, asserts counts are equal.

Strengthened in `TestExtractAndLink`:
- `test_returns_summary_dict`: assert `result["claims_extracted"] >= 3` (was `>= 0`).

### `tests/test_research_extract_claims_cli.py` (new file)

Seven offline smoke tests for `tools/cli/research_extract_claims.main()`:

1. `test_main_help_returns_zero` — `--help` exits 0.
2. `test_main_no_args_returns_error` — no args exits 2 (argparse required group).
3. `test_main_doc_id_not_found` — nonexistent `--doc-id` returns 0.
4. `test_main_all_empty_store` — `--all` on empty store prints "No source documents", returns 0.
5. `test_main_all_json_output_shape` — `--all --json` returns valid JSON with `documents_processed`, `total_claims`, `total_relations`, `per_doc_results` keys; `total_claims >= 1`.
6. `test_main_dry_run_does_not_write` — `--all --dry-run` returns 0 and store has 0 claims after.
7. `test_main_all_json_dry_run` — `--all --dry-run --json` returns JSON with `"dry_run": true` and `"total_claims_estimate" >= 1`.

## Test Results

```
tests/test_ris_claim_extraction.py + tests/test_research_extract_claims_cli.py:
66 passed in 0.77s

Full project regression suite:
3272 passed, 25 warnings in 92.55s (0:01:32)
```

`python -m polytool --help` loads cleanly with no import errors.

## Known Limitations

- `claim_relations` table has no UNIQUE constraint on `(source_claim_id, target_claim_id, relation_type)`. Running `build_intra_doc_relations` twice on the same claim set inserts duplicate rows. This is a schema concern for a future ticket and is documented in `test_relation_idempotent_on_rerun`.

- Relation type assignment (SUPPORTS vs CONTRADICTS) uses a simple negation-word heuristic, not semantic analysis. False positives and negatives are expected for nuanced text where negation is implicit or contextual.

## Codex Review Tier

Skip — tests and docs only per CLAUDE.md review policy (no strategy, execution, or SimTrader core files modified).
