"""Offline unit tests for CLOB prices-history request parameter shaping."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from packages.polymarket.clob import ClobClient


class _CaptureHttpClient:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def get_json(self, path, params=None, headers=None):
        self.calls.append({"path": path, "params": dict(params or {}), "headers": headers})
        return {"ok": True}


def _utc(*, day: int, hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 2, day, hour, minute, tzinfo=timezone.utc)


def test_get_prices_history_bounded_window_uses_market_key_and_omits_interval():
    clob = ClobClient()
    capture = _CaptureHttpClient()
    clob.client = capture

    clob.get_prices_history(
        token_id="tok-123",
        start_ts=_utc(day=19, hour=11, minute=50),
        end_ts=_utc(day=19, hour=12, minute=0),
        interval="1m",
        fidelity="high",
    )

    assert len(capture.calls) == 1
    params = capture.calls[0]["params"]
    assert params["market"] == "tok-123"
    assert "token_id" not in params
    assert "interval" not in params
    assert "startTs" in params
    assert "endTs" in params
    assert params["fidelity"] == 1
    assert isinstance(params["fidelity"], int)


def test_get_prices_history_unbounded_request_can_use_interval_with_numeric_fidelity():
    clob = ClobClient()
    capture = _CaptureHttpClient()
    clob.client = capture

    clob.get_prices_history(
        token_id="tok-456",
        interval="1h",
        fidelity="5",
    )

    params = capture.calls[0]["params"]
    assert params["market"] == "tok-456"
    assert params["interval"] == "1h"
    assert params["fidelity"] == 5
    assert "startTs" not in params
    assert "endTs" not in params


def test_get_prices_history_rejects_half_bounded_window():
    clob = ClobClient()
    capture = _CaptureHttpClient()
    clob.client = capture

    with pytest.raises(ValueError):
        clob.get_prices_history(
            token_id="tok-789",
            start_ts=_utc(day=19, hour=11, minute=50),
            end_ts=None,
            fidelity=1,
        )
