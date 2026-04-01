"""CLI entrypoint for RIS v1 document ingestion.

Usage:
  python -m polytool research-ingest --file path/to/doc.md --no-eval
  python -m polytool research-ingest --file path/to/doc.md --json
  python -m polytool research-ingest --text "Document body..." --title "My Doc" --no-eval
  python -m polytool research-ingest --file path/to/doc.md --source-type dossier --author "analyst"
"""

from __future__ import annotations

import argparse
import json
import sys
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
        "--json", dest="output_json", action="store_true",
        help="Output raw JSON instead of human-readable text.",
    )

    if not argv:
        parser.print_help(sys.stderr)
        return 1

    args = parser.parse_args(argv)

    # Validate input arguments
    if args.file is None and args.text is None:
        print("Error: --file or --text is required.", file=sys.stderr)
        return 1

    if args.text is not None and not args.title:
        print("Error: --title is required when using --text.", file=sys.stderr)
        return 1

    if args.file is not None:
        file_path = Path(args.file)
        if not file_path.exists():
            print(f"Error: file not found: {args.file}", file=sys.stderr)
            return 1

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

        # Determine source and kwargs
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

        result = pipeline.ingest(source, **ingest_kwargs)

    except Exception as exc:
        print(f"Error: ingestion failed: {exc}", file=sys.stderr)
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
            display_title = args.title or (Path(args.file).stem if args.file else "inline")
            short_id = result.doc_id[:12] + "..." if result.doc_id else "(none)"
            print(
                f"Ingested: {display_title} | doc_id={short_id} "
                f"| chunks={result.chunk_count} | gate={gate_label}"
            )

    return 0
