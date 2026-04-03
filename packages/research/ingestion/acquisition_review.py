"""RIS Phase 5 -- acquisition review writer.

Maintains an append-only JSONL audit log of every source acquisition attempt,
recording metadata, dedup status, cached path, and any error that occurred.

Usage:
    writer = AcquisitionReviewWriter("artifacts/research/acquisition_reviews")
    record = AcquisitionRecord(
        acquired_at="2026-04-02T10:00:00Z",
        source_url="https://arxiv.org/abs/2301.12345",
        source_family="academic",
        source_id="abc123def456abcd",
        canonical_ids={"arxiv_id": "2301.12345"},
        cached_path="artifacts/research/raw_source_cache/academic/abc123def456abcd.json",
        normalized_title="Test Paper",
        dedup_status="new",
        error=None,
    )
    path = writer.write_review(record)
    all_reviews = writer.read_reviews()
"""

from __future__ import annotations

import dataclasses
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# AcquisitionRecord
# ---------------------------------------------------------------------------


@dataclass
class AcquisitionRecord:
    """Structured record of a single source acquisition attempt.

    Attributes
    ----------
    acquired_at:
        UTC ISO-8601 timestamp when acquisition was attempted.
    source_url:
        Original URL supplied by the operator.
    source_family:
        Source family (academic, github, blog, news).
    source_id:
        Deterministic 16-char SHA-256 ID computed from canonical URL.
    canonical_ids:
        Dict of extracted identifiers (arxiv_id, doi, ssrn_id, repo_url).
    cached_path:
        Path to the cached raw payload on disk (str), or "" if not cached.
    normalized_title:
        Title as extracted by the fetcher / adapter.
    dedup_status:
        "new" if source_id was not previously cached; "cached" if duplicate.
    error:
        Error message string if acquisition failed, otherwise None.
    """

    acquired_at: str
    source_url: str
    source_family: str
    source_id: str
    canonical_ids: dict
    cached_path: str
    normalized_title: str
    dedup_status: str
    error: Optional[str]


# ---------------------------------------------------------------------------
# AcquisitionReviewWriter
# ---------------------------------------------------------------------------


class AcquisitionReviewWriter:
    """Append-only JSONL writer for acquisition review records.

    Parameters
    ----------
    review_dir:
        Directory where ``acquisition_review.jsonl`` will be written.
        Created automatically on first write if it does not exist.
    """

    def __init__(self, review_dir: "str | Path") -> None:
        self._root = Path(review_dir)

    @property
    def _review_path(self) -> Path:
        return self._root / "acquisition_review.jsonl"

    def write_review(self, record: AcquisitionRecord) -> Path:
        """Append *record* as a single JSON line to the review JSONL file.

        Parameters
        ----------
        record:
            An AcquisitionRecord dataclass instance.

        Returns
        -------
        Path
            Path to the JSONL file (created or appended-to).
        """
        self._root.mkdir(parents=True, exist_ok=True)
        line = json.dumps(dataclasses.asdict(record), ensure_ascii=False) + "\n"
        with self._review_path.open("a", encoding="utf-8") as fh:
            fh.write(line)
        return self._review_path

    def read_reviews(self) -> list[dict]:
        """Read all review records from the JSONL file.

        Returns
        -------
        list[dict]
            Each element corresponds to one written AcquisitionRecord.
            Returns an empty list if the file does not exist.
        """
        if not self._review_path.exists():
            return []
        records = []
        with self._review_path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    try:
                        records.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        return records
