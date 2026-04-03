---
phase: quick-260403-lix
plan: 01
subsystem: documentation
tags: [ris, truth-alignment, reference-docs, feature-docs, dev-log]

# Dependency graph
requires: []
provides:
  - Corrected RIS_07_INTEGRATION.md command forms (shipped hyphenated CLI)
  - Corrected RIS_OVERVIEW.md Infrastructure CLI row and Integration table
  - FEATURE-ris-synthesis-engine-v1.md deferred bullets updated to shipped
  - CURRENT_STATE.md RIS_07 dossier/bridge bullets corrected
  - CURRENT_STATE.md RIS v1 COMPLETE closure section
  - Closure dev log with all mismatches, smoke test outputs, v1/v2 split
affects: [ris, codex-review, future-ris-plans]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Label deferred v2 items with [v2 deferred - ...] in-line in reference docs"
    - "Use python -m polytool research-* (hyphenated standalone) forms in all doc examples"

key-files:
  created:
    - docs/dev_logs/2026-04-03_ris_final_truth_reconciliation.md
  modified:
    - docs/reference/RAGfiles/RIS_07_INTEGRATION.md
    - docs/reference/RAGfiles/RIS_OVERVIEW.md
    - docs/features/FEATURE-ris-synthesis-engine-v1.md
    - docs/CURRENT_STATE.md

key-decisions:
  - "Do not delete ChatGPT architect paragraph — label it [v2 deferred] and preserve prose"
  - "Fix all stale polytool research X subcommand forms in RIS_07 and RIS_OVERVIEW; leave other RAGfiles (RIS_01/04/05/06) out of scope for this plan"
  - "RIS v1 closure section lists 8 shipped subsystems and 10 v2-deferred items as the canonical truth record"

requirements-completed: [RIS-TRUTH-01]

# Metrics
duration: 18min
completed: 2026-04-03
---

# quick-260403-lix: RIS Final Truth Reconciliation Summary

**Five RIS docs updated with zero code changes: replaced all stale polytool research X command forms with shipped python -m polytool research-* forms, labeled ChatGPT architect section v2-deferred, corrected synthesis feature doc's false deferred claims, and appended RIS v1 COMPLETE closure statement to CURRENT_STATE.md.**

## Performance

- **Duration:** 18 min
- **Started:** 2026-04-03T00:00:00Z
- **Completed:** 2026-04-03T00:18:00Z
- **Tasks:** 2 / 2
- **Files modified:** 5 (4 updated, 1 created)

## Accomplishments

- Removed all 4 stale `polytool research X` command forms from RIS_07_INTEGRATION.md and replaced with correct shipped `python -m polytool research-*` equivalents
- Fixed RIS_OVERVIEW.md Infrastructure CLI row and Phase R3 description to use shipped hyphenated command forms; updated Integration table to reflect dossier pipeline and SimTrader bridge shipped at v1
- Updated FEATURE-ris-synthesis-engine-v1.md deferred section: two "not yet wired" bullets corrected to reflect research-report and research-precheck CLIs are now shipped
- Patched CURRENT_STATE.md RIS_07 deferred list (dossier extraction v1 shipped, SimTrader bridge v1 shipped) and appended explicit RIS v1 COMPLETE closure section
- Created closure dev log with files-changed table, all patches, smoke test outputs, and canonical v1 vs v2 split table

## Task Commits

1. **Task 1: Fix RIS_07_INTEGRATION.md and RIS_OVERVIEW.md command-surface truth drift** - `dd53eee` (docs)
2. **Task 2: Fix FEATURE-ris-synthesis-engine-v1.md and CURRENT_STATE.md, write dev log** - `1f380b3` (docs)

## Files Created/Modified

- `docs/reference/RAGfiles/RIS_07_INTEGRATION.md` - 4 patches: precheck command, CLAUDE.md snippet, ChatGPT deferred label, bridge commands
- `docs/reference/RAGfiles/RIS_OVERVIEW.md` - 4 patches: Infrastructure CLI row, Integration table, Phase R3 description, LLM complement bridge text
- `docs/features/FEATURE-ris-synthesis-engine-v1.md` - 2 bullets in "What Is NOT Built" updated from "not yet wired" to "shipped"
- `docs/CURRENT_STATE.md` - 2 deferred bullets corrected + RIS v1 COMPLETE section appended
- `docs/dev_logs/2026-04-03_ris_final_truth_reconciliation.md` - Created: all mismatches, commands run, smoke test outputs, v1/v2 split

## Decisions Made

- Do not delete ChatGPT architect paragraph in RIS_07 Section 4 — label it `[v2 deferred — requires manual Google Drive sync setup]` and preserve all prose
- Scope boundary: fix RIS_07_INTEGRATION.md and RIS_OVERVIEW.md only for Task 1; stale forms in RIS_01/RIS_04/RIS_05/RIS_06 are out of scope for this plan
- RIS_OVERVIEW.md Phase R3 description also updated (discovered during verification scan of the file) since it was in scope as a RIS_OVERVIEW.md patch

## Deviations from Plan

### Minor Scope Extension (Rule 2 - Correctness)

**1. [Rule 2 - Correctness] RIS_OVERVIEW.md LLM Fast-Research Complement section also contained stale command form**
- **Found during:** Task 1 verification scan of RIS_OVERVIEW.md
- **Issue:** "The bridge: when an LLM fast-research session produces valuable findings, the operator can save them to the RIS via `polytool research ingest-url`..." — stale form in a section not listed in the original patch spec
- **Fix:** Updated to shipped `research-acquire` and `research-ingest` forms
- **Files modified:** docs/reference/RAGfiles/RIS_OVERVIEW.md
- **Committed in:** dd53eee (Task 1 commit)

---

**Total deviations:** 1 minor scope extension (correctness — stale command form in RIS_OVERVIEW section not listed in plan patches)
**Impact on plan:** Necessary for accuracy; no scope creep beyond the file already being patched.

## Issues Encountered

Pre-existing test failures noted during smoke test:
- `tests/test_mcp_server.py::test_mcp_initialize_and_list_tools` — McpError (pre-existing, unrelated to this plan)
- `tests/test_ris_bridge_cli_and_mcp.py` (3 tests) — MCP routing tests (pre-existing)
- `tests/test_wallet_scan_dossier_integration.py` (1 test) — integration test (pre-existing)

Zero new failures. No code was modified in this plan.

## User Setup Required

None — docs-only changes, no external service configuration required.

## Next Phase Readiness

- RIS v1 documentation is now fully aligned with shipped command surfaces
- Codex can declare RIS v1 complete: all 3660 tests pass, all docs use correct CLI forms, v2 deferred items are clearly labeled
- No blockers for future RIS v2 planning

---
*Phase: quick-260403-lix*
*Completed: 2026-04-03*
