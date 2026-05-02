"""CLI for managing the L3 prefetch relevance filter review queue and label store.

The review queue holds REVIEW-decision candidates that were held out of
ingestion by --prefetch-filter-mode hold-review. Labeling items here
accumulates training examples for a future SVM classifier (L3 v1).

Usage:
  python -m polytool research-prefetch-review list [--json] [--queue-path PATH]
  python -m polytool research-prefetch-review label <CANDIDATE_ID> allow|reject [--note TEXT]
  python -m polytool research-prefetch-review counts [--json]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


_REPO_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_QUEUE_PATH = (
    _REPO_ROOT / "artifacts" / "research" / "prefetch_review_queue" / "review_queue.jsonl"
)
_DEFAULT_LABEL_PATH = (
    _REPO_ROOT / "artifacts" / "research" / "svm_filter_labels" / "labels.jsonl"
)


def _add_queue_path_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--queue-path",
        dest="queue_path",
        metavar="PATH",
        default=None,
        help="Override review queue JSONL path.",
    )


def _add_label_path_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--label-path",
        dest="label_path",
        metavar="PATH",
        default=None,
        help="Override label store JSONL path.",
    )


def _add_json_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--json",
        dest="output_json",
        action="store_true",
        help="Output raw JSON instead of human-readable text.",
    )


def _open_queue(args: argparse.Namespace):
    from packages.research.relevance_filter.queue_store import ReviewQueueStore
    path = Path(args.queue_path) if getattr(args, "queue_path", None) else _DEFAULT_QUEUE_PATH
    return ReviewQueueStore(path)


def _open_labels(args: argparse.Namespace):
    from packages.research.relevance_filter.queue_store import LabelStore
    path = Path(args.label_path) if getattr(args, "label_path", None) else _DEFAULT_LABEL_PATH
    return LabelStore(path)


# ---------------------------------------------------------------------------
# Subcommand: list
# ---------------------------------------------------------------------------

def _cmd_list(args: argparse.Namespace) -> int:
    store = _open_queue(args)
    records = store.all_records()

    if args.output_json:
        print(json.dumps(records, indent=2))
        return 0

    if not records:
        print("No items in prefetch review queue.")
        return 0

    print(f"Prefetch review queue — {len(records)} item(s)")
    print("")
    for rec in records:
        cid = rec.get("candidate_id", "")[:12]
        title = rec.get("title") or "(no title)"
        score = rec.get("score", 0.0)
        url = rec.get("source_url", "")
        created = rec.get("created_at", "")[:10]
        print(f"  {cid}  score={score:.4f}  [{created}]  {title}")
        if url:
            print(f"           {url}")
    print("")
    print("Use 'research-prefetch-review label <CANDIDATE_ID> allow|reject' to label an item.")
    return 0


# ---------------------------------------------------------------------------
# Subcommand: label
# ---------------------------------------------------------------------------

def _cmd_label(args: argparse.Namespace) -> int:
    candidate_id = args.candidate_id
    label = args.label

    # Find matching queue record for title/URL
    queue = _open_queue(args)
    records = queue.all_records()
    matched = [r for r in records if r.get("candidate_id", "").startswith(candidate_id)]

    if not matched:
        print(
            f"Error: no queue record found with candidate_id starting with {candidate_id!r}.",
            file=sys.stderr,
        )
        print("Run 'research-prefetch-review list' to see available IDs.", file=sys.stderr)
        return 1

    if len(matched) > 1:
        print(
            f"Error: ambiguous prefix {candidate_id!r} matches {len(matched)} records. "
            "Use more characters.",
            file=sys.stderr,
        )
        return 1

    rec = matched[0]
    full_id = rec["candidate_id"]
    source_url = rec.get("source_url", "")
    title = rec.get("title", "")

    label_store = _open_labels(args)
    label_record = label_store.append_label(
        candidate_id=full_id,
        source_url=source_url,
        title=title,
        label=label,
        note=getattr(args, "note", "") or "",
    )

    if args.output_json:
        print(json.dumps(label_record, indent=2))
    else:
        print(f"Labeled: {full_id[:12]}  label={label}  title={title or source_url}")
        counts = label_store.counts()
        print(f"Label store totals — total={counts['total']}  allow={counts['allow']}  reject={counts['reject']}")

    return 0


# ---------------------------------------------------------------------------
# Subcommand: counts
# ---------------------------------------------------------------------------

def _cmd_counts(args: argparse.Namespace) -> int:
    queue = _open_queue(args)
    label_store = _open_labels(args)

    pending = queue.pending_count()
    counts = label_store.counts()

    if args.output_json:
        print(json.dumps({
            "pending_review_count": pending,
            "label_count": counts["total"],
            "allowed_label_count": counts["allow"],
            "rejected_label_count": counts["reject"],
        }, indent=2))
        return 0

    print(f"Prefetch review queue : {pending} item(s) pending")
    print(f"Label store           : {counts['total']} total  |  {counts['allow']} allow  |  {counts['reject']} reject")
    svm_target = 30
    allow_gap = max(0, svm_target - counts["allow"])
    reject_gap = max(0, svm_target - counts["reject"])
    if allow_gap or reject_gap:
        print(f"SVM trigger (>={svm_target} each) : need {allow_gap} more allow, {reject_gap} more reject")
    else:
        print(f"SVM trigger (>={svm_target} each) : threshold met — ready for L3 v1 training")
    return 0


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="research-prefetch-review",
        description=(
            "Manage the L3 prefetch relevance filter review queue and label store. "
            "Labeling items here accumulates SVM training data for L3 v1."
        ),
    )
    subparsers = parser.add_subparsers(dest="subcommand", metavar="SUBCOMMAND")

    # --- list ---
    list_parser = subparsers.add_parser(
        "list",
        help="List all items in the prefetch review queue.",
    )
    _add_queue_path_arg(list_parser)
    _add_json_arg(list_parser)

    # --- label ---
    label_parser = subparsers.add_parser(
        "label",
        help="Label a queue item allow or reject (appends to label store).",
    )
    label_parser.add_argument(
        "candidate_id",
        metavar="CANDIDATE_ID",
        help="Full candidate_id or unambiguous prefix (from 'list' output).",
    )
    label_parser.add_argument(
        "label",
        metavar="LABEL",
        choices=["allow", "reject"],
        help="Label: 'allow' or 'reject'.",
    )
    label_parser.add_argument(
        "--note",
        default="",
        help="Optional operator note.",
    )
    _add_queue_path_arg(label_parser)
    _add_label_path_arg(label_parser)
    _add_json_arg(label_parser)

    # --- counts ---
    counts_parser = subparsers.add_parser(
        "counts",
        help="Show queue size and label store counts.",
    )
    _add_queue_path_arg(counts_parser)
    _add_label_path_arg(counts_parser)
    _add_json_arg(counts_parser)

    args = parser.parse_args(argv)

    if not args.subcommand:
        parser.print_help()
        return 1

    if args.subcommand == "list":
        return _cmd_list(args)
    if args.subcommand == "label":
        return _cmd_label(args)
    if args.subcommand == "counts":
        return _cmd_counts(args)

    parser.print_help()
    return 1
