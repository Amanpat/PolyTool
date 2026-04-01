"""RIS v1 synthesis — precheck runner and research report generation."""

from packages.research.synthesis.precheck import PrecheckResult, run_precheck
from packages.research.synthesis.precheck_ledger import append_precheck, list_prechecks

__all__ = [
    "run_precheck",
    "PrecheckResult",
    "append_precheck",
    "list_prechecks",
]
