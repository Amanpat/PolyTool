"""Binance-first reference price feed for Track 2 / Phase 1A crypto pair bot.

Tracks live spot prices for BTC, ETH, SOL via the Binance public WebSocket
aggTrade stream.  Provides explicit connection-state and stale-state
representation so the accumulation engine can freeze new intents when the feed
is unreliable.

Architecture:
- ``BinanceFeed`` holds mutable internal price state.  Callers retrieve an
  immutable ``ReferencePriceSnapshot`` via ``get_snapshot()``.
- The live WebSocket loop runs in a background daemon thread started by
  ``connect()``.  Tests bypass the WS entirely via ``_inject_price()``.
- Coinbase fallback is planned (Phase 1A follow-on) but not yet implemented.
  The ``feed_source`` field on ``ReferencePriceSnapshot`` reserves space for it.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Optional

_log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SUPPORTED_SYMBOLS: frozenset[str] = frozenset({"BTC", "ETH", "SOL"})

# Binance combined stream URL for BTC/ETH/SOL aggTrade feeds
_BINANCE_STREAM_SYMBOLS: dict[str, str] = {
    "BTC": "btcusdt",
    "ETH": "ethusdt",
    "SOL": "solusdt",
}

_BINANCE_COMBINED_STREAM_URL = (
    "wss://stream.binance.com:9443/stream?streams="
    "btcusdt@aggTrade/ethusdt@aggTrade/solusdt@aggTrade"
)

# Reverse map: stream symbol → canonical symbol
_STREAM_TO_SYMBOL: dict[str, str] = {v: k for k, v in _BINANCE_STREAM_SYMBOLS.items()}

DEFAULT_STALE_THRESHOLD_S: float = 15.0


# ---------------------------------------------------------------------------
# Enums and snapshot data model
# ---------------------------------------------------------------------------


class FeedConnectionState(str, Enum):
    """Lifecycle connection state for a reference feed."""

    NEVER_CONNECTED = "never_connected"
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"


@dataclass(frozen=True)
class ReferencePriceSnapshot:
    """Immutable point-in-time reference price snapshot for one symbol.

    Attributes:
        symbol: Canonical symbol ("BTC", "ETH", "SOL").
        price: Spot price in USD; ``None`` if no price has been received yet.
        observed_at_s: Unix timestamp when the price was observed; ``None`` if
            no price has been received.
        connection_state: Current connection lifecycle state.
        is_stale: ``True`` if the price age exceeds ``stale_threshold_s`` or
            if no price has been received.
        stale_threshold_s: Configured staleness threshold (seconds).
        feed_source: "binance" when price came from Binance; "none" otherwise.
            Reserved for future "coinbase" value.
    """

    symbol: str
    price: Optional[float]
    observed_at_s: Optional[float]
    connection_state: FeedConnectionState
    is_stale: bool
    stale_threshold_s: float
    feed_source: str

    @property
    def is_usable(self) -> bool:
        """``True`` when price is present, fresh, and connection is live."""
        return (
            self.price is not None
            and not self.is_stale
            and self.connection_state == FeedConnectionState.CONNECTED
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "price": self.price,
            "observed_at_s": self.observed_at_s,
            "connection_state": self.connection_state.value,
            "is_stale": self.is_stale,
            "is_usable": self.is_usable,
            "stale_threshold_s": self.stale_threshold_s,
            "feed_source": self.feed_source,
        }


# ---------------------------------------------------------------------------
# BinanceFeed
# ---------------------------------------------------------------------------


class BinanceFeed:
    """Binance reference price feed for BTC, ETH, and SOL.

    Thread-safe.  The WebSocket loop runs in a background daemon thread;
    ``get_snapshot()`` never blocks.

    Args:
        stale_threshold_s: Age (seconds) after which a price is considered
            stale.  Defaults to ``DEFAULT_STALE_THRESHOLD_S`` (15 s).
        _time_fn: Injectable clock.  Overridden in tests to control perceived
            price age without real delays.
    """

    def __init__(
        self,
        stale_threshold_s: float = DEFAULT_STALE_THRESHOLD_S,
        _time_fn: Optional[Callable[[], float]] = None,
    ) -> None:
        self._stale_threshold_s = stale_threshold_s
        self._time_fn: Callable[[], float] = _time_fn if _time_fn is not None else time.time

        self._lock = threading.Lock()
        self._prices: dict[str, float] = {}
        self._timestamps: dict[str, float] = {}
        self._connection_state = FeedConnectionState.NEVER_CONNECTED
        self._ws_thread: Optional[threading.Thread] = None

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def connect(self) -> None:
        """Start the WebSocket background thread (idempotent)."""
        if self._ws_thread is not None and self._ws_thread.is_alive():
            return
        self._ws_thread = threading.Thread(
            target=self._ws_loop,
            name="BinanceFeed-WS",
            daemon=True,
        )
        self._ws_thread.start()

    def disconnect(self) -> None:
        """Signal the feed to stop reconnecting.

        The background thread may still be running briefly after this returns.
        """
        with self._lock:
            self._connection_state = FeedConnectionState.DISCONNECTED

    def get_snapshot(self, symbol: str) -> ReferencePriceSnapshot:
        """Return an immutable point-in-time snapshot for *symbol*.

        Thread-safe.  Never blocks.  Always returns a value even when no
        price has been received yet (price=None, is_stale=True).

        Raises:
            ValueError: If *symbol* is not in ``SUPPORTED_SYMBOLS``.
        """
        symbol_upper = symbol.strip().upper()
        if symbol_upper not in SUPPORTED_SYMBOLS:
            raise ValueError(
                f"Unsupported symbol {symbol!r}. "
                f"Supported: {sorted(SUPPORTED_SYMBOLS)}"
            )

        now = self._time_fn()

        with self._lock:
            conn_state = self._connection_state
            price = self._prices.get(symbol_upper)
            observed_at = self._timestamps.get(symbol_upper)

        if price is None or observed_at is None:
            return ReferencePriceSnapshot(
                symbol=symbol_upper,
                price=None,
                observed_at_s=None,
                connection_state=conn_state,
                is_stale=True,
                stale_threshold_s=self._stale_threshold_s,
                feed_source="none",
            )

        age_s = now - observed_at
        is_stale = age_s > self._stale_threshold_s

        return ReferencePriceSnapshot(
            symbol=symbol_upper,
            price=price,
            observed_at_s=observed_at,
            connection_state=conn_state,
            is_stale=is_stale,
            stale_threshold_s=self._stale_threshold_s,
            feed_source="binance",
        )

    # ------------------------------------------------------------------
    # Test / offline interface
    # ------------------------------------------------------------------

    def _inject_price(
        self,
        symbol: str,
        price: float,
        *,
        observed_at_s: Optional[float] = None,
    ) -> None:
        """Inject a price directly without a WebSocket connection.

        Sets connection state to CONNECTED so ``is_usable`` returns True
        immediately.  Intended for tests and offline simulation only.

        Args:
            symbol: "BTC", "ETH", or "SOL" (case-insensitive).
            price: Spot price in USD.
            observed_at_s: Unix timestamp for the price.  Defaults to the
                current value of ``_time_fn()``.

        Raises:
            ValueError: If *symbol* is not supported.
        """
        symbol_upper = symbol.strip().upper()
        if symbol_upper not in SUPPORTED_SYMBOLS:
            raise ValueError(
                f"Unsupported symbol {symbol!r}. "
                f"Supported: {sorted(SUPPORTED_SYMBOLS)}"
            )
        ts = observed_at_s if observed_at_s is not None else self._time_fn()
        with self._lock:
            self._prices[symbol_upper] = price
            self._timestamps[symbol_upper] = ts
            self._connection_state = FeedConnectionState.CONNECTED

    # ------------------------------------------------------------------
    # WebSocket loop
    # ------------------------------------------------------------------

    def _ws_loop(self) -> None:
        """Live WebSocket reconnect loop (background daemon thread).

        Not called in offline tests.  Requires ``websocket-client>=1.6``.
        """
        try:
            import websocket  # type: ignore[import]
        except ImportError:
            _log.error(
                "websocket-client is required for BinanceFeed live mode. "
                "Run: pip install 'websocket-client>=1.6'"
            )
            return

        def _on_message(_ws: Any, message: str) -> None:
            import json as _json

            try:
                outer = _json.loads(message)
                # Combined stream wraps payload in {"stream": ..., "data": {...}}
                data = outer.get("data", outer)
                stream: str = outer.get("stream", "")
                stream_sym = stream.split("@")[0] if "@" in stream else ""
                symbol = _STREAM_TO_SYMBOL.get(stream_sym)
                price_str = data.get("p")
                if symbol is None or price_str is None:
                    return
                price = float(price_str)
                with self._lock:
                    self._prices[symbol] = price
                    self._timestamps[symbol] = self._time_fn()
                    if self._connection_state != FeedConnectionState.DISCONNECTED:
                        self._connection_state = FeedConnectionState.CONNECTED
            except Exception as exc:
                _log.debug("BinanceFeed: message parse error: %s", exc)

        def _on_open(_ws: Any) -> None:
            _log.info("BinanceFeed: WebSocket connected")
            with self._lock:
                if self._connection_state != FeedConnectionState.DISCONNECTED:
                    self._connection_state = FeedConnectionState.CONNECTED

        def _on_close(_ws: Any, code: Any, msg: Any) -> None:
            _log.warning("BinanceFeed: WebSocket closed (code=%s)", code)
            with self._lock:
                if self._connection_state != FeedConnectionState.DISCONNECTED:
                    self._connection_state = FeedConnectionState.DISCONNECTED

        def _on_error(_ws: Any, error: Any) -> None:
            _log.error("BinanceFeed: WebSocket error: %s", error)
            with self._lock:
                if self._connection_state != FeedConnectionState.DISCONNECTED:
                    self._connection_state = FeedConnectionState.DISCONNECTED

        while True:
            with self._lock:
                if self._connection_state == FeedConnectionState.DISCONNECTED:
                    break

            try:
                ws_app = websocket.WebSocketApp(
                    _BINANCE_COMBINED_STREAM_URL,
                    on_message=_on_message,
                    on_open=_on_open,
                    on_close=_on_close,
                    on_error=_on_error,
                )
                ws_app.run_forever(ping_interval=20, ping_timeout=10)
            except Exception as exc:
                _log.error("BinanceFeed: connection attempt failed: %s", exc)

            # Mark disconnected; check before sleeping
            with self._lock:
                if self._connection_state == FeedConnectionState.DISCONNECTED:
                    break
                self._connection_state = FeedConnectionState.DISCONNECTED

            time.sleep(2)
