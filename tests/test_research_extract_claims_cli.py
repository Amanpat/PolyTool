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

Frontmatter-stripping tests (Tests A-D):
- Test A: YAML frontmatter lines do NOT appear as claim_text in extracted claims
- Test B: Body content after the closing --- IS extracted as a claim
- Test C: Docs with no frontmatter are extracted the same as before
- Test D: Docs with opening --- but no closing --- (malformed) are handled safely
"""

from __future__ import annotations

import hashlib
import json
import sys

import pytest

from tools.cli.research_extract_claims import main
from packages.polymarket.rag.knowledge_store import KnowledgeStore
from packages.research.ingestion.claim_extractor import (
    extract_claims_from_document,
    _strip_yaml_frontmatter,
)


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


# ---------------------------------------------------------------------------
# Frontmatter-stripping unit tests (Tests A-D)
# ---------------------------------------------------------------------------

# YAML frontmatter keys that must NEVER appear in claim_text
_FRONTMATTER_KEY_PREFIXES = (
    "title:",
    "freshness_tier:",
    "confidence_tier:",
    "validation_status:",
    "source_family:",
    "source_quality_caution:",
)

FIXTURE_WITH_FRONTMATTER = """\
---
title: "Polymarket Fee Structure (April 2026)"
freshness_tier: CURRENT
confidence_tier: PRACTITIONER
validation_status: UNTESTED
source_family: external_knowledge
source_quality_caution: >
  Derived from corrected internal notes and secondary packet references.
---

# Polymarket Fee Structure

Polymarket uses the formula fee equals C times feeRate times p times one minus p for all taker fills.
The feeRate varies by category: crypto markets have a higher rate of 0.072 compared to sports markets at 0.03.
Makers do not pay per-fill fees and receive daily rebates funded from a share of accumulated taker fees.
"""

FIXTURE_BODY_ONLY = """\
# Market Analysis

The algorithm detects strong momentum patterns in market order flow signals over time.
Statistical evidence confirms that momentum patterns generate consistent market signals.
Market makers should maintain adequate inventory buffers to avoid adverse selection risk.
"""

FIXTURE_MALFORMED_FRONTMATTER = """\
---
title: "Malformed Doc Without Closing Fence"
freshness_tier: CURRENT

This line starts inside the frontmatter but there is no closing fence within 200 lines.
The body should be returned unchanged to avoid data loss when frontmatter is malformed.
Real content sentences appear here so that extraction still finds something useful.
Extraction should proceed normally and include these sentences as candidate claims.
"""


def _create_store_with_file_doc(tmp_path, body: str, title: str = "Test Doc") -> tuple:
    """Create an in-memory KnowledgeStore with a file:// source_url doc.

    Returns (store, doc_id) — caller is responsible for closing the store.
    """
    store = KnowledgeStore(":memory:")
    fpath = tmp_path / "doc.md"
    fpath.write_text(body, encoding="utf-8")
    content_hash = hashlib.sha256(body.encode()).hexdigest()
    doc_id = store.add_source_document(
        title=title,
        source_url=f"file://{fpath.as_posix()}",
        source_family="external_knowledge",
        content_hash=content_hash,
        chunk_count=0,
        confidence_tier="PRACTITIONER",
        metadata_json="{}",
    )
    return store, doc_id


class TestFrontmatterStripping:
    """Tests A-D for _strip_yaml_frontmatter and claim extraction behavior."""

    # ------------------------------------------------------------------
    # Test A: Frontmatter key-value lines must NOT appear as claim_text
    # ------------------------------------------------------------------

    def test_a_frontmatter_excluded_from_claims(self, tmp_path):
        """Test A: No claim_text starts with a YAML frontmatter key line after extraction."""
        store, doc_id = _create_store_with_file_doc(tmp_path, FIXTURE_WITH_FRONTMATTER)
        claim_ids = extract_claims_from_document(store, doc_id)
        claims = [store.get_claim(cid) for cid in claim_ids]
        store.close()

        for claim in claims:
            if claim is None:
                continue
            text = claim["claim_text"]
            for prefix in _FRONTMATTER_KEY_PREFIXES:
                assert not text.strip().startswith(prefix), (
                    f"Frontmatter key line leaked into claim_text: {text!r}"
                )

    # ------------------------------------------------------------------
    # Test B: Body content after closing --- IS extracted as a claim
    # ------------------------------------------------------------------

    def test_b_body_claims_still_extracted(self, tmp_path):
        """Test B: Body sentence after the closing --- is extracted as a claim."""
        store, doc_id = _create_store_with_file_doc(tmp_path, FIXTURE_WITH_FRONTMATTER)
        claim_ids = extract_claims_from_document(store, doc_id)
        claims = [store.get_claim(cid) for cid in claim_ids]
        store.close()

        # At least one claim should reference body content (fee formula or rates)
        body_keywords = ("feeRate", "taker", "makers", "0.072", "fee equals")
        found_body_claim = any(
            any(kw.lower() in (c["claim_text"] or "").lower() for kw in body_keywords)
            for c in claims
            if c is not None
        )
        assert found_body_claim, (
            "No body claim found — frontmatter stripping may have removed body content too. "
            f"Claims extracted: {[c['claim_text'] for c in claims if c]}"
        )
        assert len(claim_ids) >= 1, "Expected at least 1 claim from the body section."

    # ------------------------------------------------------------------
    # Test C: No-frontmatter docs are unaffected (claim count matches)
    # ------------------------------------------------------------------

    def test_c_no_frontmatter_doc_unaffected(self, tmp_path):
        """Test C: A doc with no YAML frontmatter is extracted the same as before."""
        # Run extraction on body-only fixture twice using different filenames;
        # compare claim counts (deterministic extractor must produce the same count).
        fpath1 = tmp_path / "doc_run1.md"
        fpath1.write_text(FIXTURE_BODY_ONLY, encoding="utf-8")
        store1 = KnowledgeStore(":memory:")
        doc_id1 = store1.add_source_document(
            title="Body Only Run 1",
            source_url=f"file://{fpath1.as_posix()}",
            source_family="blog",
            content_hash=hashlib.sha256(FIXTURE_BODY_ONLY.encode()).hexdigest(),
            chunk_count=0,
            confidence_tier="PRACTITIONER",
            metadata_json="{}",
        )
        ids1 = extract_claims_from_document(store1, doc_id1)
        store1.close()

        fpath2 = tmp_path / "doc_run2.md"
        fpath2.write_text(FIXTURE_BODY_ONLY, encoding="utf-8")
        store2 = KnowledgeStore(":memory:")
        doc_id2 = store2.add_source_document(
            title="Body Only Run 2",
            source_url=f"file://{fpath2.as_posix()}",
            source_family="blog",
            content_hash=hashlib.sha256(FIXTURE_BODY_ONLY.encode()).hexdigest(),
            chunk_count=0,
            confidence_tier="PRACTITIONER",
            metadata_json="{}",
        )
        ids2 = extract_claims_from_document(store2, doc_id2)
        store2.close()

        # Deterministic extractor: same input yields same output count
        assert len(ids1) == len(ids2), (
            f"Claim count inconsistent for body-only doc: {len(ids1)} vs {len(ids2)}"
        )
        assert len(ids1) >= 1, "Expected at least 1 claim from body-only fixture."

    # ------------------------------------------------------------------
    # Test D: Malformed frontmatter (no closing ---) is handled safely
    # ------------------------------------------------------------------

    def test_d_malformed_frontmatter_safe(self, tmp_path):
        """Test D: A doc starting with --- but no closing --- is left unchanged (no data loss)."""
        # The malformed fixture has real content sentences; extraction should find them
        # (body is unchanged, so heuristic extractor still sees the full text)
        store, doc_id = _create_store_with_file_doc(tmp_path, FIXTURE_MALFORMED_FRONTMATTER)
        claim_ids = extract_claims_from_document(store, doc_id)
        store.close()

        # Content should still be extractable; the body is NOT stripped
        assert len(claim_ids) >= 1, (
            "Malformed-frontmatter doc should still yield claims (body unchanged). "
            "Check that _strip_yaml_frontmatter does not strip without a valid closing ---."
        )

    # ------------------------------------------------------------------
    # Unit tests for _strip_yaml_frontmatter directly
    # ------------------------------------------------------------------

    def test_strip_removes_valid_frontmatter(self):
        """_strip_yaml_frontmatter removes a well-formed YAML block."""
        body = "---\ntitle: Foo\nconfidence_tier: PRACTITIONER\n---\n\nReal content here."
        result = _strip_yaml_frontmatter(body)
        assert "title:" not in result
        assert "confidence_tier:" not in result
        assert "Real content here." in result

    def test_strip_handles_crlf(self):
        """_strip_yaml_frontmatter works with \\r\\n line endings."""
        body = "---\r\ntitle: Foo\r\n---\r\n\r\nReal content here."
        result = _strip_yaml_frontmatter(body)
        assert "title:" not in result
        assert "Real content here." in result

    def test_strip_leaves_no_frontmatter_unchanged(self):
        """_strip_yaml_frontmatter returns body unchanged when no frontmatter present."""
        body = "# Just a heading\n\nSome content here."
        result = _strip_yaml_frontmatter(body)
        assert result == body

    def test_strip_leaves_malformed_unchanged(self):
        """_strip_yaml_frontmatter returns body unchanged when no closing --- found."""
        body = "---\ntitle: Foo\n\nNo closing fence in this document ever."
        result = _strip_yaml_frontmatter(body)
        # Should be returned unchanged (no closing fence found within 200 lines)
        assert "title: Foo" in result
        assert "No closing fence" in result
