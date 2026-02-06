import json
import os
import sqlite3
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "packages"))

from polymarket.rag.chunker import chunk_text
from polymarket.rag.embedder import BaseEmbedder
from polymarket.rag.index import DEFAULT_COLLECTION, build_index, reconcile_index, sanitize_collection_name
from polymarket.rag.manifest import write_manifest
from polymarket.rag.metadata import (
    build_chunk_metadata,
    canonicalize_rel_path,
    compute_chunk_id,
    compute_doc_id,
    derive_created_at,
    derive_doc_type,
    derive_is_private,
    derive_proxy_wallet,
    derive_user_slug,
)
from polymarket.rag.query import build_chroma_where, query_index


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


# ---------------------------------------------------------------------------
# Collection name sanitization tests
# ---------------------------------------------------------------------------


class CollectionNameSanitizerTests(unittest.TestCase):
    def test_trailing_underscore_trimmed(self) -> None:
        self.assertEqual(sanitize_collection_name("test_tmpl_f8p83_"), "test_tmpl_f8p83")

    def test_spaces_and_slashes_replaced(self) -> None:
        self.assertEqual(sanitize_collection_name("my collection/one"), "my_collection_one")

    def test_short_name_falls_back(self) -> None:
        self.assertEqual(sanitize_collection_name("a"), DEFAULT_COLLECTION)
        self.assertEqual(sanitize_collection_name(""), DEFAULT_COLLECTION)


# ---------------------------------------------------------------------------
# Original tests (unchanged)
# ---------------------------------------------------------------------------


class RAGTests(unittest.TestCase):
    def test_chunking_is_deterministic(self) -> None:
        text = "alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu"
        chunks_a = chunk_text(text, chunk_size=4, overlap=1)
        chunks_b = chunk_text(text, chunk_size=4, overlap=1)
        self.assertEqual([chunk.text for chunk in chunks_a], [chunk.text for chunk in chunks_b])
        self.assertEqual([chunk.start_word for chunk in chunks_a], [chunk.start_word for chunk in chunks_b])

    def test_manifest_written(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            manifest_path = Path(tmpdir) / "manifest.json"
            repo_root = Path.cwd()
            manifest = write_manifest(
                manifest_path,
                embed_model="test-model",
                embed_dim=4,
                chunk_size=10,
                overlap=2,
                indexed_roots=["kb"],
                repo_root=repo_root,
                collection_name="test_coll",
            )
            self.assertTrue(manifest_path.exists())
            loaded = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(loaded["embed_model"], "test-model")
            self.assertEqual(manifest["chunk_size"], 10)
            self.assertEqual(manifest["schema_version"], 3)
            self.assertIsInstance(manifest["id_scheme"], dict)
            self.assertEqual(manifest["id_scheme"]["hash"], "sha256")
            self.assertIn("doc_id", manifest["id_scheme"])
            self.assertIn("chunk_id", manifest["id_scheme"])
            self.assertEqual(manifest["collection_name"], "test_coll")

    def test_query_returns_stable_structure(self) -> None:
        repo_root = Path.cwd()
        kb_root = repo_root / "kb" / "tmp_tests"
        kb_root.mkdir(parents=True, exist_ok=True)

        with tempfile.TemporaryDirectory(dir=kb_root) as tmpdir:
            root_path = Path(tmpdir)
            sample_file = root_path / "notes.txt"
            sample_file.write_text("alpha beta gamma delta epsilon", encoding="utf-8")

            index_dir = repo_root / "kb" / "rag" / "index" / f"test_{root_path.name}"
            collection_name = sanitize_collection_name(f"test_{root_path.name}")
            manifest_path = root_path / "manifest.json"
            embedder = _FakeEmbedder()

            build_index(
                roots=[root_path.as_posix()],
                embedder=embedder,
                chunk_size=3,
                overlap=1,
                persist_directory=index_dir,
                collection_name=collection_name,
                rebuild=True,
                manifest_path=manifest_path,
            )

            results = query_index(
                question="alpha",
                embedder=embedder,
                k=2,
                persist_directory=index_dir,
                collection_name=collection_name,
                private_only=False,
            )

            self.assertTrue(results)
            for result in results:
                self.assertIn("file_path", result)
                self.assertIn("chunk_id", result)
                self.assertIn("chunk_index", result)
                self.assertIn("doc_id", result)
                self.assertIn("score", result)
                self.assertIn("snippet", result)
                self.assertIn("metadata", result)


# ---------------------------------------------------------------------------
# PACKET 2 – metadata derivation unit tests
# ---------------------------------------------------------------------------


class MetadataDerivationTests(unittest.TestCase):
    """Unit tests for individual metadata extraction functions."""

    def test_doc_type_user_kb(self) -> None:
        self.assertEqual(derive_doc_type("kb/users/alice/notes.md"), "user_kb")

    def test_doc_type_kb(self) -> None:
        self.assertEqual(derive_doc_type("kb/shared/config.yaml"), "kb")

    def test_doc_type_dossier(self) -> None:
        self.assertEqual(derive_doc_type("artifacts/dossiers/alice/report.md"), "dossier")

    def test_doc_type_artifact(self) -> None:
        self.assertEqual(derive_doc_type("artifacts/exports/data.csv"), "artifact")

    def test_doc_type_docs(self) -> None:
        self.assertEqual(derive_doc_type("docs/README.md"), "docs")

    def test_doc_type_archive(self) -> None:
        self.assertEqual(derive_doc_type("docs/archive/old_spec.md"), "archive")

    def test_user_slug_from_kb(self) -> None:
        self.assertEqual(derive_user_slug("kb/users/alice/notes.md"), "alice")

    def test_user_slug_from_dossier(self) -> None:
        self.assertEqual(derive_user_slug("artifacts/dossiers/bob/report.md"), "bob")

    def test_user_slug_from_dossier_users(self) -> None:
        self.assertEqual(derive_user_slug("artifacts/dossiers/users/carol/data.md"), "carol")

    def test_user_slug_none_for_shared(self) -> None:
        self.assertIsNone(derive_user_slug("kb/shared/config.yaml"))

    def test_user_slug_none_for_docs(self) -> None:
        self.assertIsNone(derive_user_slug("docs/README.md"))

    def test_is_private_kb(self) -> None:
        self.assertTrue(derive_is_private("kb/users/alice/notes.md"))

    def test_is_private_artifacts(self) -> None:
        self.assertTrue(derive_is_private("artifacts/dossiers/bob/report.md"))

    def test_is_private_docs(self) -> None:
        self.assertFalse(derive_is_private("docs/README.md"))

    def test_proxy_wallet_extracted(self) -> None:
        path = "artifacts/dossiers/alice/0xAbCdEf1234567890AbCdEf1234567890AbCdEf12/data.md"
        wallet = derive_proxy_wallet(path)
        self.assertEqual(wallet, "0xabcdef1234567890abcdef1234567890abcdef12")

    def test_proxy_wallet_none(self) -> None:
        self.assertIsNone(derive_proxy_wallet("kb/users/alice/notes.md"))

    def test_created_at_from_dossier_date(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            tmp_root = Path(tmpdir)
            rel_path = "artifacts/dossiers/users/alice/0xabc/2026-02-03/run1/memo.md"
            abs_path = tmp_root / Path(rel_path)
            abs_path.parent.mkdir(parents=True, exist_ok=True)
            abs_path.write_text("memo", encoding="utf-8")

            created_at = derive_created_at(rel_path, abs_path)

        self.assertEqual(created_at, "2026-02-03T00:00:00+00:00")

    def test_created_at_prefers_manifest_created_at(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            tmp_root = Path(tmpdir)
            rel_path = "artifacts/dossiers/users/alice/0xabc/2026-02-01/run2/manifest.json"
            abs_path = tmp_root / Path(rel_path)
            abs_path.parent.mkdir(parents=True, exist_ok=True)
            abs_path.write_text(
                json.dumps({"created_at_utc": "2026-02-03T12:34:56Z"}),
                encoding="utf-8",
            )

            created_at = derive_created_at(rel_path, abs_path)

        self.assertEqual(created_at, "2026-02-03T12:34:56+00:00")

    def test_created_at_ignores_out_of_range_path_dates(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            tmp_root = Path(tmpdir)
            rel_path = "artifacts/dossiers/users/alice/0xabc/9146-11-03/run1/memo.md"
            abs_path = tmp_root / Path(rel_path)
            abs_path.parent.mkdir(parents=True, exist_ok=True)
            abs_path.write_text("memo", encoding="utf-8")

            fallback_dt = datetime(2026, 2, 5, 1, 2, 3, tzinfo=timezone.utc)
            ts = fallback_dt.timestamp()
            os.utime(abs_path, (ts, ts))

            created_at = derive_created_at(rel_path, abs_path)

        self.assertEqual(created_at, "2026-02-05T01:02:03+00:00")

    def test_build_chunk_metadata_keys(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            tmp_file = Path(tmpdir) / "notes.md"
            tmp_file.write_text("test", encoding="utf-8")
            meta = build_chunk_metadata(
                rel_path="kb/users/alice/notes.md",
                abs_path=tmp_file,
                doc_id="abc123",
                chunk_index=0,
                start_word=0,
                end_word=10,
            )

        self.assertEqual(meta["file_path"], "kb/users/alice/notes.md")
        self.assertEqual(meta["doc_id"], "abc123")
        self.assertEqual(meta["chunk_index"], 0)
        self.assertEqual(meta["doc_type"], "user_kb")
        self.assertEqual(meta["user_slug"], "alice")
        self.assertTrue(meta["is_private"])
        self.assertIn("created_at", meta)
        self.assertNotIn("proxy_wallet", meta)


# ---------------------------------------------------------------------------
# PACKET 2 – build_chroma_where unit tests
# ---------------------------------------------------------------------------


class ChromaWhereTests(unittest.TestCase):
    """Unit tests for the filter-builder function."""

    def test_default_is_private_only(self) -> None:
        where = build_chroma_where()
        # Should have private_only and archive exclusion
        self.assertIsNotNone(where)
        self.assertIn("$and", where)
        conds = where["$and"]
        has_private = any(c.get("is_private") == {"$eq": True} for c in conds)
        self.assertTrue(has_private)

    def test_user_slug_filter(self) -> None:
        where = build_chroma_where(user_slug="alice", private_only=False)
        self.assertIsNotNone(where)
        # Should include user_slug condition
        if "$and" in where:
            conds = where["$and"]
        else:
            conds = [where]
        has_user = any(c.get("user_slug") == {"$eq": "alice"} for c in conds)
        self.assertTrue(has_user)

    def test_doc_type_single(self) -> None:
        where = build_chroma_where(doc_types=["dossier"], private_only=False, include_archive=True)
        self.assertIsNotNone(where)
        self.assertEqual(where, {"doc_type": {"$eq": "dossier"}})

    def test_doc_type_multiple(self) -> None:
        where = build_chroma_where(
            doc_types=["dossier", "user_kb"], private_only=False, include_archive=True
        )
        self.assertIsNotNone(where)
        if "$and" in where:
            conds = where["$and"]
        else:
            conds = [where]
        has_in = any(c.get("doc_type") == {"$in": ["dossier", "user_kb"]} for c in conds)
        self.assertTrue(has_in)

    def test_mutually_exclusive_raises(self) -> None:
        with self.assertRaises(ValueError):
            build_chroma_where(private_only=True, public_only=True)

    def test_archive_excluded_by_default(self) -> None:
        where = build_chroma_where(private_only=False)
        self.assertIsNotNone(where)
        # Single condition: archive excluded
        if "$and" in (where or {}):
            conds = where["$and"]
        else:
            conds = [where]
        has_ne = any(c.get("doc_type") == {"$ne": "archive"} for c in conds)
        self.assertTrue(has_ne)

    def test_archive_included(self) -> None:
        where = build_chroma_where(private_only=False, include_archive=True)
        # No conditions -> None
        self.assertIsNone(where)

    def test_date_range(self) -> None:
        where = build_chroma_where(
            date_from="2025-01-01", date_to="2025-12-31",
            private_only=False, include_archive=True,
        )
        self.assertIsNotNone(where)
        if "$and" in where:
            conds = where["$and"]
        else:
            conds = [where]
        has_gte = any("created_at" in c and "$gte" in c["created_at"] for c in conds)
        has_lte = any("created_at" in c and "$lte" in c["created_at"] for c in conds)
        self.assertTrue(has_gte)
        self.assertTrue(has_lte)


# ---------------------------------------------------------------------------
# PACKET 2 – integration tests (Chroma where-filter enforcement)
# ---------------------------------------------------------------------------


class _IndexHelper:
    """Sets up a temp Chroma index with synthetic multi-user data.

    Monkeypatches ``_resolve_repo_root`` so that the temp directory is treated
    as the repository root, allowing paths like ``kb/users/alice/`` to pass
    the ``ALLOWED_ROOTS`` check in ``index.py``.
    """

    def __init__(self) -> None:
        self.embedder = _FakeEmbedder()
        self._patches: list = []

    def build(self, tmpdir: Path):
        """Create synthetic files, index them, return (index_dir, collection_name).

        Callers must call ``cleanup()`` when done (or use as context manager
        via the test methods below).
        """
        kb_users_alice = tmpdir / "kb" / "users" / "alice"
        kb_users_bob = tmpdir / "kb" / "users" / "bob"
        artifacts_alice = tmpdir / "artifacts" / "dossiers" / "alice"
        kb_shared = tmpdir / "kb" / "shared"

        for d in (kb_users_alice, kb_users_bob, artifacts_alice, kb_shared):
            d.mkdir(parents=True, exist_ok=True)

        (kb_users_alice / "notes.md").write_text(
            "Alice private notes about market strategy alpha beta gamma",
            encoding="utf-8",
        )
        (kb_users_bob / "notes.md").write_text(
            "Bob private notes about risk analysis delta epsilon zeta",
            encoding="utf-8",
        )
        (artifacts_alice / "report.md").write_text(
            "Alice dossier report on trading patterns theta iota kappa",
            encoding="utf-8",
        )
        (kb_shared / "config.yaml").write_text(
            "shared_setting: true\nlambda mu nu xi omicron pi rho sigma",
            encoding="utf-8",
        )

        index_dir = tmpdir / "_chroma_index"
        manifest_path = tmpdir / "manifest.json"
        collection_name = sanitize_collection_name(f"test_{tmpdir.name}")

        # Monkeypatch repo root so ALLOWED_ROOTS validation passes.
        fake_root = lambda: tmpdir  # noqa: E731
        p1 = patch("polymarket.rag.index._resolve_repo_root", fake_root)
        p2 = patch("polymarket.rag.query._resolve_repo_root", fake_root)
        p1.start()
        p2.start()
        self._patches = [p1, p2]

        build_index(
            roots=[
                (tmpdir / "kb").as_posix(),
                (tmpdir / "artifacts").as_posix(),
            ],
            embedder=self.embedder,
            chunk_size=10,
            overlap=2,
            persist_directory=index_dir,
            collection_name=collection_name,
            rebuild=True,
            manifest_path=manifest_path,
        )

        return index_dir, collection_name

    def cleanup(self) -> None:
        for p in self._patches:
            p.stop()
        self._patches.clear()


class UserIsolationTests(unittest.TestCase):
    """Querying with --user X must not return chunks with user_slug != X."""

    def test_user_alice_isolation(self) -> None:
        helper = _IndexHelper()
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as raw:
            tmpdir = Path(raw)
            index_dir, coll = helper.build(tmpdir)
            try:
                results = query_index(
                    question="notes strategy",
                    embedder=helper.embedder,
                    k=20,
                    persist_directory=index_dir,
                    collection_name=coll,
                    user_slug="alice",
                    private_only=False,
                    include_archive=True,
                )

                self.assertTrue(results, "Expected at least one result for alice")
                for r in results:
                    slug = r["metadata"].get("user_slug")
                    self.assertEqual(
                        slug,
                        "alice",
                        f"User isolation violated: got user_slug={slug!r} in {r['file_path']}",
                    )
            finally:
                helper.cleanup()

    def test_user_bob_cannot_see_alice(self) -> None:
        helper = _IndexHelper()
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as raw:
            tmpdir = Path(raw)
            index_dir, coll = helper.build(tmpdir)
            try:
                results = query_index(
                    question="market strategy alpha",
                    embedder=helper.embedder,
                    k=20,
                    persist_directory=index_dir,
                    collection_name=coll,
                    user_slug="bob",
                    private_only=False,
                    include_archive=True,
                )

                for r in results:
                    slug = r["metadata"].get("user_slug")
                    self.assertNotEqual(
                        slug,
                        "alice",
                        f"User isolation violated: bob's query returned alice's doc {r['file_path']}",
                    )
            finally:
                helper.cleanup()


class PrivateOnlyScopeTests(unittest.TestCase):
    """Default query (private_only=True) must not return docs/ content."""

    def test_private_only_excludes_public(self) -> None:
        """Inject a public chunk directly into Chroma and verify it's excluded."""
        import chromadb

        helper = _IndexHelper()
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as raw:
            tmpdir = Path(raw)
            index_dir, coll = helper.build(tmpdir)
            try:
                # Manually insert a "docs/" chunk with is_private=False
                client = chromadb.PersistentClient(path=str(index_dir))
                collection = client.get_collection(coll)
                fake_embedding = helper.embedder.embed_texts(
                    ["public documentation about markets"]
                ).tolist()
                collection.upsert(
                    ids=["docs/README.md::chunk_0"],
                    documents=["public documentation about markets tau upsilon phi"],
                    embeddings=fake_embedding,
                    metadatas=[
                        {
                            "file_path": "docs/README.md",
                            "chunk_id": 0,
                            "start_word": 0,
                            "end_word": 6,
                            "root": "docs",
                            "doc_type": "docs",
                            "is_private": False,
                        }
                    ],
                )

                # Default query: private_only=True
                results = query_index(
                    question="documentation about markets",
                    embedder=helper.embedder,
                    k=20,
                    persist_directory=index_dir,
                    collection_name=coll,
                    # private_only=True is the default
                    include_archive=True,
                )

                for r in results:
                    self.assertTrue(
                        r["metadata"].get("is_private", True),
                        f"Private-only scope violated: got public doc {r['file_path']}",
                    )
            finally:
                helper.cleanup()

    def test_public_only_returns_only_public(self) -> None:
        """With public_only=True, only docs/ content should be returned."""
        import chromadb

        helper = _IndexHelper()
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as raw:
            tmpdir = Path(raw)
            index_dir, coll = helper.build(tmpdir)
            try:
                client = chromadb.PersistentClient(path=str(index_dir))
                collection = client.get_collection(coll)
                fake_embedding = helper.embedder.embed_texts(
                    ["public documentation about analytics"]
                ).tolist()
                collection.upsert(
                    ids=["docs/guide.md::chunk_0"],
                    documents=["public documentation about analytics chi psi omega"],
                    embeddings=fake_embedding,
                    metadatas=[
                        {
                            "file_path": "docs/guide.md",
                            "chunk_id": 0,
                            "start_word": 0,
                            "end_word": 6,
                            "root": "docs",
                            "doc_type": "docs",
                            "is_private": False,
                        }
                    ],
                )

                results = query_index(
                    question="analytics documentation",
                    embedder=helper.embedder,
                    k=20,
                    persist_directory=index_dir,
                    collection_name=coll,
                    private_only=False,
                    public_only=True,
                    include_archive=True,
                )

                for r in results:
                    self.assertFalse(
                        r["metadata"].get("is_private", False),
                        f"Public-only scope violated: got private doc {r['file_path']}",
                    )
            finally:
                helper.cleanup()


class DocTypeFilterTests(unittest.TestCase):
    """doc_type filter correctly restricts results."""

    def test_dossier_filter(self) -> None:
        helper = _IndexHelper()
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as raw:
            tmpdir = Path(raw)
            index_dir, coll = helper.build(tmpdir)
            try:
                results = query_index(
                    question="notes report data",
                    embedder=helper.embedder,
                    k=20,
                    persist_directory=index_dir,
                    collection_name=coll,
                    doc_types=["dossier"],
                    private_only=False,
                    include_archive=True,
                )

                self.assertTrue(results, "Expected at least one dossier result")
                for r in results:
                    self.assertEqual(
                        r["metadata"].get("doc_type"),
                        "dossier",
                        f"doc_type filter violated: got {r['metadata'].get('doc_type')} "
                        f"in {r['file_path']}",
                    )
            finally:
                helper.cleanup()

    def test_user_kb_filter(self) -> None:
        helper = _IndexHelper()
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as raw:
            tmpdir = Path(raw)
            index_dir, coll = helper.build(tmpdir)
            try:
                results = query_index(
                    question="notes strategy risk",
                    embedder=helper.embedder,
                    k=20,
                    persist_directory=index_dir,
                    collection_name=coll,
                    doc_types=["user_kb"],
                    private_only=False,
                    include_archive=True,
                )

                self.assertTrue(results, "Expected at least one user_kb result")
                for r in results:
                    self.assertEqual(
                        r["metadata"].get("doc_type"),
                        "user_kb",
                        f"doc_type filter violated: got {r['metadata'].get('doc_type')} "
                        f"in {r['file_path']}",
                    )
            finally:
                helper.cleanup()

    def test_multi_doc_type_filter(self) -> None:
        helper = _IndexHelper()
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as raw:
            tmpdir = Path(raw)
            index_dir, coll = helper.build(tmpdir)
            try:
                results = query_index(
                    question="notes strategy risk report",
                    embedder=helper.embedder,
                    k=20,
                    persist_directory=index_dir,
                    collection_name=coll,
                    doc_types=["user_kb", "dossier"],
                    private_only=False,
                    include_archive=True,
                )

                self.assertTrue(results)
                for r in results:
                    self.assertIn(
                        r["metadata"].get("doc_type"),
                        ("user_kb", "dossier"),
                        f"doc_type filter violated: got {r['metadata'].get('doc_type')} "
                        f"in {r['file_path']}",
                    )
            finally:
                helper.cleanup()


# ---------------------------------------------------------------------------
# PACKET 3 – deterministic ID + idempotence tests
# ---------------------------------------------------------------------------


class HashDeterminismTests(unittest.TestCase):
    """compute_doc_id and compute_chunk_id are deterministic and collision-safe."""

    def test_doc_id_deterministic(self) -> None:
        content = b"alpha beta gamma"
        self.assertEqual(
            compute_doc_id("kb/notes.md", content),
            compute_doc_id("kb/notes.md", content),
        )

    def test_doc_id_changes_on_edit(self) -> None:
        self.assertNotEqual(
            compute_doc_id("kb/notes.md", b"alpha beta gamma"),
            compute_doc_id("kb/notes.md", b"alpha beta CHANGED"),
        )

    def test_doc_id_differs_across_paths(self) -> None:
        """Two different rel_paths with identical file bytes produce different doc_id."""
        same_bytes = b"identical content in both files"
        id_a = compute_doc_id("kb/users/alice/notes.md", same_bytes)
        id_b = compute_doc_id("kb/users/bob/notes.md", same_bytes)
        self.assertNotEqual(id_a, id_b)

    def test_chunk_id_deterministic(self) -> None:
        doc_id = compute_doc_id("kb/users/alice/notes.md", b"file bytes")
        cid1 = compute_chunk_id(doc_id, 0, "hello world")
        cid2 = compute_chunk_id(doc_id, 0, "hello world")
        self.assertEqual(cid1, cid2)

    def test_chunk_id_differs_across_files(self) -> None:
        """Same text in different files must produce different chunk IDs."""
        doc_a = compute_doc_id("kb/users/alice/notes.md", b"alice file")
        doc_b = compute_doc_id("kb/users/bob/notes.md", b"bob file")
        cid_a = compute_chunk_id(doc_a, 0, "hello world")
        cid_b = compute_chunk_id(doc_b, 0, "hello world")
        self.assertNotEqual(cid_a, cid_b)

    def test_chunk_id_differs_by_index(self) -> None:
        """Same chunk_text at different chunk_index produces different chunk_id."""
        doc_id = compute_doc_id("kb/notes.md", b"some file content")
        cid_0 = compute_chunk_id(doc_id, 0, "repeated text")
        cid_1 = compute_chunk_id(doc_id, 1, "repeated text")
        self.assertNotEqual(cid_0, cid_1)

    def test_chunk_id_is_64_hex_chars(self) -> None:
        doc_id = compute_doc_id("path.md", b"bytes")
        cid = compute_chunk_id(doc_id, 0, "text")
        self.assertEqual(len(cid), 64)
        int(cid, 16)  # must be valid hex

    def test_rel_path_canonicalization(self) -> None:
        """Backslash and forward-slash paths produce the same IDs."""
        content = b"same file bytes"
        id_posix = compute_doc_id("kb/users/alice/notes.md", content)
        id_win = compute_doc_id("kb\\users\\alice\\notes.md", content)
        self.assertEqual(id_posix, id_win)

    def test_canonicalize_rel_path(self) -> None:
        self.assertEqual(canonicalize_rel_path("kb\\users\\alice\\notes.md"), "kb/users/alice/notes.md")
        self.assertEqual(canonicalize_rel_path("kb/users/alice/notes.md"), "kb/users/alice/notes.md")


class IdempotentIndexTests(unittest.TestCase):
    """Re-indexing the same content must not create duplicates."""

    def test_double_index_same_count(self) -> None:
        import chromadb

        helper = _IndexHelper()
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as raw:
            tmpdir = Path(raw)
            index_dir, coll = helper.build(tmpdir)
            try:
                client = chromadb.PersistentClient(path=str(index_dir))
                count_after_first = client.get_collection(coll).count()

                # Index again (incremental — no rebuild)
                build_index(
                    roots=[
                        (tmpdir / "kb").as_posix(),
                        (tmpdir / "artifacts").as_posix(),
                    ],
                    embedder=helper.embedder,
                    chunk_size=10,
                    overlap=2,
                    persist_directory=index_dir,
                    collection_name=coll,
                    rebuild=False,
                )

                count_after_second = client.get_collection(coll).count()
                self.assertEqual(
                    count_after_first,
                    count_after_second,
                    f"Duplicate chunks created: {count_after_first} -> {count_after_second}",
                )
            finally:
                helper.cleanup()

    def test_rebuild_same_count(self) -> None:
        """--rebuild drops and recreates; count must match first run."""
        import chromadb

        helper = _IndexHelper()
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as raw:
            tmpdir = Path(raw)
            index_dir, coll = helper.build(tmpdir)  # first run (rebuild=True inside build)
            try:
                client = chromadb.PersistentClient(path=str(index_dir))
                count_first = client.get_collection(coll).count()

                # Rebuild again
                build_index(
                    roots=[
                        (tmpdir / "kb").as_posix(),
                        (tmpdir / "artifacts").as_posix(),
                    ],
                    embedder=helper.embedder,
                    chunk_size=10,
                    overlap=2,
                    persist_directory=index_dir,
                    collection_name=coll,
                    rebuild=True,
                )

                count_rebuild = client.get_collection(coll).count()
                self.assertEqual(count_first, count_rebuild)
            finally:
                helper.cleanup()


class ReplacementOnChangeTests(unittest.TestCase):
    """Changing file content replaces old chunks without leaving orphans."""

    def test_edit_file_replaces_chunks(self) -> None:
        import chromadb

        helper = _IndexHelper()
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as raw:
            tmpdir = Path(raw)
            index_dir, coll = helper.build(tmpdir)
            try:
                client = chromadb.PersistentClient(path=str(index_dir))
                count_before = client.get_collection(coll).count()

                # Modify alice's notes (same word count to keep chunk count stable)
                alice_notes = tmpdir / "kb" / "users" / "alice" / "notes.md"
                alice_notes.write_text(
                    "Alice UPDATED notes about market strategy alpha beta gamma",
                    encoding="utf-8",
                )

                # Re-index incrementally
                build_index(
                    roots=[
                        (tmpdir / "kb").as_posix(),
                        (tmpdir / "artifacts").as_posix(),
                    ],
                    embedder=helper.embedder,
                    chunk_size=10,
                    overlap=2,
                    persist_directory=index_dir,
                    collection_name=coll,
                    rebuild=False,
                )

                count_after = client.get_collection(coll).count()
                self.assertEqual(
                    count_before,
                    count_after,
                    f"Chunk count changed after edit: {count_before} -> {count_after}",
                )

                # Verify the updated content is in the index
                results = query_index(
                    question="UPDATED notes",
                    embedder=helper.embedder,
                    k=5,
                    persist_directory=index_dir,
                    collection_name=coll,
                    private_only=False,
                    include_archive=True,
                )
                found_updated = any("UPDATED" in r["snippet"] for r in results)
                self.assertTrue(found_updated, "Updated content not found in index")
            finally:
                helper.cleanup()

    def test_shrink_file_removes_orphans(self) -> None:
        """If a file shrinks (fewer chunks), old trailing chunks are removed."""
        import chromadb

        helper = _IndexHelper()
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as raw:
            tmpdir = Path(raw)

            # Create a file with LOTS of words so it produces multiple chunks
            alice_notes = tmpdir / "kb" / "users" / "alice"
            alice_notes.mkdir(parents=True, exist_ok=True)
            (alice_notes / "notes.md").write_text(
                " ".join(f"word{i}" for i in range(50)),
                encoding="utf-8",
            )

            # Also need minimal structure for _IndexHelper
            (tmpdir / "kb" / "users" / "bob").mkdir(parents=True, exist_ok=True)
            (tmpdir / "kb" / "users" / "bob" / "notes.md").write_text("bob", encoding="utf-8")
            (tmpdir / "artifacts" / "dossiers" / "alice").mkdir(parents=True, exist_ok=True)
            (tmpdir / "artifacts" / "dossiers" / "alice" / "report.md").write_text(
                "report", encoding="utf-8"
            )
            (tmpdir / "kb" / "shared").mkdir(parents=True, exist_ok=True)
            (tmpdir / "kb" / "shared" / "config.yaml").write_text("cfg", encoding="utf-8")

            index_dir = tmpdir / "_chroma_index"
            manifest_path = tmpdir / "manifest.json"
            collection_name = sanitize_collection_name(f"test_{tmpdir.name}")

            fake_root = lambda: tmpdir  # noqa: E731
            p1 = patch("polymarket.rag.index._resolve_repo_root", fake_root)
            p2 = patch("polymarket.rag.query._resolve_repo_root", fake_root)
            p1.start()
            p2.start()

            try:
                build_index(
                    roots=[(tmpdir / "kb").as_posix(), (tmpdir / "artifacts").as_posix()],
                    embedder=helper.embedder,
                    chunk_size=10,
                    overlap=2,
                    persist_directory=index_dir,
                    collection_name=collection_name,
                    rebuild=True,
                    manifest_path=manifest_path,
                )

                client = chromadb.PersistentClient(path=str(index_dir))
                count_big = client.get_collection(collection_name).count()

                # Shrink alice's file to very few words
                (alice_notes / "notes.md").write_text("tiny", encoding="utf-8")

                build_index(
                    roots=[(tmpdir / "kb").as_posix(), (tmpdir / "artifacts").as_posix()],
                    embedder=helper.embedder,
                    chunk_size=10,
                    overlap=2,
                    persist_directory=index_dir,
                    collection_name=collection_name,
                    rebuild=False,
                    manifest_path=manifest_path,
                )

                count_small = client.get_collection(collection_name).count()
                self.assertLess(
                    count_small,
                    count_big,
                    "Orphan chunks were not cleaned up after file shrinkage",
                )
            finally:
                p1.stop()
                p2.stop()

    def test_doc_id_in_metadata(self) -> None:
        """Indexed chunks carry a doc_id metadata field."""
        import chromadb

        helper = _IndexHelper()
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as raw:
            tmpdir = Path(raw)
            index_dir, coll = helper.build(tmpdir)
            try:
                client = chromadb.PersistentClient(path=str(index_dir))
                collection = client.get_collection(coll)
                sample = collection.peek(limit=1)
                meta = sample["metadatas"][0]
                self.assertIn("doc_id", meta)
                self.assertEqual(len(meta["doc_id"]), 64)  # sha256 hex
                self.assertIn("chunk_index", meta)
            finally:
                helper.cleanup()


# ---------------------------------------------------------------------------
# PACKET 4 – Hybrid retrieval tests
# ---------------------------------------------------------------------------


from polymarket.rag.lexical import (
    clear_all as lexical_clear_all,
    delete_file_chunks as lexical_delete_file,
    insert_chunks as lexical_insert,
    lexical_search,
    list_indexed_file_paths,
    open_lexical_db,
    reciprocal_rank_fusion,
    FTS5_REQUIRED_MESSAGE,
    RRF_K,
)


class RRFFusionTests(unittest.TestCase):
    """Reciprocal Rank Fusion produces deterministic, stable ordering."""

    def _make_result(self, chunk_id: str, score=None) -> dict:
        return {
            "file_path": f"f/{chunk_id}.md",
            "chunk_id": chunk_id,
            "chunk_index": 0,
            "doc_id": f"d_{chunk_id}",
            "score": score,
            "snippet": chunk_id,
            "metadata": {},
        }

    def test_rrf_deterministic_ordering(self) -> None:
        """Given fixed ranked lists, RRF produces the expected order."""
        vector = [self._make_result("a", 0.9), self._make_result("b", 0.8), self._make_result("c", 0.7)]
        lexical = [self._make_result("b"), self._make_result("d"), self._make_result("a")]

        fused = reciprocal_rank_fusion(vector, lexical, rrf_k=60)

        # b: vector rank 2 + lexical rank 1 → 1/62 + 1/61 ≈ 0.03252
        # a: vector rank 1 + lexical rank 3 → 1/61 + 1/63 ≈ 0.03226
        # d: lexical rank 2 only → 1/62 ≈ 0.01613
        # c: vector rank 3 only → 1/63 ≈ 0.01587
        ids = [r["chunk_id"] for r in fused]
        self.assertEqual(ids, ["b", "a", "d", "c"])

        # Explainable fields on the top result
        self.assertEqual(fused[0]["vector_rank"], 2)
        self.assertEqual(fused[0]["lexical_rank"], 1)
        self.assertEqual(fused[0]["final_rank"], 1)
        self.assertIsNotNone(fused[0]["fused_score"])

        # Vector-only result has no lexical rank
        c_entry = next(r for r in fused if r["chunk_id"] == "c")
        self.assertEqual(c_entry["vector_rank"], 3)
        self.assertIsNone(c_entry["lexical_rank"])

        # Lexical-only result has no vector rank
        d_entry = next(r for r in fused if r["chunk_id"] == "d")
        self.assertIsNone(d_entry["vector_rank"])
        self.assertEqual(d_entry["lexical_rank"], 2)

    def test_rrf_stable_on_rerun(self) -> None:
        """Running RRF twice with the same input produces identical output."""
        vector = [self._make_result("x", 0.5), self._make_result("y", 0.4)]
        lexical = [self._make_result("y"), self._make_result("z")]
        run1 = reciprocal_rank_fusion(vector, lexical)
        run2 = reciprocal_rank_fusion(vector, lexical)
        self.assertEqual(
            [r["chunk_id"] for r in run1],
            [r["chunk_id"] for r in run2],
        )
        self.assertEqual(
            [r["fused_score"] for r in run1],
            [r["fused_score"] for r in run2],
        )

    def test_rrf_empty_inputs(self) -> None:
        """RRF handles empty lists gracefully."""
        self.assertEqual(reciprocal_rank_fusion([], []), [])
        vector = [self._make_result("a")]
        self.assertEqual(len(reciprocal_rank_fusion(vector, [])), 1)
        self.assertEqual(len(reciprocal_rank_fusion([], vector)), 1)


class LexicalFilterTests(unittest.TestCase):
    """Lexical retrieval enforces the same filters as the vector path."""

    def _build_lexical_db(self, tmpdir: Path) -> sqlite3.Connection:
        """Insert synthetic multi-user chunks into a temp lexical DB."""
        import sqlite3  # noqa: F811

        lex_db = tmpdir / "lex" / "lexical.sqlite3"
        conn = open_lexical_db(lex_db)
        lexical_insert(conn, [
            {
                "chunk_id": "alice_1",
                "doc_id": "d_alice",
                "file_path": "kb/users/alice/notes.md",
                "chunk_index": 0,
                "doc_type": "user_kb",
                "user_slug": "alice",
                "is_private": True,
                "chunk_text": "Alice private notes about market strategy blockchain",
            },
            {
                "chunk_id": "bob_1",
                "doc_id": "d_bob",
                "file_path": "kb/users/bob/notes.md",
                "chunk_index": 0,
                "doc_type": "user_kb",
                "user_slug": "bob",
                "is_private": True,
                "chunk_text": "Bob private notes about risk analysis blockchain",
            },
            {
                "chunk_id": "public_1",
                "doc_id": "d_public",
                "file_path": "docs/README.md",
                "chunk_index": 0,
                "doc_type": "docs",
                "is_private": False,
                "chunk_text": "Public documentation about blockchain technology overview",
            },
            {
                "chunk_id": "archive_1",
                "doc_id": "d_archive",
                "file_path": "docs/archive/old.md",
                "chunk_index": 0,
                "doc_type": "archive",
                "is_private": False,
                "chunk_text": "Archived old documentation about blockchain history",
            },
        ])
        conn.commit()
        return conn

    def test_lexical_user_isolation(self) -> None:
        """Searching with user_slug only returns that user's chunks."""
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as raw:
            conn = self._build_lexical_db(Path(raw))
            try:
                results = lexical_search(
                    conn, "blockchain",
                    k=10, user_slug="alice", private_only=False, include_archive=True,
                )
                self.assertTrue(results, "Expected at least one result for alice")
                for r in results:
                    self.assertEqual(
                        r["metadata"].get("user_slug"), "alice",
                        f"User isolation violated: got {r['metadata'].get('user_slug')}",
                    )
            finally:
                conn.close()

    def test_lexical_private_only(self) -> None:
        """Default private_only=True excludes public and archive chunks."""
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as raw:
            conn = self._build_lexical_db(Path(raw))
            try:
                results = lexical_search(conn, "blockchain", k=10)
                self.assertTrue(results)
                for r in results:
                    self.assertTrue(
                        r["metadata"].get("is_private", False),
                        f"Private-only violated: got public doc {r['file_path']}",
                    )
            finally:
                conn.close()

    def test_lexical_public_only(self) -> None:
        """public_only=True returns only public chunks."""
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as raw:
            conn = self._build_lexical_db(Path(raw))
            try:
                results = lexical_search(
                    conn, "blockchain", k=10,
                    private_only=False, public_only=True, include_archive=True,
                )
                self.assertTrue(results)
                for r in results:
                    self.assertFalse(
                        r["metadata"].get("is_private", True),
                        f"Public-only violated: got private doc {r['file_path']}",
                    )
            finally:
                conn.close()

    def test_lexical_archive_excluded_by_default(self) -> None:
        """Archive docs excluded unless include_archive=True."""
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as raw:
            conn = self._build_lexical_db(Path(raw))
            try:
                results = lexical_search(
                    conn, "blockchain", k=10, private_only=False,
                )
                for r in results:
                    self.assertNotEqual(
                        r["metadata"].get("doc_type"), "archive",
                        f"Archive not excluded: got {r['file_path']}",
                    )
            finally:
                conn.close()

    def test_lexical_doc_type_filter(self) -> None:
        """doc_types filter restricts results to matching types."""
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as raw:
            conn = self._build_lexical_db(Path(raw))
            try:
                results = lexical_search(
                    conn, "blockchain", k=10,
                    doc_types=["docs"], private_only=False, include_archive=True,
                )
                self.assertTrue(results)
                for r in results:
                    self.assertEqual(r["metadata"].get("doc_type"), "docs")
            finally:
                conn.close()


class FTS5AvailabilityTests(unittest.TestCase):
    """Lexical/hybrid queries fail loudly when FTS5 is unavailable."""

    def test_lexical_only_requires_fts5(self) -> None:
        with patch("polymarket.rag.lexical._probe_fts5", return_value=False):
            with self.assertRaises(RuntimeError) as ctx:
                query_index(
                    question="alpha",
                    lexical_only=True,
                    k=5,
                )
            self.assertEqual(str(ctx.exception), FTS5_REQUIRED_MESSAGE)

    def test_hybrid_requires_fts5(self) -> None:
        with patch("polymarket.rag.lexical._probe_fts5", return_value=False):
            with self.assertRaises(RuntimeError) as ctx:
                query_index(
                    question="alpha",
                    hybrid=True,
                    embedder=_FakeEmbedder(),
                    k=5,
                )
            self.assertEqual(str(ctx.exception), FTS5_REQUIRED_MESSAGE)

    def test_vector_only_unaffected(self) -> None:
        stub_result = [{
            "file_path": "kb/users/alice/notes.md",
            "chunk_id": "stub",
            "chunk_index": 0,
            "doc_id": "d_stub",
            "score": 0.9,
            "snippet": "alpha beta gamma",
            "metadata": {},
        }]
        with patch("polymarket.rag.lexical._probe_fts5", return_value=False):
            with patch("polymarket.rag.query._run_vector_query", return_value=stub_result):
                results = query_index(
                    question="alpha",
                    embedder=_FakeEmbedder(),
                    k=1,
                )
        self.assertEqual(results, stub_result)


class HybridIntegrationTests(unittest.TestCase):
    """End-to-end integration tests for hybrid retrieval."""

    def test_lexical_finds_keyword(self) -> None:
        """A unique keyword is found by lexical retrieval."""
        helper = _IndexHelper()
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as raw:
            tmpdir = Path(raw)
            # Add a file with a unique keyword
            kb_users_carol = tmpdir / "kb" / "users" / "carol"
            kb_users_carol.mkdir(parents=True, exist_ok=True)
            (kb_users_carol / "notes.md").write_text(
                "Carol notes about xylophone instrument practice schedule weekly",
                encoding="utf-8",
            )
            index_dir, coll = helper.build(tmpdir)
            try:
                results = query_index(
                    question="xylophone",
                    lexical_only=True,
                    k=5,
                    private_only=False,
                    include_archive=True,
                )
                self.assertTrue(results, "Lexical should find the unique keyword")
                found = any("xylophone" in r["snippet"].lower() for r in results)
                self.assertTrue(found, "xylophone not found in lexical results")
            finally:
                helper.cleanup()

    def test_hybrid_fuses_stubbed_vector_with_lexical(self) -> None:
        """Hybrid mode fuses stubbed vector results with real lexical search."""
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as raw:
            tmpdir = Path(raw)
            lex_db = tmpdir / "kb" / "rag" / "lexical" / "lexical.sqlite3"
            conn = open_lexical_db(lex_db)
            lexical_insert(conn, [
                {
                    "chunk_id": "shared_1",
                    "doc_id": "d_shared",
                    "file_path": "kb/users/alice/notes.md",
                    "chunk_index": 0,
                    "doc_type": "user_kb",
                    "user_slug": "alice",
                    "is_private": True,
                    "chunk_text": "alpha beta gamma",
                },
                {
                    "chunk_id": "lex_only",
                    "doc_id": "d_lex",
                    "file_path": "kb/users/bob/notes.md",
                    "chunk_index": 0,
                    "doc_type": "user_kb",
                    "user_slug": "bob",
                    "is_private": True,
                    "chunk_text": "alpha delta epsilon",
                },
            ])
            conn.commit()
            conn.close()

            conn = open_lexical_db(lex_db)
            lexical_results = lexical_search(conn, "alpha", k=10)
            conn.close()
            self.assertTrue(lexical_results, "Expected lexical results for 'alpha'")

            vector_results = [
                {
                    "file_path": "kb/users/alice/notes.md",
                    "chunk_id": "shared_1",
                    "chunk_index": 0,
                    "doc_id": "d_shared",
                    "score": 0.9,
                    "snippet": "alpha beta gamma",
                    "metadata": {
                        "file_path": "kb/users/alice/notes.md",
                        "doc_id": "d_shared",
                        "chunk_index": 0,
                        "doc_type": "user_kb",
                        "user_slug": "alice",
                        "is_private": True,
                    },
                },
                {
                    "file_path": "kb/users/carol/notes.md",
                    "chunk_id": "vec_only",
                    "chunk_index": 0,
                    "doc_id": "d_vec",
                    "score": 0.7,
                    "snippet": "alpha zeta eta",
                    "metadata": {
                        "file_path": "kb/users/carol/notes.md",
                        "doc_id": "d_vec",
                        "chunk_index": 0,
                        "doc_type": "user_kb",
                        "user_slug": "carol",
                        "is_private": True,
                    },
                },
            ]

            with patch("polymarket.rag.query._run_vector_query", return_value=vector_results):
                results = query_index(
                    question="alpha",
                    embedder=_FakeEmbedder(),
                    k=10,
                    hybrid=True,
                    lexical_db_path=lex_db,
                )

            expected = reciprocal_rank_fusion(vector_results, lexical_results)[:10]
            self.assertEqual(
                [r["chunk_id"] for r in results],
                [r["chunk_id"] for r in expected],
            )

            ids = {r["chunk_id"] for r in results}
            self.assertTrue({"shared_1", "lex_only", "vec_only"}.issubset(ids))
            for r in results:
                self.assertIn("fused_score", r)
                self.assertIn("final_rank", r)
                self.assertIn("vector_rank", r)
                self.assertIn("lexical_rank", r)

    def test_lexical_only_no_embedder_needed(self) -> None:
        """lexical_only=True works without an embedder."""
        helper = _IndexHelper()
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as raw:
            tmpdir = Path(raw)
            index_dir, coll = helper.build(tmpdir)
            try:
                # embedder=None should not raise for lexical_only
                results = query_index(
                    question="notes",
                    embedder=None,
                    lexical_only=True,
                    k=5,
                    private_only=False,
                    include_archive=True,
                )
                # Should not raise; results may or may not be empty
                self.assertIsInstance(results, list)
            finally:
                helper.cleanup()

    def test_hybrid_and_lexical_only_mutually_exclusive(self) -> None:
        """Passing both hybrid=True and lexical_only=True raises ValueError."""
        with self.assertRaises(ValueError):
            query_index(
                question="test",
                hybrid=True,
                lexical_only=True,
            )


class LexicalIdempotenceTests(unittest.TestCase):
    """Re-indexing the same content does not create duplicates in lexical DB."""

    def test_double_index_same_count(self) -> None:
        import sqlite3

        helper = _IndexHelper()
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as raw:
            tmpdir = Path(raw)
            index_dir, coll = helper.build(tmpdir)
            try:
                lex_db = tmpdir / "kb" / "rag" / "lexical" / "lexical.sqlite3"
                conn = open_lexical_db(lex_db)
                count_first = conn.execute("SELECT count(*) FROM chunks").fetchone()[0]
                conn.close()

                # Index again (incremental)
                build_index(
                    roots=[
                        (tmpdir / "kb").as_posix(),
                        (tmpdir / "artifacts").as_posix(),
                    ],
                    embedder=helper.embedder,
                    chunk_size=10,
                    overlap=2,
                    persist_directory=index_dir,
                    collection_name=coll,
                    rebuild=False,
                )

                conn = open_lexical_db(lex_db)
                count_second = conn.execute("SELECT count(*) FROM chunks").fetchone()[0]
                conn.close()

                self.assertEqual(
                    count_first, count_second,
                    f"Lexical duplicates: {count_first} -> {count_second}",
                )
            finally:
                helper.cleanup()


# ---------------------------------------------------------------------------
# PACKET 4.2 – Index reconcile mode tests
# ---------------------------------------------------------------------------


class ReconcileTests(unittest.TestCase):
    """Reconcile removes stale entries from both Chroma and lexical DB."""

    def test_reconcile_removes_deleted_file(self) -> None:
        """Index two files, delete one from disk, reconcile, verify removal."""
        import chromadb

        helper = _IndexHelper()
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as raw:
            tmpdir = Path(raw)

            # Create two user files
            alice_dir = tmpdir / "kb" / "users" / "alice"
            bob_dir = tmpdir / "kb" / "users" / "bob"
            artifacts_dir = tmpdir / "artifacts" / "dossiers" / "alice"
            shared_dir = tmpdir / "kb" / "shared"

            for d in (alice_dir, bob_dir, artifacts_dir, shared_dir):
                d.mkdir(parents=True, exist_ok=True)

            (alice_dir / "notes.md").write_text(
                "Alice notes about alpha beta gamma delta epsilon zeta",
                encoding="utf-8",
            )
            (bob_dir / "notes.md").write_text(
                "Bob notes about theta iota kappa lambda mu nu",
                encoding="utf-8",
            )
            (artifacts_dir / "report.md").write_text(
                "Alice dossier report omicron pi rho sigma tau",
                encoding="utf-8",
            )
            (shared_dir / "config.yaml").write_text(
                "shared_config: true\nupsilon phi chi psi omega",
                encoding="utf-8",
            )

            index_dir = tmpdir / "_chroma_index"
            manifest_path = tmpdir / "manifest.json"
            lex_db_path = tmpdir / "lex" / "lexical.sqlite3"
            collection_name = sanitize_collection_name(f"test_{tmpdir.name}")

            fake_root = lambda: tmpdir  # noqa: E731
            p1 = patch("polymarket.rag.index._resolve_repo_root", fake_root)
            p1.start()

            try:
                build_index(
                    roots=[
                        (tmpdir / "kb").as_posix(),
                        (tmpdir / "artifacts").as_posix(),
                    ],
                    embedder=helper.embedder,
                    chunk_size=10,
                    overlap=2,
                    persist_directory=index_dir,
                    collection_name=collection_name,
                    rebuild=True,
                    manifest_path=manifest_path,
                    lexical_db_path=lex_db_path,
                )

                # Verify both files are indexed in both stores
                client = chromadb.PersistentClient(path=str(index_dir))
                collection = client.get_collection(collection_name)
                chroma_count_before = collection.count()
                self.assertGreater(chroma_count_before, 0)

                conn = open_lexical_db(lex_db_path)
                lex_paths_before = list_indexed_file_paths(conn)
                conn.close()
                self.assertIn("kb/users/alice/notes.md", lex_paths_before)
                self.assertIn("kb/users/bob/notes.md", lex_paths_before)

                # --- Delete bob's file from disk ---
                (bob_dir / "notes.md").unlink()

                # --- Run reconcile ---
                summary = reconcile_index(
                    roots=[
                        (tmpdir / "kb").as_posix(),
                        (tmpdir / "artifacts").as_posix(),
                    ],
                    persist_directory=index_dir,
                    collection_name=collection_name,
                    lexical_db_path=lex_db_path,
                )

                # Verify summary
                self.assertEqual(summary.stale_files, 1)
                self.assertEqual(summary.lexical_deleted, 1)

                # Verify lexical DB no longer has bob's chunks
                conn = open_lexical_db(lex_db_path)
                lex_paths_after = list_indexed_file_paths(conn)
                bob_count = conn.execute(
                    "SELECT count(*) FROM chunks WHERE file_path = ?",
                    ("kb/users/bob/notes.md",),
                ).fetchone()[0]
                conn.close()
                self.assertNotIn("kb/users/bob/notes.md", lex_paths_after)
                self.assertEqual(bob_count, 0)

                # Verify alice is still in lexical
                self.assertIn("kb/users/alice/notes.md", lex_paths_after)

                # Verify Chroma no longer has bob's chunks
                chroma_bob = collection.get(
                    where={"file_path": "kb/users/bob/notes.md"},
                    include=["metadatas"],
                )
                self.assertEqual(
                    len(chroma_bob["ids"]), 0,
                    "Bob's chunks should be removed from Chroma after reconcile",
                )

                # Verify alice is still in Chroma
                chroma_alice = collection.get(
                    where={"file_path": "kb/users/alice/notes.md"},
                    include=["metadatas"],
                )
                self.assertGreater(len(chroma_alice["ids"]), 0)

                # vector_deleted should be 1 (bob)
                self.assertEqual(summary.vector_deleted, 1)
                self.assertEqual(summary.warnings, [])

            finally:
                p1.stop()

    def test_reconcile_noop_when_nothing_stale(self) -> None:
        """When all indexed files still exist, reconcile deletes nothing."""
        helper = _IndexHelper()
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as raw:
            tmpdir = Path(raw)
            index_dir, coll = helper.build(tmpdir)
            lex_db_path = tmpdir / "kb" / "rag" / "lexical" / "lexical.sqlite3"

            try:
                summary = reconcile_index(
                    roots=[
                        (tmpdir / "kb").as_posix(),
                        (tmpdir / "artifacts").as_posix(),
                    ],
                    persist_directory=index_dir,
                    collection_name=coll,
                    lexical_db_path=lex_db_path,
                )

                self.assertEqual(summary.stale_files, 0)
                self.assertEqual(summary.vector_deleted, 0)
                self.assertEqual(summary.lexical_deleted, 0)
                self.assertEqual(summary.warnings, [])
            finally:
                helper.cleanup()

    def test_reconcile_warns_on_chroma_delete_failure(self) -> None:
        """If Chroma delete-by-where raises, a warning is emitted but lexical is still cleaned."""
        helper = _IndexHelper()
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as raw:
            tmpdir = Path(raw)

            alice_dir = tmpdir / "kb" / "users" / "alice"
            bob_dir = tmpdir / "kb" / "users" / "bob"
            artifacts_dir = tmpdir / "artifacts" / "dossiers" / "alice"
            shared_dir = tmpdir / "kb" / "shared"

            for d in (alice_dir, bob_dir, artifacts_dir, shared_dir):
                d.mkdir(parents=True, exist_ok=True)

            (alice_dir / "notes.md").write_text("Alice notes alpha beta", encoding="utf-8")
            (bob_dir / "notes.md").write_text("Bob notes gamma delta", encoding="utf-8")
            (artifacts_dir / "report.md").write_text("report data", encoding="utf-8")
            (shared_dir / "config.yaml").write_text("config: true", encoding="utf-8")

            index_dir = tmpdir / "_chroma_index"
            manifest_path = tmpdir / "manifest.json"
            lex_db_path = tmpdir / "lex" / "lexical.sqlite3"
            collection_name = sanitize_collection_name(f"test_{tmpdir.name}")

            fake_root = lambda: tmpdir  # noqa: E731
            p1 = patch("polymarket.rag.index._resolve_repo_root", fake_root)
            p1.start()

            try:
                build_index(
                    roots=[
                        (tmpdir / "kb").as_posix(),
                        (tmpdir / "artifacts").as_posix(),
                    ],
                    embedder=helper.embedder,
                    chunk_size=10,
                    overlap=2,
                    persist_directory=index_dir,
                    collection_name=collection_name,
                    rebuild=True,
                    manifest_path=manifest_path,
                    lexical_db_path=lex_db_path,
                )

                # Delete bob from disk
                (bob_dir / "notes.md").unlink()

                # Patch _chroma_indexed_file_paths and the collection.delete
                # to simulate a Chroma delete failure for bob's file.
                import chromadb

                real_client = chromadb.PersistentClient(path=str(index_dir))
                real_coll = real_client.get_or_create_collection(
                    name=collection_name, metadata={"hnsw:space": "cosine"},
                )
                original_delete = real_coll.delete

                def _failing_delete(**kwargs):
                    where = kwargs.get("where", {})
                    if where.get("file_path") == "kb/users/bob/notes.md":
                        raise RuntimeError("Simulated Chroma delete failure")
                    return original_delete(**kwargs)

                real_coll.delete = _failing_delete

                # Make get_or_create_collection return our patched collection
                real_client.get_or_create_collection = lambda **kw: real_coll

                with patch("chromadb.PersistentClient", return_value=real_client):
                    summary = reconcile_index(
                        roots=[
                            (tmpdir / "kb").as_posix(),
                            (tmpdir / "artifacts").as_posix(),
                        ],
                        persist_directory=index_dir,
                        collection_name=collection_name,
                        lexical_db_path=lex_db_path,
                    )

                # Warning should be emitted for failed vector delete
                self.assertEqual(len(summary.warnings), 1)
                self.assertIn("Chroma delete-by-where failed", summary.warnings[0])
                self.assertIn("--rebuild", summary.warnings[0])

                # Lexical should still have been cleaned
                self.assertEqual(summary.lexical_deleted, 1)
                conn = open_lexical_db(lex_db_path)
                bob_count = conn.execute(
                    "SELECT count(*) FROM chunks WHERE file_path = ?",
                    ("kb/users/bob/notes.md",),
                ).fetchone()[0]
                conn.close()
                self.assertEqual(bob_count, 0)

            finally:
                p1.stop()

    def test_list_indexed_file_paths(self) -> None:
        """list_indexed_file_paths returns the correct set of file_path values."""
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as raw:
            lex_db = Path(raw) / "lex" / "lexical.sqlite3"
            conn = open_lexical_db(lex_db)
            lexical_insert(conn, [
                {
                    "chunk_id": "c1",
                    "doc_id": "d1",
                    "file_path": "kb/users/alice/notes.md",
                    "chunk_index": 0,
                    "doc_type": "user_kb",
                    "user_slug": "alice",
                    "is_private": True,
                    "chunk_text": "alpha beta gamma",
                },
                {
                    "chunk_id": "c2",
                    "doc_id": "d1",
                    "file_path": "kb/users/alice/notes.md",
                    "chunk_index": 1,
                    "doc_type": "user_kb",
                    "user_slug": "alice",
                    "is_private": True,
                    "chunk_text": "delta epsilon zeta",
                },
                {
                    "chunk_id": "c3",
                    "doc_id": "d2",
                    "file_path": "kb/users/bob/notes.md",
                    "chunk_index": 0,
                    "doc_type": "user_kb",
                    "user_slug": "bob",
                    "is_private": True,
                    "chunk_text": "theta iota kappa",
                },
            ])
            conn.commit()

            paths = list_indexed_file_paths(conn)
            conn.close()

            self.assertEqual(paths, {"kb/users/alice/notes.md", "kb/users/bob/notes.md"})


if __name__ == "__main__":
    unittest.main()
