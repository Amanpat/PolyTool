"""WP2-J: CLI truth-sync tests for research-eval.

Tests verify:
- list-providers output accurately separates implemented vs unimplemented
- list-providers shows routing config state
- --provider openai / --provider anthropic → "not yet implemented" error (rc=1)
  regardless of whether cloud guard is set
- --provider gemini / --provider deepseek without cloud guard → cloud guard error (rc=1)
- compare subcommand: both manual providers → rc=0, produces gate comparison
- compare subcommand: unimplemented provider in either slot → rc=1, clear error
- compare --json output format
- compare with cloud provider without guard → cloud guard error (rc=1)
"""

from __future__ import annotations

import io
import json
import os


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run_main(argv: list, monkeypatch=None) -> tuple[int, str, str]:
    """Run research_eval.main(argv) and capture stdout + stderr.

    Returns (rc, stdout_text, stderr_text).
    """
    import sys
    from tools.cli import research_eval

    stdout_buf = io.StringIO()
    stderr_buf = io.StringIO()

    orig_stdout = sys.stdout
    orig_stderr = sys.stderr
    sys.stdout = stdout_buf
    sys.stderr = stderr_buf

    try:
        rc = research_eval.main(argv)
    finally:
        sys.stdout = orig_stdout
        sys.stderr = orig_stderr

    return rc, stdout_buf.getvalue(), stderr_buf.getvalue()


def _make_body() -> str:
    return (
        "This analysis covers prediction market microstructure, spread dynamics, "
        "inventory risk, and calibration details relevant to a market-making system."
    )


# ---------------------------------------------------------------------------
# list-providers: section accuracy
# ---------------------------------------------------------------------------

def test_list_providers_shows_implemented_cloud(monkeypatch):
    """list-providers output contains gemini and deepseek in implemented cloud section."""
    monkeypatch.delenv("RIS_ENABLE_CLOUD_PROVIDERS", raising=False)
    rc, out, _ = _run_main(["list-providers"])
    assert rc == 0
    # Both implemented cloud providers present
    assert "gemini" in out
    assert "deepseek" in out


def test_list_providers_shows_unimplemented_cloud(monkeypatch):
    """list-providers output contains openai and anthropic in not-yet-implemented section."""
    monkeypatch.delenv("RIS_ENABLE_CLOUD_PROVIDERS", raising=False)
    rc, out, _ = _run_main(["list-providers"])
    assert rc == 0
    assert "openai" in out
    assert "anthropic" in out
    # Both must be marked as not yet implemented
    assert "not yet implemented" in out


def test_list_providers_separates_local_and_cloud(monkeypatch):
    """list-providers output has separate local and cloud sections."""
    monkeypatch.delenv("RIS_ENABLE_CLOUD_PROVIDERS", raising=False)
    rc, out, _ = _run_main(["list-providers"])
    assert rc == 0
    assert "manual" in out
    assert "ollama" in out
    # Local section appears before cloud section
    local_pos = out.index("manual")
    cloud_pos = out.index("gemini")
    assert local_pos < cloud_pos


def test_list_providers_shows_routing_config(monkeypatch):
    """list-providers output includes routing config (mode, primary, escalation)."""
    monkeypatch.delenv("RIS_ENABLE_CLOUD_PROVIDERS", raising=False)
    from packages.research.evaluation.config import reset_eval_config
    reset_eval_config()
    try:
        rc, out, _ = _run_main(["list-providers"])
        assert rc == 0
        assert "mode" in out
        assert "primary_provider" in out or "primary" in out
    finally:
        reset_eval_config()


def test_list_providers_cloud_guard_status_not_set(monkeypatch):
    """list-providers shows cloud guard as not set when env var absent."""
    monkeypatch.delenv("RIS_ENABLE_CLOUD_PROVIDERS", raising=False)
    rc, out, _ = _run_main(["list-providers"])
    assert rc == 0
    assert "not set" in out


def test_list_providers_cloud_guard_status_set(monkeypatch):
    """list-providers shows cloud guard as SET when env var is present."""
    monkeypatch.setenv("RIS_ENABLE_CLOUD_PROVIDERS", "1")
    rc, out, _ = _run_main(["list-providers"])
    assert rc == 0
    assert "SET" in out


# ---------------------------------------------------------------------------
# _check_provider_guard: unimplemented providers blocked before cloud guard
# ---------------------------------------------------------------------------

def test_provider_openai_blocked_without_cloud_guard(monkeypatch):
    """--provider openai without cloud guard → rc=1, 'not yet implemented' message."""
    monkeypatch.delenv("RIS_ENABLE_CLOUD_PROVIDERS", raising=False)
    rc, _, err = _run_main(
        ["eval", "--provider", "openai", "--title", "T", "--body", _make_body()]
    )
    assert rc == 1
    assert "not yet implemented" in err


def test_provider_anthropic_blocked_without_cloud_guard(monkeypatch):
    """--provider anthropic without cloud guard → rc=1, 'not yet implemented' message."""
    monkeypatch.delenv("RIS_ENABLE_CLOUD_PROVIDERS", raising=False)
    rc, _, err = _run_main(
        ["eval", "--provider", "anthropic", "--title", "T", "--body", _make_body()]
    )
    assert rc == 1
    assert "not yet implemented" in err


def test_provider_openai_blocked_even_with_cloud_guard(monkeypatch):
    """--provider openai WITH cloud guard → rc=1, 'not yet implemented' (intercepted before backend)."""
    monkeypatch.setenv("RIS_ENABLE_CLOUD_PROVIDERS", "1")
    rc, _, err = _run_main(
        ["eval", "--provider", "openai", "--enable-cloud", "--title", "T", "--body", _make_body()]
    )
    assert rc == 1
    assert "not yet implemented" in err


def test_provider_anthropic_blocked_even_with_cloud_guard(monkeypatch):
    """--provider anthropic WITH cloud guard → rc=1, 'not yet implemented' (intercepted before backend)."""
    monkeypatch.setenv("RIS_ENABLE_CLOUD_PROVIDERS", "1")
    rc, _, err = _run_main(
        ["eval", "--provider", "anthropic", "--enable-cloud", "--title", "T", "--body", _make_body()]
    )
    assert rc == 1
    assert "not yet implemented" in err


# ---------------------------------------------------------------------------
# _check_provider_guard: implemented cloud providers need the guard
# ---------------------------------------------------------------------------

def test_provider_gemini_blocked_without_cloud_guard(monkeypatch):
    """--provider gemini without cloud guard → rc=1, cloud guard error (not 'not yet implemented')."""
    monkeypatch.delenv("RIS_ENABLE_CLOUD_PROVIDERS", raising=False)
    rc, _, err = _run_main(
        ["eval", "--provider", "gemini", "--title", "T", "--body", _make_body()]
    )
    assert rc == 1
    # Should get cloud guard message, NOT the "not yet implemented" message
    assert "not yet implemented" not in err
    assert "requires opt-in" in err or "cloud provider" in err.lower()


def test_provider_deepseek_blocked_without_cloud_guard(monkeypatch):
    """--provider deepseek without cloud guard → rc=1, cloud guard error."""
    monkeypatch.delenv("RIS_ENABLE_CLOUD_PROVIDERS", raising=False)
    rc, _, err = _run_main(
        ["eval", "--provider", "deepseek", "--title", "T", "--body", _make_body()]
    )
    assert rc == 1
    assert "not yet implemented" not in err
    assert "requires opt-in" in err or "cloud provider" in err.lower()


# ---------------------------------------------------------------------------
# compare subcommand: basic correctness
# ---------------------------------------------------------------------------

def test_compare_both_manual_succeeds(monkeypatch, tmp_path):
    """compare with manual+manual → rc=0 and output contains gate results for both."""
    monkeypatch.delenv("RIS_ENABLE_CLOUD_PROVIDERS", raising=False)
    rc, out, _ = _run_main([
        "compare",
        "--provider-a", "manual",
        "--provider-b", "manual",
        "--title", "Test Doc",
        "--body", _make_body(),
    ])
    assert rc == 0
    assert "Gate=" in out or "gate" in out.lower()


def test_compare_gate_changed_field_present(monkeypatch):
    """compare output always contains gate-changed indicator."""
    monkeypatch.delenv("RIS_ENABLE_CLOUD_PROVIDERS", raising=False)
    rc, out, _ = _run_main([
        "compare",
        "--provider-a", "manual",
        "--provider-b", "manual",
        "--title", "Test Doc",
        "--body", _make_body(),
    ])
    assert rc == 0
    assert "Gate changed" in out or "gate_changed" in out


def test_compare_json_output_structure(monkeypatch):
    """compare --json → valid JSON with required keys."""
    monkeypatch.delenv("RIS_ENABLE_CLOUD_PROVIDERS", raising=False)
    rc, out, _ = _run_main([
        "compare",
        "--provider-a", "manual",
        "--provider-b", "manual",
        "--title", "Test Doc",
        "--body", _make_body(),
        "--json",
    ])
    assert rc == 0
    data = json.loads(out)
    assert "provider_a" in data
    assert "provider_b" in data
    assert "gate_a" in data
    assert "gate_b" in data
    assert "gate_changed" in data
    assert "dim_diffs" in data
    assert data["provider_a"] == "manual"
    assert data["provider_b"] == "manual"


def test_compare_json_gate_changed_bool(monkeypatch):
    """compare --json: gate_changed is a bool, same provider produces gate_changed=false."""
    monkeypatch.delenv("RIS_ENABLE_CLOUD_PROVIDERS", raising=False)
    rc, out, _ = _run_main([
        "compare",
        "--provider-a", "manual",
        "--provider-b", "manual",
        "--title", "Test Doc",
        "--body", _make_body(),
        "--json",
    ])
    assert rc == 0
    data = json.loads(out)
    assert isinstance(data["gate_changed"], bool)
    # Same provider → same result → gate_changed must be false
    assert data["gate_changed"] is False


# ---------------------------------------------------------------------------
# compare subcommand: unimplemented provider rejection
# ---------------------------------------------------------------------------

def test_compare_openai_in_slot_a_blocked(monkeypatch):
    """compare --provider-a openai → rc=1, 'not yet implemented'."""
    monkeypatch.delenv("RIS_ENABLE_CLOUD_PROVIDERS", raising=False)
    rc, _, err = _run_main([
        "compare",
        "--provider-a", "openai",
        "--provider-b", "manual",
        "--title", "T",
        "--body", _make_body(),
    ])
    assert rc == 1
    assert "not yet implemented" in err


def test_compare_anthropic_in_slot_b_blocked(monkeypatch):
    """compare --provider-b anthropic → rc=1, 'not yet implemented'."""
    monkeypatch.delenv("RIS_ENABLE_CLOUD_PROVIDERS", raising=False)
    rc, _, err = _run_main([
        "compare",
        "--provider-a", "manual",
        "--provider-b", "anthropic",
        "--title", "T",
        "--body", _make_body(),
    ])
    assert rc == 1
    assert "not yet implemented" in err


def test_compare_unimplemented_blocked_even_with_cloud_guard(monkeypatch):
    """compare with unimplemented + cloud guard → rc=1, 'not yet implemented' not cloud guard msg."""
    monkeypatch.setenv("RIS_ENABLE_CLOUD_PROVIDERS", "1")
    rc, _, err = _run_main([
        "compare",
        "--provider-a", "openai",
        "--provider-b", "manual",
        "--enable-cloud",
        "--title", "T",
        "--body", _make_body(),
    ])
    assert rc == 1
    assert "not yet implemented" in err


# ---------------------------------------------------------------------------
# compare subcommand: cloud guard on implemented cloud provider
# ---------------------------------------------------------------------------

def test_compare_gemini_without_guard_blocked(monkeypatch):
    """compare --provider-a gemini without cloud guard → rc=1, cloud guard error."""
    monkeypatch.delenv("RIS_ENABLE_CLOUD_PROVIDERS", raising=False)
    rc, _, err = _run_main([
        "compare",
        "--provider-a", "gemini",
        "--provider-b", "manual",
        "--title", "T",
        "--body", _make_body(),
    ])
    assert rc == 1
    assert "not yet implemented" not in err
    assert "requires opt-in" in err or "cloud provider" in err.lower()


# ---------------------------------------------------------------------------
# compare subcommand: no args shows help
# ---------------------------------------------------------------------------

def test_compare_no_args_shows_help():
    """compare with no args → rc=1 (missing required args)."""
    rc, _, _ = _run_main(["compare"])
    assert rc == 1
