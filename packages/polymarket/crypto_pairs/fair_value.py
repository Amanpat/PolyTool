"""Fair-value helpers for 5m/15m crypto up/down binary markets.

Model: Log-normal spot price process, zero drift (risk-neutral approximation).

    P(YES) = P(S_T > K) = N(d)
    where  d = ln(S / K) / (σ · √τ)

    S  = current underlying price (from reference feed)
    K  = market resolution threshold
    σ  = annualized volatility assumption (per symbol, table below)
    τ  = remaining time to expiry in years

For the NO leg: P(NO) = 1 − P(YES)

The model is intentionally simple and explicit.  Its purpose is the soft
entry-rule gate in the accumulation engine ("is this leg underpriced?") —
not precise option pricing.  Assumptions are attached to every output for
operator visibility.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Optional


# ---------------------------------------------------------------------------
# Volatility assumptions
# ---------------------------------------------------------------------------

# Conservative annualized volatility estimates for crypto pair soft-rule gating.
# These are STRATEGY ASSUMPTIONS only — not calibrated from live data.
# Operator review is expected before live capital deployment.
DEFAULT_ANNUAL_VOL: dict[str, float] = {
    "BTC": 0.80,   # 80 % annualised
    "ETH": 1.00,   # 100 % annualised
    "SOL": 1.20,   # 120 % annualised
}

_SECONDS_PER_YEAR: float = 365.25 * 24.0 * 3600.0

# Minimum τ (1 second in years) to avoid division by zero at expiry
_MIN_TAU_YEARS: float = 1.0 / _SECONDS_PER_YEAR

# Probability clamp: keep fair values in the open interval (FLOOR, CEIL)
_PROB_FLOOR: float = 0.005
_PROB_CEIL: float = 0.995


# ---------------------------------------------------------------------------
# Output model
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FairValueEstimate:
    """Fair-value probability estimate for one leg of a binary market.

    Attributes:
        symbol: "BTC", "ETH", or "SOL".
        duration_min: 5 or 15.
        side: "YES" or "NO".
        underlying_price: Spot price used as input.
        threshold: Market resolution threshold used as input.
        remaining_seconds: Time-to-expiry used as input.
        fair_prob: Estimated probability in the range (0.005, 0.995).
        d_param: Log-normal *d* parameter (diagnostic, unitless).
        annual_vol: Annualized volatility assumption actually used.
        model: Model identifier string.
        assumptions: Operator-visible assumption flags.
    """

    symbol: str
    duration_min: int
    side: str
    underlying_price: float
    threshold: float
    remaining_seconds: float

    fair_prob: float
    d_param: float
    annual_vol: float
    model: str = "lognormal_no_drift"

    assumptions: tuple[str, ...] = field(
        default_factory=lambda: (
            "lognormal_no_drift",
            "vol_assumption_not_calibrated",
            "no_transaction_cost_adjustment",
        )
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "duration_min": self.duration_min,
            "side": self.side,
            "underlying_price": self.underlying_price,
            "threshold": self.threshold,
            "remaining_seconds": self.remaining_seconds,
            "fair_prob": self.fair_prob,
            "d_param": self.d_param,
            "annual_vol": self.annual_vol,
            "model": self.model,
            "assumptions": list(self.assumptions),
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _norm_cdf(x: float) -> float:
    """Standard normal CDF using Python stdlib ``math.erf``."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


# ---------------------------------------------------------------------------
# Core function
# ---------------------------------------------------------------------------


def estimate_fair_value(
    symbol: str,
    duration_min: int,
    side: str,
    underlying_price: float,
    threshold: float,
    remaining_seconds: float,
    *,
    annual_vol: Optional[float] = None,
) -> FairValueEstimate:
    """Estimate the fair probability for one leg of a crypto binary market.

    Args:
        symbol: "BTC", "ETH", or "SOL" (case-insensitive).
        duration_min: Market duration in minutes (5 or 15).
        side: "YES" (price above threshold) or "NO" (price below threshold).
            Case-insensitive.
        underlying_price: Current spot price from the reference feed.
        threshold: Market resolution threshold.
        remaining_seconds: Seconds until market expiry (≥ 0).
        annual_vol: Annualized volatility override.  Defaults to
            ``DEFAULT_ANNUAL_VOL[symbol]`` when ``None``.

    Returns:
        :class:`FairValueEstimate` with ``fair_prob`` in (0.005, 0.995).

    Raises:
        ValueError: If symbol or side is unsupported, or if prices are
            non-positive.
    """
    symbol_upper = symbol.strip().upper()
    side_upper = side.strip().upper()

    if symbol_upper not in DEFAULT_ANNUAL_VOL:
        raise ValueError(
            f"Unsupported symbol {symbol!r}. "
            f"Supported: {sorted(DEFAULT_ANNUAL_VOL)}"
        )
    if side_upper not in ("YES", "NO"):
        raise ValueError(f"side must be 'YES' or 'NO', got {side!r}")
    if underlying_price <= 0.0:
        raise ValueError(
            f"underlying_price must be > 0, got {underlying_price!r}"
        )
    if threshold <= 0.0:
        raise ValueError(f"threshold must be > 0, got {threshold!r}")

    sigma = annual_vol if annual_vol is not None else DEFAULT_ANNUAL_VOL[symbol_upper]
    tau_years = max(remaining_seconds / _SECONDS_PER_YEAR, _MIN_TAU_YEARS)
    vol_sqrt_tau = sigma * math.sqrt(tau_years)

    if vol_sqrt_tau <= 0.0:
        # Degenerate: no uncertainty — price relative to threshold is deterministic
        raw_d = math.copysign(10.0, math.log(underlying_price / threshold))
    else:
        raw_d = math.log(underlying_price / threshold) / vol_sqrt_tau

    p_yes = _clamp(_norm_cdf(raw_d), _PROB_FLOOR, _PROB_CEIL)

    if side_upper == "YES":
        fair_prob = p_yes
    else:
        fair_prob = _clamp(1.0 - p_yes, _PROB_FLOOR, _PROB_CEIL)

    return FairValueEstimate(
        symbol=symbol_upper,
        duration_min=duration_min,
        side=side_upper,
        underlying_price=underlying_price,
        threshold=threshold,
        remaining_seconds=remaining_seconds,
        fair_prob=fair_prob,
        d_param=raw_d,
        annual_vol=sigma,
        model="lognormal_no_drift",
    )
