"""Orderbook slippage estimation for Polymarket trades.

Estimates slippage by simulating execution through the orderbook depth.
For a BUY order, walks the asks from best to worst; for SELL, walks bids.
Computes VWAP and calculates slippage vs mid-price.
"""

from dataclasses import dataclass
from typing import Optional, Literal
import logging

logger = logging.getLogger(__name__)

Confidence = Literal["high", "medium", "low"]


@dataclass
class SlippageResult:
    """Result of slippage estimation for a trade."""

    slippage_bps: Optional[float]  # Slippage in basis points, or None if insufficient data
    vwap: Optional[float]  # Volume-weighted average price of simulated execution
    mid: Optional[float]  # Mid-price (best_bid + best_ask) / 2
    filled_size: float  # Size that could be filled from orderbook
    requested_size: float  # Original requested size
    confidence: Confidence  # Confidence level of estimate
    reason: str  # Explanation of confidence level


def _extract_level_price(level: object) -> Optional[float]:
    """Extract price from an orderbook level."""
    if isinstance(level, dict):
        price = level.get("price") or level.get("p")
    elif isinstance(level, (list, tuple)) and level:
        price = level[0]
    else:
        return None

    try:
        return float(price)
    except (TypeError, ValueError):
        return None


def _extract_level_size(level: object) -> Optional[float]:
    """Extract size from an orderbook level."""
    if isinstance(level, dict):
        size = level.get("size") or level.get("s")
    elif isinstance(level, (list, tuple)) and len(level) > 1:
        size = level[1]
    else:
        return None

    try:
        return float(size)
    except (TypeError, ValueError):
        return None


def estimate_slippage_bps(
    book: dict,
    side: str,
    size: float,
) -> SlippageResult:
    """
    Estimate slippage for a trade by walking the orderbook.

    For BUY: walks asks from best (lowest) to worst (highest)
    For SELL: walks bids from best (highest) to worst (lowest)

    Computes VWAP and calculates slippage vs mid-price:
        BUY slippage = (VWAP - mid) / mid * 10000
        SELL slippage = (mid - VWAP) / mid * 10000

    Args:
        book: Orderbook dict with 'bids' and 'asks' arrays
        side: 'BUY' or 'SELL'
        size: Number of shares to simulate execution for

    Returns:
        SlippageResult with slippage estimate and confidence level
    """
    if size <= 0:
        return SlippageResult(
            slippage_bps=0.0,
            vwap=None,
            mid=None,
            filled_size=0.0,
            requested_size=size,
            confidence="high",
            reason="Zero size requested",
        )

    bids = book.get("bids") or []
    asks = book.get("asks") or []

    if not bids or not asks:
        return SlippageResult(
            slippage_bps=None,
            vwap=None,
            mid=None,
            filled_size=0.0,
            requested_size=size,
            confidence="low",
            reason="Empty orderbook",
        )

    # Extract best bid/ask for mid-price
    best_bid = _extract_level_price(bids[0])
    best_ask = _extract_level_price(asks[0])

    if best_bid is None or best_ask is None:
        return SlippageResult(
            slippage_bps=None,
            vwap=None,
            mid=None,
            filled_size=0.0,
            requested_size=size,
            confidence="low",
            reason="Could not parse best bid/ask",
        )

    mid = (best_bid + best_ask) / 2.0

    # Select levels to walk based on side
    side_upper = side.upper()
    if side_upper == "BUY":
        levels = asks  # Walk asks for buying
    elif side_upper == "SELL":
        levels = bids  # Walk bids for selling
    else:
        return SlippageResult(
            slippage_bps=None,
            vwap=None,
            mid=mid,
            filled_size=0.0,
            requested_size=size,
            confidence="low",
            reason=f"Invalid side: {side}",
        )

    # Walk levels and compute VWAP
    remaining = size
    total_value = 0.0
    filled = 0.0

    for level in levels:
        level_price = _extract_level_price(level)
        level_size = _extract_level_size(level)

        if level_price is None or level_size is None or level_size <= 0:
            continue

        fill_size = min(remaining, level_size)
        total_value += level_price * fill_size
        filled += fill_size
        remaining -= fill_size

        if remaining <= 0:
            break

    if filled <= 0:
        return SlippageResult(
            slippage_bps=None,
            vwap=None,
            mid=mid,
            filled_size=0.0,
            requested_size=size,
            confidence="low",
            reason="No fillable depth in orderbook",
        )

    vwap = total_value / filled

    # Calculate slippage vs mid
    if mid > 0:
        if side_upper == "BUY":
            # BUY: paying more than mid is slippage
            slippage_bps = (vwap - mid) / mid * 10000
        else:
            # SELL: receiving less than mid is slippage
            slippage_bps = (mid - vwap) / mid * 10000
    else:
        slippage_bps = 0.0

    # Determine confidence
    fill_ratio = filled / size
    if fill_ratio >= 1.0:
        confidence: Confidence = "high"
        reason = "Full size simulated through orderbook"
    elif fill_ratio >= 0.5:
        confidence = "medium"
        reason = f"Partial fill ({fill_ratio:.0%}) - remaining extrapolated"
    else:
        confidence = "low"
        reason = f"Insufficient depth - only {fill_ratio:.0%} fillable"

    return SlippageResult(
        slippage_bps=round(slippage_bps, 2),
        vwap=round(vwap, 6),
        mid=round(mid, 6),
        filled_size=filled,
        requested_size=size,
        confidence=confidence,
        reason=reason,
    )


def estimate_round_trip_slippage_bps(
    book: dict,
    size: float,
) -> dict:
    """
    Estimate total slippage for a round-trip (BUY + SELL).

    Args:
        book: Orderbook dict
        size: Number of shares for each leg

    Returns:
        Dict with buy_slippage_bps, sell_slippage_bps, total_slippage_bps, confidence
    """
    buy_result = estimate_slippage_bps(book, "BUY", size)
    sell_result = estimate_slippage_bps(book, "SELL", size)

    buy_slip = buy_result.slippage_bps or 0.0
    sell_slip = sell_result.slippage_bps or 0.0

    # Determine overall confidence (use lowest)
    confidence_order = {"high": 2, "medium": 1, "low": 0}
    min_conf = min(
        confidence_order[buy_result.confidence],
        confidence_order[sell_result.confidence],
    )
    overall_confidence = {2: "high", 1: "medium", 0: "low"}[min_conf]

    return {
        "buy_slippage_bps": buy_slip,
        "sell_slippage_bps": sell_slip,
        "total_slippage_bps": buy_slip + sell_slip,
        "buy_vwap": buy_result.vwap,
        "sell_vwap": sell_result.vwap,
        "mid": buy_result.mid,
        "confidence": overall_confidence,
        "buy_reason": buy_result.reason,
        "sell_reason": sell_result.reason,
    }
