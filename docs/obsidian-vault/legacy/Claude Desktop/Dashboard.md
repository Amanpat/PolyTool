---
tags: [meta, dashboard]
created: 2026-04-22
---
# Claude Desktop Dashboard

Unified view of all working knowledge. Zone B at a glance.

---

## Active Focus

![[Current-Focus]]

---

## Recent Decisions

```dataview
TABLE date, status, topics
FROM "Claude Desktop/09-Decisions"
WHERE tags AND contains(tags, "decision")
SORT date DESC
LIMIT 10
```

---

## Recent Sessions

```dataview
TABLE date, topics
FROM "Claude Desktop/10-Session-Notes"
WHERE tags AND contains(tags, "session-note")
SORT date DESC
LIMIT 10
```

---

## Open Ideas

```dataview
TABLE date, status
FROM "Claude Desktop/12-Ideas"
WHERE tags AND contains(tags, "idea") AND status = "parked"
SORT date DESC
```

---

## Recent Prompt Archives

```dataview
TABLE date, model
FROM "Claude Desktop/11-Prompt-Archive"
WHERE tags AND contains(tags, "prompt-archive")
SORT date DESC
LIMIT 10
```

---

## Active Research Threads

```dataview
LIST
FROM "Claude Desktop/08-Research"
SORT file.mtime DESC
LIMIT 10
```

---

## Vault Health

### Recently Modified (Last 7 Days)

```dataview
LIST
FROM "Claude Desktop"
WHERE file.mtime >= date(today) - dur(7 days)
SORT file.mtime DESC
```

### Stale Notes (No Updates in 30+ Days)

```dataview
LIST
FROM "Claude Desktop"
WHERE file.mtime < date(today) - dur(30 days)
SORT file.mtime ASC
LIMIT 10
```
