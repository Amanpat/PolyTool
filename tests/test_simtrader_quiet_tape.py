"""Tests for the quiet-tape warning in simtrader run."""

from __future__ import annotations

import json
import sys
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from tools.cli.simtrader import DEFAULT_MIN_EVENTS, _QUIET_TAPE_MSG


def _make_tape(tmp_path: Path, event_count: int = 10) -> Path:
    """Create a minimal tape directory with meta.json and events.jsonl."""
    tape_dir = tmp_path / "tape"
    tape_dir.mkdir()
    meta = {"event_count": event_count}
    (tape_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    lines = [json.dumps({"seq": i, "event_type": "price_change"}) for i in range(event_count)]
    (tape_dir / "events.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return tape_dir / "events.jsonl"


def test_quiet_tape_warning_triggered(tmp_path: Path) -> None:
    """A tape with event_count < DEFAULT_MIN_EVENTS should produce a warning on stderr."""
    events_path = _make_tape(tmp_path, event_count=10)

    # Build a minimal args namespace that _run() expects.
    args = SimpleNamespace(
        tape=str(events_path),
        strategy="copy_wallet_replay",
        strategy_preset="sane",
        strategy_config_json=None,
        strategy_config_file=None,
        asset_id=None,
        yes_asset_id=None,
        no_asset_id=None,
        starting_cash="1000",
        fee_rate_bps=None,
        mark_method="mid",
        run_id="test_quiet",
        latency_ticks=0,
        cancel_latency_ticks=0,
        strict=False,
        allow_degraded=False,
        min_events=DEFAULT_MIN_EVENTS,
    )

    stderr_buf = StringIO()

    # We only care about the warning printed *before* run_strategy is called,
    # so we patch run_strategy to avoid needing a real engine.
    with (
        patch("packages.polymarket.simtrader.strategy.facade.run_strategy", side_effect=RuntimeError("stop")),
        patch("sys.stderr", stderr_buf),
    ):
        from tools.cli.simtrader import _run

        _run(args)  # return code is irrelevant here

    captured = stderr_buf.getvalue()
    expected_msg = _QUIET_TAPE_MSG.format(count=10)
    assert expected_msg in captured, f"Expected quiet-tape warning in stderr, got:\n{captured}"


def test_quiet_tape_warning_not_triggered_when_enough_events(tmp_path: Path) -> None:
    """A tape with event_count >= min_events should NOT produce a warning."""
    events_path = _make_tape(tmp_path, event_count=100)

    args = SimpleNamespace(
        tape=str(events_path),
        strategy="copy_wallet_replay",
        strategy_preset="sane",
        strategy_config_json=None,
        strategy_config_file=None,
        asset_id=None,
        yes_asset_id=None,
        no_asset_id=None,
        starting_cash="1000",
        fee_rate_bps=None,
        mark_method="mid",
        run_id="test_not_quiet",
        latency_ticks=0,
        cancel_latency_ticks=0,
        strict=False,
        allow_degraded=False,
        min_events=DEFAULT_MIN_EVENTS,
    )

    stderr_buf = StringIO()

    with (
        patch("packages.polymarket.simtrader.strategy.facade.run_strategy", side_effect=RuntimeError("stop")),
        patch("sys.stderr", stderr_buf),
    ):
        from tools.cli.simtrader import _run

        _run(args)

    captured = stderr_buf.getvalue()
    assert "tape is quiet" not in captured.lower(), (
        f"Unexpected quiet-tape warning in stderr:\n{captured}"
    )
