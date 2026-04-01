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
from typing import Optional


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _iso_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat()


def _stable_id(text: str) -> str:
    """Deterministic 12-char ID from text (SHA256-based)."""
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return digest[:12]


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


def check_stale_evidence(result: PrecheckResult) -> PrecheckResult:
    """Check whether the evidence references are stale and set stale_warning.

    Currently a stub. Returns result unchanged.

    TODO: Wire to RAG query to check document dates. If all cited sources are
    pre-2023 or no sources found, set stale_warning=True.
    """
    return result


def find_contradictions(idea: str) -> list:
    """Find documents that may contradict the idea using semantic search.

    Currently a stub. Returns empty list.

    TODO: Wire to packages/polymarket/rag/query.py query_index() to find
    documents that may contradict the idea. Use semantic similarity search,
    then LLM to classify support vs contradiction.
    """
    return []


def run_precheck(
    idea: str,
    provider_name: str = "manual",
    ledger_path: Optional[Path] = None,
    **kwargs,
) -> PrecheckResult:
    """Run a precheck on an idea and return GO/CAUTION/STOP recommendation.

    Steps:
    1. Build precheck prompt from idea text.
    2. Get provider (default: ManualProvider).
    3. Call provider.score() using a synthetic EvalDocument.
    4. Parse response into PrecheckResult (fall back to CAUTION on ManualProvider).
    5. Check stale evidence (stub).
    6. Append to ledger if ledger_path is not None.
    7. Return result.

    Args:
        idea: The idea or concept to precheck.
        provider_name: Provider to use for evaluation (default: "manual").
        ledger_path: Path to JSONL ledger. Pass None to skip ledger write.
        **kwargs: Passed to get_provider().

    Returns:
        PrecheckResult with GO/CAUTION/STOP recommendation.
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

    # If ManualProvider gave us a valid evaluation JSON but no precheck fields,
    # the parse will return CAUTION with manual fallback message — that is correct.

    # Stale evidence check (stub for now)
    result = check_stale_evidence(result)

    # Append to ledger unless explicitly skipped
    if ledger_path is not None:
        append_precheck(result, ledger_path=ledger_path)

    return result
