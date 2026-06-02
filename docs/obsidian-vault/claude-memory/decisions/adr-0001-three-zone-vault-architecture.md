---
title: "ADR-0001: Three-Zone Vault Architecture"
adr_number: 1
decision: "Adopt three-zone vault architecture: repo-docs/ (read-only repo mirror), claude-memory/ (writable working knowledge), ris-mirror/ (RIS sync target)"
type: adr
status: active
source_zone: claude_memory
last_updated: 2026-05-23
lifecycle: reviewed
decided_at: 2026-05-23
decided_by: operator
supersedes: decision-two-zone-vault-architecture
tags: [vault, architecture, decision]
---

# ADR-0001: Three-Zone Vault Architecture

## Status

Active — supersedes [[claude-memory/decisions/decision-two-zone-vault-architecture]]

## Context

The two-zone vault architecture (ADR from 2026-04-08) defined:
- **Zone A (folders 00–07):** Repo mirror, read-only for all except Claude Code
- **Zone B (folders 08–12):** Working knowledge, Claude Project can write here

This design served well initially but had several gaps:
1. No formal zone for the RIS pipeline's Chroma-backed knowledge store
2. No standardized frontmatter schema across documents
3. No tier hierarchy (spec/adr/decision vs research vs session notes)
4. Flat folder structure with numeric prefixes tied to the old two-zone model
5. Dataview-dependent indexes that break in other Obsidian installations and LLM contexts

The vault redesign spec (v1.0, 2026-05-23) defines a complete replacement.

## Decision

Adopt the **three-zone vault architecture** as defined in [[claude-memory/spec/vault-redesign-spec]]:

| Zone | Folder | Purpose | Write Policy |
|------|--------|---------|-------------|
| A | `repo-docs/` | Read-only mirror of repo `docs/` | Edit in repo, sync to vault |
| B | `claude-memory/` | Agent and human working memory | Freely writable |
| C | `ris-mirror/` | Read-only Chroma RIS mirror | Written only by RIS sync service |

### Key changes from two-zone model

- `repo-docs/` replaces the old Zone A (folders 00–07) with a structured mirror
- `claude-memory/` replaces Zone B (folders 08–12) with typed subfolders
- `ris-mirror/` is a new Zone C with no equivalent in the old model
- Frontmatter schema is standardized across all documents
- Tier hierarchy (Tier 1: spec/adr/decision > Tier 2: research/concept > Tier 3: session_note/work_packet) is formally defined
- Naming: kebab-case slugs, ISO date prefixes for temporal docs, `adr-NNNN-` for ADRs
- Wikilinks use full zone-prefixed paths for cross-zone references

## Consequences

### Positive

- LLM agents can navigate the vault without Dataview or Obsidian plugins
- Zone discipline prevents accidental writes to read-only zones
- Tier hierarchy provides unambiguous conflict resolution
- Frontmatter schema enables programmatic querying

### Negative

- One-time migration cost to reorganize ~100 existing vault documents
- Old numeric folder structure (00–07, 08–12) is archived, not deleted

### Migration

The old two-zone vault documents are preserved in `claude-memory/archive/` with `status: archived`. The migration was executed on 2026-05-23 and documented in [[claude-memory/work-packets/2026-05-23-vault-redesign-execution-report]].

## Connections

- [[claude-memory/spec/vault-redesign-spec]]
- [[claude-memory/decisions/decision-two-zone-vault-architecture]]
- [[repo-docs/adrs/_index]]
- [[index|Vault Home]]
