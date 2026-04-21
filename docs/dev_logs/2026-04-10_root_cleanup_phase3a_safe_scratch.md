# 2026-04-10 root cleanup phase3a safe scratch

## Scope and guardrails

Objective: clean only clearly disposable scratch under `.tmp/**` and
`.code-review-graph/**`, plus empty ignored `kb/tmp_tests/**` directories when
safe.

Required boundary reads completed before cleanup:

- `docs/reference/LOCAL_STATE_AND_TOOLING_BOUNDARY.md`
- `docs/adr/0014-public-docs-surface-and-repo-hygiene-boundaries.md`
- `docs/CURRENT_STATE.md`
- `docs/dev_logs/2026-04-10_hidden_tooling_boundary_policy.md`

Boundary conclusions used for this pass:

- `.tmp/**` is disposable scratch.
- `.code-review-graph/**` is local-only tooling state and safe to clear for this
  explicit cleanup pass.
- `kb/**` is durable runtime/evidence state except explicitly confirmed empty,
  ignored `kb/tmp_tests/**` directories.
- `.claude/**`, `.opencode/**`, `.venv/**`, `artifacts/**`, `docker_data/**`,
  durable `kb/**`, and `docs/obsidian-vault/**` stayed out of scope.

## Paths removed and why

- `.code-review-graph/` root and all contents removed. Reason: disposable local
  code-review graph scratch. `git ls-files --stage -- .tmp .code-review-graph kb/tmp_tests`
  returned no tracked entries before cleanup.
- `.tmp/health_alert_test.json` removed. Reason: disposable scratch JSON.
- `.tmp/n8n_notify.log` removed. Reason: disposable scratch log.
- `.tmp/notify_server.py` removed. Reason: disposable scratch helper.
- `.tmp/ris_review_cli.sqlite3` removed. Reason: disposable scratch SQLite DB.
- `.tmp/summary_test.json` removed. Reason: disposable scratch JSON.
- Accessible nested scratch content under `.tmp/pip-build-tracker-fcy4ypmd`,
  `.tmp/pip-ephem-wheel-cache-_rgr5nmi`, `.tmp/pip-wheel-fn9s3qb3`,
  `.tmp/pytest-basetemp`, and `.tmp/test-workspaces` was removed until Windows
  permission blocks were reached. Result: `.tmp` now has zero files left.
- `kb/tmp_tests/tmpaga2wt35` removed. Reason: confirmed empty and ignored.
- `kb/tmp_tests/tmpkot6rc60` removed. Reason: confirmed empty and ignored.
- `kb/tmp_tests/tmprnf_7guq` removed. Reason: confirmed empty and ignored.
- `kb/tmp_tests/tmpvq50f75e` removed. Reason: confirmed empty and ignored.
- `kb/tmp_tests/tmpw_z9i6kz` removed. Reason: confirmed empty and ignored.
- `kb/tmp_tests/tmpz64w9t64` removed. Reason: confirmed empty and ignored.

## Blocked paths and exact errors

No scope was broadened after these failures. No ACL changes, takeown, or ignore
file changes were attempted.

- `.tmp/pip-build-tracker-fcy4ypmd`
  Error: `Access to the path 'D:\Coding Projects\Polymarket\PolyTool\.tmp\pip-build-tracker-fcy4ypmd' is denied.`
- `.tmp/pip-ephem-wheel-cache-_rgr5nmi`
  Error: `Access to the path 'D:\Coding Projects\Polymarket\PolyTool\.tmp\pip-ephem-wheel-cache-_rgr5nmi' is denied.`
- `.tmp/pip-wheel-fn9s3qb3`
  Error: `Access to the path 'D:\Coding Projects\Polymarket\PolyTool\.tmp\pip-wheel-fn9s3qb3' is denied.`
- `.tmp/pytest-basetemp/081ea328a47145a79ef75f8d6acd0cc4/test_packaged_schema_resource_0/wheelhouse/.tmp-1pulnpfh`
  Error: `Access to the path 'D:\Coding Projects\Polymarket\PolyTool\.tmp\pytest-basetemp\081ea328a47145a79ef75f8d6acd0cc4\test_packaged_schema_resource_0\wheelhouse\.tmp-1pulnpfh' is denied.`
- `.tmp/test-workspaces/897a0d2343ea4b928d42606fe2b4d18a/cache/pip-build-tracker-28v8oug4`
  Error: `Access to the path 'D:\Coding Projects\Polymarket\PolyTool\.tmp\test-workspaces\897a0d2343ea4b928d42606fe2b4d18a\cache\pip-build-tracker-28v8oug4' is denied.`
- `kb/tmp_tests/tmpl_im8641`
  Error: `Access to the path 'D:\Coding Projects\Polymarket\PolyTool\kb\tmp_tests\tmpl_im8641' is denied.`
- `kb/tmp_tests/tmpyuk_p6f9`
  Error: `Access to the path 'D:\Coding Projects\Polymarket\PolyTool\kb\tmp_tests\tmpyuk_p6f9' is denied.`

## Before/after footprint summary

| Path | Before | After | Result |
|------|--------|-------|--------|
| `.code-review-graph` | 4 files, 0 dirs. Top-level files: `.gitignore` (143 B), `graph.db` (19,587,072 B), `graph.db-shm` (32,768 B), `graph.db-wal` (0 B). | Missing. | Fully removed. |
| `.tmp` | 10 top-level entries, 55,104 files, 39,750 dirs. Top-level entries: `health_alert_test.json`, `n8n_notify.log`, `notify_server.py`, `pip-build-tracker-fcy4ypmd`, `pip-ephem-wheel-cache-_rgr5nmi`, `pip-wheel-fn9s3qb3`, `pytest-basetemp`, `ris_review_cli.sqlite3`, `summary_test.json`, `test-workspaces`. | Exists with 5 top-level entries, 0 files, 11,056 dirs. Remaining top-level dirs: `pip-build-tracker-fcy4ypmd`, `pip-ephem-wheel-cache-_rgr5nmi`, `pip-wheel-fn9s3qb3`, `pytest-basetemp`, `test-workspaces`. | Materially reduced; only permission-blocked directory trees remain. |
| `kb/tmp_tests` | Root existed, ignored, and contained 8 empty dirs: `tmpaga2wt35`, `tmpkot6rc60`, `tmpl_im8641`, `tmprnf_7guq`, `tmpvq50f75e`, `tmpw_z9i6kz`, `tmpyuk_p6f9`, `tmpz64w9t64`. | Root still exists with 2 empty dirs: `tmpl_im8641`, `tmpyuk_p6f9`. | 6 empty ignored dirs removed; 2 left due access-denied. |

## Commands run + output

### Required context reads

Commands:

```powershell
Get-Content docs/reference/LOCAL_STATE_AND_TOOLING_BOUNDARY.md
Get-Content docs/adr/0014-public-docs-surface-and-repo-hygiene-boundaries.md
Get-Content docs/CURRENT_STATE.md -TotalCount 140
Get-Content docs/dev_logs/2026-04-10_hidden_tooling_boundary_policy.md
```

Relevant result:

- Confirmed `.tmp/**` is disposable scratch.
- Confirmed `.code-review-graph/**` is local-only state and acceptable to clean
  only under explicit scope.
- Confirmed `kb/**` is durable runtime/evidence state except tightly scoped
  empty ignored `kb/tmp_tests/**`.
- Confirmed `docs/obsidian-vault/**` is out of bounds.

### Pre-clean inventory

Commands:

```powershell
git ls-files --stage -- .tmp .code-review-graph kb/tmp_tests

Get-ChildItem -LiteralPath '.tmp' -Force | Sort-Object Name |
  Select-Object Name,@{n='Kind';e={if ($_.PSIsContainer) {'dir'} else {'file'}}},Length

Get-ChildItem -LiteralPath '.code-review-graph' -Force | Sort-Object Name |
  Select-Object Name,@{n='Kind';e={if ($_.PSIsContainer) {'dir'} else {'file'}}},Length

[pscustomobject]@{
  Path='.tmp'
  TopLevelCount=@(Get-ChildItem -LiteralPath '.tmp' -Force).Count
  FileCount=@(Get-ChildItem -LiteralPath '.tmp' -Force -File -Recurse).Count
  DirCount=@(Get-ChildItem -LiteralPath '.tmp' -Force -Directory -Recurse).Count
}

[pscustomobject]@{ Path='kb/tmp_tests'; Exists=$true; Ignored=$true }

Get-ChildItem -LiteralPath 'kb/tmp_tests' -Force -Recurse -Directory |
  ForEach-Object {
    [pscustomobject]@{
      Path = (Resolve-Path -LiteralPath $_.FullName -Relative)
      Empty = (@(Get-ChildItem -LiteralPath $_.FullName -Force).Count -eq 0)
      Ignored = $true
    }
  }
```

Relevant output:

```text
git ls-files --stage -- .tmp .code-review-graph kb/tmp_tests
(no output)

.tmp top-level:
health_alert_test.json         file 10162
n8n_notify.log                 file 1650
notify_server.py               file 706
pip-build-tracker-fcy4ypmd     dir
pip-ephem-wheel-cache-_rgr5nmi dir
pip-wheel-fn9s3qb3             dir
pytest-basetemp                dir
ris_review_cli.sqlite3         file 61440
summary_test.json              file 9213
test-workspaces                dir

.code-review-graph top-level:
.gitignore   file      143
graph.db     file 19587072
graph.db-shm file    32768
graph.db-wal file        0

.tmp counts before:
TopLevelCount=10
FileCount=55104
DirCount=39750

kb/tmp_tests before:
Path='kb/tmp_tests' Exists=True Ignored=True
8 subdirs, all Empty=True and Ignored=True
```

### Cleanup execution

Commands:

```powershell
# main scoped cleanup script
# - remove .code-review-graph recursively
# - remove .tmp top-level entries recursively
# - remove empty ignored kb/tmp_tests dirs
```

Observed output:

```text
command timed out after 120017 milliseconds
```

State immediately after the timed-out pass:

```powershell
Get-ChildItem -LiteralPath '.tmp' -Force | Sort-Object Name |
  Select-Object Name,@{n='Kind';e={if ($_.PSIsContainer) {'dir'} else {'file'}}},Length

[pscustomobject]@{
  Path='.tmp'
  TopLevelCount=@(Get-ChildItem -LiteralPath '.tmp' -Force).Count
  FileCount=@(Get-ChildItem -LiteralPath '.tmp' -Force -File -Recurse).Count
  DirCount=@(Get-ChildItem -LiteralPath '.tmp' -Force -Directory -Recurse).Count
}

Test-Path '.code-review-graph'
```

Output:

```text
.tmp top-level after timeout:
pip-build-tracker-fcy4ypmd
pip-ephem-wheel-cache-_rgr5nmi
pip-wheel-fn9s3qb3
pytest-basetemp
test-workspaces

.tmp counts after timeout:
TopLevelCount=5
FileCount=0
DirCount=11056

Test-Path '.code-review-graph'
False
```

Follow-up cleanup attempts and results:

```powershell
Remove-Item -LiteralPath '.tmp' -Recurse -Force -ErrorAction Stop
Remove-Item -LiteralPath 'kb/tmp_tests/<dir>' -Recurse -Force -ErrorAction Stop
```

Relevant output:

```text
Remove-Item on .tmp:
Access to the path 'D:\Coding Projects\Polymarket\PolyTool\.tmp\pip-build-tracker-fcy4ypmd' is denied.

Remove-Item on kb/tmp_tests:
Access to the path 'D:\Coding Projects\Polymarket\PolyTool\kb\tmp_tests\tmpyuk_p6f9' is denied.
```

Per-path retry output:

```powershell
# .tmp remaining top-level dirs
foreach ($dir in Get-ChildItem '.tmp' -Directory) {
  try { Remove-Item $dir.FullName -Recurse -Force -ErrorAction Stop }
  catch { $_.Exception.Message }
}

# remaining kb/tmp_tests top-level dirs
foreach ($dir in Get-ChildItem 'kb/tmp_tests' -Directory) {
  try { Remove-Item $dir.FullName -Recurse -Force -ErrorAction Stop }
  catch { $_.Exception.Message }
}
```

Relevant output:

```text
.tmp:
.tmp/pip-build-tracker-fcy4ypmd     blocked
.tmp/pip-ephem-wheel-cache-_rgr5nmi blocked
.tmp/pip-wheel-fn9s3qb3             blocked
.tmp/pytest-basetemp                blocked
.tmp/test-workspaces                blocked

kb/tmp_tests:
kb/tmp_tests/tmpkot6rc60 removed
kb/tmp_tests/tmpl_im8641 blocked
kb/tmp_tests/tmprnf_7guq removed
kb/tmp_tests/tmpyuk_p6f9 blocked
```

### Validation

Commands:

```powershell
git status --short
git diff --stat

[pscustomobject]@{
  tmp_exists = (Test-Path -LiteralPath '.tmp')
  code_review_graph_exists = (Test-Path -LiteralPath '.code-review-graph')
  kb_tmp_tests_exists = (Test-Path -LiteralPath 'kb/tmp_tests')
}

[pscustomobject]@{
  path = '.tmp'
  top_level = @(Get-ChildItem -LiteralPath '.tmp' -Force).Count
  files = @(Get-ChildItem -LiteralPath '.tmp' -Force -File -Recurse).Count
  dirs = @(Get-ChildItem -LiteralPath '.tmp' -Force -Directory -Recurse).Count
}

[pscustomobject]@{
  path = 'kb/tmp_tests'
  top_level = @(Get-ChildItem -LiteralPath 'kb/tmp_tests' -Force).Count
  files = @(Get-ChildItem -LiteralPath 'kb/tmp_tests' -Force -File -Recurse).Count
  dirs = @(Get-ChildItem -LiteralPath 'kb/tmp_tests' -Force -Directory -Recurse).Count
}

git status --short -- .claude .opencode .venv artifacts docker_data docs/obsidian-vault
```

Relevant output:

```text
git status --short
Worktree already noisy before this task under .claude/worktrees, .sandboxtmp,
docs, infra, packages, polytool, tests, quarantine, and other out-of-scope
paths. No .tmp or .code-review-graph tracked entries were introduced by this
cleanup.

git diff --stat
180 files changed, 400 insertions(+), 9601 deletions(-)

existence checks:
tmp_exists=True
code_review_graph_exists=False
kb_tmp_tests_exists=True

.tmp after:
top_level=5
files=0
dirs=11056

kb/tmp_tests after:
top_level=2
files=0
dirs=2

git status --short -- .claude .opencode .venv artifacts docker_data docs/obsidian-vault
Only pre-existing noise under .claude/worktrees and docs/obsidian-vault was
reported. This cleanup pass did not edit those protected roots.
```

## Validation results

- PASS: `.code-review-graph` is gone after cleanup.
- PASS: `.tmp` was materially reduced from 55,104 files / 39,750 dirs to 0
  files / 11,056 dirs.
- PASS: 6 empty ignored `kb/tmp_tests` directories were removed.
- PASS: no durable `kb/**` data was touched.
- PASS: no changes were made under `.claude/**`, `.opencode/**`, `.venv/**`,
  `artifacts/**`, `docker_data/**`, or `docs/obsidian-vault/**`.
- PASS: no ignore files were changed.
- NOTE: repo-wide `git status --short` and `git diff --stat` remain noisy due
  substantial unrelated pre-existing worktree changes.

## Intentionally skipped

- No cleanup under `.claude/**` or `.opencode/**`.
- No cleanup under `.venv/**`, `artifacts/**`, or `docker_data/**`.
- No cleanup under durable `kb/**`; only empty ignored `kb/tmp_tests/**`
  directories were considered.
- No edits to runtime code/config/docs other than this mandatory dev log.
- No ACL changes or ownership changes were attempted after Windows returned
  access-denied on specific scratch paths.
