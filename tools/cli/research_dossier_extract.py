"""CLI entrypoint for RIS dossier extraction pipeline.

Parses existing wallet-scan dossier artifacts (dossier.json, memo.md,
hypothesis_candidates.json) into structured research findings and ingests
them into the KnowledgeStore as source_family="dossier_report".

Usage:
  python -m polytool research-dossier-extract --dossier-dir DIR
  python -m polytool research-dossier-extract --batch
  python -m polytool research-dossier-extract --dossier-dir DIR --dry-run
  python -m polytool research-dossier-extract --batch --extract-claims
  python -m polytool research-dossier-extract --batch --db-path kb/rag/knowledge/knowledge.sqlite3
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


# Default base dir for wallet dossiers
_DEFAULT_DOSSIER_BASE = Path("artifacts") / "dossiers" / "users"


def main(argv: list) -> int:
    """Extract and ingest dossier findings into the KnowledgeStore.

    Single-dossier mode: --dossier-dir DIR
    Batch mode:          --batch [--dossier-base DIR]

    Returns:
        0 on success; 1 on fatal error.
    """
    parser = argparse.ArgumentParser(
        prog="research-dossier-extract",
        description=(
            "Parse wallet-scan dossier artifacts into KnowledgeStore findings "
            "with source_family=dossier_report."
        ),
    )

    mode_group = parser.add_mutually_exclusive_group(required=True)
    mode_group.add_argument(
        "--dossier-dir",
        dest="dossier_dir",
        metavar="DIR",
        help=(
            "Path to a single dossier run directory containing dossier.json. "
            "Extracts findings from this one run."
        ),
    )
    mode_group.add_argument(
        "--batch",
        action="store_true",
        help=(
            "Walk --dossier-base and extract from all run directories that "
            "contain dossier.json."
        ),
    )

    parser.add_argument(
        "--dossier-base",
        dest="dossier_base",
        metavar="DIR",
        default=str(_DEFAULT_DOSSIER_BASE),
        help=(
            f"Base directory for batch mode (default: {_DEFAULT_DOSSIER_BASE}). "
            "Recursively walks for dossier.json files."
        ),
    )
    parser.add_argument(
        "--db-path",
        dest="db_path",
        metavar="PATH",
        default=None,
        help=(
            "KnowledgeStore SQLite DB path. "
            "Defaults to the standard RIS knowledge store path."
        ),
    )
    parser.add_argument(
        "--extract-claims",
        dest="extract_claims",
        action="store_true",
        help="Run claim extraction on each ingested document (slow, no-LLM rule-based).",
    )
    parser.add_argument(
        "--dry-run",
        dest="dry_run",
        action="store_true",
        help=(
            "Parse and print findings without ingesting into KnowledgeStore. "
            "Useful for previewing what will be extracted."
        ),
    )

    args = parser.parse_args(argv)

    # --- Determine source of findings ---
    try:
        from packages.research.integration.dossier_extractor import (
            batch_extract_dossiers,
            extract_dossier_findings,
            ingest_dossier_findings,
        )
    except ImportError as exc:
        print(f"Error: could not import dossier extractor: {exc}", file=sys.stderr)
        return 1

    if args.dossier_dir:
        dossier_dir = Path(args.dossier_dir)
        if not dossier_dir.exists():
            print(
                f"Error: dossier directory does not exist: {dossier_dir}",
                file=sys.stderr,
            )
            return 1
        dossier_json = dossier_dir / "dossier.json"
        if not dossier_json.exists():
            print(
                f"Error: dossier.json not found in {dossier_dir}",
                file=sys.stderr,
            )
            return 1
        try:
            findings = extract_dossier_findings(dossier_dir)
        except Exception as exc:
            print(f"Error: failed to extract from {dossier_dir}: {exc}", file=sys.stderr)
            return 1
        print(f"Extracted {len(findings)} finding(s) from {dossier_dir}")
    else:
        # Batch mode
        dossier_base = Path(args.dossier_base)
        if not dossier_base.exists():
            print(
                f"Warning: dossier base directory does not exist: {dossier_base}",
                file=sys.stderr,
            )
            print("No findings to extract.")
            return 0
        findings = batch_extract_dossiers(dossier_base)
        print(f"Batch scan of {dossier_base}: {len(findings)} finding(s) extracted")

    if not findings:
        print("No findings extracted. Nothing to ingest.")
        return 0

    # --- Dry run: just print findings ---
    if args.dry_run:
        print("")
        print("Dry run — findings preview (not ingested):")
        for i, f in enumerate(findings, 1):
            meta = f.get("metadata", {})
            print(
                f"  [{i}] {f['title']}"
                f" | wallet={meta.get('wallet', '?')[:12]}..."
                f" | run_id={meta.get('run_id', '?')[:8]}..."
                f" | family={f.get('source_family', '?')}"
                f" | body_len={len(f.get('body', ''))}"
            )
        return 0

    # --- Ingest into KnowledgeStore ---
    try:
        from packages.polymarket.rag.knowledge_store import (
            DEFAULT_KNOWLEDGE_DB_PATH,
            KnowledgeStore,
        )
    except ImportError as exc:
        print(f"Error: could not import KnowledgeStore: {exc}", file=sys.stderr)
        return 1

    db_path = Path(args.db_path) if args.db_path else DEFAULT_KNOWLEDGE_DB_PATH
    try:
        store = KnowledgeStore(db_path=db_path)
    except Exception as exc:
        print(f"Error: could not open KnowledgeStore at {db_path}: {exc}", file=sys.stderr)
        return 1

    try:
        results = ingest_dossier_findings(
            findings, store, post_extract_claims=args.extract_claims
        )
    except Exception as exc:
        print(f"Error during ingestion: {exc}", file=sys.stderr)
        return 1

    # --- Summarize results ---
    n_total = len(results)
    n_accepted = sum(1 for r in results if not r.rejected and r.chunk_count > 0)
    n_dedup = sum(1 for r in results if not r.rejected and r.chunk_count == 0)
    n_rejected = sum(1 for r in results if r.rejected)

    print("")
    print(f"Ingestion summary:")
    print(f"  Total findings:  {n_total}")
    print(f"  Ingested (new):  {n_accepted}")
    print(f"  Already existed: {n_dedup} (dedup by content_hash)")
    print(f"  Rejected:        {n_rejected}")
    print(f"  DB path:         {db_path}")

    if args.extract_claims:
        print("  Claim extraction: enabled")

    return 0
