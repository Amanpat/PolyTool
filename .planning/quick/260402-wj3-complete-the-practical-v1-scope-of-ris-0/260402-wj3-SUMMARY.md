---
phase: quick-260402-wj3
plan: 01
subsystem: ris-ingestion
tags: [ris, academic, arxiv, book, claim-extraction, cli]
dependency_graph:
  requires: [quick-260402-rm1, quick-260402-ogu]
  provides: [ArXiv topic search, BookAdapter, extract-claims CLI flag]
  affects: [research-ingest CLI, research-acquire CLI, IngestPipeline.ingest_external]
tech_stack:
  added: []
  patterns: [injectable _http_fn for offline testing, internal:// stable URL identity, non-fatal post-ingest extraction]
key_files:
  created:
    - packages/research/ingestion/adapters.py (BookAdapter, _slugify)
    - tests/test_ris_academic_ingest_v1.py
    - tests/fixtures/ris_external_sources/book_sample.json
    - docs/features/FEATURE-ris-academic-ingest-v1.md
    - docs/dev_logs/2026-04-02_ris_r1_academic_ingestion_completion.md
  modified:
    - packages/research/ingestion/fetchers.py (search_by_topic)
    - packages/research/ingestion/normalize.py (canonicalize_url guard)
    - packages/research/ingestion/pipeline.py (ingest_external post_ingest_extract)
    - tools/cli/research_ingest.py (--extract-claims, book family)
    - tools/cli/research_acquire.py (--search, --extract-claims, book family — wired in wj9-02)
    - docs/CURRENT_STATE.md
decisions:
  - "BookAdapter uses internal:// stable URL identity (not SHA of content) so book_id+chapter reruns produce same canonical_url for dedup"
  - "canonicalize_url guard uses url.lower() check (case-insensitive) to avoid regression on HTTPS:// uppercase URLs"
  - "SSRN live scraper deferred — SSRN blocks automated crawlers; URL-pattern source_type detection is sufficient for manual --from-adapter path"
  - "search_by_topic returns [] on empty feed rather than FetchError — consistent with semantics: zero results is valid, not an error"
metrics:
  duration: ~35 minutes
  completed: "2026-04-03T03:44:00Z"
  tasks_completed: 2
  files_changed: 10
---

# Phase quick-260402-wj3 Plan 01: Complete RIS_01 Academic Ingestion Pipeline v1 Summary

## One-liner

ArXiv topic search, BookAdapter with stable book_id/chapter identity, --extract-claims CLI flags, and truthful SSRN deferred documentation close the practical v1 scope of RIS_01.

## Tasks Completed

| Task | Name | Commit | Key Files |
|------|------|--------|-----------|
| 1 | ArXiv topic search + BookAdapter + ingest_external claim extraction | 4c33f27 | fetchers.py, adapters.py, normalize.py, pipeline.py, book_sample.json, test_ris_academic_ingest_v1.py |
| 2 | CLI --search and --extract-claims flags + docs + dev log | c6016ae | research_ingest.py, normalize.py (fix), FEATURE doc, dev log, CURRENT_STATE.md |

## What Was Built

### Task 1

**`LiveAcademicFetcher.search_by_topic(query, max_results=5) -> list[dict]`**
- ArXiv Atom search API: `http://export.arxiv.org/api/query?search_query=all:{encoded}&max_results={n}`
- Parses all `atom:entry` elements; returns same dict structure as `fetch()`
- Returns `[]` on empty feed, raises `FetchError` on network failure
- `_http_fn` injectable for offline testing

**`BookAdapter`** (registered as `ADAPTER_REGISTRY["book"]`)
- Stable `canonical_url = "internal://book/{book_id}/{chapter_or_section_slug}"`
- `_slugify()`: lowercase + replace non-alnum with `_` + strip/collapse
- `canonical_ids = {"book_id": book_id}` for metadata traceability
- No live fetcher (books are local fixtures / manual dicts)

**`canonicalize_url()` guard**
- Non-HTTP(S) URLs (`internal://`) pass through unchanged
- Guard uses `url.lower()` for case-insensitive check

**`IngestPipeline.ingest_external()` extension**
- `post_ingest_extract: bool = False` kwarg added
- Non-fatal claim extraction block (same pattern as `ingest()`)

**26 offline tests** in `tests/test_ris_academic_ingest_v1.py`:
- TestSearchByTopic (7), TestBookAdapter (12), TestIngestExternalWithExtractClaims (4), TestBookSampleFixture (3)

### Task 2

**`research-ingest` CLI extensions:**
- `--extract-claims`: wired to `post_ingest_extract` on both adapter path and file/text path
- `"book"` added to `--source-family` choices

**`research-acquire` CLI extensions** (committed in wj9-02 / a332abf):
- `--search QUERY` + `--max-results N` for ArXiv topic search
- `--extract-claims` flag

**Documentation:**
- `docs/features/FEATURE-ris-academic-ingest-v1.md` — complete v1 feature doc with SSRN deferred status
- `docs/dev_logs/2026-04-02_ris_r1_academic_ingestion_completion.md` — dev log with exact counts
- `docs/CURRENT_STATE.md` — brief wj3 bullet

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] canonicalize_url case-insensitive guard**
- **Found during:** Task 1 test `test_canonicalize_url_lowercases_scheme_host`
- **Issue:** Original guard used `url.startswith("http://")` which is case-sensitive; `HTTPS://ArXiv.ORG/...` would skip lowercasing
- **Fix:** Use `url_lower = url.lower()` for the startswith check
- **Files modified:** `packages/research/ingestion/normalize.py`
- **Commit:** c6016ae

**2. [Note] research_acquire.py already committed by wj9**
- `research_acquire.py` Task 2 changes (--search, --extract-claims, --source-family reddit/youtube) were committed in `a332abf` by the concurrent wj9 agent before this session resumed
- No duplication or conflict; wj3 Task 2 CLI work was limited to `research_ingest.py`

## Known Stubs

None. All shipped functionality is fully wired. SSRN deferred status is explicit documentation, not a stub.

## Verification

### Final test results
- `tests/test_ris_academic_ingest_v1.py`: 26 passed, 0 failed
- Full regression: 3405 passed, 3 deselected, 0 failed

### CLI smoke tests
```
python -m polytool research-ingest \
  --from-adapter tests/fixtures/ris_external_sources/book_sample.json \
  --source-family book --no-eval --json
# {"doc_id": "2053fbc7aee79885...", "chunk_count": 1, "rejected": false}

python -m polytool research-ingest --help | grep extract-claims
# [--extract-claims]

python -m polytool research-acquire --help | grep extract-claims
# [--extract-claims]
```

## Self-Check: PASSED

- [x] `packages/research/ingestion/fetchers.py` — search_by_topic exists
- [x] `packages/research/ingestion/adapters.py` — BookAdapter + ADAPTER_REGISTRY["book"]
- [x] `packages/research/ingestion/pipeline.py` — post_ingest_extract kwarg
- [x] `tests/test_ris_academic_ingest_v1.py` — 26 tests, all pass
- [x] `tests/fixtures/ris_external_sources/book_sample.json` — exists
- [x] `docs/features/FEATURE-ris-academic-ingest-v1.md` — created
- [x] `docs/dev_logs/2026-04-02_ris_r1_academic_ingestion_completion.md` — created
- [x] Commits 4c33f27 and c6016ae exist
