from __future__ import annotations

import json
import os
import shutil
import uuid
from pathlib import Path

from tools.cli import scan


def test_run_scan_emits_trust_artifacts_from_canonical_scan_path(monkeypatch):
    tmp_path = Path("artifacts") / "_pytest_scan_trust" / uuid.uuid4().hex
    shutil.rmtree(tmp_path, ignore_errors=True)
    tmp_path.mkdir(parents=True, exist_ok=True)
    original_cwd = Path.cwd()
    try:
        os.chdir(tmp_path)

        run_root = (
            tmp_path
            / "artifacts"
            / "dossiers"
            / "users"
            / "testuser"
            / "0xabc"
            / "2026-02-06"
            / "run-123"
        )
        run_root.mkdir(parents=True, exist_ok=True)
        (run_root / "dossier.json").write_text(
            json.dumps(
                {
                    "positions": {
                        "positions": [
                            {
                                "trade_uid": "uid-1",
                                "resolved_token_id": "tok-1",
                                "resolution_outcome": "WIN",
                                "realized_pnl_net": 3.0,
                                "position_remaining": 0.0,
                            },
                            {
                                "resolved_token_id": "tok-2",
                                "resolution_outcome": "LOSS_EXIT",
                                "realized_pnl_net": -1.0,
                                "position_remaining": 0.0,
                            },
                        ]
                    }
                },
                indent=2,
            ),
            encoding="utf-8",
        )

        def fake_post_json(base_url, path, payload, timeout=120.0, retries=3, backoff_seconds=1.0):
            assert base_url == "http://localhost:8000"
            if path == "/api/resolve":
                return {"username": "TestUser", "proxy_wallet": "0xabc"}
            if path == "/api/ingest/trades":
                return {
                    "pages_fetched": 1,
                    "rows_fetched_total": 2,
                    "rows_written": 2,
                    "distinct_trade_uids_total": 2,
                }
            if path == "/api/run/detectors":
                return {"results": [], "backfill_stats": None}
            if path == "/api/export/user_dossier":
                return {
                    "export_id": "run-123",
                    "artifact_path": str(run_root),
                    "proxy_wallet": "0xabc",
                    "username_slug": "testuser",
                }
            raise AssertionError(f"Unexpected scan API path: {path}")

        monkeypatch.setattr(scan, "post_json", fake_post_json)

        config = {
            "user": "@TestUser",
            "max_pages": 10,
            "bucket": "day",
            "backfill": True,
            "ingest_markets": False,
            "ingest_activity": False,
            "ingest_positions": False,
            "compute_pnl": False,
            "compute_opportunities": False,
            "snapshot_books": False,
            "api_base_url": "http://localhost:8000",
            "timeout_seconds": 30.0,
        }

        emitted = scan.run_scan(
            config=config,
            argv=["--user", "@TestUser"],
            started_at="2026-02-06T12:00:00+00:00",
        )

        assert Path(emitted["coverage_reconciliation_report_json"]).exists()
        assert Path(emitted["run_manifest"]).exists()

        coverage = json.loads(Path(emitted["coverage_reconciliation_report_json"]).read_text(encoding="utf-8"))
        assert coverage["totals"]["positions_total"] > 0
        assert "deterministic_trade_uid_coverage" in coverage
        assert "fallback_uid_coverage" in coverage
        assert "trade_uid_coverage" not in coverage
        assert coverage["deterministic_trade_uid_coverage"]["with_trade_uid"] == 1
        assert coverage["fallback_uid_coverage"]["with_fallback_uid"] == 2
        assert coverage["fallback_uid_coverage"]["fallback_only_count"] == 1

        manifest = json.loads(Path(emitted["run_manifest"]).read_text(encoding="utf-8"))
        assert manifest["command_name"] == "scan"
        assert manifest["run_id"] == "run-123"
        assert manifest["output_paths"]["run_root"] == str(run_root)
        assert manifest["output_paths"]["coverage_reconciliation_report_json"] == emitted[
            "coverage_reconciliation_report_json"
        ]
    finally:
        os.chdir(original_cwd)
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_run_scan_calls_resolution_enrichment_when_enabled(monkeypatch):
    tmp_path = Path("artifacts") / "_pytest_scan_trust" / uuid.uuid4().hex
    shutil.rmtree(tmp_path, ignore_errors=True)
    tmp_path.mkdir(parents=True, exist_ok=True)
    original_cwd = Path.cwd()
    try:
        os.chdir(tmp_path)

        run_root = (
            tmp_path
            / "artifacts"
            / "dossiers"
            / "users"
            / "testuser"
            / "0xabc"
            / "2026-02-06"
            / "run-enrich"
        )
        run_root.mkdir(parents=True, exist_ok=True)
        (run_root / "dossier.json").write_text(
            json.dumps(
                {
                    "positions": {
                        "positions": [
                            {
                                "trade_uid": "uid-1",
                                "resolved_token_id": "tok-1",
                                "resolution_outcome": "WIN",
                                "realized_pnl_net": 1.0,
                                "position_remaining": 0.0,
                            }
                        ]
                    }
                },
                indent=2,
            ),
            encoding="utf-8",
        )

        calls = []

        def fake_post_json(base_url, path, payload, timeout=120.0, retries=3, backoff_seconds=1.0):
            calls.append((path, payload))
            if path == "/api/resolve":
                return {"username": "TestUser", "proxy_wallet": "0xabc"}
            if path == "/api/ingest/trades":
                return {
                    "pages_fetched": 1,
                    "rows_fetched_total": 1,
                    "rows_written": 1,
                    "distinct_trade_uids_total": 1,
                }
            if path == "/api/enrich/resolutions":
                return {
                    "proxy_wallet": "0xabc",
                    "max_candidates": payload["max_candidates"],
                    "batch_size": payload["batch_size"],
                    "max_concurrency": payload["max_concurrency"],
                    "candidates_total": 1,
                    "candidates_processed": 1,
                    "cached_hits": 0,
                    "resolved_written": 1,
                    "unresolved_network": 0,
                    "skipped_missing_identifiers": 0,
                    "skipped_unsupported": 0,
                    "errors": 0,
                    "skipped_reasons": {},
                    "warnings": [],
                }
            if path == "/api/run/detectors":
                return {"results": [], "backfill_stats": None}
            if path == "/api/export/user_dossier":
                return {
                    "export_id": "run-enrich",
                    "artifact_path": str(run_root),
                    "proxy_wallet": "0xabc",
                    "username_slug": "testuser",
                }
            raise AssertionError(f"Unexpected scan API path: {path}")

        monkeypatch.setattr(scan, "post_json", fake_post_json)

        config = {
            "user": "@TestUser",
            "max_pages": 10,
            "bucket": "day",
            "backfill": True,
            "ingest_markets": False,
            "ingest_activity": False,
            "ingest_positions": False,
            "compute_pnl": False,
            "compute_opportunities": False,
            "snapshot_books": False,
            "enrich_resolutions": True,
            "resolution_max_candidates": 123,
            "resolution_batch_size": 12,
            "resolution_max_concurrency": 3,
            "api_base_url": "http://localhost:8000",
            "timeout_seconds": 30.0,
        }

        scan.run_scan(
            config=config,
            argv=["--user", "@TestUser", "--enrich-resolutions"],
            started_at="2026-02-06T12:00:00+00:00",
        )

        path_to_payload = {path: payload for path, payload in calls}
        assert "/api/enrich/resolutions" in path_to_payload
        assert path_to_payload["/api/enrich/resolutions"]["max_candidates"] == 123
        assert path_to_payload["/api/enrich/resolutions"]["batch_size"] == 12
        assert path_to_payload["/api/enrich/resolutions"]["max_concurrency"] == 3
    finally:
        os.chdir(original_cwd)
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_scan_trust_artifacts_use_positions_count_fallback_when_rows_missing(monkeypatch):
    tmp_path = Path("artifacts") / "_pytest_scan_trust" / uuid.uuid4().hex
    shutil.rmtree(tmp_path, ignore_errors=True)
    tmp_path.mkdir(parents=True, exist_ok=True)
    original_cwd = Path.cwd()
    try:
        os.chdir(tmp_path)

        run_root = (
            tmp_path
            / "artifacts"
            / "dossiers"
            / "users"
            / "testuser"
            / "0xabc"
            / "2026-02-06"
            / "run-456"
        )
        run_root.mkdir(parents=True, exist_ok=True)
        # Count-only shape: no lifecycle rows, but dossier/history says positions exist.
        (run_root / "dossier.json").write_text(
            json.dumps(
                {
                    "coverage": {"positions_count": 3},
                    "positions": {"count": 3, "positions": []},
                },
                indent=2,
            ),
            encoding="utf-8",
        )

        def fake_post_json(base_url, path, payload, timeout=120.0, retries=3, backoff_seconds=1.0):
            assert base_url == "http://localhost:8000"
            if path == "/api/resolve":
                return {"username": "TestUser", "proxy_wallet": "0xabc"}
            if path == "/api/ingest/trades":
                return {
                    "pages_fetched": 1,
                    "rows_fetched_total": 2,
                    "rows_written": 2,
                    "distinct_trade_uids_total": 2,
                }
            if path == "/api/run/detectors":
                return {"results": [], "backfill_stats": None}
            if path == "/api/export/user_dossier":
                return {
                    "export_id": "run-456",
                    "artifact_path": str(run_root),
                    "proxy_wallet": "0xabc",
                    "username_slug": "testuser",
                }
            raise AssertionError(f"Unexpected scan API path: {path}")

        monkeypatch.setattr(scan, "post_json", fake_post_json)

        config = {
            "user": "@TestUser",
            "max_pages": 10,
            "bucket": "day",
            "backfill": True,
            "ingest_markets": False,
            "ingest_activity": False,
            "ingest_positions": False,
            "compute_pnl": False,
            "compute_opportunities": False,
            "snapshot_books": False,
            "api_base_url": "http://localhost:8000",
            "timeout_seconds": 30.0,
        }

        emitted = scan.run_scan(
            config=config,
            argv=["--user", "@TestUser"],
            started_at="2026-02-06T12:00:00+00:00",
        )
        coverage = json.loads(Path(emitted["coverage_reconciliation_report_json"]).read_text(encoding="utf-8"))
        assert coverage["totals"]["positions_total"] == 3
        assert "trade_uid_coverage" not in coverage
    finally:
        os.chdir(original_cwd)
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_scan_trust_artifacts_hydrates_from_history_when_export_is_empty(monkeypatch):
    tmp_path = Path("artifacts") / "_pytest_scan_trust" / uuid.uuid4().hex
    shutil.rmtree(tmp_path, ignore_errors=True)
    tmp_path.mkdir(parents=True, exist_ok=True)
    original_cwd = Path.cwd()
    try:
        os.chdir(tmp_path)

        run_root = (
            tmp_path
            / "artifacts"
            / "dossiers"
            / "users"
            / "testuser"
            / "0xabc"
            / "2026-02-07"
            / "run-789"
        )
        run_root.mkdir(parents=True, exist_ok=True)
        # Simulate empty latest export payload on disk.
        (run_root / "dossier.json").write_text(
            json.dumps(
                {
                    "coverage": {"positions_count": 0, "trades_count": 0},
                    "positions": {"positions": []},
                    "trades": {"trades": []},
                },
                indent=2,
            ),
            encoding="utf-8",
        )

        history_payload = {
            "positions": {
                "positions": [
                    {
                        "trade_uid": "uid-h1",
                        "resolved_token_id": "tok-h1",
                        "resolution_outcome": "WIN",
                        "realized_pnl_net": 2.5,
                        "position_remaining": 0.0,
                    }
                ]
            },
            "trades": {"count": 4},
            "coverage": {"positions_count": 1, "trades_count": 4},
        }

        def fake_post_json(base_url, path, payload, timeout=120.0, retries=3, backoff_seconds=1.0):
            assert base_url == "http://localhost:8000"
            if path == "/api/resolve":
                return {"username": "TestUser", "proxy_wallet": "0xabc"}
            if path == "/api/ingest/trades":
                return {
                    "pages_fetched": 1,
                    "rows_fetched_total": 1,
                    "rows_written": 1,
                    "distinct_trade_uids_total": 1,
                }
            if path == "/api/run/detectors":
                return {"results": [], "backfill_stats": None}
            if path == "/api/export/user_dossier":
                return {
                    "export_id": "run-789",
                    "artifact_path": str(run_root),
                    "proxy_wallet": "0xabc",
                    "username_slug": "testuser",
                    "stats": {"positions_count": 0, "trades_count": 0},
                }
            raise AssertionError(f"Unexpected scan API path: {path}")

        def fake_get_json(base_url, path, params, timeout=120.0, retries=3, backoff_seconds=1.0):
            assert base_url == "http://localhost:8000"
            assert path == "/api/export/user_dossier/history"
            return {
                "rows": [
                    {
                        "export_id": "run-789",
                        "positions_count": 1,
                        "trades_count": 4,
                        "dossier_json": json.dumps(history_payload),
                        "memo_md": "# hydrated",
                    }
                ]
            }

        monkeypatch.setattr(scan, "post_json", fake_post_json)
        monkeypatch.setattr(scan, "get_json", fake_get_json)

        config = {
            "user": "@TestUser",
            "max_pages": 10,
            "bucket": "day",
            "backfill": True,
            "ingest_markets": False,
            "ingest_activity": False,
            "ingest_positions": False,
            "compute_pnl": False,
            "compute_opportunities": False,
            "snapshot_books": False,
            "debug_export": False,
            "api_base_url": "http://localhost:8000",
            "timeout_seconds": 30.0,
        }

        emitted = scan.run_scan(
            config=config,
            argv=["--user", "@TestUser"],
            started_at="2026-02-07T01:00:00+00:00",
        )

        coverage = json.loads(Path(emitted["coverage_reconciliation_report_json"]).read_text(encoding="utf-8"))
        assert coverage["totals"]["positions_total"] > 0
        assert "deterministic_trade_uid_coverage" in coverage
        assert "fallback_uid_coverage" in coverage
        assert not any("positions_total=0" in warning for warning in coverage["warnings"])

        hydrated = json.loads((run_root / "dossier.json").read_text(encoding="utf-8"))
        hydrated_positions = hydrated["positions"]["positions"]
        assert len(hydrated_positions) == 1
        assert hydrated_positions[0]["trade_uid"] == "uid-h1"
    finally:
        os.chdir(original_cwd)
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_scan_trust_artifacts_warns_when_positions_total_is_zero(monkeypatch, capsys):
    tmp_path = Path("artifacts") / "_pytest_scan_trust" / uuid.uuid4().hex
    shutil.rmtree(tmp_path, ignore_errors=True)
    tmp_path.mkdir(parents=True, exist_ok=True)
    original_cwd = Path.cwd()
    try:
        os.chdir(tmp_path)

        run_root = (
            tmp_path
            / "artifacts"
            / "dossiers"
            / "users"
            / "testuser"
            / "0xabc"
            / "2026-02-07"
            / "run-790"
        )
        run_root.mkdir(parents=True, exist_ok=True)
        (run_root / "dossier.json").write_text(
            json.dumps(
                {
                    "coverage": {"positions_count": 0, "trades_count": 5},
                    "positions": {"positions": []},
                    "trades": {"count": 5},
                },
                indent=2,
            ),
            encoding="utf-8",
        )

        def fake_post_json(base_url, path, payload, timeout=120.0, retries=3, backoff_seconds=1.0):
            assert base_url == "http://localhost:8000"
            if path == "/api/resolve":
                return {"username": "TestUser", "proxy_wallet": "0xabc"}
            if path == "/api/ingest/trades":
                return {
                    "pages_fetched": 1,
                    "rows_fetched_total": 5,
                    "rows_written": 5,
                    "distinct_trade_uids_total": 5,
                }
            if path == "/api/run/detectors":
                return {"results": [], "backfill_stats": None}
            if path == "/api/export/user_dossier":
                return {
                    "export_id": "run-790",
                    "artifact_path": str(run_root),
                    "proxy_wallet": "0xabc",
                    "username_slug": "testuser",
                    "stats": {"positions_count": 0, "trades_count": 5},
                }
            raise AssertionError(f"Unexpected scan API path: {path}")

        def fake_get_json(base_url, path, params, timeout=120.0, retries=3, backoff_seconds=1.0):
            assert base_url == "http://localhost:8000"
            assert path == "/api/export/user_dossier/history"
            return {"rows": []}

        monkeypatch.setattr(scan, "post_json", fake_post_json)
        monkeypatch.setattr(scan, "get_json", fake_get_json)

        config = {
            "user": "@TestUser",
            "max_pages": 10,
            "bucket": "day",
            "backfill": True,
            "ingest_markets": False,
            "ingest_activity": False,
            "ingest_positions": False,
            "compute_pnl": False,
            "compute_opportunities": False,
            "snapshot_books": False,
            "debug_export": False,
            "api_base_url": "http://localhost:8000",
            "timeout_seconds": 30.0,
        }

        emitted = scan.run_scan(
            config=config,
            argv=["--user", "@TestUser"],
            started_at="2026-02-07T02:00:00+00:00",
        )

        captured = capsys.readouterr()
        assert "positions_total=0 for wallet=0xabc" in captured.err
        assert "/api/export/user_dossier/history" in captured.err
        assert "confirm wallet mapping/proxy_wallet" in captured.err

        coverage = json.loads(Path(emitted["coverage_reconciliation_report_json"]).read_text(encoding="utf-8"))
        assert coverage["totals"]["positions_total"] == 0
        assert any("positions_total=0 for wallet=0xabc" in warning for warning in coverage["warnings"])
        assert any("increase lookback" in warning for warning in coverage["warnings"])
    finally:
        os.chdir(original_cwd)
        shutil.rmtree(tmp_path, ignore_errors=True)
