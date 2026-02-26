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
    script = (
        "import sys\n"
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
    listed = client.get("/api/sessions").json()["sessions"]
    assert any(row["session_id"] == session_id for row in listed)


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
