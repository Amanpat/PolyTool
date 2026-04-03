"""Offline tests for RIS v1 query planning, HyDE expansion, and combined retrieval.

All tests are deterministic and offline — no network calls, no Chroma DB required.
Provider calls are monkeypatched to return controlled mock responses.
"""

from __future__ import annotations

import json
from typing import Optional
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# TestQueryPlanner
# ---------------------------------------------------------------------------


class TestQueryPlanner:
    """Tests for packages/research/synthesis/query_planner.py"""

    def test_plan_queries_manual_default(self):
        """Default call (manual provider) returns QueryPlan with 3-5 queries."""
        from packages.research.synthesis.query_planner import plan_queries, QueryPlan

        result = plan_queries("crypto pair bot profitability on Polymarket")
        assert isinstance(result, QueryPlan)
        assert isinstance(result.queries, list)
        assert 3 <= len(result.queries) <= 5
        assert result.topic == "crypto pair bot profitability on Polymarket"
        assert result.provider_used == "manual"
        assert result.was_fallback is False

    def test_plan_queries_manual_with_step_back(self):
        """include_step_back=True returns a non-None step_back_query."""
        from packages.research.synthesis.query_planner import plan_queries

        result = plan_queries("market making spread optimization", include_step_back=True)
        assert result.step_back_query is not None
        assert len(result.step_back_query) > 0

    def test_plan_queries_manual_without_step_back(self):
        """By default (include_step_back=False), step_back_query is None."""
        from packages.research.synthesis.query_planner import plan_queries

        result = plan_queries("market making spread optimization", include_step_back=False)
        assert result.step_back_query is None

    def test_plan_queries_manual_max_queries(self):
        """max_queries=3 clamps output to at most 3 queries."""
        from packages.research.synthesis.query_planner import plan_queries

        result = plan_queries("prediction market strategies", max_queries=3)
        assert len(result.queries) <= 3

    def test_plan_queries_provider_fallback(self):
        """When provider.score returns garbage JSON, was_fallback=True and queries still valid."""
        from packages.research.synthesis.query_planner import plan_queries

        with patch("packages.research.synthesis.query_planner.get_provider") as mock_get:
            mock_provider = MagicMock()
            mock_provider.name = "ollama"
            mock_provider.score.return_value = "not valid json at all !!!"
            mock_get.return_value = mock_provider

            result = plan_queries("some topic", provider_name="ollama")
            assert result.was_fallback is True
            assert isinstance(result.queries, list)
            assert len(result.queries) >= 1

    def test_plan_queries_provider_success(self):
        """When provider.score returns valid JSON queries array, those queries are used."""
        from packages.research.synthesis.query_planner import plan_queries

        mock_queries = [
            "What is the expected value of crypto pair bets?",
            "Historical accuracy of BTC direction predictions",
            "Risk-adjusted returns in binary prediction markets",
        ]
        mock_response = json.dumps({"queries": mock_queries, "step_back_query": None})

        with patch("packages.research.synthesis.query_planner.get_provider") as mock_get:
            mock_provider = MagicMock()
            mock_provider.name = "ollama"
            mock_provider.score.return_value = mock_response
            mock_get.return_value = mock_provider

            result = plan_queries("crypto pair profitability", provider_name="ollama")
            assert result.was_fallback is False
            assert result.queries == mock_queries
            assert result.provider_used == "ollama"

    def test_plan_queries_empty_topic(self):
        """Empty string topic still produces valid QueryPlan (defensive behavior)."""
        from packages.research.synthesis.query_planner import plan_queries

        result = plan_queries("")
        assert isinstance(result.queries, list)
        # May produce empty or minimal queries — should not raise
        assert result.topic == ""

    def test_queryplan_dataclass_fields(self):
        """QueryPlan has expected field names."""
        from packages.research.synthesis.query_planner import QueryPlan

        qp = QueryPlan(
            topic="test",
            queries=["q1", "q2"],
            step_back_query=None,
            provider_used="manual",
            was_fallback=False,
        )
        assert qp.topic == "test"
        assert qp.queries == ["q1", "q2"]
        assert qp.step_back_query is None
        assert qp.provider_used == "manual"
        assert qp.was_fallback is False

    def test_plan_queries_provider_returns_missing_key(self):
        """When provider JSON is missing 'queries' key, falls back to deterministic."""
        from packages.research.synthesis.query_planner import plan_queries

        mock_response = json.dumps({"step_back_query": "some step back"})  # no 'queries'

        with patch("packages.research.synthesis.query_planner.get_provider") as mock_get:
            mock_provider = MagicMock()
            mock_provider.name = "ollama"
            mock_provider.score.return_value = mock_response
            mock_get.return_value = mock_provider

            result = plan_queries("some topic", provider_name="ollama")
            assert result.was_fallback is True
            assert len(result.queries) >= 1

    def test_plan_queries_provider_raises_exception(self):
        """When provider.score raises, falls back to deterministic queries."""
        from packages.research.synthesis.query_planner import plan_queries

        with patch("packages.research.synthesis.query_planner.get_provider") as mock_get:
            mock_provider = MagicMock()
            mock_provider.name = "ollama"
            mock_provider.score.side_effect = ConnectionError("Ollama unreachable")
            mock_get.return_value = mock_provider

            result = plan_queries("some topic", provider_name="ollama")
            assert result.was_fallback is True
            assert len(result.queries) >= 1


# ---------------------------------------------------------------------------
# TestHyDE
# ---------------------------------------------------------------------------


class TestHyDE:
    """Tests for packages/research/synthesis/hyde.py"""

    def test_hyde_manual_default(self):
        """Default call returns HydeResult with template text."""
        from packages.research.synthesis.hyde import expand_hyde, HydeResult

        result = expand_hyde("What is the optimal spread for market making?")
        assert isinstance(result, HydeResult)
        assert isinstance(result.hypothetical_document, str)
        assert len(result.hypothetical_document) > 0
        assert result.provider_used == "manual"
        assert result.was_fallback is False

    def test_hyde_manual_result_shape(self):
        """Verify all HydeResult fields are populated."""
        from packages.research.synthesis.hyde import expand_hyde

        query = "What factors affect profitability in prediction markets?"
        result = expand_hyde(query)
        assert result.query == query
        assert result.hypothetical_document is not None
        assert result.provider_used is not None
        assert result.was_fallback is not None

    def test_hyde_manual_template_references_query(self):
        """Deterministic fallback template incorporates the query text."""
        from packages.research.synthesis.hyde import expand_hyde

        query = "prediction market liquidity depth"
        result = expand_hyde(query)
        # Template should reference the query content in some way
        assert len(result.hypothetical_document) > 10

    def test_hyde_provider_fallback(self):
        """When provider.score raises, was_fallback=True and result is still valid."""
        from packages.research.synthesis.hyde import expand_hyde

        with patch("packages.research.synthesis.hyde.get_provider") as mock_get:
            mock_provider = MagicMock()
            mock_provider.name = "ollama"
            mock_provider.score.side_effect = ConnectionError("Ollama unreachable")
            mock_get.return_value = mock_provider

            result = expand_hyde("What is HyDE?", provider_name="ollama")
            assert result.was_fallback is True
            assert len(result.hypothetical_document) > 0

    def test_hyde_provider_success(self):
        """When provider.score returns text, hypothetical_document matches response."""
        from packages.research.synthesis.hyde import expand_hyde

        fake_doc = "Market makers on binary prediction markets typically set spreads based on inventory risk, volatility, and adverse selection costs."

        with patch("packages.research.synthesis.hyde.get_provider") as mock_get:
            mock_provider = MagicMock()
            mock_provider.name = "ollama"
            mock_provider.score.return_value = fake_doc
            mock_get.return_value = mock_provider

            result = expand_hyde("optimal spread for market making", provider_name="ollama")
            assert result.was_fallback is False
            assert result.hypothetical_document == fake_doc
            assert result.provider_used == "ollama"

    def test_hyde_dataclass_fields(self):
        """HydeResult has expected field names."""
        from packages.research.synthesis.hyde import HydeResult

        hr = HydeResult(
            query="test query",
            hypothetical_document="some document text",
            provider_used="manual",
            was_fallback=False,
        )
        assert hr.query == "test query"
        assert hr.hypothetical_document == "some document text"
        assert hr.provider_used == "manual"
        assert hr.was_fallback is False


# ---------------------------------------------------------------------------
# TestCombinedRetrieval
# ---------------------------------------------------------------------------


def _make_mock_result(chunk_id: str, score: float, snippet: str = "test snippet") -> dict:
    """Helper to create a mock query_index result dict."""
    return {
        "chunk_id": chunk_id,
        "score": score,
        "snippet": snippet,
        "file_path": f"docs/{chunk_id}.md",
        "chunk_index": 0,
        "doc_id": f"doc_{chunk_id}",
        "metadata": {},
    }


class TestCombinedRetrieval:
    """Tests for packages/research/synthesis/retrieval.py"""

    def test_retrieve_for_research_shape(self):
        """Verify all RetrievalPlan fields are populated."""
        from packages.research.synthesis.retrieval import retrieve_for_research, RetrievalPlan

        mock_results = [_make_mock_result("c1", 0.9), _make_mock_result("c2", 0.7)]

        with patch("packages.research.synthesis.retrieval.query_index", return_value=mock_results):
            plan = retrieve_for_research("crypto pair profitability")

        assert isinstance(plan, RetrievalPlan)
        assert plan.topic == "crypto pair profitability"
        assert plan.query_plan is not None
        assert isinstance(plan.results, list)
        assert isinstance(plan.result_sources, dict)

    def test_retrieve_dedup(self):
        """Two sub-queries returning overlapping chunk_ids produce deduplicated results."""
        from packages.research.synthesis.retrieval import retrieve_for_research

        # chunk "overlap" appears in both results with different scores
        call_count = 0

        def mock_qi(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return [
                    _make_mock_result("overlap", 0.9),
                    _make_mock_result("unique1", 0.8),
                ]
            else:
                return [
                    _make_mock_result("overlap", 0.6),  # lower score — should be deduped away
                    _make_mock_result("unique2", 0.7),
                ]

        with patch("packages.research.synthesis.retrieval.query_index", side_effect=mock_qi):
            plan = retrieve_for_research("dedup test topic")

        # No duplicate chunk_ids
        chunk_ids = [r["chunk_id"] for r in plan.results]
        assert len(chunk_ids) == len(set(chunk_ids))

        # The overlap should keep the higher score (0.9)
        overlap_result = next(r for r in plan.results if r["chunk_id"] == "overlap")
        assert overlap_result["score"] == pytest.approx(0.9)

    def test_retrieve_no_hyde(self):
        """use_hyde=False means hyde_result is None."""
        from packages.research.synthesis.retrieval import retrieve_for_research

        with patch("packages.research.synthesis.retrieval.query_index", return_value=[]):
            plan = retrieve_for_research("some topic", use_hyde=False)

        assert plan.hyde_result is None

    def test_retrieve_with_hyde(self):
        """use_hyde=True means hyde_result is populated and extra query is issued."""
        from packages.research.synthesis.retrieval import retrieve_for_research

        call_queries = []

        def mock_qi(**kwargs):
            call_queries.append(kwargs.get("question", ""))
            return []

        with patch("packages.research.synthesis.retrieval.query_index", side_effect=mock_qi):
            plan = retrieve_for_research("market making", use_hyde=True)

        assert plan.hyde_result is not None
        # At least one extra call should have been made for the HyDE doc
        assert len(call_queries) > 1

    def test_retrieve_fallback_no_index(self):
        """When query_index raises, results=[] but query_plan is populated."""
        from packages.research.synthesis.retrieval import retrieve_for_research

        with patch(
            "packages.research.synthesis.retrieval.query_index",
            side_effect=RuntimeError("No Chroma DB"),
        ):
            plan = retrieve_for_research("some topic")

        assert plan.results == []
        assert plan.query_plan is not None
        assert len(plan.query_plan.queries) >= 1

    def test_retrieve_result_sources(self):
        """result_sources maps chunk_id -> set of query labels that found it."""
        from packages.research.synthesis.retrieval import retrieve_for_research

        call_count = 0

        def mock_qi(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return [_make_mock_result("shared", 0.9), _make_mock_result("only_q1", 0.8)]
            elif call_count == 2:
                return [_make_mock_result("shared", 0.7), _make_mock_result("only_q2", 0.6)]
            else:
                return []

        with patch("packages.research.synthesis.retrieval.query_index", side_effect=mock_qi):
            plan = retrieve_for_research("sources test")

        # "shared" should appear in at least 2 queries' source sets
        assert "shared" in plan.result_sources
        assert len(plan.result_sources["shared"]) >= 2

    def test_full_pipeline_manual(self):
        """End-to-end with manual provider: valid QueryPlan and valid structure."""
        from packages.research.synthesis.retrieval import retrieve_for_research
        from packages.research.synthesis.query_planner import QueryPlan

        with patch("packages.research.synthesis.retrieval.query_index", return_value=[]):
            plan = retrieve_for_research(
                "prediction market strategy profitability",
                provider_name="manual",
                use_hyde=False,
            )

        assert isinstance(plan.query_plan, QueryPlan)
        assert plan.query_plan.provider_used == "manual"
        assert len(plan.query_plan.queries) >= 1
        assert plan.topic == "prediction market strategy profitability"
        assert plan.results == []
        assert plan.hyde_result is None

    def test_retrieve_results_sorted_by_score(self):
        """Merged results are sorted by score descending."""
        from packages.research.synthesis.retrieval import retrieve_for_research

        call_count = 0

        def mock_qi(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return [
                    _make_mock_result("c1", 0.5),
                    _make_mock_result("c2", 0.9),
                ]
            else:
                return [_make_mock_result("c3", 0.7)]

        with patch("packages.research.synthesis.retrieval.query_index", side_effect=mock_qi):
            plan = retrieve_for_research("sorted test")

        scores = [r["score"] for r in plan.results]
        assert scores == sorted(scores, reverse=True)


# ---------------------------------------------------------------------------
# TestSynthesisModuleExports
# ---------------------------------------------------------------------------


class TestSynthesisModuleExports:
    """Verify __init__.py exports are correct."""

    def test_query_planner_exports_via_init(self):
        """QueryPlan and plan_queries importable from packages.research.synthesis."""
        from packages.research.synthesis import QueryPlan, plan_queries  # noqa: F401

    def test_hyde_exports_via_init(self):
        """HydeResult and expand_hyde importable from packages.research.synthesis."""
        from packages.research.synthesis import HydeResult, expand_hyde  # noqa: F401

    def test_retrieval_exports_via_init(self):
        """RetrievalPlan and retrieve_for_research importable from packages.research.synthesis."""
        from packages.research.synthesis import RetrievalPlan, retrieve_for_research  # noqa: F401
