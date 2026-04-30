"""Rule-based A-E recommendation engine for the Scientific RAG Evaluation Benchmark v0.

Analyzes AllMetricsResult and returns a prioritized recommendation label with
triggered rules and justification.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from packages.research.eval_benchmark.metrics import AllMetricsResult


RECOMMENDATION_LABELS = {
    "A": "Pre-fetch relevance filtering (Layer 3)",
    "B": "Old-paper re-ingest cleanup",
    "C": "PaperQA2-style retrieval (Layer 2)",
    "D": "Marker production validation (Layer 1)",
    "E": "Chunking changes",
    "NONE": "No action required",
}


@dataclass
class RecommendationResult:
    label: str  # "A" | "B" | "C" | "D" | "E" | "NONE"
    title: str
    justification: str
    triggered_rules: List[str] = field(default_factory=list)


def recommend(metrics: AllMetricsResult) -> RecommendationResult:
    """Analyze metrics and return the highest-priority triggered recommendation.

    Priority order: A > B > C > D > E > NONE.

    Parameters
    ----------
    metrics:
        AllMetricsResult from compute_all_metrics().

    Returns
    -------
    RecommendationResult
    """
    triggered_rules: List[str] = []

    # --- Rule A: high off-topic rate (> 30%) ---
    rule_a_fired = False
    m1 = metrics.off_topic_rate
    if m1.status == "ok" and m1.value:
        rate = m1.value.get("off_topic_rate_pct", 0.0)
        if rate > 30.0:
            rule_a_fired = True
            triggered_rules.append(
                f"Rule A: off_topic_rate={rate}% > 30% — "
                "High off-topic rate suggests pre-fetch filtering needed"
            )

    # --- Rule B: high fallback rate (> 40%) ---
    rule_b_fired = False
    m3 = metrics.fallback_rate
    if m3.status == "ok" and m3.value:
        rate = m3.value.get("fallback_rate_pct", 0.0)
        if rate > 40.0:
            rule_b_fired = True
            triggered_rules.append(
                f"Rule B: fallback_rate={rate}% > 40% — "
                "High fallback rate suggests re-ingest of abstract-only papers"
            )

    # --- Rule C: low retrieval P@5 (< 0.5) ---
    rule_c_fired = False
    m6 = metrics.retrieval_answer_quality
    if m6.status == "ok" and m6.value:
        p_at_5 = m6.value.get("p_at_5", None)
        if p_at_5 is not None and p_at_5 < 0.5:
            rule_c_fired = True
            triggered_rules.append(
                f"Rule C: p_at_5={p_at_5} < 0.5 — "
                "Low retrieval P@5 suggests retrieval improvements needed"
            )

    # --- Rule D: >30% of equation_heavy docs flagged as not parseable ---
    rule_d_fired = False
    m9 = metrics.parser_quality_notes
    if m9.status == "ok" and m9.detail:
        eq_heavy = [
            d for d in m9.detail
            if d.get("category") == "equation_heavy"
            and d.get("body_source") != "abstract_fallback"
        ]
        if eq_heavy:
            not_parseable = [
                d for d in eq_heavy
                if not d.get("quality_flags", {}).get("equation_parseable", True)
            ]
            eq_not_parseable_pct = 100.0 * len(not_parseable) / len(eq_heavy)
            if eq_not_parseable_pct > 30.0:
                rule_d_fired = True
                triggered_rules.append(
                    f"Rule D: {eq_not_parseable_pct:.1f}% of equation_heavy docs not parseable "
                    "> 30% — Parser quality issues suggest Marker rollout"
                )

    # --- Rule E: low median chunk count (< 3) ---
    rule_e_fired = False
    m4 = metrics.chunk_count_distribution
    if m4.status == "ok" and m4.value:
        median_chunks = m4.value.get("median", None)
        if median_chunks is not None and median_chunks < 3:
            rule_e_fired = True
            triggered_rules.append(
                f"Rule E: median_chunks={median_chunks} < 3 — "
                "Low median chunk count suggests chunking issues"
            )

    # Priority: A > B > C > D > E
    if rule_a_fired:
        label = "A"
        justification = "High off-topic rate suggests pre-fetch filtering needed"
    elif rule_b_fired:
        label = "B"
        justification = "High fallback rate suggests re-ingest of abstract-only papers"
    elif rule_c_fired:
        label = "C"
        justification = "Low retrieval P@5 suggests retrieval improvements needed"
    elif rule_d_fired:
        label = "D"
        justification = "Parser quality issues suggest Marker rollout"
    elif rule_e_fired:
        label = "E"
        justification = "Low median chunk count suggests chunking issues"
    else:
        label = "NONE"
        justification = "No action threshold exceeded. System healthy."

    title = RECOMMENDATION_LABELS.get(label, "Unknown")

    return RecommendationResult(
        label=label,
        title=title,
        justification=justification,
        triggered_rules=triggered_rules,
    )
