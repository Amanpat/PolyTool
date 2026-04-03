"""Deterministic offline tests for packages/research/metrics.py.

All tests use tmp_path or in-memory data. No network, no ClickHouse.
"""

from __future__ import annotations

import io
import json
import sqlite3
from contextlib import redirect_stdout
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _create_ks_db(path: Path, docs: list[dict], claims: list[dict]) -> None:
    """Create a minimal KnowledgeStore-compatible SQLite at *path*.

    Only the columns read by collect_ris_metrics() are populated.
    """
    conn = sqlite3.connect(str(path))
    conn.execute(
        """CREATE TABLE IF NOT EXISTS source_documents (
            id TEXT PRIMARY KEY,
            source_family TEXT
        )"""
    )
    conn.execute(
        """CREATE TABLE IF NOT EXISTS derived_claims (
            id TEXT PRIMARY KEY
        )"""
    )
    for doc in docs:
        conn.execute(
            "INSERT INTO source_documents (id, source_family) VALUES (?, ?)",
            (doc["id"], doc["source_family"]),
        )
    for claim in claims:
        conn.execute(
            "INSERT INTO derived_claims (id) VALUES (?)",
            (claim["id"],),
        )
    conn.commit()
    conn.close()


def _write_eval_artifacts(artifacts_dir: Path, records: list[dict]) -> None:
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    fpath = artifacts_dir / "eval_artifacts.jsonl"
    with fpath.open("w", encoding="utf-8") as fh:
        for rec in records:
            fh.write(json.dumps(rec) + "\n")


def _write_precheck_ledger(ledger_path: Path, events: list[dict]) -> None:
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    with ledger_path.open("w", encoding="utf-8") as fh:
        for evt in events:
            fh.write(json.dumps(evt) + "\n")


def _write_report_index(report_dir: Path, entries: list[dict]) -> None:
    report_dir.mkdir(parents=True, exist_ok=True)
    index_path = report_dir / "report_index.jsonl"
    with index_path.open("w", encoding="utf-8") as fh:
        for entry in entries:
            fh.write(json.dumps(entry) + "\n")


def _write_acquisition_reviews(review_dir: Path, records: list[dict]) -> None:
    review_dir.mkdir(parents=True, exist_ok=True)
    review_path = review_dir / "acquisition_review.jsonl"
    with review_path.open("w", encoding="utf-8") as fh:
        for rec in records:
            fh.write(json.dumps(rec) + "\n")


# ---------------------------------------------------------------------------
# Import target
# ---------------------------------------------------------------------------

from packages.research.metrics import (
    RisMetricsSnapshot,
    collect_ris_metrics,
    format_metrics_summary,
)


# ---------------------------------------------------------------------------
# Test 1: empty KS -> all counts 0
# ---------------------------------------------------------------------------

def test_empty_ks_returns_zero_counts(tmp_path):
    db_path = tmp_path / "test.sqlite3"
    _create_ks_db(db_path, docs=[], claims=[])
    snapshot = collect_ris_metrics(
        db_path=db_path,
        eval_artifacts_dir=tmp_path / "no_eval",
        precheck_ledger_path=tmp_path / "no_ledger.jsonl",
        report_dir=tmp_path / "no_reports",
        acquisition_review_dir=tmp_path / "no_reviews",
    )
    assert snapshot.total_docs == 0
    assert snapshot.total_claims == 0
    assert snapshot.docs_by_family == {}


# ---------------------------------------------------------------------------
# Test 2: docs_by_family aggregation
# ---------------------------------------------------------------------------

def test_docs_by_family_aggregation(tmp_path):
    db_path = tmp_path / "test.sqlite3"
    _create_ks_db(
        db_path,
        docs=[
            {"id": "d1", "source_family": "academic"},
            {"id": "d2", "source_family": "academic"},
            {"id": "d3", "source_family": "blog"},
        ],
        claims=[],
    )
    snapshot = collect_ris_metrics(
        db_path=db_path,
        eval_artifacts_dir=tmp_path / "no_eval",
        precheck_ledger_path=tmp_path / "no_ledger.jsonl",
        report_dir=tmp_path / "no_reports",
        acquisition_review_dir=tmp_path / "no_reviews",
    )
    assert snapshot.total_docs == 3
    assert snapshot.docs_by_family == {"academic": 2, "blog": 1}


# ---------------------------------------------------------------------------
# Test 3: eval gate distribution
# ---------------------------------------------------------------------------

def test_eval_gate_distribution(tmp_path):
    db_path = tmp_path / "test.sqlite3"
    _create_ks_db(db_path, docs=[], claims=[])
    eval_dir = tmp_path / "eval"
    _write_eval_artifacts(eval_dir, [
        {"gate": "ACCEPT", "source_family": "academic"},
        {"gate": "ACCEPT", "source_family": "blog"},
        {"gate": "ACCEPT", "source_family": "academic"},
        {"gate": "REVIEW", "source_family": "news"},
        {"gate": "REVIEW", "source_family": "reddit"},
        {"gate": "REJECT", "source_family": "blog"},
    ])
    snapshot = collect_ris_metrics(
        db_path=db_path,
        eval_artifacts_dir=eval_dir,
        precheck_ledger_path=tmp_path / "no_ledger.jsonl",
        report_dir=tmp_path / "no_reports",
        acquisition_review_dir=tmp_path / "no_reviews",
    )
    assert snapshot.gate_distribution == {"ACCEPT": 3, "REVIEW": 2, "REJECT": 1}


# ---------------------------------------------------------------------------
# Test 4: ingestion_by_family from eval artifacts
# ---------------------------------------------------------------------------

def test_ingestion_by_family_from_eval_artifacts(tmp_path):
    db_path = tmp_path / "test.sqlite3"
    _create_ks_db(db_path, docs=[], claims=[])
    eval_dir = tmp_path / "eval"
    _write_eval_artifacts(eval_dir, [
        {"gate": "ACCEPT", "source_family": "academic"},
        {"gate": "REJECT", "source_family": "academic"},
        {"gate": "ACCEPT", "source_family": "github"},
    ])
    snapshot = collect_ris_metrics(
        db_path=db_path,
        eval_artifacts_dir=eval_dir,
        precheck_ledger_path=tmp_path / "no_ledger.jsonl",
        report_dir=tmp_path / "no_reports",
        acquisition_review_dir=tmp_path / "no_reviews",
    )
    assert snapshot.ingestion_by_family == {"academic": 2, "github": 1}


# ---------------------------------------------------------------------------
# Test 5: precheck ledger GO/CAUTION/STOP counts; non-precheck_run excluded
# ---------------------------------------------------------------------------

def test_precheck_ledger_decision_counts(tmp_path):
    db_path = tmp_path / "test.sqlite3"
    _create_ks_db(db_path, docs=[], claims=[])
    ledger_path = tmp_path / "precheck_ledger.jsonl"
    _write_precheck_ledger(ledger_path, [
        {"event_type": "precheck_run", "recommendation": "GO"},
        {"event_type": "precheck_run", "recommendation": "GO"},
        {"event_type": "precheck_run", "recommendation": "CAUTION"},
        {"event_type": "precheck_run", "recommendation": "STOP"},
        # These should NOT be counted
        {"event_type": "override", "recommendation": "GO"},
        {"event_type": "outcome", "outcome_label": "successful"},
    ])
    snapshot = collect_ris_metrics(
        db_path=db_path,
        eval_artifacts_dir=tmp_path / "no_eval",
        precheck_ledger_path=ledger_path,
        report_dir=tmp_path / "no_reports",
        acquisition_review_dir=tmp_path / "no_reviews",
    )
    assert snapshot.precheck_decisions == {"GO": 2, "CAUTION": 1, "STOP": 1}


# ---------------------------------------------------------------------------
# Test 6: missing precheck ledger -> zeros, no error
# ---------------------------------------------------------------------------

def test_missing_precheck_ledger_returns_zeros(tmp_path):
    db_path = tmp_path / "test.sqlite3"
    _create_ks_db(db_path, docs=[], claims=[])
    snapshot = collect_ris_metrics(
        db_path=db_path,
        eval_artifacts_dir=tmp_path / "no_eval",
        precheck_ledger_path=tmp_path / "nonexistent.jsonl",
        report_dir=tmp_path / "no_reports",
        acquisition_review_dir=tmp_path / "no_reviews",
    )
    assert snapshot.precheck_decisions == {"GO": 0, "CAUTION": 0, "STOP": 0}


# ---------------------------------------------------------------------------
# Test 7: report index counts by type
# ---------------------------------------------------------------------------

def test_report_index_counts_by_type(tmp_path):
    db_path = tmp_path / "test.sqlite3"
    _create_ks_db(db_path, docs=[], claims=[])
    report_dir = tmp_path / "reports"
    _write_report_index(report_dir, [
        {"report_id": "r1", "report_type": "precheck_summary"},
        {"report_id": "r2", "report_type": "precheck_summary"},
        {"report_id": "r3", "report_type": "weekly_digest"},
    ])
    snapshot = collect_ris_metrics(
        db_path=db_path,
        eval_artifacts_dir=tmp_path / "no_eval",
        precheck_ledger_path=tmp_path / "no_ledger.jsonl",
        report_dir=report_dir,
        acquisition_review_dir=tmp_path / "no_reviews",
    )
    assert snapshot.reports_by_type == {"precheck_summary": 2, "weekly_digest": 1}
    assert snapshot.total_reports == 3


# ---------------------------------------------------------------------------
# Test 8: acquisition review counts
# ---------------------------------------------------------------------------

def test_acquisition_review_counts(tmp_path):
    db_path = tmp_path / "test.sqlite3"
    _create_ks_db(db_path, docs=[], claims=[])
    review_dir = tmp_path / "reviews"
    _write_acquisition_reviews(review_dir, [
        {"dedup_status": "new", "error": None},
        {"dedup_status": "new", "error": None},
        {"dedup_status": "new", "error": None},
        {"dedup_status": "cached", "error": None},
        {"dedup_status": "cached", "error": None},
        {"dedup_status": "new", "error": "fetch timeout"},
    ])
    snapshot = collect_ris_metrics(
        db_path=db_path,
        eval_artifacts_dir=tmp_path / "no_eval",
        precheck_ledger_path=tmp_path / "no_ledger.jsonl",
        report_dir=tmp_path / "no_reports",
        acquisition_review_dir=review_dir,
    )
    assert snapshot.acquisition_new == 3
    assert snapshot.acquisition_cached == 2
    assert snapshot.acquisition_errors == 1


# ---------------------------------------------------------------------------
# Test 9: derived_claims count
# ---------------------------------------------------------------------------

def test_derived_claims_count(tmp_path):
    db_path = tmp_path / "test.sqlite3"
    _create_ks_db(
        db_path,
        docs=[],
        claims=[{"id": "c1"}, {"id": "c2"}, {"id": "c3"}],
    )
    snapshot = collect_ris_metrics(
        db_path=db_path,
        eval_artifacts_dir=tmp_path / "no_eval",
        precheck_ledger_path=tmp_path / "no_ledger.jsonl",
        report_dir=tmp_path / "no_reports",
        acquisition_review_dir=tmp_path / "no_reviews",
    )
    assert snapshot.total_claims == 3


# ---------------------------------------------------------------------------
# Test 10: returns RisMetricsSnapshot dataclass; all numeric fields are int
# ---------------------------------------------------------------------------

def test_returns_dataclass_with_int_fields(tmp_path):
    db_path = tmp_path / "test.sqlite3"
    _create_ks_db(db_path, docs=[], claims=[])
    snapshot = collect_ris_metrics(
        db_path=db_path,
        eval_artifacts_dir=tmp_path / "no_eval",
        precheck_ledger_path=tmp_path / "no_ledger.jsonl",
        report_dir=tmp_path / "no_reports",
        acquisition_review_dir=tmp_path / "no_reviews",
    )
    assert isinstance(snapshot, RisMetricsSnapshot)
    assert isinstance(snapshot.total_docs, int)
    assert isinstance(snapshot.total_claims, int)
    assert isinstance(snapshot.total_reports, int)
    assert isinstance(snapshot.acquisition_new, int)
    assert isinstance(snapshot.acquisition_cached, int)
    assert isinstance(snapshot.acquisition_errors, int)
    # Ensure none are None
    assert snapshot.total_docs is not None
    assert snapshot.total_claims is not None


# ---------------------------------------------------------------------------
# Test 11: to_dict() is JSON-serializable and has generated_at
# ---------------------------------------------------------------------------

def test_to_dict_is_json_serializable(tmp_path):
    db_path = tmp_path / "test.sqlite3"
    _create_ks_db(db_path, docs=[], claims=[])
    snapshot = collect_ris_metrics(
        db_path=db_path,
        eval_artifacts_dir=tmp_path / "no_eval",
        precheck_ledger_path=tmp_path / "no_ledger.jsonl",
        report_dir=tmp_path / "no_reports",
        acquisition_review_dir=tmp_path / "no_reviews",
    )
    d = snapshot.to_dict()
    # Should not raise
    serialized = json.dumps(d)
    assert "generated_at" in d
    assert isinstance(d["generated_at"], str)
    # Should be parseable back
    reparsed = json.loads(serialized)
    assert reparsed["total_docs"] == 0


# ---------------------------------------------------------------------------
# Test 12: path overrides work for all ledger paths
# ---------------------------------------------------------------------------

def test_path_overrides_are_used(tmp_path):
    """Ensures collect_ris_metrics actually reads from the overridden paths."""
    db_path = tmp_path / "ks.sqlite3"
    _create_ks_db(
        db_path,
        docs=[{"id": "d1", "source_family": "academic"}],
        claims=[{"id": "c1"}],
    )
    eval_dir = tmp_path / "eval"
    _write_eval_artifacts(eval_dir, [{"gate": "ACCEPT", "source_family": "academic"}])

    ledger_path = tmp_path / "pcheck.jsonl"
    _write_precheck_ledger(ledger_path, [
        {"event_type": "precheck_run", "recommendation": "GO"},
    ])

    report_dir = tmp_path / "rpts"
    _write_report_index(report_dir, [{"report_id": "x", "report_type": "custom"}])

    review_dir = tmp_path / "acq"
    _write_acquisition_reviews(review_dir, [{"dedup_status": "new", "error": None}])

    snapshot = collect_ris_metrics(
        db_path=db_path,
        eval_artifacts_dir=eval_dir,
        precheck_ledger_path=ledger_path,
        report_dir=report_dir,
        acquisition_review_dir=review_dir,
    )
    assert snapshot.total_docs == 1
    assert snapshot.total_claims == 1
    assert snapshot.gate_distribution.get("ACCEPT", 0) == 1
    assert snapshot.precheck_decisions["GO"] == 1
    assert snapshot.total_reports == 1
    assert snapshot.acquisition_new == 1


# ---------------------------------------------------------------------------
# Test 13: format_metrics_summary returns multi-line string with sections
# ---------------------------------------------------------------------------

def test_format_metrics_summary_has_section_headers(tmp_path):
    db_path = tmp_path / "test.sqlite3"
    _create_ks_db(db_path, docs=[], claims=[])
    snapshot = collect_ris_metrics(
        db_path=db_path,
        eval_artifacts_dir=tmp_path / "no_eval",
        precheck_ledger_path=tmp_path / "no_ledger.jsonl",
        report_dir=tmp_path / "no_reports",
        acquisition_review_dir=tmp_path / "no_reviews",
    )
    text = format_metrics_summary(snapshot)
    assert isinstance(text, str)
    assert "Knowledge Store" in text
    assert "Eval Gate" in text
    assert "Prechecks" in text
    assert "Reports" in text


# ---------------------------------------------------------------------------
# Test 14: format_metrics_summary handles zero total_docs without crash
# ---------------------------------------------------------------------------

def test_format_metrics_summary_handles_zero_docs(tmp_path):
    db_path = tmp_path / "test.sqlite3"
    _create_ks_db(db_path, docs=[], claims=[])
    snapshot = collect_ris_metrics(
        db_path=db_path,
        eval_artifacts_dir=tmp_path / "no_eval",
        precheck_ledger_path=tmp_path / "no_ledger.jsonl",
        report_dir=tmp_path / "no_reports",
        acquisition_review_dir=tmp_path / "no_reviews",
    )
    text = format_metrics_summary(snapshot)
    # Should have "0" somewhere in KS section
    assert "0" in text


# ---------------------------------------------------------------------------
# Test 15: module import does not raise even when knowledge.sqlite3 missing
# ---------------------------------------------------------------------------

def test_import_does_not_raise():
    """metrics.py must import cleanly with no network or DB access at import time."""
    import importlib
    import packages.research.metrics as m
    importlib.reload(m)
    assert hasattr(m, "collect_ris_metrics")
    assert hasattr(m, "RisMetricsSnapshot")
    assert hasattr(m, "format_metrics_summary")


# ---------------------------------------------------------------------------
# CLI-level tests for research-stats command
# ---------------------------------------------------------------------------

from tools.cli.research_stats import main as stats_main


def _make_path_override_args(tmp_path: Path) -> list[str]:
    """Return common CLI path-override args pointing to tmp_path subdirs."""
    db_path = tmp_path / "ks.sqlite3"
    _create_ks_db(db_path, docs=[], claims=[])
    return [
        "--db", str(db_path),
        "--eval-artifacts-dir", str(tmp_path / "no_eval"),
        "--precheck-ledger", str(tmp_path / "no_ledger.jsonl"),
        "--report-dir", str(tmp_path / "no_reports"),
        "--acquisition-review-dir", str(tmp_path / "no_reviews"),
    ]


class TestResearchStatsCLI:
    """CLI-level tests for the research-stats command (main() entrypoint)."""

    def test_cli_summary_returns_0(self, tmp_path):
        """main(['summary', ...overrides]) returns 0 and prints 'Knowledge Store'."""
        path_args = _make_path_override_args(tmp_path)
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = stats_main(["summary"] + path_args)
        assert rc == 0
        output = buf.getvalue()
        assert "Knowledge Store" in output

    def test_cli_summary_json_returns_valid_json(self, tmp_path):
        """main(['summary', '--json', ...overrides]) returns 0 with valid JSON containing key fields."""
        path_args = _make_path_override_args(tmp_path)
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = stats_main(["summary", "--json"] + path_args)
        assert rc == 0
        parsed = json.loads(buf.getvalue())
        assert "generated_at" in parsed
        assert "total_docs" in parsed

    def test_cli_export_writes_file(self, tmp_path):
        """main(['export', '--out', PATH, ...overrides]) returns 0 and creates a valid JSON file."""
        path_args = _make_path_override_args(tmp_path)
        out_path = tmp_path / "out.json"
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = stats_main(["export", "--out", str(out_path)] + path_args)
        assert rc == 0
        assert out_path.exists()
        content = json.loads(out_path.read_text(encoding="utf-8"))
        assert "generated_at" in content

    def test_cli_missing_subcommand_returns_1(self, tmp_path):
        """main([]) with no subcommand returns exit code 1."""
        rc = stats_main([])
        assert rc == 1

    def test_cli_export_creates_parent_dirs(self, tmp_path):
        """main(['export', '--out', nested/path/out.json, ...overrides]) creates parent dirs."""
        path_args = _make_path_override_args(tmp_path)
        out_path = tmp_path / "sub" / "dir" / "out.json"
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = stats_main(["export", "--out", str(out_path)] + path_args)
        assert rc == 0
        assert out_path.exists()

    def test_cli_summary_with_populated_data(self, tmp_path):
        """With pre-populated KS db and eval artifacts, summary --json returns total_docs > 0."""
        db_path = tmp_path / "ks.sqlite3"
        _create_ks_db(
            db_path,
            docs=[
                {"id": "d1", "source_family": "academic"},
                {"id": "d2", "source_family": "blog"},
            ],
            claims=[{"id": "c1"}],
        )
        eval_dir = tmp_path / "eval"
        _write_eval_artifacts(eval_dir, [
            {"gate": "ACCEPT", "source_family": "academic"},
            {"gate": "REVIEW", "source_family": "blog"},
        ])
        path_args = [
            "--db", str(db_path),
            "--eval-artifacts-dir", str(eval_dir),
            "--precheck-ledger", str(tmp_path / "no_ledger.jsonl"),
            "--report-dir", str(tmp_path / "no_reports"),
            "--acquisition-review-dir", str(tmp_path / "no_reviews"),
        ]
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = stats_main(["summary", "--json"] + path_args)
        assert rc == 0
        parsed = json.loads(buf.getvalue())
        assert parsed["total_docs"] > 0
        assert parsed["gate_distribution"] != {}
