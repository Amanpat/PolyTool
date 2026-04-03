"""RIS v1 operational layer — health condition evaluators.

Implements the RIS_06 health check table with 6 checks:
  1. pipeline_failed
  2. no_new_docs_48h
  3. accept_rate_low
  4. accept_rate_high
  5. model_unavailable  (GREEN stub — awaiting provider event data)
  6. rejection_audit_disagreement

Each check returns a HealthCheckResult with status GREEN/YELLOW/RED.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Literal, Optional

from packages.research.monitoring.run_log import RunRecord

HealthStatus = Literal["GREEN", "YELLOW", "RED"]


@dataclass
class HealthCheck:
    """Descriptor for a single health check."""

    name: str
    description: str


@dataclass
class HealthCheckResult:
    """Result of a single health check evaluation."""

    check_name: str
    status: HealthStatus
    message: str
    data: dict = field(default_factory=dict)


# Registry of all implemented checks (order is cosmetic; evaluate_health
# always produces exactly these 6).
ALL_CHECKS: List[HealthCheck] = [
    HealthCheck(
        name="pipeline_failed",
        description="RED when any run in the window has exit_status==error.",
    ),
    HealthCheck(
        name="no_new_docs_48h",
        description="YELLOW when no documents were accepted in the last 48h.",
    ),
    HealthCheck(
        name="accept_rate_low",
        description="YELLOW when accept rate < 30% over the window (min 5 total docs).",
    ),
    HealthCheck(
        name="accept_rate_high",
        description="YELLOW when accept rate > 90% over the window (min 10 total docs).",
    ),
    HealthCheck(
        name="model_unavailable",
        description="GREEN stub — deferred until provider event data is wired.",
    ),
    HealthCheck(
        name="rejection_audit_disagreement",
        description="YELLOW when audit disagreement rate > 30% (requires audit runner).",
    ),
]


def _check_pipeline_failed(runs: List[RunRecord]) -> HealthCheckResult:
    """RED when the most-recent run has exit_status==error."""
    if not runs:
        return HealthCheckResult(
            check_name="pipeline_failed",
            status="GREEN",
            message="No run data available.",
            data={},
        )

    # Runs are newest-first (list_runs sorts that way); check them in order
    for run in runs:
        if run.exit_status == "error":
            return HealthCheckResult(
                check_name="pipeline_failed",
                status="RED",
                message=f"Pipeline '{run.pipeline}' failed (exit_status=error) at {run.started_at}.",
                data={"run_id": run.run_id, "started_at": run.started_at},
            )

    return HealthCheckResult(
        check_name="pipeline_failed",
        status="GREEN",
        message="No pipeline errors detected.",
        data={},
    )


def _check_no_new_docs_48h(runs: List[RunRecord]) -> HealthCheckResult:
    """YELLOW when runs exist but total accepted is 0."""
    if not runs:
        return HealthCheckResult(
            check_name="no_new_docs_48h",
            status="GREEN",
            message="No run data — insufficient data for this check.",
            data={},
        )

    total_accepted = sum(r.accepted for r in runs)
    if total_accepted == 0:
        return HealthCheckResult(
            check_name="no_new_docs_48h",
            status="YELLOW",
            message="No documents were accepted in the monitored window.",
            data={"run_count": len(runs), "total_accepted": 0},
        )

    return HealthCheckResult(
        check_name="no_new_docs_48h",
        status="GREEN",
        message=f"{total_accepted} document(s) accepted in the monitored window.",
        data={"run_count": len(runs), "total_accepted": total_accepted},
    )


def _check_accept_rate_low(runs: List[RunRecord]) -> HealthCheckResult:
    """YELLOW when accept_rate < 30% AND total > 5."""
    total_accepted = sum(r.accepted for r in runs)
    total_rejected = sum(r.rejected for r in runs)
    total = total_accepted + total_rejected

    if total <= 5:
        return HealthCheckResult(
            check_name="accept_rate_low",
            status="GREEN",
            message=f"Insufficient data ({total} total docs) for accept-rate check.",
            data={"total": total},
        )

    rate = total_accepted / total
    if rate < 0.30:
        return HealthCheckResult(
            check_name="accept_rate_low",
            status="YELLOW",
            message=f"Accept rate is low: {rate:.1%} ({total_accepted}/{total}).",
            data={"accept_rate": rate, "accepted": total_accepted, "total": total},
        )

    return HealthCheckResult(
        check_name="accept_rate_low",
        status="GREEN",
        message=f"Accept rate is healthy: {rate:.1%} ({total_accepted}/{total}).",
        data={"accept_rate": rate, "accepted": total_accepted, "total": total},
    )


def _check_accept_rate_high(runs: List[RunRecord]) -> HealthCheckResult:
    """YELLOW when accept_rate > 90% AND total > 10."""
    total_accepted = sum(r.accepted for r in runs)
    total_rejected = sum(r.rejected for r in runs)
    total = total_accepted + total_rejected

    if total <= 10:
        return HealthCheckResult(
            check_name="accept_rate_high",
            status="GREEN",
            message=f"Insufficient volume ({total} total docs) for high-rate check.",
            data={"total": total},
        )

    rate = total_accepted / total
    if rate > 0.90:
        return HealthCheckResult(
            check_name="accept_rate_high",
            status="YELLOW",
            message=f"Accept rate is suspiciously high: {rate:.1%} ({total_accepted}/{total}). Gate may be too lenient.",
            data={"accept_rate": rate, "accepted": total_accepted, "total": total},
        )

    return HealthCheckResult(
        check_name="accept_rate_high",
        status="GREEN",
        message=f"Accept rate is {rate:.1%} ({total_accepted}/{total}) — within expected bounds.",
        data={"accept_rate": rate, "accepted": total_accepted, "total": total},
    )


def _check_model_unavailable() -> HealthCheckResult:
    """Always GREEN — deferred until provider event data is wired."""
    return HealthCheckResult(
        check_name="model_unavailable",
        status="GREEN",
        message="Model availability monitoring not yet wired (deferred to scheduler integration).",
        data={"deferred": True},
    )


def _check_rejection_audit_disagreement(
    audit_disagreement_rate: Optional[float],
) -> HealthCheckResult:
    """YELLOW when audit_disagreement_rate > 30%."""
    if audit_disagreement_rate is None:
        return HealthCheckResult(
            check_name="rejection_audit_disagreement",
            status="GREEN",
            message="No audit disagreement data provided.",
            data={},
        )

    if audit_disagreement_rate > 0.30:
        return HealthCheckResult(
            check_name="rejection_audit_disagreement",
            status="YELLOW",
            message=(
                f"Rejection audit disagreement rate is high: {audit_disagreement_rate:.1%}. "
                "Manual review recommended."
            ),
            data={"audit_disagreement_rate": audit_disagreement_rate},
        )

    return HealthCheckResult(
        check_name="rejection_audit_disagreement",
        status="GREEN",
        message=f"Rejection audit disagreement rate is acceptable: {audit_disagreement_rate:.1%}.",
        data={"audit_disagreement_rate": audit_disagreement_rate},
    )


def evaluate_health(
    runs: List[RunRecord],
    *,
    window_hours: int = 48,
    audit_disagreement_rate: Optional[float] = None,
) -> List[HealthCheckResult]:
    """Evaluate all 6 RIS health checks and return one result per check.

    Args:
        runs:                    List of RunRecord objects in the evaluation window.
                                 Pass an empty list when no run data is available.
        window_hours:            Window size in hours (informational — caller is
                                 responsible for pre-filtering runs to this window).
        audit_disagreement_rate: If provided, used by the rejection audit check.

    Returns:
        List of 6 HealthCheckResult objects, one per check.
    """
    return [
        _check_pipeline_failed(runs),
        _check_no_new_docs_48h(runs),
        _check_accept_rate_low(runs),
        _check_accept_rate_high(runs),
        _check_model_unavailable(),
        _check_rejection_audit_disagreement(audit_disagreement_rate),
    ]
