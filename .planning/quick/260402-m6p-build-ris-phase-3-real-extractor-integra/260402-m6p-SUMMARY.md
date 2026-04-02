---
phase: quick
plan: 260402-m6p
subsystem: research-ingestion
tags: [ris, extractors, benchmark, seed, markdown, pdf, docx]
dependency_graph:
  requires: [quick-260401-nzz, 260401-o1q]
  provides: [structured-markdown-extractor, real-pdf-docx-extractors, benchmark-quality-proxies, reseed-workflow]
  affects: [ris-knowledge-store, rag-query-spine, seed-manifest]
tech_stack:
  added: []
  patterns:
    - optional-dep pattern for pdfplumber and python-docx (module-level try/import, instance attr check at call-time)
    - structural Markdown parsing via regex (heading, table block, fenced code block)
    - reseed DELETE-before-ingest via store._conn direct access (same pattern as source_family UPDATE)
key_files:
  created:
    - packages/research/ingestion/extractors.py (StructuredMarkdownExtractor, PDFExtractor, DocxExtractor)
    - tests/test_ris_real_extractors.py
    - tests/fixtures/ris_seed_corpus/sample_structured.md
    - docs/features/FEATURE-ris-v3-real-extractors.md
    - docs/dev_logs/2026-04-02_ris_phase3_real_extractor_and_backfill.md
  modified:
    - packages/research/ingestion/benchmark.py (quality proxy fields)
    - packages/research/ingestion/seed.py (extractor field, reseed param)
    - packages/research/ingestion/__init__.py (new exports)
    - config/seed_manifest.json (v3, extractor fields)
    - tools/cli/research_seed.py (--reseed flag)
    - tests/test_ris_extractor_benchmark.py (PDFExtractor/DocxExtractor assertions)
    - tests/test_ris_calibration.py (version assertion v2 or v3)
    - docs/CURRENT_STATE.md
decisions:
  - StructuredMarkdownExtractor preserves body text unchanged; structural data lives in metadata only — avoids altering RAG retrieval inputs while adding provenance
  - pdfplumber and python-docx are optional deps checked at extract() call-time (not import time) — no install friction for current Markdown-only corpus
  - StubPDFExtractor and StubDocxExtractor retained for backward compat but removed from EXTRACTOR_REGISTRY
  - Reseed uses DELETE-before-ingest via store._conn direct access (same pattern as source_family UPDATE workaround)
  - Seed auto-detect maps .md -> structured_markdown (not plain_text) as Phase 3 default
metrics:
  duration_minutes: 45
  completed_date: "2026-04-02"
  tasks_completed: 3
  tasks_total: 3
  files_created: 5
  files_modified: 8
  tests_added: 42
  tests_total: 3110
---

# Phase quick Plan 260402-m6p: RIS Phase 3 Real Extractor Integration Summary

StructuredMarkdownExtractor, real PDF/DOCX extractors with optional-dep fallback, benchmark quality proxies, and reseed workflow for corpus backfill.

## What Was Built

### Task 1: Real extractors, enhanced benchmark, extractor fallback (commit: ad96713)

**StructuredMarkdownExtractor** added to `packages/research/ingestion/extractors.py`:
- Regex-based heading detection (`^#{1,6}\s+(.+)`) builds `sections` list and `section_count`
- Table detection requires both pipe rows and separator row — avoids false positives
- Fenced code block counting via fence pair detection (``` or ~~~)
- Body text returned unchanged; structural metadata stored in `ExtractedDocument.metadata`
- Fallback: parse failure degrades to PlainTextExtractor behavior (no crash)

**PDFExtractor** and **DocxExtractor** replace stubs:
- Module-level optional dep detection; `ImportError` raised at `extract()` call-time when absent
- `EXTRACTOR_REGISTRY` updated: `"pdf": PDFExtractor`, `"docx": DocxExtractor`, `"structured_markdown": StructuredMarkdownExtractor`
- Stubs retained but not registered

**ExtractorMetric** extended with `section_count`, `header_count`, `table_count`, `code_block_count`, `extractor_used`. BenchmarkResult.summary per-extractor dict adds `avg_section_count`, `avg_header_count`, `total_table_count`.

42 tests added in `tests/test_ris_real_extractors.py`.

### Task 2: Seed manifest expansion, reseed workflow, corpus backfill (commit: eb208c3)

- `SeedEntry` gains `extractor: Optional[str] = None` field
- `_detect_extractor(path)` maps `.md` -> `"structured_markdown"`, `.pdf` -> `"pdf"`, `.docx/.doc` -> `"docx"`, else `"plain_text"`
- `run_seed(reseed=True)` deletes existing docs by `source_url` before re-ingest
- `config/seed_manifest.json` bumped to v3; all 11 entries have `"extractor": "structured_markdown"`
- `--reseed` flag added to `research-seed` CLI
- Human-readable output now includes Extractor column

### Task 3: Feature doc, dev log, CURRENT_STATE update, full regression (commit: 2a118dc)

- `docs/features/FEATURE-ris-v3-real-extractors.md` created
- `docs/dev_logs/2026-04-02_ris_phase3_real_extractor_and_backfill.md` created with benchmark comparison
- `docs/CURRENT_STATE.md` updated with RIS Phase 3 section and benchmark delta table
- Full regression: **3110 passed, 0 failed**

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] `test_real_seed_manifest_v2_parses` checking for exact version "2"**
- **Found during:** Task 3 full regression
- **Issue:** `tests/test_ris_calibration.py` asserted `manifest.version == "2"` but manifest was bumped to "3" in Task 2. Test name and intent ("parses with all 11 entries") was correct; only the version string assertion was stale.
- **Fix:** Updated assertion to `assert manifest.version in ("2", "3")` and updated docstring to say "v3". The rest of the test (11 entries, source_type checks, evidence_tier checks) is unchanged.
- **Files modified:** `tests/test_ris_calibration.py`
- **Commit:** 2a118dc

**2. [Rule 1 - Bug] test_ris_extractor_benchmark.py `test_get_extractor_pdf_stub` and `test_get_extractor_docx_stub`**
- **Found during:** Task 1 GREEN phase
- **Issue:** Existing tests checked that `get_extractor('pdf')` returns `StubPDFExtractor` / `get_extractor('docx')` returns `StubDocxExtractor`, but Task 1 replaced the registry entries with real extractors.
- **Fix:** Updated method names and assertions to check for `PDFExtractor` / `DocxExtractor` instead.
- **Files modified:** `tests/test_ris_extractor_benchmark.py`
- **Commit:** ad96713

## Benchmark Comparison on Real Corpus

`docs/reference/RAGfiles/` (8 files):

| Extractor             | avg_section_count | avg_header_count | total_table_count |
|-----------------------|-------------------|------------------|-------------------|
| `plain_text`          | 0.0               | 0.0              | 0                 |
| `structured_markdown` | 28.5              | 28.5             | 23                |

Char counts identical (body preserved). Quality proxy delta is entirely from structural metadata.

## Known Stubs

None that affect plan goals. `StubPDFExtractor` and `StubDocxExtractor` are retained
as importable classes for backward compat but are not in `EXTRACTOR_REGISTRY`. PDF and
DOCX corpus files do not exist yet; both extractor paths are wired but untested on real docs.

## Self-Check: PASSED

Files checked:
- `docs/features/FEATURE-ris-v3-real-extractors.md` — FOUND
- `docs/dev_logs/2026-04-02_ris_phase3_real_extractor_and_backfill.md` — FOUND
- `tests/test_ris_real_extractors.py` — FOUND (42 tests)
- `tests/fixtures/ris_seed_corpus/sample_structured.md` — FOUND

Commits checked:
- ad96713 (Task 1) — FOUND
- eb208c3 (Task 2) — FOUND
- 2a118dc (Task 3) — FOUND

Full regression: 3110 passed, 0 failed — CONFIRMED
