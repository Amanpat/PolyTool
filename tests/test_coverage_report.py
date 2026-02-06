"""Tests for polytool.reports.coverage — Coverage & Reconciliation Report."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from polytool.reports.coverage import (
    build_coverage_report,
    normalize_fee_fields,
    write_coverage_report,
)


def _make_positions():
    """Build a synthetic set of positions for testing."""
    return [
        {
            "resolved_token_id": "tok_001",
            "resolution_outcome": "WIN",
            "realized_pnl_net": 10.5,
            "fees_actual": 0.25,
            "fees_estimated": 0.0,
            "fees_source": "actual",
            "position_remaining": 5.0,
        },
        {
            "resolved_token_id": "tok_002",
            "resolution_outcome": "LOSS",
            "realized_pnl_net": -3.2,
            "fees_actual": 0.0,
            "fees_estimated": 0.12,
            "fees_source": "estimated",
            "position_remaining": 2.0,
        },
        {
            "resolved_token_id": "tok_003",
            "resolution_outcome": "PROFIT_EXIT",
            "realized_pnl_net": 7.0,
            "fees_actual": 0.0,
            "fees_estimated": 0.0,
            "fees_source": "unknown",
            "position_remaining": 0.0,
        },
        {
            "resolved_token_id": "tok_004",
            "resolution_outcome": "LOSS_EXIT",
            "realized_pnl_net": -1.0,
            "fees_actual": 0.0,
            "fees_estimated": 0.0,
            "fees_source": "unknown",
            "position_remaining": 0.0,
        },
        {
            "resolved_token_id": "tok_005",
            "resolution_outcome": "PENDING",
            "realized_pnl_net": 0.0,
            "fees_actual": 0.0,
            "fees_estimated": 0.0,
            "fees_source": "unknown",
            "position_remaining": 10.0,
        },
        {
            "resolved_token_id": "tok_006",
            "resolution_outcome": "UNKNOWN_RESOLUTION",
            "realized_pnl_net": None,
            "fees_actual": 0.0,
            "fees_estimated": 0.0,
            "fees_source": "unknown",
            "position_remaining": 0.0,
        },
    ]


class TestNormalizeFeeFields:
    def test_actual_fee_sets_source(self):
        pos = {"fees_actual": 1.5, "fees_estimated": 0.0}
        normalize_fee_fields(pos)
        assert pos["fees_source"] == "actual"

    def test_estimated_fee_sets_source(self):
        pos = {"fees_actual": 0.0, "fees_estimated": 0.5}
        normalize_fee_fields(pos)
        assert pos["fees_source"] == "estimated"

    def test_no_fees_sets_unknown(self):
        pos = {"fees_actual": 0.0, "fees_estimated": 0.0}
        normalize_fee_fields(pos)
        assert pos["fees_source"] == "unknown"

    def test_missing_fields_default(self):
        pos = {}
        normalize_fee_fields(pos)
        assert pos["fees_actual"] == 0.0
        assert pos["fees_estimated"] == 0.0
        assert pos["fees_source"] == "unknown"

    def test_actual_takes_precedence(self):
        pos = {"fees_actual": 2.0, "fees_estimated": 1.0}
        normalize_fee_fields(pos)
        assert pos["fees_source"] == "actual"


class TestBuildCoverageReport:
    def test_outcome_counts(self):
        positions = _make_positions()
        report = build_coverage_report(
            positions=positions,
            run_id="test-run-001",
            user_slug="testuser",
            wallet="0xabc",
        )
        assert report["totals"]["positions_total"] == 6
        assert report["outcome_counts"]["WIN"] == 1
        assert report["outcome_counts"]["LOSS"] == 1
        assert report["outcome_counts"]["PROFIT_EXIT"] == 1
        assert report["outcome_counts"]["LOSS_EXIT"] == 1
        assert report["outcome_counts"]["PENDING"] == 1
        assert report["outcome_counts"]["UNKNOWN_RESOLUTION"] == 1

    def test_outcome_percentages_sum_to_one(self):
        positions = _make_positions()
        report = build_coverage_report(
            positions=positions,
            run_id="test-run",
            user_slug="testuser",
            wallet="0xabc",
        )
        total_pct = sum(report["outcome_percentages"].values())
        assert abs(total_pct - 1.0) < 0.001

    def test_trade_uid_coverage_no_duplicates(self):
        positions = _make_positions()
        report = build_coverage_report(
            positions=positions,
            run_id="test-run",
            user_slug="testuser",
            wallet="0xabc",
        )
        tuc = report["trade_uid_coverage"]
        assert tuc["total"] == 6
        assert tuc["with_trade_uid"] == 6
        assert tuc["duplicate_trade_uid_count"] == 0

    def test_trade_uid_duplicates_detected(self):
        positions = [
            {"resolved_token_id": "dup1", "resolution_outcome": "WIN",
             "realized_pnl_net": 1.0, "position_remaining": 0.0},
            {"resolved_token_id": "dup1", "resolution_outcome": "LOSS",
             "realized_pnl_net": -1.0, "position_remaining": 0.0},
        ]
        report = build_coverage_report(
            positions=positions,
            run_id="test-run",
            user_slug="testuser",
            wallet="0xabc",
        )
        assert report["trade_uid_coverage"]["duplicate_trade_uid_count"] == 1
        assert "dup1" in report["trade_uid_coverage"]["duplicate_sample"]

    def test_pnl_totals(self):
        positions = _make_positions()
        report = build_coverage_report(
            positions=positions,
            run_id="test-run",
            user_slug="testuser",
            wallet="0xabc",
        )
        pnl = report["pnl"]
        # 10.5 + (-3.2) + 7.0 + (-1.0) + 0.0 = 13.3  (None is skipped)
        assert abs(pnl["realized_pnl_net_total"] - 13.3) < 0.001
        assert pnl["missing_realized_pnl_count"] == 1  # tok_006 has None

    def test_fee_source_counts(self):
        positions = _make_positions()
        report = build_coverage_report(
            positions=positions,
            run_id="test-run",
            user_slug="testuser",
            wallet="0xabc",
        )
        fees = report["fees"]
        assert fees["fees_source_counts"]["actual"] == 1
        assert fees["fees_source_counts"]["estimated"] == 1
        assert fees["fees_source_counts"]["unknown"] == 4
        assert fees["fees_actual_present_count"] == 1
        assert fees["fees_estimated_present_count"] == 1

    def test_resolution_coverage(self):
        positions = _make_positions()
        report = build_coverage_report(
            positions=positions,
            run_id="test-run",
            user_slug="testuser",
            wallet="0xabc",
        )
        res = report["resolution_coverage"]
        # resolved = total - PENDING = 6 - 1 = 5
        assert res["resolved_total"] == 5
        assert res["unknown_resolution_total"] == 1
        # held_to_resolution: position_remaining > 0 AND not PENDING/UNKNOWN
        # tok_001 (WIN, remaining=5) and tok_002 (LOSS, remaining=2) = 2
        assert res["held_to_resolution_total"] == 2
        # WIN + LOSS = 2, held_to_resolution = 2 -> rate = 1.0
        assert res["win_loss_covered_rate"] == 1.0

    def test_warnings_for_unknown_resolution(self):
        # 2/3 = 66% unknown -> should trigger warning
        positions = [
            {"resolved_token_id": "a", "resolution_outcome": "UNKNOWN_RESOLUTION",
             "realized_pnl_net": 0.0, "position_remaining": 0.0},
            {"resolved_token_id": "b", "resolution_outcome": "UNKNOWN_RESOLUTION",
             "realized_pnl_net": 0.0, "position_remaining": 0.0},
            {"resolved_token_id": "c", "resolution_outcome": "WIN",
             "realized_pnl_net": 1.0, "position_remaining": 0.0},
        ]
        report = build_coverage_report(
            positions=positions,
            run_id="test-run",
            user_slug="testuser",
            wallet="0xabc",
        )
        assert any("UNKNOWN_RESOLUTION" in w for w in report["warnings"])

    def test_empty_positions(self):
        report = build_coverage_report(
            positions=[],
            run_id="empty-run",
            user_slug="testuser",
            wallet="0xabc",
        )
        assert report["totals"]["positions_total"] == 0
        assert report["pnl"]["realized_pnl_net_total"] == 0.0
        assert report["warnings"] == []

    def test_report_has_required_fields(self):
        report = build_coverage_report(
            positions=_make_positions(),
            run_id="test-run",
            user_slug="testuser",
            wallet="0xabc",
        )
        required = [
            "report_version", "generated_at", "run_id", "user_slug",
            "wallet", "proxy_wallet", "totals", "outcome_counts",
            "outcome_percentages", "trade_uid_coverage", "pnl",
            "fees", "resolution_coverage", "warnings",
        ]
        for field in required:
            assert field in report, f"Missing required field: {field}"

    def test_no_network_required(self):
        """Building a report must not require any network/service access."""
        # This test simply verifies the function completes without error
        # when given purely synthetic data and no external dependencies.
        report = build_coverage_report(
            positions=_make_positions(),
            run_id="offline-run",
            user_slug="testuser",
            wallet="0xabc",
        )
        assert report["report_version"] == "1.0.0"


class TestWriteCoverageReport:
    def test_writes_json_and_md(self, tmp_path):
        report = build_coverage_report(
            positions=_make_positions(),
            run_id="write-test",
            user_slug="testuser",
            wallet="0xabc",
        )
        paths = write_coverage_report(report, tmp_path, write_markdown=True)
        assert "json" in paths
        assert "md" in paths

        # Verify JSON is valid
        json_data = json.loads(Path(paths["json"]).read_text(encoding="utf-8"))
        assert json_data["run_id"] == "write-test"

        # Verify Markdown contains key sections
        md_text = Path(paths["md"]).read_text(encoding="utf-8")
        assert "# Coverage & Reconciliation Report" in md_text
        assert "Outcome Distribution" in md_text

    def test_json_only(self, tmp_path):
        report = build_coverage_report(
            positions=_make_positions(),
            run_id="json-only",
            user_slug="testuser",
            wallet="0xabc",
        )
        paths = write_coverage_report(report, tmp_path, write_markdown=False)
        assert "json" in paths
        assert "md" not in paths
