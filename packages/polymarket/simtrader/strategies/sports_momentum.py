"""SportsMomentum: Final Period Momentum strategy for SimTrader.

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
class MomentumConfig:
    """Immutable parameters for SportsMomentum."""

    market_close_time: float = 0.0       # Unix seconds; <= 0 disables activation
    final_period_minutes: float = 30.0
    entry_price: float = 0.80
    take_profit_price: float = 0.92
    stop_loss_price: float = 0.50
    trade_size: int = 100


class SportsMomentum(Strategy):
    """Buy on a below-to-above price crossing within the final period window.

    Activates when ts_recv enters the window [close - window_secs, close].
    Entry requires the midpoint price to cross above entry_price from below.
    Exits at take_profit_price, stop_loss_price, or at market close. One entry per tape.

    Config keys accepted via --strategy-config-json:
      market_close_time_ns  — market close Unix nanoseconds (takes priority when > 0)
      market_close_time     — market close Unix seconds (fallback)
      final_period_minutes  — width of entry window in minutes
      entry_price, take_profit_price, stop_loss_price, trade_size
    """

    def __init__(
        self,
        market_close_time: float = 0.0,
        market_close_time_ns: float = 0.0,
        final_period_minutes: float = 30.0,
        entry_price: float = 0.80,
        take_profit_price: float = 0.92,
        stop_loss_price: float = 0.50,
        trade_size: int = 100,
    ) -> None:
        effective_close = (
            float(market_close_time_ns) / 1e9
            if float(market_close_time_ns) > 0
            else float(market_close_time)
        )
        self._cfg = MomentumConfig(
            market_close_time=effective_close,
            final_period_minutes=float(final_period_minutes),
            entry_price=float(entry_price),
            take_profit_price=float(take_profit_price),
            stop_loss_price=float(stop_loss_price),
            trade_size=int(trade_size),
        )
        self._prev_price: Optional[float] = None
        self._entry_pending: bool = False
        self._fill_price: Optional[Decimal] = None
        self._done: bool = False

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
        if self._done:
            return []

        cfg = self._cfg
        price = self._midpoint(best_bid, best_ask)
        if price is None:
            return []

        intents: list[OrderIntent] = []

        if self._fill_price is not None:
            # In position — check exit conditions
            at_close = cfg.market_close_time > 0 and ts_recv >= cfg.market_close_time
            if (
                price >= cfg.take_profit_price
                or price <= cfg.stop_loss_price
                or at_close
            ):
                exit_lp = (
                    Decimal(str(best_bid)) if best_bid is not None else self._fill_price
                )
                intents.append(
                    OrderIntent(
                        action="submit",
                        side="SELL",
                        limit_price=exit_lp,
                        size=Decimal(str(cfg.trade_size)),
                        reason="momentum_exit",
                    )
                )
                self._done = True
        elif not self._entry_pending:
            # Not in position and no pending order — check entry signal
            if cfg.market_close_time <= 0:
                self._prev_price = price
                return []

            window_start = cfg.market_close_time - cfg.final_period_minutes * 60.0
            in_window = window_start <= ts_recv <= cfg.market_close_time

            if (
                in_window
                and self._prev_price is not None
                and self._prev_price < cfg.entry_price <= price
                and best_ask is not None
            ):
                intents.append(
                    OrderIntent(
                        action="submit",
                        side="BUY",
                        limit_price=Decimal(str(best_ask)),
                        size=Decimal(str(cfg.trade_size)),
                        reason="momentum_entry",
                    )
                )
                self._entry_pending = True

        self._prev_price = price
        return intents

    def on_fill(
        self,
        order_id: str,
        asset_id: str,
        side: str,
        fill_price: Decimal,
        fill_size: Decimal,
        fill_status: str,
        seq: int,
        ts_recv: float,
    ) -> None:
        if side == "BUY" and self._entry_pending and self._fill_price is None:
            self._fill_price = fill_price
            self._entry_pending = False
