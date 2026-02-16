import json
import os
import sys
from datetime import datetime
from pathlib import Path

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
    assert "new memo" in bundle_text
    assert "[file_path: kb/users/herewego446/notes/2026-02-02.md]" in bundle_text

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["created_at_utc"] == "2026-02-03T21:00:00Z"
    assert manifest["user_slug"] == user_slug
    assert manifest["run_id"] == "run123"
    assert isinstance(manifest["model_hint"], str)
    assert manifest["dossier_path"] == "artifacts/dossiers/users/herewego446/0xabc/2026-02-03/newrun"
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
    rag_queries = json.loads(rag_path.read_text(encoding="utf-8"))
    assert rag_queries == []


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
