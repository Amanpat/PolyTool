"""RIS SimTrader bridge v1 -- research finding to hypothesis candidate converter.

Connects ResearchBrief / EnhancedPrecheck outputs from the RIS synthesis layer
to the existing hypothesis registry. This is a practical v1 bridge -- no
automatic test-loop orchestration, no auto-promotion, no Discord approval flow.
The operator (or a future orchestrator) calls these functions manually after
reviewing research outputs.

Functions
---------
brief_to_candidate(brief)
    Convert a ResearchBrief into a hypothesis candidate dict.
precheck_to_candidate(precheck)
    Convert an EnhancedPrecheck into a hypothesis candidate dict.
register_research_hypothesis(registry_path, candidate)
    Write a candidate as a JSONL registry event and return the hypothesis_id.

Deferred (R5 / v2)
------------------
- Automatic test-loop orchestration
- Auto-hypothesis promotion on Gate 2 pass
- Discord approval integration
- Scheduled re-validation
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from packages.research.hypotheses.registry import append_event
from packages.research.synthesis.report import EnhancedPrecheck, ResearchBrief

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

BRIDGE_ACTOR = "research_bridge_v1"
BRIDGE_SCHEMA_VERSION = "research_hypothesis_v0"

_SLUG_UNSAFE = re.compile(r"[^a-z0-9_]+")
_MAX_SLUG_LEN = 60


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _slugify(text: str) -> str:
    """Convert a free-text string to a snake_case slug (max 60 chars)."""
    lower = text.lower().strip()
    slug = _SLUG_UNSAFE.sub("_", lower)
    slug = slug.strip("_")
    return slug[:_MAX_SLUG_LEN]


def _utcnow_iso() -> str:
    return datetime.now(tz=timezone.utc).replace(microsecond=0).isoformat()


def _research_hypothesis_id(name: str) -> str:
    """Derive a stable hypothesis ID for a research candidate by name.

    Uses sha256 of {"kind": "research_candidate", "name": <name>} to produce
    a hyp_<16-hex-chars> ID. Does NOT reuse stable_hypothesis_id() from
    registry.py -- that function expects dimension_key / segment_key shapes.
    """
    payload = json.dumps(
        {"kind": "research_candidate", "name": name},
        sort_keys=True,
        separators=(",", ":"),
    )
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
    return f"hyp_{digest}"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def brief_to_candidate(brief: ResearchBrief) -> dict:
    """Convert a ResearchBrief into a hypothesis candidate dict.

    The candidate dict can be passed directly to ``register_research_hypothesis()``.

    Parameters
    ----------
    brief:
        A ResearchBrief from ``ReportSynthesizer.synthesize_brief()``.

    Returns
    -------
    dict
        Keys: name, source_brief_topic, hypothesis_text, evidence_doc_ids,
        suggested_parameters, strategy_type, overall_confidence, generated_at.
    """
    # Slug name from topic
    slug = _slugify(brief.topic)
    name = f"{slug}_v1"

    # hypothesis_text: use summary unless it is the empty-brief fallback
    _fallback_summary_prefix = "Insufficient evidence"
    if brief.summary and not brief.summary.startswith(_fallback_summary_prefix):
        hypothesis_text = brief.summary
    elif brief.key_findings:
        # Use first key finding description as hypothesis text
        first = brief.key_findings[0]
        hypothesis_text = str(first.get("description") or first.get("title") or "")
    else:
        hypothesis_text = f"Investigate: {brief.topic}"

    # evidence_doc_ids: deduplicated, non-empty source_doc_id values
    seen: set[str] = set()
    evidence_doc_ids: list[str] = []
    for ev in brief.cited_sources:
        doc_id = getattr(ev, "source_doc_id", None) or ""
        if doc_id and doc_id not in seen:
            seen.add(doc_id)
            evidence_doc_ids.append(doc_id)

    # strategy_type from actionability.target_track
    strategy_type = str(
        (brief.actionability or {}).get("target_track") or "general"
    )
    if not strategy_type:
        strategy_type = "general"

    # suggested_parameters: structured dict from actionability
    actionability = brief.actionability or {}
    suggested_parameters: dict = {
        "can_inform_strategy": actionability.get("can_inform_strategy", False),
        "estimated_impact": actionability.get("estimated_impact", ""),
        "suggested_next_step": actionability.get("suggested_next_step", ""),
    }

    return {
        "name": name,
        "source_brief_topic": brief.topic,
        "hypothesis_text": hypothesis_text,
        "evidence_doc_ids": evidence_doc_ids,
        "suggested_parameters": suggested_parameters,
        "strategy_type": strategy_type,
        "overall_confidence": brief.overall_confidence,
        "generated_at": brief.generated_at,
    }


def precheck_to_candidate(precheck: EnhancedPrecheck) -> dict:
    """Convert an EnhancedPrecheck into a hypothesis candidate dict.

    The candidate dict can be passed directly to ``register_research_hypothesis()``.

    Parameters
    ----------
    precheck:
        An EnhancedPrecheck from ``ReportSynthesizer.synthesize_precheck()``.

    Returns
    -------
    dict
        Keys: name, source_brief_topic, hypothesis_text, evidence_doc_ids,
        suggested_parameters, strategy_type, overall_confidence, generated_at.
    """
    # Slug name from idea
    slug = _slugify(precheck.idea)
    name = f"{slug}_v1"

    # hypothesis_text: combine recommendation context with idea
    hypothesis_text = (
        f"[{precheck.recommendation}] {precheck.idea}. "
        f"Validation: {precheck.validation_approach or 'see precheck'}"
    )

    # evidence_doc_ids: from supporting evidence only
    seen: set[str] = set()
    evidence_doc_ids: list[str] = []
    for ev in precheck.supporting:
        doc_id = getattr(ev, "source_doc_id", None) or ""
        if doc_id and doc_id not in seen:
            seen.add(doc_id)
            evidence_doc_ids.append(doc_id)

    # strategy_type: try to infer from idea text (reuse report.py approach)
    idea_lower = precheck.idea.lower()
    _TRACK_KEYWORDS = {
        "market_maker": ["market maker", "market-maker", "quoting", "avellaneda", "stoikov"],
        "crypto": ["crypto", "btc", "eth", "bitcoin", "ethereum", "sol"],
        "sports": ["sports", "football", "nba", "nfl", "soccer"],
    }
    strategy_type = "general"
    for track, keywords in _TRACK_KEYWORDS.items():
        if any(kw in idea_lower for kw in keywords):
            strategy_type = track
            break

    # suggested_parameters: precheck risk and validation context
    suggested_parameters: dict = {
        "recommendation": precheck.recommendation,
        "validation_approach": precheck.validation_approach,
        "risk_factors": precheck.risk_factors[:3] if precheck.risk_factors else [],
    }

    return {
        "name": name,
        "source_brief_topic": precheck.idea,
        "hypothesis_text": hypothesis_text,
        "evidence_doc_ids": evidence_doc_ids,
        "suggested_parameters": suggested_parameters,
        "strategy_type": strategy_type,
        "overall_confidence": precheck.overall_confidence,
        "generated_at": precheck.timestamp,
    }


def register_research_hypothesis(
    registry_path: str | Path,
    candidate: dict,
) -> str:
    """Register a research hypothesis candidate in the JSONL registry.

    Writes one JSONL event with event_type="registered" and
    source.origin="research_bridge". The hypothesis_id is derived
    deterministically from the candidate name -- calling this function
    twice with the same candidate appends a second event but does not
    error (the registry is append-only).

    Parameters
    ----------
    registry_path:
        Path to the registry JSONL file. Parent directories are created if
        they do not exist (handled by ``append_event``).
    candidate:
        Candidate dict from ``brief_to_candidate()`` or
        ``precheck_to_candidate()``.

    Returns
    -------
    str
        The deterministic hypothesis_id (``hyp_<16hex>``).
    """
    hypothesis_id = _research_hypothesis_id(candidate["name"])
    created_at = _utcnow_iso()

    event: dict = {
        "schema_version": BRIDGE_SCHEMA_VERSION,
        "hypothesis_id": hypothesis_id,
        "title": candidate["name"],
        "created_at": created_at,
        "status": "proposed",
        "source": {
            "origin": "research_bridge",
            "brief_topic": candidate.get("source_brief_topic", ""),
            "evidence_doc_ids": candidate.get("evidence_doc_ids", []),
        },
        "assumptions": [candidate.get("hypothesis_text", "")],
        "metrics_plan": {
            "strategy_type": candidate.get("strategy_type", ""),
            "suggested_parameters": candidate.get("suggested_parameters", {}),
        },
        "stop_conditions": [],
        "notes": [],
        "status_reason": None,
        "event_type": "registered",
        "event_at": created_at,
    }

    append_event(registry_path, event)
    return hypothesis_id
