"""RIS v1 synthesis — append-only JSONL precheck ledger.

Replicates the JSONL pattern from packages/research/hypotheses/registry.py.

Schema versions:
- precheck_ledger_v0: original schema (no enriched fields)
- precheck_ledger_v1: adds precheck_id, reason_code, evidence_gap, review_horizon
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from packages.research.synthesis.precheck import PrecheckResult

LEDGER_SCHEMA_VERSION = "precheck_ledger_v1"
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
