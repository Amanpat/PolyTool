"""Tests for simtrader clean sub-command."""

from __future__ import annotations

import json
from pathlib import Path


def _seed_artifacts(root: Path) -> None:
    """Create a minimal artifact tree under *root* (acts as artifacts/simtrader)."""
    for subdir, name in [
        ("runs", "20260225T000000Z"),
        ("tapes", "20260225T000000Z_abc12345"),
        ("sweeps", "quickrun_20260225T000000Z_abc12345"),
        ("batches", "batch_20260225T000000Z"),
        ("shadow_runs", "20260225T000000Z_shadow_abc12345"),
    ]:
        d = root / subdir / name
        d.mkdir(parents=True, exist_ok=True)
        (d / "dummy.json").write_text(
            json.dumps({"placeholder": True}), encoding="utf-8"
        )


def test_clean_dry_run_does_not_delete(
    tmp_path: Path, capsys, monkeypatch
) -> None:
    """Default (no --yes) must print what would be deleted but not remove anything."""
    from tools.cli.simtrader import main as simtrader_main

    artifacts_root = tmp_path / "artifacts" / "simtrader"
    monkeypatch.setattr("tools.cli.simtrader.DEFAULT_ARTIFACTS_DIR", artifacts_root)
    _seed_artifacts(artifacts_root)

    exit_code = simtrader_main(["clean"])
    assert exit_code == 0

    out = capsys.readouterr().out
    assert "[dry-run]" in out
    assert "Re-run with --yes" in out

    # All directories still present.
    for subdir in ("runs", "tapes", "sweeps", "batches", "shadow_runs"):
        assert (artifacts_root / subdir).exists()
        children = list((artifacts_root / subdir).iterdir())
        assert len(children) == 1, f"{subdir} should still have 1 child"


def test_clean_yes_deletes(tmp_path: Path, capsys, monkeypatch) -> None:
    """--yes must actually remove artifact folders and report a summary."""
    from tools.cli.simtrader import main as simtrader_main

    artifacts_root = tmp_path / "artifacts" / "simtrader"
    monkeypatch.setattr("tools.cli.simtrader.DEFAULT_ARTIFACTS_DIR", artifacts_root)
    _seed_artifacts(artifacts_root)

    exit_code = simtrader_main(["clean", "--yes"])
    assert exit_code == 0

    out = capsys.readouterr().out
    assert "Deleted" in out
    assert "5 folder(s)" in out

    # Category dirs still exist but are now empty.
    for subdir in ("runs", "tapes", "sweeps", "batches", "shadow_runs"):
        assert list((artifacts_root / subdir).iterdir()) == []


def test_clean_targeting_flags(tmp_path: Path, capsys, monkeypatch) -> None:
    """Passing --runs should only clean runs/ and skip everything else."""
    from tools.cli.simtrader import main as simtrader_main

    artifacts_root = tmp_path / "artifacts" / "simtrader"
    monkeypatch.setattr("tools.cli.simtrader.DEFAULT_ARTIFACTS_DIR", artifacts_root)
    _seed_artifacts(artifacts_root)

    exit_code = simtrader_main(["clean", "--yes", "--runs"])
    assert exit_code == 0

    out = capsys.readouterr().out
    assert "1 folder(s)" in out
    assert "Skipped:" in out

    # runs/ cleaned, others untouched.
    assert list((artifacts_root / "runs").iterdir()) == []
    assert len(list((artifacts_root / "tapes").iterdir())) == 1


def test_clean_refuses_bad_root(tmp_path: Path, capsys, monkeypatch) -> None:
    """If DEFAULT_ARTIFACTS_DIR doesn't end in artifacts/simtrader, refuse."""
    from tools.cli.simtrader import main as simtrader_main

    bad_root = tmp_path / "not_artifacts" / "danger"
    bad_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr("tools.cli.simtrader.DEFAULT_ARTIFACTS_DIR", bad_root)

    exit_code = simtrader_main(["clean", "--yes"])
    assert exit_code == 1

    err = capsys.readouterr().err
    assert "expected artifacts root" in err
