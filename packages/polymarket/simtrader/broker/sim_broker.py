"""SimBroker: order lifecycle management for SimTrader tape replay.

Processing order within a single tape event (``step()``):

  1. **Activate** PENDING orders whose ``effective_seq <= current_seq``.
  2. **Fill** ACTIVE/PARTIAL orders (only when the event is book-affecting).
  3. **Cancel** orders whose ``cancel_effective_seq <= current_seq``.

This ordering enforces the "no perfect cancels" guarantee:

    A cancel submitted at seq N (with 0 cancel_ticks → cancel_effective_seq N)
    cannot prevent a fill that also fires at seq N, because fills are processed
    *before* cancels within the same step.

Usage::

    broker = SimBroker(latency=LatencyConfig(submit_ticks=2, cancel_ticks=1))

    # Outside the replay loop:
    oid = broker.submit_order("tok1", Side.BUY, Decimal("0.42"), Decimal("100"), submit_seq=10)

    # Inside the replay loop (book must be updated before calling step):
    for event in events:
        book.apply(event)
        new_fills = broker.step(event, book)

    # Retrieve results:
    all_fills   = broker.fills         # list[FillRecord]
    order_log   = broker.order_events  # list[dict]  (lifecycle events)
"""

from __future__ import annotations

import logging
import uuid
from decimal import Decimal
from typing import Optional

from ..orderbook.l2book import L2Book
from ..tape.schema import EVENT_TYPE_BOOK, EVENT_TYPE_PRICE_CHANGE
from .fill_engine import try_fill
from .latency import ZERO_LATENCY, LatencyConfig
from .rules import FillRecord, Order, OrderStatus, Side

logger = logging.getLogger(__name__)

_ZERO = Decimal("0")
_BOOK_AFFECTING = frozenset({EVENT_TYPE_BOOK, EVENT_TYPE_PRICE_CHANGE})


class SimBroker:
    """Minimal simulated broker for a single replay session.

    Thread-safety: not thread-safe; designed for single-threaded replay.
    """

    def __init__(self, latency: LatencyConfig = ZERO_LATENCY) -> None:
        self._latency = latency
        self._orders: dict[str, Order] = {}
        self._fills: list[FillRecord] = []
        self._order_events: list[dict] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def submit_order(
        self,
        asset_id: str,
        side: str,
        limit_price: Decimal,
        size: Decimal,
        submit_seq: int,
        submit_ts: float = 0.0,
        order_id: Optional[str] = None,
    ) -> str:
        """Submit a new order.

        Args:
            asset_id:    Token/asset ID to trade.
            side:        ``Side.BUY`` or ``Side.SELL``.
            limit_price: Limit price.  Ceiling for buys (fill at <= limit);
                         floor for sells (fill at >= limit).
            size:        Total order size.
            submit_seq:  Tape ``seq`` at which the order is submitted.
            submit_ts:   Wall-clock ``ts_recv`` at submission (for logs).
            order_id:    Optional caller-provided ID; generated if omitted.

        Returns:
            The ``order_id`` string.
        """
        if order_id is None:
            order_id = uuid.uuid4().hex[:8]

        eff_seq = self._latency.effective_seq(submit_seq)
        order = Order(
            order_id=order_id,
            asset_id=asset_id,
            side=side,
            limit_price=limit_price,
            size=size,
            submit_seq=submit_seq,
            effective_seq=eff_seq,
        )
        self._orders[order_id] = order
        self._append_event(
            "submitted",
            order_id,
            submit_seq,
            submit_ts,
            {
                "asset_id": asset_id,
                "side": side,
                "limit_price": str(limit_price),
                "size": str(size),
                "effective_seq": eff_seq,
            },
        )
        logger.debug(
            "Order submitted: id=%s side=%s limit=%s size=%s eff_seq=%d",
            order_id, side, limit_price, size, eff_seq,
        )
        return order_id

    def cancel_order(
        self,
        order_id: str,
        cancel_seq: int,
        cancel_ts: float = 0.0,
    ) -> None:
        """Request cancellation of an open order.

        The cancel takes effect at ``cancel_seq + cancel_ticks``.  Any fill
        that fires at the *same* ``seq`` as ``cancel_effective_seq`` still
        goes through (fills are processed before cancels in ``step()``).

        Raises:
            KeyError:   ``order_id`` not found.
            ValueError: Order is already in a terminal state.
        """
        if order_id not in self._orders:
            raise KeyError(f"Order {order_id!r} not found")
        order = self._orders[order_id]
        if OrderStatus.is_terminal(order.status):
            raise ValueError(
                f"Order {order_id!r} is already terminal (status={order.status!r})"
            )
        eff_cancel = self._latency.cancel_effective_seq(cancel_seq)
        order.cancel_effective_seq = eff_cancel
        self._append_event(
            "cancel_submitted",
            order_id,
            cancel_seq,
            cancel_ts,
            {"cancel_effective_seq": eff_cancel},
        )
        logger.debug(
            "Cancel submitted: id=%s cancel_seq=%d eff_cancel=%d",
            order_id, cancel_seq, eff_cancel,
        )

    def step(
        self,
        event: dict,
        book: L2Book,
        fill_asset_id: Optional[str] = None,
    ) -> list[FillRecord]:
        """Process one tape event against all managed orders.

        Must be called **after** ``book.apply(event)`` so the book already
        reflects the latest state when fill decisions are made.

        Processing order:
          1. Activate PENDING orders (effective_seq <= seq).
          2. Attempt fills on ACTIVE/PARTIAL orders (book events only).
          3. Apply cancels (cancel_effective_seq <= seq).

        Args:
            event:         Tape event dict.
            book:          L2 book for this event's asset (already updated).
            fill_asset_id: When set, only attempt fills for orders whose
                           ``asset_id`` matches this value.  Activate and
                           cancel steps are NOT filtered — they fire for all
                           orders whenever any event advances the seq.
                           Default ``None`` means no filter (original behaviour).

        Returns:
            List of ``FillRecord`` objects produced in this step (may be empty).
        """
        seq: int = event.get("seq", 0)
        ts_recv: float = event.get("ts_recv", 0.0)
        is_book_event: bool = event.get("event_type", "") in _BOOK_AFFECTING

        new_fills: list[FillRecord] = []

        for order in list(self._orders.values()):
            if OrderStatus.is_terminal(order.status):
                continue

            # --- 1. Activate ---
            if order.status == OrderStatus.PENDING and seq >= order.effective_seq:
                order.status = OrderStatus.ACTIVE
                self._append_event("activated", order.order_id, seq, ts_recv, {})
                logger.debug("Order activated: id=%s seq=%d", order.order_id, seq)

            # --- 2. Fill (book-affecting events only; optionally asset-filtered) ---
            fill_allowed = fill_asset_id is None or order.asset_id == fill_asset_id
            if is_book_event and order.is_active and fill_allowed:
                fill = try_fill(order, book, seq, ts_recv)
                if fill.fill_size > _ZERO:
                    order.filled_size += fill.fill_size
                    order.status = (
                        OrderStatus.FILLED
                        if fill.fill_status == "full"
                        else OrderStatus.PARTIAL
                    )
                    self._fills.append(fill)
                    new_fills.append(fill)
                    self._append_event(
                        "fill",
                        order.order_id,
                        seq,
                        ts_recv,
                        {
                            "fill_price": str(fill.fill_price),
                            "fill_size": str(fill.fill_size),
                            "remaining": str(fill.remaining),
                            "fill_status": fill.fill_status,
                            "because": fill.because,
                        },
                    )
                    logger.debug(
                        "Fill: id=%s seq=%d size=%s price=%s status=%s",
                        order.order_id, seq, fill.fill_size,
                        fill.fill_price, fill.fill_status,
                    )

            # --- 3. Cancel ---
            if (
                order.cancel_effective_seq is not None
                and seq >= order.cancel_effective_seq
                and order.status in (
                    OrderStatus.ACTIVE,
                    OrderStatus.PARTIAL,
                    OrderStatus.PENDING,
                )
            ):
                order.status = OrderStatus.CANCELLED
                self._append_event(
                    "cancelled",
                    order.order_id,
                    seq,
                    ts_recv,
                    {"remaining": str(order.remaining)},
                )
                logger.debug("Order cancelled: id=%s seq=%d", order.order_id, seq)

        return new_fills

    # ------------------------------------------------------------------
    # Read-only accessors
    # ------------------------------------------------------------------

    @property
    def fills(self) -> list[FillRecord]:
        """All fill records produced so far (copies; safe to iterate)."""
        return list(self._fills)

    @property
    def order_events(self) -> list[dict]:
        """All order lifecycle events produced so far."""
        return list(self._order_events)

    def get_order(self, order_id: str) -> Order:
        """Return the Order for *order_id* (raises KeyError if not found)."""
        return self._orders[order_id]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _append_event(
        self,
        event_type: str,
        order_id: str,
        seq: int,
        ts_recv: float,
        extra: dict,
    ) -> None:
        self._order_events.append(
            {
                "event": event_type,
                "order_id": order_id,
                "seq": seq,
                "ts_recv": ts_recv,
                **extra,
            }
        )
