"""Studio session manager for running SimTrader jobs concurrently."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

SESSION_KINDS = {"shadow", "run", "sweep", "batch", "ondemand"}
TERMINAL_STATUSES = {"succeeded", "failed", "terminated", "stopped"}
RUNNING_STATUSES = {"starting", "running", "terminating"}

_ORDERS_RE = re.compile(r"\bOrders:\s*(\d+)\b", re.IGNORECASE)
_FILLS_RE = re.compile(r"\bFills:\s*(\d+)\b", re.IGNORECASE)
_NET_PNL_RE = re.compile(
    r"\bNet(?:\s+profit|\s+pnl)?\s*:\s*([+-]?\d+(?:\.\d+)?)\b",
    re.IGNORECASE,
)
_NET_PNL_JSON_RE = re.compile(
    r'"net_profit"\s*:\s*"?([+-]?\d+(?:\.\d+)?)"?',
    re.IGNORECASE,
)

_ARTIFACT_LINE_PATTERNS = (
    re.compile(r"^\[simtrader run\]\s*run dir\s*:\s*(?P<path>.+)$", re.IGNORECASE),
    re.compile(r"^\[shadow\]\s*run dir\s*:\s*(?P<path>.+)$", re.IGNORECASE),
    re.compile(r"^\[simtrader sweep\]\s*sweep dir\s*:\s*(?P<path>.+)$", re.IGNORECASE),
    re.compile(r"^\[quickrun sweep\]\s*sweep dir\s*:\s*(?P<path>.+)$", re.IGNORECASE),
    re.compile(r"^Sweep complete:\s*(?P<path>.+)$", re.IGNORECASE),
    re.compile(r"^\s*Run dir\s*:\s*(?P<path>artifacts/simtrader/\S+)\s*$", re.IGNORECASE),
    re.compile(r"^\s*Batch dir\s*:\s*(?P<path>\S+)\s*$", re.IGNORECASE),
    re.compile(r"^\s*Tape dir\s*:\s*(?P<path>artifacts/simtrader/\S+)\s*$", re.IGNORECASE),
)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_session_id() -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{ts}_{uuid.uuid4().hex[:8]}"


def _pid_exists(pid: int | None) -> bool:
    if pid is None or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _resolve_simtrader_artifacts_root(explicit_root: Path | None) -> Path:
    if explicit_root is not None:
        root = Path(explicit_root)
    else:
        env_root = os.getenv("POLYTOOL_ARTIFACTS_ROOT")
        if env_root:
            root = Path(env_root) / "simtrader"
        else:
            root = Path("artifacts") / "simtrader"
    return root.resolve()


@dataclass(slots=True)
class StudioSessionRecord:
    session_id: str
    kind: str
    subcommand: str
    status: str
    started_at: str
    artifact_dir: Path | None
    args: list[str]
    pid: int | None
    exit_reason: str | None
    session_dir: Path
    log_path: Path
    command: list[str]
    counters: dict[str, int | float | None] = field(
        default_factory=lambda: {"orders": None, "fills": None, "net_pnl": None}
    )
    ended_at: str | None = None
    return_code: int | None = None

    def to_manifest(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "kind": self.kind,
            "subcommand": self.subcommand,
            "status": self.status,
            "started_at": self.started_at,
            "artifact_dir": str(self.artifact_dir) if self.artifact_dir is not None else None,
            "args": list(self.args),
            "pid": self.pid,
            "exit_reason": self.exit_reason,
            "session_dir": str(self.session_dir),
            "log_path": str(self.log_path),
            "command": list(self.command),
            "counters": dict(self.counters),
            "ended_at": self.ended_at,
            "return_code": self.return_code,
            "updated_at": _utc_now_iso(),
        }

    def to_snapshot(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "kind": self.kind,
            "subcommand": self.subcommand,
            "status": self.status,
            "started_at": self.started_at,
            "artifact_dir": str(self.artifact_dir) if self.artifact_dir is not None else None,
            "args": list(self.args),
            "pid": self.pid,
            "exit_reason": self.exit_reason,
            "log_path": str(self.log_path),
            "counters": dict(self.counters),
            "ended_at": self.ended_at,
            "return_code": self.return_code,
        }


CommandBuilder = Callable[[str, list[str]], list[str]]


class StudioSessionManager:
    """Run and track multiple SimTrader subprocess sessions."""

    def __init__(
        self,
        artifacts_root: Path | None = None,
        command_builder: CommandBuilder | None = None,
    ) -> None:
        self._artifacts_root = _resolve_simtrader_artifacts_root(artifacts_root)
        self._sessions_root = self._artifacts_root / "studio_sessions"
        self._sessions_root.mkdir(parents=True, exist_ok=True)
        self._command_builder = command_builder or self._default_command_builder
        self._lock = threading.RLock()
        self._sessions: dict[str, StudioSessionRecord] = {}
        self._processes: dict[str, subprocess.Popen[str]] = {}
        self._kill_requested: set[str] = set()
        self._load_existing_manifests()

    @property
    def artifacts_root(self) -> Path:
        return self._artifacts_root

    @property
    def sessions_root(self) -> Path:
        return self._sessions_root

    def list_sessions(self) -> list[dict[str, Any]]:
        with self._lock:
            ordered = sorted(
                self._sessions.values(),
                key=lambda row: row.started_at,
                reverse=True,
            )
            return [row.to_snapshot() for row in ordered]

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._sessions.get(session_id)
            if row is None:
                return None
            return row.to_snapshot()

    def start_session(
        self,
        kind: str,
        args: list[str] | None = None,
        subcommand: str | None = None,
    ) -> dict[str, Any]:
        kind_norm = str(kind).strip().lower()
        if kind_norm not in SESSION_KINDS:
            known = ", ".join(sorted(SESSION_KINDS))
            raise ValueError(f"Unsupported kind {kind!r}. Expected one of: {known}")

        raw_args = [str(x) for x in (args or [])]
        session_id = _safe_session_id()

        effective_subcommand, effective_args, artifact_dir = self._prepare_invocation(
            kind=kind_norm,
            args=raw_args,
            subcommand=subcommand,
            session_id=session_id,
        )
        command = self._command_builder(effective_subcommand, effective_args)
        if not command:
            raise ValueError("Command builder returned an empty command.")

        session_dir = self._sessions_root / session_id
        log_path = session_dir / "logs.txt"
        session_dir.mkdir(parents=True, exist_ok=True)
        log_path.touch(exist_ok=True)

        row = StudioSessionRecord(
            session_id=session_id,
            kind=kind_norm,
            subcommand=effective_subcommand,
            status="starting",
            started_at=_utc_now_iso(),
            artifact_dir=artifact_dir,
            args=effective_args,
            pid=None,
            exit_reason=None,
            session_dir=session_dir,
            log_path=log_path,
            command=list(command),
        )

        with self._lock:
            self._sessions[session_id] = row
            self._write_manifest_locked(row)

        worker = threading.Thread(
            target=self._run_session_worker,
            args=(session_id,),
            daemon=True,
        )
        worker.start()
        return row.to_snapshot()

    def kill_session(self, session_id: str, force: bool = False) -> dict[str, Any]:
        with self._lock:
            row = self._sessions.get(session_id)
            if row is None:
                raise KeyError(f"Unknown session_id: {session_id}")
            proc = self._processes.get(session_id)
            if proc is None or proc.poll() is not None:
                return row.to_snapshot()
            self._kill_requested.add(session_id)
            row.status = "terminating"
            row.exit_reason = "kill_requested"
            self._write_manifest_locked(row)

        try:
            if force:
                proc.kill()
            else:
                proc.terminate()
        except OSError:
            # Process may have already exited between poll() and terminate().
            pass

        with self._lock:
            latest = self._sessions.get(session_id)
            if latest is None:
                raise KeyError(f"Unknown session_id: {session_id}")
            return latest.to_snapshot()

    def read_log_chunk(self, session_id: str, offset: int) -> tuple[int, list[str]]:
        with self._lock:
            row = self._sessions.get(session_id)
            if row is None:
                raise KeyError(f"Unknown session_id: {session_id}")
            log_path = row.log_path

        if offset < 0:
            offset = 0
        if not log_path.exists():
            return offset, []

        lines: list[str] = []
        with log_path.open("r", encoding="utf-8", errors="replace") as fh:
            fh.seek(offset)
            while True:
                line = fh.readline()
                if line == "":
                    break
                lines.append(line.rstrip("\r\n"))
            new_offset = fh.tell()
        return new_offset, lines

    def _prepare_invocation(
        self,
        kind: str,
        args: list[str],
        subcommand: str | None,
        session_id: str,
    ) -> tuple[str, list[str], Path | None]:
        effective_args = list(args)
        artifact_dir: Path | None = None

        if kind == "ondemand":
            if subcommand is not None and subcommand.strip():
                effective_subcommand = subcommand.strip()
            elif effective_args:
                effective_subcommand = effective_args.pop(0)
            else:
                raise ValueError("kind='ondemand' requires subcommand or first args entry.")
        else:
            effective_subcommand = kind

        id_binding = {
            "run": ("--run-id", self._artifacts_root / "runs" / session_id),
            "sweep": ("--sweep-id", self._artifacts_root / "sweeps" / session_id),
            "batch": ("--batch-id", self._artifacts_root / "batches" / session_id),
        }.get(effective_subcommand)
        if id_binding is not None:
            flag, target_dir = id_binding
            effective_args.extend([flag, session_id])
            artifact_dir = target_dir

        return effective_subcommand, effective_args, artifact_dir

    def _default_command_builder(self, subcommand: str, args: list[str]) -> list[str]:
        return [sys.executable, "-m", "polytool", "simtrader", subcommand, *args]

    def _run_session_worker(self, session_id: str) -> None:
        with self._lock:
            row = self._sessions.get(session_id)
            if row is None:
                return
            command = list(row.command)
            log_path = row.log_path

        popen_kwargs: dict[str, Any] = {
            "stdout": subprocess.PIPE,
            "stderr": subprocess.STDOUT,
            "text": True,
            "encoding": "utf-8",
            "errors": "replace",
            "bufsize": 1,
        }
        if os.name != "nt":
            popen_kwargs["start_new_session"] = True
        else:
            popen_kwargs["creationflags"] = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)

        try:
            proc = subprocess.Popen(command, **popen_kwargs)  # noqa: S603
        except Exception as exc:  # noqa: BLE001
            with self._lock:
                current = self._sessions.get(session_id)
                if current is None:
                    return
                current.status = "failed"
                current.exit_reason = f"start_failed: {exc}"
                current.ended_at = _utc_now_iso()
                self._write_manifest_locked(current)
            return

        with self._lock:
            current = self._sessions.get(session_id)
            if current is None:
                proc.terminate()
                return
            self._processes[session_id] = proc
            current.pid = proc.pid
            current.status = "running"
            current.exit_reason = None
            self._write_manifest_locked(current)

        with log_path.open("a", encoding="utf-8", buffering=1) as log_file:
            stdout = proc.stdout
            if stdout is not None:
                for line in stdout:
                    log_file.write(line)
                    self._handle_output_line(session_id=session_id, line=line)

        return_code = proc.wait()
        with self._lock:
            current = self._sessions.get(session_id)
            if current is None:
                self._processes.pop(session_id, None)
                self._kill_requested.discard(session_id)
                return

            self._processes.pop(session_id, None)
            kill_requested = session_id in self._kill_requested
            self._kill_requested.discard(session_id)

            current.return_code = return_code
            current.ended_at = _utc_now_iso()
            if kill_requested:
                current.status = "terminated"
                current.exit_reason = "killed"
            elif return_code == 0:
                current.status = "succeeded"
                current.exit_reason = "completed"
            else:
                current.status = "failed"
                current.exit_reason = f"exit_code_{return_code}"
            self._write_manifest_locked(current)

    def _handle_output_line(self, session_id: str, line: str) -> None:
        stripped = line.rstrip("\r\n")
        if not stripped:
            return

        with self._lock:
            row = self._sessions.get(session_id)
            if row is None:
                return

            changed = False
            maybe_artifact = self._extract_artifact_path(stripped)
            if maybe_artifact is not None:
                if self._should_replace_artifact(existing=row.artifact_dir, candidate=maybe_artifact):
                    row.artifact_dir = maybe_artifact
                    changed = True

            orders_match = _ORDERS_RE.search(stripped)
            if orders_match is not None:
                orders_value = int(orders_match.group(1))
                if row.counters.get("orders") != orders_value:
                    row.counters["orders"] = orders_value
                    changed = True

            fills_match = _FILLS_RE.search(stripped)
            if fills_match is not None:
                fills_value = int(fills_match.group(1))
                if row.counters.get("fills") != fills_value:
                    row.counters["fills"] = fills_value
                    changed = True

            net_match = _NET_PNL_RE.search(stripped) or _NET_PNL_JSON_RE.search(stripped)
            if net_match is not None:
                net_value = float(net_match.group(1))
                if row.counters.get("net_pnl") != net_value:
                    row.counters["net_pnl"] = net_value
                    changed = True

            if changed:
                self._write_manifest_locked(row)

    def _extract_artifact_path(self, line: str) -> Path | None:
        for pattern in _ARTIFACT_LINE_PATTERNS:
            match = pattern.search(line)
            if match is None:
                continue
            raw_path = str(match.group("path")).strip().strip('"').strip("'")
            if not raw_path:
                continue
            raw_path = raw_path.rstrip("/\\")
            candidate = Path(raw_path)
            if not candidate.is_absolute():
                candidate = (Path.cwd() / candidate).resolve()
            else:
                candidate = candidate.resolve()
            if not _is_relative_to(candidate, self._artifacts_root):
                continue
            return candidate
        return None

    def _should_replace_artifact(self, existing: Path | None, candidate: Path) -> bool:
        if existing is None:
            return True
        existing_rank = self._artifact_rank(existing)
        candidate_rank = self._artifact_rank(candidate)
        return candidate_rank > existing_rank

    def _artifact_rank(self, path: Path) -> int:
        text = str(path).replace("\\", "/")
        high_priority = ("/runs/", "/sweeps/", "/batches/", "/shadow_runs/")
        if any(part in text for part in high_priority):
            return 2
        if "/tapes/" in text:
            return 1
        return 0

    def _manifest_path(self, row: StudioSessionRecord) -> Path:
        return row.session_dir / "session_manifest.json"

    def _write_manifest_locked(self, row: StudioSessionRecord) -> None:
        manifest_path = self._manifest_path(row)
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = manifest_path.with_suffix(".json.tmp")
        tmp_path.write_text(
            json.dumps(row.to_manifest(), indent=2) + "\n",
            encoding="utf-8",
        )
        tmp_path.replace(manifest_path)

    def _load_existing_manifests(self) -> None:
        for manifest_path in sorted(self._sessions_root.glob("*/session_manifest.json")):
            try:
                payload = json.loads(manifest_path.read_text(encoding="utf-8"))
            except Exception:  # noqa: BLE001
                continue
            if not isinstance(payload, dict):
                continue

            session_id = str(payload.get("session_id") or manifest_path.parent.name)
            kind = str(payload.get("kind") or "ondemand")
            subcommand = str(payload.get("subcommand") or kind)
            status = str(payload.get("status") or "stopped")
            args = [str(x) for x in payload.get("args", []) if isinstance(x, (str, int, float))]
            artifact_raw = payload.get("artifact_dir")
            artifact_dir = (
                Path(artifact_raw)
                if isinstance(artifact_raw, str) and artifact_raw
                else None
            )
            if artifact_dir is not None and not artifact_dir.is_absolute():
                artifact_dir = (Path.cwd() / artifact_dir).resolve()
            log_raw = payload.get("log_path")
            log_path = (
                Path(log_raw)
                if isinstance(log_raw, str) and log_raw
                else manifest_path.parent / "logs.txt"
            )
            if not log_path.is_absolute():
                log_path = (Path.cwd() / log_path).resolve()
            command_raw = payload.get("command")
            command = [str(x) for x in command_raw] if isinstance(command_raw, list) else []

            row = StudioSessionRecord(
                session_id=session_id,
                kind=kind,
                subcommand=subcommand,
                status=status,
                started_at=str(payload.get("started_at") or _utc_now_iso()),
                artifact_dir=artifact_dir,
                args=args,
                pid=payload.get("pid") if isinstance(payload.get("pid"), int) else None,
                exit_reason=payload.get("exit_reason") if isinstance(payload.get("exit_reason"), str) else None,
                session_dir=manifest_path.parent,
                log_path=log_path,
                command=command,
                counters=dict(payload.get("counters") or {"orders": None, "fills": None, "net_pnl": None}),
                ended_at=payload.get("ended_at") if isinstance(payload.get("ended_at"), str) else None,
                return_code=payload.get("return_code") if isinstance(payload.get("return_code"), int) else None,
            )

            if row.status in RUNNING_STATUSES and not _pid_exists(row.pid):
                row.status = "stopped"
                if row.exit_reason is None:
                    row.exit_reason = "process_not_running"
                if row.ended_at is None:
                    row.ended_at = _utc_now_iso()
                self._write_manifest_locked(row)

            self._sessions[row.session_id] = row
