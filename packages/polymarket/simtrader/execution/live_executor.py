"""Live order executor for the execution layer.

LiveExecutor wraps a CLOB client with kill-switch and rate-limiter guards.
In dry-run mode (default) it never calls the underlying client.

The minimal CLOB client interface expected is::

    client.place_order(asset_id, side, price, size, post_only) -> dict
    client.cancel_order(order_id) -> dict

Both should return a dict with at minimum {"status": "ok"|"error", ...}.
Any object with these two methods is accepted (duck-typed).

When a ``real_client`` (py_clob_client ``ClobClient``) is supplied and
``dry_run=False``, the executor calls the Polymarket CLOB REST API directly::

    real_client.create_order(...)  -> dict
    real_client.cancel(order_id)   -> dict
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Optional

from packages.polymarket.simtrader.execution.kill_switch import KillSwitch
from packages.polymarket.simtrader.execution.rate_limiter import TokenBucketRateLimiter


@dataclass
class OrderRequest:
    """A request to place a limit order.

    Attributes:
        asset_id:  Token identifier.
        side:      "BUY" or "SELL".
        price:     Limit price (Decimal).
        size:      Order size in units (Decimal).
        post_only: If True, reject if order would cross (maker-only).
        meta:      Arbitrary metadata for audit logging.
    """

    asset_id: str
    side: str
    price: Decimal
    size: Decimal
    post_only: bool = True
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass
class OrderResult:
    """Result of a place-order or cancel-order attempt.

    Attributes:
        submitted:    True iff the order was actually sent to the exchange.
        dry_run:      True iff the result was produced in dry-run mode.
        reason:       Human-readable explanation when submitted=False.
        raw_response: Raw dict returned by the CLOB client (if called).
    """

    submitted: bool
    dry_run: bool = False
    reason: str = ""
    raw_response: Optional[dict] = None


class LiveExecutor:
    """Executes order requests against a CLOB client with safety guards.

    Args:
        clob_client:  Object implementing ``place_order`` / ``cancel_order``
                      (duck-typed simulation interface).
        rate_limiter: TokenBucketRateLimiter instance.
        kill_switch:  KillSwitch instance.
        dry_run:      When True, never call any CLOB client.
        real_client:  Optional py_clob_client ``ClobClient``.  When supplied
                      and ``dry_run=False``, live orders are sent via
                      ``real_client.create_order`` / ``real_client.cancel``
                      instead of the duck-typed ``clob_client`` interface.
    """

    def __init__(
        self,
        clob_client: Any,
        rate_limiter: TokenBucketRateLimiter,
        kill_switch: KillSwitch,
        dry_run: bool = True,
        real_client: Optional[Any] = None,
    ) -> None:
        self._client = clob_client
        self._limiter = rate_limiter
        self._ks = kill_switch
        self.dry_run = dry_run
        self._real_client = real_client

    def place_order(self, request: OrderRequest) -> OrderResult:
        """Place a limit order.

        Always checks the kill switch first.  In dry-run mode returns an
        OrderResult with submitted=False and dry_run=True without touching
        the client.  Otherwise, acquires a rate-limiter token and calls
        ``client.place_order``.

        Raises:
            RuntimeError: If the kill switch is active.
        """
        # Kill switch is always checked — even in dry-run.
        self._ks.check_or_raise()

        if self.dry_run:
            return OrderResult(submitted=False, dry_run=True, reason="dry_run")

        # Acquire rate-limit token before calling the client.
        self._limiter.acquire(1)

        if self._real_client is not None:
            raw = self._real_client.create_order(
                request.asset_id,
                request.side,
                request.price,
                request.size,
                request.post_only,
            )
        else:
            raw = self._client.place_order(
                request.asset_id,
                request.side,
                request.price,
                request.size,
                request.post_only,
            )
        return OrderResult(submitted=True, dry_run=False, raw_response=raw)

    def cancel_order(self, order_id: str) -> OrderResult:
        """Cancel an open order.

        Always checks the kill switch first.  In dry-run mode returns without
        calling the client.

        Raises:
            RuntimeError: If the kill switch is active.
        """
        self._ks.check_or_raise()

        if self.dry_run:
            return OrderResult(submitted=False, dry_run=True, reason="dry_run")

        self._limiter.acquire(1)
        if self._real_client is not None:
            raw = self._real_client.cancel(order_id)
        else:
            raw = self._client.cancel_order(order_id)
        return OrderResult(submitted=True, dry_run=False, raw_response=raw)
