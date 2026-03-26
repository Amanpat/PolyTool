from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from tools.gates.mm_sweep import (
    MMSweepResult,
    TapeCandidate,
    TapeSweepOutcome,
    _build_gate_payload,
    _build_tape_candidate,
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


def test_discover_mm_sweep_tapes_accepts_explicit_benchmark_manifest(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import packages.polymarket.benchmark_manifest_contract as benchmark_contract

    tapes_dir = tmp_path / "tapes"
    explicit_a = _write_tape_dir(
        tapes_dir,
        "explicit-a",
        market_slug="explicit-a",
        yes_id="YES_A",
        no_id="NO_A",
        event_count=12,
    )
    explicit_b = _write_tape_dir(
        tapes_dir,
        "explicit-b",
        market_slug="explicit-b",
        yes_id="YES_B",
        no_id="NO_B",
        event_count=14,
    )
    benchmark_manifest = tmp_path / "benchmark_v1.tape_manifest"
    benchmark_manifest.write_text("[]\n", encoding="utf-8")

    fake_validation = SimpleNamespace(
        resolved_tape_paths=[
            explicit_a / "events.jsonl",
            explicit_b / "events.jsonl",
        ]
    )
    monkeypatch.setattr(
        benchmark_contract,
        "validate_benchmark_manifest",
        lambda manifest_path, lock_path=None: fake_validation,
    )
    monkeypatch.setattr(
        benchmark_contract,
        "default_lock_path_for_manifest",
        lambda manifest_path: tmp_path / "benchmark_v1.lock.json",
    )

    discovered = discover_mm_sweep_tapes(
        benchmark_manifest_path=benchmark_manifest,
    )

    assert [candidate.tape_dir.name for candidate in discovered] == ["explicit-a", "explicit-b"]
    assert [candidate.market_slug for candidate in discovered] == ["explicit-a", "explicit-b"]
    assert [candidate.yes_asset_id for candidate in discovered] == ["YES_A", "YES_B"]


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
    assert captured["benchmark_manifest_path"] is None
    assert captured["threshold"] == 0.70
    assert captured["min_events"] == 75
    assert captured["spread_multipliers"] == (0.5, 1.0, 1.5, 2.0, 3.0)
    assert "stub-mm-summary" in captured_out.out
    assert NOT_RUN_REASON_SUFFIX in captured_out.err


# ---------------------------------------------------------------------------
# New tests: watch_meta.json, market_meta.json, bucket_breakdown, close CLI
# ---------------------------------------------------------------------------


def _make_events_file(tape_dir: Path, *, yes_id: str, no_id: str, count: int = 10) -> Path:
    """Write a minimal events.jsonl for a tape dir."""
    events_path = tape_dir / "events.jsonl"
    rows = [
        json.dumps(
            {
                "seq": i,
                "asset_id": yes_id,
                "event_type": "price_change",
                "price_changes": [
                    {"asset_id": yes_id, "price": "0.50"},
                    {"asset_id": no_id, "price": "0.50"},
                ],
            }
        )
        for i in range(count)
    ]
    events_path.write_text("\n".join(rows) + "\n", encoding="utf-8")
    return events_path


def test_build_tape_candidate_reads_yes_asset_id_from_watch_meta(tmp_path: Path) -> None:
    """_build_tape_candidate must extract yes_asset_id from watch_meta.json when
    meta.json and prep_meta.json do not carry it."""
    tape_dir = tmp_path / "doge-updown-5m-1774209300"
    tape_dir.mkdir()
    events_path = _make_events_file(
        tape_dir,
        yes_id="94093621017194142016089689998471999649872898131309934810269761269305659224070",
        no_id="11899570848126135228924604216106261784526786677702690322120222904385223782723",
    )
    watch_meta = {
        "market_slug": "doge-updown-5m-1774209300",
        "yes_asset_id": "94093621017194142016089689998471999649872898131309934810269761269305659224070",
        "no_asset_id": "11899570848126135228924604216106261784526786677702690322120222904385223782723",
        "bucket": "new_market",
        "regime": "new_market",
    }
    (tape_dir / "watch_meta.json").write_text(json.dumps(watch_meta), encoding="utf-8")

    candidate = _build_tape_candidate(
        tape_dir=tape_dir,
        events_path=events_path,
        meta={},
        prep_meta={},
        watch_meta=watch_meta,
        market_meta={},
        silver_meta={},
        manifest_entry={},
        require_selected=False,
    )

    assert candidate is not None
    assert candidate.yes_asset_id == "94093621017194142016089689998471999649872898131309934810269761269305659224070"
    assert candidate.market_slug == "doge-updown-5m-1774209300"
    assert candidate.regime == "new_market"
    assert candidate.bucket == "new_market"


def test_build_tape_candidate_reads_yes_asset_id_from_market_meta(tmp_path: Path) -> None:
    """_build_tape_candidate must extract token_id from market_meta.json (Silver tapes)
    when meta.json and prep_meta.json do not carry a YES token."""
    tape_dir = tmp_path / "5500958648222024" / "2026-03-15T10-00-00Z"
    tape_dir.mkdir(parents=True)
    yes_token_id = "5500958648222024490080262026563017618333773328581609432182941377205770769101"
    events_path = _make_events_file(tape_dir, yes_id=yes_token_id, no_id="NO_TOKEN")
    market_meta = {
        "schema_version": "silver_market_meta_v1",
        "slug": "israeli-parliament-dissolved-by-june-30",
        "category": "politics",
        "token_id": yes_token_id,
        "benchmark_bucket": "politics",
    }
    (tape_dir / "market_meta.json").write_text(json.dumps(market_meta), encoding="utf-8")

    candidate = _build_tape_candidate(
        tape_dir=tape_dir,
        events_path=events_path,
        meta={},
        prep_meta={},
        watch_meta={},
        market_meta=market_meta,
        silver_meta={},
        manifest_entry={},
        require_selected=False,
    )

    assert candidate is not None
    assert candidate.yes_asset_id == yes_token_id
    assert candidate.market_slug == "israeli-parliament-dissolved-by-june-30"
    assert candidate.bucket == "politics"


def test_build_tape_candidate_reads_yes_asset_id_from_silver_meta(tmp_path: Path) -> None:
    """_build_tape_candidate must extract token_id from silver_meta.json as last
    fallback when no other source has the YES token."""
    tape_dir = tmp_path / "silver-tape"
    tape_dir.mkdir()
    yes_token_id = "99999999999999999999999999999999999999999999999999999999999999999999999999999"
    events_path = _make_events_file(tape_dir, yes_id=yes_token_id, no_id="NO_TOKEN")
    silver_meta = {"token_id": yes_token_id}

    candidate = _build_tape_candidate(
        tape_dir=tape_dir,
        events_path=events_path,
        meta={},
        prep_meta={},
        watch_meta={},
        market_meta={},
        silver_meta=silver_meta,
        manifest_entry={},
        require_selected=False,
    )

    assert candidate is not None
    assert candidate.yes_asset_id == yes_token_id


def test_build_gate_payload_includes_bucket_breakdown() -> None:
    """_build_gate_payload must emit bucket_breakdown when tapes carry bucket metadata."""

    def _make_outcome(bucket: str, positive: bool) -> TapeSweepOutcome:
        from decimal import Decimal

        tape = TapeCandidate(
            tape_dir=Path("/fake/tape"),
            events_path=Path("/fake/tape/events.jsonl"),
            market_slug="test-market",
            yes_asset_id="YES_ID",
            recorded_by=None,
            regime=None,
            parsed_events=100,
            tracked_asset_count=1,
            effective_events=100,
            bucket=bucket,
        )
        return TapeSweepOutcome(
            tape=tape,
            status="RAN",
            sweep_dir=None,
            scenario_rows=[],
            best_scenario_id="spread-x100",
            best_scenario_name="spread-x100",
            best_net_profit=Decimal("1.0") if positive else Decimal("-1.0"),
            positive=positive,
        )

    outcomes = [
        _make_outcome("crypto", positive=True),
        _make_outcome("crypto", positive=True),
        _make_outcome("crypto", positive=False),
        _make_outcome("politics", positive=True),
        _make_outcome("politics", positive=False),
        _make_outcome("new_market", positive=False),
    ]

    payload = _build_gate_payload(outcomes=outcomes, threshold=0.70)

    assert "bucket_breakdown" in payload
    bd = payload["bucket_breakdown"]
    assert bd["crypto"]["total"] == 3
    assert bd["crypto"]["positive"] == 2
    assert abs(bd["crypto"]["pass_rate"] - round(2 / 3, 4)) < 1e-6
    assert bd["politics"]["total"] == 2
    assert bd["politics"]["positive"] == 1
    assert bd["new_market"]["total"] == 1
    assert bd["new_market"]["positive"] == 0
    # Overall pass_rate: 3/6 = 0.5
    assert payload["pass_rate"] == pytest.approx(0.5, abs=1e-4)
    assert payload["passed"] is False  # 0.5 < 0.70


def test_build_gate_payload_no_bucket_breakdown_when_no_bucket_metadata() -> None:
    """_build_gate_payload must omit bucket_breakdown when no tape has bucket metadata."""
    from decimal import Decimal

    tape = TapeCandidate(
        tape_dir=Path("/fake/tape"),
        events_path=Path("/fake/tape/events.jsonl"),
        market_slug="test-market",
        yes_asset_id="YES_ID",
        recorded_by=None,
        regime=None,
        parsed_events=100,
        tracked_asset_count=1,
        effective_events=100,
        # bucket=None (default)
    )
    outcome = TapeSweepOutcome(
        tape=tape,
        status="RAN",
        sweep_dir=None,
        scenario_rows=[],
        best_scenario_id="spread-x100",
        best_scenario_name="spread-x100",
        best_net_profit=Decimal("1.0"),
        positive=True,
    )

    payload = _build_gate_payload(outcomes=[outcome], threshold=0.70)

    assert "bucket_breakdown" not in payload


def test_close_mm_sweep_gate_cli_accepts_benchmark_manifest_flag(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """close_mm_sweep_gate.main() must accept --benchmark-manifest and pass it to run_mm_sweep."""
    import tools.gates.close_mm_sweep_gate as close_gate

    benchmark_manifest = tmp_path / "benchmark_v1.tape_manifest"
    benchmark_manifest.write_text("[]", encoding="utf-8")

    captured: dict[str, object] = {}

    def fake_run_mm_sweep(**kwargs: object) -> MMSweepResult:
        captured.update(kwargs)
        return MMSweepResult(
            tapes=[],
            outcomes=[],
            gate_payload=None,
            artifact_path=None,
            threshold=0.70,
            min_events=50,
            not_run_reason="No eligible tapes found.",
        )

    # Patch in the close_gate module's namespace (that's where the name is bound
    # via its top-level `from tools.gates.mm_sweep import ...` statement).
    monkeypatch.setattr(close_gate, "run_mm_sweep", fake_run_mm_sweep)
    monkeypatch.setattr(close_gate, "format_mm_sweep_summary", lambda result: "stub-summary")

    rc = close_gate.main(
        [
            "--benchmark-manifest",
            str(benchmark_manifest),
            "--out",
            str(tmp_path / "out"),
        ]
    )

    assert rc == 1  # gate_payload is None -> not-run -> error
    assert captured.get("benchmark_manifest_path") == benchmark_manifest


def test_write_gate_result_writes_markdown_summary(tmp_path: Path) -> None:
    """_write_gate_result must create gate_summary.md alongside the gate JSON artifact."""
    from tools.gates.mm_sweep import _write_gate_result

    payload = {
        "gate": "mm_sweep",
        "passed": True,
        "tapes_total": 3,
        "tapes_positive": 3,
        "pass_rate": 1.0,
        "best_scenarios": [
            {
                "tape_dir": "artifacts/simtrader/tapes/demo-tape",
                "market_slug": "demo-market",
                "recorded_by": "prepare-gate2",
                "regime": "sports",
                "bucket": "sports",
                "best_scenario_id": "spread-x100",
                "best_scenario_name": "spread-x100",
                "best_net_profit": "5.00",
                "positive": True,
                "scenario_count": 5,
                "sweep_dir": None,
                "error": None,
            }
        ],
        "bucket_breakdown": {
            "sports": {"total": 3, "positive": 3, "pass_rate": 1.0}
        },
        "generated_at": "2026-03-26T00:00:00+00:00",
    }

    out_dir = tmp_path / "out"
    artifact_path = _write_gate_result(out_dir=out_dir, passed=True, payload=payload)

    assert artifact_path.name == "gate_passed.json"
    summary_path = out_dir / "gate_summary.md"
    assert summary_path.exists(), "gate_summary.md must be written alongside gate JSON"
    content = summary_path.read_text(encoding="utf-8")
    assert "PASS" in content
    assert "Per-Bucket Breakdown" in content
    assert "sports" in content
    assert "Per-Tape Results" in content
    assert "demo-tape" in content


def test_extract_yes_asset_id_fallback_to_asset_ids_list(tmp_path: Path) -> None:
    """_extract_yes_asset_id must return asset_ids[0] for early shadow tapes that
    have no shadow_context, no yes_token_id, but do have asset_ids=[YES, NO]."""
    from tools.gates.mm_sweep import _extract_yes_asset_id

    yes_id = "97449340182256366014320155718265676486703217567849039806162053075113517266910"
    no_id = "59259495934562596318644973716893809974860301509869285036503555129962149752635"

    meta_early_shadow = {
        "ws_url": "wss://ws-subscriptions-clob.polymarket.com/ws/market",
        "asset_ids": [yes_id, no_id],
        "source": "websocket",
        "started_at": "2026-02-25T23:40:32.259807+00:00",
        "ended_at": "2026-02-25T23:43:33.160409+00:00",
    }
    result = _extract_yes_asset_id(meta_early_shadow)
    assert result == yes_id, "asset_ids[0] must be returned as YES when no context fields exist"

    # shadow_context must win over asset_ids when present
    meta_with_context = {
        "asset_ids": ["WRONG", "NO"],
        "shadow_context": {"yes_token_id": "CORRECT", "no_token_id": "NO"},
    }
    result2 = _extract_yes_asset_id(meta_with_context)
    assert result2 == "CORRECT", "shadow_context.yes_token_id must take priority over asset_ids"

    # empty asset_ids must return None
    meta_empty = {"asset_ids": []}
    assert _extract_yes_asset_id(meta_empty) is None
