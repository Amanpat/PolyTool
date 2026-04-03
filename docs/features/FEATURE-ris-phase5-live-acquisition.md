# FEATURE: RIS Phase 5 — Live Source Acquisition Adapters

**Status:** Shipped (2026-04-02)
**Plan:** quick-260402-rm1
**Branch:** feat/ws-clob-feed

## Overview

RIS Phase 5 adds live HTTP acquisition adapters that fetch real external
sources, normalize their content into the adapter contract format, and ingest
them into the knowledge store — all triggered from a single CLI command.

The layer is stdlib-only (no new runtime dependencies), hermetically testable
via injectable `_http_fn` parameters, and writes an append-only JSONL audit log
of every acquisition attempt.

## CLI Usage

```bash
# Dry-run preview (no files written)
python -m polytool research-acquire \
  --url https://arxiv.org/abs/2301.12345 \
  --source-family academic \
  --dry-run --json --no-eval

# Full acquisition with evaluation gate skipped
python -m polytool research-acquire \
  --url https://arxiv.org/abs/2301.12345 \
  --source-family academic \
  --no-eval --json

# GitHub repo
python -m polytool research-acquire \
  --url https://github.com/polymarket/py-clob-client \
  --source-family github \
  --no-eval --json

# Blog/news article
python -m polytool research-acquire \
  --url https://blog.example.com/article \
  --source-family blog \
  --no-eval

# With evaluation provider
python -m polytool research-acquire \
  --url https://arxiv.org/abs/2301.12345 \
  --source-family academic \
  --provider ollama --json
```

## Supported Source Families

| Family | Fetcher class | HTTP endpoint | Key fields returned |
|---|---|---|---|
| `academic` | `LiveAcademicFetcher` | arXiv Atom API | url, title, abstract, authors, published_date |
| `github` | `LiveGitHubFetcher` | GitHub REST API | repo_url, readme_text, description, stars, forks, license, last_commit_date |
| `blog` | `LiveBlogFetcher` | Direct HTML fetch | url, title, body_text, author, published_date, publisher |
| `news` | `LiveBlogFetcher` | Direct HTML fetch | (same as blog) |

## Arguments

| Argument | Default | Description |
|---|---|---|
| `--url URL` | required | Source URL to fetch |
| `--source-family FAMILY` | required | One of: academic, github, blog, news |
| `--cache-dir PATH` | `artifacts/research/raw_source_cache` | Raw-source cache directory |
| `--review-dir PATH` | `artifacts/research/acquisition_reviews` | Acquisition review JSONL directory |
| `--db PATH` | system default | Knowledge store database path |
| `--no-eval` | off | Skip evaluation gate (hard-stop checks still run) |
| `--dry-run` | off | Fetch and normalize only; no caching, ingestion, or review |
| `--json` | off | Output JSON to stdout |
| `--provider NAME` | `manual` | Evaluation provider: manual or ollama |

## Return Codes

| Code | Meaning |
|---|---|
| 0 | Success (including dry-run) |
| 1 | Argument error (missing --url or --source-family) |
| 2 | Fetch error or ingest failure |

## Artifact Paths

| Artifact | Default location |
|---|---|
| Raw source cache | `artifacts/research/raw_source_cache/{family}/{source_id}.json` |
| Acquisition review log | `artifacts/research/acquisition_reviews/acquisition_review.jsonl` |

## JSON Output Schema (full flow)

```json
{
  "source_url": "https://arxiv.org/abs/2301.12345",
  "source_id": "abc123def456abcd",
  "source_family": "academic",
  "normalized_title": "Test Paper",
  "dedup_status": "new",
  "cached_path": "artifacts/research/raw_source_cache/academic/abc123def456abcd.json",
  "doc_id": "sha256-...",
  "chunk_count": 3,
  "rejected": false,
  "reject_reason": null
}
```

## Acquisition Review Record Schema

Each line in `acquisition_review.jsonl` is a JSON object with:

```json
{
  "acquired_at": "2026-04-02T10:00:00+00:00",
  "source_url": "https://arxiv.org/abs/2301.12345",
  "source_family": "academic",
  "source_id": "abc123def456abcd",
  "canonical_ids": {"arxiv_id": "2301.12345"},
  "cached_path": "artifacts/research/raw_source_cache/academic/abc123def456abcd.json",
  "normalized_title": "Test Paper",
  "dedup_status": "new",
  "error": null
}
```

## Operator Notes

### GitHub Token

Set `GITHUB_TOKEN` in `.env` for authenticated GitHub API requests:

```bash
GITHUB_TOKEN=ghp_...
```

Without a token, the unauthenticated rate limit applies (60 req/hr per IP).
With a token, the limit is 5,000 req/hr. The token is optional — acquisition
works without it but may be rate-limited for batch use.

### arXiv Courtesy Delay

For batch acquisition of multiple arXiv papers, add a 1–2 second delay between
fetches to respect arXiv's API usage policy:

```bash
for arxiv_id in 2301.12345 2302.67890; do
  python -m polytool research-acquire \
    --url "https://arxiv.org/abs/$arxiv_id" \
    --source-family academic --no-eval
  sleep 2
done
```

### Dry-Run for Preview

Use `--dry-run --json` to inspect what would be acquired without writing any
files to disk:

```bash
python -m polytool research-acquire \
  --url https://arxiv.org/abs/2301.12345 \
  --source-family academic \
  --dry-run --json --no-eval
```

Dry-run creates no cache files and no review records.

### Dedup Handling

If the same URL is acquired twice, `dedup_status` will be `"cached"` on the
second run. Ingestion still proceeds (the `IngestPipeline` handles idempotency),
but the review record documents the duplicate status.

## Implementation

### Key modules

| Module | Role |
|---|---|
| `packages/research/ingestion/fetchers.py` | Fetcher classes, `FetchError`, `get_fetcher()`, `FETCHER_REGISTRY` |
| `packages/research/ingestion/acquisition_review.py` | `AcquisitionRecord`, `AcquisitionReviewWriter` |
| `tools/cli/research_acquire.py` | CLI `main(argv) -> int` |

### Integration points

- Calls `IngestPipeline.ingest_external(raw_source, source_family, cache=cache)` from `packages/research/ingestion/pipeline.py`
- Uses `RawSourceCache` from `packages/research/ingestion/source_cache.py` for dedup and caching
- Uses `canonicalize_url`, `extract_canonical_ids`, `normalize_metadata` from `packages/research/ingestion/normalize.py`
- Uses `KnowledgeStore` from `packages/polymarket/rag/knowledge_store.py`
- Uses `DocumentEvaluator` and `get_provider` from `packages/research/evaluation/` when `--no-eval` is not set

## Tests

| File | Count | Scope |
|---|---|---|
| `tests/test_ris_fetchers.py` | 33 offline + 3 live | Fetcher classes, registry, FetchError |
| `tests/test_ris_acquisition_review.py` | 10 offline | AcquisitionRecord, AcquisitionReviewWriter |
| `tests/test_ris_research_acquire_cli.py` | 14 offline | CLI argument handling, dry-run, full flow |

Live tests (`@pytest.mark.live`) require network access and are excluded by
default. Run with:

```bash
pytest tests/test_ris_fetchers.py -m live -v
```
