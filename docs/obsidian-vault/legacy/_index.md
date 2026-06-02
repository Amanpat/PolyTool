---
title: Legacy Zone Index
type: index
status: active
source_zone: claude_memory
last_updated: 2026-05-23
lifecycle: reviewed
tags:
  - legacy
  - index
  - migration
---

# Legacy Zone

> [!warning] Excluded from active vault
> This folder is excluded from Obsidian's search, graph view, quick-switcher, and link suggestions via `.obsidian/app.json` `userIgnoreFilters`. Files remain on disk for reference and one-by-one migration into the active vault zones (`claude-memory/`, `repo-docs/`).

## Contents

- `Claude Desktop/` — pre-redesign Zone B working memory (folders 08–12). Most content was migrated to `claude-memory/` during Phase 4 of the vault redesign; originals preserved here per the no-deletion rule.
- `PolyTool/` — pre-redesign Zone A repo-docs surface (folders 00–07). Contains older project docs, dashboards, and indexes.
- `10-Session-Notes/` — pre-redesign session notes. Migrated to `claude-memory/session-notes/`; originals preserved.

## Migration Workflow

When feature work surfaces a need for specific legacy content:

1. Identify the specific legacy file by path.
2. Read its content (legacy files remain accessible to obsidian MCP tools — the exclusion only affects Obsidian's UI features, not filesystem-level reads).
3. Rewrite into the active schema with proper frontmatter and a `## Connections` section.
4. Place in the appropriate `claude-memory/` subfolder.
5. Append a log.md entry noting the migration.
6. Optionally mark the legacy file's frontmatter with `migrated_to:` pointing to the new path so future scans can detect migrated content.

Do not bulk-migrate. Let actual feature work surface what matters.

## Why This Zone Exists

The vault redesign (2026-05-23) preserved all pre-redesign content per the no-deletion rule. Most useful content was migrated to `claude-memory/` during Phase 4, but originals were kept in case migration missed something. Rather than archive them out of view immediately, this zone holds them in a clearly-labeled isolated folder where they can be referenced when needed but don't clutter active navigation.

After 1–2 months of active use with no need to consult these files, consider archiving the entire `legacy/` folder to a separate location outside the vault.

## Connections

- [[index|Vault Home]]
- [[claude-memory/spec/vault-redesign-spec]]
- [[claude-memory/work-packets/2026-05-23-vault-redesign-execution-report]]
- [[log|Vault Log]]
