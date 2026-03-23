"""Deterministic provenance helpers for historical import packets."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping


REQUIRED_PROVENANCE_FIELDS = (
    "source_kind",
    "source_path",
    "dataset_version_or_snapshot",
    "import_mode",
    "destination_reference",
)

VALID_IMPORT_MODES = frozenset(("dry-run", "sample", "full"))
VALID_SOURCE_STATES = frozenset(("complete", "partial", "missing"))

_FIELD_ALIASES = {
    "source_kind": ("source_kind",),
    "source_path": ("source_path", "local_path", "resolved_path"),
    "dataset_version_or_snapshot": (
        "dataset_version_or_snapshot",
        "snapshot_version",
    ),
    "import_mode": ("import_mode",),
    "destination_reference": (
        "destination_reference",
        "destination_table",
        "destination_tables",
        "destination_artifact",
        "destination_artifact_path",
    ),
}


@dataclass
class ProvenanceValidationResult:
    valid: bool
    import_ready: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    normalized: Dict[str, Any] = field(default_factory=dict)


def _first_present(provenance: Mapping[str, Any], keys: Iterable[str]) -> Any:
    for key in keys:
        if key in provenance:
            return provenance[key]
    return None


def _normalize_string(
    value: Any,
    *,
    field_name: str,
    errors: list[str],
    resolve_path: bool = False,
) -> str:
    if not isinstance(value, str):
        errors.append(f"Provenance field '{field_name}' must be a non-empty string.")
        return ""
    normalized = value.strip()
    if not normalized:
        errors.append(f"Provenance field '{field_name}' must be a non-empty string.")
        return ""
    if resolve_path:
        return str(Path(normalized).resolve())
    return normalized


def _normalize_destination_references(value: Any, errors: list[str]) -> list[str]:
    refs: list[str] = []
    if isinstance(value, str):
        refs = [value]
    elif isinstance(value, (list, tuple, set)):
        refs = list(value)
    else:
        errors.append(
            "Provenance field 'destination_reference' must be a non-empty string "
            "or a sequence of non-empty strings."
        )
        return []

    normalized = sorted({str(ref).strip() for ref in refs if str(ref).strip()})
    if not normalized:
        errors.append(
            "Provenance field 'destination_reference' must include at least one "
            "destination artifact or table reference."
        )
    return normalized


def _normalize_source_state(
    provenance: Mapping[str, Any],
    errors: list[str],
) -> str:
    raw_state = provenance.get("source_state")
    if raw_state is not None:
        if not isinstance(raw_state, str):
            errors.append("Provenance field 'source_state' must be a string.")
            return ""
        normalized = raw_state.strip().lower()
        if normalized not in VALID_SOURCE_STATES:
            errors.append(
                "Provenance field 'source_state' must be one of: "
                f"{', '.join(sorted(VALID_SOURCE_STATES))}."
            )
            return ""
        return normalized

    partial_flag = provenance.get("partial_source")
    missing_flag = provenance.get("source_missing", provenance.get("missing_source"))
    has_partial_flag = partial_flag is not None
    has_missing_flag = missing_flag is not None

    if not has_partial_flag and not has_missing_flag:
        errors.append(
            "Provenance must explicitly declare source completeness via "
            "'source_state' or boolean partial/missing flags."
        )
        return ""

    if has_partial_flag and not isinstance(partial_flag, bool):
        errors.append("Provenance field 'partial_source' must be a boolean when set.")
        return ""
    if has_missing_flag and not isinstance(missing_flag, bool):
        errors.append("Provenance field 'source_missing' must be a boolean when set.")
        return ""
    if partial_flag and missing_flag:
        errors.append(
            "Provenance cannot mark a source as both partial and missing."
        )
        return ""
    if missing_flag:
        return "missing"
    if partial_flag:
        return "partial"
    return "complete"


def validate_required_provenance_fields(
    provenance: Mapping[str, Any],
) -> ProvenanceValidationResult:
    errors: list[str] = []
    warnings: list[str] = []
    normalized: Dict[str, Any] = {}

    for canonical_name in REQUIRED_PROVENANCE_FIELDS:
        raw_value = _first_present(provenance, _FIELD_ALIASES[canonical_name])
        if raw_value is None:
            errors.append(
                f"Missing required provenance field '{canonical_name}'."
            )
            continue

        if canonical_name == "destination_reference":
            normalized["destination_references"] = _normalize_destination_references(
                raw_value,
                errors,
            )
            continue

        normalized[canonical_name] = _normalize_string(
            raw_value,
            field_name=canonical_name,
            errors=errors,
            resolve_path=(canonical_name == "source_path"),
        )

    source_state = _normalize_source_state(provenance, errors)
    if source_state:
        normalized["source_state"] = source_state

    import_mode = normalized.get("import_mode", "")
    if import_mode and import_mode not in VALID_IMPORT_MODES:
        errors.append(
            "Provenance field 'import_mode' must be one of: "
            f"{', '.join(sorted(VALID_IMPORT_MODES))}."
        )

    if not errors and source_state == "partial":
        warnings.append(
            "Source is explicitly marked partial; the main import packet should "
            "refuse a full import until provenance is complete."
        )
    if not errors and source_state == "missing":
        warnings.append(
            "Source is explicitly marked missing; the main import packet should "
            "refuse execution until the source is present."
        )

    valid = not errors
    import_ready = valid and source_state == "complete"
    return ProvenanceValidationResult(
        valid=valid,
        import_ready=import_ready,
        errors=errors,
        warnings=warnings,
        normalized=normalized if valid else {},
    )


def _canonical_provenance_payload(provenance: Mapping[str, Any]) -> Dict[str, Any]:
    validation = validate_required_provenance_fields(provenance)
    if not validation.valid:
        raise ValueError("; ".join(validation.errors))
    return validation.normalized


def build_deterministic_provenance_hash(provenance: Mapping[str, Any]) -> str:
    payload = _canonical_provenance_payload(provenance)
    raw = json.dumps(
        payload,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def build_deterministic_import_manifest_id(provenance: Mapping[str, Any]) -> str:
    return f"import_manifest_{build_deterministic_provenance_hash(provenance)}"
