"""Offline tests for simtrader diff command."""

from __future__ import annotations

import json
from pathlib import Path


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row) + "\n")


def _build_fixture_run(
    run_dir: Path,
    *,
    run_id: str,
    strategy: str,
    strategy_config: dict,
    net_profit: str,
    decisions: int,
    orders: int,
    fills: int,
    exit_reason: str | None,
    rejection_counts: dict[str, int],
) -> None:
    manifest: dict = {
        "run_id": run_id,
        "strategy": strategy,
        "strategy_config": strategy_config,
        "portfolio_config": {"fee_rate_bps": "200", "mark_method": "bid"},
        "latency_config": {"submit_ticks": 0, "cancel_ticks": 1},
        "decisions_count": decisions,
        "fills_count": fills,
        "net_profit": net_profit,
        "strategy_debug": {"rejection_counts": rejection_counts},
    }
    if exit_reason is not None:
        manifest["exit_reason"] = exit_reason

    _write_json(run_dir / "run_manifest.json", manifest)
    _write_json(run_dir / "summary.json", {"net_profit": net_profit})

    _write_jsonl(run_dir / "decisions.jsonl", [{"i": i} for i in range(decisions)])
    _write_jsonl(run_dir / "orders.jsonl", [{"i": i} for i in range(orders)])
    _write_jsonl(run_dir / "fills.jsonl", [{"i": i} for i in range(fills)])


def test_simtrader_diff_writes_json_and_prints_summary(tmp_path: Path, capsys) -> None:
    from tools.cli.simtrader import main as simtrader_main

    run_a = tmp_path / "runs" / "run_a"
    run_b = tmp_path / "runs" / "run_b"
    out_dir = tmp_path / "diff_out"

    _build_fixture_run(
        run_a,
        run_id="run-a",
        strategy="copy_wallet_replay",
        strategy_config={"signal_delay_ticks": 1},
        net_profit="10.5",
        decisions=3,
        orders=2,
        fills=1,
        exit_reason=None,
        rejection_counts={"no_bbo": 2, "edge_below_threshold": 1},
    )
    _build_fixture_run(
        run_b,
        run_id="run-b",
        strategy="binary_complement_arb",
        strategy_config={"signal_delay_ticks": 2},
        net_profit="8.0",
        decisions=5,
        orders=4,
        fills=2,
        exit_reason="stall: ws quiet",
        rejection_counts={"no_bbo": 4, "insufficient_depth_no": 3},
    )

    rc = simtrader_main(
        [
            "diff",
            "--a",
            str(run_a),
            "--b",
            str(run_b),
            "--output-dir",
            str(out_dir),
        ]
    )
    assert rc == 0

    out = capsys.readouterr().out
    assert "SimTrader diff summary" in out
    assert "Strategy: copy_wallet_replay -> binary_complement_arb (changed=True)" in out
    assert "Config changed: True" in out
    assert "decisions 3 -> 5 (+2)" in out
    assert "orders 2 -> 4 (+2)" in out
    assert "fills 1 -> 2 (+1)" in out
    assert "Net PnL: 10.5 -> 8.0 (delta=-2.5)" in out
    assert "Exit reason: none -> stall: ws quiet (changed=True)" in out

    summary_path = out_dir / "diff_summary.json"
    assert summary_path.exists()

    payload = json.loads(summary_path.read_text(encoding="utf-8"))
    assert payload["runs"]["a"]["run_id"] == "run-a"
    assert payload["runs"]["b"]["run_id"] == "run-b"
    assert payload["strategy"] == {
        "a": "copy_wallet_replay",
        "b": "binary_complement_arb",
        "changed": True,
    }
    assert payload["counts"]["decisions"] == {"a": 3, "b": 5, "delta": 2}
    assert payload["counts"]["orders"] == {"a": 2, "b": 4, "delta": 2}
    assert payload["counts"]["fills"] == {"a": 1, "b": 2, "delta": 1}
    assert payload["net_pnl"] == {"a": "10.5", "b": "8.0", "delta": "-2.5"}
    assert payload["exit_reason"] == {"a": "none", "b": "stall: ws quiet", "changed": True}
    assert payload["dominant_rejections"]["a"][0] == {"key": "no_bbo", "count": 2}
    assert payload["dominant_rejections"]["b"][0] == {"key": "no_bbo", "count": 4}


def test_simtrader_diff_default_output_under_artifacts(tmp_path: Path, monkeypatch) -> None:
    from tools.cli.simtrader import main as simtrader_main

    artifacts_root = tmp_path / "sim_artifacts"
    monkeypatch.setattr("tools.cli.simtrader.DEFAULT_ARTIFACTS_DIR", artifacts_root)

    run_a = tmp_path / "a"
    run_b = tmp_path / "b"

    _build_fixture_run(
        run_a,
        run_id="alpha",
        strategy="simtrader run",
        strategy_config={"x": 1},
        net_profit="0",
        decisions=1,
        orders=1,
        fills=0,
        exit_reason=None,
        rejection_counts={},
    )
    _build_fixture_run(
        run_b,
        run_id="beta",
        strategy="simtrader run",
        strategy_config={"x": 1},
        net_profit="0",
        decisions=1,
        orders=1,
        fills=0,
        exit_reason=None,
        rejection_counts={},
    )

    rc = simtrader_main(["diff", "--a", str(run_a), "--b", str(run_b)])
    assert rc == 0

    diff_files = sorted((artifacts_root / "diffs").glob("*/diff_summary.json"))
    assert len(diff_files) == 1
    payload = json.loads(diff_files[0].read_text(encoding="utf-8"))
    assert payload["strategy"]["changed"] is False
    assert payload["config"]["changed"] is False
    assert payload["counts"]["decisions"]["delta"] == 0
