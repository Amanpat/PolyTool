"""Decimal-safe fee computation for SimTrader portfolio.

Implements the Polymarket quadratic-curve fee formula using Decimal arithmetic
for full determinism.  The existing ``packages/polymarket/fees.py`` uses float;
this module re-implements the same formula with Decimal so that ledger totals
never drift due to floating-point rounding.

Conservative by default
-----------------------
If ``fee_rate_bps`` is not supplied, :data:`DEFAULT_FEE_RATE_BPS` (200 bps)
is applied and a warning is logged.  This is the *maximum* typical taker fee
observed on Polymarket, so the estimate is always pessimistic — fees will be at
least as large as (and usually larger than) the actual exchange fee.

Fee formula (unchanged from SPEC-0004)
---------------------------------------
  fee_usdc = shares × price × (fee_rate_bps / 10 000)
             × (price × (1 − price))^FEE_CURVE_EXPONENT

The curve factor ``(p × (1−p))²`` reaches its maximum of 0.0625 at p = 0.5
and approaches 0 at the extremes (p → 0 or p → 1).  For a typical binary
prediction-market trade near p = 0.5 the effective fee rate is
``fee_rate_bps × 0.0625``.
"""

from __future__ import annotations

import logging
from decimal import Decimal

logger = logging.getLogger(__name__)

_ZERO = Decimal("0")
_ONE = Decimal("1")
_TEN_THOUSAND = Decimal("10000")
_CURVE_EXPONENT = 2  # integer so Decimal ** int works exactly

#: Conservative default: 200 bps (2 %).  Used when the caller does not supply
#: a live fee rate from the /fee-rate endpoint.
DEFAULT_FEE_RATE_BPS: Decimal = Decimal("200")


def compute_fill_fee(
    fill_size: Decimal,
    fill_price: Decimal,
    fee_rate_bps: Decimal | None = None,
) -> Decimal:
    """Return the taker fee in USDC for one fill (all-Decimal arithmetic).

    Args:
        fill_size:    Number of shares filled.
        fill_price:   Fill price per share (must be in (0, 1) exclusive).
        fee_rate_bps: Fee rate in basis points.  Pass ``None`` to apply the
                      conservative default (:data:`DEFAULT_FEE_RATE_BPS`).

    Returns:
        Fee in USDC as a ``Decimal``.  Returns ``Decimal("0")`` when the
        inputs are out of range (zero size, price at boundary, etc.).
    """
    if fee_rate_bps is None:
        logger.warning(
            "fee_rate_bps not provided; applying conservative default %s bps",
            DEFAULT_FEE_RATE_BPS,
        )
        fee_rate_bps = DEFAULT_FEE_RATE_BPS

    if fill_size <= _ZERO or fill_price <= _ZERO or fill_price >= _ONE:
        return _ZERO

    rate = fee_rate_bps / _TEN_THOUSAND
    # (price × (1 − price))²  — integer exponent keeps Decimal exact
    curve_factor = (fill_price * (_ONE - fill_price)) ** _CURVE_EXPONENT
    return fill_size * fill_price * rate * curve_factor


def worst_case_fee(
    fill_size: Decimal,
    fill_price: Decimal,
    fee_rate_bps: Decimal | None = None,
) -> Decimal:
    """Return the *worst-case* fee using the maximum curve factor (price = 0.5).

    This is useful for pre-trade estimates when the exact fill price is unknown.
    It intentionally over-estimates the fee.

    The maximum curve factor is ``(0.5 × 0.5)² = 0.0625``.
    """
    if fee_rate_bps is None:
        fee_rate_bps = DEFAULT_FEE_RATE_BPS

    if fill_size <= _ZERO:
        return _ZERO

    MAX_CURVE = Decimal("0.0625")
    rate = fee_rate_bps / _TEN_THOUSAND
    # Use the actual notional if price is known, else assume worst-case price=0.5
    price = fill_price if (_ZERO < fill_price < _ONE) else Decimal("0.5")
    return fill_size * price * rate * MAX_CURVE
