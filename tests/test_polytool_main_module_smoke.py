from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]


def _run_polytool(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "polytool", *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=30,
    )


def _write_gate2_candidate_tape(tapes_dir: Path) -> str:
    slug = "politics-election-market"
    tape_dir = tapes_dir / slug
    tape_dir.mkdir()

    events = [
        {
            "event_type": "book",
            "asset_id": "yes-token",
            "seq": 0,
            "ts_recv": 1000.0,
            "bids": [],
            "asks": [{"price": "0.40", "size": "100"}],
        },
        {
            "event_type": "book",
            "asset_id": "no-token",
            "seq": 1,
            "ts_recv": 1001.0,
            "bids": [],
            "asks": [{"price": "0.50", "size": "100"}],
        },
        {
            "event_type": "price_change",
            "price_changes": [
                {"asset_id": "yes-token", "price": "0.40", "size": "100", "side": "SELL"},
                {"asset_id": "no-token", "price": "0.50", "size": "100", "side": "SELL"},
            ],
            "seq": 2,
            "ts_recv": 1002.0,
        },
    ]
    (tape_dir / "events.jsonl").write_text(
        "\n".join(json.dumps(event) for event in events) + "\n",
        encoding="utf-8",
    )
    (tape_dir / "meta.json").write_text(
        json.dumps(
            {
                "market_slug": slug,
                "category": "politics",
                "question": "Will the election outcome resolve this market?",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    return slug


@pytest.mark.parametrize(
    ("argv", "expected_fragments"),
    [
        (["--help"], ["Usage: polytool <command> [options]", "scan-gate2-candidates"]),
        (["simtrader", "run", "--help"], ["usage: polytool simtrader run", "--strategy"]),
        (["scan-gate2-candidates", "--help"], ["usage: scan-gate2-candidates", "--all"]),
        (
            ["scan-gate2-candidates", "--regime", "politics", "--help"],
            ["usage: scan-gate2-candidates", "--regime", "politics"],
        ),
    ],
)
def test_polytool_main_module_help_smoke(argv: list[str], expected_fragments: list[str]) -> None:
    proc = _run_polytool(*argv)
    combined_output = proc.stdout + proc.stderr

    assert proc.returncode == 0, combined_output
    for fragment in expected_fragments:
        assert fragment in combined_output


def test_polytool_main_module_scan_gate2_candidates_offline_smoke(tmp_path: Path) -> None:
    slug = _write_gate2_candidate_tape(tmp_path)

    proc = _run_polytool(
        "scan-gate2-candidates",
        "--tapes-dir",
        str(tmp_path),
        "--regime",
        "politics",
        "--top",
        "1",
    )
    combined_output = proc.stdout + proc.stderr

    assert proc.returncode == 0, combined_output
    assert slug in combined_output
    assert "Regime 'politics'" in combined_output
    assert "Mode: tape" in combined_output
