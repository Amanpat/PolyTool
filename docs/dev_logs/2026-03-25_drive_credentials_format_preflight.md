# Drive Credentials Format Preflight

**Date**: 2026-03-25
**Type**: Workflow-only hardening for Google Drive sync credential validation.

---

## Root Cause Observed

After the missing `GDRIVE_FOLDER_ID` issue was addressed, the Drive sync run
failed inside the upload action with:

`Error: fetching JWT credentials failed with error: invalid character '^' looking for beginning of object key string`

That strongly indicates `GDRIVE_CREDENTIALS` was present but malformed for the
expected service-account input format. Without a preflight check, the failure
surfaced inside the third-party action rather than as a deterministic workflow
validation error.

---

## Files Changed And Why

| File | Change | Reason |
|---|---|---|
| `.github/workflows/sync-docs-to-drive.yml` | Kept the existing triggers and upload steps, but strengthened `Validate Google Drive secrets` to check presence, base64 decoding, JSON parsing, and required service-account keys before upload. | Fail early with explicit messages for empty secrets, bad base64, invalid JSON, or wrong credential shape. |
| `docs/dev_logs/2026-03-25_drive_credentials_format_preflight.md` | Created this dev log. | Records the malformed-credentials failure mode and the new deterministic preflight behavior. |

---

## How To Interpret Each Validation Failure

- `GDRIVE_CREDENTIALS missing or empty...`
  The repository secret is missing, empty, or unavailable to the workflow run.
- `GDRIVE_FOLDER_ID missing or empty...`
  The folder ID secret is missing, empty, or unavailable to the workflow run.
- `GDRIVE_CREDENTIALS base64 decode failed...`
  The secret is present but is not valid base64-encoded data.
- `GDRIVE_CREDENTIALS JSON parse failed...`
  The secret decoded successfully, but the decoded payload is not valid JSON.
- `GDRIVE_CREDENTIALS JSON validation failed. Missing required service-account keys: ...`
  The decoded JSON exists, but it is not shaped like the expected Google service-account credential.
- `GDRIVE_CREDENTIALS JSON validation failed. type must be service_account.`
  The decoded JSON parsed, but it is not the expected service-account credential type.

When validation passes, the workflow prints only safe status lines:

- `GDRIVE_CREDENTIALS present`
- `GDRIVE_FOLDER_ID present`
- `GDRIVE_CREDENTIALS base64 decode passed`
- `GDRIVE_CREDENTIALS JSON parse passed`

No secret contents are printed.

---

## Manual Rerun Instructions

1. Open the repository on GitHub.
2. Go to **Actions**.
3. Open **Sync Docs to Google Drive**.
4. Use **Run workflow** to trigger a manual run.
5. Inspect `Validate Google Drive secrets` before the upload steps.
6. If validation fails, correct the named repository secret and rerun.
7. If validation passes, continue troubleshooting with the upload action logs.
