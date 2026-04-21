# 2026-04-10 public docs surface cleanup phase2a

## Files moved and why

This pass moved only obviously typed support docs out of `docs/` root so the
root surface is slimmer and more aligned with ADR 0014.

### Moved to `docs/audits/`

| Old path | New path | Why |
|----------|----------|-----|
| `docs/CODEBASE_AUDIT.md` | `docs/audits/CODEBASE_AUDIT.md` | Clearly an audit artifact, not a first-class root doc |
| `docs/RAG_IMPLEMENTATION_REPORT.md` | `docs/audits/RAG_IMPLEMENTATION_REPORT.md` | Clearly an implementation audit/report |
| `docs/RIS_AUDIT_REPORT.md` | `docs/audits/RIS_AUDIT_REPORT.md` | Clearly a layer-by-layer audit artifact |

### Moved to `docs/reference/`

| Old path | New path | Why |
|----------|----------|-----|
| `docs/HYPOTHESIS_STANDARD.md` | `docs/reference/HYPOTHESIS_STANDARD.md` | Stable reference/standard document |
| `docs/RESEARCH_SOURCES.md` | `docs/reference/RESEARCH_SOURCES.md` | Stable reference list and policy surface |
| `docs/TRUST_ARTIFACTS.md` | `docs/reference/TRUST_ARTIFACTS.md` | Stable reference for artifact interpretation |

### Moved to `docs/runbooks/`

| Old path | New path | Why |
|----------|----------|-----|
| `docs/LLM_BUNDLE_WORKFLOW.md` | `docs/runbooks/LLM_BUNDLE_WORKFLOW.md` | Operator workflow/runbook |
| `docs/LOCAL_RAG_WORKFLOW.md` | `docs/runbooks/LOCAL_RAG_WORKFLOW.md` | Operator workflow/runbook |
| `docs/README_SIMTRADER.md` | `docs/runbooks/README_SIMTRADER.md` | Operator guide/runbook |
| `docs/RUNBOOK_MANUAL_EXAMINE.md` | `docs/runbooks/RUNBOOK_MANUAL_EXAMINE.md` | Operator runbook |
| `docs/WINDOWS_DEVELOPMENT_GOTCHAS.md` | `docs/runbooks/WINDOWS_DEVELOPMENT_GOTCHAS.md` | Operator/developer runbook |
| `docs/OPERATOR_QUICKSTART.md` | `docs/runbooks/OPERATOR_QUICKSTART.md` | Operator quickstart/runbook |
| `docs/OPERATOR_SETUP_GUIDE.md` | `docs/runbooks/OPERATOR_SETUP_GUIDE.md` | Operator setup runbook |
| `docs/PARTNER_DEPLOYMENT_GUIDE_docker.md` | `docs/runbooks/PARTNER_DEPLOYMENT_GUIDE_docker.md` | Deployment runbook |
| `docs/RIS_OPERATOR_GUIDE.md` | `docs/runbooks/RIS_OPERATOR_GUIDE.md` | Operator guide/runbook |

No redirect stub files were created at the old root paths.

## Backlinks updated

Direct references were updated on active, in-scope surfaces that would
otherwise strand on the old root paths.

### Navigation and public docs

- `docs/README.md`
- `docs/INDEX.md`
- `README.md`
- `docs/CURRENT_STATE.md`
- `docs/ARCHITECT_CONTEXT_PACK.md`
- `docs/PROJECT_CONTEXT_PUBLIC.md`
- `docs/PROJECT_OVERVIEW.md`
- `docs/TODO.md`
- `docs/pdr/PDR-ROADMAP4-WRAPUP.md`

### Runbooks and supporting docs

- `docs/runbooks/OPERATOR_SETUP_GUIDE.md`
- `docs/runbooks/OPERATOR_QUICKSTART.md`
- `docs/runbooks/WINDOWS_DEVELOPMENT_GOTCHAS.md`
- `docs/runbooks/LOCAL_RAG_WORKFLOW.md`
- `docs/runbooks/RUNBOOK_MANUAL_EXAMINE.md`
- `docs/runbooks/README_SIMTRADER.md`
- `docs/runbooks/RIS_OPERATOR_GUIDE.md`
- `docs/runbooks/RIS_N8N_OPERATOR_SOP.md`
- `docs/runbooks/RIS_N8N_SMOKE_TEST.md`
- `infra/n8n/README.md`

### Code / CLI / package surfaces

- `packages/polymarket/simtrader/README.md`
- `polytool/__main__.py`
- `tools/cli/research_health.py`
- `docs/eval/sample_queries.jsonl`

## Navigation changes made

- `docs/README.md` now surfaces the moved docs under explicit `Reference`,
  `Runbooks`, and `Audits` sections instead of presenting them as root docs.
- `docs/README.md` directory navigation now explicitly includes `audits/`,
  `reference/`, and `runbooks/`.
- `docs/INDEX.md` now lists moved docs under `Runbooks`, `Reference`, and
  `Audits`.
- `docs/INDEX.md` `Getting Started` now points to
  `runbooks/OPERATOR_QUICKSTART.md` and `runbooks/OPERATOR_SETUP_GUIDE.md`
  instead of implying those docs still live at the root.

## Commands run and relevant output

### Required context reads

Commands:

```powershell
Get-Content -Raw docs/adr/0014-public-docs-surface-and-repo-hygiene-boundaries.md
Get-Content -Raw docs/README.md
Get-Content -Raw docs/INDEX.md
Get-Content -Raw docs/PLAN_OF_RECORD.md
Get-Content -Raw docs/CURRENT_STATE.md
Get-Content -Raw docs/dev_logs/2026-04-10_repo_cleanup_policy_foundation.md
Get-Content -Raw docs/dev_logs/2026-04-10_kill_switch_contract_fix.md
```

Result:

- Confirmed ADR 0014 root-doc allowlist and non-destructive cleanup boundary.
- Confirmed `README.md` / `INDEX.md` are navigation only.
- Confirmed this pass should avoid vault edits and broader governance/roadmap
  reconciliation.

### Folder creation and moves

Command:

```powershell
New-Item -ItemType Directory -Force -Path docs/audits,docs/reference,docs/runbooks | Out-Null
Move-Item ... (15 scoped file moves)
```

Relevant output:

```text
MOVED docs/CODEBASE_AUDIT.md -> docs/audits/CODEBASE_AUDIT.md
MOVED docs/RAG_IMPLEMENTATION_REPORT.md -> docs/audits/RAG_IMPLEMENTATION_REPORT.md
MOVED docs/RIS_AUDIT_REPORT.md -> docs/audits/RIS_AUDIT_REPORT.md
MOVED docs/HYPOTHESIS_STANDARD.md -> docs/reference/HYPOTHESIS_STANDARD.md
MOVED docs/RESEARCH_SOURCES.md -> docs/reference/RESEARCH_SOURCES.md
MOVED docs/TRUST_ARTIFACTS.md -> docs/reference/TRUST_ARTIFACTS.md
MOVED docs/LLM_BUNDLE_WORKFLOW.md -> docs/runbooks/LLM_BUNDLE_WORKFLOW.md
MOVED docs/LOCAL_RAG_WORKFLOW.md -> docs/runbooks/LOCAL_RAG_WORKFLOW.md
MOVED docs/README_SIMTRADER.md -> docs/runbooks/README_SIMTRADER.md
MOVED docs/RUNBOOK_MANUAL_EXAMINE.md -> docs/runbooks/RUNBOOK_MANUAL_EXAMINE.md
MOVED docs/WINDOWS_DEVELOPMENT_GOTCHAS.md -> docs/runbooks/WINDOWS_DEVELOPMENT_GOTCHAS.md
MOVED docs/OPERATOR_QUICKSTART.md -> docs/runbooks/OPERATOR_QUICKSTART.md
MOVED docs/OPERATOR_SETUP_GUIDE.md -> docs/runbooks/OPERATOR_SETUP_GUIDE.md
MOVED docs/PARTNER_DEPLOYMENT_GUIDE_docker.md -> docs/runbooks/PARTNER_DEPLOYMENT_GUIDE_docker.md
MOVED docs/RIS_OPERATOR_GUIDE.md -> docs/runbooks/RIS_OPERATOR_GUIDE.md
```

### Required verification commands

Command:

```powershell
git status --short
```

Relevant output excerpt:

```text
 M README.md
 D docs/CODEBASE_AUDIT.md
 D docs/HYPOTHESIS_STANDARD.md
 M docs/INDEX.md
 D docs/LLM_BUNDLE_WORKFLOW.md
 D docs/LOCAL_RAG_WORKFLOW.md
 D docs/OPERATOR_QUICKSTART.md
 D docs/OPERATOR_SETUP_GUIDE.md
 D docs/PARTNER_DEPLOYMENT_GUIDE_docker.md
 D docs/RAG_IMPLEMENTATION_REPORT.md
 M docs/README.md
 D docs/README_SIMTRADER.md
 D docs/RESEARCH_SOURCES.md
 D docs/RIS_AUDIT_REPORT.md
 D docs/RIS_OPERATOR_GUIDE.md
 D docs/RUNBOOK_MANUAL_EXAMINE.md
 D docs/TRUST_ARTIFACTS.md
 D docs/WINDOWS_DEVELOPMENT_GOTCHAS.md
 ?? docs/audits/
 ?? docs/reference/HYPOTHESIS_STANDARD.md
 ?? docs/reference/RESEARCH_SOURCES.md
 ?? docs/reference/TRUST_ARTIFACTS.md
 ?? docs/runbooks/LLM_BUNDLE_WORKFLOW.md
 ?? docs/runbooks/LOCAL_RAG_WORKFLOW.md
 ?? docs/runbooks/OPERATOR_QUICKSTART.md
 ?? docs/runbooks/OPERATOR_SETUP_GUIDE.md
 ?? docs/runbooks/PARTNER_DEPLOYMENT_GUIDE_docker.md
 ?? docs/runbooks/README_SIMTRADER.md
 ?? docs/runbooks/RIS_OPERATOR_GUIDE.md
 ?? docs/runbooks/RUNBOOK_MANUAL_EXAMINE.md
 ?? docs/runbooks/WINDOWS_DEVELOPMENT_GOTCHAS.md
```

Interpretation: the requested status command confirms the root files are gone
from `docs/` and new typed-folder paths now exist. The command is noisy because
the worktree already contained unrelated pre-existing changes.

Command:

```powershell
git diff --stat
```

Relevant output excerpt:

```text
README.md                                          |    4 +-
docs/ARCHITECT_CONTEXT_PACK.md                     |   10 +-
docs/CODEBASE_AUDIT.md                             |  835 ------
docs/CURRENT_STATE.md                              |    6 +-
docs/HYPOTHESIS_STANDARD.md                        |  197 --
docs/INDEX.md                                      |   81 +-
docs/LLM_BUNDLE_WORKFLOW.md                        |   86 -
docs/LOCAL_RAG_WORKFLOW.md                         |  188 --
docs/OPERATOR_QUICKSTART.md                        |  386 ---
docs/OPERATOR_SETUP_GUIDE.md                       |  370 ---
docs/PARTNER_DEPLOYMENT_GUIDE_docker.md            |  183 --
docs/RAG_IMPLEMENTATION_REPORT.md                  |  157 --
docs/README.md                                     |  104 +-
docs/README_SIMTRADER.md                           |  434 ---
docs/RESEARCH_SOURCES.md                           |   73 -
docs/RIS_AUDIT_REPORT.md                           |  491 ----
docs/RIS_OPERATOR_GUIDE.md                         |  892 ------
docs/RUNBOOK_MANUAL_EXAMINE.md                     |  205 --
docs/TRUST_ARTIFACTS.md                            |  216 --
docs/WINDOWS_DEVELOPMENT_GOTCHAS.md                |  204 --
```

Interpretation: the diff shows root-path deletions for the moved docs plus the
navigation/backlink edits. The full repo-wide stat is also noisy because of
unrelated pre-existing worktree changes.

Command:

```powershell
git grep -n "docs/CODEBASE_AUDIT.md\|docs/RAG_IMPLEMENTATION_REPORT.md\|docs/RIS_AUDIT_REPORT.md\|docs/HYPOTHESIS_STANDARD.md\|docs/RESEARCH_SOURCES.md\|docs/TRUST_ARTIFACTS.md\|docs/LLM_BUNDLE_WORKFLOW.md\|docs/LOCAL_RAG_WORKFLOW.md\|docs/README_SIMTRADER.md\|docs/RUNBOOK_MANUAL_EXAMINE.md\|docs/WINDOWS_DEVELOPMENT_GOTCHAS.md\|docs/OPERATOR_QUICKSTART.md\|docs/OPERATOR_SETUP_GUIDE.md\|docs/PARTNER_DEPLOYMENT_GUIDE_docker.md\|docs/RIS_OPERATOR_GUIDE.md"
```

Relevant output categories:

- `.planning/**`
- `docs/dev_logs/**`
- `docs/specs/**`
- `docs/reference/POLYTOOL_MASTER_ROADMAP*`
- `docs/obsidian-vault/**`
- untouched authority/history docs such as `docs/PLAN_OF_RECORD.md`,
  `docs/ROADMAP.md`, and `docs/archive/**`

Interpretation: the exact repo-wide grep remains noisy because it includes
historical, planning, vault, and explicitly untouched authority surfaces.
That is expected under this pass boundary.

Command:

```powershell
Get-ChildItem docs/audits,docs/reference,docs/runbooks -File | Sort-Object DirectoryName,Name
```

Relevant output for the moved set:

```text
docs/audits/CODEBASE_AUDIT.md
docs/audits/RAG_IMPLEMENTATION_REPORT.md
docs/audits/RIS_AUDIT_REPORT.md
docs/reference/HYPOTHESIS_STANDARD.md
docs/reference/RESEARCH_SOURCES.md
docs/reference/TRUST_ARTIFACTS.md
docs/runbooks/LLM_BUNDLE_WORKFLOW.md
docs/runbooks/LOCAL_RAG_WORKFLOW.md
docs/runbooks/OPERATOR_QUICKSTART.md
docs/runbooks/OPERATOR_SETUP_GUIDE.md
docs/runbooks/PARTNER_DEPLOYMENT_GUIDE_docker.md
docs/runbooks/README_SIMTRADER.md
docs/runbooks/RIS_OPERATOR_GUIDE.md
docs/runbooks/RUNBOOK_MANUAL_EXAMINE.md
docs/runbooks/WINDOWS_DEVELOPMENT_GOTCHAS.md
```

### Supplemental validation

Command:

```powershell
git grep -n "docs/CODEBASE_AUDIT.md\|docs/RAG_IMPLEMENTATION_REPORT.md\|docs/RIS_AUDIT_REPORT.md\|docs/HYPOTHESIS_STANDARD.md\|docs/RESEARCH_SOURCES.md\|docs/TRUST_ARTIFACTS.md\|docs/LLM_BUNDLE_WORKFLOW.md\|docs/LOCAL_RAG_WORKFLOW.md\|docs/README_SIMTRADER.md\|docs/RUNBOOK_MANUAL_EXAMINE.md\|docs/WINDOWS_DEVELOPMENT_GOTCHAS.md\|docs/OPERATOR_QUICKSTART.md\|docs/OPERATOR_SETUP_GUIDE.md\|docs/PARTNER_DEPLOYMENT_GUIDE_docker.md\|docs/RIS_OPERATOR_GUIDE.md" -- . ':(exclude)docs/obsidian-vault/**' ':(exclude)docs/dev_logs/**' ':(exclude)docs/specs/**' ':(exclude)docs/features/**' ':(exclude)docs/reference/POLYTOOL_MASTER_ROADMAP*' ':(exclude).planning/**' ':(exclude).claude/**' ':(exclude)docs/PLAN_OF_RECORD.md' ':(exclude)docs/ROADMAP.md' ':(exclude)docs/archive/**'
```

Output:

```text
(no matches; command exited 1)
```

Interpretation: the active in-scope surface is clean after excluding the
explicitly untouched governance/history/planning/vault areas.

Command:

```powershell
$old = @(
  'docs/CODEBASE_AUDIT.md',
  'docs/RAG_IMPLEMENTATION_REPORT.md',
  'docs/RIS_AUDIT_REPORT.md',
  'docs/HYPOTHESIS_STANDARD.md',
  'docs/RESEARCH_SOURCES.md',
  'docs/TRUST_ARTIFACTS.md',
  'docs/LLM_BUNDLE_WORKFLOW.md',
  'docs/LOCAL_RAG_WORKFLOW.md',
  'docs/README_SIMTRADER.md',
  'docs/RUNBOOK_MANUAL_EXAMINE.md',
  'docs/WINDOWS_DEVELOPMENT_GOTCHAS.md',
  'docs/OPERATOR_QUICKSTART.md',
  'docs/OPERATOR_SETUP_GUIDE.md',
  'docs/PARTNER_DEPLOYMENT_GUIDE_docker.md',
  'docs/RIS_OPERATOR_GUIDE.md'
)
foreach ($p in $old) { '{0}={1}' -f $p, (Test-Path $p) }
```

Output:

```text
docs/CODEBASE_AUDIT.md=False
docs/RAG_IMPLEMENTATION_REPORT.md=False
docs/RIS_AUDIT_REPORT.md=False
docs/HYPOTHESIS_STANDARD.md=False
docs/RESEARCH_SOURCES.md=False
docs/TRUST_ARTIFACTS.md=False
docs/LLM_BUNDLE_WORKFLOW.md=False
docs/LOCAL_RAG_WORKFLOW.md=False
docs/README_SIMTRADER.md=False
docs/RUNBOOK_MANUAL_EXAMINE.md=False
docs/WINDOWS_DEVELOPMENT_GOTCHAS.md=False
docs/OPERATOR_QUICKSTART.md=False
docs/OPERATOR_SETUP_GUIDE.md=False
docs/PARTNER_DEPLOYMENT_GUIDE_docker.md=False
docs/RIS_OPERATOR_GUIDE.md=False
```

Command:

```powershell
git diff --name-only -- docs/obsidian-vault
```

Output:

```text
docs/obsidian-vault/.obsidian/graph.json
docs/obsidian-vault/.obsidian/workspace.json
```

Interpretation: the repo already had pre-existing vault diffs. This cleanup
pass did not intentionally touch `docs/obsidian-vault/**`.

## Validation results

- PASS: all 15 scoped docs were moved out of `docs/` root into typed folders.
- PASS: old root paths for the moved docs no longer exist.
- PASS: active in-scope backlink surfaces were updated to the new typed-folder
  paths.
- PASS: `docs/README.md` and `docs/INDEX.md` now present a slimmer root surface
  and list moved docs under `runbooks/`, `reference/`, and `audits/`.
- PASS: no redirect stub files were left at the old root paths.
- NOTE: the exact repo-wide grep still returns matches in intentionally
  untouched governance/history/planning/vault/spec surfaces.
- NOTE: the repo already had unrelated dirty worktree state, including
  `docs/obsidian-vault/.obsidian/graph.json` and
  `docs/obsidian-vault/.obsidian/workspace.json`.

## Intentionally deferred

Per the stated pass boundary, these surfaces were not edited even though the
exact repo-wide grep still mentions old paths:

- `docs/PLAN_OF_RECORD.md`
- `docs/ROADMAP.md`
- `docs/archive/**`
- `docs/dev_logs/**`
- `docs/specs/**`
- `docs/features/**`
- `docs/reference/POLYTOOL_MASTER_ROADMAP*`
- `.planning/**`
- `docs/obsidian-vault/**`

That leaves a later boundary-scoped pass to reconcile authority/history/path
references without mixing that work into this structural cleanup.
