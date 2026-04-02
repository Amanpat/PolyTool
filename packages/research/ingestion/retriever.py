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


def query_knowledge_store_enriched(
    store: KnowledgeStore,
    *,
    source_family: Optional[str] = None,
    min_freshness: Optional[float] = None,
    top_k: int = 20,
    include_contradicted: bool = False,  # noqa: ARG001 — extensibility hook
) -> list[dict]:
    """Query claims with provenance, contradiction, staleness, and lifecycle data.

    Parameters
    ----------
    store:
        A ``KnowledgeStore`` instance.
    source_family:
        If provided, only return claims whose source document belongs to this
        source family.
    min_freshness:
        If provided, exclude claims whose ``freshness_modifier`` is below this
        threshold.
    top_k:
        Maximum number of results to return (sorted by ``effective_score`` DESC).
    include_contradicted:
        Documentation/extensibility hook. Contradicted claims are already
        downweighted via KnowledgeStore's 0.5x ``effective_score`` penalty and
        appear in results regardless of this flag. Setting ``True`` or ``False``
        produces the same result set (both annotated, sorted lower by score).

    Returns
    -------
    list[dict]
        Up to ``top_k`` claim dicts, each augmented with:
        - ``provenance_docs``: list of source document dicts from get_provenance()
        - ``contradiction_summary``: list of claim texts that CONTRADICT this claim
        - ``is_contradicted``: bool — True if contradiction_summary is non-empty
        - ``staleness_note``: "STALE" if freshness_modifier < 0.5,
          "AGING" if < 0.7, else ""
        - ``lifecycle``: from the claim's own lifecycle field
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

        claim_id = claim["id"]

        # Provenance: source documents linked via claim_evidence
        provenance_docs = store.get_provenance(claim_id)

        # Contradiction summary: texts of claims that CONTRADICT this one
        contradiction_relations = store.get_relations(claim_id, relation_type="CONTRADICTS")
        contradiction_summary: list[str] = []
        for rel in contradiction_relations:
            # The other claim could be source or target of the relation
            other_id = (
                rel["source_claim_id"]
                if rel["target_claim_id"] == claim_id
                else rel["target_claim_id"]
            )
            if other_id == claim_id:
                continue
            other_claim = store.get_claim(other_id)
            if other_claim:
                contradiction_summary.append(other_claim["claim_text"])

        # Staleness note
        fm = claim.get("freshness_modifier", 1.0)
        if fm < 0.5:
            staleness_note = "STALE"
        elif fm < 0.7:
            staleness_note = "AGING"
        else:
            staleness_note = ""

        enriched = dict(claim)
        enriched["provenance_docs"] = provenance_docs
        enriched["contradiction_summary"] = contradiction_summary
        enriched["is_contradicted"] = len(contradiction_summary) > 0
        enriched["staleness_note"] = staleness_note
        enriched["lifecycle"] = claim.get("lifecycle", "active")

        results.append(enriched)
        if len(results) >= top_k:
            break

    return results


def query_knowledge_store_for_rrf(
    store: KnowledgeStore,
    *,
    text_query: Optional[str] = None,
    source_family: Optional[str] = None,
    min_freshness: Optional[float] = None,
    top_k: int = 25,
) -> list[dict]:
    """Query claims and return RRF-compatible result dicts.

    Adapts KnowledgeStore enriched claims into the same dict contract used by
    ``reciprocal_rank_fusion`` so they can participate in three-way RRF
    fusion alongside Chroma vector and FTS5 lexical results.

    Parameters
    ----------
    store:
        A ``KnowledgeStore`` instance.
    text_query:
        Optional keyword filter.  When provided, only claims whose
        ``claim_text`` contains the query as a case-insensitive substring
        are returned.  When ``None``, all claims pass through.
    source_family:
        Optional source_family filter for KS claims.
    min_freshness:
        Optional minimum freshness_modifier threshold.
    top_k:
        Maximum number of RRF-compatible results to return.

    Returns
    -------
    list[dict]
        Each dict matches the RRF contract:
        ``chunk_id``, ``score``, ``snippet``, ``file_path``,
        ``chunk_index``, ``doc_id``, ``metadata``.
        Results are sorted by score descending and limited to ``top_k``.
    """
    enriched = query_knowledge_store_enriched(
        store,
        source_family=source_family,
        min_freshness=min_freshness,
        top_k=top_k * 4,  # over-fetch before text filter
        include_contradicted=True,
    )

    # Apply optional text filter (case-insensitive substring match)
    if text_query is not None:
        query_lower = text_query.lower()
        enriched = [c for c in enriched if query_lower in c.get("claim_text", "").lower()]

    results: list[dict] = []
    for claim in enriched:
        claim_id = claim["id"]
        claim_text = claim.get("claim_text", "")
        snippet = claim_text[:400].rstrip() + ("..." if len(claim_text) > 400 else "")

        # Build provenance_docs as lightweight dicts (title/source_url/source_family)
        provenance_docs_full: list[dict] = claim.get("provenance_docs", [])
        provenance_docs = [
            {
                "title": d.get("title"),
                "source_url": d.get("source_url"),
                "source_family": d.get("source_family"),
            }
            for d in provenance_docs_full
        ]

        metadata: dict = {
            "source": "knowledge_store",
            "claim_type": claim.get("claim_type"),
            "confidence": claim.get("confidence"),
            "freshness_modifier": claim.get("freshness_modifier", 1.0),
            "staleness_note": claim.get("staleness_note", ""),
            "is_contradicted": claim.get("is_contradicted", False),
            "contradiction_summary": claim.get("contradiction_summary", []),
            "provenance_docs": provenance_docs,
            "lifecycle": claim.get("lifecycle", "active"),
            "claim_text": claim_text,
        }

        rrf_result: dict = {
            "chunk_id": claim_id,
            "score": claim.get("effective_score", 0.0),
            "snippet": snippet,
            "file_path": f"knowledge_store://claim/{claim_id}",
            "chunk_index": 0,
            "doc_id": claim.get("source_document_id", "") or "",
            "metadata": metadata,
        }
        results.append(rrf_result)
        if len(results) >= top_k:
            break

    return results


def format_enriched_report(claims: list[dict]) -> str:
    """Format a structured multi-line report of enriched claims.

    Parameters
    ----------
    claims:
        A list of enriched claim dicts from ``query_knowledge_store_enriched()``.

    Returns
    -------
    str
        Multi-line report string with one section per claim, separated by "---".
    """
    if not claims:
        return "(no claims)"

    sections: list[str] = []
    for i, claim in enumerate(claims, start=1):
        claim_text = claim.get("claim_text", "(no claim text)")
        confidence = claim.get("confidence", 0.0)
        freshness = claim.get("freshness_modifier", 1.0)
        effective_score = claim.get("effective_score", 0.0)
        lifecycle = claim.get("lifecycle", "active")
        validation_status = claim.get("validation_status", "UNTESTED")
        staleness_note = claim.get("staleness_note", "") or "(fresh)"
        contradiction_summary: list[str] = claim.get("contradiction_summary", [])
        provenance_docs: list[dict] = claim.get("provenance_docs", [])

        # Format contradiction summary
        if contradiction_summary:
            contradictions_str = "; ".join(contradiction_summary)
        else:
            contradictions_str = "(none)"

        # Format provenance
        if provenance_docs:
            titles = [doc.get("title") or "(untitled)" for doc in provenance_docs]
            provenance_str = "; ".join(titles)
        else:
            provenance_str = "(none linked)"

        section_lines = [
            f"[{i}] Claim: {claim_text}",
            f"    Confidence: {confidence} | Freshness: {freshness:.2f} | Score: {effective_score:.3f}",
            f"    Lifecycle: {lifecycle} | Status: {validation_status}",
            f"    Staleness: {staleness_note}",
            f"    Contradictions: {contradictions_str}",
            f"    Provenance: {provenance_str}",
        ]
        sections.append("\n".join(section_lines))

    return "\n---\n".join(sections)


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
