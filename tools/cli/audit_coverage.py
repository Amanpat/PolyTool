#!/usr/bin/env python3
"""Offline accuracy + trust sanity check: audit-coverage CLI.

Reads existing scan run artifacts from disk (no ClickHouse, no RAG, no network).
Produces a markdown (and optionally JSON) report summarising coverage stats,
red flags, and a deterministic sample of positions.

Usage:
    python -m polytool audit-coverage --user "@example" --sample 25
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "packages"))

from polytool.reports.coverage import (
    DEFAULT_ENTRY_PRICE_TIERS,
    normalize_fee_fields as _coverage_normalize_fee_fields,
    _classify_entry_price_tier,
    _detect_league,
    _detect_sport,
    _detect_market_type,
)
from polytool.user_context import UserContext, resolve_user_context
from tools.cli.llm_bundle import _find_latest_scan_run, _as_posix

RESOLVED_OUTCOMES = frozenset({"WIN", "LOSS", "PROFIT_EXIT", "LOSS_EXIT"})
DEFAULT_SAMPLE = 25
DEFAULT_SEED = 1337


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _safe_str(value: Any, default: str = "Unknown") -> str:
    if value is None or str(value).strip() == "":
        return default
    return str(value).strip()


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


def _fmt_pct(rate: Optional[float], default: str = "N/A") -> str:
    if rate is None:
        return default
    return f"{rate * 100:.1f}%"


def _fmt_val(value: Any, default: str = "N/A") -> str:
    if value is None:
        return default
    return str(value)


def _truncate(text: str, max_len: int = 80) -> str:
    if len(text) <= max_len:
        return text
    return text[: max_len - 1] + "\u2026"


# ---------------------------------------------------------------------------
# Run discovery
# ---------------------------------------------------------------------------

def _find_run_by_id(user_ctx: UserContext, run_id: str) -> Optional[Path]:
    """Find a run directory whose run_manifest.json run_id matches."""
    base = user_ctx.artifacts_user_dir
    if not base.exists():
        return None
    for manifest_path in base.rglob("run_manifest.json"):
        try:
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if payload.get("run_id") == run_id:
            return manifest_path.parent
    return None


def _find_run_root(
    user_ctx: UserContext,
    run_id: Optional[str] = None,
) -> Tuple[Optional[Path], str]:
    """Return (run_root_path, warning_msg).

    warning_msg is non-empty when a fallback strategy was used.
    Returns (None, error_msg) when nothing is found.
    """
    if run_id:
        run_dir = _find_run_by_id(user_ctx, run_id)
        if run_dir is None:
            return (
                None,
                f"No run found with run_id='{run_id}' for user '{user_ctx.slug}'.",
            )
        return run_dir, ""

    run_dir = _find_latest_scan_run(user_ctx)
    if run_dir is None:
        return (
            None,
            (
                f"No scan run found for user '{user_ctx.slug}'. "
                "Run 'python -m polytool scan --user ...' first."
            ),
        )
    return run_dir, ""


# ---------------------------------------------------------------------------
# Artifact loading
# ---------------------------------------------------------------------------

def _load_json(path: Path) -> Optional[Dict[str, Any]]:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except (json.JSONDecodeError, OSError):
        return None


def _extract_positions(dossier: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract positions list from a dossier.json payload.

    Mirrors the extraction logic used by scan.py so that the same position
    records are consumed by the audit report.
    """
    candidates: List[Any] = []

    positions_section = dossier.get("positions")
    if isinstance(positions_section, dict):
        if isinstance(positions_section.get("positions"), list):
            candidates = positions_section["positions"]
        elif isinstance(positions_section.get("items"), list):
            candidates = positions_section["items"]
    elif isinstance(positions_section, list):
        candidates = positions_section

    if not candidates:
        for key in ("positions_lifecycle", "position_lifecycle", "position_lifecycles"):
            alt = dossier.get(key)
            if isinstance(alt, list):
                candidates = alt
                break
            if isinstance(alt, dict) and isinstance(alt.get("positions"), list):
                candidates = alt["positions"]
                break

    return [dict(item) for item in candidates if isinstance(item, dict)]


# ---------------------------------------------------------------------------
# Deterministic sampling
# ---------------------------------------------------------------------------

def _stable_sort_key(pos: Dict[str, Any]) -> tuple:
    token_id = str(pos.get("token_id") or pos.get("resolved_token_id") or "")
    condition_id = str(pos.get("condition_id") or "")
    created_at = str(pos.get("created_at") or "")
    return (token_id, condition_id, created_at)


def _is_resolved(pos: Dict[str, Any]) -> bool:
    outcome = str(pos.get("resolution_outcome") or "").strip().upper()
    return outcome in RESOLVED_OUTCOMES


def sample_positions(
    positions: List[Dict[str, Any]],
    n: int,
    seed: int,
) -> List[Dict[str, Any]]:
    """Return a deterministic sample of up to *n* positions.

    Resolved positions fill the pool first; remaining slots come from
    pending/unknown positions.  Within each group positions are sorted by
    a stable key (token_id, condition_id, created_at) before sampling so
    that the same seed always yields the same result regardless of the
    input order.
    """
    if n <= 0 or not positions:
        return []

    sorted_pos = sorted(positions, key=_stable_sort_key)
    resolved = [p for p in sorted_pos if _is_resolved(p)]
    unresolved = [p for p in sorted_pos if not _is_resolved(p)]
    pool = resolved + unresolved

    if len(pool) <= n:
        return pool

    rng = random.Random(seed)
    indices = sorted(rng.sample(range(len(pool)), n))
    return [pool[i] for i in indices]


# ---------------------------------------------------------------------------
# Position enrichment
# ---------------------------------------------------------------------------

def _enrich_position_for_audit(pos: Dict[str, Any]) -> Dict[str, Any]:
    """Return an enriched copy of a position with derived fields applied.

    Applies the same fee normalization and classification logic used by
    build_coverage_report(), so that audit sample rows are consistent with the
    Quick Stats computed from coverage_reconciliation_report.json.

    Derived fields (filled only when the position does not already carry them):
    - league, sport  (from market_slug prefix via _detect_league/_detect_sport)
    - market_type    (from question/slug heuristic)
    - entry_price_tier (from entry_price against default tiers)
    - fees_estimated, fees_source, realized_pnl_net_estimated_fees
      (from normalize_fee_fields — always recomputed for consistency)
    """
    enriched = dict(pos)

    league = str(enriched.get("league") or "").strip()
    if not league:
        league = _detect_league(enriched)
        enriched["league"] = league

    sport = str(enriched.get("sport") or "").strip()
    if not sport:
        enriched["sport"] = _detect_sport(league)

    market_type = str(enriched.get("market_type") or "").strip()
    if not market_type:
        enriched["market_type"] = _detect_market_type(enriched)

    entry_price_tier = str(enriched.get("entry_price_tier") or "").strip()
    if not entry_price_tier:
        ep = _safe_float(enriched.get("entry_price"))
        enriched["entry_price_tier"] = _classify_entry_price_tier(ep, DEFAULT_ENTRY_PRICE_TIERS)

    # Always recompute fee fields so audit samples agree with coverage stats.
    _coverage_normalize_fee_fields(enriched)

    return enriched


# ---------------------------------------------------------------------------
# Segment analysis helpers
# ---------------------------------------------------------------------------

def _unknown_rate_from_segment(buckets: Any) -> Optional[float]:
    """Compute the fraction of positions in the 'unknown' bucket."""
    if not isinstance(buckets, dict) or not buckets:
        return None
    total = sum(
        (_safe_int((b or {}).get("total_count")) or 0) for b in buckets.values()
    )
    if total == 0:
        return None
    unknown_count = _safe_int((buckets.get("unknown") or {}).get("total_count")) or 0
    return unknown_count / total


# ---------------------------------------------------------------------------
# Report rendering
# ---------------------------------------------------------------------------

def _render_position_block(pos: Dict[str, Any]) -> List[str]:
    market_slug = _safe_str(pos.get("market_slug"))
    question = _truncate(_safe_str(pos.get("question")))
    outcome_name = _safe_str(pos.get("outcome_name"))
    category = _safe_str(pos.get("category"))
    league = _safe_str(pos.get("league"))
    sport = _safe_str(pos.get("sport"))
    market_type = _safe_str(pos.get("market_type"))
    entry_price_tier = _safe_str(pos.get("entry_price_tier"))
    resolution_outcome = _safe_str(pos.get("resolution_outcome"))

    entry_price = _fmt_val(pos.get("entry_price"))
    size_val = pos.get("size") if pos.get("size") is not None else pos.get("notional")
    size = _fmt_val(size_val)

    gross_pnl = _fmt_val(pos.get("gross_pnl"))
    fees_est = _fmt_val(pos.get("fees_estimated"))
    net_fees = _fmt_val(pos.get("realized_pnl_net_estimated_fees"))

    return [
        f"- **market_slug**: `{market_slug}`",
        f"  **question**: {question}",
        f"  **outcome_name**: {outcome_name}",
        f"  **category**: {category} | **league**: {league} | **sport**: {sport}",
        f"  **market_type**: {market_type} | **entry_price_tier**: {entry_price_tier}",
        f"  **entry_price**: {entry_price} | **size/notional**: {size}",
        f"  **resolution_outcome**: {resolution_outcome}",
        f"  **gross_pnl**: {gross_pnl} | **fees_estimated**: {fees_est} | **net_estimated_fees**: {net_fees}",
    ]


def _build_quick_stats(
    coverage_report: Optional[Dict[str, Any]],
    segment_data: Optional[Dict[str, Any]],
    raw_positions: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Extract all quick-stats fields from loaded artifacts."""
    stats: Dict[str, Any] = {}

    if coverage_report is None:
        return stats

    totals = coverage_report.get("totals") or {}
    outcome_counts = coverage_report.get("outcome_counts") or {}

    positions_total = _safe_int(totals.get("positions_total")) or 0
    resolved_count = sum(
        _safe_int(outcome_counts.get(k)) or 0
        for k in ("WIN", "LOSS", "PROFIT_EXIT", "LOSS_EXIT")
    )
    pending_count = _safe_int(outcome_counts.get("PENDING")) or 0

    cat_cov = coverage_report.get("category_coverage") or {}
    cat_rate = _safe_float(cat_cov.get("coverage_rate"))
    cat_missing = _safe_int(cat_cov.get("missing_count"))

    mm_cov = coverage_report.get("market_metadata_coverage") or {}
    mm_rate = _safe_float(mm_cov.get("coverage_rate"))
    mm_conflicts = (
        _safe_int(mm_cov.get("metadata_conflicts_count"))
        or _safe_int(mm_cov.get("conflicts_count"))
        or 0
    )

    fees = coverage_report.get("fees") or {}
    fees_estimated_count = _safe_int(fees.get("fees_estimated_present_count"))
    fee_source_counts = fees.get("fees_source_counts") or {}

    stats["positions_total"] = positions_total
    stats["resolved_count"] = resolved_count
    stats["pending_count"] = pending_count
    stats["category_coverage_rate"] = cat_rate
    stats["category_missing_count"] = cat_missing
    stats["market_metadata_coverage_rate"] = mm_rate
    stats["market_metadata_conflicts_count"] = mm_conflicts
    stats["fees_estimated_present_count"] = fees_estimated_count
    stats["fee_source_counts"] = fee_source_counts
    stats["positive_pnl_with_zero_fee_count"] = _count_positive_pnl_with_zero_fee(
        raw_positions or []
    )

    if isinstance(segment_data, dict):
        seg = segment_data.get("segment_analysis") or {}
        stats["unknown_league_rate"] = _unknown_rate_from_segment(seg.get("by_league"))
        stats["unknown_sport_rate"] = _unknown_rate_from_segment(seg.get("by_sport"))
        stats["unknown_market_type_rate"] = _unknown_rate_from_segment(
            seg.get("by_market_type")
        )

    return stats


def _count_positive_pnl_with_zero_fee(positions: List[Dict[str, Any]]) -> int:
    count = 0
    for pos in positions:
        gross_pnl = _safe_float(pos.get("gross_pnl"))
        if gross_pnl is None:
            gross_pnl = _safe_float(pos.get("realized_pnl_net"))
        gross_pnl = gross_pnl if gross_pnl is not None else 0.0

        fees_estimated = _safe_float(pos.get("fees_estimated"))
        fees_estimated = fees_estimated if fees_estimated is not None else 0.0

        if gross_pnl > 0 and abs(fees_estimated) < 1e-12:
            count += 1
    return count


def _build_red_flags(stats: Dict[str, Any]) -> List[str]:
    """Derive deterministic red-flag strings from quick stats."""
    flags: List[str] = []

    positions_total = stats.get("positions_total") or 0
    cat_rate = stats.get("category_coverage_rate")
    cat_missing = stats.get("category_missing_count") or 0

    if cat_rate is not None:
        cat_missing_rate = 1.0 - cat_rate
    elif positions_total > 0:
        cat_missing_rate = cat_missing / positions_total
    else:
        cat_missing_rate = 0.0

    if cat_missing_rate > 0.20:
        flags.append(
            f"category_missing_rate={_fmt_pct(cat_missing_rate)} exceeds 20% threshold"
        )

    mm_conflicts = stats.get("market_metadata_conflicts_count") or 0
    if mm_conflicts > 0:
        flags.append(
            f"market_metadata_conflicts_count={mm_conflicts} (expected 0)"
        )

    positive_pnl_with_zero_fee_count = stats.get("positive_pnl_with_zero_fee_count") or 0
    if positive_pnl_with_zero_fee_count > 0:
        flags.append(
            "positive_pnl_with_zero_fee_count="
            f"{positive_pnl_with_zero_fee_count} "
            "(gross_pnl>0 with fees_estimated=0)"
        )

    resolved_count = stats.get("resolved_count") or 0
    pending_count = stats.get("pending_count") or 0

    if positions_total > 0 and pending_count == positions_total:
        flags.append(
            "all positions are PENDING — resolution enrichment may not have applied"
        )
    elif positions_total > 0 and resolved_count == 0:
        flags.append(
            "resolved_count=0 — no resolved positions found; check resolution enrichment"
        )

    for label in ("league", "sport", "market_type"):
        rate = stats.get(f"unknown_{label}_rate")
        if rate is not None and rate > 0.20:
            flags.append(
                f"unknown_{label}_rate={_fmt_pct(rate)} exceeds 20% threshold"
            )

    return flags


def render_report_md(
    *,
    user_input: str,
    user_slug: str,
    wallet: str,
    run_id: str,
    generated_at: str,
    run_root: Path,
    coverage_report: Optional[Dict[str, Any]],
    segment_data: Optional[Dict[str, Any]],
    raw_positions: Optional[List[Dict[str, Any]]],
    positions: List[Dict[str, Any]],
    n: int,
    seed: int,
    all_mode: bool = False,
) -> str:
    """Render the audit coverage report as a markdown string."""
    lines: List[str] = []

    lines.append("# Audit Coverage Report")
    lines.append("")
    lines.append(f"[file_path: {_as_posix(run_root)}]")
    lines.append("")
    lines.append(f"**User:** {user_input}  ")
    lines.append(f"**Slug:** {user_slug}  ")
    lines.append(f"**Wallet:** {wallet or 'N/A'}  ")
    lines.append(f"**Run ID:** {run_id}  ")
    lines.append(f"**Generated at:** {generated_at}  ")
    lines.append("")

    # --- Quick Stats ---
    lines.append("## Quick Stats")
    lines.append("")

    if coverage_report is None:
        lines.append("_Coverage reconciliation report not found in run directory._")
        lines.append("")
    else:
        stats = _build_quick_stats(
            coverage_report,
            segment_data,
            raw_positions=raw_positions,
        )
        positions_total = stats.get("positions_total", 0)

        lines.append(f"- **positions_total**: {positions_total}")
        lines.append(f"- **resolved_count**: {stats.get('resolved_count', 0)}")
        lines.append(f"- **pending_count**: {stats.get('pending_count', 0)}")
        lines.append("")

        lines.append("**Category Coverage**")
        lines.append(
            f"- coverage_rate: {_fmt_pct(stats.get('category_coverage_rate'))}"
        )
        lines.append(
            f"- missing_count: {_fmt_val(stats.get('category_missing_count'))}"
        )
        lines.append("")

        lines.append("**Market Metadata Coverage**")
        lines.append(
            f"- coverage_rate: {_fmt_pct(stats.get('market_metadata_coverage_rate'))}"
        )
        lines.append(
            f"- metadata_conflicts_count: {stats.get('market_metadata_conflicts_count', 0)}"
        )
        lines.append("")

        ul = stats.get("unknown_league_rate")
        us = stats.get("unknown_sport_rate")
        um = stats.get("unknown_market_type_rate")
        if any(v is not None for v in (ul, us, um)):
            lines.append("**Segment Unknown Rates**")
            lines.append(f"- unknown_league_rate: {_fmt_pct(ul)}")
            lines.append(f"- unknown_sport_rate: {_fmt_pct(us)}")
            lines.append(f"- unknown_market_type_rate: {_fmt_pct(um)}")
            lines.append("")

        lines.append("**Fee Stats**")
        lines.append(
            f"- fees_estimated_present_count: {_fmt_val(stats.get('fees_estimated_present_count'))}"
        )
        lines.append(
            "- positive_pnl_with_zero_fee_count: "
            f"{_fmt_val(stats.get('positive_pnl_with_zero_fee_count'))}"
        )
        fee_src = stats.get("fee_source_counts")
        if fee_src:
            lines.append(
                f"- fees_source_counts: {json.dumps(fee_src, separators=(',', ':'))}"
            )
        lines.append(
            "- note: fees_estimated is only applied when gross_pnl > 0 "
            "(losses, zero, and pending positions intentionally show fees_estimated=0)."
        )
        lines.append("")

    # --- Red Flags ---
    lines.append("## Red Flags")
    lines.append("")

    if coverage_report is None:
        lines.append(
            "- Cannot evaluate: coverage_reconciliation_report.json not found."
        )
    else:
        stats = _build_quick_stats(
            coverage_report,
            segment_data,
            raw_positions=raw_positions,
        )
        flags = _build_red_flags(stats)
        if flags:
            for flag in flags:
                lines.append(f"- \u26a0 {flag}")
        else:
            lines.append("- No red flags detected.")
    lines.append("")

    # --- Samples / All Positions ---
    sampled = sample_positions(positions, n, seed)
    actual_n = len(sampled)

    if all_mode:
        lines.append(f"## All Positions ({actual_n})")
    else:
        lines.append(f"## Samples ({actual_n})")
    lines.append("")

    if not sampled:
        lines.append("_No positions available._")
    else:
        if all_mode:
            lines.append(
                f"_All {actual_n} position(s) (stable sort by token_id / condition_id / created_at; resolved-first)._"
            )
        else:
            lines.append(
                f"_Deterministic sample of {actual_n} position(s) "
                f"(seed={seed}; resolved-first)._"
            )
        lines.append("")
        for i, pos in enumerate(sampled, 1):
            lines.append(f"### Position {i}")
            lines.append("")
            lines.extend(_render_position_block(pos))
            lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def render_report_json(
    *,
    user_input: str,
    user_slug: str,
    wallet: str,
    run_id: str,
    generated_at: str,
    run_root: Path,
    coverage_report: Optional[Dict[str, Any]],
    segment_data: Optional[Dict[str, Any]],
    raw_positions: Optional[List[Dict[str, Any]]],
    positions: List[Dict[str, Any]],
    n: int,
    seed: int,
    all_mode: bool = False,
) -> str:
    """Render the audit coverage report as a JSON string."""
    stats = _build_quick_stats(
        coverage_report,
        segment_data,
        raw_positions=raw_positions,
    )
    flags = _build_red_flags(stats) if coverage_report is not None else []
    sampled = sample_positions(positions, n, seed)

    payload: Dict[str, Any] = {
        "report_type": "audit_coverage",
        "user_input": user_input,
        "user_slug": user_slug,
        "wallet": wallet or "",
        "run_id": run_id,
        "generated_at": generated_at,
        "run_root": _as_posix(run_root),
        "quick_stats": stats,
        "red_flags": flags,
        "samples": {
            "n_requested": None if all_mode else n,
            "all_mode": all_mode,
            "n_returned": len(sampled),
            "seed": seed,
            "positions": sampled,
        },
    }
    return json.dumps(payload, indent=2, sort_keys=True, default=str)


def write_audit_coverage_report(
    *,
    run_root: Path,
    user_input: str,
    user_slug: str,
    wallet: str,
    run_id: str,
    sample: Optional[int] = None,
    seed: int = DEFAULT_SEED,
    fmt: str = "md",
    output_path: Optional[Path] = None,
) -> Path:
    """Generate and write an audit coverage report for a known run root.

    When *sample* is ``None`` (the default), all positions are included in the
    report (ordered by stable sort key).  Pass an explicit integer to limit to
    that many positions (deterministic sampling with *seed*).
    """
    if fmt not in {"md", "json"}:
        raise ValueError(f"Unsupported format: {fmt}")

    coverage_report = _load_json(run_root / "coverage_reconciliation_report.json")
    segment_data = _load_json(run_root / "segment_analysis.json")
    dossier = _load_json(run_root / "dossier.json")

    raw_positions: List[Dict[str, Any]] = []
    if dossier is not None:
        raw_positions = _extract_positions(dossier)
    positions = [_enrich_position_for_audit(p) for p in raw_positions]

    all_mode = sample is None
    n = len(positions) if all_mode else max(0, int(sample))
    seed_value = int(seed)
    generated_at = _utcnow_iso()

    ext = "json" if fmt == "json" else "md"
    out_path = output_path if output_path is not None else run_root / f"audit_coverage_report.{ext}"

    common_kwargs = dict(
        user_input=user_input,
        user_slug=user_slug,
        wallet=wallet,
        run_id=run_id,
        generated_at=generated_at,
        run_root=run_root,
        coverage_report=coverage_report,
        segment_data=segment_data,
        raw_positions=raw_positions,
        positions=positions,
        n=n,
        seed=seed_value,
        all_mode=all_mode,
    )

    if fmt == "json":
        report_text = render_report_json(**common_kwargs)
    else:
        report_text = render_report_md(**common_kwargs)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(report_text, encoding="utf-8")
    return out_path


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Offline audit of scan run coverage artifacts. "
            "No ClickHouse, RAG, or network calls required."
        )
    )
    parser.add_argument(
        "--user",
        required=True,
        help="Target user handle (with or without @).",
    )
    parser.add_argument(
        "--sample",
        type=int,
        default=None,
        metavar="N",
        help=(
            "Number of positions to include in the report. "
            "Omit to include ALL positions (default). "
            "When provided, a deterministic sample of min(N, total) is used."
        ),
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=DEFAULT_SEED,
        help=f"Random seed for deterministic sampling (default: {DEFAULT_SEED}).",
    )
    parser.add_argument(
        "--run-id",
        dest="run_id",
        help="Specific run_id to audit (default: latest scan run).",
    )
    parser.add_argument(
        "--output",
        help="Output file path override (default: <run_root>/audit_coverage_report.md).",
    )
    parser.add_argument(
        "--format",
        choices=["md", "json"],
        default="md",
        help="Output format: md (default) or json.",
    )
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    user_raw = args.user.strip() if args.user else ""
    if not user_raw or user_raw == "@":
        print("Error: --user must be a non-empty handle.", file=sys.stderr)
        return 1

    original_handle = (
        user_raw if user_raw.startswith("@") else f"@{user_raw}"
    )
    user_ctx = resolve_user_context(
        handle=original_handle,
        wallet=None,
        kb_root=Path("kb"),
        artifacts_root=Path("artifacts"),
        persist_mapping=False,
    )

    run_root, err_msg = _find_run_root(user_ctx, run_id=args.run_id)
    if run_root is None:
        print(f"Error: {err_msg}", file=sys.stderr)
        return 1

    # Load manifest for provenance fallbacks.
    run_manifest = _load_json(run_root / "run_manifest.json")

    # Derive identifiers from manifest (fall back to what we know)
    if run_manifest:
        run_id = run_manifest.get("run_id") or str(run_root.name)
        wallet = (run_manifest.get("wallets") or [None])[0] or ""
        slug_from_manifest = run_manifest.get("user_slug") or user_ctx.slug
    else:
        run_id = str(run_root.name)
        wallet = ""
        slug_from_manifest = user_ctx.slug

    out_path = write_audit_coverage_report(
        run_root=run_root,
        user_input=original_handle,
        user_slug=slug_from_manifest,
        wallet=wallet,
        run_id=run_id,
        sample=args.sample,  # None => all positions; int => deterministic sample
        seed=args.seed,
        fmt=args.format,
        output_path=Path(args.output) if args.output else None,
    )

    print(f"Audit coverage report written to: {out_path.as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
