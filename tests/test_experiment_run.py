import json
from datetime import datetime, timezone
from pathlib import Path

from packages.research.hypotheses import registry as registry_module
from packages.research.hypotheses.registry import (
    experiment_run,
    get_latest,
    register_from_candidate,
)
from polytool.__main__ import main as polytool_main


def _write_candidate_file(path: Path) -> Path:
    payload = {
        "schema_version": "alpha_distill_v0",
        "candidates": [
            {
                "candidate_id": "venue__binary__rank001",
                "rank": 1,
                "label": "Venue edge (venue=binary)",
                "mechanism_hint": "Assume venue structure stays stable.",
                "sample_size": 18,
                "measured_edge": {"total_count": 18, "net_clv_after_fee_adj": 0.015},
                "next_test": "Replay the next tape batch with the same filters.",
                "stop_condition": "Discard if CLV turns negative.",
                "evidence_refs": [
                    {
                        "dimension": "venue",
                        "key": "binary",
                        "count": 18,
                    }
                ],
            }
        ],
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return path


def test_experiment_run_cli_creates_generated_attempt_dir(tmp_path: Path, monkeypatch) -> None:
    fixed_now = datetime(2026, 3, 5, 16, 17, 18, tzinfo=timezone.utc)
    monkeypatch.setattr(registry_module, "_utcnow", lambda: fixed_now)

    registry_path = tmp_path / "registry.jsonl"
    candidate_file = _write_candidate_file(tmp_path / "alpha_candidates.json")
    hypothesis_id = register_from_candidate(registry_path, candidate_file, rank=1)
    outdir = tmp_path / "experiments" / hypothesis_id

    rc = polytool_main(
        [
            "experiment-run",
            "--id",
            hypothesis_id,
            "--registry",
            str(registry_path),
            "--outdir",
            str(outdir),
        ]
    )

    assert rc == 0

    experiment_path = outdir / "exp-20260305T161718Z" / "experiment.json"
    payload = json.loads(experiment_path.read_text(encoding="utf-8"))

    assert payload["schema_version"] == "experiment_init_v0"
    assert payload["hypothesis_id"] == hypothesis_id
    assert payload["experiment_id"] == "exp-20260305T161718Z"
    assert payload["created_at"] == "2026-03-05T16:17:18+00:00"
    assert payload["registry_snapshot"]["source"]["candidate_file"] == candidate_file.as_posix()
    assert payload["planned_execution"] == {
        "notes": [],
        "sweep_config": {},
        "tape_path": None,
    }


def test_experiment_run_adds_suffix_when_timestamp_dir_exists(tmp_path: Path, monkeypatch) -> None:
    fixed_now = datetime(2026, 3, 5, 16, 17, 18, tzinfo=timezone.utc)
    monkeypatch.setattr(registry_module, "_utcnow", lambda: fixed_now)

    registry_path = tmp_path / "registry.jsonl"
    candidate_file = _write_candidate_file(tmp_path / "alpha_candidates.json")
    hypothesis_id = register_from_candidate(registry_path, candidate_file, rank=1)
    snapshot = get_latest(registry_path, hypothesis_id)
    outdir = tmp_path / "experiments" / hypothesis_id

    first_path = experiment_run(outdir, hypothesis_id, snapshot)
    second_path = experiment_run(outdir, hypothesis_id, snapshot)

    assert first_path.parent.name == "exp-20260305T161718Z"
    assert second_path.parent.name == "exp-20260305T161718Z-02"

    second_payload = json.loads(second_path.read_text(encoding="utf-8"))
    assert second_payload["experiment_id"] == "exp-20260305T161718Z-02"
    assert second_payload["created_at"] == "2026-03-05T16:17:18+00:00"
