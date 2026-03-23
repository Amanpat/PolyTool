"""Deterministic diff helpers for saved hypothesis JSON artifacts."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any, Callable


DIFF_SCHEMA_VERSION = "hypothesis_diff_v0"

_METADATA_IDENTITY_FIELDS = (
    "dossier_export_id",
    "proxy_wallet",
    "run_id",
    "user_slug",
)
_METADATA_CONTEXT_FIELDS = (
    "created_at_utc",
    "model",
    "window_days",
)
_TOP_LEVEL_LIST_FIELDS = (
    "limitations",
    "missing_data_for_backtest",
    "next_features_needed",
    "risks",
    "execution_recommendations",
)
_TOP_LEVEL_HANDLED_FIELDS = frozenset(
    {
        "schema_version",
        "metadata",
        "executive_summary",
        "hypotheses",
        *_TOP_LEVEL_LIST_FIELDS,
    }
)
_HYPOTHESIS_CORE_FIELDS = (
    "id",
    "claim",
    "confidence",
    "falsification",
)
_HYPOTHESIS_OPTIONAL_FIELDS = (
    "next_feature_needed",
    "execution_recommendation",
)
_HYPOTHESIS_HANDLED_FIELDS = frozenset(
    {
        *_HYPOTHESIS_CORE_FIELDS,
        *_HYPOTHESIS_OPTIONAL_FIELDS,
        "evidence",
        "tags",
    }
)


def load_hypothesis_artifact(path: Path) -> dict[str, Any]:
    """Load a hypothesis JSON artifact from disk."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Hypothesis artifact root must be a JSON object: {path}")
    return payload


def diff_hypothesis_documents(
    old_doc: Any,
    new_doc: Any,
    *,
    old_path: str | None = None,
    new_path: str | None = None,
) -> dict[str, Any]:
    """Compare two hypothesis JSON payloads and return a deterministic diff."""
    if not isinstance(old_doc, dict):
        raise ValueError("Old hypothesis document root must be a JSON object")
    if not isinstance(new_doc, dict):
        raise ValueError("New hypothesis document root must be a JSON object")

    field_paths = {
        "added": set(),
        "removed": set(),
        "changed": set(),
    }

    document = {
        "hypothesis_schema_version": _value_row_for_field(
            old_doc,
            new_doc,
            "schema_version",
            base_path="",
            field_paths=field_paths,
            always=True,
        ),
    }

    old_metadata = _as_object(old_doc.get("metadata"))
    new_metadata = _as_object(new_doc.get("metadata"))
    metadata = {
        "identity_fields": _compare_named_fields(
            old_metadata,
            new_metadata,
            _METADATA_IDENTITY_FIELDS,
            base_path="metadata",
            field_paths=field_paths,
            always=True,
        ),
        "context_fields": _compare_named_fields(
            old_metadata,
            new_metadata,
            _METADATA_CONTEXT_FIELDS,
            base_path="metadata",
            field_paths=field_paths,
            always=True,
        ),
        "other_fields": _group_rows_by_status(
            _compare_unhandled_fields(
                old_metadata,
                new_metadata,
                exclude=set(_METADATA_IDENTITY_FIELDS) | set(_METADATA_CONTEXT_FIELDS),
                base_path="metadata",
                field_paths=field_paths,
            )
        ),
    }

    old_exec = _as_object(old_doc.get("executive_summary"))
    new_exec = _as_object(new_doc.get("executive_summary"))
    executive_summary = {
        "overall_assessment": _value_row_for_field(
            old_exec,
            new_exec,
            "overall_assessment",
            base_path="executive_summary",
            field_paths=field_paths,
            always=True,
        ),
        "bullets": _diff_named_collection(
            old_exec,
            new_exec,
            "bullets",
            base_path="executive_summary",
            field_paths=field_paths,
        ),
    }

    hypotheses = _diff_hypotheses(
        old_doc.get("hypotheses"),
        new_doc.get("hypotheses"),
        old_present="hypotheses" in old_doc,
        new_present="hypotheses" in new_doc,
        field_paths=field_paths,
    )

    top_level_lists = {
        field_name: _diff_named_collection(
            old_doc,
            new_doc,
            field_name,
            base_path="",
            field_paths=field_paths,
        )
        for field_name in _TOP_LEVEL_LIST_FIELDS
    }

    other_top_level_fields = _group_rows_by_status(
        _compare_unhandled_fields(
            old_doc,
            new_doc,
            exclude=_TOP_LEVEL_HANDLED_FIELDS,
            base_path="",
            field_paths=field_paths,
        )
    )

    field_changes = {
        name: sorted(paths)
        for name, paths in field_paths.items()
    }
    has_changes = any(field_changes[name] for name in ("added", "removed", "changed"))

    return {
        "schema_version": DIFF_SCHEMA_VERSION,
        "document": document,
        "executive_summary": executive_summary,
        "execution_recommendations": top_level_lists["execution_recommendations"],
        "field_changes": field_changes,
        "hypotheses": hypotheses,
        "limitations": top_level_lists["limitations"],
        "metadata": metadata,
        "missing_data_for_backtest": top_level_lists["missing_data_for_backtest"],
        "new": {
            "path": new_path,
        },
        "next_features_needed": top_level_lists["next_features_needed"],
        "old": {
            "path": old_path,
        },
        "other_top_level_fields": other_top_level_fields,
        "risks": top_level_lists["risks"],
        "summary": {
            "confidence_changes": len(hypotheses["confidence_changes"]),
            "evidence_changes": len(hypotheses["evidence_changes"]),
            "field_change_counts": {
                "added": len(field_changes["added"]),
                "changed": len(field_changes["changed"]),
                "removed": len(field_changes["removed"]),
            },
            "has_changes": has_changes,
            "hypotheses": hypotheses["summary"],
        },
    }


def _as_object(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _path_for(base_path: str, field_name: str) -> str:
    if not base_path:
        return field_name
    return f"{base_path}.{field_name}"


def _normalize_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            str(key): _normalize_value(inner)
            for key, inner in sorted(value.items(), key=lambda item: str(item[0]))
        }
    if isinstance(value, list):
        return [_normalize_value(item) for item in value]
    return value


def _canonical_signature(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, separators=(",", ":"), sort_keys=True)


def _normalize_citation(value: Any) -> Any:
    if not isinstance(value, dict):
        return _normalize_value(value)

    normalized: dict[str, Any] = {}
    for key in sorted(value):
        item = value[key]
        if key == "trade_uids" and isinstance(item, list):
            normalized[key] = sorted(
                (_normalize_value(entry) for entry in item),
                key=_canonical_signature,
            )
        else:
            normalized[key] = _normalize_value(item)
    return normalized


def _normalize_hypothesis_entry(value: Any) -> Any:
    if not isinstance(value, dict):
        return _normalize_value(value)

    normalized: dict[str, Any] = {}
    for key in sorted(value):
        item = value[key]
        if key == "evidence" and isinstance(item, list):
            normalized[key] = sorted(
                (_normalize_citation(entry) for entry in item),
                key=_canonical_signature,
            )
        elif key == "tags" and isinstance(item, list):
            normalized[key] = sorted(
                (_normalize_value(entry) for entry in item),
                key=_canonical_signature,
            )
        else:
            normalized[key] = _normalize_value(item)
    return normalized


def _status_for(
    *,
    old_present: bool,
    new_present: bool,
    old_value: Any,
    new_value: Any,
) -> str:
    if old_present and not new_present:
        return "removed"
    if new_present and not old_present:
        return "added"
    if old_value != new_value:
        return "changed"
    return "unchanged"


def _register_path(status: str, path: str, field_paths: dict[str, set[str]]) -> None:
    if status in ("added", "removed", "changed"):
        field_paths[status].add(path)


def _value_row(
    *,
    old_present: bool,
    new_present: bool,
    old_value: Any,
    new_value: Any,
    path: str,
    field_paths: dict[str, set[str]],
) -> dict[str, Any]:
    status = _status_for(
        old_present=old_present,
        new_present=new_present,
        old_value=old_value,
        new_value=new_value,
    )
    _register_path(status, path, field_paths)
    return {
        "changed": status != "unchanged",
        "new": new_value if new_present else None,
        "old": old_value if old_present else None,
        "status": status,
    }


def _value_row_for_field(
    old_obj: dict[str, Any],
    new_obj: dict[str, Any],
    field_name: str,
    *,
    base_path: str,
    field_paths: dict[str, set[str]],
    always: bool = False,
) -> dict[str, Any] | None:
    old_present = field_name in old_obj
    new_present = field_name in new_obj
    if not always and not old_present and not new_present:
        return None
    return _value_row(
        old_present=old_present,
        new_present=new_present,
        old_value=old_obj.get(field_name),
        new_value=new_obj.get(field_name),
        path=_path_for(base_path, field_name),
        field_paths=field_paths,
    )


def _compare_named_fields(
    old_obj: dict[str, Any],
    new_obj: dict[str, Any],
    field_names: tuple[str, ...],
    *,
    base_path: str,
    field_paths: dict[str, set[str]],
    always: bool = False,
) -> dict[str, Any]:
    rows: dict[str, Any] = {}
    for field_name in field_names:
        row = _value_row_for_field(
            old_obj,
            new_obj,
            field_name,
            base_path=base_path,
            field_paths=field_paths,
            always=always,
        )
        if row is not None:
            rows[field_name] = row
    return rows


def _compare_unhandled_fields(
    old_obj: dict[str, Any],
    new_obj: dict[str, Any],
    *,
    exclude: set[str] | frozenset[str],
    base_path: str,
    field_paths: dict[str, set[str]],
) -> dict[str, dict[str, Any]]:
    keys = sorted((set(old_obj) | set(new_obj)) - set(exclude))
    rows: dict[str, dict[str, Any]] = {}
    for key in keys:
        row = _value_row_for_field(
            old_obj,
            new_obj,
            key,
            base_path=base_path,
            field_paths=field_paths,
        )
        if row is not None:
            rows[key] = row
    return rows


def _group_rows_by_status(rows: dict[str, dict[str, Any]]) -> dict[str, dict[str, dict[str, Any]]]:
    grouped = {
        "added": {},
        "removed": {},
        "changed": {},
    }
    for key, row in rows.items():
        status = row.get("status")
        if status in grouped:
            grouped[status][key] = row
    return grouped


def _membership_diff(
    old_values: list[Any],
    new_values: list[Any],
    *,
    normalize_item: Callable[[Any], Any],
) -> dict[str, Any]:
    old_rows = [(normalize_item(value), normalize_item(value)) for value in old_values]
    new_rows = [(normalize_item(value), normalize_item(value)) for value in new_values]
    old_counts = Counter(_canonical_signature(value) for value, _ in old_rows)
    new_counts = Counter(_canonical_signature(value) for value, _ in new_rows)

    old_lookup = {
        _canonical_signature(signature_source): normalized
        for signature_source, normalized in old_rows
    }
    new_lookup = {
        _canonical_signature(signature_source): normalized
        for signature_source, normalized in new_rows
    }

    added: list[Any] = []
    removed: list[Any] = []
    unchanged: list[Any] = []
    for signature in sorted(set(old_counts) | set(new_counts)):
        overlap = min(old_counts[signature], new_counts[signature])
        if overlap:
            unchanged.extend([new_lookup.get(signature, old_lookup[signature])] * overlap)
        if new_counts[signature] > old_counts[signature]:
            added.extend(
                [new_lookup[signature]] * (new_counts[signature] - old_counts[signature])
            )
        if old_counts[signature] > new_counts[signature]:
            removed.extend(
                [old_lookup[signature]] * (old_counts[signature] - new_counts[signature])
            )

    return {
        "added": added,
        "new_count": len(new_values),
        "old_count": len(old_values),
        "removed": removed,
        "unchanged": unchanged,
    }


def _collection_type_name(value: Any, *, present: bool) -> str | None:
    if not present:
        return None
    if isinstance(value, list):
        return "list"
    return type(value).__name__


def _value_descriptor(value: Any, *, present: bool) -> dict[str, Any] | None:
    if not present:
        return None
    return {
        "type": _collection_type_name(value, present=present),
        "value": _normalize_value(value),
    }


def _type_mismatch_collection_row(
    *,
    old_present: bool,
    new_present: bool,
    old_raw: Any,
    new_raw: Any,
    path: str,
    field_paths: dict[str, set[str]],
) -> dict[str, Any]:
    status = _status_for(
        old_present=old_present,
        new_present=new_present,
        old_value=_normalize_value(old_raw),
        new_value=_normalize_value(new_raw),
    )
    _register_path(status, path, field_paths)
    return {
        "added": [],
        "new": _normalize_value(new_raw) if new_present else None,
        "new_count": len(new_raw) if isinstance(new_raw, list) else None,
        "old": _normalize_value(old_raw) if old_present else None,
        "old_count": len(old_raw) if isinstance(old_raw, list) else None,
        "removed": [],
        "status": status,
        "type_mismatch": {
            "new_type": _collection_type_name(new_raw, present=new_present),
            "old_type": _collection_type_name(old_raw, present=old_present),
        },
        "unchanged": [],
    }


def _diff_named_collection(
    old_obj: dict[str, Any],
    new_obj: dict[str, Any],
    field_name: str,
    *,
    base_path: str,
    field_paths: dict[str, set[str]],
    normalize_item: Callable[[Any], Any] = _normalize_value,
) -> dict[str, Any]:
    old_present = field_name in old_obj
    new_present = field_name in new_obj
    old_raw = old_obj.get(field_name)
    new_raw = new_obj.get(field_name)
    if (old_present and not isinstance(old_raw, list)) or (
        new_present and not isinstance(new_raw, list)
    ):
        return _type_mismatch_collection_row(
            old_present=old_present,
            new_present=new_present,
            old_raw=old_raw,
            new_raw=new_raw,
            path=_path_for(base_path, field_name),
            field_paths=field_paths,
        )

    old_values = _as_list(old_raw)
    new_values = _as_list(new_raw)
    diff = _membership_diff(
        old_values,
        new_values,
        normalize_item=normalize_item,
    )
    diff["status"] = _status_for(
        old_present=old_present,
        new_present=new_present,
        old_value=diff["removed"],
        new_value=diff["added"],
    )
    _register_path(diff["status"], _path_for(base_path, field_name), field_paths)
    return diff

def _build_hypothesis_records(values: Any, *, side: str) -> list[dict[str, Any]]:
    entries = _as_list(values)
    records: list[dict[str, Any]] = []
    for idx, entry in enumerate(entries):
        raw_entry = entry if isinstance(entry, dict) else None
        entry_id = raw_entry.get("id") if raw_entry is not None else None
        claim = raw_entry.get("claim") if raw_entry is not None else None
        normalized_entry = _normalize_hypothesis_entry(entry)
        records.append(
            {
                "claim": claim if isinstance(claim, str) and claim else None,
                "entry": normalized_entry,
                "entry_is_object": raw_entry is not None,
                "entry_type": type(entry).__name__,
                "id": entry_id if isinstance(entry_id, str) and entry_id else None,
                "index": idx,
                "signature": _canonical_signature(normalized_entry),
                "token": f"{side}:{idx}",
            }
        )
    return records


def _record_sort_key(record: dict[str, Any]) -> tuple[Any, ...]:
    return (
        record["signature"],
        record["claim"] or "",
        record["id"] or "",
        record["index"],
        record["token"],
    )


def _group_records_by_field(
    records: list[dict[str, Any]],
    field_name: str,
) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        value = record.get(field_name)
        if not isinstance(value, str) or not value:
            continue
        grouped.setdefault(value, []).append(record)
    return grouped


def _record_similarity(old_record: dict[str, Any], new_record: dict[str, Any]) -> int:
    score = 0
    if old_record["id"] and new_record["id"] and old_record["id"] == new_record["id"]:
        score += 256
    if (
        old_record["claim"]
        and new_record["claim"]
        and old_record["claim"] == new_record["claim"]
    ):
        score += 128

    old_entry = old_record["entry"] if old_record["entry_is_object"] else {}
    new_entry = new_record["entry"] if new_record["entry_is_object"] else {}

    weighted_fields = (
        ("falsification", 64),
        ("confidence", 32),
        ("next_feature_needed", 16),
        ("execution_recommendation", 16),
    )
    for field_name, weight in weighted_fields:
        if (
            field_name in old_entry
            and field_name in new_entry
            and old_entry.get(field_name) == new_entry.get(field_name)
        ):
            score += weight

    if "tags" in old_entry and "tags" in new_entry and old_entry["tags"] == new_entry["tags"]:
        score += 8
    if (
        "evidence" in old_entry
        and "evidence" in new_entry
        and old_entry["evidence"] == new_entry["evidence"]
    ):
        score += 8

    shared_extra_keys = sorted((set(old_entry) & set(new_entry)) - _HYPOTHESIS_HANDLED_FIELDS)
    for key in shared_extra_keys:
        if old_entry.get(key) == new_entry.get(key):
            score += 4

    return score


def _hypothesis_structure_issue(
    key: str,
    old_record: dict[str, Any] | None,
    new_record: dict[str, Any] | None,
) -> dict[str, Any] | None:
    old_is_malformed = old_record is not None and not old_record["entry_is_object"]
    new_is_malformed = new_record is not None and not new_record["entry_is_object"]
    if not old_is_malformed and not new_is_malformed:
        return None
    return {
        "key": key,
        "new": _value_descriptor(
            new_record["entry"] if new_record is not None else None,
            present=new_is_malformed,
        ),
        "old": _value_descriptor(
            old_record["entry"] if old_record is not None else None,
            present=old_is_malformed,
        ),
        "path": f"hypotheses[{key}]",
        "status": _status_for(
            old_present=old_is_malformed,
            new_present=new_is_malformed,
            old_value=old_record["entry"] if old_is_malformed else None,
            new_value=new_record["entry"] if new_is_malformed else None,
        ),
    }


def _pair_hypothesis_records(
    old_records: list[dict[str, Any]],
    new_records: list[dict[str, Any]],
    *,
    exhaust_bucket: bool,
) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    unmatched_old = {record["token"]: record for record in old_records}
    unmatched_new = {record["token"]: record for record in new_records}
    pairs: list[tuple[dict[str, Any], dict[str, Any]]] = []

    old_by_signature: dict[str, list[dict[str, Any]]] = {}
    new_by_signature: dict[str, list[dict[str, Any]]] = {}
    for record in old_records:
        old_by_signature.setdefault(record["signature"], []).append(record)
    for record in new_records:
        new_by_signature.setdefault(record["signature"], []).append(record)

    for signature in sorted(set(old_by_signature) & set(new_by_signature)):
        old_group = sorted(old_by_signature[signature], key=_record_sort_key)
        new_group = sorted(new_by_signature[signature], key=_record_sort_key)
        for old_record, new_record in zip(old_group, new_group):
            if (
                old_record["token"] not in unmatched_old
                or new_record["token"] not in unmatched_new
            ):
                continue
            unmatched_old.pop(old_record["token"], None)
            unmatched_new.pop(new_record["token"], None)
            pairs.append((old_record, new_record))

    candidates: list[tuple[int, dict[str, Any], dict[str, Any]]] = []
    foreach_old = sorted(unmatched_old.values(), key=_record_sort_key)
    foreach_new = sorted(unmatched_new.values(), key=_record_sort_key)
    for old_record in foreach_old:
        for new_record in foreach_new:
            score = _record_similarity(old_record, new_record)
            if score > 0:
                candidates.append((score, old_record, new_record))

    candidates.sort(
        key=lambda item: (
            -item[0],
            _record_sort_key(item[1]),
            _record_sort_key(item[2]),
        )
    )
    for _, old_record, new_record in candidates:
        if old_record["token"] not in unmatched_old or new_record["token"] not in unmatched_new:
            continue
        unmatched_old.pop(old_record["token"], None)
        unmatched_new.pop(new_record["token"], None)
        pairs.append((old_record, new_record))

    if exhaust_bucket:
        old_remaining = sorted(unmatched_old.values(), key=_record_sort_key)
        new_remaining = sorted(unmatched_new.values(), key=_record_sort_key)
        for old_record, new_record in zip(old_remaining, new_remaining):
            if (
                old_record["token"] not in unmatched_old
                or new_record["token"] not in unmatched_new
            ):
                continue
            unmatched_old.pop(old_record["token"], None)
            unmatched_new.pop(new_record["token"], None)
            pairs.append((old_record, new_record))

    return pairs


def _fallback_identity(record: dict[str, Any]) -> tuple[str, str | None]:
    if record["id"]:
        return "id", record["id"]
    if record["claim"]:
        return "claim", record["claim"]
    return "anonymous", None


def _match_hypothesis_records(
    old_values: Any,
    new_values: Any,
) -> list[dict[str, Any]]:
    old_records = _build_hypothesis_records(old_values, side="old")
    new_records = _build_hypothesis_records(new_values, side="new")
    unmatched_old = {record["token"]: record for record in old_records}
    unmatched_new = {record["token"]: record for record in new_records}
    matched_items: list[dict[str, Any]] = []

    for field_name, identity_source in (("id", "id"), ("claim", "claim")):
        old_groups = _group_records_by_field(list(unmatched_old.values()), field_name)
        new_groups = _group_records_by_field(list(unmatched_new.values()), field_name)
        for identity_value in sorted(set(old_groups) & set(new_groups)):
            pairs = _pair_hypothesis_records(
                old_groups[identity_value],
                new_groups[identity_value],
                exhaust_bucket=True,
            )
            for old_record, new_record in pairs:
                if (
                    old_record["token"] not in unmatched_old
                    or new_record["token"] not in unmatched_new
                ):
                    continue
                unmatched_old.pop(old_record["token"], None)
                unmatched_new.pop(new_record["token"], None)
                matched_items.append(
                    {
                        "identity_source": identity_source,
                        "identity_value": identity_value,
                        "new": new_record,
                        "old": old_record,
                    }
                )

    anonymous_pairs = _pair_hypothesis_records(
        list(unmatched_old.values()),
        list(unmatched_new.values()),
        exhaust_bucket=False,
    )
    for old_record, new_record in anonymous_pairs:
        if old_record["token"] not in unmatched_old or new_record["token"] not in unmatched_new:
            continue
        unmatched_old.pop(old_record["token"], None)
        unmatched_new.pop(new_record["token"], None)
        matched_items.append(
            {
                "identity_source": "anonymous",
                "identity_value": None,
                "new": new_record,
                "old": old_record,
            }
        )

    for old_record in unmatched_old.values():
        identity_source, identity_value = _fallback_identity(old_record)
        matched_items.append(
            {
                "identity_source": identity_source,
                "identity_value": identity_value,
                "new": None,
                "old": old_record,
            }
        )
    for new_record in unmatched_new.values():
        identity_source, identity_value = _fallback_identity(new_record)
        matched_items.append(
            {
                "identity_source": identity_source,
                "identity_value": identity_value,
                "new": new_record,
                "old": None,
            }
        )

    grouped_items: dict[str, list[dict[str, Any]]] = {}
    for item in matched_items:
        if item["identity_source"] == "id":
            base_key = f"id:{item['identity_value']}"
        elif item["identity_source"] == "claim":
            base_key = f"claim:{item['identity_value']}"
        else:
            base_key = "anonymous"
        item["base_key"] = base_key
        grouped_items.setdefault(base_key, []).append(item)

    ordered_items: list[dict[str, Any]] = []
    for base_key in sorted(grouped_items):
        bucket = sorted(
            grouped_items[base_key],
            key=lambda item: (
                item["new"]["signature"] if item["new"] is not None else "",
                item["old"]["signature"] if item["old"] is not None else "",
                item["old"]["index"] if item["old"] is not None else -1,
                item["new"]["index"] if item["new"] is not None else -1,
            ),
        )
        use_suffix = base_key == "anonymous" or len(bucket) > 1
        for idx, item in enumerate(bucket, start=1):
            item["key"] = f"{base_key}#{idx}" if use_suffix else base_key
            ordered_items.append(item)

    ordered_items.sort(key=lambda item: item["key"])
    return ordered_items


def _diff_hypotheses(
    old_values: Any,
    new_values: Any,
    *,
    old_present: bool,
    new_present: bool,
    field_paths: dict[str, set[str]],
) -> dict[str, Any]:
    if (old_present and not isinstance(old_values, list)) or (
        new_present and not isinstance(new_values, list)
    ):
        diff = _type_mismatch_collection_row(
            old_present=old_present,
            new_present=new_present,
            old_raw=old_values,
            new_raw=new_values,
            path="hypotheses",
            field_paths=field_paths,
        )
        diff.update(
            {
                "changed": [],
                "confidence_changes": [],
                "evidence_changes": [],
                "structure_issues": [
                    {
                        "key": "hypotheses",
                        "new": _value_descriptor(new_values, present=new_present),
                        "old": _value_descriptor(old_values, present=old_present),
                        "path": "hypotheses",
                        "status": diff["status"],
                    }
                ],
                "summary": {
                    "added": 0,
                    "changed": 0,
                    "removed": 0,
                    "unchanged": 0,
                },
            }
        )
        return diff

    changed: list[dict[str, Any]] = []
    unchanged: list[str] = []
    confidence_changes: list[dict[str, Any]] = []
    evidence_changes: list[dict[str, Any]] = []
    added: list[dict[str, Any]] = []
    removed: list[dict[str, Any]] = []
    structure_issues: list[dict[str, Any]] = []

    for item in _match_hypothesis_records(old_values, new_values):
        key = item["key"]
        old_record = item["old"]
        new_record = item["new"]
        structure_issue = _hypothesis_structure_issue(key, old_record, new_record)
        if structure_issue is not None:
            structure_issues.append(structure_issue)
        if old_record is None and new_record is not None:
            added.append(
                {
                    "entry": new_record["entry"],
                    "identity_source": item["identity_source"],
                    "key": key,
                }
            )
            field_paths["added"].add(f"hypotheses[{key}]")
            continue
        if new_record is None and old_record is not None:
            removed.append(
                {
                    "entry": old_record["entry"],
                    "identity_source": item["identity_source"],
                    "key": key,
                }
            )
            field_paths["removed"].add(f"hypotheses[{key}]")
            continue

        old_entry = old_record["entry"] if old_record["entry_is_object"] else {}
        new_entry = new_record["entry"] if new_record["entry_is_object"] else {}
        if old_entry == new_entry:
            unchanged.append(key)
            continue

        base_path = f"hypotheses[{key}]"
        scalar_rows = {
            field_name: _value_row_for_field(
                old_entry,
                new_entry,
                field_name,
                base_path=base_path,
                field_paths=field_paths,
                always=field_name in _HYPOTHESIS_CORE_FIELDS,
            )
            for field_name in (*_HYPOTHESIS_CORE_FIELDS, *_HYPOTHESIS_OPTIONAL_FIELDS)
        }
        tags = _diff_named_collection(
            old_entry,
            new_entry,
            "tags",
            base_path=base_path,
            field_paths=field_paths,
        )
        evidence = _diff_named_collection(
            old_entry,
            new_entry,
            "evidence",
            base_path=base_path,
            field_paths=field_paths,
            normalize_item=_normalize_citation,
        )
        extra_fields = _group_rows_by_status(
            _compare_unhandled_fields(
                old_entry,
                new_entry,
                exclude=_HYPOTHESIS_HANDLED_FIELDS,
                base_path=base_path,
                field_paths=field_paths,
            )
        )

        changed_fields = sorted(
            [
                field_name
                for field_name, row in scalar_rows.items()
                if row is not None and row["status"] != "unchanged"
            ]
            + (["tags"] if tags["status"] != "unchanged" else [])
            + (["evidence"] if evidence["status"] != "unchanged" else [])
            + list(extra_fields["added"].keys())
            + list(extra_fields["removed"].keys())
            + list(extra_fields["changed"].keys())
        )

        row = {
            "changed_fields": changed_fields,
            "claim": scalar_rows["claim"],
            "confidence": scalar_rows["confidence"],
            "evidence": evidence,
            "execution_recommendation": scalar_rows["execution_recommendation"],
            "extra_fields": extra_fields,
            "falsification": scalar_rows["falsification"],
            "id": scalar_rows["id"],
            "identity_source": item["identity_source"],
            "key": key,
            "next_feature_needed": scalar_rows["next_feature_needed"],
            "tags": tags,
        }
        changed.append(row)

        confidence_row = row["confidence"]
        if confidence_row is not None and confidence_row["status"] == "changed":
            confidence_changes.append(
                {
                    "key": key,
                    "new": confidence_row["new"],
                    "old": confidence_row["old"],
                }
            )

        if evidence["status"] != "unchanged":
            evidence_changes.append(
                {
                    "added_count": len(evidence["added"]),
                    "key": key,
                    "new_count": evidence["new_count"],
                    "old_count": evidence["old_count"],
                    "removed_count": len(evidence["removed"]),
                }
            )

    return {
        "added": added,
        "changed": changed,
        "confidence_changes": confidence_changes,
        "evidence_changes": evidence_changes,
        "removed": removed,
        "structure_issues": structure_issues,
        "summary": {
            "added": len(added),
            "changed": len(changed),
            "removed": len(removed),
            "unchanged": len(unchanged),
        },
        "unchanged": unchanged,
    }
