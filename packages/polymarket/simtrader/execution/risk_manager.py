"""Pre-trade and runtime risk guard for the live execution layer.

All limits default to conservative Stage-0 values.  The operator must
explicitly widen them for Stage 1+ capital deployment.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional


@dataclass
class RiskConfig:
    """Conservative defaults suitable for Stage-0 (dry-run only).

    Attributes:
        max_order_notional_usd:    Maximum USD notional for a single order.
        max_position_notional_usd: Maximum USD notional held in any one asset.
        daily_loss_cap_usd:        Maximum cumulative net loss allowed per day.
        max_inventory_units:       Maximum total inventory units across all assets.
        inventory_skew_limit_usd:  Maximum absolute net inventory notional
                                   (sum of units * last_fill_price per asset).
                                   Prevents large directional exposure.
    """

    max_order_notional_usd: Decimal = Decimal("25")
    max_position_notional_usd: Decimal = Decimal("100")
    daily_loss_cap_usd: Decimal = Decimal("15")
    max_inventory_units: Decimal = Decimal("1000")
    inventory_skew_limit_usd: Decimal = Decimal("400")


@dataclass
class _PositionState:
    units: Decimal = Decimal("0")
    notional: Decimal = Decimal("0")


class RiskManager:
    """Enforces pre-trade risk limits and tracks runtime state.

    Usage::

        rm = RiskManager(RiskConfig())
        allowed, reason = rm.check_order(asset_id="abc", side="BUY",
                                         price=Decimal("0.50"), size=Decimal("10"))
        if allowed:
            # submit order
            ...
            rm.on_fill(asset_id="abc", side="BUY",
                       fill_price=Decimal("0.50"), fill_size=Decimal("10"),
                       fee=Decimal("0.01"))
    """

    def __init__(self, config: Optional[RiskConfig] = None) -> None:
        self.config = config or RiskConfig()
        self._positions: dict[str, _PositionState] = {}
        self._total_inventory_units: Decimal = Decimal("0")
        self._daily_realized_pnl: Decimal = Decimal("0")
        self._total_fees_paid: Decimal = Decimal("0")
        self._halt_reason: Optional[str] = None
        self._last_fill_price: dict[str, Decimal] = {}

    # ------------------------------------------------------------------
    # Pre-trade gate
    # ------------------------------------------------------------------

    def check_order(
        self,
        asset_id: str,
        side: str,
        price: Decimal,
        size: Decimal,
    ) -> tuple[bool, str]:
        """Validate a proposed order against all risk limits.

        Args:
            asset_id: Token identifier.
            side:     "BUY" or "SELL".
            price:    Limit price (Decimal).
            size:     Order size in units (Decimal).

        Returns:
            (allowed, reason) — reason is empty string when allowed=True.
        """
        halted, halt_reason = self.should_halt()
        if halted:
            return False, halt_reason

        if price <= 0:
            return False, f"risk: price must be > 0, got {price}"
        if size <= 0:
            return False, f"risk: size must be > 0, got {size}"

        notional = price * size

        # 1. Per-order notional cap
        if notional > self.config.max_order_notional_usd:
            return (
                False,
                f"risk: order notional {notional} exceeds max_order_notional_usd "
                f"{self.config.max_order_notional_usd}",
            )

        # 2. Projected position notional cap (BUY increases exposure)
        if side.upper() == "BUY":
            pos = self._positions.get(asset_id, _PositionState())
            projected_notional = pos.notional + notional
            if projected_notional > self.config.max_position_notional_usd:
                return (
                    False,
                    f"risk: projected position notional {projected_notional} for "
                    f"asset {asset_id!r} exceeds max_position_notional_usd "
                    f"{self.config.max_position_notional_usd}",
                )

        # 3. Inventory units cap
        projected_inventory = self._total_inventory_units + size
        if projected_inventory > self.config.max_inventory_units:
            return (
                False,
                f"risk: projected total inventory {projected_inventory} exceeds "
                f"max_inventory_units {self.config.max_inventory_units}",
            )

        # 4. Inventory skew limit
        skew = abs(self.net_inventory_notional)
        if skew > self.config.inventory_skew_limit_usd:
            return (
                False,
                f"risk: inventory_skew_limit",
            )

        return True, ""

    # ------------------------------------------------------------------
    # Computed properties
    # ------------------------------------------------------------------

    @property
    def net_inventory_notional(self) -> Decimal:
        """Sum of (position.units * last_fill_price) across all tracked assets.

        Returns a signed value: positive means net long, negative means net
        short.  Assets with no recorded fill price are excluded.
        """
        total = Decimal("0")
        for asset_id, pos in self._positions.items():
            price = self._last_fill_price.get(asset_id)
            if price is not None:
                total += pos.units * price
        return total

    # ------------------------------------------------------------------
    # Runtime state update
    # ------------------------------------------------------------------

    def on_fill(
        self,
        asset_id: str,
        side: str,
        fill_price: Decimal,
        fill_size: Decimal,
        fee: Decimal = Decimal("0"),
    ) -> None:
        """Update internal state after a confirmed fill.

        Args:
            asset_id:   Token identifier.
            side:       "BUY" or "SELL".
            fill_price: Actual fill price.
            fill_size:  Size filled.
            fee:        Fee paid on this fill (positive value).
        """
        notional = fill_price * fill_size

        if asset_id not in self._positions:
            self._positions[asset_id] = _PositionState()
        pos = self._positions[asset_id]
        self._last_fill_price[asset_id] = fill_price

        if side.upper() == "BUY":
            pos.units += fill_size
            pos.notional += notional
            self._total_inventory_units += fill_size
        else:  # SELL
            pos.units -= fill_size
            pos.notional -= notional
            self._total_inventory_units -= fill_size
            # Realise PnL approximation: revenue minus cost basis proportional
            self._daily_realized_pnl += notional

        self._total_fees_paid += fee

        # Check halt after update
        self.should_halt()

    # ------------------------------------------------------------------
    # Halt check
    # ------------------------------------------------------------------

    def should_halt(self) -> tuple[bool, str]:
        """Return (True, reason) if any runtime limit has been breached.

        Once triggered, subsequent calls return the same halt reason even
        if the condition is transiently cleared (conservative policy).
        """
        if self._halt_reason is not None:
            return True, self._halt_reason

        # Daily loss cap: fees are a guaranteed loss
        net_loss = self._total_fees_paid - self._daily_realized_pnl
        if net_loss > self.config.daily_loss_cap_usd:
            self._halt_reason = (
                f"risk: daily net loss {net_loss} exceeds "
                f"daily_loss_cap_usd {self.config.daily_loss_cap_usd}"
            )
            return True, self._halt_reason

        return False, ""
