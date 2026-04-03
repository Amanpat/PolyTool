---
phase: quick
plan: 260402-rm1
subsystem: research-ingestion
tags: [ris, fetchers, acquisition, cli, tdd, stdlib]
dependency_graph:
  requires: [260402-ogu, 260402-qud]
  provides: [live-fetchers, acquisition-review-log, research-acquire-cli]
  affects: [ris-pipeline, knowledge-store]
tech_stack:
  added: []
  patterns: [injectable-http-fn, append-only-jsonl, tdd-red-green, stdlib-only-http]
key_files:
  created:
    - packages/research/ingestion/fetchers.py
    - packages/research/ingestion/acquisition_review.py
    - tools/cli/research_acquire.py
    - tests/test_ris_fetchers.py
    - tests/test_ris_acquisition_review.py
    - tests/test_ris_research_acquire_cli.py
    - docs/dev_logs/2026-04-02_ris_phase5_live_acquisition.md
    - docs/features/FEATURE-ris-phase5-live-acquisition.md
  modified:
    - polytool/__main__.py
    - tests/conftest.py
decisions:
  - Local regex copies in fetchers.py (not imported from normalize.py) to avoid circular import risk
  - Injectable _http_fn pattern for hermetic offline test isolation without subprocess overhead
  - stdlib-only HTTP (urllib.request) -- no new runtime dependencies
  - Dedup check before pipeline but ingest proceeds regardless (idempotent cache write)
  - Review record written even on ingest failure for complete audit trail
metrics:
  duration_minutes: 75
  completed_date: "2026-04-03T00:12:46Z"
  tasks_completed: 4
  tasks_total: 4
  files_created: 8
  files_modified: 2
---

# Phase quick Plan 260402-rm1: RIS Phase 5 Live Source Acquisition Adapters Summary

**One-liner:** stdlib-only live fetchers (arXiv/GitHub/blog) + JSONL acquisition audit log + `research-acquire` CLI with injectable `_http_fn` for offline testing.

## Tasks Completed

| # | Name | Commit | Key files |
|---|---|---|---|
| 1 | TDD: fetchers + acquisition_review | `d906703` | fetchers.py, acquisition_review.py, test_ris_fetchers.py (33 offline), test_ris_acquisition_review.py (10) |
| 2 | TDD: research-acquire CLI | `128c4f9` | tools/cli/research_acquire.py, polytool/__main__.py, test_ris_research_acquire_cli.py (14) |
| 3 | pytest.mark.live marker | `c53ff5b` | tests/conftest.py |
| 4 | Dev log + feature doc + verification | (this commit) | docs/dev_logs/2026-04-02_ris_phase5_live_acquisition.md, docs/features/FEATURE-ris-phase5-live-acquisition.md |

## Test Results

Full regression with `-m "not live"`:

```
1 failed (pre-existing), 3328 passed, 3 deselected
```

New tests added: 57 offline (33 fetchers + 10 review + 14 CLI) + 3 live-marked smoke tests.

Pre-existing failure: `tests/test_ris_evaluation.py::TestEvaluateDocumentConvenience::test_get_provider_factory_unknown_raises`
caused by commit `fefbabe` on the parallel `quick-260402-rmz` track — not caused by this plan.

## Deviations from Plan

None — plan executed exactly as written.

The live smoke tests in `tests/test_ris_fetchers.py` are correctly marked
`@pytest.mark.live` and excluded from the offline regression run.

## CLI Verification

```
$ python -m polytool research-acquire --help
usage: research-acquire [-h] [--url URL] [--source-family FAMILY]
                        [--cache-dir PATH] [--review-dir PATH] [--db PATH]
                        [--no-eval] [--dry-run] [--json] [--provider NAME]
...
```

`research-acquire` appears in `python -m polytool --help` under the
`Research Intelligence (RIS v1/v2)` section.

## Known Stubs

None. All data flows are wired end-to-end.

## Self-Check: PASSED

Files confirmed present:
- packages/research/ingestion/fetchers.py: FOUND
- packages/research/ingestion/acquisition_review.py: FOUND
- tools/cli/research_acquire.py: FOUND
- tests/test_ris_fetchers.py: FOUND
- tests/test_ris_acquisition_review.py: FOUND
- tests/test_ris_research_acquire_cli.py: FOUND

Commits confirmed:
- d906703: FOUND
- 128c4f9: FOUND
- c53ff5b: FOUND
