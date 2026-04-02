"""RIS evaluation gate — document evaluation pipeline.

DocumentEvaluator runs hard stops first, then optional dedup check, then
feature extraction, then scores with the configured provider, and finally
persists a structured artifact if artifacts_dir is set.

Phase 3 additions (backward compatible):
- Near-duplicate detection before LLM scoring (skipped if no existing_hashes provided)
- Per-family feature extraction (always runs, stored in artifact)
- Structured JSONL artifact persistence (skipped if no artifacts_dir provided)
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
from packages.research.evaluation.scoring import score_document
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
    ):
        from packages.research.evaluation.providers import ManualProvider
        self._provider = provider if provider is not None else ManualProvider()
        self._artifacts_dir = Path(artifacts_dir) if artifacts_dir is not None else None
        self._existing_hashes: set = existing_hashes if existing_hashes is not None else set()
        self._existing_shingles: list = existing_shingles if existing_shingles is not None else []

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
        from packages.research.evaluation.artifacts import EvalArtifact, persist_eval_artifact

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
                    )
                    persist_eval_artifact(artifact, self._artifacts_dir)
                return decision

        # Step 3: feature extraction
        features_result = extract_features(doc)

        # Step 4: score with provider
        scores = score_document(doc, self._provider)

        # Step 5: persist artifact
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
            }
            near_dup_dict = dataclasses.asdict(near_dup_result) if near_dup_result else None
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
    **kwargs,
) -> GateDecision:
    """Module-level convenience function for one-shot document evaluation.

    Creates a DocumentEvaluator with the specified provider and evaluates
    the document in a single call.

    Args:
        doc: The document to evaluate.
        provider_name: Provider identifier (default: "manual").
        artifacts_dir: Optional path for artifact persistence.
        **kwargs: Passed to get_provider() (e.g., model= for OllamaProvider).

    Returns:
        GateDecision with gate (ACCEPT|REVIEW|REJECT), scores, and metadata.
    """
    provider = get_provider(provider_name, **kwargs)
    evaluator = DocumentEvaluator(provider=provider, artifacts_dir=artifacts_dir)
    return evaluator.evaluate(doc)
