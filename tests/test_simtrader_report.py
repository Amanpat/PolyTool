"""Offline tests for simtrader report.html generation."""

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


def test_sweep_report_created_and_contains_expected_fields(tmp_path: Path) -> None:
    from tools.cli.simtrader import main as simtrader_main

    sweep_dir = tmp_path / "sweep_artifact"
    _write_json(
        sweep_dir / "sweep_manifest.json",
        {
            "sweep_id": "sweep-test-1",
            "base_config": {
                "fee_rate_bps": None,
                "mark_method": "bid",
                "latency_cancel_ticks": 0,
            },
            "quickrun_context": {
                "selected_slug": "demo-market-slug",
                "selected_at": "2026-02-25T00:00:00+00:00",
            },
            "scenarios": [
                {
                    "scenario_id": "scenario-alpha",
                    "overrides": {"fee_rate_bps": 50, "cancel_latency_ticks": 2},
                }
            ],
        },
    )
    _write_json(
        sweep_dir / "sweep_summary.json",
        {
            "sweep_id": "sweep-test-1",
            "aggregate": {
                "best_net_profit": "12.5",
                "total_decisions": 10,
                "total_orders": 7,
                "total_fills": 4,
                "scenarios_with_trades": 1,
                "dominant_rejection_counts": [
                    {"key": "insufficient_depth_no", "count": 12},
                    {"key": "edge_below_threshold", "count": 5},
                ],
            },
            "scenarios": [
                {
                    "scenario_id": "scenario-alpha",
                    "net_profit": "12.5",
                    "artifact_path": str(sweep_dir / "runs" / "scenario-alpha"),
                }
            ],
        },
    )
    _write_json(
        sweep_dir / "runs" / "scenario-alpha" / "run_manifest.json",
        {
            "fills_count": 4,
            "strategy_debug": {
                "rejection_counts": {
                    "insufficient_depth_no": 12,
                    "edge_below_threshold": 5,
                }
            },
        },
    )
    _write_jsonl(
        sweep_dir / "runs" / "scenario-alpha" / "orders.jsonl",
        [{"event": "order_submitted"}, {"event": "order_filled"}],
    )

    exit_code = simtrader_main(["report", "--path", str(sweep_dir)])
    assert exit_code == 0

    report_path = sweep_dir / "report.html"
    assert report_path.exists()
    html = report_path.read_text(encoding="utf-8")
    assert "sweep-test-1" in html
    assert "demo-market-slug" in html
    assert "scenario-alpha" in html
    assert "net_profit" in html
    assert "dominant_rejection_counts" in html
    assert "insufficient_depth_no" in html


def test_batch_report_created_and_contains_expected_fields(tmp_path: Path) -> None:
    from tools.cli.simtrader import main as simtrader_main

    batch_dir = tmp_path / "batch_artifact"
    _write_json(
        batch_dir / "batch_manifest.json",
        {
            "batch_id": "batch-test-1",
            "created_at": "20260225T010101Z",
            "fee_rate_bps": "200",
            "mark_method": "bid",
            "preset": "quick",
        },
    )
    _write_json(
        batch_dir / "batch_summary.json",
        {
            "batch_id": "batch-test-1",
            "aggregate": {
                "best_net_profit": "33.0",
                "total_decisions": 40,
                "total_orders": 22,
                "total_fills": 9,
            },
            "markets": [
                {
                    "slug": "market-a",
                    "median_net_profit": "10.0",
                    "dominant_rejection_key": "no_bbo",
                    "dominant_rejection_count": 9,
                    "total_fills": 6,
                },
                {
                    "slug": "market-b",
                    "median_net_profit": "-3.0",
                    "dominant_rejection_key": "edge_below_threshold",
                    "dominant_rejection_count": 4,
                    "total_fills": 0,
                },
            ],
        },
    )
    _write_json(
        batch_dir / "markets" / "market-a" / "runs" / "s1" / "run_manifest.json",
        {"fills_count": 2},
    )
    _write_json(
        batch_dir / "markets" / "market-a" / "runs" / "s2" / "run_manifest.json",
        {"fills_count": 1},
    )
    _write_json(
        batch_dir / "markets" / "market-b" / "runs" / "s1" / "run_manifest.json",
        {"fills_count": 0},
    )

    exit_code = simtrader_main(["report", "--path", str(batch_dir)])
    assert exit_code == 0

    report_path = batch_dir / "report.html"
    assert report_path.exists()
    html = report_path.read_text(encoding="utf-8")
    assert "batch-test-1" in html
    assert "market-a" in html
    assert "market-b" in html
    assert "scenarios_with_trades" in html
    assert "dominant_rejection" in html
    assert "no_bbo" in html


def test_run_report_created_and_contains_expected_fields(
    tmp_path: Path,
    capsys,
) -> None:
    from tools.cli.simtrader import main as simtrader_main

    run_dir = tmp_path / "run_artifact"
    _write_json(
        run_dir / "run_manifest.json",
        {
            "run_id": "run-test-1",
            "created_at": "2026-02-25T02:02:02+00:00",
            "decisions_count": 8,
            "fills_count": 3,
            "net_profit": "5.0",
            "latency_config": {"cancel_ticks": 2},
            "portfolio_config": {"fee_rate_bps": "150", "mark_method": "midpoint"},
            "quickrun_context": {"selected_slug": "run-market-slug"},
            "strategy_debug": {
                "rejection_counts": {"fee_kills_edge": 3, "no_bbo": 1}
            },
        },
    )
    _write_json(
        run_dir / "summary.json",
        {
            "run_id": "run-test-1",
            "net_profit": "5.0",
            "total_fees": "1.0",
            "final_equity": "1005.0",
        },
    )
    _write_jsonl(
        run_dir / "orders.jsonl",
        [{"event": "order_submitted"}, {"event": "order_filled"}],
    )

    exit_code = simtrader_main(["report", "--path", str(run_dir), "--open"])
    assert exit_code == 0

    out = capsys.readouterr().out
    assert "Report written:" in out
    assert "Open this report in a browser:" in out

    report_path = run_dir / "report.html"
    assert report_path.exists()
    html = report_path.read_text(encoding="utf-8")
    assert "run-test-1" in html
    assert "run-market-slug" in html
    assert "fee_kills_edge" in html
    assert "./summary.json" in html


def test_run_report_slug_from_shadow_context(tmp_path: Path) -> None:
    """Report shows slug from shadow_context when no quickrun_context present."""
    from tools.cli.simtrader import main as simtrader_main

    run_dir = tmp_path / "shadow_run_artifact"
    _write_json(
        run_dir / "run_manifest.json",
        {
            "run_id": "shadow-run-1",
            "mode": "shadow",
            "created_at": "2026-02-25T03:00:00+00:00",
            "decisions_count": 5,
            "fills_count": 2,
            "net_profit": "3.0",
            "latency_config": {"cancel_ticks": 1},
            "portfolio_config": {"fee_rate_bps": "100", "mark_method": "bid"},
            "shadow_context": {"selected_slug": "shadow-market-slug"},
        },
    )
    _write_json(run_dir / "summary.json", {"net_profit": "3.0"})

    exit_code = simtrader_main(["report", "--path", str(run_dir)])
    assert exit_code == 0

    html_text = (run_dir / "report.html").read_text(encoding="utf-8")
    assert "shadow-market-slug" in html_text
    assert "missing tape linkage" not in html_text


def test_run_report_slug_from_tape_meta(tmp_path: Path) -> None:
    """Report shows slug from tape meta.json when manifest has no context but has tape_dir."""
    from tools.cli.simtrader import main as simtrader_main

    tape_dir = tmp_path / "tape_20260225T000000Z"
    tape_dir.mkdir()
    _write_json(
        tape_dir / "meta.json",
        {
            "shadow_context": {
                "selected_slug": "tape-meta-slug",
                "selected_at": "2026-02-25T00:00:00+00:00",
            }
        },
    )

    run_dir = tmp_path / "run_from_tape"
    _write_json(
        run_dir / "run_manifest.json",
        {
            "run_id": "tape-linked-run",
            "created_at": "2026-02-25T01:00:00+00:00",
            "tape_path": str(tape_dir / "events.jsonl"),
            "tape_dir": str(tape_dir),
            "decisions_count": 3,
            "fills_count": 1,
            "net_profit": "1.5",
            "latency_config": {"cancel_ticks": 2},
            "portfolio_config": {"fee_rate_bps": "200", "mark_method": "bid"},
        },
    )
    _write_json(run_dir / "summary.json", {"net_profit": "1.5"})

    exit_code = simtrader_main(["report", "--path", str(run_dir)])
    assert exit_code == 0

    html_text = (run_dir / "report.html").read_text(encoding="utf-8")
    assert "tape-meta-slug" in html_text
    assert "missing tape linkage" not in html_text


def test_run_report_missing_tape_linkage_hint(tmp_path: Path) -> None:
    """Report shows missing tape linkage hint when no context and no tape meta."""
    from tools.cli.simtrader import main as simtrader_main

    run_dir = tmp_path / "unlinked_run"
    _write_json(
        run_dir / "run_manifest.json",
        {
            "run_id": "unlinked-run-1",
            "created_at": "2026-02-25T04:00:00+00:00",
            "decisions_count": 0,
            "fills_count": 0,
            "net_profit": "0.0",
            "latency_config": {"cancel_ticks": 0},
            "portfolio_config": {"fee_rate_bps": "200", "mark_method": "bid"},
            # no quickrun_context, no shadow_context, no tape_dir/tape_path
        },
    )
    _write_json(run_dir / "summary.json", {"net_profit": "0.0"})

    exit_code = simtrader_main(["report", "--path", str(run_dir)])
    assert exit_code == 0

    html_text = (run_dir / "report.html").read_text(encoding="utf-8")
    assert "missing tape linkage" in html_text


def test_sweep_header_includes_scenario_count(tmp_path: Path) -> None:
    """Sweep report header must contain scenario_count derived from manifest scenarios list."""
    from packages.polymarket.simtrader.report import generate_report

    sweep_dir = tmp_path / "sweep_hdr"
    _write_json(
        sweep_dir / "sweep_manifest.json",
        {
            "sweep_id": "sweep-hdr-1",
            "quickrun_context": {"selected_slug": "hdr-slug", "selected_at": "2026-02-25T10:00:00Z"},
            "base_config": {},
            "scenarios": [
                {"scenario_id": "s1", "overrides": {}},
                {"scenario_id": "s2", "overrides": {}},
                {"scenario_id": "s3", "overrides": {}},
            ],
        },
    )
    _write_json(
        sweep_dir / "sweep_summary.json",
        {
            "sweep_id": "sweep-hdr-1",
            "aggregate": {},
            "scenarios": [],
        },
    )

    result = generate_report(sweep_dir)
    assert result.artifact_type == "sweep"

    html_text = result.report_path.read_text(encoding="utf-8")
    assert "scenario_count" in html_text
    # 3 scenarios in the manifest -> header value "3"
    assert "<th>scenario_count</th><td>3</td>" in html_text
    assert "hdr-slug" in html_text
    assert "sweep-hdr-1" in html_text


def test_batch_header_includes_markets_count(tmp_path: Path) -> None:
    """Batch report header must contain markets_count derived from summary markets list."""
    from packages.polymarket.simtrader.report import generate_report

    batch_dir = tmp_path / "batch_hdr"
    _write_json(
        batch_dir / "batch_manifest.json",
        {
            "batch_id": "batch-hdr-1",
            "created_at": "20260225T120000Z",
            "fee_rate_bps": "200",
            "mark_method": "bid",
        },
    )
    _write_json(
        batch_dir / "batch_summary.json",
        {
            "batch_id": "batch-hdr-1",
            "aggregate": {},
            "markets": [
                {"slug": "mkt-a", "total_fills": 0},
                {"slug": "mkt-b", "total_fills": 0},
            ],
        },
    )

    result = generate_report(batch_dir)
    assert result.artifact_type == "batch"

    html_text = result.report_path.read_text(encoding="utf-8")
    assert "markets_count" in html_text
    # 2 markets in summary -> header value "2"
    assert "<th>markets_count</th><td>2</td>" in html_text
    assert "batch-hdr-1" in html_text
    assert "multiple (2)" in html_text


def test_run_header_includes_started_at_and_run_metrics_and_exit_reason(tmp_path: Path) -> None:
    """Unit test: header loads run manifest metadata including started_at -> created_at,
    strategy, exit_reason, and run_metrics."""
    from tools.cli.simtrader import main as simtrader_main

    run_dir = tmp_path / "hdr_run_artifact"
    # Minimal run_manifest with the fields used by the header loader
    from json import dumps
    manifest = {
        "run_id": "hdr-run-1",
        "started_at": "2026-02-25T03:00:00+00:00",
        "tape_path": str(run_dir / "tape.jsonl"),
        "tape_dir": str(run_dir / "tape"),
        "asset_id": "asset-1",
        "latency_config": {"cancel_ticks": 0},
        "portfolio_config": {"fee_rate_bps": "150", "mark_method": "bid"},
        "quickrun_context": {"selected_slug": "demo-slug"},
        "strategy": "binary_complement_arb",
        "exit_reason": "timeout",
        "run_metrics": {"net_profit": "1.0", "realized_pnl": "0.0"},
    }
    _write_json(run_dir / "run_manifest.json", manifest)
    _write_json(run_dir / "summary.json", {"net_profit": "1.0"})
    # Provide a minimal orders.jsonl so header computation can count orders if needed
    _write_jsonl(run_dir / "orders.jsonl", [{"order":"x"}])

    exit_code = simtrader_main(["report", "--path", str(run_dir)])
    assert exit_code == 0

    html = (run_dir / "report.html").read_text(encoding="utf-8")
    assert "hdr-run-1" in html
    assert "demo-slug" in html
    assert "2026-02-25T03:00:00+00:00" in html
    assert "timeout" in html
    assert "net_profit" in html  # from run_metrics dump in header
