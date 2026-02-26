"""Offline tests for simtrader browse command."""

from __future__ import annotations

import json
import re
from pathlib import Path
from types import SimpleNamespace


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def test_browse_lists_recent_artifacts_across_types(
    tmp_path: Path,
    capsys,
    monkeypatch,
) -> None:
    from tools.cli.simtrader import main as simtrader_main

    artifacts_root = tmp_path / "sim"
    monkeypatch.setattr("tools.cli.simtrader.DEFAULT_ARTIFACTS_DIR", artifacts_root)

    sweep_dir = artifacts_root / "sweeps" / "quickrun_20260224T220832Z_aaaa1111"
    _write_json(
        sweep_dir / "sweep_manifest.json",
        {
            "sweep_id": "sweep-artifact",
            "quickrun_context": {"selected_slug": "sweep-slug"},
            "scenarios": [],
        },
    )
    _write_json(
        sweep_dir / "sweep_summary.json",
        {"sweep_id": "sweep-artifact", "aggregate": {}, "scenarios": []},
    )

    run_dir = artifacts_root / "runs" / "quickrun_20260224T223000Z_bbbb2222"
    _write_json(
        run_dir / "run_manifest.json",
        {
            "run_id": "run-artifact",
            "created_at": "2026-02-24T22:30:00+00:00",
            "quickrun_context": {"selected_slug": "run-slug"},
        },
    )
    _write_json(run_dir / "summary.json", {"net_profit": "1.0"})

    batch_dir = artifacts_root / "batches" / "batch_20260224T225237Z_cccc3333"
    _write_json(
        batch_dir / "batch_manifest.json",
        {
            "batch_id": "batch-artifact",
            "created_at": "20260224T225237Z",
            "markets": [{"slug": "batch-market-a"}, {"slug": "batch-market-b"}],
        },
    )
    _write_json(
        batch_dir / "batch_summary.json",
        {"batch_id": "batch-artifact", "aggregate": {}, "markets": []},
    )

    shadow_dir = artifacts_root / "shadow_runs" / "20260224T230000Z_shadow_dddd4444"
    _write_json(
        shadow_dir / "run_manifest.json",
        {
            "run_id": "shadow-artifact",
            "mode": "shadow",
            "started_at": "2026-02-24T23:00:00+00:00",
            "shadow_context": {"selected_slug": "shadow-slug"},
        },
    )
    _write_json(shadow_dir / "summary.json", {"net_profit": "0.0"})

    exit_code = simtrader_main(["browse", "--limit", "3"])
    assert exit_code == 0

    out = capsys.readouterr().out
    lines = [
        line.strip()
        for line in out.splitlines()
        if re.match(r"^\d+\.\s", line.strip())
    ]
    assert len(lines) == 3
    assert "type=shadow" in lines[0]
    assert "type=batch" in lines[1]
    assert "type=run" in lines[2]
    assert "market=shadow-slug" in lines[0]
    assert "market=multiple(2)" in lines[1]
    assert "market=run-slug" in lines[2]
    assert "sweep-artifact" not in out


def test_browse_type_filter_report_all_generates_reports(
    tmp_path: Path,
    capsys,
    monkeypatch,
) -> None:
    from tools.cli.simtrader import main as simtrader_main

    artifacts_root = tmp_path / "sim"
    monkeypatch.setattr("tools.cli.simtrader.DEFAULT_ARTIFACTS_DIR", artifacts_root)

    run_a = artifacts_root / "runs" / "quickrun_20260224T200000Z_runa"
    run_b = artifacts_root / "runs" / "quickrun_20260224T210000Z_runb"
    for run_dir, run_id, slug in (
        (run_a, "run-a", "market-a"),
        (run_b, "run-b", "market-b"),
    ):
        _write_json(
            run_dir / "run_manifest.json",
            {
                "run_id": run_id,
                "created_at": "2026-02-24T20:00:00+00:00",
                "quickrun_context": {"selected_slug": slug},
                "decisions_count": 0,
                "fills_count": 0,
            },
        )
        _write_json(run_dir / "summary.json", {"net_profit": "0"})

    sweep_dir = artifacts_root / "sweeps" / "quickrun_20260224T220832Z_sweep"
    _write_json(
        sweep_dir / "sweep_manifest.json",
        {"sweep_id": "sweep-ignore", "scenarios": []},
    )
    _write_json(
        sweep_dir / "sweep_summary.json",
        {"sweep_id": "sweep-ignore", "aggregate": {}, "scenarios": []},
    )

    exit_code = simtrader_main(["browse", "--type", "run", "--report-all"])
    assert exit_code == 0

    out = capsys.readouterr().out
    assert "type=sweep" not in out
    assert out.count("Report written:") == 2
    assert (run_a / "report.html").exists()
    assert (run_b / "report.html").exists()
    assert not (sweep_dir / "report.html").exists()


def test_browse_open_generates_report_for_newest_only(
    tmp_path: Path,
    capsys,
    monkeypatch,
) -> None:
    from tools.cli.simtrader import main as simtrader_main

    artifacts_root = tmp_path / "sim"
    monkeypatch.setattr("tools.cli.simtrader.DEFAULT_ARTIFACTS_DIR", artifacts_root)

    run_dir = artifacts_root / "runs" / "quickrun_20260224T220000Z_oldrun"
    _write_json(
        run_dir / "run_manifest.json",
        {
            "run_id": "older-run",
            "created_at": "2026-02-24T22:00:00+00:00",
            "quickrun_context": {"selected_slug": "old-market"},
        },
    )
    _write_json(run_dir / "summary.json", {"net_profit": "0"})

    sweep_dir = artifacts_root / "sweeps" / "quickrun_20260224T230000Z_newsweep"
    _write_json(
        sweep_dir / "sweep_manifest.json",
        {
            "sweep_id": "newest-sweep",
            "quickrun_context": {"selected_slug": "new-market"},
            "scenarios": [],
        },
    )
    _write_json(
        sweep_dir / "sweep_summary.json",
        {"sweep_id": "newest-sweep", "aggregate": {}, "scenarios": []},
    )

    exit_code = simtrader_main(["browse", "--open"])
    assert exit_code == 0

    out = capsys.readouterr().out
    assert f'ii "{sweep_dir / "report.html"}"' in out
    assert str(sweep_dir / "report.html") in out
    assert (sweep_dir / "report.html").exists()
    assert not (run_dir / "report.html").exists()


def test_browse_run_with_tape_linkage_shows_slug(
    tmp_path: Path,
    capsys,
    monkeypatch,
) -> None:
    """Run artifact with no manifest context but tape_dir pointing to meta.json shows slug."""
    from tools.cli.simtrader import main as simtrader_main

    artifacts_root = tmp_path / "sim"
    monkeypatch.setattr("tools.cli.simtrader.DEFAULT_ARTIFACTS_DIR", artifacts_root)

    # Tape directory with meta.json that has shadow_context
    tape_dir = tmp_path / "tapes" / "tape_20260225T120000Z"
    tape_dir.mkdir(parents=True)
    _write_json(
        tape_dir / "meta.json",
        {
            "shadow_context": {
                "selected_slug": "tape-linked-market",
                "selected_at": "2026-02-25T12:00:00+00:00",
            }
        },
    )

    # Run artifact references tape_dir but has no quickrun_context/shadow_context
    run_dir = artifacts_root / "runs" / "20260225T130000Z_plain_run"
    _write_json(
        run_dir / "run_manifest.json",
        {
            "run_id": "plain-run-1",
            "created_at": "2026-02-25T13:00:00+00:00",
            "tape_path": str(tape_dir / "events.jsonl"),
            "tape_dir": str(tape_dir),
        },
    )
    _write_json(run_dir / "summary.json", {"net_profit": "0.0"})

    exit_code = simtrader_main(["browse", "--limit", "5"])
    assert exit_code == 0

    out = capsys.readouterr().out
    lines = [line.strip() for line in out.splitlines() if line.strip().startswith("1.")]
    assert len(lines) == 1
    assert "market=tape-linked-market" in lines[0]


def test_browse_run_tape_linkage_via_tape_path_fallback(
    tmp_path: Path,
    capsys,
    monkeypatch,
) -> None:
    """Run artifact with tape_path (no tape_dir field) resolves slug from parent meta.json."""
    from tools.cli.simtrader import main as simtrader_main

    artifacts_root = tmp_path / "sim"
    monkeypatch.setattr("tools.cli.simtrader.DEFAULT_ARTIFACTS_DIR", artifacts_root)

    tape_dir = tmp_path / "tapes" / "tape_20260225T140000Z"
    tape_dir.mkdir(parents=True)
    _write_json(
        tape_dir / "meta.json",
        {
            "quickrun_context": {
                "selected_slug": "quickrun-tape-market",
            }
        },
    )

    run_dir = artifacts_root / "runs" / "20260225T150000Z_tape_path_only"
    _write_json(
        run_dir / "run_manifest.json",
        {
            "run_id": "tape-path-only-run",
            "created_at": "2026-02-25T15:00:00+00:00",
            "tape_path": str(tape_dir / "events.jsonl"),
            # tape_dir intentionally absent to test fallback
        },
    )
    _write_json(run_dir / "summary.json", {"net_profit": "0.0"})

    exit_code = simtrader_main(["browse", "--limit", "5"])
    assert exit_code == 0

    out = capsys.readouterr().out
    lines = [line.strip() for line in out.splitlines() if line.strip().startswith("1.")]
    assert len(lines) == 1
    assert "market=quickrun-tape-market" in lines[0]


def test_browse_run_tape_linkage_shadow_context_via_tape_path(
    tmp_path: Path,
    capsys,
    monkeypatch,
) -> None:
    """Run artifact with tape_path resolves slug from tape meta shadow_context."""
    from tools.cli.simtrader import main as simtrader_main

    artifacts_root = tmp_path / "sim"
    monkeypatch.setattr("tools.cli.simtrader.DEFAULT_ARTIFACTS_DIR", artifacts_root)

    tape_dir = tmp_path / "tapes" / "tape_20260225T160000Z"
    tape_dir.mkdir(parents=True)
    _write_json(
        tape_dir / "meta.json",
        {
            "shadow_context": {
                "selected_slug": "shadow-tape-market",
            }
        },
    )

    run_dir = artifacts_root / "runs" / "20260225T170000Z_shadow_tape_path_only"
    _write_json(
        run_dir / "run_manifest.json",
        {
            "run_id": "shadow-tape-path-only-run",
            "created_at": "2026-02-25T17:00:00+00:00",
            "tape_path": str(tape_dir / "events.jsonl"),
        },
    )
    _write_json(run_dir / "summary.json", {"net_profit": "0.0"})

    exit_code = simtrader_main(["browse", "--limit", "5"])
    assert exit_code == 0

    out = capsys.readouterr().out
    lines = [line.strip() for line in out.splitlines() if line.strip().startswith("1.")]
    assert len(lines) == 1
    assert "market=shadow-tape-market" in lines[0]


def test_browse_run_manifest_market_slug_preferred_over_tape_meta(
    tmp_path: Path,
    capsys,
    monkeypatch,
) -> None:
    """When run_manifest.market_slug exists, browse should use it first."""
    from tools.cli.simtrader import main as simtrader_main

    artifacts_root = tmp_path / "sim"
    monkeypatch.setattr("tools.cli.simtrader.DEFAULT_ARTIFACTS_DIR", artifacts_root)

    tape_dir = tmp_path / "tapes" / "tape_20260225T180000Z"
    tape_dir.mkdir(parents=True)
    _write_json(
        tape_dir / "meta.json",
        {
            "shadow_context": {
                "selected_slug": "meta-shadow-market",
            }
        },
    )

    run_dir = artifacts_root / "runs" / "20260225T181500Z_market_slug_preferred"
    _write_json(
        run_dir / "run_manifest.json",
        {
            "run_id": "market-slug-preferred-run",
            "created_at": "2026-02-25T18:15:00+00:00",
            "market_slug": "manifest-market-slug",
            "tape_path": str(tape_dir / "events.jsonl"),
        },
    )
    _write_json(run_dir / "summary.json", {"net_profit": "0.0"})

    exit_code = simtrader_main(["browse", "--limit", "5"])
    assert exit_code == 0

    out = capsys.readouterr().out
    lines = [line.strip() for line in out.splitlines() if line.strip().startswith("1.")]
    assert len(lines) == 1
    assert "market=manifest-market-slug" in lines[0]


def test_browse_open_skips_existing_report_unless_force(
    tmp_path: Path,
    capsys,
    monkeypatch,
) -> None:
    from tools.cli.simtrader import main as simtrader_main

    artifacts_root = tmp_path / "sim"
    monkeypatch.setattr("tools.cli.simtrader.DEFAULT_ARTIFACTS_DIR", artifacts_root)

    run_dir = artifacts_root / "runs" / "quickrun_20260224T230000Z_newrun"
    _write_json(
        run_dir / "run_manifest.json",
        {
            "run_id": "new-run",
            "created_at": "2026-02-24T23:00:00+00:00",
            "quickrun_context": {"selected_slug": "new-market"},
        },
    )
    _write_json(run_dir / "summary.json", {"net_profit": "0"})

    report_path = run_dir / "report.html"
    report_path.write_text("existing report", encoding="utf-8")

    def _fail_generate_report(_artifact_dir: Path) -> None:
        raise AssertionError("generate_report should not run when report.html exists")

    monkeypatch.setattr(
        "packages.polymarket.simtrader.report.generate_report",
        _fail_generate_report,
    )

    exit_code = simtrader_main(["browse", "--open"])
    assert exit_code == 0
    assert report_path.read_text(encoding="utf-8") == "existing report"
    out = capsys.readouterr().out
    assert f'ii "{report_path}"' in out

    called: list[Path] = []

    def _fake_generate_report(artifact_dir: Path) -> SimpleNamespace:
        called.append(artifact_dir)
        report_path.write_text("forced report", encoding="utf-8")
        return SimpleNamespace(report_path=report_path)

    monkeypatch.setattr(
        "packages.polymarket.simtrader.report.generate_report",
        _fake_generate_report,
    )

    exit_code = simtrader_main(["browse", "--open", "--force"])
    assert exit_code == 0
    assert called == [run_dir]
    assert report_path.read_text(encoding="utf-8") == "forced report"
    out = capsys.readouterr().out
    assert f'ii "{report_path}"' in out
