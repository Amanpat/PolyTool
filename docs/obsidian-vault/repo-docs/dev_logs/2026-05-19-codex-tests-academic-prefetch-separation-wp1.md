---
title: Codex Tests Academic Prefetch Separation Wp1
type: session_note
status: active
source_zone: repo
mirror_of: docs/dev_logs/2026-05-19_codex-tests-academic-prefetch-separation-wp1.md
last_synced: '2026-05-25T22:03:09Z'
lifecycle: reviewed
generator: repo-sync
---

# Codex Tests - Academic Prefetch Separation WP-1

**Date:** 2026-05-19
**Track:** RIS L1 Marker queue
**Type:** Test coverage / verification

---

## Files Changed

| File | Why |
|------|-----|
| `tests/test_ris_marker_queue.py` | Added offline WP-1 tests for PDF prefetch manifest state, idempotency, failure recording, cached warm-process routing, CLI help, and direct-PDF backward compatibility. |
| `docs/dev_logs/2026-05-19_codex-tests-academic-prefetch-separation-wp1.md` | Required handoff log for this work unit. |

No implementation code, runbook prose, benchmark baselines, or runtime artifacts were changed by this work unit.

---

## Tests Added

Added a focused WP-1 test block covering:

- Prefetch writes `pdf_cache/manifest.jsonl` with `candidate_id`, `arxiv_id`, `source_url`, `pdf_cache_path`, `status`, `attempts`, `error`, `fetched_at`, and `file_size`.
- Prefetch updates the queue record with local `pdf_url` while preserving queue status/attempt state.
- Re-running prefetch skips a valid cached PDF and does not call the injected HTTP function again.
- Failed prefetch records `status=failed`, a clear error, attempts, timestamp, and zero file size without corrupting the queue item.
- `get_status_report()` surfaces cached/failed prefetch manifest counts.
- `process_next_ipc()` prefers the cached local PDF path and calls `fetch_pdf_direct`, not live `fetch()`, when cache exists.
- Direct local `pdf_url` queue items still work without a prefetch manifest.
- `prefetch --help` exposes `--max-items`, `--delay-seconds`, and `--json`; top-level queue help exposes `--queue-dir`, `prefetch`, and `status-report`.
- A marked xfail documents the current runbook mismatch where `prefetch --status` is shown, but the CLI implements `status-report`.

---

## Commands Run

### Session start checks

```powershell
git status --short
```

Initial output: clean.

```powershell
git log --oneline -5
```

Output:
```text
50775d1 feat(ris): WP-1 academic PDF prefetch separation
1fb000d Academic Pipeline Improvements/Testing
de72208 docs(ris): academic pipeline scaled validation - Batch 1 execution record
03c9546 academic pipeline complete
dbcf2ec feat(ris): L4 Multi-source Academic Harvesters - Feature 3 closed
```

```powershell
python -m polytool --help
```

Result: exit 0; top-level CLI loaded.

### CLI contract checks

```powershell
python -m polytool research-marker-queue prefetch --help
```

Result: exit 0; help shows `--max-items`, `--delay-seconds`, and `--json`.

```powershell
python -m polytool research-marker-queue --help
```

Result: exit 0; help shows top-level `--queue-dir` plus `prefetch` and `status-report` subcommands.

### Focused tests

```powershell
pytest tests/test_ris_marker_queue.py -q
```

Final result after test cleanup:

```text
143 passed, 1 skipped, 1 xfailed in 3.42s
```

The xfail is intentional and documents the runbook mismatch described below.

### Adjacent RIS queue/fetcher subset

```powershell
pytest tests/test_ris_marker_queue.py tests/test_ris_fetchers.py tests/test_ris_marker_ipc_worker.py tests/test_ris_claim_extraction.py -q
```

Result:

```text
294 passed, 1 skipped, 3 deselected, 1 xfailed, 2 warnings in 97.24s
```

Warnings were existing Pydantic deprecation warnings from `marker` / `surya`.

### Required repo smoke

```powershell
python -m pytest tests/ -x -q --tb=short
```

Result:

```text
1 failed, 3297 passed, 1 skipped, 3 deselected, 1 xfailed, 21 warnings in 213.42s
```

First failure:

```text
tests/test_ris_phase4_source_acquisition.py::TestEndToEnd::test_ingest_external_arxiv_fixture
AssertionError: Rejected: academic_marker_gate: body_source='abstract' with body_length=0 is not Marker-quality; only Marker-parsed bodies (>= 5000 chars) are indexed as canonical academic corpus
```

Assessment: unrelated to this WP-1 test change. The failing test expects abstract-only arXiv fixture ingestion to pass, but current RIS academic gating rejects non-Marker academic bodies.

---

## Bugs / Mismatches Found

### Runbook / CLI mismatch

The runbook still documents this unsupported form in two places:

```powershell
python -m polytool research-marker-queue prefetch `
  --queue-dir artifacts/research/marker_parse_queue --status
```

and:

```powershell
python -m polytool research-marker-queue prefetch `
  --queue-dir artifacts/research/marker_parse_queue `
  --status
```

Actual CLI contract:

```powershell
python -m polytool research-marker-queue --queue-dir artifacts/research/marker_parse_queue status-report
```

Recommendation: update `docs/runbooks/RIS_MARKER_QUEUE_RUNBOOK.md` to replace `prefetch --status` with `status-report`.

### Full-suite unrelated failure

`tests/test_ris_phase4_source_acquisition.py::TestEndToEnd::test_ingest_external_arxiv_fixture` should be reconciled with the current Marker-only academic gate. Minimal likely fix: update the fixture/test expectation so abstract-only arXiv ingestion is rejected, or route the fixture through a Marker-quality body when the test intends canonical academic ingestion.

---

## Decisions

- Kept implementation code untouched; the WP-1 behavior is testable through existing injection seams.
- Used fake PDF bytes and injected HTTP/fetcher fakes only; no arXiv, Docker, GPU, or Marker model weights required.
- Added an xfail instead of modifying runbook prose because the work packet explicitly said to report runbook mismatches rather than edit the runbook.
- Preserved backward compatibility coverage for direct local PDF queue items independent of the prefetch manifest.

---

## Open Questions / Next Action

1. Fix the runbook `prefetch --status` references to use `status-report`.
2. Decide whether the Phase 4 arXiv fixture test should now expect rejection under the Marker-only academic gate.
3. After those are fixed, rerun `python -m pytest tests/ -x -q --tb=short`.

---

## Codex Review Summary

Tier: skip. Only tests and this dev log were changed. No execution, risk, rate limiter, order placement, or live-trading paths touched.
