"""Tests for tools/gates/mm_sweep_diagnostic.py (TDD)."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

# ---------------------------------------------------------------------------
# Helpers to build minimal fixtures
# ---------------------------------------------------------------------------


def _make_tape_candidate(
    tmp_path: Path,
    *,
    slug: str = "test-market",
    bucket: str | None = "politics",
    effective_events: int = 60,
    parsed_events: int = 120,
    tracked_asset_count: int = 2,
    recorded_by: str | None = "silver",
    regime: str | None = "politics",
    yes_asset_id: str = "1234",
) -> Any:
    """Build a minimal TapeCandidate-like namespace for testing."""
    from tools.gates.mm_sweep import TapeCandidate

    tape_dir = tmp_path / slug
    tape_dir.mkdir(parents=True, exist_ok=True)
    events_path = tape_dir / "events.jsonl"
    events_path.write_text("{}\n", encoding="utf-8")

    return TapeCandidate(
        tape_dir=tape_dir,
        events_path=events_path,
        market_slug=slug,
        yes_asset_id=yes_asset_id,
        recorded_by=recorded_by,
        regime=regime,
        parsed_events=parsed_events,
        tracked_asset_count=tracked_asset_count,
        effective_events=effective_events,
        bucket=bucket,
    )


def _make_sweep_result(
    *,
    sweep_dir: Path,
    net_profit: str = "0.00",
    scenario_id: str = "spread-x100",
) -> Any:
    """Build a minimal SweepRunResult-like namespace for testing."""
    return SimpleNamespace(
        sweep_dir=sweep_dir,
        summary={
            "scenarios": [
                {
                    "scenario_id": scenario_id,
                    "scenario_name": scenario_id,
                    "net_profit": net_profit,
                }
            ]
        },
    )


# ---------------------------------------------------------------------------
# Test 1: TapeDiagnostic for a too-short tape
# ---------------------------------------------------------------------------


def test_tape_diagnostic_too_short(tmp_path: Path) -> None:
    """A tape with effective_events < min_events should produce SKIPPED_TOO_SHORT."""
    from tools.gates.mm_sweep_diagnostic import (
        TapeDiagnostic,
        _diagnose_tape,
    )

    tape = _make_tape_candidate(
        tmp_path,
        slug="short-market",
        effective_events=10,
        parsed_events=20,
        tracked_asset_count=2,
    )

    diagnostic = _diagnose_tape(tape, min_events=50, sweep_result=None)

    assert isinstance(diagnostic, TapeDiagnostic)
    assert diagnostic.status == "SKIPPED_TOO_SHORT"
    assert diagnostic.fill_opportunity == "none"
    assert diagnostic.quote_count == 0
    assert diagnostic.fill_count == 0
    assert diagnostic.best_net_profit is None
    assert diagnostic.skip_reason is not None
    assert "effective_events" in diagnostic.skip_reason.lower() or "10" in diagnostic.skip_reason


# ---------------------------------------------------------------------------
# Test 2: TapeDiagnostic for a tape that ran with net_profit=0 and no fills
# ---------------------------------------------------------------------------


def test_tape_diagnostic_ran_zero_profit(tmp_path: Path) -> None:
    """A tape that ran with net_profit=0 and no fills has RAN_ZERO_PROFIT, no_touch."""
    from tools.gates.mm_sweep_diagnostic import (
        TapeDiagnostic,
        _diagnose_tape,
    )

    tape = _make_tape_candidate(
        tmp_path,
        slug="zero-profit-market",
        effective_events=60,
    )
    sweep_dir = tmp_path / "sweep_zero"
    sweep_dir.mkdir()
    sweep_result = _make_sweep_result(sweep_dir=sweep_dir, net_profit="0.00")

    diagnostic = _diagnose_tape(tape, min_events=50, sweep_result=sweep_result)

    assert isinstance(diagnostic, TapeDiagnostic)
    assert diagnostic.status == "RAN_ZERO_PROFIT"
    assert diagnostic.best_net_profit == Decimal("0.00")
    assert diagnostic.fill_opportunity == "no_touch"
    assert diagnostic.skip_reason is None


# ---------------------------------------------------------------------------
# Test 3: run_mm_sweep_diagnostic returns one TapeDiagnostic per tape
# ---------------------------------------------------------------------------


def test_run_mm_sweep_diagnostic_returns_one_per_tape(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """run_mm_sweep_diagnostic returns a TapeDiagnostic for each tape in the manifest."""
    import tools.gates.mm_sweep_diagnostic as diag_module

    tape_a = _make_tape_candidate(tmp_path, slug="tape-a", effective_events=60)
    tape_b = _make_tape_candidate(tmp_path, slug="tape-b", effective_events=30)  # too short
    tape_c = _make_tape_candidate(tmp_path, slug="tape-c", effective_events=80)

    def fake_discover(*, benchmark_manifest_path: Path) -> list[Any]:
        return [tape_a, tape_b, tape_c]

    sweep_dir = tmp_path / "sweep_out"
    sweep_dir.mkdir()

    def fake_run_sweep(params: Any, *, sweep_config: Any) -> Any:
        return _make_sweep_result(sweep_dir=sweep_dir, net_profit="1.50")

    monkeypatch.setattr(diag_module, "discover_mm_sweep_tapes", fake_discover)
    monkeypatch.setattr(diag_module, "run_sweep", fake_run_sweep)

    out_dir = tmp_path / "diag_out"
    benchmark_manifest = tmp_path / "manifest.json"
    benchmark_manifest.write_text("{}", encoding="utf-8")

    results = diag_module.run_mm_sweep_diagnostic(
        benchmark_manifest_path=benchmark_manifest,
        out_dir=out_dir,
        min_events=50,
    )

    assert len(results) == 3
    slugs = {d.market_slug for d in results}
    assert "tape-a" in slugs
    assert "tape-b" in slugs
    assert "tape-c" in slugs

    tape_b_diag = next(d for d in results if d.market_slug == "tape-b")
    assert tape_b_diag.status == "SKIPPED_TOO_SHORT"

    tape_a_diag = next(d for d in results if d.market_slug == "tape-a")
    assert tape_a_diag.status in ("RAN_POSITIVE", "RAN_ZERO_PROFIT", "RAN")


# ---------------------------------------------------------------------------
# Test 4: format_diagnostic_report produces a markdown table
# ---------------------------------------------------------------------------


def test_format_diagnostic_report_produces_markdown(tmp_path: Path) -> None:
    """format_diagnostic_report should produce a markdown table with expected columns."""
    from tools.gates.mm_sweep_diagnostic import (
        TapeDiagnostic,
        format_diagnostic_report,
    )

    tape_dir = tmp_path / "tape-x"
    tape_dir.mkdir()

    diag = TapeDiagnostic(
        tape_dir=tape_dir,
        market_slug="tape-x",
        bucket="sports",
        tier="silver",
        effective_events=60,
        parsed_events=120,
        tracked_asset_count=2,
        status="RAN_ZERO_PROFIT",
        skip_reason=None,
        best_net_profit=Decimal("0.00"),
        quote_count=15,
        fill_opportunity="no_touch",
        fill_count=0,
        notes=["test note"],
    )

    report = format_diagnostic_report([diag])

    # Should contain header keywords
    assert "Tape" in report
    assert "Bucket" in report
    assert "Tier" in report
    assert "Status" in report
    assert "FillOpp" in report or "fill" in report.lower()

    # Should contain the data row
    assert "tape-x" in report
    assert "sports" in report
    assert "silver" in report
    assert "RAN_ZERO_PROFIT" in report

    # Should contain summary section
    assert "SKIPPED_TOO_SHORT" in report or "skipped" in report.lower()
    assert "total" in report.lower() or "Total" in report
