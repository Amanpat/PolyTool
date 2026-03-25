from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest

from packages.polymarket.crypto_pairs.reporting import (
    build_paper_soak_summary,
    generate_crypto_pair_paper_report,
    load_paper_run,
)
from tools.cli.crypto_pair_report import main as crypto_pair_report_main


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    if not rows:
        return
    path.write_text(
        "\n".join(
            json.dumps(row, sort_keys=True, allow_nan=False)
            for row in rows
        )
        + "\n",
        encoding="utf-8",
    )


def _runtime_event(event_type: str, recorded_at: str, **payload) -> dict:
    return {
        "record_type": "runtime_event",
        "schema_version": "crypto_pair_run_store_v0",
        "run_id": "placeholder",
        "mode": "paper",
        "event_type": event_type,
        "recorded_at": recorded_at,
        "payload": payload,
    }


def _observation(run_id: str, market_id: str, symbol: str = "BTC") -> dict:
    return {
        "record_type": "paper_opportunity_observed",
        "run_id": run_id,
        "opportunity_id": f"opp-{market_id}",
        "market_id": market_id,
        "symbol": symbol,
        "duration_min": 5,
        "paired_quote_cost": "0.95",
        "target_pair_cost_threshold": "0.97",
        "threshold_passed": True,
    }


def _intent(run_id: str, market_id: str, symbol: str = "BTC") -> dict:
    return {
        "record_type": "paper_order_intent_generated",
        "run_id": run_id,
        "intent_id": f"intent-{market_id}",
        "market_id": market_id,
        "symbol": symbol,
        "duration_min": 5,
        "pair_size": "1",
        "intended_pair_cost": "0.95",
    }


def _fill(run_id: str, market_id: str, leg: str) -> dict:
    return {
        "record_type": "paper_leg_fill_recorded",
        "run_id": run_id,
        "fill_id": f"fill-{market_id}-{leg.lower()}",
        "intent_id": f"intent-{market_id}",
        "market_id": market_id,
        "leg": leg,
        "price": "0.47" if leg == "YES" else "0.48",
        "size": "1",
    }


def _paired_exposure(run_id: str, market_id: str, symbol: str = "BTC") -> dict:
    return {
        "record_type": "paper_exposure_state",
        "run_id": run_id,
        "intent_id": f"intent-{market_id}",
        "market_id": market_id,
        "symbol": symbol,
        "duration_min": 5,
        "paired_size": "1",
        "paired_cost_usdc": "0.95",
        "paired_net_cash_outflow_usdc": "0.9480",
        "unpaired_size": "0",
        "exposure_status": "paired",
    }


def _settlement(run_id: str, market_id: str, net_pnl_usdc: str = "0.0520") -> dict:
    return {
        "record_type": "paper_pair_settlement",
        "run_id": run_id,
        "settlement_id": f"settlement-{market_id}",
        "intent_id": f"intent-{market_id}",
        "market_id": market_id,
        "symbol": "BTC",
        "duration_min": 5,
        "paired_size": "1",
        "paired_cost_usdc": "0.95",
        "paired_net_cash_outflow_usdc": "0.9480",
        "settlement_value_usdc": "1",
        "gross_pnl_usdc": "0.05",
        "net_pnl_usdc": net_pnl_usdc,
    }


def _write_fixture_run(
    tmp_path: Path,
    *,
    run_id: str,
    started_at: str = "2026-03-23T00:00:00+00:00",
    completed_at: str = "2026-03-24T00:00:00+00:00",
    opportunities: int = 30,
    intents: int = 30,
    paired_exposures: int = 30,
    settled_pairs: int = 30,
    runtime_events: list[dict] | None = None,
    stopped_reason: str = "completed",
    has_open_unpaired_exposure_final: bool = False,
    sink_enabled: bool = False,
    sink_error: str = "",
    sink_skipped_reason: str = "disabled",
) -> Path:
    run_dir = tmp_path / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    observation_rows = [
        _observation(run_id, f"market-{index}")
        for index in range(opportunities)
    ]
    intent_rows = [
        _intent(run_id, f"market-{index}")
        for index in range(intents)
    ]
    fill_rows = []
    for index in range(paired_exposures):
        market_id = f"market-{index}"
        fill_rows.append(_fill(run_id, market_id, "YES"))
        fill_rows.append(_fill(run_id, market_id, "NO"))
    exposure_rows = [
        _paired_exposure(run_id, f"market-{index}")
        for index in range(paired_exposures)
    ]
    settlement_rows = [
        _settlement(run_id, f"market-{index}")
        for index in range(settled_pairs)
    ]

    if runtime_events is None:
        runtime_events = [
            _runtime_event("runner_started", started_at),
            _runtime_event("cycle_started", started_at, cycle=1),
            _runtime_event("cycle_completed", completed_at, cycle=1),
        ]
    runtime_event_rows = []
    for event in runtime_events:
        runtime_event_rows.append({**event, "run_id": run_id})

    net_pnl_usdc = sum(
        (Decimal(row["net_pnl_usdc"]) for row in settlement_rows),
        start=Decimal("0"),
    )

    run_summary = {
        "record_type": "paper_run_summary",
        "run_id": run_id,
        "generated_at": completed_at,
        "markets_seen": opportunities,
        "opportunities_observed": opportunities,
        "threshold_pass_count": opportunities,
        "threshold_miss_count": 0,
        "order_intents_generated": intents,
        "paired_exposure_count": paired_exposures,
        "partial_exposure_count": 0,
        "settled_pair_count": settled_pairs,
        "intended_paired_notional_usdc": str(Decimal("0.95") * intents),
        "open_unpaired_notional_usdc": "0",
        "gross_pnl_usdc": str(Decimal("0.05") * settled_pairs),
        "net_pnl_usdc": str(net_pnl_usdc),
    }

    manifest = {
        "schema_version": "crypto_pair_run_store_v0",
        "run_id": run_id,
        "mode": "paper",
        "started_at": started_at,
        "completed_at": completed_at,
        "stopped_reason": stopped_reason,
        "artifact_dir": str(run_dir),
        "counts": {
            "runtime_events": len(runtime_event_rows),
            "observations": len(observation_rows),
            "order_intents": len(intent_rows),
            "fills": len(fill_rows),
            "exposures": len(exposure_rows),
            "settlements": len(settlement_rows),
            "market_rollups": 0,
        },
        "has_open_unpaired_exposure_final": has_open_unpaired_exposure_final,
        "sink_write_result": {
            "enabled": sink_enabled,
            "attempted_events": 0,
            "written_rows": 0,
            "skipped_reason": sink_skipped_reason,
            "error": sink_error,
        },
        "run_summary": run_summary,
    }

    _write_json(run_dir / "run_manifest.json", manifest)
    _write_json(run_dir / "run_summary.json", run_summary)
    _write_jsonl(run_dir / "runtime_events.jsonl", runtime_event_rows)
    _write_jsonl(run_dir / "observations.jsonl", observation_rows)
    _write_jsonl(run_dir / "order_intents.jsonl", intent_rows)
    _write_jsonl(run_dir / "fills.jsonl", fill_rows)
    _write_jsonl(run_dir / "exposures.jsonl", exposure_rows)
    _write_jsonl(run_dir / "settlements.jsonl", settlement_rows)
    return run_dir


def test_generate_report_promote_and_write_artifacts(tmp_path: Path) -> None:
    run_dir = _write_fixture_run(
        tmp_path,
        run_id="promote-run",
        opportunities=30,
        intents=30,
        paired_exposures=30,
        settled_pairs=30,
    )

    result = generate_crypto_pair_paper_report(run_dir)
    report = result.report

    assert report["rubric"]["decision"] == "promote"
    assert report["rubric"]["rubric_pass"] is True
    assert report["metrics"]["completed_pairs"] == 30
    assert report["metrics"]["pair_completion_rate"] == pytest.approx(1.0)
    assert report["metrics"]["average_completed_pair_cost"] == pytest.approx(0.95)
    assert report["metrics"]["estimated_profit_per_completed_pair"] == pytest.approx(
        0.052
    )
    assert report["metrics"]["maker_fill_rate_floor"] == pytest.approx(1.0)
    assert report["metrics"]["partial_leg_incidence"] == pytest.approx(0.0)
    assert result.json_path.exists()
    assert result.markdown_path.exists()

    written_json = json.loads(result.json_path.read_text(encoding="utf-8"))
    written_markdown = result.markdown_path.read_text(encoding="utf-8")
    assert written_json["rubric"]["verdict"] == "PROMOTE TO MICRO LIVE CANDIDATE"
    assert "PROMOTE TO MICRO LIVE CANDIDATE" in written_markdown


def test_cli_report_reruns_when_evidence_floor_not_met(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    run_dir = _write_fixture_run(
        tmp_path,
        run_id="rerun-run",
        opportunities=5,
        intents=5,
        paired_exposures=5,
        settled_pairs=5,
    )

    exit_code = crypto_pair_report_main(["--run", str(run_dir)])
    captured = capsys.readouterr()
    report = json.loads(
        (run_dir / "paper_soak_summary.json").read_text(encoding="utf-8")
    )

    assert exit_code == 0
    assert report["rubric"]["decision"] == "rerun"
    assert report["evidence_floor"]["met"] is False
    assert any(
        "evidence floor not met" in reason
        for reason in report["rubric"]["decision_reasons"]
    )
    assert "RERUN PAPER SOAK" in captured.out


def test_report_rejects_intent_created_during_frozen_feed_window(
    tmp_path: Path,
) -> None:
    runtime_events = [
        _runtime_event(
            "feed_state_changed",
            "2026-03-23T00:10:00+00:00",
            symbol="BTC",
            from_state="connected_fresh",
            to_state="stale",
        ),
        _runtime_event(
            "paper_new_intents_frozen",
            "2026-03-23T00:10:01+00:00",
            market_id="market-0",
            freeze_reason="reference_feed_stale",
        ),
        _runtime_event(
            "order_intent_created",
            "2026-03-23T00:10:05+00:00",
            market_id="market-0",
            pair_size="1",
            selected_legs=["YES", "NO"],
        ),
    ]
    run_dir = _write_fixture_run(
        tmp_path,
        run_id="reject-run",
        opportunities=1,
        intents=1,
        paired_exposures=1,
        settled_pairs=1,
        runtime_events=runtime_events,
    )

    report = build_paper_soak_summary(load_paper_run(run_dir))

    assert report["rubric"]["decision"] == "reject"
    assert report["metrics"]["safety_violation_count"] == 1
    assert report["feed_state"]["freeze_window_breach_count"] == 1
    assert report["rubric"]["metric_bands"]["feed_state_transitions"]["band"] == "reject"
    assert report["safety_violations"][0]["code"] == "intent_created_during_frozen_feed_window"


def test_operator_interrupt_is_treated_as_graceful_stop(tmp_path: Path) -> None:
    run_dir = _write_fixture_run(
        tmp_path,
        run_id="operator-stop-run",
        stopped_reason="operator_interrupt",
        opportunities=30,
        intents=30,
        paired_exposures=30,
        settled_pairs=30,
    )

    report = build_paper_soak_summary(load_paper_run(run_dir))

    assert report["rubric"]["decision"] == "promote"
    assert all(
        violation["code"] != "stopped_reason_not_completed"
        for violation in report["safety_violations"]
    )
