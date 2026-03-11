from __future__ import annotations

import json
from pathlib import Path

import pytest

from packages.research.hypotheses.registry import (
    SCHEMA_VERSION,
    append_event,
    get_latest,
    register_from_candidate,
    stable_hypothesis_id,
    update_status,
)


def _candidate(*, rank: int = 1) -> dict:
    return {
        "candidate_id": f"entry_price_tier__deep_underdog__rank{rank:03d}",
        "rank": rank,
        "label": "Entry price tier edge (entry_price_tier=deep_underdog)",
        "mechanism_hint": "Assume oversold deep underdogs can retain positive CLV.",
        "sample_size": 42,
        "measured_edge": {
            "total_count": 42,
            "net_clv_after_fee_adj": 0.031,
        },
        "next_test": "Re-run on a fresh cohort and confirm net CLV stays positive.",
        "stop_condition": "Discard if beat_close_rate falls below 0.50.",
        "evidence_refs": [
            {
                "dimension": "entry_price_tier",
                "key": "deep_underdog",
                "count": 42,
            }
        ],
    }


def _write_candidate_file(path: Path, *candidates: dict) -> Path:
    path.write_text(
        json.dumps(
            {
                "schema_version": "alpha_distill_v0",
                "candidates": list(candidates),
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    return path


def test_stable_hypothesis_id_ignores_rank_suffix() -> None:
    first = _candidate(rank=1)
    second = _candidate(rank=2)

    assert stable_hypothesis_id(first) == stable_hypothesis_id(second)


def test_append_only_registry_preserves_prior_events(tmp_path: Path) -> None:
    registry_path = tmp_path / "registry.jsonl"
    candidate_file = _write_candidate_file(tmp_path / "alpha_candidates.json", _candidate(rank=1))

    hypothesis_id = register_from_candidate(registry_path, candidate_file, rank=1)
    update_status(registry_path, hypothesis_id, "testing", "manual review started")

    lines = registry_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2

    first_event = json.loads(lines[0])
    second_event = json.loads(lines[1])
    assert first_event["status"] == "proposed"
    assert second_event["status"] == "testing"
    assert second_event["status_reason"] == "manual review started"


def test_get_latest_materializes_state_from_events(tmp_path: Path) -> None:
    registry_path = tmp_path / "registry.jsonl"
    hypothesis_id = "hyp_materialized"

    append_event(
        registry_path,
        {
            "schema_version": SCHEMA_VERSION,
            "hypothesis_id": hypothesis_id,
            "title": "Materialized hypothesis",
            "created_at": "2026-03-05T12:00:00+00:00",
            "status": "proposed",
            "source": {"candidate_file": "alpha_candidates.json", "rank": 1},
            "assumptions": ["Assumption A"],
            "metrics_plan": {"next_test": "Check stability"},
            "stop_conditions": ["Stop on negative CLV"],
            "notes": ["Initial note"],
        },
    )
    append_event(
        registry_path,
        {
            "schema_version": SCHEMA_VERSION,
            "hypothesis_id": hypothesis_id,
            "status": "testing",
            "status_reason": "queued for manual review",
            "event_type": "status_change",
            "event_at": "2026-03-05T13:00:00+00:00",
        },
    )

    latest = get_latest(registry_path, hypothesis_id)

    assert latest["title"] == "Materialized hypothesis"
    assert latest["status"] == "testing"
    assert latest["status_reason"] == "queued for manual review"
    assert latest["metrics_plan"]["next_test"] == "Check stability"


def test_update_status_rejects_invalid_status(tmp_path: Path) -> None:
    registry_path = tmp_path / "registry.jsonl"
    candidate_file = _write_candidate_file(tmp_path / "alpha_candidates.json", _candidate(rank=1))
    hypothesis_id = register_from_candidate(registry_path, candidate_file, rank=1)

    with pytest.raises(ValueError, match="Invalid status"):
        update_status(registry_path, hypothesis_id, "confirmed", "not a valid enum")


def test_register_from_candidate_populates_latest_snapshot(tmp_path: Path) -> None:
    registry_path = tmp_path / "registry.jsonl"
    candidate_file = _write_candidate_file(tmp_path / "alpha_candidates.json", _candidate(rank=1))

    hypothesis_id = register_from_candidate(
        registry_path,
        candidate_file,
        rank=1,
        title="Custom title",
        notes="seeded from alpha-distill",
    )
    latest = get_latest(registry_path, hypothesis_id)

    assert latest["title"] == "Custom title"
    assert latest["status"] == "proposed"
    assert latest["source"]["candidate_file"] == candidate_file.as_posix()
    assert latest["source"]["rank"] == 1
    assert latest["stop_conditions"] == ["Discard if beat_close_rate falls below 0.50."]
    assert latest["notes"] == ["seeded from alpha-distill"]
