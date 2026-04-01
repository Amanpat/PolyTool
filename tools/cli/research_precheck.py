"""CLI entrypoint for RIS v1 precheck runner.

Subcommands:
  run       Run a precheck on an idea (default — backward compatible)
  override  Record an operator override for a precheck
  outcome   Record the actual outcome of a precheckd idea
  history   Show event history for a precheck or time window
  inspect   Show enriched KnowledgeStore query output

Usage:
  python -m polytool research-precheck --idea "Is crypto pair accumulation viable?"
  python -m polytool research-precheck run --idea "Test idea" --no-ledger
  python -m polytool research-precheck override --precheck-id abc123 --reason "Changed approach"
  python -m polytool research-precheck outcome --precheck-id abc123 --label successful
  python -m polytool research-precheck history --precheck-id abc123 --json
  python -m polytool research-precheck inspect --top-k 5
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_KNOWN_SUBCOMMANDS = frozenset({"run", "override", "outcome", "history", "inspect"})


def _resolve_ledger_path(args) -> Path | None:
    """Resolve ledger path from CLI args, or return None for --no-ledger."""
    no_ledger = getattr(args, "no_ledger", False)
    if no_ledger:
        return None
    ledger_arg = getattr(args, "ledger", None)
    if ledger_arg:
        return Path(ledger_arg)
    from packages.research.synthesis.precheck_ledger import DEFAULT_LEDGER_PATH
    return DEFAULT_LEDGER_PATH


def _cmd_run(args) -> int:
    """Execute the 'run' subcommand: evaluate an idea."""
    ledger_path = _resolve_ledger_path(args)

    try:
        from packages.research.synthesis.precheck import run_precheck
        result = run_precheck(
            args.idea,
            provider_name=args.provider,
            ledger_path=ledger_path,
        )
    except Exception as exc:
        print(f"Error: precheck failed: {exc}", file=sys.stderr)
        return 1

    if args.output_json:
        output = {
            "recommendation": result.recommendation,
            "idea": result.idea,
            "supporting_evidence": result.supporting_evidence,
            "contradicting_evidence": result.contradicting_evidence,
            "risk_factors": result.risk_factors,
            "stale_warning": result.stale_warning,
            "timestamp": result.timestamp,
            "provider_used": result.provider_used,
            "precheck_id": result.precheck_id,
            "reason_code": result.reason_code,
            "evidence_gap": result.evidence_gap,
            "review_horizon": result.review_horizon,
        }
        print(json.dumps(output, indent=2))
    else:
        def _bullet_list(items: list, fallback: str = "  (none)") -> str:
            if not items:
                return fallback
            return "\n".join(f"  - {item}" for item in items)

        print(f"Recommendation: {result.recommendation}")
        print("")
        print(f"Idea: {result.idea}")
        print("")
        print("Supporting:")
        print(_bullet_list(result.supporting_evidence))
        print("")
        print("Contradicting:")
        print(_bullet_list(result.contradicting_evidence))
        print("")
        print("Risks:")
        print(_bullet_list(result.risk_factors))
        print("")
        print(f"Stale warning: {'yes' if result.stale_warning else 'no'}")

        if ledger_path is not None:
            print(f"\nLogged to: {ledger_path}")

    return 0


def _cmd_override(args) -> int:
    """Execute the 'override' subcommand: record an operator override."""
    ledger_arg = getattr(args, "ledger", None)
    if ledger_arg:
        ledger_path = Path(ledger_arg)
    else:
        from packages.research.synthesis.precheck_ledger import DEFAULT_LEDGER_PATH
        ledger_path = DEFAULT_LEDGER_PATH

    try:
        from packages.research.synthesis.precheck_ledger import append_override
        append_override(args.precheck_id, args.reason, ledger_path=ledger_path)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Error: override failed: {exc}", file=sys.stderr)
        return 1

    if args.output_json:
        print(json.dumps({
            "status": "ok",
            "event_type": "override",
            "precheck_id": args.precheck_id,
            "reason": args.reason,
            "ledger": str(ledger_path),
        }, indent=2))
    else:
        print(f"Override recorded for precheck_id={args.precheck_id}")
        print(f"Reason: {args.reason}")
        print(f"Ledger: {ledger_path}")

    return 0


def _cmd_outcome(args) -> int:
    """Execute the 'outcome' subcommand: record the actual outcome."""
    ledger_arg = getattr(args, "ledger", None)
    if ledger_arg:
        ledger_path = Path(ledger_arg)
    else:
        from packages.research.synthesis.precheck_ledger import DEFAULT_LEDGER_PATH
        ledger_path = DEFAULT_LEDGER_PATH

    outcome_date = getattr(args, "date", None) or None

    try:
        from packages.research.synthesis.precheck_ledger import append_outcome
        append_outcome(args.precheck_id, args.label, outcome_date=outcome_date, ledger_path=ledger_path)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Error: outcome recording failed: {exc}", file=sys.stderr)
        return 1

    if args.output_json:
        print(json.dumps({
            "status": "ok",
            "event_type": "outcome",
            "precheck_id": args.precheck_id,
            "label": args.label,
            "ledger": str(ledger_path),
        }, indent=2))
    else:
        print(f"Outcome recorded for precheck_id={args.precheck_id}")
        print(f"Label: {args.label}")
        print(f"Ledger: {ledger_path}")

    return 0


def _cmd_history(args) -> int:
    """Execute the 'history' subcommand: retrieve event history."""
    ledger_arg = getattr(args, "ledger", None)
    if ledger_arg:
        ledger_path = Path(ledger_arg)
    else:
        from packages.research.synthesis.precheck_ledger import DEFAULT_LEDGER_PATH
        ledger_path = DEFAULT_LEDGER_PATH

    precheck_id = getattr(args, "precheck_id", None)
    start = getattr(args, "start", None)
    end = getattr(args, "end", None)

    if precheck_id:
        from packages.research.synthesis.precheck_ledger import get_precheck_history
        events = get_precheck_history(precheck_id, ledger_path=ledger_path)
    elif start and end:
        from packages.research.synthesis.precheck_ledger import list_prechecks_by_window
        events = list_prechecks_by_window(start, end, ledger_path=ledger_path)
    else:
        print("Error: provide --precheck-id or both --start and --end", file=sys.stderr)
        return 1

    if args.output_json:
        print(json.dumps(events, indent=2))
    else:
        if not events:
            print("(no events found)")
        for event in events:
            event_type = event.get("event_type", "?")
            pid = event.get("precheck_id", "?")
            written_at = event.get("written_at", "?")
            print(f"{written_at}  [{event_type}]  precheck_id={pid}")

    return 0


def _cmd_inspect(args) -> int:
    """Execute the 'inspect' subcommand: enriched KnowledgeStore query."""
    db_path = getattr(args, "db", None)
    if db_path:
        db_file = Path(db_path)
        if not db_file.exists():
            print(
                f"Error: KnowledgeStore database not found: {db_path}\n"
                "Create a knowledge store first using the RIS ingestion pipeline.",
                file=sys.stderr,
            )
            return 1
    else:
        from packages.polymarket.rag.knowledge_store import DEFAULT_KNOWLEDGE_DB_PATH
        db_file = DEFAULT_KNOWLEDGE_DB_PATH
        if not db_file.exists():
            print(
                f"Error: Default KnowledgeStore database not found: {db_file}\n"
                "Create a knowledge store first using the RIS ingestion pipeline,\n"
                "or specify a path with --db.",
                file=sys.stderr,
            )
            return 1

    source_family = getattr(args, "source_family", None)
    min_freshness = getattr(args, "min_freshness", None)
    top_k = getattr(args, "top_k", 20)
    include_contradicted = getattr(args, "include_contradicted", False)

    try:
        from packages.polymarket.rag.knowledge_store import KnowledgeStore
        from packages.research.ingestion.retriever import (
            query_knowledge_store_enriched,
            format_enriched_report,
        )
        store = KnowledgeStore(db_file)
        claims = query_knowledge_store_enriched(
            store,
            source_family=source_family,
            min_freshness=min_freshness,
            top_k=top_k,
            include_contradicted=include_contradicted,
        )
        store.close()
    except Exception as exc:
        print(f"Error: inspect failed: {exc}", file=sys.stderr)
        return 1

    if args.output_json:
        # Remove non-serializable bits if any
        print(json.dumps(claims, indent=2, default=str))
    else:
        print(format_enriched_report(claims))

    return 0


def main(argv: list) -> int:
    """Route subcommands for research-precheck.

    Backward compat: if argv[0] is not a known subcommand and --idea is in argv,
    treat as the 'run' subcommand (existing callers keep working).

    Returns:
        0 on success
        1 on argument error or failure
    """
    # Backward compatibility: no subcommand token but --idea present -> 'run'
    if argv and argv[0] not in _KNOWN_SUBCOMMANDS and "--idea" in argv:
        argv = ["run"] + list(argv)

    # Top-level parser with subparsers
    parser = argparse.ArgumentParser(
        prog="research-precheck",
        description="RIS v1 precheck: GO/CAUTION/STOP recommendation + lifecycle management.",
    )
    subparsers = parser.add_subparsers(dest="subcommand", metavar="SUBCOMMAND")

    # ---- run ----
    run_parser = subparsers.add_parser(
        "run",
        help="Evaluate an idea: GO / CAUTION / STOP recommendation.",
    )
    run_parser.add_argument(
        "--idea", metavar="TEXT", required=True,
        help="The idea or concept to evaluate (required).",
    )
    run_parser.add_argument(
        "--provider", metavar="NAME", default="manual",
        choices=["manual", "ollama"],
        help="Evaluation provider (default: manual).",
    )
    run_parser.add_argument(
        "--ledger", metavar="PATH", default=None,
        help="Custom ledger path.",
    )
    run_parser.add_argument(
        "--no-ledger", action="store_true",
        help="Skip writing to the ledger (dry-run mode).",
    )
    run_parser.add_argument(
        "--json", dest="output_json", action="store_true",
        help="Output raw JSON instead of formatted text.",
    )

    # ---- override ----
    override_parser = subparsers.add_parser(
        "override",
        help="Record an operator override for a precheck recommendation.",
    )
    override_parser.add_argument(
        "--precheck-id", dest="precheck_id", required=True,
        help="The precheck ID to override.",
    )
    override_parser.add_argument(
        "--reason", required=True,
        help="Human-readable reason for the override.",
    )
    override_parser.add_argument(
        "--ledger", metavar="PATH", default=None,
        help="Custom ledger path.",
    )
    override_parser.add_argument(
        "--json", dest="output_json", action="store_true",
        help="Output raw JSON.",
    )

    # ---- outcome ----
    outcome_parser = subparsers.add_parser(
        "outcome",
        help="Record the actual outcome of a precheckd idea.",
    )
    outcome_parser.add_argument(
        "--precheck-id", dest="precheck_id", required=True,
        help="The precheck ID to record the outcome for.",
    )
    outcome_parser.add_argument(
        "--label", required=True,
        choices=["successful", "failed", "partial", "not_tried"],
        help="Outcome label.",
    )
    outcome_parser.add_argument(
        "--date", metavar="ISO", default=None,
        help="Outcome date (ISO-8601). Defaults to now.",
    )
    outcome_parser.add_argument(
        "--ledger", metavar="PATH", default=None,
        help="Custom ledger path.",
    )
    outcome_parser.add_argument(
        "--json", dest="output_json", action="store_true",
        help="Output raw JSON.",
    )

    # ---- history ----
    history_parser = subparsers.add_parser(
        "history",
        help="Show event history for a precheck ID or time window.",
    )
    history_parser.add_argument(
        "--precheck-id", dest="precheck_id", default=None,
        help="Show all events for this precheck ID.",
    )
    history_parser.add_argument(
        "--start", metavar="ISO", default=None,
        help="Start of time window (inclusive, ISO-8601).",
    )
    history_parser.add_argument(
        "--end", metavar="ISO", default=None,
        help="End of time window (inclusive, ISO-8601).",
    )
    history_parser.add_argument(
        "--ledger", metavar="PATH", default=None,
        help="Custom ledger path.",
    )
    history_parser.add_argument(
        "--json", dest="output_json", action="store_true",
        help="Output raw JSON.",
    )

    # ---- inspect ----
    inspect_parser = subparsers.add_parser(
        "inspect",
        help="Show enriched KnowledgeStore query output with provenance and contradictions.",
    )
    inspect_parser.add_argument(
        "--source-family", dest="source_family", metavar="TEXT", default=None,
        help="Filter by source family.",
    )
    inspect_parser.add_argument(
        "--min-freshness", dest="min_freshness", type=float, default=None,
        help="Minimum freshness modifier threshold.",
    )
    inspect_parser.add_argument(
        "--top-k", dest="top_k", type=int, default=20,
        help="Maximum number of results (default: 20).",
    )
    inspect_parser.add_argument(
        "--db", metavar="PATH", default=None,
        help="Path to the KnowledgeStore SQLite database.",
    )
    inspect_parser.add_argument(
        "--include-contradicted", dest="include_contradicted", action="store_true",
        help="Extensibility hook (contradicted claims are already annotated by default).",
    )
    inspect_parser.add_argument(
        "--json", dest="output_json", action="store_true",
        help="Output raw JSON instead of formatted report.",
    )

    try:
        args = parser.parse_args(argv)
    except SystemExit:
        raise

    if args.subcommand == "run":
        return _cmd_run(args)
    elif args.subcommand == "override":
        return _cmd_override(args)
    elif args.subcommand == "outcome":
        return _cmd_outcome(args)
    elif args.subcommand == "history":
        return _cmd_history(args)
    elif args.subcommand == "inspect":
        return _cmd_inspect(args)
    else:
        parser.print_help()
        return 1
