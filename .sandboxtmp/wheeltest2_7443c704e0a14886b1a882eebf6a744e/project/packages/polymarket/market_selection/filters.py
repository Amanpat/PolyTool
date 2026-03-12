"""Pre-filter checks for market selection."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _coerce_float(value: Any) -> Optional[float]:
    try:
        if value in (None, ""):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _parse_datetime(value: Any) -> Optional[datetime]:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        dt = value
    else:
        text = str(value).strip()
        if not text:
            return None
        try:
            dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def passes_filters(market: dict, reward_config: dict) -> tuple[bool, str]:
    """Apply the five Construction Manual pre-filters."""

    now = _utcnow()
    best_bid = _coerce_float(market.get("best_bid"))
    best_ask = _coerce_float(market.get("best_ask"))
    if best_bid is None or best_ask is None:
        return False, "mid_price_out_of_range"

    mid_price = (best_bid + best_ask) / 2.0
    if mid_price < 0.10 or mid_price > 0.90:
        return False, "mid_price_out_of_range"

    end_date = _parse_datetime(market.get("end_date_iso") or market.get("endDate"))
    if end_date is None:
        return False, "resolution_too_close"
    days_to_resolution = (end_date - now).total_seconds() / 86400.0
    if days_to_resolution <= 3.0:
        return False, "resolution_too_close"

    volume_24h = _coerce_float(market.get("volume_24h")) or 0.0
    if volume_24h <= 5000.0:
        return False, "volume_too_low"

    if reward_config is None or not reward_config:
        return False, "missing_reward_config"

    resolved_at = _parse_datetime(market.get("resolved_at") or market.get("resolvedAt"))
    if resolved_at is not None:
        hours_since_resolution = (now - resolved_at).total_seconds() / 3600.0
        if hours_since_resolution <= 24.0:
            return False, "recently_resolved"

    return True, ""

