---
tags: [meta, system, entry-point]
created: 2026-04-22
updated: 2026-04-22
---
# Agent Entry Point

Read this file first at the start of every session.

---

## Quick Orientation

| What | Where |
|------|-------|
| **Current priorities & blockers** | `Claude Desktop/Current-Focus.md` |
| **Zone B dashboard** | `Claude Desktop/Dashboard.md` |
| **Zone A dashboard** | `PolyTool/00-Index/Dashboard.md` |
| **Vault rules & conventions** | `PolyTool/00-Index/Vault-System-Guide.md` |
| **Decision log** | `Claude Desktop/09-Decisions/Decision-Log.md` |

## Vault Structure

| Folder | Zone | Who Writes |
|--------|------|------------|
| `PolyTool/` | A — Repo Mirror | Claude Code only (read-only for Claude Project) |
| `Claude Desktop/` | B — Working Knowledge | Claude Project writes here |
| `Templates/` | Shared | Templates for new notes |

## Session Protocol

1. Read `Claude Desktop/Current-Focus.md` — know what matters right now
2. If topic may be decided already → check `Claude Desktop/09-Decisions/`
3. For technical ground truth → reference `PolyTool/` Zone A folders
4. **At session end:**
   - Update `Current-Focus.md` if priorities shifted
   - Save decisions → `Claude Desktop/09-Decisions/` using Decision template
   - Offer to save session notes → `Claude Desktop/10-Session-Notes/`

## Templates (in `/Templates`)

| Template | Use For | Creates In |
|----------|---------|------------|
| Decision | Architectural/strategic consensus reached | `Claude Desktop/09-Decisions/` |
| Session-Note | End-of-session summary | `Claude Desktop/10-Session-Notes/` |
| Prompt-Archive | Saving LLM research results | `Claude Desktop/11-Prompt-Archive/` |
| Idea | Parking an idea for later | `Claude Desktop/12-Ideas/` |
| Research | Deep-dive research thread | `Claude Desktop/08-Research/` |

## Rules

- Zone A is **read-only** for Claude Project
- Every note needs YAML frontmatter — Dataview depends on it
- Link everything with `[[wikilinks]]`
- Update `Current-Focus.md` when priorities shift — it's how future sessions orient
- Never skip saving a decision — the #1 failure mode is "we decided this but forgot"
