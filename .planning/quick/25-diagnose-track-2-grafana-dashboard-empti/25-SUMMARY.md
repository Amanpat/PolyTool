---
phase: quick-025
plan: 01
subsystem: track2-grafana
tags: [grafana, clickhouse, diagnostics, operator-ux, track2]
dependency_graph:
  requires: [crypto_pair_events_schema, grafana_provisioning]
  provides: [grafana_no_data_guidance, operator_remediation_doc]
  affects: [docs/features/FEATURE-crypto-pair-grafana-panels-v1.md, infra/grafana/dashboards/polyttool_crypto_pair_paper_soak.json]
tech_stack:
  added: []
  patterns: [grafana_noDataText, clickhouse_http_diagnostic]
key_files:
  created:
    - docs/dev_logs/2026-03-25_phase1a_grafana_no_data_diagnostics.md
  modified:
    - infra/grafana/dashboards/polyttool_crypto_pair_paper_soak.json
    - docs/features/FEATURE-crypto-pair-grafana-panels-v1.md
decisions:
  - "noDataText placed inside existing options blocks on all 12 panels — no panel restructuring required"
  - "Root cause confirmed as zero rows: infrastructure chain is intact and correctly provisioned"
  - "Feature doc appended with operator guide section rather than modifying existing content"
metrics:
  duration: "~15 minutes"
  completed: "2026-03-25"
  tasks_completed: 3
  tasks_total: 3
  files_created: 1
  files_modified: 2
---

# Quick-025: Diagnose Track 2 Grafana Dashboard Emptiness — Summary

**One-liner:** Confirmed zero-row root cause via live ClickHouse diagnostic, added `noDataText` to all 12 dashboard panels, and appended operator remediation checklist to feature doc.

---

## What Was Done

### Task 1 — ClickHouse Diagnostic and Dev Log

Ran live HTTP diagnostics against ClickHouse as `grafana_ro`:

- `SELECT 1` returned `1` — service reachable.
- `system.tables` query returned `crypto_pair_events` — table exists.
- `count()` returned `0` — zero rows confirmed.
- `GROUP BY run_id, event_type` returned empty — no partial data from any run.

Dev log written at `docs/dev_logs/2026-03-25_phase1a_grafana_no_data_diagnostics.md` with:
- Infrastructure PASS/FAIL findings for all 6 chain components
- Root cause verdict (zero rows, not broken infrastructure)
- Soak history table (quick-022/023/024) explaining why no rows landed
- Step-by-step path to live data (market watcher → paper run with `--sink-enabled` → verify manifest)

### Task 2 — noDataText Added to All 12 Dashboard Panels

Added `"noDataText": "No Track 2 events yet. Causes: (1) sink disabled — rerun with --sink-enabled, (2) no eligible BTC/ETH/SOL 5m-15m markets — run crypto-pair-watch --watch, (3) Docker not running. Table: polytool.crypto_pair_events"` to the `options` block of every panel.

Panel coverage by type:
- Table panels (ids 1, 2, 3, 4, 5, 8, 12) — 7 panels
- Timeseries panels (ids 7, 9, 10, 11) — 4 panels
- Barchart panel (id 6) — 1 panel

JSON validated with `python -c "import json; json.load(...)"` — parse clean.

### Task 3 — Feature Doc Operator Guide

Appended `## No-Data Operator Guide` section to `docs/features/FEATURE-crypto-pair-grafana-panels-v1.md` with:
- 5-step checklist (Docker health, table row count, sink condition explanation, market-wait + resoak commands, time range note)
- Zero existing content modified

---

## Root Cause Verdict

The dashboard is empty because `polytool.crypto_pair_events` contains zero rows.
The infrastructure provisioning chain is fully intact:
- ClickHouse HTTP reachable as `grafana_ro`
- Table exists with correct schema and SELECT grant
- Datasource UID `clickhouse-polytool` matches provisioning config
- Dashboard file auto-provisioned via bind mount with 30s reload

The primary blocker remains market availability: Polymarket has no active BTC/ETH/SOL 5m/15m binary pair markets as of 2026-03-25.

---

## Deviations from Plan

None — plan executed exactly as written.

---

## Commits

| Task | Commit | Message |
|------|--------|---------|
| 1 | 3b40778 | docs(quick-025): add Grafana no-data diagnostics dev log |
| 2 | 1673688 | feat(quick-025): add noDataText to all 12 Grafana dashboard panels |
| 3 | ff31016 | docs(quick-025): add No-Data Operator Guide to Grafana feature doc |

---

## Self-Check

### Files Exist

- `docs/dev_logs/2026-03-25_phase1a_grafana_no_data_diagnostics.md` — FOUND
- `infra/grafana/dashboards/polyttool_crypto_pair_paper_soak.json` — FOUND (modified)
- `docs/features/FEATURE-crypto-pair-grafana-panels-v1.md` — FOUND (modified)

### Commits Exist

- 3b40778 — FOUND
- 1673688 — FOUND
- ff31016 — FOUND

### JSON Validation

All 12 panels have `noDataText`. JSON parses cleanly.

## Self-Check: PASSED
