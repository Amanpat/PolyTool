"""
test_gold_capture_hardening.py -- Deterministic tests for the Gold tape capture
path fix and post-capture tape validation logic.

Covers:
- Canonical shadow tape path (regression guard)
- Tape validator BLOCKED cases (missing file, price-only, empty)
- Tape validator PASS cases (L2 book present, binary tape)
- Tape validator WARN cases (low event count, missing watch_meta)
- Operator output actionability (reason contains useful failure mode text)
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from packages.polymarket.simtrader.tape_validator import (
    TapeValidationResult,
    validate_captured_tape,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_events(tape_dir: Path, events: list[dict]) -> Path:
    """Write events as JSONL to tape_dir/events.jsonl."""
    tape_dir.mkdir(parents=True, exist_ok=True)
    events_path = tape_dir / "events.jsonl"
    with open(events_path, "w", encoding="utf-8") as fh:
        for event in events:
            fh.write(json.dumps(event) + "\n")
    return events_path


def _write_meta(tape_dir: Path) -> None:
    (tape_dir / "meta.json").write_text(json.dumps({"total_events": 60}), encoding="utf-8")


def _write_watch_meta(tape_dir: Path) -> None:
    (tape_dir / "watch_meta.json").write_text(
        json.dumps({"bucket": "sports", "yes_asset_id": "AAA"}), encoding="utf-8"
    )


# ---------------------------------------------------------------------------
# TestCanonicalShadowPath
# ---------------------------------------------------------------------------


class TestCanonicalShadowPath:
    def test_shadow_tape_dir_uses_canonical_path(self):
        """DEFAULT_SHADOW_TAPE_DIR must point to artifacts/tapes/shadow exactly."""
        from tools.cli.simtrader import DEFAULT_SHADOW_TAPE_DIR

        assert DEFAULT_SHADOW_TAPE_DIR == Path("artifacts/tapes/shadow"), (
            f"Expected Path('artifacts/tapes/shadow') but got {DEFAULT_SHADOW_TAPE_DIR!r}. "
            "This constant controls where shadow tapes are written. "
            "Changing it breaks corpus_audit visibility."
        )

    def test_shadow_tape_dir_under_corpus_audit_roots(self):
        """artifacts/tapes/shadow must be discoverable by default corpus_audit scan."""
        from tools.cli.simtrader import DEFAULT_SHADOW_TAPE_DIR
        from tools.gates.corpus_audit import DEFAULT_TAPE_ROOTS

        shadow_str = str(DEFAULT_SHADOW_TAPE_DIR).replace("\\", "/")
        # At least one corpus_audit root must be a prefix of the shadow tape dir
        found = any(
            shadow_str.startswith(root.replace("\\", "/"))
            for root in DEFAULT_TAPE_ROOTS
        )
        assert found, (
            f"DEFAULT_SHADOW_TAPE_DIR ({shadow_str!r}) is not under any of "
            f"corpus_audit's DEFAULT_TAPE_ROOTS: {DEFAULT_TAPE_ROOTS}. "
            "Shadow tapes will be invisible to corpus audit."
        )


# ---------------------------------------------------------------------------
# TestTapeValidatorBlocked
# ---------------------------------------------------------------------------


class TestTapeValidatorBlocked:
    def test_blocked_no_events_file(self, tmp_path):
        """Tape dir with no events.jsonl returns BLOCKED."""
        tape_dir = tmp_path / "tape_no_events"
        tape_dir.mkdir()
        # Do NOT create events.jsonl

        result = validate_captured_tape(tape_dir)

        assert isinstance(result, TapeValidationResult)
        assert result.verdict == "BLOCKED"
        assert "no events.jsonl" in result.reason
        assert result.events_total == 0
        assert result.effective_events == 0

    def test_blocked_price_only_tape(self, tmp_path):
        """Tape with only price_2min_guide events (no 'book') returns BLOCKED."""
        tape_dir = tmp_path / "tape_price_only"
        events = [
            {"event_type": "price_2min_guide", "asset_id": "AAA", "seq": i, "price": 0.5}
            for i in range(60)
        ]
        _write_events(tape_dir, events)

        result = validate_captured_tape(tape_dir)

        assert result.verdict == "BLOCKED"
        assert result.has_l2_book is False
        assert "price-only" in result.reason
        assert "book_not_initialized" in result.reason
        assert result.events_total == 60

    def test_blocked_empty_events_file(self, tmp_path):
        """Empty events.jsonl (0 bytes) returns BLOCKED."""
        tape_dir = tmp_path / "tape_empty"
        tape_dir.mkdir(parents=True, exist_ok=True)
        (tape_dir / "events.jsonl").write_text("", encoding="utf-8")

        result = validate_captured_tape(tape_dir)

        assert result.verdict == "BLOCKED"
        assert result.events_total == 0


# ---------------------------------------------------------------------------
# TestTapeValidatorPass
# ---------------------------------------------------------------------------


class TestTapeValidatorPass:
    def test_pass_gold_tape_with_l2(self, tmp_path):
        """Gold tape with L2 book snapshot and 60 events returns PASS."""
        tape_dir = tmp_path / "tape_gold"
        events = [
            {
                "event_type": "book",
                "asset_id": "AAA",
                "bids": [{"price": "0.49", "size": "100"}],
                "asks": [{"price": "0.51", "size": "100"}],
                "seq": 0,
            }
        ] + [
            {"event_type": "price_change", "asset_id": "AAA", "seq": i + 1, "price": 0.5}
            for i in range(59)
        ]
        _write_events(tape_dir, events)
        _write_meta(tape_dir)
        _write_watch_meta(tape_dir)

        result = validate_captured_tape(tape_dir, min_effective_events=50)

        assert result.verdict == "PASS"
        assert result.has_l2_book is True
        assert result.effective_events == 60
        assert result.asset_count == 1
        assert result.has_meta_json is True
        assert result.has_watch_meta is True

    def test_pass_binary_tape_effective_events(self, tmp_path):
        """Binary market tape (2 assets, 120 events) computes effective_events ~60."""
        tape_dir = tmp_path / "tape_binary"
        events: list[dict] = []
        # One book event per asset
        events.append(
            {"event_type": "book", "asset_id": "AAA", "bids": [], "asks": [], "seq": 0}
        )
        events.append(
            {"event_type": "book", "asset_id": "BBB", "bids": [], "asks": [], "seq": 1}
        )
        # 118 price_change events alternating between assets
        for i in range(118):
            asset = "AAA" if i % 2 == 0 else "BBB"
            events.append(
                {"event_type": "price_change", "asset_id": asset, "seq": i + 2, "price": 0.5}
            )
        _write_events(tape_dir, events)
        _write_watch_meta(tape_dir)

        result = validate_captured_tape(tape_dir, min_effective_events=50)

        # 120 total events / 2 assets = 60 effective
        assert result.events_total == 120
        assert result.asset_count == 2
        assert result.effective_events == 60
        assert result.verdict == "PASS"
        assert result.has_l2_book is True


# ---------------------------------------------------------------------------
# TestTapeValidatorWarn
# ---------------------------------------------------------------------------


class TestTapeValidatorWarn:
    def test_warn_low_event_count(self, tmp_path):
        """Tape with 30 events (including book) returns WARN for low count."""
        tape_dir = tmp_path / "tape_low_count"
        events = [
            {"event_type": "book", "asset_id": "AAA", "bids": [], "asks": [], "seq": 0}
        ] + [
            {"event_type": "price_change", "asset_id": "AAA", "seq": i + 1, "price": 0.5}
            for i in range(29)
        ]
        _write_events(tape_dir, events)
        _write_watch_meta(tape_dir)

        result = validate_captured_tape(tape_dir, min_effective_events=50)

        assert result.verdict == "WARN"
        assert "need >= 50" in result.reason
        assert result.has_l2_book is True
        assert result.effective_events == 30

    def test_warn_missing_watch_meta(self, tmp_path):
        """Tape with enough events and L2 book but no watch_meta.json returns WARN."""
        tape_dir = tmp_path / "tape_no_watch_meta"
        events = [
            {"event_type": "book", "asset_id": "AAA", "bids": [], "asks": [], "seq": 0}
        ] + [
            {"event_type": "price_change", "asset_id": "AAA", "seq": i + 1, "price": 0.5}
            for i in range(59)
        ]
        _write_events(tape_dir, events)
        _write_meta(tape_dir)
        # Deliberately do NOT create watch_meta.json

        result = validate_captured_tape(tape_dir, min_effective_events=50)

        assert result.verdict == "WARN"
        assert "missing watch_meta.json" in result.reason
        assert result.has_watch_meta is False
        assert result.has_l2_book is True


# ---------------------------------------------------------------------------
# TestOperatorOutput
# ---------------------------------------------------------------------------


class TestOperatorOutput:
    def test_verdict_block_contains_actionable_message(self, tmp_path):
        """BLOCKED reason must contain a greppable failure mode string."""
        # Price-only tape case
        tape_dir = tmp_path / "tape_price_only_op"
        events = [
            {"event_type": "price_2min_guide", "asset_id": "AAA", "seq": i}
            for i in range(40)
        ]
        _write_events(tape_dir, events)

        result = validate_captured_tape(tape_dir)

        assert result.verdict == "BLOCKED"
        # Operator must be able to grep output for the failure mode without reading code
        assert any(
            phrase in result.reason
            for phrase in ("book_not_initialized", "price-only", "no events.jsonl")
        ), (
            f"BLOCKED reason lacks actionable failure mode text: {result.reason!r}. "
            "Operator must be able to grep the output to understand why the tape is blocked."
        )
