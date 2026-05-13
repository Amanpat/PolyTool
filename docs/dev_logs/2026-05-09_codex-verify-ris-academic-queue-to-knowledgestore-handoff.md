# Codex Verify — RIS Academic Queue-to-KnowledgeStore Handoff

**Date:** 2026-05-09
**Verdict:** PASS

---

## What Was Verified

The RIS queue-to-KnowledgeStore handoff fix implemented in
`docs/dev_logs/2026-05-09_fix-ris-academic-queue-to-knowledgestore-handoff.md`.

---

## Root Cause Confirmation

Reviewed `packages/research/ingestion/marker_queue.py`. The original `_process_item()`
called `fetcher.fetch()` which returned a dict containing `body_text`, but only
`body_source`, `body_length`, and `parse_seconds` were captured. `body_text` was
discarded. After `warm-process`, no body text was persisted, making KS indexing
impossible without re-running Marker.

The fix adds `_persist_body_sidecar()` called from `_process_item()` when
`marker_ready=True`, writing:
- `bodies/{candidate_id}.body.txt` — raw Marker body
- `bodies/{candidate_id}.meta.json` — fetch metadata (no body_text, stored separately)

And `index_done_items()` reads those sidecars and calls
`IngestPipeline.ingest_external(raw_source, "academic")`.

**Root cause matches code and dev log. Confirmed.**

---

## Tests Run

```
pytest tests/test_ris_marker_queue.py tests/test_research_query.py tests/test_academic_harvesters.py -q --tb=short
231 passed, 1 skipped (Linux-only platform skip, correct on Windows)
```

New test coverage (135 collected in marker queue file):
- `TestPersistBodySidecar` — body.txt/meta.json written on success, not on failure/pdfplumber/short
- `TestIndexDoneItems` — happy path, gate rejection, missing body, idempotency, force, indexed.jsonl, multi-paper, E2E query
- `TestCLIIndexDone` — help, empty queue, no-body warning, JSON output

---

## Gate Verification

**Only `marker_ready=True` items enter the candidate pool:**

```python
marker_ready_done = {
    cid: rec
    for cid, rec in best_results.items()
    if rec.get("marker_ready") and rec.get("queue_status") == "done"
}
```

Test: injected a pdfplumber result (`marker_ready=False, queue_status=failed`) with a
body sidecar manually created. `index_done_items` correctly returned all-empty summary
(pdfplumber excluded at pool level, not even in `skipped_no_body`).

**Output:** `{"indexed":[],"skipped_already_indexed":[],"skipped_no_body":[],"failed":[]}`
**PASS: pdfplumber gate holds.**

**IngestPipeline also enforces the Marker gate** (`academic_marker_gate` in
`pipeline.py:ingest_external`) so even if a caller constructed a raw_source dict with
`body_source=pdfplumber_fallback`, it would be rejected.

---

## Idempotency Verification

Three calls on the same queue:

```
Call 1: {"indexed": [{"candidate_id": "arxiv:2604.24366", "doc_id": "...", "chunk_count": 4}]}
Call 2: {"skipped_already_indexed": ["arxiv:2604.24366"]}
Call 3 (force): {"indexed": [{"candidate_id": "arxiv:2604.24366", ...}]}
```

**PASS: idempotency confirmed via `indexed.jsonl` tracking.**

---

## E2E Synthetic Smoke (queue→index→query)

Built a synthetic queue in a temp directory with:
- `queue.jsonl`: status=done record
- `results.jsonl`: `marker_ready=True, body_source=marker, body_length=52500`
- `bodies/arxiv:2604.24366.body.txt`: synthetic Marker body (~52K chars)
- `bodies/arxiv:2604.24366.meta.json`: fetch metadata

Ran `index_done_items(_store=KnowledgeStore(':memory:'))`:

```
INDEX SUMMARY:
  indexed: [{"candidate_id": "arxiv:2604.24366", "doc_id": "3ed8c083...", "chunk_count": 18}]
  skipped_already_indexed: []
  skipped_no_body: []
  failed: []

SOURCE DOC:
  title: Anatomy of a Decentralized Prediction Market
  source_family: academic
  body_source: marker
  body_length: 52500
  chunk_count: 18
```

Added one claim linked to `doc_id`, then ran `query_academic_corpus`:

```
QUERY RESULT:
  had_fallback: False
  citations: 1
  citation[0].title: Anatomy of a Decentralized Prediction Market
  citation[0].body_source: marker
  citation[0].arxiv_id: 2604.24366
```

**PASS: full queue→index→query flow works end-to-end.**

---

## Real Operator Queue Smoke

Ran against `artifacts/research/operator_test_queue_direct` (arxiv:2604.24366,
processed before the fix — no body sidecar):

```
$ python -m polytool research-marker-queue --queue-dir artifacts/research/operator_test_queue_direct index-done --json

{
  "indexed": [],
  "skipped_already_indexed": [],
  "skipped_no_body": ["arxiv:2604.24366"],
  "failed": []
}
```

**Expected behavior.** Pre-fix items lack body sidecars. The command correctly
identifies them as `skipped_no_body` and exits 0 (no failures). Recovery:
`enqueue --force` → `warm-process` (Docker/GPU) → `index-done`.

```
$ python -m polytool research-query --question "prediction markets"
{"had_fallback": true, ...}
```

**Expected behavior.** No academic docs in the real KS. The warning message
correctly instructs the operator to run `research-marker-queue enqueue`.

---

## Runbook Verification

`docs/runbooks/RIS_MARKER_QUEUE_RUNBOOK.md` reviewed. Contains:
- Updated pipeline diagram showing body sidecar persistence and index step
- Step 4b: `python -m polytool research-marker-queue index-done`
- Body-missing recovery path (`enqueue --force` → `warm-process` → `index-done`)
- Updated query prerequisite pointing to `index-done`
- Output artifact table (`bodies/`, `indexed.jsonl`)

**5-step operator sequence confirmed present.**

---

## CLI Verification

```
$ python -m polytool research-marker-queue --help
  {enqueue,list,process,warm-process,index-done,counts}

$ python -m polytool research-marker-queue index-done --help
  --ks-path PATH  Override KnowledgeStore SQLite path
  --force         Re-index even items already recorded in indexed.jsonl
  --json          Output summary as JSON
```

**PASS: `index-done` appears in top-level help and subcommand help is correct.**

---

## Fixes Made

None. Implementation verified as correct. No small blockers found.

---

## Files Reviewed

| File | Verdict |
|------|---------|
| `packages/research/ingestion/marker_queue.py` | PASS — `_persist_body_sidecar`, `_read_best_results`, `index_done_items`, `_process_item` all correct |
| `tools/cli/research_marker_queue.py` | PASS — `_cmd_index_done`, `index-done` subparser, `main()` wiring correct |
| `tests/test_ris_marker_queue.py` | PASS — 134 pass, 1 skip (Linux); 20 new tests cover all scenarios |
| `tests/test_research_query.py` | PASS — 36 pass, no regressions |
| `tests/test_academic_harvesters.py` | PASS — 61 pass, no regressions |
| `docs/runbooks/RIS_MARKER_QUEUE_RUNBOOK.md` | PASS — Step 4b present, pipeline diagram updated |
| `docs/dev_logs/2026-05-09_fix-ris-academic-queue-to-knowledgestore-handoff.md` | PASS — root cause, implementation, and blockers accurate |

---

## Remaining Blockers (carried from implementation dev log)

1. **Pre-fix done items lack body sidecars.** Must re-process through `warm-process`
   (Docker/GPU) to create sidecars. This is a known operator action, not a code bug.

2. **Claim extraction.** `IngestPipeline.ingest_external` indexes the source document
   but the claim extractor cannot retrieve the body text (reads from `metadata_json["body"]`
   or `file://` URL — neither set by AcademicAdapter). Claims must be added separately.
   `research-query` returns the paper in citations only once a claim is linked to its
   `doc_id`. This is the same limitation as all existing L2 tests (which inject claims
   manually). A future `index-done --extract-claims` flag or a body-aware AcademicAdapter
   would close this gap.

3. **ChromaDB academic path** (L2.1): `body_source` not in Chroma chunk metadata;
   semantic search over academic papers remains deferred.

---

## Final Verdict

**PASS.**

The queue-to-KnowledgeStore handoff is correctly implemented and verified:
- Body sidecar persistence during `warm-process` ✓
- `index-done` CLI indexes only Marker-ready (`body_source=marker, marker_ready=True`) docs ✓
- pdfplumber/marker_failed/short bodies excluded at pool level (marker_ready gate) ✓
- Idempotency via `indexed.jsonl` ✓
- `research-query` returns correct citations for indexed papers (with manual claim) ✓
- Pre-fix done items report `skipped_no_body` with actionable recovery message ✓
- Runbook has exact 5-step operator command sequence ✓
- 231 tests pass, 1 skipped (correct Linux-only skip) ✓
