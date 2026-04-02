"""RIS v1 ingestion pipeline package.

Provides pluggable extraction, pipeline orchestration, seed manifest tooling,
and retrieval helpers for ingesting external research documents into the
KnowledgeStore.
"""

from packages.research.ingestion.extractors import (
    Extractor,
    ExtractedDocument,
    PlainTextExtractor,
    MarkdownExtractor,
    StructuredMarkdownExtractor,
    PDFExtractor,
    DocxExtractor,
    StubPDFExtractor,
    StubDocxExtractor,
    EXTRACTOR_REGISTRY,
    get_extractor,
)
from packages.research.ingestion.pipeline import IngestPipeline, IngestResult
from packages.research.ingestion.source_cache import RawSourceCache, make_source_id
from packages.research.ingestion.normalize import (
    NormalizedMetadata,
    canonicalize_url,
    extract_canonical_ids,
    normalize_metadata,
)
from packages.research.ingestion.adapters import (
    SourceAdapter,
    AcademicAdapter,
    GithubAdapter,
    BlogNewsAdapter,
    ADAPTER_REGISTRY,
    get_adapter,
)
from packages.research.ingestion.seed import (
    SeedEntry,
    SeedManifest,
    SeedResult,
    load_seed_manifest,
    run_seed,
)
from packages.research.ingestion.benchmark import (
    BenchmarkResult,
    ExtractorMetric,
    run_extractor_benchmark,
)
from packages.research.ingestion.claim_extractor import (
    HeuristicClaimExtractor,
    extract_claims_from_document,
    build_intra_doc_relations,
    extract_and_link,
    EXTRACTOR_ID as CLAIM_EXTRACTOR_ID,
)

__all__ = [
    # Extractors
    "Extractor",
    "ExtractedDocument",
    "PlainTextExtractor",
    "MarkdownExtractor",
    "StructuredMarkdownExtractor",
    "PDFExtractor",
    "DocxExtractor",
    "StubPDFExtractor",
    "StubDocxExtractor",
    "EXTRACTOR_REGISTRY",
    "get_extractor",
    # Pipeline
    "IngestPipeline",
    "IngestResult",
    # Phase 4 — Source Cache
    "RawSourceCache",
    "make_source_id",
    # Phase 4 — Normalization
    "NormalizedMetadata",
    "canonicalize_url",
    "extract_canonical_ids",
    "normalize_metadata",
    # Phase 4 — Adapters
    "SourceAdapter",
    "AcademicAdapter",
    "GithubAdapter",
    "BlogNewsAdapter",
    "ADAPTER_REGISTRY",
    "get_adapter",
    # Seed
    "SeedEntry",
    "SeedManifest",
    "SeedResult",
    "load_seed_manifest",
    "run_seed",
    # Benchmark
    "BenchmarkResult",
    "ExtractorMetric",
    "run_extractor_benchmark",
    # Phase 4 — Claim Extraction
    "HeuristicClaimExtractor",
    "extract_claims_from_document",
    "build_intra_doc_relations",
    "extract_and_link",
    "CLAIM_EXTRACTOR_ID",
]
