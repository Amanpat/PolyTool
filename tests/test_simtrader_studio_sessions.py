from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from packages.polymarket.simtrader.studio_sessions import (
    TERMINAL_STATUSES,
    StudioSessionManager,
)


def _wait_for_terminal(
    manager: StudioSessionManager,
    session_id: str,
    timeout_seconds: float = 10.0,
) -> dict:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        session = manager.get_session(session_id)
        if session is None:
            raise AssertionError(f"session disappeared: {session_id}")
        if session["status"] in TERMINAL_STATUSES:
            return session
        time.sleep(0.05)
    raise AssertionError(f"session did not reach terminal state: {session_id}")


def test_session_lifecycle_log_capture_and_manifest_reload(tmp_path: Path) -> None:
    artifacts_root = tmp_path / "artifacts" / "simtrader"
    shadow_dir = (artifacts_root / "shadow_runs" / "shadow-unit").resolve()

    script = (
        "import sys\n"
        f"print('[shadow] run dir  : {shadow_dir.as_posix()}')\n"
        "print('Decisions  : 5   Orders: 4   Fills: 3')\n"
        "print('Net profit : 1.25')\n"
        "sys.stdout.flush()\n"
    )

    def command_builder(subcommand: str, args: list[str]) -> list[str]:
        assert subcommand == "shadow"
        return [sys.executable, "-u", "-c", script]

    manager = StudioSessionManager(artifacts_root=artifacts_root, command_builder=command_builder)
    started = manager.start_session(kind="shadow", args=["--market", "ignored"])
    session_id = started["session_id"]

    finished = _wait_for_terminal(manager, session_id)
    assert finished["status"] == "succeeded"
    assert finished["artifact_dir"] == str(shadow_dir)
    assert finished["counters"]["orders"] == 4
    assert finished["counters"]["fills"] == 3
    assert finished["counters"]["net_pnl"] == 1.25

    _, lines = manager.read_log_chunk(session_id, 0)
    assert any("Orders: 4" in line for line in lines)
    assert any("Net profit : 1.25" in line for line in lines)

    manifest_path = artifacts_root / "studio_sessions" / session_id / "session_manifest.json"
    assert manifest_path.exists()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["session_id"] == session_id
    assert manifest["kind"] == "shadow"
    assert manifest["status"] == "succeeded"
    assert manifest["artifact_dir"] == str(shadow_dir)

    reloaded = StudioSessionManager(artifacts_root=artifacts_root, command_builder=command_builder)
    restored = reloaded.get_session(session_id)
    assert restored is not None
    assert restored["status"] == "succeeded"
    assert restored["artifact_dir"] == str(shadow_dir)


def test_run_session_has_explicit_artifact_binding_and_can_be_killed(tmp_path: Path) -> None:
    artifacts_root = tmp_path / "artifacts" / "simtrader"
    captured: dict[str, object] = {}

    def command_builder(subcommand: str, args: list[str]) -> list[str]:
        captured["subcommand"] = subcommand
        captured["args"] = list(args)
        run_id = ""
        for idx, token in enumerate(args):
            if token == "--run-id" and idx + 1 < len(args):
                run_id = args[idx + 1]
                break
        assert run_id, "expected --run-id to be injected"
        run_dir = (artifacts_root / "runs" / run_id).resolve()
        script = (
            "import sys,time\n"
            f"print('[simtrader run] run dir        : {run_dir.as_posix()}')\n"
            "sys.stdout.flush()\n"
            "time.sleep(30)\n"
        )
        return [sys.executable, "-u", "-c", script]

    manager = StudioSessionManager(artifacts_root=artifacts_root, command_builder=command_builder)
    started = manager.start_session(kind="run", args=["--tape", "ignored.jsonl", "--strategy", "noop"])
    session_id = started["session_id"]

    assert started["artifact_dir"] == str((artifacts_root / "runs" / session_id).resolve())
    assert captured.get("subcommand") == "run"
    assert "--run-id" in list(captured.get("args", []))
    assert session_id in list(captured.get("args", []))

    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline:
        current = manager.get_session(session_id)
        assert current is not None
        if current["status"] == "running":
            break
        time.sleep(0.05)
    else:
        raise AssertionError("session did not become running")

    manager.kill_session(session_id)
    finished = _wait_for_terminal(manager, session_id)
    assert finished["status"] == "terminated"
    assert finished["exit_reason"] == "killed"
    assert finished["pid"] is not None

    _, lines = manager.read_log_chunk(session_id, 0)
    assert any("run dir" in line.lower() for line in lines)
