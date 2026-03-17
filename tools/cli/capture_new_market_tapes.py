"""CLI: capture-new-market-tapes — record Gold tapes for benchmark new_market targets.

Consumes ``config/benchmark_v1_new_market_capture.targets.json``
(schema: ``benchmark_new_market_capture_v1``) and records a live Gold tape for
each target via TapeRecorder (Polymarket Market Channel WS).

Per-target failures are recorded without aborting the batch.  The
``--benchmark-refresh`` flag re-runs benchmark curation after capture so
``config/benchmark_v1.tape_manifest`` is written as soon as the quota is met.

Exit codes
----------
  0 — at least one tape created (or dry-run with >= 1 resolvable target)
  1 — all targets failed / skipped (0 tapes created) or manifest load error

Usage
-----
    python -m polytool capture-new-market-tapes
    python -m polytool capture-new-market-tapes --dry-run
    python -m polytool capture-new-market-tapes \\
        --targets-manifest config/benchmark_v1_new_market_capture.targets.json \\
        --benchmark-refresh \\
        --result-out artifacts/benchmark_capture/run.json
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Module-level imports — kept at top level so unittest.mock.patch can target them
# ---------------------------------------------------------------------------

try:
    from packages.polymarket.simtrader.tape.recorder import TapeRecorder
except ImportError:
    TapeRecorder = None  # type: ignore[assignment,misc]

try:
    from packages.polymarket.simtrader.market_picker import MarketPicker
except ImportError:
    MarketPicker = None  # type: ignore[assignment,misc]

try:
    from packages.polymarket.silver_tape_metadata import (
        TapeMetadataRow,
        write_to_clickhouse,
        write_to_jsonl,
    )
except ImportError:
    TapeMetadataRow = None  # type: ignore[assignment,misc]
    write_to_clickhouse = None  # type: ignore[assignment]
    write_to_jsonl = None  # type: ignore[assignment]

# ---------------------------------------------------------------------------
# Schema constants
# ---------------------------------------------------------------------------

CAPTURE_MANIFEST_SCHEMA = "benchmark_new_market_capture_v1"
CAPTURE_RUN_SCHEMA = "benchmark_new_market_capture_run_v1"

_DEFAULT_TARGETS_PATH = Path("config/benchmark_v1_new_market_capture.targets.json")
_DEFAULT_TAPES_ROOT = Path("artifacts/simtrader/tapes/new_market_capture")


# ---------------------------------------------------------------------------
# Manifest loading
# ---------------------------------------------------------------------------


def load_capture_targets(path: Path) -> Tuple[List[dict], Optional[str]]:
    """Load and validate a ``benchmark_new_market_capture_v1`` targets manifest.

    Returns ``(targets_list, error_string)``.  On error ``targets_list`` is
    ``[]`` and ``error_string`` describes the problem.  Never raises.
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
    if sv != CAPTURE_MANIFEST_SCHEMA:
        return [], (
            f"unsupported schema_version: {sv!r} "
            f"(expected {CAPTURE_MANIFEST_SCHEMA!r})"
        )
    targets = data.get("targets")
    if not isinstance(targets, list):
        return [], "targets manifest missing 'targets' array"
    return targets, None


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------


def canonical_tape_dir(slug: str, out_root: Path) -> Path:
    """Return canonical output directory for a Gold tape: ``<out_root>/<slug>/``."""
    safe_slug = (slug or "unknown").replace("/", "_").replace("\\", "_")
    return out_root / safe_slug


# ---------------------------------------------------------------------------
# Token ID resolution
# ---------------------------------------------------------------------------


def resolve_both_token_ids(
    slug: str,
    *,
    _picker_factory=None,
) -> Tuple[str, str, Optional[str]]:
    """Resolve YES and NO token IDs for a market slug.

    Returns ``(yes_token_id, no_token_id, error_or_None)``.
    On error both IDs are ``""`` and ``error_or_None`` is a human-readable
    message.  Never raises.
    """
    try:
        if _picker_factory is not None:
            picker = _picker_factory()
        else:
            if MarketPicker is None:
                return "", "", "MarketPicker not available (missing dependency)"
            picker = MarketPicker()
        resolved = picker.resolve_slug(slug)
        return resolved.yes_token_id, resolved.no_token_id, None
    except Exception as exc:
        return "", "", f"resolve_slug failed for {slug!r}: {exc}"


# ---------------------------------------------------------------------------
# Gold tape metadata builder
# ---------------------------------------------------------------------------


def _build_gold_tape_metadata_row(
    *,
    run_id: str,
    tape_path: str,
    token_id: str,
    recorded_at: str,
    record_duration_seconds: int,
    slug: str,
    listed_at: str,
    age_hours: float,
    batch_run_id: str,
) -> "TapeMetadataRow":
    """Build a :class:`~packages.polymarket.silver_tape_metadata.TapeMetadataRow`
    for a Gold tape.  Reuses the Silver metadata table with ``tier="gold"``.
    """
    try:
        dt_start = datetime.fromisoformat(recorded_at.replace("Z", "+00:00"))
        dt_end = dt_start + timedelta(seconds=record_duration_seconds)
        window_end = dt_end.isoformat()
    except Exception:
        window_end = recorded_at

    source_inputs: Dict[str, Any] = {
        "slug": slug,
        "bucket": "new_market",
        "listed_at": listed_at,
        "age_hours": age_hours,
        "recorded_from_live_ws": True,
    }
    return TapeMetadataRow(
        run_id=run_id,
        tape_path=tape_path,
        tier="gold",
        token_id=token_id,
        window_start=recorded_at,
        window_end=window_end,
        reconstruction_confidence="gold",
        warning_count=0,
        source_inputs_json=json.dumps(source_inputs),
        generated_at=datetime.now(timezone.utc).isoformat(),
        batch_run_id=batch_run_id,
    )


# ---------------------------------------------------------------------------
# Per-target outcome helpers
# ---------------------------------------------------------------------------


def _skip_outcome(
    token_id: str,
    slug: str,
    priority: int,
    listed_at: str,
    age_hours: float,
    record_duration_seconds: int,
    skip_reason: str,
) -> dict:
    return {
        "token_id": token_id,
        "slug": slug,
        "bucket": "new_market",
        "priority": priority,
        "status": "skip",
        "skip_reason": skip_reason,
        "tape_dir": None,
        "events_path": None,
        "event_count": 0,
        "listed_at": listed_at,
        "age_hours": age_hours,
        "record_duration_seconds": record_duration_seconds,
        "error": None,
        "metadata_write": "skipped",
        "metadata_write_detail": "",
    }


# ---------------------------------------------------------------------------
# Benchmark refresh (shared pattern with batch_reconstruct_silver)
# ---------------------------------------------------------------------------


def _refresh_benchmark_curation(
    *,
    manifest_out: str = "config/benchmark_v1.tape_manifest",
    gap_out: str = "config/benchmark_v1.gap_report.json",
    audit_out: str = "config/benchmark_v1.audit.json",
) -> dict:
    """Re-run benchmark curation post-capture.  Never raises."""
    try:
        from tools.cli.benchmark_manifest import _run_build  # type: ignore[import]

        argv: List[str] = [
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


# ---------------------------------------------------------------------------
# Core batch runner
# ---------------------------------------------------------------------------


def run_capture_batch(
    targets: List[dict],
    *,
    out_root: Path,
    dry_run: bool = False,
    skip_metadata: bool = False,
    no_metadata_fallback: bool = False,
    clickhouse_host: str = "localhost",
    clickhouse_port: int = 8123,
    clickhouse_user: str = "polytool_admin",
    clickhouse_password: str = "polytool_admin",
    metadata_fallback_path: Optional[Path] = None,
    batch_run_id: Optional[str] = None,
    _picker_factory=None,
    _recorder_factory=None,
) -> dict:
    """Record a Gold tape for each target in a ``benchmark_new_market_capture_v1`` manifest.

    Each target is processed independently; failures are recorded without
    aborting the batch.

    Args:
        targets:              List of target dicts from the manifest.
        out_root:             Root directory for Gold tapes.
        dry_run:              If True, resolve markets but skip recording and
                              file writes.
        skip_metadata:        If True, skip all tape_metadata writes.
        no_metadata_fallback: If True, skip JSONL fallback when CH write fails.
        _picker_factory:      Callable ``() -> MarketPicker``-like; for testing.
        _recorder_factory:    Callable ``(tape_dir, asset_ids) -> TapeRecorder``-like;
                              for testing.

    Returns:
        ``benchmark_new_market_capture_run_v1`` result dict.
    """
    if batch_run_id is None:
        batch_run_id = str(uuid.uuid4())

    started_at = datetime.now(timezone.utc).isoformat()

    outcomes: List[dict] = []
    tapes_created = 0
    failure_count = 0
    skip_count = 0
    metadata_ch_count = 0
    metadata_jsonl_count = 0
    metadata_skip_count = 0

    for target in targets:
        if not isinstance(target, dict):
            skip_count += 1
            outcomes.append(_skip_outcome("", "", 0, "", 0.0, 1800, "target entry is not a JSON object"))
            continue

        slug = str(target.get("slug") or "").strip()
        token_id_hint = str(target.get("token_id") or "").strip()
        priority = int(target.get("priority") or 0)
        listed_at = str(target.get("listed_at") or "")
        age_hours = float(target.get("age_hours") or 0.0)
        record_duration_seconds = int(target.get("record_duration_seconds") or 1800)

        if not slug:
            skip_count += 1
            outcomes.append(_skip_outcome(
                token_id_hint, slug, priority, listed_at, age_hours,
                record_duration_seconds, "missing slug",
            ))
            continue

        # Resolve both YES and NO token IDs from the live market
        yes_id, no_id, resolve_err = resolve_both_token_ids(slug, _picker_factory=_picker_factory)
        if resolve_err or not yes_id or not no_id:
            err_msg = resolve_err or "could not resolve YES/NO token IDs for slug"
            skip_count += 1
            outcomes.append(_skip_outcome(
                token_id_hint, slug, priority, listed_at, age_hours,
                record_duration_seconds, err_msg,
            ))
            continue

        tape_dir = canonical_tape_dir(slug, out_root)

        # ----------------------------------------------------------------
        # Dry run — resolved OK, skip actual recording
        # ----------------------------------------------------------------
        if dry_run:
            tapes_created += 1
            metadata_skip_count += 1
            outcomes.append({
                "token_id": yes_id,
                "slug": slug,
                "bucket": "new_market",
                "priority": priority,
                "status": "success",
                "skip_reason": None,
                "tape_dir": str(tape_dir),
                "events_path": str(tape_dir / "events.jsonl"),
                "event_count": 0,
                "listed_at": listed_at,
                "age_hours": age_hours,
                "record_duration_seconds": record_duration_seconds,
                "error": None,
                "metadata_write": "skipped",
                "metadata_write_detail": "",
            })
            continue

        # ----------------------------------------------------------------
        # Live recording
        # ----------------------------------------------------------------
        recorded_at = datetime.now(timezone.utc).isoformat()
        event_count = 0
        record_error = None

        try:
            tape_dir.mkdir(parents=True, exist_ok=True)

            # Write watch_meta.json (same pattern as watch-arb-candidates)
            watch_meta: Dict[str, Any] = {
                "market_slug": slug,
                "yes_asset_id": yes_id,
                "no_asset_id": no_id,
                "recorded_at": recorded_at,
                "bucket": "new_market",
                "listed_at": listed_at,
                "age_hours": age_hours,
                "regime": "new_market",
                "threshold_source": "new_market_capture_plan",
            }
            (tape_dir / "watch_meta.json").write_text(
                json.dumps(watch_meta, indent=2), encoding="utf-8"
            )

            # Create recorder and record
            if _recorder_factory is not None:
                recorder = _recorder_factory(tape_dir, [yes_id, no_id])
            else:
                if TapeRecorder is None:
                    raise ImportError("TapeRecorder not available (missing SimTrader dependency)")
                recorder = TapeRecorder(tape_dir=tape_dir, asset_ids=[yes_id, no_id])

            recorder.record(duration_seconds=record_duration_seconds)

            # Read event_count from meta.json written by TapeRecorder
            meta_path = tape_dir / "meta.json"
            if meta_path.exists():
                try:
                    meta_data = json.loads(meta_path.read_text(encoding="utf-8"))
                    event_count = int(meta_data.get("event_count") or 0)
                except Exception:
                    event_count = 0

        except Exception as exc:
            failure_count += 1
            metadata_skip_count += 1
            outcomes.append({
                "token_id": yes_id,
                "slug": slug,
                "bucket": "new_market",
                "priority": priority,
                "status": "failure",
                "skip_reason": None,
                "tape_dir": str(tape_dir),
                "events_path": None,
                "event_count": 0,
                "listed_at": listed_at,
                "age_hours": age_hours,
                "record_duration_seconds": record_duration_seconds,
                "error": str(exc),
                "metadata_write": "skipped",
                "metadata_write_detail": "",
            })
            continue

        tapes_created += 1
        events_path = tape_dir / "events.jsonl"

        # ----------------------------------------------------------------
        # Metadata persistence
        # ----------------------------------------------------------------
        meta_write_status = "skipped"
        meta_write_detail = ""

        if not skip_metadata:
            row = _build_gold_tape_metadata_row(
                run_id=str(uuid.uuid4()),
                tape_path=str(events_path),
                token_id=yes_id,
                recorded_at=recorded_at,
                record_duration_seconds=record_duration_seconds,
                slug=slug,
                listed_at=listed_at,
                age_hours=age_hours,
                batch_run_id=batch_run_id,
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
                fallback = metadata_fallback_path or (out_root / "capture_metadata_fallback.jsonl")
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
            "token_id": yes_id,
            "slug": slug,
            "bucket": "new_market",
            "priority": priority,
            "status": "success",
            "skip_reason": None,
            "tape_dir": str(tape_dir),
            "events_path": str(events_path),
            "event_count": event_count,
            "listed_at": listed_at,
            "age_hours": age_hours,
            "record_duration_seconds": record_duration_seconds,
            "error": None,
            "metadata_write": meta_write_status,
            "metadata_write_detail": meta_write_detail,
        })

    ended_at = datetime.now(timezone.utc).isoformat()

    return {
        "schema_version": CAPTURE_RUN_SCHEMA,
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


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="capture-new-market-tapes",
        description=(
            "Record Gold tapes for benchmark_v1 new_market targets.\n\n"
            "Consumes a benchmark_new_market_capture_v1 targets manifest produced by\n"
            "'new-market-capture' and records a live Gold tape for each target via\n"
            "the TapeRecorder (Polymarket Market Channel WS).\n\n"
            "Per-target failures are recorded without aborting the batch.\n"
            "After capture, --benchmark-refresh re-runs benchmark curation to check\n"
            "if config/benchmark_v1.tape_manifest can now be written."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument(
        "--targets-manifest",
        default=str(_DEFAULT_TARGETS_PATH),
        metavar="PATH",
        help=(
            f"Path to benchmark_new_market_capture_v1 targets JSON "
            f"(default: {_DEFAULT_TARGETS_PATH})."
        ),
    )
    p.add_argument(
        "--out-root",
        default=str(_DEFAULT_TAPES_ROOT),
        metavar="PATH",
        help=f"Root directory for Gold tapes (default: {_DEFAULT_TAPES_ROOT}).",
    )
    p.add_argument(
        "--result-out",
        default=None,
        metavar="PATH",
        help=(
            "Write batch result JSON to this path. "
            "Default: <out-root>/capture_run_<id[:8]>.json."
        ),
    )
    p.add_argument(
        "--benchmark-refresh",
        action="store_true",
        default=False,
        help=(
            "After batch completes (non-dry-run only), re-run benchmark "
            "curation to write config/benchmark_v1.tape_manifest if quotas "
            "are met, or update config/benchmark_v1.gap_report.json."
        ),
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help=(
            "Resolve markets and verify targets without connecting to the WS "
            "or writing tape files."
        ),
    )
    p.add_argument(
        "--skip-metadata",
        action="store_true",
        default=False,
        help="Skip all tape_metadata writes (ClickHouse + JSONL fallback).",
    )
    p.add_argument(
        "--no-metadata-fallback",
        action="store_true",
        default=False,
        help="Do not write JSONL fallback if ClickHouse metadata write fails.",
    )
    p.add_argument(
        "--clickhouse-host",
        default="localhost",
        metavar="HOST",
        help="ClickHouse host (default: localhost).",
    )
    p.add_argument(
        "--clickhouse-port",
        default=8123,
        type=int,
        metavar="PORT",
        help="ClickHouse HTTP port (default: 8123).",
    )
    p.add_argument(
        "--clickhouse-user",
        default="polytool_admin",
        metavar="USER",
        help="ClickHouse user (default: polytool_admin).",
    )
    p.add_argument(
        "--clickhouse-password",
        default=None,
        metavar="PASSWORD",
        help="ClickHouse password (falls back to CLICKHOUSE_PASSWORD env var).",
    )
    return p


def main(argv: Optional[List[str]] = None) -> int:
    """CLI entrypoint: python -m polytool capture-new-market-tapes [options]."""
    import os

    parser = _build_parser()
    args = parser.parse_args(argv)

    ch_password = args.clickhouse_password
    if ch_password is None:
        ch_password = os.environ.get("CLICKHOUSE_PASSWORD", "polytool_admin")

    targets_path = Path(args.targets_manifest)
    out_root = Path(args.out_root)
    batch_run_id = str(uuid.uuid4())

    # Load targets manifest
    targets, load_err = load_capture_targets(targets_path)
    if load_err:
        print(f"Error: --targets-manifest: {load_err}", file=sys.stderr)
        return 1

    mode_label = "DRY-RUN" if args.dry_run else "LIVE"
    print(f"[capture-new-market-tapes] [{mode_label}] targets={len(targets)}")
    print(f"  manifest: {targets_path}")
    print(f"  out-root: {out_root}")
    print(f"  batch_run_id: {batch_run_id}")

    # Run capture batch
    result = run_capture_batch(
        targets=targets,
        out_root=out_root,
        dry_run=args.dry_run,
        skip_metadata=args.skip_metadata,
        no_metadata_fallback=args.no_metadata_fallback,
        clickhouse_host=args.clickhouse_host,
        clickhouse_port=args.clickhouse_port,
        clickhouse_user=args.clickhouse_user,
        clickhouse_password=ch_password,
        batch_run_id=batch_run_id,
    )

    # Benchmark refresh (non-dry-run only)
    if args.benchmark_refresh and not args.dry_run:
        print("\n[capture-new-market-tapes] running benchmark refresh...")
        refresh = _refresh_benchmark_curation()
        result["benchmark_refresh"] = refresh
        if refresh.get("manifest_written"):
            print(f"  [benchmark-manifest] manifest written: {refresh.get('manifest_path')}")
        else:
            print(
                f"  [benchmark-manifest] outcome={refresh.get('outcome')} "
                f"gap_report={refresh.get('gap_report_path')}"
            )

    # Print summary
    print(f"\n[capture-new-market-tapes] complete")
    print(f"  targets_attempted: {result['targets_attempted']}")
    print(f"  tapes_created:     {result['tapes_created']}")
    print(f"  failure_count:     {result['failure_count']}")
    print(f"  skip_count:        {result['skip_count']}")
    meta = result["metadata_summary"]
    print(f"  metadata: ch={meta['clickhouse']} jsonl={meta['jsonl_fallback']} skipped={meta['skipped']}")

    for outcome in result["outcomes"]:
        status = outcome["status"]
        slug = (outcome.get("slug") or "")[:40]
        if status == "skip":
            print(f"  [SKIP] {slug}  reason={outcome.get('skip_reason', '')}")
        elif status == "success":
            events = outcome.get("event_count", 0)
            print(f"  [OK]   {slug}  events={events}")
        else:
            print(f"  [FAIL] {slug}  error={outcome.get('error', '')}")

    # Write result artifact
    result_path: Optional[Path] = None
    if args.result_out:
        result_path = Path(args.result_out)
    elif not args.dry_run:
        out_root.mkdir(parents=True, exist_ok=True)
        result_path = out_root / f"capture_run_{batch_run_id[:8]}.json"

    if result_path is not None:
        result_path.parent.mkdir(parents=True, exist_ok=True)
        result_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(f"\n  result artifact: {result_path}")

    # Exit non-zero only when zero tapes created with non-empty target list (non-dry-run)
    if result["tapes_created"] == 0 and result["targets_attempted"] > 0 and not args.dry_run:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
