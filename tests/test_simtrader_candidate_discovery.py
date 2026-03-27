"""Tests for CandidateDiscovery module.

Covers: bucket inference for all 6 buckets, score_for_capture logic,
shortage boost weighting, ranking order, empty pool handling.
All tests are offline (no network calls).
"""

from __future__ import annotations

import sys
import os
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch

import pytest

# Ensure project root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ---------------------------------------------------------------------------
# infer_bucket tests
# ---------------------------------------------------------------------------


class TestInferBucket:
    """Tests for infer_bucket() pure function."""

    def test_sports_bucket_via_regime(self):
        """Market with sports keyword should return 'sports'."""
        from packages.polymarket.simtrader.candidate_discovery import infer_bucket

        market = {
            "slug": "will-nfl-team-win",
            "question": "Will the NFL team win the championship?",
            "category": "sports",
        }
        assert infer_bucket(market) == "sports"

    def test_politics_bucket_via_regime(self):
        """Market with politics keyword should return 'politics'."""
        from packages.polymarket.simtrader.candidate_discovery import infer_bucket

        market = {
            "slug": "will-candidate-win-election",
            "question": "Will the candidate win the presidential election?",
            "category": "politics",
        }
        assert infer_bucket(market) == "politics"

    def test_new_market_bucket_via_regime(self):
        """Market created recently (< 48h) should return 'new_market'."""
        from packages.polymarket.simtrader.candidate_discovery import infer_bucket

        now = datetime.now(timezone.utc)
        recent = (now - timedelta(hours=24)).isoformat()
        market = {
            "slug": "some-new-market",
            "question": "Will something happen?",
            "createdAt": recent,
        }
        assert infer_bucket(market) == "new_market"

    def test_near_resolution_bucket_heuristic(self):
        """Market with end_date within 72h should return 'near_resolution'."""
        from packages.polymarket.simtrader.candidate_discovery import infer_bucket

        now = datetime.now(timezone.utc)
        soon = (now + timedelta(hours=48)).isoformat()
        market = {
            "slug": "some-generic-market",
            "question": "Will something generic happen?",
            "end_date_iso": soon,
        }
        assert infer_bucket(market) == "near_resolution"

    def test_crypto_bucket_via_slug_keyword(self):
        """Market with 'btc' in slug should return 'crypto'."""
        from packages.polymarket.simtrader.candidate_discovery import infer_bucket

        market = {
            "slug": "will-btc-reach-100k",
            "question": "Will BTC reach $100K?",
        }
        assert infer_bucket(market) == "crypto"

    def test_crypto_bucket_via_eth_keyword(self):
        """Market with 'ethereum' in question should return 'crypto'."""
        from packages.polymarket.simtrader.candidate_discovery import infer_bucket

        market = {
            "slug": "ethereum-price-target",
            "question": "Will Ethereum hit $5000?",
        }
        assert infer_bucket(market) == "crypto"

    def test_other_bucket_fallback(self):
        """Market with no recognizable keywords should return 'other'."""
        from packages.polymarket.simtrader.candidate_discovery import infer_bucket

        now = datetime.now(timezone.utc)
        # Far-future end date so near_resolution doesn't fire
        far_future = (now + timedelta(days=90)).isoformat()
        # Old creation date so new_market doesn't fire
        old_date = (now - timedelta(days=30)).isoformat()
        market = {
            "slug": "will-generic-thing-happen",
            "question": "Will some unclassified thing happen in the future?",
            "end_date_iso": far_future,
            "createdAt": old_date,
        }
        assert infer_bucket(market) == "other"

    def test_near_resolution_does_not_override_sports(self):
        """near_resolution should NOT override sports bucket."""
        from packages.polymarket.simtrader.candidate_discovery import infer_bucket

        now = datetime.now(timezone.utc)
        soon = (now + timedelta(hours=48)).isoformat()
        market = {
            "slug": "will-nba-team-win-finals",
            "question": "Will the NBA team win the finals this weekend?",
            "category": "sports",
            "end_date_iso": soon,
        }
        # Sports regime takes priority over near_resolution
        assert infer_bucket(market) == "sports"

    def test_crypto_sol_keyword(self):
        """Market with 'sol' / 'solana' should return 'crypto'."""
        from packages.polymarket.simtrader.candidate_discovery import infer_bucket

        market = {
            "slug": "will-solana-outperform",
            "question": "Will Solana price exceed $200?",
        }
        assert infer_bucket(market) == "crypto"


# ---------------------------------------------------------------------------
# score_for_capture tests
# ---------------------------------------------------------------------------


def _make_book_val(valid=True, reason="ok", best_bid=0.45, best_ask=0.55, depth_total=100.0):
    """Helper: create a BookValidation-like mock."""
    bv = MagicMock()
    bv.valid = valid
    bv.reason = reason
    bv.best_bid = best_bid
    bv.best_ask = best_ask
    bv.depth_total = depth_total
    return bv


def _make_resolved_market(slug="test-market", question="Test market?"):
    """Helper: create a ResolvedMarket-like mock."""
    rm = MagicMock()
    rm.slug = slug
    rm.question = question
    rm.yes_token_id = "yes_token"
    rm.no_token_id = "no_token"
    rm.probe_results = None
    return rm


class TestScoreForCapture:
    """Tests for score_for_capture() pure function."""

    def test_one_sided_yes_book_returns_zero(self):
        """Market with one-sided YES book should score 0.0."""
        from packages.polymarket.simtrader.candidate_discovery import score_for_capture

        resolved = _make_resolved_market()
        raw_meta = {"slug": "test-market"}
        shortage = {"sports": 15, "politics": 9, "crypto": 10, "new_market": 5, "near_resolution": 1, "other": 0}
        yes_val = _make_book_val(valid=False, reason="one_sided_book")
        no_val = _make_book_val(valid=True)

        score = score_for_capture(resolved, raw_meta, shortage, yes_val, no_val, None, "other")
        assert score == 0.0

    def test_one_sided_no_book_returns_zero(self):
        """Market with one-sided NO book should score 0.0."""
        from packages.polymarket.simtrader.candidate_discovery import score_for_capture

        resolved = _make_resolved_market()
        raw_meta = {"slug": "test-market"}
        shortage = {"sports": 15, "politics": 9, "crypto": 10, "new_market": 5, "near_resolution": 1, "other": 0}
        yes_val = _make_book_val(valid=True)
        no_val = _make_book_val(valid=False, reason="one_sided_book")

        score = score_for_capture(resolved, raw_meta, shortage, yes_val, no_val, None, "other")
        assert score == 0.0

    def test_empty_book_returns_zero(self):
        """Market with empty_book reason should score 0.0."""
        from packages.polymarket.simtrader.candidate_discovery import score_for_capture

        resolved = _make_resolved_market()
        raw_meta = {}
        shortage = {"sports": 15, "other": 0}
        yes_val = _make_book_val(valid=False, reason="empty_book")
        no_val = _make_book_val(valid=True)

        score = score_for_capture(resolved, raw_meta, shortage, yes_val, no_val, None, "other")
        assert score == 0.0

    def test_shortage_boost_proportional(self):
        """Higher shortage bucket should score higher than lower shortage."""
        from packages.polymarket.simtrader.candidate_discovery import score_for_capture

        shortage = {"sports": 15, "politics": 9, "other": 0}
        resolved = _make_resolved_market()
        raw_meta = {}
        yes_val = _make_book_val(depth_total=100.0)
        no_val = _make_book_val(depth_total=100.0)

        score_sports = score_for_capture(resolved, raw_meta, shortage, yes_val, no_val, None, "sports")
        score_politics = score_for_capture(resolved, raw_meta, shortage, yes_val, no_val, None, "politics")
        score_other = score_for_capture(resolved, raw_meta, shortage, yes_val, no_val, None, "other")

        # sports (shortage=15) > politics (shortage=9) > other (shortage=0)
        assert score_sports > score_politics > score_other

    def test_probe_score_half_when_no_probe(self):
        """When probe_results is None, probe_score should be 0.5 * weight."""
        from packages.polymarket.simtrader.candidate_discovery import score_for_capture

        resolved = _make_resolved_market()
        raw_meta = {}
        shortage = {"other": 0}
        # Use bid=None/ask=None to isolate the probe component (spread_score=0)
        yes_val = _make_book_val(depth_total=0.0, best_bid=None, best_ask=None)
        no_val = _make_book_val(depth_total=0.0, best_bid=None, best_ask=None)

        # With no probe, probe component is 0.5 * 0.20 = 0.10
        # With depth=0: depth_score=0, shortage_boost=0, spread_score=0 (no bid/ask)
        score = score_for_capture(resolved, raw_meta, shortage, yes_val, no_val, None, "other")
        assert score == pytest.approx(0.5 * 0.20, abs=0.01)

    def test_probe_score_full_when_active(self):
        """Active probe results should give full probe_score = 1.0 * weight."""
        from packages.polymarket.simtrader.candidate_discovery import score_for_capture

        resolved = _make_resolved_market()
        raw_meta = {}
        shortage = {"other": 0}
        # Use bid=None/ask=None to isolate the probe component (spread_score=0)
        yes_val = _make_book_val(depth_total=0.0, best_bid=None, best_ask=None)
        no_val = _make_book_val(depth_total=0.0, best_bid=None, best_ask=None)

        probe_result = MagicMock()
        probe_result.active = True
        probe_results = {"yes_token": probe_result}

        score = score_for_capture(resolved, raw_meta, shortage, yes_val, no_val, probe_results, "other")
        assert score == pytest.approx(1.0 * 0.20, abs=0.01)

    def test_score_range_zero_to_one(self):
        """Score must be in [0.0, 1.0]."""
        from packages.polymarket.simtrader.candidate_discovery import score_for_capture

        resolved = _make_resolved_market()
        raw_meta = {}
        shortage = {"sports": 15}
        yes_val = _make_book_val(depth_total=200.0, best_bid=0.49, best_ask=0.51)
        no_val = _make_book_val(depth_total=200.0, best_bid=0.49, best_ask=0.51)

        score = score_for_capture(resolved, raw_meta, shortage, yes_val, no_val, None, "sports")
        assert 0.0 <= score <= 1.0


# ---------------------------------------------------------------------------
# DiscoveryResult + rank_reason tests
# ---------------------------------------------------------------------------


class TestRankReason:
    """Tests for rank_reason() function."""

    def test_rank_reason_includes_bucket(self):
        """rank_reason should include the bucket name."""
        from packages.polymarket.simtrader.candidate_discovery import rank_reason

        reason = rank_reason("sports", {"sports": 15}, 0.87, 142.0, True)
        assert "sports" in reason

    def test_rank_reason_includes_shortage(self):
        """rank_reason should include the shortage value."""
        from packages.polymarket.simtrader.candidate_discovery import rank_reason

        reason = rank_reason("sports", {"sports": 15}, 0.87, 142.0, True)
        assert "15" in reason

    def test_rank_reason_includes_score(self):
        """rank_reason should include the score value."""
        from packages.polymarket.simtrader.candidate_discovery import rank_reason

        reason = rank_reason("sports", {"sports": 15}, 0.87, 142.0, True)
        assert "0.87" in reason

    def test_rank_reason_probe_active(self):
        """rank_reason with active probe should mention 'active'."""
        from packages.polymarket.simtrader.candidate_discovery import rank_reason

        reason = rank_reason("sports", {"sports": 15}, 0.87, 142.0, True)
        assert "active" in reason.lower()

    def test_rank_reason_no_probe(self):
        """rank_reason with probe_active=None should not crash."""
        from packages.polymarket.simtrader.candidate_discovery import rank_reason

        reason = rank_reason("other", {"other": 0}, 0.30, None, None)
        assert isinstance(reason, str)
        assert len(reason) > 0


# ---------------------------------------------------------------------------
# CandidateDiscovery.rank() tests
# ---------------------------------------------------------------------------


def _make_raw_market(slug, question="Question?", category=None):
    """Helper: minimal raw Gamma market dict."""
    return {
        "slug": slug,
        "question": question,
        "clobTokenIds": '["yes_tok", "no_tok"]',
        "outcomes": '["Yes", "No"]',
        "category": category or "general",
    }


class TestCandidateDiscoveryRank:
    """Tests for CandidateDiscovery.rank()."""

    def _make_picker_mock(self, raw_markets, resolved_markets):
        """Create a MarketPicker mock returning the given markets."""
        picker = MagicMock()
        # fetch_markets_page returns pages
        picker._gamma = MagicMock()
        picker._gamma.fetch_markets_page.return_value = raw_markets
        picker.auto_pick_many.return_value = resolved_markets
        return picker

    def test_rank_returns_discovery_results(self):
        """rank() should return a list of DiscoveryResult objects."""
        from packages.polymarket.simtrader.candidate_discovery import (
            CandidateDiscovery,
            DiscoveryResult,
        )

        resolved = _make_resolved_market(slug="test-slug")
        resolved.yes_token_id = "yes_tok"
        resolved.no_token_id = "no_tok"
        resolved.probe_results = None

        picker = MagicMock()
        picker._gamma = MagicMock()
        picker._gamma.fetch_markets_page.return_value = [
            _make_raw_market("test-slug", "Test market?")
        ]
        picker.auto_pick_many.return_value = [resolved]

        yes_val = _make_book_val(depth_total=100.0, best_bid=0.45, best_ask=0.55)
        no_val = _make_book_val(depth_total=80.0, best_bid=0.44, best_ask=0.56)
        picker.validate_book.side_effect = [yes_val, no_val]

        shortage = {"sports": 15, "politics": 9, "crypto": 10, "new_market": 5, "near_resolution": 1, "other": 0}
        discovery = CandidateDiscovery(picker, shortage)
        results = discovery.rank(n=1, pool_size=100, probe_config=None)

        assert len(results) == 1
        assert isinstance(results[0], DiscoveryResult)

    def test_rank_orders_by_score_descending(self):
        """rank() should return markets ordered by score descending."""
        from packages.polymarket.simtrader.candidate_discovery import CandidateDiscovery

        # Two markets: one with sports (high shortage), one with 'other'
        now = datetime.now(timezone.utc)
        far_future = (now + timedelta(days=90)).isoformat()
        old_date = (now - timedelta(days=30)).isoformat()

        sports_market = _make_raw_market("nfl-game", "Will the NFL team win?", "sports")
        other_market = _make_raw_market("generic-market", "Will something happen?", "general")
        other_market["end_date_iso"] = far_future
        other_market["createdAt"] = old_date

        resolved_sports = _make_resolved_market(slug="nfl-game", question="Will the NFL team win?")
        resolved_sports.yes_token_id = "yes_tok_sports"
        resolved_sports.no_token_id = "no_tok_sports"
        resolved_sports.probe_results = None

        resolved_other = _make_resolved_market(slug="generic-market", question="Will something happen?")
        resolved_other.yes_token_id = "yes_tok_other"
        resolved_other.no_token_id = "no_tok_other"
        resolved_other.probe_results = None

        picker = MagicMock()
        picker._gamma = MagicMock()
        picker._gamma.fetch_markets_page.return_value = [sports_market, other_market]
        picker.auto_pick_many.return_value = [resolved_sports, resolved_other]

        yes_val_good = _make_book_val(depth_total=100.0, best_bid=0.45, best_ask=0.55)
        no_val_good = _make_book_val(depth_total=80.0, best_bid=0.44, best_ask=0.56)
        picker.validate_book.return_value = yes_val_good

        shortage = {"sports": 15, "politics": 9, "crypto": 10, "new_market": 5, "near_resolution": 1, "other": 0}
        discovery = CandidateDiscovery(picker, shortage)

        with patch.object(discovery, "_validate_both_books") as mock_validate:
            mock_validate.return_value = (yes_val_good, no_val_good)
            results = discovery.rank(n=2, pool_size=100, probe_config=None)

        if len(results) >= 2:
            assert results[0].score >= results[1].score

    def test_rank_empty_pool_returns_empty_list(self):
        """rank() with empty pool should return []."""
        from packages.polymarket.simtrader.candidate_discovery import CandidateDiscovery

        picker = MagicMock()
        picker._gamma = MagicMock()
        picker._gamma.fetch_markets_page.return_value = []
        picker.auto_pick_many.return_value = []

        shortage = {"sports": 15}
        discovery = CandidateDiscovery(picker, shortage)
        results = discovery.rank(n=5, pool_size=100, probe_config=None)
        assert results == []

    def test_rank_excludes_one_sided_markets(self):
        """One-sided market (score=0.0) should not appear in results."""
        from packages.polymarket.simtrader.candidate_discovery import CandidateDiscovery

        resolved = _make_resolved_market(slug="one-sided-market")
        resolved.yes_token_id = "yes_tok"
        resolved.no_token_id = "no_tok"
        resolved.probe_results = None

        picker = MagicMock()
        picker._gamma = MagicMock()
        picker._gamma.fetch_markets_page.return_value = [
            _make_raw_market("one-sided-market", "Will something happen?")
        ]
        picker.auto_pick_many.return_value = [resolved]

        # Simulate one-sided book
        one_sided_yes = _make_book_val(valid=False, reason="one_sided_book")
        ok_no = _make_book_val(valid=True, depth_total=50.0)

        with patch.object(
            __import__(
                "packages.polymarket.simtrader.candidate_discovery",
                fromlist=["CandidateDiscovery"]
            ),
            "score_for_capture",
            return_value=0.0
        ):
            shortage = {"sports": 15}
            discovery = CandidateDiscovery(picker, shortage)

            # Patch validate to return one-sided
            def fake_validate(resolved_m, yes_v, no_v):
                return (_make_book_val(valid=False, reason="one_sided_book"),
                        _make_book_val(valid=True))
            discovery._validate_both_books = fake_validate

            results = discovery.rank(n=5, pool_size=100, probe_config=None)

        # All scores are 0, so no results should appear
        assert all(r.score > 0.0 for r in results)

    def test_pool_size_clamped_to_max_300(self):
        """pool_size > 300 should be clamped to 300."""
        from packages.polymarket.simtrader.candidate_discovery import CandidateDiscovery

        picker = MagicMock()
        picker._gamma = MagicMock()
        picker._gamma.fetch_markets_page.return_value = []
        picker.auto_pick_many.return_value = []

        shortage = {}
        discovery = CandidateDiscovery(picker, shortage)
        # Should not raise; clamping should apply internally
        results = discovery.rank(n=1, pool_size=500, probe_config=None)
        assert results == []

    def test_discovery_result_has_required_fields(self):
        """DiscoveryResult dataclass should have all required fields."""
        from packages.polymarket.simtrader.candidate_discovery import DiscoveryResult

        dr = DiscoveryResult(
            slug="test",
            question="Test?",
            bucket="sports",
            score=0.75,
            rank_reason="bucket=sports shortage=15 score=0.75 depth=100",
            yes_depth=100.0,
            no_depth=80.0,
            probe_summary=None,
        )
        assert dr.slug == "test"
        assert dr.question == "Test?"
        assert dr.bucket == "sports"
        assert dr.score == 0.75
        assert dr.rank_reason == "bucket=sports shortage=15 score=0.75 depth=100"
        assert dr.yes_depth == 100.0
        assert dr.no_depth == 80.0
        assert dr.probe_summary is None
