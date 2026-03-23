from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
YES_ID = "yes-token"
NO_ID = "no-token"


def _run_polytool(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "polytool", *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=30,
    )


def _write_eligible_tape(tapes_dir: Path, regime: str) -> str:
    slug = f"{regime}-ready-market"
    tape_dir = tapes_dir / slug
    tape_dir.mkdir()
    (tape_dir / "watch_meta.json").write_text(
        json.dumps(
            {
                "market_slug": slug,
                "yes_asset_id": YES_ID,
                "no_asset_id": NO_ID,
                "regime": regime,
            }
        ),
        encoding="utf-8",
    )
    events = [
        {
            "event_type": "book",
            "asset_id": YES_ID,
            "asks": [{"price": "0.40", "size": "100"}],
            "bids": [],
        },
        {
            "event_type": "book",
            "asset_id": NO_ID,
            "asks": [{"price": "0.50", "size": "100"}],
            "bids": [],
        },
    ]
    (tape_dir / "events.jsonl").write_text(
        "\n".join(json.dumps(event) for event in events) + "\n",
        encoding="utf-8",
    )
    return slug


@pytest.mark.parametrize(
    ("argv", "expected_fragments"),
    [
        (
            ["--help"],
            [
                "Usage: polytool <command> [options]",
                "scan-gate2-candidates",
                "tape-manifest",
                "watch-arb-candidates",
                "make-session-pack",
                "gate2-preflight",
                "hypothesis-summary",
            ],
        ),
        (
            ["tape-manifest", "--help"],
            ["usage: tape-manifest", "--tapes-dir", "--out"],
        ),
        (
            ["scan-gate2-candidates", "--help"],
            ["usage: scan-gate2-candidates", "--all", "--regime"],
        ),
        (
            ["make-session-pack", "--help"],
            ["usage: make-session-pack", "--regime", "--markets"],
        ),
        (
            ["watch-arb-candidates", "--help"],
            ["usage: watch-arb-candidates", "--markets", "--session-plan"],
        ),
        (
            ["gate2-preflight", "--help"],
            ["usage: gate2-preflight", "Check whether Gate 2 sweep is ready"],
        ),
        (
            ["hypothesis-summary", "--help"],
            ["hypothesis-summary [-h]", "--hypothesis-path"],
        ),
        (
            ["benchmark-manifest", "validate", "--help"],
            ["usage: benchmark-manifest validate", "--manifest", "--write-lock"],
        ),
    ],
)
def test_polytool_main_module_help_surface_smoke(
    argv: list[str], expected_fragments: list[str]
) -> None:
    proc = _run_polytool(*argv)
    combined_output = proc.stdout + proc.stderr

    assert proc.returncode == 0, combined_output
    for fragment in expected_fragments:
        assert fragment in combined_output


def test_polytool_main_module_gate2_preflight_ready_smoke(tmp_path: Path) -> None:
    for regime in ("politics", "sports", "new_market"):
        _write_eligible_tape(tmp_path, regime)

    proc = _run_polytool("gate2-preflight", "--tapes-dir", str(tmp_path))
    combined_output = proc.stdout + proc.stderr

    assert proc.returncode == 0, combined_output
    assert "Result: READY" in combined_output
    assert "Eligible tapes: 3" in combined_output
    assert "Missing regimes: none" in combined_output

