"""HTTP helpers for market selection."""

from __future__ import annotations

import json
from typing import Any, Optional

from packages.polymarket.clob import DEFAULT_CLOB_API_BASE
from packages.polymarket.gamma import DEFAULT_GAMMA_API_BASE
from packages.polymarket.http_client import HttpClient

_GAMMA_CLIENT = HttpClient(DEFAULT_GAMMA_API_BASE, timeout=20.0)
_CLOB_CLIENT = HttpClient(DEFAULT_CLOB_API_BASE, timeout=20.0)


def _coerce_float(value: Any) -> Optional[float]:
    try:
        if value in (None, ""):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _parse_token_ids(value: Any) -> list[str]:
    if value in (None, ""):
        return []
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            return [value]
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item or "").strip()]


def _extract_token_id(raw_market: dict[str, Any]) -> str:
    token_ids = _parse_token_ids(
        raw_market.get("clobTokenIds")
        or raw_market.get("clob_token_ids")
        or raw_market.get("tokenIds")
        or raw_market.get("token_ids")
    )
    return token_ids[0] if token_ids else ""


def _normalize_levels(levels: list[Any]) -> list[list[float]]:
    normalized: list[list[float]] = []
    for level in levels:
        if isinstance(level, dict):
            price = _coerce_float(level.get("price"))
            size = _coerce_float(level.get("size"))
        elif isinstance(level, (list, tuple)) and len(level) >= 2:
            price = _coerce_float(level[0])
            size = _coerce_float(level[1])
        else:
            continue

        if price is None or size is None:
            continue
        normalized.append([price, size])
    return normalized


def _markets_from_response(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if isinstance(payload, dict):
        rows = payload.get("data", payload.get("markets", []))
        if isinstance(rows, list):
            return [row for row in rows if isinstance(row, dict)]
    return []


def fetch_active_markets(min_volume: float = 5000, limit: int = 50) -> list[dict]:
    """Fetch active markets from Gamma and normalize the fields used by market selection."""

    payload = _GAMMA_CLIENT.get_json(
        "/markets",
        params={"active": "true", "closed": "false", "limit": int(limit)},
    )
    markets: list[dict] = []
    for raw_market in _markets_from_response(payload):
        volume_24h = (
            _coerce_float(raw_market.get("volume_24h"))
            or _coerce_float(raw_market.get("volume24h"))
            or _coerce_float(raw_market.get("volume24hr"))
            or _coerce_float(raw_market.get("volume"))
            or _coerce_float(raw_market.get("volumeNum"))
            or 0.0
        )
        if volume_24h < float(min_volume):
            continue

        markets.append(
            {
                "slug": str(raw_market.get("slug") or "").strip(),
                "best_bid": _coerce_float(raw_market.get("best_bid") or raw_market.get("bestBid")),
                "best_ask": _coerce_float(raw_market.get("best_ask") or raw_market.get("bestAsk")),
                "volume_24h": volume_24h,
                "end_date_iso": raw_market.get("end_date_iso") or raw_market.get("endDate"),
                "created_at": raw_market.get("created_at") or raw_market.get("createdAt"),
                "resolved_at": raw_market.get("resolved_at") or raw_market.get("resolvedAt"),
                "token_id": _extract_token_id(raw_market),
                # Regime-classification fields (used by regime_policy.enrich_with_regime)
                "title": raw_market.get("title") or raw_market.get("question") or None,
                "question": raw_market.get("question") or None,
                "category": raw_market.get("category") or None,
                "subcategory": raw_market.get("subcategory") or None,
                "tags": (
                    raw_market.get("tags")
                    or raw_market.get("tag_names")
                    or raw_market.get("tagNames")
                    or None
                ),
                "event_slug": raw_market.get("event_slug") or raw_market.get("eventSlug") or None,
                "event_title": raw_market.get("event_title") or raw_market.get("eventTitle") or None,
            }
        )
    return markets


def fetch_reward_config(market_slug: str) -> dict | None:
    """Fetch reward configuration for a market slug, returning None on 404."""

    response = _GAMMA_CLIENT.get_response(f"/markets/{market_slug}/rewards")
    if response.status_code == 404:
        return None
    response.raise_for_status()
    payload = response.json()
    if isinstance(payload, dict):
        return payload
    if isinstance(payload, list):
        if len(payload) == 1 and isinstance(payload[0], dict):
            return payload[0]
        return {"rewards": payload}
    return {}


def fetch_orderbook(token_id: str) -> dict:
    """Fetch and normalize the order book for a token."""

    payload = _CLOB_CLIENT.get_json("/book", params={"token_id": token_id})
    if not isinstance(payload, dict):
        return {"bids": [], "asks": []}
    return {
        "bids": _normalize_levels(payload.get("bids") or []),
        "asks": _normalize_levels(payload.get("asks") or []),
    }

