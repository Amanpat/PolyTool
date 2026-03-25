"""CLI entrypoint for artifact-first crypto-pair paper-soak reports."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Optional

from packages.polymarket.crypto_pairs.reporting import (
    CryptoPairReportError,
    generate_crypto_pair_paper_report,
)


_PREFIX = "[crypto-pair-report]"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Summarize one completed crypto-pair paper run from local artifacts only. "
            "Reads the run directory, computes the paper-soak rubric metrics, and writes "
            "paper_soak_summary.json plus paper_soak_summary.md next to the run artifacts."
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
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        result = generate_crypto_pair_paper_report(Path(args.run))
    except CryptoPairReportError as exc:
        print(f"{_PREFIX} Error: {exc}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"{_PREFIX} Error writing report: {exc}", file=sys.stderr)
        return 1

    report = result.report
    metrics = report.get("metrics", {})
    rubric = report.get("rubric", {})

    print(f"{_PREFIX} run_id        : {report.get('run_id', 'unknown')}")
    print(f"{_PREFIX} verdict       : {rubric.get('verdict', 'unknown')}")
    print(
        f"{_PREFIX} rubric_pass   : "
        f"{'yes' if rubric.get('rubric_pass') else 'no'}"
    )
    print(
        f"{_PREFIX} safety_count  : "
        f"{metrics.get('safety_violation_count', 0)}"
    )
    print(f"{_PREFIX} summary_json  : {result.json_path}")
    print(f"{_PREFIX} summary_md    : {result.markdown_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
