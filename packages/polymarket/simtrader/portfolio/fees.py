"""Decimal-safe fee computation for SimTrader portfolio.

Two dispatch paths:

Category-aware path (new, exponent-1)
    Activated when ``category`` is supplied to :func:`compute_fill_fee`.
    fee_usdc = shares × category_rate × price × (1 − price)

Legacy path (exponent-2, backward-compatible)
    Used when only ``fee_rate_bps`` is supplied (or neither argument).
    fee_usdc = shares × price × (fee_rate_bps / 10 000)
               × (price × (1 − price))²

Maker role
    Polymarket charges makers zero fees (Option A, no rebate estimator).
    :func:`compute_fill_fee` returns ``Decimal("0")`` when ``role="maker"``.

Kalshi fee — :class:`KalshiFeeModel`
    fee_usdc = ceil(0.07 × contracts × price × (1 − price))
"""

from __future__ import annotations

import logging
from decimal import ROUND_CEILING, Decimal
from typing import Union

logger = logging.getLogger(__name__)

_ZERO = Decimal("0")
_ONE = Decimal("1")
_TEN_THOUSAND = Decimal("10000")
_CURVE_EXPONENT = 2  # integer so Decimal ** int works exactly

#: Conservative default: 200 bps (2 %).  Used when the caller does not supply
#: a live fee rate from the /fee-rate endpoint.
DEFAULT_FEE_RATE_BPS: Decimal = Decimal("200")

#: Taker fee rates by Polymarket market category (fractional, not bps).
#: Source: Polymarket /fee-rate endpoint; verified against acceptance criteria
#: from the Unified Open Source Integration Sprint work packet (2026-04-21).
#: geopolitics = 0 (free markets on Polymarket).
POLYMARKET_CATEGORY_FEE_RATES: dict[str, Decimal] = {
    "crypto": Decimal("0.072"),
    "sports": Decimal("0.03"),
    "politics": Decimal("0.04"),
    "finance": Decimal("0.04"),
    "mentions": Decimal("0.04"),
    "tech": Decimal("0.04"),
    "economics": Decimal("0.05"),
    "culture": Decimal("0.05"),
    "weather": Decimal("0.05"),
    "other": Decimal("0.05"),
    "geopolitics": Decimal("0"),
}


def compute_fill_fee(
    fill_size: Decimal,
    fill_price: Decimal,
    fee_rate_bps: Decimal | None = None,
    *,
    role: str = "taker",
    category: str | None = None,
) -> Decimal:
    """Return the fee in USDC for one fill (all-Decimal arithmetic).

    Dispatch rules:
    - ``role="maker"`` → always returns ``Decimal("0")``.
    - ``category`` supplied → category-aware exponent-1 formula.
    - ``category`` omitted → legacy exponent-2 formula (``fee_rate_bps``).

    Args:
        fill_size:    Number of shares filled.
        fill_price:   Fill price per share (must be in (0, 1) exclusive).
        fee_rate_bps: Fee rate in basis points (legacy path only).
        role:         ``"taker"`` or ``"maker"``.  Makers pay zero (Option A).
        category:     Polymarket market category (activates new path).

    Returns:
        Fee in USDC as a ``Decimal``.  Returns ``Decimal("0")`` for
        out-of-range inputs, maker role, or a zero-rate category.
    """
    if role == "maker":
        return _ZERO

    if fill_size <= _ZERO or fill_price <= _ZERO or fill_price >= _ONE:
        return _ZERO

    # --- Category-aware path (exponent-1) ---
    if category is not None:
        cat_key = category.lower()
        cat_rate = POLYMARKET_CATEGORY_FEE_RATES.get(cat_key)
        if cat_rate is None:
            logger.warning(
                "Unknown Polymarket category %r; defaulting to 'other' rate (0.05)",
                category,
            )
            cat_rate = POLYMARKET_CATEGORY_FEE_RATES["other"]
        return fill_size * cat_rate * fill_price * (_ONE - fill_price)

    # --- Legacy path (exponent-2) — unchanged for backward compatibility ---
    if fee_rate_bps is None:
        logger.warning(
            "fee_rate_bps not provided; applying conservative default %s bps",
            DEFAULT_FEE_RATE_BPS,
        )
        fee_rate_bps = DEFAULT_FEE_RATE_BPS

    rate = fee_rate_bps / _TEN_THOUSAND
    curve_factor = (fill_price * (_ONE - fill_price)) ** _CURVE_EXPONENT
    return fill_size * fill_price * rate * curve_factor


def worst_case_fee(
    fill_size: Decimal,
    fill_price: Decimal,
    fee_rate_bps: Decimal | None = None,
) -> Decimal:
    """Return the *worst-case* fee using the maximum curve factor (price = 0.5).

    Uses the legacy exponent-2 path.  Useful for pre-trade estimates when the
    exact fill price is unknown.  The maximum curve factor is ``(0.5×0.5)² = 0.0625``.
    """
    if fee_rate_bps is None:
        fee_rate_bps = DEFAULT_FEE_RATE_BPS

    if fill_size <= _ZERO:
        return _ZERO

    MAX_CURVE = Decimal("0.0625")
    rate = fee_rate_bps / _TEN_THOUSAND
    price = fill_price if (_ZERO < fill_price < _ONE) else Decimal("0.5")
    return fill_size * price * rate * MAX_CURVE


class KalshiFeeModel:
    """Kalshi exchange fee model (taker fees only).

    Formula: fee = ceil(0.07 × contracts × price × (1 − price))
    Rounded up to the nearest cent (USDC).

    Attribution: derived from evan-kolberg/prediction-market-backtesting (MIT).
    """

    KALSHI_FEE_RATE: Decimal = Decimal("0.07")
    _CENT: Decimal = Decimal("0.01")

    @classmethod
    def compute_fee(
        cls,
        contracts: Union[Decimal, int, float],
        price: Union[Decimal, int, float],
    ) -> Decimal:
        """Return the Kalshi taker fee for one fill, rounded up to the cent.

        Args:
            contracts: Number of contracts.
            price:     Fill price per contract (0 < price < 1).

        Returns:
            Fee in USDC as a ``Decimal``, rounded up to the nearest cent.
            Returns ``Decimal("0")`` for out-of-range inputs.
        """
        c = Decimal(str(contracts))
        p = Decimal(str(price))
        if c <= _ZERO or p <= _ZERO or p >= _ONE:
            return _ZERO
        raw = cls.KALSHI_FEE_RATE * c * p * (_ONE - p)
        return raw.quantize(cls._CENT, rounding=ROUND_CEILING)
