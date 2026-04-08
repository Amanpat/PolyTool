"""Tests for RIS Phase 2: Weighted Composite Gate Contract.

Covers:
- Weighted composite score computation
- Per-dimension floor enforcement
- Per-priority threshold gates
- Floor waiver for priority_1
- Fail-closed on parse/scorer failure
- ManualProvider no longer silently auto-accepts (yields REVIEW for P3)
- Config loading from file and env-var overrides
- Evaluator fail-closed exception handling
- Artifact fields include composite_score, simple_sum_score, priority_tier

All tests are fully offline (no network, no Ollama, no file I/O beyond config).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_doc(**kwargs):
    """Build a minimal valid EvalDocument for testing."""
    from packages.research.evaluation.types import EvalDocument
    defaults = dict(
        doc_id="test_doc_p2_001",
        title="Weighted Gate Test Document",
        author="Test Author",
        source_type="manual",
        source_url="https://example.com/test",
        source_publish_date=None,
        body=(
            "This document discusses Avellaneda-Stoikov market making strategies "
            "on Polymarket prediction markets. It covers spread calculations, "
            "inventory risk, and the logit transformation for probability space. "
            "Empirical results from the BTC/ETH crypto pair show consistent edge. "
            "The approach involves careful calibration of kappa and gamma parameters."
        ),
        metadata={},
    )
    defaults.update(kwargs)
    return EvalDocument(**defaults)


def _make_scoring(
    relevance=3, novelty=3, actionability=3, credibility=3,
    priority_tier="priority_3",
    reject_reason=None,
    composite_score=None,
):
    """Build a ScoringResult with explicit composite_score or computed."""
    from packages.research.evaluation.types import ScoringResult
    from packages.research.evaluation.scoring import _compute_composite
    if composite_score is None:
        composite_score = _compute_composite(relevance, novelty, actionability, credibility)
    return ScoringResult(
        relevance=relevance,
        novelty=novelty,
        actionability=actionability,
        credibility=credibility,
        total=relevance + novelty + actionability + credibility,
        composite_score=composite_score,
        priority_tier=priority_tier,
        reject_reason=reject_reason,
        epistemic_type="EMPIRICAL",
        summary="Test summary.",
        key_findings=["Finding 1"],
        eval_model="test_model",
    )


# ---------------------------------------------------------------------------
# Composite score computation
# ---------------------------------------------------------------------------

class TestCompositeScoreComputation:
    def test_composite_formula_mixed_dims(self):
        """rel=4, nov=3, act=3, cred=4 -> 4*0.30+3*0.25+3*0.25+4*0.20 = 1.20+0.75+0.75+0.80 = 3.50"""
        from packages.research.evaluation.scoring import _compute_composite
        result = _compute_composite(4, 3, 3, 4)
        assert abs(result - 3.50) < 0.001

    def test_composite_all_threes(self):
        """All dims=3 -> composite=3.0 (ManualProvider scenario)."""
        from packages.research.evaluation.scoring import _compute_composite
        result = _compute_composite(3, 3, 3, 3)
        assert abs(result - 3.0) < 0.001

    def test_composite_all_fives(self):
        """All dims=5 -> composite=5.0."""
        from packages.research.evaluation.scoring import _compute_composite
        result = _compute_composite(5, 5, 5, 5)
        assert abs(result - 5.0) < 0.001

    def test_composite_all_ones(self):
        """All dims=1 -> composite=1.0."""
        from packages.research.evaluation.scoring import _compute_composite
        result = _compute_composite(1, 1, 1, 1)
        assert abs(result - 1.0) < 0.001

    def test_composite_weights_sum_to_one(self):
        """Weights in default config sum to 1.0."""
        from packages.research.evaluation.config import get_eval_config, reset_eval_config
        reset_eval_config()
        cfg = get_eval_config()
        total_weight = sum(cfg.weights.values())
        assert abs(total_weight - 1.0) < 0.001

    def test_simple_sum_score_equals_total(self):
        """simple_sum_score is an alias for total."""
        r = _make_scoring(relevance=4, novelty=3, actionability=3, credibility=4)
        assert r.simple_sum_score == r.total
        assert r.simple_sum_score == 14


# ---------------------------------------------------------------------------
# Per-priority threshold gate
# ---------------------------------------------------------------------------

class TestPriorityThresholdGate:
    def test_priority_3_accept_at_threshold(self):
        """composite=3.2 for priority_3 -> ACCEPT."""
        r = _make_scoring(priority_tier="priority_3", composite_score=3.2)
        assert r.gate == "ACCEPT"

    def test_priority_3_review_below_threshold(self):
        """composite=3.1 for priority_3 -> REVIEW."""
        r = _make_scoring(priority_tier="priority_3", composite_score=3.1)
        assert r.gate == "REVIEW"

    def test_priority_1_accept_at_threshold(self):
        """composite=2.5 for priority_1 -> ACCEPT (floor waived)."""
        r = _make_scoring(relevance=2, novelty=2, actionability=2, credibility=2,
                          priority_tier="priority_1", composite_score=2.5)
        assert r.gate == "ACCEPT"

    def test_priority_1_review_below_threshold(self):
        """composite=2.4 for priority_1 -> REVIEW."""
        r = _make_scoring(relevance=2, novelty=2, actionability=2, credibility=2,
                          priority_tier="priority_1", composite_score=2.4)
        assert r.gate == "REVIEW"

    def test_priority_2_accept_at_threshold(self):
        """composite=3.0 for priority_2 -> ACCEPT."""
        r = _make_scoring(priority_tier="priority_2", composite_score=3.0)
        assert r.gate == "ACCEPT"

    def test_priority_2_review_below_threshold(self):
        """composite=2.9 for priority_2 -> REVIEW."""
        r = _make_scoring(priority_tier="priority_2", composite_score=2.9)
        assert r.gate == "REVIEW"

    def test_priority_4_accept_at_threshold(self):
        """composite=3.5 for priority_4 -> ACCEPT."""
        r = _make_scoring(priority_tier="priority_4", composite_score=3.5)
        assert r.gate == "ACCEPT"

    def test_priority_4_review_below_threshold(self):
        """composite=3.4 for priority_4 -> REVIEW."""
        r = _make_scoring(priority_tier="priority_4", composite_score=3.4)
        assert r.gate == "REVIEW"


# ---------------------------------------------------------------------------
# Per-dimension floor enforcement
# ---------------------------------------------------------------------------

class TestFloorEnforcement:
    def test_relevance_floor_failure_priority_2(self):
        """relevance=1, credibility=3, priority_2 -> REJECT regardless of composite."""
        r = _make_scoring(relevance=1, novelty=4, actionability=4, credibility=3,
                          priority_tier="priority_2")
        assert r.gate == "REJECT"

    def test_credibility_floor_failure_priority_3(self):
        """credibility=1, priority_3 -> REJECT."""
        r = _make_scoring(relevance=4, novelty=4, actionability=4, credibility=1,
                          priority_tier="priority_3")
        assert r.gate == "REJECT"

    def test_floor_at_minimum_passes(self):
        """relevance=2, credibility=2 (exactly at floor) should not trigger floor failure."""
        r = _make_scoring(relevance=2, novelty=5, actionability=5, credibility=2,
                          priority_tier="priority_3")
        # composite = 2*0.30 + 5*0.25 + 5*0.25 + 2*0.20 = 0.60+1.25+1.25+0.40 = 3.50
        # 3.50 >= 3.2 (P3 threshold) -> ACCEPT (no floor failure since rel=2, cred=2 meet floor)
        assert r.gate == "ACCEPT"

    def test_relevance_below_floor_priority_3(self):
        """relevance=1 for priority_3 -> REJECT regardless of high composite."""
        r = _make_scoring(relevance=1, novelty=5, actionability=5, credibility=5,
                          priority_tier="priority_3")
        assert r.gate == "REJECT"

    def test_credibility_below_floor_priority_4(self):
        """credibility=1 for priority_4 -> REJECT."""
        r = _make_scoring(relevance=5, novelty=5, actionability=5, credibility=1,
                          priority_tier="priority_4")
        assert r.gate == "REJECT"

    def test_priority_1_floor_waived_low_dims(self):
        """priority_1 with relevance=1, credibility=1 still ACCEPTS if composite >= 2.5."""
        # composite = 1*0.30+1*0.25+5*0.25+5*0.20 = 0.30+0.25+1.25+1.00 = 2.80
        r = _make_scoring(relevance=1, novelty=1, actionability=5, credibility=5,
                          priority_tier="priority_1")
        assert r.gate == "ACCEPT"

    def test_priority_1_floor_waived_all_low(self):
        """priority_1 with low dims and composite < 2.5 -> REVIEW (not REJECT from floor)."""
        # composite = 1*0.30+1*0.25+1*0.25+1*0.20 = 1.0 < 2.5 -> REVIEW
        r = _make_scoring(relevance=1, novelty=1, actionability=1, credibility=1,
                          priority_tier="priority_1", composite_score=1.0)
        assert r.gate == "REVIEW"


# ---------------------------------------------------------------------------
# Scorer failure / fail-closed
# ---------------------------------------------------------------------------

class TestScorerFailure:
    def test_reject_reason_scorer_failure_returns_reject(self):
        """reject_reason='scorer_failure' -> gate=REJECT regardless of other fields."""
        r = _make_scoring(relevance=5, novelty=5, actionability=5, credibility=5,
                          priority_tier="priority_1", composite_score=5.0,
                          reject_reason="scorer_failure")
        assert r.gate == "REJECT"

    def test_parse_scoring_response_malformed_json_fails_closed(self):
        """parse_scoring_response on malformed JSON returns ScoringResult with gate=REJECT."""
        from packages.research.evaluation.scoring import parse_scoring_response
        result = parse_scoring_response("not json at all {{{{", "test_model")
        assert result.gate == "REJECT"
        assert result.reject_reason == "scorer_failure"

    def test_parse_scoring_response_non_object_fails_closed(self):
        """parse_scoring_response on JSON array returns gate=REJECT."""
        from packages.research.evaluation.scoring import parse_scoring_response
        result = parse_scoring_response("[1, 2, 3]", "test_model")
        assert result.gate == "REJECT"
        assert result.reject_reason == "scorer_failure"

    def test_parse_scoring_response_empty_string_fails_closed(self):
        """parse_scoring_response on empty string returns gate=REJECT."""
        from packages.research.evaluation.scoring import parse_scoring_response
        result = parse_scoring_response("", "test_model")
        assert result.gate == "REJECT"
        assert result.reject_reason == "scorer_failure"

    def test_parse_scoring_response_malformed_has_composite_score(self):
        """Malformed parse failure still populates composite_score field (0.0)."""
        from packages.research.evaluation.scoring import parse_scoring_response
        result = parse_scoring_response("{bad json", "test_model")
        assert hasattr(result, "composite_score")
        assert result.composite_score == pytest.approx(1.0, abs=0.01)

    def test_parse_scoring_response_missing_dim_defaults_to_1(self):
        """Valid JSON with missing credibility dim: credibility defaults to 1."""
        from packages.research.evaluation.scoring import parse_scoring_response
        data = {
            "relevance": {"score": 4, "rationale": "Relevant"},
            "novelty": {"score": 3, "rationale": "Novel"},
            "actionability": {"score": 3, "rationale": "Actionable"},
            # credibility missing
            "epistemic_type": "EMPIRICAL",
            "summary": "Test",
            "key_findings": [],
            "eval_model": "test",
        }
        result = parse_scoring_response(json.dumps(data), "test")
        assert result.credibility == 1
        assert result.reject_reason is None  # parse succeeded
        # Gate depends on floor: cred=1 fails floor for priority_3 -> REJECT
        assert result.gate == "REJECT"


# ---------------------------------------------------------------------------
# ManualProvider gate behavior
# ---------------------------------------------------------------------------

class TestManualProviderGate:
    def test_manual_provider_all_threes_yields_review_for_priority_3(self):
        """ManualProvider all-3s -> composite=3.0, below P3 threshold 3.2 -> REVIEW."""
        from packages.research.evaluation.providers import ManualProvider
        from packages.research.evaluation.scoring import parse_scoring_response
        provider = ManualProvider()
        doc = _make_doc()
        raw = provider.score(doc, "dummy prompt")
        result = parse_scoring_response(raw, provider.name)
        result.priority_tier = "priority_3"
        assert abs(result.composite_score - 3.0) < 0.001
        assert result.gate == "REVIEW"

    def test_manual_provider_does_not_silently_accept(self):
        """ManualProvider with default priority does NOT auto-accept."""
        from packages.research.evaluation.evaluator import DocumentEvaluator
        doc = _make_doc()
        evaluator = DocumentEvaluator()
        decision = evaluator.evaluate(doc)
        # ManualProvider all-3s -> REVIEW (not ACCEPT)
        assert decision.gate != "ACCEPT"
        assert decision.gate == "REVIEW"

    def test_manual_provider_composite_score_present(self):
        """Scores from ManualProvider have composite_score and simple_sum_score fields."""
        from packages.research.evaluation.evaluator import DocumentEvaluator
        doc = _make_doc()
        evaluator = DocumentEvaluator()
        decision = evaluator.evaluate(doc)
        assert decision.scores is not None
        assert hasattr(decision.scores, "composite_score")
        assert hasattr(decision.scores, "simple_sum_score")
        assert abs(decision.scores.composite_score - 3.0) < 0.001
        assert decision.scores.simple_sum_score == 12


# ---------------------------------------------------------------------------
# Config loading
# ---------------------------------------------------------------------------

class TestConfigLoading:
    def test_default_config_weights(self):
        """Default config weights match spec: rel=0.30, nov=0.25, act=0.25, cred=0.20."""
        from packages.research.evaluation.config import load_eval_config
        cfg = load_eval_config()
        assert abs(cfg.weights["relevance"] - 0.30) < 0.001
        assert abs(cfg.weights["novelty"] - 0.25) < 0.001
        assert abs(cfg.weights["actionability"] - 0.25) < 0.001
        assert abs(cfg.weights["credibility"] - 0.20) < 0.001

    def test_default_config_floors(self):
        """Default floors: relevance>=2, credibility>=2."""
        from packages.research.evaluation.config import load_eval_config
        cfg = load_eval_config()
        assert cfg.floors["relevance"] == 2
        assert cfg.floors["credibility"] == 2

    def test_default_config_thresholds(self):
        """Default thresholds: P1=2.5, P2=3.0, P3=3.2, P4=3.5."""
        from packages.research.evaluation.config import load_eval_config
        cfg = load_eval_config()
        assert abs(cfg.thresholds["priority_1"] - 2.5) < 0.001
        assert abs(cfg.thresholds["priority_2"] - 3.0) < 0.001
        assert abs(cfg.thresholds["priority_3"] - 3.2) < 0.001
        assert abs(cfg.thresholds["priority_4"] - 3.5) < 0.001

    def test_default_priority_tier(self):
        """Default priority tier is priority_3."""
        from packages.research.evaluation.config import load_eval_config
        cfg = load_eval_config()
        assert cfg.default_priority_tier == "priority_3"

    def test_floor_waive_tiers_contains_priority_1(self):
        """Floor waive tiers contains priority_1."""
        from packages.research.evaluation.config import load_eval_config
        cfg = load_eval_config()
        assert "priority_1" in cfg.floor_waive_tiers

    def test_env_var_overrides_relevance_weight(self, monkeypatch):
        """RIS_EVAL_RELEVANCE_WEIGHT env var overrides config file value."""
        from packages.research.evaluation.config import load_eval_config, reset_eval_config
        monkeypatch.setenv("RIS_EVAL_RELEVANCE_WEIGHT", "0.50")
        reset_eval_config()
        try:
            cfg = load_eval_config()
            assert abs(cfg.weights["relevance"] - 0.50) < 0.001
        finally:
            reset_eval_config()

    def test_env_var_overrides_p3_threshold(self, monkeypatch):
        """RIS_EVAL_P3_THRESHOLD env var overrides config file value."""
        from packages.research.evaluation.config import load_eval_config, reset_eval_config
        monkeypatch.setenv("RIS_EVAL_P3_THRESHOLD", "4.0")
        reset_eval_config()
        try:
            cfg = load_eval_config()
            assert abs(cfg.thresholds["priority_3"] - 4.0) < 0.001
        finally:
            reset_eval_config()

    def test_env_var_overrides_credibility_floor(self, monkeypatch):
        """RIS_EVAL_CREDIBILITY_FLOOR env var overrides config file value."""
        from packages.research.evaluation.config import load_eval_config, reset_eval_config
        monkeypatch.setenv("RIS_EVAL_CREDIBILITY_FLOOR", "3")
        reset_eval_config()
        try:
            cfg = load_eval_config()
            assert cfg.floors["credibility"] == 3
        finally:
            reset_eval_config()

    def test_get_eval_config_returns_cached_instance(self):
        """get_eval_config() returns the same object on repeated calls."""
        from packages.research.evaluation.config import get_eval_config, reset_eval_config
        reset_eval_config()
        cfg1 = get_eval_config()
        cfg2 = get_eval_config()
        assert cfg1 is cfg2

    def test_reset_eval_config_clears_cache(self):
        """reset_eval_config() causes the next get_eval_config() to reload."""
        from packages.research.evaluation.config import get_eval_config, reset_eval_config
        reset_eval_config()
        cfg1 = get_eval_config()
        reset_eval_config()
        cfg2 = get_eval_config()
        # They are different objects (new load), but have equal values
        assert cfg1 is not cfg2
        assert cfg1.weights == cfg2.weights


# ---------------------------------------------------------------------------
# Evaluator fail-closed wiring
# ---------------------------------------------------------------------------

class TestEvaluatorFailClosed:
    def test_provider_connection_error_fails_closed(self):
        """OllamaProvider that raises ConnectionError -> evaluator returns gate=REJECT."""
        from packages.research.evaluation.providers import EvalProvider
        from packages.research.evaluation.evaluator import DocumentEvaluator
        from packages.research.evaluation.types import EvalDocument

        class FailingProvider(EvalProvider):
            @property
            def name(self):
                return "failing_test"

            def score(self, doc, prompt):
                raise ConnectionError("Simulated connection failure")

        doc = _make_doc()
        evaluator = DocumentEvaluator(provider=FailingProvider())
        decision = evaluator.evaluate(doc)
        assert decision.gate == "REJECT"
        assert decision.scores is not None
        assert decision.scores.reject_reason == "scorer_failure"

    def test_provider_value_error_fails_closed(self):
        """Provider that raises ValueError -> evaluator returns gate=REJECT."""
        from packages.research.evaluation.providers import EvalProvider
        from packages.research.evaluation.evaluator import DocumentEvaluator

        class ValueErrorProvider(EvalProvider):
            @property
            def name(self):
                return "error_test"

            def score(self, doc, prompt):
                raise ValueError("Simulated value error")

        doc = _make_doc()
        evaluator = DocumentEvaluator(provider=ValueErrorProvider())
        decision = evaluator.evaluate(doc)
        assert decision.gate == "REJECT"
        assert decision.scores.reject_reason == "scorer_failure"

    def test_provider_garbage_output_fails_closed(self):
        """Provider returning non-JSON garbage -> evaluator returns gate=REJECT."""
        from packages.research.evaluation.providers import EvalProvider
        from packages.research.evaluation.evaluator import DocumentEvaluator

        class GarbageProvider(EvalProvider):
            @property
            def name(self):
                return "garbage_test"

            def score(self, doc, prompt):
                return "this is not valid json !!! @@@"

        doc = _make_doc()
        evaluator = DocumentEvaluator(provider=GarbageProvider())
        decision = evaluator.evaluate(doc)
        assert decision.gate == "REJECT"
        assert decision.scores.reject_reason == "scorer_failure"

    def test_evaluator_priority_tier_flows_to_scores(self):
        """priority_tier passed to evaluator flows through to ScoringResult."""
        from packages.research.evaluation.evaluator import DocumentEvaluator
        doc = _make_doc()
        evaluator = DocumentEvaluator(priority_tier="priority_1")
        decision = evaluator.evaluate(doc)
        assert decision.scores is not None
        assert decision.scores.priority_tier == "priority_1"

    def test_evaluator_default_priority_tier_from_config(self):
        """Evaluator with priority_tier=None uses config default (priority_3)."""
        from packages.research.evaluation.evaluator import DocumentEvaluator
        doc = _make_doc()
        evaluator = DocumentEvaluator()
        decision = evaluator.evaluate(doc)
        assert decision.scores is not None
        assert decision.scores.priority_tier == "priority_3"


# ---------------------------------------------------------------------------
# Artifact fields
# ---------------------------------------------------------------------------

class TestArtifactFields:
    def test_artifact_includes_composite_score(self, tmp_path):
        """Persisted artifact includes composite_score field."""
        from packages.research.evaluation.evaluator import DocumentEvaluator
        from packages.research.evaluation.artifacts import load_eval_artifacts
        doc = _make_doc()
        evaluator = DocumentEvaluator(artifacts_dir=tmp_path)
        evaluator.evaluate(doc)
        arts = load_eval_artifacts(tmp_path)
        assert len(arts) == 1
        scores = arts[0].get("scores") or {}
        assert "composite_score" in scores

    def test_artifact_includes_simple_sum_score(self, tmp_path):
        """Persisted artifact includes simple_sum_score field."""
        from packages.research.evaluation.evaluator import DocumentEvaluator
        from packages.research.evaluation.artifacts import load_eval_artifacts
        doc = _make_doc()
        evaluator = DocumentEvaluator(artifacts_dir=tmp_path)
        evaluator.evaluate(doc)
        arts = load_eval_artifacts(tmp_path)
        scores = arts[0].get("scores") or {}
        assert "simple_sum_score" in scores
        assert scores["simple_sum_score"] == 12  # ManualProvider all-3s

    def test_artifact_includes_priority_tier(self, tmp_path):
        """Persisted artifact includes priority_tier field."""
        from packages.research.evaluation.evaluator import DocumentEvaluator
        from packages.research.evaluation.artifacts import load_eval_artifacts
        doc = _make_doc()
        evaluator = DocumentEvaluator(artifacts_dir=tmp_path)
        evaluator.evaluate(doc)
        arts = load_eval_artifacts(tmp_path)
        scores = arts[0].get("scores") or {}
        assert "priority_tier" in scores

    def test_artifact_includes_reject_reason(self, tmp_path):
        """Persisted artifact includes reject_reason field (None for normal evaluation)."""
        from packages.research.evaluation.evaluator import DocumentEvaluator
        from packages.research.evaluation.artifacts import load_eval_artifacts
        doc = _make_doc()
        evaluator = DocumentEvaluator(artifacts_dir=tmp_path)
        evaluator.evaluate(doc)
        arts = load_eval_artifacts(tmp_path)
        scores = arts[0].get("scores") or {}
        assert "reject_reason" in scores


# ---------------------------------------------------------------------------
# evaluate_document convenience function with priority_tier
# ---------------------------------------------------------------------------

class TestEvaluateDocumentPriorityTier:
    def test_evaluate_document_accepts_priority_tier_kwarg(self):
        """evaluate_document() accepts priority_tier kwarg without error."""
        from packages.research.evaluation.evaluator import evaluate_document
        doc = _make_doc()
        decision = evaluate_document(doc, provider_name="manual", priority_tier="priority_1")
        assert decision.gate in ("ACCEPT", "REVIEW", "REJECT")

    def test_evaluate_document_priority_1_uses_lower_threshold(self):
        """priority_tier='priority_1' -> lower threshold (2.5) applied to ManualProvider output."""
        from packages.research.evaluation.evaluator import evaluate_document
        doc = _make_doc()
        # ManualProvider -> all-3s, composite=3.0 >= 2.5 (P1 threshold) -> ACCEPT
        decision = evaluate_document(doc, provider_name="manual", priority_tier="priority_1")
        assert decision.gate == "ACCEPT"

    def test_evaluate_document_priority_3_does_not_accept_manual(self):
        """priority_tier='priority_3' -> composite=3.0 < 3.2 threshold -> REVIEW."""
        from packages.research.evaluation.evaluator import evaluate_document
        doc = _make_doc()
        decision = evaluate_document(doc, provider_name="manual", priority_tier="priority_3")
        assert decision.gate == "REVIEW"
