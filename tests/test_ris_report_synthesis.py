"""Deterministic offline tests for RIS v1 ReportSynthesizer.

All tests are fully offline -- no network, no LLM, no KnowledgeStore.
Tests cover: dataclass shapes, CitedEvidence extraction, ResearchBrief production,
EnhancedPrecheck production, contradiction handling, staleness, trust tiers,
format functions, and edge cases.
"""

from __future__ import annotations

import pytest
from dataclasses import fields


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

def _make_provenance_doc(
    doc_id: str = "doc_001",
    title: str = "Test Paper",
    source_type: str = "arxiv",
    source_url: str = "https://arxiv.org/abs/test",
    source_family: str = "academic",
    trust_tier: str = "tier_1_primary",
    source_publish_date: str = "2026-01-01",
    author: str = "Test Author",
) -> dict:
    return {
        "id": doc_id,
        "title": title,
        "author": author,
        "source_type": source_type,
        "source_url": source_url,
        "source_family": source_family,
        "trust_tier": trust_tier,
        "source_publish_date": source_publish_date,
    }


def _make_enriched_claim(
    claim_text: str = "Market makers profit from bid-ask spreads",
    confidence: float = 0.85,
    trust_tier: str = "tier_1_primary",
    source_family: str = "academic",
    is_contradicted: bool = False,
    staleness_note: str = "",
    provenance_docs: list | None = None,
    claim_id: str = "claim_001",
    claim_type: str = "empirical",
    effective_score: float = 0.85,
    freshness_modifier: float = 1.0,
    contradiction_summary: list | None = None,
    lifecycle: str = "active",
    source_document_id: str = "doc_001",
) -> dict:
    if provenance_docs is None:
        provenance_docs = [_make_provenance_doc(trust_tier=trust_tier)]
    if contradiction_summary is None:
        contradiction_summary = []
    return {
        "id": claim_id,
        "claim_text": claim_text,
        "claim_type": claim_type,
        "confidence": confidence,
        "trust_tier": trust_tier,
        "source_document_id": source_document_id,
        "freshness_modifier": freshness_modifier,
        "effective_score": effective_score,
        "provenance_docs": provenance_docs,
        "contradiction_summary": contradiction_summary,
        "is_contradicted": is_contradicted,
        "staleness_note": staleness_note,
        "lifecycle": lifecycle,
    }


# ---------------------------------------------------------------------------
# Test 1 & 2: ResearchBrief and CitedEvidence dataclass shapes
# ---------------------------------------------------------------------------

class TestResearchBriefDataclass:
    def test_research_brief_has_required_fields(self):
        from packages.research.synthesis.report import ResearchBrief, CitedEvidence
        brief = ResearchBrief(
            topic="test topic",
            generated_at="2026-04-03T00:00:00Z",
            sources_queried=5,
            sources_cited=2,
            overall_confidence="HIGH",
            summary="Test summary",
            key_findings=[],
            contradictions=[],
            actionability={
                "can_inform_strategy": False,
                "target_track": "",
                "suggested_next_step": "",
                "estimated_impact": "",
            },
            knowledge_gaps=[],
            cited_sources=[],
        )
        assert brief.topic == "test topic"
        assert brief.generated_at == "2026-04-03T00:00:00Z"
        assert brief.sources_queried == 5
        assert brief.sources_cited == 2
        assert brief.overall_confidence == "HIGH"
        assert brief.summary == "Test summary"
        assert brief.key_findings == []
        assert brief.contradictions == []
        assert isinstance(brief.actionability, dict)
        assert brief.knowledge_gaps == []
        assert brief.cited_sources == []

    def test_cited_evidence_has_required_fields(self):
        from packages.research.synthesis.report import CitedEvidence
        ev = CitedEvidence(
            claim_text="Test claim",
            source_doc_id="doc_001",
            source_title="Test Paper",
            source_type="arxiv",
            trust_tier="tier_1_primary",
            confidence=0.9,
            freshness_note="",
            provenance_url="https://arxiv.org/abs/test",
        )
        assert ev.claim_text == "Test claim"
        assert ev.source_doc_id == "doc_001"
        assert ev.source_title == "Test Paper"
        assert ev.source_type == "arxiv"
        assert ev.trust_tier == "tier_1_primary"
        assert ev.confidence == 0.9
        assert ev.freshness_note == ""
        assert ev.provenance_url == "https://arxiv.org/abs/test"


# ---------------------------------------------------------------------------
# Test 3: format_research_brief markdown sections
# ---------------------------------------------------------------------------

class TestFormatResearchBrief:
    def test_format_research_brief_returns_markdown_with_all_sections(self):
        from packages.research.synthesis.report import (
            ResearchBrief,
            CitedEvidence,
            format_research_brief,
        )
        ev = CitedEvidence(
            claim_text="Market making generates returns",
            source_doc_id="doc_001",
            source_title="Test Paper",
            source_type="arxiv",
            trust_tier="tier_1_primary",
            confidence=0.9,
            freshness_note="",
            provenance_url="https://arxiv.org/abs/test",
        )
        brief = ResearchBrief(
            topic="Market making strategies",
            generated_at="2026-04-03T00:00:00Z",
            sources_queried=10,
            sources_cited=1,
            overall_confidence="HIGH",
            summary="Market making is effective.",
            key_findings=[
                {
                    "title": "Spread revenue",
                    "description": "Market makers earn from spreads",
                    "source": ev,
                    "confidence_tier": "HIGH",
                }
            ],
            contradictions=[],
            actionability={
                "can_inform_strategy": True,
                "target_track": "market_maker",
                "suggested_next_step": "Run Gate 2 sweep",
                "estimated_impact": "High",
            },
            knowledge_gaps=["Need more data on crypto markets"],
            cited_sources=[ev],
        )
        md = format_research_brief(brief)
        assert isinstance(md, str)
        assert len(md) > 0
        # Required sections
        assert "Summary" in md
        assert "Key Findings" in md
        assert "Contradictions" in md
        assert "Actionability" in md
        assert "Knowledge Gaps" in md
        assert "Sources Cited" in md


# ---------------------------------------------------------------------------
# Test 4 & 5: EnhancedPrecheck dataclass and format
# ---------------------------------------------------------------------------

class TestEnhancedPrecheckDataclass:
    def test_enhanced_precheck_has_required_fields(self):
        from packages.research.synthesis.report import EnhancedPrecheck, CitedEvidence
        ev = CitedEvidence(
            claim_text="Evidence for idea",
            source_doc_id="doc_001",
            source_title="Test Paper",
            source_type="reddit",
            trust_tier="tier_2_community",
            confidence=0.7,
            freshness_note="",
            provenance_url="",
        )
        pc = EnhancedPrecheck(
            recommendation="GO",
            idea="Build a momentum signal",
            supporting=[ev],
            contradicting=[],
            risk_factors=["Market may be closed"],
            past_failures=[],
            knowledge_gaps=[],
            validation_approach="Run paper trade",
            timestamp="2026-04-03T00:00:00Z",
            overall_confidence="HIGH",
        )
        assert pc.recommendation == "GO"
        assert pc.idea == "Build a momentum signal"
        assert len(pc.supporting) == 1
        assert pc.contradicting == []
        assert pc.risk_factors == ["Market may be closed"]
        assert pc.past_failures == []
        assert pc.knowledge_gaps == []
        assert pc.validation_approach == "Run paper trade"
        assert pc.timestamp == "2026-04-03T00:00:00Z"
        assert pc.overall_confidence == "HIGH"

    def test_format_enhanced_precheck_contains_recommendation_and_sections(self):
        from packages.research.synthesis.report import (
            EnhancedPrecheck,
            CitedEvidence,
            format_enhanced_precheck,
        )
        ev = CitedEvidence(
            claim_text="Momentum works in crypto",
            source_doc_id="doc_002",
            source_title="Crypto Analysis",
            source_type="arxiv",
            trust_tier="tier_1_primary",
            confidence=0.8,
            freshness_note="",
            provenance_url="https://arxiv.org/abs/002",
        )
        pc = EnhancedPrecheck(
            recommendation="CAUTION",
            idea="Momentum crypto signal",
            supporting=[ev],
            contradicting=[],
            risk_factors=["High volatility"],
            past_failures=[],
            knowledge_gaps=["No 5m market data"],
            validation_approach="Paper trade first",
            timestamp="2026-04-03T00:00:00Z",
            overall_confidence="MEDIUM",
        )
        md = format_enhanced_precheck(pc)
        assert isinstance(md, str)
        assert len(md) > 0
        assert "CAUTION" in md
        assert "Supporting" in md or "supporting" in md.lower()


# ---------------------------------------------------------------------------
# Tests 6-10: ReportSynthesizer.synthesize_brief()
# ---------------------------------------------------------------------------

class TestSynthesizeBrief:
    def setup_method(self):
        from packages.research.synthesis.report import ReportSynthesizer
        self.synth = ReportSynthesizer()

    def test_synthesize_brief_returns_research_brief(self):
        from packages.research.synthesis.report import ResearchBrief
        claims = [
            _make_enriched_claim(
                claim_text="Market making yields positive PnL at Gate 2",
                confidence=0.85,
                trust_tier="tier_1_primary",
                effective_score=0.85,
            )
        ]
        brief = self.synth.synthesize_brief("market making strategies", claims)
        assert isinstance(brief, ResearchBrief)
        assert brief.topic == "market making strategies"
        assert brief.summary != ""
        assert isinstance(brief.key_findings, list)

    def test_provenance_docs_produce_cited_evidence(self):
        from packages.research.synthesis.report import CitedEvidence
        prov = _make_provenance_doc(doc_id="doc_abc", title="Test Paper", source_type="arxiv")
        claims = [
            _make_enriched_claim(
                claim_text="Spread capture is profitable",
                provenance_docs=[prov],
                effective_score=0.9,
            )
        ]
        brief = self.synth.synthesize_brief("spread capture", claims)
        # cited_sources should contain CitedEvidence with provenance
        assert len(brief.cited_sources) > 0
        for ev in brief.cited_sources:
            assert isinstance(ev, CitedEvidence)
            assert ev.source_doc_id != ""

    def test_contradicted_claims_go_to_contradictions_section(self):
        non_contradicted = _make_enriched_claim(
            claim_id="c001",
            claim_text="Momentum signals work",
            is_contradicted=False,
            effective_score=0.9,
        )
        contradicted = _make_enriched_claim(
            claim_id="c002",
            claim_text="Momentum signals fail in choppy markets",
            is_contradicted=True,
            contradiction_summary=["Momentum signals work"],
            effective_score=0.4,
        )
        claims = [non_contradicted, contradicted]
        brief = self.synth.synthesize_brief("momentum signals", claims)
        # The contradicted claim should appear in contradictions
        assert len(brief.contradictions) > 0

    def test_stale_claims_appear_in_knowledge_gaps(self):
        stale_claim = _make_enriched_claim(
            claim_id="c003",
            claim_text="Old data shows markets are efficient",
            staleness_note="STALE",
            freshness_modifier=0.3,
            effective_score=0.3,
        )
        claims = [stale_claim]
        brief = self.synth.synthesize_brief("market efficiency", claims)
        # Stale claims should generate knowledge gap entries
        assert len(brief.knowledge_gaps) > 0

    def test_empty_evidence_produces_insufficient_brief(self):
        brief = self.synth.synthesize_brief("market efficiency", [])
        assert "insufficient" in brief.summary.lower() or brief.key_findings == []
        assert brief.sources_cited == 0


# ---------------------------------------------------------------------------
# Tests 11-15: ReportSynthesizer.synthesize_precheck()
# ---------------------------------------------------------------------------

class TestSynthesizePrecheck:
    def setup_method(self):
        from packages.research.synthesis.report import ReportSynthesizer
        self.synth = ReportSynthesizer()

    def test_synthesize_precheck_returns_enhanced_precheck(self):
        from packages.research.synthesis.report import EnhancedPrecheck
        claims = [
            _make_enriched_claim(
                claim_text="crypto momentum signals produce 15% edge",
                confidence=0.85,
                effective_score=0.85,
            )
        ]
        pc = self.synth.synthesize_precheck("crypto momentum signal", claims)
        assert isinstance(pc, EnhancedPrecheck)
        assert pc.recommendation in ("GO", "CAUTION", "STOP")

    def test_high_confidence_non_contradicted_claims_populate_supporting(self):
        claims = [
            _make_enriched_claim(
                claim_text="crypto pair directional momentum produces edge",
                confidence=0.85,
                is_contradicted=False,
                effective_score=0.85,
            )
        ]
        pc = self.synth.synthesize_precheck("crypto pair directional momentum", claims)
        assert len(pc.supporting) > 0

    def test_contradicting_claims_populate_contradicting_with_citations(self):
        from packages.research.synthesis.report import CitedEvidence
        prov = _make_provenance_doc(doc_id="doc_contra", title="Contra Paper")
        claims = [
            _make_enriched_claim(
                claim_text="directional momentum fails in efficient markets",
                is_contradicted=True,
                contradiction_summary=["momentum does not persist"],
                provenance_docs=[prov],
                effective_score=0.4,
            )
        ]
        pc = self.synth.synthesize_precheck("directional momentum signal", claims)
        assert len(pc.contradicting) > 0
        for ev in pc.contradicting:
            assert isinstance(ev, CitedEvidence)

    def test_all_stale_evidence_sets_stale_warning_and_low_confidence(self):
        claims = [
            _make_enriched_claim(
                claim_text="stale momentum data from 2020",
                staleness_note="STALE",
                freshness_modifier=0.2,
                effective_score=0.2,
                confidence=0.3,
            )
        ]
        pc = self.synth.synthesize_precheck("momentum", claims)
        assert pc.stale_warning is True
        assert pc.overall_confidence == "LOW"

    def test_no_evidence_gives_caution_with_evidence_gap(self):
        pc = self.synth.synthesize_precheck("some obscure idea", [])
        assert pc.recommendation == "CAUTION"
        assert pc.evidence_gap != ""


# ---------------------------------------------------------------------------
# Tests 16-17: Citation formatting
# ---------------------------------------------------------------------------

class TestCitationFormatting:
    def test_format_citation_produces_expected_string(self):
        from packages.research.synthesis.report import CitedEvidence, format_citation
        ev = CitedEvidence(
            claim_text="Some claim",
            source_doc_id="doc_001",
            source_title="My Paper",
            source_type="arxiv",
            trust_tier="tier_1_primary",
            confidence=0.9,
            freshness_note="",
            provenance_url="",
        )
        citation = format_citation(ev)
        assert "doc_001" in citation
        assert "arxiv" in citation
        assert "tier_1_primary" in citation

    def test_sources_cited_table_in_format_research_brief(self):
        from packages.research.synthesis.report import (
            ResearchBrief,
            CitedEvidence,
            format_research_brief,
        )
        ev1 = CitedEvidence(
            claim_text="Claim A",
            source_doc_id="doc_alpha",
            source_title="Alpha Paper",
            source_type="arxiv",
            trust_tier="tier_1_primary",
            confidence=0.9,
            freshness_note="",
            provenance_url="",
        )
        ev2 = CitedEvidence(
            claim_text="Claim B",
            source_doc_id="doc_beta",
            source_title="Beta Thread",
            source_type="reddit",
            trust_tier="tier_2_community",
            confidence=0.6,
            freshness_note="AGING",
            provenance_url="",
        )
        brief = ResearchBrief(
            topic="Test",
            generated_at="2026-04-03T00:00:00Z",
            sources_queried=2,
            sources_cited=2,
            overall_confidence="MEDIUM",
            summary="Test summary",
            key_findings=[],
            contradictions=[],
            actionability={
                "can_inform_strategy": False,
                "target_track": "",
                "suggested_next_step": "",
                "estimated_impact": "",
            },
            knowledge_gaps=[],
            cited_sources=[ev1, ev2],
        )
        md = format_research_brief(brief)
        assert "doc_alpha" in md
        assert "doc_beta" in md


# ---------------------------------------------------------------------------
# Tests 18-19: Contradiction handling
# ---------------------------------------------------------------------------

class TestContradictionHandling:
    def setup_method(self):
        from packages.research.synthesis.report import ReportSynthesizer
        self.synth = ReportSynthesizer()

    def test_contradictions_section_lists_both_sides_with_citations(self):
        prov_a = _make_provenance_doc(doc_id="doc_a", title="Paper A")
        prov_b = _make_provenance_doc(doc_id="doc_b", title="Paper B")
        claim_a = _make_enriched_claim(
            claim_id="ca",
            claim_text="Momentum works in crypto",
            is_contradicted=True,
            contradiction_summary=["Momentum fails in crypto"],
            provenance_docs=[prov_a],
            effective_score=0.6,
        )
        claim_b = _make_enriched_claim(
            claim_id="cb",
            claim_text="Momentum fails in crypto",
            is_contradicted=True,
            contradiction_summary=["Momentum works in crypto"],
            provenance_docs=[prov_b],
            effective_score=0.5,
        )
        brief = self.synth.synthesize_brief("crypto momentum", [claim_a, claim_b])
        assert len(brief.contradictions) > 0
        # At least one contradiction entry should have 'sources'
        for c in brief.contradictions:
            assert "claim_a" in c or "claim_b" in c or "sources" in c

    def test_unresolved_contradictions_surfaced_as_unresolved_questions(self):
        claim = _make_enriched_claim(
            claim_id="cu",
            claim_text="Market structure is efficient",
            is_contradicted=True,
            contradiction_summary=["Market structure is inefficient"],
            effective_score=0.5,
        )
        brief = self.synth.synthesize_brief("market structure", [claim])
        # Should have some unresolved content -- either in contradictions or knowledge_gaps
        assert len(brief.contradictions) > 0 or len(brief.knowledge_gaps) > 0


# ---------------------------------------------------------------------------
# Tests 20-21: Trust tier differentiation and confidence calculation
# ---------------------------------------------------------------------------

class TestTrustTierDifferentiation:
    def setup_method(self):
        from packages.research.synthesis.report import ReportSynthesizer
        self.synth = ReportSynthesizer()

    def test_tier1_claims_rank_higher_in_key_findings(self):
        tier1_claim = _make_enriched_claim(
            claim_id="t1",
            claim_text="Tier 1 finding about market making",
            confidence=0.9,
            trust_tier="tier_1_primary",
            effective_score=0.9,
        )
        tier2_claim = _make_enriched_claim(
            claim_id="t2",
            claim_text="Tier 2 finding about market making",
            confidence=0.6,
            trust_tier="tier_2_community",
            effective_score=0.6,
        )
        # Pass tier2 first to test that ordering isn't just insertion order
        brief = self.synth.synthesize_brief("market making", [tier2_claim, tier1_claim])
        if len(brief.key_findings) >= 2:
            first_source = brief.key_findings[0].get("source")
            if first_source is not None:
                assert first_source.trust_tier == "tier_1_primary"

    def test_confidence_reflected_in_overall_confidence(self):
        # All high confidence -> HIGH
        high_claims = [
            _make_enriched_claim(
                claim_id=f"h{i}",
                claim_text=f"High confidence claim {i}",
                confidence=0.9,
                staleness_note="",
                effective_score=0.9,
            )
            for i in range(3)
        ]
        brief_high = self.synth.synthesize_brief("test high", high_claims)
        assert brief_high.overall_confidence == "HIGH"

        # All low confidence -> LOW
        low_claims = [
            _make_enriched_claim(
                claim_id=f"l{i}",
                claim_text=f"Low confidence claim {i}",
                confidence=0.3,
                staleness_note="STALE",
                freshness_modifier=0.2,
                effective_score=0.2,
            )
            for i in range(3)
        ]
        brief_low = self.synth.synthesize_brief("test low", low_claims)
        assert brief_low.overall_confidence == "LOW"

        # Mixed -> MEDIUM
        mixed_claims = [
            _make_enriched_claim(
                claim_id="m1",
                claim_text="High confidence claim",
                confidence=0.9,
                effective_score=0.9,
            ),
            _make_enriched_claim(
                claim_id="m2",
                claim_text="Low confidence stale claim",
                confidence=0.3,
                staleness_note="STALE",
                freshness_modifier=0.2,
                effective_score=0.2,
            ),
        ]
        brief_mixed = self.synth.synthesize_brief("test mixed", mixed_claims)
        assert brief_mixed.overall_confidence == "MEDIUM"
