# 2026-04-27 — RIS Academic PDF Fix

## Objective

Fix `research-acquire --source-family academic` so arXiv papers are ingested with
full PDF body text instead of abstract-only.

---

## Reproduction (before fix)

```
python -m polytool research-acquire --url "https://arxiv.org/abs/2510.15205" --source-family academic --no-eval --json
```

Output: `chunk_count: 1`, cached payload had only `abstract` (1567 chars), no `body_text`.

Root cause: `LiveAcademicFetcher.fetch()` called the arXiv Atom API and returned
`{url, title, abstract, authors, published_date}` only. `AcademicAdapter.adapt()` used
`body_text if body_text else abstract`, so academic docs were always abstract-only.
`PDFExtractor` already existed in `extractors.py` but was never called for arXiv fetches.

---

## Files Changed

### `packages/research/ingestion/fetchers.py`
- Added `import logging` and module-level `_logger`.
- Added `_pdf_http_fn` and `_pdf_extractor_cls` injectable parameters to
  `LiveAcademicFetcher.__init__` (test injection without patching imports).
- Added `_fetch_pdf_body(arxiv_id)` method: downloads
  `https://arxiv.org/pdf/{id}.pdf`, writes to temp file, calls `PDFExtractor`,
  deletes temp file in `finally`. Returns `(body_text, meta_dict)`.
  - Success: `body_source=pdf`, `body_length`, `page_count`.
  - Short text (< 2000 chars) or any exception: `body_source=abstract_fallback`,
    `fallback_reason`. Never raises.
- Updated `fetch()` return dict: calls `_fetch_pdf_body`, merges result, sets
  `body_text` to full PDF text or abstract fallback, logs INFO line.
- Updated `search_by_topic()`: captures `arxiv_id` per entry, calls
  `_fetch_pdf_body` for each, merges result into entry dict.

### `packages/research/ingestion/adapters.py`
- `AcademicAdapter.adapt()`: adds `body_source` (default `"abstract"`) to
  persisted metadata; conditionally adds `body_length`, `page_count`,
  `fallback_reason` when present in `raw_source`.

### `pyproject.toml`
- Added `pdfplumber>=0.10.0` to `[project.optional-dependencies] ris`.

### `tests/test_ris_academic_ingest_v1.py`
- `test_two_entries_returns_two_dicts`: relaxed `len(calls) == 1` to `>= 1`
  (PDF download adds 1 call per result entry).
- `test_result_dict_keys`: changed `set(keys) == {…}` to `issubset` — PDF fetch
  adds `body_text`, `body_source`, etc. to the result dict.

---

## Dependency Changes

- `pdfplumber>=0.10.0` added to `ris` optional group in `pyproject.toml`.
- `pdfplumber 0.11.9` installed in active environment.

---

## Live Validation

```
# Fresh run (cache cleared)
python -m polytool research-acquire --url "https://arxiv.org/abs/2510.15205" --source-family academic --no-eval --json
```

Result:
```json
{
  "dedup_status": "new",
  "chunk_count": 27,
  "rejected": false
}
```

Cached payload: `body_source=pdf`, `body_length=58927`, `page_count=25`.

Repeat run: `dedup_status=cached`, same `chunk_count=27` — no re-download.

---

## Test Results

```
python -m pytest tests/test_ris_academic_pdf.py tests/test_ris_academic_ingest_v1.py tests/test_ris_research_acquire_cli.py -v
```

**54 passed, 0 failed.**

New tests in `tests/test_ris_academic_pdf.py` (14 tests):
- PDF success: body_text = extracted PDF, not abstract; URL format; abstract preserved.
- HTTP failure: falls back to abstract, body_source=abstract_fallback, no raise.
- Short text: < 2000 chars → fallback with "too short" reason.
- Extraction exception: any error → fallback.
- search_by_topic: body_source/body_text in every result; success and failure paths.
- AcademicAdapter: body_source, body_length, page_count, fallback_reason in metadata.

---

## Codex Review

Scope: fetchers.py (strategy-adjacent, Recommended tier). No mandatory files touched.
Issues found: none. No adversarial review required.

---

## Remaining Limitations

- No arXiv version-aware cache invalidation (always downloads latest PDF).
- No SSRN / OpenReview / bioRxiv / other preprint host support.
- No math-aware or structural PDF extraction (equations become garbled text).
- PDF download is synchronous; search_by_topic blocks on N sequential PDF downloads.
- `pdfplumber` is a new dependency in the `ris` group — existing installs need
  `pip install polytool[ris]` to refresh.
