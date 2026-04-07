---
phase: quick-260407-ioi
plan: "01"
subsystem: docs
tags: [readme, documentation, operator-facing]
dependency_graph:
  requires: []
  provides: [root-readme-accuracy]
  affects: [operator-onboarding]
tech_stack:
  added: []
  patterns: []
key_files:
  created:
    - docs/dev_logs/2026-04-07_root_readme_refresh.md
  modified:
    - README.md
decisions:
  - "Gate 2 status documented as FAILED at 14% (not 'not passed yet' as old README stated)"
  - "Python version corrected to 3.10+ from 3.11+ (pyproject.toml source of truth)"
  - "Config file corrected to .env.example (polytool.example.yaml does not exist in repo)"
  - "Telegram section removed; Discord is the shipped alerting path"
  - "Alpha Factory removed; not a shipped feature name"
  - "SimTrader Studio guide removed from README; linked to docs/README_SIMTRADER.md instead"
  - "All 63 CLI commands in grouped tables matching --help output groupings exactly"
metrics:
  duration: "~15 minutes"
  completed: "2026-04-07"
  tasks_completed: 2
  files_modified: 2
---

# Phase quick-260407-ioi Plan 01: Root README Rewrite Summary

**One-liner:** Root README rewritten from scratch: stale gate status, Telegram alerts, Alpha Factory, and duplicate sections removed; 63 CLI commands in grouped tables; honest Gate 2 FAILED status; Python 3.10+ and .env.example corrected.

---

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Inventory CLI commands and create dev log | ce5f258 | docs/dev_logs/2026-04-07_root_readme_refresh.md |
| 2 | Rewrite README.md from scratch | c4a6728 | README.md |

---

## What Was Built

The old README (~900 lines, 1017 changed) was replaced with a clean 462-line operator reference.

**Sections in new README:**
1. Header and one-paragraph overview with explicit "What PolyTool is NOT"
2. What is shipped today (honest current state) with validation gate status table
3. Experimental / Gated section
4. Prerequisites (Python 3.10+, Docker Desktop, Git)
5. Installation with all optional dependency groups from pyproject.toml
6. Configuration (step-by-step: .env, docker compose, profiles, bootstrap, tests)
7. Quick workflows (research loop, single user, RAG, market scan, SimTrader, RIS, crypto pair)
8. Complete CLI command reference (63 commands in 8 grouped tables)
9. Operator surfaces (CLI, Grafana, Studio, MCP, n8n)
10. Project structure
11. Deeper documentation links
12. Security reminders
13. License

---

## Deviations from Plan

### Auto-fixed Issues

None.

### Documentation corrections (not plan deviations -- plan directed finding and fixing these)

**1. Python version requirement**
- Found during: Task 1 cross-reference
- Issue: Old README said Python 3.11+; pyproject.toml says >=3.10
- Fix: New README says Python 3.10+
- Files modified: README.md

**2. Config file name**
- Found during: Task 1 cross-reference
- Issue: Old README referenced `polytool.example.yaml` which does not exist in repo
- Fix: New README uses `.env.example` (the actual file)
- Files modified: README.md

**3. Gate 2 status wording**
- Found during: Task 1 cross-reference
- Issue: Old README said "Gate 2 not passed yet" (March 2026 framing); CURRENT_STATE.md records it as FAILED (14%) since 2026-03-29
- Fix: New README says Gate 2 FAILED at 7/50 tapes (14%), threshold is 70%
- Files modified: README.md

---

## Conflicts Found (documented in dev log)

All conflicts found between old README and governing docs were documented in `docs/dev_logs/2026-04-07_root_readme_refresh.md` and corrected in the new README. No silent choices made.

| Conflict | Governing truth |
|----------|----------------|
| Gate 2 "not passed yet" | FAILED 14% (CURRENT_STATE.md) |
| Gate 3 "90% complete" | BLOCKED behind Gate 2 |
| Python 3.11+ | >=3.10 (pyproject.toml) |
| Gate 1 "Open" (archive block) | PASSED |
| polytool.example.yaml | .env.example |

---

## Known Stubs

None. README is documentation only; no data-flow stubs apply.

---

## Threat Flags

None. Documentation-only change. No network endpoints, auth paths, or schema changes introduced.

---

## Test Results

`python -m pytest -q --tb=short`: **3695 passed, 3 deselected, 25 warnings** (no regressions).

---

## Self-Check: PASSED

- `README.md` exists and is 462 lines (>= 200 minimum): FOUND
- `docs/dev_logs/2026-04-07_root_readme_refresh.md` exists: FOUND
- Commit ce5f258 exists: FOUND
- Commit c4a6728 exists: FOUND
- No Telegram references in README: PASSED
- No Alpha Factory references in README: PASSED
- OPERATOR_QUICKSTART link present: PASSED
- CURRENT_STATE link present: PASSED
- README_SIMTRADER link present: PASSED
- INDEX.md link present: PASSED
