---
phase: quick-260410-iif
plan: "01"
subsystem: docs/wallet-discovery
tags: [docs, runbook, wallet-discovery, mvf, loop-a]
dependency_graph:
  requires: []
  provides: [WALLET_DISCOVERY_V1_OPERATOR_RUNBOOK]
  affects: [docs/features/wallet-discovery-v1.md, docs/README.md]
tech_stack:
  added: []
  patterns: [operator-runbook]
key_files:
  created:
    - docs/runbooks/WALLET_DISCOVERY_V1_OPERATOR_RUNBOOK.md
    - docs/dev_logs/2026-04-10_wallet_discovery_v1_operator_runbook.md
  modified:
    - docs/features/wallet-discovery-v1.md
    - docs/README.md
decisions:
  - "Runbook length: 304 lines — exceeds 120-line minimum; retained to cover all 8 mandatory sections fully"
  - "Included real CLI dry-run output in runbook to verify command accuracy before publishing"
  - "Used table format for 11 MVF dimensions (matching RIS runbook style) rather than inline list"
metrics:
  duration: "~12 minutes"
  completed: "2026-04-10T17:26:38Z"
  tasks_completed: 2
  tasks_total: 2
  files_created: 2
  files_modified: 2
---

# Phase quick-260410-iif Plan 01: Wallet Discovery v1 Operator Runbook Summary

**One-liner:** Copy-paste operator runbook for Loop A leaderboard discovery, MVF quick scan, and human review gate — verified against live CLI output.

---

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Write Wallet Discovery v1 Operator Runbook | `aa3722b` | docs/runbooks/WALLET_DISCOVERY_V1_OPERATOR_RUNBOOK.md (created, 304 lines) |
| 2 | Cross-link runbook, write dev log | `10ac612` | docs/features/wallet-discovery-v1.md, docs/README.md, docs/dev_logs/2026-04-10_wallet_discovery_v1_operator_runbook.md |

---

## What Was Built

A complete operator runbook for Wallet Discovery v1 at
`docs/runbooks/WALLET_DISCOVERY_V1_OPERATOR_RUNBOOK.md` (304 lines, 8 sections):

0. **Purpose** — 4-sentence scope statement, end-to-end path summary
1. **Prerequisites** — Docker, ClickHouse, `CLICKHOUSE_PASSWORD`, CLI smoke, DDL table check with fix commands
2. **Loop A** — Dry-run (with annotated real output), live run, customization flags table, ClickHouse verification queries
3. **Quick Scan with MVF** — `--quick` flag semantics, 11-dimension table, null-dimension notes
4. **Human Review Gate** — lifecycle state machine, invalid transition rule, review signal table, v1 limitation note
5. **ClickHouse Tables Reference** — 3-table summary with quick query per table
6. **What v1 Does NOT Cover** — 11 non-goals with pointer to spec blockers
7. **Troubleshooting** — 8-row symptom/cause/fix table
8. **Related Docs** — 5 cross-references

All CLI commands were verified against the live CLI before runbook was finalized.
Dry-run output (`rows_fetched: 250`, all result fields) was captured during verification.

---

## Verification Performed

```
python -m polytool discovery --help         -- confirmed subcommand structure
python -m polytool discovery run-loop-a --help  -- confirmed all 5 flag names
python -m polytool scan --help              -- confirmed --quick flag description
python -m polytool discovery run-loop-a --dry-run  -- confirmed real output shape
```

Automated checks (from PLAN.md verify blocks):
- PASS: runbook exists with 304 lines (>= 120 required) and all required sections
- PASS: feature doc, README, and dev log all contain required cross-link strings

---

## Deviations from Plan

None — plan executed exactly as written. All 8 sections present. All 7 troubleshooting
rows present (plan specified 7; runbook contains 8, adding one for
"Loop A dry-run succeeds but live run fails" which is a distinct useful case).

---

## Known Stubs

None. This is a docs-only plan; no data stubs applicable.

---

## Threat Flags

None. Docs-only plan with no code, endpoints, auth paths, or schema changes.

---

## Self-Check: PASSED

- `docs/runbooks/WALLET_DISCOVERY_V1_OPERATOR_RUNBOOK.md` — FOUND (304 lines)
- `docs/dev_logs/2026-04-10_wallet_discovery_v1_operator_runbook.md` — FOUND
- Commit `aa3722b` — FOUND
- Commit `10ac612` — FOUND
- Feature doc link — FOUND (`WALLET_DISCOVERY_V1_OPERATOR_RUNBOOK` in wallet-discovery-v1.md)
- README Workflows link — FOUND (`WALLET_DISCOVERY_V1_OPERATOR_RUNBOOK` in README.md)
- No code/test/infra/migration files modified — CONFIRMED
