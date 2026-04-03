"""RIS v1 synthesis — append-only JSONL report ledger.

Replicates the JSONL pattern from packages/research/synthesis/precheck_ledger.py.

Reports are saved as markdown files under artifacts/research/reports/ with a
lightweight JSONL index for list and search operations. No ClickHouse dependency
in this pass; ClickHouse indexing is deferred to a future RIS_06 work item.

Schema versions:
- report_ledger_v1: initial schema
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterator, Optional

REPORT_LEDGER_SCHEMA_VERSION = "report_ledger_v1"
DEFAULT_REPORT_DIR = Path("artifacts/research/reports")
DEFAULT_REPORT_INDEX_FILENAME = "report_index.jsonl"

VALID_REPORT_TYPES = frozenset({
    "precheck_summary",
    "eval_summary",
    "weekly_digest",
    "custom",
})


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _iso_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat()


def _make_report_id(title: str, iso_timestamp: str) -> str:
    """Generate a short deterministic report ID from title and timestamp."""
    key = f"{title}\x00{iso_timestamp}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:12]


def _iter_index(index_path: Path) -> Iterator[dict]:
    """Yield parsed dicts from the JSONL index file, skipping blank/invalid lines."""
    if not index_path.exists():
        return
    for line in index_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        try:
            payload = json.loads(stripped)
            if isinstance(payload, dict):
                yield payload
        except json.JSONDecodeError:
            continue


@dataclass
class ReportEntry:
    """Index record for a persisted report artifact.

    Attributes:
        report_id: sha256(title + timestamp)[:12] — short deterministic ID.
        title: Human-readable title for the report.
        report_type: One of "precheck_summary", "eval_summary", "weekly_digest", "custom".
        created_at: ISO-8601 UTC timestamp of when the report was created.
        artifact_path: Relative path to the markdown file on disk.
        source_window: Time window covered (e.g., "7d", "30d", "all").
        summary_line: One-line summary for list display (truncated to 200 chars).
        tags: Searchable lowercase tags.
        metadata: Arbitrary extra metadata dict.
        schema_version: Ledger schema version.
    """

    report_id: str
    title: str
    report_type: str
    created_at: str
    artifact_path: str
    source_window: str
    summary_line: str
    tags: list = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    schema_version: str = REPORT_LEDGER_SCHEMA_VERSION


def persist_report(
    title: str,
    body_md: str,
    report_type: str = "custom",
    source_window: str = "all",
    summary_line: str = "",
    tags: Optional[list] = None,
    metadata: Optional[dict] = None,
    report_dir: Optional[Path] = None,
) -> ReportEntry:
    """Persist a report as a markdown artifact and append its entry to the JSONL index.

    Creates parent directories and the index file if they do not exist.

    Args:
        title: Human-readable title for the report.
        body_md: Markdown body of the report.
        report_type: One of VALID_REPORT_TYPES (default "custom").
        source_window: Time window the report covers (e.g., "7d", "all").
        summary_line: One-line summary; defaults to first 80 chars of body_md.
        tags: List of searchable string tags.
        metadata: Arbitrary extra metadata dict.
        report_dir: Directory for reports. Defaults to DEFAULT_REPORT_DIR.

    Returns:
        The persisted ReportEntry.
    """
    rdir = Path(report_dir) if report_dir is not None else DEFAULT_REPORT_DIR
    rdir.mkdir(parents=True, exist_ok=True)

    now = _utcnow()
    iso_ts = _iso_utc(now)
    report_id = _make_report_id(title, iso_ts)

    date_prefix = now.strftime("%Y-%m-%d")
    md_filename = f"{date_prefix}_{report_id}.md"
    artifact_path = rdir / md_filename

    # Write markdown file
    artifact_path.write_text(body_md, encoding="utf-8")

    # Compute summary_line default
    if not summary_line:
        first_line = body_md.strip().split("\n")[0] if body_md.strip() else ""
        # Strip leading markdown heading markers
        first_line = first_line.lstrip("# ").strip()
        summary_line = first_line[:200] if first_line else "(no summary)"

    entry = ReportEntry(
        report_id=report_id,
        title=title,
        report_type=report_type,
        created_at=iso_ts,
        artifact_path=str(rdir / md_filename),
        source_window=source_window,
        summary_line=summary_line[:200],
        tags=[str(t).lower() for t in (tags or [])],
        metadata=metadata or {},
        schema_version=REPORT_LEDGER_SCHEMA_VERSION,
    )

    index_path = rdir / DEFAULT_REPORT_INDEX_FILENAME
    row = json.dumps(
        dataclasses.asdict(entry),
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    with index_path.open("a", encoding="utf-8") as fh:
        fh.write(row + "\n")

    return entry


def list_reports(
    report_dir: Optional[Path] = None,
    window_start: Optional[str] = None,
    window_end: Optional[str] = None,
) -> list[dict]:
    """Read all report entries from the JSONL index.

    Args:
        report_dir: Directory for reports. Defaults to DEFAULT_REPORT_DIR.
        window_start: Inclusive ISO-8601 lower bound for created_at filtering.
        window_end: Inclusive ISO-8601 upper bound for created_at filtering.

    Returns:
        List of dicts sorted by created_at descending. Empty list if index missing.
    """
    rdir = Path(report_dir) if report_dir is not None else DEFAULT_REPORT_DIR
    index_path = rdir / DEFAULT_REPORT_INDEX_FILENAME

    results = []
    for entry in _iter_index(index_path):
        created_at = entry.get("created_at", "")
        if window_start and created_at and created_at < window_start:
            continue
        if window_end and created_at and created_at > window_end:
            continue
        results.append(entry)

    results.sort(key=lambda e: e.get("created_at", ""), reverse=True)
    return results


def search_reports(
    query: str,
    report_dir: Optional[Path] = None,
) -> list[dict]:
    """Search reports by keyword (case-insensitive substring).

    Searches title, summary_line, and tags fields.

    Args:
        query: Search keyword or phrase.
        report_dir: Directory for reports. Defaults to DEFAULT_REPORT_DIR.

    Returns:
        List of matching dicts sorted by created_at descending.
    """
    rdir = Path(report_dir) if report_dir is not None else DEFAULT_REPORT_DIR
    index_path = rdir / DEFAULT_REPORT_INDEX_FILENAME

    query_lower = query.lower()
    results = []
    for entry in _iter_index(index_path):
        title_match = query_lower in entry.get("title", "").lower()
        summary_match = query_lower in entry.get("summary_line", "").lower()
        tags = entry.get("tags", [])
        tags_text = " ".join(str(t) for t in tags).lower()
        tag_match = query_lower in tags_text
        if title_match or summary_match or tag_match:
            results.append(entry)

    results.sort(key=lambda e: e.get("created_at", ""), reverse=True)
    return results


def generate_digest(
    window_days: int = 7,
    report_dir: Optional[Path] = None,
    precheck_ledger_path: Optional[Path] = None,
    eval_artifacts_dir: Optional[Path] = None,
) -> ReportEntry:
    """Generate a weekly (or arbitrary-window) digest from recent RIS data.

    Loads prechecks, eval artifacts, and previous reports from the given window,
    then builds and persists a markdown digest.

    Args:
        window_days: Number of days to look back (default 7).
        report_dir: Directory for reports. Defaults to DEFAULT_REPORT_DIR.
        precheck_ledger_path: Path to precheck JSONL ledger. Defaults to
            packages/research/synthesis/precheck_ledger.DEFAULT_LEDGER_PATH.
        eval_artifacts_dir: Directory containing eval_artifacts.jsonl. Defaults to
            "artifacts/research/eval_artifacts".

    Returns:
        The persisted ReportEntry for the digest.
    """
    rdir = Path(report_dir) if report_dir is not None else DEFAULT_REPORT_DIR

    from packages.research.synthesis.precheck_ledger import (
        DEFAULT_LEDGER_PATH,
        list_prechecks_by_window,
    )
    from packages.research.evaluation.artifacts import load_eval_artifacts

    pcheck_path = Path(precheck_ledger_path) if precheck_ledger_path else DEFAULT_LEDGER_PATH
    eval_dir = Path(eval_artifacts_dir) if eval_artifacts_dir else Path("artifacts/research/eval_artifacts")

    now = _utcnow()
    window_start = _iso_utc(now - timedelta(days=window_days))
    window_end = _iso_utc(now)

    # Load data
    prechecks = list_prechecks_by_window(window_start, window_end, ledger_path=pcheck_path)
    all_eval_artifacts = load_eval_artifacts(eval_dir)

    # Filter eval artifacts by timestamp
    eval_artifacts = [
        a for a in all_eval_artifacts
        if a.get("timestamp", "") >= window_start
    ]

    # Load reports in window
    recent_reports = list_reports(
        report_dir=rdir,
        window_start=window_start,
        window_end=window_end,
    )

    # Count prechecks by recommendation
    precheck_run_events = [p for p in prechecks if p.get("event_type") == "precheck_run"]
    rec_counts: dict[str, int] = {}
    for p in precheck_run_events:
        rec = p.get("recommendation", "UNKNOWN")
        rec_counts[rec] = rec_counts.get(rec, 0) + 1

    override_events = [p for p in prechecks if p.get("event_type") == "override"]
    stale_count = sum(1 for p in precheck_run_events if p.get("stale_warning"))

    # Count eval artifacts by gate
    gate_counts: dict[str, int] = {}
    for a in eval_artifacts:
        gate = a.get("gate", "UNKNOWN")
        gate_counts[gate] = gate_counts.get(gate, 0) + 1

    # Build markdown
    date_range_label = f"{window_start[:10]} to {window_end[:10]}"
    lines = [
        f"# Weekly Digest — {date_range_label}",
        "",
        f"> Generated: {window_end}  |  Window: {window_days}d",
        "",
        "---",
        "",
        "## Prechecks",
        "",
    ]

    total_prechecks = len(precheck_run_events)
    if total_prechecks == 0:
        lines.append("No precheck runs in this window.")
    else:
        lines.append(f"**Total precheck runs:** {total_prechecks}")
        lines.append("")
        for rec in ["GO", "CAUTION", "STOP"]:
            count = rec_counts.get(rec, 0)
            lines.append(f"- {rec}: {count}")
        other_recs = {k: v for k, v in rec_counts.items() if k not in {"GO", "CAUTION", "STOP"}}
        for rec, count in sorted(other_recs.items()):
            lines.append(f"- {rec}: {count}")
        lines.append("")

        if stale_count > 0:
            lines.append(f"**Stale warnings:** {stale_count} precheck(s) triggered stale data warning.")
            lines.append("")

        lines.append("### Ideas evaluated")
        lines.append("")
        for p in precheck_run_events:
            idea = p.get("idea", "(no idea)")
            rec = p.get("recommendation", "?")
            lines.append(f"- [{rec}] {idea}")

    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## Evaluations")
    lines.append("")

    total_evals = len(eval_artifacts)
    if total_evals == 0:
        lines.append("No evaluation artifacts in this window.")
    else:
        lines.append(f"**Total evaluations:** {total_evals}")
        lines.append("")
        for gate in ["ACCEPT", "REVIEW", "REJECT"]:
            count = gate_counts.get(gate, 0)
            lines.append(f"- {gate}: {count}")
        other_gates = {k: v for k, v in gate_counts.items() if k not in {"ACCEPT", "REVIEW", "REJECT"}}
        for gate, count in sorted(other_gates.items()):
            lines.append(f"- {gate}: {count}")

    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## Reports Generated")
    lines.append("")

    if not recent_reports:
        lines.append("No reports generated in this window (not counting this digest).")
    else:
        for r in recent_reports:
            rtitle = r.get("title", "(untitled)")
            rtype = r.get("report_type", "custom")
            rcreated = r.get("created_at", "")[:10]
            lines.append(f"- [{rcreated}] **{rtitle}** ({rtype})")

    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## Key Observations")
    lines.append("")

    observations = []
    if stale_count > 0:
        observations.append(
            f"{stale_count} precheck(s) flagged stale supporting evidence — "
            "consider refreshing the knowledge store."
        )
    if override_events:
        observations.append(
            f"{len(override_events)} operator override(s) recorded in this window."
        )
    if not observations:
        observations.append("No notable anomalies detected.")

    for obs in observations:
        lines.append(f"- {obs}")

    lines.append("")

    body_md = "\n".join(lines)

    # Count for summary line
    summary_line = (
        f"Prechecks: {total_prechecks} "
        f"(GO={rec_counts.get('GO', 0)}, "
        f"CAUTION={rec_counts.get('CAUTION', 0)}, "
        f"STOP={rec_counts.get('STOP', 0)}), "
        f"Evals: {total_evals}, "
        f"Reports: {len(recent_reports)}"
    )

    title = f"Weekly Digest {date_range_label}"

    return persist_report(
        title=title,
        body_md=body_md,
        report_type="weekly_digest",
        source_window=f"{window_days}d",
        summary_line=summary_line,
        tags=["digest", "automated"],
        metadata={
            "window_days": window_days,
            "window_start": window_start,
            "window_end": window_end,
            "precheck_count": total_prechecks,
            "eval_count": total_evals,
            "report_count": len(recent_reports),
            "override_count": len(override_events),
            "stale_count": stale_count,
        },
        report_dir=rdir,
    )
