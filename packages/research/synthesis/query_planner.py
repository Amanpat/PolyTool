"""RIS v1 synthesis — query planner module.

Converts a research topic string into a set of diverse retrieval queries using
template-based decomposition (deterministic) or LLM expansion (via provider).

Usage:
    from packages.research.synthesis.query_planner import plan_queries, QueryPlan

    # Deterministic (default)
    qp = plan_queries("crypto pair bot profitability on Polymarket")

    # LLM-expanded (requires Ollama running)
    qp = plan_queries("prediction market strategies", provider_name="ollama")
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Optional

from packages.research.evaluation.providers import get_provider
from packages.research.evaluation.types import EvalDocument


# ---------------------------------------------------------------------------
# Angle prefixes for deterministic query decomposition
# ---------------------------------------------------------------------------

ANGLE_PREFIXES: list[str] = [
    "evidence for",
    "risks of",
    "alternatives to",
    "recent developments in",
    "key assumptions behind",
]

_STEP_BACK_TEMPLATE = "What broader factors affect {topic_summary}?"


# ---------------------------------------------------------------------------
# QueryPlan dataclass
# ---------------------------------------------------------------------------


@dataclass
class QueryPlan:
    """Result of query planning for a research topic.

    Fields:
        topic: The original research topic string.
        queries: List of diverse retrieval queries generated from the topic.
        step_back_query: Optional broader contextual query for step-back prompting.
        provider_used: Provider identifier string ("manual", "ollama", etc.).
        was_fallback: True if deterministic fallback was triggered (LLM unavailable
            or returned unparseable output). False for intended manual mode.
    """
    topic: str
    queries: list[str]
    step_back_query: Optional[str]
    provider_used: str
    was_fallback: bool


# ---------------------------------------------------------------------------
# Deterministic helpers
# ---------------------------------------------------------------------------


def _deterministic_queries(topic: str, include_step_back: bool, max_queries: int) -> QueryPlan:
    """Generate deterministic template-based queries for the given topic.

    Combines topic with ANGLE_PREFIXES to produce diverse queries.
    Clamped to max_queries.

    Args:
        topic: The research topic string.
        include_step_back: If True, include a broader step-back query.
        max_queries: Maximum number of queries to return (not counting step-back).

    Returns:
        QueryPlan with was_fallback=False (manual is the intended mode).
    """
    queries: list[str] = []
    for prefix in ANGLE_PREFIXES:
        if len(queries) >= max_queries:
            break
        queries.append(f"{prefix} {topic}" if topic else prefix)

    step_back: Optional[str] = None
    if include_step_back:
        # Produce a broader contextual step-back query
        topic_summary = topic[:80] if topic else "this topic"
        step_back = _STEP_BACK_TEMPLATE.format(topic_summary=topic_summary)

    return QueryPlan(
        topic=topic,
        queries=queries,
        step_back_query=step_back,
        provider_used="manual",
        was_fallback=False,
    )


def _build_planner_prompt(topic: str, include_step_back: bool) -> str:
    """Build an LLM prompt requesting diverse retrieval queries as JSON.

    Args:
        topic: The research topic string.
        include_step_back: Whether to request a step-back query.

    Returns:
        Prompt string instructing the LLM to return JSON with a "queries" array.
    """
    step_back_instruction = ""
    step_back_field = '    "step_back_query": null'
    if include_step_back:
        step_back_instruction = (
            '\n5. Provide one "step_back_query": a broader contextual question that'
            "\n   places the specific topic in a larger domain context."
        )
        step_back_field = '    "step_back_query": "<broader question>"'

    example_json = json.dumps(
        {
            "queries": [
                "<query 1>",
                "<query 2>",
                "<query 3>",
            ],
            "step_back_query": None,
        },
        indent=2,
    )

    return "\n".join(
        [
            "You are a research query planner for PolyTool, a Polymarket prediction market",
            "research system. Generate diverse retrieval queries for the following topic.",
            "",
            "INSTRUCTIONS:",
            "1. Generate 3-5 retrieval queries that approach the topic from different angles.",
            "2. Each query should be specific and retrieval-focused (suitable for a semantic search).",
            "3. Cover perspectives such as: empirical evidence, risks, alternatives, recent",
            "   developments, underlying assumptions, and practical implementation.",
            "4. Do NOT repeat the topic verbatim — rephrase to maximize retrieval diversity.",
            step_back_instruction,
            "",
            f"TOPIC: {topic}",
            "",
            "OUTPUT FORMAT (JSON only, no markdown, no explanation):",
            example_json,
        ]
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def plan_queries(
    topic: str,
    provider_name: str = "manual",
    include_step_back: bool = False,
    max_queries: int = 5,
    **kwargs,
) -> QueryPlan:
    """Generate diverse retrieval queries for a research topic.

    Deterministic mode (provider_name="manual"):
        Returns template-based queries using ANGLE_PREFIXES. No LLM required.
        was_fallback is False (manual is the intended path, not a fallback).

    LLM mode (provider_name="ollama" etc.):
        Sends a prompt to the provider requesting a JSON array of queries.
        Falls back to deterministic mode if the response is unparseable or
        missing the "queries" key (was_fallback=True).

    Args:
        topic: The research topic to plan queries for.
        provider_name: Provider to use. Default "manual" for deterministic mode.
        include_step_back: If True, include a broader step-back query.
        max_queries: Maximum number of primary queries to return.
        **kwargs: Passed to get_provider() (e.g., model="llama3" for OllamaProvider).

    Returns:
        QueryPlan with topic, queries, step_back_query, provider_used, was_fallback.
    """
    if provider_name == "manual":
        return _deterministic_queries(topic, include_step_back, max_queries)

    # LLM path
    provider = get_provider(provider_name, **kwargs)

    prompt = _build_planner_prompt(topic, include_step_back)
    doc_id = f"planner_{abs(hash(topic))}"
    synthetic_doc = EvalDocument(
        doc_id=doc_id,
        title="Query planner: " + topic[:80],
        author="operator",
        source_type="manual",
        source_url="",
        source_publish_date=None,
        body=topic,
        metadata={"query_planning": True},
    )

    try:
        raw_response = provider.score(synthetic_doc, prompt)
    except Exception:
        raw_response = "{}"

    # Parse LLM response
    try:
        data = json.loads(raw_response)
        if not isinstance(data, dict):
            raise ValueError("Expected JSON object")
        llm_queries = data.get("queries")
        if not llm_queries or not isinstance(llm_queries, list):
            raise ValueError("Missing or invalid 'queries' key")
        # Validate and clamp
        queries = [str(q) for q in llm_queries if q][:max_queries]
        if not queries:
            raise ValueError("Empty queries list after filtering")
        step_back: Optional[str] = None
        if include_step_back:
            sb = data.get("step_back_query")
            step_back = str(sb) if sb else None
        return QueryPlan(
            topic=topic,
            queries=queries,
            step_back_query=step_back,
            provider_used=provider.name,
            was_fallback=False,
        )
    except (json.JSONDecodeError, ValueError, KeyError):
        # Fall back to deterministic
        fallback = _deterministic_queries(topic, include_step_back, max_queries)
        return QueryPlan(
            topic=fallback.topic,
            queries=fallback.queries,
            step_back_query=fallback.step_back_query,
            provider_used=provider.name,
            was_fallback=True,
        )
