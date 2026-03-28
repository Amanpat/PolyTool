---
phase: quick-034
plan: 34
type: execute
wave: 1
depends_on: []
files_modified:
  - .github/workflows/sync-docs-to-drive.yml
  - docs/dev_logs/2026-03-28_google_drive_sync_branch_agnostic.md
autonomous: true
requirements: [QUICK-034]

must_haves:
  truths:
    - "Pushing to any branch that changes a watched path fires the sync workflow"
    - "New and renamed branches trigger without workflow edits"
    - "The workflow log clearly shows which branch triggered the run"
    - "All existing auth/secret guardrails remain intact"
  artifacts:
    - path: ".github/workflows/sync-docs-to-drive.yml"
      provides: "Branch-agnostic workflow trigger"
      contains: "branches: ['**']"
    - path: "docs/dev_logs/2026-03-28_google_drive_sync_branch_agnostic.md"
      provides: "Operator record of the change"
  key_links:
    - from: ".github/workflows/sync-docs-to-drive.yml"
      to: "Google Drive root folder"
      via: "rclone copy on push"
      pattern: "rclone copy docs gdrive:docs"
---

<objective>
Fix the Google Drive docs sync workflow so it fires on every push, regardless of branch name.

Purpose: The current trigger is `branches: [main, phase-1, phase-1B]`. Any push to a branch
not in that list silently skips the sync. New branches and renamed branches are never synced
until someone manually edits the workflow.

Output: A single-line trigger change (`branches: ['**']`) plus a branch-echo log step and a
dev log. No helper scripts exist; the entire fix lives in the workflow file.
</objective>

<execution_context>
@D:/Coding Projects/Polymarket/PolyTool/.claude/get-shit-done/workflows/execute-plan.md
@D:/Coding Projects/Polymarket/PolyTool/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md

Relevant source file (read before editing):
@.github/workflows/sync-docs-to-drive.yml
</context>

<tasks>

<task type="auto">
  <name>Task 1: Make the workflow trigger branch-agnostic and add a branch-echo log step</name>
  <files>.github/workflows/sync-docs-to-drive.yml</files>
  <action>
    Read the file first (already read — 130 lines).

    Change 1 — trigger (line 6): replace the hardcoded list
      FROM:  branches: [main, phase-1, phase-1B]
      TO:    branches: ['**']

    The `'**'` glob matches every branch name including branches with slashes. GitHub Actions
    requires the single-quote form for glob patterns inside bracket syntax.

    Change 2 — add a "Show current branch" step immediately after the checkout step (line 19)
    and before the "Validate Google Drive secrets" step. Insert:

      - name: Show current branch
        shell: bash
        run: |
          set -euo pipefail
          echo "Triggered by push to branch: ${GITHUB_REF_NAME}"
          echo "Full ref: ${GITHUB_REF}"

    GITHUB_REF_NAME is the short branch name (e.g. phase-1B, my-new-feature).
    GITHUB_REF is the full ref (e.g. refs/heads/phase-1B). Both are set automatically
    by GitHub Actions on every push event — no extra secrets or config needed.

    No other changes. The rclone sync itself is already branch-agnostic (it always writes
    to the same Drive root folder). The trigger was the only blocker.

    Validate: the final YAML must pass `python3 -c "import yaml; yaml.safe_load(open('.github/workflows/sync-docs-to-drive.yml'))"` without error.
  </action>
  <verify>
    <automated>python3 -c "import yaml; yaml.safe_load(open('.github/workflows/sync-docs-to-drive.yml'))" && grep -q "'**'" .github/workflows/sync-docs-to-drive.yml && grep -q "GITHUB_REF_NAME" .github/workflows/sync-docs-to-drive.yml && echo "PASS"</automated>
  </verify>
  <done>
    - `branches: ['**']` is present in the trigger block
    - "Show current branch" step exists and references GITHUB_REF_NAME
    - YAML parses without error
  </done>
</task>

<task type="auto">
  <name>Task 2: Write dev log and run regression suite</name>
  <files>docs/dev_logs/2026-03-28_google_drive_sync_branch_agnostic.md</files>
  <action>
    Create docs/dev_logs/2026-03-28_google_drive_sync_branch_agnostic.md with the
    following content (plain ASCII, no emoji):

    ---
    # Dev Log: Google Drive Docs Sync — Branch-Agnostic Fix
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
    1. Changed trigger to `branches: ['**']` — matches all branch names including
       branches with slashes or any naming convention.
    2. Added "Show current branch" step (GITHUB_REF_NAME / GITHUB_REF echo) so
       operators can confirm which branch triggered each run in the Actions log.

    ## Files Changed
    - `.github/workflows/sync-docs-to-drive.yml` — trigger + log step

    ## Behavior After Fix
    - Every push to any branch that touches a watched path fires the sync.
    - New branches auto-sync without workflow edits.
    - Renamed branches auto-sync without workflow edits.
    - Drive destination is unchanged: same root folder, same rclone paths.

    ## Validation
    - YAML parse check passed.
    - grep confirms `'**'` trigger and GITHUB_REF_NAME step present.
    - Full pytest suite run: (record exact count from run below).

    ## Tests
    Run `python -m pytest tests/ -x -q --tb=short` and record result here.
    Expected: all passing, no regressions (workflow change touches no Python code).
    ---

    After writing the dev log, run the regression suite:
      python -m pytest tests/ -x -q --tb=short

    Record the exact pass/fail count in the dev log's "Tests" section.
  </action>
  <verify>
    <automated>python -m pytest tests/ -x -q --tb=short 2>&1 | tail -5</automated>
  </verify>
  <done>
    - Dev log exists at the required path
    - pytest passes with no new failures
    - Dev log records exact test count
  </done>
</task>

</tasks>

<verification>
After both tasks:
1. `python3 -c "import yaml; yaml.safe_load(open('.github/workflows/sync-docs-to-drive.yml'))"` exits 0
2. `grep "'\\*\\*'" .github/workflows/sync-docs-to-drive.yml` matches
3. `grep "GITHUB_REF_NAME" .github/workflows/sync-docs-to-drive.yml` matches
4. `python -m polytool --help` loads without error
5. `python -m pytest tests/ -x -q --tb=short` — no regressions
</verification>

<success_criteria>
- The workflow trigger no longer contains a hardcoded branch list
- Any push to any branch fires the sync (no code edit required for new/renamed branches)
- The Actions log shows the triggering branch ref clearly
- All existing guardrails (secret validation, rclone config, credential checks) are untouched
- Existing tests pass
</success_criteria>

<output>
After completion, create `.planning/quick/34-fix-google-drive-docs-sync-to-be-branch-/34-SUMMARY.md`
</output>
