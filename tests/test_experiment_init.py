from __future__ import annotations

import json
from pathlib import Path

from packages.research.hypotheses.registry import experiment_init, get_latest, register_from_candidate


def _write_candidate_file(path: Path) -> Path:
    payload = {
        "schema_version": "alpha_distill_v0",
        "candidates": [
            {
                "candidate_id": "league__nfl__rank001",
                "rank": 1,
                "label": "League edge (league=nfl)",
                "mechanism_hint": "Assume the NFL segment keeps positive CLV.",
                "sample_size": 24,
                "measured_edge": {"total_count": 24, "net_clv_after_fee_adj": 0.02},
                "next_test": "Compare against the next cohort.",
                "stop_condition": "Discard if CLV turns negative.",
                "evidence_refs": [
                    {
                        "dimension": "league",
                        "key": "nfl",
                        "count": 24,
                    }
                ],
            }
        ],
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return path


def test_experiment_init_writes_expected_fields(tmp_path: Path) -> None:
    registry_path = tmp_path / "registry.jsonl"
    candidate_file = _write_candidate_file(tmp_path / "alpha_candidates.json")
    hypothesis_id = register_from_candidate(registry_path, candidate_file, rank=1)
    snapshot = get_latest(registry_path, hypothesis_id)

    out_path = experiment_init(tmp_path / "experiments" / hypothesis_id / "exp001", hypothesis_id, snapshot)
    payload = json.loads(out_path.read_text(encoding="utf-8"))

    assert out_path.name == "experiment.json"
    assert payload["schema_version"] == "experiment_init_v0"
    assert payload["hypothesis_id"] == hypothesis_id
    assert payload["registry_snapshot"]["source"]["candidate_file"] == candidate_file.as_posix()
    assert payload["inputs"]["candidate_rank"] == 1
    assert payload["inputs"]["source_candidate_id"] == "league__nfl__rank001"
    assert payload["planned_execution"] == {
        "notes": [],
        "sweep_config": {},
        "tape_path": None,
    }
