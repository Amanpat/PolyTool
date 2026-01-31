"""Embedding interfaces and SentenceTransformer implementation."""

from __future__ import annotations

from typing import Iterable, List

import numpy as np

DEFAULT_EMBED_MODEL = "BAAI/bge-large-en-v1.5"


class BaseEmbedder:
    """Simple embedder interface for text and query embedding."""

    model_name: str
    dimension: int

    def embed_texts(self, texts: Iterable[str]) -> np.ndarray:
        raise NotImplementedError

    def embed_query(self, text: str) -> np.ndarray:
        embeddings = self.embed_texts([text])
        if embeddings.size == 0:
            return np.zeros((self.dimension,), dtype="float32")
        return embeddings[0]


class SentenceTransformerEmbedder(BaseEmbedder):
    """Sentence-Transformers embedder for local RAG."""

    def __init__(
        self,
        model_name: str = DEFAULT_EMBED_MODEL,
        device: str = "auto",
        normalize: bool = True,
    ) -> None:
        try:
            import torch
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise RuntimeError(
                "sentence-transformers (and torch) are required. Install requirements-rag.txt."
            ) from exc

        self.model_name = model_name
        resolved_device = device
        if device == "auto":
            resolved_device = "cuda" if torch.cuda.is_available() else "cpu"
        self.device = resolved_device
        self.normalize = normalize
        self.model = SentenceTransformer(model_name, device=resolved_device)
        self.dimension = int(self.model.get_sentence_embedding_dimension())

    def embed_texts(self, texts: Iterable[str]) -> np.ndarray:
        text_list: List[str] = list(texts)
        if not text_list:
            return np.zeros((0, self.dimension), dtype="float32")
        embeddings = self.model.encode(
            text_list,
            convert_to_numpy=True,
            normalize_embeddings=self.normalize,
            show_progress_bar=False,
        )
        return embeddings.astype("float32")
