"""Offline tests for accumulation_engine.py (Track 2 / Phase 1A).

All tests are deterministic — no network, no side-effects.
The engine is a pure function; every test constructs explicit state.
"""

from __future__ import annotations

import json
from decimal import Decimal

import pytest

from packages.polymarket.crypto_pairs.accumulation_engine import (
    ACTION_ACCUMULATE,
    ACTION_FREEZE,
    ACTION_SKIP,
    AccumulationIntent,
    BestQuote,
    LEG_NO,
    LEG_YES,
    PairMarketState,
    evaluate_accumulation,
)
from packages.polymarket.crypto_pairs.config_models import CryptoPairPaperModeConfig
from packages.polymarket.crypto_pairs.reference_feed import (
    BinanceFeed,
    FeedConnectionState,
    ReferencePriceSnapshot,
)


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


def _config(**overrides) -> CryptoPairPaperModeConfig:
    payload = {
        "max_capital_per_market_usdc": "25",
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
    payload.update(overrides)
    return CryptoPairPaperModeConfig.from_dict(payload)


def _fresh_snapshot(symbol: str = "BTC", price: float = 60_000.0) -> ReferencePriceSnapshot:
    """A usable (connected + fresh) snapshot for use in tests."""
    return ReferencePriceSnapshot(
        symbol=symbol,
        price=price,
        observed_at_s=1000.0,
        connection_state=FeedConnectionState.CONNECTED,
        is_stale=False,
        stale_threshold_s=15.0,
        feed_source="binance",
    )


def _stale_snapshot(symbol: str = "BTC") -> ReferencePriceSnapshot:
    return ReferencePriceSnapshot(
        symbol=symbol,
        price=60_000.0,
        observed_at_s=900.0,
        connection_state=FeedConnectionState.CONNECTED,
        is_stale=True,
        stale_threshold_s=15.0,
        feed_source="binance",
    )


def _disconnected_snapshot(symbol: str = "BTC") -> ReferencePriceSnapshot:
    return ReferencePriceSnapshot(
        symbol=symbol,
        price=60_000.0,
        observed_at_s=1000.0,
        connection_state=FeedConnectionState.DISCONNECTED,
        is_stale=False,
        stale_threshold_s=15.0,
        feed_source="binance",
    )


def _quote(leg: str, price: str = "0.47") -> BestQuote:
    return BestQuote(leg=leg, token_id=f"token-{leg.lower()}", ask_price=Decimal(price))


def _state(
    *,
    yes_price: str = "0.47",
    no_price: str = "0.48",
    yes_accumulated: str = "0",
    no_accumulated: str = "0",
    fair_value_yes: float | None = None,
    fair_value_no: float | None = None,
    feed_snapshot: ReferencePriceSnapshot | None = None,
    symbol: str = "BTC",
    market_id: str = "mkt-btc-5m",
    yes_quote: BestQuote | None = ...,  # type: ignore[assignment]
    no_quote: BestQuote | None = ...,   # type: ignore[assignment]
) -> PairMarketState:
    if yes_quote is ...:  # type: ignore[comparison-overlap]
        yes_quote = _quote(LEG_YES, yes_price) if yes_price is not None else None
    if no_quote is ...:  # type: ignore[comparison-overlap]
        no_quote = _quote(LEG_NO, no_price) if no_price is not None else None
    if feed_snapshot is None:
        feed_snapshot = _fresh_snapshot(symbol)
    return PairMarketState(
        symbol=symbol,
        duration_min=5,
        market_id=market_id,
        yes_quote=yes_quote,
        no_quote=no_quote,
        yes_accumulated_size=Decimal(yes_accumulated),
        no_accumulated_size=Decimal(no_accumulated),
        fair_value_yes=fair_value_yes,
        fair_value_no=fair_value_no,
        feed_snapshot=feed_snapshot,
    )


# ---------------------------------------------------------------------------
# Gate 1 — Feed gate (FREEZE on stale / disconnected / missing)
# ---------------------------------------------------------------------------


class TestFeedGate:
    def test_freeze_when_feed_snapshot_is_none(self) -> None:
        cfg = _config()
        st = _state(feed_snapshot=None)
        # Patch: _state uses fresh snapshot by default, so manually clear it
        st2 = PairMarketState(
            symbol=st.symbol,
            duration_min=st.duration_min,
            market_id=st.market_id,
            yes_quote=st.yes_quote,
            no_quote=st.no_quote,
            feed_snapshot=None,
        )
        intent = evaluate_accumulation(st2, cfg)
        assert intent.action == ACTION_FREEZE
        assert intent.legs == ()

    def test_freeze_when_feed_is_stale(self) -> None:
        cfg = _config()
        st = _state(feed_snapshot=_stale_snapshot())
        intent = evaluate_accumulation(st, cfg)
        assert intent.action == ACTION_FREEZE

    def test_freeze_when_feed_is_disconnected(self) -> None:
        cfg = _config()
        st = _state(feed_snapshot=_disconnected_snapshot())
        intent = evaluate_accumulation(st, cfg)
        assert intent.action == ACTION_FREEZE

    def test_freeze_when_never_connected(self) -> None:
        snap = ReferencePriceSnapshot(
            symbol="BTC",
            price=None,
            observed_at_s=None,
            connection_state=FeedConnectionState.NEVER_CONNECTED,
            is_stale=True,
            stale_threshold_s=15.0,
            feed_source="none",
        )
        intent = evaluate_accumulation(_state(feed_snapshot=snap), _config())
        assert intent.action == ACTION_FREEZE

    def test_freeze_rationale_contains_feed_not_usable(self) -> None:
        intent = evaluate_accumulation(_state(feed_snapshot=_stale_snapshot()), _config())
        assert "freeze_reason" in intent.rationale
        assert "feed_not_usable" in intent.rationale["freeze_reason"]

    def test_freeze_rationale_records_feed_usable_false(self) -> None:
        intent = evaluate_accumulation(_state(feed_snapshot=_stale_snapshot()), _config())
        assert intent.rationale["feed_usable"] is False

    def test_fresh_feed_passes_gate(self) -> None:
        """A connected, fresh feed does NOT trigger FREEZE."""
        intent = evaluate_accumulation(_state(), _config())
        assert intent.action != ACTION_FREEZE


# ---------------------------------------------------------------------------
# Gate 2 — Quote availability
# ---------------------------------------------------------------------------


class TestQuoteGate:
    def test_skip_when_yes_quote_missing(self) -> None:
        st = _state(yes_quote=None)
        intent = evaluate_accumulation(st, _config())
        assert intent.action == ACTION_SKIP
        assert "YES" in intent.rationale.get("skip_reason", "")

    def test_skip_when_no_quote_missing(self) -> None:
        st = _state(no_quote=None)
        intent = evaluate_accumulation(st, _config())
        assert intent.action == ACTION_SKIP
        assert "NO" in intent.rationale.get("skip_reason", "")

    def test_skip_when_both_quotes_missing(self) -> None:
        st = _state(yes_quote=None, no_quote=None)
        intent = evaluate_accumulation(st, _config())
        assert intent.action == ACTION_SKIP
        assert "YES" in intent.rationale.get("skip_reason", "")
        assert "NO" in intent.rationale.get("skip_reason", "")

    def test_projected_cost_is_none_when_quotes_missing(self) -> None:
        intent = evaluate_accumulation(_state(yes_quote=None), _config())
        assert intent.projected_pair_cost is None

    def test_hard_rule_false_when_quotes_missing(self) -> None:
        intent = evaluate_accumulation(_state(yes_quote=None), _config())
        assert intent.hard_rule_passed is False


# ---------------------------------------------------------------------------
# Gate 3 — Target-bid gate (per-leg, replaces hard pair-cost rule)
# Default: target_bid = 0.5 - 0.04 = 0.46
# ---------------------------------------------------------------------------


class TestHardRule:
    def test_skip_when_no_leg_meets_target_bid(self) -> None:
        # Both asks above target_bid=0.46
        st = _state(yes_price="0.47", no_price="0.48")
        intent = evaluate_accumulation(st, _config())
        assert intent.action == ACTION_SKIP
        assert intent.hard_rule_passed is False
        assert intent.rationale.get("skip_reason") == "no_leg_meets_target_bid"

    def test_projected_cost_is_populated_when_quotes_present(self) -> None:
        # Even when gate fails, projected_pair_cost is set
        st = _state(yes_price="0.47", no_price="0.48")
        intent = evaluate_accumulation(st, _config())
        assert intent.projected_pair_cost == Decimal("0.95")

    def test_pass_when_both_legs_meet_target_bid(self) -> None:
        # Both asks at 0.44 <= 0.46 target_bid
        st = _state(yes_price="0.44", no_price="0.44")
        intent = evaluate_accumulation(st, _config())
        assert intent.hard_rule_passed is True
        assert intent.action == ACTION_ACCUMULATE

    def test_pass_when_one_leg_meets_target_bid(self) -> None:
        # YES meets (0.44 <= 0.46), NO does not (0.48 > 0.46)
        st = _state(yes_price="0.44", no_price="0.48")
        intent = evaluate_accumulation(st, _config())
        assert intent.hard_rule_passed is True
        # Only YES leg should be included
        assert LEG_YES in intent.legs
        assert LEG_NO not in intent.legs

    def test_target_bid_equals_boundary_passes(self) -> None:
        # ask == target_bid exactly should pass (<=)
        st = _state(yes_price="0.46", no_price="0.46")
        intent = evaluate_accumulation(st, _config())
        assert intent.hard_rule_passed is True
        assert intent.action == ACTION_ACCUMULATE

    def test_custom_edge_buffer_respected(self) -> None:
        # edge_buffer=0.10 → target_bid = 0.40; ask=0.44 > 0.40 → skip
        cfg = _config(edge_buffer_per_leg="0.10")
        st = _state(yes_price="0.44", no_price="0.44")
        intent = evaluate_accumulation(st, cfg)
        assert intent.action == ACTION_SKIP
        assert intent.hard_rule_passed is False

    def test_rationale_records_target_bid(self) -> None:
        st = _state(yes_price="0.44", no_price="0.44")
        intent = evaluate_accumulation(st, _config())
        assert "target_bid" in intent.rationale
        assert intent.rationale["target_bid"] == "0.46"

    def test_rationale_records_per_leg_target_met(self) -> None:
        st = _state(yes_price="0.44", no_price="0.48")
        intent = evaluate_accumulation(st, _config())
        assert intent.rationale["yes_target_met"] is True
        assert intent.rationale["no_target_met"] is False


# ---------------------------------------------------------------------------
# Per-leg target-bid exclusion (formerly "soft rule" tests)
# The soft fair-value rule has been replaced by the per-leg target-bid gate.
# Legs with ask > target_bid are excluded from the intent.
# ---------------------------------------------------------------------------


class TestSoftRule:
    def test_soft_rule_yes_passed_true_when_yes_meets_target(self) -> None:
        """soft_rule_yes_passed field reflects whether YES met the target-bid."""
        st = _state(yes_price="0.44", no_price="0.44")
        intent = evaluate_accumulation(st, _config())
        assert intent.soft_rule_yes_passed is True

    def test_soft_rule_yes_passed_false_when_yes_misses_target(self) -> None:
        """YES ask above target_bid → soft_rule_yes_passed is False."""
        st = _state(yes_price="0.48", no_price="0.44")
        intent = evaluate_accumulation(st, _config())
        assert intent.soft_rule_yes_passed is False

    def test_soft_rule_no_passed_true_when_no_meets_target(self) -> None:
        st = _state(yes_price="0.44", no_price="0.44")
        intent = evaluate_accumulation(st, _config())
        assert intent.soft_rule_no_passed is True

    def test_soft_rule_no_passed_false_when_no_misses_target(self) -> None:
        st = _state(yes_price="0.44", no_price="0.48")
        intent = evaluate_accumulation(st, _config())
        assert intent.soft_rule_no_passed is False

    def test_skip_when_both_legs_miss_target_bid(self) -> None:
        # Both asks above target_bid (0.46)
        st = _state(yes_price="0.47", no_price="0.48")
        intent = evaluate_accumulation(st, _config())
        assert intent.action == ACTION_SKIP
        assert intent.rationale.get("skip_reason") == "no_leg_meets_target_bid"
        assert intent.hard_rule_passed is False

    def test_only_yes_leg_included_when_no_misses_target(self) -> None:
        # YES: 0.44 <= 0.46 (meets), NO: 0.48 > 0.46 (misses)
        st = _state(yes_price="0.44", no_price="0.48")
        intent = evaluate_accumulation(st, _config())
        assert intent.action == ACTION_ACCUMULATE
        assert LEG_YES in intent.legs
        assert LEG_NO not in intent.legs

    def test_only_no_leg_included_when_yes_misses_target(self) -> None:
        # YES: 0.48 > 0.46 (misses), NO: 0.44 <= 0.46 (meets)
        st = _state(yes_price="0.48", no_price="0.44")
        intent = evaluate_accumulation(st, _config())
        assert intent.action == ACTION_ACCUMULATE
        assert LEG_NO in intent.legs
        assert LEG_YES not in intent.legs

    def test_fair_value_fields_ignored_by_engine(self) -> None:
        """fair_value_yes/no are still in PairMarketState but engine ignores them."""
        # With asks at 0.44, both meet target regardless of fair_value fields
        st = _state(yes_price="0.44", no_price="0.44", fair_value_yes=0.30, fair_value_no=0.30)
        intent = evaluate_accumulation(st, _config())
        # Engine does not use fair_value — both legs should still accumulate
        assert intent.action == ACTION_ACCUMULATE
        assert LEG_YES in intent.legs
        assert LEG_NO in intent.legs


# ---------------------------------------------------------------------------
# Happy path: ACCUMULATE
# ---------------------------------------------------------------------------


class TestAccumulateAction:
    def test_accumulate_when_all_gates_pass(self) -> None:
        # Both legs at 0.44 <= target_bid=0.46 → all gates pass
        st = _state(yes_price="0.44", no_price="0.44")
        intent = evaluate_accumulation(st, _config())
        assert intent.action == ACTION_ACCUMULATE

    def test_accumulate_includes_both_legs_when_no_partial(self) -> None:
        st = _state(yes_price="0.44", no_price="0.44")
        intent = evaluate_accumulation(st, _config())
        assert LEG_YES in intent.legs
        assert LEG_NO in intent.legs

    def test_projected_cost_is_populated_on_accumulate(self) -> None:
        st = _state(yes_price="0.44", no_price="0.44")
        intent = evaluate_accumulation(st, _config())
        assert intent.projected_pair_cost == Decimal("0.88")

    def test_accumulate_only_yes_when_no_exceeds_target_bid(self) -> None:
        # YES at 0.44 meets target; NO at 0.48 > target_bid=0.46 → excluded
        st = _state(yes_price="0.44", no_price="0.48")
        intent = evaluate_accumulation(st, _config())
        assert intent.action == ACTION_ACCUMULATE
        assert LEG_YES in intent.legs
        assert LEG_NO not in intent.legs

    def test_accumulate_only_no_when_yes_exceeds_target_bid(self) -> None:
        # NO at 0.44 meets target; YES at 0.48 > target_bid=0.46 → excluded
        st = _state(yes_price="0.48", no_price="0.44")
        intent = evaluate_accumulation(st, _config())
        assert intent.action == ACTION_ACCUMULATE
        assert LEG_NO in intent.legs
        assert LEG_YES not in intent.legs

    def test_to_dict_is_json_serializable(self) -> None:
        st = _state(yes_price="0.44", no_price="0.44")
        intent = evaluate_accumulation(st, _config())
        d = intent.to_dict()
        json.dumps(d)  # must not raise

    def test_to_dict_contains_expected_keys(self) -> None:
        st = _state(yes_price="0.44", no_price="0.44")
        intent = evaluate_accumulation(st, _config())
        d = intent.to_dict()
        for key in ("action", "legs", "rationale", "projected_pair_cost", "hard_rule_passed"):
            assert key in d

    def test_projected_cost_in_dict_is_string(self) -> None:
        st = _state(yes_price="0.44", no_price="0.44")
        intent = evaluate_accumulation(st, _config())
        d = intent.to_dict()
        assert isinstance(d["projected_pair_cost"], str)


# ---------------------------------------------------------------------------
# Partial-pair state logic
# ---------------------------------------------------------------------------


class TestPartialPairLogic:
    def test_yes_only_focuses_on_no_leg(self) -> None:
        """Already hold YES → focus on completing the pair by buying NO."""
        # NO at 0.44 meets target_bid=0.46; yes_only state → only NO eligible
        st = _state(yes_price="0.44", no_price="0.44", yes_accumulated="5", no_accumulated="0")
        intent = evaluate_accumulation(st, _config())
        assert intent.action == ACTION_ACCUMULATE
        assert intent.legs == (LEG_NO,)
        assert LEG_YES not in intent.legs

    def test_no_only_focuses_on_yes_leg(self) -> None:
        """Already hold NO → focus on completing the pair by buying YES."""
        # YES at 0.44 meets target_bid=0.46; no_only state → only YES eligible
        st = _state(yes_price="0.44", no_price="0.44", yes_accumulated="0", no_accumulated="5")
        intent = evaluate_accumulation(st, _config())
        assert intent.action == ACTION_ACCUMULATE
        assert intent.legs == (LEG_YES,)
        assert LEG_NO not in intent.legs

    def test_both_legs_accumulated_considers_all_legs(self) -> None:
        """Full pair already held — engine still evaluates fresh entry for more."""
        st = _state(yes_price="0.44", no_price="0.44", yes_accumulated="5", no_accumulated="5")
        intent = evaluate_accumulation(st, _config())
        assert intent.action == ACTION_ACCUMULATE
        assert LEG_YES in intent.legs
        assert LEG_NO in intent.legs

    def test_yes_only_skip_when_no_misses_target_bid(self) -> None:
        """yes_only but NO ask > target_bid → target-bid gate blocks NO → SKIP."""
        # yes_only state: only NO leg is eligible; NO at 0.48 > 0.46 → SKIP
        st = _state(
            yes_accumulated="5",
            no_accumulated="0",
            yes_price="0.44",
            no_price="0.48",  # 0.48 > target_bid=0.46 → NO excluded
        )
        intent = evaluate_accumulation(st, _config())
        # partial state is yes_only → only NO is eligible; NO misses target → SKIP
        assert intent.action == ACTION_SKIP

    def test_no_only_skip_when_yes_misses_target_bid(self) -> None:
        """no_only but YES ask > target_bid → target-bid gate blocks YES → SKIP."""
        # no_only state: only YES leg is eligible; YES at 0.48 > 0.46 → SKIP
        st = _state(
            yes_accumulated="0",
            no_accumulated="5",
            yes_price="0.48",  # 0.48 > target_bid=0.46 → YES excluded
            no_price="0.44",
        )
        intent = evaluate_accumulation(st, _config())
        # partial state is no_only → only YES is eligible; YES misses target → SKIP
        assert intent.action == ACTION_SKIP

    def test_partial_state_recorded_in_rationale(self) -> None:
        st = _state(yes_price="0.44", no_price="0.44", yes_accumulated="5", no_accumulated="0")
        intent = evaluate_accumulation(st, _config())
        assert intent.rationale["partial_pair_state"] == "yes_only"

    def test_no_partial_state_recorded_as_none(self) -> None:
        st = _state(yes_price="0.44", no_price="0.44")
        intent = evaluate_accumulation(st, _config())
        assert intent.rationale["partial_pair_state"] == "none"


# ---------------------------------------------------------------------------
# Rationale completeness
# ---------------------------------------------------------------------------


class TestRationale:
    def test_rationale_always_includes_base_keys(self) -> None:
        for snapshot in [_fresh_snapshot(), _stale_snapshot(), _disconnected_snapshot()]:
            intent = evaluate_accumulation(_state(feed_snapshot=snapshot), _config())
            for key in ("symbol", "duration_min", "market_id", "feed_usable"):
                assert key in intent.rationale, f"Missing key {key!r} with snapshot {snapshot.connection_state}"

    def test_rationale_symbol_matches_state(self) -> None:
        st = _state(symbol="ETH")
        intent = evaluate_accumulation(st, _config())
        assert intent.rationale["symbol"] == "ETH"

    def test_rationale_market_id_matches_state(self) -> None:
        st = _state(market_id="mkt-eth-15m")
        intent = evaluate_accumulation(st, _config())
        assert intent.rationale["market_id"] == "mkt-eth-15m"
