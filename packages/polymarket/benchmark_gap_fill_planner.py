"""Benchmark v1 gap-fill planner.

Discovers Silver reconstruction targets from local pmxt + Jon-Becker data
to fill the shortage buckets in ``config/benchmark_v1.gap_report.json``.

Data sources queried (via DuckDB):

  pmxt_archive:   L2 orderbook snapshots (Polymarket subdirectory)
                  Covers 2026-03-15T10:00–15:00 UTC (5 hourly parquet files).
  jon_becker:     Historical trade + market metadata parquet files.
                  Markets parquet has: condition_id, question, slug,
                  clob_token_ids, end_date, created_at.

How it works:

  1. Query pmxt for distinct (condition_id, ts_start, ts_end) — no JSON
     extraction needed on the ``data`` column (condition_id = market_id).
  2. Load Jon-Becker markets parquet, filter to matching condition_ids
     (Python-side join; ~9k matched markets in practice).
  3. Classify each matched market into benchmark buckets using keyword +
     date-based rules.  Classification is conservative: uses only well-
     established keyword lists from the existing benchmark_manifest.py.
  4. Select priority-ordered targets per shortage bucket.
  5. Return a ``GapFillResult`` containing targets + per-bucket coverage.
     The caller writes output files:
       config/benchmark_v1_gap_fill.targets.json   (if any targets found)
       config/benchmark_v1_gap_fill.insufficiency.json (if any bucket still short)

Real-data findings (2026-03-17):

  politics:      2 052 candidates  (shortage=9  → COVERED)
  sports:        1 915 candidates  (shortage=11 → COVERED)
  crypto:          253 candidates  (shortage=10 → COVERED)
  near_resolution: 272 candidates  (shortage=9  → COVERED)
  new_market:        0 candidates  (shortage=5  → INSUFFICIENT)
    Reason: JB dataset snapshot is ~2026-02-03; no markets created after
    that date are present.  new_market requires markets created within 48h
    of 2026-03-15 — a gap the current local data cannot fill.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Schema versions
# ---------------------------------------------------------------------------

TARGETS_SCHEMA_VERSION = "benchmark_gap_fill_v1"
INSUFFICIENCY_SCHEMA_VERSION = "benchmark_gap_fill_insufficient_v1"

# ---------------------------------------------------------------------------
# Benchmark bucket definitions (mirrors benchmark_manifest.py)
# ---------------------------------------------------------------------------

BUCKET_ORDER = ("politics", "sports", "crypto", "near_resolution", "new_market")

# ---------------------------------------------------------------------------
# Classification keywords (conservative — mirrors benchmark_manifest.py)
# ---------------------------------------------------------------------------

_CRYPTO_KEYWORDS = frozenset({
    "bitcoin", "btc", "crypto", "cryptocurrency", "doge", "dogecoin",
    "ethereum", "eth", "solana", "sol", "xrp", "coinbase", "binance",
    "defi", "nft", "bnb", "blockchain", "chainlink", "stablecoin",
    "polygon", "matic", "uniswap", "arbitrum", "avax", "avalanche",
    "memecoin",
})

_POLITICS_KEYWORDS = frozenset({
    "ballot", "congress", "election", "elections", "government", "governor",
    "parliament", "politics", "political", "president", "presidential",
    "prime minister", "senate", "vote", "voting", "referendum", "mayor",
    "biden", "deport", "deportation", "trump", "harris", "tariff",
    "immigration", "kamala", "desantis",
})

_SPORTS_KEYWORDS = frozenset({
    "baseball", "basketball", "champions league", "cricket", "f1",
    "football", "formula 1", "golf", "hockey", "mlb", "mls", "mma",
    "nba", "ncaa", "nfl", "nhl", "premier league", "soccer", "sport",
    "sports", "super bowl", "tennis", "ufc", "wnba", "world cup",
    "stanley cup", "olympics",
})

# near_resolution: end_date within this many hours of reference_time
NEAR_RESOLUTION_MAX_HOURS = 48.0

# new_market: created within this many hours before reference_time
NEW_MARKET_MAX_HOURS = 48.0

# Max candidates to emit per bucket (priority 1 fills shortage; priority 2 is overflow)
_MAX_CANDIDATES_PER_BUCKET = 30

# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


@dataclass
class _MarketInfo:
    """Minimal market information used internally for classification."""

    condition_id: str
    token_id: str          # YES token (first clob_token_id)
    slug: str
    question: str
    end_date: Optional[datetime]
    created_at: Optional[datetime]
    window_start: str      # ISO UTC
    window_end: str        # ISO UTC


@dataclass
class GapFillTarget:
    """A single Silver reconstruction target."""

    bucket: str
    platform: str = "polymarket"
    slug: str = ""
    market_id: str = ""
    token_id: str = ""
    window_start: str = ""
    window_end: str = ""
    priority: int = 1
    selection_reason: str = ""
    price_2min_ready: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "bucket": self.bucket,
            "platform": self.platform,
            "slug": self.slug,
            "market_id": self.market_id,
            "token_id": self.token_id,
            "window_start": self.window_start,
            "window_end": self.window_end,
            "priority": self.priority,
            "selection_reason": self.selection_reason,
            "price_2min_ready": self.price_2min_ready,
        }


@dataclass
class BucketResult:
    """Coverage result for one benchmark bucket."""

    bucket: str
    shortage: int
    candidates_found: int
    targets_selected: int
    insufficient: bool
    insufficiency_reason: str = ""


@dataclass
class GapFillResult:
    """Overall result from the gap-fill planning run."""

    targets: List[GapFillTarget] = field(default_factory=list)
    bucket_results: List[BucketResult] = field(default_factory=list)
    generated_at: str = ""
    source_roots: Dict[str, str] = field(default_factory=dict)
    error: Optional[str] = None

    @property
    def any_targets(self) -> bool:
        return len(self.targets) > 0

    @property
    def fully_sufficient(self) -> bool:
        return all(not br.insufficient for br in self.bucket_results)

    def to_targets_dict(self) -> Dict[str, Any]:
        """Serialise to the targets.json contract (plus bucket_summary extension)."""
        bucket_summary: Dict[str, Any] = {}
        for br in self.bucket_results:
            bucket_summary[br.bucket] = {
                "shortage": br.shortage,
                "candidates_found": br.candidates_found,
                "targets_selected": br.targets_selected,
                "insufficient": br.insufficient,
                "insufficiency_reason": br.insufficiency_reason,
            }
        return {
            "schema_version": TARGETS_SCHEMA_VERSION,
            "generated_at": self.generated_at,
            "source_roots": self.source_roots,
            "bucket_summary": bucket_summary,
            "targets": [t.to_dict() for t in self.targets],
        }

    def to_insufficiency_dict(self) -> Dict[str, Any]:
        """Serialise to the insufficiency report contract."""
        insufficient = {
            br.bucket: {
                "shortage": br.shortage,
                "candidates_found": br.candidates_found,
                "reason": br.insufficiency_reason,
            }
            for br in self.bucket_results
            if br.insufficient
        }
        return {
            "schema_version": INSUFFICIENCY_SCHEMA_VERSION,
            "generated_at": self.generated_at,
            "source_roots": self.source_roots,
            "insufficient_buckets": insufficient,
            "error": self.error,
        }


# ---------------------------------------------------------------------------
# Injectable type aliases
# ---------------------------------------------------------------------------

PmxtFetchFn = Callable[[], List[Tuple[str, Any, Any]]]
# () -> [(condition_id, ts_start, ts_end), ...]

JonMarketsFetchFn = Callable[
    [Set[str]],
    List[Tuple[str, Optional[str], Optional[str], Optional[str], Any, Any]],
]
# (condition_ids) -> [(condition_id, question, slug, clob_token_ids_json, end_date, created_at), ...]

# ---------------------------------------------------------------------------
# DuckDB fetch helpers (real implementations)
# ---------------------------------------------------------------------------


def _real_fetch_pmxt(pmxt_root: str) -> List[Tuple[str, Any, Any]]:
    """Return [(condition_id, ts_start, ts_end)] from pmxt archive.

    Uses the ``market_id`` column directly (no JSON extraction from ``data``).
    """
    try:
        import duckdb  # noqa: PLC0415
    except ImportError:
        logger.warning("duckdb not available; pmxt probe skipped")
        return []

    glob = str(Path(pmxt_root).resolve() / "Polymarket" / "*.parquet").replace("\\", "/")
    try:
        conn = duckdb.connect()
        rows = conn.execute(
            f"""
            SELECT market_id,
                   MIN(timestamp_received) AS ts_start,
                   MAX(timestamp_received) AS ts_end
            FROM read_parquet('{glob}', union_by_name=true)
            GROUP BY market_id
            """
        ).fetchall()
        conn.close()
        return [(r[0], r[1], r[2]) for r in rows if r[0]]
    except Exception as exc:
        logger.warning("pmxt probe failed: %s", exc)
        return []


def _real_fetch_jon_markets(
    jon_root: str,
    condition_ids: Set[str],
) -> List[Tuple[str, Optional[str], Optional[str], Optional[str], Any, Any]]:
    """Return JB market metadata rows matching ``condition_ids``.

    Loads all markets parquet files and filters Python-side.
    Returns [(condition_id, question, slug, clob_token_ids_json, end_date, created_at)].
    """
    try:
        import duckdb  # noqa: PLC0415
    except ImportError:
        logger.warning("duckdb not available; JB markets probe skipped")
        return []

    glob = str(
        Path(jon_root).resolve() / "data" / "polymarket" / "markets" / "*.parquet"
    ).replace("\\", "/")
    try:
        conn = duckdb.connect()
        rows = conn.execute(
            f"""
            SELECT condition_id, question, slug, clob_token_ids, end_date, created_at
            FROM read_parquet('{glob}', union_by_name=true)
            WHERE condition_id IS NOT NULL
            """
        ).fetchall()
        conn.close()
        return [r for r in rows if r[0] in condition_ids]
    except Exception as exc:
        logger.warning("JB markets probe failed: %s", exc)
        return []


# ---------------------------------------------------------------------------
# Classification helpers
# ---------------------------------------------------------------------------


def _normalize_text(text: str) -> str:
    return text.lower().replace("-", " ").replace("_", " ")


def classify_market(
    question: str,
    slug: str,
    end_date: Optional[datetime],
    created_at: Optional[datetime],
    reference_time: datetime,
) -> Tuple[List[str], List[str]]:
    """Return (candidate_buckets, classification_notes) for a market.

    Classification is conservative: keyword lists are the same as those in
    ``benchmark_manifest.py``.  A market may qualify for multiple buckets.
    The returned list is ordered according to BUCKET_ORDER.

    Args:
        question:       Market question text.
        slug:           Market slug (hyphens treated as spaces).
        end_date:       Scheduled resolution datetime (tz-aware preferred).
        created_at:     Market creation datetime (tz-aware preferred).
        reference_time: Reference datetime for near_resolution/new_market
                        (tz-aware UTC; use pmxt capture start).

    Returns:
        (buckets, notes) — parallel lists, one entry per assigned bucket.
    """
    text = _normalize_text((question or "") + " " + (slug or ""))

    buckets: List[str] = []
    notes: List[str] = []

    if any(kw in text for kw in _SPORTS_KEYWORDS):
        buckets.append("sports")
        notes.append("sports via keyword match")

    if any(kw in text for kw in _POLITICS_KEYWORDS):
        buckets.append("politics")
        notes.append("politics via keyword match")

    if any(kw in text for kw in _CRYPTO_KEYWORDS):
        buckets.append("crypto")
        notes.append("crypto via keyword match")

    if end_date is not None:
        try:
            end_utc = (
                end_date.replace(tzinfo=timezone.utc)
                if end_date.tzinfo is None
                else end_date.astimezone(timezone.utc)
            )
            hours_to_end = (end_utc - reference_time).total_seconds() / 3600
            if 0.0 <= hours_to_end <= NEAR_RESOLUTION_MAX_HOURS:
                buckets.append("near_resolution")
                notes.append(
                    f"near_resolution via end_date hours_to_end={hours_to_end:.1f}"
                )
        except Exception:
            pass

    if created_at is not None:
        try:
            cr_utc = (
                created_at.replace(tzinfo=timezone.utc)
                if created_at.tzinfo is None
                else created_at.astimezone(timezone.utc)
            )
            age_hours = (reference_time - cr_utc).total_seconds() / 3600
            if 0.0 <= age_hours <= NEW_MARKET_MAX_HOURS:
                buckets.append("new_market")
                notes.append(f"new_market via created_at age_hours={age_hours:.1f}")
        except Exception:
            pass

    # Preserve BUCKET_ORDER ordering and deduplicate
    bucket_set = set(buckets)
    ordered_buckets = [b for b in BUCKET_ORDER if b in bucket_set]
    # Collect first note per bucket in order
    bucket_to_note: Dict[str, str] = {}
    for b, n in zip(buckets, notes):
        if b not in bucket_to_note:
            bucket_to_note[b] = n
    ordered_notes = [bucket_to_note[b] for b in ordered_buckets]
    return ordered_buckets, ordered_notes


def _parse_first_token_id(clob_token_ids_json: Optional[str]) -> str:
    """Extract the first (YES) token ID from JB ``clob_token_ids`` JSON string."""
    if not clob_token_ids_json:
        return ""
    try:
        tokens = json.loads(clob_token_ids_json)
        if isinstance(tokens, list) and tokens:
            return str(tokens[0]).strip()
    except (json.JSONDecodeError, TypeError):
        pass
    return ""


def _ts_to_utc_iso(ts: Any) -> str:
    """Convert a datetime (possibly tz-aware) to UTC ISO string."""
    if ts is None:
        return ""
    try:
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        return ts.astimezone(timezone.utc).isoformat()
    except Exception:
        return str(ts)


# ---------------------------------------------------------------------------
# Core planner
# ---------------------------------------------------------------------------


class GapFillPlanner:
    """Discover Silver reconstruction targets from pmxt + Jon-Becker data.

    Args:
        pmxt_root:              Root of pmxt_archive (expects Polymarket/ subdir).
        jon_root:               Root of Jon-Becker dataset (expects
                                data/polymarket/markets/).
        shortages:              Dict mapping bucket -> integer shortage count.
                                Typically from gap_report["shortages_by_bucket"].
        reference_time:         Reference datetime for near_resolution /
                                new_market classification.  Defaults to
                                2026-03-15T00:00Z (pmxt snapshot date).
        _pmxt_fetch_fn:         Injectable pmxt fetch (for offline testing).
        _jon_markets_fetch_fn:  Injectable JB markets fetch (for offline testing).
    """

    def __init__(
        self,
        pmxt_root: str,
        jon_root: str,
        shortages: Dict[str, int],
        *,
        reference_time: Optional[datetime] = None,
        _pmxt_fetch_fn: Optional[PmxtFetchFn] = None,
        _jon_markets_fetch_fn: Optional[JonMarketsFetchFn] = None,
    ) -> None:
        self._pmxt_root = pmxt_root
        self._jon_root = jon_root
        self._shortages = {b: shortages.get(b, 0) for b in BUCKET_ORDER}
        self._reference_time = reference_time or datetime(2026, 3, 15, tzinfo=timezone.utc)
        self._pmxt_fetch_fn = _pmxt_fetch_fn
        self._jon_markets_fetch_fn = _jon_markets_fetch_fn

    def plan(self) -> GapFillResult:
        """Run the gap-fill planning pipeline.

        Returns:
            GapFillResult with selected targets + per-bucket coverage.
        """
        now_iso = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        source_roots = {"pmxt_root": self._pmxt_root, "jon_root": self._jon_root}

        # 1. Fetch pmxt condition_ids + windows
        fetch_pmxt = self._pmxt_fetch_fn or (lambda: _real_fetch_pmxt(self._pmxt_root))
        try:
            pmxt_rows = fetch_pmxt()
        except Exception as exc:
            return GapFillResult(
                generated_at=now_iso,
                source_roots=source_roots,
                error=f"pmxt_fetch_failed: {exc}",
            )

        if not pmxt_rows:
            return GapFillResult(
                generated_at=now_iso,
                source_roots=source_roots,
                error="pmxt_probe_empty: no data returned from pmxt archive",
            )

        # Build {condition_id: (ts_start, ts_end)} (first-wins on duplicate condition_ids)
        pmxt_map: Dict[str, Tuple[Any, Any]] = {}
        for cid, ts_s, ts_e in pmxt_rows:
            if cid and cid not in pmxt_map:
                pmxt_map[cid] = (ts_s, ts_e)

        logger.info("pmxt: %d distinct condition_ids", len(pmxt_map))

        # 2. Fetch Jon-Becker market metadata for matching condition_ids
        condition_ids: Set[str] = set(pmxt_map.keys())
        fetch_jon = self._jon_markets_fetch_fn or (
            lambda ids: _real_fetch_jon_markets(self._jon_root, ids)
        )
        try:
            jb_rows = fetch_jon(condition_ids)
        except Exception as exc:
            return GapFillResult(
                generated_at=now_iso,
                source_roots=source_roots,
                error=f"jon_fetch_failed: {exc}",
            )

        logger.info("JB markets: %d rows matched condition_ids", len(jb_rows))

        # 3. Build _MarketInfo + classify
        markets_by_bucket: Dict[str, List[_MarketInfo]] = {b: [] for b in BUCKET_ORDER}

        for row in jb_rows:
            cid, question, slug, tok_json, end_date, created_at = row
            if cid not in pmxt_map:
                continue
            token_id = _parse_first_token_id(tok_json)
            if not token_id:
                continue

            ts_s, ts_e = pmxt_map[cid]
            window_start = _ts_to_utc_iso(ts_s)
            window_end = _ts_to_utc_iso(ts_e)

            buckets, _ = classify_market(
                question or "",
                slug or "",
                end_date,
                created_at,
                self._reference_time,
            )

            info = _MarketInfo(
                condition_id=cid,
                token_id=token_id,
                slug=slug or cid[:16],
                question=question or "",
                end_date=end_date,
                created_at=created_at,
                window_start=window_start,
                window_end=window_end,
            )
            for b in buckets:
                markets_by_bucket[b].append(info)

        # Deduplicate within each bucket (by condition_id), sort for determinism
        for bucket in BUCKET_ORDER:
            seen: Set[str] = set()
            unique: List[_MarketInfo] = []
            for m in sorted(markets_by_bucket[bucket], key=lambda x: x.slug):
                if m.condition_id not in seen:
                    seen.add(m.condition_id)
                    unique.append(m)
            markets_by_bucket[bucket] = unique

        # 4. Select targets per bucket
        targets: List[GapFillTarget] = []
        bucket_results: List[BucketResult] = []

        for bucket in BUCKET_ORDER:
            shortage = self._shortages.get(bucket, 0)
            candidates = list(markets_by_bucket[bucket])
            n_found = len(candidates)
            insufficient = n_found < shortage

            # near_resolution: prefer markets closest to resolution
            if bucket == "near_resolution":
                candidates = sorted(candidates, key=lambda m: _nr_sort_key(m, self._reference_time))

            max_emit = min(n_found, _MAX_CANDIDATES_PER_BUCKET)
            selected = 0

            for i, m in enumerate(candidates[:max_emit]):
                priority = 1 if i < shortage else 2
                reason = (
                    f"{bucket} via keyword/date classification from pmxt+JB "
                    f"(shortage={shortage})"
                )
                targets.append(
                    GapFillTarget(
                        bucket=bucket,
                        platform="polymarket",
                        slug=m.slug,
                        market_id=m.condition_id,
                        token_id=m.token_id,
                        window_start=m.window_start,
                        window_end=m.window_end,
                        priority=priority,
                        selection_reason=reason,
                        price_2min_ready=False,
                    )
                )
                if priority == 1:
                    selected += 1

            insuff_reason = ""
            if insufficient:
                insuff_reason = (
                    f"Only {n_found} candidates found; need {shortage}. "
                    "JB dataset snapshot likely predates the required creation window."
                )

            bucket_results.append(
                BucketResult(
                    bucket=bucket,
                    shortage=shortage,
                    candidates_found=n_found,
                    targets_selected=selected,
                    insufficient=insufficient,
                    insufficiency_reason=insuff_reason,
                )
            )

        return GapFillResult(
            targets=targets,
            bucket_results=bucket_results,
            generated_at=now_iso,
            source_roots=source_roots,
        )


def _nr_sort_key(m: _MarketInfo, ref: datetime) -> Tuple[float, str]:
    """Sort key for near_resolution: smallest positive hours_to_end first."""
    if m.end_date is None:
        return (1e12, m.slug)
    try:
        end_utc = (
            m.end_date.replace(tzinfo=timezone.utc)
            if m.end_date.tzinfo is None
            else m.end_date.astimezone(timezone.utc)
        )
        h = (end_utc - ref).total_seconds() / 3600
        return (max(h, 0.0), m.slug)
    except Exception:
        return (1e12, m.slug)


# ---------------------------------------------------------------------------
# Public run() convenience function
# ---------------------------------------------------------------------------


def run(
    pmxt_root: str,
    jon_root: str,
    gap_report: Dict[str, Any],
    *,
    out_path: Optional[Path] = None,
    insufficiency_path: Optional[Path] = None,
    reference_time: Optional[datetime] = None,
    _pmxt_fetch_fn: Optional[PmxtFetchFn] = None,
    _jon_markets_fetch_fn: Optional[JonMarketsFetchFn] = None,
) -> GapFillResult:
    """Run gap-fill planning and optionally write output files.

    Args:
        pmxt_root:            Root of pmxt_archive dataset.
        jon_root:             Root of Jon-Becker dataset.
        gap_report:           Parsed gap report dict.
        out_path:             Where to write targets.json (skipped if None).
        insufficiency_path:   Where to write insufficiency report (skipped if None).
        reference_time:       Reference time for classification (default: 2026-03-15).

    Returns:
        GapFillResult with all planning output.
    """
    shortages = gap_report.get("shortages_by_bucket", {})
    planner = GapFillPlanner(
        pmxt_root=pmxt_root,
        jon_root=jon_root,
        shortages=shortages,
        reference_time=reference_time,
        _pmxt_fetch_fn=_pmxt_fetch_fn,
        _jon_markets_fetch_fn=_jon_markets_fetch_fn,
    )
    result = planner.plan()

    if result.any_targets and out_path is not None:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(
            json.dumps(result.to_targets_dict(), indent=2, default=str) + "\n",
            encoding="utf-8",
        )
        logger.info("Written targets: %s (%d targets)", out_path, len(result.targets))

    has_insufficient = any(br.insufficient for br in result.bucket_results)
    if has_insufficient and insufficiency_path is not None:
        insufficiency_path.parent.mkdir(parents=True, exist_ok=True)
        insufficiency_path.write_text(
            json.dumps(result.to_insufficiency_dict(), indent=2, default=str) + "\n",
            encoding="utf-8",
        )
        logger.info("Written insufficiency report: %s", insufficiency_path)

    return result
