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

    # From gap-fill targets manifest (each target has its own window):
    python -m polytool batch-reconstruct-silver \\
        --targets-manifest config/benchmark_v1_gap_fill.targets.json \\
        --pmxt-root /data/raw/pmxt_archive \\
        --jon-root  /data/raw/jon_becker \\
        --benchmark-refresh \\
        --gap-fill-out artifacts/silver/gap_fill_run.json
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


def write_market_meta(target: dict, tape_dir: Path) -> bool:
    """Write market_meta.json to a Silver tape directory from a gap-fill target entry.

    Contains only the fields needed for benchmark bucket classification:
    slug, category (= bucket), market_id, platform, token_id, benchmark_bucket.

    Returns True on success, False on OSError. Never raises.
    """
    bucket = target.get("bucket", "")
    slug = target.get("slug", "")
    market_id = target.get("market_id", "")
    platform = target.get("platform", "")
    token_id = target.get("token_id", "")

    payload = {
        "schema_version": "silver_market_meta_v1",
        "slug": slug,
        "category": bucket,
        "market_id": market_id,
        "platform": platform,
        "token_id": token_id,
        "benchmark_bucket": bucket,
    }
    try:
        (tape_dir / "market_meta.json").write_text(
            json.dumps(payload, indent=2),
            encoding="utf-8",
        )
        return True
    except OSError:
        return False


def backfill_market_meta_from_targets(
    targets: List[dict],
    *,
    out_root: Path,
) -> dict:
    """Write market_meta.json to existing Silver tape dirs for all targets.

    For each target, computes the canonical tape directory. If
    silver_events.jsonl exists there (tape was previously created),
    writes market_meta.json. Skips targets with missing token_id or
    unparseable window_start.

    Returns a summary dict with counts: written, skipped, missing, error.
    """
    written = 0
    skipped = 0
    missing = 0
    errors = 0

    for target in targets:
        if not isinstance(target, dict):
            skipped += 1
            continue
        token_id = target.get("token_id", "")
        win_start_raw = target.get("window_start", "")
        if not token_id or not win_start_raw:
            skipped += 1
            continue
        try:
            window_start_f = _parse_ts(win_start_raw)
        except (ValueError, TypeError):
            skipped += 1
            continue

        tape_dir = canonical_tape_dir(token_id, window_start_f, out_root)
        if not (tape_dir / "silver_events.jsonl").exists():
            missing += 1
            continue

        ok = write_market_meta(target, tape_dir)
        if ok:
            written += 1
        else:
            errors += 1

    return {"written": written, "skipped": skipped, "missing": missing, "errors": errors}


BATCH_MANIFEST_SCHEMA = "silver_batch_manifest_v1"
TARGETS_MANIFEST_SCHEMA = "benchmark_gap_fill_v1"
GAP_FILL_RUN_SCHEMA = "benchmark_gap_fill_run_v1"


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
    clickhouse_password: str = "",
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


def load_targets_manifest(path: Path) -> tuple:
    """Load and validate a benchmark_gap_fill_v1 targets manifest.

    Returns (targets_list, error_string). On error targets_list is [] and
    error_string is a human-readable message. Never raises.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return [], f"cannot read targets manifest: {exc}"
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        return [], f"targets manifest is not valid JSON: {exc}"
    if not isinstance(data, dict):
        return [], "targets manifest root must be a JSON object"
    sv = data.get("schema_version")
    if sv != TARGETS_MANIFEST_SCHEMA:
        return [], (
            f"unsupported schema_version: {sv!r} "
            f"(expected {TARGETS_MANIFEST_SCHEMA!r})"
        )
    targets = data.get("targets")
    if not isinstance(targets, list):
        return [], "targets manifest missing 'targets' array"
    return targets, None


def run_batch_from_targets(
    targets: List[dict],
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
    clickhouse_password: str = "",
    metadata_fallback_path: Optional[Path] = None,
    batch_run_id: Optional[str] = None,
    _reconstructor_factory=None,
) -> dict:
    """Run batch Silver reconstruction from a gap-fill targets manifest.

    Unlike run_batch(), each target provides its own window_start/window_end,
    bucket, and slug. Invalid or incomplete targets are skipped with a
    recorded reason without aborting the batch.

    Returns a gap-fill batch result dict (schema_version=GAP_FILL_RUN_SCHEMA).
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
    tapes_created = 0
    failure_count = 0
    skip_count = 0
    metadata_ch_count = 0
    metadata_jsonl_count = 0
    metadata_skip_count = 0

    for target in targets:
        if not isinstance(target, dict):
            skip_count += 1
            outcomes.append({
                "token_id": "",
                "bucket": "",
                "slug": "",
                "priority": 0,
                "status": "skip",
                "skip_reason": "target entry is not a JSON object",
                "reconstruction_confidence": "none",
                "event_count": 0,
                "fill_count": 0,
                "price_2min_count": 0,
                "warning_count": 0,
                "warnings": [],
                "out_dir": None,
                "events_path": None,
                "error": None,
                "metadata_write": "skipped",
                "metadata_write_detail": "",
                "window_start": None,
                "window_end": None,
            })
            continue

        token_id = target.get("token_id", "")
        bucket = target.get("bucket", "")
        slug = target.get("slug", "")
        priority = target.get("priority", 0)
        win_start_raw = target.get("window_start", "")
        win_end_raw = target.get("window_end", "")

        # Validate required fields; skip cleanly on any issue
        skip_reason = None
        window_start_f: Optional[float] = None
        window_end_f: Optional[float] = None

        if not token_id:
            skip_reason = "missing token_id"
        else:
            try:
                window_start_f = _parse_ts(win_start_raw) if win_start_raw else None
                if window_start_f is None:
                    skip_reason = "missing or unparseable window_start"
            except (ValueError, TypeError) as exc:
                skip_reason = f"invalid window_start: {exc}"

        if skip_reason is None:
            try:
                window_end_f = _parse_ts(win_end_raw) if win_end_raw else None
                if window_end_f is None:
                    skip_reason = "missing or unparseable window_end"
            except (ValueError, TypeError) as exc:
                skip_reason = f"invalid window_end: {exc}"

        if skip_reason is None and window_end_f <= window_start_f:
            skip_reason = "window_end must be after window_start"

        if skip_reason is not None:
            skip_count += 1
            outcomes.append({
                "token_id": token_id,
                "bucket": bucket,
                "slug": slug,
                "priority": priority,
                "status": "skip",
                "skip_reason": skip_reason,
                "reconstruction_confidence": "none",
                "event_count": 0,
                "fill_count": 0,
                "price_2min_count": 0,
                "warning_count": 0,
                "warnings": [],
                "out_dir": None,
                "events_path": None,
                "error": None,
                "metadata_write": "skipped",
                "metadata_write_detail": "",
                "window_start": win_start_raw,
                "window_end": win_end_raw,
            })
            continue

        out_dir = None if dry_run else canonical_tape_dir(token_id, window_start_f, out_root)

        try:
            if _reconstructor_factory is not None:
                reconstructor = _reconstructor_factory(config)
            else:
                reconstructor = SilverReconstructor(config)

            result = reconstructor.reconstruct(
                token_id=token_id,
                window_start=window_start_f,
                window_end=window_end_f,
                out_dir=out_dir,
                dry_run=dry_run,
            )
            status = "failure" if result.error else "success"
            if result.error:
                failure_count += 1
            else:
                tapes_created += 1

            # Write market metadata companion file for benchmark classification.
            # market_meta.json lets benchmark_manifest.py classify Silver tapes
            # into politics/sports/crypto buckets using slug and category fields.
            if out_dir is not None and not dry_run and not result.error:
                write_market_meta(target, out_dir)

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
                "bucket": bucket,
                "slug": slug,
                "priority": priority,
                "status": status,
                "skip_reason": None,
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
                "window_start": win_start_raw,
                "window_end": win_end_raw,
            })
        except Exception as exc:
            failure_count += 1
            metadata_skip_count += 1
            outcomes.append({
                "token_id": token_id,
                "bucket": bucket,
                "slug": slug,
                "priority": priority,
                "status": "failure",
                "skip_reason": None,
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
                "window_start": win_start_raw,
                "window_end": win_end_raw,
            })

    ended_at = datetime.now(timezone.utc).isoformat()

    return {
        "schema_version": GAP_FILL_RUN_SCHEMA,
        "batch_run_id": batch_run_id,
        "started_at": started_at,
        "ended_at": ended_at,
        "dry_run": dry_run,
        "targets_attempted": len(targets),
        "tapes_created": tapes_created,
        "failure_count": failure_count,
        "skip_count": skip_count,
        "metadata_summary": {
            "clickhouse": metadata_ch_count,
            "jsonl_fallback": metadata_jsonl_count,
            "skipped": metadata_skip_count,
        },
        "out_root": str(out_root),
        "benchmark_refresh": {"triggered": False, "outcome": "not_requested"},
        "outcomes": outcomes,
    }


def _refresh_benchmark_curation(
    *,
    roots: Optional[List[str]] = None,
    manifest_out: str = "config/benchmark_v1.tape_manifest",
    gap_out: str = "config/benchmark_v1.gap_report.json",
    audit_out: str = "config/benchmark_v1.audit.json",
) -> dict:
    """Run benchmark curation and return a machine-readable result summary.

    Calls _run_build() from tools.cli.benchmark_manifest. Never raises;
    returns an error dict on unexpected failure.
    """
    try:
        from tools.cli.benchmark_manifest import _run_build  # type: ignore[import]

        argv: List[str] = []
        if roots:
            for r in roots:
                argv += ["--root", r]
        argv += [
            "--manifest-out", manifest_out,
            "--gap-out", gap_out,
            "--audit-out", audit_out,
        ]
        rc = _run_build(argv)
        manifest_written = rc == 0 and Path(manifest_out).exists()
        if manifest_written:
            outcome = "manifest_written"
        elif rc == 2:
            outcome = "gap_report_updated"
        else:
            outcome = "error"
        return {
            "triggered": True,
            "return_code": rc,
            "manifest_written": manifest_written,
            "outcome": outcome,
            "manifest_path": manifest_out if manifest_written else None,
            "gap_report_path": gap_out if not manifest_written else None,
        }
    except Exception as exc:
        return {
            "triggered": True,
            "return_code": -1,
            "manifest_written": False,
            "outcome": "error",
            "error": str(exc),
            "manifest_path": None,
            "gap_report_path": None,
        }


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="batch-reconstruct-silver",
        description=(
            "Batch-reconstruct Silver tapes for multiple tokens.\n\n"
            "MODE 1 — shared window (--token-id / --token-ids-file):\n"
            "  All tokens share the same --window-start / --window-end.\n\n"
            "MODE 2 — gap-fill targets manifest (--targets-manifest):\n"
            "  Each target provides its own token_id, window_start, window_end,\n"
            "  bucket, and slug from a benchmark_gap_fill_v1 JSON file.\n"
            "  --window-start / --window-end are not required in this mode.\n\n"
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
        help="Polymarket CLOB token ID. Repeat for multiple tokens (MODE 1).",
    )
    p.add_argument(
        "--token-ids-file",
        default=None,
        metavar="PATH",
        help="File with one token ID per line (blank lines and # comments ignored; MODE 1).",
    )
    p.add_argument(
        "--targets-manifest",
        default=None,
        metavar="PATH",
        help=(
            "Path to a benchmark_gap_fill_v1 JSON targets manifest (MODE 2). "
            "Each target provides its own token_id, window_start, window_end, bucket, slug."
        ),
    )
    # window-start/end are required for MODE 1, optional for MODE 2
    p.add_argument("--window-start", default=None, metavar="TS",
                   help="Window start as ISO 8601 or Unix epoch float (required for MODE 1).")
    p.add_argument("--window-end", default=None, metavar="TS",
                   help="Window end as ISO 8601 or Unix epoch float (required for MODE 1).")
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
    # Gap-fill mode extras
    p.add_argument(
        "--benchmark-refresh",
        action="store_true",
        default=False,
        help=(
            "After batch completes (MODE 2 only), re-run benchmark curation "
            "(benchmark-manifest build) to write config/benchmark_v1.tape_manifest "
            "if quotas are now met, or update config/benchmark_v1.gap_report.json."
        ),
    )
    p.add_argument(
        "--gap-fill-out",
        default=None,
        metavar="PATH",
        help=(
            "Write the gap-fill batch result JSON to this path (MODE 2). "
            "Defaults to <batch-out-dir>/gap_fill_run_<batch_id[:8]>.json."
        ),
    )
    p.add_argument(
        "--backfill-market-meta",
        action="store_true",
        default=False,
        help=(
            "Write market_meta.json to existing Silver tape dirs without re-running "
            "reconstruction (MODE 2 only). For each target in --targets-manifest, "
            "finds the canonical tape dir and writes market_meta.json if "
            "silver_events.jsonl is already present. Use this to backfill metadata "
            "for tapes created before market_meta.json was introduced."
        ),
    )
    return p


def main(argv: Optional[List[str]] = None) -> int:
    """CLI entrypoint: python -m polytool batch-reconstruct-silver [options]."""
    import os

    parser = _build_parser()
    args = parser.parse_args(argv)

    ch_password = args.clickhouse_password
    if ch_password is None:
        ch_password = os.environ.get("CLICKHOUSE_PASSWORD")
    # Backfill-only and dry-run modes do not write to ClickHouse; skip the password check.
    backfill_only = getattr(args, "backfill_market_meta", False)
    dry_run_mode = getattr(args, "dry_run", False)
    if not backfill_only and not dry_run_mode and not ch_password:
        print(
            "Error: ClickHouse password not set.\n"
            "  Pass --clickhouse-password PASSWORD, or export CLICKHOUSE_PASSWORD=<password>.",
            file=sys.stderr,
        )
        return 1
    ch_password = ch_password or ""

    out_root = Path(args.out_root)
    batch_out_dir = Path(args.batch_out_dir) if args.batch_out_dir else out_root / "silver"
    batch_run_id = str(uuid.uuid4())

    # -----------------------------------------------------------------------
    # MODE 2: gap-fill targets manifest
    # -----------------------------------------------------------------------
    if args.targets_manifest:
        targets_path = Path(args.targets_manifest)
        targets, load_err = load_targets_manifest(targets_path)
        if load_err:
            print(f"Error: --targets-manifest: {load_err}", file=sys.stderr)
            return 1

        # -----------------------------------------------------------------------
        # BACKFILL-ONLY mode: write market_meta.json to existing tapes
        # -----------------------------------------------------------------------
        if args.backfill_market_meta:
            print(f"[batch-reconstruct-silver] [BACKFILL] writing market_meta.json to existing tapes")
            print(f"  manifest: {targets_path}  targets={len(targets)}")
            print(f"  out-root: {out_root}")
            summary = backfill_market_meta_from_targets(targets, out_root=out_root)
            print(f"\n[batch-reconstruct-silver] backfill complete")
            print(f"  written: {summary['written']}")
            print(f"  missing: {summary['missing']}  (tape dir not found)")
            print(f"  skipped: {summary['skipped']}  (invalid targets)")
            print(f"  errors:  {summary['errors']}")
            return 0 if summary["errors"] == 0 else 1

        mode_label = "DRY-RUN" if args.dry_run else "LIVE"
        print(f"[batch-reconstruct-silver] [{mode_label}] targets-manifest mode")
        print(f"  manifest: {targets_path}  targets={len(targets)}")
        print(f"  out-root: {out_root}")
        print(f"  batch_run_id: {batch_run_id}")

        result = run_batch_from_targets(
            targets=targets,
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

        # Optionally run benchmark refresh
        if args.benchmark_refresh and not args.dry_run:
            print("\n[batch-reconstruct-silver] running benchmark refresh...")
            refresh = _refresh_benchmark_curation()
            result["benchmark_refresh"] = refresh
            if refresh.get("manifest_written"):
                print(f"  [benchmark-manifest] manifest written: {refresh.get('manifest_path')}")
            else:
                print(f"  [benchmark-manifest] outcome={refresh.get('outcome')} gap_report={refresh.get('gap_report_path')}")

        # Print summary
        print(f"\n[batch-reconstruct-silver] gap-fill complete")
        print(f"  targets_attempted: {result['targets_attempted']}")
        print(f"  tapes_created: {result['tapes_created']}")
        print(f"  failure_count: {result['failure_count']}")
        print(f"  skip_count: {result['skip_count']}")
        meta = result["metadata_summary"]
        print(f"  metadata: ch={meta['clickhouse']} jsonl={meta['jsonl_fallback']} skipped={meta['skipped']}")
        for outcome in result["outcomes"]:
            status = outcome["status"]
            tid = (outcome["token_id"] or "")[:16]
            if status == "skip":
                print(f"  [SKIP] {tid}... reason={outcome.get('skip_reason', '')}")
            else:
                icon = "OK" if status == "success" else "FAIL"
                confidence = outcome.get("reconstruction_confidence", "none")
                events = outcome.get("event_count", 0)
                print(f"  [{icon}] {tid}... bucket={outcome.get('bucket','')} confidence={confidence} events={events}")
                if outcome.get("error"):
                    print(f"       error: {outcome['error']}")

        # Write gap-fill result artifact
        result_path = None
        if args.gap_fill_out:
            result_path = Path(args.gap_fill_out)
        elif not args.dry_run:
            result_path = batch_out_dir / f"gap_fill_run_{batch_run_id[:8]}.json"

        if result_path:
            result_path.parent.mkdir(parents=True, exist_ok=True)
            result_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
            print(f"\n  gap-fill result: {result_path}")

        # Exit non-zero only if all targets failed or were skipped (no tapes created)
        if result["tapes_created"] == 0 and result["targets_attempted"] > 0 and not args.dry_run:
            return 1
        return 0

    # -----------------------------------------------------------------------
    # MODE 1: shared window (original behavior)
    # -----------------------------------------------------------------------

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
        print(
            "Error: at least one --token-id or --token-ids-file is required "
            "(or use --targets-manifest for gap-fill mode).",
            file=sys.stderr,
        )
        return 1

    # --window-start/end are required for MODE 1
    if not args.window_start:
        print("Error: --window-start is required (or use --targets-manifest for gap-fill mode).", file=sys.stderr)
        return 1
    if not args.window_end:
        print("Error: --window-end is required (or use --targets-manifest for gap-fill mode).", file=sys.stderr)
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

    mode_label = "DRY-RUN" if args.dry_run else "LIVE"
    print(f"[batch-reconstruct-silver] [{mode_label}] tokens={len(token_ids)}")
    print(f"  window: {args.window_start} -> {args.window_end}")
    print(f"  out-root: {out_root}")
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
