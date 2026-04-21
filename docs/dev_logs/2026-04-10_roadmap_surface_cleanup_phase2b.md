# 2026-04-10 roadmap surface cleanup phase2b

## Files changed and why

| Path | Why |
|------|-----|
| `docs/ROADMAP.md` | Replaced the old authority-shaped milestone ledger with a short router that explicitly says it is non-governing and points readers to the governing roadmap, current state, and retained roadmap history |
| `docs/README.md` | Added explicit roadmap-surface labeling so the public docs hub treats Master Roadmap v5.1 as governing and `ROADMAP.md` as a secondary router |
| `docs/INDEX.md` | Aligned the quick-reference index with the same roadmap contract and surfaced `ROADMAP.md` only as a labeled router |
| `docs/PLAN_OF_RECORD.md` | Reinforced the authority chain at the top of the document and relabeled the `ROADMAP.md` cross-reference as non-governing |
| `docs/CURRENT_STATE.md` | Clarified that `docs/ROADMAP.md` is a non-governing router/operator surface, while this file remains implemented truth |
| `docs/reference/POLYTOOL_MASTER_ROADMAP_v5_1.md` | Added a tiny boundary note so the governing roadmap identifies itself as the roadmap authority and points readers to `CURRENT_STATE.md` and the router companion |
| `docs/pdr/PDR-ROADMAP4-WRAPUP.md` | Retargeted a direct backlink that previously pointed to old `ROADMAP.md` section content |
| `docs/pdr/PDR-ROADMAP5-WRAPUP.md` | Retargeted a direct backlink that previously pointed to old `ROADMAP.md` section content |
| `docs/runbooks/OPERATOR_QUICKSTART.md` | Relabeled the quick-reference entry so it presents `docs/ROADMAP.md` as a router, not a governing roadmap |
| `docs/dev_logs/2026-04-10_roadmap_surface_cleanup_phase2b.md` | Recorded this scoped cleanup pass, the contract chosen, commands run, and validation results |

## Roadmap-surface ambiguity found

- ADR 0014 already made `docs/reference/POLYTOOL_MASTER_ROADMAP_v5_1.md` the first-class public roadmap surface, and `README.md`, `INDEX.md`, `PLAN_OF_RECORD.md`, and `CURRENT_STATE.md` were already moving in that direction.
- `docs/ROADMAP.md` still read like a competing authority surface: it said a roadmap was governing, pointed at the obsolete `docs/reference/POLYTOOL_MASTER_ROADMAP_v5.md`, and preserved a full numbered milestone ledger that looked authoritative instead of secondary.
- `docs/PLAN_OF_RECORD.md` still cross-referenced `ROADMAP.md` as a milestone checklist / kill-condition surface without labeling it as secondary.
- Direct public-doc backlinks in `docs/pdr/PDR-ROADMAP4-WRAPUP.md`, `docs/pdr/PDR-ROADMAP5-WRAPUP.md`, and `docs/runbooks/OPERATOR_QUICKSTART.md` still assumed the pre-router `ROADMAP.md` shape.
- `docs/PROJECT_OVERVIEW.md` and `docs/PROJECT_CONTEXT_PUBLIC.md` were scanned during this pass and did not need roadmap-authority edits.

## Contract chosen

- `docs/reference/POLYTOOL_MASTER_ROADMAP_v5_1.md` is the governing roadmap.
- `docs/CURRENT_STATE.md` is implemented repo truth.
- `docs/PLAN_OF_RECORD.md` remains the implementation-policy companion.
- `docs/ROADMAP.md` is a thin router / operator-facing roadmap surface only and has zero governing authority.
- Historical and supporting roadmap materials stay in place for this pass, including `docs/roadmaps/**`, `docs/pdr/**`, `docs/archive/**`, and `docs/dev_logs/**`.

## Commands run + output

### Roadmap-material scan

Command:

```powershell
Get-ChildItem docs/roadmaps -Recurse -File | ForEach-Object { $_.FullName.Replace((Get-Location).Path + '\','') }
```

Output:

```text
docs\roadmaps\RIS_PHASE2_evaluation_gate_monitoring_rag_testing_v1_1.md
```

### Required repo-state commands

Command:

```powershell
git status --short
```

Relevant output excerpt:

```text
M docs/CURRENT_STATE.md
M docs/INDEX.md
M docs/PLAN_OF_RECORD.md
M docs/README.md
M docs/ROADMAP.md
M docs/pdr/PDR-ROADMAP4-WRAPUP.md
M docs/pdr/PDR-ROADMAP5-WRAPUP.md
M docs/reference/POLYTOOL_MASTER_ROADMAP_v5_1.md
?? docs/runbooks/OPERATOR_QUICKSTART.md
```

Note: the full command output was noisy because the worktree already contained
many unrelated modifications before this pass.

Command:

```powershell
git diff --stat
```

Relevant output excerpt:

```text
docs/CURRENT_STATE.md                          |  11 +-
docs/INDEX.md                                  |  85 ++--
docs/PLAN_OF_RECORD.md                         |  41 +-
docs/README.md                                 | 107 +++--
docs/ROADMAP.md                                | 618 ++-----------------------
docs/pdr/PDR-ROADMAP4-WRAPUP.md                |  10 +-
docs/pdr/PDR-ROADMAP5-WRAPUP.md                |   3 +-
docs/reference/POLYTOOL_MASTER_ROADMAP_v5_1.md |  10 +
180 files changed, 386 insertions(+), 9600 deletions(-)
```

Interpretation: the repo-wide diff stat is noisy because of pre-existing worktree
changes. The roadmap-surface cleanup itself is captured by the targeted stat
below.

Command:

```powershell
git diff --stat -- docs/ROADMAP.md docs/README.md docs/INDEX.md docs/PLAN_OF_RECORD.md docs/CURRENT_STATE.md docs/reference/POLYTOOL_MASTER_ROADMAP_v5_1.md docs/pdr/PDR-ROADMAP4-WRAPUP.md docs/pdr/PDR-ROADMAP5-WRAPUP.md docs/runbooks/OPERATOR_QUICKSTART.md
```

Output:

```text
docs/CURRENT_STATE.md                          |  11 +-
docs/INDEX.md                                  |  85 ++--
docs/PLAN_OF_RECORD.md                         |  41 +-
docs/README.md                                 | 107 +++--
docs/ROADMAP.md                                | 618 ++-----------------------
docs/pdr/PDR-ROADMAP4-WRAPUP.md                |  10 +-
docs/pdr/PDR-ROADMAP5-WRAPUP.md                |   3 +-
docs/reference/POLYTOOL_MASTER_ROADMAP_v5_1.md |  10 +
8 files changed, 214 insertions(+), 671 deletions(-)
```

### Required roadmap-reference grep

Command:

```powershell
git grep -n -e 'ROADMAP.md\|POLYTOOL_MASTER_ROADMAP_v5_1.md' -- docs README.md
```

Relevant active-surface output excerpt:

```text
docs/CURRENT_STATE.md:9:Master Roadmap v5.1 (`docs/reference/POLYTOOL_MASTER_ROADMAP_v5_1.md`) is the
docs/CURRENT_STATE.md:20:  remains preserved history; `docs/ROADMAP.md` is a non-governing roadmap
docs/INDEX.md:15:| [Master Roadmap v5.1](reference/POLYTOOL_MASTER_ROADMAP_v5_1.md) | Strategic roadmap and LLM policy |
docs/INDEX.md:42:| [Roadmap Router](ROADMAP.md) | Secondary operator-facing roadmap surface; routes to the governing roadmap, current state, and historical roadmap materials |
docs/PLAN_OF_RECORD.md:7:Master Roadmap v5.1 (`docs/reference/POLYTOOL_MASTER_ROADMAP_v5_1.md`) is the
docs/PLAN_OF_RECORD.md:525:- [Roadmap router](ROADMAP.md) - Secondary operator-facing roadmap surface; not governing
docs/README.md:95:- [Master Roadmap v5.1](reference/POLYTOOL_MASTER_ROADMAP_v5_1.md) - Strategic roadmap and LLM policy
docs/README.md:96:- [Roadmap router](ROADMAP.md) - Secondary operator-facing roadmap surface; not governing
docs/ROADMAP.md:8:- Governing roadmap: [Master Roadmap v5.1](reference/POLYTOOL_MASTER_ROADMAP_v5_1.md)
docs/pdr/PDR-ROADMAP4-WRAPUP.md:181:  `docs/reference/POLYTOOL_MASTER_ROADMAP_v5_1.md` and
docs/pdr/PDR-ROADMAP5-WRAPUP.md:168:- See `docs/reference/POLYTOOL_MASTER_ROADMAP_v5_1.md` and
docs/reference/POLYTOOL_MASTER_ROADMAP_v5_1.md:5:> `docs/CURRENT_STATE.md` for implemented repo truth and `docs/ROADMAP.md`
docs/runbooks/OPERATOR_QUICKSTART.md:385: | Roadmap router | `docs/ROADMAP.md` (non-governing) |
```

Note: the exact grep also returns matches from intentionally untouched
historical/dev-log/archive/spec surfaces. Those were not edited in this pass.

### `docs/ROADMAP.md` router-role verification

Command:

```powershell
Select-String -Path docs/ROADMAP.md -Pattern 'not the governing roadmap|secondary roadmap router|governing roadmap|Implemented repo truth|Historical and Supporting Material' | ForEach-Object { "docs/ROADMAP.md:{0}: {1}" -f $_.LineNumber, $_.Line.Trim() }
```

Output:

```text
docs/ROADMAP.md:3: This file is a secondary roadmap router for operators. It is not the governing
docs/ROADMAP.md:8: - Governing roadmap: [Master Roadmap v5.1](reference/POLYTOOL_MASTER_ROADMAP_v5_1.md)
docs/ROADMAP.md:9: - Implemented repo truth: [Current State](CURRENT_STATE.md)
docs/ROADMAP.md:28: ## Historical and Supporting Material
```

### Supplemental validation

Command:

```powershell
Get-ChildItem docs -Recurse -File -Filter *.md | Where-Object { $_.FullName -notmatch '\\(archive|dev_logs|specs|features|obsidian-vault)\\' } | Select-String -Pattern 'docs/ROADMAP\.md|ROADMAP.md' | ForEach-Object { $_.Path.Replace((Get-Location).Path + '\','') + ':' + $_.LineNumber + ': ' + $_.Line.Trim() }
```

Output:

```text
docs/CURRENT_STATE.md:20: remains preserved history; `docs/ROADMAP.md` is a non-governing roadmap
docs/INDEX.md:20: public docs count goals. [ROADMAP.md](ROADMAP.md) is a secondary roadmap
docs/INDEX.md:42: | [Roadmap Router](ROADMAP.md) | Secondary operator-facing roadmap surface; routes to the governing roadmap, current state, and historical roadmap materials |
docs/PLAN_OF_RECORD.md:11: them. `docs/ROADMAP.md` is retained only as a non-governing roadmap router.
docs/PLAN_OF_RECORD.md:525: - [Roadmap router](ROADMAP.md) - Secondary operator-facing roadmap surface; not governing
docs/README.md:34: from public docs count goals. [ROADMAP.md](ROADMAP.md) is retained only as a
docs/README.md:96: - [Roadmap router](ROADMAP.md) - Secondary operator-facing roadmap surface; not governing
docs/reference/POLYTOOL_MASTER_ROADMAP_v5_1.md:5: > `docs/CURRENT_STATE.md` for implemented repo truth and `docs/ROADMAP.md`
docs/runbooks/OPERATOR_QUICKSTART.md:385: | Roadmap router | `docs/ROADMAP.md` (non-governing) |
```

Interpretation: outside deferred areas, the remaining `ROADMAP.md` mentions are
the intentional router labels plus the master-roadmap boundary note.

Command:

```powershell
$files = @('docs/ROADMAP.md','docs/README.md','docs/INDEX.md','docs/PLAN_OF_RECORD.md','docs/CURRENT_STATE.md','docs/reference/POLYTOOL_MASTER_ROADMAP_v5_1.md','docs/pdr/PDR-ROADMAP4-WRAPUP.md','docs/pdr/PDR-ROADMAP5-WRAPUP.md','docs/runbooks/OPERATOR_QUICKSTART.md')
$pat='\[[^\]]+\]\(([^)]+)\)'
foreach($f in $files){
  $text = Get-Content $f -Raw
  $matches = [regex]::Matches($text,$pat)
  $missing=@()
  foreach($m in $matches){
    $target = $m.Groups[1].Value.Split('#')[0].Trim()
    if(-not $target -or $target.Contains('://') -or $target.StartsWith('mailto:')){ continue }
    $resolved = [System.IO.Path]::GetFullPath((Join-Path (Split-Path $f) $target))
    if(-not (Test-Path $resolved)){ $missing += $target }
  }
  if($missing.Count -eq 0){ '{0}: OK' -f $f } else { '{0}: FAIL' -f $f }
}
```

Output:

```text
docs/ROADMAP.md: OK
docs/README.md: OK
docs/INDEX.md: OK
docs/PLAN_OF_RECORD.md: OK
docs/CURRENT_STATE.md: OK
docs/reference/POLYTOOL_MASTER_ROADMAP_v5_1.md: OK
docs/pdr/PDR-ROADMAP4-WRAPUP.md: OK
docs/pdr/PDR-ROADMAP5-WRAPUP.md: OK
docs/runbooks/OPERATOR_QUICKSTART.md: OK
```

## Validation results

- PASS: `docs/reference/POLYTOOL_MASTER_ROADMAP_v5_1.md` is now unambiguously labeled as the governing roadmap across the active public docs surface.
- PASS: `docs/ROADMAP.md` no longer reads like a competing authority source; it now opens as a non-governing router and routes readers to strategic truth, implemented truth, and retained history.
- PASS: roadmap-related navigation in `docs/README.md`, `docs/INDEX.md`, `docs/PLAN_OF_RECORD.md`, `docs/CURRENT_STATE.md`, `docs/pdr/PDR-ROADMAP4-WRAPUP.md`, `docs/pdr/PDR-ROADMAP5-WRAPUP.md`, and `docs/runbooks/OPERATOR_QUICKSTART.md` is consistent with the chosen contract.
- PASS: all local markdown links in the touched roadmap-surface docs resolved successfully.
- PASS: no edits were made under `docs/obsidian-vault/**`, `docs/specs/**`, `docs/features/**`, `docs/archive/**`, or runtime code/config.

## Intentionally deferred

- Historical references inside `docs/dev_logs/**` were left untouched.
- Historical references inside `docs/archive/**` were left untouched, including archive material that still describes the older authority-shaped `ROADMAP.md`.
- Spec and feature documents that still mention `docs/ROADMAP.md` were left untouched per pass boundary.
- Older historical roadmap files under `docs/reference/` (for example v4.2 and v5) were left in place and not rewritten.
- No files were moved or deleted under `docs/roadmaps/**`; the folder remains a retained supporting history/task surface only.
