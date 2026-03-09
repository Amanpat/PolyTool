"""Pure helpers for Track A mixed-regime policy checks."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import re
from typing import Any, Iterable, Mapping

POLITICS = "politics"
SPORTS = "sports"
NEW_MARKET = "new_market"
OTHER = "other"
REQUIRED_REGIMES = (POLITICS, SPORTS, NEW_MARKET)

_TEXT_KEYS = (
    "slug",
    "market_slug",
    "question",
    "title",
    "event_slug",
    "event_title",
    "category",
    "subcategory",
)
_TAG_KEYS = ("tags", "tag_names", "tagNames")
_CATEGORY_KEYS = ("category", "subcategory")
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

_POLITICS_KEYWORDS = frozenset(
    {
        "ballot",
        "caucus",
        "congress",
        "election",
        "elections",
        "geopolitical",
        "government",
        "governor",
        "house",
        "mayor",
        "minister",
        "parliament",
        "policy",
        "politics",
        "political",
        "president",
        "presidential",
        "prime minister",
        "primary",
        "referendum",
        "senate",
        "vote",
        "voting",
    }
)
_SPORTS_KEYWORDS = frozenset(
    {
        "baseball",
        "basketball",
        "champions league",
        "cricket",
        "f1",
        "football",
        "formula 1",
        "golf",
        "hockey",
        "mlb",
        "mls",
        "mma",
        "nba",
        "ncaa",
        "nfl",
        "nhl",
        "premier league",
        "soccer",
        "sport",
        "sports",
        "super bowl",
        "tennis",
        "ufc",
        "wnba",
        "world cup",
    }
)
_NEW_MARKET_KEYWORDS = frozenset(
    {
        "fresh market",
        "fresh markets",
        "new market",
        "new markets",
    }
)


def classify_market_regime(
    market: Mapping[str, Any],
    *,
    reference_time: Any = None,
    new_market_max_age_hours: float = 48.0,
) -> str:
    """Return the primary Track A regime for a market metadata entry."""

    primary_regime = _classify_primary_regime(market)
    if primary_regime != OTHER:
        return primary_regime
    if _is_new_market(
        market,
        reference_time=reference_time,
        new_market_max_age_hours=new_market_max_age_hours,
    ):
        return NEW_MARKET
    return OTHER


def check_mixed_regime_coverage(
    markets: Iterable[Mapping[str, Any]],
    *,
    reference_time: Any = None,
    new_market_max_age_hours: float = 48.0,
) -> dict[str, Any]:
    """Check whether a corpus covers politics, sports, and new markets."""

    regime_counts = {regime: 0 for regime in REQUIRED_REGIMES}

    for market in markets:
        primary_regime = _classify_primary_regime(market)
        if primary_regime in (POLITICS, SPORTS):
            regime_counts[primary_regime] += 1

        if _is_new_market(
            market,
            reference_time=reference_time,
            new_market_max_age_hours=new_market_max_age_hours,
        ):
            regime_counts[NEW_MARKET] += 1

    covered_regimes = tuple(regime for regime in REQUIRED_REGIMES if regime_counts[regime] > 0)
    missing_regimes = tuple(regime for regime in REQUIRED_REGIMES if regime_counts[regime] == 0)

    return {
        "satisfies_policy": len(missing_regimes) == 0,
        "covered_regimes": covered_regimes,
        "missing_regimes": missing_regimes,
        "regime_counts": regime_counts,
    }


def _classify_primary_regime(market: Mapping[str, Any]) -> str:
    category_text = _collect_text(market, keys=_CATEGORY_KEYS + _TAG_KEYS)
    politics_hits = _count_keyword_hits(category_text, _POLITICS_KEYWORDS)
    sports_hits = _count_keyword_hits(category_text, _SPORTS_KEYWORDS)

    if politics_hits == 0 and sports_hits == 0:
        full_text = _collect_text(market, keys=_TEXT_KEYS + _TAG_KEYS)
        politics_hits = _count_keyword_hits(full_text, _POLITICS_KEYWORDS)
        sports_hits = _count_keyword_hits(full_text, _SPORTS_KEYWORDS)

    if politics_hits > sports_hits and politics_hits > 0:
        return POLITICS
    if sports_hits > politics_hits and sports_hits > 0:
        return SPORTS
    if politics_hits > 0:
        return POLITICS
    if sports_hits > 0:
        return SPORTS
    return OTHER


def _is_new_market(
    market: Mapping[str, Any],
    *,
    reference_time: Any = None,
    new_market_max_age_hours: float,
) -> bool:
    if _count_keyword_hits(_collect_text(market, keys=_TEXT_KEYS + _TAG_KEYS), _NEW_MARKET_KEYWORDS) > 0:
        return True

    age_hours = _market_age_hours(market, reference_time=reference_time)
    if age_hours is None:
        return False
    return 0.0 <= age_hours < new_market_max_age_hours


def _market_age_hours(market: Mapping[str, Any], *, reference_time: Any = None) -> float | None:
    for key in _AGE_HOURS_KEYS:
        age_hours = _coerce_float(market.get(key))
        if age_hours is not None and age_hours >= 0.0:
            return age_hours

    created_at = _first_datetime(market, _CREATED_AT_KEYS)
    reference_dt = _coerce_datetime(reference_time)
    if created_at is None or reference_dt is None:
        return None

    age_hours = (reference_dt - created_at).total_seconds() / 3600.0
    if age_hours < 0.0:
        return None
    return age_hours


def _first_datetime(market: Mapping[str, Any], keys: Iterable[str]) -> datetime | None:
    for key in keys:
        value = market.get(key)
        dt = _coerce_datetime(value)
        if dt is not None:
            return dt
    return None


def _collect_text(market: Mapping[str, Any], *, keys: Iterable[str]) -> str:
    values: list[str] = []
    for key in keys:
        values.extend(_string_values(market.get(key)))
    return _normalize_text(" ".join(values))


def _string_values(value: Any) -> list[str]:
    if value in (None, ""):
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, Mapping):
        values: list[str] = []
        for key in ("label", "name", "slug", "title", "value"):
            values.extend(_string_values(value.get(key)))
        return values
    if isinstance(value, (list, tuple, set, frozenset)):
        values: list[str] = []
        for item in value:
            values.extend(_string_values(item))
        return values
    return [str(value)]


def _normalize_text(value: Any) -> str:
    if value in (None, ""):
        return ""
    text = str(value).strip().lower()
    if not text:
        return ""
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def _count_keyword_hits(text: str, keywords: Iterable[str]) -> int:
    if not text:
        return 0
    haystack = f" {text} "
    hits = 0
    for keyword in keywords:
        needle = _normalize_text(keyword)
        if needle and f" {needle} " in haystack:
            hits += 1
    return hits


def _coerce_float(value: Any) -> float | None:
    try:
        if value in (None, ""):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _coerce_datetime(value: Any) -> datetime | None:
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


# ---------------------------------------------------------------------------
# Tape regime integrity (used by tape_manifest to derive + audit operator labels)
# ---------------------------------------------------------------------------


UNKNOWN = "unknown"


@dataclass(frozen=True)
class TapeRegimeIntegrity:
    """Regime provenance fields for one tape artifact.

    Produced by :func:`derive_tape_regime` and embedded in manifest tape entries.
    """
    derived_regime: str   # from classify_market_regime; "other" when signal is weak
    operator_regime: str  # label from tape metadata; "unknown" if absent
    final_regime: str     # authoritative regime for corpus counting
    regime_source: str    # "derived" | "operator" | "fallback_unknown"
    regime_mismatch: bool # True when derived and operator disagree (both named)


def derive_tape_regime(
    tape_metadata: Mapping[str, Any],
    *,
    operator_regime: str = "unknown",
    reference_time: Any = None,
) -> "TapeRegimeIntegrity":
    """Compute regime integrity fields for a tape artifact.

    Derives regime from tape metadata (slug, title, question, tags, created_at
    if available) using the shared classifier.  Compares derived classification
    against the operator-provided label and produces provenance fields so
    downstream artifacts can distinguish machine-derived from operator-entered
    regimes.

    Selection logic:
    - If derived regime is a named regime (politics/sports/new_market) -> use it
      as final_regime (more trustworthy than freeform operator input).
    - If derived is "other" (weak/no signal) and operator supplied a named
      regime -> use operator label as final_regime.
    - If both are weak/unknown -> final_regime = "unknown",
      regime_source = "fallback_unknown".

    Mismatch rule:
    - regime_mismatch = True ONLY when BOTH derived and operator are named
      regimes AND they disagree.  If either side is "other"/"unknown" there is
      not enough signal to declare a mismatch.

    Args:
        tape_metadata:    Dict of tape metadata fields (slug, title, question,
                          tags, created_at, etc.).  At minimum should contain
                          ``market_slug`` from watch_meta.json/prep_meta.json.
        operator_regime:  Regime label from tape metadata (the raw value read
                          from watch_meta.json or prep_meta.json).
        reference_time:   Used for new_market age check (optional).

    Returns:
        TapeRegimeIntegrity with derived_regime, operator_regime, final_regime,
        regime_source, and regime_mismatch.
    """
    market = _tape_metadata_to_market_dict(tape_metadata)
    derived = classify_market_regime(market, reference_time=reference_time)

    op_clean = operator_regime.lower().strip() if isinstance(operator_regime, str) else "unknown"
    op_named = op_clean in (POLITICS, SPORTS, NEW_MARKET)
    derived_named = derived in (POLITICS, SPORTS, NEW_MARKET)

    if derived_named:
        final_regime = derived
        regime_source = "derived"
    elif op_named:
        final_regime = op_clean
        regime_source = "operator"
    else:
        final_regime = UNKNOWN
        regime_source = "fallback_unknown"

    regime_mismatch = derived_named and op_named and (derived != op_clean)

    return TapeRegimeIntegrity(
        derived_regime=derived,
        operator_regime=operator_regime,
        final_regime=final_regime,
        regime_source=regime_source,
        regime_mismatch=regime_mismatch,
    )


def _tape_metadata_to_market_dict(tape_metadata: Mapping[str, Any]) -> dict:
    """Build a market-like dict from tape metadata for regime classification."""
    market: dict[str, Any] = {}
    _field_map = (
        ("market_slug", "slug"),
        ("slug", "slug"),
        ("title", "title"),
        ("question", "question"),
        ("tags", "tags"),
        ("category", "category"),
        ("subcategory", "subcategory"),
        ("event_slug", "event_slug"),
        ("event_title", "event_title"),
        ("created_at", "created_at"),
        ("age_hours", "age_hours"),
    )
    for src_key, dst_key in _field_map:
        value = tape_metadata.get(src_key)
        if value is not None and dst_key not in market:
            market[dst_key] = value
    return market


def coverage_from_classified_regimes(
    final_regimes: "Iterable[str]",
) -> "dict[str, Any]":
    """Check whether a set of pre-classified final_regimes covers required regimes.

    Unlike :func:`check_mixed_regime_coverage` which takes full market metadata
    dicts and derives regimes internally, this function takes already-classified
    regime strings (``final_regime`` values from :class:`TapeRegimeIntegrity`
    or ``TapeRecord``).

    Used by ``tape_manifest.build_corpus_summary`` to compute mixed-regime
    coverage from shared policy logic rather than ad hoc label counting.

    Args:
        final_regimes: Iterable of regime strings (e.g. from tape records).
                       Only ``politics``, ``sports``, ``new_market`` count toward
                       coverage; ``unknown`` and ``other`` are ignored.

    Returns:
        Same shape as :func:`check_mixed_regime_coverage`:
        ``{satisfies_policy, covered_regimes, missing_regimes, regime_counts}``
    """
    regime_counts: dict[str, int] = {regime: 0 for regime in REQUIRED_REGIMES}
    for regime in final_regimes:
        if regime in regime_counts:
            regime_counts[regime] += 1

    covered = tuple(r for r in REQUIRED_REGIMES if regime_counts[r] > 0)
    missing = tuple(r for r in REQUIRED_REGIMES if regime_counts[r] == 0)

    return {
        "satisfies_policy": len(missing) == 0,
        "covered_regimes": covered,
        "missing_regimes": missing,
        "regime_counts": dict(regime_counts),
    }
