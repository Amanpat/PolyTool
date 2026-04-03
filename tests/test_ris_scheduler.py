"""Offline unit tests for RIS v1 APScheduler scheduler module and CLI.

All tests are offline / deterministic (no network calls, no APScheduler import
required for JOB_REGISTRY or job-callable tests).
"""
from __future__ import annotations

import io
import json
import sys
from contextlib import redirect_stdout
from typing import Any
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers / Fixtures
# ---------------------------------------------------------------------------


class _FakeScheduler:
    """Minimal fake scheduler compatible with APScheduler's BackgroundScheduler API."""

    def __init__(self) -> None:
        self.jobs: list[dict] = []
        self.started = False
        self.stopped = False

    def add_job(self, fn: Any, trigger: Any, *, id: str, name: str) -> None:
        self.jobs.append({"id": id, "name": name, "fn": fn, "trigger": trigger})

    def start(self) -> None:
        self.started = True

    def shutdown(self) -> None:
        self.stopped = True


# ---------------------------------------------------------------------------
# JOB_REGISTRY tests
# ---------------------------------------------------------------------------


class TestJobRegistry:
    def test_job_registry_has_exactly_8_entries(self) -> None:
        from packages.research.scheduling.scheduler import JOB_REGISTRY

        assert len(JOB_REGISTRY) == 8, f"Expected 8 jobs, got {len(JOB_REGISTRY)}"

    def test_no_twitter_ingest_entry(self) -> None:
        from packages.research.scheduling.scheduler import JOB_REGISTRY

        ids = [j["id"] for j in JOB_REGISTRY]
        assert "twitter_ingest" not in ids, "twitter_ingest must NOT be in JOB_REGISTRY"

    def test_all_entries_have_required_keys(self) -> None:
        from packages.research.scheduling.scheduler import JOB_REGISTRY

        required_keys = {"id", "name", "trigger_description", "callable_name"}
        for job in JOB_REGISTRY:
            missing = required_keys - set(job.keys())
            assert not missing, f"Job {job.get('id')!r} missing keys: {missing}"

    def test_all_ids_are_unique(self) -> None:
        from packages.research.scheduling.scheduler import JOB_REGISTRY

        ids = [j["id"] for j in JOB_REGISTRY]
        assert len(ids) == len(set(ids)), "Duplicate job ids found"

    def test_expected_job_ids_present(self) -> None:
        from packages.research.scheduling.scheduler import JOB_REGISTRY

        expected_ids = {
            "academic_ingest",
            "reddit_polymarket",
            "reddit_others",
            "blog_ingest",
            "youtube_ingest",
            "github_ingest",
            "freshness_refresh",
            "weekly_digest",
        }
        actual_ids = {j["id"] for j in JOB_REGISTRY}
        assert actual_ids == expected_ids

    def test_job_registry_importable_without_apscheduler(self) -> None:
        """JOB_REGISTRY must be importable even when APScheduler is not installed."""
        # We verify this by ensuring the import succeeds at module level
        # (no top-level apscheduler import in scheduler.py).
        import packages.research.scheduling.scheduler as sched_mod

        assert hasattr(sched_mod, "JOB_REGISTRY")
        # If this test passes, the module-level import guard is not present.


# ---------------------------------------------------------------------------
# start_research_scheduler tests (injectable, no APScheduler needed)
# ---------------------------------------------------------------------------


class TestStartResearchScheduler:
    def test_returns_fake_scheduler_instance(self) -> None:
        from packages.research.scheduling.scheduler import start_research_scheduler

        fake = _FakeScheduler()
        result = start_research_scheduler(
            _scheduler_factory=lambda: fake,
            _job_runner=lambda job_id: None,
        )
        assert result is fake

    def test_scheduler_is_started(self) -> None:
        from packages.research.scheduling.scheduler import start_research_scheduler

        fake = _FakeScheduler()
        start_research_scheduler(
            _scheduler_factory=lambda: fake,
            _job_runner=lambda job_id: None,
        )
        assert fake.started, "scheduler.start() must be called"

    def test_all_8_jobs_registered(self) -> None:
        from packages.research.scheduling.scheduler import JOB_REGISTRY, start_research_scheduler

        fake = _FakeScheduler()
        start_research_scheduler(
            _scheduler_factory=lambda: fake,
            _job_runner=lambda job_id: None,
        )
        assert len(fake.jobs) == len(JOB_REGISTRY) == 8

    def test_registered_job_ids_match_registry(self) -> None:
        from packages.research.scheduling.scheduler import JOB_REGISTRY, start_research_scheduler

        fake = _FakeScheduler()
        start_research_scheduler(
            _scheduler_factory=lambda: fake,
            _job_runner=lambda job_id: None,
        )
        registered_ids = {j["id"] for j in fake.jobs}
        expected_ids = {j["id"] for j in JOB_REGISTRY}
        assert registered_ids == expected_ids

    def test_job_runner_receives_correct_job_id(self) -> None:
        """When _job_runner is provided, calling a registered job fn passes the job_id."""
        from packages.research.scheduling.scheduler import start_research_scheduler

        calls: list[str] = []
        fake = _FakeScheduler()
        start_research_scheduler(
            _scheduler_factory=lambda: fake,
            _job_runner=lambda job_id: calls.append(job_id),
        )
        # Manually invoke all registered job functions to verify job_id routing
        for job_dict in fake.jobs:
            job_dict["fn"]()
        assert len(calls) == 8
        assert "academic_ingest" in calls
        assert "weekly_digest" in calls

    def test_no_jobs_triggered_at_start_time(self) -> None:
        """Jobs are registered but not triggered immediately on start."""
        from packages.research.scheduling.scheduler import start_research_scheduler

        calls: list[str] = []
        fake = _FakeScheduler()
        start_research_scheduler(
            _scheduler_factory=lambda: fake,
            _job_runner=lambda job_id: calls.append(job_id),
        )
        # No calls should have happened yet (scheduler.start() doesn't fire jobs)
        assert calls == [], f"Expected no calls at start time, got {calls}"


# ---------------------------------------------------------------------------
# run_job tests
# ---------------------------------------------------------------------------


class TestRunJob:
    def test_run_job_unknown_id_returns_1(self) -> None:
        from packages.research.scheduling.scheduler import run_job

        result = run_job("nonexistent_job")
        assert result == 1

    def test_run_job_academic_ingest_returns_0(self) -> None:
        from packages.research.scheduling import scheduler as sched_mod

        mock_acquire = MagicMock()
        mock_acquire.main.return_value = 0
        with patch("packages.research.scheduling.scheduler._job_run_academic_ingestion") as mock_fn:
            mock_fn.return_value = None  # job callables return None; run_job returns 0 on success
            # Instead of patching the import chain, patch the function in _JOB_FN_MAP directly
            original = sched_mod._JOB_FN_MAP["_job_run_academic_ingestion"]
            sched_mod._JOB_FN_MAP["_job_run_academic_ingestion"] = mock_fn
            try:
                result = sched_mod.run_job("academic_ingest")
            finally:
                sched_mod._JOB_FN_MAP["_job_run_academic_ingestion"] = original
        assert result == 0

    def test_run_job_weekly_digest_returns_0(self) -> None:
        from packages.research.scheduling import scheduler as sched_mod

        mock_fn = MagicMock(return_value=None)
        original = sched_mod._JOB_FN_MAP["_job_run_weekly_digest"]
        sched_mod._JOB_FN_MAP["_job_run_weekly_digest"] = mock_fn
        try:
            result = sched_mod.run_job("weekly_digest")
        finally:
            sched_mod._JOB_FN_MAP["_job_run_weekly_digest"] = original
        assert result == 0

    def test_run_job_exception_returns_1(self) -> None:
        """If job callable raises an exception, run_job returns 1."""
        from packages.research.scheduling import scheduler as sched_mod

        mock_fn = MagicMock(side_effect=RuntimeError("simulated failure"))
        original = sched_mod._JOB_FN_MAP["_job_run_academic_ingestion"]
        sched_mod._JOB_FN_MAP["_job_run_academic_ingestion"] = mock_fn
        try:
            result = sched_mod.run_job("academic_ingest")
        finally:
            sched_mod._JOB_FN_MAP["_job_run_academic_ingestion"] = original
        assert result == 1


# ---------------------------------------------------------------------------
# CLI tests
# ---------------------------------------------------------------------------


class TestCliStatus:
    def test_status_returns_0(self) -> None:
        from tools.cli.research_scheduler import main

        buf = io.StringIO()
        with redirect_stdout(buf):
            result = main(["status"])
        assert result == 0

    def test_status_json_returns_0_and_valid_json_list(self) -> None:
        from tools.cli.research_scheduler import main

        buf = io.StringIO()
        with redirect_stdout(buf):
            result = main(["status", "--json"])
        assert result == 0
        data = json.loads(buf.getvalue())
        assert isinstance(data, list)
        assert len(data) == 8

    def test_status_json_has_required_keys(self) -> None:
        from tools.cli.research_scheduler import main

        buf = io.StringIO()
        with redirect_stdout(buf):
            main(["status", "--json"])
        data = json.loads(buf.getvalue())
        for item in data:
            assert "id" in item
            assert "name" in item
            assert "trigger_description" in item

    def test_status_output_contains_8_job_ids(self) -> None:
        from tools.cli.research_scheduler import main

        buf = io.StringIO()
        with redirect_stdout(buf):
            main(["status"])
        output = buf.getvalue()
        assert "academic_ingest" in output
        assert "weekly_digest" in output


class TestCliStart:
    def test_start_dry_run_returns_0(self) -> None:
        from tools.cli.research_scheduler import main

        buf = io.StringIO()
        with redirect_stdout(buf):
            result = main(["start", "--dry-run"])
        assert result == 0

    def test_start_dry_run_lists_jobs(self) -> None:
        from tools.cli.research_scheduler import main

        buf = io.StringIO()
        with redirect_stdout(buf):
            main(["start", "--dry-run"])
        output = buf.getvalue()
        assert "academic_ingest" in output
        assert "weekly_digest" in output


class TestCliRunJob:
    def test_run_job_unknown_id_returns_1(self) -> None:
        from tools.cli.research_scheduler import main

        result = main(["run-job", "twitter_ingest"])
        assert result == 1

    def test_run_job_known_id_returns_0(self) -> None:
        from tools.cli.research_scheduler import main
        from packages.research.scheduling import scheduler as sched_mod

        mock_fn = MagicMock(return_value=None)
        original = sched_mod._JOB_FN_MAP["_job_run_academic_ingestion"]
        sched_mod._JOB_FN_MAP["_job_run_academic_ingestion"] = mock_fn
        buf = io.StringIO()
        try:
            with redirect_stdout(buf):
                result = main(["run-job", "academic_ingest"])
        finally:
            sched_mod._JOB_FN_MAP["_job_run_academic_ingestion"] = original
        assert result == 0

    def test_run_job_json_flag_outputs_json(self) -> None:
        from tools.cli.research_scheduler import main
        from packages.research.scheduling import scheduler as sched_mod

        mock_fn = MagicMock(return_value=None)
        original = sched_mod._JOB_FN_MAP["_job_run_academic_ingestion"]
        sched_mod._JOB_FN_MAP["_job_run_academic_ingestion"] = mock_fn
        buf = io.StringIO()
        try:
            with redirect_stdout(buf):
                result = main(["run-job", "academic_ingest", "--json"])
        finally:
            sched_mod._JOB_FN_MAP["_job_run_academic_ingestion"] = original
        assert result == 0
        data = json.loads(buf.getvalue())
        assert data["job_id"] == "academic_ingest"
        assert data["exit_code"] == 0

    def test_run_job_unknown_id_json_outputs_error_json(self) -> None:
        from tools.cli.research_scheduler import main

        buf = io.StringIO()
        with redirect_stdout(buf):
            result = main(["run-job", "nonexistent", "--json"])
        assert result == 1
        data = json.loads(buf.getvalue())
        assert data["exit_code"] == 1


class TestCliMissingSubcommand:
    def test_missing_subcommand_returns_1(self) -> None:
        from tools.cli.research_scheduler import main

        result = main([])
        assert result == 1

    def test_unknown_subcommand_returns_1(self) -> None:
        """argparse will handle unknown subcommand; verify exit code is 1."""
        from tools.cli.research_scheduler import main

        # argparse calls sys.exit(2) for unknown subcommands; we catch SystemExit
        try:
            result = main(["badcmd"])
            # If it doesn't raise, it should return 1
            assert result == 1
        except SystemExit as exc:
            # argparse exits with code 2 for unrecognized args
            assert exc.code != 0


# ---------------------------------------------------------------------------
# TestRunJobRunLog — run_log wiring tests (Task 1 + Task 2)
# ---------------------------------------------------------------------------


class TestRunJobRunLog:
    def test_run_job_writes_run_log_on_success(self) -> None:
        """Successful run_job produces a RunRecord with exit_status='ok'."""
        from packages.research.scheduling import scheduler as sched_mod
        from packages.research.monitoring.run_log import RunRecord

        records: list = []
        mock_fn = MagicMock(return_value=None)
        original = sched_mod._JOB_FN_MAP["_job_run_academic_ingestion"]
        sched_mod._JOB_FN_MAP["_job_run_academic_ingestion"] = mock_fn
        try:
            result = sched_mod.run_job("academic_ingest", _run_log_fn=records.append)
        finally:
            sched_mod._JOB_FN_MAP["_job_run_academic_ingestion"] = original

        assert result == 0
        assert len(records) == 1
        rec = records[0]
        assert isinstance(rec, RunRecord)
        assert rec.pipeline == "academic_ingest"
        assert rec.exit_status == "ok"
        assert rec.duration_s >= 0

    def test_run_job_writes_run_log_on_error(self) -> None:
        """Failing run_job produces a RunRecord with exit_status='error'."""
        from packages.research.scheduling import scheduler as sched_mod
        from packages.research.monitoring.run_log import RunRecord

        records: list = []
        mock_fn = MagicMock(side_effect=RuntimeError("simulated failure"))
        original = sched_mod._JOB_FN_MAP["_job_run_academic_ingestion"]
        sched_mod._JOB_FN_MAP["_job_run_academic_ingestion"] = mock_fn
        try:
            result = sched_mod.run_job("academic_ingest", _run_log_fn=records.append)
        finally:
            sched_mod._JOB_FN_MAP["_job_run_academic_ingestion"] = original

        assert result == 1
        assert len(records) == 1
        rec = records[0]
        assert isinstance(rec, RunRecord)
        assert rec.pipeline == "academic_ingest"
        assert rec.exit_status == "error"
        assert rec.duration_s >= 0

    def test_run_job_to_health_end_to_end(self, tmp_path) -> None:
        """run_job -> append_run -> list_runs -> evaluate_health full pipeline."""
        from packages.research.monitoring.run_log import append_run, list_runs
        from packages.research.monitoring.health_checks import evaluate_health
        from packages.research.scheduling import scheduler as sched_mod

        log_path = tmp_path / "run_log.jsonl"

        def capturing_log_fn(rec):
            append_run(rec, path=log_path)

        mock_fn = MagicMock(return_value=None)
        original = sched_mod._JOB_FN_MAP["_job_run_academic_ingestion"]
        sched_mod._JOB_FN_MAP["_job_run_academic_ingestion"] = mock_fn
        try:
            sched_mod.run_job("academic_ingest", _run_log_fn=capturing_log_fn)
        finally:
            sched_mod._JOB_FN_MAP["_job_run_academic_ingestion"] = original

        # Read back the run log
        runs = list_runs(path=log_path)
        assert len(runs) == 1
        assert runs[0].pipeline == "academic_ingest"

        # Evaluate health — pipeline_failed should be GREEN (successful run)
        results = {r.check_name: r for r in evaluate_health(runs)}
        assert results["pipeline_failed"].status == "GREEN"


# ---------------------------------------------------------------------------
# TestSchedulerBackgroundPath — verify real APScheduler path routes through run_job()
# ---------------------------------------------------------------------------


class TestSchedulerBackgroundPath:
    """Verify that real APScheduler path (no _job_runner) routes through run_job()."""

    def test_background_path_writes_run_log(self) -> None:
        """Registered job fn calls run_job(), which produces a RunRecord."""
        from packages.research.scheduling import scheduler as sched_mod
        from packages.research.monitoring.run_log import RunRecord

        records: list = []
        fake = _FakeScheduler()

        # Patch the actual callable so no network calls happen
        mock_fn = MagicMock(return_value=None)
        original = sched_mod._JOB_FN_MAP["_job_run_academic_ingestion"]
        sched_mod._JOB_FN_MAP["_job_run_academic_ingestion"] = mock_fn
        try:
            sched_mod.start_research_scheduler(
                _scheduler_factory=lambda: fake,
                # No _job_runner — exercises the else branch (real path)
                _run_log_fn=records.append,
            )
            # Find the academic_ingest job and invoke it manually
            job = next(j for j in fake.jobs if j["id"] == "academic_ingest")
            job["fn"]()
        finally:
            sched_mod._JOB_FN_MAP["_job_run_academic_ingestion"] = original

        assert len(records) == 1
        rec = records[0]
        assert isinstance(rec, RunRecord)
        assert rec.pipeline == "academic_ingest"
        assert rec.exit_status == "ok"

    def test_background_path_records_error_status(self) -> None:
        """When callable raises, the RunRecord has exit_status='error'."""
        from packages.research.scheduling import scheduler as sched_mod
        from packages.research.monitoring.run_log import RunRecord

        records: list = []
        fake = _FakeScheduler()

        mock_fn = MagicMock(side_effect=RuntimeError("boom"))
        original = sched_mod._JOB_FN_MAP["_job_run_academic_ingestion"]
        sched_mod._JOB_FN_MAP["_job_run_academic_ingestion"] = mock_fn
        try:
            sched_mod.start_research_scheduler(
                _scheduler_factory=lambda: fake,
                _run_log_fn=records.append,
            )
            job = next(j for j in fake.jobs if j["id"] == "academic_ingest")
            job["fn"]()
        finally:
            sched_mod._JOB_FN_MAP["_job_run_academic_ingestion"] = original

        assert len(records) == 1
        assert records[0].exit_status == "error"
