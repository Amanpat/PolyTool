---
title: Vault Redesign Codex Audit 2026-05-23
type: work_packet
status: active
source_zone: claude_memory
last_updated: 2026-05-23
lifecycle: reviewed
target_agent: codex
acceptance_criteria:
  - Re-run vault frontmatter validation script
  - Independently verify file-level migration claims
  - Spot-check schema compliance across claude-memory subfolders
  - Sample wikilink integrity
  - Verify contradiction resolution C-001 through C-006
  - Verify legacy zones remain present
  - State AC-1 through AC-14 verdicts from filesystem evidence
---

# Vault Redesign Codex Audit

Date: 2026-05-23
Auditor: Codex
Vault root: `docs/obsidian-vault`
Spec: `docs/specs/vault-redesign-spec-v1.md`

## Verdict

**Verdict: needs cleanup**

**Confidence: high** for filesystem, frontmatter, link, and contradiction-pointer findings. **Confidence: medium** for "no files deleted" because there is no pre-migration manifest in the prompt; I used current filesystem state plus `git status` as the available evidence.

The migration is substantially scaffolded and the scoped validation script passes, but the vault does **not** meet the full spec acceptance criteria. Main blockers: broken wikilinks, incomplete reciprocal supersession metadata, missing `## Connections` sections on many Tier 1/Tier 2 active docs, incomplete/unenforced plugin/template setup, repo-doc schema gaps skipped by the validation script, and the C-004 source research file remains a draft placeholder.

## 1. Validation Script Re-run

Command run from repo root:

```powershell
python docs\scripts\validate-vault-frontmatter.py
```

Output:

```text
Validation: 143 checked, 143 pass, 0 fail, 207 skipped (legacy)
Report: D:\Coding Projects\Polymarket\PolyTool\docs\obsidian-vault\claude-memory\work-packets\2026-05-23-frontmatter-validation-report.md
```

This matches the prior validation report claim: 143 checked, 143 pass, 0 fail, 207 skipped.

Important limitation: the script skips `.obsidian/`, `.smart-env/`, `10-Session-Notes/`, `Claude Desktop/`, `PolyTool/`, `Templates/`, `repo-docs/`, and `ris-mirror/`. Therefore it does **not** prove "every document in the vault" satisfies the spec schema.

## 2. File-Level Claims

PASS: `docs/obsidian-vault/AGENT.md` is not present at vault root.

PASS: `docs/obsidian-vault/claude-memory/archive/AGENT.md` exists and has:

```yaml
status: superseded
superseded_by: AGENTS.md
lifecycle: archived
```

PASS: The first non-blank body line in archived `AGENT.md` is:

```text
> [!warning] This file is superseded. See [[AGENTS|Agent Rules]] for current operating rules.
```

PASS: `ris-mirror/` contains only the allowed structure files:

```text
ris-mirror/_index.md
ris-mirror/external_knowledge/_index.md
ris-mirror/manifest.json
ris-mirror/research/_index.md
ris-mirror/signals/_index.md
ris-mirror/user_data/_index.md
```

PASS: `docs/obsidian-vault/.gitignore` contains a standalone `ris-mirror/` entry.

## 3. Stratified Schema Sample

I sampled up to 5 non-index markdown files from each `claude-memory/` subfolder. All sampled files had required universal fields, type-specific required fields where applicable, and valid enum values.

Sampled files:

```text
decisions:
- claude-memory/decisions/adr-0001-three-zone-vault-architecture.md
- claude-memory/decisions/decision-loop-d-clob-subscription.md
- claude-memory/decisions/decision-ris-n8n-pilot-scope.md
- claude-memory/decisions/decision-scientific-rag-architecture.md
- claude-memory/decisions/decision-workflow-harness-refresh-2026-04.md

research:
- claude-memory/research/2026-05-23-research-llm-obsidian-vault-design.md
- claude-memory/research/concept-risk-framework.md
- claude-memory/research/reference-issue-fastapi-island.md
- claude-memory/research/reference-phase-8-scale-platform.md
- claude-memory/research/ris-operational-readiness-roadmap-v1.md

session-notes:
- claude-memory/session-notes/2026-04-09-architect-review-assessment.md
- claude-memory/session-notes/2026-04-09-wallet-discovery-pipeline-design.md
- claude-memory/session-notes/2026-04-10-ris-phase2-audit-results.md
- claude-memory/session-notes/2026-04-22-ris-roadmap-v1.1-review.md
- claude-memory/session-notes/2026-05-22-continuous-development-workflow-research.md

work-packets:
- claude-memory/work-packets/2026-05-23-frontmatter-validation-report.md
- claude-memory/work-packets/work-packet-fee-model-maker-taker-kalshi.md
- claude-memory/work-packets/work-packet-marker-single-paper-validation.md
- claude-memory/work-packets/work-packet-pre-fetch-svm-topic-filter.md
- claude-memory/work-packets/work-packet-unified-open-source-integration.md

prompts:
- claude-memory/prompts/2026-04-09-claude-architect-response.md
- claude-memory/prompts/2026-04-09-glm5-gemini-flash-structured-eval.md
- claude-memory/prompts/2026-04-09-glm5-polymarket-event-volume.md
- claude-memory/prompts/2026-04-10-glm5-unified-gap-fill-open-source.md
- claude-memory/prompts/2026-04-22-research-ollama-cloud-api.md

ideas:
- claude-memory/ideas/idea-cross-platform-price-divergence-ris-signal.md
- claude-memory/ideas/idea-graphify-pattern-adoption.md
- claude-memory/ideas/idea-pmxt-sidecar-architecture-evaluation.md

spec:
- claude-memory/spec/vault-redesign-spec.md

archive:
- claude-memory/archive/AGENT.md
- claude-memory/archive/archive-ideas-index.md
- claude-memory/archive/archive-polytool-done.md
- claude-memory/archive/archive-prompt-archive-index.md
- claude-memory/archive/archive-vault-system-guide.md
```

Finding: sampled `claude-memory/` frontmatter is clean. This does not cover `repo-docs/`, which the validator skips and where I found invalid lifecycle enum values such as `lifecycle: active` in `repo-docs/adrs/adr-0013-ris-n8n-pilot-scoped.md`.

## 4. Wikilink Integrity

Method: sampled 20 wikilinks with deterministic seed `20260523`; targets were resolved against actual markdown files in the vault.

Result: **18/20 sampled links resolved; 2/20 were broken.**

Broken sampled links:

```text
claude-memory/session-notes/2026-04-09-wallet-discovery-pipeline-design.md
  [[claude-memory/prompts/2026-04-09-glm5-polymarket-leaderboard-api]]

claude-memory/session-notes/2026-04-09-wallet-discovery-pipeline-design.md
  [[claude-memory/decisions/decision-two-feed-architecture]]
```

Additional full-scan context: across new-zone markdown files I found 960 wikilinks and 110 unresolved targets. Examples include:

```text
claude-memory/decisions/decision-agent-parallelism-ris-phase2.md
  [[Claude Desktop/09-Decisions/RIS_OPERATIONAL_READINESS_ROADMAP]]

claude-memory/decisions/decision-loop-a-leaderboard-api.md
  [[Claude Desktop/08-Research/01-Wallet-Discovery-Pipeline]]

claude-memory/prompts/2026-04-22-research-ollama-cloud-api.md
  [[Claude Desktop/09-Decisions/RIS_OPERATIONAL_READINESS_ROADMAP_v1.1]]

claude-memory/research/ris-operational-readiness-roadmap-v1.1.md
  [[Claude Desktop/08-Research/Hermes Agent - PolyTool Integration Setup Guide]]
```

Finding: the spec criterion "No broken wikilinks" is not met.

## 5. Contradiction Resolution

### C-001: Two-zone vault architecture superseded by three-zone

PARTIAL/PASS.

Old doc:

```text
claude-memory/decisions/decision-two-zone-vault-architecture.md
status: superseded
superseded_by: claude-memory/decisions/adr-0001-three-zone-vault-architecture
```

New doc:

```text
claude-memory/decisions/adr-0001-three-zone-vault-architecture.md
status: active
supersedes: decision-two-zone-vault-architecture
```

The reciprocal pointer exists, though it uses a short ID rather than the full path used by the old doc.

### C-002: RIS n8n pilot scope superseded by repo ADR-0013

PARTIAL/FAIL.

Old doc:

```text
claude-memory/decisions/decision-ris-n8n-pilot-scope.md
status: superseded
superseded_by: repo-docs/adrs/adr-0013-ris-n8n-pilot-scoped
```

Superseding doc:

```text
repo-docs/adrs/adr-0013-ris-n8n-pilot-scoped.md
status: active
lifecycle: active
```

Problems:
- Missing reciprocal `supersedes` pointer back to `claude-memory/decisions/decision-ris-n8n-pilot-scope`.
- `lifecycle: active` is not valid per spec enum (`draft`, `reviewed`, `verified`, `stale`, `archived`). The validator does not catch this because it skips `repo-docs/`.

### C-003: RIS roadmap v1 superseded by v1.1

PARTIAL/FAIL.

Old doc:

```text
claude-memory/research/ris-operational-readiness-roadmap-v1.md
status: superseded
superseded_by: ris-operational-readiness-roadmap-v1.1
```

Superseding doc:

```text
claude-memory/research/ris-operational-readiness-roadmap-v1.1.md
status: active
supersedes: RIS_OPERATIONAL_READINESS_ROADMAP.md (original + three appended updates)
```

Problem: the superseding doc does not point back to `claude-memory/research/ris-operational-readiness-roadmap-v1.md`; it points to a legacy/source title instead.

### C-004: Missing research file

OPEN/PARTIAL.

File exists:

```text
claude-memory/research/2026-05-23-research-llm-obsidian-vault-design.md
status: draft
lifecycle: draft
```

This confirms the execution report's open item: the file is a placeholder stub, not a verified migrated source research packet.

### C-005: Stale PolyTool architecture docs vs repo-docs

PARTIAL.

Evidence:

```text
claude-memory/research/_index.md:
## Concepts (from PolyTool zone - lifecycle: stale, superseded by repo-docs/)
```

Many migrated concept/reference files have `lifecycle: stale`, for example:

```text
claude-memory/research/concept-fastapi-service.md
claude-memory/research/concept-core-library.md
claude-memory/research/reference-cli-reference.md
```

Problem: these are generally still `status: active`, not `status: superseded`, and do not carry `superseded_by` pointers. The execution report describes this as resolved by staleness marking, but the audit procedure asked for superseded docs to have `status=superseded` and `superseded_by`.

### C-006: AGENT.md superseded by AGENTS.md

PARTIAL/FAIL.

Old doc:

```text
claude-memory/archive/AGENT.md
status: superseded
superseded_by: AGENTS.md
lifecycle: archived
```

New doc:

```text
AGENTS.md
status: active
```

Problem: `AGENTS.md` has no reciprocal `supersedes: AGENT.md` pointer.

## 6. Legacy Zones

Legacy zones exist at vault root:

```text
Claude Desktop/ exists, 78 markdown files
PolyTool/ exists, 48 markdown files
10-Session-Notes/ exists, 2 markdown files
Templates/ exists, 5 markdown files
```

No deletion is visible under these legacy zones in `git status`.

However, the legacy zones are not strictly "untouched": current `git status` shows:

```text
M  docs/obsidian-vault/Claude Desktop/11-Prompt-Archive/2026-04-21 Architect Custom Instructions v2.md
?? docs/obsidian-vault/10-Session-Notes/
?? docs/obsidian-vault/Claude Desktop/10-Session-Notes/2026-05-22 Continuous Development Workflow Research.md
?? docs/obsidian-vault/Claude Desktop/11-Prompt-Archive/2026-04-22 Architect Custom Instructions v3.md
```

Finding: legacy zones still exist and no deletion is visible there, but "untouched" is false based on the modified and untracked files.

## 7. Acceptance Criteria AC-1 Through AC-14

I used the AC numbering from the execution report because the spec's final checklist is unnumbered.

| AC | Criterion | Verdict | Evidence |
|---|---|---|---|
| AC-1 | Three zone folders exist | PASS | `repo-docs/`, `claude-memory/`, `ris-mirror/` all exist with `_index.md`. |
| AC-2 | Every document has valid frontmatter | PARTIAL | Script says 143/143 pass, but skips `repo-docs/` and legacy zones. `repo-docs/adrs/adr-0013-ris-n8n-pilot-scoped.md` has invalid `lifecycle: active`. |
| AC-3 | `ris-mirror/` empty except structure + manifest | PASS | Only `_index.md` files plus `manifest.json` present. |
| AC-4 | `ris-mirror/` gitignored | PASS | `.gitignore` contains `ris-mirror/`. |
| AC-5 | `repo-docs/` files read-only/not modified post-copy | PARTIAL | Zone exists and files carry `source_zone: repo`, but read-only is not enforced by filesystem evidence; repo-docs schema is not fully valid and validation skips it. |
| AC-6 | Naming conventions followed | PARTIAL | Most new slugs are kebab-case/dated; exceptions include archived uppercase `AGENT.md` and dotted `ris-operational-readiness-roadmap-v1.1.md`. |
| AC-7 | Wikilinks use full zone-prefixed paths cross-zone | FAIL | Broken/legacy links remain, e.g. `[[claude-memory/decisions/decision-two-feed-architecture]]` and `[[Claude Desktop/08-Research/01-Wallet-Discovery-Pipeline]]`. |
| AC-8 | `CLAUDE.md` and `AGENTS.md` at vault root | PASS | Both files exist. |
| AC-9 | `index.md` lists all Tier 1 docs | PARTIAL | It lists `claude-memory` Tier 1 decisions/spec, but not every active Tier 1 repo-doc spec/ADR individually. |
| AC-10 | `log.md` has entries for all phases | PASS | `log.md` contains `phase-1` through `phase-6`, plus cleanup and supersession entries. |
| AC-11 | Contradictions resolved or recorded | PARTIAL/FAIL | C-002, C-003, C-005, C-006 have incomplete reciprocal supersession or only stale marking; C-004 remains open. |
| AC-12 | Source research file placed in `claude-memory/research/` | PARTIAL | File exists but is `status: draft`, `lifecycle: draft`; execution report says operator must export source from Claude Desktop. |
| AC-13 | No files deleted, archive instead | PARTIAL | Content for root `AGENT.md` is archived, but `git status` shows `D docs/obsidian-vault/AGENT.md`. No deletion visible inside named legacy zones. |
| AC-14 | `## Connections` on all Tier 1/Tier 2 docs | FAIL | Full scan found 105 active Tier 1/Tier 2 docs without `## Connections`, including most active decisions and repo-doc specs/ADRs. |

## Additional Spec Findings

Plugin stack is incomplete relative to the spec:

```text
.obsidian/community-plugins.json includes:
dataview, calendar, obsidian-kanban, obsidian-local-rest-api,
smart-connections, smart-connections-visualizer, templater-obsidian,
obsidian-tasks-plugin
```

Findings:
- Bases core plugin is enabled in `.obsidian/core-plugins.json`.
- Templater and Local REST API are installed.
- Linter is not installed.
- MetaEdit is not installed.
- Mermaid is not directly verifiable as an installed community plugin; it is normally built into Obsidian markdown rendering, not listed separately here.
- Smart Connections and Smart Connections Visualizer are installed, despite the spec's "Do Not Install" section saying Smart Connections should not be installed.

Templater folder templates are not configured for each `claude-memory/` subfolder:

```json
"enable_folder_templates": true,
"folder_templates": [
  {
    "folder": "",
    "template": ""
  }
]
```

Repo-doc sync is incomplete if interpreted as all repo docs/spec docs:

```text
docs/specs markdown count: 47
repo-docs/specs markdown count excluding _index.md: 45
```

Missing from `repo-docs/specs/` by filename normalization:

```text
LLM_BUNDLE_CONTRACT.md
```

`ADR-benchmark-versioning-and-crypto-unavailability.md` is not in `repo-docs/specs/` but does exist under `repo-docs/adrs/`, so it was reclassified rather than lost.

## Consolidated Deviations

1. The validation script passes but is scoped; it skips `repo-docs/`, `ris-mirror/`, and legacy zones, so it does not prove full-vault schema compliance.
2. `repo-docs/` contains invalid lifecycle enum values such as `lifecycle: active`.
3. Wikilink integrity fails: 2/20 sampled links broken; full scan found 110 unresolved links.
4. Contradiction resolution is incomplete for C-002, C-003, C-005, and C-006; C-004 remains open as a draft placeholder.
5. Many active Tier 1/Tier 2 docs lack `## Connections` sections; full scan found 105 such files.
6. `index.md` does not list every active Tier 1 repo-doc spec/ADR individually.
7. Plugin stack is incomplete: Linter and MetaEdit are absent; Smart Connections is installed despite the spec prohibition.
8. Templater folder templates are effectively blank and not configured per `claude-memory/` subfolder.
9. Legacy zones exist and no deletion is visible under them, but they are not untouched: one file is modified and new untracked files exist under legacy paths.
10. `LLM_BUNDLE_CONTRACT.md` from `docs/specs/` is not present in `repo-docs/specs/`.

## Commands Run

```text
git status --short
git log --oneline -5
python -m polytool --help
python docs\scripts\validate-vault-frontmatter.py
Get-Content docs\specs\vault-redesign-spec-v1.md
Get-Content docs\obsidian-vault\claude-memory\work-packets\2026-05-23-vault-redesign-execution-report.md
Get-Content docs\obsidian-vault\claude-memory\work-packets\2026-05-23-frontmatter-validation-report.md
Get-Content docs\scripts\validate-vault-frontmatter.py
Multiple read-only PowerShell/Python filesystem audits for frontmatter, links, contradiction metadata, legacy-zone status, plugins, and counts
```

## Connections

- [[claude-memory/spec/vault-redesign-spec]]
- [[claude-memory/work-packets/2026-05-23-vault-redesign-execution-report]]
- [[claude-memory/work-packets/2026-05-23-frontmatter-validation-report]]
- [[claude-memory/decisions/adr-0001-three-zone-vault-architecture]]
- [[index|Vault Home]]
