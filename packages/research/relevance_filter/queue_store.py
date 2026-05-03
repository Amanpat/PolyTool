"""File-backed review queue and label store for the L3 prefetch relevance filter.

The review queue holds REVIEW-decision candidates held out of ingestion by
hold-review mode. The label store accumulates operator accept/reject decisions
for future SVM training data.

Artifact paths (gitignored under artifacts/**):
  - Review queue: artifacts/research/prefetch_review_queue/review_queue.jsonl
  - Label store:  artifacts/research/svm_filter_labels/labels.jsonl
"""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


_REPO_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_QUEUE_PATH = (
    _REPO_ROOT / "artifacts" / "research" / "prefetch_review_queue" / "review_queue.jsonl"
)
_DEFAULT_LABEL_PATH = (
    _REPO_ROOT / "artifacts" / "research" / "svm_filter_labels" / "labels.jsonl"
)


def candidate_id_from_url(source_url: str) -> str:
    """Derive a stable candidate_id from source_url using SHA-256."""
    return hashlib.sha256(source_url.encode("utf-8")).hexdigest()


def _utcnow_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    records: list[dict] = []
    with path.open("r", encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, start=1):
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError as exc:
                    print(
                        f"WARNING: malformed JSONL in {path} at line {lineno}: {exc}",
                        file=sys.stderr,
                    )
    return records


class ReviewQueueStore:
    """File-backed JSONL queue for REVIEW-decision candidates.

    Append-only. Idempotent: a record with the same candidate_id is never
    written twice.

    Record schema (all fields):
        candidate_id    sha256(source_url)
        source_url      original URL
        title           paper/source title
        abstract        text used for scoring (may be empty)
        score           sigmoid-normalized filter score
        raw_score       pre-sigmoid score
        decision        always "review" for queue entries
        reason_codes    list of matched term reason strings
        matched_terms   dict keyed by category
        allow_threshold threshold from filter config
        review_threshold threshold from filter config
        config_version  filter config version string
        created_at      ISO-8601 UTC timestamp
    """

    def __init__(self, queue_path: Optional[Path] = None) -> None:
        self._path = Path(queue_path) if queue_path else _DEFAULT_QUEUE_PATH

    def enqueue(self, record: dict) -> bool:
        """Append a record to the queue if not already present.

        Parameters
        ----------
        record:
            Must include at least 'source_url'. 'candidate_id' is derived from
            source_url if absent. 'created_at' is set if not present.

        Returns
        -------
        bool
            True if written; False if already present (idempotent).
        """
        source_url = record.get("source_url", "")
        candidate_id = record.get("candidate_id") or candidate_id_from_url(source_url)

        existing_ids = {r.get("candidate_id") for r in _read_jsonl(self._path)}
        if candidate_id in existing_ids:
            return False

        out = dict(record)
        out["candidate_id"] = candidate_id
        out.setdefault("created_at", _utcnow_iso())

        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(out) + "\n")

        return True

    def all_records(self) -> list[dict]:
        """Return all queue records."""
        return _read_jsonl(self._path)

    def pending_count(self) -> int:
        """Return total number of queued records (labeled or not)."""
        return len(_read_jsonl(self._path))

    def queue_stats(self, label_store: "LabelStore | None" = None) -> dict:
        """Return joined counts across queue and label store.

        Parameters
        ----------
        label_store:
            If provided, cross-joins with label records to determine which
            queue items have been labeled.

        Returns
        -------
        dict with keys:
            total_queued       -- all records in the queue (labeled or not)
            pending_unlabeled  -- queued records with no label yet
            labeled_total      -- queued records that have at least one label
            labeled_allow      -- label records with label='allow' for queued items
            labeled_reject     -- label records with label='reject' for queued items
        """
        records = _read_jsonl(self._path)
        total_queued = len(records)
        queued_ids = {r.get("candidate_id") for r in records}

        labeled_ids: set[str] = set()
        labeled_allow: int = 0
        labeled_reject: int = 0

        if label_store is not None:
            for lr in label_store.all_labels():
                cid = lr.get("candidate_id", "")
                if cid in queued_ids:
                    labeled_ids.add(cid)
                    if lr.get("label") == "allow":
                        labeled_allow += 1
                    elif lr.get("label") == "reject":
                        labeled_reject += 1

        labeled_total = len(labeled_ids)
        pending_unlabeled = total_queued - labeled_total

        return {
            "total_queued": total_queued,
            "pending_unlabeled": pending_unlabeled,
            "labeled_total": labeled_total,
            "labeled_allow": labeled_allow,
            "labeled_reject": labeled_reject,
        }


class LabelStore:
    """File-backed JSONL store for operator-assigned filter labels.

    Append-only. Each record is one labeled training example for a future SVM.

    Label record schema:
        candidate_id  sha256(source_url)
        source_url    original URL
        title         paper/source title
        label         'allow' or 'reject'
        note          operator free-text note (may be empty)
        labeled_at    ISO-8601 UTC timestamp
    """

    def __init__(self, label_path: Optional[Path] = None) -> None:
        self._path = Path(label_path) if label_path else _DEFAULT_LABEL_PATH

    def append_label(
        self,
        candidate_id: str,
        source_url: str,
        title: str,
        label: str,
        note: str = "",
    ) -> dict:
        """Append a label record.

        Parameters
        ----------
        candidate_id:
            Stable ID (use candidate_id_from_url if building from URL).
        source_url:
            Original source URL.
        title:
            Paper/source title (informational).
        label:
            'allow' or 'reject'.
        note:
            Optional operator note.

        Returns
        -------
        dict
            The written label record.

        Raises
        ------
        ValueError
            If label is not 'allow' or 'reject'.
        """
        if label not in ("allow", "reject"):
            raise ValueError(f"label must be 'allow' or 'reject', got {label!r}")

        record = {
            "candidate_id": candidate_id,
            "source_url": source_url,
            "title": title,
            "label": label,
            "note": note,
            "labeled_at": _utcnow_iso(),
        }

        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record) + "\n")

        return record

    def all_labels(self) -> list[dict]:
        """Return all label records."""
        return _read_jsonl(self._path)

    def counts(self) -> dict:
        """Return {'total': N, 'allow': N, 'reject': N}."""
        records = _read_jsonl(self._path)
        allow_count = sum(1 for r in records if r.get("label") == "allow")
        reject_count = sum(1 for r in records if r.get("label") == "reject")
        return {
            "total": len(records),
            "allow": allow_count,
            "reject": reject_count,
        }
