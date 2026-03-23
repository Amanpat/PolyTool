import io
import json
import os
import sys
from datetime import datetime
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "packages"))

from tools.cli import llm_save


def _write_text(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def test_llm_save_writes_layout_and_manifest(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "kb").mkdir()
    (tmp_path / "docs").mkdir()

    report_path = tmp_path / "report.md"
    prompt_path = tmp_path / "prompt.md"
    _write_text(report_path, "report body")
    _write_text(prompt_path, "prompt body")

    fixed_now = datetime(2026, 2, 3, 12, 0, 0)
    monkeypatch.setattr(llm_save, "_utcnow", lambda: fixed_now)

    exit_code = llm_save.main([
        "--user", "@HereWeGo446",
        "--model", "Opus 4.5 Turbo",
        "--run-id", "run123",
        "--date", "2026-02-03",
        "--report-path", str(report_path),
        "--prompt-path", str(prompt_path),
        "--input", "inputs/a.csv",
        "--input", "inputs/b.json",
        "--tags", "alpha, beta",
    ])

    assert exit_code == 0

    expected_dir = (
        tmp_path
        / "kb"
        / "users"
        / "herewego446"
        / "llm_reports"
        / "2026-02-03"
        / "opus_4_5_turbo_run123"
    )

    assert expected_dir.exists()
    assert (expected_dir / "report.md").read_text(encoding="utf-8") == "report body"
    assert not (expected_dir / "prompt.txt").exists()

    manifest = json.loads((expected_dir / "inputs_manifest.json").read_text(encoding="utf-8"))
    assert manifest["model"] == "Opus 4.5 Turbo"
    assert manifest["model_slug"] == "opus_4_5_turbo"
    assert manifest["run_id"] == "run123"
    assert manifest["created_at_utc"] == "2026-02-03T12:00:00Z"
    assert manifest["user_slug"] == "herewego446"
    assert manifest["input_paths"] == ["inputs/a.csv", "inputs/b.json"]
    assert manifest["tags"] == ["alpha", "beta"]

    devlog_path = (
        tmp_path
        / "kb"
        / "devlog"
        / "2026-02-03_llm_save_herewego446_opus_4_5_turbo_run123.md"
    )
    devlog_text = devlog_path.read_text(encoding="utf-8")
    assert "prompt body" in devlog_text
    assert "model_slug: opus_4_5_turbo" in devlog_text
    assert "Report path: kb/users/herewego446/llm_reports/2026-02-03/opus_4_5_turbo_run123/report.md" in devlog_text


def test_llm_save_accepts_user_without_at(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "kb").mkdir()

    report_path = tmp_path / "report.md"
    prompt_path = tmp_path / "prompt.md"
    _write_text(report_path, "report")
    _write_text(prompt_path, "prompt")

    fixed_now = datetime(2026, 2, 3, 9, 30, 0)
    monkeypatch.setattr(llm_save, "_utcnow", lambda: fixed_now)

    exit_code = llm_save.main([
        "--user", "HereWeGo446",
        "--model", "opus45",
        "--run-id", "run456",
        "--date", "2026-02-03",
        "--report-path", str(report_path),
        "--prompt-path", str(prompt_path),
    ])

    assert exit_code == 0

    expected_dir = (
        tmp_path
        / "kb"
        / "users"
        / "herewego446"
        / "llm_reports"
        / "2026-02-03"
        / "opus45_run456"
    )
    assert expected_dir.exists()
    assert not (expected_dir / "prompt.txt").exists()


def test_llm_save_reads_prompt_from_stdin(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "kb").mkdir()

    report_path = tmp_path / "report.md"
    _write_text(report_path, "report from file")

    fixed_now = datetime(2026, 2, 3, 15, 0, 0)
    monkeypatch.setattr(llm_save, "_utcnow", lambda: fixed_now)
    monkeypatch.setattr(sys, "stdin", io.StringIO("prompt from stdin"))

    exit_code = llm_save.main([
        "--user", "@Tester",
        "--model", "opus45",
        "--run-id", "stdin123",
        "--date", "2026-02-03",
        "--report-path", str(report_path),
    ])

    assert exit_code == 0

    expected_dir = (
        tmp_path
        / "kb"
        / "users"
        / "tester"
        / "llm_reports"
        / "2026-02-03"
        / "opus45_stdin123"
    )
    assert not (expected_dir / "prompt.txt").exists()
    devlog_path = (
        tmp_path
        / "kb"
        / "devlog"
        / "2026-02-03_llm_save_tester_opus45_stdin123.md"
    )
    devlog_text = devlog_path.read_text(encoding="utf-8")
    assert "prompt from stdin" in devlog_text


def test_llm_save_errors_when_both_paths_missing(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "kb").mkdir()

    fixed_now = datetime(2026, 2, 3, 18, 0, 0)
    monkeypatch.setattr(llm_save, "_utcnow", lambda: fixed_now)

    exit_code = llm_save.main([
        "--user", "@Tester",
        "--model", "opus45",
    ])

    assert exit_code == 1
    captured = capsys.readouterr()
    assert "report" in captured.err.lower()
    assert "prompt" in captured.err.lower()


def test_llm_save_never_writes_to_docs(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "kb").mkdir()

    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    sentinel = docs_dir / "sentinel.txt"
    _write_text(sentinel, "keep")

    report_path = tmp_path / "report.md"
    prompt_path = tmp_path / "prompt.md"
    _write_text(report_path, "report")
    _write_text(prompt_path, "prompt")

    fixed_now = datetime(2026, 2, 3, 20, 0, 0)
    monkeypatch.setattr(llm_save, "_utcnow", lambda: fixed_now)

    exit_code = llm_save.main([
        "--user", "@Tester",
        "--model", "opus45",
        "--run-id", "nodocs",
        "--date", "2026-02-03",
        "--report-path", str(report_path),
        "--prompt-path", str(prompt_path),
    ])

    assert exit_code == 0
    doc_files = [path for path in docs_dir.rglob("*") if path.is_file()]
    assert doc_files == [sentinel]


# ── hypothesis-path behavior ───────────────────────────────────────────────────

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


def _write_hypothesis(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _base_args(tmp_path: Path) -> list:
    report_path = tmp_path / "report.md"
    prompt_path = tmp_path / "prompt.md"
    _write_text(report_path, "report")
    _write_text(prompt_path, "prompt")
    return [
        "--user", "@Tester",
        "--model", "opus45",
        "--run-id", "hyp001",
        "--date", "2026-03-11",
        "--report-path", str(report_path),
        "--prompt-path", str(prompt_path),
        "--no-devlog",
    ]


def test_llm_save_hypothesis_valid_writes_artifacts(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "kb").mkdir()
    monkeypatch.setattr(llm_save, "_utcnow", lambda: datetime(2026, 3, 11, 0, 0, 0))

    hyp_path = tmp_path / "hypothesis.json"
    _write_hypothesis(hyp_path, _minimal_valid_hypothesis())

    exit_code = llm_save.main(_base_args(tmp_path) + ["--hypothesis-path", str(hyp_path)])
    assert exit_code == 0

    out_dir = tmp_path / "kb" / "users" / "tester" / "llm_reports" / "2026-03-11" / "opus45_hyp001"
    assert (out_dir / "hypothesis.json").exists()
    vr = json.loads((out_dir / "validation_result.json").read_text(encoding="utf-8"))
    assert vr["valid"] is True
    assert vr["errors"] == []


def test_llm_save_hypothesis_schema_invalid_exits_0_and_writes_both(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "kb").mkdir()
    monkeypatch.setattr(llm_save, "_utcnow", lambda: datetime(2026, 3, 11, 0, 0, 0))

    bad_hyp = _minimal_valid_hypothesis()
    bad_hyp["schema_version"] = "wrong_version"
    hyp_path = tmp_path / "hypothesis.json"
    _write_hypothesis(hyp_path, bad_hyp)

    exit_code = llm_save.main(_base_args(tmp_path) + ["--hypothesis-path", str(hyp_path)])
    assert exit_code == 0  # schema-invalid but parseable: does not block save

    out_dir = tmp_path / "kb" / "users" / "tester" / "llm_reports" / "2026-03-11" / "opus45_hyp001"
    assert (out_dir / "hypothesis.json").exists()  # parseable JSON persisted
    vr = json.loads((out_dir / "validation_result.json").read_text(encoding="utf-8"))
    assert vr["valid"] is False
    assert len(vr["errors"]) > 0

    captured = capsys.readouterr()
    assert "validation error" in captured.err.lower() or "schema_version" in captured.err


def test_llm_save_hypothesis_malformed_json_exits_1_no_hypothesis_json(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "kb").mkdir()
    monkeypatch.setattr(llm_save, "_utcnow", lambda: datetime(2026, 3, 11, 0, 0, 0))

    hyp_path = tmp_path / "hypothesis.json"
    hyp_path.write_text("{not valid json", encoding="utf-8")

    exit_code = llm_save.main(_base_args(tmp_path) + ["--hypothesis-path", str(hyp_path)])
    assert exit_code == 1

    out_dir = tmp_path / "kb" / "users" / "tester" / "llm_reports" / "2026-03-11" / "opus45_hyp001"
    assert not (out_dir / "hypothesis.json").exists()  # malformed: must NOT be persisted
    vr = json.loads((out_dir / "validation_result.json").read_text(encoding="utf-8"))
    assert vr["valid"] is False
    assert any("parsed" in e.lower() or "json" in e.lower() for e in vr["errors"])

    captured = capsys.readouterr()
    assert "error" in captured.err.lower()


def test_llm_save_hypothesis_unreadable_path_exits_1(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "kb").mkdir()
    monkeypatch.setattr(llm_save, "_utcnow", lambda: datetime(2026, 3, 11, 0, 0, 0))

    missing_path = tmp_path / "does_not_exist.json"

    exit_code = llm_save.main(_base_args(tmp_path) + ["--hypothesis-path", str(missing_path)])
    assert exit_code == 1

    out_dir = tmp_path / "kb" / "users" / "tester" / "llm_reports" / "2026-03-11" / "opus45_hyp001"
    assert not (out_dir / "hypothesis.json").exists()
    vr = json.loads((out_dir / "validation_result.json").read_text(encoding="utf-8"))
    assert vr["valid"] is False

    captured = capsys.readouterr()
    assert "error" in captured.err.lower()
