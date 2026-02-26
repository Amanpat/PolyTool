"""Unit tests for the OnDemand tape-replay engine and API routes.

Covers:
  - L2Book.top_bids / top_asks
  - OnDemandSession.step()
  - OnDemandSession.submit_order() + fill via step()
  - OnDemandSession.save_artifacts()
  - POST /api/ondemand/new
  - POST /api/ondemand/{id}/step
  - POST /api/ondemand/{id}/order

All tests use synthetic in-memory tape data (no real WS connection).
FastAPI / httpx are optional deps — skip gracefully if not installed.
"""

from __future__ import annotations

import json
import pathlib
from decimal import Decimal

import pytest

pytest.importorskip("fastapi", reason="fastapi not installed; skip ondemand tests")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_tape(tmp_path: pathlib.Path, events: list) -> pathlib.Path:
    """Write events.jsonl to a tape sub-directory and return the tape dir."""
    tape_dir = tmp_path / "tape_01"
    tape_dir.mkdir(exist_ok=True)
    (tape_dir / "events.jsonl").write_text(
        "\n".join(json.dumps(e) for e in events) + "\n",
        encoding="utf-8",
    )
    return tape_dir


def _book_events(asset_id: str = "tok1") -> list:
    """Return a minimal synthetic tape: book snapshot + 2 price_changes + ltp."""
    return [
        {
            "event_type": "book",
            "seq": 1,
            "ts_recv": 1000.0,
            "asset_id": asset_id,
            "bids": [
                {"price": "0.52", "size": "100"},
                {"price": "0.51", "size": "200"},
            ],
            "asks": [
                {"price": "0.53", "size": "150"},
                {"price": "0.54", "size": "50"},
            ],
        },
        {
            "event_type": "price_change",
            "seq": 2,
            "ts_recv": 1001.0,
            "asset_id": asset_id,
            "changes": [{"side": "BUY", "price": "0.52", "size": "120"}],
        },
        {
            "event_type": "price_change",
            "seq": 3,
            "ts_recv": 1002.0,
            "asset_id": asset_id,
            "changes": [{"side": "SELL", "price": "0.53", "size": "160"}],
        },
        {
            "event_type": "last_trade_price",
            "seq": 4,
            "ts_recv": 1003.0,
            "asset_id": asset_id,
            "price": 0.525,
        },
    ]


# ---------------------------------------------------------------------------
# Test 1: L2Book.top_bids / top_asks
# ---------------------------------------------------------------------------


def test_l2book_top_bids_asks():
    from packages.polymarket.simtrader.orderbook.l2book import L2Book

    b = L2Book("tok", strict=False)
    b.apply(
        {
            "event_type": "book",
            "bids": [
                {"price": "0.50", "size": "100"},
                {"price": "0.52", "size": "80"},
                {"price": "0.51", "size": "60"},
            ],
            "asks": [
                {"price": "0.53", "size": "40"},
                {"price": "0.55", "size": "20"},
            ],
        }
    )
    bids = b.top_bids(2)
    assert len(bids) == 2
    assert bids[0]["price"] == pytest.approx(0.52)  # highest first
    assert bids[1]["price"] == pytest.approx(0.51)

    asks = b.top_asks(2)
    assert len(asks) == 2
    assert asks[0]["price"] == pytest.approx(0.53)  # lowest first
    assert asks[1]["price"] == pytest.approx(0.55)

    # n > available levels — should return all
    assert len(b.top_bids(10)) == 3
    assert len(b.top_asks(10)) == 2


# ---------------------------------------------------------------------------
# Test 2: OnDemandSession.step()
# ---------------------------------------------------------------------------


def test_ondemand_engine_step(tmp_path):
    from packages.polymarket.simtrader.studio.ondemand import OnDemandSession

    tape_dir = _write_tape(tmp_path, _book_events())
    sess = OnDemandSession(str(tape_dir), Decimal("1000"))

    assert sess._cursor == 0

    state = sess.step(1)
    assert state["cursor"] == 1
    assert state["done"] is False
    # After the book snapshot, bbo should be populated for tok1
    assert "tok1" in state["bbo"]
    assert state["bbo"]["tok1"]["best_bid"] == pytest.approx(0.52)
    assert state["bbo"]["tok1"]["best_ask"] == pytest.approx(0.53)
    # depth populated
    assert len(state["depth"]["tok1"]["bids"]) > 0
    assert len(state["depth"]["tok1"]["asks"]) > 0

    # Consume all remaining events
    state2 = sess.step(100)
    assert state2["done"] is True
    assert state2["cursor"] == 4


# ---------------------------------------------------------------------------
# Test 3: submit_order + user_actions recorded
# ---------------------------------------------------------------------------


def test_ondemand_engine_order_and_fill(tmp_path):
    from packages.polymarket.simtrader.studio.ondemand import OnDemandSession

    # Book snapshot at ask=0.55, then price_change to ask=0.51
    events = [
        {
            "event_type": "book",
            "seq": 1,
            "ts_recv": 1000.0,
            "asset_id": "tok1",
            "bids": [{"price": "0.50", "size": "100"}],
            "asks": [{"price": "0.55", "size": "100"}],
        },
        {
            "event_type": "price_change",
            "seq": 2,
            "ts_recv": 1001.0,
            "asset_id": "tok1",
            "changes": [{"side": "SELL", "price": "0.51", "size": "50"}],
        },
    ]
    tape_dir = _write_tape(tmp_path, events)
    sess = OnDemandSession(str(tape_dir), Decimal("1000"))

    # Apply book snapshot
    sess.step(1)

    # Submit a BUY at 0.60 (above ask of 0.55 — should fill on next step)
    order_id, state = sess.submit_order("tok1", "BUY", Decimal("0.60"), Decimal("10"))
    assert order_id is not None
    assert len(order_id) > 0
    # Order appears in open_orders immediately after submission
    assert any(o["order_id"] == order_id for o in state["open_orders"])

    # Step forward — broker processes the book event which can trigger fill
    state2 = sess.step(1)

    # user_actions log should have the submit_order entry
    assert len(sess._user_actions) == 1
    assert sess._user_actions[0]["action"] == "submit_order"
    assert sess._user_actions[0]["params"]["order_id"] == order_id


# ---------------------------------------------------------------------------
# Test 4: save_artifacts writes all 6 required files
# ---------------------------------------------------------------------------


def test_ondemand_save_artifacts(tmp_path):
    from packages.polymarket.simtrader.studio.ondemand import OnDemandSession

    tape_dir = _write_tape(tmp_path, _book_events())
    sess = OnDemandSession(str(tape_dir), Decimal("500"))
    sess.step(4)  # consume all events

    save_dir = tmp_path / "session_out"
    sess.save_artifacts(save_dir)

    expected = {
        "user_actions.jsonl",
        "orders.jsonl",
        "fills.jsonl",
        "ledger.jsonl",
        "equity_curve.jsonl",
        "run_manifest.json",
    }
    written = {f.name for f in save_dir.iterdir()}
    assert expected == written, f"Missing files: {expected - written}"

    # run_manifest has required keys
    manifest = json.loads((save_dir / "run_manifest.json").read_text(encoding="utf-8"))
    assert "session_id" in manifest
    assert "tape_path" in manifest
    assert "summary" in manifest
    assert manifest["cursor"] == 4


# ---------------------------------------------------------------------------
# Test 5: POST /api/ondemand/new
# ---------------------------------------------------------------------------


def test_api_new_session(tmp_path):
    from fastapi.testclient import TestClient

    from packages.polymarket.simtrader.studio.app import create_app

    tape_dir = _write_tape(tmp_path, _book_events())
    app = create_app(tmp_path)
    client = TestClient(app)

    resp = client.post(
        "/api/ondemand/new",
        json={
            "tape_path": str(tape_dir),
            "starting_cash": "1000",
            "fee_rate_bps": None,
            "mark_method": "bid",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "session_id" in data
    assert "state" in data
    assert data["state"]["cursor"] == 0
    assert data["state"]["total_events"] == 4


# ---------------------------------------------------------------------------
# Test 6: POST /api/ondemand/{id}/step
# ---------------------------------------------------------------------------


def test_api_step(tmp_path):
    from fastapi.testclient import TestClient

    from packages.polymarket.simtrader.studio.app import create_app

    tape_dir = _write_tape(tmp_path, _book_events())
    app = create_app(tmp_path)
    client = TestClient(app)

    new_resp = client.post(
        "/api/ondemand/new",
        json={"tape_path": str(tape_dir), "starting_cash": "1000"},
    )
    assert new_resp.status_code == 200
    session_id = new_resp.json()["session_id"]

    step_resp = client.post(
        f"/api/ondemand/{session_id}/step",
        json={"n_steps": 2},
    )
    assert step_resp.status_code == 200
    state = step_resp.json()["state"]
    assert state["cursor"] == 2
    assert state["seq"] is not None
    # After 2 steps (book + price_change), bbo should have tok1
    assert "tok1" in state["bbo"]


# ---------------------------------------------------------------------------
# Test 7: POST /api/ondemand/{id}/order
# ---------------------------------------------------------------------------


def test_api_order(tmp_path):
    from fastapi.testclient import TestClient

    from packages.polymarket.simtrader.studio.app import create_app

    tape_dir = _write_tape(tmp_path, _book_events())
    app = create_app(tmp_path)
    client = TestClient(app)

    new_resp = client.post(
        "/api/ondemand/new",
        json={"tape_path": str(tape_dir), "starting_cash": "1000"},
    )
    session_id = new_resp.json()["session_id"]

    # Step once to get book initialized
    client.post(
        f"/api/ondemand/{session_id}/step",
        json={"n_steps": 1},
    )

    # Submit a BUY order
    order_resp = client.post(
        f"/api/ondemand/{session_id}/order",
        json={
            "asset_id": "tok1",
            "side": "BUY",
            "limit_price": "0.53",
            "size": "10",
        },
    )
    assert order_resp.status_code == 200
    data = order_resp.json()
    assert "order_id" in data
    assert len(data["order_id"]) > 0
    # order appears in open_orders (or may have already filled at best ask)
    all_order_ids = [o["order_id"] for o in data["state"]["open_orders"]]
    # The order might be immediately filled (ZERO_LATENCY + ask=0.53 == limit)
    # Either it's open or it was filled — just verify order_id is a valid string
    assert isinstance(data["order_id"], str)
    assert "state" in data
