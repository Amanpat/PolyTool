"""CLI entrypoint for RIS operator stats and metrics export.

Subcommands:
  summary  Print a human-readable metrics snapshot to stdout.
  export   Write metrics_snapshot.json to artifacts/research/ (local-first Grafana file).

Usage:
  python -m polytool research-stats summary
  python -m polytool research-stats summary --json
  python -m polytool research-stats export
  python -m polytool research-stats export --out artifacts/research/metrics_snapshot.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_KNOWN_SUBCOMMANDS = frozenset({"summary", "export"})
_DEFAULT_EXPORT_PATH = "artifacts/research/metrics_snapshot.json"


def _add_common_path_args(parser: argparse.ArgumentParser) -> None:
    """Add shared path-override arguments to a subcommand parser."""
    parser.add_argument(
        "--db",
        metavar="PATH",
        default=None,
        help="Override KnowledgeStore SQLite path (default: kb/rag/knowledge/knowledge.sqlite3)",
    )
    parser.add_argument(
        "--eval-artifacts-dir",
        metavar="PATH",
        default=None,
        help="Override eval artifacts directory (default: artifacts/research/eval_artifacts)",
    )
    parser.add_argument(
        "--precheck-ledger",
        metavar="PATH",
        default=None,
        help="Override precheck ledger path (default: artifacts/research/prechecks/precheck_ledger.jsonl)",
    )
    parser.add_argument(
        "--report-dir",
        metavar="PATH",
        default=None,
        help="Override report directory (default: artifacts/research/reports)",
    )
    parser.add_argument(
        "--acquisition-review-dir",
        metavar="PATH",
        default=None,
        help="Override acquisition review directory (default: artifacts/research/acquisition_reviews)",
    )


def _collect_from_args(args: argparse.Namespace):
    """Call collect_ris_metrics() applying any CLI path overrides."""
    from packages.research.metrics import collect_ris_metrics

    kwargs = {}
    if args.db:
        kwargs["db_path"] = Path(args.db)
    if args.eval_artifacts_dir:
        kwargs["eval_artifacts_dir"] = Path(args.eval_artifacts_dir)
    if args.precheck_ledger:
        kwargs["precheck_ledger_path"] = Path(args.precheck_ledger)
    if args.report_dir:
        kwargs["report_dir"] = Path(args.report_dir)
    if args.acquisition_review_dir:
        kwargs["acquisition_review_dir"] = Path(args.acquisition_review_dir)

    return collect_ris_metrics(**kwargs)


def _cmd_summary(args: argparse.Namespace) -> int:
    """Handle `research-stats summary` subcommand."""
    from packages.research.metrics import format_metrics_summary

    snapshot = _collect_from_args(args)

    if getattr(args, "json", False):
        print(json.dumps(snapshot.to_dict(), indent=2))
    else:
        print(format_metrics_summary(snapshot))

    return 0


def _cmd_export(args: argparse.Namespace) -> int:
    """Handle `research-stats export` subcommand."""
    out_path = Path(getattr(args, "out", _DEFAULT_EXPORT_PATH))
    snapshot = _collect_from_args(args)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(snapshot.to_dict(), indent=2), encoding="utf-8")
    print(f"Metrics exported to: {out_path}")
    return 0


def main(argv: list) -> int:
    """CLI entrypoint for research-stats command.

    Args:
        argv: Command-line arguments (excluding the command name itself).

    Returns:
        Exit code (0 = success, 1 = error).
    """
    parser = argparse.ArgumentParser(
        prog="research-stats",
        description="RIS operator metrics snapshot and local-first export.",
    )
    subparsers = parser.add_subparsers(dest="subcommand", metavar="SUBCOMMAND")

    # summary subcommand
    summary_parser = subparsers.add_parser(
        "summary",
        help="Print a human-readable metrics snapshot to stdout.",
    )
    summary_parser.add_argument(
        "--json",
        action="store_true",
        default=False,
        help="Output raw JSON instead of formatted text.",
    )
    _add_common_path_args(summary_parser)

    # export subcommand
    export_parser = subparsers.add_parser(
        "export",
        help="Write metrics_snapshot.json to disk for Grafana/Infinity plugin.",
    )
    export_parser.add_argument(
        "--out",
        metavar="PATH",
        default=_DEFAULT_EXPORT_PATH,
        help=f"Output file path (default: {_DEFAULT_EXPORT_PATH})",
    )
    _add_common_path_args(export_parser)

    args = parser.parse_args(argv)

    if not args.subcommand or args.subcommand not in _KNOWN_SUBCOMMANDS:
        parser.print_help()
        return 1

    if args.subcommand == "summary":
        return _cmd_summary(args)
    elif args.subcommand == "export":
        return _cmd_export(args)

    # Should not reach here
    parser.print_help()
    return 1
