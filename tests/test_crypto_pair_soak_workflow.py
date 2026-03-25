from __future__ import annotations

import json
from pathlib import Path
from typing import Optional
from unittest.mock import MagicMock

import pytest

from packages.polymarket.clob import OrderBookTop
from packages.polymarket.crypto_pairs.reference_feed import (
    FeedConnectionState,
    ReferencePriceSnapshot,
)
from tools.cli import crypto_pair_run
from tools.cli.crypto_pair_run import run_crypto_pair_runner


def _make_mock_market(slug: str = "btc-5m-up") -> MagicMock:
    market = MagicMock()
    market.market_slug = slug
    market.question = "Will BTC be higher in 5 minutes?"
    market.clob_token_ids = [f"{slug}-yes", f"{slug}-no"]
    market.outcomes = ["Yes", "No"]
    market.active = True
    market.accepting_orders = True
    market.condition_id = f"cond-{slug}"
    market.end_date_iso = None
    return market


def _make_gamma_client(markets: list[MagicMock]) -> MagicMock:
    result = MagicMock()
    result.markets = markets
    client = MagicMock()
    client.fetch_all_markets.return_value = result
    return client


def _make_clob_client(
    prices: dict[str, tuple[Optional[float], Optional[float]]],
) -> MagicMock:
    def _side_effect(token_id: str):
        if token_id not in prices:
            return None
        best_bid, best_ask = prices[token_id]
        return OrderBookTop(
            token_id=token_id,
            best_bid=best_bid,
            best_ask=best_ask,
            raw_json={},
        )

    client = MagicMock()
    client.get_best_bid_ask.side_effect = _side_effect
    return client


def _fresh_snapshot(symbol: str = "BTC") -> ReferencePriceSnapshot:
    return ReferencePriceSnapshot(
        symbol=symbol,
        price=60_000.0,
        observed_at_s=1000.0,
        connection_state=FeedConnectionState.CONNECTED,
        is_stale=False,
        stale_threshold_s=15.0,
        feed_source="binance",
    )


class StaticFeed:
    def __init__(self, snapshot: ReferencePriceSnapshot) -> None:
        self.snapshot = snapshot

    def connect(self) -> None:
        return None

    def disconnect(self) -> None:
        return None

    def get_snapshot(self, symbol: str) -> ReferencePriceSnapshot:
        return self.snapshot


def test_auto_report_execution_on_graceful_exit_writes_artifacts(
    tmp_path: Path,
) -> None:
    market = _make_mock_market()
    gamma = _make_gamma_client([market])
    clob = _make_clob_client(
        {
            "btc-5m-up-yes": (None, 0.47),
            "btc-5m-up-no": (None, 0.48),
        }
    )

    manifest = run_crypto_pair_runner(
        output_base=tmp_path,
        duration_seconds=0,
        cycle_limit=1,
        gamma_client=gamma,
        clob_client=clob,
        reference_feed=StaticFeed(_fresh_snapshot()),
        auto_report=True,
    )

    run_dir = Path(manifest["artifact_dir"])
    persisted_manifest = json.loads(
        (run_dir / "run_manifest.json").read_text(encoding="utf-8")
    )

    assert manifest["auto_report"]["executed"] is True
    assert (run_dir / "paper_soak_summary.json").exists()
    assert (run_dir / "paper_soak_summary.md").exists()
    assert persisted_manifest["auto_report"]["summary_json"] == str(
        run_dir / "paper_soak_summary.json"
    )
    assert persisted_manifest["auto_report"]["summary_markdown"] == str(
        run_dir / "paper_soak_summary.md"
    )


def test_cli_soak_flags_parse_and_print_status(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    captured_kwargs: dict[str, object] = {}
    run_dir = tmp_path / "cli-run"
    run_dir.mkdir()
    manifest_path = run_dir / "run_manifest.json"
    run_summary_path = run_dir / "run_summary.json"
    summary_json_path = run_dir / "paper_soak_summary.json"
    summary_md_path = run_dir / "paper_soak_summary.md"
    manifest_path.write_text("{}\n", encoding="utf-8")
    run_summary_path.write_text("{}\n", encoding="utf-8")
    summary_json_path.write_text("{}\n", encoding="utf-8")
    summary_md_path.write_text("# summary\n", encoding="utf-8")

    def _fake_run_crypto_pair_runner(**kwargs):
        captured_kwargs.update(kwargs)
        heartbeat_callback = kwargs.get("heartbeat_callback")
        if callable(heartbeat_callback):
            heartbeat_callback(
                {
                    "elapsed_runtime": "00:05:00",
                    "cycle": 3,
                    "opportunities_observed": 12,
                    "intents_generated": 4,
                    "completed_pairs": 4,
                    "partial_exposure_count": 1,
                    "latest_feed_states": {"BTC": "connected_fresh"},
                    "stale_symbols": [],
                }
            )
        return {
            "run_id": "cli-run-id",
            "stopped_reason": "completed",
            "artifact_dir": str(run_dir),
            "artifacts": {
                "manifest_path": str(manifest_path),
                "run_summary_path": str(run_summary_path),
            },
            "auto_report": {
                "enabled": True,
                "executed": True,
                "summary_json": str(summary_json_path),
                "summary_markdown": str(summary_md_path),
                "verdict": "RERUN PAPER SOAK",
            },
        }

    monkeypatch.setattr(
        crypto_pair_run,
        "run_crypto_pair_runner",
        _fake_run_crypto_pair_runner,
    )

    exit_code = crypto_pair_run.main(
        [
            "--duration-hours",
            "1",
            "--duration-minutes",
            "30",
            "--heartbeat-minutes",
            "5",
            "--auto-report",
            "--output",
            str(tmp_path),
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert captured_kwargs["live"] is False
    assert captured_kwargs["duration_seconds"] == 5400
    assert captured_kwargs["heartbeat_interval_seconds"] == 300
    assert captured_kwargs["auto_report"] is True
    assert captured_kwargs["output_base"] == tmp_path
    assert "[crypto-pair-run] heartbeat" in captured.out
    assert "report_json" in captured.out
    assert "report_md" in captured.out
