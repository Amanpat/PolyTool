"""CLV + entry-context enrichment helpers with cache-first price resolution."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import logging
import math
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import requests

logger = logging.getLogger(__name__)


PRICE_SNAPSHOT_TABLE = "polyttool.market_price_snapshots"
PRICE_SNAPSHOT_KIND_CLOSING = "closing"
PRICE_SNAPSHOT_KIND_ENTRY_CONTEXT = "entry_context"
PRICE_SNAPSHOT_SOURCE = "clob_prices_history"

DEFAULT_CLOSING_WINDOW_SECONDS = 24 * 60 * 60
DEFAULT_ENTRY_CONTEXT_CORE_WINDOW_SECONDS = 2 * 60 * 60
DEFAULT_ENTRY_CONTEXT_OPEN_LOOKBACK_SECONDS = 24 * 60 * 60
MAX_ENTRY_CONTEXT_OPEN_LOOKBACK_SECONDS = 24 * 60 * 60
ONE_HOUR_SECONDS = 60 * 60
DEFAULT_PRICES_INTERVAL = "1m"
DEFAULT_PRICES_FIDELITY = 1
_LEGACY_FIDELITY_MINUTES = {
    "high": 1,
    "medium": 5,
    "low": 60,
}
_MAX_HTTP_ERROR_BODY_CHARS = 800

MISSING_REASON_NO_CLOSE_TS = "NO_CLOSE_TS"
MISSING_REASON_NO_SETTLEMENT_CLOSE_TS = "NO_SETTLEMENT_CLOSE_TS"
MISSING_REASON_NO_PRE_EVENT_CLOSE_TS = "NO_PRE_EVENT_CLOSE_TS"
MISSING_REASON_OFFLINE = "OFFLINE"
MISSING_REASON_AUTH_MISSING = "AUTH_MISSING"
MISSING_REASON_CONNECTIVITY = "CONNECTIVITY"
MISSING_REASON_HTTP_ERROR = "HTTP_ERROR"
MISSING_REASON_RATE_LIMITED = "RATE_LIMITED"
MISSING_REASON_TIMEOUT = "TIMEOUT"
MISSING_REASON_EMPTY_HISTORY = "EMPTY_HISTORY"
MISSING_REASON_OUTSIDE_WINDOW = "OUTSIDE_WINDOW"
MISSING_REASON_INVALID_PRICE_VALUE = "INVALID_PRICE_VALUE"

MISSING_REASON_MISSING_ENTRY_PRICE = "MISSING_ENTRY_PRICE"
MISSING_REASON_INVALID_ENTRY_PRICE_RANGE = "INVALID_ENTRY_PRICE_RANGE"
MISSING_REASON_MISSING_OUTCOME_TOKEN_ID = "MISSING_OUTCOME_TOKEN_ID"
MISSING_REASON_MISSING_ENTRY_TS = "MISSING_ENTRY_TS"
MISSING_REASON_NO_PRICE_IN_LOOKBACK_WINDOW = "NO_PRICE_IN_LOOKBACK_WINDOW"
MISSING_REASON_NO_PRIOR_PRICE_BEFORE_ENTRY = "NO_PRIOR_PRICE_BEFORE_ENTRY"
MISSING_REASON_NO_PRICE_1H_BEFORE_ENTRY_IN_WINDOW = "NO_PRICE_1H_BEFORE_ENTRY_IN_WINDOW"
MISSING_REASON_INVALID_TIME_ORDER_ENTRY_AFTER_CLOSE = "INVALID_TIME_ORDER_ENTRY_AFTER_CLOSE"

_MOVEMENT_EPSILON = 1e-9
_ENTRY_TS_KEYS: Sequence[str] = (
    "entry_ts",
    "entryTime",
    "entry_time",
    "first_buy_ts",
)

_CLOSE_TS_LADDER: Sequence[Tuple[str, Sequence[str]]] = (
    (
        "onchain_resolved_at",
        ("resolved_at", "resolvedAt", "resolution_resolved_at"),
    ),
    (
        "gamma_closedTime",
        (
            "gamma_closedTime",
            "closedTime",
            "closeTime",
            "closed_time",
            "gamma_close_date_iso",
            "close_date_iso",
            "closeDate",
            "close_date",
        ),
    ),
    (
        "gamma_endDate",
        (
            "gamma_endDate",
            "endDate",
            "end_date",
            "end_time",
            "gamma_end_date_iso",
            "end_date_iso",
        ),
    ),
    (
        "gamma_umaEndDate",
        (
            "gamma_umaEndDate",
            "umaEndDate",
            "uma_end_date",
            "uma_endDate",
            "gamma_uma_end_date",
        ),
    ),
)

# Settlement sub-ladder: ONLY onchain_resolved_at stage
_SETTLEMENT_TS_LADDER: Sequence[Tuple[str, Sequence[str]]] = (
    _CLOSE_TS_LADDER[0],  # ("onchain_resolved_at", ("resolved_at", "resolvedAt", ...))
)

# Pre-event sub-ladder: closedTime/endDate/umaEndDate (skip resolution stage)
_PRE_EVENT_TS_LADDER: Sequence[Tuple[str, Sequence[str]]] = _CLOSE_TS_LADDER[1:]


@dataclass(frozen=True)
class PricePoint:
    token_id: str
    ts_observed: datetime
    price: float


@dataclass(frozen=True)
class ClosingPriceResolution:
    closing_price: Optional[float]
    closing_ts_observed: Optional[datetime]
    clv_source: Optional[str]
    reason_if_missing: Optional[str]
    history_points_count: int = 0
    cache_points_written: int = 0
    error_detail: Optional[str] = None


@dataclass(frozen=True)
class HistoryWindowResolution:
    points: List[PricePoint]
    reason_if_missing: Optional[str]
    history_points_count: int = 0
    cache_points_written: int = 0
    error_detail: Optional[str] = None
    from_cache: bool = False
    network_call_made: bool = False


@dataclass(frozen=True)
class EntryContextResolution:
    open_price: Optional[float]
    open_price_ts: Optional[datetime]
    open_price_missing_reason: Optional[str]
    price_1h_before_entry: Optional[float]
    price_1h_before_entry_ts: Optional[datetime]
    price_1h_before_entry_missing_reason: Optional[str]
    price_at_entry: Optional[float]
    price_at_entry_ts: Optional[datetime]
    price_at_entry_missing_reason: Optional[str]
    movement_direction: Optional[str]
    movement_direction_missing_reason: Optional[str]
    minutes_to_close: Optional[int]
    minutes_to_close_missing_reason: Optional[str]
    cache_points_written: int = 0


def clv_recommended_next_action(reason_code: str) -> str:
    recommendations = {
        MISSING_REASON_OFFLINE: (
            "CLV online fetch is disabled. Re-run without --clv-offline to allow live "
            "/prices-history requests."
        ),
        MISSING_REASON_AUTH_MISSING: (
            "CLOB request appears unauthenticated. Configure required CLOB auth headers/keys "
            "for /prices-history access."
        ),
        MISSING_REASON_CONNECTIVITY: (
            "Network path to CLOB appears unavailable. Verify DNS, outbound internet, and API host access."
        ),
        MISSING_REASON_HTTP_ERROR: (
            "CLOB returned a non-2xx response. Inspect status/body and retry once service health is normal."
        ),
        MISSING_REASON_RATE_LIMITED: (
            "CLOB request was rate-limited. Back off and retry with a lower request rate."
        ),
        MISSING_REASON_TIMEOUT: (
            "CLOB request timed out. Increase timeout and verify network latency/packet loss."
        ),
        MISSING_REASON_EMPTY_HISTORY: (
            "CLOB returned no price history in the requested window. Increase window or warm cache earlier."
        ),
        MISSING_REASON_OUTSIDE_WINDOW: (
            "History exists but no valid sample <= close_ts within window. Increase closing window minutes if needed."
        ),
        MISSING_REASON_NO_CLOSE_TS: (
            "No close timestamp source was available. Ensure resolution enrichment and gamma market metadata are present."
        ),
        MISSING_REASON_MISSING_OUTCOME_TOKEN_ID: (
            "Position is missing token id. Ensure lifecycle rows include resolved_token_id/token_id."
        ),
        MISSING_REASON_MISSING_ENTRY_PRICE: (
            "Entry price is missing. Ensure lifecycle export includes entry_price_avg."
        ),
        MISSING_REASON_INVALID_ENTRY_PRICE_RANGE: (
            "Entry price must be in (0,1]. Verify lifecycle normalization."
        ),
        MISSING_REASON_MISSING_ENTRY_TS: (
            "Entry timestamp is missing. Ensure lifecycle export includes entry_ts."
        ),
        MISSING_REASON_NO_PRICE_IN_LOOKBACK_WINDOW: (
            "No valid prices were found in the entry lookback window."
        ),
        MISSING_REASON_NO_PRIOR_PRICE_BEFORE_ENTRY: (
            "No valid prior price was found at or before entry_ts."
        ),
        MISSING_REASON_NO_PRICE_1H_BEFORE_ENTRY_IN_WINDOW: (
            "No valid sample was found for the 1h-before-entry anchor window."
        ),
        MISSING_REASON_INVALID_TIME_ORDER_ENTRY_AFTER_CLOSE: (
            "entry_ts is after close_ts. Verify lifecycle and resolution timestamps."
        ),
        MISSING_REASON_INVALID_PRICE_VALUE: (
            "Received invalid price values. Inspect /prices-history payload quality."
        ),
    }
    return recommendations.get(
        str(reason_code or "").strip(),
        "Inspect CLV diagnostics artifact and logs for request/response details.",
    )


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


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


def normalize_prices_fidelity_minutes(value: Any) -> int:
    """Normalize CLV fidelity settings into integer minute resolution."""
    if isinstance(value, bool):
        logger.warning(
            "Invalid CLV fidelity=%r; defaulting to %s minute(s).",
            value,
            DEFAULT_PRICES_FIDELITY,
        )
        return DEFAULT_PRICES_FIDELITY

    if isinstance(value, (int, float)) and int(value) == value:
        minutes = int(value)
        if minutes > 0:
            return minutes
        logger.warning(
            "Non-positive CLV fidelity=%r; defaulting to %s minute(s).",
            value,
            DEFAULT_PRICES_FIDELITY,
        )
        return DEFAULT_PRICES_FIDELITY

    raw = str(value or "").strip().lower()
    if not raw:
        return DEFAULT_PRICES_FIDELITY
    if raw in _LEGACY_FIDELITY_MINUTES:
        return _LEGACY_FIDELITY_MINUTES[raw]

    if raw.endswith("m") and raw[:-1].isdigit():
        minutes = int(raw[:-1])
    else:
        try:
            minutes = int(raw)
        except ValueError:
            logger.warning(
                "Invalid CLV fidelity=%r; defaulting to %s minute(s).",
                value,
                DEFAULT_PRICES_FIDELITY,
            )
            return DEFAULT_PRICES_FIDELITY

    if minutes <= 0:
        logger.warning(
            "Non-positive CLV fidelity=%r; defaulting to %s minute(s).",
            value,
            DEFAULT_PRICES_FIDELITY,
        )
        return DEFAULT_PRICES_FIDELITY
    return minutes


def _truncate_text(value: str, max_chars: int) -> str:
    text = str(value or "").strip().replace("\r", " ").replace("\n", " ")
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "... [truncated]"


def format_prices_history_error_detail(exc: Exception) -> str:
    """Return a stable, debuggable detail string for /prices-history failures."""
    if not isinstance(exc, requests.exceptions.HTTPError):
        return _truncate_text(str(exc), _MAX_HTTP_ERROR_BODY_CHARS)

    response = getattr(exc, "response", None)
    if response is None:
        return _truncate_text(str(exc), _MAX_HTTP_ERROR_BODY_CHARS)

    status = getattr(response, "status_code", None)
    url = getattr(response, "url", None)
    body = ""
    try:
        body = response.text or ""
    except Exception:
        body = ""
    body_snippet = _truncate_text(body, _MAX_HTTP_ERROR_BODY_CHARS)

    parts: List[str] = []
    if status is not None:
        parts.append(f"status={status}")
    if url:
        parts.append(f"url={url}")
    if body_snippet:
        parts.append(f"body={body_snippet}")

    if parts:
        return "; ".join(parts)
    return _truncate_text(str(exc), _MAX_HTTP_ERROR_BODY_CHARS)


def _isoformat(value: Optional[datetime]) -> Optional[str]:
    if value is None:
        return None
    return _ensure_utc(value).replace(microsecond=0).isoformat()


def _parse_timestamp(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return _ensure_utc(value)

    if isinstance(value, (int, float)):
        ts = float(value)
        # Heuristic: timestamps above 1e12 are likely milliseconds.
        if abs(ts) > 1e12:
            ts = ts / 1000.0
        try:
            return datetime.fromtimestamp(ts, tz=timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None

    text = str(value).strip()
    if not text:
        return None

    # Numeric strings are accepted.
    if text.isdigit():
        try:
            return _parse_timestamp(int(text))
        except ValueError:
            return None

    normalized = text.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    return _ensure_utc(parsed)


def resolve_close_ts_with_diagnostics(
    position: Dict[str, Any],
) -> Tuple[Optional[datetime], Optional[str], List[str], Optional[str]]:
    """Resolve close_ts from the canonical ladder and expose explainability fields."""
    attempted_sources = [label for label, _ in _CLOSE_TS_LADDER]
    saw_non_empty_unparsed = False

    for source_label, keys in _CLOSE_TS_LADDER:
        for key in keys:
            raw_value = position.get(key)
            parsed = _parse_timestamp(raw_value)
            if parsed is not None:
                return parsed, source_label, attempted_sources, None
            if raw_value not in (None, "") and str(raw_value).strip():
                saw_non_empty_unparsed = True

    failure_reason = (
        "INVALID_CLOSE_TS_FORMAT"
        if saw_non_empty_unparsed
        else "MISSING_CLOSE_TS_FIELDS"
    )
    return None, None, attempted_sources, failure_reason


def resolve_close_ts(position: Dict[str, Any]) -> Tuple[Optional[datetime], Optional[str]]:
    """Resolve close_ts from the canonical ladder."""
    close_ts, close_ts_source, _, _ = resolve_close_ts_with_diagnostics(position)
    return close_ts, close_ts_source


def _resolve_close_ts_from_ladder(
    position: Dict[str, Any],
    ladder: Sequence[Tuple[str, Sequence[str]]],
) -> Tuple[Optional[datetime], Optional[str], List[str], Optional[str]]:
    """Resolve close_ts from an explicit ladder sequence.

    Returns (ts, source_label, attempted_sources, failure_reason).
    Mirrors resolve_close_ts_with_diagnostics but accepts a custom ladder.
    """
    attempted_sources = [label for label, _ in ladder]
    saw_non_empty_unparsed = False

    for source_label, keys in ladder:
        for key in keys:
            raw_value = position.get(key)
            parsed = _parse_timestamp(raw_value)
            if parsed is not None:
                return parsed, source_label, attempted_sources, None
            if raw_value not in (None, "") and str(raw_value).strip():
                saw_non_empty_unparsed = True

    failure_reason = (
        "INVALID_CLOSE_TS_FORMAT"
        if saw_non_empty_unparsed
        else "MISSING_CLOSE_TS_FIELDS"
    )
    return None, None, attempted_sources, failure_reason


def resolve_close_ts_settlement(
    position: Dict[str, Any],
) -> Tuple[Optional[datetime], Optional[str]]:
    """Resolve close_ts using only the onchain_resolved_at stage (settlement anchor)."""
    ts, source, _, _ = _resolve_close_ts_from_ladder(position, _SETTLEMENT_TS_LADDER)
    return ts, source


def resolve_close_ts_pre_event(
    position: Dict[str, Any],
) -> Tuple[Optional[datetime], Optional[str]]:
    """Resolve close_ts using the gamma closedTime/endDate/umaEndDate ladder (pre-event anchor)."""
    ts, source, _, _ = _resolve_close_ts_from_ladder(position, _PRE_EVENT_TS_LADDER)
    return ts, source


def classify_prices_history_error(exc: Exception) -> str:
    """Classify CLOB /prices-history failures into actionable, stable reason codes."""
    if isinstance(exc, requests.exceptions.Timeout):
        return MISSING_REASON_TIMEOUT

    if isinstance(exc, requests.exceptions.HTTPError):
        status = getattr(getattr(exc, "response", None), "status_code", None)
        if status == 429:
            return MISSING_REASON_RATE_LIMITED
        if status in (401, 403):
            return MISSING_REASON_AUTH_MISSING
        if status is not None:
            return MISSING_REASON_HTTP_ERROR

    if isinstance(exc, (requests.exceptions.ConnectionError, requests.exceptions.RetryError)):
        text = str(exc).lower()
        if "timeout" in text or "timed out" in text:
            return MISSING_REASON_TIMEOUT
        return MISSING_REASON_CONNECTIVITY

    text = str(exc).lower()
    if any(term in text for term in ("timeout", "timed out")):
        return MISSING_REASON_TIMEOUT
    if any(
        term in text
        for term in (
            "429",
            "rate limit",
            "too many requests",
        )
    ):
        return MISSING_REASON_RATE_LIMITED
    if any(
        term in text
        for term in (
            "401",
            "403",
            "unauthorized",
            "forbidden",
            "missing auth",
            "missing api key",
            "authentication",
        )
    ):
        return MISSING_REASON_AUTH_MISSING
    if any(
        term in text
        for term in (
            "dns",
            "name resolution",
            "connection refused",
            "no route to host",
            "failed to establish a new connection",
            "connection aborted",
            "connection reset",
            "network is unreachable",
        )
    ):
        return MISSING_REASON_CONNECTIVITY

    return MISSING_REASON_HTTP_ERROR


def resolve_outcome_token_id(position: Dict[str, Any]) -> str:
    for key in ("resolved_token_id", "token_id", "outcome_token_id"):
        token_id = str(position.get(key) or "").strip()
        if token_id:
            return token_id
    return ""


def resolve_entry_ts(position: Dict[str, Any]) -> Optional[datetime]:
    for key in _ENTRY_TS_KEYS:
        parsed = _parse_timestamp(position.get(key))
        if parsed is not None:
            return parsed
    return None


def classify_movement_direction(
    price_1h_before_entry: Optional[float],
    price_at_entry: Optional[float],
) -> Optional[str]:
    start = _safe_float(price_1h_before_entry)
    end = _safe_float(price_at_entry)
    if start is None or end is None:
        return None
    delta = end - start
    if delta > _MOVEMENT_EPSILON:
        return "up"
    if delta < -_MOVEMENT_EPSILON:
        return "down"
    return "flat"


def build_cache_lookup_sql() -> str:
    """Return the deterministic cache lookup query used by CLV resolution."""
    return f"""
        SELECT
            ts_observed,
            price
        FROM {PRICE_SNAPSHOT_TABLE}
        WHERE token_id = {{token_id:String}}
          AND kind = {{kind:String}}
          AND close_ts = {{close_ts:DateTime64(3)}}
          AND source = {{source:String}}
          AND query_window_seconds = {{query_window_seconds:UInt32}}
          AND interval = {{interval:String}}
          AND fidelity = {{fidelity:String}}
        ORDER BY ts_observed DESC
    """


def _cache_insert_columns() -> List[str]:
    return [
        "token_id",
        "ts_observed",
        "price",
        "kind",
        "close_ts",
        "source",
        "query_window_seconds",
        "interval",
        "fidelity",
    ]


def _extract_points_from_history_payload(payload: Any, token_id: str) -> List[PricePoint]:
    raw_points: Any = payload
    if isinstance(payload, dict):
        for key in ("history", "prices", "priceHistory", "prices_history", "data", "result"):
            candidate = payload.get(key)
            if isinstance(candidate, list):
                raw_points = candidate
                break

    if not isinstance(raw_points, list):
        return []

    points: List[PricePoint] = []
    for item in raw_points:
        ts_raw: Any = None
        price_raw: Any = None
        if isinstance(item, dict):
            ts_raw = (
                item.get("t")
                or item.get("ts")
                or item.get("timestamp")
                or item.get("time")
                or item.get("observed_at")
            )
            price_raw = item.get("p") or item.get("price") or item.get("value")
        elif isinstance(item, (list, tuple)) and len(item) >= 2:
            ts_raw = item[0]
            price_raw = item[1]
        if ts_raw is None:
            continue
        ts_observed = _parse_timestamp(ts_raw)
        price = _safe_float(price_raw)
        if ts_observed is None or price is None:
            continue
        points.append(PricePoint(token_id=token_id, ts_observed=ts_observed, price=price))
    return points


def select_last_price_le_close(
    points: Iterable[PricePoint],
    close_ts: datetime,
    *,
    closing_window_seconds: int = DEFAULT_CLOSING_WINDOW_SECONDS,
) -> Optional[PricePoint]:
    """Return the most recent valid sample <= close_ts within the closing window."""
    close_ts_utc = _ensure_utc(close_ts)
    window_start = close_ts_utc - timedelta(seconds=max(int(closing_window_seconds), 0))
    candidates = [
        p
        for p in points
        if window_start <= p.ts_observed <= close_ts_utc and 0.0 <= p.price <= 1.0
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.ts_observed)


def select_first_price_in_window(
    points: Iterable[PricePoint],
    *,
    window_start: datetime,
    window_end: datetime,
) -> Optional[PricePoint]:
    """Return the earliest valid sample within [window_start, window_end]."""
    start = _ensure_utc(window_start)
    end = _ensure_utc(window_end)
    candidates = [
        p
        for p in points
        if start <= p.ts_observed <= end and 0.0 <= p.price <= 1.0
    ]
    if not candidates:
        return None
    return min(candidates, key=lambda p: p.ts_observed)


def select_last_price_le_anchor(
    points: Iterable[PricePoint],
    *,
    window_start: datetime,
    anchor_ts: datetime,
) -> Optional[PricePoint]:
    """Return nearest valid sample <= anchor_ts within the provided window."""
    start = _ensure_utc(window_start)
    anchor = _ensure_utc(anchor_ts)
    candidates = [
        p
        for p in points
        if start <= p.ts_observed <= anchor and 0.0 <= p.price <= 1.0
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.ts_observed)


def _has_invalid_price_points(
    points: Iterable[PricePoint],
    *,
    window_start: datetime,
    window_end: datetime,
) -> bool:
    start = _ensure_utc(window_start)
    end = _ensure_utc(window_end)
    for point in points:
        if start <= point.ts_observed <= end and not (0.0 <= point.price <= 1.0):
            return True
    return False


def _query_cached_points(
    clickhouse_client: Any,
    *,
    token_id: str,
    close_ts: datetime,
    kind: str,
    source: str,
    query_window_seconds: int,
    interval: str,
    fidelity: str,
) -> List[PricePoint]:
    if clickhouse_client is None:
        return []

    try:
        result = clickhouse_client.query(
            build_cache_lookup_sql(),
            parameters={
                "token_id": token_id,
                "kind": kind,
                "close_ts": _ensure_utc(close_ts),
                "source": source,
                "query_window_seconds": int(query_window_seconds),
                "interval": interval,
                "fidelity": fidelity,
            },
        )
    except Exception as exc:
        logger.warning("CLV cache lookup failed for token_id=%s: %s", token_id, exc)
        return []

    points: List[PricePoint] = []
    for row in getattr(result, "result_rows", []) or []:
        if len(row) < 2:
            continue
        ts_observed = _parse_timestamp(row[0])
        price = _safe_float(row[1])
        if ts_observed is None or price is None:
            continue
        points.append(PricePoint(token_id=token_id, ts_observed=ts_observed, price=price))
    return points


def _insert_snapshot_points(
    clickhouse_client: Any,
    *,
    token_id: str,
    close_ts: datetime,
    points: Sequence[PricePoint],
    kind: str,
    source: str,
    query_window_seconds: int,
    interval: str,
    fidelity: str,
) -> int:
    if clickhouse_client is None or not points:
        return 0

    rows = [
        (
            token_id,
            _ensure_utc(point.ts_observed),
            float(point.price),
            kind,
            _ensure_utc(close_ts),
            source,
            int(query_window_seconds),
            interval,
            fidelity,
        )
        for point in points
    ]
    try:
        insert_result = clickhouse_client.insert(
            PRICE_SNAPSHOT_TABLE,
            rows,
            column_names=_cache_insert_columns(),
        )
        if isinstance(insert_result, int) and insert_result >= 0:
            return int(insert_result)
        return len(rows)
    except Exception as exc:
        logger.warning("Failed writing CLV price snapshots for token_id=%s: %s", token_id, exc)
        return 0


def _fetch_online_points(
    *,
    token_id: str,
    close_ts: datetime,
    clickhouse_client: Any,
    clob_client: Any,
    allow_online: bool,
    query_window_seconds: int,
    kind: str,
    source: str,
    interval: str,
    fidelity_key: str,
    fidelity_minutes: int,
) -> Tuple[List[PricePoint], Optional[str], int, Optional[str]]:
    if not allow_online:
        return [], MISSING_REASON_OFFLINE, 0, None
    if clob_client is None:
        return [], MISSING_REASON_AUTH_MISSING, 0, None

    window_start = _ensure_utc(close_ts) - timedelta(seconds=max(int(query_window_seconds), 0))
    try:
        payload = clob_client.get_prices_history(
            token_id=token_id,
            start_ts=window_start,
            end_ts=_ensure_utc(close_ts),
            fidelity=fidelity_minutes,
        )
    except Exception as exc:
        classified = classify_prices_history_error(exc)
        error_detail = format_prices_history_error_detail(exc)
        logger.warning(
            "CLOB prices-history failed for token_id=%s: %s (classified=%s, detail=%s)",
            token_id,
            exc,
            classified,
            error_detail,
        )
        return [], classified, 0, error_detail

    fetched_points = _extract_points_from_history_payload(payload, token_id=token_id)
    if not fetched_points:
        return [], MISSING_REASON_EMPTY_HISTORY, 0, None

    written = _insert_snapshot_points(
        clickhouse_client,
        token_id=token_id,
        close_ts=_ensure_utc(close_ts),
        points=fetched_points,
        kind=kind,
        source=source,
        query_window_seconds=int(query_window_seconds),
        interval=interval,
        fidelity=fidelity_key,
    )
    return fetched_points, None, written, None


def _resolve_history_window_points(
    *,
    token_id: str,
    anchor_ts: datetime,
    clickhouse_client: Any,
    clob_client: Any = None,
    allow_online: bool = True,
    query_window_seconds: int,
    kind: str,
    source: str,
    interval: str,
    fidelity: Any,
) -> HistoryWindowResolution:
    anchor_ts_utc = _ensure_utc(anchor_ts)
    window_seconds = max(int(query_window_seconds), 0)
    interval_key = str(interval or "").strip() or DEFAULT_PRICES_INTERVAL
    fidelity_minutes = normalize_prices_fidelity_minutes(fidelity)
    fidelity_key = str(fidelity_minutes)

    cached_points = _query_cached_points(
        clickhouse_client,
        token_id=token_id,
        close_ts=anchor_ts_utc,
        kind=kind,
        source=source,
        query_window_seconds=window_seconds,
        interval=interval_key,
        fidelity=fidelity_key,
    )
    if cached_points:
        return HistoryWindowResolution(
            points=cached_points,
            reason_if_missing=None,
            history_points_count=0,
            cache_points_written=0,
            from_cache=True,
            network_call_made=False,
        )

    if not allow_online:
        return HistoryWindowResolution(
            points=[],
            reason_if_missing=MISSING_REASON_OFFLINE,
            history_points_count=0,
            cache_points_written=0,
            network_call_made=False,
        )

    fetched_points, fetch_error_reason, cache_points_written, fetch_error_detail = _fetch_online_points(
        token_id=token_id,
        close_ts=anchor_ts_utc,
        clickhouse_client=clickhouse_client,
        clob_client=clob_client,
        allow_online=allow_online,
        query_window_seconds=window_seconds,
        kind=kind,
        source=source,
        interval=interval_key,
        fidelity_key=fidelity_key,
        fidelity_minutes=fidelity_minutes,
    )
    if fetch_error_reason is not None:
        return HistoryWindowResolution(
            points=[],
            reason_if_missing=fetch_error_reason,
            history_points_count=0,
            cache_points_written=cache_points_written,
            error_detail=fetch_error_detail,
            network_call_made=True,
        )

    return HistoryWindowResolution(
        points=fetched_points,
        reason_if_missing=None,
        history_points_count=len(fetched_points),
        cache_points_written=cache_points_written,
        from_cache=False,
        network_call_made=True,
    )


def _compute_minutes_to_close(
    entry_ts: Optional[datetime],
    close_ts: Optional[datetime],
) -> Tuple[Optional[int], Optional[str]]:
    if entry_ts is None:
        return None, MISSING_REASON_MISSING_ENTRY_TS
    if close_ts is None:
        return None, MISSING_REASON_NO_CLOSE_TS

    entry_utc = _ensure_utc(entry_ts)
    close_utc = _ensure_utc(close_ts)
    if close_utc < entry_utc:
        return None, MISSING_REASON_INVALID_TIME_ORDER_ENTRY_AFTER_CLOSE

    delta_seconds = (close_utc - entry_utc).total_seconds()
    minutes = int(delta_seconds // 60)
    return minutes, None


def _normalize_entry_context_open_window(open_window_seconds: int) -> int:
    requested = max(int(open_window_seconds), DEFAULT_ENTRY_CONTEXT_CORE_WINDOW_SECONDS)
    capped = max(int(MAX_ENTRY_CONTEXT_OPEN_LOOKBACK_SECONDS), DEFAULT_ENTRY_CONTEXT_CORE_WINDOW_SECONDS)
    return min(requested, capped)


def resolve_entry_price_context(
    token_id: str,
    entry_ts: Optional[datetime],
    close_ts: Optional[datetime],
    *,
    clickhouse_client: Any,
    clob_client: Any = None,
    allow_online: bool = True,
    core_window_seconds: int = DEFAULT_ENTRY_CONTEXT_CORE_WINDOW_SECONDS,
    open_window_seconds: int = DEFAULT_ENTRY_CONTEXT_OPEN_LOOKBACK_SECONDS,
    kind: str = PRICE_SNAPSHOT_KIND_ENTRY_CONTEXT,
    source: str = PRICE_SNAPSHOT_SOURCE,
    interval: str = DEFAULT_PRICES_INTERVAL,
    fidelity: Any = DEFAULT_PRICES_FIDELITY,
) -> EntryContextResolution:
    minutes_to_close, minutes_to_close_missing_reason = _compute_minutes_to_close(entry_ts, close_ts)
    if entry_ts is None:
        return EntryContextResolution(
            open_price=None,
            open_price_ts=None,
            open_price_missing_reason=MISSING_REASON_MISSING_ENTRY_TS,
            price_1h_before_entry=None,
            price_1h_before_entry_ts=None,
            price_1h_before_entry_missing_reason=MISSING_REASON_MISSING_ENTRY_TS,
            price_at_entry=None,
            price_at_entry_ts=None,
            price_at_entry_missing_reason=MISSING_REASON_MISSING_ENTRY_TS,
            movement_direction=None,
            movement_direction_missing_reason=MISSING_REASON_MISSING_ENTRY_TS,
            minutes_to_close=minutes_to_close,
            minutes_to_close_missing_reason=minutes_to_close_missing_reason,
            cache_points_written=0,
        )
    if not token_id:
        return EntryContextResolution(
            open_price=None,
            open_price_ts=None,
            open_price_missing_reason=MISSING_REASON_MISSING_OUTCOME_TOKEN_ID,
            price_1h_before_entry=None,
            price_1h_before_entry_ts=None,
            price_1h_before_entry_missing_reason=MISSING_REASON_MISSING_OUTCOME_TOKEN_ID,
            price_at_entry=None,
            price_at_entry_ts=None,
            price_at_entry_missing_reason=MISSING_REASON_MISSING_OUTCOME_TOKEN_ID,
            movement_direction=None,
            movement_direction_missing_reason=MISSING_REASON_MISSING_OUTCOME_TOKEN_ID,
            minutes_to_close=minutes_to_close,
            minutes_to_close_missing_reason=minutes_to_close_missing_reason,
            cache_points_written=0,
        )

    entry_ts_utc = _ensure_utc(entry_ts)
    core_window = max(int(core_window_seconds), ONE_HOUR_SECONDS)
    core_window_start = entry_ts_utc - timedelta(seconds=core_window)
    open_window = _normalize_entry_context_open_window(open_window_seconds)
    open_window_start = entry_ts_utc - timedelta(seconds=open_window)
    one_hour_anchor = entry_ts_utc - timedelta(seconds=ONE_HOUR_SECONDS)

    core_resolution = _resolve_history_window_points(
        token_id=token_id,
        anchor_ts=entry_ts_utc,
        clickhouse_client=clickhouse_client,
        clob_client=clob_client,
        allow_online=allow_online,
        query_window_seconds=core_window,
        kind=kind,
        source=source,
        interval=interval,
        fidelity=fidelity,
    )
    open_resolution = core_resolution
    if open_window != core_window:
        open_resolution = _resolve_history_window_points(
            token_id=token_id,
            anchor_ts=entry_ts_utc,
            clickhouse_client=clickhouse_client,
            clob_client=clob_client,
            allow_online=allow_online,
            query_window_seconds=open_window,
            kind=kind,
            source=source,
            interval=interval,
            fidelity=fidelity,
        )

    open_choice = select_first_price_in_window(
        open_resolution.points,
        window_start=open_window_start,
        window_end=entry_ts_utc,
    )
    if open_choice is not None:
        open_price = float(open_choice.price)
        open_price_ts = _ensure_utc(open_choice.ts_observed)
        open_price_missing_reason = None
    else:
        open_price = None
        open_price_ts = None
        if open_resolution.reason_if_missing and not open_resolution.points:
            open_price_missing_reason = open_resolution.reason_if_missing
        elif _has_invalid_price_points(
            open_resolution.points,
            window_start=open_window_start,
            window_end=entry_ts_utc,
        ):
            open_price_missing_reason = MISSING_REASON_INVALID_PRICE_VALUE
        else:
            open_price_missing_reason = MISSING_REASON_NO_PRICE_IN_LOOKBACK_WINDOW

    price_at_choice = select_last_price_le_anchor(
        core_resolution.points,
        window_start=core_window_start,
        anchor_ts=entry_ts_utc,
    )
    if price_at_choice is not None:
        price_at_entry = float(price_at_choice.price)
        price_at_entry_ts = _ensure_utc(price_at_choice.ts_observed)
        price_at_entry_missing_reason = None
    else:
        price_at_entry = None
        price_at_entry_ts = None
        if core_resolution.reason_if_missing and not core_resolution.points:
            price_at_entry_missing_reason = core_resolution.reason_if_missing
        elif _has_invalid_price_points(
            core_resolution.points,
            window_start=core_window_start,
            window_end=entry_ts_utc,
        ):
            price_at_entry_missing_reason = MISSING_REASON_INVALID_PRICE_VALUE
        else:
            price_at_entry_missing_reason = MISSING_REASON_NO_PRIOR_PRICE_BEFORE_ENTRY

    one_hour_choice = select_last_price_le_anchor(
        core_resolution.points,
        window_start=core_window_start,
        anchor_ts=one_hour_anchor,
    )
    if one_hour_choice is not None:
        price_1h_before_entry = float(one_hour_choice.price)
        price_1h_before_entry_ts = _ensure_utc(one_hour_choice.ts_observed)
        price_1h_before_entry_missing_reason = None
    else:
        price_1h_before_entry = None
        price_1h_before_entry_ts = None
        if core_resolution.reason_if_missing and not core_resolution.points:
            price_1h_before_entry_missing_reason = core_resolution.reason_if_missing
        elif _has_invalid_price_points(
            core_resolution.points,
            window_start=core_window_start,
            window_end=one_hour_anchor,
        ):
            price_1h_before_entry_missing_reason = MISSING_REASON_INVALID_PRICE_VALUE
        else:
            price_1h_before_entry_missing_reason = MISSING_REASON_NO_PRICE_1H_BEFORE_ENTRY_IN_WINDOW

    movement_direction = classify_movement_direction(price_1h_before_entry, price_at_entry)
    if movement_direction is None:
        movement_direction_missing_reason = (
            price_1h_before_entry_missing_reason
            or price_at_entry_missing_reason
            or "UNSPECIFIED"
        )
    else:
        movement_direction_missing_reason = None

    cache_points_written = core_resolution.cache_points_written
    if open_resolution is not core_resolution:
        cache_points_written += open_resolution.cache_points_written

    return EntryContextResolution(
        open_price=open_price,
        open_price_ts=open_price_ts,
        open_price_missing_reason=open_price_missing_reason,
        price_1h_before_entry=price_1h_before_entry,
        price_1h_before_entry_ts=price_1h_before_entry_ts,
        price_1h_before_entry_missing_reason=price_1h_before_entry_missing_reason,
        price_at_entry=price_at_entry,
        price_at_entry_ts=price_at_entry_ts,
        price_at_entry_missing_reason=price_at_entry_missing_reason,
        movement_direction=movement_direction,
        movement_direction_missing_reason=movement_direction_missing_reason,
        minutes_to_close=minutes_to_close,
        minutes_to_close_missing_reason=minutes_to_close_missing_reason,
        cache_points_written=cache_points_written,
    )


def resolve_closing_price(
    token_id: str,
    close_ts: Optional[datetime],
    *,
    clickhouse_client: Any,
    clob_client: Any = None,
    allow_online: bool = True,
    closing_window_seconds: int = DEFAULT_CLOSING_WINDOW_SECONDS,
    kind: str = PRICE_SNAPSHOT_KIND_CLOSING,
    source: str = PRICE_SNAPSHOT_SOURCE,
    interval: str = DEFAULT_PRICES_INTERVAL,
    fidelity: Any = DEFAULT_PRICES_FIDELITY,
) -> ClosingPriceResolution:
    """Resolve closing price from cache first, then optional live CLOB history."""
    if close_ts is None:
        return ClosingPriceResolution(
            closing_price=None,
            closing_ts_observed=None,
            clv_source=None,
            reason_if_missing=MISSING_REASON_NO_CLOSE_TS,
            history_points_count=0,
            cache_points_written=0,
        )

    close_ts_utc = _ensure_utc(close_ts)
    window_seconds = max(int(closing_window_seconds), 0)
    window_resolution = _resolve_history_window_points(
        token_id=token_id,
        anchor_ts=close_ts_utc,
        clickhouse_client=clickhouse_client,
        clob_client=clob_client,
        allow_online=allow_online,
        kind=kind,
        source=source,
        query_window_seconds=window_seconds,
        interval=interval,
        fidelity=fidelity,
    )
    if not window_resolution.points:
        return ClosingPriceResolution(
            closing_price=None,
            closing_ts_observed=None,
            clv_source=None,
            reason_if_missing=window_resolution.reason_if_missing or MISSING_REASON_EMPTY_HISTORY,
            history_points_count=window_resolution.history_points_count,
            cache_points_written=window_resolution.cache_points_written,
            error_detail=window_resolution.error_detail,
        )

    fetched_choice = select_last_price_le_close(
        window_resolution.points,
        close_ts_utc,
        closing_window_seconds=window_seconds,
    )
    if fetched_choice is not None:
        return ClosingPriceResolution(
            closing_price=float(fetched_choice.price),
            closing_ts_observed=_ensure_utc(fetched_choice.ts_observed),
            clv_source=source,
            reason_if_missing=None,
            history_points_count=window_resolution.history_points_count,
            cache_points_written=window_resolution.cache_points_written,
        )

    if any(not (0.0 <= point.price <= 1.0) for point in window_resolution.points):
        return ClosingPriceResolution(
            closing_price=None,
            closing_ts_observed=None,
            clv_source=None,
            reason_if_missing=MISSING_REASON_INVALID_PRICE_VALUE,
            history_points_count=window_resolution.history_points_count,
            cache_points_written=window_resolution.cache_points_written,
        )
    return ClosingPriceResolution(
        closing_price=None,
        closing_ts_observed=None,
        clv_source=None,
        reason_if_missing=MISSING_REASON_OUTSIDE_WINDOW,
        history_points_count=window_resolution.history_points_count,
        cache_points_written=window_resolution.cache_points_written,
    )


def _set_missing_clv_fields(position: Dict[str, Any], reason: str) -> None:
    position["closing_price"] = None
    position["closing_ts_observed"] = None
    position["clv"] = None
    position["clv_pct"] = None
    position["beat_close"] = None
    position["clv_source"] = None
    position["clv_missing_reason"] = reason


def _apply_entry_context_fields(
    position: Dict[str, Any],
    context: EntryContextResolution,
) -> None:
    position["open_price"] = (
        round(float(context.open_price), 6)
        if context.open_price is not None
        else None
    )
    position["open_price_ts"] = _isoformat(context.open_price_ts)
    position["open_price_missing_reason"] = (
        None if context.open_price is not None else context.open_price_missing_reason or "UNSPECIFIED"
    )

    position["price_1h_before_entry"] = (
        round(float(context.price_1h_before_entry), 6)
        if context.price_1h_before_entry is not None
        else None
    )
    position["price_1h_before_entry_ts"] = _isoformat(context.price_1h_before_entry_ts)
    position["price_1h_before_entry_missing_reason"] = (
        None
        if context.price_1h_before_entry is not None
        else context.price_1h_before_entry_missing_reason or "UNSPECIFIED"
    )

    position["price_at_entry"] = (
        round(float(context.price_at_entry), 6)
        if context.price_at_entry is not None
        else None
    )
    position["price_at_entry_ts"] = _isoformat(context.price_at_entry_ts)
    position["price_at_entry_missing_reason"] = (
        None
        if context.price_at_entry is not None
        else context.price_at_entry_missing_reason or "UNSPECIFIED"
    )

    position["movement_direction"] = context.movement_direction
    position["movement_direction_missing_reason"] = (
        None
        if context.movement_direction is not None
        else context.movement_direction_missing_reason or "UNSPECIFIED"
    )

    position["minutes_to_close"] = (
        int(context.minutes_to_close)
        if context.minutes_to_close is not None
        else None
    )
    position["minutes_to_close_missing_reason"] = (
        None
        if context.minutes_to_close is not None
        else context.minutes_to_close_missing_reason or "UNSPECIFIED"
    )


def enrich_position_with_clv(
    position: Dict[str, Any],
    *,
    clickhouse_client: Any,
    clob_client: Any = None,
    allow_online: bool = True,
    closing_window_seconds: int = DEFAULT_CLOSING_WINDOW_SECONDS,
    interval: str = DEFAULT_PRICES_INTERVAL,
    fidelity: Any = DEFAULT_PRICES_FIDELITY,
) -> Dict[str, Any]:
    """Mutate one position with CLV fields and explicit missing reasons."""
    close_ts, close_ts_source, attempted_sources, close_ts_failure_reason = (
        resolve_close_ts_with_diagnostics(position)
    )
    position["close_ts"] = _isoformat(close_ts)
    position["close_ts_source"] = close_ts_source
    position["close_ts_attempted_sources"] = attempted_sources
    position["close_ts_failure_reason"] = close_ts_failure_reason

    token_id = resolve_outcome_token_id(position)
    entry_ts = resolve_entry_ts(position)
    entry_price = _safe_float(position.get("entry_price"))
    entry_context = resolve_entry_price_context(
        token_id=token_id,
        entry_ts=entry_ts,
        close_ts=close_ts,
        clickhouse_client=clickhouse_client,
        clob_client=clob_client,
        allow_online=allow_online,
        core_window_seconds=DEFAULT_ENTRY_CONTEXT_CORE_WINDOW_SECONDS,
        open_window_seconds=max(
            int(closing_window_seconds),
            DEFAULT_ENTRY_CONTEXT_CORE_WINDOW_SECONDS,
        ),
        interval=interval,
        fidelity=fidelity,
    )
    _apply_entry_context_fields(position, entry_context)

    if close_ts is None:
        _set_missing_clv_fields(position, MISSING_REASON_NO_CLOSE_TS)
        return position
    if not token_id:
        _set_missing_clv_fields(position, MISSING_REASON_MISSING_OUTCOME_TOKEN_ID)
        return position
    if entry_price is None:
        _set_missing_clv_fields(position, MISSING_REASON_MISSING_ENTRY_PRICE)
        return position
    if not (0.0 < entry_price <= 1.0):
        _set_missing_clv_fields(position, MISSING_REASON_INVALID_ENTRY_PRICE_RANGE)
        return position

    resolved = resolve_closing_price(
        token_id,
        close_ts,
        clickhouse_client=clickhouse_client,
        clob_client=clob_client,
        allow_online=allow_online,
        closing_window_seconds=closing_window_seconds,
        interval=interval,
        fidelity=fidelity,
    )
    if resolved.closing_price is None:
        _set_missing_clv_fields(
            position,
            resolved.reason_if_missing or MISSING_REASON_OUTSIDE_WINDOW,
        )
        return position

    closing_price = float(resolved.closing_price)
    clv_value = closing_price - entry_price
    position["closing_price"] = round(closing_price, 6)
    position["closing_ts_observed"] = _isoformat(resolved.closing_ts_observed)
    position["clv"] = round(clv_value, 6)
    position["clv_pct"] = round(clv_value / entry_price, 6)
    position["beat_close"] = bool(entry_price < closing_price)
    position["clv_source"] = f"prices_history|{close_ts_source or 'unknown'}"
    position["clv_missing_reason"] = None
    return position


def enrich_positions_with_clv(
    positions: List[Dict[str, Any]],
    *,
    clickhouse_client: Any,
    clob_client: Any = None,
    allow_online: bool = True,
    closing_window_seconds: int = DEFAULT_CLOSING_WINDOW_SECONDS,
    interval: str = DEFAULT_PRICES_INTERVAL,
    fidelity: Any = DEFAULT_PRICES_FIDELITY,
) -> Dict[str, Any]:
    """Enrich a list of positions with CLV fields and return a summary."""
    missing_reason_counts: Dict[str, int] = {}
    clv_present_count = 0

    for position in positions:
        enrich_position_with_clv(
            position,
            clickhouse_client=clickhouse_client,
            clob_client=clob_client,
            allow_online=allow_online,
            closing_window_seconds=closing_window_seconds,
            interval=interval,
            fidelity=fidelity,
        )
        if _safe_float(position.get("clv")) is None:
            reason = str(position.get("clv_missing_reason") or "UNSPECIFIED")
            missing_reason_counts[reason] = missing_reason_counts.get(reason, 0) + 1
        else:
            clv_present_count += 1

    return {
        "positions_total": len(positions),
        "clv_present_count": clv_present_count,
        "clv_missing_count": len(positions) - clv_present_count,
        "missing_reason_counts": dict(sorted(missing_reason_counts.items())),
    }


def _set_missing_clv_variant_fields(
    position: Dict[str, Any],
    variant: str,
    reason: str,
) -> None:
    """Write all 6 per-variant CLV fields as None/reason."""
    position[f"closing_price_{variant}"] = None
    position[f"closing_ts_{variant}"] = None
    position[f"clv_pct_{variant}"] = None
    position[f"beat_close_{variant}"] = None
    position[f"clv_source_{variant}"] = None
    position[f"clv_missing_reason_{variant}"] = reason


def _apply_clv_variant(
    position: Dict[str, Any],
    variant: str,
    close_ts: Optional[datetime],
    close_ts_source: Optional[str],
    entry_price: float,
    token_id: str,
    *,
    clickhouse_client: Any,
    clob_client: Any = None,
    allow_online: bool = True,
    closing_window_seconds: int = DEFAULT_CLOSING_WINDOW_SECONDS,
    interval: str = DEFAULT_PRICES_INTERVAL,
    fidelity: Any = DEFAULT_PRICES_FIDELITY,
) -> None:
    """Resolve closing price for a specific variant and write the 6 per-variant fields."""
    if close_ts is None:
        missing_reason = (
            MISSING_REASON_NO_SETTLEMENT_CLOSE_TS
            if variant == "settlement"
            else MISSING_REASON_NO_PRE_EVENT_CLOSE_TS
        )
        _set_missing_clv_variant_fields(position, variant, missing_reason)
        return

    resolved = resolve_closing_price(
        token_id,
        close_ts,
        clickhouse_client=clickhouse_client,
        clob_client=clob_client,
        allow_online=allow_online,
        closing_window_seconds=closing_window_seconds,
        interval=interval,
        fidelity=fidelity,
    )

    if resolved.closing_price is None:
        _set_missing_clv_variant_fields(
            position,
            variant,
            resolved.reason_if_missing or MISSING_REASON_OUTSIDE_WINDOW,
        )
        return

    closing_price = float(resolved.closing_price)
    clv_value = closing_price - entry_price
    position[f"closing_price_{variant}"] = round(closing_price, 6)
    position[f"closing_ts_{variant}"] = _isoformat(resolved.closing_ts_observed)
    position[f"clv_pct_{variant}"] = round(clv_value / entry_price, 6)
    position[f"beat_close_{variant}"] = bool(entry_price < closing_price)
    position[f"clv_source_{variant}"] = f"prices_history|{close_ts_source or 'unknown'}"
    position[f"clv_missing_reason_{variant}"] = None


def enrich_position_with_dual_clv(
    position: Dict[str, Any],
    *,
    clickhouse_client: Any,
    clob_client: Any = None,
    allow_online: bool = True,
    closing_window_seconds: int = DEFAULT_CLOSING_WINDOW_SECONDS,
    interval: str = DEFAULT_PRICES_INTERVAL,
    fidelity: Any = DEFAULT_PRICES_FIDELITY,
) -> Dict[str, Any]:
    """Mutate one position with dual CLV variant fields (settlement + pre_event).

    Calls enrich_position_with_clv first to preserve all existing fields,
    then applies settlement and pre_event variant fields separately.
    """
    # Preserve existing CLV fields (close_ts, entry context, etc.)
    enrich_position_with_clv(
        position,
        clickhouse_client=clickhouse_client,
        clob_client=clob_client,
        allow_online=allow_online,
        closing_window_seconds=closing_window_seconds,
        interval=interval,
        fidelity=fidelity,
    )

    token_id = resolve_outcome_token_id(position)
    entry_price = _safe_float(position.get("entry_price"))

    # Guard: if missing entry_price or token_id, fill both variants as missing
    if not token_id:
        _set_missing_clv_variant_fields(
            position, "settlement", MISSING_REASON_MISSING_OUTCOME_TOKEN_ID
        )
        _set_missing_clv_variant_fields(
            position, "pre_event", MISSING_REASON_MISSING_OUTCOME_TOKEN_ID
        )
        return position

    if entry_price is None:
        _set_missing_clv_variant_fields(
            position, "settlement", MISSING_REASON_MISSING_ENTRY_PRICE
        )
        _set_missing_clv_variant_fields(
            position, "pre_event", MISSING_REASON_MISSING_ENTRY_PRICE
        )
        return position

    if not (0.0 < entry_price <= 1.0):
        _set_missing_clv_variant_fields(
            position, "settlement", MISSING_REASON_INVALID_ENTRY_PRICE_RANGE
        )
        _set_missing_clv_variant_fields(
            position, "pre_event", MISSING_REASON_INVALID_ENTRY_PRICE_RANGE
        )
        return position

    # Settlement variant: anchor = onchain_resolved_at only
    settlement_ts, settlement_source = resolve_close_ts_settlement(position)
    _apply_clv_variant(
        position,
        "settlement",
        settlement_ts,
        settlement_source,
        entry_price,
        token_id,
        clickhouse_client=clickhouse_client,
        clob_client=clob_client,
        allow_online=allow_online,
        closing_window_seconds=closing_window_seconds,
        interval=interval,
        fidelity=fidelity,
    )

    # Pre-event variant: anchor = closedTime/endDate/umaEndDate ladder
    pre_event_ts, pre_event_source = resolve_close_ts_pre_event(position)
    _apply_clv_variant(
        position,
        "pre_event",
        pre_event_ts,
        pre_event_source,
        entry_price,
        token_id,
        clickhouse_client=clickhouse_client,
        clob_client=clob_client,
        allow_online=allow_online,
        closing_window_seconds=closing_window_seconds,
        interval=interval,
        fidelity=fidelity,
    )

    return position


def enrich_positions_with_dual_clv(
    positions: List[Dict[str, Any]],
    *,
    clickhouse_client: Any,
    clob_client: Any = None,
    allow_online: bool = True,
    closing_window_seconds: int = DEFAULT_CLOSING_WINDOW_SECONDS,
    interval: str = DEFAULT_PRICES_INTERVAL,
    fidelity: Any = DEFAULT_PRICES_FIDELITY,
) -> Dict[str, Any]:
    """Enrich a list of positions with dual CLV variant fields and return a summary."""
    missing_reason_counts: Dict[str, int] = {}
    clv_present_count = 0
    settlement_present_count = 0
    pre_event_present_count = 0

    for position in positions:
        enrich_position_with_dual_clv(
            position,
            clickhouse_client=clickhouse_client,
            clob_client=clob_client,
            allow_online=allow_online,
            closing_window_seconds=closing_window_seconds,
            interval=interval,
            fidelity=fidelity,
        )
        # Track base CLV
        if _safe_float(position.get("clv")) is None:
            reason = str(position.get("clv_missing_reason") or "UNSPECIFIED")
            missing_reason_counts[reason] = missing_reason_counts.get(reason, 0) + 1
        else:
            clv_present_count += 1
        # Track settlement variant
        if _safe_float(position.get("clv_pct_settlement")) is not None:
            settlement_present_count += 1
        # Track pre_event variant
        if _safe_float(position.get("clv_pct_pre_event")) is not None:
            pre_event_present_count += 1

    return {
        "positions_total": len(positions),
        "clv_present_count": clv_present_count,
        "clv_missing_count": len(positions) - clv_present_count,
        "missing_reason_counts": dict(sorted(missing_reason_counts.items())),
        "settlement_present_count": settlement_present_count,
        "settlement_missing_count": len(positions) - settlement_present_count,
        "pre_event_present_count": pre_event_present_count,
        "pre_event_missing_count": len(positions) - pre_event_present_count,
    }


def warm_clv_snapshot_cache(
    positions: List[Dict[str, Any]],
    *,
    clickhouse_client: Any,
    clob_client: Any = None,
    allow_online: bool = True,
    closing_window_seconds: int = DEFAULT_CLOSING_WINDOW_SECONDS,
    interval: str = DEFAULT_PRICES_INTERVAL,
    fidelity: Any = DEFAULT_PRICES_FIDELITY,
) -> Dict[str, Any]:
    """Warm CLV price-snapshot cache without mutating position CLV outputs."""
    attempted = 0
    cache_hit_count = 0
    fetched_count = 0
    inserted_rows_count = 0
    succeeded_positions_count = 0
    failed_positions_count = 0
    skipped_not_eligible = 0
    failure_reason_counts: Dict[str, int] = {}
    failure_samples: List[Dict[str, str]] = []

    def _normalize_failure_reason(reason: Optional[str], error_detail: Optional[str]) -> str:
        normalized = str(reason or "").strip()
        if normalized:
            return normalized
        if str(error_detail or "").strip():
            return "UNKNOWN_ERROR"
        return MISSING_REASON_HTTP_ERROR

    for position in positions:
        close_ts, _ = resolve_close_ts(position)
        token_id = resolve_outcome_token_id(position)
        if close_ts is None or not token_id:
            skipped_not_eligible += 1
            continue

        attempted += 1
        close_ts_utc = _ensure_utc(close_ts)
        window_seconds = max(int(closing_window_seconds), 0)
        resolution = _resolve_history_window_points(
            token_id=token_id,
            anchor_ts=close_ts_utc,
            clickhouse_client=clickhouse_client,
            clob_client=clob_client,
            allow_online=allow_online,
            query_window_seconds=window_seconds,
            kind=PRICE_SNAPSHOT_KIND_CLOSING,
            source=PRICE_SNAPSHOT_SOURCE,
            interval=interval,
            fidelity=fidelity,
        )
        if resolution.from_cache and resolution.points:
            cache_hit_count += 1
        if resolution.network_call_made:
            fetched_count += 1
        inserted_rows_count += max(int(resolution.cache_points_written or 0), 0)

        if resolution.points:
            succeeded_positions_count += 1
            continue

        failed_positions_count += 1
        reason = _normalize_failure_reason(
            resolution.reason_if_missing,
            resolution.error_detail,
        )
        failure_reason_counts[reason] = failure_reason_counts.get(reason, 0) + 1
        if len(failure_samples) < 5:
            detail = str(resolution.error_detail or "").strip()
            if not detail:
                detail = (
                    "No additional error detail. "
                    f"history_points_count={int(resolution.history_points_count or 0)}"
                )
            failure_samples.append(
                {
                    "token_id": token_id,
                    "reason": reason,
                    "error_detail": _truncate_text(detail, 240),
                }
            )

    return {
        "positions_total": len(positions),
        "eligible_positions": attempted,
        "attempted": attempted,
        "succeeded": succeeded_positions_count,
        "failed": failed_positions_count,
        "cache_hit_count": cache_hit_count,
        "fetched_count": fetched_count,
        "inserted_rows_count": inserted_rows_count,
        "succeeded_positions_count": succeeded_positions_count,
        "failed_positions_count": failed_positions_count,
        "skipped_not_eligible": skipped_not_eligible,
        "failure_reason_counts": dict(sorted(failure_reason_counts.items())),
        "failure_samples": failure_samples,
    }
