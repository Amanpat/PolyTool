---
title: Session - Vault Redesign Spec Drafted
type: session_note
status: active
source_zone: conversation
last_updated: 2026-05-23
generator: claude-desktop
human_authored: false
tags:
  - session
  - spec
  - vault-design
  - tier-1
references:
  - "[[2026-05-23-research-captured-vault-redesign]]"
  - "[[2026-05-23-research-llm-obsidian-vault-design]]"
aliases:
  - Vault Spec v1 Drafted
---

# Session — Vault Redesign Spec Drafted

## Context

Tier 1 design specification for the PolyTool vault redesign drafted and saved. This is the contract that Claude Code execution will be measured against.

Full spec saved to `/mnt/user-data/outputs/vault-redesign-spec-v1.md`. Target location in new vault: `claude-memory/spec/vault-redesign-spec.md`.

## Spec Summary

Three-zone vault:
- **Zone A — `repo-docs/`**: synced from PolyTool repo
- **Zone B — `claude-memory/`** (renamed from "conversations"): agent + human working memory
- **Zone C — `ris-mirror/`**: auto-generated mirror of Chroma RIS (centerpiece, gitignored)

Five hard rules going into vault-level `CLAUDE.md`:
1. Frontmatter is authoritative
2. Respect tier hierarchy (spec/adr/decision > research/concept > session_note)
3. Respect zone discipline (never write to mirror or repo-docs)
4. No silent overwrites (record contradictions explicitly)
5. No deletion (archive instead)

Six-phase migration playbook with explicit acceptance criteria per phase.

## What's Included in the Spec

- Three-zone architecture with write-discipline rules per zone
- Complete vault root layout (folder + file map)
- Full frontmatter schema (required fields, type-specific extensions, optional fields, cross-references, validation rules)
- Naming conventions (kebab-case slugs, ISO date prefix for temporal, ADR numbering)
- Linking patterns (`## Connections` section, cross-zone full paths)
- RIS mirror sync architecture diagram + manifest format + failure modes + partition policies
- Plugin stack with install + do-not-install lists
- Vault-level CLAUDE.md / AGENTS.md operating rules
- Six-phase migration playbook
- Initial file skeletons (`index.md`, `log.md`, `README.md`, `CLAUDE.md`, `.gitignore`)
- Acceptance criteria for Claude Code execution

## Open Items

- The RIS mirror **sync service** is NOT built in this redesign. The vault gets the structure and policies; sync service is a separate work packet (deferred).
- Current vault audit (Phase 3 of migration) will reveal duplicates and contradictions in existing docs — these get resolved via ADRs during Phase 4.
- "claude-memory" final name agreed in this session. Anthropomorphic alternatives ("claude-brain") rejected as overclaiming.

## Next Step

Hand spec + research packet to Claude Code with `/goal`. After execution, Codex audit against spec acceptance criteria.

## Connections

- [[2026-05-23-research-captured-vault-redesign]] — captured the research that grounds this spec
- [[2026-05-23-research-llm-obsidian-vault-design]] — full research packet
