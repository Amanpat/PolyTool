from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest


def _patch_time(
    monkeypatch: pytest.MonkeyPatch,
    recorder_mod: Any,
    *,
    start: float = 1000.0,
    step: float = 0.01,
) -> None:
    clock = {"value": start}

    def _fake_time() -> float:
        clock["value"] += step
        return clock["value"]

    monkeypatch.setattr(recorder_mod.time, "time", _fake_time)


def test_recorder_sends_ping_on_timeout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import packages.polymarket.simtrader.tape.recorder as recorder_mod
    from packages.polymarket.simtrader.tape.recorder import TapeRecorder

    monkeypatch.setattr(recorder_mod.signal, "signal", lambda *_args, **_kwargs: None)
    _patch_time(monkeypatch, recorder_mod)

    class FakeTimeout(Exception):
        pass

    class FakeClosed(Exception):
        pass

    instances: list["FakeWebSocket"] = []

    class FakeWebSocket:
        def __init__(self) -> None:
            self.recv_calls = 0
            self.ping_calls = 0
            self.sent: list[str] = []
            self.timeout: float | None = None
            instances.append(self)

        def connect(self, _url: str) -> None:
            return None

        def settimeout(self, timeout: float) -> None:
            self.timeout = timeout

        def send(self, payload: str) -> None:
            self.sent.append(payload)

        def ping(self, _payload: str) -> None:
            self.ping_calls += 1

        def recv(self) -> str:
            self.recv_calls += 1
            if self.recv_calls == 1:
                raise FakeTimeout()
            if self.recv_calls == 2:
                return json.dumps(
                    {
                        "event_type": "book",
                        "asset_id": "asset-1",
                        "bids": [{"price": "0.40", "size": "100"}],
                        "asks": [{"price": "0.45", "size": "100"}],
                    }
                )
            raise FakeTimeout()

        def close(self) -> None:
            return None

    fake_ws_module = type(
        "FakeWebsocketModule",
        (),
        {
            "WebSocket": FakeWebSocket,
            "WebSocketTimeoutException": FakeTimeout,
            "WebSocketConnectionClosedException": FakeClosed,
        },
    )
    monkeypatch.setitem(sys.modules, "websocket", fake_ws_module)

    recorder = TapeRecorder(
        tape_dir=tmp_path / "tape_ping",
        asset_ids=["asset-1"],
        strict=True,
    )
    recorder.record(duration_seconds=0.15, ws_url="wss://unit-test")

    assert len(instances) == 1
    ws = instances[0]
    assert ws.timeout == 5.0
    assert ws.ping_calls >= 1
    assert ws.sent == [
        json.dumps(
            {
                "assets_ids": ["asset-1"],
                "type": "market",
                "custom_feature_enabled": True,
                "initial_dump": True,
            }
        )
    ]


def test_recorder_reconnects_and_resubscribes_on_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import packages.polymarket.simtrader.tape.recorder as recorder_mod
    from packages.polymarket.simtrader.tape.recorder import TapeRecorder

    monkeypatch.setattr(recorder_mod.signal, "signal", lambda *_args, **_kwargs: None)
    _patch_time(monkeypatch, recorder_mod)

    class FakeTimeout(Exception):
        pass

    class FakeClosed(Exception):
        pass

    instances: list["FakeWebSocket"] = []

    class FakeWebSocket:
        def __init__(self) -> None:
            self.idx = len(instances)
            self.recv_calls = 0
            self.sent: list[str] = []
            instances.append(self)

        def connect(self, _url: str) -> None:
            return None

        def settimeout(self, _timeout: float) -> None:
            return None

        def send(self, payload: str) -> None:
            self.sent.append(payload)

        def ping(self, _payload: str) -> None:
            return None

        def recv(self) -> str:
            self.recv_calls += 1
            if self.idx == 0:
                raise FakeClosed("closed by server")
            if self.idx == 1 and self.recv_calls == 1:
                return json.dumps(
                    {
                        "event_type": "book",
                        "asset_id": "asset-2",
                        "bids": [{"price": "0.41", "size": "100"}],
                        "asks": [{"price": "0.47", "size": "100"}],
                    }
                )
            raise FakeTimeout()

        def close(self) -> None:
            return None

    fake_ws_module = type(
        "FakeWebsocketModule",
        (),
        {
            "WebSocket": FakeWebSocket,
            "WebSocketTimeoutException": FakeTimeout,
            "WebSocketConnectionClosedException": FakeClosed,
        },
    )
    monkeypatch.setitem(sys.modules, "websocket", fake_ws_module)

    recorder = TapeRecorder(
        tape_dir=tmp_path / "tape_reconnect",
        asset_ids=["asset-2"],
        strict=True,
    )
    recorder.record(duration_seconds=0.20, ws_url="wss://unit-test")

    assert len(instances) >= 2
    subscribe_msg = json.dumps(
        {
            "assets_ids": ["asset-2"],
            "type": "market",
            "custom_feature_enabled": True,
            "initial_dump": True,
        }
    )
    assert subscribe_msg in instances[0].sent
    assert subscribe_msg in instances[1].sent

    meta = json.loads((tmp_path / "tape_reconnect" / "meta.json").read_text(encoding="utf-8"))
    assert meta["reconnect_count"] == 1
    assert any("WebSocket reconnect #1" in warning for warning in meta["warnings"])


def test_recorder_seq_is_monotonic_across_reconnects(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import packages.polymarket.simtrader.tape.recorder as recorder_mod
    from packages.polymarket.simtrader.tape.recorder import TapeRecorder

    monkeypatch.setattr(recorder_mod.signal, "signal", lambda *_args, **_kwargs: None)
    _patch_time(monkeypatch, recorder_mod)

    class FakeTimeout(Exception):
        pass

    class FakeClosed(Exception):
        pass

    instances: list["FakeWebSocket"] = []

    class FakeWebSocket:
        def __init__(self) -> None:
            self.idx = len(instances)
            self.recv_calls = 0
            instances.append(self)

        def connect(self, _url: str) -> None:
            return None

        def settimeout(self, _timeout: float) -> None:
            return None

        def send(self, _payload: str) -> None:
            return None

        def ping(self, _payload: str) -> None:
            return None

        def recv(self) -> str:
            self.recv_calls += 1
            if self.idx == 0:
                if self.recv_calls == 1:
                    return json.dumps(
                        {
                            "event_type": "book",
                            "asset_id": "asset-3",
                            "bids": [{"price": "0.40", "size": "100"}],
                            "asks": [{"price": "0.45", "size": "100"}],
                        }
                    )
                raise FakeClosed("closed after first frame")
            if self.idx == 1:
                if self.recv_calls == 1:
                    return json.dumps(
                        {
                            "event_type": "price_change",
                            "asset_id": "asset-3",
                            "changes": [{"side": "BUY", "price": "0.41", "size": "50"}],
                        }
                    )
                if self.recv_calls == 2:
                    return json.dumps(
                        {
                            "event_type": "last_trade_price",
                            "asset_id": "asset-3",
                            "price": "0.42",
                        }
                    )
            raise FakeTimeout()

        def close(self) -> None:
            return None

    fake_ws_module = type(
        "FakeWebsocketModule",
        (),
        {
            "WebSocket": FakeWebSocket,
            "WebSocketTimeoutException": FakeTimeout,
            "WebSocketConnectionClosedException": FakeClosed,
        },
    )
    monkeypatch.setitem(sys.modules, "websocket", fake_ws_module)

    tape_dir = tmp_path / "tape_seq"
    recorder = TapeRecorder(
        tape_dir=tape_dir,
        asset_ids=["asset-3"],
        strict=True,
    )
    recorder.record(duration_seconds=0.30, ws_url="wss://unit-test")

    raw_rows = [
        json.loads(line)
        for line in (tape_dir / "raw_ws.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    events_rows = [
        json.loads(line)
        for line in (tape_dir / "events.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    assert [row["frame_seq"] for row in raw_rows] == list(range(len(raw_rows)))
    assert [row["seq"] for row in events_rows] == list(range(len(events_rows)))
    assert len(raw_rows) == 3
    assert len(events_rows) == 3
