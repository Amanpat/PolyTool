"""Tests for Gate 2 candidate ranking: explainable scores, missing-data handling,
new-market logic, and reason-code output.

Tests must pass alongside existing tests/test_market_selection.py without touching
other test files.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from packages.polymarket.market_selection import scorer
from packages.polymarket.market_selection.scorer import (
    GATE2_RANK_WEIGHTS,
    Gate2RankScore,
    score_gate2_candidate,
    rank_gate2_candidates,
)

FIXED_NOW = datetime(2026, 3, 9, 12, 0, 0, tzinfo=timezone.utc)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _candidate_kwargs(**overrides) -> dict:
    """Minimal Gate 2 signal kwargs for a no-signal market."""
    base = dict(
        executable_ticks=0,
        edge_ok_ticks=0,
        depth_ok_ticks=0,
        best_edge_raw=-98.0,   # sentinel: no BBO data
        depth_yes=0.0,
        depth_no=0.0,
        source="live",
    )
    base.update(overrides)
    return base


def _good_market() -> dict:
    return {
        "volume_24h": 30_000.0,
        "created_at": _iso(FIXED_NOW - timedelta(hours=100)),  # mature
    }


def _new_market() -> dict:
    return {
        "volume_24h": 8_000.0,
        "created_at": _iso(FIXED_NOW - timedelta(hours=20)),  # < 48h
    }


def _reward_config() -> dict:
    return {"reward_rate": 0.004110, "min_size_cutoff": 100.0}  # ≈1.5 APR


def _orderbook_low_crowd() -> dict:
    # Only one thin bid → competition_score = 0.5
    return {
        "bids": [{"price": "0.48", "size": "3.0"}],  # 0.48*3=1.44 < 50 → thin
        "asks": [{"price": "0.52", "size": "100.0"}],
    }


# ---------------------------------------------------------------------------
# Test: complete inputs produce expected factor values
# ---------------------------------------------------------------------------

def test_score_gate2_candidate_complete_inputs(monkeypatch):
    monkeypatch.setattr(scorer, "_utcnow", lambda: FIXED_NOW)

    result = score_gate2_candidate(
        "alpha-market",
        **_candidate_kwargs(
            executable_ticks=2,
            edge_ok_ticks=5,
            depth_ok_ticks=3,
            best_edge_raw=0.02,   # real edge: 2% above threshold
            depth_yes=80.0,
            depth_no=65.0,
        ),
        market=_good_market(),
        reward_config=_reward_config(),
        orderbook=_orderbook_low_crowd(),
        max_size=50.0,
        buffer=0.01,
    )

    assert isinstance(result, Gate2RankScore)
    assert result.slug == "alpha-market"
    assert result.executable_ticks == 2
    assert result.gate2_status == "EXECUTABLE"

    # depth factor: min(65, 80) / 50 = 1.3 → capped at 1.0
    # edge factor: (0.02 - (-0.10)) / 0.15 = 0.80
    # reward_apr_est = min(0.004110 * 365, 3.0) = 1.50015; reward_factor = 1.50015 / 3.0
    reward_apr = min(0.004110 * 365.0, 3.0)
    expected_rank = (
        1.0 * GATE2_RANK_WEIGHTS["gate2_depth"]
        + 0.80 * GATE2_RANK_WEIGHTS["gate2_edge"]
        + (reward_apr / 3.0) * GATE2_RANK_WEIGHTS["reward"]
        + min(30_000.0 / 50_000.0, 1.0) * GATE2_RANK_WEIGHTS["volume"]
        + 0.5 * GATE2_RANK_WEIGHTS["competition"]  # 1/(1+1) = 0.5
        + 0.0 * GATE2_RANK_WEIGHTS["age"]           # mature market
    )
    assert result.rank_score == pytest.approx(expected_rank, abs=0.01)

    # Factor fields
    assert result.reward_apr_est == pytest.approx(0.004110 * 365.0, abs=0.01)
    assert result.volume_24h == pytest.approx(30_000.0)
    assert result.competition_score == pytest.approx(0.5)
    assert result.age_hours == pytest.approx(100.0, abs=0.1)
    assert result.is_new_market is False
    assert result.best_edge == pytest.approx(0.02)

    # Explanation must contain all factor headings
    all_text = "\n".join(result.explanation)
    assert "GATE2: EXECUTABLE" in all_text
    assert "depth:" in all_text
    assert "edge:" in all_text
    assert "reward:" in all_text
    assert "volume_24h:" in all_text
    assert "competition:" in all_text
    assert "age:" in all_text
    assert "regime: UNKNOWN" in all_text

    # No UNKNOWN for factors that have data
    assert "reward: UNKNOWN" not in all_text
    assert "volume_24h: UNKNOWN" not in all_text
    assert "competition: UNKNOWN" not in all_text
    assert "age: UNKNOWN" not in all_text


# ---------------------------------------------------------------------------
# Test: missing data → UNKNOWN in explanation, factor contributes 0
# ---------------------------------------------------------------------------

def test_score_gate2_candidate_all_unknown(monkeypatch):
    monkeypatch.setattr(scorer, "_utcnow", lambda: FIXED_NOW)

    result = score_gate2_candidate(
        "bare-market",
        **_candidate_kwargs(
            depth_yes=10.0,
            depth_no=8.0,
            best_edge_raw=-98.5,  # sentinel
        ),
        # no market, no reward_config, no orderbook
    )

    assert result.reward_apr_est is None
    assert result.volume_24h is None
    assert result.competition_score is None
    assert result.age_hours is None
    assert result.is_new_market is None
    assert result.best_edge is None
    assert result.regime is None

    text = "\n".join(result.explanation)
    assert "reward: UNKNOWN" in text
    assert "volume_24h: UNKNOWN" in text
    assert "competition: UNKNOWN" in text
    assert "age: UNKNOWN" in text
    assert "edge: UNKNOWN" in text

    # Rank score = depth component only (other factors 0)
    # depth_min = 8; gate2_depth_factor = 8/50 = 0.16
    expected = 0.16 * GATE2_RANK_WEIGHTS["gate2_depth"]
    assert result.rank_score == pytest.approx(expected, abs=1e-6)


def test_missing_factors_do_not_inflate_rank_score(monkeypatch):
    """Missing data must not score higher than a market with known-low data."""
    monkeypatch.setattr(scorer, "_utcnow", lambda: FIXED_NOW)

    # Market A: all UNKNOWN
    a = score_gate2_candidate(
        "unknown-market",
        **_candidate_kwargs(depth_yes=60.0, depth_no=60.0, best_edge_raw=-0.05),
    )

    # Market B: same Gate 2 signals + known-low quality
    b = score_gate2_candidate(
        "low-quality-market",
        **_candidate_kwargs(depth_yes=60.0, depth_no=60.0, best_edge_raw=-0.05),
        market={"volume_24h": 5_100.0, "created_at": _iso(FIXED_NOW - timedelta(hours=200))},
        reward_config={"reward_rate": 0.0001},
        orderbook={"bids": [{"price": "0.48", "size": "2.0"} for _ in range(20)], "asks": []},
    )

    # Both have same Gate 2 depth/edge. Market B has real (low) reward+volume+competition.
    # Market A (UNKNOWN) must not score higher than market B just because data is missing.
    # (UNKNOWN = 0 for those factors, so B may score similarly or slightly above)
    # The test checks that missing data doesn't inflate: A's market-quality portion is 0,
    # B's market-quality portion is low-but-real.
    assert a.reward_apr_est is None
    assert b.reward_apr_est is not None
    # A should not score strictly MORE than B on the composite
    # (B has real rewards, however small, which A doesn't)
    assert a.rank_score <= b.rank_score + 1e-6


# ---------------------------------------------------------------------------
# Test: new-market age logic
# ---------------------------------------------------------------------------

def test_new_market_flag_set_when_under_48h(monkeypatch):
    monkeypatch.setattr(scorer, "_utcnow", lambda: FIXED_NOW)

    result = score_gate2_candidate(
        "fresh-market",
        **_candidate_kwargs(),
        market={"volume_24h": 10_000.0, "created_at": _iso(FIXED_NOW - timedelta(hours=10))},
    )

    assert result.is_new_market is True
    assert result.age_hours == pytest.approx(10.0, abs=0.1)
    text = "\n".join(result.explanation)
    assert "NEW MARKET" in text
    assert "new_market" in text   # hint to use --regime new_market


def test_mature_market_flag_when_over_48h(monkeypatch):
    monkeypatch.setattr(scorer, "_utcnow", lambda: FIXED_NOW)

    result = score_gate2_candidate(
        "old-market",
        **_candidate_kwargs(),
        market={"volume_24h": 10_000.0, "created_at": _iso(FIXED_NOW - timedelta(hours=72))},
    )

    assert result.is_new_market is False
    assert result.age_hours == pytest.approx(72.0, abs=0.1)
    text = "\n".join(result.explanation)
    assert "NEW MARKET" not in text
    assert "mature" in text


def test_new_market_age_factor_is_nonzero(monkeypatch):
    """New-market age factor (1.0) must contribute to rank_score."""
    monkeypatch.setattr(scorer, "_utcnow", lambda: FIXED_NOW)

    new_m = score_gate2_candidate(
        "new",
        **_candidate_kwargs(),
        market={"volume_24h": None, "created_at": _iso(FIXED_NOW - timedelta(hours=5))},
    )
    old_m = score_gate2_candidate(
        "old",
        **_candidate_kwargs(),
        market={"volume_24h": None, "created_at": _iso(FIXED_NOW - timedelta(hours=200))},
    )

    # New market gets age_factor=1.0, old gets 0.0
    assert new_m.rank_score > old_m.rank_score
    age_contribution = 1.0 * GATE2_RANK_WEIGHTS["age"]
    assert new_m.rank_score - old_m.rank_score == pytest.approx(age_contribution, abs=1e-6)


def test_unknown_age_when_no_created_at(monkeypatch):
    monkeypatch.setattr(scorer, "_utcnow", lambda: FIXED_NOW)

    result = score_gate2_candidate(
        "no-age-market",
        **_candidate_kwargs(),
        market={"volume_24h": 10_000.0},  # no created_at key
    )

    assert result.age_hours is None
    assert result.is_new_market is None
    text = "\n".join(result.explanation)
    assert "age: UNKNOWN" in text


# ---------------------------------------------------------------------------
# Test: explanation / reason-code output
# ---------------------------------------------------------------------------

def test_explanation_contains_gate2_status_codes(monkeypatch):
    monkeypatch.setattr(scorer, "_utcnow", lambda: FIXED_NOW)

    cases = [
        (_candidate_kwargs(executable_ticks=1), "EXECUTABLE"),
        (_candidate_kwargs(edge_ok_ticks=2, depth_ok_ticks=1), "NEAR"),
        (_candidate_kwargs(edge_ok_ticks=3), "EDGE_ONLY"),
        (_candidate_kwargs(depth_ok_ticks=2), "DEPTH_ONLY"),
        (_candidate_kwargs(), "NO_SIGNAL"),
    ]

    for kwargs, expected_status in cases:
        result = score_gate2_candidate("m", **kwargs)
        assert result.gate2_status == expected_status
        assert f"GATE2: {expected_status}" in result.explanation[0]


def test_regime_label_written_when_present(monkeypatch):
    monkeypatch.setattr(scorer, "_utcnow", lambda: FIXED_NOW)

    result = score_gate2_candidate(
        "political-market",
        **_candidate_kwargs(),
        market={"volume_24h": 20_000.0, "_regime": "politics"},
    )

    assert result.regime == "politics"
    text = "\n".join(result.explanation)
    assert "regime: politics" in text
    assert "UNKNOWN" not in [l for l in result.explanation if l.startswith("regime:")][-1]


def test_regime_unknown_when_not_set(monkeypatch):
    monkeypatch.setattr(scorer, "_utcnow", lambda: FIXED_NOW)

    result = score_gate2_candidate("plain-market", **_candidate_kwargs(), market={})
    assert result.regime is None
    text = "\n".join(result.explanation)
    assert "regime: UNKNOWN" in text


# ---------------------------------------------------------------------------
# Test: ranking order
# ---------------------------------------------------------------------------

def test_rank_gate2_candidates_executable_first(monkeypatch):
    monkeypatch.setattr(scorer, "_utcnow", lambda: FIXED_NOW)

    executable = score_gate2_candidate(
        "exec-market",
        **_candidate_kwargs(executable_ticks=3, depth_yes=80.0, depth_no=80.0, best_edge_raw=0.03),
    )
    no_signal = score_gate2_candidate(
        "no-signal",
        **_candidate_kwargs(depth_yes=5.0, depth_no=5.0),
        market={"volume_24h": 100_000.0, "created_at": _iso(FIXED_NOW - timedelta(hours=10))},
        reward_config={"reward_rate": 0.01},
        orderbook={"bids": [], "asks": []},
    )

    ranked = rank_gate2_candidates([no_signal, executable])
    assert ranked[0].slug == "exec-market"
    assert ranked[1].slug == "no-signal"


def test_rank_gate2_candidates_by_rank_score_when_no_executable(monkeypatch):
    monkeypatch.setattr(scorer, "_utcnow", lambda: FIXED_NOW)

    high_quality = score_gate2_candidate(
        "high-quality",
        **_candidate_kwargs(edge_ok_ticks=2, depth_yes=40.0, depth_no=40.0, best_edge_raw=-0.02),
        market={"volume_24h": 50_000.0, "created_at": _iso(FIXED_NOW - timedelta(hours=200))},
        reward_config={"reward_rate": 0.008},
        orderbook={"bids": [], "asks": []},
    )
    low_quality = score_gate2_candidate(
        "low-quality",
        **_candidate_kwargs(edge_ok_ticks=2, depth_yes=40.0, depth_no=40.0, best_edge_raw=-0.02),
        # no metadata → all UNKNOWN except gate2 signals
    )

    ranked = rank_gate2_candidates([low_quality, high_quality])
    assert ranked[0].slug == "high-quality"


def test_rank_gate2_candidates_empty_list():
    assert rank_gate2_candidates([]) == []


# ---------------------------------------------------------------------------
# Test: scan_gate2_candidates integration
# ---------------------------------------------------------------------------

def test_score_and_rank_candidates_integration():
    """score_and_rank_candidates wraps CandidateResult list correctly."""
    from tools.cli.scan_gate2_candidates import CandidateResult, score_and_rank_candidates

    candidates = [
        CandidateResult(
            slug="market-a",
            total_ticks=100,
            depth_ok_ticks=50,
            edge_ok_ticks=30,
            executable_ticks=0,
            best_edge=-0.05,
            max_depth_yes=60.0,
            max_depth_no=55.0,
            source="tape",
        ),
        CandidateResult(
            slug="market-b",
            total_ticks=50,
            depth_ok_ticks=0,
            edge_ok_ticks=0,
            executable_ticks=0,
            best_edge=-98.5,   # sentinel
            max_depth_yes=5.0,
            max_depth_no=3.0,
            source="live",
        ),
    ]

    ranked = score_and_rank_candidates(candidates)

    assert len(ranked) == 2
    assert ranked[0].slug == "market-a"  # higher depth/edge → higher rank_score
    assert ranked[1].slug == "market-b"

    # gate2_status reflects actual signals
    assert ranked[0].gate2_status in ("NEAR", "EDGE_ONLY", "DEPTH_ONLY")
    assert ranked[1].gate2_status == "NO_SIGNAL"

    # All market-quality factors are UNKNOWN (no market_meta etc.)
    assert ranked[0].reward_apr_est is None
    assert ranked[0].volume_24h is None
    assert ranked[0].competition_score is None


def test_score_and_rank_candidates_with_market_meta(monkeypatch):
    monkeypatch.setattr(scorer, "_utcnow", lambda: FIXED_NOW)
    from tools.cli.scan_gate2_candidates import CandidateResult, score_and_rank_candidates

    candidates = [
        CandidateResult(
            slug="politics-market",
            total_ticks=1, depth_ok_ticks=1, edge_ok_ticks=0, executable_ticks=0,
            best_edge=-0.03, max_depth_yes=80.0, max_depth_no=70.0, source="live",
        ),
    ]

    market_meta = {
        "politics-market": {
            "volume_24h": 20_000.0,
            "created_at": _iso(FIXED_NOW - timedelta(hours=30)),
            "_regime": "politics",
        }
    }
    reward_configs = {"politics-market": {"reward_rate": 0.005}}

    ranked = score_and_rank_candidates(
        candidates,
        market_meta=market_meta,
        reward_configs=reward_configs,
    )

    assert len(ranked) == 1
    r = ranked[0]
    assert r.slug == "politics-market"
    assert r.regime == "politics"
    assert r.is_new_market is True  # 30h < 48h
    assert r.volume_24h == pytest.approx(20_000.0)
    assert r.reward_apr_est == pytest.approx(0.005 * 365.0, abs=0.01)
    assert r.rank_score > 0
