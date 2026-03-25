# Drive Secret Preflight Fix

**Date**: 2026-03-25
**Type**: Workflow-only hardening for Google Drive sync troubleshooting.

---

## Root Cause Observed

The Drive sync workflow was reaching the upload action and failing with:

`missing input 'folderId'`

That indicates `GDRIVE_FOLDER_ID` was empty or unavailable at runtime. Without a
preflight check, the failure surfaced inside the third-party upload action,
which made troubleshooting less direct than it needed to be.

---

## Files Changed And Why

| File | Change | Reason |
|---|---|---|
| `.github/workflows/sync-docs-to-drive.yml` | Added job-level env wiring for `GDRIVE_CREDENTIALS` and `GDRIVE_FOLDER_ID`, plus a `Validate Google Drive secrets` step immediately after checkout. | Fail fast with explicit, deterministic error messages before the upload action runs. |
| `docs/dev_logs/2026-03-25_drive_secret_preflight_fix.md` | Created this dev log. | Records the root cause, the guard added, and how to verify the behavior from GitHub Actions. |

---

## How To Interpret Preflight Pass/Fail

- If the step prints `GDRIVE_CREDENTIALS present` and `GDRIVE_FOLDER_ID present`,
  the workflow can proceed to the upload steps with the expected secret inputs
  available.
- If the step fails on `GDRIVE_CREDENTIALS`, the repository secret is missing,
  empty, or unavailable to the workflow run context.
- If the step fails on `GDRIVE_FOLDER_ID`, the repository secret is missing,
  empty, or unavailable to the workflow run context.
- The validation step never prints secret values; it only prints safe presence
  status or a clear failure reason.

---

## Manual Next Check In GitHub UI

1. Open the repository on GitHub.
2. Go to **Actions**.
3. Open **Sync Docs to Google Drive**.
4. Use **Run workflow** to trigger a manual run.
5. Confirm `Validate Google Drive secrets` runs immediately after checkout.
6. If it passes, inspect the upload steps.
7. If it fails, update the missing repository secret and rerun the workflow.
