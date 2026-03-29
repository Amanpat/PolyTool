"""Dev-only synthetic Track 2 event seeding for dashboard validation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import uuid4

from .clickhouse_sink import ClickHouseWriteResult, CryptoPairClickHouseEventWriter
from .config_models import CryptoPairPaperModeConfig
from .event_models import (
    CRYPTO_PAIR_EVENT_TYPES,
    CRYPTO_PAIR_EVENTS_TABLE,
    CryptoPairTrack2Event,
    SafetyStateTransitionEvent,
    build_events_from_paper_records,
)
from .paper_ledger import (
    LEG_YES,
    PaperLegFill,
    PaperOpportunityObservation,
    build_market_rollups,
    build_run_summary,
    compute_pair_settlement_pnl,
    compute_partial_leg_exposure,
    generate_order_intent,
)


DEMO_SEED_SOURCE = "crypto_pair_demo_seed_dev_only_v0"
DEMO_RUN_ID_PREFIX = "synthetic-demo-track2"
DEMO_MARKET_PREFIX = "synthetic-demo"
DEMO_STOPPED_REASON = "synthetic_demo_seed_completed"
DEMO_SYNTHETIC_ASSUMPTIONS = (
    "synthetic_demo_event_not_real_market",
    "dev_only_dashboard_validation_seed",
)


@dataclass(frozen=True)
class CryptoPairDemoSeedBatch:
    run_id: str
    source: str
    events: tuple[CryptoPairTrack2Event, ...]
    table_name: str = CRYPTO_PAIR_EVENTS_TABLE

    @property
    def event_count(self) -> int:
        return len(self.events)

    @property
    def event_types(self) -> tuple[str, ...]:
        present = {event.event_type for event in self.events}
        return tuple(
            event_type
            for event_type in CRYPTO_PAIR_EVENT_TYPES
            if event_type in present
        )

    @property
    def cleanup_sql(self) -> str:
        return (
            f"ALTER TABLE {self.table_name} DELETE "
            f"WHERE run_id = '{self.run_id}' AND source = '{self.source}'"
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "run_id": self.run_id,
            "source": self.source,
            "table_name": self.table_name,
            "event_count": self.event_count,
            "event_types": list(self.event_types),
            "cleanup_sql": self.cleanup_sql,
        }


@dataclass(frozen=True)
class CryptoPairDemoSeedWriteResult:
    batch: CryptoPairDemoSeedBatch
    write_result: ClickHouseWriteResult

    def to_dict(self) -> dict[str, object]:
        payload = self.batch.to_dict()
        payload["write_result"] = self.write_result.to_dict()
        return payload


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _iso_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


def _default_run_id(started_at: datetime) -> str:
    return (
        f"{DEMO_RUN_ID_PREFIX}-{started_at.strftime('%Y%m%dT%H%M%SZ')}-"
        f"{uuid4().hex[:8]}"
    )


def _demo_config() -> CryptoPairPaperModeConfig:
    return CryptoPairPaperModeConfig.from_dict(
        {
            "max_capital_per_market_usdc": "25",
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


def _build_observation(
    *,
    run_id: str,
    observed_at: datetime,
    market_key: str,
    symbol: str,
    duration_min: int,
    yes_quote_price: str,
    no_quote_price: str,
) -> PaperOpportunityObservation:
    synthetic_key = f"{DEMO_MARKET_PREFIX}-{market_key}"
    return PaperOpportunityObservation(
        opportunity_id=f"{synthetic_key}-{run_id}-opportunity",
        run_id=run_id,
        observed_at=_iso_utc(observed_at),
        market_id=synthetic_key,
        condition_id=f"{synthetic_key}-condition",
        slug=f"{synthetic_key}-dashboard-validation",
        symbol=symbol,
        duration_min=duration_min,
        yes_token_id=f"{synthetic_key}-yes",
        no_token_id=f"{synthetic_key}-no",
        yes_quote_price=yes_quote_price,
        no_quote_price=no_quote_price,
        quote_age_seconds=3,
        source=DEMO_SEED_SOURCE,
        assumptions=DEMO_SYNTHETIC_ASSUMPTIONS,
    )


def _build_fill(
    intent,
    *,
    fill_id_suffix: str,
    leg: str,
    token_id: str,
    filled_at: datetime,
    price: str,
    size: str,
    fee_adjustment_usdc: str,
) -> PaperLegFill:
    return PaperLegFill(
        fill_id=f"{intent.intent_id}-{fill_id_suffix}",
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
        filled_at=_iso_utc(filled_at),
        price=price,
        size=size,
        fee_adjustment_usdc=fee_adjustment_usdc,
    )


def build_demo_seed_batch(
    *,
    run_id: Optional[str] = None,
    started_at: Optional[datetime] = None,
) -> CryptoPairDemoSeedBatch:
    base_time = (started_at or _utcnow()).astimezone(timezone.utc).replace(
        microsecond=0
    )
    resolved_run_id = run_id or _default_run_id(base_time)
    config = _demo_config()

    paired_observation = _build_observation(
        run_id=resolved_run_id,
        observed_at=base_time,
        market_key="btc-5m-paired",
        symbol="BTC",
        duration_min=5,
        yes_quote_price="0.47",
        no_quote_price="0.48",
    )
    paired_intent = generate_order_intent(
        paired_observation,
        config,
        intent_id=f"{DEMO_MARKET_PREFIX}-{resolved_run_id}-btc-5m-paired-intent",
        created_at=_iso_utc(base_time + timedelta(seconds=1)),
        pair_size="10",
    )
    if paired_intent is None:
        raise ValueError("synthetic paired observation failed Track 2 intent generation")
    paired_fills = [
        _build_fill(
            paired_intent,
            fill_id_suffix="yes-fill",
            leg="YES",
            token_id=paired_observation.yes_token_id,
            filled_at=base_time + timedelta(seconds=2),
            price="0.47",
            size="10",
            fee_adjustment_usdc="0.0094",
        ),
        _build_fill(
            paired_intent,
            fill_id_suffix="no-fill",
            leg="NO",
            token_id=paired_observation.no_token_id,
            filled_at=base_time + timedelta(seconds=3),
            price="0.48",
            size="10",
            fee_adjustment_usdc="0.0096",
        ),
    ]
    paired_exposure = compute_partial_leg_exposure(
        paired_intent,
        paired_fills,
        as_of=_iso_utc(base_time + timedelta(seconds=4)),
    )
    paired_settlement = compute_pair_settlement_pnl(
        paired_exposure,
        settlement_id=(
            f"{DEMO_MARKET_PREFIX}-{resolved_run_id}-btc-5m-paired-settlement"
        ),
        resolved_at=_iso_utc(base_time + timedelta(minutes=5)),
        winning_leg="YES",
    )

    partial_observation = _build_observation(
        run_id=resolved_run_id,
        observed_at=base_time + timedelta(minutes=10),
        market_key="eth-15m-partial",
        symbol="ETH",
        duration_min=15,
        yes_quote_price="0.46",
        no_quote_price="0.49",
    )
    partial_intent = generate_order_intent(
        partial_observation,
        config,
        intent_id=f"{DEMO_MARKET_PREFIX}-{resolved_run_id}-eth-15m-partial-intent",
        created_at=_iso_utc(base_time + timedelta(minutes=10, seconds=1)),
        pair_size="5",
    )
    if partial_intent is None:
        raise ValueError(
            "synthetic partial observation failed Track 2 intent generation"
        )
    partial_fills = [
        _build_fill(
            partial_intent,
            fill_id_suffix="yes-fill",
            leg=LEG_YES,
            token_id=partial_observation.yes_token_id,
            filled_at=base_time + timedelta(minutes=10, seconds=2),
            price="0.46",
            size="5",
            fee_adjustment_usdc="0.0046",
        )
    ]
    partial_exposure = compute_partial_leg_exposure(
        partial_intent,
        partial_fills,
        as_of=_iso_utc(base_time + timedelta(minutes=10, seconds=4)),
    )

    market_rollups = build_market_rollups(
        [paired_observation, partial_observation],
        [paired_intent, partial_intent],
        [paired_exposure, partial_exposure],
        [paired_settlement],
    )
    run_summary = build_run_summary(
        run_id=resolved_run_id,
        generated_at=_iso_utc(base_time + timedelta(minutes=11)),
        market_rollups=market_rollups,
    )

    events = build_events_from_paper_records(
        observations=[paired_observation, partial_observation],
        intents=[paired_intent, partial_intent],
        fills=[*paired_fills, *partial_fills],
        exposures=[paired_exposure, partial_exposure],
        settlements=[paired_settlement],
        run_summary=run_summary,
        mode="paper",
        source=DEMO_SEED_SOURCE,
        stopped_reason=DEMO_STOPPED_REASON,
    )
    events.append(
        SafetyStateTransitionEvent.from_feed_state_change(
            transition_id=(
                f"{DEMO_MARKET_PREFIX}-{resolved_run_id}-reference-feed-disconnect"
            ),
            event_ts=_iso_utc(base_time + timedelta(minutes=10, seconds=30)),
            run_id=resolved_run_id,
            mode="paper",
            source=DEMO_SEED_SOURCE,
            symbol="ETH",
            from_state="connected_fresh",
            to_state="disconnected",
            market_id=partial_observation.market_id,
            condition_id=partial_observation.condition_id,
            slug=partial_observation.slug,
            duration_min=partial_observation.duration_min,
            reason="synthetic_demo_disconnect_for_dashboard_validation",
            cycle=2,
            details={
                "synthetic": True,
                "dev_only": True,
                "dashboard_validation_only": True,
            },
        )
    )
    ordered_events = tuple(
        sorted(
            events,
            key=lambda event: (
                event.event_ts,
                event.recorded_at,
                event.event_type,
                event.event_id,
            ),
        )
    )
    return CryptoPairDemoSeedBatch(
        run_id=resolved_run_id,
        source=DEMO_SEED_SOURCE,
        events=ordered_events,
    )


def seed_demo_events(
    *,
    writer: CryptoPairClickHouseEventWriter,
    run_id: Optional[str] = None,
    started_at: Optional[datetime] = None,
) -> CryptoPairDemoSeedWriteResult:
    batch = build_demo_seed_batch(run_id=run_id, started_at=started_at)
    write_result = writer.write_events(batch.events)
    return CryptoPairDemoSeedWriteResult(batch=batch, write_result=write_result)


__all__ = [
    "DEMO_MARKET_PREFIX",
    "DEMO_RUN_ID_PREFIX",
    "DEMO_SEED_SOURCE",
    "DEMO_STOPPED_REASON",
    "DEMO_SYNTHETIC_ASSUMPTIONS",
    "CryptoPairDemoSeedBatch",
    "CryptoPairDemoSeedWriteResult",
    "build_demo_seed_batch",
    "seed_demo_events",
]
