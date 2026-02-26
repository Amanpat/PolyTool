"""Unit tests for SimTrader Studio FastAPI server.

Requires fastapi and httpx (both come with fastapi[all] or fastapi + httpx).
The whole module is skipped gracefully if fastapi is not installed.
"""

from __future__ import annotations

import json

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
