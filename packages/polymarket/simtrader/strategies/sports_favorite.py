"""SportsFavorite: Late Favorite Limit Hold strategy for SimTrader.

Signal logic and default parameters derived from sports strategy research
in evan-kolberg/prediction-market-backtesting.
Reimplemented from scratch for PolyTool SimTrader.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Optional

from packages.polymarket.simtrader.strategy.base import OrderIntent, Strategy


@dataclass(frozen=True)
class FavoriteConfig:
    """Immutable parameters for SportsFavorite."""

    entry_price: float = 0.90
    trade_size: int = 25
    activation_start_time: float = 0.0  # Unix seconds; <= 0 activates immediately
    market_close_time: float = 0.0       # Unix seconds; <= 0 no close cutoff


class SportsFavorite(Strategy):
    """Buy once when midpoint crosses at or above entry_price within the activation window.

    Activation window: [activation_start_time, market_close_time].
    If activation_start_time <= 0, activates immediately.
    If market_close_time <= 0, no upper-bound cutoff.
    No in-strategy profit target, stop loss, or timed exit — position held open
    through strategy lifetime (runner marks to settlement).
    One entry per tape.

    Config keys accepted via --strategy-config-json:
      activation_start_time_ns — activation start Unix nanoseconds (takes priority when > 0)
      market_close_time_ns     — market close Unix nanoseconds (takes priority when > 0)
      activation_start_time    — activation start Unix seconds (fallback)
      market_close_time        — market close Unix seconds (fallback)
      entry_price, trade_size
    """

    def __init__(
        self,
        entry_price: float = 0.90,
        trade_size: int = 25,
        activation_start_time: float = 0.0,
        activation_start_time_ns: float = 0.0,
        market_close_time: float = 0.0,
        market_close_time_ns: float = 0.0,
    ) -> None:
        effective_activation = (
            float(activation_start_time_ns) / 1e9
            if float(activation_start_time_ns) > 0
            else float(activation_start_time)
        )
        effective_close = (
            float(market_close_time_ns) / 1e9
            if float(market_close_time_ns) > 0
            else float(market_close_time)
        )
        self._cfg = FavoriteConfig(
            entry_price=float(entry_price),
            trade_size=int(trade_size),
            activation_start_time=effective_activation,
            market_close_time=effective_close,
        )
        self._entered: bool = False

    def _midpoint(
        self,
        best_bid: Optional[float],
        best_ask: Optional[float],
    ) -> Optional[float]:
        if best_bid is not None and best_ask is not None:
            return (best_bid + best_ask) / 2.0
        return best_ask if best_ask is not None else best_bid

    def on_event(
        self,
        event: dict,
        seq: int,
        ts_recv: float,
        best_bid: Optional[float],
        best_ask: Optional[float],
        open_orders: dict[str, Any],
    ) -> list[OrderIntent]:
        if self._entered:
            return []

        cfg = self._cfg
        price = self._midpoint(best_bid, best_ask)
        if price is None:
            return []

        # Check activation window
        if cfg.activation_start_time > 0 and ts_recv < cfg.activation_start_time:
            return []
        if cfg.market_close_time > 0 and ts_recv > cfg.market_close_time:
            return []

        if price >= cfg.entry_price and best_ask is not None:
            self._entered = True
            return [
                OrderIntent(
                    action="submit",
                    side="BUY",
                    limit_price=Decimal(str(best_ask)),
                    size=Decimal(str(cfg.trade_size)),
                    reason="favorite_entry",
                )
            ]

        return []
