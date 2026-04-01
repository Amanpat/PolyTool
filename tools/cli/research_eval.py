"""CLI entrypoint for RIS v1 document evaluation.

Usage:
  python -m polytool research-eval --file path/to/doc.md
  python -m polytool research-eval --title "Title" --body "Body text..." --source-type arxiv
  python -m polytool research-eval --title "Title" --body "Body..." --json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main(argv: list) -> int:
    """Evaluate a document through the RIS quality gate.

    Returns:
        0 on success
        1 on argument error
        2 on evaluation error
    """
    parser = argparse.ArgumentParser(
        prog="research-eval",
        description="Evaluate a document through the RIS v1 quality gate.",
    )
    input_group = parser.add_mutually_exclusive_group()
    input_group.add_argument(
        "--file", metavar="PATH",
        help="Read document from file (markdown or plain text). Title from filename.",
    )
    parser.add_argument(
        "--title", metavar="TEXT",
        help="Document title (required if no --file).",
    )
    parser.add_argument(
        "--body", metavar="TEXT",
        help="Document body inline (required if no --file).",
    )
    parser.add_argument(
        "--source-type", metavar="TYPE", default="manual",
        help="Source type (default: manual). Examples: arxiv, reddit, github, blog, news.",
    )
    parser.add_argument(
        "--author", metavar="TEXT", default="unknown",
        help="Document author (default: unknown).",
    )
    parser.add_argument(
        "--provider", metavar="NAME", default="manual",
        choices=["manual", "ollama"],
        help="Evaluation provider (default: manual).",
    )
    parser.add_argument(
        "--json", dest="output_json", action="store_true",
        help="Output raw JSON instead of formatted text.",
    )

    if not argv:
        parser.print_help(sys.stderr)
        return 1

    args = parser.parse_args(argv)

    # Resolve document content
    if args.file:
        file_path = Path(args.file)
        if not file_path.exists():
            print(f"Error: file not found: {args.file}", file=sys.stderr)
            return 1
        title = file_path.stem
        body = file_path.read_text(encoding="utf-8")
    else:
        if not args.title or not args.body:
            print(
                "Error: --title and --body are required when --file is not provided.",
                file=sys.stderr,
            )
            return 1
        title = args.title
        body = args.body

    # Build doc and evaluate
    try:
        from packages.research.evaluation.types import EvalDocument
        from packages.research.evaluation.evaluator import evaluate_document

        import hashlib
        doc_id = "cli_" + hashlib.sha256(body.encode("utf-8")).hexdigest()[:12]

        doc = EvalDocument(
            doc_id=doc_id,
            title=title,
            author=args.author,
            source_type=args.source_type,
            source_url="",
            source_publish_date=None,
            body=body,
        )

        decision = evaluate_document(doc, provider_name=args.provider)

    except Exception as exc:
        print(f"Error: evaluation failed: {exc}", file=sys.stderr)
        return 2

    # Output
    if args.output_json:
        output = {
            "gate": decision.gate,
            "doc_id": decision.doc_id,
            "timestamp": decision.timestamp,
        }
        if decision.scores:
            output["scores"] = {
                "relevance": decision.scores.relevance,
                "novelty": decision.scores.novelty,
                "actionability": decision.scores.actionability,
                "credibility": decision.scores.credibility,
                "total": decision.scores.total,
                "epistemic_type": decision.scores.epistemic_type,
                "summary": decision.scores.summary,
                "key_findings": decision.scores.key_findings,
                "eval_model": decision.scores.eval_model,
            }
        if decision.hard_stop and not decision.hard_stop.passed:
            output["hard_stop"] = {
                "stop_type": decision.hard_stop.stop_type,
                "reason": decision.hard_stop.reason,
            }
        print(json.dumps(output, indent=2))
    else:
        if decision.hard_stop and not decision.hard_stop.passed:
            print(
                f"Gate: REJECT | Hard stop: {decision.hard_stop.stop_type} "
                f"-- {decision.hard_stop.reason}"
            )
        elif decision.scores:
            s = decision.scores
            print(
                f"Gate: {decision.gate} | Total: {s.total}/20 | "
                f"R:{s.relevance} N:{s.novelty} A:{s.actionability} C:{s.credibility} | "
                f"Model: {s.eval_model}"
            )
        else:
            print(f"Gate: {decision.gate}")

    return 0
