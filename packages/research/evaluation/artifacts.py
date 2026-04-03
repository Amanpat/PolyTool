"""RIS Phase 3 — structured eval artifact persistence.

Provides EvalArtifact dataclass and JSONL-based persistence helpers for
recording every evaluation run's structured output. Artifacts capture
gate decisions, hard-stop results, near-duplicate checks, and family
features in a queryable, append-only log.

Phase 5 additions (backward compatible):
- ProviderEvent dataclass for replay-grade metadata on every scoring event.
- EvalArtifact gains optional provider_event and event_id fields (None for old records).
- generate_event_id() and compute_output_hash() helpers.

File layout:
    {artifacts_dir}/eval_artifacts.jsonl

Each line is a JSON object corresponding to one EvalArtifact.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

_ARTIFACT_FILENAME = "eval_artifacts.jsonl"


@dataclass
class ProviderEvent:
    """Replay-grade metadata for a single LLM provider scoring call.

    Captures everything needed to reproduce or audit an evaluation event:
    provider identity, model, prompt template version, generation params,
    source references, and content hashes for the prompt and output.

    Attributes:
        provider_name: Provider identifier (e.g., "manual", "ollama", "gemini").
        model_id: Model identifier within the provider (e.g., "qwen3:30b").
        prompt_template_id: Identifier for the prompt template used (e.g., "scoring_v1").
        prompt_template_version: First 12 hex chars of sha256(prompt_text).
            Detects prompt drift across runs even when template ID is unchanged.
        generation_params: Provider-specific generation parameters (e.g., format, stream).
        source_chunk_refs: List of doc_id or chunk references fed into the prompt.
        timestamp: ISO-8601 UTC timestamp of the scoring call.
        output_hash: First 16 hex chars of sha256(raw_output). Allows detecting
            output changes between replay runs.
        raw_output: The raw provider output string. None by default to keep
            artifact size small; set explicitly when auditing output content.
    """

    provider_name: str
    model_id: str
    prompt_template_id: str
    prompt_template_version: str
    generation_params: dict
    source_chunk_refs: List[str]
    timestamp: str
    output_hash: str
    raw_output: Optional[str] = field(default=None)


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
        provider_event: Serialized ProviderEvent dict (Phase 5+). None for older
            artifacts that predate Phase 5, or for hard-stop/dedup paths where
            no scoring occurred.
        event_id: Unique identifier for this eval event (Phase 5+). sha256 of
            doc_id + timestamp + provider_name, first 16 hex chars. None for
            older artifacts.
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
    # Phase 5 additions — Optional with default=None for backward compatibility
    provider_event: Optional[dict] = field(default=None)
    event_id: Optional[str] = field(default=None)


def generate_event_id(doc_id: str, timestamp: str, provider_name: str) -> str:
    """Generate a unique event ID for an eval scoring event.

    Computes sha256(f"{doc_id}\\0{timestamp}\\0{provider_name}") and returns the
    first 16 hex characters. The null-byte delimiter prevents accidental collisions
    between concatenated substrings.

    Args:
        doc_id: Document identifier.
        timestamp: ISO-8601 UTC timestamp of the event.
        provider_name: Provider identifier (e.g., "manual", "ollama").

    Returns:
        16-character hex string that uniquely identifies this eval event.
    """
    key = f"{doc_id}\0{timestamp}\0{provider_name}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]


def compute_output_hash(raw_output: str) -> str:
    """Compute a short content hash for a raw provider output string.

    Used in ProviderEvent to detect output differences between replay runs
    with the same prompt but different providers or model versions.

    Args:
        raw_output: The raw string returned by the provider's score() call.

    Returns:
        First 16 hex characters of sha256(raw_output.encode("utf-8")).
    """
    return hashlib.sha256(raw_output.encode("utf-8")).hexdigest()[:16]


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
