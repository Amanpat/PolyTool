"""Adverse-selection signal computation for the live risk/control path.

Two signals are provided:

OFISignal — Order-Flow Imbalance (VPIN proxy)
    Approximates buy/sell pressure using the tick-rule on mid-price changes.
    True VPIN requires trade-tick volume with aggressor-side labels, which our
    tape format does not provide (``last_trade_price`` events carry price only,
    no size or direction).  The OFI proxy classifies each mid-price move as a
    buy tick (up) or sell tick (down) and triggers when the rolling imbalance
    ratio exceeds a threshold.

    Cold-start / missing-data behaviour:
      * No book update ever received → no-trigger, metadata status ``"cold_start"``
      * Fewer than ``min_samples`` classified ticks → no-trigger, status ``"warming_up"``
      * All ticks are neutral (mid unchanged) → no-trigger, status ``"neutral"``

MMWithdrawalSignal — Competing market-maker quote withdrawal
    Detects BBO depth collapse: when total size across the top N bid + ask
    levels drops below ``depth_drop_threshold`` × rolling average, other MMs
    are likely withdrawing quotes.

    Cold-start / missing-data behaviour:
      * No book update ever received → no-trigger, metadata status ``"cold_start"``
      * Fewer than ``min_samples`` updates → no-trigger, status ``"warming_up"``
      * Rolling baseline is zero (e.g. empty book) → no-trigger, status ``"zero_baseline"``

AdverseSelectionGuard
    Wraps both signals.  Exposes ``on_book_update(book)`` (call once per book
    tick) and ``check()`` which returns a ``GuardResult``.  Either signal
    triggering is sufficient to block an order.  If the book argument is
    ``None`` or lacks expected attributes, both signals receive empty data and
    stay at their safe no-trigger state.
"""

from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass
from typing import Any, Optional

logger = logging.getLogger(__name__)

ORDER_FLOW_SIGNAL_PROXY = "proxy"
ORDER_FLOW_SIGNAL_TRUE_VPIN = "true_vpin"

ADVERSE_SELECTION_MODE_DISABLED = "disabled"
ADVERSE_SELECTION_MODE_PROXY = "proxy"
ADVERSE_SELECTION_MODE_TRUE_VPIN = "true_vpin"
ADVERSE_SELECTION_MODE_UNAVAILABLE = "unavailable"

TRUE_VPIN_UNAVAILABLE_SENTINEL = "true_vpin_unavailable"
_ORDER_FLOW_SIGNAL_CHOICES = frozenset(
    {ORDER_FLOW_SIGNAL_PROXY, ORDER_FLOW_SIGNAL_TRUE_VPIN}
)


def build_adverse_selection_truth_surface(
    *,
    enabled: bool,
    order_flow_signal: str = ORDER_FLOW_SIGNAL_PROXY,
    true_vpin_available: bool = False,
) -> dict[str, Any]:
    """Return operator-facing truth metadata for adverse-selection wiring."""
    signal_name = str(order_flow_signal).strip().lower() or ORDER_FLOW_SIGNAL_PROXY
    if signal_name not in _ORDER_FLOW_SIGNAL_CHOICES:
        known = ", ".join(sorted(_ORDER_FLOW_SIGNAL_CHOICES))
        raise ValueError(
            f"order_flow_signal must be one of: {known}; got {order_flow_signal!r}"
        )

    if not enabled:
        return {
            "enabled": False,
            "status": "disabled",
            "mode": ADVERSE_SELECTION_MODE_DISABLED,
            "requested_order_flow_signal": signal_name,
            "effective_order_flow_signal": ADVERSE_SELECTION_MODE_DISABLED,
            "sentinel": None,
        }

    if signal_name == ORDER_FLOW_SIGNAL_PROXY:
        return {
            "enabled": True,
            "status": "active",
            "mode": ADVERSE_SELECTION_MODE_PROXY,
            "requested_order_flow_signal": signal_name,
            "effective_order_flow_signal": "ofi_proxy",
            "sentinel": None,
        }

    if true_vpin_available:
        return {
            "enabled": True,
            "status": "active",
            "mode": ADVERSE_SELECTION_MODE_TRUE_VPIN,
            "requested_order_flow_signal": signal_name,
            "effective_order_flow_signal": ORDER_FLOW_SIGNAL_TRUE_VPIN,
            "sentinel": None,
        }

    return {
        "enabled": True,
        "status": "active",
        "mode": ADVERSE_SELECTION_MODE_UNAVAILABLE,
        "requested_order_flow_signal": signal_name,
        "effective_order_flow_signal": TRUE_VPIN_UNAVAILABLE_SENTINEL,
        "sentinel": TRUE_VPIN_UNAVAILABLE_SENTINEL,
    }


def format_adverse_selection_truth_surface(surface: dict[str, Any]) -> str:
    """Render a compact operator-facing label for one truth surface."""
    mode = str(surface.get("mode") or "").strip().lower()
    if mode == ADVERSE_SELECTION_MODE_DISABLED:
        return "disabled"
    if mode == ADVERSE_SELECTION_MODE_PROXY:
        return "proxy signal active (OFI VPIN proxy)"
    if mode == ADVERSE_SELECTION_MODE_TRUE_VPIN:
        return "true VPIN active"
    if mode == ADVERSE_SELECTION_MODE_UNAVAILABLE:
        sentinel = str(surface.get("sentinel") or TRUE_VPIN_UNAVAILABLE_SENTINEL)
        return (
            f"unavailable sentinel ({sentinel}; true VPIN unavailable, "
            "MM withdrawal signal still active)"
        )
    return mode or "unknown"


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass
class SignalResult:
    """Result from a single signal check."""

    triggered: bool
    reason: str  # empty string when not triggered
    metadata: dict  # always populated for audit / instrumentation


@dataclass
class GuardResult:
    """Combined result from AdverseSelectionGuard.check()."""

    blocked: bool
    reason: str  # combined reason string; empty when not blocked
    signals: dict  # signal name → SignalResult


# ---------------------------------------------------------------------------
# OFI Signal
# ---------------------------------------------------------------------------


class OFISignal:
    """Order-Flow Imbalance proxy using the mid-price tick rule.

    Each book update is classified as +1 (buy tick, mid went up) or -1 (sell
    tick, mid went down).  Ties (mid unchanged) produce no tick and are not
    counted in the imbalance denominator.

    Imbalance = |buy_ticks - sell_ticks| / (buy_ticks + sell_ticks)

    Triggers when imbalance > ``threshold`` and at least ``min_samples``
    classified ticks have been accumulated.

    Args:
        window_ticks: Rolling window size (max classified ticks to retain).
        threshold:    Imbalance ratio in (0, 1] that triggers the signal.
        min_samples:  Minimum classified ticks required before triggering.
    """

    def __init__(
        self,
        window_ticks: int = 50,
        threshold: float = 0.70,
        min_samples: int = 20,
    ) -> None:
        if window_ticks < 2:
            raise ValueError("OFISignal: window_ticks must be >= 2")
        if not 0.0 < threshold <= 1.0:
            raise ValueError("OFISignal: threshold must be in (0, 1]")
        if min_samples < 1:
            raise ValueError("OFISignal: min_samples must be >= 1")

        self.window_ticks = window_ticks
        self.threshold = threshold
        self.min_samples = min_samples

        self._ticks: deque[int] = deque(maxlen=window_ticks)
        self._last_mid: Optional[float] = None
        self._updates_seen: int = 0

    def on_book_update(self, mid: Optional[float]) -> None:
        """Record one book update.

        Args:
            mid: Current (best_bid + best_ask) / 2.  None if book has no
                 valid BBO; the tick is skipped and does not affect
                 ``_last_mid`` so next valid tick is still compared against
                 the last known price.
        """
        self._updates_seen += 1

        if mid is None:
            # No valid mid: skip; do not update _last_mid so next valid
            # tick is still compared against the last known price.
            return

        if self._last_mid is None:
            # First observation: record baseline, no classification yet.
            self._last_mid = mid
            return

        if mid > self._last_mid:
            self._ticks.append(1)
        elif mid < self._last_mid:
            self._ticks.append(-1)
        # mid == _last_mid: neutral — no tick appended.

        self._last_mid = mid

    def check(self) -> SignalResult:
        """Evaluate current OFI state and return a SignalResult."""
        if self._updates_seen == 0:
            return SignalResult(
                triggered=False,
                reason="",
                metadata={"signal": "ofi", "status": "cold_start"},
            )

        classified = len(self._ticks)
        buy_ticks = sum(1 for t in self._ticks if t > 0)
        sell_ticks = sum(1 for t in self._ticks if t < 0)
        total = buy_ticks + sell_ticks

        # Neutral (all flat) takes precedence over warming_up: if no classified
        # ticks have accumulated yet (all moves were flat), report neutral so
        # callers know the signal is quiet rather than just cold.
        if total == 0:
            return SignalResult(
                triggered=False,
                reason="",
                metadata={
                    "signal": "ofi",
                    "status": "neutral",
                    "classified_ticks": classified,
                },
            )

        if classified < self.min_samples:
            return SignalResult(
                triggered=False,
                reason="",
                metadata={
                    "signal": "ofi",
                    "status": "warming_up",
                    "classified_ticks": classified,
                    "min_samples": self.min_samples,
                },
            )

        imbalance = abs(buy_ticks - sell_ticks) / total
        triggered = imbalance > self.threshold
        return SignalResult(
            triggered=triggered,
            reason=(
                f"ofi: imbalance {imbalance:.3f} > threshold {self.threshold}"
                if triggered
                else ""
            ),
            metadata={
                "signal": "ofi",
                "status": "active",
                "imbalance": round(imbalance, 4),
                "buy_ticks": buy_ticks,
                "sell_ticks": sell_ticks,
                "threshold": self.threshold,
            },
        )


class UnavailableVPINSignal:
    """Sentinel signal used when true VPIN is requested but unavailable."""

    def on_book_update(self, mid: Optional[float]) -> None:
        del mid

    def check(self) -> SignalResult:
        return SignalResult(
            triggered=False,
            reason="",
            metadata={
                "signal": ORDER_FLOW_SIGNAL_TRUE_VPIN,
                "status": "unavailable",
                "sentinel": TRUE_VPIN_UNAVAILABLE_SENTINEL,
            },
        )


# ---------------------------------------------------------------------------
# MM Withdrawal Signal
# ---------------------------------------------------------------------------


class MMWithdrawalSignal:
    """Detects BBO depth collapse indicating competing MM withdrawal.

    On each book update the total size across the top ``depth_levels`` bid
    and ask levels is recorded.  When the current value falls below
    ``depth_drop_threshold`` × rolling average of prior samples, the signal
    triggers.

    Args:
        window_ticks:         Rolling window for depth baseline (samples kept).
        depth_levels:         Number of price levels on each side to sum.
        depth_drop_threshold: Fraction [relative to baseline] below which
                              the signal triggers.  E.g. 0.50 means depth
                              < 50 % of rolling average → trigger.
        min_samples:          Minimum samples required before triggering.
    """

    def __init__(
        self,
        window_ticks: int = 30,
        depth_levels: int = 3,
        depth_drop_threshold: float = 0.50,
        min_samples: int = 10,
    ) -> None:
        if window_ticks < 2:
            raise ValueError("MMWithdrawalSignal: window_ticks must be >= 2")
        if depth_levels < 1:
            raise ValueError("MMWithdrawalSignal: depth_levels must be >= 1")
        if not 0.0 < depth_drop_threshold < 1.0:
            raise ValueError(
                "MMWithdrawalSignal: depth_drop_threshold must be in (0, 1)"
            )
        if min_samples < 1:
            raise ValueError("MMWithdrawalSignal: min_samples must be >= 1")

        self.window_ticks = window_ticks
        self.depth_levels = depth_levels
        self.depth_drop_threshold = depth_drop_threshold
        self.min_samples = min_samples

        self._depths: deque[float] = deque(maxlen=window_ticks)
        self._updates_seen: int = 0

    def on_book_update(
        self,
        top_bids: list[dict],
        top_asks: list[dict],
    ) -> None:
        """Record one book update.

        Args:
            top_bids: List of {"price": float, "size": float} bid levels,
                      best price first.  May be empty.
            top_asks: Same for ask side.
        """
        self._updates_seen += 1
        bid_depth = sum(
            float(lvl.get("size", 0.0)) for lvl in top_bids[: self.depth_levels]
        )
        ask_depth = sum(
            float(lvl.get("size", 0.0)) for lvl in top_asks[: self.depth_levels]
        )
        self._depths.append(bid_depth + ask_depth)

    def check(self) -> SignalResult:
        """Evaluate current MM-withdrawal state and return a SignalResult."""
        if self._updates_seen == 0:
            return SignalResult(
                triggered=False,
                reason="",
                metadata={"signal": "mm_withdrawal", "status": "cold_start"},
            )

        n = len(self._depths)
        if n < self.min_samples:
            return SignalResult(
                triggered=False,
                reason="",
                metadata={
                    "signal": "mm_withdrawal",
                    "status": "warming_up",
                    "samples": n,
                    "min_samples": self.min_samples,
                },
            )

        current = self._depths[-1]
        prior = list(self._depths)[:-1]
        if not prior:
            # Only one sample; cannot compute a meaningful baseline.
            return SignalResult(
                triggered=False,
                reason="",
                metadata={
                    "signal": "mm_withdrawal",
                    "status": "warming_up",
                    "samples": n,
                    "min_samples": self.min_samples,
                },
            )
        baseline_avg = sum(prior) / len(prior)

        if baseline_avg <= 0.0:
            return SignalResult(
                triggered=False,
                reason="",
                metadata={
                    "signal": "mm_withdrawal",
                    "status": "zero_baseline",
                    "current_depth": current,
                },
            )

        ratio = current / baseline_avg
        triggered = ratio < self.depth_drop_threshold
        return SignalResult(
            triggered=triggered,
            reason=(
                f"mm_withdrawal: BBO depth ratio {ratio:.3f} < threshold "
                f"{self.depth_drop_threshold}"
                if triggered
                else ""
            ),
            metadata={
                "signal": "mm_withdrawal",
                "status": "active",
                "current_depth": round(current, 2),
                "baseline_avg": round(baseline_avg, 2),
                "ratio": round(ratio, 4),
                "threshold": self.depth_drop_threshold,
            },
        )


# ---------------------------------------------------------------------------
# Combined guard
# ---------------------------------------------------------------------------


class AdverseSelectionGuard:
    """Combines OFI and MM-withdrawal signals into a single pre-trade gate.

    Either signal triggering causes ``check()`` to return ``blocked=True``.

    Usage::

        guard = AdverseSelectionGuard()
        # On each book event — before strategy generates orders:
        guard.on_book_update(book)
        # Pre-trade check:
        result = guard.check()
        if result.blocked:
            # suppress or reject

    Both signals default to conservative safe values.  Pass custom
    ``OFISignal`` / ``MMWithdrawalSignal`` instances to override parameters.

    Args:
        ofi:           OFI signal instance.  Defaults to OFISignal().
        mm_withdrawal: MM-withdrawal signal instance.  Defaults to
                       MMWithdrawalSignal().
    """

    def __init__(
        self,
        ofi: Optional[OFISignal] = None,
        mm_withdrawal: Optional[MMWithdrawalSignal] = None,
    ) -> None:
        self.ofi = ofi if ofi is not None else OFISignal()
        self.mm_withdrawal = (
            mm_withdrawal if mm_withdrawal is not None else MMWithdrawalSignal()
        )

    def on_book_update(self, book: Any) -> None:
        """Feed current book state to both signals.

        Safe to call with ``None`` or an object lacking expected attributes;
        both signals will receive empty / None data and stay at no-trigger.

        Args:
            book: L2Book instance (or duck-type with best_bid, best_ask,
                  top_bids(n), top_asks(n) interface).
        """
        if book is None:
            logger.debug("adverse_selection: on_book_update called with None book")
            return

        best_bid = getattr(book, "best_bid", None)
        best_ask = getattr(book, "best_ask", None)
        mid: Optional[float] = None
        if best_bid is not None and best_ask is not None:
            mid = (float(best_bid) + float(best_ask)) / 2.0

        top_bids: list[dict] = []
        top_asks: list[dict] = []
        if hasattr(book, "top_bids") and hasattr(book, "top_asks"):
            try:
                top_bids = list(book.top_bids(5))
                top_asks = list(book.top_asks(5))
            except Exception as exc:  # noqa: BLE001
                logger.warning("adverse_selection: could not read book levels: %s", exc)

        self.ofi.on_book_update(mid)
        self.mm_withdrawal.on_book_update(top_bids, top_asks)

    def check(self) -> GuardResult:
        """Check both signals and return a combined GuardResult."""
        ofi_result = self.ofi.check()
        mm_result = self.mm_withdrawal.check()

        blocked = ofi_result.triggered or mm_result.triggered
        active_reasons = [
            r.reason
            for r in (ofi_result, mm_result)
            if r.triggered and r.reason
        ]
        reason = "; ".join(active_reasons) if active_reasons else ""

        return GuardResult(
            blocked=blocked,
            reason=reason,
            signals={
                "ofi": ofi_result,
                "mm_withdrawal": mm_result,
            },
        )
