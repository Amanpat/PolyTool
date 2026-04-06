---
phase: quick-260406-nb7
plan: 01
subsystem: docs
tags: [n8n, mcp, ris, docs, contradiction-fix]
dependency_graph:
  requires: [quick-260406-le7]
  provides: [clean-ris-n8n-docs]
  affects: [docs/CURRENT_STATE.md, docs/adr/0013-ris-n8n-pilot-scoped.md, docs/RIS_OPERATOR_GUIDE.md, docs/RIS_AUDIT_REPORT.md]
tech_stack:
  added: []
  patterns: []
key_files:
  created:
    - docs/dev_logs/2026-04-06_ris_n8n_mcp_truth_fix.md
  modified:
    - docs/CURRENT_STATE.md
    - docs/adr/0013-ris-n8n-pilot-scoped.md
    - docs/RIS_OPERATOR_GUIDE.md
    - docs/RIS_AUDIT_REPORT.md
decisions:
  - "n8n instance-level MCP works on community edition >= 2.14.2 (not Enterprise-only)"
  - "N8N_MCP_BEARER_TOKEN is operative (not informational)"
  - "research-scheduler has exactly three subcommands: status, start, run-job"
metrics:
  duration: ~10min
  completed: 2026-04-06
---

# Phase quick-260406-nb7 Plan 01: Eliminate Remaining RIS n8n Documentation Contradictions -- Summary

Removed five stale claims from four operator-facing docs using n8n MCP POST probe results (quick-260406-le7) as authoritative truth: replaced "Enterprise-only" and "informational placeholder" language with correct community edition facts, fixed internal RIS_OPERATOR_GUIDE contradiction on bearer token, and corrected scheduler CLI table from four fictional subcommands to three real ones.

## Tasks Completed

| # | Task | Commit | Files Changed |
|---|------|--------|---------------|
| 1 | Fix MCP and CLI contradictions in all four docs | 563cfa0 | docs/CURRENT_STATE.md, docs/adr/0013-ris-n8n-pilot-scoped.md, docs/RIS_OPERATOR_GUIDE.md, docs/RIS_AUDIT_REPORT.md |
| 2 | Create dev log for this doc fix session | 2e6c4b6 | docs/dev_logs/2026-04-06_ris_n8n_mcp_truth_fix.md |

## Verification Results

All success criteria satisfied:

- "Enterprise feature only": 0 matches across all four docs
- "informational placeholder": 0 matches across CURRENT_STATE.md and ADR 0013
- "not operative": 0 matches in RIS_OPERATOR_GUIDE.md
- "start, stop, status, list": 0 matches in RIS_AUDIT_REPORT.md
- "community edition": 3 matches in CURRENT_STATE.md, 1 match in ADR 0013
- "start, status, run-job": 1 match in RIS_AUDIT_REPORT.md
- Dev log exists at docs/dev_logs/2026-04-06_ris_n8n_mcp_truth_fix.md
- No code, workflow JSON, docker-compose, scripts/, or .claude/** files were modified

## Changes Made

### docs/CURRENT_STATE.md

- Replaced "Enterprise tier for backend endpoint" with "works on community edition; requires JWT bearer token from n8n Settings UI"
- Replaced three-line "Enterprise feature only / informational placeholder" block with corrected MCP probe truth including SPA catch-all explanation
- Added new "n8n Instance MCP Connection Debug (quick-260406-le7, 2026-04-06)" section documenting the root cause and findings

### docs/adr/0013-ris-n8n-pilot-scoped.md

- Replaced "Enterprise feature -- not available in the community edition" + "informational" paragraph with corrected finding: community edition >= 2.14.2, JWT bearer token, SPA catch-all explanation, and link to probe evidence

### docs/RIS_OPERATOR_GUIDE.md

- Fixed step 1 bearer token from "not operative -- MCP uses stdio, not HTTP" to "operative when instance-level MCP is enabled in n8n Settings UI" -- resolving the internal contradiction with the later MCP section (lines 627+)

### docs/RIS_AUDIT_REPORT.md

- Fixed scheduler CLI table: "start, stop, status, list subcommands" -> "start, status, run-job subcommands" to match actual CLI parser (tools/cli/research_scheduler.py)

## Deviations from Plan

None -- plan executed exactly as written.

## Known Stubs

None.

## Threat Flags

None. Docs-only change; no new network endpoints, auth paths, file access patterns, or schema changes.

## Self-Check: PASSED

- docs/CURRENT_STATE.md: exists and contains "community edition" (3 hits)
- docs/adr/0013-ris-n8n-pilot-scoped.md: exists and contains "community edition" (1 hit)
- docs/RIS_OPERATOR_GUIDE.md: exists and does not contain "not operative" (0 hits)
- docs/RIS_AUDIT_REPORT.md: exists and contains "start, status, run-job" (1 hit)
- docs/dev_logs/2026-04-06_ris_n8n_mcp_truth_fix.md: exists
- Commit 563cfa0: task 1 changes
- Commit 2e6c4b6: task 2 dev log
