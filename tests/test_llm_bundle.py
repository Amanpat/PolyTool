import json
import os
import sys
from datetime import datetime
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "packages"))

from tools.cli import llm_bundle


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _fake_rag_queries(questions, settings, user_slug, prefixes):
    return [
        {
            "question": questions[0]["question"],
            "k": settings.k,
            "mode": "hybrid+rerank",
            "filters": {
                "user_slug": user_slug,
                "doc_types": None,
                "private_only": True,
                "public_only": False,
                "date_from": None,
                "date_to": None,
                "include_archive": False,
                "prefix_backstop": prefixes or [],
            },
            "results": [
                {
                    "file_path": "kb/users/herewego446/notes/2026-02-02.md",
                    "chunk_id": "chunk123",
                    "doc_id": "doc123",
                    "snippet": "Snippet alpha.",
                }
            ],
        }
    ]


def _setup_dossier_dirs(tmp_path, user_slug="herewego446"):
    """Create minimal dossier dirs with older + newer run."""
    base = tmp_path / "artifacts" / "dossiers" / "users" / user_slug

    older_dir = base / "0xabc" / "2026-02-01" / "oldrun"
    _write_text(older_dir / "memo.md", "old memo")
    _write_text(older_dir / "dossier.json", '{"old": true}')
    _write_json(older_dir / "manifest.json", {"created_at_utc": "2026-02-01T00:00:00Z"})

    latest_dir = base / "0xabc" / "2026-02-03" / "newrun"
    _write_text(latest_dir / "memo.md", "new memo")
    _write_text(latest_dir / "dossier.json", '{"new": true}')
    _write_json(latest_dir / "manifest.json", {"created_at_utc": "2026-02-03T12:00:00Z"})

    return base, latest_dir


def test_is_bundle_artifact_matches_only_self_referential_outputs():
    assert llm_bundle._is_bundle_artifact(
        "kb/users/herewego446/llm_bundles/2026-03-04/cf55d57b/rag_queries.json"
    )
    assert llm_bundle._is_bundle_artifact(
        "kb/users/herewego446/llm_bundles/2026-03-04/cf55d57b/prompt.txt"
    )
    assert not llm_bundle._is_bundle_artifact(
        "artifacts/dossiers/users/herewego446/0xabc/2026-03-04/scanrun/audit_coverage_report.md"
    )


def test_collect_excerpts_excludes_bundle_artifacts_and_keeps_audit_paths():
    audit_path = "artifacts/dossiers/users/herewego446/0xabc/2026-03-04/scanrun/audit_coverage_report.md"
    payloads = [
        {
            "results": [
                {
                    "file_path": "kb/users/herewego446/llm_bundles/2026-03-04/cf55d57b/rag_queries.json",
                    "chunk_id": "skip-rag-queries",
                    "doc_id": "doc-skip-rag-queries",
                    "snippet": "Exclude this rag query artifact.",
                },
                {
                    "file_path": "kb/users/herewego446/llm_bundles/2026-03-04/cf55d57b/prompt.txt",
                    "chunk_id": "skip-prompt",
                    "doc_id": "doc-skip-prompt",
                    "snippet": "Exclude this prompt artifact.",
                },
                {
                    "file_path": audit_path,
                    "chunk_id": "audit-keep",
                    "doc_id": "doc-audit-keep",
                    "snippet": "Keep this audit evidence.",
                },
            ]
        }
    ]

    excerpts, filtered_count = llm_bundle._collect_excerpts(payloads)

    assert filtered_count == 2
    assert excerpts == [
        {
            "file_path": audit_path,
            "chunk_id": "audit-keep",
            "doc_id": "doc-audit-keep",
            "snippet": "Keep this audit evidence.",
        }
    ]


def test_find_run_manifest_uses_manifest_json_when_only_legacy_exists(tmp_path):
    run_dir = tmp_path / "legacy_run"
    _write_json(run_dir / "manifest.json", {"created_at_utc": "2026-02-03T12:00:00Z"})

    manifest_path = llm_bundle.find_run_manifest(run_dir)
    assert manifest_path == run_dir / "manifest.json"


def test_find_run_manifest_uses_run_manifest_json_when_only_new_exists(tmp_path):
    run_dir = tmp_path / "scan_run"
    _write_json(run_dir / "run_manifest.json", {"created_at_utc": "2026-02-03T12:00:00Z"})

    manifest_path = llm_bundle.find_run_manifest(run_dir)
    assert manifest_path == run_dir / "run_manifest.json"


def test_find_run_manifest_prefers_run_manifest_json_when_both_exist(tmp_path):
    run_dir = tmp_path / "mixed_run"
    _write_json(run_dir / "manifest.json", {"source": "legacy"})
    _write_json(run_dir / "run_manifest.json", {"source": "scan"})

    manifest_path = llm_bundle.find_run_manifest(run_dir)
    assert manifest_path == run_dir / "run_manifest.json"


def test_find_run_manifest_errors_when_both_manifest_names_missing(tmp_path):
    run_dir = tmp_path / "missing_manifest_run"
    run_dir.mkdir(parents=True, exist_ok=True)

    with pytest.raises(FileNotFoundError) as exc_info:
        llm_bundle.find_run_manifest(run_dir)

    err = str(exc_info.value)
    assert llm_bundle._as_posix(run_dir / "run_manifest.json") in err
    assert llm_bundle._as_posix(run_dir / "manifest.json") in err
    assert "export-dossier" in err
    assert "scan --user" in err


def test_llm_bundle_builds_bundle_and_manifest(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "kb").mkdir()

    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    sentinel = docs_dir / "sentinel.txt"
    sentinel.write_text("keep", encoding="utf-8")

    user_slug = "herewego446"
    _base, latest_dir = _setup_dossier_dirs(tmp_path, user_slug)

    fixed_now = datetime(2026, 2, 3, 21, 0, 0)
    monkeypatch.setattr(llm_bundle, "_utcnow", lambda: fixed_now)
    monkeypatch.setattr(llm_bundle, "_short_uuid", lambda: "run123")
    monkeypatch.setattr(llm_bundle, "_run_rag_queries", _fake_rag_queries)

    exit_code = llm_bundle.main(["--user", "@HereWeGo446"])

    assert exit_code == 0

    expected_dir = (
        tmp_path
        / "kb"
        / "users"
        / user_slug
        / "llm_bundles"
        / "2026-02-03"
        / "run123"
    )
    assert expected_dir.exists()

    bundle_path = expected_dir / "bundle.md"
    manifest_path = expected_dir / "bundle_manifest.json"
    rag_path = expected_dir / "rag_queries.json"

    assert bundle_path.exists()
    assert manifest_path.exists()
    assert rag_path.exists()

    bundle_text = bundle_path.read_text(encoding="utf-8")
    assert "## manifest.json" in bundle_text
    assert "new memo" in bundle_text
    assert "[file_path: kb/users/herewego446/notes/2026-02-02.md]" in bundle_text

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["created_at_utc"] == "2026-02-03T21:00:00Z"
    assert manifest["user_slug"] == user_slug
    assert manifest["run_id"] == "run123"
    assert isinstance(manifest["model_hint"], str)
    assert manifest["dossier_path"] == "artifacts/dossiers/users/herewego446/0xabc/2026-02-03/newrun"
    assert manifest["memo_fill_mode"] == "deterministic_v1"
    assert manifest["memo_template_path"] == (
        "artifacts/dossiers/users/herewego446/0xabc/2026-02-03/newrun/memo.md"
    )
    assert manifest["memo_filled_path"] == (
        "kb/users/herewego446/llm_bundles/2026-02-03/run123/memo_filled.md"
    )
    assert manifest["rag_query_settings"]["k"] == 8
    assert manifest["selected_excerpts"] == [
        {
            "file_path": "kb/users/herewego446/notes/2026-02-02.md",
            "chunk_id": "chunk123",
            "doc_id": "doc123",
        }
    ]

    rag_queries = json.loads(rag_path.read_text(encoding="utf-8"))
    assert isinstance(rag_queries, list)
    assert rag_queries[0]["results"][0]["snippet"] == "Snippet alpha."

    devlog_path = (
        tmp_path
        / "kb"
        / "devlog"
        / "2026-02-03_llm_bundle_herewego446_run123.md"
    )
    devlog_text = devlog_path.read_text(encoding="utf-8")
    assert "Bundle dir: kb/users/herewego446/llm_bundles/2026-02-03/run123" in devlog_text
    assert "Questions file: default" in devlog_text
    assert "Prompt to paste: kb/users/herewego446/llm_bundles/2026-02-03/run123/bundle.md" in devlog_text
    assert "new memo" not in devlog_text

    doc_files = sorted(path for path in docs_dir.rglob("*") if path.is_file())
    assert doc_files == [sentinel]


def test_llm_bundle_writes_todo_free_memo_filled(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "kb").mkdir()

    user_slug = "herewego446"
    base, latest_dir = _setup_dossier_dirs(tmp_path, user_slug)

    memo_template = """# LLM Research Packet v1

## Executive Summary
- TODO: Summarize the strategy in 2-3 sentences.

## Key Observations
- TODO: Bullet observations backed by metrics/trade_uids.

## Hypotheses
| claim | evidence (metrics/trade_uids) | confidence | how to falsify | next feature needed |
| --- | --- | --- | --- | --- |
| TODO | TODO | TODO | TODO | TODO |

## What changed recently
- TODO: Compare to prior exports or recent buckets.

## Next features to compute
- TODO: Add derived metrics that would raise confidence.
"""
    _write_text(latest_dir / "memo.md", memo_template)
    _write_json(
        latest_dir / "dossier.json",
        {
            "coverage": {
                "mapping_coverage": 0.125,
            }
        },
    )

    scan_dir = base / "0xabc" / "2026-02-03" / "scanrun"
    _write_json(
        scan_dir / "run_manifest.json",
        {
            "command_name": "scan",
            "started_at": "2026-02-03T15:00:00Z",
        },
    )
    _write_json(
        scan_dir / "coverage_reconciliation_report.json",
        {
            "totals": {"positions_total": 10},
            "outcome_counts": {"WIN": 7, "LOSS": 3, "PENDING": 0},
            "pnl": {"realized_pnl_net_estimated_fees_total": 123.45},
            "market_metadata_coverage": {"coverage_rate": 0.8},
            "category_coverage": {"coverage_rate": 0.6},
        },
    )

    fixed_now = datetime(2026, 2, 3, 21, 0, 0)
    monkeypatch.setattr(llm_bundle, "_utcnow", lambda: fixed_now)
    monkeypatch.setattr(llm_bundle, "_short_uuid", lambda: "filled1")
    monkeypatch.setattr(llm_bundle, "_run_rag_queries", _fake_rag_queries)

    exit_code = llm_bundle.main(["--user", "@HereWeGo446", "--no-devlog"])
    assert exit_code == 0

    output_dir = (
        tmp_path / "kb" / "users" / user_slug / "llm_bundles" / "2026-02-03" / "filled1"
    )
    memo_filled_path = output_dir / "memo_filled.md"
    assert memo_filled_path.exists()

    memo_filled = memo_filled_path.read_text(encoding="utf-8")
    assert "TODO:" not in memo_filled
    assert "TODO" not in memo_filled
    assert "Outcome distribution from coverage report: WIN 7, LOSS 3, other 0, positions 10." in memo_filled
    assert "Realized net PnL after estimated fees (coverage report): 123.450000." in memo_filled
    assert (
        "Coverage scope note: trade-level mapping coverage = 12.50%; "
        "position-level market metadata coverage = 80.00%; "
        "position-level category coverage = 60.00%."
    ) in memo_filled

    bundle_text = (output_dir / "bundle.md").read_text(encoding="utf-8")
    assert "## memo_filled.md" in bundle_text
    assert "TODO:" not in bundle_text

def test_bundle_includes_coverage_md(tmp_path, monkeypatch):
    """When coverage_reconciliation_report.md exists in a scan run, bundle includes it."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "kb").mkdir()

    user_slug = "herewego446"
    _base, latest_dir = _setup_dossier_dirs(tmp_path, user_slug)

    # Add a scan run with run_manifest.json + coverage md
    scan_dir = _base / "0xabc" / "2026-02-03" / "scanrun"
    _write_json(scan_dir / "run_manifest.json", {
        "command_name": "scan",
        "started_at": "2026-02-03T15:00:00Z",
    })
    coverage_md = "# Coverage Report\n\nPositions: 50\nFallback UID coverage: 100.00%\nWarnings: none"
    _write_text(scan_dir / "coverage_reconciliation_report.md", coverage_md)

    fixed_now = datetime(2026, 2, 3, 21, 0, 0)
    monkeypatch.setattr(llm_bundle, "_utcnow", lambda: fixed_now)
    monkeypatch.setattr(llm_bundle, "_short_uuid", lambda: "cov01")
    monkeypatch.setattr(llm_bundle, "_run_rag_queries", _fake_rag_queries)

    exit_code = llm_bundle.main(["--user", "@HereWeGo446", "--no-devlog"])
    assert exit_code == 0

    bundle_path = (
        tmp_path / "kb" / "users" / user_slug / "llm_bundles" / "2026-02-03" / "cov01" / "bundle.md"
    )
    bundle_text = bundle_path.read_text(encoding="utf-8")

    assert "## Coverage & Reconciliation" in bundle_text
    # file_path header should use forward slashes
    assert "[file_path:" in bundle_text
    assert "coverage_reconciliation_report.md" in bundle_text
    # Sentinel lines from the coverage md
    assert "Positions: 50" in bundle_text
    assert "Fallback UID coverage: 100.00%" in bundle_text


def test_bundle_coverage_json_fallback(tmp_path, monkeypatch):
    """When only coverage_reconciliation_report.json exists, bundle includes a summary."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "kb").mkdir()

    user_slug = "herewego446"
    _base, latest_dir = _setup_dossier_dirs(tmp_path, user_slug)

    scan_dir = _base / "0xabc" / "2026-02-03" / "scanrun"
    _write_json(scan_dir / "run_manifest.json", {
        "command_name": "scan",
        "started_at": "2026-02-03T15:00:00Z",
    })
    coverage_data = {
        "totals": {"positions_total": 42},
        "outcome_counts": {"WIN": 20, "LOSS": 15, "PENDING": 7},
        "deterministic_trade_uid_coverage": {"pct_with_trade_uid": 0.95},
        "fallback_uid_coverage": {"pct_with_fallback_uid": 1.0},
        "resolution_coverage": {"unknown_resolution_rate": 0.0},
        "warnings": ["All rows have fees_source=unknown"],
    }
    _write_json(scan_dir / "coverage_reconciliation_report.json", coverage_data)

    fixed_now = datetime(2026, 2, 3, 21, 0, 0)
    monkeypatch.setattr(llm_bundle, "_utcnow", lambda: fixed_now)
    monkeypatch.setattr(llm_bundle, "_short_uuid", lambda: "cov02")
    monkeypatch.setattr(llm_bundle, "_run_rag_queries", _fake_rag_queries)

    exit_code = llm_bundle.main(["--user", "@HereWeGo446", "--no-devlog"])
    assert exit_code == 0

    bundle_path = (
        tmp_path / "kb" / "users" / user_slug / "llm_bundles" / "2026-02-03" / "cov02" / "bundle.md"
    )
    bundle_text = bundle_path.read_text(encoding="utf-8")

    assert "## Coverage & Reconciliation" in bundle_text
    assert "[file_path:" in bundle_text
    assert "coverage_reconciliation_report.json" in bundle_text
    # Deterministic summary lines
    assert "Positions: 42" in bundle_text
    assert "Fallback UID coverage: 100.00%" in bundle_text
    assert "All rows have fees_source=unknown" in bundle_text


def test_bundle_rag_unavailable_still_succeeds(tmp_path, monkeypatch):
    """When RAG is unavailable, llm-bundle still exits 0 with coverage section."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "kb").mkdir()

    user_slug = "herewego446"
    _base, latest_dir = _setup_dossier_dirs(tmp_path, user_slug)

    # Add a scan run with coverage md
    scan_dir = _base / "0xabc" / "2026-02-03" / "scanrun"
    _write_json(scan_dir / "run_manifest.json", {
        "command_name": "scan",
        "started_at": "2026-02-03T15:00:00Z",
    })
    _write_text(
        scan_dir / "coverage_reconciliation_report.md",
        "Positions: 50\nFallback UID coverage: 100.00%",
    )

    fixed_now = datetime(2026, 2, 3, 21, 0, 0)
    monkeypatch.setattr(llm_bundle, "_utcnow", lambda: fixed_now)
    monkeypatch.setattr(llm_bundle, "_short_uuid", lambda: "norag1")

    # Simulate RAG unavailable
    monkeypatch.setattr(llm_bundle, "_RAG_AVAILABLE", False)

    exit_code = llm_bundle.main(["--user", "@HereWeGo446", "--no-devlog"])
    assert exit_code == 0

    bundle_path = (
        tmp_path / "kb" / "users" / user_slug / "llm_bundles" / "2026-02-03" / "norag1" / "bundle.md"
    )
    bundle_text = bundle_path.read_text(encoding="utf-8")

    # Coverage section should still be present
    assert "## Coverage & Reconciliation" in bundle_text
    assert "Positions: 50" in bundle_text
    assert "Fallback UID coverage: 100.00%" in bundle_text

    # RAG section should note unavailability
    assert "RAG unavailable; excerpts omitted" in bundle_text

    # Output artifacts should still exist
    rag_path = bundle_path.parent / "rag_queries.json"
    manifest_path = bundle_path.parent / "bundle_manifest.json"
    assert rag_path.exists()
    assert manifest_path.exists()
    # When RAG is unavailable, rag_queries.json must not be silently empty:
    # it should contain template entries with explicit execution_status.
    rag_queries = json.loads(rag_path.read_text(encoding="utf-8"))
    assert isinstance(rag_queries, list)
    assert len(rag_queries) == len(llm_bundle.DEFAULT_QUESTIONS)
    for entry in rag_queries:
        assert entry["execution_status"] == "not_executed"
        assert entry["execution_reason"] == "rag_unavailable"
        assert entry["results"] == []
        assert "question" in entry
        assert "filters" in entry


def test_bundle_no_scan_run_shows_not_found(tmp_path, monkeypatch):
    """When no scan run exists, coverage section shows a not-found note."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "kb").mkdir()

    user_slug = "herewego446"
    _base, latest_dir = _setup_dossier_dirs(tmp_path, user_slug)
    # No run_manifest.json anywhere -> no scan run found

    fixed_now = datetime(2026, 2, 3, 21, 0, 0)
    monkeypatch.setattr(llm_bundle, "_utcnow", lambda: fixed_now)
    monkeypatch.setattr(llm_bundle, "_short_uuid", lambda: "noscan")
    monkeypatch.setattr(llm_bundle, "_run_rag_queries", _fake_rag_queries)

    exit_code = llm_bundle.main(["--user", "@HereWeGo446", "--no-devlog"])
    assert exit_code == 0

    bundle_path = (
        tmp_path / "kb" / "users" / user_slug / "llm_bundles" / "2026-02-03" / "noscan" / "bundle.md"
    )
    bundle_text = bundle_path.read_text(encoding="utf-8")

    assert "## Coverage & Reconciliation" in bundle_text
    assert "Coverage report not found" in bundle_text


def test_llm_bundle_supports_run_manifest_json(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "kb").mkdir()

    user_slug = "herewego446"
    base = tmp_path / "artifacts" / "dossiers" / "users" / user_slug

    older_dir = base / "0xabc" / "2026-02-01" / "oldrun"
    _write_text(older_dir / "memo.md", "old memo")
    _write_text(older_dir / "dossier.json", '{"old": true}')
    _write_json(older_dir / "manifest.json", {"created_at_utc": "2026-02-01T00:00:00Z"})

    latest_dir = base / "0xabc" / "2026-02-03" / "newrun"
    _write_text(latest_dir / "memo.md", "new memo")
    _write_text(latest_dir / "dossier.json", '{"new": true}')
    _write_json(
        latest_dir / "run_manifest.json",
        {"created_at_utc": "2026-02-03T12:00:00Z", "started_at": "2026-02-03T12:00:00Z"},
    )

    fixed_now = datetime(2026, 2, 3, 21, 0, 0)
    monkeypatch.setattr(llm_bundle, "_utcnow", lambda: fixed_now)
    monkeypatch.setattr(llm_bundle, "_short_uuid", lambda: "runnew1")
    monkeypatch.setattr(llm_bundle, "_run_rag_queries", _fake_rag_queries)

    exit_code = llm_bundle.main(["--user", "@HereWeGo446", "--no-devlog"])
    assert exit_code == 0

    bundle_path = (
        tmp_path / "kb" / "users" / user_slug / "llm_bundles" / "2026-02-03" / "runnew1" / "bundle.md"
    )
    bundle_text = bundle_path.read_text(encoding="utf-8")
    assert "## run_manifest.json" in bundle_text
    assert "new memo" in bundle_text
    assert "old memo" not in bundle_text


def test_llm_bundle_run_root_wins_over_user_lookup(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "kb").mkdir()

    user_slug = "herewego446"
    _setup_dossier_dirs(tmp_path, user_slug)

    override_dir = tmp_path / "custom_run" / "manual_run"
    _write_text(override_dir / "memo.md", "override memo")
    _write_text(override_dir / "dossier.json", '{"override": true}')
    _write_json(override_dir / "run_manifest.json", {"created_at_utc": "2026-02-01T00:00:00Z"})

    fixed_now = datetime(2026, 2, 3, 21, 0, 0)
    monkeypatch.setattr(llm_bundle, "_utcnow", lambda: fixed_now)
    monkeypatch.setattr(llm_bundle, "_short_uuid", lambda: "runroot1")
    monkeypatch.setattr(llm_bundle, "_run_rag_queries", _fake_rag_queries)

    exit_code = llm_bundle.main(
        ["--user", "@HereWeGo446", "--run-root", str(override_dir), "--no-devlog"]
    )
    assert exit_code == 0

    bundle_path = (
        tmp_path / "kb" / "users" / user_slug / "llm_bundles" / "2026-02-03" / "runroot1" / "bundle.md"
    )
    bundle_text = bundle_path.read_text(encoding="utf-8")
    assert "override memo" in bundle_text
    assert "new memo" not in bundle_text


def test_llm_bundle_errors_when_manifest_missing(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "kb").mkdir()

    user_slug = "herewego446"
    run_dir = tmp_path / "artifacts" / "dossiers" / "users" / user_slug / "0xabc" / "2026-02-03" / "newrun"
    _write_text(run_dir / "memo.md", "memo only")
    _write_text(run_dir / "dossier.json", '{"new": true}')

    exit_code = llm_bundle.main(["--user", "@HereWeGo446", "--no-devlog"])
    assert exit_code == 1

    err = capsys.readouterr().err
    assert "run_manifest.json" in err
    assert "manifest.json" in err
    assert "export-dossier" in err
    assert "--run-root" in err


# ---------------------------------------------------------------------------
# RAG de-noising filter tests
# ---------------------------------------------------------------------------

class TestIsBundleArtifact:
    def test_rag_queries_json_excluded(self):
        assert llm_bundle._is_bundle_artifact(
            "kb/users/herewego446/llm_bundles/2026-03-04/abc12345/rag_queries.json"
        )

    def test_prompt_txt_excluded(self):
        assert llm_bundle._is_bundle_artifact(
            "kb/users/trader99/llm_bundles/2026-01-01/deadbeef/prompt.txt"
        )

    def test_bundle_md_excluded(self):
        assert llm_bundle._is_bundle_artifact(
            "kb/users/alice/llm_bundles/2025-12-31/feed1234/bundle.md"
        )

    def test_dossier_notes_not_excluded(self):
        assert not llm_bundle._is_bundle_artifact(
            "kb/users/herewego446/notes/2026-02-02.md"
        )

    def test_dossier_json_not_excluded(self):
        assert not llm_bundle._is_bundle_artifact(
            "artifacts/dossiers/users/herewego446/0xabc/2026-02-03/newrun/dossier.json"
        )

    def test_bundle_manifest_json_not_excluded(self):
        # bundle_manifest.json is not in the exclusion list (it's provenance, not evidence)
        assert not llm_bundle._is_bundle_artifact(
            "kb/users/herewego446/llm_bundles/2026-03-04/abc12345/bundle_manifest.json"
        )

    def test_empty_path_not_excluded(self):
        assert not llm_bundle._is_bundle_artifact("")


class TestCollectExcerptsDenoising:
    def _make_result(self, file_path: str, chunk_id: str = "c1") -> dict:
        return {"file_path": file_path, "chunk_id": chunk_id, "doc_id": "d1", "snippet": "x"}

    def _make_payload(self, results: list) -> dict:
        return {"results": results}

    def test_clean_results_pass_through(self):
        payloads = [
            self._make_payload([
                self._make_result("kb/users/alice/notes/note.md", "c1"),
                self._make_result("artifacts/dossiers/users/alice/run/dossier.json", "c2"),
            ])
        ]
        excerpts, filtered = llm_bundle._collect_excerpts(payloads)
        assert filtered == 0
        assert len(excerpts) == 2

    def test_rag_queries_json_filtered(self):
        payloads = [
            self._make_payload([
                self._make_result("kb/users/alice/llm_bundles/2026-03-04/abc/rag_queries.json", "c1"),
                self._make_result("kb/users/alice/notes/note.md", "c2"),
            ])
        ]
        excerpts, filtered = llm_bundle._collect_excerpts(payloads)
        assert filtered == 1
        assert len(excerpts) == 1
        assert excerpts[0]["file_path"] == "kb/users/alice/notes/note.md"

    def test_prompt_txt_filtered(self):
        payloads = [
            self._make_payload([
                self._make_result("kb/users/alice/llm_bundles/2026-01-01/run1/prompt.txt", "c1"),
            ])
        ]
        excerpts, filtered = llm_bundle._collect_excerpts(payloads)
        assert filtered == 1
        assert excerpts == []

    def test_bundle_md_filtered(self):
        payloads = [
            self._make_payload([
                self._make_result("kb/users/alice/llm_bundles/2026-03-04/run2/bundle.md", "c1"),
            ])
        ]
        excerpts, filtered = llm_bundle._collect_excerpts(payloads)
        assert filtered == 1
        assert excerpts == []

    def test_multiple_artifact_types_all_filtered(self):
        payloads = [
            self._make_payload([
                self._make_result("kb/users/alice/llm_bundles/2026-03-04/r/rag_queries.json", "c1"),
                self._make_result("kb/users/alice/llm_bundles/2026-03-04/r/prompt.txt", "c2"),
                self._make_result("kb/users/alice/llm_bundles/2026-03-04/r/bundle.md", "c3"),
                self._make_result("kb/users/alice/notes/real_note.md", "c4"),
            ])
        ]
        excerpts, filtered = llm_bundle._collect_excerpts(payloads)
        assert filtered == 3
        assert len(excerpts) == 1
        assert excerpts[0]["file_path"] == "kb/users/alice/notes/real_note.md"

    def test_empty_payloads(self):
        excerpts, filtered = llm_bundle._collect_excerpts([])
        assert excerpts == []
        assert filtered == 0


def test_bundle_selected_excerpts_never_contain_bundle_artifacts(tmp_path, monkeypatch):
    """Integration test: selected_excerpts in bundle_manifest.json must not contain bundle artifact paths."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "kb").mkdir()

    user_slug = "herewego446"
    _setup_dossier_dirs(tmp_path, user_slug)

    def _fake_rag_with_artifacts(questions, settings, user_slug, prefixes):
        return [
            {
                "question": questions[0]["question"],
                "k": settings.k,
                "mode": "hybrid+rerank",
                "filters": {},
                "results": [
                    # These should be filtered out:
                    {
                        "file_path": f"kb/users/{user_slug}/llm_bundles/2026-03-04/oldrun/rag_queries.json",
                        "chunk_id": "bad1",
                        "doc_id": "d1",
                        "snippet": "old rag query log",
                    },
                    {
                        "file_path": f"kb/users/{user_slug}/llm_bundles/2026-03-04/oldrun/prompt.txt",
                        "chunk_id": "bad2",
                        "doc_id": "d2",
                        "snippet": "old prompt",
                    },
                    {
                        "file_path": f"kb/users/{user_slug}/llm_bundles/2026-03-04/oldrun/bundle.md",
                        "chunk_id": "bad3",
                        "doc_id": "d3",
                        "snippet": "old bundle",
                    },
                    # This should pass through:
                    {
                        "file_path": f"kb/users/{user_slug}/notes/legit_note.md",
                        "chunk_id": "good1",
                        "doc_id": "d4",
                        "snippet": "real evidence",
                    },
                ],
            }
        ]

    fixed_now = datetime(2026, 3, 4, 10, 0, 0)
    monkeypatch.setattr(llm_bundle, "_utcnow", lambda: fixed_now)
    monkeypatch.setattr(llm_bundle, "_short_uuid", lambda: "denoise1")
    monkeypatch.setattr(llm_bundle, "_run_rag_queries", _fake_rag_with_artifacts)

    exit_code = llm_bundle.main(["--user", "@HereWeGo446", "--no-devlog"])
    assert exit_code == 0

    manifest_path = (
        tmp_path / "kb" / "users" / user_slug / "llm_bundles" / "2026-03-04" / "denoise1" / "bundle_manifest.json"
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    # Verify filtered count is recorded
    assert manifest.get("rag_denoise_filtered_count") == 3

    # Verify no bundle artifact paths appear in selected_excerpts
    selected_paths = {e["file_path"] for e in manifest["selected_excerpts"]}
    for path in selected_paths:
        assert not llm_bundle._is_bundle_artifact(path), (
            f"Bundle artifact path leaked into selected_excerpts: {path}"
        )

    # The legit note should be present
    assert f"kb/users/{user_slug}/notes/legit_note.md" in selected_paths

    # Bundle text should not contain the artifact snippets
    bundle_text = (
        tmp_path / "kb" / "users" / user_slug / "llm_bundles" / "2026-03-04" / "denoise1" / "bundle.md"
    ).read_text(encoding="utf-8")
    assert "old rag query log" not in bundle_text
    assert "old prompt" not in bundle_text
    assert "old bundle" not in bundle_text
    assert "real evidence" in bundle_text


# ---------------------------------------------------------------------------
# Report stub tests
# ---------------------------------------------------------------------------

def test_report_stub_created_on_bundle_run(tmp_path, monkeypatch):
    """llm-bundle creates a report stub in kb/users/<slug>/reports/<date>/<bundle_id>_report.md."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "kb").mkdir()

    user_slug = "herewego446"
    _setup_dossier_dirs(tmp_path, user_slug)

    fixed_now = datetime(2026, 3, 5, 12, 0, 0)
    monkeypatch.setattr(llm_bundle, "_utcnow", lambda: fixed_now)
    monkeypatch.setattr(llm_bundle, "_short_uuid", lambda: "rep00001")
    monkeypatch.setattr(llm_bundle, "_run_rag_queries", _fake_rag_queries)

    exit_code = llm_bundle.main(["--user", "@HereWeGo446", "--no-devlog"])
    assert exit_code == 0

    stub_path = (
        tmp_path / "kb" / "users" / user_slug / "reports" / "2026-03-05" / "rep00001_report.md"
    )
    assert stub_path.exists(), f"Report stub not found at {stub_path}"

    content = stub_path.read_text(encoding="utf-8")
    assert "## Executive Summary" in content
    assert "## Data Quality / Coverage Gaps" in content
    assert "## Findings" in content
    assert "## Hypotheses" in content
    assert "## Next Experiments" in content
    assert "## Go/No-Go (research-only)" in content
    assert "rep00001" in content
    assert user_slug in content
    assert "bundle_id" in content
    assert "generated_at" in content
    assert "bundle.md" in content
    assert "memo_filled.md" in content
    assert "Cite evidence anchors" in content


def test_report_stub_idempotent_on_rerun(tmp_path, monkeypatch):
    """Running llm-bundle twice with the same bundle_id overwrites cleanly without error."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "kb").mkdir()

    user_slug = "herewego446"
    _setup_dossier_dirs(tmp_path, user_slug)

    fixed_now = datetime(2026, 3, 5, 12, 0, 0)
    monkeypatch.setattr(llm_bundle, "_utcnow", lambda: fixed_now)
    monkeypatch.setattr(llm_bundle, "_short_uuid", lambda: "idem0001")
    monkeypatch.setattr(llm_bundle, "_run_rag_queries", _fake_rag_queries)

    # First run creates the stub
    assert llm_bundle.main(["--user", "@HereWeGo446", "--no-devlog"]) == 0

    stub_path = (
        tmp_path / "kb" / "users" / user_slug / "reports" / "2026-03-05" / "idem0001_report.md"
    )
    assert stub_path.exists()
    stub_path.write_text("user edited content", encoding="utf-8")

    # Second run with same UUID must not crash (idempotent overwrite)
    assert llm_bundle.main(["--user", "@HereWeGo446", "--no-devlog"]) == 0
    # File is overwritten with the template (not the user content)
    content = stub_path.read_text(encoding="utf-8")
    assert "## Executive Summary" in content


def test_bundle_manifest_no_denoise_field_when_nothing_filtered(tmp_path, monkeypatch):
    """When no filtering occurs, rag_denoise_filtered_count is absent from manifest."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "kb").mkdir()

    user_slug = "herewego446"
    _setup_dossier_dirs(tmp_path, user_slug)

    fixed_now = datetime(2026, 3, 4, 10, 0, 0)
    monkeypatch.setattr(llm_bundle, "_utcnow", lambda: fixed_now)
    monkeypatch.setattr(llm_bundle, "_short_uuid", lambda: "nofilt1")
    monkeypatch.setattr(llm_bundle, "_run_rag_queries", _fake_rag_queries)

    exit_code = llm_bundle.main(["--user", "@HereWeGo446", "--no-devlog"])
    assert exit_code == 0

    manifest_path = (
        tmp_path / "kb" / "users" / user_slug / "llm_bundles" / "2026-03-04" / "nofilt1" / "bundle_manifest.json"
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert "rag_denoise_filtered_count" not in manifest
