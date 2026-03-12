"""Mark-price computation for unrealized PnL.

Two methods are supported:

bid (default — conservative)
    Long positions (BUY) are marked at ``best_bid`` — what you would receive
    if you sold immediately.  Short positions are marked at ``best_ask``.
    This always understates the mark value of a winning position.

midpoint
    Mark = (best_bid + best_ask) / 2.  Less conservative; useful when the
    spread is very wide and the mid is the best available estimate of fair
    value.

The method used for a run is recorded in ``summary.json`` and
``run_manifest.json`` so results are always reproducible.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Optional

#: Method constants — use these rather than raw strings.
MARK_BID = "bid"
MARK_MID = "midpoint"

_ZERO = Decimal("0")
_TWO = Decimal("2")

#: Sides (mirrors broker.rules.Side to avoid circular import)
_SIDE_BUY = "BUY"
_SIDE_SELL = "SELL"


def mark_price(
    side: str,
    best_bid: Optional[float],
    best_ask: Optional[float],
    method: str = MARK_BID,
) -> Optional[Decimal]:
    """Return the mark price for a position.

    Args:
        side:     ``"BUY"`` (long) or ``"SELL"`` (short).
        best_bid: Current best bid from the L2 book (or ``None`` if empty).
        best_ask: Current best ask from the L2 book (or ``None`` if empty).
        method:   ``"bid"`` (conservative, default) or ``"midpoint"``.

    Returns:
        Mark price as ``Decimal``, or ``None`` if the required book data is
        unavailable.

    Examples:
        Conservative long: marked at bid so unrealized PnL cannot be inflated.

            >>> mark_price("BUY", 0.58, 0.60)
            Decimal('0.58')

        Midpoint mode:

            >>> mark_price("BUY", 0.58, 0.60, method="midpoint")
            Decimal('0.59')
    """
    if method == MARK_BID:
        if side == _SIDE_BUY:
            if best_bid is None:
                return None
            return Decimal(str(best_bid))
        else:  # SELL (short position)
            if best_ask is None:
                return None
            return Decimal(str(best_ask))

    if method == MARK_MID:
        if best_bid is None or best_ask is None:
            return None
        return (Decimal(str(best_bid)) + Decimal(str(best_ask))) / _TWO

    raise ValueError(f"Unknown mark method: {method!r}. Use 'bid' or 'midpoint'.")
