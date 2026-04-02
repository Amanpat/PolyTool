---
phase: quick-260402-qud
plan: 260402-qud
subsystem: research
tags: [ris, claim-extraction, testing, hardening, sqlite, cli, python]

# Dependency graph
requires:
  - phase: quick-260402-ogq
    provides: HeuristicClaimExtractor, extract_and_link(), build_intra_doc_relations(), research-extract-claims CLI

provides:
  - narrowed exception handling in build_intra_doc_relations (sqlite3.IntegrityError only)
  - exact SUPPORTS/CONTRADICTS relation row assertions in test suite
  - full evidence JSON shape assertions (section_heading, excerpt length cap, document_id)
  - idempotency tests for claim extraction and evidence linking
  - 7 CLI smoke tests for research-extract-claims (help/no-args/missing-doc/empty-store/JSON-shape/dry-run/JSON-dry-run)

affects: [ris-phase-5, claim-hardening]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Narrow except clauses to specific exception types (sqlite3.IntegrityError not Exception)"
    - "Purpose-built relation fixtures with deterministic claim counts (exactly 2 sentences, 8+ shared key terms)"
    - "CLI smoke tests via capsys + monkeypatch sys.argv on main(argv) entrypoints"

key-files:
  created:
    - tests/test_research_extract_claims_cli.py
    - docs/dev_logs/2026-04-02_ris_phase4_claim_extraction_hardening.md
  modified:
    - packages/research/ingestion/claim_extractor.py
    - tests/test_ris_claim_extraction.py

key-decisions:
  - "claim_relations table has NO UNIQUE constraint — duplicate rows from repeated build_intra_doc_relations are a known limitation, documented in tests and dev log"
  - "except sqlite3.IntegrityError catches CHECK constraint violations (invalid relation_type); all other errors now propagate"
  - "SUPPORTS/CONTRADICTS fixture design: 8+ shared non-stopword terms ensures deterministic single relation insertion"
  - "evidence idempotency relies on pre-insert SELECT in add_evidence() — confirmed by test, not just assumed"

requirements-completed: []

# Metrics
duration: 10min
completed: 2026-04-02
---

# Quick 260402-qud: RIS Phase 4 Claim Extraction Hardening Summary

**Narrowed broad exception swallowing in build_intra_doc_relations, replaced count-only relation tests with exact SUPPORTS/CONTRADICTS row assertions, added evidence JSON shape + idempotency tests, added 7 offline CLI smoke tests for research-extract-claims.**

## Performance

- **Duration:** ~10 min
- **Started:** 2026-04-02
- **Completed:** 2026-04-02
- **Tasks:** 4 completed
- **Files modified:** 4 (2 created, 2 modified)

## Accomplishments

- Replaced `except Exception: pass` with `except sqlite3.IntegrityError` + `_log.debug(...)` in `build_intra_doc_relations` — programming errors and connection errors now propagate instead of being silently swallowed
- Added 3 deterministic relation fixtures (SUPPORTS, CONTRADICTS, NO_MATCH) and replaced count-only tests with exact row-type assertions; `SUPPORTS`/`CONTRADICTS` occurrences in test file: 13 (was ~2)
- Strengthened evidence tests: asserts `section_heading`, `document_id`, excerpt length cap (0–500 chars), and idempotency (second extract does not double evidence rows)
- Created `tests/test_research_extract_claims_cli.py` with 7 offline smoke tests covering all CLI paths

## Task Commits

1. **Task 1: Narrow exception handling** — `1410494`
2. **Task 2: Exact relation + evidence tests** — `08532cf`
3. **Task 3: CLI smoke tests** — `75cf544`
4. **Task 4: Dev log** — `91d79ea`

## Files Created/Modified

- `packages/research/ingestion/claim_extractor.py` — sqlite3 + logging imports; except narrowed; debug log added
- `tests/test_ris_claim_extraction.py` — 3 new tests, 3 replaced/strengthened (59 total, was 56)
- `tests/test_research_extract_claims_cli.py` — new file, 7 CLI smoke tests
- `docs/dev_logs/2026-04-02_ris_phase4_claim_extraction_hardening.md` — dev log with test counts and known limitations

## Decisions Made

- `claim_relations` has no UNIQUE constraint: duplicate rows on rerun are expected and documented (not fixed here — schema change is a future ticket)
- `sqlite3.IntegrityError` is the correct narrow catch: it covers FK misses and CHECK constraint violations on `relation_type`, which are the only expected non-bug DB errors in this path
- Fixture design uses 8+ shared key terms above the `_MIN_SHARED_TERMS_FOR_RELATION = 3` threshold to guarantee deterministic single-relation insertion

## Deviations from Plan

None. All 4 tasks executed as specified.

## Known Limitations

- `claim_relations` has no UNIQUE constraint — running `build_intra_doc_relations` twice on the same claim set inserts duplicate rows. Documented in test docstring and dev log. Schema fix deferred.
- Relation type assignment (SUPPORTS vs CONTRADICTS) uses simple negation heuristic — semantic false positives/negatives expected for nuanced text.

## Next Phase Readiness

- Claim set A is now strongly verified: exact row-type assertions, evidence shape assertions, and CLI smoke coverage all pass
- Any future change to `build_intra_doc_relations` that introduces a new exception class will now surface as a test failure rather than silent pass
- CLI path is covered for the 7 main invocation patterns

---
*Phase: quick-260402-qud*
*Completed: 2026-04-02*
