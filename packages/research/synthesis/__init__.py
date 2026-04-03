"""RIS v1 synthesis — precheck runner, query planning, HyDE expansion, combined retrieval, and report synthesis."""

from packages.research.synthesis.precheck import PrecheckResult, run_precheck
from packages.research.synthesis.precheck_ledger import append_precheck, list_prechecks
from packages.research.synthesis.report_ledger import (
    ReportEntry,
    persist_report,
    list_reports,
    search_reports,
    generate_digest,
)
from packages.research.synthesis.report import (
    CitedEvidence,
    EnhancedPrecheck,
    ResearchBrief,
    ReportSynthesizer,
    format_citation,
    format_enhanced_precheck,
    format_research_brief,
)
from packages.research.synthesis.query_planner import QueryPlan, plan_queries
from packages.research.synthesis.hyde import HydeResult, expand_hyde
from packages.research.synthesis.retrieval import RetrievalPlan, retrieve_for_research

__all__ = [
    "run_precheck",
    "PrecheckResult",
    "append_precheck",
    "list_prechecks",
    "ReportEntry",
    "persist_report",
    "list_reports",
    "search_reports",
    "generate_digest",
    # Report synthesis (RIS_05)
    "CitedEvidence",
    "EnhancedPrecheck",
    "ResearchBrief",
    "ReportSynthesizer",
    "format_citation",
    "format_enhanced_precheck",
    "format_research_brief",
    # Query planner (RIS_05 query planning)
    "QueryPlan",
    "plan_queries",
    # HyDE expansion (RIS_05 query planning)
    "HydeResult",
    "expand_hyde",
    # Combined retrieval (RIS_05 query planning)
    "RetrievalPlan",
    "retrieve_for_research",
]
