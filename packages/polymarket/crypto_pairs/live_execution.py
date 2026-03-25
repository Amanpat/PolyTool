"""Live execution scaffold for crypto-pair runner v0."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Optional, Protocol

from packages.polymarket.simtrader.execution.kill_switch import KillSwitch


LIMIT_ORDER_TYPE = "limit"


class CryptoPairLiveExecutionError(RuntimeError):
    """Raised when the live execution scaffold rejects an unsafe request."""


@dataclass(frozen=True)
class LiveOrderRequest:
    """Limit-only, post-only order request."""

    market_id: str
    token_id: str
    side: str
    price: Decimal
    size: Decimal
    order_type: str = LIMIT_ORDER_TYPE
    post_only: bool = True
    meta: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if str(self.order_type).strip().lower() != LIMIT_ORDER_TYPE:
            raise CryptoPairLiveExecutionError(
                "market-order path is not implemented; live scaffold only supports limit orders"
            )
        if self.post_only is not True:
            raise CryptoPairLiveExecutionError(
                "live scaffold requires post_only=True for every order"
            )
        if self.price <= 0:
            raise CryptoPairLiveExecutionError("price must be > 0")
        if self.size <= 0:
            raise CryptoPairLiveExecutionError("size must be > 0")


@dataclass(frozen=True)
class WorkingOrder:
    """Tracked working order entry used for cancel-on-disconnect handling."""

    order_id: str
    market_id: str
    token_id: str
    side: str
    price: Decimal
    size: Decimal


@dataclass(frozen=True)
class LiveOrderResult:
    """Result of a live-scaffold place/cancel attempt."""

    accepted: bool
    submitted: bool
    action: str
    reason: str = ""
    order_id: Optional[str] = None
    raw_response: Optional[dict[str, Any]] = None


class CryptoPairOrderClient(Protocol):
    """Future order-client contract for the real execution path."""

    def place_limit_order(self, request: LiveOrderRequest) -> dict[str, Any]: ...

    def cancel_order(self, order_id: str) -> dict[str, Any]: ...


class CryptoPairLiveExecutionAdapter:
    """Execution adapter with explicit safety boundaries.

    The scaffold can run with ``order_client=None``. In that case it validates
    requests and records operator-visible reasons, but it does not submit
    anything to a venue.
    """

    def __init__(
        self,
        *,
        kill_switch: KillSwitch,
        order_client: Optional[CryptoPairOrderClient] = None,
        live_enabled: bool = False,
    ) -> None:
        self._kill_switch = kill_switch
        self._order_client = order_client
        self.live_enabled = bool(live_enabled)
        self._working_orders: dict[str, WorkingOrder] = {}

    def working_orders(self) -> list[WorkingOrder]:
        return list(self._working_orders.values())

    def place_order(self, request: LiveOrderRequest) -> LiveOrderResult:
        self._kill_switch.check_or_raise()

        if not self.live_enabled:
            return LiveOrderResult(
                accepted=False,
                submitted=False,
                action="place_order",
                reason="live_mode_disabled",
            )

        if self._order_client is None:
            return LiveOrderResult(
                accepted=False,
                submitted=False,
                action="place_order",
                reason="live_client_unconfigured",
            )

        raw = self._order_client.place_limit_order(request)
        order_id = str(raw.get("order_id") or raw.get("id") or "").strip() or None
        if order_id is not None:
            self._working_orders[order_id] = WorkingOrder(
                order_id=order_id,
                market_id=request.market_id,
                token_id=request.token_id,
                side=request.side,
                price=request.price,
                size=request.size,
            )
        return LiveOrderResult(
            accepted=True,
            submitted=True,
            action="place_order",
            order_id=order_id,
            raw_response=raw,
        )

    def cancel_order(self, order_id: str) -> LiveOrderResult:
        order_id_text = str(order_id).strip()
        self._working_orders.pop(order_id_text, None)

        if not self.live_enabled:
            return LiveOrderResult(
                accepted=False,
                submitted=False,
                action="cancel_order",
                reason="live_mode_disabled",
                order_id=order_id_text or None,
            )

        if self._order_client is None:
            return LiveOrderResult(
                accepted=False,
                submitted=False,
                action="cancel_order",
                reason="live_client_unconfigured",
                order_id=order_id_text or None,
            )

        raw = self._order_client.cancel_order(order_id_text)
        return LiveOrderResult(
            accepted=True,
            submitted=True,
            action="cancel_order",
            order_id=order_id_text or None,
            raw_response=raw,
        )

    def cancel_all_working_orders(self) -> list[LiveOrderResult]:
        results: list[LiveOrderResult] = []
        for working_order in list(self._working_orders.values()):
            results.append(self.cancel_order(working_order.order_id))
        return results
