"""Facade helpers for single SimTrader strategy runs.

This module centralizes strategy loading + ``StrategyRunner`` wiring so both
CLI commands and higher-level orchestrators (for example sweeps) can reuse the
exact same execution path.
"""

from __future__ import annotations

import copy
import importlib
import json
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any, Optional

from ..broker.latency import LatencyConfig
from ..execution.adverse_selection import (
    AdverseSelectionGuard,
    GuardResult,
    MMWithdrawalSignal,
    OFISignal,
    ORDER_FLOW_SIGNAL_PROXY,
    UnavailableVPINSignal,
    build_adverse_selection_truth_surface,
)
from ..portfolio.mark import MARK_BID, MARK_MID
from .base import OrderIntent, Strategy
from .runner import StrategyRunner

STRATEGY_REGISTRY: dict[str, str] = {
    "copy_wallet_replay": (
        "packages.polymarket.simtrader.strategies.copy_wallet_replay.CopyWalletReplay"
    ),
    "binary_complement_arb": (
        "packages.polymarket.simtrader.strategies.binary_complement_arb.BinaryComplementArb"
    ),
    "market_maker_v0": (
        "packages.polymarket.simtrader.strategies.market_maker_v0.MarketMakerV0"
    ),
    "market_maker_v1": (
        "packages.polymarket.simtrader.strategies.market_maker_v1.MarketMakerV1"
    ),
    "sports_momentum": (
        "packages.polymarket.simtrader.strategies.sports_momentum.SportsMomentum"
    ),
    "sports_favorite": (
        "packages.polymarket.simtrader.strategies.sports_favorite.SportsFavorite"
    ),
    "sports_vwap": (
        "packages.polymarket.simtrader.strategies.sports_vwap.SportsVWAP"
    ),
}

_MARK_METHODS = frozenset({MARK_BID, MARK_MID})
_SUMMARY_METRIC_KEYS = (
    "net_profit",
    "realized_pnl",
    "unrealized_pnl",
    "total_fees",
)
_MARKET_MAKER_V1 = "market_maker_v1"
_ADVERSE_SELECTION_CONFIG_KEY = "adverse_selection"
_ADVERSE_SELECTION_ALLOWED_KEYS = frozenset(
    {"enabled", "order_flow_signal", "ofi", "mm_withdrawal"}
)
_DEFAULT_ADVERSE_SELECTION_CONFIG: dict[str, Any] = {
    "enabled": True,
    "order_flow_signal": ORDER_FLOW_SIGNAL_PROXY,
}


class StrategyRunConfigError(ValueError):
    """Raised when run configuration is invalid."""


class _GuardedMarketMakerStrategy(Strategy):
    """Wrap one strategy instance and suppress submits while the guard is active."""

    def __init__(self, inner: Strategy, guard: AdverseSelectionGuard) -> None:
        self._inner = inner
        self._adverse_selection_guard = guard
        existing_counts = getattr(inner, "rejection_counts", None)
        if isinstance(existing_counts, dict):
            self.rejection_counts = existing_counts
        else:
            self.rejection_counts: dict[str, int] = {}
            setattr(inner, "rejection_counts", self.rejection_counts)
        self.last_guard_result: GuardResult | None = None

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)

    def on_start(self, asset_id: str, starting_cash: Decimal) -> None:
        self._inner.on_start(asset_id, starting_cash)

    def on_event(
        self,
        event: dict,
        seq: int,
        ts_recv: float,
        best_bid: Optional[float],
        best_ask: Optional[float],
        open_orders: dict[str, Any],
    ) -> list[OrderIntent]:
        intents = list(
            self._inner.on_event(
                event,
                seq,
                ts_recv,
                best_bid,
                best_ask,
                open_orders,
            )
        )
        if not intents:
            return intents

        book = getattr(self._inner, "_book", None)
        if book is None:
            return self._suppress_submit_intents(intents)

        self._adverse_selection_guard.on_book_update(book)
        guard_result = self._adverse_selection_guard.check()
        self.last_guard_result = guard_result
        if not guard_result.blocked:
            return intents
        return self._suppress_submit_intents(intents)

    def on_fill(
        self,
        order_id: str,
        asset_id: str,
        side: str,
        fill_price: Decimal,
        fill_size: Decimal,
        fill_status: str,
        seq: int,
        ts_recv: float,
    ) -> None:
        self._inner.on_fill(
            order_id=order_id,
            asset_id=asset_id,
            side=side,
            fill_price=fill_price,
            fill_size=fill_size,
            fill_status=fill_status,
            seq=seq,
            ts_recv=ts_recv,
        )

    def on_finish(self) -> None:
        self._inner.on_finish()

    def _suppress_submit_intents(
        self,
        intents: list[OrderIntent],
    ) -> list[OrderIntent]:
        filtered: list[OrderIntent] = []
        blocked_submits = 0
        for intent in intents:
            if intent.action == "submit":
                blocked_submits += 1
                continue
            filtered.append(intent)

        if blocked_submits:
            self.rejection_counts["adverse_selection"] = (
                int(self.rejection_counts.get("adverse_selection", 0))
                + blocked_submits
            )

        return filtered


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
    strategy_preset: Optional[str] = None
    market_slug: Optional[str] = None
    fee_category: Optional[str] = None
    fee_role: str = "taker"


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
        fee_category=params.fee_category,
        fee_role=params.fee_role,
        strict=params.strict,
        allow_degraded=params.allow_degraded,
        strategy_name=params.strategy_name,
        strategy_preset=params.strategy_preset,
        market_slug=params.market_slug,
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

    constructor_config, adverse_selection_config = _split_strategy_config(
        strategy_name,
        strategy_config,
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
        strategy = strategy_cls(**constructor_config)
    except TypeError as exc:
        raise StrategyRunConfigError(
            f"invalid strategy config for {strategy_name!r}: {exc}"
        ) from exc

    if adverse_selection_config is None:
        return strategy

    adverse_selection_surface = _build_adverse_selection_surface(
        adverse_selection_config
    )
    _attach_adverse_selection_surface(strategy, adverse_selection_surface)
    if not adverse_selection_config["enabled"]:
        return strategy

    wrapped_strategy = _GuardedMarketMakerStrategy(
        strategy,
        _build_adverse_selection_guard(adverse_selection_config),
    )
    _attach_adverse_selection_surface(wrapped_strategy, adverse_selection_surface)
    return wrapped_strategy


def _split_strategy_config(
    strategy_name: str,
    strategy_config: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    constructor_config = dict(strategy_config)
    raw_adverse_selection = constructor_config.pop(_ADVERSE_SELECTION_CONFIG_KEY, None)

    if strategy_name != _MARKET_MAKER_V1:
        if raw_adverse_selection is not None:
            raise StrategyRunConfigError(
                f"{_ADVERSE_SELECTION_CONFIG_KEY!r} is supported only for "
                f"{_MARKET_MAKER_V1!r}"
            )
        return constructor_config, None

    if raw_adverse_selection is None:
        raw_adverse_selection = copy.deepcopy(_DEFAULT_ADVERSE_SELECTION_CONFIG)

    adverse_selection_config = _normalize_adverse_selection_config(
        raw_adverse_selection
    )
    return constructor_config, adverse_selection_config


def _normalize_adverse_selection_config(raw_config: Any) -> dict[str, Any]:
    if isinstance(raw_config, bool):
        return {
            "enabled": raw_config,
            "order_flow_signal": ORDER_FLOW_SIGNAL_PROXY,
        }

    if not isinstance(raw_config, dict):
        raise StrategyRunConfigError(
            "adverse_selection must be a boolean or JSON object"
        )

    unknown_keys = sorted(set(raw_config) - _ADVERSE_SELECTION_ALLOWED_KEYS)
    if unknown_keys:
        unknown = ", ".join(repr(key) for key in unknown_keys)
        raise StrategyRunConfigError(
            f"unknown adverse_selection keys: {unknown}"
        )

    enabled = raw_config.get("enabled", True)
    if not isinstance(enabled, bool):
        raise StrategyRunConfigError(
            "adverse_selection.enabled must be true or false"
        )

    order_flow_signal = raw_config.get("order_flow_signal", ORDER_FLOW_SIGNAL_PROXY)
    if not isinstance(order_flow_signal, str):
        raise StrategyRunConfigError(
            "adverse_selection.order_flow_signal must be a string"
        )
    try:
        truth_surface = build_adverse_selection_truth_surface(
            enabled=enabled,
            order_flow_signal=order_flow_signal,
        )
    except ValueError as exc:
        raise StrategyRunConfigError(
            f"invalid adverse_selection config: {exc}"
        ) from exc

    normalized: dict[str, Any] = {
        "enabled": enabled,
        "order_flow_signal": str(
            truth_surface["requested_order_flow_signal"]
        ),
    }
    for key in ("ofi", "mm_withdrawal"):
        value = raw_config.get(key)
        if value is None:
            continue
        if not isinstance(value, dict):
            raise StrategyRunConfigError(
                f"adverse_selection.{key} must be a JSON object"
            )
        normalized[key] = dict(value)
    return normalized


def _build_adverse_selection_surface(
    guard_config: dict[str, Any],
) -> dict[str, Any]:
    return build_adverse_selection_truth_surface(
        enabled=bool(guard_config.get("enabled", True)),
        order_flow_signal=str(
            guard_config.get("order_flow_signal", ORDER_FLOW_SIGNAL_PROXY)
        ),
    )


def _attach_adverse_selection_surface(
    strategy: Any,
    surface: dict[str, Any],
) -> None:
    setattr(strategy, "adverse_selection_surface", dict(surface))


def _build_adverse_selection_guard(
    guard_config: dict[str, Any],
) -> AdverseSelectionGuard:
    ofi_config = dict(guard_config.get("ofi", {}))
    mm_config = dict(guard_config.get("mm_withdrawal", {}))
    order_flow_signal = str(
        guard_config.get("order_flow_signal", ORDER_FLOW_SIGNAL_PROXY)
    )
    try:
        if order_flow_signal == ORDER_FLOW_SIGNAL_PROXY:
            order_flow_guard: Any = OFISignal(**ofi_config)
        else:
            order_flow_guard = UnavailableVPINSignal()
        return AdverseSelectionGuard(
            ofi=order_flow_guard,
            mm_withdrawal=MMWithdrawalSignal(**mm_config),
        )
    except (TypeError, ValueError) as exc:
        raise StrategyRunConfigError(
            f"invalid adverse_selection config: {exc}"
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
