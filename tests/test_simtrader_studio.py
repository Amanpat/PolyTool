"""Unit tests for SimTrader Studio FastAPI server.

Requires fastapi and httpx (both come with fastapi[all] or fastapi + httpx).
The whole module is skipped gracefully if fastapi is not installed.
"""

from __future__ import annotations

import json
import sys
import time

import pytest

pytest.importorskip("fastapi", reason="fastapi not installed; skip studio tests")


# ---------------------------------------------------------------------------
# Test 1: root route returns 200 with SimTrader Studio in response body
# ---------------------------------------------------------------------------


def test_root_returns_200(tmp_path):
    from fastapi.testclient import TestClient

    from packages.polymarket.simtrader.studio.app import create_app

    app = create_app(artifacts_dir=tmp_path)
    client = TestClient(app)
    resp = client.get("/")
    assert resp.status_code == 200
    assert "SimTrader Studio" in resp.text


# ---------------------------------------------------------------------------
# Test 2: /api/artifacts returns empty list when artifacts dir does not exist
# ---------------------------------------------------------------------------


def test_artifacts_endpoint_empty(tmp_path):
    from fastapi.testclient import TestClient

    from packages.polymarket.simtrader.studio.app import create_app

    app = create_app(artifacts_dir=tmp_path / "nonexistent")
    client = TestClient(app)
    resp = client.get("/api/artifacts")
    assert resp.status_code == 200
    data = resp.json()
    assert "artifacts" in data
    assert data["artifacts"] == []


# ---------------------------------------------------------------------------
# Test 3: /api/artifacts returns artifacts from populated runs/ subdir
# ---------------------------------------------------------------------------


def test_artifacts_endpoint_with_run(tmp_path):
    from fastapi.testclient import TestClient

    from packages.polymarket.simtrader.studio.app import create_app

    # Create a fake run artifact with a run_manifest.json marker.
    run_dir = tmp_path / "runs" / "20260226T120000Z_testmarket"
    run_dir.mkdir(parents=True)
    (run_dir / "run_manifest.json").write_text(json.dumps({"artifact_type": "run"}))

    app = create_app(artifacts_dir=tmp_path)
    client = TestClient(app)
    resp = client.get("/api/artifacts")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["artifacts"]) == 1
    assert data["artifacts"][0]["artifact_type"] == "run"
    assert data["artifacts"][0]["artifact_id"] == "20260226T120000Z_testmarket"


def test_artifacts_endpoint_uses_manifest_display_name(tmp_path):
    from fastapi.testclient import TestClient

    from packages.polymarket.simtrader.studio.app import create_app

    run_dir = tmp_path / "runs" / "20260226T120000Z_named"
    run_dir.mkdir(parents=True)
    expected_name = (
        "2026-02-26 12:00Z | run | market=will-btc-above-100k | "
        "strategy=binary_complement_arb | preset=sane"
    )
    (run_dir / "run_manifest.json").write_text(
        json.dumps({"display_name": expected_name}),
        encoding="utf-8",
    )

    app = create_app(artifacts_dir=tmp_path)
    client = TestClient(app)
    resp = client.get("/api/artifacts")
    assert resp.status_code == 200
    artifact = resp.json()["artifacts"][0]
    assert artifact["artifact_id"] == "20260226T120000Z_named"
    assert artifact["display_name"] == expected_name


def test_artifacts_endpoint_derives_display_name_when_legacy_manifest_missing_field(tmp_path):
    from fastapi.testclient import TestClient

    from packages.polymarket.simtrader.studio.app import create_app

    run_dir = tmp_path / "runs" / "20260226T183132Z_legacy"
    run_dir.mkdir(parents=True)
    (run_dir / "run_manifest.json").write_text(
        json.dumps(
            {
                "run_id": "20260226T183132Z_legacy",
                "created_at": "2026-02-26T18:31:32+00:00",
                "market_slug": "will-btc-above-100k",
                "strategy": "binary_complement_arb",
                "strategy_preset": "sane",
            }
        ),
        encoding="utf-8",
    )

    app = create_app(artifacts_dir=tmp_path)
    client = TestClient(app)
    resp = client.get("/api/artifacts")
    assert resp.status_code == 200
    name = resp.json()["artifacts"][0]["display_name"]
    assert "run" in name
    assert "market=will-btc-above-100k" in name
    assert "strategy=binary_complement_arb" in name
    assert "preset=sane" in name


# ---------------------------------------------------------------------------
# Test 4: /api/run rejects commands not on the allowlist (HTTP 400)
# ---------------------------------------------------------------------------


def test_run_endpoint_rejects_unknown_command(tmp_path):
    from fastapi.testclient import TestClient

    from packages.polymarket.simtrader.studio.app import create_app

    app = create_app(artifacts_dir=tmp_path)
    client = TestClient(app)
    resp = client.post("/api/run", json={"command": "rm", "args": ["-rf", "/"]})
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Test 4b: /api/sessions returns an empty list when no sessions exist
# ---------------------------------------------------------------------------


def test_sessions_endpoint_empty(tmp_path):
    from fastapi.testclient import TestClient

    from packages.polymarket.simtrader.studio.app import create_app

    app = create_app(artifacts_dir=tmp_path)
    client = TestClient(app)
    resp = client.get("/api/sessions")
    assert resp.status_code == 200
    assert resp.json()["sessions"] == []


# ---------------------------------------------------------------------------
# Test 4c: /api/sessions can start a session and expose detail/list snapshots
# ---------------------------------------------------------------------------


def test_sessions_start_and_detail(tmp_path):
    from fastapi.testclient import TestClient

    from packages.polymarket.simtrader.studio.app import create_app
    from packages.polymarket.simtrader.studio_sessions import (
        TERMINAL_STATUSES,
        StudioSessionManager,
    )

    artifacts_root = tmp_path / "artifacts" / "simtrader"
    run_dir = (artifacts_root / "shadow_runs" / "unit-shadow").resolve()
    tape_dir = (artifacts_root / "tapes" / "unit-shadow-tape").resolve()
    script = (
        "import sys\n"
        f"print('  Tape dir   : {tape_dir.as_posix()}')\n"
        f"print('[shadow] run dir  : {run_dir.as_posix()}')\n"
        "print('Orders: 2   Fills: 1')\n"
        "sys.stdout.flush()\n"
    )

    def command_builder(subcommand: str, args: list[str]) -> list[str]:
        assert subcommand == "shadow"
        return [sys.executable, "-u", "-c", script]

    manager = StudioSessionManager(artifacts_root=artifacts_root, command_builder=command_builder)
    app = create_app(artifacts_dir=artifacts_root, session_manager=manager)
    client = TestClient(app)

    start = client.post("/api/sessions", json={"command": "shadow", "args": ["--market", "slug"]})
    assert start.status_code == 200
    started = start.json()["session"]
    session_id = started["session_id"]
    assert started["subcommand"] == "shadow"

    for _ in range(120):
        detail_resp = client.get(f"/api/sessions/{session_id}")
        assert detail_resp.status_code == 200
        detail = detail_resp.json()["session"]
        if detail["status"] in TERMINAL_STATUSES:
            break
        time.sleep(0.05)
    else:
        raise AssertionError("session did not reach terminal state")

    assert detail["status"] == "succeeded"
    assert detail["artifact_dir"] == str(run_dir)
    assert detail["tape_dir"] == str(tape_dir)
    listed = client.get("/api/sessions").json()["sessions"]
    row = next(row for row in listed if row["session_id"] == session_id)
    assert row["tape_dir"] == str(tape_dir)


# ---------------------------------------------------------------------------
# Test 4d: /api/sessions/{id}/log returns captured output lines
# ---------------------------------------------------------------------------


def test_session_log_endpoint_returns_lines(tmp_path):
    from fastapi.testclient import TestClient

    from packages.polymarket.simtrader.studio.app import create_app
    from packages.polymarket.simtrader.studio_sessions import (
        TERMINAL_STATUSES,
        StudioSessionManager,
    )

    artifacts_root = tmp_path / "artifacts" / "simtrader"
    script = (
        "import sys\n"
        "print('line one')\n"
        "print('line two')\n"
        "sys.stdout.flush()\n"
    )

    def command_builder(subcommand: str, args: list[str]) -> list[str]:
        assert subcommand == "clean"
        return [sys.executable, "-u", "-c", script]

    manager = StudioSessionManager(artifacts_root=artifacts_root, command_builder=command_builder)
    app = create_app(artifacts_dir=artifacts_root, session_manager=manager)
    client = TestClient(app)

    start = client.post("/api/sessions", json={"command": "clean", "args": "--yes"})
    assert start.status_code == 200
    session_id = start.json()["session"]["session_id"]

    for _ in range(120):
        detail = client.get(f"/api/sessions/{session_id}").json()["session"]
        if detail["status"] in TERMINAL_STATUSES:
            break
        time.sleep(0.05)
    else:
        raise AssertionError("session did not reach terminal state")

    log_resp = client.get(f"/api/sessions/{session_id}/log?offset=0")
    assert log_resp.status_code == 200
    payload = log_resp.json()
    assert payload["offset"] >= 0
    assert any("line one" in line for line in payload["lines"])
    assert any("line two" in line for line in payload["lines"])


# ---------------------------------------------------------------------------
# Test 4e: /api/sessions/{id}/viewer returns chart/orders/fills/reasons payload
# ---------------------------------------------------------------------------


def test_session_viewer_endpoint(tmp_path):
    from fastapi.testclient import TestClient

    from packages.polymarket.simtrader.studio.app import create_app
    from packages.polymarket.simtrader.studio_sessions import (
        TERMINAL_STATUSES,
        StudioSessionManager,
    )

    artifacts_root = tmp_path / "artifacts" / "simtrader"

    def command_builder(subcommand: str, args: list[str]) -> list[str]:
        assert subcommand == "run"
        run_id = ""
        for idx, token in enumerate(args):
            if token == "--run-id" and idx + 1 < len(args):
                run_id = args[idx + 1]
                break
        assert run_id
        run_dir = artifacts_root / "runs" / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "equity_curve.jsonl").write_text(
            '{"seq": 1, "equity": "1000"}\n{"seq": 2, "equity": "1001.5"}\n',
            encoding="utf-8",
        )
        (run_dir / "orders.jsonl").write_text(
            '{"seq": 2, "event": "submitted", "order_id": "o1", "side": "BUY", "limit_price": "0.45", "size": "10", "status": "ACTIVE"}\n',
            encoding="utf-8",
        )
        (run_dir / "fills.jsonl").write_text(
            '{"seq": 3, "order_id": "o1", "side": "BUY", "fill_price": "0.45", "fill_size": "10", "remaining_size": "0"}\n',
            encoding="utf-8",
        )
        (run_dir / "run_manifest.json").write_text(
            json.dumps({"strategy_debug": {"rejection_counts": {"edge_below_threshold": 5}}}),
            encoding="utf-8",
        )
        script = "print('viewer run complete')\n"
        return [sys.executable, "-u", "-c", script]

    manager = StudioSessionManager(artifacts_root=artifacts_root, command_builder=command_builder)
    app = create_app(artifacts_dir=artifacts_root, session_manager=manager)
    client = TestClient(app)

    start = client.post(
        "/api/sessions",
        json={"command": "run", "args": ["--tape", "ignored.jsonl", "--strategy", "noop"]},
    )
    assert start.status_code == 200
    session_id = start.json()["session"]["session_id"]

    for _ in range(120):
        detail = client.get(f"/api/sessions/{session_id}").json()["session"]
        if detail["status"] in TERMINAL_STATUSES:
            break
        time.sleep(0.05)
    else:
        raise AssertionError("session did not reach terminal state")

    viewer = client.get(f"/api/sessions/{session_id}/viewer")
    assert viewer.status_code == 200
    payload = viewer.json()
    assert payload["session"]["session_id"] == session_id
    assert len(payload["equity_curve"]) == 2
    assert len(payload["orders"]) == 1
    assert len(payload["fills"]) == 1
    assert payload["rejection_reasons"][0]["reason"] == "edge_below_threshold"


def test_session_viewer_endpoint_accepts_tape_only_session(tmp_path):
    from fastapi.testclient import TestClient

    from packages.polymarket.simtrader.studio.app import create_app

    artifacts_root = tmp_path / "artifacts" / "simtrader"
    tape_dir = (artifacts_root / "tapes" / "shadow-viewer-tape").resolve()
    tape_dir.mkdir(parents=True)
    (tape_dir / "events.jsonl").write_text('{"type":"book","seq":1}\n', encoding="utf-8")

    session_id = "shadow-viewer"
    row = {
        "session_id": session_id,
        "kind": "shadow",
        "subcommand": "shadow",
        "status": "running",
        "started_at": "2026-03-03T00:00:00+00:00",
        "artifact_dir": None,
        "tape_dir": str(tape_dir),
        "args": ["--market", "slug"],
        "pid": None,
        "exit_reason": None,
        "log_path": str((artifacts_root / "studio_sessions" / session_id / "logs.txt").resolve()),
        "counters": {},
        "ended_at": None,
        "return_code": None,
    }

    class FakeSessionManager:
        def list_sessions(self):
            return [row]

        def get_session(self, requested_session_id: str):
            if requested_session_id == session_id:
                return dict(row)
            return None

        def start_session(self, *args, **kwargs):
            raise AssertionError("start_session should not be called")

        def kill_session(self, *args, **kwargs):
            raise KeyError("unused")

        def read_log_chunk(self, *args, **kwargs):
            return 0, []

    app = create_app(artifacts_dir=artifacts_root, session_manager=FakeSessionManager())
    client = TestClient(app)

    viewer = client.get(f"/api/sessions/{session_id}/viewer")
    assert viewer.status_code == 200
    payload = viewer.json()
    assert payload["session"]["session_id"] == session_id
    assert payload["session"]["artifact_dir"] is None
    assert payload["session"]["tape_dir"] == str(tape_dir)
    assert payload["equity_curve"] == []


# ---------------------------------------------------------------------------
# Test 4f: /api/simulation/{type}/{id}/series downsamples best_bid_ask.jsonl
# ---------------------------------------------------------------------------


def test_simulation_series_endpoint_downsamples_best_bid_ask(tmp_path):
    from fastapi.testclient import TestClient

    from packages.polymarket.simtrader.studio.app import create_app

    run_id = "20260226T150000Z_simulation_unit"
    run_dir = tmp_path / "runs" / run_id
    run_dir.mkdir(parents=True)

    rows = []
    for seq in range(40):
        rows.append(
            json.dumps(
                {
                    "seq": seq,
                    "ts_recv": 1772120000.0 + seq,
                    "asset_id": "asset_yes",
                    "event_type": "price_change",
                    "best_bid": 0.20 + (seq * 0.001),
                    "best_ask": 0.30 + (seq * 0.001),
                }
            )
        )
    (run_dir / "best_bid_ask.jsonl").write_text("\n".join(rows) + "\n", encoding="utf-8")
    (run_dir / "run_manifest.json").write_text(
        json.dumps({"asset_id": "asset_yes", "extra_book_asset_ids": ["asset_no"]}),
        encoding="utf-8",
    )

    app = create_app(artifacts_dir=tmp_path)
    client = TestClient(app)

    resp = client.get(f"/api/simulation/run/{run_id}/series?max_points=9")
    assert resp.status_code == 200
    payload = resp.json()
    series = payload["series"]

    assert payload["artifact"]["artifact_type"] == "run"
    assert payload["artifact"]["artifact_id"] == run_id
    assert series["source_rows"] == 40
    assert series["filtered_rows"] == 40
    assert series["downsampled_rows"] == 9
    assert len(series["points"]) == 9
    assert series["points"][0]["seq"] == 0
    assert series["points"][-1]["seq"] == 39
    seqs = [row["seq"] for row in series["points"]]
    assert seqs == sorted(seqs)


# ---------------------------------------------------------------------------
# Test 5: /api/tapes returns empty list when tapes dir does not exist
# ---------------------------------------------------------------------------


def test_tapes_endpoint_empty(tmp_path):
    from fastapi.testclient import TestClient

    from packages.polymarket.simtrader.studio.app import create_app

    app = create_app(artifacts_dir=tmp_path / "nonexistent")
    client = TestClient(app)
    resp = client.get("/api/tapes")
    assert resp.status_code == 200
    data = resp.json()
    assert "tapes" in data
    assert data["tapes"] == []


# ---------------------------------------------------------------------------
# Test 6: /api/tapes lists tapes containing events.jsonl
# ---------------------------------------------------------------------------


def test_tapes_endpoint_with_tape(tmp_path):
    from fastapi.testclient import TestClient

    from packages.polymarket.simtrader.studio.app import create_app

    tape_dir = tmp_path / "tapes" / "20260226T130000Z_abc12345"
    tape_dir.mkdir(parents=True)
    (tape_dir / "events.jsonl").write_text('{"type":"book"}\n')

    app = create_app(artifacts_dir=tmp_path)
    client = TestClient(app)
    resp = client.get("/api/tapes")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["tapes"]) == 1
    assert data["tapes"][0]["tape_id"] == "20260226T130000Z_abc12345"
    assert data["tapes"][0]["has_events"] is True


# ---------------------------------------------------------------------------
# Test 7: artifacts with has_report=True when report.html present
# ---------------------------------------------------------------------------


def test_artifacts_has_report_flag(tmp_path):
    from fastapi.testclient import TestClient

    from packages.polymarket.simtrader.studio.app import create_app

    run_dir = tmp_path / "runs" / "20260226T140000Z_withreport"
    run_dir.mkdir(parents=True)
    (run_dir / "run_manifest.json").write_text("{}")
    (run_dir / "report.html").write_text("<html></html>")

    app = create_app(artifacts_dir=tmp_path)
    client = TestClient(app)
    resp = client.get("/api/artifacts")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["artifacts"]) == 1
    assert data["artifacts"][0]["has_report"] is True


# ---------------------------------------------------------------------------
# Test 8: studio subparser --host flag
# ---------------------------------------------------------------------------


def test_studio_parser_host_default():
    """--host defaults to 127.0.0.1."""
    from tools.cli.simtrader import _build_parser

    parser = _build_parser()
    args = parser.parse_args(["studio"])
    assert args.host == "127.0.0.1"


def test_studio_parser_host_explicit():
    """--host 0.0.0.0 is accepted and stored on args."""
    from tools.cli.simtrader import _build_parser

    parser = _build_parser()
    args = parser.parse_args(["studio", "--host", "0.0.0.0"])
    assert args.host == "0.0.0.0"


# ---------------------------------------------------------------------------
# Test 9: /api/sessions/{id}/monitor returns lightweight stats shape
# ---------------------------------------------------------------------------


def test_session_monitor_endpoint_no_artifact_dir(tmp_path):
    """Monitor endpoint returns correct shape even when session has no artifact_dir."""
    from fastapi.testclient import TestClient

    from packages.polymarket.simtrader.studio.app import create_app
    from packages.polymarket.simtrader.studio_sessions import (
        TERMINAL_STATUSES,
        StudioSessionManager,
    )

    artifacts_root = tmp_path / "artifacts" / "simtrader"
    script = "import sys\nprint('monitor test')\nsys.stdout.flush()\n"

    def command_builder(subcommand: str, args: list[str]) -> list[str]:
        return [sys.executable, "-u", "-c", script]

    manager = StudioSessionManager(artifacts_root=artifacts_root, command_builder=command_builder)
    app = create_app(artifacts_dir=artifacts_root, session_manager=manager)
    client = TestClient(app)

    start = client.post("/api/sessions", json={"command": "clean", "args": "--yes"})
    assert start.status_code == 200
    session_id = start.json()["session"]["session_id"]

    for _ in range(120):
        detail = client.get(f"/api/sessions/{session_id}").json()["session"]
        if detail["status"] in TERMINAL_STATUSES:
            break
        import time
        time.sleep(0.05)
    else:
        raise AssertionError("session did not reach terminal state")

    resp = client.get(f"/api/sessions/{session_id}/monitor")
    assert resp.status_code == 200
    payload = resp.json()
    # Required fields present
    assert payload["session_id"] == session_id
    assert "status" in payload
    assert "started_at" in payload
    assert "subcommand" in payload
    assert "report_url" in payload
    assert "artifact_dir" in payload
    assert "run_metrics" in payload
    assert "net_profit" in payload
    assert "strategy" in payload
    assert "decisions_count" in payload
    assert "orders_count" in payload
    assert "fills_count" in payload
    # No artifact_dir => run_metrics is empty dict, counts are None
    assert payload["run_metrics"] == {}
    assert payload["net_profit"] is None
    assert payload["strategy"] is None


def test_session_monitor_endpoint_with_artifact_dir(tmp_path):
    """Monitor endpoint reads run_manifest.json and summary.json for metrics."""
    from fastapi.testclient import TestClient

    from packages.polymarket.simtrader.studio.app import create_app
    from packages.polymarket.simtrader.studio_sessions import (
        TERMINAL_STATUSES,
        StudioSessionManager,
    )

    artifacts_root = tmp_path / "artifacts" / "simtrader"

    def command_builder(subcommand: str, args: list[str]) -> list[str]:
        # run subcommand receives --run-id; use it to write artifacts
        run_id = ""
        for idx, token in enumerate(args):
            if token == "--run-id" and idx + 1 < len(args):
                run_id = args[idx + 1]
                break
        assert run_id, f"--run-id not found in args: {args}"
        run_dir = artifacts_root / "runs" / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        manifest = {
            "run_metrics": {
                "events_received": 42,
                "ws_reconnects": 1,
                "ws_timeouts": 0,
            },
            "strategy": "binary_complement_arb",
        }
        (run_dir / "run_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        summary_data = {"net_profit": "3.14", "orders_count": 5, "fills_count": 3}
        (run_dir / "summary.json").write_text(json.dumps(summary_data), encoding="utf-8")
        return [sys.executable, "-u", "-c", "print('done')"]

    manager = StudioSessionManager(artifacts_root=artifacts_root, command_builder=command_builder)
    app = create_app(artifacts_dir=artifacts_root, session_manager=manager)
    client = TestClient(app)

    start = client.post(
        "/api/sessions",
        json={"command": "run", "args": ["--tape", "ignored.jsonl", "--strategy", "noop"]},
    )
    assert start.status_code == 200
    session_id = start.json()["session"]["session_id"]

    for _ in range(120):
        detail = client.get(f"/api/sessions/{session_id}").json()["session"]
        if detail["status"] in TERMINAL_STATUSES:
            break
        import time
        time.sleep(0.05)
    else:
        raise AssertionError("session did not reach terminal state")

    resp = client.get(f"/api/sessions/{session_id}/monitor")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["run_metrics"]["events_received"] == 42
    assert payload["run_metrics"]["ws_reconnects"] == 1
    assert payload["run_metrics"]["ws_timeouts"] == 0
    assert payload["strategy"] == "binary_complement_arb"
    assert payload["net_profit"] == "3.14"
    assert payload["orders_count"] == 5
    assert payload["fills_count"] == 3


def test_session_monitor_endpoint_unknown_returns_404(tmp_path):
    """Monitor endpoint returns 404 for unknown session_id."""
    from fastapi.testclient import TestClient

    from packages.polymarket.simtrader.studio.app import create_app

    app = create_app(artifacts_dir=tmp_path)
    client = TestClient(app)
    resp = client.get("/api/sessions/nonexistent-id/monitor")
    assert resp.status_code == 404
