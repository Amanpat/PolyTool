#!/usr/bin/env python3
"""Gate 1 — Replay Determinism Gate.

Steps
-----
1. Run ``simtrader quickrun --sweep quick_small`` to record a live tape.
2. Parse stdout to extract the tape directory path.
3. Replay the same tape twice using ``simtrader run --strategy binary_complement_arb``.
4. Compare the two ``summary.json`` outputs field-by-field.
5. Write ``artifacts/gates/replay_gate/gate_passed.json`` on success, or
   ``gate_failed.json`` with a diff on failure.

Usage
-----
    python tools/gates/close_replay_gate.py [--market SLUG] [--duration SECONDS]

The script requires a live internet connection (Polymarket WS + Gamma API).
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[2]
_GATE_DIR = _REPO_ROOT / "artifacts" / "gates" / "replay_gate"
_TAPE_LINE_RE = re.compile(r"tape\s+dir\s*:\s*(.+?)/?$", re.MULTILINE | re.IGNORECASE)
_RUN_DIR_LINE_RE = re.compile(r"run\s+dir\s*:\s*(.+?)/?$", re.MULTILINE | re.IGNORECASE)

NUMERIC_FIELDS = {
    "starting_cash",
    "final_cash",
    "reserved_cash",
    "position_mark_value",
    "final_equity",
    "realized_pnl",
    "unrealized_pnl",
    "total_fees",
    "net_profit",
}

# Fields that are always expected to differ between replay runs (e.g. timestamped IDs).
# Excluding them prevents false-positive failures in the determinism comparison.
_DIFF_EXCLUDE = frozenset({"run_id"})


def _run(cmd: list[str], *, timeout: int = 300) -> subprocess.CompletedProcess:
    """Run a shell command and return the CompletedProcess result."""
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
        capture_output=True,
        text=True,
        cwd=str(_REPO_ROOT),
    )
    return result.stdout.strip() or "unknown"


def _write_gate_result(passed: bool, payload: dict) -> Path:
    _GATE_DIR.mkdir(parents=True, exist_ok=True)
    fname = "gate_passed.json" if passed else "gate_failed.json"
    path = _GATE_DIR / fname
    # Remove the opposite file so only one exists
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


def _extract_tape_dir(output: str) -> Path | None:
    m = _TAPE_LINE_RE.search(output)
    if not m:
        return None
    raw = m.group(1).strip()
    p = Path(raw)
    if not p.is_absolute():
        p = _REPO_ROOT / p
    return p


def _extract_run_dir(output: str) -> Path | None:
    m = _RUN_DIR_LINE_RE.search(output)
    if not m:
        return None
    raw = m.group(1).strip()
    p = Path(raw)
    if not p.is_absolute():
        p = _REPO_ROOT / p
    return p


def _load_summary(run_dir: Path) -> dict | None:
    summary_path = run_dir / "summary.json"
    if not summary_path.exists():
        return None
    return json.loads(summary_path.read_text(encoding="utf-8"))


def _diff_summaries(a: dict, b: dict) -> list[str]:
    """Return a list of diff lines for mismatched fields.

    Fields in ``_DIFF_EXCLUDE`` (e.g. ``run_id``) are skipped because they
    are always expected to differ between replay runs (timestamped directory names).
    """
    diffs: list[str] = []
    all_keys = (set(a) | set(b)) - _DIFF_EXCLUDE
    for key in sorted(all_keys):
        va = a.get(key, "<missing>")
        vb = b.get(key, "<missing>")
        if va != vb:
            diffs.append(f"  {key}: run_a={va!r}  run_b={vb!r}")
    return diffs


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--market", default=None, metavar="SLUG",
                        help="Polymarket market slug (optional; auto-picks if omitted)")
    parser.add_argument("--duration", type=float, default=30.0, metavar="SECONDS",
                        help="Tape recording duration in seconds (default: 30)")
    args = parser.parse_args(argv)

    ts = datetime.now(timezone.utc).isoformat()
    commit = _git_hash()

    print("=" * 60)
    print("Gate 1 — Replay Determinism")
    print("=" * 60)

    # ------------------------------------------------------------------
    # Step 1: Record tape via quickrun --sweep quick_small
    # ------------------------------------------------------------------
    print("\n[1/4] Recording tape with quickrun --sweep quick_small ...")
    qr_cmd = [
        sys.executable, "-m", "polytool",
        "simtrader", "quickrun",
        "--sweep", "quick_small",
        "--duration", str(args.duration),
    ]
    if args.market:
        qr_cmd += ["--market", args.market]

    qr_result = _run(qr_cmd, timeout=int(args.duration) + 120)
    qr_output = qr_result.stdout + qr_result.stderr

    if qr_result.returncode != 0:
        print(f"  ERROR: quickrun failed (exit {qr_result.returncode})")
        print(qr_output[-2000:])
        artifact = _write_gate_result(False, {
            "gate": "replay",
            "passed": False,
            "commit": commit,
            "timestamp": ts,
            "failure_reason": f"quickrun exited with code {qr_result.returncode}",
            "quickrun_output_tail": qr_output[-1000:],
        })
        print(f"\nFailed: {artifact}")
        return 1

    tape_dir = _extract_tape_dir(qr_output)
    if tape_dir is None or not (tape_dir / "events.jsonl").exists():
        print("  ERROR: could not locate tape directory from quickrun output.")
        print("  Output searched:")
        print(qr_output[-1000:])
        artifact = _write_gate_result(False, {
            "gate": "replay",
            "passed": False,
            "commit": commit,
            "timestamp": ts,
            "failure_reason": "tape_dir not found in quickrun output",
        })
        print(f"\nFailed: {artifact}")
        return 1

    events_path = tape_dir / "events.jsonl"
    print(f"  Tape: {events_path.relative_to(_REPO_ROOT)}")

    # ------------------------------------------------------------------
    # Step 2 & 3: Replay the tape twice
    # ------------------------------------------------------------------
    run_dirs: list[Path] = []
    for attempt in (1, 2):
        print(f"\n[{attempt + 1}/4] Replay run #{attempt} ...")
        run_cmd = [
            sys.executable, "-m", "polytool",
            "simtrader", "run",
            "--tape", str(events_path.relative_to(_REPO_ROOT)),
            "--strategy", "binary_complement_arb",
        ]
        run_result = _run(run_cmd, timeout=120)
        run_output = run_result.stdout + run_result.stderr

        if run_result.returncode != 0:
            print(f"  ERROR: replay run #{attempt} failed (exit {run_result.returncode})")
            artifact = _write_gate_result(False, {
                "gate": "replay",
                "passed": False,
                "commit": commit,
                "timestamp": ts,
                "tape_path": str(events_path.relative_to(_REPO_ROOT)),
                "failure_reason": f"replay run #{attempt} exited {run_result.returncode}",
                "run_output_tail": run_output[-500:],
            })
            print(f"\nFailed: {artifact}")
            return 1

        run_dir = _extract_run_dir(run_output)
        if run_dir is None or not (run_dir / "summary.json").exists():
            print(f"  ERROR: could not locate run_dir for replay #{attempt}")
            artifact = _write_gate_result(False, {
                "gate": "replay",
                "passed": False,
                "commit": commit,
                "timestamp": ts,
                "tape_path": str(events_path.relative_to(_REPO_ROOT)),
                "failure_reason": f"run_dir not found for replay #{attempt}",
            })
            print(f"\nFailed: {artifact}")
            return 1

        run_dirs.append(run_dir)
        print(f"  Run dir: {run_dir.relative_to(_REPO_ROOT)}")

    # ------------------------------------------------------------------
    # Step 4: Compare summary.json
    # ------------------------------------------------------------------
    print("\n[4/4] Comparing summary.json ...")
    summary_a = _load_summary(run_dirs[0])
    summary_b = _load_summary(run_dirs[1])

    if summary_a is None or summary_b is None:
        artifact = _write_gate_result(False, {
            "gate": "replay",
            "passed": False,
            "commit": commit,
            "timestamp": ts,
            "tape_path": str(events_path.relative_to(_REPO_ROOT)),
            "failure_reason": "summary.json missing for one or both replay runs",
        })
        print(f"\nFailed: {artifact}")
        return 1

    diffs = _diff_summaries(summary_a, summary_b)
    if diffs:
        print("  FAIL — summaries differ:")
        for d in diffs:
            print(d)
        artifact = _write_gate_result(False, {
            "gate": "replay",
            "passed": False,
            "commit": commit,
            "timestamp": ts,
            "tape_path": str(events_path.relative_to(_REPO_ROOT)),
            "run_a": str(run_dirs[0].relative_to(_REPO_ROOT)),
            "run_b": str(run_dirs[1].relative_to(_REPO_ROOT)),
            "failure_reason": "summary.json fields differ between replay runs",
            "diff": diffs,
        })
        print(f"\nFailed: {artifact}")
        return 1

    print("  PASS — both replays produced identical summary.json")
    artifact = _write_gate_result(True, {
        "gate": "replay",
        "passed": True,
        "commit": commit,
        "timestamp": ts,
        "tape_path": str(events_path.relative_to(_REPO_ROOT)),
        "run_a": str(run_dirs[0].relative_to(_REPO_ROOT)),
        "run_b": str(run_dirs[1].relative_to(_REPO_ROOT)),
        "summary_snapshot": summary_a,
    })
    print(f"\nPassed: {artifact}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
