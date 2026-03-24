#!/usr/bin/env python3
"""Gate 4 — Dry-Run Live Gate.

Steps
-----
1. Run ``simtrader live --strategy market_maker_v0 --best-bid 0.45 --best-ask 0.55
   --asset-id test_token``.
2. Parse the JSON summary printed to stdout.
3. Gate criteria:
   - ``submitted == 0`` (no real orders sent)
   - ``dry_run == true``
   - No RuntimeError in output
4. Write ``artifacts/gates/dry_run_gate/gate_passed.json`` or ``gate_failed.json``.

Usage
-----
    python tools/gates/run_dry_run_gate.py [--best-bid PRICE] [--best-ask PRICE]
                                           [--asset-id TOKEN_ID]

No network connection required — the dry-run gate runs fully offline.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[2]
_GATE_DIR = _REPO_ROOT / "artifacts" / "gates" / "dry_run_gate"


def _run(cmd: list[str], *, timeout: int = 30) -> subprocess.CompletedProcess:
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


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--best-bid", type=float, default=0.45, dest="best_bid")
    parser.add_argument("--best-ask", type=float, default=0.55, dest="best_ask")
    parser.add_argument("--asset-id", default="test_token", dest="asset_id")
    args = parser.parse_args(argv)

    ts = datetime.now(timezone.utc).isoformat()
    commit = _git_hash()

    print("=" * 60)
    print("Gate 4 — Dry-Run Live")
    print("=" * 60)

    # ------------------------------------------------------------------
    # Step 1: Run simtrader live in dry-run mode (default)
    # ------------------------------------------------------------------
    print("\n[1/2] Running simtrader live (dry-run mode) ...")
    live_cmd = [
        sys.executable, "-m", "polytool",
        "simtrader", "live",
        "--strategy", "market_maker_v0",
        "--best-bid", str(args.best_bid),
        "--best-ask", str(args.best_ask),
        "--asset-id", args.asset_id,
    ]

    live_result = _run(live_cmd, timeout=30)
    stdout = live_result.stdout
    stderr = live_result.stderr

    # ------------------------------------------------------------------
    # Step 2: Evaluate gate criteria
    # ------------------------------------------------------------------
    print("\n[2/2] Evaluating gate criteria ...")

    # Check for RuntimeError
    if "RuntimeError" in stderr or "Error:" in stderr:
        error_line = next(
            (l for l in stderr.splitlines() if "Error" in l), stderr[:200]
        )
        print(f"  FAIL — RuntimeError or error in stderr: {error_line}")
        artifact = _write_gate_result(False, {
            "gate": "dry_run",
            "passed": False,
            "commit": commit,
            "timestamp": ts,
            "failure_reason": f"RuntimeError or error in stderr: {error_line}",
            "stderr_tail": stderr[-500:],
            "returncode": live_result.returncode,
        })
        print(f"\nFailed: {artifact}")
        return 1

    if live_result.returncode != 0:
        print(f"  FAIL — live command exited with code {live_result.returncode}")
        artifact = _write_gate_result(False, {
            "gate": "dry_run",
            "passed": False,
            "commit": commit,
            "timestamp": ts,
            "failure_reason": f"exit code {live_result.returncode}",
            "stderr_tail": stderr[-500:],
            "returncode": live_result.returncode,
        })
        print(f"\nFailed: {artifact}")
        return 1

    # Parse JSON from stdout
    try:
        summary = json.loads(stdout.strip())
    except json.JSONDecodeError as exc:
        print(f"  FAIL — stdout is not valid JSON: {exc}")
        print(f"  stdout was: {stdout[:500]!r}")
        artifact = _write_gate_result(False, {
            "gate": "dry_run",
            "passed": False,
            "commit": commit,
            "timestamp": ts,
            "failure_reason": f"stdout not parseable as JSON: {exc}",
            "stdout_raw": stdout[:500],
        })
        print(f"\nFailed: {artifact}")
        return 1

    submitted = summary.get("submitted")
    dry_run_flag = summary.get("dry_run")

    failures: list[str] = []
    if submitted != 0:
        failures.append(f"submitted={submitted!r} (expected 0)")
    if dry_run_flag is not True:
        failures.append(f"dry_run={dry_run_flag!r} (expected true)")

    if failures:
        print("  FAIL:")
        for f in failures:
            print(f"    - {f}")
        artifact = _write_gate_result(False, {
            "gate": "dry_run",
            "passed": False,
            "commit": commit,
            "timestamp": ts,
            "failure_reason": "; ".join(failures),
            "summary": summary,
        })
        print(f"\nFailed: {artifact}")
        return 1

    print(f"  submitted  = {submitted}  [ok]")
    print(f"  dry_run    = {dry_run_flag}  [ok]")
    print(f"  exit_code  = {live_result.returncode}  [ok]")
    print("  PASS")

    artifact = _write_gate_result(True, {
        "gate": "dry_run",
        "passed": True,
        "commit": commit,
        "timestamp": ts,
        "asset_id": args.asset_id,
        "best_bid": args.best_bid,
        "best_ask": args.best_ask,
        "summary": summary,
    })
    print(f"\nPassed: {artifact}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
