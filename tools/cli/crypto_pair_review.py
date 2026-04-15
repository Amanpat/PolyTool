"""CLI entrypoint for crypto-pair post-soak review helper."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

from packages.polymarket.crypto_pairs.reporting import (
    CryptoPairReportError,
    format_post_soak_review,
    load_or_generate_report,
)


_PREFIX = "[crypto-pair-review]"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Review a completed crypto-pair paper soak. Reads existing report artifacts "
            "(or generates them) and prints a concise one-screen operator summary."
        )
    )
    parser.add_argument(
        "--run",
        required=True,
        metavar="PATH",
        help=(
            "Path to a completed paper-run directory. You may also point at "
            "run_manifest.json or run_summary.json inside that directory."
        ),
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="output_json",
        help=(
            "If set, print the paper_soak_summary.json content to stdout as formatted "
            "JSON instead of the human-readable review. Useful for scripting."
        ),
    )
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        report = load_or_generate_report(Path(args.run))
    except CryptoPairReportError as exc:
        print(f"{_PREFIX} Error: {exc}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"{_PREFIX} Error reading run: {exc}", file=sys.stderr)
        return 1

    if args.output_json:
        print(json.dumps(report, indent=2, sort_keys=True, allow_nan=False))
        return 0

    try:
        review_text = format_post_soak_review(report)
    except Exception as exc:  # noqa: BLE001
        print(f"{_PREFIX} Error formatting review: {exc}", file=sys.stderr)
        return 1

    print(review_text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
