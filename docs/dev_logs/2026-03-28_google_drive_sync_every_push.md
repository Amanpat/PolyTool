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
python -c "
import yaml
with open('.github/workflows/sync-docs-to-drive.yml') as f:
    doc = yaml.safe_load(f)
# PyYAML parses 'on' as True (boolean key)
push = doc[True]['push']
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
