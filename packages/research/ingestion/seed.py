"""RIS Phase 2 — manifest-driven batch seeder.

Provides manifest loading and batch ingestion of the docs/reference/ corpus
into the KnowledgeStore with stable deterministic IDs and source_family tags
matching freshness_decay.json families.

Usage::

    from packages.research.ingestion.seed import load_seed_manifest, run_seed

    manifest = load_seed_manifest(Path("config/seed_manifest.json"))
    result = run_seed(manifest, store, dry_run=False, skip_eval=True)
    print(f"Ingested: {result.ingested}/{result.total}")
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# Default repo-relative paths
_DEFAULT_MANIFEST_PATH = Path("config") / "seed_manifest.json"
_REPO_ROOT = Path(__file__).parent.parent.parent.parent


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


@dataclass
class SeedEntry:
    """A single entry in the seed manifest.

    Attributes
    ----------
    path:
        File path relative to the repo root (or absolute if absolute).
    title:
        Human-readable document title.
    source_type:
        Source type key (e.g. "book", "dossier"). Used as IngestPipeline kwarg.
    source_family:
        Source-family key matching freshness_decay.json entries (authoritative).
    author:
        Document author string.
    publish_date:
        ISO-8601 publication date string, or None.
    tags:
        List of string tags for metadata.
    """

    path: str
    title: str
    source_type: str
    source_family: str
    author: str = "unknown"
    publish_date: Optional[str] = None
    tags: list = field(default_factory=list)


@dataclass
class SeedManifest:
    """Parsed seed manifest.

    Attributes
    ----------
    version:
        Manifest schema version string.
    description:
        Human-readable description.
    entries:
        List of SeedEntry objects.
    """

    version: str
    description: str
    entries: list[SeedEntry]


@dataclass
class SeedResult:
    """Result from a run_seed() call.

    Attributes
    ----------
    total:
        Total entries in manifest.
    ingested:
        Successfully ingested entries.
    skipped:
        Skipped entries (already existed in store).
    failed:
        Failed entries (file not found, hard-stop rejection, etc.).
    results:
        Per-entry result dicts with keys: title, path, status, doc_id, reason.
    """

    total: int
    ingested: int
    skipped: int
    failed: int
    results: list[dict] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Manifest loading
# ---------------------------------------------------------------------------


def load_seed_manifest(manifest_path: "str | Path") -> SeedManifest:
    """Load and parse a seed manifest JSON file.

    Parameters
    ----------
    manifest_path:
        Path to the manifest JSON file.

    Returns
    -------
    SeedManifest

    Raises
    ------
    FileNotFoundError
        If the manifest file does not exist.
    ValueError
        If the manifest JSON is malformed or missing required fields.
    """
    path = Path(manifest_path)
    if not path.exists():
        raise FileNotFoundError(f"Seed manifest not found: {path}")

    raw = json.loads(path.read_text(encoding="utf-8"))

    version = str(raw.get("version", "1"))
    description = raw.get("description", "")
    raw_entries = raw.get("entries", [])

    if not isinstance(raw_entries, list):
        raise ValueError(f"Seed manifest 'entries' must be a list, got {type(raw_entries)}")

    entries: list[SeedEntry] = []
    for i, e in enumerate(raw_entries):
        if not isinstance(e, dict):
            raise ValueError(f"Entry {i} in seed manifest is not a dict")
        try:
            entry = SeedEntry(
                path=e["path"],
                title=e["title"],
                source_type=e["source_type"],
                source_family=e["source_family"],
                author=e.get("author", "unknown"),
                publish_date=e.get("publish_date"),
                tags=e.get("tags", []),
            )
        except KeyError as exc:
            raise ValueError(f"Entry {i} missing required field: {exc}") from exc
        entries.append(entry)

    return SeedManifest(version=version, description=description, entries=entries)


# ---------------------------------------------------------------------------
# Batch seeder
# ---------------------------------------------------------------------------


def run_seed(
    manifest: SeedManifest,
    store: "KnowledgeStore",  # type: ignore[name-defined]  # noqa: F821
    *,
    dry_run: bool = False,
    skip_eval: bool = True,
    base_dir: Optional[Path] = None,
) -> SeedResult:
    """Ingest all manifest entries into the KnowledgeStore.

    Parameters
    ----------
    manifest:
        Parsed SeedManifest to process.
    store:
        KnowledgeStore instance to write to.
    dry_run:
        If True, collect and report entries without writing to store.
    skip_eval:
        If True, skip the optional evaluation gate (hard-stop checks still run).
    base_dir:
        Base directory for resolving relative entry paths.
        Defaults to the repo root.

    Returns
    -------
    SeedResult
        Aggregate counts and per-entry result dicts.
    """
    from packages.research.ingestion.pipeline import IngestPipeline

    base = Path(base_dir) if base_dir is not None else _REPO_ROOT

    ingested = 0
    skipped = 0
    failed = 0
    results: list[dict] = []

    for entry in manifest.entries:
        entry_path = Path(entry.path)
        if not entry_path.is_absolute():
            entry_path = base / entry_path

        # --- dry run mode ---
        if dry_run:
            results.append({
                "title": entry.title,
                "path": str(entry_path),
                "status": "dry_run",
                "doc_id": None,
                "reason": None,
            })
            continue

        # --- resolve file existence ---
        if not entry_path.exists():
            failed += 1
            results.append({
                "title": entry.title,
                "path": str(entry_path),
                "status": "failed",
                "doc_id": None,
                "reason": f"File not found: {entry_path}",
            })
            continue

        # --- run ingestion pipeline ---
        try:
            evaluator = None
            if not skip_eval:
                from packages.research.evaluation.evaluator import DocumentEvaluator
                from packages.research.evaluation.providers import get_provider
                evaluator = DocumentEvaluator(provider=get_provider("manual"))

            pipeline = IngestPipeline(store=store, evaluator=evaluator)
            ingest_kwargs: dict = {
                "source_type": entry.source_type,
                "author": entry.author,
                "title": entry.title,
            }
            if entry.publish_date:
                ingest_kwargs["publish_date"] = entry.publish_date

            ingest_result = pipeline.ingest(entry_path, **ingest_kwargs)

        except FileNotFoundError as exc:
            failed += 1
            results.append({
                "title": entry.title,
                "path": str(entry_path),
                "status": "failed",
                "doc_id": None,
                "reason": str(exc),
            })
            continue
        except Exception as exc:
            failed += 1
            results.append({
                "title": entry.title,
                "path": str(entry_path),
                "status": "failed",
                "doc_id": None,
                "reason": f"Unexpected error: {exc}",
            })
            continue

        if ingest_result.rejected:
            failed += 1
            results.append({
                "title": entry.title,
                "path": str(entry_path),
                "status": "failed",
                "doc_id": None,
                "reason": ingest_result.reject_reason or "rejected by pipeline",
            })
            continue

        doc_id = ingest_result.doc_id

        # --- override source_family with authoritative manifest value ---
        # PlainTextExtractor maps source_type through SOURCE_FAMILIES which produces
        # different family keys than freshness_decay.json. The manifest entry's
        # source_family is authoritative.
        try:
            store._conn.execute(
                "UPDATE source_documents SET source_family = ? WHERE id = ?",
                (entry.source_family, doc_id),
            )
            store._conn.commit()
        except Exception:
            pass  # Non-fatal; doc was ingested even if family update fails

        # Determine if this was a new insert or a duplicate (idempotent INSERT OR IGNORE)
        # If the doc already existed, the UPDATE above is a no-op but the doc_id is valid
        # We track this as "ingested" for both new and existing because INSERT OR IGNORE
        # is the idempotency mechanism -- the result is the same stable doc_id.
        ingested += 1
        results.append({
            "title": entry.title,
            "path": str(entry_path),
            "status": "ingested",
            "doc_id": doc_id,
            "reason": None,
        })

    total = len(manifest.entries)

    return SeedResult(
        total=total,
        ingested=ingested,
        skipped=skipped,
        failed=failed,
        results=results,
    )
