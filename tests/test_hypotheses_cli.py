from __future__ import annotations

import json
from pathlib import Path

from polytool.__main__ import main as polytool_main


def _write_candidate_file(path: Path) -> Path:
    payload = {
        "schema_version": "alpha_distill_v0",
        "candidates": [
            {
                "candidate_id": "market_type__sports__rank001",
                "rank": 1,
                "label": "Market type edge (market_type=sports)",
                "mechanism_hint": "Assume sports segments are more stable.",
                "sample_size": 30,
                "measured_edge": {"total_count": 30, "net_clv_after_fee_adj": 0.025},
                "next_test": "Validate on a new batch.",
                "stop_condition": "Discard if beat_close_rate falls below 0.50.",
                "evidence_refs": [
                    {
                        "dimension": "market_type",
                        "key": "sports",
                        "count": 30,
                    }
                ],
            }
        ],
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return path


def test_top_level_help_lists_hypothesis_commands(capsys) -> None:
    rc = polytool_main(["--help"])
    captured = capsys.readouterr()

    assert rc == 0
    assert "hypothesis-register" in captured.out
    assert "hypothesis-status" in captured.out
    assert "experiment-init" in captured.out
    assert "experiment-run" in captured.out


def test_cli_round_trip_register_status_and_experiment(tmp_path: Path) -> None:
    candidate_file = _write_candidate_file(tmp_path / "alpha_candidates.json")
    registry_path = tmp_path / "registry.jsonl"

    rc_register = polytool_main(
        [
            "hypothesis-register",
            "--candidate-file",
            str(candidate_file),
            "--rank",
            "1",
            "--registry",
            str(registry_path),
            "--notes",
            "cli smoke",
        ]
    )
    assert rc_register == 0

    first_event = json.loads(registry_path.read_text(encoding="utf-8").splitlines()[0])
    hypothesis_id = first_event["hypothesis_id"]

    rc_status = polytool_main(
        [
            "hypothesis-status",
            "--id",
            hypothesis_id,
            "--status",
            "testing",
            "--reason",
            "manual review",
            "--registry",
            str(registry_path),
        ]
    )
    assert rc_status == 0

    outdir = tmp_path / "experiments" / hypothesis_id / "exp001"
    rc_experiment = polytool_main(
        [
            "experiment-init",
            "--id",
            hypothesis_id,
            "--registry",
            str(registry_path),
            "--outdir",
            str(outdir),
        ]
    )
    assert rc_experiment == 0
    assert (outdir / "experiment.json").exists()
