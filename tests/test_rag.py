import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "packages"))

from polymarket.rag.chunker import chunk_text
from polymarket.rag.embedder import BaseEmbedder
from polymarket.rag.index import DEFAULT_COLLECTION, build_index, sanitize_collection_name
from polymarket.rag.manifest import write_manifest
from polymarket.rag.metadata import (
    build_chunk_metadata,
    canonicalize_rel_path,
    compute_chunk_id,
    compute_doc_id,
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


if __name__ == "__main__":
    unittest.main()
