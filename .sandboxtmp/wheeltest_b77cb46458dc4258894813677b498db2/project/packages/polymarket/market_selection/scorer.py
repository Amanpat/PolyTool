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


# ---------------------------------------------------------------------------
# Gate 2 candidate ranking (extends existing scorer for candidate discovery)
# ---------------------------------------------------------------------------

GATE2_RANK_WEIGHTS: dict[str, float] = {
    "gate2_depth": 0.25,
    "gate2_edge":  0.25,
    "reward":      0.20,
    "volume":      0.15,
    "competition": 0.10,
    "age":         0.05,
}

# Edge normalization range (best_edge = threshold - sum_ask)
# best_edge below _EDGE_NORM_LOW → factor = 0
# best_edge above _EDGE_NORM_HIGH → factor = 1
_EDGE_NORM_LOW:  float = -0.10
_EDGE_NORM_HIGH: float =  0.05
# CandidateResult uses (threshold - 99) as sentinel when no BBO data
_EDGE_SENTINEL_FLOOR: float = -90.0


@dataclass(frozen=True)
class Gate2RankScore:
    """Explainable ranking score for a Gate 2 candidate market.

    Combines Gate 2 depth/edge signals with market quality factors.
    ``None`` on any quality factor means the data was unavailable —
    missing factors contribute **zero** to ``rank_score``, not positive evidence.

    A high ``rank_score`` is NOT the same as Gate 2 tradable.
    Only ``executable_ticks > 0`` (verified in a tape capture) proves eligibility.
    """

    slug: str

    # Gate 2 signals (always present from snapshot scan or tape replay)
    executable_ticks: int
    edge_ok_ticks: int
    depth_ok_ticks: int
    best_edge: Optional[float]   # None when no dual-leg BBO available
    depth_yes: float             # peak YES best-ask size observed
    depth_no: float              # peak NO best-ask size observed

    # Market quality factors (None = data unavailable / UNKNOWN)
    reward_apr_est: Optional[float]
    volume_24h: Optional[float]
    competition_score: Optional[float]
    age_hours: Optional[float]
    is_new_market: Optional[bool]  # True if age_hours < 48
    regime: Optional[str]          # None = not yet labeled

    # Composite attractiveness score (0–1)
    rank_score: float

    # Factor-by-factor operator explanation
    explanation: list[str]

    source: str  # "live" or "tape"

    @property
    def gate2_status(self) -> str:
        """Short code for the Gate 2 signal level."""
        if self.executable_ticks > 0:
            return "EXECUTABLE"
        if self.edge_ok_ticks > 0 and self.depth_ok_ticks > 0:
            return "NEAR"
        if self.edge_ok_ticks > 0:
            return "EDGE_ONLY"
        if self.depth_ok_ticks > 0:
            return "DEPTH_ONLY"
        return "NO_SIGNAL"

    @property
    def has_signal(self) -> bool:
        return self.executable_ticks > 0 or self.edge_ok_ticks > 0 or self.depth_ok_ticks > 0


def score_gate2_candidate(
    slug: str,
    *,
    executable_ticks: int,
    edge_ok_ticks: int,
    depth_ok_ticks: int,
    best_edge_raw: float,
    depth_yes: float,
    depth_no: float,
    market: Optional[dict] = None,
    reward_config: Optional[dict] = None,
    orderbook: Optional[dict] = None,
    source: str = "live",
    max_size: float = 50.0,
    buffer: float = 0.01,
) -> Gate2RankScore:
    """Score a Gate 2 candidate market with an explainable factor breakdown.

    Args:
        slug:             Market identifier.
        executable_ticks: Ticks with simultaneous depth+edge (from CandidateResult).
        edge_ok_ticks:    Ticks where sum_ask < threshold (may lack depth).
        depth_ok_ticks:   Ticks where both legs met depth requirement.
        best_edge_raw:    CandidateResult.best_edge — uses a sentinel value
                          (below _EDGE_SENTINEL_FLOOR) when no dual-leg BBO exists.
        depth_yes:        Peak YES-leg best-ask size observed.
        depth_no:         Peak NO-leg best-ask size observed.
        market:           Optional dict with keys: volume_24h, created_at, _regime.
        reward_config:    Optional dict with keys: reward_rate, min_size_cutoff.
        orderbook:        Optional dict {"bids": [...], "asks": [...]} for
                          competition score computation.
        source:           "live" or "tape".
        max_size:         Required depth threshold (match strategy sane preset: 50).
        buffer:           Entry buffer (match strategy sane preset: 0.01).

    Returns:
        Gate2RankScore.  rank_score is in [0, 1].  UNKNOWN factors contribute 0.
    """
    explanation: list[str] = []
    threshold = 1.0 - buffer

    # ---- Gate 2 summary header -----------------------------------------
    if executable_ticks > 0:
        explanation.append(
            f"GATE2: EXECUTABLE — {executable_ticks} tick(s) with depth+edge simultaneously"
        )
    elif edge_ok_ticks > 0 and depth_ok_ticks > 0:
        explanation.append(
            "GATE2: NEAR — edge and depth both seen but never simultaneously"
        )
    elif edge_ok_ticks > 0:
        explanation.append(
            f"GATE2: EDGE_ONLY — complement sum crossed threshold but depth insufficient "
            f"(YES {depth_yes:.0f} / NO {depth_no:.0f} vs {max_size:.0f} required)"
        )
    elif depth_ok_ticks > 0:
        explanation.append(
            "GATE2: DEPTH_ONLY — depth OK but sum_ask never fell below threshold"
        )
    else:
        explanation.append(
            "GATE2: NO_SIGNAL — neither depth nor edge condition met at this snapshot"
        )

    # ---- Factor: Gate 2 depth ------------------------------------------
    depth_min = min(depth_yes, depth_no)
    gate2_depth_factor = min(depth_min / max_size, 1.0) if max_size > 0 else 0.0
    if depth_min >= max_size:
        explanation.append(
            f"depth: YES {depth_yes:.0f} / NO {depth_no:.0f} — MEETS target ({max_size:.0f} shares)"
        )
    else:
        pct = depth_min / max_size * 100 if max_size > 0 else 0.0
        explanation.append(
            f"depth: YES {depth_yes:.0f} / NO {depth_no:.0f} — {pct:.0f}% of target "
            f"({max_size:.0f}; weaker leg is the binding constraint)"
        )

    # ---- Factor: Gate 2 edge -------------------------------------------
    real_edge_data = best_edge_raw > _EDGE_SENTINEL_FLOOR
    if real_edge_data:
        best_edge: Optional[float] = best_edge_raw
        edge_range = _EDGE_NORM_HIGH - _EDGE_NORM_LOW
        gate2_edge_factor = min(
            max((best_edge_raw - _EDGE_NORM_LOW) / edge_range, 0.0), 1.0
        )
        edge_pct = best_edge_raw * 100
        if best_edge_raw >= 0:
            explanation.append(
                f"edge: best_edge={edge_pct:+.2f}% ABOVE threshold ({threshold:.4f}) — "
                "arb window existed at this snapshot"
            )
        else:
            explanation.append(
                f"edge: best_edge={edge_pct:+.2f}% — sum_ask was "
                f"{abs(edge_pct):.2f}% above threshold (not yet executable)"
            )
    else:
        best_edge = None
        gate2_edge_factor = 0.0
        explanation.append(
            "edge: UNKNOWN — no dual-leg BBO data available for this market"
        )

    # ---- Factor: reward ------------------------------------------------
    reward_apr_est: Optional[float] = None
    reward_factor = 0.0
    if reward_config:
        rr = _coerce_float(reward_config.get("reward_rate"))
        if rr is not None and rr > 0:
            reward_apr_est = min(rr * 365.0, 3.0)
            reward_factor = reward_apr_est / 3.0
            level = "HIGH" if reward_apr_est >= 1.5 else "MED" if reward_apr_est >= 0.5 else "LOW"
            explanation.append(f"reward: APR≈{reward_apr_est:.2f}/yr ({level})")
        else:
            explanation.append(
                "reward: UNKNOWN — reward_config present but rate is zero or missing"
            )
    else:
        explanation.append(
            "reward: UNKNOWN — no reward_config data "
            "(market may not participate in a reward program)"
        )

    # ---- Factor: volume / liquidity ------------------------------------
    volume_24h: Optional[float] = None
    volume_factor = 0.0
    if market is not None:
        vol = _coerce_float(market.get("volume_24h"))
        if vol is not None:
            volume_24h = vol
            volume_factor = min(vol / 50_000.0, 1.0)
            level = "HIGH" if vol >= 25_000 else "MED" if vol >= 5_000 else "LOW"
            explanation.append(f"volume_24h: ${vol:,.0f} ({level})")
        else:
            explanation.append(
                "volume_24h: UNKNOWN — volume field missing from market metadata"
            )
    else:
        explanation.append("volume_24h: UNKNOWN — no market metadata supplied")

    # ---- Factor: competition / crowding --------------------------------
    competition_score_val: Optional[float] = None
    competition_factor = 0.0
    if orderbook is not None:
        bids = orderbook.get("bids") or []
        n_thin = sum(
            1 for price, size in _iter_levels(bids) if price * size < 50.0
        )
        competition_score_val = 1.0 / (n_thin + 1.0)
        competition_factor = min(competition_score_val, 1.0)
        crowd = "LOW CROWDING" if competition_score_val >= 0.5 else "HIGH CROWDING"
        explanation.append(
            f"competition: {competition_score_val:.2f} ({crowd}; "
            f"{n_thin} thin bid(s) < $50 as crowding proxy)"
        )
    else:
        explanation.append(
            "competition: UNKNOWN — no orderbook supplied for competition estimation"
        )

    # ---- Factor: age / new-market logic --------------------------------
    age_hours: Optional[float] = None
    is_new_market: Optional[bool] = None
    age_factor = 0.0
    if market is not None:
        created_at = _parse_datetime(market.get("created_at"))
        if created_at is not None:
            age_hours = max((_utcnow() - created_at).total_seconds() / 3600.0, 0.0)
            is_new_market = age_hours < 48.0
            if is_new_market:
                age_factor = 1.0
                explanation.append(
                    f"age: NEW MARKET ({age_hours:.1f}h old) — wider spreads, lower "
                    "competition, and higher reward volatility expected; "
                    "label tape with --regime new_market"
                )
            else:
                age_factor = 0.0
                explanation.append(
                    f"age: {age_hours:.1f}h (mature; no new-market bonus)"
                )
        else:
            explanation.append(
                "age: UNKNOWN — no created_at in market metadata"
            )
    else:
        explanation.append("age: UNKNOWN — no market metadata supplied")

    # ---- Regime label --------------------------------------------------
    regime: Optional[str] = None
    if market is not None:
        r = market.get("_regime") or market.get("regime")
        if r:
            regime = str(r).strip() or None
    if regime:
        explanation.append(f"regime: {regime} (labeled)")
    else:
        explanation.append(
            "regime: UNKNOWN — not yet labeled; set with --regime during tape capture "
            "(politics | sports | new_market | unknown)"
        )

    # ---- Composite rank score ------------------------------------------
    rank_score = (
        gate2_depth_factor   * GATE2_RANK_WEIGHTS["gate2_depth"]
        + gate2_edge_factor  * GATE2_RANK_WEIGHTS["gate2_edge"]
        + reward_factor      * GATE2_RANK_WEIGHTS["reward"]
        + volume_factor      * GATE2_RANK_WEIGHTS["volume"]
        + competition_factor * GATE2_RANK_WEIGHTS["competition"]
        + age_factor         * GATE2_RANK_WEIGHTS["age"]
    )

    return Gate2RankScore(
        slug=slug,
        executable_ticks=executable_ticks,
        edge_ok_ticks=edge_ok_ticks,
        depth_ok_ticks=depth_ok_ticks,
        best_edge=best_edge,
        depth_yes=depth_yes,
        depth_no=depth_no,
        reward_apr_est=reward_apr_est,
        volume_24h=volume_24h,
        competition_score=competition_score_val,
        age_hours=age_hours,
        is_new_market=is_new_market,
        regime=regime,
        rank_score=rank_score,
        explanation=explanation,
        source=source,
    )


def rank_gate2_candidates(
    scores: list[Gate2RankScore],
) -> list[Gate2RankScore]:
    """Sort Gate 2 candidate scores by executability then composite rank.

    Sort key (all descending):
      1. executable_ticks — confirmed Gate 2 opportunity first
      2. rank_score       — composite attractiveness (market quality + edge proximity)
      3. edge_ok_ticks    — secondary Gate 2 signal
      4. depth_ok_ticks   — tertiary Gate 2 signal
    """
    def _key(s: Gate2RankScore) -> tuple:
        return (s.executable_ticks, s.rank_score, s.edge_ok_ticks, s.depth_ok_ticks)

    return sorted(scores, key=_key, reverse=True)
