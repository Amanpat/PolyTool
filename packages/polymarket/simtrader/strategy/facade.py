"""Facade helpers for single SimTrader strategy runs.

This module centralizes strategy loading + ``StrategyRunner`` wiring so both
CLI commands and higher-level orchestrators (for example sweeps) can reuse the
exact same execution path.
"""

from __future__ import annotations

import importlib
import json
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any, Optional

from ..broker.latency import LatencyConfig
from ..portfolio.mark import MARK_BID, MARK_MID
from .runner import StrategyRunner

STRATEGY_REGISTRY: dict[str, str] = {
    "copy_wallet_replay": (
        "packages.polymarket.simtrader.strategies.copy_wallet_replay.CopyWalletReplay"
    ),
    "binary_complement_arb": (
        "packages.polymarket.simtrader.strategies.binary_complement_arb.BinaryComplementArb"
    ),
}

_MARK_METHODS = frozenset({MARK_BID, MARK_MID})
_SUMMARY_METRIC_KEYS = (
    "net_profit",
    "realized_pnl",
    "unrealized_pnl",
    "total_fees",
)


class StrategyRunConfigError(ValueError):
    """Raised when run configuration is invalid."""


@dataclass(frozen=True)
class StrategyRunParams:
    """Typed parameters for one ``StrategyRunner`` execution."""

    events_path: Path
    run_dir: Path
    strategy_name: str
    strategy_config: dict[str, Any]
    asset_id: Optional[str] = None
    starting_cash: Decimal = Decimal("1000")
    fee_rate_bps: Optional[Decimal] = None
    mark_method: str = MARK_BID
    latency_submit_ticks: int = 0
    latency_cancel_ticks: int = 0
    strict: bool = False
    allow_degraded: bool = False


@dataclass(frozen=True)
class StrategyRunResult:
    """High-level result summary for one strategy run."""

    run_id: str
    run_dir: Path
    summary: dict[str, Any]
    metrics: dict[str, str]
    warnings_count: int


def known_strategies() -> list[str]:
    """Return known strategy names in deterministic order."""
    return sorted(STRATEGY_REGISTRY)


def validate_mark_method(mark_method: str) -> str:
    """Validate mark method and return it."""
    if mark_method not in _MARK_METHODS:
        known = ", ".join(sorted(_MARK_METHODS))
        raise StrategyRunConfigError(
            f"unknown mark_method {mark_method!r}; expected one of: {known}"
        )
    return mark_method


def run_strategy(params: StrategyRunParams) -> StrategyRunResult:
    """Run one strategy and return parsed metrics from the run artifacts."""
    if not params.events_path.exists():
        raise StrategyRunConfigError(f"tape file not found: {params.events_path}")
    if params.starting_cash < 0:
        raise StrategyRunConfigError("starting_cash must be non-negative")
    if params.fee_rate_bps is not None and params.fee_rate_bps < 0:
        raise StrategyRunConfigError("fee_rate_bps must be non-negative")
    if params.latency_submit_ticks < 0:
        raise StrategyRunConfigError("latency_submit_ticks must be non-negative")
    if params.latency_cancel_ticks < 0:
        raise StrategyRunConfigError("latency_cancel_ticks must be non-negative")
    validate_mark_method(params.mark_method)

    strategy = _build_strategy(params.strategy_name, params.strategy_config)

    extra_book_asset_ids: list[str] = []
    if isinstance(params.strategy_config.get("extra_book_asset_ids"), list):
        extra_book_asset_ids = [
            str(x) for x in params.strategy_config["extra_book_asset_ids"]
        ]
    else:
        no_asset_id = getattr(strategy, "_no_id", None)
        if isinstance(no_asset_id, str) and no_asset_id:
            extra_book_asset_ids = [no_asset_id]

    runner = StrategyRunner(
        events_path=params.events_path,
        run_dir=params.run_dir,
        strategy=strategy,
        asset_id=params.asset_id,
        extra_book_asset_ids=extra_book_asset_ids or None,
        latency=LatencyConfig(
            submit_ticks=params.latency_submit_ticks,
            cancel_ticks=params.latency_cancel_ticks,
        ),
        starting_cash=params.starting_cash,
        fee_rate_bps=params.fee_rate_bps,
        mark_method=params.mark_method,
        strict=params.strict,
        allow_degraded=params.allow_degraded,
    )

    summary = runner.run()
    warnings_count = _read_warnings_count(params.run_dir / "run_manifest.json")
    metrics = {key: str(summary.get(key, "0")) for key in _SUMMARY_METRIC_KEYS}

    return StrategyRunResult(
        run_id=params.run_dir.name,
        run_dir=params.run_dir,
        summary=summary,
        metrics=metrics,
        warnings_count=warnings_count,
    )


def _build_strategy(strategy_name: str, strategy_config: dict[str, Any]) -> Any:
    if not isinstance(strategy_config, dict):
        raise StrategyRunConfigError("strategy_config must be a JSON object")
    if strategy_name not in STRATEGY_REGISTRY:
        known = ", ".join(known_strategies())
        raise StrategyRunConfigError(
            f"unknown strategy {strategy_name!r}. Known: {known}"
        )
    module_path, class_name = STRATEGY_REGISTRY[strategy_name].rsplit(".", 1)
    try:
        module = importlib.import_module(module_path)
        strategy_cls = getattr(module, class_name)
    except (ImportError, AttributeError) as exc:
        raise StrategyRunConfigError(
            f"could not load strategy {strategy_name!r}: {exc}"
        ) from exc
    try:
        return strategy_cls(**strategy_config)
    except TypeError as exc:
        raise StrategyRunConfigError(
            f"invalid strategy config for {strategy_name!r}: {exc}"
        ) from exc


def _read_warnings_count(manifest_path: Path) -> int:
    if not manifest_path.exists():
        return 0
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return 0
    warnings = payload.get("warnings")
    if isinstance(warnings, list):
        return len(warnings)
    return 0
