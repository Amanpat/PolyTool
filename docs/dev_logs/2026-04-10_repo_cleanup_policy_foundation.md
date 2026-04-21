# 2026-04-10 repo cleanup policy foundation

## Files changed and why

| File | Change | Reason |
|------|--------|--------|
| `docs/adr/0014-public-docs-surface-and-repo-hygiene-boundaries.md` | Created | Durable cleanup contract: first-class root docs allowlist, authority chain, doc classes, keep/archive/quarantine/delete rules, and first-pass non-destructive boundary |
| `docs/README.md` | Updated | Converted into navigation-only surface; added first-class root docs list and explicit vault/dev-log boundary notes |
| `docs/INDEX.md` | Updated | Converted into navigation-only index; added first-class root docs table, ADR reference, and removed a dev log from primary workflow navigation |
| `docs/PLAN_OF_RECORD.md` | Updated | Normalized roadmap reference to v5.1 and approved repo hygiene as a non-destructive maintenance stream |
| `docs/CURRENT_STATE.md` | Updated | Normalized roadmap reference to v5.1 and recorded current docs-governance boundary as repo truth |
| `docs/reference/POLYTOOL_MASTER_ROADMAP_v5_1.md` | Updated | Added short docs-governance boundary note near the mandatory dev-log rule |
| `docs/dev_logs/2026-04-10_repo_cleanup_policy_foundation.md` | Created | Mandatory session log for this docs-governance task |

No code, tests, Docker files, infra files, archive moves, or vault content were edited by this task.

## Commands run + output

### Worktree baseline

Command:

```powershell
git status --short --branch
```

Relevant output:

```text
## main...origin/main [ahead 89]
 M docs/CURRENT_STATE.md
 M docs/INDEX.md
 M docs/PLAN_OF_RECORD.md
 M docs/README.md
 M docs/reference/POLYTOOL_MASTER_ROADMAP_v5_1.md
?? docs/adr/0014-public-docs-surface-and-repo-hygiene-boundaries.md
...
```

Note: the worktree was already dirty before this task. Unrelated modified or
untracked files existed under `.claude/`, `docs/obsidian-vault/`, `infra/`,
`packages/`, `tests/`, and other paths outside this docs-governance scope.

### Requested repo-wide diff stat

Command:

```powershell
git diff --stat
```

Observed output excerpt:

```text
docs/CURRENT_STATE.md                          |  13 ++-
docs/INDEX.md                                  |  30 +++++--
docs/PLAN_OF_RECORD.md                         |  31 +++++--
docs/README.md                                 |  62 +++++++++-----
docs/obsidian-vault/.obsidian/workspace.json   | 109 +++++++++++++++++++++----
docs/reference/POLYTOOL_MASTER_ROADMAP_v5_1.md |   6 ++
infra/n8n/import_workflows.py                  |  54 ++++++++++++
...
23 files changed, 254 insertions(+), 57 deletions(-)
```

Interpretation: the raw repo-wide diff is noisy because of pre-existing
unrelated changes outside this task.

### Scoped docs diff stat for this task

Command:

```powershell
git diff --stat -- docs/README.md docs/INDEX.md docs/PLAN_OF_RECORD.md docs/CURRENT_STATE.md docs/reference/POLYTOOL_MASTER_ROADMAP_v5_1.md docs/adr/0014-public-docs-surface-and-repo-hygiene-boundaries.md
```

Observed output:

```text
docs/CURRENT_STATE.md                          | 13 ++++--
docs/INDEX.md                                  | 30 ++++++++++---
docs/PLAN_OF_RECORD.md                         | 31 +++++++++----
docs/README.md                                 | 62 +++++++++++++++++---------
docs/reference/POLYTOOL_MASTER_ROADMAP_v5_1.md |  6 +++
5 files changed, 104 insertions(+), 38 deletions(-)
```

Note: `git diff` does not include the new untracked ADR file; that file appears
in `git status --short`.

### Requested roadmap-reference grep

Command:

```powershell
git grep -n -E "POLYTOOL_MASTER_ROADMAP_v5\.md|POLYTOOL_MASTER_ROADMAP_v5_1\.md" -- docs
```

Observed output excerpt:

```text
docs/CURRENT_STATE.md:9:Master Roadmap v5.1 (`docs/reference/POLYTOOL_MASTER_ROADMAP_v5_1.md`) is the
docs/INDEX.md:15:| [Master Roadmap v5.1](reference/POLYTOOL_MASTER_ROADMAP_v5_1.md) | Strategic roadmap and LLM policy |
docs/PLAN_OF_RECORD.md:7:Master Roadmap v5.1 (`docs/reference/POLYTOOL_MASTER_ROADMAP_v5_1.md`) is the
docs/README.md:28:4. [Master Roadmap v5.1](reference/POLYTOOL_MASTER_ROADMAP_v5_1.md)
docs/ARCHITECTURE.md:6:Master Roadmap v5 (`docs/reference/POLYTOOL_MASTER_ROADMAP_v5.md`) is the
docs/ROADMAP.md:3:Master Roadmap v5 (`docs/reference/POLYTOOL_MASTER_ROADMAP_v5.md`) is the
...
```

Interpretation: touched governance docs now point to `POLYTOOL_MASTER_ROADMAP_v5_1.md`.
Remaining `v5.md` references are in out-of-scope historical or secondary files
such as `docs/ARCHITECTURE.md`, `docs/ROADMAP.md`, archive, dev logs, and specs.

### Requested obsidian-vault grep

Command:

```powershell
git grep -n "obsidian-vault" -- docs
```

Observed output excerpt:

```text
docs/CURRENT_STATE.md:20:  remains preserved history; `docs/obsidian-vault/**` remains a separate
docs/INDEX.md:19:history, and `docs/obsidian-vault/` is a separate subsystem excluded from
docs/PLAN_OF_RECORD.md:32:- no rewrites under `docs/obsidian-vault/**`;
docs/README.md:32:preserved history, and `docs/obsidian-vault/` is a separate subsystem excluded
docs/reference/POLYTOOL_MASTER_ROADMAP_v5_1.md:280:> history, and `docs/obsidian-vault/` remains a separate subsystem excluded
docs/obsidian-vault/00-Index/Dashboard.md:9:Master Map of Content for the PolyTool Obsidian vault...
...
```

Interpretation: touched governance docs now declare the vault boundary. The
remaining hits are existing vault content, specs, and historical dev logs; this
task did not edit `docs/obsidian-vault/**`.

## Test results

- PASS: Created a durable policy artifact in `docs/adr/0014-public-docs-surface-and-repo-hygiene-boundaries.md`.
- PASS: `docs/README.md` and `docs/INDEX.md` now explicitly state that they are navigation surfaces only.
- PASS: Touched governance docs now use `docs/reference/POLYTOOL_MASTER_ROADMAP_v5_1.md`.
- PASS: The policy and governing docs explicitly state that `docs/obsidian-vault/**` is a separate subsystem excluded from public docs count goals.
- PASS: Dev logs are preserved and no longer surfaced as primary workflow navigation in `docs/INDEX.md`.
- NOTE: Raw `git diff --stat` does not satisfy the "only docs-governance files changed" expectation because the repo already contained unrelated modifications outside this task. The scoped docs diff for this task is clean.

## Decisions made

- Used an ADR, not a standalone reference doc, as the durable cleanup policy artifact.
- Defined the first-class public root surface as `README`, `INDEX`, `PLAN_OF_RECORD`, `ARCHITECTURE`, `STRATEGY_PLAYBOOK`, `reference/POLYTOOL_MASTER_ROADMAP_v5_1.md`, and `CURRENT_STATE`.
- Preserved the user-specified authority chain for docs-governance cleanup decisions: `PLAN_OF_RECORD` -> `ARCHITECTURE` -> `STRATEGY_PLAYBOOK` -> roadmap v5.1 -> `CURRENT_STATE`.
- Declared `README` and `INDEX` to have zero authority and limited them to navigation duties.
- Declared `docs/dev_logs/**` to be preserved historical record, not primary navigation.
- Declared `docs/obsidian-vault/**` to be a separate subsystem excluded from public docs count goals.
- Approved repo hygiene as a maintenance stream only when it remains non-destructive unless explicitly scoped otherwise.

## Open questions for cleanup implementation

- Should `docs/ARCHITECTURE.md` and `docs/ROADMAP.md` be normalized to v5.1 in a follow-up governance pass?
- Which non-allowlisted root docs should be the first archive or quarantine candidates after explicit review?
- Should public docs count goals include all surfaced runbooks and feature docs, or only a tighter curated subset?
- How should pre-existing local Obsidian workspace and plugin files be handled so repo-wide diff checks stop flagging unrelated vault metadata?
