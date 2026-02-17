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


REPORT_VERSION = "1.1.0"
PENDING_COVERAGE_INVALID_WARNING = (
    "All positions are PENDING despite strong identifier coverage. "
    "This often indicates resolution enrichment did not apply to the relevant tokens "
    "(candidate cap/truncation or join mismatch). "
    "Re-run with --resolution-max-candidates 300+ and verify enrichment truncation metrics."
)

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
MONEYLINE_WILL_WIN_PATTERN = re.compile(r"will .* win", re.IGNORECASE)


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
    if MONEYLINE_WILL_WIN_PATTERN.search(question):
        return "moneyline"
    return "unknown"


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
        "total_pnl_net": 0.0,
    }


def _accumulate_segment_bucket(bucket: Dict[str, Any], outcome: str, pnl_net: float) -> None:
    bucket["count"] += 1
    if outcome == "WIN":
        bucket["wins"] += 1
    elif outcome == "LOSS":
        bucket["losses"] += 1
    elif outcome == "PROFIT_EXIT":
        bucket["profit_exits"] += 1
    elif outcome == "LOSS_EXIT":
        bucket["loss_exits"] += 1
    bucket["total_pnl_net"] += pnl_net


def _finalize_segment_bucket(bucket: Dict[str, Any]) -> Dict[str, Any]:
    wins = int(bucket.get("wins") or 0)
    losses = int(bucket.get("losses") or 0)
    profit_exits = int(bucket.get("profit_exits") or 0)
    loss_exits = int(bucket.get("loss_exits") or 0)
    denominator = wins + losses + profit_exits + loss_exits
    numerator = wins + profit_exits
    return {
        "count": int(bucket.get("count") or 0),
        "wins": wins,
        "losses": losses,
        "profit_exits": profit_exits,
        "loss_exits": loss_exits,
        "win_rate": _safe_pct(numerator, denominator),
        "total_pnl_net": round(float(bucket.get("total_pnl_net") or 0.0), 6),
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
        "unknown": _empty_segment_bucket(),
    }

    by_league_raw: Dict[str, Dict[str, Any]] = {"unknown": _empty_segment_bucket()}
    by_sport_raw: Dict[str, Dict[str, Any]] = {"unknown": _empty_segment_bucket()}

    for position in positions:
        outcome = _normalize_outcome(position.get("resolution_outcome"))
        pnl_net = _safe_float(position.get("realized_pnl_net"))
        pnl_net_value = pnl_net if pnl_net is not None else 0.0

        league = _detect_league(position)
        sport = _detect_sport(league)
        market_type = _detect_market_type(position)
        entry_price = _safe_float(position.get("entry_price"))
        entry_price_tier = _classify_entry_price_tier(entry_price, tiers)

        by_league_raw.setdefault(league, _empty_segment_bucket())
        by_sport_raw.setdefault(sport, _empty_segment_bucket())
        by_market_type_raw.setdefault(market_type, _empty_segment_bucket())
        by_entry_price_tier_raw.setdefault(entry_price_tier, _empty_segment_bucket())

        _accumulate_segment_bucket(by_entry_price_tier_raw[entry_price_tier], outcome, pnl_net_value)
        _accumulate_segment_bucket(by_market_type_raw[market_type], outcome, pnl_net_value)
        _accumulate_segment_bucket(by_league_raw[league], outcome, pnl_net_value)
        _accumulate_segment_bucket(by_sport_raw[sport], outcome, pnl_net_value)

    by_entry_price_tier = {
        name: _finalize_segment_bucket(by_entry_price_tier_raw[name])
        for name in tier_names + ["unknown"]
    }
    by_market_type = {
        name: _finalize_segment_bucket(by_market_type_raw[name])
        for name in ("moneyline", "spread", "unknown")
    }

    league_keys = sorted(k for k in by_league_raw.keys() if k != "unknown")
    league_keys.append("unknown")
    by_league = {name: _finalize_segment_bucket(by_league_raw[name]) for name in league_keys}

    sport_keys = sorted(k for k in by_sport_raw.keys() if k != "unknown")
    sport_keys.append("unknown")
    by_sport = {name: _finalize_segment_bucket(by_sport_raw[name]) for name in sport_keys}

    return {
        "entry_price_tiers": tiers,
        "by_entry_price_tier": by_entry_price_tier,
        "by_market_type": by_market_type,
        "by_league": by_league,
        "by_sport": by_sport,
    }


def _collect_segment_rankings(segment_analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
    ranked: List[Dict[str, Any]] = []
    dimensions = (
        ("entry_price_tier", "by_entry_price_tier"),
        ("market_type", "by_market_type"),
        ("league", "by_league"),
        ("sport", "by_sport"),
    )
    for dimension_label, field in dimensions:
        buckets = segment_analysis.get(field)
        if not isinstance(buckets, dict):
            continue
        for bucket_name, metrics in buckets.items():
            if not isinstance(metrics, dict):
                continue
            total_pnl_net = _safe_float(metrics.get("total_pnl_net"))
            if total_pnl_net is None:
                continue
            ranked.append({
                "segment": f"{dimension_label}:{bucket_name}",
                "count": _coerce_int(metrics.get("count")),
                "total_pnl_net": round(total_pnl_net, 6),
            })

    ranked.sort(key=lambda row: (-row["total_pnl_net"], row["segment"]))
    return ranked


def normalize_fee_fields(position: Dict[str, Any]) -> Dict[str, Any]:
    """Ensure every position has explicit fee sourcing.

    Rules:
      - If ``fees_actual`` is present and > 0  -> fees_source = "actual"
      - Elif ``fees_estimated`` is present and > 0 -> fees_source = "estimated"
      - Else -> fees_source = "unknown"

    Returns the position dict (mutated in place for convenience).
    """
    fees_actual = float(position.get("fees_actual") or 0)
    fees_estimated = float(position.get("fees_estimated") or 0)

    if fees_actual > 0:
        position["fees_source"] = "actual"
    elif fees_estimated > 0:
        position["fees_source"] = "estimated"
    else:
        position.setdefault("fees_source", "unknown")

    # Ensure fields always exist
    position.setdefault("fees_actual", 0.0)
    position.setdefault("fees_estimated", 0.0)
    return position


def build_coverage_report(
    positions: List[Dict[str, Any]],
    run_id: str,
    user_slug: str,
    wallet: str,
    proxy_wallet: Optional[str] = None,
    resolution_enrichment_response: Optional[Dict[str, Any]] = None,
    entry_price_tiers: Optional[List[Dict[str, Any]]] = None,
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
    # --- Normalize fees on every position first ---
    for pos in positions:
        normalize_fee_fields(pos)

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
    realized_total = 0.0
    by_outcome: Dict[str, float] = {}
    missing_pnl = 0

    for pos in positions:
        outcome = pos.get("resolution_outcome", "UNKNOWN_RESOLUTION")
        if outcome == "PENDING":
            pos["settlement_price"] = None
            if not pos.get("resolved_at"):
                pos["resolved_at"] = None
            if _coerce_int(pos.get("sell_count")) == 0:
                pos["gross_pnl"] = 0.0
                pos["realized_pnl_net"] = 0.0

        pnl = _safe_float(pos.get("realized_pnl_net"))
        if pnl is None:
            missing_pnl += 1
            continue
        realized_total += pnl
        by_outcome[outcome] = by_outcome.get(outcome, 0.0) + pnl

    pnl_section = {
        "realized_pnl_net_total": round(realized_total, 6),
        "realized_pnl_net_by_outcome": {k: round(v, 6) for k, v in sorted(by_outcome.items())},
        "missing_realized_pnl_count": missing_pnl,
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

    fees_section = {
        "fees_source_counts": dict(fee_source_counter),
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
    if missing_pnl > 0:
        warnings.append(f"{missing_pnl} positions missing realized_pnl_net")
    if fee_source_counter.get("unknown", 0) == total and total > 0:
        warnings.append("All positions have fees_source=unknown; no actual or estimated fees")

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
        "segment_analysis": segment_analysis,
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
    lines.append(f"- Realized PnL (net, total): {pnl['realized_pnl_net_total']:.6f}")
    lines.append(f"- Missing PnL: {pnl['missing_realized_pnl_count']}")
    lines.append("")

    lines.append("## Fee Sourcing")
    fees = report["fees"]
    for src, cnt in sorted(fees["fees_source_counts"].items()):
        lines.append(f"- {src}: {cnt}")
    lines.append("")

    lines.append("## Resolution Coverage")
    res = report["resolution_coverage"]
    lines.append(f"- Resolved: {res['resolved_total']}")
    lines.append(f"- Unknown resolution: {res['unknown_resolution_total']} ({res['unknown_resolution_rate']:.2%})")
    lines.append(f"- Held to resolution: {res['held_to_resolution_total']}")
    lines.append(f"- WIN+LOSS covered rate: {res['win_loss_covered_rate']:.2%}")
    lines.append("")

    lines.extend(_render_segment_highlights(report))

    if report["warnings"]:
        lines.append("## Warnings")
        for w in report["warnings"]:
            lines.append(f"- {w}")
        lines.append("")

    return "\n".join(lines)


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

    lines.append("### Top 3 Segments by total_pnl_net")
    if top_segments:
        for row in top_segments:
            lines.append(
                f"- {row['segment']}: pnl={row['total_pnl_net']:.6f}, count={row['count']}"
            )
    else:
        lines.append("- None")
    lines.append("")

    lines.append("### Bottom 3 Segments by total_pnl_net")
    if bottom_segments:
        for row in bottom_segments:
            lines.append(
                f"- {row['segment']}: pnl={row['total_pnl_net']:.6f}, count={row['count']}"
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
