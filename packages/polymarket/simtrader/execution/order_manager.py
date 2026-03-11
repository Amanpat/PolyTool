"""OrderManager: reconcile desired quotes against open orders.

Responsibilities
----------------
* Diff desired_orders vs open_orders to produce an ActionPlan.
* Respect ``min_order_lifetime_seconds`` — do not cancel orders that were
  placed too recently (avoids wasteful churn when quotes wobble).
* Enforce ``max_cancels_per_minute`` and ``max_places_per_minute`` via a
  sliding-window rate cap.  Actions that exceed the cap are skipped and
  counted in ``ActionPlan.skipped_cancels`` / ``skipped_places``.

The reconcile_once method is pure given a fixed ``now`` timestamp so it
is straightforward to unit-test without real clocks.

Usage::

    from packages.polymarket.simtrader.execution.order_manager import (
        OrderManager, OrderManagerConfig, OpenOrder, DesiredOrder,
    )

    config = OrderManagerConfig(max_cancels_per_minute=5, max_places_per_minute=5)
    mgr = OrderManager(config)

    desired = [DesiredOrder(asset_id="tok1", side="BUY", price=D("0.48"), size=D("10"))]
    open_orders = {}
    plan = mgr.reconcile_once(desired, open_orders)
    # plan.to_place == [DesiredOrder(asset_id="tok1", side="BUY", price=D("0.48"), size=D("10"))]
"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Callable, Optional


@dataclass
class OrderManagerConfig:
    """Configuration knobs for OrderManager.

    Attributes:
        max_cancels_per_minute:     Hard cap on cancel actions per rolling minute.
        max_places_per_minute:      Hard cap on place actions per rolling minute.
        min_order_lifetime_seconds: Minimum age before an order may be cancelled.
                                    Protects against unnecessary churn when quotes
                                    move by only one tick and back.
    """

    max_cancels_per_minute: int = 10
    max_places_per_minute: int = 10
    min_order_lifetime_seconds: float = 5.0


@dataclass
class OpenOrder:
    """A currently-open order tracked by the OrderManager.

    Attributes:
        order_id:     Exchange-assigned or locally-assigned identifier.
        asset_id:     Token being traded.
        side:         "BUY" or "SELL".
        price:        Resting limit price.
        size:         Remaining resting size.
        submitted_at: Monotonic timestamp (seconds) when the order was placed.
    """

    order_id: str
    asset_id: str
    side: str
    price: Decimal
    size: Decimal
    submitted_at: float


@dataclass
class DesiredOrder:
    """A quote the strategy wants to maintain.

    Attributes:
        asset_id: Token being traded.
        side:     "BUY" or "SELL".
        price:    Desired limit price.
        size:     Desired size.
    """

    asset_id: str
    side: str
    price: Decimal
    size: Decimal


@dataclass
class ActionPlan:
    """Output of OrderManager.reconcile_once.

    Attributes:
        to_cancel:        order_ids that should be cancelled.
        to_place:         DesiredOrders that should be placed.
        skipped_cancels:  Cancels that were rate-limited or age-blocked.
        skipped_places:   Places that were rate-limited.
        reasons:          Human-readable reasons for skipped actions.
    """

    to_cancel: list[str] = field(default_factory=list)
    to_place: list[DesiredOrder] = field(default_factory=list)
    skipped_cancels: int = 0
    skipped_places: int = 0
    reasons: list[str] = field(default_factory=list)


_WINDOW_SECONDS = 60.0


class OrderManager:
    """Reconcile desired quotes against the current open-order set.

    Args:
        config:  OrderManagerConfig instance (uses defaults if not provided).
        _clock:  Callable[[], float] — monotonic clock.  Inject a fake in
                 tests to avoid real time dependencies.
    """

    def __init__(
        self,
        config: Optional[OrderManagerConfig] = None,
        _clock: Optional[Callable[[], float]] = None,
    ) -> None:
        self.config = config or OrderManagerConfig()
        self._clock: Callable[[], float] = _clock or time.monotonic
        # Sliding-window action history (stores timestamps of past actions)
        self._cancel_ts: deque[float] = deque()
        self._place_ts: deque[float] = deque()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _recent_count(self, ts_deque: deque[float], now: float) -> int:
        """Count events in ``ts_deque`` within the last 60 seconds."""
        cutoff = now - _WINDOW_SECONDS
        while ts_deque and ts_deque[0] < cutoff:
            ts_deque.popleft()
        return len(ts_deque)

    def _record_cancel(self, now: float) -> None:
        self._cancel_ts.append(now)

    def _record_place(self, now: float) -> None:
        self._place_ts.append(now)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def reconcile_once(
        self,
        desired_orders: list[DesiredOrder],
        open_orders: dict[str, OpenOrder],
        now: Optional[float] = None,
    ) -> ActionPlan:
        """Compute an ActionPlan to move from open_orders toward desired_orders.

        This method does NOT execute any actions — it only returns the plan.
        The caller is responsible for calling LiveExecutor.place_order /
        cancel_order for each item in the plan and recording fills.

        Args:
            desired_orders: Quotes the strategy wants open.
            open_orders:    Currently open orders keyed by order_id.
            now:            Monotonic timestamp for age/rate checks.
                            Defaults to self._clock().

        Returns:
            ActionPlan with to_cancel and to_place lists.
        """
        if now is None:
            now = self._clock()

        plan = ActionPlan()

        recent_cancels = self._recent_count(self._cancel_ts, now)
        recent_places = self._recent_count(self._place_ts, now)

        # ---- Index desired orders by (asset_id, side) ----
        # Each (asset_id, side) should have at most one desired quote.
        desired_by_key: dict[tuple[str, str], DesiredOrder] = {}
        for d in desired_orders:
            key = (d.asset_id, d.side.upper())
            desired_by_key[key] = d  # last one wins if duplicates

        # ---- Index open orders by (asset_id, side) → list[OpenOrder] ----
        open_by_key: dict[tuple[str, str], list[OpenOrder]] = {}
        for o in open_orders.values():
            key = (o.asset_id, o.side.upper())
            open_by_key.setdefault(key, []).append(o)

        # ---- All (asset_id, side) keys we need to consider ----
        all_keys = set(desired_by_key) | set(open_by_key)

        for key in all_keys:
            desired = desired_by_key.get(key)
            open_list = open_by_key.get(key, [])

            if desired is None:
                # No desired order for this side: cancel all open orders.
                for o in open_list:
                    if not _is_old_enough(o, now, self.config.min_order_lifetime_seconds):
                        plan.skipped_cancels += 1
                        plan.reasons.append(
                            f"order_manager: {o.order_id} too young to cancel "
                            f"(age={now - o.submitted_at:.1f}s < "
                            f"min={self.config.min_order_lifetime_seconds}s)"
                        )
                        continue
                    if recent_cancels >= self.config.max_cancels_per_minute:
                        plan.skipped_cancels += 1
                        plan.reasons.append(
                            f"order_manager: cancel rate cap reached "
                            f"({recent_cancels}/{self.config.max_cancels_per_minute}/min)"
                        )
                        continue
                    plan.to_cancel.append(o.order_id)
                    self._record_cancel(now)
                    recent_cancels += 1
                continue

            # Desired order exists.
            if not open_list:
                # No open order for this side: place new.
                if recent_places >= self.config.max_places_per_minute:
                    plan.skipped_places += 1
                    plan.reasons.append(
                        f"order_manager: place rate cap reached "
                        f"({recent_places}/{self.config.max_places_per_minute}/min)"
                    )
                    continue
                plan.to_place.append(desired)
                self._record_place(now)
                recent_places += 1
                continue

            # There are open orders.  Check if any matches the desired price.
            matching = [o for o in open_list if o.price == desired.price]
            stale = [o for o in open_list if o.price != desired.price]

            # Cancel stale orders (wrong price).
            for o in stale:
                if not _is_old_enough(o, now, self.config.min_order_lifetime_seconds):
                    plan.skipped_cancels += 1
                    plan.reasons.append(
                        f"order_manager: {o.order_id} too young to cancel "
                        f"(age={now - o.submitted_at:.1f}s)"
                    )
                    continue
                if recent_cancels >= self.config.max_cancels_per_minute:
                    plan.skipped_cancels += 1
                    plan.reasons.append(
                        f"order_manager: cancel rate cap reached "
                        f"({recent_cancels}/{self.config.max_cancels_per_minute}/min)"
                    )
                    continue
                plan.to_cancel.append(o.order_id)
                self._record_cancel(now)
                recent_cancels += 1

            # If no matching order, place the desired one.
            if not matching:
                if recent_places >= self.config.max_places_per_minute:
                    plan.skipped_places += 1
                    plan.reasons.append(
                        f"order_manager: place rate cap reached "
                        f"({recent_places}/{self.config.max_places_per_minute}/min)"
                    )
                    continue
                plan.to_place.append(desired)
                self._record_place(now)
                recent_places += 1

        return plan


def _is_old_enough(order: OpenOrder, now: float, min_lifetime: float) -> bool:
    """Return True iff the order is old enough to be eligible for cancellation."""
    return (now - order.submitted_at) >= min_lifetime
