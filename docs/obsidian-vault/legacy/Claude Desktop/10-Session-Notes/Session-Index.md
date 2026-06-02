---
tags: [index, session-notes]
created: 2026-04-08
---
# Session Notes

Structured summaries of every working session between Aman and Claude. Captures decisions made, discussion points, open questions, and action items.

> [!info] How this works
> At the end of each conversation, Aman says "save session" (or similar) and Claude writes a structured summary here. Decisions made during the session are also saved immediately to [[09-Decisions/Decision-Log]].

## Recent Sessions

```dataview
TABLE date as "Date", topics as "Topics", WITHOUT ID file.link as "Session"
FROM "10-Session-Notes"
WHERE tags AND contains(tags, "session-note")
SORT date DESC
LIMIT 20
```
