"""RIS operator metrics aggregation -- local-first, no network, no ClickHouse.

Reads from:
  - KnowledgeStore SQLite (source_documents, derived_claims) via direct sqlite3
  - eval_artifacts.jsonl (gate decision distribution, ingestion by family)
  - precheck_ledger.jsonl (GO/CAUTION/STOP counts)
  - report_index.jsonl (report counts by type)
  - acquisition_review JSONL (ingest counts, dedup, errors)

ClickHouse export is deferred to a future RIS_06 v2 work item.
Grafana integration: write metrics_snapshot.json to artifacts/research/;
  use Grafana JSON file data source or Infinity plugin to poll this file.
"""

from __future__ import annotations

import dataclasses
import json
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Default paths (mirror the defaults in the source modules)
# ---------------------------------------------------------------------------

_DEFAULT_KS_DB_PATH = Path("kb") / "rag" / "knowledge" / "knowledge.sqlite3"
_DEFAULT_EVAL_ARTIFACTS_DIR = Path("artifacts/research/eval_artifacts")
_DEFAULT_PRECHECK_LEDGER_PATH = Path("artifacts/research/prechecks/precheck_ledger.jsonl")
_DEFAULT_REPORT_DIR = Path("artifacts/research/reports")
_DEFAULT_ACQUISITION_REVIEW_DIR = Path("artifacts/research/acquisition_reviews")


# ---------------------------------------------------------------------------
# RisMetricsSnapshot dataclass
# ---------------------------------------------------------------------------

@dataclass
class RisMetricsSnapshot:
    """Aggregated RIS pipeline health metrics snapshot.

    All numeric fields are int (never None). Dict fields are empty dicts when
    no data is available.
    """

    generated_at: str
    total_docs: int
    total_claims: int
    docs_by_family: dict
    gate_distribution: dict
    ingestion_by_family: dict
    precheck_decisions: dict
    reports_by_type: dict
    total_reports: int
    acquisition_new: int
    acquisition_cached: int
    acquisition_errors: int

    def to_dict(self) -> dict:
        """Return a fully JSON-serializable dict representation."""
        return dataclasses.asdict(self)


# ---------------------------------------------------------------------------
# Internal JSONL helper (inlined to avoid circular imports)
# ---------------------------------------------------------------------------

def _iter_jsonl(path: Path):
    """Yield parsed dicts from a JSONL file, skipping blank/invalid lines.

    Returns an empty iterator if the file does not exist.
    """
    if not path.exists():
        return
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        try:
            payload = json.loads(stripped)
            if isinstance(payload, dict):
                yield payload
        except json.JSONDecodeError:
            continue


# ---------------------------------------------------------------------------
# Aggregation function
# ---------------------------------------------------------------------------

def collect_ris_metrics(
    *,
    db_path: Optional[Path] = None,
    eval_artifacts_dir: Optional[Path] = None,
    precheck_ledger_path: Optional[Path] = None,
    report_dir: Optional[Path] = None,
    acquisition_review_dir: Optional[Path] = None,
) -> RisMetricsSnapshot:
    """Collect RIS pipeline metrics from local artifacts.

    All path arguments default to the canonical defaults used by the
    underlying modules. Pass overrides to redirect to test fixtures.

    Args:
        db_path: Path to knowledge.sqlite3. Defaults to the KnowledgeStore default.
        eval_artifacts_dir: Directory containing eval_artifacts.jsonl.
        precheck_ledger_path: Path to precheck_ledger.jsonl.
        report_dir: Directory containing report_index.jsonl.
        acquisition_review_dir: Directory containing acquisition_review.jsonl.

    Returns:
        RisMetricsSnapshot with all counts populated (zeros when data is absent).
    """
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()

    # Resolve paths
    ks_path = Path(db_path) if db_path is not None else _DEFAULT_KS_DB_PATH
    ea_dir = Path(eval_artifacts_dir) if eval_artifacts_dir is not None else _DEFAULT_EVAL_ARTIFACTS_DIR
    pl_path = Path(precheck_ledger_path) if precheck_ledger_path is not None else _DEFAULT_PRECHECK_LEDGER_PATH
    rd_path = Path(report_dir) if report_dir is not None else _DEFAULT_REPORT_DIR
    ar_dir = Path(acquisition_review_dir) if acquisition_review_dir is not None else _DEFAULT_ACQUISITION_REVIEW_DIR

    # --- KnowledgeStore stats ---
    total_docs = 0
    total_claims = 0
    docs_by_family: dict[str, int] = {}

    if ks_path.exists():
        try:
            conn = sqlite3.connect(str(ks_path))
            try:
                rows = conn.execute(
                    "SELECT source_family, COUNT(*) FROM source_documents GROUP BY source_family"
                ).fetchall()
                for family, count in rows:
                    fam = family if family else "unknown"
                    docs_by_family[fam] = int(count)
                    total_docs += int(count)

                claims_row = conn.execute(
                    "SELECT COUNT(*) FROM derived_claims"
                ).fetchone()
                if claims_row:
                    total_claims = int(claims_row[0])
            finally:
                conn.close()
        except (sqlite3.Error, OSError):
            # Gracefully handle any DB errors
            pass

    # --- Eval artifacts stats ---
    gate_distribution: dict[str, int] = {}
    ingestion_by_family: dict[str, int] = {}

    # Use load_eval_artifacts from the evaluation module
    from packages.research.evaluation.artifacts import load_eval_artifacts
    artifacts = load_eval_artifacts(ea_dir)
    for artifact in artifacts:
        gate = artifact.get("gate", "")
        if gate:
            gate_distribution[gate] = gate_distribution.get(gate, 0) + 1
        fam = artifact.get("source_family", "")
        if fam:
            ingestion_by_family[fam] = ingestion_by_family.get(fam, 0) + 1

    # --- Precheck ledger stats ---
    precheck_decisions: dict[str, int] = {"GO": 0, "CAUTION": 0, "STOP": 0}
    for event in _iter_jsonl(pl_path):
        # The real ledger uses event_type="precheck_run"; handle both variants
        etype = event.get("event_type", "")
        if etype in ("precheck_run", "precheck"):
            rec = event.get("recommendation", "")
            if rec in precheck_decisions:
                precheck_decisions[rec] += 1

    # --- Report index stats ---
    reports_by_type: dict[str, int] = {}
    total_reports = 0
    index_path = rd_path / "report_index.jsonl"
    for entry in _iter_jsonl(index_path):
        rtype = entry.get("report_type", "")
        if rtype:
            reports_by_type[rtype] = reports_by_type.get(rtype, 0) + 1
        total_reports += 1

    # --- Acquisition review stats ---
    acquisition_new = 0
    acquisition_cached = 0
    acquisition_errors = 0
    from packages.research.ingestion.acquisition_review import AcquisitionReviewWriter
    arw = AcquisitionReviewWriter(ar_dir)
    for review in arw.read_reviews():
        has_error = review.get("error") is not None
        if has_error:
            acquisition_errors += 1
        else:
            status = review.get("dedup_status", "")
            if status == "new":
                acquisition_new += 1
            elif status == "cached":
                acquisition_cached += 1

    return RisMetricsSnapshot(
        generated_at=generated_at,
        total_docs=total_docs,
        total_claims=total_claims,
        docs_by_family=docs_by_family,
        gate_distribution=gate_distribution,
        ingestion_by_family=ingestion_by_family,
        precheck_decisions=precheck_decisions,
        reports_by_type=reports_by_type,
        total_reports=total_reports,
        acquisition_new=acquisition_new,
        acquisition_cached=acquisition_cached,
        acquisition_errors=acquisition_errors,
    )


# ---------------------------------------------------------------------------
# Human-readable formatter
# ---------------------------------------------------------------------------

def format_metrics_summary(snapshot: RisMetricsSnapshot) -> str:
    """Return a compact multi-line human-readable summary of a RisMetricsSnapshot.

    Returns:
        Multi-line string with section headers: Knowledge Store, Eval Gate,
        Prechecks, Reports, Acquisition.
    """
    lines = []
    lines.append("=== RIS Metrics Snapshot ===")
    lines.append(f"Generated: {snapshot.generated_at}")
    lines.append("")

    # Knowledge Store
    lines.append("[Knowledge Store]")
    family_str = "  ".join(
        f"{k}={v}" for k, v in sorted(snapshot.docs_by_family.items())
    )
    if family_str:
        lines.append(f"  Documents : {snapshot.total_docs}  (by family: {family_str})")
    else:
        lines.append(f"  Documents : {snapshot.total_docs}")
    lines.append(f"  Claims    : {snapshot.total_claims}")
    lines.append("")

    # Eval Gate
    lines.append("[Eval Gate]")
    gd = snapshot.gate_distribution
    accept = gd.get("ACCEPT", 0)
    review = gd.get("REVIEW", 0)
    reject = gd.get("REJECT", 0)
    lines.append(f"  ACCEPT={accept}  REVIEW={review}  REJECT={reject}")
    family_str2 = "  ".join(
        f"{k}={v}" for k, v in sorted(snapshot.ingestion_by_family.items())
    )
    if family_str2:
        lines.append(f"  By family: {family_str2}")
    lines.append("")

    # Prechecks
    lines.append("[Prechecks]")
    pd = snapshot.precheck_decisions
    lines.append(
        f"  GO={pd.get('GO', 0)}  CAUTION={pd.get('CAUTION', 0)}  STOP={pd.get('STOP', 0)}"
    )
    lines.append("")

    # Reports
    lines.append("[Reports]")
    rbt = snapshot.reports_by_type
    type_str = "  ".join(f"{k}={v}" for k, v in sorted(rbt.items()))
    if type_str:
        lines.append(f"  Total={snapshot.total_reports}  ({type_str})")
    else:
        lines.append(f"  Total={snapshot.total_reports}")
    lines.append("")

    # Acquisition
    lines.append("[Acquisition]")
    lines.append(
        f"  New={snapshot.acquisition_new}  "
        f"Cached={snapshot.acquisition_cached}  "
        f"Errors={snapshot.acquisition_errors}"
    )

    return "\n".join(lines)
