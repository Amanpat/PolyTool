---
title: "Session Notes"
type: reference
status: archived
source_zone: claude_memory
last_updated: 2026-05-23
lifecycle: archived
archived_from: Claude Desktop\10-Session-Notes\Session-Index.md
archived_reason: "Dataview index; superseded by claude-memory/session-notes/_index.md"
archived_at: 2026-05-23
---

# Session Notes

Structured summaries of every working session between Aman and Claude. Captures decisions made, discussion points, open questions, and action items.

> [!info] How this works
> At the end of each conversation, Aman says "save session" (or similar) and Claude writes a structured summary here. Decisions made during the session are also saved immediately to [[legacy/Claude Desktop/09-Decisions/Decision-Log]].

## Recent Sessions

```dataview
TABLE date as "Date", topics as "Topics", WITHOUT ID file.link as "Session"
FROM "10-Session-Notes"
WHERE tags AND contains(tags, "session-note")
SORT date DESC
LIMIT 20
```

## Connections

- [[claude-memory/archive/_index]]
- [[index|Vault Home]]
