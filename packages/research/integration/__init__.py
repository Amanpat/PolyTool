"""RIS integration package.

Provides bridges between the dossier pipeline, SimTrader, and the
KnowledgeStore — converting locked-away analysis outputs into reusable,
queryable research memory.

SimTrader bridge (v1) — research-to-hypothesis integration:
    brief_to_candidate(brief)
        Convert a ResearchBrief into a hypothesis candidate dict.
    precheck_to_candidate(precheck)
        Convert an EnhancedPrecheck into a hypothesis candidate dict.
    register_research_hypothesis(registry_path, candidate)
        Write a candidate as a JSONL registry event; returns hypothesis_id.
    record_validation_outcome(store, hypothesis_id, claim_ids, outcome, reason)
        Update claim validation_status for all claim_ids.

Dossier pipeline (R5) — wallet analysis -> KnowledgeStore:
    extract_dossier_findings(dossier_dir) -> list[dict]
    batch_extract_dossiers(base_dir) -> list[dict]
    ingest_dossier_findings(findings, store, post_extract_claims=False) -> list
    DossierAdapter  — SourceAdapter registered as "dossier"
"""

from packages.research.integration.hypothesis_bridge import (
    brief_to_candidate,
    precheck_to_candidate,
    register_research_hypothesis,
)
from packages.research.integration.validation_feedback import record_validation_outcome
from packages.research.integration.dossier_extractor import (
    DossierAdapter,
    extract_dossier_findings,
    batch_extract_dossiers,
    ingest_dossier_findings,
)

__all__ = [
    # SimTrader bridge
    "brief_to_candidate",
    "precheck_to_candidate",
    "register_research_hypothesis",
    "record_validation_outcome",
    # Dossier pipeline
    "DossierAdapter",
    "extract_dossier_findings",
    "batch_extract_dossiers",
    "ingest_dossier_findings",
]
