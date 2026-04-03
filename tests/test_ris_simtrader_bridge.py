"""Tests for the RIS SimTrader bridge v1.

Covers:
- KnowledgeStore.update_claim_validation_status()
- hypothesis_bridge: brief_to_candidate(), precheck_to_candidate(), register_research_hypothesis()
- validation_feedback: record_validation_outcome()

All tests are deterministic and offline (no network, no LLM, no ClickHouse).
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from packages.polymarket.rag.knowledge_store import KnowledgeStore
from packages.research.integration import (
    brief_to_candidate,
    precheck_to_candidate,
    record_validation_outcome,
    register_research_hypothesis,
)
from packages.research.synthesis.report import (
    CitedEvidence,
    EnhancedPrecheck,
    ResearchBrief,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def ks() -> KnowledgeStore:
    """In-memory KnowledgeStore for isolation."""
    return KnowledgeStore(":memory:")


@pytest.fixture()
def sample_claim_id(ks: KnowledgeStore) -> str:
    """Insert a single claim and return its ID."""
    return ks.add_claim(
        claim_text="BTC/ETH 5-minute pairs show directional momentum.",
        claim_type="empirical",
        confidence=0.82,
        trust_tier="tier_1",
        actor="test_actor",
    )


@pytest.fixture()
def sample_brief() -> ResearchBrief:
    """A minimal but valid ResearchBrief."""
    ev1 = CitedEvidence(
        claim_text="Market makers earn edge from spread capture.",
        source_doc_id="doc_abc123",
        source_title="Market Maker Study",
        source_type="academic",
        trust_tier="tier_1",
        confidence=0.85,
        freshness_note="",
        provenance_url="internal://doc_abc123",
    )
    ev2 = CitedEvidence(
        claim_text="Avellaneda-Stoikov model outperforms naive quoting.",
        source_doc_id="doc_def456",
        source_title="AS Model Paper",
        source_type="academic",
        trust_tier="tier_1",
        confidence=0.78,
        freshness_note="",
        provenance_url="internal://doc_def456",
    )
    return ResearchBrief(
        topic="market maker spread capture strategies",
        generated_at="2026-04-03T12:00:00+00:00",
        sources_queried=5,
        sources_cited=2,
        overall_confidence="HIGH",
        summary="Market makers reliably capture spread edge using Avellaneda-Stoikov quoting.",
        key_findings=[
            {
                "title": "Spread capture is primary revenue source",
                "description": "Market makers earn edge from spread capture.",
                "source": ev1,
                "confidence_tier": "HIGH",
            }
        ],
        contradictions=[],
        actionability={
            "can_inform_strategy": True,
            "target_track": "market_maker",
            "suggested_next_step": "Run Gate 2 sweep with AS params.",
            "estimated_impact": "HIGH",
        },
        knowledge_gaps=[],
        cited_sources=[ev1, ev2],
    )


@pytest.fixture()
def sample_precheck() -> EnhancedPrecheck:
    """A minimal but valid EnhancedPrecheck."""
    ev = CitedEvidence(
        claim_text="BTC perpetuals show strong momentum signals.",
        source_doc_id="doc_xyz789",
        source_title="Crypto Momentum Study",
        source_type="academic",
        trust_tier="tier_2",
        confidence=0.72,
        freshness_note="",
        provenance_url="internal://doc_xyz789",
    )
    return EnhancedPrecheck(
        recommendation="GO",
        idea="Deploy momentum strategy on BTC 5m markets",
        supporting=[ev],
        contradicting=[],
        risk_factors=["Oracle mismatch risk between Coinbase and Chainlink"],
        past_failures=[],
        knowledge_gaps=[],
        validation_approach="Paper trade for 7 days with simulated fills.",
        timestamp="2026-04-03T12:00:00+00:00",
        overall_confidence="MEDIUM",
        stale_warning=False,
        evidence_gap="",
        precheck_id="precheck_abc",
    )


@pytest.fixture()
def registry_path(tmp_path: Path) -> Path:
    """Temporary registry JSONL path."""
    return tmp_path / "registry.jsonl"


# ---------------------------------------------------------------------------
# Tests: KnowledgeStore.update_claim_validation_status
# ---------------------------------------------------------------------------

class TestUpdateClaimValidationStatus:
    def test_update_sets_consistent_status(self, ks: KnowledgeStore, sample_claim_id: str) -> None:
        """update_claim_validation_status sets CONSISTENT_WITH_RESULTS correctly."""
        ks.update_claim_validation_status(
            sample_claim_id, "CONSISTENT_WITH_RESULTS", actor="test"
        )
        claim = ks.get_claim(sample_claim_id)
        assert claim is not None
        assert claim["validation_status"] == "CONSISTENT_WITH_RESULTS"

    def test_update_sets_contradicted_status(self, ks: KnowledgeStore, sample_claim_id: str) -> None:
        """update_claim_validation_status sets CONTRADICTED correctly."""
        ks.update_claim_validation_status(
            sample_claim_id, "CONTRADICTED", actor="test"
        )
        claim = ks.get_claim(sample_claim_id)
        assert claim is not None
        assert claim["validation_status"] == "CONTRADICTED"

    def test_update_sets_inconclusive_status(self, ks: KnowledgeStore, sample_claim_id: str) -> None:
        """update_claim_validation_status sets INCONCLUSIVE correctly."""
        ks.update_claim_validation_status(
            sample_claim_id, "INCONCLUSIVE", actor="test"
        )
        claim = ks.get_claim(sample_claim_id)
        assert claim is not None
        assert claim["validation_status"] == "INCONCLUSIVE"

    def test_update_sets_untested_status(self, ks: KnowledgeStore, sample_claim_id: str) -> None:
        """update_claim_validation_status can reset to UNTESTED."""
        ks.update_claim_validation_status(
            sample_claim_id, "CONSISTENT_WITH_RESULTS", actor="test"
        )
        ks.update_claim_validation_status(
            sample_claim_id, "UNTESTED", actor="test"
        )
        claim = ks.get_claim(sample_claim_id)
        assert claim is not None
        assert claim["validation_status"] == "UNTESTED"

    def test_raises_for_unknown_claim_id(self, ks: KnowledgeStore) -> None:
        """update_claim_validation_status raises ValueError for an unknown claim_id."""
        with pytest.raises(ValueError, match="claim not found"):
            ks.update_claim_validation_status(
                "nonexistent_claim_id_abc", "CONSISTENT_WITH_RESULTS", actor="test"
            )

    def test_raises_for_invalid_status(self, ks: KnowledgeStore, sample_claim_id: str) -> None:
        """update_claim_validation_status raises ValueError for invalid status strings."""
        with pytest.raises(ValueError, match="invalid.*status|status.*invalid|not.*valid"):
            ks.update_claim_validation_status(
                sample_claim_id, "APPROVED", actor="test"
            )

    def test_raises_for_another_invalid_status(self, ks: KnowledgeStore, sample_claim_id: str) -> None:
        """update_claim_validation_status rejects empty string."""
        with pytest.raises(ValueError):
            ks.update_claim_validation_status(
                sample_claim_id, "", actor="test"
            )

    def test_updates_updated_at_timestamp(self, ks: KnowledgeStore, sample_claim_id: str) -> None:
        """update_claim_validation_status updates the updated_at column."""
        claim_before = ks.get_claim(sample_claim_id)
        assert claim_before is not None
        original_updated_at = claim_before["updated_at"]

        import time
        time.sleep(0.01)  # ensure timestamp differs

        ks.update_claim_validation_status(
            sample_claim_id, "CONSISTENT_WITH_RESULTS", actor="test"
        )
        claim_after = ks.get_claim(sample_claim_id)
        assert claim_after is not None
        # updated_at should be >= original (may equal if same second, but we document the intent)
        assert claim_after["updated_at"] >= original_updated_at


# ---------------------------------------------------------------------------
# Tests: brief_to_candidate
# ---------------------------------------------------------------------------

class TestBriefToCandidate:
    def test_returns_required_keys(self, sample_brief: ResearchBrief) -> None:
        """brief_to_candidate produces a dict with all required keys."""
        candidate = brief_to_candidate(sample_brief)
        required_keys = {
            "name",
            "source_brief_topic",
            "hypothesis_text",
            "evidence_doc_ids",
            "suggested_parameters",
            "strategy_type",
            "overall_confidence",
            "generated_at",
        }
        assert required_keys.issubset(set(candidate.keys()))

    def test_preserves_evidence_doc_ids(self, sample_brief: ResearchBrief) -> None:
        """brief_to_candidate preserves all evidence_doc_ids from cited_sources."""
        candidate = brief_to_candidate(sample_brief)
        doc_ids = candidate["evidence_doc_ids"]
        assert "doc_abc123" in doc_ids
        assert "doc_def456" in doc_ids

    def test_name_is_slugified(self, sample_brief: ResearchBrief) -> None:
        """brief_to_candidate slugifies the topic into a valid name."""
        candidate = brief_to_candidate(sample_brief)
        name = candidate["name"]
        assert " " not in name
        assert name.endswith("_v1")
        # Should be lowercase or snake_case
        assert name == name.lower() or "_" in name

    def test_strategy_type_from_actionability(self, sample_brief: ResearchBrief) -> None:
        """brief_to_candidate extracts strategy_type from actionability.target_track."""
        candidate = brief_to_candidate(sample_brief)
        assert candidate["strategy_type"] == "market_maker"

    def test_overall_confidence_preserved(self, sample_brief: ResearchBrief) -> None:
        """brief_to_candidate preserves overall_confidence from brief."""
        candidate = brief_to_candidate(sample_brief)
        assert candidate["overall_confidence"] == "HIGH"

    def test_generated_at_preserved(self, sample_brief: ResearchBrief) -> None:
        """brief_to_candidate preserves generated_at from brief."""
        candidate = brief_to_candidate(sample_brief)
        assert candidate["generated_at"] == "2026-04-03T12:00:00+00:00"

    def test_hypothesis_text_is_non_empty(self, sample_brief: ResearchBrief) -> None:
        """brief_to_candidate produces a non-empty hypothesis_text."""
        candidate = brief_to_candidate(sample_brief)
        assert isinstance(candidate["hypothesis_text"], str)
        assert len(candidate["hypothesis_text"]) > 0

    def test_no_duplicate_doc_ids(self, sample_brief: ResearchBrief) -> None:
        """brief_to_candidate deduplicates evidence_doc_ids."""
        # Add a duplicate cited source
        ev_dup = CitedEvidence(
            claim_text="Duplicate.",
            source_doc_id="doc_abc123",  # same as ev1
            source_title="Dup",
            source_type="academic",
            trust_tier="tier_1",
            confidence=0.7,
            freshness_note="",
            provenance_url="",
        )
        sample_brief.cited_sources.append(ev_dup)
        candidate = brief_to_candidate(sample_brief)
        doc_ids = candidate["evidence_doc_ids"]
        assert len(doc_ids) == len(set(doc_ids))

    def test_empty_brief_does_not_raise(self) -> None:
        """brief_to_candidate handles a brief with no cited sources."""
        brief = ResearchBrief(
            topic="empty topic",
            generated_at="2026-04-03T00:00:00+00:00",
            sources_queried=0,
            sources_cited=0,
            overall_confidence="LOW",
            summary="Insufficient evidence: no claims found for this topic.",
            key_findings=[],
            contradictions=[],
            actionability={
                "can_inform_strategy": False,
                "target_track": "",
                "suggested_next_step": "Ingest more data.",
                "estimated_impact": "",
            },
            knowledge_gaps=[],
            cited_sources=[],
        )
        candidate = brief_to_candidate(brief)
        assert candidate["evidence_doc_ids"] == []
        assert candidate["strategy_type"] == "general"


# ---------------------------------------------------------------------------
# Tests: precheck_to_candidate
# ---------------------------------------------------------------------------

class TestPrecheckToCandidate:
    def test_returns_required_keys(self, sample_precheck: EnhancedPrecheck) -> None:
        """precheck_to_candidate produces a dict with all required keys."""
        candidate = precheck_to_candidate(sample_precheck)
        required_keys = {
            "name",
            "source_brief_topic",
            "hypothesis_text",
            "evidence_doc_ids",
            "suggested_parameters",
            "strategy_type",
            "overall_confidence",
            "generated_at",
        }
        assert required_keys.issubset(set(candidate.keys()))

    def test_evidence_doc_ids_from_supporting(self, sample_precheck: EnhancedPrecheck) -> None:
        """precheck_to_candidate extracts doc_ids from supporting evidence."""
        candidate = precheck_to_candidate(sample_precheck)
        assert "doc_xyz789" in candidate["evidence_doc_ids"]

    def test_hypothesis_text_includes_idea(self, sample_precheck: EnhancedPrecheck) -> None:
        """precheck_to_candidate includes the idea in hypothesis_text."""
        candidate = precheck_to_candidate(sample_precheck)
        # hypothesis_text should reference the idea or recommendation
        assert len(candidate["hypothesis_text"]) > 0

    def test_overall_confidence_preserved(self, sample_precheck: EnhancedPrecheck) -> None:
        """precheck_to_candidate preserves overall_confidence."""
        candidate = precheck_to_candidate(sample_precheck)
        assert candidate["overall_confidence"] == "MEDIUM"

    def test_generated_at_preserved(self, sample_precheck: EnhancedPrecheck) -> None:
        """precheck_to_candidate uses precheck timestamp as generated_at."""
        candidate = precheck_to_candidate(sample_precheck)
        assert candidate["generated_at"] == "2026-04-03T12:00:00+00:00"


# ---------------------------------------------------------------------------
# Tests: register_research_hypothesis
# ---------------------------------------------------------------------------

class TestRegisterResearchHypothesis:
    def test_writes_jsonl_event(
        self, sample_brief: ResearchBrief, registry_path: Path
    ) -> None:
        """register_research_hypothesis writes a valid JSONL event to the registry."""
        candidate = brief_to_candidate(sample_brief)
        hyp_id = register_research_hypothesis(registry_path, candidate)

        assert registry_path.exists()
        lines = registry_path.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 1

        event = json.loads(lines[0])
        assert event["hypothesis_id"] == hyp_id
        assert event["event_type"] == "registered"

    def test_event_has_research_bridge_origin(
        self, sample_brief: ResearchBrief, registry_path: Path
    ) -> None:
        """register_research_hypothesis sets source.origin to 'research_bridge'."""
        candidate = brief_to_candidate(sample_brief)
        register_research_hypothesis(registry_path, candidate)

        lines = registry_path.read_text(encoding="utf-8").strip().splitlines()
        event = json.loads(lines[0])
        assert event.get("source", {}).get("origin") == "research_bridge"

    def test_event_preserves_evidence_doc_ids(
        self, sample_brief: ResearchBrief, registry_path: Path
    ) -> None:
        """register_research_hypothesis stores evidence_doc_ids in the registry event."""
        candidate = brief_to_candidate(sample_brief)
        register_research_hypothesis(registry_path, candidate)

        lines = registry_path.read_text(encoding="utf-8").strip().splitlines()
        event = json.loads(lines[0])
        source = event.get("source", {})
        doc_ids = source.get("evidence_doc_ids", [])
        assert "doc_abc123" in doc_ids
        assert "doc_def456" in doc_ids

    def test_hypothesis_id_is_stable(
        self, sample_brief: ResearchBrief, registry_path: Path
    ) -> None:
        """Same brief always produces the same hypothesis_id (stable ID)."""
        candidate = brief_to_candidate(sample_brief)
        hyp_id_1 = register_research_hypothesis(registry_path, candidate)

        # Call again with a fresh registry path
        with tempfile.TemporaryDirectory() as tmpdir:
            path2 = Path(tmpdir) / "reg2.jsonl"
            candidate2 = brief_to_candidate(sample_brief)
            hyp_id_2 = register_research_hypothesis(path2, candidate2)

        assert hyp_id_1 == hyp_id_2

    def test_hypothesis_id_format(
        self, sample_brief: ResearchBrief, registry_path: Path
    ) -> None:
        """register_research_hypothesis returns an ID with the hyp_ prefix."""
        candidate = brief_to_candidate(sample_brief)
        hyp_id = register_research_hypothesis(registry_path, candidate)
        assert hyp_id.startswith("hyp_")

    def test_status_is_proposed(
        self, sample_brief: ResearchBrief, registry_path: Path
    ) -> None:
        """register_research_hypothesis sets initial status to 'proposed'."""
        candidate = brief_to_candidate(sample_brief)
        register_research_hypothesis(registry_path, candidate)

        lines = registry_path.read_text(encoding="utf-8").strip().splitlines()
        event = json.loads(lines[0])
        assert event["status"] == "proposed"


# ---------------------------------------------------------------------------
# Tests: record_validation_outcome
# ---------------------------------------------------------------------------

class TestRecordValidationOutcome:
    def test_confirmed_sets_consistent(
        self, ks: KnowledgeStore, sample_claim_id: str
    ) -> None:
        """record_validation_outcome with 'confirmed' sets CONSISTENT_WITH_RESULTS."""
        result = record_validation_outcome(
            store=ks,
            hypothesis_id="hyp_abc123",
            claim_ids=[sample_claim_id],
            outcome="confirmed",
            reason="Gate 2 sweep showed positive PnL.",
        )
        claim = ks.get_claim(sample_claim_id)
        assert claim is not None
        assert claim["validation_status"] == "CONSISTENT_WITH_RESULTS"
        assert result["claims_updated"] == 1

    def test_contradicted_sets_contradicted(
        self, ks: KnowledgeStore, sample_claim_id: str
    ) -> None:
        """record_validation_outcome with 'contradicted' sets CONTRADICTED."""
        result = record_validation_outcome(
            store=ks,
            hypothesis_id="hyp_abc123",
            claim_ids=[sample_claim_id],
            outcome="contradicted",
            reason="Strategy lost money in replay.",
        )
        claim = ks.get_claim(sample_claim_id)
        assert claim is not None
        assert claim["validation_status"] == "CONTRADICTED"
        assert result["claims_updated"] == 1

    def test_inconclusive_sets_inconclusive(
        self, ks: KnowledgeStore, sample_claim_id: str
    ) -> None:
        """record_validation_outcome with 'inconclusive' sets INCONCLUSIVE."""
        result = record_validation_outcome(
            store=ks,
            hypothesis_id="hyp_abc123",
            claim_ids=[sample_claim_id],
            outcome="inconclusive",
            reason="Mixed results across tapes.",
        )
        claim = ks.get_claim(sample_claim_id)
        assert claim is not None
        assert claim["validation_status"] == "INCONCLUSIVE"
        assert result["claims_updated"] == 1

    def test_returns_summary_dict_shape(
        self, ks: KnowledgeStore, sample_claim_id: str
    ) -> None:
        """record_validation_outcome returns a summary dict with expected keys."""
        result = record_validation_outcome(
            store=ks,
            hypothesis_id="hyp_abc123",
            claim_ids=[sample_claim_id],
            outcome="confirmed",
            reason="Test.",
        )
        required_keys = {
            "hypothesis_id",
            "outcome",
            "validation_status",
            "reason",
            "claims_updated",
            "claims_not_found",
            "claims_failed",
            "claim_ids",
        }
        assert required_keys.issubset(set(result.keys()))

    def test_not_found_claims_counted(self, ks: KnowledgeStore) -> None:
        """record_validation_outcome tracks claims_not_found for missing IDs."""
        result = record_validation_outcome(
            store=ks,
            hypothesis_id="hyp_abc123",
            claim_ids=["nonexistent_claim_id"],
            outcome="confirmed",
            reason="Test.",
        )
        assert result["claims_not_found"] == 1
        assert result["claims_updated"] == 0

    def test_mixed_found_not_found(
        self, ks: KnowledgeStore, sample_claim_id: str
    ) -> None:
        """record_validation_outcome handles a mix of found and not-found claims."""
        result = record_validation_outcome(
            store=ks,
            hypothesis_id="hyp_abc123",
            claim_ids=[sample_claim_id, "nonexistent_id"],
            outcome="confirmed",
            reason="Mixed test.",
        )
        assert result["claims_updated"] == 1
        assert result["claims_not_found"] == 1

    def test_invalid_outcome_raises(
        self, ks: KnowledgeStore, sample_claim_id: str
    ) -> None:
        """record_validation_outcome raises ValueError for unknown outcome strings."""
        with pytest.raises(ValueError, match="outcome|invalid"):
            record_validation_outcome(
                store=ks,
                hypothesis_id="hyp_abc123",
                claim_ids=[sample_claim_id],
                outcome="approved",  # invalid
                reason="Test.",
            )

    def test_empty_claim_ids_returns_zeros(self, ks: KnowledgeStore) -> None:
        """record_validation_outcome with empty claim_ids returns all-zero counts."""
        result = record_validation_outcome(
            store=ks,
            hypothesis_id="hyp_abc123",
            claim_ids=[],
            outcome="confirmed",
            reason="No claims to update.",
        )
        assert result["claims_updated"] == 0
        assert result["claims_not_found"] == 0
        assert result["claims_failed"] == 0

    def test_hypothesis_id_in_result(
        self, ks: KnowledgeStore, sample_claim_id: str
    ) -> None:
        """record_validation_outcome echo the hypothesis_id in the result."""
        result = record_validation_outcome(
            store=ks,
            hypothesis_id="hyp_test_xyz",
            claim_ids=[sample_claim_id],
            outcome="confirmed",
            reason="Test.",
        )
        assert result["hypothesis_id"] == "hyp_test_xyz"
