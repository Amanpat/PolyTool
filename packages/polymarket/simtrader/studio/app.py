"""SimTrader Studio — local FastAPI web UI.

Factory function `create_app(artifacts_dir)` returns a FastAPI application that:
- Serves a single-page HTML UI at GET /
- Lists recent artifacts at GET /api/artifacts
- Lists recorded WS tapes at GET /api/tapes
- Runs SimTrader CLI subcommands (allowlisted) at POST /api/run

Usage
-----
    uvicorn packages.polymarket.simtrader.studio.app:app --port 8765
    # or via CLI:
    python -m polytool simtrader studio --open
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

# ---------------------------------------------------------------------------
# Constants (mirrors simtrader.py constants so Studio stays consistent)
# ---------------------------------------------------------------------------

DEFAULT_ARTIFACTS_DIR = Path("artifacts/simtrader")

_BROWSE_TYPE_DIRS: dict[str, str] = {
    "sweep": "sweeps",
    "batch": "batches",
    "run": "runs",
    "shadow": "shadow_runs",
}

_BROWSE_TS_RE = re.compile(r"(20\d{6}T\d{6}Z)")

# Commands that the /api/run endpoint is allowed to invoke.
_ALLOWED_COMMANDS = frozenset(
    ["quickrun", "shadow", "run", "sweep", "batch", "diff", "clean", "report", "browse"]
)

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_HERE = Path(__file__).parent


def _extract_timestamp(artifact_dir: Path) -> str:
    """Return ISO timestamp string from dirname or file mtime."""
    m = _BROWSE_TS_RE.search(artifact_dir.name)
    if m:
        raw = m.group(1)
        # e.g. 20260226T120000Z -> 2026-02-26T12:00:00Z
        try:
            dt = datetime.strptime(raw, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
            return dt.isoformat()
        except ValueError:
            pass
    try:
        mtime = artifact_dir.stat().st_mtime
        return datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat()
    except OSError:
        return datetime.fromtimestamp(0, tz=timezone.utc).isoformat()


def _scan_artifacts(artifacts_dir: Path) -> list[dict[str, Any]]:
    """Scan artifact subdirectories and return list of artifact metadata dicts.

    Considers a directory a valid artifact if it contains ``run_manifest.json``
    or ``meta.json``.  Returns at most 50 entries sorted newest-first.
    """
    if not artifacts_dir.exists():
        return []

    results: list[dict[str, Any]] = []

    for artifact_type, subdir_name in _BROWSE_TYPE_DIRS.items():
        subdir = artifacts_dir / subdir_name
        if not subdir.is_dir():
            continue
        try:
            entries = list(subdir.iterdir())
        except OSError:
            continue
        for entry in entries:
            if not entry.is_dir():
                continue
            has_manifest = (entry / "run_manifest.json").exists()
            has_meta = (entry / "meta.json").exists()
            if not (has_manifest or has_meta):
                continue
            try:
                ts = _extract_timestamp(entry)
                has_report = (entry / "report.html").exists()
                results.append(
                    {
                        "artifact_type": artifact_type,
                        "artifact_id": entry.name,
                        "artifact_path": str(entry),
                        "timestamp": ts,
                        "has_report": has_report,
                    }
                )
            except OSError:
                continue

    results.sort(key=lambda r: r["timestamp"], reverse=True)
    return results[:50]


def _scan_tapes(artifacts_dir: Path) -> list[dict[str, Any]]:
    """Scan artifacts_dir/tapes/ for tape directories containing events.jsonl."""
    tapes_dir = artifacts_dir / "tapes"
    if not tapes_dir.is_dir():
        return []
    results: list[dict[str, Any]] = []
    try:
        entries = list(tapes_dir.iterdir())
    except OSError:
        return []
    for entry in entries:
        if not entry.is_dir():
            continue
        if not (entry / "events.jsonl").exists():
            continue
        try:
            ts = _extract_timestamp(entry)
            results.append(
                {
                    "tape_id": entry.name,
                    "tape_path": str(entry),
                    "timestamp": ts,
                    "has_events": True,
                }
            )
        except OSError:
            continue
    results.sort(key=lambda r: r["timestamp"], reverse=True)
    return results


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------


def create_app(artifacts_dir: Path = DEFAULT_ARTIFACTS_DIR) -> FastAPI:
    """Create and return the SimTrader Studio FastAPI application.

    Parameters
    ----------
    artifacts_dir:
        Root directory for SimTrader artifacts.  Defaults to
        ``artifacts/simtrader`` relative to the current working directory.
        Pass a ``tmp_path`` in tests to isolate filesystem state.
    """
    _artifacts_dir = artifacts_dir

    app = FastAPI(title="SimTrader Studio", version="0.1.0")

    # Mount static files (index.html, etc.) — only if the static dir exists.
    _static_dir = _HERE / "static"
    if _static_dir.is_dir():
        app.mount("/static", StaticFiles(directory=str(_static_dir)), name="static")

    # ------------------------------------------------------------------
    # GET /
    # ------------------------------------------------------------------

    @app.get("/", response_class=HTMLResponse)
    async def root() -> HTMLResponse:
        index_path = _static_dir / "index.html"
        if not index_path.exists():
            return HTMLResponse(content="<h1>SimTrader Studio</h1><p>index.html not found.</p>", status_code=200)
        return HTMLResponse(content=index_path.read_text(encoding="utf-8"), status_code=200)

    # ------------------------------------------------------------------
    # GET /api/artifacts
    # ------------------------------------------------------------------

    @app.get("/api/artifacts")
    async def list_artifacts() -> dict[str, Any]:
        return {"artifacts": _scan_artifacts(_artifacts_dir)}

    # ------------------------------------------------------------------
    # GET /api/tapes
    # ------------------------------------------------------------------

    @app.get("/api/tapes")
    async def list_tapes() -> dict[str, Any]:
        return {"tapes": _scan_tapes(_artifacts_dir)}

    # ------------------------------------------------------------------
    # POST /api/run
    # ------------------------------------------------------------------

    @app.post("/api/run")
    async def run_command(body: dict[str, Any]) -> dict[str, Any]:
        command = body.get("command", "")
        args_list = body.get("args", [])

        if command not in _ALLOWED_COMMANDS:
            raise HTTPException(status_code=400, detail=f"command not allowed: {command!r}")

        if not isinstance(args_list, list):
            raise HTTPException(status_code=400, detail="args must be a list")

        # Build the subprocess command.
        cmd = [sys.executable, "-m", "polytool", "simtrader", command, *[str(a) for a in args_list]]

        try:
            proc = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                timeout=300,
            )
            return {"output": proc.stdout, "returncode": proc.returncode}
        except subprocess.TimeoutExpired:
            return {"output": "Error: command timed out after 300 seconds.", "returncode": -1}
        except Exception as exc:  # noqa: BLE001
            return {"output": f"Error launching command: {exc}", "returncode": -1}

    return app


# ---------------------------------------------------------------------------
# Module-level app instance (for `uvicorn packages...studio.app:app`)
# ---------------------------------------------------------------------------

app = create_app()
