"""Offline tests for RIS v1 evaluation gate.

Tests cover: hard stops, scoring result, provider behavior, evaluator pipeline,
source-family guidance, and convenience functions. All fully offline (no network,
no LLM, no Chroma).
"""

from __future__ import annotations

import json

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_doc(**kwargs):
    """Build a minimal valid EvalDocument for testing."""
    from packages.research.evaluation.types import EvalDocument
    defaults = dict(
        doc_id="test_doc_001",
        title="Test Document",
        author="Test Author",
        source_type="manual",
        source_url="https://example.com/test",
        source_publish_date=None,
        body="This is a sufficiently long test body for evaluation gate testing purposes. "
             "It contains enough text to pass the hard stop minimum length check and "
             "is clearly English prose without any encoding issues.",
        metadata={},
    )
    defaults.update(kwargs)
    return EvalDocument(**defaults)


# ---------------------------------------------------------------------------
# Hard Stop Tests
# ---------------------------------------------------------------------------

class TestHardStops:
    def test_empty_body_none(self):
        from packages.research.evaluation.hard_stops import check_hard_stops
        from packages.research.evaluation.types import EvalDocument
        doc = _make_doc(body=None)
        result = check_hard_stops(doc)
        assert result.passed is False
        assert result.stop_type == "empty_body"
        assert result.reason is not None

    def test_empty_body_empty_string(self):
        from packages.research.evaluation.hard_stops import check_hard_stops
        doc = _make_doc(body="")
        result = check_hard_stops(doc)
        assert result.passed is False
        assert result.stop_type == "empty_body"

    def test_empty_body_whitespace_only(self):
        from packages.research.evaluation.hard_stops import check_hard_stops
        doc = _make_doc(body="   \n\t  ")
        result = check_hard_stops(doc)
        assert result.passed is False
        assert result.stop_type == "empty_body"

    def test_too_short(self):
        from packages.research.evaluation.hard_stops import check_hard_stops
        doc = _make_doc(body="Too short.")
        result = check_hard_stops(doc)
        assert result.passed is False
        assert result.stop_type == "too_short"

    def test_too_short_exactly_49_chars(self):
        from packages.research.evaluation.hard_stops import check_hard_stops
        # 49 chars — should fail
        doc = _make_doc(body="A" * 49)
        result = check_hard_stops(doc)
        assert result.passed is False
        assert result.stop_type == "too_short"

    def test_exactly_50_chars_passes_length(self):
        from packages.research.evaluation.hard_stops import check_hard_stops
        # 50 ASCII chars — should pass too_short; encoding_garbage check: 0% non-ASCII
        doc = _make_doc(body="A" * 50)
        result = check_hard_stops(doc)
        # Should not fail on too_short — but may fail spam check (all-caps)
        assert result.stop_type != "too_short"

    def test_encoding_garbage(self):
        from packages.research.evaluation.hard_stops import check_hard_stops
        # 85% non-ASCII characters
        ascii_part = "Hello " * 5  # 30 chars
        garbage = "\x80\x81\x82\x83\x84\x85\x86\x87\x88\x89\x8a\x8b\x8c\x8d\x8e\x8f\x90\x91\x92\x93" * 10  # 200 non-ASCII
        doc = _make_doc(body=ascii_part + garbage)
        result = check_hard_stops(doc)
        assert result.passed is False
        assert result.stop_type == "encoding_garbage"

    def test_spam_all_caps(self):
        from packages.research.evaluation.hard_stops import check_hard_stops
        # >60% uppercase alpha chars, sufficient length
        doc = _make_doc(body="AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA" +
                              "aaa normal")
        result = check_hard_stops(doc)
        assert result.passed is False
        assert result.stop_type == "spam_malformed"

    def test_spam_repeated_urls(self):
        from packages.research.evaluation.hard_stops import check_hard_stops
        # Same URL appearing 4+ times
        url = "https://example.com/product"
        doc = _make_doc(body=(url + " ") * 5 + "normal text padding " * 3)
        result = check_hard_stops(doc)
        assert result.passed is False
        assert result.stop_type == "spam_malformed"

    def test_valid_english_paragraph_passes(self):
        from packages.research.evaluation.hard_stops import check_hard_stops
        doc = _make_doc()  # default is a valid body
        result = check_hard_stops(doc)
        assert result.passed is True
        assert result.stop_type is None
        assert result.reason is None


# ---------------------------------------------------------------------------
# ScoringResult gate property
# ---------------------------------------------------------------------------

class TestScoringResultGate:
    def _make_scoring(self, composite: float, relevance: int = 3, credibility: int = 3,
                      priority_tier: str = "priority_3", reject_reason=None):
        """Build a ScoringResult with explicit composite_score for gate testing.

        Phase 2: gate is driven by composite_score + floors + priority_tier.
        The total field is retained as a diagnostic but does not drive gate decisions.
        """
        from packages.research.evaluation.types import ScoringResult
        return ScoringResult(
            relevance=relevance, novelty=3, actionability=3, credibility=credibility,
            total=relevance + 3 + 3 + credibility,
            composite_score=composite,
            priority_tier=priority_tier,
            reject_reason=reject_reason,
            epistemic_type="EMPIRICAL",
            summary="Test summary.",
            key_findings=["Finding 1"],
            eval_model="manual_placeholder",
        )

    def test_gate_accept_above_p3_threshold(self):
        # composite >= 3.2 and floors met -> ACCEPT for priority_3
        r = self._make_scoring(composite=3.5)
        assert r.gate == "ACCEPT"

    def test_gate_accept_at_p3_threshold(self):
        # composite == 3.2 exactly -> ACCEPT
        r = self._make_scoring(composite=3.2)
        assert r.gate == "ACCEPT"

    def test_gate_review_below_p3_threshold(self):
        # composite=3.0 < 3.2 -> REVIEW (floors still met)
        r = self._make_scoring(composite=3.0)
        assert r.gate == "REVIEW"

    def test_gate_review_at_2_5(self):
        # composite=2.5 < 3.2 -> REVIEW
        r = self._make_scoring(composite=2.5)
        assert r.gate == "REVIEW"

    def test_gate_reject_floor_fail_relevance(self):
        # relevance=1 fails floor (floor=2) -> REJECT
        r = self._make_scoring(composite=3.5, relevance=1)
        assert r.gate == "REJECT"

    def test_gate_reject_floor_fail_credibility(self):
        # credibility=1 fails floor (floor=2) -> REJECT
        r = self._make_scoring(composite=3.5, credibility=1)
        assert r.gate == "REJECT"

    def test_gate_reject_scorer_failure(self):
        # reject_reason="scorer_failure" always REJECTs regardless of composite
        r = self._make_scoring(composite=4.5, reject_reason="scorer_failure")
        assert r.gate == "REJECT"

    def test_gate_priority_1_waives_floors(self):
        # priority_1 with floor-failing relevance=1 -> floors waived -> gate by threshold
        r = self._make_scoring(composite=3.5, relevance=1, priority_tier="priority_1")
        assert r.gate == "ACCEPT"

    def test_gate_priority_1_low_composite(self):
        # priority_1 threshold=2.5; composite=2.6 -> ACCEPT (no floor check)
        r = self._make_scoring(composite=2.6, relevance=1, priority_tier="priority_1")
        assert r.gate == "ACCEPT"


# ---------------------------------------------------------------------------
# ManualProvider
# ---------------------------------------------------------------------------

class TestManualProvider:
    def test_returns_valid_json(self):
        from packages.research.evaluation.providers import ManualProvider
        doc = _make_doc()
        prompt = "dummy prompt"
        provider = ManualProvider()
        raw = provider.score(doc, prompt)
        data = json.loads(raw)  # must not raise
        assert isinstance(data, dict)

    def test_all_scores_are_3(self):
        from packages.research.evaluation.providers import ManualProvider
        doc = _make_doc()
        provider = ManualProvider()
        raw = provider.score(doc, "")
        data = json.loads(raw)
        for dim in ("relevance", "novelty", "actionability", "credibility"):
            assert data[dim]["score"] == 3

    def test_eval_model_is_manual_placeholder(self):
        from packages.research.evaluation.providers import ManualProvider
        doc = _make_doc()
        provider = ManualProvider()
        raw = provider.score(doc, "")
        data = json.loads(raw)
        assert data.get("eval_model") == "manual_placeholder"

    def test_name_property(self):
        from packages.research.evaluation.providers import ManualProvider
        assert ManualProvider().name == "manual"

    def test_total_is_12(self):
        from packages.research.evaluation.providers import ManualProvider
        doc = _make_doc()
        provider = ManualProvider()
        raw = provider.score(doc, "")
        data = json.loads(raw)
        assert data.get("total") == 12


# ---------------------------------------------------------------------------
# DocumentEvaluator
# ---------------------------------------------------------------------------

class TestDocumentEvaluator:
    def test_hard_stop_returns_reject_no_scoring(self):
        from packages.research.evaluation.evaluator import DocumentEvaluator
        doc = _make_doc(body="")
        evaluator = DocumentEvaluator()
        decision = evaluator.evaluate(doc)
        assert decision.gate == "REJECT"
        assert decision.scores is None
        assert decision.hard_stop is not None
        assert decision.hard_stop.passed is False

    def test_valid_doc_with_manual_provider_returns_review(self):
        """ManualProvider returns all-3s -> composite=3.0 < P3 threshold 3.2 -> REVIEW.

        Phase 2 behavior: ManualProvider no longer auto-accepts. All-3s composite
        (3*0.30 + 3*0.20 + 3*0.20 + 3*0.30 = 3.0) falls below the priority_3
        threshold of 3.2, so documents score as REVIEW rather than ACCEPT.
        This forces operator review instead of silent acceptance.
        """
        from packages.research.evaluation.evaluator import DocumentEvaluator
        doc = _make_doc()
        evaluator = DocumentEvaluator()
        decision = evaluator.evaluate(doc)
        assert decision.gate == "REVIEW"
        assert decision.scores is not None
        assert decision.hard_stop is not None
        assert decision.hard_stop.passed is True

    def test_decision_has_doc_id(self):
        from packages.research.evaluation.evaluator import DocumentEvaluator
        doc = _make_doc(doc_id="my_doc_xyz")
        decision = DocumentEvaluator().evaluate(doc)
        assert decision.doc_id == "my_doc_xyz"

    def test_decision_has_timestamp(self):
        from packages.research.evaluation.evaluator import DocumentEvaluator
        doc = _make_doc()
        decision = DocumentEvaluator().evaluate(doc)
        assert decision.timestamp is not None
        assert "T" in decision.timestamp  # ISO format check


# ---------------------------------------------------------------------------
# Source-family guidance
# ---------------------------------------------------------------------------

class TestSourceFamilyGuidance:
    def test_all_families_have_guidance(self):
        from packages.research.evaluation.types import SOURCE_FAMILIES, SOURCE_FAMILY_GUIDANCE
        families = set(SOURCE_FAMILIES.values())
        for family in families:
            assert family in SOURCE_FAMILY_GUIDANCE, f"Missing guidance for family: {family}"
            assert len(SOURCE_FAMILY_GUIDANCE[family]) > 10

    def test_arxiv_maps_to_academic(self):
        from packages.research.evaluation.types import SOURCE_FAMILIES
        assert SOURCE_FAMILIES.get("arxiv") == "academic"

    def test_reddit_maps_to_forum_social(self):
        from packages.research.evaluation.types import SOURCE_FAMILIES
        assert SOURCE_FAMILIES.get("reddit") == "forum_social"

    def test_github_maps_to_github(self):
        from packages.research.evaluation.types import SOURCE_FAMILIES
        assert SOURCE_FAMILIES.get("github") == "github"


# ---------------------------------------------------------------------------
# build_scoring_prompt
# ---------------------------------------------------------------------------

class TestBuildScoringPrompt:
    def test_includes_source_family_guidance(self):
        from packages.research.evaluation.scoring import build_scoring_prompt
        doc = _make_doc(source_type="arxiv")
        prompt = build_scoring_prompt(doc)
        # Should include guidance about academic sources
        assert "academic" in prompt.lower() or "peer-reviewed" in prompt.lower()

    def test_includes_body_text(self):
        from packages.research.evaluation.scoring import build_scoring_prompt
        doc = _make_doc(body="This is the unique body content xyz123.")
        prompt = build_scoring_prompt(doc)
        assert "xyz123" in prompt

    def test_includes_rubric_dimensions(self):
        from packages.research.evaluation.scoring import build_scoring_prompt
        doc = _make_doc()
        prompt = build_scoring_prompt(doc)
        for dim in ("relevance", "novelty", "actionability", "credibility"):
            assert dim.lower() in prompt.lower()


# ---------------------------------------------------------------------------
# parse_scoring_response
# ---------------------------------------------------------------------------

class TestParseScoringResponse:
    def test_valid_json_parses_correctly(self):
        from packages.research.evaluation.scoring import parse_scoring_response
        data = {
            "relevance": {"score": 4, "rationale": "Relevant"},
            "novelty": {"score": 3, "rationale": "Moderate novelty"},
            "actionability": {"score": 5, "rationale": "Highly actionable"},
            "credibility": {"score": 2, "rationale": "Weak source"},
            "epistemic_type": "EMPIRICAL",
            "summary": "Good paper.",
            "key_findings": ["Finding A"],
            "eval_model": "test_model",
        }
        result = parse_scoring_response(json.dumps(data), "test_model")
        assert result.relevance == 4
        assert result.novelty == 3
        assert result.actionability == 5
        assert result.credibility == 2
        assert result.total == 14
        assert result.epistemic_type == "EMPIRICAL"
        assert result.eval_model == "test_model"

    def test_malformed_json_returns_defaults(self):
        from packages.research.evaluation.scoring import parse_scoring_response
        result = parse_scoring_response("not valid json {{{{", "test_model")
        # Should not raise; should return defaults
        assert result.relevance == 1
        assert result.total >= 4  # all 1s = 4


# ---------------------------------------------------------------------------
# evaluate_document convenience function
# ---------------------------------------------------------------------------

class TestEvaluateDocumentConvenience:
    def test_end_to_end_manual_provider(self):
        from packages.research.evaluation.evaluator import evaluate_document
        doc = _make_doc()
        decision = evaluate_document(doc, provider_name="manual")
        assert decision.gate in ("ACCEPT", "REVIEW", "REJECT")
        assert decision.doc_id == doc.doc_id

    def test_get_provider_factory_manual(self):
        from packages.research.evaluation.providers import get_provider, ManualProvider
        provider = get_provider("manual")
        assert isinstance(provider, ManualProvider)

    def test_get_provider_factory_unknown_raises(self):
        from packages.research.evaluation.providers import get_provider
        with pytest.raises(ValueError, match="unknown provider"):
            get_provider("nonexistent_provider_xyz")
