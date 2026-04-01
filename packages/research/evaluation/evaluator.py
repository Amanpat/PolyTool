"""RIS v1 evaluation gate — document evaluation pipeline.

DocumentEvaluator runs hard stops first, then scores with the configured
provider, and returns a GateDecision (ACCEPT / REVIEW / REJECT).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from packages.research.evaluation.types import (
    EvalDocument,
    GateDecision,
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

    Uses ManualProvider by default — the pipeline works offline with no
    cloud API keys required. Pass a different provider for LLM-based scoring.
    """

    def __init__(self, provider: Optional[EvalProvider] = None):
        from packages.research.evaluation.providers import ManualProvider
        self._provider = provider if provider is not None else ManualProvider()

    def evaluate(self, doc: EvalDocument) -> GateDecision:
        """Evaluate a document through the quality gate.

        Steps:
        1. Run hard stops — if any fail, return REJECT immediately (no scoring).
        2. If all hard stops pass, score the document with the provider.
        3. Return GateDecision with gate derived from scoring total.

        Args:
            doc: The document to evaluate.

        Returns:
            GateDecision with gate (ACCEPT|REVIEW|REJECT), scores, and metadata.
        """
        now = _iso_utc(_utcnow())

        # Step 1: hard stops
        hard_stop_result = check_hard_stops(doc)
        if not hard_stop_result.passed:
            return GateDecision(
                gate="REJECT",
                scores=None,
                hard_stop=hard_stop_result,
                doc_id=doc.doc_id,
                timestamp=now,
            )

        # Step 2: score with provider
        scores = score_document(doc, self._provider)

        # Step 3: return decision
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
    **kwargs,
) -> GateDecision:
    """Module-level convenience function for one-shot document evaluation.

    Creates a DocumentEvaluator with the specified provider and evaluates
    the document in a single call.

    Args:
        doc: The document to evaluate.
        provider_name: Provider identifier (default: "manual").
        **kwargs: Passed to get_provider() (e.g., model= for OllamaProvider).

    Returns:
        GateDecision with gate (ACCEPT|REVIEW|REJECT), scores, and metadata.
    """
    provider = get_provider(provider_name, **kwargs)
    evaluator = DocumentEvaluator(provider=provider)
    return evaluator.evaluate(doc)
