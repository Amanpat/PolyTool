"""Deterministic offline tests for packages/research/monitoring/.

Covers:
- RunLog: append_run, list_runs, load_last_run
- HealthChecks: evaluate_health with all 6 check conditions
- AlertSink: LogSink, WebhookSink (mocked), fire_alerts
- CLI: research_health.main()
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _iso_utc(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _make_record(
    pipeline: str = "ris_ingest",
    exit_status: str = "ok",
    accepted: int = 5,
    rejected: int = 2,
    errors: int = 0,
    duration_s: float = 1.5,
    started_at: Optional[str] = None,
    run_id: Optional[str] = None,
) -> dict:
    """Build a minimal RunRecord-compatible dict for testing."""
    if started_at is None:
        started_at = _iso_utc(_now())
    if run_id is None:
        import hashlib
        run_id = hashlib.sha256(f"{pipeline}{started_at}".encode()).hexdigest()[:12]
    return {
        "run_id": run_id,
        "pipeline": pipeline,
        "started_at": started_at,
        "duration_s": duration_s,
        "accepted": accepted,
        "rejected": rejected,
        "errors": errors,
        "exit_status": exit_status,
        "metadata": {},
        "schema_version": "run_log_v1",
    }


# ---------------------------------------------------------------------------
# RunLog tests
# ---------------------------------------------------------------------------

class TestRunLog:

    def test_append_creates_file_and_writes_valid_json(self, tmp_path):
        from packages.research.monitoring.run_log import RunRecord, append_run, list_runs

        log_path = tmp_path / "subdir" / "run_log.jsonl"
        assert not log_path.exists()

        rec = RunRecord(
            pipeline="test_pipeline",
            started_at=_iso_utc(_now()),
            duration_s=2.0,
            accepted=3,
            rejected=1,
            errors=0,
            exit_status="ok",
        )
        append_run(rec, path=log_path)

        assert log_path.exists()
        lines = log_path.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 1
        data = json.loads(lines[0])
        assert data["pipeline"] == "test_pipeline"
        assert data["accepted"] == 3
        assert data["exit_status"] == "ok"
        assert "run_id" in data
        assert "schema_version" in data

    def test_append_does_not_overwrite(self, tmp_path):
        from packages.research.monitoring.run_log import RunRecord, append_run, list_runs

        log_path = tmp_path / "run_log.jsonl"
        base_ts = _now()

        for i in range(3):
            rec = RunRecord(
                pipeline="test",
                started_at=_iso_utc(base_ts + timedelta(seconds=i)),
                duration_s=1.0,
                accepted=i,
                rejected=0,
                errors=0,
                exit_status="ok",
            )
            append_run(rec, path=log_path)

        runs = list_runs(path=log_path)
        assert len(runs) == 3

    def test_list_runs_empty_when_no_file(self, tmp_path):
        from packages.research.monitoring.run_log import list_runs

        missing = tmp_path / "nonexistent.jsonl"
        result = list_runs(path=missing)
        assert result == []

    def test_list_runs_window_hours_filters(self, tmp_path):
        from packages.research.monitoring.run_log import RunRecord, append_run, list_runs

        log_path = tmp_path / "run_log.jsonl"
        now = _now()

        # Old run (60 hours ago)
        old_rec = RunRecord(
            pipeline="test",
            started_at=_iso_utc(now - timedelta(hours=60)),
            duration_s=1.0,
            accepted=5,
            rejected=0,
            errors=0,
            exit_status="ok",
        )
        append_run(old_rec, path=log_path)

        # Recent run (1 hour ago)
        recent_rec = RunRecord(
            pipeline="test",
            started_at=_iso_utc(now - timedelta(hours=1)),
            duration_s=1.0,
            accepted=3,
            rejected=0,
            errors=0,
            exit_status="ok",
        )
        append_run(recent_rec, path=log_path)

        filtered = list_runs(path=log_path, window_hours=24)
        assert len(filtered) == 1
        assert filtered[0].accepted == 3

    def test_list_runs_newest_first(self, tmp_path):
        from packages.research.monitoring.run_log import RunRecord, append_run, list_runs

        log_path = tmp_path / "run_log.jsonl"
        base = _now() - timedelta(hours=10)

        for i in range(5):
            rec = RunRecord(
                pipeline="test",
                started_at=_iso_utc(base + timedelta(hours=i)),
                duration_s=1.0,
                accepted=i,
                rejected=0,
                errors=0,
                exit_status="ok",
            )
            append_run(rec, path=log_path)

        runs = list_runs(path=log_path)
        assert len(runs) == 5
        # Newest first: accepted values should be 4, 3, 2, 1, 0
        assert runs[0].accepted == 4
        assert runs[-1].accepted == 0

    def test_load_last_run_returns_none_when_empty(self, tmp_path):
        from packages.research.monitoring.run_log import load_last_run

        missing = tmp_path / "run_log.jsonl"
        result = load_last_run(path=missing)
        assert result is None

    def test_load_last_run_returns_latest_record(self, tmp_path):
        from packages.research.monitoring.run_log import RunRecord, append_run, load_last_run

        log_path = tmp_path / "run_log.jsonl"
        base = _now() - timedelta(hours=5)

        for i in range(3):
            rec = RunRecord(
                pipeline="test",
                started_at=_iso_utc(base + timedelta(hours=i)),
                duration_s=1.0,
                accepted=i * 10,
                rejected=0,
                errors=0,
                exit_status="ok",
            )
            append_run(rec, path=log_path)

        last = load_last_run(path=log_path)
        assert last is not None
        assert last.accepted == 20  # i=2, accepted=2*10=20

    def test_run_record_auto_run_id(self, tmp_path):
        from packages.research.monitoring.run_log import RunRecord

        rec = RunRecord(
            pipeline="test",
            started_at=_iso_utc(_now()),
            duration_s=1.0,
            accepted=0,
            rejected=0,
            errors=0,
            exit_status="ok",
        )
        assert rec.run_id is not None
        assert len(rec.run_id) == 12

    def test_run_record_roundtrip_jsonl(self, tmp_path):
        from packages.research.monitoring.run_log import RunRecord, append_run, list_runs

        log_path = tmp_path / "run_log.jsonl"
        rec = RunRecord(
            pipeline="ris_ingest",
            started_at="2026-04-03T00:00:00+00:00",
            duration_s=3.14,
            accepted=7,
            rejected=2,
            errors=1,
            exit_status="partial",
            metadata={"source": "test"},
        )
        append_run(rec, path=log_path)
        runs = list_runs(path=log_path)
        assert len(runs) == 1
        r = runs[0]
        assert r.pipeline == "ris_ingest"
        assert r.duration_s == pytest.approx(3.14)
        assert r.accepted == 7
        assert r.rejected == 2
        assert r.errors == 1
        assert r.exit_status == "partial"
        assert r.metadata == {"source": "test"}


# ---------------------------------------------------------------------------
# HealthCheck tests
# ---------------------------------------------------------------------------

class TestHealthChecks:

    def _make_run_record(self, **kwargs):
        """Create RunRecord from kwargs."""
        from packages.research.monitoring.run_log import RunRecord
        defaults = dict(
            pipeline="ris_ingest",
            started_at=_iso_utc(_now()),
            duration_s=1.0,
            accepted=5,
            rejected=2,
            errors=0,
            exit_status="ok",
        )
        defaults.update(kwargs)
        return RunRecord(**defaults)

    def test_evaluate_health_empty_runs_all_green(self):
        from packages.research.monitoring.health_checks import evaluate_health

        results = evaluate_health([])
        assert len(results) > 0
        for r in results:
            assert r.status == "GREEN", f"Expected GREEN for {r.check_name}, got {r.status}: {r.message}"

    def test_pipeline_failed_red_on_error_status(self):
        from packages.research.monitoring.health_checks import evaluate_health

        runs = [self._make_run_record(exit_status="error")]
        results = {r.check_name: r for r in evaluate_health(runs)}
        assert results["pipeline_failed"].status == "RED"

    def test_pipeline_failed_green_on_ok_runs(self):
        from packages.research.monitoring.health_checks import evaluate_health

        runs = [
            self._make_run_record(exit_status="ok"),
            self._make_run_record(exit_status="partial"),
        ]
        results = {r.check_name: r for r in evaluate_health(runs)}
        assert results["pipeline_failed"].status == "GREEN"

    def test_no_new_docs_48h_yellow_when_no_accepted(self):
        from packages.research.monitoring.health_checks import evaluate_health

        # Run within 48h but accepted=0
        runs = [self._make_run_record(accepted=0, rejected=5)]
        results = {r.check_name: r for r in evaluate_health(runs, window_hours=48)}
        assert results["no_new_docs_48h"].status == "YELLOW"

    def test_no_new_docs_48h_green_when_accepted_present(self):
        from packages.research.monitoring.health_checks import evaluate_health

        runs = [self._make_run_record(accepted=3, rejected=1)]
        results = {r.check_name: r for r in evaluate_health(runs, window_hours=48)}
        assert results["no_new_docs_48h"].status == "GREEN"

    def test_no_new_docs_48h_green_when_no_runs(self):
        from packages.research.monitoring.health_checks import evaluate_health

        results = {r.check_name: r for r in evaluate_health([], window_hours=48)}
        assert results["no_new_docs_48h"].status == "GREEN"

    def test_accept_rate_low_yellow(self):
        from packages.research.monitoring.health_checks import evaluate_health

        # 1 accepted out of 10 total = 10% < 30%
        runs = [self._make_run_record(accepted=1, rejected=9)]
        results = {r.check_name: r for r in evaluate_health(runs)}
        assert results["accept_rate_low"].status == "YELLOW"

    def test_accept_rate_low_green_sufficient_rate(self):
        from packages.research.monitoring.health_checks import evaluate_health

        # 5 out of 10 = 50% > 30%
        runs = [self._make_run_record(accepted=5, rejected=5)]
        results = {r.check_name: r for r in evaluate_health(runs)}
        assert results["accept_rate_low"].status == "GREEN"

    def test_accept_rate_low_green_insufficient_data(self):
        from packages.research.monitoring.health_checks import evaluate_health

        # Only 3 total docs - below threshold of 5
        runs = [self._make_run_record(accepted=0, rejected=3)]
        results = {r.check_name: r for r in evaluate_health(runs)}
        assert results["accept_rate_low"].status == "GREEN"

    def test_accept_rate_high_yellow(self):
        from packages.research.monitoring.health_checks import evaluate_health

        # 11 accepted out of 11 total = 100% > 90%, and total > 10
        runs = [self._make_run_record(accepted=11, rejected=0)]
        results = {r.check_name: r for r in evaluate_health(runs)}
        assert results["accept_rate_high"].status == "YELLOW"

    def test_accept_rate_high_green_small_volume(self):
        from packages.research.monitoring.health_checks import evaluate_health

        # 10 out of 10 = 100%, but total == 10, not > 10
        runs = [self._make_run_record(accepted=10, rejected=0)]
        results = {r.check_name: r for r in evaluate_health(runs)}
        assert results["accept_rate_high"].status == "GREEN"

    def test_model_unavailable_always_green(self):
        from packages.research.monitoring.health_checks import evaluate_health

        for runs in [[], [self._make_run_record()]]:
            results = {r.check_name: r for r in evaluate_health(runs)}
            assert results["model_unavailable"].status == "GREEN"

    def test_rejection_audit_disagreement_yellow(self):
        from packages.research.monitoring.health_checks import evaluate_health

        runs = [self._make_run_record()]
        results = {r.check_name: r for r in evaluate_health(runs, audit_disagreement_rate=0.40)}
        assert results["rejection_audit_disagreement"].status == "YELLOW"

    def test_rejection_audit_disagreement_green_below_threshold(self):
        from packages.research.monitoring.health_checks import evaluate_health

        runs = [self._make_run_record()]
        results = {r.check_name: r for r in evaluate_health(runs, audit_disagreement_rate=0.20)}
        assert results["rejection_audit_disagreement"].status == "GREEN"

    def test_rejection_audit_disagreement_green_when_none(self):
        from packages.research.monitoring.health_checks import evaluate_health

        runs = [self._make_run_record()]
        results = {r.check_name: r for r in evaluate_health(runs, audit_disagreement_rate=None)}
        assert results["rejection_audit_disagreement"].status == "GREEN"

    def test_evaluate_health_returns_all_six_checks(self):
        from packages.research.monitoring.health_checks import evaluate_health, ALL_CHECKS

        results = evaluate_health([])
        assert len(results) == 6
        check_names = {r.check_name for r in results}
        expected = {
            "pipeline_failed",
            "no_new_docs_48h",
            "accept_rate_low",
            "accept_rate_high",
            "model_unavailable",
            "rejection_audit_disagreement",
        }
        assert check_names == expected

    def test_health_check_result_has_required_fields(self):
        from packages.research.monitoring.health_checks import evaluate_health

        results = evaluate_health([])
        for r in results:
            assert hasattr(r, "check_name")
            assert hasattr(r, "status")
            assert hasattr(r, "message")
            assert hasattr(r, "data")
            assert r.status in ("GREEN", "YELLOW", "RED")
            assert isinstance(r.message, str)
            assert isinstance(r.data, dict)


# ---------------------------------------------------------------------------
# AlertSink tests
# ---------------------------------------------------------------------------

class TestAlertSink:

    def _make_result(self, status: str, check_name: str = "test_check") -> object:
        from packages.research.monitoring.health_checks import HealthCheckResult
        return HealthCheckResult(
            check_name=check_name,
            status=status,
            message="test message",
            data={},
        )

    def test_log_sink_returns_true(self, caplog):
        from packages.research.monitoring.alert_sink import LogSink

        sink = LogSink()
        result = self._make_result("RED")
        with caplog.at_level(logging.WARNING, logger="ris.alerts"):
            ret = sink.fire(result)
        assert ret is True

    def test_log_sink_no_network_calls(self):
        from packages.research.monitoring.alert_sink import LogSink

        sink = LogSink()
        result = self._make_result("YELLOW")
        # Should not raise any network-related error
        ret = sink.fire(result)
        assert ret is True

    def test_webhook_sink_returns_true_on_200(self):
        from packages.research.monitoring.alert_sink import WebhookSink

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.ok = True

        with patch("requests.post", return_value=mock_response) as mock_post:
            sink = WebhookSink(webhook_url="http://example.com/webhook")
            result = self._make_result("RED")
            ret = sink.fire(result)
            assert ret is True
            mock_post.assert_called_once()

    def test_webhook_sink_returns_false_on_exception(self):
        from packages.research.monitoring.alert_sink import WebhookSink

        with patch("requests.post", side_effect=Exception("network error")):
            sink = WebhookSink(webhook_url="http://example.com/webhook")
            result = self._make_result("RED")
            ret = sink.fire(result)
            assert ret is False

    def test_fire_alerts_skips_green(self):
        from packages.research.monitoring.alert_sink import LogSink, fire_alerts

        sink = MagicMock(spec=LogSink)
        sink.fire.return_value = True

        from packages.research.monitoring.health_checks import HealthCheckResult
        results = [
            HealthCheckResult("check_a", "GREEN", "ok", {}),
            HealthCheckResult("check_b", "YELLOW", "warn", {}),
            HealthCheckResult("check_c", "RED", "error", {}),
            HealthCheckResult("check_d", "GREEN", "ok", {}),
        ]
        count = fire_alerts(results, sink)

        assert count == 2
        assert sink.fire.call_count == 2
        # GREEN checks should not be in fired calls
        fired_names = [call.args[0].check_name for call in sink.fire.call_args_list]
        assert "check_b" in fired_names
        assert "check_c" in fired_names
        assert "check_a" not in fired_names
        assert "check_d" not in fired_names

    def test_fire_alerts_all_green_returns_zero(self):
        from packages.research.monitoring.alert_sink import LogSink, fire_alerts
        from packages.research.monitoring.health_checks import HealthCheckResult

        sink = MagicMock(spec=LogSink)
        sink.fire.return_value = True

        results = [
            HealthCheckResult("check_a", "GREEN", "ok", {}),
            HealthCheckResult("check_b", "GREEN", "ok", {}),
        ]
        count = fire_alerts(results, sink)
        assert count == 0
        sink.fire.assert_not_called()

    def test_fire_alerts_with_log_sink_no_network(self):
        from packages.research.monitoring.alert_sink import LogSink, fire_alerts
        from packages.research.monitoring.health_checks import HealthCheckResult

        sink = LogSink()
        results = [
            HealthCheckResult("check_a", "YELLOW", "warn", {}),
            HealthCheckResult("check_b", "RED", "error", {}),
        ]
        # Should complete without raising (no network calls)
        count = fire_alerts(results, sink)
        assert count == 2


# ---------------------------------------------------------------------------
# Module __init__ exports
# ---------------------------------------------------------------------------

class TestMonitoringInit:

    def test_all_public_symbols_importable(self):
        from packages.research.monitoring import (
            RunRecord,
            append_run,
            list_runs,
            load_last_run,
            HealthCheckResult,
            HealthCheck,
            ALL_CHECKS,
            evaluate_health,
            AlertSink,
            LogSink,
            WebhookSink,
            fire_alerts,
        )
        # Just checking they exist and are not None
        assert RunRecord is not None
        assert ALL_CHECKS is not None
        assert len(ALL_CHECKS) == 6


# ---------------------------------------------------------------------------
# CLI tests (research_health.main)
# ---------------------------------------------------------------------------

class TestResearchHealthCLI:

    def test_no_run_log_exits_zero_prints_no_data(self, tmp_path, capsys):
        from tools.cli.research_health import main

        log_path = tmp_path / "run_log.jsonl"
        ret = main(["--run-log", str(log_path)])
        assert ret == 0
        captured = capsys.readouterr()
        assert "No run data" in captured.out or "no_data" in captured.out or "0 runs" in captured.out

    def test_json_no_data_valid_json(self, tmp_path, capsys):
        from tools.cli.research_health import main

        log_path = tmp_path / "run_log.jsonl"
        ret = main(["--json", "--run-log", str(log_path)])
        assert ret == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert "checks" in data
        assert "summary" in data
        assert "run_count" in data
        assert data["run_count"] == 0
        assert data["summary"] == "no_data"

    def test_error_run_shows_red(self, tmp_path, capsys):
        from packages.research.monitoring.run_log import RunRecord, append_run
        from tools.cli.research_health import main

        log_path = tmp_path / "run_log.jsonl"
        rec = RunRecord(
            pipeline="ris_ingest",
            started_at=_iso_utc(_now()),
            duration_s=1.0,
            accepted=0,
            rejected=0,
            errors=1,
            exit_status="error",
        )
        append_run(rec, path=log_path)

        ret = main(["--run-log", str(log_path)])
        assert ret == 0
        captured = capsys.readouterr()
        assert "RED" in captured.out

    def test_json_with_error_run_shows_red_summary(self, tmp_path, capsys):
        from packages.research.monitoring.run_log import RunRecord, append_run
        from tools.cli.research_health import main

        log_path = tmp_path / "run_log.jsonl"
        rec = RunRecord(
            pipeline="ris_ingest",
            started_at=_iso_utc(_now()),
            duration_s=1.0,
            accepted=0,
            rejected=0,
            errors=1,
            exit_status="error",
        )
        append_run(rec, path=log_path)

        ret = main(["--json", "--run-log", str(log_path)])
        assert ret == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["summary"] == "RED"

    def test_window_hours_filters_runs(self, tmp_path, capsys):
        from packages.research.monitoring.run_log import RunRecord, append_run
        from tools.cli.research_health import main

        log_path = tmp_path / "run_log.jsonl"
        now = _now()

        # Old error run (2 hours ago) - within 1h window? No
        old_rec = RunRecord(
            pipeline="ris_ingest",
            started_at=_iso_utc(now - timedelta(hours=2)),
            duration_s=1.0,
            accepted=0,
            rejected=0,
            errors=1,
            exit_status="error",
        )
        append_run(old_rec, path=log_path)

        # --window-hours 1 should exclude the 2h-old error run
        ret = main(["--window-hours", "1", "--run-log", str(log_path)])
        assert ret == 0
        captured = capsys.readouterr()
        # No RED since the error run is outside the window
        assert "RED" not in captured.out

    def test_no_live_network_in_cli(self, tmp_path, capsys):
        """CLI must not make any network calls during health check."""
        from tools.cli.research_health import main

        log_path = tmp_path / "run_log.jsonl"
        # Patch requests to fail if called
        with patch("requests.post", side_effect=Exception("NO NETWORK ALLOWED")):
            ret = main(["--run-log", str(log_path)])
        assert ret == 0  # Should complete without network
