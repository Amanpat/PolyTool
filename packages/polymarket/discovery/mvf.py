"""MVF (Multi-Variate Fingerprint) computation for Wallet Discovery v1.

Computes an 11-dimensional fingerprint vector from a wallet's trade/position
history using pure Python stdlib math only.

Constraints:
- No cloud LLM calls. No network calls.
- No numpy, no pandas, no external dependencies beyond stdlib.
- Deterministic: same input always produces same output.
- All division operations guard against ZeroDivisionError.
- maker_taker_ratio is explicitly null (not fabricated) when data unavailable.

Dimensions:
1.  win_rate               — float [0, 1]
2.  avg_hold_duration_hours — float >= 0 (null if timestamps absent)
3.  median_entry_price     — float [0, 1] (null if no entry prices)
4.  market_concentration   — float [0, 1] Herfindahl index
5.  category_entropy       — float >= 0 Shannon entropy (nats)
6.  avg_position_size_usdc — float >= 0 (null if no notional data)
7.  trade_frequency_per_day — float >= 0
8.  late_entry_rate        — float [0, 1] (null if timing data absent)
9.  dca_score              — float [0, 1]
10. resolution_coverage_rate — float [0, 1]
11. maker_taker_ratio      — float [0, 1] or null when data unavailable
"""
from __future__ import annotations

import math
import statistics
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

# Resolution outcomes treated as wins for win_rate computation.
_WIN_OUTCOMES = frozenset({"WIN", "PROFIT_EXIT"})
# Resolution outcomes treated as losses for win_rate computation.
_LOSS_OUTCOMES = frozenset({"LOSS", "LOSS_EXIT"})
# Outcomes excluded from the win_rate denominator (unresolved / ambiguous).
_EXCLUDED_FROM_WIN_RATE = frozenset({"PENDING", "UNKNOWN_RESOLUTION"})

# Fields that indicate maker/taker side.
_MAKER_FIELDS = ("maker", "side_type")
_MAKER_VALUES = frozenset({"maker", "MAKER", "True", "true", "1", True})


@dataclass
class MvfResult:
    """Result of MVF computation for a single wallet."""

    dimensions: Dict[str, Optional[float]]
    metadata: Dict[str, Any]


def _safe_float(value: Any) -> Optional[float]:
    """Parse a float, returning None on failure."""
    if value is None:
        return None
    try:
        v = float(value)
        if math.isfinite(v):
            return v
    except (TypeError, ValueError):
        pass
    return None


def _parse_timestamp(value: Any) -> Optional[float]:
    """Return a Unix timestamp (float seconds) from various input formats.

    Accepts:
    - numeric (int/float) — treated as seconds since epoch
    - ISO-8601 string — parsed via datetime.fromisoformat
    """
    if value is None:
        return None
    if isinstance(value, (int, float)):
        try:
            v = float(value)
            if math.isfinite(v) and v > 0:
                return v
        except (TypeError, ValueError):
            pass
        return None
    if isinstance(value, str):
        raw = value.strip().rstrip("Z")
        # Try ISO format (replace Z for UTC).
        try:
            dt = datetime.fromisoformat(raw)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.timestamp()
        except ValueError:
            pass
        # Try plain integer string.
        try:
            v = float(raw)
            if math.isfinite(v) and v > 0:
                return v
        except ValueError:
            pass
    return None


def _compute_win_rate(positions: List[Dict[str, Any]]) -> Optional[float]:
    """Fraction of resolved positions (excl. PENDING/UNKNOWN) that are WIN or PROFIT_EXIT."""
    wins = 0
    losses = 0
    for pos in positions:
        outcome = str(pos.get("resolution_outcome") or "").strip().upper()
        if outcome in _WIN_OUTCOMES:
            wins += 1
        elif outcome in _LOSS_OUTCOMES:
            losses += 1
        # PENDING and UNKNOWN_RESOLUTION are excluded from denominator
    denominator = wins + losses
    if denominator == 0:
        return None
    return wins / denominator


def _compute_avg_hold_duration_hours(
    positions: List[Dict[str, Any]],
) -> tuple[Optional[float], bool]:
    """Compute mean hold duration in hours.

    Returns (value, data_note_needed). data_note_needed is True when at least
    one position was missing timestamp data (so caller can record a note).
    """
    durations: List[float] = []
    has_missing = False
    for pos in positions:
        first_ts = _parse_timestamp(
            pos.get("first_trade_timestamp") or pos.get("open_timestamp") or pos.get("created_at")
        )
        last_ts = _parse_timestamp(
            pos.get("last_trade_timestamp") or pos.get("close_timestamp") or pos.get("closed_at")
        )
        if first_ts is not None and last_ts is not None:
            duration_seconds = last_ts - first_ts
            if duration_seconds >= 0:
                durations.append(duration_seconds / 3600.0)
            else:
                has_missing = True
        else:
            has_missing = True

    if not durations:
        return None, True
    return sum(durations) / len(durations), has_missing


def _compute_median_entry_price(positions: List[Dict[str, Any]]) -> Optional[float]:
    """Median of entry_price across all positions with a valid entry_price."""
    prices: List[float] = []
    for pos in positions:
        v = _safe_float(pos.get("entry_price"))
        if v is not None and 0.0 <= v <= 1.0:
            prices.append(v)
    if not prices:
        return None
    return statistics.median(prices)


def _compute_market_concentration(positions: List[Dict[str, Any]]) -> Optional[float]:
    """Herfindahl index over market_slug values.

    1.0 = all one market; approaches 0 for fully diversified.
    """
    counts: Dict[str, int] = {}
    for pos in positions:
        slug = str(pos.get("market_slug") or "").strip()
        if slug:
            counts[slug] = counts.get(slug, 0) + 1
    total = sum(counts.values())
    if total == 0:
        return None
    # Sort to ensure deterministic iteration.
    return sum((count / total) ** 2 for count in sorted(counts.values()))


def _compute_category_entropy(positions: List[Dict[str, Any]]) -> Optional[float]:
    """Shannon entropy (nats) of category distribution.

    Empty/Unknown categories are included. Returns 0.0 for single-category
    inputs (entropy = 0 when all entries are in one bucket).
    """
    counts: Dict[str, int] = {}
    for pos in positions:
        cat = str(pos.get("category") or "Unknown").strip() or "Unknown"
        counts[cat] = counts.get(cat, 0) + 1
    total = sum(counts.values())
    if total == 0:
        return None
    entropy = 0.0
    for count in sorted(counts.values()):
        p = count / total
        if p > 0:
            entropy -= p * math.log(p)
    return entropy


def _compute_avg_position_size_usdc(positions: List[Dict[str, Any]]) -> Optional[float]:
    """Mean notional size per position in USDC.

    Priority chain (same as coverage.extract_position_notional_usd):
    1. position_notional_usd if positive finite
    2. total_cost if positive finite
    3. size * entry_price if both present and entry_price > 0
    """
    notionals: List[float] = []
    for pos in positions:
        v = _safe_float(pos.get("position_notional_usd"))
        if v is not None and v > 0:
            notionals.append(v)
            continue
        v = _safe_float(pos.get("total_cost"))
        if v is not None and v > 0:
            notionals.append(v)
            continue
        size = _safe_float(pos.get("size"))
        ep = _safe_float(pos.get("entry_price"))
        if size is not None and ep is not None and ep > 0:
            computed = size * ep
            if computed > 0:
                notionals.append(computed)
    if not notionals:
        return None
    return sum(notionals) / len(notionals)


def _compute_trade_frequency_per_day(
    positions: List[Dict[str, Any]],
) -> Optional[float]:
    """Total positions / observation window in days.

    Window = max timestamp - min timestamp across all positions.
    If window < 1 day, use 1 day as floor.
    """
    if not positions:
        return None

    timestamps: List[float] = []
    for pos in positions:
        for field_name in (
            "first_trade_timestamp", "open_timestamp", "created_at",
            "last_trade_timestamp", "close_timestamp", "closed_at",
        ):
            ts = _parse_timestamp(pos.get(field_name))
            if ts is not None:
                timestamps.append(ts)

    if not timestamps:
        # No timestamp data — use 1-day floor with total count
        return float(len(positions))

    min_ts = min(timestamps)
    max_ts = max(timestamps)
    window_seconds = max_ts - min_ts
    window_days = max(window_seconds / 86400.0, 1.0)  # floor at 1 day
    return len(positions) / window_days


def _compute_late_entry_rate(
    positions: List[Dict[str, Any]],
) -> tuple[Optional[float], bool]:
    """Fraction of positions entered in the final 20% of a market's life.

    Since market end time is not reliably available (Gap E), we rely on
    available timing data. If no timing data is present, returns (None, True).

    Implementation: Among positions with both entry timestamp and a reference
    close/end timestamp, compute whether entry occurred in the last 20% of the
    market window.
    """
    applicable = 0
    late_count = 0
    has_missing = False

    for pos in positions:
        outcome = str(pos.get("resolution_outcome") or "").strip().upper()
        if outcome == "PENDING":
            continue

        entry_ts = _parse_timestamp(
            pos.get("first_trade_timestamp") or pos.get("open_timestamp") or pos.get("created_at")
        )
        close_ts = _parse_timestamp(
            pos.get("close_timestamp")
            or pos.get("closed_at")
            or pos.get("gamma_close_time")
            or pos.get("end_date_ts")
        )

        if entry_ts is None or close_ts is None:
            has_missing = True
            continue

        # We need a market start reference. Use market_open_ts or a heuristic.
        market_open_ts = _parse_timestamp(
            pos.get("market_open_ts") or pos.get("market_created_at")
        )
        if market_open_ts is None:
            has_missing = True
            continue

        market_duration = close_ts - market_open_ts
        if market_duration <= 0:
            has_missing = True
            continue

        # Is entry in the final 20%?
        elapsed = entry_ts - market_open_ts
        fraction_elapsed = elapsed / market_duration
        applicable += 1
        if fraction_elapsed >= 0.80:
            late_count += 1

    if applicable == 0:
        return None, True
    return late_count / applicable, has_missing


def _compute_dca_score(positions: List[Dict[str, Any]]) -> Optional[float]:
    """Fraction of distinct market_slugs where more than one entry was made."""
    counts: Dict[str, int] = {}
    for pos in positions:
        slug = str(pos.get("market_slug") or "").strip()
        if slug:
            counts[slug] = counts.get(slug, 0) + 1
    if not counts:
        return None
    multi_entry = sum(1 for c in counts.values() if c > 1)
    return multi_entry / len(counts)


def _compute_resolution_coverage_rate(positions: List[Dict[str, Any]]) -> Optional[float]:
    """Fraction of positions with resolution_outcome NOT in (UNKNOWN_RESOLUTION, PENDING)."""
    if not positions:
        return None
    resolved = sum(
        1
        for pos in positions
        if str(pos.get("resolution_outcome") or "").strip().upper()
        not in ("UNKNOWN_RESOLUTION", "PENDING", "")
    )
    return resolved / len(positions)


def _compute_maker_taker_ratio(
    positions: List[Dict[str, Any]],
) -> tuple[Optional[float], bool]:
    """Fraction of trades that are maker-side.

    Checks for 'side_type' or 'maker' fields. Returns (None, True) when no
    position has maker/taker data — this value is NEVER fabricated.
    """
    total_with_data = 0
    maker_count = 0
    for pos in positions:
        found = False
        for field_name in _MAKER_FIELDS:
            raw = pos.get(field_name)
            if raw is not None:
                found = True
                if raw in _MAKER_VALUES:
                    maker_count += 1
                break
        if found:
            total_with_data += 1

    if total_with_data == 0:
        return None, True
    return maker_count / total_with_data, False


def compute_mvf(
    positions: List[Dict[str, Any]],
    wallet_address: str = "",
) -> MvfResult:
    """Compute the 11-dimension MVF fingerprint for a wallet.

    Parameters
    ----------
    positions:
        List of position dicts from a wallet's dossier. Each dict may have
        fields: resolution_outcome, entry_price, market_slug, category,
        size, position_notional_usd, total_cost, first_trade_timestamp,
        last_trade_timestamp, etc.
    wallet_address:
        The wallet's proxy address string (0x-prefixed or empty string).

    Returns
    -------
    MvfResult with 11 dimensions and a metadata block.
    """
    data_notes: List[str] = []

    if not positions:
        dimensions: Dict[str, Optional[float]] = {
            "win_rate": None,
            "avg_hold_duration_hours": None,
            "median_entry_price": None,
            "market_concentration": None,
            "category_entropy": None,
            "avg_position_size_usdc": None,
            "trade_frequency_per_day": None,
            "late_entry_rate": None,
            "dca_score": None,
            "resolution_coverage_rate": None,
            "maker_taker_ratio": None,
        }
        data_notes.append("maker_taker_data_unavailable")
        data_notes.append("no_positions_provided")
        metadata: Dict[str, Any] = {
            "wallet_address": wallet_address,
            "computation_timestamp": _now_utc_iso(),
            "input_trade_count": 0,
            "data_notes": data_notes,
        }
        return MvfResult(dimensions=dimensions, metadata=metadata)

    # --- Dimension 1: win_rate ---
    win_rate = _compute_win_rate(positions)

    # --- Dimension 2: avg_hold_duration_hours ---
    avg_hold_duration_hours, hold_missing = _compute_avg_hold_duration_hours(positions)
    if hold_missing and avg_hold_duration_hours is None:
        data_notes.append("avg_hold_duration_unavailable: no valid first/last timestamps found")

    # --- Dimension 3: median_entry_price ---
    median_entry_price = _compute_median_entry_price(positions)

    # --- Dimension 4: market_concentration ---
    market_concentration = _compute_market_concentration(positions)

    # --- Dimension 5: category_entropy ---
    category_entropy = _compute_category_entropy(positions)

    # --- Dimension 6: avg_position_size_usdc ---
    avg_position_size_usdc = _compute_avg_position_size_usdc(positions)

    # --- Dimension 7: trade_frequency_per_day ---
    trade_frequency_per_day = _compute_trade_frequency_per_day(positions)

    # --- Dimension 8: late_entry_rate ---
    late_entry_rate, late_missing = _compute_late_entry_rate(positions)
    if late_missing and late_entry_rate is None:
        data_notes.append(
            "late_entry_rate_unavailable: market timing data (market_open_ts, close_timestamp) absent"
        )

    # --- Dimension 9: dca_score ---
    dca_score = _compute_dca_score(positions)

    # --- Dimension 10: resolution_coverage_rate ---
    resolution_coverage_rate = _compute_resolution_coverage_rate(positions)

    # --- Dimension 11: maker_taker_ratio ---
    maker_taker_ratio, maker_missing = _compute_maker_taker_ratio(positions)
    if maker_missing:
        data_notes.append("maker_taker_data_unavailable")

    dimensions = {
        "win_rate": win_rate,
        "avg_hold_duration_hours": avg_hold_duration_hours,
        "median_entry_price": median_entry_price,
        "market_concentration": market_concentration,
        "category_entropy": category_entropy,
        "avg_position_size_usdc": avg_position_size_usdc,
        "trade_frequency_per_day": trade_frequency_per_day,
        "late_entry_rate": late_entry_rate,
        "dca_score": dca_score,
        "resolution_coverage_rate": resolution_coverage_rate,
        "maker_taker_ratio": maker_taker_ratio,
    }

    metadata = {
        "wallet_address": wallet_address,
        "computation_timestamp": _now_utc_iso(),
        "input_trade_count": len(positions),
        "data_notes": data_notes,
    }

    return MvfResult(dimensions=dimensions, metadata=metadata)


def mvf_to_dict(result: MvfResult) -> Dict[str, Any]:
    """Serialize an MvfResult to a plain dict suitable for JSON output."""
    return {
        "dimensions": dict(result.dimensions),
        "metadata": dict(result.metadata),
    }


def _now_utc_iso() -> str:
    """Return current UTC time as an ISO-8601 string (second precision)."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
