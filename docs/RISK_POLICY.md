# Risk Policy

This repo is public. Private data must never be committed.

## What goes where
- `docs/`: public truth source (safe to commit)
- `packages/`, `services/`, `infra/`, `tools/`: source code (safe to commit)
- `kb/`: **private knowledge base** (gitignored)
- `artifacts/`: **private exports + dossiers** (gitignored)

## Guardrails
- `.gitignore` blocks `kb/**`, `artifacts/**`, and common secret-like files.
- A local pre-push guard blocks pushes that include forbidden paths.

## Enable the pre-push hook
Copy the guard into `.git/hooks/pre-push`:

PowerShell:
```
Copy-Item tools\guard\pre_push_guard.py .git\hooks\pre-push
```

CMD:
```
copy tools\guard\pre_push_guard.py .git\hooks\pre-push
```

## Run the guard manually
PowerShell:
```
python tools\guard\pre_push_guard.py
```

Or:
```
tools\guard\run_guard.ps1
```

If the guard blocks a push, move the data into `kb/` or `artifacts/` (and keep it out of Git),
then recommit.
