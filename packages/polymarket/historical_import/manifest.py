"""Provenance manifests for bulk historical data imports.

Each manifest captures source_kind, local_path, a deterministic manifest_id,
destination ClickHouse tables, file_count, checksum, and import status.

manifest_id is sha256(f"{source_kind}:{resolved_absolute_path}") — always
deterministic given the same source kind and path.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional


SCHEMA_VERSION = "import_manifest_v0"


class SourceKind(str, Enum):
    PMXT_ARCHIVE = "pmxt_archive"
    JON_BECKER = "jon_becker"
    PRICE_HISTORY_2MIN = "price_history_2min"


_DESTINATION_TABLES: Dict[str, List[str]] = {
    SourceKind.PMXT_ARCHIVE.value: ["polytool.pmxt_l2_snapshots"],
    SourceKind.JON_BECKER.value: ["polytool.jb_trades"],
    SourceKind.PRICE_HISTORY_2MIN.value: ["polytool.price_history_2min"],
}


def _manifest_id(source_kind: str, resolved_path: str) -> str:
    """Deterministic manifest ID: sha256(source_kind + ':' + resolved_path)."""
    raw = f"{source_kind}:{resolved_path}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _utcnow() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@dataclass
class ProvenanceRecord:
    schema_version: str = SCHEMA_VERSION
    manifest_id: str = ""
    source_kind: str = ""
    local_path: str = ""
    resolved_path: str = ""
    destination_tables: List[str] = field(default_factory=list)
    snapshot_version: str = ""
    file_count: int = 0
    checksum: str = ""
    status: str = "staged"
    created_at: str = ""
    validated_at: str = ""
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, sort_keys=True)


def make_provenance_record(
    source_kind: str,
    local_path: str,
    *,
    status: str = "staged",
    file_count: int = 0,
    checksum: str = "",
    snapshot_version: str = "",
    notes: str = "",
) -> ProvenanceRecord:
    """Create a deterministic ProvenanceRecord for a local data source."""
    sk_values = {k.value for k in SourceKind}
    if source_kind not in sk_values:
        raise ValueError(
            f"Unknown source_kind {source_kind!r}. Valid values: {sorted(sk_values)}"
        )
    resolved = str(Path(local_path).resolve())
    mid = _manifest_id(source_kind, resolved)
    dest = list(_DESTINATION_TABLES.get(source_kind, []))
    return ProvenanceRecord(
        schema_version=SCHEMA_VERSION,
        manifest_id=mid,
        source_kind=source_kind,
        local_path=local_path,
        resolved_path=resolved,
        destination_tables=dest,
        snapshot_version=snapshot_version,
        file_count=file_count,
        checksum=checksum,
        status=status,
        created_at=_utcnow(),
        validated_at="",
        notes=notes,
    )


@dataclass
class ImportManifest:
    schema_version: str = SCHEMA_VERSION
    generated_at: str = ""
    sources: List[ProvenanceRecord] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "generated_at": self.generated_at,
            "sources": [s.to_dict() for s in self.sources],
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, sort_keys=True)


def make_import_manifest(sources: List[ProvenanceRecord]) -> ImportManifest:
    return ImportManifest(
        schema_version=SCHEMA_VERSION,
        generated_at=_utcnow(),
        sources=sources,
    )


# ---------------------------------------------------------------------------
# ImportRunRecord — post-import run record (Packet 2)
# ---------------------------------------------------------------------------

_RUN_RECORD_SCHEMA_VERSION = "import_run_v0"


@dataclass
class ImportRunRecord:
    schema_version: str = _RUN_RECORD_SCHEMA_VERSION
    run_id: str = ""
    source_kind: str = ""
    import_mode: str = ""
    resolved_source_path: str = ""
    snapshot_version: str = ""
    destination_tables: List[str] = field(default_factory=list)
    files_processed: int = 0
    files_skipped: int = 0
    rows_attempted: int = 0  # rows sent to CH insert(); may exceed CH count due to ReplacingMergeTree dedup
    rows_skipped: int = 0
    rows_rejected: int = 0
    import_completeness: str = ""  # dry-run / complete / partial / failed
    started_at: str = ""
    completed_at: str = ""
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    notes: str = ""
    provenance_hash: str = ""  # from provenance.py build_deterministic_import_manifest_id

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, sort_keys=True)


def make_import_run_record(
    result: Any,
    *,
    snapshot_version: str = "",
    notes: str = "",
) -> ImportRunRecord:
    """Build a deterministic post-import run record from an ImportResult.

    Args:
        result: An ImportResult instance (from importer.py).
        snapshot_version: Optional version label (e.g. "2026-03").
        notes: Optional free-form notes.

    Returns:
        ImportRunRecord with all fields populated and a provenance_hash.
    """
    from packages.polymarket.historical_import.provenance import (
        build_deterministic_import_manifest_id,
    )

    provenance_payload: Dict[str, Any] = {
        "source_kind": result.source_kind,
        "source_path": result.resolved_source_path,
        "dataset_version_or_snapshot": snapshot_version or result.source_kind,
        "import_mode": result.import_mode,
        "destination_reference": result.destination_tables,
        "source_state": (
            "complete"
            if result.import_completeness in ("complete", "dry-run")
            else "partial"
        ),
    }
    try:
        provenance_hash = build_deterministic_import_manifest_id(provenance_payload)
    except Exception:
        provenance_hash = ""

    return ImportRunRecord(
        run_id=result.run_id,
        source_kind=result.source_kind,
        import_mode=result.import_mode,
        resolved_source_path=result.resolved_source_path,
        snapshot_version=snapshot_version,
        destination_tables=list(result.destination_tables),
        files_processed=result.files_processed,
        files_skipped=result.files_skipped,
        rows_attempted=result.rows_attempted,
        rows_skipped=result.rows_skipped,
        rows_rejected=result.rows_rejected,
        import_completeness=result.import_completeness,
        started_at=result.started_at,
        completed_at=result.completed_at,
        errors=list(result.errors),
        warnings=list(result.warnings),
        notes=notes or result.notes,
        provenance_hash=provenance_hash,
    )
