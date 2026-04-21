---
tags: [meta, system]
created: 2026-04-08
---
# Vault System Guide

This document defines how the PolyTool Obsidian vault works. All Claude sessions (Project, Code, or otherwise) must follow these rules.

## Two-Zone Architecture

### Zone A: Repo Mirror (Folders 00–07) — READ ONLY

| Folder | Purpose | Writer |
|--------|---------|--------|
| 00-Index | Dashboard, Done/Todo tracking | Claude Code only |
| 01-Architecture | System design, DB rules, data stack | Claude Code only |
| 02-Modules | Per-module documentation | Claude Code only |
| 03-Strategies | Track 1A/1B/1C status | Claude Code only |
| 04-CLI | CLI command reference | Claude Code only |
| 05-Roadmap | Phase checklists with status | Claude Code only |
| 06-Dev-Log | Convention note (logs live in repo) | Claude Code only |
| 07-Issues | Audit findings and tech debt | Claude Code only |

**Rule:** Claude Project and all other LLMs may READ these folders. Only Claude Code may CREATE or EDIT files here. If Claude Project finds something outdated, it tells Aman who tasks Claude Code.

### Zone B: Working Knowledge (Folders 08+) — CLAUDE PROJECT WRITES

| Folder | Purpose | What Goes Here |
|--------|---------|----------------|
| 08-Research | Deep research threads | Multi-note research on specific topics (wallet discovery, metrics, etc.) |
| 09-Decisions | Decision log | Every architectural/strategic decision with context and rationale |
| 10-Session-Notes | Conversation summaries | Structured notes after each working session |
| 11-Prompt-Archive | LLM research results | Prompts sent to GLM-5/ChatGPT and their key findings |
| 12-Ideas | Raw ideas & parking lot | Ideas that haven't become decisions yet |

## When Claude Writes

### Immediate (during conversation):
- **Decisions**: When Aman and Claude reach consensus → save to `09-Decisions/`
- **Ideas**: When an interesting idea comes up but isn't decided → save to `12-Ideas/`

### On request ("save session" or conversation ending):
- **Session notes**: Structured summary → save to `10-Session-Notes/`

### When Aman shares research:
- **Prompt archives**: Aman pastes a GLM-5/ChatGPT result → Claude asks "archive this?" → save to `11-Prompt-Archive/`

## Note Naming Conventions

| Folder | Format | Example |
|--------|--------|---------|
| 09-Decisions | `Decision - <Topic>.md` | `Decision - Swappable LLM Models.md` |
| 10-Session-Notes | `YYYY-MM-DD <Topic>.md` | `2026-04-08 Obsidian Vault Design.md` |
| 11-Prompt-Archive | `YYYY-MM-DD <Model> - <Topic>.md` | `2026-04-08 GLM5 - AS Binary Markets.md` |
| 12-Ideas | `Idea - <Topic>.md` | `Idea - Cross-Platform Arb Dashboard.md` |
| 08-Research | `NN-<Topic>.md` | `06-Resolution-Timing.md` |

## Required Frontmatter

Every note Claude creates must include YAML frontmatter for Dataview queries:

```yaml
---
tags: [<note-type>]        # decision, session-note, prompt-archive, idea, research
date: YYYY-MM-DD
status: <status>           # accepted/superseded (decisions), parked/explored/promoted/shelved (ideas)
topics: [<topic1>, <topic2>]  # for session notes
model: <model-name>        # for prompt archives (GLM-5-Turbo, ChatGPT, etc.)
---
```

## How Claude Reads the Vault

Before answering questions about project state, Claude checks in this order:
1. **Zone A folders** (02-Modules, 03-Strategies, 05-Roadmap) for what's built
2. **09-Decisions** for what was decided
3. **08-Research** for deep research context
4. **10-Session-Notes** for recent discussion history
5. **Claude memory + conversation_search** as fallback

## Obsidian Plugins in Use

| Plugin | Purpose |
|--------|---------|
| **Dataview** | Auto-generates tables and lists from frontmatter across the vault |
| **Smart Connections** | Semantic search — find notes by meaning, not just keywords |
| **Templater** | Consistent note templates with auto-populated fields |
| **Tasks** | Queryable checkboxes across the entire vault |

## Anti-Drift Rules

1. **Never skip saving a decision.** If consensus is reached, save immediately. The number one failure mode is "we decided this but forgot."
2. **Check vault before re-discussing.** If Aman raises a topic, search the vault first — it may already be decided.
3. **Link everything.** Every note should have at least one `[[backlink]]` to related notes.
4. **Don't duplicate repo docs.** Zone B notes reference Zone A notes, they don't copy content from them.
5. **Frontmatter is mandatory.** No note without tags and date — Dataview queries depend on it.
