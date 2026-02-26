"""Studio UI server — lightweight FastAPI app.

Serves the static Studio front-end and exposes a handful of read-only
JSON endpoints that scan ``artifacts/simtrader/`` on disk.

Usage:
    uvicorn services.studio.serve:app --reload --port 8501
    # or
    python services/studio/serve.py
"""

from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Resolve project root (two levels up from services/studio/)
_THIS_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _THIS_DIR.parent.parent
ARTIFACTS_ROOT = _PROJECT_ROOT / "artifacts" / "simtrader"

app = FastAPI(title="PolyTool Studio", version="0.1.0")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_TS_RE = re.compile(r"(20\d{6}T\d{6}Z)")


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return None


def _parse_ts(name: str) -> str | None:
    m = _TS_RE.search(name)
    if not m:
        return None
    raw = m.group(1)
    try:
        dt = datetime.strptime(raw, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
        return dt.isoformat()
    except ValueError:
        return raw


def _scan_run_dirs(category: str, subdir: str) -> list[dict[str, Any]]:
    """Scan a category directory and return a list of session dicts."""
    root = ARTIFACTS_ROOT / subdir
    if not root.is_dir():
        return []

    sessions: list[dict[str, Any]] = []
    for entry in sorted(root.iterdir(), reverse=True):
        if not entry.is_dir():
            continue

        manifest = _read_json(entry / "run_manifest.json")
        summary = _read_json(entry / "summary.json")
        meta = _read_json(entry / "meta.json")

        run_id = entry.name
        created_at = None
        if manifest and manifest.get("created_at"):
            created_at = manifest["created_at"]
        if not created_at:
            created_at = _parse_ts(run_id)

        market_slug = ""
        if manifest:
            market_slug = (
                manifest.get("market_slug")
                or (manifest.get("market_context") or {}).get("market_slug")
                or ""
            )

        status = "ok"
        if meta and meta.get("run_quality"):
            status = meta["run_quality"]
        elif manifest and manifest.get("run_quality"):
            status = manifest["run_quality"]

        net_profit = "0"
        if summary and summary.get("net_profit") is not None:
            net_profit = str(summary["net_profit"])
        elif manifest and manifest.get("net_profit") is not None:
            net_profit = str(manifest["net_profit"])

        has_report = (entry / "report.html").exists()
        strategy = ""
        if manifest:
            strategy = manifest.get("command", "")
            tc = manifest.get("tape_coverage") or {}
            strategy = tc.get("strategy", strategy)

        sessions.append(
            {
                "run_id": run_id,
                "category": category,
                "created_at": created_at,
                "market_slug": market_slug,
                "status": status,
                "net_profit": net_profit,
                "strategy": strategy,
                "has_report": has_report,
                "artifact_dir": f"artifacts/simtrader/{subdir}/{run_id}",
            }
        )

    return sessions


# ---------------------------------------------------------------------------
# API endpoints
# ---------------------------------------------------------------------------


@app.get("/api/studio/sessions")
async def list_sessions():
    """List all runs + shadow_runs as 'sessions'."""
    sessions: list[dict[str, Any]] = []
    sessions.extend(_scan_run_dirs("run", "runs"))
    sessions.extend(_scan_run_dirs("shadow", "shadow_runs"))
    sessions.extend(_scan_run_dirs("sweep", "sweeps"))
    # Sort newest-first by created_at
    sessions.sort(key=lambda s: s.get("created_at") or "", reverse=True)
    return {"sessions": sessions, "count": len(sessions)}


@app.get("/api/studio/tapes")
async def list_tapes():
    """List recorded tapes."""
    root = ARTIFACTS_ROOT / "tapes"
    if not root.is_dir():
        return {"tapes": [], "count": 0}

    tapes: list[dict[str, Any]] = []
    for entry in sorted(root.iterdir(), reverse=True):
        if not entry.is_dir():
            continue

        meta = _read_json(entry / "meta.json")
        events_path = entry / "events.jsonl"
        event_count: int | None = None
        if meta:
            event_count = (
                meta.get("event_count")
                or meta.get("parsed_events")
                or meta.get("total_events")
            )
        if event_count is None and events_path.exists():
            try:
                event_count = sum(
                    1 for line in events_path.read_text("utf-8").splitlines() if line.strip()
                )
            except Exception:
                pass

        market_slug = ""
        if meta:
            for ctx_key in ("quickrun_context", "shadow_context"):
                ctx = meta.get(ctx_key)
                if isinstance(ctx, dict):
                    market_slug = ctx.get("selected_slug") or ctx.get("market_slug") or ""
                    if market_slug:
                        break

        tapes.append(
            {
                "tape_id": entry.name,
                "created_at": _parse_ts(entry.name),
                "event_count": event_count,
                "market_slug": market_slug,
                "has_events": events_path.exists(),
                "artifact_dir": f"artifacts/simtrader/tapes/{entry.name}",
            }
        )

    return {"tapes": tapes, "count": len(tapes)}


@app.get("/api/studio/reports")
async def list_reports():
    """List all artifacts that contain a report.html."""
    reports: list[dict[str, Any]] = []

    for subdir in ("runs", "shadow_runs", "sweeps"):
        root = ARTIFACTS_ROOT / subdir
        if not root.is_dir():
            continue
        for entry in sorted(root.iterdir(), reverse=True):
            report_path = entry / "report.html"
            if not report_path.exists():
                continue

            manifest = _read_json(entry / "run_manifest.json")
            market_slug = ""
            if manifest:
                market_slug = (
                    manifest.get("market_slug")
                    or (manifest.get("market_context") or {}).get("market_slug")
                    or ""
                )

            reports.append(
                {
                    "run_id": entry.name,
                    "category": subdir.rstrip("s"),
                    "market_slug": market_slug,
                    "created_at": _parse_ts(entry.name),
                    "report_url": f"/artifacts/{subdir}/{entry.name}/report.html",
                }
            )

    return {"reports": reports, "count": len(reports)}


@app.get("/api/studio/dashboard")
async def dashboard():
    """Return summary counts for the dashboard."""
    counts: dict[str, int] = {}
    for label, subdir in [
        ("runs", "runs"),
        ("shadow_runs", "shadow_runs"),
        ("sweeps", "sweeps"),
        ("tapes", "tapes"),
    ]:
        root = ARTIFACTS_ROOT / subdir
        if root.is_dir():
            counts[label] = sum(1 for d in root.iterdir() if d.is_dir())
        else:
            counts[label] = 0

    return counts


# ---------------------------------------------------------------------------
# Serve artifact files (report.html, etc.)
# ---------------------------------------------------------------------------


@app.get("/artifacts/{rest:path}")
async def serve_artifact(rest: str):
    """Serve files from the artifacts directory (read-only)."""
    safe = Path(rest)
    if ".." in safe.parts:
        raise HTTPException(status_code=400, detail="Invalid path")
    full = ARTIFACTS_ROOT / safe
    if not full.exists() or not full.is_file():
        raise HTTPException(status_code=404, detail="Not found")
    return FileResponse(full)


# ---------------------------------------------------------------------------
# Serve static front-end
# ---------------------------------------------------------------------------

# Serve index.html as the default page
@app.get("/", response_class=HTMLResponse)
async def index():
    index_path = _THIS_DIR / "index.html"
    if not index_path.exists():
        raise HTTPException(status_code=404, detail="index.html not found")
    return HTMLResponse(index_path.read_text(encoding="utf-8"))


# Mount static assets last so the explicit routes above take priority
if (_THIS_DIR / "static").is_dir():
    app.mount("/static", StaticFiles(directory=str(_THIS_DIR / "static")), name="static")


# ---------------------------------------------------------------------------
# Direct run support: python services/studio/serve.py
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "services.studio.serve:app",
        host="127.0.0.1",
        port=8501,
        reload=True,
    )
