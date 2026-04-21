# 2026-04-10 hidden tooling boundary policy

## Files changed and why

| File | Change | Reason |
|------|--------|--------|
| `docs/reference/LOCAL_STATE_AND_TOOLING_BOUNDARY.md` | Created | Durable root-boundary policy for hidden tooling, local workspace state, runtime evidence/state, scratch, and repo-cleanliness exclusions |
| `docs/README.md` | Updated | Added discovery links to the new root-boundary policy from primary docs navigation |
| `docs/INDEX.md` | Updated | Added discovery links to the new root-boundary policy from the quick-reference index |
| `docs/CURRENT_STATE.md` | Updated | Recorded that the hidden tooling/local-state boundary now exists and that repo-cleanliness expectations exclude those roots unless a task targets them |
| `docs/dev_logs/2026-04-10_hidden_tooling_boundary_policy.md` | Created | Mandatory session log for this policy-only pass |

No hidden/local roots, `docs/obsidian-vault/**`, runtime code/config, or ignore
files were edited by this task.

## Policy decisions made

- ADR 0014 remains the authority for public docs surface. The new reference doc
  complements ADR 0014; it does not replace it.
- Public repo surface remains the normal committed collaboration surface:
  `docs/`, `infra/`, `packages/`, `polytool/`, `services/`, `tools/`, `tests/`,
  `scripts/`, `config/`, `workflows/`, `.github/`, `.githooks/`, and committed
  root manifests/examples.
- Stable shared tooling definitions inside hidden roots count as public repo
  surface when intentionally changed. This includes repo-shared prompt/agent/
  command/hook content under `.claude/**`, `.gemini/**`, and `.opencode/**`.
- Local-only tooling/workspace state does not count toward repo cleanliness by
  default. This includes `.claude/worktrees/**`, `.claude/settings.local.json`,
  `.planning/**`, `.code-review-graph/**`, `.venv/**`, and nested local
  install/cache folders such as `.opencode/node_modules/**`.
- Runtime evidence/state does not count toward repo cleanliness by default.
  This includes `artifacts/**`, `kb/**`, and `docker_data/**`.
- Disposable scratch/quarantine does not count toward repo cleanliness by
  default. This includes `.tmp/**`, `.sandboxtmp/**`, `quarantine/**`, and
  generated temp/build roots such as `build/`, `polytool.egg-info/`, pip temp
  dirs, and pytest temp dirs.
- Raw `git status` is not treated as a cleanliness metric by itself when these
  excluded roots are present. Validation should separate `public-surface drift`
  from excluded local-state/runtime noise.

## Commands run + output

### Required context reads

Commands:

```powershell
Get-Content docs/adr/0014-public-docs-surface-and-repo-hygiene-boundaries.md
Get-Content docs/README.md
Get-Content docs/INDEX.md
Get-Content docs/PLAN_OF_RECORD.md
Get-Content docs/CURRENT_STATE.md
Get-Content docs/dev_logs/2026-04-10_repo_cleanup_policy_foundation.md
Get-Content docs/dev_logs/2026-04-10_repo_cleanup_phase1_safe_batch.md
Get-Content docs/dev_logs/2026-04-10_public_docs_surface_cleanup_phase2a.md
```

Relevant result:

- Confirmed ADR 0014 is the governing public-doc boundary.
- Confirmed `docs/README.md` and `docs/INDEX.md` are navigation-only surfaces.
- Confirmed prior cleanup passes already encountered noisy repo-wide diff/status
  because of pre-existing hidden-root, runtime-state, and vault churn.

### Root inventory and classification inputs

Commands:

```powershell
Get-ChildItem -Force -Name
Get-ChildItem -Force .claude -Name
Get-ChildItem -Force .planning -Name
Get-ChildItem -Force .tmp -Name
Get-ChildItem -Force .gemini -Name
Get-ChildItem -Force .opencode -Name
Get-ChildItem -Force .code-review-graph -Name
Get-ChildItem -Force artifacts -Name | Select-Object -First 20
Get-ChildItem -Force kb -Name | Select-Object -First 20
Get-ChildItem -Force docker_data -Name
git ls-files .claude .code-review-graph .gemini .opencode .planning .tmp .venv artifacts docker_data kb quarantine .mcp.json .claudeignore .dockerignore .env.example .githooks .github
```

Relevant output:

```text
repo-root hidden/local candidates:
.claude
.code-review-graph
.gemini
.opencode
.planning
.tmp
.venv
artifacts
docker_data
kb
quarantine

.claude:
agents
commands
get-shit-done
hooks
skills
worktrees
gsd-file-manifest.json
package.json
settings.json
settings.local.json

.planning:
codebase
phases
quick
config.json
PROJECT.md
ROADMAP.md
STATE.md

.tmp:
pip-build-tracker-fcy4ypmd
pip-ephem-wheel-cache-_rgr5nmi
pip-wheel-fn9s3qb3
pytest-basetemp
test-workspaces
health_alert_test.json
n8n_notify.log
notify_server.py
ris_review_cli.sqlite3
summary_test.json

.code-review-graph:
.gitignore
graph.db
graph.db-shm
graph.db-wal

artifacts:
benchmark
corpus_audit
crypto_pairs
debug
dossiers
gates
imports
manual_verify
market_selection
research
simtrader
tapes
watchlists

kb:
dev
devlog
experiments
incidents
rag
research_dumps
specs
tmp_tests
users
.gitkeep
README.md

docker_data:
live
paper
.gitkeep
```

Interpretation:

- The repo contains mixed hidden roots: some hold stable shared tooling
  definitions, while others hold clearly local per-session state, caches, and
  runtime evidence.
- `git ls-files` confirmed that several hidden roots already contain tracked
  shared tooling content, so the policy must split stable tooling surface from
  volatile local state instead of labeling every dot-root the same way.

### Required validation

Commands:

```powershell
git diff --stat
git status --short
Select-String -Path docs\README.md,docs\INDEX.md -Pattern 'LOCAL_STATE_AND_TOOLING_BOUNDARY'
git diff --stat -- docs/README.md docs/INDEX.md docs/CURRENT_STATE.md docs/reference/LOCAL_STATE_AND_TOOLING_BOUNDARY.md
git status --short -- docs/README.md docs/INDEX.md docs/CURRENT_STATE.md docs/reference/LOCAL_STATE_AND_TOOLING_BOUNDARY.md
git status --short -- docs/README.md docs/INDEX.md docs/CURRENT_STATE.md docs/reference/LOCAL_STATE_AND_TOOLING_BOUNDARY.md docs/dev_logs/2026-04-10_hidden_tooling_boundary_policy.md
git status --short -- docs/obsidian-vault
Test-Path docs/reference/LOCAL_STATE_AND_TOOLING_BOUNDARY.md
Test-Path docs/dev_logs/2026-04-10_hidden_tooling_boundary_policy.md
```

Relevant output:

```text
git diff --stat
180 files changed, 400 insertions(+), 9601 deletions(-)

git status --short
(noisy pre-existing output under .claude/worktrees, .sandboxtmp, docs/debug,
docs/obsidian-vault, infra, packages, tests, and other out-of-scope paths)

Select-String -Path docs\README.md,docs\INDEX.md -Pattern 'LOCAL_STATE_AND_TOOLING_BOUNDARY'
docs\README.md:9:[Local State and Tooling Boundary](reference/LOCAL_STATE_AND_TOOLING_BOUNDARY.md).
docs\README.md:69:- [Local state and tooling boundary](reference/LOCAL_STATE_AND_TOOLING_BOUNDARY.md) - ...
docs\README.md:102:- [Local State and Tooling Boundary](reference/LOCAL_STATE_AND_TOOLING_BOUNDARY.md) - ...
docs\INDEX.md:8:[Local State and Tooling Boundary](reference/LOCAL_STATE_AND_TOOLING_BOUNDARY.md).
docs\INDEX.md:85:| [Local State and Tooling Boundary](reference/LOCAL_STATE_AND_TOOLING_BOUNDARY.md) | ... |

git diff --stat -- docs/README.md docs/INDEX.md docs/CURRENT_STATE.md docs/reference/LOCAL_STATE_AND_TOOLING_BOUNDARY.md
docs/CURRENT_STATE.md |  18 +++++---
docs/INDEX.md         |  88 +++++++++++++++++++++++++++------------
docs/README.md        | 112 ++++++++++++++++++++++++++++++++++----------------
3 files changed, 149 insertions(+), 69 deletions(-)

git status --short -- docs/README.md docs/INDEX.md docs/CURRENT_STATE.md docs/reference/LOCAL_STATE_AND_TOOLING_BOUNDARY.md
 M docs/CURRENT_STATE.md
 M docs/INDEX.md
 M docs/README.md
?? docs/reference/LOCAL_STATE_AND_TOOLING_BOUNDARY.md

git status --short -- docs/README.md docs/INDEX.md docs/CURRENT_STATE.md docs/reference/LOCAL_STATE_AND_TOOLING_BOUNDARY.md docs/dev_logs/2026-04-10_hidden_tooling_boundary_policy.md
 M docs/CURRENT_STATE.md
 M docs/INDEX.md
 M docs/README.md
?? docs/dev_logs/2026-04-10_hidden_tooling_boundary_policy.md
?? docs/reference/LOCAL_STATE_AND_TOOLING_BOUNDARY.md

git status --short -- docs/obsidian-vault
 M docs/obsidian-vault/.obsidian/graph.json
 M docs/obsidian-vault/.obsidian/workspace.json
 ?? docs/obsidian-vault/.obsidian/plugins/calendar/
 ?? docs/obsidian-vault/.obsidian/plugins/obsidian-kanban/
 ...

Test-Path docs/reference/LOCAL_STATE_AND_TOOLING_BOUNDARY.md
True

Test-Path docs/dev_logs/2026-04-10_hidden_tooling_boundary_policy.md
True
```

Interpretation:

- The required repo-wide `git diff --stat` and `git status --short` are noisy
  because the worktree already contained unrelated changes outside this task.
- The scoped docs status is clean for this pass: only `docs/README.md`,
  `docs/INDEX.md`, `docs/CURRENT_STATE.md`, the new policy doc, and this new
  dev log were in the touched set at validation time.
- The scoped `git diff --stat` does not include the new untracked policy doc;
  that file is confirmed separately by `git status --short` and `Test-Path`.
- Vault drift is still present in the raw worktree, but it pre-existed and this
  policy pass did not edit `docs/obsidian-vault/**`.

## Validation results

- PASS: created `docs/reference/LOCAL_STATE_AND_TOOLING_BOUNDARY.md`.
- PASS: linked the new policy from both `docs/README.md` and `docs/INDEX.md`.
- PASS: added a short current-state note that the hidden tooling/local-state
  boundary now exists.
- PASS: no roots were moved or deleted by this task.
- PASS: no files under `docs/obsidian-vault/**` were edited by this task.
- PASS: no runtime code/config files were edited by this task.
- NOTE: raw repo-wide diff/status still show substantial unrelated worktree
  noise outside this task boundary.

## Open questions for actual cleanup implementation

- Should future cleanup tooling formalize a machine-readable exclusion set for
  cleanliness reports, for example `.claude/worktrees/**`, `.planning/**`,
  `.tmp/**`, `artifacts/**`, `kb/**`, `docker_data/**`, `quarantine/**`, and
  `docs/obsidian-vault/**`?
- Should `.gemini/**` and `.opencode/**` get an explicit stable-vs-local
  subpath split in follow-up docs if those roots begin accumulating more local
  cache/runtime state?
- Should `quarantine/**` remain a separate cleanup holding area, or be folded
  into a later archive/disposal policy after explicit approval?
