"""RIS v1 ingestion — knowledge store query helpers.

Provides query_knowledge_store() and format_provenance() as thin helpers
on top of KnowledgeStore.query_claims(), separate from the Chroma query path.
"""

from __future__ import annotations

from typing import Optional

from packages.polymarket.rag.knowledge_store import KnowledgeStore


def query_knowledge_store(
    store: KnowledgeStore,
    *,
    source_family: Optional[str] = None,
    min_freshness: Optional[float] = None,
    top_k: int = 20,
) -> list[dict]:
    """Query claims from the KnowledgeStore with optional filtering.

    Parameters
    ----------
    store:
        A ``KnowledgeStore`` instance.
    source_family:
        If provided, only return claims whose source document belongs to this
        source family.
    min_freshness:
        If provided, exclude claims whose ``freshness_modifier`` is below this
        threshold.  Claims with no source document are included (freshness=1.0).
    top_k:
        Maximum number of results to return (already sorted by
        ``effective_score`` DESC from ``query_claims``).

    Returns
    -------
    list[dict]
        Up to ``top_k`` claim dicts, each augmented with ``freshness_modifier``
        and ``effective_score``.
    """
    claims = store.query_claims(apply_freshness=True)

    # Cache source document lookups to avoid N+1 queries
    _doc_cache: dict[str, Optional[dict]] = {}

    def _get_doc(doc_id: Optional[str]) -> Optional[dict]:
        if not doc_id:
            return None
        if doc_id not in _doc_cache:
            _doc_cache[doc_id] = store.get_source_document(doc_id)
        return _doc_cache[doc_id]

    results: list[dict] = []
    for claim in claims:
        # --- source_family filter ---
        if source_family is not None:
            src_doc = _get_doc(claim.get("source_document_id"))
            if src_doc is None or src_doc.get("source_family") != source_family:
                continue

        # --- min_freshness filter ---
        if min_freshness is not None:
            fm = claim.get("freshness_modifier", 1.0)
            if fm < min_freshness:
                continue

        results.append(claim)
        if len(results) >= top_k:
            break

    return results


def format_provenance(claim: dict, source_docs: list[dict]) -> str:
    """Format a human-readable provenance string for a claim.

    Parameters
    ----------
    claim:
        A claim dict (from ``KnowledgeStore.get_claim()`` or ``query_claims()``).
    source_docs:
        List of source document dicts linked to this claim (from
        ``KnowledgeStore.get_provenance()``).

    Returns
    -------
    str
        Multi-line provenance string.
    """
    claim_text = claim.get("claim_text", "(no claim text)")
    confidence = claim.get("confidence", 0.0)
    freshness = claim.get("freshness_modifier", 1.0)
    status = claim.get("validation_status", "UNTESTED")

    lines = [
        f"Claim: {claim_text}",
        f"Confidence: {confidence} | Freshness: {freshness:.2f} | Status: {status}",
    ]

    if source_docs:
        lines.append("Sources:")
        for doc in source_docs:
            title = doc.get("title") or "(untitled)"
            url = doc.get("source_url") or "(no url)"
            family = doc.get("source_family") or "(unknown)"
            lines.append(f"  - {title} ({url}) [family: {family}]")
    else:
        lines.append("Sources: (none linked)")

    return "\n".join(lines)
