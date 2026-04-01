# Dev Log: RIS Phase 2 — Corpus Seeding and Extractor Benchmark

**Date:** 2026-04-01
**Session:** quick-260401-nzz (Tasks 1–3)
**Branch:** feat/ws-clob-feed
**Commits:** daf312e (Task 1), d3eafe9 (Task 2)

## Objective

Extend the RIS v1 ingestion pipeline with:
1. A manifest-driven batch seeder for the `docs/reference/` corpus (Task 1)
2. Extractor stubs, EXTRACTOR_REGISTRY, and a benchmark harness (Task 2)
3. Feature doc, dev log, and CURRENT_STATE update (Task 3)

## What Was Built

### Task 1 — Seed Manifest, Batch Seeder, research-seed CLI

**New files:**
- `config/seed_manifest.json` — 11 entries: 8 RAGfiles + 3 roadmap docs, all `source_family="book_foundational"`
- `packages/research/ingestion/seed.py` — `SeedEntry`, `SeedManifest`, `SeedResult`, `load_seed_manifest()`, `run_seed()`
- `tools/cli/research_seed.py` — `research-seed` CLI with `--manifest`, `--db`, `--no-eval`, `--dry-run`, `--json`
- `tests/test_ris_seed.py` — 18 tests, all offline/deterministic

**Modified files:**
- `packages/research/ingestion/__init__.py` — added seed exports
- `polytool/__main__.py` — registered `research-seed` and `research-benchmark` entrypoints

**TDD result:** 18/18 tests GREEN on first run.

**Key design decision:** `source_family` mismatch between `SOURCE_FAMILIES` in
`types.py` (maps `"book"` -> `"academic"`) and `freshness_decay.json` (uses
`"book_foundational"`). Resolution: `run_seed()` issues a direct SQL `UPDATE
source_documents SET source_family = ? WHERE id = ?` after each successful
ingestion to override with the manifest's authoritative value. This avoids
touching the pipeline or types.py mapping, which are shared across other flows.

### Task 2 — Extractor Stubs, EXTRACTOR_REGISTRY, Benchmark Harness

**New files:**
- `packages/research/ingestion/benchmark.py` — `ExtractorMetric`, `BenchmarkResult`, `run_extractor_benchmark()`
- `tools/cli/research_benchmark.py` — `research-benchmark` CLI with `--fixtures-dir`, `--extractors`, `--output-dir`, `--json`
- `tests/test_ris_extractor_benchmark.py` — 34 tests, all offline/deterministic
- `tests/fixtures/ris_seed_corpus/sample_structured.pdf.txt` — fixture file for benchmark tests

**Modified files:**
- `packages/research/ingestion/extractors.py` — added `MarkdownExtractor`, `StubPDFExtractor`, `StubDocxExtractor`, `EXTRACTOR_REGISTRY`, `get_extractor()`
- `packages/research/ingestion/__init__.py` — added benchmark and extractor exports

**TDD result:** 34/34 tests GREEN on first run.

**Key design decision:** `MarkdownExtractor` delegates entirely to
`PlainTextExtractor` (which already handles H1-title extraction and file-URI
generation for Markdown files). It exists as a separately-named class so callers
can register it under `"markdown"` in the registry and get a semantically named
extractor without duplicating logic.

**Key design decision:** Stub extractors (`StubPDFExtractor`, `StubDocxExtractor`)
raise `NotImplementedError` with messages that name the concrete libraries to
install. This surfaces the implementation gap at call time rather than returning
partial/empty documents that might be silently ingested.

**Key design decision:** `run_extractor_benchmark()` catches all exceptions
(including `NotImplementedError` from stubs) and records them as
`ExtractorMetric.error` strings. The harness never crashes on partial failures —
it gives a complete picture of what works and what doesn't across the extractor set.

## Tests Run

```
tests/test_ris_seed.py               — 18 passed
tests/test_ris_extractor_benchmark.py — 34 passed
```

Full regression (run as part of Task 3):
```
3012 passed, 0 failed, 25 warnings  (pre-existing datetime.utcnow() deprecation warnings, not this work)
```

## Scope Constraints Honored

- No new external dependencies added (no docling, marker, pymupdf4llm, python-docx)
- No changes to live execution, SimTrader, OMS, risk manager
- No changes to ClickHouse schema, benchmark manifests, or gate files
- Cloud LLM APIs NOT enabled by default (`--no-eval` is the seeder default)
- Stub extractors do NOT commit to any long-term parser choice

## Open Issues

- PDF and DOCX extraction remain stubs — wiring a real library is a separate task
- `research-seed` default manifest path (`config/seed_manifest.json`) does NOT exist at the default install location; first-time users must provide `--manifest` or initialize the config

## Codex Review

Tier: Skip (docs, tests, CLI formatting — no execution-path code touching OMS, risk, or kill switch)
