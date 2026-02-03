"""Local RAG utilities (embeddings + chunking + indexing + querying + eval)."""

from .chunker import TextChunk, chunk_text
from .embedder import BaseEmbedder, SentenceTransformerEmbedder
from .eval import EvalCase, EvalReport, load_suite, run_eval, write_report
from .index import build_index, reconcile_index
from .lexical import lexical_query, lexical_search, list_indexed_file_paths, reciprocal_rank_fusion
from .manifest import write_manifest
from .metadata import build_chunk_metadata, canonicalize_rel_path, compute_chunk_id, compute_doc_id
from .query import build_chroma_where, query_index
from .reranker import BaseReranker, CrossEncoderReranker, rerank_results

__all__ = [
    "BaseEmbedder",
    "BaseReranker",
    "CrossEncoderReranker",
    "EvalCase",
    "EvalReport",
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
    "list_indexed_file_paths",
    "load_suite",
    "query_index",
    "reconcile_index",
    "reciprocal_rank_fusion",
    "rerank_results",
    "run_eval",
    "write_manifest",
    "write_report",
]
