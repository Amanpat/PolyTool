# FEATURE: RIS Phase 4 — External Source Acquisition

## Status: Shipped (2026-04-02)

## What Shipped

### Core Modules

**`packages/research/ingestion/source_cache.py`** — RawSourceCache
- `RawSourceCache(cache_dir)`: disk-backed envelope storage
- `cache_raw(source_id, payload, source_family) -> Path`: writes `{cache_dir}/{family}/{source_id}.json`
- `get_raw(source_id, source_family) -> Optional[dict]`: reads cached envelope
- `has_raw(source_id, source_family) -> bool`: existence check
- `make_source_id(canonical_url) -> str`: deterministic sha256[:16] source ID
- Envelope format: `{source_id, source_family, cached_at (UTC ISO), payload}`
- All I/O uses UTF-8 encoding with `ensure_ascii=False`

**`packages/research/ingestion/normalize.py`** — Metadata Normalization
- `NormalizedMetadata` dataclass: canonical_url, title, author, publish_date, source_family, source_type, canonical_ids, publisher, raw_metadata
- `canonicalize_url(url) -> str`: strips fragments, trailing slashes, lowercases scheme+host, normalizes arXiv pdf->abs URLs, strips GitHub tree/blob/commit suffixes
- `extract_canonical_ids(text, url) -> dict`: extracts doi, arxiv_id, ssrn_id, repo_url
- `normalize_metadata(raw, source_family) -> NormalizedMetadata`: family-specific field mapping

**`packages/research/ingestion/adapters.py`** — Source Adapters
- `SourceAdapter` ABC: `adapt(raw_source, cache=None) -> ExtractedDocument`
- `AcademicAdapter`: handles arXiv/SSRN/book sources (url, title, abstract, authors, published_date, body_text)
- `GithubAdapter`: handles GitHub repos (repo_url, readme_text, description, stars, forks, license, last_commit_date)
- `BlogNewsAdapter`: handles blog posts and news articles (url, title, body_text, author, published_date, publisher)
- `ADAPTER_REGISTRY`: `{"academic": AcademicAdapter, "github": GithubAdapter, "blog": BlogNewsAdapter, "news": BlogNewsAdapter}`
- `get_adapter(family) -> SourceAdapter`: factory function

### Pipeline Extension

**`packages/research/ingestion/pipeline.py`** — `IngestPipeline.ingest_external()`
- Signature: `ingest_external(raw_source, source_family, *, cache=None, **kwargs) -> IngestResult`
- Validates source_family against ADAPTER_REGISTRY
- Calls adapter.adapt(raw_source, cache=cache) -> ExtractedDocument
- Continues through standard pipeline: hard-stop -> eval gate -> chunk -> store
- Returns rejected=True with clear reason on unknown family or adapter error

### CLI Extension

**`tools/cli/research_ingest.py`** — `--from-adapter` path
- `--from-adapter JSON_PATH`: path to raw-source JSON file
- `--source-family FAMILY`: required with --from-adapter (academic/github/blog/news)
- `--cache-dir PATH`: optional cache root (default: artifacts/research/raw_source_cache/)
- Workflow: load JSON -> create RawSourceCache -> pipeline.ingest_external()
- Output identical to existing --file/--text path (JSON or human-readable)

## Source Families Covered

| Family   | source_type      | Key canonical IDs |
|----------|------------------|-------------------|
| academic | arxiv / ssrn / book | doi, arxiv_id, ssrn_id |
| github   | github           | repo_url          |
| blog     | blog             | (URL normalized)  |
| news     | news             | (URL normalized)  |

News vs blog heuristic: known news domains (reuters.com, bloomberg.com, ft.com, wsj.com, etc.) receive source_type="news"; all others receive "blog".

## Canonical IDs Extracted

- **DOI**: regex `10.NNNN/...` from body text and URL
- **arXiv ID**: regex `arXiv:YYMM.NNNNN` from body text; also parsed from arxiv.org URL path
- **SSRN ID**: regex `SSRN:NNNNNN` from body text
- **GitHub repo URL**: `https://github.com/owner/repo` normalized from URL or text

## Raw-Source Caching: Disk Layout

```
artifacts/research/raw_source_cache/
  academic/
    <sha256[:16]>.json    # envelope {source_id, source_family, cached_at, payload}
  github/
    <sha256[:16]>.json
  blog/
    <sha256[:16]>.json
  news/
    <sha256[:16]>.json
```

Cache is written before any processing so the original payload is always recoverable.

## Fixtures (Offline Testing)

All fixtures live under `tests/fixtures/ris_external_sources/`:
- `arxiv_sample.json`: realistic arXiv-style source with DOI, arXiv ID, SSRN companion ref, methodology cues
- `github_sample.json`: realistic GitHub repo source (py-clob-client) with readme, stars, forks, license
- `blog_sample.json`: realistic blog post with author, publisher, published_date

## CLI Example

```bash
# Ingest an arXiv-style source fixture
python -m polytool research-ingest \
  --from-adapter tests/fixtures/ris_external_sources/arxiv_sample.json \
  --source-family academic \
  --no-eval \
  --json

# Output:
# {
#   "doc_id": "d744370bac4412c9...",
#   "chunk_count": 1,
#   "rejected": false,
#   "reject_reason": null,
#   "gate": "skipped"
# }

# With raw-source caching to disk
python -m polytool research-ingest \
  --from-adapter tests/fixtures/ris_external_sources/github_sample.json \
  --source-family github \
  --cache-dir artifacts/research/raw_source_cache/ \
  --no-eval
```

## What Remains Deferred

- **Live HTTP fetching**: adapters are fixture-backed only. Future scraper modules will produce the same raw dicts and pass them to adapters.
- **Scraper orchestration**: no scheduler, n8n, or HTTP client layer yet (Phase 3+ deliverable).
- **Additional source families**: `forum_social` (reddit, twitter, youtube), `dossier`, `manual` — not adapter-backed yet.
- **Dedup integration**: canonical_ids are extracted and stored in metadata but not yet wired to the dedup check (near-duplicate detection uses content hash and shingles).
- **Rate limiting / politeness**: N/A until live scraping is added.

## Tests

- `tests/test_ris_phase4_source_acquisition.py`: 49 tests
  - TestRawSourceCache: 7 tests
  - TestNormalization: 14 tests
  - TestAcademicAdapter: 7 tests
  - TestGithubAdapter: 4 tests
  - TestBlogNewsAdapter: 5 tests
  - TestAdapterRegistry: 5 tests
  - TestEndToEnd: 7 tests
- All 49 pass; zero regressions in existing suite
