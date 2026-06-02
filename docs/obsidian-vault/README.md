---
title: PolyTool Vault README
type: reference
status: active
source_zone: claude_memory
last_updated: 2026-05-23
lifecycle: reviewed
---

# PolyTool Vault

This is the PolyTool project knowledge vault. Primary consumers: LLM agents (Claude, Claude Code, Codex). Secondary: humans.

## Quick Orientation

- **Looking for project state?** → [[repo-docs/current-state]]
- **Looking for the RIS data?** → [[ris-mirror/_index]]
- **Looking for a past decision?** → [[index]] under "Active Decisions"
- **Want to know the rules?** → [[CLAUDE]] or [[AGENTS]]
- **Want the spec for this vault?** → [[claude-memory/spec/vault-redesign-spec]]

## Three Zones

- `repo-docs/` — Mirror of PolyTool code repo documentation
- `claude-memory/` — Claude Desktop sessions, decisions, research, work
- `ris-mirror/` — Auto-generated mirror of Chroma RIS state (gitignored)

## Operating Principles

1. Frontmatter is authoritative.
2. Tier hierarchy: spec/adr/decision > research/concept > session_note/prompt.
3. Never silently overwrite. Record contradictions.
4. Never delete. Archive.

See [[CLAUDE]] for full rules.

## Connections

- [[index]]
- [[CLAUDE]]
- [[claude-memory/spec/vault-redesign-spec]]
