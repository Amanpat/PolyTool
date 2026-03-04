"""Tests for the OnDemand session listing API."""

from __future__ import annotations

import json
import pathlib
from decimal import Decimal

import pytest

pytest.importorskip("fastapi", reason="fastapi not installed; skip ondemand tests")


def _write_tape(tmp_path: pathlib.Path, events: list[dict]) -> pathlib.Path:
    tape_dir = tmp_path / "tape_list"
    tape_dir.mkdir(exist_ok=True)
    (tape_dir / "events.jsonl").write_text(
        "\n".join(json.dumps(row) for row in events) + "\n",
        encoding="utf-8",
    )
    return tape_dir


def test_api_list_ondemand_sessions(tmp_path):
    from fastapi.testclient import TestClient

    from packages.polymarket.simtrader.studio.app import create_app

    tape_dir = _write_tape(
        tmp_path,
        [
            {
                "event_type": "book",
                "seq": 1,
                "ts_recv": 1000.0,
                "asset_id": "tok1",
                "bids": [{"price": "0.52", "size": "100"}],
                "asks": [{"price": "0.53", "size": "100"}],
            }
        ],
    )
    app = create_app(tmp_path)
    client = TestClient(app)

    session = client.post(
        "/api/ondemand/new",
        json={
            "tape_path": str(tape_dir),
            "starting_cash": str(Decimal("1000")),
        },
    )
    assert session.status_code == 200
    session_id = session.json()["session_id"]

    listing = client.get("/api/ondemand")
    assert listing.status_code == 200
    rows = listing.json()["sessions"]
    assert any(row["session_id"] == session_id for row in rows)
    row = next(row for row in rows if row["session_id"] == session_id)
    assert row["tape_path"] == str(tape_dir)
    assert row["state"]["total_events"] == 1
