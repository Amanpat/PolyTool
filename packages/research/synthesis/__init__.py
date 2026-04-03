"""RIS v1 synthesis — precheck runner and research report generation."""

from packages.research.synthesis.precheck import PrecheckResult, run_precheck
from packages.research.synthesis.precheck_ledger import append_precheck, list_prechecks
from packages.research.synthesis.report_ledger import (
    ReportEntry,
    persist_report,
    list_reports,
    search_reports,
    generate_digest,
)

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
]
