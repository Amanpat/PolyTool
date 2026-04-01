"""RIS v1 ingestion pipeline.

Orchestrates: extract -> hard-stop check -> optional eval gate -> KnowledgeStore persistence.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from packages.research.evaluation.hard_stops import check_hard_stops
from packages.research.evaluation.types import EvalDocument, GateDecision
from packages.polymarket.rag.chunker import chunk_text
from packages.polymarket.rag.knowledge_store import KnowledgeStore
from packages.research.ingestion.extractors import Extractor, PlainTextExtractor


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _utcnow_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def _sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# IngestResult
# ---------------------------------------------------------------------------

@dataclass
class IngestResult:
    """Result returned by IngestPipeline.ingest().

    Attributes
    ----------
    doc_id:
        The KnowledgeStore source-document ID (deterministic SHA-256).
        Empty string if the document was rejected before storage.
    chunk_count:
        Number of text chunks derived from the document body.
        0 if rejected before chunking.
    gate_decision:
        The eval-gate GateDecision, or None if eval was skipped (--no-eval).
    rejected:
        True if the document was rejected (hard-stop or eval-gate REJECT).
    reject_reason:
        Human-readable rejection reason, or None if accepted.
    """
    doc_id: str
    chunk_count: int
    gate_decision: Optional[GateDecision]
    rejected: bool
    reject_reason: Optional[str]


# ---------------------------------------------------------------------------
# IngestPipeline
# ---------------------------------------------------------------------------

class IngestPipeline:
    """Orchestrates extract -> hard-stop -> optional eval-gate -> KnowledgeStore.

    Parameters
    ----------
    store:
        A ``KnowledgeStore`` instance (may be in-memory for tests).
    extractor:
        Extractor to use.  Defaults to ``PlainTextExtractor()``.
    evaluator:
        ``DocumentEvaluator`` instance for eval gating.  Pass ``None`` to skip
        eval gating entirely (equivalent to ``--no-eval``).
    """

    def __init__(
        self,
        store: KnowledgeStore,
        extractor: Optional[Extractor] = None,
        evaluator=None,  # Optional[DocumentEvaluator] -- avoid circular import
    ) -> None:
        self._store = store
        self._extractor = extractor if extractor is not None else PlainTextExtractor()
        self._evaluator = evaluator

    def ingest(self, source: "str | Path", **kwargs) -> IngestResult:
        """Ingest a document from *source* into the KnowledgeStore.

        Parameters
        ----------
        source:
            File path or raw text string (same semantics as PlainTextExtractor).
        **kwargs:
            Passed to ``extractor.extract()`` (e.g. ``source_type``, ``author``,
            ``title``, ``publish_date``).

        Returns
        -------
        IngestResult
            Always returns a result (never raises on expected rejection).
        """
        # Step 1: Extract
        extracted = self._extractor.extract(source, **kwargs)

        # Step 2: Build EvalDocument for hard-stop check
        doc_id_seed = _sha256_hex(extracted.body[:200] + extracted.title)
        eval_doc = EvalDocument(
            doc_id=doc_id_seed,
            title=extracted.title,
            author=extracted.author,
            source_type=kwargs.get("source_type", "manual"),
            source_url=extracted.source_url,
            source_publish_date=extracted.publish_date,
            body=extracted.body,
            metadata=extracted.metadata,
        )

        # Step 3: Hard-stop pre-screening
        hard_stop = check_hard_stops(eval_doc)
        if not hard_stop.passed:
            return IngestResult(
                doc_id="",
                chunk_count=0,
                gate_decision=None,
                rejected=True,
                reject_reason=hard_stop.reason or hard_stop.stop_type or "hard stop failed",
            )

        # Step 4: Optional eval gate
        gate_decision: Optional[GateDecision] = None
        if self._evaluator is not None:
            gate_decision = self._evaluator.evaluate(eval_doc)
            if gate_decision.gate == "REJECT":
                reason = (
                    gate_decision.hard_stop.reason
                    if gate_decision.hard_stop and gate_decision.hard_stop.reason
                    else f"eval gate: {gate_decision.gate}"
                )
                return IngestResult(
                    doc_id="",
                    chunk_count=0,
                    gate_decision=gate_decision,
                    rejected=True,
                    reject_reason=reason,
                )

        # Step 5: Chunk
        chunks = chunk_text(extracted.body)
        chunk_count = len(chunks)

        # Step 6: Store source document
        content_hash = extracted.metadata.get("content_hash") or _sha256_hex(extracted.body)
        doc_id = self._store.add_source_document(
            title=extracted.title,
            source_url=extracted.source_url,
            source_family=extracted.source_family,
            content_hash=content_hash,
            chunk_count=chunk_count,
            published_at=extracted.publish_date,
            ingested_at=_utcnow_iso(),
            confidence_tier=None,
            metadata_json=json.dumps(extracted.metadata),
        )

        # Step 7: Return result
        return IngestResult(
            doc_id=doc_id,
            chunk_count=chunk_count,
            gate_decision=gate_decision,
            rejected=False,
            reject_reason=None,
        )
