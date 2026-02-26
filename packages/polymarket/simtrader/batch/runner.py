"""Batch runner: pick N markets, run a quicksweep per market, aggregate results.

Usage (via CLI):
    python -m polytool simtrader batch \\
        --preset quick --num-markets 5 --duration 300

Artifacts layout::

    artifacts/simtrader/batches/<batch_id>/
        batch_manifest.json       # params, seed, market list
        batch_summary.json        # per-market aggregated rows
        batch_summary.csv         # same data as CSV (for spreadsheets)
        markets/
            <slug>/
                sweep_manifest.json
                sweep_summary.json
                tape_meta.json    # copy of tape/meta.json
                runs/
                    <scenario_id>/
                        ...

Idempotency: if ``markets/<slug>/sweep_summary.json`` already exists this
market is skipped unless ``rerun=True``.
"""

from __future__ import annotations

import csv
import hashlib
import json
import shutil
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Optional

from ..market_picker import MarketPicker, MarketPickerError
from ..strategy_presets import (
    build_binary_complement_strategy_config,
    normalize_strategy_preset,
)
from ..sweeps.runner import SweepRunParams, run_sweep
from ..tape.recorder import TapeRecorder
from ..tape.schema import EVENT_TYPE_BOOK, EVENT_TYPE_PRICE_CHANGE


class BatchRunError(ValueError):
    """Raised when the batch cannot start due to invalid parameters."""


@dataclass(frozen=True)
class BatchRunParams:
    """Parameters for one batch run."""

    num_markets: int = 5
    preset: str = "quick"
    strategy_preset: str = "sane"
    duration: float = 300.0
    starting_cash: Decimal = field(default_factory=lambda: Decimal("1000"))
    fee_rate_bps: Optional[Decimal] = None
    mark_method: str = "bid"
    max_candidates: int = 100
    min_events: int = 0
    allow_empty_book: bool = False
    min_depth_size: float = 0.0
    top_n_levels: int = 3
    artifacts_root: Path = field(default_factory=lambda: Path("artifacts/simtrader"))
    batch_id: Optional[str] = None
    rerun: bool = False
    time_budget_seconds: Optional[float] = None


@dataclass
class _MarketRow:
    slug: str
    question: str
    yes_token_id: str
    no_token_id: str
    tape_path: Optional[str]
    tape_events_count: int
    tape_bbo_rows: int
    yes_snapshot: bool
    no_snapshot: bool
    best_net_profit: Optional[str]
    median_net_profit: Optional[str]
    worst_net_profit: Optional[str]
    best_scenario: Optional[str]
    total_scenarios: int
    total_orders: int
    total_decisions: int
    total_fills: int
    dominant_rejection_key: Optional[str]
    dominant_rejection_count: int
    status: str  # "ok" | "skipped" | "error"
    error_msg: Optional[str] = None
    sweep_dir: Optional[str] = None
    tape_dir: Optional[str] = None


@dataclass(frozen=True)
class BatchRunResult:
    """Outcome of a completed batch run."""

    batch_id: str
    batch_dir: Path
    summary: dict[str, Any]
    manifest: dict[str, Any]


@dataclass(frozen=True)
class _RunStats:
    total_orders: int
    total_decisions: int
    total_fills: int
    dominant_rejection_key: Optional[str]
    dominant_rejection_count: int


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def run_batch(
    params: BatchRunParams,
    gamma_client,
    clob_client,
    sweep_config_factory,
) -> BatchRunResult:
    """Run a batch of quicksweeps and produce aggregated artifacts.

    Args:
        params:               Batch configuration.
        gamma_client:         GammaClient instance (for MarketPicker).
        clob_client:          ClobClient instance (for MarketPicker).
        sweep_config_factory: Callable() → sweep config dict (the preset).

    Returns:
        BatchRunResult with paths and aggregated summary.
    """
    # -- Validate params -------------------------------------------------------
    if params.num_markets < 1 or params.num_markets > 200:
        raise BatchRunError(
            f"num_markets must be between 1 and 200 (got {params.num_markets})"
        )
    if params.max_candidates < 1 or params.max_candidates > 100:
        raise BatchRunError(
            f"max_candidates must be between 1 and 100 (got {params.max_candidates})"
        )
    if params.max_candidates < params.num_markets:
        raise BatchRunError(
            f"max_candidates ({params.max_candidates}) must be >= "
            f"num_markets ({params.num_markets})"
        )
    if params.min_events < 0:
        raise BatchRunError(
            f"min_events must be non-negative (got {params.min_events})"
        )
    if params.min_depth_size < 0:
        raise BatchRunError(
            f"min_depth_size must be non-negative (got {params.min_depth_size})"
        )
    if params.top_n_levels < 1:
        raise BatchRunError(
            f"top_n_levels must be >= 1 (got {params.top_n_levels})"
        )
    if params.time_budget_seconds is not None and params.time_budget_seconds <= 0:
        raise BatchRunError(
            "time_budget_seconds must be > 0 when provided "
            f"(got {params.time_budget_seconds})"
        )
    try:
        strategy_preset = normalize_strategy_preset(params.strategy_preset)
    except ValueError as exc:
        raise BatchRunError(str(exc)) from exc

    # -- Batch ID / dir --------------------------------------------------------
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    batch_id = params.batch_id or _derive_batch_id(params, ts)
    batch_dir = params.artifacts_root / "batches" / batch_id
    markets_dir = batch_dir / "markets"
    markets_dir.mkdir(parents=True, exist_ok=True)

    # -- Pick markets ----------------------------------------------------------
    picker = MarketPicker(gamma_client, clob_client)
    markets = picker.auto_pick_many(
        n=params.num_markets,
        max_candidates=params.max_candidates,
        allow_empty_book=params.allow_empty_book,
        min_depth_size=params.min_depth_size,
        top_n_levels=params.top_n_levels,
    )

    if not markets:
        raise MarketPickerError(
            f"no valid binary markets found in {params.max_candidates} candidates"
        )

    # -- Write manifest (before running so it exists even on partial failure) --
    manifest: dict[str, Any] = {
        "batch_id": batch_id,
        "created_at": ts,
        "seed": _derive_seed(params),
        "preset": params.preset,
        "strategy_preset": strategy_preset,
        "num_markets_requested": params.num_markets,
        "num_markets_found": len(markets),
        "duration": params.duration,
        "starting_cash": str(params.starting_cash),
        "fee_rate_bps": str(params.fee_rate_bps) if params.fee_rate_bps is not None else None,
        "mark_method": params.mark_method,
        "max_candidates": params.max_candidates,
        "min_events": params.min_events,
        "allow_empty_book": params.allow_empty_book,
        "min_depth_size": params.min_depth_size,
        "top_n_levels": params.top_n_levels,
        "rerun": params.rerun,
        "time_budget_seconds": params.time_budget_seconds,
        "markets": [
            {
                "slug": m.slug,
                "question": m.question,
                "yes_token_id": m.yes_token_id,
                "no_token_id": m.no_token_id,
                "mapping_tier": getattr(m, "mapping_tier", "explicit"),
            }
            for m in markets
        ],
    }
    _write_json(batch_dir / "batch_manifest.json", manifest)

    # -- Process each market ---------------------------------------------------
    rows: list[_MarketRow] = []
    sweep_config = sweep_config_factory()
    batch_start_monotonic = time.monotonic()

    for idx, resolved in enumerate(markets):
        if params.time_budget_seconds is not None:
            elapsed = time.monotonic() - batch_start_monotonic
            if elapsed >= params.time_budget_seconds:
                remaining = markets[idx:]
                print(
                    "[batch] time budget exhausted "
                    f"({elapsed:.1f}s >= {params.time_budget_seconds:.1f}s); "
                    f"skipping {len(remaining)} remaining market(s).",
                    file=sys.stderr,
                )
                for pending in remaining:
                    rows.append(_time_budget_skipped_row(pending))
                break
        row = _run_market(
            resolved=resolved,
            params=params,
            markets_dir=markets_dir,
            sweep_config=sweep_config,
            ts=ts,
        )
        rows.append(row)

    # -- Aggregate + write summary --------------------------------------------
    summary = _build_summary(batch_id, ts, params, rows)
    _write_json(batch_dir / "batch_summary.json", summary)
    _write_csv(batch_dir / "batch_summary.csv", rows)

    return BatchRunResult(
        batch_id=batch_id,
        batch_dir=batch_dir,
        summary=summary,
        manifest=manifest,
    )


def _time_budget_skipped_row(resolved) -> _MarketRow:
    """Return a skipped row for markets not launched due to elapsed time budget."""
    return _MarketRow(
        slug=resolved.slug,
        question=resolved.question,
        yes_token_id=resolved.yes_token_id,
        no_token_id=resolved.no_token_id,
        tape_path=None,
        tape_events_count=0,
        tape_bbo_rows=0,
        yes_snapshot=False,
        no_snapshot=False,
        best_net_profit=None,
        median_net_profit=None,
        worst_net_profit=None,
        best_scenario=None,
        total_scenarios=0,
        total_orders=0,
        total_decisions=0,
        total_fills=0,
        dominant_rejection_key=None,
        dominant_rejection_count=0,
        status="skipped",
        error_msg="time_budget_exceeded",
    )


# ---------------------------------------------------------------------------
# Per-market logic
# ---------------------------------------------------------------------------


def _run_market(
    resolved,
    params: BatchRunParams,
    markets_dir: Path,
    sweep_config: dict[str, Any],
    ts: str,
) -> _MarketRow:
    """Record tape + run sweep for one market, return aggregated row."""

    slug = resolved.slug
    market_dir = markets_dir / slug
    sweep_summary_path = market_dir / "sweep_summary.json"

    # -- Idempotency check -----------------------------------------------------
    if sweep_summary_path.exists() and not params.rerun:
        # Load existing summary and return as "skipped"
        try:
            existing_summary = json.loads(sweep_summary_path.read_text(encoding="utf-8"))
            agg = existing_summary.get("aggregate", {})
            scenarios = existing_summary.get("scenarios", [])
            run_stats = _aggregate_run_stats(market_dir / "runs")
            return _MarketRow(
                slug=slug,
                question=resolved.question,
                yes_token_id=resolved.yes_token_id,
                no_token_id=resolved.no_token_id,
                tape_path=None,
                tape_events_count=0,
                tape_bbo_rows=0,
                yes_snapshot=False,
                no_snapshot=False,
                best_net_profit=str(agg.get("best_net_profit", "0")),
                median_net_profit=str(agg.get("median_net_profit", "0")),
                worst_net_profit=str(agg.get("worst_net_profit", "0")),
                best_scenario=agg.get("best_scenario"),
                total_scenarios=len(scenarios),
                total_orders=run_stats.total_orders,
                total_decisions=run_stats.total_decisions,
                total_fills=run_stats.total_fills,
                dominant_rejection_key=run_stats.dominant_rejection_key,
                dominant_rejection_count=run_stats.dominant_rejection_count,
                status="skipped",
                sweep_dir=str(market_dir),
            )
        except Exception:  # noqa: BLE001
            pass  # fall through and re-run

    market_dir.mkdir(parents=True, exist_ok=True)

    # -- Record tape -----------------------------------------------------------
    tape_dir = params.artifacts_root / "tapes" / f"{ts}_batch_{slug[:16]}_{resolved.yes_token_id[:8]}"
    recorder = TapeRecorder(
        tape_dir=tape_dir,
        asset_ids=[resolved.yes_token_id, resolved.no_token_id],
        strict=False,
    )
    try:
        recorder.record(duration_seconds=params.duration)
    except Exception as exc:  # noqa: BLE001
        return _MarketRow(
            slug=slug,
            question=resolved.question,
            yes_token_id=resolved.yes_token_id,
            no_token_id=resolved.no_token_id,
            tape_path=None,
            tape_events_count=0,
            tape_bbo_rows=0,
            yes_snapshot=False,
            no_snapshot=False,
            best_net_profit=None,
            median_net_profit=None,
            worst_net_profit=None,
            best_scenario=None,
            total_scenarios=0,
            total_orders=0,
            total_decisions=0,
            total_fills=0,
            dominant_rejection_key=None,
            dominant_rejection_count=0,
            status="error",
            error_msg=f"tape recording failed: {exc}",
        )

    events_path = tape_dir / "events.jsonl"
    if not events_path.exists():
        return _MarketRow(
            slug=slug,
            question=resolved.question,
            yes_token_id=resolved.yes_token_id,
            no_token_id=resolved.no_token_id,
            tape_path=None,
            tape_events_count=0,
            tape_bbo_rows=0,
            yes_snapshot=False,
            no_snapshot=False,
            best_net_profit=None,
            median_net_profit=None,
            worst_net_profit=None,
            best_scenario=None,
            total_scenarios=0,
            total_orders=0,
            total_decisions=0,
            total_fills=0,
            dominant_rejection_key=None,
            dominant_rejection_count=0,
            status="error",
            error_msg="events.jsonl not created by recorder",
        )

    # Tape quality stats
    tape_meta_path = tape_dir / "meta.json"
    tape_events_count, yes_snapshot, no_snapshot, tape_bbo_rows = _read_tape_stats(
        events_path, tape_meta_path, resolved.yes_token_id, resolved.no_token_id
    )
    if params.min_events > 0 and tape_events_count < params.min_events:
        print(
            f"[quickrun] warning: tape has {tape_events_count} parsed events "
            f"(< --min-events {params.min_events}).",
            file=sys.stderr,
        )
        print(
            "[quickrun] warning: rerun with a longer --duration for better tape quality.",
            file=sys.stderr,
        )
    # Copy tape meta to market dir for reference
    if tape_meta_path.exists():
        shutil.copy2(tape_meta_path, market_dir / "tape_meta.json")

    # -- Build strategy config -------------------------------------------------
    strategy_config = build_binary_complement_strategy_config(
        yes_asset_id=resolved.yes_token_id,
        no_asset_id=resolved.no_token_id,
        strategy_preset=params.strategy_preset,
    )

    # -- Run sweep -------------------------------------------------------------
    sweep_id = f"batch_{slug[:16]}_{resolved.yes_token_id[:8]}_{ts}"
    try:
        sweep_result = run_sweep(
            SweepRunParams(
                events_path=events_path,
                strategy_name="binary_complement_arb",
                strategy_config=strategy_config,
                asset_id=resolved.yes_token_id,
                starting_cash=params.starting_cash,
                fee_rate_bps=None,  # overridden per scenario
                mark_method="bid",
                latency_submit_ticks=0,
                latency_cancel_ticks=0,
                strict=False,
                sweep_id=sweep_id,
                artifacts_root=params.artifacts_root,
            ),
            sweep_config=sweep_config,
        )
    except Exception as exc:  # noqa: BLE001
        return _MarketRow(
            slug=slug,
            question=resolved.question,
            yes_token_id=resolved.yes_token_id,
            no_token_id=resolved.no_token_id,
            tape_path=str(events_path),
            tape_events_count=tape_events_count,
            tape_bbo_rows=tape_bbo_rows,
            yes_snapshot=yes_snapshot,
            no_snapshot=no_snapshot,
            best_net_profit=None,
            median_net_profit=None,
            worst_net_profit=None,
            best_scenario=None,
            total_scenarios=0,
            total_orders=0,
            total_decisions=0,
            total_fills=0,
            dominant_rejection_key=None,
            dominant_rejection_count=0,
            status="error",
            error_msg=f"sweep failed: {exc}",
            tape_dir=str(tape_dir),
        )

    # -- Copy sweep artifacts to market dir ------------------------------------
    sweep_dir = sweep_result.sweep_dir
    for fname in ("sweep_manifest.json", "sweep_summary.json"):
        src = sweep_dir / fname
        if src.exists():
            shutil.copy2(src, market_dir / fname)

    runs_src = sweep_dir / "runs"
    if runs_src.exists():
        runs_dst = market_dir / "runs"
        if runs_dst.exists():
            shutil.rmtree(runs_dst)
        shutil.copytree(runs_src, runs_dst)

    # -- Aggregate orders/decisions/fills and rejection counts -----------------
    run_stats = _aggregate_run_stats(market_dir / "runs")

    agg = sweep_result.summary.get("aggregate", {})
    scenarios = sweep_result.summary.get("scenarios", [])

    return _MarketRow(
        slug=slug,
        question=resolved.question,
        yes_token_id=resolved.yes_token_id,
        no_token_id=resolved.no_token_id,
        tape_path=str(events_path),
        tape_events_count=tape_events_count,
        tape_bbo_rows=tape_bbo_rows,
        yes_snapshot=yes_snapshot,
        no_snapshot=no_snapshot,
        best_net_profit=str(agg.get("best_net_profit", "0")),
        median_net_profit=str(agg.get("median_net_profit", "0")),
        worst_net_profit=str(agg.get("worst_net_profit", "0")),
        best_scenario=agg.get("best_scenario"),
        total_scenarios=len(scenarios),
        total_orders=run_stats.total_orders,
        total_decisions=run_stats.total_decisions,
        total_fills=run_stats.total_fills,
        dominant_rejection_key=run_stats.dominant_rejection_key,
        dominant_rejection_count=run_stats.dominant_rejection_count,
        status="ok",
        sweep_dir=str(market_dir),
        tape_dir=str(tape_dir),
    )


# ---------------------------------------------------------------------------
# Aggregation helpers
# ---------------------------------------------------------------------------


def _aggregate_run_stats(runs_dir: Path) -> _RunStats:
    """Aggregate run-level metrics from scenario folders under ``runs_dir``."""
    total_orders = 0
    total_decisions = 0
    total_fills = 0
    rejection_totals: dict[str, int] = {}

    if not runs_dir.exists():
        return _RunStats(
            total_orders=0,
            total_decisions=0,
            total_fills=0,
            dominant_rejection_key=None,
            dominant_rejection_count=0,
        )

    for manifest_path in runs_dir.glob("*/run_manifest.json"):
        run_dir = manifest_path.parent
        try:
            mf = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            continue

        total_fills += _as_int(mf.get("fills_count"))
        total_decisions += _as_int(mf.get("decisions_count"))
        total_orders += _count_orders_for_run(run_dir)

        debug = mf.get("strategy_debug", {})
        rejection_counts = debug.get("rejection_counts", {})
        if isinstance(rejection_counts, dict):
            for key, count in rejection_counts.items():
                count_i = _as_int(count)
                if count_i > 0:
                    rejection_totals[key] = rejection_totals.get(key, 0) + count_i

    dominant_key: Optional[str]
    dominant_count: int
    if rejection_totals:
        dominant_key = max(rejection_totals, key=lambda k: rejection_totals[k])
        dominant_count = rejection_totals[dominant_key]
    else:
        dominant_key = None
        dominant_count = 0

    return _RunStats(
        total_orders=total_orders,
        total_decisions=total_decisions,
        total_fills=total_fills,
        dominant_rejection_key=dominant_key,
        dominant_rejection_count=dominant_count,
    )


def _read_tape_stats(
    events_path: Path,
    tape_meta_path: Path,
    yes_token_id: str,
    no_token_id: str,
) -> tuple[int, bool, bool, int]:
    """Return (parsed_events, yes_snapshot, no_snapshot, bbo_rows) from tape files."""
    parsed_events = 0
    yes_snapshot = False
    no_snapshot = False
    bbo_rows = 0
    tracked_assets = {yes_token_id, no_token_id}

    try:
        with open(events_path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    ev = json.loads(line)
                except Exception:  # noqa: BLE001
                    continue
                parsed_events += 1
                event_type = ev.get("event_type")
                asset_id = str(ev.get("asset_id") or "")
                if event_type == EVENT_TYPE_BOOK and asset_id in tracked_assets:
                    bbo_rows += 1
                    if asset_id == yes_token_id:
                        yes_snapshot = True
                    elif asset_id == no_token_id:
                        no_snapshot = True
                elif event_type == EVENT_TYPE_PRICE_CHANGE:
                    entries = ev.get("price_changes")
                    if isinstance(entries, list):
                        for entry in entries:
                            entry_asset = str(
                                (entry or {}).get("asset_id") if isinstance(entry, dict) else ""
                            )
                            if entry_asset in tracked_assets:
                                bbo_rows += 1
                    elif asset_id in tracked_assets:
                        bbo_rows += 1
    except Exception:  # noqa: BLE001
        pass

    return parsed_events, yes_snapshot, no_snapshot, bbo_rows


def _build_summary(
    batch_id: str,
    ts: str,
    params: BatchRunParams,
    rows: list[_MarketRow],
) -> dict[str, Any]:
    """Build the batch_summary.json payload."""
    ok_rows = [r for r in rows if r.status == "ok"]
    skipped = sum(1 for r in rows if r.status == "skipped")
    errors = sum(1 for r in rows if r.status == "error")

    markets_list = []
    for r in rows:
        markets_list.append(
            {
                "slug": r.slug,
                "question": r.question,
                "yes_token_id": r.yes_token_id,
                "no_token_id": r.no_token_id,
                "tape_path": r.tape_path,
                "tape_events_count": r.tape_events_count,
                "tape_bbo_rows": r.tape_bbo_rows,
                "yes_snapshot": r.yes_snapshot,
                "no_snapshot": r.no_snapshot,
                "best_net_profit": r.best_net_profit,
                "median_net_profit": r.median_net_profit,
                "worst_net_profit": r.worst_net_profit,
                "best_scenario": r.best_scenario,
                "total_scenarios": r.total_scenarios,
                "total_orders": r.total_orders,
                "total_decisions": r.total_decisions,
                "total_fills": r.total_fills,
                "dominant_rejection_key": r.dominant_rejection_key,
                "dominant_rejection_count": r.dominant_rejection_count,
                "status": r.status,
                "error_msg": r.error_msg,
                "sweep_dir": r.sweep_dir,
                "tape_dir": r.tape_dir,
            }
        )

    # Compute aggregate over ok_rows
    aggregate: dict[str, Any] = {
        "markets_ok": len(ok_rows),
        "markets_skipped": skipped,
        "markets_error": errors,
        "total_orders": sum(r.total_orders for r in rows),
        "total_decisions": sum(r.total_decisions for r in rows),
        "total_fills": sum(r.total_fills for r in rows),
        "tape_events_count": sum(r.tape_events_count for r in rows),
        "tape_bbo_rows": sum(r.tape_bbo_rows for r in rows),
    }

    if ok_rows:
        try:
            best_row = max(ok_rows, key=lambda r: Decimal(r.best_net_profit or "0"))
            worst_row = min(ok_rows, key=lambda r: Decimal(r.best_net_profit or "0"))
            aggregate["best_market"] = best_row.slug
            aggregate["best_net_profit"] = best_row.best_net_profit
            aggregate["worst_market"] = worst_row.slug
            aggregate["worst_net_profit"] = worst_row.best_net_profit
        except Exception:  # noqa: BLE001
            pass

    return {
        "batch_id": batch_id,
        "created_at": ts,
        "preset": params.preset,
        "aggregate": aggregate,
        "markets": markets_list,
    }


def _write_csv(path: Path, rows: list[_MarketRow]) -> None:
    """Write batch_summary.csv with key numeric fields."""
    fieldnames = [
        "slug",
        "status",
        "tape_events_count",
        "tape_bbo_rows",
        "yes_snapshot",
        "no_snapshot",
        "best_net_profit",
        "median_net_profit",
        "worst_net_profit",
        "best_scenario",
        "total_scenarios",
        "total_orders",
        "total_decisions",
        "total_fills",
        "dominant_rejection_key",
        "dominant_rejection_count",
        "error_msg",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for r in rows:
            writer.writerow(
                {
                    "slug": r.slug,
                    "status": r.status,
                    "tape_events_count": r.tape_events_count,
                    "tape_bbo_rows": r.tape_bbo_rows,
                    "yes_snapshot": r.yes_snapshot,
                    "no_snapshot": r.no_snapshot,
                    "best_net_profit": r.best_net_profit,
                    "median_net_profit": r.median_net_profit,
                    "worst_net_profit": r.worst_net_profit,
                    "best_scenario": r.best_scenario,
                    "total_scenarios": r.total_scenarios,
                    "total_orders": r.total_orders,
                    "total_decisions": r.total_decisions,
                    "total_fills": r.total_fills,
                    "dominant_rejection_key": r.dominant_rejection_key,
                    "dominant_rejection_count": r.dominant_rejection_count,
                    "error_msg": r.error_msg or "",
                }
            )


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------


def _as_int(value: object) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _count_orders_for_run(run_dir: Path) -> int:
    """Count non-empty lines in ``orders.jsonl`` for one scenario run."""
    orders_path = run_dir / "orders.jsonl"
    if not orders_path.exists():
        return 0
    count = 0
    try:
        with open(orders_path, encoding="utf-8") as fh:
            for line in fh:
                if line.strip():
                    count += 1
    except Exception:  # noqa: BLE001
        return 0
    return count


def _derive_seed(params: BatchRunParams) -> int:
    """Derive a deterministic seed from batch parameters."""
    payload = json.dumps(
        {
            "preset": params.preset,
            "num_markets": params.num_markets,
            "duration": params.duration,
            "strategy_preset": normalize_strategy_preset(params.strategy_preset),
            "starting_cash": str(params.starting_cash),
            "fee_rate_bps": (
                str(params.fee_rate_bps) if params.fee_rate_bps is not None else None
            ),
            "mark_method": params.mark_method,
            "max_candidates": params.max_candidates,
            "min_events": params.min_events,
            "allow_empty_book": params.allow_empty_book,
            "min_depth_size": params.min_depth_size,
            "top_n_levels": params.top_n_levels,
            "time_budget_seconds": params.time_budget_seconds,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return int(hashlib.sha256(payload.encode("utf-8")).hexdigest()[:8], 16)


def _derive_batch_id(params: BatchRunParams, ts: str) -> str:
    """Derive a deterministic batch ID from parameters + timestamp."""
    payload = json.dumps(
        {
            "ts": ts,
            "preset": params.preset,
            "strategy_preset": normalize_strategy_preset(params.strategy_preset),
            "num_markets": params.num_markets,
            "duration": params.duration,
            "starting_cash": str(params.starting_cash),
            "fee_rate_bps": str(params.fee_rate_bps),
            "mark_method": params.mark_method,
            "min_events": params.min_events,
            "min_depth_size": params.min_depth_size,
            "time_budget_seconds": params.time_budget_seconds,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    digest = hashlib.sha256(payload.encode()).hexdigest()[:10]
    return f"batch_{ts}_{digest}"


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
