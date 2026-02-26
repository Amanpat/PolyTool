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
import uuid
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
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

    from .ondemand import OnDemandSessionManager  # local import to avoid circular
    _sessions = OnDemandSessionManager()

    def _get_session(mgr: OnDemandSessionManager, sid: str):  # type: ignore[return]
        try:
            return mgr.get(sid)
        except KeyError:
            raise HTTPException(status_code=404, detail=f"session not found: {sid!r}")

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

    # ------------------------------------------------------------------
    # POST /api/ondemand/new
    # ------------------------------------------------------------------

    @app.post("/api/ondemand/new")
    async def ondemand_new(body: dict[str, Any]) -> dict[str, Any]:
        tape_path_str = body.get("tape_path", "")
        if not tape_path_str:
            raise HTTPException(status_code=400, detail="tape_path is required")

        tape_path = Path(tape_path_str)
        if not tape_path.is_dir() or not (tape_path / "events.jsonl").exists():
            raise HTTPException(
                status_code=400,
                detail=f"tape_path must be a directory containing events.jsonl: {tape_path_str!r}",
            )

        # Parse starting_cash
        starting_cash_str = body.get("starting_cash", "1000")
        try:
            starting_cash = Decimal(str(starting_cash_str))
        except InvalidOperation:
            raise HTTPException(status_code=400, detail=f"invalid starting_cash: {starting_cash_str!r}")

        # Parse fee_rate_bps (optional)
        fee_rate_bps: Any = None
        fee_str = body.get("fee_rate_bps")
        if fee_str is not None and str(fee_str).strip():
            try:
                fee_rate_bps = Decimal(str(fee_str))
            except InvalidOperation:
                raise HTTPException(status_code=400, detail=f"invalid fee_rate_bps: {fee_str!r}")

        # mark_method
        mark_method = body.get("mark_method", "bid")
        if mark_method not in ("bid", "midpoint"):
            raise HTTPException(status_code=400, detail=f"mark_method must be 'bid' or 'midpoint'; got {mark_method!r}")

        session = _sessions.create(tape_path_str, starting_cash, fee_rate_bps, mark_method)
        return {"session_id": session.session_id, "state": session.get_state()}

    # ------------------------------------------------------------------
    # GET /api/ondemand/{session_id}/state
    # ------------------------------------------------------------------

    @app.get("/api/ondemand/{session_id}/state")
    async def ondemand_state(session_id: str) -> dict[str, Any]:
        session = _get_session(_sessions, session_id)
        return {"state": session.get_state()}

    # ------------------------------------------------------------------
    # POST /api/ondemand/{session_id}/step
    # ------------------------------------------------------------------

    @app.post("/api/ondemand/{session_id}/step")
    async def ondemand_step(session_id: str, body: dict[str, Any]) -> dict[str, Any]:
        session = _get_session(_sessions, session_id)
        n_steps = int(body.get("n_steps", 1))
        n_steps = max(1, min(n_steps, 1000))
        return {"state": session.step(n_steps)}

    # ------------------------------------------------------------------
    # POST /api/ondemand/{session_id}/play
    # ------------------------------------------------------------------

    @app.post("/api/ondemand/{session_id}/play")
    async def ondemand_play(session_id: str, body: dict[str, Any]) -> dict[str, Any]:
        session = _get_session(_sessions, session_id)
        n_steps = int(body.get("n_steps", 50))
        n_steps = max(1, min(n_steps, 500))
        return {"state": session.step(n_steps)}

    # ------------------------------------------------------------------
    # POST /api/ondemand/{session_id}/order
    # ------------------------------------------------------------------

    @app.post("/api/ondemand/{session_id}/order")
    async def ondemand_order(session_id: str, body: dict[str, Any]) -> dict[str, Any]:
        session = _get_session(_sessions, session_id)

        asset_id = body.get("asset_id", "")
        if not asset_id:
            raise HTTPException(status_code=400, detail="asset_id is required")

        side = (body.get("side") or "").upper()
        if side not in ("BUY", "SELL"):
            raise HTTPException(status_code=400, detail=f"side must be BUY or SELL; got {side!r}")

        limit_price_str = body.get("limit_price", "")
        size_str = body.get("size", "")
        try:
            limit_price = Decimal(str(limit_price_str))
        except InvalidOperation:
            raise HTTPException(status_code=400, detail=f"invalid limit_price: {limit_price_str!r}")
        try:
            size = Decimal(str(size_str))
        except InvalidOperation:
            raise HTTPException(status_code=400, detail=f"invalid size: {size_str!r}")

        if not (Decimal("0") < limit_price <= Decimal("1")):
            raise HTTPException(
                status_code=400,
                detail=f"limit_price must be in (0, 1] for binary markets; got {limit_price}",
            )
        if size <= Decimal("0"):
            raise HTTPException(status_code=400, detail=f"size must be > 0; got {size}")

        order_id, state = session.submit_order(asset_id, side, limit_price, size)
        return {"order_id": order_id, "state": state}

    # ------------------------------------------------------------------
    # POST /api/ondemand/{session_id}/cancel
    # ------------------------------------------------------------------

    @app.post("/api/ondemand/{session_id}/cancel")
    async def ondemand_cancel(session_id: str, body: dict[str, Any]) -> dict[str, Any]:
        session = _get_session(_sessions, session_id)
        order_id = body.get("order_id", "")
        if not order_id:
            raise HTTPException(status_code=400, detail="order_id is required")
        try:
            state = session.cancel_order(order_id)
        except KeyError:
            raise HTTPException(status_code=404, detail=f"order not found: {order_id!r}")
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        return {"state": state}

    # ------------------------------------------------------------------
    # POST /api/ondemand/{session_id}/save
    # ------------------------------------------------------------------

    @app.post("/api/ondemand/{session_id}/save")
    async def ondemand_save(session_id: str, body: dict[str, Any]) -> dict[str, Any]:
        session = _get_session(_sessions, session_id)
        session_dir_str = body.get("session_dir")
        if session_dir_str:
            session_dir = Path(session_dir_str)
        else:
            session_dir = _artifacts_dir / "ondemand_sessions" / session.session_id
        session.save_artifacts(session_dir)
        return {"artifact_dir": str(session_dir.resolve())}

    # ------------------------------------------------------------------
    # DELETE /api/ondemand/{session_id}
    # ------------------------------------------------------------------

    @app.delete("/api/ondemand/{session_id}")
    async def ondemand_delete(session_id: str) -> dict[str, Any]:
        _sessions.delete(session_id)
        return {"deleted": session_id}

    return app


# ---------------------------------------------------------------------------
# Module-level app instance (for `uvicorn packages...studio.app:app`)
# ---------------------------------------------------------------------------

app = create_app()
