from __future__ import annotations

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




