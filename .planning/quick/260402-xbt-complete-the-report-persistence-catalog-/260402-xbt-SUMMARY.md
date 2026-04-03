---
phase: quick
plan: 260402-xbt
subsystem: research-intelligence
tags: [ris, report-persistence, catalog, digest, cli, jsonl]
dependency_graph:
  requires:
    - packages/research/synthesis/precheck_ledger.py
    - packages/research/evaluation/artifacts.py
  provides:
    - packages/research/synthesis/report_ledger.py
    - tools/cli/research_report.py
  affects:
    - packages/research/synthesis/__init__.py
    - polytool/__main__.py
tech_stack:
  added: []
  patterns:
    - append-only JSONL index (same as precheck_ledger pattern)
    - dataclass-based report entry
    - argparse subcommand CLI with --json output
key_files:
  created:
    - packages/research/synthesis/report_ledger.py
    - tools/cli/research_report.py
    - tests/test_ris_report_catalog.py
    - docs/features/FEATURE-ris-report-persistence.md
    - docs/dev_logs/2026-04-02_ris_r3_report_storage_and_catalog.md
  modified:
    - packages/research/synthesis/__init__.py
    - polytool/__main__.py
    - docs/CURRENT_STATE.md
decisions:
  - "JSONL local-first for report index; ClickHouse indexing deferred (low volume, no cross-report analytics needed yet)"
  - "Reports excluded from RAG indexing to prevent circular evidence injection"
  - "Digest is manual-trigger only; APScheduler automation deferred to RIS_06"
metrics:
  duration: "~30 minutes"
  completed: "2026-04-02"
  tasks_completed: 3
  tasks_total: 3
  tests_added: 21
  tests_total: 3334
  files_created: 5
  files_modified: 3
---

# Phase quick Plan 260402-xbt: RIS Report Persistence and Catalog Summary

**One-liner:** Local-first JSONL report catalog with persist/list/search/digest CLI for RIS synthesis artifacts.

---

## What Was Built

Complete report persistence and catalog layer for the RIS synthesis engine:

- `packages/research/synthesis/report_ledger.py` — Core library with `ReportEntry` dataclass, `persist_report`, `list_reports`, `search_reports`, `generate_digest`. Follows the same append-only JSONL pattern as `precheck_ledger.py`.

- `tools/cli/research_report.py` — CLI entrypoint with four subcommands:
  - `save` — persist a markdown report from `--body`, `--body-file`, or stdin
  - `list` — list past reports with `--window` filter (7d / 30d / Nh / all)
  - `search` — case-insensitive keyword search across title, summary, tags
  - `digest` — aggregate precheck runs + eval artifacts into a weekly summary

- Report artifacts stored at `artifacts/research/reports/{YYYY-MM-DD}_{report_id}.md` with a JSONL index at `artifacts/research/reports/report_index.jsonl`.

- 21 deterministic offline tests covering all paths. 3334 total suite passes, 0 regressions.

---

## Tasks Completed

| Task | Name | Commit | Key Files |
|------|------|--------|-----------|
| 1 | Report ledger library and CLI entrypoint | 056ba37 | report_ledger.py, research_report.py, __main__.py |
| 2 | Deterministic tests | b37e476 | tests/test_ris_report_catalog.py |
| 3 | Documentation and state updates | 04a5e33 | FEATURE doc, dev log, CURRENT_STATE.md |

---

## Deviations from Plan

None — plan executed exactly as written.

---

## Decisions Made

1. **JSONL local-first index** — Report volume for RIS is low (tens to hundreds per week). JSONL append-only index matches existing `precheck_ledger.py` pattern and avoids ClickHouse dependency. Escalation trigger documented in feature doc.

2. **Reports excluded from RAG** — Reports summarize knowledge store content; feeding them back as sources would create circular evidence injection. Reports live under `artifacts/` (gitignored), not `kb/`.

3. **Digest is manual-only** — APScheduler/n8n scheduling deferred to RIS_06 as explicitly planned. No scheduler integration added.

---

## Known Stubs

None — all functions are fully wired and functional. No placeholder data.

---

## RIS_05 Completion vs Deferred

| Component | Status |
|-----------|--------|
| Report persistence (persist_report, list/search) | Complete |
| Weekly digest generation | Complete |
| CLI: save/list/search/digest | Complete |
| Query planner | Separate work item |
| Synthesis engine content generation | Separate work item |
| ClickHouse report indexing | Deferred (RIS_06+) |
| Automated digest scheduling | Deferred (RIS_06) |

## Self-Check: PASSED

Files verified:
- packages/research/synthesis/report_ledger.py: FOUND
- tools/cli/research_report.py: FOUND
- tests/test_ris_report_catalog.py: FOUND
- docs/features/FEATURE-ris-report-persistence.md: FOUND
- docs/dev_logs/2026-04-02_ris_r3_report_storage_and_catalog.md: FOUND

Commits verified:
- 056ba37: FOUND
- b37e476: FOUND
- 04a5e33: FOUND
