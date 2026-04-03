"""Offline tests for research-bridge CLI and MCP KnowledgeStore routing.

Covers:
- TestBridgeCLI_RegisterHypothesis: register-hypothesis subcommand
- TestBridgeCLI_RecordOutcome: record-outcome subcommand
- TestMCPKnowledgeStoreRouting: polymarket_rag_query KS routing
"""

from __future__ import annotations

import json
import sys
import io
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run_bridge_main(argv: list[str], capsys=None) -> tuple[int, str]:
    """Run research_bridge.main(argv) and capture stdout output.

    Returns (exit_code, stdout_text).
    """
    from tools.cli import research_bridge

    buf = io.StringIO()
    try:
        with patch("sys.stdout", buf):
            rc = research_bridge.main(argv)
    except SystemExit as exc:
        rc = int(exc.code) if exc.code is not None else 0
    return rc, buf.getvalue()


# ---------------------------------------------------------------------------
# TestBridgeCLI_RegisterHypothesis
# ---------------------------------------------------------------------------

class TestBridgeCLI_RegisterHypothesis:
    """Tests tagged bridge_cli — register-hypothesis subcommand."""

    def test_register_valid_candidate(self, tmp_path):
        """Valid candidate via --candidate-json file: exits 0, prints hypothesis_id."""
        candidate = {
            "name": "test_hypothesis_v1",
            "hypothesis_text": "BTC momentum predicts direction",
            "evidence_doc_ids": ["doc_abc"],
        }
        cand_file = tmp_path / "cand.json"
        cand_file.write_text(json.dumps(candidate), encoding="utf-8")
        reg_path = tmp_path / "reg.jsonl"

        rc, out = _run_bridge_main([
            "register-hypothesis",
            "--candidate-json", str(cand_file),
            "--registry-path", str(reg_path),
        ])

        assert rc == 0, f"expected exit 0, got {rc}; output: {out}"
        result = json.loads(out.strip())
        assert result["hypothesis_id"].startswith("hyp_"), result
        assert reg_path.exists(), "registry file should be created"
        events = [json.loads(line) for line in reg_path.read_text().splitlines() if line.strip()]
        assert len(events) == 1
        assert events[0]["source"]["origin"] == "research_bridge"

    def test_register_json_string(self, tmp_path):
        """Valid candidate via --candidate-json-string: exits 0, prints hypothesis_id."""
        candidate = {
            "name": "inline_hypothesis_v1",
            "hypothesis_text": "Test from string input",
        }
        reg_path = tmp_path / "reg.jsonl"

        rc, out = _run_bridge_main([
            "register-hypothesis",
            "--candidate-json-string", json.dumps(candidate),
            "--registry-path", str(reg_path),
        ])

        assert rc == 0, f"expected exit 0, got {rc}; output: {out}"
        result = json.loads(out.strip())
        assert result["hypothesis_id"].startswith("hyp_")
        assert result["candidate_name"] == "inline_hypothesis_v1"

    def test_register_missing_name_key(self, tmp_path):
        """Candidate JSON without 'name' key: exits 1."""
        candidate = {"hypothesis_text": "no name here"}
        cand_file = tmp_path / "no_name.json"
        cand_file.write_text(json.dumps(candidate), encoding="utf-8")
        reg_path = tmp_path / "reg.jsonl"

        rc, _out = _run_bridge_main([
            "register-hypothesis",
            "--candidate-json", str(cand_file),
            "--registry-path", str(reg_path),
        ])

        assert rc == 1, "should exit 1 when 'name' key is missing"

    def test_register_no_input(self, tmp_path):
        """No --candidate-json and no --candidate-json-string: exits 1."""
        reg_path = tmp_path / "reg.jsonl"

        rc, _out = _run_bridge_main([
            "register-hypothesis",
            "--registry-path", str(reg_path),
        ])

        assert rc == 1, "should exit 1 when no candidate input provided"

    def test_register_evidence_doc_ids_preserved(self, tmp_path):
        """evidence_doc_ids must be preserved in the JSONL registry event."""
        candidate = {
            "name": "evidence_test_v1",
            "hypothesis_text": "Evidence chain test",
            "evidence_doc_ids": ["doc_abc", "doc_def"],
        }
        cand_file = tmp_path / "ev_cand.json"
        cand_file.write_text(json.dumps(candidate), encoding="utf-8")
        reg_path = tmp_path / "reg.jsonl"

        rc, out = _run_bridge_main([
            "register-hypothesis",
            "--candidate-json", str(cand_file),
            "--registry-path", str(reg_path),
        ])

        assert rc == 0
        events = [json.loads(line) for line in reg_path.read_text().splitlines() if line.strip()]
        assert len(events) == 1
        assert events[0]["source"]["evidence_doc_ids"] == ["doc_abc", "doc_def"]


# ---------------------------------------------------------------------------
# TestBridgeCLI_RecordOutcome
# ---------------------------------------------------------------------------

class TestBridgeCLI_RecordOutcome:
    """Tests tagged bridge_cli — record-outcome subcommand."""

    def _make_ks_with_claim(self):
        """Create an in-memory KnowledgeStore with one claim; return (ks, claim_id)."""
        from packages.polymarket.rag.knowledge_store import KnowledgeStore
        ks = KnowledgeStore(":memory:")
        doc_id = ks.add_source_document(
            title="Test source",
            source_url="internal://test",
            source_family="wallet_analysis",
        )
        claim_id = ks.add_claim(
            claim_text="Test claim for validation",
            claim_type="empirical",
            confidence=0.8,
            trust_tier="silver",
            actor="test_agent",
            source_document_id=doc_id,
        )
        return ks, claim_id

    def test_record_outcome_confirmed(self, tmp_path):
        """Valid record-outcome with 'confirmed': exits 0, claims_updated=1."""
        ks, claim_id = self._make_ks_with_claim()

        # Patch KnowledgeStore constructor to return our in-memory instance
        with patch(
            "tools.cli.research_bridge.KnowledgeStore",
            return_value=ks,
        ):
            rc, out = _run_bridge_main([
                "record-outcome",
                "--hypothesis-id", "hyp_test",
                "--claim-ids", claim_id,
                "--outcome", "confirmed",
                "--reason", "replay positive result",
            ])

        assert rc == 0, f"expected exit 0, got {rc}; output: {out}"
        result = json.loads(out.strip())
        assert result["claims_updated"] == 1
        assert result["validation_status"] == "CONSISTENT_WITH_RESULTS"

    def test_record_outcome_invalid(self, tmp_path):
        """Invalid --outcome value: exits non-zero (argparse exits 2 for invalid choice)."""
        rc, _out = _run_bridge_main([
            "record-outcome",
            "--hypothesis-id", "hyp_test",
            "--claim-ids", "claim_abc",
            "--outcome", "unknown_value",
            "--reason", "test",
        ])

        assert rc != 0, "should exit non-zero for invalid outcome"

    def test_record_outcome_empty_claim_ids(self, tmp_path):
        """Empty --claim-ids: exits 0 with claims_updated=0."""
        from packages.polymarket.rag.knowledge_store import KnowledgeStore
        ks = KnowledgeStore(":memory:")

        with patch(
            "tools.cli.research_bridge.KnowledgeStore",
            return_value=ks,
        ):
            rc, out = _run_bridge_main([
                "record-outcome",
                "--hypothesis-id", "hyp_empty",
                "--claim-ids", "",
                "--outcome", "inconclusive",
                "--reason", "no claims to update",
            ])

        assert rc == 0, f"expected exit 0, got {rc}; output: {out}"
        result = json.loads(out.strip())
        assert result["claims_updated"] == 0


# ---------------------------------------------------------------------------
# TestMCPKnowledgeStoreRouting
# ---------------------------------------------------------------------------

class TestMCPKnowledgeStoreRouting:
    """Tests tagged mcp — polymarket_rag_query KS routing.

    Since polymarket.rag imports are lazy (inside the function body to avoid
    breaking the MCP subprocess), we patch the underlying modules directly.
    """

    @pytest.fixture(autouse=True)
    def _import_mcp_server(self):
        """Ensure mcp_server is imported and packages/ is on sys.path for patching."""
        import os
        import sys
        # packages/ must be on sys.path so patch("polymarket.rag.…") can resolve
        packages_dir = os.path.normpath(
            os.path.join(os.path.dirname(__file__), "..", "packages")
        )
        if packages_dir not in sys.path:
            sys.path.insert(0, packages_dir)
        # mcp SDK is required to import mcp_server; skip gracefully if absent
        try:
            import tools.cli.mcp_server  # noqa: F401
        except ImportError as exc:
            pytest.skip(f"mcp_server not importable: {exc}")

    def _make_fake_embedder(self):
        embedder = MagicMock()
        embedder.encode.return_value = [[0.1] * 384]
        return embedder

    def test_mcp_ks_active_when_db_exists(self):
        """When DEFAULT_KNOWLEDGE_DB_PATH exists, hybrid=True and ks_path is passed."""
        import tools.cli.mcp_server as mcp_mod
        captured_kwargs = {}

        def fake_query_index(**kwargs):
            captured_kwargs.update(kwargs)
            return []

        fake_embedder = self._make_fake_embedder()

        # Patch at the source module level (lazy imports inside the function)
        with patch("polymarket.rag.embedder.SentenceTransformerEmbedder", return_value=fake_embedder), \
             patch("polymarket.rag.query.query_index", side_effect=fake_query_index), \
             patch("polymarket.rag.knowledge_store.DEFAULT_KNOWLEDGE_DB_PATH") as mock_ks_path:
            mock_ks_path.exists.return_value = True

            raw = mcp_mod.polymarket_rag_query("test question")

        result = json.loads(raw)
        assert result["ks_active"] is True
        assert captured_kwargs.get("hybrid") is True
        assert captured_kwargs.get("knowledge_store_path") is not None

    def test_mcp_ks_inactive_when_db_absent(self):
        """When DEFAULT_KNOWLEDGE_DB_PATH does not exist, ks_active=False, no error."""
        import tools.cli.mcp_server as mcp_mod
        captured_kwargs = {}

        def fake_query_index(**kwargs):
            captured_kwargs.update(kwargs)
            return []

        fake_embedder = self._make_fake_embedder()

        with patch("polymarket.rag.embedder.SentenceTransformerEmbedder", return_value=fake_embedder), \
             patch("polymarket.rag.query.query_index", side_effect=fake_query_index), \
             patch("polymarket.rag.knowledge_store.DEFAULT_KNOWLEDGE_DB_PATH") as mock_ks_path:
            mock_ks_path.exists.return_value = False

            raw = mcp_mod.polymarket_rag_query("test question")

        result = json.loads(raw)
        assert result["ks_active"] is False
        # When KS absent, knowledge_store_path should NOT be in kwargs or should be None
        ks_path = captured_kwargs.get("knowledge_store_path")
        assert ks_path is None, f"expected no KS path, got {ks_path}"

    def test_mcp_result_structure_unchanged(self):
        """Both ks_active=True and False cases return JSON with required keys."""
        import tools.cli.mcp_server as mcp_mod
        required_keys = {"success", "question", "results", "count", "ks_active"}

        fake_embedder = self._make_fake_embedder()

        for ks_exists in (True, False):
            with patch("polymarket.rag.embedder.SentenceTransformerEmbedder", return_value=fake_embedder), \
                 patch("polymarket.rag.query.query_index", return_value=[]), \
                 patch("polymarket.rag.knowledge_store.DEFAULT_KNOWLEDGE_DB_PATH") as mock_ks_path:
                mock_ks_path.exists.return_value = ks_exists

                raw = mcp_mod.polymarket_rag_query("test question")

            result = json.loads(raw)
            missing = required_keys - set(result.keys())
            assert not missing, f"Missing keys when ks_exists={ks_exists}: {missing}"
            assert result["success"] is True
            assert result["question"] == "test question"
            assert isinstance(result["results"], list)
            assert result["count"] == 0
