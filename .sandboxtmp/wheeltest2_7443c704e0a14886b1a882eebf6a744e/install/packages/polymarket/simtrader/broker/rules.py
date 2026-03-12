"""Order and fill data types for SimTrader broker simulation.

All monetary values use Decimal to prevent floating-point drift.
Serialisation helpers produce JSON-safe dicts with string-encoded Decimals.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Optional


class OrderStatus:
    """Order lifecycle states (string constants)."""

    PENDING = "pending"      # submitted; effective_seq not yet reached
    ACTIVE = "active"        # effective; waiting for a fill opportunity
    PARTIAL = "partial"      # partially filled; still seeking more size
    FILLED = "filled"        # fully filled; terminal
    CANCELLED = "cancelled"  # cancelled; terminal
    REJECTED = "rejected"    # rejected at submission time; terminal

    _TERMINAL = frozenset({FILLED, CANCELLED, REJECTED})

    @classmethod
    def is_terminal(cls, status: str) -> bool:
        return status in cls._TERMINAL


class Side:
    """Order sides."""

    BUY = "BUY"
    SELL = "SELL"


@dataclass
class Order:
    """A single simulated order tracked by the broker.

    Prices and sizes are Decimal for precision.  String coercion happens
    only at serialisation time.
    """

    order_id: str
    asset_id: str
    side: str
    limit_price: Decimal
    size: Decimal
    submit_seq: int
    effective_seq: int
    cancel_effective_seq: Optional[int] = None
    status: str = OrderStatus.PENDING
    filled_size: Decimal = field(default_factory=lambda: Decimal("0"))

    @property
    def remaining(self) -> Decimal:
        """Size still to be filled."""
        return self.size - self.filled_size

    @property
    def is_active(self) -> bool:
        """True if the order is in a state where fills can occur."""
        return self.status in (OrderStatus.ACTIVE, OrderStatus.PARTIAL)


@dataclass
class FillRecord:
    """Result of one fill evaluation against the book.

    The ``because`` dict records the exact book state used to make the
    fill decision, providing a complete audit trail:

    .. code-block:: python

        {
            "eval_seq":          int,               # tape seq at fill time
            "book_best_bid":     float | None,
            "book_best_ask":     float | None,
            "levels_consumed":   [{"price": str, "size": str}, ...],
        }
    """

    order_id: str
    asset_id: str
    seq: int
    ts_recv: float
    side: str
    fill_price: Decimal       # weighted average across all levels consumed
    fill_size: Decimal        # total size filled in this evaluation
    remaining: Decimal        # order size remaining after this fill
    fill_status: str          # "full" | "partial" | "rejected"
    reject_reason: Optional[str]
    because: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-safe dict (Decimals serialised as strings)."""
        return {
            "order_id": self.order_id,
            "asset_id": self.asset_id,
            "seq": self.seq,
            "ts_recv": self.ts_recv,
            "side": self.side,
            "fill_price": str(self.fill_price),
            "fill_size": str(self.fill_size),
            "remaining": str(self.remaining),
            "fill_status": self.fill_status,
            "reject_reason": self.reject_reason,
            "because": self.because,
        }
