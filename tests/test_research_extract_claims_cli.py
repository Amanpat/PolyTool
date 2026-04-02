"""Offline smoke tests for the research-extract-claims CLI entrypoint.

All tests use a temporary SQLite file via tmp_path or an empty store.
No network calls, no LLM calls.

Tests cover:
- --help exits 0
- Missing required args exits 2 (argparse error)
- --doc-id with nonexistent ID returns 0 (processes 0 claims, no error)
- --all on empty store returns 0 with "No source documents" message
- --all --json output shape (keys present, total_claims >= 1)
- --all --dry-run does not write any claims
- --all --dry-run --json output shape (dry_run: true, total_claims_estimate >= 1)
"""

from __future__ import annotations

import hashlib
import json
import sys

import pytest

from tools.cli.research_extract_claims import main
from packages.polymarket.rag.knowledge_store import KnowledgeStore


# ---------------------------------------------------------------------------
# Fixture data
# ---------------------------------------------------------------------------

FIXTURE_MARKDOWN = """\
## Introduction

The algorithm detects strong momentum patterns in market order flow signals.
Statistical evidence confirms that momentum patterns generate consistent market signals.
The system processes thousands of market data points every second continuously.

## Risk Assessment

Market makers should maintain adequate inventory buffers to avoid adverse selection.
Best practice recommends a minimum spread of 20 basis points for liquid markets.
"""


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _create_store_with_doc(tmp_path, body: str = FIXTURE_MARKDOWN) -> str:
    """Create a SQLite KnowledgeStore with one registered document, return db_path str."""
    db_path = tmp_path / "test_kb.sqlite3"
    store = KnowledgeStore(str(db_path))
    content_hash = hashlib.sha256(body.encode()).hexdigest()
    fpath = tmp_path / "doc.md"
    fpath.write_text(body, encoding="utf-8")
    store.add_source_document(
        title="Test Doc",
        source_url=f"file://{fpath.as_posix()}",
        source_family="blog",
        content_hash=content_hash,
        chunk_count=0,
        confidence_tier="PRACTITIONER",
        metadata_json="{}",
    )
    store.close()
    return str(db_path)


def _create_empty_store(tmp_path) -> str:
    """Create an empty SQLite KnowledgeStore, return db_path str."""
    db_path = tmp_path / "empty_kb.sqlite3"
    store = KnowledgeStore(str(db_path))
    store.close()
    return str(db_path)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestResearchExtractClaimsCLI:
    def test_main_help_returns_zero(self):
        """--help exits with code 0."""
        with pytest.raises(SystemExit) as exc_info:
            main(["--help"])
        assert exc_info.value.code == 0

    def test_main_no_args_returns_error(self):
        """Missing required --doc-id or --all exits with code 2 (argparse error)."""
        with pytest.raises(SystemExit) as exc_info:
            main([])
        assert exc_info.value.code == 2

    def test_main_doc_id_not_found(self, tmp_path):
        """--doc-id with nonexistent ID processes 0 claims, returns 0."""
        db_path = _create_empty_store(tmp_path)
        ret = main(["--doc-id", "nonexistent-doc-id-xyz", "--db-path", db_path])
        assert ret == 0

    def test_main_all_empty_store(self, tmp_path, capsys):
        """--all on empty store prints 'No source documents' and returns 0."""
        db_path = _create_empty_store(tmp_path)
        ret = main(["--all", "--db-path", db_path])
        assert ret == 0
        captured = capsys.readouterr()
        assert "No source documents" in captured.out

    def test_main_all_json_output_shape(self, tmp_path, capsys):
        """--all --json on a store with one doc outputs valid JSON with expected keys."""
        db_path = _create_store_with_doc(tmp_path)
        ret = main(["--all", "--json", "--db-path", db_path])
        assert ret == 0
        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert "documents_processed" in output
        assert "total_claims" in output
        assert "total_relations" in output
        assert "per_doc_results" in output
        assert output["total_claims"] >= 1

    def test_main_dry_run_does_not_write(self, tmp_path):
        """--all --dry-run does not write any claims to the store."""
        db_path = _create_store_with_doc(tmp_path)
        ret = main(["--all", "--dry-run", "--db-path", db_path])
        assert ret == 0

        # Re-open store and verify no claims were written
        store = KnowledgeStore(db_path)
        claims = store.query_claims(apply_freshness=False)
        store.close()
        assert len(claims) == 0

    def test_main_all_json_dry_run(self, tmp_path, capsys):
        """--all --json --dry-run outputs JSON with dry_run=true and total_claims_estimate >= 1."""
        db_path = _create_store_with_doc(tmp_path)
        ret = main(["--all", "--dry-run", "--json", "--db-path", db_path])
        assert ret == 0
        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert output.get("dry_run") is True
        assert "total_claims_estimate" in output
        assert output["total_claims_estimate"] >= 1
