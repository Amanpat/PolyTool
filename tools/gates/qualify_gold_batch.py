"""Post-capture qualification tool for Gold tape batches.

Read-only. Accepts batch tape directories, qualifies each tape against
Gate 2 admission rules, computes before/after shortage delta against
the existing corpus, and reports which tapes are ready for Gate 2.

Exit codes:
  0 -- at least one tape in the batch qualifies and reduces a shortage
  1 -- no tape qualifies or no batch dirs provided

Usage:
  python tools/gates/qualify_gold_batch.py --tape-dirs DIR [DIR ...]
      [--tape-roots PATH ...]  # defaults to DEFAULT_TAPE_ROOTS
      [--json]                 # machine-readable JSON output
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from tools.gates.corpus_audit import (
    DEFAULT_MIN_EVENTS,
    DEFAULT_TAPE_ROOTS,
    _BUCKET_QUOTAS,
    _VALID_BUCKETS,
    _detect_bucket,
    _detect_tier,
    _get_events_path,
)
from tools.gates.capture_status import compute_status
from tools.gates.mm_sweep import _count_effective_events, _read_json_object


# ---------------------------------------------------------------------------
# Core qualification function
# ---------------------------------------------------------------------------


def qualify_batch(
    batch_dirs: list[Path],
    tape_roots: list[Path],
    *,
    min_events: int = DEFAULT_MIN_EVENTS,
) -> dict[str, Any]:
    """
    Qualify a batch of newly captured tape directories.

    Logic:
    1. Compute "before" snapshot of existing corpus via compute_status().
    2. For each batch_dir, check admission rules (too_short, no_bucket_label).
    3. Apply per-bucket quota caps accounting for what the corpus already has.
    4. Compute shortage_delta: before vs after for affected buckets.
    5. Build gate2_ready list: QUALIFIED tapes that reduce a real shortage.

    Returns a dict with keys:
      batch_results: list of per-tape dicts
      shortage_delta: {bucket: {before, after, delta}}
      gate2_ready: list of tape_dir paths (strings) ready for Gate 2
      summary: {total_in_batch, qualified, rejected, shortages_reduced}
    """
    # Step 1: Compute "before" corpus snapshot
    before_status = compute_status(tape_roots, min_events=min_events)
    before_buckets = before_status["buckets"]

    # Step 2: Evaluate each batch tape (pre-quota)
    pre_quota_results: list[dict[str, Any]] = []
    seen_canonical: set[str] = set()

    for tape_dir in batch_dirs:
        tape_dir = Path(tape_dir).resolve()
        canonical = str(tape_dir)
        if canonical in seen_canonical:
            continue
        seen_canonical.add(canonical)

        # Check it is a valid tape dir
        events_path = _get_events_path(tape_dir)
        if events_path is None:
            # Skip non-tape dirs with a warning
            print(
                f"WARNING: {tape_dir} has no events.jsonl or silver_events.jsonl — skipped",
                file=sys.stderr,
            )
            continue

        # Read metadata files
        meta = _read_json_object(tape_dir / "meta.json")
        watch_meta = _read_json_object(tape_dir / "watch_meta.json")
        market_meta = _read_json_object(tape_dir / "market_meta.json")
        silver_meta = _read_json_object(tape_dir / "silver_meta.json")

        # Count effective events
        _, _, effective_events = _count_effective_events(events_path)

        # Detect tier
        tier = _detect_tier(tape_dir)

        # Detect bucket
        bucket = _detect_bucket(
            tape_dir,
            meta=meta,
            watch_meta=watch_meta,
            market_meta=market_meta,
            silver_meta=silver_meta,
        )

        # Apply admission rules (pre-quota)
        if effective_events < min_events:
            pre_quota_results.append({
                "tape_dir": canonical,
                "bucket": bucket,
                "tier": tier,
                "effective_events": effective_events,
                "status": "REJECTED",
                "reject_reason": "too_short",
            })
            continue

        if bucket is None or bucket not in _VALID_BUCKETS:
            pre_quota_results.append({
                "tape_dir": canonical,
                "bucket": bucket,
                "tier": tier,
                "effective_events": effective_events,
                "status": "REJECTED",
                "reject_reason": "no_bucket_label",
            })
            continue

        # Pre-quota QUALIFIED — will be subject to quota caps below
        pre_quota_results.append({
            "tape_dir": canonical,
            "bucket": bucket,
            "tier": tier,
            "effective_events": effective_events,
            "status": "QUALIFIED",
            "reject_reason": None,
        })

    # Step 3: Apply per-bucket quota caps accounting for existing corpus
    # Track how many slots remain per bucket
    remaining_slots: dict[str, int] = {}
    for bucket, info in before_buckets.items():
        remaining_slots[bucket] = info["need"]  # need = quota - have (clamped to 0)

    # Separate pre-quota QUALIFIED from already-REJECTED
    pre_accepted = [r for r in pre_quota_results if r["status"] == "QUALIFIED"]
    pre_rejected = [r for r in pre_quota_results if r["status"] == "REJECTED"]

    # Group pre-accepted by bucket
    by_bucket: dict[str, list[dict[str, Any]]] = {}
    for r in pre_accepted:
        b = r["bucket"]
        by_bucket.setdefault(b, []).append(r)

    # Sort each bucket group: Gold first, then by effective_events descending
    def _sort_key(r: dict[str, Any]) -> tuple[int, int]:
        tier_rank = 0 if r["tier"] == "gold" else 1
        return (tier_rank, -r["effective_events"])

    # Track per-bucket counts that will be added from batch
    batch_adds: dict[str, int] = {}  # bucket -> count of QUALIFIED from batch
    final_batch_results: list[dict[str, Any]] = list(pre_rejected)

    for bucket, bucket_candidates in by_bucket.items():
        sorted_candidates = sorted(bucket_candidates, key=_sort_key)
        quota = _BUCKET_QUOTAS.get(bucket, 0)
        # Slots available = min(remaining_slots, quota total remaining after corpus)
        # remaining_slots already accounts for corpus "have"
        slots = remaining_slots.get(bucket, 0)
        batch_quota_used = 0

        for r in sorted_candidates:
            new_r = dict(r)
            if batch_quota_used < slots:
                new_r["status"] = "QUALIFIED"
                new_r["reject_reason"] = None
                batch_quota_used += 1
            else:
                # Check if it would also exceed the absolute quota (even if slots > 0)
                corpus_have = before_buckets.get(bucket, {}).get("have", 0)
                if corpus_have + batch_quota_used >= quota:
                    new_r["status"] = "REJECTED"
                    new_r["reject_reason"] = "over_quota"
                else:
                    # This shouldn't happen if slots is calculated correctly,
                    # but guard anyway
                    new_r["status"] = "REJECTED"
                    new_r["reject_reason"] = "over_quota"
            final_batch_results.append(new_r)

        batch_adds[bucket] = batch_quota_used

    # Step 4: Compute shortage_delta
    shortage_delta: dict[str, dict[str, int]] = {}
    all_buckets_in_batch = set(by_bucket.keys()) | {r["bucket"] for r in pre_rejected if r["bucket"]}

    for bucket in _VALID_BUCKETS:
        if bucket not in all_buckets_in_batch and batch_adds.get(bucket, 0) == 0:
            continue

        before_need = before_buckets.get(bucket, {}).get("need", 0)
        added = batch_adds.get(bucket, 0)
        after_need = max(0, before_need - added)
        delta = before_need - after_need

        # Include if delta != 0 or batch has tapes in this bucket
        if delta != 0 or bucket in all_buckets_in_batch:
            shortage_delta[bucket] = {
                "before": before_need,
                "after": after_need,
                "delta": delta,
            }

    # Step 5: Build gate2_ready list — QUALIFIED tapes that reduce a real shortage
    gate2_ready: list[str] = []
    for r in final_batch_results:
        if r["status"] == "QUALIFIED":
            bucket = r["bucket"]
            # Only include if this bucket had a shortage before
            if shortage_delta.get(bucket, {}).get("delta", 0) > 0:
                gate2_ready.append(r["tape_dir"])

    # Step 6: Build summary
    qualified_count = sum(1 for r in final_batch_results if r["status"] == "QUALIFIED")
    rejected_count = sum(1 for r in final_batch_results if r["status"] == "REJECTED")
    shortages_reduced = sum(
        1 for d in shortage_delta.values() if d["delta"] > 0
    )

    return {
        "batch_results": final_batch_results,
        "shortage_delta": shortage_delta,
        "gate2_ready": gate2_ready,
        "summary": {
            "total_in_batch": len(final_batch_results),
            "qualified": qualified_count,
            "rejected": rejected_count,
            "shortages_reduced": shortages_reduced,
        },
    }


# ---------------------------------------------------------------------------
# Output formatters
# ---------------------------------------------------------------------------


def _print_human_readable(result: dict[str, Any]) -> None:
    """Print a human-readable qualification report."""
    print("=== Batch Qualification Report ===")
    print()

    # Per-tape results
    print("Per-tape results:")
    for r in result["batch_results"]:
        status_tag = f"[{r['status']}]"
        bucket = r.get("bucket") or "unknown"
        tier = r.get("tier") or "unknown"
        events = r.get("effective_events", 0)
        tape_path = r["tape_dir"]
        if r["status"] == "REJECTED":
            reason = r.get("reject_reason") or "unknown"
            print(
                f"  {status_tag:<12} {tape_path}  bucket={bucket}  "
                f"tier={tier}  events={events}  reason={reason}"
            )
        else:
            print(
                f"  {status_tag:<12} {tape_path}  bucket={bucket}  "
                f"tier={tier}  events={events}"
            )

    print()

    # Shortage delta
    shortage_delta = result["shortage_delta"]
    if shortage_delta:
        print("Shortage delta:")
        print(f"  {'Bucket':<18}  {'Before':>6}  {'After':>5}  {'Delta':>5}")
        print(f"  {'-'*18}  {'------':>6}  {'-----':>5}  {'-----':>5}")
        for bucket in sorted(shortage_delta.keys()):
            d = shortage_delta[bucket]
            print(
                f"  {bucket:<18}  {d['before']:>6}  {d['after']:>5}  {d['delta']:>5}"
            )
        print()

    # Summary
    summary = result["summary"]
    shortages_reduced = summary["shortages_reduced"]
    print(
        f"Summary: {summary['qualified']} qualified, {summary['rejected']} rejected, "
        f"{shortages_reduced} bucket shortage{'s' if shortages_reduced != 1 else ''} reduced"
    )
    print()

    # Gate 2 ready list
    gate2_ready = result["gate2_ready"]
    if gate2_ready:
        print("Gate 2 ready tapes (feed to corpus_audit.py):")
        for path in gate2_ready:
            print(f"  {path}")
    else:
        print("No tapes in this batch qualify for Gate 2.")


def _print_json_output(result: dict[str, Any]) -> None:
    """Print machine-readable JSON."""
    print(json.dumps(result, indent=2))


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    """Main entry point. Returns 0 if at least one tape qualifies, 1 otherwise."""
    parser = argparse.ArgumentParser(
        description=(
            "Post-capture batch qualification tool for Gold tapes. "
            "Read-only — never writes files or mutates manifests."
        )
    )
    parser.add_argument(
        "--tape-dirs",
        dest="tape_dirs",
        nargs="+",
        metavar="DIR",
        required=True,
        help="One or more batch tape directories to qualify.",
    )
    parser.add_argument(
        "--tape-roots",
        dest="tape_roots",
        action="append",
        metavar="PATH",
        default=None,
        help=(
            "Existing corpus tape root directory (repeatable, for baseline comparison). "
            f"Default: {', '.join(DEFAULT_TAPE_ROOTS)}"
        ),
    )
    parser.add_argument(
        "--min-events",
        type=int,
        default=DEFAULT_MIN_EVENTS,
        metavar="INT",
        help=f"Minimum effective_events per tape. Default: {DEFAULT_MIN_EVENTS}",
    )
    parser.add_argument(
        "--json",
        dest="json_output",
        action="store_true",
        default=False,
        help="Emit machine-readable JSON instead of human-readable output.",
    )

    args = parser.parse_args(argv)

    # Validate --tape-dirs non-empty (argparse nargs="+" ensures at least 1)
    if not args.tape_dirs:
        print(
            "ERROR: --tape-dirs requires at least one directory path.",
            file=sys.stderr,
        )
        parser.print_usage(sys.stderr)
        return 1

    # Resolve tape roots
    tape_root_strs = args.tape_roots if args.tape_roots else DEFAULT_TAPE_ROOTS
    tape_roots = [
        (Path(r) if Path(r).is_absolute() else _REPO_ROOT / r)
        for r in tape_root_strs
    ]

    # Resolve batch dirs
    batch_dirs = [
        (Path(d) if Path(d).is_absolute() else _REPO_ROOT / d)
        for d in args.tape_dirs
    ]

    result = qualify_batch(batch_dirs, tape_roots, min_events=args.min_events)

    if args.json_output:
        _print_json_output(result)
    else:
        _print_human_readable(result)

    # Exit 0 if at least one tape qualifies and reduces a shortage
    return 0 if result["summary"]["qualified"] > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
