# Dev Log: RIS_01 Academic Ingestion Pipeline — Practical v1 Closure

**Date:** 2026-04-02
**Task:** quick-260402-wj3
**Codex review tier:** Skip

---

## Objective

Close four concrete gaps in the RIS_01 academic ingestion pipeline to reach practical v1 scope:

1. ArXiv topic search via `LiveAcademicFetcher.search_by_topic()`
2. Curated book ingestion via `BookAdapter` with stable `book_id/chapter` identity
3. `--extract-claims` opt-in flag on both `research-ingest` and `research-acquire` CLIs
4. Truthful SSRN status documentation (deferred, not implied as working)

---

## Files Changed

| File | Change | Why |
|------|--------|-----|
| `packages/research/ingestion/fetchers.py` | Added `search_by_topic()` to `LiveAcademicFetcher` | ArXiv Atom search API, injectable `_http_fn`, returns `list[dict]` |
| `packages/research/ingestion/adapters.py` | Added `BookAdapter` + `_slugify()`, registered in `ADAPTER_REGISTRY["book"]` | Stable canonical URL for book chapters via `internal://book/{id}/{slug}` |
| `packages/research/ingestion/normalize.py` | Added guard in `canonicalize_url()` for non-HTTP schemes | `internal://` book URLs were crashing URL parsing |
| `packages/research/ingestion/pipeline.py` | Added `post_ingest_extract: bool = False` to `ingest_external()` | Expose claim extraction on the external-source path (was only on `ingest()`) |
| `tools/cli/research_acquire.py` | Added `--search`, `--max-results`, `--extract-claims`; added `_run_search_mode()` | ArXiv topic search + claim extraction opt-in via CLI |
| `tools/cli/research_ingest.py` | Added `--extract-claims`; added `"book"` to `--source-family` choices | Claim extraction opt-in + book adapter path accessible from CLI |
| `tests/test_ris_academic_ingest_v1.py` | Created — 26 offline tests | All new code paths covered; no network calls |
| `tests/fixtures/ris_external_sources/book_sample.json` | Created — Market Microstructure Theory fixture | Enables offline smoke test of `BookAdapter` |
| `docs/features/FEATURE-ris-academic-ingest-v1.md` | Created — full v1 feature doc | Documents all shipped functionality + truthful SSRN deferred status |
| `docs/CURRENT_STATE.md` | Brief bullet under recent progress | Session-standard doc update |

---

## Implementation Notes

### ArXiv topic search

The arXiv Atom API is identical to the by-ID path but uses `search_query=all:{encoded}`
instead of `id_list`. The existing `_parse_single_entry()` helper (or inline XML parsing)
iterates all `atom:entry` elements and returns the same dict structure as `fetch()`.

The injectable `_http_fn` pattern is the same as in `fetch()` — the method signature is:

```python
def search_by_topic(self, query: str, max_results: int = 5) -> list[dict]:
```

Empty feeds return `[]` (not `FetchError`). Network failures raise `FetchError`.

### BookAdapter stable identity

The key design decision is that `canonical_url = "internal://book/{book_id}/{slug}"` is
deterministic across re-runs. The slug is derived from `chapter or section or "root"` using
`_slugify()`:

```python
def _slugify(text: str) -> str:
    slug = re.sub(r"[^\w]", "_", text.lower())
    slug = re.sub(r"_+", "_", slug).strip("_")
    return slug or "root"
```

This means `"Chapter 3: The Inventory Model"` always maps to
`"chapter_3_the_inventory_model"`, giving a stable dedup key even across separate ingest runs.

### canonicalize_url guard

`BookAdapter.adapt()` produces `source_url = "internal://book/..."`. When the pipeline
calls `canonicalize_url()` on this URL, the function previously tried to parse and
lowercase the scheme+host using `urlparse`, which could produce unexpected output.

Fix: added guard at the top of `canonicalize_url()`:

```python
url_lower = url.lower()
if not url_lower.startswith("http://") and not url_lower.startswith("https://"):
    return url  # internal:// and other non-HTTP schemes pass through unchanged
```

The `url_lower` form is used for the check (not `url.startswith(...)`) to avoid a
regression where `HTTPS://ArXiv.ORG/...` would pass the check but skip lowercasing.

### post_ingest_extract wiring

`ingest_external()` now accepts `post_ingest_extract: bool = False` explicitly in the
method signature. The non-fatal block mirrors the `ingest()` pattern:

```python
if post_ingest_extract and doc_id:
    try:
        from packages.research.ingestion.claim_extractor import extract_and_link
        extract_and_link(self._store, doc_id)
    except Exception:
        pass
```

Tests verify the call happens (via `claim_extractor` module monkey-patching), does not
happen when `False`, and that an exception does not propagate to the caller.

---

## Commands Run

```bash
# All tests for new paths
python -m pytest tests/test_ris_academic_ingest_v1.py -v --tb=short
# 26 passed in 0.47s

# Book fixture smoke test
python -m polytool research-ingest \
  --from-adapter tests/fixtures/ris_external_sources/book_sample.json \
  --source-family book --no-eval --json
# {"doc_id": "2053fbc7aee79885...", "chunk_count": 1, "rejected": false, "reject_reason": null, "gate": "skipped"}

# --extract-claims in help text
python -m polytool research-ingest --help | grep extract-claims
# [--extract-claims]
python -m polytool research-acquire --help | grep extract-claims
# [--extract-claims]

# --search in help text
python -m polytool research-acquire --help | grep search
# [--url URL | --search QUERY]

# Full regression
python -m pytest tests/ -x -q --tb=short
# 3405 passed, 3 deselected, 25 warnings in 90.39s
```

---

## Test Results

| Suite | New Tests | Pass | Fail |
|-------|-----------|------|------|
| `test_ris_academic_ingest_v1.py` | 26 | 26 | 0 |
| Full regression | — | 3405 | 0 |

Baseline before this task: 3349 passing. The increase to 3405 includes tests from this
task and concurrent tasks (quick-260402-wj9: RedditAdapter/YouTubeAdapter).

---

## RIS_01 Completion Status

| Capability | Status |
|-----------|--------|
| Manual file ingest (`--file`) | Shipped (Phase 1) |
| Manual text ingest (`--text`) | Shipped (Phase 1) |
| ArXiv by-ID fetch | Shipped (Phase 5) |
| ArXiv topic search (`--search`) | Shipped (this task) |
| BookAdapter + stable book_id identity | Shipped (this task) |
| `--extract-claims` on both CLIs | Shipped (this task) |
| GitHub live fetcher | Shipped (Phase 5) |
| Reddit live fetcher | Shipped (quick-260402-wj9) |
| YouTube live fetcher | Shipped (quick-260402-wj9) |
| SSRN source_type detection (URL-pattern) | Shipped (Phase 4) |
| **SSRN live scraper** | **DEFERRED** |
| **Semantic chunking by section** | **DEFERRED** |
| **Chroma namespace-per-family** | **DEFERRED** |

---

## What Remains Explicitly Deferred

### SSRN live scraper

SSRN blocks automated crawlers and requires session-authenticated access. Implementing
a compliant scraper is non-trivial and low-ROI relative to other RIS priorities.

Operator workaround: pre-build a raw_source dict manually and use `--from-adapter`:

```json
{"url": "https://ssrn.com/abstract=1234567", "title": "...", "abstract": "...", "authors": ["..."], "published_date": "..."}
```

### Semantic chunking by section

Current pipeline uses fixed-size chunking. Section-aware chunking for academic papers and
books would improve retrieval quality but is a separate body of work.

### Chroma namespace per family

KnowledgeStore uses a single ChromaDB collection. Family-aware namespacing is a future
improvement tied to retrieval tuning work.

---

## Open Questions

None from this task. All four v1 scope items are closed.
