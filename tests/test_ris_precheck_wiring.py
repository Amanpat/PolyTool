"""Offline tests for RIS v1 precheck wiring to KnowledgeStore and freshness.

Task 1: Wire find_contradictions() and check_stale_evidence() to KnowledgeStore and freshness.
Task 2: Enrich precheck ledger schema (precheck_id, reason_code, evidence_gap, review_horizon).

All tests are fully offline — no network, no LLM, no Chroma, :memory: SQLite only.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_ks():
    """Create a fresh in-memory KnowledgeStore."""
    from packages.polymarket.rag.knowledge_store import KnowledgeStore
    return KnowledgeStore(":memory:")


def _make_result(recommendation="CAUTION", idea="test idea", contradicting=None, stale_warning=False):
    """Create a minimal PrecheckResult for testing."""
    from packages.research.synthesis.precheck import PrecheckResult
    return PrecheckResult(
        recommendation=recommendation,
        idea=idea,
        supporting_evidence=["Some supporting evidence"],
        contradicting_evidence=contradicting or [],
        risk_factors=["Some risk factor"],
        timestamp="2026-04-01T00:00:00+00:00",
        provider_used="manual",
        stale_warning=stale_warning,
    )


# ---------------------------------------------------------------------------
# Task 1: find_contradictions() wiring
# ---------------------------------------------------------------------------

class TestFindContradictions:
    def test_no_knowledge_store_returns_empty(self):
        """Backward compat: no ks = empty list."""
        from packages.research.synthesis.precheck import find_contradictions
        result = find_contradictions("any idea")
        assert result == []

    def test_none_knowledge_store_returns_empty(self):
        """Explicit None ks = empty list."""
        from packages.research.synthesis.precheck import find_contradictions
        result = find_contradictions("any idea", knowledge_store=None)
        assert result == []

    def test_empty_knowledge_store_returns_empty(self):
        """KS with no claims returns empty list."""
        from packages.research.synthesis.precheck import find_contradictions
        ks = _make_ks()
        result = find_contradictions("any idea", knowledge_store=ks)
        assert result == []
        ks.close()

    def test_claims_with_no_relations_returns_empty(self):
        """Claims exist but no CONTRADICTS relations -> empty list."""
        from packages.research.synthesis.precheck import find_contradictions
        ks = _make_ks()
        ks.add_claim(
            claim_text="Market liquidity is high on 5m BTC.",
            claim_type="empirical",
            confidence=0.8,
            trust_tier="high",
            actor="test",
            created_at="2026-04-01T00:00:00+00:00",
        )
        result = find_contradictions("any idea", knowledge_store=ks)
        assert result == []
        ks.close()

    def test_claims_with_contradicts_relation_returned(self):
        """Claims involved in CONTRADICTS relations are returned."""
        from packages.research.synthesis.precheck import find_contradictions
        ks = _make_ks()
        cid1 = ks.add_claim(
            claim_text="Momentum signals are reliable for BTC.",
            claim_type="empirical",
            confidence=0.8,
            trust_tier="high",
            actor="test",
            created_at="2026-04-01T00:00:00+00:00",
        )
        cid2 = ks.add_claim(
            claim_text="BTC prices are random walk, no momentum.",
            claim_type="empirical",
            confidence=0.7,
            trust_tier="medium",
            actor="test",
            created_at="2026-04-01T00:00:00+00:00",
        )
        ks.add_relation(cid1, cid2, "CONTRADICTS")
        result = find_contradictions("momentum strategy", knowledge_store=ks)
        # Both claims involved in CONTRADICTS should be returned
        assert len(result) >= 1
        all_texts = set(result)
        assert "Momentum signals are reliable for BTC." in all_texts or \
               "BTC prices are random walk, no momentum." in all_texts
        ks.close()

    def test_only_contradicts_relations_included_not_supports(self):
        """SUPPORTS relations do NOT cause inclusion in results."""
        from packages.research.synthesis.precheck import find_contradictions
        ks = _make_ks()
        cid1 = ks.add_claim(
            claim_text="Coin A is correlated with Coin B.",
            claim_type="empirical",
            confidence=0.9,
            trust_tier="high",
            actor="test",
            created_at="2026-04-01T00:00:00+00:00",
        )
        cid2 = ks.add_claim(
            claim_text="Trading correlated coins has alpha.",
            claim_type="empirical",
            confidence=0.7,
            trust_tier="medium",
            actor="test",
            created_at="2026-04-01T00:00:00+00:00",
        )
        # Only a SUPPORTS relation — no CONTRADICTS
        ks.add_relation(cid1, cid2, "SUPPORTS")
        result = find_contradictions("correlation trading", knowledge_store=ks)
        assert result == []
        ks.close()

    def test_only_contradicts_relations_included_not_extends(self):
        """EXTENDS relations do NOT cause inclusion in results."""
        from packages.research.synthesis.precheck import find_contradictions
        ks = _make_ks()
        cid1 = ks.add_claim(
            claim_text="Base claim about market dynamics.",
            claim_type="empirical",
            confidence=0.8,
            trust_tier="high",
            actor="test",
            created_at="2026-04-01T00:00:00+00:00",
        )
        cid2 = ks.add_claim(
            claim_text="Extended claim building on base.",
            claim_type="empirical",
            confidence=0.6,
            trust_tier="medium",
            actor="test",
            created_at="2026-04-01T00:00:00+00:00",
        )
        ks.add_relation(cid1, cid2, "EXTENDS")
        result = find_contradictions("market dynamics idea", knowledge_store=ks)
        assert result == []
        ks.close()

    def test_returns_list_of_strings(self):
        """Return type is list[str], not list of dicts."""
        from packages.research.synthesis.precheck import find_contradictions
        ks = _make_ks()
        cid1 = ks.add_claim(
            claim_text="Claim A text here.",
            claim_type="empirical",
            confidence=0.8,
            trust_tier="high",
            actor="test",
            created_at="2026-04-01T00:00:00+00:00",
        )
        cid2 = ks.add_claim(
            claim_text="Claim B contradicts claim A.",
            claim_type="empirical",
            confidence=0.7,
            trust_tier="medium",
            actor="test",
            created_at="2026-04-01T00:00:00+00:00",
        )
        ks.add_relation(cid1, cid2, "CONTRADICTS")
        result = find_contradictions("idea", knowledge_store=ks)
        for item in result:
            assert isinstance(item, str), f"Expected str, got {type(item)}"
        ks.close()


# ---------------------------------------------------------------------------
# Task 1: check_stale_evidence() wiring
# ---------------------------------------------------------------------------

class TestCheckStaleEvidence:
    def test_no_knowledge_store_returns_unchanged(self):
        """Backward compat: no ks = result returned unchanged."""
        from packages.research.synthesis.precheck import check_stale_evidence
        result = _make_result()
        result.stale_warning = False
        out = check_stale_evidence(result)
        assert out.stale_warning is False

    def test_none_knowledge_store_returns_unchanged(self):
        """Explicit None ks = result returned unchanged."""
        from packages.research.synthesis.precheck import check_stale_evidence
        result = _make_result()
        out = check_stale_evidence(result, knowledge_store=None)
        assert out is result or out.stale_warning == result.stale_warning

    def test_empty_knowledge_store_returns_unchanged(self):
        """KS with no source docs -> no penalty, result unchanged."""
        from packages.research.synthesis.precheck import check_stale_evidence
        ks = _make_ks()
        result = _make_result()
        out = check_stale_evidence(result, knowledge_store=ks)
        assert out.stale_warning is False
        ks.close()

    def test_all_stale_docs_sets_stale_warning(self):
        """When all source docs have freshness_modifier < 0.5, stale_warning=True."""
        from packages.research.synthesis.precheck import check_stale_evidence
        from packages.polymarket.rag.freshness import compute_freshness_modifier
        ks = _make_ks()
        # Use news family (half_life=3 months) with a very old published date to force staleness
        # A document published 24 months ago with 3-month half-life:
        # modifier = 2^(-24/3) = 2^(-8) = 0.0039 -> clamped to floor 0.3
        # Actually 0.3 < 0.5, so stale_warning should be set
        old_date = (datetime.now(timezone.utc) - timedelta(days=730)).isoformat()
        ks.add_source_document(
            title="Old news article",
            source_url="http://example.com/old",
            source_family="news",
            content_hash="abc123",
            chunk_count=1,
            published_at=old_date,
            ingested_at=old_date,
            confidence_tier="medium",
            metadata_json="{}",
        )
        result = _make_result()
        out = check_stale_evidence(result, knowledge_store=ks)
        assert out.stale_warning is True
        ks.close()

    def test_fresh_doc_preserves_stale_warning_false(self):
        """When at least one fresh doc (modifier >= 0.5), stale_warning stays False."""
        from packages.research.synthesis.precheck import check_stale_evidence
        ks = _make_ks()
        # A document published 1 day ago with news family (half_life=3 months):
        # modifier = 2^(-0.033/3) ≈ 0.999 -> definitely >= 0.5
        fresh_date = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        ks.add_source_document(
            title="Fresh news article",
            source_url="http://example.com/fresh",
            source_family="news",
            content_hash="fresh123",
            chunk_count=1,
            published_at=fresh_date,
            ingested_at=fresh_date,
            confidence_tier="high",
            metadata_json="{}",
        )
        result = _make_result()
        out = check_stale_evidence(result, knowledge_store=ks)
        assert out.stale_warning is False
        ks.close()

    def test_mixed_docs_one_fresh_keeps_stale_false(self):
        """One stale + one fresh -> not all stale -> stale_warning=False."""
        from packages.research.synthesis.precheck import check_stale_evidence
        ks = _make_ks()
        old_date = (datetime.now(timezone.utc) - timedelta(days=730)).isoformat()
        fresh_date = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        ks.add_source_document(
            title="Old article",
            source_url="http://example.com/old2",
            source_family="news",
            content_hash="old456",
            chunk_count=1,
            published_at=old_date,
            ingested_at=old_date,
            confidence_tier="medium",
            metadata_json="{}",
        )
        ks.add_source_document(
            title="Fresh article",
            source_url="http://example.com/fresh2",
            source_family="news",
            content_hash="fresh456",
            chunk_count=1,
            published_at=fresh_date,
            ingested_at=fresh_date,
            confidence_tier="high",
            metadata_json="{}",
        )
        result = _make_result()
        out = check_stale_evidence(result, knowledge_store=ks)
        assert out.stale_warning is False
        ks.close()

    def test_stale_result_preserves_all_other_fields(self):
        """When stale_warning is set, other PrecheckResult fields are unchanged."""
        from packages.research.synthesis.precheck import check_stale_evidence
        ks = _make_ks()
        old_date = (datetime.now(timezone.utc) - timedelta(days=730)).isoformat()
        ks.add_source_document(
            title="Old source",
            source_url="http://example.com/old3",
            source_family="news",
            content_hash="old789",
            chunk_count=1,
            published_at=old_date,
            ingested_at=old_date,
            confidence_tier="low",
            metadata_json="{}",
        )
        result = _make_result(recommendation="GO", idea="preserve fields idea")
        out = check_stale_evidence(result, knowledge_store=ks)
        assert out.stale_warning is True
        assert out.recommendation == "GO"
        assert out.idea == "preserve fields idea"
        assert out.supporting_evidence == result.supporting_evidence
        assert out.risk_factors == result.risk_factors
        ks.close()


# ---------------------------------------------------------------------------
# Task 1: run_precheck() wiring
# ---------------------------------------------------------------------------

class TestRunPrecheckWiring:
    def test_run_precheck_with_knowledge_store_merges_contradictions(self):
        """Contradictions from KS are merged into result.contradicting_evidence."""
        from packages.research.synthesis.precheck import run_precheck
        ks = _make_ks()
        cid1 = ks.add_claim(
            claim_text="Directional momentum fails in low-volatility regimes.",
            claim_type="empirical",
            confidence=0.8,
            trust_tier="high",
            actor="test",
            created_at="2026-04-01T00:00:00+00:00",
        )
        cid2 = ks.add_claim(
            claim_text="BTC shows strong momentum in high-volatility periods.",
            claim_type="empirical",
            confidence=0.7,
            trust_tier="medium",
            actor="test",
            created_at="2026-04-01T00:00:00+00:00",
        )
        ks.add_relation(cid1, cid2, "CONTRADICTS")
        result = run_precheck(
            "directional momentum on BTC 5m markets",
            provider_name="manual",
            ledger_path=None,
            knowledge_store=ks,
        )
        assert any(
            "Directional momentum fails" in e or "BTC shows strong" in e
            for e in result.contradicting_evidence
        )
        ks.close()

    def test_run_precheck_no_knowledge_store_uses_stubs(self):
        """Without knowledge_store, run_precheck behaves as before (backward compat)."""
        from packages.research.synthesis.precheck import run_precheck
        result = run_precheck(
            "test backward compat idea",
            provider_name="manual",
            ledger_path=None,
        )
        assert result.recommendation in ("GO", "CAUTION", "STOP")
        # No KS-derived contradictions (stubs return [])
        # result.contradicting_evidence should be [] from ManualProvider path
        assert isinstance(result.contradicting_evidence, list)

    def test_run_precheck_deduplicates_contradictions(self):
        """If same contradiction text appears multiple times, it appears once."""
        from packages.research.synthesis.precheck import run_precheck
        ks = _make_ks()
        cid1 = ks.add_claim(
            claim_text="Dedup test contradiction claim.",
            claim_type="empirical",
            confidence=0.8,
            trust_tier="high",
            actor="test",
            created_at="2026-04-01T00:00:00+00:00",
        )
        cid2 = ks.add_claim(
            claim_text="Another claim for dedup test.",
            claim_type="empirical",
            confidence=0.7,
            trust_tier="medium",
            actor="test",
            created_at="2026-04-01T00:00:00+00:00",
        )
        ks.add_relation(cid1, cid2, "CONTRADICTS")
        result = run_precheck(
            "dedup contradiction idea",
            provider_name="manual",
            ledger_path=None,
            knowledge_store=ks,
        )
        # Check for no duplicates
        assert len(result.contradicting_evidence) == len(set(result.contradicting_evidence))
        ks.close()


# ---------------------------------------------------------------------------
# Task 2: Enriched PrecheckResult schema
# ---------------------------------------------------------------------------

class TestEnrichedPrecheckResult:
    def test_precheck_result_has_enriched_fields(self):
        """PrecheckResult can be constructed with precheck_id, reason_code, evidence_gap, review_horizon."""
        from packages.research.synthesis.precheck import PrecheckResult
        r = PrecheckResult(
            recommendation="GO",
            idea="enrichment test",
            supporting_evidence=[],
            contradicting_evidence=[],
            risk_factors=[],
            timestamp="2026-04-01T00:00:00+00:00",
            provider_used="manual",
            precheck_id="abc123def456",
            reason_code="STRONG_SUPPORT",
            evidence_gap="",
            review_horizon="",
        )
        assert r.precheck_id == "abc123def456"
        assert r.reason_code == "STRONG_SUPPORT"
        assert r.evidence_gap == ""
        assert r.review_horizon == ""

    def test_enriched_fields_default_to_empty_string(self):
        """New enriched fields default to empty string — existing construction sites unaffected."""
        from packages.research.synthesis.precheck import PrecheckResult
        r = PrecheckResult(
            recommendation="CAUTION",
            idea="default test",
            supporting_evidence=[],
            contradicting_evidence=[],
            risk_factors=[],
            timestamp="2026-04-01T00:00:00+00:00",
            provider_used="manual",
        )
        assert r.precheck_id == ""
        assert r.reason_code == ""
        assert r.evidence_gap == ""
        assert r.review_horizon == ""


class TestRunPrecheckPopulatesEnrichedFields:
    def test_run_precheck_populates_precheck_id(self):
        """precheck_id is deterministic sha256[:12] of idea text."""
        import hashlib
        from packages.research.synthesis.precheck import run_precheck
        idea = "deterministic precheck id test idea"
        expected_id = hashlib.sha256(idea.encode("utf-8")).hexdigest()[:12]
        result = run_precheck(idea, provider_name="manual", ledger_path=None)
        assert result.precheck_id == expected_id

    def test_run_precheck_go_gets_strong_support(self):
        """GO recommendation -> reason_code='STRONG_SUPPORT'."""
        from packages.research.synthesis.precheck import run_precheck, PrecheckResult
        # Force a GO result by using a custom provider that returns GO JSON
        # We'll test via parse_precheck_response + run logic

        # Use monkeypatching to simulate a GO response from the provider
        import packages.research.synthesis.precheck as precheck_module
        original_parse = precheck_module.parse_precheck_response

        def fake_parse(raw_json, idea, model_name):
            return PrecheckResult(
                recommendation="GO",
                idea=idea,
                supporting_evidence=["Strong support"],
                contradicting_evidence=[],
                risk_factors=["minimal risk"],
                timestamp="2026-04-01T00:00:00+00:00",
                provider_used=model_name,
            )

        precheck_module.parse_precheck_response = fake_parse
        try:
            result = run_precheck("GO test idea", provider_name="manual", ledger_path=None)
            assert result.reason_code == "STRONG_SUPPORT"
        finally:
            precheck_module.parse_precheck_response = original_parse

    def test_run_precheck_caution_gets_mixed_evidence(self):
        """CAUTION recommendation -> reason_code='MIXED_EVIDENCE'."""
        from packages.research.synthesis.precheck import run_precheck
        # ManualProvider always returns CAUTION
        result = run_precheck("CAUTION test idea for reason code", provider_name="manual", ledger_path=None)
        assert result.recommendation == "CAUTION"
        assert result.reason_code == "MIXED_EVIDENCE"

    def test_run_precheck_stop_gets_fundamental_blocker(self):
        """STOP recommendation -> reason_code='FUNDAMENTAL_BLOCKER'."""
        from packages.research.synthesis.precheck import run_precheck, PrecheckResult
        import packages.research.synthesis.precheck as precheck_module
        original_parse = precheck_module.parse_precheck_response

        def fake_parse(raw_json, idea, model_name):
            return PrecheckResult(
                recommendation="STOP",
                idea=idea,
                supporting_evidence=[],
                contradicting_evidence=["Fundamental blocker exists"],
                risk_factors=["Cannot proceed"],
                timestamp="2026-04-01T00:00:00+00:00",
                provider_used=model_name,
            )

        precheck_module.parse_precheck_response = fake_parse
        try:
            result = run_precheck("STOP test idea", provider_name="manual", ledger_path=None)
            assert result.reason_code == "FUNDAMENTAL_BLOCKER"
        finally:
            precheck_module.parse_precheck_response = original_parse

    def test_run_precheck_evidence_gap_when_no_contradictions_and_not_go(self):
        """evidence_gap set when contradicting_evidence empty and recommendation != GO."""
        from packages.research.synthesis.precheck import run_precheck
        # ManualProvider returns CAUTION with empty contradicting_evidence (by default)
        result = run_precheck("evidence gap test idea", provider_name="manual", ledger_path=None)
        if result.recommendation != "GO" and not result.contradicting_evidence:
            assert "manual review" in result.evidence_gap.lower() or \
                   "contradicting" in result.evidence_gap.lower() or \
                   len(result.evidence_gap) > 0

    def test_run_precheck_go_has_no_evidence_gap(self):
        """GO recommendation -> evidence_gap=''."""
        from packages.research.synthesis.precheck import run_precheck, PrecheckResult
        import packages.research.synthesis.precheck as precheck_module
        original_parse = precheck_module.parse_precheck_response

        def fake_parse(raw_json, idea, model_name):
            return PrecheckResult(
                recommendation="GO",
                idea=idea,
                supporting_evidence=["Strong support"],
                contradicting_evidence=[],
                risk_factors=["minimal risk"],
                timestamp="2026-04-01T00:00:00+00:00",
                provider_used=model_name,
            )

        precheck_module.parse_precheck_response = fake_parse
        try:
            result = run_precheck("GO no gap idea", provider_name="manual", ledger_path=None)
            assert result.evidence_gap == ""
        finally:
            precheck_module.parse_precheck_response = original_parse

    def test_run_precheck_caution_review_horizon_7d(self):
        """CAUTION recommendation -> review_horizon='7d'."""
        from packages.research.synthesis.precheck import run_precheck
        result = run_precheck("review horizon caution test", provider_name="manual", ledger_path=None)
        assert result.recommendation == "CAUTION"
        assert result.review_horizon == "7d"

    def test_run_precheck_stop_review_horizon_30d(self):
        """STOP recommendation -> review_horizon='30d'."""
        from packages.research.synthesis.precheck import run_precheck, PrecheckResult
        import packages.research.synthesis.precheck as precheck_module
        original_parse = precheck_module.parse_precheck_response

        def fake_parse(raw_json, idea, model_name):
            return PrecheckResult(
                recommendation="STOP",
                idea=idea,
                supporting_evidence=[],
                contradicting_evidence=["Fundamental blocker exists"],
                risk_factors=["Cannot proceed"],
                timestamp="2026-04-01T00:00:00+00:00",
                provider_used=model_name,
            )

        precheck_module.parse_precheck_response = fake_parse
        try:
            result = run_precheck("STOP review horizon idea", provider_name="manual", ledger_path=None)
            assert result.review_horizon == "30d"
        finally:
            precheck_module.parse_precheck_response = original_parse

    def test_run_precheck_go_review_horizon_empty(self):
        """GO recommendation -> review_horizon=''."""
        from packages.research.synthesis.precheck import run_precheck, PrecheckResult
        import packages.research.synthesis.precheck as precheck_module
        original_parse = precheck_module.parse_precheck_response

        def fake_parse(raw_json, idea, model_name):
            return PrecheckResult(
                recommendation="GO",
                idea=idea,
                supporting_evidence=["Strong support"],
                contradicting_evidence=[],
                risk_factors=["minimal risk"],
                timestamp="2026-04-01T00:00:00+00:00",
                provider_used=model_name,
            )

        precheck_module.parse_precheck_response = fake_parse
        try:
            result = run_precheck("GO review horizon empty idea", provider_name="manual", ledger_path=None)
            assert result.review_horizon == ""
        finally:
            precheck_module.parse_precheck_response = original_parse


# ---------------------------------------------------------------------------
# Task 2: Enriched precheck ledger schema
# ---------------------------------------------------------------------------

class TestEnrichedPrecheckLedger:
    def test_ledger_schema_version_bumped(self):
        """LEDGER_SCHEMA_VERSION is 'precheck_ledger_v1'."""
        from packages.research.synthesis.precheck_ledger import LEDGER_SCHEMA_VERSION
        assert LEDGER_SCHEMA_VERSION == "precheck_ledger_v1"

    def test_append_precheck_includes_enriched_fields(self, tmp_path):
        """Appended JSONL line contains precheck_id, reason_code, evidence_gap, review_horizon."""
        from packages.research.synthesis.precheck import PrecheckResult
        from packages.research.synthesis.precheck_ledger import append_precheck
        ledger = tmp_path / "ledger_v1.jsonl"
        r = PrecheckResult(
            recommendation="GO",
            idea="enriched ledger test",
            supporting_evidence=["evidence"],
            contradicting_evidence=[],
            risk_factors=["risk"],
            timestamp="2026-04-01T00:00:00+00:00",
            provider_used="manual",
            precheck_id="abc123def456",
            reason_code="STRONG_SUPPORT",
            evidence_gap="",
            review_horizon="",
        )
        append_precheck(r, ledger_path=ledger)
        data = json.loads(ledger.read_text().strip())
        assert "precheck_id" in data
        assert "reason_code" in data
        assert "evidence_gap" in data
        assert "review_horizon" in data
        assert data["precheck_id"] == "abc123def456"
        assert data["reason_code"] == "STRONG_SUPPORT"

    def test_append_precheck_schema_version_is_v1(self, tmp_path):
        """Appended entries have schema_version='precheck_ledger_v1'."""
        from packages.research.synthesis.precheck import PrecheckResult
        from packages.research.synthesis.precheck_ledger import append_precheck
        ledger = tmp_path / "schema_v1.jsonl"
        r = PrecheckResult(
            recommendation="CAUTION",
            idea="schema version test",
            supporting_evidence=[],
            contradicting_evidence=[],
            risk_factors=[],
            timestamp="2026-04-01T00:00:00+00:00",
            provider_used="manual",
        )
        append_precheck(r, ledger_path=ledger)
        data = json.loads(ledger.read_text().strip())
        assert data["schema_version"] == "precheck_ledger_v1"

    def test_v0_ledger_entries_still_readable(self, tmp_path):
        """list_prechecks() can read v0 entries without error (missing fields default to None)."""
        from packages.research.synthesis.precheck_ledger import list_prechecks
        ledger = tmp_path / "v0_compat.jsonl"
        # Write a v0-format entry manually (no new fields)
        v0_entry = {
            "schema_version": "precheck_ledger_v0",
            "event_type": "precheck_run",
            "recommendation": "GO",
            "idea": "v0 idea",
            "supporting_evidence": ["old evidence"],
            "contradicting_evidence": [],
            "risk_factors": ["old risk"],
            "stale_warning": False,
            "timestamp": "2026-04-01T00:00:00+00:00",
            "provider_used": "manual",
            "written_at": "2026-04-01T00:00:00+00:00",
        }
        ledger.write_text(json.dumps(v0_entry) + "\n")
        entries = list_prechecks(ledger_path=ledger)
        assert len(entries) == 1
        entry = entries[0]
        # Required fields present
        assert entry["recommendation"] == "GO"
        assert entry["idea"] == "v0 idea"
        # New fields absent from v0 (list_prechecks() returns raw dicts -- no KeyError)
        assert entry.get("precheck_id") is None
        assert entry.get("reason_code") is None

    def test_run_precheck_precheck_id_in_ledger(self, tmp_path):
        """run_precheck() writes precheck_id to ledger."""
        import hashlib
        from packages.research.synthesis.precheck import run_precheck
        from packages.research.synthesis.precheck_ledger import list_prechecks
        idea = "ledger precheck_id write test"
        ledger = tmp_path / "id_test.jsonl"
        run_precheck(idea, provider_name="manual", ledger_path=ledger)
        entries = list_prechecks(ledger_path=ledger)
        assert len(entries) == 1
        expected_id = hashlib.sha256(idea.encode("utf-8")).hexdigest()[:12]
        assert entries[0]["precheck_id"] == expected_id


# ---------------------------------------------------------------------------
# CLI smoke test for enriched fields
# ---------------------------------------------------------------------------

class TestResearchPrecheckCLIEnriched:
    def test_json_output_includes_enriched_fields(self, tmp_path):
        """--json output includes precheck_id, reason_code, evidence_gap, review_horizon."""
        import io
        import sys
        from tools.cli.research_precheck import main

        # Capture stdout
        captured = io.StringIO()
        old_stdout = sys.stdout
        sys.stdout = captured
        try:
            exit_code = main([
                "--idea", "CLI enriched fields test idea",
                "--no-ledger",
                "--json",
            ])
        finally:
            sys.stdout = old_stdout

        assert exit_code == 0
        output = captured.getvalue().strip()
        # Should produce JSON output with enriched fields
        data = json.loads(output)
        assert "precheck_id" in data
        assert "reason_code" in data
        assert "evidence_gap" in data
        assert "review_horizon" in data
