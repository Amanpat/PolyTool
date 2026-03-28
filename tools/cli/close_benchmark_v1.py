"""CLI: close-benchmark-v1 — Benchmark v1 closure orchestration.

Runs four ordered stages:
  1. Preflight    — verify data readiness and connectivity
  2. Silver       — fetch price_2min + reconstruct Silver tapes for gap-fill targets
  3. New-market   — plan + record Gold tapes for new_market bucket
  4. Finalization — validate manifest or surface residual blockers

Exit codes:
  0  — config/benchmark_v1.tape_manifest created (closure achieved)
  1  — final status is blocked (quota not met or stage errors)
  2  — preflight blocked, no mutations attempted

Usage:
    python -m polytool close-benchmark-v1 [--dry-run] [--skip-silver]
                                          [--skip-new-market] [--out PATH]
                                          [--pmxt-root PATH] [--jon-root PATH]
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Schema + default path constants
# ---------------------------------------------------------------------------

RUN_SCHEMA = "benchmark_closure_run_v1"

GAP_FILL_TARGETS_PATH   = Path("config/benchmark_v1_gap_fill.targets.json")
NEW_MARKET_TARGETS_PATH = Path("config/benchmark_v1_new_market_capture.targets.json")
NEW_MARKET_INSUFF_PATH  = Path("config/benchmark_v1_new_market_capture.insufficiency.json")
MANIFEST_PATH           = Path("config/benchmark_v1.tape_manifest")
GAP_REPORT_PATH         = Path("config/benchmark_v1.gap_report.json")
GAP_FILL_INSUFF_PATH    = Path("config/benchmark_v1_gap_fill.insufficiency.json")
PRIORITY1_TOKENS_TXT    = Path("config/benchmark_v1_priority1_tokens.txt")
PRIORITY1_TOKENS_JSON   = Path("config/benchmark_v1_priority1_tokens.json")


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _check_clickhouse(
    host: str = "localhost",
    port: int = 8123,
    user: str = "polytool_admin",
    password: str = "",
) -> dict:
    """Probe ClickHouse availability via authenticated HTTP SELECT 1.  Never raises."""
    import base64
    import urllib.request
    url = f"http://{host}:{port}/?query=SELECT+1"
    try:
        req = urllib.request.Request(url)
        if user or password:
            creds = base64.b64encode(f"{user}:{password}".encode()).decode()
            req.add_header("Authorization", f"Basic {creds}")
        with urllib.request.urlopen(req, timeout=5) as resp:
            body = resp.read().decode("utf-8", errors="replace").strip()
            ok = resp.status == 200 and body == "1"
            if ok:
                return {"available": True, "url": url}
            return {"available": False, "url": url, "status": resp.status, "body": body}
    except Exception as exc:
        return {"available": False, "url": url, "error": str(exc)}


def _priority1_token_ids(targets: List[dict]) -> List[str]:
    """Return token IDs for priority-1 targets in a gap-fill targets list."""
    return [
        t["token_id"]
        for t in targets
        if isinstance(t, dict) and t.get("priority") == 1 and t.get("token_id")
    ]


def _all_unique_token_ids(targets: List[dict]) -> List[str]:
    """Return deduplicated token IDs from ALL targets (all priorities).

    Preserves first-seen order via dict.fromkeys.  Used so that
    fetch-price-2min covers every gap-fill target, not just priority-1.
    """
    return list(dict.fromkeys(
        t["token_id"]
        for t in targets
        if isinstance(t, dict) and t.get("token_id")
    ))


def _read_gap_report(path: Path = GAP_REPORT_PATH) -> Optional[dict]:
    """Read gap report JSON; return None on any failure."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _load_targets_manifest_safe(path: Path) -> Tuple[List[dict], Optional[str]]:
    """Thin wrapper so callers don't need to import batch_reconstruct_silver."""
    try:
        from tools.cli.batch_reconstruct_silver import load_targets_manifest
        return load_targets_manifest(path)
    except ImportError as exc:
        return [], f"batch_reconstruct_silver not importable: {exc}"


# ---------------------------------------------------------------------------
# Stage 1: Preflight
# ---------------------------------------------------------------------------


def run_preflight(
    *,
    clickhouse_host: str = "localhost",
    clickhouse_port: int = 8123,
    clickhouse_user: str = "polytool_admin",
    clickhouse_password: str = "",
    skip_silver: bool = False,
    skip_new_market: bool = False,
) -> dict:
    """Run preflight checks.  Never raises.  Returns structured result dict."""
    checks: Dict[str, Any] = {}
    blockers: List[str] = []
    warnings: List[str] = []

    # Short-circuit: manifest already exists — benchmark already closed
    if MANIFEST_PATH.exists():
        return {
            "status": "already_closed",
            "manifest_path": str(MANIFEST_PATH),
            "checks": {"manifest_already_exists": True},
            "blockers": [],
            "warnings": [],
        }

    checks["manifest_already_exists"] = False

    # Gap-fill targets manifest
    gft_exists = GAP_FILL_TARGETS_PATH.exists()
    checks["gap_fill_targets_exists"] = gft_exists
    if not gft_exists and not skip_silver:
        blockers.append(f"missing gap-fill targets manifest: {GAP_FILL_TARGETS_PATH}")

    # Count targets if manifest is present
    if gft_exists:
        targets, load_err = _load_targets_manifest_safe(GAP_FILL_TARGETS_PATH)
        if load_err:
            if not skip_silver:
                blockers.append(f"gap-fill targets manifest invalid: {load_err}")
        else:
            p1_count = len(_priority1_token_ids(targets))
            checks["gap_fill_targets_count"] = len(targets)
            checks["gap_fill_priority1_count"] = p1_count

    # ClickHouse availability
    ch = _check_clickhouse(
        clickhouse_host, clickhouse_port,
        user=clickhouse_user, password=clickhouse_password,
    )
    checks["clickhouse"] = ch
    if not ch["available"] and not skip_silver:
        warnings.append(
            f"ClickHouse not reachable at {clickhouse_host}:{clickhouse_port} — "
            "Silver stage metadata writes will use JSONL fallback"
        )

    # Prior insufficiency from gap-fill planner
    if GAP_FILL_INSUFF_PATH.exists():
        checks["gap_fill_insufficiency_exists"] = True
        try:
            insuff = json.loads(GAP_FILL_INSUFF_PATH.read_text(encoding="utf-8"))
            checks["gap_fill_insufficient_buckets"] = insuff.get("insufficient_buckets", [])
        except Exception:
            pass
    else:
        checks["gap_fill_insufficiency_exists"] = False

    # New-market targets from a previous run
    checks["new_market_targets_exists"] = NEW_MARKET_TARGETS_PATH.exists()

    # Live connectivity note for new-market stage
    if not skip_new_market:
        warnings.append(
            "new-market stage requires live Gamma API (discovery) "
            "and WS connectivity (tape recording)"
        )

    status = "blocked" if blockers else "ready"
    return {
        "status": status,
        "checks": checks,
        "blockers": blockers,
        "warnings": warnings,
    }


# ---------------------------------------------------------------------------
# Stage 2: Silver gap-fill
# ---------------------------------------------------------------------------


def run_silver_gap_fill_stage(
    *,
    dry_run: bool = False,
    pmxt_root: Optional[str] = None,
    jon_root: Optional[str] = None,
    out_root: Path = Path("artifacts"),
    clickhouse_host: str = "localhost",
    clickhouse_port: int = 8123,
    clickhouse_user: str = "polytool_admin",
    clickhouse_password: str = "",
    skip_price_2min: bool = False,
    run_id: Optional[str] = None,
    _fetch_price_2min_main=None,
) -> dict:
    """Execute the Silver gap-fill stage.

    1. Load ALL unique token IDs from the gap-fill targets manifest.
    2. Fetch price_2min for ALL those tokens (skipped in dry-run or --skip-price-2min).
    3. Run batch Silver reconstruction against all targets.
    4. Run benchmark curation refresh.

    Returns a structured stage outcome dict.
    """
    started_at = _utcnow()

    if not GAP_FILL_TARGETS_PATH.exists():
        return {
            "status": "skipped",
            "reason": f"gap-fill targets manifest not found: {GAP_FILL_TARGETS_PATH}",
            "started_at": started_at,
            "completed_at": _utcnow(),
        }

    targets, load_err = _load_targets_manifest_safe(GAP_FILL_TARGETS_PATH)
    if load_err:
        return {
            "status": "error",
            "reason": f"failed to load gap-fill targets manifest: {load_err}",
            "started_at": started_at,
            "completed_at": _utcnow(),
        }

    priority1_ids = _priority1_token_ids(targets)
    all_token_ids = _all_unique_token_ids(targets)

    # ---- fetch-price-2min ------------------------------------------------
    # Prefetch price_2min for ALL unique token IDs, not just priority-1.
    # The Silver reconstructor queries ClickHouse inline; tokens that were
    # never pre-fetched produce price_2min_missing warnings and confidence=none
    # empty tapes.  Covering the full set maximises confidence outcomes.
    fetch_outcome: Dict[str, Any] = {
        "token_count": len(all_token_ids),
        "priority1_count": len(priority1_ids),
        "status": "skipped",
    }

    if dry_run:
        fetch_outcome["status"] = "dry_run"
        fetch_outcome["planned_tokens"] = all_token_ids
    elif skip_price_2min:
        fetch_outcome["status"] = "skipped_flag"
    elif all_token_ids:
        print(
            f"[fetch-price-2min] prefetching price_2min for "
            f"{len(all_token_ids)} unique token IDs ({len(targets)} targets)"
        )
        try:
            if _fetch_price_2min_main is None:
                from tools.cli.fetch_price_2min import main as _fetch_price_2min_main  # type: ignore[assignment]
            argv: List[str] = []
            for tid in all_token_ids:
                argv += ["--token-id", tid]
            argv += [
                "--clickhouse-host", clickhouse_host,
                "--clickhouse-port", str(clickhouse_port),
                "--clickhouse-user", clickhouse_user,
                "--clickhouse-password", clickhouse_password,
            ]
            rc = _fetch_price_2min_main(argv)
            fetch_outcome["return_code"] = rc
            fetch_outcome["status"] = "success" if rc == 0 else "error"
        except Exception as exc:
            fetch_outcome["status"] = "error"
            fetch_outcome["error"] = str(exc)

    # ---- batch-reconstruct-silver + benchmark refresh --------------------
    recon_outcome: Dict[str, Any] = {}
    benchmark_refresh: Dict[str, Any] = {"triggered": False, "outcome": "not_requested"}

    if dry_run:
        recon_outcome = {
            "dry_run": True,
            "targets_count": len(targets),
            "priority1_count": len(priority1_ids),
            "note": "no files written; re-run without --dry-run to reconstruct tapes",
        }
        benchmark_refresh = {"triggered": False, "outcome": "dry_run"}
    else:
        try:
            from tools.cli.batch_reconstruct_silver import (
                _refresh_benchmark_curation,
                run_batch_from_targets,
            )
        except ImportError as exc:
            return {
                "status": "error",
                "reason": f"batch_reconstruct_silver not importable: {exc}",
                "started_at": started_at,
                "completed_at": _utcnow(),
                "fetch_price_2min": fetch_outcome,
            }

        try:
            batch_result = run_batch_from_targets(
                targets=targets,
                out_root=out_root,
                pmxt_root=pmxt_root,
                jon_root=jon_root,
                dry_run=False,
                skip_price_2min=skip_price_2min,
                clickhouse_host=clickhouse_host,
                clickhouse_port=clickhouse_port,
                clickhouse_user=clickhouse_user,
                clickhouse_password=clickhouse_password,
                batch_run_id=run_id,
            )
            failed = [
                {
                    "token_id": o.get("token_id"),
                    "bucket": o.get("bucket"),
                    "slug": o.get("slug"),
                    "error": o.get("error"),
                }
                for o in batch_result.get("outcomes", [])
                if o.get("status") == "failure"
            ]
            recon_outcome = {
                "schema_version": batch_result.get("schema_version"),
                "targets_attempted": batch_result.get("targets_attempted"),
                "tapes_created": batch_result.get("tapes_created"),
                "failure_count": batch_result.get("failure_count"),
                "skip_count": batch_result.get("skip_count"),
                "failed_targets": failed,
            }
        except Exception as exc:
            recon_outcome = {"status": "error", "error": str(exc)}

        try:
            benchmark_refresh = _refresh_benchmark_curation()
        except Exception as exc:
            benchmark_refresh = {
                "triggered": True,
                "outcome": "error",
                "error": str(exc),
            }

    return {
        "status": "dry_run" if dry_run else "completed",
        "started_at": started_at,
        "completed_at": _utcnow(),
        "targets_count": len(targets),
        "priority1_count": len(priority1_ids),
        "fetch_price_2min": fetch_outcome,
        "batch_reconstruct": recon_outcome,
        "benchmark_refresh": benchmark_refresh,
    }


# ---------------------------------------------------------------------------
# Stage 3: New-market closure
# ---------------------------------------------------------------------------


def run_new_market_stage(
    *,
    dry_run: bool = False,
    _new_market_capture_main=None,
    _capture_new_market_tapes_main=None,
) -> dict:
    """Execute the new-market closure stage.

    1. Run new-market-capture planner (live Gamma API).
    2. If target manifest has candidates, run capture-new-market-tapes
       with --benchmark-refresh.

    Returns a structured stage outcome dict.
    """
    started_at = _utcnow()

    if dry_run:
        return {
            "status": "dry_run",
            "started_at": started_at,
            "completed_at": _utcnow(),
            "planner": {
                "dry_run": True,
                "status": "skipped",
                "note": "new-market-capture requires live Gamma API connectivity",
            },
            "capture": {"dry_run": True, "status": "skipped"},
            "benchmark_refresh": {"triggered": False, "outcome": "dry_run"},
        }

    # ---- new-market-capture planner -------------------------------------
    planner_outcome: Dict[str, Any] = {}
    try:
        if _new_market_capture_main is None:
            from tools.cli.new_market_capture import main as _new_market_capture_main  # type: ignore[assignment]
        planner_rc = _new_market_capture_main([])
        planner_outcome = {
            "return_code": planner_rc,
            "status": (
                "success"      if planner_rc == 0
                else "insufficient" if planner_rc == 2
                else "error"
            ),
        }
        if NEW_MARKET_TARGETS_PATH.exists():
            try:
                nm_data = json.loads(NEW_MARKET_TARGETS_PATH.read_text(encoding="utf-8"))
                planner_outcome["targets_count"] = len(nm_data.get("targets", []))
                planner_outcome["sufficient"] = planner_rc == 0
            except Exception:
                pass
    except Exception as exc:
        planner_outcome = {"status": "error", "error": str(exc), "return_code": -1}

    # ---- capture-new-market-tapes + benchmark refresh -------------------
    capture_outcome: Dict[str, Any] = {}
    benchmark_refresh: Dict[str, Any] = {"triggered": False, "outcome": "not_requested"}

    planner_rc_val = planner_outcome.get("return_code", 1)
    has_targets = NEW_MARKET_TARGETS_PATH.exists()

    if planner_rc_val in (0, 2) and has_targets:
        try:
            if _capture_new_market_tapes_main is None:
                from tools.cli.capture_new_market_tapes import main as _capture_new_market_tapes_main  # type: ignore[assignment]
            capture_rc = _capture_new_market_tapes_main(["--benchmark-refresh"])
            capture_outcome = {
                "return_code": capture_rc,
                "status": "success" if capture_rc == 0 else "error",
            }
            # Determine refresh outcome from artifact state
            if MANIFEST_PATH.exists():
                benchmark_refresh = {
                    "triggered": True,
                    "manifest_written": True,
                    "outcome": "manifest_written",
                    "manifest_path": str(MANIFEST_PATH),
                }
            elif GAP_REPORT_PATH.exists():
                benchmark_refresh = {
                    "triggered": True,
                    "manifest_written": False,
                    "outcome": "gap_report_updated",
                    "gap_report_path": str(GAP_REPORT_PATH),
                }
            else:
                benchmark_refresh = {
                    "triggered": True,
                    "manifest_written": False,
                    "outcome": "unknown",
                }
        except Exception as exc:
            capture_outcome = {"status": "error", "error": str(exc)}
    else:
        reason = (
            "planner returned no candidates" if planner_rc_val == 1
            else "planner error"              if planner_rc_val < 0
            else "new-market targets file not written"
        )
        capture_outcome = {"status": "skipped", "reason": reason}

    return {
        "status": "completed",
        "started_at": started_at,
        "completed_at": _utcnow(),
        "planner": planner_outcome,
        "capture": capture_outcome,
        "benchmark_refresh": benchmark_refresh,
    }


# ---------------------------------------------------------------------------
# Stage 4: Finalization
# ---------------------------------------------------------------------------


def run_finalization() -> dict:
    """Check manifest or surface residual blockers from the gap report."""
    started_at = _utcnow()

    if MANIFEST_PATH.exists():
        try:
            manifest_data = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
            tape_count = len(manifest_data) if isinstance(manifest_data, list) else "unknown"
            return {
                "status": "manifest_created",
                "manifest_path": str(MANIFEST_PATH),
                "tape_count": tape_count,
                "started_at": started_at,
                "completed_at": _utcnow(),
                "blockers": [],
            }
        except Exception as exc:
            return {
                "status": "manifest_invalid",
                "manifest_path": str(MANIFEST_PATH),
                "error": str(exc),
                "started_at": started_at,
                "completed_at": _utcnow(),
                "blockers": [f"manifest exists but is invalid JSON: {exc}"],
            }

    # Manifest absent — surface residual blockers
    blockers: List[str] = []
    gap_report = _read_gap_report(GAP_REPORT_PATH)
    if gap_report:
        shortages = gap_report.get("shortages_by_bucket", {})
        for bucket, shortage in shortages.items():
            if isinstance(shortage, (int, float)) and shortage > 0:
                blockers.append(f"bucket '{bucket}': shortage={int(shortage)}")
        if not shortages and not blockers:
            blockers.append("benchmark quota not met; gap report has no shortage details")
    else:
        blockers.append("benchmark quota not met; gap report unavailable")

    # New-market insufficiency
    if NEW_MARKET_INSUFF_PATH.exists():
        try:
            insuff = json.loads(NEW_MARKET_INSUFF_PATH.read_text(encoding="utf-8"))
            reason = insuff.get("insufficiency_reason", "")
            candidates = insuff.get("candidates_found", "unknown")
            blockers.append(
                f"new_market bucket: planner found {candidates} candidates "
                f"(need 5); reason: {reason}"
            )
        except Exception:
            blockers.append("new_market bucket: insufficiency report exists but unreadable")

    return {
        "status": "blocked",
        "manifest_path": None,
        "started_at": started_at,
        "completed_at": _utcnow(),
        "blockers": blockers,
        "gap_report_path": str(GAP_REPORT_PATH) if GAP_REPORT_PATH.exists() else None,
    }


# ---------------------------------------------------------------------------
# Orchestration core
# ---------------------------------------------------------------------------


def _build_run_artifact(
    *,
    run_id: str,
    started_at: str,
    dry_run: bool,
    preflight: dict,
    silver_stage: dict,
    new_market_stage: dict,
    finalization: dict,
) -> dict:
    final_status = finalization.get("status", "blocked")
    top_status = "manifest_created" if final_status == "manifest_created" else "blocked"
    return {
        "schema_version": RUN_SCHEMA,
        "run_id": run_id,
        "started_at": started_at,
        "completed_at": _utcnow(),
        "dry_run": dry_run,
        "final_status": top_status,
        "preflight": preflight,
        "silver_gap_fill": silver_stage,
        "new_market_capture": new_market_stage,
        "finalization": finalization,
        "residual_blockers": finalization.get("blockers", []),
        "manifest_path": finalization.get("manifest_path"),
    }


def _write_run_artifact(
    artifact: dict,
    out_path: Optional[Path],
    run_id: str,
    started_at: str,
) -> Optional[Path]:
    if out_path is None:
        date_str = started_at[:10]
        out_path = (
            Path("artifacts") / "benchmark_closure" / date_str / run_id
            / "benchmark_closure_run_v1.json"
        )
    try:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(artifact, indent=2), encoding="utf-8")
        print(f"\n[close-benchmark-v1] run artifact: {out_path}")
        return out_path
    except Exception as exc:
        print(
            f"\n[close-benchmark-v1] WARNING: failed to write run artifact: {exc}",
            file=sys.stderr,
        )
        return None


def _print_stage_summary(name: str, stage: dict) -> None:
    status = stage.get("status", "unknown")
    print(f"  status: {status}")
    reason = stage.get("reason")
    if reason:
        print(f"  reason: {reason}")
    br = stage.get("benchmark_refresh", {})
    if br.get("manifest_written"):
        print(f"  [OK] benchmark manifest written: {br.get('manifest_path')}")
    elif br.get("triggered"):
        print(f"  benchmark_refresh: outcome={br.get('outcome')}")


def run_closure(
    *,
    dry_run: bool = False,
    skip_silver: bool = False,
    skip_new_market: bool = False,
    out_path: Optional[Path] = None,
    pmxt_root: Optional[str] = None,
    jon_root: Optional[str] = None,
    clickhouse_host: str = "localhost",
    clickhouse_port: int = 8123,
    clickhouse_user: str = "polytool_admin",
    clickhouse_password: str = "",
    skip_price_2min: bool = False,
    # Test injection hooks — passed through to stage runners
    _fetch_price_2min_main=None,
    _new_market_capture_main=None,
    _capture_new_market_tapes_main=None,
) -> Tuple[dict, int]:
    """Run the full benchmark closure orchestration.

    Returns (run_artifact_dict, exit_code).
    Exit codes: 0 = manifest_created, 1 = blocked, 2 = preflight_blocked.
    """
    run_id = str(uuid.uuid4())
    started_at = _utcnow()

    # ---- Stage 1: Preflight -----------------------------------------------
    print("[close-benchmark-v1] starting run")
    if dry_run:
        print("  mode: DRY-RUN (no mutations)")
    print("\n[close-benchmark-v1] Stage 1: Preflight")
    preflight = run_preflight(
        clickhouse_host=clickhouse_host,
        clickhouse_port=clickhouse_port,
        clickhouse_user=clickhouse_user,
        clickhouse_password=clickhouse_password,
        skip_silver=skip_silver,
        skip_new_market=skip_new_market,
    )
    for b in preflight.get("blockers", []):
        print(f"  [BLOCKER] {b}")
    for w in preflight.get("warnings", []):
        print(f"  [WARNING] {w}")

    if preflight["status"] == "already_closed":
        print(f"  [OK] benchmark already closed: {MANIFEST_PATH}")
        artifact = _build_run_artifact(
            run_id=run_id, started_at=started_at, dry_run=dry_run,
            preflight=preflight,
            silver_stage={"status": "skipped", "reason": "manifest already exists"},
            new_market_stage={"status": "skipped", "reason": "manifest already exists"},
            finalization={
                "status": "manifest_created",
                "manifest_path": str(MANIFEST_PATH),
                "blockers": [],
            },
        )
        _write_run_artifact(artifact, out_path, run_id, started_at)
        return artifact, 0

    if preflight["status"] == "blocked":
        print(f"  [BLOCKED] preflight failed — {len(preflight['blockers'])} blocker(s)")
        finalization: dict = {
            "status": "blocked",
            "blockers": preflight["blockers"],
            "manifest_path": None,
        }
        artifact = _build_run_artifact(
            run_id=run_id, started_at=started_at, dry_run=dry_run,
            preflight=preflight,
            silver_stage={"status": "skipped", "reason": "preflight blocked"},
            new_market_stage={"status": "skipped", "reason": "preflight blocked"},
            finalization=finalization,
        )
        _write_run_artifact(artifact, out_path, run_id, started_at)
        return artifact, 2

    print("  [OK] preflight passed")

    # ---- Stage 2: Silver gap-fill -----------------------------------------
    if skip_silver:
        print("\n[close-benchmark-v1] Stage 2: Silver gap-fill — skipped (--skip-silver)")
        silver_stage: dict = {"status": "skipped", "reason": "--skip-silver flag"}
    else:
        print("\n[close-benchmark-v1] Stage 2: Silver gap-fill")
        silver_stage = run_silver_gap_fill_stage(
            dry_run=dry_run,
            pmxt_root=pmxt_root,
            jon_root=jon_root,
            out_root=Path("artifacts"),
            clickhouse_host=clickhouse_host,
            clickhouse_port=clickhouse_port,
            clickhouse_user=clickhouse_user,
            clickhouse_password=clickhouse_password,
            skip_price_2min=skip_price_2min,
            run_id=run_id,
            _fetch_price_2min_main=_fetch_price_2min_main,
        )
        _print_stage_summary("silver", silver_stage)

    # ---- Stage 3: New-market closure --------------------------------------
    if skip_new_market:
        print("\n[close-benchmark-v1] Stage 3: New-market — skipped (--skip-new-market)")
        new_market_stage: dict = {"status": "skipped", "reason": "--skip-new-market flag"}
    else:
        print("\n[close-benchmark-v1] Stage 3: New-market closure")
        new_market_stage = run_new_market_stage(
            dry_run=dry_run,
            _new_market_capture_main=_new_market_capture_main,
            _capture_new_market_tapes_main=_capture_new_market_tapes_main,
        )
        _print_stage_summary("new_market", new_market_stage)

    # ---- Stage 4: Finalization --------------------------------------------
    print("\n[close-benchmark-v1] Stage 4: Finalization")
    finalization = run_finalization()
    final_status = finalization["status"]
    print(f"  final_status: {final_status}")
    if finalization.get("manifest_path"):
        print(f"  manifest: {finalization['manifest_path']}")
    for b in finalization.get("blockers", []):
        print(f"  [BLOCKER] {b}")

    # ---- Build + write run artifact ---------------------------------------
    artifact = _build_run_artifact(
        run_id=run_id, started_at=started_at, dry_run=dry_run,
        preflight=preflight,
        silver_stage=silver_stage,
        new_market_stage=new_market_stage,
        finalization=finalization,
    )
    _write_run_artifact(artifact, out_path, run_id, started_at)

    exit_code = 0 if final_status == "manifest_created" else 1
    return artifact, exit_code


# ---------------------------------------------------------------------------
# CLI surface
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Operator helpers: token export + status
# ---------------------------------------------------------------------------


def run_export_tokens(
    *,
    out_txt: Path = PRIORITY1_TOKENS_TXT,
    out_json: Path = PRIORITY1_TOKENS_JSON,
) -> int:
    """Export priority-1 token IDs from the gap-fill targets manifest.

    Writes:
      - config/benchmark_v1_priority1_tokens.txt  (one token per line)
      - config/benchmark_v1_priority1_tokens.json (list of strings)

    Returns 0 on success, 1 on failure.
    """
    if not GAP_FILL_TARGETS_PATH.exists():
        print(
            f"[close-benchmark-v1] ERROR: gap-fill targets manifest not found: "
            f"{GAP_FILL_TARGETS_PATH}",
            file=sys.stderr,
        )
        print(
            "  Run: python -m polytool benchmark-manifest  "
            "(or the gap-fill planner) to generate it.",
            file=sys.stderr,
        )
        return 1

    targets, load_err = _load_targets_manifest_safe(GAP_FILL_TARGETS_PATH)
    if load_err:
        print(f"[close-benchmark-v1] ERROR loading targets manifest: {load_err}", file=sys.stderr)
        return 1

    token_ids = _priority1_token_ids(targets)
    if not token_ids:
        print(
            "[close-benchmark-v1] WARNING: no priority-1 targets found in manifest",
            file=sys.stderr,
        )

    out_txt.parent.mkdir(parents=True, exist_ok=True)
    out_txt.write_text("\n".join(token_ids) + ("\n" if token_ids else ""), encoding="utf-8")
    out_json.write_text(json.dumps(token_ids, indent=2), encoding="utf-8")

    print(f"[close-benchmark-v1] Exported {len(token_ids)} priority-1 token IDs")
    print(f"  source: {GAP_FILL_TARGETS_PATH}")
    print(f"  txt:    {out_txt}")
    print(f"  json:   {out_json}")
    return 0


def _find_latest_run_artifact() -> Optional[Path]:
    """Return the path to the newest benchmark_closure_run_v1.json, or None."""
    closure_root = Path("artifacts") / "benchmark_closure"
    if not closure_root.exists():
        return None
    candidates = sorted(closure_root.rglob("benchmark_closure_run_v1.json"))
    return candidates[-1] if candidates else None


def run_status() -> int:
    """Print a human-readable status summary of benchmark closure progress.

    Returns 0 always (status queries are informational).
    """
    width = 72
    print("=" * width)
    print(f"  benchmark_v1 closure status  ({_utcnow()[:19]}Z)")
    print("=" * width)

    # Manifest
    manifest_ok = MANIFEST_PATH.exists()
    print(f"\n  Manifest:             {'CREATED  ' if manifest_ok else 'MISSING  '} {MANIFEST_PATH}")
    if manifest_ok:
        print("  *** benchmark_v1 is CLOSED — config/benchmark_v1.tape_manifest exists ***")

    # Gap-fill targets
    gft_ok = GAP_FILL_TARGETS_PATH.exists()
    if gft_ok:
        targets, load_err = _load_targets_manifest_safe(GAP_FILL_TARGETS_PATH)
        if load_err:
            print(f"  Gap-fill targets:     ERROR    {GAP_FILL_TARGETS_PATH} (parse error: {load_err})")
        else:
            p1 = _priority1_token_ids(targets)
            print(
                f"  Gap-fill targets:     FOUND    {GAP_FILL_TARGETS_PATH}"
                f"  ({len(targets)} targets, {len(p1)} priority-1)"
            )
    else:
        print(f"  Gap-fill targets:     MISSING  {GAP_FILL_TARGETS_PATH}")

    # Priority-1 token export
    tok_txt_ok = PRIORITY1_TOKENS_TXT.exists()
    tok_json_ok = PRIORITY1_TOKENS_JSON.exists()
    if tok_txt_ok:
        lines = PRIORITY1_TOKENS_TXT.read_text(encoding="utf-8").splitlines()
        n = len([l for l in lines if l.strip()])
        print(f"  Token export (.txt):  FOUND    {PRIORITY1_TOKENS_TXT}  ({n} tokens)")
    else:
        print(f"  Token export (.txt):  MISSING  {PRIORITY1_TOKENS_TXT}")
    if tok_json_ok:
        print(f"  Token export (.json): FOUND    {PRIORITY1_TOKENS_JSON}")
    else:
        print(f"  Token export (.json): MISSING  {PRIORITY1_TOKENS_JSON}")

    # New-market targets
    nm_ok = NEW_MARKET_TARGETS_PATH.exists()
    print(f"  New-market targets:   {'FOUND    ' if nm_ok else 'MISSING  '} {NEW_MARKET_TARGETS_PATH}")

    # Latest closure run
    latest = _find_latest_run_artifact()
    if latest:
        try:
            run_data = json.loads(latest.read_text(encoding="utf-8"))
            dry = run_data.get("dry_run", False)
            status = run_data.get("final_status", "unknown")
            started = run_data.get("started_at", "")[:10]
            print(f"  Latest run:           {started}  {latest.parent.name}  [{status}, dry_run={dry}]")
        except Exception:
            print(f"  Latest run:           {latest.parent.name}  (unreadable)")
    else:
        print(f"  Latest run:           none found under artifacts/benchmark/")

    # Residual blockers from gap report
    gap_report = _read_gap_report(GAP_REPORT_PATH)
    if gap_report:
        shortages = gap_report.get("shortages_by_bucket", {})
        active = [(k, v) for k, v in shortages.items() if isinstance(v, (int, float)) and v > 0]
        if active:
            print(f"\n  Residual blockers (from {GAP_REPORT_PATH}):")
            for bucket, shortage in active:
                print(f"    • bucket '{bucket}': shortage={int(shortage)}")
        else:
            print(f"\n  No residual blockers in gap report.")
    else:
        if not manifest_ok:
            print(f"\n  Gap report not found: {GAP_REPORT_PATH}")

    # New-market insufficiency
    if NEW_MARKET_INSUFF_PATH.exists():
        try:
            insuff = json.loads(NEW_MARKET_INSUFF_PATH.read_text(encoding="utf-8"))
            candidates = insuff.get("candidates_found", "unknown")
            reason = insuff.get("insufficiency_reason", "")
            print(f"  New-market insuff:   {candidates} candidates found (need 5); {reason}")
        except Exception:
            print(f"  New-market insuff:   file exists but unreadable")

    # Suggested next step
    print(f"\n  Suggested next step:")
    if manifest_ok:
        print("    Nothing — benchmark is closed. Proceed to Gate 2 scenario sweep.")
    elif not gft_ok:
        print("    Run: python -m polytool benchmark-manifest  (to generate gap report + targets)")
    elif not tok_txt_ok:
        print(
            "    1. Export tokens:   python -m polytool close-benchmark-v1 --export-tokens\n"
            "    2. Start Docker:    docker compose up -d\n"
            "    3. Fetch prices:    python -m polytool fetch-price-2min"
            " --token-id $(cat config/benchmark_v1_priority1_tokens.txt | head -1) ...\n"
            "       (see RUNBOOK: docs/runbooks/BENCHMARK_CLOSURE_RUNBOOK.md)"
        )
    else:
        print(
            "    1. Start Docker:    docker compose up -d\n"
            "    2. Fetch prices:    see docs/runbooks/BENCHMARK_CLOSURE_RUNBOOK.md step 3\n"
            "    3. Close Silver:    python -m polytool close-benchmark-v1"
            " --skip-new-market --pmxt-root <path> --jon-root <path>"
        )

    print("=" * width)
    return 0


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="close-benchmark-v1",
        description=(
            "Benchmark v1 closure orchestration.\n\n"
            "Runs preflight, Silver gap-fill, new-market capture, and finalization\n"
            "in sequence, then emits a machine-readable closure status artifact.\n\n"
            "Exit 0 = manifest_created  |  exit 1 = blocked  |  exit 2 = preflight_blocked"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--dry-run", action="store_true",
                   help="Planning/preflight only; no mutations performed.")
    p.add_argument("--skip-silver", action="store_true",
                   help="Skip the Silver gap-fill stage entirely.")
    p.add_argument("--skip-new-market", action="store_true",
                   help="Skip the new-market capture stage entirely.")
    p.add_argument("--out", default=None, metavar="PATH",
                   help="Override the canonical run artifact output path.")
    p.add_argument("--pmxt-root", default=None, metavar="PATH",
                   help="Root directory of the pmxt_archive dataset.")
    p.add_argument("--jon-root", default=None, metavar="PATH",
                   help="Root directory of the jon_becker dataset.")
    p.add_argument("--clickhouse-host", default="localhost", metavar="HOST")
    p.add_argument("--clickhouse-port", default=8123, type=int, metavar="PORT")
    p.add_argument("--clickhouse-user", default="polytool_admin", metavar="USER")
    p.add_argument("--clickhouse-password", default=None, metavar="PASSWORD")
    p.add_argument("--skip-price-2min", action="store_true",
                   help="Skip the fetch-price-2min call in the Silver stage.")
    p.add_argument("--status", action="store_true",
                   help="Print a human-readable status summary and exit.")
    p.add_argument("--export-tokens", action="store_true",
                   help="Export priority-1 token IDs to config/ and exit.")
    return p


def main(argv: Optional[List[str]] = None) -> int:
    """CLI entrypoint: python -m polytool close-benchmark-v1 [options]."""
    import os

    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.status:
        return run_status()

    if args.export_tokens:
        return run_export_tokens()

    ch_password = args.clickhouse_password
    if ch_password is None:
        ch_password = os.environ.get("CLICKHOUSE_PASSWORD")
    if not ch_password:
        print(
            "Error: ClickHouse password not set.\n"
            "  Pass --clickhouse-password PASSWORD, or export CLICKHOUSE_PASSWORD=<password>.",
            file=sys.stderr,
        )
        return 1

    out_path = Path(args.out) if args.out else None

    _, exit_code = run_closure(
        dry_run=args.dry_run,
        skip_silver=args.skip_silver,
        skip_new_market=args.skip_new_market,
        out_path=out_path,
        pmxt_root=args.pmxt_root,
        jon_root=args.jon_root,
        clickhouse_host=args.clickhouse_host,
        clickhouse_port=args.clickhouse_port,
        clickhouse_user=args.clickhouse_user,
        clickhouse_password=ch_password,
        skip_price_2min=args.skip_price_2min,
    )
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
