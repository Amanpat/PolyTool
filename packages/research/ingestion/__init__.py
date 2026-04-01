"""RIS v1 ingestion pipeline package.

Provides pluggable extraction, pipeline orchestration, and retrieval helpers
for ingesting external research documents into the KnowledgeStore.
"""

from packages.research.ingestion.extractors import (
    Extractor,
    ExtractedDocument,
    PlainTextExtractor,
)
from packages.research.ingestion.pipeline import IngestPipeline, IngestResult

__all__ = [
    "Extractor",
    "ExtractedDocument",
    "PlainTextExtractor",
    "IngestPipeline",
    "IngestResult",
]
