"""SimTrader Studio local FastAPI app.

Factory function ``create_app(artifacts_dir)`` returns a FastAPI app that:
- Serves the Studio UI at ``GET /``
- Exposes artifact/tape browse APIs
- Uses ``StudioSessionManager`` as the single execution path for Studio commands
- Streams live session updates/logs over SSE
"""

from __future__ import annotations

import asyncio
import math
import json
import re
import shlex
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Iterator

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from ..display_name import derive_artifact_display_name, derive_session_display_name
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
            manifest_payload: dict[str, Any] = {}
            if artifact_type in {"run", "shadow"}:
                run_manifest = _read_json_file(entry / "run_manifest.json")
                has_meta = (entry / "meta.json").exists()
                if run_manifest is None and not has_meta:
                    continue
                manifest_payload = run_manifest or {}
            elif artifact_type == "sweep":
                sweep_manifest = _read_json_file(entry / "sweep_manifest.json")
                sweep_summary = _read_json_file(entry / "sweep_summary.json")
                if sweep_manifest is None and sweep_summary is None:
                    continue
                manifest_payload = sweep_manifest or sweep_summary or {}
            elif artifact_type == "batch":
                batch_manifest = _read_json_file(entry / "batch_manifest.json")
                batch_summary = _read_json_file(entry / "batch_summary.json")
                if batch_manifest is None and batch_summary is None:
                    continue
                manifest_payload = batch_manifest or batch_summary or {}
            else:
                continue
            try:
                ts = _extract_timestamp(entry)
                has_report = (entry / "report.html").exists()
                results.append(
                    {
                        "artifact_type": artifact_type,
                        "artifact_id": entry.name,
                        "display_name": derive_artifact_display_name(
                            artifact_type=artifact_type,
                            artifact_id=entry.name,
                            manifest=manifest_payload,
                        ),
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


def _iter_jsonl_dict_rows(path: Path) -> Iterator[dict[str, Any]]:
    if not path.exists() or not path.is_file():
        return
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
                    yield payload
    except OSError:
        return


def _as_float(raw: Any) -> float | None:
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        value = float(raw)
    elif isinstance(raw, Decimal):
        value = float(raw)
    else:
        text = str(raw).strip()
        if not text:
            return None
        try:
            value = float(text)
        except ValueError:
            return None
    if not math.isfinite(value):
        return None
    return value


def _parse_time_bound(raw: str | None) -> float | None:
    if raw is None:
        return None
    text = raw.strip()
    if not text:
        return None
    as_float = _as_float(text)
    if as_float is not None:
        return as_float
    normalized = text[:-1] + "+00:00" if text.endswith("Z") else text
    try:
        dt = datetime.fromisoformat(normalized)
    except ValueError:
        raise ValueError(f"invalid time bound: {raw!r}. expected unix seconds or ISO-8601")
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt.timestamp()


def _normalize_bbo_point(raw: dict[str, Any]) -> dict[str, Any] | None:
    best_bid = _as_float(raw.get("best_bid"))
    best_ask = _as_float(raw.get("best_ask"))
    if best_bid is None and best_ask is None:
        return None
    seq_raw = raw.get("seq")
    seq: int | None = None
    try:
        if seq_raw is not None and str(seq_raw).strip() != "":
            seq = int(seq_raw)
    except (TypeError, ValueError):
        seq = None
    ts_recv = _as_float(raw.get("ts_recv"))
    mid = (best_bid + best_ask) / 2 if best_bid is not None and best_ask is not None else None
    return {
        "seq": seq,
        "ts_recv": ts_recv,
        "asset_id": str(raw.get("asset_id") or ""),
        "event_type": str(raw.get("event_type") or ""),
        "best_bid": best_bid,
        "best_ask": best_ask,
        "mid": mid,
    }


def _downsample_rows(rows: list[dict[str, Any]], max_points: int) -> list[dict[str, Any]]:
    if max_points <= 0 or len(rows) <= max_points:
        return rows
    if max_points == 1:
        return [rows[-1]]
    first = rows[0]
    last = rows[-1]
    step = (len(rows) - 1) / float(max_points - 1)
    sampled: list[dict[str, Any]] = []
    prev_idx = -1
    for i in range(max_points):
        idx = int(round(i * step))
        if idx <= prev_idx:
            idx = min(len(rows) - 1, prev_idx + 1)
        sampled.append(rows[idx])
        prev_idx = idx
    sampled[0] = first
    sampled[-1] = last
    return sampled


def _resolve_simulation_artifact_dir(
    artifacts_root: Path,
    artifact_type: str,
    artifact_id: str,
) -> Path:
    artifact_type_norm = artifact_type.strip().lower()
    if artifact_type_norm not in {"run", "shadow"}:
        raise HTTPException(
            status_code=400,
            detail="artifact_type must be 'run' or 'shadow'",
        )
    artifact_id_norm = artifact_id.strip()
    if not artifact_id_norm:
        raise HTTPException(status_code=400, detail="artifact_id is required")

    artifact_rel = Path(artifact_id_norm)
    if ".." in artifact_rel.parts or len(artifact_rel.parts) != 1:
        raise HTTPException(status_code=400, detail="invalid artifact_id path")

    target = (
        artifacts_root / _BROWSE_TYPE_DIRS[artifact_type_norm] / artifact_id_norm
    ).resolve()
    if not _is_relative_to(target, artifacts_root):
        raise HTTPException(status_code=400, detail="artifact path escapes artifacts root")
    if not target.exists() or not target.is_dir():
        raise HTTPException(status_code=404, detail="artifact not found")
    return target


def _extract_asset_context(run_manifest: dict[str, Any]) -> dict[str, Any]:
    yes_asset_id = str(run_manifest.get("asset_id") or "").strip() or None
    no_asset_id: str | None = None
    extras = run_manifest.get("extra_book_asset_ids")
    if isinstance(extras, list):
        for raw in extras:
            text = str(raw or "").strip()
            if text:
                no_asset_id = text
                break

    yes_label = "YES"
    no_label = "NO"
    shadow_context = run_manifest.get("shadow_context")
    if isinstance(shadow_context, dict):
        yes_shadow = str(shadow_context.get("yes_token_id") or "").strip()
        no_shadow = str(shadow_context.get("no_token_id") or "").strip()
        if yes_shadow:
            yes_asset_id = yes_shadow
        if no_shadow:
            no_asset_id = no_shadow
        yes_no_mapping = shadow_context.get("yes_no_mapping")
        if isinstance(yes_no_mapping, dict):
            yes_label = str(yes_no_mapping.get("yes_label") or yes_label)
            no_label = str(yes_no_mapping.get("no_label") or no_label)

    if yes_asset_id and no_asset_id and yes_asset_id == no_asset_id:
        no_asset_id = None

    return {
        "yes_asset_id": yes_asset_id,
        "no_asset_id": no_asset_id,
        "yes_label": yes_label,
        "no_label": no_label,
    }


def _infer_row_leg(row: dict[str, Any], asset_context: dict[str, Any]) -> str | None:
    yes_asset_id = asset_context.get("yes_asset_id")
    no_asset_id = asset_context.get("no_asset_id")
    asset_id = str(row.get("asset_id") or "").strip()
    if yes_asset_id and asset_id == yes_asset_id:
        return "yes"
    if no_asset_id and asset_id == no_asset_id:
        return "no"

    leg_raw = row.get("leg")
    if leg_raw is None:
        meta = row.get("meta")
        if isinstance(meta, dict):
            leg_raw = meta.get("leg")
    if isinstance(leg_raw, str):
        leg = leg_raw.strip().lower()
        if leg in {"yes", "no"}:
            return leg
    return None


def _row_in_time_window(
    row: dict[str, Any],
    *,
    time_from: float | None,
    time_to: float | None,
) -> bool:
    if time_from is None and time_to is None:
        return True
    ts_recv = _as_float(row.get("ts_recv"))
    if ts_recv is None:
        return False
    if time_from is not None and ts_recv < time_from:
        return False
    if time_to is not None and ts_recv > time_to:
        return False
    return True


def _filter_rows(
    rows: list[dict[str, Any]],
    *,
    time_from: float | None = None,
    time_to: float | None = None,
    asset_filter: str = "all",
    reason_type: str | None = None,
    asset_context: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    filtered: list[dict[str, Any]] = []
    for row in rows:
        if not _row_in_time_window(row, time_from=time_from, time_to=time_to):
            continue
        if asset_filter in {"yes", "no"} and asset_context is not None:
            leg = _infer_row_leg(row, asset_context)
            if leg != asset_filter:
                continue
        if reason_type is not None:
            reason = str(row.get("reason") or "").strip()
            if reason != reason_type:
                continue
        filtered.append(row)
    return filtered


def _load_best_bid_ask_series(
    path: Path,
    *,
    max_points: int,
    time_from: float | None = None,
    time_to: float | None = None,
    asset_filter: str = "all",
    asset_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    source_rows = 0
    filtered_rows: list[dict[str, Any]] = []
    for raw in _iter_jsonl_dict_rows(path):
        point = _normalize_bbo_point(raw)
        if point is None:
            continue
        source_rows += 1
        if not _row_in_time_window(point, time_from=time_from, time_to=time_to):
            continue
        if asset_filter in {"yes", "no"} and asset_context is not None:
            leg = _infer_row_leg(point, asset_context)
            if leg != asset_filter:
                continue
        filtered_rows.append(point)

    sampled_rows = _downsample_rows(filtered_rows, max_points=max_points)

    asset_ids = sorted(
        {
            str(row.get("asset_id") or "")
            for row in filtered_rows
            if str(row.get("asset_id") or "")
        }
    )
    ts_values = [
        ts
        for ts in (_as_float(row.get("ts_recv")) for row in filtered_rows)
        if ts is not None
    ]
    seq_values = [
        seq
        for seq in (
            int(row["seq"])
            for row in filtered_rows
            if row.get("seq") is not None and str(row.get("seq")).strip() != ""
        )
    ]

    return {
        "source_rows": source_rows,
        "filtered_rows": len(filtered_rows),
        "downsampled_rows": len(sampled_rows),
        "points": sampled_rows,
        "asset_ids": asset_ids,
        "min_ts_recv": min(ts_values) if ts_values else None,
        "max_ts_recv": max(ts_values) if ts_values else None,
        "min_seq": min(seq_values) if seq_values else None,
        "max_seq": max(seq_values) if seq_values else None,
    }


def _build_reason_counts(
    *,
    decisions: list[dict[str, Any]],
    rejection_reasons: list[dict[str, Any]],
    reason_type: str | None = None,
) -> list[dict[str, Any]]:
    counts: Counter[str] = Counter()
    for row in rejection_reasons:
        reason = str(row.get("reason") or "").strip()
        if not reason:
            continue
        if reason_type is not None and reason != reason_type:
            continue
        try:
            count = int(row.get("count") or 0)
        except (TypeError, ValueError):
            count = 0
        if count > 0:
            counts[reason] += count
    for row in decisions:
        reason = str(row.get("reason") or "").strip()
        if not reason:
            continue
        if reason_type is not None and reason != reason_type:
            continue
        counts[reason] += 1
    return [
        {"reason": reason, "count": count}
        for reason, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    ]


def _decorate_session_snapshot(snapshot: dict[str, Any], artifacts_root: Path) -> dict[str, Any]:
    row = dict(snapshot)
    display_name = row.get("display_name")
    if isinstance(display_name, str) and display_name.strip():
        row["display_name"] = display_name.strip()
    else:
        row["display_name"] = derive_session_display_name(row)
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

    @app.get("/api/simulation/{artifact_type}/{artifact_id}/series")
    async def simulation_series(
        artifact_type: str,
        artifact_id: str,
        max_points: int = Query(default=1200, ge=2, le=5000),
        time_from: str | None = Query(default=None),
        time_to: str | None = Query(default=None),
        asset: str = Query(default="all"),
    ) -> dict[str, Any]:
        artifact_dir = _resolve_simulation_artifact_dir(
            _artifacts_dir,
            artifact_type=artifact_type,
            artifact_id=artifact_id,
        )
        asset_filter = asset.strip().lower()
        if asset_filter not in {"all", "yes", "no"}:
            raise HTTPException(status_code=400, detail="asset must be one of: all, yes, no")
        try:
            from_bound = _parse_time_bound(time_from)
            to_bound = _parse_time_bound(time_to)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        if from_bound is not None and to_bound is not None and from_bound > to_bound:
            raise HTTPException(status_code=400, detail="time_from must be <= time_to")

        run_manifest = _read_json_file(artifact_dir / "run_manifest.json") or {}
        artifact_display_name = derive_artifact_display_name(
            artifact_type=artifact_type.strip().lower(),
            artifact_id=artifact_id.strip(),
            manifest=run_manifest,
        )
        asset_context = _extract_asset_context(run_manifest)
        series = _load_best_bid_ask_series(
            artifact_dir / "best_bid_ask.jsonl",
            max_points=max_points,
            time_from=from_bound,
            time_to=to_bound,
            asset_filter=asset_filter,
            asset_context=asset_context,
        )
        return {
            "artifact": {
                "artifact_type": artifact_type.strip().lower(),
                "artifact_id": artifact_id.strip(),
                "display_name": artifact_display_name,
                "artifact_path": str(artifact_dir),
                "timestamp": _extract_timestamp(artifact_dir),
            },
            "asset_context": asset_context,
            "series": series,
            "filters": {
                "time_from": from_bound,
                "time_to": to_bound,
                "asset": asset_filter,
            },
        }

    @app.get("/api/simulation/{artifact_type}/{artifact_id}/viewer")
    async def simulation_viewer(
        artifact_type: str,
        artifact_id: str,
        series_points: int = Query(default=1200, ge=2, le=5000),
        equity_limit: int = Query(default=2000, ge=10, le=10000),
        row_limit: int = Query(default=1000, ge=10, le=10000),
        time_from: str | None = Query(default=None),
        time_to: str | None = Query(default=None),
        reason_type: str | None = Query(default=None),
        asset: str = Query(default="all"),
    ) -> dict[str, Any]:
        artifact_dir = _resolve_simulation_artifact_dir(
            _artifacts_dir,
            artifact_type=artifact_type,
            artifact_id=artifact_id,
        )

        asset_filter = asset.strip().lower()
        if asset_filter not in {"all", "yes", "no"}:
            raise HTTPException(status_code=400, detail="asset must be one of: all, yes, no")
        reason_filter = (reason_type or "").strip()
        if not reason_filter or reason_filter.lower() == "all":
            reason_filter = ""

        try:
            from_bound = _parse_time_bound(time_from)
            to_bound = _parse_time_bound(time_to)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        if from_bound is not None and to_bound is not None and from_bound > to_bound:
            raise HTTPException(status_code=400, detail="time_from must be <= time_to")

        run_manifest = _read_json_file(artifact_dir / "run_manifest.json") or {}
        artifact_display_name = derive_artifact_display_name(
            artifact_type=artifact_type.strip().lower(),
            artifact_id=artifact_id.strip(),
            manifest=run_manifest,
        )
        summary = _read_json_file(artifact_dir / "summary.json") or {}
        asset_context = _extract_asset_context(run_manifest)
        rejection_reasons = _extract_rejection_rows(run_manifest=run_manifest, summary=summary)

        best_bid_ask = _load_best_bid_ask_series(
            artifact_dir / "best_bid_ask.jsonl",
            max_points=series_points,
            time_from=from_bound,
            time_to=to_bound,
            asset_filter=asset_filter,
            asset_context=asset_context,
        )

        equity_curve_raw = _read_jsonl_rows(artifact_dir / "equity_curve.jsonl", limit=equity_limit)
        orders_raw = _read_jsonl_rows(artifact_dir / "orders.jsonl", limit=row_limit)
        fills_raw = _read_jsonl_rows(artifact_dir / "fills.jsonl", limit=row_limit)
        decisions_raw = _read_jsonl_rows(artifact_dir / "decisions.jsonl", limit=row_limit)
        ledger_raw = _read_jsonl_rows(artifact_dir / "ledger.jsonl", limit=row_limit)

        equity_curve = _filter_rows(
            equity_curve_raw,
            time_from=from_bound,
            time_to=to_bound,
        )
        orders = _filter_rows(
            orders_raw,
            time_from=from_bound,
            time_to=to_bound,
            asset_filter=asset_filter,
            asset_context=asset_context,
        )
        fills = _filter_rows(
            fills_raw,
            time_from=from_bound,
            time_to=to_bound,
            asset_filter=asset_filter,
            asset_context=asset_context,
        )
        decisions = _filter_rows(
            decisions_raw,
            time_from=from_bound,
            time_to=to_bound,
            asset_filter=asset_filter,
            reason_type=reason_filter or None,
            asset_context=asset_context,
        )
        ledger_snapshots = _filter_rows(
            ledger_raw,
            time_from=from_bound,
            time_to=to_bound,
        )
        if reason_filter:
            rejection_reasons = [
                row
                for row in rejection_reasons
                if str(row.get("reason") or "").strip() == reason_filter
            ]

        reason_counts = _build_reason_counts(
            decisions=decisions,
            rejection_reasons=rejection_reasons,
            reason_type=reason_filter or None,
        )

        reason_types: set[str] = {
            str(row.get("reason") or "").strip()
            for row in rejection_reasons
            if str(row.get("reason") or "").strip()
        }
        reason_types.update(
            str(row.get("reason") or "").strip()
            for row in decisions_raw
            if str(row.get("reason") or "").strip()
        )

        return {
            "artifact": {
                "artifact_type": artifact_type.strip().lower(),
                "artifact_id": artifact_id.strip(),
                "display_name": artifact_display_name,
                "artifact_path": str(artifact_dir),
                "timestamp": _extract_timestamp(artifact_dir),
            },
            "asset_context": asset_context,
            "summary": summary,
            "run_manifest": run_manifest,
            "best_bid_ask": best_bid_ask,
            "equity_curve": equity_curve,
            "orders": orders,
            "fills": fills,
            "decisions": decisions,
            "ledger_snapshots": ledger_snapshots,
            "rejection_reasons": rejection_reasons,
            "reason_counts": reason_counts,
            "available_reason_types": sorted(reason_types),
            "filters": {
                "time_from": from_bound,
                "time_to": to_bound,
                "asset": asset_filter,
                "reason_type": reason_filter or "all",
            },
        }

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

    @app.get("/api/sessions/{session_id}/monitor")
    async def session_monitor(session_id: str) -> dict[str, Any]:
        """Lightweight stats endpoint — reads only run_manifest.json and summary.json.

        Returns run_metrics, net_profit, strategy, and basic counts without
        loading equity_curve, orders, fills, or decisions rows.
        """
        session = _get_tracked_session(session_id)

        artifact_raw = session.get("artifact_dir")
        run_metrics: dict[str, Any] = {}
        net_profit = None
        strategy = None
        decisions_count = None
        orders_count = None
        fills_count = None

        if isinstance(artifact_raw, str) and artifact_raw:
            artifact_dir = Path(artifact_raw).resolve()
            if artifact_dir.exists() and artifact_dir.is_dir():
                run_manifest = _read_json_file(artifact_dir / "run_manifest.json") or {}
                summary = _read_json_file(artifact_dir / "summary.json") or {}

                raw_metrics = run_manifest.get("run_metrics")
                if isinstance(raw_metrics, dict):
                    run_metrics = {
                        "events_received": raw_metrics.get("events_received"),
                        "ws_reconnects": raw_metrics.get("ws_reconnects"),
                        "ws_timeouts": raw_metrics.get("ws_timeouts"),
                    }

                net_profit = run_manifest.get("net_profit") or summary.get("net_profit")
                strategy = run_manifest.get("strategy") or summary.get("strategy")

                decisions_count = run_manifest.get("decisions_count")
                if decisions_count is None:
                    decisions_count = summary.get("decisions_count")

                orders_count = run_manifest.get("orders_count")
                if orders_count is None:
                    orders_count = summary.get("orders_count")

                fills_count = run_manifest.get("fills_count")
                if fills_count is None:
                    fills_count = summary.get("fills_count")

        return {
            "session_id": session_id,
            "status": session.get("status"),
            "started_at": session.get("started_at"),
            "subcommand": session.get("subcommand") or session.get("kind"),
            "report_url": session.get("report_url"),
            "artifact_dir": session.get("artifact_dir"),
            "run_metrics": run_metrics,
            "net_profit": net_profit,
            "strategy": strategy,
            "decisions_count": decisions_count,
            "orders_count": orders_count,
            "fills_count": fills_count,
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

        checkpoint_create_kwargs: dict[str, Any] = {}

        checkpoint_every_events_raw = body.get("checkpoint_every_events")
        if checkpoint_every_events_raw is not None and str(checkpoint_every_events_raw).strip():
            try:
                checkpoint_create_kwargs["checkpoint_every_events"] = int(checkpoint_every_events_raw)
            except (TypeError, ValueError):
                raise HTTPException(
                    status_code=400,
                    detail=f"invalid checkpoint_every_events: {checkpoint_every_events_raw!r}",
                )

        checkpoint_every_seconds_raw = body.get("checkpoint_every_seconds")
        if checkpoint_every_seconds_raw is not None and str(checkpoint_every_seconds_raw).strip():
            try:
                checkpoint_create_kwargs["checkpoint_every_seconds"] = float(checkpoint_every_seconds_raw)
            except (TypeError, ValueError):
                raise HTTPException(
                    status_code=400,
                    detail=f"invalid checkpoint_every_seconds: {checkpoint_every_seconds_raw!r}",
                )

        max_checkpoints_raw = body.get("max_checkpoints")
        if max_checkpoints_raw is not None and str(max_checkpoints_raw).strip():
            try:
                checkpoint_create_kwargs["max_checkpoints"] = int(max_checkpoints_raw)
            except (TypeError, ValueError):
                raise HTTPException(
                    status_code=400,
                    detail=f"invalid max_checkpoints: {max_checkpoints_raw!r}",
                )

        mark_method = body.get("mark_method", "bid")
        if mark_method not in ("bid", "midpoint"):
            raise HTTPException(status_code=400, detail=f"mark_method must be 'bid' or 'midpoint'; got {mark_method!r}")

        try:
            session = _ondemand_sessions.create(
                tape_path_str,
                starting_cash,
                fee_rate_bps,
                mark_method,
                **checkpoint_create_kwargs,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        return {"session_id": session.session_id, "state": session.get_state()}

    @app.get("/api/ondemand")
    async def ondemand_list() -> dict[str, Any]:
        rows: list[dict[str, Any]] = []
        for session in _ondemand_sessions.list():
            rows.append(
                {
                    "session_id": session.session_id,
                    "tape_path": session.tape_path,
                    "state": session.get_state(),
                }
            )
        return {"sessions": rows}

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

    @app.post("/api/ondemand/{session_id}/seek")
    async def ondemand_seek(session_id: str, body: dict[str, Any]) -> dict[str, Any]:
        session = _get_ondemand_session(_ondemand_sessions, session_id)
        raw_timestamp = body.get("timestamp")
        if raw_timestamp is None or str(raw_timestamp).strip() == "":
            raise HTTPException(status_code=400, detail="timestamp is required")
        try:
            timestamp = float(raw_timestamp)
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail=f"invalid timestamp: {raw_timestamp!r}")
        return {"state": session.seek_to(timestamp)}

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

