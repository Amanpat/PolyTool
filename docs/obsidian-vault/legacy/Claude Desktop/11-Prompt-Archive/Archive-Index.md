---
tags: [index, prompt-archive]
created: 2026-04-08
---
# Prompt Archive

Research prompts and their results from external LLMs (GLM-5 Turbo, ChatGPT, etc.). Preserves research findings that would otherwise be lost when chat windows close.

> [!info] How this works
> When Aman shares a research prompt result in conversation, Claude asks "want me to archive this?" and saves the key findings here with context and links to related vault notes.

## Recent Archives

```dataview
TABLE date as "Date", model as "Model", topic as "Topic", WITHOUT ID file.link as "Research"
FROM "11-Prompt-Archive"
WHERE tags AND contains(tags, "prompt-archive")
SORT date DESC
LIMIT 20
```

## By Model

```dataview
TABLE length(rows) as "Count"
FROM "11-Prompt-Archive"
WHERE tags AND contains(tags, "prompt-archive")
GROUP BY model
```
