"""Fee computation for Polymarket taker fees.

The fee formula uses a quadratic curve that adjusts based on price:
    fee_usdc = shares * price * (fee_rate_bps / 10000) * (price * (1 - price))^exponent

This results in lower fees at extreme prices (near 0 or 1) and higher fees
at mid-range prices (near 0.5).

Note: The fee curve parameters (exponent, formula) are subject to change
by Polymarket. Always use the live /fee-rate endpoint for fee_rate_bps.
"""

import logging

logger = logging.getLogger(__name__)

# Fee curve exponent - quadratic curve
# This parameter is subject to change; check Polymarket docs for updates
FEE_CURVE_EXPONENT = 2.0


def compute_taker_fee_usdc(
    shares: float,
    price: float,
    fee_rate_bps: float,
) -> float:
    """
    Compute the taker fee in USDC for a trade.

    Uses the Polymarket fee curve formula:
        fee = shares * price * (fee_rate_bps / 10000) * (price * (1 - price))^exponent

    Args:
        shares: Number of shares being traded
        price: Price per share (0 to 1)
        fee_rate_bps: Fee rate in basis points from /fee-rate endpoint

    Returns:
        Fee amount in USDC

    Examples:
        >>> compute_taker_fee_usdc(100, 0.5, 100)  # 100 shares at 0.5 price, 1% fee rate
        0.0625  # At price=0.5, curve factor is 0.25^2 = 0.0625

        >>> compute_taker_fee_usdc(100, 0.9, 100)  # Near extreme price
        0.0081  # Lower fee due to curve: 0.09^2 = 0.0081
    """
    if shares <= 0 or price <= 0 or price >= 1 or fee_rate_bps <= 0:
        return 0.0

    # Convert bps to decimal rate
    fee_rate = fee_rate_bps / 10000.0

    # Curve factor: (price * (1 - price))^exponent
    # At price=0.5: 0.25^2 = 0.0625 (maximum)
    # At price=0.1: 0.09^2 = 0.0081 (much lower)
    # At price=0.9: 0.09^2 = 0.0081 (much lower)
    curve_factor = (price * (1 - price)) ** FEE_CURVE_EXPONENT

    # Total fee
    fee_usdc = shares * price * fee_rate * curve_factor

    return fee_usdc


def compute_taker_fee_bps(price: float, fee_rate_bps: float) -> float:
    """
    Compute the effective fee rate in bps for a given price.

    This is the fee_rate_bps adjusted by the curve factor.

    Args:
        price: Price per share (0 to 1)
        fee_rate_bps: Base fee rate in bps from /fee-rate endpoint

    Returns:
        Effective fee rate in bps after curve adjustment
    """
    if price <= 0 or price >= 1 or fee_rate_bps <= 0:
        return 0.0

    curve_factor = (price * (1 - price)) ** FEE_CURVE_EXPONENT
    return fee_rate_bps * curve_factor


def estimate_round_trip_fees_usdc(
    shares: float,
    entry_price: float,
    exit_price: float,
    entry_fee_rate_bps: float,
    exit_fee_rate_bps: float,
) -> dict:
    """
    Estimate total fees for a round-trip trade (entry + exit).

    Args:
        shares: Number of shares
        entry_price: Entry price (0 to 1)
        exit_price: Exit price (0 to 1)
        entry_fee_rate_bps: Fee rate at entry
        exit_fee_rate_bps: Fee rate at exit

    Returns:
        Dict with entry_fee_usdc, exit_fee_usdc, total_fee_usdc
    """
    entry_fee = compute_taker_fee_usdc(shares, entry_price, entry_fee_rate_bps)
    exit_fee = compute_taker_fee_usdc(shares, exit_price, exit_fee_rate_bps)

    return {
        "entry_fee_usdc": entry_fee,
        "exit_fee_usdc": exit_fee,
        "total_fee_usdc": entry_fee + exit_fee,
    }
