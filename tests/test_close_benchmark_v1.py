"""Offline tests for the benchmark closure orchestrator (close-benchmark-v1).

Scenarios:
  1. Full dry-run flow — preflight + dry-run stages + blocked finalization
  2. Silver success, new-market skipped — benchmark still blocked
  3. Silver success + benchmark still blocked — residual blockers surfaced
  4. New-market planner insufficiency — capture skipped, blockers surfaced
  5. Final manifest validation pass — manifest written by Silver refresh
  6. Resumable rerun — manifest already exists before run starts
  7. CLI smoke — main() dry-run with --help and --dry-run

All tests are offline: no ClickHouse, no network calls.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

_project_root = Path(__file__).parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from tools.cli.close_benchmark_v1 import (
    _all_unique_token_ids,
    _check_clickhouse,
    _priority1_token_ids,
    _read_gap_report,
    main,
    run_closure,
    run_finalization,
    run_new_market_stage,
    run_preflight,
    run_silver_gap_fill_stage,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_TARGETS_JSON = {
    "schema_version": "benchmark_gap_fill_v1",
    "targets": [
        {
            "bucket": "politics",
            "priority": 1,
            "token_id": "0xAAA111",
            "slug": "politics-market-1",
            "market_id": "0xMKT1",
            "window_start": "2024-01-01T00:00:00Z",
            "window_end":   "2024-01-01T02:00:00Z",
        },
        {
            "bucket": "sports",
            "priority": 1,
            "token_id": "0xBBB222",
            "slug": "sports-market-1",
            "market_id": "0xMKT2",
            "window_start": "2024-01-02T00:00:00Z",
            "window_end":   "2024-01-02T02:00:00Z",
        },
        {
            "bucket": "crypto",
            "priority": 2,            # priority-2, should NOT appear in priority1 list
            "token_id": "0xCCC333",
            "slug": "crypto-market-1",
            "market_id": "0xMKT3",
            "window_start": "2024-01-03T00:00:00Z",
            "window_end":   "2024-01-03T02:00:00Z",
        },
    ],
}

_GAP_REPORT_JSON = {
    "schema_version": "benchmark_tape_gap_report_v1",
    "manifest_exists": False,
    "shortages_by_bucket": {
        "politics": 9,
        "sports": 11,
        "crypto": 10,
        "near_resolution": 9,
        "new_market": 5,
    },
}

_NEW_MARKET_TARGETS_JSON = {
    "schema_version": "benchmark_new_market_capture_v1",
    "targets": [
        {"slug": "new-mkt-1", "token_id": "0xNM1", "priority": 1, "record_duration_seconds": 3600},
        {"slug": "new-mkt-2", "token_id": "0xNM2", "priority": 2, "record_duration_seconds": 3600},
        {"slug": "new-mkt-3", "token_id": "0xNM3", "priority": 3, "record_duration_seconds": 3600},
        {"slug": "new-mkt-4", "token_id": "0xNM4", "priority": 4, "record_duration_seconds": 3600},
        {"slug": "new-mkt-5", "token_id": "0xNM5", "priority": 5, "record_duration_seconds": 3600},
    ],
}

_VALID_MANIFEST_JSON = [
    {"tape_path": "artifacts/silver/token1/events.jsonl"},
    {"tape_path": "artifacts/simtrader/tapes/gold1/events.jsonl"},
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write(path: Path, data: dict | list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


# ---------------------------------------------------------------------------
# Unit tests: helpers
# ---------------------------------------------------------------------------

class TestHelpers(unittest.TestCase):
    def test_priority1_token_ids_filters_correctly(self):
        targets = _TARGETS_JSON["targets"]
        ids = _priority1_token_ids(targets)
        self.assertEqual(ids, ["0xAAA111", "0xBBB222"])
        # priority-2 entry must not appear
        self.assertNotIn("0xCCC333", ids)

    def test_priority1_token_ids_empty_list(self):
        self.assertEqual(_priority1_token_ids([]), [])

    def test_priority1_token_ids_skips_malformed(self):
        targets = [None, "bad", {"priority": 1}]  # missing token_id
        self.assertEqual(_priority1_token_ids(targets), [])

    def test_read_gap_report_returns_none_on_missing(self):
        result = _read_gap_report(Path("/nonexistent/path/gap.json"))
        self.assertIsNone(result)

    def test_check_clickhouse_returns_error_on_unreachable(self):
        result = _check_clickhouse("localhost", 19999)
        self.assertFalse(result["available"])
        self.assertIn("error", result)

    # ------------------------------------------------------------------
    # _all_unique_token_ids — regression tests for full-target prefetch
    # ------------------------------------------------------------------

    def test_all_unique_token_ids_includes_all_priorities(self):
        """All targets regardless of priority contribute their token_id."""
        targets = _TARGETS_JSON["targets"]
        ids = _all_unique_token_ids(targets)
        self.assertIn("0xAAA111", ids)  # priority-1
        self.assertIn("0xBBB222", ids)  # priority-1
        self.assertIn("0xCCC333", ids)  # priority-2 — must now be included
        self.assertEqual(len(ids), 3)

    def test_all_unique_token_ids_deduplicates(self):
        """Duplicate token_ids across buckets appear only once."""
        targets = [
            {"bucket": "politics", "priority": 1, "token_id": "0xDUP"},
            {"bucket": "sports",   "priority": 2, "token_id": "0xDUP"},
            {"bucket": "crypto",   "priority": 1, "token_id": "0xUNIQ"},
        ]
        ids = _all_unique_token_ids(targets)
        self.assertEqual(ids.count("0xDUP"), 1, "duplicate token must appear only once")
        self.assertIn("0xUNIQ", ids)
        self.assertEqual(len(ids), 2)

    def test_all_unique_token_ids_empty_list(self):
        self.assertEqual(_all_unique_token_ids([]), [])

    def test_all_unique_token_ids_skips_malformed(self):
        targets = [None, "bad", {"priority": 1}]  # missing token_id
        self.assertEqual(_all_unique_token_ids(targets), [])

    def test_all_unique_token_ids_returns_more_than_priority1(self):
        """Regression: _all_unique_token_ids must include more tokens than _priority1_token_ids
        when overflow (priority > 1) targets exist."""
        targets = _TARGETS_JSON["targets"]
        all_ids = _all_unique_token_ids(targets)
        p1_ids = _priority1_token_ids(targets)
        self.assertGreater(len(all_ids), len(p1_ids),
                           "full-target set must be larger than priority-1 subset when overflows exist")


# ---------------------------------------------------------------------------
# Scenario 1: Full dry-run flow
# ---------------------------------------------------------------------------

class TestFullDryRunFlow(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.tmp = Path(self.tmpdir.name)
        self.targets_path = self.tmp / "targets.json"
        self.manifest_path = self.tmp / "manifest.json"
        self.gap_report_path = self.tmp / "gap_report.json"
        self.artifact_out = self.tmp / "artifact.json"
        _write(self.targets_path, _TARGETS_JSON)
        _write(self.gap_report_path, _GAP_REPORT_JSON)

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_dry_run_produces_blocked_artifact(self):
        with (
            patch("tools.cli.close_benchmark_v1.GAP_FILL_TARGETS_PATH", self.targets_path),
            patch("tools.cli.close_benchmark_v1.MANIFEST_PATH", self.manifest_path),
            patch("tools.cli.close_benchmark_v1.GAP_REPORT_PATH", self.gap_report_path),
            patch("tools.cli.close_benchmark_v1.NEW_MARKET_TARGETS_PATH", self.tmp / "nm_targets.json"),
            patch("tools.cli.close_benchmark_v1.NEW_MARKET_INSUFF_PATH", self.tmp / "nm_insuff.json"),
            patch("tools.cli.close_benchmark_v1.GAP_FILL_INSUFF_PATH", self.tmp / "gf_insuff.json"),
            patch("tools.cli.close_benchmark_v1._check_clickhouse", return_value={"available": True}),
        ):
            artifact, exit_code = run_closure(
                dry_run=True,
                out_path=self.artifact_out,
                _fetch_price_2min_main=MagicMock(return_value=0),
                _new_market_capture_main=MagicMock(return_value=0),
                _capture_new_market_tapes_main=MagicMock(return_value=0),
            )

        # Exit code 1 because manifest not created in dry-run
        self.assertEqual(exit_code, 1)
        self.assertEqual(artifact["final_status"], "blocked")
        self.assertTrue(artifact["dry_run"])
        self.assertEqual(artifact["schema_version"], "benchmark_closure_run_v1")

        # Silver and new-market stages should be dry_run
        self.assertEqual(artifact["silver_gap_fill"]["status"], "dry_run")
        self.assertEqual(artifact["new_market_capture"]["status"], "dry_run")

        # Artifact file written
        self.assertTrue(self.artifact_out.exists())
        on_disk = json.loads(self.artifact_out.read_text())
        self.assertEqual(on_disk["final_status"], "blocked")

    def test_dry_run_silver_reports_planned_tokens(self):
        with (
            patch("tools.cli.close_benchmark_v1.GAP_FILL_TARGETS_PATH", self.targets_path),
            patch("tools.cli.close_benchmark_v1.MANIFEST_PATH", self.manifest_path),
            patch("tools.cli.close_benchmark_v1.GAP_REPORT_PATH", self.gap_report_path),
            patch("tools.cli.close_benchmark_v1.NEW_MARKET_TARGETS_PATH", self.tmp / "nm_targets.json"),
            patch("tools.cli.close_benchmark_v1.NEW_MARKET_INSUFF_PATH", self.tmp / "nm_insuff.json"),
            patch("tools.cli.close_benchmark_v1.GAP_FILL_INSUFF_PATH", self.tmp / "gf_insuff.json"),
            patch("tools.cli.close_benchmark_v1._check_clickhouse", return_value={"available": True}),
        ):
            artifact, _ = run_closure(
                dry_run=True,
                out_path=self.artifact_out,
            )

        silver = artifact["silver_gap_fill"]
        self.assertEqual(silver["status"], "dry_run")
        fetch = silver["fetch_price_2min"]
        self.assertEqual(fetch["status"], "dry_run")
        # ALL unique token IDs planned (priority-1 and priority-2)
        self.assertIn("0xAAA111", fetch["planned_tokens"])
        self.assertIn("0xBBB222", fetch["planned_tokens"])
        # priority-2 token now included — fix for price_2min_missing on overflow targets
        self.assertIn("0xCCC333", fetch["planned_tokens"])
        # token_count covers all 3 targets
        self.assertEqual(fetch["token_count"], 3)


# ---------------------------------------------------------------------------
# Scenario 2 + 3: Silver success, new-market skipped, benchmark still blocked
# ---------------------------------------------------------------------------

class TestSilverSuccessNewMarketSkipped(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.tmp = Path(self.tmpdir.name)
        self.targets_path = self.tmp / "targets.json"
        self.manifest_path = self.tmp / "manifest.json"
        self.gap_report_path = self.tmp / "gap_report.json"
        self.artifact_out = self.tmp / "artifact.json"
        _write(self.targets_path, _TARGETS_JSON)
        _write(self.gap_report_path, _GAP_REPORT_JSON)

    def tearDown(self):
        self.tmpdir.cleanup()

    def _mock_run_batch(self, *args, **kwargs):
        return {
            "schema_version": "benchmark_gap_fill_run_v1",
            "targets_attempted": 3,
            "tapes_created": 2,
            "failure_count": 0,
            "skip_count": 1,
        }

    def _mock_refresh_blocked(self):
        return {
            "triggered": True,
            "return_code": 2,
            "manifest_written": False,
            "outcome": "gap_report_updated",
            "manifest_path": None,
            "gap_report_path": str(self.gap_report_path),
        }

    def test_silver_success_new_market_skipped_blocked_result(self):
        mock_fetch = MagicMock(return_value=0)

        with (
            patch("tools.cli.close_benchmark_v1.GAP_FILL_TARGETS_PATH", self.targets_path),
            patch("tools.cli.close_benchmark_v1.MANIFEST_PATH", self.manifest_path),
            patch("tools.cli.close_benchmark_v1.GAP_REPORT_PATH", self.gap_report_path),
            patch("tools.cli.close_benchmark_v1.NEW_MARKET_TARGETS_PATH", self.tmp / "nm_t.json"),
            patch("tools.cli.close_benchmark_v1.NEW_MARKET_INSUFF_PATH", self.tmp / "nm_i.json"),
            patch("tools.cli.close_benchmark_v1.GAP_FILL_INSUFF_PATH", self.tmp / "gf_i.json"),
            patch("tools.cli.close_benchmark_v1._check_clickhouse", return_value={"available": True}),
            patch("tools.cli.batch_reconstruct_silver.run_batch_from_targets", side_effect=self._mock_run_batch),
            patch("tools.cli.batch_reconstruct_silver._refresh_benchmark_curation", side_effect=self._mock_refresh_blocked),
        ):
            artifact, exit_code = run_closure(
                dry_run=False,
                skip_new_market=True,
                out_path=self.artifact_out,
                _fetch_price_2min_main=mock_fetch,
            )

        self.assertEqual(exit_code, 1)
        self.assertEqual(artifact["final_status"], "blocked")

        # Silver stage ran
        silver = artifact["silver_gap_fill"]
        self.assertEqual(silver["status"], "completed")
        self.assertEqual(silver["batch_reconstruct"]["tapes_created"], 2)

        # New-market stage was skipped
        nm = artifact["new_market_capture"]
        self.assertEqual(nm["status"], "skipped")
        self.assertIn("skip-new-market", nm["reason"])

        # fetch-price-2min was called with ALL unique token IDs (not just priority-1)
        mock_fetch.assert_called_once()
        call_argv = mock_fetch.call_args[0][0]
        self.assertIn("0xAAA111", call_argv)
        self.assertIn("0xBBB222", call_argv)
        # priority-2 token now included — fix for price_2min_missing on overflow targets
        self.assertIn("0xCCC333", call_argv)

    def test_residual_blockers_surfaced_from_gap_report(self):
        with (
            patch("tools.cli.close_benchmark_v1.GAP_FILL_TARGETS_PATH", self.targets_path),
            patch("tools.cli.close_benchmark_v1.MANIFEST_PATH", self.manifest_path),
            patch("tools.cli.close_benchmark_v1.GAP_REPORT_PATH", self.gap_report_path),
            patch("tools.cli.close_benchmark_v1.NEW_MARKET_TARGETS_PATH", self.tmp / "nm_t.json"),
            patch("tools.cli.close_benchmark_v1.NEW_MARKET_INSUFF_PATH", self.tmp / "nm_i.json"),
            patch("tools.cli.close_benchmark_v1.GAP_FILL_INSUFF_PATH", self.tmp / "gf_i.json"),
            patch("tools.cli.close_benchmark_v1._check_clickhouse", return_value={"available": True}),
            patch("tools.cli.batch_reconstruct_silver.run_batch_from_targets", side_effect=self._mock_run_batch),
            patch("tools.cli.batch_reconstruct_silver._refresh_benchmark_curation", side_effect=self._mock_refresh_blocked),
        ):
            artifact, _ = run_closure(
                dry_run=False,
                skip_new_market=True,
                out_path=self.artifact_out,
                _fetch_price_2min_main=MagicMock(return_value=0),
            )

        blockers = artifact["residual_blockers"]
        self.assertTrue(len(blockers) >= 3, f"Expected >=3 blockers, got: {blockers}")
        blocker_text = " ".join(blockers)
        self.assertIn("politics", blocker_text)
        self.assertIn("sports", blocker_text)
        self.assertIn("crypto", blocker_text)


# ---------------------------------------------------------------------------
# Scenario 4: New-market planner insufficiency
# ---------------------------------------------------------------------------

class TestNewMarketPlannerInsufficiency(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.tmp = Path(self.tmpdir.name)
        self.manifest_path = self.tmp / "manifest.json"
        self.gap_report_path = self.tmp / "gap_report.json"
        self.nm_insuff_path = self.tmp / "nm_insuff.json"
        self.artifact_out = self.tmp / "artifact.json"
        _write(self.gap_report_path, _GAP_REPORT_JSON)
        _write(self.nm_insuff_path, {
            "schema_version": "benchmark_new_market_capture_insufficiency_v1",
            "candidates_found": 0,
            "required": 5,
            "insufficiency_reason": "No markets listed in the last 48h",
            "insufficient_buckets": ["new_market"],
        })

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_planner_no_candidates_capture_skipped(self):
        # new_market_capture returns 1 (zero candidates)
        mock_nmc = MagicMock(return_value=1)
        mock_capture = MagicMock(return_value=0)

        with (
            patch("tools.cli.close_benchmark_v1.MANIFEST_PATH", self.manifest_path),
            patch("tools.cli.close_benchmark_v1.GAP_REPORT_PATH", self.gap_report_path),
            patch("tools.cli.close_benchmark_v1.NEW_MARKET_TARGETS_PATH", self.tmp / "nm_t.json"),
            patch("tools.cli.close_benchmark_v1.NEW_MARKET_INSUFF_PATH", self.nm_insuff_path),
            patch("tools.cli.close_benchmark_v1.GAP_FILL_INSUFF_PATH", self.tmp / "gf_i.json"),
            patch("tools.cli.close_benchmark_v1._check_clickhouse", return_value={"available": True}),
        ):
            # Use a fake targets manifest so preflight passes
            targets_path = self.tmp / "targets.json"
            _write(targets_path, _TARGETS_JSON)
            with patch("tools.cli.close_benchmark_v1.GAP_FILL_TARGETS_PATH", targets_path):
                artifact, exit_code = run_closure(
                    dry_run=False,
                    skip_silver=True,
                    out_path=self.artifact_out,
                    _new_market_capture_main=mock_nmc,
                    _capture_new_market_tapes_main=mock_capture,
                )

        self.assertEqual(exit_code, 1)
        nm = artifact["new_market_capture"]
        self.assertEqual(nm["status"], "completed")
        self.assertEqual(nm["planner"]["status"], "error")  # rc=1 → error
        self.assertEqual(nm["capture"]["status"], "skipped")
        self.assertIn("no candidates", nm["capture"]["reason"])

        # Capture was not called
        mock_capture.assert_not_called()

        # new_market insufficiency block appears in residual_blockers
        blocker_text = " ".join(artifact["residual_blockers"])
        self.assertIn("new_market", blocker_text)

    def test_planner_insufficient_rc2_triggers_capture(self):
        # new_market_capture returns 2 (partial — some targets but < required)
        nm_targets_path = self.tmp / "nm_targets.json"
        _write(nm_targets_path, _NEW_MARKET_TARGETS_JSON)
        mock_nmc = MagicMock(return_value=2)
        mock_capture = MagicMock(return_value=0)

        with (
            patch("tools.cli.close_benchmark_v1.MANIFEST_PATH", self.manifest_path),
            patch("tools.cli.close_benchmark_v1.GAP_REPORT_PATH", self.gap_report_path),
            patch("tools.cli.close_benchmark_v1.NEW_MARKET_TARGETS_PATH", nm_targets_path),
            patch("tools.cli.close_benchmark_v1.NEW_MARKET_INSUFF_PATH", self.tmp / "nm_i.json"),
            patch("tools.cli.close_benchmark_v1.GAP_FILL_INSUFF_PATH", self.tmp / "gf_i.json"),
            patch("tools.cli.close_benchmark_v1._check_clickhouse", return_value={"available": True}),
        ):
            targets_path = self.tmp / "targets.json"
            _write(targets_path, _TARGETS_JSON)
            with patch("tools.cli.close_benchmark_v1.GAP_FILL_TARGETS_PATH", targets_path):
                artifact, _ = run_closure(
                    dry_run=False,
                    skip_silver=True,
                    out_path=self.artifact_out,
                    _new_market_capture_main=mock_nmc,
                    _capture_new_market_tapes_main=mock_capture,
                )

        nm = artifact["new_market_capture"]
        self.assertEqual(nm["planner"]["status"], "insufficient")
        # capture SHOULD have been triggered (rc=2 and targets file exists)
        mock_capture.assert_called_once_with(["--benchmark-refresh"])


# ---------------------------------------------------------------------------
# Scenario 5: Final manifest validation pass
# ---------------------------------------------------------------------------

class TestManifestCreatedDuringRun(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.tmp = Path(self.tmpdir.name)
        self.targets_path = self.tmp / "targets.json"
        self.manifest_path = self.tmp / "manifest.json"
        self.gap_report_path = self.tmp / "gap_report.json"
        self.artifact_out = self.tmp / "artifact.json"
        _write(self.targets_path, _TARGETS_JSON)
        _write(self.gap_report_path, _GAP_REPORT_JSON)

    def tearDown(self):
        self.tmpdir.cleanup()

    def _mock_refresh_writes_manifest(self):
        """Simulate benchmark refresh that writes the manifest."""
        _write(self.manifest_path, _VALID_MANIFEST_JSON)
        return {
            "triggered": True,
            "return_code": 0,
            "manifest_written": True,
            "outcome": "manifest_written",
            "manifest_path": str(self.manifest_path),
        }

    def test_manifest_written_by_silver_refresh_exits_0(self):
        with (
            patch("tools.cli.close_benchmark_v1.GAP_FILL_TARGETS_PATH", self.targets_path),
            patch("tools.cli.close_benchmark_v1.MANIFEST_PATH", self.manifest_path),
            patch("tools.cli.close_benchmark_v1.GAP_REPORT_PATH", self.gap_report_path),
            patch("tools.cli.close_benchmark_v1.NEW_MARKET_TARGETS_PATH", self.tmp / "nm_t.json"),
            patch("tools.cli.close_benchmark_v1.NEW_MARKET_INSUFF_PATH", self.tmp / "nm_i.json"),
            patch("tools.cli.close_benchmark_v1.GAP_FILL_INSUFF_PATH", self.tmp / "gf_i.json"),
            patch("tools.cli.close_benchmark_v1._check_clickhouse", return_value={"available": True}),
            patch("tools.cli.batch_reconstruct_silver.run_batch_from_targets",
                  return_value={"schema_version": "benchmark_gap_fill_run_v1",
                                "targets_attempted": 3, "tapes_created": 3,
                                "failure_count": 0, "skip_count": 0}),
            patch("tools.cli.batch_reconstruct_silver._refresh_benchmark_curation",
                  side_effect=self._mock_refresh_writes_manifest),
        ):
            artifact, exit_code = run_closure(
                dry_run=False,
                skip_new_market=True,
                out_path=self.artifact_out,
                _fetch_price_2min_main=MagicMock(return_value=0),
            )

        self.assertEqual(exit_code, 0)
        self.assertEqual(artifact["final_status"], "manifest_created")
        self.assertIsNotNone(artifact["manifest_path"])
        self.assertEqual(artifact["residual_blockers"], [])

    def test_finalization_reads_manifest_tape_count(self):
        _write(self.manifest_path, _VALID_MANIFEST_JSON)
        with patch("tools.cli.close_benchmark_v1.MANIFEST_PATH", self.manifest_path):
            result = run_finalization()
        self.assertEqual(result["status"], "manifest_created")
        self.assertEqual(result["tape_count"], 2)
        self.assertEqual(result["blockers"], [])


# ---------------------------------------------------------------------------
# Scenario 6: Resumable rerun — manifest already exists
# ---------------------------------------------------------------------------

class TestResumableRerun(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.tmp = Path(self.tmpdir.name)
        self.manifest_path = self.tmp / "manifest.json"
        self.artifact_out = self.tmp / "artifact.json"
        _write(self.manifest_path, _VALID_MANIFEST_JSON)  # exists before run

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_manifest_exists_before_run_exits_0_skips_stages(self):
        mock_fetch = MagicMock(return_value=0)
        mock_nmc   = MagicMock(return_value=0)
        mock_cap   = MagicMock(return_value=0)

        with patch("tools.cli.close_benchmark_v1.MANIFEST_PATH", self.manifest_path):
            artifact, exit_code = run_closure(
                dry_run=False,
                out_path=self.artifact_out,
                _fetch_price_2min_main=mock_fetch,
                _new_market_capture_main=mock_nmc,
                _capture_new_market_tapes_main=mock_cap,
            )

        self.assertEqual(exit_code, 0)
        self.assertEqual(artifact["final_status"], "manifest_created")
        self.assertEqual(artifact["preflight"]["status"], "already_closed")

        # No stage should have executed
        self.assertEqual(artifact["silver_gap_fill"]["status"], "skipped")
        self.assertEqual(artifact["new_market_capture"]["status"], "skipped")
        mock_fetch.assert_not_called()
        mock_nmc.assert_not_called()
        mock_cap.assert_not_called()

    def test_preflight_already_closed_short_circuits(self):
        with patch("tools.cli.close_benchmark_v1.MANIFEST_PATH", self.manifest_path):
            result = run_preflight()
        self.assertEqual(result["status"], "already_closed")
        self.assertIn("manifest_path", result)
        self.assertEqual(result["blockers"], [])


# ---------------------------------------------------------------------------
# Scenario 7: CLI smoke
# ---------------------------------------------------------------------------

class TestCLISmoke(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.tmp = Path(self.tmpdir.name)
        self.targets_path = self.tmp / "targets.json"
        self.manifest_path = self.tmp / "manifest.json"
        self.gap_report_path = self.tmp / "gap_report.json"
        self.artifact_out = self.tmp / "artifact.json"
        _write(self.targets_path, _TARGETS_JSON)
        _write(self.gap_report_path, _GAP_REPORT_JSON)

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_main_dry_run_exits_1_when_blocked(self):
        with (
            patch("tools.cli.close_benchmark_v1.GAP_FILL_TARGETS_PATH", self.targets_path),
            patch("tools.cli.close_benchmark_v1.MANIFEST_PATH", self.manifest_path),
            patch("tools.cli.close_benchmark_v1.GAP_REPORT_PATH", self.gap_report_path),
            patch("tools.cli.close_benchmark_v1.NEW_MARKET_TARGETS_PATH", self.tmp / "nm_t.json"),
            patch("tools.cli.close_benchmark_v1.NEW_MARKET_INSUFF_PATH", self.tmp / "nm_i.json"),
            patch("tools.cli.close_benchmark_v1.GAP_FILL_INSUFF_PATH", self.tmp / "gf_i.json"),
            patch("tools.cli.close_benchmark_v1._check_clickhouse", return_value={"available": True}),
        ):
            rc = main([
                "--dry-run",
                "--skip-new-market",
                "--clickhouse-password", "testpass",
                "--out", str(self.artifact_out),
            ])

        self.assertEqual(rc, 1)
        self.assertTrue(self.artifact_out.exists())
        artifact = json.loads(self.artifact_out.read_text())
        self.assertTrue(artifact["dry_run"])
        self.assertEqual(artifact["schema_version"], "benchmark_closure_run_v1")

    def test_main_help_exits_0(self):
        with self.assertRaises(SystemExit) as ctx:
            main(["--help"])
        self.assertEqual(ctx.exception.code, 0)

    def test_main_skip_silver_and_new_market(self):
        with (
            patch("tools.cli.close_benchmark_v1.GAP_FILL_TARGETS_PATH", self.targets_path),
            patch("tools.cli.close_benchmark_v1.MANIFEST_PATH", self.manifest_path),
            patch("tools.cli.close_benchmark_v1.GAP_REPORT_PATH", self.gap_report_path),
            patch("tools.cli.close_benchmark_v1.NEW_MARKET_TARGETS_PATH", self.tmp / "nm_t.json"),
            patch("tools.cli.close_benchmark_v1.NEW_MARKET_INSUFF_PATH", self.tmp / "nm_i.json"),
            patch("tools.cli.close_benchmark_v1.GAP_FILL_INSUFF_PATH", self.tmp / "gf_i.json"),
            patch("tools.cli.close_benchmark_v1._check_clickhouse", return_value={"available": True}),
        ):
            rc = main([
                "--skip-silver",
                "--skip-new-market",
                "--clickhouse-password", "testpass",
                "--out", str(self.artifact_out),
            ])

        self.assertEqual(rc, 1)  # blocked (no tapes created)
        artifact = json.loads(self.artifact_out.read_text())
        self.assertEqual(artifact["silver_gap_fill"]["status"], "skipped")
        self.assertEqual(artifact["new_market_capture"]["status"], "skipped")

    def test_missing_password_returns_1(self):
        """No --clickhouse-password and no env var → rc=1 with error message."""
        env_without_pw = {k: v for k, v in os.environ.items()
                         if k != "CLICKHOUSE_PASSWORD"}
        with (
            patch("tools.cli.close_benchmark_v1.GAP_FILL_TARGETS_PATH", self.targets_path),
            patch("tools.cli.close_benchmark_v1.MANIFEST_PATH", self.manifest_path),
            patch("tools.cli.close_benchmark_v1.GAP_REPORT_PATH", self.gap_report_path),
            patch("tools.cli.close_benchmark_v1.NEW_MARKET_TARGETS_PATH", self.tmp / "nm_t.json"),
            patch("tools.cli.close_benchmark_v1.NEW_MARKET_INSUFF_PATH", self.tmp / "nm_i.json"),
            patch("tools.cli.close_benchmark_v1.GAP_FILL_INSUFF_PATH", self.tmp / "gf_i.json"),
            patch.dict(os.environ, env_without_pw, clear=True),
        ):
            rc = main(["--dry-run", "--skip-new-market"])
        self.assertEqual(rc, 1)

    def test_empty_string_password_returns_1(self):
        """CLICKHOUSE_PASSWORD='' (empty string) must fail fast, not proceed.

        Regression for 2026-03-19 auth fix: prior code only checked `is None`,
        allowing empty-string through to ClickHouse → HTTP 516 auth failure.
        """
        with (
            patch("tools.cli.close_benchmark_v1.GAP_FILL_TARGETS_PATH", self.targets_path),
            patch("tools.cli.close_benchmark_v1.MANIFEST_PATH", self.manifest_path),
            patch("tools.cli.close_benchmark_v1.GAP_REPORT_PATH", self.gap_report_path),
            patch("tools.cli.close_benchmark_v1.NEW_MARKET_TARGETS_PATH", self.tmp / "nm_t.json"),
            patch("tools.cli.close_benchmark_v1.NEW_MARKET_INSUFF_PATH", self.tmp / "nm_i.json"),
            patch("tools.cli.close_benchmark_v1.GAP_FILL_INSUFF_PATH", self.tmp / "gf_i.json"),
            patch.dict(os.environ, {"CLICKHOUSE_PASSWORD": ""}),
        ):
            rc = main(["--dry-run", "--skip-new-market"])
        self.assertEqual(rc, 1)

    def test_password_via_env_var_proceeds(self):
        """CLICKHOUSE_PASSWORD env var → code proceeds past credential check."""
        with (
            patch("tools.cli.close_benchmark_v1.GAP_FILL_TARGETS_PATH", self.targets_path),
            patch("tools.cli.close_benchmark_v1.MANIFEST_PATH", self.manifest_path),
            patch("tools.cli.close_benchmark_v1.GAP_REPORT_PATH", self.gap_report_path),
            patch("tools.cli.close_benchmark_v1.NEW_MARKET_TARGETS_PATH", self.tmp / "nm_t.json"),
            patch("tools.cli.close_benchmark_v1.NEW_MARKET_INSUFF_PATH", self.tmp / "nm_i.json"),
            patch("tools.cli.close_benchmark_v1.GAP_FILL_INSUFF_PATH", self.tmp / "gf_i.json"),
            patch("tools.cli.close_benchmark_v1._check_clickhouse", return_value={"available": True}),
            patch.dict(os.environ, {"CLICKHOUSE_PASSWORD": "envpass"}),
        ):
            rc = main([
                "--dry-run",
                "--skip-new-market",
                "--out", str(self.artifact_out),
            ])
        # rc=1 means blocked (correct — no tapes), not auth failure
        self.assertEqual(rc, 1)
        self.assertTrue(self.artifact_out.exists())

    def test_password_flag_takes_precedence_over_env(self):
        """--clickhouse-password flag forwarded correctly even when env var set."""
        with (
            patch("tools.cli.close_benchmark_v1.GAP_FILL_TARGETS_PATH", self.targets_path),
            patch("tools.cli.close_benchmark_v1.MANIFEST_PATH", self.manifest_path),
            patch("tools.cli.close_benchmark_v1.GAP_REPORT_PATH", self.gap_report_path),
            patch("tools.cli.close_benchmark_v1.NEW_MARKET_TARGETS_PATH", self.tmp / "nm_t.json"),
            patch("tools.cli.close_benchmark_v1.NEW_MARKET_INSUFF_PATH", self.tmp / "nm_i.json"),
            patch("tools.cli.close_benchmark_v1.GAP_FILL_INSUFF_PATH", self.tmp / "gf_i.json"),
            patch("tools.cli.close_benchmark_v1._check_clickhouse", return_value={"available": True}),
            patch.dict(os.environ, {"CLICKHOUSE_PASSWORD": "envpass"}),
        ):
            rc = main([
                "--dry-run",
                "--skip-new-market",
                "--clickhouse-password", "flagpass",
                "--out", str(self.artifact_out),
            ])
        self.assertEqual(rc, 1)
        self.assertTrue(self.artifact_out.exists())


# ---------------------------------------------------------------------------
# Bonus: run_silver_gap_fill_stage isolation
# ---------------------------------------------------------------------------

class TestSilverStageDirect(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.tmp = Path(self.tmpdir.name)
        self.targets_path = self.tmp / "targets.json"
        _write(self.targets_path, _TARGETS_JSON)

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_missing_targets_returns_skipped(self):
        missing = self.tmp / "not_there.json"
        with patch("tools.cli.close_benchmark_v1.GAP_FILL_TARGETS_PATH", missing):
            result = run_silver_gap_fill_stage(dry_run=True)
        self.assertEqual(result["status"], "skipped")

    def test_dry_run_no_external_calls(self):
        mock_fetch = MagicMock(return_value=0)
        with patch("tools.cli.close_benchmark_v1.GAP_FILL_TARGETS_PATH", self.targets_path):
            result = run_silver_gap_fill_stage(
                dry_run=True,
                _fetch_price_2min_main=mock_fetch,
            )
        self.assertEqual(result["status"], "dry_run")
        mock_fetch.assert_not_called()

    def test_skip_price_2min_flag(self):
        mock_fetch = MagicMock(return_value=0)
        with (
            patch("tools.cli.close_benchmark_v1.GAP_FILL_TARGETS_PATH", self.targets_path),
            patch("tools.cli.batch_reconstruct_silver.run_batch_from_targets",
                  return_value={"schema_version": "x", "targets_attempted": 1,
                                "tapes_created": 1, "failure_count": 0, "skip_count": 0}),
            patch("tools.cli.batch_reconstruct_silver._refresh_benchmark_curation",
                  return_value={"triggered": True, "outcome": "gap_report_updated",
                                "manifest_written": False, "manifest_path": None,
                                "gap_report_path": None}),
        ):
            result = run_silver_gap_fill_stage(
                dry_run=False,
                skip_price_2min=True,
                _fetch_price_2min_main=mock_fetch,
            )
        mock_fetch.assert_not_called()
        self.assertEqual(result["fetch_price_2min"]["status"], "skipped_flag")


# ---------------------------------------------------------------------------
# Bonus: run_new_market_stage isolation
# ---------------------------------------------------------------------------

class TestNewMarketStageDirect(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.tmp = Path(self.tmpdir.name)

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_dry_run_skips_everything(self):
        mock_nmc = MagicMock(return_value=0)
        mock_cap = MagicMock(return_value=0)
        result = run_new_market_stage(
            dry_run=True,
            _new_market_capture_main=mock_nmc,
            _capture_new_market_tapes_main=mock_cap,
        )
        self.assertEqual(result["status"], "dry_run")
        mock_nmc.assert_not_called()
        mock_cap.assert_not_called()

    def test_planner_error_skips_capture(self):
        mock_nmc = MagicMock(return_value=1)
        mock_cap = MagicMock(return_value=0)
        with patch("tools.cli.close_benchmark_v1.NEW_MARKET_TARGETS_PATH", self.tmp / "nm_t.json"):
            result = run_new_market_stage(
                dry_run=False,
                _new_market_capture_main=mock_nmc,
                _capture_new_market_tapes_main=mock_cap,
            )
        self.assertEqual(result["capture"]["status"], "skipped")
        mock_cap.assert_not_called()


# ---------------------------------------------------------------------------
# Preflight credential consistency + failed_targets bubbling
# ---------------------------------------------------------------------------

class TestPreflightCredentialConsistency(unittest.TestCase):
    """Verify that _check_clickhouse sends Basic Auth and that run_preflight
    forwards credentials correctly, plus that failed_targets appear in the
    Silver-stage recon_outcome."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.tmp = Path(self.tmpdir.name)
        self.targets_path = self.tmp / "targets.json"
        _write(self.targets_path, _TARGETS_JSON)

    def tearDown(self):
        self.tmpdir.cleanup()

    # ------------------------------------------------------------------
    # _check_clickhouse sends Authorization: Basic header
    # ------------------------------------------------------------------

    def test_check_clickhouse_sends_auth_header(self):
        """_check_clickhouse must attach Basic-Auth header when user+password given."""
        import base64
        import urllib.request

        captured_headers: list[dict] = []

        class _FakeResponse:
            status = 200
            def read(self):
                return b"1"
            def __enter__(self):
                return self
            def __exit__(self, *_):
                pass

        def _fake_urlopen(req, timeout=5):
            # req is a urllib.request.Request; capture its unredirected_hdrs
            hdrs = {k.lower(): v for k, v in req.header_items()}
            captured_headers.append(hdrs)
            return _FakeResponse()

        with patch("urllib.request.urlopen", side_effect=_fake_urlopen):
            result = _check_clickhouse("localhost", 8123, user="myuser", password="s3cr3t")

        self.assertTrue(result["available"])
        self.assertEqual(len(captured_headers), 1)
        self.assertIn("authorization", captured_headers[0])
        expected = "Basic " + base64.b64encode(b"myuser:s3cr3t").decode()
        self.assertEqual(captured_headers[0]["authorization"], expected)

    # ------------------------------------------------------------------
    # run_preflight forwards credentials to _check_clickhouse
    # ------------------------------------------------------------------

    def test_run_preflight_forwards_credentials_to_check_clickhouse(self):
        """run_preflight must pass clickhouse_user + clickhouse_password to _check_clickhouse."""
        with (
            patch("tools.cli.close_benchmark_v1.GAP_FILL_TARGETS_PATH", self.targets_path),
            patch("tools.cli.close_benchmark_v1.MANIFEST_PATH", self.tmp / "manifest.json"),
            patch("tools.cli.close_benchmark_v1.GAP_FILL_INSUFF_PATH", self.tmp / "gf_insuff.json"),
            patch("tools.cli.close_benchmark_v1.NEW_MARKET_TARGETS_PATH", self.tmp / "nm_t.json"),
            patch("tools.cli.close_benchmark_v1.NEW_MARKET_INSUFF_PATH", self.tmp / "nm_i.json"),
            patch("tools.cli.close_benchmark_v1._check_clickhouse",
                  return_value={"available": True}) as mock_ch,
        ):
            run_preflight(
                clickhouse_host="myhost",
                clickhouse_port=9000,
                clickhouse_user="myuser",
                clickhouse_password="s3cr3t",
            )

        mock_ch.assert_called_once_with(
            "myhost", 9000,
            user="myuser",
            password="s3cr3t",
        )

    # ------------------------------------------------------------------
    # failed_targets bubbled into recon_outcome
    # ------------------------------------------------------------------

    def test_silver_stage_failed_targets_in_recon_outcome(self):
        """batch_result outcomes with status='failure' must appear in
        batch_reconstruct['failed_targets'] of the Silver-stage result."""
        batch_result_with_failures = {
            "schema_version": "benchmark_gap_fill_run_v1",
            "targets_attempted": 3,
            "tapes_created": 1,
            "failure_count": 2,
            "skip_count": 0,
            "outcomes": [
                {
                    "status": "success",
                    "token_id": "0xAAA111",
                    "bucket": "politics",
                    "slug": "politics-market-1",
                    "error": None,
                },
                {
                    "status": "failure",
                    "token_id": "0xBBB222",
                    "bucket": "sports",
                    "slug": "sports-market-1",
                    "error": "ClickHouse 516 auth failed",
                },
                {
                    "status": "failure",
                    "token_id": "0xCCC333",
                    "bucket": "crypto",
                    "slug": "crypto-market-1",
                    "error": "timeout",
                },
            ],
        }

        with (
            patch("tools.cli.close_benchmark_v1.GAP_FILL_TARGETS_PATH", self.targets_path),
            patch("tools.cli.batch_reconstruct_silver.run_batch_from_targets",
                  return_value=batch_result_with_failures),
            patch("tools.cli.batch_reconstruct_silver._refresh_benchmark_curation",
                  return_value={"triggered": False, "outcome": "not_requested"}),
        ):
            result = run_silver_gap_fill_stage(
                dry_run=False,
                skip_price_2min=True,
                _fetch_price_2min_main=MagicMock(return_value=0),
            )

        recon = result["batch_reconstruct"]
        self.assertIn("failed_targets", recon)
        self.assertEqual(len(recon["failed_targets"]), 2)

        token_ids = {ft["token_id"] for ft in recon["failed_targets"]}
        self.assertIn("0xBBB222", token_ids)
        self.assertIn("0xCCC333", token_ids)
        self.assertNotIn("0xAAA111", token_ids)

        sports_failure = next(ft for ft in recon["failed_targets"] if ft["token_id"] == "0xBBB222")
        self.assertEqual(sports_failure["bucket"], "sports")
        self.assertEqual(sports_failure["error"], "ClickHouse 516 auth failed")


# ---------------------------------------------------------------------------
# Regression: full-target price_2min prefetch
# ---------------------------------------------------------------------------

class TestFullTargetPricePrefetch(unittest.TestCase):
    """Regression tests for the fix that extends fetch-price-2min coverage from
    priority-1-only (39 tokens) to ALL unique token IDs in the targets manifest.

    Root cause: run_silver_gap_fill_stage() previously called _priority1_token_ids()
    to build the fetch-price-2min argv, leaving overflow (priority>1) tokens without
    price_2min data in ClickHouse, which caused confidence=none empty tapes.
    """

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.tmp = Path(self.tmpdir.name)
        self.targets_path = self.tmp / "targets.json"
        # Manifest has 2 priority-1 and 1 priority-2 target
        _write(self.targets_path, _TARGETS_JSON)

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_fetch_argv_includes_overflow_token(self):
        """fetch-price-2min argv must include priority-2 token 0xCCC333."""
        mock_fetch = MagicMock(return_value=0)
        with (
            patch("tools.cli.close_benchmark_v1.GAP_FILL_TARGETS_PATH", self.targets_path),
            patch("tools.cli.batch_reconstruct_silver.run_batch_from_targets",
                  return_value={"schema_version": "x", "targets_attempted": 3,
                                "tapes_created": 3, "failure_count": 0, "skip_count": 0}),
            patch("tools.cli.batch_reconstruct_silver._refresh_benchmark_curation",
                  return_value={"triggered": False, "outcome": "not_requested"}),
        ):
            result = run_silver_gap_fill_stage(
                dry_run=False,
                _fetch_price_2min_main=mock_fetch,
            )

        self.assertEqual(result["status"], "completed")
        mock_fetch.assert_called_once()
        call_argv = mock_fetch.call_args[0][0]
        self.assertIn("0xAAA111", call_argv, "priority-1 token must be fetched")
        self.assertIn("0xBBB222", call_argv, "priority-1 token must be fetched")
        self.assertIn("0xCCC333", call_argv, "priority-2 token must now be fetched")

    def test_fetch_outcome_token_count_reflects_all_targets(self):
        """fetch_price_2min.token_count must equal total unique token count, not just priority-1."""
        mock_fetch = MagicMock(return_value=0)
        with (
            patch("tools.cli.close_benchmark_v1.GAP_FILL_TARGETS_PATH", self.targets_path),
            patch("tools.cli.batch_reconstruct_silver.run_batch_from_targets",
                  return_value={"schema_version": "x", "targets_attempted": 3,
                                "tapes_created": 3, "failure_count": 0, "skip_count": 0}),
            patch("tools.cli.batch_reconstruct_silver._refresh_benchmark_curation",
                  return_value={"triggered": False, "outcome": "not_requested"}),
        ):
            result = run_silver_gap_fill_stage(
                dry_run=False,
                _fetch_price_2min_main=mock_fetch,
            )

        fetch = result["fetch_price_2min"]
        # 3 unique tokens in the fixture (2 priority-1 + 1 priority-2)
        self.assertEqual(fetch["token_count"], 3)
        # priority1_count still correctly reflects the smaller subset
        self.assertEqual(fetch["priority1_count"], 2)

    def test_dry_run_planned_tokens_includes_overflow(self):
        """dry_run planned_tokens must include priority-2 tokens."""
        with patch("tools.cli.close_benchmark_v1.GAP_FILL_TARGETS_PATH", self.targets_path):
            result = run_silver_gap_fill_stage(dry_run=True)

        fetch = result["fetch_price_2min"]
        self.assertEqual(fetch["status"], "dry_run")
        self.assertIn("0xCCC333", fetch["planned_tokens"],
                      "priority-2 overflow token must appear in dry_run planned_tokens")

    def test_deduplication_when_token_appears_in_multiple_buckets(self):
        """When a slug appears in two buckets (real-world case), token fetched once."""
        targets_with_dup = {
            "schema_version": "benchmark_gap_fill_v1",
            "targets": [
                {"bucket": "politics", "priority": 1, "token_id": "0xDUP",
                 "slug": "dup-slug", "market_id": "0xM1",
                 "window_start": "2024-01-01T00:00:00Z", "window_end": "2024-01-01T02:00:00Z"},
                {"bucket": "sports",   "priority": 2, "token_id": "0xDUP",
                 "slug": "dup-slug", "market_id": "0xM1",
                 "window_start": "2024-01-01T00:00:00Z", "window_end": "2024-01-01T02:00:00Z"},
                {"bucket": "crypto",   "priority": 1, "token_id": "0xUNIQ",
                 "slug": "uniq-slug", "market_id": "0xM2",
                 "window_start": "2024-01-02T00:00:00Z", "window_end": "2024-01-02T02:00:00Z"},
            ],
        }
        dup_targets_path = self.tmp / "dup_targets.json"
        _write(dup_targets_path, targets_with_dup)

        mock_fetch = MagicMock(return_value=0)
        with (
            patch("tools.cli.close_benchmark_v1.GAP_FILL_TARGETS_PATH", dup_targets_path),
            patch("tools.cli.batch_reconstruct_silver.run_batch_from_targets",
                  return_value={"schema_version": "x", "targets_attempted": 3,
                                "tapes_created": 2, "failure_count": 0, "skip_count": 0}),
            patch("tools.cli.batch_reconstruct_silver._refresh_benchmark_curation",
                  return_value={"triggered": False, "outcome": "not_requested"}),
        ):
            run_silver_gap_fill_stage(dry_run=False, _fetch_price_2min_main=mock_fetch)

        call_argv = mock_fetch.call_args[0][0]
        # 0xDUP appears in 2 buckets but should only appear once in argv
        dup_count = call_argv.count("0xDUP")
        self.assertEqual(dup_count, 1, f"0xDUP appeared {dup_count} times in argv, expected 1")

    def test_old_priority1_only_behavior_no_longer_present(self):
        """Regression guard: the old narrow subset path must not exclude overflow tokens.

        This is the core fix assertion.  Before the fix, _priority1_token_ids() was
        used to build the fetch argv, so 0xCCC333 (priority-2) was never fetched.
        After the fix, _all_unique_token_ids() is used and 0xCCC333 must be present.
        """
        mock_fetch = MagicMock(return_value=0)
        with (
            patch("tools.cli.close_benchmark_v1.GAP_FILL_TARGETS_PATH", self.targets_path),
            patch("tools.cli.batch_reconstruct_silver.run_batch_from_targets",
                  return_value={"schema_version": "x", "targets_attempted": 3,
                                "tapes_created": 3, "failure_count": 0, "skip_count": 0}),
            patch("tools.cli.batch_reconstruct_silver._refresh_benchmark_curation",
                  return_value={"triggered": False, "outcome": "not_requested"}),
        ):
            run_silver_gap_fill_stage(dry_run=False, _fetch_price_2min_main=mock_fetch)

        call_argv = mock_fetch.call_args[0][0]
        self.assertIn("0xCCC333", call_argv,
                      "REGRESSION: priority-2 token must be in fetch argv; "
                      "old code excluded it, causing price_2min_missing on overflow targets")


if __name__ == "__main__":
    unittest.main()
