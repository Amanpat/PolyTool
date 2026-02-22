"""Offline unit tests for CLV cache-first closing price resolution."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

import requests

from packages.polymarket.clv import (
    MISSING_REASON_AUTH_MISSING,
    MISSING_REASON_CONNECTIVITY,
    MISSING_REASON_EMPTY_HISTORY,
    MISSING_REASON_HTTP_ERROR,
    MISSING_REASON_INVALID_TIME_ORDER_ENTRY_AFTER_CLOSE,
    MISSING_REASON_NO_CLOSE_TS,
    MISSING_REASON_NO_PRICE_1H_BEFORE_ENTRY_IN_WINDOW,
    MISSING_REASON_NO_PRICE_IN_LOOKBACK_WINDOW,
    MISSING_REASON_NO_PRIOR_PRICE_BEFORE_ENTRY,
    MISSING_REASON_NO_PRE_EVENT_CLOSE_TS,
    MISSING_REASON_NO_SETTLEMENT_CLOSE_TS,
    MISSING_REASON_OFFLINE,
    MISSING_REASON_OUTSIDE_WINDOW,
    MISSING_REASON_RATE_LIMITED,
    MISSING_REASON_TIMEOUT,
    MISSING_REASON_INVALID_PRICE_VALUE,
    MISSING_REASON_MISSING_ENTRY_TS,
    build_cache_lookup_sql,
    classify_movement_direction,
    enrich_position_with_clv,
    enrich_position_with_dual_clv,
    format_prices_history_error_detail,
    normalize_prices_fidelity_minutes,
    resolve_close_ts_settlement,
    resolve_close_ts_pre_event,
    resolve_entry_price_context,
    resolve_closing_price,
    select_last_price_le_anchor,
    select_last_price_le_close,
    warm_clv_snapshot_cache,
    PricePoint,
)


@dataclass
class _QueryResult:
    result_rows: list[tuple]


class _FakeClickHouse:
    def __init__(self, rows: list[tuple] | None = None):
        self.rows = rows or []
        self.queries: list[str] = []
        self.inserts: list[tuple[str, list[tuple], tuple[str, ...] | None]] = []

    def query(self, query: str, parameters=None):
        self.queries.append(query)
        return _QueryResult(result_rows=list(self.rows))

    def insert(self, table, rows, column_names=None):
        self.inserts.append((table, list(rows), tuple(column_names) if column_names else None))


class _FakeClob:
    def __init__(self, payload):
        self.payload = payload
        self.calls = 0

    def get_prices_history(self, **kwargs):
        self.calls += 1
        return self.payload


class _RaiseClob:
    def __init__(self, exc: Exception):
        self.exc = exc
        self.calls = 0

    def get_prices_history(self, **kwargs):
        self.calls += 1
        raise self.exc


class _RouteClob:
    def __init__(self, routes: dict[str, object]):
        self.routes = routes
        self.calls = 0

    def get_prices_history(self, **kwargs):
        self.calls += 1
        token_id = str(kwargs.get("token_id") or "")
        action = self.routes[token_id]
        if isinstance(action, Exception):
            raise action
        return action


def _http_error(status: int, body: str = "") -> requests.exceptions.HTTPError:
    response = requests.Response()
    response.status_code = int(status)
    response.url = "https://clob.polymarket.com/prices-history"
    response._content = body.encode("utf-8")
    response.encoding = "utf-8"
    return requests.exceptions.HTTPError(f"HTTP {status}", response=response)


def _utc(*, day: int, hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 2, day, hour, minute, tzinfo=timezone.utc)


def test_select_last_price_le_close_within_window():
    close_ts = _utc(day=19, hour=12, minute=0)
    points = [
        PricePoint("tok", _utc(day=19, hour=10), 0.40),
        PricePoint("tok", _utc(day=19, hour=11, minute=20), 0.47),
        PricePoint("tok", _utc(day=19, hour=11, minute=50), 0.49),
        PricePoint("tok", _utc(day=19, hour=12, minute=5), 0.55),  # after close, excluded
    ]
    chosen = select_last_price_le_close(points, close_ts, closing_window_seconds=3 * 60 * 60)
    assert chosen is not None
    assert chosen.ts_observed == _utc(day=19, hour=11, minute=50)
    assert chosen.price == 0.49


def test_resolve_closing_price_missing_reason_no_close_ts():
    resolved = resolve_closing_price(
        token_id="tok",
        close_ts=None,
        clickhouse_client=_FakeClickHouse(),
        allow_online=False,
    )
    assert resolved.reason_if_missing == MISSING_REASON_NO_CLOSE_TS


def test_resolve_closing_price_missing_reason_offline():
    resolved = resolve_closing_price(
        token_id="tok",
        close_ts=_utc(day=19, hour=12),
        clickhouse_client=_FakeClickHouse(rows=[]),
        allow_online=False,
    )
    assert resolved.reason_if_missing == MISSING_REASON_OFFLINE


def test_resolve_closing_price_missing_reason_auth_missing_when_client_unavailable():
    resolved = resolve_closing_price(
        token_id="tok",
        close_ts=_utc(day=19, hour=12),
        clickhouse_client=_FakeClickHouse(rows=[]),
        clob_client=None,
        allow_online=True,
    )
    assert resolved.reason_if_missing == MISSING_REASON_AUTH_MISSING


def test_resolve_closing_price_missing_reason_connectivity():
    clob = _RaiseClob(requests.exceptions.ConnectionError("dns lookup failed"))
    resolved = resolve_closing_price(
        token_id="tok",
        close_ts=_utc(day=19, hour=12),
        clickhouse_client=_FakeClickHouse(rows=[]),
        clob_client=clob,
        allow_online=True,
    )
    assert resolved.reason_if_missing == MISSING_REASON_CONNECTIVITY


def test_resolve_closing_price_missing_reason_rate_limited():
    clob = _RaiseClob(_http_error(429))
    resolved = resolve_closing_price(
        token_id="tok",
        close_ts=_utc(day=19, hour=12),
        clickhouse_client=_FakeClickHouse(rows=[]),
        clob_client=clob,
        allow_online=True,
    )
    assert resolved.reason_if_missing == MISSING_REASON_RATE_LIMITED


def test_resolve_closing_price_missing_reason_http_error():
    clob = _RaiseClob(_http_error(503))
    resolved = resolve_closing_price(
        token_id="tok",
        close_ts=_utc(day=19, hour=12),
        clickhouse_client=_FakeClickHouse(rows=[]),
        clob_client=clob,
        allow_online=True,
    )
    assert resolved.reason_if_missing == MISSING_REASON_HTTP_ERROR


def test_resolve_closing_price_http_error_includes_status_and_body_detail():
    clob = _RaiseClob(_http_error(400, body='{"error":"invalid query params"}'))
    resolved = resolve_closing_price(
        token_id="tok",
        close_ts=_utc(day=19, hour=12),
        clickhouse_client=_FakeClickHouse(rows=[]),
        clob_client=clob,
        allow_online=True,
    )
    assert resolved.reason_if_missing == MISSING_REASON_HTTP_ERROR
    assert resolved.error_detail is not None
    assert "status=400" in resolved.error_detail
    assert "invalid query params" in resolved.error_detail


def test_normalize_prices_fidelity_minutes_supports_legacy_and_numeric_values():
    assert normalize_prices_fidelity_minutes("high") == 1
    assert normalize_prices_fidelity_minutes("medium") == 5
    assert normalize_prices_fidelity_minutes("low") == 60
    assert normalize_prices_fidelity_minutes("1") == 1
    assert normalize_prices_fidelity_minutes("5m") == 5
    assert normalize_prices_fidelity_minutes(60) == 60


def test_format_prices_history_error_detail_for_non_http_error():
    detail = format_prices_history_error_detail(requests.exceptions.Timeout("read timed out"))
    assert "timed out" in detail


def test_resolve_closing_price_missing_reason_timeout():
    clob = _RaiseClob(requests.exceptions.Timeout("read timed out"))
    resolved = resolve_closing_price(
        token_id="tok",
        close_ts=_utc(day=19, hour=12),
        clickhouse_client=_FakeClickHouse(rows=[]),
        clob_client=clob,
        allow_online=True,
    )
    assert resolved.reason_if_missing == MISSING_REASON_TIMEOUT


def test_resolve_closing_price_missing_reason_empty_history():
    clob = _FakeClob(payload={"history": []})
    resolved = resolve_closing_price(
        token_id="tok",
        close_ts=_utc(day=19, hour=12),
        clickhouse_client=_FakeClickHouse(rows=[]),
        clob_client=clob,
        allow_online=True,
    )
    assert clob.calls == 1
    assert resolved.reason_if_missing == MISSING_REASON_EMPTY_HISTORY


def test_resolve_closing_price_missing_reason_outside_window():
    close_ts = _utc(day=19, hour=12)
    clob = _FakeClob(
        payload={
            "history": [
                # Too old for the 2h window.
                {"t": int((_utc(day=19, hour=8)).timestamp()), "p": 0.31},
                # After close_ts, also excluded.
                {"t": int((_utc(day=19, hour=13)).timestamp()), "p": 0.35},
            ]
        }
    )
    resolved = resolve_closing_price(
        token_id="tok",
        close_ts=close_ts,
        clickhouse_client=_FakeClickHouse(rows=[]),
        clob_client=clob,
        allow_online=True,
        closing_window_seconds=2 * 60 * 60,
    )
    assert resolved.reason_if_missing == MISSING_REASON_OUTSIDE_WINDOW


def test_cache_first_uses_cached_snapshot_without_client_call():
    close_ts = _utc(day=19, hour=12)
    cached_rows = [
        (_utc(day=19, hour=11, minute=55), 0.44),
        (_utc(day=19, hour=11, minute=20), 0.41),
    ]
    clickhouse = _FakeClickHouse(rows=cached_rows)
    clob = _FakeClob(payload={"history": [{"t": int(close_ts.timestamp()), "p": 0.99}]})

    resolved = resolve_closing_price(
        token_id="tok",
        close_ts=close_ts,
        clickhouse_client=clickhouse,
        clob_client=clob,
        allow_online=True,
        closing_window_seconds=24 * 60 * 60,
    )
    assert resolved.reason_if_missing is None
    assert resolved.closing_price == 0.44
    assert clob.calls == 0


def test_cache_lookup_sql_contract_includes_clv_snapshot_columns():
    sql = build_cache_lookup_sql()
    assert "SELECT" in sql
    assert "ts_observed" in sql
    assert "price" in sql
    assert "FROM polyttool.market_price_snapshots" in sql
    assert "token_id = {token_id:String}" in sql
    assert "close_ts = {close_ts:DateTime64(3)}" in sql
    assert "query_window_seconds = {query_window_seconds:UInt32}" in sql


def test_warm_clv_snapshot_cache_writes_rows_and_counts_success():
    positions = [
        {
            "resolved_token_id": "tok-warm",
            "entry_price": 0.42,
            "resolved_at": "2026-02-19T12:00:00Z",
        }
    ]
    clickhouse = _FakeClickHouse(rows=[])
    clob = _FakeClob(payload={"history": [{"t": int(_utc(day=19, hour=11, minute=58).timestamp()), "p": 0.55}]})

    summary = warm_clv_snapshot_cache(
        positions,
        clickhouse_client=clickhouse,
        clob_client=clob,
        allow_online=True,
    )

    assert summary["attempted"] == 1
    assert summary["succeeded"] == 1
    assert summary["failed"] == 0
    assert summary["cache_hit_count"] == 0
    assert summary["fetched_count"] == 1
    assert summary["succeeded_positions_count"] == 1
    assert summary["failed_positions_count"] == 0
    assert summary["inserted_rows_count"] == 1
    assert len(clickhouse.inserts) == 1


def test_warm_clv_snapshot_cache_failure_reason_breakdown():
    positions = [
        {
            "resolved_token_id": "tok-timeout",
            "entry_price": 0.42,
            "resolved_at": "2026-02-19T12:00:00Z",
        },
        {
            "resolved_token_id": "tok-rate",
            "entry_price": 0.44,
            "resolved_at": "2026-02-19T12:00:00Z",
        },
    ]
    clob = _RouteClob(
        {
            "tok-timeout": requests.exceptions.Timeout("timed out"),
            "tok-rate": _http_error(429),
        }
    )

    summary = warm_clv_snapshot_cache(
        positions,
        clickhouse_client=_FakeClickHouse(rows=[]),
        clob_client=clob,
        allow_online=True,
    )

    assert summary["attempted"] == 2
    assert summary["failed"] == 2
    assert summary["failure_reason_counts"] == {
        MISSING_REASON_RATE_LIMITED: 1,
        MISSING_REASON_TIMEOUT: 1,
    }


def test_warm_clv_snapshot_cache_counts_cache_hit_as_success_without_fetch():
    positions = [
        {
            "resolved_token_id": "tok-cached",
            "entry_price": 0.42,
            "resolved_at": "2026-02-19T12:00:00Z",
        }
    ]
    clickhouse = _FakeClickHouse(
        rows=[(_utc(day=19, hour=11, minute=58), 0.51)]
    )
    clob = _FakeClob(payload={"history": [{"t": int(_utc(day=19, hour=11, minute=57).timestamp()), "p": 0.50}]})
    summary = warm_clv_snapshot_cache(
        positions,
        clickhouse_client=clickhouse,
        clob_client=clob,
        allow_online=True,
    )
    assert clob.calls == 0
    assert summary["cache_hit_count"] == 1
    assert summary["fetched_count"] == 0
    assert summary["succeeded_positions_count"] == 1
    assert summary["failed_positions_count"] == 0


def test_warm_clv_snapshot_cache_fetch_noop_insert_still_counts_success():
    class _NoopInsertClickHouse(_FakeClickHouse):
        def insert(self, table, rows, column_names=None):
            # Simulates duplicate no-op write accepted by backend.
            super().insert(table, rows, column_names=column_names)
            return 0

    positions = [
        {
            "resolved_token_id": "tok-dup-noop",
            "entry_price": 0.42,
            "resolved_at": "2026-02-19T12:00:00Z",
        }
    ]
    clickhouse = _NoopInsertClickHouse(rows=[])
    clob = _FakeClob(
        payload={
            "history": [
                {"t": int(_utc(day=19, hour=11, minute=58).timestamp()), "p": 0.51},
                {"t": int(_utc(day=19, hour=11, minute=57).timestamp()), "p": 0.50},
            ]
        }
    )

    summary = warm_clv_snapshot_cache(
        positions,
        clickhouse_client=clickhouse,
        clob_client=clob,
        allow_online=True,
    )

    assert clob.calls == 1
    assert summary["fetched_count"] == 1
    assert summary["inserted_rows_count"] == 0
    assert summary["succeeded_positions_count"] == 1
    assert summary["failed_positions_count"] == 0
    assert summary["failure_reason_counts"] == {}


def test_warm_clv_snapshot_cache_http_error_records_failure_sample():
    positions = [
        {
            "resolved_token_id": "tok-http",
            "entry_price": 0.40,
            "resolved_at": "2026-02-19T12:00:00Z",
        }
    ]
    clob = _RaiseClob(_http_error(503, body='{"error":"backend unavailable"}'))
    summary = warm_clv_snapshot_cache(
        positions,
        clickhouse_client=_FakeClickHouse(rows=[]),
        clob_client=clob,
        allow_online=True,
    )
    assert summary["failed_positions_count"] == 1
    assert summary["failure_reason_counts"] == {MISSING_REASON_HTTP_ERROR: 1}
    assert len(summary["failure_samples"]) == 1
    sample = summary["failure_samples"][0]
    assert sample["token_id"] == "tok-http"
    assert sample["reason"] == MISSING_REASON_HTTP_ERROR
    assert "status=503" in sample["error_detail"]


def test_enrich_position_with_clv_uses_gamma_closed_time_when_onchain_missing():
    position = {
        "resolved_token_id": "tok-gamma-close",
        "entry_price": 0.42,
        "resolved_at": None,
        "gamma_closedTime": "2026-02-19T12:00:00Z",
    }

    enriched = enrich_position_with_clv(
        position,
        clickhouse_client=_FakeClickHouse(rows=[]),
        clob_client=_FakeClob(payload={"history": [{"t": int(_utc(day=19, hour=11, minute=58).timestamp()), "p": 0.47}]}),
        allow_online=True,
    )

    assert enriched["close_ts"] == "2026-02-19T12:00:00+00:00"
    assert enriched["close_ts_source"] == "gamma_closedTime"
    assert enriched["clv_missing_reason"] is None


def test_enrich_position_with_clv_populates_close_ts_explainability_when_missing():
    position = {
        "resolved_token_id": "tok-no-close",
        "entry_price": 0.55,
    }

    enriched = enrich_position_with_clv(
        position,
        clickhouse_client=_FakeClickHouse(rows=[]),
        clob_client=None,
        allow_online=True,
    )

    assert enriched["close_ts"] is None
    assert enriched["close_ts_source"] is None
    assert enriched["close_ts_attempted_sources"] == [
        "onchain_resolved_at",
        "gamma_closedTime",
        "gamma_endDate",
        "gamma_umaEndDate",
    ]
    assert enriched["close_ts_failure_reason"] == "MISSING_CLOSE_TS_FIELDS"
    assert enriched["clv_missing_reason"] == MISSING_REASON_NO_CLOSE_TS


def test_invalid_fetched_prices_set_invalid_price_reason():
    clob = _FakeClob(
        payload={"history": [{"t": int(_utc(day=19, hour=11, minute=50).timestamp()), "p": 1.7}]}
    )
    resolved = resolve_closing_price(
        token_id="tok-invalid",
        close_ts=_utc(day=19, hour=12),
        clickhouse_client=_FakeClickHouse(rows=[]),
        clob_client=clob,
        allow_online=True,
        closing_window_seconds=2 * 60 * 60,
    )
    assert resolved.reason_if_missing == MISSING_REASON_INVALID_PRICE_VALUE


def test_select_last_price_le_anchor_within_window():
    anchor = _utc(day=19, hour=11, minute=0)
    points = [
        PricePoint("tok", _utc(day=19, hour=9, minute=58), 0.22),  # before window
        PricePoint("tok", _utc(day=19, hour=10, minute=15), 0.31),
        PricePoint("tok", _utc(day=19, hour=10, minute=59), 0.36),
        PricePoint("tok", _utc(day=19, hour=11, minute=5), 0.42),  # after anchor
    ]
    chosen = select_last_price_le_anchor(
        points,
        window_start=_utc(day=19, hour=10, minute=0),
        anchor_ts=anchor,
    )
    assert chosen is not None
    assert chosen.ts_observed == _utc(day=19, hour=10, minute=59)
    assert chosen.price == 0.36


def test_classify_movement_direction_values():
    assert classify_movement_direction(0.40, 0.45) == "up"
    assert classify_movement_direction(0.40, 0.35) == "down"
    assert classify_movement_direction(0.40, 0.40) == "flat"


def test_resolve_entry_price_context_selectors_choose_nearest_prior_points():
    entry_ts = _utc(day=19, hour=12, minute=0)
    close_ts = _utc(day=19, hour=13, minute=0)
    cached_rows = [
        (_utc(day=19, hour=10, minute=1), 0.21),
        (_utc(day=19, hour=10, minute=58), 0.33),
        (_utc(day=19, hour=11, minute=30), 0.39),
        (_utc(day=19, hour=11, minute=59), 0.44),
    ]
    context = resolve_entry_price_context(
        token_id="tok-entry",
        entry_ts=entry_ts,
        close_ts=close_ts,
        clickhouse_client=_FakeClickHouse(rows=cached_rows),
        clob_client=_FakeClob(payload={"history": []}),
        allow_online=True,
        core_window_seconds=2 * 60 * 60,
        open_window_seconds=2 * 60 * 60,
    )
    assert context.open_price == 0.21
    assert context.price_1h_before_entry == 0.33
    assert context.price_at_entry == 0.44
    assert context.movement_direction == "up"
    assert context.minutes_to_close == 60


def test_entry_context_cache_first_avoids_client_call_when_cached():
    position = {
        "resolved_token_id": "tok-entry-cache",
        "entry_price": 0.45,
        "entry_ts": "2026-02-19T12:00:00Z",
        # No close_ts on purpose: isolates entry-context path.
    }
    cached_rows = [
        (_utc(day=19, hour=10, minute=5), 0.30),
        (_utc(day=19, hour=10, minute=59), 0.32),
        (_utc(day=19, hour=11, minute=55), 0.38),
    ]
    clob = _FakeClob(payload={"history": [{"t": int(_utc(day=19, hour=11, minute=50).timestamp()), "p": 0.99}]})
    enriched = enrich_position_with_clv(
        position,
        clickhouse_client=_FakeClickHouse(rows=cached_rows),
        clob_client=clob,
        allow_online=True,
    )
    assert clob.calls == 0
    assert enriched["price_at_entry"] == 0.38
    assert enriched["clv_missing_reason"] == MISSING_REASON_NO_CLOSE_TS


def test_entry_context_missing_reason_codes_for_missing_entry_ts():
    position = {
        "resolved_token_id": "tok-no-entry-ts",
        "entry_price": 0.44,
        "resolved_at": "2026-02-19T13:00:00Z",
    }
    enriched = enrich_position_with_clv(
        position,
        clickhouse_client=_FakeClickHouse(rows=[]),
        clob_client=None,
        allow_online=False,
    )
    assert enriched["open_price"] is None
    assert enriched["open_price_missing_reason"] == MISSING_REASON_MISSING_ENTRY_TS
    assert enriched["price_1h_before_entry"] is None
    assert (
        enriched["price_1h_before_entry_missing_reason"]
        == MISSING_REASON_MISSING_ENTRY_TS
    )
    assert enriched["price_at_entry"] is None
    assert enriched["price_at_entry_missing_reason"] == MISSING_REASON_MISSING_ENTRY_TS
    assert enriched["movement_direction"] is None
    assert enriched["movement_direction_missing_reason"] == MISSING_REASON_MISSING_ENTRY_TS
    assert enriched["minutes_to_close"] is None
    assert enriched["minutes_to_close_missing_reason"] == MISSING_REASON_MISSING_ENTRY_TS


def test_entry_context_missing_reason_code_when_1h_anchor_missing():
    position = {
        "resolved_token_id": "tok-anchor-gap",
        "entry_price": 0.41,
        "entry_ts": "2026-02-19T12:00:00Z",
        "resolved_at": "2026-02-19T14:00:00Z",
    }
    cached_rows = [
        (_utc(day=19, hour=11, minute=25), 0.47),
        (_utc(day=19, hour=11, minute=50), 0.49),
    ]
    enriched = enrich_position_with_clv(
        position,
        clickhouse_client=_FakeClickHouse(rows=cached_rows),
        clob_client=None,
        allow_online=False,
    )
    assert enriched["price_at_entry"] == 0.49
    assert enriched["price_1h_before_entry"] is None
    assert (
        enriched["price_1h_before_entry_missing_reason"]
        == MISSING_REASON_NO_PRICE_1H_BEFORE_ENTRY_IN_WINDOW
    )
    assert enriched["movement_direction"] is None
    assert (
        enriched["movement_direction_missing_reason"]
        == MISSING_REASON_NO_PRICE_1H_BEFORE_ENTRY_IN_WINDOW
    )


def test_entry_context_minutes_to_close_reason_when_entry_after_close():
    position = {
        "resolved_token_id": "tok-invalid-order",
        "entry_price": 0.39,
        "entry_ts": "2026-02-19T12:30:00Z",
        "resolved_at": "2026-02-19T12:00:00Z",
    }
    enriched = enrich_position_with_clv(
        position,
        clickhouse_client=_FakeClickHouse(rows=[]),
        clob_client=None,
        allow_online=False,
    )
    assert enriched["minutes_to_close"] is None
    assert (
        enriched["minutes_to_close_missing_reason"]
        == MISSING_REASON_INVALID_TIME_ORDER_ENTRY_AFTER_CLOSE
    )


# ---------------------------------------------------------------------------
# Dual CLV variant tests
# ---------------------------------------------------------------------------


def test_resolve_close_ts_settlement_uses_only_onchain_resolved_at():
    """Settlement resolver should return resolved_at, not closedTime."""
    position = {
        "resolved_at": "2026-02-19T12:00:00Z",
        "closedTime": "2026-02-18T20:00:00Z",
    }
    ts, source = resolve_close_ts_settlement(position)
    assert ts is not None
    assert source == "onchain_resolved_at"
    assert ts.hour == 12  # from resolved_at, not closedTime hour 20


def test_resolve_close_ts_settlement_missing_when_no_onchain():
    """Settlement resolver returns None when only closedTime is available."""
    position = {
        "resolved_at": None,
        "closedTime": "2026-02-18T20:00:00Z",
    }
    ts, source = resolve_close_ts_settlement(position)
    assert ts is None
    assert source is None


def test_resolve_close_ts_pre_event_skips_onchain_resolved_at():
    """Pre-event resolver returns closedTime, not resolved_at."""
    position = {
        "resolved_at": "2026-02-19T12:00:00Z",  # should be ignored
        "closedTime": "2026-02-18T20:00:00Z",
    }
    ts, source = resolve_close_ts_pre_event(position)
    assert ts is not None
    assert source == "gamma_closedTime"
    assert ts.hour == 20  # from closedTime


def test_resolve_close_ts_pre_event_ladder_fallback():
    """Pre-event resolver falls back to endDate when closedTime is missing."""
    position = {
        "resolved_at": "2026-02-19T12:00:00Z",
        "endDate": "2026-02-17T18:00:00Z",
    }
    ts, source = resolve_close_ts_pre_event(position)
    assert ts is not None
    assert source == "gamma_endDate"
    assert ts.day == 17


def test_enrich_position_with_dual_clv_both_variants_present():
    """Both settlement and pre_event variants populate all 12 fields when both timestamps exist."""
    position = {
        "resolved_token_id": "tok-dual-both",
        "entry_price": 0.42,
        "entry_ts": "2026-02-18T10:00:00Z",
        "resolved_at": "2026-02-19T12:00:00Z",
        "closedTime": "2026-02-19T11:00:00Z",
    }
    close_ts_epoch = int(_utc(day=19, hour=11, minute=0).timestamp())
    fake_price_row = {"t": close_ts_epoch, "p": 0.55}
    clob = _FakeClob(payload={"history": [fake_price_row]})

    # CH cache misses so it falls to clob
    enriched = enrich_position_with_dual_clv(
        position,
        clickhouse_client=_FakeClickHouse(rows=[]),
        clob_client=clob,
        allow_online=True,
    )

    # Both variant CLV fields should be set
    assert enriched.get("clv_pct_settlement") is not None
    assert enriched.get("clv_pct_pre_event") is not None
    assert enriched.get("closing_price_settlement") is not None
    assert enriched.get("closing_price_pre_event") is not None
    assert enriched.get("beat_close_settlement") is not None
    assert enriched.get("beat_close_pre_event") is not None
    assert enriched.get("clv_source_settlement") is not None
    assert enriched.get("clv_source_pre_event") is not None
    assert enriched.get("clv_missing_reason_settlement") is None
    assert enriched.get("clv_missing_reason_pre_event") is None


def test_enrich_position_with_dual_clv_settlement_missing_pre_event_present():
    """When no resolved_at, settlement is missing but pre_event is populated."""
    position = {
        "resolved_token_id": "tok-dual-pre-only",
        "entry_price": 0.40,
        "entry_ts": "2026-02-18T10:00:00Z",
        "resolved_at": None,
        "closedTime": "2026-02-19T11:00:00Z",
    }
    close_ts_epoch = int(_utc(day=19, hour=11, minute=0).timestamp())
    clob = _FakeClob(payload={"history": [{"t": close_ts_epoch, "p": 0.52}]})

    enriched = enrich_position_with_dual_clv(
        position,
        clickhouse_client=_FakeClickHouse(rows=[]),
        clob_client=clob,
        allow_online=True,
    )

    # Settlement variant must be missing
    assert enriched.get("clv_pct_settlement") is None
    assert enriched.get("clv_missing_reason_settlement") == MISSING_REASON_NO_SETTLEMENT_CLOSE_TS

    # Pre-event variant should be populated
    assert enriched.get("clv_pct_pre_event") is not None
    assert enriched.get("clv_missing_reason_pre_event") is None


def test_enrich_position_with_dual_clv_preserves_existing_clv_fields():
    """Dual enrichment does not remove existing base CLV fields."""
    position = {
        "resolved_token_id": "tok-dual-preserve",
        "entry_price": 0.45,
        "entry_ts": "2026-02-18T10:00:00Z",
        "resolved_at": "2026-02-19T12:00:00Z",
    }
    enriched = enrich_position_with_dual_clv(
        position,
        clickhouse_client=_FakeClickHouse(rows=[]),
        clob_client=None,
        allow_online=False,
    )

    # Base fields must still be present
    assert "clv" in enriched
    assert "clv_pct" in enriched
    assert "beat_close" in enriched
    assert "close_ts" in enriched
    assert "close_ts_source" in enriched
    assert "clv_missing_reason" in enriched
    # Variant fields must be present too
    assert "clv_pct_settlement" in enriched
    assert "clv_pct_pre_event" in enriched
