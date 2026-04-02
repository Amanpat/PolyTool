# Dev Log: RIS Phase 3 — Real Extractor Integration and Corpus Backfill

**Date:** 2026-04-02
**Plan:** quick-260402-m6p
**Branch:** feat/ws-clob-feed

---

## Objective

Replace stub extractors with real implementations, add a structure-aware Markdown
extractor, enhance the benchmark harness with quality proxy metrics, and add a
reseed workflow. Full corpus backfill of `docs/reference/` with `structured_markdown`.

---

## Files Changed

| File | Change |
|------|--------|
| `packages/research/ingestion/extractors.py` | Added `StructuredMarkdownExtractor`, `PDFExtractor`, `DocxExtractor`; updated `EXTRACTOR_REGISTRY` |
| `packages/research/ingestion/benchmark.py` | Added `section_count`, `header_count`, `table_count`, `code_block_count`, `extractor_used` to `ExtractorMetric`; updated summary stats |
| `packages/research/ingestion/seed.py` | Added `extractor` field to `SeedEntry`, `_detect_extractor()` helper, `reseed: bool` param to `run_seed()` |
| `packages/research/ingestion/__init__.py` | Exported `StructuredMarkdownExtractor`, `PDFExtractor`, `DocxExtractor` |
| `config/seed_manifest.json` | Bumped version "2" -> "3"; added `"extractor": "structured_markdown"` to all 11 entries |
| `tools/cli/research_seed.py` | Added `--reseed` flag; added Extractor column to human-readable table output |
| `tests/test_ris_real_extractors.py` | 42 new offline tests for all new functionality |
| `tests/fixtures/ris_seed_corpus/sample_structured.md` | Rich Markdown fixture with H1/H2/H3, pipe table, fenced code block |
| `tests/test_ris_extractor_benchmark.py` | Updated 2 tests: `test_get_extractor_pdf` now expects `PDFExtractor`, not `StubPDFExtractor` |
| `tests/test_ris_calibration.py` | Updated manifest version assertion to accept "2" or "3" |

---

## Extractor Choice Rationale

**Why StructuredMarkdownExtractor is the right primary extractor for the current corpus:**

The entire `docs/reference/` corpus is Markdown (RIS_OVERVIEW.md, RIS_0[1-7]_*.md,
three roadmap docs). No PDFs or DOCX files exist. PlainTextExtractor treats all these
files as flat text, discarding heading structure entirely. This means the knowledge store
cannot surface structural provenance ("this claim comes from Section 4.2 on ingestion
hard stops") — the claim appears as context-free body text.

`StructuredMarkdownExtractor` adds structural metadata to `ExtractedDocument.metadata`
without transforming or stripping the body. The body is passed to RAG unchanged; the
metadata is used by the benchmark harness and can be used by future chunking logic.

**Why pdfplumber/python-docx are optional deps, not hard deps:**

Neither `pdfplumber` nor `python-docx` is currently needed for any corpus file. Making
them optional means the extractor path is wired and ready the moment a PDF or DOCX
appears in `docs/reference/`, without adding install friction for the current Markdown-only
workflow. The optional-dep pattern mirrors how existing rag optional deps work in the repo.

**The fallback chain when reseed is used:**
1. Manifest entry has explicit `extractor: "structured_markdown"` — uses `StructuredMarkdownExtractor`
2. Manifest entry has no extractor — auto-detect from extension: `.md` -> `structured_markdown`
3. `get_extractor()` raises `KeyError` or `ImportError` — falls back to `PlainTextExtractor`

---

## Test Results

### Targeted test run (Task 1 + Task 2 verification)

```
python -m pytest tests/test_ris_real_extractors.py tests/test_ris_extractor_benchmark.py tests/test_ris_seed.py -v --tb=short
```

Result: **94 passed, 0 failed**

### Full regression (Task 3 — after test_ris_calibration.py fix)

```
python -m pytest tests/ -x -q --tb=short
```

Result: **3110 passed, 0 failed, 25 warnings** (92 seconds)

The only deviation from baseline was `test_real_seed_manifest_v2_parses` in
`test_ris_calibration.py` which was checking for manifest version exactly `"2"`.
This was a test accuracy issue (not a behavior bug): the test name says "v2_parses"
but the assertion was checking for the exact string `"2"` rather than checking that
the manifest parses with all 11 valid entries. Fixed by updating the assertion to
`assert manifest.version in ("2", "3")` and the docstring to reflect v3. The
underlying behavior (parse all 11 entries, check source types, check evidence tiers)
is unchanged.

---

## Benchmark Comparison: plain_text vs structured_markdown on Real Corpus

Command:
```
python -m polytool research-benchmark \
  --fixtures-dir docs/reference/RAGfiles \
  --extractors plain_text,structured_markdown \
  --json
```

### Summary statistics

| Extractor           | Files | Success | avg_section_count | avg_header_count | total_table_count |
|---------------------|-------|---------|-------------------|------------------|-------------------|
| `plain_text`        | 8     | 8       | 0.0               | 0.0              | 0                 |
| `structured_markdown` | 8   | 8       | 28.5              | 28.5             | 23                |

### Per-file results (structured_markdown)

| File                      | sections | headers | tables | code_blocks | char_count |
|---------------------------|----------|---------|--------|-------------|------------|
| RIS_01_INGESTION_ACADEMIC | 26       | 26      | 1      | 5           | 16,222     |
| RIS_02_INGESTION_SOCIAL   | 26       | 26      | 4      | 5           | 14,964     |
| RIS_03_EVALUATION_GATE    | 27       | 27      | 6      | 8           | 16,504     |
| RIS_04_KNOWLEDGE_STORE    | 24       | 24      | 2      | 11          | 15,463     |
| RIS_05_SYNTHESIS_ENGINE   | 37       | 37      | 2      | 12          | 14,442     |
| RIS_06_INFRASTRUCTURE     | 34       | 34      | 3      | 8           | 10,876     |
| RIS_07_INTEGRATION        | 29       | 29      | 3      | 10          | 13,989     |
| RIS_OVERVIEW              | 25       | 25      | 2      | 5           | 17,493     |

**Observations:**
- `plain_text` produces zero structural metadata on every file (as expected — it reads
  raw bytes and does not parse Markdown structure).
- `structured_markdown` detects an average of 28.5 sections per file, 23 tables total
  across 8 files, and between 5-12 code blocks per file.
- Char counts are identical between extractors (body text is not transformed).
- Elapsed_ms for `structured_markdown` is ~1-2ms vs ~7-12ms for `plain_text` on these
  files — the structural parsing regex is fast; the speed difference likely reflects
  OS I/O variance since both read the same files.
- All 8 files are rich, well-structured technical documents; the heading/table/code
  metadata correctly reflects their structure.

---

## Remaining Gaps and Parser-Quality Limits

1. **No semantic chunking**: Section detection is by heading regex only. The body is
   returned whole; there is no splitting at section boundaries. Future work: chunk by
   section for more targeted RAG retrieval.

2. **No PDF/DOCX corpus files yet**: `PDFExtractor` and `DocxExtractor` are wired and
   ready, but the `docs/reference/` corpus contains no PDF or DOCX files as of
   2026-04-02. Both extractors remain untested on real documents.

3. **Table extraction is detection-only**: `table_count` counts table blocks; the cell
   contents are not parsed into row/column structure. Table data remains in the body text
   as raw Markdown pipe syntax.

4. **No heading hierarchy tracking**: All headings (H1-H6) are counted equally. The
   `sections` list is flat — no nesting of H3 under H2 under H1. Future work: build
   section tree from heading depth.

5. **Code block language detection**: Fenced code blocks are counted but their language
   specifier (```python, ```json, etc.) is not extracted into metadata.

---

## Codex Review

Tier: Skip (docs, config, tests, research tooling — not execution/kill-switch/risk code).
No adversarial review required.

---

## Open Questions

None. Plan executed as specified with one deviation (calibration test version assertion fix).
