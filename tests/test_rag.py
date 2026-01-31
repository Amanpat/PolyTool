import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "packages"))

from polymarket.rag.chunker import chunk_text
from polymarket.rag.embedder import BaseEmbedder
from polymarket.rag.index import build_index
from polymarket.rag.manifest import write_manifest
from polymarket.rag.query import query_index


class _FakeEmbedder(BaseEmbedder):
    def __init__(self) -> None:
        self.model_name = "fake-embedder"
        self.dimension = 4

    def embed_texts(self, texts):
        vectors = []
        for text in texts:
            value = float(len(text))
            vectors.append([value, value / 2.0, value / 3.0, 1.0])
        return np.array(vectors, dtype="float32")


class RAGTests(unittest.TestCase):
    def test_chunking_is_deterministic(self) -> None:
        text = "alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu"
        chunks_a = chunk_text(text, chunk_size=4, overlap=1)
        chunks_b = chunk_text(text, chunk_size=4, overlap=1)
        self.assertEqual([chunk.text for chunk in chunks_a], [chunk.text for chunk in chunks_b])
        self.assertEqual([chunk.start_word for chunk in chunks_a], [chunk.start_word for chunk in chunks_b])

    def test_manifest_written(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            manifest_path = Path(tmpdir) / "manifest.json"
            repo_root = Path(os.path.dirname(__file__)).resolve().parents[1]
            manifest = write_manifest(
                manifest_path,
                embed_model="test-model",
                embed_dim=4,
                chunk_size=10,
                overlap=2,
                indexed_roots=["kb"],
                repo_root=repo_root,
            )
            self.assertTrue(manifest_path.exists())
            loaded = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(loaded["embed_model"], "test-model")
            self.assertEqual(manifest["chunk_size"], 10)

    def test_query_returns_stable_structure(self) -> None:
        repo_root = Path(os.path.dirname(__file__)).resolve().parents[1]
        kb_root = repo_root / "kb" / "tmp_tests"
        kb_root.mkdir(parents=True, exist_ok=True)

        with tempfile.TemporaryDirectory(dir=kb_root) as tmpdir:
            root_path = Path(tmpdir)
            sample_file = root_path / "notes.txt"
            sample_file.write_text("alpha beta gamma delta epsilon", encoding="utf-8")

            index_dir = repo_root / "kb" / "rag" / "index" / f"test_{root_path.name}"
            manifest_path = root_path / "manifest.json"
            embedder = _FakeEmbedder()

            build_index(
                roots=[root_path.as_posix()],
                embedder=embedder,
                chunk_size=3,
                overlap=1,
                persist_directory=index_dir,
                collection_name=f"test_{root_path.name}",
                rebuild=True,
                manifest_path=manifest_path,
            )

            results = query_index(
                question="alpha",
                embedder=embedder,
                k=2,
                persist_directory=index_dir,
                collection_name=f"test_{root_path.name}",
            )

            self.assertTrue(results)
            for result in results:
                self.assertIn("file_path", result)
                self.assertIn("chunk_id", result)
                self.assertIn("score", result)
                self.assertIn("snippet", result)
                self.assertIn("metadata", result)


if __name__ == "__main__":
    unittest.main()
