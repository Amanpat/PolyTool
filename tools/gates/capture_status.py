"""Read-only corpus quota status helper for Gate 2.

Prints a compact shortage table showing how many tapes are needed per bucket.
Never writes any files. Never mutates any state.

Exit codes:
  0 -- corpus complete (all bucket quotas satisfied)
  1 -- shortage exists

Usage:
  python tools/gates/capture_status.py [--tape-roots PATH ...] [--json]
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
    _TOTAL_QUOTA,
    _discover_tape_dirs,
    audit_tape_candidates,
)


# ---------------------------------------------------------------------------
# Core status computation
# ---------------------------------------------------------------------------


def compute_status(
    tape_roots: list[Path],
    *,
    min_events: int = DEFAULT_MIN_EVENTS,
) -> dict[str, Any]:
    """
    Scan tape roots and compute per-bucket quota status.

    Returns a dict with keys:
      total_have, total_quota, total_need, complete, buckets

    Where buckets is a dict of:
      {bucket: {"quota": Q, "have": H, "need": N, "gold": G, "silver": S}}
    """
    # Discover all tape dirs across all roots
    all_tape_dirs: list[Path] = []
    for root in tape_roots:
        all_tape_dirs.extend(_discover_tape_dirs(root))

    # Audit candidates (applies quota caps)
    all_results = audit_tape_candidates(all_tape_dirs, min_events=min_events)

    # Build per-bucket summary from ACCEPTED tapes only
    accepted = [r for r in all_results if r["status"] == "ACCEPTED"]

    # Initialize all buckets with zero counts
    buckets: dict[str, dict[str, Any]] = {}
    for bucket, quota in _BUCKET_QUOTAS.items():
        buckets[bucket] = {
            "quota": quota,
            "have": 0,
            "need": quota,  # will be updated below
            "gold": 0,
            "silver": 0,
        }

    # Tally accepted tapes
    for r in accepted:
        bucket = r.get("bucket")
        if bucket not in buckets:
            continue
        buckets[bucket]["have"] += 1
        tier = r.get("tier", "unknown")
        if tier == "gold":
            buckets[bucket]["gold"] += 1
        elif tier == "silver":
            buckets[bucket]["silver"] += 1

    # Compute need per bucket
    for bucket, info in buckets.items():
        info["need"] = max(0, info["quota"] - info["have"])

    total_have = sum(info["have"] for info in buckets.values())
    total_need = sum(info["need"] for info in buckets.values())
    complete = total_need == 0

    return {
        "total_have": total_have,
        "total_quota": _TOTAL_QUOTA,
        "total_need": total_need,
        "complete": complete,
        "buckets": buckets,
    }


# ---------------------------------------------------------------------------
# Output formatters
# ---------------------------------------------------------------------------


def _print_table(status: dict[str, Any]) -> None:
    """Print a compact human-readable table to stdout."""
    total_have = status["total_have"]
    total_quota = status["total_quota"]
    total_need = status["total_need"]
    complete = status["complete"]

    if complete:
        print(f"Corpus status: {total_have} / {total_quota} tapes qualified — COMPLETE")
        print(
            "Run: python tools/gates/close_mm_sweep_gate.py"
            " --benchmark-manifest config/recovery_corpus_v1.tape_manifest"
            " --out artifacts/gates/gate2_sweep"
        )
        return

    print(f"Corpus status: {total_have} / {total_quota} tapes qualified ({total_need} needed)")
    print()

    # Table header
    col_bucket = 15
    col_num = 6
    header = (
        f"{'Bucket':<{col_bucket}}"
        f"  {'Quota':>{col_num}}"
        f"  {'Have':>{col_num}}"
        f"  {'Need':>{col_num}}"
        f"  {'Gold':>{col_num}}"
        f"  {'Silver':>{col_num}}"
    )
    sep = "-" * col_bucket + "  " + ("  ".join(["-" * col_num] * 5))
    print(header)
    print(sep)

    buckets = status["buckets"]
    # Print in a consistent order
    bucket_order = ["sports", "politics", "crypto", "new_market", "near_resolution"]
    total_gold = 0
    total_silver = 0

    for bucket in bucket_order:
        if bucket not in buckets:
            continue
        info = buckets[bucket]
        print(
            f"{bucket:<{col_bucket}}"
            f"  {info['quota']:>{col_num}}"
            f"  {info['have']:>{col_num}}"
            f"  {info['need']:>{col_num}}"
            f"  {info['gold']:>{col_num}}"
            f"  {info['silver']:>{col_num}}"
        )
        total_gold += info["gold"]
        total_silver += info["silver"]

    print(sep)
    print(
        f"{'Total':<{col_bucket}}"
        f"  {total_quota:>{col_num}}"
        f"  {total_have:>{col_num}}"
        f"  {total_need:>{col_num}}"
        f"  {total_gold:>{col_num}}"
        f"  {total_silver:>{col_num}}"
    )
    print()
    print(
        "Next: run corpus_audit.py after capturing tapes."
        " Gate 2 unblocks at exit 0."
    )


def _print_json(status: dict[str, Any]) -> None:
    """Print machine-readable JSON to stdout."""
    print(json.dumps(status, indent=2))


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    """Main entry point. Returns int exit code (0=complete, 1=shortage)."""
    parser = argparse.ArgumentParser(
        description=(
            "Read-only corpus quota status helper. Prints current shortage per bucket. "
            "Never writes any file."
        )
    )
    parser.add_argument(
        "--tape-roots",
        dest="tape_roots",
        action="append",
        metavar="PATH",
        default=None,
        help=(
            "Tape root directory to scan (repeatable). "
            f"Default: {', '.join(DEFAULT_TAPE_ROOTS)}"
        ),
    )
    parser.add_argument(
        "--json",
        dest="json_output",
        action="store_true",
        default=False,
        help="Emit machine-readable JSON instead of a human-readable table.",
    )

    args = parser.parse_args(argv)

    tape_root_strs = args.tape_roots if args.tape_roots else DEFAULT_TAPE_ROOTS
    tape_roots = [
        (Path(r) if Path(r).is_absolute() else _REPO_ROOT / r)
        for r in tape_root_strs
    ]

    status = compute_status(tape_roots)

    if args.json_output:
        _print_json(status)
    else:
        _print_table(status)

    return 0 if status["complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
