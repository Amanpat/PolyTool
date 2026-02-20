"""Coverage & Reconciliation Report builder.

Generates a JSON (and optionally Markdown) report summarising position
outcome coverage, trade-UID integrity, PnL totals, fee sourcing, and
resolution coverage for a single examination run.
"""

from __future__ import annotations

import json
import math
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


REPORT_VERSION = "1.5.0"
TOP_SEGMENT_MIN_COUNT = 5  # Minimum positions in a segment to appear in Top Segments tables
PENDING_COVERAGE_INVALID_WARNING = (
    "All positions are PENDING despite strong identifier coverage. "
    "This often indicates resolution enrichment did not apply to the relevant tokens "
    "(candidate cap/truncation or join mismatch). "
    "Re-run with --resolution-max-candidates 300+ and verify enrichment truncation metrics."
)
DEFAULT_PROFIT_FEE_RATE = 0.02
DEFAULT_FEE_SOURCE_LABEL = "estimated"
NOT_APPLICABLE_FEE_SOURCE = "not_applicable"

KNOWN_OUTCOMES = frozenset({
    "WIN", "LOSS", "PROFIT_EXIT", "LOSS_EXIT", "PENDING", "UNKNOWN_RESOLUTION",
})

DEFAULT_ENTRY_PRICE_TIERS: List[Dict[str, Any]] = [
    {"name": "deep_underdog", "max": 0.30},
    {"name": "underdog", "min": 0.30, "max": 0.45},
    {"name": "coinflip", "min": 0.45, "max": 0.55},
    {"name": "favorite", "min": 0.55},
]

LEAGUE_TO_SPORT: Dict[str, str] = {
    "nba": "basketball",
    "wnba": "basketball",
    "ncaamb": "basketball",
    "nfl": "american_football",
    "ncaafb": "american_football",
    "mlb": "baseball",
    "nhl": "hockey",
    "epl": "soccer",
    "lal": "soccer",
    "elc": "soccer",
    "ucl": "soccer",
    "mls": "soccer",
    "atp": "tennis",
    "wta": "tennis",
    "ufc": "mma",
    "pga": "golf",
    "nascar": "motorsport",
    "f1": "motorsport",
    "unknown": "unknown",
}

MARKET_TYPE_SPREAD_HINTS = ("spread", "handicap")
MARKET_TYPE_TOTAL_HINTS = ("total", "over/under", "over under", "o/u")
MARKET_TYPE_PROP_HINTS = (
    "player prop",
    "player props",
    "to score",
    "to record",
    "rebounds",
    "assists",
    "passing yards",
    "rushing yards",
    "receiving yards",
    "strikeouts",
)
MONEYLINE_WILL_WIN_PATTERN = re.compile(r"will .* win", re.IGNORECASE)
MATCHUP_VS_PATTERN = re.compile(r"\b(?:vs|v)\b", re.IGNORECASE)


_MARKET_METADATA_FIELDS = ("market_slug", "question", "outcome_name")
_POSITION_IDENTIFIER_KEYS = ("token_id", "resolved_token_id", "condition_id")
_CATEGORY_UNKNOWN = "Unknown"


def _has_market_metadata(position: Dict[str, Any]) -> bool:
    """Return True if at least one market metadata field is non-empty."""
    return any(str(position.get(f) or "").strip() for f in _MARKET_METADATA_FIELDS)


def _get_position_identifier(position: Dict[str, Any]) -> tuple[str, str]:
    """Return identifier key/value for unmappable diagnostics.

    Token-level identifiers (`token_id` or `resolved_token_id`) are surfaced as
    `token_id` in report payloads. Market-level identifiers are surfaced as
    `condition_id`.
    """
    for key in _POSITION_IDENTIFIER_KEYS:
        val = str(position.get(key) or "").strip()
        if val:
            if key == "condition_id":
                return "condition_id", val
            return "token_id", val
    return "", ""


def _rank_unmappable(
    unmappable_counts: Counter,
    unmappable_examples: Dict[tuple[str, str], Dict[str, Any]],
    limit: int = 10,
) -> List[Dict[str, Any]]:
    ranked = sorted(
        unmappable_counts.items(),
        key=lambda item: (-item[1], item[0][0], item[0][1]),
    )[:limit]
    return [
        {
            id_key: id_value,
            "count": count,
            "example": unmappable_examples.get((id_key, id_value), {}),
        }
        for (id_key, id_value), count in ranked
    ]


def backfill_market_metadata(
    positions: List[Dict[str, Any]],
    market_metadata_map: Optional[Dict[str, Dict[str, str]]] = None,
) -> set:
    """Backfill missing market_slug/question/outcome_name from a local token/condition map.

    Mutates *positions* in place — only fills fields that are currently empty and
    only when the mapping contains a non-empty value.  Never guesses: if no
    mapping is found the field is left empty.

    **Key invariant — condition_id cannot fill outcome_name.**
    A ``condition_id`` identifies a *market* (shared across all outcome tokens within
    that market), so we cannot know which specific outcome a position corresponds to
    from the condition alone.  ``token_id`` and ``resolved_token_id`` each identify a
    single outcome token and may fill all three fields.

    Parameters
    ----------
    positions : list[dict]
        Position lifecycle records, potentially missing market metadata.
    market_metadata_map : dict[str, dict[str, str]] | None
        Maps a token_id or condition_id string to a dict with any subset of
        ``{market_slug, question, outcome_name}``.  Pass *None* or ``{}`` to
        skip backfill entirely.

    Returns
    -------
    set of int
        Indices of positions where at least one field was backfilled.
    """
    backfilled: set = set()
    if not market_metadata_map:
        return backfilled

    for idx, pos in enumerate(positions):
        slug = str(pos.get("market_slug") or "").strip()
        question = str(pos.get("question") or "").strip()
        outcome_name = str(pos.get("outcome_name") or "").strip()
        category = str(pos.get("category") or "").strip()

        if slug and question and outcome_name and category:
            continue  # Already fully populated

        # Determine which identifier key is available and track its type.
        # Priority: token_id > resolved_token_id > condition_id
        used_key: Optional[str] = None
        identifier = ""
        for key in ("token_id", "resolved_token_id", "condition_id"):
            val = str(pos.get(key) or "").strip()
            if val:
                identifier = val
                used_key = key
                break

        if not identifier:
            continue

        mapping = market_metadata_map.get(identifier)
        if not mapping:
            continue

        # condition_id resolves to market level only — outcome_name is token-specific
        # and must NOT be inferred from a condition-level mapping.
        allow_outcome_name = used_key != "condition_id"

        changed = False
        if not slug:
            new_slug = str(mapping.get("market_slug") or "").strip()
            if new_slug:
                pos["market_slug"] = new_slug
                changed = True
        if not question:
            new_question = str(mapping.get("question") or "").strip()
            if new_question:
                pos["question"] = new_question
                changed = True
        if not outcome_name and allow_outcome_name:
            new_outcome_name = str(mapping.get("outcome_name") or "").strip()
            if new_outcome_name:
                pos["outcome_name"] = new_outcome_name
                changed = True
        # category is market-level — safe to fill from any identifier key including condition_id
        if not category:
            new_category = str(mapping.get("category") or "").strip()
            if new_category:
                pos["category"] = new_category
                changed = True

        if changed:
            backfilled.add(idx)

    return backfilled


def _build_market_metadata_coverage(
    positions: List[Dict[str, Any]],
    backfilled_indices: Optional[set] = None,
    metadata_conflicts_count: int = 0,
    metadata_conflict_sample: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Compute market metadata coverage statistics from positions.

    A position is considered *present* when at least one of
    ``market_slug``, ``question``, or ``outcome_name`` is non-empty after
    any backfill has been applied.

    Parameters
    ----------
    positions : list[dict]
        Position records (call *after* ``backfill_market_metadata`` has run).
    backfilled_indices : set[int] | None
        Set of position indices where backfill was applied.  Used to populate
        ``source_counts.backfilled`` vs ``source_counts.ingested``.
    metadata_conflicts_count : int
        Number of mapping collisions detected when building the map (two
        positions with the same identifier but different metadata values).
        Kept first-wins deterministically.
    metadata_conflict_sample : list[dict] | None
        Up to 5 examples of conflicting entries for debugging.
    """
    if backfilled_indices is None:
        backfilled_indices = set()

    present_count = 0
    missing_count = 0
    source_counts: Dict[str, int] = {"ingested": 0, "backfilled": 0, "unknown": 0}
    unmappable_counts: Counter = Counter()
    unmappable_examples: Dict[tuple[str, str], Dict[str, Any]] = {}

    for idx, pos in enumerate(positions):
        if _has_market_metadata(pos):
            present_count += 1
            if idx in backfilled_indices:
                source_counts["backfilled"] += 1
            else:
                source_counts["ingested"] += 1
        else:
            missing_count += 1
            source_counts["unknown"] += 1
            identifier_key, identifier_value = _get_position_identifier(pos)
            if identifier_value:
                identifier = (identifier_key, identifier_value)
                unmappable_counts[identifier] += 1
                if identifier not in unmappable_examples:
                    unmappable_examples[identifier] = {
                        k: pos.get(k)
                        for k in ("token_id", "resolved_token_id", "condition_id",
                                  "resolution_outcome")
                    }

    total = len(positions)
    top_unmappable = _rank_unmappable(unmappable_counts, unmappable_examples, limit=10)

    result: Dict[str, Any] = {
        "present_count": present_count,
        "missing_count": missing_count,
        "coverage_rate": _safe_pct(present_count, total),
        "source_counts": source_counts,
        "metadata_conflicts_count": metadata_conflicts_count,
        "top_unmappable": top_unmappable,
    }
    if metadata_conflict_sample:
        result["metadata_conflict_sample"] = metadata_conflict_sample[:5]
    return result


def _get_category_key(position: Dict[str, Any]) -> str:
    """Return the Polymarket category label, or 'Unknown' if absent/empty."""
    return str(position.get("category") or "").strip() or _CATEGORY_UNKNOWN


def _build_category_coverage(
    positions: List[Dict[str, Any]],
    backfilled_category_indices: Optional[set] = None,
) -> Dict[str, Any]:
    """Compute category coverage statistics from positions.

    A position is considered *present* when ``category`` is non-empty after
    any backfill has been applied.

    Parameters
    ----------
    positions : list[dict]
        Position records (call *after* ``backfill_market_metadata`` has run).
    backfilled_category_indices : set[int] | None
        Indices of positions where ``category`` was filled by backfill.
    """
    if backfilled_category_indices is None:
        backfilled_category_indices = set()

    present_count = 0
    missing_count = 0
    source_counts: Dict[str, int] = {"ingested": 0, "backfilled": 0, "unknown": 0}
    unmappable_counts: Counter = Counter()
    unmappable_examples: Dict[tuple[str, str], Dict[str, Any]] = {}

    for idx, pos in enumerate(positions):
        category = str(pos.get("category") or "").strip()
        if category:
            present_count += 1
            if idx in backfilled_category_indices:
                source_counts["backfilled"] += 1
            else:
                source_counts["ingested"] += 1
        else:
            missing_count += 1
            source_counts["unknown"] += 1
            identifier_key, identifier_value = _get_position_identifier(pos)
            if identifier_value:
                identifier = (identifier_key, identifier_value)
                unmappable_counts[identifier] += 1
                if identifier not in unmappable_examples:
                    unmappable_examples[identifier] = {
                        k: pos.get(k)
                        for k in ("token_id", "resolved_token_id", "condition_id",
                                  "resolution_outcome")
                    }

    total = len(positions)
    top_unmappable = _rank_unmappable(unmappable_counts, unmappable_examples, limit=10)

    return {
        "present_count": present_count,
        "missing_count": missing_count,
        "coverage_rate": _safe_pct(present_count, total),
        "source_counts": source_counts,
        "top_unmappable": top_unmappable,
    }


def _build_clv_coverage(positions: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Compute CLV coverage + missingness from position-level CLV fields."""
    eligible_positions = 0
    clv_present_count = 0
    clv_missing_count = 0

    close_ts_source_counts: Counter = Counter()
    clv_source_counts: Counter = Counter()
    missing_reason_counts: Counter = Counter()

    for pos in positions:
        entry_price = _safe_float(pos.get("entry_price"))
        token_id = str(
            pos.get("resolved_token_id")
            or pos.get("token_id")
            or pos.get("outcome_token_id")
            or ""
        ).strip()

        # Eligibility: binary probability-like rows with a token id and valid entry price.
        if entry_price is None or not (0.0 < entry_price <= 1.0) or not token_id:
            continue
        eligible_positions += 1

        close_ts_source = str(pos.get("close_ts_source") or "").strip()
        if close_ts_source:
            close_ts_source_counts[close_ts_source] += 1

        clv_value = _safe_float(pos.get("clv"))
        if clv_value is not None:
            clv_present_count += 1
            clv_source = str(pos.get("clv_source") or "").strip()
            if clv_source:
                clv_source_counts[clv_source] += 1
        else:
            clv_missing_count += 1
            reason = str(pos.get("clv_missing_reason") or "UNSPECIFIED").strip() or "UNSPECIFIED"
            missing_reason_counts[reason] += 1

    return {
        "eligible_positions": eligible_positions,
        "clv_present_count": clv_present_count,
        "clv_missing_count": clv_missing_count,
        "coverage_rate": _safe_pct(clv_present_count, eligible_positions),
        "close_ts_source_counts": dict(sorted(close_ts_source_counts.items())),
        "clv_source_counts": dict(sorted(clv_source_counts.items())),
        "missing_reason_counts": dict(sorted(missing_reason_counts.items())),
    }


def _build_entry_context_coverage(positions: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Compute entry price/time context coverage from position-level fields."""
    eligible_positions = len(positions)
    open_price_present_count = 0
    price_1h_before_entry_present_count = 0
    price_at_entry_present_count = 0
    movement_direction_present_count = 0
    minutes_to_close_present_count = 0
    missing_reason_counts: Counter = Counter()

    def _reason_or_unspecified(position: Dict[str, Any], reason_field: str) -> str:
        return str(position.get(reason_field) or "UNSPECIFIED").strip() or "UNSPECIFIED"

    for pos in positions:
        open_price = _safe_float(pos.get("open_price"))
        if open_price is not None:
            open_price_present_count += 1
        else:
            missing_reason_counts[_reason_or_unspecified(pos, "open_price_missing_reason")] += 1

        price_1h_before_entry = _safe_float(pos.get("price_1h_before_entry"))
        if price_1h_before_entry is not None:
            price_1h_before_entry_present_count += 1
        else:
            missing_reason_counts[
                _reason_or_unspecified(pos, "price_1h_before_entry_missing_reason")
            ] += 1

        price_at_entry = _safe_float(pos.get("price_at_entry"))
        if price_at_entry is not None:
            price_at_entry_present_count += 1
        else:
            missing_reason_counts[_reason_or_unspecified(pos, "price_at_entry_missing_reason")] += 1

        movement_direction = str(pos.get("movement_direction") or "").strip().lower()
        if movement_direction in {"up", "down", "flat"}:
            movement_direction_present_count += 1
        else:
            missing_reason_counts[
                _reason_or_unspecified(pos, "movement_direction_missing_reason")
            ] += 1

        minutes_to_close = _safe_float(pos.get("minutes_to_close"))
        if minutes_to_close is not None:
            minutes_to_close_present_count += 1
        else:
            missing_reason_counts[
                _reason_or_unspecified(pos, "minutes_to_close_missing_reason")
            ] += 1

    return {
        "eligible_positions": eligible_positions,
        "open_price_present_count": open_price_present_count,
        "price_1h_before_entry_present_count": price_1h_before_entry_present_count,
        "price_at_entry_present_count": price_at_entry_present_count,
        "movement_direction_present_count": movement_direction_present_count,
        "minutes_to_close_present_count": minutes_to_close_present_count,
        "missing_reason_counts": dict(sorted(missing_reason_counts.items())),
    }


def _safe_pct(numerator: int, denominator: int) -> float:
    if denominator == 0:
        return 0.0
    return round(numerator / denominator, 6)


def _safe_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(numeric):
        return None
    return numeric


def extract_position_notional_usd(pos: Dict[str, Any]) -> Optional[float]:
    """Extract position notional USD using a priority fallback chain.

    Source priority:
    1. ``position_notional_usd`` — explicit notional field (preferred)
    2. ``total_cost`` — total cost paid for the position (common dossier field)
    3. ``size * entry_price`` — computed from raw size and entry price

    Returns *None* when no source yields a positive finite value.
    """
    v = _safe_float(pos.get("position_notional_usd"))
    if v is not None and v > 0:
        return v

    v = _safe_float(pos.get("total_cost"))
    if v is not None and v > 0:
        return v

    size = _safe_float(pos.get("size"))
    entry_price = _safe_float(pos.get("entry_price"))
    if size is not None and entry_price is not None and entry_price > 0:
        computed = size * entry_price
        if computed > 0:
            return computed

    return None


def _coerce_int(value: Any) -> int:
    if value is None:
        return 0
    try:
        return int(value)
    except (TypeError, ValueError):
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return 0


def _now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _normalize_fee_config(fee_config: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    raw = fee_config if isinstance(fee_config, dict) else {}

    rate = _safe_float(raw.get("profit_fee_rate"))
    if rate is None or rate < 0:
        rate = DEFAULT_PROFIT_FEE_RATE

    source_label = str(raw.get("source_label") or "").strip()
    if not source_label:
        source_label = DEFAULT_FEE_SOURCE_LABEL

    return {
        "profit_fee_rate": float(rate),
        "source_label": source_label,
    }


def _normalize_outcome(value: Any) -> str:
    outcome = str(value or "UNKNOWN_RESOLUTION").strip().upper()
    if outcome in KNOWN_OUTCOMES:
        return outcome
    return "UNKNOWN_RESOLUTION"


def _normalize_entry_price_tiers(entry_price_tiers: Optional[List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    default_tiers = [dict(tier) for tier in DEFAULT_ENTRY_PRICE_TIERS]
    if not isinstance(entry_price_tiers, list) or not entry_price_tiers:
        return default_tiers

    normalized: List[Dict[str, Any]] = []
    for raw in entry_price_tiers:
        if not isinstance(raw, dict):
            continue
        name = str(raw.get("name") or "").strip()
        if not name or name == "unknown":
            continue

        min_value = _safe_float(raw.get("min"))
        max_value = _safe_float(raw.get("max"))
        tier: Dict[str, Any] = {"name": name}
        if min_value is not None:
            tier["min"] = min_value
        if max_value is not None:
            tier["max"] = max_value
        if "min" not in tier and "max" not in tier:
            continue
        if "min" in tier and "max" in tier and float(tier["min"]) >= float(tier["max"]):
            continue
        normalized.append(tier)

    if not normalized:
        return default_tiers
    return normalized


def _detect_league(position: Dict[str, Any]) -> str:
    market_slug = str(position.get("market_slug") or "").strip().lower()
    if not market_slug:
        return "unknown"
    league_code = market_slug.split("-", 1)[0]
    if league_code in LEAGUE_TO_SPORT and league_code != "unknown":
        return league_code
    return "unknown"


def _detect_sport(league: str) -> str:
    return LEAGUE_TO_SPORT.get(league, "unknown")


def _detect_market_type(position: Dict[str, Any]) -> str:
    question = str(position.get("question") or "")
    market_slug = str(position.get("market_slug") or "")
    haystack = f"{question} {market_slug}".lower()

    if any(hint in haystack for hint in MARKET_TYPE_SPREAD_HINTS):
        return "spread"
    if any(hint in haystack for hint in MARKET_TYPE_TOTAL_HINTS):
        return "total"
    if MONEYLINE_WILL_WIN_PATTERN.search(question):
        return "moneyline"
    league = _detect_league(position)
    if league == "unknown":
        return "unknown"
    if not MATCHUP_VS_PATTERN.search(haystack):
        return "unknown"
    if any(hint in haystack for hint in MARKET_TYPE_PROP_HINTS):
        return "unknown"
    return "moneyline"


def _classify_entry_price_tier(entry_price: Optional[float], tiers: List[Dict[str, Any]]) -> str:
    if entry_price is None:
        return "unknown"
    for tier in tiers:
        min_value = _safe_float(tier.get("min"))
        max_value = _safe_float(tier.get("max"))
        if min_value is not None and entry_price < min_value:
            continue
        if max_value is not None and entry_price >= max_value:
            continue
        return str(tier["name"])
    return "unknown"


def _empty_segment_bucket() -> Dict[str, Any]:
    return {
        "count": 0,
        "wins": 0,
        "losses": 0,
        "profit_exits": 0,
        "loss_exits": 0,
        "total_pnl_gross": 0.0,
        "total_pnl_net": 0.0,
        # Count-weighted CLV
        "clv_pct_sum": 0.0,
        "clv_pct_count": 0,
        "beat_close_true_count": 0,
        "beat_close_count": 0,
        # Count-weighted entry drift
        "entry_drift_pct_sum": 0.0,
        "entry_drift_pct_count": 0,
        # Movement direction counts
        "movement_up_count": 0,
        "movement_down_count": 0,
        "movement_flat_count": 0,
        # Minutes to close
        "minutes_to_close_sum": 0.0,
        "minutes_to_close_count": 0,
        "_minutes_to_close_values": [],  # raw list for median; not emitted in finalized output
        # Notional-weighted accumulators
        "notional_w_total_weight": 0.0,
        "notional_w_clv_pct_sum": 0.0,
        "notional_w_clv_pct_weight": 0.0,
        "notional_w_beat_close_sum": 0.0,
        "notional_w_beat_close_weight": 0.0,
        "notional_w_entry_drift_pct_sum": 0.0,
        "notional_w_entry_drift_pct_weight": 0.0,
    }


def _accumulate_segment_bucket(
    bucket: Dict[str, Any],
    outcome: str,
    pnl_net: float,
    pnl_gross: float,
    clv_pct: Optional[float],
    beat_close: Optional[bool],
    entry_drift_pct: Optional[float] = None,
    movement_direction: Optional[str] = None,
    minutes_to_close: Optional[float] = None,
    position_notional_usd: Optional[float] = None,
) -> None:
    bucket["count"] += 1
    if outcome == "WIN":
        bucket["wins"] += 1
    elif outcome == "LOSS":
        bucket["losses"] += 1
    elif outcome == "PROFIT_EXIT":
        bucket["profit_exits"] += 1
    elif outcome == "LOSS_EXIT":
        bucket["loss_exits"] += 1
    bucket["total_pnl_gross"] += pnl_gross
    bucket["total_pnl_net"] += pnl_net

    # Count-weighted CLV + beat_close
    if clv_pct is not None:
        bucket["clv_pct_sum"] += clv_pct
        bucket["clv_pct_count"] += 1
    if isinstance(beat_close, bool):
        bucket["beat_close_count"] += 1
        if beat_close:
            bucket["beat_close_true_count"] += 1

    # Count-weighted entry drift
    if entry_drift_pct is not None:
        bucket["entry_drift_pct_sum"] += entry_drift_pct
        bucket["entry_drift_pct_count"] += 1

    # Movement direction
    md = (movement_direction or "").strip().lower()
    if md == "up":
        bucket["movement_up_count"] += 1
    elif md == "down":
        bucket["movement_down_count"] += 1
    elif md == "flat":
        bucket["movement_flat_count"] += 1

    # Minutes to close
    if minutes_to_close is not None:
        bucket["minutes_to_close_sum"] += float(minutes_to_close)
        bucket["minutes_to_close_count"] += 1
        bucket["_minutes_to_close_values"].append(float(minutes_to_close))

    # Notional-weighted accumulators (skip if notional is missing or zero)
    if position_notional_usd is not None and position_notional_usd > 0:
        w = float(position_notional_usd)
        bucket["notional_w_total_weight"] += w
        if clv_pct is not None:
            bucket["notional_w_clv_pct_sum"] += clv_pct * w
            bucket["notional_w_clv_pct_weight"] += w
        if isinstance(beat_close, bool):
            bucket["notional_w_beat_close_sum"] += (1.0 if beat_close else 0.0) * w
            bucket["notional_w_beat_close_weight"] += w
        if entry_drift_pct is not None:
            bucket["notional_w_entry_drift_pct_sum"] += entry_drift_pct * w
            bucket["notional_w_entry_drift_pct_weight"] += w


def _compute_median(values: List[float]) -> Optional[float]:
    """Return median of a sorted-or-unsorted list, or None if empty."""
    if not values:
        return None
    sorted_vals = sorted(values)
    n = len(sorted_vals)
    mid = n // 2
    if n % 2 == 1:
        return sorted_vals[mid]
    return round((sorted_vals[mid - 1] + sorted_vals[mid]) / 2.0, 6)


def _finalize_segment_bucket(bucket: Dict[str, Any]) -> Dict[str, Any]:
    wins = int(bucket.get("wins") or 0)
    losses = int(bucket.get("losses") or 0)
    profit_exits = int(bucket.get("profit_exits") or 0)
    loss_exits = int(bucket.get("loss_exits") or 0)
    total_count = int(bucket.get("count") or 0)
    denominator = wins + losses + profit_exits + loss_exits
    numerator = wins + profit_exits

    # Count-weighted CLV
    clv_pct_count = int(bucket.get("clv_pct_count") or 0)
    beat_close_count = int(bucket.get("beat_close_count") or 0)
    beat_close_true_count = int(bucket.get("beat_close_true_count") or 0)
    clv_pct_sum = float(bucket.get("clv_pct_sum") or 0.0)

    # Count-weighted entry drift
    entry_drift_pct_count = int(bucket.get("entry_drift_pct_count") or 0)
    entry_drift_pct_sum = float(bucket.get("entry_drift_pct_sum") or 0.0)

    # Movement counts → rates (denominator = total_count; partition is exact)
    movement_up_count = int(bucket.get("movement_up_count") or 0)
    movement_down_count = int(bucket.get("movement_down_count") or 0)
    movement_flat_count = int(bucket.get("movement_flat_count") or 0)
    movement_unknown_count = total_count - movement_up_count - movement_down_count - movement_flat_count

    # Minutes to close
    minutes_to_close_count = int(bucket.get("minutes_to_close_count") or 0)
    minutes_to_close_sum = float(bucket.get("minutes_to_close_sum") or 0.0)
    minutes_to_close_values: List[float] = list(bucket.get("_minutes_to_close_values") or [])

    # Notional-weighted accumulators
    notional_w_total_weight = float(bucket.get("notional_w_total_weight") or 0.0)
    notional_w_clv_pct_sum = float(bucket.get("notional_w_clv_pct_sum") or 0.0)
    notional_w_clv_pct_weight = float(bucket.get("notional_w_clv_pct_weight") or 0.0)
    notional_w_beat_close_sum = float(bucket.get("notional_w_beat_close_sum") or 0.0)
    notional_w_beat_close_weight = float(bucket.get("notional_w_beat_close_weight") or 0.0)
    notional_w_entry_drift_sum = float(bucket.get("notional_w_entry_drift_pct_sum") or 0.0)
    notional_w_entry_drift_weight = float(bucket.get("notional_w_entry_drift_pct_weight") or 0.0)

    # Derived count-weighted metrics
    avg_clv_pct = round(clv_pct_sum / clv_pct_count, 6) if clv_pct_count > 0 else None
    beat_close_rate = (_safe_pct(beat_close_true_count, beat_close_count)
                       if beat_close_count > 0 else None)
    avg_entry_drift_pct = (round(entry_drift_pct_sum / entry_drift_pct_count, 6)
                           if entry_drift_pct_count > 0 else None)

    # Movement rates (only meaningful when count > 0; partition of total_count)
    if total_count > 0:
        movement_up_rate: Optional[float] = round(movement_up_count / total_count, 6)
        movement_down_rate: Optional[float] = round(movement_down_count / total_count, 6)
        movement_flat_rate: Optional[float] = round(movement_flat_count / total_count, 6)
        movement_unknown_rate: Optional[float] = round(movement_unknown_count / total_count, 6)
    else:
        movement_up_rate = None
        movement_down_rate = None
        movement_flat_rate = None
        movement_unknown_rate = None

    avg_minutes_to_close = (round(minutes_to_close_sum / minutes_to_close_count, 6)
                            if minutes_to_close_count > 0 else None)
    median_minutes_to_close = _compute_median(minutes_to_close_values)

    # Derived notional-weighted metrics
    notional_weighted_avg_clv_pct = (
        round(notional_w_clv_pct_sum / notional_w_clv_pct_weight, 6)
        if notional_w_clv_pct_weight > 0 else None
    )
    notional_weighted_beat_close_rate = (
        round(notional_w_beat_close_sum / notional_w_beat_close_weight, 6)
        if notional_w_beat_close_weight > 0 else None
    )
    notional_weighted_avg_entry_drift_pct = (
        round(notional_w_entry_drift_sum / notional_w_entry_drift_weight, 6)
        if notional_w_entry_drift_weight > 0 else None
    )

    return {
        "count": total_count,
        "wins": wins,
        "losses": losses,
        "profit_exits": profit_exits,
        "loss_exits": loss_exits,
        "win_rate": _safe_pct(numerator, denominator),
        "total_pnl_gross": round(float(bucket.get("total_pnl_gross") or 0.0), 6),
        "total_pnl_net": round(float(bucket.get("total_pnl_net") or 0.0), 6),
        # Count-weighted
        "avg_clv_pct": avg_clv_pct,
        "avg_clv_pct_count_used": clv_pct_count,
        "beat_close_rate": beat_close_rate,
        "beat_close_rate_count_used": beat_close_count,
        "avg_entry_drift_pct": avg_entry_drift_pct,
        "avg_entry_drift_pct_count_used": entry_drift_pct_count,
        "movement_up_rate": movement_up_rate,
        "movement_down_rate": movement_down_rate,
        "movement_flat_rate": movement_flat_rate,
        "movement_unknown_rate": movement_unknown_rate,
        "avg_minutes_to_close": avg_minutes_to_close,
        "median_minutes_to_close": median_minutes_to_close,
        "minutes_to_close_count_used": minutes_to_close_count,
        # Notional-weighted
        "notional_weighted_avg_clv_pct": notional_weighted_avg_clv_pct,
        "notional_weighted_avg_clv_pct_weight_used": round(notional_w_clv_pct_weight, 6),
        "notional_weighted_beat_close_rate": notional_weighted_beat_close_rate,
        "notional_weighted_beat_close_rate_weight_used": round(notional_w_beat_close_weight, 6),
        "notional_weighted_avg_entry_drift_pct": notional_weighted_avg_entry_drift_pct,
        "notional_weighted_avg_entry_drift_pct_weight_used": round(notional_w_entry_drift_weight, 6),
        "notional_w_total_weight_used": round(notional_w_total_weight, 6),
    }


def _build_segment_analysis(
    positions: List[Dict[str, Any]],
    entry_price_tiers: Optional[List[Dict[str, Any]]],
) -> Dict[str, Any]:
    tiers = _normalize_entry_price_tiers(entry_price_tiers)
    tier_names = [str(tier["name"]) for tier in tiers]

    by_entry_price_tier_raw: Dict[str, Dict[str, Any]] = {
        name: _empty_segment_bucket() for name in tier_names
    }
    by_entry_price_tier_raw["unknown"] = _empty_segment_bucket()

    by_market_type_raw: Dict[str, Dict[str, Any]] = {
        "moneyline": _empty_segment_bucket(),
        "spread": _empty_segment_bucket(),
        "total": _empty_segment_bucket(),
        "unknown": _empty_segment_bucket(),
    }

    by_league_raw: Dict[str, Dict[str, Any]] = {"unknown": _empty_segment_bucket()}
    by_sport_raw: Dict[str, Dict[str, Any]] = {"unknown": _empty_segment_bucket()}
    by_category_raw: Dict[str, Dict[str, Any]] = {_CATEGORY_UNKNOWN: _empty_segment_bucket()}
    by_market_slug_raw: Dict[str, Dict[str, Any]] = {}

    notional_weight_global_total = 0.0

    for position in positions:
        outcome = _normalize_outcome(position.get("resolution_outcome"))
        pnl_net = _safe_float(position.get("realized_pnl_net_estimated_fees"))
        if pnl_net is None:
            pnl_net = _safe_float(position.get("realized_pnl_net"))
        pnl_gross = _safe_float(position.get("gross_pnl"))
        clv_pct = _safe_float(position.get("clv_pct"))
        beat_close_raw = position.get("beat_close")
        beat_close = beat_close_raw if isinstance(beat_close_raw, bool) else None
        pnl_net_value = pnl_net if pnl_net is not None else 0.0
        pnl_gross_value = pnl_gross if pnl_gross is not None else 0.0

        # Hypothesis-ready: entry_drift_pct
        price_at_entry = _safe_float(position.get("price_at_entry"))
        price_1h_before_entry = _safe_float(position.get("price_1h_before_entry"))
        entry_drift_pct: Optional[float] = None
        if (price_at_entry is not None
                and price_1h_before_entry is not None
                and price_1h_before_entry > 0):
            entry_drift_pct = (price_at_entry - price_1h_before_entry) / price_1h_before_entry

        movement_direction = str(position.get("movement_direction") or "").strip().lower()
        minutes_to_close = _safe_float(position.get("minutes_to_close"))
        position_notional_usd = extract_position_notional_usd(position)
        if position_notional_usd is not None:
            notional_weight_global_total += position_notional_usd

        league = _detect_league(position)
        sport = _detect_sport(league)
        market_type = _detect_market_type(position)
        entry_price = _safe_float(position.get("entry_price"))
        entry_price_tier = _classify_entry_price_tier(entry_price, tiers)
        category_key = _get_category_key(position)
        market_slug = str(position.get("market_slug") or "").strip() or "unknown"

        by_league_raw.setdefault(league, _empty_segment_bucket())
        by_sport_raw.setdefault(sport, _empty_segment_bucket())
        by_market_type_raw.setdefault(market_type, _empty_segment_bucket())
        by_entry_price_tier_raw.setdefault(entry_price_tier, _empty_segment_bucket())
        by_category_raw.setdefault(category_key, _empty_segment_bucket())
        by_market_slug_raw.setdefault(market_slug, _empty_segment_bucket())

        _accumulate_segment_bucket(
            by_entry_price_tier_raw[entry_price_tier],
            outcome, pnl_net_value, pnl_gross_value, clv_pct, beat_close,
            entry_drift_pct=entry_drift_pct,
            movement_direction=movement_direction,
            minutes_to_close=minutes_to_close,
            position_notional_usd=position_notional_usd,
        )
        _accumulate_segment_bucket(
            by_market_type_raw[market_type],
            outcome, pnl_net_value, pnl_gross_value, clv_pct, beat_close,
            entry_drift_pct=entry_drift_pct,
            movement_direction=movement_direction,
            minutes_to_close=minutes_to_close,
            position_notional_usd=position_notional_usd,
        )
        _accumulate_segment_bucket(
            by_league_raw[league],
            outcome, pnl_net_value, pnl_gross_value, clv_pct, beat_close,
            entry_drift_pct=entry_drift_pct,
            movement_direction=movement_direction,
            minutes_to_close=minutes_to_close,
            position_notional_usd=position_notional_usd,
        )
        _accumulate_segment_bucket(
            by_sport_raw[sport],
            outcome, pnl_net_value, pnl_gross_value, clv_pct, beat_close,
            entry_drift_pct=entry_drift_pct,
            movement_direction=movement_direction,
            minutes_to_close=minutes_to_close,
            position_notional_usd=position_notional_usd,
        )
        _accumulate_segment_bucket(
            by_category_raw[category_key],
            outcome, pnl_net_value, pnl_gross_value, clv_pct, beat_close,
            entry_drift_pct=entry_drift_pct,
            movement_direction=movement_direction,
            minutes_to_close=minutes_to_close,
            position_notional_usd=position_notional_usd,
        )
        _accumulate_segment_bucket(
            by_market_slug_raw[market_slug],
            outcome, pnl_net_value, pnl_gross_value, clv_pct, beat_close,
            entry_drift_pct=entry_drift_pct,
            movement_direction=movement_direction,
            minutes_to_close=minutes_to_close,
            position_notional_usd=position_notional_usd,
        )

    by_entry_price_tier = {
        name: _finalize_segment_bucket(by_entry_price_tier_raw[name])
        for name in tier_names + ["unknown"]
    }
    by_market_type = {
        name: _finalize_segment_bucket(by_market_type_raw[name])
        for name in ("moneyline", "spread", "total", "unknown")
    }

    league_keys = sorted(k for k in by_league_raw.keys() if k != "unknown")
    league_keys.append("unknown")
    by_league = {name: _finalize_segment_bucket(by_league_raw[name]) for name in league_keys}

    sport_keys = sorted(k for k in by_sport_raw.keys() if k != "unknown")
    sport_keys.append("unknown")
    by_sport = {name: _finalize_segment_bucket(by_sport_raw[name]) for name in sport_keys}

    # by_category: Unknown bucket always last, others alphabetically
    cat_keys = sorted(k for k in by_category_raw.keys() if k != _CATEGORY_UNKNOWN)
    cat_keys.append(_CATEGORY_UNKNOWN)
    by_category = {name: _finalize_segment_bucket(by_category_raw[name]) for name in cat_keys}

    # by_market_slug: top-N tables (deterministic: sort by pnl desc then slug asc)
    finalized_slugs = {
        slug: _finalize_segment_bucket(bucket)
        for slug, bucket in by_market_slug_raw.items()
    }
    _TOP_N = 10
    def _market_row(slug: str, metrics: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "market_slug": slug,
            "count": _coerce_int(metrics.get("count")),
            "win_rate": float(metrics.get("win_rate") or 0.0),
            "total_pnl_net": round(float(metrics.get("total_pnl_net") or 0.0), 6),
        }

    top_by_total_pnl_net = [
        _market_row(slug, metrics)
        for slug, metrics in sorted(
            finalized_slugs.items(),
            key=lambda item: (-item[1]["total_pnl_net"], item[0]),
        )[:_TOP_N]
    ]
    top_by_count = [
        _market_row(slug, metrics)
        for slug, metrics in sorted(
            finalized_slugs.items(),
            key=lambda item: (-item[1]["count"], item[0]),
        )[:_TOP_N]
    ]

    return {
        "entry_price_tiers": tiers,
        "by_entry_price_tier": by_entry_price_tier,
        "by_market_type": by_market_type,
        "by_league": by_league,
        "by_sport": by_sport,
        "by_category": by_category,
        "by_market_slug": {
            "top_by_total_pnl_net": top_by_total_pnl_net,
            "top_by_count": top_by_count,
        },
        "hypothesis_meta": {
            "notional_weight_total_global": round(notional_weight_global_total, 6),
            "min_count_threshold": TOP_SEGMENT_MIN_COUNT,
        },
    }


def _collect_top_segments_by_metric(
    segment_analysis: Dict[str, Any],
    metric_key: str,
    top_n: int = 5,
    min_count: int = TOP_SEGMENT_MIN_COUNT,
) -> List[Dict[str, Any]]:
    """Return top N segment buckets by *metric_key* (desc), breaking ties by segment name (asc).

    Skips buckets with count < *min_count* or where the metric is None.
    Covers the five standard dimensions (not by_market_slug).
    """
    dimensions = (
        ("entry_price_tier", "by_entry_price_tier"),
        ("market_type", "by_market_type"),
        ("league", "by_league"),
        ("sport", "by_sport"),
        ("category", "by_category"),
    )
    rows: List[Dict[str, Any]] = []
    for dimension_label, field in dimensions:
        buckets = segment_analysis.get(field)
        if not isinstance(buckets, dict):
            continue
        for bucket_name, metrics in buckets.items():
            if not isinstance(metrics, dict):
                continue
            count = _coerce_int(metrics.get("count"))
            if count < min_count:
                continue
            value = _safe_float(metrics.get(metric_key))
            if value is None:
                continue
            rows.append({
                "segment": f"{dimension_label}:{bucket_name}",
                "count": count,
                metric_key: value,
            })

    rows.sort(key=lambda row: (-row[metric_key], row["segment"]))
    return rows[:top_n]


_DIMENSION_FIELD_MAP: Dict[str, str] = {
    "entry_price_tier": "by_entry_price_tier",
    "market_type": "by_market_type",
    "league": "by_league",
    "sport": "by_sport",
    "category": "by_category",
}


def _build_hypothesis_candidates(
    segment_analysis: Dict[str, Any],
    top_n: int = 5,
) -> List[Dict[str, Any]]:
    """Build top-N hypothesis candidate entries from segment_analysis.

    Ranks segments by notional_weighted_avg_clv_pct desc (primary),
    notional_weighted_beat_close_rate desc (secondary), segment_key asc (tertiary).
    Only includes segments with count >= TOP_SEGMENT_MIN_COUNT and a non-None
    notional_weighted_avg_clv_pct (or count-weighted fallback when weight is zero).

    Returns a list of up to top_n candidate dicts.
    """
    if not segment_analysis:
        return []

    # Collect all qualifying segments across the five dimensions.
    candidates_raw: List[Dict[str, Any]] = []
    for dimension_label, field in _DIMENSION_FIELD_MAP.items():
        buckets = segment_analysis.get(field)
        if not isinstance(buckets, dict):
            continue
        for bucket_name, metrics in buckets.items():
            if not isinstance(metrics, dict):
                continue
            count = _coerce_int(metrics.get("count"))
            if count < TOP_SEGMENT_MIN_COUNT:
                continue
            notional_clv = _safe_float(metrics.get("notional_weighted_avg_clv_pct"))
            notional_clv_weight = _safe_float(
                metrics.get("notional_weighted_avg_clv_pct_weight_used")
            ) or 0.0
            # Use count-weighted fallback if notional weight is 0
            if notional_clv is None:
                fallback_clv = _safe_float(metrics.get("avg_clv_pct"))
                if fallback_clv is None:
                    continue
                rank_clv = fallback_clv
                weighting = "count"
            else:
                rank_clv = notional_clv
                weighting = "count" if notional_clv_weight == 0.0 else "notional"

            notional_beat = _safe_float(metrics.get("notional_weighted_beat_close_rate"))

            candidates_raw.append({
                "segment_key": f"{dimension_label}:{bucket_name}",
                "rank_clv": rank_clv,
                "rank_beat": notional_beat,
                "metrics_raw": metrics,
                "weighting": weighting,
                "notional_clv_weight": notional_clv_weight,
            })

    # Sort: notional_weighted_avg_clv_pct desc (None last), beat_close_rate desc (None last), key asc
    def _sort_key(c: Dict[str, Any]) -> tuple:
        clv = c["rank_clv"]
        beat = c["rank_beat"]
        return (
            0 if clv is None else -clv,
            0 if beat is None else -beat,
            c["segment_key"],
        )

    candidates_raw.sort(key=_sort_key)
    candidates_raw = candidates_raw[:top_n]

    # Build output structs
    result: List[Dict[str, Any]] = []
    for rank_idx, raw in enumerate(candidates_raw, start=1):
        m = raw["metrics_raw"]
        count = _coerce_int(m.get("count"))
        notional_clv_weight = raw["notional_clv_weight"]
        weighting = raw["weighting"]

        metrics_out: Dict[str, Any] = {
            "notional_weighted_avg_clv_pct": _safe_float(m.get("notional_weighted_avg_clv_pct")),
            "notional_weighted_avg_clv_pct_weight_used": float(
                m.get("notional_weighted_avg_clv_pct_weight_used") or 0.0
            ),
            "notional_weighted_beat_close_rate": _safe_float(
                m.get("notional_weighted_beat_close_rate")
            ),
            "notional_weighted_beat_close_rate_weight_used": float(
                m.get("notional_weighted_beat_close_rate_weight_used") or 0.0
            ),
            "avg_clv_pct": _safe_float(m.get("avg_clv_pct")),
            "avg_clv_pct_count_used": _coerce_int(m.get("avg_clv_pct_count_used")),
            "beat_close_rate": _safe_float(m.get("beat_close_rate")),
            "beat_close_rate_count_used": _coerce_int(m.get("beat_close_rate_count_used")),
            "avg_entry_drift_pct": _safe_float(m.get("avg_entry_drift_pct")),
            "avg_entry_drift_pct_count_used": _coerce_int(m.get("avg_entry_drift_pct_count_used")),
            "avg_minutes_to_close": _safe_float(m.get("avg_minutes_to_close")),
            "median_minutes_to_close": _safe_float(m.get("median_minutes_to_close")),
            "minutes_to_close_count_used": _coerce_int(m.get("minutes_to_close_count_used")),
            "win_rate": float(m.get("win_rate") or 0.0),
            "count": count,
        }

        denominators: Dict[str, Any] = {
            "count_used": count,
            "weight_used": notional_clv_weight,
            "weighting": weighting,
        }

        falsification_plan: Dict[str, Any] = {
            "min_sample_size": max(30, count * 2),
            "min_coverage_rate": 0.80,
            "stop_conditions": [
                "notional_weighted_avg_clv_pct < 0 for 2 consecutive future periods",
                f"count drops below {TOP_SEGMENT_MIN_COUNT} in a future run",
            ],
        }

        result.append({
            "segment_key": raw["segment_key"],
            "rank": rank_idx,
            "metrics": metrics_out,
            "denominators": denominators,
            "falsification_plan": falsification_plan,
        })

    return result


def write_hypothesis_candidates(
    candidates: List[Dict[str, Any]],
    output_dir: Path,
    generated_at: str,
    run_id: str,
    user_slug: str,
    wallet: str,
) -> str:
    """Write hypothesis_candidates.json to output_dir.

    Returns the POSIX path of the written file.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    envelope = {
        "generated_at": generated_at,
        "run_id": run_id,
        "user_slug": user_slug,
        "wallet": wallet,
        "candidates": candidates,
    }
    path = output_dir / "hypothesis_candidates.json"
    path.write_text(
        json.dumps(envelope, indent=2, sort_keys=True, allow_nan=False),
        encoding="utf-8",
    )
    return path.as_posix()


def _render_hypothesis_candidates(report: Dict[str, Any]) -> List[str]:
    """Render the Hypothesis Candidates markdown section."""
    lines: List[str] = []
    lines.append("## Hypothesis Candidates")
    lines.append("")

    candidates = report.get("hypothesis_candidates")
    if not candidates:
        lines.append(
            "- None (no segments meet the minimum count threshold or lack "
            "notional-weighted CLV data)."
        )
        lines.append("")
        return lines

    # Summary table
    lines.append(
        "| Rank | Segment | Count | Notional-Wt CLV% | Notional-Wt Beat-Close | Weighting | Min Sample |"
    )
    lines.append("| ---: | --- | ---: | ---: | ---: | --- | ---: |")
    for c in candidates:
        m = c.get("metrics", {})
        d = c.get("denominators", {})
        fp = c.get("falsification_plan", {})
        nw_clv = m.get("notional_weighted_avg_clv_pct")
        nw_beat = m.get("notional_weighted_beat_close_rate")
        lines.append(
            f"| {c['rank']} | {c['segment_key']} | {m.get('count', 0)} | "
            f"{'N/A' if nw_clv is None else f'{nw_clv:.4f}'} | "
            f"{'N/A' if nw_beat is None else f'{nw_beat:.4f}'} | "
            f"{d.get('weighting', 'N/A')} | {fp.get('min_sample_size', 'N/A')} |"
        )
    lines.append("")

    # Per-candidate falsification details
    for c in candidates:
        fp = c.get("falsification_plan", {})
        lines.append(f"### Candidate {c['rank']}: {c['segment_key']}")
        lines.append("")
        lines.append(f"- **min_sample_size**: {fp.get('min_sample_size', 'N/A')}")
        lines.append(f"- **min_coverage_rate**: {fp.get('min_coverage_rate', 'N/A')}")
        stop_conditions = fp.get("stop_conditions") or []
        if stop_conditions:
            lines.append("- **stop_conditions**:")
            for sc in stop_conditions:
                lines.append(f"  - {sc}")
        lines.append("")

    return lines


def _collect_segment_rankings(segment_analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
    ranked: List[Dict[str, Any]] = []
    dimensions = (
        ("entry_price_tier", "by_entry_price_tier"),
        ("market_type", "by_market_type"),
        ("league", "by_league"),
        ("sport", "by_sport"),
        ("category", "by_category"),
    )
    for dimension_label, field in dimensions:
        buckets = segment_analysis.get(field)
        if not isinstance(buckets, dict):
            continue
        for bucket_name, metrics in buckets.items():
            if not isinstance(metrics, dict):
                continue
            total_pnl_net = _safe_float(metrics.get("total_pnl_net"))
            total_pnl_gross = _safe_float(metrics.get("total_pnl_gross"))
            if total_pnl_net is None:
                continue
            ranked.append({
                "segment": f"{dimension_label}:{bucket_name}",
                "count": _coerce_int(metrics.get("count")),
                "total_pnl_net": round(total_pnl_net, 6),
                "total_pnl_gross": round(total_pnl_gross or 0.0, 6),
            })

    ranked.sort(key=lambda row: (-row["total_pnl_net"], row["segment"]))
    return ranked


def normalize_fee_fields(
    position: Dict[str, Any],
    fee_config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Ensure every position has explicit fee sourcing.

    Rules:
      - If ``gross_pnl`` > 0:
          fees_estimated = gross_pnl * profit_fee_rate
          fees_source = source_label
      - Else:
          fees_estimated = 0.0
          fees_source = "not_applicable"

    Also materializes ``realized_pnl_net_estimated_fees``:

      gross_pnl - fees_estimated

    Returns the position dict (mutated in place for convenience).
    """
    normalized_fee_config = _normalize_fee_config(fee_config)
    profit_fee_rate = float(normalized_fee_config["profit_fee_rate"])
    source_label = str(normalized_fee_config["source_label"])

    gross_pnl = _safe_float(position.get("gross_pnl"))
    if gross_pnl is None:
        gross_pnl = _safe_float(position.get("realized_pnl_net"))
    gross_pnl = gross_pnl if gross_pnl is not None else 0.0

    fees_actual = _safe_float(position.get("fees_actual"))
    if fees_actual is None:
        fees_actual = 0.0

    if gross_pnl > 0:
        fees_estimated = gross_pnl * profit_fee_rate
        fees_source = source_label
    else:
        fees_estimated = 0.0
        fees_source = NOT_APPLICABLE_FEE_SOURCE

    realized_net_estimated_fees = gross_pnl - fees_estimated

    position["gross_pnl"] = round(gross_pnl, 6)
    position["fees_actual"] = round(fees_actual, 6)
    position["fees_estimated"] = round(fees_estimated, 6)
    position["fees_source"] = fees_source
    position["realized_pnl_net_estimated_fees"] = round(realized_net_estimated_fees, 6)
    return position


def build_coverage_report(
    positions: List[Dict[str, Any]],
    run_id: str,
    user_slug: str,
    wallet: str,
    proxy_wallet: Optional[str] = None,
    resolution_enrichment_response: Optional[Dict[str, Any]] = None,
    entry_price_tiers: Optional[List[Dict[str, Any]]] = None,
    fee_config: Optional[Dict[str, Any]] = None,
    market_metadata_map: Optional[Dict[str, Dict[str, str]]] = None,
    metadata_conflicts_count: int = 0,
    metadata_conflict_sample: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Build a Coverage & Reconciliation Report from position lifecycle data.

    Parameters
    ----------
    positions : list[dict]
        Position lifecycle records, each expected to carry at minimum:
        ``resolution_outcome``, ``trade_uid`` and/or fallback identifiers
        (for example ``resolved_token_id``),
        ``realized_pnl_net``, ``fees_actual``, ``fees_estimated``,
        ``fees_source``, ``position_remaining``.
    run_id : str
        Unique identifier for this examination run.
    user_slug : str
        Canonical user slug.
    wallet : str
        Primary wallet address.
    proxy_wallet : str | None
        Proxy wallet if different from *wallet*.
    resolution_enrichment_response : dict | None
        Optional enrichment summary payload used for diagnostics-only warnings.
    """
    effective_fee_config = _normalize_fee_config(fee_config)

    # --- Snapshot which positions already have category (before backfill) ---
    had_category_before: set = {
        i for i, pos in enumerate(positions)
        if str(pos.get("category") or "").strip()
    }

    # --- Backfill missing market metadata + category from local mapping (deterministic, no network) ---
    backfilled_indices = backfill_market_metadata(positions, market_metadata_map)

    # --- Determine which positions had category filled by backfill ---
    has_category_after: set = {
        i for i, pos in enumerate(positions)
        if str(pos.get("category") or "").strip()
    }
    backfilled_category_indices: set = has_category_after - had_category_before

    # --- Pre-normalize settlement + fees on every position first ---
    for pos in positions:
        outcome = pos.get("resolution_outcome", "UNKNOWN_RESOLUTION")
        if outcome == "PENDING":
            pos["settlement_price"] = None
            if not pos.get("resolved_at"):
                pos["resolved_at"] = None
            if _coerce_int(pos.get("sell_count")) == 0:
                pos["gross_pnl"] = 0.0
                pos["realized_pnl_net"] = 0.0

        normalize_fee_fields(pos, fee_config=effective_fee_config)

    total = len(positions)

    # --- Outcome counts ---
    outcome_counter: Counter = Counter()
    for pos in positions:
        outcome = pos.get("resolution_outcome", "UNKNOWN_RESOLUTION")
        if outcome not in KNOWN_OUTCOMES:
            outcome = "UNKNOWN_RESOLUTION"
        outcome_counter[outcome] += 1

    outcome_counts = {k: outcome_counter.get(k, 0) for k in sorted(KNOWN_OUTCOMES)}
    outcome_pcts = {k: _safe_pct(v, total) for k, v in outcome_counts.items()}

    # --- UID coverage ---
    deterministic_trade_uids: List[str] = []
    fallback_uids: List[str] = []

    for pos in positions:
        trade_uid = str(pos.get("trade_uid") or "").strip()
        deterministic_trade_uids.append(trade_uid)

        fallback_uid = ""
        for key in ("resolved_token_id", "token_id", "condition_id"):
            value = str(pos.get(key) or "").strip()
            if value:
                fallback_uid = value
                break
        fallback_uids.append(fallback_uid)

    deterministic_with_uid = sum(1 for uid in deterministic_trade_uids if uid)
    deterministic_uid_counter = Counter(uid for uid in deterministic_trade_uids if uid)
    deterministic_duplicates = {
        uid: cnt for uid, cnt in deterministic_uid_counter.items() if cnt > 1
    }
    deterministic_dup_sample = list(deterministic_duplicates.keys())[:5]

    fallback_with_uid = sum(1 for uid in fallback_uids if uid)
    fallback_only_count = sum(
        1
        for deterministic_uid, fallback_uid in zip(deterministic_trade_uids, fallback_uids)
        if (not deterministic_uid) and fallback_uid
    )

    deterministic_trade_uid_coverage = {
        "total": total,
        "with_trade_uid": deterministic_with_uid,
        "pct_with_trade_uid": _safe_pct(deterministic_with_uid, total),
        "duplicate_trade_uid_count": len(deterministic_duplicates),
        "duplicate_sample": deterministic_dup_sample,
    }
    fallback_uid_coverage = {
        "total": total,
        "with_fallback_uid": fallback_with_uid,
        "pct_with_fallback_uid": _safe_pct(fallback_with_uid, total),
        "fallback_only_count": fallback_only_count,
        "pct_fallback_only": _safe_pct(fallback_only_count, total),
    }

    # --- PnL ---
    gross_total = 0.0
    gross_by_outcome: Dict[str, float] = {}
    estimated_net_total = 0.0
    estimated_net_by_outcome: Dict[str, float] = {}
    reported_net_total = 0.0
    reported_net_by_outcome: Dict[str, float] = {}
    missing_reported_pnl = 0

    for pos in positions:
        outcome = pos.get("resolution_outcome", "UNKNOWN_RESOLUTION")
        gross_pnl = _safe_float(pos.get("gross_pnl"))
        gross_pnl_value = gross_pnl if gross_pnl is not None else 0.0
        gross_total += gross_pnl_value
        gross_by_outcome[outcome] = gross_by_outcome.get(outcome, 0.0) + gross_pnl_value

        pnl_estimated = _safe_float(pos.get("realized_pnl_net_estimated_fees"))
        if pnl_estimated is None:
            pnl_estimated = gross_pnl_value - float(pos.get("fees_estimated") or 0.0)
        estimated_net_total += pnl_estimated
        estimated_net_by_outcome[outcome] = estimated_net_by_outcome.get(outcome, 0.0) + pnl_estimated

        pnl_reported = _safe_float(pos.get("realized_pnl_net"))
        if pnl_reported is None:
            missing_reported_pnl += 1
            continue
        reported_net_total += pnl_reported
        reported_net_by_outcome[outcome] = reported_net_by_outcome.get(outcome, 0.0) + pnl_reported

    pnl_section = {
        "gross_pnl_total": round(gross_total, 6),
        "gross_pnl_by_outcome": {k: round(v, 6) for k, v in sorted(gross_by_outcome.items())},
        "realized_pnl_net_total": round(estimated_net_total, 6),
        "realized_pnl_net_by_outcome": {k: round(v, 6) for k, v in sorted(estimated_net_by_outcome.items())},
        "realized_pnl_net_estimated_fees_total": round(estimated_net_total, 6),
        "realized_pnl_net_estimated_fees_by_outcome": {
            k: round(v, 6) for k, v in sorted(estimated_net_by_outcome.items())
        },
        "reported_realized_pnl_net_total": round(reported_net_total, 6),
        "reported_realized_pnl_net_by_outcome": {
            k: round(v, 6) for k, v in sorted(reported_net_by_outcome.items())
        },
        "missing_realized_pnl_count": missing_reported_pnl,
    }

    # --- Fees ---
    fee_source_counter: Counter = Counter()
    fees_actual_count = 0
    fees_estimated_count = 0

    for pos in positions:
        src = pos.get("fees_source", "unknown")
        fee_source_counter[src] += 1
        if float(pos.get("fees_actual") or 0) > 0:
            fees_actual_count += 1
        if float(pos.get("fees_estimated") or 0) > 0:
            fees_estimated_count += 1

    fee_source_counts = dict(fee_source_counter)
    fee_source_counts.setdefault(str(effective_fee_config["source_label"]), 0)
    fee_source_counts.setdefault(NOT_APPLICABLE_FEE_SOURCE, 0)

    fees_section = {
        "fees_source_counts": fee_source_counts,
        "fees_actual_present_count": fees_actual_count,
        "fees_estimated_present_count": fees_estimated_count,
    }

    # --- Resolution coverage ---
    pending = outcome_counts.get("PENDING", 0)
    unknown = outcome_counts.get("UNKNOWN_RESOLUTION", 0)
    resolved_total = total - pending

    # Held-to-resolution: position_remaining > 0 at settlement time
    held_to_resolution = sum(
        1 for pos in positions
        if float(pos.get("position_remaining") or 0) > 0
        and pos.get("resolution_outcome") not in ("PENDING", "UNKNOWN_RESOLUTION")
    )
    win_loss = outcome_counts.get("WIN", 0) + outcome_counts.get("LOSS", 0)
    win_loss_covered_rate = _safe_pct(win_loss, held_to_resolution) if held_to_resolution else 0.0

    resolution_section = {
        "resolved_total": resolved_total,
        "unknown_resolution_total": unknown,
        "unknown_resolution_rate": _safe_pct(unknown, total),
        "held_to_resolution_total": held_to_resolution,
        "win_loss_covered_rate": win_loss_covered_rate,
    }

    # --- Warnings ---
    warnings: List[str] = []
    if deterministic_trade_uid_coverage["duplicate_trade_uid_count"] > 0:
        warnings.append(
            f"Found {deterministic_trade_uid_coverage['duplicate_trade_uid_count']} duplicate deterministic trade UIDs"
        )
    if _safe_pct(unknown, total) > 0.05 and total > 0:
        warnings.append(
            f"UNKNOWN_RESOLUTION rate is {_safe_pct(unknown, total):.1%}, above 5% threshold"
        )
    if missing_reported_pnl > 0:
        warnings.append(f"{missing_reported_pnl} positions missing realized_pnl_net")

    pending_count = outcome_counts.get("PENDING", 0)
    pending_pct = outcome_pcts.get("PENDING", 0.0)
    fallback_pct = float(fallback_uid_coverage.get("pct_with_fallback_uid") or 0.0)
    pending_distribution_is_all = pending_count == total or pending_pct >= 1.0
    pending_coverage_invalid = (
        total > 0
        and fallback_pct >= 0.95
        and resolution_section.get("resolved_total", 0) == 0
        and pending_distribution_is_all
    )
    if pending_coverage_invalid:
        warning = PENDING_COVERAGE_INVALID_WARNING
        if bool((resolution_enrichment_response or {}).get("truncated")):
            warning = f"{warning} Enrichment response reported truncated=true."
        warnings.append(warning)

    segment_analysis = _build_segment_analysis(
        positions=positions,
        entry_price_tiers=entry_price_tiers,
    )
    hypothesis_candidates = _build_hypothesis_candidates(segment_analysis)

    market_metadata_coverage = _build_market_metadata_coverage(
        positions,
        backfilled_indices,
        metadata_conflicts_count=metadata_conflicts_count,
        metadata_conflict_sample=metadata_conflict_sample,
    )

    missing_meta_count = market_metadata_coverage["missing_count"]
    missing_meta_rate = _safe_pct(missing_meta_count, total)
    if missing_meta_rate > 0.20 and total > 0:
        warnings.append(
            f"market_metadata_coverage missing rate is {missing_meta_rate:.1%} "
            f"({missing_meta_count}/{total} positions lack market_slug/question/outcome_name). "
            "Consider running with --ingest-markets or providing a market_metadata_map."
        )

    category_coverage = _build_category_coverage(positions, backfilled_category_indices)

    missing_cat_count = category_coverage["missing_count"]
    missing_cat_rate = _safe_pct(missing_cat_count, total)
    if missing_cat_rate > 0.20 and total > 0:
        warnings.append(
            f"category_coverage missing rate is {missing_cat_rate:.1%} "
            f"({missing_cat_count}/{total} positions lack a Polymarket category). "
            "Ensure market_metadata_map includes the 'category' field."
        )

    clv_coverage = _build_clv_coverage(positions)
    clv_eligible = int(clv_coverage.get("eligible_positions") or 0)
    clv_rate = float(clv_coverage.get("coverage_rate") or 0.0)
    if clv_eligible > 0 and clv_rate < 0.30:
        warnings.append(
            f"clv_coverage rate is {clv_rate:.1%} ({clv_coverage['clv_present_count']}/{clv_eligible}), "
            "below 30% threshold."
        )
    entry_context_coverage = _build_entry_context_coverage(positions)

    report = {
        "report_version": REPORT_VERSION,
        "generated_at": _now_utc(),
        "run_id": run_id,
        "user_slug": user_slug,
        "wallet": wallet,
        "proxy_wallet": proxy_wallet or wallet,
        "totals": {
            "positions_total": total,
        },
        "outcome_counts": outcome_counts,
        "outcome_percentages": outcome_pcts,
        "deterministic_trade_uid_coverage": deterministic_trade_uid_coverage,
        "fallback_uid_coverage": fallback_uid_coverage,
        "pnl": pnl_section,
        "fees": fees_section,
        "resolution_coverage": resolution_section,
        "market_metadata_coverage": market_metadata_coverage,
        "category_coverage": category_coverage,
        "clv_coverage": clv_coverage,
        "entry_context_coverage": entry_context_coverage,
        "segment_analysis": segment_analysis,
        "hypothesis_candidates": hypothesis_candidates,
        "warnings": warnings,
    }
    return report


def write_coverage_report(
    report: Dict[str, Any],
    output_dir: Path,
    write_markdown: bool = True,
) -> Dict[str, str]:
    """Write coverage report JSON (and optionally Markdown) to *output_dir*.

    Returns dict of written file paths.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    json_path = output_dir / "coverage_reconciliation_report.json"
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True, allow_nan=False), encoding="utf-8")

    paths: Dict[str, str] = {"json": json_path.as_posix()}

    if write_markdown:
        md_path = output_dir / "coverage_reconciliation_report.md"
        md_path.write_text(_render_markdown(report), encoding="utf-8")
        paths["md"] = md_path.as_posix()

    return paths


def _render_markdown(report: Dict[str, Any]) -> str:
    lines: List[str] = []
    lines.append("# Coverage & Reconciliation Report")
    lines.append("")
    lines.append(f"- **Run ID**: {report['run_id']}")
    lines.append(f"- **User**: {report['user_slug']}")
    lines.append(f"- **Wallet**: {report['wallet']}")
    lines.append(f"- **Generated**: {report['generated_at']}")
    lines.append(f"- **Positions**: {report['totals']['positions_total']}")
    lines.append("")

    lines.append("## Outcome Distribution")
    lines.append("")
    lines.append("| Outcome | Count | % |")
    lines.append("| --- | ---: | ---: |")
    for outcome in sorted(KNOWN_OUTCOMES):
        count = report["outcome_counts"].get(outcome, 0)
        pct = report["outcome_percentages"].get(outcome, 0)
        lines.append(f"| {outcome} | {count} | {pct:.2%} |")
    lines.append("")

    lines.append("## UID Coverage")
    deterministic = report["deterministic_trade_uid_coverage"]
    fallback = report["fallback_uid_coverage"]
    lines.append(
        f"- Deterministic trade_uid: {deterministic['with_trade_uid']} of {deterministic['total']} "
        f"({deterministic['pct_with_trade_uid']:.2%})"
    )
    lines.append(
        f"- Fallback UID (resolved_token_id/token_id/condition_id): {fallback['with_fallback_uid']} of "
        f"{fallback['total']} ({fallback['pct_with_fallback_uid']:.2%})"
    )
    lines.append(
        f"- Fallback-only rows: {fallback['fallback_only_count']} ({fallback['pct_fallback_only']:.2%})"
    )
    lines.append(f"- Duplicate deterministic trade_uids: {deterministic['duplicate_trade_uid_count']}")
    lines.append("")

    lines.append("## PnL Summary")
    pnl = report["pnl"]
    lines.append(f"- Gross PnL (total): {pnl['gross_pnl_total']:.6f}")
    lines.append(
        f"- Realized PnL (net after estimated fees, total): "
        f"{pnl['realized_pnl_net_estimated_fees_total']:.6f}"
    )
    lines.append(
        f"- Reported realized_pnl_net (source rows, total): "
        f"{pnl['reported_realized_pnl_net_total']:.6f}"
    )
    lines.append(f"- Missing reported realized_pnl_net: {pnl['missing_realized_pnl_count']}")
    lines.append("")

    lines.append("## Fee Sourcing")
    fees = report["fees"]
    for src, cnt in sorted(fees["fees_source_counts"].items()):
        lines.append(f"- {src}: {cnt}")
    lines.append(f"- fees_estimated_present_count: {fees['fees_estimated_present_count']}")
    lines.append("")

    lines.append("## Resolution Coverage")
    res = report["resolution_coverage"]
    lines.append(f"- Resolved: {res['resolved_total']}")
    lines.append(f"- Unknown resolution: {res['unknown_resolution_total']} ({res['unknown_resolution_rate']:.2%})")
    lines.append(f"- Held to resolution: {res['held_to_resolution_total']}")
    lines.append(f"- WIN+LOSS covered rate: {res['win_loss_covered_rate']:.2%}")
    lines.append("")

    lines.extend(_render_market_metadata_coverage(report))
    lines.extend(_render_category_coverage(report))
    lines.extend(_render_clv_coverage(report))
    lines.extend(_render_entry_context_coverage(report))
    lines.extend(_render_hypothesis_signals(report))
    lines.extend(_render_hypothesis_candidates(report))
    lines.extend(_render_segment_highlights(report))
    lines.extend(_render_top_categories(report))
    lines.extend(_render_top_markets(report))

    if report["warnings"]:
        lines.append("## Warnings")
        for w in report["warnings"]:
            lines.append(f"- {w}")
        lines.append("")

    return "\n".join(lines)


def _render_market_metadata_coverage(report: Dict[str, Any]) -> List[str]:
    lines: List[str] = []
    lines.append("## Market Metadata Coverage")
    lines.append("")

    mmc = report.get("market_metadata_coverage")
    if not isinstance(mmc, dict):
        lines.append("- Market metadata coverage unavailable.")
        lines.append("")
        return lines

    coverage_rate = float(mmc.get("coverage_rate") or 0.0)
    present = _coerce_int(mmc.get("present_count"))
    missing = _coerce_int(mmc.get("missing_count"))
    total = present + missing
    lines.append(f"- Coverage: {coverage_rate:.2%} ({present}/{total} positions have market metadata)")

    source_counts = mmc.get("source_counts") or {}
    lines.append(
        f"- Sources: ingested={source_counts.get('ingested', 0)}, "
        f"backfilled={source_counts.get('backfilled', 0)}, "
        f"unknown={source_counts.get('unknown', 0)}"
    )

    missing_rate = _safe_pct(missing, total) if total > 0 else 0.0
    if missing_rate > 0.20:
        lines.append(
            f"> **Warning:** {missing_rate:.1%} of positions lack market metadata. "
            "Run with --ingest-markets or provide a market_metadata_map."
        )

    conflicts = _coerce_int(mmc.get("metadata_conflicts_count"))
    if conflicts > 0:
        lines.append(
            f"> **Warning:** {conflicts} metadata map collision(s) detected "
            "(same token/condition ID found with different values — first entry kept). "
            "See `metadata_conflict_sample` in JSON report for details."
        )

    top_unmappable = mmc.get("top_unmappable") or []
    if top_unmappable:
        lines.append("")
        lines.append("### Top Unmappable IDs")
        for entry in top_unmappable[:5]:
            identifier_key = "token_id"
            identifier_value = str(entry.get("token_id") or "").strip()
            if not identifier_value:
                identifier_key = "condition_id"
                identifier_value = str(entry.get("condition_id") or "").strip() or "?"
            lines.append(
                f"- `{identifier_key}={identifier_value}`: {entry.get('count', 0)} occurrence(s)"
            )
    lines.append("")

    return lines


def _render_category_coverage(report: Dict[str, Any]) -> List[str]:
    lines: List[str] = []
    lines.append("## Category Coverage")
    lines.append("")

    cc = report.get("category_coverage")
    if not isinstance(cc, dict):
        lines.append("- Category coverage unavailable.")
        lines.append("")
        return lines

    coverage_rate = float(cc.get("coverage_rate") or 0.0)
    present = _coerce_int(cc.get("present_count"))
    missing = _coerce_int(cc.get("missing_count"))
    total = present + missing
    lines.append(f"- Coverage: {coverage_rate:.2%} ({present}/{total} positions have a Polymarket category)")

    source_counts = cc.get("source_counts") or {}
    lines.append(
        f"- Sources: ingested={source_counts.get('ingested', 0)}, "
        f"backfilled={source_counts.get('backfilled', 0)}, "
        f"unknown={source_counts.get('unknown', 0)}"
    )

    missing_rate = _safe_pct(missing, total) if total > 0 else 0.0
    if missing_rate > 0.20:
        lines.append(
            f"> **Warning:** {missing_rate:.1%} of positions lack a Polymarket category. "
            "Ensure the market_metadata_map includes the 'category' field."
        )

    top_unmappable = cc.get("top_unmappable") or []
    if top_unmappable:
        lines.append("")
        lines.append("### Top Unmappable (no category)")
        for entry in top_unmappable[:5]:
            identifier_key = "token_id"
            identifier_value = str(entry.get("token_id") or "").strip()
            if not identifier_value:
                identifier_key = "condition_id"
                identifier_value = str(entry.get("condition_id") or "").strip() or "?"
            lines.append(
                f"- `{identifier_key}={identifier_value}`: {entry.get('count', 0)} occurrence(s)"
            )
    lines.append("")

    return lines


def _render_clv_coverage(report: Dict[str, Any]) -> List[str]:
    lines: List[str] = []
    lines.append("## CLV Coverage")
    lines.append("")

    clv = report.get("clv_coverage")
    if not isinstance(clv, dict):
        lines.append("- CLV coverage unavailable.")
        lines.append("")
        return lines

    eligible = _coerce_int(clv.get("eligible_positions"))
    present = _coerce_int(clv.get("clv_present_count"))
    missing = _coerce_int(clv.get("clv_missing_count"))
    coverage_rate = float(clv.get("coverage_rate") or 0.0)
    lines.append(
        f"- Coverage: {coverage_rate:.2%} ({present}/{eligible} eligible positions with CLV)"
    )
    lines.append(f"- Missing: {missing}")

    close_ts_source_counts = clv.get("close_ts_source_counts") or {}
    if close_ts_source_counts:
        lines.append(
            f"- close_ts_source_counts: {json.dumps(close_ts_source_counts, sort_keys=True)}"
        )

    clv_source_counts = clv.get("clv_source_counts") or {}
    if clv_source_counts:
        lines.append(f"- clv_source_counts: {json.dumps(clv_source_counts, sort_keys=True)}")

    missing_reason_counts = clv.get("missing_reason_counts") or {}
    if missing_reason_counts:
        lines.append("- Top missing reasons:")
        for reason, count in sorted(
            missing_reason_counts.items(),
            key=lambda item: (-_coerce_int(item[1]), str(item[0])),
        )[:5]:
            lines.append(f"  - {reason}: {count}")

    if eligible > 0 and coverage_rate < 0.30:
        lines.append(
            f"> **Warning:** CLV coverage below 30% ({coverage_rate:.1%}; {present}/{eligible})."
        )

    lines.append("")
    return lines


def _render_entry_context_coverage(report: Dict[str, Any]) -> List[str]:
    lines: List[str] = []
    lines.append("## Entry Context Coverage")
    lines.append("")

    context = report.get("entry_context_coverage")
    if not isinstance(context, dict):
        lines.append("- Entry context coverage unavailable.")
        lines.append("")
        return lines

    eligible = _coerce_int(context.get("eligible_positions"))
    open_present = _coerce_int(context.get("open_price_present_count"))
    one_hour_present = _coerce_int(context.get("price_1h_before_entry_present_count"))
    at_entry_present = _coerce_int(context.get("price_at_entry_present_count"))
    movement_present = _coerce_int(context.get("movement_direction_present_count"))
    minutes_present = _coerce_int(context.get("minutes_to_close_present_count"))

    lines.append(f"- Eligible positions: {eligible}")
    lines.append(
        f"- open_price_present_count: {open_present} ({_safe_pct(open_present, eligible):.2%})"
        if eligible > 0
        else f"- open_price_present_count: {open_present}"
    )
    lines.append(
        f"- price_1h_before_entry_present_count: {one_hour_present} ({_safe_pct(one_hour_present, eligible):.2%})"
        if eligible > 0
        else f"- price_1h_before_entry_present_count: {one_hour_present}"
    )
    lines.append(
        f"- price_at_entry_present_count: {at_entry_present} ({_safe_pct(at_entry_present, eligible):.2%})"
        if eligible > 0
        else f"- price_at_entry_present_count: {at_entry_present}"
    )
    lines.append(
        f"- movement_direction_present_count: {movement_present} ({_safe_pct(movement_present, eligible):.2%})"
        if eligible > 0
        else f"- movement_direction_present_count: {movement_present}"
    )
    lines.append(
        f"- minutes_to_close_present_count: {minutes_present} ({_safe_pct(minutes_present, eligible):.2%})"
        if eligible > 0
        else f"- minutes_to_close_present_count: {minutes_present}"
    )

    missing_reason_counts = context.get("missing_reason_counts") or {}
    if missing_reason_counts:
        lines.append("- Top missing reasons:")
        for reason, count in sorted(
            missing_reason_counts.items(),
            key=lambda item: (-_coerce_int(item[1]), str(item[0])),
        )[:8]:
            lines.append(f"  - {reason}: {count}")
    lines.append("")

    return lines


def _render_top_categories(report: Dict[str, Any]) -> List[str]:
    lines: List[str] = []
    segment_analysis = report.get("segment_analysis")
    if not isinstance(segment_analysis, dict):
        return lines

    by_category = segment_analysis.get("by_category")
    if not isinstance(by_category, dict):
        return lines

    # Top 10 by total_pnl_net (desc), then category name (asc)
    rows = sorted(
        by_category.items(),
        key=lambda item: (-item[1].get("total_pnl_net", 0.0), item[0]),
    )[:10]

    if not rows:
        return lines

    lines.append("## Top Categories")
    lines.append("")
    lines.append("| Category | Count | Win Rate | Total PnL (net) |")
    lines.append("| --- | ---: | ---: | ---: |")
    for cat, metrics in rows:
        count = _coerce_int(metrics.get("count"))
        win_rate = float(metrics.get("win_rate") or 0.0)
        total_pnl_net = float(metrics.get("total_pnl_net") or 0.0)
        lines.append(f"| {cat} | {count} | {win_rate:.2%} | {total_pnl_net:.6f} |")
    lines.append("")

    return lines


def _render_top_markets(report: Dict[str, Any]) -> List[str]:
    lines: List[str] = []
    segment_analysis = report.get("segment_analysis")
    if not isinstance(segment_analysis, dict):
        return lines

    by_market_slug = segment_analysis.get("by_market_slug")
    if not isinstance(by_market_slug, dict):
        return lines

    top_rows = by_market_slug.get("top_by_total_pnl_net") or []
    if not top_rows:
        return lines

    lines.append("## Top Markets")
    lines.append("")
    lines.append("| Market Slug | Count | Win Rate | Total PnL (net) |")
    lines.append("| --- | ---: | ---: | ---: |")
    for row in top_rows[:10]:
        slug = str(row.get("market_slug") or "")
        count = _coerce_int(row.get("count"))
        win_rate = float(row.get("win_rate") or 0.0)
        total_pnl_net = float(row.get("total_pnl_net") or 0.0)
        lines.append(f"| {slug} | {count} | {win_rate:.2%} | {total_pnl_net:.6f} |")
    lines.append("")

    return lines


def _render_hypothesis_signals(report: Dict[str, Any]) -> List[str]:
    """Render the Hypothesis Signals section (CLV + entry context coverage + top segments)."""
    lines: List[str] = []
    lines.append("## Hypothesis Signals")
    lines.append("")

    # CLV coverage summary
    clv = report.get("clv_coverage")
    if isinstance(clv, dict):
        eligible = _coerce_int(clv.get("eligible_positions"))
        present = _coerce_int(clv.get("clv_present_count"))
        rate = float(clv.get("coverage_rate") or 0.0)
        lines.append(
            f"- CLV coverage: {rate:.2%} ({present}/{eligible} eligible positions)"
        )

    # Entry context coverage summary
    context = report.get("entry_context_coverage")
    if isinstance(context, dict):
        eligible = _coerce_int(context.get("eligible_positions"))
        one_h_count = _coerce_int(context.get("price_1h_before_entry_present_count"))
        movement_count = _coerce_int(context.get("movement_direction_present_count"))
        minutes_count = _coerce_int(context.get("minutes_to_close_present_count"))
        lines.append(
            f"- Entry context (price_1h_before_entry): "
            f"{one_h_count}/{eligible} ({_safe_pct(one_h_count, eligible):.2%})"
        )
        lines.append(
            f"- Entry context (movement_direction): "
            f"{movement_count}/{eligible} ({_safe_pct(movement_count, eligible):.2%})"
        )
        lines.append(
            f"- Entry context (minutes_to_close): "
            f"{minutes_count}/{eligible} ({_safe_pct(minutes_count, eligible):.2%})"
        )

    # Notional-weighted denominator (global)
    segment_analysis = report.get("segment_analysis")
    if isinstance(segment_analysis, dict):
        hyp_meta = segment_analysis.get("hypothesis_meta")
        if isinstance(hyp_meta, dict):
            total_weight = float(hyp_meta.get("notional_weight_total_global") or 0.0)
            min_thresh = _coerce_int(hyp_meta.get("min_count_threshold"))
            lines.append(
                f"- Notional-weighted denominator (global): "
                f"{total_weight:.2f} USD total notional included in weighted metrics"
            )
            lines.append(f"- Top Segments min_count threshold: {min_thresh}")

    lines.append("")

    if not isinstance(segment_analysis, dict):
        return lines

    # Top 5 segments by notional_weighted_avg_clv_pct
    lines.append("### Top Segments by notional_weighted_avg_clv_pct")
    top_clv = _collect_top_segments_by_metric(segment_analysis, "notional_weighted_avg_clv_pct")
    if top_clv:
        lines.append("")
        lines.append("| Segment | Count | Notional Weighted Avg CLV% |")
        lines.append("| --- | ---: | ---: |")
        for row in top_clv:
            lines.append(
                f"| {row['segment']} | {row['count']} | "
                f"{row['notional_weighted_avg_clv_pct']:.4f} |"
            )
    else:
        lines.append(
            "- None (no segments meet min_count threshold or no notional-weighted CLV data)"
        )
    lines.append("")

    # Top 5 segments by notional_weighted_beat_close_rate
    lines.append("### Top Segments by notional_weighted_beat_close_rate")
    top_beat = _collect_top_segments_by_metric(
        segment_analysis, "notional_weighted_beat_close_rate"
    )
    if top_beat:
        lines.append("")
        lines.append("| Segment | Count | Notional Weighted Beat Close Rate |")
        lines.append("| --- | ---: | ---: |")
        for row in top_beat:
            lines.append(
                f"| {row['segment']} | {row['count']} | "
                f"{row['notional_weighted_beat_close_rate']:.4f} |"
            )
    else:
        lines.append(
            "- None (no segments meet min_count threshold or no notional-weighted beat_close data)"
        )
    lines.append("")

    return lines


def _render_segment_highlights(report: Dict[str, Any]) -> List[str]:
    lines: List[str] = []
    lines.append("## Segment Highlights")
    lines.append("")

    segment_analysis = report.get("segment_analysis")
    if not isinstance(segment_analysis, dict):
        lines.append("- Segment analysis unavailable.")
        lines.append("")
        return lines

    ranked = _collect_segment_rankings(segment_analysis)
    top_segments = ranked[:3]
    bottom_segments = sorted(ranked, key=lambda row: (row["total_pnl_net"], row["segment"]))[:3]

    lines.append("### Top 3 Segments by total_pnl_net (estimated fees)")
    if top_segments:
        for row in top_segments:
            lines.append(
                f"- {row['segment']}: net={row['total_pnl_net']:.6f}, "
                f"gross={row['total_pnl_gross']:.6f}, count={row['count']}"
            )
    else:
        lines.append("- None")
    lines.append("")

    lines.append("### Bottom 3 Segments by total_pnl_net (estimated fees)")
    if bottom_segments:
        for row in bottom_segments:
            lines.append(
                f"- {row['segment']}: net={row['total_pnl_net']:.6f}, "
                f"gross={row['total_pnl_gross']:.6f}, count={row['count']}"
            )
    else:
        lines.append("- None")
    lines.append("")

    total_positions = _coerce_int(report.get("totals", {}).get("positions_total"))
    lines.append("### Unknown Rate Callouts (>20%)")
    callouts: List[str] = []
    if total_positions > 0:
        for field, label in (
            ("by_league", "league"),
            ("by_sport", "sport"),
            ("by_market_type", "market_type"),
        ):
            buckets = segment_analysis.get(field)
            if not isinstance(buckets, dict):
                continue
            unknown_bucket = buckets.get("unknown")
            if not isinstance(unknown_bucket, dict):
                continue
            unknown_count = _coerce_int(unknown_bucket.get("count"))
            unknown_rate = _safe_pct(unknown_count, total_positions)
            if unknown_rate > 0.20:
                callouts.append(
                    f"{label}: {unknown_rate:.2%} ({unknown_count}/{total_positions})"
                )

    if callouts:
        for callout in callouts:
            lines.append(f"- {callout}")
    else:
        lines.append("- None above 20%")
    lines.append("")

    return lines
