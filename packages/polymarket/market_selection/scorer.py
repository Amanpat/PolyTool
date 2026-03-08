"""Market scoring utilities for market selection."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable, Optional

WEIGHTS = {
    "reward_apr_est": 0.35,
    "spread_score": 0.25,
    "fill_score": 0.20,
    "competition_score": 0.15,
    "age_factor": 0.05,
}


@dataclass(frozen=True)
class MarketScore:
    market_slug: str
    reward_apr_est: float
    spread_score: float
    fill_score: float
    competition_score: float
    age_hours: float
    composite: float


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


def _iter_levels(levels: Iterable[Any]) -> Iterable[tuple[float, float]]:
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
        yield price, size


def _best_price(levels: Iterable[Any]) -> Optional[float]:
    for price, _size in _iter_levels(levels):
        return price
    return None


def score_market(market: dict, orderbook: dict, reward_config: dict) -> MarketScore:
    """Score a market candidate using the Construction Manual Section 4 weights."""

    market_slug = str(market.get("slug") or market.get("market_slug") or "").strip()

    reward_rate = _coerce_float(reward_config.get("reward_rate")) or 0.0
    min_size_cutoff = _coerce_float(reward_config.get("min_size_cutoff")) or 0.0
    reward_apr_raw = 0.0
    if min_size_cutoff > 0:
        reward_apr_raw = ((reward_rate * min_size_cutoff) / min_size_cutoff) * 365.0
    reward_apr_est = min(max(reward_apr_raw, 0.0), 3.0)

    best_bid = _coerce_float(market.get("best_bid"))
    best_ask = _coerce_float(market.get("best_ask"))
    if best_bid is None:
        best_bid = _best_price(orderbook.get("bids") or [])
    if best_ask is None:
        best_ask = _best_price(orderbook.get("asks") or [])
    spread_score_raw = 0.0
    if best_bid is not None and best_ask is not None:
        spread_score_raw = (best_ask - best_bid) / 0.015
    spread_score = min(max(spread_score_raw, 0.0), 3.0)

    volume_24h = _coerce_float(market.get("volume_24h")) or 0.0
    fill_score = min(max(volume_24h / 10000.0, 0.0), 2.0)

    count_of_bids_under_50_usdc = sum(
        1 for price, size in _iter_levels(orderbook.get("bids") or []) if (price * size) < 50.0
    )
    competition_score = 1.0 / (count_of_bids_under_50_usdc + 1.0)

    created_at = _parse_datetime(market.get("created_at"))
    age_hours = 0.0
    if created_at is not None:
        age_hours = max((_utcnow() - created_at).total_seconds() / 3600.0, 0.0)
    age_factor = max(0.0, 1.0 - (age_hours / 48.0))

    composite = (
        (reward_apr_est * WEIGHTS["reward_apr_est"])
        + (spread_score * WEIGHTS["spread_score"])
        + (fill_score * WEIGHTS["fill_score"])
        + (competition_score * WEIGHTS["competition_score"])
        + (age_factor * WEIGHTS["age_factor"])
    )

    return MarketScore(
        market_slug=market_slug,
        reward_apr_est=reward_apr_est,
        spread_score=spread_score,
        fill_score=fill_score,
        competition_score=competition_score,
        age_hours=age_hours,
        composite=composite,
    )
