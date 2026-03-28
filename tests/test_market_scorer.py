"""Offline unit tests for the seven-factor Market Selection Engine."""

from __future__ import annotations

import math
import pytest
from datetime import datetime, timezone, timedelta

from packages.polymarket.market_selection.config import (
    CATEGORY_EDGE,
    CATEGORY_EDGE_DEFAULT,
    FACTOR_WEIGHTS,
    NEGRISK_PENALTY,
    LONGSHOT_BONUS_MAX,
    LONGSHOT_THRESHOLD,
    TIME_SCORE_CENTER_DAYS,
    MAX_SPREAD_REFERENCE,
    MIN_VOLUME_24H,
    MIN_SPREAD,
)
from packages.polymarket.market_selection.filters import passes_gates
from packages.polymarket.market_selection.scorer import MarketScorer, SevenFactorScore


REF_NOW = datetime(2026, 3, 28, 12, 0, 0, tzinfo=timezone.utc)


def _market(**kwargs):
    base = {
        "slug": "test-market",
        "best_bid": 0.45,
        "best_ask": 0.55,
        "volume_24h": 10_000.0,
        "category": "Sports",
        "end_date_iso": (REF_NOW + timedelta(days=14)).isoformat(),
        "accepting_orders": True,
        "enable_order_book": True,
        "neg_risk": False,
    }
    base.update(kwargs)
    return base


# ---------------------------------------------------------------------------
# Test 1: Category edge lookup
# ---------------------------------------------------------------------------

def test_category_edge_lookup():
    assert CATEGORY_EDGE["Crypto"] == 0.70
    unknown = CATEGORY_EDGE.get("NonExistentCategory", CATEGORY_EDGE_DEFAULT)
    assert unknown == CATEGORY_EDGE_DEFAULT


# ---------------------------------------------------------------------------
# Test 2: Spread normalization
# ---------------------------------------------------------------------------

def test_spread_normalization():
    scorer = MarketScorer(now=REF_NOW)
    # Wider spread (0.06) should score higher than narrow spread (0.02)
    wide = scorer._score_single(_market(best_bid=0.47, best_ask=0.53))   # spread=0.06
    narrow = scorer._score_single(_market(best_bid=0.49, best_ask=0.51)) # spread=0.02
    assert wide.spread_score > narrow.spread_score

    # Spread at or beyond MAX_SPREAD_REFERENCE should clip to 1.0
    at_max = scorer._score_single(_market(best_bid=0.45, best_ask=0.55))  # spread=0.10
    assert at_max.spread_score == 1.0

    beyond_max = scorer._score_single(_market(best_bid=0.40, best_ask=0.60))  # spread=0.20
    assert beyond_max.spread_score == 1.0


# ---------------------------------------------------------------------------
# Test 3: Volume log scaling
# ---------------------------------------------------------------------------

def test_volume_log_scaling():
    scorer = MarketScorer(now=REF_NOW)
    high_vol = scorer._score_single(_market(volume_24h=50_000.0))
    low_vol = scorer._score_single(_market(volume_24h=500.0))
    assert high_vol.volume_score > low_vol.volume_score

    # Volume below MIN_VOLUME_24H should gate out
    below_min = scorer._score_single(_market(volume_24h=float(MIN_VOLUME_24H) - 1.0))
    assert below_min.gate_passed is False
    assert "volume_below_min" in below_min.gate_reason


# ---------------------------------------------------------------------------
# Test 4: Competition inverse
# ---------------------------------------------------------------------------

def test_competition_inverse():
    scorer = MarketScorer(now=REF_NOW)

    # No orderbook bids at all
    no_bids = scorer._score_single(_market())
    # With many large bids (competition should be lower = more crowded)
    many_bids = scorer._score_single(_market(bids=[
        {"price": 0.45, "size": 100},
        {"price": 0.44, "size": 100},
        {"price": 0.43, "size": 100},
        {"price": 0.42, "size": 100},
        {"price": 0.41, "size": 100},
        {"price": 0.40, "size": 100},
        {"price": 0.39, "size": 100},
        {"price": 0.38, "size": 100},
        {"price": 0.37, "size": 100},
    ]))
    # More large bids means lower competition_score (more competition)
    assert many_bids.competition_score < no_bids.competition_score


# ---------------------------------------------------------------------------
# Test 5: Time Gaussian
# ---------------------------------------------------------------------------

def test_time_gaussian():
    scorer = MarketScorer(now=REF_NOW)
    center = scorer._score_single(_market(
        end_date_iso=(REF_NOW + timedelta(days=14)).isoformat()
    ))
    near = scorer._score_single(_market(
        end_date_iso=(REF_NOW + timedelta(days=1)).isoformat()
    ))
    far = scorer._score_single(_market(
        end_date_iso=(REF_NOW + timedelta(days=90)).isoformat()
    ))
    # Centered at 14 days should score highest
    assert center.time_score > near.time_score
    assert center.time_score > far.time_score


# ---------------------------------------------------------------------------
# Test 6: Longshot bonus
# ---------------------------------------------------------------------------

def test_longshot_bonus():
    scorer = MarketScorer(now=REF_NOW)

    # mid_price = 0.10 -> bonus = LONGSHOT_BONUS_MAX * (1 - 0.10/LONGSHOT_THRESHOLD)
    longshot = scorer._score_single(_market(best_bid=0.08, best_ask=0.12))
    mid = 0.10
    expected_bonus = LONGSHOT_BONUS_MAX * (1 - mid / LONGSHOT_THRESHOLD)
    assert abs(longshot.longshot_bonus - expected_bonus) < 1e-9

    # mid_price = 0.50 -> bonus = 0
    no_bonus = scorer._score_single(_market(best_bid=0.48, best_ask=0.52))
    assert no_bonus.longshot_bonus == 0.0


# ---------------------------------------------------------------------------
# Test 7: passes_gates rejects low volume
# ---------------------------------------------------------------------------

def test_passes_gates_reject_volume():
    result, reason = passes_gates(
        volume_24h=100.0,
        spread=0.02,
        days_to_resolution=10.0,
        accepting_orders=True,
        enable_order_book=True,
    )
    assert result is False
    assert "volume_below_min" in reason


# ---------------------------------------------------------------------------
# Test 8: passes_gates rejects low spread
# ---------------------------------------------------------------------------

def test_passes_gates_reject_spread():
    result, reason = passes_gates(
        volume_24h=10_000.0,
        spread=0.001,
        days_to_resolution=10.0,
        accepting_orders=True,
        enable_order_book=True,
    )
    assert result is False
    assert "spread_below_min" in reason


# ---------------------------------------------------------------------------
# Test 9: passes_gates passes valid inputs
# ---------------------------------------------------------------------------

def test_passes_gates_pass():
    result, reason = passes_gates(
        volume_24h=10_000.0,
        spread=0.02,
        days_to_resolution=10.0,
        accepting_orders=True,
        enable_order_book=True,
    )
    assert result is True
    assert reason == ""


# ---------------------------------------------------------------------------
# Test 10: NegRisk penalty
# ---------------------------------------------------------------------------

def test_negrisk_penalty():
    scorer = MarketScorer(now=REF_NOW)
    normal = scorer._score_single(_market(neg_risk=False))
    neg_risk = scorer._score_single(_market(neg_risk=True))
    # NegRisk composite should be approximately normal * NEGRISK_PENALTY
    assert abs(neg_risk.composite - normal.composite * NEGRISK_PENALTY) < 1e-6


# ---------------------------------------------------------------------------
# Test 11: Composite ordering
# ---------------------------------------------------------------------------

def test_composite_ordering():
    scorer = MarketScorer(now=REF_NOW)

    high_signal = _market(
        slug="high-signal",
        best_bid=0.20,   # wider spread (longshot)
        best_ask=0.30,
        volume_24h=80_000.0,
        category="Crypto",
        end_date_iso=(REF_NOW + timedelta(days=14)).isoformat(),
    )
    low_signal = _market(
        slug="low-signal",
        best_bid=0.495,   # very narrow spread
        best_ask=0.505,
        volume_24h=600.0,
        category="Sports",
        end_date_iso=(REF_NOW + timedelta(days=90)).isoformat(),
    )

    results = scorer.score_universe([high_signal, low_signal], include_failing=True)
    slugs = [r.market_slug for r in results]
    high_idx = slugs.index("high-signal")
    low_idx = slugs.index("low-signal")
    assert high_idx < low_idx, "High-signal market should rank before low-signal market"
