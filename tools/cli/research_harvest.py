"""CLI for RIS L4 Multi-source Academic Harvesters.

Discover academic paper candidates from multiple sources (arXiv, Semantic Scholar,
Crossref, OpenReview), score with the existing L3 relevance filter, and enqueue
to the prefetch review queue for operator labeling.

METADATA-ONLY: No PDFs are downloaded. No Marker is called. No indexing occurs.
Candidates flow into the existing review queue and wait for:
  1. Operator label (allow/reject via research-prefetch-review label)
  2. Enqueue to Marker queue (research-marker-queue enqueue)
  3. Marker parse + L1 ingest (research-marker-queue warm-process)
  4. L2 query (research-query)

Usage:
  python -m polytool research-harvest \\
    --search "prediction markets microstructure" \\
    --source semantic_scholar \\
    --max-results 20

  python -m polytool research-harvest \\
    --search "limit order book dynamics" \\
    --source arxiv \\
    --since 2024-01-01

  python -m polytool research-harvest \\
    --search "market making optimal strategy" \\
    --source all \\
    --max-results 10

  python -m polytool research-harvest --list-sources
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional


_REPO_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_QUEUE_PATH = (
    _REPO_ROOT / "artifacts" / "research" / "prefetch_review_queue" / "review_queue.jsonl"
)


def _load_filter_config():
    """Load the lexical filter config, returning None on failure."""
    try:
        from packages.research.relevance_filter.scorer import load_filter_config
        cfg_path = _REPO_ROOT / "config" / "research" / "relevance_filter_config.json"
        if cfg_path.exists():
            return load_filter_config(str(cfg_path))
        return load_filter_config(None)
    except Exception as exc:
        print(f"WARNING: could not load filter config: {exc}", file=sys.stderr)
        return None


def _print_source_matrix() -> None:
    """Print the source capability matrix and exit."""
    from packages.research.ingestion.academic_harvesters import SOURCE_CAPABILITY_MATRIX

    print("L4 Academic Source Capability Matrix")
    print("=" * 72)
    for name, caps in SOURCE_CAPABILITY_MATRIX.items():
        status = caps.get("status", "active")
        label = f"[{status.upper()}]" if status != "active" else ""
        print(f"\n{name} {label}")
        print(f"  {caps['description']}")
        print(f"  Auth required:    {caps['auth_required']}")
        print(f"  Metadata only:    {caps['metadata_only']}")
        print(f"  PDF URL capable:  {caps['pdf_url_capable']}")
        print(f"  Backfill mode:    {caps['backfill_mode']}")
        print(f"  Monitoring mode:  {caps['monitoring_mode']}")
        print(f"  Rate limit:       {caps['rate_limit_note']}")
        print(f"  Notes: {caps['notes']}")


def _run_harvest(
    query: str,
    sources: list[str],
    max_results: int,
    since_date: Optional[str],
    force: bool,
    dry_run: bool,
    queue_path: Path,
    _http_fn=None,
) -> int:
    """Core harvest logic. Returns exit code."""
    from packages.research.ingestion.academic_harvesters import (
        HARVESTER_REGISTRY,
        dedup_candidates,
        get_harvester,
    )
    from packages.research.relevance_filter import (
        CandidateInput,
        RelevanceScorer,
        ReviewQueueStore,
        candidate_id_from_url,
    )

    filter_cfg = _load_filter_config()
    scorer = RelevanceScorer(filter_cfg) if filter_cfg else None
    if scorer is None:
        print("WARNING: L3 relevance filter config not loaded. "
              "All candidates will be enqueued as 'review'.", file=sys.stderr)

    queue = ReviewQueueStore(queue_path)

    # Collect candidates from all requested sources
    all_candidates = []
    for source in sources:
        if source not in HARVESTER_REGISTRY:
            print(f"ERROR: unknown source '{source}'. Use --list-sources.", file=sys.stderr)
            return 1

        harvester = get_harvester(source, _http_fn=_http_fn)
        print(f"  [{source}] searching: {query!r} max_results={max_results}", file=sys.stderr)
        try:
            if since_date:
                candidates = harvester.search_since(query, since_date, max_results=max_results)
            else:
                candidates = harvester.search(query, max_results=max_results)
        except Exception as exc:
            print(f"  [{source}] ERROR: {exc}", file=sys.stderr)
            candidates = []

        print(f"  [{source}] found {len(candidates)} candidates", file=sys.stderr)
        all_candidates.extend(candidates)

    if not all_candidates:
        print("No candidates found.")
        return 0

    # Cross-source deduplication
    before_dedup = len(all_candidates)
    all_candidates = dedup_candidates(all_candidates)
    deduped = before_dedup - len(all_candidates)
    if deduped:
        print(f"  Deduplication: removed {deduped} cross-source duplicate(s)", file=sys.stderr)

    # Score and enqueue
    enqueued = 0
    skipped_existing = 0
    skipped_reject = 0

    results_summary: list[dict] = []

    for candidate in all_candidates:
        if scorer and filter_cfg:
            ci = CandidateInput(
                title=candidate.title,
                abstract=candidate.abstract,
                source_url=candidate.source_url,
                fields_of_study=candidate.fields_of_study,
            )
            decision_obj = scorer.score(ci)
            decision = decision_obj.decision
            score = decision_obj.score
            raw_score = decision_obj.raw_score
            reason_codes = decision_obj.reason_codes
            matched_terms = decision_obj.matched_terms
            allow_threshold = filter_cfg.allow_threshold
            review_threshold = filter_cfg.review_threshold
            config_version = filter_cfg.version
        else:
            decision = "review"
            score = 0.5
            raw_score = 0.0
            reason_codes = []
            matched_terms = {}
            allow_threshold = 0.55
            review_threshold = 0.35
            config_version = "unknown"

        if decision == "reject":
            skipped_reject += 1
            results_summary.append({
                "action": "reject",
                "title": candidate.title[:60],
                "source": candidate.source_name,
                "score": round(score, 3),
            })
            continue

        record = candidate.to_review_queue_record(
            decision=decision,
            score=score,
            raw_score=raw_score,
            reason_codes=reason_codes,
            matched_terms=matched_terms,
            allow_threshold=allow_threshold,
            review_threshold=review_threshold,
            config_version=config_version,
        )

        if dry_run:
            results_summary.append({
                "action": f"dry-run-{decision}",
                "title": candidate.title[:60],
                "source": candidate.source_name,
                "score": round(score, 3),
                "url": candidate.source_url,
            })
            enqueued += 1
        else:
            written = queue.enqueue(record, force=force)
            if written:
                enqueued += 1
                results_summary.append({
                    "action": f"enqueued-{decision}",
                    "title": candidate.title[:60],
                    "source": candidate.source_name,
                    "score": round(score, 3),
                    "url": candidate.source_url,
                })
            else:
                skipped_existing += 1
                results_summary.append({
                    "action": "skip-existing",
                    "title": candidate.title[:60],
                    "source": candidate.source_name,
                })

    # Print summary
    print()
    print("=== research-harvest results ===")
    print(f"  query:           {query!r}")
    print(f"  sources:         {', '.join(sources)}")
    print(f"  discovered:      {before_dedup}")
    print(f"  after dedup:     {len(all_candidates)}")
    print(f"  rejected:        {skipped_reject}")
    print(f"  skip-existing:   {skipped_existing}")
    print(f"  enqueued:        {enqueued}{'  [DRY RUN - not written]' if dry_run else ''}")
    print()
    for r in results_summary[:40]:
        action = r["action"]
        title = r.get("title", "")
        source = r.get("source", "")
        score_str = f"  score={r['score']:.3f}" if "score" in r else ""
        print(f"  [{action}] [{source}]{score_str}  {title}")
    if len(results_summary) > 40:
        print(f"  ... and {len(results_summary) - 40} more")

    if not dry_run and enqueued > 0:
        print()
        print("Next steps:")
        print("  1. Label items:  python -m polytool research-prefetch-review list")
        print("  2. For each allowed paper:")
        print("     python -m polytool research-marker-queue enqueue --url <arxiv_url>")
        print("  3. Process queue: python -m polytool research-marker-queue warm-process")
        print("  4. Query corpus:  python -m polytool research-query --question '...'")

    return 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="research-harvest",
        description=(
            "L4 Multi-source academic candidate discovery. "
            "Searches multiple academic APIs for paper metadata, scores with "
            "the L3 relevance filter, and enqueues to the prefetch review queue. "
            "NO PDFs are downloaded. NO Marker is called. NO indexing occurs."
        ),
    )
    parser.add_argument(
        "--search",
        metavar="QUERY",
        help="Topic/keyword search query (required unless --list-sources)",
    )
    parser.add_argument(
        "--source",
        metavar="SOURCE",
        default="semantic_scholar",
        help=(
            "Source to harvest from: arxiv | semantic_scholar | crossref | openreview | all. "
            "Default: semantic_scholar. Use 'all' to query all active sources."
        ),
    )
    parser.add_argument(
        "--max-results",
        type=int,
        default=20,
        metavar="N",
        help="Max candidates per source. Default: 20.",
    )
    parser.add_argument(
        "--since",
        metavar="YYYY-MM-DD",
        help="Only return papers published on or after this date (monitoring mode).",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-enqueue candidates already in the review queue (skip dedup).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be enqueued without writing to the queue.",
    )
    parser.add_argument(
        "--list-sources",
        action="store_true",
        help="Print the source capability matrix and exit.",
    )
    parser.add_argument(
        "--queue-path",
        metavar="PATH",
        help=f"Override queue file path. Default: {_DEFAULT_QUEUE_PATH}",
    )
    parser.add_argument(
        "--json",
        dest="output_json",
        action="store_true",
        help="Print results as JSON lines to stdout.",
    )

    args = parser.parse_args(argv)

    if args.list_sources:
        _print_source_matrix()
        return 0

    if not args.search:
        parser.error("--search QUERY is required (or use --list-sources)")

    # Expand 'all' to all active sources
    from packages.research.ingestion.academic_harvesters import HARVESTER_REGISTRY
    if args.source == "all":
        sources = list(HARVESTER_REGISTRY.keys())
    else:
        sources = [args.source]

    queue_path = Path(args.queue_path) if args.queue_path else _DEFAULT_QUEUE_PATH

    return _run_harvest(
        query=args.search,
        sources=sources,
        max_results=args.max_results,
        since_date=args.since,
        force=args.force,
        dry_run=args.dry_run,
        queue_path=queue_path,
    )
