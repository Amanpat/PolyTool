#!/usr/bin/env python3
"""Export ClickHouse datasets into the private KB for offline RAG."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

import clickhouse_connect

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "packages"))

from polymarket.gamma import GammaClient
from polymarket.llm_research_packets import _username_to_slug

DEFAULT_CLICKHOUSE_USER = "polyttool_admin"
DEFAULT_CLICKHOUSE_PASSWORD = "polyttool_admin"
DEFAULT_GAMMA_BASE = "https://gamma-api.polymarket.com"
DEFAULT_HTTP_TIMEOUT = 20.0


def _running_in_docker() -> bool:
    """Return True when executing inside a Docker container."""
    if os.environ.get("POLYTOOL_IN_DOCKER") == "1":
        return True
    return Path("/.dockerenv").exists()


def _resolve_clickhouse_host() -> str:
    host = os.environ.get("CLICKHOUSE_HOST")
    if host:
        return host
    return "clickhouse" if _running_in_docker() else "localhost"


def _resolve_clickhouse_port() -> int:
    port = os.environ.get("CLICKHOUSE_PORT") or os.environ.get("CLICKHOUSE_HTTP_PORT")
    return int(port) if port else 8123


def _resolve_clickhouse_database() -> str:
    return os.environ.get("CLICKHOUSE_DATABASE") or os.environ.get("CLICKHOUSE_DB") or "polyttool"


def load_env_file(path: str) -> Dict[str, str]:
    if not os.path.exists(path):
        return {}
    env: Dict[str, str] = {}
    with open(path, "r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip("'").strip('"')
            if key:
                env[key] = value
    return env


def apply_env_defaults(env: Dict[str, str]) -> None:
    for key, value in env.items():
        os.environ.setdefault(key, value)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Export ClickHouse datasets for local RAG.")
    target_group = parser.add_mutually_exclusive_group(required=True)
    target_group.add_argument("--user", help="Target Polymarket username (@name)")
    target_group.add_argument("--wallet", help="Target proxy wallet address (0x...)")
    parser.add_argument(
        "--out",
        help="Output directory (default: kb/users/<slug>/exports/<YYYY-MM-DD>/)",
    )
    parser.add_argument("--trades-limit", type=int, default=2000, help="Trades rows limit.")
    parser.add_argument("--orderbook-limit", type=int, default=1000, help="Orderbook rows limit.")
    parser.add_argument("--arb-limit", type=int, default=400, help="Arb rows limit.")
    parser.add_argument("--no-arb", action="store_true", help="Skip arb_feasibility_bucket export.")
    return parser


def _get_clickhouse_client():
    return clickhouse_connect.get_client(
        host=_resolve_clickhouse_host(),
        port=_resolve_clickhouse_port(),
        username=os.getenv("CLICKHOUSE_USER", DEFAULT_CLICKHOUSE_USER),
        password=os.getenv("CLICKHOUSE_PASSWORD", DEFAULT_CLICKHOUSE_PASSWORD),
        database=_resolve_clickhouse_database(),
    )


def _serialize_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.replace(microsecond=0).isoformat() + "Z"
    if isinstance(value, date):
        return value.isoformat()
    return value


def _rows_to_dicts(result) -> list[dict]:
    rows = []
    column_names = getattr(result, "column_names", None) or []
    for row in result.result_rows:
        record = {}
        for idx, name in enumerate(column_names):
            value = row[idx] if idx < len(row) else None
            record[name] = _serialize_value(value)
        rows.append(record)
    return rows


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _export_user_trades(client, proxy_wallet: str, limit: int) -> list[dict]:
    query = """
        SELECT
            trade_uid,
            ts,
            resolved_token_id,
            resolved_condition_id,
            market_slug,
            question,
            resolved_outcome_name,
            side,
            price,
            size,
            transaction_hash
        FROM user_trades_resolved
        WHERE proxy_wallet = {wallet:String}
        ORDER BY ts DESC
        LIMIT {limit:Int32}
    """
    result = client.query(query, parameters={"wallet": proxy_wallet, "limit": int(limit)})
    return _rows_to_dicts(result)


def _export_detector_latest(client, proxy_wallet: str) -> list[dict]:
    query = """
        SELECT
            detector_name,
            bucket_type,
            max(bucket_start) AS bucket_start,
            argMax(score, bucket_start) AS score,
            argMax(label, bucket_start) AS label,
            argMax(evidence_json, bucket_start) AS evidence_json,
            max(computed_at) AS computed_at
        FROM detector_results
        WHERE proxy_wallet = {wallet:String}
        GROUP BY detector_name, bucket_type
        ORDER BY detector_name ASC, bucket_type ASC
    """
    result = client.query(query, parameters={"wallet": proxy_wallet})
    return _rows_to_dicts(result)


def _export_pnl_latest(client, proxy_wallet: str) -> list[dict]:
    query = """
        SELECT
            bucket_type,
            max(bucket_start) AS bucket_start,
            argMax(realized_pnl, bucket_start) AS realized_pnl,
            argMax(mtm_pnl_estimate, bucket_start) AS mtm_pnl_estimate,
            argMax(exposure_notional_estimate, bucket_start) AS exposure_notional_estimate,
            argMax(open_position_tokens, bucket_start) AS open_position_tokens,
            argMax(pricing_source, bucket_start) AS pricing_source,
            max(computed_at) AS computed_at
        FROM user_pnl_bucket
        WHERE proxy_wallet = {wallet:String}
        GROUP BY bucket_type
        ORDER BY bucket_type ASC
    """
    result = client.query(query, parameters={"wallet": proxy_wallet})
    return _rows_to_dicts(result)


def _export_orderbook_snapshots(client, proxy_wallet: str, limit: int) -> list[dict]:
    query = """
        SELECT
            snapshot_ts,
            resolved_token_id,
            market_slug,
            question,
            status,
            best_bid,
            best_ask,
            spread_bps,
            depth_bid_usd_50bps,
            depth_ask_usd_50bps,
            slippage_buy_bps_100,
            slippage_sell_bps_100
        FROM orderbook_snapshots_enriched
        WHERE resolved_token_id IN (
            SELECT DISTINCT resolved_token_id
            FROM user_trades_resolved
            WHERE proxy_wallet = {wallet:String}
              AND resolved_token_id != ''
        )
        ORDER BY snapshot_ts DESC
        LIMIT {limit:Int32}
    """
    result = client.query(query, parameters={"wallet": proxy_wallet, "limit": int(limit)})
    return _rows_to_dicts(result)


def _export_arb_feasibility(client, proxy_wallet: str, limit: int) -> list[dict]:
    query = """
        SELECT
            bucket_type,
            bucket_start,
            condition_id,
            gross_edge_est_bps,
            total_fees_est_usdc,
            total_slippage_est_usdc,
            net_edge_est_bps,
            break_even_notional_usd,
            confidence,
            evidence_json,
            computed_at
        FROM arb_feasibility_bucket
        WHERE proxy_wallet = {wallet:String}
        ORDER BY bucket_start DESC
        LIMIT {limit:Int32}
    """
    result = client.query(query, parameters={"wallet": proxy_wallet, "limit": int(limit)})
    return _rows_to_dicts(result)


def main(argv: Optional[list[str]] = None) -> int:
    env_values = load_env_file(os.path.join(os.getcwd(), ".env"))
    apply_env_defaults(env_values)

    parser = build_parser()
    args = parser.parse_args(argv)

    if args.trades_limit <= 0 or args.orderbook_limit <= 0 or args.arb_limit <= 0:
        print("Error: limits must be positive.")
        return 1

    client = _get_clickhouse_client()
    proxy_wallet = None
    username_label = None

    if args.user:
        gamma_client = GammaClient(
            base_url=os.getenv("GAMMA_API_BASE", DEFAULT_GAMMA_BASE),
            timeout=float(os.getenv("HTTP_TIMEOUT_SECONDS", str(DEFAULT_HTTP_TIMEOUT))),
        )
        profile = gamma_client.resolve(args.user)
        if profile is None:
            print(f"Error: could not resolve user {args.user}", file=sys.stderr)
            return 1
        proxy_wallet = profile.proxy_wallet
        if profile.username:
            username_label = f"@{profile.username}"
        else:
            cleaned = args.user.strip()
            if cleaned:
                username_label = cleaned if cleaned.startswith("@") else f"@{cleaned}"
    else:
        proxy_wallet = args.wallet.strip()

    username_slug = _username_to_slug(username_label or proxy_wallet)
    date_label = datetime.utcnow().strftime("%Y-%m-%d")
    default_out = Path("kb") / "users" / username_slug / "exports" / date_label
    output_dir = Path(args.out) if args.out else default_out
    output_dir.mkdir(parents=True, exist_ok=True)

    payloads = {
        "user_trades_resolved.json": _export_user_trades(client, proxy_wallet, args.trades_limit),
        "detector_results_latest.json": _export_detector_latest(client, proxy_wallet),
        "user_pnl_bucket_latest.json": _export_pnl_latest(client, proxy_wallet),
        "orderbook_snapshots_enriched.json": _export_orderbook_snapshots(
            client, proxy_wallet, args.orderbook_limit
        ),
    }
    if not args.no_arb:
        payloads["arb_feasibility_bucket.json"] = _export_arb_feasibility(
            client, proxy_wallet, args.arb_limit
        )

    for filename, payload in payloads.items():
        _write_json(output_dir / filename, payload)

    manifest = {
        "proxy_wallet": proxy_wallet,
        "username": username_label or "",
        "username_slug": username_slug,
        "generated_at_utc": datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        "output_dir": str(output_dir),
        "files": sorted(payloads.keys()),
    }
    _write_json(output_dir / "export_manifest.json", manifest)

    print("ClickHouse export complete")
    print(f"Proxy wallet: {proxy_wallet}")
    print(f"Username: {username_label or 'unknown'}")
    print(f"Username slug: {username_slug}")
    print(f"Output dir: {output_dir}")
    print(f"Files: {', '.join(sorted(payloads.keys()))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
