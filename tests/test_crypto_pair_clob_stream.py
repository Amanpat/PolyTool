"""Offline unit tests for ClobStreamClient.

All tests use _event_source and _time_fn injection — no network connections made.
"""

from __future__ import annotations

import json
import threading
import time
from typing import Iterable

import pytest

from packages.polymarket.crypto_pairs.clob_stream import ClobStreamClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _book_event(asset_id: str, bids: list, asks: list) -> dict:
    """Construct a book snapshot event dict."""
    return {
        "event_type": "book",
        "asset_id": asset_id,
        "bids": [{"price": str(b[0]), "size": str(b[1])} for b in bids],
        "asks": [{"price": str(a[0]), "size": str(a[1])} for a in asks],
    }


def _delta_event(asset_id: str, changes: list) -> dict:
    """Construct a price_change delta event dict.

    changes: list of (side, price, size) — side is 'BUY' or 'SELL'
    """
    return {
        "event_type": "price_change",
        "asset_id": asset_id,
        "changes": [
            {"side": c[0], "price": str(c[1]), "size": str(c[2])}
            for c in changes
        ],
    }


def _make_client(events: list[dict], time_fn=None) -> ClobStreamClient:
    """Create a ClobStreamClient with injected event source and optional clock."""
    client = ClobStreamClient(
        _event_source=iter(events),
        _time_fn=time_fn,
    )
    return client


def _start_and_drain(client: ClobStreamClient) -> None:
    """Start the client and wait for the event-source thread to finish."""
    client.start()
    # Give the daemon thread time to process all events
    for _ in range(50):
        time.sleep(0.02)
        if not client._ws_thread or not client._ws_thread.is_alive():
            break


# ---------------------------------------------------------------------------
# Test 1: Snapshot bootstrap
# ---------------------------------------------------------------------------

class TestSnapshotBootstrap:
    def test_snapshot_sets_best_bid_ask(self):
        """After a book snapshot, get_best_bid_ask returns the correct (bid, ask)."""
        events = [
            _book_event("T1", bids=[(0.48, 50)], asks=[(0.52, 100)]),
        ]
        client = _make_client(events)
        client.subscribe("T1")
        _start_and_drain(client)

        result = client.get_best_bid_ask("T1")
        assert result is not None, "Expected (bid, ask) tuple, got None"
        bid, ask = result
        assert abs(bid - 0.48) < 1e-9, f"Expected bid=0.48, got {bid}"
        assert abs(ask - 0.52) < 1e-9, f"Expected ask=0.52, got {ask}"


# ---------------------------------------------------------------------------
# Test 2: Delta application
# ---------------------------------------------------------------------------

class TestDeltaApplication:
    def test_delta_removes_and_adds_level(self):
        """Delta removes ask at 0.52 (size=0) and adds ask at 0.51; best_ask becomes 0.51."""
        events = [
            _book_event("T1", bids=[(0.48, 50)], asks=[(0.52, 100)]),
            _delta_event("T1", [
                ("SELL", 0.52, 0),   # remove 0.52 level
                ("SELL", 0.51, 75),  # add 0.51 level
            ]),
        ]
        client = _make_client(events)
        client.subscribe("T1")
        _start_and_drain(client)

        result = client.get_best_bid_ask("T1")
        assert result is not None
        bid, ask = result
        assert abs(bid - 0.48) < 1e-9, f"Expected bid=0.48, got {bid}"
        assert abs(ask - 0.51) < 1e-9, f"Expected best_ask=0.51, got {ask}"


# ---------------------------------------------------------------------------
# Test 3: Staleness guard
# ---------------------------------------------------------------------------

class TestStalenessGuard:
    def test_stale_book_returns_none(self):
        """If book age > stale_threshold_s, get_best_bid_ask returns None."""
        # Start at t=0, advance to t=6 (past 5s default threshold)
        tick = [0.0]

        def mock_time():
            return tick[0]

        events = [
            _book_event("T1", bids=[(0.48, 50)], asks=[(0.52, 100)]),
        ]
        client = ClobStreamClient(
            stale_threshold_s=5.0,
            _event_source=iter(events),
            _time_fn=mock_time,
        )
        client.subscribe("T1")
        _start_and_drain(client)

        # Verify it's fresh at t=0
        assert client.get_best_bid_ask("T1") is not None, "Should be fresh at t=0"

        # Advance clock to t=6 (stale)
        tick[0] = 6.0
        result = client.get_best_bid_ask("T1")
        assert result is None, f"Expected None (stale), got {result}"

    def test_fresh_book_within_threshold_returns_value(self):
        """Book within stale threshold returns a valid value."""
        tick = [0.0]

        def mock_time():
            return tick[0]

        events = [
            _book_event("T1", bids=[(0.48, 50)], asks=[(0.52, 100)]),
        ]
        client = ClobStreamClient(
            stale_threshold_s=5.0,
            _event_source=iter(events),
            _time_fn=mock_time,
        )
        client.subscribe("T1")
        _start_and_drain(client)

        # Advance only to t=4 (still fresh)
        tick[0] = 4.0
        result = client.get_best_bid_ask("T1")
        assert result is not None, "Expected fresh result at t=4"


# ---------------------------------------------------------------------------
# Test 4: Unsubscribe removes book state
# ---------------------------------------------------------------------------

class TestUnsubscribe:
    def test_unsubscribe_clears_book_and_ready_state(self):
        """After unsubscribing, is_ready() returns False and get_best_bid_ask returns None."""
        events = [
            _book_event("T1", bids=[(0.48, 50)], asks=[(0.52, 100)]),
        ]
        client = _make_client(events)
        client.subscribe("T1")
        _start_and_drain(client)

        # Verify it was ready
        assert client.is_ready("T1"), "Expected is_ready=True before unsubscribe"

        # Unsubscribe
        client.unsubscribe("T1")
        assert not client.is_ready("T1"), "Expected is_ready=False after unsubscribe"
        assert client.get_best_bid_ask("T1") is None, "Expected None after unsubscribe"


# ---------------------------------------------------------------------------
# Test 5: Sort order correctness
# ---------------------------------------------------------------------------

class TestSortOrder:
    def test_best_ask_is_minimum_price(self):
        """With asks in random price order, best_ask is the minimum (cheapest) price."""
        events = [
            _book_event(
                "T1",
                bids=[(0.40, 50)],
                asks=[(0.55, 30), (0.51, 20), (0.53, 40)],
            ),
        ]
        client = _make_client(events)
        client.subscribe("T1")
        _start_and_drain(client)

        result = client.get_best_bid_ask("T1")
        assert result is not None
        bid, ask = result
        assert abs(ask - 0.51) < 1e-9, f"Expected best_ask=0.51 (min), got {ask}"

    def test_best_bid_is_maximum_price(self):
        """With bids in random price order, best_bid is the maximum price."""
        events = [
            _book_event(
                "T1",
                bids=[(0.42, 10), (0.48, 20), (0.45, 15)],
                asks=[(0.52, 100)],
            ),
        ]
        client = _make_client(events)
        client.subscribe("T1")
        _start_and_drain(client)

        result = client.get_best_bid_ask("T1")
        assert result is not None
        bid, ask = result
        assert abs(bid - 0.48) < 1e-9, f"Expected best_bid=0.48 (max), got {bid}"


# ---------------------------------------------------------------------------
# Test 6: Multi-token on one connection
# ---------------------------------------------------------------------------

class TestMultiToken:
    def test_two_tokens_independent_books(self):
        """Two tokens receive separate snapshots and return per-token values."""
        events = [
            _book_event("T1", bids=[(0.48, 50)], asks=[(0.52, 100)]),
            _book_event("T2", bids=[(0.35, 80)], asks=[(0.65, 60)]),
        ]
        client = _make_client(events)
        client.subscribe("T1")
        client.subscribe("T2")
        _start_and_drain(client)

        t1 = client.get_best_bid_ask("T1")
        t2 = client.get_best_bid_ask("T2")

        assert t1 is not None
        assert t2 is not None

        bid1, ask1 = t1
        bid2, ask2 = t2

        assert abs(bid1 - 0.48) < 1e-9, f"T1 bid expected 0.48, got {bid1}"
        assert abs(ask1 - 0.52) < 1e-9, f"T1 ask expected 0.52, got {ask1}"
        assert abs(bid2 - 0.35) < 1e-9, f"T2 bid expected 0.35, got {bid2}"
        assert abs(ask2 - 0.65) < 1e-9, f"T2 ask expected 0.65, got {ask2}"

    def test_unsubscribed_token_returns_none(self):
        """A token that was never subscribed returns None from get_best_bid_ask."""
        events = [
            _book_event("T1", bids=[(0.48, 50)], asks=[(0.52, 100)]),
        ]
        client = _make_client(events)
        client.subscribe("T1")
        _start_and_drain(client)

        # T2 was never subscribed
        assert client.get_best_bid_ask("T2") is None


# ---------------------------------------------------------------------------
# Additional: is_ready and get_book_age_ms
# ---------------------------------------------------------------------------

class TestIsReadyAndAge:
    def test_is_ready_false_when_no_snapshot(self):
        """is_ready returns False when subscribed but no snapshot received."""
        client = ClobStreamClient(_event_source=iter([]))
        client.subscribe("T1")
        # Don't start — just check state
        assert not client.is_ready("T1")

    def test_get_book_age_ms_returns_large_value_when_no_snapshot(self):
        """get_book_age_ms returns 999999 when no snapshot received."""
        client = ClobStreamClient(_event_source=iter([]))
        assert client.get_book_age_ms("T1") == 999999

    def test_get_book_age_ms_after_snapshot(self):
        """get_book_age_ms returns 0 immediately after snapshot (same clock tick)."""
        tick = [100.0]

        def mock_time():
            return tick[0]

        events = [
            _book_event("T1", bids=[(0.48, 50)], asks=[(0.52, 100)]),
        ]
        client = ClobStreamClient(
            _event_source=iter(events),
            _time_fn=mock_time,
        )
        client.subscribe("T1")
        _start_and_drain(client)

        # Still at the same tick — age should be 0ms
        age = client.get_book_age_ms("T1")
        assert age == 0, f"Expected age=0ms at same tick, got {age}"

        # Advance by 1 second
        tick[0] = 101.0
        age = client.get_book_age_ms("T1")
        assert age == 1000, f"Expected age=1000ms after 1s, got {age}"
