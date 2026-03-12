from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from packages.polymarket.hypotheses.summary import (
    extract_hypothesis_summary,
    load_hypothesis_summary_artifact,
)


def _summary_fixture() -> dict:
    return {
        "schema_version": "hypothesis_v1",
        "metadata": {
            "user_slug": "tester",
            "run_id": "run-001",
            "created_at_utc": "2026-03-12T00:00:00Z",
            "model": "claude-sonnet-4-6",
            "dossier_export_id": "dossier-001",
        },
        "executive_summary": {
            "bullets": [
                "Edge appears concentrated in late-event NBA entries.",
                "Evidence is still limited to one export window.",
            ],
            "overall_assessment": "mixed",
        },
        "hypotheses": [
            {
                "id": "H2",
                "claim": "Secondary pattern about hold duration.",
                "confidence": "low",
                "falsification": "Check the next export.",
                "evidence": [{"text": "Only a small sample supports this."}],
            },
            {
                "id": "H1",
                "claim": "Trader sizes up in late-event NBA markets.",
                "confidence": "medium",
                "falsification": "Check whether the timing cluster disappears on a fresh export.",
                "next_feature_needed": "Minute-level entry timing",
                "execution_recommendation": "Manual follow-up only",
                "evidence": [
                    {
                        "text": "Two late NBA entries produced positive exits.",
                        "file_path": "kb/users/tester/llm_reports/2026-03-12/run-001/hypothesis.json",
                        "trade_uids": ["t2", "t1"],
                        "metrics": {"avg_entry_price": 0.42},
                    }
                ],
            },
        ],
        "limitations": ["No pre-trade context is available."],
        "missing_data_for_backtest": ["Historical orderbook depth at trade time"],
        "next_features_needed": ["Hold-duration buckets"],
        "risks": ["Sample still covers only one export window."],
        "execution_recommendations": ["Do not automate without a fresh export."],
    }


def test_extract_hypothesis_summary_returns_expected_contract() -> None:
    payload = extract_hypothesis_summary(
        _summary_fixture(),
        hypothesis_path="kb/users/tester/llm_reports/2026-03-12/run-001/hypothesis.json",
    )

    assert payload["schema_version"] == "hypothesis_summary_v0"
    assert payload["source"]["hypothesis_path"] == (
        "kb/users/tester/llm_reports/2026-03-12/run-001/hypothesis.json"
    )
    assert payload["primary_hypothesis"]["key"] == "id:H1"
    assert payload["primary_hypothesis"]["claim"] == "Trader sizes up in late-event NBA markets."
    assert payload["primary_hypothesis"]["primary_evidence"] == {
        "file_path": "kb/users/tester/llm_reports/2026-03-12/run-001/hypothesis.json",
        "metrics": {"avg_entry_price": 0.42},
        "path": "evidence[0].text",
        "text": "Two late NBA entries produced positive exits.",
        "trade_uid_count": 2,
        "trade_uids": ["t1", "t2"],
    }
    assert payload["summary"] == {
        "available_sections": [
            "metadata",
            "executive_summary",
            "hypotheses",
            "limitations",
            "missing_data_for_backtest",
            "next_features_needed",
            "risks",
            "execution_recommendations",
        ],
        "bullet_count": 8,
        "hypothesis_count": 2,
        "observation_count": 0,
        "primary_hypothesis_key": "id:H1",
        "structured_fields_used": [
            "metadata.user_slug",
            "metadata.run_id",
            "metadata.model",
            "hypotheses[id:H1].id",
            "executive_summary.overall_assessment",
            "executive_summary.bullets[0]",
            "hypotheses[id:H1].claim",
            "hypotheses[id:H1].confidence",
            "hypotheses[id:H1].evidence[0].text",
            "risks[0]",
            "limitations[0]",
            "missing_data_for_backtest[0]",
            "hypotheses[id:H1].execution_recommendation",
            "hypotheses[id:H1].next_feature_needed",
        ],
    }
    assert [bullet["key"] for bullet in payload["summary_bullets"]] == [
        "identity",
        "overall_assessment",
        "executive_summary",
        "core_edge_claim",
        "confidence",
        "primary_evidence",
        "risks_limitations",
        "next_step",
    ]
    assert payload["summary_bullets"][0]["text"] == (
        "Identity: user_slug=tester; run_id=run-001; model=claude-sonnet-4-6; "
        "primary_hypothesis=id:H1; hypothesis_count=2."
    )
    assert payload["summary_bullets"][6]["text"] == (
        "Risks / limitations: Sample still covers only one export window. "
        "Limitation: No pre-trade context is available. "
        "Missing data: Historical orderbook depth at trade time."
    )
    assert payload["summary_bullets"][7]["text"] == (
        "Next step: Execution recommendation: Manual follow-up only. "
        "Next feature: Minute-level entry timing."
    )


def test_extract_hypothesis_summary_is_stable_across_hypothesis_reordering() -> None:
    left = _summary_fixture()
    right = copy.deepcopy(left)
    right["hypotheses"] = [right["hypotheses"][1], right["hypotheses"][0]]
    right["hypotheses"][0]["evidence"][0]["trade_uids"] = ["t1", "t2"]

    assert extract_hypothesis_summary(left) == extract_hypothesis_summary(right)


def test_extract_hypothesis_summary_omits_missing_optional_bullets() -> None:
    payload = extract_hypothesis_summary(
        {
            "schema_version": "hypothesis_v1",
            "metadata": {
                "user_slug": "tester",
                "run_id": "run-002",
                "created_at_utc": "2026-03-12T00:00:00Z",
                "model": "claude-sonnet-4-6",
            },
            "executive_summary": {
                "bullets": ["Evidence is thin but structured."],
            },
            "hypotheses": [],
        }
    )

    assert payload["primary_hypothesis"] is None
    assert [bullet["key"] for bullet in payload["summary_bullets"]] == [
        "identity",
        "executive_summary",
    ]
    assert payload["summary"]["bullet_count"] == 2


def test_load_hypothesis_summary_artifact_rejects_non_object_root(tmp_path: Path) -> None:
    hypothesis_path = tmp_path / "hypothesis.json"
    hypothesis_path.write_text(json.dumps(["not", "an", "object"]), encoding="utf-8")

    with pytest.raises(ValueError, match="root must be a JSON object"):
        load_hypothesis_summary_artifact(hypothesis_path)
