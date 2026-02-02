"""Local RAG utilities (embeddings + chunking + indexing + querying)."""

from .chunker import TextChunk, chunk_text
from .embedder import BaseEmbedder, SentenceTransformerEmbedder
from .index import build_index
from .lexical import lexical_query, lexical_search, reciprocal_rank_fusion
from .manifest import write_manifest
from .metadata import build_chunk_metadata, canonicalize_rel_path, compute_chunk_id, compute_doc_id
from .query import build_chroma_where, query_index

__all__ = [
    "BaseEmbedder",
    "SentenceTransformerEmbedder",
    "TextChunk",
    "build_chunk_metadata",
    "build_chroma_where",
    "build_index",
    "canonicalize_rel_path",
    "chunk_text",
    "compute_chunk_id",
    "compute_doc_id",
    "lexical_query",
    "lexical_search",
    "query_index",
    "reciprocal_rank_fusion",
    "write_manifest",
]
