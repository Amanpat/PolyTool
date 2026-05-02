"""Tests for the L3 cold-start lexical relevance filter.

All tests are offline and deterministic. No network calls, no external DBs.
Uses tmp_path for file I/O.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from packages.research.relevance_filter.scorer import (
    CandidateInput,
    FilterConfig,
    FilterDecision,
    RelevanceScorer,
    load_filter_config,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_config(
    *,
    strong_positive_terms=None,
    positive_terms=None,
    strong_negative_terms=None,
    negative_terms=None,
    strong_positive_weight=2.0,
    positive_weight=1.0,
    strong_negative_weight=-3.0,
    negative_weight=-1.5,
    allow_threshold=0.55,
    review_threshold=0.35,
) -> FilterConfig:
    return FilterConfig(
        version="test",
        strong_positive_terms=strong_positive_terms or [],
        positive_terms=positive_terms or [],
        strong_negative_terms=strong_negative_terms or [],
        negative_terms=negative_terms or [],
        strong_positive_weight=strong_positive_weight,
        positive_weight=positive_weight,
        strong_negative_weight=strong_negative_weight,
        negative_weight=negative_weight,
        allow_threshold=allow_threshold,
        review_threshold=review_threshold,
    )


def _make_candidate(title: str, abstract: str = "", source_id: str = "") -> CandidateInput:
    return CandidateInput(title=title, abstract=abstract, source_id=source_id)


def _write_config_json(path: Path, data: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


_MINIMAL_CONFIG_DICT = {
    "version": "test-v1",
    "strong_positive_weight": 2.0,
    "positive_weight": 1.0,
    "strong_negative_weight": -3.0,
    "negative_weight": -1.5,
    "allow_threshold": 0.55,
    "review_threshold": 0.35,
    "strong_positive_terms": ["prediction market", "stoikov"],
    "positive_terms": ["market microstructure", "liquidity"],
    "strong_negative_terms": ["hastelloy"],
    "negative_terms": ["e-commerce"],
}


# ---------------------------------------------------------------------------
# TestFilterConfig
# ---------------------------------------------------------------------------

class TestFilterConfig:

    def test_load_valid_config(self, tmp_path):
        """Write a minimal config JSON to tmp_path, load it, assert fields."""
        cfg_path = tmp_path / "filter_config.json"
        _write_config_json(cfg_path, _MINIMAL_CONFIG_DICT)
        cfg = load_filter_config(cfg_path)
        assert cfg.version == "test-v1"
        assert cfg.allow_threshold == 0.55
        assert cfg.review_threshold == 0.35
        assert cfg.strong_positive_weight == 2.0
        assert cfg.positive_weight == 1.0
        assert cfg.strong_negative_weight == -3.0
        assert cfg.negative_weight == -1.5
        assert "prediction market" in cfg.strong_positive_terms
        assert "stoikov" in cfg.strong_positive_terms
        assert "market microstructure" in cfg.positive_terms
        assert "hastelloy" in cfg.strong_negative_terms
        assert "e-commerce" in cfg.negative_terms

    def test_load_default_config(self):
        """Load the actual config/research_relevance_filter_v1.json from repo."""
        cfg = load_filter_config()  # uses default path
        assert cfg.version != ""
        assert len(cfg.strong_positive_terms) > 0
        assert len(cfg.positive_terms) > 0
        assert len(cfg.strong_negative_terms) > 0
        assert len(cfg.negative_terms) > 0

    def test_terms_are_lowercased(self, tmp_path):
        """Loaded config has all-lowercase terms regardless of input case."""
        data = dict(_MINIMAL_CONFIG_DICT)
        data["strong_positive_terms"] = ["Prediction Market", "STOIKOV"]
        data["positive_terms"] = ["Market Microstructure"]
        data["strong_negative_terms"] = ["HASTELLOY"]
        data["negative_terms"] = ["E-Commerce"]
        cfg_path = tmp_path / "filter_config.json"
        _write_config_json(cfg_path, data)
        cfg = load_filter_config(cfg_path)
        for term in cfg.strong_positive_terms:
            assert term == term.lower(), f"Term not lowercased: {term!r}"
        for term in cfg.positive_terms:
            assert term == term.lower()
        for term in cfg.strong_negative_terms:
            assert term == term.lower()
        for term in cfg.negative_terms:
            assert term == term.lower()

    def test_missing_config_raises(self, tmp_path):
        """FileNotFoundError when path doesn't exist."""
        bad_path = tmp_path / "nonexistent_config.json"
        with pytest.raises(FileNotFoundError):
            load_filter_config(bad_path)


# ---------------------------------------------------------------------------
# TestRelevanceScorerDecisions
# ---------------------------------------------------------------------------

class TestRelevanceScorerDecisions:

    def test_strong_positive_scores_allow(self):
        """Candidate with strong positive terms scores allow."""
        cfg = _make_config(strong_positive_terms=["prediction market", "avellaneda-stoikov"])
        scorer = RelevanceScorer(cfg)
        candidate = _make_candidate(
            title="prediction market avellaneda-stoikov optimal quoting"
        )
        result = scorer.score(candidate)
        assert result.decision == "allow", f"Expected allow, got {result.decision} (score={result.score})"

    def test_strong_negative_scores_reject(self):
        """Candidate with strong negative terms and no positives scores reject."""
        cfg = _make_config(strong_negative_terms=["hastelloy", "slm fabricated", "fatigue life"])
        scorer = RelevanceScorer(cfg)
        candidate = _make_candidate(
            title="hastelloy slm fabricated fatigue life prediction model"
        )
        result = scorer.score(candidate)
        assert result.decision == "reject", f"Expected reject, got {result.decision} (score={result.score})"

    def test_neutral_scores_review(self):
        """Candidate with weak positive signal but not strong enough for allow scores review."""
        cfg = _make_config(
            positive_terms=["financial market"],
            allow_threshold=0.75,
            review_threshold=0.35,
        )
        scorer = RelevanceScorer(cfg)
        candidate = _make_candidate(
            title="a generic paper about financial market behavior"
        )
        result = scorer.score(candidate)
        # sigmoid(1.0) = 0.731 < 0.75 allow_threshold => review
        assert result.decision == "review", f"Expected review, got {result.decision} (score={result.score})"

    def test_score_in_range(self):
        """Score for any input is in [0.0, 1.0]."""
        cfg = load_filter_config()
        scorer = RelevanceScorer(cfg)
        candidates = [
            _make_candidate("a completely irrelevant paper about nothing"),
            _make_candidate("prediction market avellaneda-stoikov kelly criterion"),
            _make_candidate("hastelloy slm fabricated fatigue life radiomics head and neck cancer"),
            _make_candidate(""),
        ]
        for c in candidates:
            result = scorer.score(c)
            assert 0.0 <= result.score <= 1.0, f"Score out of range: {result.score}"

    def test_deterministic(self):
        """Same input always produces same output."""
        cfg = load_filter_config()
        scorer = RelevanceScorer(cfg)
        candidate = _make_candidate(
            title="prediction market microstructure and limit order book dynamics"
        )
        result1 = scorer.score(candidate)
        result2 = scorer.score(candidate)
        assert result1.decision == result2.decision
        assert result1.score == result2.score
        assert result1.raw_score == result2.raw_score
        assert result1.reason_codes == result2.reason_codes


# ---------------------------------------------------------------------------
# TestRelevanceScorerReasonCodes
# ---------------------------------------------------------------------------

class TestRelevanceScorerReasonCodes:

    def test_reason_codes_include_matched_terms(self):
        """Positive match produces reason_code starting with 'positive:' or 'strong_positive:'."""
        cfg = _make_config(
            strong_positive_terms=["prediction market"],
            positive_terms=["liquidity"],
        )
        scorer = RelevanceScorer(cfg)
        candidate = _make_candidate(title="prediction market liquidity analysis")
        result = scorer.score(candidate)
        code_prefixes = {rc.split(":")[0] for rc in result.reason_codes}
        assert "strong_positive" in code_prefixes or "positive" in code_prefixes
        assert any("prediction market" in rc for rc in result.reason_codes)
        assert any("liquidity" in rc for rc in result.reason_codes)

    def test_no_matches_reports_no_matched_terms(self):
        """Title with no keywords produces reason_codes == ['no_matched_terms']."""
        cfg = _make_config(
            strong_positive_terms=["prediction market"],
            positive_terms=["liquidity"],
            strong_negative_terms=["hastelloy"],
            negative_terms=["e-commerce"],
        )
        scorer = RelevanceScorer(cfg)
        candidate = _make_candidate(title="a completely unrelated paper about cheese")
        result = scorer.score(candidate)
        assert result.reason_codes == ["no_matched_terms"]

    def test_matched_terms_dict_structure(self):
        """matched_terms has all four required keys."""
        cfg = load_filter_config()
        scorer = RelevanceScorer(cfg)
        candidate = _make_candidate(title="prediction market microstructure")
        result = scorer.score(candidate)
        assert set(result.matched_terms.keys()) == {
            "strong_positive",
            "positive",
            "strong_negative",
            "negative",
        }

    def test_negative_terms_in_reason_codes(self):
        """Negative term match appears in reason_codes."""
        cfg = _make_config(negative_terms=["e-commerce"])
        scorer = RelevanceScorer(cfg)
        candidate = _make_candidate(title="counterfactual e-commerce sales prediction")
        result = scorer.score(candidate)
        assert any("negative:e-commerce" in rc for rc in result.reason_codes)


# ---------------------------------------------------------------------------
# TestRelevanceScorerThresholds
# ---------------------------------------------------------------------------

class TestRelevanceScorerThresholds:

    def _sigmoid(self, x: float) -> float:
        return 1.0 / (1.0 + math.exp(-x))

    def test_allow_threshold_boundary(self):
        """A raw_score whose sigmoid is just at or above allow_threshold => allow."""
        # sigmoid(1.5) = ~0.818 > 0.55 => allow
        cfg = _make_config(
            strong_positive_terms=["alpha"],
            strong_positive_weight=1.5,
            allow_threshold=0.55,
            review_threshold=0.35,
        )
        scorer = RelevanceScorer(cfg)
        candidate = _make_candidate(title="alpha term paper")
        result = scorer.score(candidate)
        expected_score = self._sigmoid(1.5)
        assert abs(result.score - round(expected_score, 6)) < 1e-5
        assert result.decision == "allow"

    def test_review_threshold_boundary(self):
        """A raw_score just below allow_threshold but above review_threshold => review."""
        # sigmoid(0.5) ~ 0.622 > 0.55 => allow with standard thresholds
        # Use a higher allow_threshold to force review
        cfg = _make_config(
            positive_terms=["beta"],
            positive_weight=0.5,
            allow_threshold=0.65,   # sigmoid(0.5)=0.622 < 0.65
            review_threshold=0.35,  # sigmoid(0.5)=0.622 > 0.35
        )
        scorer = RelevanceScorer(cfg)
        candidate = _make_candidate(title="beta term paper")
        result = scorer.score(candidate)
        assert result.decision == "review", f"Expected review, got {result.decision} (score={result.score})"

    def test_reject_boundary(self):
        """A raw_score whose sigmoid is below review_threshold => reject."""
        # sigmoid(-2.0) ~ 0.119 < 0.35 => reject
        cfg = _make_config(
            strong_negative_terms=["zeta"],
            strong_negative_weight=-2.0,
            allow_threshold=0.55,
            review_threshold=0.35,
        )
        scorer = RelevanceScorer(cfg)
        candidate = _make_candidate(title="zeta irrelevant paper")
        result = scorer.score(candidate)
        assert result.decision == "reject", f"Expected reject, got {result.decision} (score={result.score})"


# ---------------------------------------------------------------------------
# TestL5CorpusFalseNegatives
# ---------------------------------------------------------------------------

_CLEAR_OFF_TOPIC_TITLES = [
    "Microstructure sensitive fatigue life prediction model for SLM fabricated Hastelloy-X",
    "Radiomics-enhanced Deep Multi-task Learning for Outcome Prediction in Head and Neck Cancer",
    "Counterfactual Multi-task Learning for Delayed Conversion Modeling in E-commerce Sales Prediction",
]

_QA_PAPER_TITLES = [
    "SoK: Market Microstructure for Decentralized Prediction Markets (DePMs)",
    "Toward Black Scholes for Prediction Markets: A Unified Kernel and Market Maker's Handbook",
    "Limit Order Book Dynamics in Matching Markets: Microstructure, Spread, and Execution Slippage",
    "Semi Markov model for market microstructure",
    "Interpretable Hypothesis-Driven Trading: A Rigorous Walk-Forward Validation Framework",
    "TradeFM: A Generative Foundation Model for Trade-flow and Market Microstructure",
    "The Inelastic Market Hypothesis: A Microstructural Interpretation",
    "How Market Ecology Explains Market Malfunction",
    "High frequency market microstructure noise estimates and liquidity measures",
    "Systemic Risk in Market Microstructure of Crude Oil and Gasoline Futures Prices",
    "Foreign Exchange Market Microstructure and the WM/Reuters 4pm Fix",
]


class TestL5CorpusFalseNegatives:

    def test_clear_off_topic_papers_rejected(self):
        """Clear off-topic paper titles (Hastelloy-X, head/neck cancer, e-commerce) all get REJECT."""
        cfg = load_filter_config()
        scorer = RelevanceScorer(cfg)
        for title in _CLEAR_OFF_TOPIC_TITLES:
            candidate = _make_candidate(title=title)
            result = scorer.score(candidate)
            assert result.decision == "reject", (
                f"Expected REJECT for off-topic title: {title!r} "
                f"(got {result.decision}, score={result.score}, reason_codes={result.reason_codes})"
            )

    def test_qa_paper_titles_not_rejected(self):
        """Known QA paper titles must not get REJECT (ALLOW or REVIEW acceptable)."""
        cfg = load_filter_config()
        scorer = RelevanceScorer(cfg)
        for title in _QA_PAPER_TITLES:
            candidate = _make_candidate(title=title)
            result = scorer.score(candidate)
            assert result.decision != "reject", (
                f"False negative: QA paper got REJECT: {title!r} "
                f"(score={result.score}, reason_codes={result.reason_codes})"
            )

    def test_prediction_market_titles_allow(self):
        """Papers with 'prediction market' in title should score ALLOW."""
        cfg = load_filter_config()
        scorer = RelevanceScorer(cfg)
        titles_with_pm = [
            t for t in _QA_PAPER_TITLES if "prediction market" in t.lower()
        ]
        assert len(titles_with_pm) > 0, "No QA titles containing 'prediction market' found"
        for title in titles_with_pm:
            candidate = _make_candidate(title=title)
            result = scorer.score(candidate)
            assert result.decision == "allow", (
                f"Expected ALLOW for prediction market title: {title!r} "
                f"(got {result.decision}, score={result.score})"
            )

    def test_microstructure_papers_allow(self):
        """Papers with 'market microstructure' in title should score ALLOW."""
        cfg = load_filter_config()
        scorer = RelevanceScorer(cfg)
        titles_with_ms = [
            t for t in _QA_PAPER_TITLES if "microstructure" in t.lower()
        ]
        assert len(titles_with_ms) > 0, "No QA titles containing 'microstructure' found"
        for title in titles_with_ms:
            candidate = _make_candidate(title=title)
            result = scorer.score(candidate)
            assert result.decision == "allow", (
                f"Expected ALLOW for microstructure title: {title!r} "
                f"(got {result.decision}, score={result.score})"
            )
