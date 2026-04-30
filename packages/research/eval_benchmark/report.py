"""Report generation for the Scientific RAG Evaluation Benchmark v0.

Generates Markdown and JSON reports from AllMetricsResult.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Tuple

from packages.research.eval_benchmark.metrics import AllMetricsResult, MetricResult


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _metric_status_badge(status: str) -> str:
    """Return a short status string for display."""
    if status == "ok":
        return "[OK]"
    elif status == "not_available":
        return "[N/A]"
    else:
        return "[ERR]"


def _format_metric_section(metric: MetricResult, index: int) -> str:
    """Format a single metric section for the Markdown report."""
    lines = []
    badge = _metric_status_badge(metric.status)
    lines.append(f"### Metric {index}: {metric.name.replace('_', ' ').title()} {badge}")
    lines.append("")

    if metric.notes:
        lines.append(f"*Note: {metric.notes}*")
        lines.append("")

    if metric.status == "not_available":
        lines.append("Metric not available for this run.")
        lines.append("")
        return "\n".join(lines)

    if metric.status == "error":
        lines.append(f"Error computing metric: {metric.notes}")
        lines.append("")
        return "\n".join(lines)

    # Render value dict as a table
    if metric.value:
        lines.append("**Summary:**")
        lines.append("")
        lines.append("| Field | Value |")
        lines.append("|-------|-------|")
        for k, v in metric.value.items():
            if isinstance(v, dict):
                lines.append(f"| {k} | *(see below)* |")
            elif isinstance(v, list):
                lines.append(f"| {k} | *(see below)* |")
            else:
                lines.append(f"| {k} | {v} |")
        lines.append("")

        # Render nested dicts/lists
        for k, v in metric.value.items():
            if isinstance(v, dict) and v:
                lines.append(f"**{k}:**")
                lines.append("")
                lines.append("| Key | Value |")
                lines.append("|-----|-------|")
                for kk, vv in v.items():
                    lines.append(f"| {kk} | {vv} |")
                lines.append("")
            elif isinstance(v, list) and v and isinstance(v[0], dict):
                lines.append(f"**{k}:**")
                lines.append("")
                cols = list(v[0].keys())
                lines.append("| " + " | ".join(cols) + " |")
                lines.append("|" + "|".join("---" for _ in cols) + "|")
                for row in v:
                    lines.append("| " + " | ".join(str(row.get(c, "")) for c in cols) + " |")
                lines.append("")

    # Render detail list if non-empty and not already shown
    if metric.detail and isinstance(metric.detail, list) and metric.detail:
        detail_0 = metric.detail[0] if metric.detail else None
        if isinstance(detail_0, dict):
            cols = list(detail_0.keys())
            if len(metric.detail) <= 20:
                lines.append("**Detail:**")
                lines.append("")
                lines.append("| " + " | ".join(cols) + " |")
                lines.append("|" + "|".join("---" for _ in cols) + "|")
                for row in metric.detail:
                    lines.append("| " + " | ".join(str(row.get(c, "")) for c in cols) + " |")
                lines.append("")
            else:
                lines.append(f"*Detail: {len(metric.detail)} records (truncated in report)*")
                lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_markdown_report(
    metrics: AllMetricsResult,
    recommendation: str,
    rec_justification: str,
) -> str:
    """Generate a Markdown report from AllMetricsResult.

    Parameters
    ----------
    metrics:
        The computed metrics result.
    recommendation:
        The recommendation label (A-E or NONE).
    rec_justification:
        Human-readable justification for the recommendation.

    Returns
    -------
    str
        The Markdown report text.
    """
    lines = []
    draft_flag = ""
    if metrics.golden_qa_review_status != "reviewed":
        draft_flag = " — DRAFT"

    lines.append(f"# Scientific RAG Evaluation Benchmark v0 Report{draft_flag}")
    lines.append("")
    lines.append(f"**Run timestamp:** {metrics.run_ts}")
    lines.append(f"**Corpus version:** {metrics.corpus_version}")
    lines.append(f"**Corpus size:** {metrics.corpus_size} documents")
    lines.append(f"**QA review status:** {metrics.golden_qa_review_status}")
    if draft_flag:
        lines.append("")
        lines.append(
            "> **WARNING:** QA set is not operator-reviewed. "
            "Results are indicative only. Do not use for baseline creation."
        )
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## Recommendation")
    lines.append("")
    lines.append(f"**Label:** {recommendation}")
    lines.append("")
    lines.append(f"**Justification:** {rec_justification}")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## Metrics")
    lines.append("")

    metric_list = [
        (metrics.off_topic_rate, 1),
        (metrics.body_source_distribution, 2),
        (metrics.fallback_rate, 3),
        (metrics.chunk_count_distribution, 4),
        (metrics.low_chunk_suspicious_records, 5),
        (metrics.retrieval_answer_quality, 6),
        (metrics.citation_traceability, 7),
        (metrics.duplicate_dedup_behavior, 8),
        (metrics.parser_quality_notes, 9),
    ]

    for metric, idx in metric_list:
        lines.append(_format_metric_section(metric, idx))

    return "\n".join(lines)


def generate_json_report(
    metrics: AllMetricsResult,
    recommendation: str,
    rec_justification: str,
) -> dict:
    """Generate a machine-readable JSON report dict.

    Parameters
    ----------
    metrics:
        The computed metrics result.
    recommendation:
        The recommendation label.
    rec_justification:
        Justification for the recommendation.

    Returns
    -------
    dict
        JSON-serializable report dict.
    """
    def _metric_to_dict(m: MetricResult) -> dict:
        return {
            "name": m.name,
            "status": m.status,
            "value": m.value,
            "detail": m.detail,
            "notes": m.notes,
        }

    return {
        "run_ts": metrics.run_ts,
        "corpus_version": metrics.corpus_version,
        "corpus_size": metrics.corpus_size,
        "golden_qa_review_status": metrics.golden_qa_review_status,
        "is_draft": metrics.golden_qa_review_status != "reviewed",
        "recommendation": {
            "label": recommendation,
            "justification": rec_justification,
        },
        "metrics": {
            "off_topic_rate": _metric_to_dict(metrics.off_topic_rate),
            "body_source_distribution": _metric_to_dict(metrics.body_source_distribution),
            "fallback_rate": _metric_to_dict(metrics.fallback_rate),
            "chunk_count_distribution": _metric_to_dict(metrics.chunk_count_distribution),
            "low_chunk_suspicious_records": _metric_to_dict(metrics.low_chunk_suspicious_records),
            "retrieval_answer_quality": _metric_to_dict(metrics.retrieval_answer_quality),
            "citation_traceability": _metric_to_dict(metrics.citation_traceability),
            "duplicate_dedup_behavior": _metric_to_dict(metrics.duplicate_dedup_behavior),
            "parser_quality_notes": _metric_to_dict(metrics.parser_quality_notes),
        },
    }


def write_reports(
    output_dir: Path,
    metrics: AllMetricsResult,
    recommendation: str,
    rec_justification: str,
) -> Tuple[Path, Path]:
    """Write both Markdown and JSON reports to output_dir.

    Parameters
    ----------
    output_dir:
        Directory to write reports into (will be created if it doesn't exist).
    metrics:
        The computed metrics result.
    recommendation:
        Recommendation label.
    rec_justification:
        Justification for the recommendation.

    Returns
    -------
    tuple[Path, Path]
        (md_path, json_path) — absolute paths to the written files.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Use date from run_ts
    try:
        date_str = metrics.run_ts[:10]  # YYYY-MM-DD
    except (IndexError, TypeError):
        from datetime import date
        date_str = date.today().isoformat()

    md_path = output_dir / f"{date_str}_benchmark_report.md"
    json_path = output_dir / f"{date_str}_benchmark_report.json"

    md_content = generate_markdown_report(metrics, recommendation, rec_justification)
    with md_path.open("w", encoding="utf-8") as fh:
        fh.write(md_content)

    json_content = generate_json_report(metrics, recommendation, rec_justification)
    with json_path.open("w", encoding="utf-8") as fh:
        json.dump(json_content, fh, indent=2)

    return (md_path, json_path)
