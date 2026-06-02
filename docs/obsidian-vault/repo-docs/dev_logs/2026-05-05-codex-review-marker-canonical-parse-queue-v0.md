---
title: Codex Review Marker Canonical Parse Queue V0
type: session_note
status: active
source_zone: repo
mirror_of: docs/dev_logs/2026-05-05_codex-review-marker-canonical-parse-queue-v0.md
last_synced: '2026-05-25T22:03:09Z'
lifecycle: reviewed
generator: repo-sync
---

# Codex Review - Marker Canonical Academic Parse Queue v0

Date: 2026-05-05
Reviewer: Codex
Scope: Review queue v0 after Claude Prompt A and B.
Verdict: FAIL

## Review Focus

Objective: determine whether v0 preserves Marker-only canonical academic embeddings,
avoids pdfplumber drift, keeps queue artifacts auditable/idempotent/gitignored, and
does not overclaim L1 production readiness before live Docker warm-worker validation.

## Files Changed By This Review

- `docs/dev_logs/2026-05-05_codex-review-marker-canonical-parse-queue-v0.md` - new review log requested by operator.

No code files were changed.

## Commands Run

### Repo hygiene / context

`git status --short`

Result: dirty worktree with queue-related untracked files plus unrelated docs/Obsidian metadata changes. Queue-related files inspected directly because they are untracked and do not appear in normal `git diff`.

`git log --oneline -5`

Output:

```text
a4fdcac docs(ris): close out Marker control surface validation - L1 still blocked
e01efd4 feat(ris): Marker single-paper validation control surface
38a13c2 docs(ris): short-paper Marker smoke validation - systematic timeout diagnosis
103eeb3 fix(ris): site-packages/static EPERM fix + L1 benchmark timeout diagnosis
3348aef fix(ris): L1 Marker rollout - Codex FAIL resolution (adapter rejection, scheduler split, cache mount)
```

`python -m polytool --help`

Result: exit 0. `research-marker-queue` is registered in the CLI help.

### Required review checks

`python -m pytest tests/test_ris_marker_queue.py tests/test_ris_scheduler.py tests/test_ris_academic_pdf.py`

Output:

```text
134 passed in 1.59s
```

`python -m polytool research-marker-queue --help`

Result: exit 0. Help exposes `enqueue`, `list`, `process`, and `counts`.

`python -m polytool research-scheduler run-academic-url --help`

Result: exit 0. Existing single-paper control-surface help loads.

`git diff --check`

Result: exit 0. Only line-ending warnings were printed for existing Obsidian/metadata files.

## Findings By Severity

### Blocking

1. Warm-worker acceptance is not implemented.

`MarkerParseQueue.process_next()` reuses one `LiveAcademicFetcher`, but the Docker/Linux production path in `LiveAcademicFetcher` still calls `_marker_production_extract_subprocess()` for every paper. That method spawns a fresh process per item, and `_marker_process_worker()` creates a fresh `MarkerPDFExtractor`; `MarkerPDFExtractor.extract()` then calls `create_model_dict()` for each paper. This means model weights are not loaded once and reused across queue items. The current implementation may process multiple queue items sequentially, but it does not satisfy the warm-model design that is supposed to remove per-paper cold load.

Relevant lines:
- `packages/research/ingestion/marker_queue.py:233-235`
- `packages/research/ingestion/fetchers.py:322-356`
- `packages/research/ingestion/extractors.py:481-482`

2. Marker-only canonical embedding enforcement is not implemented.

The queue writes a `marker_ready` flag, but `packages/research/ingestion/pipeline.py` has no `body_source == "marker"` or `marker_ready` gate before chunking and storing academic documents. `ingest_external()` adapts the raw source, runs hard stops, chunks `extracted.body`, and stores it without checking parser provenance. A long pdfplumber body can still be indexed if it reaches this path via `RIS_PDF_PARSER=pdfplumber`, `RIS_PDF_PARSER=auto`, compatibility tests, or a caller-provided raw source.

Relevant lines:
- `packages/research/ingestion/pipeline.py:253-330`
- `docs/dev_logs/2026-05-05_marker-canonical-parse-queue-v0.md:125-126` documents that embedding code "should" gate, but the gate is not present.

### Non-blocking

1. Short Marker bodies are marked `done` instead of an explicit failure state.

`is_marker_ready("marker", body_length < 5000)` correctly returns false, but `_process_item()` only sets `rejected=True` when `body_source != "marker"`. A short Marker output therefore becomes `queue_status="done"` with `marker_ready=false` and no `failure_reason`. That is not a RAG-ready overclaim, but it weakens failure auditability and can make queue counts look healthier than the usable corpus.

Relevant lines:
- `packages/research/ingestion/marker_queue.py:262-270`
- `packages/research/ingestion/marker_queue.py:332-348`
- `tests/test_ris_marker_queue.py` codifies this behavior in `test_marker_short_body_not_ready`.

2. Queue state is auditable only by correlating two files.

`queue.jsonl` stores mutable status/attempts; `results.jsonl` stores parse details and failure reasons. That is acceptable for a single-worker v0, but failed queue rows do not themselves carry `failure_reason`, `body_source`, `body_length`, or `parse_seconds` as requested in the work packet. Operators must correlate the latest result record manually.

3. Documentation and CLI text overclaim warm throughput.

The dev log and CLI describe `process` as a "warm-model worker" and state that subsequent papers run around 6s/paper. Live Docker validation is correctly marked deferred, but those timing claims are not supported by the implementation because models are recreated per item in the current Marker path.

Relevant lines:
- `packages/research/ingestion/marker_queue.py:216-217`
- `tools/cli/research_marker_queue.py:185-187`
- `docs/dev_logs/2026-05-05_marker-canonical-parse-queue-v0.md:130-135`

## Checklist Assessment

1. Marker only canonical parser for final academic RAG-ready output: FAIL. Queue-level `marker_ready` exists, but the ingestion/indexing gate is missing.
2. pdfplumber not reintroduced as normal production fallback: PASS for default Marker and queue rejection; not sufficient end-to-end because the pipeline still accepts pdfplumber-sourced academic bodies if they reach it.
3. Queue artifacts file-backed, idempotent, auditable, gitignored: PASS WITH CAVEAT. JSONL artifacts are under ignored `/artifacts/`; enqueue is idempotent; audit requires correlating `queue.jsonl` and `results.jsonl`.
4. CLI exposes enqueue/list/process/counts: PASS.
5. Worker can process multiple items sequentially in one process: PARTIAL. Parent CLI loops sequentially; Marker parsing itself is not warm-reused in Docker.
6. RAG-ready requires `body_source=marker` and useful body length: PASS at queue flag level, FAIL as an embedding/indexing invariant.
7. Failure states explicit and include `failure_reason`: PARTIAL. Non-marker and exceptions include reasons in `results.jsonl`; short Marker output is `done` with no failure reason.
8. No L2/PaperQA2, SVM/SPECTER2, L4, n8n, or trading scope creep: PASS.
9. Tests offline/deterministic and pass: PASS, 134 passed.
10. Docs do not claim L1 production is shipped before live Docker/warm-worker validation: PASS WITH FIXES. They do not claim production shipped, but they overstate warm throughput and worker behavior.

## Decision

Live Docker queue validation may not proceed as an acceptance validation yet.

Reason: the current code path does not implement the warm Marker worker architecture that live validation is meant to prove, and canonical embedding enforcement is not wired into the ingestion pipeline. A limited smoke of `enqueue`, `list`, `counts`, and maybe one negative/cold parse can be run for diagnostics, but it should not be treated as the L1 queue validation gate.

## Open Questions / Blockers

- Should v0 fix the worker by loading Marker models once in a true long-lived worker process, or should the documented acceptance gate be narrowed to "file-backed queue only" and leave warm parsing to v1?
- Should `IngestPipeline.ingest_external()` reject non-marker academic sources by default, or should the gate live in a dedicated embedding/indexing path that consumes queue results?
- Should `marker` outputs below `MIN_MARKER_BODY_LENGTH` transition to `failed` or a dedicated `not_rag_ready` terminal state with `failure_reason`?

## Codex Review Summary

Tier: Recommended/Mandatory for RIS parser and ingestion correctness. Blocking issues found: 2. Non-blocking issues found: 3. Issues addressed in this review: none; code edits were out of scope.
