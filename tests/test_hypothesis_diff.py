from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from packages.polymarket.hypotheses.diff import (
    diff_hypothesis_documents,
    load_hypothesis_artifact,
)


def _base_hypothesis() -> dict:
    return {
        "schema_version": "hypothesis_v1",
        "metadata": {
            "user_slug": "tester",
            "run_id": "run-001",
            "created_at_utc": "2026-03-11T00:00:00Z",
            "model": "claude-sonnet-4-6",
            "dossier_export_id": "dossier-001",
        },
        "executive_summary": {
            "bullets": [
                "Edge appears concentrated in late-event entries.",
                "Evidence is still limited to one export window.",
            ],
            "overall_assessment": "mixed",
        },
        "hypotheses": [
            {
                "id": "H1",
                "claim": "Trader sizes up in late-event NBA markets.",
                "confidence": "medium",
                "falsification": "Check if the pattern disappears in a fresh export.",
                "next_feature_needed": "Minute-level entry timing",
                "evidence": [
                    {
                        "text": "Two late NBA entries produced positive exits.",
                        "file_path": "kb/users/tester/llm_reports/2026-03-11/run-001/hypothesis.json",
                        "trade_uids": ["t2", "t1"],
                        "metrics": {"avg_entry_price": 0.42},
                    }
                ],
                "tags": ["nba", "timing"],
            }
        ],
        "limitations": ["No pre-trade context is available."],
        "missing_data_for_backtest": ["Historical orderbook depth"],
        "next_features_needed": ["Minute-level entry timing"],
    }


def test_diff_reports_added_removed_and_changed_fields() -> None:
    old_doc = _base_hypothesis()
    new_doc = copy.deepcopy(old_doc)
    new_doc["metadata"]["run_id"] = "run-002"
    new_doc["metadata"]["proxy_wallet"] = "0x1234567890abcdef1234567890abcdef12345678"
    new_doc["executive_summary"]["bullets"] = [
        "Edge appears concentrated in late-event entries.",
        "Confidence increased after the second evidence pass.",
    ]
    new_doc["executive_summary"]["overall_assessment"] = "profitable"
    new_doc["hypotheses"][0]["confidence"] = "high"
    new_doc["hypotheses"][0]["evidence"] = [
        {
            "text": "Two late NBA entries produced positive exits.",
            "file_path": "kb/users/tester/llm_reports/2026-03-11/run-001/hypothesis.json",
            "trade_uids": ["t1", "t2"],
            "metrics": {"avg_entry_price": 0.42},
        },
        {
            "text": "A second export found the same timing cluster.",
            "file_path": "kb/users/tester/llm_reports/2026-03-12/run-002/hypothesis.json",
            "trade_uids": ["t3"],
        },
    ]
    new_doc["hypotheses"][0]["execution_recommendation"] = "Manual follow-up only."
    new_doc["hypotheses"][0]["tags"] = ["timing", "nba"]
    new_doc["hypotheses"].append(
        {
            "id": "H2",
            "claim": "Trader avoids early-game entries.",
            "confidence": "low",
            "falsification": "Measure early-entry frequency on the next export.",
            "evidence": [
                {
                    "text": "No early entries were found in this sample.",
                }
            ],
        }
    )
    new_doc["limitations"] = [
        "No pre-trade context is available.",
        "The sample still covers only one month.",
    ]
    del new_doc["missing_data_for_backtest"]
    new_doc["next_features_needed"] = [
        "Minute-level entry timing",
        "Hold-duration buckets",
    ]

    diff = diff_hypothesis_documents(old_doc, new_doc)

    assert diff["summary"]["has_changes"] is True
    assert "metadata.proxy_wallet" in diff["field_changes"]["added"]
    assert "missing_data_for_backtest" in diff["field_changes"]["removed"]
    assert "metadata.run_id" in diff["field_changes"]["changed"]
    assert "hypotheses[id:H1].confidence" in diff["field_changes"]["changed"]
    assert diff["metadata"]["identity_fields"]["run_id"]["status"] == "changed"
    assert diff["executive_summary"]["bullets"]["added"] == [
        "Confidence increased after the second evidence pass.",
    ]
    assert diff["executive_summary"]["bullets"]["removed"] == [
        "Evidence is still limited to one export window.",
    ]
    assert diff["missing_data_for_backtest"]["status"] == "removed"
    assert diff["next_features_needed"]["added"] == ["Hold-duration buckets"]
    assert diff["hypotheses"]["summary"] == {
        "added": 1,
        "changed": 1,
        "removed": 0,
        "unchanged": 0,
    }
    assert diff["hypotheses"]["added"][0]["key"] == "id:H2"
    assert diff["hypotheses"]["confidence_changes"] == [
        {"key": "id:H1", "new": "high", "old": "medium"}
    ]
    assert diff["hypotheses"]["evidence_changes"] == [
        {
            "added_count": 1,
            "key": "id:H1",
            "new_count": 2,
            "old_count": 1,
            "removed_count": 0,
        }
    ]

    changed_hypothesis = diff["hypotheses"]["changed"][0]
    assert changed_hypothesis["key"] == "id:H1"
    assert changed_hypothesis["confidence"]["old"] == "medium"
    assert changed_hypothesis["confidence"]["new"] == "high"
    assert changed_hypothesis["execution_recommendation"]["status"] == "added"
    assert changed_hypothesis["tags"]["status"] == "unchanged"
    assert len(changed_hypothesis["evidence"]["added"]) == 1


def test_diff_ignores_order_only_changes_for_hypotheses_and_citations() -> None:
    old_doc = _base_hypothesis()
    old_doc["hypotheses"].append(
        {
            "id": "H2",
            "claim": "Trader avoids early-game entries.",
            "confidence": "low",
            "falsification": "Measure early-entry frequency on the next export.",
            "evidence": [{"text": "No early entries were found in this sample."}],
            "tags": ["timing", "filter"],
        }
    )

    new_doc = copy.deepcopy(old_doc)
    new_doc["hypotheses"] = [new_doc["hypotheses"][1], new_doc["hypotheses"][0]]
    new_doc["hypotheses"][1]["tags"] = ["timing", "nba"]
    new_doc["hypotheses"][1]["evidence"] = [
        {
            "text": "Two late NBA entries produced positive exits.",
            "file_path": "kb/users/tester/llm_reports/2026-03-11/run-001/hypothesis.json",
            "trade_uids": ["t1", "t2"],
            "metrics": {"avg_entry_price": 0.42},
        }
    ]

    diff = diff_hypothesis_documents(old_doc, new_doc)

    assert diff["summary"]["has_changes"] is False
    assert diff["field_changes"] == {"added": [], "changed": [], "removed": []}
    assert diff["hypotheses"]["summary"] == {
        "added": 0,
        "changed": 0,
        "removed": 0,
        "unchanged": 2,
    }


def test_load_hypothesis_artifact_rejects_non_object_root(tmp_path: Path) -> None:
    path = tmp_path / "hypothesis.json"
    path.write_text(json.dumps(["not", "an", "object"]), encoding="utf-8")

    with pytest.raises(ValueError, match="root must be a JSON object"):
        load_hypothesis_artifact(path)
def test_diff_matches_duplicate_claims_across_docs_deterministically() -> None:
    old_doc = _base_hypothesis()
    old_doc["hypotheses"] = [
        {
            "claim": "Trader clusters around the same late-event window.",
            "confidence": "medium",
            "falsification": "Re-run the same market bucket on a fresh export.",
            "evidence": [{"text": "Baseline timing cluster."}],
            "tags": ["timing"],
        }
    ]

    new_doc = copy.deepcopy(old_doc)
    new_doc["hypotheses"] = [
        {
            "claim": "Trader clusters around the same late-event window.",
            "confidence": "high",
            "falsification": "Re-run the same market bucket on a fresh export.",
            "evidence": [{"text": "Baseline timing cluster."}],
            "tags": ["timing"],
        },
        {
            "claim": "Trader clusters around the same late-event window.",
            "confidence": "low",
            "falsification": "Check whether the pattern disappears outside NBA.",
            "evidence": [{"text": "Possible second cluster."}],
            "tags": ["expansion"],
        },
    ]

    diff = diff_hypothesis_documents(old_doc, new_doc)

    assert diff["summary"]["has_changes"] is True
    assert diff["hypotheses"]["summary"] == {
        "added": 1,
        "changed": 1,
        "removed": 0,
        "unchanged": 0,
    }
    assert diff["hypotheses"]["confidence_changes"] == [
        {
            "key": diff["hypotheses"]["changed"][0]["key"],
            "new": "high",
            "old": "medium",
        }
    ]
    assert diff["hypotheses"]["changed"][0]["identity_source"] == "claim"
    assert diff["hypotheses"]["changed"][0]["key"].startswith(
        "claim:Trader clusters around the same late-event window.#"
    )
    assert diff["hypotheses"]["added"][0]["identity_source"] == "claim"
    assert diff["hypotheses"]["added"][0]["key"].startswith(
        "claim:Trader clusters around the same late-event window.#"
    )
    assert diff["hypotheses"]["changed"][0]["key"] != diff["hypotheses"]["added"][0]["key"]


def test_diff_ignores_order_only_changes_for_duplicate_claims_without_ids() -> None:
    old_doc = _base_hypothesis()
    old_doc["hypotheses"] = [
        {
            "claim": "Duplicate claim without ids.",
            "confidence": "medium",
            "falsification": "Check the first slice again.",
            "evidence": [{"text": "Slice one."}],
        },
        {
            "claim": "Duplicate claim without ids.",
            "confidence": "low",
            "falsification": "Check the second slice again.",
            "evidence": [{"text": "Slice two."}],
        },
    ]

    new_doc = copy.deepcopy(old_doc)
    new_doc["hypotheses"] = [new_doc["hypotheses"][1], new_doc["hypotheses"][0]]

    diff = diff_hypothesis_documents(old_doc, new_doc)

    assert diff["summary"]["has_changes"] is False
    assert diff["field_changes"] == {"added": [], "changed": [], "removed": []}
    assert diff["hypotheses"]["summary"] == {
        "added": 0,
        "changed": 0,
        "removed": 0,
        "unchanged": 2,
    }
    assert all(key.startswith("claim:Duplicate claim without ids.#") for key in diff["hypotheses"]["unchanged"])


def test_diff_ignores_order_only_changes_for_anonymous_hypotheses() -> None:
    old_doc = _base_hypothesis()
    old_doc["hypotheses"] = [
        {
            "confidence": "medium",
            "falsification": "Check the first anonymous slice.",
            "evidence": [{"text": "Anonymous slice one."}],
        },
        {
            "confidence": "low",
            "falsification": "Check the second anonymous slice.",
            "evidence": [{"text": "Anonymous slice two."}],
        },
    ]

    new_doc = copy.deepcopy(old_doc)
    new_doc["hypotheses"] = [new_doc["hypotheses"][1], new_doc["hypotheses"][0]]

    diff = diff_hypothesis_documents(old_doc, new_doc)

    assert diff["summary"]["has_changes"] is False
    assert diff["field_changes"] == {"added": [], "changed": [], "removed": []}
    assert diff["hypotheses"]["summary"] == {
        "added": 0,
        "changed": 0,
        "removed": 0,
        "unchanged": 2,
    }
    assert diff["hypotheses"]["unchanged"] == ["anonymous#1", "anonymous#2"]


def test_diff_reports_malformed_list_like_fields_without_silent_coercion() -> None:
    old_doc = _base_hypothesis()
    old_doc["limitations"] = "not-a-list"
    old_doc["hypotheses"][0]["tags"] = "timing"

    new_doc = copy.deepcopy(old_doc)
    new_doc["limitations"] = []
    new_doc["hypotheses"][0]["tags"] = []

    diff = diff_hypothesis_documents(old_doc, new_doc)

    assert diff["summary"]["has_changes"] is True
    assert "limitations" in diff["field_changes"]["changed"]
    assert "hypotheses[id:H1].tags" in diff["field_changes"]["changed"]
    assert diff["limitations"]["status"] == "changed"
    assert diff["limitations"]["old"] == "not-a-list"
    assert diff["limitations"]["new"] == []
    assert diff["limitations"]["type_mismatch"] == {
        "new_type": "list",
        "old_type": "str",
    }
    assert diff["hypotheses"]["summary"] == {
        "added": 0,
        "changed": 1,
        "removed": 0,
        "unchanged": 0,
    }
    changed = diff["hypotheses"]["changed"][0]
    assert changed["changed_fields"] == ["tags"]
    assert changed["tags"]["status"] == "changed"
    assert changed["tags"]["old"] == "timing"
    assert changed["tags"]["new"] == []
    assert changed["tags"]["type_mismatch"] == {
        "new_type": "list",
        "old_type": "str",
    }



def test_diff_reports_top_level_malformed_hypotheses_without_silent_coercion() -> None:
    old_doc = _base_hypothesis()
    old_doc["hypotheses"] = "not-a-list"

    new_doc = copy.deepcopy(old_doc)
    new_doc["hypotheses"] = []

    diff = diff_hypothesis_documents(old_doc, new_doc)

    assert diff["summary"]["has_changes"] is True
    assert diff["field_changes"] == {"added": [], "changed": ["hypotheses"], "removed": []}
    assert diff["hypotheses"]["status"] == "changed"
    assert diff["hypotheses"]["old"] == "not-a-list"
    assert diff["hypotheses"]["new"] == []
    assert diff["hypotheses"]["type_mismatch"] == {
        "new_type": "list",
        "old_type": "str",
    }
    assert diff["hypotheses"]["structure_issues"] == [
        {
            "key": "hypotheses",
            "new": {"type": "list", "value": []},
            "old": {"type": "str", "value": "not-a-list"},
            "path": "hypotheses",
            "status": "changed",
        }
    ]


def test_diff_reports_non_object_hypothesis_entries_explicitly() -> None:
    old_doc = _base_hypothesis()
    old_doc["hypotheses"] = ["not-an-object"]

    new_doc = copy.deepcopy(old_doc)
    new_doc["hypotheses"] = [{}]

    diff = diff_hypothesis_documents(old_doc, new_doc)

    assert diff["summary"]["has_changes"] is True
    assert diff["hypotheses"]["summary"] == {
        "added": 1,
        "changed": 0,
        "removed": 1,
        "unchanged": 0,
    }
    assert diff["hypotheses"]["removed"] == [
        {
            "entry": "not-an-object",
            "identity_source": "anonymous",
            "key": "anonymous#1",
        }
    ]
    assert diff["hypotheses"]["added"] == [
        {
            "entry": {},
            "identity_source": "anonymous",
            "key": "anonymous#2",
        }
    ]
    assert diff["hypotheses"]["structure_issues"] == [
        {
            "key": "anonymous#1",
            "new": None,
            "old": {"type": "str", "value": "not-an-object"},
            "path": "hypotheses[anonymous#1]",
            "status": "removed",
        }
    ]
