"""CLI entrypoint for the crypto-pair await-and-launch smoke-soak helper."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Optional

from packages.polymarket.crypto_pairs.await_soak import (
    DEFAULT_DURATION_SECONDS,
    DEFAULT_POLL_INTERVAL_SECONDS,
    DEFAULT_TIMEOUT_SECONDS,
    run_crypto_pair_await_soak,
)


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
        default=DEFAULT_DURATION_SECONDS,
        help=(
            "Override the launched paper smoke-soak duration in seconds "
            f"(default: {DEFAULT_DURATION_SECONDS})."
        ),
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Base artifact directory for launcher manifests (default: artifacts/crypto_pairs/await_soak).",
    )
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        manifest = run_crypto_pair_await_soak(
            timeout_seconds=args.timeout,
            poll_interval_seconds=args.poll_interval,
            duration_seconds=args.duration_seconds,
            output_base=Path(args.output) if args.output else None,
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
