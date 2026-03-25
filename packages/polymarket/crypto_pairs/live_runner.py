"""Live-mode scaffold for crypto-pair runner v0."""

from __future__ import annotations

import time
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any, Optional

from packages.polymarket.simtrader.execution.kill_switch import FileBasedKillSwitch

from .accumulation_engine import (
    ACTION_ACCUMULATE,
    ACTION_FREEZE,
    BestQuote,
    PairMarketState,
    evaluate_accumulation,
)
from .live_execution import CryptoPairLiveExecutionAdapter, LiveOrderRequest
from .market_discovery import discover_crypto_pair_markets
from .opportunity_scan import rank_opportunities, scan_opportunities
from .paper_ledger import generate_order_intent, get_order_intent_block_reason
from .paper_runner import (
    CryptoPairRunnerSettings,
    apply_market_filters,
    build_observation,
    classify_feed_state,
    compute_pair_size,
    cycle_count_from_settings,
)
from .position_store import CryptoPairPositionStore, iso_utc, utc_now
from .reference_feed import BinanceFeed


DEFAULT_LIVE_ARTIFACTS_DIR = Path("artifacts/crypto_pairs/live_runs")

_ZERO = Decimal("0")


@dataclass(frozen=True)
class LiveRunnerResult:
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


class CryptoPairLiveRunner:
    """Live scaffold with explicit safety gates and no production activation requirement."""

    def __init__(
        self,
        settings: CryptoPairRunnerSettings,
        *,
        execution_adapter: Optional[CryptoPairLiveExecutionAdapter] = None,
        gamma_client: Any = None,
        clob_client: Any = None,
        reference_feed=None,
        store: Optional[CryptoPairPositionStore] = None,
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
        self.store = store or CryptoPairPositionStore(
            mode="live",
            artifact_base_dir=self.settings.artifact_base_dir,
        )
        self.execution_adapter = execution_adapter or CryptoPairLiveExecutionAdapter(
            kill_switch=FileBasedKillSwitch(self.settings.kill_switch_path),
            live_enabled=True,
        )
        self.kill_switch = FileBasedKillSwitch(self.settings.kill_switch_path)
        self.now_fn = now_fn
        self.sleep_fn = sleep_fn
        self.discovery_fn = discovery_fn
        self.scan_fn = scan_fn
        self.rank_fn = rank_fn
        self._feed_states: dict[str, str] = {}
        self._resume_blocked = False

    def run(self) -> dict[str, Any]:
        self.store.write_config_snapshot(
            {
                "runner": self.settings.to_dict(),
                "mode": "live",
                "safety": {
                    "live_flag_required": True,
                    "confirm_string_required": True,
                    "kill_switch_checked_each_cycle": True,
                    "post_only_only": True,
                    "limit_only_only": True,
                    "market_orders_not_supported": True,
                    "disconnect_cancels_working_orders": True,
                    "reconnect_required_before_resume": True,
                },
            }
        )
        self.store.record_runtime_event(
            "runner_started",
            mode="live",
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
                    resume_blocked=self._resume_blocked,
                )

                for opportunity in ranked:
                    self._process_opportunity(opportunity, cycle=completed_cycles)

                self.store.record_runtime_event(
                    "cycle_completed",
                    at=iso_utc(self.now_fn()),
                    cycle=completed_cycles,
                    working_orders=len(self.execution_adapter.working_orders()),
                    resume_blocked=self._resume_blocked,
                )

                if cycle_index < total_cycles - 1:
                    self.sleep_fn(self.settings.cycle_interval_seconds)
        finally:
            if self._owns_reference_feed:
                self.reference_feed.disconnect()
                self.store.record_runtime_event("reference_feed_disconnect_called")

        manifest = self.store.finalize(
            stopped_reason=stopped_reason,
            completed_at=self.now_fn(),
            extra_manifest_fields={
                "runner_result": LiveRunnerResult(
                    run_id=self.store.run_id,
                    mode="live",
                    artifact_dir=str(self.store.run_dir),
                    stopped_reason=stopped_reason,
                    cycles_completed=completed_cycles,
                    manifest_path=str(self.store.paths.manifest_path),
                ).to_dict(),
            },
        )
        return manifest

    def _process_opportunity(self, opportunity, *, cycle: int) -> None:
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

        if current_feed_state != "connected_fresh":
            self._handle_disconnect_state(
                symbol=opportunity.symbol,
                cycle=cycle,
                at=event_at,
                state=current_feed_state,
            )
        elif self._resume_blocked:
            self._resume_blocked = False
            self.store.record_runtime_event(
                "live_resume_allowed",
                at=event_at,
                cycle=cycle,
                symbol=opportunity.symbol,
            )

        yes_size, no_size = self.store.market_leg_sizes(observation.market_id)
        state = PairMarketState(
            symbol=opportunity.symbol,
            duration_min=opportunity.duration_min,
            market_id=observation.market_id,
            yes_quote=BestQuote(
                leg="YES",
                token_id=opportunity.yes_token_id,
                ask_price=Decimal(str(opportunity.yes_ask)),
            ),
            no_quote=BestQuote(
                leg="NO",
                token_id=opportunity.no_token_id,
                ask_price=Decimal(str(opportunity.no_ask)),
            ),
            yes_accumulated_size=yes_size,
            no_accumulated_size=no_size,
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

        if self._resume_blocked or accumulation.action == ACTION_FREEZE:
            return
        if accumulation.action != ACTION_ACCUMULATE:
            return

        if self.store.open_pair_count() >= self.settings.max_open_pairs:
            self.store.record_runtime_event(
                "live_order_blocked",
                at=event_at,
                cycle=cycle,
                market_id=observation.market_id,
                reason="open_pairs_cap_reached",
            )
            return

        if (
            self.store.estimated_daily_drawdown_usdc()
            >= self.settings.daily_loss_cap_usdc
        ):
            self.store.record_runtime_event(
                "live_order_blocked",
                at=event_at,
                cycle=cycle,
                market_id=observation.market_id,
                reason="daily_loss_cap_reached",
            )
            return

        pair_size = compute_pair_size(
            observation=observation,
            max_capital_per_market_usdc=self.settings.paper_config.max_capital_per_market_usdc,
        )
        if pair_size <= _ZERO:
            self.store.record_runtime_event(
                "live_order_blocked",
                at=event_at,
                cycle=cycle,
                market_id=observation.market_id,
                reason="pair_size_zero",
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
                "live_order_blocked",
                at=event_at,
                cycle=cycle,
                market_id=observation.market_id,
                reason=block_reason,
            )
            return

        intent = generate_order_intent(
            observation,
            self.settings.paper_config,
            intent_id=f"intent-{self.store.run_id}-{observation.market_id}-{cycle}",
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
                "live_order_blocked",
                at=event_at,
                cycle=cycle,
                market_id=observation.market_id,
                reason="generate_order_intent_returned_none",
            )
            return

        self.store.record_intent(intent)
        for leg in accumulation.legs:
            if leg == "YES":
                token_id = intent.yes_token_id
                price = intent.intended_yes_price
            else:
                token_id = intent.no_token_id
                price = intent.intended_no_price
            result = self.execution_adapter.place_order(
                LiveOrderRequest(
                    market_id=intent.market_id,
                    token_id=token_id,
                    side="BUY",
                    price=price,
                    size=intent.pair_size,
                    order_type="limit",
                    post_only=True,
                    meta={
                        "intent_id": intent.intent_id,
                        "cycle": cycle,
                        "leg": leg,
                    },
                )
            )
            self.store.record_runtime_event(
                "live_order_attempted",
                at=event_at,
                cycle=cycle,
                market_id=intent.market_id,
                leg=leg,
                accepted=result.accepted,
                submitted=result.submitted,
                order_id=result.order_id,
                reason=result.reason,
            )

    def _handle_disconnect_state(
        self,
        *,
        symbol: str,
        cycle: int,
        at: str,
        state: str,
    ) -> None:
        self._resume_blocked = True
        cancel_results = self.execution_adapter.cancel_all_working_orders()
        self.store.record_runtime_event(
            "live_disconnect_guard_armed",
            at=at,
            cycle=cycle,
            symbol=symbol,
            state=state,
            cancelled_orders=len(cancel_results),
        )
        for result in cancel_results:
            self.store.record_runtime_event(
                "live_working_order_cancelled",
                at=at,
                cycle=cycle,
                symbol=symbol,
                order_id=result.order_id,
                submitted=result.submitted,
                reason=result.reason,
            )
