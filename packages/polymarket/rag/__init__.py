"""Local RAG utilities with lazy exports for optional heavy dependencies."""

from __future__ import annotations

from importlib import import_module
from typing import Any

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

_EXPORTS: dict[str, tuple[str, str]] = {
    "BaseEmbedder": ("packages.polymarket.rag.embedder", "BaseEmbedder"),
    "BaseReranker": ("packages.polymarket.rag.reranker", "BaseReranker"),
    "CrossEncoderReranker": ("packages.polymarket.rag.reranker", "CrossEncoderReranker"),
    "EvalCase": ("packages.polymarket.rag.eval", "EvalCase"),
    "EvalReport": ("packages.polymarket.rag.eval", "EvalReport"),
    "SentenceTransformerEmbedder": (
        "packages.polymarket.rag.embedder",
        "SentenceTransformerEmbedder",
    ),
    "TextChunk": ("packages.polymarket.rag.chunker", "TextChunk"),
    "build_chunk_metadata": ("packages.polymarket.rag.metadata", "build_chunk_metadata"),
    "build_chroma_where": ("packages.polymarket.rag.query", "build_chroma_where"),
    "build_index": ("packages.polymarket.rag.index", "build_index"),
    "canonicalize_rel_path": ("packages.polymarket.rag.metadata", "canonicalize_rel_path"),
    "chunk_text": ("packages.polymarket.rag.chunker", "chunk_text"),
    "compute_chunk_id": ("packages.polymarket.rag.metadata", "compute_chunk_id"),
    "compute_doc_id": ("packages.polymarket.rag.metadata", "compute_doc_id"),
    "lexical_query": ("packages.polymarket.rag.lexical", "lexical_query"),
    "lexical_search": ("packages.polymarket.rag.lexical", "lexical_search"),
    "list_indexed_file_paths": (
        "packages.polymarket.rag.lexical",
        "list_indexed_file_paths",
    ),
    "load_suite": ("packages.polymarket.rag.eval", "load_suite"),
    "query_index": ("packages.polymarket.rag.query", "query_index"),
    "reconcile_index": ("packages.polymarket.rag.index", "reconcile_index"),
    "reciprocal_rank_fusion": (
        "packages.polymarket.rag.lexical",
        "reciprocal_rank_fusion",
    ),
    "rerank_results": ("packages.polymarket.rag.reranker", "rerank_results"),
    "run_eval": ("packages.polymarket.rag.eval", "run_eval"),
    "write_manifest": ("packages.polymarket.rag.manifest", "write_manifest"),
    "write_report": ("packages.polymarket.rag.eval", "write_report"),
}


def __getattr__(name: str) -> Any:
    try:
        module_name, attr_name = _EXPORTS[name]
    except KeyError as exc:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from exc

    module = import_module(module_name)
    value = getattr(module, attr_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
