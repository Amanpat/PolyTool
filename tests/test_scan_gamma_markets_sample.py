from __future__ import annotations

import json
import os
import shutil
import uuid
from pathlib import Path

from tools.cli import scan


def test_run_scan_writes_gamma_markets_sample_when_debug_export_enabled(monkeypatch):
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
            / "2026-02-19"
            / "run-gamma-sample"
        )
        run_root.mkdir(parents=True, exist_ok=True)
        (run_root / "dossier.json").write_text(
            json.dumps(
                {
                    "positions": {
                        "positions": [
                            {
                                "resolved_token_id": "tok-1",
                                "resolution_outcome": "PENDING",
                            }
                        ]
                    }
                },
                indent=2,
            ),
            encoding="utf-8",
        )

        sample_payload = {
            "request": {
                "url": "https://gamma-api.polymarket.com/markets",
                "params": {"limit": 100, "offset": 0, "closed": "false"},
            },
            "sample_limit": 10,
            "sample_count": 1,
            "markets": [
                {
                    "keys": ["category", "clobTokenIds", "conditionId", "id", "slug"],
                    "id": "1",
                    "slug": "test-market",
                    "conditionId": "0xabc",
                    "clobTokenIds": '["tok-1","tok-2"]',
                    "category": "Politics",
                    "events_0_category": None,
                    "events_0_subcategory": None,
                }
            ],
        }

        def fake_post_json(base_url, path, payload, timeout=120.0, retries=3, backoff_seconds=1.0):
            if path == "/api/ingest/markets":
                return {
                    "pages_fetched": 1,
                    "markets_total": 1,
                    "market_tokens_written": 2,
                    "gamma_markets_sample": sample_payload,
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
            if path == "/api/export/user_dossier":
                return {
                    "export_id": "run-gamma-sample",
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
            "ingest_markets": True,
            "ingest_activity": False,
            "ingest_positions": False,
            "compute_pnl": False,
            "compute_opportunities": False,
            "snapshot_books": False,
            "enrich_resolutions": False,
            "debug_export": True,
            "api_base_url": "http://localhost:8000",
            "timeout_seconds": 30.0,
        }

        emitted = scan.run_scan(
            config=config,
            argv=["--user", "@TestUser", "--ingest-markets", "--debug-export"],
            started_at="2026-02-19T12:00:00+00:00",
        )

        assert "gamma_markets_sample_json" in emitted
        sample_path = Path(emitted["gamma_markets_sample_json"])
        assert sample_path.exists()
        written = json.loads(sample_path.read_text(encoding="utf-8"))
        assert written["request"]["url"].endswith("/markets")
        assert written["sample_count"] == 1

        manifest = json.loads(Path(emitted["run_manifest"]).read_text(encoding="utf-8"))
        assert manifest["output_paths"]["gamma_markets_sample_json"] == sample_path.as_posix()
    finally:
        os.chdir(original_cwd)
        shutil.rmtree(tmp_path, ignore_errors=True)
