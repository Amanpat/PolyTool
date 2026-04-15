"""Operator-safe launcher for the next Coinbase crypto-pair smoke soak."""

from __future__ import annotations

import dataclasses
import json
import os
import subprocess
import sys
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

from packages.polymarket.crypto_pairs.market_watch import (
    AvailabilitySummary,
    run_watch_loop,
)
from packages.polymarket.crypto_pairs.paper_runner import (
    DEFAULT_KILL_SWITCH_PATH,
)


DEFAULT_AWAIT_SOAK_ARTIFACTS_DIR = Path("artifacts/crypto_pairs/await_soak")
DEFAULT_TIMEOUT_SECONDS = 3600
DEFAULT_POLL_INTERVAL_SECONDS = 60
# Backward-compat alias kept for existing callers/tests
DEFAULT_DURATION_SECONDS = 1800
DEFAULT_SMOKE_DURATION_SECONDS = 1800
DEFAULT_SOAK_DURATION_SECONDS = 86400  # 24 hours — full paper soak
# Backward-compat alias kept for existing callers/tests
DEFAULT_HEARTBEAT_SECONDS = 60
DEFAULT_SOAK_HEARTBEAT_SECONDS = 1800  # 30 minutes — full paper soak
DEFAULT_REFERENCE_FEED_PROVIDER = "coinbase"
AWAIT_SOAK_SCHEMA_VERSION = "crypto_pair_await_soak_v0"


@dataclass(frozen=True)
class AwaitSoakLaunchPlan:
    """Concrete paper smoke-soak command to run once markets are eligible."""

    argv: tuple[str, ...]
    display_argv: tuple[str, ...]
    display_command: str
    duration_seconds: int
    heartbeat_seconds: int
    reference_feed_provider: str
    auto_report: bool = True
    sink_enabled: bool = False
    max_capital_window_usdc: Optional[float] = None


@dataclass(frozen=True)
class AwaitSoakLaunchResult:
    """Observed outcome of the child crypto-pair-run process."""

    exit_code: int
    output_text: str = ""
    launched_run_artifact_dir: Optional[str] = None
    launched_run_manifest_path: Optional[str] = None
    launched_run_summary_path: Optional[str] = None
    launched_run_verdict: Optional[str] = None


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _iso_utc(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat()


def _run_dir(base: Path, date_str: str, run_id: str) -> Path:
    return base / date_str / run_id


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _print_summary(summary: AvailabilitySummary, print_fn: Callable[[str], None]) -> None:
    eligible_str = "yes" if summary.eligible_now else "no"
    print_fn(f"[crypto-pair-await-soak] eligible_now : {eligible_str}")
    print_fn(f"[crypto-pair-await-soak] total_eligible: {summary.total_eligible}")
    print_fn(
        "[crypto-pair-await-soak] by_symbol     : "
        f"BTC={summary.by_symbol.get('BTC', 0)} "
        f"ETH={summary.by_symbol.get('ETH', 0)} "
        f"SOL={summary.by_symbol.get('SOL', 0)}"
    )
    print_fn(
        "[crypto-pair-await-soak] by_duration   : "
        f"5m={summary.by_duration.get('5m', 0)} "
        f"15m={summary.by_duration.get('15m', 0)}"
    )
    print_fn(f"[crypto-pair-await-soak] checked_at    : {summary.checked_at}")
    if summary.first_eligible_slugs:
        print_fn(
            "[crypto-pair-await-soak] first_slugs   : "
            + ", ".join(summary.first_eligible_slugs)
        )
    elif summary.rejection_reason:
        print_fn(
            f"[crypto-pair-await-soak] reason        : {summary.rejection_reason}"
        )


def validate_soak_prerequisites(
    *,
    kill_switch_path: Path = DEFAULT_KILL_SWITCH_PATH,
) -> list[str]:
    """Return a list of blocking issues. Empty list = all clear."""
    issues: list[str] = []
    if kill_switch_path.exists():
        content = kill_switch_path.read_text(encoding="utf-8").strip().lower()
        if content in ("1", "true", "yes", "on"):
            issues.append(
                f"Kill switch is tripped ({kill_switch_path}). "
                f"Clear it before launching: rm {kill_switch_path}"
            )
    return issues


def build_coinbase_smoke_soak_launch_plan(
    *,
    duration_seconds: int = DEFAULT_SOAK_DURATION_SECONDS,
    heartbeat_seconds: int = DEFAULT_SOAK_HEARTBEAT_SECONDS,
    python_executable: Optional[str] = None,
    auto_report: bool = True,
    sink_enabled: bool = False,
    max_capital_window_usdc: Optional[float] = None,
) -> AwaitSoakLaunchPlan:
    """Build the standard paper-only Coinbase smoke-soak command."""

    executable = python_executable or sys.executable or "python"

    # Base argv shared by both real and display variants
    base_args: list[str] = [
        "-m",
        "polytool",
        "crypto-pair-run",
        "--reference-feed-provider",
        DEFAULT_REFERENCE_FEED_PROVIDER,
        "--duration-seconds",
        str(duration_seconds),
        "--heartbeat-seconds",
        str(heartbeat_seconds),
    ]

    # Optional flags appended in deterministic order
    optional_args: list[str] = []
    if auto_report:
        optional_args.append("--auto-report")
    if sink_enabled:
        optional_args.append("--sink-enabled")
    if max_capital_window_usdc is not None:
        optional_args.extend(["--max-capital-window-usdc", str(max_capital_window_usdc)])

    all_base_and_optional = base_args + optional_args

    argv = tuple([executable] + all_base_and_optional)
    display_argv = tuple(["python"] + all_base_and_optional)

    return AwaitSoakLaunchPlan(
        argv=argv,
        display_argv=display_argv,
        display_command=" ".join(display_argv),
        duration_seconds=duration_seconds,
        heartbeat_seconds=heartbeat_seconds,
        reference_feed_provider=DEFAULT_REFERENCE_FEED_PROVIDER,
        auto_report=auto_report,
        sink_enabled=sink_enabled,
        max_capital_window_usdc=max_capital_window_usdc,
    )


def _extract_cli_value(output_lines: list[str], field_name: str) -> Optional[str]:
    prefix = f"[crypto-pair-run] {field_name}"
    for line in output_lines:
        if not line.startswith(prefix):
            continue
        _, _, value = line.partition(":")
        value = value.strip()
        return value or None
    return None


def launch_smoke_soak_subprocess(
    plan: AwaitSoakLaunchPlan,
    *,
    print_fn: Callable[[str], None] = print,
) -> AwaitSoakLaunchResult:
    """Run the child crypto-pair paper soak and tee its output to the operator."""

    process = subprocess.Popen(
        list(plan.argv),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        env={
            **os.environ,
            "PYTHONUNBUFFERED": "1",
        },
    )
    assert process.stdout is not None

    output_lines: list[str] = []
    try:
        for raw_line in process.stdout:
            line = raw_line.rstrip("\r\n")
            output_lines.append(line)
            print_fn(line)
    finally:
        process.stdout.close()

    exit_code = process.wait()
    output_text = "\n".join(output_lines)
    if output_text:
        output_text += "\n"

    verdict = _extract_cli_value(output_lines, "report_verdict")

    return AwaitSoakLaunchResult(
        exit_code=exit_code,
        output_text=output_text,
        launched_run_artifact_dir=_extract_cli_value(output_lines, "artifact_dir"),
        launched_run_manifest_path=_extract_cli_value(output_lines, "manifest_path"),
        launched_run_summary_path=_extract_cli_value(output_lines, "run_summary"),
        launched_run_verdict=verdict,
    )


def _write_launcher_artifacts(
    *,
    run_dir: Path,
    summary: AvailabilitySummary,
    manifest: dict[str, Any],
    launch_output_text: str,
) -> None:
    _write_json(run_dir / "availability_summary.json", dataclasses.asdict(summary))
    if launch_output_text:
        _write_text(run_dir / "launch_output.log", launch_output_text)
        manifest["launch_output_ref"] = str(run_dir / "launch_output.log")
    _write_json(run_dir / "launcher_manifest.json", manifest)


def run_crypto_pair_await_soak(
    *,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    poll_interval_seconds: int = DEFAULT_POLL_INTERVAL_SECONDS,
    duration_seconds: int = DEFAULT_SOAK_DURATION_SECONDS,
    heartbeat_seconds: int = DEFAULT_SOAK_HEARTBEAT_SECONDS,
    output_base: Optional[Path] = None,
    gamma_client=None,
    python_executable: Optional[str] = None,
    auto_report: bool = True,
    sink_enabled: bool = False,
    max_capital_window_usdc: Optional[float] = None,
    kill_switch_path: Optional[Path] = None,
    _watch_fn: Optional[Callable[..., tuple[bool, AvailabilitySummary]]] = None,
    _launcher_fn: Optional[Callable[[AwaitSoakLaunchPlan], AwaitSoakLaunchResult]] = None,
    _sleep_fn: Optional[Callable[[float], None]] = None,
    _check_fn: Optional[Callable[[], AvailabilitySummary]] = None,
    _print_fn: Callable[[str], None] = print,
    _validate_fn: Optional[Callable[..., list[str]]] = None,
) -> dict[str, Any]:
    """Wait for eligible markets, then launch the standard paper smoke soak."""

    if timeout_seconds < 0:
        raise ValueError("timeout_seconds must be >= 0")
    if poll_interval_seconds <= 0:
        raise ValueError("poll_interval_seconds must be > 0")
    if duration_seconds < 0:
        raise ValueError("duration_seconds must be >= 0")
    if heartbeat_seconds <= 0:
        raise ValueError("heartbeat_seconds must be > 0")

    now = _utcnow()
    date_str = now.date().isoformat()
    run_id = uuid.uuid4().hex[:12]
    base_dir = output_base or DEFAULT_AWAIT_SOAK_ARTIFACTS_DIR
    run_dir = _run_dir(base_dir, date_str, run_id)
    generated_at = _iso_utc(now)

    watch_fn = _watch_fn or run_watch_loop
    launcher_fn = _launcher_fn or (
        lambda plan: launch_smoke_soak_subprocess(plan, print_fn=_print_fn)
    )
    validate_fn = _validate_fn or validate_soak_prerequisites
    resolved_kill_switch_path = kill_switch_path or DEFAULT_KILL_SWITCH_PATH

    _print_fn(
        "[crypto-pair-await-soak] waiting for eligible markets "
        f"(poll every {poll_interval_seconds}s, timeout {timeout_seconds}s)..."
    )
    found, summary = watch_fn(
        poll_interval_seconds=poll_interval_seconds,
        timeout_seconds=timeout_seconds,
        gamma_client=gamma_client,
        _sleep_fn=_sleep_fn,
        _check_fn=_check_fn,
    )
    _print_summary(summary, _print_fn)

    manifest: dict[str, Any] = {
        "schema_version": AWAIT_SOAK_SCHEMA_VERSION,
        "run_id": run_id,
        "generated_at": generated_at,
        "artifact_dir": str(run_dir),
        "availability_summary_ref": str(run_dir / "availability_summary.json"),
        "status": "timed_out",
        "wait": {
            "eligible_found": found,
            "poll_interval_seconds": poll_interval_seconds,
            "timeout_seconds": timeout_seconds,
        },
        "launch": {
            "launched": False,
            "reference_feed_provider": DEFAULT_REFERENCE_FEED_PROVIDER,
            "duration_seconds": duration_seconds,
            "heartbeat_seconds": heartbeat_seconds,
            "command": None,
            "command_argv": None,
            "exit_code": None,
            "run_artifact_dir": None,
            "run_manifest_path": None,
            "run_summary_path": None,
            "preflight_issues": None,
            "launched_run_verdict": None,
            "launched_run_verdict_json_path": None,
            "error": None,
        },
    }

    if not found:
        _write_launcher_artifacts(
            run_dir=run_dir,
            summary=summary,
            manifest=manifest,
            launch_output_text="",
        )
        _print_fn(
            f"[crypto-pair-await-soak] timeout reached after {timeout_seconds}s. "
            "No soak launched."
        )
        _print_fn(f"[crypto-pair-await-soak] launcher_manifest: {run_dir / 'launcher_manifest.json'}")
        manifest["exit_code"] = 1
        return manifest

    # Preflight: check kill switch before launching
    preflight_issues = validate_fn(kill_switch_path=resolved_kill_switch_path)
    if preflight_issues:
        manifest["status"] = "preflight_failed"
        manifest["launch"]["preflight_issues"] = preflight_issues
        for issue in preflight_issues:
            _print_fn(f"[crypto-pair-await-soak] preflight_fail: {issue}")
        _write_launcher_artifacts(
            run_dir=run_dir,
            summary=summary,
            manifest=manifest,
            launch_output_text="",
        )
        _print_fn(
            f"[crypto-pair-await-soak] launcher_manifest: {run_dir / 'launcher_manifest.json'}"
        )
        manifest["exit_code"] = 1
        return manifest

    plan = build_coinbase_smoke_soak_launch_plan(
        duration_seconds=duration_seconds,
        heartbeat_seconds=heartbeat_seconds,
        python_executable=python_executable,
        auto_report=auto_report,
        sink_enabled=sink_enabled,
        max_capital_window_usdc=max_capital_window_usdc,
    )
    manifest["status"] = "launched"
    manifest["launch"]["launched"] = True
    manifest["launch"]["command"] = plan.display_command
    manifest["launch"]["command_argv"] = list(plan.display_argv)

    _print_fn(f"[crypto-pair-await-soak] launching     : {plan.display_command}")
    try:
        launch_result = launcher_fn(plan)
    except Exception as exc:
        manifest["status"] = "launch_failed"
        manifest["launch"]["error"] = f"{type(exc).__name__}: {exc}"
        manifest["launch"]["exit_code"] = 1
        _write_launcher_artifacts(
            run_dir=run_dir,
            summary=summary,
            manifest=manifest,
            launch_output_text="",
        )
        _print_fn(
            f"[crypto-pair-await-soak] launch failed : {type(exc).__name__}: {exc}"
        )
        _print_fn(
            f"[crypto-pair-await-soak] launcher_manifest: {run_dir / 'launcher_manifest.json'}"
        )
        manifest["exit_code"] = 1
        return manifest

    manifest["launch"]["exit_code"] = launch_result.exit_code
    manifest["launch"]["run_artifact_dir"] = launch_result.launched_run_artifact_dir
    manifest["launch"]["run_manifest_path"] = launch_result.launched_run_manifest_path
    manifest["launch"]["run_summary_path"] = launch_result.launched_run_summary_path

    # Extract verdict from child output
    verdict = launch_result.launched_run_verdict
    verdict_json_path: Optional[str] = None
    if launch_result.launched_run_artifact_dir:
        verdict_json_path = str(
            Path(launch_result.launched_run_artifact_dir) / "paper_soak_verdict.json"
        )
    manifest["launch"]["launched_run_verdict"] = verdict
    manifest["launch"]["launched_run_verdict_json_path"] = verdict_json_path

    if launch_result.exit_code != 0:
        manifest["status"] = "launch_failed"

    _write_launcher_artifacts(
        run_dir=run_dir,
        summary=summary,
        manifest=manifest,
        launch_output_text=launch_result.output_text,
    )
    _print_fn(
        f"[crypto-pair-await-soak] child_exit_code: {launch_result.exit_code}"
    )
    if launch_result.launched_run_artifact_dir:
        _print_fn(
            "[crypto-pair-await-soak] run_artifact   : "
            f"{launch_result.launched_run_artifact_dir}"
        )
    if verdict:
        _print_fn(f"[crypto-pair-await-soak] verdict       : {verdict}")
    if verdict_json_path:
        _print_fn(f"[crypto-pair-await-soak] verdict_json  : {verdict_json_path}")
    _print_fn(f"[crypto-pair-await-soak] launcher_manifest: {run_dir / 'launcher_manifest.json'}")

    manifest["exit_code"] = launch_result.exit_code
    return manifest
