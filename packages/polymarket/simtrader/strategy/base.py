"""Strategy interface for SimTrader.

A Strategy is called at each tape event during replay and returns a list of
OrderIntents that the StrategyRunner routes to the SimBroker.

Lifecycle
---------
  on_start  — called once before the replay loop; use for initialisation
  on_event  — called for every tape event; return intents to act on
  on_finish — called once after the last event; use for teardown / logging
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Optional


@dataclass
class OrderIntent:
    """An instruction from a Strategy to the StrategyRunner.

    The runner executes each intent by calling SimBroker.submit_order or
    SimBroker.cancel_order at the current tape seq / ts_recv.

    For ``action="submit"`` the fields *side*, *limit_price*, and *size* are
    required.  *asset_id* may be omitted when the tape has exactly one asset;
    the runner fills it in automatically.

    For ``action="cancel"`` only *order_id* is required.

    The optional *reason* and *meta* fields are written verbatim to
    ``decisions.jsonl`` for post-hoc analysis.
    """

    action: str  # "submit" | "cancel"

    # submit fields
    asset_id: Optional[str] = None
    side: Optional[str] = None        # "BUY" | "SELL"
    limit_price: Optional[Decimal] = None
    size: Optional[Decimal] = None

    # cancel fields
    order_id: Optional[str] = None    # required when action="cancel"

    # audit / logging
    reason: Optional[str] = None      # human-readable rationale → decisions.jsonl
    meta: dict[str, Any] = field(default_factory=dict)


class Strategy:
    """Base class for all SimTrader strategies.

    Subclass this and override the three lifecycle methods.  Default
    implementations are no-ops so you only override what you need.
    """

    def on_start(self, asset_id: str, starting_cash: Decimal) -> None:
        """Called once before the replay loop begins.

        Args:
            asset_id:      The primary asset being replayed.
            starting_cash: Initial portfolio cash in USDC (Decimal).
        """

    def on_event(
        self,
        event: dict,
        seq: int,
        ts_recv: float,
        best_bid: Optional[float],
        best_ask: Optional[float],
        open_orders: dict[str, Any],
    ) -> list[OrderIntent]:
        """Called for every tape event, after book.apply and before broker.step.

        Args:
            event:       Raw normalised tape event dict.
            seq:         Tape sequence number for this event.
            ts_recv:     Receive timestamp (Unix seconds, float).
            best_bid:    Current best bid price or None if book is empty.
            best_ask:    Current best ask price or None if book is empty.
            open_orders: Currently open (non-terminal) orders keyed by
                         order_id.  Each value is a plain dict with at
                         minimum the fields:
                           order_id, side, asset_id, limit_price (str),
                           size (str), status, filled_size (str).

        Returns:
            List of OrderIntents to execute at this seq.  May be empty.
        """
        return []

    def on_finish(self) -> None:
        """Called once after the last tape event has been processed."""
