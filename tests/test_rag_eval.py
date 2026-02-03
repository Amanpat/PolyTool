"""Tests for the offline RAG eval harness (packages/polymarket/rag/eval.py)."""

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
from polymarket.rag.eval import (
    EvalCase,
    _match_pattern,
    load_suite,
    run_eval,
    write_report,
)
from polymarket.rag.index import build_index, sanitize_collection_name
from polymarket.rag.lexical import open_lexical_db


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


class _EvalIndexHelper:
    """Build a temp index with synthetic data for eval tests."""

    def __init__(self) -> None:
        self.embedder = _FakeEmbedder()
        self._patches: list = []

    def build(self, tmpdir: Path):
        alice_dir = tmpdir / "kb" / "users" / "alice"
        bob_dir = tmpdir / "kb" / "users" / "bob"
        alice_dir.mkdir(parents=True, exist_ok=True)
        bob_dir.mkdir(parents=True, exist_ok=True)

        (alice_dir / "notes.md").write_text(
            "Alice private notes about xylophone instrument practice blockchain",
            encoding="utf-8",
        )
        (bob_dir / "notes.md").write_text(
            "Bob private notes about risk analysis quantum computing delta",
            encoding="utf-8",
        )

        index_dir = tmpdir / "_chroma_index"
        manifest_path = tmpdir / "manifest.json"
        collection_name = sanitize_collection_name(f"test_{tmpdir.name}")

        fake_root = lambda: tmpdir  # noqa: E731
        p1 = patch("polymarket.rag.index._resolve_repo_root", fake_root)
        p2 = patch("polymarket.rag.query._resolve_repo_root", fake_root)
        p1.start()
        p2.start()
        self._patches = [p1, p2]

        build_index(
            roots=[(tmpdir / "kb").as_posix()],
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


# ---------------------------------------------------------------------------
# Pattern matching unit tests
# ---------------------------------------------------------------------------


class PatternMatchingTests(unittest.TestCase):
    """Unit tests for _match_pattern with various pattern types."""

    def _result(self, **overrides) -> dict:
        base = {
            "file_path": "kb/users/alice/notes.md",
            "chunk_id": "a" * 64,
            "doc_id": "b" * 64,
            "score": 0.9,
            "snippet": "some text",
            "metadata": {
                "file_path": "kb/users/alice/notes.md",
                "doc_type": "user_kb",
                "user_slug": "alice",
                "is_private": True,
            },
        }
        base.update(overrides)
        return base

    def test_user_slug_match(self) -> None:
        r = self._result()
        self.assertTrue(_match_pattern("user_slug:alice", r))
        self.assertFalse(_match_pattern("user_slug:bob", r))

    def test_doc_type_match(self) -> None:
        r = self._result()
        self.assertTrue(_match_pattern("doc_type:user_kb", r))
        self.assertFalse(_match_pattern("doc_type:dossier", r))

    def test_is_private_true(self) -> None:
        r = self._result()
        self.assertTrue(_match_pattern("is_private:true", r))
        self.assertFalse(_match_pattern("is_private:false", r))

    def test_is_private_false(self) -> None:
        r = self._result(metadata={"is_private": False})
        self.assertTrue(_match_pattern("is_private:false", r))
        self.assertFalse(_match_pattern("is_private:true", r))

    def test_hex64_matches_chunk_id(self) -> None:
        cid = "a" * 64
        r = self._result(chunk_id=cid)
        self.assertTrue(_match_pattern(cid, r))

    def test_hex64_matches_doc_id(self) -> None:
        did = "b" * 64
        r = self._result(doc_id=did)
        self.assertTrue(_match_pattern(did, r))

    def test_hex64_no_match(self) -> None:
        r = self._result(chunk_id="a" * 64, doc_id="b" * 64)
        self.assertFalse(_match_pattern("c" * 64, r))

    def test_file_path_substring(self) -> None:
        r = self._result(file_path="kb/users/alice/notes.md")
        self.assertTrue(_match_pattern("alice/notes.md", r))
        self.assertTrue(_match_pattern("kb/users/alice", r))
        self.assertFalse(_match_pattern("bob/notes.md", r))

    def test_file_path_full_path(self) -> None:
        r = self._result(file_path="kb/users/alice/notes.md")
        self.assertTrue(_match_pattern("kb/users/alice/notes.md", r))


# ---------------------------------------------------------------------------
# Suite loading tests
# ---------------------------------------------------------------------------


class LoadSuiteTests(unittest.TestCase):
    """Test load_suite validates input correctly."""

    def test_valid_suite(self) -> None:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".jsonl", delete=False, encoding="utf-8"
        ) as f:
            f.write(json.dumps({"query": "test", "expect": {"must_include_any": ["file.md"]}}) + "\n")
            f.write(json.dumps({"query": "test2"}) + "\n")
            f.flush()
            path = f.name

        try:
            cases = load_suite(Path(path))
            self.assertEqual(len(cases), 2)
            self.assertEqual(cases[0].query, "test")
            self.assertEqual(cases[0].must_include_any, ["file.md"])
            self.assertEqual(cases[1].must_include_any, [])
        finally:
            os.unlink(path)

    def test_missing_query_raises(self) -> None:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".jsonl", delete=False, encoding="utf-8"
        ) as f:
            f.write(json.dumps({"filters": {}}) + "\n")
            f.flush()
            path = f.name

        try:
            with self.assertRaises(ValueError) as ctx:
                load_suite(Path(path))
            self.assertIn("Missing 'query'", str(ctx.exception))
        finally:
            os.unlink(path)

    def test_invalid_json_raises(self) -> None:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".jsonl", delete=False, encoding="utf-8"
        ) as f:
            f.write("not json\n")
            f.flush()
            path = f.name

        try:
            with self.assertRaises(ValueError) as ctx:
                load_suite(Path(path))
            self.assertIn("Invalid JSON", str(ctx.exception))
        finally:
            os.unlink(path)

    def test_empty_suite_raises(self) -> None:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".jsonl", delete=False, encoding="utf-8"
        ) as f:
            f.write("\n\n")
            f.flush()
            path = f.name

        try:
            with self.assertRaises(ValueError) as ctx:
                load_suite(Path(path))
            self.assertIn("empty", str(ctx.exception))
        finally:
            os.unlink(path)

    def test_file_not_found(self) -> None:
        with self.assertRaises(FileNotFoundError):
            load_suite(Path("/nonexistent/path.jsonl"))


# ---------------------------------------------------------------------------
# Eval integration tests
# ---------------------------------------------------------------------------


class EvalBasicRecallTests(unittest.TestCase):
    """Index 2 files, query for unique keyword, assert recall@k."""

    def test_eval_basic_recall(self) -> None:
        helper = _EvalIndexHelper()
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as raw:
            tmpdir = Path(raw)
            index_dir, coll = helper.build(tmpdir)
            lex_db = tmpdir / "kb" / "rag" / "lexical" / "lexical.sqlite3"

            try:
                suite = [
                    EvalCase(
                        query="xylophone instrument",
                        filters={"private_only": False},
                        must_include_any=["kb/users/alice/notes.md"],
                        must_exclude_any=[],
                        notes="should find alice's notes",
                    ),
                ]

                report = run_eval(
                    suite,
                    k=8,
                    embedder=helper.embedder,
                    persist_directory=index_dir,
                    collection_name=coll,
                    lexical_db_path=lex_db,
                    suite_path="test_suite",
                )

                # At least one mode should have recall > 0
                any_recall = False
                for mode_name, agg in report.modes.items():
                    for cr in agg.case_results:
                        if cr.recall_at_k > 0:
                            any_recall = True
                self.assertTrue(any_recall, "Expected at least one mode to find alice's notes")

            finally:
                helper.cleanup()


class EvalScopeViolationTests(unittest.TestCase):
    """Create a case with must_exclude_any and verify violations are detected."""

    def test_eval_scope_violation_detected(self) -> None:
        helper = _EvalIndexHelper()
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as raw:
            tmpdir = Path(raw)
            index_dir, coll = helper.build(tmpdir)
            lex_db = tmpdir / "kb" / "rag" / "lexical" / "lexical.sqlite3"

            try:
                # Query without user filter but expect no bob results
                # Since both alice and bob have "notes" keyword, a broad query
                # should return both, causing a violation for bob exclusion.
                suite = [
                    EvalCase(
                        query="private notes",
                        filters={"private_only": False},
                        must_include_any=[],
                        must_exclude_any=["user_slug:bob"],
                        notes="should detect bob in results as violation",
                    ),
                ]

                report = run_eval(
                    suite,
                    k=20,
                    embedder=helper.embedder,
                    persist_directory=index_dir,
                    collection_name=coll,
                    lexical_db_path=lex_db,
                    suite_path="test_suite",
                )

                # Check if at least one mode reports violations
                any_violations = False
                for mode_name, agg in report.modes.items():
                    if agg.total_scope_violations > 0:
                        any_violations = True
                self.assertTrue(
                    any_violations,
                    "Expected scope violations for bob in unfiltered query",
                )

            finally:
                helper.cleanup()


class EvalAllModesRunTests(unittest.TestCase):
    """Verify report contains results for vector, lexical, and hybrid modes."""

    def test_eval_all_modes_run(self) -> None:
        helper = _EvalIndexHelper()
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as raw:
            tmpdir = Path(raw)
            index_dir, coll = helper.build(tmpdir)
            lex_db = tmpdir / "kb" / "rag" / "lexical" / "lexical.sqlite3"

            try:
                suite = [
                    EvalCase(
                        query="notes",
                        filters={"private_only": False},
                        must_include_any=[],
                        must_exclude_any=[],
                    ),
                ]

                report = run_eval(
                    suite,
                    k=8,
                    embedder=helper.embedder,
                    persist_directory=index_dir,
                    collection_name=coll,
                    lexical_db_path=lex_db,
                    suite_path="test_suite",
                )

                self.assertIn("vector", report.modes)
                self.assertIn("lexical", report.modes)
                self.assertIn("hybrid", report.modes)

                for mode_name in ("vector", "lexical", "hybrid"):
                    agg = report.modes[mode_name]
                    self.assertEqual(len(agg.case_results), 1)
                    self.assertGreaterEqual(agg.case_results[0].latency_ms, 0)

            finally:
                helper.cleanup()


class EvalWriteReportTests(unittest.TestCase):
    """Test write_report produces expected files."""

    def test_write_report_creates_files(self) -> None:
        helper = _EvalIndexHelper()
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as raw:
            tmpdir = Path(raw)
            index_dir, coll = helper.build(tmpdir)
            lex_db = tmpdir / "kb" / "rag" / "lexical" / "lexical.sqlite3"

            try:
                suite = [
                    EvalCase(
                        query="notes",
                        filters={"private_only": False},
                        must_include_any=[],
                        must_exclude_any=[],
                    ),
                ]

                report = run_eval(
                    suite,
                    k=8,
                    embedder=helper.embedder,
                    persist_directory=index_dir,
                    collection_name=coll,
                    lexical_db_path=lex_db,
                    suite_path="test_suite",
                )

                report_dir = tmpdir / "eval_reports"
                json_path, md_path = write_report(report, report_dir)

                self.assertTrue(json_path.exists())
                self.assertTrue(md_path.exists())

                # Validate JSON is parseable
                with open(json_path, encoding="utf-8") as f:
                    data = json.load(f)
                self.assertIn("modes", data)
                self.assertIn("timestamp", data)
                self.assertEqual(data["k"], 8)

                # Validate markdown has content
                md_text = md_path.read_text(encoding="utf-8")
                self.assertIn("RAG Eval Report", md_text)
                self.assertIn("vector", md_text)
                self.assertIn("lexical", md_text)
                self.assertIn("hybrid", md_text)

            finally:
                helper.cleanup()


# ---------------------------------------------------------------------------
# Eval hybrid+rerank mode tests
# ---------------------------------------------------------------------------


class _FakeReranker:
    """Deterministic reranker for testing."""

    def __init__(self) -> None:
        self.model_name = "fake-reranker"

    def score_pairs(self, query: str, documents: list[str]) -> list[float]:
        """Score documents by their length."""
        return [float(len(doc)) for doc in documents]


class EvalHybridRerankModeTests(unittest.TestCase):
    """Test eval harness with hybrid+rerank mode."""

    def test_eval_includes_hybrid_rerank_mode(self) -> None:
        """Test that eval includes hybrid+rerank mode when reranker is provided."""
        helper = _EvalIndexHelper()
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as raw:
            tmpdir = Path(raw)
            index_dir, coll = helper.build(tmpdir)
            lex_db = tmpdir / "kb" / "rag" / "lexical" / "lexical.sqlite3"

            try:
                suite = [
                    EvalCase(
                        query="notes",
                        filters={"private_only": False},
                        must_include_any=[],
                        must_exclude_any=[],
                    ),
                ]

                reranker = _FakeReranker()
                report = run_eval(
                    suite,
                    k=8,
                    embedder=helper.embedder,
                    persist_directory=index_dir,
                    collection_name=coll,
                    lexical_db_path=lex_db,
                    reranker=reranker,
                    suite_path="test_suite",
                )

                # Should include hybrid+rerank mode
                self.assertIn("hybrid+rerank", report.modes)
                agg = report.modes["hybrid+rerank"]
                self.assertEqual(len(agg.case_results), 1)
                self.assertGreater(agg.case_results[0].result_count, 0)
                self.assertNotEqual(agg.case_results[0].notes, "skipped: no reranker")

            finally:
                helper.cleanup()

    def test_eval_skips_hybrid_rerank_without_reranker(self) -> None:
        """Test that eval skips hybrid+rerank mode when reranker is None."""
        helper = _EvalIndexHelper()
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as raw:
            tmpdir = Path(raw)
            index_dir, coll = helper.build(tmpdir)
            lex_db = tmpdir / "kb" / "rag" / "lexical" / "lexical.sqlite3"

            try:
                suite = [
                    EvalCase(
                        query="notes",
                        filters={"private_only": False},
                        must_include_any=[],
                        must_exclude_any=[],
                    ),
                ]

                report = run_eval(
                    suite,
                    k=8,
                    embedder=helper.embedder,
                    persist_directory=index_dir,
                    collection_name=coll,
                    lexical_db_path=lex_db,
                    reranker=None,  # No reranker
                    suite_path="test_suite",
                )

                # Should have hybrid+rerank mode but it should be skipped
                self.assertIn("hybrid+rerank", report.modes)
                agg = report.modes["hybrid+rerank"]
                self.assertEqual(len(agg.case_results), 1)
                self.assertEqual(agg.case_results[0].notes, "skipped: no reranker")
                self.assertEqual(agg.case_results[0].result_count, 0)

            finally:
                helper.cleanup()


# ---------------------------------------------------------------------------
# CLI tests
# ---------------------------------------------------------------------------


class CLITests(unittest.TestCase):
    """Test the CLI main function."""

    def test_cli_main_with_valid_suite(self) -> None:
        from tools.cli.rag_eval import main as rag_eval_main

        helper = _EvalIndexHelper()
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as raw:
            tmpdir = Path(raw)
            index_dir, coll = helper.build(tmpdir)

            # Write a minimal suite file
            suite_path = tmpdir / "suite.jsonl"
            suite_path.write_text(
                json.dumps({
                    "query": "notes",
                    "filters": {"private_only": False},
                    "expect": {},
                }) + "\n",
                encoding="utf-8",
            )

            report_dir = tmpdir / "reports"

            try:
                # Patch embedder to avoid loading real model
                with patch(
                    "tools.cli.rag_eval.SentenceTransformerEmbedder",
                    return_value=helper.embedder,
                ):
                    exit_code = rag_eval_main([
                        "--suite", str(suite_path),
                        "--k", "4",
                        "--persist-dir", str(index_dir),
                        "--collection", coll,
                        "--output-dir", str(report_dir),
                    ])

                self.assertIn(exit_code, (0, 2))

                # Verify report was written
                report_dirs = list(report_dir.iterdir())
                self.assertEqual(len(report_dirs), 1)
                self.assertTrue((report_dirs[0] / "report.json").exists())
                self.assertTrue((report_dirs[0] / "summary.md").exists())

            finally:
                helper.cleanup()

    def test_cli_main_bad_suite(self) -> None:
        from tools.cli.rag_eval import main as rag_eval_main

        exit_code = rag_eval_main(["--suite", "/nonexistent/suite.jsonl"])
        self.assertEqual(exit_code, 1)


if __name__ == "__main__":
    unittest.main()
