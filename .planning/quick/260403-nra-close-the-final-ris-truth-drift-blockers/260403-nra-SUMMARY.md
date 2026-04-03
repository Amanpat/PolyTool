---
phase: quick-260403-nra
plan: 01
subsystem: docs / cli-help
tags: [truth-drift, wallet-scan, ris, documentation]
dependency_graph:
  requires: [quick-260403-n2o]
  provides: [accurate-wallet-scan-docs, correct-cli-help]
  affects: [docs/features/wallet-scan-v0.md, tools/cli/wallet_scan.py]
tech_stack:
  added: []
  patterns: [docs-only fix, help-string correction]
key_files:
  modified:
    - docs/features/wallet-scan-v0.md
    - tools/cli/wallet_scan.py
  created:
    - docs/dev_logs/2026-04-03_wallet_scan_truth_drift_fix.md
    - .planning/quick/260403-nra-close-the-final-ris-truth-drift-blockers/260403-nra-SUMMARY.md
decisions:
  - "Fixed rag-query example by removing --knowledge-store from vector-only path (confirmed --knowledge-store requires --hybrid in rag_query.py line 210)"
metrics:
  duration: ~8 minutes
  completed: 2026-04-03T21:10:39Z
  tasks_completed: 2
  files_modified: 2
  files_created: 2
---

# Phase quick-260403-nra Plan 01: wallet-scan truth-drift doc fix Summary

**One-liner**: Corrected 3 truth-drift blockers in wallet-scan docs and help text — post_extract_claims flag name, rag-query --knowledge-store requires --hybrid, removed non-existent research-query from CLI help.

---

## Tasks Completed

| # | Task | Commit | Files |
|---|------|--------|-------|
| 1 | Fix wallet-scan-v0.md truth drift (2 blockers) | 4c5c4ef | docs/features/wallet-scan-v0.md |
| 2 | Fix wallet_scan.py help text + dev log | 7397d86 | tools/cli/wallet_scan.py, docs/dev_logs/2026-04-03_wallet_scan_truth_drift_fix.md |

---

## What Was Done

### Task 1: wallet-scan-v0.md (2 blockers)

**Blocker 1 — post_ingest_extract flag drift**

The feature doc said `post_ingest_extract=True` which was the pipeline flag approach that was NOT used. The shipped code calls `ingest_dossier_findings(findings, store, post_extract_claims=True)` which calls `extract_and_link()` directly. Updated the doc to reflect the actual shipped parameter and mechanism.

**Blocker 2 — rag-query second example broken at runtime**

The second example (`--knowledge-store default` without `--hybrid`) would fail with `Error: --knowledge-store requires --hybrid mode.` (confirmed in `tools/cli/rag_query.py` lines 210-212). Fixed by replacing it with a plain vector-only query (no `--knowledge-store`) with a comment clarifying what each path searches.

### Task 2: wallet_scan.py help text (1 blocker) + dev log

**Blocker 3 — research-query in help text**

`--extract-dossier` help string referenced `research-query` which does not exist in the CLI (not registered in `polytool/__main__.py`). Replaced with `rag-query command (use --hybrid --knowledge-store default for derived claims)`.

Dev log created at `docs/dev_logs/2026-04-03_wallet_scan_truth_drift_fix.md`.

---

## Verification Results

All success criteria passed:

```
PASS 1: post_ingest_extract removed, post_extract_claims present
PASS 2: research-query removed from help text
PASS 3: dev log exists
```

CLI smoke test: `python -m polytool --help` and `python -m polytool wallet-scan --help` both load without errors.

---

## Deviations from Plan

**1. [Rule 1 - Bug] rag-query second example had broken --knowledge-store usage**

- **Found during**: Task 1, Blocker 2 investigation
- **Issue**: The plan said "if `--knowledge-store` truly errors without --hybrid, remove it." Confirmed: `rag_query.py` lines 210-212 show a hard error when `--knowledge-store` is used without `--hybrid`. The old example `--knowledge-store default` without `--hybrid` would fail at runtime.
- **Fix**: Replaced with a plain vector-only example (no `--knowledge-store` flag) with clarifying comment, rather than adding `--hybrid` to a "Standard vector-only retrieval" example which would be semantically contradictory.
- **Files modified**: `docs/features/wallet-scan-v0.md`
- **Commit**: 4c5c4ef

No other deviations.

---

## Known Stubs

None. All changes are documentation and help text corrections with no data-flow stubs.

---

## Self-Check: PASSED

- [x] `docs/features/wallet-scan-v0.md` — modified and committed in 4c5c4ef
- [x] `tools/cli/wallet_scan.py` — modified and committed in 7397d86
- [x] `docs/dev_logs/2026-04-03_wallet_scan_truth_drift_fix.md` — created and committed in 7397d86
- [x] Commit 4c5c4ef exists
- [x] Commit 7397d86 exists
- [x] `python -m polytool wallet-scan --help` runs without error
- [x] `grep "post_ingest_extract" docs/features/wallet-scan-v0.md` returns empty
- [x] `grep "research-query" tools/cli/wallet_scan.py` returns empty
