"""RIS v1 operational layer — append-only pipeline run log.

Tracks each RIS pipeline execution with outcome, counts, and duration.
Persisted as JSONL at artifacts/research/run_log.jsonl by default.

Schema version: run_log_v1
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal, Optional

DEFAULT_RUN_LOG_PATH = Path("artifacts/research/run_log.jsonl")

_SCHEMA_VERSION = "run_log_v1"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _iso_utc(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat()


def _make_run_id(pipeline: str, started_at: str) -> str:
    """Derive a short deterministic run ID from pipeline + started_at."""
    return hashlib.sha256(f"{pipeline}{started_at}".encode()).hexdigest()[:12]


@dataclass
class RunRecord:
    """One RIS pipeline execution record.

    Fields:
        run_id:        Short 12-char ID derived from pipeline+started_at.
        pipeline:      Pipeline name (e.g. "ris_ingest").
        started_at:    ISO-8601 UTC timestamp of run start.
        duration_s:    Elapsed seconds.
        accepted:      Documents accepted this run.
        rejected:      Documents rejected this run.
        errors:        Hard errors encountered.
        exit_status:   "ok" | "error" | "partial"
        metadata:      Free-form extra data.
        schema_version: Always "run_log_v1".
    """

    pipeline: str
    started_at: str
    duration_s: float
    accepted: int
    rejected: int
    errors: int
    exit_status: Literal["ok", "error", "partial"]
    run_id: str = field(default="")
    metadata: dict = field(default_factory=dict)
    schema_version: str = field(default=_SCHEMA_VERSION)

    def __post_init__(self) -> None:
        if not self.run_id:
            self.run_id = _make_run_id(self.pipeline, self.started_at)


def _iter_lines(path: Path):
    """Yield parsed dicts from JSONL, skipping blank/invalid lines.

    Returns empty iterator if file does not exist.
    """
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        try:
            payload = json.loads(stripped)
            if isinstance(payload, dict):
                yield payload
        except json.JSONDecodeError:
            continue


def _dict_to_record(d: dict) -> RunRecord:
    return RunRecord(
        run_id=d.get("run_id", ""),
        pipeline=d.get("pipeline", ""),
        started_at=d.get("started_at", ""),
        duration_s=float(d.get("duration_s", 0.0)),
        accepted=int(d.get("accepted", 0)),
        rejected=int(d.get("rejected", 0)),
        errors=int(d.get("errors", 0)),
        exit_status=d.get("exit_status", "ok"),  # type: ignore[arg-type]
        metadata=d.get("metadata", {}),
        schema_version=d.get("schema_version", _SCHEMA_VERSION),
    )


def append_run(record: RunRecord, path: Optional[Path] = None) -> None:
    """Append a RunRecord as a JSONL line to the run log.

    Creates parent directories and the file if they do not exist.
    Always appends — never overwrites existing data.

    Args:
        record: The RunRecord to persist.
        path:   Path to the JSONL log file. Defaults to DEFAULT_RUN_LOG_PATH.
    """
    target = Path(path) if path is not None else DEFAULT_RUN_LOG_PATH
    target.parent.mkdir(parents=True, exist_ok=True)

    event = {
        "schema_version": record.schema_version,
        "run_id": record.run_id,
        "pipeline": record.pipeline,
        "started_at": record.started_at,
        "duration_s": record.duration_s,
        "accepted": record.accepted,
        "rejected": record.rejected,
        "errors": record.errors,
        "exit_status": record.exit_status,
        "metadata": record.metadata,
    }

    with target.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, sort_keys=True, separators=(",", ":"), allow_nan=False))
        f.write("\n")


def list_runs(
    path: Optional[Path] = None,
    window_hours: Optional[float] = None,
) -> list[RunRecord]:
    """Read all run records, optionally filtered to a recent time window.

    Args:
        path:         Path to the JSONL log file. Defaults to DEFAULT_RUN_LOG_PATH.
        window_hours: If set, only return runs with started_at within the last N hours.

    Returns:
        List of RunRecord objects, newest first. Empty list if file absent.
    """
    target = Path(path) if path is not None else DEFAULT_RUN_LOG_PATH
    records = [_dict_to_record(d) for d in _iter_lines(target)]

    if window_hours is not None:
        cutoff = _utcnow().astimezone(timezone.utc)
        from datetime import timedelta
        cutoff = cutoff.replace(tzinfo=timezone.utc) if cutoff.tzinfo is None else cutoff
        threshold = cutoff - timedelta(hours=window_hours)
        threshold_iso = _iso_utc(threshold)
        records = [r for r in records if r.started_at >= threshold_iso]

    # Sort newest first (ISO strings compare lexicographically for UTC)
    records.sort(key=lambda r: r.started_at, reverse=True)
    return records


def load_last_run(path: Optional[Path] = None) -> Optional[RunRecord]:
    """Return the most recent RunRecord from the log.

    Args:
        path: Path to the JSONL log file. Defaults to DEFAULT_RUN_LOG_PATH.

    Returns:
        The RunRecord with the latest started_at, or None if log is empty / absent.
    """
    runs = list_runs(path=path)
    return runs[0] if runs else None
