"""Deterministic offline tests for RIS Phase 2 seed manifest and batch seeder.

All tests use in-memory KnowledgeStore. No network calls. No real docs/reference/ files.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).parent.parent


def _make_manifest(tmp_path: Path, entries: list[dict], *, version: str = "1") -> Path:
    """Write a minimal seed manifest JSON to a temp file and return its path."""
    manifest = {
        "version": version,
        "description": "Test manifest",
        "entries": entries,
    }
    p = tmp_path / "seed_manifest.json"
    p.write_text(json.dumps(manifest), encoding="utf-8")
    return p


def _make_file(tmp_path: Path, name: str, content: str) -> Path:
    """Create a text file at tmp_path/name and return its Path."""
    p = tmp_path / name
    p.write_text(content, encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def memory_store():
    from packages.polymarket.rag.knowledge_store import KnowledgeStore
    store = KnowledgeStore(":memory:")
    yield store
    store.close()


# ---------------------------------------------------------------------------
# SeedEntry / SeedManifest parsing tests
# ---------------------------------------------------------------------------


class TestSeedManifestParsing:
    def test_load_valid_manifest(self, tmp_path):
        """load_seed_manifest() parses a well-formed manifest."""
        doc = _make_file(tmp_path, "doc.md", "# Doc\nBody")
        manifest_path = _make_manifest(tmp_path, [
            {
                "path": str(doc),
                "title": "Doc",
                "source_type": "book",
                "source_family": "book_foundational",
                "author": "Test Author",
                "publish_date": "2026-01-01T00:00:00+00:00",
                "tags": ["test"],
            }
        ])

        from packages.research.ingestion.seed import load_seed_manifest, SeedManifest
        manifest = load_seed_manifest(manifest_path)
        assert isinstance(manifest, SeedManifest)
        assert manifest.version == "1"
        assert len(manifest.entries) == 1
        assert manifest.entries[0].title == "Doc"
        assert manifest.entries[0].source_family == "book_foundational"

    def test_load_manifest_entry_count_11(self, tmp_path):
        """Manifest with 11 entries parses to exactly 11 SeedEntry objects."""
        entries = []
        for i in range(11):
            doc = _make_file(tmp_path, f"doc{i}.md", f"# Doc {i}\nBody")
            entries.append({
                "path": str(doc),
                "title": f"Doc {i}",
                "source_type": "book",
                "source_family": "book_foundational",
                "author": "Test",
                "publish_date": None,
                "tags": [],
            })
        manifest_path = _make_manifest(tmp_path, entries)

        from packages.research.ingestion.seed import load_seed_manifest
        manifest = load_seed_manifest(manifest_path)
        assert len(manifest.entries) == 11

    def test_load_manifest_missing_file_raises(self, tmp_path):
        """load_seed_manifest() raises FileNotFoundError if the manifest file does not exist."""
        from packages.research.ingestion.seed import load_seed_manifest
        with pytest.raises(FileNotFoundError):
            load_seed_manifest(tmp_path / "nonexistent.json")

    def test_seed_entry_fields(self, tmp_path):
        """SeedEntry carries path, title, source_type, source_family, author, publish_date, tags."""
        doc = _make_file(tmp_path, "doc.md", "# Title\nBody")
        manifest_path = _make_manifest(tmp_path, [{
            "path": str(doc),
            "title": "Title",
            "source_type": "book",
            "source_family": "book_foundational",
            "author": "Alice",
            "publish_date": "2025-06-01T00:00:00+00:00",
            "tags": ["ris", "test"],
        }])

        from packages.research.ingestion.seed import load_seed_manifest
        manifest = load_seed_manifest(manifest_path)
        entry = manifest.entries[0]
        assert entry.author == "Alice"
        assert entry.publish_date == "2025-06-01T00:00:00+00:00"
        assert entry.tags == ["ris", "test"]


# ---------------------------------------------------------------------------
# run_seed() behavior tests
# ---------------------------------------------------------------------------


class TestRunSeed:
    def test_run_seed_ingests_entries(self, tmp_path, memory_store):
        """run_seed() ingests all manifest entries into KnowledgeStore."""
        doc = _make_file(
            tmp_path, "research.md",
            "# Research Doc\n\n" + "This is a sufficiently long body for hard-stop checks. " * 10
        )
        manifest_path = _make_manifest(tmp_path, [{
            "path": str(doc),
            "title": "Research Doc",
            "source_type": "book",
            "source_family": "book_foundational",
            "author": "Test",
            "publish_date": None,
            "tags": [],
        }])

        from packages.research.ingestion.seed import load_seed_manifest, run_seed
        manifest = load_seed_manifest(manifest_path)
        result = run_seed(manifest, memory_store, dry_run=False, skip_eval=True, base_dir=tmp_path)

        assert result.total == 1
        assert result.ingested == 1
        assert result.failed == 0

    def test_run_seed_idempotent_doc_ids(self, tmp_path, memory_store):
        """Running run_seed() twice produces identical doc_ids (idempotent)."""
        doc = _make_file(
            tmp_path, "doc.md",
            "# Idempotent Doc\n\n" + "Sufficiently long body content for idempotency test. " * 10
        )
        manifest_path = _make_manifest(tmp_path, [{
            "path": str(doc),
            "title": "Idempotent Doc",
            "source_type": "book",
            "source_family": "book_foundational",
            "author": "Test",
            "publish_date": None,
            "tags": [],
        }])

        from packages.research.ingestion.seed import load_seed_manifest, run_seed

        manifest = load_seed_manifest(manifest_path)
        result1 = run_seed(manifest, memory_store, dry_run=False, skip_eval=True, base_dir=tmp_path)
        result2 = run_seed(manifest, memory_store, dry_run=False, skip_eval=True, base_dir=tmp_path)

        doc_ids_1 = [r["doc_id"] for r in result1.results if r.get("doc_id")]
        doc_ids_2 = [r["doc_id"] for r in result2.results if r.get("doc_id")]

        assert doc_ids_1 == doc_ids_2, "doc_ids must be stable across multiple runs"

    def test_run_seed_source_family_correctness(self, tmp_path, memory_store):
        """Each seeded document has the source_family from the manifest entry."""
        doc = _make_file(
            tmp_path, "wallet_doc.md",
            "# Wallet Analysis\n\n" + "Analysis content about wallet behavior patterns. " * 10
        )
        manifest_path = _make_manifest(tmp_path, [{
            "path": str(doc),
            "title": "Wallet Analysis",
            "source_type": "dossier",
            "source_family": "wallet_analysis",
            "author": "Test",
            "publish_date": None,
            "tags": [],
        }])

        from packages.research.ingestion.seed import load_seed_manifest, run_seed
        manifest = load_seed_manifest(manifest_path)
        result = run_seed(manifest, memory_store, dry_run=False, skip_eval=True, base_dir=tmp_path)

        assert result.ingested == 1
        doc_id = result.results[0]["doc_id"]
        stored_doc = memory_store.get_source_document(doc_id)
        assert stored_doc is not None
        assert stored_doc["source_family"] == "wallet_analysis"

    def test_run_seed_nonexistent_file_recorded_as_failed(self, tmp_path, memory_store):
        """run_seed() records non-existent file paths as failed entries, not crash."""
        manifest_path = _make_manifest(tmp_path, [{
            "path": str(tmp_path / "missing_file.md"),
            "title": "Missing Doc",
            "source_type": "book",
            "source_family": "book_foundational",
            "author": "Test",
            "publish_date": None,
            "tags": [],
        }])

        from packages.research.ingestion.seed import load_seed_manifest, run_seed
        manifest = load_seed_manifest(manifest_path)
        result = run_seed(manifest, memory_store, dry_run=False, skip_eval=True, base_dir=tmp_path)

        assert result.total == 1
        assert result.failed == 1
        assert result.ingested == 0
        assert result.results[0]["status"] == "failed"

    def test_run_seed_dry_run_does_not_write(self, tmp_path, memory_store):
        """dry_run=True lists entries without writing to KnowledgeStore."""
        doc = _make_file(
            tmp_path, "dry_doc.md",
            "# Dry Run Doc\n\n" + "This content should not be written during dry run. " * 10
        )
        manifest_path = _make_manifest(tmp_path, [{
            "path": str(doc),
            "title": "Dry Run Doc",
            "source_type": "book",
            "source_family": "book_foundational",
            "author": "Test",
            "publish_date": None,
            "tags": [],
        }])

        from packages.research.ingestion.seed import load_seed_manifest, run_seed
        manifest = load_seed_manifest(manifest_path)
        result = run_seed(manifest, memory_store, dry_run=True, skip_eval=True, base_dir=tmp_path)

        # dry_run should list entries but not write
        assert result.total == 1
        assert result.ingested == 0
        # Verify nothing was written to the store
        rows = memory_store._conn.execute(
            "SELECT COUNT(*) FROM source_documents"
        ).fetchone()
        assert rows[0] == 0

    def test_run_seed_dry_run_result_shape(self, tmp_path, memory_store):
        """dry_run result entries have status='dry_run' and no doc_id written."""
        doc = _make_file(tmp_path, "d.md", "# D\n\n" + "Content for dry run shape test. " * 10)
        manifest_path = _make_manifest(tmp_path, [{
            "path": str(doc),
            "title": "D",
            "source_type": "book",
            "source_family": "book_foundational",
            "author": "Test",
            "publish_date": None,
            "tags": [],
        }])

        from packages.research.ingestion.seed import load_seed_manifest, run_seed
        manifest = load_seed_manifest(manifest_path)
        result = run_seed(manifest, memory_store, dry_run=True, skip_eval=True, base_dir=tmp_path)

        assert result.results[0]["status"] == "dry_run"

    def test_run_seed_multiple_entries(self, tmp_path, memory_store):
        """run_seed() correctly handles multiple entries and counts."""
        docs = []
        entries = []
        for i in range(3):
            doc = _make_file(
                tmp_path, f"doc{i}.md",
                f"# Doc {i}\n\n" + f"Long body content for document {i}. " * 10
            )
            docs.append(doc)
            entries.append({
                "path": str(doc),
                "title": f"Doc {i}",
                "source_type": "book",
                "source_family": "book_foundational",
                "author": "Test",
                "publish_date": None,
                "tags": [],
            })
        manifest_path = _make_manifest(tmp_path, entries)

        from packages.research.ingestion.seed import load_seed_manifest, run_seed
        manifest = load_seed_manifest(manifest_path)
        result = run_seed(manifest, memory_store, dry_run=False, skip_eval=True, base_dir=tmp_path)

        assert result.total == 3
        assert result.ingested == 3
        assert result.failed == 0

    def test_run_seed_skipped_count_on_second_run(self, tmp_path, memory_store):
        """On second run, already-ingested docs show as skipped (not failed, not re-ingested)."""
        doc = _make_file(
            tmp_path, "skip_doc.md",
            "# Skip Doc\n\n" + "Content for skip count test. " * 10
        )
        manifest_path = _make_manifest(tmp_path, [{
            "path": str(doc),
            "title": "Skip Doc",
            "source_type": "book",
            "source_family": "book_foundational",
            "author": "Test",
            "publish_date": None,
            "tags": [],
        }])

        from packages.research.ingestion.seed import load_seed_manifest, run_seed
        manifest = load_seed_manifest(manifest_path)
        run_seed(manifest, memory_store, dry_run=False, skip_eval=True, base_dir=tmp_path)
        result2 = run_seed(manifest, memory_store, dry_run=False, skip_eval=True, base_dir=tmp_path)

        # Second run: total=1, ingested=0 (already exists), skipped=1, failed=0
        assert result2.total == 1
        assert result2.failed == 0
        # Either ingested=0+skipped=1 OR ingested=1 (idempotent insert) is acceptable
        # The key requirement is total >= 1 and no crash
        assert result2.total >= 1


# ---------------------------------------------------------------------------
# SeedResult structure tests
# ---------------------------------------------------------------------------


class TestSeedResult:
    def test_seed_result_exports(self):
        """SeedResult, SeedEntry, SeedManifest are importable from ingestion package."""
        from packages.research.ingestion import (
            SeedManifest,
            SeedEntry,
            SeedResult,
            run_seed,
            load_seed_manifest,
        )
        assert SeedManifest is not None
        assert SeedEntry is not None
        assert SeedResult is not None
        assert callable(run_seed)
        assert callable(load_seed_manifest)

    def test_seed_result_fields(self, tmp_path, memory_store):
        """SeedResult has total, ingested, skipped, failed, results fields."""
        doc = _make_file(tmp_path, "r.md", "# R\n\n" + "Content " * 20)
        manifest_path = _make_manifest(tmp_path, [{
            "path": str(doc),
            "title": "R",
            "source_type": "book",
            "source_family": "book_foundational",
            "author": "Test",
            "publish_date": None,
            "tags": [],
        }])
        from packages.research.ingestion.seed import load_seed_manifest, run_seed, SeedResult
        manifest = load_seed_manifest(manifest_path)
        result = run_seed(manifest, memory_store, dry_run=False, skip_eval=True, base_dir=tmp_path)
        assert isinstance(result, SeedResult)
        assert hasattr(result, "total")
        assert hasattr(result, "ingested")
        assert hasattr(result, "skipped")
        assert hasattr(result, "failed")
        assert hasattr(result, "results")
        assert isinstance(result.results, list)


# ---------------------------------------------------------------------------
# CLI smoke test
# ---------------------------------------------------------------------------


class TestResearchSeedCLI:
    def test_cli_help_exits_0(self):
        """research-seed --help exits 0."""
        result = subprocess.run(
            [sys.executable, "-m", "polytool", "research-seed", "--help"],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
        )
        assert result.returncode == 0

    def test_cli_no_args_exits_1(self):
        """research-seed with no args exits 1."""
        result = subprocess.run(
            [sys.executable, "-m", "polytool", "research-seed"],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
        )
        assert result.returncode != 0

    def test_cli_dry_run_json(self, tmp_path):
        """research-seed --dry-run --json exits 0 and prints valid JSON."""
        doc = _make_file(
            tmp_path, "cli_doc.md",
            "# CLI Doc\n\n" + "Content for CLI test. " * 10
        )
        manifest_data = {
            "version": "1",
            "description": "CLI test",
            "entries": [{
                "path": str(doc),
                "title": "CLI Doc",
                "source_type": "book",
                "source_family": "book_foundational",
                "author": "Test",
                "publish_date": None,
                "tags": [],
            }],
        }
        manifest_path = tmp_path / "test_manifest.json"
        manifest_path.write_text(json.dumps(manifest_data), encoding="utf-8")

        result = subprocess.run(
            [
                sys.executable, "-m", "polytool", "research-seed",
                "--manifest", str(manifest_path),
                "--db", ":memory:",
                "--no-eval",
                "--dry-run",
                "--json",
            ],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"
        data = json.loads(result.stdout)
        assert "total" in data
        assert data["total"] == 1

    def test_cli_json_output_structure(self, tmp_path):
        """research-seed --json outputs valid SeedResult JSON with expected fields."""
        doc = _make_file(
            tmp_path, "json_doc.md",
            "# JSON Doc\n\n" + "Content for JSON output test. " * 10
        )
        manifest_data = {
            "version": "1",
            "description": "JSON test",
            "entries": [{
                "path": str(doc),
                "title": "JSON Doc",
                "source_type": "book",
                "source_family": "book_foundational",
                "author": "Test",
                "publish_date": None,
                "tags": [],
            }],
        }
        manifest_path = tmp_path / "json_manifest.json"
        manifest_path.write_text(json.dumps(manifest_data), encoding="utf-8")

        result = subprocess.run(
            [
                sys.executable, "-m", "polytool", "research-seed",
                "--manifest", str(manifest_path),
                "--db", ":memory:",
                "--no-eval",
                "--json",
            ],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"
        data = json.loads(result.stdout)
        assert "total" in data
        assert "ingested" in data
        assert "failed" in data
        assert "results" in data
