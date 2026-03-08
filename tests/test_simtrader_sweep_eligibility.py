"""Tests for the pre-sweep tape eligibility check.

Covers three scenarios:
  1. Insufficient-depth tape — rejected early (no tick has enough ask size).
  2. No-edge tape          — rejected early (sum_ask never < threshold).
  3. Eligible tape         — passes and proceeds to sweep.
  4. Integration with run_sweep() — raises SweepEligibilityError before any
     scenario runs.
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest

from packages.polymarket.simtrader.sweeps.eligibility import (
    EligibilityResult,
    SweepEligibilityError,
    check_binary_arb_tape_eligibility,
    check_sweep_eligibility,
)

# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

YES_ID = "yes-token-aaaa"
NO_ID = "no-token-bbbb"

_DEFAULT_CONFIG = {
    "yes_asset_id": YES_ID,
    "no_asset_id": NO_ID,
    "max_size": 50,   # shares required per leg
    "buffer": 0.01,   # sum_ask must be < 0.99 to enter
}


def _write_tape(tmp_path: Path, events: list[dict]) -> Path:
    tape = tmp_path / "events.jsonl"
    with open(tape, "w", encoding="utf-8") as fh:
        for ev in events:
            fh.write(json.dumps(ev) + "\n")
    return tape


def _book(asset_id: str, seq: int, asks: list[dict], bids: list[dict] | None = None) -> dict:
    return {
        "parser_version": 1,
        "seq": seq,
        "ts_recv": float(seq),
        "event_type": "book",
        "asset_id": asset_id,
        "bids": bids if bids is not None else [{"price": "0.50", "size": "100"}],
        "asks": asks,
    }


def _price_change(asset_id: str, seq: int, side: str, price: str, size: str) -> dict:
    return {
        "parser_version": 1,
        "seq": seq,
        "ts_recv": float(seq),
        "event_type": "price_change",
        "asset_id": asset_id,
        "changes": [{"side": side, "price": price, "size": size}],
    }


# ---------------------------------------------------------------------------
# 1. Insufficient-depth tape
# ---------------------------------------------------------------------------


class TestInsufficientDepth:
    """Tape where ask sizes are always below max_size (50) on at least one side."""

    def _make_shallow_tape(self, tmp_path: Path) -> Path:
        """YES has depth 1.88, NO has depth 15 — both below required 50."""
        events = [
            _book(YES_ID, 0, asks=[{"price": "0.175", "size": "1.88"}]),
            _book(NO_ID, 1, asks=[{"price": "0.84", "size": "15"}]),
            # A few price changes that don't add depth
            _price_change(YES_ID, 2, "SELL", "0.175", "1.50"),
            _price_change(NO_ID, 3, "SELL", "0.84", "10"),
        ]
        return _write_tape(tmp_path, events)

    def test_result_is_not_eligible(self, tmp_path):
        tape = self._make_shallow_tape(tmp_path)
        result = check_binary_arb_tape_eligibility(tape, _DEFAULT_CONFIG)
        assert isinstance(result, EligibilityResult)
        assert result.eligible is False

    def test_reason_mentions_depth(self, tmp_path):
        tape = self._make_shallow_tape(tmp_path)
        result = check_binary_arb_tape_eligibility(tape, _DEFAULT_CONFIG)
        assert "depth" in result.reason.lower()

    def test_stats_ticks_with_depth_ok_is_zero(self, tmp_path):
        tape = self._make_shallow_tape(tmp_path)
        result = check_binary_arb_tape_eligibility(tape, _DEFAULT_CONFIG)
        assert result.stats["ticks_with_depth_ok"] == 0

    def test_stats_ticks_with_depth_and_edge_is_zero(self, tmp_path):
        tape = self._make_shallow_tape(tmp_path)
        result = check_binary_arb_tape_eligibility(tape, _DEFAULT_CONFIG)
        assert result.stats["ticks_with_depth_and_edge"] == 0

    def test_stats_events_scanned_positive(self, tmp_path):
        tape = self._make_shallow_tape(tmp_path)
        result = check_binary_arb_tape_eligibility(tape, _DEFAULT_CONFIG)
        assert result.stats["events_scanned"] > 0

    def test_check_sweep_eligibility_raises(self, tmp_path):
        tape = self._make_shallow_tape(tmp_path)
        with pytest.raises(SweepEligibilityError) as exc_info:
            check_sweep_eligibility(tape, "binary_complement_arb", _DEFAULT_CONFIG)
        assert "non-actionable" in str(exc_info.value).lower()
        assert "depth" in str(exc_info.value).lower()


# ---------------------------------------------------------------------------
# 2. No-edge tape (sufficient depth but sum_ask always >= threshold)
# ---------------------------------------------------------------------------


class TestNoEdge:
    """Tape where depth is fine but sum_ask >= 1 - buffer = 0.99 always."""

    def _make_no_edge_tape(self, tmp_path: Path) -> Path:
        """YES=0.51, NO=0.49 → sum_ask=1.00 ≥ 0.99.  Depth=200 (fine)."""
        events = [
            _book(YES_ID, 0, asks=[{"price": "0.51", "size": "200"}]),
            _book(NO_ID, 1, asks=[{"price": "0.49", "size": "200"}]),
            # Tick that maintains the same bad sum
            _price_change(YES_ID, 2, "SELL", "0.51", "100"),
            _price_change(NO_ID, 3, "SELL", "0.49", "100"),
        ]
        return _write_tape(tmp_path, events)

    def test_result_is_not_eligible(self, tmp_path):
        tape = self._make_no_edge_tape(tmp_path)
        result = check_binary_arb_tape_eligibility(tape, _DEFAULT_CONFIG)
        assert result.eligible is False

    def test_reason_mentions_edge(self, tmp_path):
        tape = self._make_no_edge_tape(tmp_path)
        result = check_binary_arb_tape_eligibility(tape, _DEFAULT_CONFIG)
        assert "edge" in result.reason.lower()

    def test_stats_depth_ok_but_no_combined_ticks(self, tmp_path):
        tape = self._make_no_edge_tape(tmp_path)
        result = check_binary_arb_tape_eligibility(tape, _DEFAULT_CONFIG)
        # Depth is fine on both sides
        assert result.stats["ticks_with_depth_ok"] > 0
        # But edge is never met
        assert result.stats["ticks_with_edge_ok"] == 0
        assert result.stats["ticks_with_depth_and_edge"] == 0

    def test_min_sum_ask_populated(self, tmp_path):
        tape = self._make_no_edge_tape(tmp_path)
        result = check_binary_arb_tape_eligibility(tape, _DEFAULT_CONFIG)
        assert result.stats["min_sum_ask_seen"] != "none"
        # The recorded minimum sum_ask should be >= threshold = 0.99
        min_sum = Decimal(result.stats["min_sum_ask_seen"])
        assert min_sum >= Decimal("0.99")

    def test_check_sweep_eligibility_raises(self, tmp_path):
        tape = self._make_no_edge_tape(tmp_path)
        with pytest.raises(SweepEligibilityError) as exc_info:
            check_sweep_eligibility(tape, "binary_complement_arb", _DEFAULT_CONFIG)
        assert "edge" in str(exc_info.value).lower()


# ---------------------------------------------------------------------------
# 3. Eligible tape
# ---------------------------------------------------------------------------


class TestEligibleTape:
    """Tape where at least one tick has sufficient depth AND positive edge."""

    def _make_eligible_tape(self, tmp_path: Path) -> Path:
        """YES=0.45 (size=100), NO=0.50 (size=100) → sum=0.95 < 0.99."""
        events = [
            _book(YES_ID, 0, asks=[{"price": "0.45", "size": "100"}]),
            _book(NO_ID, 1, asks=[{"price": "0.50", "size": "100"}]),
        ]
        return _write_tape(tmp_path, events)

    def test_result_is_eligible(self, tmp_path):
        tape = self._make_eligible_tape(tmp_path)
        result = check_binary_arb_tape_eligibility(tape, _DEFAULT_CONFIG)
        assert result.eligible is True

    def test_reason_is_empty(self, tmp_path):
        tape = self._make_eligible_tape(tmp_path)
        result = check_binary_arb_tape_eligibility(tape, _DEFAULT_CONFIG)
        assert result.reason == ""

    def test_stats_ticks_with_depth_and_edge_positive(self, tmp_path):
        tape = self._make_eligible_tape(tmp_path)
        result = check_binary_arb_tape_eligibility(tape, _DEFAULT_CONFIG)
        assert result.stats["ticks_with_depth_and_edge"] > 0

    def test_check_sweep_eligibility_does_not_raise(self, tmp_path):
        tape = self._make_eligible_tape(tmp_path)
        # Should not raise
        check_sweep_eligibility(tape, "binary_complement_arb", _DEFAULT_CONFIG)

    def test_eligible_with_large_buffer(self, tmp_path):
        """Buffer=0.10 → threshold=0.90; sum=0.95 is no longer eligible."""
        config = dict(_DEFAULT_CONFIG, buffer=0.10)
        tape = self._make_eligible_tape(tmp_path)
        result = check_binary_arb_tape_eligibility(tape, config)
        assert result.eligible is False

    def test_eligible_boundary_exactly_at_threshold_is_ineligible(self, tmp_path):
        """sum_ask == threshold (not strictly less) → ineligible."""
        # YES=0.49, NO=0.50 → sum=0.99 == threshold(0.99) → not eligible
        events = [
            _book(YES_ID, 0, asks=[{"price": "0.49", "size": "100"}]),
            _book(NO_ID, 1, asks=[{"price": "0.50", "size": "100"}]),
        ]
        tape = _write_tape(tmp_path, events)
        result = check_binary_arb_tape_eligibility(tape, _DEFAULT_CONFIG)
        assert result.eligible is False

    def test_stats_required_depth_and_edge_in_stats(self, tmp_path):
        tape = self._make_eligible_tape(tmp_path)
        result = check_binary_arb_tape_eligibility(tape, _DEFAULT_CONFIG)
        assert "required_depth" in result.stats
        assert "required_edge_threshold" in result.stats
        assert result.stats["required_depth"] == "50"
        assert result.stats["required_edge_threshold"] == "0.99"


# ---------------------------------------------------------------------------
# 4. Non-binary_complement_arb strategies are not checked
# ---------------------------------------------------------------------------


class TestOtherStrategiesSkipped:
    def test_unknown_strategy_is_always_eligible(self, tmp_path):
        """Non-arb strategies are not checked — eligibility returns without raising."""
        # An empty tape that would fail arb eligibility
        tape = _write_tape(tmp_path, [])
        # Should not raise
        check_sweep_eligibility(tape, "copy_wallet_replay", {"max_size": 50})

    def test_eligible_for_any_strategy_name(self, tmp_path):
        """check_sweep_eligibility is a no-op for unknown strategy names."""
        tape = _write_tape(tmp_path, [])
        check_sweep_eligibility(tape, "market_maker_v0", {})


# ---------------------------------------------------------------------------
# 5. Integration: run_sweep raises SweepEligibilityError before any scenario
# ---------------------------------------------------------------------------


class TestRunSweepIntegration:
    """Verify run_sweep() raises SweepEligibilityError on an ineligible tape."""

    def _minimal_sweep_config(self) -> dict:
        return {
            "scenarios": [
                {"name": "fee0", "overrides": {"fee_rate_bps": 0}},
            ]
        }

    def _shallow_tape(self, tmp_path: Path) -> Path:
        """Shallow tape: sum_ask=1.00, depth=1 → fails both checks."""
        events = [
            _book(YES_ID, 0, asks=[{"price": "0.51", "size": "1"}]),
            _book(NO_ID, 1, asks=[{"price": "0.49", "size": "1"}]),
        ]
        return _write_tape(tmp_path, events)

    def _eligible_tape(self, tmp_path: Path) -> Path:
        """Eligible tape: YES=0.45/100, NO=0.50/100."""
        events = [
            _book(YES_ID, 0, asks=[{"price": "0.45", "size": "100"}]),
            _book(NO_ID, 1, asks=[{"price": "0.50", "size": "100"}]),
        ]
        return _write_tape(tmp_path, events)

    def test_run_sweep_raises_on_ineligible_tape(self, tmp_path):
        from packages.polymarket.simtrader.sweeps.runner import (
            SweepRunParams,
            run_sweep,
        )

        tape = self._shallow_tape(tmp_path)
        strategy_config = dict(_DEFAULT_CONFIG)

        with pytest.raises(SweepEligibilityError):
            run_sweep(
                SweepRunParams(
                    events_path=tape,
                    strategy_name="binary_complement_arb",
                    strategy_config=strategy_config,
                    starting_cash=Decimal("1000"),
                    asset_id=YES_ID,
                    artifacts_root=tmp_path / "artifacts",
                ),
                sweep_config=self._minimal_sweep_config(),
            )

    def test_run_sweep_no_scenario_dirs_written_on_eligibility_failure(self, tmp_path):
        """No run directories should be created if eligibility fails."""
        from packages.polymarket.simtrader.sweeps.runner import (
            SweepRunParams,
            run_sweep,
        )

        tape = self._shallow_tape(tmp_path)
        artifacts = tmp_path / "artifacts"

        with pytest.raises(SweepEligibilityError):
            run_sweep(
                SweepRunParams(
                    events_path=tape,
                    strategy_name="binary_complement_arb",
                    strategy_config=dict(_DEFAULT_CONFIG),
                    starting_cash=Decimal("1000"),
                    asset_id=YES_ID,
                    artifacts_root=artifacts,
                ),
                sweep_config=self._minimal_sweep_config(),
            )

        # No sweep directory should have been created.
        sweep_root = artifacts / "sweeps"
        assert not sweep_root.exists() or not any(sweep_root.iterdir()), (
            "Sweep directory should not be created when eligibility check fails"
        )

    def test_run_sweep_proceeds_on_eligible_tape(self, tmp_path):
        """run_sweep() completes normally when tape is eligible."""
        from packages.polymarket.simtrader.sweeps.runner import (
            SweepRunParams,
            SweepRunResult,
            run_sweep,
        )

        tape = self._eligible_tape(tmp_path)

        result = run_sweep(
            SweepRunParams(
                events_path=tape,
                strategy_name="binary_complement_arb",
                strategy_config=dict(_DEFAULT_CONFIG),
                starting_cash=Decimal("1000"),
                asset_id=YES_ID,
                artifacts_root=tmp_path / "artifacts",
            ),
            sweep_config=self._minimal_sweep_config(),
        )

        assert isinstance(result, SweepRunResult)
        assert result.sweep_dir.exists()


# ---------------------------------------------------------------------------
# 6. Miscellaneous edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_empty_tape_is_ineligible(self, tmp_path):
        tape = _write_tape(tmp_path, [])
        result = check_binary_arb_tape_eligibility(tape, _DEFAULT_CONFIG)
        assert result.eligible is False

    def test_tape_with_only_last_trade_price_events_is_ineligible(self, tmp_path):
        events = [
            {
                "parser_version": 1,
                "seq": 0,
                "ts_recv": 0.0,
                "event_type": "last_trade_price",
                "asset_id": YES_ID,
                "price": "0.45",
            }
        ]
        tape = _write_tape(tmp_path, events)
        result = check_binary_arb_tape_eligibility(tape, _DEFAULT_CONFIG)
        assert result.eligible is False
        assert result.stats["ticks_with_both_bbo"] == 0

    def test_only_yes_book_no_no_book_is_ineligible(self, tmp_path):
        """If NO book is absent, no combined check can pass."""
        events = [
            _book(YES_ID, 0, asks=[{"price": "0.45", "size": "100"}]),
        ]
        tape = _write_tape(tmp_path, events)
        result = check_binary_arb_tape_eligibility(tape, _DEFAULT_CONFIG)
        assert result.eligible is False

    def test_modern_batched_price_change_counted(self, tmp_path):
        """Modern price_changes[] format is handled correctly."""
        events = [
            _book(YES_ID, 0, asks=[{"price": "0.45", "size": "100"}]),
            _book(NO_ID, 1, asks=[{"price": "0.50", "size": "100"}]),
            {
                "parser_version": 1,
                "seq": 2,
                "ts_recv": 2.0,
                "event_type": "price_change",
                "price_changes": [
                    {"asset_id": YES_ID, "side": "SELL", "price": "0.45", "size": "80"},
                    {"asset_id": NO_ID, "side": "SELL", "price": "0.50", "size": "80"},
                ],
            },
        ]
        tape = _write_tape(tmp_path, events)
        result = check_binary_arb_tape_eligibility(tape, _DEFAULT_CONFIG)
        assert result.eligible is True
        assert result.stats["events_scanned"] > 0

    def test_non_existent_tape_returns_ineligible(self, tmp_path):
        tape = tmp_path / "does_not_exist.jsonl"
        result = check_binary_arb_tape_eligibility(tape, _DEFAULT_CONFIG)
        assert result.eligible is False
        assert "could not read" in result.reason

    def test_min_yes_ask_size_populated_in_stats(self, tmp_path):
        """Stats always report the minimum ask sizes seen."""
        events = [
            _book(YES_ID, 0, asks=[{"price": "0.45", "size": "30"}]),  # below max_size
            _book(NO_ID, 1, asks=[{"price": "0.50", "size": "200"}]),
        ]
        tape = _write_tape(tmp_path, events)
        result = check_binary_arb_tape_eligibility(tape, _DEFAULT_CONFIG)
        assert result.stats["min_yes_ask_size_seen"] == "30"
        assert result.stats["min_no_ask_size_seen"] == "200"
