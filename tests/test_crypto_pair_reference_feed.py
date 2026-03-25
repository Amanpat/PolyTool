"""Offline tests for BinanceFeed reference price feed (Track 2 / Phase 1A).

All tests use injectable clocks and _inject_price() — no network required.
"""

from __future__ import annotations

import json

import pytest

from packages.polymarket.crypto_pairs.reference_feed import (
    DEFAULT_STALE_THRESHOLD_S,
    AutoReferenceFeed,
    BinanceFeed,
    CoinbaseFeed,
    FeedConnectionState,
    ReferencePriceSnapshot,
    build_reference_feed,
    normalize_coinbase_product_id,
    normalize_reference_feed_provider,
    parse_coinbase_ws_message,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _feed(stale_threshold_s: float = 15.0, *, now: float = 1000.0) -> BinanceFeed:
    """Create a feed with a fixed-time clock."""
    return BinanceFeed(stale_threshold_s=stale_threshold_s, _time_fn=lambda: now)


def _coinbase_feed(
    stale_threshold_s: float = 15.0,
    *,
    now: float = 1000.0,
) -> CoinbaseFeed:
    """Create a Coinbase feed with a fixed-time clock."""
    return CoinbaseFeed(stale_threshold_s=stale_threshold_s, _time_fn=lambda: now)


# ---------------------------------------------------------------------------
# ReferencePriceSnapshot unit tests
# ---------------------------------------------------------------------------


class TestReferencePriceSnapshot:
    def test_is_usable_connected_and_fresh(self) -> None:
        snap = ReferencePriceSnapshot(
            symbol="BTC",
            price=60000.0,
            observed_at_s=999.0,
            connection_state=FeedConnectionState.CONNECTED,
            is_stale=False,
            stale_threshold_s=15.0,
            feed_source="binance",
        )
        assert snap.is_usable is True

    def test_not_usable_when_price_is_none(self) -> None:
        snap = ReferencePriceSnapshot(
            symbol="BTC",
            price=None,
            observed_at_s=None,
            connection_state=FeedConnectionState.CONNECTED,
            is_stale=True,
            stale_threshold_s=15.0,
            feed_source="none",
        )
        assert snap.is_usable is False

    def test_not_usable_when_stale(self) -> None:
        snap = ReferencePriceSnapshot(
            symbol="ETH",
            price=3000.0,
            observed_at_s=900.0,
            connection_state=FeedConnectionState.CONNECTED,
            is_stale=True,
            stale_threshold_s=15.0,
            feed_source="binance",
        )
        assert snap.is_usable is False

    def test_not_usable_when_disconnected(self) -> None:
        snap = ReferencePriceSnapshot(
            symbol="SOL",
            price=150.0,
            observed_at_s=999.0,
            connection_state=FeedConnectionState.DISCONNECTED,
            is_stale=False,
            stale_threshold_s=15.0,
            feed_source="binance",
        )
        assert snap.is_usable is False

    def test_not_usable_when_never_connected(self) -> None:
        snap = ReferencePriceSnapshot(
            symbol="BTC",
            price=60000.0,
            observed_at_s=999.0,
            connection_state=FeedConnectionState.NEVER_CONNECTED,
            is_stale=False,
            stale_threshold_s=15.0,
            feed_source="binance",
        )
        assert snap.is_usable is False

    def test_to_dict_is_json_serializable(self) -> None:
        snap = ReferencePriceSnapshot(
            symbol="BTC",
            price=60000.0,
            observed_at_s=1000.0,
            connection_state=FeedConnectionState.CONNECTED,
            is_stale=False,
            stale_threshold_s=15.0,
            feed_source="binance",
        )
        d = snap.to_dict()
        json.dumps(d)
        assert d["symbol"] == "BTC"
        assert d["price"] == 60000.0
        assert d["is_usable"] is True
        assert d["connection_state"] == "connected"


# ---------------------------------------------------------------------------
# BinanceFeed initial state
# ---------------------------------------------------------------------------


class TestBinanceFeedInitialState:
    def test_initial_connection_state_is_never_connected(self) -> None:
        feed = _feed()
        snap = feed.get_snapshot("BTC")
        assert snap.connection_state == FeedConnectionState.NEVER_CONNECTED

    def test_initial_price_is_none(self) -> None:
        feed = _feed()
        snap = feed.get_snapshot("BTC")
        assert snap.price is None

    def test_initial_snapshot_is_not_usable(self) -> None:
        feed = _feed()
        snap = feed.get_snapshot("BTC")
        assert snap.is_usable is False

    def test_initial_snapshot_is_stale(self) -> None:
        feed = _feed()
        snap = feed.get_snapshot("BTC")
        assert snap.is_stale is True

    def test_initial_feed_source_is_none(self) -> None:
        feed = _feed()
        snap = feed.get_snapshot("BTC")
        assert snap.feed_source == "none"


# ---------------------------------------------------------------------------
# BinanceFeed._inject_price
# ---------------------------------------------------------------------------


class TestBinanceFeedInjectPrice:
    def test_inject_btc_makes_snapshot_usable(self) -> None:
        feed = BinanceFeed(stale_threshold_s=15.0, _time_fn=lambda: 1000.0)
        feed._inject_price("BTC", 60000.0, observed_at_s=999.0)
        snap = feed.get_snapshot("BTC")
        assert snap.price == 60000.0
        assert snap.is_stale is False
        assert snap.is_usable is True
        assert snap.connection_state == FeedConnectionState.CONNECTED

    def test_inject_eth(self) -> None:
        feed = BinanceFeed(stale_threshold_s=15.0, _time_fn=lambda: 1000.0)
        feed._inject_price("ETH", 3000.0, observed_at_s=998.0)
        snap = feed.get_snapshot("ETH")
        assert snap.price == 3000.0
        assert snap.feed_source == "binance"

    def test_inject_sol(self) -> None:
        feed = BinanceFeed(stale_threshold_s=15.0, _time_fn=lambda: 1000.0)
        feed._inject_price("SOL", 150.0, observed_at_s=997.0)
        snap = feed.get_snapshot("SOL")
        assert snap.price == 150.0

    def test_inject_sets_connection_state_to_connected(self) -> None:
        feed = _feed()
        assert feed.get_snapshot("BTC").connection_state == FeedConnectionState.NEVER_CONNECTED
        feed._inject_price("BTC", 60000.0)
        assert feed.get_snapshot("BTC").connection_state == FeedConnectionState.CONNECTED

    def test_inject_uses_current_time_when_observed_at_not_given(self) -> None:
        feed = BinanceFeed(stale_threshold_s=15.0, _time_fn=lambda: 1000.0)
        feed._inject_price("BTC", 60000.0)
        snap = feed.get_snapshot("BTC")
        assert snap.observed_at_s == 1000.0
        assert snap.is_stale is False

    def test_inject_case_insensitive_symbol(self) -> None:
        feed = BinanceFeed(stale_threshold_s=15.0, _time_fn=lambda: 1000.0)
        feed._inject_price("btc", 60000.0)
        snap = feed.get_snapshot("BTC")
        assert snap.price == 60000.0

    def test_inject_unsupported_symbol_raises(self) -> None:
        feed = _feed()
        with pytest.raises(ValueError, match="Unsupported symbol"):
            feed._inject_price("DOGE", 1.0)


# ---------------------------------------------------------------------------
# BinanceFeed staleness detection
# ---------------------------------------------------------------------------


class TestBinanceFeedStaleness:
    def test_price_becomes_stale_when_age_exceeds_threshold(self) -> None:
        current_time: list[float] = [1000.0]
        feed = BinanceFeed(
            stale_threshold_s=15.0,
            _time_fn=lambda: current_time[0],
        )
        feed._inject_price("BTC", 60000.0, observed_at_s=1000.0)
        assert feed.get_snapshot("BTC").is_stale is False

        current_time[0] = 1016.0  # 16 s later — exceeds 15 s threshold
        snap = feed.get_snapshot("BTC")
        assert snap.is_stale is True
        assert snap.is_usable is False

    def test_price_exactly_at_threshold_is_not_stale(self) -> None:
        # age = now − observed_at = 1015 − 1000 = 15.0; threshold = 15.0
        # Condition: age > threshold → 15.0 > 15.0 is False → not stale
        feed = BinanceFeed(stale_threshold_s=15.0, _time_fn=lambda: 1015.0)
        feed._inject_price("BTC", 60000.0, observed_at_s=1000.0)
        snap = feed.get_snapshot("BTC")
        assert snap.is_stale is False

    def test_price_one_tick_past_threshold_is_stale(self) -> None:
        feed = BinanceFeed(stale_threshold_s=15.0, _time_fn=lambda: 1015.001)
        feed._inject_price("BTC", 60000.0, observed_at_s=1000.0)
        snap = feed.get_snapshot("BTC")
        assert snap.is_stale is True

    def test_no_price_for_other_symbol_is_stale(self) -> None:
        feed = BinanceFeed(stale_threshold_s=15.0, _time_fn=lambda: 1000.0)
        feed._inject_price("BTC", 60000.0)
        snap = feed.get_snapshot("ETH")  # ETH has no price
        assert snap.price is None
        assert snap.is_stale is True
        assert snap.is_usable is False

    def test_custom_stale_threshold(self) -> None:
        feed = BinanceFeed(stale_threshold_s=5.0, _time_fn=lambda: 1006.0)
        feed._inject_price("SOL", 150.0, observed_at_s=1000.0)
        # age = 6 > 5 → stale
        assert feed.get_snapshot("SOL").is_stale is True


# ---------------------------------------------------------------------------
# BinanceFeed unsupported symbol
# ---------------------------------------------------------------------------


class TestBinanceFeedUnsupportedSymbol:
    def test_get_snapshot_unsupported_symbol_raises(self) -> None:
        feed = _feed()
        with pytest.raises(ValueError, match="Unsupported symbol"):
            feed.get_snapshot("DOGE")

    def test_get_snapshot_unknown_symbol_raises(self) -> None:
        feed = _feed()
        with pytest.raises(ValueError, match="Unsupported symbol"):
            feed.get_snapshot("XRP")


# ---------------------------------------------------------------------------
# BinanceFeed.disconnect
# ---------------------------------------------------------------------------


class TestBinanceFeedDisconnect:
    def test_disconnect_makes_snapshot_not_usable(self) -> None:
        feed = BinanceFeed(stale_threshold_s=15.0, _time_fn=lambda: 1000.0)
        feed._inject_price("BTC", 60000.0, observed_at_s=999.0)
        assert feed.get_snapshot("BTC").is_usable is True

        feed.disconnect()
        snap = feed.get_snapshot("BTC")
        assert snap.connection_state == FeedConnectionState.DISCONNECTED
        assert snap.is_usable is False

    def test_disconnect_does_not_clear_prices(self) -> None:
        feed = BinanceFeed(stale_threshold_s=15.0, _time_fn=lambda: 1000.0)
        feed._inject_price("ETH", 3000.0, observed_at_s=999.0)
        feed.disconnect()
        snap = feed.get_snapshot("ETH")
        # Price is still there but snapshot is not usable due to DISCONNECTED
        assert snap.price == 3000.0
        assert snap.is_usable is False


# ---------------------------------------------------------------------------
# FeedConnectionState enum
# ---------------------------------------------------------------------------


class TestFeedConnectionState:
    def test_enum_values(self) -> None:
        assert FeedConnectionState.CONNECTED.value == "connected"
        assert FeedConnectionState.DISCONNECTED.value == "disconnected"
        assert FeedConnectionState.NEVER_CONNECTED.value == "never_connected"

    def test_string_comparison(self) -> None:
        assert FeedConnectionState.CONNECTED == "connected"


# ---------------------------------------------------------------------------
# Provider selection helpers
# ---------------------------------------------------------------------------


class TestReferenceFeedProviderSelection:
    def test_build_reference_feed_defaults_to_binance(self) -> None:
        feed = build_reference_feed()
        assert isinstance(feed, BinanceFeed)
        assert feed.SOURCE_NAME == "binance"
        assert DEFAULT_STALE_THRESHOLD_S == 15.0

    def test_build_reference_feed_coinbase(self) -> None:
        feed = build_reference_feed("coinbase")
        assert isinstance(feed, CoinbaseFeed)
        assert feed.SOURCE_NAME == "coinbase"

    def test_build_reference_feed_auto(self) -> None:
        feed = build_reference_feed("auto")
        assert isinstance(feed, AutoReferenceFeed)

    def test_normalize_reference_feed_provider_rejects_unknown_provider(self) -> None:
        with pytest.raises(ValueError, match="Unsupported reference_feed_provider"):
            normalize_reference_feed_provider("kraken")


# ---------------------------------------------------------------------------
# Coinbase normalization helpers
# ---------------------------------------------------------------------------


class TestCoinbaseNormalization:
    def test_parse_coinbase_ticker_normalizes_product_id_to_symbol(self) -> None:
        parsed = parse_coinbase_ws_message(
            json.dumps(
                {
                    "type": "ticker",
                    "product_id": "ETH-USD",
                    "price": "3025.50",
                }
            )
        )
        assert parsed == ("ETH", 3025.50)

    def test_parse_coinbase_message_ignores_non_ticker_payloads(self) -> None:
        parsed = parse_coinbase_ws_message(
            json.dumps(
                {
                    "type": "subscriptions",
                    "channels": [{"name": "ticker"}],
                }
            )
        )
        assert parsed is None

    def test_normalize_coinbase_product_id_rejects_unsupported_symbol(self) -> None:
        with pytest.raises(ValueError, match="Unsupported Coinbase product_id"):
            normalize_coinbase_product_id("DOGE-USD")


# ---------------------------------------------------------------------------
# CoinbaseFeed offline behavior
# ---------------------------------------------------------------------------


class TestCoinbaseFeedInjectPrice:
    def test_inject_price_uses_coinbase_feed_source(self) -> None:
        feed = _coinbase_feed()
        feed._inject_price("ETH", 3000.0, observed_at_s=999.0)
        snap = feed.get_snapshot("ETH")
        assert snap.feed_source == "coinbase"
        assert snap.is_usable is True


class TestCoinbaseFeedStateSemantics:
    def test_coinbase_price_becomes_stale_when_age_exceeds_threshold(self) -> None:
        current_time: list[float] = [1000.0]
        feed = CoinbaseFeed(
            stale_threshold_s=15.0,
            _time_fn=lambda: current_time[0],
        )
        feed._inject_price("BTC", 60000.0, observed_at_s=1000.0)
        assert feed.get_snapshot("BTC").is_stale is False

        current_time[0] = 1016.0
        snap = feed.get_snapshot("BTC")
        assert snap.is_stale is True
        assert snap.feed_source == "coinbase"
        assert snap.is_usable is False

    def test_coinbase_disconnect_makes_snapshot_not_usable(self) -> None:
        feed = _coinbase_feed()
        feed._inject_price("SOL", 150.0, observed_at_s=999.0)
        feed.disconnect()
        snap = feed.get_snapshot("SOL")
        assert snap.connection_state == FeedConnectionState.DISCONNECTED
        assert snap.price == 150.0
        assert snap.feed_source == "coinbase"
        assert snap.is_usable is False


# ---------------------------------------------------------------------------
# AutoReferenceFeed fallback behavior
# ---------------------------------------------------------------------------


class TestAutoReferenceFeed:
    def test_auto_prefers_binance_when_both_feeds_are_usable(self) -> None:
        primary = _feed(now=1000.0)
        fallback = _coinbase_feed(now=1000.0)
        primary._inject_price("BTC", 60000.0, observed_at_s=999.0)
        fallback._inject_price("BTC", 60010.0, observed_at_s=999.5)
        feed = AutoReferenceFeed(primary_feed=primary, fallback_feed=fallback)

        snap = feed.get_snapshot("BTC")

        assert snap.feed_source == "binance"
        assert snap.price == 60000.0
        assert snap.is_usable is True

    def test_auto_falls_back_to_coinbase_when_binance_is_disconnected(self) -> None:
        primary = _feed(now=1000.0)
        fallback = _coinbase_feed(now=1000.0)
        primary._inject_price("BTC", 60000.0, observed_at_s=999.0)
        primary.disconnect()
        fallback._inject_price("BTC", 60010.0, observed_at_s=999.5)
        feed = AutoReferenceFeed(primary_feed=primary, fallback_feed=fallback)

        snap = feed.get_snapshot("BTC")

        assert snap.feed_source == "coinbase"
        assert snap.price == 60010.0
        assert snap.connection_state == FeedConnectionState.CONNECTED
        assert snap.is_usable is True
