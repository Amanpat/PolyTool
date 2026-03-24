#!/usr/bin/env python3
"""Gate 2 — Scenario Sweep Gate.

Steps
-----
1. Run ``simtrader quickrun --sweep quick`` (24 scenarios: 4 fee × 3 cancel × 2 mark).
2. Parse stdout to find the sweep directory.
3. Read ``sweep_summary.json`` and extract per-scenario ``net_profit``.
4. Gate criterion: ``profitable_scenarios / total_scenarios >= 0.70``.
5. Write ``artifacts/gates/sweep_gate/gate_passed.json`` or ``gate_failed.json``.

Usage
-----
    python tools/gates/close_sweep_gate.py [--market SLUG] [--duration SECONDS]
                                           [--threshold FLOAT]

The script requires a live internet connection.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[2]
_GATE_DIR = _REPO_ROOT / "artifacts" / "gates" / "sweep_gate"
_SWEEP_DIR_RE = re.compile(r"Sweep dir\s*:\s*(.+?)/?$", re.MULTILINE)

_DEFAULT_THRESHOLD = 0.70  # fraction of scenarios that must show net_profit > 0


def _run(cmd: list[str], *, timeout: int = 600) -> subprocess.CompletedProcess:
    print(f"  $ {' '.join(cmd)}")
    return subprocess.run(
        cmd,
        capture_output=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
        cwd=str(_REPO_ROOT),
    )


def _git_hash() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"],
        capture_output=True, text=True, cwd=str(_REPO_ROOT),
    )
    return result.stdout.strip() or "unknown"


def _write_gate_result(passed: bool, payload: dict) -> Path:
    _GATE_DIR.mkdir(parents=True, exist_ok=True)
    fname = "gate_passed.json" if passed else "gate_failed.json"
    path = _GATE_DIR / fname
    opposite = _GATE_DIR / ("gate_failed.json" if passed else "gate_passed.json")
    if opposite.exists():
        opposite.unlink()
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    try:
        from packages.polymarket.notifications.discord import notify_gate_result as _ng
        _ng(
            payload.get("gate", "unknown"),
            passed,
            commit=payload.get("commit", "unknown"),
            detail=payload.get("failure_reason") if not passed else None,
        )
    except Exception:
        pass  # notifications are best-effort; never block gate script
    return path


def _extract_sweep_dir(output: str) -> Path | None:
    m = _SWEEP_DIR_RE.search(output)
    if not m:
        return None
    raw = m.group(1).strip()
    p = Path(raw)
    if not p.is_absolute():
        p = _REPO_ROOT / p
    return p


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--market", default=None, metavar="SLUG")
    parser.add_argument("--duration", type=float, default=60.0, metavar="SECONDS",
                        help="Tape recording duration (default: 60s for better tape quality)")
    parser.add_argument("--threshold", type=float, default=_DEFAULT_THRESHOLD,
                        metavar="FLOAT",
                        help=f"Minimum fraction of profitable scenarios (default: {_DEFAULT_THRESHOLD})")
    args = parser.parse_args(argv)

    ts = datetime.now(timezone.utc).isoformat()
    commit = _git_hash()

    print("=" * 60)
    print("Gate 2 — Scenario Sweep")
    print("=" * 60)

    # ------------------------------------------------------------------
    # Step 1: Run quickrun --sweep quick (full 24-scenario sweep)
    # ------------------------------------------------------------------
    print(f"\n[1/3] Running quickrun --sweep quick (24 scenarios) ...")
    qr_cmd = [
        sys.executable, "-m", "polytool",
        "simtrader", "quickrun",
        "--sweep", "quick",
        "--duration", str(args.duration),
    ]
    if args.market:
        qr_cmd += ["--market", args.market]

    qr_result = _run(qr_cmd, timeout=int(args.duration) + 600)
    qr_output = qr_result.stdout + qr_result.stderr

    if qr_result.returncode != 0:
        print(f"  ERROR: quickrun failed (exit {qr_result.returncode})")
        print(qr_output[-2000:])
        artifact = _write_gate_result(False, {
            "gate": "sweep",
            "passed": False,
            "commit": commit,
            "timestamp": ts,
            "failure_reason": f"quickrun exited with code {qr_result.returncode}",
            "quickrun_output_tail": qr_output[-1000:],
        })
        print(f"\nFailed: {artifact}")
        return 1

    # ------------------------------------------------------------------
    # Step 2: Find sweep directory and load sweep_summary.json
    # ------------------------------------------------------------------
    print("\n[2/3] Locating sweep_summary.json ...")
    sweep_dir = _extract_sweep_dir(qr_output)
    if sweep_dir is None:
        print("  ERROR: could not parse sweep dir from quickrun output.")
        print(qr_output[-1000:])
        artifact = _write_gate_result(False, {
            "gate": "sweep",
            "passed": False,
            "commit": commit,
            "timestamp": ts,
            "failure_reason": "sweep_dir not found in quickrun output",
        })
        print(f"\nFailed: {artifact}")
        return 1

    summary_path = sweep_dir / "sweep_summary.json"
    if not summary_path.exists():
        print(f"  ERROR: sweep_summary.json not found at {summary_path}")
        artifact = _write_gate_result(False, {
            "gate": "sweep",
            "passed": False,
            "commit": commit,
            "timestamp": ts,
            "sweep_dir": str(sweep_dir.relative_to(_REPO_ROOT)),
            "failure_reason": "sweep_summary.json not found",
        })
        print(f"\nFailed: {artifact}")
        return 1

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    scenarios: list[dict] = summary.get("scenarios", [])
    print(f"  Sweep dir    : {sweep_dir.relative_to(_REPO_ROOT)}")
    print(f"  Scenario count: {len(scenarios)}")

    # ------------------------------------------------------------------
    # Step 3: Evaluate gate criterion
    # ------------------------------------------------------------------
    print(f"\n[3/3] Evaluating gate (threshold: >= {args.threshold:.0%} profitable) ...")
    if not scenarios:
        artifact = _write_gate_result(False, {
            "gate": "sweep",
            "passed": False,
            "commit": commit,
            "timestamp": ts,
            "sweep_dir": str(sweep_dir.relative_to(_REPO_ROOT)),
            "failure_reason": "no scenarios in sweep_summary.json",
        })
        print(f"\nFailed: {artifact}")
        return 1

    scenario_breakdown: list[dict] = []
    profitable = 0
    for s in scenarios:
        net_pnl = Decimal(str(s.get("net_profit", "0")))
        is_profitable = net_pnl > 0
        if is_profitable:
            profitable += 1
        scenario_breakdown.append({
            "scenario_id": s.get("scenario_id", "?"),
            "scenario_name": s.get("scenario_name", "?"),
            "net_profit": str(net_pnl),
            "profitable": is_profitable,
        })

    total = len(scenarios)
    fraction = profitable / total
    passed = fraction >= args.threshold

    print(f"  Profitable   : {profitable}/{total}  ({fraction:.1%})")
    print(f"  Threshold    : {args.threshold:.0%}")
    print(f"  Gate         : {'PASS' if passed else 'FAIL'}")

    payload = {
        "gate": "sweep",
        "passed": passed,
        "commit": commit,
        "timestamp": ts,
        "sweep_dir": str(sweep_dir.relative_to(_REPO_ROOT)),
        "total_scenarios": total,
        "profitable_scenarios": profitable,
        "profitable_fraction": round(fraction, 4),
        "threshold": args.threshold,
        "scenario_breakdown": scenario_breakdown,
        "aggregate": summary.get("aggregate", {}),
    }
    artifact = _write_gate_result(passed, payload)
    print(f"\n{'Passed' if passed else 'Failed'}: {artifact}")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
