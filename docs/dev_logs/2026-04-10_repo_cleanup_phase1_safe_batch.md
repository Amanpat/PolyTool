# 2026-04-10 repo cleanup phase1 safe batch

## Files moved / deleted and why

| Path | Action | Reason |
|------|--------|--------|
| `docs/debug/DEBUG-category-coverage-zero.md` | Moved to `docs/archive/debug/DEBUG-category-coverage-zero.md` | Archive human-authored debug notes instead of deleting them |
| `docs/debug/DEBUG-clickhouse-hostname-resolution.md` | Moved to `docs/archive/debug/DEBUG-clickhouse-hostname-resolution.md` | Archive human-authored debug notes instead of deleting them |
| `docs/debug/DEBUG-history-export-empty-positions.md` | Moved to `docs/archive/debug/DEBUG-history-export-empty-positions.md` | Archive human-authored debug notes instead of deleting them |
| `docs/debug/DEBUG-llm-bundle-manifest-precedence.md` | Moved to `docs/archive/debug/DEBUG-llm-bundle-manifest-precedence.md` | Archive human-authored debug notes instead of deleting them |
| `docs/debug/DEBUG-market-metadata-backfill-conflicts.md` | Moved to `docs/archive/debug/DEBUG-market-metadata-backfill-conflicts.md` | Archive human-authored debug notes instead of deleting them |
| `docs/debug/DEBUG-windows-permissionerror-pytest-tempdirs.md` | Moved to `docs/archive/debug/DEBUG-windows-permissionerror-pytest-tempdirs.md` | Archive human-authored debug notes instead of deleting them |
| `docs/debug/unknown_resolution_diagnosis.md` | Moved to `docs/archive/debug/unknown_resolution_diagnosis.md` | Archive human-authored debug notes instead of deleting them |
| `.codex_tmp_artifacts_audit.sh` | Moved to `quarantine/repo-root/.codex_tmp_artifacts_audit.sh` | Quarantine stray root temp script instead of leaving it at repo root |
| `build/` | Deleted | Generated build output in approved safe batch |
| `polytool.egg-info/` | Deleted | Generated packaging metadata in approved safe batch |
| `.sandboxtmp/` | Deleted | Generated sandbox junk in approved safe batch |
| `.tmp/pytest-basetemp/` | Partially deleted | Reduced from 984 top-level child dirs to 2; final removal blocked by persistent `Access is denied` on exact nested temp paths |
| `.tmp/pip-build-tracker-fcy4ypmd` | Not deleted | Persistent `Access is denied` on exact approved path |
| `.tmp/pip-ephem-wheel-cache-_rgr5nmi` | Not deleted | Persistent `Access is denied` on exact approved path |
| `.tmp/pip-wheel-fn9s3qb3` | Not deleted | Persistent `Access is denied` on exact approved path |

## References updated

Only direct path references that would break after the archive move were updated.

| File | Change |
|------|--------|
| `docs/README.md` | `debug/DEBUG-windows-permissionerror-pytest-tempdirs.md` -> `archive/debug/DEBUG-windows-permissionerror-pytest-tempdirs.md` |
| `docs/features/FEATURE-polymarket-taxonomy-ingestion.md` | `docs/debug/DEBUG-category-coverage-zero.md` -> `docs/archive/debug/DEBUG-category-coverage-zero.md` |
| `docs/pdr/PDR-ROADMAP4-WRAPUP.md` | `docs/debug/DEBUG-category-coverage-zero.md` -> `docs/archive/debug/DEBUG-category-coverage-zero.md` |
| `docs/pdr/PDR-ROADMAP4-WRAPUP.md` | `docs/debug/DEBUG-history-export-empty-positions.md` -> `docs/archive/debug/DEBUG-history-export-empty-positions.md` |

No files under `docs/obsidian-vault/**`, `docs/reference/**`, `docs/roadmaps/**`,
`docs/CURRENT_STATE.md`, `kill_switch.json`, `docker-compose.yml`,
`.claude/`, `.planning/`, `.gemini/`, `.opencode/`, `artifacts/`,
`docker_data/`, or `.venv/` were intentionally modified by this cleanup task.

## Commands run + relevant output

### Boundary and context reads

Commands:

```powershell
Get-Content docs/adr/0014-public-docs-surface-and-repo-hygiene-boundaries.md
Get-Content docs/README.md
Get-Content docs/INDEX.md
Get-Content docs/dev_logs/2026-04-10_repo_cleanup_policy_foundation.md
```

Relevant result: confirmed ADR-0014 is the governing cleanup boundary, that
`README.md` and `INDEX.md` are navigation-only, and that the prior cleanup pass
was intentionally non-destructive.

### Reference search before moves

Command:

```powershell
git grep -n -e 'DEBUG-category-coverage-zero.md' `
             -e 'DEBUG-clickhouse-hostname-resolution.md' `
             -e 'DEBUG-history-export-empty-positions.md' `
             -e 'DEBUG-llm-bundle-manifest-precedence.md' `
             -e 'DEBUG-market-metadata-backfill-conflicts.md' `
             -e 'DEBUG-windows-permissionerror-pytest-tempdirs.md' `
             -e 'unknown_resolution_diagnosis.md' `
  -- . ':!docs/obsidian-vault/**' ':!docs/dev_logs/**' ':!docs/reference/**' `
     ':!.claude/**' ':!.planning/**' ':!.gemini/**' ':!.opencode/**'
```

Output:

```text
docs/README.md:69:- [Debug: Windows pytest PermissionError tempdirs](debug/DEBUG-windows-permissionerror-pytest-tempdirs.md)
docs/features/FEATURE-polymarket-taxonomy-ingestion.md:75:See `docs/debug/DEBUG-category-coverage-zero.md` for the full root-cause analysis
docs/pdr/PDR-ROADMAP4-WRAPUP.md:69:- Debug: `docs/debug/DEBUG-category-coverage-zero.md`
docs/pdr/PDR-ROADMAP4-WRAPUP.md:97:- Debug: `docs/debug/DEBUG-history-export-empty-positions.md`
```

### Archive + quarantine moves

Commands:

```powershell
New-Item -ItemType Directory -Force -Path docs/archive/debug
New-Item -ItemType Directory -Force -Path quarantine/repo-root
Move-Item docs/debug/* docs/archive/debug/
Move-Item .codex_tmp_artifacts_audit.sh quarantine/repo-root/
```

Relevant output:

```text
MOVED ...\docs\debug\DEBUG-category-coverage-zero.md -> ...\docs\archive\debug\DEBUG-category-coverage-zero.md
MOVED ...\docs\debug\DEBUG-clickhouse-hostname-resolution.md -> ...\docs\archive\debug\DEBUG-clickhouse-hostname-resolution.md
MOVED ...\docs\debug\DEBUG-history-export-empty-positions.md -> ...\docs\archive\debug\DEBUG-history-export-empty-positions.md
MOVED ...\docs\debug\DEBUG-llm-bundle-manifest-precedence.md -> ...\docs\archive\debug\DEBUG-llm-bundle-manifest-precedence.md
MOVED ...\docs\debug\DEBUG-market-metadata-backfill-conflicts.md -> ...\docs\archive\debug\DEBUG-market-metadata-backfill-conflicts.md
MOVED ...\docs\debug\DEBUG-windows-permissionerror-pytest-tempdirs.md -> ...\docs\archive\debug\DEBUG-windows-permissionerror-pytest-tempdirs.md
MOVED ...\docs\debug\unknown_resolution_diagnosis.md -> ...\docs\archive\debug\unknown_resolution_diagnosis.md
MOVED ...\.codex_tmp_artifacts_audit.sh -> ...\quarantine\repo-root\.codex_tmp_artifacts_audit.sh
```

### Exact generated-junk deletion pass

Initial command:

```powershell
Remove-Item -LiteralPath build, polytool.egg-info, .sandboxtmp, .tmp/pytest-basetemp `
  -Recurse -Force
Remove-Item -LiteralPath .tmp/pip-build-tracker-fcy4ypmd, `
  .tmp/pip-ephem-wheel-cache-_rgr5nmi, .tmp/pip-wheel-fn9s3qb3 `
  -Recurse -Force
```

Relevant output:

```text
DELETED D:\Coding Projects\Polymarket\PolyTool\.sandboxtmp
DELETED D:\Coding Projects\Polymarket\PolyTool\build
DELETED D:\Coding Projects\Polymarket\PolyTool\polytool.egg-info
Remove-Item : Access to the path '...\ .tmp\pip-build-tracker-fcy4ypmd' is denied.
Remove-Item : Access to the path '...\ .tmp\pip-ephem-wheel-cache-_rgr5nmi' is denied.
Remove-Item : Access to the path '...\ .tmp\pip-wheel-fn9s3qb3' is denied.
Remove-Item : Access to the path '...\ .tmp\pytest-basetemp\081ea328...\wheelhouse\.tmp-1pulnpfh' is denied.
```

Follow-up retries attempted:

- direct `Remove-Item` outside the sandbox on the exact four remaining targets;
- `takeown.exe` + `icacls.exe` on the exact remaining targets;
- child-by-child deletion passes within `.tmp/pytest-basetemp`.

Relevant results:

```text
DELETED_CHILDREN=449
FAILED_CHILDREN=43
```

```text
DELETED_CHILDREN=41
FAILED_CHILDREN=2
```

The child-by-child retries reduced `.tmp/pytest-basetemp` from 984 top-level
children to 2 remaining top-level children, but the last nested temp nodes
still returned `Access is denied`.

## Verification results

### Requested verification commands

Commands:

```powershell
git status --short
git diff --stat
Get-ChildItem docs/archive/debug -Name | Sort-Object
Test-Path quarantine/repo-root/.codex_tmp_artifacts_audit.sh
Test-Path build
Test-Path polytool.egg-info
Test-Path .sandboxtmp
Test-Path .tmp/pip-build-tracker-fcy4ypmd
Test-Path .tmp/pip-ephem-wheel-cache-_rgr5nmi
Test-Path .tmp/pip-wheel-fn9s3qb3
Test-Path .tmp/pytest-basetemp
```

Relevant output:

```text
docs/archive/debug contains:
DEBUG-category-coverage-zero.md
DEBUG-clickhouse-hostname-resolution.md
DEBUG-history-export-empty-positions.md
DEBUG-llm-bundle-manifest-precedence.md
DEBUG-market-metadata-backfill-conflicts.md
DEBUG-windows-permissionerror-pytest-tempdirs.md
unknown_resolution_diagnosis.md

quarantine/repo-root/.codex_tmp_artifacts_audit.sh = TRUE

build=False
polytool.egg-info=False
.sandboxtmp=False
.tmp/pip-build-tracker-fcy4ypmd=True
.tmp/pip-ephem-wheel-cache-_rgr5nmi=True
.tmp/pip-wheel-fn9s3qb3=True
.tmp/pytest-basetemp=True

docs/debug child count = 0
```

### Interpretation

- PASS: all files from `docs/debug/` were moved to `docs/archive/debug/`.
- PASS: the stray temp script was quarantined under
  `quarantine/repo-root/.codex_tmp_artifacts_audit.sh`.
- PASS: `build/`, `polytool.egg-info/`, and `.sandboxtmp/` no longer exist.
- PASS: direct path references that would have broken after the move were updated.
- PASS: `docs/debug/` no longer contains files.
- NOTE: raw `git status --short` and `git diff --stat` are noisy because the
  repo already had unrelated dirty work under `.claude/`, `docs/obsidian-vault/`,
  `infra/`, and other out-of-scope paths before this cleanup.
- NOTE: `git diff --name-only -- docs/obsidian-vault` still reports
  `docs/obsidian-vault/.obsidian/graph.json` and
  `docs/obsidian-vault/.obsidian/workspace.json`, but those are pre-existing
  out-of-scope repo changes; this cleanup task did not target or edit the vault.

## Anything skipped and why

The following exact approved cleanup targets remain because repeated direct
deletion, elevated deletion, and ACL-reset retries all failed with persistent
Windows `Access is denied` errors:

- `.tmp/pip-build-tracker-fcy4ypmd`
- `.tmp/pip-ephem-wheel-cache-_rgr5nmi`
- `.tmp/pip-wheel-fn9s3qb3`
- `.tmp/pytest-basetemp`

The exact nested blocker nodes observed during final retries were:

- `.tmp/pytest-basetemp/081ea328a47145a79ef75f8d6acd0cc4/test_packaged_schema_resource_0/wheelhouse/.tmp-1pulnpfh`
- `.tmp/pytest-basetemp/448147343a3a44b7865754fa5593c1e5/test_packaged_schema_resource_0/pip-tmp/pip-build-tracker-wfg8pux8`
- `.tmp/pytest-basetemp/448147343a3a44b7865754fa5593c1e5/test_packaged_schema_resource_0/pip-tmp/pip-ephem-wheel-cache-q55fb4jg`
- `.tmp/pytest-basetemp/448147343a3a44b7865754fa5593c1e5/test_packaged_schema_resource_0/pip-tmp/pip-install-lbnu1ipx`
- `.tmp/pytest-basetemp/448147343a3a44b7865754fa5593c1e5/test_packaged_schema_resource_0/pip-tmp/pip-target-0z77sx31`

No broader `.tmp` cleanup was attempted, and no out-of-scope directories were
modified in order to work around those access-denied paths.
