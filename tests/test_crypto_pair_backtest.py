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
    yes_ask: float | None = 0.47,
    no_ask: float | None = 0.48,
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
        yes_ask=0.47,
        no_ask=0.48,
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
    obs = _obs(yes_ask=None, no_ask=0.48)
    result = _harness().run([obs])
    assert result.observations_total == 1
    assert result.quote_skips == 1
    assert result.intents_generated == 0


def test_missing_no_quote_counts_as_quote_skip() -> None:
    obs = _obs(yes_ask=0.47, no_ask=None)
    result = _harness().run([obs])
    assert result.observations_total == 1
    assert result.quote_skips == 1
    assert result.intents_generated == 0


def test_hard_rule_exceeded_counts_as_hard_rule_skip() -> None:
    # 0.51 + 0.51 = 1.02 > 0.97 threshold
    obs = _obs(yes_ask=0.51, no_ask=0.51)
    result = _harness().run([obs])
    assert result.observations_total == 1
    assert result.hard_rule_skips == 1
    assert result.intents_generated == 0


def test_soft_rule_blocks_all_legs_counts_as_soft_rule_skip() -> None:
    # Strategy: simulate yes_only partial state (yes_accumulated_size=1.0).
    # In yes_only state the engine only evaluates the NO leg via soft rule.
    # With S==K, fair_no ≈ 0.5.  Set no_ask=0.60 > 0.5 → NO soft rule fails.
    # Set yes_ask=0.36 so pair_cost = 0.36 + 0.60 = 0.96 ≤ 0.97 (hard rule passes).
    # Result: empty legs → soft_rule_blocked_all_legs → soft_rule_skip.
    obs = BacktestObservation(
        symbol="BTC",
        duration_min=5,
        market_id="mkt-btc-5m",
        yes_ask=0.36,
        no_ask=0.60,
        underlying_price=60000.0,
        threshold=60000.0,   # S == K → p_yes ≈ 0.5, fair_no ≈ 0.5
        remaining_seconds=300.0,
        yes_accumulated_size=1.0,  # yes_only state → focus on NO only
    )
    result = _harness().run([obs])
    assert result.observations_total == 1
    assert result.soft_rule_skips == 1
    assert result.intents_generated == 0


def test_clean_observation_below_threshold_generates_intent() -> None:
    # 0.47 + 0.48 = 0.95 < 0.97 → hard rule passes
    # No fair values → soft rule vacuously passes
    obs = _obs(yes_ask=0.47, no_ask=0.48)
    result = _harness().run([obs])
    assert result.observations_total == 1
    assert result.intents_generated == 1
    assert result.hard_rule_skips == 0
    assert result.feed_stale_skips == 0
    assert result.quote_skips == 0


def test_completed_pair_both_legs_counted_in_completed_pairs_simulated() -> None:
    # With no fair values, both legs pass soft rule → ACCUMULATE (YES, NO) → completed pair
    obs = _obs(yes_ask=0.47, no_ask=0.48)
    result = _harness().run([obs])
    assert result.completed_pairs_simulated == 1
    assert result.partial_leg_intents == 0


def test_partial_leg_intent_counted_in_partial_leg_intents() -> None:
    # Use S >> K so p_yes ~1.0, fair_yes ~0.995, fair_no ~0.005
    # yes_ask=0.47 < 0.995 → passes
    # no_ask=0.48 > 0.005 → FAILS soft rule for NO
    # → legs=(YES,) → partial intent
    obs = _obs(
        yes_ask=0.47,
        no_ask=0.48,
        underlying_price=200000.0,  # BTC far above threshold
        threshold=50000.0,          # threshold well below current price
        remaining_seconds=300.0,
    )
    result = _harness().run([obs])
    # yes passes soft (0.47 < ~0.995), no fails soft (0.48 > ~0.005)
    # → ACCUMULATE with legs=(YES,) only
    assert result.intents_generated == 1
    assert result.partial_leg_intents == 1
    assert result.completed_pairs_simulated == 0


def test_avg_pair_cost_correct_for_single_completed_pair() -> None:
    obs = _obs(yes_ask=0.47, no_ask=0.48)
    result = _harness().run([obs])
    assert result.completed_pairs_simulated == 1
    assert result.avg_completed_pair_cost is not None
    assert abs(result.avg_completed_pair_cost - 0.95) < 1e-9


def test_est_profit_correct_for_single_completed_pair() -> None:
    obs = _obs(yes_ask=0.47, no_ask=0.48)
    result = _harness().run([obs])
    assert result.est_profit_per_completed_pair is not None
    # est_profit = 1.0 - 0.95 = 0.05
    assert abs(result.est_profit_per_completed_pair - 0.05) < 1e-9


def test_deterministic_repeated_run_same_input_same_output() -> None:
    observations = [
        _obs(yes_ask=0.47, no_ask=0.48),
        _obs(feed_is_stale=True),
        _obs(yes_ask=0.51, no_ask=0.51),
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
        _obs(yes_ask=0.47, no_ask=0.48),
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
        _obs(yes_ask=0.47, no_ask=0.48),          # intent
        _obs(feed_is_stale=True),                   # feed_stale_skip
        _obs(yes_ask=0.51, no_ask=0.51),            # hard_rule_skip (1.02 > 0.97)
        _obs(yes_ask=None),                         # quote_skip
        _obs(yes_ask=0.45, no_ask=0.49),            # intent (0.94 < 0.97)
    ]
    result = _harness().run(observations)
    assert result.observations_total == 5
    assert result.feed_stale_skips == 1
    assert result.hard_rule_skips == 1
    assert result.quote_skips == 1
    assert result.intents_generated == 2
    assert result.completed_pairs_simulated == 2


def test_avg_pair_cost_averages_multiple_completed_pairs() -> None:
    observations = [
        _obs(yes_ask=0.40, no_ask=0.50),  # pair_cost=0.90
        _obs(yes_ask=0.45, no_ask=0.50),  # pair_cost=0.95
    ]
    result = _harness().run(observations)
    assert result.completed_pairs_simulated == 2
    expected_avg = (0.90 + 0.95) / 2
    assert abs(result.avg_completed_pair_cost - expected_avg) < 1e-9


def test_safety_skips_always_zero_v0() -> None:
    obs = _obs(yes_ask=0.47, no_ask=0.48)
    result = _harness().run([obs])
    assert result.safety_skips == 0


def test_run_id_is_string() -> None:
    result = _harness().run([])
    assert isinstance(result.run_id, str)
    assert len(result.run_id) > 0


def test_config_snapshot_has_target_pair_cost_threshold() -> None:
    result = _harness().run([])
    assert "target_pair_cost_threshold" in result.config_snapshot


def test_both_missing_quotes_counts_as_single_quote_skip() -> None:
    obs = _obs(yes_ask=None, no_ask=None)
    result = _harness().run([obs])
    assert result.quote_skips == 1


def test_fair_value_not_computed_when_params_missing() -> None:
    # No threshold/remaining_seconds → soft rule vacuously passes both legs
    obs = _obs(yes_ask=0.47, no_ask=0.48, underlying_price=60000.0)
    result = _harness().run([obs])
    # Both legs pass vacuously → completed pair
    assert result.completed_pairs_simulated == 1


def test_hard_rule_at_exact_threshold_passes() -> None:
    # default threshold is 0.97; 0.49 + 0.48 = 0.97 exactly → should pass
    obs = _obs(yes_ask=0.49, no_ask=0.48)
    result = _harness().run([obs])
    assert result.hard_rule_skips == 0
    assert result.intents_generated == 1
