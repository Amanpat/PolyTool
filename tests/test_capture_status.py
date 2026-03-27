"""Tests for tools/gates/capture_status.py (TDD RED -> GREEN).

Four tests covering shortage table display, complete state, JSON mode,
and empty roots as specified in quick-029 PLAN.md.
"""

from __future__ import annotations

import json
import sys
from io import StringIO
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_gold_tape(
    parent: Path,
    *,
    slug: str,
    bucket: str,
    n_events: int = 60,
) -> Path:
    """Create a minimal Gold tape dir with watch_meta.json and events.jsonl."""
    tape_dir = parent / slug
    tape_dir.mkdir(parents=True, exist_ok=True)

    # events.jsonl with price_change events (Gold-style)
    events_path = tape_dir / "events.jsonl"
    lines = [
        json.dumps({"type": "price_change", "asset_id": "x", "price": 0.5})
        for _ in range(n_events)
    ]
    events_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    # watch_meta.json with explicit bucket field (Gold tapes always have this)
    watch_meta = {"bucket": bucket, "market_slug": slug}
    (tape_dir / "watch_meta.json").write_text(
        json.dumps(watch_meta), encoding="utf-8"
    )

    return tape_dir


# ---------------------------------------------------------------------------
# Test 1: shortage_table — 1 politics tape → exit 1, table shows bucket data
# ---------------------------------------------------------------------------


def test_shortage_table(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    """1 politics tape → exit 1, stdout contains bucket table with 'politics' and 'Need'."""
    _make_gold_tape(tmp_path, slug="politics-market-1", bucket="politics")

    from tools.gates import capture_status

    exit_code = capture_status.main(["--tape-roots", str(tmp_path)])

    captured = capsys.readouterr()
    assert exit_code == 1, f"Expected exit 1 (shortage), got {exit_code}"
    assert "politics" in captured.out
    assert "Need" in captured.out


# ---------------------------------------------------------------------------
# Test 2: complete_state — 50 tapes across all buckets → exit 0, COMPLETE
# ---------------------------------------------------------------------------


def test_complete_state(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    """50 tapes across all 5 buckets → exit 0, stdout contains 'COMPLETE'."""
    bucket_counts = {
        "politics": 10,
        "sports": 15,
        "crypto": 10,
        "near_resolution": 10,
        "new_market": 5,
    }
    for bucket, count in bucket_counts.items():
        for i in range(count):
            _make_gold_tape(
                tmp_path,
                slug=f"{bucket}-market-{i:02d}",
                bucket=bucket,
            )

    from tools.gates import capture_status

    exit_code = capture_status.main(["--tape-roots", str(tmp_path)])

    captured = capsys.readouterr()
    assert exit_code == 0, f"Expected exit 0 (complete), got {exit_code}"
    assert "COMPLETE" in captured.out


# ---------------------------------------------------------------------------
# Test 3: json_mode — 1 politics tape, --json → valid JSON with expected fields
# ---------------------------------------------------------------------------


def test_json_mode(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    """--json mode with 1 politics tape → valid JSON, complete=false, total_need=49,
    buckets['politics']['have']==1."""
    _make_gold_tape(tmp_path, slug="politics-market-json", bucket="politics")

    from tools.gates import capture_status

    exit_code = capture_status.main(["--tape-roots", str(tmp_path), "--json"])

    captured = capsys.readouterr()
    assert exit_code == 1, f"Expected exit 1 (shortage), got {exit_code}"

    # Must parse as valid JSON
    data = json.loads(captured.out)

    assert data["complete"] is False
    assert data["total_need"] == 49
    assert data["buckets"]["politics"]["have"] == 1
    assert "total_have" in data
    assert "total_quota" in data
    assert "buckets" in data


# ---------------------------------------------------------------------------
# Test 4: empty_roots — empty directory → exit 1, 0 tapes
# ---------------------------------------------------------------------------


def test_empty_roots(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    """Empty tape root → exit 1, JSON total_have=0."""
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()

    from tools.gates import capture_status

    exit_code = capture_status.main(["--tape-roots", str(empty_dir), "--json"])

    captured = capsys.readouterr()
    assert exit_code == 1, f"Expected exit 1 (shortage), got {exit_code}"

    data = json.loads(captured.out)
    assert data["total_have"] == 0
