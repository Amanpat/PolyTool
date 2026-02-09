"""Coverage & Reconciliation Report builder.

Generates a JSON (and optionally Markdown) report summarising position
outcome coverage, trade-UID integrity, PnL totals, fee sourcing, and
resolution coverage for a single examination run.
"""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


REPORT_VERSION = "1.0.0"

KNOWN_OUTCOMES = frozenset({
    "WIN", "LOSS", "PROFIT_EXIT", "LOSS_EXIT", "PENDING", "UNKNOWN_RESOLUTION",
})


def _safe_pct(numerator: int, denominator: int) -> float:
    if denominator == 0:
        return 0.0
    return round(numerator / denominator, 6)


def _now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


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
        pnl = pos.get("realized_pnl_net")
        outcome = pos.get("resolution_outcome", "UNKNOWN_RESOLUTION")
        if pnl is None:
            missing_pnl += 1
            continue
        realized_total += float(pnl)
        by_outcome[outcome] = by_outcome.get(outcome, 0.0) + float(pnl)

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
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")

    paths: Dict[str, str] = {"json": str(json_path)}

    if write_markdown:
        md_path = output_dir / "coverage_reconciliation_report.md"
        md_path.write_text(_render_markdown(report), encoding="utf-8")
        paths["md"] = str(md_path)

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

    if report["warnings"]:
        lines.append("## Warnings")
        for w in report["warnings"]:
            lines.append(f"- {w}")
        lines.append("")

    return "\n".join(lines)
