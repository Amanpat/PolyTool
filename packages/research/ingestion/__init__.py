"""RIS v1 ingestion pipeline package.

Provides pluggable extraction, pipeline orchestration, seed manifest tooling,
and retrieval helpers for ingesting external research documents into the
KnowledgeStore.
"""

from packages.research.ingestion.extractors import (
    Extractor,
    ExtractedDocument,
    PlainTextExtractor,
)
from packages.research.ingestion.pipeline import IngestPipeline, IngestResult
from packages.research.ingestion.seed import (
    SeedEntry,
    SeedManifest,
    SeedResult,
    load_seed_manifest,
    run_seed,
)

__all__ = [
    # Extractors
    "Extractor",
    "ExtractedDocument",
    "PlainTextExtractor",
    # Pipeline
    "IngestPipeline",
    "IngestResult",
    # Seed
    "SeedEntry",
    "SeedManifest",
    "SeedResult",
    "load_seed_manifest",
    "run_seed",
]
