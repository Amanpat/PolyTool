"""Tests for SimTrader scenario sweeps."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path


ASSET_ID = "test-asset-001"

TAPE_EVENTS = [
    {
        "parser_version": 1,
        "seq": 0,
        "ts_recv": 0.0,
        "event_type": "book",
        "asset_id": ASSET_ID,
        "bids": [{"price": "0.40", "size": "500"}],
        "asks": [{"price": "0.45", "size": "300"}],
    },
    {
        "parser_version": 1,
        "seq": 1,
        "ts_recv": 1.0,
        "event_type": "price_change",
        "asset_id": ASSET_ID,
        "changes": [{"side": "SELL", "price": "0.45", "size": "200"}],
    },
    {
        "parser_version": 1,
        "seq": 2,
        "ts_recv": 2.0,
        "event_type": "price_change",
        "asset_id": ASSET_ID,
        "changes": [{"side": "BUY", "price": "0.41", "size": "100"}],
    },
    {
        "parser_version": 1,
        "seq": 3,
        "ts_recv": 3.0,
        "event_type": "price_change",
        "asset_id": ASSET_ID,
        "changes": [{"side": "SELL", "price": "0.45", "size": "100"}],
    },
    {
        "parser_version": 1,
        "seq": 4,
        "ts_recv": 4.0,
        "event_type": "price_change",
        "asset_id": ASSET_ID,
        "changes": [{"side": "BUY", "price": "0.42", "size": "50"}],
    },
    {
        "parser_version": 1,
        "seq": 5,
        "ts_recv": 5.0,
        "event_type": "price_change",
        "asset_id": ASSET_ID,
        "changes": [{"side": "SELL", "price": "0.46", "size": "150"}],
    },
]


def _write_tape(path: Path) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        for event in TAPE_EVENTS:
            fh.write(json.dumps(event) + "\n")


def _write_trades(path: Path) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(
            json.dumps(
                {
                    "seq": 2,
                    "side": "BUY",
                    "limit_price": "0.50",
                    "size": "100",
                    "trade_id": "t1",
                }
            )
            + "\n"
        )


def _run_sweep_cli(
    tape_path: Path,
    trades_path: Path,
    sweep_config: dict,
    *,
    sweep_id: str | None = None,
) -> int:
    from tools.cli.simtrader import main as simtrader_main

    strategy_cfg = json.dumps(
        {
            "trades_path": str(trades_path),
            "signal_delay_ticks": 0,
        }
    )
    argv = [
        "sweep",
        "--tape",
        str(tape_path),
        "--strategy",
        "copy_wallet_replay",
        "--strategy-config",
        strategy_cfg,
        "--starting-cash",
        "1000",
        "--fee-rate-bps",
        "100",
        "--mark-method",
        "bid",
        "--sweep-config",
        json.dumps(sweep_config),
    ]
    if sweep_id:
        argv.extend(["--sweep-id", sweep_id])
    return simtrader_main(argv)


def _load_sweep_summary(sweep_id: str) -> tuple[Path, dict]:
    sweeps_root = Path("artifacts/simtrader/sweeps")
    summary_path = sweeps_root / sweep_id / "sweep_summary.json"
    assert summary_path.exists(), "sweep_summary.json was not created"
    return summary_path, json.loads(summary_path.read_text(encoding="utf-8"))


def _decision_seq(run_dir: Path) -> int:
    decisions_path = run_dir / "decisions.jsonl"
    rows = [
        json.loads(line)
        for line in decisions_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert rows, f"Expected decisions in {decisions_path}"
    return int(rows[0]["seq"])


def test_sweep_determinism_and_stable_order(tmp_path: Path) -> None:
    tape_path = tmp_path / "events.jsonl"
    trades_path = tmp_path / "trades.jsonl"
    _write_tape(tape_path)
    _write_trades(trades_path)

    sweep_config = {
        "scenarios": [
            {"name": "fees_high", "overrides": {"fee_rate_bps": 300}},
            {"name": "base", "overrides": {}},
            {
                "name": "delay_more",
                "overrides": {"strategy_config": {"signal_delay_ticks": 2}},
            },
        ]
    }

    sweep_id = "determinism-sweep"
    rc1 = _run_sweep_cli(tape_path, trades_path, sweep_config, sweep_id=sweep_id)
    assert rc1 == 0
    summary_path, summary_a = _load_sweep_summary(sweep_id)
    summary_text_a = summary_path.read_text(encoding="utf-8")

    rc2 = _run_sweep_cli(tape_path, trades_path, sweep_config, sweep_id=sweep_id)
    assert rc2 == 0
    summary_text_b = summary_path.read_text(encoding="utf-8")

    assert summary_text_a == summary_text_b, (
        "sweep_summary.json should be byte-identical across identical sweep runs"
    )

    scenario_names = [row["scenario_name"] for row in summary_a["scenarios"]]
    assert scenario_names == ["base", "delay_more", "fees_high"]

    required_artifacts = {
        "best_bid_ask.jsonl",
        "orders.jsonl",
        "fills.jsonl",
        "ledger.jsonl",
        "equity_curve.jsonl",
        "summary.json",
        "decisions.jsonl",
        "run_manifest.json",
        "meta.json",
    }
    for row in summary_a["scenarios"]:
        run_dir = Path(row["artifact_path"])
        for filename in required_artifacts:
            assert (run_dir / filename).exists(), f"Missing {filename} in {run_dir}"


def test_sweep_fee_override_changes_fees_and_net_profit(tmp_path: Path) -> None:
    tape_path = tmp_path / "events.jsonl"
    trades_path = tmp_path / "trades.jsonl"
    _write_tape(tape_path)
    _write_trades(trades_path)

    sweep_config = {
        "scenarios": [
            {"name": "base", "overrides": {}},
            {"name": "fees_high", "overrides": {"fee_rate_bps": 300}},
        ]
    }
    sweep_id = "fees-override-sweep"
    rc = _run_sweep_cli(tape_path, trades_path, sweep_config, sweep_id=sweep_id)
    assert rc == 0

    _, summary = _load_sweep_summary(sweep_id)
    by_name = {row["scenario_name"]: row for row in summary["scenarios"]}
    base = by_name["base"]
    fees_high = by_name["fees_high"]

    assert Decimal(fees_high["total_fees"]) > Decimal(base["total_fees"])
    assert Decimal(fees_high["net_profit"]) < Decimal(base["net_profit"])


def test_sweep_strategy_override_patches_strategy_config(tmp_path: Path) -> None:
    tape_path = tmp_path / "events.jsonl"
    trades_path = tmp_path / "trades.jsonl"
    _write_tape(tape_path)
    _write_trades(trades_path)

    sweep_config = {
        "scenarios": [
            {"name": "base", "overrides": {}},
            {
                "name": "delay_more",
                "overrides": {"strategy_config": {"signal_delay_ticks": 2}},
            },
        ]
    }
    sweep_id = "strategy-override-sweep"
    rc = _run_sweep_cli(tape_path, trades_path, sweep_config, sweep_id=sweep_id)
    assert rc == 0

    _, summary = _load_sweep_summary(sweep_id)
    by_name = {row["scenario_name"]: row for row in summary["scenarios"]}
    base_dir = Path(by_name["base"]["artifact_path"])
    delayed_dir = Path(by_name["delay_more"]["artifact_path"])

    base_seq = _decision_seq(base_dir)
    delayed_seq = _decision_seq(delayed_dir)

    assert base_seq == 2
    assert delayed_seq == 4
    assert delayed_seq > base_seq


def test_sweep_summary_activity_and_rejection_aggregates_offline(
    tmp_path: Path, monkeypatch
) -> None:
    from packages.polymarket.simtrader.strategy.facade import StrategyRunResult
    from packages.polymarket.simtrader.sweeps.runner import SweepRunParams, run_sweep

    tape_path = tmp_path / "events.jsonl"
    tape_path.write_text("{}\n", encoding="utf-8")

    scenario_data = {
        "alpha": {
            "net_profit": "1.0",
            "decisions_count": 10,
            "orders_count": 12,
            "fills_count": 3,
            "rejection_counts": {
                "no_bbo": 5,
                "edge_below_threshold": 2,
                "waiting_on_attempt": 1,
            },
        },
        "beta": {
            "net_profit": "-1.0",
            "decisions_count": 4,
            "orders_count": 4,
            "fills_count": 0,
            "rejection_counts": {
                "no_bbo": 1,
                "stale_or_missing_snapshot": 7,
            },
        },
        "gamma": {
            "net_profit": "0.5",
            "decisions_count": 8,
            "orders_count": 9,
            "fills_count": 2,
            "rejection_counts": {
                "edge_below_threshold": 6,
                "fee_kills_edge": 3,
                "insufficient_depth_yes": 3,
            },
        },
    }

    def fake_run_strategy(params):
        scenario_id = params.run_dir.name
        payload = scenario_data[scenario_id]
        params.run_dir.mkdir(parents=True, exist_ok=True)

        orders_count = int(payload["orders_count"])
        (params.run_dir / "orders.jsonl").write_text(
            "".join("{}\n" for _ in range(orders_count)),
            encoding="utf-8",
        )
        (params.run_dir / "run_manifest.json").write_text(
            json.dumps(
                {
                    "run_id": scenario_id,
                    "decisions_count": payload["decisions_count"],
                    "fills_count": payload["fills_count"],
                    "strategy_debug": {
                        "rejection_counts": payload["rejection_counts"]
                    },
                }
            )
            + "\n",
            encoding="utf-8",
        )

        return StrategyRunResult(
            run_id=scenario_id,
            run_dir=params.run_dir,
            summary={},
            metrics={
                "net_profit": payload["net_profit"],
                "realized_pnl": "0",
                "unrealized_pnl": "0",
                "total_fees": "0",
            },
            warnings_count=0,
        )

    monkeypatch.setattr(
        "packages.polymarket.simtrader.sweeps.runner.run_strategy",
        fake_run_strategy,
    )

    result = run_sweep(
        SweepRunParams(
            events_path=tape_path,
            strategy_name="copy_wallet_replay",
            strategy_config={},
            starting_cash=Decimal("1000"),
            sweep_id="offline-aggregate-sweep",
            artifacts_root=tmp_path / "artifacts",
        ),
        sweep_config={
            "scenarios": [
                {"name": "gamma", "overrides": {}},
                {"name": "alpha", "overrides": {}},
                {"name": "beta", "overrides": {}},
            ]
        },
    )

    aggregate = result.summary["aggregate"]

    assert aggregate["total_decisions"] == 22
    assert aggregate["total_orders"] == 25
    assert aggregate["total_fills"] == 5
    assert aggregate["scenarios_with_trades"] == 2
    assert aggregate["dominant_rejection_counts"] == [
        {"key": "edge_below_threshold", "count": 8},
        {"key": "stale_or_missing_snapshot", "count": 7},
        {"key": "no_bbo", "count": 6},
        {"key": "fee_kills_edge", "count": 3},
        {"key": "insufficient_depth_yes", "count": 3},
    ]

    # Backward-compatible schema: old aggregate fields are still present.
    old_aggregate_fields = {
        "best_net_profit",
        "best_scenario",
        "best_run_id",
        "median_net_profit",
        "median_scenario",
        "median_run_id",
        "worst_net_profit",
        "worst_scenario",
        "worst_run_id",
    }
    assert old_aggregate_fields.issubset(set(aggregate))
    assert aggregate["best_scenario"] == "alpha"
    assert aggregate["median_scenario"] == "gamma"
    assert aggregate["worst_scenario"] == "beta"

    # Scenario rows remain backward-compatible (no required fields removed).
    expected_scenario_fields = {
        "scenario_id",
        "scenario_name",
        "run_id",
        "net_profit",
        "realized_pnl",
        "unrealized_pnl",
        "total_fees",
        "warnings_count",
        "artifact_path",
    }
    for row in result.summary["scenarios"]:
        assert expected_scenario_fields.issubset(set(row))
