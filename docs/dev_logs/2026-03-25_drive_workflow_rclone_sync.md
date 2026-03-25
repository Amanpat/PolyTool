# Drive Workflow Rclone Sync

**Date**: 2026-03-25
**Type**: Workflow-only Drive sync fix; no app code, strategy code, or unrelated CI changes.

---

## Root Cause Of The Prior Behavior

The previous workflow used `adityak74/google-drive-upload-git-action@main` with:

- `filename: "docs/"`
- `folderId: ${{ secrets.GDRIVE_FOLDER_ID }}`
- `mirrorDirectoryStructure: "true"`

That treated the local `docs/` directory as an upload object under the target
Drive folder instead of applying directory-contents semantics to the existing
Drive `docs/` folder. The result was a newly created `docs` folder object in
Drive rather than a predictable update of the contents already expected at:

`<Drive root folder>/docs/`

`AGENTS.md` and `claude.md` were not affected in the same way because they were
already being uploaded as explicit single files.

---

## Why Rclone Was Chosen

`rclone` makes the destination path semantics explicit:

- `rclone copy docs gdrive:docs` updates the contents of the repo `docs/`
  directory into the fixed remote `docs/` path.
- `rclone copyto claude.md gdrive:claude.md` updates one exact file path.
- `rclone copyto AGENTS.md gdrive:AGENTS.md` updates one exact file path.

It also supports configuring the Google Drive remote from the existing repo
secrets without printing them:

- `GDRIVE_CREDENTIALS` -> base64-decoded service-account JSON file
- `GDRIVE_FOLDER_ID` -> `root_folder_id` for the rclone Drive remote

With `root_folder_id` set, the workflow treats the configured Drive folder as
the remote root, which keeps all uploads anchored to one fixed Drive location.

---

## Files Changed And Why

| File | Change | Reason |
|---|---|---|
| `.github/workflows/sync-docs-to-drive.yml` | Replaced the old Google Drive upload action steps with `rclone` install plus a single rclone-driven sync step. Kept the existing `push` path scope and `workflow_dispatch`. | Make `docs/` land in the fixed Drive `docs/` destination, keep `AGENTS.md` and `claude.md` deterministic, and avoid stray Drive folder creation. |
| `docs/dev_logs/2026-03-25_drive_workflow_rclone_sync.md` | Created this dev log. | Record the root cause, the rclone decision, the chosen semantics, and the expected post-run Drive layout. |

---

## Commands And Steps Used In The Workflow

1. Validate `GDRIVE_CREDENTIALS` and `GDRIVE_FOLDER_ID` are present, base64-decode
   the credential payload, and confirm the decoded JSON is a Google
   service-account credential.
2. Install `rclone`.
3. Echo the planned Drive targets so the intended layout is obvious in the run log.
4. Base64-decode `GDRIVE_CREDENTIALS` into a temporary JSON file.
5. Build a temporary rclone config with:
   - `type = drive`
   - `scope = drive`
   - `root_folder_id = ${GDRIVE_FOLDER_ID}`
   - `service_account_file = <temporary decoded JSON path>`
6. Ensure the fixed remote docs destination exists with:
   - `rclone mkdir gdrive:docs`
7. Copy repo docs into the fixed Drive docs destination with:
   - `rclone copy docs gdrive:docs`
8. Update the fixed root-level files with:
   - `rclone copyto claude.md gdrive:claude.md`
   - `rclone copyto AGENTS.md gdrive:AGENTS.md`

The workflow never prints credential contents or the decoded JSON.

---

## Chosen Semantics

`docs/` uses **copy**, not `sync`.

Reason:

- The requested safe default says to use exact mirroring only if deletion
  behavior is clearly intended.
- The current requirement is to update the existing Drive docs folder contents
  predictably and stop creating stray `docs` folders.
- `rclone copy` satisfies that without propagating deletions from the repo to
  Drive.

Operational consequence:

- New and changed repo files under `docs/` are copied to `<Drive root folder>/docs/`.
- Files that exist only in Drive are **not** deleted by this workflow.

If exact mirror semantics are wanted later, the `docs` command can be changed
from `rclone copy docs gdrive:docs` to `rclone sync docs gdrive:docs`.

---

## Expected Drive Structure After A Run

Given `GDRIVE_FOLDER_ID` points to the intended Drive root folder, the workflow
targets this exact layout:

```text
<Drive root folder>/
  AGENTS.md
  claude.md
  docs/
    PLAN_OF_RECORD.md
    ARCHITECTURE.md
    reference/
      POLYTOOL_MASTER_ROADMAP_v5.md
    ...
```

Important behavior:

- Repo `docs/` contents land under the existing remote `docs/` path.
- `AGENTS.md` is updated in place at `<Drive root folder>/AGENTS.md`.
- `claude.md` is updated in place at `<Drive root folder>/claude.md`.
- The workflow does not rely on the third-party action's directory upload
  behavior for `docs/`.

---

## Open Operational Notes

- The existing trigger scope remains unchanged:
  - `docs/**`
  - `claude.md`
  - `AGENTS.md`
  - `config/strategy_research_program.md`
  - `workflow_dispatch`
- `config/strategy_research_program.md` still acts only as a trigger path for
  this workflow; it is not uploaded by the current job.
- `rclone copy` does not delete Drive-only files from the remote `docs/` folder.
- The workflow now depends on installing `rclone` at runtime instead of the
  previous upload action.
