"""Deterministic tests for the DR-1 scan on/off/status toggle (scripts/scan.sh).

These tests assert the SAFETY-CRITICAL properties of the wrapper without
requiring Docker:

  1. ``on``  emits exactly ``docker compose up -d clickhouse api discovery-scheduler``.
  2. ``off`` emits exactly ``docker compose stop discovery-scheduler`` (and stops
     ONLY the scheduler — ClickHouse/API are not stopped).
  3. The wrapper NEVER contains ``docker compose down`` and NEVER passes ``-v`` /
     ``--volumes`` (the central DR-1 safety property).
  4. A teardown token (``down``, ``-v``, ``--volumes``) passed through the wrapper
     is actively REFUSED (non-zero exit), proven by invoking the script under
     bash when available.

The wrapper is pure shell, so (1)-(3) are asserted by parsing the script text
(a deterministic, Docker-free contract check). (4) is asserted by executing the
refusal branch under bash; if bash is unavailable on the runner the live
invocation is skipped but the static refusal-branch assertion still holds.
"""
from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SCAN_SH = _REPO_ROOT / "scripts" / "scan.sh"
_SCAN_STATUS_PY = _REPO_ROOT / "scripts" / "scan_status.py"


@pytest.fixture(scope="module")
def script_text() -> str:
    assert _SCAN_SH.exists(), f"missing wrapper: {_SCAN_SH}"
    return _SCAN_SH.read_text(encoding="utf-8")


# --------------------------------------------------------------------------- #
# Exact command-string contract
# --------------------------------------------------------------------------- #

def test_on_emits_exact_up_command(script_text: str) -> None:
    """`on` must bring up exactly the three day-run services with `up -d`."""
    # SERVICES array + the up invocation together produce the exact command.
    assert "SERVICES=(clickhouse api discovery-scheduler)" in script_text
    assert 'docker compose up -d "${SERVICES[@]}"' in script_text


def test_off_emits_exact_stop_command(script_text: str) -> None:
    """`off` must stop ONLY the scheduler."""
    assert 'SCHEDULER_SERVICE="discovery-scheduler"' in script_text
    assert 'docker compose stop "${SCHEDULER_SERVICE}"' in script_text


def _executable_lines(script_text: str) -> list[str]:
    """Return only executable shell lines (drop comments and heredoc/usage text).

    Comments (``#``) and the ``usage()`` heredoc DOCUMENT the guardrail (they
    deliberately mention ``down`` / ``-v`` to warn operators). The safety
    assertions below must look only at lines that actually *invoke* docker
    compose, i.e. lines containing ``docker compose`` that are not comments.
    """
    out: list[str] = []
    in_heredoc = False
    for ln in script_text.splitlines():
        stripped = ln.strip()
        # Heredoc body (cat <<'EOF' ... EOF) is documentation text, not code.
        if in_heredoc:
            if stripped == "EOF":
                in_heredoc = False
            continue
        if "<<'EOF'" in stripped or '<<"EOF"' in stripped or stripped.endswith("<<EOF"):
            in_heredoc = True
            continue
        if stripped.startswith("#"):
            continue
        out.append(ln)
    return out


def _executable_compose_invocations(script_text: str) -> list[str]:
    """Executable lines that actually run `docker compose ...`.

    Excludes echo/print lines and heredoc body lines (which only document the
    commands for the operator).
    """
    result: list[str] = []
    for ln in _executable_lines(script_text):
        stripped = ln.strip()
        if "docker compose" not in stripped:
            continue
        # Skip lines that merely echo/document a command rather than run it.
        if stripped.startswith(("echo", "cat", '"', "'", "->", "EOF")):
            continue
        if stripped.lstrip().startswith("-> docker compose"):
            continue
        result.append(stripped)
    return result


def test_off_does_not_stop_clickhouse_or_api(script_text: str) -> None:
    """`off` must never stop clickhouse or api (data store survives off)."""
    # The only EXECUTED `docker compose stop` targets SCHEDULER_SERVICE.
    stop_lines = [
        ln for ln in _executable_compose_invocations(script_text)
        if "compose stop" in ln
    ]
    assert stop_lines, "expected an executed `docker compose stop` line"
    for ln in stop_lines:
        assert "SCHEDULER_SERVICE" in ln, f"stop must target only the scheduler: {ln!r}"
        assert "clickhouse" not in ln
        assert "api" not in ln


# --------------------------------------------------------------------------- #
# Guardrail: never `down`, never `-v`
# --------------------------------------------------------------------------- #

def test_wrapper_never_executes_compose_down(script_text: str) -> None:
    """No EXECUTED code path invokes `docker compose down`.

    The guardrail/usage text deliberately mentions `down` to warn operators;
    those are comments/heredoc lines and are excluded. Here we assert no line
    that actually runs `docker compose` invokes `down`.
    """
    for ln in _executable_compose_invocations(script_text):
        assert not re.search(r"docker\s+compose\s+down", ln), (
            f"FORBIDDEN: executable line invokes `docker compose down`: {ln!r}"
        )


def test_wrapper_never_executes_volume_flag(script_text: str) -> None:
    """No EXECUTED docker compose line passes `-v` / `--volumes`."""
    for ln in _executable_compose_invocations(script_text):
        assert not re.search(r"\s-v(\s|$)", ln), (
            f"FORBIDDEN: executable line passes `-v`: {ln!r}"
        )
        assert "--volumes" not in ln, (
            f"FORBIDDEN: executable line passes `--volumes`: {ln!r}"
        )


def test_refusal_branch_lists_teardown_tokens(script_text: str) -> None:
    """The refuse_teardown branch must guard the teardown/volume tokens."""
    assert "refuse_teardown()" in script_text
    # The case pattern that triggers refusal must include these tokens.
    assert "down|-v|--volumes" in script_text


# --------------------------------------------------------------------------- #
# Live refusal (bash) — skipped if bash unavailable
# --------------------------------------------------------------------------- #

@pytest.fixture(scope="module")
def bash_path() -> str | None:
    return shutil.which("bash")


@pytest.mark.parametrize("token", ["down", "-v", "--volumes"])
def test_teardown_token_is_refused_live(bash_path, token) -> None:
    """Invoking the wrapper with a teardown token must exit non-zero (refused)."""
    if not bash_path:
        pytest.skip("bash not available on this runner")
    proc = subprocess.run(
        [bash_path, str(_SCAN_SH), token],
        cwd=str(_REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert proc.returncode != 0, (
        f"teardown token {token!r} must be refused (non-zero exit); "
        f"stdout={proc.stdout!r} stderr={proc.stderr!r}"
    )
    assert "REFUSED" in (proc.stdout + proc.stderr)


def test_unknown_command_exits_nonzero(bash_path) -> None:
    if not bash_path:
        pytest.skip("bash not available on this runner")
    proc = subprocess.run(
        [bash_path, str(_SCAN_SH), "bogus"],
        cwd=str(_REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert proc.returncode != 0


# --------------------------------------------------------------------------- #
# scan_status.py: reuses existing readers, no new SQL, read-only
# --------------------------------------------------------------------------- #

def test_status_reader_reuses_existing_functions() -> None:
    """scan_status must import the existing readers, not define new SQL."""
    text = _SCAN_STATUS_PY.read_text(encoding="utf-8")
    assert "from packages.polymarket.discovery.scan_queue import ScanQueueManager" in text
    assert (
        "from packages.polymarket.discovery.clickhouse_writer import (\n            read_pending_candidates,\n        )"
        in text
        or "read_pending_candidates" in text
    )
    # No hand-rolled SQL in the status helper (the imported readers own the SQL).
    # Look for actual query shapes, not the English word "selects" in prose.
    assert "FORMAT JSONEachRow" not in text, "status helper must not write its own SQL"
    assert "FROM polytool." not in text, "status helper must not write its own SQL"


def test_status_reader_imports_and_runs_without_creds(monkeypatch) -> None:
    """With no CLICKHOUSE_PASSWORD, status is state-only and returns 0 (no raise)."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("scan_status", _SCAN_STATUS_PY)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    monkeypatch.delenv("CLICKHOUSE_PASSWORD", raising=False)
    rc = mod._read_clickhouse_counts()
    assert rc == 0
