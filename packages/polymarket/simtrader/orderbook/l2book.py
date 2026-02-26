"""L2 order book state machine for SimTrader replay.

Applies book snapshots and price_change deltas to maintain a two-sided
level-2 order book.  Prices and sizes are stored as Decimal strings to
avoid floating-point precision drift during accumulation.

Terminology:
  bid  (BUY)  — highest price wins  → best_bid  = max(bid prices)
  ask  (SELL) — lowest  price wins  → best_ask  = min(ask prices)
"""

from __future__ import annotations

import logging
from decimal import Decimal, InvalidOperation
from typing import Optional

from ..tape.schema import EVENT_TYPE_BOOK, EVENT_TYPE_PRICE_CHANGE

logger = logging.getLogger(__name__)


class L2BookError(Exception):
    """Raised when the L2 book receives an invalid state transition."""


class L2Book:
    """Level-2 order book driven by normalized SimTrader events.

    Usage::

        book = L2Book("tok1", strict=True)
        book.apply(book_event)          # initializes from snapshot
        book.apply(price_change_event)  # applies delta
        print(book.best_bid, book.best_ask)
    """

    def __init__(self, asset_id: str, strict: bool = True) -> None:
        """
        Args:
            asset_id: Token ID this book tracks (used in error messages).
            strict:   If True, raise L2BookError on invalid transitions
                      (e.g. price_change before book snapshot).
                      If False, log a warning and skip.
        """
        self.asset_id = asset_id
        self.strict = strict
        self._initialized = False
        # price string -> Decimal size  (size > 0 means level is present)
        self._bids: dict[str, Decimal] = {}
        self._asks: dict[str, Decimal] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def best_bid(self) -> Optional[float]:
        """Highest bid price, or None if the bid side is empty."""
        if not self._bids:
            return None
        return float(max(Decimal(p) for p in self._bids))

    @property
    def best_ask(self) -> Optional[float]:
        """Lowest ask price, or None if the ask side is empty."""
        if not self._asks:
            return None
        return float(min(Decimal(p) for p in self._asks))

    def top_bids(self, n: int = 5) -> list[dict]:
        """Return top N bid levels sorted by price descending (highest first).

        Each entry: {"price": float, "size": float}
        Returns empty list if book not initialized or bid side is empty.
        """
        if not self._bids:
            return []
        sorted_levels = sorted(
            ((Decimal(p), s) for p, s in self._bids.items()),
            key=lambda x: x[0],
            reverse=True,
        )
        return [{"price": float(p), "size": float(s)} for p, s in sorted_levels[:n]]

    def top_asks(self, n: int = 5) -> list[dict]:
        """Return top N ask levels sorted by price ascending (lowest first).

        Each entry: {"price": float, "size": float}
        Returns empty list if book not initialized or ask side is empty.
        """
        if not self._asks:
            return []
        sorted_levels = sorted(
            ((Decimal(p), s) for p, s in self._asks.items()),
            key=lambda x: x[0],
        )
        return [{"price": float(p), "size": float(s)} for p, s in sorted_levels[:n]]

    def apply(self, event: dict) -> bool:
        """Apply a normalized tape event to update book state.

        Returns True if the event was applied (book state was modified or
        initialised), False if the event was skipped (e.g. price_change
        before a book snapshot in lenient mode, or a non-book event type).

        Only EVENT_TYPE_BOOK and EVENT_TYPE_PRICE_CHANGE affect the book.
        Other event types return False and have no side-effects.

        Raises:
            L2BookError: In strict mode, if price_change arrives before book.
        """
        event_type = event.get("event_type")

        if event_type == EVENT_TYPE_BOOK:
            self._apply_snapshot(event)
            return True

        if event_type == EVENT_TYPE_PRICE_CHANGE:
            if not self._initialized:
                msg = (
                    f"price_change received before book snapshot "
                    f"(seq={event.get('seq')}, asset_id={self.asset_id!r})"
                )
                if self.strict:
                    raise L2BookError(msg)
                logger.warning(msg)
                return False
            self._apply_price_change(event)
            return True

        # last_trade_price, tick_size_change, etc. — no book effect
        return False

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _apply_snapshot(self, event: dict) -> None:
        """Replace entire book state from a 'book' snapshot event."""
        self._bids.clear()
        self._asks.clear()

        for level in event.get("bids", []):
            price, size = self._parse_level(level)
            if price is not None and size is not None and size > 0:
                self._bids[price] = size

        for level in event.get("asks", []):
            price, size = self._parse_level(level)
            if price is not None and size is not None and size > 0:
                self._asks[price] = size

        self._initialized = True

    def apply_single_delta(self, change: dict) -> bool:
        """Apply one price-change entry from a modern batched ``price_changes[]`` message.

        Each entry has direct ``side`` / ``price`` / ``size`` fields — the same
        shape as items inside a legacy ``price_change`` event's ``changes[]`` list.

        Returns True if applied, False if skipped (not yet initialized in lenient mode).

        Raises:
            L2BookError: In strict mode, if called before a book snapshot.
        """
        if not self._initialized:
            msg = (
                f"price_changes[] entry received before book snapshot "
                f"(asset_id={self.asset_id!r})"
            )
            if self.strict:
                raise L2BookError(msg)
            logger.warning(msg)
            return False
        self._apply_single_change(change)
        return True

    def _apply_price_change(self, event: dict) -> None:
        """Apply a 'price_change' delta event (legacy ``changes[]`` format).

        Each change entry has:
          side  — "BUY" (bid) or "SELL" (ask)
          price — price level string
          size  — new size string; "0" or 0 means remove the level
        """
        for change in event.get("changes", []):
            self._apply_single_change(change)

    def _apply_single_change(self, change: dict) -> None:
        """Apply one delta entry: side, price, size to the appropriate book side."""
        side = (change.get("side") or "").upper()
        price = str(change.get("price") or "")
        size_raw = change.get("size", "0")

        if not price:
            logger.warning("price_change entry missing price field: %r", change)
            return

        try:
            size = Decimal(str(size_raw))
        except InvalidOperation:
            logger.warning(
                "Invalid size in price_change: %r — skipping level.", size_raw
            )
            return

        if side == "BUY":
            book = self._bids
        elif side == "SELL":
            book = self._asks
        else:
            logger.warning(
                "Unknown side in price_change: %r — skipping.", side
            )
            return

        if size == 0:
            book.pop(price, None)
        else:
            book[price] = size

    @staticmethod
    def _parse_level(level: object) -> tuple[Optional[str], Optional[Decimal]]:
        """Parse a book level from snapshot into (price_str, Decimal_size).

        Accepts both dict formats:
          {"price": "0.55", "size": "100"}  — standard CLOB format
          {"p": "0.55", "s": "100"}         — compact format
        And list/tuple format:
          ["0.55", "100"]                   — [price, size]
        """
        if isinstance(level, dict):
            price = str(level.get("price") or level.get("p") or "")
            size_raw = level.get("size") or level.get("s") or "0"
        elif isinstance(level, (list, tuple)) and len(level) >= 2:
            price = str(level[0])
            size_raw = level[1]
        else:
            return None, None

        if not price:
            return None, None

        try:
            size = Decimal(str(size_raw))
        except InvalidOperation:
            logger.warning("Invalid size in level: %r", size_raw)
            return price, None

        return price, size
