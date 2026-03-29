"""Offline tests for momentum signal logic in accumulation_engine.py.

Tests cover:
- MomentumConfig default values and validation
- CryptoPairPaperModeConfig backward-compat with no "momentum" key
- compute_momentum_signal() behavior
- evaluate_directional_entry() gate logic
- AccumulationIntent fields from directional entry
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from packages.polymarket.crypto_pairs.accumulation_engine import (
    ACTION_ACCUMULATE,
    ACTION_FREEZE,
    ACTION_SKIP,
    BestQuote,
    PairMarketState,
    compute_momentum_signal,
    evaluate_directional_entry,
)
from packages.polymarket.crypto_pairs.config_models import (
    CryptoPairPaperModeConfig,
    MomentumConfig,
)
from packages.polymarket.crypto_pairs.reference_feed import (
    FeedConnectionState,
    ReferencePriceSnapshot,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _usable_snapshot(price: float = 85000.0) -> ReferencePriceSnapshot:
    """Return a usable (connected, fresh) feed snapshot."""
    return ReferencePriceSnapshot(
        symbol="BTC",
        price=price,
        observed_at_s=1.0,
        connection_state=FeedConnectionState.CONNECTED,
        is_stale=False,
        stale_threshold_s=15.0,
        feed_source="coinbase",
    )


def _frozen_snapshot() -> ReferencePriceSnapshot:
    """Return an unusable (disconnected) feed snapshot."""
    return ReferencePriceSnapshot(
        symbol="BTC",
        price=None,
        observed_at_s=None,
        connection_state=FeedConnectionState.DISCONNECTED,
        is_stale=True,
        stale_threshold_s=15.0,
        feed_source="none",
    )


def _config_with_momentum(**momentum_overrides) -> CryptoPairPaperModeConfig:
    """Build a config with optional momentum overrides."""
    payload: dict = {
        "max_capital_per_market_usdc": "10",
        "max_open_paired_notional_usdc": "50",
        "edge_buffer_per_leg": "0.04",
        "max_pair_completion_pct": "0.80",
        "min_projected_profit": "0.03",
        "fees": {
            "maker_rebate_bps": "20",
            "maker_fee_bps": "0",
            "taker_fee_bps": "0",
        },
        "safety": {
            "stale_quote_timeout_seconds": 15,
            "max_unpaired_exposure_seconds": 120,
            "block_new_intents_with_open_unpaired": True,
            "require_fresh_quotes": True,
        },
    }
    if momentum_overrides:
        payload["momentum"] = momentum_overrides
    return CryptoPairPaperModeConfig.from_dict(payload)


def _state(
    *,
    yes_ask: float = 0.72,
    no_ask: float = 0.28,
    price_history: tuple[float, ...] = (),
    cooldown_brackets: frozenset[str] = frozenset(),
    market_id: str = "btc-up-5m",
    snapshot: ReferencePriceSnapshot | None = None,
) -> PairMarketState:
    if snapshot is None:
        snapshot = _usable_snapshot()
    return PairMarketState(
        symbol="BTC",
        duration_min=5,
        market_id=market_id,
        yes_quote=BestQuote(leg="YES", token_id="yes-tok", ask_price=Decimal(str(yes_ask))),
        no_quote=BestQuote(leg="NO", token_id="no-tok", ask_price=Decimal(str(no_ask))),
        feed_snapshot=snapshot,
        price_history=price_history,
        cooldown_brackets=cooldown_brackets,
    )


# ---------------------------------------------------------------------------
# Test 1: MomentumConfig default values
# ---------------------------------------------------------------------------


def test_momentum_config_defaults():
    cfg = MomentumConfig()
    assert cfg.momentum_window_seconds == 30
    assert cfg.momentum_threshold == pytest.approx(0.003)
    assert cfg.max_favorite_entry == pytest.approx(0.75)
    assert cfg.max_hedge_price == pytest.approx(0.20)
    assert cfg.favorite_leg_size_usdc == pytest.approx(8.0)
    assert cfg.hedge_leg_size_usdc == pytest.approx(2.0)


# ---------------------------------------------------------------------------
# Test 2: CryptoPairPaperModeConfig backward compat — no "momentum" key
# ---------------------------------------------------------------------------


def test_paper_mode_config_no_momentum_key():
    """CryptoPairPaperModeConfig.from_dict() with no momentum key uses defaults."""
    payload = {
        "max_capital_per_market_usdc": "10",
        "max_open_paired_notional_usdc": "50",
        "edge_buffer_per_leg": "0.04",
        "max_pair_completion_pct": "0.80",
        "min_projected_profit": "0.03",
    }
    cfg = CryptoPairPaperModeConfig.from_dict(payload)
    assert hasattr(cfg, "momentum")
    assert isinstance(cfg.momentum, MomentumConfig)
    assert cfg.momentum.momentum_window_seconds == 30


# ---------------------------------------------------------------------------
# Test 3: CryptoPairPaperModeConfig passes through momentum threshold override
# ---------------------------------------------------------------------------


def test_paper_mode_config_momentum_threshold_override():
    payload = {
        "max_capital_per_market_usdc": "10",
        "max_open_paired_notional_usdc": "50",
        "edge_buffer_per_leg": "0.04",
        "max_pair_completion_pct": "0.80",
        "min_projected_profit": "0.03",
        "momentum": {"momentum_threshold": 0.005},
    }
    cfg = CryptoPairPaperModeConfig.from_dict(payload)
    assert cfg.momentum.momentum_threshold == pytest.approx(0.005)


# ---------------------------------------------------------------------------
# Test 4: evaluate_directional_entry — no price history -> SKIP
# ---------------------------------------------------------------------------


def test_evaluate_directional_entry_no_price_history():
    cfg = _config_with_momentum()
    st = _state(price_history=())
    result = evaluate_directional_entry(st, cfg)
    assert result.action == ACTION_SKIP
    assert result.rationale.get("skip_reason") == "no_momentum_signal"


# ---------------------------------------------------------------------------
# Test 5: evaluate_directional_entry — feed frozen -> FREEZE
# ---------------------------------------------------------------------------


def test_evaluate_directional_entry_feed_frozen():
    cfg = _config_with_momentum()
    st = _state(
        price_history=(100.0, 100.3),
        snapshot=_frozen_snapshot(),
    )
    result = evaluate_directional_entry(st, cfg)
    assert result.action == ACTION_FREEZE


# ---------------------------------------------------------------------------
# Test 6: compute_momentum_signal — 0.3% move fires UP signal
# ---------------------------------------------------------------------------


def test_compute_momentum_signal_up():
    from packages.polymarket.crypto_pairs.accumulation_engine import MomentumSignal
    # Use 100.31 to avoid floating-point edge case at exactly 0.3%
    signal = compute_momentum_signal([100.0, 100.0, 100.31], threshold=0.003)
    assert signal.signal_direction == "UP"
    assert signal.price_change_pct == pytest.approx(0.0031, rel=0.01)


# ---------------------------------------------------------------------------
# Test 7: signal=UP, yes_ask <= max_favorite_entry -> ACCUMULATE, favorite=YES
# ---------------------------------------------------------------------------


def test_evaluate_directional_entry_up_signal_yes_favorite():
    # price history: 1% rise -> UP
    price_history = (100.0, 101.0)
    cfg = _config_with_momentum(momentum_threshold=0.003, max_favorite_entry=0.75, max_hedge_price=0.20)
    st = _state(yes_ask=0.72, no_ask=0.28, price_history=price_history)
    result = evaluate_directional_entry(st, cfg)
    assert result.action == ACTION_ACCUMULATE
    assert "YES" in result.legs
    assert "NO" in result.legs
    assert result.rationale["signal_direction"] == "UP"
    assert result.rationale["favorite_leg"] == "YES"
    assert result.rationale["hedge_leg"] == "NO"
    assert result.rationale["hedge_price"] == pytest.approx(0.20)


# ---------------------------------------------------------------------------
# Test 8: signal=DOWN -> favorite=NO, hedge=YES
# ---------------------------------------------------------------------------


def test_evaluate_directional_entry_down_signal_no_favorite():
    # price history: 1% drop -> DOWN
    price_history = (100.0, 99.0)
    cfg = _config_with_momentum(momentum_threshold=0.003, max_favorite_entry=0.75)
    st = _state(yes_ask=0.30, no_ask=0.70, price_history=price_history)
    result = evaluate_directional_entry(st, cfg)
    assert result.action == ACTION_ACCUMULATE
    assert result.rationale["signal_direction"] == "DOWN"
    assert result.rationale["favorite_leg"] == "NO"
    assert result.rationale["hedge_leg"] == "YES"


# ---------------------------------------------------------------------------
# Test 9: signal=UP, yes_ask > max_favorite_entry -> SKIP
# ---------------------------------------------------------------------------


def test_evaluate_directional_entry_favorite_too_expensive():
    price_history = (100.0, 101.0)  # UP signal
    cfg = _config_with_momentum(momentum_threshold=0.003, max_favorite_entry=0.75)
    st = _state(yes_ask=0.80, no_ask=0.20, price_history=price_history)
    result = evaluate_directional_entry(st, cfg)
    assert result.action == ACTION_SKIP
    assert result.rationale.get("skip_reason") == "favorite_too_expensive"


# ---------------------------------------------------------------------------
# Test 10: bracket already in cooldown -> SKIP
# ---------------------------------------------------------------------------


def test_evaluate_directional_entry_bracket_cooldown():
    price_history = (100.0, 101.0)  # would fire UP
    cfg = _config_with_momentum(momentum_threshold=0.003)
    # market_id is in the cooldown_brackets set
    st = _state(
        yes_ask=0.72,
        no_ask=0.28,
        price_history=price_history,
        market_id="btc-up-5m",
        cooldown_brackets=frozenset({"btc-up-5m"}),
    )
    result = evaluate_directional_entry(st, cfg)
    assert result.action == ACTION_SKIP
    assert result.rationale.get("skip_reason") == "bracket_cooldown"


# ---------------------------------------------------------------------------
# Test 11: AccumulationIntent.to_dict() includes new directional fields
# ---------------------------------------------------------------------------


def test_accumulation_intent_to_dict_includes_directional_fields():
    price_history = (100.0, 101.0)
    cfg = _config_with_momentum(momentum_threshold=0.003)
    st = _state(yes_ask=0.72, no_ask=0.28, price_history=price_history)
    result = evaluate_directional_entry(st, cfg)
    d = result.to_dict()
    assert "signal_direction" in d["rationale"]
    assert "price_change_pct" in d["rationale"]
    assert "reference_price" in d["rationale"]


# ---------------------------------------------------------------------------
# Test 12: leg sizes come from config.momentum
# ---------------------------------------------------------------------------


def test_evaluate_directional_entry_leg_sizes_from_config():
    price_history = (100.0, 101.0)
    cfg = _config_with_momentum(
        momentum_threshold=0.003,
        favorite_leg_size_usdc=12.0,
        hedge_leg_size_usdc=3.0,
    )
    st = _state(yes_ask=0.72, no_ask=0.28, price_history=price_history)
    result = evaluate_directional_entry(st, cfg)
    assert result.action == ACTION_ACCUMULATE
    assert result.rationale["favorite_leg_size_usdc"] == pytest.approx(12.0)
    assert result.rationale["hedge_leg_size_usdc"] == pytest.approx(3.0)
