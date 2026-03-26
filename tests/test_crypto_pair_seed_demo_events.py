from __future__ import annotations

from datetime import datetime, timezone

from packages.polymarket.crypto_pairs.clickhouse_sink import (
    ClickHouseWriteResult,
    CryptoPairClickHouseSinkConfig,
)
from packages.polymarket.crypto_pairs.dev_seed import (
    DEMO_RUN_ID_PREFIX,
    DEMO_SEED_SOURCE,
    DEMO_STOPPED_REASON,
    DEMO_SYNTHETIC_ASSUMPTIONS,
    build_demo_seed_batch,
)
from packages.polymarket.crypto_pairs.event_models import (
    EVENT_TYPE_INTENT_GENERATED,
    EVENT_TYPE_OPPORTUNITY_OBSERVED,
    EVENT_TYPE_PAIR_SETTLEMENT_COMPLETED,
    EVENT_TYPE_PARTIAL_EXPOSURE_UPDATED,
    EVENT_TYPE_RUN_SUMMARY,
    EVENT_TYPE_SAFETY_STATE_TRANSITION,
    EVENT_TYPE_SIMULATED_FILL_RECORDED,
    serialize_events,
)
from tools.cli.crypto_pair_seed_demo_events import (
    main,
    run_crypto_pair_seed_demo_events,
)


def test_build_demo_seed_batch_matches_dashboard_contract_and_is_synthetic() -> None:
    batch = build_demo_seed_batch(
        started_at=datetime(2026, 3, 25, 22, 0, tzinfo=timezone.utc)
    )
    serialized = serialize_events(batch.events)

    assert batch.run_id.startswith(DEMO_RUN_ID_PREFIX)
    assert batch.source == DEMO_SEED_SOURCE
    assert batch.event_count == 12
    assert batch.event_types == (
        EVENT_TYPE_OPPORTUNITY_OBSERVED,
        EVENT_TYPE_INTENT_GENERATED,
        EVENT_TYPE_SIMULATED_FILL_RECORDED,
        EVENT_TYPE_PARTIAL_EXPOSURE_UPDATED,
        EVENT_TYPE_PAIR_SETTLEMENT_COMPLETED,
        EVENT_TYPE_SAFETY_STATE_TRANSITION,
        EVENT_TYPE_RUN_SUMMARY,
    )
    assert all(event["mode"] == "paper" for event in serialized)
    assert all(event["source"] == DEMO_SEED_SOURCE for event in serialized)
    assert all(event["run_id"] == batch.run_id for event in serialized)
    assert all(
        "synthetic-demo" in event["market_id"] or event["event_type"] == EVENT_TYPE_RUN_SUMMARY
        for event in serialized
    )
    assert any(
        event["event_type"] == EVENT_TYPE_OPPORTUNITY_OBSERVED
        and tuple(event["assumptions"]) == DEMO_SYNTHETIC_ASSUMPTIONS
        for event in serialized
    )
    assert any(
        event["event_type"] == EVENT_TYPE_PARTIAL_EXPOSURE_UPDATED
        and event["exposure_status"] == "paired"
        for event in serialized
    )
    assert any(
        event["event_type"] == EVENT_TYPE_PARTIAL_EXPOSURE_UPDATED
        and event["exposure_status"] == "partial_yes"
        for event in serialized
    )
    assert any(
        event["event_type"] == EVENT_TYPE_SAFETY_STATE_TRANSITION
        and event["reason"] == "synthetic_demo_disconnect_for_dashboard_validation"
        for event in serialized
    )
    assert any(
        event["event_type"] == EVENT_TYPE_RUN_SUMMARY
        and event["stopped_reason"] == DEMO_STOPPED_REASON
        for event in serialized
    )
    assert (
        batch.cleanup_sql
        == "ALTER TABLE polytool.crypto_pair_events DELETE "
        f"WHERE run_id = '{batch.run_id}' AND source = '{DEMO_SEED_SOURCE}'"
    )


def test_run_crypto_pair_seed_demo_events_builds_enabled_sink_and_writes_events() -> None:
    captured: dict[str, object] = {}

    class _Writer:
        def __init__(self) -> None:
            self.events = []

        def write_events(self, events):
            self.events = list(events)
            return ClickHouseWriteResult(
                enabled=True,
                table_name="polytool.crypto_pair_events",
                attempted_events=len(self.events),
                written_rows=len(self.events),
            )

    writer = _Writer()

    def _writer_factory(config: CryptoPairClickHouseSinkConfig):
        captured["config"] = config
        captured["writer"] = writer
        return writer

    result = run_crypto_pair_seed_demo_events(
        clickhouse_host="clickhouse.local",
        clickhouse_port=9000,
        clickhouse_user="demo_user",
        clickhouse_password="demo_password",
        run_id="synthetic-demo-track2-explicit",
        started_at=datetime(2026, 3, 25, 22, 30, tzinfo=timezone.utc),
        writer_factory=_writer_factory,
    )

    assert captured["config"] == CryptoPairClickHouseSinkConfig(
        enabled=True,
        clickhouse_host="clickhouse.local",
        clickhouse_port=9000,
        clickhouse_user="demo_user",
        clickhouse_password="demo_password",
        soft_fail=False,
    )
    assert result["run_id"] == "synthetic-demo-track2-explicit"
    assert result["source"] == DEMO_SEED_SOURCE
    assert result["event_count"] == len(writer.events)
    assert result["write_result"]["written_rows"] == len(writer.events)
    assert all(event.source == DEMO_SEED_SOURCE for event in writer.events)


def test_main_rejects_missing_clickhouse_password(monkeypatch, capsys) -> None:
    monkeypatch.delenv("CLICKHOUSE_PASSWORD", raising=False)

    rc = main([])

    captured = capsys.readouterr()
    assert rc == 1
    assert "CLICKHOUSE_PASSWORD" in captured.err
