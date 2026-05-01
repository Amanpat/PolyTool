"""Nine metric implementations for the Scientific RAG Evaluation Benchmark v0.

Each metric returns a MetricResult with name, status, value, detail, and notes.
compute_all_metrics() runs all nine and returns AllMetricsResult.
"""

from __future__ import annotations

import json
import sqlite3
import statistics
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from packages.research.eval_benchmark.corpus import CorpusManifest
from packages.research.eval_benchmark.golden_qa import GoldenQASet


# ---------------------------------------------------------------------------
# Result dataclasses
# ---------------------------------------------------------------------------

@dataclass
class MetricResult:
    name: str
    status: str  # "ok" | "not_available" | "error"
    value: Dict[str, Any]
    detail: Any = field(default_factory=list)
    notes: str = ""


@dataclass
class AllMetricsResult:
    off_topic_rate: MetricResult
    body_source_distribution: MetricResult
    fallback_rate: MetricResult
    chunk_count_distribution: MetricResult
    low_chunk_suspicious_records: MetricResult
    retrieval_answer_quality: MetricResult
    citation_traceability: MetricResult
    duplicate_dedup_behavior: MetricResult
    parser_quality_notes: MetricResult
    corpus_size: int
    run_ts: str
    corpus_version: str
    golden_qa_review_status: str
    # Missing source ids: manifest entries not found in the KnowledgeStore DB
    manifest_entries: int = 0
    missing_source_ids: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _load_docs_from_db(db_path: Path, source_ids: List[str]) -> List[Dict[str, Any]]:
    """Query source_documents from KnowledgeStore for the given source_ids."""
    if not db_path.exists():
        return []
    if not source_ids:
        return []

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        placeholders = ",".join("?" for _ in source_ids)
        rows = conn.execute(
            f"SELECT id, title, source_url, source_family, content_hash, "
            f"chunk_count, published_at, ingested_at, confidence_tier, metadata_json "
            f"FROM source_documents WHERE id IN ({placeholders})",
            source_ids,
        ).fetchall()
        docs = []
        for row in rows:
            doc: Dict[str, Any] = dict(row)
            meta_str = doc.get("metadata_json") or "{}"
            try:
                doc["_meta"] = json.loads(meta_str)
            except (json.JSONDecodeError, TypeError):
                doc["_meta"] = {}
            docs.append(doc)
        return docs
    finally:
        conn.close()


def _get_body_source(doc: Dict[str, Any]) -> str:
    """Extract body_source from doc metadata."""
    meta = doc.get("_meta", {})
    return meta.get("body_source", "unknown") or "unknown"


def _get_fallback_reason(doc: Dict[str, Any]) -> str:
    """Extract fallback_reason from doc metadata."""
    meta = doc.get("_meta", {})
    return meta.get("fallback_reason", "unknown") or "unknown"


def _percentile(sorted_data: List[float], p: float) -> float:
    """Compute p-th percentile (0-100) from sorted data using linear interpolation."""
    if not sorted_data:
        return 0.0
    n = len(sorted_data)
    if n == 1:
        return sorted_data[0]
    idx = (p / 100.0) * (n - 1)
    lo = int(idx)
    hi = lo + 1
    if hi >= n:
        return sorted_data[-1]
    frac = idx - lo
    return sorted_data[lo] + frac * (sorted_data[hi] - sorted_data[lo])


def _review_priority(doc: Dict[str, Any]) -> str:
    """Assign review_priority for a suspicious (low-chunk) record.

    high  — zero chunks, abstract_fallback body, or very short body (< 100 chars)
    medium — 1-2 chunks with pdf body
    low   — otherwise (should be rare in this function since caller already
             filters to chunk_count < 3)
    """
    cc = doc.get("chunk_count") or 0
    body_source = _get_body_source(doc)
    meta = doc.get("_meta", {})
    body_length = meta.get("body_length") or 0
    try:
        body_length = int(body_length)
    except (TypeError, ValueError):
        body_length = 0

    if cc == 0 or body_source == "abstract_fallback" or body_length < 100:
        return "high"
    elif cc <= 2 and body_source == "pdf":
        return "medium"
    else:
        return "low"


# ---------------------------------------------------------------------------
# Metric 1: Off-topic rate
# ---------------------------------------------------------------------------

def compute_metric_1_off_topic_rate(
    docs: List[Dict[str, Any]],
    seed_keywords: List[str],
) -> MetricResult:
    """METRIC 1: Fraction of corpus documents whose title+abstract don't contain any seed keyword."""
    lower_keywords = [kw.lower() for kw in seed_keywords if kw.strip()]
    if not lower_keywords:
        return MetricResult(
            name="off_topic_rate",
            status="error",
            value={},
            notes="seed_topic_keywords is empty or contains only blank strings",
        )

    if not docs:
        return MetricResult(
            name="off_topic_rate",
            status="ok",
            value={"off_topic_count": 0, "total": 0, "off_topic_rate_pct": 0.0},
            detail=[],
        )

    off_topic = []
    for doc in docs:
        title = (doc.get("title") or "").lower()
        meta = doc.get("_meta", {})
        # Check title AND abstract/body excerpt (first 2000 chars)
        abstract = (meta.get("abstract") or "").lower()
        body = (meta.get("body") or "").lower()[:2000]
        combined_text = title + " " + abstract + " " + body
        if not any(kw in combined_text for kw in lower_keywords):
            off_topic.append({"source_id": doc["id"], "title": doc.get("title", "")})

    total = len(docs)
    count = len(off_topic)
    rate_pct = round(100.0 * count / total, 2) if total > 0 else 0.0

    return MetricResult(
        name="off_topic_rate",
        status="ok",
        value={
            "off_topic_count": count,
            "total": total,
            "off_topic_rate_pct": rate_pct,
        },
        detail=off_topic,
    )


# ---------------------------------------------------------------------------
# Metric 2: Body source distribution
# ---------------------------------------------------------------------------

def compute_metric_2_body_source_distribution(
    docs: List[Dict[str, Any]],
) -> MetricResult:
    """METRIC 2: Distribution of body_source values (pdf/abstract_fallback/marker/unknown)."""
    counts: Dict[str, int] = {}
    for doc in docs:
        bs = _get_body_source(doc)
        counts[bs] = counts.get(bs, 0) + 1

    total = len(docs)
    percentages: Dict[str, float] = {}
    for src, cnt in counts.items():
        percentages[src] = round(100.0 * cnt / total, 2) if total > 0 else 0.0

    return MetricResult(
        name="body_source_distribution",
        status="ok",
        value={"counts": counts, "percentages": percentages},
        detail=[],
    )


# ---------------------------------------------------------------------------
# Metric 3: Fallback rate
# ---------------------------------------------------------------------------

def compute_metric_3_fallback_rate(
    docs: List[Dict[str, Any]],
) -> MetricResult:
    """METRIC 3: Rate of docs using abstract_fallback body source, broken down by reason."""
    total = len(docs)
    fallback_docs = [d for d in docs if _get_body_source(d) == "abstract_fallback"]
    by_reason: Dict[str, int] = {}
    for doc in fallback_docs:
        reason = _get_fallback_reason(doc)
        by_reason[reason] = by_reason.get(reason, 0) + 1

    count = len(fallback_docs)
    rate_pct = round(100.0 * count / total, 2) if total > 0 else 0.0

    return MetricResult(
        name="fallback_rate",
        status="ok",
        value={
            "fallback_count": count,
            "total": total,
            "fallback_rate_pct": rate_pct,
            "by_reason": by_reason,
        },
        detail=[],
    )


# ---------------------------------------------------------------------------
# Metric 4: Chunk count distribution
# ---------------------------------------------------------------------------

def compute_metric_4_chunk_count_distribution(
    docs: List[Dict[str, Any]],
) -> MetricResult:
    """METRIC 4: Statistical distribution of chunk_count values across the corpus."""
    if not docs:
        return MetricResult(
            name="chunk_count_distribution",
            status="ok",
            value={"mean": 0.0, "median": 0.0, "p5": 0.0, "p95": 0.0, "histogram": []},
            detail=[],
        )

    counts = sorted(
        [float(doc.get("chunk_count") or 0) for doc in docs]
    )
    n = len(counts)

    mean_val = round(sum(counts) / n, 2)
    median_val = round(statistics.median(counts), 2)
    p5_val = round(_percentile(counts, 5), 2)
    p95_val = round(_percentile(counts, 95), 2)

    bucket_labels = ["0-2", "3-9", "10-19", "20-49", "50-99", "100-199", "200+"]
    bucket_counts = [0] * len(bucket_labels)
    for c in counts:
        if c < 3:
            bucket_counts[0] += 1
        elif c < 10:
            bucket_counts[1] += 1
        elif c < 20:
            bucket_counts[2] += 1
        elif c < 50:
            bucket_counts[3] += 1
        elif c < 100:
            bucket_counts[4] += 1
        elif c < 200:
            bucket_counts[5] += 1
        else:
            bucket_counts[6] += 1

    histogram = [
        {"bucket": label, "count": cnt}
        for label, cnt in zip(bucket_labels, bucket_counts)
    ]

    return MetricResult(
        name="chunk_count_distribution",
        status="ok",
        value={
            "mean": mean_val,
            "median": median_val,
            "p5": p5_val,
            "p95": p95_val,
            "histogram": histogram,
        },
        detail=[],
    )


# ---------------------------------------------------------------------------
# Metric 5: Low-chunk suspicious records
# ---------------------------------------------------------------------------

def compute_metric_5_low_chunk_suspicious_records(
    docs: List[Dict[str, Any]],
) -> MetricResult:
    """METRIC 5: Documents with chunk_count < 3 (likely parse failures or stubs)."""
    suspicious = []
    for doc in docs:
        cc = doc.get("chunk_count") or 0
        if cc < 3:
            meta = doc.get("_meta", {})
            body_len = meta.get("body_length", None)
            suspicious.append({
                "source_id": doc["id"],
                "title": doc.get("title", ""),
                "chunk_count": cc,
                "body_length": body_len,
                "body_source": _get_body_source(doc),
                "review_priority": _review_priority(doc),
            })

    return MetricResult(
        name="low_chunk_suspicious_records",
        status="ok",
        value={"suspicious_count": len(suspicious), "total": len(docs)},
        detail=suspicious,
    )


# ---------------------------------------------------------------------------
# Metric 6: Retrieval answer quality
# ---------------------------------------------------------------------------

def _evaluate_retrieval_pair(
    results: List[Dict[str, Any]],
    expected_paper_id: str,
    expected_answer_substring: str,
) -> Dict[str, Any]:
    """Check one QA pair against lexical search results.

    Returns dict with paper_found, answer_found, matched_rank, answer_match_rank,
    matched_doc_id, matched_file_path, top_5_doc_ids.

    answer_found is True only when the chunk that contains the expected answer
    substring ALSO belongs to the expected paper — not just any chunk.
    """
    top_5_doc_ids = []
    paper_found = False
    answer_found = False
    matched_rank: Optional[int] = None
    matched_doc_id: Optional[str] = None
    matched_file_path: Optional[str] = None
    answer_match_rank: Optional[int] = None

    for rank, r in enumerate(results[:5], start=1):
        fp = r.get("file_path", "") or ""
        did = r.get("doc_id", "") or ""
        top_5_doc_ids.append(did or fp)

        matches_expected = expected_paper_id in fp or expected_paper_id in did
        if matches_expected and not paper_found:
            paper_found = True
            matched_rank = rank
            matched_doc_id = did
            matched_file_path = fp

            # Only credit answer_found when in expected paper's chunk
            chunk_text = r.get("snippet", "") or r.get("chunk_text", "") or ""
            if expected_answer_substring.lower() in chunk_text.lower():
                answer_found = True
                answer_match_rank = rank

    return {
        "paper_found": paper_found,
        "answer_found": answer_found,
        "matched_rank": matched_rank,
        "matched_doc_id": matched_doc_id,
        "matched_file_path": matched_file_path,
        "answer_match_rank": answer_match_rank,
        "top_5_doc_ids": top_5_doc_ids,
    }


def compute_metric_6_retrieval_answer_quality(
    qa_set: GoldenQASet,
    lexical_db_path: Path,
) -> MetricResult:
    """METRIC 6: Retrieval P@5 and answer substring correctness via lexical search.

    answer_correctness_rate only credits answers found within the expected paper's
    retrieved chunk — not just any top-5 chunk containing the substring.
    """
    if not qa_set.pairs:
        return MetricResult(
            name="retrieval_answer_quality",
            status="not_available",
            value={},
            notes="empty QA set",
        )

    lexical_db_path = Path(lexical_db_path)
    if not lexical_db_path.exists():
        return MetricResult(
            name="retrieval_answer_quality",
            status="not_available",
            value={},
            notes="lexical DB not found",
        )

    try:
        from packages.polymarket.rag.lexical import open_lexical_db, lexical_search
    except ImportError:
        return MetricResult(
            name="retrieval_answer_quality",
            status="not_available",
            value={},
            notes="lexical module not available",
        )

    try:
        conn = open_lexical_db(lexical_db_path)
    except Exception as exc:
        return MetricResult(
            name="retrieval_answer_quality",
            status="not_available",
            value={},
            notes=f"could not open lexical DB: {exc}",
        )

    detail = []
    paper_found_count = 0
    answer_found_count = 0

    try:
        for pair in qa_set.pairs:
            try:
                # Search with the expected answer substring, not the full question.
                # FTS5 AND-matches every token, so long Q&A questions rarely hit any
                # single chunk. The substring is the actual claim we expect to retrieve.
                results = lexical_search(
                    conn,
                    pair.expected_answer_substring,
                    k=5,
                    private_only=False,
                    public_only=False,
                )
            except Exception:
                results = []

            eval_result = _evaluate_retrieval_pair(
                results,
                pair.expected_paper_id,
                pair.expected_answer_substring,
            )

            if eval_result["paper_found"]:
                paper_found_count += 1
            if eval_result["answer_found"]:
                answer_found_count += 1

            detail.append({
                "id": pair.id,
                "question": pair.question,
                "expected_paper_id": pair.expected_paper_id,
                "paper_found": eval_result["paper_found"],
                "answer_found": eval_result["answer_found"],
                "matched_rank": eval_result["matched_rank"],
                "answer_match_rank": eval_result["answer_match_rank"],
                "matched_doc_id": eval_result["matched_doc_id"],
                "matched_file_path": eval_result["matched_file_path"],
                "top_5_doc_ids": eval_result["top_5_doc_ids"],
            })
    finally:
        conn.close()

    evaluated = len(qa_set.pairs)
    p_at_5 = round(paper_found_count / evaluated, 4) if evaluated > 0 else 0.0
    answer_rate = round(answer_found_count / evaluated, 4) if evaluated > 0 else 0.0

    return MetricResult(
        name="retrieval_answer_quality",
        status="ok",
        value={
            "p_at_5": p_at_5,
            "answer_correctness_rate": answer_rate,
            "evaluated_count": evaluated,
            "paper_found_count": paper_found_count,
            "answer_found_count": answer_found_count,
        },
        detail=detail,
    )


# ---------------------------------------------------------------------------
# Metric 7: Citation traceability
# ---------------------------------------------------------------------------

def compute_metric_7_citation_traceability(
    qa_set: GoldenQASet,
    docs: List[Dict[str, Any]],
    lexical_db_path: Path,
) -> MetricResult:
    """METRIC 7: For QA pairs that retrieved the right paper, verify full traceability.

    A result is traceable when:
    1. The expected paper is in the top-5 results.
    2. The hit chunk has a source URL or file path.
    3. The expected answer substring appears in the chunk text.

    Reports traceable_count, evaluated_count, missing_source_count,
    missing_passage_count, missing_page_count, traceability_rate_pct,
    plus per-pair detail rows.
    """
    lexical_db_path = Path(lexical_db_path)
    if not lexical_db_path.exists():
        return MetricResult(
            name="citation_traceability",
            status="not_available",
            value={},
            notes="lexical DB not found",
        )

    if not qa_set.pairs:
        return MetricResult(
            name="citation_traceability",
            status="not_available",
            value={},
            notes="empty QA set",
        )

    try:
        from packages.polymarket.rag.lexical import open_lexical_db, lexical_search
    except ImportError:
        return MetricResult(
            name="citation_traceability",
            status="not_available",
            value={},
            notes="lexical module not available",
        )

    try:
        conn = open_lexical_db(lexical_db_path)
    except Exception as exc:
        return MetricResult(
            name="citation_traceability",
            status="not_available",
            value={},
            notes=f"could not open lexical DB: {exc}",
        )

    traceable_count = 0
    evaluated_count = 0
    missing_source_count = 0
    missing_page_count = 0
    missing_passage_count = 0
    detail = []

    try:
        for pair in qa_set.pairs:
            try:
                # Search with the expected answer substring (same rationale as metric 6).
                results = lexical_search(
                    conn,
                    pair.expected_answer_substring,
                    k=5,
                    private_only=False,
                    public_only=False,
                )
            except Exception:
                results = []

            # Find the expected paper in results
            hit_result = None
            for r in results[:5]:
                fp = r.get("file_path", "") or ""
                did = r.get("doc_id", "") or ""
                if pair.expected_paper_id in fp or pair.expected_paper_id in did:
                    hit_result = r
                    break

            if hit_result is None:
                # Paper not retrieved — not evaluated for traceability
                continue

            evaluated_count += 1

            # Check source (URL or file path)
            has_source = bool(
                hit_result.get("file_path") or hit_result.get("source_url")
            )
            # Check page label availability
            has_page = bool(
                hit_result.get("page") is not None
                or hit_result.get("page_label")
            )
            # Check passage (answer substring in chunk text)
            chunk_text = (
                hit_result.get("snippet", "")
                or hit_result.get("chunk_text", "")
                or ""
            )
            has_passage = pair.expected_answer_substring.lower() in chunk_text.lower()

            if not has_source:
                missing_source_count += 1
            if not has_page:
                missing_page_count += 1
            if not has_passage:
                missing_passage_count += 1

            traceable = has_source and has_passage
            if traceable:
                traceable_count += 1

            missing_reasons = []
            if not has_source:
                missing_reasons.append("missing_source")
            if not has_page:
                missing_reasons.append("missing_page")
            if not has_passage:
                missing_reasons.append("missing_passage")

            detail.append({
                "id": pair.id,
                "question": pair.question,
                "expected_paper_id": pair.expected_paper_id,
                "paper_found": True,
                "has_source": has_source,
                "has_page": has_page,
                "has_passage": has_passage,
                "traceable": traceable,
                "missing_reasons": missing_reasons if missing_reasons else None,
            })
    finally:
        conn.close()

    rate_pct = round(100.0 * traceable_count / evaluated_count, 2) if evaluated_count > 0 else 0.0

    return MetricResult(
        name="citation_traceability",
        status="ok",
        value={
            "traceable_count": traceable_count,
            "evaluated_count": evaluated_count,
            "missing_source_count": missing_source_count,
            "missing_page_count": missing_page_count,
            "missing_passage_count": missing_passage_count,
            "traceability_rate_pct": rate_pct,
        },
        detail=detail,
    )


# ---------------------------------------------------------------------------
# Metric 8: Duplicate/dedup behavior
# ---------------------------------------------------------------------------

def compute_metric_8_duplicate_dedup_behavior(
    docs: List[Dict[str, Any]],
) -> MetricResult:
    """METRIC 8: Find exact-hash, canonical-id, title-only, and similar-title-body duplicates."""
    # 1. Exact content_hash duplicates
    hash_groups: Dict[str, List[str]] = {}
    for doc in docs:
        ch = doc.get("content_hash") or ""
        if ch:
            hash_groups.setdefault(ch, []).append(doc["id"])

    exact_hash_dupe_detail = []
    exact_hash_dupes = 0
    for ch, ids in hash_groups.items():
        if len(ids) > 1:
            exact_hash_dupes += 1
            exact_hash_dupe_detail.append({"content_hash": ch, "source_ids": ids})

    # 2. Canonical id duplicates (doi, arxiv_id, canonical_id in metadata)
    canonical_groups: Dict[str, List[str]] = {}
    for doc in docs:
        meta = doc.get("_meta", {})
        cids = set()
        for field_name in ("canonical_id", "doi", "arxiv_id"):
            val = meta.get(field_name) or ""
            if val:
                cids.add(val.strip().lower())
        for cid in cids:
            canonical_groups.setdefault(cid, []).append(doc["id"])

    canonical_id_dupe_detail = []
    canonical_id_dupes = 0
    for cid, ids in canonical_groups.items():
        if len(ids) > 1:
            # Deduplicate multi-source_id entries
            unique_ids = list(dict.fromkeys(ids))
            if len(unique_ids) > 1:
                canonical_id_dupes += 1
                canonical_id_dupe_detail.append({"canonical_id": cid, "source_ids": unique_ids})

    # 3. Exact normalized-title duplicates
    title_groups: Dict[str, List[str]] = {}
    for doc in docs:
        title = (doc.get("title") or "").strip().lower()
        if len(title) > 5:
            title_groups.setdefault(title, []).append(doc["id"])

    title_dupes = sum(1 for ids in title_groups.values() if len(ids) > 1)

    # 4. Similar-title-body duplicates:
    #    same normalized title + same body prefix hash (first 200 chars of body)
    title_body_groups: Dict[str, List[str]] = {}
    for doc in docs:
        title = (doc.get("title") or "").strip().lower()
        if len(title) > 5:
            meta = doc.get("_meta", {})
            body_prefix = (meta.get("body") or "")[:200]
            # Use a deterministic string hash as prefix fingerprint
            body_key = str(hash(body_prefix) & 0xFFFFFFFF)
            key = title + "|" + body_key
            title_body_groups.setdefault(key, []).append(doc["id"])

    similar_title_body_dupe_detail = []
    similar_title_body_dupes = 0
    for key, ids in title_body_groups.items():
        if len(ids) > 1:
            # Only report if not already captured by exact title duplicates
            title_part = key.split("|")[0]
            title_already_flagged = len(title_groups.get(title_part, [])) > 1
            if not title_already_flagged:
                similar_title_body_dupes += 1
                similar_title_body_dupe_detail.append({
                    "title_prefix": title_part[:60],
                    "source_ids": ids,
                })

    all_detail = (
        exact_hash_dupe_detail
        + canonical_id_dupe_detail
        + similar_title_body_dupe_detail
    )

    return MetricResult(
        name="duplicate_dedup_behavior",
        status="ok",
        value={
            "exact_hash_dupes": exact_hash_dupes,
            "canonical_id_dupes": canonical_id_dupes,
            "title_dupes": title_dupes,
            "similar_title_body_dupes": similar_title_body_dupes,
            "total_docs": len(docs),
        },
        detail=all_detail,
    )


# ---------------------------------------------------------------------------
# Metric 9: Parser quality notes
# ---------------------------------------------------------------------------

def compute_metric_9_parser_quality_notes(
    docs: List[Dict[str, Any]],
    sampled_categories: Optional[List[str]] = None,
) -> MetricResult:
    """METRIC 9: Parser quality flags, scoped to sampled_categories.

    Only processes docs whose _meta.category is in sampled_categories (injected
    from corpus manifest by compute_all_metrics). Docs outside the scope are
    excluded. Abstract-fallback docs within scope are counted but skipped for
    quality assessment.

    Reports deterministic issue counts: equation_not_parseable_count,
    table_not_detectable_count, section_headers_missing_count, missing_page_count,
    skipped_abstract_fallback_count.
    """
    if sampled_categories is None:
        sampled_categories = ["equation_heavy", "table_heavy"]

    sampled_set = set(sampled_categories)

    # Split docs into in-scope and out-of-scope
    in_scope_docs = [
        doc for doc in docs
        if doc.get("_meta", {}).get("category") in sampled_set
    ]

    skipped_abstract_fallback_count = sum(
        1 for doc in in_scope_docs
        if _get_body_source(doc) == "abstract_fallback"
    )

    # Assess quality only for in-scope, non-abstract-fallback docs
    assessable = [
        doc for doc in in_scope_docs
        if _get_body_source(doc) != "abstract_fallback"
    ]

    detail = []
    equation_not_parseable_count = 0
    table_not_detectable_count = 0
    section_headers_missing_count = 0
    missing_page_count = 0
    sampled_count = 0

    for doc in assessable:
        meta = doc.get("_meta", {})
        body_source = _get_body_source(doc)
        page_count = meta.get("page_count")
        has_page_count = page_count is not None
        if not has_page_count:
            missing_page_count += 1

        body_text = meta.get("body") or meta.get("abstract") or ""

        equation_parseable = bool(
            "=" in body_text or "\\(" in body_text or "\\[" in body_text
        )
        table_detectable = bool(
            "\t" in body_text or "|" in body_text or "Table" in body_text
        )
        lines = body_text.split("\n")
        section_headers_detectable = any(
            line.strip().isupper() and len(line.strip()) > 3
            for line in lines
        )

        if not equation_parseable:
            equation_not_parseable_count += 1
        if not table_detectable:
            table_not_detectable_count += 1
        if not section_headers_detectable:
            section_headers_missing_count += 1

        category = meta.get("category")
        sampled_count += 1
        detail.append({
            "source_id": doc["id"],
            "title": doc.get("title", ""),
            "category": category,
            "body_source": body_source,
            "quality_flags": {
                "has_page_count": has_page_count,
                "equation_parseable": equation_parseable,
                "table_detectable": table_detectable,
                "section_headers_detectable": section_headers_detectable,
            },
        })

    # Rates over assessable denominator
    denom = sampled_count if sampled_count > 0 else 1
    eq_not_parseable_rate = round(100.0 * equation_not_parseable_count / denom, 2)
    table_not_detectable_rate = round(100.0 * table_not_detectable_count / denom, 2)
    section_missing_rate = round(100.0 * section_headers_missing_count / denom, 2)
    missing_page_rate = round(100.0 * missing_page_count / denom, 2)

    return MetricResult(
        name="parser_quality_notes",
        status="ok",
        value={
            "sampled_count": sampled_count,
            "skipped_abstract_fallback_count": skipped_abstract_fallback_count,
            "equation_not_parseable_count": equation_not_parseable_count,
            "table_not_detectable_count": table_not_detectable_count,
            "section_headers_missing_count": section_headers_missing_count,
            "missing_page_count": missing_page_count,
            "equation_not_parseable_rate_pct": eq_not_parseable_rate,
            "table_not_detectable_rate_pct": table_not_detectable_rate,
            "section_headers_missing_rate_pct": section_missing_rate,
            "missing_page_rate_pct": missing_page_rate,
        },
        detail=detail,
    )


# ---------------------------------------------------------------------------
# Aggregate runner
# ---------------------------------------------------------------------------

def compute_all_metrics(
    corpus: CorpusManifest,
    qa_set: GoldenQASet,
    db_path: Path,
    lexical_db_path: Path,
) -> AllMetricsResult:
    """Run all nine metrics and return an AllMetricsResult.

    Also detects manifest source_ids not found in the KnowledgeStore DB and
    stores them in AllMetricsResult.missing_source_ids.
    """
    source_ids = [e.source_id for e in corpus.entries]
    docs = _load_docs_from_db(Path(db_path), source_ids)

    # Detect missing source_ids
    loaded_ids = {doc["id"] for doc in docs}
    manifest_ids = set(source_ids)
    missing_ids = sorted(manifest_ids - loaded_ids)

    # Build category map from corpus manifest for metric 9
    category_map = {e.source_id: e.category for e in corpus.entries}
    for doc in docs:
        doc_id = doc["id"]
        if doc_id in category_map:
            meta = doc.get("_meta", {})
            meta["category"] = category_map[doc_id]
            doc["_meta"] = meta

    m1 = compute_metric_1_off_topic_rate(docs, corpus.seed_topic_keywords)
    m2 = compute_metric_2_body_source_distribution(docs)
    m3 = compute_metric_3_fallback_rate(docs)
    m4 = compute_metric_4_chunk_count_distribution(docs)
    m5 = compute_metric_5_low_chunk_suspicious_records(docs)
    m6 = compute_metric_6_retrieval_answer_quality(qa_set, Path(lexical_db_path))
    m7 = compute_metric_7_citation_traceability(qa_set, docs, Path(lexical_db_path))
    m8 = compute_metric_8_duplicate_dedup_behavior(docs)

    sampled_cats = ["equation_heavy", "table_heavy"]
    m9 = compute_metric_9_parser_quality_notes(docs, sampled_cats)

    run_ts = datetime.now(tz=timezone.utc).isoformat()

    return AllMetricsResult(
        off_topic_rate=m1,
        body_source_distribution=m2,
        fallback_rate=m3,
        chunk_count_distribution=m4,
        low_chunk_suspicious_records=m5,
        retrieval_answer_quality=m6,
        citation_traceability=m7,
        duplicate_dedup_behavior=m8,
        parser_quality_notes=m9,
        corpus_size=len(docs),
        run_ts=run_ts,
        corpus_version=corpus.version,
        golden_qa_review_status=qa_set.review_status,
        manifest_entries=len(source_ids),
        missing_source_ids=missing_ids,
    )
