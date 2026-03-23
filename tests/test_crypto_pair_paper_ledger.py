"""Offline tests for Track 2 / Phase 1A crypto-pair paper ledger."""

from __future__ import annotations

import json
from decimal import Decimal

import pytest

from packages.polymarket.crypto_pairs.config_models import (
    CryptoPairPaperConfigError,
    CryptoPairPaperModeConfig,
)
from packages.polymarket.crypto_pairs.paper_ledger import (
    LEG_NO,
    LEG_YES,
    PaperLegFill,
    PaperOpportunityObservation,
    build_market_rollups,
    build_run_summary,
    compute_pair_settlement_pnl,
    compute_partial_leg_exposure,
    generate_order_intent,
    get_order_intent_block_reason,
)


def _config(**overrides) -> CryptoPairPaperModeConfig:
    payload = {
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
    payload.update(overrides)
    return CryptoPairPaperModeConfig.from_dict(payload)


def _observation(
    *,
    run_id: str = "run-1",
    opportunity_id: str = "opp-1",
    market_id: str = "market-btc-5m",
    yes_quote_price: str = "0.47",
    no_quote_price: str = "0.48",
    target_pair_cost_threshold: str = "0.97",
    quote_age_seconds: int = 4,
) -> PaperOpportunityObservation:
    return PaperOpportunityObservation(
        opportunity_id=opportunity_id,
        run_id=run_id,
        observed_at="2026-03-23T12:00:00Z",
        market_id=market_id,
        condition_id="cond-btc-5m",
        slug="btc-5m-up-or-down",
        symbol="BTC",
        duration_min=5,
        yes_token_id="yes-token",
        no_token_id="no-token",
        yes_quote_price=yes_quote_price,
        no_quote_price=no_quote_price,
        target_pair_cost_threshold=target_pair_cost_threshold,
        quote_age_seconds=quote_age_seconds,
        assumptions=("modeled_pair_settlement", "maker_rebate_assumption"),
    )


def _fill(
    intent,
    *,
    fill_id: str,
    leg: str,
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
        token_id=intent.yes_token_id if leg == LEG_YES else intent.no_token_id,
        side="BUY",
        filled_at="2026-03-23T12:00:03Z",
        price=price,
        size=size,
        fee_adjustment_usdc=fee_adjustment_usdc,
    )


def test_complete_paired_fill_below_threshold_end_to_end() -> None:
    config = _config()
    observation = _observation(target_pair_cost_threshold=str(config.target_pair_cost_threshold))

    intent = generate_order_intent(
        observation,
        config,
        intent_id="intent-1",
        created_at="2026-03-23T12:00:01Z",
        pair_size="10",
    )

    assert intent is not None
    assert intent.intended_pair_cost == Decimal("0.95")
    assert intent.intended_paired_notional_usdc == Decimal("9.50")

    fills = [
        _fill(intent, fill_id="fill-yes", leg=LEG_YES, price="0.47", size="10", fee_adjustment_usdc="0.0094"),
        _fill(intent, fill_id="fill-no", leg=LEG_NO, price="0.48", size="10", fee_adjustment_usdc="0.0096"),
    ]
    exposure = compute_partial_leg_exposure(intent, fills, as_of="2026-03-23T12:00:04Z")
    settlement = compute_pair_settlement_pnl(
        exposure,
        settlement_id="settlement-1",
        resolved_at="2026-03-23T12:05:00Z",
        winning_leg=LEG_YES,
    )
    market_rollups = build_market_rollups([observation], [intent], [exposure], [settlement])
    run_summary = build_run_summary(
        run_id=intent.run_id,
        generated_at="2026-03-23T12:05:01Z",
        market_rollups=market_rollups,
    )

    assert exposure.exposure_status == "paired"
    assert exposure.paired_size == Decimal("10")
    assert exposure.unpaired_size == Decimal("0")
    assert exposure.paired_cost_usdc == Decimal("9.50")
    assert exposure.paired_fee_adjustment_usdc == Decimal("0.0190")

    assert settlement.settlement_value_usdc == Decimal("10")
    assert settlement.gross_pnl_usdc == Decimal("0.50")
    assert settlement.net_pnl_usdc == Decimal("0.5190")

    assert len(market_rollups) == 1
    assert market_rollups[0].threshold_pass_count == 1
    assert market_rollups[0].order_intents_generated == 1
    assert market_rollups[0].settled_pair_count == 1
    assert market_rollups[0].net_pnl_usdc == Decimal("0.5190")

    assert run_summary.markets_seen == 1
    assert run_summary.opportunities_observed == 1
    assert run_summary.settled_pair_count == 1
    assert run_summary.net_pnl_usdc == Decimal("0.5190")

    json.dumps(config.to_dict())
    json.dumps(observation.to_dict())
    json.dumps(intent.to_dict())
    json.dumps([fill.to_dict() for fill in fills])
    json.dumps(exposure.to_dict())
    json.dumps(settlement.to_dict())
    json.dumps(market_rollups[0].to_dict())
    json.dumps(run_summary.to_dict())


def test_one_leg_only_partial_exposure() -> None:
    config = _config()
    observation = _observation(target_pair_cost_threshold=str(config.target_pair_cost_threshold))
    intent = generate_order_intent(
        observation,
        config,
        intent_id="intent-2",
        created_at="2026-03-23T12:00:01Z",
        pair_size="10",
    )

    assert intent is not None

    fills = [
        _fill(intent, fill_id="fill-yes-only", leg=LEG_YES, price="0.47", size="10", fee_adjustment_usdc="0.0094"),
    ]
    exposure = compute_partial_leg_exposure(intent, fills, as_of="2026-03-23T12:00:04Z")
    market_rollups = build_market_rollups([observation], [intent], [exposure], [])
    run_summary = build_run_summary(
        run_id=intent.run_id,
        generated_at="2026-03-23T12:01:00Z",
        market_rollups=market_rollups,
    )

    assert exposure.exposure_status == "partial_yes"
    assert exposure.paired_size == Decimal("0")
    assert exposure.unpaired_leg == LEG_YES
    assert exposure.unpaired_size == Decimal("10")
    assert exposure.unpaired_notional_usdc == Decimal("4.70")
    assert exposure.unpaired_net_cash_outflow_usdc == Decimal("4.6906")
    assert exposure.unpaired_max_loss_usdc == Decimal("4.6906")
    assert exposure.unpaired_max_gain_usdc == Decimal("5.3094")

    assert market_rollups[0].paired_exposure_count == 0
    assert market_rollups[0].partial_exposure_count == 1
    assert market_rollups[0].open_unpaired_notional_usdc == Decimal("4.70")

    assert run_summary.partial_exposure_count == 1
    assert run_summary.open_unpaired_notional_usdc == Decimal("4.70")


def test_threshold_miss_blocks_intent_generation() -> None:
    config = _config(target_pair_cost_threshold="0.96")
    observation = _observation(
        yes_quote_price="0.49",
        no_quote_price="0.48",
        target_pair_cost_threshold="0.96",
    )

    block_reason = get_order_intent_block_reason(
        observation,
        config,
        pair_size="10",
    )
    intent = generate_order_intent(
        observation,
        config,
        intent_id="intent-threshold-miss",
        created_at="2026-03-23T12:00:01Z",
        pair_size="10",
    )
    market_rollups = build_market_rollups([observation], [], [], [])
    run_summary = build_run_summary(
        run_id="run-1",
        generated_at="2026-03-23T12:01:00Z",
        market_rollups=market_rollups,
    )

    assert block_reason == "threshold_miss"
    assert intent is None
    assert market_rollups[0].threshold_miss_count == 1
    assert market_rollups[0].order_intents_generated == 0
    assert run_summary.threshold_miss_count == 1
    assert run_summary.order_intents_generated == 0


def test_pair_settlement_accounting_is_independent_of_winning_leg_for_full_pair() -> None:
    config = _config(target_pair_cost_threshold="0.98")
    observation = _observation(
        yes_quote_price="0.49",
        no_quote_price="0.48",
        target_pair_cost_threshold="0.98",
    )
    intent = generate_order_intent(
        observation,
        config,
        intent_id="intent-3",
        created_at="2026-03-23T12:00:01Z",
        pair_size="2",
    )

    assert intent is not None

    exposure = compute_partial_leg_exposure(
        intent,
        [
            _fill(intent, fill_id="fill-yes-2", leg=LEG_YES, price="0.49", size="2"),
            _fill(intent, fill_id="fill-no-2", leg=LEG_NO, price="0.48", size="2"),
        ],
        as_of="2026-03-23T12:00:04Z",
    )
    settlement = compute_pair_settlement_pnl(
        exposure,
        settlement_id="settlement-2",
        resolved_at="2026-03-23T12:05:00Z",
        winning_leg=LEG_NO,
    )

    assert settlement.winning_leg == LEG_NO
    assert settlement.paired_size == Decimal("2")
    assert settlement.paired_cost_usdc == Decimal("1.94")
    assert settlement.settlement_value_usdc == Decimal("2")
    assert settlement.gross_pnl_usdc == Decimal("0.06")
    assert settlement.net_pnl_usdc == Decimal("0.06")


@pytest.mark.parametrize(
    ("payload", "match"),
    [
        (
            {"filters": {"symbols": ["DOGE"]}},
            "unsupported symbol",
        ),
        (
            {"target_pair_cost_threshold": "1.10"},
            "target_pair_cost_threshold",
        ),
        (
            {"fees": {"maker_rebate_bps": "20", "maker_fee_bps": "5"}},
            "cannot both be positive",
        ),
        (
            {
                "max_capital_per_market_usdc": "60",
                "max_open_paired_notional_usdc": "50",
            },
            "cannot exceed",
        ),
    ],
)
def test_config_validation_rejects_bad_inputs(payload, match: str) -> None:
    with pytest.raises(CryptoPairPaperConfigError, match=match):
        CryptoPairPaperModeConfig.from_dict(payload)
