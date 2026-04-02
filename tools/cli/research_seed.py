"""CLI entrypoint for RIS Phase 2 manifest-driven corpus seeding.

Phase 3: adds --reseed flag to re-ingest with improved extractors.

Usage:
  python -m polytool research-seed
  python -m polytool research-seed --manifest config/seed_manifest.json --no-eval --json
  python -m polytool research-seed --manifest config/seed_manifest.json --dry-run
  python -m polytool research-seed --manifest config/seed_manifest.json --db :memory: --json
  python -m polytool research-seed --manifest config/seed_manifest.json --reseed --no-eval
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main(argv: list) -> int:
    """Seed the RIS knowledge store from a manifest file.

    Returns:
        0 on success (even if some entries fail -- expected behavior)
        1 on argument error or manifest not found
        2 on unexpected exception
    """
    parser = argparse.ArgumentParser(
        prog="research-seed",
        description="Seed the RIS v1 knowledge store from a manifest file.",
    )
    parser.add_argument(
        "--manifest", metavar="PATH",
        default="config/seed_manifest.json",
        help="Path to seed manifest JSON (default: config/seed_manifest.json).",
    )
    parser.add_argument(
        "--db", metavar="PATH", default=None,
        help="Custom knowledge store path (default: kb/rag/knowledge/knowledge.sqlite3).",
    )
    parser.add_argument(
        "--no-eval", dest="no_eval", action="store_true",
        help="Skip evaluation gate (hard-stop checks still run). Default for seed.",
    )
    parser.add_argument(
        "--dry-run", dest="dry_run", action="store_true",
        help="List what would be ingested without writing to KnowledgeStore.",
    )
    parser.add_argument(
        "--reseed", action="store_true",
        help=(
            "Delete and re-ingest existing documents. Use after extractor upgrades to "
            "replace stale extraction metadata with improved versions. "
            "Document identity (ID) is preserved for unchanged content."
        ),
    )
    parser.add_argument(
        "--json", dest="output_json", action="store_true",
        help="Output raw JSON instead of human-readable text.",
    )

    if not argv:
        parser.print_help(sys.stderr)
        return 1

    args = parser.parse_args(argv)

    # Resolve manifest path
    manifest_path = Path(args.manifest)
    if not manifest_path.is_absolute():
        # Try relative to cwd first, then repo root
        if not manifest_path.exists():
            repo_root = Path(__file__).parent.parent.parent
            manifest_path = repo_root / args.manifest

    store = None
    try:
        from packages.research.ingestion.seed import load_seed_manifest, run_seed

        try:
            manifest = load_seed_manifest(manifest_path)
        except FileNotFoundError:
            print(f"Error: manifest not found: {args.manifest}", file=sys.stderr)
            return 1
        except ValueError as exc:
            print(f"Error: invalid manifest: {exc}", file=sys.stderr)
            return 1

        from packages.polymarket.rag.knowledge_store import (
            KnowledgeStore,
            DEFAULT_KNOWLEDGE_DB_PATH,
        )

        db_path = args.db if args.db else DEFAULT_KNOWLEDGE_DB_PATH
        # For in-memory, don't bother creating directory
        if db_path != ":memory:":
            store = KnowledgeStore(db_path)
        else:
            store = KnowledgeStore(":memory:")

        skip_eval = args.no_eval  # for seed, --no-eval is common; default respects the flag

        result = run_seed(
            manifest,
            store,
            dry_run=args.dry_run,
            skip_eval=skip_eval,
            base_dir=None,  # use repo root
            reseed=args.reseed,
        )

    except Exception as exc:
        print(f"Error: seed failed: {exc}", file=sys.stderr)
        return 2
    finally:
        if store is not None:
            store.close()

    # Output
    if args.output_json:
        output = {
            "total": result.total,
            "ingested": result.ingested,
            "skipped": result.skipped,
            "failed": result.failed,
            "dry_run": args.dry_run,
            "reseed": args.reseed,
            "results": result.results,
        }
        print(json.dumps(output, indent=2))
    else:
        mode = "[DRY RUN] " if args.dry_run else ""
        reseed_note = " [reseed mode]" if args.reseed else ""
        print(f"{mode}Seed complete{reseed_note}: {result.ingested} ingested, "
              f"{result.skipped} skipped, {result.failed} failed "
              f"(total: {result.total})")
        print()
        # Print table header
        col_w = 40
        print(f"{'Title':<{col_w}} {'Status':<12} {'doc_id':<16} {'Extractor':<22} {'Reason'}")
        print("-" * 110)
        for r in result.results:
            title = (r["title"] or "")[:col_w - 1]
            status = r.get("status", "?")
            doc_id_short = (r.get("doc_id") or "")[:14]
            extractor = (r.get("extractor_used") or "")[:20]
            reason = (r.get("reason") or "")[:30]
            print(f"{title:<{col_w}} {status:<12} {doc_id_short:<16} {extractor:<22} {reason}")

    return 0
