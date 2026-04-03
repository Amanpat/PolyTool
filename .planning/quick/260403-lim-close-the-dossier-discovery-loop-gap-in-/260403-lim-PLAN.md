---
phase: quick-260403-lim
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - tools/cli/wallet_scan.py
  - tests/test_wallet_scan.py
  - tests/test_wallet_scan_dossier_integration.py
  - docs/features/wallet-scan-v0.md
  - docs/CURRENT_STATE.md
  - docs/dev_logs/2026-04-03_ris_final_dossier_operationalization.md
autonomous: true
requirements: [RIS-07-DOSSIER-LOOP]

must_haves:
  truths:
    - "After wallet-scan completes, dossier findings are automatically extracted and written to KnowledgeStore when --extract-dossier is passed"
    - "Each finding preserves provenance: wallet address, user_slug, run_id, dossier_path as file:// URI"
    - "The hook is opt-in via --extract-dossier flag so all existing tests pass unchanged"
    - "An end-to-end test proves: scan-adjacent flow -> dossier extraction -> KnowledgeStore ingest -> queryable"
    - "Docs describe the dossier/discovery loop as shipped, not as aspirational"
  artifacts:
    - path: "tools/cli/wallet_scan.py"
      provides: "post-scan dossier extraction hook + --extract-dossier CLI flag"
      contains: "post_scan_extractor"
    - path: "tests/test_wallet_scan_dossier_integration.py"
      provides: "end-to-end integration test from scan-adjacent flow to KnowledgeStore"
    - path: "docs/dev_logs/2026-04-03_ris_final_dossier_operationalization.md"
      provides: "mandatory dev log"
  key_links:
    - from: "tools/cli/wallet_scan.py WalletScanner.run()"
      to: "packages/research/integration/dossier_extractor.extract_dossier_findings"
      via: "optional post_scan_extractor callable called after each successful per-user scan"
    - from: "packages/research/integration/dossier_extractor.ingest_dossier_findings"
      to: "KnowledgeStore (in-memory SQLite in tests)"
      via: "IngestPipeline with DossierAdapter"
---

<objective>
Close the dossier/discovery-loop gap identified in the prior dev log
(2026-04-03_ris_r5_dossier_and_discovery_loop.md). The dossier extraction
capability exists and is tested, but it is still a disconnected manual CLI
tool with no wallet-scan hook.

Purpose: Make dossier findings a first-class output of the wallet-scan
workflow rather than a disconnected manual side-step. The RIS_07 integration
spec describes the flow as: wallet-scan -> dossier -> KnowledgeStore. This
plan makes that flow real without redesigning the scanner.

Output:
- Thin post-scan hook wired into WalletScanner.run()
- --extract-dossier CLI flag on wallet-scan command
- End-to-end integration test proving scan -> extract -> ingest -> queryable
- Dev log + doc updates reflecting what was shipped
</objective>

<execution_context>
@D:/Coding Projects/Polymarket/PolyTool/.claude/get-shit-done/workflows/execute-plan.md
@D:/Coding Projects/Polymarket/PolyTool/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@D:/Coding Projects/Polymarket/PolyTool/docs/reference/RAGfiles/RIS_07_INTEGRATION.md
@D:/Coding Projects/Polymarket/PolyTool/docs/dev_logs/2026-04-03_ris_r5_dossier_and_discovery_loop.md

<!-- Key interfaces the executor needs. No codebase exploration required. -->

<interfaces>
<!-- From tools/cli/wallet_scan.py — the current WalletScanner.run() loop -->
```python
# WalletScanner.__init__ currently accepts:
#   scan_callable: Optional[ScanCallable] = None
#   now_provider: Optional[Callable[[], datetime]] = None

# WalletScanner.run() currently:
#   for entry in entries:
#       scan_run_root_str = self._scan_callable(identifier, scan_flags)
#       scan_run_root = Path(scan_run_root_str)
#       result = _success_result(entry, slug, scan_run_root)
#       per_user_results.append(result)
#
# The hook point is after _success_result(), before appending to per_user_results.
# scan_run_root IS the dossier directory (scan.py writes dossier.json there).

# ScanCallable type alias:
ScanCallable = Callable[[str, Dict[str, Any]], str]

# New type alias for the extractor hook:
# PostScanExtractor = Callable[[Path, str, str], None]
# args: (scan_run_root, user_slug, wallet_address)
# Returns None — results are side-effects (KnowledgeStore writes)
# Errors must be caught and logged non-fatally (never abort the scan loop)
```

<!-- From packages/research/integration/dossier_extractor.py — public API -->
```python
def extract_dossier_findings(dossier_dir: str | Path) -> list[dict]:
    """Parse dossier.json, memo.md, hypothesis_candidates.json -> 1-3 finding dicts."""

def ingest_dossier_findings(
    findings: list[dict],
    store: KnowledgeStore,
    post_extract_claims: bool = False,
) -> list[IngestResult]:
    """Ingest findings into KnowledgeStore via IngestPipeline + DossierAdapter."""

# Each finding dict has metadata.wallet, metadata.user_slug, metadata.run_id,
# metadata.dossier_path — provenance is already embedded by extract_dossier_findings.
```

<!-- From packages/polymarket/rag/knowledge_store.py — constructor for tests -->
```python
# In-memory store for tests:
from packages.polymarket.rag.knowledge_store import KnowledgeStore
store = KnowledgeStore(db_path=":memory:", embedding_model=None)

# query_knowledge_store for verifying ingest:
from packages.research.ingestion.retriever import query_knowledge_store
results = query_knowledge_store("strategy detectors", store, top_k=5)
```

<!-- From tests/test_ris_dossier_extractor.py — pattern for minimal dossier.json fixture -->
```python
# Minimal valid dossier.json fixture:
MINIMAL_DOSSIER = {
    "header": {
        "export_id": "test-export-001",
        "proxy_wallet": "0xABC",
        "user_input": "testuser",
        "generated_at": "2026-04-03T10:00:00Z",
        "window_days": 90,
        "window_start": "2026-01-03",
        "window_end": "2026-04-03",
        "max_trades": 1000,
    },
    "detectors": {
        "latest": [
            {"detector": "holding_style", "label": "MOMENTUM", "score": 0.8}
        ]
    },
    "pnl_summary": {
        "pricing_confidence": "HIGH",
        "trend_30d": "POSITIVE",
        "latest_bucket": "profitable",
    },
}
```

<!-- From tests/test_wallet_scan.py — existing test scaffolding pattern -->
```python
# _make_scan_run_root creates a scan run dir with coverage_reconciliation_report.json
# For integration test, also write dossier.json to the same run root dir.
# WalletScanner accepts scan_callable + now_provider for full offline testing.
```
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Wire post-scan dossier extraction hook into WalletScanner</name>
  <files>tools/cli/wallet_scan.py, tests/test_wallet_scan.py</files>
  <behavior>
    - Test 1: WalletScanner with no post_scan_extractor (default) runs unchanged — no dossier calls made
    - Test 2: WalletScanner with a mock post_scan_extractor receives (scan_run_root, slug, wallet) for each successful scan
    - Test 3: Failed scans do NOT call the post_scan_extractor
    - Test 4: post_scan_extractor raising an exception does NOT abort the scan loop (non-fatal, logged via print/stderr)
    - Test 5: --extract-dossier CLI flag constructs a real extractor callable that calls extract_dossier_findings + ingest_dossier_findings
    - Test 6: Without --extract-dossier, the CLI runs with no extractor (backward-compatible default)
  </behavior>
  <action>
In tools/cli/wallet_scan.py:

1. Add type alias near top:
   ```python
   PostScanExtractor = Callable[[Path, str, str], None]
   # signature: (scan_run_root, user_slug, wallet_address) -> None
   ```

2. Update WalletScanner.__init__ to accept:
   ```python
   post_scan_extractor: Optional[PostScanExtractor] = None
   ```
   Store as self._post_scan_extractor.

3. In WalletScanner.run(), after _success_result() is called and before
   per_user_results.append(result), add:
   ```python
   if self._post_scan_extractor is not None:
       wallet_addr = result.get("run_root", "")  # slug is already in result
       try:
           self._post_scan_extractor(
               scan_run_root,
               str(slug or ""),
               str(parsed_dossier_wallet(scan_run_root)),
           )
       except Exception as exc:
           print(
               f"[dossier-extract] Non-fatal error for {identifier!r}: {exc}",
               file=sys.stderr,
           )
   ```
   Note: to get the wallet, read it from the dossier if available, otherwise
   fall back to the result["run_root"] path parsing. The simplest correct
   approach: add a tiny helper `_read_wallet_from_dossier(scan_run_root)` that
   reads dossier.json["header"]["proxy_wallet"] if the file exists, returns ""
   otherwise. This keeps the hook thin with no required dossier presence.

4. Add factory function for the real extractor:
   ```python
   def _make_dossier_extractor(store_path: str = ":memory:") -> PostScanExtractor:
       """Return a post-scan extractor callable that writes findings to KnowledgeStore."""
       from packages.polymarket.rag.knowledge_store import KnowledgeStore
       from packages.research.integration.dossier_extractor import (
           extract_dossier_findings,
           ingest_dossier_findings,
       )
       store = KnowledgeStore(db_path=store_path, embedding_model=None)

       def _extract_and_ingest(scan_run_root: Path, slug: str, wallet: str) -> None:
           findings = extract_dossier_findings(scan_run_root)
           if findings:
               ingest_dossier_findings(findings, store)
               print(
                   f"[dossier-extract] {slug}: {len(findings)} finding(s) ingested "
                   f"into {store_path}",
                   file=sys.stderr,
               )

       return _extract_and_ingest
   ```
   Use lazy imports inside the factory so the default (no-extractor) path
   never imports research packages.

5. In build_parser(), add:
   ```python
   parser.add_argument(
       "--extract-dossier",
       action="store_true",
       default=False,
       help=(
           "After each wallet scan, extract dossier findings and ingest into "
           "KnowledgeStore (default db: kb/rag/knowledge/knowledge.sqlite3). "
           "Requires dossier.json to be present in the scan run root."
       ),
   )
   parser.add_argument(
       "--extract-dossier-db",
       default="kb/rag/knowledge/knowledge.sqlite3",
       help="KnowledgeStore SQLite path for --extract-dossier (default: kb/rag/knowledge/knowledge.sqlite3).",
   )
   ```

6. In main(), pass extractor to WalletScanner:
   ```python
   post_scan_extractor = None
   if args.extract_dossier:
       post_scan_extractor = _make_dossier_extractor(args.extract_dossier_db)
   scanner = WalletScanner(post_scan_extractor=post_scan_extractor)
   ```

In tests/test_wallet_scan.py:

Add a new test class TestWalletScannerDossierHook with the 6 behaviors above.
Use the existing _make_scan_run_root helper. Write a minimal dossier.json
alongside the coverage report for tests that verify the real path.
Use a call-tracking mock (a list that captures calls) rather than unittest.mock
to avoid importing mock in tests that prefer direct assertions.
  </action>
  <verify>
    <automated>python -m pytest tests/test_wallet_scan.py -x -q --tb=short</automated>
  </verify>
  <done>
    All existing wallet_scan tests pass. New TestWalletScannerDossierHook tests
    pass. WalletScanner accepts post_scan_extractor. --extract-dossier flag exists
    in CLI help. Non-fatal error handling confirmed by test.
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: End-to-end integration test + docs + dev log</name>
  <files>
    tests/test_wallet_scan_dossier_integration.py,
    docs/features/wallet-scan-v0.md,
    docs/CURRENT_STATE.md,
    docs/dev_logs/2026-04-03_ris_final_dossier_operationalization.md
  </files>
  <behavior>
    - Test 1: scan_callable writes dossier.json to scan_run_root -> WalletScanner with real extractor -> findings land in in-memory KnowledgeStore -> store has at least 1 source_document with source_family="dossier_report"
    - Test 2: Provenance fields (wallet, user_slug, dossier_path) are present in the ingested document's metadata or in source_documents table
    - Test 3: If scan_run_root has no dossier.json, the extractor hook completes without error (graceful skip)
    - Test 4: Re-running extraction on the same dossier (idempotent) produces 0 new rows due to content-hash dedup
  </behavior>
  <action>
Create tests/test_wallet_scan_dossier_integration.py:

```python
"""End-to-end integration: wallet-scan -> dossier extraction -> KnowledgeStore."""
from __future__ import annotations
import json
from pathlib import Path
import pytest
from tools.cli.wallet_scan import WalletScanner, _make_dossier_extractor

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

def _make_full_scan_root(base: Path, name: str) -> Path:
    """Create a scan run root with both coverage report and dossier.json."""
    run_root = base / name
    run_root.mkdir(parents=True, exist_ok=True)
    coverage = {
        "positions_total": 10,
        "outcome_counts": {"WIN": 5},
        "outcome_pcts": {"WIN": 1.0},
        "pnl": {"realized_pnl_net_estimated_fees_total": 42.0, "gross_pnl_total": 50.0},
        "clv_coverage": {"coverage_rate": 0.8},
    }
    (run_root / "coverage_reconciliation_report.json").write_text(
        json.dumps(coverage), encoding="utf-8"
    )
    (run_root / "dossier.json").write_text(
        json.dumps(MINIMAL_DOSSIER), encoding="utf-8"
    )
    return run_root
```

Tests:

class TestWalletScanDossierIntegration:
  test_findings_land_in_knowledge_store: 
    - Create scan_root with dossier.json using _make_full_scan_root
    - Create KnowledgeStore(db_path=":memory:", embedding_model=None)
    - Create extractor via _make_dossier_extractor but override store to in-memory
      (either expose store param, or patch the factory, or call the inner function directly)
    - Best approach: call extract_dossier_findings(scan_root) + ingest_dossier_findings(findings, store) 
      directly in the test — this IS the integration path, WalletScanner wires these together
    - Actually, for true E2E, use WalletScanner with a custom post_scan_extractor that
      captures calls AND also ingests into an in-memory store
    - Assert: store._conn.execute("SELECT COUNT(*) FROM source_documents").fetchone()[0] >= 1
    - Assert: row source_family = "dossier_report"

  test_provenance_preserved:
    - Same setup, query source_documents for the ingested row
    - Assert wallet "0xINTEGWALLET" appears in the document body or metadata column
    - Assert user_slug "integuser" appears

  test_no_dossier_json_graceful_skip:
    - Create scan_root WITHOUT dossier.json
    - Call extract_dossier_findings(scan_root) — should raise FileNotFoundError
    - WalletScanner non-fatal handler catches this; test the handler behavior by
      calling the extractor callable directly inside try/except and asserting no re-raise

  test_idempotent_reingest:
    - Ingest once, ingest again, assert row count unchanged (dedup by content_hash)

Docs updates:

1. docs/features/wallet-scan-v0.md: Add section "## Dossier Extraction (--extract-dossier)"
   after the existing output artifacts section. Describe:
   - What the flag does (calls research-dossier-extract pipeline after each successful scan)
   - CLI example: python -m polytool wallet-scan --input wallets.txt --extract-dossier
   - What gets stored (source_family=dossier_report, 1-3 docs per wallet)
   - Provenance fields (wallet, user_slug, run_id, dossier_path)
   - That findings are queryable via research-query / rag-query commands

2. docs/CURRENT_STATE.md: Find the RIS dossier section. Update the deferred item
   "Auto-trigger after wallet-scan | Not wired into wallet-scan end-of-run hook" to:
   "Auto-trigger after wallet-scan | Wired via --extract-dossier flag (2026-04-03)"
   Do a targeted search for the prior dev log reference to find the right section.
   Do NOT rewrite the entire file — only update the specific deferred-items table row.

3. docs/dev_logs/2026-04-03_ris_final_dossier_operationalization.md: Create this file
   with the mandatory dev log. Include:
   - Objective: close the auto-trigger gap from prior dev log
   - Files changed (wallet_scan.py, both test files, docs)
   - Implementation notes: hook design, non-fatal error handling, opt-in flag rationale
   - Commands run and output (pytest counts, --help grep)
   - What is now real vs still deferred
   - Codex review: Skip tier (no execution/risk code)
  </action>
  <verify>
    <automated>python -m pytest tests/test_wallet_scan_dossier_integration.py -x -q --tb=short && python -m pytest tests/ -q --tb=short --ignore=tests/test_wallet_scan_dossier_integration.py 2>&1 | tail -5</automated>
  </verify>
  <done>
    All 4 integration tests pass. Full test suite passes with no regressions.
    docs/features/wallet-scan-v0.md has --extract-dossier section.
    docs/CURRENT_STATE.md deferred item updated to reflect shipped state.
    Dev log written to docs/dev_logs/2026-04-03_ris_final_dossier_operationalization.md.
    python -m polytool wallet-scan --help shows --extract-dossier flag.
  </done>
</task>

</tasks>

<verification>
After both tasks:

1. python -m polytool --help | grep wallet-scan    # command still loads
2. python -m polytool wallet-scan --help | grep extract-dossier    # flag visible
3. python -m pytest tests/test_wallet_scan.py -x -q --tb=short    # all pass
4. python -m pytest tests/test_wallet_scan_dossier_integration.py -x -q --tb=short    # all pass
5. python -m pytest tests/ -q --tb=short 2>&1 | tail -3    # no regressions, report exact count
</verification>

<success_criteria>
- WalletScanner.run() calls the post-scan extractor for each successful scan
- Extractor errors are non-fatal (loop continues, error printed to stderr)
- --extract-dossier flag controls the feature (default off = backward compatible)
- Integration test proves: scan_run_root with dossier.json -> extract -> ingest -> >= 1 row in source_documents
- Provenance (wallet, user_slug) confirmed in ingested document
- Idempotent reingest confirmed (content-hash dedup works end-to-end)
- All pre-existing tests pass
- Dev log exists at docs/dev_logs/2026-04-03_ris_final_dossier_operationalization.md
</success_criteria>

<output>
After completion, create .planning/quick/260403-lim-close-the-dossier-discovery-loop-gap-in-/260403-lim-SUMMARY.md
</output>
