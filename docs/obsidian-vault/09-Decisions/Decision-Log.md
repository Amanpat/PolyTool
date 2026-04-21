---
tags: [index, decisions]
created: 2026-04-08
---
# Decision Log

All architectural, strategic, and design decisions for PolyTool. Each decision is a separate note in this folder with full context, alternatives considered, and consequences.

> [!info] How this works
> When Claude and Aman reach consensus on a decision during a conversation, Claude immediately saves a decision note here. The table below auto-generates from all decision notes via Dataview.

## Active Decisions

```dataview
TABLE date as "Date", status as "Status", WITHOUT ID file.link as "Decision"
FROM "09-Decisions"
WHERE tags AND contains(tags, "decision")
SORT date DESC
```

## Superseded Decisions

```dataview
TABLE date as "Date", supersedes as "Supersedes", WITHOUT ID file.link as "Decision"
FROM "09-Decisions"
WHERE status = "superseded"
SORT date DESC
```
