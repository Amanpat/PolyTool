"""RIS v1 evaluation gate — 4-dimension scoring rubric and prompt construction.

Provides the scoring prompt builder, LLM response parser, and the
score_document() convenience function.

Phase 5 additions (backward compatible):
- SCORING_PROMPT_TEMPLATE_ID: constant identifying the active prompt template.
- score_document_with_metadata(): returns (ScoringResult, raw_output, prompt_hash)
  for replay-grade auditability.
"""

from __future__ import annotations

import hashlib
import json
from typing import TYPE_CHECKING, Tuple

from packages.research.evaluation.types import (
    EvalDocument,
    ScoringResult,
    SOURCE_FAMILIES,
    SOURCE_FAMILY_GUIDANCE,
)

if TYPE_CHECKING:
    from packages.research.evaluation.providers import EvalProvider

# Identifier for the current scoring prompt template.
# Increment this (e.g., "scoring_v2") when the prompt rubric changes substantially
# to allow detection of evaluation drift across artifact records.
SCORING_PROMPT_TEMPLATE_ID = "scoring_v1"


def build_scoring_prompt(doc: EvalDocument) -> str:
    """Construct the full evaluation prompt for a document.

    Includes:
    - Domain context
    - Source-family credibility guidance (based on doc.source_type)
    - 4-dimension scoring rubric (1-5 scale)
    - Epistemic type tagging instructions
    - Expected JSON output format
    """
    family = SOURCE_FAMILIES.get(doc.source_type, "manual")
    guidance = SOURCE_FAMILY_GUIDANCE.get(family, SOURCE_FAMILY_GUIDANCE["manual"])

    prompt_parts = [
        "You are a research evaluator for a prediction market trading system called PolyTool.",
        "",
        "Your task: evaluate whether this document should be added to our knowledge base.",
        "",
        "DOMAIN CONTEXT:",
        "PolyTool is a Polymarket-first research, simulation, and execution system. Current",
        "strategy tracks: (1) Market Maker (Avellaneda-Stoikov style), (2) Crypto Pair Bot",
        "(directional momentum on BTC/ETH/SOL markets), (3) Sports Directional Model.",
        "We need research on: prediction market microstructure, market making strategies,",
        "quantitative trading, crypto pair dynamics, and sports probability modeling.",
        "",
        "SOURCE FAMILY GUIDANCE:",
        f"Source type: {doc.source_type} (family: {family})",
        guidance,
        "",
        "SCORING RUBRIC (1-5 per dimension, total /20):",
        "",
        "Dimension 1: Relevance",
        "  5 = Directly about Polymarket, prediction market microstructure, or a strategy type we are building",
        "  4 = About general market making, quantitative trading, or prediction markets on other platforms",
        "  3 = Adjacent topic (DeFi trading, options MM, sports analytics) with transferable insights",
        "  2 = Tangentially related (general ML, general finance, broad crypto)",
        "  1 = Not relevant to our domain",
        "",
        "Dimension 2: Novelty",
        "  5 = Entirely new strategy concept, data source, or empirical finding",
        "  4 = New angle on a known concept, or significant new data",
        "  3 = Moderate new information, some overlap with existing knowledge",
        "  2 = Mostly redundant, adds minor detail",
        "  1 = Already covered comprehensively in the knowledge base",
        "",
        "Dimension 3: Actionability",
        "  5 = Contains specific parameters, thresholds, or implementations directly testable",
        "  4 = Contains a testable hypothesis or clear strategic recommendation",
        "  3 = Useful context that informs strategy design indirectly",
        "  2 = Interesting background but no clear path to action",
        "  1 = Pure theory with no practical application",
        "",
        "Dimension 4: Credibility",
        "  5 = Peer-reviewed paper, published dataset with methodology, verified on-chain analysis",
        "  4 = Experienced practitioner with evidence, well-reasoned post with data",
        "  3 = Community member with some evidence, anecdotal but plausible",
        "  2 = Unverified claim, single data point, promotional content",
        "  1 = Known unreliable, contradicted by data, spam",
        "",
        "GATE THRESHOLDS:",
        "  ACCEPT: total >= 12/20",
        "  REVIEW: 8-11/20",
        "  REJECT: < 8/20",
        "",
        "EPISTEMIC TYPE TAGGING (pick one):",
        "  EMPIRICAL    = contains verifiable data or measured results",
        "  THEORETICAL  = contains a model or framework without empirical validation",
        "  ANECDOTAL    = personal experience or observation",
        "  SPECULATIVE  = prediction or hypothesis without evidence",
        "",
        "INSTRUCTIONS:",
        "1. Score each dimension 1-5 with a one-sentence rationale.",
        "2. Compute total = sum of all 4 dimension scores.",
        "3. Tag the epistemic type: EMPIRICAL | THEORETICAL | ANECDOTAL | SPECULATIVE",
        "4. Write a 2-3 sentence summary of the document's key contribution.",
        "5. List 1-3 key findings as bullet points.",
        "6. Set gate: ACCEPT (>=12), REVIEW (8-11), REJECT (<8).",
        "7. Evaluate substance, not grammar. Typos and informal language do not reduce scores.",
        "",
        "DOCUMENT TO EVALUATE:",
        f"Source type: {doc.source_type}",
        f"Title: {doc.title}",
        f"Author: {doc.author}",
        f"Date: {doc.source_publish_date or 'unknown'}",
        f"Text:",
        doc.body,
        "",
        "OUTPUT FORMAT (JSON only, no markdown, no explanation):",
        json.dumps({
            "relevance": {"score": "<1-5>", "rationale": "<one sentence>"},
            "novelty": {"score": "<1-5>", "rationale": "<one sentence>"},
            "actionability": {"score": "<1-5>", "rationale": "<one sentence>"},
            "credibility": {"score": "<1-5>", "rationale": "<one sentence>"},
            "total": "<sum of 4 scores>",
            "epistemic_type": "EMPIRICAL|THEORETICAL|ANECDOTAL|SPECULATIVE",
            "summary": "<2-3 sentences>",
            "key_findings": ["<finding 1>", "<finding 2>"],
            "eval_model": "<model name>",
        }, indent=2),
    ]

    return "\n".join(prompt_parts)


def parse_scoring_response(raw_json: str, model_name: str) -> ScoringResult:
    """Parse an LLM JSON response into a ScoringResult.

    Handles missing fields gracefully — defaults all missing dimension scores
    to 1. Computes total from individual dimensions if not present.

    Args:
        raw_json: Raw JSON string from the LLM provider.
        model_name: Name of the model used for scoring (set as eval_model).

    Returns:
        ScoringResult with parsed or default values.
    """
    try:
        data = json.loads(raw_json)
        if not isinstance(data, dict):
            raise ValueError("Expected JSON object")
    except (json.JSONDecodeError, ValueError):
        # Return safe defaults on parse failure
        return ScoringResult(
            relevance=1, novelty=1, actionability=1, credibility=1,
            total=4,
            epistemic_type="UNKNOWN",
            summary="Parse error — could not evaluate document.",
            key_findings=[],
            eval_model=model_name,
        )

    def _extract_score(key: str) -> int:
        val = data.get(key, {})
        if isinstance(val, dict):
            score = val.get("score", 1)
        elif isinstance(val, (int, float)):
            score = int(val)
        else:
            score = 1
        try:
            return max(1, min(5, int(score)))
        except (TypeError, ValueError):
            return 1

    relevance = _extract_score("relevance")
    novelty = _extract_score("novelty")
    actionability = _extract_score("actionability")
    credibility = _extract_score("credibility")

    # Total from data if present, else compute from dimensions
    if "total" in data:
        try:
            total = max(4, min(20, int(data["total"])))
        except (TypeError, ValueError):
            total = relevance + novelty + actionability + credibility
    else:
        total = relevance + novelty + actionability + credibility

    epistemic_type = str(data.get("epistemic_type", "UNKNOWN")).upper()
    if epistemic_type not in ("EMPIRICAL", "THEORETICAL", "ANECDOTAL", "SPECULATIVE"):
        epistemic_type = "UNKNOWN"

    summary = str(data.get("summary", ""))
    key_findings_raw = data.get("key_findings", [])
    if isinstance(key_findings_raw, list):
        key_findings = [str(f) for f in key_findings_raw]
    else:
        key_findings = []

    # Use eval_model from response if present, else use passed model_name
    eval_model = str(data.get("eval_model", model_name)) or model_name

    return ScoringResult(
        relevance=relevance,
        novelty=novelty,
        actionability=actionability,
        credibility=credibility,
        total=total,
        epistemic_type=epistemic_type,
        summary=summary,
        key_findings=key_findings,
        eval_model=eval_model,
    )


def score_document(doc: EvalDocument, provider: "EvalProvider") -> ScoringResult:
    """Score a document using the given provider.

    Builds the scoring prompt, calls provider.score(), and parses the result.

    Args:
        doc: The document to evaluate.
        provider: The LLM provider to use for scoring.

    Returns:
        ScoringResult with dimension scores and gate decision.
    """
    prompt = build_scoring_prompt(doc)
    raw_json = provider.score(doc, prompt)
    return parse_scoring_response(raw_json, provider.name)


def score_document_with_metadata(
    doc: EvalDocument, provider: "EvalProvider"
) -> Tuple[ScoringResult, str, str]:
    """Score a document and return replay-grade metadata alongside the result.

    Same scoring logic as score_document() but also returns the raw provider
    output and a prompt hash for auditability. Used by DocumentEvaluator when
    persisting EvalArtifacts with Phase 5 provider_event metadata.

    Args:
        doc: The document to evaluate.
        provider: The LLM provider to use for scoring.

    Returns:
        Tuple of (ScoringResult, raw_output, prompt_hash) where:
        - ScoringResult: parsed scoring dimensions and gate decision.
        - raw_output: the raw string returned by provider.score().
        - prompt_hash: first 12 hex chars of sha256(prompt_text), used as
          prompt_template_version in ProviderEvent for drift detection.
    """
    prompt = build_scoring_prompt(doc)
    prompt_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:12]
    raw_output = provider.score(doc, prompt)
    result = parse_scoring_response(raw_output, provider.name)
    return result, raw_output, prompt_hash
