from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional
from unittest.mock import MagicMock

from packages.polymarket.clob import OrderBookTop
from packages.polymarket.crypto_pairs.paper_runner import (
    CryptoPairPaperRunner,
    build_runner_settings,
)
from packages.polymarket.crypto_pairs.position_store import CryptoPairPositionStore
from packages.polymarket.crypto_pairs.reference_feed import (
    FeedConnectionState,
    ReferencePriceSnapshot,
)
from tools.cli.crypto_pair_run import run_crypto_pair_runner


def _make_mock_market(
    slug: str = "btc-5m-up",
    question: str = "Will BTC be higher in 5 minutes?",
    symbol: str = "BTC",
) -> MagicMock:
    market = MagicMock()
    market.market_slug = slug
    market.question = question
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


def _stale_snapshot(symbol: str = "BTC") -> ReferencePriceSnapshot:
    return ReferencePriceSnapshot(
        symbol=symbol,
        price=60_000.0,
        observed_at_s=980.0,
        connection_state=FeedConnectionState.CONNECTED,
        is_stale=True,
        stale_threshold_s=15.0,
        feed_source="binance",
    )


class StaticFeed:
    def __init__(self, snapshot: ReferencePriceSnapshot) -> None:
        self.snapshot = snapshot

    def connect(self) -> None:
        return None

    def disconnect(self) -> None:
        return None

    def get_snapshot(self, symbol: str) -> ReferencePriceSnapshot:
        return self.snapshot


def _read_jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_paper_default_path_creates_jsonl_bundle(tmp_path: Path) -> None:
    market = _make_mock_market()
    gamma = _make_gamma_client([market])
    clob = _make_clob_client(
        {
            "btc-5m-up-yes": (None, 0.47),
            "btc-5m-up-no": (None, 0.48),
        }
    )

    manifest = run_crypto_pair_runner(
        output_base=tmp_path,
        duration_seconds=0,
        cycle_limit=1,
        gamma_client=gamma,
        clob_client=clob,
        reference_feed=StaticFeed(_fresh_snapshot()),
    )

    run_dir = Path(manifest["artifact_dir"])
    assert manifest["mode"] == "paper"
    assert manifest["stopped_reason"] == "completed"
    assert run_dir.exists()
    assert (run_dir / "run_manifest.json").exists()
    assert (run_dir / "config_snapshot.json").exists()
    assert (run_dir / "runtime_events.jsonl").exists()
    assert (run_dir / "observations.jsonl").exists()
    assert (run_dir / "order_intents.jsonl").exists()
    assert (run_dir / "fills.jsonl").exists()
    assert (run_dir / "exposures.jsonl").exists()
    assert (run_dir / "market_rollups.jsonl").exists()
    assert (run_dir / "run_summary.json").exists()

    intents = _read_jsonl(run_dir / "order_intents.jsonl")
    fills = _read_jsonl(run_dir / "fills.jsonl")
    exposures = _read_jsonl(run_dir / "exposures.jsonl")
    assert len(intents) == 1
    assert len(fills) == 2
    assert len(exposures) == 1
    assert exposures[0]["exposure_status"] == "paired"


def test_paper_disconnect_freezes_new_intents_and_logs_transition(tmp_path: Path) -> None:
    market = _make_mock_market()
    gamma = _make_gamma_client([market])
    clob = _make_clob_client(
        {
            "btc-5m-up-yes": (None, 0.47),
            "btc-5m-up-no": (None, 0.48),
        }
    )

    manifest = run_crypto_pair_runner(
        output_base=tmp_path,
        duration_seconds=0,
        cycle_limit=1,
        gamma_client=gamma,
        clob_client=clob,
        reference_feed=StaticFeed(_stale_snapshot()),
    )

    run_dir = Path(manifest["artifact_dir"])
    runtime_events = _read_jsonl(run_dir / "runtime_events.jsonl")
    intents_path = run_dir / "order_intents.jsonl"

    assert not intents_path.exists()
    assert any(
        event["event_type"] == "feed_state_changed"
        and event["payload"]["to_state"] == "stale"
        for event in runtime_events
    )
    assert any(
        event["event_type"] == "paper_new_intents_frozen"
        for event in runtime_events
    )


def test_duration_window_stops_after_expected_cycles(tmp_path: Path) -> None:
    market = _make_mock_market()
    gamma = _make_gamma_client([market])
    clob = _make_clob_client(
        {
            "btc-5m-up-yes": (None, 0.47),
            "btc-5m-up-no": (None, 0.48),
        }
    )
    sleep_calls: list[int] = []

    settings = build_runner_settings(
        config_payload={"cycle_interval_seconds": 5},
        artifact_base_dir=tmp_path,
        duration_seconds=11,
    )
    runner = CryptoPairPaperRunner(
        settings,
        gamma_client=gamma,
        clob_client=clob,
        reference_feed=StaticFeed(_fresh_snapshot()),
        sleep_fn=lambda seconds: sleep_calls.append(seconds),
    )

    manifest = runner.run()

    assert manifest["stopped_reason"] == "completed"
    assert manifest["runner_result"]["cycles_completed"] == 3
    assert sleep_calls == [5, 5]


def test_runner_emits_heartbeat_event_and_callback(tmp_path: Path) -> None:
    market = _make_mock_market()
    gamma = _make_gamma_client([market])
    clob = _make_clob_client(
        {
            "btc-5m-up-yes": (None, 0.47),
            "btc-5m-up-no": (None, 0.48),
        }
    )
    started_at = datetime(2026, 3, 23, 0, 0, tzinfo=timezone.utc)
    current_time = started_at + timedelta(minutes=2)
    store = CryptoPairPositionStore(
        mode="paper",
        artifact_base_dir=tmp_path,
        started_at=started_at,
    )
    heartbeat_payloads: list[dict] = []

    settings = build_runner_settings(
        config_payload={"cycle_interval_seconds": 5},
        artifact_base_dir=tmp_path,
        duration_seconds=0,
        cycle_limit=1,
        heartbeat_interval_seconds=60,
    )
    runner = CryptoPairPaperRunner(
        settings,
        gamma_client=gamma,
        clob_client=clob,
        reference_feed=StaticFeed(_fresh_snapshot()),
        store=store,
        heartbeat_callback=heartbeat_payloads.append,
        now_fn=lambda: current_time,
        sleep_fn=lambda _: None,
    )

    manifest = runner.run()

    runtime_events = _read_jsonl(Path(manifest["artifact_dir"]) / "runtime_events.jsonl")
    heartbeats = [
        event for event in runtime_events if event["event_type"] == "runner_heartbeat"
    ]

    assert len(heartbeats) == 1
    assert heartbeat_payloads[0]["elapsed_runtime"] == "00:02:00"
    assert heartbeats[0]["payload"]["opportunities_observed"] == 1
    assert heartbeats[0]["payload"]["intents_generated"] == 1
    assert heartbeats[0]["payload"]["completed_pairs"] == 1
    assert heartbeats[0]["payload"]["partial_exposure_count"] == 0
    assert heartbeats[0]["payload"]["latest_feed_states"] == {"BTC": "connected_fresh"}
    assert heartbeats[0]["payload"]["stale_symbols"] == []


def test_operator_interrupt_finalizes_artifacts_cleanly(tmp_path: Path) -> None:
    market = _make_mock_market()
    gamma = _make_gamma_client([market])
    clob = _make_clob_client(
        {
            "btc-5m-up-yes": (None, 0.47),
            "btc-5m-up-no": (None, 0.48),
        }
    )

    settings = build_runner_settings(
        config_payload={"cycle_interval_seconds": 5},
        artifact_base_dir=tmp_path,
        duration_seconds=10,
    )
    runner = CryptoPairPaperRunner(
        settings,
        gamma_client=gamma,
        clob_client=clob,
        reference_feed=StaticFeed(_fresh_snapshot()),
        sleep_fn=lambda _: (_ for _ in ()).throw(KeyboardInterrupt()),
    )

    manifest = runner.run()
    run_dir = Path(manifest["artifact_dir"])
    runtime_events = _read_jsonl(run_dir / "runtime_events.jsonl")

    assert manifest["stopped_reason"] == "operator_interrupt"
    assert (run_dir / "run_manifest.json").exists()
    assert (run_dir / "run_summary.json").exists()
    assert any(
        event["event_type"] == "operator_interrupt"
        for event in runtime_events
    )
