---
phase: quick-035
plan: 35
subsystem: ci
tags: [github-actions, google-drive, workflow, trigger]
dependency_graph:
  requires: [quick-034]
  provides: [every-push-drive-sync]
  affects: [.github/workflows/sync-docs-to-drive.yml]
tech_stack:
  added: []
  patterns: [yaml-trigger-no-paths-filter]
key_files:
  created:
    - docs/dev_logs/2026-03-28_google_drive_sync_every_push.md
  modified:
    - .github/workflows/sync-docs-to-drive.yml
decisions:
  - Remove paths filter from push trigger so every push syncs Drive unconditionally
metrics:
  duration: "4 minutes"
  completed: "2026-03-28"
  tasks_completed: 2
  files_changed: 2
---

# Phase quick-035 Plan 35: Remove Paths Filter from Google Drive Sync Summary

## One-liner

Removed `paths:` filter from sync-docs-to-drive.yml push trigger so every git push to any branch unconditionally fires the Drive sync.

## What Was Done

### Task 1: Remove paths filter and add explanatory comment (commit: dc300e6)

Edited `.github/workflows/sync-docs-to-drive.yml`. Removed the `paths:` sub-key and its four entries (`docs/**`, `claude.md`, `AGENTS.md`, `config/strategy_research_program.md`) from the `push:` trigger. Added an explanatory comment `# Fires on every push to every branch — no paths filter intentional.` above the `push:` key. Updated `workflow_dispatch` comment to remove the now-stale reference to path filters.

Before:
```yaml
on:
  # Manual trigger exists for connector/sync verification when path filters do not fire.
  workflow_dispatch:
  push:
    branches: ['**']
    paths:
      - "docs/**"
      - "claude.md"
      - "AGENTS.md"
      - "config/strategy_research_program.md"
```

After:
```yaml
on:
  # Manual trigger exists for connector/sync verification.
  workflow_dispatch:
  # Fires on every push to every branch — no paths filter intentional.
  push:
    branches: ['**']
```

### Task 2: Write dev log (commit: 23b598f)

Created `docs/dev_logs/2026-03-28_google_drive_sync_every_push.md` documenting the before/after trigger block, what "every push" means operationally, the Drive targets table, a verification command (with note about PyYAML boolean key), and no-op changes.

## Verification Results

- YAML parses cleanly: `push:` has no `paths:` key, `branches: ['**']` present, `workflow_dispatch` preserved.
- Dev log exists and contains expected content.
- Test suite: 2717 passed, 0 failed (baseline unchanged). Pre-existing `test_batch_time_budget_stops_launching_new_markets` flaky failure not caused by this change.

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None.

## Self-Check: PASSED

- `.github/workflows/sync-docs-to-drive.yml` — verified modified and correct
- `docs/dev_logs/2026-03-28_google_drive_sync_every_push.md` — verified exists with expected content
- Commits dc300e6 and 23b598f both present in git log
