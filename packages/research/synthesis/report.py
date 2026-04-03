"""RIS v1 synthesis -- deterministic report and enhanced precheck generation.

Provides ReportSynthesizer, which takes enriched claim dicts from
``query_knowledge_store_enriched()`` and produces structured, cited research
artifacts. This is purely deterministic synthesis -- no LLM calls.
LLM-based synthesis (DeepSeek V3) is a v2 feature.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class CitedEvidence:
    """A single piece of evidence with full source attribution."""
    claim_text: str
    source_doc_id: str
    source_title: str
    source_type: str
    trust_tier: str
    confidence: float
    freshness_note: str
    provenance_url: str


@dataclass
class ResearchBrief:
    """Structured research brief matching RIS_05 format."""
    topic: str
    generated_at: str
    sources_queried: int
    sources_cited: int
    overall_confidence: str                 # HIGH | MEDIUM | LOW
    summary: str
    key_findings: list                      # list[dict] keys: title, description, source, confidence_tier
    contradictions: list                    # list[dict] keys: claim_a, claim_b, sources
    actionability: dict                     # keys: can_inform_strategy, target_track, suggested_next_step, estimated_impact
    knowledge_gaps: list                    # list[str]
    cited_sources: list                     # list[CitedEvidence]


@dataclass
class EnhancedPrecheck:
    """Enhanced precheck with cited evidence lists. Parallel to PrecheckResult; does not replace it."""
    recommendation: str                     # GO | CAUTION | STOP
    idea: str
    supporting: list                        # list[CitedEvidence]
    contradicting: list                     # list[CitedEvidence]
    risk_factors: list                      # list[str]
    past_failures: list                     # list[str]
    knowledge_gaps: list                    # list[str]
    validation_approach: str
    timestamp: str
    overall_confidence: str                 # HIGH | MEDIUM | LOW
    stale_warning: bool = False
    evidence_gap: str = ""
    precheck_id: str = ""


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def format_citation(evidence: CitedEvidence) -> str:
    """Produce a short inline citation string for a CitedEvidence entry.

    Format: ``[doc_id] (source_type, trust_tier)``
    """
    return f"[{evidence.source_doc_id}] ({evidence.source_type}, {evidence.trust_tier})"


def _extract_cited_evidence(claim: dict) -> CitedEvidence:
    """Extract CitedEvidence from an enriched claim dict.

    Uses the first provenance document if available; falls back to synthetic
    values derived from the claim itself.
    """
    provenance_docs: list[dict] = claim.get("provenance_docs") or []
    staleness_note: str = claim.get("staleness_note") or ""

    freshness_note = ""
    if staleness_note == "STALE":
        freshness_note = "STALE"
    elif staleness_note == "AGING":
        freshness_note = "AGING"

    if provenance_docs:
        doc = provenance_docs[0]
        return CitedEvidence(
            claim_text=claim.get("claim_text", ""),
            source_doc_id=doc.get("id") or claim.get("source_document_id") or "",
            source_title=doc.get("title") or "",
            source_type=doc.get("source_type") or "",
            trust_tier=doc.get("trust_tier") or claim.get("trust_tier") or "",
            confidence=float(claim.get("confidence") or 0.0),
            freshness_note=freshness_note,
            provenance_url=doc.get("source_url") or "",
        )
    else:
        # No provenance docs -- synthesize from claim metadata
        return CitedEvidence(
            claim_text=claim.get("claim_text", ""),
            source_doc_id=claim.get("source_document_id") or "",
            source_title="",
            source_type=claim.get("source_type") or "",
            trust_tier=claim.get("trust_tier") or "",
            confidence=float(claim.get("confidence") or 0.0),
            freshness_note=freshness_note,
            provenance_url="",
        )


def _compute_overall_confidence(claims: list[dict]) -> str:
    """Derive HIGH/MEDIUM/LOW from claim quality metrics.

    - HIGH: avg confidence >= 0.8 and no STALE claims
    - LOW: avg confidence < 0.5 OR majority are STALE
    - MEDIUM: otherwise
    """
    if not claims:
        return "LOW"

    confidences = [float(c.get("confidence") or 0.0) for c in claims]
    avg_conf = sum(confidences) / len(confidences)
    stale_count = sum(1 for c in claims if c.get("staleness_note") == "STALE")
    stale_ratio = stale_count / len(claims)

    if avg_conf >= 0.8 and stale_count == 0:
        return "HIGH"
    if avg_conf < 0.5 or stale_ratio > 0.5:
        return "LOW"
    return "MEDIUM"


_STRATEGY_KEYWORDS = {
    "market_maker": ["market maker", "market-maker", "avellaneda", "stoikov", "quoting", "bid-ask", "spread"],
    "crypto": ["crypto", "bitcoin", "btc", "eth", "ethereum", "sol", "solana", "pair bot", "pair accumulation"],
    "sports": ["sports", "football", "nba", "nfl", "nhl", "soccer", "baseball"],
}


def _detect_strategy_relevance(claim_text: str) -> tuple[bool, str]:
    """Return (is_relevant, track_name) for the claim text.

    Checks claim text for strategy keywords to support actionability assessment.
    """
    text_lower = claim_text.lower()
    for track, keywords in _STRATEGY_KEYWORDS.items():
        for kw in keywords:
            if kw in text_lower:
                return True, track
    return False, ""


def _idea_relevance_score(idea: str, claim_text: str) -> float:
    """Simple keyword overlap score for precheck relevance filtering.

    Splits the idea into words (min length 4) and counts how many appear
    in the claim text. Returns fraction of idea words that matched.
    """
    idea_words = [w.lower() for w in idea.split() if len(w) >= 4]
    if not idea_words:
        return 0.0
    claim_lower = claim_text.lower()
    matched = sum(1 for w in idea_words if w in claim_lower)
    return matched / len(idea_words)


# ---------------------------------------------------------------------------
# ReportSynthesizer
# ---------------------------------------------------------------------------

class ReportSynthesizer:
    """Deterministic synthesis from enriched claim evidence.

    No LLM calls. All outputs are assembled from structured evidence metadata.
    LLM-based synthesis is a v2 feature (DeepSeek V3, deferred per RIS_05 spec).
    """

    # Maximum number of claims included as key findings
    _MAX_KEY_FINDINGS = 5

    def synthesize_brief(self, topic: str, enriched_claims: list[dict]) -> ResearchBrief:
        """Produce a ResearchBrief from enriched claims.

        Parameters
        ----------
        topic:
            The research topic string.
        enriched_claims:
            List of enriched claim dicts from ``query_knowledge_store_enriched()``.

        Returns
        -------
        ResearchBrief
        """
        now = _utcnow_iso()

        if not enriched_claims:
            return ResearchBrief(
                topic=topic,
                generated_at=now,
                sources_queried=0,
                sources_cited=0,
                overall_confidence="LOW",
                summary="Insufficient evidence: no claims found for this topic.",
                key_findings=[],
                contradictions=[],
                actionability={
                    "can_inform_strategy": False,
                    "target_track": "",
                    "suggested_next_step": "Ingest more research on this topic before drawing conclusions.",
                    "estimated_impact": "",
                },
                knowledge_gaps=["No evidence available -- ingestion required"],
                cited_sources=[],
            )

        # Sort by effective_score descending (tier_1 claims naturally score higher)
        sorted_claims = sorted(
            enriched_claims,
            key=lambda c: float(c.get("effective_score") or 0.0),
            reverse=True,
        )

        # Build CitedEvidence for all claims
        cited_map: dict[str, CitedEvidence] = {}
        for claim in sorted_claims:
            ev = _extract_cited_evidence(claim)
            claim_id = claim.get("id") or hashlib.md5(
                claim.get("claim_text", "").encode()
            ).hexdigest()[:8]
            cited_map[claim_id] = ev

        # Overall confidence
        overall_confidence = _compute_overall_confidence(sorted_claims)

        # Key findings: top N non-contradicted claims
        non_contradicted = [
            c for c in sorted_claims if not c.get("is_contradicted")
        ]
        key_findings: list[dict] = []
        for claim in non_contradicted[: self._MAX_KEY_FINDINGS]:
            claim_id = claim.get("id") or ""
            ev = cited_map.get(claim_id) or _extract_cited_evidence(claim)
            conf = float(claim.get("confidence") or 0.0)
            if conf >= 0.8:
                conf_tier = "HIGH"
            elif conf >= 0.5:
                conf_tier = "MEDIUM"
            else:
                conf_tier = "LOW"

            claim_text = claim.get("claim_text") or ""
            # Use the first sentence as the title (up to 80 chars)
            first_sentence = claim_text.split(".")[0].strip()
            title = first_sentence[:80] if first_sentence else claim_text[:80]

            key_findings.append({
                "title": title,
                "description": claim_text,
                "source": ev,
                "confidence_tier": conf_tier,
            })

        # Contradictions section: gather claims with is_contradicted=True
        contradictions: list[dict] = []
        seen_contra: set[str] = set()
        for claim in sorted_claims:
            if not claim.get("is_contradicted"):
                continue
            claim_text = claim.get("claim_text") or ""
            contradiction_summary: list[str] = claim.get("contradiction_summary") or []
            claim_id = claim.get("id") or ""

            for contra_text in contradiction_summary:
                pair_key = tuple(sorted([claim_text[:60], contra_text[:60]]))
                if pair_key in seen_contra:
                    continue
                seen_contra.add(pair_key)

                ev_a = cited_map.get(claim_id) or _extract_cited_evidence(claim)
                contradictions.append({
                    "claim_a": claim_text,
                    "claim_b": contra_text,
                    "sources": [ev_a],
                    "unresolved": True,
                })

        # Knowledge gaps: stale claims and sparse coverage
        knowledge_gaps: list[str] = []
        for claim in sorted_claims:
            if claim.get("staleness_note") in ("STALE", "AGING"):
                gap_text = (
                    f"Stale evidence ({claim.get('staleness_note')}): "
                    f"'{(claim.get('claim_text') or '')[:100]}' -- fresher data needed"
                )
                knowledge_gaps.append(gap_text)

        # Actionability: check if any claim references a strategy track
        can_inform = False
        target_track = ""
        for claim in sorted_claims:
            relevant, track = _detect_strategy_relevance(claim.get("claim_text") or "")
            if relevant:
                can_inform = True
                target_track = track
                break

        actionability: dict = {
            "can_inform_strategy": can_inform,
            "target_track": target_track,
            "suggested_next_step": (
                f"Review top {len(key_findings)} findings and assess fit for {target_track} track"
                if can_inform else "Explore broader context before applying to strategy tracks"
            ),
            "estimated_impact": "MEDIUM" if can_inform else "LOW",
        }

        # Summary: synthesize from top findings (deterministic, no LLM)
        if key_findings:
            top_texts = [f["description"] for f in key_findings[:3]]
            summary = " | ".join(t[:120] for t in top_texts)
        elif sorted_claims:
            # Only contradicted claims available
            summary = "Mixed evidence: all top claims are contradicted. Review contradictions section."
        else:
            summary = "Insufficient evidence."

        # Collect unique cited_sources
        unique_docs: dict[str, CitedEvidence] = {}
        for ev in cited_map.values():
            if ev.source_doc_id and ev.source_doc_id not in unique_docs:
                unique_docs[ev.source_doc_id] = ev
        cited_sources = list(unique_docs.values())

        return ResearchBrief(
            topic=topic,
            generated_at=now,
            sources_queried=len(enriched_claims),
            sources_cited=len(cited_sources),
            overall_confidence=overall_confidence,
            summary=summary,
            key_findings=key_findings,
            contradictions=contradictions,
            actionability=actionability,
            knowledge_gaps=knowledge_gaps,
            cited_sources=cited_sources,
        )

    def synthesize_precheck(self, idea: str, enriched_claims: list[dict]) -> EnhancedPrecheck:
        """Produce an EnhancedPrecheck from enriched claims for an idea.

        Filters claims by keyword relevance to the idea, then separates them
        into supporting and contradicting evidence to determine a
        GO/CAUTION/STOP recommendation.

        Parameters
        ----------
        idea:
            The idea or development hypothesis to check.
        enriched_claims:
            List of enriched claim dicts from ``query_knowledge_store_enriched()``.

        Returns
        -------
        EnhancedPrecheck
        """
        now = _utcnow_iso()
        precheck_id = hashlib.sha256(idea.encode("utf-8")).hexdigest()[:12]

        if not enriched_claims:
            return EnhancedPrecheck(
                recommendation="CAUTION",
                idea=idea,
                supporting=[],
                contradicting=[],
                risk_factors=["No evidence available -- manual review required"],
                past_failures=[],
                knowledge_gaps=["No relevant claims found for this idea"],
                validation_approach="Run a targeted ingestion sweep before committing to this idea.",
                timestamp=now,
                overall_confidence="LOW",
                stale_warning=False,
                evidence_gap="No relevant claims found in knowledge store",
                precheck_id=precheck_id,
            )

        # Filter claims by keyword relevance to idea (case-insensitive overlap)
        relevant_claims = [
            c for c in enriched_claims
            if _idea_relevance_score(idea, c.get("claim_text") or "") > 0.0
        ]

        # If relevance filtering yields nothing, use all claims (broad topic)
        if not relevant_claims:
            relevant_claims = enriched_claims

        # Separate supporting vs contradicting
        supporting_evs: list[CitedEvidence] = []
        contradicting_evs: list[CitedEvidence] = []

        for claim in relevant_claims:
            ev = _extract_cited_evidence(claim)
            is_contradicted = claim.get("is_contradicted", False)
            contradiction_summary = claim.get("contradiction_summary") or []
            confidence = float(claim.get("confidence") or 0.0)

            if is_contradicted or contradiction_summary:
                contradicting_evs.append(ev)
            elif confidence >= 0.6:
                supporting_evs.append(ev)
            # Low-confidence, non-contradicted claims are not strongly supporting

        # Staleness check
        all_stale = (
            len(relevant_claims) > 0
            and all(c.get("staleness_note") == "STALE" for c in relevant_claims)
        )

        # Overall confidence for precheck
        overall_confidence = _compute_overall_confidence(relevant_claims)

        # Recommendation logic
        n_sup = len(supporting_evs)
        n_con = len(contradicting_evs)

        if all_stale:
            overall_confidence = "LOW"
            recommendation = "CAUTION"
        elif n_con > 2 * n_sup:
            recommendation = "STOP"
        elif n_sup > 0 and n_con == 0 and not all_stale:
            recommendation = "GO"
        else:
            recommendation = "CAUTION"

        # Risk factors from contradicting evidence
        risk_factors = [ev.claim_text[:160] for ev in contradicting_evs[:3]]
        if not risk_factors:
            risk_factors = ["No contradicting evidence found -- evidence may be incomplete"]

        # Knowledge gaps
        knowledge_gaps: list[str] = []
        if len(relevant_claims) < 3:
            knowledge_gaps.append(
                f"Sparse evidence: only {len(relevant_claims)} relevant claim(s) found -- ingest more data"
            )
        for claim in relevant_claims:
            if claim.get("staleness_note") in ("STALE", "AGING"):
                knowledge_gaps.append(
                    f"Stale evidence ({claim.get('staleness_note')}): "
                    f"'{(claim.get('claim_text') or '')[:80]}'"
                )

        evidence_gap = ""
        if not supporting_evs and not contradicting_evs:
            evidence_gap = "No relevant claims with sufficient confidence found -- manual review recommended"

        return EnhancedPrecheck(
            recommendation=recommendation,
            idea=idea,
            supporting=supporting_evs,
            contradicting=contradicting_evs,
            risk_factors=risk_factors,
            past_failures=[],  # Populated in v2 via research partition query
            knowledge_gaps=knowledge_gaps,
            validation_approach=(
                "Paper trade for 7 days with simulated fills before committing capital."
                if recommendation == "GO"
                else "Resolve contradicting evidence and re-run precheck before proceeding."
            ),
            timestamp=now,
            overall_confidence=overall_confidence,
            stale_warning=all_stale,
            evidence_gap=evidence_gap,
            precheck_id=precheck_id,
        )


# ---------------------------------------------------------------------------
# Format functions
# ---------------------------------------------------------------------------

def format_research_brief(brief: ResearchBrief) -> str:
    """Produce full markdown for a ResearchBrief with all RIS_05 sections."""
    lines: list[str] = []

    # Header
    lines.append(f"# Research Brief: {brief.topic}")
    lines.append(f"**Generated:** {brief.generated_at}")
    lines.append(f"**Sources queried:** {brief.sources_queried}")
    lines.append(f"**Sources cited:** {brief.sources_cited}")
    lines.append(f"**Overall confidence:** {brief.overall_confidence}")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Summary
    lines.append("## Summary")
    lines.append("")
    lines.append(brief.summary)
    lines.append("")

    # Key Findings
    lines.append("## Key Findings")
    lines.append("")
    if brief.key_findings:
        for i, finding in enumerate(brief.key_findings, start=1):
            title = finding.get("title") or "(untitled)"
            description = finding.get("description") or ""
            source: Optional[CitedEvidence] = finding.get("source")
            conf_tier = finding.get("confidence_tier") or ""
            lines.append(f"{i}. **{title}** -- {description[:200]}")
            if source:
                lines.append(f"   - Source: {format_citation(source)}")
            if conf_tier:
                lines.append(f"   - Confidence: {conf_tier}")
            lines.append("")
    else:
        lines.append("(No key findings -- insufficient evidence)")
        lines.append("")

    # Contradictions & Unresolved Questions
    lines.append("## Contradictions & Unresolved Questions")
    lines.append("")
    if brief.contradictions:
        for c in brief.contradictions:
            claim_a = c.get("claim_a") or ""
            claim_b = c.get("claim_b") or ""
            sources: list[CitedEvidence] = c.get("sources") or []
            source_str = "; ".join(format_citation(s) for s in sources) if sources else "(no source)"
            lines.append(f"- **Claim A:** {claim_a[:120]}")
            lines.append(f"  **Claim B:** {claim_b[:120]}")
            lines.append(f"  **Sources:** {source_str}")
            if c.get("unresolved"):
                lines.append("  *(Unresolved contradiction)*")
            lines.append("")
    else:
        lines.append("(No contradictions detected)")
        lines.append("")

    # Actionability Assessment
    lines.append("## Actionability Assessment")
    lines.append("")
    act = brief.actionability
    can_inform = act.get("can_inform_strategy", False)
    lines.append(f"- **Can this inform a current strategy track?** {'YES' if can_inform else 'NO'}")
    if can_inform:
        target = act.get("target_track") or ""
        lines.append(f"  - Track: {target}")
    next_step = act.get("suggested_next_step") or ""
    impact = act.get("estimated_impact") or ""
    if next_step:
        lines.append(f"- **Suggested next step:** {next_step}")
    if impact:
        lines.append(f"- **Estimated impact:** {impact}")
    lines.append("")

    # Knowledge Gaps
    lines.append("## Knowledge Gaps")
    lines.append("")
    if brief.knowledge_gaps:
        for gap in brief.knowledge_gaps:
            lines.append(f"- {gap}")
        lines.append("")
    else:
        lines.append("(No significant knowledge gaps identified)")
        lines.append("")

    # Sources Cited
    lines.append("## Sources Cited")
    lines.append("")
    if brief.cited_sources:
        lines.append("| # | Doc ID | Title | Type | Tier | Freshness |")
        lines.append("|---|--------|-------|------|------|-----------|")
        for i, ev in enumerate(brief.cited_sources, start=1):
            title = (ev.source_title or "(untitled)")[:40]
            freshness = ev.freshness_note or "fresh"
            lines.append(
                f"| {i} | {ev.source_doc_id} | {title} | {ev.source_type} | {ev.trust_tier} | {freshness} |"
            )
        lines.append("")
    else:
        lines.append("(No sources cited)")
        lines.append("")

    return "\n".join(lines)


def format_enhanced_precheck(precheck: EnhancedPrecheck) -> str:
    """Produce full markdown for an EnhancedPrecheck with GO/CAUTION/STOP sections."""
    lines: list[str] = []

    # Recommendation badge
    badge_map = {"GO": "GO", "CAUTION": "CAUTION", "STOP": "STOP"}
    badge = badge_map.get(precheck.recommendation, precheck.recommendation)

    lines.append(f"# Pre-Development Check: {precheck.idea}")
    lines.append(f"**Generated:** {precheck.timestamp}")
    lines.append(f"**Overall confidence:** {precheck.overall_confidence}")
    lines.append("")
    lines.append(f"## Recommendation: {badge}")
    lines.append("")

    if precheck.stale_warning:
        lines.append("> WARNING: All evidence is stale. Recommendation confidence is reduced.")
        lines.append("")

    if precheck.evidence_gap:
        lines.append(f"> EVIDENCE GAP: {precheck.evidence_gap}")
        lines.append("")

    # Supporting evidence
    lines.append("## Evidence")
    lines.append("")
    lines.append("### Supporting evidence (why this might work)")
    lines.append("")
    if precheck.supporting:
        for ev in precheck.supporting:
            citation = format_citation(ev)
            lines.append(f"- {ev.claim_text[:160]} {citation}")
        lines.append("")
    else:
        lines.append("(No supporting evidence found)")
        lines.append("")

    # Contradicting evidence
    lines.append("### Contradicting evidence (why this might fail)")
    lines.append("")
    if precheck.contradicting:
        for ev in precheck.contradicting:
            citation = format_citation(ev)
            lines.append(f"- {ev.claim_text[:160]} {citation}")
        lines.append("")
    else:
        lines.append("(No contradicting evidence found)")
        lines.append("")

    # Past failures
    if precheck.past_failures:
        lines.append("### Past failures")
        lines.append("")
        for pf in precheck.past_failures:
            lines.append(f"- {pf}")
        lines.append("")

    # Risk assessment
    lines.append("## Risk Assessment")
    lines.append("")
    for rf in precheck.risk_factors:
        lines.append(f"- {rf}")
    lines.append("")

    # Knowledge gaps
    if precheck.knowledge_gaps:
        lines.append("## Knowledge Gaps")
        lines.append("")
        for kg in precheck.knowledge_gaps:
            lines.append(f"- {kg}")
        lines.append("")

    # Validation approach
    if precheck.validation_approach:
        lines.append("## If proceeding, recommended validation approach")
        lines.append("")
        lines.append(precheck.validation_approach)
        lines.append("")

    return "\n".join(lines)
