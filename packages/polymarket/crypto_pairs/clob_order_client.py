"""Real Polymarket CLOB order client implementing CryptoPairOrderClient Protocol.

This module is the ONLY file that imports py-clob-client. All other crypto-pair
code interacts through the CryptoPairOrderClient Protocol defined in live_execution.py.
This isolation means paper mode, backtest, and all tests never need py-clob-client installed.

Environment variables required:
    PK                  — Hex private key for the HOT WALLET (no 0x prefix)
    CLOB_API_KEY        — CLOB API key
    CLOB_API_SECRET     — CLOB API secret
    CLOB_API_PASSPHRASE — CLOB API passphrase
    CLOB_API_BASE       — CLOB API base URL (default: https://clob.polymarket.com)
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


_REQUIRED_ENV_VARS = ("PK", "CLOB_API_KEY", "CLOB_API_SECRET", "CLOB_API_PASSPHRASE")


class ClobOrderClientConfigError(ValueError):
    """Raised when required env vars are missing."""


@dataclass(frozen=True)
class ClobOrderClientConfig:
    """Configuration for the live CLOB order client.

    All fields populated from environment variables. Never pass real secrets
    as constructor arguments in code — always use ``from_env()``.
    """

    private_key: str
    api_key: str
    api_secret: str
    api_passphrase: str
    clob_api_base: str = "https://clob.polymarket.com"

    @classmethod
    def from_env(cls) -> "ClobOrderClientConfig":
        """Load configuration from environment variables.

        Raises:
            ClobOrderClientConfigError: If any required env var is missing or empty.
        """
        missing = [k for k in _REQUIRED_ENV_VARS if not os.environ.get(k, "").strip()]
        if missing:
            raise ClobOrderClientConfigError(
                f"Live CLOB client requires env vars: {', '.join(missing)}"
            )
        return cls(
            private_key=os.environ["PK"].strip(),
            api_key=os.environ["CLOB_API_KEY"].strip(),
            api_secret=os.environ["CLOB_API_SECRET"].strip(),
            api_passphrase=os.environ["CLOB_API_PASSPHRASE"].strip(),
            clob_api_base=os.environ.get("CLOB_API_BASE", "https://clob.polymarket.com").strip(),
        )


class PolymarketClobOrderClient:
    """CryptoPairOrderClient Protocol implementation backed by py-clob-client.

    Import of py-clob-client is deferred inside _build_client so the rest of
    the package does not hard-depend on the library. Paper mode, backtest, and
    all offline tests never trigger the deferred import.
    """

    def __init__(self, config: ClobOrderClientConfig) -> None:
        self._config = config
        self._client = self._build_client(config)
        logger.info(
            "PolymarketClobOrderClient initialized (clob_api_base=%s)",
            config.clob_api_base,
        )

    @staticmethod
    def _build_client(config: ClobOrderClientConfig) -> Any:
        """Construct and return a configured py-clob-client ClobClient."""
        from py_clob_client.client import ClobClient  # deferred import
        from py_clob_client.clob_types import ApiCreds

        creds = ApiCreds(
            api_key=config.api_key,
            api_secret=config.api_secret,
            api_passphrase=config.api_passphrase,
        )
        return ClobClient(
            host=config.clob_api_base,
            key=config.private_key,
            chain_id=137,  # Polygon mainnet
            creds=creds,
        )

    def place_limit_order(self, request: Any) -> dict[str, Any]:
        """Submit a GTC limit order via the Polymarket CLOB.

        Args:
            request: A LiveOrderRequest (or any object with token_id, price, size, side).

        Returns:
            Response dict from the CLOB API. May contain ``order_id`` / ``id`` on success.
            On error, returns ``{"error": "<message>", "order_id": None}``.
        """
        from py_clob_client.clob_types import OrderArgs, OrderType  # deferred import

        order_args = OrderArgs(
            token_id=request.token_id,
            price=float(request.price),
            size=float(request.size),
            side=str(request.side).strip().upper(),
        )

        logger.info(
            "Placing limit order: token=%s side=%s price=%.4f size=%.2f",
            str(request.token_id)[:20],
            request.side,
            float(request.price),
            float(request.size),
        )

        try:
            signed_order = self._client.create_order(order_args)
            resp = self._client.post_order(signed_order, OrderType.GTC)
            result = dict(resp) if not isinstance(resp, dict) else resp
            order_id = (
                result.get("order_id")
                or result.get("orderID")
                or result.get("id")
                or ""
            )
            logger.info(
                "Order placed successfully: order_id=%s",
                str(order_id)[:20] if order_id else "unknown",
            )
            return result
        except Exception as exc:
            logger.error("Order placement failed: %s", exc)
            return {"error": str(exc), "order_id": None}

    def cancel_order(self, order_id: str) -> dict[str, Any]:
        """Cancel a working order by order_id.

        Returns:
            Response dict from the CLOB API.
            On error, returns ``{"error": "<message>"}``.
        """
        order_id_text = str(order_id).strip()
        logger.info("Cancelling order: %s", order_id_text[:20])
        try:
            resp = self._client.cancel(order_id_text)
            return dict(resp) if not isinstance(resp, dict) else resp
        except Exception as exc:
            logger.error("Cancel failed for %s: %s", order_id_text, exc)
            return {"error": str(exc)}
