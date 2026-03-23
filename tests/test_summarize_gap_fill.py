"""Tests for tools.cli.summarize_gap_fill (read-only gap-fill summariser).

All tests are offline and deterministic — no network, no ClickHouse.
"""

from __future__ import annotations

import io
import json
import textwrap
from pathlib import Path
from unittest.mock import patch

import pytest

from tools.cli.summarize_gap_fill import (
    SUPPORTED_SCHEMA,
    _normalize_error,
    _normalize_warning,
    main,
    summarize,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_outcome(
    *,
    token_id: str = "0" * 64,
    bucket: str = "politics",
    slug: str = "test-slug",
    priority: int = 1,
    status: str = "success",
    skip_reason=None,
    reconstruction_confidence: str = "low",
    event_count: int = 10,
    fill_count: int = 0,
    price_2min_count: int = 10,
    warnings=None,
    error=None,
    out_dir: str = "artifacts/silver/abc/2026-01-01",
    events_path: str = "artifacts/silver/abc/2026-01-01/silver_events.jsonl",
    metadata_write: str = "clickhouse",
) -> dict:
    return {
        "token_id": token_id,
        "bucket": bucket,
        "slug": slug,
        "priority": priority,
        "status": status,
        "skip_reason": skip_reason,
        "reconstruction_confidence": reconstruction_confidence,
        "event_count": event_count,
        "fill_count": fill_count,
        "price_2min_count": price_2min_count,
        "warning_count": len(warnings or []),
        "warnings": warnings or [],
        "out_dir": out_dir,
        "events_path": events_path,
        "error": error,
        "metadata_write": metadata_write,
        "metadata_write_detail": "",
        "window_start": "2026-01-01T00:00:00+00:00",
        "window_end": "2026-01-01T06:00:00+00:00",
    }


def _make_run(
    *,
    outcomes=None,
    targets_attempted: int = 3,
    tapes_created: int = 3,
    failure_count: int = 0,
    skip_count: int = 0,
    dry_run: bool = False,
    benchmark_refresh: dict | None = None,
) -> dict:
    return {
        "schema_version": SUPPORTED_SCHEMA,
        "batch_run_id": "test-run-id-001",
        "started_at": "2026-01-01T00:00:00+00:00",
        "ended_at": "2026-01-01T01:00:00+00:00",
        "dry_run": dry_run,
        "targets_attempted": targets_attempted,
        "tapes_created": tapes_created,
        "failure_count": failure_count,
        "skip_count": skip_count,
        "metadata_summary": {"clickhouse": 3, "jsonl_fallback": 0, "skipped": 0},
        "out_root": "artifacts",
        "benchmark_refresh": benchmark_refresh or {"triggered": False, "outcome": "not_requested"},
        "outcomes": outcomes if outcomes is not None else [],
    }


# ---------------------------------------------------------------------------
# Unit: normalization helpers
# ---------------------------------------------------------------------------

class TestNormalizeWarning:
    def test_extracts_class_prefix(self):
        w = "pmxt_anchor_missing: no pmxt snapshot found at or before window_start=..."
        assert _normalize_warning(w) == "pmxt_anchor_missing"

    def test_extracts_jon_fills_class(self):
        w = "jon_fills_missing: no Jon-Becker fills found for token 12345678901234567890"
        assert _normalize_warning(w) == "jon_fills_missing"

    def test_fallback_strips_token_ids(self):
        w = "some warning with token 12345678901234567890 embedded"
        result = _normalize_warning(w)
        assert "12345678901234567890" not in result
        assert "<TOKEN>" in result

    def test_short_warning_no_colon(self):
        w = "generic problem"
        result = _normalize_warning(w)
        assert result == "generic problem"


class TestNormalizeError:
    def test_strips_long_numbers(self):
        e = "error fetching token 98765432109876543210: connection refused"
        result = _normalize_error(e)
        assert "98765432109876543210" not in result
        assert "<TOKEN>" in result

    def test_strips_timestamps(self):
        e = "error at 2026-01-01T12:00:00+00:00"
        result = _normalize_error(e)
        assert "2026-01-01T12:00:00" not in result
        assert "<TS>" in result

    def test_truncates_at_120(self):
        e = "x" * 200
        assert len(_normalize_error(e)) <= 120

    def test_empty_string(self):
        assert _normalize_error("") == ""


# ---------------------------------------------------------------------------
# Unit: summarize()
# ---------------------------------------------------------------------------

class TestSummarize:
    def test_totals_from_top_level_fields(self):
        run = _make_run(
            targets_attempted=5,
            tapes_created=4,
            failure_count=1,
            skip_count=0,
        )
        s = summarize(run)
        assert s["totals"]["targets_attempted"] == 5
        assert s["totals"]["tapes_created"] == 4
        assert s["totals"]["failure_count"] == 1
        assert s["totals"]["skip_count"] == 0

    def test_by_bucket_groups_correctly(self):
        outcomes = [
            _make_outcome(bucket="politics", status="success", reconstruction_confidence="low"),
            _make_outcome(bucket="politics", status="success", reconstruction_confidence="high"),
            _make_outcome(bucket="sports", status="failure", reconstruction_confidence="none", error="boom"),
        ]
        s = summarize(_make_run(outcomes=outcomes))
        assert s["by_bucket"]["politics"]["success"] == 2
        assert s["by_bucket"]["politics"]["failure"] == 0
        assert s["by_bucket"]["sports"]["failure"] == 1
        assert s["by_bucket"]["sports"]["success"] == 0

    def test_confidence_breakdown_in_bucket(self):
        outcomes = [
            _make_outcome(bucket="crypto", status="success", reconstruction_confidence="low"),
            _make_outcome(bucket="crypto", status="success", reconstruction_confidence="low"),
            _make_outcome(bucket="crypto", status="success", reconstruction_confidence="high"),
        ]
        s = summarize(_make_run(outcomes=outcomes))
        conf = s["by_bucket"]["crypto"]["confidence_breakdown"]
        assert conf["low"] == 2
        assert conf["high"] == 1

    def test_warning_classes_normalized(self):
        outcomes = [
            _make_outcome(warnings=["pmxt_anchor_missing: detail1", "jon_fills_missing: detail2"]),
            _make_outcome(warnings=["pmxt_anchor_missing: other detail"]),
        ]
        s = summarize(_make_run(outcomes=outcomes))
        wc = s["warning_classes"]
        assert wc["pmxt_anchor_missing"] == 2
        assert wc["jon_fills_missing"] == 1

    def test_error_classes_normalized(self):
        outcomes = [
            _make_outcome(status="failure", error="ConnectionError: host unreachable"),
            _make_outcome(status="failure", error="ConnectionError: host unreachable"),
            _make_outcome(status="failure", error="KeyError: token_id"),
        ]
        s = summarize(_make_run(outcomes=outcomes, failure_count=3, tapes_created=0))
        ec = s["error_classes"]
        # Both connection errors map to the same normalized class
        # (they're short enough that normalization is a passthrough with <120 truncation)
        assert sum(ec.values()) == 3

    def test_success_class_price_2min_only(self):
        outcomes = [
            _make_outcome(
                status="success",
                reconstruction_confidence="low",
                fill_count=0,
                price_2min_count=28,
            ),
        ]
        s = summarize(_make_run(outcomes=outcomes))
        sc = s["success_classes"]
        assert any("price_2min_only" in k for k in sc)

    def test_success_class_has_fills(self):
        outcomes = [
            _make_outcome(
                status="success",
                reconstruction_confidence="high",
                fill_count=5,
                price_2min_count=20,
            ),
        ]
        s = summarize(_make_run(outcomes=outcomes))
        sc = s["success_classes"]
        assert any("has_fills" in k for k in sc)

    def test_artifact_paths_collected(self):
        outcomes = [
            _make_outcome(
                events_path="artifacts/silver/aaa/silver_events.jsonl",
                out_dir="artifacts/silver/aaa",
            ),
            _make_outcome(
                events_path="artifacts/silver/bbb/silver_events.jsonl",
                out_dir="artifacts/silver/bbb",
            ),
        ]
        s = summarize(_make_run(outcomes=outcomes))
        assert "artifacts/silver/aaa/silver_events.jsonl" in s["artifact_paths"]
        assert "artifacts/silver/bbb/silver_events.jsonl" in s["artifact_paths"]

    def test_artifact_paths_deduped(self):
        outcomes = [
            _make_outcome(events_path="same/path.jsonl", out_dir="same"),
            _make_outcome(events_path="same/path.jsonl", out_dir="same"),
        ]
        s = summarize(_make_run(outcomes=outcomes))
        assert s["artifact_paths"].count("same/path.jsonl") == 1

    def test_skip_outcomes_counted(self):
        outcomes = [
            _make_outcome(status="skip", skip_reason="missing token_id", bucket="politics"),
            _make_outcome(status="success", bucket="politics"),
        ]
        s = summarize(_make_run(outcomes=outcomes, skip_count=1, tapes_created=1))
        assert s["by_bucket"]["politics"]["skip"] == 1
        assert s["by_bucket"]["politics"]["success"] == 1

    def test_benchmark_refresh_passthrough(self):
        refresh = {"triggered": True, "outcome": "gap_report_updated", "return_code": 2}
        s = summarize(_make_run(benchmark_refresh=refresh))
        assert s["benchmark_refresh"]["triggered"] is True
        assert s["benchmark_refresh"]["outcome"] == "gap_report_updated"

    def test_empty_outcomes(self):
        s = summarize(_make_run(outcomes=[], targets_attempted=0, tapes_created=0))
        assert s["totals"]["targets_attempted"] == 0
        assert s["by_bucket"] == {}
        assert s["warning_classes"] == {}
        assert s["error_classes"] == {}

    def test_unknown_bucket_fallback(self):
        outcomes = [_make_outcome(bucket="")]
        s = summarize(_make_run(outcomes=outcomes))
        # Empty bucket name maps to "unknown"
        assert "unknown" in s["by_bucket"]


# ---------------------------------------------------------------------------
# Integration: main() CLI
# ---------------------------------------------------------------------------

class TestMain:
    def _write_fixture(self, tmp_path: Path, data: dict) -> Path:
        p = tmp_path / "gap_fill_run.json"
        p.write_text(json.dumps(data, indent=2), encoding="utf-8")
        return p

    def test_returns_0_on_valid_file(self, tmp_path, capsys):
        run = _make_run(outcomes=[_make_outcome()])
        p = self._write_fixture(tmp_path, run)
        rc = main(["--path", str(p)])
        assert rc == 0

    def test_returns_1_on_missing_file(self, capsys):
        rc = main(["--path", "/nonexistent/path/gap_fill_run.json"])
        assert rc == 1
        captured = capsys.readouterr()
        assert "not found" in captured.err

    def test_returns_1_on_invalid_json(self, tmp_path, capsys):
        p = tmp_path / "bad.json"
        p.write_text("not json {{{", encoding="utf-8")
        rc = main(["--path", str(p)])
        assert rc == 1
        captured = capsys.readouterr()
        assert "invalid JSON" in captured.err

    def test_returns_1_on_non_object_json(self, tmp_path, capsys):
        p = tmp_path / "arr.json"
        p.write_text("[1, 2, 3]", encoding="utf-8")
        rc = main(["--path", str(p)])
        assert rc == 1
        captured = capsys.readouterr()
        assert "JSON object" in captured.err

    def test_warns_on_unknown_schema_version(self, tmp_path, capsys):
        run = _make_run()
        run["schema_version"] = "some_future_schema_v99"
        p = self._write_fixture(tmp_path, run)
        rc = main(["--path", str(p)])
        assert rc == 0
        captured = capsys.readouterr()
        assert "schema_version" in captured.err

    def test_human_output_contains_totals(self, tmp_path, capsys):
        run = _make_run(
            outcomes=[_make_outcome()],
            targets_attempted=3,
            tapes_created=3,
            failure_count=0,
            skip_count=0,
        )
        p = self._write_fixture(tmp_path, run)
        main(["--path", str(p)])
        out = capsys.readouterr().out
        assert "targets_attempted" in out
        assert "tapes_created" in out

    def test_human_output_contains_bucket_section(self, tmp_path, capsys):
        outcomes = [
            _make_outcome(bucket="politics"),
            _make_outcome(bucket="sports"),
        ]
        run = _make_run(outcomes=outcomes)
        p = self._write_fixture(tmp_path, run)
        main(["--path", str(p)])
        out = capsys.readouterr().out
        assert "BY BUCKET" in out
        assert "politics" in out
        assert "sports" in out

    def test_human_output_shows_warning_classes(self, tmp_path, capsys):
        outcomes = [
            _make_outcome(warnings=["pmxt_anchor_missing: some detail"]),
        ]
        run = _make_run(outcomes=outcomes)
        p = self._write_fixture(tmp_path, run)
        main(["--path", str(p)])
        out = capsys.readouterr().out
        assert "pmxt_anchor_missing" in out

    def test_json_flag_emits_parseable_json(self, tmp_path, capsys):
        run = _make_run(outcomes=[_make_outcome()])
        p = self._write_fixture(tmp_path, run)
        rc = main(["--path", str(p), "--json"])
        assert rc == 0
        out = capsys.readouterr().out
        parsed = json.loads(out)
        assert "totals" in parsed
        assert "by_bucket" in parsed
        assert "warning_classes" in parsed

    def test_json_output_totals_correct(self, tmp_path, capsys):
        run = _make_run(
            targets_attempted=5,
            tapes_created=4,
            failure_count=1,
            outcomes=[
                _make_outcome(status="success"),
                _make_outcome(status="success"),
                _make_outcome(status="success"),
                _make_outcome(status="success"),
                _make_outcome(status="failure", error="boom"),
            ],
        )
        p = self._write_fixture(tmp_path, run)
        main(["--path", str(p), "--json"])
        out = capsys.readouterr().out
        parsed = json.loads(out)
        assert parsed["totals"]["targets_attempted"] == 5
        assert parsed["totals"]["failure_count"] == 1

    def test_path_shown_in_header(self, tmp_path, capsys):
        run = _make_run(outcomes=[_make_outcome()])
        p = self._write_fixture(tmp_path, run)
        main(["--path", str(p)])
        out = capsys.readouterr().out
        assert str(p) in out

    def test_dry_run_flag_visible_in_output(self, tmp_path, capsys):
        run = _make_run(dry_run=True, outcomes=[_make_outcome()])
        p = self._write_fixture(tmp_path, run)
        main(["--path", str(p)])
        out = capsys.readouterr().out
        assert "DRY RUN" in out or "dry_run" in out


# ---------------------------------------------------------------------------
# Smoke test against real probe-3 fixture shape
# ---------------------------------------------------------------------------

PROBE3_FIXTURE = {
    "schema_version": "benchmark_gap_fill_run_v1",
    "batch_run_id": "be6018cf-05f0-492a-a2d7-732f8f29ac7f",
    "started_at": "2026-03-19T23:04:44.318447+00:00",
    "ended_at": "2026-03-19T23:06:08.471094+00:00",
    "dry_run": False,
    "targets_attempted": 3,
    "tapes_created": 3,
    "failure_count": 0,
    "skip_count": 0,
    "metadata_summary": {"clickhouse": 3, "jsonl_fallback": 0, "skipped": 0},
    "out_root": "artifacts",
    "benchmark_refresh": {"triggered": False, "outcome": "not_requested"},
    "outcomes": [
        {
            "token_id": "74401044150815233212315835920011636780189603928313623397904798907525089171384",
            "bucket": "politics",
            "slug": "100-tariff-on-canada-in-effect-by-june-30",
            "priority": 1,
            "status": "success",
            "skip_reason": None,
            "reconstruction_confidence": "low",
            "event_count": 28,
            "fill_count": 0,
            "price_2min_count": 28,
            "warning_count": 2,
            "warnings": [
                "pmxt_anchor_missing: no pmxt snapshot found...",
                "jon_fills_missing: no Jon-Becker fills found...",
            ],
            "out_dir": "artifacts\\silver\\7440104415081523\\2026-03-15T10-00-09Z",
            "events_path": "artifacts\\silver\\7440104415081523\\2026-03-15T10-00-09Z\\silver_events.jsonl",
            "error": None,
            "metadata_write": "clickhouse",
            "metadata_write_detail": "",
            "window_start": "2026-03-15T10:00:09.554000+00:00",
            "window_end": "2026-03-15T14:59:42.056000+00:00",
        },
        {
            "token_id": "64683994534201646450394391725616228695952599577525859664835161186648784031970",
            "bucket": "sports",
            "slug": "2025-2026-epl-winner-more-than-90-points",
            "priority": 1,
            "status": "success",
            "skip_reason": None,
            "reconstruction_confidence": "low",
            "event_count": 29,
            "fill_count": 0,
            "price_2min_count": 29,
            "warning_count": 2,
            "warnings": [
                "pmxt_anchor_missing: no pmxt snapshot found...",
                "jon_fills_missing: no Jon-Becker fills found...",
            ],
            "out_dir": "artifacts\\silver\\6468399453420164\\2026-03-15T10-00-15Z",
            "events_path": "artifacts\\silver\\6468399453420164\\2026-03-15T10-00-15Z\\silver_events.jsonl",
            "error": None,
            "metadata_write": "clickhouse",
            "metadata_write_detail": "",
            "window_start": "2026-03-15T10:00:15.373000+00:00",
            "window_end": "2026-03-15T14:59:20.801000+00:00",
        },
        {
            "token_id": "113005234308749261641273809104525222871932092818248517014310727082878210014694",
            "bucket": "crypto",
            "slug": "another-crypto-hack-over-100m-before-2027",
            "priority": 1,
            "status": "success",
            "skip_reason": None,
            "reconstruction_confidence": "low",
            "event_count": 28,
            "fill_count": 0,
            "price_2min_count": 28,
            "warning_count": 2,
            "warnings": [
                "pmxt_anchor_missing: no pmxt snapshot...",
                "jon_fills_missing: no Jon-Becker fills...",
            ],
            "out_dir": "artifacts\\silver\\1130052343087492\\2026-03-15T10-00-48Z",
            "events_path": "artifacts\\silver\\1130052343087492\\2026-03-15T10-00-48Z\\silver_events.jsonl",
            "error": None,
            "metadata_write": "clickhouse",
            "metadata_write_detail": "",
            "window_start": "2026-03-15T10:00:48.018000+00:00",
            "window_end": "2026-03-15T14:57:01.370000+00:00",
        },
    ],
}


class TestProbe3Smoke:
    def test_summarize_probe3(self):
        s = summarize(PROBE3_FIXTURE)
        assert s["totals"]["targets_attempted"] == 3
        assert s["totals"]["tapes_created"] == 3
        assert s["totals"]["failure_count"] == 0
        # All three buckets present
        assert "politics" in s["by_bucket"]
        assert "sports" in s["by_bucket"]
        assert "crypto" in s["by_bucket"]
        # All success, all low confidence
        for bucket in ("politics", "sports", "crypto"):
            assert s["by_bucket"][bucket]["success"] == 1
            assert s["by_bucket"][bucket]["confidence_breakdown"]["low"] == 1
        # Two warning classes, 3 occurrences each
        assert s["warning_classes"]["pmxt_anchor_missing"] == 3
        assert s["warning_classes"]["jon_fills_missing"] == 3
        # No errors
        assert s["error_classes"] == {}
        # All price_2min_only
        assert all("price_2min_only" in k for k in s["success_classes"])

    def test_main_probe3_smoke(self, tmp_path, capsys):
        p = tmp_path / "gap_fill_run.json"
        p.write_text(json.dumps(PROBE3_FIXTURE, indent=2), encoding="utf-8")
        rc = main(["--path", str(p)])
        assert rc == 0
        out = capsys.readouterr().out
        assert "politics" in out
        assert "sports" in out
        assert "crypto" in out
        assert "pmxt_anchor_missing" in out
        assert "jon_fills_missing" in out
        assert "price_2min_only" in out
