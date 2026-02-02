# Risk Policy

This repo is public. Private data must never be committed.

## What goes where
- `docs/`: public truth source (safe to commit)
- `packages/`, `services/`, `infra/`, `tools/`: source code (safe to commit)
- `kb/`: **private knowledge base** (gitignored)
- `artifacts/`: **private exports + dossiers** (gitignored)

## Guardrails
- `.gitignore` blocks `kb/**`, `artifacts/**`, and common secret-like files.
- Local pre-commit + pre-push guards block commits/pushes that include forbidden paths.
- Guards also fail if `kb/` or `artifacts/` contain tracked files (except `kb/README.md` and `kb/.gitkeep`).

### What is blocked (and why)
- Any staged file under `kb/` or `artifacts/` (private by definition).
- Any tracked file already under `kb/` or `artifacts/` (prevents private data from living in Git).
- Common secrets-like filenames (env files, `response_*.json`, export logs, secret-key-ish names).

## Enable hooks (recommended)

Use the versioned `.githooks/` directory so every contributor gets the guard automatically:

1. Create `.githooks/pre-commit` and `.githooks/pre-push` (already committed in this repo):
```bash
#!/usr/bin/env bash
python tools/guard/pre_commit_guard.py
```
```bash
#!/usr/bin/env bash
python tools/guard/pre_push_guard.py
```

2. Tell Git to use that directory:
```
git config core.hooksPath .githooks
```

### Legacy alternative (copy into .git/hooks)
If you prefer the classic approach, copy the guard manually:

PowerShell:
```
Copy-Item tools\guard\pre_push_guard.py .git\hooks\pre-push
Copy-Item tools\guard\pre_commit_guard.py .git\hooks\pre-commit
```

CMD:
```
copy tools\guard\pre_push_guard.py .git\hooks\pre-push
copy tools\guard\pre_commit_guard.py .git\hooks\pre-commit
```

## Run the guard manually
PowerShell:
```
python tools\guard\pre_commit_guard.py
python tools\guard\pre_push_guard.py
```

Or:
```
tools\guard\run_guard.ps1
```

If the guard blocks a push, move the data into `kb/` or `artifacts/` (and keep it out of Git),
then recommit.
