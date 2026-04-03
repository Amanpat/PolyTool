"""CLI entrypoint for RIS v1 document ingestion.

Usage:
  python -m polytool research-ingest --file path/to/doc.md --no-eval
  python -m polytool research-ingest --file path/to/doc.md --json
  python -m polytool research-ingest --text "Document body..." --title "My Doc" --no-eval
  python -m polytool research-ingest --file path/to/doc.md --source-type dossier --author "analyst"

  # Phase 4 external-source adapter path:
  python -m polytool research-ingest --from-adapter tests/fixtures/ris_external_sources/arxiv_sample.json --source-family academic --no-eval --json
  python -m polytool research-ingest --from-adapter github_repo.json --source-family github --cache-dir artifacts/research/raw_source_cache/ --no-eval
"""

from __future__ import annotations

import argparse
import json
import sys
import time as _time
from datetime import datetime, timezone
from pathlib import Path


def main(argv: list) -> int:
    """Ingest a document into the RIS knowledge store.

    Returns:
        0 on success (including hard-stop rejections -- that is expected behavior)
        1 on argument error
        2 on unexpected exception
    """
    parser = argparse.ArgumentParser(
        prog="research-ingest",
        description="Ingest a document into the RIS v1 knowledge store.",
    )
    input_group = parser.add_mutually_exclusive_group()
    input_group.add_argument(
        "--file", metavar="PATH",
        help="Read document from file (Markdown or plain text).",
    )
    input_group.add_argument(
        "--text", metavar="TEXT",
        help="Inline document body to ingest (requires --title).",
    )
    input_group.add_argument(
        "--from-adapter", metavar="JSON_PATH",
        dest="from_adapter",
        help="Ingest from a raw-source JSON file via the adapter path (requires --source-family).",
    )
    parser.add_argument(
        "--title", metavar="TEXT",
        help="Document title (required with --text; optional override with --file).",
    )
    parser.add_argument(
        "--source-type", metavar="TYPE", default="manual",
        help="Source type (default: manual). Examples: arxiv, reddit, dossier, blog, news.",
    )
    parser.add_argument(
        "--author", metavar="TEXT", default="unknown",
        help="Document author (default: unknown).",
    )
    parser.add_argument(
        "--db", metavar="PATH", default=None,
        help="Custom knowledge store path (default: kb/rag/knowledge/knowledge.sqlite3).",
    )
    parser.add_argument(
        "--no-eval", dest="no_eval", action="store_true",
        help="Skip evaluation gate (hard-stop checks still run).",
    )
    parser.add_argument(
        "--provider", metavar="NAME", default="manual",
        choices=["manual", "ollama"],
        help="Evaluation provider (default: manual; only used when eval is active).",
    )
    parser.add_argument(
        "--source-family", metavar="FAMILY",
        dest="source_family",
        choices=["academic", "github", "blog", "news", "book"],
        help="Source family for --from-adapter path (academic/github/blog/news/book).",
    )
    parser.add_argument(
        "--cache-dir", metavar="PATH",
        dest="cache_dir",
        default=None,
        help="Directory for raw-source cache (default: artifacts/research/raw_source_cache/). "
             "Only used with --from-adapter.",
    )
    parser.add_argument(
        "--json", dest="output_json", action="store_true",
        help="Output raw JSON instead of human-readable text.",
    )
    parser.add_argument(
        "--extract-claims",
        dest="extract_claims",
        action="store_true",
        help="Run claim extraction after ingest (opt-in; non-fatal if extraction fails).",
    )
    parser.add_argument(
        "--run-log",
        dest="run_log",
        metavar="PATH",
        default="artifacts/research/run_log.jsonl",
        help="Path to run log JSONL for health tracking (default: artifacts/research/run_log.jsonl).",
    )

    if not argv:
        parser.print_help(sys.stderr)
        return 1

    args = parser.parse_args(argv)

    # Validate input arguments
    if args.file is None and args.text is None and args.from_adapter is None:
        print("Error: --file, --text, or --from-adapter is required.", file=sys.stderr)
        return 1

    if args.text is not None and not args.title:
        print("Error: --title is required when using --text.", file=sys.stderr)
        return 1

    if args.file is not None:
        file_path = Path(args.file)
        if not file_path.exists():
            print(f"Error: file not found: {args.file}", file=sys.stderr)
            return 1

    if args.from_adapter is not None:
        adapter_path = Path(args.from_adapter)
        if not adapter_path.exists():
            print(f"Error: adapter JSON file not found: {args.from_adapter}", file=sys.stderr)
            return 1
        if not args.source_family:
            print("Error: --source-family is required when using --from-adapter.", file=sys.stderr)
            return 1

    # Capture timing for run_log (health surface)
    _t0 = _time.monotonic()
    _started_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    _ingest_error: bool = False

    store = None
    try:
        from packages.polymarket.rag.knowledge_store import (
            KnowledgeStore,
            DEFAULT_KNOWLEDGE_DB_PATH,
        )
        from packages.research.ingestion.pipeline import IngestPipeline

        db_path = args.db if args.db else DEFAULT_KNOWLEDGE_DB_PATH
        store = KnowledgeStore(db_path)

        # Build evaluator if eval is active
        evaluator = None
        if not args.no_eval:
            from packages.research.evaluation.evaluator import DocumentEvaluator
            from packages.research.evaluation.providers import get_provider
            provider = get_provider(args.provider)
            evaluator = DocumentEvaluator(provider=provider)

        pipeline = IngestPipeline(store=store, evaluator=evaluator)

        if args.from_adapter:
            # Phase 4 adapter path: load raw JSON -> ingest via adapter
            from packages.research.ingestion.source_cache import RawSourceCache

            adapter_path = Path(args.from_adapter)
            raw_source = json.loads(adapter_path.read_text(encoding="utf-8"))

            cache_dir = args.cache_dir or "artifacts/research/raw_source_cache"
            raw_cache = RawSourceCache(Path(cache_dir))

            result = pipeline.ingest_external(
                raw_source,
                args.source_family,
                cache=raw_cache,
                post_ingest_extract=args.extract_claims,
            )
        else:
            # Standard file/text path
            ingest_kwargs: dict = {
                "source_type": args.source_type,
                "author": args.author,
            }
            if args.title:
                ingest_kwargs["title"] = args.title

            if args.file:
                source = Path(args.file)
            else:
                source = args.text  # type: ignore[assignment]

            result = pipeline.ingest(
                source,
                post_ingest_extract=args.extract_claims,
                **ingest_kwargs,
            )

    except Exception as exc:
        print(f"Error: ingestion failed: {exc}", file=sys.stderr)
        _ingest_error = True
        # Write error run record (non-fatal — health surface, not core pipeline)
        try:
            from packages.research.monitoring.run_log import RunRecord, append_run
            _duration = _time.monotonic() - _t0
            rec = RunRecord(
                pipeline="research_ingest",
                started_at=_started_at,
                duration_s=_duration,
                accepted=0,
                rejected=0,
                errors=1,
                exit_status="error",
                metadata={"source_type": args.source_type},
            )
            append_run(rec, path=Path(args.run_log))
        except Exception:
            pass  # Non-fatal: health surface, not core pipeline
        return 2
    finally:
        if store is not None:
            store.close()

    # Output
    if result.rejected:
        print(f"Rejected: {result.reject_reason}", file=sys.stderr)

    gate_label = "skipped"
    if result.gate_decision is not None:
        gate_label = result.gate_decision.gate

    if args.output_json:
        output: dict = {
            "doc_id": result.doc_id,
            "chunk_count": result.chunk_count,
            "rejected": result.rejected,
            "reject_reason": result.reject_reason,
            "gate": gate_label,
        }
        if result.gate_decision is not None and result.gate_decision.scores:
            s = result.gate_decision.scores
            output["scores"] = {
                "total": s.total,
                "relevance": s.relevance,
                "novelty": s.novelty,
                "actionability": s.actionability,
                "credibility": s.credibility,
            }
        print(json.dumps(output, indent=2))
    else:
        if result.rejected:
            print(f"Rejected | reason={result.reject_reason}")
        else:
            # Determine title for display
            if args.title:
                display_title = args.title
            elif args.file:
                display_title = Path(args.file).stem
            elif args.from_adapter:
                display_title = Path(args.from_adapter).stem
            else:
                display_title = "inline"
            short_id = result.doc_id[:12] + "..." if result.doc_id else "(none)"
            print(
                f"Ingested: {display_title} | doc_id={short_id} "
                f"| chunks={result.chunk_count} | gate={gate_label}"
            )

    # Write success run record (non-fatal — health surface, not core pipeline)
    try:
        from packages.research.monitoring.run_log import RunRecord, append_run
        _duration = _time.monotonic() - _t0
        _accepted = 0 if result.rejected else 1
        _rejected = 1 if result.rejected else 0
        rec = RunRecord(
            pipeline="research_ingest",
            started_at=_started_at,
            duration_s=_duration,
            accepted=_accepted,
            rejected=_rejected,
            errors=0,
            exit_status="ok",
            metadata={"source_type": args.source_type},
        )
        append_run(rec, path=Path(args.run_log))
    except Exception:
        pass  # Non-fatal: health surface, not core pipeline

    return 0
