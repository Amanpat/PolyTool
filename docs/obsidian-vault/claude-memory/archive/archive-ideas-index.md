---
title: "Ideas & Parking Lot"
type: reference
status: archived
source_zone: claude_memory
last_updated: 2026-05-23
lifecycle: archived
archived_from: Claude Desktop\12-Ideas\Ideas-Index.md
archived_reason: "Dataview index; superseded by claude-memory/ideas/_index.md"
archived_at: 2026-05-23
---

# Ideas & Parking Lot

Raw ideas, feature thoughts, and discussion threads that haven't yet become formal decisions or roadmap items. Nothing gets lost here.

## Parking Lot

Quick-capture ideas that came up mid-conversation. Review periodically to promote to decisions or discard.

```dataview
LIST
FROM "12-Ideas"
WHERE tags AND contains(tags, "idea") AND status = "parked"
SORT date DESC
```

## Explored Ideas

Ideas that were discussed in depth and either promoted to a decision or shelved with reasoning.

```dataview
TABLE date as "Date", status as "Status", WITHOUT ID file.link as "Idea"
FROM "12-Ideas"
WHERE tags AND contains(tags, "idea") AND status != "parked"
SORT date DESC
```

## Connections

- [[claude-memory/archive/_index]]
- [[index|Vault Home]]
