---
phase: quick-260409-khd
plan: 01
subsystem: infra/n8n
tags: [n8n, workflow-migration, docs, cleanup]
dependency_graph:
  requires: []
  provides: [infra/n8n/workflows/ as single canonical workflow source]
  affects: [infra/n8n/import_workflows.py, scripts/smoke_ris_n8n.py, docs/RIS_OPERATOR_GUIDE.md, docs/CURRENT_STATE.md, docs/adr/0013-ris-n8n-pilot-scoped.md, docs/runbooks/RIS_N8N_SMOKE_TEST.md]
tech_stack:
  added: []
  patterns: [git mv for file renames with history, force-add for gitignored .env files]
key_files:
  created:
    - docs/dev_logs/2026-04-09_n8n_workflow_location_migration.md
    - infra/n8n/workflows/ris-unified-dev.json (moved from workflows/n8n/)
    - infra/n8n/workflows/ris-health-webhook.json (moved from workflows/n8n/)
    - infra/n8n/workflows/workflow_ids.env (moved from workflows/n8n/)
  modified:
    - infra/n8n/import_workflows.py
    - scripts/smoke_ris_n8n.py
    - infra/n8n/README.md
    - workflows/n8n/README.md (replaced with stub)
    - docs/RIS_OPERATOR_GUIDE.md
    - docs/CURRENT_STATE.md
    - docs/adr/0013-ris-n8n-pilot-scoped.md
    - docs/runbooks/RIS_N8N_SMOKE_TEST.md
decisions:
  - Stub README left at workflows/n8n/ rather than deleting the directory, to avoid broken links in docs referencing the directory
  - workflow_ids.env force-added with git add -f to override the *.env gitignore pattern (file contains n8n internal IDs, not secrets)
  - Orphan check in smoke_ris_n8n.py changed from "directory must not exist" to "no JSON files in directory" to accommodate the stub README
metrics:
  duration: ~35 minutes
  completed: 2026-04-09
  tasks_completed: 2/2
  files_changed: 11
---

# Phase quick-260409-khd Plan 01: Migrate Canonical n8n Workflow Source Summary

**One-liner:** Moved active n8n workflow JSON from `workflows/n8n/` to `infra/n8n/workflows/`, deleted 18 legacy JSON files, and updated all import tooling and operator docs to use the single canonical location.

## What Was Done

Eliminated dual-canonical ambiguity for n8n workflow JSON. The repo previously had active workflow JSON in `workflows/n8n/` but import tooling and some docs pointing to `infra/n8n/workflows/`, with contradictory "legacy" labels in different files.

### Task 1: File moves and deletions (commit: f888d41)

- Moved 3 active files from `workflows/n8n/` to `infra/n8n/workflows/` (byte-identical, MD5 verified)
- Deleted 11 initial pilot template JSONs from `infra/n8n/workflows/` (superseded 2026-04-07)
- Deleted 9 JSON files from `workflows/n8n/` (7 legacy multi-workflow rebuild artifacts + 2 active files now at new location)
- Replaced `workflows/n8n/README.md` with stub redirect

### Task 2: Tooling and doc updates (commit: 950d31f)

- `infra/n8n/import_workflows.py`: `WORKFLOW_DIR` updated from `workflows/n8n` to `infra/n8n/workflows`
- `scripts/smoke_ris_n8n.py`: orphan check updated to verify no JSON in `workflows/n8n/` (stub README remains, which is expected)
- `infra/n8n/README.md`: Workflow Source Layout table updated; old location demoted to stub-only
- `docs/RIS_OPERATOR_GUIDE.md`: step 5 import command and canonical file paths updated
- `docs/CURRENT_STATE.md`: RIS n8n Pilot section updated with correct canonical path
- `docs/adr/0013-ris-n8n-pilot-scoped.md`: Workflow sources section updated; legacy note clarified
- `docs/runbooks/RIS_N8N_SMOKE_TEST.md`: all path references updated to `infra/n8n/workflows/`
- `docs/dev_logs/2026-04-09_n8n_workflow_location_migration.md`: migration audit log created

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| 1 | f888d41 | chore(quick-260409-khd-01): move canonical n8n workflow JSON to infra/n8n/workflows/ |
| 2 | 950d31f | feat(quick-260409-khd-01): update import tooling, smoke script, and operator docs to point to infra/n8n/workflows/ |

## Verification Results

### Final canonical location

```
ls infra/n8n/workflows/
ris-health-webhook.json  ris-unified-dev.json  workflow_ids.env
```

### Old location cleaned

```
ls workflows/n8n/
README.md
```

### Import script

`python infra/n8n/import_workflows.py --help` exits 0. Docstring references `infra/n8n/workflows`.

### Smoke script

`python scripts/smoke_ris_n8n.py`: 51 PASS, 2 FAIL, 0 SKIP.

Pre-existing failures unrelated to this task:
- `no-leading-equals:ris-unified-dev.json:Ingest: Run Acquire` — the Ingest node uses n8n expression syntax (`=` prefix for dynamic URL from webhook body); this was present in the original `workflows/n8n/ris-unified-dev.json` before migration (byte-identical move confirmed).
- `compose-profile-render` — Docker compose fails due to missing env var in the migrate service; unrelated to workflow JSON location.

All migration-critical checks pass: `workflow-files-exist`, `orphan-json-removed`, `json-parse`, `has-name`, `has-nodes`, `correct-container`, `known-subcommand`.

### Stale path grep

`git grep "workflows/n8n/ris-unified-dev" -- "*.py" "*.md"` returns no results outside dev_logs/ and .planning/. No active operator docs reference the old path.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] git mv failed after legacy files deleted from target directory**

- **Found during:** Task 1
- **Issue:** After `git rm` deleted the 11 legacy JSON files from `infra/n8n/workflows/`, git removed the physical directory. Subsequent `git mv workflows/n8n/ris-unified-dev.json infra/n8n/workflows/` failed with "No such file or directory."
- **Fix:** Used `mkdir -p infra/n8n/workflows/` to recreate the directory, then copied files from the main repo, verified MD5 checksums, and used `git add` + `git rm --cached` to simulate `git mv`.
- **Files modified:** infra/n8n/workflows/{ris-unified-dev.json, ris-health-webhook.json, workflow_ids.env}
- **Commit:** f888d41

**2. [Rule 3 - Blocking] workflow_ids.env rejected by git add due to *.env gitignore**

- **Found during:** Task 1
- **Issue:** `git add infra/n8n/workflows/workflow_ids.env` was rejected — the file matches `*.env` in root `.gitignore`.
- **Fix:** Used `git add -f infra/n8n/workflows/workflow_ids.env` to force-add. The file contains n8n-internal workflow IDs only (not secrets), same gitignore behavior as at the original location.
- **Commit:** f888d41

**3. [Rule 3 - Blocking] Orphan check would fail because stub README remains in workflows/n8n/**

- **Found during:** Task 2 planning
- **Issue:** The original smoke script check verified that `workflows/n8n/` directory does not exist at all. After this migration, the stub README remains there. A direct `if ORPHAN_DIR.exists(): FAIL` would trigger falsely.
- **Fix:** Updated orphan check to glob for `*.json` files specifically, consistent with the plan's specified code pattern. PASS when no JSON files remain regardless of whether the directory exists.
- **Files modified:** scripts/smoke_ris_n8n.py
- **Commit:** 950d31f

## Known Stubs

None. All active workflow JSON is wired to the canonical location. The `workflows/n8n/README.md` stub is intentional and documented.

## Threat Flags

None. No new network endpoints, auth paths, file access patterns, or schema changes introduced.

## Self-Check: PASSED

- f888d41 exists: confirmed via `git log`
- 950d31f exists: confirmed via `git log`
- `infra/n8n/workflows/` contains ris-unified-dev.json, ris-health-webhook.json, workflow_ids.env: confirmed
- `workflows/n8n/` contains only README.md: confirmed
- `infra/n8n/import_workflows.py` WORKFLOW_DIR = infra/n8n/workflows: confirmed
- `scripts/smoke_ris_n8n.py` orphan check uses glob for *.json: confirmed
- Dev log created at docs/dev_logs/2026-04-09_n8n_workflow_location_migration.md: confirmed
