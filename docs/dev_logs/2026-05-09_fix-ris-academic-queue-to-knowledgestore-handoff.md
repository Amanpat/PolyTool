# Fix: RIS Academic Queue-to-KnowledgeStore Handoff

**Date:** 2026-05-09
**Objective:** Close the gap between a completed Marker queue item and `research-query` returning citations.

---

## Root Cause

`MarkerParseQueue._process_item()` called `fetcher.fetch()` which returned a dict containing
`body_text` (the full Marker-extracted text). However only metadata fields (`body_source`,
`body_length`, `parse_seconds`) were copied into the result and persisted to `results.jsonl`.
The `body_text` was silently discarded.

Consequence: after `warm-process` marked a queue item `done` with `marker_ready=True`,
the body text was gone. There was no way to index it into the KnowledgeStore without
re-running Marker. So `research-query` always returned `had_fallback=True`.

Confirmed by operator test: `artifacts/research/operator_test_queue_direct` had
`arxiv:2604.24366` with `body_source=marker, body_length=56856, marker_ready=True,
queue_status=done` — but the `bodies/` subdirectory was absent and the KnowledgeStore
contained no academic documents.

---

## Files Changed

| File | Change |
|------|--------|
| `packages/research/ingestion/marker_queue.py` | Added `_BODY_STORE_SUBDIR`, `_persist_body_sidecar()`, `_read_best_results()`, `index_done_items()`; modified `_process_item()` to call `_persist_body_sidecar` when `marker_ready=True` |
| `tools/cli/research_marker_queue.py` | Added `_cmd_index_done()` handler, `index-done` subparser, wired into `main()` |
| `tests/test_ris_marker_queue.py` | Added 20 tests across `TestPersistBodySidecar`, `TestIndexDoneItems`, `TestCLIIndexDone` |
| `docs/runbooks/RIS_MARKER_QUEUE_RUNBOOK.md` | Added Step 4b (index-done), body-file diagram, body-missing recovery path, updated query prerequisite |

---

## Implementation

### Body persistence (during warm-process)

`_process_item` now calls `_persist_body_sidecar(candidate_id, raw)` immediately after
confirming `marker_ready=True`. This writes:

- `queue_dir/bodies/{candidate_id}.body.txt` — raw Marker body (UTF-8)
- `queue_dir/bodies/{candidate_id}.meta.json` — fetch metadata without `body_text`
  (title, abstract, authors, published_date, body_source, body_length, ...)

Both files are overwritten on re-process (idempotent for `--force` re-enqueue).
Sidecar writes are non-fatal: failure is logged and processing continues.

### Index-done step

`index_done_items(ks_path, force, _store)` reads `results.jsonl` to find all
`queue_status=done AND marker_ready=True` records (most-recent result per candidate_id),
then for each:

1. Checks `indexed.jsonl` — skips if already indexed (unless `force=True`)
2. Reads body from `bodies/{candidate_id}.body.txt` — reports `skipped_no_body` if absent
3. Reads metadata sidecar from `bodies/{candidate_id}.meta.json`
4. Builds `raw_source` dict compatible with `AcademicAdapter`
5. Calls `IngestPipeline.ingest_external(raw_source, "academic")` — enforces Marker gate
6. Appends to `indexed.jsonl` with `doc_id`, `chunk_count`, `indexed_at`

**Gate enforcement:** `ingest_external` applies the academic Marker gate
(`body_source=marker AND body_length >= 5000`). pdfplumber, marker_failed, abstract_fallback,
and short bodies are all rejected. This gate was already in place; `index_done_items` cannot
accidentally index non-Marker content.

### CLI

```bash
python -m polytool research-marker-queue index-done
python -m polytool research-marker-queue index-done --force
python -m polytool research-marker-queue index-done --json
python -m polytool research-marker-queue --queue-dir PATH index-done
```

Exit code: 0 unless there are hard failures (`failed` list non-empty).
Empty/skipped/no-body results are all rc=0.

---

## Tests Run and Results

```
pytest tests/test_ris_marker_queue.py tests/test_research_query.py tests/test_academic_harvesters.py -q
231 passed, 1 skipped (Linux-only platform skip, correct on Windows)
```

New test classes:
- `TestPersistBodySidecar` (7 tests) — body.txt and meta.json written on success; not written on failure/pdfplumber/short; overwritten on re-process
- `TestIndexDoneItems` (9 tests) — happy path; failed/pdfplumber not indexed; missing body reported; idempotency; force reindexes; indexed.jsonl written; multi-paper; E2E query (manually added claim verifying source_doc metadata)
- `TestCLIIndexDone` (5 tests) — help, empty queue, no-body warning, JSON output

---

## Operator Command Sequence

Full pipeline after this fix:

```bash
# 1. Discover
python -m polytool research-harvest --search "..." --source all

# 2. Label
python -m polytool research-prefetch-review label --id ID --label allow

# 3. Enqueue
python -m polytool research-marker-queue enqueue --url ARXIV_ID

# 4. Parse (Docker/GPU)
docker compose --profile ris-gpu run --rm ris-scheduler-gpu \
  python -m polytool research-marker-queue warm-process --max-items 5

# 4b. Index completed papers into KnowledgeStore
python -m polytool research-marker-queue index-done

# 5. Query
python -m polytool research-query --question "prediction markets"
```

---

## Smoke Test Result

Ran against `artifacts/research/operator_test_queue_direct` (arxiv:2604.24366,
`marker_ready=True`, processed before this fix — no body sidecar):

```
$ python -m polytool research-marker-queue --queue-dir artifacts/research/operator_test_queue_direct index-done

Indexing marker-ready done items into KnowledgeStore...

Skipped 1 paper(s) — body file missing:
  [no-body] arxiv:2604.24366  (re-enqueue with --force to re-process)

Total: 1 done item(s) examined — 0 indexed, 0 already-indexed, 1 no-body, 0 failed.
```

Correct behavior: pre-fix items report `no-body` and show the recovery path.
To index this paper: `research-marker-queue enqueue --url 2604.24366 --force`
then `warm-process` (requires Docker/GPU), then `index-done`.

---

## Remaining Blockers

1. **Pre-fix done items lack body sidecars.** Must be re-processed through `warm-process`
   (Docker/GPU required) to create the sidecar files before `index-done` can index them.

2. **Claim extraction.** `IngestPipeline.ingest_external` stores the source document
   but does not extract claims (the claim extractor reads body text from
   `metadata_json["body"]` or a `file://` source_url — neither is set by the academic
   adapter). Claims must be added separately (e.g. via `research-ingest` with the full
   acquire path, or a future `index-done --extract-claims` flag). For now, `research-query`
   will return the paper in citations once at least one claim is linked to the doc_id.
   This matches the pattern of all existing L2 tests which inject claims manually.

3. **ChromaDB academic path** (L2.1): `body_source` is not in Chroma chunk metadata;
   semantic search over academic papers is still deferred.

---

## Codex Review Summary

Tier: skip — no execution, kill-switch, risk-manager, or rate-limiter files touched.
Changes are purely in queue ingestion, CLI, tests, and docs.
