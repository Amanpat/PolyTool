"""Market scoring utilities for market selection."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping, Optional

from packages.polymarket.market_selection.regime_policy import (
    NEW_MARKET,
    POLITICS,
    SPORTS,
    classify_market_regime,
)

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
_AGE_HOURS_KEYS = ("age_hours", "ageHours")
_CREATED_AT_KEYS = (
    "created_at",
    "createdAt",
    "created_time",
    "createdTime",
    "published_at",
    "publishedAt",
    "listed_at",
    "listedAt",
)
_NAMED_REGIMES = {POLITICS, SPORTS, NEW_MARKET}


def _market_age_hours(
    market: Mapping[str, Any],
    *,
    reference_time: datetime,
) -> Optional[float]:
    for key in _AGE_HOURS_KEYS:
        age_hours = _coerce_float(market.get(key))
        if age_hours is not None and age_hours >= 0.0:
            return age_hours

    for key in _CREATED_AT_KEYS:
        created_at = _parse_datetime(market.get(key))
        if created_at is None:
            continue
        age_hours = (reference_time - created_at).total_seconds() / 3600.0
        if age_hours < 0.0:
            return None
        return age_hours

    return None


def _operator_regime_label(market: Mapping[str, Any]) -> Optional[str]:
    for key in ("_regime", "regime"):
        raw_value = market.get(key)
        if not isinstance(raw_value, str):
            continue
        clean = raw_value.strip().lower()
        if clean in _NAMED_REGIMES:
            return clean
    return None


def _derive_regime_context(
    market: Mapping[str, Any],
    *,
    reference_time: datetime,
) -> tuple[Optional[str], Optional[str], Optional[str], str]:
    derived_raw = classify_market_regime(market, reference_time=reference_time)
    derived_regime = derived_raw if derived_raw in _NAMED_REGIMES else None
    operator_regime = _operator_regime_label(market)

    if derived_regime is not None:
        final_regime = derived_regime
        regime_source = "derived"
    elif operator_regime is not None:
        final_regime = operator_regime
        regime_source = "operator"
    else:
        final_regime = None
        regime_source = "fallback_unknown"

    return derived_regime, operator_regime, final_regime, regime_source


@dataclass(frozen=True)
class Gate2RankScore:
    """Explainable ranking score for a Gate 2 candidate market.

    Combines Gate 2 depth/edge signals with market quality factors.
    ``None`` on any quality factor means the data was unavailable  -
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
    derived_regime: Optional[str]  # classifier result when metadata is strong enough
    operator_regime: Optional[str] # optional label carried in market metadata
    regime: Optional[str]          # final displayed regime; None = unknown
    regime_source: str             # derived | operator | fallback_unknown

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
        best_edge_raw:    CandidateResult.best_edge  - uses a sentinel value
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
            f"GATE2: EXECUTABLE - {executable_ticks} tick(s) with depth+edge simultaneously"
        )
    elif edge_ok_ticks > 0 and depth_ok_ticks > 0:
        explanation.append(
            "GATE2: NEAR  - edge and depth both seen but never simultaneously"
        )
    elif edge_ok_ticks > 0:
        explanation.append(
            f"GATE2: EDGE_ONLY  - complement sum crossed threshold but depth insufficient "
            f"(YES {depth_yes:.0f} / NO {depth_no:.0f} vs {max_size:.0f} required)"
        )
    elif depth_ok_ticks > 0:
        explanation.append(
            "GATE2: DEPTH_ONLY  - depth OK but sum_ask never fell below threshold"
        )
    else:
        explanation.append(
            "GATE2: NO_SIGNAL  - neither depth nor edge condition met at this snapshot"
        )

    # ---- Factor: Gate 2 depth ------------------------------------------
    depth_min = min(depth_yes, depth_no)
    gate2_depth_factor = min(depth_min / max_size, 1.0) if max_size > 0 else 0.0
    if depth_min >= max_size:
        explanation.append(
            f"depth: YES {depth_yes:.0f} / NO {depth_no:.0f}  - MEETS target ({max_size:.0f} shares)"
        )
    else:
        pct = depth_min / max_size * 100 if max_size > 0 else 0.0
        explanation.append(
            f"depth: YES {depth_yes:.0f} / NO {depth_no:.0f}  - {pct:.0f}% of target "
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
                f"edge: best_edge={edge_pct:+.2f}% ABOVE threshold ({threshold:.4f})  - "
                "arb window existed at this snapshot"
            )
        else:
            explanation.append(
                f"edge: best_edge={edge_pct:+.2f}%  - sum_ask was "
                f"{abs(edge_pct):.2f}% above threshold (not yet executable)"
            )
    else:
        best_edge = None
        gate2_edge_factor = 0.0
        explanation.append(
            "edge: UNKNOWN  - no dual-leg BBO data available for this market"
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
            explanation.append(f"reward: APR~{reward_apr_est:.2f}/yr ({level})")
        else:
            explanation.append(
                "reward: UNKNOWN  - reward_config present but rate is zero or missing"
            )
    else:
        explanation.append(
            "reward: UNKNOWN  - no reward_config data "
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
                "volume_24h: UNKNOWN  - volume field missing from market metadata"
            )
    else:
        explanation.append("volume_24h: UNKNOWN  - no market metadata supplied")

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
            "competition: UNKNOWN  - no orderbook supplied for competition estimation"
        )

    # ---- Factor: age / new-market logic --------------------------------
    reference_time = _utcnow()

    age_hours: Optional[float] = None
    is_new_market: Optional[bool] = None
    age_factor = 0.0
    if market is not None:
        age_hours = _market_age_hours(market, reference_time=reference_time)
        if age_hours is not None:
            is_new_market = age_hours < 48.0
            if is_new_market:
                age_factor = 1.0
                explanation.append(
                    f"age: NEW MARKET ({age_hours:.1f}h old)  - derived from market age metadata; "
                    "label tape with --regime new_market during capture if preserving early-market context"
                )
            else:
                explanation.append(
                    f"age: {age_hours:.1f}h old (mature; no new-market bonus)"
                )
        else:
            explanation.append(
                "age: UNKNOWN  - no created_at/age_hours metadata supplied"
            )
    else:
        explanation.append("age: UNKNOWN  - no market metadata supplied")

    # ---- Regime label --------------------------------------------------
    derived_regime: Optional[str] = None
    operator_regime: Optional[str] = None
    regime_source = "fallback_unknown"
    regime: Optional[str] = None
    if market is not None:
        derived_regime, operator_regime, regime, regime_source = _derive_regime_context(
            market,
            reference_time=reference_time,
        )
    regime_mismatch = (
        derived_regime is not None
        and operator_regime is not None
        and derived_regime != operator_regime
    )
    if regime:
        details = (
            f"source={regime_source}; derived={derived_regime or 'UNKNOWN'}; "
            f"operator={operator_regime or 'UNKNOWN'}"
        )
        if regime_mismatch:
            details += "; mismatch"
        explanation.append(f"regime: {regime} ({details})")
    else:
        explanation.append(
            "regime: UNKNOWN  - source=fallback_unknown; derived=UNKNOWN; operator=UNKNOWN"
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
        derived_regime=derived_regime,
        operator_regime=operator_regime,
        regime=regime,
        regime_source=regime_source,
        rank_score=rank_score,
        explanation=explanation,
        source=source,
    )


def rank_gate2_candidates(
    scores: list[Gate2RankScore],
) -> list[Gate2RankScore]:
    """Sort Gate 2 candidate scores by executability then composite rank.

    Sort key (all descending):
      1. executable_ticks  - confirmed Gate 2 opportunity first
      2. rank_score        - composite attractiveness (market quality + edge proximity)
      3. edge_ok_ticks     - secondary Gate 2 signal
      4. depth_ok_ticks    - tertiary Gate 2 signal
    """
    def _key(s: Gate2RankScore) -> tuple:
        return (s.executable_ticks, s.rank_score, s.edge_ok_ticks, s.depth_ok_ticks)

    return sorted(scores, key=_key, reverse=True)


# ---------------------------------------------------------------------------
# Seven-factor Market Selection Engine
# (Gate2RankScore and MarketScore above are UNTOUCHED)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SevenFactorScore:
    """Composite opportunity score for the seven-factor Market Selection Engine."""

    market_slug: str
    category: str
    spread_score: float
    volume_score: float
    competition_score: float
    reward_apr_score: float
    adverse_selection_score: float
    time_score: float
    category_edge_score: float
    longshot_bonus: float
    composite: float
    gate_passed: bool
    gate_reason: str
    neg_risk: bool


class MarketScorer:
    """Score a universe of Polymarket markets using the seven-factor model.

    Args:
        now: Reference datetime for days_to_resolution computation.
             Defaults to UTC now. Pass a fixed value for deterministic tests.
    """

    def __init__(self, *, now: Optional[datetime] = None) -> None:
        if now is None:
            now = datetime.now(timezone.utc)
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
        self._now = now.astimezone(timezone.utc)

    def score_universe(
        self,
        markets: list[dict],
        *,
        include_failing: bool = False,
    ) -> list[SevenFactorScore]:
        """Score all markets and return sorted descending by composite.

        By default only gate-passed markets are returned.  Pass
        ``include_failing=True`` to include gate-failed markets as well
        (useful for diagnostics).  Duplicates by market_slug are
        deduplicated — the entry with the highest composite is kept.
        """
        seen: dict[str, SevenFactorScore] = {}
        for market in markets:
            score = self._score_single(market)
            if not include_failing and not score.gate_passed:
                continue
            slug = score.market_slug
            if slug not in seen or score.composite > seen[slug].composite:
                seen[slug] = score

        return sorted(seen.values(), key=lambda s: s.composite, reverse=True)

    def _score_single(self, market: dict) -> SevenFactorScore:
        """Compute SevenFactorScore for a single market dict."""
        from packages.polymarket.market_selection.config import (
            FACTOR_WEIGHTS,
            CATEGORY_EDGE,
            CATEGORY_EDGE_DEFAULT,
            ADVERSE_SELECTION_PRIOR,
            ADVERSE_SELECTION_DEFAULT,
            MAX_SPREAD_REFERENCE,
            COMPETITION_SPREAD_THRESHOLD,
            TARGET_REWARD_APR,
            LONGSHOT_BONUS_MAX,
            LONGSHOT_THRESHOLD,
            TIME_SCORE_CENTER_DAYS,
            NEGRISK_PENALTY,
        )
        from packages.polymarket.market_selection.filters import passes_gates
        import math as _math

        market_slug = str(market.get("slug") or market.get("market_slug") or "").strip()
        category = str(market.get("category") or "Other").strip()

        # ---- BBO data -------------------------------------------------------
        best_bid = _coerce_float(market.get("best_bid"))
        best_ask = _coerce_float(market.get("best_ask"))
        has_bbo = best_bid is not None and best_ask is not None

        # ---- spread_score ---------------------------------------------------
        if has_bbo:
            spread = best_ask - best_bid  # type: ignore[operator]
            spread_score = min(spread / MAX_SPREAD_REFERENCE, 1.0)
            spread_score = max(spread_score, 0.0)
        else:
            spread = None
            spread_score = 0.0

        # ---- volume_score ---------------------------------------------------
        volume_24h = _coerce_float(market.get("volume_24h")) or 0.0
        volume_score = _math.log10(max(volume_24h, 1)) / _math.log10(100_000)
        volume_score = max(0.0, min(volume_score, 1.0))

        # ---- competition_score ----------------------------------------------
        bids = market.get("bids") or market.get("orderbook_bids") or []
        if bids:
            non_trivial_count = sum(
                1
                for level in bids
                if isinstance(level, dict)
                and (_coerce_float(level.get("price")) or 0.0)
                * (_coerce_float(level.get("size")) or 0.0)
                >= COMPETITION_SPREAD_THRESHOLD * 100
            )
            competition_score = 1.0 / (non_trivial_count + 1)
        else:
            competition_score = 0.5  # default when no orderbook data

        # ---- reward_apr_score -----------------------------------------------
        reward_rate = _coerce_float(market.get("reward_rate")) or 0.0
        reward_apr_score = min(reward_rate * 365 / TARGET_REWARD_APR, 1.0)
        reward_apr_score = max(reward_apr_score, 0.0)

        # ---- adverse_selection_score ----------------------------------------
        adverse_selection_score = ADVERSE_SELECTION_PRIOR.get(category, ADVERSE_SELECTION_DEFAULT)

        # ---- time_score ------------------------------------------------------
        end_date_raw = market.get("end_date_iso") or market.get("endDate")
        days_to_resolution: Optional[float] = None
        if end_date_raw is not None:
            end_dt = _parse_datetime(end_date_raw)
            if end_dt is not None:
                days_to_resolution = (end_dt - self._now).total_seconds() / 86400.0

        if days_to_resolution is not None:
            sigma = TIME_SCORE_CENTER_DAYS
            time_score = _math.exp(
                -((days_to_resolution - TIME_SCORE_CENTER_DAYS) ** 2) / (2 * sigma ** 2)
            )
            time_score = max(0.0, min(time_score, 1.0))
        else:
            time_score = 0.5

        # ---- category_edge_score --------------------------------------------
        category_edge_score = CATEGORY_EDGE.get(category, CATEGORY_EDGE_DEFAULT)

        # ---- longshot_bonus -------------------------------------------------
        if has_bbo:
            mid_price = (best_bid + best_ask) / 2.0  # type: ignore[operator]
            if mid_price <= LONGSHOT_THRESHOLD:
                longshot_bonus = LONGSHOT_BONUS_MAX * (1.0 - mid_price / LONGSHOT_THRESHOLD)
            else:
                longshot_bonus = 0.0
        else:
            longshot_bonus = 0.0

        # ---- composite ------------------------------------------------------
        composite = (
            category_edge_score    * FACTOR_WEIGHTS["category_edge"]
            + spread_score         * FACTOR_WEIGHTS["spread_opportunity"]
            + volume_score         * FACTOR_WEIGHTS["volume"]
            + competition_score    * FACTOR_WEIGHTS["competition"]
            + reward_apr_score     * FACTOR_WEIGHTS["reward_apr"]
            + adverse_selection_score * FACTOR_WEIGHTS["adverse_selection"]
            + time_score           * FACTOR_WEIGHTS["time_to_resolution"]
            + longshot_bonus
        )

        neg_risk = bool(market.get("neg_risk", False))
        if neg_risk:
            composite *= NEGRISK_PENALTY

        composite = max(0.0, min(composite, 1.0))

        # ---- gate check -----------------------------------------------------
        accepting_orders = market.get("accepting_orders")
        enable_order_book = market.get("enable_order_book")
        gate_passed, gate_reason = passes_gates(
            volume_24h=volume_24h,
            spread=spread,
            days_to_resolution=days_to_resolution,
            accepting_orders=accepting_orders,
            enable_order_book=enable_order_book,
        )

        return SevenFactorScore(
            market_slug=market_slug,
            category=category,
            spread_score=spread_score,
            volume_score=volume_score,
            competition_score=competition_score,
            reward_apr_score=reward_apr_score,
            adverse_selection_score=adverse_selection_score,
            time_score=time_score,
            category_edge_score=category_edge_score,
            longshot_bonus=longshot_bonus,
            composite=composite,
            gate_passed=gate_passed,
            gate_reason=gate_reason,
            neg_risk=neg_risk,
        )
