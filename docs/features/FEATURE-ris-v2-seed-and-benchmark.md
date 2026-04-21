# Feature: RIS Phase 2 — Corpus Seeding and Extractor Benchmark

**Status:** Implemented (2026-04-01, quick-260401-nzz)
**Track:** Research Intelligence System (RIS)

## Overview

Extends the RIS v1 ingestion pipeline with:

1. **Manifest-driven corpus seeder** (`research-seed` CLI) — ingests the
   `docs/reference/RAGfiles/` corpus and roadmap docs in one shot with stable
   deterministic IDs and authoritative `source_family` tagging.
2. **Extractor stubs and registry** — `MarkdownExtractor`, `StubPDFExtractor`,
   `StubDocxExtractor`, `EXTRACTOR_REGISTRY`, and `get_extractor()` factory.
3. **Benchmark harness** (`research-benchmark` CLI) — compares extractor outputs
   on a fixture directory, writes inspectable JSON artifacts.

## Architecture

```
config/seed_manifest.json            # manifest of docs to seed
  -> packages/research/ingestion/seed.py  # load_seed_manifest, run_seed
    -> packages/research/ingestion/pipeline.py  # IngestPipeline
      -> packages/polymarket/rag/knowledge_store.py  # KnowledgeStore

packages/research/ingestion/extractors.py  # PlainTextExtractor, MarkdownExtractor, StubPDF/DocxExtractor, EXTRACTOR_REGISTRY, get_extractor
packages/research/ingestion/benchmark.py   # ExtractorMetric, BenchmarkResult, run_extractor_benchmark
tools/cli/research_seed.py                 # research-seed CLI
tools/cli/research_benchmark.py            # research-benchmark CLI
```

## Seed Manifest

`config/seed_manifest.json` seeds 11 entries:
- 8 RAGfiles (`docs/reference/RAGfiles/`): RIS_OVERVIEW.md, RIS_01–RIS_07
- 3 roadmap docs: POLYTOOL_MASTER_ROADMAP_v4.2.md (archived), v5.md (archived), v5_1.md (current)

All entries use `source_family: "book_foundational"` (null half-life per
`config/freshness_decay.json`), so they never decay out of retrieval.

The seeder overrides `source_family` after ingestion via direct SQL UPDATE
because `IngestPipeline` maps `source_type="book"` to `"academic"` via
`SOURCE_FAMILIES`, which differs from the `freshness_decay.json` family keys.

## Extractor Registry

```python
from packages.research.ingestion.extractors import get_extractor, EXTRACTOR_REGISTRY

extractor = get_extractor("plain_text")   # PlainTextExtractor()
extractor = get_extractor("markdown")     # MarkdownExtractor()
extractor = get_extractor("pdf")          # StubPDFExtractor() — raises NotImplementedError
extractor = get_extractor("docx")         # StubDocxExtractor() — raises NotImplementedError
```

`StubPDFExtractor` error message mentions `docling`, `marker`, and `pymupdf4llm`
so the operator can pick a library when PDF support is needed.
`StubDocxExtractor` error message mentions `python-docx`.

## Benchmark Harness

```python
from packages.research.ingestion.benchmark import run_extractor_benchmark, BenchmarkResult

result = run_extractor_benchmark(
    Path("tests/fixtures/ris_seed_corpus"),
    extractors=["plain_text", "markdown"],
    output_dir=Path("artifacts/benchmark/extractor_eval"),
)
# result.metrics: list[ExtractorMetric]
# result.summary: {"plain_text": {"success_count": N, "fail_count": M}, ...}
```

Errors (including `NotImplementedError` from stub extractors) are caught and
recorded as `ExtractorMetric.error` strings — the harness never crashes on stubs.

## CLI Usage

```bash
# Seed the knowledge store from config/seed_manifest.json (default)
python -m polytool research-seed --no-eval --json

# Dry run (no writes, shows what would be ingested)
python -m polytool research-seed --dry-run

# Use a custom DB (e.g. in-memory for testing)
python -m polytool research-seed --db :memory: --no-eval

# Benchmark plain_text and markdown extractors on fixtures
python -m polytool research-benchmark \
  --fixtures-dir tests/fixtures/ris_seed_corpus \
  --extractors plain_text,markdown \
  --json

# Write artifact to disk
python -m polytool research-benchmark \
  --fixtures-dir docs/reference/RAGfiles \
  --output-dir artifacts/benchmark/extractor_eval
```

## Tests

- `tests/test_ris_seed.py` — 18 tests (seeder, manifest parsing, CLI smoke)
- `tests/test_ris_extractor_benchmark.py` — 34 tests (extractors, registry, benchmark harness, CLI smoke)
- Fixture: `tests/fixtures/ris_seed_corpus/sample_structured.pdf.txt`

All tests are offline and deterministic (no network calls, no ClickHouse, no external LLM).

## Not Included (Stubs / Future Work)

- Real PDF extraction — use `docling`, `marker`, or `pymupdf4llm` when needed
- Real DOCX extraction — use `python-docx` when needed
- Chunking-level benchmarks — current benchmark measures document-level char/word counts only
- Cloud LLM eval during seeding — `--no-eval` is the default for seed; operator decision required to enable
