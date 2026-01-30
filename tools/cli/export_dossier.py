#!/usr/bin/env python3
"""Export a deterministic LLM Research Packet v1 dossier and memo."""

from __future__ import annotations

import argparse
import os
import sys
from typing import Dict, Optional

import clickhouse_connect

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "packages"))

from polymarket.gamma import GammaClient
from polymarket.llm_research_packets import (
    DEFAULT_MAX_TRADES,
    DEFAULT_WINDOW_DAYS,
    export_user_dossier,
)

DEFAULT_CLICKHOUSE_HOST = "clickhouse"
DEFAULT_CLICKHOUSE_PORT = 8123
DEFAULT_CLICKHOUSE_USER = "polyttool_admin"
DEFAULT_CLICKHOUSE_PASSWORD = "polyttool_admin"
DEFAULT_CLICKHOUSE_DATABASE = "polyttool"
DEFAULT_GAMMA_BASE = "https://gamma-api.polymarket.com"
DEFAULT_HTTP_TIMEOUT = 20.0


def load_env_file(path: str) -> Dict[str, str]:
    """Load key/value pairs from a .env-style file."""
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
    """Populate os.environ with defaults from .env without overriding existing vars."""
    for key, value in env.items():
        os.environ.setdefault(key, value)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Export an LLM Research Packet v1 dossier + memo for a user.",
    )
    parser.add_argument("--user", help="Target Polymarket username (@name) or wallet address")
    parser.add_argument(
        "--days",
        type=int,
        default=DEFAULT_WINDOW_DAYS,
        help="Lookback window in days",
    )
    parser.add_argument(
        "--max-trades",
        type=int,
        default=DEFAULT_MAX_TRADES,
        help="Max anchor trades across all lists",
    )
    parser.add_argument(
        "--artifacts-dir",
        default="artifacts",
        help="Base path for artifacts output",
    )
    return parser


def _get_clickhouse_client():
    return clickhouse_connect.get_client(
        host=os.getenv("CLICKHOUSE_HOST", DEFAULT_CLICKHOUSE_HOST),
        port=int(os.getenv("CLICKHOUSE_PORT", str(DEFAULT_CLICKHOUSE_PORT))),
        username=os.getenv("CLICKHOUSE_USER", DEFAULT_CLICKHOUSE_USER),
        password=os.getenv("CLICKHOUSE_PASSWORD", DEFAULT_CLICKHOUSE_PASSWORD),
        database=os.getenv("CLICKHOUSE_DATABASE", DEFAULT_CLICKHOUSE_DATABASE),
    )


def main(argv: Optional[list[str]] = None) -> int:
    env_values = load_env_file(os.path.join(os.getcwd(), ".env"))
    apply_env_defaults(env_values)

    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.user:
        print("Error: --user is required.", file=sys.stderr)
        return 1
    if args.days <= 0:
        print("Error: --days must be positive.", file=sys.stderr)
        return 1
    if args.max_trades <= 0:
        print("Error: --max-trades must be positive.", file=sys.stderr)
        return 1

    client = _get_clickhouse_client()
    gamma_client = GammaClient(
        base_url=os.getenv("GAMMA_API_BASE", DEFAULT_GAMMA_BASE),
        timeout=float(os.getenv("HTTP_TIMEOUT_SECONDS", str(DEFAULT_HTTP_TIMEOUT))),
    )
    profile = gamma_client.resolve(args.user)
    if profile is None:
        print(f"Error: could not resolve user {args.user}", file=sys.stderr)
        return 1

    result = export_user_dossier(
        clickhouse_client=client,
        proxy_wallet=profile.proxy_wallet,
        user_input=args.user,
        window_days=args.days,
        max_trades=args.max_trades,
        artifacts_base_path=args.artifacts_dir,
    )

    print("Export complete")
    print(f"Export id: {result.export_id}")
    print(f"Proxy wallet: {result.proxy_wallet}")
    print(f"Generated at: {result.generated_at}")
    print(f"Dossier JSON: {result.path_json}")
    print(f"Memo MD: {result.path_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
