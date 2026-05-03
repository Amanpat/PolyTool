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
    queue = _open_queue(args)
    label_store = _open_labels(args)

    all_records = queue.all_records()
    stats = queue.queue_stats(label_store)

    # Build label lookup: candidate_id -> label (last label wins for each ID)
    label_by_id: dict[str, str] = {}
    for lr in label_store.all_labels():
        cid = lr.get("candidate_id", "")
        label_by_id[cid] = lr.get("label", "?")
    queued_ids = {r.get("candidate_id") for r in all_records}
    labeled_ids = set(label_by_id.keys()) & queued_ids

    show_all = getattr(args, "show_all", False)
    records = all_records if show_all else [
        r for r in all_records if r.get("candidate_id") not in labeled_ids
    ]

    if args.output_json:
        out = []
        for r in records:
            annotated = dict(r)
            if show_all:
                cid = r.get("candidate_id", "")
                annotated["label"] = label_by_id.get(cid)
            out.append(annotated)
        print(json.dumps(out, indent=2))
        return 0

    total = stats["total_queued"]
    pending = stats["pending_unlabeled"]

    if not show_all:
        if not records:
            if total:
                print(
                    f"No pending unlabeled items. "
                    f"({total} total queued, all labeled. Use --all to see labeled items.)"
                )
            else:
                print("No items in prefetch review queue.")
            return 0
        print(f"Prefetch review queue — {pending} unlabeled pending item(s)  ({total} total queued)")
    else:
        labeled_count = total - pending
        print(
            f"Prefetch review queue — {total} total item(s)  "
            f"({pending} pending, {labeled_count} labeled)"
        )

    print("")
    for rec in records:
        cid = rec.get("candidate_id", "")
        cid_short = cid[:12]
        title = rec.get("title") or "(no title)"
        score = rec.get("score", 0.0)
        url = rec.get("source_url", "")
        created = rec.get("created_at", "")[:10]
        label_tag = ""
        if show_all:
            lbl = label_by_id.get(cid)
            label_tag = f"  [label={lbl}]" if lbl else "  [pending]"
        print(f"  {cid_short}  score={score:.4f}  [{created}]{label_tag}  {title}")
        if url:
            print(f"           {url}")
    print("")
    if not show_all:
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

    stats = queue.queue_stats(label_store)
    label_counts = label_store.counts()

    if args.output_json:
        print(json.dumps({
            "total_queued": stats["total_queued"],
            "pending_unlabeled": stats["pending_unlabeled"],
            "labeled_total": stats["labeled_total"],
            "labeled_allow": stats["labeled_allow"],
            "labeled_reject": stats["labeled_reject"],
            # Legacy keys kept for backward compat with existing test consumers
            "pending_review_count": stats["total_queued"],
            "label_count": label_counts["total"],
            "allowed_label_count": label_counts["allow"],
            "rejected_label_count": label_counts["reject"],
        }, indent=2))
        return 0

    print(
        f"Prefetch review queue : {stats['total_queued']} total queued  |  "
        f"{stats['pending_unlabeled']} pending unlabeled"
    )
    print(
        f"Labels (in queue)     : {stats['labeled_total']} labeled  |  "
        f"{stats['labeled_allow']} allow  |  {stats['labeled_reject']} reject"
    )
    svm_target = 30
    allow_gap = max(0, svm_target - stats["labeled_allow"])
    reject_gap = max(0, svm_target - stats["labeled_reject"])
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
        help="List items in the prefetch review queue (pending unlabeled only by default).",
    )
    _add_queue_path_arg(list_parser)
    _add_label_path_arg(list_parser)
    _add_json_arg(list_parser)
    list_parser.add_argument(
        "--all",
        dest="show_all",
        action="store_true",
        help="Show all queue items including already-labeled ones.",
    )

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
