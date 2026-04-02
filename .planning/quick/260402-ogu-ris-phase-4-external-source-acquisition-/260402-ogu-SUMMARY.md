---
phase: quick-260402-ogu
plan: "01"
subsystem: research-ingestion
tags: [ris, ingestion, adapters, source-cache, normalization, phase4]
dependency_graph:
  requires:
    - packages/research/ingestion/extractors.py (ExtractedDocument)
    - packages/research/ingestion/pipeline.py (IngestPipeline)
    - packages/research/evaluation/hard_stops.py
    - packages/polymarket/rag/knowledge_store.py (KnowledgeStore)
  provides:
    - packages/research/ingestion/source_cache.py (RawSourceCache, make_source_id)
    - packages/research/ingestion/normalize.py (NormalizedMetadata, canonicalize_url, extract_canonical_ids)
    - packages/research/ingestion/adapters.py (SourceAdapter ABC, AcademicAdapter, GithubAdapter, BlogNewsAdapter, ADAPTER_REGISTRY)
    - packages/research/ingestion/pipeline.py:ingest_external()
    - tools/cli/research_ingest.py:--from-adapter path
  affects:
    - packages/research/ingestion/__init__.py (new Phase 4 exports)
    - docs/CURRENT_STATE.md
tech_stack:
  added:
    - hashlib SHA-256 for deterministic source IDs
  patterns:
    - Adapter ABC pattern (SourceAdapter -> AcademicAdapter, GithubAdapter, BlogNewsAdapter)
    - Envelope format for raw payload caching {source_id, source_family, cached_at, payload}
    - Registry pattern (ADAPTER_REGISTRY dict + get_adapter() factory)
    - Canonical ID extraction via regex (DOI, arXiv ID, SSRN ID, GitHub repo URL)
    - URL canonicalization (fragment stripping, arXiv pdf->abs, GitHub tree/blob suffix removal)
    - News vs blog heuristic via known news domain set
key_files:
  created:
    - packages/research/ingestion/source_cache.py
    - packages/research/ingestion/normalize.py
    - packages/research/ingestion/adapters.py
    - tests/fixtures/ris_external_sources/arxiv_sample.json
    - tests/fixtures/ris_external_sources/github_sample.json
    - tests/fixtures/ris_external_sources/blog_sample.json
    - tests/test_ris_phase4_source_acquisition.py
    - docs/features/FEATURE-ris-phase4-source-acquisition.md
    - docs/dev_logs/2026-04-02_ris_phase4_source_acquisition.md
  modified:
    - packages/research/ingestion/pipeline.py (added ingest_external())
    - packages/research/ingestion/__init__.py (Phase 4 exports)
    - tools/cli/research_ingest.py (--from-adapter, --source-family, --cache-dir flags)
    - docs/CURRENT_STATE.md (RIS Phase 4 section)
decisions:
  - "Adapter.adapt() returns ExtractedDocument directly (not NormalizedMetadata) to stay compatible with existing pipeline without a translation layer"
  - "Source IDs are sha256(canonical_url)[:16] — 16-char hex provides determinism + low collision risk for file naming"
  - "ingest_external() uses late import of ADAPTER_REGISTRY to avoid circular import at module load time"
  - "Blog vs news heuristic uses frozenset of known news domains in normalize.py; BlogNewsAdapter imports it to avoid duplication"
  - "AcademicAdapter source_type inference: arxiv.org URL -> arxiv, ssrn.com URL -> ssrn, default -> book"
  - "Adapters are fixture-backed only (no HTTP client); future scraper modules produce same raw dicts and pass to adapters"
metrics:
  duration: "~25 minutes"
  tasks_completed: 2
  files_changed: 11
  tests_added: 49
  completed_date: "2026-04-02"
---

# Phase quick-260402-ogu Plan 01: RIS Phase 4 External Source Acquisition Summary

## One-liner

Disk-backed raw-source caching, SourceAdapter ABC with three family implementations (academic/github/blog-news), URL canonicalization and canonical ID extraction, and IngestPipeline.ingest_external() wiring fixture-backed external sources into the full adapter -> cache -> normalize -> eval -> store pipeline.

## What Was Built

### RawSourceCache (`packages/research/ingestion/source_cache.py`)

Disk-backed preservation of original source payloads before any processing.

- `make_source_id(canonical_url) -> str`: deterministic `sha256(url)[:16]` source ID
- `cache_raw(source_id, payload, source_family) -> Path`: writes `{cache_dir}/{family}/{source_id}.json`
- `get_raw(source_id, source_family) -> Optional[dict]`: reads cached envelope
- `has_raw(source_id, source_family) -> bool`: existence check
- Envelope format: `{source_id, source_family, cached_at (UTC ISO), payload}`
- Disk layout: `{cache_dir}/{source_family}/{source_id}.json` — family isolation

### Metadata Normalization (`packages/research/ingestion/normalize.py`)

- `NormalizedMetadata` dataclass: canonical_url, title, author, publish_date, source_family, source_type, canonical_ids, publisher, raw_metadata
- `canonicalize_url(url) -> str`: strip fragment, trailing slash, lowercase scheme+host, arXiv pdf->abs, GitHub tree/blob/commit suffix removal
- `extract_canonical_ids(text, url) -> dict`: DOI (`10.NNNN/...`), arXiv ID (`YYMM.NNNNN`), SSRN ID, GitHub repo URL
- `normalize_metadata(raw, source_family) -> NormalizedMetadata`: family-specific field mapping

### Source Adapters (`packages/research/ingestion/adapters.py`)

- `SourceAdapter` ABC with `adapt(raw_source, cache=None) -> ExtractedDocument`
- `AcademicAdapter`: url, title, abstract, authors, published_date, body_text; source_type: arxiv/ssrn/book
- `GithubAdapter`: repo_url, readme_text, description, stars, forks, license, last_commit_date; title from owner/repo
- `BlogNewsAdapter`: url, title, body_text, author, published_date, publisher; news/blog heuristic from domain set
- `ADAPTER_REGISTRY`: `{"academic": AcademicAdapter, "github": GithubAdapter, "blog": BlogNewsAdapter, "news": BlogNewsAdapter}`
- `get_adapter(family) -> SourceAdapter`: factory function

### Pipeline Extension (`packages/research/ingestion/pipeline.py`)

`IngestPipeline.ingest_external(raw_source, source_family, *, cache=None, **kwargs) -> IngestResult`:
- Validates source_family against ADAPTER_REGISTRY; returns rejected=True on unknown family
- Calls adapter.adapt(raw_source, cache=cache) -> ExtractedDocument
- Continues through standard pipeline: hard-stop -> eval gate -> chunk -> store
- Catches adapter errors (ValueError, KeyError, TypeError) and returns rejected=True

### CLI Extension (`tools/cli/research_ingest.py`)

- `--from-adapter JSON_PATH`: path to raw-source JSON file
- `--source-family FAMILY` (choices: academic/github/blog/news)
- `--cache-dir PATH` (default: artifacts/research/raw_source_cache/)

## Test Results

| Suite | Tests | Status |
|-------|-------|--------|
| TestRawSourceCache | 7 | PASS |
| TestNormalization | 14 | PASS |
| TestAcademicAdapter | 7 | PASS |
| TestGithubAdapter | 4 | PASS |
| TestBlogNewsAdapter | 5 | PASS |
| TestAdapterRegistry | 5 | PASS |
| TestEndToEnd | 7 | PASS |
| **Phase 4 total** | **49** | **PASS** |
| Full regression | 2009 | PASS |
| Pre-existing failures | 1 | (test_normative_recommend — another agent's work, unrelated) |

## CLI Smoke Test

```
$ python -m polytool research-ingest \
    --from-adapter tests/fixtures/ris_external_sources/arxiv_sample.json \
    --source-family academic --no-eval --json
{
  "doc_id": "d744370bac4412c936a66004d3875e1789aee9bd7e44099dd5aaac2232360ba5",
  "chunk_count": 1,
  "rejected": false,
  "reject_reason": null,
  "gate": "skipped"
}
```

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| Task 1 (RED+GREEN) | `59efca5` | RIS Phase 4 source cache, normalization, adapters + fixtures |
| Task 2 (wiring + docs) | `94c184e` | Wire pipeline/CLI/docs for RIS Phase 4 (via 92f9b15 + CURRENT_STATE) |

Note: pipeline.py, __init__.py, research_ingest.py, feature doc, and dev log were committed as part of `92f9b15` by a parallel agent (260402-ogq) that ran concurrently. CURRENT_STATE.md update committed in `94c184e` to complete this plan's scope.

## Deviations from Plan

None — plan executed exactly as written. All 49 tests pass. All required artifacts created.

## Known Stubs

None. The adapter path is fixture-backed by design (no live HTTP client). Future scraper modules will produce the same raw dicts and pass them to adapters — this is the intended contract, not a stub.

## What Remains Deferred

1. Live HTTP client: adapters accept pre-fetched dicts only. Future scraper module will fetch from URLs and pass raw dicts to adapters.
2. Scraper orchestration: no scheduler, n8n, or polling loop.
3. `forum_social` family: reddit, twitter, youtube not yet adapter-backed.
4. Dedup integration: canonical_ids extracted and stored in metadata but not yet wired to near-duplicate check (which uses content hash + shingles).
5. Rate limiting: N/A until live scraping is added.

## Self-Check: PASSED

- [x] `packages/research/ingestion/source_cache.py` — exists
- [x] `packages/research/ingestion/normalize.py` — exists
- [x] `packages/research/ingestion/adapters.py` — exists
- [x] `tests/test_ris_phase4_source_acquisition.py` — exists
- [x] `docs/features/FEATURE-ris-phase4-source-acquisition.md` — exists
- [x] `docs/dev_logs/2026-04-02_ris_phase4_source_acquisition.md` — exists
- [x] commit `59efca5` — exists
- [x] commit `94c184e` — exists
