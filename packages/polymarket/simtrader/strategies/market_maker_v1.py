"""MarketMakerV1 — logit-space Avellaneda-Stoikov for binary prediction markets.

Quote model
-----------
  1. Clip probability p to [_PROB_CLIP_EPS, 1 - _PROB_CLIP_EPS].
  2. Transform to logit space: x = ln(p / (1-p)).
  3. Compute reservation price x_r and spread delta_x in logit space:
       x_r    = x - q * gamma * sigma_sq * T
       delta_x = gamma * sigma_sq * T + (2/gamma) * ln(1 + gamma/kappa)
  4. Convert bid/ask back via sigmoid: sigmoid(x) = 1 / (1 + exp(-x)).
       p_bid = sigmoid(x_r - delta_x/2)
       p_ask = sigmoid(x_r + delta_x/2)
  5. Inventory q = net_YES_position / order_size.

Why this is correct for binary markets
---------------------------------------
In logit space the mid-price is an unbounded real number and the A-S
diffusion assumption is far more natural than in probability space (which is
bounded to [0, 1]).  As a consequence:

  * Near p = 0.50 the sigmoid derivative is 0.25, so a fixed logit spread
    maps to the *widest* physical spread.
  * Near the tails (p ≈ 0.05 / 0.95) the sigmoid derivative is ~0.05, so
    the same logit spread maps to a *compressed* physical spread.

This matches economic intuition: markets near certainty carry less
mid-point uncertainty per unit probability move.

All constructor parameters are identical to MarketMakerV0 for compatibility
with existing replay, sweep, and live-execution interfaces.
"""

from __future__ import annotations

import math
from collections import deque
from decimal import Decimal
from statistics import pvariance
from typing import Any, Optional

from packages.polymarket.simtrader.strategies.market_maker_v0 import (
    MarketMakerV0,
    _MAX_ASK_PRICE,
    _MAX_BID_PRICE,
    _MIN_ASK_PRICE,
    _MIN_BID_PRICE,
    _MIN_REMAINING_HOURS,
    _clamp,
)
from packages.polymarket.simtrader.strategy.base import OrderIntent

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_PROB_CLIP_EPS: float = 1e-4
"""Probability clipping bounds: inputs are clipped to [eps, 1-eps] before
logit to avoid ±inf.  1e-4 corresponds to logit ≈ ±9.2, well within float64.
"""

_DEFAULT_SIGMA_SQ_LOGIT: float = 0.003
"""Fallback logit-space variance when fewer than 3 mid-history points exist.

Calibration: at p=0.5 a probability move of Δp has logit move Δx ≈ 4·Δp.
So logit σ² ≈ 16 × probability σ².  MarketMakerV0 uses 0.0002 → this
default is 0.0002 × 16 ≈ 0.003.
"""

_MIN_TRADES_FOR_KAPPA: int = 5
"""Minimum ``last_trade_price`` arrivals in the rolling window before the
live kappa proxy is engaged.  Below this count the constructor kappa is
returned as the explicit fallback (see :meth:`MarketMakerV1._kappa`).
"""

_KAPPA_TRADES_PER_SEC_SCALE: float = 10.0
"""Scale factor converting trades/second → kappa proxy value.

Derivation: at 1 trade per 10 seconds (rate = 0.1 t/s) this yields
kappa ≈ 1.0, which matches the default constructor value for a moderately
active binary market.

IMPORTANT — this is an ORDINAL PROXY, not an MLE estimate of the A-S
fill-decay parameter κ.  The true κ is the rate at which fill probability
decays with posted spread.  Calibrating κ properly requires observing fill
rates at multiple spread levels across many sessions — data that is not
available during a single tape replay.

What we can observe: ``last_trade_price`` event arrival timestamps.  A
busier market (more arrivals) is more liquid and therefore supports a
tighter spread, which is directionally correct.  The absolute scale is
held constant via the clamp [_MIN_KAPPA, _MAX_KAPPA].
"""

_MIN_KAPPA: float = 0.20
"""Lower bound on calibrated kappa (prevents degenerate wide spreads)."""

_MAX_KAPPA: float = 10.0
"""Upper bound on calibrated kappa (prevents degenerate narrow spreads)."""


# ---------------------------------------------------------------------------
# Math helpers
# ---------------------------------------------------------------------------


def _logit(p: float) -> float:
    """Logit transform ln(p / (1-p)).  Caller must ensure 0 < p < 1."""
    return math.log(p / (1.0 - p))


def _sigmoid(x: float) -> float:
    """Numerically stable sigmoid 1 / (1 + exp(-x))."""
    if x >= 0.0:
        return 1.0 / (1.0 + math.exp(-x))
    exp_x = math.exp(x)
    return exp_x / (1.0 + exp_x)


def _clip_prob(p: float, eps: float = _PROB_CLIP_EPS) -> float:
    """Clip p to [eps, 1-eps] to avoid inf in logit."""
    return max(eps, min(1.0 - eps, p))


# ---------------------------------------------------------------------------
# Strategy class
# ---------------------------------------------------------------------------


class MarketMakerV1(MarketMakerV0):
    """Logit-space Avellaneda-Stoikov market maker for binary prediction markets.

    Inherits the full constructor, lifecycle hooks (on_start / on_fill),
    volatility window management, time-horizon tracking, microprice, and
    reprice-threshold logic from MarketMakerV0.

    Methods overridden beyond V0:
      __init__        — adds _trade_arrival_ts deque for kappa calibration
      on_start        — resets _trade_arrival_ts on session open
      on_event        — captures last_trade_price arrivals before forwarding
      _record_mid     — stores logit(mid) so vol is measured in logit space
      _sigma_sq       — falls back to logit-scale default instead of V0 default
      _kappa          — trade-arrival proxy for kappa; explicit static fallback
      _compute_quotes — applies A-S entirely in logit space using _kappa()

    The public ``compute_quotes`` / ``compute_order_requests`` signatures are
    unchanged so existing sweep configs and CLI bridges continue to work.

    Kappa calibration
    -----------------
    True MLE calibration of κ (the A-S fill-decay rate) requires observing
    fill rates at different posted spreads across many sessions — data that
    is not available from a single tape replay.  Instead, V1 counts
    ``last_trade_price`` arrivals in the rolling volatility window and maps
    rate → kappa via a fixed scale factor (_KAPPA_TRADES_PER_SEC_SCALE).

    When fewer than _MIN_TRADES_FOR_KAPPA arrivals are present the constructor
    kappa is returned verbatim (the explicit documented fallback).
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._trade_arrival_ts: deque[float] = deque()
        self.calibration_provenance: Optional[dict] = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def on_start(self, asset_id: str, starting_cash: Decimal) -> None:
        super().on_start(asset_id, starting_cash)
        self._trade_arrival_ts.clear()

    # ------------------------------------------------------------------
    # Trade-arrival capture (kappa calibration input)
    # ------------------------------------------------------------------

    def _record_trade_arrival(self, event: dict, ts_recv: float) -> None:
        """Append ts_recv when event is a last_trade_price; prune old entries."""
        if str(event.get("event_type") or "") != "last_trade_price":
            return
        self._trade_arrival_ts.append(ts_recv)
        cutoff = ts_recv - self.mm_config.vol_window_seconds
        while self._trade_arrival_ts and self._trade_arrival_ts[0] < cutoff:
            self._trade_arrival_ts.popleft()

    def _kappa(self, t_now: float) -> float:
        """Return effective kappa: trade-arrival proxy or constructor fallback.

        Proxy formula (when n >= _MIN_TRADES_FOR_KAPPA)::

            rate  = n / vol_window_seconds          # trades / second
            kappa = clamp(rate × _KAPPA_TRADES_PER_SEC_SCALE,
                          _MIN_KAPPA, _MAX_KAPPA)

        Fallback (when n < _MIN_TRADES_FOR_KAPPA)::

            kappa = self.mm_config.kappa            # static constructor value

        The proxy is ORDINAL only — it is NOT an MLE estimate of the A-S
        fill-decay parameter.  See module-level docstring and constants for
        the explicit statement of what is and is not being calibrated.
        """
        cutoff = t_now - self.mm_config.vol_window_seconds
        while self._trade_arrival_ts and self._trade_arrival_ts[0] < cutoff:
            self._trade_arrival_ts.popleft()

        n = len(self._trade_arrival_ts)
        if n < _MIN_TRADES_FOR_KAPPA:
            return self.mm_config.kappa  # explicit static fallback

        rate = n / self.mm_config.vol_window_seconds
        return _clamp(rate * _KAPPA_TRADES_PER_SEC_SCALE, _MIN_KAPPA, _MAX_KAPPA)

    # ------------------------------------------------------------------
    # Override: capture trade arrivals before forwarding to base class
    # ------------------------------------------------------------------

    def on_event(
        self,
        event: dict,
        seq: int,
        ts_recv: float,
        best_bid: Optional[float],
        best_ask: Optional[float],
        open_orders: dict[str, Any],
    ) -> list[OrderIntent]:
        self._record_trade_arrival(event, ts_recv)
        return super().on_event(event, seq, ts_recv, best_bid, best_ask, open_orders)

    # ------------------------------------------------------------------
    # Overrides: volatility in logit space
    # ------------------------------------------------------------------

    def _record_mid(self, t_now: float, mid: float) -> None:
        """Record clipped logit(mid) for logit-space variance estimation."""
        self._mid_history.append((t_now, _logit(_clip_prob(mid))))
        cutoff = t_now - self.mm_config.vol_window_seconds
        while self._mid_history and self._mid_history[0][0] < cutoff:
            self._mid_history.popleft()

    def _sigma_sq(self, t_now: float) -> float:
        """Variance of logit-space mid changes; falls back to logit default."""
        cutoff = t_now - self.mm_config.vol_window_seconds
        while self._mid_history and self._mid_history[0][0] < cutoff:
            self._mid_history.popleft()

        if len(self._mid_history) < 3:
            return _DEFAULT_SIGMA_SQ_LOGIT

        changes = [
            curr - prev
            for (_, prev), (_, curr) in zip(
                self._mid_history, list(self._mid_history)[1:]
            )
        ]
        if len(changes) < 2:
            return _DEFAULT_SIGMA_SQ_LOGIT
        return float(pvariance(changes))

    # ------------------------------------------------------------------
    # Override: logit-space quote math
    # ------------------------------------------------------------------

    def _compute_quotes(
        self, mid: float, t_elapsed_hours: float, sigma_sq: float
    ) -> tuple[float, float]:
        """A-S reservation price and spread in logit space; convert via sigmoid.

        Steps
        -----
        1. x     = logit(clip(mid))
        2. x_r   = x - q * gamma * sigma_sq * T_remaining
        3. delta  = gamma * sigma_sq * T_remaining
                  + (2/gamma) * ln(1 + gamma/kappa)   [logit-space spread]
        4. Optional resolution-guard widening (applied in logit space).
        5. p_bid = sigmoid(x_r - delta/2)
           p_ask = sigmoid(x_r + delta/2)
        6. Clamp probability-space spread to [min_spread, max_spread].
        7. Hard-clamp to [MIN_BID, MAX_BID] × [MIN_ASK, MAX_ASK].
        """
        remaining_hours = max(
            self.mm_config.session_hours - t_elapsed_hours, _MIN_REMAINING_HOURS
        )
        q = float(self._inventory) / (float(self.order_size) + 1e-9)

        # --- logit-space reservation price ---
        x = _logit(_clip_prob(mid))
        x_r = x - q * self.mm_config.gamma * sigma_sq * remaining_hours

        # --- logit-space spread (A-S formula) ---
        # kappa: trade-arrival proxy when sufficient history exists, else
        # falls back to the static constructor value (see _kappa docstring).
        kappa = self._kappa(self._last_ts_recv or 0.0)
        spread_x = (
            self.mm_config.gamma * sigma_sq * remaining_hours
            + (2.0 / self.mm_config.gamma)
            * math.log(1.0 + (self.mm_config.gamma / kappa))
        )

        # Resolution guard: widen logit spread near tails.
        if mid < self.mm_config.resolution_guard or mid > (
            1.0 - self.mm_config.resolution_guard
        ):
            spread_x *= 2.5

        spread_x *= self.mm_config.spread_multiplier

        # --- convert back to probability space ---
        bid = _sigmoid(x_r - spread_x / 2.0)
        ask = _sigmoid(x_r + spread_x / 2.0)

        # Clamp probability-space spread to configured [min, max].
        prob_spread = ask - bid
        if prob_spread < self.mm_config.min_spread:
            center = (bid + ask) / 2.0
            half = self.mm_config.min_spread / 2.0
            bid = center - half
            ask = center + half
        elif prob_spread > self.mm_config.max_spread:
            center = (bid + ask) / 2.0
            half = self.mm_config.max_spread / 2.0
            bid = center - half
            ask = center + half

        # Hard price bounds.
        bid = _clamp(bid, _MIN_BID_PRICE, _MAX_BID_PRICE)
        ask = _clamp(ask, _MIN_ASK_PRICE, _MAX_ASK_PRICE)
        return round(bid, 3), round(ask, 3)

    # ------------------------------------------------------------------
    # Calibration provenance
    # ------------------------------------------------------------------

    def _build_calibration_provenance(self, t_now: float) -> dict:
        """Snapshot calibration state at *t_now* and return provenance dict.

        Calls ``_sigma_sq`` and ``_kappa`` (which prune their respective
        deques in-place) then reads the post-prune counts to determine
        which path was actually taken.

        Schema::

            {
              "vol_window_seconds": float,
              "sigma": {
                  "source": "rolling_logit_var" | "static_fallback",
                  "sample_count": int,
                  "value": float,
                  "fallback_reason": str | null
              },
              "kappa": {
                  "source": "trade_arrival_proxy" | "static_fallback",
                  "trade_count": int,
                  "value": float,
                  "constructor_kappa": float,
                  "fallback_reason": str | null
              }
            }
        """
        sigma_value = self._sigma_sq(t_now)
        sigma_sample_count = len(self._mid_history)
        if sigma_sample_count >= 3:
            sigma_source = "rolling_logit_var"
            sigma_fallback_reason = None
        else:
            sigma_source = "static_fallback"
            sigma_fallback_reason = f"insufficient_samples({sigma_sample_count}<3)"

        kappa_value = self._kappa(t_now)
        trade_count = len(self._trade_arrival_ts)
        if trade_count >= _MIN_TRADES_FOR_KAPPA:
            kappa_source = "trade_arrival_proxy"
            kappa_fallback_reason = None
        else:
            kappa_source = "static_fallback"
            kappa_fallback_reason = (
                f"insufficient_trades({trade_count}<{_MIN_TRADES_FOR_KAPPA})"
            )

        return {
            "vol_window_seconds": self.mm_config.vol_window_seconds,
            "sigma": {
                "source": sigma_source,
                "sample_count": sigma_sample_count,
                "value": sigma_value,
                "fallback_reason": sigma_fallback_reason,
            },
            "kappa": {
                "source": kappa_source,
                "trade_count": trade_count,
                "value": kappa_value,
                "constructor_kappa": self.mm_config.kappa,
                "fallback_reason": kappa_fallback_reason,
            },
        }

    def on_finish(self) -> None:
        """Snapshot calibration provenance at end of run for artifact emission."""
        t_now = self._last_ts_recv or 0.0
        self.calibration_provenance = self._build_calibration_provenance(t_now)

    # ------------------------------------------------------------------
    # Override: relabel reasons so run artifacts show v1
    # ------------------------------------------------------------------

    def compute_quotes(self, *args: Any, **kwargs: Any):  # type: ignore[override]
        intents = super().compute_quotes(*args, **kwargs)
        for intent in intents:
            if intent.reason:
                intent.reason = intent.reason.replace(
                    "market_maker_v0", "market_maker_v1"
                )
        return intents
