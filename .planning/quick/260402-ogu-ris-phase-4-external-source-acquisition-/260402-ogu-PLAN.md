---
phase: quick-260402-ogu
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - packages/research/ingestion/source_cache.py
  - packages/research/ingestion/adapters.py
  - packages/research/ingestion/normalize.py
  - packages/research/ingestion/__init__.py
  - packages/research/ingestion/pipeline.py
  - packages/research/evaluation/types.py
  - tools/cli/research_ingest.py
  - polytool/__main__.py
  - tests/fixtures/ris_external_sources/arxiv_sample.json
  - tests/fixtures/ris_external_sources/github_sample.json
  - tests/fixtures/ris_external_sources/blog_sample.json
  - tests/test_ris_phase4_source_acquisition.py
  - docs/features/FEATURE-ris-phase4-source-acquisition.md
  - docs/dev_logs/2026-04-02_ris_phase4_source_acquisition.md
  - docs/CURRENT_STATE.md
autonomous: true
must_haves:
  truths:
    - "External-style sources (academic, github, blog) can be ingested through adapter boundaries"
    - "Raw source payload is cached on disk before any processing"
    - "Metadata is normalized with canonical IDs (DOI, arXiv ID, repo URL) and dedup-sensitive fields"
    - "Fixtures exist for each source family enabling offline testing without network"
    - "Adapted sources flow through the existing eval gate and IngestPipeline into KnowledgeStore"
  artifacts:
    - path: "packages/research/ingestion/source_cache.py"
      provides: "RawSourceCache: disk-backed preservation of original payloads with metadata"
    - path: "packages/research/ingestion/adapters.py"
      provides: "SourceAdapter ABC + AcademicAdapter, GithubAdapter, BlogNewsAdapter implementations"
    - path: "packages/research/ingestion/normalize.py"
      provides: "Metadata normalization, canonical ID extraction (DOI/arXiv/SSRN/repo URL), URL canonicalization"
    - path: "tests/test_ris_phase4_source_acquisition.py"
      provides: "Deterministic tests for cache, normalization, adapters, and end-to-end flow"
  key_links:
    - from: "packages/research/ingestion/adapters.py"
      to: "packages/research/ingestion/extractors.py"
      via: "Adapter.adapt() returns ExtractedDocument"
      pattern: "ExtractedDocument"
    - from: "packages/research/ingestion/adapters.py"
      to: "packages/research/ingestion/source_cache.py"
      via: "Adapter stores raw payload in RawSourceCache before producing ExtractedDocument"
      pattern: "RawSourceCache"
    - from: "packages/research/ingestion/adapters.py"
      to: "packages/research/ingestion/normalize.py"
      via: "Adapter calls normalize_metadata() to produce canonical metadata"
      pattern: "normalize_metadata"
    - from: "packages/research/ingestion/pipeline.py"
      to: "packages/research/ingestion/adapters.py"
      via: "IngestPipeline.ingest_external() uses adapter to convert raw source dict into ExtractedDocument"
      pattern: "ingest_external"
---

<objective>
Build RIS Phase 4 external source acquisition: raw-source caching, adapter boundaries for
three source families (academic/preprint, GitHub/repo, blog/news/article), metadata
normalization with canonical IDs, and a CLI/callable path that ingests fixture-backed
external-style sources through the full adapter -> cache -> normalize -> eval -> store
pipeline.

Purpose: RIS can now ingest repeatable external-style sources with raw-source preservation,
making future live-scraper automation straightforward without requiring orchestration yet.

Output:
- `packages/research/ingestion/source_cache.py` (RawSourceCache)
- `packages/research/ingestion/adapters.py` (SourceAdapter ABC + 3 family adapters)
- `packages/research/ingestion/normalize.py` (metadata normalization + canonical IDs)
- Updated `IngestPipeline` with `ingest_external()` method
- CLI `research-ingest --from-adapter` path
- 3 fixture files + deterministic test suite
- Feature doc + dev log + CURRENT_STATE.md update
</objective>

<execution_context>
@D:/Coding Projects/Polymarket/PolyTool/.claude/get-shit-done/workflows/execute-plan.md
@D:/Coding Projects/Polymarket/PolyTool/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@packages/research/ingestion/__init__.py
@packages/research/ingestion/extractors.py
@packages/research/ingestion/pipeline.py
@packages/research/ingestion/seed.py
@packages/research/ingestion/retriever.py
@packages/research/evaluation/types.py
@packages/research/evaluation/feature_extraction.py
@packages/research/evaluation/dedup.py
@tools/cli/research_ingest.py
@polytool/__main__.py
@packages/polymarket/rag/knowledge_store.py
@tests/fixtures/ris_seed_corpus/

<interfaces>
<!-- Key types and contracts the executor needs -->

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
```

From packages/research/evaluation/types.py:
```python
@dataclass
class EvalDocument:
    doc_id: str
    title: str
    author: str
    source_type: str
    source_url: str
    source_publish_date: Optional[str]
    body: str
    metadata: dict = field(default_factory=dict)

SOURCE_FAMILIES: dict[str, str] = {
    "arxiv": "academic", "ssrn": "academic", "book": "academic",
    "reddit": "forum_social", "twitter": "forum_social", "youtube": "forum_social",
    "github": "github", "blog": "blog", "news": "news",
    "dossier": "dossier_report", "manual": "manual",
    "reference_doc": "book_foundational", "roadmap": "book_foundational",
}
```

From packages/research/ingestion/pipeline.py:
```python
class IngestPipeline:
    def __init__(self, store, extractor=None, evaluator=None): ...
    def ingest(self, source, **kwargs) -> IngestResult: ...

@dataclass
class IngestResult:
    doc_id: str
    chunk_count: int
    gate_decision: Optional[GateDecision]
    rejected: bool
    reject_reason: Optional[str]
```

From packages/polymarket/rag/knowledge_store.py:
```python
class KnowledgeStore:
    def add_source_document(self, *, title, source_url, source_family,
                            content_hash, chunk_count, published_at,
                            ingested_at, confidence_tier, metadata_json) -> str: ...
```
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Build raw-source cache, metadata normalization, and source adapters</name>
  <files>
    packages/research/ingestion/source_cache.py,
    packages/research/ingestion/normalize.py,
    packages/research/ingestion/adapters.py,
    packages/research/evaluation/types.py,
    tests/fixtures/ris_external_sources/arxiv_sample.json,
    tests/fixtures/ris_external_sources/github_sample.json,
    tests/fixtures/ris_external_sources/blog_sample.json,
    tests/test_ris_phase4_source_acquisition.py
  </files>
  <behavior>
    RAW-SOURCE CACHE (source_cache.py):
    - RawSourceCache(cache_dir: Path) — disk-backed cache storing original payloads
    - cache_raw(source_id: str, payload: dict, source_family: str) -> Path — writes JSON to cache_dir/source_family/source_id.json with envelope: {source_id, source_family, cached_at (UTC ISO), payload}
    - get_raw(source_id: str, source_family: str) -> Optional[dict] — reads cached envelope, returns None if missing
    - has_raw(source_id: str, source_family: str) -> bool
    - source_id is deterministic: sha256 of canonical_url or fallback identifier
    - Test: cache_raw then get_raw returns same payload; has_raw returns True; missing returns None; cache_dir auto-created

    METADATA NORMALIZATION (normalize.py):
    - normalize_metadata(raw: dict, source_family: str) -> NormalizedMetadata dataclass
    - NormalizedMetadata: canonical_url, title, author, publish_date, source_family, source_type, canonical_ids (dict of doi/arxiv_id/ssrn_id/repo_url as applicable), publisher, raw_metadata (original dict)
    - canonicalize_url(url: str) -> str — strips fragments, trailing slashes, lowercases scheme+host, normalizes arxiv abs/pdf URLs, normalizes github URLs
    - extract_canonical_ids(text: str, url: str) -> dict — extracts DOI (10.NNNN/...), arXiv ID (YYMM.NNNNN), SSRN ID (ssrn:\d{6,}), GitHub repo URL (github.com/owner/repo)
    - Test: DOI extracted from body text; arXiv ID from URL and body; GitHub repo URL normalized; duplicate-sensitive IDs are stable; canonical_url strips fragment/trailing-slash

    SOURCE ADAPTERS (adapters.py):
    - SourceAdapter(ABC) with adapt(raw_source: dict, cache: Optional[RawSourceCache] = None) -> ExtractedDocument
    - AcademicAdapter: expects raw_source with keys {url, title, abstract, authors, published_date, body_text (optional)}. Extracts DOI/arXiv/SSRN IDs. Sets source_type="arxiv"|"ssrn"|"book" based on URL heuristic. Normalizes metadata. Caches raw if cache provided. Returns ExtractedDocument with source_family="academic", metadata including canonical_ids.
    - GithubAdapter: expects raw_source with keys {repo_url, readme_text, description, stars, forks, license, last_commit_date}. Sets source_type="github". Normalizes repo URL. Caches raw. Returns ExtractedDocument with source_family="github", metadata including stars/forks/commit_recency.
    - BlogNewsAdapter: expects raw_source with keys {url, title, body_text, author, published_date, publisher}. Sets source_type="blog"|"news" (heuristic: known news domains -> "news", else "blog"). Normalizes URL. Caches raw. Returns ExtractedDocument with source_family="blog"|"news".
    - ADAPTER_REGISTRY: dict mapping source_family -> adapter class
    - get_adapter(family: str) -> SourceAdapter
    - Test per adapter: fixture dict in -> ExtractedDocument out with correct fields; canonical_ids populated; raw cached when cache provided; missing optional fields handled gracefully

    FIXTURES (tests/fixtures/ris_external_sources/):
    - arxiv_sample.json: realistic arXiv-like source with DOI, arXiv ID, abstract, authors
    - github_sample.json: realistic GitHub repo source with readme, stars, forks, license
    - blog_sample.json: realistic blog/article source with byline, date, publisher

    Update packages/research/evaluation/types.py:
    - No new source families needed — existing SOURCE_FAMILIES already covers arxiv/ssrn/github/blog/news. No changes unless a new source_type is introduced by adapters.
  </behavior>
  <action>
    1. Create tests/fixtures/ris_external_sources/ directory with three JSON fixture files.
       Each fixture is a dict representing what a future scraper would produce:
       - arxiv_sample.json: {url: "https://arxiv.org/abs/2301.12345", title: "Prediction Market Microstructure...", abstract: "We study...", authors: ["A. Smith", "B. Jones"], published_date: "2023-01-15", body_text: "... contains DOI 10.1234/pm.2023.001 and arXiv:2301.12345 references ... methodology regression p-value sample size ..."}
       - github_sample.json: {repo_url: "https://github.com/polymarket/py-clob-client", readme_text: "# py-clob-client\nPython client for Polymarket CLOB...\n## License\nMIT", description: "Python CLOB client", stars: 142, forks: 38, license: "MIT", last_commit_date: "2026-03-15"}
       - blog_sample.json: {url: "https://blog.polymarket.com/prediction-markets-2026", title: "The State of Prediction Markets in 2026", body_text: "By Jane Doe\n\nPublished January 2026\n\n# Introduction\n\nPrediction markets have grown...", author: "Jane Doe", published_date: "2026-01-10", publisher: "Polymarket Blog"}

    2. Create tests/test_ris_phase4_source_acquisition.py with RED tests for:
       - TestRawSourceCache: test_cache_and_retrieve, test_has_raw_true_false, test_get_missing_returns_none, test_cache_dir_auto_created, test_source_id_deterministic, test_envelope_has_required_fields
       - TestNormalization: test_canonicalize_url_strips_fragment, test_canonicalize_url_trailing_slash, test_canonicalize_url_arxiv_normalize, test_canonicalize_url_github_normalize, test_extract_doi, test_extract_arxiv_id_from_body, test_extract_arxiv_id_from_url, test_extract_ssrn_id, test_extract_github_repo_url, test_normalize_metadata_academic, test_normalize_metadata_github, test_normalize_metadata_blog
       - TestAcademicAdapter: test_adapt_arxiv_fixture, test_adapt_produces_correct_source_family, test_adapt_extracts_canonical_ids, test_adapt_caches_raw, test_adapt_missing_optional_fields
       - TestGithubAdapter: test_adapt_github_fixture, test_adapt_produces_correct_metadata, test_adapt_caches_raw
       - TestBlogNewsAdapter: test_adapt_blog_fixture, test_adapt_news_heuristic, test_adapt_caches_raw
       - TestAdapterRegistry: test_get_adapter_academic, test_get_adapter_github, test_get_adapter_blog

    3. Create packages/research/ingestion/source_cache.py:
       - RawSourceCache class with cache_dir, cache_raw(), get_raw(), has_raw()
       - source_id computation: hashlib.sha256(canonical_url.encode()).hexdigest()[:16]
       - Storage path: cache_dir / source_family / f"{source_id}.json"
       - Envelope: {"source_id": ..., "source_family": ..., "cached_at": utcnow_iso, "payload": raw_dict}
       - All I/O uses json.dumps/loads with ensure_ascii=False, UTF-8 encoding

    4. Create packages/research/ingestion/normalize.py:
       - NormalizedMetadata dataclass: canonical_url, title, author, publish_date, source_family, source_type, canonical_ids (dict), publisher (Optional[str]), raw_metadata (dict)
       - canonicalize_url(url): strip #fragment, strip trailing /, lowercase scheme+host, normalize arxiv abs<->pdf (always use /abs/), normalize github to github.com/owner/repo (strip tree/blob suffixes)
       - extract_canonical_ids(text, url): return dict with optional keys doi, arxiv_id, ssrn_id, repo_url. Use same regex patterns as feature_extraction.py (_DOI_RE, _ARXIV_RE, _SSRN_RE) for consistency. Add github.com/owner/repo extraction from URL.
       - normalize_metadata(raw, source_family): build NormalizedMetadata from raw dict + family-specific field mapping

    5. Create packages/research/ingestion/adapters.py:
       - SourceAdapter ABC: adapt(raw_source: dict, cache: Optional[RawSourceCache] = None) -> ExtractedDocument
       - AcademicAdapter, GithubAdapter, BlogNewsAdapter implementing adapt()
       - Each adapter: (a) normalizes metadata via normalize.py, (b) caches raw payload if cache provided, (c) builds ExtractedDocument with correct source_family, metadata including canonical_ids
       - ADAPTER_REGISTRY: {"academic": AcademicAdapter, "github": GithubAdapter, "blog": BlogNewsAdapter, "news": BlogNewsAdapter}
       - get_adapter(family: str) -> SourceAdapter factory

    6. Run tests to go GREEN. Iterate until all pass.
  </action>
  <verify>
    <automated>python -m pytest tests/test_ris_phase4_source_acquisition.py -v --tb=short</automated>
  </verify>
  <done>
    - RawSourceCache stores and retrieves payloads deterministically
    - NormalizedMetadata extracts DOI, arXiv ID, SSRN ID, GitHub repo URL from text/URLs
    - canonicalize_url handles fragment stripping, trailing slash, arxiv/github normalization
    - Three adapters produce correct ExtractedDocument with populated canonical_ids
    - All adapters cache raw payload when cache is provided
    - Fixture files exist for offline testing of all three families
    - All tests pass with zero network calls
  </done>
</task>

<task type="auto">
  <name>Task 2: Wire adapters into IngestPipeline, add CLI path, update docs</name>
  <files>
    packages/research/ingestion/pipeline.py,
    packages/research/ingestion/__init__.py,
    tools/cli/research_ingest.py,
    polytool/__main__.py,
    tests/test_ris_phase4_source_acquisition.py,
    docs/features/FEATURE-ris-phase4-source-acquisition.md,
    docs/dev_logs/2026-04-02_ris_phase4_source_acquisition.md,
    docs/CURRENT_STATE.md
  </files>
  <action>
    1. Add ingest_external() method to IngestPipeline (pipeline.py):
       - Signature: ingest_external(self, raw_source: dict, source_family: str, *, cache: Optional[RawSourceCache] = None, **kwargs) -> IngestResult
       - Gets adapter via get_adapter(source_family)
       - Calls adapter.adapt(raw_source, cache=cache) to get ExtractedDocument
       - Merges any kwargs (override title, author, etc.) into the extracted doc
       - Continues with existing steps 2-7 (hard-stop, eval gate, chunk, store)
       - If adapter raises ValueError (missing required fields), return IngestResult with rejected=True, reject_reason describing the issue

    2. Update packages/research/ingestion/__init__.py:
       - Add exports: RawSourceCache, SourceAdapter, AcademicAdapter, GithubAdapter, BlogNewsAdapter, ADAPTER_REGISTRY, get_adapter, NormalizedMetadata, canonicalize_url, extract_canonical_ids, normalize_metadata

    3. Add CLI path in tools/cli/research_ingest.py:
       - Add --from-adapter flag (mutually exclusive with --file/--text)
       - --from-adapter takes a JSON file path containing the raw source dict
       - --source-family (required with --from-adapter): one of academic/github/blog/news
       - --cache-dir (optional): path for raw-source cache (default: artifacts/research/raw_source_cache/)
       - Workflow: load JSON -> create RawSourceCache(cache_dir) -> pipeline.ingest_external(raw_source, source_family, cache=cache)
       - Output: same as existing ingest output (doc_id, chunk_count, gate, rejected)

    4. Add integration tests to tests/test_ris_phase4_source_acquisition.py:
       - TestEndToEnd: test_ingest_external_arxiv_fixture (fixture -> ingest_external -> doc stored in KnowledgeStore with correct source_family and canonical_ids in metadata)
       - TestEndToEnd: test_ingest_external_github_fixture (same pattern)
       - TestEndToEnd: test_ingest_external_blog_fixture (same pattern)
       - TestEndToEnd: test_ingest_external_with_cache (verify raw payload persisted on disk)
       - TestEndToEnd: test_ingest_external_bad_family_rejected (unknown family -> rejected)
       - TestEndToEnd: test_ingest_external_missing_required_fields_rejected

    5. Run full regression: python -m pytest tests/ -x -q --tb=short
       Confirm zero new failures. Record exact pass count.

    6. Run CLI smoke test:
       python -m polytool research-ingest --from-adapter tests/fixtures/ris_external_sources/arxiv_sample.json --source-family academic --no-eval --json
       Verify output shows doc_id, chunk_count > 0, rejected=false.

    7. Create docs/features/FEATURE-ris-phase4-source-acquisition.md:
       - What shipped: RawSourceCache, 3 adapters, metadata normalization with canonical IDs, ingest_external() pipeline method, CLI --from-adapter path
       - Source families covered: academic (arXiv/SSRN/book), github, blog/news
       - Canonical IDs extracted: DOI, arXiv ID, SSRN ID, GitHub repo URL
       - Raw-source caching: disk-backed JSON envelopes under artifacts/research/raw_source_cache/{family}/
       - What remains deferred: live HTTP fetching (adapters are fixture-backed only), scraper orchestration, n8n, scheduler, additional source families (forum_social, dossier)

    8. Create docs/dev_logs/2026-04-02_ris_phase4_source_acquisition.md with:
       - Files changed and why
       - Commands run and exact output
       - Test results (targeted + full regression)
       - Source families and adapters implemented
       - Raw-source caching decisions (envelope format, disk layout, deterministic IDs)
       - Remaining gaps before full scraper automation
       - Note on pre-existing unrelated test failures

    9. Update docs/CURRENT_STATE.md: add RIS Phase 4 section after the Phase 3 section with:
       - Summary of what shipped
       - Module paths
       - CLI command example
       - Test count
       - Link to feature doc and dev log
  </action>
  <verify>
    <automated>python -m pytest tests/test_ris_phase4_source_acquisition.py tests/test_ris_ingestion_integration.py -v --tb=short && python -m polytool --help</automated>
  </verify>
  <done>
    - IngestPipeline.ingest_external() converts raw source dicts through adapters into stored documents
    - CLI research-ingest --from-adapter ingests fixture JSON through the full pipeline
    - Raw-source cache preserves original payloads on disk
    - Normalized metadata with canonical IDs survives into KnowledgeStore
    - All existing tests still pass (zero regressions)
    - Feature doc, dev log, and CURRENT_STATE.md updated
  </done>
</task>

</tasks>

<verification>
1. All tests in tests/test_ris_phase4_source_acquisition.py pass (adapter + cache + normalization + end-to-end)
2. Existing tests in tests/test_ris_ingestion_integration.py still pass (no regressions)
3. Full regression: python -m pytest tests/ -x -q --tb=short reports zero new failures
4. CLI smoke: python -m polytool research-ingest --from-adapter tests/fixtures/ris_external_sources/arxiv_sample.json --source-family academic --no-eval --json produces valid output
5. python -m polytool --help loads cleanly with no import errors
</verification>

<success_criteria>
- RIS has a real external-source acquisition layer with raw-source preservation
- Three source families (academic, github, blog/news) are adapter-backed and fixture-tested
- Metadata normalization extracts canonical IDs (DOI, arXiv, SSRN, repo URL) for dedup
- Raw payloads are cached on disk before any processing
- Adapted sources flow through eval gate and into KnowledgeStore
- Zero regressions in existing test suite
- Docs updated with exact shipped behavior
</success_criteria>

<output>
After completion, create `.planning/quick/260402-ogu-ris-phase-4-external-source-acquisition-/260402-ogu-SUMMARY.md`
</output>
