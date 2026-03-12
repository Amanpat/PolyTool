"""Deterministic summary extraction for saved hypothesis JSON artifacts."""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


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

    metadata = _extract_metadata(document.get("metadata"))
    executive_summary = _extract_executive_summary(document.get("executive_summary"))
    hypotheses = _build_hypothesis_entries(document.get("hypotheses"))
    primary_hypothesis = hypotheses[0] if hypotheses else None

    limitations = _extract_text_entries(document.get("limitations"), "limitations")
    missing_data = _extract_text_entries(
        document.get("missing_data_for_backtest"),
        "missing_data_for_backtest",
    )
    next_features = _extract_text_entries(
        document.get("next_features_needed"),
        "next_features_needed",
    )
    risks = _extract_text_entries(document.get("risks"), "risks")
    execution_recommendations = _extract_text_entries(
        document.get("execution_recommendations"),
        "execution_recommendations",
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


def _extract_executive_summary(value: Any) -> dict[str, Any]:
    summary = value if isinstance(value, dict) else {}
    bullets = []
    for index, item in enumerate(_as_list(summary.get("bullets"))):
        text = _nonempty_string(item)
        if text is None:
            continue
        bullets.append(
            {
                "path": f"executive_summary.bullets[{index}]",
                "text": text,
            }
        )
    return {
        "bullets": bullets,
        "overall_assessment": _nonempty_string(summary.get("overall_assessment")),
    }


def _extract_text_entries(value: Any, base_path: str) -> list[dict[str, str]]:
    entries: list[dict[str, str]] = []
    if isinstance(value, list):
        iterable = enumerate(value)
    elif isinstance(value, str):
        iterable = [(0, value)]
    else:
        iterable = []

    for index, item in iterable:
        text = _nonempty_string(item)
        if text is None:
            continue
        entries.append(
            {
                "path": f"{base_path}[{index}]",
                "text": text,
            }
        )
    return entries


def _canonical_signature(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, separators=(",", ":"), sort_keys=True)


def _build_hypothesis_entries(value: Any) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for index, raw_entry in enumerate(_as_list(value)):
        hypothesis = raw_entry if isinstance(raw_entry, dict) else {}
        evidence = _build_evidence_entries(hypothesis.get("evidence"))
        entry = {
            "claim": _nonempty_string(hypothesis.get("claim")),
            "confidence": _nonempty_string(hypothesis.get("confidence")),
            "evidence_count": len(evidence),
            "execution_recommendation": _nonempty_string(
                hypothesis.get("execution_recommendation")
            ),
            "id": _nonempty_string(hypothesis.get("id")),
            "index": index,
            "next_feature_needed": _nonempty_string(
                hypothesis.get("next_feature_needed")
            ),
            "primary_evidence": _select_primary_evidence(evidence),
            "raw": raw_entry,
            "signature": _canonical_signature(raw_entry),
        }
        entries.append(entry)

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
    match = _HYPOTHESIS_ID_RE.match(hypothesis_id or "")
    if match is not None:
        return (0, int(match.group("number")), hypothesis_id, claim.lower(), entry["index"])
    if hypothesis_id is not None:
        return (1, hypothesis_id.lower(), claim.lower(), entry["index"])
    if claim:
        return (2, claim.lower(), entry["index"])
    return (3, entry["signature"], entry["index"])


def _hypothesis_base_key(entry: dict[str, Any]) -> str:
    if entry["id"] is not None:
        return f"id:{entry['id']}"
    if entry["claim"] is not None:
        return f"claim:{entry['claim']}"
    return "anonymous"


def _build_evidence_entries(value: Any) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for index, raw_entry in enumerate(_as_list(value)):
        evidence = raw_entry if isinstance(raw_entry, dict) else {}
        trade_uids = sorted(
            item
            for item in _as_list(evidence.get("trade_uids"))
            if isinstance(item, str) and item.strip()
        )
        metrics = evidence.get("metrics") if isinstance(evidence.get("metrics"), dict) else {}
        text = _nonempty_string(evidence.get("text"))
        file_path = _nonempty_string(evidence.get("file_path"))
        if text is None and isinstance(raw_entry, str):
            text = _nonempty_string(raw_entry)
        entries.append(
            {
                "file_path": file_path,
                "metrics": metrics,
                "path": f"evidence[{index}].text",
                "text": text,
                "trade_uid_count": len(trade_uids),
                "trade_uids": trade_uids,
            }
        )
    return entries


def _select_primary_evidence(entries: list[dict[str, Any]]) -> dict[str, Any] | None:
    for entry in entries:
        if entry["text"] is not None:
            return entry
    return entries[0] if entries else None


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

