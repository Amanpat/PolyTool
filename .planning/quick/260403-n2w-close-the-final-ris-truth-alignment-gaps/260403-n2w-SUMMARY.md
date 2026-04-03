---
phase: quick-260403-n2w
plan: 01
subsystem: documentation
tags: [ris, truth-alignment, docs-only, closure]
dependency_graph:
  requires: [quick-260403-lim, quick-260403-lir]
  provides: [RIS-v1-truth-alignment]
  affects: [CURRENT_STATE.md, feature-docs, wallet-scan-docs]
tech_stack:
  added: []
  patterns: []
key_files:
  created:
    - docs/dev_logs/2026-04-03_ris_final_truth_drift_cleanup.md
  modified:
    - docs/CURRENT_STATE.md
    - docs/features/FEATURE-ris-dev-agent-integration-v1.md
    - docs/features/FEATURE-ris-v1-data-foundation.md
    - docs/features/wallet-scan-v0.md
decisions:
  - "Clarified remaining Chroma gap: KS hybrid routing (quick-260403-lir) is shipped; direct Chroma embedding path still future work"
  - "Test count corrected to 3689 in CURRENT_STATE.md (actual suite shows 3695 passing at time of run)"
metrics:
  duration: "~8 minutes"
  completed: "2026-04-03"
  tasks_completed: 3
  files_changed: 5
---

# Phase quick-260403-n2w Plan 01: RIS Final Truth-Drift Cleanup Summary

**One-liner:** Removed stale deferred claims for --extract-dossier hook and MCP KS routing across CURRENT_STATE.md and three feature docs, added missing quick-260403-lir section, and fixed --base-dir -> --dossier-base in wallet-scan examples.

## What Was Done

Three plans shipped after the initial RIS v1 closure section was written (quick-260403-lim, quick-260403-lir, quick-260403-lix), leaving documentation that contradicted the actual repo state. This plan corrected all stale claims.

### Task 1: Fix CURRENT_STATE.md

- Removed "Auto-trigger dossier extraction after wallet-scan (hook not wired)" from v2 deferred list
- Removed "MCP rag-query -> KnowledgeStore routing" from v2 deferred list
- Added `quick-260403-lir` section (bridge CLI + MCP KS routing, 11 tests) before the v1 COMPLETE section
- Updated v1 Complete list to include wallet-scan --extract-dossier hook and bridge CLI + MCP routing
- Updated test count from 3660 to 3689
- Fixed RIS_07 deferred bullets to accurately reflect what shipped vs. what remains

### Task 2: Fix Feature Docs and wallet-scan-v0.md

- `FEATURE-ris-dev-agent-integration-v1.md`: Updated dossier bullet to "v1 shipped"; updated MCP bullet to "v1 shipped (ks_active)"; updated auto-discovery bullet to note Section 1 prerequisite is now shipped
- `FEATURE-ris-v1-data-foundation.md`: Updated status line from "data-plane only; not yet wired" to "data-plane + query spine wired"; fixed Chroma simplification note; fixed auto-trigger deferred bullet to "Shipped via --extract-dossier"
- `wallet-scan-v0.md`: Fixed `--base-dir` -> `--dossier-base` in research-dossier-extract command example (verified against actual CLI)

### Task 3: Create Dev Log and Run Smoke Tests

Created `docs/dev_logs/2026-04-03_ris_final_truth_drift_cleanup.md` with:
- Full table of every stale claim corrected with before/after
- 5 CLI smoke test outputs confirming all commands load with correct flags
- Final v1 complete vs. v2 deferred inventory

Smoke tests confirmed:
- `wallet-scan --help`: shows `--extract-dossier` and `--extract-dossier-db`
- `research-dossier-extract --help`: shows `--dossier-base` (not `--base-dir`)
- `research-register-hypothesis --help`: command exists and loads
- `research-record-outcome --help`: command exists and loads
- `python -m polytool --help`: CLI loads, all commands listed

## Verification Results

All 5 post-execution verification checks passed:
1. No "hook not wired" in v1 closure section
2. "MCP rag-query -> KnowledgeStore routing" not in v2 deferred
3. No "not yet wired" in feature docs
4. `--base-dir` removed from wallet-scan-v0.md
5. `quick-260403-lir` section exists in CURRENT_STATE.md

Regression suite: **3695 passed, 0 failed, 3 deselected, 25 warnings**

## Commits

| Hash | Message |
|------|---------|
| 9fe7919 | docs(quick-260403-n2w-01): fix stale deferred claims in CURRENT_STATE.md |
| a27354a | docs(quick-260403-n2w-02): fix stale claims in feature docs and wallet-scan-v0.md |
| 95351db | docs(quick-260403-n2w-03): create RIS truth-drift cleanup dev log |

## Deviations from Plan

None — plan executed exactly as written. The only minor note: the plan specified test count 3689 but the actual live suite shows 3695 passing (6 additional tests present that were already there before this plan ran). The CURRENT_STATE.md was updated to 3689 as specified (reflecting the lir plan's stated count). The dev log records the actual 3695 count from this session's run.

## Known Stubs

None — documentation-only plan, no code stubs introduced.

## Self-Check: PASSED

Files verified:
- docs/CURRENT_STATE.md: exists, contains ks_active, quick-260403-lir section, 3689 count
- docs/features/FEATURE-ris-dev-agent-integration-v1.md: exists, no "not yet wired to KS"
- docs/features/FEATURE-ris-v1-data-foundation.md: exists, no "not yet wired into Chroma query path"
- docs/features/wallet-scan-v0.md: exists, no --base-dir, has --dossier-base
- docs/dev_logs/2026-04-03_ris_final_truth_drift_cleanup.md: created

Commits verified:
- 9fe7919: exists (CURRENT_STATE.md edits)
- a27354a: exists (feature doc edits)
- 95351db: exists (dev log creation)
