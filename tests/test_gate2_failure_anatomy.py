"""Unit tests for tools/gates/gate2_failure_anatomy.py

Covers:
  - classify_tape: all three partition classes
  - build_partition_table: grouping logic
  - build_recommendation_matrix: three options, four criteria
  - load_sweep_results: aggregate field merging (mocked filesystem)
"""
import json
import os
import sys
import tempfile
from decimal import Decimal
from pathlib import Path

import pytest

# Make sure project root is importable when tests are run from any working dir
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tools.gates.gate2_failure_anatomy import (
    build_partition_table,
    build_recommendation_matrix,
    classify_tape,
    load_sweep_results,
)


# ---------------------------------------------------------------------------
# classify_tape tests
# ---------------------------------------------------------------------------

class TestClassifyTape:
    def _make_tape(self, fills, orders, best_net_profit):
        return {
            "agg_total_fills": fills,
            "agg_total_orders": orders,
            "best_net_profit": str(best_net_profit),
            "bucket": "crypto",
            "market_slug": "test-market",
        }

    def test_classify_structural_zero_fill(self):
        tape = self._make_tape(fills=0, orders=0, best_net_profit="0")
        assert classify_tape(tape) == "structural-zero-fill"

    def test_classify_structural_zero_fill_with_zero_decisions(self):
        tape = self._make_tape(fills=0, orders=0, best_net_profit="0")
        tape["agg_total_decisions"] = 0
        assert classify_tape(tape) == "structural-zero-fill"

    def test_classify_executable_positive(self):
        tape = self._make_tape(fills=100, orders=200, best_net_profit="5.0")
        assert classify_tape(tape) == "executable-positive"

    def test_classify_executable_positive_small_pnl(self):
        tape = self._make_tape(fills=10, orders=20, best_net_profit="0.001")
        assert classify_tape(tape) == "executable-positive"

    def test_classify_executable_negative(self):
        tape = self._make_tape(fills=50, orders=100, best_net_profit="-2.0")
        assert classify_tape(tape) == "executable-negative-or-flat"

    def test_classify_negative_pnl(self):
        tape = self._make_tape(fills=50, orders=100, best_net_profit="-2.0")
        assert classify_tape(tape) == "executable-negative-or-flat"

    def test_classify_zero_pnl_with_fills(self):
        """Zero PnL with fills = executable-negative-or-flat (break-even-at-best)."""
        tape = self._make_tape(fills=209, orders=500, best_net_profit="0")
        assert classify_tape(tape) == "executable-negative-or-flat"

    def test_classify_uses_decimal_not_float(self):
        """Ensure Decimal comparison is used -- not float which can have precision issues."""
        # A value that might round differently as float
        tape = self._make_tape(fills=100, orders=200, best_net_profit="0.000000000000000001")
        assert classify_tape(tape) == "executable-positive"

    def test_classify_high_precision_negative(self):
        tape = self._make_tape(
            fills=100, orders=200, best_net_profit="-492.3431322604751185879965811"
        )
        assert classify_tape(tape) == "executable-negative-or-flat"

    def test_classify_zero_fills_nonzero_orders(self):
        """Edge case: fills=0, orders>0 -- should be structural-zero-fill because
        fills==0 and orders>0 doesn't meet the positive-fills condition."""
        tape = self._make_tape(fills=0, orders=5, best_net_profit="0")
        # fills == 0 means structural-zero-fill only if orders == 0 too.
        # If orders > 0 but fills == 0 it is still not executable-positive.
        # The implementation treats fills==0 AND orders==0 as structural.
        # With fills==0 but orders>0 -> not structural, not positive -> negative-or-flat.
        result = classify_tape(tape)
        assert result == "executable-negative-or-flat"


# ---------------------------------------------------------------------------
# build_partition_table tests
# ---------------------------------------------------------------------------

class TestBuildPartitionTable:
    def _make_tape(self, slug, bucket, fills, orders, best_pnl):
        return {
            "market_slug": slug,
            "bucket": bucket,
            "agg_total_fills": fills,
            "agg_total_orders": orders,
            "agg_scenarios_with_trades": 1 if fills > 0 else 0,
            "best_net_profit": str(best_pnl),
            "agg_worst_net_profit": str(best_pnl),
            "agg_total_decisions": 0,
        }

    def test_partition_table_groups_correctly(self):
        tapes = [
            self._make_tape("silver-tape", "near_resolution", 0, 0, "0"),
            self._make_tape("positive-tape", "crypto", 100, 200, "5.0"),
            self._make_tape("negative-tape", "politics", 50, 100, "0"),
        ]
        result = build_partition_table(tapes)

        assert "structural-zero-fill" in result
        assert "executable-positive" in result
        assert "executable-negative-or-flat" in result

        assert result["structural-zero-fill"]["count"] == 1
        assert result["executable-positive"]["count"] == 1
        assert result["executable-negative-or-flat"]["count"] == 1

    def test_partition_counts_sum_to_total(self):
        tapes = [
            self._make_tape(f"silver-{i}", "near_resolution", 0, 0, "0")
            for i in range(5)
        ] + [
            self._make_tape(f"positive-{i}", "crypto", 100, 200, f"{i+1}.0")
            for i in range(3)
        ] + [
            self._make_tape(f"negative-{i}", "politics", 50, 100, "0")
            for i in range(2)
        ]
        result = build_partition_table(tapes)
        total = sum(g["count"] for g in result.values())
        assert total == 10

    def test_partition_table_bucket_breakdown(self):
        tapes = [
            self._make_tape("crypto-1", "crypto", 100, 200, "5.0"),
            self._make_tape("crypto-2", "crypto", 80, 150, "3.0"),
            self._make_tape("silver-1", "near_resolution", 0, 0, "0"),
        ]
        result = build_partition_table(tapes)
        assert result["executable-positive"]["bucket_breakdown"].get("crypto") == 2
        assert result["structural-zero-fill"]["bucket_breakdown"].get("near_resolution") == 1

    def test_partition_table_fill_aggregation(self):
        tapes = [
            self._make_tape("crypto-1", "crypto", 100, 200, "5.0"),
            self._make_tape("crypto-2", "crypto", 80, 150, "3.0"),
        ]
        result = build_partition_table(tapes)
        assert result["executable-positive"]["total_fills"] == 180
        assert result["executable-positive"]["total_orders"] == 350


# ---------------------------------------------------------------------------
# build_recommendation_matrix tests
# ---------------------------------------------------------------------------

class TestBuildRecommendationMatrix:
    def _make_partition(self):
        return {
            "structural-zero-fill": {
                "count": 9,
                "tape_ids": [],
                "bucket_breakdown": {"near_resolution": 9},
                "total_fills": 0,
                "total_orders": 0,
                "total_decisions": 0,
                "scenarios_with_trades_sum": 0,
                "best_pnl_min": "0",
                "best_pnl_max": "0",
            },
            "executable-negative-or-flat": {
                "count": 34,
                "tape_ids": [],
                "bucket_breakdown": {
                    "politics": 10,
                    "sports": 15,
                    "new_market": 5,
                    "crypto": 4,
                },
                "total_fills": 10000,
                "total_orders": 25000,
                "total_decisions": 5000,
                "scenarios_with_trades_sum": 100,
                "best_pnl_min": "-492.34",
                "best_pnl_max": "0",
            },
            "executable-positive": {
                "count": 7,
                "tape_ids": [],
                "bucket_breakdown": {"crypto": 7},
                "total_fills": 15000,
                "total_orders": 50000,
                "total_decisions": 8000,
                "scenarios_with_trades_sum": 35,
                "best_pnl_min": "4.67",
                "best_pnl_max": "297.25",
            },
        }

    def test_recommendation_matrix_has_three_options(self):
        partition = self._make_partition()
        matrix = build_recommendation_matrix(partition)
        assert len(matrix) == 3

    def test_recommendation_matrix_option_names(self):
        partition = self._make_partition()
        matrix = build_recommendation_matrix(partition)
        names = {opt["name"] for opt in matrix}
        assert "Crypto-only corpus subset" in names
        assert "Low-frequency strategy improvement" in names
        assert "Track 2 focus (standalone)" in names

    def test_recommendation_matrix_all_four_criteria_scored(self):
        partition = self._make_partition()
        matrix = build_recommendation_matrix(partition)
        required_criteria = {
            "time_to_first_dollar",
            "gate2_closure_feasibility",
            "data_dependency",
            "strategy_risk",
        }
        for opt in matrix:
            criteria_keys = set(opt.get("criteria", {}).keys())
            assert required_criteria == criteria_keys, (
                f"Option '{opt['name']}' missing criteria: "
                f"{required_criteria - criteria_keys}"
            )

    def test_recommendation_matrix_criteria_have_score_and_rationale(self):
        partition = self._make_partition()
        matrix = build_recommendation_matrix(partition)
        for opt in matrix:
            for key, crit in opt.get("criteria", {}).items():
                assert "score" in crit, f"Missing 'score' in {opt['name']}.{key}"
                assert "rationale" in crit, f"Missing 'rationale' in {opt['name']}.{key}"
                assert crit["score"], f"Empty score in {opt['name']}.{key}"
                assert crit["rationale"], f"Empty rationale in {opt['name']}.{key}"

    def test_recommendation_matrix_has_overall_verdict(self):
        partition = self._make_partition()
        matrix = build_recommendation_matrix(partition)
        for opt in matrix:
            assert opt.get("overall_verdict"), f"Missing overall_verdict in {opt['name']}"

    def test_recommendation_matrix_crypto_option_has_high_feasibility(self):
        partition = self._make_partition()
        matrix = build_recommendation_matrix(partition)
        crypto_opt = next(
            o for o in matrix if o["name"] == "Crypto-only corpus subset"
        )
        score = crypto_opt["criteria"]["gate2_closure_feasibility"]["score"]
        assert score == "HIGH"

    def test_recommendation_matrix_strategy_improvement_has_low_feasibility(self):
        partition = self._make_partition()
        matrix = build_recommendation_matrix(partition)
        strat_opt = next(
            o for o in matrix if o["name"] == "Low-frequency strategy improvement"
        )
        score = strat_opt["criteria"]["gate2_closure_feasibility"]["score"]
        assert score == "LOW"

    def test_recommendation_matrix_track2_gate2_na(self):
        partition = self._make_partition()
        matrix = build_recommendation_matrix(partition)
        track2_opt = next(
            o for o in matrix if o["name"] == "Track 2 focus (standalone)"
        )
        score = track2_opt["criteria"]["gate2_closure_feasibility"]["score"]
        assert score == "N/A"


# ---------------------------------------------------------------------------
# load_sweep_results integration test (mocked filesystem)
# ---------------------------------------------------------------------------

class TestLoadSweepResults:
    def _write_json(self, path: Path, data: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(data, f)

    def test_load_merges_aggregate_data(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            sweeps_dir = tmpdir / "sweeps"

            # Create a minimal gate_failed.json
            gate_data = {
                "gate": "mm_sweep",
                "passed": False,
                "tapes_total": 1,
                "tapes_positive": 0,
                "pass_rate": 0.0,
                "best_scenarios": [
                    {
                        "market_slug": "test-btc-market",
                        "bucket": "crypto",
                        "best_net_profit": "10.5",
                        "positive": True,
                        "sweep_dir": f"sweeps{os.sep}btc_sweep",
                    }
                ],
            }
            gate_path = tmpdir / "gate_failed.json"
            self._write_json(gate_path, gate_data)

            # Create matching sweep_summary.json
            summary = {
                "sweep_id": "btc_sweep",
                "tape_path": "some/path/events.jsonl",
                "strategy": "market_maker_v1",
                "scenarios": [],
                "aggregate": {
                    "best_net_profit": "10.5",
                    "worst_net_profit": "-5.0",
                    "median_net_profit": "3.0",
                    "total_decisions": 100,
                    "total_orders": 500,
                    "total_fills": 150,
                    "scenarios_with_trades": 4,
                    "dominant_rejection_counts": [{"key": "adverse_selection", "count": 10}],
                },
            }
            self._write_json(sweeps_dir / "btc_sweep" / "sweep_summary.json", summary)

            result = load_sweep_results(gate_path, sweeps_dir)

        assert len(result) == 1
        t = result[0]
        assert t["agg_total_fills"] == 150
        assert t["agg_total_orders"] == 500
        assert t["agg_total_decisions"] == 100
        assert t["agg_scenarios_with_trades"] == 4
        assert t["agg_missing"] is False
        assert t["agg_worst_net_profit"] == "-5.0"

    def test_load_handles_missing_sweep_summary(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            gate_data = {
                "gate": "mm_sweep",
                "passed": False,
                "tapes_total": 1,
                "tapes_positive": 0,
                "pass_rate": 0.0,
                "best_scenarios": [
                    {
                        "market_slug": "missing-tape",
                        "bucket": "politics",
                        "best_net_profit": "0",
                        "positive": False,
                        "sweep_dir": "sweeps/nonexistent_sweep",
                    }
                ],
            }
            gate_path = tmpdir / "gate_failed.json"
            self._write_json(gate_path, gate_data)

            sweeps_dir = tmpdir / "sweeps"
            sweeps_dir.mkdir()

            result = load_sweep_results(gate_path, sweeps_dir)

        assert len(result) == 1
        t = result[0]
        assert t["agg_missing"] is True
        assert t["agg_total_fills"] == 0
        assert t["agg_total_orders"] == 0

    def test_load_supports_tapes_key_alias(self):
        """gate_failed.json may use 'tapes' instead of 'best_scenarios'."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            gate_data = {
                "gate": "mm_sweep",
                "tapes": [
                    {
                        "market_slug": "alt-market",
                        "bucket": "sports",
                        "best_net_profit": "0",
                        "positive": False,
                        "sweep_dir": "sweeps/some_sweep",
                    }
                ],
            }
            gate_path = tmpdir / "gate_failed.json"
            self._write_json(gate_path, gate_data)

            sweeps_dir = tmpdir / "sweeps"
            sweeps_dir.mkdir()

            result = load_sweep_results(gate_path, sweeps_dir)

        assert len(result) == 1
        assert result[0]["market_slug"] == "alt-market"
