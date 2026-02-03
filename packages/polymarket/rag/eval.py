"""Offline RAG evaluation harness.

Loads a JSONL suite of test cases, runs each query against the local index
in vector / lexical / hybrid modes, and produces recall@k, MRR@k, and
scope-violation metrics.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from .embedder import BaseEmbedder
from .index import DEFAULT_COLLECTION, DEFAULT_PERSIST_DIR
from .lexical import DEFAULT_LEXICAL_DB_PATH
from .query import query_index
from .reranker import BaseReranker

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

_HEX64_RE = re.compile(r"^[0-9a-fA-F]{64}$")


@dataclass
class EvalCase:
    query: str
    filters: dict
    must_include_any: list[str]
    must_exclude_any: list[str]
    notes: str = ""


@dataclass
class CaseResult:
    query: str
    mode: str  # "vector" | "lexical" | "hybrid"
    recall_at_k: float
    mrr_at_k: float
    scope_violations: list[dict]
    latency_ms: float
    result_count: int
    notes: str = ""


@dataclass
class ModeAggregate:
    mean_recall_at_k: float
    mean_mrr_at_k: float
    total_scope_violations: int
    queries_with_violations: int
    mean_latency_ms: float
    case_results: list[CaseResult] = field(default_factory=list)


@dataclass
class EvalReport:
    timestamp: str
    suite_path: str
    k: int
    modes: dict[str, ModeAggregate]


# ---------------------------------------------------------------------------
# Suite loading
# ---------------------------------------------------------------------------


def load_suite(path: Path) -> list[EvalCase]:
    """Parse a JSONL eval suite, validate required fields, return list."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Suite file not found: {path}")

    cases: list[EvalCase] = []
    with open(path, encoding="utf-8") as fh:
        for line_num, raw_line in enumerate(fh, 1):
            line = raw_line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON on line {line_num}: {exc}") from exc

            if "query" not in obj:
                raise ValueError(f"Missing 'query' on line {line_num}")

            filters = obj.get("filters") or {}
            expect = obj.get("expect") or {}

            cases.append(
                EvalCase(
                    query=obj["query"],
                    filters=filters,
                    must_include_any=expect.get("must_include_any") or [],
                    must_exclude_any=expect.get("must_exclude_any") or [],
                    notes=expect.get("notes", ""),
                )
            )

    if not cases:
        raise ValueError(f"Suite file is empty: {path}")

    return cases


# ---------------------------------------------------------------------------
# Pattern matching
# ---------------------------------------------------------------------------


def _match_pattern(pattern: str, result: dict) -> bool:
    """Check whether *pattern* matches a single search *result*.

    Matching rules:
    - ``user_slug:<value>`` matches result metadata ``user_slug``
    - ``doc_type:<value>`` matches result metadata ``doc_type``
    - ``is_private:true/false`` matches result metadata ``is_private``
    - 64-char hex string matches ``doc_id`` or ``chunk_id`` exactly
    - Anything else is a substring match against ``file_path``
    """
    meta = result.get("metadata") or {}

    if pattern.startswith("user_slug:"):
        val = pattern[len("user_slug:"):]
        return meta.get("user_slug") == val

    if pattern.startswith("doc_type:"):
        val = pattern[len("doc_type:"):]
        return meta.get("doc_type") == val

    if pattern.startswith("is_private:"):
        val = pattern[len("is_private:"):].lower()
        expected = val == "true"
        return meta.get("is_private") is expected or meta.get("is_private") == expected

    if _HEX64_RE.match(pattern):
        return result.get("doc_id") == pattern or result.get("chunk_id") == pattern

    # Default: substring match on file_path
    file_path = result.get("file_path", "")
    return pattern in file_path


# ---------------------------------------------------------------------------
# Single-case evaluation
# ---------------------------------------------------------------------------


def _eval_single(
    case: EvalCase,
    results: list[dict],
    k: int,
) -> tuple[float, float, list[dict]]:
    """Compute recall@k, MRR@k, and scope violations for one case.

    Returns (recall_at_k, mrr_at_k, scope_violations).
    """
    top_k = results[:k]

    # --- recall@k (OR semantics: at least one pattern matches one result) ---
    if case.must_include_any:
        found = 0
        first_rank = 0
        for pattern in case.must_include_any:
            for rank, r in enumerate(top_k, 1):
                if _match_pattern(pattern, r):
                    found += 1
                    if first_rank == 0:
                        first_rank = rank
                    break
        recall = found / len(case.must_include_any)
        mrr = (1.0 / first_rank) if first_rank > 0 else 0.0
    else:
        recall = 1.0  # no expectations = trivially met
        mrr = 0.0

    # --- scope violations (AND semantics: NO result may match ANY pattern) ---
    violations: list[dict] = []
    for pattern in case.must_exclude_any:
        for r in top_k:
            if _match_pattern(pattern, r):
                violations.append({
                    "pattern": pattern,
                    "file_path": r.get("file_path", ""),
                    "chunk_id": r.get("chunk_id", ""),
                    "metadata": r.get("metadata", {}),
                })

    return recall, mrr, violations


# ---------------------------------------------------------------------------
# Full eval run
# ---------------------------------------------------------------------------

_MODES = [
    ("vector", {"hybrid": False, "lexical_only": False}),
    ("lexical", {"hybrid": False, "lexical_only": True}),
    ("hybrid", {"hybrid": True, "lexical_only": False}),
    ("hybrid+rerank", {"hybrid": True, "lexical_only": False}),
]


def run_eval(
    suite: list[EvalCase],
    *,
    k: int = 8,
    embedder: Optional[BaseEmbedder] = None,
    persist_directory: Path = DEFAULT_PERSIST_DIR,
    collection_name: str = DEFAULT_COLLECTION,
    lexical_db_path: Optional[Path] = DEFAULT_LEXICAL_DB_PATH,
    top_k_vector: int = 25,
    top_k_lexical: int = 25,
    rrf_k: int = 60,
    reranker: Optional[BaseReranker] = None,
    rerank_top_n: int = 50,
    suite_path: str = "",
) -> EvalReport:
    """Run every case in *suite* across vector/lexical/hybrid modes.

    Returns an :class:`EvalReport` with per-mode aggregates and per-case
    detail.
    """
    mode_results: dict[str, list[CaseResult]] = {m: [] for m, _ in _MODES}

    for case in suite:
        # Build filter kwargs from the case's filters dict.
        filter_kw = {
            "user_slug": case.filters.get("user_slug"),
            "doc_types": case.filters.get("doc_types"),
            "private_only": case.filters.get("private_only", False),
            "public_only": case.filters.get("public_only", False),
            "date_from": case.filters.get("date_from"),
            "date_to": case.filters.get("date_to"),
            "include_archive": case.filters.get("include_archive", False),
        }

        for mode_name, mode_flags in _MODES:
            needs_embedder = mode_name != "lexical"
            if needs_embedder and embedder is None:
                # Skip vector/hybrid if no embedder supplied
                mode_results[mode_name].append(
                    CaseResult(
                        query=case.query,
                        mode=mode_name,
                        recall_at_k=0.0,
                        mrr_at_k=0.0,
                        scope_violations=[],
                        latency_ms=0.0,
                        result_count=0,
                        notes="skipped: no embedder",
                    )
                )
                continue

            # Skip hybrid+rerank if no reranker supplied
            if mode_name == "hybrid+rerank" and reranker is None:
                mode_results[mode_name].append(
                    CaseResult(
                        query=case.query,
                        mode=mode_name,
                        recall_at_k=0.0,
                        mrr_at_k=0.0,
                        scope_violations=[],
                        latency_ms=0.0,
                        result_count=0,
                        notes="skipped: no reranker",
                    )
                )
                continue

            t0 = time.perf_counter()
            try:
                # Pass reranker only for hybrid+rerank mode
                query_reranker = reranker if mode_name == "hybrid+rerank" else None
                results = query_index(
                    question=case.query,
                    embedder=embedder if needs_embedder else None,
                    k=k,
                    persist_directory=persist_directory,
                    collection_name=collection_name,
                    lexical_db_path=lexical_db_path,
                    top_k_vector=top_k_vector,
                    top_k_lexical=top_k_lexical,
                    rrf_k=rrf_k,
                    reranker=query_reranker,
                    rerank_top_n=rerank_top_n,
                    **filter_kw,
                    **mode_flags,
                )
            except Exception as exc:
                results = []
                error_note = f"error: {exc}"
                mode_results[mode_name].append(
                    CaseResult(
                        query=case.query,
                        mode=mode_name,
                        recall_at_k=0.0,
                        mrr_at_k=0.0,
                        scope_violations=[],
                        latency_ms=(time.perf_counter() - t0) * 1000,
                        result_count=0,
                        notes=error_note,
                    )
                )
                continue
            latency_ms = (time.perf_counter() - t0) * 1000

            recall, mrr, violations = _eval_single(case, results, k)

            mode_results[mode_name].append(
                CaseResult(
                    query=case.query,
                    mode=mode_name,
                    recall_at_k=recall,
                    mrr_at_k=mrr,
                    scope_violations=violations,
                    latency_ms=latency_ms,
                    result_count=len(results),
                    notes=case.notes,
                )
            )

    # --- Aggregate per mode ---
    modes: dict[str, ModeAggregate] = {}
    for mode_name, case_list in mode_results.items():
        n = len(case_list)
        if n == 0:
            modes[mode_name] = ModeAggregate(
                mean_recall_at_k=0.0,
                mean_mrr_at_k=0.0,
                total_scope_violations=0,
                queries_with_violations=0,
                mean_latency_ms=0.0,
                case_results=[],
            )
            continue

        total_recall = sum(c.recall_at_k for c in case_list)
        total_mrr = sum(c.mrr_at_k for c in case_list)
        total_violations = sum(len(c.scope_violations) for c in case_list)
        queries_with_viols = sum(1 for c in case_list if c.scope_violations)
        total_latency = sum(c.latency_ms for c in case_list)

        modes[mode_name] = ModeAggregate(
            mean_recall_at_k=total_recall / n,
            mean_mrr_at_k=total_mrr / n,
            total_scope_violations=total_violations,
            queries_with_violations=queries_with_viols,
            mean_latency_ms=total_latency / n,
            case_results=case_list,
        )

    return EvalReport(
        timestamp=datetime.now(timezone.utc).isoformat(),
        suite_path=suite_path,
        k=k,
        modes=modes,
    )


# ---------------------------------------------------------------------------
# Report output
# ---------------------------------------------------------------------------


def write_report(report: EvalReport, output_dir: Path) -> tuple[Path, Path]:
    """Write ``report.json`` and ``summary.md`` under *output_dir*.

    Returns ``(json_path, md_path)``.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    json_path = output_dir / "report.json"
    md_path = output_dir / "summary.md"

    # --- JSON ---
    json_path.write_text(
        json.dumps(asdict(report), indent=2, default=str),
        encoding="utf-8",
    )

    # --- Markdown summary ---
    lines: list[str] = [
        f"# RAG Eval Report",
        f"",
        f"- **Timestamp**: {report.timestamp}",
        f"- **Suite**: {report.suite_path}",
        f"- **k**: {report.k}",
        f"",
        f"## Per-mode Summary",
        f"",
        f"| Mode | Recall@{report.k} | MRR@{report.k} | Scope Violations | Queries w/ Violations | Mean Latency (ms) |",
        f"|------|{'-' * 12}|{'-' * 11}|{'-' * 18}|{'-' * 23}|{'-' * 20}|",
    ]

    for mode_name in ("vector", "lexical", "hybrid", "hybrid+rerank"):
        agg = report.modes.get(mode_name)
        if agg is None:
            continue
        lines.append(
            f"| {mode_name} "
            f"| {agg.mean_recall_at_k:.3f} "
            f"| {agg.mean_mrr_at_k:.3f} "
            f"| {agg.total_scope_violations} "
            f"| {agg.queries_with_violations} "
            f"| {agg.mean_latency_ms:.1f} |"
        )

    lines.append("")
    lines.append("## Per-case Detail")
    lines.append("")

    for mode_name in ("vector", "lexical", "hybrid", "hybrid+rerank"):
        agg = report.modes.get(mode_name)
        if agg is None:
            continue
        lines.append(f"### {mode_name}")
        lines.append("")
        for cr in agg.case_results:
            status = "PASS" if not cr.scope_violations else "VIOLATION"
            lines.append(f"- **{cr.query}** [{status}] recall={cr.recall_at_k:.2f} mrr={cr.mrr_at_k:.2f} latency={cr.latency_ms:.0f}ms results={cr.result_count}")
            if cr.scope_violations:
                for v in cr.scope_violations:
                    lines.append(f"  - violation: pattern=`{v['pattern']}` file=`{v.get('file_path', '')}`")
            if cr.notes:
                lines.append(f"  - note: {cr.notes}")
        lines.append("")

    md_path.write_text("\n".join(lines), encoding="utf-8")

    return json_path, md_path
