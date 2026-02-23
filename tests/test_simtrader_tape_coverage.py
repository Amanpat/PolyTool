from __future__ import annotations

import json
import sys
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest


def _write_events(path: Path, events: list[dict]) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        for event in events:
            fh.write(json.dumps(event) + "\n")


def test_tape_info_summarizes_two_asset_tape(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    from tools.cli.simtrader import main as simtrader_main

    yes_id = "yes-asset-1"
    no_id = "no-asset-1"
    tape_path = tmp_path / "events.jsonl"
    _write_events(
        tape_path,
        [
            {
                "parser_version": 1,
                "seq": 10,
                "ts_recv": 1.0,
                "event_type": "book",
                "asset_id": yes_id,
                "bids": [{"price": "0.40", "size": "100"}],
                "asks": [{"price": "0.60", "size": "100"}],
            },
            {
                "parser_version": 1,
                "seq": 11,
                "ts_recv": 2.0,
                "event_type": "price_change",
                "asset_id": yes_id,
                "changes": [{"side": "BUY", "price": "0.41", "size": "50"}],
            },
            {
                "parser_version": 1,
                "seq": 12,
                "ts_recv": 3.0,
                "event_type": "price_change",
                "asset_id": no_id,
                "changes": [{"side": "SELL", "price": "0.55", "size": "30"}],
            },
        ],
    )

    rc = simtrader_main(["tape-info", "--tape", str(tape_path)])
    assert rc == 0

    captured = capsys.readouterr()
    summary = json.loads(captured.out)
    assert summary["asset_ids"] == [no_id, yes_id]
    assert summary["event_type_counts"] == {"book": 1, "price_change": 2}
    assert summary["first_seq"] == 10
    assert summary["last_seq"] == 12
    assert summary["snapshot_by_asset"][yes_id] is True
    assert summary["snapshot_by_asset"][no_id] is False


def test_binary_arb_missing_complement_marks_invalid_and_fails_fast(tmp_path: Path) -> None:
    from packages.polymarket.simtrader.strategies.binary_complement_arb import (
        BinaryComplementArb,
    )
    from packages.polymarket.simtrader.strategy.runner import StrategyRunner

    yes_id = "yes-only-asset"
    no_id = "no-missing-asset"
    tape_path = tmp_path / "events_yes_only.jsonl"
    _write_events(
        tape_path,
        [
            {
                "parser_version": 1,
                "seq": 0,
                "ts_recv": 1.0,
                "event_type": "book",
                "asset_id": yes_id,
                "bids": [{"price": "0.40", "size": "100"}],
                "asks": [{"price": "0.45", "size": "100"}],
            },
            {
                "parser_version": 1,
                "seq": 1,
                "ts_recv": 2.0,
                "event_type": "price_change",
                "asset_id": yes_id,
                "changes": [{"side": "BUY", "price": "0.41", "size": "40"}],
            },
        ],
    )

    run_dir = tmp_path / "arb_invalid_run"
    runner = StrategyRunner(
        events_path=tape_path,
        run_dir=run_dir,
        strategy=BinaryComplementArb(
            yes_asset_id=yes_id,
            no_asset_id=no_id,
            buffer=0.02,
            max_size=10.0,
        ),
        asset_id=yes_id,
        extra_book_asset_ids=[no_id],
        starting_cash=Decimal("1000"),
    )

    with pytest.raises(ValueError, match="Tape coverage check failed"):
        runner.run()

    meta = json.loads((run_dir / "meta.json").read_text(encoding="utf-8"))
    assert meta["run_quality"] == "invalid"
    assert any("missing events for required asset_ids" in warning for warning in meta["warnings"])
    assert (run_dir / "summary.json").exists() is False


def test_binary_arb_missing_complement_allow_degraded_continues(tmp_path: Path) -> None:
    from packages.polymarket.simtrader.strategies.binary_complement_arb import (
        BinaryComplementArb,
    )
    from packages.polymarket.simtrader.strategy.runner import StrategyRunner

    yes_id = "yes-only-asset"
    no_id = "no-missing-asset"
    tape_path = tmp_path / "events_yes_only_degraded.jsonl"
    _write_events(
        tape_path,
        [
            {
                "parser_version": 1,
                "seq": 0,
                "ts_recv": 1.0,
                "event_type": "book",
                "asset_id": yes_id,
                "bids": [{"price": "0.40", "size": "100"}],
                "asks": [{"price": "0.45", "size": "100"}],
            },
            {
                "parser_version": 1,
                "seq": 1,
                "ts_recv": 2.0,
                "event_type": "price_change",
                "asset_id": yes_id,
                "changes": [{"side": "BUY", "price": "0.41", "size": "40"}],
            },
        ],
    )

    run_dir = tmp_path / "arb_degraded_run"
    runner = StrategyRunner(
        events_path=tape_path,
        run_dir=run_dir,
        strategy=BinaryComplementArb(
            yes_asset_id=yes_id,
            no_asset_id=no_id,
            buffer=0.02,
            max_size=10.0,
        ),
        asset_id=yes_id,
        extra_book_asset_ids=[no_id],
        starting_cash=Decimal("1000"),
        allow_degraded=True,
    )
    runner.run()

    meta = json.loads((run_dir / "meta.json").read_text(encoding="utf-8"))
    assert meta["run_quality"] == "degraded"
    summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
    assert summary["run_quality"] == "degraded"
    assert any("missing events for required asset_ids" in warning for warning in summary["warnings"])


def test_multi_asset_recording_has_deterministic_global_seq_order(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import packages.polymarket.simtrader.tape.recorder as recorder_mod
    from packages.polymarket.simtrader.tape.recorder import TapeRecorder

    frames = [
        json.dumps(
            [
                {
                    "event_type": "book",
                    "asset_id": "yes-1",
                    "bids": [{"price": "0.40", "size": "100"}],
                    "asks": [{"price": "0.44", "size": "100"}],
                },
                {
                    "event_type": "book",
                    "asset_id": "no-1",
                    "bids": [{"price": "0.52", "size": "100"}],
                    "asks": [{"price": "0.56", "size": "100"}],
                },
            ]
        ),
        json.dumps(
            {
                "event_type": "price_change",
                "asset_id": "yes-1",
                "changes": [{"side": "BUY", "price": "0.41", "size": "50"}],
            }
        ),
        json.dumps(
            [
                {
                    "event_type": "price_change",
                    "asset_id": "no-1",
                    "changes": [{"side": "SELL", "price": "0.55", "size": "70"}],
                },
                {
                    "event_type": "last_trade_price",
                    "asset_id": "yes-1",
                    "price": "0.42",
                },
            ]
        ),
    ]

    monkeypatch.setattr(recorder_mod.signal, "signal", lambda *_args, **_kwargs: None)

    def _record_once(out_dir: Path) -> str:
        class FakeTimeout(Exception):
            pass

        class FakeWebSocket:
            def __init__(self) -> None:
                self._idx = 0

            def connect(self, _ws_url: str) -> None:
                return None

            def send(self, _payload: str) -> None:
                return None

            def settimeout(self, _seconds: float) -> None:
                return None

            def recv(self) -> str:
                if self._idx >= len(frames):
                    raise FakeTimeout()
                payload = frames[self._idx]
                self._idx += 1
                return payload

            def close(self) -> None:
                return None

        fake_ws_module = SimpleNamespace(
            WebSocket=FakeWebSocket,
            WebSocketTimeoutException=FakeTimeout,
        )
        monkeypatch.setitem(sys.modules, "websocket", fake_ws_module)

        tick = {"value": 1000.0}

        def _fake_time() -> float:
            tick["value"] += 0.01
            return tick["value"]

        monkeypatch.setattr(recorder_mod.time, "time", _fake_time)

        recorder = TapeRecorder(
            tape_dir=out_dir,
            asset_ids=["yes-1", "no-1"],
            strict=True,
        )
        recorder.record(duration_seconds=0.50, ws_url="wss://unit-test")
        return (out_dir / "events.jsonl").read_text(encoding="utf-8")

    text_a = _record_once(tmp_path / "tape_a")
    text_b = _record_once(tmp_path / "tape_b")
    assert text_a == text_b

    events = [json.loads(line) for line in text_a.splitlines() if line.strip()]
    assert [event["seq"] for event in events] == list(range(len(events)))
    assert [event["asset_id"] for event in events] == [
        "yes-1",
        "no-1",
        "yes-1",
        "no-1",
        "yes-1",
    ]
