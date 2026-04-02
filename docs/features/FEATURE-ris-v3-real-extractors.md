# FEATURE: RIS Phase 3 — Real Extractor Integration and Corpus Backfill

**Status:** Implemented (2026-04-02)
**Plan:** quick-260402-m6p
**Replaces:** RIS Phase 2 stub extractors (StubPDFExtractor, StubDocxExtractor)

---

## Overview

RIS Phase 3 replaces stub extractors with real implementations and adds a
structure-aware Markdown extractor that materially improves metadata quality
over plain text ingestion. The entire `docs/reference/` corpus is Markdown
(no PDF or DOCX files exist yet), so `StructuredMarkdownExtractor` is the
highest-impact improvement for current corpus quality.

**What this plan adds:**

- `StructuredMarkdownExtractor` — section-aware Markdown extractor that
  captures structural metadata (section list, heading count, table count,
  code block count) alongside the preserved body text
- `PDFExtractor` — real pdfplumber-backed extractor with graceful
  `ImportError` fallback when the optional dep is absent
- `DocxExtractor` — real python-docx-backed extractor with graceful
  `ImportError` fallback when the optional dep is absent
- Enhanced benchmark harness with quality proxy metrics per extraction
- Seed manifest v3 with explicit extractor field on all entries
- `--reseed` CLI flag for re-ingesting existing documents with improved extractors

---

## Extractor Hierarchy

```
Extractor (ABC)
├── PlainTextExtractor          key: "plain_text"     — raw UTF-8 text
├── MarkdownExtractor           key: "markdown"        — lightweight Markdown (title from H1)
├── StructuredMarkdownExtractor key: "structured_markdown" — section/table/code metadata
├── PDFExtractor                key: "pdf"             — pdfplumber (optional dep)
└── DocxExtractor               key: "docx"            — python-docx (optional dep)
```

All extractors return `ExtractedDocument(title, body, source_url, source_family,
author, publish_date, metadata)`. Structural metadata lives in `metadata`.

---

## EXTRACTOR_REGISTRY

```python
EXTRACTOR_REGISTRY = {
    "plain_text":           PlainTextExtractor,
    "markdown":             MarkdownExtractor,
    "structured_markdown":  StructuredMarkdownExtractor,
    "pdf":                  PDFExtractor,
    "docx":                 DocxExtractor,
}
```

`get_extractor(name)` instantiates the class. Raises `KeyError` for unknown
names. `PDFExtractor` and `DocxExtractor` raise `ImportError` at call-time
(inside `extract()`) when the optional dep is absent — this is not raised at
import time or registry lookup time.

`StubPDFExtractor` and `StubDocxExtractor` are retained for backward
compatibility but are no longer registered.

---

## StructuredMarkdownExtractor

**Location:** `packages/research/ingestion/extractors.py`

**Parsing logic:**

| Metadata key      | How extracted                                         |
|-------------------|-------------------------------------------------------|
| `sections`        | Lines matching `^#{1,6}\s+(.+)` — list of heading text strings |
| `section_count`   | `len(sections)`                                       |
| `header_count`    | Same as `section_count` (total heading lines)         |
| `table_count`     | Blocks of pipe-delimited rows containing a separator row (`---`) |
| `code_block_count`| Count of fenced code block pairs (``` or ~~~)         |
| `content_hash`    | SHA256 of raw body text (same as PlainTextExtractor)  |

Body text is returned **unchanged** — Markdown structure is preserved, not
stripped. The value-add is the structural metadata, not body transformation.

**Fallback:** If structural parsing raises any exception, the extractor falls
back to `PlainTextExtractor` behavior (returns body with only `content_hash`
in metadata, no structural fields). This ensures no corpus-wide failures from
edge-case documents.

**Auto-detect:** Extension `.md` and `.markdown` map to `"structured_markdown"`
in the seed auto-detect table, replacing the old `"structured_markdown"` ->
`plain_text` fallback.

---

## PDFExtractor

**Location:** `packages/research/ingestion/extractors.py`

Optional dep: `pdfplumber`. If not installed, `extract()` raises:
```
ImportError: PDF extraction requires pdfplumber. Install: pip install pdfplumber
```

When installed: opens PDF, concatenates all page text, extracts title from first
non-empty page content or filename stem, populates `metadata["page_count"]`.

---

## DocxExtractor

**Location:** `packages/research/ingestion/extractors.py`

Optional dep: `python-docx` (imported as `import docx`). If not installed,
`extract()` raises:
```
ImportError: DOCX extraction requires python-docx. Install: pip install python-docx
```

When installed: opens DOCX, concatenates all paragraph text, extracts title from
first heading-style paragraph or filename stem, populates `metadata["paragraph_count"]`.

---

## Benchmark Quality Proxies

`ExtractorMetric` now includes:

| Field              | Type  | Description                           |
|--------------------|-------|---------------------------------------|
| `section_count`    | `int` | Sections detected by extractor        |
| `header_count`     | `int` | Total headings detected               |
| `table_count`      | `int` | Table blocks detected                 |
| `code_block_count` | `int` | Code fences detected                  |
| `extractor_used`   | `str` | Extractor registry key used           |

`BenchmarkResult.summary` per-extractor dict now includes:
- `avg_section_count` — mean sections across all successful extractions
- `avg_header_count` — mean headers across all successful extractions
- `total_table_count` — sum of tables across all files

---

## Seed Manifest v3

`config/seed_manifest.json` bumped to version `"3"`. All 11 entries have:

```json
"extractor": "structured_markdown"
```

This instructs the seeder to use `StructuredMarkdownExtractor` instead of the
auto-detected plain text path.

**Extractor auto-detection** (when `extractor` field is null/absent):

| Extension        | Resolved extractor     |
|------------------|------------------------|
| `.md`, `.markdown` | `structured_markdown` |
| `.pdf`           | `pdf`                  |
| `.docx`, `.doc`  | `docx`                 |
| other            | `plain_text`           |

---

## Reseed Workflow

**CLI flag:** `python -m polytool research-seed --reseed`

**Behavior when `--reseed` is set:**
1. For each manifest entry, query `source_documents WHERE source_url = ?`
2. DELETE all matching rows before re-ingesting
3. Run `IngestPipeline.ingest()` fresh — doc_id is recomputed from content hash
4. If content is unchanged, the same doc_id is produced (deterministic)
5. Result dict includes `"extractor_used"` field for traceability

**When to use:** After an extractor upgrade (e.g., Phase 3 migration from
plain text to structured_markdown). Without `--reseed`, the seeder skips
existing documents (INSERT OR IGNORE semantics).

---

## CLI Usage

```bash
# Seed the corpus using manifest-specified extractors
python -m polytool research-seed --manifest config/seed_manifest.json --no-eval

# Re-ingest with improved extractors (replaces existing docs)
python -m polytool research-seed --manifest config/seed_manifest.json --reseed --no-eval

# Dry run to preview what would be ingested
python -m polytool research-seed --manifest config/seed_manifest.json --dry-run

# Benchmark plain_text vs structured_markdown on the reference corpus
python -m polytool research-benchmark \
  --fixtures-dir docs/reference/RAGfiles \
  --extractors plain_text,structured_markdown \
  --json
```

---

## Not Included

- **Cloud extractors** (Azure Document Intelligence, AWS Textract) — out of scope pre-profit
- **Qdrant** or other vector stores — Chroma remains the current vector backend
- **Chunking-level benchmarks** — ExtractorMetric measures whole-document quality
- **PDF/DOCX corpus files** — no such files exist in `docs/reference/` yet; extractors
  are wired and ready but untested on real docs
- **Semantic section splitting** — sections are detected by heading regex only;
  no NLP-based boundary detection
- **Table structured parsing** — table_count is detection only; table content is not
  parsed into row/column structure

---

## Files Changed

| File | Change |
|------|--------|
| `packages/research/ingestion/extractors.py` | Added `StructuredMarkdownExtractor`, `PDFExtractor`, `DocxExtractor`; updated `EXTRACTOR_REGISTRY` |
| `packages/research/ingestion/benchmark.py` | Added quality proxy fields to `ExtractorMetric`; updated per-extractor summary |
| `packages/research/ingestion/seed.py` | Added `extractor` field to `SeedEntry`, `_detect_extractor()`, `reseed` param to `run_seed()` |
| `packages/research/ingestion/__init__.py` | Added exports for new extractor classes |
| `config/seed_manifest.json` | Bumped to v3; added `extractor` field to all 11 entries |
| `tools/cli/research_seed.py` | Added `--reseed` flag; added Extractor column to human-readable output |
| `tests/test_ris_real_extractors.py` | 42 new tests for extractors, benchmark quality proxies, seed/reseed |
| `tests/fixtures/ris_seed_corpus/sample_structured.md` | Rich Markdown fixture for structural extraction tests |
| `tests/test_ris_extractor_benchmark.py` | Updated 2 tests for real PDFExtractor/DocxExtractor (no longer stubs) |
| `tests/test_ris_calibration.py` | Updated manifest version assertion (v2 -> v2 or v3) |
