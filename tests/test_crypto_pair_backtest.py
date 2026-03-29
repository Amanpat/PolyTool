"""Offline deterministic tests for BacktestHarness (Phase 1A crypto-pair bot).

All tests use synthetic observations only — no network calls, no filesystem
writes from the harness itself.
"""

from __future__ import annotations

import json
from decimal import Decimal

import pytest

from packages.polymarket.crypto_pairs.backtest_harness import (
    BacktestHarness,
    BacktestObservation,
    BacktestResult,
)


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


def _obs(
    *,
    symbol: str = "BTC",
    duration_min: int = 5,
    market_id: str = "mkt-btc-5m",
    yes_ask: float | None = 0.44,
    no_ask: float | None = 0.44,
    underlying_price: float | None = None,
    threshold: float | None = None,
    remaining_seconds: float | None = None,
    feed_is_stale: bool = False,
    yes_accumulated_size: float = 0.0,
    no_accumulated_size: float = 0.0,
    timestamp_iso: str | None = None,
) -> BacktestObservation:
    return BacktestObservation(
        symbol=symbol,
        duration_min=duration_min,
        market_id=market_id,
        yes_ask=yes_ask,
        no_ask=no_ask,
        underlying_price=underlying_price,
        threshold=threshold,
        remaining_seconds=remaining_seconds,
        feed_is_stale=feed_is_stale,
        yes_accumulated_size=yes_accumulated_size,
        no_accumulated_size=no_accumulated_size,
        timestamp_iso=timestamp_iso,
    )


def _harness() -> BacktestHarness:
    return BacktestHarness()


# ---------------------------------------------------------------------------
# BacktestObservation dataclass
# ---------------------------------------------------------------------------


def test_observation_defaults() -> None:
    obs = BacktestObservation(
        symbol="BTC",
        duration_min=5,
        market_id="mkt-btc-5m",
        yes_ask=0.44,
        no_ask=0.44,
    )
    assert obs.feed_is_stale is False
    assert obs.underlying_price is None
    assert obs.threshold is None
    assert obs.remaining_seconds is None
    assert obs.yes_accumulated_size == 0.0
    assert obs.no_accumulated_size == 0.0
    assert obs.timestamp_iso is None


# ---------------------------------------------------------------------------
# Basic count tests
# ---------------------------------------------------------------------------


def test_empty_observations_returns_zero_counts() -> None:
    result = _harness().run([])
    assert result.observations_total == 0
    assert result.feed_stale_skips == 0
    assert result.safety_skips == 0
    assert result.quote_skips == 0
    assert result.hard_rule_skips == 0
    assert result.soft_rule_skips == 0
    assert result.intents_generated == 0
    assert result.partial_leg_intents == 0
    assert result.completed_pairs_simulated == 0
    assert result.avg_completed_pair_cost is None
    assert result.est_profit_per_completed_pair is None


def test_stale_feed_counts_as_feed_stale_skip() -> None:
    obs = _obs(feed_is_stale=True)
    result = _harness().run([obs])
    assert result.observations_total == 1
    assert result.feed_stale_skips == 1
    assert result.intents_generated == 0


def test_missing_yes_quote_counts_as_quote_skip() -> None:
    obs = _obs(yes_ask=None, no_ask=0.44)
    result = _harness().run([obs])
    assert result.observations_total == 1
    assert result.quote_skips == 1
    assert result.intents_generated == 0


def test_missing_no_quote_counts_as_quote_skip() -> None:
    obs = _obs(yes_ask=0.44, no_ask=None)
    result = _harness().run([obs])
    assert result.observations_total == 1
    assert result.quote_skips == 1
    assert result.intents_generated == 0


def test_hard_rule_exceeded_counts_as_hard_rule_skip() -> None:
    # Both asks above target_bid=0.46 → no_leg_meets_target_bid → hard_rule_skip
    obs = _obs(yes_ask=0.51, no_ask=0.51)
    result = _harness().run([obs])
    assert result.observations_total == 1
    assert result.hard_rule_skips == 1
    assert result.intents_generated == 0


def test_soft_rule_skips_always_zero_v1() -> None:
    # The soft fair-value rule has been replaced by the per-leg target-bid gate.
    # soft_rule_skips should always be 0 regardless of observations.
    # A yes_only partial state where NO exceeds target_bid is now a hard_rule_skip.
    obs = BacktestObservation(
        symbol="BTC",
        duration_min=5,
        market_id="mkt-btc-5m",
        yes_ask=0.44,
        no_ask=0.48,          # > target_bid=0.46 → NO excluded
        yes_accumulated_size=1.0,  # yes_only state → focus on NO only
    )
    result = _harness().run([obs])
    assert result.observations_total == 1
    assert result.soft_rule_skips == 0
    assert result.hard_rule_skips == 1
    assert result.intents_generated == 0


def test_clean_observation_below_target_bid_generates_intent() -> None:
    # Both asks at 0.44 <= target_bid=0.46 → target-bid gate passes → ACCUMULATE
    obs = _obs(yes_ask=0.44, no_ask=0.44)
    result = _harness().run([obs])
    assert result.observations_total == 1
    assert result.intents_generated == 1
    assert result.hard_rule_skips == 0
    assert result.feed_stale_skips == 0
    assert result.quote_skips == 0


def test_completed_pair_both_legs_counted_in_completed_pairs_simulated() -> None:
    # Both legs at 0.44 <= target_bid=0.46 → ACCUMULATE (YES, NO) → completed pair
    obs = _obs(yes_ask=0.44, no_ask=0.44)
    result = _harness().run([obs])
    assert result.completed_pairs_simulated == 1
    assert result.partial_leg_intents == 0


def test_partial_leg_intent_counted_in_partial_leg_intents() -> None:
    # YES at 0.44 meets target_bid=0.46; NO at 0.48 > 0.46 → NO excluded
    # → legs=(YES,) only → partial intent
    obs = _obs(yes_ask=0.44, no_ask=0.48)
    result = _harness().run([obs])
    assert result.intents_generated == 1
    assert result.partial_leg_intents == 1
    assert result.completed_pairs_simulated == 0


def test_avg_pair_cost_correct_for_single_completed_pair() -> None:
    # Both at 0.44 → pair_cost = 0.88
    obs = _obs(yes_ask=0.44, no_ask=0.44)
    result = _harness().run([obs])
    assert result.completed_pairs_simulated == 1
    assert result.avg_completed_pair_cost is not None
    assert abs(result.avg_completed_pair_cost - 0.88) < 1e-9


def test_est_profit_correct_for_single_completed_pair() -> None:
    # Both at 0.44 → pair_cost = 0.88 → est_profit = 1.0 - 0.88 = 0.12
    obs = _obs(yes_ask=0.44, no_ask=0.44)
    result = _harness().run([obs])
    assert result.est_profit_per_completed_pair is not None
    assert abs(result.est_profit_per_completed_pair - 0.12) < 1e-9


def test_deterministic_repeated_run_same_input_same_output() -> None:
    observations = [
        _obs(yes_ask=0.44, no_ask=0.44),   # intent
        _obs(feed_is_stale=True),            # feed_stale_skip
        _obs(yes_ask=0.51, no_ask=0.51),    # hard_rule_skip (both > 0.46)
    ]
    h = _harness()
    result_a = h.run(observations)
    result_b = h.run(observations)
    # run_id will differ between calls (uuid), so compare the metrics
    assert result_a.observations_total == result_b.observations_total
    assert result_a.feed_stale_skips == result_b.feed_stale_skips
    assert result_a.hard_rule_skips == result_b.hard_rule_skips
    assert result_a.intents_generated == result_b.intents_generated
    assert result_a.completed_pairs_simulated == result_b.completed_pairs_simulated


def test_result_to_dict_is_json_serializable() -> None:
    observations = [
        _obs(yes_ask=0.44, no_ask=0.44),
        _obs(feed_is_stale=True),
    ]
    result = _harness().run(observations)
    d = result.to_dict()
    # Must not raise
    serialized = json.dumps(d)
    loaded = json.loads(serialized)
    assert loaded["observations_total"] == 2
    assert loaded["feed_stale_skips"] == 1
    assert loaded["intents_generated"] == 1


# ---------------------------------------------------------------------------
# Multi-observation aggregation
# ---------------------------------------------------------------------------


def test_mixed_observations_correct_counts() -> None:
    observations = [
        _obs(yes_ask=0.44, no_ask=0.44),            # intent (both <= 0.46)
        _obs(feed_is_stale=True),                    # feed_stale_skip
        _obs(yes_ask=0.51, no_ask=0.51),             # hard_rule_skip (both > 0.46)
        _obs(yes_ask=None),                          # quote_skip
        _obs(yes_ask=0.44, no_ask=0.44),             # intent (both <= 0.46)
    ]
    result = _harness().run(observations)
    assert result.observations_total == 5
    assert result.feed_stale_skips == 1
    assert result.hard_rule_skips == 1
    assert result.quote_skips == 1
    assert result.intents_generated == 2
    assert result.completed_pairs_simulated == 2


def test_avg_pair_cost_averages_multiple_completed_pairs() -> None:
    # Both legs must be <= target_bid=0.46 for completed-pair count
    observations = [
        _obs(yes_ask=0.40, no_ask=0.44),  # pair_cost=0.84; both <= 0.46
        _obs(yes_ask=0.44, no_ask=0.42),  # pair_cost=0.86; both <= 0.46
    ]
    result = _harness().run(observations)
    assert result.completed_pairs_simulated == 2
    expected_avg = (0.84 + 0.86) / 2
    assert abs(result.avg_completed_pair_cost - expected_avg) < 1e-9


def test_safety_skips_always_zero_v0() -> None:
    obs = _obs(yes_ask=0.44, no_ask=0.44)
    result = _harness().run([obs])
    assert result.safety_skips == 0


def test_run_id_is_string() -> None:
    result = _harness().run([])
    assert isinstance(result.run_id, str)
    assert len(result.run_id) > 0


def test_config_snapshot_has_edge_buffer_per_leg() -> None:
    result = _harness().run([])
    assert "edge_buffer_per_leg" in result.config_snapshot


def test_both_missing_quotes_counts_as_single_quote_skip() -> None:
    obs = _obs(yes_ask=None, no_ask=None)
    result = _harness().run([obs])
    assert result.quote_skips == 1


def test_fair_value_not_computed_when_params_missing() -> None:
    # No threshold/remaining_seconds → fair values not computed; target-bid gate still applies
    # Both asks at 0.44 <= target_bid=0.46 → both legs pass → completed pair
    obs = _obs(yes_ask=0.44, no_ask=0.44, underlying_price=60000.0)
    result = _harness().run([obs])
    assert result.completed_pairs_simulated == 1


def test_hard_rule_at_exact_target_bid_passes() -> None:
    # ask == target_bid=0.46 exactly → should pass (<=)
    obs = _obs(yes_ask=0.46, no_ask=0.46)
    result = _harness().run([obs])
    assert result.hard_rule_skips == 0
    assert result.intents_generated == 1
