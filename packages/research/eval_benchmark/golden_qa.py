"""Golden QA set loader for the Scientific RAG Evaluation Benchmark v0.

Loads and validates the golden QA JSON that defines question-answer pairs
used to evaluate retrieval quality and answer correctness.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional


VALID_CATEGORIES = {
    "concept_definition",
    "formula_lookup",
    "empirical_finding",
    "methodology",
    "survey_question",
}

VALID_DIFFICULTIES = {"easy", "medium", "hard"}


class GoldenQAValidationError(ValueError):
    """Raised when a golden QA set fails validation."""


@dataclass
class QAPair:
    id: str
    question: str
    expected_paper_id: str
    expected_answer_substring: str
    category: str
    difficulty: str
    expected_section_or_page: Optional[str] = None


@dataclass
class GoldenQASet:
    version: str
    review_status: str
    pairs: List[QAPair]
    description: Optional[str] = None


def load_golden_qa(path: Path) -> GoldenQASet:
    """Load and validate a golden QA JSON file.

    Parameters
    ----------
    path:
        Path to the JSON file.

    Returns
    -------
    GoldenQASet

    Raises
    ------
    GoldenQAValidationError
        If the file is missing required fields or contains invalid data.
    FileNotFoundError
        If the path does not exist.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Golden QA file not found: {path}")

    try:
        with path.open("r", encoding="utf-8") as fh:
            raw = json.load(fh)
    except json.JSONDecodeError as exc:
        raise GoldenQAValidationError(f"Invalid JSON in golden QA file: {exc}") from exc

    if not isinstance(raw, dict):
        raise GoldenQAValidationError("Golden QA file must be a JSON object")

    # Required top-level fields
    for required in ("version", "review_status", "pairs"):
        if required not in raw:
            raise GoldenQAValidationError(
                f"Golden QA file missing required field: '{required}'"
            )

    version = raw["version"]
    if not isinstance(version, str) or not version:
        raise GoldenQAValidationError("'version' must be a non-empty string")

    review_status = raw["review_status"]
    if not isinstance(review_status, str):
        raise GoldenQAValidationError("'review_status' must be a string")

    pairs_raw = raw["pairs"]
    if not isinstance(pairs_raw, list):
        raise GoldenQAValidationError("'pairs' must be a list")

    pairs: List[QAPair] = []
    for i, pair_raw in enumerate(pairs_raw):
        if not isinstance(pair_raw, dict):
            raise GoldenQAValidationError(f"QA pair {i} must be a JSON object")

        # Required pair fields
        for required in (
            "id",
            "question",
            "expected_paper_id",
            "expected_answer_substring",
            "category",
            "difficulty",
        ):
            if required not in pair_raw:
                raise GoldenQAValidationError(
                    f"QA pair {i} missing required field '{required}'"
                )

        category = pair_raw["category"]
        if category not in VALID_CATEGORIES:
            raise GoldenQAValidationError(
                f"QA pair {i} has invalid category '{category}'. "
                f"Valid categories: {sorted(VALID_CATEGORIES)}"
            )

        difficulty = pair_raw["difficulty"]
        if difficulty not in VALID_DIFFICULTIES:
            raise GoldenQAValidationError(
                f"QA pair {i} has invalid difficulty '{difficulty}'. "
                f"Valid difficulties: {sorted(VALID_DIFFICULTIES)}"
            )

        pairs.append(
            QAPair(
                id=str(pair_raw["id"]),
                question=str(pair_raw["question"]),
                expected_paper_id=str(pair_raw["expected_paper_id"]),
                expected_answer_substring=str(pair_raw["expected_answer_substring"]),
                category=category,
                difficulty=difficulty,
                expected_section_or_page=pair_raw.get("expected_section_or_page", None),
            )
        )

    return GoldenQASet(
        version=version,
        review_status=review_status,
        pairs=pairs,
        description=raw.get("description", None),
    )


def is_reviewed(qa: GoldenQASet) -> bool:
    """Return True if the QA set has been operator-reviewed.

    Parameters
    ----------
    qa:
        The loaded GoldenQASet.

    Returns
    -------
    bool
        True if review_status == "reviewed", False otherwise.
    """
    return qa.review_status == "reviewed"
