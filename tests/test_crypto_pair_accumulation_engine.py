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
        "target_pair_cost_threshold": "0.97",
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
# Gate 3 — Hard pair-cost rule
# ---------------------------------------------------------------------------


class TestHardRule:
    def test_skip_when_pair_cost_exceeds_threshold(self) -> None:
        # 0.50 + 0.50 = 1.00 > 0.97
        st = _state(yes_price="0.50", no_price="0.50")
        intent = evaluate_accumulation(st, _config())
        assert intent.action == ACTION_SKIP
        assert intent.hard_rule_passed is False
        assert intent.rationale.get("skip_reason") == "hard_rule_failed"

    def test_projected_cost_is_populated_on_hard_failure(self) -> None:
        st = _state(yes_price="0.50", no_price="0.50")
        intent = evaluate_accumulation(st, _config())
        assert intent.projected_pair_cost == Decimal("1.00")

    def test_pass_when_pair_cost_equals_threshold(self) -> None:
        # threshold = 0.97; 0.49 + 0.48 = 0.97 — should pass (<=)
        st = _state(yes_price="0.49", no_price="0.48")
        intent = evaluate_accumulation(st, _config())
        assert intent.hard_rule_passed is True
        # May still be SKIP if soft rule blocks, but hard rule passed
        assert intent.action != ACTION_SKIP or intent.rationale.get("skip_reason") != "hard_rule_failed"

    def test_pass_when_pair_cost_below_threshold(self) -> None:
        st = _state(yes_price="0.47", no_price="0.48")
        intent = evaluate_accumulation(st, _config())
        assert intent.hard_rule_passed is True

    def test_custom_threshold_respected(self) -> None:
        cfg = _config(target_pair_cost_threshold="0.90")
        st = _state(yes_price="0.46", no_price="0.46")  # 0.92 > 0.90
        intent = evaluate_accumulation(st, cfg)
        assert intent.action == ACTION_SKIP
        assert intent.hard_rule_passed is False


# ---------------------------------------------------------------------------
# Gate 4 — Soft fair-value rule
# ---------------------------------------------------------------------------


class TestSoftRule:
    def test_vacuous_pass_when_no_fair_values(self) -> None:
        """No fair-value estimates → soft rule vacuously passes both legs."""
        st = _state(yes_price="0.47", no_price="0.48", fair_value_yes=None, fair_value_no=None)
        intent = evaluate_accumulation(st, _config())
        assert intent.soft_rule_yes_passed is True
        assert intent.soft_rule_no_passed is True

    def test_soft_yes_passes_when_ask_below_fair_value(self) -> None:
        # ask=0.47 < fair=0.55 → passes
        st = _state(yes_price="0.47", no_price="0.48", fair_value_yes=0.55, fair_value_no=0.55)
        intent = evaluate_accumulation(st, _config())
        assert intent.soft_rule_yes_passed is True

    def test_soft_yes_fails_when_ask_equals_fair_value(self) -> None:
        # ask=0.55 == fair=0.55 → NOT strictly below → fails
        st = _state(yes_price="0.55", no_price="0.40", fair_value_yes=0.55, fair_value_no=0.55)
        intent = evaluate_accumulation(st, _config())
        assert intent.soft_rule_yes_passed is False

    def test_soft_yes_fails_when_ask_above_fair_value(self) -> None:
        # ask=0.60 > fair=0.55 → overpriced → fails
        st = _state(yes_price="0.60", no_price="0.30", fair_value_yes=0.55, fair_value_no=0.55)
        intent = evaluate_accumulation(st, _config())
        assert intent.soft_rule_yes_passed is False

    def test_soft_no_passes_when_ask_below_fair_value(self) -> None:
        st = _state(yes_price="0.47", no_price="0.48", fair_value_yes=0.55, fair_value_no=0.55)
        intent = evaluate_accumulation(st, _config())
        assert intent.soft_rule_no_passed is True

    def test_skip_when_both_legs_blocked_by_soft_rule(self) -> None:
        # Both asks above their fair values
        st = _state(yes_price="0.60", no_price="0.30", fair_value_yes=0.50, fair_value_no=0.25)
        intent = evaluate_accumulation(st, _config())
        assert intent.action == ACTION_SKIP
        assert intent.rationale.get("skip_reason") == "soft_rule_blocked_all_legs"
        assert intent.hard_rule_passed is True

    def test_rationale_records_soft_rule_details(self) -> None:
        st = _state(yes_price="0.47", no_price="0.48", fair_value_yes=0.55, fair_value_no=0.55)
        intent = evaluate_accumulation(st, _config())
        assert "soft_rule_yes" in intent.rationale
        assert "soft_rule_no" in intent.rationale

    def test_soft_rule_reason_underpriced_when_passes(self) -> None:
        st = _state(yes_price="0.47", no_price="0.48", fair_value_yes=0.55, fair_value_no=0.55)
        intent = evaluate_accumulation(st, _config())
        assert intent.rationale["soft_rule_yes"]["reason"] == "underpriced"

    def test_soft_rule_reason_overpriced_when_fails(self) -> None:
        st = _state(yes_price="0.60", no_price="0.30", fair_value_yes=0.55, fair_value_no=0.55)
        intent = evaluate_accumulation(st, _config())
        assert intent.rationale["soft_rule_yes"]["reason"] == "overpriced"

    def test_vacuous_pass_recorded_in_rationale(self) -> None:
        st = _state(yes_price="0.47", no_price="0.48")
        intent = evaluate_accumulation(st, _config())
        assert intent.rationale["soft_rule_yes"]["reason"] == "no_fair_value_estimate"


# ---------------------------------------------------------------------------
# Happy path: ACCUMULATE
# ---------------------------------------------------------------------------


class TestAccumulateAction:
    def test_accumulate_when_all_gates_pass(self) -> None:
        # 0.47 + 0.48 = 0.95 < 0.97; no fair values → vacuous pass
        st = _state(yes_price="0.47", no_price="0.48")
        intent = evaluate_accumulation(st, _config())
        assert intent.action == ACTION_ACCUMULATE

    def test_accumulate_includes_both_legs_when_no_partial(self) -> None:
        st = _state(yes_price="0.47", no_price="0.48")
        intent = evaluate_accumulation(st, _config())
        assert LEG_YES in intent.legs
        assert LEG_NO in intent.legs

    def test_projected_cost_is_populated_on_accumulate(self) -> None:
        st = _state(yes_price="0.47", no_price="0.48")
        intent = evaluate_accumulation(st, _config())
        assert intent.projected_pair_cost == Decimal("0.95")

    def test_accumulate_only_yes_when_no_blocked_by_soft(self) -> None:
        # YES underpriced; NO overpriced
        st = _state(yes_price="0.47", no_price="0.48", fair_value_yes=0.55, fair_value_no=0.40)
        intent = evaluate_accumulation(st, _config())
        assert intent.action == ACTION_ACCUMULATE
        assert LEG_YES in intent.legs
        assert LEG_NO not in intent.legs

    def test_accumulate_only_no_when_yes_blocked_by_soft(self) -> None:
        # NO underpriced; YES overpriced
        st = _state(yes_price="0.60", no_price="0.35", fair_value_yes=0.55, fair_value_no=0.40)
        intent = evaluate_accumulation(st, _config())
        assert intent.action == ACTION_ACCUMULATE
        assert LEG_NO in intent.legs
        assert LEG_YES not in intent.legs

    def test_to_dict_is_json_serializable(self) -> None:
        st = _state(yes_price="0.47", no_price="0.48")
        intent = evaluate_accumulation(st, _config())
        d = intent.to_dict()
        json.dumps(d)  # must not raise

    def test_to_dict_contains_expected_keys(self) -> None:
        st = _state(yes_price="0.47", no_price="0.48")
        intent = evaluate_accumulation(st, _config())
        d = intent.to_dict()
        for key in ("action", "legs", "rationale", "projected_pair_cost", "hard_rule_passed"):
            assert key in d

    def test_projected_cost_in_dict_is_string(self) -> None:
        st = _state(yes_price="0.47", no_price="0.48")
        intent = evaluate_accumulation(st, _config())
        d = intent.to_dict()
        assert isinstance(d["projected_pair_cost"], str)


# ---------------------------------------------------------------------------
# Partial-pair state logic
# ---------------------------------------------------------------------------


class TestPartialPairLogic:
    def test_yes_only_focuses_on_no_leg(self) -> None:
        """Already hold YES → focus on completing the pair by buying NO."""
        st = _state(yes_accumulated="5", no_accumulated="0")
        intent = evaluate_accumulation(st, _config())
        assert intent.action == ACTION_ACCUMULATE
        assert intent.legs == (LEG_NO,)
        assert LEG_YES not in intent.legs

    def test_no_only_focuses_on_yes_leg(self) -> None:
        """Already hold NO → focus on completing the pair by buying YES."""
        st = _state(yes_accumulated="0", no_accumulated="5")
        intent = evaluate_accumulation(st, _config())
        assert intent.action == ACTION_ACCUMULATE
        assert intent.legs == (LEG_YES,)
        assert LEG_NO not in intent.legs

    def test_both_legs_accumulated_considers_all_legs(self) -> None:
        """Full pair already held — engine still evaluates fresh entry for more."""
        st = _state(yes_accumulated="5", no_accumulated="5")
        intent = evaluate_accumulation(st, _config())
        assert intent.action == ACTION_ACCUMULATE
        assert LEG_YES in intent.legs
        assert LEG_NO in intent.legs

    def test_yes_only_skip_when_soft_blocks_no(self) -> None:
        """yes_only but NO leg is overpriced → soft rule blocks → SKIP."""
        st = _state(
            yes_accumulated="5",
            no_accumulated="0",
            fair_value_yes=0.55,
            fair_value_no=0.40,
            yes_price="0.47",
            no_price="0.48",  # 0.48 > 0.40 → NO overpriced
        )
        intent = evaluate_accumulation(st, _config())
        # partial state is yes_only → only NO is eligible
        # soft rule blocks NO → SKIP
        assert intent.action == ACTION_SKIP

    def test_no_only_skip_when_soft_blocks_yes(self) -> None:
        """no_only but YES leg is overpriced → soft rule blocks → SKIP."""
        st = _state(
            yes_accumulated="0",
            no_accumulated="5",
            fair_value_yes=0.40,
            fair_value_no=0.55,
            yes_price="0.48",  # 0.48 > 0.40 → YES overpriced
            no_price="0.47",
        )
        intent = evaluate_accumulation(st, _config())
        # partial state is no_only → only YES is eligible
        # soft rule blocks YES → SKIP
        assert intent.action == ACTION_SKIP

    def test_partial_state_recorded_in_rationale(self) -> None:
        st = _state(yes_accumulated="5", no_accumulated="0")
        intent = evaluate_accumulation(st, _config())
        assert intent.rationale["partial_pair_state"] == "yes_only"

    def test_no_partial_state_recorded_as_none(self) -> None:
        st = _state()
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
