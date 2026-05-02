"""CLI entrypoint for the Scientific RAG Evaluation Benchmark v0.

Measures corpus quality and retrieval accuracy across nine metrics, produces
Markdown and JSON reports, and emits a prioritized recommendation (A-E or NONE).

Usage:
  python -m polytool research-eval-benchmark --corpus PATH --golden-set PATH
  python -m polytool research-eval-benchmark --corpus v0 --golden-set v0 --dry-run
  python -m polytool research-eval-benchmark --corpus v0 --golden-set v0 --strict
  python -m polytool research-eval-benchmark --corpus v0 --golden-set v0 --save-baseline
  python -m polytool research-eval-benchmark --corpus v0 --golden-set v0 --json
  python -m polytool research-eval-benchmark --corpus v0 --refresh-lexical
  python -m polytool research-eval-benchmark --corpus v0 --simulate-prefetch-filter
  python -m polytool research-eval-benchmark --corpus v0 --golden-set v0 --simulate-prefetch-filter

Exit codes:
  0 — success
  1 — validation error (bad inputs, strict mode with unreviewed QA, etc.)
  2 — computation error
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import List, Optional


# ---------------------------------------------------------------------------
# Default paths
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_CORPUS_JSON = _REPO_ROOT / "config" / "research_eval_benchmark_v0_corpus.json"
_DEFAULT_CORPUS_DRAFT_JSON = _REPO_ROOT / "config" / "research_eval_benchmark_v0_corpus.draft.json"
_DEFAULT_GOLDEN_JSON = (
    _REPO_ROOT / "tests" / "fixtures" / "research_eval_benchmark" / "golden_qa_v0.json"
)
_DEFAULT_GOLDEN_DRAFT_JSON = (
    _REPO_ROOT / "tests" / "fixtures" / "research_eval_benchmark" / "golden_qa_v0.draft.json"
)
_DEFAULT_OUTPUT_DIR = _REPO_ROOT / "artifacts" / "research" / "eval_benchmark"
_DEFAULT_LEXICAL_DB = _REPO_ROOT / "kb" / "rag" / "lexical" / "lexical.sqlite3"
_DEFAULT_KNOWLEDGE_DB = _REPO_ROOT / "kb" / "rag" / "knowledge" / "knowledge.sqlite3"
_BASELINE_PATH = _REPO_ROOT / "artifacts" / "research" / "eval_benchmark" / "baseline_v0.json"
_DEFAULT_RAW_CACHE_DIR = (
    _REPO_ROOT / "artifacts" / "research" / "raw_source_cache" / "academic"
)
_DEFAULT_FILTER_CONFIG = _REPO_ROOT / "config" / "research_relevance_filter_v1.json"


# ---------------------------------------------------------------------------
# Auto-discovery helpers
# ---------------------------------------------------------------------------

def _resolve_corpus_path(corpus_arg: str) -> Optional[Path]:
    """Resolve corpus path, handling 'v0' shorthand."""
    if corpus_arg == "v0":
        if _DEFAULT_CORPUS_JSON.exists():
            return _DEFAULT_CORPUS_JSON
        if _DEFAULT_CORPUS_DRAFT_JSON.exists():
            return _DEFAULT_CORPUS_DRAFT_JSON
        return None
    path = Path(corpus_arg)
    if path.exists():
        return path
    return None


def _resolve_golden_path(golden_arg: str) -> Optional[Path]:
    """Resolve golden QA path, handling 'v0' shorthand."""
    if golden_arg == "v0":
        if _DEFAULT_GOLDEN_JSON.exists():
            return _DEFAULT_GOLDEN_JSON
        if _DEFAULT_GOLDEN_DRAFT_JSON.exists():
            return _DEFAULT_GOLDEN_DRAFT_JSON
        return None
    path = Path(golden_arg)
    if path.exists():
        return path
    return None


# ---------------------------------------------------------------------------
# Main entrypoint
# ---------------------------------------------------------------------------

def _run_discover_corpus(db_path: Path) -> int:
    """List academic records from the KnowledgeStore as corpus candidates."""
    import sqlite3 as _sqlite3

    if not db_path.exists():
        print(f"ERROR: KnowledgeStore DB not found: {db_path}", file=sys.stderr)
        return 1

    try:
        conn = _sqlite3.connect(str(db_path))
        conn.row_factory = _sqlite3.Row
        rows = conn.execute(
            """
            SELECT id, title, source_family, source_url, chunk_count, content_hash, metadata_json
            FROM source_documents
            WHERE source_family = 'academic'
            ORDER BY chunk_count DESC, ingested_at DESC
            """
        ).fetchall()
        conn.close()
    except Exception as exc:
        print(f"ERROR: DB query failed: {exc}", file=sys.stderr)
        return 1

    candidates = []
    for row in rows:
        meta: dict = {}
        try:
            meta = json.loads(row["metadata_json"] or "{}")
        except (json.JSONDecodeError, TypeError):
            pass
        candidates.append({
            "source_id": row["id"],
            "title": row["title"] or "",
            "source_url": row["source_url"] or "",
            "chunk_count": row["chunk_count"] or 0,
            "body_source": meta.get("body_source", "unknown"),
            "body_length": meta.get("body_length"),
            "content_hash": row["content_hash"] or "",
        })

    print(f"# Corpus discovery: {len(candidates)} academic records in KnowledgeStore")
    print(f"# DB: {db_path}")
    print(f"# Columns: source_id, title, chunk_count, body_source, body_length")
    print()
    for c in candidates:
        bs = c["body_source"]
        bl = c["body_length"]
        cc = c["chunk_count"]
        print(
            f"  [{cc:3d} chunks | {bs:20s} | body={bl}]  "
            f"{c['source_id'][:20]}...  {c['title'][:60]}"
        )
    print()
    print(json.dumps(candidates, indent=2))
    return 0


def _run_simulate_prefetch_filter(args, corpus, qa_set=None) -> int:
    """Simulate the L3 lexical relevance filter against the corpus.

    Reports projected off_topic_rate for allow/review/reject scenarios.
    Does not modify any DB state.
    """
    from packages.research.relevance_filter.scorer import (
        CandidateInput,
        RelevanceScorer,
        load_filter_config,
    )
    from packages.research.eval_benchmark.metrics import (
        _load_docs_from_db,
        compute_metric_1_off_topic_rate,
    )

    # Load filter config
    filter_config_path = Path(args.filter_config) if args.filter_config else None
    try:
        filter_cfg = load_filter_config(filter_config_path)
    except FileNotFoundError as exc:
        print(f"ERROR: Filter config not found: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"ERROR: Failed to load filter config: {exc}", file=sys.stderr)
        return 1

    scorer = RelevanceScorer(filter_cfg)

    # Load docs from DB (same pattern as compute_all_metrics)
    source_ids = [e.source_id for e in corpus.entries]
    docs = _load_docs_from_db(Path(args.db), source_ids)

    # Build a title lookup from corpus entries (fallback when doc not in DB)
    corpus_title_map = {e.source_id: (e.title or "") for e in corpus.entries}

    # Score each corpus entry
    allow_ids: list = []
    review_ids: list = []
    reject_ids: list = []
    per_paper_results: list = []

    for entry in corpus.entries:
        sid = entry.source_id
        # Find matching doc from DB if available
        doc = next((d for d in docs if d["id"] == sid), None)
        title = ""
        abstract = ""
        if doc is not None:
            title = doc.get("title") or ""
            meta = doc.get("_meta", {})
            abstract = meta.get("abstract") or ""
        else:
            title = corpus_title_map.get(sid, "")

        candidate = CandidateInput(
            title=title,
            abstract=abstract,
            source_id=sid,
        )
        decision = scorer.score(candidate)

        per_paper_results.append({
            "source_id": sid,
            "title": title,
            "decision": decision.decision,
            "score": decision.score,
            "raw_score": decision.raw_score,
            "reason_codes": decision.reason_codes,
            "matched_terms": decision.matched_terms,
            "allow_threshold": decision.allow_threshold,
            "review_threshold": decision.review_threshold,
        })

        if decision.decision == "allow":
            allow_ids.append(sid)
        elif decision.decision == "review":
            review_ids.append(sid)
        else:
            reject_ids.append(sid)

    # --- Baseline off_topic_rate (all docs) ---
    baseline_m1 = compute_metric_1_off_topic_rate(docs, corpus.seed_topic_keywords)
    baseline_off_topic_count = baseline_m1.value.get("off_topic_count", 0) if baseline_m1.status == "ok" else 0
    baseline_total = baseline_m1.value.get("total", len(docs)) if baseline_m1.status == "ok" else len(docs)
    baseline_rate = baseline_m1.value.get("off_topic_rate_pct", 0.0) if baseline_m1.status == "ok" else 0.0

    # --- Scenario A: reject excluded, review included ---
    scenario_a_ids = allow_ids + review_ids
    scenario_a_docs = [d for d in docs if d["id"] in set(scenario_a_ids)]
    scenario_a_m1 = compute_metric_1_off_topic_rate(scenario_a_docs, corpus.seed_topic_keywords)
    scenario_a_rate = scenario_a_m1.value.get("off_topic_rate_pct", 0.0) if scenario_a_m1.status == "ok" else 0.0

    # --- Scenario B: reject + review excluded (allow only) ---
    scenario_b_docs = [d for d in docs if d["id"] in set(allow_ids)]
    scenario_b_m1 = compute_metric_1_off_topic_rate(scenario_b_docs, corpus.seed_topic_keywords)
    scenario_b_rate = scenario_b_m1.value.get("off_topic_rate_pct", 0.0) if scenario_b_m1.status == "ok" else 0.0

    # --- False negative analysis (if golden set provided) ---
    fn_in_reject: list = []
    fn_in_review: list = []
    if qa_set is not None and qa_set.pairs:
        qa_paper_ids = {pair.expected_paper_id for pair in qa_set.pairs}
        reject_set = set(reject_ids)
        review_set = set(review_ids)
        fn_in_reject = [pid for pid in qa_paper_ids if pid in reject_set]
        fn_in_review = [pid for pid in qa_paper_ids if pid in review_set]

    # --- Print report ---
    print("")
    print("=" * 70)
    print("PREFETCH FILTER SIMULATION REPORT")
    print("=" * 70)
    print(f"Filter config version : {filter_cfg.version}")
    print(f"Allow threshold       : {filter_cfg.allow_threshold}")
    print(f"Review threshold      : {filter_cfg.review_threshold}")
    print(f"Corpus entries        : {len(corpus.entries)}")
    print(f"Docs loaded from DB   : {len(docs)}")
    print("")
    print("--- Baseline (no filter) ---")
    print(f"  Off-topic count : {baseline_off_topic_count} / {baseline_total}")
    print(f"  Off-topic rate  : {baseline_rate}%")
    print("")
    print("--- Filter decisions ---")
    print(f"  ALLOW  : {len(allow_ids)}")
    print(f"  REVIEW : {len(review_ids)}")
    print(f"  REJECT : {len(reject_ids)}")
    print("")
    print("--- Per-paper decisions ---")
    print(f"  {'Title':<52} {'Decision':<8} {'Score':<7} Reason codes")
    print(f"  {'-'*52} {'-'*8} {'-'*7} {'-'*30}")
    for r in per_paper_results:
        title_trunc = r["title"][:50] if r["title"] else "(no title)"
        codes_str = ", ".join(r["reason_codes"])
        print(f"  {title_trunc:<52} {r['decision']:<8} {r['score']:<7.4f} {codes_str}")
    print("")
    # --- Detail for REVIEW and REJECT papers ---
    non_allow = [r for r in per_paper_results if r["decision"] in ("review", "reject")]
    if non_allow:
        print("--- Detail for REVIEW and REJECT papers ---")
        for r in non_allow:
            print(f"  source_id     : {r['source_id'][:20]}")
            print(f"  decision      : {r['decision']}")
            print(f"  score         : {r['score']}")
            print(f"  raw_score     : {r['raw_score']}")
            print(f"  allow_thresh  : {r['allow_threshold']}")
            print(f"  review_thresh : {r['review_threshold']}")
            print(f"  reason_codes  :")
            for rc in r["reason_codes"]:
                print(f"    {rc}")
            print(f"  matched_terms : {r['matched_terms']}")
            print("")
    print("--- Projected off_topic_rate ---")
    print(f"  Scenario A (reject excluded, review included) : {scenario_a_rate}%  [{len(scenario_a_docs)} docs]")
    print(f"  Scenario B (reject+review excluded)          : {scenario_b_rate}%  [{len(scenario_b_docs)} docs]")
    print("")
    if qa_set is not None and qa_set.pairs:
        print("--- False negative analysis (QA papers in reject/review) ---")
        print(f"  QA paper source_ids tracked : {len({p.expected_paper_id for p in qa_set.pairs})}")
        print(f"  QA papers in REJECT         : {len(fn_in_reject)}")
        if fn_in_reject:
            for pid in fn_in_reject:
                print(f"    - {pid}")
        print(f"  QA papers in REVIEW         : {len(fn_in_review)}")
        if fn_in_review:
            for pid in fn_in_review:
                print(f"    - {pid}")
        print("")
    target_met = scenario_b_rate < 10.0
    print(f"Target <10% off_topic (scenario B): {'YES' if target_met else 'NO'} ({scenario_b_rate}%)")
    print("=" * 70)

    return 0


def main(argv: List[str]) -> int:
    """CLI entrypoint for research-eval-benchmark command."""
    parser = argparse.ArgumentParser(
        prog="polytool research-eval-benchmark",
        description=(
            "Scientific RAG Evaluation Benchmark v0 — "
            "measure corpus and retrieval quality across nine metrics."
        ),
    )
    parser.add_argument(
        "--corpus",
        required=False,
        default=None,
        metavar="PATH",
        help=(
            "Path to corpus manifest JSON. Use 'v0' to auto-discover "
            "config/research_eval_benchmark_v0_corpus[.draft].json. "
            "Not required when --discover-corpus is used."
        ),
    )
    parser.add_argument(
        "--golden-set",
        required=False,
        default=None,
        metavar="PATH",
        help=(
            "Path to golden QA JSON. Use 'v0' to auto-discover "
            "tests/fixtures/research_eval_benchmark/golden_qa_v0[.draft].json. "
            "If omitted, metrics requiring QA will show as not_available."
        ),
    )
    parser.add_argument(
        "--output-dir",
        default=str(_DEFAULT_OUTPUT_DIR),
        metavar="PATH",
        help=f"Output directory for reports (default: {_DEFAULT_OUTPUT_DIR})",
    )
    parser.add_argument(
        "--db",
        default=str(_DEFAULT_KNOWLEDGE_DB),
        metavar="PATH",
        help=f"KnowledgeStore DB path (default: {_DEFAULT_KNOWLEDGE_DB})",
    )
    parser.add_argument(
        "--lexical-db",
        default=str(_DEFAULT_LEXICAL_DB),
        metavar="PATH",
        help=f"FTS5 lexical DB path (default: {_DEFAULT_LEXICAL_DB})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate inputs only; do not compute metrics.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Refuse to proceed if QA set is unreviewed.",
    )
    parser.add_argument(
        "--save-baseline",
        action="store_true",
        help="Write baseline_v0.json to output dir. Requires reviewed QA.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Output machine-readable JSON summary to stdout.",
    )
    parser.add_argument(
        "--discover-corpus",
        action="store_true",
        help=(
            "List academic records from the KnowledgeStore DB as corpus candidates "
            "and exit. Outputs JSON array to stdout."
        ),
    )
    parser.add_argument(
        "--refresh-lexical",
        action="store_true",
        help=(
            "Build/refresh the FTS5 lexical index for ONLY the corpus papers listed "
            "in --corpus. Reads body text from --raw-cache instead of running the "
            "full global rag-refresh. Requires --corpus."
        ),
    )
    parser.add_argument(
        "--raw-cache",
        default=str(_DEFAULT_RAW_CACHE_DIR),
        metavar="PATH",
        help=(
            f"Directory of raw academic source JSON files used by --refresh-lexical "
            f"(default: {_DEFAULT_RAW_CACHE_DIR})"
        ),
    )
    parser.add_argument(
        "--simulate-prefetch-filter",
        action="store_true",
        help=(
            "Simulate the L3 lexical relevance filter against the corpus and report "
            "projected off_topic_rate for allow/review/reject scenarios. "
            "Requires --corpus. Does not modify any DB state."
        ),
    )
    parser.add_argument(
        "--filter-config",
        default=None,
        metavar="PATH",
        help=(
            f"Path to relevance filter config JSON "
            f"(default: auto-discover {_DEFAULT_FILTER_CONFIG})"
        ),
    )

    args = parser.parse_args(argv)

    # --- Corpus discovery ---
    if args.discover_corpus:
        return _run_discover_corpus(Path(args.db))

    # --corpus is required for all non-discover-corpus flows
    if args.corpus is None:
        parser.error("--corpus is required (or use --discover-corpus to list candidates)")

    # --- Resolve corpus path ---
    corpus_path = _resolve_corpus_path(args.corpus)
    if corpus_path is None:
        if args.corpus == "v0":
            print(
                "ERROR: Could not find corpus manifest. "
                "Expected config/research_eval_benchmark_v0_corpus[.draft].json",
                file=sys.stderr,
            )
        else:
            print(f"ERROR: Corpus file not found: {args.corpus}", file=sys.stderr)
        return 1

    # --- Load corpus ---
    try:
        from packages.research.eval_benchmark.corpus import (
            load_corpus_manifest,
            CorpusValidationError,
        )
        corpus = load_corpus_manifest(corpus_path)
    except Exception as exc:
        print(f"ERROR: Failed to load corpus manifest: {exc}", file=sys.stderr)
        return 1

    # --- Simulate prefetch filter ---
    if args.simulate_prefetch_filter:
        # Load golden QA if provided (for false-negative analysis)
        pf_qa_set = None
        if args.golden_set is not None:
            golden_path = _resolve_golden_path(args.golden_set)
            if golden_path is not None:
                try:
                    from packages.research.eval_benchmark.golden_qa import load_golden_qa
                    pf_qa_set = load_golden_qa(golden_path)
                except Exception as exc:
                    print(f"WARNING: Could not load golden QA for false-negative analysis: {exc}", file=sys.stderr)
        return _run_simulate_prefetch_filter(args, corpus, qa_set=pf_qa_set)

    # --- Scoped lexical refresh ---
    if args.refresh_lexical:
        try:
            from packages.research.eval_benchmark.lexical_refresh import (
                refresh_lexical_for_corpus,
            )
            source_ids = [e.source_id for e in corpus.entries]
            result = refresh_lexical_for_corpus(
                source_ids,
                lexical_db_path=Path(args.lexical_db),
                knowledge_db_path=Path(args.db),
                cache_dir=Path(args.raw_cache),
                verbose=True,
            )
            if result.indexed == 0 and result.corpus_entries > 0:
                print(
                    "WARNING: No papers were indexed. "
                    "Check that --raw-cache points to the correct directory "
                    f"({args.raw_cache}) and that payload.body_text is non-empty.",
                    file=sys.stderr,
                )
                return 1
            return 0
        except Exception as exc:
            print(f"ERROR: Lexical refresh failed: {exc}", file=sys.stderr)
            import traceback
            traceback.print_exc(file=sys.stderr)
            return 2

    # --- Resolve golden QA path ---
    qa_set = None
    if args.golden_set is not None:
        golden_path = _resolve_golden_path(args.golden_set)
        if golden_path is None:
            if args.golden_set == "v0":
                print(
                    "ERROR: Could not find golden QA file. "
                    "Expected tests/fixtures/research_eval_benchmark/golden_qa_v0[.draft].json",
                    file=sys.stderr,
                )
            else:
                print(f"ERROR: Golden QA file not found: {args.golden_set}", file=sys.stderr)
            return 1

        try:
            from packages.research.eval_benchmark.golden_qa import (
                load_golden_qa,
                GoldenQAValidationError,
                is_reviewed,
            )
            qa_set = load_golden_qa(golden_path)
        except Exception as exc:
            print(f"ERROR: Failed to load golden QA: {exc}", file=sys.stderr)
            return 1

        # --- QA review checks ---
        if qa_set is not None and not is_reviewed(qa_set):
            print(
                f"WARNING: QA set is NOT operator-reviewed "
                f"(review_status='{qa_set.review_status}'). "
                "Results are indicative only.",
                file=sys.stderr,
            )
            if args.strict:
                print(
                    "ERROR: --strict mode requires a reviewed QA set. "
                    "Change review_status to 'reviewed' after operator review.",
                    file=sys.stderr,
                )
                return 1

        if args.save_baseline:
            if qa_set is None or not is_reviewed(qa_set):
                print(
                    "ERROR: --save-baseline requires reviewed QA. "
                    "Operator must review the QA set and set review_status='reviewed'.",
                    file=sys.stderr,
                )
                return 1

    else:
        # No golden set provided
        if args.save_baseline:
            print(
                "ERROR: --save-baseline requires --golden-set.",
                file=sys.stderr,
            )
            return 1

    # --- Dry-run: validation only ---
    if args.dry_run:
        print(f"Corpus loaded: {corpus_path}")
        print(f"  version={corpus.version}, entries={len(corpus.entries)}, "
              f"review_status={corpus.review_status}")
        if qa_set is not None:
            print(f"Golden QA loaded: {golden_path}")
            print(f"  version={qa_set.version}, pairs={len(qa_set.pairs)}, "
                  f"review_status={qa_set.review_status}")
        else:
            print("Golden QA: not provided (QA-dependent metrics will be not_available)")
        print("Dry-run complete. Inputs are valid.")
        return 0

    # --- Compute metrics ---
    try:
        from packages.research.eval_benchmark.metrics import compute_all_metrics
        from packages.research.eval_benchmark.golden_qa import GoldenQASet

        # Create empty QA set if none provided
        if qa_set is None:
            qa_set = GoldenQASet(
                version="none",
                review_status="not_provided",
                pairs=[],
            )

        metrics = compute_all_metrics(
            corpus=corpus,
            qa_set=qa_set,
            db_path=Path(args.db),
            lexical_db_path=Path(args.lexical_db),
        )
    except Exception as exc:
        print(f"ERROR: Metric computation failed: {exc}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        return 2

    # --- Recommendation ---
    try:
        from packages.research.eval_benchmark.recommender import recommend
        rec = recommend(metrics)
    except Exception as exc:
        print(f"ERROR: Recommendation failed: {exc}", file=sys.stderr)
        return 2

    # --- Strict: fail if manifest source_ids are missing from DB ---
    if args.strict and metrics.missing_source_ids:
        print(
            f"ERROR: --strict: {len(metrics.missing_source_ids)} manifest source_id(s) not "
            f"found in KnowledgeStore: {metrics.missing_source_ids[:5]}",
            file=sys.stderr,
        )
        return 1

    if metrics.missing_source_ids:
        print(
            f"WARNING: {len(metrics.missing_source_ids)} manifest source_id(s) not found "
            f"in KnowledgeStore DB. Run --discover-corpus to see what's available.",
            file=sys.stderr,
        )

    # --- Write reports ---
    try:
        from packages.research.eval_benchmark.report import write_reports
        output_dir = Path(args.output_dir)
        md_path, json_path = write_reports(
            output_dir=output_dir,
            metrics=metrics,
            recommendation=rec.label,
            rec_justification=rec.justification,
            triggered_rules=rec.triggered_rules,
        )
        print(f"Reports written:")
        print(f"  Markdown: {md_path}")
        print(f"  JSON:     {json_path}")
    except Exception as exc:
        print(f"ERROR: Report generation failed: {exc}", file=sys.stderr)
        return 2

    # --- Save baseline ---
    if args.save_baseline:
        try:
            from packages.research.eval_benchmark.report import generate_json_report
            baseline_dir = Path(args.output_dir)
            baseline_dir.mkdir(parents=True, exist_ok=True)
            baseline_path = baseline_dir / "baseline_v0.json"
            baseline_content = generate_json_report(
                metrics, rec.label, rec.justification, rec.triggered_rules
            )
            baseline_content["_baseline_tag"] = "v0"
            with baseline_path.open("w", encoding="utf-8") as fh:
                import json as _json
                _json.dump(baseline_content, fh, indent=2)
            print(f"Baseline saved: {baseline_path}")
        except Exception as exc:
            print(f"ERROR: Baseline save failed: {exc}", file=sys.stderr)
            return 2

    # --- Print summary ---
    print("")
    print(f"Recommendation: [{rec.label}] {rec.title}")
    print(f"  {rec.justification}")
    if rec.triggered_rules:
        for rule in rec.triggered_rules:
            print(f"  - {rule}")
    print("")
    print(f"Corpus size:           {metrics.corpus_size} documents")
    print(f"QA review status:      {metrics.golden_qa_review_status}")

    m1 = metrics.off_topic_rate
    if m1.status == "ok":
        print(f"Off-topic rate:        {m1.value.get('off_topic_rate_pct', '?')}%")
    m3 = metrics.fallback_rate
    if m3.status == "ok":
        print(f"Fallback rate:         {m3.value.get('fallback_rate_pct', '?')}%")
    m6 = metrics.retrieval_answer_quality
    if m6.status == "ok":
        print(f"Retrieval P@5:         {m6.value.get('p_at_5', '?')}")
    elif m6.status == "not_available":
        print(f"Retrieval P@5:         N/A ({m6.notes})")
    m4 = metrics.chunk_count_distribution
    if m4.status == "ok":
        print(f"Median chunk count:    {m4.value.get('median', '?')}")

    # --- JSON stdout ---
    if args.json_output:
        from packages.research.eval_benchmark.report import generate_json_report
        report = generate_json_report(metrics, rec.label, rec.justification, rec.triggered_rules)
        print("")
        print("--- JSON SUMMARY ---")
        print(json.dumps(report, indent=2))

    return 0
