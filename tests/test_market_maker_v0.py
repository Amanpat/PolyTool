"""Offline unit tests for MarketMakerV0 strategy."""

from __future__ import annotations

from collections import deque
from decimal import Decimal

import pytest

from packages.polymarket.simtrader.strategies.market_maker_v0 import (
    MarketMakerV0,
    _tick_ceil,
    _tick_floor,
)


def _mm(**kwargs) -> MarketMakerV0:
    kwargs.setdefault("tick_size", "0.01")
    kwargs.setdefault("order_size", "10")
    return MarketMakerV0(**kwargs)


def _quotes(mm: MarketMakerV0, best_bid, best_ask, asset_id="tok1", **kwargs):
    return mm.compute_quotes(best_bid=best_bid, best_ask=best_ask, asset_id=asset_id, **kwargs)


def _book_event(
    *,
    asset_id: str = "tok1",
    seq: int = 1,
    ts_recv: float = 1000.0,
    bids=None,
    asks=None,
    market_metadata=None,
) -> dict:
    event = {
        "parser_version": 1,
        "seq": seq,
        "ts_recv": ts_recv,
        "event_type": "book",
        "asset_id": asset_id,
        "bids": bids if bids is not None else [{"price": "0.45", "size": "100"}],
        "asks": asks if asks is not None else [{"price": "0.55", "size": "100"}],
    }
    if market_metadata is not None:
        event["market_metadata"] = market_metadata
    return event


def _bid_ask(intents):
    bid = next(i for i in intents if i.side == "BUY")
    ask = next(i for i in intents if i.side == "SELL")
    return bid, ask


def _quote_center(intents) -> Decimal:
    bid, ask = _bid_ask(intents)
    return (bid.limit_price + ask.limit_price) / Decimal("2")


class TestTickHelpers:
    def test_tick_floor_aligned(self) -> None:
        assert _tick_floor(Decimal("0.50"), Decimal("0.01")) == Decimal("0.50")

    def test_tick_floor_rounds_down(self) -> None:
        assert _tick_floor(Decimal("0.509"), Decimal("0.01")) == Decimal("0.50")

    def test_tick_ceil_aligned(self) -> None:
        assert _tick_ceil(Decimal("0.55"), Decimal("0.01")) == Decimal("0.55")

    def test_tick_ceil_rounds_up(self) -> None:
        assert _tick_ceil(Decimal("0.501"), Decimal("0.01")) == Decimal("0.51")


class TestConstructor:
    def test_default_construction(self) -> None:
        mm = MarketMakerV0()
        assert mm.tick_size == Decimal("0.01")
        assert mm.order_size == Decimal("10")
        assert mm.quote_ticks_from_bbo == 0
        assert mm.inventory_skew_factor == Decimal("0.5")
        assert mm.max_skew_ticks == 5
        assert mm.mm_config.gamma == pytest.approx(0.10)
        assert mm.mm_config.kappa == pytest.approx(1.50)
        assert mm.hours_to_resolution == pytest.approx(24.0)

    def test_invalid_tick_size_zero(self) -> None:
        with pytest.raises(ValueError, match="tick_size"):
            MarketMakerV0(tick_size="0")

    def test_invalid_gamma_zero(self) -> None:
        with pytest.raises(ValueError, match="gamma"):
            MarketMakerV0(gamma=0.0)

    def test_invalid_hours_to_resolution_zero(self) -> None:
        with pytest.raises(ValueError, match="hours_to_resolution"):
            MarketMakerV0(hours_to_resolution=0.0)


class TestMicroprice:
    def test_microprice_returns_size_weighted_value(self) -> None:
        mm = _mm()
        book = {
            "bids": [
                {"price": "0.49", "size": "100"},
                {"price": "0.48", "size": "50"},
                {"price": "0.47", "size": "25"},
            ],
            "asks": [
                {"price": "0.51", "size": "80"},
                {"price": "0.52", "size": "40"},
                {"price": "0.53", "size": "20"},
            ],
        }
        expected = (
            0.49 * 100
            + 0.48 * 50
            + 0.47 * 25
            + 0.51 * 80
            + 0.52 * 40
            + 0.53 * 20
        ) / (100 + 50 + 25 + 80 + 40 + 20)
        assert mm._microprice(book) == pytest.approx(expected)

    def test_microprice_returns_none_for_one_sided_book(self) -> None:
        mm = _mm()
        assert mm._microprice({"bids": [{"price": "0.49", "size": "10"}], "asks": []}) is None


class TestSigmaSq:
    def test_sigma_sq_uses_default_with_less_than_three_points(self) -> None:
        mm = _mm()
        mm._mid_history = deque([(1000.0, 0.50), (1001.0, 0.51)])
        assert mm._sigma_sq(1001.0) == pytest.approx(0.0002)

    def test_sigma_sq_returns_variance_with_many_points(self) -> None:
        mm = _mm()
        mids = [0.50, 0.52, 0.51, 0.53, 0.54, 0.52, 0.55, 0.57, 0.56, 0.58, 0.60]
        mm._mid_history = deque((1000.0 + idx, mid) for idx, mid in enumerate(mids))

        changes = [curr - prev for prev, curr in zip(mids, mids[1:])]
        mean_change = sum(changes) / len(changes)
        expected = sum((change - mean_change) ** 2 for change in changes) / len(changes)

        assert mm._sigma_sq(1010.0) == pytest.approx(expected)


class TestASQuoteModel:
    def test_compute_quotes_zero_inventory_is_symmetric_around_mid(self) -> None:
        mm = _mm(gamma=100.0, kappa=1000.0, session_hours=1.0, min_spread=0.01, max_spread=0.20)
        mm._inventory = Decimal("0")
        bid, ask = mm._compute_quotes(mid=0.50, t_elapsed_hours=0.0, sigma_sq=0.0005)
        assert ((bid + ask) / 2.0) == pytest.approx(0.50, abs=1e-3)

    def test_compute_quotes_positive_inventory_shifts_center_down(self) -> None:
        flat = _mm(gamma=100.0, kappa=1000.0, session_hours=1.0, min_spread=0.01, max_spread=0.20)
        long = _mm(gamma=100.0, kappa=1000.0, session_hours=1.0, min_spread=0.01, max_spread=0.20)
        long._inventory = Decimal("20")

        flat_bid, flat_ask = flat._compute_quotes(mid=0.50, t_elapsed_hours=0.0, sigma_sq=0.0005)
        long_bid, long_ask = long._compute_quotes(mid=0.50, t_elapsed_hours=0.0, sigma_sq=0.0005)

        assert ((long_bid + long_ask) / 2.0) < ((flat_bid + flat_ask) / 2.0)

    def test_resolution_guard_widens_spread_below_guard_band(self) -> None:
        mm = _mm(
            gamma=100.0,
            kappa=1000.0,
            session_hours=1.0,
            min_spread=0.01,
            max_spread=0.50,
            resolution_guard=0.10,
        )
        normal_bid, normal_ask = mm._compute_quotes(mid=0.50, t_elapsed_hours=0.0, sigma_sq=0.0002)
        guard_bid, guard_ask = mm._compute_quotes(mid=0.09, t_elapsed_hours=0.0, sigma_sq=0.0002)
        assert (guard_ask - guard_bid) > (normal_ask - normal_bid)


class TestComputeQuotes:
    def test_empty_book_returns_empty(self) -> None:
        mm = _mm()
        assert _quotes(mm, best_bid=None, best_ask=0.55) == []

    def test_crossed_book_returns_empty(self) -> None:
        mm = _mm()
        assert _quotes(mm, best_bid=0.55, best_ask=0.50) == []

    def test_order_size_below_min_returns_empty(self) -> None:
        mm = _mm(order_size="0.5", min_order_size="1")
        assert _quotes(mm, best_bid=0.45, best_ask=0.55) == []

    def test_returns_two_submit_intents_with_expected_shape(self) -> None:
        mm = _mm()
        intents = _quotes(mm, best_bid=0.45, best_ask=0.55, asset_id="mytoken")
        assert len(intents) == 2
        sides = {intent.side for intent in intents}
        assert sides == {"BUY", "SELL"}
        for intent in intents:
            assert intent.action == "submit"
            assert intent.asset_id == "mytoken"
            assert intent.size == Decimal("10")
            assert "market_maker_v0" in (intent.reason or "")

    def test_prices_are_tick_aligned(self) -> None:
        mm = _mm()
        intents = _quotes(mm, best_bid=0.45, best_ask=0.55)
        for intent in intents:
            assert intent.limit_price % Decimal("0.01") == Decimal("0")

    def test_quote_ticks_from_bbo_still_moves_quotes_outward(self) -> None:
        base = _mm(gamma=100.0, kappa=1000.0, session_hours=1.0, min_spread=0.01, max_spread=0.20)
        wider = _mm(
            gamma=100.0,
            kappa=1000.0,
            session_hours=1.0,
            min_spread=0.01,
            max_spread=0.20,
            quote_ticks_from_bbo=2,
        )
        base_bid, base_ask = _bid_ask(_quotes(base, best_bid=0.45, best_ask=0.55))
        wider_bid, wider_ask = _bid_ask(_quotes(wider, best_bid=0.45, best_ask=0.55))
        assert wider_bid.limit_price < base_bid.limit_price
        assert wider_ask.limit_price > base_ask.limit_price


class TestEventFlow:
    def test_on_event_uses_book_microprice_for_quote_center(self) -> None:
        mm = _mm(
            tick_size="0.001",
            gamma=100.0,
            kappa=1000.0,
            session_hours=1.0,
            min_spread=0.01,
            max_spread=0.20,
        )
        mm.on_start("tok1", Decimal("1000"))
        event = _book_event(
            bids=[
                {"price": "0.490", "size": "120"},
                {"price": "0.489", "size": "80"},
                {"price": "0.488", "size": "60"},
            ],
            asks=[
                {"price": "0.510", "size": "5"},
                {"price": "0.511", "size": "5"},
                {"price": "0.512", "size": "5"},
            ],
        )
        intents = mm.on_event(
            event=event,
            seq=1,
            ts_recv=event["ts_recv"],
            best_bid=0.49,
            best_ask=0.51,
            open_orders={},
        )
        assert _quote_center(intents) < Decimal("0.500")

    def test_on_event_pulls_hours_to_resolution_from_market_metadata(self) -> None:
        mm = _mm()
        mm.on_start("tok1", Decimal("1000"))
        event = _book_event(market_metadata={"hours_to_resolution": 6.0})
        mm.on_event(
            event=event,
            seq=1,
            ts_recv=event["ts_recv"],
            best_bid=0.45,
            best_ask=0.55,
            open_orders={},
        )
        assert mm.hours_to_resolution == pytest.approx(6.0)

    def test_on_event_skips_reprice_when_quotes_have_not_moved(self) -> None:
        mm = _mm(
            tick_size="0.001",
            gamma=100.0,
            kappa=1000.0,
            session_hours=1.0,
            min_spread=0.01,
            max_spread=0.20,
        )
        mm.on_start("tok1", Decimal("1000"))
        first = _book_event(seq=1, ts_recv=1000.0)
        second = _book_event(seq=2, ts_recv=1001.0)

        initial = mm.on_event(
            event=first,
            seq=1,
            ts_recv=first["ts_recv"],
            best_bid=0.45,
            best_ask=0.55,
            open_orders={},
        )
        assert len(initial) == 2

        skipped = mm.on_event(
            event=second,
            seq=2,
            ts_recv=second["ts_recv"],
            best_bid=0.45,
            best_ask=0.55,
            open_orders={
                "bid-1": {"side": "BUY"},
                "ask-1": {"side": "SELL"},
            },
        )
        assert skipped == []


class TestLifecycle:
    def test_on_start_initializes_inventory_and_asset(self) -> None:
        mm = _mm()
        mm._inventory = Decimal("5")
        mm.on_start("tok1", Decimal("1000"))
        assert mm._inventory == Decimal("0")
        assert mm._asset_id == "tok1"

    def test_on_fill_updates_inventory_buy(self) -> None:
        mm = _mm()
        mm.on_start("tok1", Decimal("1000"))
        mm.on_fill("o1", "tok1", "BUY", Decimal("0.45"), Decimal("10"), "full", 1, 1.0)
        assert mm._inventory == Decimal("10")

    def test_on_fill_updates_inventory_sell(self) -> None:
        mm = _mm()
        mm.on_start("tok1", Decimal("1000"))
        mm._inventory = Decimal("10")
        mm.on_fill("o2", "tok1", "SELL", Decimal("0.55"), Decimal("5"), "full", 2, 2.0)
        assert mm._inventory == Decimal("5")


class TestComputeOrderRequests:
    def test_returns_order_requests(self) -> None:
        mm = _mm()
        requests = mm.compute_order_requests(best_bid=0.45, best_ask=0.55, asset_id="tok1")
        assert len(requests) == 2
        assert {request.side for request in requests} == {"BUY", "SELL"}

    def test_post_only_is_true(self) -> None:
        mm = _mm()
        requests = mm.compute_order_requests(best_bid=0.45, best_ask=0.55, asset_id="tok1")
        assert all(request.post_only is True for request in requests)

    def test_empty_book_returns_empty(self) -> None:
        mm = _mm()
        assert mm.compute_order_requests(best_bid=None, best_ask=0.55, asset_id="tok1") == []
