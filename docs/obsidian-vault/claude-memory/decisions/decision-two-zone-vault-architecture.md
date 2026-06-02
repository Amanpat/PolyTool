---
title: "Decision: Two-Zone Obsidian Vault Architecture"
type: decision
status: superseded
source_zone: claude_memory
last_updated: 2026-05-23
lifecycle: reviewed
decided_at: 2026-04-08
decided_by: operator
superseded_by: claude-memory/decisions/adr-0001-three-zone-vault-architecture
tags: [decision]
---
# Decision: Two-Zone Obsidian Vault Architecture

## Context
PolyTool's docs were getting stale and contradictory. Aman was losing track of what's built, what was decided, and research done across sessions. Multiple LLM tools (Claude Code, Claude Project, ChatGPT) all touch different aspects of the project with no shared persistent knowledge system.

## Decision
The Obsidian vault at `docs/obsidian-vault/` uses a two-zone architecture:

- **Zone A (folders 00–07):** Repo mirror. Read-only for all except Claude Code. Reflects actual codebase state from the audit.
- **Zone B (folders 08–12):** Working knowledge. Claude Project can write here. Stores decisions, session notes, research archives, and ideas.

## Alternatives Considered
- **Google Drive as shared knowledge store** → rejected (adds a dependency, vault already in repo)
- **Separate Obsidian vault outside repo** → rejected (loses version control, vault and repo drift apart)
- **Full chat transcripts stored as notes** → rejected (too noisy, 20-100k words per session; structured summaries + `conversation_search` tool is better)

## Consequences
- Claude Code must update Zone A after meaningful code changes
- Claude Project saves decisions immediately during conversations (Option C)
- Session summaries saved on request at end of conversation
- All notes require YAML frontmatter for Dataview queries
- See [[legacy/PolyTool/00-Index/Vault-System-Guide]] for full rules

## Related

- [[legacy/Claude Desktop/08-Research/00-INDEX]]
- [[legacy/PolyTool/00-Index/Dashboard|PolyTool Dashboard (legacy)]]



## Connections

- [[claude-memory/decisions/_index]]
- [[index|Vault Home]]
- [[claude-memory/decisions/adr-0001-three-zone-vault-architecture]]
