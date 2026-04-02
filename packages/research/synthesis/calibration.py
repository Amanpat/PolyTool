"""RIS Phase 2 — calibration analytics helpers.

Provides compute_calibration_summary() and compute_family_drift() for
analyzing the precheck ledger over time windows.

Usage::

    from packages.research.synthesis.calibration import (
        compute_calibration_summary,
        compute_family_drift,
        format_calibration_report,
    )
    from packages.research.synthesis.precheck_ledger import list_prechecks

    events = list_prechecks()
    summary = compute_calibration_summary(events)
    drift = compute_family_drift(events)
    print(format_calibration_report(summary, drift))
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from packages.research.ingestion.seed import SeedManifest


# ---------------------------------------------------------------------------
# Domain keyword mapping for family-drift heuristic
# ---------------------------------------------------------------------------

# Maps domain label -> list of keywords that trigger it (case-insensitive substring match).
# Order matters: first match wins. "general" is the fallback.
_DOMAIN_KEYWORDS: list[tuple[str, list[str]]] = [
    ("market_maker", ["market maker", "market-maker", "avellaneda", "stoikov", "amm", "quoting"]),
    ("crypto", ["crypto", "bitcoin", "btc", "eth", "solana", "sol", "ethereum", "defi", "token"]),
    ("sports", ["sports", "football", "basketball", "nba", "nfl", "tennis", "soccer", "baseball"]),
    ("ris", ["ris", "research intelligence", "precheck", "ingestion pipeline", "knowledge store"]),
    ("polymarket", ["polymarket", "clob", "prediction market", "yes/no market"]),
    ("wallet", ["wallet", "dossier", "alpha", "user behavior"]),
    ("news", ["news", "breaking", "election", "geopolitical", "politics"]),
]
_FALLBACK_DOMAIN = "general"


def _assign_domain(idea: str) -> str:
    """Assign a domain label to an idea string using keyword heuristics.

    This is a best-effort approximation. Future versions can add source_family
    directly to precheck events for precise attribution.

    Args:
        idea: The idea text from a precheck_run event.

    Returns:
        Domain label string.
    """
    lower = idea.lower()
    for domain, keywords in _DOMAIN_KEYWORDS:
        for kw in keywords:
            if kw in lower:
                return domain
    return _FALLBACK_DOMAIN


# ---------------------------------------------------------------------------
# CalibrationSummary
# ---------------------------------------------------------------------------


@dataclass
class CalibrationSummary:
    """Aggregate calibration health metrics over a set of precheck ledger events.

    Attributes
    ----------
    window_start:
        ISO-8601 start of the analysis window (or "all" if unbounded).
    window_end:
        ISO-8601 end of the analysis window (or "all" if unbounded).
    total_prechecks:
        Number of precheck_run events in the window.
    recommendation_distribution:
        Counts of each recommendation value (GO, CAUTION, STOP).
    override_count:
        Number of operator override events.
    override_rate:
        override_count / total_prechecks, or 0.0 if total_prechecks == 0.
    outcome_distribution:
        Counts of each outcome label (successful, failed, partial, not_tried).
    outcome_count:
        Total number of outcome events.
    stale_warning_count:
        Number of precheck_run events with stale_warning=True.
    avg_evidence_count:
        Mean of (len(supporting_evidence) + len(contradicting_evidence)) per
        precheck_run event. 0.0 if no prechecks.
    """

    window_start: str
    window_end: str
    total_prechecks: int
    recommendation_distribution: dict[str, int]
    override_count: int
    override_rate: float
    outcome_distribution: dict[str, int]
    outcome_count: int
    stale_warning_count: int
    avg_evidence_count: float


# ---------------------------------------------------------------------------
# FamilyDriftReport
# ---------------------------------------------------------------------------


@dataclass
class FamilyDriftReport:
    """Per-domain breakdown of precheck recommendations.

    Attributes
    ----------
    family_counts:
        Mapping of domain label -> {recommendation: count}.
        e.g. {"market_maker": {"GO": 3, "CAUTION": 1, "STOP": 0}}
    overrepresented_in_stop:
        List of domain labels where STOP count > 50% of that domain's total events.
    total_prechecks:
        Total precheck_run events analyzed.
    """

    family_counts: dict[str, dict[str, int]]
    overrepresented_in_stop: list[str]
    total_prechecks: int


# ---------------------------------------------------------------------------
# compute_calibration_summary
# ---------------------------------------------------------------------------


def compute_calibration_summary(
    events: list[dict],
    window_start: str = "all",
    window_end: str = "all",
) -> CalibrationSummary:
    """Compute aggregate calibration health metrics from a list of ledger events.

    Partitions events by event_type:
    - "precheck_run": counts toward total_prechecks, recommendation_distribution,
      stale_warning_count, avg_evidence_count.
    - "override": counts toward override_count.
    - "outcome": counts toward outcome_count, outcome_distribution.

    Uses .get() with defaults for all fields to maintain backward compatibility
    with v0/v1 ledger entries that may lack enriched fields.

    Args:
        events: List of raw dicts from the precheck ledger (all event types).
        window_start: ISO-8601 start of window or "all".
        window_end: ISO-8601 end of window or "all".

    Returns:
        CalibrationSummary with computed metrics.
    """
    precheck_runs: list[dict] = []
    overrides: list[dict] = []
    outcomes: list[dict] = []

    for ev in events:
        et = ev.get("event_type", "")
        if et == "precheck_run":
            precheck_runs.append(ev)
        elif et == "override":
            overrides.append(ev)
        elif et == "outcome":
            outcomes.append(ev)

    total_prechecks = len(precheck_runs)
    override_count = len(overrides)
    outcome_count = len(outcomes)

    # Recommendation distribution
    recommendation_distribution: dict[str, int] = {}
    for ev in precheck_runs:
        rec = ev.get("recommendation", "UNKNOWN")
        if rec:
            recommendation_distribution[rec] = recommendation_distribution.get(rec, 0) + 1

    # Override rate
    override_rate = (override_count / total_prechecks) if total_prechecks > 0 else 0.0

    # Outcome distribution
    outcome_distribution: dict[str, int] = {}
    for ev in outcomes:
        label = ev.get("outcome_label", "UNKNOWN")
        if label:
            outcome_distribution[label] = outcome_distribution.get(label, 0) + 1

    # Stale warning count
    stale_warning_count = sum(
        1 for ev in precheck_runs if ev.get("stale_warning", False)
    )

    # Average evidence count
    if total_prechecks > 0:
        total_evidence = sum(
            len(ev.get("supporting_evidence") or [])
            + len(ev.get("contradicting_evidence") or [])
            for ev in precheck_runs
        )
        avg_evidence_count = total_evidence / total_prechecks
    else:
        avg_evidence_count = 0.0

    return CalibrationSummary(
        window_start=window_start,
        window_end=window_end,
        total_prechecks=total_prechecks,
        recommendation_distribution=recommendation_distribution,
        override_count=override_count,
        override_rate=override_rate,
        outcome_distribution=outcome_distribution,
        outcome_count=outcome_count,
        stale_warning_count=stale_warning_count,
        avg_evidence_count=avg_evidence_count,
    )


# ---------------------------------------------------------------------------
# compute_family_drift
# ---------------------------------------------------------------------------


def compute_family_drift(
    events: list[dict],
    manifest: "SeedManifest | None" = None,
) -> FamilyDriftReport:
    """Compute per-domain recommendation breakdown from precheck ledger events.

    Since precheck_run events do not currently carry source_family, this
    function uses keyword-based heuristics on the "idea" field text to
    assign a domain label. If a manifest is provided, it also checks whether
    any manifest entry titles or tags overlap with the idea text.

    This is a best-effort heuristic. Future versions can add source_family
    directly to precheck events for precise attribution.

    For overrepresented_in_stop: a domain is flagged if its STOP count
    exceeds 50% of that domain's total events.

    Args:
        events: List of raw dicts from the precheck ledger.
        manifest: Optional SeedManifest for additional domain-title matching.

    Returns:
        FamilyDriftReport with per-domain counts and overrepresented families.
    """
    precheck_runs = [ev for ev in events if ev.get("event_type") == "precheck_run"]
    total_prechecks = len(precheck_runs)

    family_counts: dict[str, dict[str, int]] = {}

    for ev in precheck_runs:
        idea = ev.get("idea", "") or ""
        recommendation = ev.get("recommendation", "UNKNOWN") or "UNKNOWN"

        # Try manifest-based matching first if manifest is provided
        domain = None
        if manifest is not None:
            for entry in manifest.entries:
                # Check if any manifest entry title/tag keywords appear in the idea
                title_words = set(entry.title.lower().split())
                idea_lower = idea.lower()
                if any(w in idea_lower for w in title_words if len(w) > 4):
                    domain = entry.source_family
                    break

        # Fall back to keyword heuristic
        if domain is None:
            domain = _assign_domain(idea)

        if domain not in family_counts:
            family_counts[domain] = {}
        family_counts[domain][recommendation] = (
            family_counts[domain].get(recommendation, 0) + 1
        )

    # Identify overrepresented_in_stop (> 50% STOP rate)
    overrepresented_in_stop: list[str] = []
    for domain, counts in family_counts.items():
        total = sum(counts.values())
        stop_count = counts.get("STOP", 0)
        if total > 0 and stop_count / total > 0.5:
            overrepresented_in_stop.append(domain)

    overrepresented_in_stop.sort()

    return FamilyDriftReport(
        family_counts=family_counts,
        overrepresented_in_stop=overrepresented_in_stop,
        total_prechecks=total_prechecks,
    )


# ---------------------------------------------------------------------------
# format_calibration_report
# ---------------------------------------------------------------------------


def format_calibration_report(
    summary: CalibrationSummary,
    drift: "FamilyDriftReport | None" = None,
) -> str:
    """Format a CalibrationSummary (and optionally FamilyDriftReport) as human-readable text.

    Args:
        summary: CalibrationSummary from compute_calibration_summary().
        drift: Optional FamilyDriftReport from compute_family_drift().

    Returns:
        Multi-line human-readable report string.
    """
    lines: list[str] = []

    window_desc = (
        f"{summary.window_start} to {summary.window_end}"
        if summary.window_start != "all"
        else "all time"
    )
    lines.append(f"=== Calibration Health Report ({window_desc}) ===")
    lines.append("")

    lines.append(f"Total prechecks:   {summary.total_prechecks}")
    lines.append(f"Override count:    {summary.override_count}")
    lines.append(f"Override rate:     {summary.override_rate:.1%}")
    lines.append(f"Outcome count:     {summary.outcome_count}")
    lines.append(f"Stale warnings:    {summary.stale_warning_count}")
    lines.append(f"Avg evidence/check:{summary.avg_evidence_count:.1f}")
    lines.append("")

    if summary.recommendation_distribution:
        lines.append("Recommendations:")
        for rec, count in sorted(summary.recommendation_distribution.items()):
            pct = count / summary.total_prechecks * 100 if summary.total_prechecks else 0
            lines.append(f"  {rec:<10}: {count:4d}  ({pct:.0f}%)")
    else:
        lines.append("Recommendations:   (none)")
    lines.append("")

    if summary.outcome_distribution:
        lines.append("Outcomes:")
        for label, count in sorted(summary.outcome_distribution.items()):
            lines.append(f"  {label:<15}: {count:4d}")
    else:
        lines.append("Outcomes:          (none)")
    lines.append("")

    if drift is not None:
        lines.append("Domain Drift:")
        if drift.family_counts:
            for domain, counts in sorted(drift.family_counts.items()):
                total = sum(counts.values())
                stop_count = counts.get("STOP", 0)
                stop_pct = stop_count / total * 100 if total > 0 else 0
                flag = " [OVERREPRESENTED]" if domain in drift.overrepresented_in_stop else ""
                lines.append(
                    f"  {domain:<20}: "
                    + "  ".join(f"{k}={v}" for k, v in sorted(counts.items()))
                    + f"  (STOP {stop_pct:.0f}%){flag}"
                )
        else:
            lines.append("  (no domain data)")
        lines.append("")

    return "\n".join(lines)
