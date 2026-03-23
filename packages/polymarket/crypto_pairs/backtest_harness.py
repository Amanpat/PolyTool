"""Deterministic backtest/history harness for the Phase 1A crypto-pair bot.

Replays a list of BacktestObservation records through the existing fair-value
and accumulation logic.  Produces a BacktestResult with per-category skip
counts, intent counts, and cost metrics.

Design constraints:
- Pure function: no network calls, no filesystem I/O.
- No imports from live_runner, live_execution, or any ClickHouse layer.
- Uses the same accumulation engine and fair-value model used by the live bot.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Optional

from .accumulation_engine import (
    ACTION_ACCUMULATE,
    ACTION_FREEZE,
    BestQuote,
    LEG_NO,
    LEG_YES,
    PairMarketState,
    evaluate_accumulation,
)
from .config_models import CryptoPairPaperModeConfig
from .fair_value import estimate_fair_value
from .paper_runner import build_default_paper_mode_config
from .reference_feed import FeedConnectionState, ReferencePriceSnapshot


# ---------------------------------------------------------------------------
# Input model
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BacktestObservation:
    """One observation record fed to the backtest harness.

    Attributes:
        symbol: "BTC", "ETH", or "SOL".
        duration_min: 5 or 15.
        market_id: Unique market identifier.
        yes_ask: Best ask for YES leg; None triggers quote_skip.
        no_ask: Best ask for NO leg; None triggers quote_skip.
        underlying_price: Spot price for fair-value computation; None means no
            fair-value filter is applied.
        threshold: Market resolution threshold; None means no fair-value filter.
        remaining_seconds: Seconds to expiry; None means no fair-value filter.
        feed_is_stale: When True the harness injects a stale snapshot which
            causes the accumulation engine to return ACTION_FREEZE (counted as
            feed_stale_skip).
        yes_accumulated_size: Simulated already-accumulated YES size.  Defaults
            to 0.0.  Set to a positive value to simulate the "yes_only" partial
            state, where the engine only evaluates the NO leg and applies the
            soft fair-value rule exclusively to it.
        no_accumulated_size: Simulated already-accumulated NO size.  Defaults
            to 0.0.
        timestamp_iso: Preserved in output records; not used for logic.
    """

    symbol: str
    duration_min: int
    market_id: str

    yes_ask: Optional[float] = None
    no_ask: Optional[float] = None
    underlying_price: Optional[float] = None
    threshold: Optional[float] = None
    remaining_seconds: Optional[float] = None
    feed_is_stale: bool = False
    yes_accumulated_size: float = 0.0
    no_accumulated_size: float = 0.0
    timestamp_iso: Optional[str] = None


# ---------------------------------------------------------------------------
# Output model
# ---------------------------------------------------------------------------


@dataclass
class BacktestResult:
    """Aggregate metrics from one backtest run.

    Attributes:
        run_id: Unique identifier for this backtest run (UUID hex prefix).
        observations_total: Total number of observations processed.
        feed_stale_skips: Observations where feed_is_stale=True (ACTION_FREEZE).
        safety_skips: Reserved; always 0 in v0.
        quote_skips: Observations skipped due to missing YES or NO ask.
        hard_rule_skips: Observations skipped because pair cost > threshold.
        soft_rule_skips: Observations skipped because soft fair-value rule
            blocked all eligible legs.
        intents_generated: Observations that produced ACTION_ACCUMULATE.
        partial_leg_intents: Intents where only one leg was included.
        completed_pairs_simulated: Intents where both YES and NO legs were
            included (full pair at evaluation time).
        avg_completed_pair_cost: Mean projected_pair_cost for completed-pair
            intents; None when completed_pairs_simulated == 0.
        est_profit_per_completed_pair: Mean (1.0 - projected_pair_cost) for
            completed-pair intents; None when completed_pairs_simulated == 0.
        config_snapshot: The CryptoPairPaperModeConfig used, serialized to dict.
    """

    run_id: str
    observations_total: int = 0
    feed_stale_skips: int = 0
    safety_skips: int = 0
    quote_skips: int = 0
    hard_rule_skips: int = 0
    soft_rule_skips: int = 0
    intents_generated: int = 0
    partial_leg_intents: int = 0
    completed_pairs_simulated: int = 0
    avg_completed_pair_cost: Optional[float] = None
    est_profit_per_completed_pair: Optional[float] = None
    config_snapshot: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable dictionary (no Decimal, no datetime)."""
        return {
            "run_id": self.run_id,
            "observations_total": self.observations_total,
            "feed_stale_skips": self.feed_stale_skips,
            "safety_skips": self.safety_skips,
            "quote_skips": self.quote_skips,
            "hard_rule_skips": self.hard_rule_skips,
            "soft_rule_skips": self.soft_rule_skips,
            "intents_generated": self.intents_generated,
            "partial_leg_intents": self.partial_leg_intents,
            "completed_pairs_simulated": self.completed_pairs_simulated,
            "avg_completed_pair_cost": self.avg_completed_pair_cost,
            "est_profit_per_completed_pair": self.est_profit_per_completed_pair,
            "config_snapshot": self.config_snapshot,
        }


# ---------------------------------------------------------------------------
# Harness
# ---------------------------------------------------------------------------


class BacktestHarness:
    """Pure-function replay engine for Phase 1A crypto-pair observations.

    Args:
        config: Optional ``CryptoPairPaperModeConfig`` to use.  Defaults to
            ``build_default_paper_mode_config()`` from paper_runner.py.
    """

    def __init__(self, config: Optional[CryptoPairPaperModeConfig] = None) -> None:
        self._config: CryptoPairPaperModeConfig = (
            config if config is not None else build_default_paper_mode_config()
        )

    def run(self, observations: list[BacktestObservation]) -> BacktestResult:
        """Replay *observations* through the accumulation engine.

        Pure function — no network calls, no filesystem I/O.

        Args:
            observations: List of ``BacktestObservation`` records.

        Returns:
            ``BacktestResult`` with per-category counts and cost metrics.
        """
        run_id = uuid.uuid4().hex[:12]
        result = BacktestResult(
            run_id=run_id,
            config_snapshot=self._config.to_dict(),
        )

        completed_pair_costs: list[float] = []

        for obs in observations:
            result.observations_total += 1

            snapshot = self._build_feed_snapshot(obs)
            fair_yes, fair_no = self._compute_fair_values(obs)

            yes_quote: Optional[BestQuote] = None
            no_quote: Optional[BestQuote] = None
            if obs.yes_ask is not None:
                yes_quote = BestQuote(
                    leg=LEG_YES,
                    token_id=f"yes-{obs.market_id}",
                    ask_price=Decimal(str(obs.yes_ask)),
                )
            if obs.no_ask is not None:
                no_quote = BestQuote(
                    leg=LEG_NO,
                    token_id=f"no-{obs.market_id}",
                    ask_price=Decimal(str(obs.no_ask)),
                )

            state = PairMarketState(
                symbol=obs.symbol,
                duration_min=obs.duration_min,
                market_id=obs.market_id,
                yes_quote=yes_quote,
                no_quote=no_quote,
                yes_accumulated_size=Decimal(str(obs.yes_accumulated_size)),
                no_accumulated_size=Decimal(str(obs.no_accumulated_size)),
                fair_value_yes=fair_yes,
                fair_value_no=fair_no,
                feed_snapshot=snapshot,
            )

            intent = evaluate_accumulation(state, self._config)
            self._classify(intent, obs, result, completed_pair_costs)

        if result.completed_pairs_simulated > 0:
            result.avg_completed_pair_cost = sum(completed_pair_costs) / len(completed_pair_costs)
            result.est_profit_per_completed_pair = (
                sum(1.0 - c for c in completed_pair_costs) / len(completed_pair_costs)
            )

        return result

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _build_feed_snapshot(self, obs: BacktestObservation) -> ReferencePriceSnapshot:
        """Build a synthetic ReferencePriceSnapshot for one observation."""
        if obs.feed_is_stale:
            return ReferencePriceSnapshot(
                symbol=obs.symbol,
                price=obs.underlying_price,
                observed_at_s=1000.0,
                connection_state=FeedConnectionState.CONNECTED,
                is_stale=True,
                stale_threshold_s=15.0,
                feed_source="backtest",
            )

        # Fresh snapshot — feed gate passes; price used only for fair-value
        # computation (handled separately), not for freeze-gate logic.
        price = obs.underlying_price if obs.underlying_price is not None else 1.0
        return ReferencePriceSnapshot(
            symbol=obs.symbol,
            price=price,
            observed_at_s=1000.0,
            connection_state=FeedConnectionState.CONNECTED,
            is_stale=False,
            stale_threshold_s=15.0,
            feed_source="backtest",
        )

    def _compute_fair_values(
        self, obs: BacktestObservation
    ) -> tuple[Optional[float], Optional[float]]:
        """Compute YES and NO fair values if all required parameters are present."""
        if (
            obs.underlying_price is None
            or obs.threshold is None
            or obs.remaining_seconds is None
        ):
            return None, None

        try:
            fv_yes = estimate_fair_value(
                symbol=obs.symbol,
                duration_min=obs.duration_min,
                side="YES",
                underlying_price=obs.underlying_price,
                threshold=obs.threshold,
                remaining_seconds=obs.remaining_seconds,
            )
            fv_no = estimate_fair_value(
                symbol=obs.symbol,
                duration_min=obs.duration_min,
                side="NO",
                underlying_price=obs.underlying_price,
                threshold=obs.threshold,
                remaining_seconds=obs.remaining_seconds,
            )
            return fv_yes.fair_prob, fv_no.fair_prob
        except (ValueError, ZeroDivisionError):
            return None, None

    def _classify(
        self,
        intent,
        obs: BacktestObservation,
        result: BacktestResult,
        completed_pair_costs: list[float],
    ) -> None:
        """Classify one AccumulationIntent result and update counters."""
        from .accumulation_engine import ACTION_SKIP  # local import avoids circular ref

        if intent.action == ACTION_FREEZE:
            result.feed_stale_skips += 1
            return

        if intent.action == ACTION_SKIP:
            rationale = intent.rationale
            skip_reason = rationale.get("skip_reason", "")
            if skip_reason.startswith("missing_quotes"):
                result.quote_skips += 1
            elif skip_reason == "hard_rule_failed":
                result.hard_rule_skips += 1
            elif skip_reason == "soft_rule_blocked_all_legs":
                result.soft_rule_skips += 1
            else:
                # Catch-all for unknown skip reasons
                result.quote_skips += 1
            return

        if intent.action == ACTION_ACCUMULATE:
            result.intents_generated += 1
            legs = intent.legs
            has_yes = LEG_YES in legs
            has_no = LEG_NO in legs
            if has_yes and has_no:
                result.completed_pairs_simulated += 1
                if intent.projected_pair_cost is not None:
                    completed_pair_costs.append(float(intent.projected_pair_cost))
            elif has_yes or has_no:
                result.partial_leg_intents += 1
