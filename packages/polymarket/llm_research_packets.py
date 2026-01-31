# This change adds a new export that captures a user's activity snapshot and a ready-to-fill research memo
# so analysts can review it later and compare how behavior changes over time without rerunning data pulls.

from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

DEFAULT_WINDOW_DAYS = 30
DEFAULT_MAX_TRADES = 200
DEFAULT_TREND_POINTS = 7

NOTIONAL_BUCKETS = [
    {"label": "0-25", "min": 0, "max": 25},
    {"label": "25-100", "min": 25, "max": 100},
    {"label": "100-500", "min": 100, "max": 500},
    {"label": "500-1000", "min": 500, "max": 1000},
    {"label": "1000-5000", "min": 1000, "max": 5000},
    {"label": "5000+", "min": 5000, "max": None},
]


@dataclass
class UserDossierExport:
    export_id: str
    proxy_wallet: str
    username: Optional[str]
    username_slug: str
    generated_at: datetime
    window_start: datetime
    window_end: datetime
    dossier: Dict[str, Any]
    memo_md: str
    dossier_json: str
    detectors_json: str
    anchor_trade_uids: List[str]
    stats: Dict[str, Any]
    artifact_path: str
    path_json: str
    path_md: str
    manifest_path: str


_USERNAME_SLUG_RE = re.compile(r"[^a-z0-9_-]")


def _username_to_slug(username: Optional[str]) -> str:
    if username is None:
        return "unknown"
    cleaned = username.strip()
    if not cleaned or cleaned == "@":
        return "unknown"
    if cleaned.startswith("@"):
        cleaned = cleaned[1:]
    cleaned = cleaned.strip().lower()
    if not cleaned:
        return "unknown"
    cleaned = _USERNAME_SLUG_RE.sub("_", cleaned)
    return cleaned or "unknown"


def build_dossier_dir(
    proxy_wallet: str,
    username: Optional[str],
    date_utc: datetime,
    run_id: str,
) -> Path:
    date_label = date_utc.strftime("%Y-%m-%d")
    username_slug = _username_to_slug(username)
    return (
        Path("artifacts")
        / "dossiers"
        / "users"
        / username_slug
        / proxy_wallet
        / date_label
        / run_id
    )


def _apply_artifacts_base_path(artifacts_base_path: str, dossier_dir: Path) -> Path:
    base_path = artifacts_base_path or "artifacts"
    if base_path == "artifacts":
        return dossier_dir
    parts = dossier_dir.parts
    if parts and parts[0] == "artifacts":
        return Path(base_path).joinpath(*parts[1:])
    return Path(base_path) / dossier_dir


def _safe_divide(numerator: float, denominator: float, digits: int = 6) -> float:
    if denominator == 0:
        return 0.0
    return round(numerator / denominator, digits)


def _round_value(value: Optional[float], digits: int = 6) -> Optional[float]:
    if value is None:
        return None
    return round(float(value), digits)


def _isoformat(dt: Optional[datetime]) -> str:
    if dt is None:
        return ""
    if isinstance(dt, datetime):
        return dt.replace(microsecond=0).isoformat() + "Z"
    if isinstance(dt, date):
        return datetime(dt.year, dt.month, dt.day).isoformat() + "Z"
    return str(dt)


def _format_number(value: Optional[float], digits: int = 4) -> str:
    if value is None:
        return ""
    return f"{value:.{digits}f}"


def _fetch_single_row(client, query: str, parameters: dict) -> List[Any]:
    result = client.query(query, parameters=parameters)
    if not result.result_rows:
        return []
    return result.result_rows[0]


def _anchor_limits(max_trades: int) -> Dict[str, int]:
    max_trades = max(1, int(max_trades))
    base = max_trades // 3
    remainder = max_trades % 3
    last_limit = base + (1 if remainder > 0 else 0)
    top_limit = base + (1 if remainder > 1 else 0)
    outlier_limit = base
    return {
        "last_trades": last_limit,
        "top_notional": top_limit,
        "outliers": outlier_limit,
        "max_trades": max_trades,
    }


def _map_anchor_row(row: List[Any]) -> Dict[str, Any]:
    return {
        "trade_uid": row[0],
        "ts": _isoformat(row[1]) if row[1] else "",
        "token_id": row[2] or "",
        "resolved_token_id": row[3] or "",
        "market_slug": row[4] or "",
        "question": row[5] or "",
        "outcome_name": row[6] or "",
        "side": row[7] or "",
        "price": _round_value(row[8]),
        "size": _round_value(row[9]),
        "notional": _round_value(row[10]),
        "tx_hash": row[11] or "",
    }


def _fetch_anchor_rows(
    client,
    proxy_wallet: str,
    window_start: datetime,
    window_end: datetime,
    limit: int,
    order_by: str,
    min_notional: Optional[float] = None,
) -> List[Dict[str, Any]]:
    if limit <= 0:
        return []

    notional_filter = ""
    parameters = {
        "wallet": proxy_wallet,
        "start": window_start,
        "end": window_end,
        "limit": limit,
    }
    if min_notional is not None:
        notional_filter = "AND (size * price) >= {min_notional:Float64}"
        parameters["min_notional"] = float(min_notional)

    query = f"""
        SELECT
            trade_uid,
            ts,
            token_id,
            resolved_token_id,
            market_slug,
            question,
            resolved_outcome_name AS outcome_name,
            side,
            price,
            size,
            (size * price) AS notional,
            transaction_hash AS tx_hash
        FROM user_trades_resolved
        WHERE proxy_wallet = {{wallet:String}}
          AND ts >= {{start:DateTime}}
          AND ts <= {{end:DateTime}}
          {notional_filter}
        ORDER BY {order_by}
        LIMIT {{limit:Int32}}
    """

    result = client.query(query, parameters=parameters)
    return [_map_anchor_row(row) for row in result.result_rows]


def _dedupe_anchors(
    rows: List[Dict[str, Any]],
    seen: set,
    limit: int,
) -> List[Dict[str, Any]]:
    output: List[Dict[str, Any]] = []
    for row in rows:
        trade_uid = row.get("trade_uid")
        if not trade_uid or trade_uid in seen:
            continue
        seen.add(trade_uid)
        output.append(row)
        if len(output) >= limit:
            break
    return output


def _build_notional_histogram(row: List[Any], trades_count: int) -> List[Dict[str, Any]]:
    if not row:
        row = [0] * len(NOTIONAL_BUCKETS)
    histogram: List[Dict[str, Any]] = []
    for idx, bucket in enumerate(NOTIONAL_BUCKETS):
        count = int(row[idx]) if idx < len(row) and row[idx] is not None else 0
        histogram.append({
            "label": bucket["label"],
            "min": bucket["min"],
            "max": bucket["max"],
            "count": count,
            "pct": _safe_divide(count, trades_count, digits=4) if trades_count else 0.0,
        })
    return histogram


def _build_detectors_payload(latest_rows: List[List[Any]], trend_rows: List[List[Any]]) -> Dict[str, Any]:
    latest: List[Dict[str, Any]] = []
    for row in latest_rows:
        latest.append({
            "detector": row[0] or "",
            "score": _round_value(row[1]),
            "label": row[2] or "",
            "bucket_start": _isoformat(row[3]) if row[3] else "",
        })

    latest_sorted = sorted(
        latest,
        key=lambda item: ((item["score"] is None), -(item["score"] or 0.0), item["detector"]),
    )

    trend: Dict[str, List[Dict[str, Any]]] = {}
    for row in trend_rows:
        name = row[0] or ""
        trend.setdefault(name, []).append({
            "bucket_start": _isoformat(row[1]) if row[1] else "",
            "score": _round_value(row[2]),
            "label": row[3] or "",
        })

    for name, entries in trend.items():
        trend[name] = entries

    return {
        "bucket_type": "day",
        "latest": latest_sorted,
        "trend": trend,
    }


def _build_research_memo(
    dossier: Dict[str, Any],
    anchor_rows: List[Dict[str, Any]],
) -> str:
    header = dossier.get("header", {})
    coverage = dossier.get("coverage", {})
    liquidity = dossier.get("liquidity_summary", {})
    pnl = dossier.get("pnl_summary", {})

    lines: List[str] = []
    lines.append("# LLM Research Packet v1")
    lines.append("")
    lines.append(f"User input: {header.get('user_input', '')}")
    lines.append(f"Proxy wallet: {header.get('proxy_wallet', '')}")
    lines.append(
        "Window: {start} to {end} ({days} days)".format(
            start=header.get("window_start", ""),
            end=header.get("window_end", ""),
            days=header.get("window_days", 0),
        )
    )
    lines.append(f"Generated at: {header.get('generated_at', '')}")
    if header.get("export_id"):
        lines.append(f"Export id: {header.get('export_id')}")
    lines.append("")

    lines.append("## Executive Summary")
    lines.append("- TODO: Summarize the strategy in 2-3 sentences.")
    lines.append("")

    lines.append("## Data Coverage & Caveats")
    lines.append(
        "- Trades: {trades}, Activity: {activity}, Positions: {positions}".format(
            trades=coverage.get("trades_count", 0),
            activity=coverage.get("activity_count", 0),
            positions=coverage.get("positions_count", 0),
        )
    )
    lines.append(
        "- Mapping coverage: {coverage_pct}% of trades include market slug/question/category.".format(
            coverage_pct=_format_number(coverage.get("mapping_coverage", 0.0) * 100, digits=2)
        )
    )
    lines.append(
        "- Liquidity snapshots: {total} total, usable rate {rate}% (ok={ok}).".format(
            total=liquidity.get("total_snapshots", 0),
            rate=_format_number(liquidity.get("usable_liquidity_rate", 0.0) * 100, digits=2),
            ok=liquidity.get("usable_liquidity_count", 0),
        )
    )
    latest_bucket = pnl.get("latest_bucket") or {}
    if latest_bucket:
        lines.append(
            "- Latest PnL bucket ({bucket_start}): realized={realized}, mtm={mtm}, exposure={exposure}.".format(
                bucket_start=latest_bucket.get("bucket_start", ""),
                realized=_format_number(latest_bucket.get("realized_pnl")),
                mtm=_format_number(latest_bucket.get("mtm_pnl_estimate")),
                exposure=_format_number(latest_bucket.get("exposure_notional_estimate")),
            )
        )
    lines.append("- Hard rule: any strategy claim must cite dossier metrics or trade_uids.")
    lines.append("")

    lines.append("## Key Observations")
    lines.append("- TODO: Bullet observations backed by metrics/trade_uids.")
    lines.append("")

    lines.append("## Hypotheses")
    lines.append("| claim | evidence (metrics/trade_uids) | confidence | how to falsify | next feature needed |")
    lines.append("| --- | --- | --- | --- | --- |")
    lines.append("| TODO | TODO | TODO | TODO | TODO |")
    lines.append("")

    lines.append("## What changed recently")
    lines.append("- TODO: Compare to prior exports or recent buckets.")
    lines.append("")

    lines.append("## Next features to compute")
    lines.append("- TODO: Add derived metrics that would raise confidence.")
    lines.append("")

    lines.append("## Evidence anchors")
    anchor_uids = [row.get("trade_uid") for row in anchor_rows if row.get("trade_uid")]
    if anchor_uids:
        lines.append("Anchor trade_uids:")
        for trade_uid in anchor_uids:
            lines.append(f"- `{trade_uid}`")
    else:
        lines.append("Anchor trade_uids: none")
    lines.append("")

    lines.append("| trade_uid | ts | market_slug | outcome_name | side | price | size | notional | tx_hash |")
    lines.append("| --- | --- | --- | --- | --- | --- | --- | --- | --- |")
    if anchor_rows:
        for row in anchor_rows:
            lines.append(
                "| {trade_uid} | {ts} | {market_slug} | {outcome_name} | {side} | {price} |"
                " {size} | {notional} | {tx_hash} |".format(
                    trade_uid=row.get("trade_uid", ""),
                    ts=row.get("ts", ""),
                    market_slug=row.get("market_slug", ""),
                    outcome_name=row.get("outcome_name", ""),
                    side=row.get("side", ""),
                    price=_format_number(row.get("price")),
                    size=_format_number(row.get("size")),
                    notional=_format_number(row.get("notional")),
                    tx_hash=row.get("tx_hash", ""),
                )
            )
    else:
        lines.append("| | | | | | | | | |")

    lines.append("")
    return "\n".join(lines)


def export_user_dossier(
    clickhouse_client,
    proxy_wallet: str,
    user_input: str,
    username: Optional[str] = None,
    window_days: int = DEFAULT_WINDOW_DAYS,
    max_trades: int = DEFAULT_MAX_TRADES,
    artifacts_base_path: str = "artifacts",
    generated_at: Optional[datetime] = None,
    trend_points: int = DEFAULT_TREND_POINTS,
) -> UserDossierExport:
    generated_at = generated_at or datetime.utcnow()
    window_days = max(1, int(window_days))
    max_trades = max(1, int(max_trades))
    window_end = generated_at
    window_start = generated_at - timedelta(days=window_days)

    export_id = str(uuid.uuid4())
    username_slug = _username_to_slug(username)

    trade_summary_query = """
        SELECT
            count() AS trades_count,
            sumIf(1, lowerUTF8(side) = 'buy') AS buys_count,
            sumIf(1, lowerUTF8(side) = 'sell') AS sells_count,
            sumIf(1, market_slug != '' AND question != '' AND category != '') AS mapped_count,
            countDistinct(toDate(ts)) AS active_days
        FROM user_trades_resolved
        WHERE proxy_wallet = {wallet:String}
          AND ts >= {start:DateTime}
          AND ts <= {end:DateTime}
    """
    trade_summary_row = _fetch_single_row(
        clickhouse_client,
        trade_summary_query,
        parameters={
            "wallet": proxy_wallet,
            "start": window_start,
            "end": window_end,
        },
    )
    trades_count = int(trade_summary_row[0]) if trade_summary_row else 0
    buys_count = int(trade_summary_row[1]) if trade_summary_row else 0
    sells_count = int(trade_summary_row[2]) if trade_summary_row else 0
    mapped_count = int(trade_summary_row[3]) if trade_summary_row else 0
    active_days = int(trade_summary_row[4]) if trade_summary_row else 0
    mapping_coverage = _safe_divide(mapped_count, trades_count)

    activity_query = """
        SELECT count()
        FROM user_activity_resolved
        WHERE proxy_wallet = {wallet:String}
          AND ts >= {start:DateTime}
          AND ts <= {end:DateTime}
    """
    activity_row = _fetch_single_row(
        clickhouse_client,
        activity_query,
        parameters={
            "wallet": proxy_wallet,
            "start": window_start,
            "end": window_end,
        },
    )
    activity_count = int(activity_row[0]) if activity_row else 0

    positions_snapshot_query = """
        SELECT maxOrNull(snapshot_ts)
        FROM user_positions_resolved
        WHERE proxy_wallet = {wallet:String}
          AND snapshot_ts >= {start:DateTime}
          AND snapshot_ts <= {end:DateTime}
    """
    snapshot_row = _fetch_single_row(
        clickhouse_client,
        positions_snapshot_query,
        parameters={
            "wallet": proxy_wallet,
            "start": window_start,
            "end": window_end,
        },
    )
    latest_snapshot_ts = snapshot_row[0] if snapshot_row else None
    positions_count = 0
    if latest_snapshot_ts:
        positions_count_row = _fetch_single_row(
            clickhouse_client,
            """
            SELECT count()
            FROM user_positions_resolved
            WHERE proxy_wallet = {wallet:String}
              AND snapshot_ts = {snapshot:DateTime}
            """,
            parameters={
                "wallet": proxy_wallet,
                "snapshot": latest_snapshot_ts,
            },
        )
        positions_count = int(positions_count_row[0]) if positions_count_row else 0

    notional_hist_query = """
        SELECT
            sumIf(1, notional < 25) AS bucket_0_25,
            sumIf(1, notional >= 25 AND notional < 100) AS bucket_25_100,
            sumIf(1, notional >= 100 AND notional < 500) AS bucket_100_500,
            sumIf(1, notional >= 500 AND notional < 1000) AS bucket_500_1000,
            sumIf(1, notional >= 1000 AND notional < 5000) AS bucket_1000_5000,
            sumIf(1, notional >= 5000) AS bucket_5000_plus
        FROM (
            SELECT (size * price) AS notional
            FROM user_trades_resolved
            WHERE proxy_wallet = {wallet:String}
              AND ts >= {start:DateTime}
              AND ts <= {end:DateTime}
        )
    """
    notional_row = _fetch_single_row(
        clickhouse_client,
        notional_hist_query,
        parameters={
            "wallet": proxy_wallet,
            "start": window_start,
            "end": window_end,
        },
    )

    top_categories_query = """
        SELECT category, count() AS trades_count, sum(size * price) AS notional
        FROM user_trades_resolved
        WHERE proxy_wallet = {wallet:String}
          AND ts >= {start:DateTime}
          AND ts <= {end:DateTime}
          AND category != ''
        GROUP BY category
        ORDER BY trades_count DESC, notional DESC, category ASC
        LIMIT 5
    """
    categories_result = clickhouse_client.query(
        top_categories_query,
        parameters={
            "wallet": proxy_wallet,
            "start": window_start,
            "end": window_end,
        },
    )
    top_categories = [
        {
            "category": row[0],
            "trades_count": int(row[1]) if row[1] is not None else 0,
            "notional": _round_value(row[2]),
        }
        for row in categories_result.result_rows
    ]

    top_markets_query = """
        SELECT market_slug, count() AS trades_count, sum(size * price) AS notional
        FROM user_trades_resolved
        WHERE proxy_wallet = {wallet:String}
          AND ts >= {start:DateTime}
          AND ts <= {end:DateTime}
          AND market_slug != ''
        GROUP BY market_slug
        ORDER BY trades_count DESC, notional DESC, market_slug ASC
        LIMIT 5
    """
    markets_result = clickhouse_client.query(
        top_markets_query,
        parameters={
            "wallet": proxy_wallet,
            "start": window_start,
            "end": window_end,
        },
    )
    top_markets = [
        {
            "market_slug": row[0],
            "trades_count": int(row[1]) if row[1] is not None else 0,
            "notional": _round_value(row[2]),
        }
        for row in markets_result.result_rows
    ]

    hold_time_query = """
        SELECT
            quantileExactIf(0.5)(dateDiff('second', first_buy, first_sell), first_sell > first_buy) AS median_seconds,
            quantileExactIf(0.9)(dateDiff('second', first_buy, first_sell), first_sell > first_buy) AS p90_seconds,
            countIf(first_sell > first_buy) AS samples
        FROM (
            SELECT
                minIf(ts, lowerUTF8(side) = 'buy') AS first_buy,
                minIf(ts, lowerUTF8(side) = 'sell') AS first_sell
            FROM user_trades_resolved
            WHERE proxy_wallet = {wallet:String}
              AND ts >= {start:DateTime}
              AND ts <= {end:DateTime}
            GROUP BY resolved_token_id
        )
    """
    hold_time_row = _fetch_single_row(
        clickhouse_client,
        hold_time_query,
        parameters={
            "wallet": proxy_wallet,
            "start": window_start,
            "end": window_end,
        },
    )
    hold_samples = int(hold_time_row[2]) if hold_time_row else 0
    hold_time_summary = {
        "available": hold_samples > 0,
        "samples": hold_samples,
        "median_hours": _round_value((hold_time_row[0] or 0) / 3600, digits=4) if hold_samples else None,
        "p90_hours": _round_value((hold_time_row[1] or 0) / 3600, digits=4) if hold_samples else None,
    }

    pnl_latest_query = """
        SELECT
            bucket_start,
            realized_pnl,
            mtm_pnl_estimate,
            exposure_notional_estimate,
            pricing_snapshot_ratio,
            pricing_confidence
        FROM user_pnl_bucket
        WHERE proxy_wallet = {wallet:String}
          AND bucket_type = 'day'
        ORDER BY bucket_start DESC
        LIMIT 1
    """
    pnl_latest_row = _fetch_single_row(
        clickhouse_client,
        pnl_latest_query,
        parameters={"wallet": proxy_wallet},
    )

    latest_bucket = None
    pricing_snapshot_ratio = 0.0
    pricing_confidence = ""
    if pnl_latest_row:
        latest_bucket = {
            "bucket_start": _isoformat(pnl_latest_row[0]) if pnl_latest_row[0] else "",
            "realized_pnl": _round_value(pnl_latest_row[1]),
            "mtm_pnl_estimate": _round_value(pnl_latest_row[2]),
            "exposure_notional_estimate": _round_value(pnl_latest_row[3]),
        }
        if len(pnl_latest_row) > 4 and pnl_latest_row[4] is not None:
            pricing_snapshot_ratio = float(pnl_latest_row[4])
        if len(pnl_latest_row) > 5 and pnl_latest_row[5] is not None:
            pricing_confidence = str(pnl_latest_row[5])

    pnl_trend_start = window_end - timedelta(days=30)
    pnl_trend_query = """
        SELECT bucket_start, realized_pnl, mtm_pnl_estimate, exposure_notional_estimate
        FROM user_pnl_bucket
        WHERE proxy_wallet = {wallet:String}
          AND bucket_type = 'day'
          AND bucket_start >= {start:DateTime}
        ORDER BY bucket_start ASC
    """
    pnl_trend_result = clickhouse_client.query(
        pnl_trend_query,
        parameters={
            "wallet": proxy_wallet,
            "start": pnl_trend_start,
        },
    )
    pnl_trend_rows = pnl_trend_result.result_rows
    pnl_trend_summary = None
    if pnl_trend_rows:
        realized_total = sum(float(row[1] or 0) for row in pnl_trend_rows)
        mtm_total = sum(float(row[2] or 0) for row in pnl_trend_rows)
        exposure_values = [float(row[3] or 0) for row in pnl_trend_rows]
        exposure_avg = sum(exposure_values) / len(exposure_values) if exposure_values else 0.0
        pnl_trend_summary = {
            "bucket_count": len(pnl_trend_rows),
            "start": _isoformat(pnl_trend_rows[0][0]) if pnl_trend_rows[0][0] else "",
            "end": _isoformat(pnl_trend_rows[-1][0]) if pnl_trend_rows[-1][0] else "",
            "realized_total": _round_value(realized_total),
            "mtm_total": _round_value(mtm_total),
            "realized_avg": _round_value(realized_total / len(pnl_trend_rows)),
            "mtm_avg": _round_value(mtm_total / len(pnl_trend_rows)),
            "exposure_avg": _round_value(exposure_avg),
        }

    detectors_latest_query = """
        SELECT
            detector_name,
            argMax(score, bucket_start) AS score,
            argMax(label, bucket_start) AS label,
            max(bucket_start) AS latest_bucket_start
        FROM detector_results
        WHERE proxy_wallet = {wallet:String}
          AND bucket_type = 'day'
        GROUP BY detector_name
        ORDER BY detector_name ASC
    """
    detectors_latest_result = clickhouse_client.query(
        detectors_latest_query,
        parameters={"wallet": proxy_wallet},
    )

    detectors_trend_start = window_start
    detectors_trend_query = """
        SELECT detector_name, bucket_start, score, label
        FROM detector_results
        WHERE proxy_wallet = {wallet:String}
          AND bucket_type = 'day'
          AND bucket_start >= {start:DateTime}
        ORDER BY detector_name ASC, bucket_start ASC
    """
    detectors_trend_result = clickhouse_client.query(
        detectors_trend_query,
        parameters={
            "wallet": proxy_wallet,
            "start": detectors_trend_start,
        },
    )

    detectors_payload = _build_detectors_payload(
        detectors_latest_result.result_rows,
        detectors_trend_result.result_rows,
    )

    for name, entries in detectors_payload["trend"].items():
        if len(entries) > trend_points:
            detectors_payload["trend"][name] = entries[-trend_points:]

    liquidity_summary_query = """
        SELECT
            count() AS total_count,
            sumIf(1, status = 'ok') AS ok_count,
            sumIf(1, status = 'empty') AS empty_count,
            sumIf(1, status = 'one_sided') AS one_sided_count,
            sumIf(1, status = 'no_orderbook') AS no_orderbook_count,
            sumIf(1, status = 'error') AS error_count,
            sumIf(1, usable_liquidity = 1) AS usable_count,
            quantileExactIf(0.5)(execution_cost_bps_100, status = 'ok') AS median_exec_cost,
            quantileExactIf(0.9)(execution_cost_bps_100, status = 'ok') AS p90_exec_cost
        FROM orderbook_snapshots_enriched
        WHERE resolved_token_id IN (
            SELECT DISTINCT resolved_token_id
            FROM user_trades_resolved
            WHERE proxy_wallet = {wallet:String}
              AND ts >= {start:DateTime}
              AND ts <= {end:DateTime}
              AND resolved_token_id != ''
        )
          AND snapshot_ts >= {start:DateTime}
          AND snapshot_ts <= {end:DateTime}
    """
    liquidity_row = _fetch_single_row(
        clickhouse_client,
        liquidity_summary_query,
        parameters={
            "wallet": proxy_wallet,
            "start": window_start,
            "end": window_end,
        },
    )

    liquidity_total = int(liquidity_row[0]) if liquidity_row else 0
    liquidity_ok = int(liquidity_row[1]) if liquidity_row else 0
    liquidity_empty = int(liquidity_row[2]) if liquidity_row else 0
    liquidity_one_sided = int(liquidity_row[3]) if liquidity_row else 0
    liquidity_no_orderbook = int(liquidity_row[4]) if liquidity_row else 0
    liquidity_error = int(liquidity_row[5]) if liquidity_row else 0
    usable_liquidity_count = int(liquidity_row[6]) if liquidity_row else 0
    median_exec_cost = _round_value(liquidity_row[7]) if liquidity_row else None
    p90_exec_cost = _round_value(liquidity_row[8]) if liquidity_row else None

    liquidity_tokens_query = """
        SELECT
            resolved_token_id,
            any(market_slug) AS market_slug,
            any(question) AS question,
            any(outcome_name) AS outcome_name,
            quantileExact(0.5)(execution_cost_bps_100) AS median_exec_cost,
            quantileExact(0.9)(execution_cost_bps_100) AS p90_exec_cost,
            count() AS snapshots
        FROM orderbook_snapshots_enriched
        WHERE resolved_token_id IN (
            SELECT DISTINCT resolved_token_id
            FROM user_trades_resolved
            WHERE proxy_wallet = {wallet:String}
              AND ts >= {start:DateTime}
              AND ts <= {end:DateTime}
              AND resolved_token_id != ''
        )
          AND snapshot_ts >= {start:DateTime}
          AND snapshot_ts <= {end:DateTime}
          AND status = 'ok'
        GROUP BY resolved_token_id
    """

    top_tokens_query = liquidity_tokens_query + " ORDER BY median_exec_cost DESC, resolved_token_id ASC LIMIT {limit:Int32}"
    bottom_tokens_query = liquidity_tokens_query + " ORDER BY median_exec_cost ASC, resolved_token_id ASC LIMIT {limit:Int32}"

    top_tokens_result = clickhouse_client.query(
        top_tokens_query,
        parameters={
            "wallet": proxy_wallet,
            "start": window_start,
            "end": window_end,
            "limit": 5,
        },
    )
    bottom_tokens_result = clickhouse_client.query(
        bottom_tokens_query,
        parameters={
            "wallet": proxy_wallet,
            "start": window_start,
            "end": window_end,
            "limit": 5,
        },
    )

    def _map_liquidity_token(row: List[Any]) -> Dict[str, Any]:
        return {
            "resolved_token_id": row[0],
            "market_slug": row[1] or "",
            "question": row[2] or "",
            "outcome_name": row[3] or "",
            "median_exec_cost_bps_100": _round_value(row[4]),
            "p90_exec_cost_bps_100": _round_value(row[5]),
            "snapshots": int(row[6]) if row[6] is not None else 0,
        }

    top_tokens = [_map_liquidity_token(row) for row in top_tokens_result.result_rows]
    bottom_tokens = [_map_liquidity_token(row) for row in bottom_tokens_result.result_rows]

    outlier_threshold_query = """
        SELECT quantileExact(0.95)(size * price) AS p95
        FROM user_trades_resolved
        WHERE proxy_wallet = {wallet:String}
          AND ts >= {start:DateTime}
          AND ts <= {end:DateTime}
    """
    outlier_row = _fetch_single_row(
        clickhouse_client,
        outlier_threshold_query,
        parameters={
            "wallet": proxy_wallet,
            "start": window_start,
            "end": window_end,
        },
    )
    outlier_threshold = float(outlier_row[0]) if outlier_row and outlier_row[0] is not None else None

    limits = _anchor_limits(max_trades)
    seen: set = set()

    last_trades_raw = _fetch_anchor_rows(
        clickhouse_client,
        proxy_wallet,
        window_start,
        window_end,
        limit=max(limits["last_trades"], 1) * 2,
        order_by="ts DESC, trade_uid DESC",
    )
    last_trades = _dedupe_anchors(last_trades_raw, seen, limits["last_trades"])

    top_notional_raw = _fetch_anchor_rows(
        clickhouse_client,
        proxy_wallet,
        window_start,
        window_end,
        limit=max(limits["top_notional"], 1) * 2,
        order_by="notional DESC, ts DESC, trade_uid DESC",
    )
    top_notional = _dedupe_anchors(top_notional_raw, seen, limits["top_notional"])

    outliers: List[Dict[str, Any]] = []
    if outlier_threshold is not None and limits["outliers"] > 0:
        outliers_raw = _fetch_anchor_rows(
            clickhouse_client,
            proxy_wallet,
            window_start,
            window_end,
            limit=max(limits["outliers"], 1) * 2,
            order_by="notional DESC, ts DESC, trade_uid DESC",
            min_notional=outlier_threshold,
        )
        outliers = _dedupe_anchors(outliers_raw, seen, limits["outliers"])

    anchor_rows = last_trades + top_notional + outliers
    anchor_trade_uids = [row["trade_uid"] for row in anchor_rows if row.get("trade_uid")]

    distributions = {
        "buys_count": buys_count,
        "sells_count": sells_count,
        "buy_sell_ratio": _round_value(buys_count / sells_count, digits=4) if sells_count else None,
        "active_days": active_days,
        "trades_per_active_day": _round_value(_safe_divide(trades_count, active_days, digits=4), digits=4)
        if active_days
        else None,
        "trades_per_window_day": _round_value(_safe_divide(trades_count, window_days, digits=4), digits=4),
        "top_categories": top_categories,
        "top_markets": top_markets,
        "notional_histogram": _build_notional_histogram(notional_row, trades_count),
        "hold_time_approx": hold_time_summary,
    }

    liquidity_summary = {
        "total_snapshots": liquidity_total,
        "status_counts": {
            "ok": liquidity_ok,
            "empty": liquidity_empty,
            "one_sided": liquidity_one_sided,
            "no_orderbook": liquidity_no_orderbook,
            "error": liquidity_error,
        },
        "usable_liquidity_count": usable_liquidity_count,
        "usable_liquidity_rate": _safe_divide(usable_liquidity_count, liquidity_total),
        "execution_cost_bps_100": {
            "median": median_exec_cost,
            "p90": p90_exec_cost,
        },
        "top_tokens_by_exec_cost": top_tokens,
        "bottom_tokens_by_exec_cost": bottom_tokens,
    }

    coverage = {
        "trades_count": trades_count,
        "activity_count": activity_count,
        "positions_count": positions_count,
        "positions_snapshot_ts": _isoformat(latest_snapshot_ts) if latest_snapshot_ts else "",
        "mapping_coverage": mapping_coverage,
        "mapped_trades": mapped_count,
    }

    pnl_summary = {
        "latest_bucket": latest_bucket,
        "trend_30d": pnl_trend_summary,
        "pricing_snapshot_ratio": _round_value(pricing_snapshot_ratio, digits=4),
        "pricing_confidence": pricing_confidence,
    }

    anchors = {
        "limits": limits,
        "last_trades": last_trades,
        "top_notional": top_notional,
        "outliers": outliers,
        "total_anchors": len(anchor_rows),
        "anchor_trade_uids": anchor_trade_uids,
    }

    dossier = {
        "schema_version": "LLM Research Packet v1",
        "header": {
            "export_id": export_id,
            "user_input": user_input,
            "proxy_wallet": proxy_wallet,
            "generated_at": _isoformat(generated_at),
            "window_days": window_days,
            "window_start": _isoformat(window_start),
            "window_end": _isoformat(window_end),
            "max_trades": max_trades,
        },
        "coverage": coverage,
        "pnl_summary": pnl_summary,
        "distributions": distributions,
        "liquidity_summary": liquidity_summary,
        "detectors": detectors_payload,
        "anchors": anchors,
    }

    dossier_json = json.dumps(dossier, indent=2, sort_keys=True)
    detectors_json = json.dumps(detectors_payload, separators=(",", ":"), sort_keys=True)

    memo_md = _build_research_memo(dossier, anchor_rows)

    dossier_dir = build_dossier_dir(
        proxy_wallet=proxy_wallet,
        username=username,
        date_utc=generated_at,
        run_id=export_id,
    )
    output_dir = _apply_artifacts_base_path(artifacts_base_path, dossier_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    path_json = output_dir / "dossier.json"
    path_md = output_dir / "memo.md"
    manifest_path = output_dir / "manifest.json"

    path_json.write_text(dossier_json, encoding="utf-8")
    path_md.write_text(memo_md, encoding="utf-8")

    manifest = {
        "proxy_wallet": proxy_wallet,
        "username": username or "",
        "username_slug": username_slug,
        "run_id": export_id,
        "created_at_utc": _isoformat(generated_at),
        "path": str(output_dir),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")

    stats = {
        "trades_count": trades_count,
        "activity_count": activity_count,
        "positions_count": positions_count,
        "mapping_coverage": mapping_coverage,
        "liquidity_ok_count": usable_liquidity_count,
        "liquidity_total_count": liquidity_total,
        "usable_liquidity_rate": _safe_divide(usable_liquidity_count, liquidity_total),
        "pricing_snapshot_ratio": _round_value(pricing_snapshot_ratio, digits=4),
        "pricing_confidence": pricing_confidence,
        "anchor_count": len(anchor_trade_uids),
    }

    clickhouse_client.insert(
        "user_dossier_exports",
        [[
            export_id,
            proxy_wallet,
            user_input,
            username or "",
            username_slug,
            str(output_dir),
            generated_at,
            window_days,
            window_start,
            window_end,
            max_trades,
            trades_count,
            activity_count,
            positions_count,
            mapping_coverage,
            usable_liquidity_count,
            liquidity_total,
            _safe_divide(usable_liquidity_count, liquidity_total),
            float(pricing_snapshot_ratio),
            pricing_confidence,
            detectors_json,
            dossier_json,
            memo_md,
            anchor_trade_uids,
            "",
        ]],
        column_names=[
            "export_id",
            "proxy_wallet",
            "user_input",
            "username",
            "username_slug",
            "artifact_path",
            "generated_at",
            "window_days",
            "window_start",
            "window_end",
            "max_trades",
            "trades_count",
            "activity_count",
            "positions_count",
            "mapping_coverage",
            "liquidity_ok_count",
            "liquidity_total_count",
            "usable_liquidity_rate",
            "pricing_snapshot_ratio",
            "pricing_confidence",
            "detectors_json",
            "dossier_json",
            "memo_md",
            "anchor_trade_uids",
            "notes",
        ],
    )

    return UserDossierExport(
        export_id=export_id,
        proxy_wallet=proxy_wallet,
        username=username,
        username_slug=username_slug,
        generated_at=generated_at,
        window_start=window_start,
        window_end=window_end,
        dossier=dossier,
        memo_md=memo_md,
        dossier_json=dossier_json,
        detectors_json=detectors_json,
        anchor_trade_uids=anchor_trade_uids,
        stats=stats,
        artifact_path=str(output_dir),
        path_json=str(path_json),
        path_md=str(path_md),
        manifest_path=str(manifest_path),
    )
