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


def _bullet(payload: dict, key: str) -> dict:
    return next(item for item in payload["summary_bullets"] if item["key"] == key)


def test_extract_hypothesis_summary_returns_expected_contract() -> None:
    payload = extract_hypothesis_summary(
        _summary_fixture(),
        hypothesis_path="kb/users/tester/llm_reports/2026-03-12/run-001/hypothesis.json",
    )

    assert payload["schema_version"] == "hypothesis_summary_v0"
    assert payload["source"]["hypothesis_path"] == (
        "kb/users/tester/llm_reports/2026-03-12/run-001/hypothesis.json"
    )
    assert payload["structure_issues"] == []
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


def test_extract_hypothesis_summary_skips_non_object_hypotheses_and_surfaces_structure_issues() -> None:
    document = _summary_fixture()
    document["hypotheses"] = ["not-an-object", *document["hypotheses"]]

    payload = extract_hypothesis_summary(document)

    assert payload["summary"]["hypothesis_count"] == 2
    assert payload["summary"]["primary_hypothesis_key"] == "id:H1"
    assert payload["primary_hypothesis"]["key"] == "id:H1"
    assert payload["structure_issues"] == [
        {
            "code": "skipped_non_object_hypothesis",
            "message": (
                "Hypothesis entry is not an object; skipped from hypothesis_count "
                "and primary_hypothesis."
            ),
            "path": "hypotheses[0]",
            "value": {"type": "str", "value": "not-an-object"},
        }
    ]


def test_extract_hypothesis_summary_skips_malformed_dict_hypotheses_without_stealing_primary() -> None:
    document = _summary_fixture()
    document["hypotheses"] = [
        {
            "id": "H0",
            "claim": "Malformed hypothesis should never become primary.",
            "evidence": [{"text": "Malformed entry still looks dict-shaped."}],
        },
        *document["hypotheses"],
    ]

    payload = extract_hypothesis_summary(document)

    assert payload["summary"]["hypothesis_count"] == 2
    assert payload["summary"]["primary_hypothesis_key"] == "id:H1"
    assert payload["primary_hypothesis"]["key"] == "id:H1"
    assert payload["structure_issues"] == [
        {
            "code": "skipped_ineligible_hypothesis",
            "message": (
                "Hypothesis entry failed schema validation for summary eligibility; "
                "skipped from hypothesis_count and primary_hypothesis."
            ),
            "path": "hypotheses[0]",
            "reasons": [
                "Missing required field: 'hypotheses[0].confidence'",
                "Missing required field: 'hypotheses[0].falsification'",
            ],
            "value": {
                "type": "dict",
                "value": {
                    "claim": "Malformed hypothesis should never become primary.",
                    "evidence": [{"text": "Malformed entry still looks dict-shaped."}],
                    "id": "H0",
                },
            },
        }
    ]


def test_extract_hypothesis_summary_stably_suffixes_duplicate_ids_across_reordering() -> None:
    left = {
        "schema_version": "hypothesis_v1",
        "metadata": {"user_slug": "tester", "run_id": "dup-id", "model": "local"},
        "hypotheses": [
            {
                "id": "H1",
                "claim": "Same claim.",
                "confidence": "medium",
                "falsification": "Zulu slice.",
                "tags": ["b", "a"],
                "evidence": [{"text": "Zulu evidence.", "trade_uids": ["t2", "t1"]}],
            },
            {
                "id": "H1",
                "claim": "Same claim.",
                "confidence": "high",
                "falsification": "Alpha slice.",
                "tags": ["c"],
                "evidence": [{"text": "Alpha evidence.", "trade_uids": ["t4", "t3"]}],
            },
        ],
    }
    right = copy.deepcopy(left)
    right["hypotheses"] = [right["hypotheses"][1], right["hypotheses"][0]]
    right["hypotheses"][1]["tags"] = ["a", "b"]
    right["hypotheses"][1]["evidence"][0]["trade_uids"] = ["t1", "t2"]

    left_payload = extract_hypothesis_summary(left)
    right_payload = extract_hypothesis_summary(right)

    assert left_payload == right_payload
    assert left_payload["primary_hypothesis"]["key"] == "id:H1#1"
    assert left_payload["primary_hypothesis"]["confidence"] == "high"


def test_extract_hypothesis_summary_stably_suffixes_duplicate_claims_across_reordering() -> None:
    left = {
        "schema_version": "hypothesis_v1",
        "metadata": {"user_slug": "tester", "run_id": "dup-claim", "model": "local"},
        "hypotheses": [
            {
                "claim": "Duplicate claim.",
                "confidence": "medium",
                "falsification": "Zulu slice.",
                "evidence": [{"text": "Zulu evidence."}],
            },
            {
                "claim": "Duplicate claim.",
                "confidence": "high",
                "falsification": "Alpha slice.",
                "evidence": [{"text": "Alpha evidence."}],
            },
        ],
    }
    right = copy.deepcopy(left)
    right["hypotheses"] = [right["hypotheses"][1], right["hypotheses"][0]]

    left_payload = extract_hypothesis_summary(left)
    right_payload = extract_hypothesis_summary(right)

    assert left_payload == right_payload
    assert left_payload["primary_hypothesis"]["key"] == "claim:Duplicate claim.#1"
    assert left_payload["primary_hypothesis"]["confidence"] == "high"


def test_extract_hypothesis_summary_uses_canonical_primary_evidence_selection() -> None:
    left = {
        "schema_version": "hypothesis_v1",
        "metadata": {"user_slug": "tester", "run_id": "evidence-order", "model": "local"},
        "hypotheses": [
            {
                "id": "H1",
                "claim": "Evidence order should not matter.",
                "confidence": "medium",
                "falsification": "Check the canonical evidence ordering.",
                "evidence": [
                    {"text": "Zulu evidence.", "trade_uids": ["t4", "t3"]},
                    {"text": "Alpha evidence.", "trade_uids": ["t2", "t1"]},
                ],
            }
        ],
    }
    right = copy.deepcopy(left)
    right["hypotheses"][0]["evidence"] = [
        right["hypotheses"][0]["evidence"][1],
        right["hypotheses"][0]["evidence"][0],
    ]
    right["hypotheses"][0]["evidence"][0]["trade_uids"] = ["t1", "t2"]
    right["hypotheses"][0]["evidence"][1]["trade_uids"] = ["t3", "t4"]

    left_payload = extract_hypothesis_summary(left)
    right_payload = extract_hypothesis_summary(right)

    assert left_payload == right_payload
    assert left_payload["primary_hypothesis"]["primary_evidence"] == {
        "file_path": None,
        "metrics": {},
        "path": "evidence[0].text",
        "text": "Alpha evidence.",
        "trade_uid_count": 2,
        "trade_uids": ["t1", "t2"],
    }
    assert _bullet(left_payload, "primary_evidence")["source_fields"] == [
        "hypotheses[id:H1].evidence[0].text"
    ]
    assert _bullet(right_payload, "primary_evidence")["source_fields"] == [
        "hypotheses[id:H1].evidence[0].text"
    ]


def test_extract_hypothesis_summary_skips_ineligible_hypotheses_with_raw_string_evidence() -> None:
    payload = extract_hypothesis_summary(
        {
            "schema_version": "hypothesis_v1",
            "metadata": {"user_slug": "tester", "run_id": "raw-paths", "model": "local"},
            "hypotheses": [
                {
                    "id": "H1",
                    "claim": "Raw strings should not invent fields.",
                    "evidence": ["Raw evidence line."],
                }
            ],
            "limitations": "Single limitation line.",
        }
    )

    assert payload["primary_hypothesis"] is None
    assert payload["summary"]["hypothesis_count"] == 0
    assert payload["summary"]["primary_hypothesis_key"] is None
    assert [bullet["key"] for bullet in payload["summary_bullets"]] == [
        "identity",
        "risks_limitations",
    ]
    assert _bullet(payload, "risks_limitations")["source_fields"] == ["limitations"]
    assert payload["structure_issues"] == [
        {
            "code": "raw_string_evidence_fallback",
            "message": (
                "Evidence entry is a raw string; using it as text without inventing object fields."
            ),
            "path": "hypotheses[0].evidence[0]",
            "value": {"type": "str", "value": "Raw evidence line."},
        },
        {
            "code": "skipped_ineligible_hypothesis",
            "message": (
                "Hypothesis entry failed schema validation for summary eligibility; "
                "skipped from hypothesis_count and primary_hypothesis."
            ),
            "path": "hypotheses[0]",
            "reasons": [
                "Missing required field: 'hypotheses[0].confidence'",
                "Missing required field: 'hypotheses[0].falsification'",
                "'hypotheses[0].evidence[0]': 'Raw evidence line.' is not of type 'object'",
            ],
            "value": {
                "type": "dict",
                "value": {
                    "claim": "Raw strings should not invent fields.",
                    "evidence": ["Raw evidence line."],
                    "id": "H1",
                },
            },
        },
        {
            "code": "scalar_string_fallback",
            "message": "Expected a list of strings; using the raw string directly.",
            "path": "limitations",
            "value": {"type": "str", "value": "Single limitation line."},
        },
    ]


@pytest.mark.parametrize(
    ("bad_entry", "expected_reasons"),
    [
        (
            {
                "id": "HX",
                "claim": "Invalid ids must not become summary-eligible.",
                "confidence": "medium",
                "falsification": "Check the next export.",
                "evidence": [{"text": "The id pattern is wrong."}],
            },
            ["'hypotheses[0].id': 'HX' does not match '^H[0-9]+$'"],
        ),
        (
            {
                "id": "H1",
                "claim": "Non-string tags must not become summary-eligible.",
                "confidence": "medium",
                "falsification": "Check the next export.",
                "tags": [1],
                "evidence": [{"text": "Tags are malformed."}],
            },
            ["'hypotheses[0].tags[0]': 1 is not of type 'string'"],
        ),
        (
            {
                "id": "H1",
                "claim": "Non-object evidence metrics must not become summary-eligible.",
                "confidence": "medium",
                "falsification": "Check the next export.",
                "evidence": [{"text": "Metrics are malformed.", "metrics": "oops"}],
            },
            ["'hypotheses[0].evidence[0].metrics': 'oops' is not of type 'object'"],
        ),
        (
            {
                "id": "H1",
                "claim": "Non-string evidence file paths must not become summary-eligible.",
                "confidence": "medium",
                "falsification": "Check the next export.",
                "evidence": [{"text": "file_path is malformed.", "file_path": 123}],
            },
            ["'hypotheses[0].evidence[0].file_path': 123 is not of type 'string'"],
        ),
    ],
    ids=["invalid_id", "non_string_tags", "bad_metrics", "bad_file_path"],
)
def test_extract_hypothesis_summary_skips_schema_invalid_hypothesis_dicts(
    bad_entry: dict,
    expected_reasons: list[str],
) -> None:
    document = _summary_fixture()
    document["hypotheses"] = [copy.deepcopy(bad_entry)]

    payload = extract_hypothesis_summary(document)

    assert payload["summary"]["hypothesis_count"] == 0
    assert payload["summary"]["primary_hypothesis_key"] is None
    assert payload["primary_hypothesis"] is None
    assert payload["structure_issues"] == [
        {
            "code": "skipped_ineligible_hypothesis",
            "message": (
                "Hypothesis entry failed schema validation for summary eligibility; "
                "skipped from hypothesis_count and primary_hypothesis."
            ),
            "path": "hypotheses[0]",
            "reasons": expected_reasons,
            "value": {
                "type": "dict",
                "value": bad_entry,
            },
        }
    ]


def test_extract_hypothesis_summary_schema_invalid_duplicate_cannot_steal_primary() -> None:
    document = _summary_fixture()
    valid_duplicate = copy.deepcopy(document["hypotheses"][1])
    invalid_duplicate = copy.deepcopy(valid_duplicate)
    invalid_duplicate["tags"] = [1]
    document["hypotheses"] = [invalid_duplicate, valid_duplicate]

    payload = extract_hypothesis_summary(document)

    assert payload["summary"]["hypothesis_count"] == 1
    assert payload["summary"]["primary_hypothesis_key"] == "id:H1"
    assert payload["primary_hypothesis"]["key"] == "id:H1"
    assert payload["primary_hypothesis"]["claim"] == valid_duplicate["claim"]
    assert payload["structure_issues"] == [
        {
            "code": "skipped_ineligible_hypothesis",
            "message": (
                "Hypothesis entry failed schema validation for summary eligibility; "
                "skipped from hypothesis_count and primary_hypothesis."
            ),
            "path": "hypotheses[0]",
            "reasons": [
                "'hypotheses[0].tags[0]': 1 is not of type 'string'",
            ],
            "value": {
                "type": "dict",
                "value": {
                    "claim": valid_duplicate["claim"],
                    "confidence": valid_duplicate["confidence"],
                    "evidence": valid_duplicate["evidence"],
                    "execution_recommendation": valid_duplicate["execution_recommendation"],
                    "falsification": valid_duplicate["falsification"],
                    "id": valid_duplicate["id"],
                    "next_feature_needed": valid_duplicate["next_feature_needed"],
                    "tags": [1],
                },
            },
        }
    ]


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
    assert payload["structure_issues"] == []
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
