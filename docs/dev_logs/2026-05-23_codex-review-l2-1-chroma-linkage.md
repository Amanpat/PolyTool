# Codex Review - L2.1 Deliverable A Chroma/KnowledgeStore Linkage

**Date:** 2026-05-23
**Reviewer:** Codex
**Verdict:** PASS WITH CONCERNS

## Objective

Review and test L2.1 Deliverable A. Done means Chroma academic records carry a
stable KnowledgeStore document link, verifier coverage proves bad links are
reported, semantic retrieval behavior remains unchanged, and Deliverable B can
start from a known state.

## Files reviewed

- `docs/specs/SPEC-ris-l2-1-academic-retrieval-quality.md`
- `docs/dev_logs/2026-05-23_l2-1-chroma-linkage.md`
- `packages/research/ingestion/marker_queue.py`
- `tools/cli/research_marker_queue.py`
- `tests/test_ris_marker_queue.py`
- `docs/runbooks/RIS_MARKER_QUEUE_RUNBOOK.md`
- `packages/research/synthesis/academic_query.py` (confirmed no dirty diff)

Out-of-scope dirty tree noted: many Obsidian/vault files, `AGENTS.md`, and
`claude.md` are modified or untracked in this working tree. I did not edit them.

## Review result

Deliverable A scope is Chroma linkage only. The dirty implementation changes are
limited to Marker queue indexing/backfill helpers, the marker-queue CLI verifier,
offline tests, and runbook text. I found no dirty change to
`packages/research/synthesis/academic_query.py`, and no semantic fallback,
ranking, or academic query behavior change was introduced.

Chroma metadata now includes `ks_doc_id` on each academic chunk. Chunk IDs are
deterministic hashes derived from `ks_doc_id` plus chunk index, while the
metadata preserves the full KnowledgeStore document ID. The `check-chroma-links`
CLI reports missing `ks_doc_id` values and `ks_doc_id` values not present in the
KnowledgeStore.

## Tests added or changed

Updated `tests/test_ris_marker_queue.py` with focused offline coverage:

- `test_chunk_id_does_not_replace_ks_doc_id_metadata`
- `test_valid_linkage_json_all_zeros` now uses a real temp KnowledgeStore row and
  asserts exit code 0.
- `test_json_output_has_all_required_fields` now uses a real temp KnowledgeStore
  row.
- `test_internal_candidate_id_metadata_is_reported_as_orphan`
- `test_mixed_valid_and_mismatched_links_are_reported`

These tests prove:

- new Chroma records preserve full 64-char `ks_doc_id` metadata;
- deterministic/internal Chroma chunk IDs do not replace KnowledgeStore IDs;
- candidate/internal IDs used as `ks_doc_id` are reported as orphaned;
- mixed valid and mismatched links fail verification with the mismatched doc ID
  reported.

## Commands run

### Initial session checks

`python -m polytool --help`

Output: exit 0; CLI loaded and listed command families, including
`research-marker-queue` and `research-query`.

### Focused tests

`python -m pytest tests/test_ris_marker_queue.py -q --tb=short`

Output:

```text
collected 205 items
204 passed, 1 skipped in 4.38s
```

`python -m pytest tests/test_research_query.py -q --tb=short`

Output:

```text
collected 83 items
83 passed in 0.84s
```

### CLI checks

`python -m polytool research-marker-queue --help`

Output: exit 0; subcommands listed:

```text
enqueue, list, process, warm-process, index-done, counts, prefetch,
status-report, jit-cache-check, check-chroma-links
```

`python -m polytool research-marker-queue check-chroma-links --help`

Output: exit 0; flags listed:

```text
--ks-path PATH
--chroma-path PATH
--collection NAME
--json
```

`python -m polytool research-marker-queue embed-chroma --help`

Output: exit 1:

```text
invalid choice: 'embed-chroma' (choose from enqueue, list, process,
warm-process, index-done, counts, prefetch, status-report, jit-cache-check,
check-chroma-links)
```

### Smoke suite

`python -m pytest tests/ -x -q --tb=short`

First run: timed out after 120 seconds at 45 percent, no failure reached.

Second run with longer timeout:

```text
1 failed, 3387 passed, 1 skipped, 3 deselected, 21 warnings in 213.10s
```

Failure:

```text
FAILED tests/test_ris_phase4_source_acquisition.py::TestEndToEnd::test_ingest_external_arxiv_fixture
AssertionError: Rejected: academic_marker_gate: body_source='abstract' with body_length=0
is not Marker-quality; only Marker-parsed bodies (>= 5000 chars) are indexed
as canonical academic corpus
```

Assessment: unrelated to this review/test change. I did not touch source
acquisition, the academic ingest fixture, or the Marker-only ingest gate.

## Linkage verification result

PASS for focused offline linkage coverage.

- Metadata contains `ks_doc_id`.
- `ks_doc_id` remains distinct from deterministic Chroma chunk IDs.
- A valid temp KnowledgeStore source document ID resolves cleanly.
- Missing `ks_doc_id` exits nonzero.
- Internal/truncated-style IDs that are not KnowledgeStore IDs are reported as
  `ks_doc_id_not_in_ks`.
- Mixed valid plus orphaned links are detected.

## Scope violations

No semantic retrieval, ranking, query fallback, Marker parser, queue processing,
GPU parsing, full 29-paper run, or benchmark baseline behavior was changed by
this review.

Concern: `docs/dev_logs/2026-05-23_l2-1-chroma-linkage.md` and
`docs/runbooks/RIS_MARKER_QUEUE_RUNBOOK.md` document
`python -m polytool research-marker-queue embed-chroma`, but that CLI subcommand
does not exist. The implementation has `embed_done_items_into_chroma()` as a
library method and `index-done --reindex-chroma` as a CLI path, but the documented
standalone backfill command is not wired.

Concern: the full smoke suite is red on an unrelated Phase 4 academic fixture
that now conflicts with the Marker-only academic ingest gate.

## Recommended next action

Before Deliverable B, fix the operator backfill mismatch by either wiring the
documented `embed-chroma` subcommand to `embed_done_items_into_chroma()` or
updating the runbook/dev log to use the supported `index-done --reindex-chroma
--force` path. Then address or quarantine the unrelated abstract-only fixture
failure so the full suite can return to green.
