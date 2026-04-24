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
    CaseResult,
    EvalCase,
    EvalReport,
    ModeAggregate,
    _build_aggregate,
    _eval_single,
    _match_pattern,
    load_suite,
    run_eval,
    save_baseline,
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
                self.assertIn("Top Scope Violations", md_text)
                self.assertIn("P50 Latency", md_text)

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


# ---------------------------------------------------------------------------
# Query class segmentation tests (Phase 2)
# ---------------------------------------------------------------------------


class QueryClassSegmentationTests(unittest.TestCase):
    """Tests for per-query-class segmentation in eval harness (Phase 2)."""

    def _build_multi_class_suite(self) -> list[EvalCase]:
        """Return a suite with factual, analytical, and exploratory cases."""
        return [
            EvalCase(
                query="What is the ClickHouse schema?",
                filters={},
                must_include_any=[],
                must_exclude_any=[],
                query_class="factual",
            ),
            EvalCase(
                query="What fee model does PolyTool use?",
                filters={},
                must_include_any=[],
                must_exclude_any=[],
                query_class="factual",
            ),
            EvalCase(
                query="How does market maker handle inventory risk?",
                filters={},
                must_include_any=[],
                must_exclude_any=[],
                query_class="analytical",
            ),
            EvalCase(
                query="What strategies exist for prediction market profitability?",
                filters={},
                must_include_any=[],
                must_exclude_any=[],
                query_class="exploratory",
            ),
        ]

    def _build_fake_report(self, suite: list[EvalCase]) -> EvalReport:
        """Build a minimal EvalReport from a suite without a real index."""
        import hashlib
        case_results: list[CaseResult] = []
        for case in suite:
            case_results.append(
                CaseResult(
                    query=case.query,
                    label=case.label or case.query,
                    mode="lexical",
                    recall_at_k=1.0,
                    mrr_at_k=1.0,
                    scope_violations=[],
                    latency_ms=10.0,
                    result_count=1,
                    query_class=case.query_class,
                )
            )
        agg = ModeAggregate(
            mean_recall_at_k=1.0,
            mean_mrr_at_k=1.0,
            total_scope_violations=0,
            queries_with_violations=0,
            mean_latency_ms=10.0,
            query_count=len(case_results),
            p50_latency_ms=10.0,
            p95_latency_ms=10.0,
            case_results=case_results,
        )
        # Build per_class_modes
        from collections import defaultdict
        class_buckets: dict[str, list[CaseResult]] = defaultdict(list)
        for cr in case_results:
            class_buckets[cr.query_class].append(cr)
        per_class_modes: dict[str, dict[str, ModeAggregate]] = {}
        for qc, cr_list in class_buckets.items():
            per_class_modes[qc] = {
                "lexical": ModeAggregate(
                    mean_recall_at_k=1.0,
                    mean_mrr_at_k=1.0,
                    total_scope_violations=0,
                    queries_with_violations=0,
                    mean_latency_ms=10.0,
                    query_count=len(cr_list),
                    p50_latency_ms=10.0,
                    p95_latency_ms=10.0,
                    case_results=cr_list,
                )
            }
        return EvalReport(
            timestamp="2026-04-08T00:00:00+00:00",
            suite_path="test_suite.jsonl",
            k=8,
            modes={"lexical": agg},
            per_class_modes=per_class_modes,
            corpus_hash="a" * 64,
            eval_config={
                "k": 8,
                "top_k_vector": 25,
                "top_k_lexical": 25,
                "rrf_k": 60,
                "rerank_top_n": 50,
                "embedder_model": None,
                "reranker_model": None,
                "suite_path": "test_suite.jsonl",
            },
        )

    def test_eval_case_has_query_class_field(self) -> None:
        case = EvalCase(
            query="test",
            filters={},
            must_include_any=[],
            must_exclude_any=[],
        )
        self.assertEqual(case.query_class, "unclassified")

    def test_eval_case_query_class_explicit(self) -> None:
        case = EvalCase(
            query="test",
            filters={},
            must_include_any=[],
            must_exclude_any=[],
            query_class="factual",
        )
        self.assertEqual(case.query_class, "factual")

    def test_case_result_has_query_class_field(self) -> None:
        cr = CaseResult(
            query="test",
            label="test",
            mode="lexical",
            recall_at_k=1.0,
            mrr_at_k=1.0,
            scope_violations=[],
            latency_ms=10.0,
            result_count=1,
        )
        self.assertEqual(cr.query_class, "unclassified")

    def test_mode_aggregate_has_query_count(self) -> None:
        agg = ModeAggregate(
            mean_recall_at_k=1.0,
            mean_mrr_at_k=1.0,
            total_scope_violations=0,
            queries_with_violations=0,
            mean_latency_ms=10.0,
            query_count=5,
            p50_latency_ms=10.0,
            p95_latency_ms=10.0,
        )
        self.assertEqual(agg.query_count, 5)
        self.assertGreaterEqual(agg.p50_latency_ms, 0)
        self.assertGreaterEqual(agg.p95_latency_ms, 0)

    def test_eval_report_has_per_class_modes(self) -> None:
        suite = self._build_multi_class_suite()
        report = self._build_fake_report(suite)
        self.assertIn("per_class_modes", report.__dataclass_fields__)
        self.assertIn("factual", report.per_class_modes)
        self.assertIn("analytical", report.per_class_modes)
        self.assertIn("exploratory", report.per_class_modes)

    def test_eval_report_has_corpus_hash(self) -> None:
        suite = self._build_multi_class_suite()
        report = self._build_fake_report(suite)
        self.assertEqual(len(report.corpus_hash), 64)

    def test_eval_report_has_eval_config(self) -> None:
        suite = self._build_multi_class_suite()
        report = self._build_fake_report(suite)
        self.assertIn("k", report.eval_config)
        self.assertIn("top_k_vector", report.eval_config)
        self.assertIn("suite_path", report.eval_config)

    def test_per_class_query_counts(self) -> None:
        suite = self._build_multi_class_suite()
        report = self._build_fake_report(suite)
        # factual has 2 cases
        self.assertEqual(report.per_class_modes["factual"]["lexical"].query_count, 2)
        # analytical has 1 case
        self.assertEqual(report.per_class_modes["analytical"]["lexical"].query_count, 1)
        # exploratory has 1 case
        self.assertEqual(report.per_class_modes["exploratory"]["lexical"].query_count, 1)

    def test_write_report_per_class_in_json(self) -> None:
        suite = self._build_multi_class_suite()
        report = self._build_fake_report(suite)
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as raw:
            tmpdir = Path(raw)
            json_path, md_path = write_report(report, tmpdir / "reports")
            with open(json_path, encoding="utf-8") as f:
                data = json.load(f)
            self.assertIn("per_class_modes", data)
            self.assertIn("corpus_hash", data)
            self.assertIn("eval_config", data)
            self.assertIn("factual", data["per_class_modes"])

    def test_write_report_per_class_in_markdown(self) -> None:
        suite = self._build_multi_class_suite()
        report = self._build_fake_report(suite)
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as raw:
            tmpdir = Path(raw)
            json_path, md_path = write_report(report, tmpdir / "reports")
            md_text = md_path.read_text(encoding="utf-8")
            self.assertIn("Per-Query-Class", md_text)

    def test_run_eval_per_class_modes_populated(self) -> None:
        """Integration test: run_eval populates per_class_modes correctly."""
        helper = _EvalIndexHelper()
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as raw:
            tmpdir = Path(raw)
            index_dir, coll = helper.build(tmpdir)
            lex_db = tmpdir / "kb" / "rag" / "lexical" / "lexical.sqlite3"

            try:
                suite = [
                    EvalCase(
                        query="xylophone",
                        filters={},
                        must_include_any=[],
                        must_exclude_any=[],
                        query_class="factual",
                    ),
                    EvalCase(
                        query="risk analysis",
                        filters={},
                        must_include_any=[],
                        must_exclude_any=[],
                        query_class="analytical",
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

                self.assertIn("factual", report.per_class_modes)
                self.assertIn("analytical", report.per_class_modes)
                self.assertIn("lexical", report.per_class_modes["factual"])
                self.assertEqual(
                    report.per_class_modes["factual"]["lexical"].query_count, 1
                )

            finally:
                helper.cleanup()


class LoadSuiteQueryClassTests(unittest.TestCase):
    """Tests for query_class parsing in load_suite."""

    def test_load_suite_with_query_class(self) -> None:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".jsonl", delete=False, encoding="utf-8"
        ) as f:
            f.write(json.dumps({
                "query": "test",
                "query_class": "factual",
                "expect": {"must_include_any": ["file.md"]},
            }) + "\n")
            f.flush()
            path = f.name

        try:
            cases = load_suite(Path(path))
            self.assertEqual(len(cases), 1)
            self.assertEqual(cases[0].query_class, "factual")
        finally:
            os.unlink(path)

    def test_load_suite_without_query_class_defaults(self) -> None:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".jsonl", delete=False, encoding="utf-8"
        ) as f:
            f.write(json.dumps({
                "query": "test",
                "expect": {},
            }) + "\n")
            f.flush()
            path = f.name

        try:
            cases = load_suite(Path(path))
            self.assertEqual(len(cases), 1)
            self.assertEqual(cases[0].query_class, "unclassified")
        finally:
            os.unlink(path)


# ---------------------------------------------------------------------------
# WP5-B fix: fetch-depth tests (k < 5 must still see a true top-5 window)
# ---------------------------------------------------------------------------


class FetchDepthTests(unittest.TestCase):
    """Tests that run_eval fetches max(k, _PRECISION_K) results so P@5 is valid."""

    def _make_results(self, paths: list[str]) -> list[dict]:
        return [
            {
                "file_path": p,
                "chunk_id": f"{'a' * 63}{i}",
                "doc_id": "b" * 64,
                "score": 1.0 - i * 0.1,
                "snippet": "text",
                "metadata": {},
            }
            for i, p in enumerate(paths)
        ]

    def test_k_less_than_5_query_index_called_with_5(self) -> None:
        """When user k=3, query_index receives fetch_k=5 (max(3, _PRECISION_K))."""
        with patch("polymarket.rag.eval.query_index", return_value=[]) as mock_qi:
            suite = [EvalCase(query="test", filters={}, must_include_any=[], must_exclude_any=[])]
            run_eval(suite, k=3, embedder=None)
            # Only the lexical mode fires when embedder=None; check that call.
            called_k = mock_qi.call_args.kwargs["k"]
            self.assertEqual(called_k, 5)

    def test_k_equal_5_query_index_called_with_5(self) -> None:
        """When user k=5, query_index receives k=5 (unchanged)."""
        with patch("polymarket.rag.eval.query_index", return_value=[]) as mock_qi:
            suite = [EvalCase(query="test", filters={}, must_include_any=[], must_exclude_any=[])]
            run_eval(suite, k=5, embedder=None)
            called_k = mock_qi.call_args.kwargs["k"]
            self.assertEqual(called_k, 5)

    def test_k_greater_than_5_query_index_called_with_k(self) -> None:
        """When user k=8, query_index receives k=8 (unchanged)."""
        with patch("polymarket.rag.eval.query_index", return_value=[]) as mock_qi:
            suite = [EvalCase(query="test", filters={}, must_include_any=[], must_exclude_any=[])]
            run_eval(suite, k=8, embedder=None)
            called_k = mock_qi.call_args.kwargs["k"]
            self.assertEqual(called_k, 8)

    def test_k_less_than_5_precision_uses_full_top5(self) -> None:
        """k=3 — recall uses top-3, precision uses top-5 from the deeper fetch."""
        # Positions 0,1 are relevant (alice); positions 2,3,4 are not.
        results = self._make_results([
            "alice/doc.md", "alice/doc2.md",
            "other.md", "other2.md", "other3.md",
        ])
        with patch("polymarket.rag.eval.query_index", return_value=results):
            suite = [EvalCase(
                query="test",
                filters={},
                must_include_any=["alice"],
                must_exclude_any=[],
            )]
            report = run_eval(suite, k=3, embedder=None)

        cr = report.modes["lexical"].case_results[0]
        self.assertAlmostEqual(cr.recall_at_k, 1.0)   # alice in top-3 → hit
        self.assertAlmostEqual(cr.precision_at_5, 0.4)  # 2 alice / 5 total

    def test_k_less_than_5_recall_respects_user_k(self) -> None:
        """k=2 — relevant doc at rank 3 misses recall@2 but lands in precision@5."""
        # Position 0,1 not relevant; position 2 is alice (rank 3).
        results = self._make_results([
            "other.md", "other2.md",
            "alice/doc.md", "other3.md", "other4.md",
        ])
        with patch("polymarket.rag.eval.query_index", return_value=results):
            suite = [EvalCase(
                query="test",
                filters={},
                must_include_any=["alice"],
                must_exclude_any=[],
            )]
            report = run_eval(suite, k=2, embedder=None)

        cr = report.modes["lexical"].case_results[0]
        self.assertAlmostEqual(cr.recall_at_k, 0.0)    # alice NOT in top-2
        self.assertAlmostEqual(cr.precision_at_5, 0.2)  # 1 alice / 5

    def test_k_greater_than_5_behavior_unchanged(self) -> None:
        """k=8 behaves as before: recall and precision both correct."""
        results = self._make_results(
            ["alice/doc.md"] * 3 + ["other.md"] * 5
        )
        with patch("polymarket.rag.eval.query_index", return_value=results):
            suite = [EvalCase(
                query="test",
                filters={},
                must_include_any=["alice"],
                must_exclude_any=[],
            )]
            report = run_eval(suite, k=8, embedder=None)

        cr = report.modes["lexical"].case_results[0]
        self.assertAlmostEqual(cr.recall_at_k, 1.0)    # alice in top-8
        self.assertAlmostEqual(cr.precision_at_5, 0.6)  # 3 alice / 5


# ---------------------------------------------------------------------------
# WP5-B: Precision@5 tests
# ---------------------------------------------------------------------------


class PrecisionAt5UnitTests(unittest.TestCase):
    """Unit tests for Precision@5 — WP5-B."""

    def _make_result(self, file_path: str) -> dict:
        return {
            "file_path": file_path,
            "chunk_id": "a" * 64,
            "doc_id": "b" * 64,
            "score": 0.9,
            "snippet": "test snippet",
            "metadata": {},
        }

    # --- dataclass field presence ---

    def test_mode_aggregate_has_precision_field(self) -> None:
        agg = ModeAggregate(
            mean_recall_at_k=1.0,
            mean_mrr_at_k=1.0,
            total_scope_violations=0,
            queries_with_violations=0,
            mean_latency_ms=10.0,
        )
        self.assertTrue(hasattr(agg, "mean_precision_at_5"))
        self.assertAlmostEqual(agg.mean_precision_at_5, 0.0)

    def test_case_result_has_precision_field(self) -> None:
        cr = CaseResult(
            query="test",
            label="test",
            mode="lexical",
            recall_at_k=1.0,
            mrr_at_k=1.0,
            scope_violations=[],
            latency_ms=10.0,
            result_count=1,
        )
        self.assertTrue(hasattr(cr, "precision_at_5"))
        self.assertAlmostEqual(cr.precision_at_5, 0.0)

    # --- _eval_single precision computation ---

    def test_eval_single_precision_all_relevant(self) -> None:
        """All top-5 results match must_include_any → precision=1.0."""
        case = EvalCase(
            query="test",
            filters={},
            must_include_any=["alice"],
            must_exclude_any=[],
        )
        results = [self._make_result("alice/notes.md")] * 5 + [self._make_result("other.md")] * 3
        _, _, _, p5 = _eval_single(case, results, 8)
        self.assertAlmostEqual(p5, 1.0)

    def test_eval_single_precision_none_relevant(self) -> None:
        """No top-5 results match must_include_any → precision=0.0."""
        case = EvalCase(
            query="test",
            filters={},
            must_include_any=["alice"],
            must_exclude_any=[],
        )
        results = [self._make_result("other.md")] * 8
        _, _, _, p5 = _eval_single(case, results, 8)
        self.assertAlmostEqual(p5, 0.0)

    def test_eval_single_precision_one_of_five(self) -> None:
        """1 of top-5 results matches → precision=0.2."""
        case = EvalCase(
            query="test",
            filters={},
            must_include_any=["alice"],
            must_exclude_any=[],
        )
        results = [self._make_result("alice/notes.md")] + [self._make_result("other.md")] * 7
        _, _, _, p5 = _eval_single(case, results, 8)
        self.assertAlmostEqual(p5, 0.2)

    def test_eval_single_precision_no_expectations(self) -> None:
        """Empty must_include_any → precision trivially 1.0."""
        case = EvalCase(
            query="test",
            filters={},
            must_include_any=[],
            must_exclude_any=[],
        )
        results = [self._make_result("any.md")] * 5
        _, _, _, p5 = _eval_single(case, results, 8)
        self.assertAlmostEqual(p5, 1.0)

    def test_eval_single_precision_relevant_outside_top5(self) -> None:
        """Relevant result at rank 6 (outside top-5) → precision=0.0."""
        case = EvalCase(
            query="test",
            filters={},
            must_include_any=["alice"],
            must_exclude_any=[],
        )
        results = [self._make_result("other.md")] * 5 + [self._make_result("alice/notes.md")] * 3
        _, _, _, p5 = _eval_single(case, results, 8)
        self.assertAlmostEqual(p5, 0.0)

    def test_eval_single_precision_two_of_five(self) -> None:
        """2 of top-5 results match → precision=0.4."""
        case = EvalCase(
            query="test",
            filters={},
            must_include_any=["alice"],
            must_exclude_any=[],
        )
        results = (
            [self._make_result("alice/notes.md")] * 2
            + [self._make_result("other.md")] * 6
        )
        _, _, _, p5 = _eval_single(case, results, 8)
        self.assertAlmostEqual(p5, 0.4)

    # --- _build_aggregate precision averaging ---

    def test_build_aggregate_precision_average(self) -> None:
        """_build_aggregate averages precision_at_5 across case_results."""
        case_results = [
            CaseResult(
                query="q1", label="q1", mode="lexical",
                recall_at_k=1.0, mrr_at_k=1.0,
                scope_violations=[], latency_ms=10.0,
                result_count=5, precision_at_5=0.4,
            ),
            CaseResult(
                query="q2", label="q2", mode="lexical",
                recall_at_k=0.0, mrr_at_k=0.0,
                scope_violations=[], latency_ms=10.0,
                result_count=5, precision_at_5=0.6,
            ),
        ]
        agg = _build_aggregate(case_results)
        self.assertAlmostEqual(agg.mean_precision_at_5, 0.5)

    def test_build_aggregate_empty_list_precision(self) -> None:
        """Empty case list → mean_precision_at_5=0.0."""
        agg = _build_aggregate([])
        self.assertAlmostEqual(agg.mean_precision_at_5, 0.0)

    def test_build_aggregate_single_case_precision(self) -> None:
        """Single case → mean_precision_at_5 equals that case's precision_at_5."""
        case_results = [
            CaseResult(
                query="q1", label="q1", mode="lexical",
                recall_at_k=1.0, mrr_at_k=1.0,
                scope_violations=[], latency_ms=10.0,
                result_count=5, precision_at_5=0.8,
            ),
        ]
        agg = _build_aggregate(case_results)
        self.assertAlmostEqual(agg.mean_precision_at_5, 0.8)

    # --- report serialization ---

    def _build_report_with_precision(self) -> EvalReport:
        """Build a minimal EvalReport with non-zero precision_at_5."""
        cr = CaseResult(
            query="q1", label="q1", mode="lexical",
            recall_at_k=1.0, mrr_at_k=1.0,
            scope_violations=[], latency_ms=10.0,
            result_count=5, precision_at_5=0.6,
            query_class="factual",
        )
        agg = ModeAggregate(
            mean_recall_at_k=1.0,
            mean_mrr_at_k=1.0,
            mean_precision_at_5=0.6,
            total_scope_violations=0,
            queries_with_violations=0,
            mean_latency_ms=10.0,
            query_count=1,
            p50_latency_ms=10.0,
            p95_latency_ms=10.0,
            case_results=[cr],
        )
        return EvalReport(
            timestamp="2026-04-23T00:00:00+00:00",
            suite_path="test.jsonl",
            k=8,
            modes={"lexical": agg},
            per_class_modes={"factual": {"lexical": agg}},
            corpus_hash="a" * 64,
            eval_config={"k": 8},
        )

    def test_write_report_precision_in_json(self) -> None:
        """report.json includes mean_precision_at_5 in ModeAggregate."""
        report = self._build_report_with_precision()
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as raw:
            json_path, _ = write_report(report, Path(raw) / "reports")
            with open(json_path, encoding="utf-8") as f:
                data = json.load(f)
            lexical = data["modes"]["lexical"]
            self.assertIn("mean_precision_at_5", lexical)
            self.assertAlmostEqual(lexical["mean_precision_at_5"], 0.6)

    def test_write_report_precision_in_markdown(self) -> None:
        """summary.md includes P@5 column header."""
        report = self._build_report_with_precision()
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as raw:
            _, md_path = write_report(report, Path(raw) / "reports")
            md_text = md_path.read_text(encoding="utf-8")
            self.assertIn("P@5", md_text)

    def test_per_class_precision_in_json(self) -> None:
        """per_class_modes in report.json includes mean_precision_at_5."""
        report = self._build_report_with_precision()
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as raw:
            json_path, _ = write_report(report, Path(raw) / "reports")
            with open(json_path, encoding="utf-8") as f:
                data = json.load(f)
            factual_lexical = data["per_class_modes"]["factual"]["lexical"]
            self.assertIn("mean_precision_at_5", factual_lexical)
            self.assertAlmostEqual(factual_lexical["mean_precision_at_5"], 0.6)

    def test_per_case_detail_has_precision_in_markdown(self) -> None:
        """Per-case detail lines in summary.md include p@5."""
        report = self._build_report_with_precision()
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as raw:
            _, md_path = write_report(report, Path(raw) / "reports")
            md_text = md_path.read_text(encoding="utf-8")
            self.assertIn("p@5=", md_text)

    def test_cli_mode_table_has_p5_column(self) -> None:
        """_print_mode_table output includes 'P@5' header."""
        import io
        from contextlib import redirect_stdout
        from tools.cli.rag_eval import _print_mode_table

        modes = {
            "lexical": ModeAggregate(
                mean_recall_at_k=0.8,
                mean_mrr_at_k=0.7,
                mean_precision_at_5=0.6,
                total_scope_violations=0,
                queries_with_violations=0,
                mean_latency_ms=10.0,
                query_count=5,
                p50_latency_ms=10.0,
                p95_latency_ms=15.0,
            ),
        }
        buf = io.StringIO()
        with redirect_stdout(buf):
            _print_mode_table(modes, 8, "Test Header", show_query_count=True)
        output = buf.getvalue()
        self.assertIn("P@5", output)
        # Verify the precision value appears in the row
        self.assertIn("0.600", output)


# ---------------------------------------------------------------------------
# WP5-D: save_baseline unit tests
# ---------------------------------------------------------------------------


def _build_minimal_report() -> EvalReport:
    """Build a minimal EvalReport with non-trivial metrics for baseline tests."""
    cr = CaseResult(
        query="q1", label="q1", mode="lexical",
        recall_at_k=1.0, mrr_at_k=0.5,
        scope_violations=[], latency_ms=12.0,
        result_count=5, precision_at_5=0.6,
        query_class="factual",
    )
    agg = ModeAggregate(
        mean_recall_at_k=1.0, mean_mrr_at_k=0.5,
        mean_precision_at_5=0.6,
        total_scope_violations=0, queries_with_violations=0,
        mean_latency_ms=12.0, query_count=1,
        p50_latency_ms=12.0, p95_latency_ms=12.0,
        case_results=[cr],
    )
    return EvalReport(
        timestamp="2026-04-23T10:00:00+00:00",
        suite_path="docs/eval/ris_retrieval_benchmark.jsonl",
        k=8,
        modes={"lexical": agg},
        per_class_modes={"factual": {"lexical": agg}},
        corpus_hash="a" * 64,
        eval_config={"k": 8, "suite_path": "docs/eval/ris_retrieval_benchmark.jsonl"},
    )


class BaselineSaveTests(unittest.TestCase):
    """Unit tests for save_baseline — WP5-D."""

    def test_save_baseline_creates_file(self) -> None:
        report = _build_minimal_report()
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as raw:
            path = Path(raw) / "baseline.json"
            save_baseline(report, path)
            self.assertTrue(path.exists())

    def test_save_baseline_creates_parent_dirs(self) -> None:
        """save_baseline creates intermediate parent directories."""
        report = _build_minimal_report()
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as raw:
            path = Path(raw) / "a" / "b" / "c" / "baseline.json"
            save_baseline(report, path)
            self.assertTrue(path.exists())

    def test_save_baseline_json_has_required_fields(self) -> None:
        report = _build_minimal_report()
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as raw:
            path = Path(raw) / "baseline.json"
            save_baseline(report, path)
            data = json.loads(path.read_text(encoding="utf-8"))
            for field_name in (
                "frozen_at", "timestamp", "suite_path", "k",
                "corpus_hash", "eval_config", "modes", "per_class_modes",
            ):
                self.assertIn(field_name, data, f"Missing required field: {field_name}")

    def test_save_baseline_frozen_at_is_valid_iso(self) -> None:
        from datetime import datetime as _datetime
        report = _build_minimal_report()
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as raw:
            path = Path(raw) / "baseline.json"
            save_baseline(report, path)
            data = json.loads(path.read_text(encoding="utf-8"))
            # fromisoformat raises ValueError if the string is not a valid ISO timestamp
            dt = _datetime.fromisoformat(data["frozen_at"])
            self.assertIsNotNone(dt)

    def test_save_baseline_preserves_report_data(self) -> None:
        report = _build_minimal_report()
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as raw:
            path = Path(raw) / "baseline.json"
            save_baseline(report, path)
            data = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(data["suite_path"], "docs/eval/ris_retrieval_benchmark.jsonl")
            self.assertEqual(data["k"], 8)
            self.assertEqual(data["corpus_hash"], "a" * 64)
            self.assertIn("lexical", data["modes"])
            self.assertAlmostEqual(data["modes"]["lexical"]["mean_precision_at_5"], 0.6)
            self.assertIn("factual", data["per_class_modes"])

    def test_save_baseline_returns_path(self) -> None:
        report = _build_minimal_report()
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as raw:
            path = Path(raw) / "baseline.json"
            result = save_baseline(report, path)
            self.assertIsInstance(result, Path)
            self.assertTrue(result.exists())


# ---------------------------------------------------------------------------
# WP5-D: CLI --save-baseline flag tests
# ---------------------------------------------------------------------------


class CLIBaselineFlagTests(unittest.TestCase):
    """Tests for --save-baseline flag in rag_eval CLI — WP5-D."""

    def _run_cli(self, argv: list, helper, index_dir, coll) -> int:
        from tools.cli.rag_eval import main as rag_eval_main
        with patch(
            "tools.cli.rag_eval.SentenceTransformerEmbedder",
            return_value=helper.embedder,
        ):
            return rag_eval_main(argv)

    def _suite_argv(self, suite_path, index_dir, coll, report_dir, extra=()) -> list:
        return [
            "--suite", str(suite_path),
            "--k", "4",
            "--persist-dir", str(index_dir),
            "--collection", coll,
            "--output-dir", str(report_dir),
            *extra,
        ]

    def test_save_baseline_flag_creates_file(self) -> None:
        """--save-baseline PATH writes the baseline artifact to PATH."""
        helper = _EvalIndexHelper()
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as raw:
            tmpdir = Path(raw)
            index_dir, coll = helper.build(tmpdir)
            suite_path = tmpdir / "suite.jsonl"
            suite_path.write_text(
                json.dumps({"query": "notes", "filters": {}, "expect": {}}) + "\n",
                encoding="utf-8",
            )
            baseline_path = tmpdir / "baseline_metrics.json"
            try:
                exit_code = self._run_cli(
                    self._suite_argv(
                        suite_path, index_dir, coll, tmpdir / "reports",
                        extra=["--save-baseline", str(baseline_path)],
                    ),
                    helper, index_dir, coll,
                )
                self.assertIn(exit_code, (0, 2))
                self.assertTrue(baseline_path.exists())
            finally:
                helper.cleanup()

    def test_no_save_baseline_without_flag(self) -> None:
        """Without --save-baseline, no baseline artifact is written."""
        helper = _EvalIndexHelper()
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as raw:
            tmpdir = Path(raw)
            index_dir, coll = helper.build(tmpdir)
            suite_path = tmpdir / "suite.jsonl"
            suite_path.write_text(
                json.dumps({"query": "notes", "filters": {}, "expect": {}}) + "\n",
                encoding="utf-8",
            )
            baseline_path = tmpdir / "should_not_exist.json"
            try:
                self._run_cli(
                    self._suite_argv(
                        suite_path, index_dir, coll, tmpdir / "reports",
                        # No --save-baseline
                    ),
                    helper, index_dir, coll,
                )
                self.assertFalse(baseline_path.exists())
            finally:
                helper.cleanup()

    def test_save_baseline_json_has_required_fields(self) -> None:
        """Baseline artifact written by CLI contains required top-level fields."""
        helper = _EvalIndexHelper()
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as raw:
            tmpdir = Path(raw)
            index_dir, coll = helper.build(tmpdir)
            suite_path = tmpdir / "suite.jsonl"
            suite_path.write_text(
                json.dumps({"query": "notes", "filters": {}, "expect": {}}) + "\n",
                encoding="utf-8",
            )
            baseline_path = tmpdir / "baseline_metrics.json"
            try:
                self._run_cli(
                    self._suite_argv(
                        suite_path, index_dir, coll, tmpdir / "reports",
                        extra=["--save-baseline", str(baseline_path)],
                    ),
                    helper, index_dir, coll,
                )
                data = json.loads(baseline_path.read_text(encoding="utf-8"))
                for field_name in ("frozen_at", "timestamp", "suite_path", "k", "modes"):
                    self.assertIn(field_name, data, f"Missing field in baseline: {field_name}")
            finally:
                helper.cleanup()

    def test_save_baseline_nested_path_creation(self) -> None:
        """--save-baseline with a nested non-existent path creates parent dirs."""
        helper = _EvalIndexHelper()
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as raw:
            tmpdir = Path(raw)
            index_dir, coll = helper.build(tmpdir)
            suite_path = tmpdir / "suite.jsonl"
            suite_path.write_text(
                json.dumps({"query": "notes", "filters": {}, "expect": {}}) + "\n",
                encoding="utf-8",
            )
            baseline_path = tmpdir / "nested" / "dirs" / "baseline_metrics.json"
            try:
                exit_code = self._run_cli(
                    self._suite_argv(
                        suite_path, index_dir, coll, tmpdir / "reports",
                        extra=["--save-baseline", str(baseline_path)],
                    ),
                    helper, index_dir, coll,
                )
                self.assertIn(exit_code, (0, 2))
                self.assertTrue(baseline_path.exists())
            finally:
                helper.cleanup()


if __name__ == "__main__":
    unittest.main()
