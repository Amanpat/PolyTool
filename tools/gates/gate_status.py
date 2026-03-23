#!/usr/bin/env python3
"""Gate Status Reporter.

Reads ``gate_passed.json`` / ``gate_failed.json`` files under
``artifacts/gates/`` and prints a status table.

Exit code 0 if every required gate has a passing artifact.
Exit code 1 if any required gate is missing or failed.

Usage
-----
    python tools/gates/gate_status.py
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_GATES_DIR = _REPO_ROOT / "artifacts" / "gates"

# Ordered list of (gate_key, dir_name, description, required)
_EXPECTED_GATES: list[tuple[str, str, str, bool]] = [
    ("replay", "replay_gate", "Gate 1 - Replay Determinism", True),
    ("sweep", "sweep_gate", "Gate 2 - Scenario Sweep (>=70% profitable)", True),
    ("shadow", "shadow_gate", "Gate 3 - Shadow Mode (manual)", True),
    ("dry_run", "dry_run_gate", "Gate 4 - Dry-Run Live", True),
    ("mm_sweep", "mm_sweep_gate", "mm_sweep_gate (Gate 2b optional)", False),
]

_COL_GATE = 46
_COL_STATUS = 10
_COL_TS = 28
_COL_NOTES = 40
_TABLE_WIDTH = 118


def _load_gate(gate_dir: Path, *, missing_label: str) -> tuple[str, dict | None]:
    """Return (status_label, payload_or_None) for a gate directory."""
    passed_path = gate_dir / "gate_passed.json"
    failed_path = gate_dir / "gate_failed.json"

    if passed_path.exists():
        try:
            return "PASSED", json.loads(passed_path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            return "CORRUPT", None

    if failed_path.exists():
        try:
            return "FAILED", json.loads(failed_path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            return "CORRUPT", None

    return missing_label, None


def _fmt_ts(ts_str: str | None) -> str:
    if not ts_str:
        return "-"
    return ts_str[:19].replace("T", " ")


def _fmt_notes(gate_key: str, status: str, payload: dict | None) -> str:
    if status == "MISSING":
        return "No artifact found"
    if status == "NOT_RUN":
        return "Optional gate not run"
    if status == "CORRUPT":
        return "artifact JSON unreadable"
    if payload is None:
        return ""

    if gate_key == "mm_sweep":
        positive = payload.get("tapes_positive")
        total = payload.get("tapes_total")
        pass_rate = payload.get("pass_rate")
        if positive is not None and total is not None and pass_rate is not None:
            return f"{positive}/{total} positive tapes ({pass_rate:.0%})"

    if status == "PASSED":
        if gate_key == "sweep":
            frac = payload.get("profitable_fraction")
            total = payload.get("total_scenarios")
            if frac is not None and total is not None:
                return f"{payload.get('profitable_scenarios')}/{total} profitable ({frac:.0%})"
        if gate_key == "replay":
            return f"commit {payload.get('commit', '?')}"
        if gate_key == "dry_run":
            return "submitted=0, dry_run=true"
        if gate_key == "shadow":
            return payload.get("notes", "manual sign-off")
        return f"commit {payload.get('commit', '?')}"

    if status == "FAILED":
        reason = payload.get("failure_reason", "")
        if reason:
            return reason[:_COL_NOTES - 3] + "..." if len(reason) > _COL_NOTES else reason

    return ""


def _status_symbol(status: str) -> str:
    return {
        "PASSED": "[PASSED]",
        "FAILED": "[FAILED]",
        "MISSING": "[MISSING]",
        "NOT_RUN": "[NOT_RUN]",
        "CORRUPT": "[CORRUPT]",
    }.get(status, status)


def main() -> int:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    print(f"\nGate Status Report  [{now}]")
    print("=" * _TABLE_WIDTH)

    header = (
        f"{'Gate':<{_COL_GATE}}"
        f"{'Status':<{_COL_STATUS}}"
        f"{'Timestamp':<{_COL_TS}}"
        f"Notes"
    )
    print(header)
    print("-" * _TABLE_WIDTH)

    all_required_passed = True

    for gate_key, dir_name, description, required in _EXPECTED_GATES:
        gate_dir = _GATES_DIR / dir_name
        status, payload = _load_gate(
            gate_dir,
            missing_label="MISSING" if required else "NOT_RUN",
        )

        if required and status != "PASSED":
            all_required_passed = False

        ts_str = None
        if payload is not None:
            ts_str = payload.get("timestamp") or payload.get("generated_at")
        notes = _fmt_notes(gate_key, status, payload)
        symbol = _status_symbol(status)

        row = (
            f"{description:<{_COL_GATE}}"
            f"{symbol:<{_COL_STATUS + 2}}"
            f"{_fmt_ts(ts_str):<{_COL_TS}}"
            f"{notes}"
        )
        print(row)

    print("-" * _TABLE_WIDTH)

    if _GATES_DIR.exists():
        extra_dirs = [
            d for d in _GATES_DIR.iterdir()
            if d.is_dir() and d.name not in {dir_name for _, dir_name, _, _ in _EXPECTED_GATES}
        ]
        if extra_dirs:
            print(f"\nExtra gate dirs (not in registry): {[d.name for d in extra_dirs]}")

    if all_required_passed:
        print("\nResult: ALL REQUIRED GATES PASSED - Track A promotion criteria met.\n")
        return 0

    print(
        "\nResult: ONE OR MORE REQUIRED GATES NOT PASSED - "
        "do not promote to Stage 1 capital.\n"
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
