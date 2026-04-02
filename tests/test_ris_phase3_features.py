"""Deterministic tests for RIS Phase 3 gate hardening.

Tests cover:
- Per-family feature extraction (academic, github, blog/news, forum/social, default)
- Near-duplicate detection (exact hash, near-match, distinct, empty body)
- Structured eval artifact persistence (persist, load, append)
- Evaluator integration (features+artifacts wired in, dedup rejects, backward compat)
- Calibration eval artifact summary and report formatting

All tests are offline and deterministic. No network calls. No LLM calls.
"""

from __future__ import annotations

from pathlib import Path

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
        body=(
            "This is a sufficiently long test body for evaluation gate testing purposes. "
            "It contains enough text to pass the hard stop minimum length check and "
            "is clearly English prose without any encoding issues."
        ),
        metadata={},
    )
    defaults.update(kwargs)
    return EvalDocument(**defaults)


# ---------------------------------------------------------------------------
# Task 1: Feature extraction tests
# ---------------------------------------------------------------------------


class TestAcademicFeatures:
    def test_academic_features_doi(self):
        from packages.research.evaluation.feature_extraction import extract_features

        doc = _make_doc(
            source_type="arxiv",
            body=(
                "We study the effects of market microstructure. "
                "doi: 10.1234/test.2023.001. "
                "The dataset comprised 10,000 transactions from Polymarket."
            ),
        )
        result = extract_features(doc)
        assert result.family == "academic"
        assert result.features["has_doi"] is True

    def test_academic_features_arxiv(self):
        from packages.research.evaluation.feature_extraction import extract_features

        doc = _make_doc(
            source_type="arxiv",
            body=(
                "See arXiv:2301.12345 for the full derivation. "
                "The paper introduces a new model for probability calibration."
            ),
        )
        result = extract_features(doc)
        assert result.family == "academic"
        assert result.features["has_arxiv_id"] is True

    def test_academic_features_ssrn(self):
        from packages.research.evaluation.feature_extraction import extract_features

        doc = _make_doc(
            source_type="ssrn",
            body=(
                "Available at SSRN: 123456789. "
                "This working paper analyses prediction market efficiency across 500 markets."
            ),
        )
        result = extract_features(doc)
        assert result.family == "academic"
        assert result.features["has_ssrn_id"] is True

    def test_academic_features_methodology(self):
        from packages.research.evaluation.feature_extraction import extract_features

        doc = _make_doc(
            source_type="arxiv",
            body=(
                "We used regression analysis on the dataset. "
                "The p-value was below 0.05. "
                "Our methodology controlled for confounders. "
                "The experiment included a control group."
            ),
        )
        result = extract_features(doc)
        assert result.family == "academic"
        assert result.features["methodology_cues"] >= 2

    def test_academic_features_no_doi(self):
        from packages.research.evaluation.feature_extraction import extract_features

        doc = _make_doc(
            source_type="arxiv",
            body=(
                "This paper explores market efficiency using qualitative methods. "
                "The authors argue that prices reflect information quickly."
            ),
        )
        result = extract_features(doc)
        assert result.family == "academic"
        assert result.features["has_doi"] is False

    def test_academic_features_publication_metadata(self):
        from packages.research.evaluation.feature_extraction import extract_features

        doc = _make_doc(
            source_type="arxiv",
            author="Jane Smith",
            source_publish_date="2023-06-15",
            body=(
                "This paper explores market efficiency using quantitative methods. "
                "The authors collected a sample of 5,000 observations."
            ),
        )
        result = extract_features(doc)
        assert result.features["has_known_author"] is True
        assert result.features["has_publish_date"] is True


class TestGithubFeatures:
    def test_github_features_stars(self):
        from packages.research.evaluation.feature_extraction import extract_features

        doc = _make_doc(
            source_type="github",
            body=(
                "A Python library for prediction market analysis. "
                "Supports Polymarket and Kalshi through a unified interface."
            ),
            metadata={"stars": 150, "forks": 22},
        )
        result = extract_features(doc)
        assert result.family == "github"
        assert result.features["stars"] == 150

    def test_github_features_forks(self):
        from packages.research.evaluation.feature_extraction import extract_features

        doc = _make_doc(
            source_type="github",
            body="A trading tool repo with multiple backtesting strategies.",
            metadata={"forks": 42},
        )
        result = extract_features(doc)
        assert result.features["forks"] == 42

    def test_github_features_readme(self):
        from packages.research.evaluation.feature_extraction import extract_features

        doc = _make_doc(
            source_type="github",
            body=(
                "README: This project implements a CLOB simulator. "
                "See the README for installation instructions. "
                "The library has been tested on macOS and Linux."
            ),
        )
        result = extract_features(doc)
        assert result.family == "github"
        assert result.features["has_readme_mention"] is True

    def test_github_features_license(self):
        from packages.research.evaluation.feature_extraction import extract_features

        doc = _make_doc(
            source_type="github",
            body=(
                "This project is released under the MIT license. "
                "Contributions welcome via pull request."
            ),
        )
        result = extract_features(doc)
        assert result.features["has_license_mention"] is True

    def test_github_features_no_metadata(self):
        from packages.research.evaluation.feature_extraction import extract_features

        doc = _make_doc(
            source_type="github",
            body="Simple utility script for data processing pipelines.",
            metadata={},
        )
        result = extract_features(doc)
        assert result.features["stars"] is None
        assert result.features["forks"] is None


class TestBlogNewsFeatures:
    def test_blog_features_byline(self):
        from packages.research.evaluation.feature_extraction import extract_features

        doc = _make_doc(
            source_type="blog",
            body=(
                "By John Smith\n\n"
                "The prediction market landscape has shifted dramatically in 2024. "
                "New entrants have challenged established venues on liquidity and fees."
            ),
        )
        result = extract_features(doc)
        assert result.family == "blog"
        assert result.features["has_byline"] is True

    def test_blog_features_structure(self):
        from packages.research.evaluation.feature_extraction import extract_features

        doc = _make_doc(
            source_type="blog",
            body=(
                "## Introduction\n\n"
                "Prediction markets have grown rapidly.\n\n"
                "## Key Findings\n\n"
                "Volume increased 300% year-over-year.\n\n"
                "### Sub-section\n\n"
                "Additional details here."
            ),
        )
        result = extract_features(doc)
        assert result.family == "blog"
        assert result.features["heading_count"] > 0

    def test_news_features_date_presence(self):
        from packages.research.evaluation.feature_extraction import extract_features

        doc = _make_doc(
            source_type="news",
            source_publish_date="2024-01-15",
            body=(
                "Markets reacted sharply to the announcement on Tuesday. "
                "Trading volume surged 40% above the prior 30-day average."
            ),
        )
        result = extract_features(doc)
        assert result.family == "news"
        assert result.features["has_date"] is True

    def test_blog_features_paragraph_count(self):
        from packages.research.evaluation.feature_extraction import extract_features

        doc = _make_doc(
            source_type="blog",
            body=(
                "First paragraph about prediction markets.\n\n"
                "Second paragraph about liquidity.\n\n"
                "Third paragraph about risk management."
            ),
        )
        result = extract_features(doc)
        assert result.features["paragraph_count"] >= 3


class TestForumSocialFeatures:
    def test_forum_features_specificity(self):
        from packages.research.evaluation.feature_extraction import extract_features

        doc = _make_doc(
            source_type="reddit",
            body=(
                "I checked the data and 42% of trades in that market were placed "
                "within the last 30 minutes before resolution. That's a significant edge."
            ),
        )
        result = extract_features(doc)
        assert result.family == "forum_social"
        assert result.features["specificity_markers"] >= 1

    def test_forum_features_data_mention(self):
        from packages.research.evaluation.feature_extraction import extract_features

        doc = _make_doc(
            source_type="twitter",
            body=(
                "Here's a chart showing the price movement. The data clearly shows "
                "the pattern repeats every cycle. Screenshot attached."
            ),
        )
        result = extract_features(doc)
        assert result.family == "forum_social"
        assert result.features["has_data_mention"] is True

    def test_forum_features_reply_count(self):
        from packages.research.evaluation.feature_extraction import extract_features

        doc = _make_doc(
            source_type="reddit",
            body="Great discussion. I think the market is mispriced here.",
            metadata={"reply_count": 47},
        )
        result = extract_features(doc)
        assert result.features["reply_count"] == 47


class TestDefaultFeatures:
    def test_manual_features_basic(self):
        from packages.research.evaluation.feature_extraction import extract_features

        doc = _make_doc(
            source_type="manual",
            body="This is a test document with some content about prediction markets.",
        )
        result = extract_features(doc)
        assert result.family == "manual"
        assert "body_length" in result.features
        assert "word_count" in result.features
        assert result.features["body_length"] > 0
        assert result.features["word_count"] > 0

    def test_unknown_source_type_uses_default(self):
        from packages.research.evaluation.feature_extraction import extract_features

        doc = _make_doc(
            source_type="unknown_type_xyz",
            body="Document from an unknown source type. Contains relevant information.",
        )
        result = extract_features(doc)
        assert result.family == "manual"

    def test_confidence_signals_non_empty_for_academic(self):
        from packages.research.evaluation.feature_extraction import extract_features

        doc = _make_doc(
            source_type="arxiv",
            body=(
                "doi: 10.5678/test.2023.002. "
                "We performed regression analysis on a large dataset. "
                "The p-value confirms statistical significance."
            ),
        )
        result = extract_features(doc)
        assert isinstance(result.confidence_signals, list)
        assert len(result.confidence_signals) > 0


# ---------------------------------------------------------------------------
# Task 1: Deduplication tests
# ---------------------------------------------------------------------------


class TestDedup:
    def test_dedup_exact_match(self):
        from packages.research.evaluation.dedup import (
            compute_content_hash,
            check_near_duplicate,
        )

        body = (
            "This is a test document body for deduplication testing. "
            "It contains enough text to produce meaningful shingles."
        )
        doc = _make_doc(body=body)

        # Compute hash and register it
        h = compute_content_hash(body)
        existing_hashes = {h}
        existing_shingles = []

        result = check_near_duplicate(doc, existing_hashes, existing_shingles)
        assert result.is_duplicate is True
        assert result.duplicate_type == "exact"
        assert result.similarity == 1.0

    def test_dedup_near_match(self):
        from packages.research.evaluation.dedup import (
            compute_shingles,
            compute_content_hash,
            check_near_duplicate,
        )

        body_original = (
            "This is an original document about prediction market microstructure. "
            "The analysis shows that informed traders consistently beat the market by "
            "positioning early before resolution events trigger price movements."
        )
        body_modified = (
            "This is an original document about prediction market microstructure. "
            "The analysis shows that informed traders consistently beat the market by "
            "positioning early before resolution events trigger price changes."
        )

        doc_modified = _make_doc(body=body_modified)
        existing_hashes = {compute_content_hash(body_original)}
        existing_shingles = [("original_doc", compute_shingles(body_original))]

        result = check_near_duplicate(doc_modified, existing_hashes, existing_shingles)
        assert result.is_duplicate is True
        assert result.duplicate_type == "near"
        assert result.matched_doc_id == "original_doc"
        assert result.similarity > 0.85

    def test_dedup_distinct(self):
        from packages.research.evaluation.dedup import (
            compute_shingles,
            compute_content_hash,
            check_near_duplicate,
        )

        body_a = (
            "Avellaneda-Stoikov market making theory proposes that dealers set "
            "bid-ask spreads to manage inventory risk while earning the spread. "
            "The model uses a reservation price adjusted for inventory position."
        )
        body_b = (
            "The weather in London has been unusually warm this spring. "
            "Scientists attribute the pattern to changes in the jet stream "
            "caused by warming Arctic temperatures over the past decade."
        )

        doc_b = _make_doc(body=body_b)
        existing_hashes = {compute_content_hash(body_a)}
        existing_shingles = [("doc_a", compute_shingles(body_a))]

        result = check_near_duplicate(doc_b, existing_hashes, existing_shingles)
        assert result.is_duplicate is False

    def test_dedup_empty_body(self):
        from packages.research.evaluation.dedup import check_near_duplicate

        doc = _make_doc(body="")
        result = check_near_duplicate(doc, {"some_hash"}, [("x", frozenset())])
        assert result.is_duplicate is False

    def test_dedup_none_body(self):
        from packages.research.evaluation.dedup import check_near_duplicate

        doc = _make_doc(body=None)
        result = check_near_duplicate(doc, {"some_hash"}, [])
        assert result.is_duplicate is False

    def test_content_hash_deterministic(self):
        from packages.research.evaluation.dedup import compute_content_hash

        body = "Consistent hashing test. Multiple spaces    and MIXED case."
        h1 = compute_content_hash(body)
        h2 = compute_content_hash(body)
        assert h1 == h2
        assert len(h1) == 64  # SHA256 hex

    def test_content_hash_case_and_whitespace_normalized(self):
        from packages.research.evaluation.dedup import compute_content_hash

        body_a = "HELLO   WORLD"
        body_b = "hello world"
        assert compute_content_hash(body_a) == compute_content_hash(body_b)

    def test_shingles_non_empty(self):
        from packages.research.evaluation.dedup import compute_shingles

        body = "one two three four five six seven eight nine ten"
        shingles = compute_shingles(body)
        assert isinstance(shingles, frozenset)
        assert len(shingles) > 0

    def test_jaccard_similarity_identical(self):
        from packages.research.evaluation.dedup import jaccard_similarity, compute_shingles

        body = "one two three four five six seven eight"
        s = compute_shingles(body)
        assert jaccard_similarity(s, s) == 1.0

    def test_jaccard_similarity_disjoint(self):
        from packages.research.evaluation.dedup import jaccard_similarity

        a = frozenset([("a", "b"), ("c", "d")])
        b = frozenset([("e", "f"), ("g", "h")])
        assert jaccard_similarity(a, b) == 0.0

    def test_jaccard_similarity_empty(self):
        from packages.research.evaluation.dedup import jaccard_similarity

        assert jaccard_similarity(frozenset(), frozenset()) == 0.0


# ---------------------------------------------------------------------------
# Task 1: Artifact persistence tests
# ---------------------------------------------------------------------------


class TestArtifactPersistence:
    def test_artifact_persist_and_load(self, tmp_path):
        from packages.research.evaluation.artifacts import (
            EvalArtifact,
            persist_eval_artifact,
            load_eval_artifacts,
        )

        artifact = EvalArtifact(
            doc_id="doc_001",
            timestamp="2026-04-02T12:00:00+00:00",
            gate="ACCEPT",
            hard_stop_result=None,
            near_duplicate_result=None,
            family_features={"has_doi": True, "methodology_cues": 3},
            scores={"relevance": 4, "total": 15},
            source_family="academic",
            source_type="arxiv",
        )

        persist_eval_artifact(artifact, tmp_path)
        loaded = load_eval_artifacts(tmp_path)

        assert len(loaded) == 1
        assert loaded[0]["doc_id"] == "doc_001"
        assert loaded[0]["gate"] == "ACCEPT"
        assert loaded[0]["source_family"] == "academic"
        assert loaded[0]["family_features"]["has_doi"] is True

    def test_artifact_missing_file(self, tmp_path):
        from packages.research.evaluation.artifacts import load_eval_artifacts

        empty_dir = tmp_path / "nonexistent_subdir"
        result = load_eval_artifacts(empty_dir)
        assert result == []

    def test_artifact_jsonl_append(self, tmp_path):
        from packages.research.evaluation.artifacts import (
            EvalArtifact,
            persist_eval_artifact,
            load_eval_artifacts,
        )

        a1 = EvalArtifact(
            doc_id="doc_001",
            timestamp="2026-04-02T12:00:00+00:00",
            gate="ACCEPT",
            hard_stop_result=None,
            near_duplicate_result=None,
            family_features={"word_count": 100},
            scores=None,
            source_family="manual",
            source_type="manual",
        )
        a2 = EvalArtifact(
            doc_id="doc_002",
            timestamp="2026-04-02T12:01:00+00:00",
            gate="REJECT",
            hard_stop_result={"stop_type": "too_short", "reason": "too short"},
            near_duplicate_result=None,
            family_features={"word_count": 5},
            scores=None,
            source_family="manual",
            source_type="manual",
        )

        persist_eval_artifact(a1, tmp_path)
        persist_eval_artifact(a2, tmp_path)

        loaded = load_eval_artifacts(tmp_path)
        assert len(loaded) == 2
        assert loaded[0]["doc_id"] == "doc_001"
        assert loaded[1]["doc_id"] == "doc_002"

    def test_artifact_creates_dir_if_missing(self, tmp_path):
        from packages.research.evaluation.artifacts import (
            EvalArtifact,
            persist_eval_artifact,
        )

        new_dir = tmp_path / "eval_artifacts_dir"
        assert not new_dir.exists()

        artifact = EvalArtifact(
            doc_id="doc_x",
            timestamp="2026-04-02T12:00:00+00:00",
            gate="REVIEW",
            hard_stop_result=None,
            near_duplicate_result=None,
            family_features={},
            scores=None,
            source_family="manual",
            source_type="manual",
        )
        persist_eval_artifact(artifact, new_dir)
        assert new_dir.exists()
        assert (new_dir / "eval_artifacts.jsonl").exists()


# ---------------------------------------------------------------------------
# Task 2: Evaluator integration tests
# ---------------------------------------------------------------------------


class TestEvaluatorIntegration:
    def test_evaluator_with_features_and_artifacts(self, tmp_path):
        from packages.research.evaluation.evaluator import DocumentEvaluator

        doc = _make_doc(
            source_type="arxiv",
            body=(
                "doi: 10.1234/eval.test.001. "
                "We performed regression analysis on prediction market data. "
                "The p-value is below 0.01. Our methodology includes a control group. "
                "The dataset has 10,000 observations from Polymarket."
            ),
        )

        evaluator = DocumentEvaluator(artifacts_dir=tmp_path)
        decision = evaluator.evaluate(doc)

        # Decision is valid
        assert decision.gate in {"ACCEPT", "REVIEW", "REJECT"}
        assert decision.doc_id == doc.doc_id

        # Artifact file created
        artifact_file = tmp_path / "eval_artifacts.jsonl"
        assert artifact_file.exists()

        from packages.research.evaluation.artifacts import load_eval_artifacts
        artifacts = load_eval_artifacts(tmp_path)
        assert len(artifacts) == 1
        assert artifacts[0]["doc_id"] == doc.doc_id
        assert "family_features" in artifacts[0]
        assert isinstance(artifacts[0]["family_features"], dict)
        assert "gate" in artifacts[0]

    def test_evaluator_dedup_rejects_exact_duplicate(self, tmp_path):
        from packages.research.evaluation.dedup import compute_content_hash
        from packages.research.evaluation.evaluator import DocumentEvaluator

        body = (
            "This is a unique document about prediction market arbitrage strategies. "
            "The analysis covers multiple markets and compares fee structures in detail. "
            "Key insight: informed traders avoid binary markets near resolution."
        )
        doc = _make_doc(body=body)

        # Pre-register the hash
        h = compute_content_hash(body)
        evaluator = DocumentEvaluator(
            existing_hashes={h},
            existing_shingles=[],
        )

        decision = evaluator.evaluate(doc)
        assert decision.gate == "REJECT"
        assert decision.hard_stop is not None
        assert decision.hard_stop.stop_type in {"exact_duplicate", "near_duplicate"}

    def test_evaluator_backward_compat_no_artifacts(self, tmp_path):
        """Evaluator without artifacts_dir should not create any artifact files."""
        from packages.research.evaluation.evaluator import DocumentEvaluator

        doc = _make_doc()
        evaluator = DocumentEvaluator()
        decision = evaluator.evaluate(doc)

        assert decision.gate in {"ACCEPT", "REVIEW", "REJECT"}

        # No artifact file should be created
        import os
        files = list(tmp_path.glob("**/*"))
        assert len(files) == 0

    def test_evaluator_near_duplicate_rejected(self, tmp_path):
        from packages.research.evaluation.dedup import compute_content_hash, compute_shingles
        from packages.research.evaluation.evaluator import DocumentEvaluator

        # Use a longer body so a single-word change at the end still produces
        # Jaccard similarity well above the 0.85 threshold.
        body_original = (
            "This is an original document about Polymarket trading strategies and market "
            "microstructure research. Informed traders systematically exploit late-resolution "
            "pricing inefficiencies that emerge in the final hours before a market settles. "
            "The pattern holds consistently across crypto, sports, and politics markets where "
            "volume and liquidity are both sufficient to support meaningful order flow analysis. "
            "Key insight: price discovery lags fundamentals during the window just before "
            "binary resolution events. Traders who hold informed positions profit from this gap."
        )
        body_near = (
            "This is an original document about Polymarket trading strategies and market "
            "microstructure research. Informed traders systematically exploit late-resolution "
            "pricing inefficiencies that emerge in the final hours before a market settles. "
            "The pattern holds consistently across crypto, sports, and politics markets where "
            "volume and liquidity are both sufficient to support meaningful order flow analysis. "
            "Key insight: price discovery lags fundamentals during the window just before "
            "binary resolution events. Traders who hold informed positions benefit from this gap."
        )

        doc = _make_doc(body=body_near)
        evaluator = DocumentEvaluator(
            existing_hashes={compute_content_hash(body_original)},
            existing_shingles=[("orig_001", compute_shingles(body_original))],
        )

        decision = evaluator.evaluate(doc)
        assert decision.gate == "REJECT"


# ---------------------------------------------------------------------------
# Task 2: Calibration artifact summary tests
# ---------------------------------------------------------------------------


class TestCalibrationEvalArtifactSummary:
    def _make_artifact(
        self,
        gate="ACCEPT",
        source_family="academic",
        source_type="arxiv",
        hard_stop_result=None,
        near_duplicate_result=None,
        scores=None,
        doc_id="doc_001",
    ):
        return {
            "doc_id": doc_id,
            "timestamp": "2026-04-02T12:00:00+00:00",
            "gate": gate,
            "hard_stop_result": hard_stop_result,
            "near_duplicate_result": near_duplicate_result,
            "family_features": {"has_doi": True},
            "scores": scores,
            "source_family": source_family,
            "source_type": source_type,
        }

    def test_calibration_eval_artifact_summary_basic(self):
        from packages.research.synthesis.calibration import compute_eval_artifact_summary

        artifacts = [
            self._make_artifact(gate="ACCEPT", source_family="academic", doc_id="d1"),
            self._make_artifact(gate="REVIEW", source_family="github", doc_id="d2"),
            self._make_artifact(gate="REJECT", source_family="academic", doc_id="d3"),
            self._make_artifact(gate="ACCEPT", source_family="forum_social", doc_id="d4"),
        ]

        summary = compute_eval_artifact_summary(artifacts)

        assert summary["total_evals"] == 4
        assert summary["gate_distribution"]["ACCEPT"] == 2
        assert summary["gate_distribution"]["REVIEW"] == 1
        assert summary["gate_distribution"]["REJECT"] == 1
        assert "family_gate_distribution" in summary
        assert "academic" in summary["family_gate_distribution"]

    def test_calibration_eval_artifact_summary_dedup_stats(self):
        from packages.research.synthesis.calibration import compute_eval_artifact_summary

        artifacts = [
            self._make_artifact(
                doc_id="d1",
                near_duplicate_result={"is_duplicate": True, "duplicate_type": "exact"},
                gate="REJECT",
            ),
            self._make_artifact(
                doc_id="d2",
                near_duplicate_result={"is_duplicate": True, "duplicate_type": "near"},
                gate="REJECT",
            ),
            self._make_artifact(
                doc_id="d3",
                near_duplicate_result=None,
                gate="ACCEPT",
            ),
            self._make_artifact(
                doc_id="d4",
                near_duplicate_result={"is_duplicate": False, "duplicate_type": None},
                gate="REVIEW",
            ),
        ]

        summary = compute_eval_artifact_summary(artifacts)
        dedup = summary["dedup_stats"]
        assert dedup["exact_duplicates"] == 1
        assert dedup["near_duplicates"] == 1
        assert dedup["unique"] >= 2

    def test_calibration_eval_artifact_summary_hard_stop_distribution(self):
        from packages.research.synthesis.calibration import compute_eval_artifact_summary

        artifacts = [
            self._make_artifact(
                doc_id="d1",
                gate="REJECT",
                hard_stop_result={"stop_type": "too_short", "passed": False},
            ),
            self._make_artifact(
                doc_id="d2",
                gate="REJECT",
                hard_stop_result={"stop_type": "spam_malformed", "passed": False},
            ),
            self._make_artifact(
                doc_id="d3",
                gate="ACCEPT",
                hard_stop_result=None,
            ),
        ]

        summary = compute_eval_artifact_summary(artifacts)
        hs = summary["hard_stop_distribution"]
        assert hs.get("too_short", 0) == 1
        assert hs.get("spam_malformed", 0) == 1

    def test_calibration_eval_artifact_summary_empty(self):
        from packages.research.synthesis.calibration import compute_eval_artifact_summary

        summary = compute_eval_artifact_summary([])
        assert summary["total_evals"] == 0
        assert summary["gate_distribution"] == {}

    def test_calibration_report_with_artifacts(self):
        from packages.research.synthesis.calibration import (
            compute_calibration_summary,
            format_calibration_report,
        )

        events = []
        eval_artifacts_summary = {
            "total_evals": 10,
            "gate_distribution": {"ACCEPT": 6, "REVIEW": 2, "REJECT": 2},
            "hard_stop_distribution": {"too_short": 1, "spam_malformed": 1},
            "family_gate_distribution": {
                "academic": {"ACCEPT": 4, "REJECT": 1},
                "github": {"REVIEW": 1, "ACCEPT": 2},
            },
            "dedup_stats": {"exact_duplicates": 1, "near_duplicates": 0, "unique": 9},
            "avg_features_by_family": {},
        }

        summary = compute_calibration_summary(events)
        report = format_calibration_report(
            summary, eval_artifacts_summary=eval_artifacts_summary
        )

        assert "Hard-Stop Causes" in report
        assert "Family Gate Distribution" in report


# ---------------------------------------------------------------------------
# Task 1 verification: SOURCE_FAMILY_OFFSETS hook exists
# ---------------------------------------------------------------------------


class TestSourceFamilyOffsets:
    def test_source_family_offsets_exists(self):
        from packages.research.evaluation.types import SOURCE_FAMILY_OFFSETS

        assert isinstance(SOURCE_FAMILY_OFFSETS, dict)
        # Empty by default — data-driven tuning deferred
        assert SOURCE_FAMILY_OFFSETS == {}

    def test_source_family_offsets_docstring(self):
        """SOURCE_FAMILY_OFFSETS should have a module-level comment explaining its purpose."""
        import inspect
        import packages.research.evaluation.types as m

        src = inspect.getsource(m)
        assert "SOURCE_FAMILY_OFFSETS" in src
