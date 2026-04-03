"""Deterministic offline tests for RIS report persistence and catalog.

Tests cover:
- TestReportPersistence: persist_report, list_reports (tests 1-5, 18-19)
- TestReportSearch: search_reports (tests 6-9)
- TestDigestGeneration: generate_digest (tests 10-12, 20)
- TestCLI: CLI subcommand routing (tests 13-17)

All tests use tmp_path. No network calls.
"""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path

import pytest

from packages.research.synthesis.report_ledger import (
    DEFAULT_REPORT_INDEX_FILENAME,
    ReportEntry,
    generate_digest,
    list_reports,
    persist_report,
    search_reports,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_precheck_ledger(path: Path, events: list[dict]) -> None:
    """Write a minimal precheck_ledger.jsonl for digest tests."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for ev in events:
            fh.write(json.dumps(ev) + "\n")


def _index_path(report_dir: Path) -> Path:
    return report_dir / DEFAULT_REPORT_INDEX_FILENAME


# ---------------------------------------------------------------------------
# TestReportPersistence
# ---------------------------------------------------------------------------

class TestReportPersistence:
    """Tests 1-5, 18-19: persist_report and list_reports."""

    def test_01_persist_creates_markdown_file_and_index(self, tmp_path):
        """Test 1: persist_report creates markdown file and appends to index JSONL."""
        rdir = tmp_path / "reports"
        entry = persist_report(
            title="Test Report",
            body_md="# Test Report\n\nHello world.",
            report_dir=rdir,
        )
        # Markdown file should exist
        artifact = Path(entry.artifact_path)
        assert artifact.exists(), "Markdown file was not created"
        assert "Hello world." in artifact.read_text(encoding="utf-8")
        # Index should exist with one line
        index = _index_path(rdir)
        assert index.exists(), "report_index.jsonl was not created"
        lines = [l for l in index.read_text(encoding="utf-8").splitlines() if l.strip()]
        assert len(lines) == 1
        row = json.loads(lines[0])
        assert row["title"] == "Test Report"

    def test_02_persist_returns_correct_report_entry(self, tmp_path):
        """Test 2: persist_report with all fields populated returns correct ReportEntry."""
        rdir = tmp_path / "reports"
        entry = persist_report(
            title="Full Fields Report",
            body_md="Report body text.",
            report_type="precheck_summary",
            source_window="7d",
            summary_line="Key finding here",
            tags=["market-maker", "analysis"],
            metadata={"extra_key": "extra_val"},
            report_dir=rdir,
        )
        assert isinstance(entry, ReportEntry)
        assert entry.title == "Full Fields Report"
        assert entry.report_type == "precheck_summary"
        assert entry.source_window == "7d"
        assert entry.summary_line == "Key finding here"
        assert "market-maker" in entry.tags
        assert "analysis" in entry.tags
        assert entry.metadata["extra_key"] == "extra_val"
        assert len(entry.report_id) == 12
        assert entry.created_at  # non-empty ISO timestamp

    def test_03_list_reports_sorted_descending(self, tmp_path):
        """Test 3: list_reports returns entries sorted by created_at descending."""
        rdir = tmp_path / "reports"
        # Persist two reports; inject custom created_at via index manipulation
        persist_report(title="Report A", body_md="body A", report_dir=rdir)
        persist_report(title="Report B", body_md="body B", report_dir=rdir)

        reports = list_reports(report_dir=rdir)
        assert len(reports) == 2
        # Later creation should appear first
        assert reports[0]["created_at"] >= reports[1]["created_at"]

    def test_04_list_reports_window_filter_excludes_out_of_range(self, tmp_path):
        """Test 4: list_reports with window filter excludes out-of-range entries."""
        rdir = tmp_path / "reports"
        # Write two index entries with manual timestamps
        index = _index_path(rdir)
        rdir.mkdir(parents=True, exist_ok=True)
        entry_old = {
            "report_id": "aaa111bbb222",
            "title": "Old Report",
            "report_type": "custom",
            "created_at": "2020-01-01T00:00:00+00:00",
            "artifact_path": str(rdir / "2020-01-01_aaa111bbb222.md"),
            "source_window": "all",
            "summary_line": "old",
            "tags": [],
            "metadata": {},
            "schema_version": "report_ledger_v1",
        }
        entry_new = {
            "report_id": "ccc333ddd444",
            "title": "New Report",
            "report_type": "custom",
            "created_at": "2026-04-01T12:00:00+00:00",
            "artifact_path": str(rdir / "2026-04-01_ccc333ddd444.md"),
            "source_window": "all",
            "summary_line": "new",
            "tags": [],
            "metadata": {},
            "schema_version": "report_ledger_v1",
        }
        with index.open("w", encoding="utf-8") as fh:
            fh.write(json.dumps(entry_old) + "\n")
            fh.write(json.dumps(entry_new) + "\n")

        reports = list_reports(
            report_dir=rdir,
            window_start="2026-01-01T00:00:00+00:00",
            window_end="2026-12-31T23:59:59+00:00",
        )
        assert len(reports) == 1
        assert reports[0]["title"] == "New Report"

    def test_05_list_reports_empty_dir_returns_empty(self, tmp_path):
        """Test 5: list_reports on empty/missing index returns []."""
        rdir = tmp_path / "empty_reports"
        result = list_reports(report_dir=rdir)
        assert result == []

    def test_18_report_id_deterministic(self, tmp_path):
        """Test 18: report_id is deterministic for same title+timestamp."""
        from packages.research.synthesis.report_ledger import _make_report_id
        rid1 = _make_report_id("Same Title", "2026-04-01T10:00:00+00:00")
        rid2 = _make_report_id("Same Title", "2026-04-01T10:00:00+00:00")
        assert rid1 == rid2
        assert len(rid1) == 12

    def test_19_multiple_persists_append_not_overwrite(self, tmp_path):
        """Test 19: multiple persist_report calls append correctly (no overwrite)."""
        rdir = tmp_path / "reports"
        for i in range(3):
            persist_report(title=f"Report {i}", body_md=f"body {i}", report_dir=rdir)

        index = _index_path(rdir)
        lines = [l for l in index.read_text(encoding="utf-8").splitlines() if l.strip()]
        assert len(lines) == 3
        titles = {json.loads(l)["title"] for l in lines}
        assert titles == {"Report 0", "Report 1", "Report 2"}


# ---------------------------------------------------------------------------
# TestReportSearch
# ---------------------------------------------------------------------------

class TestReportSearch:
    """Tests 6-9: search_reports."""

    def _seed_reports(self, rdir: Path) -> None:
        """Seed three reports with varied titles, summaries, and tags."""
        persist_report(
            title="Market Maker Edge Analysis",
            body_md="Detailed market maker analysis.",
            summary_line="Market maker spread and fill quality",
            tags=["market-maker", "edge"],
            report_dir=rdir,
        )
        persist_report(
            title="Crypto Pair Strategy Review",
            body_md="Review of crypto pair performance.",
            summary_line="BTC/ETH pair strategy outcomes",
            tags=["crypto", "pair-bot"],
            report_dir=rdir,
        )
        persist_report(
            title="Weekly Digest April 2026",
            body_md="Digest of research this week.",
            summary_line="Summary of precheck and eval results",
            tags=["digest", "automated"],
            report_dir=rdir,
        )

    def test_06_search_matches_title_case_insensitive(self, tmp_path):
        """Test 6: search_reports matches on title substring (case-insensitive)."""
        rdir = tmp_path / "reports"
        self._seed_reports(rdir)
        results = search_reports(query="market maker", report_dir=rdir)
        assert len(results) == 1
        assert results[0]["title"] == "Market Maker Edge Analysis"

    def test_07_search_matches_tags(self, tmp_path):
        """Test 7: search_reports matches on tags."""
        rdir = tmp_path / "reports"
        self._seed_reports(rdir)
        results = search_reports(query="pair-bot", report_dir=rdir)
        assert len(results) == 1
        assert results[0]["title"] == "Crypto Pair Strategy Review"

    def test_08_search_matches_summary_line(self, tmp_path):
        """Test 8: search_reports matches on summary_line."""
        rdir = tmp_path / "reports"
        self._seed_reports(rdir)
        results = search_reports(query="precheck and eval", report_dir=rdir)
        assert len(results) == 1
        assert "Digest" in results[0]["title"]

    def test_09_search_no_match_returns_empty(self, tmp_path):
        """Test 9: search_reports with no matches returns []."""
        rdir = tmp_path / "reports"
        self._seed_reports(rdir)
        results = search_reports(query="zzz_no_match_xyz_999", report_dir=rdir)
        assert results == []


# ---------------------------------------------------------------------------
# TestDigestGeneration
# ---------------------------------------------------------------------------

class TestDigestGeneration:
    """Tests 10-12, 20: generate_digest."""

    def _make_precheck_events(self, tmp_path: Path) -> Path:
        """Create a minimal precheck ledger with mixed recommendations."""
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)

        def iso(dt):
            return dt.replace(microsecond=0).isoformat()

        events = [
            {
                "schema_version": "precheck_ledger_v2",
                "event_type": "precheck_run",
                "recommendation": "GO",
                "idea": "Test idea alpha",
                "supporting_evidence": ["evidence A"],
                "contradicting_evidence": [],
                "risk_factors": [],
                "stale_warning": False,
                "timestamp": iso(now),
                "provider_used": "manual",
                "precheck_id": "abc001",
                "reason_code": None,
                "evidence_gap": None,
                "review_horizon": None,
                "written_at": iso(now),
            },
            {
                "schema_version": "precheck_ledger_v2",
                "event_type": "precheck_run",
                "recommendation": "CAUTION",
                "idea": "Test idea beta",
                "supporting_evidence": [],
                "contradicting_evidence": ["concern B"],
                "risk_factors": ["risk C"],
                "stale_warning": True,
                "timestamp": iso(now),
                "provider_used": "manual",
                "precheck_id": "abc002",
                "reason_code": None,
                "evidence_gap": None,
                "review_horizon": None,
                "written_at": iso(now),
            },
            {
                "schema_version": "precheck_ledger_v2",
                "event_type": "precheck_run",
                "recommendation": "STOP",
                "idea": "Test idea gamma",
                "supporting_evidence": [],
                "contradicting_evidence": ["strong contra"],
                "risk_factors": [],
                "stale_warning": False,
                "timestamp": iso(now),
                "provider_used": "manual",
                "precheck_id": "abc003",
                "reason_code": None,
                "evidence_gap": None,
                "review_horizon": None,
                "written_at": iso(now),
            },
        ]

        ledger_path = tmp_path / "prechecks" / "precheck_ledger.jsonl"
        _make_precheck_ledger(ledger_path, events)
        return ledger_path

    def test_10_generate_digest_creates_report(self, tmp_path):
        """Test 10: generate_digest creates digest report with correct structure."""
        rdir = tmp_path / "reports"
        ledger_path = self._make_precheck_events(tmp_path)
        eval_dir = tmp_path / "eval_artifacts"  # empty dir

        entry = generate_digest(
            window_days=7,
            report_dir=rdir,
            precheck_ledger_path=ledger_path,
            eval_artifacts_dir=eval_dir,
        )

        assert isinstance(entry, ReportEntry)
        assert entry.report_type == "weekly_digest"
        assert "digest" in entry.tags
        assert "automated" in entry.tags
        assert Path(entry.artifact_path).exists()

    def test_11_generate_digest_empty_precheck_ledger_succeeds(self, tmp_path):
        """Test 11: generate_digest with empty precheck ledger still succeeds."""
        rdir = tmp_path / "reports"
        ledger_path = tmp_path / "prechecks" / "precheck_ledger.jsonl"
        ledger_path.parent.mkdir(parents=True, exist_ok=True)
        ledger_path.write_text("", encoding="utf-8")
        eval_dir = tmp_path / "eval_artifacts"

        entry = generate_digest(
            window_days=7,
            report_dir=rdir,
            precheck_ledger_path=ledger_path,
            eval_artifacts_dir=eval_dir,
        )
        assert entry.report_type == "weekly_digest"
        md_content = Path(entry.artifact_path).read_text(encoding="utf-8")
        assert "## Prechecks" in md_content

    def test_12_generate_digest_markdown_contains_expected_sections(self, tmp_path):
        """Test 12: generate_digest markdown contains expected sections."""
        rdir = tmp_path / "reports"
        ledger_path = self._make_precheck_events(tmp_path)
        eval_dir = tmp_path / "eval_artifacts"

        entry = generate_digest(
            window_days=7,
            report_dir=rdir,
            precheck_ledger_path=ledger_path,
            eval_artifacts_dir=eval_dir,
        )
        md_content = Path(entry.artifact_path).read_text(encoding="utf-8")
        assert "## Prechecks" in md_content
        assert "## Evaluations" in md_content
        assert "## Reports Generated" in md_content
        assert "## Key Observations" in md_content

    def test_20_generate_digest_includes_precheck_counts(self, tmp_path):
        """Test 20: generate_digest includes precheck counts in markdown body."""
        rdir = tmp_path / "reports"
        ledger_path = self._make_precheck_events(tmp_path)
        eval_dir = tmp_path / "eval_artifacts"

        entry = generate_digest(
            window_days=7,
            report_dir=rdir,
            precheck_ledger_path=ledger_path,
            eval_artifacts_dir=eval_dir,
        )
        md_content = Path(entry.artifact_path).read_text(encoding="utf-8")
        # Expect GO/CAUTION/STOP counts in the body
        assert "GO" in md_content
        assert "CAUTION" in md_content
        assert "STOP" in md_content
        # Should list at least one precheck idea
        assert "Test idea alpha" in md_content
        # Metadata should record counts
        assert entry.metadata["precheck_count"] == 3


# ---------------------------------------------------------------------------
# TestCLI
# ---------------------------------------------------------------------------

class TestCLI:
    """Tests 13-17: CLI subcommand routing."""

    def test_13_cli_save_with_body_exits_zero(self, tmp_path):
        """Test 13: CLI save subcommand with --body writes report and exits 0."""
        from tools.cli.research_report import main
        rdir = str(tmp_path / "reports")
        rc = main([
            "save",
            "--title", "CLI Test Report",
            "--body", "This is the report body.",
            "--report-dir", rdir,
        ])
        assert rc == 0
        index = tmp_path / "reports" / DEFAULT_REPORT_INDEX_FILENAME
        assert index.exists()
        lines = [l for l in index.read_text(encoding="utf-8").splitlines() if l.strip()]
        assert len(lines) == 1
        row = json.loads(lines[0])
        assert row["title"] == "CLI Test Report"

    def test_14_cli_list_exits_zero(self, tmp_path):
        """Test 14: CLI list subcommand exits 0."""
        from tools.cli.research_report import main
        rdir = str(tmp_path / "empty_reports")
        rc = main(["list", "--window", "all", "--report-dir", rdir])
        assert rc == 0

    def test_15_cli_search_exits_zero(self, tmp_path):
        """Test 15: CLI search subcommand exits 0."""
        from tools.cli.research_report import main
        rdir = str(tmp_path / "empty_reports")
        rc = main(["search", "--query", "any keyword", "--report-dir", rdir])
        assert rc == 0

    def test_16_cli_digest_exits_zero(self, tmp_path):
        """Test 16: CLI digest subcommand exits 0."""
        from tools.cli.research_report import main
        rdir = str(tmp_path / "reports")
        # Empty ledger and eval dir
        ledger = tmp_path / "prechecks" / "precheck_ledger.jsonl"
        ledger.parent.mkdir(parents=True, exist_ok=True)
        ledger.write_text("", encoding="utf-8")
        eval_dir = str(tmp_path / "eval_artifacts")
        rc = main([
            "digest",
            "--window", "7",
            "--precheck-ledger", str(ledger),
            "--eval-artifacts-dir", eval_dir,
            "--report-dir", rdir,
        ])
        assert rc == 0

    def test_17_cli_help_exits_without_error(self, tmp_path):
        """Test 17: CLI backward compat: --help exits without error."""
        from tools.cli.research_report import main
        with pytest.raises(SystemExit) as exc_info:
            main(["--help"])
        # argparse --help exits with code 0
        assert exc_info.value.code == 0

    def test_13b_cli_save_json_output(self, tmp_path):
        """Additional: CLI save --json returns valid JSON with report_id."""
        import io
        from contextlib import redirect_stdout

        from tools.cli.research_report import main
        rdir = str(tmp_path / "reports")
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = main([
                "save",
                "--title", "JSON Output Test",
                "--body", "Body content here.",
                "--report-dir", rdir,
                "--json",
            ])
        assert rc == 0
        output = json.loads(buf.getvalue())
        assert "report_id" in output
        assert output["title"] == "JSON Output Test"
