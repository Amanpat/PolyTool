"""RIS SimTrader bridge v1 -- research-to-hypothesis integration layer.

Provides a practical v1 bridge between RIS research outputs (ResearchBrief /
EnhancedPrecheck) and the hypothesis registry / KnowledgeStore feedback loop.

Public API
----------
brief_to_candidate(brief)
    Convert a ResearchBrief into a hypothesis candidate dict.
precheck_to_candidate(precheck)
    Convert an EnhancedPrecheck into a hypothesis candidate dict.
register_research_hypothesis(registry_path, candidate)
    Write a candidate as a JSONL registry event; returns hypothesis_id.
record_validation_outcome(store, hypothesis_id, claim_ids, outcome, reason)
    Update claim validation_status for all claim_ids based on a validation outcome.
"""

from packages.research.integration.hypothesis_bridge import (
    brief_to_candidate,
    precheck_to_candidate,
    register_research_hypothesis,
)
from packages.research.integration.validation_feedback import record_validation_outcome

__all__ = [
    "brief_to_candidate",
    "precheck_to_candidate",
    "register_research_hypothesis",
    "record_validation_outcome",
]
