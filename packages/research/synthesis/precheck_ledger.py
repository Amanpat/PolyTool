"""RIS v1 synthesis — append-only JSONL precheck ledger.

Replicates the JSONL pattern from packages/research/hypotheses/registry.py.

Schema versions:
- precheck_ledger_v0: original schema (no enriched fields)
- precheck_ledger_v1: adds precheck_id, reason_code, evidence_gap, review_horizon
- precheck_ledger_v2: adds override and outcome event types, get_precheck_history,
  list_prechecks_by_window
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from packages.research.synthesis.precheck import PrecheckResult

LEDGER_SCHEMA_VERSION = "precheck_ledger_v2"
DEFAULT_LEDGER_PATH = Path("artifacts/research/prechecks/precheck_ledger.jsonl")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _iso_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat()


def _iter_events(path: Path):
    """Yield parsed dicts from a JSONL file, skipping blank lines.

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


def append_precheck(result: "PrecheckResult", ledger_path: Path | None = None) -> None:
    """Append a precheck result as a JSONL line to the ledger.

    Creates parent directories and the file if they do not exist.

    Schema version: precheck_ledger_v1 (adds precheck_id, reason_code,
    evidence_gap, review_horizon to the event dict).

    v0 entries written before the schema bump are still readable by
    list_prechecks() -- missing fields will simply be absent from the
    returned dict (callers should use .get() with a default).

    Args:
        result: The PrecheckResult to persist.
        ledger_path: Path to the JSONL ledger file. Defaults to DEFAULT_LEDGER_PATH.
    """
    path = ledger_path if ledger_path is not None else DEFAULT_LEDGER_PATH
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    event = {
        "schema_version": LEDGER_SCHEMA_VERSION,
        "event_type": "precheck_run",
        "recommendation": result.recommendation,
        "idea": result.idea,
        "supporting_evidence": result.supporting_evidence,
        "contradicting_evidence": result.contradicting_evidence,
        "risk_factors": result.risk_factors,
        "stale_warning": result.stale_warning,
        "timestamp": result.timestamp,
        "provider_used": result.provider_used,
        # Enriched fields (v1)
        "precheck_id": result.precheck_id,
        "reason_code": result.reason_code,
        "evidence_gap": result.evidence_gap,
        "review_horizon": result.review_horizon,
        "written_at": _iso_utc(_utcnow()),
    }

    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, sort_keys=True, separators=(",", ":"), allow_nan=False))
        f.write("\n")


def list_prechecks(ledger_path: Path | None = None) -> list[dict]:
    """Read all precheck entries from the ledger.

    Returns raw dicts from JSONL. v0 entries (missing enriched fields) are
    returned as-is; callers should use .get() with a default for new fields.

    Args:
        ledger_path: Path to the JSONL ledger file. Defaults to DEFAULT_LEDGER_PATH.

    Returns:
        List of parsed dicts (empty list if file does not exist).
    """
    path = ledger_path if ledger_path is not None else DEFAULT_LEDGER_PATH
    path = Path(path)
    return list(_iter_events(path))


def append_override(
    precheck_id: str,
    override_reason: str,
    ledger_path: Path | None = None,
) -> None:
    """Append an operator override event to the ledger.

    Records that an operator manually overrode the precheck recommendation
    for a given precheck_id.

    Args:
        precheck_id: The precheck ID to override. Must be non-empty.
        override_reason: Human-readable reason for the override. May be empty.
        ledger_path: Path to the JSONL ledger file. Defaults to DEFAULT_LEDGER_PATH.

    Raises:
        ValueError: If precheck_id is empty.
    """
    if not precheck_id:
        raise ValueError("precheck_id must be a non-empty string")

    path = ledger_path if ledger_path is not None else DEFAULT_LEDGER_PATH
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    event = {
        "schema_version": LEDGER_SCHEMA_VERSION,
        "event_type": "override",
        "precheck_id": precheck_id,
        "was_overridden": True,
        "override_reason": override_reason,
        "written_at": _iso_utc(_utcnow()),
    }

    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, sort_keys=True, separators=(",", ":"), allow_nan=False))
        f.write("\n")


_VALID_OUTCOME_LABELS = frozenset({"successful", "failed", "partial", "not_tried"})


def append_outcome(
    precheck_id: str,
    outcome_label: str,
    outcome_date: str | None = None,
    ledger_path: Path | None = None,
) -> None:
    """Append an outcome event to the ledger.

    Records the actual outcome of an idea that was previously precheckd.

    Args:
        precheck_id: The precheck ID to record the outcome for.
        outcome_label: One of "successful", "failed", "partial", "not_tried".
        outcome_date: ISO-8601 date string. Defaults to current UTC time.
        ledger_path: Path to the JSONL ledger file. Defaults to DEFAULT_LEDGER_PATH.

    Raises:
        ValueError: If outcome_label is not one of the valid values.
    """
    if outcome_label not in _VALID_OUTCOME_LABELS:
        raise ValueError(
            f"outcome_label must be one of {sorted(_VALID_OUTCOME_LABELS)}, "
            f"got {outcome_label!r}"
        )

    path = ledger_path if ledger_path is not None else DEFAULT_LEDGER_PATH
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    resolved_outcome_date = outcome_date if outcome_date is not None else _iso_utc(_utcnow())

    event = {
        "schema_version": LEDGER_SCHEMA_VERSION,
        "event_type": "outcome",
        "precheck_id": precheck_id,
        "outcome_label": outcome_label,
        "outcome_date": resolved_outcome_date,
        "written_at": _iso_utc(_utcnow()),
    }

    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, sort_keys=True, separators=(",", ":"), allow_nan=False))
        f.write("\n")


def get_precheck_history(
    precheck_id: str,
    ledger_path: Path | None = None,
) -> list[dict]:
    """Return all events for a given precheck_id, sorted by written_at ascending.

    Returns events of any type (precheck_run, override, outcome) that match
    the given precheck_id. Events without a written_at field sort to the front.

    Args:
        precheck_id: The precheck ID to query.
        ledger_path: Path to the JSONL ledger file. Defaults to DEFAULT_LEDGER_PATH.

    Returns:
        List of matching event dicts sorted by written_at ascending.
    """
    path = ledger_path if ledger_path is not None else DEFAULT_LEDGER_PATH
    path = Path(path)
    matching = [
        event for event in _iter_events(path)
        if event.get("precheck_id") == precheck_id
    ]
    matching.sort(key=lambda e: e.get("written_at", ""))
    return matching


def list_prechecks_by_window(
    start_iso: str,
    end_iso: str,
    ledger_path: Path | None = None,
) -> list[dict]:
    """Return all events whose written_at falls within [start_iso, end_iso].

    ISO string comparison is used (UTC ISO-8601 strings sort lexicographically).
    Events without a written_at field are excluded.

    Args:
        start_iso: Start of window (inclusive), ISO-8601 string.
        end_iso: End of window (inclusive), ISO-8601 string.
        ledger_path: Path to the JSONL ledger file. Defaults to DEFAULT_LEDGER_PATH.

    Returns:
        List of event dicts within the time window.
    """
    path = ledger_path if ledger_path is not None else DEFAULT_LEDGER_PATH
    path = Path(path)
    results = []
    for event in _iter_events(path):
        written_at = event.get("written_at", "")
        if written_at and start_iso <= written_at <= end_iso:
            results.append(event)
    return results
