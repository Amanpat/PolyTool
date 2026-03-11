import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "packages"))

from polymarket.rag.embedder import BaseEmbedder
from polymarket.rag.index import build_index, sanitize_collection_name


class _FakeEmbedder(BaseEmbedder):
    def __init__(self) -> None:
        self.model_name = "fake-embedder"
        self.dimension = 4

    def embed_texts(self, texts):
        rows = []
        for text in texts:
            value = float(len(text))
            rows.append([value, value / 2.0, value / 3.0, 1.0])
        return np.array(rows, dtype="float32")


class _FakeCollection:
    def __init__(self) -> None:
        self._rows: dict[str, dict] = {}

    def upsert(self, *, ids, documents, embeddings, metadatas):
        for i, chunk_id in enumerate(ids):
            self._rows[chunk_id] = {
                "document": documents[i],
                "embedding": embeddings[i],
                "metadata": metadatas[i],
            }

    def add(self, *, ids, documents, embeddings, metadatas):
        self.upsert(ids=ids, documents=documents, embeddings=embeddings, metadatas=metadatas)

    def delete(self, *, where=None):
        if where is None:
            self._rows.clear()
            return
        target_path = where.get("file_path")
        if target_path is None:
            return
        self._rows = {
            chunk_id: row
            for chunk_id, row in self._rows.items()
            if row.get("metadata", {}).get("file_path") != target_path
        }

    def get(self, include=None):
        return {"metadatas": [row["metadata"] for row in self._rows.values()]}


class _FakePersistentClient:
    def __init__(self, path: str) -> None:
        self._path = path
        self._collections: dict[str, _FakeCollection] = {}

    def delete_collection(self, name: str) -> None:
        self._collections.pop(name, None)

    def get_or_create_collection(self, *, name: str, metadata=None):
        _ = metadata
        if name not in self._collections:
            self._collections[name] = _FakeCollection()
        return self._collections[name]


def _fake_chromadb_module():
    return types.SimpleNamespace(PersistentClient=_FakePersistentClient)


class RagIndexProgressFilterTests(unittest.TestCase):
    def _run_index(
        self,
        *,
        files: dict[str, str | bytes],
        max_bytes: int = 4 * 1024 * 1024,
        progress_every_files: int = 100,
        progress_every_chunks: int = 100,
        progress_callback=None,
    ):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as raw:
            repo_root = Path(raw)
            for rel_path, payload in files.items():
                abs_path = repo_root / rel_path
                abs_path.parent.mkdir(parents=True, exist_ok=True)
                if isinstance(payload, bytes):
                    abs_path.write_bytes(payload)
                else:
                    abs_path.write_text(payload, encoding="utf-8")

            manifest_path = repo_root / "manifest.json"
            persist_dir = repo_root / "_index"
            collection_name = sanitize_collection_name(f"test_{repo_root.name}")

            with patch("polymarket.rag.index._resolve_repo_root", lambda: repo_root), patch.dict(
                sys.modules, {"chromadb": _fake_chromadb_module()}
            ):
                return build_index(
                    roots=[(repo_root / "kb").as_posix()],
                    embedder=_FakeEmbedder(),
                    chunk_size=8,
                    overlap=2,
                    persist_directory=persist_dir,
                    collection_name=collection_name,
                    rebuild=True,
                    manifest_path=manifest_path,
                    lexical_db_path=None,
                    max_bytes=max_bytes,
                    progress_every_files=progress_every_files,
                    progress_every_chunks=progress_every_chunks,
                    progress_callback=progress_callback,
                )

    def test_filter_skips_binary_extension(self) -> None:
        summary = self._run_index(
            files={
                "kb/users/alice/notes.md": "alpha beta gamma delta epsilon",
                "kb/users/alice/image.png": b"\x89PNG\r\n\x1a\nfake",
            }
        )
        self.assertEqual(summary.scanned_files, 2)
        self.assertEqual(summary.files_indexed, 1)
        self.assertEqual(summary.skipped_binary, 1)
        self.assertEqual(summary.skipped_too_big, 0)
        self.assertEqual(summary.skipped_decode, 0)

    def test_filter_skips_over_max_bytes(self) -> None:
        summary = self._run_index(
            files={"kb/users/alice/large.md": "x" * 128},
            max_bytes=32,
        )
        self.assertEqual(summary.scanned_files, 1)
        self.assertEqual(summary.files_indexed, 0)
        self.assertEqual(summary.skipped_too_big, 1)
        self.assertEqual(summary.skipped_binary, 0)
        self.assertEqual(summary.skipped_decode, 0)

    def test_decode_failure_increments_skipped_decode(self) -> None:
        summary = self._run_index(
            files={"kb/users/alice/bad.txt": b"\xff\xfe\xfa\xfd"},
            max_bytes=1024,
        )
        self.assertEqual(summary.scanned_files, 1)
        self.assertEqual(summary.files_indexed, 0)
        self.assertEqual(summary.skipped_decode, 1)
        self.assertEqual(summary.skipped_binary, 0)
        self.assertEqual(summary.skipped_too_big, 0)

    def test_progress_callback_invoked(self) -> None:
        events = []

        summary = self._run_index(
            files={
                "kb/users/alice/a.md": "alpha beta gamma delta epsilon zeta eta theta iota kappa",
                "kb/users/alice/b.md": "lambda mu nu xi omicron pi rho sigma tau upsilon",
            },
            progress_every_files=1,
            progress_every_chunks=0,
            progress_callback=events.append,
        )

        self.assertGreaterEqual(len(events), 2)
        self.assertTrue(any(not event.is_final for event in events))
        self.assertTrue(events[-1].is_final)
        self.assertEqual(events[-1].scanned_files, summary.scanned_files)
        self.assertEqual(events[-1].embedded_chunks, summary.chunks_indexed)
        self.assertTrue(events[-1].last_path.endswith(".md"))

    def test_rebuild_clears_persist_directory(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as raw:
            repo_root = Path(raw)
            source_file = repo_root / "kb" / "users" / "alice" / "notes.md"
            source_file.parent.mkdir(parents=True, exist_ok=True)
            source_file.write_text("alpha beta gamma delta", encoding="utf-8")

            persist_dir = repo_root / "_index"
            persist_dir.mkdir(parents=True, exist_ok=True)
            stale_file = persist_dir / "stale.lock"
            stale_file.write_text("stale-lock", encoding="utf-8")

            manifest_path = repo_root / "manifest.json"
            collection_name = sanitize_collection_name(f"test_{repo_root.name}")

            with patch("polymarket.rag.index._resolve_repo_root", lambda: repo_root), patch.dict(
                sys.modules, {"chromadb": _fake_chromadb_module()}
            ):
                build_index(
                    roots=[(repo_root / "kb").as_posix()],
                    embedder=_FakeEmbedder(),
                    chunk_size=8,
                    overlap=2,
                    persist_directory=persist_dir,
                    collection_name=collection_name,
                    rebuild=True,
                    manifest_path=manifest_path,
                    lexical_db_path=None,
                )

            self.assertFalse(stale_file.exists())


if __name__ == "__main__":
    unittest.main()
