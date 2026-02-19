"""Tests for audit-coverage CLI (tools/cli/audit_coverage.py).

All tests run offline: no ClickHouse, no RAG, no network.
"""

import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "packages"))

from tools.cli import audit_coverage


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _make_run_dir(
    base: Path,
    run_id: str,
    *,
    wallet: str = "0xabc123",
    date: str = "2026-02-18",
    command_name: str = "scan",
    started_at: str = "2026-02-18T10:00:00Z",
    positions: list | None = None,
    with_coverage: bool = True,
    with_segment: bool = False,
) -> Path:
    """Create a minimal scan run directory under *base*."""
    run_dir = base / wallet / date / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    manifest = {
        "run_id": run_id,
        "command_name": command_name,
        "started_at": started_at,
        "user_slug": base.name,
        "wallets": [wallet],
        "output_paths": {"run_root": run_dir.as_posix()},
    }
    _write_json(run_dir / "run_manifest.json", manifest)

    if positions is None:
        positions = _default_positions()

    dossier = {"positions": positions}
    _write_json(run_dir / "dossier.json", dossier)

    if with_coverage:
        coverage = _default_coverage_report(run_id, base.name, wallet, positions)
        _write_json(run_dir / "coverage_reconciliation_report.json", coverage)

    if with_segment:
        segment = _default_segment_analysis(run_id, base.name, wallet)
        _write_json(run_dir / "segment_analysis.json", segment)

    return run_dir


def _default_positions(n: int = 5) -> list:
    positions = []
    for i in range(n):
        outcome = "WIN" if i % 2 == 0 else "PENDING"
        positions.append(
            {
                "token_id": f"tok_{i:04d}",
                "condition_id": f"cond_{i:04d}",
                "market_slug": f"market-slug-{i}",
                "question": f"Will event {i} happen?",
                "outcome_name": "Yes" if i % 2 == 0 else "No",
                "category": "Sports" if i < 3 else "",
                "league": "nba" if i < 2 else "unknown",
                "sport": "basketball" if i < 2 else "unknown",
                "market_type": "moneyline" if i < 4 else "unknown",
                "entry_price_tier": "coinflip",
                "entry_price": 0.50 + i * 0.01,
                "size": 10.0 * (i + 1),
                "resolution_outcome": outcome,
                "gross_pnl": 5.0 if outcome == "WIN" else None,
                "fees_estimated": 0.10 if outcome == "WIN" else None,
                "net_estimated_fees": 4.90 if outcome == "WIN" else None,
            }
        )
    return positions


def _default_coverage_report(
    run_id: str, slug: str, wallet: str, positions: list
) -> dict:
    total = len(positions)
    resolved = sum(
        1
        for p in positions
        if str(p.get("resolution_outcome") or "").upper()
        in ("WIN", "LOSS", "PROFIT_EXIT", "LOSS_EXIT")
    )
    pending = sum(
        1
        for p in positions
        if str(p.get("resolution_outcome") or "").upper() == "PENDING"
    )
    return {
        "report_version": "1.4.0",
        "run_id": run_id,
        "user_slug": slug,
        "wallet": wallet,
        "totals": {"positions_total": total},
        "outcome_counts": {
            "WIN": resolved,
            "LOSS": 0,
            "PROFIT_EXIT": 0,
            "LOSS_EXIT": 0,
            "PENDING": pending,
            "UNKNOWN_RESOLUTION": total - resolved - pending,
        },
        "category_coverage": {
            "present_count": 3,
            "missing_count": total - 3,
            "coverage_rate": 3 / total,
        },
        "market_metadata_coverage": {
            "present_count": total,
            "missing_count": 0,
            "coverage_rate": 1.0,
            "metadata_conflicts_count": 0,
        },
        "fees": {
            "fees_estimated_present_count": resolved,
            "fees_source_counts": {"estimated": resolved},
        },
        "warnings": [],
    }


def _default_segment_analysis(run_id: str, slug: str, wallet: str) -> dict:
    return {
        "run_id": run_id,
        "user_slug": slug,
        "wallet": wallet,
        "segment_analysis": {
            "by_league": {
                "nba": {"total_count": 2},
                "unknown": {"total_count": 3},
            },
            "by_sport": {
                "basketball": {"total_count": 2},
                "unknown": {"total_count": 3},
            },
            "by_market_type": {
                "moneyline": {"total_count": 4},
                "unknown": {"total_count": 1},
            },
        },
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_finds_latest_scan_run_among_multiple(tmp_path, monkeypatch):
    """Command selects the latest scan run when multiple runs exist."""
    monkeypatch.chdir(tmp_path)
    slug = "audituser"
    base = tmp_path / "artifacts" / "dossiers" / "users" / slug

    _make_run_dir(
        base,
        "old_run",
        date="2026-02-01",
        started_at="2026-02-01T10:00:00Z",
    )
    latest_dir = _make_run_dir(
        base,
        "new_run",
        date="2026-02-18",
        started_at="2026-02-18T12:00:00Z",
    )

    rc = audit_coverage.main(["--user", "@audituser", "--sample", "3"])
    assert rc == 0

    report_path = latest_dir / "audit_coverage_report.md"
    assert report_path.exists(), f"Expected report at {report_path}"


def test_report_written_at_expected_path(tmp_path, monkeypatch):
    """Report is written to run_root/audit_coverage_report.md by default."""
    monkeypatch.chdir(tmp_path)
    slug = "audituser"
    base = tmp_path / "artifacts" / "dossiers" / "users" / slug

    run_dir = _make_run_dir(base, "run_abc")

    rc = audit_coverage.main(["--user", "@audituser", "--sample", "5"])
    assert rc == 0

    report_path = run_dir / "audit_coverage_report.md"
    assert report_path.exists()

    text = report_path.read_text(encoding="utf-8")
    assert len(text) > 0


def test_report_contains_required_headings(tmp_path, monkeypatch):
    """Markdown report must contain the three required headings."""
    monkeypatch.chdir(tmp_path)
    slug = "audituser"
    base = tmp_path / "artifacts" / "dossiers" / "users" / slug
    _make_run_dir(base, "run_headings")

    rc = audit_coverage.main(["--user", "@audituser", "--sample", "5"])
    assert rc == 0

    run_dir = base / "0xabc123" / "2026-02-18" / "run_headings"
    text = (run_dir / "audit_coverage_report.md").read_text(encoding="utf-8")

    assert "## Quick Stats" in text
    assert "## Red Flags" in text
    assert "## Samples" in text


def test_samples_count_equals_n(tmp_path, monkeypatch):
    """Exactly N samples are rendered (or min(N, available))."""
    monkeypatch.chdir(tmp_path)
    slug = "audituser"
    base = tmp_path / "artifacts" / "dossiers" / "users" / slug
    # 10 positions available, request 7
    positions = _default_positions(n=10)
    _make_run_dir(base, "run_samples", positions=positions)

    rc = audit_coverage.main(["--user", "@audituser", "--sample", "7"])
    assert rc == 0

    run_dir = base / "0xabc123" / "2026-02-18" / "run_samples"
    text = (run_dir / "audit_coverage_report.md").read_text(encoding="utf-8")

    assert "## Samples (7)" in text


def test_samples_capped_at_available(tmp_path, monkeypatch):
    """When N > available positions, all positions are returned."""
    monkeypatch.chdir(tmp_path)
    slug = "audituser"
    base = tmp_path / "artifacts" / "dossiers" / "users" / slug
    positions = _default_positions(n=3)
    _make_run_dir(base, "run_cap", positions=positions)

    rc = audit_coverage.main(["--user", "@audituser", "--sample", "25"])
    assert rc == 0

    run_dir = base / "0xabc123" / "2026-02-18" / "run_cap"
    text = (run_dir / "audit_coverage_report.md").read_text(encoding="utf-8")

    # Only 3 available, so header should say "Samples (3)"
    assert "## Samples (3)" in text


def test_deterministic_sampling_same_seed(tmp_path):
    """Same seed yields same first-sample key on repeated calls."""
    positions = _default_positions(n=20)
    first_call = audit_coverage.sample_positions(positions, 5, seed=1337)
    second_call = audit_coverage.sample_positions(positions, 5, seed=1337)
    assert first_call == second_call

    first_key = audit_coverage._stable_sort_key(first_call[0])
    second_key = audit_coverage._stable_sort_key(second_call[0])
    assert first_key == second_key


def test_deterministic_sampling_different_seed(tmp_path):
    """Different seeds should generally yield different samples (for reasonable N)."""
    positions = _default_positions(n=20)
    s1 = audit_coverage.sample_positions(positions, 10, seed=1337)
    s2 = audit_coverage.sample_positions(positions, 10, seed=42)
    # With 20 positions sampling 10, two seeds should not be identical
    keys1 = [audit_coverage._stable_sort_key(p) for p in s1]
    keys2 = [audit_coverage._stable_sort_key(p) for p in s2]
    assert keys1 != keys2


def test_resolved_positions_sampled_first(tmp_path):
    """Resolved positions appear before unresolved in the sample pool."""
    # 4 PENDING, 2 WIN — all 6 fit within n=6
    positions = [
        {"token_id": f"tok_{i}", "resolution_outcome": "PENDING"} for i in range(4)
    ] + [
        {"token_id": f"tok_res_{i}", "resolution_outcome": "WIN"} for i in range(2)
    ]
    sampled = audit_coverage.sample_positions(positions, 6, seed=1337)
    # The two WIN positions should be in the first 2 slots (resolved-first pool)
    resolution_outcomes = [s.get("resolution_outcome") for s in sampled]
    assert resolution_outcomes.count("WIN") == 2
    # First items in sample are from the resolved pool
    assert sampled[0].get("resolution_outcome") == "WIN"
    assert sampled[1].get("resolution_outcome") == "WIN"


def test_no_crash_on_missing_fields(tmp_path, monkeypatch):
    """Report must not crash when position fields are absent."""
    monkeypatch.chdir(tmp_path)
    slug = "audituser"
    base = tmp_path / "artifacts" / "dossiers" / "users" / slug

    minimal_positions = [
        {"token_id": "tok_0"},  # Almost no fields
        {"condition_id": "cond_1", "resolution_outcome": "PENDING"},
    ]
    _make_run_dir(base, "run_minimal", positions=minimal_positions)

    rc = audit_coverage.main(["--user", "@audituser", "--sample", "5"])
    assert rc == 0

    run_dir = base / "0xabc123" / "2026-02-18" / "run_minimal"
    text = (run_dir / "audit_coverage_report.md").read_text(encoding="utf-8")
    assert "## Samples" in text
    # Should show "Unknown" for absent fields
    assert "Unknown" in text


def test_no_scan_run_returns_error(tmp_path, monkeypatch):
    """Returns exit code 1 and error message when no scan runs exist."""
    monkeypatch.chdir(tmp_path)
    # Don't create any artifacts

    rc = audit_coverage.main(["--user", "@nobodyhere", "--sample", "5"])
    assert rc == 1


def test_specific_run_id(tmp_path, monkeypatch):
    """--run-id selects the specified run regardless of recency."""
    monkeypatch.chdir(tmp_path)
    slug = "audituser"
    base = tmp_path / "artifacts" / "dossiers" / "users" / slug

    _make_run_dir(base, "newer_run", date="2026-02-18", started_at="2026-02-18T12:00:00Z")
    older_dir = _make_run_dir(
        base, "older_run", date="2026-02-01", started_at="2026-02-01T10:00:00Z"
    )

    rc = audit_coverage.main(
        ["--user", "@audituser", "--sample", "3", "--run-id", "older_run"]
    )
    assert rc == 0

    # Report should appear in the older run directory
    report_path = older_dir / "audit_coverage_report.md"
    assert report_path.exists()


def test_custom_output_path(tmp_path, monkeypatch):
    """--output writes report to the specified path."""
    monkeypatch.chdir(tmp_path)
    slug = "audituser"
    base = tmp_path / "artifacts" / "dossiers" / "users" / slug
    _make_run_dir(base, "run_out")

    custom_out = tmp_path / "my_report" / "report.md"
    rc = audit_coverage.main(
        ["--user", "@audituser", "--sample", "3", "--output", str(custom_out)]
    )
    assert rc == 0
    assert custom_out.exists()


def test_json_format(tmp_path, monkeypatch):
    """--format json writes a valid JSON file with expected keys."""
    monkeypatch.chdir(tmp_path)
    slug = "audituser"
    base = tmp_path / "artifacts" / "dossiers" / "users" / slug
    run_dir = _make_run_dir(base, "run_json")

    rc = audit_coverage.main(["--user", "@audituser", "--sample", "3", "--format", "json"])
    assert rc == 0

    report_path = run_dir / "audit_coverage_report.json"
    assert report_path.exists()

    data = json.loads(report_path.read_text(encoding="utf-8"))
    assert data["report_type"] == "audit_coverage"
    assert "quick_stats" in data
    assert "red_flags" in data
    assert "samples" in data
    assert data["samples"]["n_requested"] == 3


def test_red_flag_category_missing_rate(tmp_path, monkeypatch):
    """Red flag fires when category missing rate exceeds 20%."""
    monkeypatch.chdir(tmp_path)
    slug = "audituser"
    base = tmp_path / "artifacts" / "dossiers" / "users" / slug
    positions = _default_positions(n=10)

    # Override coverage to set high category missing rate
    run_dir = _make_run_dir(base, "run_flags", positions=positions, with_coverage=False)
    bad_coverage = {
        "report_version": "1.4.0",
        "run_id": "run_flags",
        "user_slug": slug,
        "wallet": "0xabc123",
        "totals": {"positions_total": 10},
        "outcome_counts": {
            "WIN": 5,
            "LOSS": 0,
            "PROFIT_EXIT": 0,
            "LOSS_EXIT": 0,
            "PENDING": 5,
            "UNKNOWN_RESOLUTION": 0,
        },
        "category_coverage": {
            "present_count": 1,
            "missing_count": 9,
            "coverage_rate": 0.10,  # 90% missing — exceeds 20% threshold
        },
        "market_metadata_coverage": {
            "present_count": 10,
            "missing_count": 0,
            "coverage_rate": 1.0,
            "metadata_conflicts_count": 0,
        },
        "fees": {
            "fees_estimated_present_count": 5,
            "fees_source_counts": {"estimated": 5},
        },
        "warnings": [],
    }
    _write_json(run_dir / "coverage_reconciliation_report.json", bad_coverage)

    rc = audit_coverage.main(["--user", "@audituser", "--sample", "5"])
    assert rc == 0

    text = (run_dir / "audit_coverage_report.md").read_text(encoding="utf-8")
    assert "category_missing_rate" in text
    assert "20%" in text


def test_segment_analysis_unknown_rates_displayed(tmp_path, monkeypatch):
    """Unknown league/sport/market_type rates appear in Quick Stats when segment data present."""
    monkeypatch.chdir(tmp_path)
    slug = "audituser"
    base = tmp_path / "artifacts" / "dossiers" / "users" / slug
    _make_run_dir(base, "run_seg", with_segment=True)

    rc = audit_coverage.main(["--user", "@audituser", "--sample", "3"])
    assert rc == 0

    run_dir = base / "0xabc123" / "2026-02-18" / "run_seg"
    text = (run_dir / "audit_coverage_report.md").read_text(encoding="utf-8")
    assert "unknown_league_rate" in text
    assert "unknown_sport_rate" in text
    assert "unknown_market_type_rate" in text


# ---------------------------------------------------------------------------
# Roadmap 4.6: Category taxonomy + derived-field consistency tests
# ---------------------------------------------------------------------------


def test_audit_report_non_unknown_category(tmp_path, monkeypatch):
    """Audit report sample shows a non-Unknown category for positions that carry one."""
    monkeypatch.chdir(tmp_path)
    slug = "audituser"
    base = tmp_path / "artifacts" / "dossiers" / "users" / slug

    positions = [
        {
            "token_id": "tok_sports_0",
            "market_slug": "sports-market-0",
            "question": "Will team A win?",
            "outcome_name": "Yes",
            "category": "Sports",
            "resolution_outcome": "WIN",
            "gross_pnl": 10.0,
            "entry_price": 0.5,
        },
        {
            "token_id": "tok_unknown_1",
            "market_slug": "other-market-1",
            "question": "Will event B happen?",
            "outcome_name": "No",
            "category": "",
            "resolution_outcome": "PENDING",
            "gross_pnl": 0.0,
            "entry_price": 0.3,
        },
    ]
    run_dir = _make_run_dir(base, "run_cat", positions=positions)

    rc = audit_coverage.main(["--user", "@audituser", "--sample", "5"])
    assert rc == 0

    text = (run_dir / "audit_coverage_report.md").read_text(encoding="utf-8")
    # At least one sample should show "Sports" (not just "Unknown")
    assert "Sports" in text


def test_audit_sample_derived_league_sport_tier_for_nba_slug(tmp_path, monkeypatch):
    """Audit sample derives league/sport/entry_price_tier for nba-prefixed slugs."""
    monkeypatch.chdir(tmp_path)
    slug = "audituser"
    base = tmp_path / "artifacts" / "dossiers" / "users" / slug

    # Position has an nba- slug but NO pre-filled league/sport fields.
    positions = [
        {
            "token_id": "tok_nba_0",
            "market_slug": "nba-lakers-celtics-game1",
            "question": "Will the Lakers win?",
            "outcome_name": "Yes",
            "category": "Sports",
            "resolution_outcome": "WIN",
            "gross_pnl": 5.0,
            "entry_price": 0.52,
        },
    ]
    run_dir = _make_run_dir(base, "run_nba", positions=positions)

    rc = audit_coverage.main(["--user", "@audituser", "--sample", "5"])
    assert rc == 0

    text = (run_dir / "audit_coverage_report.md").read_text(encoding="utf-8")
    # Derived league and sport must appear in the sample block
    assert "nba" in text
    assert "basketball" in text
    # Derived entry_price_tier: 0.52 falls in "coinflip" (0.45-0.55)
    assert "coinflip" in text


def test_audit_sample_fees_positive_for_positive_gross_pnl(tmp_path, monkeypatch):
    """Audit sample shows fees_estimated > 0 and net_estimated_fees when gross_pnl > 0."""
    monkeypatch.chdir(tmp_path)
    slug = "audituser"
    base = tmp_path / "artifacts" / "dossiers" / "users" / slug

    # Simulate raw dossier position as it comes from ClickHouse: fees_estimated=0.0
    # The audit enrichment should compute fees_estimated = gross_pnl * 0.02
    positions = [
        {
            "token_id": "tok_win_0",
            "market_slug": "sports-market-0",
            "question": "Will team win?",
            "outcome_name": "Yes",
            "category": "Sports",
            "resolution_outcome": "WIN",
            "gross_pnl": 10.0,
            "fees_estimated": 0.0,  # raw from ClickHouse view before normalization
            "entry_price": 0.5,
        },
    ]
    run_dir = _make_run_dir(base, "run_fees", positions=positions)

    rc = audit_coverage.main(["--user", "@audituser", "--sample", "5"])
    assert rc == 0

    text = (run_dir / "audit_coverage_report.md").read_text(encoding="utf-8")
    # fees_estimated should be 10.0 * 0.02 = 0.2 (not 0.0)
    assert "fees_estimated" in text
    assert "0.2" in text or "fees_estimated**: 0.2" in text
    # realized_pnl_net_estimated_fees should appear (10.0 - 0.2 = 9.8)
    assert "realized_pnl_net_estimated_fees" in text or "net_estimated_fees" in text


def test_fee_sanity_red_flag_when_positive_pnl_has_zero_estimated_fee(tmp_path, monkeypatch):
    """Red flag fires when raw positions contain gross_pnl>0 with fees_estimated=0."""
    monkeypatch.chdir(tmp_path)
    slug = "audituser"
    base = tmp_path / "artifacts" / "dossiers" / "users" / slug

    positions = [
        {
            "token_id": "tok_win_zero_fee",
            "market_slug": "sports-market-zero-fee",
            "question": "Will team win?",
            "outcome_name": "Yes",
            "category": "Sports",
            "resolution_outcome": "WIN",
            "gross_pnl": 12.0,
            "fees_estimated": 0.0,
            "entry_price": 0.5,
        }
    ]
    run_dir = _make_run_dir(base, "run_fee_sanity", positions=positions)

    rc = audit_coverage.main(["--user", "@audituser", "--sample", "1"])
    assert rc == 0

    text = (run_dir / "audit_coverage_report.md").read_text(encoding="utf-8")
    assert "positive_pnl_with_zero_fee_count: 1" in text
    assert "positive_pnl_with_zero_fee_count=1" in text
    assert "gross_pnl>0 with fees_estimated=0" in text
    assert "fees_estimated is only applied when gross_pnl > 0" in text


def test_deterministic_sampling_same_seed_yields_same_first_sample_key(tmp_path):
    """Same seed always yields same first sample key (stable sort key check)."""
    positions = _default_positions(n=15)
    first = audit_coverage.sample_positions(positions, 5, seed=1337)
    second = audit_coverage.sample_positions(positions, 5, seed=1337)
    assert first == second
    assert audit_coverage._stable_sort_key(first[0]) == audit_coverage._stable_sort_key(second[0])


# ---------------------------------------------------------------------------
# Roadmap 4.6+: default-all behavior tests
# ---------------------------------------------------------------------------


def test_default_includes_all_positions(tmp_path, monkeypatch):
    """No --sample flag → report includes ALL positions with 'All Positions' heading."""
    monkeypatch.chdir(tmp_path)
    slug = "audituser"
    base = tmp_path / "artifacts" / "dossiers" / "users" / slug

    positions = _default_positions(n=8)
    run_dir = _make_run_dir(base, "run_all_default", positions=positions)

    # No --sample flag at all
    rc = audit_coverage.main(["--user", "@audituser"])
    assert rc == 0

    text = (run_dir / "audit_coverage_report.md").read_text(encoding="utf-8")

    # Heading must say "All Positions" not "Samples"
    assert "## All Positions (8)" in text
    assert "## Samples" not in text

    # All 8 position blocks must be present
    position_blocks = [line for line in text.splitlines() if line.startswith("### Position ")]
    assert len(position_blocks) == 8


def test_explicit_sample_uses_samples_heading(tmp_path, monkeypatch):
    """Explicit --sample N → report uses 'Samples' heading with exactly N blocks."""
    monkeypatch.chdir(tmp_path)
    slug = "audituser"
    base = tmp_path / "artifacts" / "dossiers" / "users" / slug

    positions = _default_positions(n=8)
    run_dir = _make_run_dir(base, "run_explicit_sample", positions=positions)

    rc = audit_coverage.main(["--user", "@audituser", "--sample", "3"])
    assert rc == 0

    text = (run_dir / "audit_coverage_report.md").read_text(encoding="utf-8")

    # Heading must say "Samples" not "All Positions"
    assert "## Samples (3)" in text
    assert "## All Positions" not in text

    # Exactly 3 position blocks
    position_blocks = [line for line in text.splitlines() if line.startswith("### Position ")]
    assert len(position_blocks) == 3
