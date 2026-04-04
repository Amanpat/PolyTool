---
phase: quick-260404-jgk
plan: 01
subsystem: RIS
tags: [audit, documentation, ris, research-intelligence-system]
dependency_graph:
  requires: []
  provides: [RIS_AUDIT_REPORT, RIS_OPERATOR_GUIDE, ris-audit-dev-log]
  affects: [docs]
tech_stack:
  added: []
  patterns: [read-only-audit, offline-inspection]
key_files:
  created:
    - docs/RIS_AUDIT_REPORT.md
    - docs/RIS_OPERATOR_GUIDE.md
    - docs/dev_logs/2026-04-04_ris-audit.md
  modified: []
decisions:
  - "Dedup threshold operative value is 0.85 (code) not 0.92 (older feature docs)"
  - "KnowledgeStore is SQLite-backed; Chroma is the separate vector index only"
  - "Cloud LLM providers raise ValueError — v2 deliverables, not partial implementations"
  - "Discord alert sink not wired to existing discord.py — uses LogSink/WebhookSink protocol"
metrics:
  duration: ~45 minutes (resumed from prior context)
  completed: 2026-04-04
  tasks_completed: 3
  tasks_total: 3
  files_created: 3
  files_modified: 0
---

# Phase quick-260404-jgk Plan 01: RIS Implementation Audit and Operator Guide Summary

## One-liner

Read-only codebase audit of RIS v1 across all 5 layers producing 491-line audit report, 506-line operator guide, and 169-line dev log with honest IMPLEMENTED/PARTIAL/PLANNED verdicts.

## What Was Done

Systematically inspected ~75 source files across all RIS layers (Ingestion, Evaluation Gate, Knowledge Store, Synthesis, Infrastructure) plus all 14 research-* CLI commands. Produced three documentation artifacts capturing the ground-truth state of the system.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Write RIS_AUDIT_REPORT.md | 59f593d | docs/RIS_AUDIT_REPORT.md (491 lines) |
| 2 | Write RIS_OPERATOR_GUIDE.md | 3ad08f2 | docs/RIS_OPERATOR_GUIDE.md (506 lines) |
| 3 | Write dev log | f1873b6 | docs/dev_logs/2026-04-04_ris-audit.md (169 lines) |

## Key Findings (audit results)

**RIS v1 overall maturity: ~80% implemented.**

All 14 research-* CLI commands exist and work. The ingestion pipeline, evaluation gate (with ManualProvider), knowledge store (SQLite + Chroma), precheck (GO/CAUTION/STOP), and report synthesizer are all functional and confirmed live.

**What is absent:**
- Twitter/X: zero code (no adapter, no fetcher, not scheduled)
- Cloud LLM providers: Gemini, DeepSeek, OpenAI, Anthropic raise ValueError — v2
- LLM-based report synthesis: DeepSeek V3 is v2 deliverable
- Grafana RIS panels: none exist
- ClickHouse RIS tables: none exist
- Discord alert integration: WebhookSink/LogSink protocol not wired to discord.py

**Spec vs implementation discrepancies found:**
- Dedup threshold: spec says 0.92, code uses 0.85
- Knowledge store: spec implied Chroma; actual is SQLite (Chroma is separate vector index)
- Claim extractor: implied LLM; actual is fully heuristic (EXTRACTOR_ID="heuristic_v1")
- SSRN: listed as adapter; no SSRN fetcher exists (arXiv only)

**Test count:** 1,272 RIS-related tests collected (34% of 3,698 total test suite).

## Deviations from Plan

None — plan executed exactly as written. Read-only audit, no source code modified.

## Known Stubs

No stubs in produced documentation. All features described as working have been verified against source code. All unimplemented features are labeled [PLANNED] in both documents.

## Threat Flags

None — documentation-only task. No network endpoints, auth paths, file access patterns, or schema changes introduced.

## Self-Check

### Files created exist:
- docs/RIS_AUDIT_REPORT.md: 491 lines (PASS >= 200)
- docs/RIS_OPERATOR_GUIDE.md: 506 lines (PASS >= 100)
- docs/dev_logs/2026-04-04_ris-audit.md: 169 lines (PASS >= 30)

### Commits exist:
- 59f593d: feat(quick-260404-jgk): write RIS_AUDIT_REPORT.md
- 3ad08f2: feat(quick-260404-jgk): write RIS_OPERATOR_GUIDE.md
- f1873b6: feat(quick-260404-jgk): write dev log for RIS implementation audit

## Self-Check: PASSED
