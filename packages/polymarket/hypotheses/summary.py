from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

from packages.polymarket.hypotheses.validator import validate_hypothesis_entry


SUMMARY_SCHEMA_VERSION = "hypothesis_summary_v0"
_MAX_SUMMARY_BULLETS = 10
_HYPOTHESIS_ID_RE = re.compile(r"^H(?P<number>\d+)$")


def load_hypothesis_summary_artifact(path: Path) -> dict[str, Any]:
    """Load a saved hypothesis JSON artifact from disk."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Hypothesis artifact root must be a JSON object: {path}")
    return payload


def extract_hypothesis_summary(
    document: Any,
    *,
    hypothesis_path: str | None = None,
) -> dict[str, Any]:
    """Return a compact, deterministic summary payload for a hypothesis artifact."""
    if not isinstance(document, dict):
        raise ValueError("Hypothesis document root must be a JSON object")

    structure_issues: list[dict[str, Any]] = []

    metadata = _extract_metadata(document.get("metadata"))
    executive_summary = _extract_executive_summary(
        document.get("executive_summary"),
        structure_issues=structure_issues,
    )
    hypotheses = _build_hypothesis_entries(
        document.get("hypotheses"),
        structure_issues=structure_issues,
    )
    primary_hypothesis = hypotheses[0] if hypotheses else None

    limitations = _extract_text_entries(
        document.get("limitations"),
        "limitations",
        structure_issues=structure_issues,
    )
    missing_data = _extract_text_entries(
        document.get("missing_data_for_backtest"),
        "missing_data_for_backtest",
        structure_issues=structure_issues,
    )
    next_features = _extract_text_entries(
        document.get("next_features_needed"),
        "next_features_needed",
        structure_issues=structure_issues,
    )
    risks = _extract_text_entries(
        document.get("risks"),
        "risks",
        structure_issues=structure_issues,
    )
    execution_recommendations = _extract_text_entries(
        document.get("execution_recommendations"),
        "execution_recommendations",
        structure_issues=structure_issues,
    )

    summary_bullets: list[dict[str, Any]] = []

    identity_text, identity_fields = _build_identity_text(
        metadata=metadata,
        primary_hypothesis=primary_hypothesis,
        hypothesis_count=len(hypotheses),
    )
    _append_bullet(
        summary_bullets,
        key="identity",
        text=identity_text,
        source_fields=identity_fields,
    )

    overall_assessment = executive_summary["overall_assessment"]
    if overall_assessment is not None:
        _append_bullet(
            summary_bullets,
            key="overall_assessment",
            text=f"Overall assessment: {_sentence(overall_assessment)}",
            source_fields=["executive_summary.overall_assessment"],
        )

    if executive_summary["bullets"]:
        first_bullet = executive_summary["bullets"][0]
        _append_bullet(
            summary_bullets,
            key="executive_summary",
            text=f"Executive summary: {_sentence(first_bullet['text'])}",
            source_fields=[first_bullet["path"]],
        )

    if primary_hypothesis is not None and primary_hypothesis["claim"] is not None:
        _append_bullet(
            summary_bullets,
            key="core_edge_claim",
            text=f"Core edge claim: {_sentence(primary_hypothesis['claim'])}",
            hypothesis_key=primary_hypothesis["key"],
            source_fields=[f"hypotheses[{primary_hypothesis['key']}].claim"],
        )

    if primary_hypothesis is not None and primary_hypothesis["confidence"] is not None:
        _append_bullet(
            summary_bullets,
            key="confidence",
            text=f"Confidence: {_sentence(primary_hypothesis['confidence'])}",
            hypothesis_key=primary_hypothesis["key"],
            source_fields=[f"hypotheses[{primary_hypothesis['key']}].confidence"],
        )

    primary_evidence = (
        primary_hypothesis["primary_evidence"] if primary_hypothesis is not None else None
    )
    if primary_evidence is not None and primary_evidence["text"] is not None:
        evidence_path = f"hypotheses[{primary_hypothesis['key']}].{primary_evidence['path']}"
        _append_bullet(
            summary_bullets,
            key="primary_evidence",
            text=f"Primary evidence: {_sentence(primary_evidence['text'])}",
            hypothesis_key=primary_hypothesis["key"] if primary_hypothesis is not None else None,
            source_fields=[evidence_path],
        )

    risks_text, risks_fields = _build_risks_text(
        risks=risks,
        limitations=limitations,
        missing_data=missing_data,
    )
    _append_bullet(
        summary_bullets,
        key="risks_limitations",
        text=risks_text,
        source_fields=risks_fields,
    )

    next_step_text, next_step_fields = _build_next_step_text(
        primary_hypothesis=primary_hypothesis,
        execution_recommendations=execution_recommendations,
        next_features=next_features,
    )
    _append_bullet(
        summary_bullets,
        key="next_step",
        text=next_step_text,
        hypothesis_key=primary_hypothesis["key"] if primary_hypothesis is not None else None,
        source_fields=next_step_fields,
    )

    structured_fields_used = _dedupe_strings(
        field
        for bullet in summary_bullets
        for field in bullet["source_fields"]
    )

    return {
        "metadata": metadata,
        "overall_assessment": overall_assessment,
        "primary_hypothesis": _serialize_primary_hypothesis(primary_hypothesis),
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "source": {
            "hypothesis_path": hypothesis_path,
        },
        "structure_issues": structure_issues,
        "summary": {
            "available_sections": _available_sections(document),
            "bullet_count": len(summary_bullets),
            "hypothesis_count": len(hypotheses),
            "observation_count": len(_as_list(document.get("observations"))),
            "primary_hypothesis_key": (
                primary_hypothesis["key"] if primary_hypothesis is not None else None
            ),
            "structured_fields_used": structured_fields_used,
        },
        "summary_bullets": summary_bullets,
    }


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _nonempty_string(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def _sentence(value: str) -> str:
    stripped = value.strip()
    if stripped.endswith((".", "!", "?")):
        return stripped
    return f"{stripped}."


def _dedupe_strings(values: Any) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if not isinstance(value, str):
            continue
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def _append_bullet(
    summary_bullets: list[dict[str, Any]],
    *,
    key: str,
    text: str | None,
    source_fields: list[str] | None = None,
    hypothesis_key: str | None = None,
) -> None:
    if not text or len(summary_bullets) >= _MAX_SUMMARY_BULLETS:
        return

    bullet: dict[str, Any] = {
        "key": key,
        "source_fields": _dedupe_strings(source_fields or []),
        "text": text,
    }
    if hypothesis_key is not None:
        bullet["hypothesis_key"] = hypothesis_key
    summary_bullets.append(bullet)


def _normalize_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            str(key): _normalize_value(inner)
            for key, inner in sorted(value.items(), key=lambda item: str(item[0]))
        }
    if isinstance(value, list):
        return [_normalize_value(item) for item in value]
    return value


def _value_descriptor(value: Any) -> dict[str, Any]:
    return {
        "type": type(value).__name__,
        "value": _normalize_value(value),
    }


def _append_structure_issue(
    structure_issues: list[dict[str, Any]],
    *,
    code: str,
    message: str,
    path: str,
    value: Any,
    reasons: list[str] | None = None,
) -> None:
    issue = {
        "code": code,
        "message": message,
        "path": path,
        "value": _value_descriptor(value),
    }
    if reasons:
        issue["reasons"] = reasons
    structure_issues.append(issue)


def _extract_metadata(value: Any) -> dict[str, Any]:
    metadata = value if isinstance(value, dict) else {}
    return {
        "created_at_utc": _nonempty_string(metadata.get("created_at_utc")),
        "dossier_export_id": _nonempty_string(metadata.get("dossier_export_id")),
        "model": _nonempty_string(metadata.get("model")),
        "proxy_wallet": _nonempty_string(metadata.get("proxy_wallet")),
        "run_id": _nonempty_string(metadata.get("run_id")),
        "user_slug": _nonempty_string(metadata.get("user_slug")),
        "window_days": metadata.get("window_days")
        if isinstance(metadata.get("window_days"), int)
        else None,
    }


def _extract_executive_summary(
    value: Any,
    *,
    structure_issues: list[dict[str, Any]],
) -> dict[str, Any]:
    summary = value if isinstance(value, dict) else {}
    bullets = _extract_text_entries(
        summary.get("bullets"),
        "executive_summary.bullets",
        structure_issues=structure_issues,
    )
    return {
        "bullets": bullets,
        "overall_assessment": _nonempty_string(summary.get("overall_assessment")),
    }


def _extract_text_entries(
    value: Any,
    base_path: str,
    *,
    structure_issues: list[dict[str, Any]],
) -> list[dict[str, str]]:
    entries: list[dict[str, str]] = []
    if isinstance(value, list):
        iterable: list[tuple[str, Any]] = [
            (f"{base_path}[{index}]", item) for index, item in enumerate(value)
        ]
    elif isinstance(value, str):
        iterable = [(base_path, value)]
        _append_structure_issue(
            structure_issues,
            code="scalar_string_fallback",
            message="Expected a list of strings; using the raw string directly.",
            path=base_path,
            value=value,
        )
    elif value is None:
        iterable = []
    else:
        iterable = []
        _append_structure_issue(
            structure_issues,
            code="invalid_text_collection",
            message="Expected a list of strings; ignored malformed value.",
            path=base_path,
            value=value,
        )

    for path, item in iterable:
        text = _nonempty_string(item)
        if text is None:
            if item is not None and not isinstance(item, str):
                _append_structure_issue(
                    structure_issues,
                    code="invalid_text_entry",
                    message="Ignored non-string text entry.",
                    path=path,
                    value=item,
                )
            continue
        entries.append(
            {
                "path": path,
                "text": text,
            }
        )
    return entries


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


def _hypothesis_summary_eligibility_errors(
    entry: dict[str, Any],
    *,
    source_path: str,
) -> list[str]:
    result = validate_hypothesis_entry(entry, path_prefix=source_path)
    return result.errors


def _build_hypothesis_entries(
    value: Any,
    *,
    structure_issues: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    if value is not None and not isinstance(value, list):
        _append_structure_issue(
            structure_issues,
            code="invalid_hypotheses_collection",
            message="Expected hypotheses to be a list; ignored malformed value.",
            path="hypotheses",
            value=value,
        )
        return entries

    for index, raw_entry in enumerate(_as_list(value)):
        source_path = f"hypotheses[{index}]"
        if not isinstance(raw_entry, dict):
            _append_structure_issue(
                structure_issues,
                code="skipped_non_object_hypothesis",
                message=(
                    "Hypothesis entry is not an object; skipped from hypothesis_count "
                    "and primary_hypothesis."
                ),
                path=source_path,
                value=raw_entry,
            )
            continue

        evidence = _build_evidence_entries(
            raw_entry.get("evidence"),
            relative_base_path="evidence",
            issue_base_path=f"{source_path}.evidence",
            structure_issues=structure_issues,
        )
        eligibility_errors = _hypothesis_summary_eligibility_errors(
            raw_entry,
            source_path=source_path,
        )
        if eligibility_errors:
            _append_structure_issue(
                structure_issues,
                code="skipped_ineligible_hypothesis",
                message=(
                    "Hypothesis entry failed schema validation for summary "
                    "eligibility; skipped from hypothesis_count and "
                    "primary_hypothesis."
                ),
                path=source_path,
                value=raw_entry,
                reasons=eligibility_errors,
            )
            continue

        entries.append(
            {
                "claim": _nonempty_string(raw_entry.get("claim")),
                "confidence": _nonempty_string(raw_entry.get("confidence")),
                "evidence_count": len(evidence),
                "execution_recommendation": _nonempty_string(
                    raw_entry.get("execution_recommendation")
                ),
                "id": _nonempty_string(raw_entry.get("id")),
                "next_feature_needed": _nonempty_string(
                    raw_entry.get("next_feature_needed")
                ),
                "primary_evidence": _select_primary_evidence(evidence),
                "signature": _canonical_signature(_normalize_hypothesis_entry(raw_entry)),
            }
        )

    entries.sort(key=_hypothesis_sort_key)

    base_key_counts = Counter(_hypothesis_base_key(entry) for entry in entries)
    seen_counts: Counter[str] = Counter()
    for entry in entries:
        base_key = _hypothesis_base_key(entry)
        seen_counts[base_key] += 1
        if base_key == "anonymous" or base_key_counts[base_key] > 1:
            entry["key"] = f"{base_key}#{seen_counts[base_key]}"
        else:
            entry["key"] = base_key
    return entries


def _hypothesis_sort_key(entry: dict[str, Any]) -> tuple[Any, ...]:
    hypothesis_id = entry["id"]
    claim = entry["claim"] or ""
    signature = entry["signature"]
    match = _HYPOTHESIS_ID_RE.match(hypothesis_id or "")
    if match is not None:
        return (0, int(match.group("number")), hypothesis_id.lower(), claim.lower(), signature)
    if hypothesis_id is not None:
        return (1, hypothesis_id.lower(), claim.lower(), signature)
    if claim:
        return (2, claim.lower(), signature)
    return (3, signature)


def _hypothesis_base_key(entry: dict[str, Any]) -> str:
    if entry["id"] is not None:
        return f"id:{entry['id']}"
    if entry["claim"] is not None:
        return f"claim:{entry['claim']}"
    return "anonymous"


def _build_evidence_entries(
    value: Any,
    *,
    relative_base_path: str,
    issue_base_path: str,
    structure_issues: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    if isinstance(value, list):
        iterable: list[tuple[str, str, Any]] = [
            (
                f"{relative_base_path}[{index}]",
                f"{issue_base_path}[{index}]",
                raw_entry,
            )
            for index, raw_entry in enumerate(value)
        ]
    elif isinstance(value, str):
        iterable = [(relative_base_path, issue_base_path, value)]
        _append_structure_issue(
            structure_issues,
            code="scalar_string_evidence_fallback",
            message="Evidence should be a list; using the raw string as a single entry.",
            path=issue_base_path,
            value=value,
        )
    elif value is None:
        iterable = []
    else:
        iterable = []
        _append_structure_issue(
            structure_issues,
            code="invalid_evidence_collection",
            message="Evidence should be a list; ignored malformed value.",
            path=issue_base_path,
            value=value,
        )

    for relative_path, issue_path, raw_entry in iterable:
        if isinstance(raw_entry, dict):
            trade_uids = sorted(
                item
                for item in _as_list(raw_entry.get("trade_uids"))
                if isinstance(item, str) and item.strip()
            )
            metrics = (
                raw_entry.get("metrics")
                if isinstance(raw_entry.get("metrics"), dict)
                else {}
            )
            entries.append(
                {
                    "entry_is_object": True,
                    "file_path": _nonempty_string(raw_entry.get("file_path")),
                    "metrics": metrics,
                    "signature": _canonical_signature(_normalize_citation(raw_entry)),
                    "text": _nonempty_string(raw_entry.get("text")),
                    "trade_uid_count": len(trade_uids),
                    "trade_uids": trade_uids,
                }
            )
            continue

        if isinstance(raw_entry, str):
            _append_structure_issue(
                structure_issues,
                code="raw_string_evidence_fallback",
                message=(
                    "Evidence entry is a raw string; using it as text without "
                    "inventing object fields."
                ),
                path=issue_path,
                value=raw_entry,
            )
            text = _nonempty_string(raw_entry)
            if text is None:
                continue
            entries.append(
                {
                    "entry_is_object": False,
                    "file_path": None,
                    "metrics": {},
                    "signature": _canonical_signature(_normalize_value(raw_entry)),
                    "text": text,
                    "trade_uid_count": 0,
                    "trade_uids": [],
                }
            )
            continue

        _append_structure_issue(
            structure_issues,
            code="invalid_evidence_entry",
            message="Ignored evidence entry that is neither an object nor a string.",
            path=issue_path,
            value=raw_entry,
        )

    entries.sort(key=_evidence_sort_key)
    for index, entry in enumerate(entries):
        suffix = ".text" if entry["entry_is_object"] else ""
        entry["path"] = f"{relative_base_path}[{index}]{suffix}"
    return entries


def _select_primary_evidence(entries: list[dict[str, Any]]) -> dict[str, Any] | None:
    ordered_entries = sorted(entries, key=_evidence_sort_key)
    for entry in ordered_entries:
        if entry["text"] is not None:
            return entry
    return ordered_entries[0] if ordered_entries else None


def _evidence_sort_key(entry: dict[str, Any]) -> tuple[Any, ...]:
    return (
        0 if entry["text"] is not None else 1,
        0 if entry["entry_is_object"] else 1,
        entry["signature"],
    )


def _build_identity_text(
    *,
    metadata: dict[str, Any],
    primary_hypothesis: dict[str, Any] | None,
    hypothesis_count: int,
) -> tuple[str | None, list[str]]:
    parts: list[str] = []
    source_fields: list[str] = []

    if metadata["user_slug"] is not None:
        parts.append(f"user_slug={metadata['user_slug']}")
        source_fields.append("metadata.user_slug")
    if metadata["run_id"] is not None:
        parts.append(f"run_id={metadata['run_id']}")
        source_fields.append("metadata.run_id")
    if metadata["model"] is not None:
        parts.append(f"model={metadata['model']}")
        source_fields.append("metadata.model")
    if primary_hypothesis is not None:
        parts.append(f"primary_hypothesis={primary_hypothesis['key']}")
        if primary_hypothesis["id"] is not None:
            source_fields.append(f"hypotheses[{primary_hypothesis['key']}].id")
        elif primary_hypothesis["claim"] is not None:
            source_fields.append(f"hypotheses[{primary_hypothesis['key']}].claim")

    parts.append(f"hypothesis_count={hypothesis_count}")
    return f"Identity: {'; '.join(parts)}.", source_fields


def _build_risks_text(
    *,
    risks: list[dict[str, str]],
    limitations: list[dict[str, str]],
    missing_data: list[dict[str, str]],
) -> tuple[str | None, list[str]]:
    parts: list[str] = []
    source_fields: list[str] = []

    if risks:
        parts.append(_sentence(risks[0]["text"]))
        source_fields.append(risks[0]["path"])
    if limitations:
        parts.append(f"Limitation: {_sentence(limitations[0]['text'])}")
        source_fields.append(limitations[0]["path"])

    if missing_data:
        parts.append(f"Missing data: {_sentence(missing_data[0]['text'])}")
        source_fields.append(missing_data[0]["path"])

    if not parts:
        return None, []
    return f"Risks / limitations: {' '.join(parts)}", source_fields


def _build_next_step_text(
    *,
    primary_hypothesis: dict[str, Any] | None,
    execution_recommendations: list[dict[str, str]],
    next_features: list[dict[str, str]],
) -> tuple[str | None, list[str]]:
    parts: list[str] = []
    source_fields: list[str] = []

    if primary_hypothesis is not None and primary_hypothesis["execution_recommendation"] is not None:
        parts.append(
            f"Execution recommendation: {_sentence(primary_hypothesis['execution_recommendation'])}"
        )
        source_fields.append(
            f"hypotheses[{primary_hypothesis['key']}].execution_recommendation"
        )
    elif execution_recommendations:
        parts.append(
            f"Execution recommendation: {_sentence(execution_recommendations[0]['text'])}"
        )
        source_fields.append(execution_recommendations[0]["path"])

    if primary_hypothesis is not None and primary_hypothesis["next_feature_needed"] is not None:
        parts.append(f"Next feature: {_sentence(primary_hypothesis['next_feature_needed'])}")
        source_fields.append(f"hypotheses[{primary_hypothesis['key']}].next_feature_needed")
    elif next_features:
        parts.append(f"Next feature: {_sentence(next_features[0]['text'])}")
        source_fields.append(next_features[0]["path"])

    if not parts:
        return None, []
    return f"Next step: {' '.join(parts)}", source_fields


def _serialize_primary_hypothesis(
    primary_hypothesis: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if primary_hypothesis is None:
        return None

    primary_evidence = primary_hypothesis["primary_evidence"]
    return {
        "claim": primary_hypothesis["claim"],
        "confidence": primary_hypothesis["confidence"],
        "evidence_count": primary_hypothesis["evidence_count"],
        "execution_recommendation": primary_hypothesis["execution_recommendation"],
        "id": primary_hypothesis["id"],
        "key": primary_hypothesis["key"],
        "next_feature_needed": primary_hypothesis["next_feature_needed"],
        "primary_evidence": {
            "file_path": primary_evidence["file_path"],
            "metrics": primary_evidence["metrics"],
            "path": primary_evidence["path"],
            "text": primary_evidence["text"],
            "trade_uid_count": primary_evidence["trade_uid_count"],
            "trade_uids": primary_evidence["trade_uids"],
        }
        if primary_evidence is not None
        else None,
    }


def _available_sections(document: dict[str, Any]) -> list[str]:
    sections = []
    for key in (
        "metadata",
        "executive_summary",
        "hypotheses",
        "observations",
        "limitations",
        "missing_data_for_backtest",
        "next_features_needed",
        "risks",
        "execution_recommendations",
    ):
        if key in document:
            sections.append(key)
    return sections

