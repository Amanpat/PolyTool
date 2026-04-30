"""Report generation for the Scientific RAG Evaluation Benchmark v0.

Generates Markdown and JSON reports from AllMetricsResult.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

from packages.research.eval_benchmark.metrics import AllMetricsResult, MetricResult


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _metric_status_badge(status: str) -> str:
    if status == "ok":
        return "[OK]"
    elif status == "not_available":
        return "[N/A]"
    else:
        return "[ERR]"


def _format_metric_section(metric: MetricResult, index: int) -> str:
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
    triggered_rules: Optional[List[str]] = None,
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
    triggered_rules:
        List of rule description strings that fired. Included verbatim in the
        report so the recommendation is auditable after stdout is gone.
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
    lines.append(f"**Manifest entries:** {metrics.manifest_entries}")
    lines.append(f"**QA review status:** {metrics.golden_qa_review_status}")
    if draft_flag:
        lines.append("")
        lines.append(
            "> **WARNING:** QA set is not operator-reviewed. "
            "Results are indicative only. Do not use for baseline creation."
        )

    if metrics.missing_source_ids:
        lines.append("")
        lines.append(
            f"> **WARNING:** {len(metrics.missing_source_ids)} manifest source_id(s) not found "
            "in the KnowledgeStore DB. Affected IDs: "
            + ", ".join(f"`{sid[:16]}...`" for sid in metrics.missing_source_ids[:5])
            + ("" if len(metrics.missing_source_ids) <= 5 else f" (+{len(metrics.missing_source_ids)-5} more)")
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

    # Triggered rules audit trail
    lines.append("**Triggered rules:**")
    lines.append("")
    if triggered_rules:
        for rule in triggered_rules:
            lines.append(f"- {rule}")
    else:
        lines.append("No threshold rules fired.")
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
    triggered_rules: Optional[List[str]] = None,
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
    triggered_rules:
        List of rule description strings that fired. Stored under
        recommendation.triggered_rules for auditability.
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
        "manifest_entries": metrics.manifest_entries,
        "missing_source_ids": metrics.missing_source_ids,
        "golden_qa_review_status": metrics.golden_qa_review_status,
        "is_draft": metrics.golden_qa_review_status != "reviewed",
        "recommendation": {
            "label": recommendation,
            "justification": rec_justification,
            "triggered_rules": triggered_rules or [],
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
    triggered_rules: Optional[List[str]] = None,
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
    triggered_rules:
        List of fired rule strings; passed through to both report formats.

    Returns
    -------
    tuple[Path, Path]
        (md_path, json_path) — absolute paths to the written files.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        date_str = metrics.run_ts[:10]
    except (IndexError, TypeError):
        from datetime import date
        date_str = date.today().isoformat()

    suffix = "_draft" if metrics.golden_qa_review_status != "reviewed" else ""
    md_path = output_dir / f"{date_str}_benchmark_report{suffix}.md"
    json_path = output_dir / f"{date_str}_benchmark_report{suffix}.json"

    md_content = generate_markdown_report(
        metrics, recommendation, rec_justification, triggered_rules
    )
    with md_path.open("w", encoding="utf-8") as fh:
        fh.write(md_content)

    json_content = generate_json_report(
        metrics, recommendation, rec_justification, triggered_rules
    )
    with json_path.open("w", encoding="utf-8") as fh:
        json.dump(json_content, fh, indent=2)

    return (md_path, json_path)
