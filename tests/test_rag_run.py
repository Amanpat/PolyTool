"""Tests for tools/cli/rag_run.py — rag-run command."""

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "packages"))

from tools.cli import rag_run


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _make_template_query(label: str, question: str, user_slug: str = "testuser") -> Dict:
    """Return a rag_queries.json entry as written by llm-bundle when RAG unavailable."""
    return {
        "execution_reason": "rag_unavailable",
        "execution_status": "not_executed",
        "filters": {
            "date_from": None,
            "date_to": None,
            "doc_types": None,
            "include_archive": False,
            "prefix_backstop": [
                f"kb/users/{user_slug}/",
                f"artifacts/dossiers/{user_slug}/",
                f"artifacts/dossiers/users/{user_slug}/",
            ],
            "private_only": True,
            "public_only": False,
            "user_slug": user_slug,
        },
        "k": 8,
        "label": label,
        "mode": "hybrid+rerank",
        "question": question,
        "results": [],
    }


def _make_bundle_manifest(collection: str = "polytool_rag", persist_dir: str = "kb/rag/index") -> Dict:
    return {
        "created_at_utc": "2026-03-04T10:00:00Z",
        "dossier_path": "artifacts/dossiers/users/testuser/0xabc/2026-03-04/run1",
        "model_hint": "opus-4.5",
        "rag_query_settings": {
            "collection": collection,
            "device": "auto",
            "hybrid": True,
            "include_archive": False,
            "k": 8,
            "model": "BAAI/bge-large-en-v1.5",
            "persist_dir": persist_dir,
            "private_only": True,
            "public_only": False,
            "rerank": True,
            "rerank_model": "cross-encoder/ms-marco-MiniLM-L-6-v2",
            "rerank_top_n": 50,
            "rrf_k": 60,
            "top_k_lexical": 25,
            "top_k_vector": 25,
        },
        "run_id": "run1",
        "selected_excerpts": [],
        "user_slug": "testuser",
    }


def _fake_execute_queries_with_results(
    queries: List[Dict], settings: Dict
) -> List[Dict]:
    """Mock _execute_queries: returns one result per query."""
    return [
        {
            **q,
            "results": [
                {
                    "file_path": f"kb/users/testuser/notes/note.md",
                    "chunk_id": f"chunk_{i}",
                    "doc_id": f"doc_{i}",
                    "snippet": f"Relevant snippet for: {q['question'][:30]}",
                }
            ],
            "execution_status": "executed",
            "execution_reason": None,
            "executed_at_utc": "2026-03-04T12:00:00Z",
        }
        for i, q in enumerate(queries)
    ]


def _fake_execute_queries_empty(
    queries: List[Dict], settings: Dict
) -> List[Dict]:
    """Mock _execute_queries: executes but returns no matches."""
    return [
        {
            **q,
            "results": [],
            "execution_status": "executed",
            "execution_reason": "no_matches_under_filters",
            "executed_at_utc": "2026-03-04T12:00:00Z",
        }
        for q in queries
    ]


# ---------------------------------------------------------------------------
# _load_rag_queries
# ---------------------------------------------------------------------------

class TestLoadRagQueries:
    def test_loads_list_format(self, tmp_path):
        entries = [_make_template_query("profile", "What is the user profile?")]
        path = tmp_path / "rag_queries.json"
        _write_json(path, entries)
        loaded = rag_run._load_rag_queries(path)
        assert loaded == entries

    def test_rejects_non_list(self, tmp_path):
        path = tmp_path / "rag_queries.json"
        _write_json(path, {"queries": []})
        with pytest.raises(ValueError, match="Expected a JSON array"):
            rag_run._load_rag_queries(path)

    def test_accepts_empty_list(self, tmp_path):
        path = tmp_path / "rag_queries.json"
        _write_json(path, [])
        result = rag_run._load_rag_queries(path)
        assert result == []


# ---------------------------------------------------------------------------
# _load_bundle_settings
# ---------------------------------------------------------------------------

class TestLoadBundleSettings:
    def test_loads_from_manifest(self, tmp_path):
        manifest = _make_bundle_manifest(collection="my_coll", persist_dir="kb/rag/myindex")
        path = tmp_path / "bundle_manifest.json"
        _write_json(path, manifest)
        settings = rag_run._load_bundle_settings(path)
        assert settings["collection"] == "my_coll"
        assert settings["persist_dir"] == "kb/rag/myindex"
        assert settings["k"] == 8

    def test_returns_defaults_when_manifest_missing(self, tmp_path):
        missing = tmp_path / "nonexistent.json"
        settings = rag_run._load_bundle_settings(missing)
        assert settings["collection"] == rag_run._DEFAULT_COLLECTION
        assert settings["persist_dir"] == rag_run._DEFAULT_PERSIST_DIR

    def test_returns_defaults_when_path_is_none(self):
        settings = rag_run._load_bundle_settings(None)
        assert settings["device"] == "auto"
        assert settings["top_k_vector"] == 25

    def test_handles_corrupt_json(self, tmp_path):
        path = tmp_path / "bundle_manifest.json"
        path.write_text("not valid json", encoding="utf-8")
        settings = rag_run._load_bundle_settings(path)
        assert settings["collection"] == rag_run._DEFAULT_COLLECTION


# ---------------------------------------------------------------------------
# _parse_mode
# ---------------------------------------------------------------------------

class TestParseMode:
    def test_hybrid_rerank(self):
        assert rag_run._parse_mode("hybrid+rerank") == (True, False, True)

    def test_hybrid_only(self):
        assert rag_run._parse_mode("hybrid") == (True, False, False)

    def test_vector_rerank(self):
        assert rag_run._parse_mode("vector+rerank") == (False, False, True)

    def test_vector_only(self):
        assert rag_run._parse_mode("vector") == (False, False, False)

    def test_lexical(self):
        assert rag_run._parse_mode("lexical") == (False, True, False)


# ---------------------------------------------------------------------------
# main — integration tests with mocked _execute_queries
# ---------------------------------------------------------------------------

class TestRagRunMain:
    def test_writes_results_back_in_place(self, tmp_path, monkeypatch):
        bundle_dir = tmp_path / "bundle"
        queries = [_make_template_query("profile", "Q1"), _make_template_query("risk", "Q2")]
        _write_json(bundle_dir / "rag_queries.json", queries)
        _write_json(bundle_dir / "bundle_manifest.json", _make_bundle_manifest())

        monkeypatch.setattr(rag_run, "_RAG_AVAILABLE", True)
        monkeypatch.setattr(rag_run, "_execute_queries", _fake_execute_queries_with_results)

        rc = rag_run.main(["--rag-queries", str(bundle_dir / "rag_queries.json")])
        assert rc == 0

        updated = json.loads((bundle_dir / "rag_queries.json").read_text(encoding="utf-8"))
        assert len(updated) == 2
        for entry in updated:
            assert entry["execution_status"] == "executed"
            assert len(entry["results"]) == 1
            assert "snippet" in entry["results"][0]

    def test_writes_to_out_path(self, tmp_path, monkeypatch):
        bundle_dir = tmp_path / "bundle"
        out_path = tmp_path / "output" / "rag_queries_updated.json"
        queries = [_make_template_query("profile", "Q1")]
        _write_json(bundle_dir / "rag_queries.json", queries)
        _write_json(bundle_dir / "bundle_manifest.json", _make_bundle_manifest())

        monkeypatch.setattr(rag_run, "_RAG_AVAILABLE", True)
        monkeypatch.setattr(rag_run, "_execute_queries", _fake_execute_queries_with_results)

        rc = rag_run.main([
            "--rag-queries", str(bundle_dir / "rag_queries.json"),
            "--out", str(out_path),
        ])
        assert rc == 0
        assert out_path.exists()
        # Original unchanged
        original = json.loads((bundle_dir / "rag_queries.json").read_text(encoding="utf-8"))
        assert original[0].get("execution_status") == "not_executed"

    def test_empty_results_writes_explicit_reason(self, tmp_path, monkeypatch):
        bundle_dir = tmp_path / "bundle"
        queries = [_make_template_query("patterns", "Trading patterns?")]
        _write_json(bundle_dir / "rag_queries.json", queries)
        _write_json(bundle_dir / "bundle_manifest.json", _make_bundle_manifest())

        monkeypatch.setattr(rag_run, "_RAG_AVAILABLE", True)
        monkeypatch.setattr(rag_run, "_execute_queries", _fake_execute_queries_empty)

        rc = rag_run.main(["--rag-queries", str(bundle_dir / "rag_queries.json")])
        assert rc == 0

        updated = json.loads((bundle_dir / "rag_queries.json").read_text(encoding="utf-8"))
        assert updated[0]["execution_status"] == "executed"
        assert updated[0]["execution_reason"] == "no_matches_under_filters"
        assert updated[0]["results"] == []

    def test_rag_unavailable_writes_explicit_status_and_returns_1(self, tmp_path, monkeypatch):
        bundle_dir = tmp_path / "bundle"
        queries = [_make_template_query("profile", "Profile?"), _make_template_query("risk", "Risk?")]
        _write_json(bundle_dir / "rag_queries.json", queries)
        _write_json(bundle_dir / "bundle_manifest.json", _make_bundle_manifest())

        monkeypatch.setattr(rag_run, "_RAG_AVAILABLE", False)

        rc = rag_run.main(["--rag-queries", str(bundle_dir / "rag_queries.json")])
        assert rc == 1  # non-zero because RAG unavailable

        updated = json.loads((bundle_dir / "rag_queries.json").read_text(encoding="utf-8"))
        assert len(updated) == 2
        for entry in updated:
            assert entry["execution_status"] == "not_executed"
            assert entry["execution_reason"] == "rag_unavailable"
            assert entry["results"] == []
            assert "executed_at_utc" in entry

    def test_missing_rag_queries_file_returns_1(self, tmp_path, capsys):
        rc = rag_run.main(["--rag-queries", str(tmp_path / "nonexistent.json")])
        assert rc == 1
        assert "not found" in capsys.readouterr().err

    def test_empty_queries_list_returns_0(self, tmp_path, monkeypatch):
        bundle_dir = tmp_path / "bundle"
        _write_json(bundle_dir / "rag_queries.json", [])
        monkeypatch.setattr(rag_run, "_RAG_AVAILABLE", True)

        rc = rag_run.main(["--rag-queries", str(bundle_dir / "rag_queries.json")])
        assert rc == 0

    def test_uses_explicit_bundle_manifest_path(self, tmp_path, monkeypatch):
        bundle_dir = tmp_path / "bundle"
        manifest_dir = tmp_path / "other"
        queries = [_make_template_query("profile", "Q1")]
        _write_json(bundle_dir / "rag_queries.json", queries)
        custom_manifest = _make_bundle_manifest(collection="custom_coll")
        _write_json(manifest_dir / "bundle_manifest.json", custom_manifest)

        captured_settings: List[Dict] = []

        def _capture_execute(queries, settings):
            captured_settings.append(settings)
            return _fake_execute_queries_with_results(queries, settings)

        monkeypatch.setattr(rag_run, "_RAG_AVAILABLE", True)
        monkeypatch.setattr(rag_run, "_execute_queries", _capture_execute)

        rc = rag_run.main([
            "--rag-queries", str(bundle_dir / "rag_queries.json"),
            "--bundle-manifest", str(manifest_dir / "bundle_manifest.json"),
        ])
        assert rc == 0
        assert captured_settings[0]["collection"] == "custom_coll"

    def test_autodetects_bundle_manifest_in_same_dir(self, tmp_path, monkeypatch):
        bundle_dir = tmp_path / "bundle"
        queries = [_make_template_query("profile", "Q1")]
        _write_json(bundle_dir / "rag_queries.json", queries)
        _write_json(bundle_dir / "bundle_manifest.json", _make_bundle_manifest(collection="auto_coll"))

        captured_settings: List[Dict] = []

        def _capture_execute(queries, settings):
            captured_settings.append(settings)
            return _fake_execute_queries_with_results(queries, settings)

        monkeypatch.setattr(rag_run, "_RAG_AVAILABLE", True)
        monkeypatch.setattr(rag_run, "_execute_queries", _capture_execute)

        rc = rag_run.main(["--rag-queries", str(bundle_dir / "rag_queries.json")])
        assert rc == 0
        assert captured_settings[0]["collection"] == "auto_coll"

    def test_no_bundle_manifest_uses_defaults(self, tmp_path, monkeypatch):
        # No bundle_manifest.json in the directory
        queries = [_make_template_query("profile", "Q1")]
        _write_json(tmp_path / "rag_queries.json", queries)
        # Do NOT write bundle_manifest.json

        captured_settings: List[Dict] = []

        def _capture_execute(queries, settings):
            captured_settings.append(settings)
            return _fake_execute_queries_with_results(queries, settings)

        monkeypatch.setattr(rag_run, "_RAG_AVAILABLE", True)
        monkeypatch.setattr(rag_run, "_execute_queries", _capture_execute)

        rc = rag_run.main(["--rag-queries", str(tmp_path / "rag_queries.json")])
        assert rc == 0
        assert captured_settings[0]["collection"] == rag_run._DEFAULT_COLLECTION

    def test_preserves_existing_fields_in_entries(self, tmp_path, monkeypatch):
        """Existing fields on query entries (label, mode, filters) are preserved."""
        bundle_dir = tmp_path / "bundle"
        queries = [_make_template_query("markets", "Which markets dominate?")]
        _write_json(bundle_dir / "rag_queries.json", queries)
        _write_json(bundle_dir / "bundle_manifest.json", _make_bundle_manifest())

        monkeypatch.setattr(rag_run, "_RAG_AVAILABLE", True)
        monkeypatch.setattr(rag_run, "_execute_queries", _fake_execute_queries_with_results)

        rag_run.main(["--rag-queries", str(bundle_dir / "rag_queries.json")])

        updated = json.loads((bundle_dir / "rag_queries.json").read_text(encoding="utf-8"))
        assert updated[0]["label"] == "markets"
        assert updated[0]["mode"] == "hybrid+rerank"
        assert updated[0]["filters"]["user_slug"] == "testuser"
        assert updated[0]["filters"]["private_only"] is True


# ---------------------------------------------------------------------------
# llm_bundle integration: rag unavailable produces explicit template entries
# ---------------------------------------------------------------------------

class TestLlmBundleRagUnavailable:
    """Verify that llm_bundle._run_rag_queries produces template entries when RAG unavailable."""

    def test_returns_template_entries_not_empty_list(self):
        from tools.cli.llm_bundle import _run_rag_queries, DEFAULT_QUESTIONS, RagSettings

        # Temporarily disable RAG to test the fallback path
        import tools.cli.llm_bundle as lb
        original = lb._RAG_AVAILABLE
        lb._RAG_AVAILABLE = False
        try:
            settings = RagSettings()
            result = _run_rag_queries(DEFAULT_QUESTIONS, settings, "alice", ["kb/users/alice/"])
        finally:
            lb._RAG_AVAILABLE = original

        assert isinstance(result, list)
        assert len(result) == len(DEFAULT_QUESTIONS)
        for entry in result:
            assert entry["execution_status"] == "not_executed"
            assert entry["execution_reason"] == "rag_unavailable"
            assert entry["results"] == []
            assert "question" in entry
            assert "filters" in entry
            assert entry["filters"]["user_slug"] == "alice"
            assert entry["filters"]["prefix_backstop"] == ["kb/users/alice/"]

    def test_executed_path_adds_execution_status(self, monkeypatch):
        """When RAG is available and queries run, each entry has execution_status=executed."""
        from tools.cli.llm_bundle import _run_rag_queries, DEFAULT_QUESTIONS, RagSettings
        import tools.cli.llm_bundle as lb
        from polymarket.rag.embedder import BaseEmbedder
        import numpy as np

        class _FakeEmbedder(BaseEmbedder):
            def __init__(self):
                self.model_name = "fake"
                self.dimension = 4
            def embed_texts(self, texts):
                return np.zeros((len(texts), 4), dtype="float32")

        def _fake_query_index(**kwargs):
            return []  # empty results, but queries ran

        def _fake_embedder(model_name, device):
            return _FakeEmbedder()

        monkeypatch.setattr(lb, "_RAG_AVAILABLE", True)
        monkeypatch.setattr(lb, "SentenceTransformerEmbedder", _fake_embedder)
        monkeypatch.setattr(lb, "CrossEncoderReranker", lambda **kw: None)
        monkeypatch.setattr(lb, "query_index", _fake_query_index)

        settings = RagSettings()
        result = _run_rag_queries(DEFAULT_QUESTIONS[:1], settings, "bob", [])

        assert result[0]["execution_status"] == "executed"
        assert result[0]["execution_reason"] == "no_matches_under_filters"
        assert result[0]["results"] == []
