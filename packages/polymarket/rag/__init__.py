"""Local RAG utilities (embeddings + chunking + indexing + querying)."""

from .chunker import TextChunk, chunk_text
from .embedder import BaseEmbedder, SentenceTransformerEmbedder
from .index import build_index
from .manifest import write_manifest
from .query import query_index

__all__ = [
    "BaseEmbedder",
    "SentenceTransformerEmbedder",
    "TextChunk",
    "build_index",
    "chunk_text",
    "query_index",
    "write_manifest",
]
