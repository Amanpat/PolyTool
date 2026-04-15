---
phase: quick-260415-pqc
plan: 01
subsystem: docs
tags: [track-2, crypto-pair, operator-runbook, paper-soak, gate-2]
dependency_graph:
  requires: [docs/dev_logs/2026-04-15_gate2_decision_packet.md]
  provides: [docs/runbooks/TRACK2_OPERATOR_RUNBOOK.md]
  affects: []
tech_stack:
  added: []
  patterns: [copy-paste-ready runbook, bash+powershell dual variants, safety checklist]
key_files:
  created:
    - docs/runbooks/TRACK2_OPERATOR_RUNBOOK.md
    - docs/dev_logs/2026-04-15_track2_operator_runbook.md
  modified: []
decisions:
  - "Default reference-feed-provider is binance per --help but runbook recommends coinbase due to geo-restriction (quick-022/023)"
  - "Runbook does not cover live deployment path -- deferred pending paper soak promote verdict"
metrics:
  duration: "~20 minutes"
  completed: "2026-04-15"
  tasks_completed: 2
  tasks_total: 2
  files_created: 2
  files_modified: 0
---

# Phase quick-260415-pqc Plan 01: Track 2 Operator Runbook Summary

**One-liner:** Track 2 operator runbook (354 lines) covering full paper-soak lifecycle with copy-paste commands, safety checklist, kill switch, and explicit Gate 2 relationship statement.

---

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Create Track 2 operator runbook | bee9ce5 | docs/runbooks/TRACK2_OPERATOR_RUNBOOK.md (created) |
| 2 | Create dev log and run smoke verification | db41b5d | docs/dev_logs/2026-04-15_track2_operator_runbook.md (created) |

---

## What Was Built

`docs/runbooks/TRACK2_OPERATOR_RUNBOOK.md` (354 lines) -- the single operator-facing
entry point for running the Track 2 crypto pair bot from market check through paper soak
verdict. Ten sections:

1. What Track 2 Is (and Is Not) -- Gate 2 relationship, strategy summary, decision context
2. Prerequisites / Environment Checks -- CLI, Docker, ClickHouse, credential handling
3. Step 1: Check Market Availability -- `crypto-pair-watch` one-shot and poll mode
4. Step 2: Dry-Run Scan -- `crypto-pair-scan` with flag explanations
5. Step 3: Paper Soak (24h) -- full launch command (bash + PowerShell), flag table, artifact locations
6. Safety Checklist -- 8 concrete pass/fail criteria
7. Stop Conditions / Kill Switch -- when/how to stop, bash and PowerShell variants
8. What Success Looks Like -- promote band metrics table
9. Troubleshooting -- 7 known failure modes with exact resolution steps
10. Reference Links -- cross-references to rubric spec, decision packet, feature docs

All CLI commands verified against actual `--help` output before writing.

---

## Verification

All must-haves confirmed:

- [x] `docs/runbooks/TRACK2_OPERATOR_RUNBOOK.md` exists, 354 lines (min 150)
- [x] `docs/dev_logs/2026-04-15_track2_operator_runbook.md` exists with smoke verification outputs
- [x] Cross-reference to `CRYPTO_PAIR_PAPER_SOAK_RUNBOOK.md` present in runbook
- [x] Cross-reference to `SPEC-crypto-pair-paper-soak-rubric-v0.md` present in runbook
- [x] Gate 2 relationship explicitly stated: FAILED (7/50 = 14%), deprioritized not abandoned
- [x] No Gate 2 thresholds, benchmark manifests, or policy documents modified
- [x] All 4 CLI commands verified: `crypto-pair-watch`, `crypto-pair-scan`, `crypto-pair-run`, `crypto-pair-report`
- [x] Both bash and PowerShell variants provided for kill switch and paper soak launch
- [x] Safety checklist has 8 concrete binary pass/fail criteria

---

## Deviations from Plan

### Auto-fixed Issues

None.

### Notes

**Flag default observation:** `--reference-feed-provider` default in `--help` is `binance`,
not `coinbase`. The runbook correctly recommends using `coinbase` explicitly for paper soaks
due to geo-restriction findings (quick-022/023). Both the default and the recommended override
are documented accurately.

---

## Known Stubs

None. The runbook is documentation only; no data sources are stubbed.

---

## Threat Surface Scan

No new network endpoints, auth paths, file access patterns, or schema changes introduced.
All commands in the runbook operate in paper mode (read-only). Threat model items addressed:

- T-pqc-01: Commands are paper-mode only. CLICKHOUSE_PASSWORD sourced from env, not hardcoded.
  Credential section explicitly states fail-fast behavior and never-hardcode rule.
- T-pqc-02: `--live` flag absence explicitly called out in three places in the runbook.

---

## Self-Check: PASSED

- docs/runbooks/TRACK2_OPERATOR_RUNBOOK.md: FOUND
- docs/dev_logs/2026-04-15_track2_operator_runbook.md: FOUND
- Commit bee9ce5: FOUND
- Commit db41b5d: FOUND
- No shared truth files (CLAUDE.md, CURRENT_STATE.md, STATE.md) modified: CONFIRMED
- No Gate 2 thresholds or benchmark manifests modified: CONFIRMED
