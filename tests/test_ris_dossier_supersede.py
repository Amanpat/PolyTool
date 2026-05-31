"""WI-2: Dossier supersede + schema lifecycle tests (offline, in-memory DBs).

Covers the wallet-level supersede-on-new-run model:
- Changed-content rescan supersedes ALL prior-run dossier docs + claims for the
  wallet (linked via superseded_by), excluded from default retrieval.
- Missing-section case: run 2 emits fewer sections -> run 1's extra docs are
  STILL superseded (not orphaned).
- Identical-content re-ingest still skipped (unchanged).
- Transaction atomicity: mid-ingest failure leaves the OLD active set intact.
- Migration idempotency: lifecycle upgrade runs twice on an old-schema DB.
- Wallet normalization: checksummed vs lowercase match as one identity.
- Disk retention: previous-results.md copied + prior raw scan gzipped, not deleted.

These tests NEVER touch the live on-disk DB; all stores are ``:memory:`` or a
temp-file sqlite created in-test.
"""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

import pytest

_PROJECT_ROOT = Path(__file__).parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from packages.polymarket.rag.knowledge_store import KnowledgeStore  # noqa: E402
from packages.research.integration.dossier_extractor import (  # noqa: E402
    extract_dossier_findings,
    ingest_dossier_findings,
)


# ---------------------------------------------------------------------------
# Helpers — build dossier run dirs on disk
# ---------------------------------------------------------------------------

def _dossier_json(wallet: str, generated_at: str, trend: str = "upward") -> dict:
    return {
        "schema_version": 1,
        "header": {
            "export_id": f"exp-{generated_at}",
            "generated_at": generated_at,
            "max_trades": 100,
            "proxy_wallet": wallet,
            "user_input": "@testuser",
            "window_days": 30,
            "window_end": generated_at,
            "window_start": "2026-03-02T00:00:00Z",
        },
        "detectors": {
            "bucket_type": "weekly",
            "latest": [
                {"detector": "HOLDING_STYLE", "label": "SHORT_TERM", "score": 0.9},
            ],
            "trend": [],
        },
        "pnl_summary": {
            "latest_bucket": generated_at,
            "pricing_confidence": "high",
            "pricing_snapshot_ratio": 0.92,
            "trend_30d": trend,
        },
        "positions": [],
    }


_MEMO = """# LLM Research Packet v1

User input: @testuser

## Executive Summary
This wallet exhibits strong arb-likely behavior with DCA laddering and {tag}.

## Key Observations
- Wallet trades high-frequency arb patterns.
"""

_CANDS = {
    "candidates": [
        {
            "rank": 1,
            "segment_key": "category:politics",
            "clv_variant_used": "settlement",
            "metrics": {
                "avg_clv_pct": 3.5,
                "beat_close_rate": 0.65,
                "count": 42,
                "win_rate": 0.58,
                "median_clv_pct": 2.8,
            },
        }
    ],
    "generated_at": "2026-04-01T10:00:00Z",
}


def _make_run(
    tmp_path: Path,
    *,
    wallet: str,
    run_id: str,
    generated_at: str,
    memo_tag: str = "alpha",
    with_candidates: bool = True,
    with_memo: bool = True,
) -> Path:
    run_dir = (
        tmp_path / "users" / "testuser" / wallet / generated_at[:10] / run_id
    )
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "dossier.json").write_text(
        json.dumps(_dossier_json(wallet, generated_at, trend=memo_tag))
    )
    if with_memo:
        (run_dir / "memo.md").write_text(_MEMO.format(tag=memo_tag))
    if with_candidates:
        (run_dir / "hypothesis_candidates.json").write_text(json.dumps(_CANDS))
    return run_dir


def _active_dossier_docs(store: KnowledgeStore) -> list[dict]:
    rows = store._conn.execute(
        "SELECT * FROM source_documents "
        "WHERE source_family='dossier_report' AND lifecycle='active'"
    ).fetchall()
    return [dict(r) for r in rows]


def _all_dossier_docs(store: KnowledgeStore) -> list[dict]:
    rows = store._conn.execute(
        "SELECT * FROM source_documents WHERE source_family='dossier_report'"
    ).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

class TestSchema:
    def test_fresh_db_has_lifecycle_columns(self):
        store = KnowledgeStore(":memory:")
        cols = {
            r["name"]
            for r in store._conn.execute(
                "PRAGMA table_info(source_documents)"
            ).fetchall()
        }
        assert {"lifecycle", "superseded_by", "superseded_at"} <= cols
        store.close()

    def test_migration_idempotent_on_old_schema(self, tmp_path):
        """Pre-populate an old-schema DB, then run the upgrade path twice."""
        db = tmp_path / "old.sqlite3"
        conn = sqlite3.connect(str(db))
        conn.execute(
            """CREATE TABLE source_documents (
                id TEXT PRIMARY KEY, title TEXT, source_url TEXT,
                source_family TEXT, content_hash TEXT, chunk_count INTEGER,
                published_at TEXT, ingested_at TEXT, confidence_tier TEXT,
                metadata_json TEXT
            )"""
        )
        conn.execute(
            "INSERT INTO source_documents (id, title) VALUES ('d1', 'Legacy Doc')"
        )
        conn.commit()
        conn.close()

        # First open runs the upgrade.
        store = KnowledgeStore(str(db))
        cols = {
            r["name"]
            for r in store._conn.execute(
                "PRAGMA table_info(source_documents)"
            ).fetchall()
        }
        assert {"lifecycle", "superseded_by", "superseded_at"} <= cols
        # Existing row defaults to active.
        row = store._conn.execute(
            "SELECT lifecycle FROM source_documents WHERE id='d1'"
        ).fetchone()
        assert row[0] == "active"
        store.close()

        # Second open is a no-op (no error, columns not duplicated).
        store2 = KnowledgeStore(str(db))
        count = sum(
            1
            for r in store2._conn.execute(
                "PRAGMA table_info(source_documents)"
            ).fetchall()
            if r["name"] == "lifecycle"
        )
        assert count == 1
        store2.close()


# ---------------------------------------------------------------------------
# Supersede behavior
# ---------------------------------------------------------------------------

class TestSupersede:
    def test_changed_content_rescan_supersedes_prior(self, tmp_path):
        wallet = "0xABCDEF1234567890"
        store = KnowledgeStore(":memory:")

        run1 = _make_run(tmp_path, wallet=wallet, run_id="r1",
                         generated_at="2026-04-01T10:00:00Z", memo_tag="alpha")
        ingest_dossier_findings(extract_dossier_findings(run1), store,
                                post_extract_claims=True)
        active1 = _active_dossier_docs(store)
        assert len(active1) == 3  # detectors + candidates + memo

        # Rescan with changed content (different memo + trend).
        run2 = _make_run(tmp_path, wallet=wallet, run_id="r2",
                         generated_at="2026-05-01T10:00:00Z", memo_tag="beta")
        ingest_dossier_findings(extract_dossier_findings(run2), store,
                                post_extract_claims=True)

        active2 = _active_dossier_docs(store)
        # Exactly one active set (3 docs from run2).
        assert len(active2) == 3
        active_ids = {d["id"] for d in active2}
        old_ids = {d["id"] for d in active1}
        assert active_ids.isdisjoint(old_ids)

        # All run1 docs are superseded and linked.
        all_docs = {d["id"]: d for d in _all_dossier_docs(store)}
        for oid in old_ids:
            assert all_docs[oid]["lifecycle"] == "superseded"
            assert all_docs[oid]["superseded_by"] in active_ids
            assert all_docs[oid]["superseded_at"]

        # Prior claims superseded too.
        old_claims = store._conn.execute(
            "SELECT lifecycle FROM derived_claims WHERE source_document_id IN "
            f"({','.join('?' * len(old_ids))})",
            tuple(old_ids),
        ).fetchall()
        if old_claims:
            assert all(c[0] == "superseded" for c in old_claims)

        # Default query_claims excludes superseded.
        claims = store.query_claims()
        for c in claims:
            assert c["source_document_id"] in active_ids or c["source_document_id"] is None
        store.close()

    def test_missing_section_still_supersedes(self, tmp_path):
        """Run 2 emits fewer sections -> run 1's extra docs STILL superseded."""
        wallet = "0xfeed00000000beef"
        store = KnowledgeStore(":memory:")

        run1 = _make_run(tmp_path, wallet=wallet, run_id="r1",
                         generated_at="2026-04-01T10:00:00Z",
                         with_candidates=True, with_memo=True)
        ingest_dossier_findings(extract_dossier_findings(run1), store)
        assert len(_active_dossier_docs(store)) == 3

        # Run 2: detectors only (no candidates, no memo).
        run2 = _make_run(tmp_path, wallet=wallet, run_id="r2",
                         generated_at="2026-05-01T10:00:00Z",
                         with_candidates=False, with_memo=False)
        ingest_dossier_findings(extract_dossier_findings(run2), store)

        active = _active_dossier_docs(store)
        assert len(active) == 1  # only detectors
        # The prior candidates + memo docs are NOT orphaned — superseded.
        superseded = [
            d for d in _all_dossier_docs(store) if d["lifecycle"] == "superseded"
        ]
        assert len(superseded) == 3
        store.close()

    def test_identical_content_reingest_skipped(self, tmp_path):
        wallet = "0xidentical0000000"
        store = KnowledgeStore(":memory:")
        run1 = _make_run(tmp_path, wallet=wallet, run_id="r1",
                         generated_at="2026-04-01T10:00:00Z")
        findings = extract_dossier_findings(run1)
        ingest_dossier_findings(findings, store)
        n1 = store._conn.execute(
            "SELECT COUNT(*) FROM source_documents"
        ).fetchone()[0]
        active1 = {d["id"] for d in _active_dossier_docs(store)}

        # Re-ingest identical findings: no new docs, nothing superseded.
        ingest_dossier_findings(findings, store)
        n2 = store._conn.execute(
            "SELECT COUNT(*) FROM source_documents"
        ).fetchone()[0]
        active2 = {d["id"] for d in _active_dossier_docs(store)}
        assert n1 == n2
        assert active1 == active2
        store.close()

    def test_wallet_normalization_match(self, tmp_path):
        """Checksummed then lowercase address treated as one identity."""
        store = KnowledgeStore(":memory:")
        checksummed = "0xAbCdEf1234567890AbCdEf1234567890AbCdEf12"
        lower = checksummed.lower()

        run1 = _make_run(tmp_path, wallet=checksummed, run_id="r1",
                         generated_at="2026-04-01T10:00:00Z", memo_tag="alpha")
        ingest_dossier_findings(extract_dossier_findings(run1), store)

        run2 = _make_run(tmp_path, wallet=lower, run_id="r2",
                         generated_at="2026-05-01T10:00:00Z", memo_tag="beta")
        ingest_dossier_findings(extract_dossier_findings(run2), store)

        active = _active_dossier_docs(store)
        # One active set only; prior (checksummed) superseded despite case diff.
        assert len(active) == 3
        # Persisted wallet is lowercase.
        for d in active:
            meta = json.loads(d["metadata_json"] or "{}")
            assert meta["wallet"] == lower
        superseded = [
            d for d in _all_dossier_docs(store) if d["lifecycle"] == "superseded"
        ]
        assert len(superseded) == 3
        store.close()

    def test_transaction_atomicity_rollback(self, tmp_path):
        """A mid-ingest failure leaves the OLD active set intact."""
        wallet = "0xrollback00000000"
        store = KnowledgeStore(":memory:")
        run1 = _make_run(tmp_path, wallet=wallet, run_id="r1",
                         generated_at="2026-04-01T10:00:00Z", memo_tag="alpha")
        ingest_dossier_findings(extract_dossier_findings(run1), store)
        active_before = {d["id"] for d in _active_dossier_docs(store)}
        assert len(active_before) == 3

        # Build run2 findings, then make supersede explode by monkeypatching.
        run2 = _make_run(tmp_path, wallet=wallet, run_id="r2",
                         generated_at="2026-05-01T10:00:00Z", memo_tag="beta")
        findings2 = extract_dossier_findings(run2)

        orig = store.supersede_dossier_run

        def _boom(*a, **k):
            raise RuntimeError("simulated mid-ingest failure")

        store.supersede_dossier_run = _boom  # type: ignore[assignment]
        results = ingest_dossier_findings(findings2, store)
        store.supersede_dossier_run = orig  # type: ignore[assignment]

        # All results for the failed wallet are rejected.
        assert all(r is not None and r.rejected for r in results)

        # OLD active set still intact; new docs rolled back; no double active set.
        active_after = {d["id"] for d in _active_dossier_docs(store)}
        assert active_after == active_before
        # Nothing got superseded.
        superseded = [
            d for d in _all_dossier_docs(store) if d["lifecycle"] == "superseded"
        ]
        assert superseded == []
        store.close()


# ---------------------------------------------------------------------------
# Mirror exclusion
# ---------------------------------------------------------------------------

class TestMirrorExclusion:
    def test_mirror_ks_rows_excludes_superseded(self, tmp_path):
        import importlib.util

        wallet = "0xmirror0000000000"
        db = tmp_path / "mirror.sqlite3"
        store = KnowledgeStore(str(db))
        run1 = _make_run(tmp_path, wallet=wallet, run_id="r1",
                         generated_at="2026-04-01T10:00:00Z", memo_tag="alpha")
        ingest_dossier_findings(extract_dossier_findings(run1), store)
        run2 = _make_run(tmp_path, wallet=wallet, run_id="r2",
                         generated_at="2026-05-01T10:00:00Z", memo_tag="beta")
        ingest_dossier_findings(extract_dossier_findings(run2), store)
        store.close()

        # Load the mirror sync module and exercise _ks_rows directly.
        sync_path = _PROJECT_ROOT / "docs" / "scripts" / "sync-ris-mirror.py"
        spec = importlib.util.spec_from_file_location("ris_mirror_sync", sync_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        conn = mod.open_ks(db)
        rows = mod._ks_rows(conn, "source_documents")
        conn.close()
        lifecycles = {r.get("lifecycle") for r in rows}
        assert "superseded" not in lifecycles
        # Only the active run2 docs remain.
        assert len(rows) == 3


# ---------------------------------------------------------------------------
# Disk retention
# ---------------------------------------------------------------------------

class TestRetention:
    def test_retention_on_rescan(self, tmp_path):
        wallet = "0xretain0000000000"
        store = KnowledgeStore(":memory:")
        run1 = _make_run(tmp_path, wallet=wallet, run_id="r1",
                         generated_at="2026-04-01T10:00:00Z", memo_tag="alpha")
        ingest_dossier_findings(extract_dossier_findings(run1), store)

        run2 = _make_run(tmp_path, wallet=wallet, run_id="r2",
                         generated_at="2026-05-01T10:00:00Z", memo_tag="beta")
        ingest_dossier_findings(extract_dossier_findings(run2), store)

        # previous-results.md copied into the new run dir.
        prev = run2 / "previous-results.md"
        assert prev.exists()
        assert "alpha" in prev.read_text(encoding="utf-8")

        # Prior raw scan dir gzipped (tar.gz), original removed (not hard-deleted
        # in the sense that the archive retains it).
        archive = Path(str(run1) + ".tar.gz")
        assert archive.exists()
        assert not run1.exists()
        store.close()

    def test_no_retention_when_no_supersede(self, tmp_path):
        """First scan (no prior run) -> no previous-results, no archive."""
        wallet = "0xfirst00000000000"
        store = KnowledgeStore(":memory:")
        run1 = _make_run(tmp_path, wallet=wallet, run_id="r1",
                         generated_at="2026-04-01T10:00:00Z")
        ingest_dossier_findings(extract_dossier_findings(run1), store)
        assert not (run1 / "previous-results.md").exists()
        assert not Path(str(run1) + ".tar.gz").exists()
        assert run1.exists()
        store.close()
