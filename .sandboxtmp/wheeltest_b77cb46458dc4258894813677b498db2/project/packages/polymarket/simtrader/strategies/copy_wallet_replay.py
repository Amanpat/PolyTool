"""CopyWalletReplay strategy: mirror a target wallet's trades with a signal delay.

Input fixture format
--------------------
JSONL file, one trade per line::

    {"seq": 42, "side": "BUY", "limit_price": "0.45", "size": "100"}

Optional per-line fields:

    "asset_id"  — override the tape's primary asset for this trade
    "trade_id"  — arbitrary identifier string for logging / analysis

Behaviour
---------
For each target trade the strategy submits an order at the first tape event
where::

    current_seq >= trade.seq + signal_delay_ticks

With ``signal_delay_ticks=0`` (the default) the order is submitted at the same
seq as the target trade; with ``signal_delay_ticks=2`` it is delayed by two
book-state updates.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any, Optional

from ..strategy.base import OrderIntent, Strategy

logger = logging.getLogger(__name__)


@dataclass
class TargetTrade:
    """A single target trade loaded from the fixture file."""

    seq: int
    side: str            # "BUY" | "SELL"
    limit_price: Decimal
    size: Decimal
    asset_id: Optional[str] = None  # None → use the tape's primary asset
    trade_id: str = ""


class CopyWalletReplay(Strategy):
    """Replicate a recorded wallet's trades, optionally with a signal delay.

    Args:
        trades_path:         Path to the JSONL fixture file of target trades.
        signal_delay_ticks:  Number of tape events to wait after ``trade.seq``
                             before submitting (default: 0 = act immediately).
    """

    def __init__(
        self,
        trades_path: str | Path,
        signal_delay_ticks: int = 0,
    ) -> None:
        self._trades_path = Path(trades_path)
        self._signal_delay_ticks = signal_delay_ticks
        self._trades: list[TargetTrade] = []
        self._submitted: set[int] = set()  # indices into self._trades
        self._default_asset_id: str = ""

    # ------------------------------------------------------------------
    # Strategy lifecycle
    # ------------------------------------------------------------------

    def on_start(self, asset_id: str, starting_cash: Decimal) -> None:
        self._default_asset_id = asset_id
        self._trades = self._load_trades()
        self._submitted = set()
        logger.info(
            "CopyWalletReplay: loaded %d trades from %s  delay=%d ticks",
            len(self._trades),
            self._trades_path,
            self._signal_delay_ticks,
        )

    def on_event(
        self,
        event: dict,
        seq: int,
        ts_recv: float,
        best_bid: Optional[float],
        best_ask: Optional[float],
        open_orders: dict[str, Any],
    ) -> list[OrderIntent]:
        intents: list[OrderIntent] = []
        for i, trade in enumerate(self._trades):
            if i in self._submitted:
                continue
            trigger_seq = trade.seq + self._signal_delay_ticks
            if seq >= trigger_seq:
                intents.append(
                    OrderIntent(
                        action="submit",
                        asset_id=trade.asset_id or self._default_asset_id,
                        side=trade.side,
                        limit_price=trade.limit_price,
                        size=trade.size,
                        reason=(
                            f"copy trade_id={trade.trade_id!r} "
                            f"original_seq={trade.seq} "
                            f"delay={self._signal_delay_ticks}"
                        ),
                        meta={
                            "original_seq": trade.seq,
                            "trade_id": trade.trade_id,
                            "trigger_seq": trigger_seq,
                        },
                    )
                )
                self._submitted.add(i)
        return intents

    def on_finish(self) -> None:
        not_submitted = len(self._trades) - len(self._submitted)
        if not_submitted:
            logger.warning(
                "CopyWalletReplay: %d trade(s) were never triggered "
                "(tape ended before their trigger_seq).",
                not_submitted,
            )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load_trades(self) -> list[TargetTrade]:
        trades: list[TargetTrade] = []
        with open(self._trades_path, encoding="utf-8") as fh:
            for lineno, line in enumerate(fh, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    t = json.loads(line)
                except json.JSONDecodeError as exc:
                    logger.warning(
                        "Skipping malformed line %d in %s: %s",
                        lineno,
                        self._trades_path,
                        exc,
                    )
                    continue
                try:
                    trades.append(
                        TargetTrade(
                            seq=int(t["seq"]),
                            side=str(t["side"]).upper(),
                            limit_price=Decimal(str(t["limit_price"])),
                            size=Decimal(str(t["size"])),
                            asset_id=t.get("asset_id"),
                            trade_id=str(t.get("trade_id", "")),
                        )
                    )
                except (KeyError, ValueError) as exc:
                    logger.warning(
                        "Skipping invalid trade at line %d in %s: %s",
                        lineno,
                        self._trades_path,
                        exc,
                    )
        return trades
