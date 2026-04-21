"""Helpers for mapping evaluator outcomes onto ingest/review dispositions."""

from __future__ import annotations

from typing import Any, Optional

from packages.research.evaluation.types import GateDecision, HardStopResult, ScoringResult
from packages.research.ingestion.extractors import ExtractedDocument

DISPOSITION_ACCEPTED = "accepted"
DISPOSITION_QUEUED = "queued_for_review"
DISPOSITION_REJECTED = "rejected"
DISPOSITION_BLOCKED = "blocked"


def classify_gate_disposition(
    gate_decision: Optional[GateDecision],
    *,
    fallback_reason: Optional[str] = None,
) -> tuple[str, Optional[str]]:
    """Map an evaluator gate result onto the final ingest disposition."""

    if gate_decision is None:
        return DISPOSITION_ACCEPTED, None

    if gate_decision.gate == "ACCEPT":
        return DISPOSITION_ACCEPTED, None

    if gate_decision.gate == "REVIEW":
        reason = None
        if gate_decision.scores is not None:
            reason = gate_decision.scores.summary or None
        return DISPOSITION_QUEUED, reason or fallback_reason or "Human review required."

    if _is_fail_closed(gate_decision):
        reason = None
        if gate_decision.scores is not None:
            reason = gate_decision.scores.summary or None
        return DISPOSITION_BLOCKED, reason or fallback_reason or "Evaluation failed closed."

    reason = _reject_reason_from_gate(gate_decision)
    return DISPOSITION_REJECTED, reason or fallback_reason or "Rejected by evaluation gate."


def build_pending_review_snapshot(
    *,
    extracted: ExtractedDocument,
    gate_decision: GateDecision,
    source_type: str,
    disposition: str,
    source_metadata_ref: Optional[str],
) -> dict[str, Any]:
    """Build a stable queue snapshot for operator review."""

    snapshot: dict[str, Any] = {
        "disposition": disposition,
        "gate": gate_decision.gate,
        "provider_name": _provider_name_from_gate(gate_decision),
        "eval_model": _eval_model_from_gate(gate_decision),
        "weighted_score": None,
        "simple_sum_score": None,
        "scores": _serialize_scores(gate_decision.scores),
        "hard_stop": _serialize_hard_stop(gate_decision.hard_stop),
        "routing": gate_decision.routing,
        "source_document": {
            "title": extracted.title,
            "author": extracted.author,
            "source_url": extracted.source_url,
            "source_type": source_type,
            "source_family": extracted.source_family,
            "publish_date": extracted.publish_date,
            "source_metadata_ref": source_metadata_ref,
            "content_hash": extracted.metadata.get("content_hash"),
            "canonical_ids": extracted.metadata.get("canonical_ids"),
            "body_preview": _body_preview(extracted.body),
            "metadata": extracted.metadata,
        },
    }

    scores = snapshot["scores"]
    if isinstance(scores, dict):
        snapshot["weighted_score"] = scores.get("composite_score")
        snapshot["simple_sum_score"] = scores.get("simple_sum_score", scores.get("total"))

    return snapshot


def is_queue_disposition(disposition: str) -> bool:
    return disposition in {DISPOSITION_QUEUED, DISPOSITION_BLOCKED}


def _is_fail_closed(gate_decision: GateDecision) -> bool:
    return bool(
        gate_decision.gate == "REJECT"
        and gate_decision.scores is not None
        and gate_decision.scores.reject_reason == "scorer_failure"
    )


def _reject_reason_from_gate(gate_decision: GateDecision) -> Optional[str]:
    if gate_decision.hard_stop is not None and gate_decision.hard_stop.reason:
        return gate_decision.hard_stop.reason
    if gate_decision.scores is not None:
        if gate_decision.scores.reject_reason:
            return gate_decision.scores.reject_reason
        if gate_decision.scores.summary:
            return gate_decision.scores.summary
    return None


def _provider_name_from_gate(gate_decision: GateDecision) -> Optional[str]:
    if gate_decision.scores is not None and gate_decision.scores.eval_provider:
        return gate_decision.scores.eval_provider
    routing = gate_decision.routing or {}
    selected_provider = routing.get("selected_provider")
    return str(selected_provider) if selected_provider else None


def _eval_model_from_gate(gate_decision: GateDecision) -> Optional[str]:
    if gate_decision.scores is not None and gate_decision.scores.eval_model:
        return gate_decision.scores.eval_model
    routing = gate_decision.routing or {}
    selected_model = routing.get("selected_model")
    return str(selected_model) if selected_model else None


def _serialize_scores(scores: Optional[ScoringResult]) -> Optional[dict[str, Any]]:
    if scores is None:
        return None
    return {
        "relevance": scores.relevance,
        "novelty": scores.novelty,
        "actionability": scores.actionability,
        "credibility": scores.credibility,
        "total": scores.total,
        "simple_sum_score": scores.simple_sum_score,
        "composite_score": scores.composite_score,
        "priority_tier": scores.priority_tier,
        "reject_reason": scores.reject_reason,
        "epistemic_type": scores.epistemic_type,
        "summary": scores.summary,
        "key_findings": scores.key_findings,
        "eval_model": scores.eval_model,
        "eval_provider": scores.eval_provider,
    }


def _serialize_hard_stop(hard_stop: Optional[HardStopResult]) -> Optional[dict[str, Any]]:
    if hard_stop is None:
        return None
    return {
        "passed": hard_stop.passed,
        "reason": hard_stop.reason,
        "stop_type": hard_stop.stop_type,
    }


def _body_preview(body: str, limit: int = 600) -> str:
    normalized = " ".join((body or "").split())
    if len(normalized) <= limit:
        return normalized
    return normalized[: limit - 3] + "..."
