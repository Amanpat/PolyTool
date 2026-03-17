"""CLI: batch-reconstruct Silver tapes for multiple tokens over the same time window.

For each token, calls SilverReconstructor.reconstruct() and writes:
  silver_events.jsonl  — deterministic Silver tape events
  silver_meta.json     — reconstruction metadata

After each reconstruction, persists tape_metadata to ClickHouse (or JSONL fallback).
Emits a batch manifest JSON summarising all outcomes.

Usage:
    python -m polytool batch-reconstruct-silver \\
        --token-id 0xAAA --token-id 0xBBB \\
        --window-start "2024-01-01T00:00:00Z" \\
        --window-end   "2024-01-01T02:00:00Z" \\
        --pmxt-root    /data/raw/pmxt_archive \\
        --jon-root     /data/raw/jon_becker

    # From file:
    python -m polytool batch-reconstruct-silver \\
        --token-ids-file tokens.txt \\
        --window-start "2024-01-01T00:00:00Z" \\
        --window-end   "2024-01-01T02:00:00Z"

    # Dry run (no files, no metadata):
    python -m polytool batch-reconstruct-silver \\
        --token-id 0xAAA \\
        --window-start "2024-01-01T00:00:00Z" \\
        --window-end   "2024-01-01T02:00:00Z" \\
        --dry-run

    # Skip metadata writes:
    python -m polytool batch-reconstruct-silver \\
        --token-id 0xAAA \\
        --window-start "2024-01-01T00:00:00Z" \\
        --window-end   "2024-01-01T02:00:00Z" \\
        --skip-metadata
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

# Module-level imports enable unittest.mock.patch to target these symbols.
# The try/except guard keeps the module importable even without all dependencies
# installed (e.g. when running --help or in minimal test environments).
try:
    from packages.polymarket.silver_reconstructor import ReconstructConfig, SilverReconstructor
    from packages.polymarket.silver_tape_metadata import (
        build_from_silver_result,
        write_to_clickhouse,
        write_to_jsonl,
    )
except ImportError:
    ReconstructConfig = None  # type: ignore[assignment,misc]
    SilverReconstructor = None  # type: ignore[assignment,misc]
    build_from_silver_result = None  # type: ignore[assignment]
    write_to_clickhouse = None  # type: ignore[assignment]
    write_to_jsonl = None  # type: ignore[assignment]


def _parse_ts(value: str) -> float:
    """Parse ISO 8601 or Unix epoch float -> epoch seconds. Raises ValueError."""
    text = value.strip()
    if not text:
        raise ValueError("timestamp string is empty")
    try:
        f = float(text)
        if math.isfinite(f):
            return f
    except ValueError:
        pass
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.timestamp()
    except ValueError as exc:
        raise ValueError(
            f"Cannot parse timestamp {value!r} as epoch float or ISO 8601: {exc}"
        ) from exc


def canonical_tape_dir(token_id: str, window_start: float, out_root: Path) -> Path:
    """Return the canonical output directory for a Silver tape.

    Format: <out_root>/silver/<token_id[:16]>/<YYYY-MM-DDTHH-MM-SSZ>/

    The 16-char token prefix (vs 8-char in single-market CLI) reduces collision
    risk in large batch runs.
    """
    token_prefix = token_id[:16] if token_id else "unknown"
    try:
        dt = datetime.fromtimestamp(window_start, tz=timezone.utc)
        date_label = dt.strftime("%Y-%m-%dT%H-%M-%SZ")
    except Exception:
        date_label = str(int(window_start))
    return out_root / "silver" / token_prefix / date_label


BATCH_MANIFEST_SCHEMA = "silver_batch_manifest_v1"


def run_batch(
    token_ids: List[str],
    window_start: float,
    window_end: float,
    *,
    out_root: Path,
    pmxt_root: Optional[str] = None,
    jon_root: Optional[str] = None,
    dry_run: bool = False,
    skip_price_2min: bool = False,
    skip_metadata: bool = False,
    no_metadata_fallback: bool = False,
    clickhouse_host: str = "localhost",
    clickhouse_port: int = 8123,
    clickhouse_user: str = "polytool_admin",
    clickhouse_password: str = "polytool_admin",
    metadata_fallback_path: Optional[Path] = None,
    batch_run_id: Optional[str] = None,
    _reconstructor_factory=None,
) -> dict:
    """Run batch Silver reconstruction for multiple tokens.

    Returns a manifest dict with per-token outcomes.
    """
    if batch_run_id is None:
        batch_run_id = str(uuid.uuid4())

    started_at = datetime.now(timezone.utc).isoformat()

    config = ReconstructConfig(
        pmxt_root=pmxt_root,
        jon_root=jon_root,
        clickhouse_host=clickhouse_host,
        clickhouse_port=clickhouse_port,
        clickhouse_user=clickhouse_user,
        clickhouse_password=clickhouse_password,
        skip_price_2min=skip_price_2min,
    )

    outcomes = []
    success_count = 0
    failure_count = 0
    metadata_ch_count = 0
    metadata_jsonl_count = 0
    metadata_skip_count = 0

    for token_id in token_ids:
        out_dir = None if dry_run else canonical_tape_dir(token_id, window_start, out_root)

        try:
            if _reconstructor_factory is not None:
                reconstructor = _reconstructor_factory(config)
            else:
                reconstructor = SilverReconstructor(config)

            result = reconstructor.reconstruct(
                token_id=token_id,
                window_start=window_start,
                window_end=window_end,
                out_dir=out_dir,
                dry_run=dry_run,
            )
            status = "failure" if result.error else "success"
            if result.error:
                failure_count += 1
            else:
                success_count += 1

            # Metadata persistence
            meta_write_status = "skipped"
            meta_write_detail = ""
            if not skip_metadata and not dry_run and not result.error:
                row = build_from_silver_result(
                    result,
                    tier="silver",
                    batch_run_id=batch_run_id,
                    tape_path=str(result.events_path) if result.events_path else str(out_dir or ""),
                )
                ch_ok = write_to_clickhouse(
                    row,
                    host=clickhouse_host,
                    port=clickhouse_port,
                    user=clickhouse_user,
                    password=clickhouse_password,
                )
                if ch_ok:
                    meta_write_status = "clickhouse"
                    metadata_ch_count += 1
                elif not no_metadata_fallback:
                    fallback = metadata_fallback_path or (out_root / "silver_batch_metadata_fallback.jsonl")
                    jl_ok = write_to_jsonl(row, fallback)
                    if jl_ok:
                        meta_write_status = "jsonl_fallback"
                        meta_write_detail = str(fallback)
                        metadata_jsonl_count += 1
                    else:
                        meta_write_status = "failed"
                else:
                    meta_write_status = "failed_no_fallback"
            else:
                metadata_skip_count += 1

            outcomes.append({
                "token_id": token_id,
                "status": status,
                "reconstruction_confidence": result.reconstruction_confidence,
                "event_count": result.event_count,
                "fill_count": result.fill_count,
                "price_2min_count": result.price_2min_count,
                "warning_count": len(result.warnings),
                "warnings": list(result.warnings),
                "out_dir": str(out_dir) if out_dir else None,
                "events_path": str(result.events_path) if result.events_path else None,
                "error": result.error,
                "metadata_write": meta_write_status,
                "metadata_write_detail": meta_write_detail,
            })
        except Exception as exc:
            failure_count += 1
            outcomes.append({
                "token_id": token_id,
                "status": "failure",
                "reconstruction_confidence": "none",
                "event_count": 0,
                "fill_count": 0,
                "price_2min_count": 0,
                "warning_count": 0,
                "warnings": [],
                "out_dir": None,
                "events_path": None,
                "error": str(exc),
                "metadata_write": "skipped",
                "metadata_write_detail": "",
            })
            metadata_skip_count += 1

    ended_at = datetime.now(timezone.utc).isoformat()

    return {
        "schema_version": BATCH_MANIFEST_SCHEMA,
        "batch_run_id": batch_run_id,
        "started_at": started_at,
        "ended_at": ended_at,
        "dry_run": dry_run,
        "token_count": len(token_ids),
        "success_count": success_count,
        "failure_count": failure_count,
        "metadata_summary": {
            "clickhouse": metadata_ch_count,
            "jsonl_fallback": metadata_jsonl_count,
            "skipped": metadata_skip_count,
        },
        "window_start": datetime.fromtimestamp(window_start, tz=timezone.utc).isoformat(),
        "window_end": datetime.fromtimestamp(window_end, tz=timezone.utc).isoformat(),
        "out_root": str(out_root),
        "outcomes": outcomes,
    }


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="batch-reconstruct-silver",
        description=(
            "Batch-reconstruct Silver tapes for multiple tokens over a shared time window.\n\n"
            "Each token gets its own canonical output directory under:\n"
            "  <out-root>/silver/<token_id[:16]>/<YYYY-MM-DDTHH-MM-SSZ>/\n\n"
            "After each reconstruction, persists tape_metadata to ClickHouse (or a\n"
            "JSONL fallback file). Emits a batch manifest JSON summarising all outcomes."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument(
        "--token-id",
        action="append",
        dest="token_ids",
        default=[],
        metavar="ID",
        help="Polymarket CLOB token ID. Repeat for multiple tokens.",
    )
    p.add_argument(
        "--token-ids-file",
        default=None,
        metavar="PATH",
        help="File with one token ID per line (blank lines and # comments ignored).",
    )
    p.add_argument("--window-start", required=True, metavar="TS",
                   help="Window start as ISO 8601 or Unix epoch float.")
    p.add_argument("--window-end", required=True, metavar="TS",
                   help="Window end as ISO 8601 or Unix epoch float.")
    p.add_argument("--pmxt-root", default=None, metavar="PATH",
                   help="Root of pmxt_archive dataset. Omit to skip pmxt anchor source.")
    p.add_argument("--jon-root", default=None, metavar="PATH",
                   help="Root of jon_becker dataset. Omit to skip Jon-Becker fill source.")
    p.add_argument("--out-root", default="artifacts", metavar="PATH",
                   help="Root for canonical output dirs (default: artifacts).")
    p.add_argument("--batch-out-dir", default=None, metavar="PATH",
                   help="Directory to write batch_manifest.json (default: <out-root>/silver).")
    p.add_argument("--dry-run", action="store_true", default=False,
                   help="Run all fetch logic but do not write output files or metadata.")
    p.add_argument("--skip-price-2min", action="store_true", default=False,
                   help="Skip the ClickHouse price_2min query (offline/test mode).")
    p.add_argument("--skip-metadata", action="store_true", default=False,
                   help="Skip all tape_metadata writes (ClickHouse + JSONL fallback).")
    p.add_argument("--no-metadata-fallback", action="store_true", default=False,
                   help="Do not write JSONL fallback if ClickHouse metadata write fails.")
    p.add_argument("--clickhouse-host", default="localhost", metavar="HOST",
                   help="ClickHouse host (default: localhost).")
    p.add_argument("--clickhouse-port", default=8123, type=int, metavar="PORT",
                   help="ClickHouse HTTP port (default: 8123).")
    p.add_argument("--clickhouse-user", default="polytool_admin", metavar="USER",
                   help="ClickHouse user (default: polytool_admin).")
    p.add_argument("--clickhouse-password", default=None, metavar="PASSWORD",
                   help="ClickHouse password (falls back to CLICKHOUSE_PASSWORD env var).")
    p.add_argument("--out", default=None, metavar="PATH",
                   help="Write batch manifest JSON to this path (overrides --batch-out-dir).")
    return p


def main(argv: Optional[List[str]] = None) -> int:
    """CLI entrypoint: python -m polytool batch-reconstruct-silver [options]."""
    import os

    parser = _build_parser()
    args = parser.parse_args(argv)

    # Collect token IDs
    token_ids: List[str] = list(args.token_ids)
    if args.token_ids_file:
        try:
            lines = Path(args.token_ids_file).read_text(encoding="utf-8").splitlines()
            for line in lines:
                line = line.strip()
                if line and not line.startswith("#"):
                    token_ids.append(line)
        except OSError as exc:
            print(f"Error reading --token-ids-file: {exc}", file=sys.stderr)
            return 1

    if not token_ids:
        print("Error: at least one --token-id or --token-ids-file is required.", file=sys.stderr)
        return 1

    # Parse timestamps
    try:
        window_start = _parse_ts(args.window_start)
    except ValueError as exc:
        print(f"Error: --window-start: {exc}", file=sys.stderr)
        return 1
    try:
        window_end = _parse_ts(args.window_end)
    except ValueError as exc:
        print(f"Error: --window-end: {exc}", file=sys.stderr)
        return 1
    if window_end <= window_start:
        print("Error: --window-end must be after --window-start.", file=sys.stderr)
        return 1

    ch_password = args.clickhouse_password
    if ch_password is None:
        ch_password = os.environ.get("CLICKHOUSE_PASSWORD", "polytool_admin")

    out_root = Path(args.out_root)
    batch_out_dir = Path(args.batch_out_dir) if args.batch_out_dir else out_root / "silver"

    mode_label = "DRY-RUN" if args.dry_run else "LIVE"
    print(f"[batch-reconstruct-silver] [{mode_label}] tokens={len(token_ids)}")
    print(f"  window: {args.window_start} -> {args.window_end}")
    print(f"  out-root: {out_root}")

    batch_run_id = str(uuid.uuid4())
    print(f"  batch_run_id: {batch_run_id}")

    manifest = run_batch(
        token_ids=token_ids,
        window_start=window_start,
        window_end=window_end,
        out_root=out_root,
        pmxt_root=args.pmxt_root,
        jon_root=args.jon_root,
        dry_run=args.dry_run,
        skip_price_2min=args.skip_price_2min,
        skip_metadata=args.skip_metadata,
        no_metadata_fallback=args.no_metadata_fallback,
        clickhouse_host=args.clickhouse_host,
        clickhouse_port=args.clickhouse_port,
        clickhouse_user=args.clickhouse_user,
        clickhouse_password=ch_password,
        batch_run_id=batch_run_id,
    )

    # Print summary
    print(f"\n[batch-reconstruct-silver] complete")
    print(f"  success: {manifest['success_count']}/{manifest['token_count']}")
    print(f"  failure: {manifest['failure_count']}/{manifest['token_count']}")
    meta = manifest["metadata_summary"]
    print(f"  metadata: ch={meta['clickhouse']} jsonl={meta['jsonl_fallback']} skipped={meta['skipped']}")
    for outcome in manifest["outcomes"]:
        icon = "OK" if outcome["status"] == "success" else "FAIL"
        print(f"  [{icon}] {outcome['token_id'][:16]}... confidence={outcome['reconstruction_confidence']} events={outcome['event_count']}")
        if outcome.get("error"):
            print(f"       error: {outcome['error']}")

    # Write manifest
    manifest_path = None
    if args.out:
        manifest_path = Path(args.out)
    elif not args.dry_run:
        manifest_path = batch_out_dir / f"batch_manifest_{batch_run_id[:8]}.json"

    if manifest_path:
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        print(f"\n  batch manifest: {manifest_path}")

    # Exit 1 only if all tokens failed
    if manifest["failure_count"] == manifest["token_count"] and manifest["token_count"] > 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
