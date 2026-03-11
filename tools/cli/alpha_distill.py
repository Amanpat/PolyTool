#!/usr/bin/env python3
"""Alpha-Distill v0: read wallet-scan outputs and segment_analysis artifacts, emit candidate
edge hypotheses as structured JSON (no LLM).

CLI: python -m polytool alpha-distill --wallet-scan-run <path> [--out alpha_candidates.json]

All outputs are explainable and falsifiable. No black-box scores. No LLM calls.
No strategy execution. Research-only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

SCHEMA_VERSION = "alpha_distill_v0"

# Minimum positions (across all contributing users) to form a candidate.
DEFAULT_MIN_SAMPLE = 30

# Conservative fee adjustment applied to CLV% estimates.
# This represents a pessimistic friction estimate (2 pp) to guard against
# overstating edge net of transaction costs.
DEFAULT_CONSERVATIVE_FEE_ADJ = 0.02

# Minimum users that must contribute to a segment for a "persistent" signal.
DEFAULT_MIN_USERS_PERSISTENCE = 2

# Segment dimensions to analyze (label, segment_analysis.json dict key).
SEGMENT_AXES: List[Tuple[str, str]] = [
    ("entry_price_tier", "by_entry_price_tier"),
    ("market_type", "by_market_type"),
    ("league", "by_league"),
    ("sport", "by_sport"),
    ("category", "by_category"),
]

# Segment keys that carry no signal (aggregate residual / data quality bucket).
_SKIP_SEGMENT_KEYS = {"unknown", "Unknown", "total"}


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _iso_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat()


def _safe_float(value: Any) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_int(value: Any) -> Optional[int]:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _round6(v: Optional[float]) -> Optional[float]:
    return round(v, 6) if v is not None else None


def _read_json(path: Path) -> Dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False),
        encoding="utf-8",
    )


def _candidate_id(dimension: str, key: str, rank: int) -> str:
    return f"{dimension}__{key}__rank{rank:03d}"


# ---------------------------------------------------------------------------
# Loading wallet-scan outputs
# ---------------------------------------------------------------------------


def load_wallet_scan_run(wallet_scan_run: Path) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """Load leaderboard.json and per_user_results.jsonl from a wallet-scan run root.

    Returns (leaderboard_payload, per_user_records).
    """
    leaderboard_path = wallet_scan_run / "leaderboard.json"
    jsonl_path = wallet_scan_run / "per_user_results.jsonl"

    if not leaderboard_path.exists():
        raise FileNotFoundError(f"leaderboard.json not found in {wallet_scan_run}")
    if not jsonl_path.exists():
        raise FileNotFoundError(f"per_user_results.jsonl not found in {wallet_scan_run}")

    leaderboard = _read_json(leaderboard_path)

    per_user: List[Dict[str, Any]] = []
    for line in jsonl_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
            if isinstance(record, dict):
                per_user.append(record)
        except json.JSONDecodeError:
            continue

    return leaderboard, per_user


# ---------------------------------------------------------------------------
# Per-user segment data loading
# ---------------------------------------------------------------------------


def load_user_segment_analysis(run_root: str) -> Optional[Dict[str, Any]]:
    """Load segment_analysis.json from a scan run_root path.

    Returns the inner ``segment_analysis`` dict, or None on any error.
    """
    path = Path(run_root) / "segment_analysis.json"
    if not path.exists():
        return None
    try:
        payload = _read_json(path)
    except Exception:
        return None
    # segment_analysis.json wraps data under the "segment_analysis" key
    inner = payload.get("segment_analysis")
    return inner if isinstance(inner, dict) else None


# ---------------------------------------------------------------------------
# Cross-user segment aggregation
# ---------------------------------------------------------------------------


class _SegmentAccumulator:
    """Accumulates segment metrics across multiple users for one (dimension, key)."""

    def __init__(self, dimension: str, key: str) -> None:
        self.dimension = dimension
        self.key = key

        self.users: List[str] = []
        self.evidence_refs: List[Dict[str, Any]] = []

        # Summed accumulators (re-weighted from individual bucket finalized metrics)
        self.total_count: int = 0
        self.total_pnl_net: float = 0.0

        # Win-rate numerator / denominator
        self._win_numerator: int = 0   # wins + profit_exits
        self._win_denominator: int = 0  # wins + losses + profit_exits + loss_exits

        # CLV (count-weighted): sum(avg_clv * count_used) / sum(count_used)
        self._clv_weighted_sum: float = 0.0
        self._clv_count_used: int = 0

        # Beat-close rate (count-weighted)
        self._beat_close_weighted_sum: float = 0.0
        self._beat_close_count_used: int = 0

        # Notional-weighted CLV: sum(nw_avg_clv * nw_weight) / sum(nw_weight)
        self._nw_clv_sum: float = 0.0
        self._nw_clv_weight: float = 0.0

        # Notional-weighted beat-close
        self._nw_beat_close_sum: float = 0.0
        self._nw_beat_close_weight: float = 0.0

    def add(self, slug: str, run_root: str, bucket: Dict[str, Any]) -> None:
        count = _safe_int(bucket.get("count")) or 0
        if count <= 0:
            return

        self.users.append(slug)
        self.evidence_refs.append({
            "user": slug,
            "run_root": run_root,
            "segment_file": (Path(run_root) / "segment_analysis.json").as_posix(),
            "dimension": self.dimension,
            "key": self.key,
            "count": count,
        })

        self.total_count += count
        self.total_pnl_net += _safe_float(bucket.get("total_pnl_net")) or 0.0

        # Win-rate
        wins = _safe_int(bucket.get("wins")) or 0
        losses = _safe_int(bucket.get("losses")) or 0
        profit_exits = _safe_int(bucket.get("profit_exits")) or 0
        loss_exits = _safe_int(bucket.get("loss_exits")) or 0
        self._win_numerator += wins + profit_exits
        self._win_denominator += wins + losses + profit_exits + loss_exits

        # Count-weighted CLV
        clv_count = _safe_int(bucket.get("avg_clv_pct_count_used")) or 0
        avg_clv = _safe_float(bucket.get("avg_clv_pct"))
        if avg_clv is not None and clv_count > 0:
            self._clv_weighted_sum += avg_clv * clv_count
            self._clv_count_used += clv_count

        # Count-weighted beat-close
        bc_count = _safe_int(bucket.get("beat_close_rate_count_used")) or 0
        bc_rate = _safe_float(bucket.get("beat_close_rate"))
        if bc_rate is not None and bc_count > 0:
            self._beat_close_weighted_sum += bc_rate * bc_count
            self._beat_close_count_used += bc_count

        # Notional-weighted CLV
        nw_clv_weight = _safe_float(bucket.get("notional_weighted_avg_clv_pct_weight_used")) or 0.0
        nw_clv_avg = _safe_float(bucket.get("notional_weighted_avg_clv_pct"))
        if nw_clv_avg is not None and nw_clv_weight > 0:
            self._nw_clv_sum += nw_clv_avg * nw_clv_weight
            self._nw_clv_weight += nw_clv_weight

        # Notional-weighted beat-close
        nw_bc_weight = _safe_float(bucket.get("notional_weighted_beat_close_rate_weight_used")) or 0.0
        nw_bc_rate = _safe_float(bucket.get("notional_weighted_beat_close_rate"))
        if nw_bc_rate is not None and nw_bc_weight > 0:
            self._nw_beat_close_sum += nw_bc_rate * nw_bc_weight
            self._nw_beat_close_weight += nw_bc_weight

    @property
    def users_contributing(self) -> int:
        return len(set(self.users))

    def aggregate_win_rate(self) -> Optional[float]:
        if self._win_denominator <= 0:
            return None
        return _round6(self._win_numerator / self._win_denominator)

    def aggregate_avg_clv_pct(self) -> Optional[float]:
        if self._clv_count_used <= 0:
            return None
        return _round6(self._clv_weighted_sum / self._clv_count_used)

    def aggregate_beat_close_rate(self) -> Optional[float]:
        if self._beat_close_count_used <= 0:
            return None
        return _round6(self._beat_close_weighted_sum / self._beat_close_count_used)

    def aggregate_nw_clv_pct(self) -> Optional[float]:
        if self._nw_clv_weight <= 0:
            return None
        return _round6(self._nw_clv_sum / self._nw_clv_weight)

    def aggregate_nw_beat_close_rate(self) -> Optional[float]:
        if self._nw_beat_close_weight <= 0:
            return None
        return _round6(self._nw_beat_close_sum / self._nw_beat_close_weight)


# ---------------------------------------------------------------------------
# Candidate construction
# ---------------------------------------------------------------------------

# Human-readable labels for each segment dimension.
_DIMENSION_LABELS: Dict[str, str] = {
    "entry_price_tier": "entry price tier",
    "market_type": "market type",
    "league": "league",
    "sport": "sport",
    "category": "category",
}

# Mechanism hints per dimension (static research-quality text).
_MECHANISM_HINTS: Dict[str, str] = {
    "entry_price_tier": (
        "Traders entering at this price tier may be systematically identifying "
        "mis-priced outcomes or have an informational edge at this probability range."
    ),
    "market_type": (
        "Performance concentration in this market type may reflect domain expertise "
        "or structural liquidity advantages in moneyline vs spread pricing."
    ),
    "league": (
        "Edge concentrated in a specific sports league may indicate league-specific "
        "knowledge, better information flow, or market inefficiency in that league."
    ),
    "sport": (
        "Consistent outperformance within a sport may reflect sport-specific "
        "expertise or structural market differences across sports segments."
    ),
    "category": (
        "Category-level concentration may indicate domain expertise (sports, politics, "
        "crypto) or liquidity differences between prediction market categories."
    ),
}


def _friction_risk_flags(
    acc: _SegmentAccumulator,
    min_sample: int,
) -> List[str]:
    flags: List[str] = []

    # Always set in v0 — fees are estimated, not actual per-trade rates
    flags.append("fee_estimate_only")

    if acc.total_count < min_sample:
        flags.append("small_sample")

    if acc.users_contributing < 2:
        flags.append("single_user_only")

    # CLV data sparsity: count_used / total_count < 0.30
    clv_coverage = acc._clv_count_used / acc.total_count if acc.total_count > 0 else 0.0
    if clv_coverage < 0.30:
        flags.append("clv_data_sparse")

    return flags


def _next_test(dimension: str, key: str, acc: _SegmentAccumulator, min_sample: int) -> str:
    needed = max(0, min_sample - acc.total_count)
    if needed > 0:
        return (
            f"Collect {needed}+ more positions in {dimension}={key} to reach min_sample={min_sample}; "
            f"run scan with --compute-clv enabled to populate CLV coverage."
        )
    return (
        f"With N={acc.total_count} across {acc.users_contributing} user(s), "
        f"verify notional_weighted_avg_clv_pct persists above conservative_fee_adj={DEFAULT_CONSERVATIVE_FEE_ADJ:.2f} "
        f"across a new cohort of users not in this wallet-scan run."
    )


def _stop_condition(dimension: str, key: str, min_sample: int) -> str:
    stop_n = min_sample * 3
    return (
        f"Discard hypothesis if beat_close_rate drops below 0.50 with total_count >= {stop_n} "
        f"across 3+ users; or if notional_weighted_avg_clv_pct becomes negative with "
        f"total_count >= {min_sample * 2} and clv_count_used >= {min_sample}."
    )


def _build_candidate(
    acc: _SegmentAccumulator,
    *,
    rank: int,
    min_sample: int,
    conservative_fee_adj: float,
) -> Dict[str, Any]:
    dimension = acc.dimension
    key = acc.key
    dim_label = _DIMENSION_LABELS.get(dimension, dimension)

    avg_clv = acc.aggregate_avg_clv_pct()
    nw_clv = acc.aggregate_nw_clv_pct()
    beat_close = acc.aggregate_beat_close_rate()
    nw_beat_close = acc.aggregate_nw_beat_close_rate()
    win_rate = acc.aggregate_win_rate()

    # Primary edge estimate: prefer notional-weighted CLV, fall back to count-weighted
    primary_clv = nw_clv if nw_clv is not None else avg_clv
    net_clv_after_fee = _round6(primary_clv - conservative_fee_adj) if primary_clv is not None else None

    return {
        "candidate_id": _candidate_id(dimension, key, rank),
        "rank": rank,
        "label": f"{dim_label.capitalize()} edge ({dimension}={key})",
        "mechanism_hint": _MECHANISM_HINTS.get(dimension, ""),
        "evidence_refs": acc.evidence_refs,
        "sample_size": acc.total_count,
        "required_min_sample": min_sample,
        "measured_edge": {
            "total_count": acc.total_count,
            "total_pnl_net": _round6(acc.total_pnl_net),
            "win_rate": win_rate,
            "win_rate_denominator": acc._win_denominator,
            "avg_clv_pct": avg_clv,
            "avg_clv_pct_count_used": acc._clv_count_used,
            "beat_close_rate": beat_close,
            "beat_close_rate_count_used": acc._beat_close_count_used,
            "notional_weighted_avg_clv_pct": nw_clv,
            "notional_weighted_avg_clv_pct_weight_used": _round6(acc._nw_clv_weight),
            "notional_weighted_beat_close_rate": nw_beat_close,
            "notional_weighted_beat_close_rate_weight_used": _round6(acc._nw_beat_close_weight),
            "users_contributing": acc.users_contributing,
            "conservative_fee_adj": conservative_fee_adj,
            "net_clv_after_fee_adj": net_clv_after_fee,
        },
        "friction_risk_flags": _friction_risk_flags(acc, min_sample),
        "next_test": _next_test(dimension, key, acc, min_sample),
        "stop_condition": _stop_condition(dimension, key, min_sample),
    }


# ---------------------------------------------------------------------------
# Scoring and ranking
# ---------------------------------------------------------------------------


def _score_accumulator(
    acc: _SegmentAccumulator,
    *,
    conservative_fee_adj: float,
) -> float:
    """Compute a scalar rank score (higher = better candidate).

    Priority:
      (a) Users contributing — persistence across wallets is the strongest signal.
      (b) Total count — larger sample is more trustworthy.
      (c) Net CLV after conservative fee adjustment — positive edge indicator.

    Each component is scaled so that persistence dominates, count is secondary,
    and edge is a tiebreaker. This is intentionally conservative.
    """
    persistence_score = acc.users_contributing * 1_000.0

    count_score = min(acc.total_count, 500) * 1.0  # cap at 500 to prevent huge samples dominating

    # Primary CLV (notional-weighted preferred)
    nw_clv = acc.aggregate_nw_clv_pct()
    avg_clv = acc.aggregate_avg_clv_pct()
    primary_clv = nw_clv if nw_clv is not None else avg_clv
    net_clv = (primary_clv - conservative_fee_adj) if primary_clv is not None else None
    edge_score = max(0.0, net_clv * 500.0) if net_clv is not None else 0.0

    return persistence_score + count_score + edge_score


# ---------------------------------------------------------------------------
# Main distillation logic
# ---------------------------------------------------------------------------


def distill(
    wallet_scan_run: Path,
    *,
    min_sample: int = DEFAULT_MIN_SAMPLE,
    conservative_fee_adj: float = DEFAULT_CONSERVATIVE_FEE_ADJ,
    min_users_persistence: int = DEFAULT_MIN_USERS_PERSISTENCE,
    run_id: Optional[str] = None,
    now_provider=None,
) -> Dict[str, Any]:
    """Run the full distillation pipeline.

    Returns the full alpha_candidates payload (suitable for JSON serialization).
    """
    if now_provider is None:
        now_provider = _utcnow
    now = now_provider()
    created_at = _iso_utc(now)
    run_id = run_id or str(uuid.uuid4())

    # --- Load wallet-scan outputs ---
    leaderboard, per_user = load_wallet_scan_run(wallet_scan_run)

    # Only process users whose scans succeeded and have a run_root
    succeeded_users = [
        r for r in per_user
        if r.get("status") == "success" and r.get("run_root")
    ]

    # --- Accumulate per-(dimension, key) across users ---
    # acc_map: (dimension, key) -> _SegmentAccumulator
    acc_map: Dict[Tuple[str, str], _SegmentAccumulator] = {}
    users_analyzed: int = 0
    users_with_segment_data: int = 0

    for user_record in succeeded_users:
        slug = str(user_record.get("slug") or user_record.get("identifier") or "unknown")
        run_root = str(user_record["run_root"])
        users_analyzed += 1

        seg_analysis = load_user_segment_analysis(run_root)
        if seg_analysis is None:
            continue
        users_with_segment_data += 1

        for dimension, field in SEGMENT_AXES:
            buckets = seg_analysis.get(field)
            if not isinstance(buckets, dict):
                continue
            for key, bucket in buckets.items():
                if key in _SKIP_SEGMENT_KEYS:
                    continue
                if not isinstance(bucket, dict):
                    continue
                count = _safe_int(bucket.get("count")) or 0
                if count <= 0:
                    continue

                acc_key = (dimension, key)
                if acc_key not in acc_map:
                    acc_map[acc_key] = _SegmentAccumulator(dimension, key)
                acc_map[acc_key].add(slug, run_root, bucket)

    total_segments_evaluated = len(acc_map)

    # --- Filter and score candidates ---
    scored: List[Tuple[float, _SegmentAccumulator]] = []
    for acc in acc_map.values():
        if acc.total_count < min_sample:
            continue
        score = _score_accumulator(acc, conservative_fee_adj=conservative_fee_adj)
        scored.append((score, acc))

    # Sort descending by score, tiebreak by (dimension, key) for determinism
    scored.sort(key=lambda t: (-t[0], t[1].dimension, t[1].key))

    # --- Build candidates ---
    candidates: List[Dict[str, Any]] = []
    for rank, (_, acc) in enumerate(scored, start=1):
        candidate = _build_candidate(
            acc,
            rank=rank,
            min_sample=min_sample,
            conservative_fee_adj=conservative_fee_adj,
        )
        candidates.append(candidate)

    return {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "created_at": created_at,
        "wallet_scan_run_root": wallet_scan_run.as_posix(),
        "parameters": {
            "min_sample_size": min_sample,
            "conservative_fee_adj": conservative_fee_adj,
            "min_users_persistence": min_users_persistence,
        },
        "summary": {
            "total_users_in_leaderboard": len(per_user),
            "total_users_analyzed": users_analyzed,
            "users_with_segment_data": users_with_segment_data,
            "total_segments_evaluated": total_segments_evaluated,
            "candidates_generated": len(candidates),
        },
        "candidates": candidates,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Alpha-Distill v0: read wallet-scan outputs + segment_analysis artifacts "
            "and emit candidate edge hypotheses as structured JSON. No LLM. No execution."
        )
    )
    parser.add_argument(
        "--wallet-scan-run",
        required=True,
        help="Path to a wallet-scan run root directory (must contain leaderboard.json + per_user_results.jsonl).",
    )
    parser.add_argument(
        "--out",
        default=None,
        help="Output path for alpha_candidates.json (default: <wallet-scan-run>/alpha_candidates.json).",
    )
    parser.add_argument(
        "--min-sample",
        type=int,
        default=DEFAULT_MIN_SAMPLE,
        help=f"Minimum total positions for a segment candidate (default: {DEFAULT_MIN_SAMPLE}).",
    )
    parser.add_argument(
        "--fee-adj",
        type=float,
        default=DEFAULT_CONSERVATIVE_FEE_ADJ,
        help=(
            f"Conservative fee adjustment subtracted from CLV%% to estimate net edge "
            f"(default: {DEFAULT_CONSERVATIVE_FEE_ADJ:.2f})."
        ),
    )
    parser.add_argument(
        "--run-id",
        help="Optional run ID (default: random uuid4).",
    )
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    wallet_scan_run = Path(args.wallet_scan_run)
    if not wallet_scan_run.is_dir():
        print(f"Error: wallet-scan run root not found or not a directory: {wallet_scan_run}", file=sys.stderr)
        return 1

    out_path = Path(args.out) if args.out else wallet_scan_run / "alpha_candidates.json"

    try:
        payload = distill(
            wallet_scan_run,
            min_sample=args.min_sample,
            conservative_fee_adj=args.fee_adj,
            run_id=args.run_id,
        )
    except FileNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Alpha distillation failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    _write_json(out_path, payload)

    n = payload["summary"]["candidates_generated"]
    print(f"Alpha distillation complete: {n} candidate(s) generated")
    print(f"Output: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
