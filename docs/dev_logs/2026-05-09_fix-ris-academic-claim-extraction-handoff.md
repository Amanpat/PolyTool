# Fix: RIS Academic Claim Extraction Handoff

**Date:** 2026-05-09
**Objective:** Close the final gap between a Marker-indexed academic paper and
`research-query` returning citations — without manually injecting claims.

---

## Root Cause

`index_done_items` stored source documents in the KnowledgeStore but the heuristic
claim extractor (`_get_document_body`) could not find the body text. It has two
strategies: (1) `metadata_json["body"]` inline, and (2) a `file://` source_url.

The `AcademicAdapter` sets `source_url` to the arXiv URL (not a file path) and
does not copy inline body text into `metadata_json`, so both strategies returned
`None`. Result: `extract_claims_from_document` always returned `[]` for academic
documents, so `research-query` found no claims and returned `had_fallback=True`.

The body text already existed on disk as a body sidecar
(`bodies/{candidate_id}.body.txt`) written during `warm-process` — it just had
no pointer stored in the KnowledgeStore.

---

## Files Changed

| File | Change |
|------|--------|
| `packages/research/ingestion/claim_extractor.py` | Added Strategy 1.5 to `_get_document_body`: reads `metadata_json["body_file"]` as a file:// path to the Marker body sidecar |
| `packages/research/ingestion/adapters.py` | Added `"body_file"` to `AcademicAdapter`'s pass-through key list so the file:// pointer survives into stored `metadata_json` |
| `packages/research/ingestion/marker_queue.py` | Added `body_file` URI to `raw_source` dict; added `extract_claims: bool = True` param; auto-runs `extract_and_link` after each successful ingest; tracks `claims_extracted` per paper and `total_claims_extracted` in summary |
| `tools/cli/research_marker_queue.py` | Added `--no-extract-claims` flag to `index-done`; updated output to show claims extracted per paper |
| `tests/test_ris_claim_extraction.py` | Added `TestAcademicBodyFileStrategy` (5 tests) and `TestIndexDoneClaimExtraction` (5 tests) |
| `docs/runbooks/RIS_MARKER_QUEUE_RUNBOOK.md` | Updated Step 4b and Quick start to reflect automatic claim extraction in `index-done` |

---

## Implementation

### Strategy 1.5 in `_get_document_body`

`_get_document_body` now parses `metadata_json` once and checks three strategies
in order:
1. `metadata_json["body"]` — inline body (tests, legacy)
1.5. `metadata_json["body_file"]` — file:// pointer to Marker body sidecar (**new**)
2. `file://` source_url — file-backed docs

The file:// prefix is stripped before passing to `Path`, which handles both POSIX
(`file:///home/user/file.txt` → `/home/user/file.txt`) and Windows
(`file://D:/path/file.txt` → `D:/path/file.txt`) correctly.

### body_file URI stored at index time

`index_done_items` now adds `"body_file": f"file://{body_file.resolve().as_posix()}"`
to `raw_source` before calling `ingest_external`. `AcademicAdapter.adapt()` passes
`body_file` through to `metadata` (new entry in the for-loop), so it survives in
the stored `metadata_json`. No body text duplication occurs in the DB.

### Automatic claim extraction in `index_done_items`

After each successful ingest, if `extract_claims=True` (default):
- `extract_and_link(store, doc_id)` is called
- Claims are written via INSERT OR IGNORE (idempotent)
- Failure is non-fatal: logged as warning, paper still recorded as indexed
- `claims_extracted` count added to each `indexed` entry and summed in `total_claims_extracted`

### Operator command sequence (updated)

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

# 4b. Index + extract claims (single step, no separate claim extraction command)
python -m polytool research-marker-queue index-done

# 5. Query — returns citations immediately after step 4b
python -m polytool research-query --question "prediction markets"
```

---

## Tests Run and Results

```
pytest tests/test_ris_marker_queue.py tests/test_research_query.py tests/test_ris_claim_extraction.py -q
236 passed, 3 failed (pre-existing), 1 skipped
```

**New test classes:**

- `TestAcademicBodyFileStrategy` (5 tests):
  - body_file pointer produces claims
  - missing body_file produces no claims
  - no body_file + no inline body produces no claims
  - body_file extraction is idempotent
  - inline body (Strategy 1) takes priority over body_file (Strategy 1.5)

- `TestIndexDoneClaimExtraction` (5 tests):
  - `extract_claims=True` produces claims per indexed paper
  - `extract_claims=False` skips extraction (0 claims, doc still indexed)
  - pdfplumber result (marker_ready=False) is never indexed or claimed
  - E2E: `index_done(extract_claims=True)` → `query_academic_corpus` returns citation
  - Re-running `index_done` is idempotent (skips already-indexed, no duplicate claims)

**Pre-existing failures (actor-string regression, NOT fixed per task instructions):**

- `TestExtractClaimsFromDocument::test_each_claim_has_required_fields` — expects
  `actor == "heuristic_v1"`, code has `EXTRACTOR_ID = "heuristic_v2_nofrontmatter"`
- `TestExtractClaimsFromDocument::test_notes_json_has_extraction_context` — same
- `TestHeuristicClaimExtractorClass::test_class_exists_and_has_expected_interface` — same

These three failures pre-date this work packet and are not caused by any change here.

---

## Smoke Result

CLI help verified:
```
$ python -m polytool research-marker-queue index-done --help
options:
  --no-extract-claims  Skip automatic claim extraction after indexing.
                       Default: extract claims from each indexed paper via body_file sidecar.
```

E2E test (`test_e2e_index_extract_query`) passes:
- Marker-ready queue fixture with `_LONG_ACADEMIC_BODY` (FIXTURE_MARKDOWN × 7 ≈ 5845 chars)
- `index_done(extract_claims=True)` → 1 paper indexed, ≥1 claim extracted
- `query_academic_corpus("momentum")` → `had_fallback=False`, ≥1 citation, `body_source="marker"`

---

## Remaining Blockers

1. **Pre-fix queue items still lack body sidecars.** Papers processed before
   2026-05-09 (the body-sidecar fix) have no `bodies/` files. `index-done` reports
   them as `no-body`. Recovery: `enqueue --force` + `warm-process` + `index-done`.

2. **ChromaDB academic path (L2.1) still deferred.** `body_source` is not in Chroma
   chunk metadata; semantic vector search over academic papers remains a future task.

3. **Pre-existing actor-string test failures.** `EXTRACTOR_ID` changed from
   `"heuristic_v1"` to `"heuristic_v2_nofrontmatter"` but 3 tests still assert `v1`.
   Fix: update the 3 assertion strings in `test_ris_claim_extraction.py` to
   `"heuristic_v2_nofrontmatter"`. Left unfixed per task instructions.

---

## Codex Review Summary

Tier: skip — no execution, kill-switch, risk-manager, or rate-limiter files touched.
Changes are in queue ingestion, claim extraction, CLI, tests, and docs.
