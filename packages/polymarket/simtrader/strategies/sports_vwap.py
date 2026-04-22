"""SportsVWAP: VWAP Reversion strategy for SimTrader.

Signal logic and default parameters derived from sports strategy research
in evan-kolberg/prediction-market-backtesting.
Reimplemented from scratch for PolyTool SimTrader.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Optional

from packages.polymarket.simtrader.strategy.base import OrderIntent, Strategy


@dataclass(frozen=True)
class VWAPConfig:
    """Immutable parameters for SportsVWAP."""

    trade_size: int = 1
    vwap_window: int = 80
    entry_threshold: float = 0.008
    exit_threshold: float = 0.002
    min_tick_size: float = 0.0   # minimum accepted trade size; ticks with size < this are ignored
    take_profit: float = 0.015
    stop_loss: float = 0.02


class SportsVWAP(Strategy):
    """Enter long when price falls sufficiently below rolling VWAP; exit on reversion or limit.

    Accumulates last_trade_price events into a rolling window of (price, size).
    Becomes eligible only after vwap_window observations with positive total size.
    Ticks with accepted trade size below min_tick_size are ignored.

    Entry: current_price < vwap - entry_threshold.
    Exit priority:
        1. Absolute take_profit offset above fill: current_price >= fill + take_profit.
        2. Absolute stop_loss offset below fill: current_price <= fill - stop_loss.
        3. VWAP reversion: current_price >= vwap - exit_threshold.
    """

    def __init__(
        self,
        trade_size: int = 1,
        vwap_window: int = 80,
        entry_threshold: float = 0.008,
        exit_threshold: float = 0.002,
        min_tick_size: float = 0.0,
        take_profit: float = 0.015,
        stop_loss: float = 0.02,
    ) -> None:
        self._cfg = VWAPConfig(
            trade_size=int(trade_size),
            vwap_window=int(vwap_window),
            entry_threshold=float(entry_threshold),
            exit_threshold=float(exit_threshold),
            min_tick_size=float(min_tick_size),
            take_profit=float(take_profit),
            stop_loss=float(stop_loss),
        )
        self._window: deque[tuple[float, float]] = deque(maxlen=self._cfg.vwap_window)
        self._last_price: Optional[float] = None
        self._entry_pending: bool = False
        self._fill_price: Optional[float] = None
        self._done: bool = False

    def _compute_vwap(self) -> Optional[float]:
        if not self._window:
            return None
        total_size = sum(s for _, s in self._window)
        if total_size <= 0.0:
            return None
        return sum(p * s for p, s in self._window) / total_size

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

        # Absorb last_trade_price events into the VWAP window
        if event.get("event_type") == "last_trade_price":
            raw_price = event.get("price")
            if raw_price is not None:
                tick_price = float(raw_price)
                raw_size = event.get("size")
                tick_size = float(raw_size) if raw_size is not None else 1.0
                if tick_size >= cfg.min_tick_size:
                    self._window.append((tick_price, tick_size))
                    self._last_price = tick_price

        price = self._last_price
        if price is None:
            return []

        vwap = self._compute_vwap()
        if vwap is None or len(self._window) < cfg.vwap_window:
            return []

        intents: list[OrderIntent] = []

        if self._fill_price is not None:
            fp = self._fill_price
            take_profit_hit = price >= fp + cfg.take_profit
            stop_loss_hit = price <= fp - cfg.stop_loss
            vwap_reversion = price >= vwap - cfg.exit_threshold

            if take_profit_hit or stop_loss_hit or vwap_reversion:
                exit_lp = (
                    Decimal(str(best_bid)) if best_bid is not None
                    else Decimal(str(price))
                )
                if take_profit_hit:
                    exit_reason = "vwap_take_profit"
                elif stop_loss_hit:
                    exit_reason = "vwap_stop_loss"
                else:
                    exit_reason = "vwap_reversion"
                intents.append(
                    OrderIntent(
                        action="submit",
                        side="SELL",
                        limit_price=exit_lp,
                        size=Decimal(str(cfg.trade_size)),
                        reason=exit_reason,
                    )
                )
                self._done = True

        elif not self._entry_pending:
            if price < vwap - cfg.entry_threshold and best_ask is not None:
                intents.append(
                    OrderIntent(
                        action="submit",
                        side="BUY",
                        limit_price=Decimal(str(best_ask)),
                        size=Decimal(str(cfg.trade_size)),
                        reason="vwap_entry",
                    )
                )
                self._entry_pending = True

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
            self._fill_price = float(fill_price)
            self._entry_pending = False
