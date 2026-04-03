"""RIS Phase 5 — replay/compare workflow for evaluation artifacts.

Provides the ability to re-run a prior evaluation on the same document with a
different provider or prompt template and produce a structured diff artifact.
Used for A/B provider comparison and auditing evaluation drift over time.

Key entry points:
- replay_eval(): run evaluation for a document, return (GateDecision, provider_event)
- compare_eval_events(): diff two artifact records to produce a ReplayDiff
- persist_replay_diff(): write diff JSON to {artifacts_dir}/replay_diffs/
- load_replay_diffs(): load all diff records from the replay_diffs/ subdirectory
- find_artifact_by_event_id(): scan JSONL for a matching event_id
"""

from __future__ import annotations

import dataclasses
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Score dimension keys for comparison
_SCORE_DIMS = ("relevance", "novelty", "actionability", "credibility", "total")


@dataclass
class ReplayDiff:
    """Structured diff between an original evaluation and a replay evaluation.

    Attributes:
        original_event_id: event_id from the original EvalArtifact (or doc_id fallback).
        replay_timestamp: ISO-8601 UTC timestamp when the replay was run.
        original_output: Scores dict from the original artifact (or None).
        replay_output: Scores dict from the replay artifact (or None).
        diff_fields: Dict of {field_name: {"original": val, "replay": val}}
            for every scoring dimension where the two artifacts differ.
        provider_original: Provider name from the original artifact.
        provider_replay: Provider name from the replay artifact.
        prompt_template_original: prompt_template_id from original provider_event.
        prompt_template_replay: prompt_template_id from replay provider_event.
        original_gate: Gate decision from the original artifact.
        replay_gate: Gate decision from the replay artifact.
        gate_changed: True if original_gate != replay_gate.
    """

    original_event_id: str
    replay_timestamp: str
    original_output: Optional[Dict]
    replay_output: Optional[Dict]
    diff_fields: Dict
    provider_original: str
    provider_replay: str
    prompt_template_original: str
    prompt_template_replay: str
    original_gate: str
    replay_gate: str
    gate_changed: bool


def replay_eval(
    doc,
    provider_name: str = "manual",
    artifacts_dir: Optional[Path] = None,
    **kwargs,
) -> Tuple:
    """Evaluate a document and return the gate decision and provider_event dict.

    Thin wrapper around DocumentEvaluator that also returns the provider_event
    metadata from the persisted artifact (if artifacts_dir is set).

    Args:
        doc: EvalDocument to evaluate.
        provider_name: Provider to use (default: "manual").
        artifacts_dir: Optional path for artifact persistence.
        **kwargs: Passed to get_provider() (e.g., model= for OllamaProvider).

    Returns:
        Tuple of (GateDecision, provider_event_dict or None).
        provider_event_dict is None if artifacts_dir is not set or no artifact
        was persisted (e.g., hard-stop path).
    """
    from packages.research.evaluation.providers import get_provider
    from packages.research.evaluation.evaluator import DocumentEvaluator
    from packages.research.evaluation.artifacts import load_eval_artifacts

    provider = get_provider(provider_name, **kwargs)
    artifacts_path = Path(artifacts_dir) if artifacts_dir is not None else None
    evaluator = DocumentEvaluator(provider=provider, artifacts_dir=artifacts_path)
    decision = evaluator.evaluate(doc)

    provider_event = None
    if artifacts_path is not None:
        loaded = load_eval_artifacts(artifacts_path)
        # Find the artifact for this doc_id (last match)
        matching = [a for a in loaded if a.get("doc_id") == doc.doc_id]
        if matching:
            provider_event = matching[-1].get("provider_event")

    return decision, provider_event


def compare_eval_events(
    original_artifact: dict,
    replay_artifact: dict,
) -> ReplayDiff:
    """Diff two eval artifact records and return a structured ReplayDiff.

    Compares scoring dimensions and gate decisions between the original and
    replay artifacts. Extracts provider metadata from provider_event when
    available; falls back to safe defaults for old artifacts without it.

    Args:
        original_artifact: Dict as loaded by load_eval_artifacts (original run).
        replay_artifact: Dict as loaded by load_eval_artifacts (replay run).

    Returns:
        ReplayDiff with diff_fields for changed scoring dimensions.
    """
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()

    # Extract event IDs (fall back to doc_id for old artifacts)
    original_event_id = (
        original_artifact.get("event_id")
        or original_artifact.get("doc_id", "unknown")
    )

    # Extract scores
    orig_scores = original_artifact.get("scores") or {}
    replay_scores = replay_artifact.get("scores") or {}

    # Compute diff_fields for scoring dimensions
    diff_fields: Dict = {}
    for dim in _SCORE_DIMS:
        orig_val = orig_scores.get(dim)
        replay_val = replay_scores.get(dim)
        if orig_val != replay_val:
            diff_fields[dim] = {"original": orig_val, "replay": replay_val}

    # Extract gate decisions
    original_gate = original_artifact.get("gate", "UNKNOWN")
    replay_gate = replay_artifact.get("gate", "UNKNOWN")
    gate_changed = original_gate != replay_gate

    # Extract provider metadata from provider_event (Phase 5+ artifacts)
    orig_pe = original_artifact.get("provider_event") or {}
    replay_pe = replay_artifact.get("provider_event") or {}

    provider_original = orig_pe.get("provider_name", "unknown")
    provider_replay = replay_pe.get("provider_name", "unknown")
    template_original = orig_pe.get("prompt_template_id", "unknown")
    template_replay = replay_pe.get("prompt_template_id", "unknown")

    return ReplayDiff(
        original_event_id=original_event_id,
        replay_timestamp=now,
        original_output=orig_scores if orig_scores else None,
        replay_output=replay_scores if replay_scores else None,
        diff_fields=diff_fields,
        provider_original=provider_original,
        provider_replay=provider_replay,
        prompt_template_original=template_original,
        prompt_template_replay=template_replay,
        original_gate=original_gate,
        replay_gate=replay_gate,
        gate_changed=gate_changed,
    )


def persist_replay_diff(diff: ReplayDiff, artifacts_dir: Path) -> Path:
    """Write a ReplayDiff as JSON to {artifacts_dir}/replay_diffs/.

    Filename: replay_{original_event_id}_{timestamp_slug}.json
    where timestamp_slug is the replay_timestamp with colons and pluses removed.

    Args:
        diff: The ReplayDiff to persist.
        artifacts_dir: Base artifacts directory.

    Returns:
        Path to the written JSON file.
    """
    artifacts_dir = Path(artifacts_dir)
    replay_dir = artifacts_dir / "replay_diffs"
    replay_dir.mkdir(parents=True, exist_ok=True)

    timestamp_slug = diff.replay_timestamp.replace(":", "").replace("+", "").replace("-", "")
    filename = f"replay_{diff.original_event_id}_{timestamp_slug}.json"
    out_path = replay_dir / filename

    out_path.write_text(
        json.dumps(dataclasses.asdict(diff), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return out_path


def load_replay_diffs(artifacts_dir: Path) -> List[dict]:
    """Load all replay diff JSON files from {artifacts_dir}/replay_diffs/.

    Args:
        artifacts_dir: Base artifacts directory containing replay_diffs/ subdirectory.

    Returns:
        List of dicts sorted by replay_timestamp ascending. Returns [] if no diffs exist.
    """
    replay_dir = Path(artifacts_dir) / "replay_diffs"
    if not replay_dir.exists():
        return []

    results = []
    for json_file in sorted(replay_dir.glob("*.json")):
        try:
            data = json.loads(json_file.read_text(encoding="utf-8"))
            results.append(data)
        except (json.JSONDecodeError, OSError):
            pass

    # Sort by replay_timestamp ascending (lexicographic works for ISO-8601)
    results.sort(key=lambda d: d.get("replay_timestamp", ""))
    return results


def find_artifact_by_event_id(
    event_id: str,
    artifacts_dir: Path,
) -> Optional[dict]:
    """Find an eval artifact by its event_id in the JSONL artifact log.

    Scans all artifacts in eval_artifacts.jsonl and returns the first match.
    Returns None if no artifact with the given event_id exists.

    Args:
        event_id: The event_id to search for (16-char hex string).
        artifacts_dir: Directory containing eval_artifacts.jsonl.

    Returns:
        Matching artifact dict or None.
    """
    from packages.research.evaluation.artifacts import load_eval_artifacts

    artifacts = load_eval_artifacts(Path(artifacts_dir))
    for artifact in artifacts:
        if artifact.get("event_id") == event_id:
            return artifact
    return None
