"""RIS Phase 3 — content-hash and n-gram near-duplicate detection.

Provides:
- compute_content_hash(body) -> SHA256 hex of normalized body
- compute_shingles(body, shingle_size) -> frozenset of word n-gram tuples
- jaccard_similarity(a, b) -> float 0.0..1.0
- check_near_duplicate(doc, existing_hashes, existing_shingles, threshold) -> NearDuplicateResult

All functions are pure; no network calls, no I/O.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Optional

from packages.research.evaluation.types import EvalDocument


@dataclass
class NearDuplicateResult:
    """Result of a near-duplicate check against a document corpus.

    Attributes:
        is_duplicate: True if this document is an exact or near-duplicate.
        duplicate_type: "exact" | "near" | None
        matched_doc_id: ID of the matched document if is_duplicate=True.
        similarity: Jaccard similarity score (1.0 for exact, <1 for near, 0.0 if not dup).
    """

    is_duplicate: bool
    duplicate_type: Optional[str] = None
    matched_doc_id: Optional[str] = None
    similarity: float = 0.0


def _normalize(body: str) -> str:
    """Normalize body text for consistent hashing.

    Lowercases and collapses all whitespace to single spaces.
    """
    return " ".join(body.lower().split())


def compute_content_hash(body: str) -> str:
    """Compute a SHA256 content hash of a normalized document body.

    Normalization: lowercase + collapse whitespace. This ensures that
    documents differing only in casing or whitespace are detected as
    exact duplicates.

    Args:
        body: Raw document body text.

    Returns:
        64-character lowercase hex SHA256 digest.
    """
    normalized = _normalize(body)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def compute_shingles(body: str, shingle_size: int = 5) -> frozenset:
    """Compute a set of word-level n-gram shingles from a document body.

    Each shingle is a tuple of `shingle_size` consecutive words from the
    normalized body. Used for Jaccard-based near-duplicate detection.

    Args:
        body: Raw document body text.
        shingle_size: Number of words per shingle (default 5).

    Returns:
        frozenset of tuples, where each tuple is a word n-gram.
    """
    words = _normalize(body).split()
    if len(words) < shingle_size:
        return frozenset(tuple(words[i:]) for i in range(max(1, len(words))))
    return frozenset(
        tuple(words[i : i + shingle_size]) for i in range(len(words) - shingle_size + 1)
    )


def jaccard_similarity(a: frozenset, b: frozenset) -> float:
    """Compute Jaccard similarity between two shingle sets.

    J(A, B) = |A ∩ B| / |A ∪ B|

    Args:
        a: First shingle set.
        b: Second shingle set.

    Returns:
        Float in [0.0, 1.0]. Returns 0.0 if both sets are empty.
    """
    union = a | b
    if not union:
        return 0.0
    intersection = a & b
    return len(intersection) / len(union)


def check_near_duplicate(
    doc: EvalDocument,
    existing_hashes: set[str],
    existing_shingles: list[tuple[str, frozenset]],
    threshold: float = 0.85,
) -> NearDuplicateResult:
    """Check whether a document is an exact or near-duplicate of known documents.

    Algorithm:
    1. If body is empty/None, return not-duplicate (no data to compare).
    2. Compute content hash. If it matches any existing hash, return exact duplicate.
    3. Compute shingles. If Jaccard similarity > threshold against any existing
       shingle set, return near-duplicate with the matching doc_id and similarity.
    4. Otherwise return not-duplicate.

    Args:
        doc: Document to check.
        existing_hashes: Set of content hashes from previously seen documents.
        existing_shingles: List of (doc_id, shingle_frozenset) pairs.
        threshold: Jaccard similarity threshold for near-duplicate detection (default 0.85).

    Returns:
        NearDuplicateResult indicating whether a duplicate was found.
    """
    body = doc.body
    if not body:
        return NearDuplicateResult(is_duplicate=False)

    # Step 1: exact duplicate check
    content_hash = compute_content_hash(body)
    if content_hash in existing_hashes:
        return NearDuplicateResult(
            is_duplicate=True,
            duplicate_type="exact",
            matched_doc_id=None,
            similarity=1.0,
        )

    # Step 2: near-duplicate check via Jaccard
    doc_shingles = compute_shingles(body)
    for candidate_id, candidate_shingles in existing_shingles:
        sim = jaccard_similarity(doc_shingles, candidate_shingles)
        if sim > threshold:
            return NearDuplicateResult(
                is_duplicate=True,
                duplicate_type="near",
                matched_doc_id=candidate_id,
                similarity=sim,
            )

    return NearDuplicateResult(is_duplicate=False)
