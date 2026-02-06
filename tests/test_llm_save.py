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
