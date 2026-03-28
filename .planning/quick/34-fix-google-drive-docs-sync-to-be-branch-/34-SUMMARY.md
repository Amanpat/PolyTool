---
phase: quick-034
plan: 34
subsystem: ci-workflow
tags: [github-actions, google-drive, sync, workflow]
dependency_graph:
  requires: []
  provides: [branch-agnostic-drive-sync]
  affects: [.github/workflows/sync-docs-to-drive.yml]
tech_stack:
  added: []
  patterns: [github-actions-glob-trigger, GITHUB_REF_NAME]
key_files:
  created:
    - docs/dev_logs/2026-03-28_google_drive_sync_branch_agnostic.md
  modified:
    - .github/workflows/sync-docs-to-drive.yml
decisions:
  - "Used branches: ['**'] glob instead of adding specific branch names; single-quote form required for GitHub Actions globs inside bracket syntax"
  - "Added Show current branch step immediately after checkout so log output identifies triggering branch without relying on job context navigation"
metrics:
  duration_minutes: 5
  completed_date: "2026-03-28"
  tasks_completed: 2
  files_changed: 2
---

# Phase quick-034 Plan 34: Fix Google Drive Docs Sync Branch-Agnostic Summary

## One-liner

Changed `branches: [main, phase-1, phase-1B]` to `branches: ['**']` and added branch-echo log step so every push fires the Drive sync without manual workflow edits.

## Tasks Completed

| # | Name | Commit | Files |
|---|------|--------|-------|
| 1 | Make workflow trigger branch-agnostic and add branch-echo step | 733297e | .github/workflows/sync-docs-to-drive.yml |
| 2 | Write dev log and run regression suite | adcf6b8 | docs/dev_logs/2026-03-28_google_drive_sync_branch_agnostic.md |

## What Was Done

The Google Drive sync workflow had a hardcoded branch allowlist (`[main, phase-1, phase-1B]`). Any push to any other branch silently skipped the sync. The fix is a single-line trigger change to `branches: ['**']` which matches all branch names including those containing slashes.

A "Show current branch" step was added immediately after checkout. It echoes `GITHUB_REF_NAME` (short name) and `GITHUB_REF` (full ref) so operators can confirm which branch triggered each Actions run without navigating into job context.

All existing guardrails are untouched: secret validation, base64 decode, JSON parse, rclone install, and the actual sync steps are unchanged.

## Decisions Made

- `branches: ['**']` glob: the `'**'` pattern in GitHub Actions matches all branch names including branches containing slashes. Single-quote form is required when using glob patterns inside the bracket list syntax. This is the canonical solution for branch-agnostic push triggers.
- "Show current branch" step position: placed immediately after checkout (before any secret-validation steps) so the branch is logged even if a later step fails, making triage easier.

## Verification Results

All four verification checks passed:
1. YAML parse via `python -c "import yaml; yaml.safe_load(...)"` — OK
2. `grep "'**'"` in workflow file — OK
3. `grep "GITHUB_REF_NAME"` in workflow file — OK
4. `python -m polytool --help` loads without error — OK
5. `python -m pytest tests/ -x -q --tb=short` — 2717 passed, 0 failed, 25 warnings

## Deviations from Plan

None - plan executed exactly as written.

## Known Stubs

None.

## Self-Check: PASSED

- `.github/workflows/sync-docs-to-drive.yml` — FOUND
- `docs/dev_logs/2026-03-28_google_drive_sync_branch_agnostic.md` — FOUND
- Commit 733297e — FOUND
- Commit adcf6b8 — FOUND
