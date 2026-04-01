---
phase: quick-260401-nzz
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - config/seed_manifest.json
  - packages/research/ingestion/seed.py
  - packages/research/ingestion/extractors.py
  - packages/research/ingestion/benchmark.py
  - packages/research/ingestion/__init__.py
  - tools/cli/research_seed.py
  - tools/cli/research_benchmark.py
  - polytool/__main__.py
  - tests/test_ris_seed.py
  - tests/test_ris_extractor_benchmark.py
  - tests/fixtures/ris_seed_corpus/sample_structured.pdf.txt
  - docs/features/FEATURE-ris-v2-seed-and-benchmark.md
  - docs/dev_logs/2026-04-01_ris_phase2_seed_and_extractor_benchmark.md
  - docs/CURRENT_STATE.md
autonomous: true
must_haves:
  truths:
    - "research-seed CLI ingests all manifest entries into KnowledgeStore with stable deterministic IDs"
    - "Running research-seed twice produces identical doc_ids (idempotent)"
    - "Each seeded document has correct source_family tag matching freshness_decay.json families"
    - "research-benchmark CLI compares PlainTextExtractor against stub extractors on a fixed fixture set and writes inspectable artifacts"
    - "Extractor ABC remains the single interface contract; new extractors implement it without changing pipeline.py"
  artifacts:
    - path: "config/seed_manifest.json"
      provides: "Explicit, reproducible corpus selection for seeding"
      contains: "docs/reference/RAGfiles"
    - path: "packages/research/ingestion/seed.py"
      provides: "Manifest-driven batch seeder with stable ID generation"
      exports: ["SeedManifest", "SeedEntry", "SeedResult", "run_seed"]
    - path: "packages/research/ingestion/benchmark.py"
      provides: "Extractor benchmark harness comparing outputs across extractors"
      exports: ["BenchmarkResult", "run_extractor_benchmark"]
    - path: "tools/cli/research_seed.py"
      provides: "research-seed CLI entrypoint"
      exports: ["main"]
    - path: "tools/cli/research_benchmark.py"
      provides: "research-benchmark CLI entrypoint"
      exports: ["main"]
    - path: "tests/test_ris_seed.py"
      provides: "Deterministic offline tests for seeding"
      min_lines: 80
    - path: "tests/test_ris_extractor_benchmark.py"
      provides: "Deterministic offline tests for benchmark harness"
      min_lines: 50
  key_links:
    - from: "packages/research/ingestion/seed.py"
      to: "packages/research/ingestion/pipeline.py"
      via: "IngestPipeline.ingest() calls per manifest entry"
      pattern: "pipeline\\.ingest"
    - from: "packages/research/ingestion/seed.py"
      to: "config/seed_manifest.json"
      via: "JSON manifest loading"
      pattern: "seed_manifest"
    - from: "packages/research/ingestion/benchmark.py"
      to: "packages/research/ingestion/extractors.py"
      via: "Extractor ABC implementations"
      pattern: "Extractor"
    - from: "tools/cli/research_seed.py"
      to: "packages/research/ingestion/seed.py"
      via: "run_seed() call"
      pattern: "run_seed"
---

<objective>
Build RIS Phase 2 corpus seeding from docs/reference/ and an extractor benchmark harness.

Purpose: Enable reproducible ingestion of the RIS reference corpus into the KnowledgeStore
with stable IDs, source_family tags, and provenance metadata. Provide an extractor benchmark
harness that compares parser outputs on a fixed fixture set without committing to any single
long-term parser.

Output: research-seed CLI command, seed manifest config, extractor benchmark harness,
interface-ready extractor stubs (PDF/structured), deterministic tests, feature doc, dev log.
</objective>

<execution_context>
@D:/Coding Projects/Polymarket/PolyTool/.claude/get-shit-done/workflows/execute-plan.md
@D:/Coding Projects/Polymarket/PolyTool/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@config/freshness_decay.json
@packages/research/ingestion/extractors.py
@packages/research/ingestion/pipeline.py
@packages/research/ingestion/retriever.py
@packages/research/ingestion/__init__.py
@packages/research/evaluation/types.py
@packages/polymarket/rag/knowledge_store.py
@tools/cli/research_ingest.py
@tests/test_ris_ingestion_integration.py
@polytool/__main__.py

<interfaces>
<!-- Key types and contracts the executor needs. Extracted from codebase. -->

From packages/research/ingestion/extractors.py:
```python
@dataclass
class ExtractedDocument:
    title: str
    body: str
    source_url: str
    source_family: str
    author: str = "unknown"
    publish_date: Optional[str] = None
    metadata: dict = field(default_factory=dict)

class Extractor(ABC):
    @abstractmethod
    def extract(self, source: "str | Path", **kwargs) -> ExtractedDocument: ...

class PlainTextExtractor(Extractor):
    def extract(self, source: "str | Path", **kwargs) -> ExtractedDocument: ...
```

From packages/research/ingestion/pipeline.py:
```python
@dataclass
class IngestResult:
    doc_id: str
    chunk_count: int
    gate_decision: Optional[GateDecision]
    rejected: bool
    reject_reason: Optional[str]

class IngestPipeline:
    def __init__(self, store: KnowledgeStore, extractor: Optional[Extractor] = None, evaluator=None) -> None: ...
    def ingest(self, source: "str | Path", **kwargs) -> IngestResult: ...
```

From packages/research/evaluation/types.py:
```python
SOURCE_FAMILIES: dict[str, str] = {
    "arxiv": "academic", "ssrn": "academic", "book": "academic",
    "reddit": "forum_social", "twitter": "forum_social", "youtube": "forum_social",
    "github": "github", "blog": "blog", "news": "news",
    "dossier": "dossier_report", "manual": "manual",
}
```

From config/freshness_decay.json:
```json
{
  "source_families": {
    "academic_foundational": null, "book_foundational": null,
    "academic_empirical": 18, "preprint": 12, "github": 12,
    "blog": 9, "reddit": 6, "twitter": 6, "youtube": 6,
    "wallet_analysis": 6, "news": 3
  }
}
```

Note: SOURCE_FAMILIES in types.py maps source_type -> source_family, but the freshness_decay.json
keys are different family names (e.g. "academic_foundational" vs "academic"). The seed manifest
should use source_family values that match freshness_decay.json keys for correct decay behavior.
The seed command should set source_family directly on the IngestPipeline call, not rely on the
SOURCE_FAMILIES mapping (which is for eval-gate source_type -> family mapping).

From polytool/__main__.py (CLI routing pattern):
```python
_COMMAND_MAP = {
    ...
    "research-eval": "research_eval_main",
    "research-precheck": "research_precheck_main",
    "research-ingest": "research_ingest_main",
}
```
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Seed manifest, batch seeder, and research-seed CLI</name>
  <files>
    config/seed_manifest.json,
    packages/research/ingestion/seed.py,
    packages/research/ingestion/__init__.py,
    tools/cli/research_seed.py,
    polytool/__main__.py,
    tests/test_ris_seed.py
  </files>
  <behavior>
    - Test: Loading seed_manifest.json parses into SeedManifest with correct entry count (8 RAGfiles + 3 roadmap docs = 11 entries)
    - Test: run_seed() with in-memory KnowledgeStore ingests all manifest entries; returned SeedResult has correct ingested/skipped/failed counts
    - Test: Running run_seed() twice on same manifest produces identical doc_ids (idempotent via INSERT OR IGNORE)
    - Test: Each seeded document has source_family matching the manifest entry's source_family field
    - Test: run_seed() with a manifest containing a non-existent file path records it as failed (not crash)
    - Test: Seed with --dry-run flag lists what would be ingested without writing to KnowledgeStore
    - Test: CLI research-seed --manifest config/seed_manifest.json --no-eval --json exits 0 and returns summary JSON
  </behavior>
  <action>
    1. Create `config/seed_manifest.json`:
       - JSON with version field, description, and entries array.
       - Each entry: `{"path": "docs/reference/RAGfiles/RIS_OVERVIEW.md", "title": "RIS Overview", "source_type": "book", "source_family": "book_foundational", "author": "PolyTool Team", "publish_date": "2026-03-01T00:00:00+00:00", "tags": ["ris", "architecture"]}`.
       - Include all 8 RAGfiles from `docs/reference/RAGfiles/` with source_family "book_foundational" (timeless internal reference docs).
       - Include the 3 roadmap docs from `docs/reference/` with source_family "book_foundational".
       - Total: 11 entries. Use descriptive titles derived from document H1 headings.

    2. Create `packages/research/ingestion/seed.py`:
       - Dataclasses: `SeedEntry(path, title, source_type, source_family, author, publish_date, tags)`, `SeedManifest(version, description, entries: list[SeedEntry])`, `SeedResult(total, ingested, skipped, failed, results: list[dict])`.
       - `load_seed_manifest(manifest_path: Path) -> SeedManifest`: Load and parse JSON manifest into SeedManifest. Validate required fields.
       - `run_seed(manifest: SeedManifest, store: KnowledgeStore, *, dry_run: bool = False, skip_eval: bool = True, base_dir: Optional[Path] = None) -> SeedResult`:
         - For each entry, resolve path relative to base_dir (default: repo root).
         - If dry_run, collect entries without writing; return SeedResult with ingested=0.
         - Otherwise call IngestPipeline.ingest() for each entry, passing source_type, author, publish_date, title from the manifest entry.
         - IMPORTANT: After IngestPipeline stores the doc, update the source_document's source_family directly via `store._conn.execute("UPDATE source_documents SET source_family = ? WHERE id = ?", (entry.source_family, result.doc_id))` + commit, because PlainTextExtractor maps source_type through SOURCE_FAMILIES which produces different family keys than what freshness_decay.json expects. The seed manifest's source_family values are authoritative.
         - Catch FileNotFoundError and record as failed entry (do not crash).
         - Return SeedResult with counts and per-entry results (doc_id, status, reject_reason).

    3. Update `packages/research/ingestion/__init__.py`: Add SeedManifest, SeedEntry, SeedResult, run_seed, load_seed_manifest to __all__ and imports.

    4. Create `tools/cli/research_seed.py`:
       - `main(argv: list) -> int` following the pattern in research_ingest.py.
       - Args: `--manifest PATH` (default: config/seed_manifest.json), `--db PATH`, `--no-eval` (default: True for seed), `--dry-run`, `--json`.
       - Load manifest via load_seed_manifest(), create KnowledgeStore, call run_seed().
       - Human-readable output: table of ingested docs with doc_id, title, status.
       - JSON output: full SeedResult serialization.
       - Exit 0 on success (even if some entries fail), exit 1 on argument error, exit 2 on unexpected exception.

    5. Wire into `polytool/__main__.py`:
       - Add `"research-seed": "research_seed_main"` to _COMMAND_MAP.
       - Add the import dispatch (same pattern as research_ingest_main).
       - Add help text line under the RIS section: `"  research-seed          Seed the RIS knowledge store from a manifest"`.
       - Also wire research-benchmark (Task 2) at the same time: `"research-benchmark": "research_benchmark_main"` with help text `"  research-benchmark     Compare extractor outputs on a fixture set"`.

    6. Write `tests/test_ris_seed.py`:
       - All tests use in-memory KnowledgeStore (`:memory:`).
       - Use tmp_path to create small fixture files for manifest testing (do not depend on real docs/reference/ files for unit tests).
       - Test manifest parsing, run_seed idempotency, source_family correctness, dry-run behavior, failed-entry handling, CLI smoke test (subprocess).
  </action>
  <verify>
    <automated>python -m pytest tests/test_ris_seed.py -v --tb=short</automated>
  </verify>
  <done>
    research-seed CLI ingests all manifest entries; running twice produces identical doc_ids;
    source_family tags match freshness_decay.json families; dry-run lists without writing;
    non-existent paths recorded as failed not crashed; all tests pass.
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Extractor stubs, benchmark harness, and research-benchmark CLI</name>
  <files>
    packages/research/ingestion/extractors.py,
    packages/research/ingestion/benchmark.py,
    packages/research/ingestion/__init__.py,
    tools/cli/research_benchmark.py,
    tests/test_ris_extractor_benchmark.py,
    tests/fixtures/ris_seed_corpus/sample_structured.pdf.txt
  </files>
  <behavior>
    - Test: MarkdownExtractor inherits Extractor ABC and produces ExtractedDocument with title from H1
    - Test: StubPDFExtractor.extract() raises NotImplementedError with a message indicating "install docling/marker/pymupdf"
    - Test: StubDocxExtractor.extract() raises NotImplementedError with a message indicating "install python-docx"
    - Test: run_extractor_benchmark() on a fixture set returns BenchmarkResult with per-extractor per-file metrics (char_count, word_count, title, elapsed_ms, error)
    - Test: run_extractor_benchmark() records errors for stub extractors (NotImplementedError) without crashing
    - Test: Benchmark writes artifacts/ris_benchmark/ output (comparison JSON) to the specified output_dir
    - Test: CLI research-benchmark --fixtures-dir <dir> --json exits 0 and prints valid JSON
  </behavior>
  <action>
    1. Extend `packages/research/ingestion/extractors.py`:
       - Add `MarkdownExtractor(Extractor)`: Identical to PlainTextExtractor but explicitly named for markdown files. Reuses PlainTextExtractor.extract() internally (thin wrapper) -- exists to have a distinct name in benchmark comparisons and to be a future extension point for markdown-specific parsing (e.g., front-matter extraction).
       - Add `StubPDFExtractor(Extractor)`: `extract()` raises `NotImplementedError("PDF extraction requires an external library. Install one of: docling, marker, pymupdf4llm. See docs/features/FEATURE-ris-v2-seed-and-benchmark.md")`.
       - Add `StubDocxExtractor(Extractor)`: `extract()` raises `NotImplementedError("DOCX extraction requires python-docx. See docs/features/FEATURE-ris-v2-seed-and-benchmark.md")`.
       - Add `EXTRACTOR_REGISTRY: dict[str, type[Extractor]]` mapping `{"plain_text": PlainTextExtractor, "markdown": MarkdownExtractor, "pdf": StubPDFExtractor, "docx": StubDocxExtractor}`.
       - Add `get_extractor(name: str) -> Extractor` factory function that instantiates from registry.

    2. Create `packages/research/ingestion/benchmark.py`:
       - Dataclasses: `ExtractorMetric(extractor_name: str, file_name: str, char_count: int, word_count: int, title: str, elapsed_ms: float, error: Optional[str])`, `BenchmarkResult(metrics: list[ExtractorMetric], summary: dict)`.
       - `run_extractor_benchmark(fixtures_dir: Path, extractors: Optional[list[str]] = None, output_dir: Optional[Path] = None) -> BenchmarkResult`:
         - Default extractors: all keys from EXTRACTOR_REGISTRY.
         - For each file in fixtures_dir (*.md, *.txt, *.pdf.txt), for each extractor:
           - Try extractor.extract(file_path, source_type="manual").
           - On success: record char_count=len(body), word_count=len(body.split()), title, elapsed_ms.
           - On NotImplementedError or other exception: record error=str(exc), char_count=0, word_count=0.
         - Summary: per-extractor success_count, fail_count, avg_char_count.
         - If output_dir is set: write `benchmark_results.json` with full metrics + summary + timestamp. Create output_dir if it does not exist.
       - No network calls. Pure filesystem + in-process extraction.

    3. Create `tests/fixtures/ris_seed_corpus/sample_structured.pdf.txt`:
       - A plain-text file that simulates what a PDF extractor *would* produce (extracted text from a hypothetical PDF). ~15 lines of research-style content about prediction market fee structures. This lets the benchmark harness have a .pdf.txt fixture to exercise without requiring an actual PDF dependency.

    4. Update `packages/research/ingestion/__init__.py`: Add MarkdownExtractor, StubPDFExtractor, StubDocxExtractor, EXTRACTOR_REGISTRY, get_extractor, BenchmarkResult, run_extractor_benchmark to __all__ and imports.

    5. Create `tools/cli/research_benchmark.py`:
       - `main(argv: list) -> int` following the CLI pattern.
       - Args: `--fixtures-dir PATH` (default: tests/fixtures/ris_seed_corpus/), `--extractors` (comma-separated, default: all), `--output-dir PATH` (default: artifacts/ris_benchmark/), `--json`.
       - Calls run_extractor_benchmark(), prints human-readable comparison table or JSON.
       - Exit 0 on success, 1 on argument error, 2 on unexpected exception.

    6. Write `tests/test_ris_extractor_benchmark.py`:
       - All tests use tmp_path for fixture files and output dirs.
       - Test MarkdownExtractor produces valid ExtractedDocument.
       - Test StubPDFExtractor raises NotImplementedError.
       - Test StubDocxExtractor raises NotImplementedError.
       - Test EXTRACTOR_REGISTRY and get_extractor factory.
       - Test run_extractor_benchmark returns BenchmarkResult with correct counts.
       - Test benchmark writes artifacts to output_dir.
       - Test CLI smoke (subprocess).
  </action>
  <verify>
    <automated>python -m pytest tests/test_ris_extractor_benchmark.py -v --tb=short</automated>
  </verify>
  <done>
    Extractor stubs exist for PDF and DOCX; MarkdownExtractor works as thin wrapper;
    EXTRACTOR_REGISTRY provides pluggable lookup; benchmark harness compares outputs
    across extractors on fixture files; benchmark artifacts are inspectable JSON;
    all tests pass; no new external dependencies added.
  </done>
</task>

<task type="auto">
  <name>Task 3: Feature doc, dev log, CURRENT_STATE update, full regression</name>
  <files>
    docs/features/FEATURE-ris-v2-seed-and-benchmark.md,
    docs/dev_logs/2026-04-01_ris_phase2_seed_and_extractor_benchmark.md,
    docs/CURRENT_STATE.md
  </files>
  <action>
    1. Create `docs/features/FEATURE-ris-v2-seed-and-benchmark.md`:
       - Document the research-seed command: usage, manifest format, source_family tagging, idempotency.
       - Document the research-benchmark command: usage, extractor registry, benchmark output format.
       - Document the extractor plug-in pattern: how to add a new extractor (implement Extractor ABC, register in EXTRACTOR_REGISTRY).
       - "Deferred" section: list what is NOT shipped (Docling/Marker/MinerU integration, automatic claim extraction, Chroma wiring, cloud extractors). Mark each as deferred with rationale.
       - "Shipped extractor stubs" section: explain StubPDFExtractor and StubDocxExtractor are interface placeholders that raise NotImplementedError; they exist so the benchmark harness can report which extractors are missing.

    2. Create `docs/dev_logs/2026-04-01_ris_phase2_seed_and_extractor_benchmark.md`:
       - Follow mandatory dev log format: Files changed, Commands run + output, Decisions made, Test results, Seed corpus chosen and why, Benchmark observations, Open questions.
       - Include exact test counts from pytest runs.
       - Note the SOURCE_FAMILIES vs freshness_decay.json family name mismatch and how seed.py handles it.

    3. Update `docs/CURRENT_STATE.md`:
       - Append to the RIS section: "RIS Phase 2 seed + benchmark shipped: research-seed CLI ingests 11 docs/reference/ files via manifest-driven pipeline; research-benchmark CLI compares extractor outputs; EXTRACTOR_REGISTRY provides pluggable extractor lookup; PDF/DOCX stubs ready for future library integration."

    4. Run full regression:
       ```
       python -m polytool --help
       python -m pytest tests/ -x -q --tb=short
       ```
       Record exact pass/fail/skip counts in the dev log.

    5. Run one real seed smoke test:
       ```
       python -m polytool research-seed --manifest config/seed_manifest.json --no-eval --json --db :memory:
       ```
       Capture output in dev log. Verify all 11 entries ingested with status "ingested".

    6. Run one real benchmark smoke test:
       ```
       python -m polytool research-benchmark --fixtures-dir tests/fixtures/ris_seed_corpus/ --json
       ```
       Capture output in dev log. Verify PlainTextExtractor/MarkdownExtractor succeed, StubPDF/StubDocx report errors.
  </action>
  <verify>
    <automated>python -m pytest tests/ -x -q --tb=short</automated>
  </verify>
  <done>
    Feature doc describes shipped behavior and deferred items; dev log records exact commands,
    outputs, decisions, and test counts; CURRENT_STATE.md reflects RIS Phase 2; full regression
    suite passes with no regressions; real seed and benchmark smoke tests produce expected output.
  </done>
</task>

</tasks>

<verification>
1. `python -m pytest tests/test_ris_seed.py tests/test_ris_extractor_benchmark.py -v --tb=short` -- all new tests pass
2. `python -m pytest tests/ -x -q --tb=short` -- full regression, no regressions
3. `python -m polytool --help` -- CLI loads, research-seed and research-benchmark visible
4. `python -m polytool research-seed --manifest config/seed_manifest.json --no-eval --json --db :memory:` -- 11 entries ingested
5. `python -m polytool research-benchmark --fixtures-dir tests/fixtures/ris_seed_corpus/ --json` -- comparison output with successes and expected errors
</verification>

<success_criteria>
- research-seed CLI exists and ingests all 11 manifest entries with stable IDs
- Running seed twice on same DB is idempotent (same doc_ids, no duplicates)
- Source families in KnowledgeStore match freshness_decay.json keys
- Extractor ABC remains the single interface contract
- EXTRACTOR_REGISTRY provides pluggable extractor lookup
- Benchmark harness compares extraction outputs and writes inspectable artifacts
- No new external dependencies added (stdlib + existing deps only)
- All existing tests continue to pass
- Dev log and feature doc written with exact shipped behavior
</success_criteria>

<output>
After completion, create `.planning/quick/260401-nzz-build-ris-phase-2-corpus-seeding-from-do/260401-nzz-SUMMARY.md`
</output>
