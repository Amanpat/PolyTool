"""Offline contract tests for Track 2 crypto-pair ClickHouse event sink."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

from packages.polymarket.crypto_pairs.clickhouse_sink import (
    ClickHouseSinkContract,
    CryptoPairClickHouseSink,
    CryptoPairClickHouseSinkConfig,
    build_clickhouse_sink,
)
from packages.polymarket.crypto_pairs.config_models import CryptoPairPaperModeConfig
from packages.polymarket.crypto_pairs.event_models import (
    CLICKHOUSE_EVENT_COLUMNS,
    CRYPTO_PAIR_EVENT_SCHEMA_VERSION,
    CRYPTO_PAIR_EVENT_TYPES,
    EVENT_TYPE_INTENT_GENERATED,
    EVENT_TYPE_OPPORTUNITY_OBSERVED,
    EVENT_TYPE_PAIR_SETTLEMENT_COMPLETED,
    EVENT_TYPE_PARTIAL_EXPOSURE_UPDATED,
    EVENT_TYPE_RUN_SUMMARY,
    EVENT_TYPE_SAFETY_STATE_TRANSITION,
    EVENT_TYPE_SIMULATED_FILL_RECORDED,
    SafetyStateTransitionEvent,
    build_events_from_paper_records,
    serialize_events,
)
from packages.polymarket.crypto_pairs.paper_ledger import (
    LEG_YES,
    PaperLegFill,
    PaperOpportunityObservation,
    build_market_rollups,
    build_run_summary,
    compute_pair_settlement_pnl,
    compute_partial_leg_exposure,
    generate_order_intent,
)


def _config() -> CryptoPairPaperModeConfig:
    return CryptoPairPaperModeConfig.from_dict(
        {
            "max_capital_per_market_usdc": "25",
            "max_open_paired_notional_usdc": "50",
            "target_pair_cost_threshold": "0.97",
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


def _observation(
    *,
    opportunity_id: str,
    market_id: str,
    condition_id: str,
    slug: str,
    symbol: str,
    yes_token_id: str,
    no_token_id: str,
    yes_quote_price: str,
    no_quote_price: str,
    observed_at: str,
) -> PaperOpportunityObservation:
    return PaperOpportunityObservation(
        opportunity_id=opportunity_id,
        run_id="run-track2",
        observed_at=observed_at,
        market_id=market_id,
        condition_id=condition_id,
        slug=slug,
        symbol=symbol,
        duration_min=5,
        yes_token_id=yes_token_id,
        no_token_id=no_token_id,
        yes_quote_price=yes_quote_price,
        no_quote_price=no_quote_price,
        target_pair_cost_threshold="0.97",
        quote_age_seconds=3,
        assumptions=("modelled_pair_close", "paper_fill_assumption"),
    )


def _fill(
    intent,
    *,
    fill_id: str,
    leg: str,
    token_id: str,
    price: str,
    size: str,
    fee_adjustment_usdc: str = "0",
) -> PaperLegFill:
    return PaperLegFill(
        fill_id=fill_id,
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
        filled_at="2026-03-23T12:00:03Z",
        price=price,
        size=size,
        fee_adjustment_usdc=fee_adjustment_usdc,
    )


def _build_sample_batch():
    config = _config()

    paired_observation = _observation(
        opportunity_id="opp-btc-paired",
        market_id="market-btc-5m",
        condition_id="cond-btc-5m",
        slug="btc-5m-up-or-down",
        symbol="BTC",
        yes_token_id="btc-yes",
        no_token_id="btc-no",
        yes_quote_price="0.47",
        no_quote_price="0.48",
        observed_at="2026-03-23T12:00:00Z",
    )
    paired_intent = generate_order_intent(
        paired_observation,
        config,
        intent_id="intent-btc-paired",
        created_at="2026-03-23T12:00:01Z",
        pair_size="10",
    )
    assert paired_intent is not None
    paired_fills = [
        _fill(
            paired_intent,
            fill_id="fill-btc-yes",
            leg="YES",
            token_id="btc-yes",
            price="0.47",
            size="10",
            fee_adjustment_usdc="0.0094",
        ),
        _fill(
            paired_intent,
            fill_id="fill-btc-no",
            leg="NO",
            token_id="btc-no",
            price="0.48",
            size="10",
            fee_adjustment_usdc="0.0096",
        ),
    ]
    paired_exposure = compute_partial_leg_exposure(
        paired_intent,
        paired_fills,
        as_of="2026-03-23T12:00:04Z",
    )
    settlement = compute_pair_settlement_pnl(
        paired_exposure,
        settlement_id="settlement-btc",
        resolved_at="2026-03-23T12:05:00Z",
        winning_leg="YES",
    )

    partial_observation = _observation(
        opportunity_id="opp-eth-partial",
        market_id="market-eth-5m",
        condition_id="cond-eth-5m",
        slug="eth-5m-up-or-down",
        symbol="ETH",
        yes_token_id="eth-yes",
        no_token_id="eth-no",
        yes_quote_price="0.46",
        no_quote_price="0.49",
        observed_at="2026-03-23T12:10:00Z",
    )
    partial_intent = generate_order_intent(
        partial_observation,
        config,
        intent_id="intent-eth-partial",
        created_at="2026-03-23T12:10:01Z",
        pair_size="5",
    )
    assert partial_intent is not None
    partial_fills = [
        _fill(
            partial_intent,
            fill_id="fill-eth-yes",
            leg=LEG_YES,
            token_id="eth-yes",
            price="0.46",
            size="5",
            fee_adjustment_usdc="0.0046",
        )
    ]
    partial_exposure = compute_partial_leg_exposure(
        partial_intent,
        partial_fills,
        as_of="2026-03-23T12:10:04Z",
    )

    rollups = build_market_rollups(
        [paired_observation, partial_observation],
        [paired_intent, partial_intent],
        [paired_exposure, partial_exposure],
        [settlement],
    )
    run_summary = build_run_summary(
        run_id="run-track2",
        generated_at="2026-03-23T12:15:00Z",
        market_rollups=rollups,
    )
    events = build_events_from_paper_records(
        observations=[paired_observation, partial_observation],
        intents=[paired_intent, partial_intent],
        fills=[*paired_fills, *partial_fills],
        exposures=[paired_exposure, partial_exposure],
        settlements=[settlement],
        run_summary=run_summary,
        mode="paper",
        stopped_reason="completed",
    )
    events.append(
        SafetyStateTransitionEvent.from_feed_state_change(
            transition_id="transition-btc-stale",
            event_ts="2026-03-23T12:00:02Z",
            run_id="run-track2",
            mode="paper",
            symbol="BTC",
            from_state="connected_fresh",
            to_state="stale",
            market_id="market-btc-5m",
            condition_id="cond-btc-5m",
            slug="btc-5m-up-or-down",
            duration_min=5,
            reason="reference_feed_stale",
            cycle=1,
            details={"freeze_new_intents": True},
        )
    )
    return events


def test_track2_event_serialization_covers_required_event_types() -> None:
    events = _build_sample_batch()

    serialized = serialize_events(events)
    event_types = {event["event_type"] for event in serialized}

    assert event_types == {
        EVENT_TYPE_OPPORTUNITY_OBSERVED,
        EVENT_TYPE_INTENT_GENERATED,
        EVENT_TYPE_SIMULATED_FILL_RECORDED,
        EVENT_TYPE_PARTIAL_EXPOSURE_UPDATED,
        EVENT_TYPE_PAIR_SETTLEMENT_COMPLETED,
        EVENT_TYPE_SAFETY_STATE_TRANSITION,
        EVENT_TYPE_RUN_SUMMARY,
    }
    assert any(
        event["event_type"] == EVENT_TYPE_PARTIAL_EXPOSURE_UPDATED
        and event["unpaired_size"] == "5"
        and event["exposure_status"] == "partial_yes"
        for event in serialized
    )
    assert any(
        event["event_type"] == EVENT_TYPE_PAIR_SETTLEMENT_COMPLETED
        and event["net_pnl_usdc"] == "0.5190"
        for event in serialized
    )
    assert any(
        event["event_type"] == EVENT_TYPE_SAFETY_STATE_TRANSITION
        and event["to_state"] == "stale"
        for event in serialized
    )
    json.dumps(serialized, sort_keys=True, allow_nan=False)


def test_disabled_clickhouse_sink_is_noop_and_does_not_use_client() -> None:
    class _ExplodingClient:
        def insert_rows(self, table: str, column_names: list[str], rows: list[list]) -> int:
            raise AssertionError("disabled sink should not call insert_rows")

    events = _build_sample_batch()
    sink = build_clickhouse_sink(
        CryptoPairClickHouseSinkConfig(enabled=False),
        client=_ExplodingClient(),
    )

    result = sink.write_events(events)

    assert result.enabled is False
    assert result.written_rows == 0
    assert result.attempted_events == len(events)
    assert result.skipped_reason == "disabled"
    assert sink.contract().to_dict()["activation_state"] == "disabled_by_default"


def test_enabled_clickhouse_sink_soft_fails_when_client_is_unavailable() -> None:
    class _FailingClient:
        def insert_rows(self, table: str, column_names: list[str], rows: list[list]) -> int:
            raise RuntimeError("clickhouse unavailable")

    sink = CryptoPairClickHouseSink(
        CryptoPairClickHouseSinkConfig(enabled=True, soft_fail=True),
        client=_FailingClient(),
    )

    result = sink.write_events(_build_sample_batch())

    assert result.enabled is True
    assert result.written_rows == 0
    assert result.skipped_reason == "write_failed"
    assert "unavailable" in result.error


def test_clickhouse_schema_contract_is_stable() -> None:
    expected_columns = (
        "event_id",
        "event_type",
        "schema_version",
        "event_ts",
        "recorded_at",
        "run_id",
        "mode",
        "source",
        "market_id",
        "condition_id",
        "slug",
        "symbol",
        "duration_min",
        "opportunity_id",
        "intent_id",
        "fill_id",
        "settlement_id",
        "transition_id",
        "leg",
        "token_id",
        "side",
        "state_key",
        "from_state",
        "to_state",
        "reason",
        "exposure_status",
        "winning_leg",
        "yes_token_id",
        "no_token_id",
        "yes_quote_price",
        "no_quote_price",
        "pair_quote_cost",
        "target_pair_cost_threshold",
        "threshold_edge_usdc",
        "pair_size",
        "intended_yes_price",
        "intended_no_price",
        "intended_pair_cost",
        "intended_paired_notional_usdc",
        "fill_price",
        "fill_size",
        "fill_notional_usdc",
        "fee_adjustment_usdc",
        "net_cash_delta_usdc",
        "paired_size",
        "paired_cost_usdc",
        "paired_fee_adjustment_usdc",
        "paired_net_cash_outflow_usdc",
        "unpaired_size",
        "unpaired_notional_usdc",
        "unpaired_max_loss_usdc",
        "unpaired_max_gain_usdc",
        "settlement_value_usdc",
        "gross_pnl_usdc",
        "net_pnl_usdc",
        "markets_seen",
        "opportunities_observed",
        "threshold_pass_count",
        "threshold_miss_count",
        "order_intents_generated",
        "paired_exposure_count",
        "partial_exposure_count",
        "settled_pair_count",
        "open_unpaired_notional_usdc",
        "quote_age_seconds",
        "threshold_passed",
        "assumptions_json",
        "event_payload_json",
    )

    assert CLICKHOUSE_EVENT_COLUMNS == expected_columns
    assert CRYPTO_PAIR_EVENT_TYPES == (
        EVENT_TYPE_OPPORTUNITY_OBSERVED,
        EVENT_TYPE_INTENT_GENERATED,
        EVENT_TYPE_SIMULATED_FILL_RECORDED,
        EVENT_TYPE_PARTIAL_EXPOSURE_UPDATED,
        EVENT_TYPE_PAIR_SETTLEMENT_COMPLETED,
        EVENT_TYPE_SAFETY_STATE_TRANSITION,
        EVENT_TYPE_RUN_SUMMARY,
    )

    contract = ClickHouseSinkContract.from_config()
    assert contract.schema_version == CRYPTO_PAIR_EVENT_SCHEMA_VERSION
    assert contract.table_name == "polytool.crypto_pair_events"
    assert contract.enabled is False

    ddl_path = (
        Path(__file__).resolve().parents[1]
        / "infra"
        / "clickhouse"
        / "initdb"
        / "26_crypto_pair_events.sql"
    )
    ddl_text = ddl_path.read_text(encoding="utf-8")
    assert "CREATE TABLE IF NOT EXISTS polytool.crypto_pair_events" in ddl_text
    for column_name in expected_columns:
        assert column_name in ddl_text

    for event in _build_sample_batch():
        assert tuple(event.to_clickhouse_row().keys()) == CLICKHOUSE_EVENT_COLUMNS
