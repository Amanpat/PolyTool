"""CLI entrypoint for RIS report persistence and catalog.

Subcommands:
  save    Save a report artifact (from --body, --body-file, or stdin)
  list    List past reports with optional time-window filter
  search  Search past reports by keyword
  digest  Generate a weekly digest from precheck and eval artifact data

Usage:
  python -m polytool research-report save --title "Market Edge Analysis" --body "Content..."
  python -m polytool research-report list --window 7d
  python -m polytool research-report list --window all --limit 50
  python -m polytool research-report search --query "market maker"
  python -m polytool research-report digest --window 7
  python -m polytool research-report digest --window 30 --json
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

_KNOWN_SUBCOMMANDS = frozenset({"save", "list", "search", "digest"})
_VALID_TYPES = ["precheck_summary", "eval_summary", "weekly_digest", "custom"]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _iso_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat()


def _parse_window(window: str) -> tuple[str | None, str | None]:
    """Parse a duration string into (start_iso, end_iso) UTC pair.

    Supported formats:
    - "all" -> (None, None)
    - "Nd" -> last N days
    - "Nh" -> last N hours

    Returns:
        Tuple of (start_iso, end_iso) or (None, None) for "all".
    """
    if window == "all":
        return None, None

    now = _utcnow()
    end_iso = _iso_utc(now)

    if window.endswith("d"):
        try:
            days = int(window[:-1])
            start_iso = _iso_utc(now - timedelta(days=days))
            return start_iso, end_iso
        except ValueError:
            pass
    elif window.endswith("h"):
        try:
            hours = int(window[:-1])
            start_iso = _iso_utc(now - timedelta(hours=hours))
            return start_iso, end_iso
        except ValueError:
            pass

    raise ValueError(
        f"Unrecognised window format: {window!r}. "
        "Use 'all', 'Nd' (days), or 'Nh' (hours)."
    )


def _resolve_report_dir(args) -> Path:
    """Resolve report directory from CLI args."""
    report_dir_arg = getattr(args, "report_dir", None)
    if report_dir_arg:
        return Path(report_dir_arg)
    from packages.research.synthesis.report_ledger import DEFAULT_REPORT_DIR
    return DEFAULT_REPORT_DIR


def _cmd_save(args) -> int:
    """Execute the 'save' subcommand: persist a report."""
    report_dir = _resolve_report_dir(args)

    # Resolve body
    body: str | None = None

    body_file_arg = getattr(args, "body_file", None)
    body_arg = getattr(args, "body", None)

    if body_arg is not None:
        body = body_arg
    elif body_file_arg is not None:
        try:
            body = Path(body_file_arg).read_text(encoding="utf-8")
        except OSError as exc:
            print(f"Error: cannot read body file: {exc}", file=sys.stderr)
            return 1
    else:
        # Read from stdin
        if sys.stdin.isatty():
            print(
                "Error: no body provided. Use --body TEXT, --body-file PATH, or pipe via stdin.",
                file=sys.stderr,
            )
            return 1
        body = sys.stdin.read()

    if not body.strip():
        print("Error: report body is empty.", file=sys.stderr)
        return 1

    title = args.title
    report_type = getattr(args, "type", "custom") or "custom"
    tags = getattr(args, "tags", None) or []
    summary_text = getattr(args, "summary", None) or ""

    try:
        from packages.research.synthesis.report_ledger import persist_report
        entry = persist_report(
            title=title,
            body_md=body,
            report_type=report_type,
            source_window="custom",
            summary_line=summary_text,
            tags=tags,
            report_dir=report_dir,
        )
    except Exception as exc:
        print(f"Error: save failed: {exc}", file=sys.stderr)
        return 1

    if getattr(args, "output_json", False):
        import dataclasses
        print(json.dumps(dataclasses.asdict(entry), indent=2))
    else:
        print(f"Report saved: {entry.report_id}")
        print(f"  Title:  {entry.title}")
        print(f"  Type:   {entry.report_type}")
        print(f"  Path:   {entry.artifact_path}")
        print(f"  Index:  {report_dir / 'report_index.jsonl'}")

    return 0


def _cmd_list(args) -> int:
    """Execute the 'list' subcommand: list past reports."""
    report_dir = _resolve_report_dir(args)
    window = getattr(args, "window", "30d") or "30d"
    limit = getattr(args, "limit", 20) or 20

    try:
        window_start, window_end = _parse_window(window)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    try:
        from packages.research.synthesis.report_ledger import list_reports
        reports = list_reports(
            report_dir=report_dir,
            window_start=window_start,
            window_end=window_end,
        )
    except Exception as exc:
        print(f"Error: list failed: {exc}", file=sys.stderr)
        return 1

    reports = reports[:limit]

    if getattr(args, "output_json", False):
        print(json.dumps(reports, indent=2))
    else:
        if not reports:
            print(f"No reports found in window: {window}")
        else:
            print(f"Reports ({len(reports)} shown, window={window}):")
            print("")
            for r in reports:
                report_id = r.get("report_id", "?")
                title = r.get("title", "(untitled)")
                report_type = r.get("report_type", "custom")
                created = r.get("created_at", "")[:10]
                summary = r.get("summary_line", "")
                if len(summary) > 80:
                    summary = summary[:77] + "..."
                print(f"  [{created}] {report_id}  {title}  ({report_type})")
                if summary:
                    print(f"             {summary}")

    return 0


def _cmd_search(args) -> int:
    """Execute the 'search' subcommand: search reports by keyword."""
    report_dir = _resolve_report_dir(args)
    query = args.query

    try:
        from packages.research.synthesis.report_ledger import search_reports
        results = search_reports(query=query, report_dir=report_dir)
    except Exception as exc:
        print(f"Error: search failed: {exc}", file=sys.stderr)
        return 1

    if getattr(args, "output_json", False):
        print(json.dumps(results, indent=2))
    else:
        if not results:
            print(f"No reports matching: {query!r}")
        else:
            print(f"Search results for {query!r} ({len(results)} found):")
            print("")
            for r in results:
                report_id = r.get("report_id", "?")
                title = r.get("title", "(untitled)")
                report_type = r.get("report_type", "custom")
                created = r.get("created_at", "")[:10]
                print(f"  [{created}] {report_id}  {title}  ({report_type})")

    return 0


def _cmd_digest(args) -> int:
    """Execute the 'digest' subcommand: generate a weekly digest."""
    report_dir = _resolve_report_dir(args)
    window_days = getattr(args, "window", 7) or 7

    precheck_ledger_arg = getattr(args, "precheck_ledger", None)
    precheck_ledger_path = Path(precheck_ledger_arg) if precheck_ledger_arg else None

    eval_artifacts_dir_arg = getattr(args, "eval_artifacts_dir", None)
    eval_artifacts_dir = Path(eval_artifacts_dir_arg) if eval_artifacts_dir_arg else None

    try:
        from packages.research.synthesis.report_ledger import generate_digest
        entry = generate_digest(
            window_days=window_days,
            report_dir=report_dir,
            precheck_ledger_path=precheck_ledger_path,
            eval_artifacts_dir=eval_artifacts_dir,
        )
    except Exception as exc:
        print(f"Error: digest generation failed: {exc}", file=sys.stderr)
        return 1

    if getattr(args, "output_json", False):
        import dataclasses
        print(json.dumps(dataclasses.asdict(entry), indent=2))
    else:
        print(f"Digest generated: {entry.report_id}")
        print(f"  Title:   {entry.title}")
        print(f"  Window:  {window_days}d")
        print(f"  Path:    {entry.artifact_path}")
        print(f"  Summary: {entry.summary_line}")

    return 0


def main(argv: list) -> int:
    """Route subcommands for research-report.

    Returns:
        0 on success
        1 on argument error or failure
    """
    parser = argparse.ArgumentParser(
        prog="research-report",
        description="RIS report persistence: save, list, search reports and generate weekly digests.",
    )
    subparsers = parser.add_subparsers(dest="subcommand", metavar="SUBCOMMAND")

    # Shared arguments factory
    def _add_common(p: argparse.ArgumentParser) -> None:
        p.add_argument(
            "--json", dest="output_json", action="store_true",
            help="Output raw JSON instead of formatted text.",
        )
        p.add_argument(
            "--report-dir", dest="report_dir", metavar="PATH", default=None,
            help="Override default report directory (artifacts/research/reports).",
        )

    # ---- save ----
    save_parser = subparsers.add_parser(
        "save",
        help="Save a report from --body, --body-file, or stdin.",
    )
    save_parser.add_argument(
        "--title", metavar="TEXT", required=True,
        help="Human-readable title for the report (required).",
    )
    save_parser.add_argument(
        "--type", dest="type", metavar="TYPE",
        choices=_VALID_TYPES, default="custom",
        help="Report type (default: custom).",
    )
    save_parser.add_argument(
        "--tags", nargs="+", metavar="TAG",
        help="Searchable tags.",
    )
    save_parser.add_argument(
        "--body", metavar="TEXT", default=None,
        help="Inline report body.",
    )
    save_parser.add_argument(
        "--body-file", dest="body_file", metavar="PATH", default=None,
        help="Read report body from file.",
    )
    save_parser.add_argument(
        "--summary", metavar="TEXT", default=None,
        help="One-line summary (defaults to first 200 chars of body).",
    )
    _add_common(save_parser)

    # ---- list ----
    list_parser = subparsers.add_parser(
        "list",
        help="List past reports, optionally filtered by time window.",
    )
    list_parser.add_argument(
        "--window", metavar="DURATION", default="30d",
        help="Time window: 'all', '7d', '30d', 'Nh' (default: 30d).",
    )
    list_parser.add_argument(
        "--limit", type=int, default=20, metavar="N",
        help="Maximum number of reports to show (default: 20).",
    )
    _add_common(list_parser)

    # ---- search ----
    search_parser = subparsers.add_parser(
        "search",
        help="Search past reports by keyword (title, summary, tags).",
    )
    search_parser.add_argument(
        "--query", metavar="TEXT", required=True,
        help="Search keyword or phrase (required).",
    )
    _add_common(search_parser)

    # ---- digest ----
    digest_parser = subparsers.add_parser(
        "digest",
        help="Generate a weekly digest from precheck and eval artifact data.",
    )
    digest_parser.add_argument(
        "--window", type=int, default=7, metavar="DAYS",
        help="Number of days to look back (default: 7).",
    )
    digest_parser.add_argument(
        "--precheck-ledger", dest="precheck_ledger", metavar="PATH", default=None,
        help="Path to precheck JSONL ledger (default: artifacts/research/prechecks/precheck_ledger.jsonl).",
    )
    digest_parser.add_argument(
        "--eval-artifacts-dir", dest="eval_artifacts_dir", metavar="PATH", default=None,
        help="Directory containing eval_artifacts.jsonl (default: artifacts/research/eval_artifacts).",
    )
    _add_common(digest_parser)

    try:
        args = parser.parse_args(argv)
    except SystemExit:
        raise

    if args.subcommand == "save":
        return _cmd_save(args)
    elif args.subcommand == "list":
        return _cmd_list(args)
    elif args.subcommand == "search":
        return _cmd_search(args)
    elif args.subcommand == "digest":
        return _cmd_digest(args)
    else:
        parser.print_help()
        return 1
