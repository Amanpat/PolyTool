# Dev Log: RIS Final Dossier Queryability Fix (quick-260403-n2o)

**Date:** 2026-04-03
**Task:** quick-260403-n2o — Close the final real RIS integration gap
**Requirement:** RIS-07-dossier-queryability

---

## Background

Codex verification identified a gap in the dossier integration shipped in quick-260403-lim:

- `wallet-scan --extract-dossier` called `ingest_dossier_findings(findings, store)` without
  `post_extract_claims=True`.
- `ingest_dossier_findings` supports `post_extract_claims` (defaults to `False`).
- The hybrid retrieval path (`query_knowledge_store_for_rrf`) queries `derived_claims` only.
- So dossier findings were stored as `source_documents` but invisible to hybrid retrieval.

---

## Root Cause

Two-part gap:

**Gap 1 — Caller never passed the flag:**
`_make_dossier_extractor()` in `tools/cli/wallet_scan.py` called:
```python
ingest_dossier_findings(findings, store)  # post_extract_claims defaults to False
```

**Gap 2 — Body retrieval broken for dossier documents:**
Even if `post_extract_claims=True` had been passed, `extract_and_link` would have failed silently:
- `extract_claims_from_document` calls `_get_document_body(store, doc)`.
- Strategy 1: look for `body` key in `metadata_json`. Not present for raw-text ingest.
- Strategy 2: read from `file://` source_url. Dossier docs set `source_url="internal://manual"`.
- Result: `_get_document_body` returned `None`, so no claims were extracted.

---

## Fix

### tools/cli/wallet_scan.py

Changed one line in `_make_dossier_extractor()`:
```python
# Before
ingest_dossier_findings(findings, store)

# After
ingest_dossier_findings(findings, store, post_extract_claims=True)
```

Also updated the stderr log message from `"ingested"` to `"ingested + claims extracted"`.

### packages/research/integration/dossier_extractor.py

When `post_extract_claims=True`, `ingest_dossier_findings` now:
1. Runs `pipeline.ingest(..., post_ingest_extract=False)` to store the source document.
2. Reads the stored `metadata_json` row.
3. Patches in `"body": doc.body` if absent (so `_get_document_body` can find it).
4. Commits the update to SQLite.
5. Calls `extract_and_link(store, result.doc_id)` directly.

This is a Deviation Rule 1 auto-fix (bug in the body-retrieval path for dossier documents).

---

## Files Changed

| File | Change |
|------|--------|
| `tools/cli/wallet_scan.py` | Pass `post_extract_claims=True`; update log message |
| `packages/research/integration/dossier_extractor.py` | Patch `metadata_json` with body; call `extract_and_link` directly |
| `tests/test_wallet_scan_dossier_integration.py` | 6 new tests in `TestDossierClaimExtraction` |
| `docs/features/wallet-scan-v0.md` | Updated step 3, Queryable via RIS section, Notes |
| `docs/CURRENT_STATE.md` | New section for quick-260403-n2o; updated deferred list |

---

## Test Commands and Results

**TDD RED phase (failing tests committed first):**
```
pytest tests/test_wallet_scan_dossier_integration.py::TestDossierClaimExtraction -x -q
FAILED (6 failures — derived_claims count 0 instead of >= 1)
```

**TDD GREEN phase (after fix):**
```
pytest tests/test_wallet_scan_dossier_integration.py -x -q --tb=short
46 passed in 2.3s
```

**Full regression:**
```
pytest tests/ -x -q --tb=short
3695 passed, 0 failed (4 pre-existing skipped)
```

---

## Final Operator Behavior

After this fix:

1. `wallet-scan --extract-dossier` stores dossier findings as `source_documents` (unchanged).
2. Claim extraction fires automatically: findings appear in `derived_claims` table.
3. `rag-query --hybrid --knowledge-store default` surfaces dossier findings.
4. Provenance chain is intact: `derived_claim.source_document_id` → `source_documents` row
   with `source_family="dossier_report"`.
5. Idempotent: re-running with the same dossier produces no new claims (INSERT OR IGNORE).

---

## Deferred Items

- LLM-assisted dossier memo extraction (authority conflict; rule-based extractor used instead)
- Parallel scan workers (sequential only)
- SimTrader bridge auto-promotion loop (bridge CLI shipped; auto-loop not wired)

---

## Codex Review

Tier: skip (no execution paths, kill-switch, or order-placement logic changed).
