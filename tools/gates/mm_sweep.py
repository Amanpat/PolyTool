"""Market maker Gate 2 sweep helpers."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from packages.polymarket.simtrader.sweeps.runner import (
    SweepConfigError,
    SweepRunParams,
    SweepRunResult,
    run_sweep,
)

_REPO_ROOT = Path(__file__).resolve().parents[2]

DEFAULT_MM_SWEEP_TAPES_DIR = _REPO_ROOT / "artifacts" / "simtrader" / "tapes"
DEFAULT_MM_SWEEP_OUT_DIR = _REPO_ROOT / "artifacts" / "gates" / "mm_sweep_gate"
DEFAULT_GATE2_MANIFEST_PATH = _REPO_ROOT / "artifacts" / "gates" / "gate2_tape_manifest.json"

DEFAULT_MM_SWEEP_THRESHOLD = 0.70
DEFAULT_MM_SWEEP_MARK_METHOD = "bid"
DEFAULT_MM_SWEEP_MIN_EVENTS = 50
DEFAULT_MM_SWEEP_MIN_ELIGIBLE_TAPES = 50  # Must match benchmark_v1 total tape count
DEFAULT_MM_SWEEP_MULTIPLIERS: tuple[float, ...] = (0.50, 1.00, 1.50, 2.00, 3.00)
DEFAULT_MM_SWEEP_BASE_CONFIG: dict[str, Any] = {
    "min_spread": 0.020,
    "max_spread": 0.120,
    "spread_multiplier": 1.0,
    "adverse_selection": {
        "enabled": True,
        "order_flow_signal": "proxy",
    },
}
DEFAULT_MM_SWEEP_STARTING_CASH = Decimal("1000")
DEFAULT_MM_SWEEP_FEE_RATE_BPS = Decimal("200")

_SPORTS_REGIMES = frozenset({"sports", "nhl"})
_TOO_SHORT_STATUS = "SKIPPED_TOO_SHORT"
_ERROR_STATUS = "ERROR"
_RAN_STATUS = "RAN"
_NOT_RUN_REASON = "No eligible tapes found — record longer tapes before running Gate 2 sweep."


@dataclass(frozen=True)
class TapeCandidate:
    """One discovered tape that can be swept with ``market_maker_v1``."""

    tape_dir: Path
    events_path: Path
    market_slug: str
    yes_asset_id: str
    recorded_by: str | None
    regime: str | None
    parsed_events: int
    tracked_asset_count: int
    effective_events: int
    bucket: str | None = None


@dataclass(frozen=True)
class TapeSweepOutcome:
    """Sweep outcome for one tape."""

    tape: TapeCandidate
    status: str
    sweep_dir: Path | None
    scenario_rows: list[dict[str, Any]]
    best_scenario_id: str | None
    best_scenario_name: str | None
    best_net_profit: Decimal | None
    positive: bool
    error: str | None = None


@dataclass(frozen=True)
class MMSweepResult:
    """Top-level result for a full market maker tape sweep."""

    tapes: list[TapeCandidate]
    outcomes: list[TapeSweepOutcome]
    gate_payload: dict[str, Any] | None
    artifact_path: Path | None
    threshold: float
    min_events: int
    min_eligible_tapes: int = DEFAULT_MM_SWEEP_MIN_ELIGIBLE_TAPES
    not_run_reason: str | None = None


def run_mm_sweep(
    *,
    tapes_dir: Path = DEFAULT_MM_SWEEP_TAPES_DIR,
    out_dir: Path = DEFAULT_MM_SWEEP_OUT_DIR,
    threshold: float = DEFAULT_MM_SWEEP_THRESHOLD,
    manifest_path: Path = DEFAULT_GATE2_MANIFEST_PATH,
    benchmark_manifest_path: Path | None = None,
    starting_cash: Decimal = DEFAULT_MM_SWEEP_STARTING_CASH,
    fee_rate_bps: Decimal = DEFAULT_MM_SWEEP_FEE_RATE_BPS,
    mark_method: str = DEFAULT_MM_SWEEP_MARK_METHOD,
    min_events: int = DEFAULT_MM_SWEEP_MIN_EVENTS,
    min_eligible_tapes: int = DEFAULT_MM_SWEEP_MIN_ELIGIBLE_TAPES,
    spread_multipliers: tuple[float, ...] = DEFAULT_MM_SWEEP_MULTIPLIERS,
) -> MMSweepResult:
    """Run the ``market_maker_v1`` sweep across all discovered candidate tapes."""
    if min_events < 0:
        raise ValueError(f"--min-events must be non-negative (got {min_events}).")
    if not spread_multipliers:
        raise ValueError("--spread-multipliers must include at least one value")
    if any(float(multiplier) <= 0 for multiplier in spread_multipliers):
        raise ValueError("--spread-multipliers values must be > 0")

    tapes = discover_mm_sweep_tapes(
        tapes_dir=tapes_dir,
        manifest_path=manifest_path,
        benchmark_manifest_path=benchmark_manifest_path,
    )
    if not tapes:
        _clear_gate_artifacts(out_dir)
        return MMSweepResult(
            tapes=[],
            outcomes=[],
            gate_payload=None,
            artifact_path=None,
            threshold=threshold,
            min_events=min_events,
            min_eligible_tapes=min_eligible_tapes,
            not_run_reason=_NOT_RUN_REASON,
        )

    sweep_config = build_mm_sweep_config(spread_multipliers)
    outcomes: list[TapeSweepOutcome] = []
    eligible_outcomes: list[TapeSweepOutcome] = []

    for tape in tapes:
        if tape.effective_events < min_events:
            outcomes.append(
                TapeSweepOutcome(
                    tape=tape,
                    status=_TOO_SHORT_STATUS,
                    sweep_dir=None,
                    scenario_rows=[],
                    best_scenario_id=None,
                    best_scenario_name=None,
                    best_net_profit=None,
                    positive=False,
                    error=(
                        f"effective_events={tape.effective_events} (< --min-events {min_events}; "
                        f"raw_events={tape.parsed_events} across {tape.tracked_asset_count} assets)"
                    ),
                )
            )
            continue

        sweep_id = f"{tape.tape_dir.name}_market_maker_v1_mm_sweep"
        try:
            sweep_result = run_sweep(
                SweepRunParams(
                    events_path=tape.events_path,
                    strategy_name="market_maker_v1",
                    strategy_config=dict(DEFAULT_MM_SWEEP_BASE_CONFIG),
                    asset_id=tape.yes_asset_id,
                    starting_cash=starting_cash,
                    fee_rate_bps=fee_rate_bps,
                    mark_method=mark_method,
                    latency_submit_ticks=0,
                    latency_cancel_ticks=0,
                    strict=False,
                    sweep_id=sweep_id,
                    artifacts_root=out_dir,
                    strategy_preset=None,
                    market_slug=tape.market_slug,
                ),
                sweep_config=sweep_config,
            )
            outcome = _build_outcome(tape, sweep_result)
        except (SweepConfigError, ValueError) as exc:
            outcome = TapeSweepOutcome(
                tape=tape,
                status=_ERROR_STATUS,
                sweep_dir=None,
                scenario_rows=[],
                best_scenario_id=None,
                best_scenario_name=None,
                best_net_profit=None,
                positive=False,
                error=str(exc),
            )
        except Exception as exc:  # noqa: BLE001
            outcome = TapeSweepOutcome(
                tape=tape,
                status=_ERROR_STATUS,
                sweep_dir=None,
                scenario_rows=[],
                best_scenario_id=None,
                best_scenario_name=None,
                best_net_profit=None,
                positive=False,
                error=f"unexpected sweep failure: {exc}",
            )

        outcomes.append(outcome)
        eligible_outcomes.append(outcome)

    if not eligible_outcomes:
        _clear_gate_artifacts(out_dir)
        return MMSweepResult(
            tapes=tapes,
            outcomes=outcomes,
            gate_payload=None,
            artifact_path=None,
            threshold=threshold,
            min_events=min_events,
            min_eligible_tapes=min_eligible_tapes,
            not_run_reason=_NOT_RUN_REASON,
        )

    if len(eligible_outcomes) < min_eligible_tapes:
        _clear_gate_artifacts(out_dir)
        not_run_msg = (
            f"Corpus too small: only {len(eligible_outcomes)}/{len(tapes)} tapes meet "
            f"--min-events={min_events} (need at least {min_eligible_tapes} eligible "
            f"tapes to compute a valid Gate 2 verdict). "
            f"{len(tapes) - len(eligible_outcomes)} tapes were skipped as SKIPPED_TOO_SHORT. "
            "Record or reconstruct longer tapes before rerunning Gate 2."
        )
        return MMSweepResult(
            tapes=tapes,
            outcomes=outcomes,
            gate_payload=None,
            artifact_path=None,
            threshold=threshold,
            min_events=min_events,
            min_eligible_tapes=min_eligible_tapes,
            not_run_reason=not_run_msg,
        )

    payload = _build_gate_payload(outcomes=eligible_outcomes, threshold=threshold)
    artifact_path = _write_gate_result(out_dir=out_dir, passed=payload["passed"], payload=payload)
    return MMSweepResult(
        tapes=tapes,
        outcomes=outcomes,
        gate_payload=payload,
        artifact_path=artifact_path,
        threshold=threshold,
        min_events=min_events,
        min_eligible_tapes=min_eligible_tapes,
    )


def discover_mm_sweep_tapes(
    *,
    tapes_dir: Path = DEFAULT_MM_SWEEP_TAPES_DIR,
    manifest_path: Path = DEFAULT_GATE2_MANIFEST_PATH,
    benchmark_manifest_path: Path | None = None,
) -> list[TapeCandidate]:
    """Discover tapes for the market maker Gate 2 sweep."""
    if benchmark_manifest_path is not None:
        return _load_benchmark_manifest_tapes(benchmark_manifest_path)

    manifest_index = _load_gate2_manifest_index(manifest_path)
    candidates: list[TapeCandidate] = []

    if not tapes_dir.exists():
        return candidates

    for tape_dir in sorted(path for path in tapes_dir.iterdir() if path.is_dir()):
        events_path = tape_dir / "events.jsonl"
        if not events_path.exists():
            continue

        meta = _read_json_object(tape_dir / "meta.json")
        prep_meta = _read_json_object(tape_dir / "prep_meta.json")
        watch_meta = _read_json_object(tape_dir / "watch_meta.json")
        market_meta = _read_json_object(tape_dir / "market_meta.json")
        silver_meta = _read_json_object(tape_dir / "silver_meta.json")
        manifest_entry = manifest_index.get(tape_dir.name, {})

        candidate = _build_tape_candidate(
            tape_dir=tape_dir,
            events_path=events_path,
            meta=meta,
            prep_meta=prep_meta,
            watch_meta=watch_meta,
            market_meta=market_meta,
            silver_meta=silver_meta,
            manifest_entry=manifest_entry,
            require_selected=True,
        )
        if candidate is not None:
            candidates.append(candidate)

    return candidates


def _load_benchmark_manifest_tapes(benchmark_manifest_path: Path) -> list[TapeCandidate]:
    from packages.polymarket.benchmark_manifest_contract import (
        default_lock_path_for_manifest,
        validate_benchmark_manifest,
    )

    lock_path = default_lock_path_for_manifest(benchmark_manifest_path)
    validation = validate_benchmark_manifest(
        benchmark_manifest_path,
        lock_path=lock_path if lock_path.exists() else None,
    )

    candidates: list[TapeCandidate] = []
    for events_path in validation.resolved_tape_paths:
        tape_dir = events_path.parent
        candidate = _build_tape_candidate(
            tape_dir=tape_dir,
            events_path=events_path,
            meta=_read_json_object(tape_dir / "meta.json"),
            prep_meta=_read_json_object(tape_dir / "prep_meta.json"),
            watch_meta=_read_json_object(tape_dir / "watch_meta.json"),
            market_meta=_read_json_object(tape_dir / "market_meta.json"),
            silver_meta=_read_json_object(tape_dir / "silver_meta.json"),
            manifest_entry={},
            require_selected=False,
            explicit_source=str(benchmark_manifest_path),
        )
        if candidate is not None:
            candidates.append(candidate)
    return candidates


def _build_tape_candidate(
    *,
    tape_dir: Path,
    events_path: Path,
    meta: dict[str, Any],
    prep_meta: dict[str, Any],
    watch_meta: dict[str, Any] | None = None,
    market_meta: dict[str, Any] | None = None,
    silver_meta: dict[str, Any] | None = None,
    manifest_entry: dict[str, Any],
    require_selected: bool,
    explicit_source: str | None = None,
) -> TapeCandidate | None:
    _watch = watch_meta or {}
    _market = market_meta or {}
    _silver = silver_meta or {}

    recorded_by = _first_text(
        meta.get("recorded_by"),
        prep_meta.get("recorded_by"),
        manifest_entry.get("recorded_by"),
    )
    regime = _first_text(
        meta.get("final_regime"),
        meta.get("regime"),
        prep_meta.get("final_regime"),
        prep_meta.get("regime"),
        _watch.get("regime"),
        _market.get("benchmark_bucket"),
        _market.get("category"),
        manifest_entry.get("final_regime"),
        manifest_entry.get("regime"),
    )
    market_slug = _first_text(
        prep_meta.get("market_slug"),
        _extract_market_slug(meta),
        _watch.get("market_slug"),
        _market.get("slug"),
        manifest_entry.get("slug"),
        tape_dir.name,
    )
    yes_asset_id = _first_text(
        prep_meta.get("yes_asset_id"),
        prep_meta.get("yes_token_id"),
        _extract_yes_asset_id(meta),
        _watch.get("yes_asset_id"),
        _watch.get("yes_token_id"),
        _market.get("token_id"),
        _silver.get("token_id"),
    )

    if yes_asset_id is None:
        if explicit_source is not None:
            raise ValueError(
                "benchmark manifest tape is missing YES asset metadata: "
                f"{_display_path(events_path)} (source {explicit_source})"
            )
        return None

    if require_selected and not _is_selected_market_maker_tape(
        recorded_by=recorded_by,
        regime=regime,
        market_slug=market_slug,
        tape_name=tape_dir.name,
    ):
        return None

    # Derive bucket from available metadata sources (benchmark manifest tapes only).
    bucket = _first_text(
        _watch.get("bucket"),
        _market.get("benchmark_bucket"),
        manifest_entry.get("bucket"),
    )

    parsed_events, tracked_asset_count, effective_events = _count_effective_events(events_path)
    return TapeCandidate(
        tape_dir=tape_dir,
        events_path=events_path,
        market_slug=market_slug,
        yes_asset_id=yes_asset_id,
        recorded_by=recorded_by,
        regime=regime,
        parsed_events=parsed_events,
        tracked_asset_count=tracked_asset_count,
        effective_events=effective_events,
        bucket=bucket,
    )


def build_mm_sweep_config(
    spread_multipliers: tuple[float, ...] = DEFAULT_MM_SWEEP_MULTIPLIERS,
) -> dict[str, Any]:
    """Build the market maker spread-multiplier sweep."""
    scenarios: list[dict[str, Any]] = []
    for multiplier in spread_multipliers:
        scenario_suffix = int(round(float(multiplier) * 100))
        scenarios.append(
            {
                "name": f"spread-x{scenario_suffix:03d}",
                "overrides": {
                    "strategy_config": {
                        "spread_multiplier": float(multiplier),
                    }
                },
            }
        )
    return {"scenarios": scenarios}


def format_mm_sweep_summary(result: MMSweepResult) -> str:
    """Render a compact human-readable summary table."""
    tape_width = 30
    scenario_width = 18
    pnl_width = 14
    lines = [
        "MM Sweep Summary",
        "=" * 88,
        f"{'Tape':<{tape_width}}{'Scenario':<{scenario_width}}{'Net PnL':>{pnl_width}}  Positive",
        "-" * 88,
    ]

    for outcome in result.outcomes:
        tape_label = _truncate(outcome.tape.tape_dir.name, tape_width)

        if outcome.status == _TOO_SHORT_STATUS:
            lines.append(
                f"{tape_label:<{tape_width}}"
                f"{_TOO_SHORT_STATUS:<{scenario_width}}"
                f"{'n/a':>{pnl_width}}  "
                f"-"
            )
            lines.append(f"  note: {outcome.error}")
            continue

        if outcome.status == _ERROR_STATUS:
            lines.append(
                f"{tape_label:<{tape_width}}"
                f"{_ERROR_STATUS:<{scenario_width}}"
                f"{'n/a':>{pnl_width}}  "
                f"NO"
            )
            if outcome.error:
                lines.append(f"  note: {outcome.error}")
            continue

        for idx, row in enumerate(outcome.scenario_rows):
            scenario_id = str(row.get("scenario_id") or "-")
            net_profit = str(row.get("net_profit") or "n/a")
            positive_label = "YES" if bool(row.get("positive")) else "NO"
            lines.append(
                f"{tape_label if idx == 0 else '':<{tape_width}}"
                f"{_truncate(scenario_id, scenario_width):<{scenario_width}}"
                f"{net_profit:>{pnl_width}}  "
                f"{positive_label}"
            )

    lines.append("-" * 88)
    if result.gate_payload is None:
        lines.append(
            f"Gate=NOT_RUN  threshold={result.threshold:.0%}  --min-events={result.min_events}"
        )
        if result.not_run_reason:
            lines.append(f"Reason: {result.not_run_reason}")
        lines.append("Artifact: not written (gate status will report NOT_RUN)")
        return "\n".join(lines)

    lines.append(
        f"Positive tapes: {result.gate_payload['tapes_positive']}/"
        f"{result.gate_payload['tapes_total']}  "
        f"pass_rate={result.gate_payload['pass_rate']:.1%}  "
        f"threshold={result.threshold:.0%}  "
        f"gate={'PASS' if result.gate_payload['passed'] else 'FAIL'}"
    )
    lines.append(f"Artifact: {_display_path(result.artifact_path)}")
    return "\n".join(lines)


def _build_outcome(tape: TapeCandidate, sweep_result: SweepRunResult) -> TapeSweepOutcome:
    scenario_rows = []
    for row in sweep_result.summary.get("scenarios", []):
        scenario_net_profit = _parse_decimal(row.get("net_profit"))
        scenario_rows.append(
            {
                "scenario_id": row.get("scenario_id"),
                "scenario_name": row.get("scenario_name"),
                "net_profit": str(row.get("net_profit")),
                "positive": bool(scenario_net_profit is not None and scenario_net_profit > 0),
            }
        )

    best_row = _best_scenario_row(scenario_rows)
    best_net_profit = _parse_decimal(best_row.get("net_profit")) if best_row else None
    return TapeSweepOutcome(
        tape=tape,
        status=_RAN_STATUS,
        sweep_dir=sweep_result.sweep_dir,
        scenario_rows=scenario_rows,
        best_scenario_id=str(best_row.get("scenario_id")) if best_row else None,
        best_scenario_name=str(best_row.get("scenario_name")) if best_row else None,
        best_net_profit=best_net_profit,
        positive=(best_net_profit is not None and best_net_profit > 0),
    )


def _build_gate_payload(
    *,
    outcomes: list[TapeSweepOutcome],
    threshold: float,
) -> dict[str, Any]:
    tapes_total = len(outcomes)
    tapes_positive = sum(1 for outcome in outcomes if outcome.positive)
    pass_rate = (tapes_positive / tapes_total) if tapes_total else 0.0
    passed = pass_rate >= threshold if tapes_total else False

    best_scenarios = []
    for outcome in outcomes:
        best_scenarios.append(
            {
                "tape_dir": _display_path(outcome.tape.tape_dir),
                "market_slug": outcome.tape.market_slug,
                "recorded_by": outcome.tape.recorded_by,
                "regime": outcome.tape.regime,
                "bucket": outcome.tape.bucket,
                "best_scenario_id": outcome.best_scenario_id,
                "best_scenario_name": outcome.best_scenario_name,
                "best_net_profit": (
                    str(outcome.best_net_profit)
                    if outcome.best_net_profit is not None
                    else None
                ),
                "positive": outcome.positive,
                "scenario_count": len(outcome.scenario_rows),
                "sweep_dir": _display_path(outcome.sweep_dir) if outcome.sweep_dir else None,
                "error": outcome.error,
            }
        )

    # Build per-bucket diagnostics when bucket metadata is available.
    bucket_breakdown: dict[str, dict[str, Any]] = {}
    for outcome in outcomes:
        bkt = outcome.tape.bucket
        if bkt is None:
            continue
        entry = bucket_breakdown.setdefault(bkt, {"total": 0, "positive": 0, "pass_rate": 0.0})
        entry["total"] += 1
        if outcome.positive:
            entry["positive"] += 1
    for entry in bucket_breakdown.values():
        entry["pass_rate"] = round(
            (entry["positive"] / entry["total"]) if entry["total"] else 0.0,
            4,
        )

    payload: dict[str, Any] = {
        "gate": "mm_sweep",
        "passed": passed,
        "tapes_total": tapes_total,
        "tapes_positive": tapes_positive,
        "pass_rate": round(pass_rate, 4),
        "best_scenarios": best_scenarios,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    if bucket_breakdown:
        payload["bucket_breakdown"] = bucket_breakdown
    return payload


def _write_gate_result(*, out_dir: Path, passed: bool, payload: dict[str, Any]) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    filename = "gate_passed.json" if passed else "gate_failed.json"
    path = out_dir / filename
    opposite = out_dir / ("gate_failed.json" if passed else "gate_passed.json")
    if opposite.exists():
        opposite.unlink()
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    _write_gate_markdown_summary(out_dir=out_dir, payload=payload)
    return path


def _write_gate_markdown_summary(*, out_dir: Path, payload: dict[str, Any]) -> None:
    """Write a human-readable Markdown summary alongside the gate JSON artifact."""
    passed = payload.get("passed", False)
    verdict = "PASS" if passed else "FAIL"
    tapes_total = payload.get("tapes_total", 0)
    tapes_positive = payload.get("tapes_positive", 0)
    pass_rate = payload.get("pass_rate", 0.0)
    generated_at = payload.get("generated_at", "")

    lines = [
        "# MM Sweep Gate Summary",
        "",
        f"**Verdict:** {verdict}",
        f"**Generated:** {generated_at}",
        f"**Positive tapes:** {tapes_positive}/{tapes_total} ({pass_rate:.1%})",
        f"**Threshold:** 70.0%",
        "",
    ]

    # Per-bucket breakdown section (present when tapes carry bucket metadata).
    bucket_breakdown: dict[str, dict[str, Any]] = payload.get("bucket_breakdown", {})
    if bucket_breakdown:
        lines += [
            "## Per-Bucket Breakdown",
            "",
            "| Bucket | Total | Positive | Pass Rate |",
            "|--------|------:|--------:|----------:|",
        ]
        for bucket, entry in sorted(bucket_breakdown.items()):
            bkt_pass_rate = entry.get("pass_rate", 0.0)
            lines.append(
                f"| {bucket} | {entry['total']} | {entry['positive']} | {bkt_pass_rate:.1%} |"
            )
        lines.append("")

    # Per-tape detail section.
    best_scenarios: list[dict[str, Any]] = payload.get("best_scenarios", [])
    if best_scenarios:
        lines += [
            "## Per-Tape Results",
            "",
            "| Tape | Bucket | Best Scenario | Net PnL | Positive |",
            "|------|--------|---------------|--------:|----------|",
        ]
        for scenario in best_scenarios:
            tape_name = Path(scenario.get("tape_dir", "")).name or scenario.get("tape_dir", "-")
            bucket = scenario.get("bucket") or "-"
            best_scenario_name = scenario.get("best_scenario_name") or scenario.get("error") or "-"
            net_pnl = scenario.get("best_net_profit") or "-"
            positive_label = "YES" if scenario.get("positive") else "NO"
            lines.append(
                f"| {tape_name} | {bucket} | {best_scenario_name} | {net_pnl} | {positive_label} |"
            )
        lines.append("")

    summary_path = out_dir / "gate_summary.md"
    summary_path.write_text("\n".join(lines), encoding="utf-8")


def _clear_gate_artifacts(out_dir: Path) -> None:
    for filename in ("gate_passed.json", "gate_failed.json"):
        artifact_path = out_dir / filename
        if artifact_path.exists():
            artifact_path.unlink()


def _load_gate2_manifest_index(manifest_path: Path) -> dict[str, dict[str, Any]]:
    payload = _read_json_object(manifest_path)
    if not isinstance(payload, dict):
        return {}

    entries = payload.get("tapes")
    if not isinstance(entries, list):
        return {}

    index: dict[str, dict[str, Any]] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        tape_dir_raw = _first_text(entry.get("tape_dir"))
        if tape_dir_raw is None:
            continue
        index[Path(tape_dir_raw).name] = entry
    return index


def _extract_market_slug(meta: dict[str, Any]) -> str | None:
    for key in ("market_slug", "slug", "market"):
        value = _first_text(meta.get(key))
        if value is not None:
            return value

    for context_key in ("quickrun_context", "shadow_context"):
        context = meta.get(context_key)
        if not isinstance(context, dict):
            continue
        for key in ("selected_slug", "market_slug", "slug", "market"):
            value = _first_text(context.get(key))
            if value is not None:
                return value
    return None


def _extract_yes_asset_id(meta: dict[str, Any]) -> str | None:
    direct_value = _first_text(meta.get("yes_token_id"), meta.get("yes_asset_id"))
    if direct_value is not None:
        return direct_value

    for context_key in ("quickrun_context", "shadow_context"):
        context = meta.get(context_key)
        if not isinstance(context, dict):
            continue
        context_value = _first_text(
            context.get("yes_token_id"),
            context.get("yes_asset_id"),
        )
        if context_value is not None:
            return context_value

    # Fallback: early shadow tapes record asset_ids=[YES, NO] without shadow_context.
    # YES is always first by tape-recording convention (confirmed by all later tapes
    # that do have shadow_context and match asset_ids[0] == shadow_context.yes_token_id).
    asset_ids = meta.get("asset_ids")
    if isinstance(asset_ids, list) and asset_ids:
        first = str(asset_ids[0]).strip()
        if first:
            return first

    return None


def _is_selected_market_maker_tape(
    *,
    recorded_by: str | None,
    regime: str | None,
    market_slug: str,
    tape_name: str,
) -> bool:
    if recorded_by == "prepare-gate2":
        return True

    regime_token = (regime or "").strip().lower()
    if regime_token in _SPORTS_REGIMES:
        return True

    return _looks_like_nhl_market(market_slug) or _looks_like_nhl_market(tape_name)


def _looks_like_nhl_market(value: str | None) -> bool:
    text = (value or "").strip().lower()
    if not text:
        return False
    return any(token in text for token in ("nhl", "stanley-cup", "maple-leafs", "canucks", "flames"))


def _best_scenario_row(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    best_row: dict[str, Any] | None = None
    best_net_profit: Decimal | None = None
    for row in rows:
        net_profit = _parse_decimal(row.get("net_profit"))
        if net_profit is None:
            continue
        if best_row is None or best_net_profit is None or net_profit > best_net_profit:
            best_row = row
            best_net_profit = net_profit
    return best_row


def _count_effective_events(events_path: Path) -> tuple[int, int, int]:
    parsed_events = 0
    asset_ids: set[str] = set()

    with open(events_path, encoding="utf-8") as fh:
        for raw_line in fh:
            raw_line = raw_line.strip()
            if not raw_line:
                continue
            try:
                event = json.loads(raw_line)
            except json.JSONDecodeError:
                continue
            if not isinstance(event, dict):
                continue

            parsed_events += 1
            asset_id = _first_text(event.get("asset_id"))
            if asset_id is not None:
                asset_ids.add(asset_id)
            for entry in event.get("price_changes", []):
                if not isinstance(entry, dict):
                    continue
                entry_asset_id = _first_text(entry.get("asset_id"))
                if entry_asset_id is not None:
                    asset_ids.add(entry_asset_id)

    tracked_asset_count = max(1, len(asset_ids))
    effective_events = parsed_events if tracked_asset_count == 1 else parsed_events // tracked_asset_count
    return parsed_events, tracked_asset_count, effective_events


def _parse_decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _read_json_object(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:  # noqa: BLE001
        return {}
    return payload if isinstance(payload, dict) else {}


def _first_text(*values: Any) -> str | None:
    for value in values:
        if not isinstance(value, str):
            continue
        text = value.strip()
        if text:
            return text
    return None


def _display_path(path: Path | None) -> str:
    if path is None:
        return ""
    try:
        return str(path.relative_to(_REPO_ROOT))
    except ValueError:
        return str(path)


def _truncate(value: str, width: int) -> str:
    if len(value) <= width:
        return value
    if width <= 3:
        return value[:width]
    return value[: width - 3] + "..."
