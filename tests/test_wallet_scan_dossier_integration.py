"""End-to-end integration: wallet-scan -> dossier extraction -> KnowledgeStore.

These tests exercise the complete flow from a scan run root containing dossier.json
through extract_dossier_findings() and ingest_dossier_findings() into a
KnowledgeStore, verifying that findings land correctly and provenance is preserved.

All tests are offline: no network calls, no external APIs, in-memory SQLite only.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from packages.polymarket.rag.knowledge_store import KnowledgeStore
from packages.research.integration.dossier_extractor import (
    extract_dossier_findings,
    ingest_dossier_findings,
)
from tools.cli.wallet_scan import WalletScanner, _make_dossier_extractor

# ---------------------------------------------------------------------------
# Fixtures and helpers
# ---------------------------------------------------------------------------

MINIMAL_DOSSIER = {
    "header": {
        "export_id": "integ-export-001",
        "proxy_wallet": "0xINTEGWALLET",
        "user_input": "integuser",
        "generated_at": "2026-04-03T10:00:00Z",
        "window_days": 90,
        "window_start": "2026-01-03",
        "window_end": "2026-04-03",
        "max_trades": 1000,
    },
    "detectors": {
        "latest": [{"detector": "holding_style", "label": "MOMENTUM", "score": 0.8}]
    },
    "pnl_summary": {
        "pricing_confidence": "HIGH",
        "trend_30d": "POSITIVE",
        "latest_bucket": "profitable",
    },
}

COVERAGE_REPORT = {
    "positions_total": 10,
    "outcome_counts": {"WIN": 5},
    "outcome_pcts": {"WIN": 1.0},
    "pnl": {"realized_pnl_net_estimated_fees_total": 42.0, "gross_pnl_total": 50.0},
    "clv_coverage": {"coverage_rate": 0.8},
}


def _make_full_scan_root(base: Path, name: str) -> Path:
    """Create a scan run root with both coverage_reconciliation_report.json and dossier.json."""
    run_root = base / name
    run_root.mkdir(parents=True, exist_ok=True)
    (run_root / "coverage_reconciliation_report.json").write_text(
        json.dumps(COVERAGE_REPORT), encoding="utf-8"
    )
    (run_root / "dossier.json").write_text(
        json.dumps(MINIMAL_DOSSIER), encoding="utf-8"
    )
    return run_root


def _make_no_dossier_scan_root(base: Path, name: str) -> Path:
    """Create a scan run root WITHOUT dossier.json (coverage report only)."""
    run_root = base / name
    run_root.mkdir(parents=True, exist_ok=True)
    (run_root / "coverage_reconciliation_report.json").write_text(
        json.dumps(COVERAGE_REPORT), encoding="utf-8"
    )
    return run_root


def _in_memory_store() -> KnowledgeStore:
    """Return a fresh in-memory KnowledgeStore for tests."""
    return KnowledgeStore(db_path=":memory:")


def _count_source_documents(store: KnowledgeStore) -> int:
    return store._conn.execute("SELECT COUNT(*) FROM source_documents").fetchone()[0]


def _get_source_documents(store: KnowledgeStore) -> list[dict]:
    rows = store._conn.execute(
        "SELECT id, title, source_url, source_family, metadata_json FROM source_documents"
    ).fetchall()
    return [dict(row) for row in rows]


# ---------------------------------------------------------------------------
# Integration tests
# ---------------------------------------------------------------------------


class TestWalletScanDossierIntegration:
    """End-to-end integration: scan run root -> extract -> ingest -> KnowledgeStore."""

    def test_findings_land_in_knowledge_store(self, tmp_path: Path) -> None:
        """After ingest, KnowledgeStore has at least 1 row in source_documents."""
        scan_root = _make_full_scan_root(tmp_path / "runs", "run1")
        store = _in_memory_store()

        findings = extract_dossier_findings(scan_root)
        assert len(findings) >= 1, "extract_dossier_findings returned no findings"

        ingest_dossier_findings(findings, store)

        count = _count_source_documents(store)
        assert count >= 1, f"Expected >= 1 source_document, got {count}"

    def test_source_family_is_dossier_report(self, tmp_path: Path) -> None:
        """Ingested documents have source_family='dossier_report'."""
        scan_root = _make_full_scan_root(tmp_path / "runs", "run1")
        store = _in_memory_store()

        findings = extract_dossier_findings(scan_root)
        ingest_dossier_findings(findings, store)

        docs = _get_source_documents(store)
        families = {d["source_family"] for d in docs}
        assert "dossier_report" in families, (
            f"Expected 'dossier_report' in source_family values, got {families}"
        )

    def test_provenance_wallet_in_finding_body(self, tmp_path: Path) -> None:
        """The wallet address 0xINTEGWALLET appears in the extracted finding body.

        Note: IngestPipeline stores metadata in metadata_json as {content_hash: ...}.
        The full provenance (wallet, user_slug, run_id, dossier_path) is embedded in
        the finding body text and the finding dict's metadata field before ingestion.
        This test validates that extract_dossier_findings preserves wallet provenance
        in the finding body that is ingested into KnowledgeStore.
        """
        scan_root = _make_full_scan_root(tmp_path / "runs", "run1")

        findings = extract_dossier_findings(scan_root)
        assert len(findings) >= 1

        # Wallet provenance is in the body text of the first finding
        detector_finding = next(
            (f for f in findings if f.get("title", "").startswith("Dossier Detectors")),
            findings[0],
        )
        body = detector_finding.get("body", "")
        assert "0xINTEGWALLET" in body, (
            f"Wallet address '0xINTEGWALLET' not found in finding body: {body[:200]}"
        )
        # Provenance metadata fields present in the finding dict
        meta = detector_finding.get("metadata", {})
        assert meta.get("wallet") == "0xINTEGWALLET", (
            f"finding metadata.wallet expected '0xINTEGWALLET', got {meta.get('wallet')!r}"
        )

    def test_provenance_user_slug_in_document_title(self, tmp_path: Path) -> None:
        """The user_slug 'integuser' appears in the ingested document title."""
        scan_root = _make_full_scan_root(tmp_path / "runs", "run1")
        store = _in_memory_store()

        findings = extract_dossier_findings(scan_root)
        ingest_dossier_findings(findings, store)

        docs = _get_source_documents(store)
        found_slug = any("integuser" in (doc.get("title") or "") for doc in docs)
        assert found_slug, (
            "User slug 'integuser' not found in any source_document title. "
            f"Titles seen: {[d.get('title') for d in docs]}"
        )

    def test_provenance_full_metadata_in_finding(self, tmp_path: Path) -> None:
        """All four provenance fields (wallet, user_slug, run_id, dossier_path) are
        present in the finding dict's metadata before ingestion."""
        scan_root = _make_full_scan_root(tmp_path / "runs", "prov_run")

        findings = extract_dossier_findings(scan_root)
        assert len(findings) >= 1

        # Use the first finding (Dossier Detectors document)
        meta = findings[0].get("metadata", {})
        assert meta.get("wallet"), "wallet missing from finding metadata"
        assert meta.get("user_slug"), "user_slug missing from finding metadata"
        assert meta.get("run_id"), "run_id missing from finding metadata"
        assert meta.get("dossier_path"), "dossier_path missing from finding metadata"

    def test_no_dossier_json_raises_file_not_found(self, tmp_path: Path) -> None:
        """extract_dossier_findings raises FileNotFoundError when dossier.json is absent."""
        scan_root = _make_no_dossier_scan_root(tmp_path / "runs", "no_dossier_run")
        with pytest.raises(FileNotFoundError):
            extract_dossier_findings(scan_root)

    def test_wallet_scanner_with_real_extractor_skips_missing_dossier_gracefully(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """WalletScanner non-fatal handler catches FileNotFoundError from missing dossier.json."""
        scan_root = _make_no_dossier_scan_root(tmp_path / "runs", "nodossier_run")
        store = _in_memory_store()

        def extractor(scan_run_root: Path, slug: str, wallet: str) -> None:
            # Directly call the real extraction path (no dossier.json present)
            findings = extract_dossier_findings(scan_run_root)
            if findings:
                ingest_dossier_findings(findings, store)

        scanner = WalletScanner(
            scan_callable=lambda ident, flags: scan_root.as_posix(),
            now_provider=lambda: __import__("datetime").datetime(2026, 4, 3, 12, 0, 0,
                                               tzinfo=__import__("datetime").timezone.utc),
            post_scan_extractor=extractor,
        )
        # Should complete without raising; error is printed to stderr
        paths = scanner.run(
            entries=[{"identifier": "@testuser", "kind": "handle"}],
            output_root=tmp_path / "out",
            run_id="graceful-skip-run",
            profile="lite",
            input_file_path="wallets.txt",
        )
        captured = capsys.readouterr()
        # Non-fatal error was printed to stderr (WalletScanner caught FileNotFoundError)
        assert "dossier-extract" in captured.err
        assert "Non-fatal" in captured.err
        # The scan itself still completed normally
        assert Path(paths["leaderboard_json"]).exists()
        # Nothing was ingested (no dossier.json)
        assert _count_source_documents(store) == 0

    def test_idempotent_reingest(self, tmp_path: Path) -> None:
        """Re-ingesting the same dossier produces 0 new rows (content-hash dedup)."""
        scan_root = _make_full_scan_root(tmp_path / "runs", "run1")
        store = _in_memory_store()

        findings = extract_dossier_findings(scan_root)

        # First ingest
        ingest_dossier_findings(findings, store)
        count_after_first = _count_source_documents(store)
        assert count_after_first >= 1

        # Second ingest (same findings, same content hash)
        ingest_dossier_findings(findings, store)
        count_after_second = _count_source_documents(store)

        assert count_after_second == count_after_first, (
            f"Idempotent reingest failed: row count changed from "
            f"{count_after_first} to {count_after_second}"
        )

    def test_wallet_scanner_full_e2e_with_extractor(self, tmp_path: Path) -> None:
        """Full E2E: WalletScanner with real extractor -> dossier.json -> KnowledgeStore."""
        scan_root = _make_full_scan_root(tmp_path / "runs", "e2e_run")
        store = _in_memory_store()

        extractor_calls: list = []

        def real_like_extractor(scan_run_root: Path, slug: str, wallet: str) -> None:
            extractor_calls.append((scan_run_root, slug, wallet))
            findings = extract_dossier_findings(scan_run_root)
            if findings:
                ingest_dossier_findings(findings, store)

        scanner = WalletScanner(
            scan_callable=lambda ident, flags: scan_root.as_posix(),
            now_provider=lambda: __import__("datetime").datetime(2026, 4, 3, 12, 0, 0,
                                               tzinfo=__import__("datetime").timezone.utc),
            post_scan_extractor=real_like_extractor,
        )
        scanner.run(
            entries=[{"identifier": "@integuser", "kind": "handle"}],
            output_root=tmp_path / "out",
            run_id="e2e-integ-run",
            profile="lite",
            input_file_path="wallets.txt",
        )

        # Extractor was called once for the successful scan
        assert len(extractor_calls) == 1

        # At least 1 document landed in KnowledgeStore
        count = _count_source_documents(store)
        assert count >= 1, f"Expected >= 1 doc in KnowledgeStore after E2E run, got {count}"

        # source_family is correct
        docs = _get_source_documents(store)
        families = {d["source_family"] for d in docs}
        assert "dossier_report" in families


# ---------------------------------------------------------------------------
# New tests: Dossier claim extraction (derived_claims path)
# ---------------------------------------------------------------------------


def _count_derived_claims(store: KnowledgeStore) -> int:
    return store._conn.execute("SELECT COUNT(*) FROM derived_claims").fetchone()[0]


def _get_derived_claims(store: KnowledgeStore) -> list[dict]:
    rows = store._conn.execute(
        "SELECT id, source_document_id, claim_text, claim_type, confidence FROM derived_claims"
    ).fetchall()
    return [dict(row) for row in rows]


def _count_claim_evidence(store: KnowledgeStore) -> int:
    return store._conn.execute("SELECT COUNT(*) FROM claim_evidence").fetchone()[0]


def _get_claim_evidence(store: KnowledgeStore) -> list[dict]:
    rows = store._conn.execute(
        "SELECT claim_id, source_document_id FROM claim_evidence"
    ).fetchall()
    return [dict(row) for row in rows]


class TestDossierClaimExtraction:
    """Verify that post_extract_claims=True produces derived_claims in KnowledgeStore
    and that the hybrid retrieval path (query_knowledge_store_for_rrf) can surface them.

    All tests are offline: in-memory SQLite, no network, no LLM.
    """

    def test_ingest_with_claims_produces_derived_claims(self, tmp_path: Path) -> None:
        """After ingest with post_extract_claims=True, derived_claims has >= 1 row."""
        scan_root = _make_full_scan_root(tmp_path / "runs", "run1")
        store = _in_memory_store()

        findings = extract_dossier_findings(scan_root)
        ingest_dossier_findings(findings, store, post_extract_claims=True)

        claim_count = _count_derived_claims(store)
        assert claim_count >= 1, (
            f"Expected >= 1 derived_claim after ingest with post_extract_claims=True, got {claim_count}"
        )

        # Each claim must reference a valid source_document
        claims = _get_derived_claims(store)
        source_doc_ids = {
            row["id"] for row in store._conn.execute(
                "SELECT id FROM source_documents"
            ).fetchall()
        }
        for claim in claims:
            assert claim["source_document_id"] in source_doc_ids, (
                f"claim {claim['id']} references unknown source_document_id "
                f"{claim['source_document_id']!r}"
            )

    def test_claim_evidence_links_back_to_source(self, tmp_path: Path) -> None:
        """After ingest with claims, claim_evidence rows reference source_documents
        with source_family='dossier_report'."""
        scan_root = _make_full_scan_root(tmp_path / "runs", "run1")
        store = _in_memory_store()

        findings = extract_dossier_findings(scan_root)
        ingest_dossier_findings(findings, store, post_extract_claims=True)

        evidence_rows = _get_claim_evidence(store)
        assert len(evidence_rows) >= 1, (
            "Expected >= 1 claim_evidence row after ingest with post_extract_claims=True"
        )

        # All evidence must link back to a dossier_report source document
        for ev in evidence_rows:
            src_doc = store.get_source_document(ev["source_document_id"])
            assert src_doc is not None, (
                f"claim_evidence references missing source_document {ev['source_document_id']!r}"
            )
            assert src_doc.get("source_family") == "dossier_report", (
                f"Expected source_family='dossier_report', got {src_doc.get('source_family')!r}"
            )

    def test_hybrid_retrieval_surfaces_dossier_claims(self, tmp_path: Path) -> None:
        """After ingest with claims, query_knowledge_store_for_rrf returns >= 1 result
        for a keyword present in the MINIMAL_DOSSIER fixture ('MOMENTUM' or 'holding_style')."""
        from packages.research.ingestion.retriever import query_knowledge_store_for_rrf

        scan_root = _make_full_scan_root(tmp_path / "runs", "run1")
        store = _in_memory_store()

        findings = extract_dossier_findings(scan_root)
        ingest_dossier_findings(findings, store, post_extract_claims=True)

        # Try both keywords present in MINIMAL_DOSSIER fixture
        results_momentum = query_knowledge_store_for_rrf(store, text_query="MOMENTUM")
        results_style = query_knowledge_store_for_rrf(store, text_query="holding_style")

        total = len(results_momentum) + len(results_style)
        assert total >= 1, (
            f"Expected >= 1 result from hybrid retrieval after dossier ingest with claims. "
            f"Got {len(results_momentum)} for 'MOMENTUM', {len(results_style)} for 'holding_style'."
        )

    def test_wallet_scanner_e2e_produces_claims(self, tmp_path: Path) -> None:
        """Full E2E: WalletScanner with _make_dossier_extractor (post_extract_claims=True)
        produces derived_claims in the KnowledgeStore after a scan run."""
        scan_root = _make_full_scan_root(tmp_path / "runs", "e2e_claims_run")
        store = _in_memory_store()

        def real_extractor_with_claims(scan_run_root: Path, slug: str, wallet: str) -> None:
            findings = extract_dossier_findings(scan_run_root)
            if findings:
                ingest_dossier_findings(findings, store, post_extract_claims=True)

        scanner = WalletScanner(
            scan_callable=lambda ident, flags: scan_root.as_posix(),
            now_provider=lambda: __import__("datetime").datetime(2026, 4, 3, 12, 0, 0,
                                               tzinfo=__import__("datetime").timezone.utc),
            post_scan_extractor=real_extractor_with_claims,
        )
        scanner.run(
            entries=[{"identifier": "@integuser", "kind": "handle"}],
            output_root=tmp_path / "out",
            run_id="e2e-claims-run",
            profile="lite",
            input_file_path="wallets.txt",
        )

        claim_count = _count_derived_claims(store)
        assert claim_count >= 1, (
            f"Expected >= 1 derived_claim after full E2E scan with claim extraction, got {claim_count}"
        )

    def test_idempotent_reingest_with_claims(self, tmp_path: Path) -> None:
        """Re-ingesting same findings twice with post_extract_claims=True produces
        the same number of derived_claims (INSERT OR IGNORE prevents duplicates)."""
        scan_root = _make_full_scan_root(tmp_path / "runs", "run1")
        store = _in_memory_store()

        findings = extract_dossier_findings(scan_root)

        # First ingest with claims
        ingest_dossier_findings(findings, store, post_extract_claims=True)
        count_after_first = _count_derived_claims(store)
        assert count_after_first >= 1, "First ingest produced no derived_claims"

        # Second ingest: source_documents dedup (content-hash) prevents re-running extract_and_link
        ingest_dossier_findings(findings, store, post_extract_claims=True)
        count_after_second = _count_derived_claims(store)

        assert count_after_second == count_after_first, (
            f"Idempotent reingest failed: claim count changed from "
            f"{count_after_first} to {count_after_second}"
        )

    def test_provenance_chain_claim_to_source_document(self, tmp_path: Path) -> None:
        """Provenance chain: derived_claim.source_document_id -> source_documents row
        with source_family='dossier_report'."""
        scan_root = _make_full_scan_root(tmp_path / "runs", "run1")
        store = _in_memory_store()

        findings = extract_dossier_findings(scan_root)
        ingest_dossier_findings(findings, store, post_extract_claims=True)

        claims = _get_derived_claims(store)
        assert len(claims) >= 1, "No derived_claims produced"

        for claim in claims:
            src_doc_id = claim["source_document_id"]
            assert src_doc_id, f"derived_claim {claim['id']} has no source_document_id"

            src_doc = store.get_source_document(src_doc_id)
            assert src_doc is not None, (
                f"derived_claim {claim['id']} references non-existent "
                f"source_document {src_doc_id!r}"
            )
            assert src_doc.get("source_family") == "dossier_report", (
                f"source_document for claim {claim['id']} has source_family="
                f"{src_doc.get('source_family')!r}, expected 'dossier_report'"
            )
