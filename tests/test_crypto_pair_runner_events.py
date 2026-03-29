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


class MomentumFeed:
    """Feed that simulates a rising price to trigger an UP momentum signal.

    Returns the base snapshot price for the first ``history_depth`` calls,
    then returns a price that is ``rise_pct`` above the base. After
    ``history_depth + 1`` calls the runner's internal price history deque
    contains a move larger than the default 0.3% threshold.
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


class _CyclingStaleFeed:
    """Returns fresh snapshot on first call, stale on subsequent calls."""

    def __init__(self, symbol: str = "BTC") -> None:
        self._symbol = symbol
        self._calls = 0

    def connect(self) -> None:
        pass

    def disconnect(self) -> None:
        pass

    def get_snapshot(self, symbol: str) -> ReferencePriceSnapshot:
        self._calls += 1
        if self._calls == 1:
            return _fresh_snapshot(symbol)
        return _stale_snapshot(symbol)


def _make_paper_obs():
    """Build a minimal PaperOpportunityObservation for direct unit tests."""
    from packages.polymarket.crypto_pairs.paper_ledger import PaperOpportunityObservation
    return PaperOpportunityObservation(
        opportunity_id="opp-unit-test",
        run_id="run-unit",
        observed_at="2026-01-01T00:00:00Z",
        market_id="btc-5m-up",
        condition_id="cond-1",
        slug="btc-5m-up",
        symbol="BTC",
        duration_min=5,
        yes_token_id="yes-tok",
        no_token_id="no-tok",
        yes_quote_price="0.44",
        no_quote_price="0.44",
        quote_age_seconds=0,
        assumptions=(),
    )


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

    def write_event(self, event) -> ClickHouseWriteResult:
        self.captured.append(event)
        return ClickHouseWriteResult(
            enabled=False,
            table_name=CRYPTO_PAIR_EVENTS_TABLE,
            attempted_events=1,
            written_rows=0,
            skipped_reason="disabled",
        )

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


class _SpySink:
    """Records write_event / write_events calls separately for assertion."""

    def __init__(self, fail_write_event: bool = False) -> None:
        self.write_event_calls: list = []
        self.write_events_calls: list = []
        self._fail_write_event = fail_write_event

    def write_event(self, event) -> ClickHouseWriteResult:
        self.write_event_calls.append(event)
        if self._fail_write_event:
            return ClickHouseWriteResult(
                enabled=True,
                table_name=CRYPTO_PAIR_EVENTS_TABLE,
                attempted_events=1,
                written_rows=0,
                error="injected_failure",
            )
        return ClickHouseWriteResult(
            enabled=True,
            table_name=CRYPTO_PAIR_EVENTS_TABLE,
            attempted_events=1,
            written_rows=1,
        )

    def write_events(self, events) -> ClickHouseWriteResult:
        events = list(events)
        self.write_events_calls.append(events)
        return ClickHouseWriteResult(
            enabled=True,
            table_name=CRYPTO_PAIR_EVENTS_TABLE,
            attempted_events=len(events),
            written_rows=len(events),
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
    """One market, 3-cycle run with MomentumFeed produces the exact expected event mix.

    Cycles 1-2 seed price history at base price (NONE signal).
    Cycle 3: +1% rise clears the 0.3% threshold -> UP signal -> intent generated.
    yes_ask=0.72 < max_favorite_entry=0.75 -> favorite=YES fills.
    no_ask=0.18 < max_hedge_price=0.20 -> hedge=NO fills (paired).
    """
    market = _make_mock_market()
    gamma = _make_gamma_client([market])
    clob = _make_clob_client(
        {
            "btc-5m-up-yes": (None, 0.72),
            "btc-5m-up-no": (None, 0.18),
        }
    )

    capture = CaptureSink()
    settings = build_runner_settings(
        artifact_base_dir=tmp_path,
        duration_seconds=0,
        cycle_limit=3,
        config_payload={"paper_config": {"momentum": {"momentum_threshold": 0.003}}},
    )
    runner = CryptoPairPaperRunner(
        settings,
        gamma_client=gamma,
        clob_client=clob,
        reference_feed=MomentumFeed(_fresh_snapshot(), rise_pct=0.01, history_depth=2),
        sink=capture,
        sleep_fn=lambda _: None,
    )
    runner.run()

    by_type: dict[str, int] = {}
    for event in capture.captured:
        by_type[event.event_type] = by_type.get(event.event_type, 0) + 1

    assert by_type.get(EVENT_TYPE_OPPORTUNITY_OBSERVED, 0) == 3
    assert by_type.get(EVENT_TYPE_INTENT_GENERATED, 0) == 1
    assert by_type.get(EVENT_TYPE_SIMULATED_FILL_RECORDED, 0) == 2
    assert by_type.get(EVENT_TYPE_PARTIAL_EXPOSURE_UPDATED, 0) == 1
    assert by_type.get(EVENT_TYPE_RUN_SUMMARY, 0) == 1
    assert by_type.get(EVENT_TYPE_SAFETY_STATE_TRANSITION, 0) == 0
    assert sum(by_type.values()) == 8


# ---------------------------------------------------------------------------
# Streaming mode tests (quick-021)
# ---------------------------------------------------------------------------


def test_batch_mode_default_unchanged(tmp_path: Path) -> None:
    """In batch mode write_event() is never called; write_events() called exactly once."""
    spy = _SpySink()
    market = _make_mock_market()
    gamma = _make_gamma_client([market])
    clob = _make_clob_client(
        {
            "btc-5m-up-yes": (None, 0.47),
            "btc-5m-up-no": (None, 0.48),
        }
    )

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
        sink=spy,
        sleep_fn=lambda _: None,
    )
    manifest = runner.run()

    assert manifest["stopped_reason"] == "completed"
    assert len(spy.write_event_calls) == 0, "write_event() must not be called in batch mode"
    assert len(spy.write_events_calls) == 1, "write_events() must be called exactly once at finalization"
    assert "sink_write_result" in manifest


def test_streaming_mode_emits_incrementally(tmp_path: Path) -> None:
    """In streaming mode write_event() is called for each in-loop event.

    Uses 3 cycles + MomentumFeed so the UP signal fires on cycle 3:
    - Cycles 1-2: seed price history at base price (NONE signal) -> 1 obs each
    - Cycle 3: +1% rise clears 0.3% threshold -> UP -> intent + 2 fills + exposure
    Total incremental write_event calls: 3 obs + 1 intent + 2 fills + 1 exposure = 7 >= 5.
    """
    spy = _SpySink()
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
        config_payload={
            "sink_flush_mode": "streaming",
            "paper_config": {"momentum": {"momentum_threshold": 0.003}},
        },
    )
    runner = CryptoPairPaperRunner(
        settings,
        gamma_client=gamma,
        clob_client=clob,
        reference_feed=MomentumFeed(_fresh_snapshot(), rise_pct=0.01, history_depth=2),
        sink=spy,
        sleep_fn=lambda _: None,
    )
    manifest = runner.run()

    assert manifest["stopped_reason"] == "completed"
    # 3 obs + 1 intent + 2 fills + 1 exposure = 7 incremental events
    assert len(spy.write_event_calls) >= 5, (
        f"Expected >= 5 incremental write_event calls in streaming mode, "
        f"got {len(spy.write_event_calls)}"
    )
    # finalization batch (run_summary at minimum) is still called
    assert len(spy.write_events_calls) == 1


def test_streaming_mode_sink_failure_soft_fails(tmp_path: Path) -> None:
    """Sink write failure in streaming mode logs a warning but run completes and artifacts exist."""
    spy = _SpySink(fail_write_event=True)
    market = _make_mock_market()
    gamma = _make_gamma_client([market])
    clob = _make_clob_client(
        {
            "btc-5m-up-yes": (None, 0.44),
            "btc-5m-up-no": (None, 0.44),
        }
    )

    settings = build_runner_settings(
        artifact_base_dir=tmp_path,
        duration_seconds=0,
        cycle_limit=1,
        config_payload={"sink_flush_mode": "streaming"},
    )
    runner = CryptoPairPaperRunner(
        settings,
        gamma_client=gamma,
        clob_client=clob,
        reference_feed=StaticFeed(_fresh_snapshot()),
        sink=spy,
        sleep_fn=lambda _: None,
    )
    # Must not raise even though all write_event calls return errors
    manifest = runner.run()

    assert manifest["stopped_reason"] == "completed"
    run_dir = Path(manifest["artifact_dir"])
    assert (run_dir / "run_manifest.json").exists()
    assert (run_dir / "observations.jsonl").exists()


def test_streaming_mode_consecutive_fail_guard(tmp_path: Path) -> None:
    """CryptoPairClickHouseSink skips write_event after max_consecutive_failures reached."""
    from packages.polymarket.crypto_pairs.event_models import OpportunityObservedEvent

    class _FailingClient:
        def insert_rows(self, table, columns, rows):
            raise RuntimeError("CH down")

    config = CryptoPairClickHouseSinkConfig(enabled=True, soft_fail=True)
    sink = CryptoPairClickHouseSink(config, client=_FailingClient(), max_consecutive_failures=2)

    obs = _make_paper_obs()
    evt = OpportunityObservedEvent.from_observation(obs, mode="paper")

    r1 = sink.write_event(evt)
    assert r1.error == "CH down"
    assert sink._consecutive_fail_count == 1

    r2 = sink.write_event(evt)
    assert r2.error == "CH down"
    assert sink._consecutive_fail_count == 2

    # 3rd call: limit reached, returns skipped
    r3 = sink.write_event(evt)
    assert r3.skipped_reason == "consecutive_fail_limit"
    assert r3.written_rows == 0


def test_streaming_mode_safety_transition_no_duplicate(tmp_path: Path) -> None:
    """Safety state transition streamed in loop is not re-emitted in finalization batch."""
    spy = _SpySink()
    market = _make_mock_market()
    gamma = _make_gamma_client([market])
    clob = _make_clob_client(
        {
            "btc-5m-up-yes": (None, 0.47),
            "btc-5m-up-no": (None, 0.48),
        }
    )

    settings = build_runner_settings(
        artifact_base_dir=tmp_path,
        duration_seconds=0,
        cycle_limit=2,
        config_payload={"sink_flush_mode": "streaming"},
    )
    # cycling feed: cycle 1 = fresh (no transition), cycle 2 = stale (triggers transition)
    runner = CryptoPairPaperRunner(
        settings,
        gamma_client=gamma,
        clob_client=clob,
        reference_feed=_CyclingStaleFeed("BTC"),
        sink=spy,
        sleep_fn=lambda _: None,
    )
    runner.run()

    streaming_transitions = [
        e for e in spy.write_event_calls
        if e.event_type == EVENT_TYPE_SAFETY_STATE_TRANSITION
    ]
    batched_transitions = [
        e
        for batch in spy.write_events_calls
        for e in batch
        if e.event_type == EVENT_TYPE_SAFETY_STATE_TRANSITION
    ]

    # Each unique transition_id must appear at most once across both channels
    all_transition_ids = [e.event_id for e in streaming_transitions] + [
        e.event_id for e in batched_transitions
    ]
    assert len(all_transition_ids) == len(set(all_transition_ids)), (
        "Same transition emitted in both streaming write_event() and finalization write_events()"
    )


def test_streaming_mode_run_summary_always_at_finalization(tmp_path: Path) -> None:
    """RunSummaryEvent is always present in the finalization write_events() batch."""
    spy = _SpySink()
    market = _make_mock_market()
    gamma = _make_gamma_client([market])
    clob = _make_clob_client(
        {
            "btc-5m-up-yes": (None, 0.47),
            "btc-5m-up-no": (None, 0.48),
        }
    )

    settings = build_runner_settings(
        artifact_base_dir=tmp_path,
        duration_seconds=0,
        cycle_limit=1,
        config_payload={"sink_flush_mode": "streaming"},
    )
    runner = CryptoPairPaperRunner(
        settings,
        gamma_client=gamma,
        clob_client=clob,
        reference_feed=StaticFeed(_fresh_snapshot()),
        sink=spy,
        sleep_fn=lambda _: None,
    )
    runner.run()

    assert len(spy.write_events_calls) == 1
    finalization_batch = spy.write_events_calls[0]
    run_summary_events = [
        e for e in finalization_batch if e.event_type == EVENT_TYPE_RUN_SUMMARY
    ]
    assert len(run_summary_events) == 1, (
        f"Expected exactly 1 RunSummaryEvent in finalization batch, "
        f"got {len(run_summary_events)}"
    )


def test_write_event_disabled_sink_noop() -> None:
    """DisabledCryptoPairClickHouseSink.write_event() returns enabled=False, skipped."""
    from packages.polymarket.crypto_pairs.event_models import OpportunityObservedEvent

    sink = DisabledCryptoPairClickHouseSink()
    obs = _make_paper_obs()
    evt = OpportunityObservedEvent.from_observation(obs, mode="paper")
    result = sink.write_event(evt)

    assert result.enabled is False
    assert result.written_rows == 0
    assert result.skipped_reason == "disabled"
    assert result.attempted_events == 1


def test_write_event_enabled_sink_delegates() -> None:
    """CryptoPairClickHouseSink.write_event() calls insert_rows exactly once with 1 row."""
    from packages.polymarket.crypto_pairs.event_models import OpportunityObservedEvent

    insert_calls: list = []

    class _TrackingClient:
        def insert_rows(self, table, columns, rows):
            insert_calls.append((table, columns, rows))
            return len(rows)

    obs = _make_paper_obs()
    evt = OpportunityObservedEvent.from_observation(obs, mode="paper")

    config = CryptoPairClickHouseSinkConfig(enabled=True)
    sink = CryptoPairClickHouseSink(config, client=_TrackingClient())
    result = sink.write_event(evt)

    assert result.enabled is True
    assert result.written_rows == 1
    assert len(insert_calls) == 1
    _, _, rows = insert_calls[0]
    assert len(rows) == 1
