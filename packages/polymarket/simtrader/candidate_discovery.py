"""CandidateDiscovery — bucket-aware, shortage-boosted candidate ranking.

Replaces the flat ``auto_pick_many`` call in ``quickrun --list-candidates``
with a scored, ranked shortlist drawn from a larger market pool (up to 200–300
Gamma markets).

Exports:
    CandidateDiscovery  -- main class; call .rank() to get DiscoveryResult list
    DiscoveryResult     -- dataclass for one ranked candidate
    infer_bucket        -- pure function: raw_market dict -> bucket string
    score_for_capture   -- pure function: scores a candidate for tape capture
    load_live_shortage  -- reads current corpus shortage from tape directories
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Optional, Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Bucket constants
# ---------------------------------------------------------------------------

BUCKET_SPORTS = "sports"
BUCKET_POLITICS = "politics"
BUCKET_CRYPTO = "crypto"
BUCKET_NEW_MARKET = "new_market"
BUCKET_NEAR_RESOLUTION = "near_resolution"
BUCKET_OTHER = "other"

# Keywords for crypto detection (applied after regime classifier returns "other")
_CRYPTO_KEYWORDS = frozenset(
    {"btc", "eth", "sol", "crypto", "bitcoin", "ethereum", "solana"}
)

# Hours before end_date that triggers near_resolution bucket
_NEAR_RESOLUTION_HOURS = 72.0

# ---------------------------------------------------------------------------
# Phase 1B campaign defaults
# Update these after each capture batch using `python tools/gates/capture_status.py`
# ---------------------------------------------------------------------------
_DEFAULT_SHORTAGE: dict[str, int] = {
    BUCKET_SPORTS: 15,
    BUCKET_POLITICS: 9,
    BUCKET_CRYPTO: 10,
    BUCKET_NEW_MARKET: 5,
    BUCKET_NEAR_RESOLUTION: 1,
    BUCKET_OTHER: 0,
}

# ---------------------------------------------------------------------------
# Live shortage loader
# ---------------------------------------------------------------------------


def load_live_shortage(
    tape_roots: Optional[list[str]] = None,
) -> tuple[dict[str, int], str]:
    """Load current corpus shortage from tape directories.

    Returns (shortage_dict, source_label) where source_label is one of:
      "live (N tapes scanned)"  -- compute_status ran and found tapes
      "fallback (no tapes found)"  -- compute_status ran but found 0 tapes
      "fallback (import error)"  -- capture_status module unavailable
      "fallback (read error)"  -- unexpected exception during scan

    The shortage_dict always has entries for all 6 buckets including "other".
    Falls back to _DEFAULT_SHORTAGE on any failure.
    """
    try:
        from tools.gates.capture_status import compute_status, _REPO_ROOT  # noqa: PLC0415
        from tools.gates.corpus_audit import DEFAULT_TAPE_ROOTS  # noqa: PLC0415
        from pathlib import Path  # noqa: PLC0415
    except ImportError:
        return dict(_DEFAULT_SHORTAGE), "fallback (import error)"

    try:
        # Build tape_roots path list the same way capture_status.main() does
        root_strs = tape_roots if tape_roots is not None else DEFAULT_TAPE_ROOTS
        resolved_roots = [
            (Path(r) if Path(r).is_absolute() else _REPO_ROOT / r)
            for r in root_strs
        ]

        status = compute_status(resolved_roots)

        total_have = status.get("total_have", 0)
        total_need = status.get("total_need", 0)

        # Empty corpus — no tapes found at all
        if total_have == 0 and total_need == 0:
            return dict(_DEFAULT_SHORTAGE), "fallback (no tapes found)"

        # Build result dict: need per bucket, "other" always 0
        buckets_raw = status.get("buckets", {})
        result: dict[str, int] = {}
        for bucket in _DEFAULT_SHORTAGE.keys():
            if bucket == BUCKET_OTHER:
                result[bucket] = 0
            else:
                result[bucket] = int(buckets_raw.get(bucket, {}).get("need", 0))

        n_tapes = total_have
        return result, f"live ({n_tapes} tapes scanned)"

    except Exception as exc:  # noqa: BLE001
        return dict(_DEFAULT_SHORTAGE), f"fallback (read error: {exc})"


# ---------------------------------------------------------------------------
# Scoring weights
# ---------------------------------------------------------------------------

_W_SHORTAGE = 0.40
_W_DEPTH = 0.30
_W_PROBE = 0.20
_W_SPREAD = 0.10

_MAX_POOL_SIZE = 300
_DEPTH_NORM = 200.0  # depth_total normalisation cap
_SPREAD_NORM = 0.15  # spread width for full spread_score = 1.0


# ---------------------------------------------------------------------------
# DiscoveryResult dataclass
# ---------------------------------------------------------------------------


@dataclass
class DiscoveryResult:
    """One ranked candidate for tape capture."""

    slug: str
    question: str
    bucket: str
    score: float
    rank_reason: str
    yes_depth: float
    no_depth: float
    probe_summary: Optional[str]


# ---------------------------------------------------------------------------
# Pure helper functions
# ---------------------------------------------------------------------------


def infer_bucket(raw_market: dict) -> str:
    """Infer the corpus bucket for a raw Gamma market dict.

    Priority order:
    1. regime_policy.classify_market_regime -> "politics" | "sports" | "new_market"
    2. near_resolution heuristic: end_date_iso within 72h of now (UTC)
       (only applied when regime is not politics/sports)
    3. crypto keyword heuristic: slug + question contain BTC/ETH/SOL/crypto keywords
    4. Fallback: "other"

    Args:
        raw_market: Raw market metadata dict from Gamma API.

    Returns:
        One of: "sports", "politics", "crypto", "near_resolution", "new_market", "other".
    """
    from packages.polymarket.market_selection.regime_policy import classify_market_regime

    regime = classify_market_regime(raw_market)

    # Regime classifier covers politics, sports, new_market directly.
    if regime == BUCKET_POLITICS:
        return BUCKET_POLITICS
    if regime == BUCKET_SPORTS:
        return BUCKET_SPORTS
    if regime == BUCKET_NEW_MARKET:
        return BUCKET_NEW_MARKET

    # Near-resolution heuristic (end_date_iso within 72h, not already classified)
    end_date_str = raw_market.get("end_date_iso") or raw_market.get("endDateIso") or ""
    if end_date_str:
        try:
            end_dt = datetime.fromisoformat(str(end_date_str).replace("Z", "+00:00"))
            if end_dt.tzinfo is None:
                end_dt = end_dt.replace(tzinfo=timezone.utc)
            now_utc = datetime.now(timezone.utc)
            hours_until_end = (end_dt - now_utc).total_seconds() / 3600.0
            if 0.0 < hours_until_end <= _NEAR_RESOLUTION_HOURS:
                return BUCKET_NEAR_RESOLUTION
        except (ValueError, TypeError):
            pass

    # Crypto keyword heuristic
    slug = str(raw_market.get("slug") or "").lower()
    question = str(raw_market.get("question") or "").lower()
    combined_text = f"{slug} {question}"
    for kw in _CRYPTO_KEYWORDS:
        if kw in combined_text:
            return BUCKET_CRYPTO

    return BUCKET_OTHER


def score_for_capture(
    resolved_market: Any,
    raw_meta: dict,
    shortage: dict[str, int],
    yes_val: Any,
    no_val: Any,
    probe_results: Optional[dict],
    bucket: str,
) -> float:
    """Score a candidate market for tape capture suitability.

    Returns 0.0 immediately when either book is one-sided or empty (these
    markets are not capture-eligible).

    Scoring formula:
        shortage_boost  = clamp(shortage[bucket] / 15.0, 0, 1)  weight=0.40
        depth_score     = min(depth_total, 200) / 200.0          weight=0.30
        probe_score     = 1.0 | 0.0 | 0.5 (active|inactive|no probe)  weight=0.20
        spread_score    = clamp((ask - bid) / 0.15, 0, 1)        weight=0.10

    Args:
        resolved_market:  ResolvedMarket (or mock with .yes_token_id / .no_token_id).
        raw_meta:         Raw Gamma market dict for metadata.
        shortage:         Bucket->shortfall count dict.
        yes_val:          BookValidation for the YES token.
        no_val:           BookValidation for the NO token.
        probe_results:    ProbeResult mapping from activeness probe (or None).
        bucket:           Inferred bucket string for this market.

    Returns:
        Float in [0.0, 1.0].  Returns 0.0 for one-sided or empty books.
    """
    # Immediate reject for unusable books
    _reject_reasons = {"one_sided_book", "empty_book"}
    if (
        getattr(yes_val, "reason", None) in _reject_reasons
        or getattr(no_val, "reason", None) in _reject_reasons
    ):
        return 0.0

    # Also reject if book is marked invalid (fetch_failed, error_response, shallow_book)
    if not getattr(yes_val, "valid", True) or not getattr(no_val, "valid", True):
        return 0.0

    # --- shortage_boost ---
    shortage_val = shortage.get(bucket, 0)
    shortage_boost = min(max(shortage_val / 15.0, 0.0), 1.0)

    # --- depth_score ---
    yes_depth = getattr(yes_val, "depth_total", None) or 0.0
    no_depth = getattr(no_val, "depth_total", None) or 0.0
    depth_total = (yes_depth + no_depth) / 2.0  # average of both sides
    depth_score = min(depth_total, _DEPTH_NORM) / _DEPTH_NORM

    # --- probe_score ---
    if probe_results is None:
        probe_score = 0.5
    else:
        any_active = any(
            getattr(r, "active", False) for r in probe_results.values()
        )
        probe_score = 1.0 if any_active else 0.0

    # --- spread_score ---
    yes_bid = getattr(yes_val, "best_bid", None)
    yes_ask = getattr(yes_val, "best_ask", None)
    if yes_bid is not None and yes_ask is not None:
        spread = abs(yes_ask - yes_bid)
        spread_score = min(max(spread / _SPREAD_NORM, 0.0), 1.0)
    else:
        spread_score = 0.0

    return (
        _W_SHORTAGE * shortage_boost
        + _W_DEPTH * depth_score
        + _W_PROBE * probe_score
        + _W_SPREAD * spread_score
    )


def rank_reason(
    bucket: str,
    shortage: dict[str, int],
    score: float,
    depth_total: Optional[float],
    probe_active: Optional[bool],
) -> str:
    """Build a human-readable explanation string for a candidate's rank.

    Example output:
        "bucket=sports shortage=15 score=0.87 depth=142 probe=active"

    Args:
        bucket:       Inferred bucket string.
        shortage:     Bucket shortage dict.
        score:        Computed score (0..1).
        depth_total:  Combined depth total, or None.
        probe_active: True=active, False=inactive, None=no probe run.

    Returns:
        Human-readable rank reason string.
    """
    parts = [
        f"bucket={bucket}",
        f"shortage={shortage.get(bucket, 0)}",
        f"score={score:.2f}",
    ]
    if depth_total is not None:
        parts.append(f"depth={depth_total:.0f}")
    if probe_active is True:
        parts.append("probe=active")
    elif probe_active is False:
        parts.append("probe=inactive")
    return " ".join(parts)


# ---------------------------------------------------------------------------
# CandidateDiscovery class
# ---------------------------------------------------------------------------


class CandidateDiscovery:
    """Fetch, score, and rank candidate markets for tape capture.

    Args:
        picker:   MarketPicker instance for market resolution and book validation.
        shortage: Bucket shortage dict (bucket -> count of tapes still needed).
                  Defaults to Phase 1B campaign values when not supplied.
    """

    def __init__(self, picker: Any, shortage: Optional[dict[str, int]] = None) -> None:
        self._picker = picker
        self._shortage: dict[str, int] = dict(shortage) if shortage else dict(_DEFAULT_SHORTAGE)

    def rank(
        self,
        n: int,
        pool_size: int = 200,
        probe_config: Optional[dict] = None,
        collect_skips: Optional[list] = None,
        exclude_slugs: Optional[set] = None,
    ) -> list[DiscoveryResult]:
        """Rank up to ``n`` markets by capture suitability.

        Fetches ``pool_size`` raw markets from Gamma (via paginated calls),
        resolves + validates each via ``auto_pick_many``, infers bucket,
        computes score, sorts descending, returns top ``n``.

        One-sided / empty / failed markets are excluded (score == 0.0).

        Args:
            n:             Maximum number of results to return.
            pool_size:     Candidate pool to fetch (default 200, clamped to 300).
            probe_config:  Optional activeness probe config dict.
            collect_skips: If not None, skip reasons are appended here.
            exclude_slugs: Slugs to exclude from consideration.

        Returns:
            List of DiscoveryResult sorted by score descending (length <= n).
        """
        pool_size = min(max(pool_size, 1), _MAX_POOL_SIZE)

        # Step 1: Collect raw market pages (up to pool_size)
        raw_index: dict[str, dict] = {}
        fetched = 0
        page_limit = 100
        for offset in range(0, pool_size, page_limit):
            batch_limit = min(page_limit, pool_size - fetched)
            try:
                page = self._picker._gamma.fetch_markets_page(
                    limit=batch_limit,
                    offset=offset,
                    active_only=True,
                )
            except Exception as exc:  # noqa: BLE001
                logger.debug("fetch_markets_page(offset=%d) failed: %s", offset, exc)
                break

            if not page:
                break

            for raw in page:
                if isinstance(raw, dict):
                    slug = raw.get("slug") or raw.get("market_slug") or ""
                    if slug:
                        raw_index[slug] = raw
            fetched += len(page)
            if fetched >= pool_size:
                break

        if not raw_index:
            return []

        # Step 2: Resolve + validate via auto_pick_many
        try:
            resolved_list = self._picker.auto_pick_many(
                n=pool_size,
                max_candidates=pool_size,
                allow_empty_book=False,
                min_depth_size=0.0,
                collect_skips=collect_skips,
                exclude_slugs=exclude_slugs,
                probe_config=probe_config,
            )
        except Exception as exc:  # noqa: BLE001
            logger.debug("auto_pick_many failed: %s", exc)
            return []

        if not resolved_list:
            return []

        # Step 3: Score each resolved market
        results: list[DiscoveryResult] = []

        for resolved in resolved_list:
            slug = getattr(resolved, "slug", "")
            raw_meta = raw_index.get(slug, {})

            # Infer bucket
            bucket = infer_bucket(raw_meta) if raw_meta else BUCKET_OTHER

            # Validate both books to get depth stats
            yes_val, no_val = self._validate_both_books(resolved, None, None)

            # Compute score
            probe_results = getattr(resolved, "probe_results", None)
            sc = score_for_capture(
                resolved, raw_meta, self._shortage, yes_val, no_val, probe_results, bucket
            )

            # Filter out zero-score markets (one-sided, empty, failed)
            if sc == 0.0:
                logger.debug("Skipping %r: score=0.0 (one-sided/empty/failed)", slug)
                continue

            # Compute display values
            yes_depth = getattr(yes_val, "depth_total", None) or 0.0
            no_depth = getattr(no_val, "depth_total", None) or 0.0
            combined_depth = yes_depth + no_depth

            # Probe summary string
            probe_summary: Optional[str] = None
            if probe_results is not None:
                active_count = sum(
                    1 for r in probe_results.values() if getattr(r, "active", False)
                )
                total_updates = sum(
                    getattr(r, "updates", 0) for r in probe_results.values()
                )
                probe_summary = f"{active_count}/{len(probe_results)} active, {total_updates} updates"

            # Determine probe_active for rank_reason
            probe_active: Optional[bool] = None
            if probe_results is not None:
                probe_active = any(
                    getattr(r, "active", False) for r in probe_results.values()
                )

            reason = rank_reason(
                bucket,
                self._shortage,
                sc,
                combined_depth if (yes_depth or no_depth) else None,
                probe_active,
            )

            results.append(
                DiscoveryResult(
                    slug=slug,
                    question=getattr(resolved, "question", ""),
                    bucket=bucket,
                    score=sc,
                    rank_reason=reason,
                    yes_depth=yes_depth,
                    no_depth=no_depth,
                    probe_summary=probe_summary,
                )
            )

        # Step 4: Sort descending by score, return top n
        results.sort(key=lambda r: r.score, reverse=True)
        return results[:n]

    def _validate_both_books(
        self,
        resolved: Any,
        yes_val: Any,
        no_val: Any,
    ) -> tuple:
        """Validate YES and NO books for a resolved market.

        If yes_val / no_val are already provided (non-None), returns them directly.
        Otherwise calls picker.validate_book for each token.

        Returns:
            (yes_val, no_val) tuple of BookValidation objects.
        """
        if yes_val is None:
            yes_val = self._picker.validate_book(
                getattr(resolved, "yes_token_id", ""),
                allow_empty=False,
                min_depth_size=0.0,
                top_n_levels=3,
            )
        if no_val is None:
            no_val = self._picker.validate_book(
                getattr(resolved, "no_token_id", ""),
                allow_empty=False,
                min_depth_size=0.0,
                top_n_levels=3,
            )
        return yes_val, no_val
