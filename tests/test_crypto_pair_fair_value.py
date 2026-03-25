"""Offline tests for fair_value.py (Track 2 / Phase 1A).

All tests are deterministic — no network, no randomness.
"""

from __future__ import annotations

import json
import math

import pytest

from packages.polymarket.crypto_pairs.fair_value import (
    DEFAULT_ANNUAL_VOL,
    FairValueEstimate,
    estimate_fair_value,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_BTC_PRICE = 60_000.0
_ETH_PRICE = 3_000.0
_SOL_PRICE = 150.0

# 5 minutes in seconds
_5M_S = 300.0
# 15 minutes in seconds
_15M_S = 900.0


def _yes(
    symbol: str = "BTC",
    underlying_price: float = _BTC_PRICE,
    threshold: float = _BTC_PRICE,
    remaining_seconds: float = _5M_S,
    **kwargs,
) -> FairValueEstimate:
    return estimate_fair_value(
        symbol,
        5,
        "YES",
        underlying_price,
        threshold,
        remaining_seconds,
        **kwargs,
    )


def _no(
    symbol: str = "BTC",
    underlying_price: float = _BTC_PRICE,
    threshold: float = _BTC_PRICE,
    remaining_seconds: float = _5M_S,
    **kwargs,
) -> FairValueEstimate:
    return estimate_fair_value(
        symbol,
        5,
        "NO",
        underlying_price,
        threshold,
        remaining_seconds,
        **kwargs,
    )


# ---------------------------------------------------------------------------
# At-the-money: S == K → d == 0 → P(YES) == 0.5
# ---------------------------------------------------------------------------


class TestEstimateFairValueAtTheMoney:
    def test_btc_yes_atm_near_half(self) -> None:
        est = _yes("BTC", _BTC_PRICE, _BTC_PRICE)
        # d=0 → N(0)=0.5 exactly, clamped to (0.005, 0.995)
        assert abs(est.fair_prob - 0.5) < 1e-9

    def test_eth_no_atm_near_half(self) -> None:
        est = _no("ETH", _ETH_PRICE, _ETH_PRICE)
        # P(NO) = 1 - N(0) = 0.5
        assert abs(est.fair_prob - 0.5) < 1e-9

    def test_sol_yes_atm_near_half(self) -> None:
        est = _yes("SOL", _SOL_PRICE, _SOL_PRICE)
        assert abs(est.fair_prob - 0.5) < 1e-9

    def test_d_param_is_zero_at_atm(self) -> None:
        est = _yes("BTC", _BTC_PRICE, _BTC_PRICE)
        assert abs(est.d_param) < 1e-9


# ---------------------------------------------------------------------------
# Directional: price > threshold → high YES prob; price < threshold → low
# ---------------------------------------------------------------------------


class TestEstimateFairValueDirectional:
    def test_price_well_above_threshold_yes_prob_high(self) -> None:
        # BTC at 63000, threshold 60000 — clearly "up" market
        est = _yes("BTC", underlying_price=63_000.0, threshold=60_000.0)
        assert est.fair_prob > 0.5

    def test_price_well_below_threshold_yes_prob_low(self) -> None:
        # BTC at 57000, threshold 60000 — clearly "down" market
        est = _yes("BTC", underlying_price=57_000.0, threshold=60_000.0)
        assert est.fair_prob < 0.5

    def test_price_well_above_threshold_no_prob_low(self) -> None:
        est = _no("BTC", underlying_price=63_000.0, threshold=60_000.0)
        assert est.fair_prob < 0.5

    def test_price_well_below_threshold_no_prob_high(self) -> None:
        est = _no("BTC", underlying_price=57_000.0, threshold=60_000.0)
        assert est.fair_prob > 0.5

    def test_yes_and_no_are_opposite_direction(self) -> None:
        price, thr = 63_000.0, 60_000.0
        yes = _yes("BTC", price, thr)
        no = _no("BTC", price, thr)
        assert yes.fair_prob > 0.5
        assert no.fair_prob < 0.5


# ---------------------------------------------------------------------------
# Symmetry: P(YES) + P(NO) ≈ 1.0
# ---------------------------------------------------------------------------


class TestEstimateFairValueSymmetry:
    @pytest.mark.parametrize(
        ("symbol", "spot", "thr"),
        [
            ("BTC", 60_000.0, 60_000.0),
            ("BTC", 63_000.0, 60_000.0),
            ("BTC", 57_000.0, 60_000.0),
            ("ETH", 3_000.0, 3_000.0),
            ("SOL", 150.0, 145.0),
        ],
    )
    def test_yes_plus_no_sums_to_one(
        self, symbol: str, spot: float, thr: float
    ) -> None:
        yes_est = estimate_fair_value(symbol, 5, "YES", spot, thr, _5M_S)
        no_est = estimate_fair_value(symbol, 5, "NO", spot, thr, _5M_S)
        # Should sum to exactly 1.0 when neither is clamped; at most 1e-9 drift
        total = yes_est.fair_prob + no_est.fair_prob
        assert abs(total - 1.0) < 1e-9


# ---------------------------------------------------------------------------
# Time decay: shorter remaining time → more extreme probability
# ---------------------------------------------------------------------------


class TestEstimateFairValueTimeDecay:
    def test_short_time_more_extreme_than_long_time(self) -> None:
        """With price above threshold, shorter τ → higher YES prob.

        Use a tiny price deviation (60_050 vs 60_000) so d stays well below
        the ceiling clamp at both time horizons.
        """
        spot, thr = 60_050.0, 60_000.0  # ~0.08% above threshold
        short_est = estimate_fair_value("BTC", 5, "YES", spot, thr, 300.0)
        long_est = estimate_fair_value("BTC", 15, "YES", spot, thr, 3600.0)
        assert short_est.fair_prob > long_est.fair_prob
        # Sanity: neither should hit the ceiling
        assert short_est.fair_prob < 0.995
        assert long_est.fair_prob < 0.995

    def test_longer_time_approaches_half(self) -> None:
        """With large τ, even a directional market approaches 0.5."""
        spot, thr = 65_000.0, 60_000.0
        very_long = estimate_fair_value("BTC", 5, "YES", spot, thr, 365.25 * 86400)
        # Very long time means enormous uncertainty — prob should be near 0.5
        assert abs(very_long.fair_prob - 0.5) < 0.10

    def test_zero_remaining_seconds_does_not_raise(self) -> None:
        """Expiry boundary — clamps τ to minimum, no ZeroDivisionError."""
        est = estimate_fair_value("BTC", 5, "YES", 62_000.0, 60_000.0, 0.0)
        assert 0.0 < est.fair_prob <= 1.0


# ---------------------------------------------------------------------------
# Volatility override: higher vol → prob closer to 0.5
# ---------------------------------------------------------------------------


class TestEstimateFairValueVolOverride:
    def test_higher_vol_softens_directional_estimate(self) -> None:
        """More vol → wider spread → prob closer to 0.5.

        Use a tiny price deviation so the low-vol estimate does not saturate
        the ceiling clamp, keeping both values comparable.
        """
        spot, thr = 60_050.0, 60_000.0  # ~0.08% above threshold
        low_vol = estimate_fair_value("BTC", 5, "YES", spot, thr, _5M_S, annual_vol=0.2)
        high_vol = estimate_fair_value("BTC", 5, "YES", spot, thr, _5M_S, annual_vol=3.0)
        # High vol → d shrinks → prob closer to 0.5
        assert high_vol.fair_prob < low_vol.fair_prob
        # Sanity: low-vol must not have already been clamped
        assert low_vol.fair_prob < 0.995

    def test_vol_override_is_recorded_in_output(self) -> None:
        override_vol = 0.50
        est = estimate_fair_value("BTC", 5, "YES", _BTC_PRICE, _BTC_PRICE, _5M_S, annual_vol=override_vol)
        assert est.annual_vol == override_vol

    def test_default_vol_used_when_none(self) -> None:
        est = _yes("ETH", _ETH_PRICE, _ETH_PRICE)
        assert est.annual_vol == DEFAULT_ANNUAL_VOL["ETH"]


# ---------------------------------------------------------------------------
# Probability clamping
# ---------------------------------------------------------------------------


class TestEstimateFairValueClamping:
    def test_floor_clamp_when_deeply_out_of_money(self) -> None:
        """Price massively below threshold → YES prob hits floor."""
        est = estimate_fair_value("BTC", 5, "YES", 1.0, 60_000.0, _5M_S)
        assert est.fair_prob >= 0.005

    def test_ceil_clamp_when_deeply_in_the_money(self) -> None:
        """Price massively above threshold → YES prob hits ceiling."""
        est = estimate_fair_value("BTC", 5, "YES", 1_000_000.0, 60_000.0, _5M_S)
        assert est.fair_prob <= 0.995

    def test_no_floor_clamp_when_deeply_in_money(self) -> None:
        """Price massively above threshold → NO prob hits floor."""
        est = estimate_fair_value("BTC", 5, "NO", 1_000_000.0, 60_000.0, _5M_S)
        assert est.fair_prob >= 0.005


# ---------------------------------------------------------------------------
# Output fields and serialization
# ---------------------------------------------------------------------------


class TestEstimateFairValueOutputFields:
    def test_output_fields_populated(self) -> None:
        est = _yes()
        assert est.symbol == "BTC"
        assert est.duration_min == 5
        assert est.side == "YES"
        assert est.underlying_price == _BTC_PRICE
        assert est.threshold == _BTC_PRICE
        assert est.remaining_seconds == _5M_S
        assert est.model == "lognormal_no_drift"
        assert len(est.assumptions) >= 1

    def test_to_dict_is_json_serializable(self) -> None:
        est = _yes()
        d = est.to_dict()
        json.dumps(d)  # must not raise

    def test_to_dict_contains_expected_keys(self) -> None:
        est = _yes()
        d = est.to_dict()
        for key in ("symbol", "duration_min", "side", "fair_prob", "d_param", "annual_vol", "model", "assumptions"):
            assert key in d

    def test_symbol_normalised_to_upper(self) -> None:
        est = estimate_fair_value("btc", 5, "YES", _BTC_PRICE, _BTC_PRICE, _5M_S)
        assert est.symbol == "BTC"

    def test_side_normalised_to_upper(self) -> None:
        est = estimate_fair_value("BTC", 5, "yes", _BTC_PRICE, _BTC_PRICE, _5M_S)
        assert est.side == "YES"

    def test_15m_duration_stored_correctly(self) -> None:
        est = estimate_fair_value("ETH", 15, "NO", _ETH_PRICE, _ETH_PRICE, _15M_S)
        assert est.duration_min == 15


# ---------------------------------------------------------------------------
# Validation: error paths
# ---------------------------------------------------------------------------


class TestEstimateFairValueValidation:
    def test_unsupported_symbol_raises(self) -> None:
        with pytest.raises(ValueError, match="Unsupported symbol"):
            estimate_fair_value("DOGE", 5, "YES", 1.0, 1.0, 60.0)

    def test_invalid_side_raises(self) -> None:
        with pytest.raises(ValueError, match="side must be"):
            estimate_fair_value("BTC", 5, "MAYBE", _BTC_PRICE, _BTC_PRICE, _5M_S)

    def test_zero_underlying_price_raises(self) -> None:
        with pytest.raises(ValueError, match="underlying_price"):
            estimate_fair_value("BTC", 5, "YES", 0.0, _BTC_PRICE, _5M_S)

    def test_negative_underlying_price_raises(self) -> None:
        with pytest.raises(ValueError, match="underlying_price"):
            estimate_fair_value("BTC", 5, "YES", -1.0, _BTC_PRICE, _5M_S)

    def test_zero_threshold_raises(self) -> None:
        with pytest.raises(ValueError, match="threshold"):
            estimate_fair_value("BTC", 5, "YES", _BTC_PRICE, 0.0, _5M_S)

    def test_negative_threshold_raises(self) -> None:
        with pytest.raises(ValueError, match="threshold"):
            estimate_fair_value("BTC", 5, "YES", _BTC_PRICE, -1.0, _5M_S)

    def test_case_insensitive_symbol(self) -> None:
        est = estimate_fair_value("sol", 5, "YES", _SOL_PRICE, _SOL_PRICE, _5M_S)
        assert est.symbol == "SOL"

    def test_case_insensitive_side(self) -> None:
        est = estimate_fair_value("SOL", 5, "no", _SOL_PRICE, _SOL_PRICE, _5M_S)
        assert est.side == "NO"
