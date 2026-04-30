"""Corpus manifest loader for the Scientific RAG Evaluation Benchmark v0.

Loads and validates the corpus manifest JSON that defines the set of documents
used for evaluation. The manifest identifies source documents by their IDs in
the KnowledgeStore, along with metadata for each entry.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional


VALID_CATEGORIES = {"equation_heavy", "table_heavy", "prose_heavy", "outlier", None}


class CorpusValidationError(ValueError):
    """Raised when a corpus manifest fails validation."""


@dataclass
class CorpusEntry:
    source_id: str
    title: Optional[str] = None
    category: Optional[str] = None
    tags: List[str] = field(default_factory=list)


@dataclass
class CorpusManifest:
    version: str
    review_status: str
    seed_topic_keywords: List[str]
    entries: List[CorpusEntry]
    freeze_date: Optional[str] = None
    description: Optional[str] = None


def load_corpus_manifest(path: Path) -> CorpusManifest:
    """Load and validate a corpus manifest JSON file.

    Parameters
    ----------
    path:
        Path to the JSON manifest file.

    Returns
    -------
    CorpusManifest

    Raises
    ------
    CorpusValidationError
        If the manifest is missing required fields or contains invalid data.
    FileNotFoundError
        If the path does not exist.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Corpus manifest not found: {path}")

    try:
        with path.open("r", encoding="utf-8") as fh:
            raw = json.load(fh)
    except json.JSONDecodeError as exc:
        raise CorpusValidationError(f"Invalid JSON in corpus manifest: {exc}") from exc

    if not isinstance(raw, dict):
        raise CorpusValidationError("Corpus manifest must be a JSON object")

    # Required top-level fields
    for required in ("version", "review_status", "seed_topic_keywords", "entries"):
        if required not in raw:
            raise CorpusValidationError(
                f"Corpus manifest missing required field: '{required}'"
            )

    version = raw["version"]
    if not isinstance(version, str) or not version:
        raise CorpusValidationError("'version' must be a non-empty string")

    review_status = raw["review_status"]
    if not isinstance(review_status, str):
        raise CorpusValidationError("'review_status' must be a string")

    seed_keywords = raw["seed_topic_keywords"]
    if not isinstance(seed_keywords, list):
        raise CorpusValidationError("'seed_topic_keywords' must be a list")

    entries_raw = raw["entries"]
    if not isinstance(entries_raw, list):
        raise CorpusValidationError("'entries' must be a list")

    entries: List[CorpusEntry] = []
    for i, entry_raw in enumerate(entries_raw):
        if not isinstance(entry_raw, dict):
            raise CorpusValidationError(f"Entry {i} must be a JSON object")
        if "source_id" not in entry_raw:
            raise CorpusValidationError(f"Entry {i} missing required field 'source_id'")

        category = entry_raw.get("category", None)
        if category not in VALID_CATEGORIES:
            raise CorpusValidationError(
                f"Entry {i} has invalid category '{category}'. "
                f"Valid categories: {sorted(c for c in VALID_CATEGORIES if c is not None)}"
            )

        entries.append(
            CorpusEntry(
                source_id=str(entry_raw["source_id"]),
                title=entry_raw.get("title", None),
                category=category,
                tags=list(entry_raw.get("tags", [])),
            )
        )

    return CorpusManifest(
        version=version,
        review_status=review_status,
        seed_topic_keywords=list(seed_keywords),
        entries=entries,
        freeze_date=raw.get("freeze_date", None),
        description=raw.get("description", None),
    )
