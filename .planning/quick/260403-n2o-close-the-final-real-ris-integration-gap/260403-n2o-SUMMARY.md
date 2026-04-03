---
phase: quick-260403-n2o
plan: "01"
subsystem: RIS / dossier integration
tags: [ris, dossier, claim-extraction, hybrid-retrieval, knowledge-store, tdd]
dependency_graph:
  requires:
    - quick-260403-lim  # wallet-scan --extract-dossier hook
    - quick-260403-lir  # KS hybrid routing in MCP
  provides:
    - derived_claims populated by wallet-scan --extract-dossier
    - hybrid retrieval surfaces dossier findings
  affects:
    - packages/research/integration/dossier_extractor.py
    - tools/cli/wallet_scan.py
    - tests/test_wallet_scan_dossier_integration.py
tech_stack:
  added: []
  patterns:
    - metadata_json body-patch for claim extractor compatibility
    - TDD (RED commit then GREEN fix)
key_files:
  created:
    - docs/dev_logs/2026-04-03_ris_final_dossier_queryability_fix.md
  modified:
    - packages/research/integration/dossier_extractor.py
    - tools/cli/wallet_scan.py
    - tests/test_wallet_scan_dossier_integration.py
    - docs/features/wallet-scan-v0.md
    - docs/CURRENT_STATE.md
decisions:
  - "Patch metadata_json with body key inline in ingest_dossier_findings rather than modifying PlainTextExtractor (smaller blast radius)"
  - "Call extract_and_link directly after metadata patch rather than using post_ingest_extract=True pipeline flag (needed to interpose the patch step)"
  - "Swallow exceptions from extract_and_link with bare except to match existing non-fatal extractor contract"
metrics:
  duration: "~45 minutes"
  completed: "2026-04-03"
  tasks_completed: 2
  tasks_total: 2
  files_changed: 5
requirements_closed: [RIS-07-dossier-queryability]
---

# Phase quick-260403-n2o Plan 01: Close the Final Real RIS Integration Gap Summary

**One-liner:** Wallet-scan dossier ingest now produces `derived_claims` via metadata body-patch + direct `extract_and_link`, making findings queryable through hybrid retrieval.

---

## Tasks Completed

| # | Name | Commit | Files |
|---|------|--------|-------|
| 1 | Enable claim extraction in dossier hook and update extractor factory | 9e6ec64 | `dossier_extractor.py`, `wallet_scan.py`, `test_wallet_scan_dossier_integration.py` |
| 2 | Update docs, feature file, dev log, and CURRENT_STATE | 86bbf16 | `wallet-scan-v0.md`, `CURRENT_STATE.md`, `2026-04-03_ris_final_dossier_queryability_fix.md` |

---

## What Was Shipped

- `_make_dossier_extractor()` now passes `post_extract_claims=True` to `ingest_dossier_findings`.
- `ingest_dossier_findings` when `post_extract_claims=True`: stores the source document, patches
  `metadata_json` with `"body": doc.body` (so `_get_document_body` can find it), commits, then
  calls `extract_and_link` directly. Non-fatal: any exception is swallowed.
- 6 new tests in `TestDossierClaimExtraction` proving:
  - `derived_claims` count >= 1 after dossier ingest with claims enabled
  - `claim_evidence` links back to `source_family="dossier_report"` document
  - `query_knowledge_store_for_rrf(store, text_query="MOMENTUM")` returns >= 1 result
  - Full E2E WalletScanner run produces `derived_claims >= 1`
  - Idempotent re-ingest produces 0 new claims
  - Provenance chain: `derived_claim.source_document_id` -> `source_documents` with `source_family="dossier_report"`
- All existing 40 wallet-scan integration tests still pass.
- Full regression: 3695 tests pass, 0 failures.

---

## Decisions Made

1. **Patch `metadata_json` inline, not in `PlainTextExtractor`:** Modifying the extractor would
   affect all raw-text ingest paths, not just dossier. Patching within `ingest_dossier_findings`
   keeps the blast radius minimal and makes the intent explicit.

2. **Call `extract_and_link` directly (not via `post_ingest_extract=True`):** The metadata patch
   must happen between ingest and claim extraction. Using `pipeline.ingest(post_ingest_extract=True)`
   would call `extract_and_link` inside the pipeline before the patch could run.

3. **Swallow exceptions from `extract_and_link` with bare `except`:** The non-fatal contract for
   the dossier extractor (extractor errors never abort the scan loop) applies to claim extraction too.

---

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Body retrieval broken for dossier documents**
- **Found during:** Task 1, TDD GREEN phase
- **Issue:** `_get_document_body()` returned `None` for dossier docs because `PlainTextExtractor`
  raw-text mode sets `source_url="internal://manual"` and stores only `content_hash` in
  `metadata_json` — no `body` key. This made claim extraction a silent no-op even when
  `post_extract_claims=True` was passed.
- **Fix:** After ingestion, query `metadata_json` from the stored row, patch in `"body": doc.body`
  if absent, commit, then call `extract_and_link` directly.
- **Files modified:** `packages/research/integration/dossier_extractor.py`
- **Commit:** 9e6ec64

**Note:** Plan stated the fix was "two lines total" (just the caller change). The actual fix
required a third change in `dossier_extractor.py` to resolve the body-retrieval gap. This
is documented as a Deviation Rule 1 auto-fix.

---

## Known Stubs

None. All data paths are wired. The `derived_claims` table is populated end-to-end.

---

## Verification Results

```
pytest tests/test_wallet_scan_dossier_integration.py -x -q --tb=short
46 passed in ~2.3s

pytest tests/test_wallet_scan.py -x -q --tb=short
All passing

pytest tests/ -x -q --tb=short
3695 passed, 0 failed
```

---

## Self-Check: PASSED

Files exist:
- FOUND: docs/dev_logs/2026-04-03_ris_final_dossier_queryability_fix.md
- FOUND: docs/features/wallet-scan-v0.md (contains "derived_claims")
- FOUND: .planning/quick/260403-n2o-close-the-final-real-ris-integration-gap/260403-n2o-SUMMARY.md

Commits exist:
- FOUND: 9e6ec64 (Task 1)
- FOUND: 86bbf16 (Task 2)
