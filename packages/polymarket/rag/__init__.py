"""Local RAG utilities (embeddings + chunking + indexing + querying)."""

from .chunker import TextChunk, chunk_text
from .embedder import BaseEmbedder, SentenceTransformerEmbedder
from .index import build_index
from .manifest import write_manifest
from .metadata import build_chunk_metadata, canonicalize_rel_path, compute_chunk_id, compute_doc_id
from .query import build_chroma_where, query_index

__all__ = [
    "BaseEmbedder",
    "SentenceTransformerEmbedder",
    "TextChunk",
    "build_chunk_metadata",
    "build_chroma_where",
    "canonicalize_rel_path",
    "build_index",
    "chunk_text",
    "compute_chunk_id",
    "compute_doc_id",
    "query_index",
    "write_manifest",
]
