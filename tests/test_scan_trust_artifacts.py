from __future__ import annotations

import argparse
import json
import os
import shutil
import uuid
from pathlib import Path

from tools.cli import scan
from polytool.reports.coverage import PENDING_COVERAGE_INVALID_WARNING


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
        assert Path(emitted["segment_analysis_json"]).exists()
        assert Path(emitted["run_manifest"]).exists()

        coverage = json.loads(Path(emitted["coverage_reconciliation_report_json"]).read_text(encoding="utf-8"))
        assert coverage["totals"]["positions_total"] > 0
        assert "deterministic_trade_uid_coverage" in coverage
        assert "fallback_uid_coverage" in coverage
        assert "segment_analysis" in coverage
        assert "trade_uid_coverage" not in coverage
        assert coverage["deterministic_trade_uid_coverage"]["with_trade_uid"] == 1
        assert coverage["fallback_uid_coverage"]["with_fallback_uid"] == 2
        assert coverage["fallback_uid_coverage"]["fallback_only_count"] == 1

        segment_analysis_payload = json.loads(Path(emitted["segment_analysis_json"]).read_text(encoding="utf-8"))
        assert "segment_analysis" in segment_analysis_payload
        assert "by_entry_price_tier" in segment_analysis_payload["segment_analysis"]

        manifest = json.loads(Path(emitted["run_manifest"]).read_text(encoding="utf-8"))
        assert manifest["command_name"] == "scan"
        assert manifest["run_id"] == "run-123"
        assert manifest["output_paths"]["run_root"] == run_root.as_posix()
        assert manifest["output_paths"]["coverage_reconciliation_report_json"] == emitted[
            "coverage_reconciliation_report_json"
        ]
        assert manifest["output_paths"]["segment_analysis_json"] == emitted["segment_analysis_json"]
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
                    "candidates_selected": 1,
                    "truncated": False,
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


def test_run_scan_orders_resolution_enrichment_after_ingest_positions_and_compute_pnl_when_enabled(
    monkeypatch,
):
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
            / "2026-02-13"
            / "run-ordering"
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

        call_order = []

        def fake_post_json(base_url, path, payload, timeout=120.0, retries=3, backoff_seconds=1.0):
            call_order.append(path)
            if path == "/api/ingest/positions":
                return {
                    "proxy_wallet": "0xabc",
                    "snapshot_ts": "2026-02-13T12:00:00+00:00",
                    "rows_written": 1,
                }
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
            if path == "/api/compute/pnl":
                return {
                    "proxy_wallet": "0xabc",
                    "bucket_type": "day",
                    "buckets_computed": 1,
                    "latest_bucket": {
                        "bucket_start": "2026-02-13T00:00:00+00:00",
                        "realized_pnl": 1.0,
                        "mtm_pnl_estimate": 1.0,
                        "exposure_notional_estimate": 0.0,
                        "open_position_tokens": 0,
                        "pricing_source": "snapshot",
                        "pricing_snapshot_ratio": 1.0,
                        "pricing_confidence": "high",
                    },
                }
            if path == "/api/enrich/resolutions":
                return {
                    "proxy_wallet": "0xabc",
                    "max_candidates": payload["max_candidates"],
                    "batch_size": payload["batch_size"],
                    "max_concurrency": payload["max_concurrency"],
                    "candidates_total": 1,
                    "candidates_selected": 1,
                    "truncated": False,
                    "candidates_processed": 1,
                    "cached_hits": 0,
                    "resolved_written": 1,
                    "unresolved_network": 0,
                    "skipped_missing_identifiers": 0,
                    "skipped_unsupported": 0,
                    "errors": 0,
                    "skipped_reasons": {},
                    "lifecycle_token_universe_size_used_for_selection": 1,
                    "warnings": [],
                }
            if path == "/api/export/user_dossier":
                return {
                    "export_id": "run-ordering",
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
            "ingest_positions": True,
            "compute_pnl": True,
            "compute_opportunities": False,
            "snapshot_books": False,
            "enrich_resolutions": True,
            "api_base_url": "http://localhost:8000",
            "timeout_seconds": 30.0,
        }

        scan.run_scan(
            config=config,
            argv=[
                "--user", "@TestUser",
                "--ingest-positions",
                "--compute-pnl",
                "--enrich-resolutions",
            ],
            started_at="2026-02-13T12:00:00+00:00",
        )

        assert call_order.index("/api/enrich/resolutions") > call_order.index("/api/ingest/positions")
        assert call_order.index("/api/enrich/resolutions") > call_order.index("/api/compute/pnl")
    finally:
        os.chdir(original_cwd)
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_run_scan_cold_start_resolves_on_first_run_when_compute_precedes_enrichment(monkeypatch):
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
            / "2026-02-13"
            / "run-cold-start"
        )
        run_root.mkdir(parents=True, exist_ok=True)

        state = {
            "lifecycle_ready": False,
            "resolved_ready": False,
            "calls": [],
        }

        def fake_post_json(base_url, path, payload, timeout=120.0, retries=3, backoff_seconds=1.0):
            state["calls"].append(path)

            if path == "/api/ingest/positions":
                return {
                    "proxy_wallet": "0xabc",
                    "snapshot_ts": "2026-02-13T12:00:00+00:00",
                    "rows_written": 2,
                }
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
            if path == "/api/compute/pnl":
                state["lifecycle_ready"] = True
                return {
                    "proxy_wallet": "0xabc",
                    "bucket_type": "day",
                    "buckets_computed": 1,
                    "latest_bucket": {
                        "bucket_start": "2026-02-13T00:00:00+00:00",
                        "realized_pnl": 1.0,
                        "mtm_pnl_estimate": 1.0,
                        "exposure_notional_estimate": 0.0,
                        "open_position_tokens": 0,
                        "pricing_source": "snapshot",
                        "pricing_snapshot_ratio": 1.0,
                        "pricing_confidence": "high",
                    },
                }
            if path == "/api/enrich/resolutions":
                lifecycle_universe = 2 if state["lifecycle_ready"] else 0
                state["resolved_ready"] = lifecycle_universe > 0
                return {
                    "proxy_wallet": "0xabc",
                    "max_candidates": payload["max_candidates"],
                    "batch_size": payload["batch_size"],
                    "max_concurrency": payload["max_concurrency"],
                    "candidates_total": 2,
                    "candidates_selected": 2 if lifecycle_universe > 0 else 0,
                    "truncated": False,
                    "candidates_processed": 2 if lifecycle_universe > 0 else 0,
                    "cached_hits": 0,
                    "resolved_written": 2 if lifecycle_universe > 0 else 0,
                    "unresolved_network": 0,
                    "skipped_missing_identifiers": 0,
                    "skipped_unsupported": 0,
                    "errors": 0,
                    "skipped_reasons": {},
                    "lifecycle_token_universe_size_used_for_selection": lifecycle_universe,
                    "warnings": [] if lifecycle_universe > 0 else [
                        "token universe empty; enrichment likely too early (positions_total=2)."
                    ],
                }
            if path == "/api/export/user_dossier":
                positions = [
                    {
                        "trade_uid": "uid-1",
                        "resolved_token_id": "tok-1",
                        "resolution_outcome": "WIN" if state["resolved_ready"] else "PENDING",
                        "realized_pnl_net": 1.0 if state["resolved_ready"] else 0.0,
                        "position_remaining": 0.0 if state["resolved_ready"] else 1.0,
                    },
                    {
                        "trade_uid": "uid-2",
                        "resolved_token_id": "tok-2",
                        "resolution_outcome": "LOSS" if state["resolved_ready"] else "PENDING",
                        "realized_pnl_net": -1.0 if state["resolved_ready"] else 0.0,
                        "position_remaining": 0.0 if state["resolved_ready"] else 1.0,
                    },
                ]
                (run_root / "dossier.json").write_text(
                    json.dumps({"positions": {"positions": positions}}, indent=2),
                    encoding="utf-8",
                )
                return {
                    "export_id": "run-cold-start",
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
            "ingest_positions": True,
            "compute_pnl": True,
            "compute_opportunities": False,
            "snapshot_books": False,
            "enrich_resolutions": True,
            "api_base_url": "http://localhost:8000",
            "timeout_seconds": 30.0,
        }

        emitted = scan.run_scan(
            config=config,
            argv=[
                "--user", "@TestUser",
                "--ingest-positions",
                "--compute-pnl",
                "--enrich-resolutions",
            ],
            started_at="2026-02-13T12:10:00+00:00",
        )

        coverage = json.loads(Path(emitted["coverage_reconciliation_report_json"]).read_text(encoding="utf-8"))
        assert coverage["resolution_coverage"]["resolved_total"] > 0
        assert not any(PENDING_COVERAGE_INVALID_WARNING in warning for warning in coverage["warnings"])

        parity = json.loads(Path(emitted["resolution_parity_debug_json"]).read_text(encoding="utf-8"))
        assert parity["lifecycle_token_universe_size_used_for_selection"] == 2

        assert state["calls"].index("/api/compute/pnl") < state["calls"].index("/api/enrich/resolutions")
    finally:
        os.chdir(original_cwd)
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_run_scan_without_resolution_knobs_uses_safe_default_and_reports_resolved_coverage(
    monkeypatch,
    capsys,
):
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
            / "2026-02-12"
            / "run-default-enrich"
        )
        run_root.mkdir(parents=True, exist_ok=True)
        positions = []
        for idx in range(8):
            positions.append(
                {
                    "trade_uid": f"uid-win-{idx}",
                    "resolved_token_id": f"tok-win-{idx}",
                    "resolution_outcome": "WIN" if idx % 2 == 0 else "LOSS",
                    "realized_pnl_net": 1.0 if idx % 2 == 0 else -1.0,
                    "position_remaining": 0.0,
                }
            )
        positions.append(
            {
                "trade_uid": "uid-pending",
                "resolved_token_id": "tok-pending",
                "resolution_outcome": "PENDING",
                "realized_pnl_net": 0.0,
                "position_remaining": 1.0,
                "sell_count": 0,
            }
        )
        (run_root / "dossier.json").write_text(
            json.dumps({"positions": {"positions": positions}}, indent=2),
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
                    "rows_fetched_total": 9,
                    "rows_written": 9,
                    "distinct_trade_uids_total": 9,
                }
            if path == "/api/enrich/resolutions":
                return {
                    "proxy_wallet": "0xabc",
                    "max_candidates": payload["max_candidates"],
                    "batch_size": payload["batch_size"],
                    "max_concurrency": payload["max_concurrency"],
                    "candidates_total": 640,
                    "candidates_selected": payload["max_candidates"],
                    "truncated": True,
                    "candidates_processed": payload["max_candidates"],
                    "cached_hits": 120,
                    "resolved_written": 48,
                    "unresolved_network": 2,
                    "skipped_missing_identifiers": 0,
                    "skipped_unsupported": 0,
                    "errors": 0,
                    "skipped_reasons": {},
                    "lifecycle_token_universe_size_used_for_selection": 2,
                    "warnings": [],
                }
            if path == "/api/run/detectors":
                return {"results": [], "backfill_stats": None}
            if path == "/api/export/user_dossier":
                return {
                    "export_id": "run-default-enrich",
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
            "api_base_url": "http://localhost:8000",
            "timeout_seconds": 30.0,
        }

        emitted = scan.run_scan(
            config=config,
            argv=["--user", "@TestUser", "--enrich-resolutions"],
            started_at="2026-02-12T12:00:00+00:00",
        )
        captured = capsys.readouterr()

        path_to_payload = {path: payload for path, payload in calls}
        enrich_payload = path_to_payload["/api/enrich/resolutions"]
        assert enrich_payload["max_candidates"] == scan.DEFAULT_RESOLUTION_MAX_CANDIDATES

        coverage = json.loads(Path(emitted["coverage_reconciliation_report_json"]).read_text(encoding="utf-8"))
        assert coverage["resolution_coverage"]["resolved_total"] > 0
        assert coverage["resolution_coverage"]["unknown_resolution_rate"] <= 0.05
        assert "selected=" in captured.out
        assert "truncated=True" in captured.out
    finally:
        os.chdir(original_cwd)
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_scan_trust_artifacts_warns_when_truncated_and_zero_resolved(monkeypatch, capsys):
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
            / "2026-02-12"
            / "run-truncated-warning"
        )
        run_root.mkdir(parents=True, exist_ok=True)
        (run_root / "dossier.json").write_text(
            json.dumps(
                {
                    "positions": {
                        "positions": [
                            {
                                "trade_uid": "uid-p1",
                                "resolved_token_id": "tok-p1",
                                "resolution_outcome": "PENDING",
                                "realized_pnl_net": 0.0,
                                "position_remaining": 1.0,
                                "sell_count": 0,
                            },
                            {
                                "trade_uid": "uid-p2",
                                "resolved_token_id": "tok-p2",
                                "resolution_outcome": "PENDING",
                                "realized_pnl_net": 0.0,
                                "position_remaining": 2.0,
                                "sell_count": 0,
                            },
                        ]
                    }
                },
                indent=2,
            ),
            encoding="utf-8",
        )

        def fake_post_json(base_url, path, payload, timeout=120.0, retries=3, backoff_seconds=1.0):
            if path == "/api/resolve":
                return {"username": "TestUser", "proxy_wallet": "0xabc"}
            if path == "/api/ingest/trades":
                return {
                    "pages_fetched": 1,
                    "rows_fetched_total": 2,
                    "rows_written": 2,
                    "distinct_trade_uids_total": 2,
                }
            if path == "/api/enrich/resolutions":
                return {
                    "proxy_wallet": "0xabc",
                    "max_candidates": payload["max_candidates"],
                    "batch_size": payload["batch_size"],
                    "max_concurrency": payload["max_concurrency"],
                    "candidates_total": 620,
                    "candidates_selected": payload["max_candidates"],
                    "truncated": True,
                    "candidates_processed": payload["max_candidates"],
                    "cached_hits": 0,
                    "resolved_written": 0,
                    "unresolved_network": payload["max_candidates"],
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
                    "export_id": "run-truncated-warning",
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
            "api_base_url": "http://localhost:8000",
            "timeout_seconds": 30.0,
        }

        emitted = scan.run_scan(
            config=config,
            argv=["--user", "@TestUser", "--enrich-resolutions"],
            started_at="2026-02-12T13:00:00+00:00",
        )
        captured = capsys.readouterr()

        coverage = json.loads(Path(emitted["coverage_reconciliation_report_json"]).read_text(encoding="utf-8"))
        assert coverage["totals"]["positions_total"] == 2
        assert coverage["resolution_coverage"]["resolved_total"] == 0
        assert any(
            "resolution_enrichment_truncated_with_zero_resolved" in warning
            for warning in coverage["warnings"]
        )
        assert "resolution_enrichment_truncated_with_zero_resolved" in captured.err
    finally:
        os.chdir(original_cwd)
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_scan_trust_artifacts_warns_when_positions_are_declared_but_rows_missing(monkeypatch, capsys):
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
        captured = capsys.readouterr()
        coverage = json.loads(Path(emitted["coverage_reconciliation_report_json"]).read_text(encoding="utf-8"))
        assert coverage["totals"]["positions_total"] == 0
        assert coverage["resolution_coverage"]["unknown_resolution_rate"] == 0.0
        assert "dossier_declares_positions_count=3 but exported positions rows=0" in captured.err
        assert any(
            "dossier_declares_positions_count=3 but exported positions rows=0" in warning
            for warning in coverage["warnings"]
        )
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


def test_scan_trust_artifacts_history_zero_count_uses_dossier_positions_with_warning(monkeypatch, capsys):
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
            / "run-791"
        )
        run_root.mkdir(parents=True, exist_ok=True)
        # Empty latest export payload on disk forces history lookup.
        (run_root / "dossier.json").write_text(
            json.dumps(
                {
                    "coverage": {"positions_count": 2, "trades_count": 4},
                    "positions": {"count": 2, "positions": []},
                    "trades": {"count": 4},
                },
                indent=2,
            ),
            encoding="utf-8",
        )

        history_payload = {
            "positions": {
                "count": 2,
                "positions": [
                    {
                        "trade_uid": "uid-hz",
                        "resolved_token_id": "tok-hz",
                        "resolution_outcome": "WIN",
                        "realized_pnl_net": 3.25,
                        "position_remaining": 0.0,
                    }
                ],
            },
            "trades": {"count": 4},
            "coverage": {"positions_count": 2, "trades_count": 4},
        }

        def fake_post_json(base_url, path, payload, timeout=120.0, retries=3, backoff_seconds=1.0):
            assert base_url == "http://localhost:8000"
            if path == "/api/resolve":
                return {"username": "TestUser", "proxy_wallet": "0xabc"}
            if path == "/api/ingest/trades":
                return {
                    "pages_fetched": 1,
                    "rows_fetched_total": 4,
                    "rows_written": 4,
                    "distinct_trade_uids_total": 4,
                }
            if path == "/api/run/detectors":
                return {"results": [], "backfill_stats": None}
            if path == "/api/export/user_dossier":
                return {
                    "export_id": "run-791",
                    "artifact_path": str(run_root),
                    "proxy_wallet": "0xabc",
                    "username_slug": "testuser",
                    "stats": {"positions_count": 2, "trades_count": 4},
                }
            raise AssertionError(f"Unexpected scan API path: {path}")

        def fake_get_json(base_url, path, params, timeout=120.0, retries=3, backoff_seconds=1.0):
            assert base_url == "http://localhost:8000"
            assert path == "/api/export/user_dossier/history"
            return {
                "rows": [
                    {
                        "export_id": "run-791",
                        "positions_count": 0,
                        "trades_count": 4,
                        "dossier_json": json.dumps(history_payload),
                        "memo_md": "# history-fallback",
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
            started_at="2026-02-07T03:00:00+00:00",
        )
        captured = capsys.readouterr()

        coverage = json.loads(Path(emitted["coverage_reconciliation_report_json"]).read_text(encoding="utf-8"))
        assert coverage["totals"]["positions_total"] > 0
        fallback_warnings = [
            warning for warning in coverage["warnings"] if "history_positions_fallback_used" in warning
        ]
        assert fallback_warnings, "Expected history fallback warning in coverage warnings"
        fallback_warning = fallback_warnings[0]
        assert "/api/export/user_dossier" in fallback_warning
        assert "/api/export/user_dossier/history" in fallback_warning
        assert "positions_count=0" in fallback_warning
        assert "positions_rows=1" in fallback_warning
        assert "Using dossier positions list for coverage/segment/audit inputs" in fallback_warning
        assert "history_positions_fallback_used" in captured.err

        hydrated = json.loads((run_root / "dossier.json").read_text(encoding="utf-8"))
        hydrated_positions = hydrated["positions"]["positions"]
        assert len(hydrated_positions) == 1
        assert hydrated_positions[0]["trade_uid"] == "uid-hz"
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


def test_build_config_always_includes_resolution_knobs_without_explicit_flags(monkeypatch):
    """build_config must populate resolution knobs even when no --resolution-* flags are passed."""
    monkeypatch.delenv("SCAN_RESOLUTION_MAX_CANDIDATES", raising=False)
    monkeypatch.delenv("SCAN_RESOLUTION_BATCH_SIZE", raising=False)
    monkeypatch.delenv("SCAN_RESOLUTION_MAX_CONCURRENCY", raising=False)

    parser = scan.build_parser()
    args = parser.parse_args(["--user", "@TestUser", "--enrich-resolutions"])
    config = scan.build_config(args)

    assert config["enrich_resolutions"] is True
    assert config["resolution_max_candidates"] == scan.DEFAULT_RESOLUTION_MAX_CANDIDATES
    assert config["resolution_batch_size"] == scan.DEFAULT_RESOLUTION_BATCH_SIZE
    assert config["resolution_max_concurrency"] == scan.DEFAULT_RESOLUTION_MAX_CONCURRENCY


def test_build_config_loads_entry_price_tiers_from_polytool_yaml():
    tmp_path = Path("artifacts") / "_pytest_scan_trust" / uuid.uuid4().hex
    shutil.rmtree(tmp_path, ignore_errors=True)
    tmp_path.mkdir(parents=True, exist_ok=True)
    original_cwd = Path.cwd()
    try:
        os.chdir(tmp_path)
        Path("polytool.yaml").write_text(
            "\n".join(
                [
                    "segment_config:",
                    "  entry_price_tiers:",
                    '    - name: "cheap"',
                    "      max: 0.25",
                    '    - name: "expensive"',
                    "      min: 0.25",
                ]
            ),
            encoding="utf-8",
        )

        parser = scan.build_parser()
        args = parser.parse_args(["--user", "@TestUser"])
        config = scan.build_config(args)
        assert config["entry_price_tiers"] == [
            {"name": "cheap", "max": 0.25},
            {"name": "expensive", "min": 0.25},
        ]
        assert config["fee_config"] == {
            "profit_fee_rate": scan.DEFAULT_PROFIT_FEE_RATE,
            "source_label": scan.DEFAULT_FEE_SOURCE_LABEL,
        }
    finally:
        os.chdir(original_cwd)
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_build_config_loads_fee_config_from_polytool_yaml():
    tmp_path = Path("artifacts") / "_pytest_scan_trust" / uuid.uuid4().hex
    shutil.rmtree(tmp_path, ignore_errors=True)
    tmp_path.mkdir(parents=True, exist_ok=True)
    original_cwd = Path.cwd()
    try:
        os.chdir(tmp_path)
        Path("polytool.yaml").write_text(
            "\n".join(
                [
                    "fee_config:",
                    "  profit_fee_rate: 0.05",
                    '  source_label: "heuristic"',
                ]
            ),
            encoding="utf-8",
        )

        parser = scan.build_parser()
        args = parser.parse_args(["--user", "@TestUser"])
        config = scan.build_config(args)
        assert config["fee_config"] == {
            "profit_fee_rate": 0.05,
            "source_label": "heuristic",
        }
    finally:
        os.chdir(original_cwd)
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_effective_resolution_config_uses_defaults_when_keys_missing():
    """_effective_resolution_config falls back to defaults for missing config keys."""
    config = {"enrich_resolutions": True}
    effective = scan._effective_resolution_config(config)
    assert effective["max_candidates"] == scan.DEFAULT_RESOLUTION_MAX_CANDIDATES
    assert effective["batch_size"] == scan.DEFAULT_RESOLUTION_BATCH_SIZE
    assert effective["max_concurrency"] == scan.DEFAULT_RESOLUTION_MAX_CONCURRENCY


def test_effective_resolution_config_uses_explicit_values():
    """_effective_resolution_config uses explicit config values when present."""
    config = {
        "resolution_max_candidates": 300,
        "resolution_batch_size": 50,
        "resolution_max_concurrency": 8,
    }
    effective = scan._effective_resolution_config(config)
    assert effective["max_candidates"] == 300
    assert effective["batch_size"] == 50
    assert effective["max_concurrency"] == 8


def test_enrichment_payload_includes_knobs_without_explicit_flags(monkeypatch):
    """POST /api/enrich/resolutions payload must include max_candidates/batch_size/max_concurrency
    even when the user only passes --enrich-resolutions without --resolution-* flags."""
    tmp_path = Path("artifacts") / "_pytest_scan_trust" / uuid.uuid4().hex
    shutil.rmtree(tmp_path, ignore_errors=True)
    tmp_path.mkdir(parents=True, exist_ok=True)
    original_cwd = Path.cwd()
    try:
        os.chdir(tmp_path)

        run_root = (
            tmp_path / "artifacts" / "dossiers" / "users" / "testuser"
            / "0xabc" / "2026-02-12" / "run-no-knobs"
        )
        run_root.mkdir(parents=True, exist_ok=True)
        (run_root / "dossier.json").write_text(
            json.dumps({"positions": {"positions": [
                {"trade_uid": "uid-1", "resolved_token_id": "tok-1",
                 "resolution_outcome": "WIN", "realized_pnl_net": 1.0,
                 "position_remaining": 0.0},
            ]}}),
            encoding="utf-8",
        )

        calls = []

        def fake_post_json(base_url, path, payload, timeout=120.0, retries=3, backoff_seconds=1.0):
            calls.append((path, payload))
            if path == "/api/resolve":
                return {"username": "TestUser", "proxy_wallet": "0xabc"}
            if path == "/api/ingest/trades":
                return {"pages_fetched": 1, "rows_fetched_total": 1,
                        "rows_written": 1, "distinct_trade_uids_total": 1}
            if path == "/api/enrich/resolutions":
                return {
                    "proxy_wallet": "0xabc",
                    "max_candidates": payload["max_candidates"],
                    "batch_size": payload["batch_size"],
                    "max_concurrency": payload["max_concurrency"],
                    "candidates_total": 1, "candidates_selected": 1,
                    "truncated": False, "candidates_processed": 1,
                    "cached_hits": 0, "resolved_written": 1,
                    "unresolved_network": 0, "skipped_missing_identifiers": 0,
                    "skipped_unsupported": 0, "errors": 0,
                    "skipped_reasons": {}, "warnings": [],
                }
            if path == "/api/run/detectors":
                return {"results": [], "backfill_stats": None}
            if path == "/api/export/user_dossier":
                return {"export_id": "run-no-knobs", "artifact_path": str(run_root),
                        "proxy_wallet": "0xabc", "username_slug": "testuser"}
            raise AssertionError(f"Unexpected scan API path: {path}")

        monkeypatch.setattr(scan, "post_json", fake_post_json)

        # Config without explicit resolution knobs (simulates --enrich-resolutions only).
        config = {
            "user": "@TestUser", "max_pages": 10, "bucket": "day",
            "backfill": True, "ingest_markets": False,
            "ingest_activity": False, "ingest_positions": False,
            "compute_pnl": False, "compute_opportunities": False,
            "snapshot_books": False, "enrich_resolutions": True,
            "api_base_url": "http://localhost:8000", "timeout_seconds": 30.0,
        }

        scan.run_scan(config=config, argv=["--user", "@TestUser", "--enrich-resolutions"],
                       started_at="2026-02-12T12:00:00+00:00")

        path_to_payload = {path: payload for path, payload in calls}
        enrich_payload = path_to_payload["/api/enrich/resolutions"]

        # Even without explicit config keys, payload must include all three knobs.
        assert enrich_payload["max_candidates"] == scan.DEFAULT_RESOLUTION_MAX_CANDIDATES
        assert enrich_payload["batch_size"] == scan.DEFAULT_RESOLUTION_BATCH_SIZE
        assert enrich_payload["max_concurrency"] == scan.DEFAULT_RESOLUTION_MAX_CONCURRENCY
    finally:
        os.chdir(original_cwd)
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_parity_debug_artifact_emitted_with_enrichment(monkeypatch):
    """When enrich_resolutions is enabled, a resolution_parity_debug.json artifact must be emitted."""
    tmp_path = Path("artifacts") / "_pytest_scan_trust" / uuid.uuid4().hex
    shutil.rmtree(tmp_path, ignore_errors=True)
    tmp_path.mkdir(parents=True, exist_ok=True)
    original_cwd = Path.cwd()
    try:
        os.chdir(tmp_path)

        run_root = (
            tmp_path / "artifacts" / "dossiers" / "users" / "testuser"
            / "0xabc" / "2026-02-12" / "run-parity"
        )
        run_root.mkdir(parents=True, exist_ok=True)
        (run_root / "dossier.json").write_text(
            json.dumps({"positions": {"positions": [
                {"trade_uid": "uid-1", "resolved_token_id": "tok-1",
                 "resolution_outcome": "WIN", "realized_pnl_net": 1.0,
                 "position_remaining": 0.0},
                {"trade_uid": "uid-2", "resolved_token_id": "tok-2",
                 "resolution_outcome": "LOSS", "realized_pnl_net": -0.5,
                 "position_remaining": 0.0},
            ]}}),
            encoding="utf-8",
        )

        def fake_post_json(base_url, path, payload, timeout=120.0, retries=3, backoff_seconds=1.0):
            if path == "/api/resolve":
                return {"username": "TestUser", "proxy_wallet": "0xabc"}
            if path == "/api/ingest/trades":
                return {"pages_fetched": 1, "rows_fetched_total": 2,
                        "rows_written": 2, "distinct_trade_uids_total": 2}
            if path == "/api/enrich/resolutions":
                return {
                    "proxy_wallet": "0xabc",
                    "max_candidates": payload["max_candidates"],
                    "batch_size": payload["batch_size"],
                    "max_concurrency": payload["max_concurrency"],
                    "candidates_total": 2, "candidates_selected": 2,
                    "truncated": False, "candidates_processed": 2,
                    "cached_hits": 1, "resolved_written": 1,
                    "unresolved_network": 0, "skipped_missing_identifiers": 0,
                    "skipped_unsupported": 0, "errors": 0,
                    "skipped_reasons": {},
                    "lifecycle_token_universe_size_used_for_selection": 2,
                    "warnings": [],
                }
            if path == "/api/run/detectors":
                return {"results": [], "backfill_stats": None}
            if path == "/api/export/user_dossier":
                return {"export_id": "run-parity", "artifact_path": str(run_root),
                        "proxy_wallet": "0xabc", "username_slug": "testuser"}
            raise AssertionError(f"Unexpected scan API path: {path}")

        monkeypatch.setattr(scan, "post_json", fake_post_json)

        config = {
            "user": "@TestUser", "max_pages": 10, "bucket": "day",
            "backfill": True, "ingest_markets": False,
            "ingest_activity": False, "ingest_positions": False,
            "compute_pnl": False, "compute_opportunities": False,
            "snapshot_books": False, "enrich_resolutions": True,
            "resolution_max_candidates": 500,
            "resolution_batch_size": 25,
            "resolution_max_concurrency": 4,
            "api_base_url": "http://localhost:8000", "timeout_seconds": 30.0,
        }

        emitted = scan.run_scan(
            config=config,
            argv=["--user", "@TestUser", "--enrich-resolutions"],
            started_at="2026-02-12T14:00:00+00:00",
        )

        # Verify parity debug artifact exists and contains expected fields.
        assert "resolution_parity_debug_json" in emitted
        parity_path = Path(emitted["resolution_parity_debug_json"])
        assert parity_path.exists()

        parity = json.loads(parity_path.read_text(encoding="utf-8"))
        assert "positions_identity_hash" in parity
        assert len(parity["positions_identity_hash"]) == 64  # sha256 hex
        assert parity["positions_count"] == 2
        assert len(parity["identifiers_sample"]) == 2
        assert parity["enrichment_request_payload"]["max_candidates"] == 500
        assert parity["enrichment_request_payload"]["batch_size"] == 25
        assert parity["enrichment_request_payload"]["max_concurrency"] == 4
        assert parity["enrichment_response_summary"]["candidates_total"] == 2
        assert parity["enrichment_response_summary"]["truncated"] is False
        assert parity["lifecycle_token_universe_size_used_for_selection"] == 2

        # Verify run_manifest includes enrichment effective config.
        manifest = json.loads(Path(emitted["run_manifest"]).read_text(encoding="utf-8"))
        assert manifest["output_paths"]["resolution_parity_debug_json"] == parity_path.as_posix()
    finally:
        os.chdir(original_cwd)
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_positions_identity_hash_stable_across_order():
    """_positions_identity_hash must produce the same hash regardless of input order."""
    positions_a = [
        {"resolved_token_id": "tok-1", "resolution_outcome": "WIN"},
        {"resolved_token_id": "tok-2", "resolution_outcome": "LOSS"},
    ]
    positions_b = [
        {"resolved_token_id": "tok-2", "resolution_outcome": "LOSS"},
        {"resolved_token_id": "tok-1", "resolution_outcome": "WIN"},
    ]
    assert scan._positions_identity_hash(positions_a) == scan._positions_identity_hash(positions_b)


def test_positions_identity_hash_differs_for_different_positions():
    """_positions_identity_hash must differ when position identifiers change."""
    positions_a = [{"resolved_token_id": "tok-1", "resolution_outcome": "WIN"}]
    positions_b = [{"resolved_token_id": "tok-99", "resolution_outcome": "WIN"}]
    assert scan._positions_identity_hash(positions_a) != scan._positions_identity_hash(positions_b)


def test_run_scan_writes_audit_report_when_audit_sample_set(monkeypatch):
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
            / "2026-02-18"
            / "run-audit"
        )
        run_root.mkdir(parents=True, exist_ok=True)
        (run_root / "dossier.json").write_text(
            json.dumps(
                {
                    "positions": {
                        "positions": [
                            {
                                "token_id": "tok-1",
                                "market_slug": "market-1",
                                "resolution_outcome": "WIN",
                                "gross_pnl": 10.0,
                                "entry_price": 0.5,
                            },
                            {
                                "token_id": "tok-2",
                                "market_slug": "market-2",
                                "resolution_outcome": "LOSS",
                                "gross_pnl": -3.0,
                                "entry_price": 0.4,
                            },
                            {
                                "token_id": "tok-3",
                                "market_slug": "market-3",
                                "resolution_outcome": "PENDING",
                                "gross_pnl": 0.0,
                                "entry_price": 0.6,
                            },
                            {
                                "token_id": "tok-4",
                                "market_slug": "market-4",
                                "resolution_outcome": "WIN",
                                "gross_pnl": 4.0,
                                "entry_price": 0.45,
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
                    "rows_fetched_total": 4,
                    "rows_written": 4,
                    "distinct_trade_uids_total": 4,
                }
            if path == "/api/run/detectors":
                return {"results": [], "backfill_stats": None}
            if path == "/api/export/user_dossier":
                return {
                    "export_id": "run-audit",
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
            "audit_sample": 3,
            "audit_seed": 77,
        }

        emitted = scan.run_scan(
            config=config,
            argv=["--user", "@TestUser", "--audit-sample", "3", "--audit-seed", "77"],
            started_at="2026-02-18T12:00:00+00:00",
        )

        assert "audit_coverage_report_md" in emitted
        audit_path = Path(emitted["audit_coverage_report_md"])
        assert audit_path.exists()
        audit_text = audit_path.read_text(encoding="utf-8")
        assert "## Samples (3)" in audit_text

        manifest = json.loads(Path(emitted["run_manifest"]).read_text(encoding="utf-8"))
        assert manifest["output_paths"]["audit_coverage_report_md"] == audit_path.as_posix()
    finally:
        os.chdir(original_cwd)
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_run_scan_audit_sampling_is_deterministic_with_seed(monkeypatch):
    tmp_path = Path("artifacts") / "_pytest_scan_trust" / uuid.uuid4().hex
    shutil.rmtree(tmp_path, ignore_errors=True)
    tmp_path.mkdir(parents=True, exist_ok=True)
    original_cwd = Path.cwd()
    try:
        os.chdir(tmp_path)

        positions = [
            {
                "token_id": f"tok-{i}",
                "condition_id": f"cond-{i}",
                "market_slug": f"market-{i}",
                "resolution_outcome": "WIN" if i % 2 == 0 else "PENDING",
                "gross_pnl": float(i + 1) if i % 2 == 0 else 0.0,
                "entry_price": 0.5,
            }
            for i in range(10)
        ]

        run_root_a = (
            tmp_path / "artifacts" / "dossiers" / "users" / "testuser" / "0xabc" / "2026-02-18" / "run-seed-a"
        )
        run_root_b = (
            tmp_path / "artifacts" / "dossiers" / "users" / "testuser" / "0xabc" / "2026-02-18" / "run-seed-b"
        )
        for run_root in (run_root_a, run_root_b):
            run_root.mkdir(parents=True, exist_ok=True)
            (run_root / "dossier.json").write_text(
                json.dumps({"positions": {"positions": positions}}, indent=2),
                encoding="utf-8",
            )

        state = {"export_calls": 0}

        def fake_post_json(base_url, path, payload, timeout=120.0, retries=3, backoff_seconds=1.0):
            assert base_url == "http://localhost:8000"
            if path == "/api/resolve":
                return {"username": "TestUser", "proxy_wallet": "0xabc"}
            if path == "/api/ingest/trades":
                return {
                    "pages_fetched": 1,
                    "rows_fetched_total": len(positions),
                    "rows_written": len(positions),
                    "distinct_trade_uids_total": len(positions),
                }
            if path == "/api/run/detectors":
                return {"results": [], "backfill_stats": None}
            if path == "/api/export/user_dossier":
                state["export_calls"] += 1
                if state["export_calls"] == 1:
                    return {
                        "export_id": "run-seed-a",
                        "artifact_path": str(run_root_a),
                        "proxy_wallet": "0xabc",
                        "username_slug": "testuser",
                    }
                return {
                    "export_id": "run-seed-b",
                    "artifact_path": str(run_root_b),
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
            "audit_sample": 5,
            "audit_seed": 1337,
        }

        emitted_a = scan.run_scan(
            config=config,
            argv=["--user", "@TestUser", "--audit-sample", "5", "--audit-seed", "1337"],
            started_at="2026-02-18T12:00:00+00:00",
        )
        emitted_b = scan.run_scan(
            config=config,
            argv=["--user", "@TestUser", "--audit-sample", "5", "--audit-seed", "1337"],
            started_at="2026-02-18T12:10:00+00:00",
        )

        report_a = Path(emitted_a["audit_coverage_report_md"]).read_text(encoding="utf-8")
        report_b = Path(emitted_b["audit_coverage_report_md"]).read_text(encoding="utf-8")

        sampled_slugs_a = [
            line.strip()
            for line in report_a.splitlines()
            if line.strip().startswith("- **market_slug**:")
        ]
        sampled_slugs_b = [
            line.strip()
            for line in report_b.splitlines()
            if line.strip().startswith("- **market_slug**:")
        ]

        assert len(sampled_slugs_a) == 5
        assert sampled_slugs_a == sampled_slugs_b
    finally:
        os.chdir(original_cwd)
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_run_scan_emits_audit_all_by_default(monkeypatch):
    """scan emits audit_coverage_report.md by default (no --audit-sample) with ALL positions."""
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
            / "2026-02-18"
            / "run-audit-default"
        )
        run_root.mkdir(parents=True, exist_ok=True)
        (run_root / "dossier.json").write_text(
            json.dumps(
                {
                    "positions": {
                        "positions": [
                            {
                                "token_id": f"tok-{i}",
                                "market_slug": f"market-{i}",
                                "resolution_outcome": "WIN" if i % 2 == 0 else "PENDING",
                                "gross_pnl": 5.0 if i % 2 == 0 else 0.0,
                                "entry_price": 0.5,
                            }
                            for i in range(4)
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
                    "rows_fetched_total": 4,
                    "rows_written": 4,
                    "distinct_trade_uids_total": 4,
                }
            if path == "/api/run/detectors":
                return {"results": [], "backfill_stats": None}
            if path == "/api/export/user_dossier":
                return {
                    "export_id": "run-audit-default",
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
            # No audit_sample key — default should emit ALL positions
        }

        emitted = scan.run_scan(
            config=config,
            argv=["--user", "@TestUser"],
            started_at="2026-02-18T12:00:00+00:00",
        )

        # Audit report must always be present in output_paths
        assert "audit_coverage_report_md" in emitted
        audit_path = Path(emitted["audit_coverage_report_md"])
        assert audit_path.exists()
        audit_text = audit_path.read_text(encoding="utf-8")

        # Default mode shows "All Positions", not "Samples"
        assert "## All Positions" in audit_text
        assert "## Samples" not in audit_text

        # All 4 positions must be present
        position_blocks = [
            line for line in audit_text.splitlines() if line.startswith("### Position ")
        ]
        assert len(position_blocks) == 4

        manifest = json.loads(Path(emitted["run_manifest"]).read_text(encoding="utf-8"))
        assert manifest["output_paths"]["audit_coverage_report_md"] == audit_path.as_posix()
    finally:
        os.chdir(original_cwd)
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_run_scan_audit_sample_3_uses_samples_heading(monkeypatch):
    """scan --audit-sample 3 limits to 3 blocks and uses 'Samples' heading."""
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
            / "2026-02-18"
            / "run-audit-sample3"
        )
        run_root.mkdir(parents=True, exist_ok=True)
        (run_root / "dossier.json").write_text(
            json.dumps(
                {
                    "positions": {
                        "positions": [
                            {
                                "token_id": f"tok-s{i}",
                                "market_slug": f"market-s{i}",
                                "resolution_outcome": "WIN",
                                "gross_pnl": 5.0,
                                "entry_price": 0.5,
                            }
                            for i in range(6)
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
                    "rows_fetched_total": 6,
                    "rows_written": 6,
                    "distinct_trade_uids_total": 6,
                }
            if path == "/api/run/detectors":
                return {"results": [], "backfill_stats": None}
            if path == "/api/export/user_dossier":
                return {
                    "export_id": "run-audit-sample3",
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
            "audit_sample": 3,
            "audit_seed": 42,
        }

        emitted = scan.run_scan(
            config=config,
            argv=["--user", "@TestUser", "--audit-sample", "3", "--audit-seed", "42"],
            started_at="2026-02-18T12:00:00+00:00",
        )

        assert "audit_coverage_report_md" in emitted
        audit_path = Path(emitted["audit_coverage_report_md"])
        assert audit_path.exists()
        audit_text = audit_path.read_text(encoding="utf-8")

        # Explicit sample uses "Samples" heading
        assert "## Samples (3)" in audit_text
        assert "## All Positions" not in audit_text

        # Exactly 3 position blocks
        position_blocks = [
            line for line in audit_text.splitlines() if line.startswith("### Position ")
        ]
        assert len(position_blocks) == 3
    finally:
        os.chdir(original_cwd)
        shutil.rmtree(tmp_path, ignore_errors=True)
