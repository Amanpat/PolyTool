"""WP1-A contract tests: canonical scoring weights.

Verifies that the live runtime uses rel=0.30, cred=0.30, nov=0.20, act=0.20
everywhere it matters: config defaults, JSON config load, and composite formula.
"""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _reset_config():
    """Reset the singleton cache before and after each test."""
    from packages.research.evaluation.config import reset_eval_config
    reset_eval_config()
    yield
    reset_eval_config()


# ---------------------------------------------------------------------------
# Config default weights (hardcoded _DEFAULT_WEIGHTS)
# ---------------------------------------------------------------------------

class TestDefaultWeights:
    def test_novelty_default_is_0_20(self):
        from packages.research.evaluation.config import _DEFAULT_WEIGHTS
        assert abs(_DEFAULT_WEIGHTS["novelty"] - 0.20) < 1e-9

    def test_actionability_default_is_0_20(self):
        from packages.research.evaluation.config import _DEFAULT_WEIGHTS
        assert abs(_DEFAULT_WEIGHTS["actionability"] - 0.20) < 1e-9

    def test_credibility_default_is_0_30(self):
        from packages.research.evaluation.config import _DEFAULT_WEIGHTS
        assert abs(_DEFAULT_WEIGHTS["credibility"] - 0.30) < 1e-9

    def test_relevance_default_is_0_30(self):
        from packages.research.evaluation.config import _DEFAULT_WEIGHTS
        assert abs(_DEFAULT_WEIGHTS["relevance"] - 0.30) < 1e-9

    def test_weights_sum_to_one(self):
        from packages.research.evaluation.config import _DEFAULT_WEIGHTS
        assert abs(sum(_DEFAULT_WEIGHTS.values()) - 1.0) < 1e-9


# ---------------------------------------------------------------------------
# Loaded config weights (via JSON config file)
# ---------------------------------------------------------------------------

class TestLoadedConfigWeights:
    def test_loaded_novelty_is_0_20(self):
        from packages.research.evaluation.config import load_eval_config
        cfg = load_eval_config()
        assert abs(cfg.weights["novelty"] - 0.20) < 0.001

    def test_loaded_actionability_is_0_20(self):
        from packages.research.evaluation.config import load_eval_config
        cfg = load_eval_config()
        assert abs(cfg.weights["actionability"] - 0.20) < 0.001

    def test_loaded_credibility_is_0_30(self):
        from packages.research.evaluation.config import load_eval_config
        cfg = load_eval_config()
        assert abs(cfg.weights["credibility"] - 0.30) < 0.001

    def test_loaded_relevance_is_0_30(self):
        from packages.research.evaluation.config import load_eval_config
        cfg = load_eval_config()
        assert abs(cfg.weights["relevance"] - 0.30) < 0.001

    def test_loaded_weights_sum_to_one(self):
        from packages.research.evaluation.config import load_eval_config
        cfg = load_eval_config()
        assert abs(sum(cfg.weights.values()) - 1.0) < 0.001


# ---------------------------------------------------------------------------
# Composite formula uses new weights
# ---------------------------------------------------------------------------

class TestCompositeFormula:
    def test_credibility_weighted_at_0_30(self):
        """A doc with high credibility only (rel=1,nov=1,act=1,cred=5) should
        reflect cred weight=0.30: composite = 1*0.30+1*0.20+1*0.20+5*0.30 = 2.20"""
        from packages.research.evaluation.scoring import _compute_composite
        result = _compute_composite(1, 1, 1, 5)
        assert abs(result - 2.20) < 0.001

    def test_novelty_weighted_at_0_20(self):
        """High novelty only (rel=1,nov=5,act=1,cred=1):
        1*0.30+5*0.20+1*0.20+1*0.30 = 1.80"""
        from packages.research.evaluation.scoring import _compute_composite
        result = _compute_composite(1, 5, 1, 1)
        assert abs(result - 1.80) < 0.001

    def test_actionability_weighted_at_0_20(self):
        """High actionability only (rel=1,nov=1,act=5,cred=1):
        1*0.30+1*0.20+5*0.20+1*0.30 = 1.80"""
        from packages.research.evaluation.scoring import _compute_composite
        result = _compute_composite(1, 1, 5, 1)
        assert abs(result - 1.80) < 0.001

    def test_relevance_weighted_at_0_30(self):
        """High relevance only (rel=5,nov=1,act=1,cred=1):
        5*0.30+1*0.20+1*0.20+1*0.30 = 2.20"""
        from packages.research.evaluation.scoring import _compute_composite
        result = _compute_composite(5, 1, 1, 1)
        assert abs(result - 2.20) < 0.001

    def test_novelty_and_actionability_equal_weight(self):
        """nov and act carry equal weight — swapping them produces same composite."""
        from packages.research.evaluation.scoring import _compute_composite
        r1 = _compute_composite(3, 4, 2, 3)
        r2 = _compute_composite(3, 2, 4, 3)
        assert abs(r1 - r2) < 1e-9

    def test_relevance_and_credibility_equal_weight(self):
        """rel and cred carry equal weight — swapping them produces same composite."""
        from packages.research.evaluation.scoring import _compute_composite
        r1 = _compute_composite(5, 3, 3, 1)
        r2 = _compute_composite(1, 3, 3, 5)
        assert abs(r1 - r2) < 1e-9

    def test_uniform_dims_always_equals_dim_value(self):
        """With weights summing to 1.0, uniform dims produce composite == dim value."""
        from packages.research.evaluation.scoring import _compute_composite
        for v in (1, 2, 3, 4, 5):
            assert abs(_compute_composite(v, v, v, v) - v) < 1e-9


# ---------------------------------------------------------------------------
# Prompt text embeds new formula
# ---------------------------------------------------------------------------

class TestPromptFormula:
    def test_prompt_contains_new_credibility_weight(self):
        from packages.research.evaluation.scoring import build_scoring_prompt
        from packages.research.evaluation.types import EvalDocument
        doc = EvalDocument(
            doc_id="wp1a-test",
            title="Test",
            body="body",
            source_type="manual",
            author="tester",
            source_url=None,
            source_publish_date=None,
        )
        prompt = build_scoring_prompt(doc)
        assert "credibility*0.30" in prompt

    def test_prompt_contains_new_novelty_weight(self):
        from packages.research.evaluation.scoring import build_scoring_prompt
        from packages.research.evaluation.types import EvalDocument
        doc = EvalDocument(
            doc_id="wp1a-test",
            title="Test",
            body="body",
            source_type="manual",
            author="tester",
            source_url=None,
            source_publish_date=None,
        )
        prompt = build_scoring_prompt(doc)
        assert "novelty*0.20" in prompt

    def test_prompt_does_not_contain_old_weights(self):
        from packages.research.evaluation.scoring import build_scoring_prompt
        from packages.research.evaluation.types import EvalDocument
        doc = EvalDocument(
            doc_id="wp1a-test",
            title="Test",
            body="body",
            source_type="manual",
            author="tester",
            source_url=None,
            source_publish_date=None,
        )
        prompt = build_scoring_prompt(doc)
        # Old formula had credibility*0.20 and novelty*0.25 — neither should appear
        assert "credibility*0.20" not in prompt
        assert "novelty*0.25" not in prompt
        assert "actionability*0.25" not in prompt
