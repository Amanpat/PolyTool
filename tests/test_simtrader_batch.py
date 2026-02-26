"""Offline tests for the simtrader batch command.

All network calls are mocked.  Tests validate:
- MarketPicker.auto_pick_many is called correctly
- TapeRecorder is invoked per market
- run_sweep is invoked per market
- batch_summary.json and batch_summary.csv are written
- Idempotency: existing sweep_summary.json skips market unless --rerun
- Leaderboard aggregation is stable and deterministic
- CLI integration: exit code 0 and leaderboard output
"""

from __future__ import annotations

import csv
import json
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Shared test data
# ---------------------------------------------------------------------------

YES_TOKEN_1 = "aaa1" * 15
NO_TOKEN_1 = "bbb1" * 15
YES_TOKEN_2 = "aaa2" * 15
NO_TOKEN_2 = "bbb2" * 15
SLUG_1 = "will-event-a-happen"
SLUG_2 = "will-event-b-happen"
QUESTION_1 = "Will event A happen?"
QUESTION_2 = "Will event B happen?"


def _make_resolved(slug, yes_token, no_token, question):
    from packages.polymarket.simtrader.market_picker import ResolvedMarket

    return ResolvedMarket(
        slug=slug,
        yes_token_id=yes_token,
        no_token_id=no_token,
        yes_label="Yes",
        no_label="No",
        question=question,
        mapping_tier="explicit",
    )


def _make_sweep_result(sweep_id, sweep_dir, net_profit="1.0"):
    from packages.polymarket.simtrader.sweeps.runner import SweepRunResult

    summary = {
        "sweep_id": sweep_id,
        "scenarios": [
            {
                "scenario_id": "fee0_cancel0_bid",
                "net_profit": net_profit,
            }
        ],
        "aggregate": {
            "best_net_profit": net_profit,
            "best_scenario": "fee0_cancel0_bid",
            "best_run_id": "run1",
            "median_net_profit": net_profit,
            "median_scenario": "fee0_cancel0_bid",
            "median_run_id": "run1",
            "worst_net_profit": net_profit,
            "worst_scenario": "fee0_cancel0_bid",
            "worst_run_id": "run1",
        },
    }
    manifest = {"sweep_id": sweep_id}
    sweep_dir.mkdir(parents=True, exist_ok=True)
    (sweep_dir / "sweep_manifest.json").write_text(
        json.dumps(manifest) + "\n", encoding="utf-8"
    )
    (sweep_dir / "sweep_summary.json").write_text(
        json.dumps(summary) + "\n", encoding="utf-8"
    )
    runs_dir = sweep_dir / "runs" / "fee0_cancel0_bid"
    runs_dir.mkdir(parents=True, exist_ok=True)
    run_manifest = {
        "run_id": "run1",
        "fills_count": 2,
        "decisions_count": 5,
        "run_quality": "ok",
        "warnings": [],
        "net_profit": net_profit,
        "strategy_debug": {
            "rejection_counts": {
                "no_bbo": 3,
                "edge_below_threshold": 1,
            }
        },
    }
    (runs_dir / "run_manifest.json").write_text(
        json.dumps(run_manifest) + "\n", encoding="utf-8"
    )
    return SweepRunResult(
        sweep_id=sweep_id,
        sweep_dir=sweep_dir,
        summary=summary,
        manifest=manifest,
    )


def _fake_tape_recorder(tape_dir, asset_ids, strict=False):
    """Write minimal tape without network."""
    rec = MagicMock()

    def _record(duration_seconds=None, ws_url=None):
        tape_dir.mkdir(parents=True, exist_ok=True)
        events = []
        for i, aid in enumerate(asset_ids):
            events.append(
                json.dumps(
                    {
                        "seq": i,
                        "ts_recv": float(i),
                        "asset_id": aid,
                        "event_type": "book",
                        "bids": [{"price": "0.45", "size": "100"}],
                        "asks": [{"price": "0.55", "size": "100"}],
                    }
                )
            )
        (tape_dir / "events.jsonl").write_text(
            "\n".join(events) + "\n", encoding="utf-8"
        )
        (tape_dir / "meta.json").write_text(
            json.dumps(
                {
                    "ws_url": "wss://fake",
                    "asset_ids": asset_ids,
                    "event_count": len(events),
                    "warnings": [],
                }
            )
            + "\n",
            encoding="utf-8",
        )

    rec.record = _record
    return rec


# ---------------------------------------------------------------------------
# Unit tests for BatchRunParams + run_batch
# ---------------------------------------------------------------------------


class TestRunBatch:
    """Unit tests for the batch runner (all network/IO mocked)."""

    def _run(
        self,
        tmp_path,
        num_markets=2,
        net_profits=None,
        rerun=False,
        batch_id="test-batch",
        min_events=0,
        strategy_preset="sane",
    ):
        from packages.polymarket.simtrader.batch.runner import BatchRunParams, run_batch

        resolved_markets = [
            _make_resolved(SLUG_1, YES_TOKEN_1, NO_TOKEN_1, QUESTION_1),
            _make_resolved(SLUG_2, YES_TOKEN_2, NO_TOKEN_2, QUESTION_2),
        ][:num_markets]
        net_profits = net_profits or ["1.5", "0.5"][:num_markets]

        gamma = MagicMock()
        clob = MagicMock()

        picker_mock = MagicMock()
        picker_mock.auto_pick_many.return_value = resolved_markets

        sweep_calls: list = []

        def fake_run_sweep(sweep_params, sweep_config):
            idx = len(sweep_calls)
            slug = resolved_markets[idx].slug
            sweep_id = f"sweep_{slug}"
            sweep_dir = (
                sweep_params.artifacts_root / "sweeps" / sweep_id
            )
            result = _make_sweep_result(sweep_id, sweep_dir, net_profits[idx])
            sweep_calls.append((sweep_params, sweep_config))
            return result

        params = BatchRunParams(
            num_markets=num_markets,
            preset="quick",
            strategy_preset=strategy_preset,
            duration=1.0,
            starting_cash=Decimal("1000"),
            min_events=min_events,
            artifacts_root=tmp_path / "sim",
            batch_id=batch_id,
            rerun=rerun,
        )

        with (
            patch(
                "packages.polymarket.simtrader.batch.runner.MarketPicker",
                return_value=picker_mock,
            ),
            patch(
                "packages.polymarket.simtrader.batch.runner.TapeRecorder",
                side_effect=_fake_tape_recorder,
            ),
            patch(
                "packages.polymarket.simtrader.batch.runner.run_sweep",
                side_effect=fake_run_sweep,
            ),
        ):
            result = run_batch(
                params=params,
                gamma_client=gamma,
                clob_client=clob,
                sweep_config_factory=lambda: {"scenarios": [{"name": "s1", "overrides": {}}]},
            )

        return result, sweep_calls

    def test_batch_creates_expected_artifacts(self, tmp_path):
        """batch_summary.json and batch_summary.csv are written."""
        result, _ = self._run(tmp_path)

        assert result.batch_dir.exists()
        assert (result.batch_dir / "batch_summary.json").exists()
        assert (result.batch_dir / "batch_manifest.json").exists()
        assert (result.batch_dir / "batch_summary.csv").exists()
        manifest = json.loads(
            (result.batch_dir / "batch_manifest.json").read_text(encoding="utf-8")
        )
        assert isinstance(manifest.get("seed"), int)

    def test_batch_summary_contains_both_markets(self, tmp_path):
        """batch_summary.json lists both markets with ok status."""
        result, _ = self._run(tmp_path, net_profits=["2.0", "0.5"])

        summary = json.loads(
            (result.batch_dir / "batch_summary.json").read_text(encoding="utf-8")
        )
        markets = summary["markets"]
        assert len(markets) == 2
        slugs = {m["slug"] for m in markets}
        assert SLUG_1 in slugs
        assert SLUG_2 in slugs
        for m in markets:
            assert m["status"] == "ok"
            assert m["best_net_profit"] is not None

    def test_batch_csv_has_all_rows(self, tmp_path):
        """batch_summary.csv has header + 2 data rows."""
        result, _ = self._run(tmp_path)

        csv_path = result.batch_dir / "batch_summary.csv"
        with open(csv_path, newline="", encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))
        assert len(rows) == 2
        slugs = {r["slug"] for r in rows}
        assert SLUG_1 in slugs
        assert SLUG_2 in slugs

    def test_batch_aggregate_correct(self, tmp_path):
        """Aggregate best/worst market identified correctly."""
        result, _ = self._run(tmp_path, net_profits=["3.0", "0.5"])

        summary = json.loads(
            (result.batch_dir / "batch_summary.json").read_text(encoding="utf-8")
        )
        agg = summary["aggregate"]
        assert agg["markets_ok"] == 2
        assert agg["markets_error"] == 0
        assert agg["best_market"] == SLUG_1  # 3.0 > 0.5
        assert agg["worst_market"] == SLUG_2

    def test_batch_sweep_called_per_market(self, tmp_path):
        """run_sweep is called once per market."""
        _, sweep_calls = self._run(tmp_path)
        assert len(sweep_calls) == 2

    def test_batch_loose_strategy_preset_expands_sweep_strategy_config(self, tmp_path):
        """Batch runner applies loose preset overrides to each sweep's base strategy config."""
        _, sweep_calls = self._run(tmp_path, num_markets=1, strategy_preset="loose")

        assert len(sweep_calls) == 1
        sweep_params, _sweep_cfg = sweep_calls[0]
        cfg = sweep_params.strategy_config
        assert cfg["max_size"] == 1
        assert abs(float(cfg["buffer"]) - 0.0005) < 1e-12
        assert cfg["max_notional_usdc"] == 25

    def test_batch_fills_aggregated_from_runs(self, tmp_path):
        """total_fills in summary is read from run_manifest.json files."""
        result, _ = self._run(tmp_path)

        summary = json.loads(
            (result.batch_dir / "batch_summary.json").read_text(encoding="utf-8")
        )
        # Each market's run has fills_count=2; 2 markets → 4 total
        assert summary["aggregate"]["total_fills"] == 4

    def test_batch_rejection_counts_in_market_rows(self, tmp_path):
        """dominant_rejection_key is populated from run_manifests."""
        result, _ = self._run(tmp_path)

        summary = json.loads(
            (result.batch_dir / "batch_summary.json").read_text(encoding="utf-8")
        )
        for m in summary["markets"]:
            assert m["dominant_rejection_key"] == "no_bbo"
            assert m["dominant_rejection_count"] == 3

    def test_batch_manifest_records_min_events(self, tmp_path):
        """batch_manifest.json records min_events from BatchRunParams."""
        result, _ = self._run(tmp_path, min_events=7)

        manifest = json.loads(
            (result.batch_dir / "batch_manifest.json").read_text(encoding="utf-8")
        )
        assert manifest["min_events"] == 7

    def test_batch_warns_when_tape_shorter_than_min_events(self, tmp_path, capsys):
        """Per-market quickrun-style warning is emitted when tape is below min_events."""
        self._run(tmp_path, num_markets=1, min_events=10)

        stderr = capsys.readouterr().err
        assert "tape has 2 parsed events (< --min-events 10)" in stderr

    def test_batch_time_budget_stops_launching_new_markets(self, tmp_path):
        """Elapsed time budget stops launching new markets and skips remaining rows."""
        from packages.polymarket.simtrader.batch.runner import BatchRunParams, run_batch

        resolved_markets = [
            _make_resolved(SLUG_1, YES_TOKEN_1, NO_TOKEN_1, QUESTION_1),
            _make_resolved(SLUG_2, YES_TOKEN_2, NO_TOKEN_2, QUESTION_2),
        ]

        picker_mock = MagicMock()
        picker_mock.auto_pick_many.return_value = resolved_markets
        sweep_calls: list = []

        def fake_run_sweep(sweep_params, sweep_config):
            idx = len(sweep_calls)
            slug = resolved_markets[idx].slug
            sweep_id = f"sweep_{slug}"
            sweep_dir = sweep_params.artifacts_root / "sweeps" / sweep_id
            result = _make_sweep_result(sweep_id, sweep_dir, ["1.0", "0.5"][idx])
            sweep_calls.append((sweep_params, sweep_config))
            return result

        params = BatchRunParams(
            num_markets=2,
            preset="quick",
            duration=1.0,
            starting_cash=Decimal("1000"),
            artifacts_root=tmp_path / "sim",
            batch_id="time-budget-batch",
            time_budget_seconds=10.0,
        )

        with (
            patch(
                "packages.polymarket.simtrader.batch.runner.MarketPicker",
                return_value=picker_mock,
            ),
            patch(
                "packages.polymarket.simtrader.batch.runner.TapeRecorder",
                side_effect=_fake_tape_recorder,
            ),
            patch(
                "packages.polymarket.simtrader.batch.runner.run_sweep",
                side_effect=fake_run_sweep,
            ),
            patch(
                "packages.polymarket.simtrader.batch.runner.time.monotonic",
                side_effect=[0.0, 0.0, 11.0],
            ),
        ):
            result = run_batch(
                params=params,
                gamma_client=MagicMock(),
                clob_client=MagicMock(),
                sweep_config_factory=lambda: {"scenarios": [{"name": "s1", "overrides": {}}]},
            )

        assert len(sweep_calls) == 1
        assert result.summary["aggregate"]["markets_ok"] == 1
        assert result.summary["aggregate"]["markets_skipped"] == 1
        assert result.summary["markets"][1]["status"] == "skipped"
        assert result.summary["markets"][1]["error_msg"] == "time_budget_exceeded"


# ---------------------------------------------------------------------------
# Idempotency tests
# ---------------------------------------------------------------------------


class TestBatchIdempotency:
    def test_existing_market_is_skipped(self, tmp_path):
        """Market with existing sweep_summary.json is not re-run."""
        from packages.polymarket.simtrader.batch.runner import BatchRunParams, run_batch

        resolved_markets = [
            _make_resolved(SLUG_1, YES_TOKEN_1, NO_TOKEN_1, QUESTION_1),
        ]

        # Pre-create market dir with sweep_summary.json
        market_dir = tmp_path / "sim" / "batches" / "test-idp" / "markets" / SLUG_1
        market_dir.mkdir(parents=True, exist_ok=True)
        existing_summary = {
            "sweep_id": "existing",
            "scenarios": [{"scenario_id": "s1", "net_profit": "9.99"}],
            "aggregate": {
                "best_net_profit": "9.99",
                "best_scenario": "s1",
                "median_net_profit": "9.99",
                "median_scenario": "s1",
                "worst_net_profit": "9.99",
                "worst_scenario": "s1",
            },
        }
        (market_dir / "sweep_summary.json").write_text(
            json.dumps(existing_summary) + "\n", encoding="utf-8"
        )

        picker_mock = MagicMock()
        picker_mock.auto_pick_many.return_value = resolved_markets
        sweep_called: list = [False]

        def fake_run_sweep(sweep_params, sweep_config):
            sweep_called[0] = True
            raise AssertionError("run_sweep should not have been called (idempotency)")

        params = BatchRunParams(
            num_markets=1,
            preset="quick",
            duration=1.0,
            starting_cash=Decimal("1000"),
            artifacts_root=tmp_path / "sim",
            batch_id="test-idp",
            rerun=False,  # key: do NOT rerun
        )

        with (
            patch(
                "packages.polymarket.simtrader.batch.runner.MarketPicker",
                return_value=picker_mock,
            ),
            patch(
                "packages.polymarket.simtrader.batch.runner.TapeRecorder",
                side_effect=_fake_tape_recorder,
            ),
            patch(
                "packages.polymarket.simtrader.batch.runner.run_sweep",
                side_effect=fake_run_sweep,
            ),
        ):
            result = run_batch(
                params=params,
                gamma_client=MagicMock(),
                clob_client=MagicMock(),
                sweep_config_factory=lambda: {"scenarios": [{"name": "s1", "overrides": {}}]},
            )

        assert not sweep_called[0], "run_sweep was called despite idempotency"
        summary = result.summary
        market_row = summary["markets"][0]
        assert market_row["status"] == "skipped"

    def test_rerun_flag_forces_rerun(self, tmp_path):
        """--rerun=True forces re-running even when sweep_summary.json exists."""
        from packages.polymarket.simtrader.batch.runner import BatchRunParams, run_batch

        resolved_markets = [
            _make_resolved(SLUG_1, YES_TOKEN_1, NO_TOKEN_1, QUESTION_1),
        ]

        # Pre-create market dir with sweep_summary.json
        market_dir = tmp_path / "sim" / "batches" / "test-rerun" / "markets" / SLUG_1
        market_dir.mkdir(parents=True, exist_ok=True)
        (market_dir / "sweep_summary.json").write_text(
            json.dumps({"scenarios": [], "aggregate": {}}) + "\n", encoding="utf-8"
        )

        picker_mock = MagicMock()
        picker_mock.auto_pick_many.return_value = resolved_markets
        sweep_called: list = [False]

        def fake_run_sweep(sweep_params, sweep_config):
            sweep_called[0] = True
            slug = resolved_markets[0].slug
            sweep_id = f"sweep_{slug}"
            sweep_dir = sweep_params.artifacts_root / "sweeps" / sweep_id
            return _make_sweep_result(sweep_id, sweep_dir, "2.0")

        params = BatchRunParams(
            num_markets=1,
            preset="quick",
            duration=1.0,
            starting_cash=Decimal("1000"),
            artifacts_root=tmp_path / "sim",
            batch_id="test-rerun",
            rerun=True,  # key: force rerun
        )

        with (
            patch(
                "packages.polymarket.simtrader.batch.runner.MarketPicker",
                return_value=picker_mock,
            ),
            patch(
                "packages.polymarket.simtrader.batch.runner.TapeRecorder",
                side_effect=_fake_tape_recorder,
            ),
            patch(
                "packages.polymarket.simtrader.batch.runner.run_sweep",
                side_effect=fake_run_sweep,
            ),
        ):
            run_batch(
                params=params,
                gamma_client=MagicMock(),
                clob_client=MagicMock(),
                sweep_config_factory=lambda: {"scenarios": [{"name": "s1", "overrides": {}}]},
            )

        assert sweep_called[0], "run_sweep was NOT called despite --rerun"


# ---------------------------------------------------------------------------
# Leaderboard aggregation stability tests
# ---------------------------------------------------------------------------


class TestLeaderboardAggregation:
    def test_aggregate_best_worst_stable(self, tmp_path):
        """Aggregate best/worst is deterministic given fixed inputs."""
        from packages.polymarket.simtrader.batch.runner import (
            BatchRunParams,
            _build_summary,
            _MarketRow,
        )

        rows = [
            _MarketRow(
                slug=SLUG_1, question=QUESTION_1,
                yes_token_id=YES_TOKEN_1, no_token_id=NO_TOKEN_1,
                tape_path=None, tape_events_count=10, tape_bbo_rows=10,
                yes_snapshot=True, no_snapshot=True,
                best_net_profit="5.0", median_net_profit="3.0",
                worst_net_profit="1.0", best_scenario="s1",
                total_scenarios=3, total_orders=12, total_decisions=9, total_fills=10,
                dominant_rejection_key="no_bbo", dominant_rejection_count=5,
                status="ok",
            ),
            _MarketRow(
                slug=SLUG_2, question=QUESTION_2,
                yes_token_id=YES_TOKEN_2, no_token_id=NO_TOKEN_2,
                tape_path=None, tape_events_count=15, tape_bbo_rows=15,
                yes_snapshot=True, no_snapshot=True,
                best_net_profit="-2.0", median_net_profit="-1.0",
                worst_net_profit="-5.0", best_scenario="s2",
                total_scenarios=3, total_orders=4, total_decisions=2, total_fills=3,
                dominant_rejection_key="edge_below_threshold",
                dominant_rejection_count=2,
                status="ok",
            ),
        ]

        params = BatchRunParams(num_markets=2)
        summary = _build_summary("bid-test", "2026T", params, rows)

        agg = summary["aggregate"]
        assert agg["best_market"] == SLUG_1
        assert agg["worst_market"] == SLUG_2
        assert agg["markets_ok"] == 2
        assert agg["total_fills"] == 13

    def test_aggregate_skipped_excluded_from_leaderboard(self, tmp_path):
        """Skipped markets are counted separately and not in best/worst."""
        from packages.polymarket.simtrader.batch.runner import (
            BatchRunParams,
            _build_summary,
            _MarketRow,
        )

        rows = [
            _MarketRow(
                slug=SLUG_1, question=QUESTION_1,
                yes_token_id=YES_TOKEN_1, no_token_id=NO_TOKEN_1,
                tape_path=None, tape_events_count=10, tape_bbo_rows=10,
                yes_snapshot=True, no_snapshot=True,
                best_net_profit="5.0", median_net_profit="3.0",
                worst_net_profit="1.0", best_scenario="s1",
                total_scenarios=3, total_orders=7, total_decisions=6, total_fills=8,
                dominant_rejection_key="no_bbo", dominant_rejection_count=2,
                status="ok",
            ),
            _MarketRow(
                slug=SLUG_2, question=QUESTION_2,
                yes_token_id=YES_TOKEN_2, no_token_id=NO_TOKEN_2,
                tape_path=None, tape_events_count=0, tape_bbo_rows=0,
                yes_snapshot=False, no_snapshot=False,
                best_net_profit=None, median_net_profit=None,
                worst_net_profit=None, best_scenario=None,
                total_scenarios=0, total_orders=0, total_decisions=0, total_fills=0,
                dominant_rejection_key=None, dominant_rejection_count=0,
                status="skipped",
            ),
        ]

        params = BatchRunParams(num_markets=2)
        summary = _build_summary("bid-test", "2026T", params, rows)

        agg = summary["aggregate"]
        assert agg["markets_ok"] == 1
        assert agg["markets_skipped"] == 1
        assert agg["markets_error"] == 0


# ---------------------------------------------------------------------------
# CLI integration test
# ---------------------------------------------------------------------------


class TestBatchCli:
    """End-to-end CLI batch test with all network calls mocked."""

    def test_batch_cli_exit_0_leaderboard_printed(self, tmp_path, capsys, monkeypatch):
        """CLI batch command exits 0 and prints LEADERBOARD."""
        resolved_markets = [
            _make_resolved(SLUG_1, YES_TOKEN_1, NO_TOKEN_1, QUESTION_1),
            _make_resolved(SLUG_2, YES_TOKEN_2, NO_TOKEN_2, QUESTION_2),
        ]

        picker_mock = MagicMock()
        picker_mock.auto_pick_many.return_value = resolved_markets

        sweep_call_count: list = [0]

        def fake_run_sweep(sweep_params, sweep_config):
            idx = sweep_call_count[0]
            slug = resolved_markets[idx].slug
            sweep_id = f"sweep_{slug}"
            sweep_dir = sweep_params.artifacts_root / "sweeps" / sweep_id
            result = _make_sweep_result(
                sweep_id, sweep_dir, ["2.5", "1.5"][idx]
            )
            sweep_call_count[0] += 1
            return result

        monkeypatch.setattr(
            "tools.cli.simtrader.DEFAULT_ARTIFACTS_DIR", tmp_path / "sim"
        )

        with (
            patch("packages.polymarket.gamma.GammaClient", return_value=MagicMock()),
            patch("packages.polymarket.clob.ClobClient", return_value=MagicMock()),
            patch(
                "packages.polymarket.simtrader.batch.runner.MarketPicker",
                return_value=picker_mock,
            ),
            patch(
                "packages.polymarket.simtrader.batch.runner.TapeRecorder",
                side_effect=_fake_tape_recorder,
            ),
            patch(
                "packages.polymarket.simtrader.batch.runner.run_sweep",
                side_effect=fake_run_sweep,
            ),
        ):
            from tools.cli.simtrader import main

            exit_code = main(
                [
                    "batch",
                    "--preset", "quick",
                    "--num-markets", "2",
                    "--duration", "1",
                ]
            )

        assert exit_code == 0, f"Expected exit 0 but got {exit_code}"

        captured = capsys.readouterr()
        out = captured.out

        assert "Batch complete" in out
        assert "LEADERBOARD" in out
        assert SLUG_1 in out
        assert SLUG_2 in out
        assert "Reproduce" in out
        assert "--preset quick" in out

    def test_batch_cli_liquidity_preset_strict_maps_and_enforces(
        self, tmp_path, monkeypatch
    ):
        """--liquidity preset:strict overrides depth knobs passed into BatchRunParams."""
        from packages.polymarket.simtrader.batch.runner import BatchRunResult

        captured: dict = {}

        def fake_run_batch(*, params, gamma_client, clob_client, sweep_config_factory):
            captured["params"] = params
            return BatchRunResult(
                batch_id="batch-liq-strict",
                batch_dir=tmp_path / "sim" / "batches" / "batch-liq-strict",
                summary={
                    "aggregate": {
                        "markets_ok": 0,
                        "markets_skipped": 0,
                        "markets_error": 0,
                        "total_orders": 0,
                        "total_decisions": 0,
                        "total_fills": 0,
                        "tape_events_count": 0,
                        "tape_bbo_rows": 0,
                    },
                    "markets": [],
                },
                manifest={},
            )

        monkeypatch.setattr("tools.cli.simtrader.DEFAULT_ARTIFACTS_DIR", tmp_path / "sim")

        with (
            patch("packages.polymarket.gamma.GammaClient", return_value=MagicMock()),
            patch("packages.polymarket.clob.ClobClient", return_value=MagicMock()),
            patch(
                "packages.polymarket.simtrader.batch.runner.run_batch",
                side_effect=fake_run_batch,
            ),
        ):
            from tools.cli.simtrader import main

            exit_code = main(
                [
                    "batch",
                    "--num-markets",
                    "1",
                    "--duration",
                    "1",
                    "--liquidity",
                    "preset:strict",
                    "--min-depth-size",
                    "10",
                    "--top-n-levels",
                    "1",
                ]
            )

        assert exit_code == 0
        params = captured["params"]
        assert params.min_depth_size == pytest.approx(200.0)
        assert params.top_n_levels == 5

    def test_batch_cli_quick_small_preset_expands_expected_defaults(
        self, tmp_path, monkeypatch
    ):
        """--preset quick_small applies compact defaults for local development."""
        from packages.polymarket.simtrader.batch.runner import BatchRunResult

        captured: dict = {}

        def fake_run_batch(*, params, gamma_client, clob_client, sweep_config_factory):
            captured["params"] = params
            captured["scenario_count"] = len(sweep_config_factory().get("scenarios", []))
            return BatchRunResult(
                batch_id="batch-quick-small",
                batch_dir=tmp_path / "sim" / "batches" / "batch-quick-small",
                summary={
                    "aggregate": {
                        "markets_ok": 0,
                        "markets_skipped": 0,
                        "markets_error": 0,
                        "total_orders": 0,
                        "total_decisions": 0,
                        "total_fills": 0,
                        "tape_events_count": 0,
                        "tape_bbo_rows": 0,
                    },
                    "markets": [],
                },
                manifest={},
            )

        monkeypatch.setattr("tools.cli.simtrader.DEFAULT_ARTIFACTS_DIR", tmp_path / "sim")

        with (
            patch("packages.polymarket.gamma.GammaClient", return_value=MagicMock()),
            patch("packages.polymarket.clob.ClobClient", return_value=MagicMock()),
            patch(
                "packages.polymarket.simtrader.batch.runner.run_batch",
                side_effect=fake_run_batch,
            ),
        ):
            from tools.cli.simtrader import main

            exit_code = main(
                ["batch", "--preset", "quick_small", "--strategy-preset", "loose"]
            )

        assert exit_code == 0
        params = captured["params"]
        assert params.preset == "quick_small"
        assert params.strategy_preset == "loose"
        assert params.num_markets == 3
        assert params.duration == pytest.approx(300.0)
        assert captured["scenario_count"] == 4

    def test_batch_cli_unknown_preset_returns_error(self, tmp_path, monkeypatch):
        """Unknown --preset returns exit code 1."""
        monkeypatch.setattr(
            "tools.cli.simtrader.DEFAULT_ARTIFACTS_DIR", tmp_path / "sim"
        )

        with (
            patch("packages.polymarket.gamma.GammaClient", return_value=MagicMock()),
            patch("packages.polymarket.clob.ClobClient", return_value=MagicMock()),
        ):
            from tools.cli.simtrader import main

            exit_code = main(
                [
                    "batch",
                    "--preset", "nonexistent_preset",
                    "--num-markets", "2",
                    "--duration", "1",
                ]
            )

        assert exit_code == 1

    def test_batch_cli_invalid_num_markets_returns_error(self, tmp_path, monkeypatch):
        """--num-markets 0 returns exit code 1."""
        monkeypatch.setattr(
            "tools.cli.simtrader.DEFAULT_ARTIFACTS_DIR", tmp_path / "sim"
        )

        with (
            patch("packages.polymarket.gamma.GammaClient", return_value=MagicMock()),
            patch("packages.polymarket.clob.ClobClient", return_value=MagicMock()),
        ):
            from tools.cli.simtrader import main

            exit_code = main(
                [
                    "batch",
                    "--num-markets", "0",
                    "--duration", "1",
                ]
            )

        assert exit_code == 1

    def test_batch_cli_parses_min_events_and_passes_to_params(
        self, tmp_path, monkeypatch
    ):
        """CLI accepts --min-events and wires it into BatchRunParams."""
        from packages.polymarket.simtrader.batch.runner import BatchRunResult

        captured: dict = {}

        def fake_run_batch(*, params, gamma_client, clob_client, sweep_config_factory):
            captured["params"] = params
            return BatchRunResult(
                batch_id="batch-min-events",
                batch_dir=tmp_path / "sim" / "batches" / "batch-min-events",
                summary={
                    "aggregate": {
                        "markets_ok": 0,
                        "markets_skipped": 0,
                        "markets_error": 0,
                        "total_orders": 0,
                        "total_decisions": 0,
                        "total_fills": 0,
                        "tape_events_count": 0,
                        "tape_bbo_rows": 0,
                    },
                    "markets": [],
                },
                manifest={},
            )

        monkeypatch.setattr("tools.cli.simtrader.DEFAULT_ARTIFACTS_DIR", tmp_path / "sim")

        with (
            patch("packages.polymarket.gamma.GammaClient", return_value=MagicMock()),
            patch("packages.polymarket.clob.ClobClient", return_value=MagicMock()),
            patch(
                "packages.polymarket.simtrader.batch.runner.run_batch",
                side_effect=fake_run_batch,
            ),
        ):
            from tools.cli.simtrader import main

            exit_code = main(
                [
                    "batch",
                    "--num-markets",
                    "1",
                    "--duration",
                    "1",
                    "--min-events",
                    "12",
                ]
            )

        assert exit_code == 0
        params = captured["params"]
        assert params.min_events == 12

    def test_batch_cli_parses_time_budget_and_passes_to_params(
        self, tmp_path, monkeypatch
    ):
        """CLI accepts --time-budget-seconds and wires it into BatchRunParams."""
        from packages.polymarket.simtrader.batch.runner import BatchRunResult

        captured: dict = {}

        def fake_run_batch(*, params, gamma_client, clob_client, sweep_config_factory):
            captured["params"] = params
            return BatchRunResult(
                batch_id="batch-time-budget",
                batch_dir=tmp_path / "sim" / "batches" / "batch-time-budget",
                summary={
                    "aggregate": {
                        "markets_ok": 0,
                        "markets_skipped": 0,
                        "markets_error": 0,
                        "total_orders": 0,
                        "total_decisions": 0,
                        "total_fills": 0,
                        "tape_events_count": 0,
                        "tape_bbo_rows": 0,
                    },
                    "markets": [],
                },
                manifest={},
            )

        monkeypatch.setattr("tools.cli.simtrader.DEFAULT_ARTIFACTS_DIR", tmp_path / "sim")

        with (
            patch("packages.polymarket.gamma.GammaClient", return_value=MagicMock()),
            patch("packages.polymarket.clob.ClobClient", return_value=MagicMock()),
            patch(
                "packages.polymarket.simtrader.batch.runner.run_batch",
                side_effect=fake_run_batch,
            ),
        ):
            from tools.cli.simtrader import main

            exit_code = main(
                [
                    "batch",
                    "--num-markets",
                    "1",
                    "--duration",
                    "1",
                    "--time-budget-seconds",
                    "30",
                ]
            )

        assert exit_code == 0
        params = captured["params"]
        assert params.time_budget_seconds == pytest.approx(30.0)

    def test_batch_cli_negative_min_events_returns_error(
        self, tmp_path, monkeypatch, capsys
    ):
        """--min-events must be non-negative, matching quickrun validation."""
        monkeypatch.setattr(
            "tools.cli.simtrader.DEFAULT_ARTIFACTS_DIR", tmp_path / "sim"
        )

        from tools.cli.simtrader import main

        exit_code = main(
            [
                "batch",
                "--num-markets",
                "1",
                "--duration",
                "1",
                "--min-events",
                "-1",
            ]
        )

        assert exit_code == 1
        stderr = capsys.readouterr().err
        assert "--min-events must be non-negative" in stderr

    def test_batch_cli_non_positive_time_budget_returns_error(
        self, tmp_path, monkeypatch, capsys
    ):
        """--time-budget-seconds must be positive when provided."""
        monkeypatch.setattr(
            "tools.cli.simtrader.DEFAULT_ARTIFACTS_DIR", tmp_path / "sim"
        )

        from tools.cli.simtrader import main

        exit_code = main(
            [
                "batch",
                "--num-markets",
                "1",
                "--duration",
                "1",
                "--time-budget-seconds",
                "0",
            ]
        )

        assert exit_code == 1
        stderr = capsys.readouterr().err
        assert "--time-budget-seconds must be > 0" in stderr
