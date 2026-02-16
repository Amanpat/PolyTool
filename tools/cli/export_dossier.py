#!/usr/bin/env python3
"""Export a deterministic LLM Research Packet v1 dossier and memo."""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path
from typing import Dict, Optional

import clickhouse_connect

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "packages"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from polymarket.gamma import GammaClient
from polymarket.llm_research_packets import (
    DEFAULT_MAX_TRADES,
    DEFAULT_WINDOW_DAYS,
    export_user_dossier,
)
from polytool.user_context import resolve_user_context

logger = logging.getLogger(__name__)

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
    target_group = parser.add_mutually_exclusive_group(required=True)
    target_group.add_argument("--user", help="Target Polymarket username (@name)")
    target_group.add_argument("--wallet", help="Target proxy wallet address (0x...)")
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
        host=_resolve_clickhouse_host(),
        port=_resolve_clickhouse_port(),
        username=os.getenv("CLICKHOUSE_USER", DEFAULT_CLICKHOUSE_USER),
        password=os.getenv("CLICKHOUSE_PASSWORD", DEFAULT_CLICKHOUSE_PASSWORD),
        database=_resolve_clickhouse_database(),
    )


def main(argv: Optional[list[str]] = None) -> int:
    env_values = load_env_file(os.path.join(os.getcwd(), ".env"))
    apply_env_defaults(env_values)

    parser = build_parser()
    args = parser.parse_args(argv)

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
    input_value = args.user or args.wallet
    profile = gamma_client.resolve(input_value)
    if profile is None:
        print(f"Error: could not resolve user {input_value}", file=sys.stderr)
        return 1

    # Use canonical identity resolver - preserves original --user input for slug derivation
    # This ensures "@DrPufferfish" always routes to "drpufferfish/" folder
    original_handle = args.user.strip() if args.user else None
    if original_handle and not original_handle.startswith("@"):
        original_handle = f"@{original_handle}"

    user_ctx = resolve_user_context(
        handle=original_handle,
        wallet=profile.proxy_wallet,
        kb_root=Path("kb"),
        artifacts_root=Path(args.artifacts_dir),
        require_wallet_for_handle=bool(args.user),
    )

    logger.debug(
        "Resolved UserContext: slug=%s handle=%s wallet=%s",
        user_ctx.slug,
        user_ctx.handle,
        user_ctx.wallet,
    )

    # username_label is used for display, derive from resolved context
    username_label = user_ctx.handle

    result = export_user_dossier(
        clickhouse_client=client,
        proxy_wallet=profile.proxy_wallet,
        user_input=input_value,
        username=username_label,
        window_days=args.days,
        max_trades=args.max_trades,
        artifacts_base_path=args.artifacts_dir,
        user_slug_override=user_ctx.slug,  # Pass canonical slug to override internal derivation
    )

    print("Export complete")
    print(f"Export id: {result.export_id}")
    print(f"Proxy wallet: {result.proxy_wallet}")
    print(f"Username: {result.username or 'unknown'}")
    print(f"Username slug: {result.username_slug}")
    print(f"Generated at: {result.generated_at}")
    print(f"Artifact dir: {result.artifact_path}")
    print(f"Dossier JSON: {result.path_json}")
    print(f"Memo MD: {result.path_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
