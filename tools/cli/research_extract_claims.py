"""CLI entrypoint for RIS Phase 4 claim extraction.

Processes already-ingested source documents into structured DERIVED_CLAIM
records with chunk-level evidence links and typed relations.

Usage:
  # Extract claims from a single document
  python -m polytool research-extract-claims --doc-id <DOC_ID>

  # Extract claims from all source documents in the store
  python -m polytool research-extract-claims --all

  # Dry run — report what would be extracted without writing
  python -m polytool research-extract-claims --all --dry-run

  # JSON output
  python -m polytool research-extract-claims --all --json

  # Custom DB path
  python -m polytool research-extract-claims --all --db-path artifacts/ris/knowledge.sqlite3
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main(argv: list | None = None) -> int:
    """Extract claims from ingested RIS source documents.

    Returns:
        0 on success
        1 on argument/runtime error
    """
    parser = argparse.ArgumentParser(
        prog="research-extract-claims",
        description=(
            "Extract structured DERIVED_CLAIM records from ingested RIS source documents. "
            "Creates chunk-level evidence links and typed SUPPORTS/CONTRADICTS relations. "
            "No LLM calls — entirely heuristic / regex-based."
        ),
    )

    target_group = parser.add_mutually_exclusive_group(required=True)
    target_group.add_argument(
        "--doc-id",
        metavar="DOC_ID",
        dest="doc_id",
        help="Extract claims from a single source document by ID.",
    )
    target_group.add_argument(
        "--all",
        action="store_true",
        help="Extract claims from ALL source documents in the knowledge store.",
    )

    parser.add_argument(
        "--db-path",
        metavar="PATH",
        dest="db_path",
        default=None,
        help=(
            "Path to the KnowledgeStore SQLite database. "
            "Defaults to kb/rag/knowledge/knowledge.sqlite3."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report what would be extracted without writing any records.",
    )
    parser.add_argument(
        "--json",
        dest="output_json",
        action="store_true",
        help="Output results as JSON instead of human-readable text.",
    )

    args = parser.parse_args(argv)

    try:
        from packages.polymarket.rag.knowledge_store import KnowledgeStore
        from packages.research.ingestion.claim_extractor import (
            extract_and_link,
            _get_document_body,
            _extract_assertive_sentences,
        )
        from packages.polymarket.rag.chunker import chunk_text
    except ImportError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    # Open the store
    try:
        if args.db_path:
            store = KnowledgeStore(args.db_path)
        else:
            store = KnowledgeStore()
    except Exception as exc:
        print(f"Error opening knowledge store: {exc}", file=sys.stderr)
        return 1

    try:
        if args.doc_id:
            doc_ids = [args.doc_id]
        else:
            # Fetch all source document IDs
            rows = store._conn.execute(
                "SELECT id FROM source_documents ORDER BY ingested_at"
            ).fetchall()
            doc_ids = [row["id"] for row in rows]

        if not doc_ids:
            if args.output_json:
                print(json.dumps({
                    "documents_processed": 0,
                    "total_claims": 0,
                    "total_relations": 0,
                    "per_doc_results": [],
                }))
            else:
                print("No source documents found in the knowledge store.")
            return 0

        if args.dry_run:
            return _run_dry(store, doc_ids, args.output_json,
                            _get_document_body, _extract_assertive_sentences,
                            chunk_text)

        # Live extraction
        per_doc_results = []
        total_claims = 0
        total_relations = 0
        errors = []

        for doc_id in doc_ids:
            try:
                result = extract_and_link(store, doc_id)
                per_doc_results.append(result)
                total_claims += result["claims_extracted"]
                total_relations += result["relations_created"]
            except Exception as exc:
                errors.append({"doc_id": doc_id, "error": str(exc)})

        if args.output_json:
            output = {
                "documents_processed": len(doc_ids),
                "total_claims": total_claims,
                "total_relations": total_relations,
                "per_doc_results": per_doc_results,
            }
            if errors:
                output["errors"] = errors
            print(json.dumps(output, indent=2))
        else:
            print(f"Processed {len(doc_ids)} document(s)")
            print(f"Claims extracted: {total_claims}")
            print(f"Relations created: {total_relations}")
            if errors:
                print(f"Errors: {len(errors)}", file=sys.stderr)
                for err in errors:
                    print(f"  {err['doc_id']}: {err['error']}", file=sys.stderr)
            if per_doc_results:
                print("")
                print("Per-document breakdown:")
                for r in per_doc_results:
                    short_id = r["doc_id"][:12] + "..."
                    print(
                        f"  {short_id}  claims={r['claims_extracted']}"
                        f"  relations={r['relations_created']}"
                    )

        return 1 if errors and not total_claims else 0

    except Exception as exc:
        print(f"Unexpected error: {exc}", file=sys.stderr)
        return 1

    finally:
        try:
            store.close()
        except Exception:
            pass


def _run_dry(
    store,
    doc_ids: list[str],
    output_json: bool,
    _get_document_body,
    _extract_assertive_sentences,
    chunk_text,
) -> int:
    """Dry-run mode: count what would be extracted without writing."""
    per_doc_results = []
    total_claims_estimate = 0

    for doc_id in doc_ids:
        try:
            doc = store.get_source_document(doc_id)
            if doc is None:
                per_doc_results.append({
                    "doc_id": doc_id,
                    "estimated_claims": 0,
                    "reason": "document not found",
                })
                continue

            body = _get_document_body(store, doc)
            if not body or not body.strip():
                per_doc_results.append({
                    "doc_id": doc_id,
                    "estimated_claims": 0,
                    "reason": "no body text",
                })
                continue

            chunks = chunk_text(body)
            estimate = 0
            for chunk in chunks:
                sentences = _extract_assertive_sentences(chunk.text)
                estimate += len(sentences)

            per_doc_results.append({
                "doc_id": doc_id,
                "estimated_claims": estimate,
            })
            total_claims_estimate += estimate

        except Exception as exc:
            per_doc_results.append({
                "doc_id": doc_id,
                "estimated_claims": 0,
                "reason": f"error: {exc}",
            })

    if output_json:
        print(json.dumps({
            "dry_run": True,
            "documents_would_process": len(doc_ids),
            "total_claims_estimate": total_claims_estimate,
            "per_doc_results": per_doc_results,
        }, indent=2))
    else:
        print(f"[DRY RUN] Would process {len(doc_ids)} document(s)")
        print(f"[DRY RUN] Estimated claims to extract: {total_claims_estimate}")
        if per_doc_results:
            print("")
            print("Per-document estimates:")
            for r in per_doc_results:
                short_id = r["doc_id"][:12] + "..."
                reason = f"  ({r['reason']})" if r.get("reason") else ""
                print(f"  {short_id}  ~{r['estimated_claims']} claims{reason}")

    return 0
