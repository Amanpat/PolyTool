"""Deterministic offline tests for Track 2 risk controls.

Covers all four control gates:
  1. kill_switch        — stops before first cycle
  2. open_pairs_cap     — blocks intents when max_open_pairs reached
  3. daily_loss_cap     — blocks intents when estimated drawdown >= cap
  4. capital_window     — blocks intents when cumulative notional >= window cap

Also tests:
  5. CryptoPairRunnerSettings validation for max_capital_per_window_usdc
  6. cumulative_committed_notional_usdc includes settled intents
  7. format_preflight_summary shows max_capital_window
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from typing import Optional
from unittest.mock import MagicMock, patch

import pytest

from packages.polymarket.clob import OrderBookTop
from packages.polymarket.crypto_pairs.paper_runner import (
    CryptoPairPaperRunner,
    CryptoPairRunnerSettings,
    _OPERATOR_MAX_CAPITAL_PER_WINDOW_USDC,
    build_runner_settings,
)
from packages.polymarket.crypto_pairs.paper_ledger import (
    PaperExposureState,
    PaperLegPosition,
)
from packages.polymarket.crypto_pairs.position_store import CryptoPairPositionStore
from packages.polymarket.crypto_pairs.reference_feed import (
    FeedConnectionState,
    ReferencePriceSnapshot,
)
from packages.polymarket.simtrader.execution.kill_switch import FileBasedKillSwitch
from tools.cli.crypto_pair_run import format_preflight_summary


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_market(slug: str = "btc-5m-up", symbol: str = "BTC") -> MagicMock:
    market = MagicMock()
    market.market_slug = slug
    market.question = f"Will {symbol} be higher in 5 minutes?"
    market.clob_token_ids = [f"{slug}-yes", f"{slug}-no"]
    market.outcomes = ["Yes", "No"]
    market.active = True
    market.accepting_orders = True
    market.condition_id = f"cond-{slug}"
    market.end_date_iso = None
    return market


def _make_gamma_client(markets: list[MagicMock]) -> MagicMock:
    result = MagicMock()
    result.markets = markets
    client = MagicMock()
    client.fetch_all_markets.return_value = result
    return client


def _make_clob_client(
    prices: dict[str, tuple[Optional[float], Optional[float]]],
) -> MagicMock:
    def _side_effect(token_id: str):
        if token_id not in prices:
            return None
        best_bid, best_ask = prices[token_id]
        return OrderBookTop(
            token_id=token_id,
            best_bid=best_bid,
            best_ask=best_ask,
            raw_json={},
        )

    client = MagicMock()
    client.get_best_bid_ask.side_effect = _side_effect
    return client


def _fresh_snapshot(symbol: str = "BTC") -> ReferencePriceSnapshot:
    return ReferencePriceSnapshot(
        symbol=symbol,
        price=60_000.0,
        observed_at_s=1000.0,
        connection_state=FeedConnectionState.CONNECTED,
        is_stale=False,
        stale_threshold_s=15.0,
        feed_source="binance",
    )


class MomentumFeed:
    """Feed that returns a rising price to trigger UP momentum entry.

    First ``history_depth`` calls return base price. Subsequent calls return
    base * (1 + rise_pct), which exceeds the default 0.3% threshold.
    """

    def __init__(
        self,
        base_snapshot: ReferencePriceSnapshot,
        *,
        rise_pct: float = 0.01,
        history_depth: int = 2,
    ) -> None:
        self._base = base_snapshot
        self._rise_pct = rise_pct
        self._history_depth = history_depth
        self._call_count: int = 0

    def connect(self) -> None:
        return None

    def disconnect(self) -> None:
        return None

    def get_snapshot(self, symbol: str) -> ReferencePriceSnapshot:
        import dataclasses

        self._call_count += 1
        if self._call_count <= self._history_depth:
            price = self._base.price
        else:
            price = self._base.price * (1.0 + self._rise_pct)
        return dataclasses.replace(self._base, price=price)


def _read_jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _make_zero_leg_position(leg: str, token_id: str) -> PaperLegPosition:
    return PaperLegPosition(
        leg=leg,
        token_id=token_id,
        filled_size=Decimal("0"),
        average_fill_price=None,
        gross_notional_usdc=Decimal("0"),
        fee_adjustment_usdc=Decimal("0"),
        net_cash_delta_usdc=Decimal("0"),
        fill_count=0,
    )


def _make_exposure(
    intent_id: str,
    market_id: str,
    *,
    paired_net_cash_outflow_usdc: Decimal = Decimal("5"),
    unpaired_net_cash_outflow_usdc: Decimal = Decimal("0"),
    paired_size: Decimal = Decimal("10"),
    unpaired_size: Decimal = Decimal("0"),
) -> PaperExposureState:
    return PaperExposureState(
        run_id="run-test",
        intent_id=intent_id,
        market_id=market_id,
        condition_id=f"cond-{market_id}",
        slug=market_id,
        symbol="BTC",
        duration_min=5,
        as_of="2026-04-15T00:00:00+00:00",
        yes_position=_make_zero_leg_position("YES", f"{market_id}-yes"),
        no_position=_make_zero_leg_position("NO", f"{market_id}-no"),
        paired_size=paired_size,
        paired_cost_usdc=paired_net_cash_outflow_usdc,
        paired_fee_adjustment_usdc=Decimal("0"),
        paired_net_cash_outflow_usdc=paired_net_cash_outflow_usdc,
        unpaired_leg=None,
        unpaired_size=unpaired_size,
        unpaired_average_fill_price=None,
        unpaired_notional_usdc=unpaired_net_cash_outflow_usdc,
        unpaired_fee_adjustment_usdc=Decimal("0"),
        unpaired_net_cash_outflow_usdc=unpaired_net_cash_outflow_usdc,
        unpaired_max_loss_usdc=unpaired_net_cash_outflow_usdc,
        unpaired_max_gain_usdc=Decimal("0"),
        exposure_status="paired" if paired_size > Decimal("0") else "unpaired",
    )


# ---------------------------------------------------------------------------
# Test 1: Kill switch stops runner before first intent
# ---------------------------------------------------------------------------


def test_kill_switch_stops_paper_runner_before_first_intent(tmp_path: Path) -> None:
    kill_switch_path = tmp_path / "kill_switch.txt"
    kill_switch_path.write_text("1", encoding="utf-8")

    market = _make_mock_market()
    gamma = _make_gamma_client([market])
    clob = _make_clob_client(
        {
            "btc-5m-up-yes": (None, 0.72),
            "btc-5m-up-no": (None, 0.18),
        }
    )

    settings = build_runner_settings(
        artifact_base_dir=tmp_path,
        kill_switch_path=kill_switch_path,
        duration_seconds=0,
        cycle_limit=2,
    )
    runner = CryptoPairPaperRunner(
        settings,
        gamma_client=gamma,
        clob_client=clob,
        reference_feed=MomentumFeed(_fresh_snapshot(), rise_pct=0.01, history_depth=2),
        sleep_fn=lambda _: None,
    )
    manifest = runner.run()

    assert manifest["stopped_reason"] == "kill_switch", (
        f"expected kill_switch, got {manifest['stopped_reason']!r}"
    )

    run_dir = Path(manifest["artifact_dir"])
    intents_path = run_dir / "order_intents.jsonl"
    assert not intents_path.exists() or intents_path.stat().st_size == 0, (
        "no intents should be recorded when kill switch fires before cycle 1"
    )


# ---------------------------------------------------------------------------
# Test 2: open_pairs_cap blocks new intents
# ---------------------------------------------------------------------------


def test_open_pairs_cap_blocks_new_intents(tmp_path: Path) -> None:
    market = _make_mock_market()
    gamma = _make_gamma_client([market])
    # Prices that would trigger a momentum entry: yes_ask=0.72 < 0.75, no_ask=0.18 < 0.20
    clob = _make_clob_client(
        {
            "btc-5m-up-yes": (None, 0.72),
            "btc-5m-up-no": (None, 0.18),
        }
    )

    settings = build_runner_settings(
        config_payload={
            "max_open_pairs": 1,
            "paper_config": {"momentum": {"momentum_threshold": 0.003}},
        },
        artifact_base_dir=tmp_path,
        duration_seconds=0,
        cycle_limit=3,
    )
    store = CryptoPairPositionStore(
        mode="paper",
        artifact_base_dir=tmp_path,
    )
    # Pre-populate one open pair so open_pair_count() == 1 == max_open_pairs
    exposure = _make_exposure("intent-pre-existing", "btc-5m-up", paired_size=Decimal("5"))
    store.record_exposure(exposure)

    runner = CryptoPairPaperRunner(
        settings,
        gamma_client=gamma,
        clob_client=clob,
        reference_feed=MomentumFeed(_fresh_snapshot(), rise_pct=0.01, history_depth=2),
        store=store,
        sleep_fn=lambda _: None,
    )
    manifest = runner.run()

    run_dir = Path(manifest["artifact_dir"])
    runtime_events = _read_jsonl(run_dir / "runtime_events.jsonl")

    blocked = [
        e for e in runtime_events
        if e.get("event_type") == "order_intent_blocked"
        and e.get("payload", {}).get("block_reason") == "open_pairs_cap_reached"
    ]
    assert len(blocked) >= 1, (
        "expected at least one order_intent_blocked with block_reason=open_pairs_cap_reached"
    )


# ---------------------------------------------------------------------------
# Test 3: daily_loss_cap blocks new intents
# ---------------------------------------------------------------------------


def test_daily_loss_cap_blocks_new_intents(tmp_path: Path) -> None:
    market = _make_mock_market()
    gamma = _make_gamma_client([market])
    clob = _make_clob_client(
        {
            "btc-5m-up-yes": (None, 0.72),
            "btc-5m-up-no": (None, 0.18),
        }
    )

    settings = build_runner_settings(
        artifact_base_dir=tmp_path,
        duration_seconds=0,
        cycle_limit=3,
    )
    store = CryptoPairPositionStore(
        mode="paper",
        artifact_base_dir=tmp_path,
    )

    runner = CryptoPairPaperRunner(
        settings,
        gamma_client=gamma,
        clob_client=clob,
        reference_feed=MomentumFeed(_fresh_snapshot(), rise_pct=0.01, history_depth=2),
        store=store,
        sleep_fn=lambda _: None,
    )

    # Mock the drawdown to return the cap value, causing the check to trip
    with patch.object(
        store,
        "estimated_daily_drawdown_usdc",
        return_value=settings.daily_loss_cap_usdc,
    ):
        manifest = runner.run()

    run_dir = Path(manifest["artifact_dir"])
    runtime_events = _read_jsonl(run_dir / "runtime_events.jsonl")

    blocked = [
        e for e in runtime_events
        if e.get("event_type") == "order_intent_blocked"
        and e.get("payload", {}).get("block_reason") == "daily_loss_cap_reached"
    ]
    assert len(blocked) >= 1, (
        "expected at least one order_intent_blocked with block_reason=daily_loss_cap_reached"
    )


# ---------------------------------------------------------------------------
# Test 4: capital_window_exceeded blocks new intents
# ---------------------------------------------------------------------------


def test_capital_window_exceeded_blocks_new_intents(tmp_path: Path) -> None:
    market = _make_mock_market()
    gamma = _make_gamma_client([market])
    clob = _make_clob_client(
        {
            "btc-5m-up-yes": (None, 0.72),
            "btc-5m-up-no": (None, 0.18),
        }
    )

    settings = build_runner_settings(
        artifact_base_dir=tmp_path,
        duration_seconds=0,
        cycle_limit=3,
    )
    store = CryptoPairPositionStore(
        mode="paper",
        artifact_base_dir=tmp_path,
    )

    runner = CryptoPairPaperRunner(
        settings,
        gamma_client=gamma,
        clob_client=clob,
        reference_feed=MomentumFeed(_fresh_snapshot(), rise_pct=0.01, history_depth=2),
        store=store,
        sleep_fn=lambda _: None,
    )

    # Mock cumulative notional to return the cap value, causing the check to trip
    with patch.object(
        store,
        "cumulative_committed_notional_usdc",
        return_value=settings.max_capital_per_window_usdc,
    ):
        manifest = runner.run()

    run_dir = Path(manifest["artifact_dir"])
    runtime_events = _read_jsonl(run_dir / "runtime_events.jsonl")

    blocked = [
        e for e in runtime_events
        if e.get("event_type") == "order_intent_blocked"
        and e.get("payload", {}).get("block_reason") == "capital_window_exceeded"
    ]
    assert len(blocked) >= 1, (
        "expected at least one order_intent_blocked with block_reason=capital_window_exceeded"
    )


# ---------------------------------------------------------------------------
# Test 5: Settings rejects max_capital_per_window_usdc <= 0
# ---------------------------------------------------------------------------


def test_capital_window_zero_raises_on_construction() -> None:
    with pytest.raises(ValueError, match="max_capital_per_window_usdc must be > 0"):
        CryptoPairRunnerSettings(max_capital_per_window_usdc=Decimal("0"))


# ---------------------------------------------------------------------------
# Test 6: Settings rejects max_capital_per_window_usdc above operator ceiling
# ---------------------------------------------------------------------------


def test_capital_window_above_ceiling_raises_on_construction() -> None:
    above_ceiling = _OPERATOR_MAX_CAPITAL_PER_WINDOW_USDC + Decimal("1")
    with pytest.raises(ValueError, match="max_capital_per_window_usdc cannot exceed"):
        CryptoPairRunnerSettings(max_capital_per_window_usdc=above_ceiling)


# ---------------------------------------------------------------------------
# Test 7: cumulative_committed_notional_usdc includes settled intents
# ---------------------------------------------------------------------------


def test_cumulative_committed_notional_includes_settled_intents(tmp_path: Path) -> None:
    store = CryptoPairPositionStore(mode="paper", artifact_base_dir=tmp_path)

    # Record two exposures: one open, one settled
    open_exposure = _make_exposure(
        "intent-open",
        "btc-5m-up",
        paired_net_cash_outflow_usdc=Decimal("5"),
        unpaired_net_cash_outflow_usdc=Decimal("0"),
        paired_size=Decimal("10"),
    )
    settled_exposure = _make_exposure(
        "intent-settled",
        "btc-5m-up",
        paired_net_cash_outflow_usdc=Decimal("3"),
        unpaired_net_cash_outflow_usdc=Decimal("0"),
        paired_size=Decimal("6"),
    )

    store.record_exposure(open_exposure)
    store.record_exposure(settled_exposure)

    # Mark one intent as settled
    from packages.polymarket.crypto_pairs.paper_ledger import PaperPairSettlement
    settlement = PaperPairSettlement(
        settlement_id="settle-1",
        run_id="run-test",
        intent_id="intent-settled",
        market_id="btc-5m-up",
        condition_id="cond-btc-5m-up",
        slug="btc-5m-up",
        symbol="BTC",
        duration_min=5,
        resolved_at="2026-04-15T00:01:00+00:00",
        winning_leg="YES",
        paired_size=Decimal("6"),
        paired_cost_usdc=Decimal("3"),
        paired_fee_adjustment_usdc=Decimal("0"),
        paired_net_cash_outflow_usdc=Decimal("3"),
        settlement_value_usdc=Decimal("3"),
        gross_pnl_usdc=Decimal("0"),
        net_pnl_usdc=Decimal("0"),
        unpaired_leg=None,
        unpaired_size=Decimal("0"),
    )
    store.record_settlement(settlement)

    # current_open_paired_notional_usdc should exclude the settled intent
    open_only = store.current_open_paired_notional_usdc()
    assert open_only == Decimal("5"), (
        f"open notional should be 5 (only open intent), got {open_only}"
    )

    # cumulative should include both
    cumulative = store.cumulative_committed_notional_usdc()
    assert cumulative == Decimal("8"), (
        f"cumulative should be 8 (5 open + 3 settled), got {cumulative}"
    )


# ---------------------------------------------------------------------------
# Test 8: format_preflight_summary shows max_capital_window
# ---------------------------------------------------------------------------


def test_preflight_summary_shows_capital_window() -> None:
    settings = CryptoPairRunnerSettings()
    preflight = {
        "mode": "paper",
        "settings": settings.to_dict(),
        "markets": [],
        "symbol_filters": [],
        "duration_filters": [],
    }
    output = format_preflight_summary(preflight)

    assert "max_capital_window" in output, (
        "format_preflight_summary output must contain 'max_capital_window'"
    )
    # Verify the configured value (default 50) appears
    assert "50 USDC" in output, (
        "format_preflight_summary should show '50 USDC' for the default window cap"
    )


def test_preflight_summary_shows_configured_capital_window() -> None:
    """When a non-default window cap is configured, preflight shows the actual value."""
    settings = CryptoPairRunnerSettings(max_capital_per_window_usdc=Decimal("25"))
    preflight = {
        "mode": "paper",
        "settings": settings.to_dict(),
        "markets": [],
        "symbol_filters": [],
        "duration_filters": [],
    }
    output = format_preflight_summary(preflight)

    assert "25 USDC" in output, (
        "format_preflight_summary should show '25 USDC' for a configured 25 USDC window cap"
    )
