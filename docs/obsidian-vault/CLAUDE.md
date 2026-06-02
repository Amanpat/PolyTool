---
title: Vault Operating Rules (Claude)
type: reference
status: active
source_zone: claude_memory
last_updated: 2026-05-23
lifecycle: reviewed
aliases: [CLAUDE, Vault Rules]
---

# Vault Operating Rules

> Rules for Claude Code, Claude Desktop, and any Claude agent reading or writing this vault.
> See [[AGENTS]] for the agent-agnostic version of these rules.

## The Five Hard Rules

1. **Frontmatter is authoritative.** When frontmatter and body contradict, frontmatter wins. Filter and weight content by `status`, `lifecycle`, `confidence`, and `last_updated`.

2. **Respect the tier hierarchy.** Tier 1 documents (`spec`, `adr`, `decision`) override Tier 2 and Tier 3. Never silently contradict a Tier 1 document.

3. **Respect zone discipline.** Never write to `ris-mirror/` (auto-overwritten). Never write to `repo-docs/` (edit the repo instead). New content defaults to `claude-memory/`.

4. **No silent overwrites.** When new information conflicts with existing content, do not overwrite. Either add `## Contradictions` to the new doc, or create an ADR. Mark old doc `superseded_by: <new-doc-id>` and new doc `supersedes: <old-doc-id>`.

5. **No deletion.** Archive instead. Set `status: archived`, move to `claude-memory/archive/`, leave the file in place.

## Operating Sequence

### When reading the vault

1. Read `index.md` to find relevant pages.
2. Read recent entries in `log.md` to understand recency.
3. Read the relevant Tier 1 document.
4. Follow forward links from there.
5. Use frontmatter to filter: skip `status: superseded` and `status: archived` unless explicitly looking for historical context.

### When writing to the vault

1. Check if a document on this topic already exists (search by `type` + `tags` + title).
2. If yes: update existing, or create new with `supersedes:` pointer.
3. If no: create new with full required frontmatter.
4. Append entry to `log.md`: `## [YYYY-MM-DD] <operation> | <title>` followed by 1-2 sentences and a wikilink.
5. Update `index.md` if the new doc is Tier 1 or Tier 2.

## Tier Hierarchy

| Tier | Types | Priority |
|------|-------|----------|
| 1 | `spec`, `adr`, `decision` | Highest — source of truth |
| 2 | `research`, `concept`, `entity`, `mirror` | Supporting context |
| 3 | `session_note`, `work_packet`, `prompt`, `conversation`, `idea`, `reference` | Lowest |

## Zone Discipline

| Zone | Folder | Write Rule |
|------|--------|------------|
| A | `repo-docs/` | Read-only from vault. Edit in repo, then sync. |
| B | `claude-memory/` | Freely writable by humans and agents. |
| C | `ris-mirror/` | Read-only. Written only by the RIS sync service. |

## Frontmatter Schema Summary

Every document must carry:
```yaml
title: string
type: string  # spec | adr | decision | index | log | research | concept | entity | mirror | session_note | work_packet | prompt | conversation | idea | reference
status: string  # draft | active | superseded | archived
source_zone: string  # repo | claude_memory | ris_mirror
last_updated: date  # ISO YYYY-MM-DD
lifecycle: string  # draft | reviewed | verified | stale | archived
```

Full schema: [[claude-memory/spec/vault-redesign-spec]]

## Linking Rules Summary

- Cross-zone links use **full paths**: `[[claude-memory/decisions/my-decision]]`
- Within same folder, short names are acceptable: `[[my-decision]]`
- **Vault-root files** (`index.md`, `log.md`, `CLAUDE.md`, `AGENTS.md`, `README.md`) may be linked by short name from any zone: `[[index]]`, `[[log]]`, `[[CLAUDE]]`, `[[AGENTS]]`, `[[README]]`

## Connections

- [[index]]
- [[AGENTS]]
- [[claude-memory/spec/vault-redesign-spec]]
