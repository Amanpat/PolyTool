# Drive Sync Manual Trigger

**Date**: 2026-03-25
**Type**: Workflow-only change; no application code, strategy logic, or infrastructure redesign.

---

## Root Cause

The Google Drive sync workflow only ran on `push` when the commit touched one
of these scoped paths:

- `docs/**`
- `claude.md`
- `AGENTS.md`
- `config/strategy_research_program.md`

A recent commit changed only `.github/workflows/sync-docs-to-drive.yml`, so the
workflow did not trigger and no Google Drive sync was attempted. The workflow
needed a manual trigger path for connector and sync verification without
broadening the existing automatic push scope.

---

## Files Changed and Why

| File | Change | Reason |
|---|---|---|
| `.github/workflows/sync-docs-to-drive.yml` | Added `workflow_dispatch` and a short explanatory comment. | Allows manual runs from the GitHub Actions UI while preserving the existing branch/path-filtered `push` trigger. |
| `docs/dev_logs/2026-03-25_drive_sync_manual_trigger.md` | Created this dev log. | Records the trigger mismatch, the workflow fix, and the manual verification path. |

---

## How To Test From GitHub Actions UI

1. Open the repository on GitHub.
2. Go to **Actions**.
3. Open the **Sync Docs to Google Drive** workflow.
4. Click **Run workflow**.
5. Choose the target branch (`main`, `phase-1`, or `phase-1A` as appropriate).
6. Start the run and confirm the `sync-to-drive` job executes.
7. Verify the three upload steps run:
   - `Upload docs folder`
   - `Upload claude.md`
   - `Upload AGENTS.md`
8. Confirm the expected files appear or update in the Drive folder referenced by
   `GDRIVE_FOLDER_ID`.

---

## Open Risks Or Follow-Ups

- This change does not validate the correctness of `GDRIVE_CREDENTIALS` or
  `GDRIVE_FOLDER_ID`; it only makes manual execution possible.
- `config/strategy_research_program.md` remains a trigger-only path. It can
  start the workflow on push, but the current workflow does not upload that
  file.
- The workflow still depends on the external action
  `adityak74/google-drive-upload-git-action@main`; any upstream behavior change
  there can affect sync results.
