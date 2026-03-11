"""Walk-the-book fill engine for SimTrader broker simulation.

Design invariants (all enforced by this module):

  1. No fill at prices not present in the book at the evaluation time.
     Levels are read directly from ``book._bids`` / ``book._asks``; nothing
     is invented.

  2. Walk-the-book math is correct.
     For a BUY order the engine walks ask levels from cheapest up to the
     order's limit price; for a SELL order it walks bid levels from highest
     down to the limit.  Weighted-average fill price is computed across all
     levels consumed.

  3. Conservative default.
     If the book is uninitialised or no competitive levels exist, the engine
     returns a ``rejected`` record with a descriptive reason — it never
     invents liquidity.

Note on book access:
    ``fill_engine`` reads ``book._bids`` and ``book._asks`` directly for
    performance.  The book is **read-only** from this module's perspective;
    it is never modified here.  The caller (SimBroker) is responsible for
    driving the book forward via ``book.apply()``.
"""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import TYPE_CHECKING

from .rules import FillRecord, Order, Side

if TYPE_CHECKING:
    from ..orderbook.l2book import L2Book

logger = logging.getLogger(__name__)

_ZERO = Decimal("0")


def try_fill(order: Order, book: "L2Book", eval_seq: int, ts_recv: float) -> FillRecord:
    """Attempt to fill *order* against the current *book* state.

    Must be called **after** the book has been updated for the current event
    (i.e. ``book.apply(event)`` already ran).

    Args:
        order:    Active order to fill.  The caller is responsible for only
                  passing orders whose ``is_active`` property is True.
        book:     Current L2 book state.  Read-only; never modified here.
        eval_seq: Tape ``seq`` at which this fill is evaluated.
        ts_recv:  Wall-clock ``ts_recv`` of the triggering event.

    Returns:
        FillRecord.  If no fill is possible, ``fill_size`` is Decimal("0")
        and ``fill_status`` is ``"rejected"``.  Partial fills are possible
        when available size is smaller than the order's remaining size.
    """

    def _reject(reason: str) -> FillRecord:
        return FillRecord(
            order_id=order.order_id,
            asset_id=order.asset_id,
            seq=eval_seq,
            ts_recv=ts_recv,
            side=order.side,
            fill_price=_ZERO,
            fill_size=_ZERO,
            remaining=order.remaining,
            fill_status="rejected",
            reject_reason=reason,
            because={
                "eval_seq": eval_seq,
                "book_best_bid": book.best_bid,
                "book_best_ask": book.best_ask,
                "levels_consumed": [],
            },
        )

    if not book._initialized:
        return _reject("book_not_initialized")

    if order.side == Side.BUY:
        # Walk the ask side, cheapest-first, up to the order's limit (ceiling).
        levels = _sorted_ask_levels(book, order.limit_price)
    elif order.side == Side.SELL:
        # Walk the bid side, highest-first, down to the order's limit (floor).
        levels = _sorted_bid_levels(book, order.limit_price)
    else:
        return _reject(f"unknown_side:{order.side!r}")

    if not levels:
        return _reject("no_competitive_levels")

    remaining = order.remaining
    total_filled = _ZERO
    total_notional = _ZERO          # running sum of price * size consumed
    consumed: list[dict[str, str]] = []   # [{price, size}, ...]

    for price_str, available_size in levels:
        if remaining <= _ZERO:
            break
        price = Decimal(price_str)
        consume = min(available_size, remaining)
        total_filled += consume
        total_notional += consume * price
        consumed.append({"price": price_str, "size": str(consume)})
        remaining -= consume

    if total_filled == _ZERO:
        # Defensive: levels existed but all had zero size (shouldn't happen).
        return _reject("no_competitive_levels")

    avg_price = total_notional / total_filled
    new_remaining = order.remaining - total_filled
    fill_status = "full" if new_remaining == _ZERO else "partial"

    return FillRecord(
        order_id=order.order_id,
        asset_id=order.asset_id,
        seq=eval_seq,
        ts_recv=ts_recv,
        side=order.side,
        fill_price=avg_price,
        fill_size=total_filled,
        remaining=new_remaining,
        fill_status=fill_status,
        reject_reason=None,
        because={
            "eval_seq": eval_seq,
            "book_best_bid": book.best_bid,
            "book_best_ask": book.best_ask,
            "levels_consumed": consumed,
        },
    )


# ---------------------------------------------------------------------------
# Internal helpers: level selection and sorting
# ---------------------------------------------------------------------------


def _sorted_ask_levels(
    book: "L2Book", limit_price: Decimal
) -> list[tuple[str, Decimal]]:
    """Ask levels at price <= *limit_price*, sorted cheapest-first.

    Only levels genuinely present in the book (positive size) are returned.
    """
    result: list[tuple[str, Decimal]] = []
    for price_str, size in book._asks.items():
        if size <= _ZERO:
            continue                          # defensive; shouldn't occur
        if Decimal(price_str) <= limit_price:
            result.append((price_str, size))
    result.sort(key=lambda x: Decimal(x[0]))  # ascending: cheapest first
    return result


def _sorted_bid_levels(
    book: "L2Book", limit_price: Decimal
) -> list[tuple[str, Decimal]]:
    """Bid levels at price >= *limit_price*, sorted highest-first.

    Only levels genuinely present in the book (positive size) are returned.
    """
    result: list[tuple[str, Decimal]] = []
    for price_str, size in book._bids.items():
        if size <= _ZERO:
            continue
        if Decimal(price_str) >= limit_price:
            result.append((price_str, size))
    result.sort(key=lambda x: Decimal(x[0]), reverse=True)  # descending
    return result
