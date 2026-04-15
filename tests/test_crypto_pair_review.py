"""Deterministic offline tests for the crypto-pair post-soak review helper.

Tests cover:
- format_post_soak_review: promote / reject / rerun verdict rendering
- format_post_soak_review: multi-symbol display
- load_or_generate_report: reads existing summary JSON without re-generating
- load_or_generate_report: generates report when summary JSON is absent
- CLI main(): formatted review output
- CLI main(): --json flag prints valid JSON
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

# Reuse fixture helpers from the existing report test module
from tests.test_crypto_pair_report import (
    _write_fixture_run,
    _write_json,
)

from packages.polymarket.crypto_pairs.reporting import (
    PAPER_SOAK_SUMMARY_JSON,
    build_paper_soak_summary,
    format_post_soak_review,
    load_or_generate_report,
    load_paper_run,
)
from tools.cli.crypto_pair_review import main as crypto_pair_review_main


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_report(tmp_path: Path, run_id: str, **kwargs: Any) -> dict[str, Any]:
    """Write a fixture run and return its paper-soak summary report dict."""
    run_dir = _write_fixture_run(tmp_path, run_id=run_id, **kwargs)
    return build_paper_soak_summary(load_paper_run(run_dir))


# ---------------------------------------------------------------------------
# Test 1: promote verdict contains all required sections
# ---------------------------------------------------------------------------


def test_review_promote_contains_all_sections(tmp_path: Path) -> None:
    """format_post_soak_review on a promote-verdict report has all 6 sections."""
    report = _build_report(
        tmp_path,
        "promote-review",
        opportunities=30,
        intents=30,
        paired_exposures=30,
        settled_pairs=30,
    )

    output = format_post_soak_review(report)

    assert "TRACK 2 POST-SOAK REVIEW" in output
    assert "VERDICT:" in output
    assert "PROMOTE TO MICRO LIVE CANDIDATE" in output
    assert "Key Metrics" in output
    assert "Promote-Band Fit" in output
    assert "Risk Controls" in output
    assert "Evidence Floor" in output
    assert "pair_completion_rate" in output
    assert "Net PnL" in output


# ---------------------------------------------------------------------------
# Test 2: reject verdict shows triggered risk control details
# ---------------------------------------------------------------------------


def test_review_reject_shows_triggered_controls(tmp_path: Path) -> None:
    """format_post_soak_review on a reject fixture shows REJECT and risk control code."""
    report = _build_report(
        tmp_path,
        "reject-review",
        stopped_reason="crash",
        opportunities=30,
        intents=30,
        paired_exposures=30,
        settled_pairs=30,
    )

    output = format_post_soak_review(report)

    assert "REJECT" in output
    assert "stopped_reason_not_completed" in output


# ---------------------------------------------------------------------------
# Test 3: rerun verdict shows failed evidence floor checks
# ---------------------------------------------------------------------------


def test_review_rerun_shows_failed_evidence_floor(tmp_path: Path) -> None:
    """format_post_soak_review on low-evidence fixture shows RERUN and NOT MET."""
    report = _build_report(
        tmp_path,
        "rerun-review",
        opportunities=5,
        intents=5,
        paired_exposures=5,
        settled_pairs=5,
    )

    output = format_post_soak_review(report)

    assert "RERUN" in output
    assert "NOT MET" in output
    assert "FAIL:" in output


# ---------------------------------------------------------------------------
# Test 4: multi-symbol display
# ---------------------------------------------------------------------------


def test_review_multi_symbol_display(tmp_path: Path) -> None:
    """format_post_soak_review shows all symbols and per-symbol market counts."""
    symbol_cycle = ["BTC"] * 10 + ["ETH"] * 10 + ["SOL"] * 10
    report = _build_report(
        tmp_path,
        "multi-symbol-review",
        opportunities=30,
        intents=30,
        paired_exposures=30,
        settled_pairs=30,
        symbol_cycle=symbol_cycle,
    )

    output = format_post_soak_review(report)

    # All three symbols present in output
    assert "BTC" in output
    assert "ETH" in output
    assert "SOL" in output
    # Per-symbol market counts
    assert "BTC=10" in output
    assert "ETH=10" in output
    assert "SOL=10" in output


# ---------------------------------------------------------------------------
# Test 5: load_or_generate_report reads existing summary JSON
# ---------------------------------------------------------------------------


def test_load_or_generate_reads_existing_summary(tmp_path: Path) -> None:
    """load_or_generate_report returns the pre-existing JSON without re-generating."""
    run_dir = _write_fixture_run(
        tmp_path,
        run_id="existing-summary",
        opportunities=30,
        intents=30,
        paired_exposures=30,
        settled_pairs=30,
    )

    # Write a pre-existing paper_soak_summary.json with a sentinel field
    sentinel_report = {"schema_version": "test_sentinel", "test_marker": "preexisting"}
    _write_json(run_dir / PAPER_SOAK_SUMMARY_JSON, sentinel_report)

    result = load_or_generate_report(run_dir)

    assert result.get("test_marker") == "preexisting"
    assert result.get("schema_version") == "test_sentinel"


# ---------------------------------------------------------------------------
# Test 6: load_or_generate_report generates when summary JSON is absent
# ---------------------------------------------------------------------------


def test_load_or_generate_generates_when_missing(tmp_path: Path) -> None:
    """load_or_generate_report generates a full report when no summary JSON exists."""
    run_dir = _write_fixture_run(
        tmp_path,
        run_id="no-summary",
        opportunities=30,
        intents=30,
        paired_exposures=30,
        settled_pairs=30,
    )

    # Confirm paper_soak_summary.json does NOT already exist
    assert not (run_dir / PAPER_SOAK_SUMMARY_JSON).exists()

    result = load_or_generate_report(run_dir)

    # Full report should have all top-level sections
    assert "schema_version" in result
    assert "rubric" in result
    assert "metrics" in result


# ---------------------------------------------------------------------------
# Test 7: CLI main() prints formatted review
# ---------------------------------------------------------------------------


def test_cli_review_prints_formatted_output(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """CLI main() with --run prints the formatted one-screen review."""
    run_dir = _write_fixture_run(
        tmp_path,
        run_id="cli-review",
        opportunities=30,
        intents=30,
        paired_exposures=30,
        settled_pairs=30,
    )

    exit_code = crypto_pair_review_main(["--run", str(run_dir)])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "TRACK 2 POST-SOAK REVIEW" in captured.out
    assert "Promote-Band Fit" in captured.out


# ---------------------------------------------------------------------------
# Test 8: CLI main() --json flag prints valid JSON
# ---------------------------------------------------------------------------


def test_cli_review_json_flag_prints_valid_json(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """CLI main() with --run --json prints valid JSON with expected top-level keys."""
    run_dir = _write_fixture_run(
        tmp_path,
        run_id="cli-json",
        opportunities=30,
        intents=30,
        paired_exposures=30,
        settled_pairs=30,
    )

    exit_code = crypto_pair_review_main(["--run", str(run_dir), "--json"])
    captured = capsys.readouterr()

    assert exit_code == 0
    parsed = json.loads(captured.out)
    assert "rubric" in parsed
    assert "metrics" in parsed
