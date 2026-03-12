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
    not_run_reason: str | None = None


def run_mm_sweep(
    *,
    tapes_dir: Path = DEFAULT_MM_SWEEP_TAPES_DIR,
    out_dir: Path = DEFAULT_MM_SWEEP_OUT_DIR,
    threshold: float = DEFAULT_MM_SWEEP_THRESHOLD,
    manifest_path: Path = DEFAULT_GATE2_MANIFEST_PATH,
    starting_cash: Decimal = DEFAULT_MM_SWEEP_STARTING_CASH,
    fee_rate_bps: Decimal = DEFAULT_MM_SWEEP_FEE_RATE_BPS,
    mark_method: str = DEFAULT_MM_SWEEP_MARK_METHOD,
    min_events: int = DEFAULT_MM_SWEEP_MIN_EVENTS,
    spread_multipliers: tuple[float, ...] = DEFAULT_MM_SWEEP_MULTIPLIERS,
) -> MMSweepResult:
    """Run the ``market_maker_v1`` sweep across all discovered candidate tapes."""
    if min_events < 0:
        raise ValueError(f"--min-events must be non-negative (got {min_events}).")
    if not spread_multipliers:
        raise ValueError("--spread-multipliers must include at least one value")
    if any(float(multiplier) <= 0 for multiplier in spread_multipliers):
        raise ValueError("--spread-multipliers values must be > 0")

    tapes = discover_mm_sweep_tapes(tapes_dir=tapes_dir, manifest_path=manifest_path)
    if not tapes:
        _clear_gate_artifacts(out_dir)
        return MMSweepResult(
            tapes=[],
            outcomes=[],
            gate_payload=None,
            artifact_path=None,
            threshold=threshold,
            min_events=min_events,
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
            not_run_reason=_NOT_RUN_REASON,
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
    )


def discover_mm_sweep_tapes(
    *,
    tapes_dir: Path = DEFAULT_MM_SWEEP_TAPES_DIR,
    manifest_path: Path = DEFAULT_GATE2_MANIFEST_PATH,
) -> list[TapeCandidate]:
    """Discover tapes for the market maker Gate 2 sweep."""
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
        manifest_entry = manifest_index.get(tape_dir.name, {})

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
            manifest_entry.get("final_regime"),
            manifest_entry.get("regime"),
        )
        market_slug = _first_text(
            prep_meta.get("market_slug"),
            _extract_market_slug(meta),
            manifest_entry.get("slug"),
            tape_dir.name,
        )
        yes_asset_id = _first_text(
            prep_meta.get("yes_asset_id"),
            prep_meta.get("yes_token_id"),
            _extract_yes_asset_id(meta),
        )

        if yes_asset_id is None:
            continue

        if not _is_selected_market_maker_tape(
            recorded_by=recorded_by,
            regime=regime,
            market_slug=market_slug,
            tape_name=tape_dir.name,
        ):
            continue

        parsed_events, tracked_asset_count, effective_events = _count_effective_events(events_path)
        candidates.append(
            TapeCandidate(
                tape_dir=tape_dir,
                events_path=events_path,
                market_slug=market_slug,
                yes_asset_id=yes_asset_id,
                recorded_by=recorded_by,
                regime=regime,
                parsed_events=parsed_events,
                tracked_asset_count=tracked_asset_count,
                effective_events=effective_events,
            )
        )

    return candidates


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

    return {
        "gate": "mm_sweep",
        "passed": passed,
        "tapes_total": tapes_total,
        "tapes_positive": tapes_positive,
        "pass_rate": round(pass_rate, 4),
        "best_scenarios": best_scenarios,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def _write_gate_result(*, out_dir: Path, passed: bool, payload: dict[str, Any]) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    filename = "gate_passed.json" if passed else "gate_failed.json"
    path = out_dir / filename
    opposite = out_dir / ("gate_failed.json" if passed else "gate_passed.json")
    if opposite.exists():
        opposite.unlink()
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


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
