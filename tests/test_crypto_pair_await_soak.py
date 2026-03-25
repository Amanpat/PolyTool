from __future__ import annotations

import json
from pathlib import Path

import pytest

from packages.polymarket.crypto_pairs.await_soak import (
    AwaitSoakLaunchPlan,
    AwaitSoakLaunchResult,
    DEFAULT_HEARTBEAT_SECONDS,
    build_coinbase_smoke_soak_launch_plan,
    run_crypto_pair_await_soak,
)
from packages.polymarket.crypto_pairs.market_watch import AvailabilitySummary
from tools.cli import crypto_pair_await_soak


def _not_eligible_summary() -> AvailabilitySummary:
    return AvailabilitySummary(
        eligible_now=False,
        total_eligible=0,
        by_symbol={"BTC": 0, "ETH": 0, "SOL": 0},
        by_duration={"5m": 0, "15m": 0},
        first_eligible_slugs=[],
        rejection_reason="No active BTC/ETH/SOL 5m/15m binary pair markets found",
        checked_at="2026-03-25T22:00:00+00:00",
    )


def _eligible_summary() -> AvailabilitySummary:
    return AvailabilitySummary(
        eligible_now=True,
        total_eligible=2,
        by_symbol={"BTC": 1, "ETH": 1, "SOL": 0},
        by_duration={"5m": 1, "15m": 1},
        first_eligible_slugs=["btc-5m-up", "eth-15m-up"],
        rejection_reason=None,
        checked_at="2026-03-25T22:05:00+00:00",
    )


def test_timeout_with_no_markets_writes_manifest_without_launch(tmp_path: Path) -> None:
    launched = {"called": False}

    def fake_watch(**kwargs):
        return False, _not_eligible_summary()

    def fake_launcher(plan: AwaitSoakLaunchPlan) -> AwaitSoakLaunchResult:
        launched["called"] = True
        return AwaitSoakLaunchResult(exit_code=0)

    manifest = run_crypto_pair_await_soak(
        timeout_seconds=30,
        poll_interval_seconds=5,
        output_base=tmp_path,
        _watch_fn=fake_watch,
        _launcher_fn=fake_launcher,
        _print_fn=lambda _: None,
    )

    assert manifest["exit_code"] == 1
    assert manifest["status"] == "timed_out"
    assert manifest["wait"]["eligible_found"] is False
    assert manifest["launch"]["launched"] is False
    assert launched["called"] is False

    artifact_dir = Path(manifest["artifact_dir"])
    persisted = json.loads((artifact_dir / "launcher_manifest.json").read_text(encoding="utf-8"))
    assert persisted["launch"]["command"] is None
    assert (artifact_dir / "availability_summary.json").exists()
    assert not (artifact_dir / "launch_output.log").exists()


def test_immediate_market_hit_launches_and_records_run_paths(tmp_path: Path) -> None:
    captured_plan: dict[str, object] = {}

    def fake_watch(**kwargs):
        return True, _eligible_summary()

    def fake_launcher(plan: AwaitSoakLaunchPlan) -> AwaitSoakLaunchResult:
        captured_plan["plan"] = plan
        return AwaitSoakLaunchResult(
            exit_code=0,
            output_text="[crypto-pair-run] artifact_dir  : artifacts/crypto_pairs/paper_runs/2026-03-25/abcd1234\n",
            launched_run_artifact_dir="artifacts/crypto_pairs/paper_runs/2026-03-25/abcd1234",
            launched_run_manifest_path="artifacts/crypto_pairs/paper_runs/2026-03-25/abcd1234/run_manifest.json",
            launched_run_summary_path="artifacts/crypto_pairs/paper_runs/2026-03-25/abcd1234/run_summary.json",
        )

    manifest = run_crypto_pair_await_soak(
        timeout_seconds=30,
        poll_interval_seconds=5,
        duration_seconds=1500,
        output_base=tmp_path,
        _watch_fn=fake_watch,
        _launcher_fn=fake_launcher,
        _print_fn=lambda _: None,
    )

    assert manifest["exit_code"] == 0
    assert manifest["status"] == "launched"
    assert manifest["wait"]["eligible_found"] is True
    assert manifest["launch"]["launched"] is True
    assert manifest["launch"]["run_artifact_dir"] == "artifacts/crypto_pairs/paper_runs/2026-03-25/abcd1234"
    assert manifest["launch"]["run_manifest_path"].endswith("run_manifest.json")
    assert manifest["launch"]["run_summary_path"].endswith("run_summary.json")
    assert isinstance(captured_plan["plan"], AwaitSoakLaunchPlan)

    artifact_dir = Path(manifest["artifact_dir"])
    persisted = json.loads((artifact_dir / "launcher_manifest.json").read_text(encoding="utf-8"))
    assert persisted["launch_output_ref"].endswith("launch_output.log")
    assert (artifact_dir / "launch_output.log").exists()


def test_launcher_exception_is_recorded_and_returns_nonzero(tmp_path: Path) -> None:
    def fake_watch(**kwargs):
        return True, _eligible_summary()

    def fake_launcher(plan: AwaitSoakLaunchPlan) -> AwaitSoakLaunchResult:
        raise RuntimeError("boom")

    manifest = run_crypto_pair_await_soak(
        timeout_seconds=30,
        poll_interval_seconds=5,
        output_base=tmp_path,
        _watch_fn=fake_watch,
        _launcher_fn=fake_launcher,
        _print_fn=lambda _: None,
    )

    assert manifest["exit_code"] == 1
    assert manifest["status"] == "launch_failed"
    assert manifest["launch"]["error"] == "RuntimeError: boom"
    assert Path(manifest["artifact_dir"], "launcher_manifest.json").exists()


def test_launch_command_construction_uses_standard_coinbase_smoke_soak_defaults() -> None:
    plan = build_coinbase_smoke_soak_launch_plan(duration_seconds=1800)

    assert plan.display_argv == (
        "python",
        "-m",
        "polytool",
        "crypto-pair-run",
        "--reference-feed-provider",
        "coinbase",
        "--duration-seconds",
        "1800",
        "--heartbeat-seconds",
        str(DEFAULT_HEARTBEAT_SECONDS),
    )
    assert plan.display_command == (
        "python -m polytool crypto-pair-run --reference-feed-provider coinbase "
        "--duration-seconds 1800 --heartbeat-seconds 60"
    )


def test_no_live_flag_is_ever_inserted_into_launch_command() -> None:
    plan = build_coinbase_smoke_soak_launch_plan(duration_seconds=600, heartbeat_seconds=30)

    assert "--live" not in plan.argv
    assert "--live" not in plan.display_argv
    assert "--live" not in plan.display_command


def test_cli_help_exits_zero() -> None:
    with pytest.raises(SystemExit) as exc_info:
        crypto_pair_await_soak.build_parser().parse_args(["--help"])
    assert exc_info.value.code == 0


def test_cli_returns_child_exit_code(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    captured_kwargs: dict[str, object] = {}

    def fake_run_crypto_pair_await_soak(**kwargs):
        captured_kwargs.update(kwargs)
        return {
            "exit_code": 0,
            "artifact_dir": str(tmp_path / "await"),
        }

    monkeypatch.setattr(
        crypto_pair_await_soak,
        "run_crypto_pair_await_soak",
        fake_run_crypto_pair_await_soak,
    )

    exit_code = crypto_pair_await_soak.main(
        [
            "--timeout",
            "90",
            "--poll-interval",
            "15",
            "--duration-seconds",
            "1200",
            "--output",
            str(tmp_path),
        ]
    )

    assert exit_code == 0
    assert captured_kwargs["timeout_seconds"] == 90
    assert captured_kwargs["poll_interval_seconds"] == 15
    assert captured_kwargs["duration_seconds"] == 1200
    assert captured_kwargs["output_base"] == tmp_path
