"""Scenario sweep orchestration for SimTrader strategy runs."""

from __future__ import annotations

import copy
import hashlib
import json
import re
import shutil
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Optional

from ..config_loader import ConfigLoadError, load_json_from_string
from ..strategy.facade import (
    StrategyRunConfigError,
    StrategyRunParams,
    known_strategies,
    run_strategy,
    validate_mark_method,
)

_SLUG_RE = re.compile(r"[^a-z0-9]+")
_ALLOWED_OVERRIDE_KEYS = frozenset(
    {
        "fee_rate_bps",
        "mark_method",
        "strategy_config",
        "latency_ticks",
        "cancel_latency_ticks",
        "latency_submit_ticks",
        "latency_cancel_ticks",
        "latency_config",
    }
)


class SweepConfigError(ValueError):
    """Raised when sweep config or overrides are invalid."""


@dataclass(frozen=True)
class SweepRunParams:
    """Base parameters for a scenario sweep."""

    events_path: Path
    strategy_name: str
    strategy_config: dict[str, Any]
    starting_cash: Decimal
    asset_id: Optional[str] = None
    fee_rate_bps: Optional[Decimal] = None
    mark_method: str = "bid"
    latency_submit_ticks: int = 0
    latency_cancel_ticks: int = 0
    strict: bool = False
    sweep_id: Optional[str] = None
    artifacts_root: Path = Path("artifacts/simtrader")


@dataclass(frozen=True)
class SweepRunResult:
    """Outcome for one completed scenario sweep."""

    sweep_id: str
    sweep_dir: Path
    summary: dict[str, Any]
    manifest: dict[str, Any]


@dataclass(frozen=True)
class _ScenarioDef:
    source_index: int
    name: Optional[str]
    overrides: dict[str, Any]
    scenario_id: str


@dataclass(frozen=True)
class _ScenarioRunStats:
    decisions_count: int
    orders_count: int
    fills_count: int
    rejection_counts: dict[str, int]


def parse_sweep_config_json(raw: str) -> dict[str, Any]:
    """Parse ``--sweep-config`` JSON and validate top-level shape.

    Routes through ``load_json_from_string`` so that BOM-prefixed strings
    (e.g. from PowerShell pipelines) are handled correctly.
    """
    try:
        return load_json_from_string(raw)
    except ConfigLoadError as exc:
        raise SweepConfigError(f"--sweep-config: {exc}") from exc


def run_sweep(params: SweepRunParams, sweep_config: dict[str, Any]) -> SweepRunResult:
    """Run all sweep scenarios and write sweep-level artifacts."""
    if not params.events_path.exists():
        raise SweepConfigError(f"tape file not found: {params.events_path}")
    if not isinstance(params.strategy_config, dict):
        raise SweepConfigError("strategy_config must be a JSON object")
    if params.strategy_name not in known_strategies():
        known = ", ".join(known_strategies())
        raise SweepConfigError(
            f"unknown strategy {params.strategy_name!r}. Known: {known}"
        )
    if params.starting_cash < 0:
        raise SweepConfigError("starting_cash must be non-negative")
    if params.fee_rate_bps is not None and params.fee_rate_bps < 0:
        raise SweepConfigError("fee_rate_bps must be non-negative")
    if params.latency_submit_ticks < 0 or params.latency_cancel_ticks < 0:
        raise SweepConfigError("latency tick values must be non-negative")
    try:
        validate_mark_method(params.mark_method)
    except StrategyRunConfigError as exc:
        raise SweepConfigError(str(exc)) from exc

    scenarios = _normalize_scenarios(sweep_config)
    sweep_id = params.sweep_id or _derive_sweep_id(params, scenarios)
    sweep_dir = params.artifacts_root / "sweeps" / sweep_id
    runs_dir = sweep_dir / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)

    scenario_rows: list[dict[str, Any]] = []
    scenario_stats: list[_ScenarioRunStats] = []
    for scenario in scenarios:
        (
            scenario_strategy_config,
            scenario_fee_rate_bps,
            scenario_mark_method,
            scenario_submit_ticks,
            scenario_cancel_ticks,
        ) = _apply_overrides(params, scenario.overrides)

        run_dir = runs_dir / scenario.scenario_id
        if run_dir.exists():
            shutil.rmtree(run_dir)
        run_result = run_strategy(
            StrategyRunParams(
                events_path=params.events_path,
                run_dir=run_dir,
                strategy_name=params.strategy_name,
                strategy_config=scenario_strategy_config,
                asset_id=params.asset_id,
                starting_cash=params.starting_cash,
                fee_rate_bps=scenario_fee_rate_bps,
                mark_method=scenario_mark_method,
                latency_submit_ticks=scenario_submit_ticks,
                latency_cancel_ticks=scenario_cancel_ticks,
                strict=params.strict,
            )
        )

        scenario_rows.append(
            {
                "scenario_id": scenario.scenario_id,
                "scenario_name": scenario.name or scenario.scenario_id,
                "run_id": run_result.run_id,
                "net_profit": run_result.metrics["net_profit"],
                "realized_pnl": run_result.metrics["realized_pnl"],
                "unrealized_pnl": run_result.metrics["unrealized_pnl"],
                "total_fees": run_result.metrics["total_fees"],
                "warnings_count": run_result.warnings_count,
                "artifact_path": run_result.run_dir.as_posix(),
            }
        )
        scenario_stats.append(_read_scenario_run_stats(run_result.run_dir))

    aggregate = _build_aggregate_summary(scenario_rows, scenario_stats)
    scenario_order = [row["scenario_id"] for row in scenario_rows]

    summary: dict[str, Any] = {
        "sweep_id": sweep_id,
        "tape_path": params.events_path.as_posix(),
        "strategy": params.strategy_name,
        "scenario_order": scenario_order,
        "scenarios": scenario_rows,
        "aggregate": aggregate,
    }

    manifest: dict[str, Any] = {
        "sweep_id": sweep_id,
        "tape_path": params.events_path.as_posix(),
        "strategy": params.strategy_name,
        "base_config": {
            "asset_id": params.asset_id,
            "starting_cash": str(params.starting_cash),
            "fee_rate_bps": (
                str(params.fee_rate_bps) if params.fee_rate_bps is not None else None
            ),
            "mark_method": params.mark_method,
            "latency_submit_ticks": params.latency_submit_ticks,
            "latency_cancel_ticks": params.latency_cancel_ticks,
            "strict": params.strict,
            "strategy_config": params.strategy_config,
        },
        "scenario_order": scenario_order,
        "scenarios": [
            {
                "source_index": scenario.source_index,
                "scenario_id": scenario.scenario_id,
                "name": scenario.name,
                "overrides": scenario.overrides,
            }
            for scenario in scenarios
        ],
    }

    _write_json(sweep_dir / "sweep_manifest.json", manifest)
    _write_json(sweep_dir / "sweep_summary.json", summary)

    return SweepRunResult(
        sweep_id=sweep_id,
        sweep_dir=sweep_dir,
        summary=summary,
        manifest=manifest,
    )


def _normalize_scenarios(sweep_config: dict[str, Any]) -> list[_ScenarioDef]:
    scenarios_raw = sweep_config.get("scenarios")
    if not isinstance(scenarios_raw, list) or not scenarios_raw:
        raise SweepConfigError("'scenarios' must be a non-empty JSON array")

    prelim: list[tuple[int, Optional[str], dict[str, Any]]] = []
    for idx, raw in enumerate(scenarios_raw):
        if not isinstance(raw, dict):
            raise SweepConfigError(f"scenario[{idx}] must be a JSON object")

        name = raw.get("name")
        if name is not None and not isinstance(name, str):
            raise SweepConfigError(f"scenario[{idx}].name must be a string")
        clean_name = name.strip() if isinstance(name, str) else None
        if clean_name == "":
            clean_name = None

        overrides = raw.get("overrides", {})
        if not isinstance(overrides, dict):
            raise SweepConfigError(f"scenario[{idx}].overrides must be a JSON object")

        prelim.append((idx, clean_name, overrides))

    all_named = all(name is not None for _, name, _ in prelim)
    if all_named:
        prelim.sort(key=lambda row: (row[1] or "", row[0]))

    used_ids: dict[str, int] = {}
    scenarios: list[_ScenarioDef] = []
    for ordinal, (source_index, name, overrides) in enumerate(prelim, start=1):
        base_id = _slugify(name) if name else f"scenario-{ordinal:03d}"
        count = used_ids.get(base_id, 0) + 1
        used_ids[base_id] = count
        scenario_id = base_id if count == 1 else f"{base_id}-{count}"
        scenarios.append(
            _ScenarioDef(
                source_index=source_index,
                name=name,
                overrides=overrides,
                scenario_id=scenario_id,
            )
        )
    return scenarios


def _apply_overrides(
    params: SweepRunParams,
    overrides: dict[str, Any],
) -> tuple[dict[str, Any], Optional[Decimal], str, int, int]:
    unknown = sorted(key for key in overrides if key not in _ALLOWED_OVERRIDE_KEYS)
    if unknown:
        raise SweepConfigError(
            f"unknown scenario override keys: {', '.join(unknown)}"
        )

    strategy_config = copy.deepcopy(params.strategy_config)
    strategy_patch = overrides.get("strategy_config")
    if strategy_patch is not None:
        if not isinstance(strategy_patch, dict):
            raise SweepConfigError("override 'strategy_config' must be a JSON object")
        strategy_config = _deep_merge_dicts(strategy_config, strategy_patch)

    fee_rate_bps = params.fee_rate_bps
    if "fee_rate_bps" in overrides:
        fee_rate_bps = _parse_optional_decimal(overrides["fee_rate_bps"], "fee_rate_bps")
        if fee_rate_bps is not None and fee_rate_bps < 0:
            raise SweepConfigError("override 'fee_rate_bps' must be non-negative")

    mark_method = params.mark_method
    if "mark_method" in overrides:
        if not isinstance(overrides["mark_method"], str):
            raise SweepConfigError("override 'mark_method' must be a string")
        try:
            mark_method = validate_mark_method(overrides["mark_method"])
        except StrategyRunConfigError as exc:
            raise SweepConfigError(str(exc)) from exc

    submit_ticks = params.latency_submit_ticks
    cancel_ticks = params.latency_cancel_ticks

    if "latency_ticks" in overrides:
        submit_ticks = _parse_non_negative_int(
            overrides["latency_ticks"], "latency_ticks"
        )
    if "cancel_latency_ticks" in overrides:
        cancel_ticks = _parse_non_negative_int(
            overrides["cancel_latency_ticks"], "cancel_latency_ticks"
        )
    if "latency_submit_ticks" in overrides:
        submit_ticks = _parse_non_negative_int(
            overrides["latency_submit_ticks"], "latency_submit_ticks"
        )
    if "latency_cancel_ticks" in overrides:
        cancel_ticks = _parse_non_negative_int(
            overrides["latency_cancel_ticks"], "latency_cancel_ticks"
        )
    if "latency_config" in overrides:
        latency_cfg = overrides["latency_config"]
        if not isinstance(latency_cfg, dict):
            raise SweepConfigError("override 'latency_config' must be a JSON object")
        if "submit_ticks" in latency_cfg:
            submit_ticks = _parse_non_negative_int(
                latency_cfg["submit_ticks"], "latency_config.submit_ticks"
            )
        if "cancel_ticks" in latency_cfg:
            cancel_ticks = _parse_non_negative_int(
                latency_cfg["cancel_ticks"], "latency_config.cancel_ticks"
            )

    return strategy_config, fee_rate_bps, mark_method, submit_ticks, cancel_ticks


def _build_aggregate_summary(
    scenario_rows: list[dict[str, Any]],
    scenario_stats: Optional[list[_ScenarioRunStats]] = None,
) -> dict[str, Any]:
    stats_rows = list(scenario_stats or [])
    if len(stats_rows) < len(scenario_rows):
        stats_rows.extend(
            _ScenarioRunStats(
                decisions_count=0,
                orders_count=0,
                fills_count=0,
                rejection_counts={},
            )
            for _ in range(len(scenario_rows) - len(stats_rows))
        )
    elif len(stats_rows) > len(scenario_rows):
        stats_rows = stats_rows[: len(scenario_rows)]

    total_decisions = sum(stats.decisions_count for stats in stats_rows)
    total_orders = sum(stats.orders_count for stats in stats_rows)
    total_fills = sum(stats.fills_count for stats in stats_rows)
    scenarios_with_trades = sum(1 for stats in stats_rows if stats.fills_count > 0)

    rejection_totals: dict[str, int] = {}
    for stats in stats_rows:
        for key, count in stats.rejection_counts.items():
            rejection_totals[key] = rejection_totals.get(key, 0) + count

    dominant_rejection_counts = [
        {"key": key, "count": count}
        for key, count in sorted(
            rejection_totals.items(), key=lambda item: (-item[1], item[0])
        )[:5]
    ]

    if not scenario_rows:
        return {
            "best_net_profit": None,
            "best_scenario": None,
            "median_net_profit": None,
            "median_scenario": None,
            "worst_net_profit": None,
            "worst_scenario": None,
            "total_decisions": total_decisions,
            "total_orders": total_orders,
            "total_fills": total_fills,
            "scenarios_with_trades": scenarios_with_trades,
            "dominant_rejection_counts": dominant_rejection_counts,
        }

    ranked = sorted(
        scenario_rows,
        key=lambda row: (Decimal(str(row["net_profit"])), row["scenario_id"]),
    )
    worst = ranked[0]
    median = ranked[len(ranked) // 2]
    best = ranked[-1]

    return {
        "best_net_profit": best["net_profit"],
        "best_scenario": best["scenario_id"],
        "best_run_id": best["run_id"],
        "median_net_profit": median["net_profit"],
        "median_scenario": median["scenario_id"],
        "median_run_id": median["run_id"],
        "worst_net_profit": worst["net_profit"],
        "worst_scenario": worst["scenario_id"],
        "worst_run_id": worst["run_id"],
        "total_decisions": total_decisions,
        "total_orders": total_orders,
        "total_fills": total_fills,
        "scenarios_with_trades": scenarios_with_trades,
        "dominant_rejection_counts": dominant_rejection_counts,
    }


def _read_scenario_run_stats(run_dir: Path) -> _ScenarioRunStats:
    manifest = _read_json_dict(run_dir / "run_manifest.json")
    decisions_count = _as_int(manifest.get("decisions_count"))
    fills_count = _as_int(manifest.get("fills_count"))
    orders_count = _count_non_empty_lines(run_dir / "orders.jsonl")

    rejection_counts: dict[str, int] = {}
    debug = manifest.get("strategy_debug")
    raw_counts = debug.get("rejection_counts") if isinstance(debug, dict) else None
    if isinstance(raw_counts, dict):
        for key, count in raw_counts.items():
            count_i = _as_int(count)
            if count_i <= 0:
                continue
            key_s = str(key).strip()
            if not key_s:
                continue
            rejection_counts[key_s] = rejection_counts.get(key_s, 0) + count_i

    return _ScenarioRunStats(
        decisions_count=decisions_count,
        orders_count=orders_count,
        fills_count=fills_count,
        rejection_counts=rejection_counts,
    )


def _derive_sweep_id(params: SweepRunParams, scenarios: list[_ScenarioDef]) -> str:
    tape_hash = _sha256_file(params.events_path)
    payload = {
        "tape_path": params.events_path.as_posix(),
        "tape_sha256": tape_hash,
        "strategy_name": params.strategy_name,
        "strategy_config": params.strategy_config,
        "asset_id": params.asset_id,
        "starting_cash": str(params.starting_cash),
        "fee_rate_bps": str(params.fee_rate_bps) if params.fee_rate_bps is not None else None,
        "mark_method": params.mark_method,
        "latency_submit_ticks": params.latency_submit_ticks,
        "latency_cancel_ticks": params.latency_cancel_ticks,
        "strict": params.strict,
        "scenarios": [
            {
                "source_index": scenario.source_index,
                "name": scenario.name,
                "overrides": scenario.overrides,
            }
            for scenario in scenarios
        ],
    }
    canonical = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        default=str,
    )
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:12]
    return f"sweep-{digest}"


def _sha256_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with open(path, "rb") as fh:
        while True:
            chunk = fh.read(1024 * 1024)
            if not chunk:
                break
            hasher.update(chunk)
    return hasher.hexdigest()


def _slugify(name: Optional[str]) -> str:
    if not name:
        return "scenario"
    slug = _SLUG_RE.sub("-", name.lower()).strip("-")
    return slug or "scenario"


def _deep_merge_dicts(base: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    merged = copy.deepcopy(base)
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge_dicts(merged[key], value)
        else:
            merged[key] = copy.deepcopy(value)
    return merged


def _parse_optional_decimal(value: Any, field_name: str) -> Optional[Decimal]:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise SweepConfigError(
            f"override '{field_name}' must be numeric or null"
        ) from exc


def _parse_non_negative_int(value: Any, field_name: str) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise SweepConfigError(f"override '{field_name}' must be an integer") from exc
    if parsed < 0:
        raise SweepConfigError(f"override '{field_name}' must be non-negative")
    return parsed


def _as_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _read_json_dict(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}
    return payload if isinstance(payload, dict) else {}


def _count_non_empty_lines(path: Path) -> int:
    if not path.exists():
        return 0
    count = 0
    try:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                if line.strip():
                    count += 1
    except Exception:  # noqa: BLE001
        return 0
    return count


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
