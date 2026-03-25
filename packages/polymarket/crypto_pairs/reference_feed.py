"""Binance-first reference price feeds for Track 2 / Phase 1A crypto pair bot.

Tracks live spot prices for BTC, ETH, and SOL via public WebSocket feeds.
Binance remains the default. Coinbase Exchange ticker feed is available as an
explicit alternative and as an optional auto-fallback wrapper.

Architecture:
- ``BinanceFeed`` and ``CoinbaseFeed`` hold mutable internal price state.
  Callers retrieve immutable ``ReferencePriceSnapshot`` values via
  ``get_snapshot()``.
- Live WebSocket loops run in background daemon threads started by ``connect()``.
- ``AutoReferenceFeed`` composes Binance and Coinbase snapshots while
  preserving Binance-first preference when both feeds are healthy.
"""

from __future__ import annotations

import json
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
REFERENCE_FEED_PROVIDER_CHOICES: tuple[str, ...] = ("binance", "coinbase", "auto")
SUPPORTED_REFERENCE_FEED_PROVIDERS: frozenset[str] = frozenset(
    REFERENCE_FEED_PROVIDER_CHOICES
)

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
_STREAM_TO_SYMBOL: dict[str, str] = {v: k for k, v in _BINANCE_STREAM_SYMBOLS.items()}

# Coinbase Exchange public ticker feed for BTC/ETH/SOL
_COINBASE_SYMBOL_PRODUCTS: dict[str, str] = {
    "BTC": "BTC-USD",
    "ETH": "ETH-USD",
    "SOL": "SOL-USD",
}
_COINBASE_PRODUCT_TO_SYMBOL: dict[str, str] = {
    product_id: symbol for symbol, product_id in _COINBASE_SYMBOL_PRODUCTS.items()
}
_COINBASE_WS_URL = "wss://ws-feed.exchange.coinbase.com"

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
        feed_source: "binance" or "coinbase" when a price is present; "none"
            otherwise.
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
# Helper normalization / parsing functions
# ---------------------------------------------------------------------------


def normalize_reference_symbol(symbol: str) -> str:
    """Normalize and validate the canonical Track 2 symbol."""
    symbol_upper = str(symbol).strip().upper()
    if symbol_upper not in SUPPORTED_SYMBOLS:
        raise ValueError(
            f"Unsupported symbol {symbol!r}. "
            f"Supported: {sorted(SUPPORTED_SYMBOLS)}"
        )
    return symbol_upper


def normalize_reference_feed_provider(provider: Optional[str]) -> str:
    """Normalize and validate the configured reference-feed provider."""
    provider_normalized = str(
        provider if provider is not None else REFERENCE_FEED_PROVIDER_CHOICES[0]
    ).strip().lower()
    if provider_normalized not in SUPPORTED_REFERENCE_FEED_PROVIDERS:
        raise ValueError(
            f"Unsupported reference_feed_provider {provider!r}. "
            f"Supported: {list(REFERENCE_FEED_PROVIDER_CHOICES)}"
        )
    return provider_normalized


def normalize_coinbase_product_id(product_id: str) -> str:
    """Map a Coinbase product id like ``BTC-USD`` to ``BTC``."""
    product_id_upper = str(product_id).strip().upper()
    symbol = _COINBASE_PRODUCT_TO_SYMBOL.get(product_id_upper)
    if symbol is None:
        raise ValueError(
            f"Unsupported Coinbase product_id {product_id!r}. "
            f"Supported: {sorted(_COINBASE_PRODUCT_TO_SYMBOL)}"
        )
    return symbol


def parse_binance_ws_message(message: str) -> Optional[tuple[str, float]]:
    """Extract ``(symbol, price)`` from a Binance aggTrade payload."""
    outer = json.loads(message)
    data = outer.get("data", outer)
    stream: str = outer.get("stream", "")
    stream_symbol = stream.split("@")[0] if "@" in stream else ""
    symbol = _STREAM_TO_SYMBOL.get(stream_symbol)
    price_str = data.get("p")
    if symbol is None or price_str is None:
        return None
    return symbol, float(price_str)


def parse_coinbase_ws_message(message: str) -> Optional[tuple[str, float]]:
    """Extract ``(symbol, price)`` from a Coinbase ticker payload."""
    payload = json.loads(message)
    if payload.get("type") != "ticker":
        return None
    product_id = payload.get("product_id")
    price_str = payload.get("price")
    if product_id is None or price_str is None:
        return None
    try:
        symbol = normalize_coinbase_product_id(product_id)
    except ValueError:
        return None
    return symbol, float(price_str)


# ---------------------------------------------------------------------------
# BinanceFeed
# ---------------------------------------------------------------------------


class BinanceFeed:
    """Binance reference price feed for BTC, ETH, and SOL.

    Thread-safe. The WebSocket loop runs in a background daemon thread;
    ``get_snapshot()`` never blocks.

    Args:
        stale_threshold_s: Age (seconds) after which a price is considered
            stale. Defaults to ``DEFAULT_STALE_THRESHOLD_S`` (15 s).
        _time_fn: Injectable clock. Overridden in tests to control perceived
            price age without real delays.
    """

    SOURCE_NAME = "binance"
    THREAD_NAME = "BinanceFeed-WS"

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
            name=self.THREAD_NAME,
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
        """Return an immutable point-in-time snapshot for *symbol*."""
        symbol_upper = normalize_reference_symbol(symbol)
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
            feed_source=self.SOURCE_NAME,
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
        """Inject a price directly without a WebSocket connection."""
        symbol_upper = normalize_reference_symbol(symbol)
        self._record_price(symbol_upper, price, observed_at_s=observed_at_s)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _record_price(
        self,
        symbol: str,
        price: float,
        *,
        observed_at_s: Optional[float] = None,
    ) -> None:
        timestamp = observed_at_s if observed_at_s is not None else self._time_fn()
        with self._lock:
            self._prices[symbol] = price
            self._timestamps[symbol] = timestamp
            if self._connection_state != FeedConnectionState.DISCONNECTED:
                self._connection_state = FeedConnectionState.CONNECTED

    def _mark_connected(self) -> None:
        with self._lock:
            if self._connection_state != FeedConnectionState.DISCONNECTED:
                self._connection_state = FeedConnectionState.CONNECTED

    def _mark_disconnected(self) -> None:
        with self._lock:
            if self._connection_state != FeedConnectionState.DISCONNECTED:
                self._connection_state = FeedConnectionState.DISCONNECTED

    # ------------------------------------------------------------------
    # WebSocket loop
    # ------------------------------------------------------------------

    def _ws_loop(self) -> None:
        """Live WebSocket reconnect loop (background daemon thread)."""
        try:
            import websocket  # type: ignore[import]
        except ImportError:
            _log.error(
                "websocket-client is required for %s live mode. "
                "Run: pip install 'websocket-client>=1.6'",
                self.__class__.__name__,
            )
            return

        def _on_message(_ws: Any, message: str) -> None:
            try:
                parsed = parse_binance_ws_message(message)
                if parsed is None:
                    return
                symbol, price = parsed
                self._record_price(symbol, price)
            except Exception as exc:
                _log.debug("BinanceFeed: message parse error: %s", exc)

        def _on_open(_ws: Any) -> None:
            _log.info("BinanceFeed: WebSocket connected")
            self._mark_connected()

        def _on_close(_ws: Any, code: Any, msg: Any) -> None:
            _log.warning("BinanceFeed: WebSocket closed (code=%s)", code)
            self._mark_disconnected()

        def _on_error(_ws: Any, error: Any) -> None:
            _log.error("BinanceFeed: WebSocket error: %s", error)
            self._mark_disconnected()

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

            with self._lock:
                if self._connection_state == FeedConnectionState.DISCONNECTED:
                    break
                self._connection_state = FeedConnectionState.DISCONNECTED

            time.sleep(2)


class CoinbaseFeed(BinanceFeed):
    """Coinbase Exchange ticker feed with the same snapshot contract as Binance."""

    SOURCE_NAME = "coinbase"
    THREAD_NAME = "CoinbaseFeed-WS"

    def _ws_loop(self) -> None:
        try:
            import websocket  # type: ignore[import]
        except ImportError:
            _log.error(
                "websocket-client is required for %s live mode. "
                "Run: pip install 'websocket-client>=1.6'",
                self.__class__.__name__,
            )
            return

        def _on_message(_ws: Any, message: str) -> None:
            try:
                parsed = parse_coinbase_ws_message(message)
                if parsed is None:
                    return
                symbol, price = parsed
                self._record_price(symbol, price)
            except Exception as exc:
                _log.debug("CoinbaseFeed: message parse error: %s", exc)

        def _on_open(ws: Any) -> None:
            _log.info("CoinbaseFeed: WebSocket connected")
            self._mark_connected()
            try:
                ws.send(
                    json.dumps(
                        {
                            "type": "subscribe",
                            "product_ids": list(_COINBASE_PRODUCT_TO_SYMBOL),
                            "channels": ["ticker"],
                        }
                    )
                )
            except Exception as exc:
                _log.error("CoinbaseFeed: subscription failed: %s", exc)
                self._mark_disconnected()
                try:
                    ws.close()
                except Exception:
                    pass

        def _on_close(_ws: Any, code: Any, msg: Any) -> None:
            _log.warning("CoinbaseFeed: WebSocket closed (code=%s)", code)
            self._mark_disconnected()

        def _on_error(_ws: Any, error: Any) -> None:
            _log.error("CoinbaseFeed: WebSocket error: %s", error)
            self._mark_disconnected()

        while True:
            with self._lock:
                if self._connection_state == FeedConnectionState.DISCONNECTED:
                    break

            try:
                ws_app = websocket.WebSocketApp(
                    _COINBASE_WS_URL,
                    on_message=_on_message,
                    on_open=_on_open,
                    on_close=_on_close,
                    on_error=_on_error,
                )
                ws_app.run_forever(ping_interval=20, ping_timeout=10)
            except Exception as exc:
                _log.error("CoinbaseFeed: connection attempt failed: %s", exc)

            with self._lock:
                if self._connection_state == FeedConnectionState.DISCONNECTED:
                    break
                self._connection_state = FeedConnectionState.DISCONNECTED

            time.sleep(2)


class AutoReferenceFeed:
    """Binance-first wrapper that falls back to Coinbase when it is healthier."""

    def __init__(
        self,
        primary_feed: Optional[BinanceFeed] = None,
        fallback_feed: Optional[CoinbaseFeed] = None,
    ) -> None:
        self._primary_feed = primary_feed or BinanceFeed()
        self._fallback_feed = fallback_feed or CoinbaseFeed()

    def connect(self) -> None:
        self._primary_feed.connect()
        self._fallback_feed.connect()

    def disconnect(self) -> None:
        self._primary_feed.disconnect()
        self._fallback_feed.disconnect()

    def get_snapshot(self, symbol: str) -> ReferencePriceSnapshot:
        primary_snapshot = self._primary_feed.get_snapshot(symbol)
        fallback_snapshot = self._fallback_feed.get_snapshot(symbol)
        if primary_snapshot.is_usable:
            return primary_snapshot
        if fallback_snapshot.is_usable:
            return fallback_snapshot
        if self._snapshot_rank(primary_snapshot, preferred=True) >= self._snapshot_rank(
            fallback_snapshot,
            preferred=False,
        ):
            return primary_snapshot
        return fallback_snapshot

    @staticmethod
    def _snapshot_rank(
        snapshot: ReferencePriceSnapshot,
        *,
        preferred: bool,
    ) -> tuple[int, int, int, int, float, int]:
        if snapshot.connection_state == FeedConnectionState.CONNECTED:
            connection_rank = 2
        elif snapshot.connection_state == FeedConnectionState.DISCONNECTED:
            connection_rank = 1
        else:
            connection_rank = 0
        observed_at = snapshot.observed_at_s if snapshot.observed_at_s is not None else -1.0
        return (
            1 if snapshot.is_usable else 0,
            1 if snapshot.price is not None else 0,
            1 if not snapshot.is_stale else 0,
            connection_rank,
            observed_at,
            1 if preferred else 0,
        )


def build_reference_feed(
    provider: Optional[str] = None,
    *,
    stale_threshold_s: float = DEFAULT_STALE_THRESHOLD_S,
    _time_fn: Optional[Callable[[], float]] = None,
) -> BinanceFeed | CoinbaseFeed | AutoReferenceFeed:
    """Build the configured reference feed with Binance as the default."""
    provider_name = normalize_reference_feed_provider(provider)
    if provider_name == "binance":
        return BinanceFeed(stale_threshold_s=stale_threshold_s, _time_fn=_time_fn)
    if provider_name == "coinbase":
        return CoinbaseFeed(stale_threshold_s=stale_threshold_s, _time_fn=_time_fn)
    return AutoReferenceFeed(
        primary_feed=BinanceFeed(
            stale_threshold_s=stale_threshold_s,
            _time_fn=_time_fn,
        ),
        fallback_feed=CoinbaseFeed(
            stale_threshold_s=stale_threshold_s,
            _time_fn=_time_fn,
        ),
    )
