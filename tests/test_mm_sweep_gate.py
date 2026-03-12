from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from tools.gates.mm_sweep import (
    MMSweepResult,
    TapeCandidate,
    TapeSweepOutcome,
    discover_mm_sweep_tapes,
    format_mm_sweep_summary,
    run_mm_sweep,
)


NOT_RUN_REASON_SUFFIX = "record longer tapes before running Gate 2 sweep."


def _write_events(events_path: Path, *, yes_id: str, no_id: str, count: int) -> None:
    rows = []
    for idx in range(count):
        rows.append(
            {
                "seq": idx + 1,
                "asset_id": yes_id,
                "event_type": "price_change",
                "price_changes": [
                    {"asset_id": yes_id, "price": "0.51"},
                    {"asset_id": no_id, "price": "0.49"},
                ],
            }
        )
    events_path.write_text(
        "\n".join(json.dumps(row) for row in rows) + "\n",
        encoding="utf-8",
    )


def _write_tape_dir(
    tapes_dir: Path,
    name: str,
    *,
    market_slug: str,
    yes_id: str,
    no_id: str,
    event_count: int,
    meta: dict | None = None,
    prep_meta: dict | None = None,
) -> Path:
    tape_dir = tapes_dir / name
    tape_dir.mkdir(parents=True, exist_ok=True)
    _write_events(tape_dir / "events.jsonl", yes_id=yes_id, no_id=no_id, count=event_count)
    (tape_dir / "meta.json").write_text(
        json.dumps(meta or {}, indent=2) + "\n",
        encoding="utf-8",
    )
    (tape_dir / "prep_meta.json").write_text(
        json.dumps(
            prep_meta
            or {
                "market_slug": market_slug,
                "yes_asset_id": yes_id,
                "no_asset_id": no_id,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return tape_dir


def _write_manifest(path: Path, tape_dirs: list[Path]) -> None:
    payload = {
        "schema_version": "gate2_tape_manifest_v2",
        "generated_at": "2026-03-12T00:00:00+00:00",
        "tapes": [
            {
                "tape_dir": str(tape_dir),
                "slug": tape_dir.name,
                "regime": "sports",
                "final_regime": "sports",
                "recorded_by": "prepare-gate2",
            }
            for tape_dir in tape_dirs
        ],
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def test_discover_mm_sweep_tapes_uses_manifest_fallback_and_tracks_effective_events(
    tmp_path: Path,
) -> None:
    tapes_dir = tmp_path / "tapes"
    prepare_dir = _write_tape_dir(
        tapes_dir,
        "20260307T195039Z_will-the-toronto-map",
        market_slug="will-the-toronto-maple-leafs-win-the-2026-nhl-stanley-cup",
        yes_id="YES_TORONTO",
        no_id="NO_TORONTO",
        event_count=10,
    )
    _write_tape_dir(
        tapes_dir,
        "sports-meta-only",
        market_slug="sports-meta-only",
        yes_id="YES_META",
        no_id="NO_META",
        event_count=8,
        meta={"regime": "sports", "yes_asset_id": "YES_META"},
        prep_meta={
            "market_slug": "sports-meta-only",
            "yes_asset_id": "YES_META",
            "no_asset_id": "NO_META",
        },
    )
    _write_tape_dir(
        tapes_dir,
        "ignore-me",
        market_slug="totally-unrelated-market",
        yes_id="YES_OTHER",
        no_id="NO_OTHER",
        event_count=8,
    )
    manifest_path = tmp_path / "gate2_tape_manifest.json"
    _write_manifest(manifest_path, [prepare_dir])

    discovered = discover_mm_sweep_tapes(
        tapes_dir=tapes_dir,
        manifest_path=manifest_path,
    )

    names = [candidate.tape_dir.name for candidate in discovered]
    assert names == ["20260307T195039Z_will-the-toronto-map", "sports-meta-only"]
    assert discovered[0].recorded_by == "prepare-gate2"
    assert discovered[0].regime == "sports"
    assert discovered[0].yes_asset_id == "YES_TORONTO"
    assert discovered[0].parsed_events == 10
    assert discovered[0].tracked_asset_count == 2
    assert discovered[0].effective_events == 5


def test_run_mm_sweep_runs_five_spread_multiplier_scenarios(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import tools.gates.mm_sweep as mm_sweep

    tapes_dir = tmp_path / "tapes"
    tape_dirs = [
        _write_tape_dir(
            tapes_dir,
            "20260307T195039Z_will-the-toronto-map",
            market_slug="toronto-nhl",
            yes_id="YES_TORONTO",
            no_id="NO_TORONTO",
            event_count=120,
        ),
        _write_tape_dir(
            tapes_dir,
            "20260307T195542Z_will-the-vancouver-c",
            market_slug="vancouver-nhl",
            yes_id="YES_VANCOUVER",
            no_id="NO_VANCOUVER",
            event_count=120,
        ),
        _write_tape_dir(
            tapes_dir,
            "20260307T200105Z_will-the-calgary-fla",
            market_slug="calgary-nhl",
            yes_id="YES_CALGARY",
            no_id="NO_CALGARY",
            event_count=120,
        ),
    ]
    manifest_path = tmp_path / "gate2_tape_manifest.json"
    _write_manifest(manifest_path, tape_dirs)
    out_dir = tmp_path / "out"

    def fake_run_sweep(params, sweep_config):
        assert params.strategy_name == "market_maker_v1"
        assert params.asset_id is not None
        scenario_names = [scenario["name"] for scenario in sweep_config["scenarios"]]
        assert scenario_names == [
            "spread-x050",
            "spread-x100",
            "spread-x150",
            "spread-x200",
            "spread-x300",
        ]
        spread_values = [
            scenario["overrides"]["strategy_config"]["spread_multiplier"]
            for scenario in sweep_config["scenarios"]
        ]
        assert spread_values == [0.5, 1.0, 1.5, 2.0, 3.0]

        sweep_dir = params.artifacts_root / "sweeps" / params.sweep_id
        sweep_dir.mkdir(parents=True, exist_ok=True)

        if "toronto" in params.events_path.parent.name:
            scenarios = [
                {"scenario_id": "spread-x050", "scenario_name": "spread-x050", "net_profit": "-0.50"},
                {"scenario_id": "spread-x100", "scenario_name": "spread-x100", "net_profit": "-0.10"},
                {"scenario_id": "spread-x150", "scenario_name": "spread-x150", "net_profit": "0.20"},
                {"scenario_id": "spread-x200", "scenario_name": "spread-x200", "net_profit": "-0.05"},
                {"scenario_id": "spread-x300", "scenario_name": "spread-x300", "net_profit": "-0.40"},
            ]
        elif "vancouver" in params.events_path.parent.name:
            scenarios = [
                {"scenario_id": "spread-x050", "scenario_name": "spread-x050", "net_profit": "-0.10"},
                {"scenario_id": "spread-x100", "scenario_name": "spread-x100", "net_profit": "0.35"},
                {"scenario_id": "spread-x150", "scenario_name": "spread-x150", "net_profit": "0.15"},
                {"scenario_id": "spread-x200", "scenario_name": "spread-x200", "net_profit": "-0.25"},
                {"scenario_id": "spread-x300", "scenario_name": "spread-x300", "net_profit": "-0.30"},
            ]
        else:
            scenarios = [
                {"scenario_id": "spread-x050", "scenario_name": "spread-x050", "net_profit": "-0.40"},
                {"scenario_id": "spread-x100", "scenario_name": "spread-x100", "net_profit": "-0.20"},
                {"scenario_id": "spread-x150", "scenario_name": "spread-x150", "net_profit": "-0.05"},
                {"scenario_id": "spread-x200", "scenario_name": "spread-x200", "net_profit": "-0.10"},
                {"scenario_id": "spread-x300", "scenario_name": "spread-x300", "net_profit": "-0.15"},
            ]

        return SimpleNamespace(
            sweep_dir=sweep_dir,
            summary={"scenarios": scenarios},
        )

    monkeypatch.setattr(mm_sweep, "run_sweep", fake_run_sweep)

    result = run_mm_sweep(
        tapes_dir=tapes_dir,
        out_dir=out_dir,
        manifest_path=manifest_path,
        threshold=0.70,
    )

    assert result.gate_payload is not None
    assert result.gate_payload["passed"] is False
    assert result.gate_payload["tapes_total"] == 3
    assert result.gate_payload["tapes_positive"] == 2
    assert result.gate_payload["pass_rate"] == pytest.approx(0.6667, rel=0, abs=1e-4)
    assert result.artifact_path is not None
    assert result.artifact_path.name == "gate_failed.json"
    assert result.artifact_path.exists()
    assert all(len(outcome.scenario_rows) == 5 for outcome in result.outcomes)

    payload = json.loads(result.artifact_path.read_text(encoding="utf-8"))
    assert payload["gate"] == "mm_sweep"
    assert len(payload["best_scenarios"]) == 3
    assert payload["best_scenarios"][0]["best_scenario_id"] == "spread-x150"
    assert payload["best_scenarios"][0]["scenario_count"] == 5

    summary_text = format_mm_sweep_summary(result)
    assert "MM Sweep Summary" in summary_text
    assert "spread-x050" in summary_text
    assert "spread-x300" in summary_text
    assert "gate=FAIL" in summary_text


def test_run_mm_sweep_short_tapes_clear_gate_artifacts_and_return_not_run(tmp_path: Path) -> None:
    tapes_dir = tmp_path / "tapes"
    tape_dirs = [
        _write_tape_dir(
            tapes_dir,
            "20260307T195039Z_will-the-toronto-map",
            market_slug="toronto-nhl",
            yes_id="YES_TORONTO",
            no_id="NO_TORONTO",
            event_count=80,
        ),
        _write_tape_dir(
            tapes_dir,
            "20260307T195542Z_will-the-vancouver-c",
            market_slug="vancouver-nhl",
            yes_id="YES_VANCOUVER",
            no_id="NO_VANCOUVER",
            event_count=66,
        ),
        _write_tape_dir(
            tapes_dir,
            "20260307T200105Z_will-the-calgary-fla",
            market_slug="calgary-nhl",
            yes_id="YES_CALGARY",
            no_id="NO_CALGARY",
            event_count=30,
        ),
    ]
    manifest_path = tmp_path / "gate2_tape_manifest.json"
    _write_manifest(manifest_path, tape_dirs)
    out_dir = tmp_path / "out"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "gate_failed.json").write_text('{"stale": true}\n', encoding="utf-8")

    result = run_mm_sweep(
        tapes_dir=tapes_dir,
        out_dir=out_dir,
        manifest_path=manifest_path,
        threshold=0.70,
        min_events=50,
    )

    assert result.gate_payload is None
    assert result.artifact_path is None
    assert result.not_run_reason is not None
    assert NOT_RUN_REASON_SUFFIX in result.not_run_reason
    assert [outcome.status for outcome in result.outcomes] == [
        "SKIPPED_TOO_SHORT",
        "SKIPPED_TOO_SHORT",
        "SKIPPED_TOO_SHORT",
    ]
    assert not (out_dir / "gate_failed.json").exists()
    assert not (out_dir / "gate_passed.json").exists()

    summary_text = format_mm_sweep_summary(result)
    assert "SKIPPED_TOO_SHORT" in summary_text
    assert "effective_events=40 (< --min-events 50; raw_events=80 across 2 assets)" in summary_text
    assert "Gate=NOT_RUN" in summary_text
    assert "Artifact: not written (gate status will report NOT_RUN)" in summary_text


def test_cli_sweep_mm_passes_min_events_and_spread_multipliers(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    import tools.cli.simtrader as simtrader_cli
    import tools.gates.mm_sweep as mm_sweep

    captured: dict[str, object] = {}

    def fake_run_mm_sweep(**kwargs):
        captured.update(kwargs)
        tape = TapeCandidate(
            tape_dir=tmp_path / "tapes" / "demo-tape",
            events_path=tmp_path / "tapes" / "demo-tape" / "events.jsonl",
            market_slug="demo-market",
            yes_asset_id="YES_DEMO",
            recorded_by="prepare-gate2",
            regime="sports",
            parsed_events=80,
            tracked_asset_count=2,
            effective_events=40,
        )
        outcome = TapeSweepOutcome(
            tape=tape,
            status="SKIPPED_TOO_SHORT",
            sweep_dir=None,
            scenario_rows=[],
            best_scenario_id=None,
            best_scenario_name=None,
            best_net_profit=None,
            positive=False,
            error="effective_events=40 (< --min-events 75; raw_events=80 across 2 assets)",
        )
        return MMSweepResult(
            tapes=[tape],
            outcomes=[outcome],
            gate_payload=None,
            artifact_path=None,
            threshold=0.70,
            min_events=75,
            not_run_reason="No eligible tapes found ? record longer tapes before running Gate 2 sweep.",
        )

    monkeypatch.setattr(mm_sweep, "run_mm_sweep", fake_run_mm_sweep)
    monkeypatch.setattr(mm_sweep, "format_mm_sweep_summary", lambda result: "stub-mm-summary")

    rc = simtrader_cli.main(
        [
            "sweep-mm",
            "--tapes-dir",
            str(tmp_path / "tapes"),
            "--out",
            str(tmp_path / "out"),
            "--min-events",
            "75",
            "--spread-multipliers",
            "0.5",
            "1.0",
            "1.5",
            "2.0",
            "3.0",
        ]
    )

    captured_out = capsys.readouterr()
    assert rc == 1
    assert captured["tapes_dir"] == tmp_path / "tapes"
    assert captured["out_dir"] == tmp_path / "out"
    assert captured["threshold"] == 0.70
    assert captured["min_events"] == 75
    assert captured["spread_multipliers"] == (0.5, 1.0, 1.5, 2.0, 3.0)
    assert "stub-mm-summary" in captured_out.out
    assert NOT_RUN_REASON_SUFFIX in captured_out.err
