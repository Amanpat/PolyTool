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
