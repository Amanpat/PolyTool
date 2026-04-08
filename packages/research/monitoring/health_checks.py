"""RIS v1 operational layer — health condition evaluators.

Implements the RIS_06 health check table with 7 checks:
  1. pipeline_failed
  2. no_new_docs_48h
  3. accept_rate_low
  4. accept_rate_high
  5. model_unavailable  (real: driven by provider failure data from eval artifacts)
  6. review_queue_backlog  (real: driven by pending_review table depth)
  7. rejection_audit_disagreement  (deferred — requires audit runner)

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
# always produces exactly these 7).
ALL_CHECKS: List[HealthCheck] = [
    HealthCheck(
        name="pipeline_failed",
        description="RED when any pipeline's latest run exited with error; YELLOW for explicit blocked/setup states.",
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
        description="YELLOW when any provider has >3 failures in window; RED when all configured providers have failures.",
    ),
    HealthCheck(
        name="review_queue_backlog",
        description="YELLOW when review queue depth > 20, RED when > 50.",
    ),
    HealthCheck(
        name="rejection_audit_disagreement",
        description="YELLOW when audit disagreement rate > 30% (requires audit runner — deferred).",
    ),
]


def _latest_runs_by_pipeline(runs: List[RunRecord]) -> List[RunRecord]:
    """Return newest-first runs, keeping only the latest entry per pipeline."""
    latest: list[RunRecord] = []
    seen: set[str] = set()
    for run in runs:
        if run.pipeline in seen:
            continue
        latest.append(run)
        seen.add(run.pipeline)
    return latest


def _summarize_pipeline_issue(run: RunRecord) -> str:
    """Render an operator-facing summary for a failed or blocked pipeline run."""
    operator_message = str(run.metadata.get("operator_message", "")).strip()
    operator_status = str(run.metadata.get("operator_status", "")).strip()

    if run.exit_status == "partial" and operator_status:
        return f"{run.pipeline} blocked: {operator_message or operator_status}."

    if operator_message:
        return f"{run.pipeline} failed at {run.started_at}: {operator_message}."

    return f"{run.pipeline} failed (exit_status={run.exit_status}) at {run.started_at}."


def _check_pipeline_failed(runs: List[RunRecord]) -> HealthCheckResult:
    """Evaluate the latest known state of each pipeline."""
    if not runs:
        return HealthCheckResult(
            check_name="pipeline_failed",
            status="GREEN",
            message="No run data available.",
            data={},
        )

    latest_runs = _latest_runs_by_pipeline(runs)
    current_errors = [run for run in latest_runs if run.exit_status == "error"]
    current_blocked = [
        run
        for run in latest_runs
        if run.exit_status == "partial" and run.metadata.get("operator_status")
    ]

    if current_errors:
        issue_summaries = [_summarize_pipeline_issue(run) for run in current_errors]
        issue_summaries.extend(_summarize_pipeline_issue(run) for run in current_blocked)
        return HealthCheckResult(
            check_name="pipeline_failed",
            status="RED",
            message="Current pipeline issues: " + " ".join(issue_summaries),
            data={
                "error_pipelines": [run.pipeline for run in current_errors],
                "blocked_pipelines": [run.pipeline for run in current_blocked],
            },
        )

    if current_blocked:
        return HealthCheckResult(
            check_name="pipeline_failed",
            status="YELLOW",
            message="Current pipeline issues: "
            + " ".join(_summarize_pipeline_issue(run) for run in current_blocked),
            data={"blocked_pipelines": [run.pipeline for run in current_blocked]},
        )

    return HealthCheckResult(
        check_name="pipeline_failed",
        status="GREEN",
        message="No current pipeline failures detected.",
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


def _check_model_unavailable(
    provider_failure_counts: Optional[dict] = None,
    routing_config: Optional[dict] = None,
) -> HealthCheckResult:
    """Evaluate provider availability from failure count data.

    Args:
        provider_failure_counts: dict mapping failure_reason or provider_name -> count.
            If empty or None, returns GREEN (no failures detected).
        routing_config: Optional dict with keys primary_provider, escalation_provider,
            fallback_provider. Used to detect when ALL configured providers are failing.

    Returns:
        GREEN  — no failures detected.
        YELLOW — at least one provider/reason with >3 total failures.
        RED    — all configured providers have failures (complete outage).
    """
    if not provider_failure_counts:
        return HealthCheckResult(
            check_name="model_unavailable",
            status="GREEN",
            message="No provider failures detected.",
            data={"deferred": False},
        )

    total_failures = sum(provider_failure_counts.values())

    # Check if all configured providers are failing (RED condition)
    if routing_config:
        configured = [
            routing_config.get("primary_provider"),
            routing_config.get("escalation_provider"),
            routing_config.get("fallback_provider"),
        ]
        configured_providers = [p for p in configured if p]
        if configured_providers:
            all_failing = all(p in provider_failure_counts for p in configured_providers)
            if all_failing:
                return HealthCheckResult(
                    check_name="model_unavailable",
                    status="RED",
                    message=(
                        f"All providers experiencing failures: "
                        + ", ".join(
                            f"{p}={provider_failure_counts[p]}"
                            for p in configured_providers
                        )
                    ),
                    data={
                        "deferred": False,
                        "provider_failure_counts": provider_failure_counts,
                        "all_providers_failing": True,
                    },
                )

    # YELLOW when any single reason/provider has >3 failures
    if total_failures > 3:
        high_counts = {k: v for k, v in provider_failure_counts.items() if v > 0}
        return HealthCheckResult(
            check_name="model_unavailable",
            status="YELLOW",
            message=(
                f"Provider failures detected: "
                + ", ".join(f"{k}={v}" for k, v in sorted(high_counts.items()))
            ),
            data={
                "deferred": False,
                "provider_failure_counts": provider_failure_counts,
                "total_failures": total_failures,
            },
        )

    # Small number of failures — still GREEN but include data
    return HealthCheckResult(
        check_name="model_unavailable",
        status="GREEN",
        message=f"Provider failure count within acceptable range ({total_failures} total).",
        data={
            "deferred": False,
            "provider_failure_counts": provider_failure_counts,
            "total_failures": total_failures,
        },
    )


def _check_review_queue_backlog(review_queue: Optional[dict] = None) -> HealthCheckResult:
    """Evaluate review queue depth from pending_review table data.

    Args:
        review_queue: dict with at minimum a 'queue_depth' key (int).
            Empty dict or None returns GREEN (no data available).

    Returns:
        GREEN  — depth <= 20 or no data.
        YELLOW — depth > 20.
        RED    — depth > 50.
    """
    if not review_queue or "queue_depth" not in review_queue:
        return HealthCheckResult(
            check_name="review_queue_backlog",
            status="GREEN",
            message="No review queue data available.",
            data={},
        )

    depth = int(review_queue.get("queue_depth", 0))
    by_status = review_queue.get("by_status", {})

    if depth > 50:
        return HealthCheckResult(
            check_name="review_queue_backlog",
            status="RED",
            message=f"Review queue critical backlog: {depth} items pending.",
            data={"queue_depth": depth, "by_status": by_status},
        )

    if depth > 20:
        return HealthCheckResult(
            check_name="review_queue_backlog",
            status="YELLOW",
            message=f"Review queue growing: {depth} items pending.",
            data={"queue_depth": depth, "by_status": by_status},
        )

    return HealthCheckResult(
        check_name="review_queue_backlog",
        status="GREEN",
        message=f"Review queue manageable: {depth} items pending.",
        data={"queue_depth": depth, "by_status": by_status},
    )


def _check_rejection_audit_disagreement(
    audit_disagreement_rate: Optional[float],
) -> HealthCheckResult:
    """YELLOW when audit_disagreement_rate > 30%."""
    if audit_disagreement_rate is None:
        return HealthCheckResult(
            check_name="rejection_audit_disagreement",
            status="GREEN",
            message="[DEFERRED] Rejection audit check requires audit runner. Not yet wired.",
            data={"deferred": True, "check_type": "stub"},
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
    provider_failure_counts: Optional[dict] = None,
    review_queue: Optional[dict] = None,
    routing_config: Optional[dict] = None,
) -> List[HealthCheckResult]:
    """Evaluate all 7 RIS health checks and return one result per check.

    Args:
        runs:                    List of RunRecord objects in the evaluation window.
                                 Pass an empty list when no run data is available.
        window_hours:            Window size in hours (informational — caller is
                                 responsible for pre-filtering runs to this window).
        audit_disagreement_rate: If provided, used by the rejection audit check.
        provider_failure_counts: If provided, dict of failure counts by reason/provider.
                                 Drives the model_unavailable check.
        review_queue:            If provided, dict with queue_depth and by_status keys.
                                 Drives the review_queue_backlog check.
        routing_config:          If provided, dict with primary_provider etc. keys.
                                 Used by model_unavailable to detect full outage.

    Returns:
        List of 7 HealthCheckResult objects, one per check.
    """
    return [
        _check_pipeline_failed(runs),
        _check_no_new_docs_48h(runs),
        _check_accept_rate_low(runs),
        _check_accept_rate_high(runs),
        _check_model_unavailable(provider_failure_counts or {}, routing_config=routing_config),
        _check_review_queue_backlog(review_queue or {}),
        _check_rejection_audit_disagreement(audit_disagreement_rate),
    ]
