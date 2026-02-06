import hashlib
import io
import os
import re
import sys
from datetime import datetime

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tools.cli import agent_run


def test_agent_run_writes_devlog_from_stdin(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    fixed_now = datetime(2026, 2, 4, 12, 0, 0)
    monkeypatch.setattr(agent_run, "_utcnow", lambda: fixed_now)
    monkeypatch.setattr(sys, "stdin", io.StringIO("Hello prompt"))

    exit_code = agent_run.main([
        "--agent", "codex",
        "--packet", "Packet-9",
        "--slug", "My Fancy Run!!",
        "--scope", "docs",
    ])

    assert exit_code == 0

    expected_path = (
        tmp_path
        / "kb"
        / "devlog"
        / "2026-02-04_codex_packet-9_my_fancy_run.md"
    )

    assert expected_path.exists()
    content = expected_path.read_text(encoding="utf-8")

    expected_hash = hashlib.sha256("Hello prompt".encode("utf-8")).hexdigest()
    assert f"prompt_sha256: {expected_hash}" in content
    assert "Hello prompt" in content
    assert re.search(r"run_id: [0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", content)


def test_agent_run_creates_kb_spec_with_prompt(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    fixed_now = datetime(2026, 2, 4, 13, 0, 0)
    monkeypatch.setattr(agent_run, "_utcnow", lambda: fixed_now)
    monkeypatch.setattr(sys, "stdin", io.StringIO("Spec prompt body"))

    exit_code = agent_run.main([
        "--agent", "codex",
        "--packet", "P2",
        "--slug", "Spec Run",
        "--spec", "kb",
    ])

    assert exit_code == 0

    spec_path = tmp_path / "kb" / "specs" / "2026-02-04_p2_spec_run.md"
    assert spec_path.exists()
    spec_text = spec_path.read_text(encoding="utf-8")
    assert "Spec prompt body" in spec_text

    devlog_path = tmp_path / "kb" / "devlog" / "2026-02-04_codex_p2_spec_run.md"
    devlog_text = devlog_path.read_text(encoding="utf-8")
    assert "spec_path: kb/specs/2026-02-04_p2_spec_run.md" in devlog_text


def test_agent_run_creates_docs_spec_without_prompt(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    fixed_now = datetime(2026, 2, 4, 14, 0, 0)
    monkeypatch.setattr(agent_run, "_utcnow", lambda: fixed_now)
    monkeypatch.setattr(sys, "stdin", io.StringIO("Secret prompt contents"))

    exit_code = agent_run.main([
        "--agent", "claude",
        "--packet", "P3",
        "--slug", "Docs Spec",
        "--spec", "docs",
    ])

    assert exit_code == 0

    spec_path = tmp_path / "docs" / "specs" / "2026-02-04_p3_docs_spec.md"
    assert spec_path.exists()
    spec_text = spec_path.read_text(encoding="utf-8")
    assert "Secret prompt contents" not in spec_text
    assert "Prompt stored in devlog" in spec_text

    devlog_path = tmp_path / "kb" / "devlog" / "2026-02-04_claude_p3_docs_spec.md"
    devlog_text = devlog_path.read_text(encoding="utf-8")
    assert "spec_path: docs/specs/2026-02-04_p3_docs_spec.md" in devlog_text
