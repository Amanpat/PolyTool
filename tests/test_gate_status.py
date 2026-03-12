from __future__ import annotations

import json
from pathlib import Path

import pytest


def _write_gate_payload(gates_dir: Path, gate_dir_name: str, filename: str, payload: dict) -> None:
    gate_dir = gates_dir / gate_dir_name
    gate_dir.mkdir(parents=True, exist_ok=True)
    (gate_dir / filename).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _write_required_passes(gates_dir: Path) -> None:
    _write_gate_payload(
        gates_dir,
        "replay_gate",
        "gate_passed.json",
        {"timestamp": "2026-03-11T00:00:00+00:00", "commit": "abc123"},
    )
    _write_gate_payload(
        gates_dir,
        "sweep_gate",
        "gate_passed.json",
        {
            "timestamp": "2026-03-11T00:00:00+00:00",
            "profitable_fraction": 0.75,
            "profitable_scenarios": 18,
            "total_scenarios": 24,
        },
    )
    _write_gate_payload(
        gates_dir,
        "shadow_gate",
        "gate_passed.json",
        {"timestamp": "2026-03-11T00:00:00+00:00", "notes": "manual sign-off"},
    )
    _write_gate_payload(
        gates_dir,
        "dry_run_gate",
        "gate_passed.json",
        {"timestamp": "2026-03-11T00:00:00+00:00"},
    )


def test_gate_status_optional_mm_sweep_not_run_is_non_blocking(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    import tools.gates.gate_status as gate_status

    gates_dir = tmp_path / "gates"
    _write_required_passes(gates_dir)
    monkeypatch.setattr(gate_status, "_GATES_DIR", gates_dir)

    rc = gate_status.main()
    output = capsys.readouterr().out

    assert rc == 0
    assert "mm_sweep_gate (Gate 2b optional)" in output
    assert "[NOT_RUN]" in output
    assert "ALL REQUIRED GATES PASSED" in output


def test_gate_status_optional_mm_sweep_failure_still_keeps_exit_code_zero(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    import tools.gates.gate_status as gate_status

    gates_dir = tmp_path / "gates"
    _write_required_passes(gates_dir)
    _write_gate_payload(
        gates_dir,
        "mm_sweep_gate",
        "gate_failed.json",
        {
            "generated_at": "2026-03-11T00:00:00+00:00",
            "tapes_positive": 2,
            "tapes_total": 3,
            "pass_rate": 0.6667,
        },
    )
    monkeypatch.setattr(gate_status, "_GATES_DIR", gates_dir)

    rc = gate_status.main()
    output = capsys.readouterr().out

    assert rc == 0
    assert "[FAILED]" in output
    assert "2/3 positive tapes (67%)" in output
