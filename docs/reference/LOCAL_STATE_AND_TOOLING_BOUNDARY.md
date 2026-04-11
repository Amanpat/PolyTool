# Local State and Tooling Boundary

This reference complements
[ADR 0014](../adr/0014-public-docs-surface-and-repo-hygiene-boundaries.md).
ADR 0014 governs the public docs surface. This document classifies repo-root
hidden tooling, local workspace state, runtime evidence/state, and disposable
scratch so repo-cleanliness checks stop mixing those classes together.

## Boundary Rules

- Classification only. This document does not authorize root moves, deletes, or
  ignore-file changes.
- `docs/obsidian-vault/**` remains governed by ADR 0014 and stays excluded from
  public-doc count goals.
- Raw `git status` is not a cleanliness metric by itself when local-state or
  runtime-state roots are present.
- Cleanliness reports must distinguish `public-surface drift` from
  `local-state/runtime noise`.

## Root Classes

| Class | Roots | Counts toward repo cleanliness? | Default handling |
|------|-------|----------------------------------|------------------|
| Public repo surface | `docs/`, `infra/`, `packages/`, `polytool/`, `services/`, `tools/`, `tests/`, `scripts/`, `config/`, `workflows/`, `.github/`, `.githooks/`, committed root manifests/examples | Yes | Review and validate normally |
| Stable tooling surface inside hidden roots | Shared tool definitions under `.claude/agents/**`, `.claude/commands/**`, `.claude/hooks/**`, `.claude/get-shit-done/**`, `.gemini/**`, `.opencode/agents/**`, `.opencode/command/**`, `.opencode/hooks/**`, `.opencode/get-shit-done/**`, plus shared manifests/settings that define repo tooling behavior | Yes, when intentionally changed | Treat as repo tooling, not as scratch |
| Local-only tooling/workspace state | `.claude/worktrees/**`, `.claude/settings.local.json`, `.planning/**`, `.code-review-graph/**`, `.venv/**`, and local install/cache folders nested under tool roots such as `.opencode/node_modules/**` | No | Exclude from cleanliness counts unless the task explicitly targets them |
| Runtime evidence/state | `artifacts/**`, `kb/**`, `docker_data/**` | No | Treat as operator/runtime state; validate only when the task is about runtime artifacts or data retention |
| Disposable scratch / quarantine | `.tmp/**`, `.sandboxtmp/**`, `quarantine/**`, generated temp/build roots such as `build/`, `polytool.egg-info/`, pip temp dirs, and pytest temp dirs | No | Exclude from cleanliness counts; cleanup requires separate explicit scope |

## Operational Notes

- `config/**` remains public repo surface even when it contains committed
  manifests, lock files, or benchmark-selection artifacts.
- `kb/**` is local-only evidence/state even though `kb/README.md` and
  `kb/.gitkeep` are committed placeholders.
- Hidden tooling roots are mixed-purpose. Count stable shared definitions, but
  do not count per-session worktrees, caches, or local installs.
- When reporting a scoped docs or code cleanup, say explicitly when raw
  `git status` is noisy because excluded local-state/runtime roots are dirty.

## Committed vs Local-Only Surface Detail

### .claude — committed surface

Shared repo tooling definitions tracked in git:

- `.claude/agents/**` — GSD agent prompts
- `.claude/commands/**` — GSD slash-command definitions
- `.claude/get-shit-done/**` — GSD framework (workflows, templates, references, bin)
- `.claude/hooks/**` — GSD hook scripts
- `.claude/gsd-file-manifest.json` — GSD file manifest
- `.claude/package.json` — GSD package manifest
- `.claude/settings.json` — shared Claude Code project settings

### .claude — local-only exceptions (gitignored)

- `.claude/settings.local.json` — per-machine Claude Code overrides
- `.claude/worktrees/` — per-session agent worktree checkouts (disposable)
- `.claude/skills/` — currently empty and unresolved; gitignored as precaution

**Tracked worktree cleanup (RESOLVED):** `.claude/worktrees/` (14 gitlink entries)
and `.claude/settings.local.json` were deindexed in quick-260411-im0 (commit
f24600a, automatic during staging) and quick-260411-ime (commit 79fe441, explicit
audit). The files remain on disk; only git index tracking was removed. The
.gitignore rules prevent new files from being tracked going forward.

### .opencode — committed surface

Shared repo tooling definitions tracked in git:

- `.opencode/agents/**` — GSD agent prompts (OpenCode variant)
- `.opencode/command/**` — GSD command definitions
- `.opencode/get-shit-done/**` — GSD framework (OpenCode variant)
- `.opencode/hooks/**` — GSD hook scripts
- `.opencode/gsd-file-manifest.json` — GSD file manifest
- `.opencode/settings.json` — shared OpenCode project settings

### .opencode — local-only exceptions (gitignored)

- `.opencode/package.json` — bun package manifest (local install artifact)
- `.opencode/bun.lock` — bun lockfile (local install artifact)
- `.opencode/node_modules/` — bun install output (disposable)

These are covered by both `.opencode/.gitignore` (nested) and root `.gitignore`
(defense-in-depth).

## Cleanliness Reporting Rule

Use this split when validating boundary-sensitive work:

1. `Public-surface drift`: changes under public repo surface and intentionally
   edited stable tooling definitions.
2. `Excluded local state/runtime noise`: changes under local tooling state,
   runtime evidence/state, scratch, quarantine, and `docs/obsidian-vault/**`.

If a task does not target the second category, it should not fail repo-
cleanliness expectations for that noise alone.
