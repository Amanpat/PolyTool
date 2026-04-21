# ADR 0014: Public Docs Surface and Repo Hygiene Boundaries

Date: 2026-04-10
Status: Accepted

## Context

The repo has accumulated too many authoritative-looking documentation surfaces.
As of this decision:

- `docs/` contains 732 files
- `docs/dev_logs/` contains 293 files
- `docs/obsidian-vault/` contains 204 files

This creates navigation noise and manual sync drift. We need a durable cleanup
contract before any destructive repo-maintenance pass.

## Decision

### 1. First-class root docs allowlist

Only the following root-level docs are first-class public surface:

| Path | Role |
|------|------|
| `docs/README.md` | Navigation only |
| `docs/INDEX.md` | Navigation only |
| `docs/PLAN_OF_RECORD.md` | Primary docs-governance and implementation-policy companion |
| `docs/ARCHITECTURE.md` | Architecture truth |
| `docs/STRATEGY_PLAYBOOK.md` | Strategy and falsification methodology |
| `docs/reference/POLYTOOL_MASTER_ROADMAP_v5_1.md` | Strategic roadmap and LLM policy |
| `docs/CURRENT_STATE.md` | Implemented repo truth |

Any other root-level document is retained for now but is not part of the
first-class public docs surface unless explicitly promoted later.

### 2. Authority chain

For public-docs governance and cleanup decisions, authority resolves in this
order:

1. `docs/PLAN_OF_RECORD.md`
2. `docs/ARCHITECTURE.md`
3. `docs/STRATEGY_PLAYBOOK.md`
4. `docs/reference/POLYTOOL_MASTER_ROADMAP_v5_1.md`
5. `docs/CURRENT_STATE.md`

`docs/README.md` and `docs/INDEX.md` have zero authority. They route readers to
the governing docs and must not become competing truth surfaces.

### 3. Doc classes and cleanup rules

| Class | Includes | Counts toward public docs goals? | Default rule |
|------|----------|----------------------------------|--------------|
| First-class root docs | Root allowlist above | Yes | Keep in place; keep concise; maintain links and labels |
| Public support docs | `docs/reference/**`, `docs/runbooks/**`, `docs/features/**`, `docs/specs/**`, `docs/adr/**` | Yes, when surfaced from `README.md` or `INDEX.md` | Keep when active and uniquely useful; archive when clearly superseded; quarantine when duplicate, ambiguous, or unowned; delete only with explicit scoped approval |
| Historical records | `docs/dev_logs/**`, `docs/archive/**` | No | Preserve as history; do not surface as primary navigation; do not rewrite existing records for cleanup |
| Separate subsystem | `docs/obsidian-vault/**` | No | Treat as a separate knowledge subsystem; do not use it to satisfy public-doc count targets |
| Tooling/internal docs | `docs/audits/**`, `docs/debug/**`, `docs/eval/**`, generated context packs and similar internal support docs | No | Keep when operationally useful; do not present as first-class public docs; quarantine or archive later only via explicit scoped review |

### 4. Keep/archive/quarantine/delete policy

- **Keep:** first-class root docs, active runbooks, active feature docs, active
  ADRs, active specs, and reference docs that are still linked from primary
  navigation.
- **Archive:** superseded public docs with clear replacements and durable
  historical value. Archive actions require explicit scoped work; this ADR does
  not authorize moves by itself.
- **Quarantine:** ambiguous or duplicate docs that look authoritative but are
  not on the allowlist and do not yet have an agreed archive destination.
  Quarantined docs must be removed from primary navigation first.
- **Delete:** only accidental duplicates, generated throwaways, or files with no
  durable value, and only when a later task explicitly scopes deletion.

### 5. First cleanup pass boundaries

The first cleanup pass is classification and navigation work only:

- no archive moves or deletes;
- no edits under `docs/obsidian-vault/**`;
- no rewrites of existing `docs/dev_logs/**` entries;
- no bulk historical rewrites of governing docs;
- normalize touched governance docs to `POLYTOOL_MASTER_ROADMAP_v5_1.md` where
  appropriate.

New dev logs remain mandatory for each scoped cleanup session.

## Consequences

- The public docs count target applies only to first-class root docs and curated
  public support docs, not to the vault, dev logs, or other internal support
  surfaces.
- README and INDEX become navigation surfaces only.
- Historical integrity is preserved while future cleanup work gains a durable
  classification contract.
