"""New-market capture planner.

Discovers newly listed Polymarket candidates (<48h old) via the live Gamma API,
ranks them conservatively, and produces a targets manifest for Gold tape capture.

The planner uses ``fetch_recent_markets()`` from
``packages.polymarket.market_selection.api_client`` as the sole discovery surface.
No fabricated markets; insufficiency is reported honestly when fewer than the
required number of candidates are found.

Target manifest contract:
    config/benchmark_v1_new_market_capture.targets.json
    {
      "schema_version": "benchmark_new_market_capture_v1",
      "generated_at": "...",
      "targets": [
        {
          "bucket": "new_market",
          "slug": "...",
          "market_id": "...",
          "token_id": "...",
          "listed_at": "...",
          "age_hours": 12.3,
          "priority": 1,
          "record_duration_seconds": 1800,
          "selection_reason": "..."
        }
      ]
    }

Insufficiency report:
    config/benchmark_v1_new_market_capture.insufficiency.json
    {
      "schema_version": "new_market_capture_insufficient_v1",
      "generated_at": "...",
      "bucket": "new_market",
      "candidates_found": N,
      "required": 5,
      "shortage": M,
      "reason": "..."
    }
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence

logger = logging.getLogger(__name__)

# Module-level import so unittest.mock.patch can target this symbol.
# The try/except keeps the module importable in minimal environments.
try:
    from packages.polymarket.market_selection.api_client import fetch_recent_markets
except ImportError:
    fetch_recent_markets = None  # type: ignore[assignment]

# ---------------------------------------------------------------------------
# Schema / constants
# ---------------------------------------------------------------------------

TARGET_MANIFEST_SCHEMA_VERSION = "benchmark_new_market_capture_v1"
INSUFFICIENCY_SCHEMA_VERSION = "new_market_capture_insufficient_v1"

NEW_MARKET_MAX_AGE_HOURS: float = 48.0
DEFAULT_REQUIRED_TARGETS: int = 5
DEFAULT_RECORD_DURATION_SECONDS: int = 1800  # 30 minutes per market


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class NewMarketTarget:
    bucket: str                     # always "new_market"
    slug: str
    market_id: str                  # Gamma integer id (str)
    token_id: str
    listed_at: str                  # ISO8601 UTC
    age_hours: float
    priority: int                   # 1..N (lower = higher priority)
    record_duration_seconds: int
    selection_reason: str


@dataclass
class NewMarketCaptureResult:
    """Result from :func:`plan_new_market_capture`."""

    targets: List[NewMarketTarget]
    candidates_found: int
    required: int
    reference_time: str             # ISO8601 UTC
    insufficient: bool
    insufficiency_reason: Optional[str]

    def to_targets_manifest(self) -> Dict[str, Any]:
        """Return the targets manifest as a dict (write to JSON)."""
        return {
            "schema_version": TARGET_MANIFEST_SCHEMA_VERSION,
            "generated_at": self.reference_time,
            "targets": [_target_to_dict(t) for t in self.targets],
        }

    def to_insufficiency_report(self) -> Dict[str, Any]:
        """Return the insufficiency report as a dict (write to JSON)."""
        shortage = max(0, self.required - len(self.targets))
        return {
            "schema_version": INSUFFICIENCY_SCHEMA_VERSION,
            "generated_at": self.reference_time,
            "bucket": "new_market",
            "candidates_found": self.candidates_found,
            "required": self.required,
            "shortage": shortage,
            "reason": self.insufficiency_reason or _default_insufficiency_reason(
                self.candidates_found, self.required
            ),
        }


# ---------------------------------------------------------------------------
# Core planner functions
# ---------------------------------------------------------------------------

def discover_candidates(
    markets: Sequence[Dict[str, Any]],
    *,
    reference_time: Optional[datetime] = None,
    max_age_hours: float = NEW_MARKET_MAX_AGE_HOURS,
) -> List[Dict[str, Any]]:
    """Filter markets to those listed within ``max_age_hours`` of ``reference_time``.

    Markets without a parseable ``created_at`` timestamp are excluded (conservative).
    Markets with ``token_id == ""`` are excluded (cannot record tape).

    Args:
        markets:        List of market dicts from :func:`fetch_recent_markets`.
        reference_time: Comparison reference (default: now).
        max_age_hours:  Age threshold in hours.  Must be > 0.

    Returns:
        Filtered list; each entry has ``age_hours`` populated.
    """
    ref = _ensure_utc(reference_time or datetime.now(timezone.utc))
    result: List[Dict[str, Any]] = []

    for market in markets:
        token_id = str(market.get("token_id") or "").strip()
        if not token_id:
            continue

        created_at_raw = market.get("created_at") or market.get("createdAt")
        if not created_at_raw:
            continue  # no timestamp → cannot confirm age → exclude

        created_dt = _parse_datetime(created_at_raw)
        if created_dt is None:
            continue  # unparseable timestamp → exclude

        age_hours = (ref - created_dt).total_seconds() / 3600.0
        if age_hours < 0.0 or age_hours >= max_age_hours:
            continue  # future-dated or too old

        result.append({**market, "age_hours": float(age_hours)})

    return result


def dedupe_candidates(candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Deduplicate by ``token_id``, keeping the first occurrence (earliest in list).

    Callers should rank before deduplicating so the best candidate for each
    token_id is retained.
    """
    seen: set[str] = set()
    deduped: List[Dict[str, Any]] = []
    for market in candidates:
        tid = str(market.get("token_id") or "").strip()
        if tid and tid not in seen:
            seen.add(tid)
            deduped.append(market)
    return deduped


def rank_candidates(candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Rank candidates deterministically.

    Sort key (ascending priority = better):
      1. age_hours ascending    — freshest first (highest chance of being "new" at record time)
      2. volume_24h descending  — more liquid → better tape
      3. slug ascending         — deterministic tiebreak
    """
    def _sort_key(m: Dict[str, Any]) -> tuple:
        age = float(m.get("age_hours") or 0.0)
        vol = float(m.get("volume_24h") or 0.0)
        slug = str(m.get("slug") or "")
        return (age, -vol, slug)

    return sorted(candidates, key=_sort_key)


def build_result(
    ranked_candidates: List[Dict[str, Any]],
    *,
    required: int = DEFAULT_REQUIRED_TARGETS,
    record_duration_seconds: int = DEFAULT_RECORD_DURATION_SECONDS,
    reference_time: Optional[datetime] = None,
) -> NewMarketCaptureResult:
    """Assemble a :class:`NewMarketCaptureResult` from ranked, deduped candidates.

    All candidates are converted to targets (priority 1..N).  If fewer than
    ``required`` candidates are found, the result is marked ``insufficient=True``.

    Args:
        ranked_candidates:      Sorted, deduplicated list from earlier pipeline steps.
        required:               Target quota (default 5).
        record_duration_seconds: Seconds to record each tape (default 1800).
        reference_time:         Timestamp for ``generated_at`` field.
    """
    ref = _ensure_utc(reference_time or datetime.now(timezone.utc))
    generated_at = ref.strftime("%Y-%m-%dT%H:%M:%SZ")

    targets: List[NewMarketTarget] = []
    for priority, market in enumerate(ranked_candidates, start=1):
        slug = str(market.get("slug") or "")
        market_id = str(market.get("market_id") or "")
        token_id = str(market.get("token_id") or "")
        age_hours = float(market.get("age_hours") or 0.0)
        listed_at = _format_listed_at(market)
        reason = _selection_reason(market, age_hours)

        targets.append(NewMarketTarget(
            bucket="new_market",
            slug=slug,
            market_id=market_id,
            token_id=token_id,
            listed_at=listed_at,
            age_hours=round(age_hours, 2),
            priority=priority,
            record_duration_seconds=record_duration_seconds,
            selection_reason=reason,
        ))

    candidates_found = len(ranked_candidates)
    insufficient = candidates_found < required
    insuff_reason = (
        _default_insufficiency_reason(candidates_found, required)
        if insufficient
        else None
    )

    return NewMarketCaptureResult(
        targets=targets,
        candidates_found=candidates_found,
        required=required,
        reference_time=generated_at,
        insufficient=insufficient,
        insufficiency_reason=insuff_reason,
    )


def plan_new_market_capture(
    markets: Optional[List[Dict[str, Any]]] = None,
    *,
    reference_time: Optional[datetime] = None,
    required: int = DEFAULT_REQUIRED_TARGETS,
    record_duration_seconds: int = DEFAULT_RECORD_DURATION_SECONDS,
    max_age_hours: float = NEW_MARKET_MAX_AGE_HOURS,
) -> NewMarketCaptureResult:
    """Full pipeline: filter → rank → dedupe → build result.

    If ``markets`` is None, :func:`fetch_recent_markets` is called automatically.

    Args:
        markets:               Pre-fetched market list (None → live fetch).
        reference_time:        Reference time for age calculation (None → now).
        required:              Minimum number of targets required (default 5).
        record_duration_seconds: Record window per tape in seconds.
        max_age_hours:         Maximum market age to qualify as new_market.

    Returns:
        :class:`NewMarketCaptureResult` with targets and insufficiency flags.
    """
    if markets is None:
        if fetch_recent_markets is None:
            raise ImportError("fetch_recent_markets is not available (missing dependency)")
        markets = fetch_recent_markets()
        logger.info("Fetched %d markets from Gamma API", len(markets))

    ref = _ensure_utc(reference_time or datetime.now(timezone.utc))

    candidates = discover_candidates(markets, reference_time=ref, max_age_hours=max_age_hours)
    logger.info("Candidates after age filter: %d", len(candidates))

    ranked = rank_candidates(candidates)
    deduped = dedupe_candidates(ranked)
    logger.info("Candidates after rank+dedupe: %d", len(deduped))

    return build_result(
        deduped,
        required=required,
        record_duration_seconds=record_duration_seconds,
        reference_time=ref,
    )


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _target_to_dict(t: NewMarketTarget) -> Dict[str, Any]:
    return {
        "bucket": t.bucket,
        "slug": t.slug,
        "market_id": t.market_id,
        "token_id": t.token_id,
        "listed_at": t.listed_at,
        "age_hours": t.age_hours,
        "priority": t.priority,
        "record_duration_seconds": t.record_duration_seconds,
        "selection_reason": t.selection_reason,
    }


def _ensure_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _parse_datetime(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return _ensure_utc(value)
    try:
        text = str(value).strip().replace("Z", "+00:00")
        dt = datetime.fromisoformat(text)
        return _ensure_utc(dt)
    except (ValueError, TypeError):
        return None


def _format_listed_at(market: Dict[str, Any]) -> str:
    """Return ISO8601 UTC string for the market's listed/created time."""
    raw = market.get("created_at") or market.get("createdAt") or ""
    dt = _parse_datetime(raw)
    if dt is None:
        return ""
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _selection_reason(market: Dict[str, Any], age_hours: float) -> str:
    slug = str(market.get("slug") or "")
    listed_at = _format_listed_at(market)
    vol = market.get("volume_24h")
    vol_part = f" volume_24h={vol:.0f}" if vol is not None else ""
    return f"age_hours={age_hours:.2f} listed_at={listed_at}{vol_part} slug={slug}"


def _default_insufficiency_reason(candidates_found: int, required: int) -> str:
    shortage = max(0, required - candidates_found)
    return (
        f"Only {candidates_found} new-market candidates found via live Gamma API; "
        f"need {required}. Shortage={shortage}. "
        "No new markets listed in the past 48 hours may be available, or "
        "the Gamma API may not be reachable."
    )
