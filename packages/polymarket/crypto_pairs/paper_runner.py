"""Paper-mode runtime shell for the crypto-pair runner."""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from decimal import Decimal, ROUND_DOWN
from pathlib import Path
from typing import Any, Optional, Protocol

from packages.polymarket.simtrader.execution.kill_switch import FileBasedKillSwitch

from .accumulation_engine import (
    ACTION_ACCUMULATE,
    ACTION_FREEZE,
    BestQuote,
    PairMarketState,
    evaluate_accumulation,
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
    SafetyStateTransitionEvent,
    build_events_from_paper_records,
)
from .position_store import CryptoPairPositionStore, iso_utc, utc_now
from .reference_feed import BinanceFeed, FeedConnectionState, ReferencePriceSnapshot


DEFAULT_PAPER_ARTIFACTS_DIR = Path("artifacts/crypto_pairs/paper_runs")
DEFAULT_KILL_SWITCH_PATH = Path("artifacts/crypto_pairs/kill_switch.txt")

_ZERO = Decimal("0")
_ONE_BPS = Decimal("10000")
_OPERATOR_MAX_CAPITAL_PER_MARKET_USDC = Decimal("10")
_OPERATOR_MAX_OPEN_PAIRS = 5
_OPERATOR_DAILY_LOSS_CAP_USDC = Decimal("15")
_OPERATOR_MAX_PAIR_COST = Decimal("0.97")
_OPERATOR_MIN_PROFIT_THRESHOLD_USDC = Decimal("0.03")


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
            "target_pair_cost_threshold": str(_OPERATOR_MAX_PAIR_COST),
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
    cycle_interval_seconds: int = 5
    max_open_pairs: int = _OPERATOR_MAX_OPEN_PAIRS
    daily_loss_cap_usdc: Decimal = _OPERATOR_DAILY_LOSS_CAP_USDC
    min_profit_threshold_usdc: Decimal = _OPERATOR_MIN_PROFIT_THRESHOLD_USDC
    symbol_filters: tuple[str, ...] = ()
    duration_filters: tuple[int, ...] = ()
    cycle_limit: Optional[int] = None

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

        if self.duration_seconds < 0:
            raise ValueError("duration_seconds must be >= 0")
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
        if self.paper_config.target_pair_cost_threshold > _OPERATOR_MAX_PAIR_COST:
            raise ValueError(
                f"v0 target_pair_cost_threshold cannot exceed {_OPERATOR_MAX_PAIR_COST}"
            )
        if (
            Decimal("1") - self.paper_config.target_pair_cost_threshold
            < self.min_profit_threshold_usdc
        ):
            raise ValueError(
                "paper_config.target_pair_cost_threshold violates the minimum profit threshold"
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
            min_profit_threshold_usdc=self.min_profit_threshold_usdc,
            symbol_filters=self.symbol_filters,
            duration_filters=self.duration_filters,
            cycle_limit=self.cycle_limit,
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
            "min_profit_threshold_usdc": str(self.min_profit_threshold_usdc),
            "symbol_filters": list(self.symbol_filters),
            "duration_filters": list(self.duration_filters),
            "cycle_limit": self.cycle_limit,
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
                "target_pair_cost_threshold",
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
        cycle_interval_seconds=int(payload.get("cycle_interval_seconds", 5)),
        max_open_pairs=int(payload.get("max_open_pairs", _OPERATOR_MAX_OPEN_PAIRS)),
        daily_loss_cap_usdc=payload.get(
            "daily_loss_cap_usdc",
            _OPERATOR_DAILY_LOSS_CAP_USDC,
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
        cycle_limit=cycle_limit if cycle_limit is not None else payload.get("cycle_limit"),
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
    target_pair_cost_threshold: Decimal,
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
        target_pair_cost_threshold=str(target_pair_cost_threshold),
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
        now_fn=utc_now,
        sleep_fn=time.sleep,
        discovery_fn=discover_crypto_pair_markets,
        scan_fn=scan_opportunities,
        rank_fn=rank_opportunities,
    ) -> None:
        self.settings = settings
        self.gamma_client = gamma_client
        self.clob_client = clob_client
        self.reference_feed = reference_feed or BinanceFeed()
        self._owns_reference_feed = reference_feed is None
        self.sink: CryptoPairClickHouseEventWriter = sink or DisabledCryptoPairClickHouseSink()
        self._feed_state_transitions: list[dict] = []
        self.store = store or CryptoPairPositionStore(
            mode="paper",
            artifact_base_dir=settings.artifact_base_dir,
            sink=self.sink,
        )
        self.execution_adapter = execution_adapter or DeterministicPaperExecutionAdapter()
        self.now_fn = now_fn
        self.sleep_fn = sleep_fn
        self.discovery_fn = discovery_fn
        self.scan_fn = scan_fn
        self.rank_fn = rank_fn
        self.kill_switch = FileBasedKillSwitch(settings.kill_switch_path)
        self._feed_states: dict[str, str] = {}

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

        stopped_reason = "completed"
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
                opportunities = self.scan_fn(pair_markets, clob_client=self.clob_client)
                ranked = self.rank_fn(apply_market_filters(opportunities, self.settings))

                self.store.record_runtime_event(
                    "cycle_started",
                    at=cycle_started_at,
                    cycle=completed_cycles,
                    markets_discovered=len(pair_markets),
                    markets_considered=len(ranked),
                )

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

                if cycle_index < total_cycles - 1:
                    self.sleep_fn(self.settings.cycle_interval_seconds)
        finally:
            if self._owns_reference_feed:
                self.reference_feed.disconnect()
                self.store.record_runtime_event("reference_feed_disconnect_called")

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
            target_pair_cost_threshold=self.settings.paper_config.target_pair_cost_threshold,
        )
        self.store.record_observation(observation)

        snapshot = self.reference_feed.get_snapshot(opportunity.symbol)
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
                self._feed_state_transitions.append({
                    "transition_id": f"fst-{self.store.run_id}-{opportunity.symbol}-{event_at}",
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

        yes_size, no_size = self.store.market_leg_sizes(observation.market_id)
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
        )
        accumulation = evaluate_accumulation(state, self.settings.paper_config)
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

        self.store.record_intent(intent)
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

        exposure = compute_partial_leg_exposure(intent, fills, as_of=event_at)
        self.store.record_exposure(exposure)
        self.store.record_runtime_event(
            "exposure_recorded",
            at=event_at,
            cycle=cycle,
            market_id=observation.market_id,
            exposure_status=exposure.exposure_status,
            paired_size=str(exposure.paired_size),
            unpaired_size=str(exposure.unpaired_size),
        )
