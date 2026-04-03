# Dev Log: RIS Final Dossier Operationalization

**Date:** 2026-04-03
**Task:** quick-260403-lim — Close the dossier/discovery-loop gap in RIS_07
**Objective:** Make dossier findings a first-class output of the wallet-scan workflow
rather than a disconnected manual side-step.

---

## Background

The prior dev log (`2026-04-03_ris_r5_dossier_and_discovery_loop.md`) shipped the
dossier extraction pipeline (`dossier_extractor.py`) and a standalone CLI command
(`research-dossier-extract`). The gap it left: the extraction was still manual-only.
An operator had to run `research-dossier-extract --dossier-dir ...` as a separate
step after each wallet scan.

RIS_07 spec describes the intended flow as: **wallet-scan -> dossier -> KnowledgeStore**.
This work closes that gap without redesigning the scanner.

---

## What was built

### Hook design

Added a `PostScanExtractor` type alias and `post_scan_extractor` parameter to
`WalletScanner.__init__()`. The hook is:

```python
PostScanExtractor = Callable[[Path, str, str], None]
# args: (scan_run_root, user_slug, wallet_address) -> None
```

The extractor is called inside `WalletScanner.run()` after each successful scan,
immediately before appending to `per_user_results`. Failed scans never trigger it.

**Non-fatal error handling:** The call is wrapped in `try/except Exception`. Any
extractor error prints to stderr (`[dossier-extract] Non-fatal error for 'X': ...`)
and the scan loop continues. The extractor can never abort a batch.

### Helper: `_read_wallet_from_dossier`

Thin helper that reads `dossier.json["header"]["proxy_wallet"]` from a scan run
root. Returns `""` gracefully if the file is absent (no required dossier presence).

### Factory: `_make_dossier_extractor(store_path)`

Factory function that uses **lazy imports** to create the real extractor callable.
The default (no-extractor) code path never pays the import cost of research packages.
Signature:

```python
def _make_dossier_extractor(store_path: str = DEFAULT_DOSSIER_DB) -> PostScanExtractor:
```

Creates a `KnowledgeStore` at `store_path` and returns a closure that calls
`extract_dossier_findings()` + `ingest_dossier_findings()` for each scan.

### CLI flags

Two new flags added to `wallet-scan`:

```
--extract-dossier        (default: False, action=store_true)
--extract-dossier-db     (default: kb/rag/knowledge/knowledge.sqlite3)
```

`main()` wires them: if `--extract-dossier` is set, calls `_make_dossier_extractor()`
and passes the result to `WalletScanner`. Default is off — all existing callers
are backward compatible.

### Opt-in rationale

The flag is opt-in (default off) because:
1. Many wallet-scan runs on `--lite` profile may not produce `dossier.json`.
2. Not all operators want RIS ingestion as part of every scan batch.
3. Existing tests and callers need zero changes.

---

## Files changed

| File | Change |
|------|--------|
| `tools/cli/wallet_scan.py` | Added `PostScanExtractor` alias, `_read_wallet_from_dossier()`, `_make_dossier_extractor()`, `post_scan_extractor` param on `WalletScanner.__init__()`, hook call in `run()`, `--extract-dossier` / `--extract-dossier-db` CLI flags, wiring in `main()` |
| `tests/test_wallet_scan.py` | Added `TestWalletScannerDossierHook` (9 tests) |
| `tests/test_wallet_scan_dossier_integration.py` | New file: 9 end-to-end integration tests |
| `docs/features/wallet-scan-v0.md` | Added "Dossier Extraction (--extract-dossier)" section |
| `docs/CURRENT_STATE.md` | Updated deferred item + new RIS Final Dossier Operationalization section |
| `docs/dev_logs/2026-04-03_ris_final_dossier_operationalization.md` | This file |

---

## Commands run and output

### TDD RED (new tests fail before implementation)

```
$ python -m pytest tests/test_wallet_scan.py::TestWalletScannerDossierHook -x -q --tb=short
ERROR: ImportError: cannot import name '_make_dossier_extractor' from 'tools.cli.wallet_scan'
1 error
```

Confirmed RED.

### TDD GREEN (implementation passes tests)

Initial green attempt hit one bug: `KnowledgeStore.__init__()` does not accept
`embedding_model` keyword argument (plan context was incorrect). Fixed by
using `KnowledgeStore(db_path=store_path)` (the actual constructor signature).

```
$ python -m pytest tests/test_wallet_scan.py -x -q --tb=short
31 passed in 0.61s
```

### Integration tests

```
$ python -m pytest tests/test_wallet_scan_dossier_integration.py -x -q --tb=short
9 passed in 0.55s
```

Initial provenance test (`test_provenance_wallet_in_document`) probed `metadata_json`
in `source_documents`, but `IngestPipeline` only stores `{content_hash: ...}` there.
The wallet is in the finding body text and the pre-ingest `metadata` dict.
Fixed tests to check the right layer: body text for wallet, title for user_slug,
and a dedicated `test_provenance_full_metadata_in_finding` that validates all four
provenance fields in the finding dict directly.

### Full regression suite

```
$ python -m pytest tests/ -q --tb=short 2>&1 | tail -5
FAILED tests/test_ris_bridge_cli_and_mcp.py::TestMCPKnowledgeStoreRouting::test_mcp_ks_active_when_db_exists
FAILED tests/test_ris_bridge_cli_and_mcp.py::TestMCPKnowledgeStoreRouting::test_mcp_ks_inactive_when_db_absent
FAILED tests/test_ris_bridge_cli_and_mcp.py::TestMCPKnowledgeStoreRouting::test_mcp_result_structure_unchanged
FAILED tests/test_simtrader_batch.py::TestRunBatch::test_batch_time_budget_stops_launching_new_markets
3685 passed, 4 failed (pre-existing, unrelated to this work)
```

All 4 failures are pre-existing and unrelated to dossier/wallet-scan changes.

### CLI flag verification

```
$ python -m polytool wallet-scan --help | grep extract
--extract-dossier       After each wallet scan, extract dossier findings and ingest ...
--extract-dossier-db    KnowledgeStore SQLite path for --extract-dossier ...
```

---

## What the first-class dossier flow now looks like

**Operator flow:**

```bash
# 1. Run wallet scan with dossier extraction
python -m polytool wallet-scan \
  --input wallets.txt \
  --profile lite \
  --extract-dossier

# 2. Query findings in RIS
python -m polytool rag-query --question "MOMENTUM strategy wallets" --hybrid --knowledge-store default
```

**Programmatic flow:**

```python
from tools.cli.wallet_scan import WalletScanner, _make_dossier_extractor

extractor = _make_dossier_extractor(store_path="kb/rag/knowledge/knowledge.sqlite3")
scanner = WalletScanner(post_scan_extractor=extractor)
scanner.run(entries=entries, ...)
```

**Integration guarantees (proven by tests):**
- `dossier.json` present -> `extract_dossier_findings()` returns >= 1 finding
- findings ingested -> `source_documents` has >= 1 row with `source_family="dossier_report"`
- user_slug visible in document title ("Dossier Detectors: integuser")
- wallet/user_slug/run_id/dossier_path all present in finding `metadata` dict
- re-ingest of same dossier: 0 new rows (content-hash dedup works end-to-end)
- missing dossier.json: WalletScanner catches `FileNotFoundError`, prints non-fatal error, loop continues

---

## What remains explicitly deferred

1. **RAG query integration**: Chroma/FTS5 full-text search not yet connected to
   `KnowledgeStore`. `rag-query` can query claims but not body text of source_documents.
   Deferred by existing authority conflict (PLAN_OF_RECORD vs Roadmap v5.1 on LLM usage).

2. **LLM-assisted memo extraction**: The `memo.md` parser strips TODO placeholders but
   requires LLM classification for higher-quality extraction. Authority conflict deferred.

3. **Parallel scan workers**: WalletScanner is still sequential. `--extract-dossier` adds
   per-scan I/O but not a bottleneck for typical batch sizes.

4. **Auto-discovery -> knowledge loop (RIS_07 Section 2)**: Candidate scanner not yet
   wired to auto-populate discovery candidates from RIS findings.

5. **SimTrader bridge / auto-hypothesis generation (RIS_07 Section 3)**: Not implemented.

---

## Codex review

**Tier: Skip** — No execution/risk/kill-switch code touched. Changes are confined to
the CLI scan hook (read-only research pipeline), test files, and docs.
No adversarial review required per Codex Review Policy.
