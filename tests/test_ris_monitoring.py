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

    def test_pipeline_failed_yellow_on_operator_blocked_partial(self):
        from packages.research.monitoring.health_checks import evaluate_health

        runs = [
            self._make_run_record(
                pipeline="reddit_polymarket",
                exit_status="partial",
                metadata={
                    "operator_status": "missing_setup",
                    "operator_message": "Install praw and set REDDIT_* vars",
                },
            )
        ]
        results = {r.check_name: r for r in evaluate_health(runs)}
        assert results["pipeline_failed"].status == "YELLOW"
        assert "reddit_polymarket blocked" in results["pipeline_failed"].message

    def test_pipeline_failed_ignores_stale_error_when_newer_partial_exists(self):
        from packages.research.monitoring.health_checks import evaluate_health

        runs = [
            self._make_run_record(
                pipeline="reddit_polymarket",
                started_at="2026-04-08T19:00:00+00:00",
                exit_status="partial",
                metadata={
                    "operator_status": "missing_setup",
                    "operator_message": "Install praw and set REDDIT_* vars",
                },
            ),
            self._make_run_record(
                pipeline="reddit_polymarket",
                started_at="2026-04-08T18:00:00+00:00",
                exit_status="error",
            ),
        ]
        results = {r.check_name: r for r in evaluate_health(runs)}
        assert results["pipeline_failed"].status == "YELLOW"
        assert "18:00:00" not in results["pipeline_failed"].message

    def test_pipeline_failed_red_includes_current_blocked_and_failed_pipelines(self):
        from packages.research.monitoring.health_checks import evaluate_health

        runs = [
            self._make_run_record(
                pipeline="blog_ingest",
                started_at="2026-04-08T20:00:00+00:00",
                exit_status="error",
            ),
            self._make_run_record(
                pipeline="reddit_polymarket",
                started_at="2026-04-08T19:00:00+00:00",
                exit_status="partial",
                metadata={
                    "operator_status": "missing_setup",
                    "operator_message": "Install praw and set REDDIT_* vars",
                },
            ),
        ]
        results = {r.check_name: r for r in evaluate_health(runs)}
        assert results["pipeline_failed"].status == "RED"
        assert "blog_ingest failed" in results["pipeline_failed"].message
        assert "reddit_polymarket blocked" in results["pipeline_failed"].message

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

    def test_model_unavailable_green_no_failures(self):
        from packages.research.monitoring.health_checks import evaluate_health

        # No provider failure data -> GREEN
        for runs in [[], [self._make_run_record()]]:
            results = {r.check_name: r for r in evaluate_health(runs, provider_failure_counts={})}
            r = results["model_unavailable"]
            assert r.status == "GREEN"
            assert r.data.get("deferred") is not True

    def test_model_unavailable_always_green_backward_compat(self):
        """Backward compat: no provider_failure_counts kwarg -> GREEN, not deferred."""
        from packages.research.monitoring.health_checks import evaluate_health

        results = {r.check_name: r for r in evaluate_health([])}
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

    def test_evaluate_health_returns_all_seven_checks(self):
        from packages.research.monitoring.health_checks import evaluate_health, ALL_CHECKS

        results = evaluate_health([])
        assert len(results) == 7
        check_names = {r.check_name for r in results}
        expected = {
            "pipeline_failed",
            "no_new_docs_48h",
            "accept_rate_low",
            "accept_rate_high",
            "model_unavailable",
            "review_queue_backlog",
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
        assert len(ALL_CHECKS) == 7


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


# ---------------------------------------------------------------------------
# Task 1: CLI run_log wiring tests
# ---------------------------------------------------------------------------

class TestCLIRunLogWiring:
    """Tests that research-ingest and research-acquire write RunRecords to run_log."""

    def test_ingest_writes_run_log(self, tmp_path):
        """research_ingest.main writes a RunRecord after successful ingest."""
        from packages.research.monitoring.run_log import list_runs
        from tools.cli.research_ingest import main

        fixture = tmp_path / "test_doc.md"
        fixture.write_text(
            "# Test Document\n\n"
            "This document discusses prediction market content, "
            "market maker strategies, and arbitrage opportunities."
        )
        log_path = tmp_path / "run_log.jsonl"

        ret = main(["--file", str(fixture), "--no-eval", "--run-log", str(log_path)])
        assert ret == 0, f"main() returned {ret}"

        runs = list_runs(path=log_path)
        assert len(runs) == 1, f"Expected 1 run record, got {len(runs)}"
        r = runs[0]
        assert r.pipeline == "research_ingest"
        assert r.accepted == 1
        assert r.rejected == 0
        assert r.exit_status == "ok"
        assert r.duration_s > 0

    def test_ingest_rejected_writes_run_log(self, tmp_path, monkeypatch):
        """When ingest returns rejected=True, run_log has accepted=0, rejected=1, exit_status='ok'."""
        from packages.research.monitoring.run_log import list_runs
        from packages.research.ingestion.pipeline import IngestResult

        rejected_result = IngestResult(
            doc_id="",
            chunk_count=0,
            gate_decision=None,
            rejected=True,
            reject_reason="hard_stop: low quality",
        )

        import packages.research.ingestion.pipeline as pipeline_mod
        monkeypatch.setattr(
            pipeline_mod.IngestPipeline, "ingest", lambda self, *a, **kw: rejected_result
        )

        from tools.cli.research_ingest import main

        fixture = tmp_path / "test_doc.md"
        fixture.write_text("# Low quality doc")
        log_path = tmp_path / "run_log.jsonl"

        ret = main(["--file", str(fixture), "--no-eval", "--run-log", str(log_path)])
        assert ret == 0

        runs = list_runs(path=log_path)
        assert len(runs) == 1
        r = runs[0]
        assert r.accepted == 0
        assert r.rejected == 1
        assert r.exit_status == "ok"

    def test_ingest_error_writes_run_log(self, tmp_path, monkeypatch):
        """When ingest raises, run_log has errors=1, exit_status='error'."""
        from packages.research.monitoring.run_log import list_runs
        import packages.research.ingestion.pipeline as pipeline_mod

        monkeypatch.setattr(
            pipeline_mod.IngestPipeline, "ingest",
            lambda self, *a, **kw: (_ for _ in ()).throw(RuntimeError("simulated failure")),
        )

        from tools.cli.research_ingest import main

        fixture = tmp_path / "test_doc.md"
        fixture.write_text("# Test Document")
        log_path = tmp_path / "run_log.jsonl"

        # CLI returns 2 on exception, but run_log should still be written
        ret = main(["--file", str(fixture), "--no-eval", "--run-log", str(log_path)])
        assert ret == 2

        runs = list_runs(path=log_path)
        assert len(runs) == 1
        r = runs[0]
        assert r.errors == 1
        assert r.exit_status == "error"

    def test_acquire_dryrun_no_run_log(self, tmp_path, monkeypatch):
        """research_acquire.main with --dry-run does NOT write a run_log entry."""
        import packages.research.ingestion.fetchers as fetchers_mod

        def _arxiv_bytes(url, timeout, headers):
            xml = b"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <id>http://arxiv.org/abs/2301.12345v1</id>
    <title>Test Paper</title>
    <summary>Abstract text.</summary>
    <author><name>Test Author</name></author>
    <published>2024-01-01T00:00:00Z</published>
  </entry>
</feed>"""
            return xml

        monkeypatch.setattr(fetchers_mod, "_default_urlopen", _arxiv_bytes)

        from tools.cli.research_acquire import main

        log_path = tmp_path / "run_log.jsonl"
        ret = main([
            "--url", "https://arxiv.org/abs/2301.12345",
            "--source-family", "academic",
            "--dry-run",
            "--no-eval",
            "--run-log", str(log_path),
        ])
        assert ret == 0
        # Dry-run: no run_log entry
        assert not log_path.exists() or log_path.read_text(encoding="utf-8").strip() == ""

    def test_acquire_writes_run_log(self, tmp_path, monkeypatch):
        """After a successful acquire (mocked fetch), run_log contains a RunRecord."""
        import packages.research.ingestion.fetchers as fetchers_mod

        def _arxiv_bytes(url, timeout, headers):
            xml = b"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <id>http://arxiv.org/abs/2301.12345v1</id>
    <title>Test Paper</title>
    <summary>Abstract text for prediction markets.</summary>
    <author><name>Test Author</name></author>
    <published>2024-01-01T00:00:00Z</published>
  </entry>
</feed>"""
            return xml

        monkeypatch.setattr(fetchers_mod, "_default_urlopen", _arxiv_bytes)

        from tools.cli.research_acquire import main
        from packages.research.monitoring.run_log import list_runs

        log_path = tmp_path / "run_log.jsonl"
        db_path = tmp_path / "test.sqlite3"
        cache_dir = tmp_path / "cache"
        review_dir = tmp_path / "reviews"

        ret = main([
            "--url", "https://arxiv.org/abs/2301.12345",
            "--source-family", "academic",
            "--no-eval",
            "--run-log", str(log_path),
            "--db", str(db_path),
            "--cache-dir", str(cache_dir),
            "--review-dir", str(review_dir),
        ])
        assert ret == 0

        runs = list_runs(path=log_path)
        assert len(runs) == 1
        r = runs[0]
        assert r.pipeline == "research_acquire"
        assert r.exit_status == "ok"

    def test_run_log_write_failure_is_nonfatal(self, tmp_path, monkeypatch):
        """When append_run raises, CLI still returns 0 (run_log write is non-fatal)."""
        import packages.research.monitoring.run_log as run_log_mod
        monkeypatch.setattr(run_log_mod, "append_run", lambda *a, **kw: (_ for _ in ()).throw(OSError("disk full")))

        from tools.cli.research_ingest import main

        fixture = tmp_path / "test_doc.md"
        fixture.write_text(
            "# Test Document\n\n"
            "This document discusses prediction market content, "
            "market maker strategies, and arbitrage opportunities."
        )

        ret = main(["--file", str(fixture), "--no-eval", "--run-log", str(tmp_path / "run_log.jsonl")])
        assert ret == 0, f"CLI returned {ret} instead of 0 when append_run raises"


# ---------------------------------------------------------------------------
# Task 2: Health check truthfulness tests
# ---------------------------------------------------------------------------

class TestHealthTruthfulness:
    """Tests that deferred checks are clearly labeled as [DEFERRED], not misleadingly GREEN."""

    def test_model_unavailable_message_says_no_failures(self):
        """evaluate_health([]) -> model_unavailable result message indicates no failures (not deferred)."""
        from packages.research.monitoring.health_checks import evaluate_health

        results = {r.check_name: r for r in evaluate_health([])}
        r = results["model_unavailable"]
        assert r.data.get("deferred") is not True
        assert r.status == "GREEN"

    def test_rejection_audit_none_says_deferred(self):
        """When audit_disagreement_rate=None, message contains '[DEFERRED]'."""
        from packages.research.monitoring.health_checks import evaluate_health
        from packages.research.monitoring.run_log import RunRecord

        runs = []
        results = {r.check_name: r for r in evaluate_health(runs, audit_disagreement_rate=None)}
        r = results["rejection_audit_disagreement"]
        assert "[DEFERRED]" in r.message, f"Expected [DEFERRED] in message, got: {r.message!r}"

    def test_deferred_checks_still_green(self):
        """Deferred check (rejection_audit_disagreement) still returns GREEN."""
        from packages.research.monitoring.health_checks import evaluate_health

        results = {r.check_name: r for r in evaluate_health([], audit_disagreement_rate=None)}
        assert results["model_unavailable"].status == "GREEN"
        assert results["rejection_audit_disagreement"].status == "GREEN"

    def test_model_unavailable_not_stub(self):
        """model_unavailable check does NOT have check_type='stub' - it is now real."""
        from packages.research.monitoring.health_checks import evaluate_health

        results = {r.check_name: r for r in evaluate_health([])}
        r = results["model_unavailable"]
        assert r.data.get("check_type") != "stub"

    def test_rejection_audit_none_has_check_type_stub(self):
        """rejection_audit_disagreement with None has check_type='stub' in data dict."""
        from packages.research.monitoring.health_checks import evaluate_health

        results = {r.check_name: r for r in evaluate_health([], audit_disagreement_rate=None)}
        r = results["rejection_audit_disagreement"]
        assert r.data.get("check_type") == "stub"


class TestIntegrationIngestToHealth:
    """Integration tests: ingest -> run_log -> research-health reads real data."""

    def test_ingest_to_run_log_to_health_green(self, tmp_path, capsys):
        """File ingest -> run_log write -> research-health reads the run and reports non-no_data status."""
        from tools.cli.research_ingest import main as ingest_main
        from tools.cli.research_health import main as health_main

        fixture = tmp_path / "test_doc.md"
        fixture.write_text(
            "# Prediction Market Research\n\n"
            "This paper discusses market maker strategies, bid-ask spreads, "
            "and inventory risk in prediction market contexts."
        )
        log_path = tmp_path / "run_log.jsonl"
        db_path = tmp_path / "test.sqlite3"

        # Step 1: ingest writes to run_log
        ret = ingest_main([
            "--file", str(fixture),
            "--no-eval",
            "--run-log", str(log_path),
            "--db", str(db_path),
        ])
        assert ret == 0, f"ingest returned {ret}"

        # Capture previous stdout from ingest
        capsys.readouterr()

        # Step 2: health reads the run_log and reports real data
        ret = health_main(["--run-log", str(log_path), "--json"])
        assert ret == 0

        captured = capsys.readouterr()
        data = json.loads(captured.out)

        assert data["summary"] != "no_data", f"Expected non-no_data summary, got: {data['summary']}"
        assert data["run_count"] >= 1, f"Expected run_count >= 1, got: {data['run_count']}"

        # pipeline_failed should be GREEN since ingest succeeded
        checks = {c["check_name"]: c for c in data["checks"]}
        assert checks["pipeline_failed"]["status"] == "GREEN"

    def test_health_json_includes_deferred_checks(self, tmp_path, capsys):
        """health --json output includes 'deferred_checks' list with both stub check names."""
        from packages.research.monitoring.run_log import RunRecord, append_run
        from tools.cli.research_health import main as health_main

        log_path = tmp_path / "run_log.jsonl"
        # Write at least one run so we don't hit no_data path
        rec = RunRecord(
            pipeline="research_ingest",
            started_at=_iso_utc(_now()),
            duration_s=1.0,
            accepted=1,
            rejected=0,
            errors=0,
            exit_status="ok",
        )
        append_run(rec, path=log_path)

        ret = health_main(["--json", "--run-log", str(log_path)])
        assert ret == 0

        captured = capsys.readouterr()
        data = json.loads(captured.out)

        assert "deferred_checks" in data, "JSON output missing 'deferred_checks' key"
        deferred = data["deferred_checks"]
        # model_unavailable is now real (not deferred)
        assert "model_unavailable" not in deferred, f"model_unavailable should NOT be in deferred_checks: {deferred}"
        assert "rejection_audit_disagreement" in deferred, (
            f"rejection_audit_disagreement not in deferred_checks: {deferred}"
        )

    def test_health_table_includes_deferred_footer(self, tmp_path, capsys):
        """health table output includes footer note about deferred checks when runs present."""
        from packages.research.monitoring.run_log import RunRecord, append_run
        from tools.cli.research_health import main as health_main

        log_path = tmp_path / "run_log.jsonl"
        rec = RunRecord(
            pipeline="research_ingest",
            started_at=_iso_utc(_now()),
            duration_s=1.0,
            accepted=1,
            rejected=0,
            errors=0,
            exit_status="ok",
        )
        append_run(rec, path=log_path)

        ret = health_main(["--run-log", str(log_path)])
        assert ret == 0

        captured = capsys.readouterr()
        assert "DEFERRED" in captured.out, "Expected deferred footer note in table output"
        assert "GREEN = no data, not verified healthy" in captured.out


# ---------------------------------------------------------------------------
# Phase 2: TestMetricsPhase2 — new metrics fields
# ---------------------------------------------------------------------------

class TestMetricsPhase2:
    """Tests for the Phase 2 RIS metrics fields added to RisMetricsSnapshot."""

    def _make_eval_artifact(
        self,
        gate: str = "ACCEPT",
        source_family: str = "academic",
        selected_provider: str = "gemini",
        escalated: bool = False,
        used_fallback: bool = False,
        provider_events: list = None,
        scores: dict = None,
    ) -> dict:
        """Build a minimal eval artifact dict for testing."""
        routing_decision = {
            "mode": "cascade",
            "primary_provider": "gemini",
            "escalation_provider": "deepseek",
            "fallback_provider": "ollama",
            "selected_provider": selected_provider,
            "selected_model": f"{selected_provider}-model",
            "final_reason": "primary_success",
            "attempts": 1,
            "escalated": escalated,
            "used_fallback": used_fallback,
        }
        return {
            "doc_id": "test-doc-001",
            "timestamp": "2026-04-08T10:00:00+00:00",
            "gate": gate,
            "hard_stop_result": None,
            "near_duplicate_result": None,
            "family_features": {},
            "scores": scores or {},
            "source_family": source_family,
            "source_type": "url",
            "provider_events": provider_events or [],
            "routing_decision": routing_decision,
        }

    def _write_eval_artifacts(self, tmp_path: Path, artifacts: list) -> Path:
        """Write eval artifacts JSONL to a temp dir, return the dir."""
        ea_dir = tmp_path / "eval_artifacts"
        ea_dir.mkdir(parents=True, exist_ok=True)
        artifact_file = ea_dir / "eval_artifacts.jsonl"
        lines = [json.dumps(a, ensure_ascii=False) for a in artifacts]
        artifact_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return ea_dir

    def _make_pending_review_db(self, tmp_path: Path, rows: list) -> Path:
        """Create a sqlite3 DB with a pending_review table and given rows."""
        import sqlite3
        db_path = tmp_path / "knowledge.sqlite3"
        conn = sqlite3.connect(str(db_path))
        conn.execute("""
            CREATE TABLE IF NOT EXISTS pending_review (
                id TEXT PRIMARY KEY,
                status TEXT,
                gate TEXT,
                provider_name TEXT,
                eval_model TEXT,
                weighted_score REAL,
                source_family TEXT,
                created_at TEXT,
                updated_at TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS source_documents (
                id TEXT PRIMARY KEY,
                source_family TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS derived_claims (
                id TEXT PRIMARY KEY
            )
        """)
        for row in rows:
            conn.execute(
                "INSERT INTO pending_review (id, status, gate, source_family) VALUES (?, ?, ?, ?)",
                (row["id"], row["status"], row.get("gate", "REVIEW"), row.get("source_family", "academic"))
            )
        conn.commit()
        conn.close()
        return db_path

    def test_provider_route_distribution(self, tmp_path):
        """collect_ris_metrics returns provider_route_distribution counting evals per selected_provider."""
        from packages.research.metrics import collect_ris_metrics

        artifacts = [
            self._make_eval_artifact(selected_provider="gemini"),
            self._make_eval_artifact(selected_provider="gemini"),
            self._make_eval_artifact(selected_provider="deepseek"),
            self._make_eval_artifact(selected_provider="ollama"),
        ]
        ea_dir = self._write_eval_artifacts(tmp_path, artifacts)
        db_path = self._make_pending_review_db(tmp_path, [])

        snapshot = collect_ris_metrics(
            db_path=db_path,
            eval_artifacts_dir=ea_dir,
        )

        dist = snapshot.provider_route_distribution
        assert dist.get("gemini") == 2
        assert dist.get("deepseek") == 1
        assert dist.get("ollama") == 1

    def test_provider_failure_counts(self, tmp_path):
        """collect_ris_metrics returns provider_failure_counts from provider_events with non-success status."""
        from packages.research.metrics import collect_ris_metrics

        provider_events_1 = [
            {"provider_name": "gemini", "status": "error", "failure_reason": "provider_unavailable",
             "selected": False, "route_role": "primary"},
            {"provider_name": "deepseek", "status": "success", "failure_reason": None,
             "selected": True, "route_role": "escalation"},
        ]
        provider_events_2 = [
            {"provider_name": "gemini", "status": "error", "failure_reason": "rate_limited",
             "selected": False, "route_role": "primary"},
            {"provider_name": "deepseek", "status": "error", "failure_reason": "provider_unavailable",
             "selected": False, "route_role": "escalation"},
            {"provider_name": "ollama", "status": "success", "failure_reason": None,
             "selected": True, "route_role": "fallback"},
        ]
        artifacts = [
            self._make_eval_artifact(provider_events=provider_events_1),
            self._make_eval_artifact(provider_events=provider_events_2),
        ]
        ea_dir = self._write_eval_artifacts(tmp_path, artifacts)
        db_path = self._make_pending_review_db(tmp_path, [])

        snapshot = collect_ris_metrics(
            db_path=db_path,
            eval_artifacts_dir=ea_dir,
        )

        failures = snapshot.provider_failure_counts
        assert failures.get("provider_unavailable") == 2
        assert failures.get("rate_limited") == 1

    def test_review_queue_from_pending_review(self, tmp_path):
        """collect_ris_metrics populates review_queue from pending_review table."""
        from packages.research.metrics import collect_ris_metrics

        pending_rows = [
            {"id": "doc-1", "status": "pending", "gate": "REVIEW"},
            {"id": "doc-2", "status": "pending", "gate": "REVIEW"},
            {"id": "doc-3", "status": "accepted", "gate": "REVIEW"},
            {"id": "doc-4", "status": "rejected", "gate": "REVIEW"},
        ]
        db_path = self._make_pending_review_db(tmp_path, pending_rows)
        ea_dir = self._write_eval_artifacts(tmp_path, [])

        snapshot = collect_ris_metrics(
            db_path=db_path,
            eval_artifacts_dir=ea_dir,
        )

        q = snapshot.review_queue
        assert q.get("queue_depth") == 2, f"Expected queue_depth=2, got {q}"
        assert q.get("by_status", {}).get("pending") == 2

    def test_review_queue_empty_when_no_table(self, tmp_path):
        """collect_ris_metrics handles missing pending_review table gracefully."""
        from packages.research.metrics import collect_ris_metrics
        import sqlite3

        # DB without pending_review table
        db_path = tmp_path / "knowledge.sqlite3"
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE source_documents (id TEXT PRIMARY KEY, source_family TEXT)")
        conn.execute("CREATE TABLE derived_claims (id TEXT PRIMARY KEY)")
        conn.commit()
        conn.close()

        ea_dir = self._write_eval_artifacts(tmp_path, [])
        snapshot = collect_ris_metrics(db_path=db_path, eval_artifacts_dir=ea_dir)

        # Should be empty dict or have queue_depth=0, not raise
        q = snapshot.review_queue
        assert isinstance(q, dict)
        assert q.get("queue_depth", 0) == 0

    def test_disposition_distribution(self, tmp_path):
        """collect_ris_metrics returns disposition_distribution with ACCEPT/REVIEW/REJECT/BLOCKED counts."""
        from packages.research.metrics import collect_ris_metrics

        artifacts = [
            self._make_eval_artifact(gate="ACCEPT"),
            self._make_eval_artifact(gate="ACCEPT"),
            self._make_eval_artifact(gate="REVIEW"),
            self._make_eval_artifact(gate="REJECT", scores={}),
            self._make_eval_artifact(gate="REJECT", scores={"reject_reason": "scorer_failure"}),
        ]
        ea_dir = self._write_eval_artifacts(tmp_path, artifacts)
        db_path = self._make_pending_review_db(tmp_path, [])

        snapshot = collect_ris_metrics(db_path=db_path, eval_artifacts_dir=ea_dir)

        d = snapshot.disposition_distribution
        assert d.get("ACCEPT") == 2
        assert d.get("REVIEW") == 1
        assert d.get("REJECT") == 1
        assert d.get("BLOCKED") == 1

    def test_routing_summary(self, tmp_path):
        """collect_ris_metrics returns routing_summary with escalation/fallback/direct counts."""
        from packages.research.metrics import collect_ris_metrics

        artifacts = [
            self._make_eval_artifact(escalated=False, used_fallback=False),  # direct
            self._make_eval_artifact(escalated=True, used_fallback=False),   # escalated
            self._make_eval_artifact(escalated=True, used_fallback=False),   # escalated
            self._make_eval_artifact(escalated=False, used_fallback=True),   # fallback
        ]
        ea_dir = self._write_eval_artifacts(tmp_path, artifacts)
        db_path = self._make_pending_review_db(tmp_path, [])

        snapshot = collect_ris_metrics(db_path=db_path, eval_artifacts_dir=ea_dir)

        rs = snapshot.routing_summary
        assert rs.get("escalation_count") == 2
        assert rs.get("fallback_count") == 1
        assert rs.get("direct_count") == 1
        assert rs.get("total_routed") == 4


# ---------------------------------------------------------------------------
# Phase 2: Extended health check tests
# ---------------------------------------------------------------------------

class TestHealthChecksPhase2:
    """Tests for the new Phase 2 health checks."""

    def test_model_unavailable_green_no_failures(self):
        """_check_model_unavailable with empty failure dict returns GREEN."""
        from packages.research.monitoring.health_checks import _check_model_unavailable

        result = _check_model_unavailable({})
        assert result.status == "GREEN"
        assert result.data.get("deferred") is not True
        assert "No provider failures" in result.message

    def test_model_unavailable_yellow_some_failures(self):
        """_check_model_unavailable with one provider >3 failures returns YELLOW."""
        from packages.research.monitoring.health_checks import _check_model_unavailable

        result = _check_model_unavailable({"provider_unavailable": 4})
        assert result.status == "YELLOW"

    def test_model_unavailable_red_all_providers_failing(self):
        """_check_model_unavailable when all configured providers have failures returns RED."""
        from packages.research.monitoring.health_checks import _check_model_unavailable

        routing_config = {"primary_provider": "gemini", "escalation_provider": "deepseek", "fallback_provider": "ollama"}
        failure_counts = {"gemini": 5, "deepseek": 2, "ollama": 1}
        result = _check_model_unavailable(failure_counts, routing_config=routing_config)
        assert result.status == "RED"

    def test_model_unavailable_yellow_partial_providers_failing(self):
        """When only some providers have failures (not all), returns YELLOW not RED."""
        from packages.research.monitoring.health_checks import _check_model_unavailable

        routing_config = {"primary_provider": "gemini", "escalation_provider": "deepseek", "fallback_provider": "ollama"}
        failure_counts = {"gemini": 5}  # only primary failing
        result = _check_model_unavailable(failure_counts, routing_config=routing_config)
        assert result.status == "YELLOW"
        assert result.status != "RED"

    def test_review_queue_backlog_green_small(self):
        """_check_review_queue_backlog with depth<=20 returns GREEN."""
        from packages.research.monitoring.health_checks import _check_review_queue_backlog

        result = _check_review_queue_backlog({"queue_depth": 5, "by_status": {"pending": 5}})
        assert result.status == "GREEN"

    def test_review_queue_backlog_yellow_medium(self):
        """_check_review_queue_backlog with depth>20 returns YELLOW."""
        from packages.research.monitoring.health_checks import _check_review_queue_backlog

        result = _check_review_queue_backlog({"queue_depth": 25, "by_status": {"pending": 25}})
        assert result.status == "YELLOW"

    def test_review_queue_backlog_red_critical(self):
        """_check_review_queue_backlog with depth>50 returns RED."""
        from packages.research.monitoring.health_checks import _check_review_queue_backlog

        result = _check_review_queue_backlog({"queue_depth": 55, "by_status": {"pending": 55}})
        assert result.status == "RED"

    def test_review_queue_backlog_green_empty_dict(self):
        """_check_review_queue_backlog with empty dict returns GREEN."""
        from packages.research.monitoring.health_checks import _check_review_queue_backlog

        result = _check_review_queue_backlog({})
        assert result.status == "GREEN"
        assert "No review queue data" in result.message

    def test_evaluate_health_passes_provider_failures_to_model_unavailable(self):
        """evaluate_health propagates provider_failure_counts to model_unavailable check."""
        from packages.research.monitoring.health_checks import evaluate_health

        # >3 failures -> YELLOW
        results = {r.check_name: r for r in evaluate_health(
            [], provider_failure_counts={"provider_unavailable": 5}
        )}
        assert results["model_unavailable"].status == "YELLOW"

    def test_evaluate_health_passes_review_queue_to_backlog_check(self):
        """evaluate_health propagates review_queue to review_queue_backlog check."""
        from packages.research.monitoring.health_checks import evaluate_health

        # depth=30 -> YELLOW
        results = {r.check_name: r for r in evaluate_health(
            [], review_queue={"queue_depth": 30}
        )}
        assert results["review_queue_backlog"].status == "YELLOW"

    def test_evaluate_health_seven_results(self):
        """evaluate_health returns exactly 7 results."""
        from packages.research.monitoring.health_checks import evaluate_health

        results = evaluate_health([])
        assert len(results) == 7
