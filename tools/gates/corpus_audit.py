"""Recovery corpus audit tool for Gate 2.

Scans tape inventory, applies admission rules from SPEC-phase1b-corpus-recovery-v1,
and either writes a qualified recovery manifest or an exact shortage report.

Exit codes:
  0 -- corpus qualifies; config/recovery_corpus_v1.tape_manifest written
  1 -- corpus insufficient; artifacts/corpus_audit/shortage_report.md written
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from tools.gates.mm_sweep import _count_effective_events, _read_json_object

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_VALID_BUCKETS = frozenset({"politics", "sports", "crypto", "near_resolution", "new_market"})
_BUCKET_QUOTAS: dict[str, int] = {
    "politics": 10,
    "sports": 15,
    "crypto": 10,
    "near_resolution": 10,
    "new_market": 5,
}
_TOTAL_QUOTA = sum(_BUCKET_QUOTAS.values())  # 50

DEFAULT_TAPE_ROOTS: list[str] = [
    "artifacts/simtrader/tapes",
    "artifacts/silver",
    "artifacts/tapes",
]
DEFAULT_OUT_DIR = "artifacts/corpus_audit"
DEFAULT_MIN_EVENTS = 50
DEFAULT_MANIFEST_OUT = "config/recovery_corpus_v1.tape_manifest"


# ---------------------------------------------------------------------------
# TapeAuditResult
# ---------------------------------------------------------------------------


@dataclass
class TapeAuditResult:
    """Admission result for a single tape candidate."""

    tape_dir: str           # canonical path string
    events_path: str        # relative events.jsonl path
    bucket: str | None
    tier: str               # "gold" | "silver" | "unknown"
    effective_events: int
    status: str             # "ACCEPTED" | "REJECTED"
    reject_reason: str | None  # None when ACCEPTED


# ---------------------------------------------------------------------------
# Tier detection (reused from mm_sweep_diagnostic logic)
# ---------------------------------------------------------------------------


def _detect_tier(tape_dir: Path) -> str:
    """Infer tape tier from metadata files present in tape_dir."""
    watch_meta_path = tape_dir / "watch_meta.json"
    if watch_meta_path.exists():
        return "gold"

    meta_path = tape_dir / "meta.json"
    if meta_path.exists():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8-sig"))
            if isinstance(meta, dict):
                recorded_by = str(meta.get("recorded_by", "")).strip().lower()
                if recorded_by in ("shadow", "tape_recorder"):
                    return "gold"
        except Exception:  # noqa: BLE001
            pass

    silver_meta_path = tape_dir / "silver_meta.json"
    if silver_meta_path.exists():
        return "silver"

    return "unknown"


# ---------------------------------------------------------------------------
# Bucket detection
# ---------------------------------------------------------------------------


def _detect_bucket(
    tape_dir: Path,
    *,
    meta: dict[str, Any],
    watch_meta: dict[str, Any],
    market_meta: dict[str, Any],
    silver_meta: dict[str, Any],
) -> str | None:
    """Extract bucket label from tape metadata, in priority order."""
    # Priority 1: watch_meta["bucket"] (Gold tapes set this explicitly)
    bucket = _first_text(watch_meta.get("bucket"))
    if bucket:
        return bucket.lower()

    # Priority 2: market_meta["benchmark_bucket"] (Silver tapes with backfilled meta)
    bucket = _first_text(market_meta.get("benchmark_bucket"))
    if bucket:
        return bucket.lower()

    # Priority 3: market_meta["category"]
    bucket = _first_text(market_meta.get("category"))
    if bucket:
        return bucket.lower()

    # Priority 4: meta["regime"] or meta["final_regime"] (some older tapes)
    for key in ("final_regime", "regime"):
        bucket = _first_text(meta.get(key))
        if bucket:
            return bucket.lower()

    # Priority 5: silver_meta has no bucket field typically
    # Priority 6: directory path inference — not attempted here to avoid false positives

    return None


# ---------------------------------------------------------------------------
# Discover all tape directories under a root (handles nested structures)
# ---------------------------------------------------------------------------


def _discover_tape_dirs(root: Path) -> list[Path]:
    """
    Discover all directories containing events.jsonl (or silver_events.jsonl)
    under root, including nested structures like artifacts/silver/{id}/{timestamp}/.
    """
    if not root.exists() or not root.is_dir():
        return []

    found: list[Path] = []

    def _walk(directory: Path, depth: int = 0) -> None:
        if depth > 4:
            return
        # Check if this directory itself is a tape dir
        if (directory / "events.jsonl").exists() or (directory / "silver_events.jsonl").exists():
            found.append(directory)
            return  # Don't descend further into a tape dir
        # Otherwise, recurse into subdirectories
        try:
            for child in sorted(directory.iterdir()):
                if child.is_dir():
                    _walk(child, depth + 1)
        except PermissionError:
            pass

    _walk(root)
    return found


# ---------------------------------------------------------------------------
# Discover events.jsonl path for a tape dir
# ---------------------------------------------------------------------------


def _get_events_path(tape_dir: Path) -> Path | None:
    """Return the events.jsonl path for a tape dir (handles silver naming)."""
    for name in ("events.jsonl", "silver_events.jsonl"):
        p = tape_dir / name
        if p.exists():
            return p
    return None


# ---------------------------------------------------------------------------
# Core audit function
# ---------------------------------------------------------------------------


def audit_tape_candidates(
    tape_dirs: list[Path],
    *,
    min_events: int = DEFAULT_MIN_EVENTS,
) -> list[dict[str, Any]]:
    """
    Evaluate each tape dir against admission rules including quota caps.

    Returns a list of dicts with keys:
      tape_dir, events_path, bucket, tier, effective_events, status, reject_reason

    Applies all rules in order:
    1. effective_events < min_events -> REJECTED / too_short
    2. no valid bucket label        -> REJECTED / no_bucket_label
    3. over per-bucket quota        -> REJECTED / over_quota
    4. otherwise                    -> ACCEPTED
    """
    seen_canonical: set[str] = set()
    pre_quota: list[dict[str, Any]] = []

    for tape_dir in tape_dirs:
        tape_dir = tape_dir.resolve()

        # Deduplicate
        canonical = str(tape_dir)
        if canonical in seen_canonical:
            continue
        seen_canonical.add(canonical)

        # Find events file
        events_path = _get_events_path(tape_dir)
        if events_path is None:
            continue  # Not a valid tape dir

        # Read metadata
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
            pre_quota.append({
                "tape_dir": str(tape_dir),
                "events_path": str(events_path),
                "bucket": bucket,
                "tier": tier,
                "effective_events": effective_events,
                "status": "REJECTED",
                "reject_reason": "too_short",
            })
            continue

        if bucket is None or bucket not in _VALID_BUCKETS:
            pre_quota.append({
                "tape_dir": str(tape_dir),
                "events_path": str(events_path),
                "bucket": bucket,
                "tier": tier,
                "effective_events": effective_events,
                "status": "REJECTED",
                "reject_reason": "no_bucket_label",
            })
            continue

        # Pre-quota ACCEPTED — will be subject to quota caps below
        pre_quota.append({
            "tape_dir": str(tape_dir),
            "events_path": str(events_path),
            "bucket": bucket,
            "tier": tier,
            "effective_events": effective_events,
            "status": "ACCEPTED",
            "reject_reason": None,
        })

    # Apply quota caps
    return _apply_quota_caps(pre_quota)


def _apply_quota_caps(
    candidates: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Apply per-bucket quota caps to the list of pre-quota ACCEPTED candidates.

    Selection preference: Gold over Silver; within same tier, higher effective_events first.
    Excess candidates are marked REJECTED with reason "over_quota".
    Returns a new list with the same items but updated status/reject_reason for over-quota entries.
    """
    # Separate pre-quota ACCEPTED from already-REJECTED
    accepted = [r for r in candidates if r["status"] == "ACCEPTED"]
    rejected = [r for r in candidates if r["status"] == "REJECTED"]

    # Group accepted by bucket
    by_bucket: dict[str, list[dict[str, Any]]] = {}
    for r in accepted:
        bucket = r["bucket"]
        by_bucket.setdefault(bucket, []).append(r)

    # Sort each bucket: Gold first, then by effective_events descending
    def _sort_key(r: dict[str, Any]) -> tuple[int, int]:
        tier_rank = 0 if r["tier"] == "gold" else 1
        return (tier_rank, -r["effective_events"])

    final: list[dict[str, Any]] = list(rejected)

    for bucket, bucket_candidates in by_bucket.items():
        quota = _BUCKET_QUOTAS.get(bucket, 0)
        sorted_candidates = sorted(bucket_candidates, key=_sort_key)
        for idx, r in enumerate(sorted_candidates):
            new_r = dict(r)
            if idx < quota:
                new_r["status"] = "ACCEPTED"
                new_r["reject_reason"] = None
            else:
                new_r["status"] = "REJECTED"
                new_r["reject_reason"] = "over_quota"
            final.append(new_r)

    return final


# ---------------------------------------------------------------------------
# run_corpus_audit — main orchestration function
# ---------------------------------------------------------------------------


def run_corpus_audit(
    *,
    tape_roots: list[Path],
    out_dir: Path,
    min_events: int = DEFAULT_MIN_EVENTS,
    manifest_out: Path,
) -> int:
    """
    Run the full corpus audit.

    Returns 0 if corpus qualifies, 1 if insufficient.
    """
    out_dir.mkdir(parents=True, exist_ok=True)

    # Discover all tape dirs across all roots
    all_tape_dirs: list[Path] = []
    for root in tape_roots:
        all_tape_dirs.extend(_discover_tape_dirs(root))

    # Audit candidates (includes quota caps)
    all_results = audit_tape_candidates(all_tape_dirs, min_events=min_events)

    # Count final accepted
    accepted = [r for r in all_results if r["status"] == "ACCEPTED"]
    total_accepted = len(accepted)

    # Check if all 5 buckets are represented
    accepted_buckets = {r["bucket"] for r in accepted}
    all_buckets_covered = _VALID_BUCKETS.issubset(accepted_buckets)

    qualified = total_accepted >= _TOTAL_QUOTA and all_buckets_covered

    # Print summary to stdout regardless of outcome
    _print_summary(all_results, total_accepted=total_accepted, qualified=qualified)

    if qualified:
        _write_manifest(accepted=accepted, manifest_out=manifest_out)
        _write_audit_report(all_results=all_results, out_dir=out_dir, manifest_out=manifest_out)
        # Remove shortage report if it exists from a prior run
        shortage_path = out_dir / "shortage_report.md"
        if shortage_path.exists():
            shortage_path.unlink()
        return 0
    else:
        _write_shortage_report(all_results=all_results, out_dir=out_dir)
        # Remove audit report if it exists from a prior qualified run
        audit_path = out_dir / "recovery_corpus_audit.md"
        if audit_path.exists():
            audit_path.unlink()
        return 1


# ---------------------------------------------------------------------------
# Output writers
# ---------------------------------------------------------------------------


def _write_manifest(*, accepted: list[dict[str, Any]], manifest_out: Path) -> None:
    """Write the recovery corpus manifest JSON array."""
    manifest_out.parent.mkdir(parents=True, exist_ok=True)

    # Build relative paths from repo root
    events_paths = []
    for r in accepted:
        events_path = Path(r["events_path"])
        try:
            rel = events_path.relative_to(_REPO_ROOT)
            events_paths.append(str(rel).replace("\\", "/"))
        except ValueError:
            events_paths.append(str(events_path).replace("\\", "/"))

    manifest_out.write_text(
        json.dumps(events_paths, indent=2) + "\n", encoding="utf-8"
    )


def _write_audit_report(
    *,
    all_results: list[dict[str, Any]],
    out_dir: Path,
    manifest_out: Path,
) -> None:
    """Write recovery_corpus_audit.md."""
    accepted = [r for r in all_results if r["status"] == "ACCEPTED"]
    rejected = [r for r in all_results if r["status"] == "REJECTED"]

    lines = [
        "# Recovery Corpus Audit Report",
        "",
        "## Per-Tape Results",
        "",
        "| Tape Dir | Bucket | Tier | EffEvents | Status | RejectReason |",
        "|----------|--------|------|----------:|--------|--------------|",
    ]

    for r in all_results:
        tape_name = Path(r["tape_dir"]).name
        bucket = r["bucket"] or "-"
        tier = r["tier"]
        eff = str(r["effective_events"])
        status = r["status"]
        reason = r.get("reject_reason") or "-"
        lines.append(f"| {tape_name} | {bucket} | {tier} | {eff} | {status} | {reason} |")

    # Summary section
    total_scanned = len(all_results)
    total_accepted = len(accepted)
    total_rejected = len(rejected)

    # Reject reason breakdown
    reject_reasons: dict[str, int] = {}
    for r in rejected:
        reason = r.get("reject_reason") or "unknown"
        reject_reasons[reason] = reject_reasons.get(reason, 0) + 1

    # Accepted by bucket/tier
    bucket_tier_counts: dict[str, dict[str, int]] = {}
    for r in accepted:
        bucket = r["bucket"] or "unknown"
        tier = r["tier"]
        bucket_tier_counts.setdefault(bucket, {})
        bucket_tier_counts[bucket][tier] = bucket_tier_counts[bucket].get(tier, 0) + 1

    lines += [
        "",
        "## Summary",
        "",
        f"- **Total scanned:** {total_scanned}",
        f"- **Accepted:** {total_accepted}",
        f"- **Rejected:** {total_rejected}",
        "",
        "### Rejected by Reason",
        "",
    ]
    for reason, count in sorted(reject_reasons.items()):
        lines.append(f"- {reason}: {count}")

    lines += [
        "",
        "### Accepted by Bucket / Tier",
        "",
        "| Bucket | Gold | Silver | Unknown | Total |",
        "|--------|-----:|-------:|--------:|------:|",
    ]
    for bucket in sorted(_VALID_BUCKETS):
        tier_counts = bucket_tier_counts.get(bucket, {})
        gold = tier_counts.get("gold", 0)
        silver = tier_counts.get("silver", 0)
        unknown = tier_counts.get("unknown", 0)
        total = gold + silver + unknown
        lines.append(f"| {bucket} | {gold} | {silver} | {unknown} | {total} |")

    # Try to compute relative manifest path for display
    try:
        rel_manifest = str(manifest_out.resolve().relative_to(_REPO_ROOT)).replace("\\", "/")
    except ValueError:
        rel_manifest = str(manifest_out)

    lines += [
        "",
        f"Qualified manifest written to: {rel_manifest}",
    ]

    report_path = out_dir / "recovery_corpus_audit.md"
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_shortage_report(
    *,
    all_results: list[dict[str, Any]],
    out_dir: Path,
) -> None:
    """Write shortage_report.md."""
    accepted = [r for r in all_results if r["status"] == "ACCEPTED"]
    total_accepted = len(accepted)

    # Count accepted by bucket / tier
    bucket_tier_counts: dict[str, dict[str, int]] = {b: {} for b in _VALID_BUCKETS}
    for r in accepted:
        bucket = r["bucket"]
        if bucket not in _VALID_BUCKETS:
            continue
        tier = r["tier"]
        bucket_tier_counts[bucket][tier] = bucket_tier_counts[bucket].get(tier, 0) + 1

    lines = [
        "# Corpus Shortage Report",
        "",
        f"**Total qualified tapes:** {total_accepted} / {_TOTAL_QUOTA} needed",
        "",
        "## Shortage by Bucket",
        "",
        "| Bucket | Quota | Have | Need | Gold | Silver | Recommended Action |",
        "|--------|------:|-----:|-----:|-----:|-------:|-------------------|",
    ]

    for bucket in sorted(_VALID_BUCKETS):
        quota = _BUCKET_QUOTAS[bucket]
        tier_counts = bucket_tier_counts.get(bucket, {})
        gold = tier_counts.get("gold", 0)
        silver = tier_counts.get("silver", 0)
        have = gold + silver + tier_counts.get("unknown", 0)
        need = max(0, quota - have)
        action = f"Record {need} Gold shadow tapes in {bucket} bucket" if need > 0 else "OK"
        lines.append(f"| {bucket} | {quota} | {have} | {need} | {gold} | {silver} | {action} |")

    lines += [
        "",
        "## Next Steps",
        "",
        "1. Record Gold shadow tapes for the buckets listed above.",
        "   See `docs/runbooks/CORPUS_GOLD_CAPTURE_RUNBOOK.md` for capture instructions.",
        "2. After capturing tapes, re-run corpus_audit to update this report:",
        "   ```",
        "   python tools/gates/corpus_audit.py \\",
        "       --tape-roots artifacts/simtrader/tapes \\",
        "       --tape-roots artifacts/silver \\",
        "       --tape-roots artifacts/tapes \\",
        "       --out-dir artifacts/corpus_audit \\",
        "       --manifest-out config/recovery_corpus_v1.tape_manifest",
        "   ```",
        "3. When corpus_audit exits 0, proceed to Gate 2 rerun:",
        "   ```",
        "   python tools/gates/close_mm_sweep_gate.py \\",
        "       --benchmark-manifest config/recovery_corpus_v1.tape_manifest \\",
        "       --out artifacts/gates/mm_sweep_gate",
        "   ```",
        "",
        "Note: `config/recovery_corpus_v1.tape_manifest` is NOT written until corpus qualifies.",
    ]

    report_path = out_dir / "shortage_report.md"
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _print_summary(
    all_results: list[dict[str, Any]],
    *,
    total_accepted: int,
    qualified: bool,
) -> None:
    """Print a compact summary table to stdout."""
    rejected = [r for r in all_results if r["status"] == "REJECTED"]

    # Accepted by bucket
    bucket_counts: dict[str, int] = {}
    for r in all_results:
        if r["status"] == "ACCEPTED":
            bucket = r["bucket"] or "unknown"
            bucket_counts[bucket] = bucket_counts.get(bucket, 0) + 1

    print("=" * 60)
    print("Corpus Audit Summary")
    print("=" * 60)
    print(f"Total scanned:   {len(all_results)}")
    print(f"Total accepted:  {total_accepted} / {_TOTAL_QUOTA} needed")
    print(f"Total rejected:  {len(rejected)}")
    print("")
    print("Accepted by bucket:")
    for bucket in sorted(_VALID_BUCKETS):
        quota = _BUCKET_QUOTAS[bucket]
        have = bucket_counts.get(bucket, 0)
        status = "OK" if have >= quota else f"NEED {quota - have} more"
        print(f"  {bucket:<18} {have:>3} / {quota}  {status}")
    print("")
    verdict = "QUALIFIED (exit 0)" if qualified else "SHORTAGE (exit 1)"
    print(f"Verdict: {verdict}")
    print("=" * 60)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Scan tape inventory, apply admission rules, and write "
            "config/recovery_corpus_v1.tape_manifest or shortage_report.md."
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
        "--out-dir",
        default=DEFAULT_OUT_DIR,
        metavar="PATH",
        help=f"Output directory for audit artifacts. Default: {DEFAULT_OUT_DIR}",
    )
    parser.add_argument(
        "--min-events",
        type=int,
        default=DEFAULT_MIN_EVENTS,
        metavar="INT",
        help=f"Minimum effective_events per tape. Default: {DEFAULT_MIN_EVENTS}",
    )
    parser.add_argument(
        "--manifest-out",
        default=DEFAULT_MANIFEST_OUT,
        metavar="PATH",
        help=f"Output path for the recovery manifest. Default: {DEFAULT_MANIFEST_OUT}",
    )

    args = parser.parse_args(argv)

    tape_root_strs = args.tape_roots if args.tape_roots else DEFAULT_TAPE_ROOTS
    tape_roots = [
        (Path(r) if Path(r).is_absolute() else _REPO_ROOT / r)
        for r in tape_root_strs
    ]
    out_dir = (
        Path(args.out_dir)
        if Path(args.out_dir).is_absolute()
        else _REPO_ROOT / args.out_dir
    )
    manifest_out = (
        Path(args.manifest_out)
        if Path(args.manifest_out).is_absolute()
        else _REPO_ROOT / args.manifest_out
    )

    if args.min_events < 50:
        print(
            f"ERROR: --min-events {args.min_events} is below the minimum allowed (50). "
            "Never weaken the min_events threshold.",
            file=sys.stderr,
        )
        return 2

    return run_corpus_audit(
        tape_roots=tape_roots,
        out_dir=out_dir,
        min_events=args.min_events,
        manifest_out=manifest_out,
    )


def _first_text(*values: Any) -> str | None:
    """Return first non-empty string from values."""
    for value in values:
        if not isinstance(value, str):
            continue
        text = value.strip()
        if text:
            return text
    return None


if __name__ == "__main__":
    raise SystemExit(main())
