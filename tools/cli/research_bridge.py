"""CLI bridge for RIS v1 hypothesis registration and validation feedback.

Two subcommands:
  register-hypothesis   Register a research hypothesis candidate in the JSONL registry.
  record-outcome        Record a SimTrader validation outcome for a set of KS claims.

Both subcommands emit JSON to stdout and exit 0 on success, exit 1 on error.

Usage::

  python -m polytool research-register-hypothesis --candidate-json PATH [--registry-path PATH]
  python -m polytool research-record-outcome --hypothesis-id ID --claim-ids ID1,ID2
      --outcome {confirmed,contradicted,inconclusive} --reason TEXT [--knowledge-store PATH]

Evidence chain: evidence_doc_ids from the candidate dict flow through unchanged
to the registry JSONL event (source.evidence_doc_ids). This preserves the D-01
provenance requirement defined in the RIS_07 spec.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Build parser
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="research-bridge",
        description="RIS v1 CLI bridge: hypothesis registration and validation feedback.",
    )
    sub = parser.add_subparsers(dest="subcommand", metavar="SUBCOMMAND")
    sub.required = True

    # ------------------------------------------------------------------
    # register-hypothesis
    # ------------------------------------------------------------------
    reg = sub.add_parser(
        "register-hypothesis",
        help="Register a research hypothesis candidate in the JSONL registry.",
    )
    src = reg.add_mutually_exclusive_group()
    src.add_argument(
        "--candidate-json",
        dest="candidate_json",
        metavar="PATH",
        help="Path to a JSON file containing the candidate dict.",
    )
    src.add_argument(
        "--candidate-json-string",
        dest="candidate_json_string",
        metavar="STR",
        help="Raw JSON string containing the candidate dict.",
    )
    reg.add_argument(
        "--registry-path",
        dest="registry_path",
        default="kb/research/hypothesis_registry.jsonl",
        metavar="PATH",
        help="Path to the JSONL registry file (default: kb/research/hypothesis_registry.jsonl).",
    )

    # ------------------------------------------------------------------
    # record-outcome
    # ------------------------------------------------------------------
    rec = sub.add_parser(
        "record-outcome",
        help="Record a validation outcome for a set of KnowledgeStore claims.",
    )
    rec.add_argument(
        "--hypothesis-id",
        dest="hypothesis_id",
        required=True,
        metavar="ID",
        help="Hypothesis ID (e.g. hyp_<hex>).",
    )
    rec.add_argument(
        "--claim-ids",
        dest="claim_ids",
        default="",
        metavar="ID1,ID2,...",
        help="Comma-separated list of claim IDs to update.",
    )
    rec.add_argument(
        "--claim-id",
        dest="extra_claim_ids",
        action="append",
        default=[],
        metavar="ID",
        help="Additional claim ID (repeatable; merged with --claim-ids).",
    )
    rec.add_argument(
        "--outcome",
        required=True,
        choices=["confirmed", "contradicted", "inconclusive"],
        help="Validation outcome.",
    )
    rec.add_argument(
        "--reason",
        required=True,
        help="Human-readable explanation of the outcome.",
    )

    from packages.polymarket.rag.knowledge_store import DEFAULT_KNOWLEDGE_DB_PATH
    rec.add_argument(
        "--knowledge-store",
        dest="knowledge_store",
        default=str(DEFAULT_KNOWLEDGE_DB_PATH),
        metavar="PATH",
        help=(
            f"Path to KnowledgeStore SQLite DB "
            f"(default: {DEFAULT_KNOWLEDGE_DB_PATH})."
        ),
    )

    return parser


# ---------------------------------------------------------------------------
# KnowledgeStore import (importable by tests for patching)
# ---------------------------------------------------------------------------

from packages.polymarket.rag.knowledge_store import KnowledgeStore  # noqa: E402


# ---------------------------------------------------------------------------
# Subcommand handlers
# ---------------------------------------------------------------------------

def _cmd_register_hypothesis(args: argparse.Namespace) -> int:
    """Handle register-hypothesis subcommand."""
    # Load candidate dict
    if args.candidate_json:
        try:
            path = Path(args.candidate_json)
            raw = path.read_text(encoding="utf-8")
            candidate = json.loads(raw)
        except Exception as exc:
            print(f"Error reading candidate JSON file: {exc}", file=sys.stderr)
            return 1
    elif args.candidate_json_string:
        try:
            candidate = json.loads(args.candidate_json_string)
        except Exception as exc:
            print(f"Error parsing candidate JSON string: {exc}", file=sys.stderr)
            return 1
    else:
        print(
            "Error: either --candidate-json or --candidate-json-string is required.",
            file=sys.stderr,
        )
        return 1

    if not isinstance(candidate, dict):
        print("Error: candidate JSON must be a dict.", file=sys.stderr)
        return 1

    if "name" not in candidate:
        print(
            "Error: candidate dict must contain a 'name' key.",
            file=sys.stderr,
        )
        return 1

    # Register
    try:
        from packages.research.integration.hypothesis_bridge import (
            register_research_hypothesis,
        )
        hyp_id = register_research_hypothesis(
            registry_path=Path(args.registry_path),
            candidate=candidate,
        )
    except Exception as exc:
        print(f"Error registering hypothesis: {exc}", file=sys.stderr)
        return 1

    print(json.dumps({
        "hypothesis_id": hyp_id,
        "registry_path": str(args.registry_path),
        "candidate_name": candidate["name"],
    }))
    return 0


def _cmd_record_outcome(args: argparse.Namespace) -> int:
    """Handle record-outcome subcommand."""
    # Merge and deduplicate claim IDs
    raw_ids = [cid.strip() for cid in args.claim_ids.split(",") if cid.strip()]
    extra_ids = [cid.strip() for cid in args.extra_claim_ids if cid.strip()]
    seen: set[str] = set()
    claim_ids: list[str] = []
    for cid in raw_ids + extra_ids:
        if cid not in seen:
            seen.add(cid)
            claim_ids.append(cid)

    # outcome is already validated by argparse choices
    try:
        store = KnowledgeStore(db_path=args.knowledge_store)
        from packages.research.integration.validation_feedback import (
            record_validation_outcome,
        )
        result = record_validation_outcome(
            store=store,
            hypothesis_id=args.hypothesis_id,
            claim_ids=claim_ids,
            outcome=args.outcome,
            reason=args.reason,
        )
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Error recording outcome: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(result))
    return 0


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main(argv: Optional[list[str]] = None) -> int:
    """Main entrypoint. argv[0] should be the subcommand name when called via
    _FULL_ARGV_COMMANDS in polytool/__main__.py."""
    if argv is None:
        argv = sys.argv[1:]

    # Normalise: if argv[0] is the full polytool command name, strip the
    # "research-" prefix to get the subparser name.
    if argv and argv[0] in ("research-register-hypothesis", "research-record-outcome"):
        argv = [argv[0].replace("research-", "", 1)] + list(argv[1:])

    parser = build_parser()
    args = parser.parse_args(argv)

    if args.subcommand == "register-hypothesis":
        return _cmd_register_hypothesis(args)
    elif args.subcommand == "record-outcome":
        return _cmd_record_outcome(args)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
