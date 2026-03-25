from __future__ import annotations

import json
from pathlib import Path
from typing import Optional
from unittest.mock import MagicMock

import pytest

from packages.polymarket.clob import OrderBookTop
from packages.polymarket.crypto_pairs.live_execution import (
    CryptoPairLiveExecutionAdapter,
    CryptoPairLiveExecutionError,
    LiveOrderRequest,
)
from packages.polymarket.crypto_pairs.reference_feed import (
    FeedConnectionState,
    ReferencePriceSnapshot,
)
from packages.polymarket.simtrader.execution.kill_switch import FileBasedKillSwitch
from tools.cli import crypto_pair_run
from tools.cli.crypto_pair_run import LIVE_CONFIRMATION_TEXT, run_crypto_pair_runner


def _make_mock_market(slug: str = "btc-5m-up") -> MagicMock:
    market = MagicMock()
    market.market_slug = slug
    market.question = "Will BTC be higher in 5 minutes?"
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


def _disconnected_snapshot(symbol: str = "BTC") -> ReferencePriceSnapshot:
    return ReferencePriceSnapshot(
        symbol=symbol,
        price=60_000.0,
        observed_at_s=1000.0,
        connection_state=FeedConnectionState.DISCONNECTED,
        is_stale=False,
        stale_threshold_s=15.0,
        feed_source="binance",
    )


class SequenceFeed:
    def __init__(self, snapshots: list[ReferencePriceSnapshot]) -> None:
        self.snapshots = list(snapshots)
        self.index = 0

    def connect(self) -> None:
        return None

    def disconnect(self) -> None:
        return None

    def get_snapshot(self, symbol: str) -> ReferencePriceSnapshot:
        snapshot = self.snapshots[min(self.index, len(self.snapshots) - 1)]
        self.index += 1
        return snapshot


class FakeOrderClient:
    def __init__(self) -> None:
        self.placed: list[str] = []
        self.cancelled: list[str] = []

    def place_limit_order(self, request: LiveOrderRequest) -> dict[str, str]:
        order_id = f"order-{len(self.placed) + 1}"
        self.placed.append(order_id)
        return {"status": "ok", "order_id": order_id}

    def cancel_order(self, order_id: str) -> dict[str, str]:
        self.cancelled.append(order_id)
        return {"status": "ok", "order_id": order_id}


def _read_jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_live_without_confirm_is_rejected(capsys) -> None:
    exit_code = crypto_pair_run.main(["--live", "--duration-seconds", "0"])
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "--confirm CONFIRM" in captured.err


def test_kill_switch_checked_before_live_cycle(tmp_path: Path) -> None:
    kill_switch_path = tmp_path / "kill_switch.txt"
    kill_switch_path.write_text("1", encoding="utf-8")

    manifest = run_crypto_pair_runner(
        live=True,
        confirm=LIVE_CONFIRMATION_TEXT,
        output_base=tmp_path,
        kill_switch_path=kill_switch_path,
        duration_seconds=0,
        cycle_limit=1,
        gamma_client=_make_gamma_client([_make_mock_market()]),
        clob_client=_make_clob_client(
            {
                "btc-5m-up-yes": (None, 0.47),
                "btc-5m-up-no": (None, 0.48),
            }
        ),
        reference_feed=SequenceFeed([_fresh_snapshot()]),
    )

    run_dir = Path(manifest["artifact_dir"])
    runtime_events = _read_jsonl(run_dir / "runtime_events.jsonl")

    assert manifest["stopped_reason"] == "kill_switch"
    assert runtime_events[1]["event_type"] == "kill_switch_checked"
    assert runtime_events[1]["payload"]["active"] is True


def test_no_market_order_path_exists() -> None:
    with pytest.raises(CryptoPairLiveExecutionError, match="market-order path"):
        LiveOrderRequest(
            market_id="market-1",
            token_id="token-1",
            side="BUY",
            price=1,
            size=1,
            order_type="market",
            post_only=True,
        )


def test_live_disconnect_cancels_working_orders_and_requires_reconnect(tmp_path: Path) -> None:
    kill_switch_path = tmp_path / "kill_switch.txt"
    client = FakeOrderClient()
    execution_adapter = CryptoPairLiveExecutionAdapter(
        kill_switch=FileBasedKillSwitch(kill_switch_path),
        order_client=client,
        live_enabled=True,
    )

    manifest = run_crypto_pair_runner(
        live=True,
        confirm=LIVE_CONFIRMATION_TEXT,
        output_base=tmp_path,
        kill_switch_path=kill_switch_path,
        duration_seconds=0,
        cycle_limit=3,
        cycle_interval_seconds=1,
        gamma_client=_make_gamma_client([_make_mock_market()]),
        clob_client=_make_clob_client(
            {
                "btc-5m-up-yes": (None, 0.47),
                "btc-5m-up-no": (None, 0.48),
            }
        ),
        reference_feed=SequenceFeed(
            [
                _fresh_snapshot(),
                _disconnected_snapshot(),
                _fresh_snapshot(),
            ]
        ),
        execution_adapter=execution_adapter,
    )

    run_dir = Path(manifest["artifact_dir"])
    runtime_events = _read_jsonl(run_dir / "runtime_events.jsonl")

    assert client.cancelled == ["order-1", "order-2"]
    assert any(
        event["event_type"] == "live_disconnect_guard_armed"
        for event in runtime_events
    )
    assert any(
        event["event_type"] == "live_resume_allowed"
        for event in runtime_events
    )
