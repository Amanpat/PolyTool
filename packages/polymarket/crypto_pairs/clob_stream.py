"""Persistent WebSocket CLOB feed for the crypto-pair bot.

Maintains a continuously-updated in-memory order book per subscribed token,
eliminating REST polling overhead (2 HTTP calls per market per cycle).

Follows the TapeRecorder WebSocket pattern (raw websocket.WebSocket(), not
WebSocketApp) and the BinanceFeed daemon-thread pattern from reference_feed.py.

Key design choices:
- All mutable state protected by a single threading.Lock.
- _event_source injection enables fully offline unit testing (same pattern as
  ShadowRunner).
- _time_fn injection enables staleness tests without real-time waits.
- WebSocket import is deferred so paper/test paths never load it unless needed.
"""

from __future__ import annotations

import json
import logging
import threading
import time
from typing import Any, Callable, Iterable, Iterator, Optional

_log = logging.getLogger(__name__)

WS_MARKET_URL = "wss://ws-subscriptions-clob.polymarket.com/ws/market"
DEFAULT_STALE_THRESHOLD_S = 5.0
DEFAULT_RECV_TIMEOUT_S = 5.0
DEFAULT_RECONNECT_SLEEP_S = 1.0

_BIDS_KEY = "bids"
_ASKS_KEY = "asks"
_SIDE_BUY = "BUY"    # maps to bids
_SIDE_SELL = "SELL"  # maps to asks

_SENTINEL_AGE_MS = 999999  # returned when no snapshot has been received


class ClobStreamClient:
    """Persistent WebSocket CLOB market feed.

    Maintains an in-memory sorted order book per subscribed token.
    Thread-safe: all state is protected by self._lock.

    Usage (production):
        stream = ClobStreamClient()
        stream.subscribe("token_id_1")
        stream.subscribe("token_id_2")
        stream.start()  # starts daemon thread; connects + streams WS
        ...
        bid, ask = stream.get_best_bid_ask("token_id_1")
        stream.stop()

    Usage (tests — no network):
        events = [{"event_type": "book", "asset_id": "T1", "bids": [...], "asks": [...]}]
        stream = ClobStreamClient(_event_source=iter(events), _time_fn=mock_time)
        stream.subscribe("T1")
        stream.start()
    """

    def __init__(
        self,
        *,
        stale_threshold_s: float = DEFAULT_STALE_THRESHOLD_S,
        ws_url: str = WS_MARKET_URL,
        recv_timeout_s: float = DEFAULT_RECV_TIMEOUT_S,
        reconnect_sleep_s: float = DEFAULT_RECONNECT_SLEEP_S,
        _time_fn: Optional[Callable[[], float]] = None,
        _event_source: Optional[Iterator[dict]] = None,
    ) -> None:
        self._stale_threshold_s = stale_threshold_s
        self._ws_url = ws_url
        self._recv_timeout_s = recv_timeout_s
        self._reconnect_sleep_s = reconnect_sleep_s
        self._time_fn: Callable[[], float] = _time_fn or time.time
        self._event_source = _event_source

        self._lock = threading.Lock()
        # Per-token books: token_id -> side_key -> {price_float: size_float}
        self._books: dict[str, dict[str, dict[float, float]]] = {}
        # Per-token last-update timestamps
        self._timestamps: dict[str, float] = {}
        # Subscribed token IDs
        self._subscribed: set[str] = set()
        # Controls reconnect loop exit
        self._stopped: bool = False
        # Background thread handle
        self._ws_thread: Optional[threading.Thread] = None

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def subscribe(self, token_id: str) -> None:
        """Add a token to the subscribed set.

        The subscription message will be sent on the next (re)connect.
        If the WS thread is already running, the new token will be included
        on the next reconnect.
        """
        with self._lock:
            self._subscribed.add(token_id)

    def unsubscribe(self, token_id: str) -> None:
        """Remove a token from the subscribed set and clear its book state."""
        with self._lock:
            self._subscribed.discard(token_id)
            self._books.pop(token_id, None)
            self._timestamps.pop(token_id, None)

    def get_best_bid_ask(self, token_id: str) -> Optional[tuple[float, float]]:
        """Return (best_bid, best_ask) from the in-memory book.

        Returns None when:
        - token_id is not subscribed
        - no snapshot has been received yet
        - book age exceeds stale_threshold_s
        - either side of the book is empty
        """
        with self._lock:
            if token_id not in self._subscribed:
                return None
            book = self._books.get(token_id)
            if book is None:
                return None
            ts = self._timestamps.get(token_id)
            if ts is None:
                return None
            age = self._time_fn() - ts
            if age > self._stale_threshold_s:
                return None
            bids = book.get(_BIDS_KEY, {})
            asks = book.get(_ASKS_KEY, {})
            if not bids or not asks:
                return None
            best_bid = max(bids.keys())
            best_ask = min(asks.keys())
            return (best_bid, best_ask)

    def get_book_age_ms(self, token_id: str) -> int:
        """Return milliseconds since the last book update for token_id.

        Returns 999999 if no snapshot has been received.
        """
        with self._lock:
            ts = self._timestamps.get(token_id)
            if ts is None:
                return _SENTINEL_AGE_MS
            age_s = self._time_fn() - ts
            return int(age_s * 1000)

    def is_ready(self, token_id: str) -> bool:
        """Return True when subscribed, has a snapshot, and age <= stale_threshold_s."""
        with self._lock:
            if token_id not in self._subscribed:
                return False
            book = self._books.get(token_id)
            if book is None:
                return False
            ts = self._timestamps.get(token_id)
            if ts is None:
                return False
            age = self._time_fn() - ts
            if age > self._stale_threshold_s:
                return False
            bids = book.get(_BIDS_KEY, {})
            asks = book.get(_ASKS_KEY, {})
            return bool(bids) and bool(asks)

    def start(self) -> None:
        """Start the background WS thread (idempotent).

        If _event_source is set: runs a thread that iterates the source and
        applies events directly (no network connection).
        If _event_source is None: runs the live WS reconnect loop.
        """
        with self._lock:
            if self._ws_thread is not None and self._ws_thread.is_alive():
                return  # already running
            self._stopped = False

        if self._event_source is not None:
            target = self._event_source_loop
        else:
            target = self._ws_loop

        self._ws_thread = threading.Thread(target=target, daemon=True)
        self._ws_thread.start()

    def stop(self) -> None:
        """Signal the WS loop to exit on next iteration."""
        with self._lock:
            self._stopped = True

    # ------------------------------------------------------------------
    # Internal: event-source loop (test mode)
    # ------------------------------------------------------------------

    def _event_source_loop(self) -> None:
        """Iterate _event_source and apply each event. Used for offline testing."""
        try:
            for event in self._event_source:  # type: ignore[union-attr]
                with self._lock:
                    stopped = self._stopped
                if stopped:
                    break
                if isinstance(event, dict):
                    self._apply_message(json.dumps(event))
                else:
                    self._apply_message(str(event))
        except Exception as exc:
            _log.debug("ClobStreamClient event_source_loop ended: %s", exc)

    # ------------------------------------------------------------------
    # Internal: live WS loop
    # ------------------------------------------------------------------

    def _ws_loop(self) -> None:
        """Reconnect-loop for the live WebSocket connection."""
        while True:
            with self._lock:
                if self._stopped:
                    break
                subscribed_ids = list(self._subscribed)

            if not subscribed_ids:
                time.sleep(0.1)
                continue

            try:
                import websocket  # soft dependency — only loaded in live mode

                ws_conn = websocket.WebSocket()
                ws_conn.connect(self._ws_url)
                ws_conn.settimeout(self._recv_timeout_s)

                subscribe_msg = json.dumps({
                    "assets_ids": subscribed_ids,
                    "type": "market",
                    "custom_feature_enabled": True,
                    "initial_dump": True,
                })
                ws_conn.send(subscribe_msg)
                _log.info(
                    "ClobStreamClient subscribed to %d tokens", len(subscribed_ids)
                )

                while True:
                    with self._lock:
                        if self._stopped:
                            break
                    try:
                        raw = ws_conn.recv()
                        if raw:
                            self._apply_message(raw)
                    except websocket.WebSocketTimeoutException:
                        continue  # normal timeout; check stopped flag
                    except websocket.WebSocketConnectionClosedException:
                        _log.warning("ClobStreamClient: WS connection closed; reconnecting")
                        break

            except Exception as exc:
                _log.warning("ClobStreamClient WS error: %s; reconnecting", exc)

            with self._lock:
                if self._stopped:
                    break

            time.sleep(self._reconnect_sleep_s)

    # ------------------------------------------------------------------
    # Internal: message parsing
    # ------------------------------------------------------------------

    def _apply_message(self, raw_msg: str) -> None:
        """Parse a raw WS message string and apply to internal book state."""
        try:
            data = json.loads(raw_msg)
        except (json.JSONDecodeError, ValueError) as exc:
            _log.debug("ClobStreamClient: failed to parse message: %s", exc)
            return

        # Handle both single-event and batched price_changes[] format
        events = data.get("price_changes") or [data]
        for event in events:
            event_type = event.get("event_type") or event.get("type")
            asset_id = event.get("asset_id") or event.get("market")
            if not asset_id:
                continue
            if event_type == "book":
                self._apply_snapshot(asset_id, event)
            elif event_type == "price_change":
                self._apply_delta(asset_id, event)

    def _apply_snapshot(self, token_id: str, event: dict) -> None:
        """Replace the entire book for token_id with parsed snapshot levels."""
        bids: dict[float, float] = {}
        asks: dict[float, float] = {}

        for level in event.get("bids") or []:
            price = _parse_price(level)
            size = _parse_size(level)
            if price is not None and size is not None and size > 0:
                bids[price] = size

        for level in event.get("asks") or []:
            price = _parse_price(level)
            size = _parse_size(level)
            if price is not None and size is not None and size > 0:
                asks[price] = size

        with self._lock:
            self._books[token_id] = {_BIDS_KEY: bids, _ASKS_KEY: asks}
            self._timestamps[token_id] = self._time_fn()

    def _apply_delta(self, token_id: str, event: dict) -> None:
        """Apply a price_change delta to the existing book for token_id."""
        with self._lock:
            if token_id not in self._books:
                # No snapshot yet; ignore delta (will be corrected by next snapshot)
                return
            book = self._books[token_id]

            for change in event.get("changes") or []:
                side_raw = change.get("side", "")
                price_str = change.get("price")
                size_str = change.get("size")

                try:
                    price = float(price_str)
                    size = float(size_str)
                except (TypeError, ValueError):
                    continue

                if side_raw == _SIDE_BUY:
                    side_key = _BIDS_KEY
                elif side_raw == _SIDE_SELL:
                    side_key = _ASKS_KEY
                else:
                    continue

                side_book = book.setdefault(side_key, {})
                if size == 0.0:
                    side_book.pop(price, None)
                else:
                    side_book[price] = size

            self._timestamps[token_id] = self._time_fn()


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _parse_price(level: object) -> Optional[float]:
    if isinstance(level, dict):
        val = level.get("price") or level.get("p")
    elif isinstance(level, (list, tuple)) and len(level) >= 1:
        val = level[0]
    else:
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def _parse_size(level: object) -> Optional[float]:
    if isinstance(level, dict):
        val = level.get("size") or level.get("s")
    elif isinstance(level, (list, tuple)) and len(level) >= 2:
        val = level[1]
    else:
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None
