"""RIS v1 synthesis — precheck runner.

Provides GO/CAUTION/STOP recommendations before starting development work,
including contradiction detection and stale-evidence warning interfaces.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from packages.polymarket.rag.knowledge_store import KnowledgeStore


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _iso_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat()


def _stable_id(text: str) -> str:
    """Deterministic 12-char ID from text (SHA256-based)."""
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return digest[:12]


# Mapping from recommendation to reason_code
_REASON_CODE_MAP = {
    "GO": "STRONG_SUPPORT",
    "CAUTION": "MIXED_EVIDENCE",
    "STOP": "FUNDAMENTAL_BLOCKER",
}


@dataclass
class PrecheckResult:
    """Result of a pre-development check on an idea or hypothesis."""
    recommendation: str           # GO | CAUTION | STOP
    idea: str
    supporting_evidence: list     # list[str]
    contradicting_evidence: list  # list[str]
    risk_factors: list            # list[str]
    timestamp: str
    provider_used: str
    stale_warning: bool = False
    raw_response: str = ""
    # Enriched fields (v1 schema)
    precheck_id: str = ""
    reason_code: str = ""
    evidence_gap: str = ""
    review_horizon: str = ""


def build_precheck_prompt(idea: str) -> str:
    """Construct the precheck prompt for evaluating an idea.

    Instructs the evaluator to identify both supporting and contradicting
    evidence and list risk factors explicitly.
    """
    prompt_parts = [
        "You are a research evaluator for PolyTool, a Polymarket prediction market",
        "trading system. Your task is to evaluate whether the following idea is worth",
        "pursuing as a research or development initiative.",
        "",
        "INSTRUCTIONS:",
        "1. Evaluate the idea against prediction market domain knowledge.",
        "2. Identify supporting evidence (data, precedent, theory that supports the idea).",
        "3. Identify contradicting evidence — things that argue AGAINST or undermine the idea.",
        "   You MUST include contradicting evidence even for promising ideas.",
        "4. List risk factors that could prevent success.",
        "   You MUST identify at least one risk factor even for promising ideas.",
        "5. Provide a recommendation: GO, CAUTION, or STOP.",
        "   - GO: Strong evidence for, low risk, actionable next step is clear",
        "   - CAUTION: Mixed evidence or significant uncertainty; proceed carefully",
        "   - STOP: Evidence against outweighs support, or fundamental blocker exists",
        "",
        "DOMAIN CONTEXT:",
        "PolyTool focuses on Polymarket binary prediction markets. Key strategies:",
        "- Market Maker (Avellaneda-Stoikov style on binary markets)",
        "- Crypto Pair Bot (directional momentum, BTC/ETH/SOL 5m/15m markets)",
        "- Sports Directional Model (probability modeling)",
        "Known constraints: Polymarket uses Coinbase CLOB price feed, Chainlink oracle for",
        "settlement, EU VPS recommended, no dedicated research infrastructure yet.",
        "",
        f"IDEA TO EVALUATE:",
        idea,
        "",
        "OUTPUT FORMAT (JSON only, no markdown, no explanation):",
        json.dumps({
            "recommendation": "GO|CAUTION|STOP",
            "supporting_evidence": ["<evidence 1>", "<evidence 2>"],
            "contradicting_evidence": ["<contradiction 1>"],
            "risk_factors": ["<risk 1>", "<risk 2>"],
        }, indent=2),
    ]
    return "\n".join(prompt_parts)


def parse_precheck_response(raw_json: str, idea: str, model_name: str) -> PrecheckResult:
    """Parse LLM JSON response into a PrecheckResult.

    Falls back to CAUTION with manual-mode messages if parsing fails or
    the required fields are missing.

    Args:
        raw_json: Raw JSON string from the LLM provider.
        idea: The original idea text.
        model_name: Provider identifier for provenance tracking.

    Returns:
        PrecheckResult with recommendation and evidence lists.
    """
    now = _iso_utc(_utcnow())

    try:
        data = json.loads(raw_json)
        if not isinstance(data, dict):
            raise ValueError("Expected JSON object")
    except (json.JSONDecodeError, ValueError):
        # Fallback for parse failure
        return PrecheckResult(
            recommendation="CAUTION",
            idea=idea,
            supporting_evidence=["Manual evaluation — no LLM analysis performed."],
            contradicting_evidence=[],
            risk_factors=["No automated analysis available — manual review recommended."],
            stale_warning=False,
            timestamp=now,
            provider_used=model_name,
            raw_response=raw_json,
        )

    rec = str(data.get("recommendation", "")).upper().strip()
    if rec not in ("GO", "CAUTION", "STOP"):
        rec = "CAUTION"

    def _str_list(key: str) -> list:
        val = data.get(key, [])
        if isinstance(val, list):
            return [str(v) for v in val if v]
        return []

    supporting = _str_list("supporting_evidence")
    contradicting = _str_list("contradicting_evidence")
    risks = _str_list("risk_factors")

    return PrecheckResult(
        recommendation=rec,
        idea=idea,
        supporting_evidence=supporting,
        contradicting_evidence=contradicting,
        risk_factors=risks,
        stale_warning=False,
        timestamp=now,
        provider_used=model_name,
        raw_response=raw_json,
    )


def find_contradictions(
    idea: str,
    knowledge_store: Optional["KnowledgeStore"] = None,
) -> list:
    """Find claims that may contradict the idea using KnowledgeStore relations.

    If knowledge_store is None, returns [] (backward compat — no KS dependency).

    When a knowledge_store is provided: queries all active claims and returns
    the claim_text of any claim that has at least one CONTRADICTS relation
    (either as source or target). This is intentionally broad — the idea text
    is NOT used for semantic filtering (that requires embeddings, out of scope).
    The precheck prompt asks the LLM to evaluate relevance.

    Args:
        idea: The idea text being evaluated. Not used for filtering currently.
        knowledge_store: Optional KnowledgeStore instance. Pass None to use
            the backward-compatible stub behavior (returns []).

    Returns:
        list[str]: Contradicting claim texts. Empty list if no KS or no contradictions.
    """
    if knowledge_store is None:
        return []

    ks = knowledge_store

    # Get all active claims (no freshness needed — we want all candidates)
    claims = ks.query_claims(apply_freshness=False)

    contradicting_texts: list[str] = []
    seen: set[str] = set()

    for claim in claims:
        claim_id = claim["id"]
        claim_text = claim["claim_text"]
        # Check if this claim has any CONTRADICTS relation (as source or target)
        relations = ks.get_relations(claim_id, relation_type="CONTRADICTS")
        if relations and claim_text not in seen:
            contradicting_texts.append(claim_text)
            seen.add(claim_text)

    return contradicting_texts


def check_stale_evidence(
    result: PrecheckResult,
    knowledge_store: Optional["KnowledgeStore"] = None,
) -> PrecheckResult:
    """Check whether the evidence references are stale and set stale_warning.

    If knowledge_store is None, returns result unchanged (backward compat).

    When a knowledge_store is provided: queries all source_documents and
    computes freshness_modifier for each. If ALL documents have
    freshness_modifier < 0.5, creates a new PrecheckResult with
    stale_warning=True. If no source documents exist, returns result unchanged.

    Args:
        result: The PrecheckResult to check.
        knowledge_store: Optional KnowledgeStore instance. Pass None to use
            the backward-compatible passthrough behavior.

    Returns:
        PrecheckResult with stale_warning set appropriately.
    """
    if knowledge_store is None:
        return result

    from packages.polymarket.rag.freshness import compute_freshness_modifier

    ks = knowledge_store

    # Query all source documents
    rows = ks._conn.execute(
        "SELECT source_family, published_at FROM source_documents"
    ).fetchall()

    if not rows:
        # No source documents — no data = no penalty
        return result

    # Check if ALL documents are stale (freshness_modifier < 0.5)
    all_stale = True
    for row in rows:
        source_family = row[0] or "unknown"
        published_at_str = row[1]

        published_at: Optional[datetime] = None
        if published_at_str:
            try:
                published_at = datetime.fromisoformat(published_at_str)
            except ValueError:
                published_at = None

        modifier = compute_freshness_modifier(source_family, published_at)
        if modifier >= 0.5:
            all_stale = False
            break

    if all_stale:
        # Return a new PrecheckResult with stale_warning=True
        return PrecheckResult(
            recommendation=result.recommendation,
            idea=result.idea,
            supporting_evidence=result.supporting_evidence,
            contradicting_evidence=result.contradicting_evidence,
            risk_factors=result.risk_factors,
            timestamp=result.timestamp,
            provider_used=result.provider_used,
            stale_warning=True,
            raw_response=result.raw_response,
            precheck_id=result.precheck_id,
            reason_code=result.reason_code,
            evidence_gap=result.evidence_gap,
            review_horizon=result.review_horizon,
        )

    return result


def run_precheck(
    idea: str,
    provider_name: str = "manual",
    ledger_path: Optional[Path] = None,
    knowledge_store: Optional["KnowledgeStore"] = None,
    **kwargs,
) -> PrecheckResult:
    """Run a precheck on an idea and return GO/CAUTION/STOP recommendation.

    Steps:
    1. Build precheck prompt from idea text.
    2. Get provider (default: ManualProvider).
    3. Call provider.score() using a synthetic EvalDocument.
    4. Parse response into PrecheckResult (fall back to CAUTION on ManualProvider).
    5. Merge contradictions from KnowledgeStore (if provided).
    6. Check stale evidence using KnowledgeStore (if provided).
    7. Populate enriched fields: precheck_id, reason_code, evidence_gap, review_horizon.
    8. Append to ledger if ledger_path is not None.
    9. Return result.

    Args:
        idea: The idea or concept to precheck.
        provider_name: Provider to use for evaluation (default: "manual").
        ledger_path: Path to JSONL ledger. Pass None to skip ledger write.
        knowledge_store: Optional KnowledgeStore for contradiction detection
            and stale evidence checking. Pass None to use stub behavior.
        **kwargs: Passed to get_provider().

    Returns:
        PrecheckResult with GO/CAUTION/STOP recommendation and enriched fields.
    """
    from packages.research.evaluation.types import EvalDocument
    from packages.research.evaluation.providers import get_provider
    from packages.research.synthesis.precheck_ledger import append_precheck

    prompt = build_precheck_prompt(idea)
    provider = get_provider(provider_name, **kwargs)

    # Use a synthetic EvalDocument as the vehicle for provider.score()
    doc_id = f"precheck_{_stable_id(idea)}"
    synthetic_doc = EvalDocument(
        doc_id=doc_id,
        title="Precheck: " + idea[:80],
        author="operator",
        source_type="manual",
        source_url="",
        source_publish_date=None,
        body=idea,
        metadata={"precheck": True},
    )

    try:
        raw_response = provider.score(synthetic_doc, prompt)
    except Exception:
        raw_response = "{}"

    # Parse the precheck-specific JSON response.
    # ManualProvider returns evaluation JSON (not precheck format), so
    # parse_precheck_response will fall through to the CAUTION default or
    # return CAUTION with empty evidence lists. In either case, inject
    # manual-mode fallback messages when no evidence fields are populated.
    result = parse_precheck_response(raw_response, idea, provider.name)

    # If all evidence lists are empty (ManualProvider case), inject fallback messages
    if (not result.supporting_evidence and
            not result.contradicting_evidence and
            not result.risk_factors):
        result = PrecheckResult(
            recommendation="CAUTION",
            idea=idea,
            supporting_evidence=["Manual evaluation — no LLM analysis performed."],
            contradicting_evidence=[],
            risk_factors=["No automated analysis available — manual review recommended."],
            stale_warning=False,
            timestamp=result.timestamp,
            provider_used=provider.name,
            raw_response=raw_response,
        )

    # Merge contradictions from KnowledgeStore (if provided)
    ks_contradictions = find_contradictions(idea, knowledge_store=knowledge_store)
    if ks_contradictions:
        # Append and deduplicate (preserve order)
        existing = set(result.contradicting_evidence)
        merged = list(result.contradicting_evidence)
        for c in ks_contradictions:
            if c not in existing:
                merged.append(c)
                existing.add(c)
        result = PrecheckResult(
            recommendation=result.recommendation,
            idea=result.idea,
            supporting_evidence=result.supporting_evidence,
            contradicting_evidence=merged,
            risk_factors=result.risk_factors,
            timestamp=result.timestamp,
            provider_used=result.provider_used,
            stale_warning=result.stale_warning,
            raw_response=result.raw_response,
        )

    # Check stale evidence using KnowledgeStore (if provided)
    result = check_stale_evidence(result, knowledge_store=knowledge_store)

    # Populate enriched fields
    precheck_id = _stable_id(idea)
    reason_code = _REASON_CODE_MAP.get(result.recommendation, "MIXED_EVIDENCE")

    # evidence_gap: set when contradicting_evidence is empty and recommendation != GO
    if not result.contradicting_evidence and result.recommendation != "GO":
        evidence_gap = (
            "No contradicting evidence found -- manual review recommended"
        )
    else:
        evidence_gap = ""

    # review_horizon: based on recommendation severity
    _review_horizon_map = {
        "CAUTION": "7d",
        "STOP": "30d",
        "GO": "",
    }
    review_horizon = _review_horizon_map.get(result.recommendation, "")

    result = PrecheckResult(
        recommendation=result.recommendation,
        idea=result.idea,
        supporting_evidence=result.supporting_evidence,
        contradicting_evidence=result.contradicting_evidence,
        risk_factors=result.risk_factors,
        timestamp=result.timestamp,
        provider_used=result.provider_used,
        stale_warning=result.stale_warning,
        raw_response=result.raw_response,
        precheck_id=precheck_id,
        reason_code=reason_code,
        evidence_gap=evidence_gap,
        review_horizon=review_horizon,
    )

    # Append to ledger unless explicitly skipped
    if ledger_path is not None:
        append_precheck(result, ledger_path=ledger_path)

    return result
