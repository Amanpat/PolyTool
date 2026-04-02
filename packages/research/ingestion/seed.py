"""RIS Phase 2 — manifest-driven batch seeder.

Provides manifest loading and batch ingestion of the docs/reference/ corpus
into the KnowledgeStore with stable deterministic IDs and source_family tags
matching freshness_decay.json families.

Phase 3 enhancements:
- SeedEntry gains optional ``extractor`` field for explicit extractor selection.
- run_seed() auto-detects extractor from file extension when extractor=None.
- run_seed(reseed=True) deletes existing docs by source_url before re-ingesting.

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
        Source type key (e.g. "book", "reference_doc", "roadmap"). Used as
        IngestPipeline kwarg.
    source_family:
        Source-family key matching freshness_decay.json entries (authoritative).
    author:
        Document author string.
    publish_date:
        ISO-8601 publication date string, or None.
    tags:
        List of string tags for metadata.
    evidence_tier:
        Optional evidence tier label (e.g. "tier_1_internal", "tier_2_superseded").
        Provides metadata hygiene for corpus provenance tracking. None if not set.
    notes:
        Optional human-readable notes about this entry (reclassification rationale,
        usage guidance, etc.). None if not set.
    extractor:
        Optional extractor registry key to use for this entry (e.g.
        "structured_markdown", "plain_text"). If None, auto-detected from
        file extension by run_seed().
    """

    path: str
    title: str
    source_type: str
    source_family: str
    author: str = "unknown"
    publish_date: Optional[str] = None
    tags: list = field(default_factory=list)
    evidence_tier: Optional[str] = None
    notes: Optional[str] = None
    extractor: Optional[str] = None


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
        Per-entry result dicts with keys: title, path, status, doc_id, reason,
        extractor_used.
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
                evidence_tier=e.get("evidence_tier"),
                notes=e.get("notes"),
                extractor=e.get("extractor"),
            )
        except KeyError as exc:
            raise ValueError(f"Entry {i} missing required field: {exc}") from exc
        entries.append(entry)

    return SeedManifest(version=version, description=description, entries=entries)


# ---------------------------------------------------------------------------
# Extractor auto-detection
# ---------------------------------------------------------------------------

_EXTENSION_TO_EXTRACTOR: dict[str, str] = {
    ".md": "structured_markdown",
    ".markdown": "structured_markdown",
    ".pdf": "pdf",
    ".docx": "docx",
    ".doc": "docx",
}


def _detect_extractor(path: Path) -> str:
    """Auto-detect the extractor registry key from a file extension.

    Parameters
    ----------
    path:
        File path to inspect.

    Returns
    -------
    str
        Extractor registry key (e.g. ``"structured_markdown"``, ``"plain_text"``).
    """
    suffix = path.suffix.lower()
    return _EXTENSION_TO_EXTRACTOR.get(suffix, "plain_text")


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
    reseed: bool = False,
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
    reseed:
        If True, delete existing documents matching the entry's source_url before
        re-ingesting. This allows re-extraction with improved extractors without
        creating duplicates. The document ID is recomputed from content hash, so
        unchanged content produces the same ID.

    Returns
    -------
    SeedResult
        Aggregate counts and per-entry result dicts.
    """
    from packages.research.ingestion.pipeline import IngestPipeline
    from packages.research.ingestion.extractors import get_extractor, PlainTextExtractor

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
                "extractor_used": None,
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
                "extractor_used": None,
            })
            continue

        # --- determine extractor ---
        extractor_name = entry.extractor if entry.extractor else _detect_extractor(entry_path)
        extractor_fallback = False

        try:
            ext = get_extractor(extractor_name)
        except KeyError:
            # Unknown extractor key: fall back to PlainTextExtractor
            ext = PlainTextExtractor()
            extractor_name = "plain_text"
            extractor_fallback = True
        except ImportError:
            # Optional dep not installed (e.g. pdfplumber): fall back to PlainTextExtractor
            ext = PlainTextExtractor()
            extractor_name = "plain_text"
            extractor_fallback = True

        # --- reseed: delete existing doc by source_url ---
        if reseed:
            abs_path = str(entry_path.resolve()).replace("\\", "/")
            source_url_pattern = f"file://{abs_path}"
            try:
                rows = store._conn.execute(
                    "SELECT id FROM source_documents WHERE source_url = ?",
                    (source_url_pattern,),
                ).fetchall()
                for row in rows:
                    existing_id = row[0]
                    store._conn.execute(
                        "DELETE FROM source_documents WHERE id = ?",
                        (existing_id,),
                    )
                store._conn.commit()
            except Exception:
                pass  # Non-fatal; proceed with ingest

        # --- run ingestion pipeline ---
        try:
            evaluator = None
            if not skip_eval:
                from packages.research.evaluation.evaluator import DocumentEvaluator
                from packages.research.evaluation.providers import get_provider
                evaluator = DocumentEvaluator(provider=get_provider("manual"))

            pipeline = IngestPipeline(store=store, extractor=ext, evaluator=evaluator)
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
                "extractor_used": extractor_name,
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
                "extractor_used": extractor_name,
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
                "extractor_used": extractor_name,
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

        # --- store extractor metadata ---
        # Record extractor_used in the result dict for traceability
        result_entry: dict = {
            "title": entry.title,
            "path": str(entry_path),
            "status": "ingested",
            "doc_id": doc_id,
            "reason": None,
            "extractor_used": extractor_name,
        }
        if extractor_fallback:
            result_entry["extractor_fallback"] = True

        ingested += 1
        results.append(result_entry)

    total = len(manifest.entries)

    return SeedResult(
        total=total,
        ingested=ingested,
        skipped=skipped,
        failed=failed,
        results=results,
    )
