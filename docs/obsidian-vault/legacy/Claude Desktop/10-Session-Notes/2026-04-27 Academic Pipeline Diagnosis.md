---
tags: [session-note]
date: 2026-04-27
topics: [ris, academic-pipeline, ingestion, diagnosis]
related-work-packet: "[[Work-Packet - Academic Pipeline PDF Download Fix]]"
---

# 2026-04-27 — Academic Pipeline Diagnosis

## Context

User reported that the academic ingest pipeline, after running an arXiv URL through `research-acquire`, only stored "the information on the page of the site, NOT the actual research paper itself." Diagnosis session goal: identify where in the fetch → extract → adapt chain the paper body gets dropped.

## Method

A single read-only Codex prompt produced a 9-section evidence dump:

1. CLI entry point — `tools/cli/research_acquire.py:main()`, which calls `get_fetcher(family).fetch(url)` then runs the result through `IngestPipeline.ingest_external()`.
2. Pipeline orchestration — `packages/research/ingestion/pipeline.py`, full file.
3. Fetcher academic path — `LiveAcademicFetcher` class in `fetchers.py:93`.
4. Extractors — `PDFExtractor` class in `extractors.py:327` plus the `ExtractedDocument` dataclass.
5. URL classification — regex `_ARXIV_URL_ID_RE` already handles both `/abs/` and `/pdf/` forms.
6. Live reproduction — skipped per read-only constraint.
7. Dependency check — `pdfplumber`, `pypdf`, `pypdf2`, `arxiv`, `feedparser` all missing.
8. Recent dev logs — most recent is `2026-04-24_ris_phase2a_live_activation_troubleshoot.md`.
9. Existing test surface — 14 RIS test files including `test_ris_academic_ingest_v1.py`.

Full code dump preserved in chat history of this Claude Project session.

## Findings

### Bug location: `LiveAcademicFetcher.fetch()`

Calls the arXiv Atom API at `http://export.arxiv.org/api/query?id_list=<id>` and returns:

```python
return {
    "url": canonical_url,
    "title": title,
    "abstract": abstract,
    "authors": authors,
    "published_date": published_date,
}
```

**No `body_text` field is ever populated.** The Atom API returns metadata only.

### Bug propagation: `AcademicAdapter.adapt()`

```python
body = body_text if body_text else abstract
if not body:
    body = title
```

With `body_text` always absent, every academic ingest stores the abstract as the document body.

### Scaffolded but unused: `PDFExtractor`

A real `PDFExtractor` class exists in `extractors.py` using pdfplumber. It accepts a file path and returns an `ExtractedDocument` with full body, title, page count, content hash. **Nothing in the codebase calls it for arXiv URLs.**

### Missing dependency: `pdfplumber`

`python -c "import pdfplumber"` → `ModuleNotFoundError`.

The PDF capability was scaffolded, never wired, and the dependency was never installed.

## Implication

Every academic document in ChromaDB and the SQLite knowledge store is currently a 1-2 chunk record holding only the abstract. The Phase R0 seed and any subsequent academic ingest has been silently shallow. The evaluation gate has been scoring abstracts (200 words) instead of papers (10,000+ words). RAG queries return abstracts when they should return paper bodies.

This is upstream of every other RIS academic concern (relevance filtering, embedding strategy, multi-source). Fix this first.

## Decision

Land the fix as a single work packet — see [[Work-Packet - Academic Pipeline PDF Download Fix]]. Scope is narrow: wire pdfplumber into `LiveAcademicFetcher` after the Atom call, populate `body_text`, propagate body-source metadata into the adapter and knowledge store, add regression tests. Out of scope: multi-source, embedding strategy, relevance filtering — those wait on the GLM-5 scientific RAG survey currently running.

## Open follow-ups

- After this packet lands, re-ingest all existing academic URLs in the cache to upgrade abstract-only records to full-body records.
- Re-run the Phase R0 seed (Jon-Becker findings, Avellaneda-Stoikov, Kelly) through the fixed pipeline.
- Add the GLM-5 survey output to `08-Research/` once it returns; design the embedding/multi-source/relevance-filter packets against its findings.

## Cross-references

- [[Work-Packet - Academic Pipeline PDF Download Fix]] — the actionable packet
- [[RIS]] — module status (currently flagged "done"; should be "partial" until this lands)
- [[Phase-2-Discovery-Engine]] — parent phase
- [[RIS_OPERATIONAL_READINESS_ROADMAP_v1.1]] — Phase 2A authoritative roadmap
