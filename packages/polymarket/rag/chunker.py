"""Deterministic, overlap-based chunking for local RAG."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class TextChunk:
    chunk_id: int
    text: str
    start_word: int
    end_word: int


def chunk_text(text: str, chunk_size: int = 400, overlap: int = 80) -> List[TextChunk]:
    """Split text into deterministic word chunks with overlap."""
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    if overlap < 0:
        raise ValueError("overlap cannot be negative")
    if overlap >= chunk_size:
        raise ValueError("overlap must be smaller than chunk_size")

    words = text.split()
    if not words:
        return []

    step = max(1, chunk_size - overlap)
    chunks: List[TextChunk] = []
    start = 0
    chunk_id = 0
    total = len(words)

    while start < total:
        end = min(total, start + chunk_size)
        chunk_words = words[start:end]
        chunk_text_value = " ".join(chunk_words)
        chunks.append(TextChunk(chunk_id=chunk_id, text=chunk_text_value, start_word=start, end_word=end))
        chunk_id += 1
        if end >= total:
            break
        start += step

    return chunks
