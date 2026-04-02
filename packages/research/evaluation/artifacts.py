"""RIS Phase 3 — structured eval artifact persistence.

Provides EvalArtifact dataclass and JSONL-based persistence helpers for
recording every evaluation run's structured output. Artifacts capture
gate decisions, hard-stop results, near-duplicate checks, and family
features in a queryable, append-only log.

File layout:
    {artifacts_dir}/eval_artifacts.jsonl

Each line is a JSON object corresponding to one EvalArtifact.
"""

from __future__ import annotations

import dataclasses
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

_ARTIFACT_FILENAME = "eval_artifacts.jsonl"


@dataclass
class EvalArtifact:
    """Structured record of a single document evaluation run.

    Attributes:
        doc_id: Unique identifier for the document.
        timestamp: ISO-8601 UTC timestamp of the evaluation.
        gate: Gate decision ("ACCEPT", "REVIEW", or "REJECT").
        hard_stop_result: Serialized HardStopResult dict (or None if passed).
        near_duplicate_result: Serialized NearDuplicateResult dict (or None).
        family_features: Dict of feature names to values from feature extraction.
        scores: Serialized ScoringResult dict (or None if scoring was skipped).
        source_family: Source family label (e.g., "academic", "github").
        source_type: Raw source_type from the EvalDocument.
    """

    doc_id: str
    timestamp: str
    gate: str
    hard_stop_result: Optional[dict]
    near_duplicate_result: Optional[dict]
    family_features: dict
    scores: Optional[dict]
    source_family: str
    source_type: str


def persist_eval_artifact(artifact: EvalArtifact, artifacts_dir: Path) -> None:
    """Append an EvalArtifact to the JSONL artifact log.

    Creates the artifacts_dir and the JSONL file if they do not exist.
    Each call appends exactly one JSON line to the file.

    Args:
        artifact: The artifact to persist.
        artifacts_dir: Directory where eval_artifacts.jsonl will be written.
    """
    artifacts_dir = Path(artifacts_dir)
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    artifact_file = artifacts_dir / _ARTIFACT_FILENAME
    row = json.dumps(dataclasses.asdict(artifact), ensure_ascii=False)
    with artifact_file.open("a", encoding="utf-8") as fh:
        fh.write(row + "\n")


def load_eval_artifacts(artifacts_dir: Path) -> list[dict]:
    """Load all eval artifacts from the JSONL artifact log.

    Args:
        artifacts_dir: Directory containing eval_artifacts.jsonl.

    Returns:
        List of dicts, one per line in the JSONL file. Returns [] if the
        file does not exist or the directory does not exist.
    """
    artifacts_dir = Path(artifacts_dir)
    artifact_file = artifacts_dir / _ARTIFACT_FILENAME
    if not artifact_file.exists():
        return []
    results: list[dict] = []
    with artifact_file.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                try:
                    results.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return results
