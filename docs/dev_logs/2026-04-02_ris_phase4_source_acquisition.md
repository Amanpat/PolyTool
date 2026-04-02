# Dev Log: RIS Phase 4 External Source Acquisition

**Date:** 2026-04-02
**Branch:** feat/ws-clob-feed
**Quick task:** 260402-ogu

---

## Objective

Ship RIS Phase 4: raw-source caching, adapter boundaries for three source families
(academic/preprint, GitHub/repo, blog/news/article), metadata normalization with
canonical IDs, and a CLI/callable path wiring fixture-backed external sources through
the full adapter -> cache -> normalize -> eval -> store pipeline.

---

## Files Changed

| File | Change Type | Why |
|------|-------------|-----|
| `packages/research/ingestion/source_cache.py` | New | Disk-backed raw payload cache |
| `packages/research/ingestion/normalize.py` | New | Metadata normalization + canonical ID extraction |
| `packages/research/ingestion/adapters.py` | New | SourceAdapter ABC + 3 family adapters |
| `packages/research/ingestion/pipeline.py` | Modified | Added `ingest_external()` method |
| `packages/research/ingestion/__init__.py` | Modified | Exported new Phase 4 symbols |
| `tools/cli/research_ingest.py` | Modified | Added `--from-adapter` CLI path |
| `tests/fixtures/ris_external_sources/arxiv_sample.json` | New | arXiv fixture |
| `tests/fixtures/ris_external_sources/github_sample.json` | New | GitHub fixture |
| `tests/fixtures/ris_external_sources/blog_sample.json` | New | Blog fixture |
| `tests/test_ris_phase4_source_acquisition.py` | New | 49 deterministic tests |
| `docs/features/FEATURE-ris-phase4-source-acquisition.md` | New | Feature doc |

---

## Commands Run and Exact Output

### Task 1 — RED test run (confirmed failures before implementation)

```
$ python -m pytest tests/test_ris_phase4_source_acquisition.py -x -q --tb=short
1 failed, 0 passed
ModuleNotFoundError: No module named 'packages.research.ingestion.source_cache'
```

### Task 1 — GREEN test run (after implementation)

```
$ python -m pytest tests/test_ris_phase4_source_acquisition.py -q --tb=short
42 passed, 7 pending (EndToEnd awaiting pipeline wiring)
```

### Task 2 — Full Phase 4 tests (after pipeline wiring)

```
$ python -m pytest tests/test_ris_phase4_source_acquisition.py tests/test_ris_ingestion_integration.py -q --tb=short
61 passed in 1.12s
```

### CLI smoke test

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

### Full regression suite

```
$ python -m pytest tests/ -x -q --tb=short
2009 passed, 1 failed (pre-existing), 19 warnings in 58.08s
```

Pre-existing failure: `tests/test_ris_claim_extraction.py::TestClaimTypeClassification::test_normative_recommend`
- This failure existed before this work packet (confirmed by git stash check)
- It is from another agent's claim_extractor work and is out of scope

---

## Source Families and Adapters Implemented

### AcademicAdapter
- Input keys: `url`, `title`, `abstract`, `authors` (list), `published_date`, `body_text` (optional)
- Body: prefers `body_text` over `abstract`
- source_type inference: "arxiv" (arxiv.org URL), "ssrn" (ssrn.com URL), "book" (default)
- canonical_ids populated: doi, arxiv_id, ssrn_id as found in text

### GithubAdapter
- Input keys: `repo_url`, `readme_text`, `description`, `stars`, `forks`, `license`, `last_commit_date`
- Title: derived from owner/repo URL path
- Body: readme_text + description
- metadata: stars, forks, license, commit_recency
- canonical_ids: repo_url (canonical normalized)

### BlogNewsAdapter
- Input keys: `url`, `title`, `body_text`, `author`, `published_date`, `publisher`
- News vs blog heuristic: if host matches known news domain set (reuters, bloomberg, ft, wsj, etc.) -> "news", else "blog"
- Source_family follows source_type ("blog" or "news")

---

## Raw-Source Caching Decisions

**Envelope format:**
```json
{
  "source_id": "<sha256[:16] of canonical_url>",
  "source_family": "academic",
  "cached_at": "2026-04-02T21:45:00.000000+00:00",
  "payload": { ...original dict... }
}
```

**Disk layout:** `{cache_dir}/{source_family}/{source_id}.json`
- Isolates families in separate subdirectories (same source_id can exist in multiple families)
- `cache_dir` defaults to `artifacts/research/raw_source_cache/` via CLI

**Deterministic IDs:** `sha256(canonical_url.encode())[:16]` — same URL always maps to same cache file, enabling idempotent scraper runs.

---

## Remaining Gaps Before Full Scraper Automation

1. **Live HTTP client**: adapters accept pre-fetched dicts only. A future scraper module will fetch from URLs and pass raw dicts to adapters.
2. **Scraper orchestration**: no scheduler, n8n, or polling loop. Adapters are ready to receive live data.
3. **forum_social family**: reddit, twitter, youtube not yet adapter-backed.
4. **Dedup wiring**: canonical_ids extracted and stored in metadata; not yet used by the near-duplicate check (which uses content hash + shingles).
5. **Rate limiting**: N/A until live scraping is added.

---

## Codex Review

- Tier: Skip (no execution, live trading, or risk-manager code touched)
- Issues: None

---

## Test Results Summary

- Targeted (Phase 4): **49 passed, 0 failed**
- Integration (existing ingestion): **12 passed, 0 failed**
- Full regression: **2009 passed, 1 pre-existing failed, 19 warnings**
