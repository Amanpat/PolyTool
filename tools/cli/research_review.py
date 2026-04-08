"""CLI entrypoint for the RIS Phase 2 review queue.

Scores in this queue classify ingestion/research usefulness only.
They are not trading recommendations.

Usage:
  python -m polytool research-review list
  python -m polytool research-review list --status all --json
  python -m polytool research-review inspect <REVIEW_ITEM_ID>
  python -m polytool research-review accept <REVIEW_ITEM_ID> --by analyst --notes "Reviewed and approved"
  python -m polytool research-review reject <REVIEW_ITEM_ID> --by analyst --notes "Low usefulness"
  python -m polytool research-review defer <REVIEW_ITEM_ID> --by analyst --notes "Need more context"
"""

from __future__ import annotations

import argparse
import getpass
import json
import sys


_ALL_STATUSES = ("pending", "deferred", "accepted", "rejected")
_STATUS_CHOICES = _ALL_STATUSES + ("unresolved", "all")
_ACTION_COMMANDS = frozenset({"accept", "reject", "defer"})
_ACTION_PAST_TENSE = {"accept": "accepted", "reject": "rejected", "defer": "deferred"}


def _default_actor() -> str:
    try:
        return getpass.getuser()
    except Exception:
        return "unknown"


def _add_common_db_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--db",
        metavar="PATH",
        default=None,
        help="Override KnowledgeStore SQLite path (default: kb/rag/knowledge/knowledge.sqlite3)",
    )


def _add_common_json_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--json",
        dest="output_json",
        action="store_true",
        help="Output raw JSON instead of human-readable text.",
    )


def _parse_metadata_json(raw: str | None) -> dict | None:
    if raw is None:
        return None
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid --metadata-json payload: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError("--metadata-json must decode to a JSON object")
    return value


def _resolve_status_filter(raw_status: str) -> list[str]:
    if raw_status == "unresolved":
        return ["pending", "deferred"]
    if raw_status == "all":
        return list(_ALL_STATUSES)
    return [raw_status]


def _open_store(db_path: str | None):
    from packages.polymarket.rag.knowledge_store import KnowledgeStore

    if db_path:
        return KnowledgeStore(db_path)
    return KnowledgeStore()


def _print_item_summary(item: dict) -> None:
    short_id = item["id"][:12]
    gate = item.get("gate") or "-"
    weighted = (
        "-"
        if item.get("weighted_score") is None
        else f"{float(item['weighted_score']):.2f}"
    )
    simple_sum = (
        "-"
        if item.get("simple_sum_score") is None
        else str(item["simple_sum_score"])
    )
    source_family = item.get("source_family") or "-"
    title = item.get("title") or "-"
    print(
        f"{short_id}  {item['status']:<8}  gate={gate:<6}  "
        f"weighted={weighted:<5}  sum={simple_sum:<4}  "
        f"family={source_family:<12}  title={title}"
    )


def _print_item_detail(item: dict) -> None:
    print(f"id: {item['id']}")
    print(f"status: {item['status']}")
    print(f"gate: {item.get('gate') or '-'}")
    print(f"title: {item.get('title') or '-'}")
    print(f"source_document_id: {item.get('source_document_id') or '-'}")
    print(f"source_metadata_ref: {item.get('source_metadata_ref') or '-'}")
    print(f"source_url: {item.get('source_url') or '-'}")
    print(f"source_type: {item.get('source_type') or '-'}")
    print(f"source_family: {item.get('source_family') or '-'}")
    print(f"provider_name: {item.get('provider_name') or '-'}")
    print(f"eval_model: {item.get('eval_model') or '-'}")
    print(f"weighted_score: {item.get('weighted_score')}")
    print(f"simple_sum_score: {item.get('simple_sum_score')}")
    print(f"created_at: {item.get('created_at')}")
    print(f"updated_at: {item.get('updated_at')}")
    print(f"final_decision: {item.get('final_decision') or '-'}")
    print(f"final_decision_at: {item.get('final_decision_at') or '-'}")
    print(f"final_decision_by: {item.get('final_decision_by') or '-'}")
    print(f"final_decision_notes: {item.get('final_decision_notes') or '-'}")
    print(
        "final_decision_metadata: "
        f"{json.dumps(item.get('final_decision_metadata'), sort_keys=True)}"
    )
    print("gate_snapshot:")
    print(json.dumps(item.get("gate_snapshot"), indent=2, sort_keys=True))
    print("history:")
    history = item.get("history", [])
    if not history:
        print("  (none)")
        return
    for entry in history:
        print(
            f"  {entry['created_at']}  action={entry['action']}  "
            f"{entry.get('previous_status') or '-'} -> {entry['new_status']}  "
            f"actor={entry.get('actor') or '-'}  notes={entry.get('notes') or '-'}"
        )


def _cmd_list(args: argparse.Namespace) -> int:
    try:
        statuses = _resolve_status_filter(args.status)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    store = _open_store(args.db)
    try:
        items = store.list_pending_reviews(statuses=statuses, limit=args.limit)
    finally:
        store.close()

    if args.output_json:
        print(json.dumps(items, indent=2, sort_keys=True))
        return 0

    if not items:
        print("No review items found.")
        return 0

    for item in items:
        _print_item_summary(item)
    return 0


def _cmd_inspect(args: argparse.Namespace) -> int:
    store = _open_store(args.db)
    try:
        item = store.get_pending_review(args.review_item_id, include_history=True)
    finally:
        store.close()

    if item is None:
        print(f"Error: review item not found: {args.review_item_id}", file=sys.stderr)
        return 1

    if args.output_json:
        print(json.dumps(item, indent=2, sort_keys=True))
    else:
        _print_item_detail(item)
    return 0


def _cmd_resolve(args: argparse.Namespace) -> int:
    try:
        metadata = _parse_metadata_json(args.metadata_json)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    store = _open_store(args.db)
    try:
        item = store.resolve_pending_review(
            args.review_item_id,
            action=args.subcommand,
            actor=args.actor,
            notes=args.notes,
            action_metadata=metadata,
        )
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        store.close()
        return 1
    finally:
        try:
            store.close()
        except Exception:
            pass

    if args.output_json:
        print(json.dumps(item, indent=2, sort_keys=True))
    else:
        print(
            f"{_ACTION_PAST_TENSE[args.subcommand]} review item {item['id']} "
            f"(status={item['status']})"
        )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="research-review",
        description=(
            "Inspect and resolve the RIS review queue. "
            "Scores classify ingestion/research usefulness only."
        ),
    )
    subparsers = parser.add_subparsers(dest="subcommand", metavar="SUBCOMMAND")

    list_parser = subparsers.add_parser(
        "list",
        help="List queued review items.",
    )
    list_parser.add_argument(
        "--status",
        choices=_STATUS_CHOICES,
        default="unresolved",
        help="Queue status filter (default: unresolved = pending + deferred).",
    )
    list_parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum number of items to return.",
    )
    _add_common_db_arg(list_parser)
    _add_common_json_arg(list_parser)

    inspect_parser = subparsers.add_parser(
        "inspect",
        help="Inspect one review item with audit history.",
    )
    inspect_parser.add_argument("review_item_id", metavar="REVIEW_ITEM_ID")
    _add_common_db_arg(inspect_parser)
    _add_common_json_arg(inspect_parser)

    for action in ("accept", "reject", "defer"):
        action_parser = subparsers.add_parser(
            action,
            help=f"{action.title()} one review item.",
        )
        action_parser.add_argument("review_item_id", metavar="REVIEW_ITEM_ID")
        action_parser.add_argument(
            "--by",
            dest="actor",
            default=_default_actor(),
            help=f"Operator identity recorded in audit history (default: {_default_actor()}).",
        )
        action_parser.add_argument(
            "--notes",
            default=None,
            help="Free-form operator notes for this action.",
        )
        action_parser.add_argument(
            "--metadata-json",
            dest="metadata_json",
            default=None,
            help="Optional JSON object with structured audit metadata.",
        )
        _add_common_db_arg(action_parser)
        _add_common_json_arg(action_parser)

    args = parser.parse_args(argv)

    if not args.subcommand:
        parser.print_help()
        return 1

    if args.subcommand == "list":
        return _cmd_list(args)
    if args.subcommand == "inspect":
        return _cmd_inspect(args)
    if args.subcommand in _ACTION_COMMANDS:
        return _cmd_resolve(args)

    parser.print_help()
    return 1
