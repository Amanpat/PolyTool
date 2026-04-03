# 2026-04-02 — RIS Phase 5: Live Source Acquisition Adapters

## Summary

Implemented the full RIS Phase 5 live source acquisition layer: three HTTP
fetcher classes (academic/arXiv, GitHub, blog/news), a JSONL acquisition audit
writer, a CLI entrypoint (`research-acquire`), and the `pytest.mark.live`
marker for offline-safe test isolation.

The design is stdlib-only (no new runtime dependencies), uses an injectable
`_http_fn` parameter for hermetic offline testing, and integrates cleanly with
the existing `IngestPipeline.ingest_external()` and `RawSourceCache` contracts
established in RIS Phase 4.

## Files Changed

### Created

| File | Description |
|---|---|
| `packages/research/ingestion/fetchers.py` | `LiveAcademicFetcher`, `LiveGitHubFetcher`, `LiveBlogFetcher`, `FETCHER_REGISTRY`, `get_fetcher()`, `FetchError`, `_default_urlopen` |
| `packages/research/ingestion/acquisition_review.py` | `AcquisitionRecord` dataclass, `AcquisitionReviewWriter` (append-only JSONL audit log) |
| `tools/cli/research_acquire.py` | `main(argv) -> int` — 7-step acquisition pipeline CLI |
| `tests/test_ris_fetchers.py` | 33 offline + 3 `@pytest.mark.live` smoke tests |
| `tests/test_ris_acquisition_review.py` | 10 offline tests for review writer |
| `tests/test_ris_research_acquire_cli.py` | 14 offline CLI tests via monkeypatching |

### Modified

| File | Change |
|---|---|
| `polytool/__main__.py` | Added `research_acquire_main` entrypoint + `"research-acquire"` to command handler map and usage output |
| `tests/conftest.py` | Registered `pytest.mark.live` custom marker |

## Test Results (full regression, -m "not live")

```
1 failed (pre-existing), 3328 passed, 3 deselected
```

The single failing test (`tests/test_ris_evaluation.py::TestEvaluateDocumentConvenience::test_get_provider_factory_unknown_raises`)
is pre-existing — caused by commit `fefbabe` on the parallel RIS Phase 5
controlled-provider track (`quick-260402-rmz-02`), which changed `providers.py`
to raise `PermissionError` instead of `ValueError` for unknown cloud providers.
This plan's changes do not cause or touch that failure.

The 3 deselected tests are the `@pytest.mark.live` smoke tests in
`tests/test_ris_fetchers.py` — correctly excluded by `-m "not live"`.

## Architecture Notes

### stdlib-only HTTP

`LiveAcademicFetcher`, `LiveGitHubFetcher`, and `LiveBlogFetcher` all use
`urllib.request` exclusively. No `requests`, `httpx`, or `aiohttp` are added.
This preserves the project's minimal-dependency stance for the acquisition layer.

### Injectable `_http_fn` pattern

Every fetcher constructor accepts an optional `_http_fn` parameter:

```python
class LiveAcademicFetcher:
    def __init__(self, timeout: int = 15, _http_fn=None) -> None:
        self._http_fn = _http_fn or _default_urlopen
```

Tests monkeypatch the module-level `_default_urlopen` symbol to serve canned
bytes without any network. This avoids subprocess overhead and keeps all 57
new offline tests sub-millisecond.

### Adapter contract alignment

Each fetcher returns a `dict` that matches the field expectations of the
corresponding adapter in `packages/research/ingestion/adapters.py`:

- `LiveAcademicFetcher` → `AcademicAdapter` (url, title, abstract, authors, published_date)
- `LiveGitHubFetcher` → `GithubAdapter` (repo_url, readme_text, description, stars, forks, license, last_commit_date)
- `LiveBlogFetcher` → `BlogNewsAdapter` (url, title, body_text, author, published_date, publisher)

### arXiv fetching

Uses the arXiv Atom API (`https://export.arxiv.org/api/query?id_list={id}`).
Extracts the arXiv ID from the URL via local regex (identical to the pattern
in `normalize.py`) to avoid circular import risk.

### GitHub fetching

Fetches `/repos/{owner}/{repo}` for metadata, then `/repos/{owner}/{repo}/readme`
for README content (base64-decoded). A 404 on the README endpoint falls back
gracefully to an empty string rather than raising `FetchError`. GitHub token
is optional; without it the 60 req/hr unauthenticated rate limit applies.

### Blog/news fetching

Strips all HTML tags via regex, collapses whitespace, and truncates body to
50,000 characters. Extracts title from `<title>`, author from meta tags
(`name="author"` or `property="article:author"`), published date from
`property="article:published_time"`, and publisher from
`property="og:site_name"`.

### Dedup detection

`RawSourceCache.has_raw(source_id, source_family)` is checked before the
full pipeline run. The dedup status (`"new"` or `"cached"`) is recorded in
both CLI JSON output and the acquisition review record. Ingestion proceeds
regardless of dedup status — the cache write is idempotent.

### Acquisition review (JSONL audit log)

`AcquisitionReviewWriter` appends one JSON line per acquisition attempt to
`{review_dir}/acquisition_review.jsonl`. The record captures: timestamp, URL,
family, source_id, canonical_ids, cached path, normalized title, dedup status,
and any error string. Written even on ingest failure so the audit trail is
complete.

## CLI Verification

```
$ python -m polytool research-acquire --help

usage: research-acquire [-h] [--url URL] [--source-family FAMILY]
                        [--cache-dir PATH] [--review-dir PATH] [--db PATH]
                        [--no-eval] [--dry-run] [--json] [--provider NAME]

Fetch a source from a URL and ingest it into the RIS knowledge store.

options:
  -h, --help            show this help message and exit
  --url URL             Source URL to fetch (required).
  --source-family FAMILY
                        Source family: academic, github, blog, or news (required).
  --cache-dir PATH      Directory for raw-source cache (default: artifacts/research/raw_source_cache).
  --review-dir PATH     Directory for acquisition review JSONL (default: artifacts/research/acquisition_reviews).
  --db PATH             Custom knowledge store path (default: system default).
  --no-eval             Skip evaluation gate (hard-stop checks still run).
  --dry-run             Fetch and normalize only; do not cache, ingest, or write review.
  --json                Output JSON to stdout.
  --provider NAME       Evaluation provider (default: manual).
```

`research-acquire` also appears in `python -m polytool --help` under the
`Research Intelligence (RIS v1/v2)` section.

## Commits

| Hash | Description |
|---|---|
| `d906703` | feat(quick-260402-rm1-01): RIS Phase 5 live fetchers and acquisition review writer |
| `128c4f9` | feat(quick-260402-rm1-02): research-acquire CLI and __main__.py registration |
| `c53ff5b` | feat(quick-260402-rm1-03): register pytest.mark.live marker in conftest.py |

## Next Steps

1. **Live smoke validation**: Run `pytest tests/test_ris_fetchers.py -m live -v`
   with network access to confirm the three `@pytest.mark.live` smoke tests
   pass against real endpoints.
2. **GitHub token**: Set `GITHUB_TOKEN` in `.env` for authenticated rate limits
   (5,000 req/hr vs 60 unauthenticated).
3. **arXiv courtesy delay**: For batch acquisition loops, add a 1–2 second
   delay between arXiv fetches to respect their API policy.
4. **Operator pipeline integration**: Wire `research-acquire` calls into the
   autoresearch loop (Phase 5 batch acquisition CLI — future plan).
5. **Pre-existing test fix**: The `test_get_provider_factory_unknown_raises`
   failure in `test_ris_evaluation.py` needs reconciliation between the
   `quick-260402-rmz` track (which changed the exception type) and the test.

## Codex Review

Tier: Skip (no execution layer, live trading, or strategy code changed).
