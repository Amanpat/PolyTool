"""RIS v1 synthesis — HyDE (Hypothetical Document Embedding) expansion utility.

Generates a hypothetical document snippet from a query. When used as a retrieval
query, HyDE typically improves recall for semantic search because the embedding of
a hypothetical answer is closer to real relevant documents than the query embedding.

Usage:
    from packages.research.synthesis.hyde import expand_hyde, HydeResult

    # Deterministic (default)
    hr = expand_hyde("What is the optimal spread for market making?")

    # LLM-generated (requires Ollama running)
    hr = expand_hyde("optimal spread for market making", provider_name="ollama")
"""

from __future__ import annotations

from dataclasses import dataclass

from packages.research.evaluation.providers import get_provider
from packages.research.evaluation.types import EvalDocument


# ---------------------------------------------------------------------------
# HydeResult dataclass
# ---------------------------------------------------------------------------


@dataclass
class HydeResult:
    """Result of HyDE hypothetical document expansion.

    Fields:
        query: The original query string.
        hypothetical_document: A generated passage that would answer the query.
        provider_used: Provider identifier string.
        was_fallback: True if the LLM call failed and a template was used instead.
    """
    query: str
    hypothetical_document: str
    provider_used: str
    was_fallback: bool


# ---------------------------------------------------------------------------
# Deterministic fallback
# ---------------------------------------------------------------------------


def _deterministic_hyde(query: str) -> str:
    """Generate a deterministic template hypothetical document for a query.

    Returns a plausible-structure paragraph that can be used as a retrieval query.
    The template is intentionally generic but references the query text so that
    the embedding captures the query's semantic content.

    Args:
        query: The original search query.

    Returns:
        Template hypothetical document string.
    """
    topic = query if query else "this research question"
    return (
        f"Research indicates that {topic}. "
        "Key considerations include empirical evidence, domain constraints, "
        "and practical implementation factors. "
        "Studies in this area show that careful analysis of underlying assumptions "
        "and risk factors is essential for deriving actionable conclusions."
    )


def _build_hyde_prompt(query: str) -> str:
    """Build an LLM prompt requesting a hypothetical expert document passage.

    Instructs the LLM to return plain text (not JSON) — the raw text IS the
    hypothetical document. This matches the HyDE paper's original approach.

    Args:
        query: The query to expand.

    Returns:
        Prompt string.
    """
    return "\n".join(
        [
            "You are a research expert for PolyTool, a Polymarket prediction market",
            "research system. Write a SHORT hypothetical document passage that answers",
            "the following question.",
            "",
            "INSTRUCTIONS:",
            "- Write 2-3 sentences as if from a high-quality research paper or expert analysis.",
            "- Be specific and factual-sounding. Use domain-appropriate language.",
            "- Return PLAIN TEXT ONLY. No JSON. No markdown. No explanation.",
            "",
            f"QUESTION: {query}",
            "",
            "Write the hypothetical document passage:",
        ]
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def expand_hyde(
    query: str,
    provider_name: str = "manual",
    **kwargs,
) -> HydeResult:
    """Generate a hypothetical document expansion for a query (HyDE technique).

    Deterministic mode (provider_name="manual"):
        Returns a template-based hypothetical document. was_fallback=False
        since manual is the intended offline mode.

    LLM mode (provider_name="ollama" etc.):
        Sends a prompt to the provider requesting a hypothetical passage.
        Falls back to deterministic template if the call fails (was_fallback=True).

    Args:
        query: The query to expand with a hypothetical document.
        provider_name: Provider to use. Default "manual" for deterministic mode.
        **kwargs: Passed to get_provider().

    Returns:
        HydeResult with query, hypothetical_document, provider_used, was_fallback.
    """
    if provider_name == "manual":
        return HydeResult(
            query=query,
            hypothetical_document=_deterministic_hyde(query),
            provider_used="manual",
            was_fallback=False,
        )

    # LLM path
    provider = get_provider(provider_name, **kwargs)
    prompt = _build_hyde_prompt(query)

    doc_id = f"hyde_{abs(hash(query))}"
    synthetic_doc = EvalDocument(
        doc_id=doc_id,
        title="HyDE expansion: " + query[:80],
        author="operator",
        source_type="manual",
        source_url="",
        source_publish_date=None,
        body=query,
        metadata={"hyde": True},
    )

    try:
        raw_response = provider.score(synthetic_doc, prompt)
        hypothetical_doc = raw_response.strip()
        if not hypothetical_doc:
            raise ValueError("Empty response from provider")
        return HydeResult(
            query=query,
            hypothetical_document=hypothetical_doc,
            provider_used=provider.name,
            was_fallback=False,
        )
    except Exception:
        return HydeResult(
            query=query,
            hypothetical_document=_deterministic_hyde(query),
            provider_used=provider.name,
            was_fallback=True,
        )
