---
phase: quick
plan: 260401-nzz
subsystem: research-ingestion
tags: [ris, ingestion, seeding, benchmark, extractors, manifest]
dependency_graph:
  requires: [packages/research/ingestion/pipeline.py, packages/polymarket/rag/knowledge_store.py, config/freshness_decay.json]
  provides: [packages/research/ingestion/seed.py, packages/research/ingestion/benchmark.py, packages/research/ingestion/extractors.py (extended), tools/cli/research_seed.py, tools/cli/research_benchmark.py]
  affects: [packages/research/ingestion/__init__.py, polytool/__main__.py, docs/CURRENT_STATE.md]
tech_stack:
  added: []
  patterns: [manifest-driven batch seeding, stub extractor pattern, pluggable extractor registry, benchmark harness with error capture]
key_files:
  created:
    - config/seed_manifest.json
    - packages/research/ingestion/seed.py
    - packages/research/ingestion/benchmark.py
    - tools/cli/research_seed.py
    - tools/cli/research_benchmark.py
    - tests/test_ris_seed.py
    - tests/test_ris_extractor_benchmark.py
    - tests/fixtures/ris_seed_corpus/sample_structured.pdf.txt
    - docs/features/FEATURE-ris-v2-seed-and-benchmark.md
    - docs/dev_logs/2026-04-01_ris_phase2_seed_and_extractor_benchmark.md
  modified:
    - packages/research/ingestion/extractors.py
    - packages/research/ingestion/__init__.py
    - polytool/__main__.py
    - docs/CURRENT_STATE.md
decisions:
  - source_family override via direct SQL UPDATE after IngestPipeline (avoids touching shared SOURCE_FAMILIES mapping)
  - MarkdownExtractor delegates to PlainTextExtractor (no logic duplication, named for registry clarity)
  - Stub extractors raise NotImplementedError with library name hints (surfaces gap at call time, not silent empty docs)
  - Benchmark harness catches all exceptions including NotImplementedError (never crashes on partial failures)
metrics:
  duration: ~40 minutes (split across two context sessions)
  completed_date: 2026-04-01
  tasks_completed: 3
  files_created: 10
  files_modified: 4
  tests_added: 52
  regression_total: 3012
---

# Phase quick Plan 260401-nzz: RIS Phase 2 Corpus Seeding and Extractor Benchmark Summary

**One-liner:** Manifest-driven corpus seeder for docs/reference/ with source_family override, pluggable extractor registry with MarkdownExtractor and PDF/DOCX stubs, and a benchmark harness writing JSON artifacts — all backed by 52 offline TDD tests.

## Tasks Completed

| Task | Name | Commit | Key Files |
|------|------|--------|-----------|
| 1 | Seed manifest, batch seeder, research-seed CLI | daf312e | config/seed_manifest.json, packages/research/ingestion/seed.py, tools/cli/research_seed.py, tests/test_ris_seed.py |
| 2 | Extractor stubs, EXTRACTOR_REGISTRY, benchmark harness, research-benchmark CLI | d3eafe9 | packages/research/ingestion/extractors.py, packages/research/ingestion/benchmark.py, tools/cli/research_benchmark.py, tests/test_ris_extractor_benchmark.py |
| 3 | Feature doc, dev log, CURRENT_STATE update, full regression | 04956f3 | docs/features/FEATURE-ris-v2-seed-and-benchmark.md, docs/dev_logs/2026-04-01_ris_phase2_seed_and_extractor_benchmark.md, docs/CURRENT_STATE.md |

## What Was Built

### Seed Manifest and Batch Seeder

`config/seed_manifest.json` defines 11 entries for the docs/reference/ corpus (8 RAGfiles + 3 roadmap docs). `packages/research/ingestion/seed.py` implements:

- `load_seed_manifest(path) -> SeedManifest` — parses JSON manifest, validates required fields
- `run_seed(manifest, store, *, dry_run, skip_eval, base_dir) -> SeedResult` — ingests all entries via IngestPipeline, then overrides source_family via direct SQL UPDATE

The source_family override is necessary because IngestPipeline maps `source_type="book"` to `"academic"` (via `SOURCE_FAMILIES` in types.py), but freshness_decay.json uses `"book_foundational"` for the null-half-life family. The SQL UPDATE is applied post-ingestion to the authoritative manifest value without touching any shared mapping.

### Extractor Registry

`packages/research/ingestion/extractors.py` extended with:

- `MarkdownExtractor(Extractor)` — delegates to `PlainTextExtractor`, explicitly named for registry
- `StubPDFExtractor(Extractor)` — raises `NotImplementedError` mentioning `docling`, `marker`, `pymupdf4llm`
- `StubDocxExtractor(Extractor)` — raises `NotImplementedError` mentioning `python-docx`
- `EXTRACTOR_REGISTRY: dict[str, type[Extractor]]` — `{plain_text, markdown, pdf, docx}`
- `get_extractor(name) -> Extractor` — factory, raises `KeyError` on unknown name

### Benchmark Harness

`packages/research/ingestion/benchmark.py`:

- `ExtractorMetric` — extractor_name, file_name, char_count, word_count, elapsed_ms, error
- `BenchmarkResult` — metrics list, per-extractor summary with success_count/fail_count
- `run_extractor_benchmark(fixture_dir, *, extractors, output_dir) -> BenchmarkResult` — iterates all (extractor, file) pairs, catches all exceptions, writes `benchmark_results.json` if output_dir given

### CLIs

```bash
python -m polytool research-seed --manifest config/seed_manifest.json --no-eval
python -m polytool research-seed --dry-run --json
python -m polytool research-benchmark --fixtures-dir tests/fixtures/ris_seed_corpus --extractors plain_text,markdown --json
```

## Verification

```
python -m pytest tests/test_ris_seed.py               # 18 passed
python -m pytest tests/test_ris_extractor_benchmark.py # 34 passed
python -m pytest tests/ -x -q                          # 3012 passed, 0 failed
python -m polytool research-seed --manifest config/seed_manifest.json --db :memory: --no-eval
# Seed complete: 11 ingested, 0 skipped, 0 failed (total: 11)
python -m polytool research-benchmark --fixtures-dir tests/fixtures/ris_seed_corpus --extractors plain_text,markdown
# Benchmark complete: 6 measurements across 2 extractor(s)  success=3 each
```

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

- `StubPDFExtractor.extract()` — always raises NotImplementedError. Intentional: no PDF library chosen yet. Future plan: wire docling/marker/pymupdf4llm when needed.
- `StubDocxExtractor.extract()` — always raises NotImplementedError. Intentional: python-docx not installed. Future plan: wire when DOCX support needed.

These stubs do NOT prevent the plan's goal from being achieved. The benchmark harness explicitly records NotImplementedError as `ExtractorMetric.error` and continues — stub behavior is the defined contract for unimplemented extractors.

## Self-Check: PASSED

Created files exist:
- config/seed_manifest.json: FOUND
- packages/research/ingestion/seed.py: FOUND
- packages/research/ingestion/benchmark.py: FOUND
- tools/cli/research_seed.py: FOUND
- tools/cli/research_benchmark.py: FOUND
- tests/test_ris_seed.py: FOUND
- tests/test_ris_extractor_benchmark.py: FOUND
- tests/fixtures/ris_seed_corpus/sample_structured.pdf.txt: FOUND
- docs/features/FEATURE-ris-v2-seed-and-benchmark.md: FOUND
- docs/dev_logs/2026-04-01_ris_phase2_seed_and_extractor_benchmark.md: FOUND

Commits exist:
- daf312e: FOUND (Task 1)
- d3eafe9: FOUND (Task 2)
- 04956f3: FOUND (Task 3)
