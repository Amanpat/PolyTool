"""RIS evaluation gate — document evaluation pipeline.

DocumentEvaluator runs hard stops first, then optional dedup check, then
feature extraction, then scores with the configured provider, and finally
persists a structured artifact if artifacts_dir is set.

Phase 3 additions (backward compatible):
- Near-duplicate detection before LLM scoring (skipped if no existing_hashes provided)
- Per-family feature extraction (always runs, stored in artifact)
- Structured JSONL artifact persistence (skipped if no artifacts_dir provided)

Phase 2 additions (backward compatible):
- priority_tier parameter: sets priority tier on ScoringResult (default: config default)
- Fail-closed scoring: any exception from provider.score() returns REJECT with
  reject_reason="scorer_failure" instead of propagating the exception.
"""

from __future__ import annotations

import dataclasses
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from packages.research.evaluation.types import (
    EvalDocument,
    GateDecision,
    HardStopResult,
    SOURCE_FAMILIES,
)
from packages.research.evaluation.hard_stops import check_hard_stops
from packages.research.evaluation.providers import EvalProvider, get_provider


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _iso_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat()


class DocumentEvaluator:
    """Multi-provider evaluation gate for incoming research documents.

    Phase 3 pipeline: hard_stops -> dedup -> feature_extraction -> scoring -> artifact

    Uses ManualProvider by default — the pipeline works offline with no
    cloud API keys required. Pass a different provider for LLM-based scoring.

    Args:
        provider: EvalProvider instance. Defaults to ManualProvider.
        artifacts_dir: If set, persist a structured EvalArtifact JSONL record
            after each evaluation. Directory is created if it does not exist.
        existing_hashes: Set of content hashes for exact-duplicate detection.
            If None or empty, dedup check is skipped.
        existing_shingles: List of (doc_id, shingle_frozenset) pairs for
            near-duplicate detection. If None, shingle comparison is skipped.
    """

    def __init__(
        self,
        provider: Optional[EvalProvider] = None,
        artifacts_dir: Optional[Path] = None,
        existing_hashes: Optional[set] = None,
        existing_shingles: Optional[list] = None,
        priority_tier: Optional[str] = None,
    ):
        from packages.research.evaluation.providers import ManualProvider
        self._provider = provider if provider is not None else ManualProvider()
        self._artifacts_dir = Path(artifacts_dir) if artifacts_dir is not None else None
        self._existing_hashes: set = existing_hashes if existing_hashes is not None else set()
        self._existing_shingles: list = existing_shingles if existing_shingles is not None else []
        # priority_tier: None means use the config default (resolved at evaluation time)
        self._priority_tier = priority_tier

    def evaluate(self, doc: EvalDocument) -> GateDecision:
        """Evaluate a document through the quality gate.

        Steps:
        1. Hard stops — if any fail, return REJECT immediately (no scoring).
        2. Near-duplicate check — if existing_hashes provided and match found,
           return REJECT with dedup hard_stop (no scoring).
        3. Feature extraction — extract per-family features (always runs).
        4. LLM scoring — score with provider.
        5. Artifact persistence — if artifacts_dir is set, write JSONL record.
        6. Return GateDecision.

        Backward compatible: without artifacts_dir/existing_hashes/existing_shingles,
        behavior is identical to Phase 2.

        Args:
            doc: The document to evaluate.

        Returns:
            GateDecision with gate (ACCEPT|REVIEW|REJECT), scores, and metadata.
        """
        from packages.research.evaluation.feature_extraction import extract_features
        from packages.research.evaluation.dedup import check_near_duplicate
        from packages.research.evaluation.artifacts import (
            EvalArtifact,
            ProviderEvent,
            persist_eval_artifact,
            generate_event_id,
            compute_output_hash,
        )
        from packages.research.evaluation.scoring import (
            score_document_with_metadata,
            SCORING_PROMPT_TEMPLATE_ID,
        )
        from packages.research.evaluation.providers import get_provider_metadata

        now = _iso_utc(_utcnow())
        source_family = SOURCE_FAMILIES.get(doc.source_type, "manual")

        # Step 1: hard stops
        hard_stop_result = check_hard_stops(doc)
        if not hard_stop_result.passed:
            decision = GateDecision(
                gate="REJECT",
                scores=None,
                hard_stop=hard_stop_result,
                doc_id=doc.doc_id,
                timestamp=now,
            )
            if self._artifacts_dir is not None:
                features_result = extract_features(doc)
                artifact = EvalArtifact(
                    doc_id=doc.doc_id,
                    timestamp=now,
                    gate="REJECT",
                    hard_stop_result=dataclasses.asdict(hard_stop_result),
                    near_duplicate_result=None,
                    family_features=features_result.features,
                    scores=None,
                    source_family=source_family,
                    source_type=doc.source_type,
                    provider_event=None,
                    event_id=None,
                )
                persist_eval_artifact(artifact, self._artifacts_dir)
            return decision

        # Step 2: near-duplicate check (only if we have existing hashes to compare)
        near_dup_result = None
        if self._existing_hashes:
            near_dup_result = check_near_duplicate(
                doc, self._existing_hashes, self._existing_shingles
            )
            if near_dup_result.is_duplicate:
                dedup_stop = HardStopResult(
                    passed=False,
                    reason=f"Document is a {near_dup_result.duplicate_type} duplicate.",
                    stop_type=f"{near_dup_result.duplicate_type}_duplicate",
                )
                decision = GateDecision(
                    gate="REJECT",
                    scores=None,
                    hard_stop=dedup_stop,
                    doc_id=doc.doc_id,
                    timestamp=now,
                )
                if self._artifacts_dir is not None:
                    features_result = extract_features(doc)
                    artifact = EvalArtifact(
                        doc_id=doc.doc_id,
                        timestamp=now,
                        gate="REJECT",
                        hard_stop_result=dataclasses.asdict(dedup_stop),
                        near_duplicate_result=dataclasses.asdict(near_dup_result),
                        family_features=features_result.features,
                        scores=None,
                        source_family=source_family,
                        source_type=doc.source_type,
                        provider_event=None,
                        event_id=None,
                    )
                    persist_eval_artifact(artifact, self._artifacts_dir)
                return decision

        # Step 3: feature extraction
        features_result = extract_features(doc)

        # Step 4: score with provider (Phase 5: captures raw_output and prompt_hash)
        # Phase 2: fail-closed — any exception from provider returns REJECT with scorer_failure
        from packages.research.evaluation.config import get_eval_config
        from packages.research.evaluation.scoring import _compute_composite
        try:
            scores, raw_output, prompt_hash = score_document_with_metadata(doc, self._provider)
        except Exception:
            composite = _compute_composite(1, 1, 1, 1)
            from packages.research.evaluation.types import ScoringResult
            scores = ScoringResult(
                relevance=1, novelty=1, actionability=1, credibility=1,
                total=4,
                composite_score=composite,
                priority_tier=self._priority_tier or get_eval_config().default_priority_tier,
                reject_reason="scorer_failure",
                epistemic_type="UNKNOWN",
                summary="Provider exception — could not evaluate document.",
                key_findings=[],
                eval_model=self._provider.name,
            )
            raw_output = ""
            prompt_hash = ""

        # Set priority_tier on scores (Phase 2: default from config if not specified)
        if self._priority_tier is not None:
            scores = dataclasses.replace(scores, priority_tier=self._priority_tier)
        elif scores.priority_tier == "priority_3":
            # Apply config default in case it differs from hardcoded "priority_3"
            cfg_default = get_eval_config().default_priority_tier
            if cfg_default != "priority_3":
                scores = dataclasses.replace(scores, priority_tier=cfg_default)

        # Step 5: persist artifact (Phase 5: includes ProviderEvent metadata)
        if self._artifacts_dir is not None:
            scores_dict = {
                "relevance": scores.relevance,
                "novelty": scores.novelty,
                "actionability": scores.actionability,
                "credibility": scores.credibility,
                "total": scores.total,
                "epistemic_type": scores.epistemic_type,
                "summary": scores.summary,
                "key_findings": scores.key_findings,
                "eval_model": scores.eval_model,
                # Phase 2 fields
                "composite_score": scores.composite_score,
                "simple_sum_score": scores.simple_sum_score,
                "priority_tier": scores.priority_tier,
                "reject_reason": scores.reject_reason,
            }
            near_dup_dict = dataclasses.asdict(near_dup_result) if near_dup_result else None

            # Build replay-grade metadata for this scoring event
            provider_meta = get_provider_metadata(self._provider)
            event_id = generate_event_id(doc.doc_id, now, provider_meta["provider_name"])
            provider_event = ProviderEvent(
                provider_name=provider_meta["provider_name"],
                model_id=provider_meta["model_id"],
                prompt_template_id=SCORING_PROMPT_TEMPLATE_ID,
                prompt_template_version=prompt_hash,
                generation_params=provider_meta["generation_params"],
                source_chunk_refs=[doc.doc_id],
                timestamp=now,
                output_hash=compute_output_hash(raw_output),
                raw_output=None,  # keep artifacts lightweight by default
            )

            artifact = EvalArtifact(
                doc_id=doc.doc_id,
                timestamp=now,
                gate=scores.gate,
                hard_stop_result=None,
                near_duplicate_result=near_dup_dict,
                family_features=features_result.features,
                scores=scores_dict,
                source_family=source_family,
                source_type=doc.source_type,
                provider_event=dataclasses.asdict(provider_event),
                event_id=event_id,
            )
            persist_eval_artifact(artifact, self._artifacts_dir)

        # Step 6: return decision
        return GateDecision(
            gate=scores.gate,
            scores=scores,
            hard_stop=hard_stop_result,
            doc_id=doc.doc_id,
            timestamp=now,
        )


def evaluate_document(
    doc: EvalDocument,
    provider_name: str = "manual",
    artifacts_dir: Optional[Path] = None,
    priority_tier: Optional[str] = None,
    **kwargs,
) -> GateDecision:
    """Module-level convenience function for one-shot document evaluation.

    Creates a DocumentEvaluator with the specified provider and evaluates
    the document in a single call.

    Args:
        doc: The document to evaluate.
        provider_name: Provider identifier (default: "manual").
        artifacts_dir: Optional path for artifact persistence.
        priority_tier: Priority tier for gate thresholds (default: config default).
            Use "priority_1" for trusted/high-signal documents (lower threshold).
            Use "priority_4" for low-trust sources (higher threshold).
        **kwargs: Passed to get_provider() (e.g., model= for OllamaProvider).

    Returns:
        GateDecision with gate (ACCEPT|REVIEW|REJECT), scores, and metadata.
    """
    provider = get_provider(provider_name, **kwargs)
    evaluator = DocumentEvaluator(
        provider=provider,
        artifacts_dir=artifacts_dir,
        priority_tier=priority_tier,
    )
    return evaluator.evaluate(doc)
