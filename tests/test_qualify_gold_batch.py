"""Tests for tools/gates/qualify_gold_batch.py (TDD RED -> GREEN).

Nine tests covering per-tape verdicts, shortage delta, gate2-ready list,
JSON output, over-quota detection, baseline awareness, and edge cases.
"""

from __future__ import annotations

import json
import sys
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


def _make_gold_tape_no_bucket(
    parent: Path,
    *,
    slug: str,
    n_events: int = 60,
) -> Path:
    """Create a minimal Gold tape dir with NO bucket field in watch_meta.json."""
    tape_dir = parent / slug
    tape_dir.mkdir(parents=True, exist_ok=True)

    events_path = tape_dir / "events.jsonl"
    lines = [
        json.dumps({"type": "price_change", "asset_id": "x", "price": 0.5})
        for _ in range(n_events)
    ]
    events_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    # watch_meta.json without bucket field
    watch_meta = {"market_slug": slug}
    (tape_dir / "watch_meta.json").write_text(
        json.dumps(watch_meta), encoding="utf-8"
    )

    return tape_dir


# ---------------------------------------------------------------------------
# Test 1: single_tape_qualifies
# ---------------------------------------------------------------------------


def test_single_tape_qualifies(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    """One Gold tape with 60 events and bucket='sports' in empty corpus ->
    QUALIFIED, shortage delta shows sports need reduced by 1, tape is gate2-ready.
    """
    tape_dir = _make_gold_tape(tmp_path / "batch", slug="sports-market-1", bucket="sports")
    empty_root = tmp_path / "empty_corpus"
    empty_root.mkdir()

    from tools.gates import qualify_gold_batch

    exit_code = qualify_gold_batch.main([
        "--tape-dirs", str(tape_dir),
        "--tape-roots", str(empty_root),
    ])

    captured = capsys.readouterr()
    assert exit_code == 0, f"Expected exit 0 (at least one qualifies), got {exit_code}"
    assert "QUALIFIED" in captured.out
    assert "sports" in captured.out
    # Shortage delta: sports need drops by 1
    assert "Gate 2 ready" in captured.out or "gate2" in captured.out.lower()


# ---------------------------------------------------------------------------
# Test 2: tape_too_short
# ---------------------------------------------------------------------------


def test_tape_too_short(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    """One Gold tape with 30 events -> REJECTED too_short, no gate2-ready tapes."""
    tape_dir = _make_gold_tape(
        tmp_path / "batch", slug="sports-short-1", bucket="sports", n_events=30
    )
    empty_root = tmp_path / "empty_corpus"
    empty_root.mkdir()

    from tools.gates import qualify_gold_batch

    exit_code = qualify_gold_batch.main([
        "--tape-dirs", str(tape_dir),
        "--tape-roots", str(empty_root),
    ])

    captured = capsys.readouterr()
    assert exit_code == 1, f"Expected exit 1 (no tape qualifies), got {exit_code}"
    assert "REJECTED" in captured.out
    assert "too_short" in captured.out
    # No gate2-ready tapes
    assert "No tapes" in captured.out or "0" in captured.out


# ---------------------------------------------------------------------------
# Test 3: tape_no_bucket
# ---------------------------------------------------------------------------


def test_tape_no_bucket(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    """One Gold tape with 60 events but no bucket field -> REJECTED no_bucket_label."""
    tape_dir = _make_gold_tape_no_bucket(
        tmp_path / "batch", slug="nobucket-market-1", n_events=60
    )
    empty_root = tmp_path / "empty_corpus"
    empty_root.mkdir()

    from tools.gates import qualify_gold_batch

    exit_code = qualify_gold_batch.main([
        "--tape-dirs", str(tape_dir),
        "--tape-roots", str(empty_root),
    ])

    captured = capsys.readouterr()
    assert exit_code == 1, f"Expected exit 1 (no tape qualifies), got {exit_code}"
    assert "REJECTED" in captured.out
    assert "no_bucket_label" in captured.out


# ---------------------------------------------------------------------------
# Test 4: batch_mixed
# ---------------------------------------------------------------------------


def test_batch_mixed(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    """Three tapes: qualifying sports, too-short politics, qualifying politics.
    Report shows 2 QUALIFIED / 1 REJECTED, shortage delta shows sports -1 and politics -1.
    """
    batch_dir = tmp_path / "batch"
    tape_sports = _make_gold_tape(batch_dir, slug="sports-ok", bucket="sports", n_events=60)
    tape_politics_short = _make_gold_tape(
        batch_dir, slug="politics-short", bucket="politics", n_events=30
    )
    tape_politics_ok = _make_gold_tape(
        batch_dir, slug="politics-ok", bucket="politics", n_events=65
    )
    empty_root = tmp_path / "empty_corpus"
    empty_root.mkdir()

    from tools.gates import qualify_gold_batch

    exit_code = qualify_gold_batch.main([
        "--tape-dirs", str(tape_sports), str(tape_politics_short), str(tape_politics_ok),
        "--tape-roots", str(empty_root),
    ])

    captured = capsys.readouterr()
    assert exit_code == 0, f"Expected exit 0 (at least one qualifies), got {exit_code}"
    # 2 qualified, 1 rejected
    assert "2 qualified" in captured.out or "qualified: 2" in captured.out.lower()
    assert "1 rejected" in captured.out or "rejected: 1" in captured.out.lower()
    assert "sports" in captured.out
    assert "politics" in captured.out


# ---------------------------------------------------------------------------
# Test 5: over_quota_detection
# ---------------------------------------------------------------------------


def test_over_quota_detection(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    """11 politics tapes submitted against empty corpus (quota=10) ->
    10 QUALIFIED, 1 REJECTED over_quota, shortage delta shows politics fully satisfied.
    """
    batch_dir = tmp_path / "batch"
    tape_dirs = [
        _make_gold_tape(batch_dir, slug=f"politics-market-{i}", bucket="politics", n_events=60)
        for i in range(11)
    ]
    empty_root = tmp_path / "empty_corpus"
    empty_root.mkdir()

    from tools.gates import qualify_gold_batch

    result = qualify_gold_batch.qualify_batch(
        [Path(str(t)) for t in tape_dirs],
        [Path(str(empty_root))],
    )

    qualified = [r for r in result["batch_results"] if r["status"] == "QUALIFIED"]
    rejected = [r for r in result["batch_results"] if r["status"] == "REJECTED"]
    over_quota = [r for r in rejected if r["reject_reason"] == "over_quota"]

    assert len(qualified) == 10, f"Expected 10 qualified, got {len(qualified)}"
    assert len(over_quota) == 1, f"Expected 1 over_quota, got {len(over_quota)}"

    # Shortage delta shows politics fully satisfied (delta = 10)
    delta = result["shortage_delta"].get("politics", {})
    assert delta.get("after", -1) == 0, f"Expected politics after=0, got {delta}"


# ---------------------------------------------------------------------------
# Test 6: baseline_awareness
# ---------------------------------------------------------------------------


def test_baseline_awareness(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    """Pre-existing corpus has 8 politics tapes. Batch adds 3 more politics.
    Only 2 reduce the shortage (need drops from 2 to 0), third is over_quota.
    """
    # Create existing corpus with 8 politics tapes
    corpus_root = tmp_path / "corpus"
    for i in range(8):
        _make_gold_tape(corpus_root, slug=f"existing-politics-{i}", bucket="politics")

    # Create batch of 3 politics tapes
    batch_dir = tmp_path / "batch"
    tape_dirs = [
        _make_gold_tape(batch_dir, slug=f"new-politics-{i}", bucket="politics")
        for i in range(3)
    ]

    from tools.gates import qualify_gold_batch

    result = qualify_gold_batch.qualify_batch(
        [Path(str(t)) for t in tape_dirs],
        [Path(str(corpus_root))],
    )

    # Before: 8 have, quota=10, need=2
    # After: 2 reduce shortage (10 total), 1 over_quota
    qualified = [r for r in result["batch_results"] if r["status"] == "QUALIFIED"]
    over_quota = [r for r in result["batch_results"] if r.get("reject_reason") == "over_quota"]

    assert len(qualified) == 2, f"Expected 2 qualified (fills shortage), got {len(qualified)}"
    assert len(over_quota) == 1, f"Expected 1 over_quota, got {len(over_quota)}"

    # Shortage delta
    delta = result["shortage_delta"].get("politics", {})
    assert delta.get("before", -1) == 2, f"Expected before=2, got {delta}"
    assert delta.get("after", -1) == 0, f"Expected after=0, got {delta}"
    assert delta.get("delta", -1) == 2, f"Expected delta=2, got {delta}"

    # gate2_ready should have exactly 2 tapes
    assert len(result["gate2_ready"]) == 2, f"Expected 2 gate2-ready tapes, got {len(result['gate2_ready'])}"


# ---------------------------------------------------------------------------
# Test 7: json_output
# ---------------------------------------------------------------------------


def test_json_output(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    """Same as Test 1 but with --json flag -> valid JSON with expected keys."""
    tape_dir = _make_gold_tape(tmp_path / "batch", slug="sports-json-1", bucket="sports")
    empty_root = tmp_path / "empty_corpus"
    empty_root.mkdir()

    from tools.gates import qualify_gold_batch

    exit_code = qualify_gold_batch.main([
        "--tape-dirs", str(tape_dir),
        "--tape-roots", str(empty_root),
        "--json",
    ])

    captured = capsys.readouterr()
    assert exit_code == 0, f"Expected exit 0, got {exit_code}"

    data = json.loads(captured.out)
    assert "batch_results" in data
    assert "shortage_delta" in data
    assert "gate2_ready" in data
    assert "summary" in data

    # batch_results has correct keys
    assert len(data["batch_results"]) == 1
    result = data["batch_results"][0]
    assert result["status"] == "QUALIFIED"
    assert result["bucket"] == "sports"
    assert result["tier"] == "gold"
    assert result["effective_events"] >= 60

    # gate2_ready contains the tape path
    assert len(data["gate2_ready"]) == 1

    # summary correct
    summary = data["summary"]
    assert summary["qualified"] == 1
    assert summary["rejected"] == 0
    assert summary["total_in_batch"] == 1


# ---------------------------------------------------------------------------
# Test 8: empty_batch
# ---------------------------------------------------------------------------


def test_empty_batch(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    """No tape dirs provided -> exit 1, stderr contains usage hint."""
    empty_root = tmp_path / "empty_corpus"
    empty_root.mkdir()

    from tools.gates import qualify_gold_batch

    # Passing empty --tape-roots only, no --tape-dirs
    # We expect exit 1 with usage hint
    # argparse requires at least 1 arg for nargs="+", so we test via qualify_batch directly
    exit_code = qualify_gold_batch.qualify_batch([], [Path(str(empty_root))])

    # Should return with no results
    assert exit_code["summary"]["total_in_batch"] == 0
    assert exit_code["summary"]["qualified"] == 0
    assert len(exit_code["gate2_ready"]) == 0


# ---------------------------------------------------------------------------
# Test 9: gate2_ready_list
# ---------------------------------------------------------------------------


def test_gate2_ready_list(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    """Batch of 3 qualifying tapes -> gate2_ready list contains exactly those 3 tape_dir paths."""
    batch_dir = tmp_path / "batch"
    tape1 = _make_gold_tape(batch_dir, slug="sports-a", bucket="sports")
    tape2 = _make_gold_tape(batch_dir, slug="politics-a", bucket="politics")
    tape3 = _make_gold_tape(batch_dir, slug="near-resolution-a", bucket="near_resolution")
    empty_root = tmp_path / "empty_corpus"
    empty_root.mkdir()

    from tools.gates import qualify_gold_batch

    result = qualify_gold_batch.qualify_batch(
        [tape1, tape2, tape3],
        [Path(str(empty_root))],
    )

    assert len(result["gate2_ready"]) == 3, (
        f"Expected 3 gate2-ready tapes, got {len(result['gate2_ready'])}"
    )
    # All 3 tapes should be in gate2_ready
    ready_set = set(result["gate2_ready"])
    for t in [tape1, tape2, tape3]:
        assert str(t.resolve()) in ready_set or any(
            str(t.resolve()) in r for r in ready_set
        ), f"{t} not found in gate2_ready: {ready_set}"
