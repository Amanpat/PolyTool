# FEATURE: RIS_01 Academic Ingestion Pipeline — Practical v1 Closure

## Status: Shipped (2026-04-02)

## What Shipped

This task closes the practical v1 scope of RIS_01 by adding four capabilities that were
previously missing from the academic ingestion path:

1. ArXiv topic search (batch ingest by keyword)
2. Curated book ingestion with stable metadata identity
3. Opt-in claim extraction flag on both CLIs (`--extract-claims`)
4. Truthful SSRN status documentation (deferred, not implied as working)

---

### ArXiv Topic Search

**`packages/research/ingestion/fetchers.py`** — `LiveAcademicFetcher.search_by_topic()`

```python
LiveAcademicFetcher(timeout=15, _http_fn=None).search_by_topic(
    query: str,
    max_results: int = 5
) -> list[dict]
```

- Calls the arXiv Atom API:
  `http://export.arxiv.org/api/query?search_query=all:{encoded_query}&max_results={n}`
- Parses all `atom:entry` elements in the response using the same field extraction as `fetch()`
- Returns a list of dicts; each dict has keys: `url`, `title`, `abstract`, `authors` (list), `published_date`
- Returns `[]` when the API returns zero entries (no FetchError)
- Raises `FetchError` on network failure
- `_http_fn` is injectable for offline testing (same pattern as `fetch()`)

**CLI usage (`research-acquire --search`):**

```bash
# Search ArXiv for up to 5 papers on prediction markets
python -m polytool research-acquire \
  --search "prediction markets microstructure" \
  --source-family academic \
  --no-eval \
  --json

# Output: JSON object with query, result_count, results list (per-paper doc_id, chunks, etc.)

# Search and run claim extraction on each ingested paper
python -m polytool research-acquire \
  --search "market maker inventory" \
  --source-family academic \
  --max-results 10 \
  --extract-claims \
  --no-eval
```

---

### BookAdapter — Curated Book Ingestion

**`packages/research/ingestion/adapters.py`** — `BookAdapter`

Books do not have a live fetcher. Raw source dicts are provided manually (via `--from-adapter`)
or loaded from structured fixtures.

**Expected raw_source keys:**

| Key | Type | Required | Description |
|-----|------|----------|-------------|
| `title` | str | yes | Book title |
| `authors` | str or list[str] | yes | Author(s) |
| `book_id` | str | yes | Stable book identifier (e.g. `"market_microstructure_theory"`) |
| `chapter` | str | no | Chapter name/label |
| `section` | str | no | Section name (used if chapter absent) |
| `body_text` | str | yes | Chapter/section body text |
| `published_date` | str | no | ISO-8601 publication date |

**Stable canonical identity:**

```
canonical_url = "internal://book/{book_id}/{chapter_or_section_slug}"
```

where `chapter_or_section_slug = slugify(chapter or section or "root")`.

The `slugify()` function: lowercases text, replaces non-alphanumeric characters with `_`,
strips leading/trailing underscores, collapses consecutive underscores.

Example: `"Chapter 3: The Inventory Model"` → `"chapter_3_the_inventory_model"`

**Registered in ADAPTER_REGISTRY as `"book"`.**

**CLI usage:**

```bash
# Ingest a book chapter from a pre-built fixture
python -m polytool research-ingest \
  --from-adapter tests/fixtures/ris_external_sources/book_sample.json \
  --source-family book \
  --no-eval \
  --json

# Output:
# {
#   "doc_id": "2053fbc7aee79885...",
#   "chunk_count": 1,
#   "rejected": false,
#   "reject_reason": null,
#   "gate": "skipped"
# }
```

**Fixture (`tests/fixtures/ris_external_sources/book_sample.json`):**

```json
{
  "title": "Market Microstructure Theory",
  "authors": ["Maureen O'Hara"],
  "book_id": "market_microstructure_theory",
  "chapter": "Chapter 3: The Inventory Model",
  "body_text": "The inventory model is central to understanding...",
  "published_date": "1995-01-01"
}
```

---

### --extract-claims Flag

Both CLIs now expose `--extract-claims` (opt-in, non-fatal). When set, claim extraction
runs on the ingested document immediately after ingest.

**`tools/cli/research-ingest`:**

```bash
python -m polytool research-ingest \
  --from-adapter tests/fixtures/ris_external_sources/arxiv_sample.json \
  --source-family academic \
  --no-eval \
  --extract-claims
```

**`tools/cli/research-acquire`:**

```bash
python -m polytool research-acquire \
  --url https://arxiv.org/abs/2301.12345 \
  --source-family academic \
  --no-eval \
  --extract-claims
```

Implementation: both CLIs pass `post_ingest_extract=args.extract_claims` to
`IngestPipeline.ingest_external()` (or `ingest()` for the file/text path).
`ingest_external()` now accepts `post_ingest_extract: bool = False` as an explicit kwarg.

Failure in claim extraction is non-fatal: the ingest result is still returned and
the document remains in the knowledge store.

---

### SSRN Status: Truthfully Deferred

**SSRN source_type detection is supported.** When a URL containing `ssrn.com` is submitted
via `--from-adapter` or `--url`, the `normalize.py` logic sets `source_type = "ssrn"` via
the `_infer_source_type()` function. This is correctly routed through `AcademicAdapter`.

**There is no live SSRN fetcher.** `LiveAcademicFetcher.fetch()` raises `FetchError` on
non-arXiv URLs (including ssrn.com).

**Live SSRN scraping is DEFERRED.** SSRN blocks automated crawlers and requires
session-authenticated access. The scraping strategy is not straightforward and has not
been implemented.

**Operator workaround:** SSRN papers can be ingested manually by downloading the paper
and supplying a pre-built raw_source dict via `--from-adapter`:

```json
{
  "url": "https://ssrn.com/abstract=1234567",
  "title": "Paper Title",
  "abstract": "...",
  "authors": ["Author Name"],
  "published_date": "2024-01-15"
}
```

```bash
python -m polytool research-ingest \
  --from-adapter my_ssrn_paper.json \
  --source-family academic \
  --no-eval
```

---

### Manual Local File Ingest (Phase 1, unchanged)

```bash
python -m polytool research-ingest --file path/to/doc.md --no-eval
python -m polytool research-ingest --text "Document body..." --title "My Doc" --no-eval
```

---

## Source Families Supported

| Family   | Live Fetcher | Adapter | source_type |
|----------|-------------|---------|-------------|
| academic | `LiveAcademicFetcher` (arXiv by ID + search) | `AcademicAdapter` | arxiv / ssrn (URL-detected) / book |
| github   | `LiveGithubFetcher` | `GithubAdapter` | github |
| blog     | `LiveBlogFetcher` | `BlogNewsAdapter` | blog |
| news     | `LiveNewsFetcher` | `BlogNewsAdapter` | news |
| book     | (none — local fixtures only) | `BookAdapter` | book |
| reddit   | `LiveRedditFetcher` | `RedditAdapter` | reddit |
| youtube  | `LiveYouTubeFetcher` | `YouTubeAdapter` | youtube |

---

## What Remains Deferred

- **SSRN live scraper**: session-authenticated scraping, not yet implemented.
- **Semantic chunking by section**: current pipeline uses fixed-size chunking.
  Section-aware chunking for academic papers and books is a future improvement.
- **Chroma wiring**: knowledge store uses SQLite/ChromaDB internally; direct Chroma
  namespace-per-family configuration is not yet exposed.
- **Automated SSRN dedup via SSRN ID**: canonical_ids extraction detects `ssrn_id`
  from body text but dedup check uses content hash + shingles, not SSRN ID lookup.

---

## Tests

- `tests/test_ris_academic_ingest_v1.py`: 26 tests
  - `TestSearchByTopic`: 7 tests (two-entry feed, result keys, empty feed, network error,
    URL encoding, max_results, multiple authors)
  - `TestBookAdapter`: 12 tests (adapt keys, source_type, canonical_url, fallback slugs,
    authors list/str, book_id in canonical_ids, body_text, publish_date, registry)
  - `TestIngestExternalWithExtractClaims`: 4 tests (True calls extractor, False does not,
    exception non-fatal, signature check)
  - `TestBookSampleFixture`: 3 tests (fixture exists, required keys, ingestible)
- All 26 pass with zero regressions (3405 total passing).
