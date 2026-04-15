"""Paper-mode runtime shell for the crypto-pair runner."""

from __future__ import annotations

import math
import time
from collections import deque
from dataclasses import dataclass, field, replace as dataclass_replace
from decimal import Decimal, ROUND_DOWN
from pathlib import Path
from typing import Any, Callable, Optional, Protocol

from packages.polymarket.simtrader.execution.kill_switch import FileBasedKillSwitch

from .accumulation_engine import (
    ACTION_ACCUMULATE,
    ACTION_FREEZE,
    BestQuote,
    PairMarketState,
    evaluate_accumulation,
    evaluate_directional_entry,
)
from .config_models import CryptoPairPaperModeConfig
from .market_discovery import discover_crypto_pair_markets
from .opportunity_scan import PairOpportunity, rank_opportunities, scan_opportunities
from .paper_ledger import (
    LEG_NO,
    LEG_YES,
    PaperLegFill,
    PaperOpportunityObservation,
    build_market_rollups,
    build_run_summary,
    compute_partial_leg_exposure,
    generate_order_intent,
    get_order_intent_block_reason,
)
from .clickhouse_sink import (
    CryptoPairClickHouseEventWriter,
    DisabledCryptoPairClickHouseSink,
)
from .event_models import (
    IntentGeneratedEvent,
    OpportunityObservedEvent,
    PartialExposureUpdatedEvent,
    SafetyStateTransitionEvent,
    SimulatedFillRecordedEvent,
    build_events_from_paper_records,
)
from .position_store import CryptoPairPositionStore, iso_utc, utc_now
from .reference_feed import (
    FeedConnectionState,
    ReferencePriceSnapshot,
    build_reference_feed,
    normalize_reference_feed_provider,
)


DEFAULT_PAPER_ARTIFACTS_DIR = Path("artifacts/tapes/crypto/paper_runs")
DEFAULT_KILL_SWITCH_PATH = Path("artifacts/crypto_pairs/kill_switch.txt")

_ZERO = Decimal("0")
_ONE_BPS = Decimal("10000")
_OPERATOR_MAX_CAPITAL_PER_MARKET_USDC = Decimal("10")
_OPERATOR_MAX_OPEN_PAIRS = 5
_OPERATOR_DAILY_LOSS_CAP_USDC = Decimal("15")
_OPERATOR_MAX_CAPITAL_PER_WINDOW_USDC = Decimal("50")
_OPERATOR_MIN_EDGE_BUFFER_PER_LEG = Decimal("0.01")
_OPERATOR_MIN_PROFIT_THRESHOLD_USDC = Decimal("0.03")
_STOPPED_REASON_COMPLETED = "completed"
_STOPPED_REASON_OPERATOR_INTERRUPT = "operator_interrupt"


class ReferenceFeed(Protocol):
    """Minimal reference-feed contract used by the runner."""

    def connect(self) -> None: ...

    def disconnect(self) -> None: ...

    def get_snapshot(self, symbol: str) -> ReferencePriceSnapshot: ...


class PaperExecutionAdapter(Protocol):
    """Deterministic paper execution interface."""

    def simulate_fills(
        self,
        *,
        intent,
        selected_legs: tuple[str, ...],
        filled_at: str,
    ) -> list[PaperLegFill]: ...


def build_default_paper_mode_config() -> CryptoPairPaperModeConfig:
    return CryptoPairPaperModeConfig.from_dict(
        {
            "max_capital_per_market_usdc": str(_OPERATOR_MAX_CAPITAL_PER_MARKET_USDC),
            "max_open_paired_notional_usdc": "50",
            "edge_buffer_per_leg": "0.04",
            "max_pair_completion_pct": "0.80",
            "min_projected_profit": "0.03",
            "fees": {
                "maker_rebate_bps": "20",
                "maker_fee_bps": "0",
                "taker_fee_bps": "0",
            },
            "safety": {
                "stale_quote_timeout_seconds": 15,
                "max_unpaired_exposure_seconds": 120,
                "block_new_intents_with_open_unpaired": True,
                "require_fresh_quotes": True,
            },
        }
    )


@dataclass(frozen=True)
class CryptoPairRunnerSettings:
    """Shared runtime settings for paper and live shells."""

    paper_config: CryptoPairPaperModeConfig = field(default_factory=build_default_paper_mode_config)
    artifact_base_dir: Path = DEFAULT_PAPER_ARTIFACTS_DIR
    kill_switch_path: Path = DEFAULT_KILL_SWITCH_PATH
    duration_seconds: int = 30
    cycle_interval_seconds: float = 0.5
    max_open_pairs: int = _OPERATOR_MAX_OPEN_PAIRS
    daily_loss_cap_usdc: Decimal = _OPERATOR_DAILY_LOSS_CAP_USDC
    max_capital_per_window_usdc: Decimal = _OPERATOR_MAX_CAPITAL_PER_WINDOW_USDC
    min_profit_threshold_usdc: Decimal = _OPERATOR_MIN_PROFIT_THRESHOLD_USDC
    symbol_filters: tuple[str, ...] = ()
    duration_filters: tuple[int, ...] = ()
    reference_feed_provider: str = "binance"
    cycle_limit: Optional[int] = None
    heartbeat_interval_seconds: int = 0
    sink_flush_mode: str = "batch"

    def __post_init__(self) -> None:
        object.__setattr__(self, "artifact_base_dir", Path(self.artifact_base_dir))
        object.__setattr__(self, "kill_switch_path", Path(self.kill_switch_path))
        object.__setattr__(
            self,
            "daily_loss_cap_usdc",
            Decimal(str(self.daily_loss_cap_usdc)),
        )
        object.__setattr__(
            self,
            "max_capital_per_window_usdc",
            Decimal(str(self.max_capital_per_window_usdc)),
        )
        object.__setattr__(
            self,
            "min_profit_threshold_usdc",
            Decimal(str(self.min_profit_threshold_usdc)),
        )
        object.__setattr__(
            self,
            "symbol_filters",
            tuple(
                sorted(
                    {
                        symbol.strip().upper()
                        for symbol in self.symbol_filters
                        if str(symbol).strip()
                    }
                )
            ),
        )
        object.__setattr__(
            self,
            "duration_filters",
            tuple(sorted({int(duration) for duration in self.duration_filters})),
        )
        object.__setattr__(
            self,
            "reference_feed_provider",
            normalize_reference_feed_provider(self.reference_feed_provider),
        )

        if self.sink_flush_mode not in ("batch", "streaming"):
            raise ValueError(
                f"sink_flush_mode must be 'batch' or 'streaming', got {self.sink_flush_mode!r}"
            )

        if self.duration_seconds < 0:
            raise ValueError("duration_seconds must be >= 0")
        if self.heartbeat_interval_seconds < 0:
            raise ValueError("heartbeat_interval_seconds must be >= 0")
        if self.cycle_interval_seconds <= 0:
            raise ValueError("cycle_interval_seconds must be > 0")
        if self.max_open_pairs <= 0:
            raise ValueError("max_open_pairs must be > 0")
        if self.max_open_pairs > _OPERATOR_MAX_OPEN_PAIRS:
            raise ValueError(
                f"v0 max_open_pairs cannot exceed {_OPERATOR_MAX_OPEN_PAIRS}"
            )
        if self.daily_loss_cap_usdc <= _ZERO:
            raise ValueError("daily_loss_cap_usdc must be > 0")
        if self.daily_loss_cap_usdc > _OPERATOR_DAILY_LOSS_CAP_USDC:
            raise ValueError(
                f"v0 daily_loss_cap_usdc cannot exceed {_OPERATOR_DAILY_LOSS_CAP_USDC}"
            )
        if self.max_capital_per_window_usdc <= _ZERO:
            raise ValueError("max_capital_per_window_usdc must be > 0")
        if self.max_capital_per_window_usdc > _OPERATOR_MAX_CAPITAL_PER_WINDOW_USDC:
            raise ValueError(
                f"v0 max_capital_per_window_usdc cannot exceed {_OPERATOR_MAX_CAPITAL_PER_WINDOW_USDC}"
            )
        if self.min_profit_threshold_usdc < _OPERATOR_MIN_PROFIT_THRESHOLD_USDC:
            raise ValueError(
                f"v0 min_profit_threshold_usdc cannot be below {_OPERATOR_MIN_PROFIT_THRESHOLD_USDC}"
            )
        if (
            self.paper_config.max_capital_per_market_usdc
            > _OPERATOR_MAX_CAPITAL_PER_MARKET_USDC
        ):
            raise ValueError(
                "v0 max_capital_per_market_usdc cannot exceed "
                f"{_OPERATOR_MAX_CAPITAL_PER_MARKET_USDC}"
            )
        if self.paper_config.edge_buffer_per_leg < _OPERATOR_MIN_EDGE_BUFFER_PER_LEG:
            raise ValueError(
                f"v0 edge_buffer_per_leg cannot be below {_OPERATOR_MIN_EDGE_BUFFER_PER_LEG}"
            )

    def with_artifact_base_dir(
        self,
        artifact_base_dir: Path,
    ) -> "CryptoPairRunnerSettings":
        return CryptoPairRunnerSettings(
            paper_config=self.paper_config,
            artifact_base_dir=artifact_base_dir,
            kill_switch_path=self.kill_switch_path,
            duration_seconds=self.duration_seconds,
            cycle_interval_seconds=self.cycle_interval_seconds,
            max_open_pairs=self.max_open_pairs,
            daily_loss_cap_usdc=self.daily_loss_cap_usdc,
            max_capital_per_window_usdc=self.max_capital_per_window_usdc,
            min_profit_threshold_usdc=self.min_profit_threshold_usdc,
            symbol_filters=self.symbol_filters,
            duration_filters=self.duration_filters,
            reference_feed_provider=self.reference_feed_provider,
            cycle_limit=self.cycle_limit,
            heartbeat_interval_seconds=self.heartbeat_interval_seconds,
            sink_flush_mode=self.sink_flush_mode,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "paper_config": self.paper_config.to_dict(),
            "artifact_base_dir": str(self.artifact_base_dir),
            "kill_switch_path": str(self.kill_switch_path),
            "duration_seconds": self.duration_seconds,
            "cycle_interval_seconds": self.cycle_interval_seconds,
            "max_open_pairs": self.max_open_pairs,
            "daily_loss_cap_usdc": str(self.daily_loss_cap_usdc),
            "max_capital_per_window_usdc": str(self.max_capital_per_window_usdc),
            "min_profit_threshold_usdc": str(self.min_profit_threshold_usdc),
            "symbol_filters": list(self.symbol_filters),
            "duration_filters": list(self.duration_filters),
            "reference_feed_provider": self.reference_feed_provider,
            "cycle_limit": self.cycle_limit,
            "heartbeat_interval_seconds": self.heartbeat_interval_seconds,
            "sink_flush_mode": self.sink_flush_mode,
        }


def build_runner_settings(
    *,
    config_payload: Optional[dict[str, Any]] = None,
    artifact_base_dir: Optional[Path] = None,
    kill_switch_path: Optional[Path] = None,
    duration_seconds: Optional[int] = None,
    symbol_filters: Optional[tuple[str, ...]] = None,
    duration_filters: Optional[tuple[int, ...]] = None,
    cycle_limit: Optional[int] = None,
    heartbeat_interval_seconds: Optional[int] = None,
) -> CryptoPairRunnerSettings:
    payload = dict(config_payload or {})
    default_paper_payload = build_default_paper_mode_config().to_dict()
    override_paper_payload = payload.get("paper_config")
    if override_paper_payload is None:
        override_paper_payload = {
            key: payload[key]
            for key in (
                "filters",
                "max_capital_per_market_usdc",
                "max_open_paired_notional_usdc",
                "edge_buffer_per_leg",
                "max_pair_completion_pct",
                "min_projected_profit",
                "fees",
                "safety",
            )
            if key in payload
        }
    paper_payload = dict(default_paper_payload)
    for key, value in dict(override_paper_payload or {}).items():
        if key in {"filters", "fees", "safety"} and isinstance(value, dict):
            merged = dict(paper_payload.get(key, {}))
            merged.update(value)
            paper_payload[key] = merged
        else:
            paper_payload[key] = value
    paper_config = CryptoPairPaperModeConfig.from_dict(paper_payload)
    return CryptoPairRunnerSettings(
        paper_config=paper_config,
        artifact_base_dir=artifact_base_dir
        or Path(payload.get("artifact_base_dir", DEFAULT_PAPER_ARTIFACTS_DIR)),
        kill_switch_path=kill_switch_path
        or Path(payload.get("kill_switch_path", DEFAULT_KILL_SWITCH_PATH)),
        duration_seconds=duration_seconds
        if duration_seconds is not None
        else int(payload.get("duration_seconds", 30)),
        cycle_interval_seconds=float(payload.get("cycle_interval_seconds", 0.5)),
        max_open_pairs=int(payload.get("max_open_pairs", _OPERATOR_MAX_OPEN_PAIRS)),
        daily_loss_cap_usdc=payload.get(
            "daily_loss_cap_usdc",
            _OPERATOR_DAILY_LOSS_CAP_USDC,
        ),
        max_capital_per_window_usdc=payload.get(
            "max_capital_per_window_usdc",
            _OPERATOR_MAX_CAPITAL_PER_WINDOW_USDC,
        ),
        min_profit_threshold_usdc=payload.get(
            "min_profit_threshold_usdc",
            _OPERATOR_MIN_PROFIT_THRESHOLD_USDC,
        ),
        symbol_filters=symbol_filters
        if symbol_filters is not None
        else tuple(payload.get("symbol_filters", ())),
        duration_filters=duration_filters
        if duration_filters is not None
        else tuple(payload.get("duration_filters", ())),
        reference_feed_provider=payload.get("reference_feed_provider", "binance"),
        cycle_limit=cycle_limit if cycle_limit is not None else payload.get("cycle_limit"),
        heartbeat_interval_seconds=heartbeat_interval_seconds
        if heartbeat_interval_seconds is not None
        else int(payload.get("heartbeat_interval_seconds", 0)),
        sink_flush_mode=payload.get("sink_flush_mode", "batch"),
    )


@dataclass(frozen=True)
class PaperRunnerResult:
    run_id: str
    mode: str
    artifact_dir: str
    stopped_reason: str
    cycles_completed: int
    manifest_path: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "mode": self.mode,
            "artifact_dir": self.artifact_dir,
            "stopped_reason": self.stopped_reason,
            "cycles_completed": self.cycles_completed,
            "manifest_path": self.manifest_path,
        }


@dataclass(frozen=True)
class PaperRunnerHeartbeat:
    recorded_at: str
    cycle: int
    elapsed_seconds: int
    elapsed_runtime: str
    opportunities_observed: int
    intents_generated: int
    completed_pairs: int
    partial_exposure_count: int
    open_pairs: int
    latest_feed_states: dict[str, str]
    stale_symbols: list[str]
    degraded_symbols: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "recorded_at": self.recorded_at,
            "cycle": self.cycle,
            "elapsed_seconds": self.elapsed_seconds,
            "elapsed_runtime": self.elapsed_runtime,
            "opportunities_observed": self.opportunities_observed,
            "intents_generated": self.intents_generated,
            "completed_pairs": self.completed_pairs,
            "partial_exposure_count": self.partial_exposure_count,
            "open_pairs": self.open_pairs,
            "latest_feed_states": dict(self.latest_feed_states),
            "stale_symbols": list(self.stale_symbols),
            "degraded_symbols": list(self.degraded_symbols),
        }


class DeterministicPaperExecutionAdapter:
    """Default paper fill simulator."""

    def simulate_fills(
        self,
        *,
        intent,
        selected_legs: tuple[str, ...],
        filled_at: str,
    ) -> list[PaperLegFill]:
        fills: list[PaperLegFill] = []
        for leg in selected_legs:
            if leg == LEG_YES:
                token_id = intent.yes_token_id
                price = intent.intended_yes_price
            else:
                token_id = intent.no_token_id
                price = intent.intended_no_price
            notional = price * intent.pair_size
            fee_adjustment = (
                notional * (intent.maker_rebate_bps - intent.maker_fee_bps) / _ONE_BPS
            ).quantize(Decimal("0.0001"))
            fills.append(
                PaperLegFill(
                    fill_id=f"{intent.intent_id}-{leg.lower()}",
                    run_id=intent.run_id,
                    intent_id=intent.intent_id,
                    market_id=intent.market_id,
                    condition_id=intent.condition_id,
                    slug=intent.slug,
                    symbol=intent.symbol,
                    duration_min=intent.duration_min,
                    leg=leg,
                    token_id=token_id,
                    side="BUY",
                    filled_at=filled_at,
                    price=price,
                    size=intent.pair_size,
                    fee_adjustment_usdc=fee_adjustment,
                )
            )
        return fills


class DirectionalPaperExecutionAdapter:
    """Paper fill simulator for directional (momentum) entries.

    Favorite leg fills at current ask (taker). Hedge leg fills only if the
    current ask is at or below config.momentum.max_hedge_price.
    """

    def __init__(self, max_hedge_price: float) -> None:
        self._max_hedge_price = Decimal(str(max_hedge_price))

    def simulate_fills(
        self,
        *,
        intent,
        selected_legs: tuple[str, ...],
        filled_at: str,
    ) -> list[PaperLegFill]:
        fills: list[PaperLegFill] = []
        for leg in selected_legs:
            if leg == LEG_YES:
                token_id = intent.yes_token_id
                price = intent.intended_yes_price
            else:
                token_id = intent.no_token_id
                price = intent.intended_no_price

            # Hedge leg: only fill if the ask is at or below max_hedge_price
            hedge_leg = LEG_NO if selected_legs[0] == LEG_YES else LEG_YES
            if leg == hedge_leg and price > self._max_hedge_price:
                continue  # hedge ask too high; maker limit not filled

            notional = price * intent.pair_size
            fee_adjustment = (
                notional * (intent.maker_rebate_bps - intent.maker_fee_bps) / _ONE_BPS
            ).quantize(Decimal("0.0001"))
            fills.append(
                PaperLegFill(
                    fill_id=f"{intent.intent_id}-{leg.lower()}",
                    run_id=intent.run_id,
                    intent_id=intent.intent_id,
                    market_id=intent.market_id,
                    condition_id=intent.condition_id,
                    slug=intent.slug,
                    symbol=intent.symbol,
                    duration_min=intent.duration_min,
                    leg=leg,
                    token_id=token_id,
                    side="BUY",
                    filled_at=filled_at,
                    price=price,
                    size=intent.pair_size,
                    fee_adjustment_usdc=fee_adjustment,
                )
            )
        return fills


def classify_feed_state(snapshot: Optional[ReferencePriceSnapshot]) -> str:
    if snapshot is None:
        return "no_snapshot"
    if snapshot.connection_state == FeedConnectionState.DISCONNECTED:
        return "disconnected"
    if snapshot.connection_state == FeedConnectionState.NEVER_CONNECTED:
        return "never_connected"
    if snapshot.is_stale:
        return "stale"
    return "connected_fresh"


def cycle_count_from_settings(settings: CryptoPairRunnerSettings) -> int:
    if settings.cycle_limit is not None:
        return max(1, int(settings.cycle_limit))
    if settings.duration_seconds <= 0:
        return 1
    return max(
        1,
        math.ceil(settings.duration_seconds / settings.cycle_interval_seconds),
    )


def apply_market_filters(
    opportunities: list[PairOpportunity],
    settings: CryptoPairRunnerSettings,
) -> list[PairOpportunity]:
    filtered = list(opportunities)
    if settings.symbol_filters:
        filtered = [
            opportunity
            for opportunity in filtered
            if opportunity.symbol.upper() in settings.symbol_filters
        ]
    if settings.duration_filters:
        filtered = [
            opportunity
            for opportunity in filtered
            if opportunity.duration_min in settings.duration_filters
        ]
    return filtered


def build_observation(
    *,
    opportunity: PairOpportunity,
    run_id: str,
    observed_at: str,
) -> PaperOpportunityObservation:
    return PaperOpportunityObservation(
        opportunity_id=f"opp-{run_id}-{opportunity.slug}",
        run_id=run_id,
        observed_at=observed_at,
        market_id=opportunity.slug,
        condition_id=opportunity.condition_id,
        slug=opportunity.slug,
        symbol=opportunity.symbol,
        duration_min=opportunity.duration_min,
        yes_token_id=opportunity.yes_token_id,
        no_token_id=opportunity.no_token_id,
        yes_quote_price=str(opportunity.yes_ask),
        no_quote_price=str(opportunity.no_ask),
        quote_age_seconds=0,
        assumptions=tuple(opportunity.assumptions),
    )


def compute_pair_size(
    *,
    observation: PaperOpportunityObservation,
    max_capital_per_market_usdc: Decimal,
) -> Decimal:
    if observation.paired_quote_cost <= _ZERO:
        return _ZERO
    return (max_capital_per_market_usdc / observation.paired_quote_cost).to_integral_value(
        rounding=ROUND_DOWN
    )


def format_elapsed_runtime(elapsed_seconds: int) -> str:
    total_seconds = max(0, int(elapsed_seconds))
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def _dashboard_header(
    settings: "CryptoPairRunnerSettings",
    market_count: int,
    started_at_str: str,
) -> str:
    symbols = sorted(set(settings.symbol_filters) if settings.symbol_filters else {"BTC", "ETH", "SOL"})
    cycle_ms = settings.cycle_interval_seconds
    threshold_pct: str = "?"
    try:
        threshold_pct = f"{settings.paper_config.momentum.momentum_threshold_pct * 100:.1f}%"
    except Exception:
        pass
    lines = [
        "=== Crypto Pair Bot — Paper Mode ===",
        f"Symbols: {', '.join(symbols)} | Feed: {settings.reference_feed_provider} | Cycle: {cycle_ms}s | Threshold: {threshold_pct}",
        f"Markets found: {market_count} | Started: {started_at_str}",
        "\u2500" * 60,
    ]
    return "\n".join(lines)


def _dashboard_market_line(
    *,
    ts: str,
    opportunity: "PairOpportunity",
    ref_price: Optional[float],
    price_change_pct: Optional[float],
    signal_direction: str,
    action: str,
) -> str:
    yes_str = f"${opportunity.yes_ask:.2f}" if opportunity.yes_ask is not None else "N/A"
    no_str = f"${opportunity.no_ask:.2f}" if opportunity.no_ask is not None else "N/A"
    pair_str = "N/A"
    if opportunity.yes_ask is not None and opportunity.no_ask is not None:
        pair_str = f"${opportunity.yes_ask + opportunity.no_ask:.2f}"
    ref_str = "N/A"
    if ref_price is not None:
        ref_str = f"${ref_price:,.0f}"
    chg_str = "N/A"
    if price_change_pct is not None:
        sign = "+" if price_change_pct >= 0 else ""
        chg_str = f"{sign}{price_change_pct * 100:.2f}%"
    label = opportunity.slug
    base = (
        f"[{ts}] {label} | YES {yes_str} NO {no_str} | Pair {pair_str} | "
        f"Ref {ref_str} | Chg {chg_str}"
    )
    if action == ACTION_ACCUMULATE and signal_direction != "NONE":
        fav_side = "YES" if signal_direction == "UP" else "NO"
        fav_price = opportunity.yes_ask if signal_direction == "UP" else opportunity.no_ask
        fav_str = f"${fav_price:.2f}" if fav_price is not None else "N/A"
        return f"{base} | >>> SIGNAL: {signal_direction} - BUY {fav_side} @ {fav_str} <<<"
    return f"{base} | Signal: {signal_direction if signal_direction else 'NONE'}"


def _dashboard_intent_line(*, ts: str, intent: Any) -> str:
    fav_leg = getattr(intent, "favorite_leg", None) or "?"
    hedge_leg = getattr(intent, "hedge_leg", None) or "?"
    if fav_leg == LEG_YES:
        fav_price = intent.intended_yes_price
        hedge_price = intent.intended_no_price
    else:
        fav_price = intent.intended_no_price
        hedge_price = intent.intended_yes_price
    pair_cost = float(fav_price) + float(hedge_price)
    fav_notional = float(fav_price) * float(intent.pair_size)
    hedge_notional = float(hedge_price) * float(intent.pair_size)
    return (
        f"[{ts}] *** INTENT: {intent.slug} | "
        f"FAV: {fav_leg} @ ${float(fav_price):.2f} (${fav_notional:.0f}) | "
        f"HEDGE: {hedge_leg} @ ${float(hedge_price):.2f} (${hedge_notional:.0f}) | "
        f"Pair cost: ${pair_cost:.2f} ***"
    )


def _fmt_duration(secs: int) -> str:
    m, s = divmod(max(0, secs), 60)
    if m:
        return f"{m}m {s}s"
    return f"{s}s"


def _dashboard_stats_line(
    *,
    cycle: int,
    observations: int,
    signals: int,
    intents: int,
    elapsed_seconds: int,
    duration_seconds: int,
) -> str:
    remaining = max(0, duration_seconds - elapsed_seconds)
    return (
        f"[STATS] Cycles: {cycle} | Observations: {observations} | "
        f"Signals: {signals} | Intents: {intents} | "
        f"Duration: {_fmt_duration(elapsed_seconds)} | Remaining: {_fmt_duration(remaining)}"
    )


class CryptoPairPaperRunner:
    """Paper-mode crypto-pair runtime shell."""

    def __init__(
        self,
        settings: CryptoPairRunnerSettings,
        *,
        gamma_client: Any = None,
        clob_client: Any = None,
        reference_feed: Optional[ReferenceFeed] = None,
        store: Optional[CryptoPairPositionStore] = None,
        execution_adapter: Optional[PaperExecutionAdapter] = None,
        sink: Optional[CryptoPairClickHouseEventWriter] = None,
        heartbeat_callback: Optional[Callable[[dict[str, Any]], None]] = None,
        now_fn=utc_now,
        sleep_fn=time.sleep,
        discovery_fn=discover_crypto_pair_markets,
        scan_fn=scan_opportunities,
        rank_fn=rank_opportunities,
        verbose: bool = False,
        clob_stream: Any = None,
    ) -> None:
        self.settings = settings
        self.gamma_client = gamma_client
        self.clob_client = clob_client
        self.clob_stream = clob_stream
        self.reference_feed = reference_feed or build_reference_feed(
            settings.reference_feed_provider
        )
        self._owns_reference_feed = reference_feed is None
        self.sink: CryptoPairClickHouseEventWriter = sink or DisabledCryptoPairClickHouseSink()
        self._feed_state_transitions: list[dict] = []
        self._streamed_transition_ids: set[str] = set()
        self.store = store or CryptoPairPositionStore(
            mode="paper",
            artifact_base_dir=settings.artifact_base_dir,
            sink=self.sink,
        )
        self.execution_adapter = execution_adapter or DirectionalPaperExecutionAdapter(
            max_hedge_price=settings.paper_config.momentum.max_hedge_price
        )
        self.heartbeat_callback = heartbeat_callback
        self.now_fn = now_fn
        self.sleep_fn = sleep_fn
        self.discovery_fn = discovery_fn
        self.scan_fn = scan_fn
        self.rank_fn = rank_fn
        self.kill_switch = FileBasedKillSwitch(settings.kill_switch_path)
        self._feed_states: dict[str, str] = {}
        # Momentum state: rolling price buffers per symbol, one-entry-per-bracket cooldown
        momentum_window = settings.paper_config.momentum.momentum_window_seconds
        self._price_history: dict[str, deque] = {}
        self._price_history_maxlen: int = max(2, momentum_window)
        self._entered_brackets: set[str] = set()
        self._next_heartbeat_elapsed_seconds = (
            settings.heartbeat_interval_seconds
            if settings.heartbeat_interval_seconds > 0
            else None
        )
        # Dashboard state
        self._verbose = verbose
        self._dashboard_signal_count: int = 0
        self._dashboard_last_stats_at: int = 0
        self._dashboard_markets_found: int = 0

    def run(self) -> dict[str, Any]:
        self.store.write_config_snapshot(
            {
                "runner": self.settings.to_dict(),
                "mode": "paper",
                "safety": {
                    "paper_mode_default": True,
                    "kill_switch_checked_each_cycle": True,
                    "freeze_on_binance_disconnect_or_stale": True,
                    "post_only_limit_only_only": True,
                },
            }
        )
        self.store.record_runtime_event(
            "runner_started",
            mode="paper",
            artifact_dir=str(self.store.run_dir),
            kill_switch_path=str(self.settings.kill_switch_path),
        )

        if self._owns_reference_feed:
            self.reference_feed.connect()
            self.store.record_runtime_event("reference_feed_connect_called")

        if self.clob_stream is not None:
            self.clob_stream.start()
            self.store.record_runtime_event("clob_stream_start_called")
            # Bootstrap token subscriptions on first cycle (deferred until markets are known)
            self._clob_stream_bootstrapped = False

        # Print startup dashboard header
        started_at_str = iso_utc(self.store.started_at)[:19].replace("T", " ")
        print(
            _dashboard_header(self.settings, market_count=0, started_at_str=started_at_str),
            flush=True,
        )

        stopped_reason = _STOPPED_REASON_COMPLETED
        completed_cycles = 0
        total_cycles = cycle_count_from_settings(self.settings)

        try:
            for cycle_index in range(total_cycles):
                cycle_started_at = iso_utc(self.now_fn())
                completed_cycles = cycle_index + 1
                kill_switch_active = self.kill_switch.is_tripped()
                self.store.record_runtime_event(
                    "kill_switch_checked",
                    at=cycle_started_at,
                    cycle=completed_cycles,
                    active=kill_switch_active,
                    path=str(self.settings.kill_switch_path),
                )
                if kill_switch_active:
                    stopped_reason = "kill_switch"
                    self.store.record_runtime_event(
                        "kill_switch_tripped",
                        at=cycle_started_at,
                        cycle=completed_cycles,
                    )
                    break

                pair_markets = self.discovery_fn(gamma_client=self.gamma_client)
                self._dashboard_markets_found = len(pair_markets)

                # Subscribe all token IDs on the first cycle once markets are known
                if self.clob_stream is not None and not getattr(self, "_clob_stream_bootstrapped", True):
                    for m in pair_markets:
                        self.clob_stream.subscribe(m.yes_token_id)
                        self.clob_stream.subscribe(m.no_token_id)
                    self._clob_stream_bootstrapped = True

                opportunities = self.scan_fn(pair_markets, clob_client=self.clob_client, stream=self.clob_stream)
                ranked = self.rank_fn(apply_market_filters(opportunities, self.settings))

                self.store.record_runtime_event(
                    "cycle_started",
                    at=cycle_started_at,
                    cycle=completed_cycles,
                    markets_discovered=len(pair_markets),
                    markets_considered=len(ranked),
                )

                self._dashboard_cycle_market_count = 0
                for opportunity in ranked:
                    self._process_opportunity(opportunity, cycle=completed_cycles)

                self.store.record_runtime_event(
                    "cycle_completed",
                    at=iso_utc(self.now_fn()),
                    cycle=completed_cycles,
                    open_pairs=self.store.open_pair_count(),
                    open_unpaired=self.store.has_open_unpaired_exposure(),
                    drawdown_usdc=str(self.store.estimated_daily_drawdown_usdc()),
                )
                self._emit_heartbeat_if_due(cycle=completed_cycles)

                # Stats line every 10 seconds
                _now_elapsed = int((self.now_fn() - self.store.started_at).total_seconds())
                if _now_elapsed - self._dashboard_last_stats_at >= 10:
                    self._dashboard_last_stats_at = _now_elapsed
                    print(
                        _dashboard_stats_line(
                            cycle=completed_cycles,
                            observations=len(self.store.observations),
                            signals=self._dashboard_signal_count,
                            intents=len(self.store.intents),
                            elapsed_seconds=_now_elapsed,
                            duration_seconds=self.settings.duration_seconds,
                        ),
                        flush=True,
                    )

                if cycle_index < total_cycles - 1:
                    self.sleep_fn(self.settings.cycle_interval_seconds)

                # Wall-clock guard: stop if elapsed >= duration_seconds regardless of cycle count
                _elapsed = (self.now_fn() - self.store.started_at).total_seconds()
                if self.settings.duration_seconds > 0 and _elapsed >= self.settings.duration_seconds:
                    break
        except KeyboardInterrupt:
            stopped_reason = _STOPPED_REASON_OPERATOR_INTERRUPT
            self.store.record_runtime_event(
                "operator_interrupt",
                at=iso_utc(self.now_fn()),
                cycle=completed_cycles,
            )
        finally:
            if self._owns_reference_feed:
                self.reference_feed.disconnect()
                self.store.record_runtime_event("reference_feed_disconnect_called")
            if self.clob_stream is not None:
                self.clob_stream.stop()
                self.store.record_runtime_event("clob_stream_stopped")

        rollups = build_market_rollups(
            self.store.observations,
            self.store.intents,
            self.store.latest_exposures(),
            self.store.settlements,
        )
        self.store.record_market_rollups(rollups)
        run_summary = build_run_summary(
            run_id=self.store.run_id,
            generated_at=iso_utc(self.now_fn()),
            market_rollups=rollups,
        )
        self.store.record_run_summary(run_summary)

        # Build SafetyStateTransitionEvent objects from collected transitions
        transition_events = [
            SafetyStateTransitionEvent.from_feed_state_change(
                transition_id=t["transition_id"],
                event_ts=t["event_ts"],
                run_id=self.store.run_id,
                mode="paper",
                symbol=t["symbol"],
                from_state=t["from_state"],
                to_state=t["to_state"],
                market_id=t["market_id"],
                condition_id=t["condition_id"],
                slug=t["slug"],
                duration_min=t["duration_min"],
                cycle=t["cycle"],
            )
            for t in self._feed_state_transitions
        ]

        if self.settings.sink_flush_mode == "streaming":
            # In streaming mode: observations, intents, fills, exposures were already
            # emitted incrementally. Only emit the run summary and any transitions that
            # were not yet streamed (avoids duplicates).
            unstreamed_transitions = [
                evt for evt in transition_events
                if evt.transition_id not in self._streamed_transition_ids
            ]
            run_summary_event_obj = None
            from .event_models import RunSummaryEvent
            run_summary_event_obj = RunSummaryEvent.from_summary(
                run_summary, mode="paper", stopped_reason=stopped_reason
            )
            finalization_events = unstreamed_transitions + [run_summary_event_obj]
            write_result = self.sink.write_events(finalization_events)
        else:
            # Batch mode: emit all events at once (default behavior, unchanged from quick-020)
            events = build_events_from_paper_records(
                observations=self.store.observations,
                intents=self.store.intents,
                fills=self.store.fills,
                exposures=self.store.latest_exposures(),
                settlements=self.store.settlements,
                run_summary=run_summary,
                mode="paper",
                stopped_reason=stopped_reason,
            )
            events.extend(transition_events)
            write_result = self.sink.write_events(events)
        self.store.record_runtime_event(
            "sink_write_result",
            enabled=write_result.enabled,
            attempted_events=write_result.attempted_events,
            written_rows=write_result.written_rows,
            skipped_reason=write_result.skipped_reason,
            error=write_result.error,
        )

        manifest = self.store.finalize(
            stopped_reason=stopped_reason,
            completed_at=self.now_fn(),
            extra_manifest_fields={
                "runner_result": PaperRunnerResult(
                    run_id=self.store.run_id,
                    mode="paper",
                    artifact_dir=str(self.store.run_dir),
                    stopped_reason=stopped_reason,
                    cycles_completed=completed_cycles,
                    manifest_path=str(self.store.paths.manifest_path),
                ).to_dict(),
                "sink_write_result": write_result.to_dict(),
            },
        )
        return manifest

    def _emit_heartbeat_if_due(self, *, cycle: int) -> None:
        interval_seconds = self.settings.heartbeat_interval_seconds
        if interval_seconds <= 0 or self._next_heartbeat_elapsed_seconds is None:
            return

        current_time = self.now_fn()
        elapsed_seconds = max(
            0,
            int((current_time - self.store.started_at).total_seconds()),
        )
        if elapsed_seconds < self._next_heartbeat_elapsed_seconds:
            return

        heartbeat = self._build_heartbeat(
            recorded_at=iso_utc(current_time),
            cycle=cycle,
            elapsed_seconds=elapsed_seconds,
        )
        heartbeat_payload = heartbeat.to_dict()
        recorded_at = heartbeat_payload.pop("recorded_at")
        self.store.record_runtime_event(
            "runner_heartbeat",
            at=recorded_at,
            **heartbeat_payload,
        )
        if self.heartbeat_callback is not None:
            self.heartbeat_callback(
                {
                    "recorded_at": recorded_at,
                    **heartbeat_payload,
                }
            )

        while elapsed_seconds >= self._next_heartbeat_elapsed_seconds:
            self._next_heartbeat_elapsed_seconds += interval_seconds

    def _build_heartbeat(
        self,
        *,
        recorded_at: str,
        cycle: int,
        elapsed_seconds: int,
    ) -> PaperRunnerHeartbeat:
        exposures = self.store.latest_exposures()
        completed_pairs = sum(1 for exposure in exposures if exposure.paired_size > _ZERO)
        partial_exposure_count = sum(
            1 for exposure in exposures if exposure.unpaired_size > _ZERO
        )
        latest_feed_states = dict(sorted(self._feed_states.items()))
        stale_symbols = sorted(
            symbol
            for symbol, state in latest_feed_states.items()
            if state == "stale"
        )
        degraded_symbols = sorted(
            symbol
            for symbol, state in latest_feed_states.items()
            if state != "connected_fresh"
        )
        return PaperRunnerHeartbeat(
            recorded_at=recorded_at,
            cycle=cycle,
            elapsed_seconds=elapsed_seconds,
            elapsed_runtime=format_elapsed_runtime(elapsed_seconds),
            opportunities_observed=len(self.store.observations),
            intents_generated=len(self.store.intents),
            completed_pairs=completed_pairs,
            partial_exposure_count=partial_exposure_count,
            open_pairs=self.store.open_pair_count(),
            latest_feed_states=latest_feed_states,
            stale_symbols=stale_symbols,
            degraded_symbols=degraded_symbols,
        )

    def _process_opportunity(self, opportunity: PairOpportunity, *, cycle: int) -> None:
        event_at = iso_utc(self.now_fn())
        if opportunity.yes_ask is None or opportunity.no_ask is None:
            self.store.record_runtime_event(
                "opportunity_skipped_missing_quotes",
                at=event_at,
                cycle=cycle,
                market_id=opportunity.slug,
                book_status=opportunity.book_status,
            )
            return

        observation = build_observation(
            opportunity=opportunity,
            run_id=self.store.run_id,
            observed_at=event_at,
        )

        snapshot = self.reference_feed.get_snapshot(opportunity.symbol)

        # Update rolling price history for momentum signal computation
        symbol_key = opportunity.symbol.upper()
        if snapshot is not None and snapshot.price is not None and snapshot.is_usable:
            if symbol_key not in self._price_history:
                self._price_history[symbol_key] = deque(maxlen=self._price_history_maxlen)
            self._price_history[symbol_key].append(snapshot.price)

        current_feed_state = classify_feed_state(snapshot)
        previous_feed_state = self._feed_states.get(opportunity.symbol)
        if previous_feed_state != current_feed_state:
            self.store.record_runtime_event(
                "feed_state_changed",
                at=event_at,
                cycle=cycle,
                symbol=opportunity.symbol,
                from_state=previous_feed_state,
                to_state=current_feed_state,
            )
            self._feed_states[opportunity.symbol] = current_feed_state
            # Only emit a sink transition event for genuine state changes
            # (skip the first-observation case where previous_feed_state is None)
            if previous_feed_state is not None:
                _transition_id = f"fst-{self.store.run_id}-{opportunity.symbol}-{event_at}"
                self._feed_state_transitions.append({
                    "transition_id": _transition_id,
                    "event_ts": event_at,
                    "symbol": opportunity.symbol,
                    "from_state": previous_feed_state,
                    "to_state": current_feed_state,
                    "market_id": opportunity.slug,
                    "condition_id": opportunity.condition_id,
                    "slug": opportunity.slug,
                    "duration_min": opportunity.duration_min,
                    "cycle": cycle,
                })
                if self.settings.sink_flush_mode == "streaming":
                    _trans_evt = SafetyStateTransitionEvent.from_feed_state_change(
                        transition_id=_transition_id,
                        event_ts=event_at,
                        run_id=self.store.run_id,
                        mode="paper",
                        symbol=opportunity.symbol,
                        from_state=previous_feed_state,
                        to_state=current_feed_state,
                        market_id=opportunity.slug,
                        condition_id=opportunity.condition_id,
                        slug=opportunity.slug,
                        duration_min=opportunity.duration_min,
                        cycle=cycle,
                    )
                    _trans_result = self.sink.write_event(_trans_evt)
                    if not _trans_result.error:
                        self._streamed_transition_ids.add(_transition_id)
                    else:
                        import logging as _logging
                        _logging.getLogger(__name__).warning(
                            "sink stream write failed (transition): %s", _trans_result.error
                        )

        yes_size, no_size = self.store.market_leg_sizes(observation.market_id)
        symbol_key = opportunity.symbol.upper()
        state = PairMarketState(
            symbol=opportunity.symbol,
            duration_min=opportunity.duration_min,
            market_id=observation.market_id,
            yes_quote=BestQuote(
                leg=LEG_YES,
                token_id=opportunity.yes_token_id,
                ask_price=Decimal(str(opportunity.yes_ask)),
            ),
            no_quote=BestQuote(
                leg=LEG_NO,
                token_id=opportunity.no_token_id,
                ask_price=Decimal(str(opportunity.no_ask)),
            ),
            yes_accumulated_size=yes_size,
            no_accumulated_size=no_size,
            fair_value_yes=None,
            fair_value_no=None,
            feed_snapshot=snapshot,
            price_history=tuple(self._price_history.get(symbol_key, deque())),
            cooldown_brackets=frozenset(self._entered_brackets),
        )
        accumulation = evaluate_directional_entry(state, self.settings.paper_config)

        # Dashboard output — capture rationale before enrichment/early returns
        _rationale = accumulation.rationale
        _signal_dir = _rationale.get("signal_direction", "NONE") or "NONE"
        _ref_price = _rationale.get("reference_price")
        _price_chg = _rationale.get("price_change_pct")
        _is_signal = accumulation.action == ACTION_ACCUMULATE and _signal_dir != "NONE"
        if _is_signal:
            self._dashboard_signal_count += 1
        _ts = iso_utc(self.now_fn())[11:19]  # HH:MM:SS portion
        # Limit verbose output to 8 unique markets per cycle
        _show_verbose = self._verbose and getattr(self, "_dashboard_cycle_market_count", 0) < 8
        if _show_verbose:
            self._dashboard_cycle_market_count = getattr(self, "_dashboard_cycle_market_count", 0) + 1
        if _show_verbose or _is_signal:
            print(
                _dashboard_market_line(
                    ts=_ts,
                    opportunity=opportunity,
                    ref_price=_ref_price,
                    price_change_pct=_price_chg,
                    signal_direction=_signal_dir,
                    action=accumulation.action,
                ),
                flush=True,
            )

        # Enrich observation with momentum signal fields from rationale
        rationale = accumulation.rationale
        if hasattr(observation, "signal_direction"):
            observation = dataclass_replace(
                observation,
                reference_price=rationale.get("reference_price"),
                price_change_pct=rationale.get("price_change_pct"),
                signal_direction=rationale.get("signal_direction", "NONE"),
                favorite_side=rationale.get("favorite_leg"),
                hedge_side=rationale.get("hedge_leg"),
            )

        self.store.record_observation(observation)
        if self.settings.sink_flush_mode == "streaming":
            _obs_evt = OpportunityObservedEvent.from_observation(observation, mode="paper")
            _obs_result = self.sink.write_event(_obs_evt)
            if _obs_result.error:
                import logging as _logging
                _logging.getLogger(__name__).warning(
                    "sink stream write failed (observation): %s", _obs_result.error
                )

        self.store.record_runtime_event(
            "accumulation_evaluated",
            at=event_at,
            cycle=cycle,
            market_id=observation.market_id,
            action=accumulation.action,
            selected_legs=list(accumulation.legs),
            rationale=accumulation.rationale,
        )

        if accumulation.action == ACTION_FREEZE:
            self.store.record_runtime_event(
                "paper_new_intents_frozen",
                at=event_at,
                cycle=cycle,
                market_id=observation.market_id,
                freeze_reason=accumulation.rationale.get("freeze_reason"),
            )
            return
        if accumulation.action != ACTION_ACCUMULATE:
            return

        if self.store.open_pair_count() >= self.settings.max_open_pairs:
            self.store.record_runtime_event(
                "order_intent_blocked",
                at=event_at,
                cycle=cycle,
                market_id=observation.market_id,
                block_reason="open_pairs_cap_reached",
            )
            return

        if (
            self.store.estimated_daily_drawdown_usdc()
            >= self.settings.daily_loss_cap_usdc
        ):
            self.store.record_runtime_event(
                "order_intent_blocked",
                at=event_at,
                cycle=cycle,
                market_id=observation.market_id,
                block_reason="daily_loss_cap_reached",
            )
            return

        if (
            self.store.cumulative_committed_notional_usdc()
            >= self.settings.max_capital_per_window_usdc
        ):
            self.store.record_runtime_event(
                "order_intent_blocked",
                at=event_at,
                cycle=cycle,
                market_id=observation.market_id,
                block_reason="capital_window_exceeded",
            )
            return

        pair_size = compute_pair_size(
            observation=observation,
            max_capital_per_market_usdc=self.settings.paper_config.max_capital_per_market_usdc,
        )
        if pair_size <= _ZERO:
            self.store.record_runtime_event(
                "order_intent_blocked",
                at=event_at,
                cycle=cycle,
                market_id=observation.market_id,
                block_reason="pair_size_zero",
            )
            return

        block_reason = get_order_intent_block_reason(
            observation,
            self.settings.paper_config,
            pair_size=pair_size,
            current_market_open_notional_usdc=self.store.current_market_open_notional_usdc(
                observation.market_id
            ),
            current_open_paired_notional_usdc=self.store.current_open_paired_notional_usdc(),
            has_open_unpaired_exposure=self.store.has_open_unpaired_exposure(),
        )
        if block_reason is not None:
            self.store.record_runtime_event(
                "order_intent_blocked",
                at=event_at,
                cycle=cycle,
                market_id=observation.market_id,
                block_reason=block_reason,
            )
            return

        intent = generate_order_intent(
            observation,
            self.settings.paper_config,
            intent_id=f"intent-{self.store.run_id}-{observation.market_id}",
            created_at=event_at,
            pair_size=pair_size,
            current_market_open_notional_usdc=self.store.current_market_open_notional_usdc(
                observation.market_id
            ),
            current_open_paired_notional_usdc=self.store.current_open_paired_notional_usdc(),
            has_open_unpaired_exposure=self.store.has_open_unpaired_exposure(),
        )
        if intent is None:
            self.store.record_runtime_event(
                "order_intent_blocked",
                at=event_at,
                cycle=cycle,
                market_id=observation.market_id,
                block_reason="generate_order_intent_returned_none",
            )
            return

        # Record bracket entry to enforce one-entry-per-bracket cooldown
        self._entered_brackets.add(state.market_id)

        self.store.record_intent(intent)
        # Intent line always prints (intents are always important)
        print(
            _dashboard_intent_line(ts=_ts, intent=intent),
            flush=True,
        )
        if self.settings.sink_flush_mode == "streaming":
            _intent_evt = IntentGeneratedEvent.from_intent(intent, mode="paper")
            _intent_result = self.sink.write_event(_intent_evt)
            if _intent_result.error:
                import logging as _logging
                _logging.getLogger(__name__).warning(
                    "sink stream write failed (intent): %s", _intent_result.error
                )
        self.store.record_runtime_event(
            "order_intent_created",
            at=event_at,
            cycle=cycle,
            market_id=observation.market_id,
            selected_legs=list(accumulation.legs),
            pair_size=str(pair_size),
        )

        fills = self.execution_adapter.simulate_fills(
            intent=intent,
            selected_legs=accumulation.legs,
            filled_at=event_at,
        )
        for fill in fills:
            self.store.record_fill(fill)
            if self.settings.sink_flush_mode == "streaming":
                _fill_evt = SimulatedFillRecordedEvent.from_fill(fill, mode="paper")
                _fill_result = self.sink.write_event(_fill_evt)
                if _fill_result.error:
                    import logging as _logging
                    _logging.getLogger(__name__).warning(
                        "sink stream write failed (fill): %s", _fill_result.error
                    )

        exposure = compute_partial_leg_exposure(intent, fills, as_of=event_at)
        self.store.record_exposure(exposure)
        if self.settings.sink_flush_mode == "streaming":
            _exp_evt = PartialExposureUpdatedEvent.from_exposure(exposure, mode="paper")
            _exp_result = self.sink.write_event(_exp_evt)
            if _exp_result.error:
                import logging as _logging
                _logging.getLogger(__name__).warning(
                    "sink stream write failed (exposure): %s", _exp_result.error
                )
        self.store.record_runtime_event(
            "exposure_recorded",
            at=event_at,
            cycle=cycle,
            market_id=observation.market_id,
            exposure_status=exposure.exposure_status,
            paired_size=str(exposure.paired_size),
            unpaired_size=str(exposure.unpaired_size),
        )
