"""Offline hypothesis registry plus experiment-init/experiment-run helpers."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

SCHEMA_VERSION = "hypothesis_registry_v0"
EXPERIMENT_SCHEMA_VERSION = "experiment_init_v0"
VALID_STATUSES = ("proposed", "testing", "validated", "rejected", "parked")

_RANK_SUFFIX_RE = re.compile(r"__rank\d+$")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _iso_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat()


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _read_json(path: Path) -> Dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object in {path}")
    return payload


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False),
        encoding="utf-8",
    )


def _normalize_candidate_id(candidate_id: Any) -> str:
    return _RANK_SUFFIX_RE.sub("", _clean_text(candidate_id))


def _infer_dimension_key(candidate: dict) -> tuple[str, str]:
    evidence_refs = candidate.get("evidence_refs")
    if isinstance(evidence_refs, list):
        for item in evidence_refs:
            if not isinstance(item, dict):
                continue
            dimension = _clean_text(item.get("dimension"))
            key = _clean_text(item.get("key"))
            if dimension and key:
                return dimension, key

    normalized_candidate_id = _normalize_candidate_id(candidate.get("candidate_id"))
    if normalized_candidate_id and "__" in normalized_candidate_id:
        dimension, key = normalized_candidate_id.split("__", 1)
        if dimension and key:
            return dimension, key

    segment_key = _clean_text(candidate.get("segment_key"))
    if "=" in segment_key:
        dimension, key = segment_key.split("=", 1)
        return dimension.strip(), key.strip()

    return "", ""


def _candidate_identity_payload(candidate: dict) -> Dict[str, Any]:
    dimension, key = _infer_dimension_key(candidate)
    if dimension and key:
        return {
            "kind": "dimension_key",
            "dimension": dimension,
            "key": key,
        }

    segment_key = _clean_text(candidate.get("segment_key"))
    if segment_key:
        return {
            "kind": "segment_key",
            "segment_key": segment_key,
        }

    normalized_candidate_id = _normalize_candidate_id(candidate.get("candidate_id"))
    if normalized_candidate_id:
        return {
            "kind": "candidate_id",
            "candidate_id": normalized_candidate_id,
        }

    fallback = {
        "kind": "fallback",
        "label": _clean_text(candidate.get("label")),
        "mechanism_hint": _clean_text(candidate.get("mechanism_hint")),
        "next_test": _clean_text(candidate.get("next_test")),
        "stop_condition": _clean_text(candidate.get("stop_condition")),
    }
    if any(value for key_name, value in fallback.items() if key_name != "kind"):
        return fallback
    return {
        "kind": "raw_candidate",
        "candidate": candidate,
    }


def _iter_events(path: Path) -> list[Dict[str, Any]]:
    events: list[Dict[str, Any]] = []
    if not path.exists():
        return events
    for line_no, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSONL event in {path} at line {line_no}") from exc
        if not isinstance(payload, dict):
            raise ValueError(f"Invalid JSONL event in {path} at line {line_no}: expected object")
        events.append(payload)
    return events


def _select_candidate(candidates: list[Any], rank: int) -> dict:
    if rank <= 0:
        raise ValueError("--rank must be a positive integer")

    for item in candidates:
        if not isinstance(item, dict):
            continue
        try:
            candidate_rank = int(item.get("rank"))
        except (TypeError, ValueError):
            continue
        if candidate_rank == rank:
            return item

    index = rank - 1
    if 0 <= index < len(candidates) and isinstance(candidates[index], dict):
        return candidates[index]

    raise KeyError(f"Candidate rank {rank} not found")


def _stop_conditions(candidate: dict) -> list[str]:
    values: list[str] = []

    stop_condition = _clean_text(candidate.get("stop_condition"))
    if stop_condition:
        values.append(stop_condition)

    falsification_plan = candidate.get("falsification_plan")
    if isinstance(falsification_plan, dict):
        for item in falsification_plan.get("stop_conditions") or []:
            text = _clean_text(item)
            if text:
                values.append(text)

    deduped: list[str] = []
    seen: set[str] = set()
    for item in values:
        if item in seen:
            continue
        seen.add(item)
        deduped.append(item)
    return deduped


def stable_hypothesis_id(candidate: dict) -> str:
    """Build a deterministic hypothesis ID from stable candidate identity fields."""
    if not isinstance(candidate, dict):
        raise TypeError("candidate must be a dict")

    canonical = _candidate_identity_payload(candidate)
    payload = json.dumps(canonical, sort_keys=True, separators=(",", ":"), allow_nan=False)
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
    return f"hyp_{digest}"


def append_event(path: str | Path, event: dict) -> None:
    """Append one registry event as a JSONL line."""
    if not isinstance(event, dict):
        raise TypeError("event must be a dict")

    registry_path = Path(path)
    registry_path.parent.mkdir(parents=True, exist_ok=True)

    payload = dict(event)
    payload.setdefault("schema_version", SCHEMA_VERSION)

    with registry_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False))
        handle.write("\n")


def get_latest(path: str | Path, hypothesis_id: str) -> dict:
    """Materialize the latest state for one hypothesis from append-only events."""
    registry_path = Path(path)
    if not registry_path.exists():
        raise FileNotFoundError(registry_path)

    state: dict[str, Any] | None = None
    for event in _iter_events(registry_path):
        if _clean_text(event.get("hypothesis_id")) != hypothesis_id:
            continue
        if state is None:
            state = {}
        state.update(event)

    if state is None:
        raise KeyError(f"Hypothesis not found: {hypothesis_id}")
    return state


def register_from_candidate(
    registry_path: str | Path,
    candidate_file: str | Path,
    rank: int,
    title: str | None = None,
    notes: str | None = None,
) -> str:
    """Register one candidate from an alpha_candidates-style JSON file."""
    candidate_path = Path(candidate_file)
    payload = _read_json(candidate_path)

    candidates = payload.get("candidates")
    if not isinstance(candidates, list):
        raise ValueError(f"Candidate file missing top-level 'candidates' list: {candidate_path}")

    candidate = _select_candidate(candidates, rank)
    hypothesis_id = stable_hypothesis_id(candidate)

    try:
        get_latest(registry_path, hypothesis_id)
    except (FileNotFoundError, KeyError):
        created_at = _iso_utc(_utcnow())

        assumptions: list[str] = []
        mechanism_hint = _clean_text(candidate.get("mechanism_hint"))
        if mechanism_hint:
            assumptions.append(mechanism_hint)

        note_rows: list[str] = []
        notes_text = _clean_text(notes)
        if notes_text:
            note_rows.append(notes_text)

        metrics_plan: dict[str, Any] = {}
        next_test = _clean_text(candidate.get("next_test"))
        if next_test:
            metrics_plan["next_test"] = next_test
        measured_edge = candidate.get("measured_edge")
        if isinstance(measured_edge, dict):
            metrics_plan["measured_edge"] = measured_edge
        metrics = candidate.get("metrics")
        if isinstance(metrics, dict):
            metrics_plan["metrics"] = metrics
        sample_size = candidate.get("sample_size")
        if sample_size is not None:
            metrics_plan["sample_size"] = sample_size

        event = {
            "schema_version": SCHEMA_VERSION,
            "hypothesis_id": hypothesis_id,
            "title": _clean_text(title) or _clean_text(candidate.get("label")) or hypothesis_id,
            "created_at": created_at,
            "status": "proposed",
            "source": {
                "candidate_file": candidate_path.as_posix(),
                "rank": rank,
                "source_candidate_id": _clean_text(candidate.get("candidate_id"))
                or _clean_text(candidate.get("segment_key")),
                "candidate_schema_version": _clean_text(payload.get("schema_version")) or None,
            },
            "assumptions": assumptions,
            "metrics_plan": metrics_plan,
            "stop_conditions": _stop_conditions(candidate),
            "notes": note_rows,
            "status_reason": None,
            "event_type": "registered",
            "event_at": created_at,
        }
        append_event(registry_path, event)

    return hypothesis_id


def update_status(
    registry_path: str | Path,
    hypothesis_id: str,
    status: str,
    reason: str,
) -> None:
    """Append a full-snapshot status change event."""
    normalized_status = _clean_text(status)
    if normalized_status not in VALID_STATUSES:
        raise ValueError(
            f"Invalid status '{status}'. Expected one of: {', '.join(VALID_STATUSES)}"
        )

    reason_text = _clean_text(reason)
    if not reason_text:
        raise ValueError("reason must be non-empty")

    latest = get_latest(registry_path, hypothesis_id)
    snapshot = dict(latest)
    snapshot["schema_version"] = SCHEMA_VERSION
    snapshot["status"] = normalized_status
    snapshot["status_reason"] = reason_text
    snapshot["event_type"] = "status_change"
    snapshot["event_at"] = _iso_utc(_utcnow())
    append_event(registry_path, snapshot)


def _build_experiment_payload(
    hypothesis_id: str,
    experiment_id: str,
    registry_snapshot: dict,
    *,
    created_at: str | None = None,
) -> Dict[str, Any]:
    """Build the experiment.json payload shared by init and run flows."""
    if not isinstance(registry_snapshot, dict):
        raise TypeError("registry_snapshot must be a dict")
    if _clean_text(registry_snapshot.get("hypothesis_id")) != hypothesis_id:
        raise ValueError("registry_snapshot does not match hypothesis_id")

    source = registry_snapshot.get("source")
    if not isinstance(source, dict):
        source = {}

    return {
        "schema_version": EXPERIMENT_SCHEMA_VERSION,
        "experiment_id": experiment_id,
        "hypothesis_id": hypothesis_id,
        "created_at": created_at or _iso_utc(_utcnow()),
        "registry_snapshot": {
            "hypothesis_id": registry_snapshot.get("hypothesis_id"),
            "title": registry_snapshot.get("title"),
            "status": registry_snapshot.get("status"),
            "created_at": registry_snapshot.get("created_at"),
            "source": source,
        },
        "inputs": {
            "candidate_file": source.get("candidate_file"),
            "candidate_rank": source.get("rank"),
            "source_candidate_id": source.get("source_candidate_id"),
        },
        "planned_execution": {
            "tape_path": None,
            "sweep_config": {},
            "notes": [],
        },
        "metrics_plan": registry_snapshot.get("metrics_plan") or {},
        "stop_conditions": registry_snapshot.get("stop_conditions") or [],
        "notes": registry_snapshot.get("notes") or [],
    }


def experiment_init(outdir: str | Path, hypothesis_id: str, registry_snapshot: dict) -> Path:
    """Write an experiment.json skeleton for a registered hypothesis."""
    outdir_path = Path(outdir)
    payload = _build_experiment_payload(
        hypothesis_id=hypothesis_id,
        experiment_id=outdir_path.name or hypothesis_id,
        registry_snapshot=registry_snapshot,
    )

    out_path = outdir_path / "experiment.json"
    _write_json(out_path, payload)
    return out_path


def _next_experiment_id(outdir: str | Path, created_at: datetime) -> str:
    """Generate a stable experiment attempt ID within an output root."""
    outdir_path = Path(outdir)
    base_id = created_at.astimezone(timezone.utc).strftime("exp-%Y%m%dT%H%M%SZ")
    experiment_id = base_id
    collision_index = 2
    while (outdir_path / experiment_id).exists():
        experiment_id = f"{base_id}-{collision_index:02d}"
        collision_index += 1
    return experiment_id


def experiment_run(outdir: str | Path, hypothesis_id: str, registry_snapshot: dict) -> Path:
    """Create a generated experiment attempt directory and write experiment.json."""
    outdir_path = Path(outdir)
    created_at_dt = _utcnow()
    experiment_id = _next_experiment_id(outdir_path, created_at_dt)
    payload = _build_experiment_payload(
        hypothesis_id=hypothesis_id,
        experiment_id=experiment_id,
        registry_snapshot=registry_snapshot,
        created_at=_iso_utc(created_at_dt),
    )

    out_path = outdir_path / experiment_id / "experiment.json"
    _write_json(out_path, payload)
    return out_path
