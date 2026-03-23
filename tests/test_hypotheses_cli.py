from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from polytool.__main__ import main as polytool_main


def _minimal_valid_hypothesis() -> dict:
    return {
        "schema_version": "hypothesis_v1",
        "metadata": {
            "user_slug": "testuser",
            "run_id": "abc123",
            "created_at_utc": "2026-03-11T00:00:00Z",
            "model": "claude-sonnet-4-6",
        },
        "executive_summary": {"bullets": ["Trader shows edge."]},
        "hypotheses": [],
    }


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
    assert "hypothesis-diff" in captured.out
    assert "hypothesis-summary" in captured.out
    assert "experiment-init" in captured.out
    assert "experiment-run" in captured.out
    assert "hypothesis-validate" in captured.out


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


# hypothesis-validate CLI

def test_hypothesis_validate_valid_file_exits_0(tmp_path: Path, capsys) -> None:
    hyp_path = tmp_path / "hypothesis.json"
    hyp_path.write_text(
        json.dumps(_minimal_valid_hypothesis(), indent=2), encoding="utf-8"
    )

    rc = polytool_main(["hypothesis-validate", "--hypothesis-path", str(hyp_path)])
    captured = capsys.readouterr()
    assert rc == 0
    result = json.loads(captured.out)
    assert result["valid"] is True
    assert result["errors"] == []


def test_hypothesis_validate_schema_invalid_exits_1(tmp_path: Path, capsys) -> None:
    bad = _minimal_valid_hypothesis()
    bad["schema_version"] = "wrong_version"
    hyp_path = tmp_path / "hypothesis.json"
    hyp_path.write_text(json.dumps(bad, indent=2), encoding="utf-8")

    rc = polytool_main(["hypothesis-validate", "--hypothesis-path", str(hyp_path)])
    captured = capsys.readouterr()
    assert rc == 1
    result = json.loads(captured.out)
    assert result["valid"] is False
    assert any("schema_version" in e for e in result["errors"])


def test_hypothesis_validate_malformed_json_exits_1(tmp_path: Path, capsys) -> None:
    hyp_path = tmp_path / "hypothesis.json"
    hyp_path.write_text("{not valid json at all", encoding="utf-8")

    rc = polytool_main(["hypothesis-validate", "--hypothesis-path", str(hyp_path)])
    captured = capsys.readouterr()
    assert rc == 1
    assert "error" in captured.err.lower() or "invalid" in captured.err.lower()


def test_hypothesis_validate_missing_file_exits_1(tmp_path: Path, capsys) -> None:
    missing = tmp_path / "does_not_exist.json"

    rc = polytool_main(["hypothesis-validate", "--hypothesis-path", str(missing)])
    captured = capsys.readouterr()
    assert rc == 1
    assert "error" in captured.err.lower() or "not found" in captured.err.lower()


def test_hypothesis_validate_uses_hypothesis_path_arg(tmp_path: Path) -> None:
    """Ensure --report-path is rejected; --hypothesis-path is the correct arg."""
    hyp_path = tmp_path / "hypothesis.json"
    hyp_path.write_text(
        json.dumps(_minimal_valid_hypothesis(), indent=2), encoding="utf-8"
    )
    rc = polytool_main(["hypothesis-validate", "--hypothesis-path", str(hyp_path)])
    assert rc == 0

    with pytest.raises(SystemExit) as exc_info:
        polytool_main(["hypothesis-validate", "--report-path", str(hyp_path)])
    assert exc_info.value.code != 0


# hypothesis-diff CLI

def test_hypothesis_diff_outputs_structured_json(tmp_path: Path, capsys) -> None:
    old_doc = _minimal_valid_hypothesis()
    old_doc["hypotheses"] = [
        {
            "id": "H1",
            "claim": "Trader shows late-entry edge.",
            "confidence": "medium",
            "falsification": "Check a fresh export.",
            "evidence": [{"text": "Late entries exited green.", "trade_uids": ["t1", "t2"]}],
        }
    ]

    new_doc = json.loads(json.dumps(old_doc))
    new_doc["metadata"]["run_id"] = "def456"
    new_doc["executive_summary"]["bullets"] = [
        "Trader shows edge.",
        "Confidence increased after the second review.",
    ]
    new_doc["hypotheses"][0]["confidence"] = "high"
    new_doc["hypotheses"][0]["evidence"] = [
        {"text": "Late entries exited green.", "trade_uids": ["t2", "t1"]},
        {"text": "A second pass found the same cluster.", "trade_uids": ["t3"]},
    ]
    new_doc["next_features_needed"] = ["Hold-duration buckets"]

    old_path = tmp_path / "old.json"
    new_path = tmp_path / "new.json"
    old_path.write_text(json.dumps(old_doc, indent=2), encoding="utf-8")
    new_path.write_text(json.dumps(new_doc, indent=2), encoding="utf-8")

    rc = polytool_main(["hypothesis-diff", "--old", str(old_path), "--new", str(new_path)])
    captured = capsys.readouterr()

    assert rc == 0
    payload = json.loads(captured.out)
    assert payload["summary"]["has_changes"] is True
    assert payload["metadata"]["identity_fields"]["run_id"]["status"] == "changed"
    assert "metadata.run_id" in payload["field_changes"]["changed"]
    assert payload["hypotheses"]["confidence_changes"] == [
        {"key": "id:H1", "new": "high", "old": "medium"}
    ]
    assert payload["next_features_needed"]["status"] == "added"


def test_hypothesis_diff_missing_file_exits_1(tmp_path: Path, capsys) -> None:
    existing = tmp_path / "new.json"
    existing.write_text(json.dumps(_minimal_valid_hypothesis(), indent=2), encoding="utf-8")

    rc = polytool_main(
        ["hypothesis-diff", "--old", str(tmp_path / "missing.json"), "--new", str(existing)]
    )
    captured = capsys.readouterr()

    assert rc == 1
    assert "file not found" in captured.err.lower()


def test_hypothesis_diff_invalid_json_exits_1(tmp_path: Path, capsys) -> None:
    old_path = tmp_path / "old.json"
    new_path = tmp_path / "new.json"
    old_path.write_text("{not valid json", encoding="utf-8")
    new_path.write_text(json.dumps(_minimal_valid_hypothesis(), indent=2), encoding="utf-8")

    rc = polytool_main(["hypothesis-diff", "--old", str(old_path), "--new", str(new_path)])
    captured = capsys.readouterr()

    assert rc == 1
    assert "invalid json" in captured.err.lower()


def test_hypothesis_diff_non_object_root_exits_1(tmp_path: Path, capsys) -> None:
    old_path = tmp_path / "old.json"
    new_path = tmp_path / "new.json"
    old_path.write_text(json.dumps(["not", "an", "object"]), encoding="utf-8")
    new_path.write_text(json.dumps(_minimal_valid_hypothesis(), indent=2), encoding="utf-8")

    rc = polytool_main(["hypothesis-diff", "--old", str(old_path), "--new", str(new_path)])
    captured = capsys.readouterr()

    assert rc == 1
    assert "root must be a json object" in captured.err.lower()


def test_hypothesis_diff_reports_top_level_hypotheses_type_mismatch(tmp_path: Path, capsys) -> None:
    old_doc = _minimal_valid_hypothesis()
    old_doc["hypotheses"] = "not-a-list"
    new_doc = _minimal_valid_hypothesis()

    old_path = tmp_path / "old.json"
    new_path = tmp_path / "new.json"
    old_path.write_text(json.dumps(old_doc, indent=2), encoding="utf-8")
    new_path.write_text(json.dumps(new_doc, indent=2), encoding="utf-8")

    rc = polytool_main(["hypothesis-diff", "--old", str(old_path), "--new", str(new_path)])
    captured = capsys.readouterr()

    assert rc == 0
    payload = json.loads(captured.out)
    assert payload["summary"]["has_changes"] is True
    assert payload["field_changes"]["changed"] == ["hypotheses"]
    assert payload["hypotheses"]["status"] == "changed"
    assert payload["hypotheses"]["old"] == "not-a-list"
    assert payload["hypotheses"]["new"] == []
    assert payload["hypotheses"]["type_mismatch"] == {
        "new_type": "list",
        "old_type": "str",
    }


def _summary_document() -> dict:
    return {
        "schema_version": "hypothesis_v1",
        "metadata": {
            "user_slug": "testuser",
            "run_id": "sum001",
            "created_at_utc": "2026-03-12T00:00:00Z",
            "model": "claude-sonnet-4-6",
        },
        "executive_summary": {
            "bullets": ["Trader shows edge in late-entry markets."],
            "overall_assessment": "mixed",
        },
        "hypotheses": [
            {
                "id": "H1",
                "claim": "Trader shows late-entry edge.",
                "confidence": "medium",
                "falsification": "Check a fresh export.",
                "next_feature_needed": "Minute-level timing data",
                "evidence": [
                    {
                        "text": "Late entries exited green.",
                        "trade_uids": ["t2", "t1"],
                    }
                ],
            }
        ],
        "limitations": ["No pre-trade context is available."],
    }


def test_hypothesis_summary_outputs_structured_json(tmp_path: Path, capsys) -> None:
    hypothesis_path = tmp_path / "hypothesis.json"
    hypothesis_path.write_text(
        json.dumps(_summary_document(), indent=2),
        encoding="utf-8",
    )

    rc = polytool_main(["hypothesis-summary", "--hypothesis-path", str(hypothesis_path)])
    captured = capsys.readouterr()

    assert rc == 0
    payload = json.loads(captured.out)
    assert payload["schema_version"] == "hypothesis_summary_v0"
    assert payload["primary_hypothesis"]["key"] == "id:H1"
    assert payload["primary_hypothesis"]["primary_evidence"]["path"] == "evidence[0].text"
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
    assert payload["summary_bullets"][5]["text"] == "Primary evidence: Late entries exited green."
    assert payload["summary_bullets"][5]["source_fields"] == [
        "hypotheses[id:H1].evidence[0].text"
    ]


def test_hypothesis_summary_primary_evidence_provenance_is_stable_under_reorder(
    tmp_path: Path, capsys
) -> None:
    left_path = tmp_path / "left.json"
    right_path = tmp_path / "right.json"

    left_payload = _summary_document()
    left_payload["hypotheses"][0]["evidence"] = [
        {"text": "Zulu evidence.", "trade_uids": ["t4", "t3"]},
        {"text": "Alpha evidence.", "trade_uids": ["t2", "t1"]},
    ]
    right_payload = copy.deepcopy(left_payload)
    right_payload["hypotheses"][0]["evidence"] = [
        right_payload["hypotheses"][0]["evidence"][1],
        right_payload["hypotheses"][0]["evidence"][0],
    ]
    right_payload["hypotheses"][0]["evidence"][0]["trade_uids"] = ["t1", "t2"]
    right_payload["hypotheses"][0]["evidence"][1]["trade_uids"] = ["t3", "t4"]

    left_path.write_text(json.dumps(left_payload, indent=2), encoding="utf-8")
    right_path.write_text(json.dumps(right_payload, indent=2), encoding="utf-8")

    rc_left = polytool_main(["hypothesis-summary", "--hypothesis-path", str(left_path)])
    captured_left = capsys.readouterr()
    rc_right = polytool_main(["hypothesis-summary", "--hypothesis-path", str(right_path)])
    captured_right = capsys.readouterr()

    assert rc_left == 0
    assert rc_right == 0

    left_summary = json.loads(captured_left.out)
    right_summary = json.loads(captured_right.out)
    assert left_summary["source"]["hypothesis_path"].endswith("left.json")
    assert right_summary["source"]["hypothesis_path"].endswith("right.json")
    left_summary["source"]["hypothesis_path"] = "PATH"
    right_summary["source"]["hypothesis_path"] = "PATH"
    assert left_summary == right_summary


def test_hypothesis_summary_reports_structure_issues_and_skips_malformed_hypotheses(
    tmp_path: Path, capsys
) -> None:
    hypothesis_path = tmp_path / "hypothesis.json"
    payload = {
        "schema_version": "hypothesis_v1",
        "metadata": {
            "user_slug": "testuser",
            "run_id": "sum-issues",
            "created_at_utc": "2026-03-12T00:00:00Z",
            "model": "claude-sonnet-4-6",
        },
        "hypotheses": [
            "not-an-object",
            {
                "id": "H0",
                "claim": "Malformed hypothesis should not be counted.",
                "evidence": ["Late entries exited green."],
            },
            {
                "id": "H1",
                "claim": "Trader shows late-entry edge.",
                "confidence": "medium",
                "falsification": "Check a fresh export.",
                "evidence": [{"text": "Canonical evidence survives."}],
            },
        ],
        "limitations": "No pre-trade context is available.",
    }
    hypothesis_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    rc = polytool_main(["hypothesis-summary", "--hypothesis-path", str(hypothesis_path)])
    captured = capsys.readouterr()

    assert rc == 0
    summary_payload = json.loads(captured.out)
    assert summary_payload["summary"]["hypothesis_count"] == 1
    assert summary_payload["summary"]["primary_hypothesis_key"] == "id:H1"
    assert summary_payload["primary_hypothesis"]["primary_evidence"]["path"] == "evidence[0].text"
    primary_evidence_bullet = next(
        bullet for bullet in summary_payload["summary_bullets"] if bullet["key"] == "primary_evidence"
    )
    assert primary_evidence_bullet["source_fields"] == ["hypotheses[id:H1].evidence[0].text"]
    assert summary_payload["structure_issues"] == [
        {
            "code": "skipped_non_object_hypothesis",
            "message": (
                "Hypothesis entry is not an object; skipped from hypothesis_count "
                "and primary_hypothesis."
            ),
            "path": "hypotheses[0]",
            "value": {"type": "str", "value": "not-an-object"},
        },
        {
            "code": "raw_string_evidence_fallback",
            "message": (
                "Evidence entry is a raw string; using it as text without inventing object fields."
            ),
            "path": "hypotheses[1].evidence[0]",
            "value": {"type": "str", "value": "Late entries exited green."},
        },
        {
            "code": "skipped_ineligible_hypothesis",
            "message": (
                "Hypothesis entry failed schema validation for summary eligibility; "
                "skipped from hypothesis_count and primary_hypothesis."
            ),
            "path": "hypotheses[1]",
            "reasons": [
                "Missing required field: 'hypotheses[1].confidence'",
                "Missing required field: 'hypotheses[1].falsification'",
                "'hypotheses[1].evidence[0]': 'Late entries exited green.' is not of type 'object'",
            ],
            "value": {
                "type": "dict",
                "value": {
                    "claim": "Malformed hypothesis should not be counted.",
                    "evidence": ["Late entries exited green."],
                    "id": "H0",
                },
            },
        },
        {
            "code": "scalar_string_fallback",
            "message": "Expected a list of strings; using the raw string directly.",
            "path": "limitations",
            "value": {"type": "str", "value": "No pre-trade context is available."},
        },
    ]


def test_hypothesis_summary_skips_schema_invalid_hypotheses_from_primary_selection(
    tmp_path: Path, capsys
) -> None:
    hypothesis_path = tmp_path / "hypothesis-schema-invalid.json"
    valid_duplicate = _summary_document()["hypotheses"][0]
    invalid_duplicate = copy.deepcopy(valid_duplicate)
    invalid_duplicate["tags"] = [1]
    payload = {
        "schema_version": "hypothesis_v1",
        "metadata": {
            "user_slug": "testuser",
            "run_id": "sum-schema-invalid",
            "created_at_utc": "2026-03-12T00:00:00Z",
            "model": "claude-sonnet-4-6",
        },
        "hypotheses": [
            {
                "id": "HX",
                "claim": "Invalid ids must not become summary-eligible.",
                "confidence": "medium",
                "falsification": "Check the next export.",
                "evidence": [{"text": "The id pattern is wrong."}],
            },
            invalid_duplicate,
            {
                "id": "H2",
                "claim": "Bad metrics must not become summary-eligible.",
                "confidence": "medium",
                "falsification": "Check the next export.",
                "evidence": [{"text": "Metrics are malformed.", "metrics": "oops"}],
            },
            {
                "id": "H3",
                "claim": "Bad file paths must not become summary-eligible.",
                "confidence": "medium",
                "falsification": "Check the next export.",
                "evidence": [{"text": "file_path is malformed.", "file_path": 123}],
            },
            valid_duplicate,
        ],
    }
    hypothesis_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    rc = polytool_main(["hypothesis-summary", "--hypothesis-path", str(hypothesis_path)])
    captured = capsys.readouterr()

    assert rc == 0
    summary_payload = json.loads(captured.out)
    assert summary_payload["summary"]["hypothesis_count"] == 1
    assert summary_payload["summary"]["primary_hypothesis_key"] == "id:H1"
    assert summary_payload["primary_hypothesis"]["key"] == "id:H1"
    assert summary_payload["primary_hypothesis"]["claim"] == valid_duplicate["claim"]
    assert summary_payload["structure_issues"] == [
        {
            "code": "skipped_ineligible_hypothesis",
            "message": (
                "Hypothesis entry failed schema validation for summary eligibility; "
                "skipped from hypothesis_count and primary_hypothesis."
            ),
            "path": "hypotheses[0]",
            "reasons": [
                "'hypotheses[0].id': 'HX' does not match '^H[0-9]+$'",
            ],
            "value": {
                "type": "dict",
                "value": {
                    "claim": "Invalid ids must not become summary-eligible.",
                    "confidence": "medium",
                    "evidence": [{"text": "The id pattern is wrong."}],
                    "falsification": "Check the next export.",
                    "id": "HX",
                },
            },
        },
        {
            "code": "skipped_ineligible_hypothesis",
            "message": (
                "Hypothesis entry failed schema validation for summary eligibility; "
                "skipped from hypothesis_count and primary_hypothesis."
            ),
            "path": "hypotheses[1]",
            "reasons": [
                "'hypotheses[1].tags[0]': 1 is not of type 'string'",
            ],
            "value": {
                "type": "dict",
                "value": {
                    "claim": valid_duplicate["claim"],
                    "confidence": valid_duplicate["confidence"],
                    "evidence": valid_duplicate["evidence"],
                    "falsification": valid_duplicate["falsification"],
                    "id": valid_duplicate["id"],
                    "next_feature_needed": valid_duplicate["next_feature_needed"],
                    "tags": [1],
                },
            },
        },
        {
            "code": "skipped_ineligible_hypothesis",
            "message": (
                "Hypothesis entry failed schema validation for summary eligibility; "
                "skipped from hypothesis_count and primary_hypothesis."
            ),
            "path": "hypotheses[2]",
            "reasons": [
                "'hypotheses[2].evidence[0].metrics': 'oops' is not of type 'object'",
            ],
            "value": {
                "type": "dict",
                "value": {
                    "claim": "Bad metrics must not become summary-eligible.",
                    "confidence": "medium",
                    "evidence": [{"metrics": "oops", "text": "Metrics are malformed."}],
                    "falsification": "Check the next export.",
                    "id": "H2",
                },
            },
        },
        {
            "code": "skipped_ineligible_hypothesis",
            "message": (
                "Hypothesis entry failed schema validation for summary eligibility; "
                "skipped from hypothesis_count and primary_hypothesis."
            ),
            "path": "hypotheses[3]",
            "reasons": [
                "'hypotheses[3].evidence[0].file_path': 123 is not of type 'string'",
            ],
            "value": {
                "type": "dict",
                "value": {
                    "claim": "Bad file paths must not become summary-eligible.",
                    "confidence": "medium",
                    "evidence": [{"file_path": 123, "text": "file_path is malformed."}],
                    "falsification": "Check the next export.",
                    "id": "H3",
                },
            },
        },
    ]


def test_hypothesis_summary_missing_file_exits_1(tmp_path: Path, capsys) -> None:
    missing = tmp_path / "does_not_exist.json"

    rc = polytool_main(["hypothesis-summary", "--hypothesis-path", str(missing)])
    captured = capsys.readouterr()

    assert rc == 1
    assert "file not found" in captured.err.lower()


def test_hypothesis_summary_invalid_json_exits_1(tmp_path: Path, capsys) -> None:
    hypothesis_path = tmp_path / "hypothesis.json"
    hypothesis_path.write_text("{not valid json", encoding="utf-8")

    rc = polytool_main(["hypothesis-summary", "--hypothesis-path", str(hypothesis_path)])
    captured = capsys.readouterr()

    assert rc == 1
    assert "invalid json" in captured.err.lower()

