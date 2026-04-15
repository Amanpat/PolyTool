"""CLI entrypoint for the crypto-pair await-and-launch smoke-soak helper."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Optional

from packages.polymarket.crypto_pairs.await_soak import (
    DEFAULT_POLL_INTERVAL_SECONDS,
    DEFAULT_SOAK_DURATION_SECONDS,
    DEFAULT_SOAK_HEARTBEAT_SECONDS,
    DEFAULT_TIMEOUT_SECONDS,
    run_crypto_pair_await_soak,
)
from packages.polymarket.crypto_pairs.paper_runner import DEFAULT_KILL_SWITCH_PATH


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Wait for eligible BTC/ETH/SOL 5m/15m markets, then launch the "
            "standard paper-only Coinbase smoke soak."
        )
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_TIMEOUT_SECONDS,
        help=f"Maximum seconds to wait before exiting cleanly (default: {DEFAULT_TIMEOUT_SECONDS}).",
    )
    parser.add_argument(
        "--poll-interval",
        type=int,
        default=DEFAULT_POLL_INTERVAL_SECONDS,
        help=f"Seconds between availability polls (default: {DEFAULT_POLL_INTERVAL_SECONDS}).",
    )
    parser.add_argument(
        "--duration-seconds",
        type=int,
        default=DEFAULT_SOAK_DURATION_SECONDS,
        help=(
            "Override the launched paper soak duration in seconds "
            f"(default: {DEFAULT_SOAK_DURATION_SECONDS} = 24h)."
        ),
    )
    parser.add_argument(
        "--heartbeat-minutes",
        type=int,
        default=DEFAULT_SOAK_HEARTBEAT_SECONDS // 60,
        help=(
            "Heartbeat interval in minutes for the launched soak "
            f"(default: {DEFAULT_SOAK_HEARTBEAT_SECONDS // 60})."
        ),
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Base artifact directory for launcher manifests (default: artifacts/crypto_pairs/await_soak).",
    )
    # auto-report is on by default; --no-auto-report opts out
    parser.set_defaults(auto_report=True)
    parser.add_argument(
        "--auto-report",
        dest="auto_report",
        action="store_true",
        help="Enable automatic post-soak report generation (default: on).",
    )
    parser.add_argument(
        "--no-auto-report",
        dest="auto_report",
        action="store_false",
        help="Disable automatic post-soak report generation.",
    )
    parser.add_argument(
        "--sink-enabled",
        action="store_true",
        default=False,
        help="Enable ClickHouse sink for soak event recording (default: off).",
    )
    parser.add_argument(
        "--max-capital-window-usdc",
        type=float,
        default=None,
        help="Cap total capital deployed per soak window in USDC (default: no cap).",
    )
    parser.add_argument(
        "--kill-switch",
        type=str,
        default=str(DEFAULT_KILL_SWITCH_PATH),
        help=(
            "Path to kill switch file checked before launch "
            f"(default: {DEFAULT_KILL_SWITCH_PATH})."
        ),
    )
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    heartbeat_seconds = args.heartbeat_minutes * 60

    try:
        manifest = run_crypto_pair_await_soak(
            timeout_seconds=args.timeout,
            poll_interval_seconds=args.poll_interval,
            duration_seconds=args.duration_seconds,
            heartbeat_seconds=heartbeat_seconds,
            output_base=Path(args.output) if args.output else None,
            auto_report=args.auto_report,
            sink_enabled=args.sink_enabled,
            max_capital_window_usdc=args.max_capital_window_usdc,
            kill_switch_path=Path(args.kill_switch),
        )
    except ValueError as exc:
        print(f"crypto-pair-await-soak rejected startup: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(
            f"crypto-pair-await-soak failed: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 1

    return int(manifest.get("exit_code", 1))


if __name__ == "__main__":
    raise SystemExit(main())
