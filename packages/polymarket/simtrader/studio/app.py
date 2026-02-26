"""SimTrader Studio local FastAPI app.

Factory function ``create_app(artifacts_dir)`` returns a FastAPI app that:
- Serves the Studio UI at ``GET /``
- Exposes artifact/tape browse APIs
- Uses ``StudioSessionManager`` as the single execution path for Studio commands
- Streams live session updates/logs over SSE
"""

from __future__ import annotations

import asyncio
import json
import re
import shlex
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from ..studio_sessions import TERMINAL_STATUSES, StudioSessionManager

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

_SESSION_COMMANDS = frozenset(
    ["quickrun", "shadow", "run", "sweep", "batch", "diff", "clean", "report", "browse"]
)

_SESSION_KINDS = frozenset({"shadow", "run", "sweep", "batch"})

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_HERE = Path(__file__).parent


def _extract_timestamp(artifact_dir: Path) -> str:
    """Return ISO timestamp string from dirname or file mtime."""
    match = _BROWSE_TS_RE.search(artifact_dir.name)
    if match:
        raw = match.group(1)
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


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _scan_artifacts(artifacts_dir: Path) -> list[dict[str, Any]]:
    """Scan artifact subdirectories and return artifact metadata dicts."""
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

    results.sort(key=lambda row: row["timestamp"], reverse=True)
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
    results.sort(key=lambda row: row["timestamp"], reverse=True)
    return results


def _coerce_args(raw: Any) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, list):
        return [str(x) for x in raw]
    if isinstance(raw, str):
        text = raw.strip()
        if not text:
            return []
        try:
            return shlex.split(text, posix=False)
        except ValueError:
            return text.split()
    raise ValueError("args must be a list of strings or a string")


def _read_json_file(path: Path) -> dict[str, Any] | None:
    if not path.exists() or not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return None
    return payload if isinstance(payload, dict) else None


def _read_jsonl_rows(path: Path, limit: int) -> list[dict[str, Any]]:
    if not path.exists() or not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8") as fh:
            for line in fh:
                text = line.strip()
                if not text:
                    continue
                try:
                    payload = json.loads(text)
                except json.JSONDecodeError:
                    continue
                if isinstance(payload, dict):
                    rows.append(payload)
    except OSError:
        return []
    if limit > 0 and len(rows) > limit:
        return rows[-limit:]
    return rows


def _extract_rejection_rows(
    run_manifest: dict[str, Any],
    summary: dict[str, Any],
) -> list[dict[str, Any]]:
    def _coerce_rows(raw: Any) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        if isinstance(raw, dict):
            for key, value in raw.items():
                try:
                    count = int(value)
                except (TypeError, ValueError):
                    continue
                if count > 0:
                    rows.append({"reason": str(key), "count": count})
        elif isinstance(raw, list):
            for row in raw:
                if not isinstance(row, dict):
                    continue
                key = row.get("key") or row.get("reason")
                count = row.get("count")
                try:
                    count_int = int(count)
                except (TypeError, ValueError):
                    continue
                if key and count_int > 0:
                    rows.append({"reason": str(key), "count": count_int})
        rows.sort(key=lambda row: (-int(row["count"]), str(row["reason"])))
        return rows

    containers = [
        run_manifest.get("strategy_debug"),
        run_manifest.get("modeled_arb_summary"),
        summary,
    ]
    for container in containers:
        if not isinstance(container, dict):
            continue
        for key in ("rejection_counts", "dominant_rejection_counts"):
            rows = _coerce_rows(container.get(key))
            if rows:
                return rows
    return []


def _decorate_session_snapshot(snapshot: dict[str, Any], artifacts_root: Path) -> dict[str, Any]:
    row = dict(snapshot)
    row["artifact_relpath"] = None
    row["has_report"] = False
    row["report_url"] = None

    artifact_raw = row.get("artifact_dir")
    if not isinstance(artifact_raw, str) or not artifact_raw:
        return row

    artifact_dir = Path(artifact_raw)
    if not artifact_dir.is_absolute():
        artifact_dir = (Path.cwd() / artifact_dir).resolve()
    else:
        artifact_dir = artifact_dir.resolve()
    row["artifact_dir"] = str(artifact_dir)

    if not _is_relative_to(artifact_dir, artifacts_root):
        return row

    relpath = artifact_dir.relative_to(artifacts_root.resolve()).as_posix()
    report_path = artifact_dir / "report.html"

    row["artifact_relpath"] = relpath
    row["has_report"] = report_path.exists()
    if row["has_report"]:
        row["report_url"] = f"/artifacts/{relpath}/report.html"
    return row


def _start_session(
    session_manager: StudioSessionManager,
    command: str,
    args: list[str],
) -> dict[str, Any]:
    if command in _SESSION_KINDS:
        return session_manager.start_session(kind=command, args=args)
    return session_manager.start_session(kind="ondemand", subcommand=command, args=args)


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------


def create_app(
    artifacts_dir: Path = DEFAULT_ARTIFACTS_DIR,
    session_manager: StudioSessionManager | None = None,
) -> FastAPI:
    """Create and return the SimTrader Studio FastAPI application."""
    _artifacts_dir = Path(artifacts_dir).resolve()
    if session_manager is not None:
        _session_manager = session_manager
    elif Path(artifacts_dir) == DEFAULT_ARTIFACTS_DIR:
        _session_manager = StudioSessionManager()
    else:
        _session_manager = StudioSessionManager(artifacts_root=_artifacts_dir)

    from .ondemand import OnDemandSessionManager  # local import to avoid circular

    _ondemand_sessions = OnDemandSessionManager()

    def _get_ondemand_session(mgr: OnDemandSessionManager, sid: str):  # type: ignore[return]
        try:
            return mgr.get(sid)
        except KeyError:
            raise HTTPException(status_code=404, detail=f"session not found: {sid!r}")

    def _get_tracked_session(session_id: str) -> dict[str, Any]:
        session = _session_manager.get_session(session_id)
        if session is None:
            raise HTTPException(status_code=404, detail=f"unknown session_id: {session_id}")
        return _decorate_session_snapshot(session, _artifacts_dir)

    def _parse_start_request(body: dict[str, Any]) -> tuple[str, list[str]]:
        command = str(body.get("command") or body.get("kind") or "").strip().lower()
        if command not in _SESSION_COMMANDS:
            known = ", ".join(sorted(_SESSION_COMMANDS))
            raise HTTPException(
                status_code=400,
                detail=f"command not allowed: {command!r}. Expected one of: {known}",
            )
        try:
            args = _coerce_args(body.get("args"))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        return command, args

    app = FastAPI(title="SimTrader Studio", version="0.2.0")

    # Mount static files (index.html, etc.) if the static dir exists.
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
            return HTMLResponse(
                content="<h1>SimTrader Studio</h1><p>index.html not found.</p>",
                status_code=200,
            )
        return HTMLResponse(content=index_path.read_text(encoding="utf-8"), status_code=200)

    # ------------------------------------------------------------------
    # Artifact browse APIs
    # ------------------------------------------------------------------

    @app.get("/api/artifacts")
    async def list_artifacts() -> dict[str, Any]:
        return {"artifacts": _scan_artifacts(_artifacts_dir)}

    @app.get("/api/tapes")
    async def list_tapes() -> dict[str, Any]:
        return {"tapes": _scan_tapes(_artifacts_dir)}

    @app.get("/artifacts/{rest:path}")
    async def serve_artifact(rest: str):
        rel = Path(rest)
        if ".." in rel.parts:
            raise HTTPException(status_code=400, detail="invalid artifact path")

        target = (_artifacts_dir / rel).resolve()
        if not _is_relative_to(target, _artifacts_dir):
            raise HTTPException(status_code=400, detail="artifact path escapes artifacts root")
        if not target.exists() or not target.is_file():
            raise HTTPException(status_code=404, detail="artifact not found")
        return FileResponse(target)

    # ------------------------------------------------------------------
    # Session manager APIs
    # ------------------------------------------------------------------

    @app.get("/api/sessions")
    async def list_sessions() -> dict[str, Any]:
        rows = [
            _decorate_session_snapshot(row, _artifacts_dir)
            for row in _session_manager.list_sessions()
        ]
        return {"sessions": rows}

    @app.get("/api/sessions/{session_id}")
    async def session_detail(session_id: str) -> dict[str, Any]:
        return {"session": _get_tracked_session(session_id)}

    @app.post("/api/sessions")
    async def start_session(body: dict[str, Any]) -> dict[str, Any]:
        command, args = _parse_start_request(body)
        try:
            started = _start_session(_session_manager, command=command, args=args)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        return {"session": _decorate_session_snapshot(started, _artifacts_dir)}

    @app.post("/api/run")
    async def start_session_legacy(body: dict[str, Any]) -> dict[str, Any]:
        """Deprecated endpoint kept for backwards compatibility."""
        command, args = _parse_start_request(body)
        try:
            started = _start_session(_session_manager, command=command, args=args)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        return {
            "deprecated": True,
            "session": _decorate_session_snapshot(started, _artifacts_dir),
        }

    @app.post("/api/sessions/{session_id}/kill")
    async def kill_session(session_id: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        force = bool((body or {}).get("force", False))
        try:
            killed = _session_manager.kill_session(session_id, force=force)
        except KeyError:
            raise HTTPException(status_code=404, detail=f"unknown session_id: {session_id}")
        return {"session": _decorate_session_snapshot(killed, _artifacts_dir)}

    @app.get("/api/sessions/{session_id}/log")
    async def read_session_log(
        session_id: str,
        offset: int = Query(default=0, ge=0),
    ) -> dict[str, Any]:
        try:
            next_offset, lines = _session_manager.read_log_chunk(session_id, offset)
        except KeyError:
            raise HTTPException(status_code=404, detail=f"unknown session_id: {session_id}")
        return {
            "session": _get_tracked_session(session_id),
            "offset": next_offset,
            "lines": lines,
        }

    @app.get("/api/sessions/{session_id}/viewer")
    async def session_viewer(
        session_id: str,
        equity_limit: int = Query(default=500, ge=1, le=5000),
        row_limit: int = Query(default=200, ge=1, le=1000),
    ) -> dict[str, Any]:
        session = _get_tracked_session(session_id)
        artifact_raw = session.get("artifact_dir")
        if not isinstance(artifact_raw, str) or not artifact_raw:
            raise HTTPException(
                status_code=400,
                detail=f"session has no artifact directory: {session_id}",
            )

        artifact_dir = Path(artifact_raw).resolve()
        if not artifact_dir.exists() or not artifact_dir.is_dir():
            raise HTTPException(
                status_code=404,
                detail=f"artifact directory not found: {artifact_dir}",
            )
        if not _is_relative_to(artifact_dir, _artifacts_dir):
            raise HTTPException(status_code=400, detail="artifact path escapes artifacts root")

        run_manifest = _read_json_file(artifact_dir / "run_manifest.json") or {}
        summary = _read_json_file(artifact_dir / "summary.json") or {}
        equity_curve = _read_jsonl_rows(artifact_dir / "equity_curve.jsonl", limit=equity_limit)
        orders = _read_jsonl_rows(artifact_dir / "orders.jsonl", limit=row_limit)
        fills = _read_jsonl_rows(artifact_dir / "fills.jsonl", limit=row_limit)
        rejection_rows = _extract_rejection_rows(run_manifest=run_manifest, summary=summary)

        return {
            "session": session,
            "summary": summary,
            "run_manifest": run_manifest,
            "equity_curve": equity_curve,
            "orders": orders,
            "fills": fills,
            "rejection_reasons": rejection_rows,
        }

    @app.get("/api/sessions/{session_id}/events")
    async def stream_session_events(
        session_id: str,
        offset: int = Query(default=0, ge=0),
        interval_ms: int = Query(default=350, ge=100, le=5000),
    ):
        if _session_manager.get_session(session_id) is None:
            raise HTTPException(status_code=404, detail=f"unknown session_id: {session_id}")

        async def _event_stream():
            cursor = offset
            last_session_payload = ""
            while True:
                session = _session_manager.get_session(session_id)
                if session is None:
                    payload = json.dumps({"detail": "session_not_found"}, ensure_ascii=False)
                    yield f"event: error\ndata: {payload}\n\n"
                    break

                decorated = _decorate_session_snapshot(session, _artifacts_dir)
                session_payload = json.dumps(
                    {"session": decorated},
                    ensure_ascii=False,
                    separators=(",", ":"),
                )
                if session_payload != last_session_payload:
                    yield f"event: session\ndata: {session_payload}\n\n"
                    last_session_payload = session_payload

                try:
                    cursor, lines = _session_manager.read_log_chunk(session_id, cursor)
                except KeyError:
                    lines = []

                for line in lines:
                    payload = json.dumps({"line": line, "offset": cursor}, ensure_ascii=False)
                    yield f"event: log\ndata: {payload}\n\n"

                if decorated.get("status") in TERMINAL_STATUSES and not lines:
                    payload = json.dumps(
                        {"status": decorated.get("status")},
                        ensure_ascii=False,
                    )
                    yield f"event: end\ndata: {payload}\n\n"
                    break

                yield ": keepalive\n\n"
                await asyncio.sleep(interval_ms / 1000.0)

        return StreamingResponse(
            _event_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    # ------------------------------------------------------------------
    # On-demand replay APIs
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

        starting_cash_str = body.get("starting_cash", "1000")
        try:
            starting_cash = Decimal(str(starting_cash_str))
        except InvalidOperation:
            raise HTTPException(status_code=400, detail=f"invalid starting_cash: {starting_cash_str!r}")

        fee_rate_bps: Any = None
        fee_str = body.get("fee_rate_bps")
        if fee_str is not None and str(fee_str).strip():
            try:
                fee_rate_bps = Decimal(str(fee_str))
            except InvalidOperation:
                raise HTTPException(status_code=400, detail=f"invalid fee_rate_bps: {fee_str!r}")

        mark_method = body.get("mark_method", "bid")
        if mark_method not in ("bid", "midpoint"):
            raise HTTPException(status_code=400, detail=f"mark_method must be 'bid' or 'midpoint'; got {mark_method!r}")

        session = _ondemand_sessions.create(tape_path_str, starting_cash, fee_rate_bps, mark_method)
        return {"session_id": session.session_id, "state": session.get_state()}

    @app.get("/api/ondemand/{session_id}/state")
    async def ondemand_state(session_id: str) -> dict[str, Any]:
        session = _get_ondemand_session(_ondemand_sessions, session_id)
        return {"state": session.get_state()}

    @app.post("/api/ondemand/{session_id}/step")
    async def ondemand_step(session_id: str, body: dict[str, Any]) -> dict[str, Any]:
        session = _get_ondemand_session(_ondemand_sessions, session_id)
        n_steps = int(body.get("n_steps", 1))
        n_steps = max(1, min(n_steps, 1000))
        return {"state": session.step(n_steps)}

    @app.post("/api/ondemand/{session_id}/play")
    async def ondemand_play(session_id: str, body: dict[str, Any]) -> dict[str, Any]:
        session = _get_ondemand_session(_ondemand_sessions, session_id)
        n_steps = int(body.get("n_steps", 50))
        n_steps = max(1, min(n_steps, 500))
        return {"state": session.step(n_steps)}

    @app.post("/api/ondemand/{session_id}/order")
    async def ondemand_order(session_id: str, body: dict[str, Any]) -> dict[str, Any]:
        session = _get_ondemand_session(_ondemand_sessions, session_id)

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

    @app.post("/api/ondemand/{session_id}/cancel")
    async def ondemand_cancel(session_id: str, body: dict[str, Any]) -> dict[str, Any]:
        session = _get_ondemand_session(_ondemand_sessions, session_id)
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

    @app.post("/api/ondemand/{session_id}/save")
    async def ondemand_save(session_id: str, body: dict[str, Any]) -> dict[str, Any]:
        session = _get_ondemand_session(_ondemand_sessions, session_id)
        session_dir_str = body.get("session_dir")
        if session_dir_str:
            session_dir = Path(session_dir_str)
        else:
            session_dir = _artifacts_dir / "ondemand_sessions" / session.session_id
        session.save_artifacts(session_dir)
        return {"artifact_dir": str(session_dir.resolve())}

    @app.delete("/api/ondemand/{session_id}")
    async def ondemand_delete(session_id: str) -> dict[str, Any]:
        _ondemand_sessions.delete(session_id)
        return {"deleted": session_id}

    return app


# ---------------------------------------------------------------------------
# Module-level app instance (for `uvicorn packages...studio.app:app`)
# ---------------------------------------------------------------------------

app = create_app()
