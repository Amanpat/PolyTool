"""Validate a hypothesis JSON document against the packaged schema resource.

Uses ``jsonschema`` for structural validation against the package-local
``hypothesis_schema_v1.json`` resource. The docs/specs copy is a documentation
mirror only. Recommended-field warnings are layered on top as an advisory-only
check.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from functools import lru_cache
from importlib import resources
from typing import Any

import jsonschema


@dataclass
class ValidationResult:
    valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


_SCHEMA_PACKAGE = "packages.polymarket.hypotheses"
_SCHEMA_RESOURCE = "hypothesis_schema_v1.json"


@lru_cache(maxsize=1)
def _load_schema() -> dict[str, Any]:
    try:
        schema_text = (
            resources.files(_SCHEMA_PACKAGE)
            .joinpath(_SCHEMA_RESOURCE)
            .read_text(encoding="utf-8")
        )
    except FileNotFoundError as exc:
        raise RuntimeError(
            "Packaged hypothesis schema resource is missing: "
            f"{_SCHEMA_PACKAGE}/{_SCHEMA_RESOURCE}"
        ) from exc
    return json.loads(schema_text)


@lru_cache(maxsize=1)
def _load_hypothesis_entry_schema() -> dict[str, Any]:
    schema = _load_schema()
    return {
        "$schema": schema.get("$schema"),
        "$defs": schema.get("$defs", {}),
        **schema["$defs"]["hypothesis"],
    }


# Requires T separator, full HH:MM:SS, and timezone (Z or +/-HH:MM).
_RFC3339_DT_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})$"
)

_REQUIRED_FIELD_RE = re.compile(r"^'([^']+)' is a required property$")

# Fields that are recommended (not required) - absent ones produce warnings.
_RECOMMENDED_TOP_LEVEL = {
    "limitations": "document what the evidence does not show",
    "missing_data_for_backtest": "needed for backtest_ready assessment",
}


def _format_path(path) -> str:
    """Format a jsonschema error path like ``hypotheses[0].evidence[1].text``."""
    result = ""
    for part in path:
        if isinstance(part, int):
            result += f"[{part}]"
        elif result:
            result += f".{part}"
        else:
            result = str(part)
    return result


def _join_error_path(path_prefix: str | None, path_str: str) -> str:
    if not path_prefix:
        return path_str
    if not path_str:
        return path_prefix
    if path_str.startswith("["):
        return f"{path_prefix}{path_str}"
    return f"{path_prefix}.{path_str}"


def _format_jsonschema_error(
    error: jsonschema.ValidationError,
    *,
    path_prefix: str | None = None,
) -> str:
    """Turn a jsonschema ValidationError into a human-readable string."""
    path_str = _format_path(error.absolute_path)

    if error.validator == "required":
        match = _REQUIRED_FIELD_RE.match(error.message)
        if match:
            missing = match.group(1)
            full = f"{path_str}.{missing}" if path_str else missing
            full = _join_error_path(path_prefix, full)
            return f"Missing required field: '{full}'"

    full_path = _join_error_path(path_prefix, path_str)
    if full_path:
        return f"'{full_path}': {error.message}"
    return error.message


def _is_rfc3339_datetime(value: str) -> bool:
    """Return True iff *value* is a valid RFC 3339 date-time."""
    if not _RFC3339_DT_RE.match(value):
        return False
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        datetime.fromisoformat(normalized)
        return True
    except ValueError:
        return False


def validate_hypothesis_json(data: Any) -> ValidationResult:
    """Validate *data* against hypothesis_schema_v1."""
    errors: list[str] = []
    warnings: list[str] = []

    if not isinstance(data, dict):
        return ValidationResult(
            valid=False,
            errors=["Root document must be a JSON object"],
        )

    validator = jsonschema.Draft202012Validator(_load_schema())
    for error in sorted(
        validator.iter_errors(data), key=lambda item: list(item.absolute_path)
    ):
        errors.append(_format_jsonschema_error(error))

    meta = data.get("metadata")
    if isinstance(meta, dict):
        created = meta.get("created_at_utc")
        if isinstance(created, str) and not _is_rfc3339_datetime(created):
            errors.append(
                "'metadata.created_at_utc' must be a valid RFC 3339 date-time "
                "(e.g., '2026-03-11T00:00:00Z')"
            )

    for field_name, hint in _RECOMMENDED_TOP_LEVEL.items():
        if field_name not in data:
            warnings.append(
                f"Recommended field '{field_name}' is absent - {hint}"
            )

    return ValidationResult(valid=len(errors) == 0, errors=errors, warnings=warnings)


def validate_hypothesis_entry(
    data: Any,
    *,
    path_prefix: str | None = None,
) -> ValidationResult:
    """Validate one hypothesis object against the packaged hypothesis schema."""
    errors: list[str] = []

    validator = jsonschema.Draft202012Validator(_load_hypothesis_entry_schema())
    for error in sorted(
        validator.iter_errors(data), key=lambda item: list(item.absolute_path)
    ):
        errors.append(_format_jsonschema_error(error, path_prefix=path_prefix))

    return ValidationResult(valid=len(errors) == 0, errors=errors, warnings=[])
