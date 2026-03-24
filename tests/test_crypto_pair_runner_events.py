"""Tests for the Track 2 event sink integration in CryptoPairPaperRunner."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional
from unittest.mock import MagicMock

from packages.polymarket.clob import OrderBookTop
from packages.polymarket.crypto_pairs.clickhouse_sink import (
    ClickHouseWriteResult,
    CryptoPairClickHouseSink,
    CryptoPairClickHouseSinkConfig,
    CRYPTO_PAIR_EVENTS_TABLE,
    DisabledCryptoPairClickHouseSink,
    build_clickhouse_sink,
)
from packages.polymarket.crypto_pairs.event_models import (
    EVENT_TYPE_OPPORTUNITY_OBSERVED,
    EVENT_TYPE_INTENT_GENERATED,
    EVENT_TYPE_SIMULATED_FILL_RECORDED,
    EVENT_TYPE_PARTIAL_EXPOSURE_UPDATED,
    EVENT_TYPE_SAFETY_STATE_TRANSITION,
    EVENT_TYPE_RUN_SUMMARY,
)
from packages.polymarket.crypto_pairs.paper_runner import (
    CryptoPairPaperRunner,
    build_runner_settings,
)
from packages.polymarket.crypto_pairs.reference_feed import (
    FeedConnectionState,
    ReferencePriceSnapshot,
)
from tools.cli.crypto_pair_run import run_crypto_pair_runner


# ---------------------------------------------------------------------------
# Shared test helpers (mirrored from test_crypto_pair_run.py)
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# CaptureSink: records all events passed to write_events
# ---------------------------------------------------------------------------


class CaptureSink:
    def __init__(self) -> None:
        self.captured: list = []

    def write_events(self, events) -> ClickHouseWriteResult:
        self.captured.extend(events)
        return ClickHouseWriteResult(
            enabled=False,
            table_name=CRYPTO_PAIR_EVENTS_TABLE,
            attempted_events=len(self.captured),
            written_rows=0,
            skipped_reason="disabled",
        )

    def contract(self):
        return DisabledCryptoPairClickHouseSink().contract()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_default_path_sink_disabled(tmp_path: Path) -> None:
    """Without --sink-enabled, sink_write_result shows disabled and no writes."""
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

    assert manifest["sink_write_result"]["enabled"] is False
    assert manifest["sink_write_result"]["skipped_reason"] == "disabled"
    assert manifest["sink_write_result"]["written_rows"] == 0


def test_opt_in_sink_receives_events(tmp_path: Path) -> None:
    """With an enabled sink, write_events is called and receives opportunity rows."""
    market = _make_mock_market()
    gamma = _make_gamma_client([market])
    clob = _make_clob_client(
        {
            "btc-5m-up-yes": (None, 0.47),
            "btc-5m-up-no": (None, 0.48),
        }
    )

    mock_client = MagicMock()
    mock_client.insert_rows.return_value = 0

    config = CryptoPairClickHouseSinkConfig(
        enabled=True,
        clickhouse_host="localhost",
        clickhouse_port=8123,
        clickhouse_user="polytool_admin",
        clickhouse_password="test",
        soft_fail=True,
    )
    sink = CryptoPairClickHouseSink(config, client=mock_client)

    settings = build_runner_settings(
        artifact_base_dir=tmp_path,
        duration_seconds=0,
        cycle_limit=1,
    )
    runner = CryptoPairPaperRunner(
        settings,
        gamma_client=gamma,
        clob_client=clob,
        reference_feed=StaticFeed(_fresh_snapshot()),
        sink=sink,
    )
    runner.run()

    assert mock_client.insert_rows.called
    call_args = mock_client.insert_rows.call_args
    rows = call_args[0][2]  # positional arg: list of row values
    # Each row is a list of column values; we check one row has opportunity_observed
    # event_type is in position 1 (the CLICKHOUSE_EVENT_COLUMNS order)
    from packages.polymarket.crypto_pairs.event_models import CLICKHOUSE_EVENT_COLUMNS
    event_type_idx = list(CLICKHOUSE_EVENT_COLUMNS).index("event_type")
    event_types_in_rows = [row[event_type_idx] for row in rows]
    assert EVENT_TYPE_OPPORTUNITY_OBSERVED in event_types_in_rows


def test_soft_fail_sink_unavailable(tmp_path: Path) -> None:
    """Soft-fail sink: connection error sets skipped_reason=write_failed; artifacts intact."""
    market = _make_mock_market()
    gamma = _make_gamma_client([market])
    clob = _make_clob_client(
        {
            "btc-5m-up-yes": (None, 0.47),
            "btc-5m-up-no": (None, 0.48),
        }
    )

    failing_client = MagicMock()
    failing_client.insert_rows.side_effect = ConnectionError("ch down")

    config = CryptoPairClickHouseSinkConfig(
        enabled=True,
        clickhouse_host="localhost",
        clickhouse_port=8123,
        clickhouse_user="polytool_admin",
        clickhouse_password="test",
        soft_fail=True,
    )
    sink = CryptoPairClickHouseSink(config, client=failing_client)

    settings = build_runner_settings(
        artifact_base_dir=tmp_path,
        duration_seconds=0,
        cycle_limit=1,
    )
    runner = CryptoPairPaperRunner(
        settings,
        gamma_client=gamma,
        clob_client=clob,
        reference_feed=StaticFeed(_fresh_snapshot()),
        sink=sink,
    )
    manifest = runner.run()

    assert manifest["sink_write_result"]["skipped_reason"] == "write_failed"
    assert "ch down" in manifest["sink_write_result"]["error"]

    run_dir = Path(manifest["artifact_dir"])
    assert (run_dir / "run_manifest.json").exists()
    assert (run_dir / "observations.jsonl").exists()


def test_feed_state_transition_emitted(tmp_path: Path) -> None:
    """Transitioning from stale to fresh generates a SafetyStateTransitionEvent."""
    market = _make_mock_market()
    gamma = _make_gamma_client([market])
    clob = _make_clob_client(
        {
            "btc-5m-up-yes": (None, 0.47),
            "btc-5m-up-no": (None, 0.48),
        }
    )

    # Two-call feed: first call stale, second call fresh
    snapshots = [_stale_snapshot(), _fresh_snapshot()]
    call_index = [0]

    class AlternatingFeed:
        def connect(self) -> None:
            return None

        def disconnect(self) -> None:
            return None

        def get_snapshot(self, symbol: str) -> ReferencePriceSnapshot:
            idx = min(call_index[0], len(snapshots) - 1)
            call_index[0] += 1
            return snapshots[idx]

    capture = CaptureSink()
    settings = build_runner_settings(
        artifact_base_dir=tmp_path,
        duration_seconds=0,
        cycle_limit=2,
    )
    runner = CryptoPairPaperRunner(
        settings,
        gamma_client=gamma,
        clob_client=clob,
        reference_feed=AlternatingFeed(),
        sink=capture,
    )
    runner.run()

    transition_events = [
        e for e in capture.captured
        if e.event_type == EVENT_TYPE_SAFETY_STATE_TRANSITION
    ]
    assert len(transition_events) >= 1
    to_states = {e.to_state for e in transition_events}
    # At least one of stale or connected_fresh must appear
    assert to_states & {"stale", "connected_fresh"}


def test_deterministic_event_count(tmp_path: Path) -> None:
    """One market, one intent run produces the exact expected event mix."""
    market = _make_mock_market()
    gamma = _make_gamma_client([market])
    clob = _make_clob_client(
        {
            "btc-5m-up-yes": (None, 0.47),
            "btc-5m-up-no": (None, 0.48),
        }
    )

    capture = CaptureSink()
    settings = build_runner_settings(
        artifact_base_dir=tmp_path,
        duration_seconds=0,
        cycle_limit=1,
    )
    runner = CryptoPairPaperRunner(
        settings,
        gamma_client=gamma,
        clob_client=clob,
        reference_feed=StaticFeed(_fresh_snapshot()),
        sink=capture,
    )
    runner.run()

    by_type: dict[str, int] = {}
    for event in capture.captured:
        by_type[event.event_type] = by_type.get(event.event_type, 0) + 1

    assert by_type.get(EVENT_TYPE_OPPORTUNITY_OBSERVED, 0) == 1
    assert by_type.get(EVENT_TYPE_INTENT_GENERATED, 0) == 1
    assert by_type.get(EVENT_TYPE_SIMULATED_FILL_RECORDED, 0) == 2
    assert by_type.get(EVENT_TYPE_PARTIAL_EXPOSURE_UPDATED, 0) == 1
    assert by_type.get(EVENT_TYPE_RUN_SUMMARY, 0) == 1
    assert by_type.get(EVENT_TYPE_SAFETY_STATE_TRANSITION, 0) == 0
    assert sum(by_type.values()) == 6
