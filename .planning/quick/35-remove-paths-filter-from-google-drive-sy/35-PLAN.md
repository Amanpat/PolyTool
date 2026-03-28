---
phase: quick-035
plan: 35
type: execute
wave: 1
depends_on: []
files_modified:
  - .github/workflows/sync-docs-to-drive.yml
  - docs/dev_logs/2026-03-28_google_drive_sync_every_push.md
autonomous: true
requirements: [QUICK-035]

must_haves:
  truths:
    - "Every push to any branch triggers the workflow, regardless of which files changed"
    - "workflow_dispatch trigger is preserved"
    - "Branch logging step is preserved"
    - "Drive sync targets (docs/, claude.md, AGENTS.md) are unchanged"
    - "A dev log exists documenting the exact trigger change"
  artifacts:
    - path: ".github/workflows/sync-docs-to-drive.yml"
      provides: "Trigger block without paths: filter"
      contains: "push:"
    - path: "docs/dev_logs/2026-03-28_google_drive_sync_every_push.md"
      provides: "Operator-facing change record"
  key_links:
    - from: ".github/workflows/sync-docs-to-drive.yml"
      to: "GitHub Actions trigger"
      via: "on: push: (no paths filter)"
      pattern: "push:\\s*\\n\\s*branches:"
---

<objective>
Remove the `paths:` filter from the Google Drive sync workflow so it fires on every push to any branch, not only when watched paths change.

Purpose: The branch-agnostic fix (quick-034) made the workflow branch-agnostic, but the remaining `paths:` gate means it still silently skips pushes that do not touch `docs/**`, `claude.md`, `AGENTS.md`, or `config/strategy_research_program.md`. Removing the filter closes that gap: every push now syncs docs unconditionally.

Output: Updated workflow YAML + dev log.
</objective>

<execution_context>
@D:/Coding Projects/Polymarket/PolyTool/.claude/get-shit-done/workflows/execute-plan.md
@D:/Coding Projects/Polymarket/PolyTool/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@.github/workflows/sync-docs-to-drive.yml
</context>

<tasks>

<task type="auto">
  <name>Task 1: Remove paths filter and add explanatory comment</name>
  <files>.github/workflows/sync-docs-to-drive.yml</files>
  <action>
Edit `.github/workflows/sync-docs-to-drive.yml`. In the `on:` block, remove the entire `paths:` key and its four list entries (lines 7-10 in the current file). The resulting `push:` entry must have only `branches: ['**']` with no `paths:` sub-key.

Add a brief YAML comment directly above the `push:` key (or inline after `branches: ['**']`) that reads:
  # Fires on every push to every branch — no paths filter intentional.

Keep `workflow_dispatch:` exactly as-is (line 3-4). Do not touch any job steps, env vars, or rclone logic.

Final `on:` block should look like:
```yaml
on:
  # Manual trigger exists for connector/sync verification.
  workflow_dispatch:
  # Fires on every push to every branch — no paths filter intentional.
  push:
    branches: ['**']
```
  </action>
  <verify>
    <automated>python3 -c "
import yaml, sys
with open('.github/workflows/sync-docs-to-drive.yml') as f:
    doc = yaml.safe_load(f)
push = doc.get('on', {}).get('push', {})
assert 'paths' not in push, 'paths filter still present'
assert push.get('branches') == ['**'], 'branches not set to wildcard'
print('OK: no paths filter, branches=[**]')
"</automated>
  </verify>
  <done>YAML parses cleanly, no `paths:` key under `push:`, `branches: ['**']` present, `workflow_dispatch` still present.</done>
</task>

<task type="auto">
  <name>Task 2: Write dev log</name>
  <files>docs/dev_logs/2026-03-28_google_drive_sync_every_push.md</files>
  <action>
Create `docs/dev_logs/2026-03-28_google_drive_sync_every_push.md` with the following content:

---
# 2026-03-28 — Google Drive Sync: Every-Push Trigger

## Context

Quick-034 fixed the branch allowlist bug by replacing the hardcoded branch list with `branches: ['**']`. However, the `paths:` filter remained, meaning the workflow only fired when a push included changes to `docs/**`, `claude.md`, `AGENTS.md`, or `config/strategy_research_program.md`. Pushes that touched only code files (e.g., Python modules, tests) silently skipped the sync.

## Change Made

**File:** `.github/workflows/sync-docs-to-drive.yml`

**Before (trigger block):**
```yaml
on:
  workflow_dispatch:
  push:
    branches: ['**']
    paths:
      - "docs/**"
      - "claude.md"
      - "AGENTS.md"
      - "config/strategy_research_program.md"
```

**After (trigger block):**
```yaml
on:
  # Manual trigger exists for connector/sync verification.
  workflow_dispatch:
  # Fires on every push to every branch — no paths filter intentional.
  push:
    branches: ['**']
```

## What "Every Push" Means

- Any `git push` to any branch (feature, hotfix, main, phase-1B, etc.) triggers the workflow.
- No file-path condition is checked.
- The workflow still syncs the same Drive targets as before: `docs/` folder, `claude.md`, `AGENTS.md`.
- Deletions are still NOT propagated to Drive (`rclone copy`, not `sync`).

## What Still Syncs

| Source | Drive destination | Method |
|--------|------------------|--------|
| `docs/` (entire tree) | `<Drive root>/docs/` | `rclone copy` |
| `claude.md` | `<Drive root>/claude.md` | `rclone copyto` |
| `AGENTS.md` | `<Drive root>/AGENTS.md` | `rclone copyto` |

## Verification

```bash
# Confirm no paths filter in YAML
python3 -c "
import yaml
with open('.github/workflows/sync-docs-to-drive.yml') as f:
    doc = yaml.safe_load(f)
push = doc['on']['push']
assert 'paths' not in push
assert push['branches'] == ['**']
print('OK')
"
```

## No-Op Changes

- Secrets model: unchanged
- rclone targets: unchanged
- Branch logging step: unchanged
- workflow_dispatch: preserved
- No new dependencies introduced
  </action>
  <verify>
    <automated>python3 -c "
import pathlib
p = pathlib.Path('docs/dev_logs/2026-03-28_google_drive_sync_every_push.md')
assert p.exists(), 'dev log missing'
text = p.read_text()
assert 'paths' in text, 'should document the paths filter removal'
assert 'every push' in text.lower(), 'should mention every push semantics'
print('OK: dev log exists and contains expected content')
"</automated>
  </verify>
  <done>Dev log file exists, documents the before/after trigger block, Drive targets table, and verification command.</done>
</task>

</tasks>

<verification>
```bash
# 1. YAML is valid and paths filter is gone
python3 -c "
import yaml
with open('.github/workflows/sync-docs-to-drive.yml') as f:
    doc = yaml.safe_load(f)
push = doc['on']['push']
assert 'paths' not in push
assert push['branches'] == ['**']
assert 'workflow_dispatch' in doc['on']
print('YAML OK')
"

# 2. Dev log exists
ls docs/dev_logs/2026-03-28_google_drive_sync_every_push.md

# 3. No regressions
python -m pytest tests/ -x -q --tb=short
```
</verification>

<success_criteria>
- `.github/workflows/sync-docs-to-drive.yml` has no `paths:` key under `push:`
- `branches: ['**']` is present
- `workflow_dispatch:` is present
- Explanatory comment is in the trigger block
- Dev log documents the exact change, drive targets, and verification command
- All existing tests still pass (2717 baseline)
</success_criteria>

<output>
After completion, create `.planning/quick/35-remove-paths-filter-from-google-drive-sy/35-SUMMARY.md` using the summary template.
</output>
