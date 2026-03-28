# Dev Log: Google Drive Docs Sync -- Branch-Agnostic Fix
Date: 2026-03-28
Quick task: 034

## Problem
The sync workflow (`sync-docs-to-drive.yml`) had a hardcoded branch list:
  branches: [main, phase-1, phase-1B]
Pushes to any other branch (new, renamed, feature) silently skipped the sync.

## Root Cause
Single `branches:` filter on line 6 of the workflow. No helper scripts involved.
The rclone sync step itself was already branch-agnostic.

## Fix Applied
1. Changed trigger to `branches: ['**']` -- matches all branch names including
   branches with slashes or any naming convention.
2. Added "Show current branch" step (GITHUB_REF_NAME / GITHUB_REF echo) so
   operators can confirm which branch triggered each run in the Actions log.

## Files Changed
- `.github/workflows/sync-docs-to-drive.yml` -- trigger + log step

## Behavior After Fix
- Every push to any branch that touches a watched path fires the sync.
- New branches auto-sync without workflow edits.
- Renamed branches auto-sync without workflow edits.
- Drive destination is unchanged: same root folder, same rclone paths.

## Validation
- YAML parse check passed.
- grep confirms `'**'` trigger and GITHUB_REF_NAME step present.
- Full pytest suite run: 2717 passed, 0 failed, 25 warnings in 85.66s.

## Tests
Run: `python -m pytest tests/ -x -q --tb=short`
Result: 2717 passed, 0 failed, 25 warnings in 85.66s
No regressions -- workflow change touches no Python code.
