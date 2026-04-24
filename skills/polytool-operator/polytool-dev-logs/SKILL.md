---
name: polytool-dev-logs
description: Read and summarize recent PolyTool dev logs. Read-only.
version: 1.0.0
category: polytool-operator
metadata:
  hermes:
    tags: [polytool, dev-logs, read-only, operator, progress]
---

# polytool-dev-logs

## Purpose

Provides read-only access to PolyTool dev logs so the operator can get progress summaries, track recent work, or find entries about a specific feature or track.

**Dev logs location (WSL absolute path):**
```
/mnt/d/Coding Projects/Polymarket/PolyTool/docs/dev_logs/
```

File naming convention: `YYYY-MM-DD_slug.md`

Slugs encode the feature area. Common prefixes:
- `ris_` — Research Intelligence System
- `hermes` — Hermes agent work
- `gate2` / `gate3` — validation gates
- `track2` / `crypto` — crypto pair bot
- `simtrader` — SimTrader replay/sweep
- `fee_model` — fee model work
- Codex verification logs: `*_codex_verification.md`

---

## When to Use

Use when the operator asks questions like:
- "What changed today?" / "What was done this week?"
- "What's the latest on RIS Phase 2A?"
- "Show me the last 5 dev logs."
- "Any recent Hermes work?"
- "Summarize Track 2 / Gate 2 / SimTrader progress."
- "What's in the April 23rd dev logs?"
- "How many logs were written this week?"

---

## Hard Boundaries

**ONLY read from:** `/mnt/d/Coding Projects/Polymarket/PolyTool/docs/dev_logs/*.md`

**NEVER:**
- Modify any file — this skill is strictly read-only
- Read files outside `docs/dev_logs/` (for other project files, that is a different skill)
- Run `python -m polytool` commands or any live system commands
- Print API keys, credentials, secrets, or tokens even if they appear in a log file — omit them and note the omission
- Use shell commands beyond the approved set: `ls`, `cat`, `head`, `grep`, `basename`, `wc`, `sort`, `uniq`, `cut`, `sed`, `xargs`

If the operator asks for anything outside this scope, **decline clearly** and name the appropriate skill (e.g., "Use polytool-status for live system state" or "Use polytool-files to read project docs").

---

## Procedure

Use this variable at the top of every command block to handle the path with spaces safely:

```
DEV_LOGS_DIR="/mnt/d/Coding Projects/Polymarket/PolyTool/docs/dev_logs"
```

### Query: Latest N logs (default N=5)

List the most recently modified files:
```bash
DEV_LOGS_DIR="/mnt/d/Coding Projects/Polymarket/PolyTool/docs/dev_logs"
ls -t "$DEV_LOGS_DIR"/*.md | head -5 | xargs -I{} basename {}
```

Then read the header of each (first 80 lines gives scope, files changed, decisions):
```bash
head -80 "/mnt/d/Coding Projects/Polymarket/PolyTool/docs/dev_logs/FILENAME.md"
```

### Query: Keyword filter — by filename slug

```bash
DEV_LOGS_DIR="/mnt/d/Coding Projects/Polymarket/PolyTool/docs/dev_logs"
ls -t "$DEV_LOGS_DIR"/*.md | grep -i "KEYWORD" | xargs -I{} basename {}
```

### Query: Keyword filter — by file content

```bash
DEV_LOGS_DIR="/mnt/d/Coding Projects/Polymarket/PolyTool/docs/dev_logs"
grep -ril "KEYWORD" "$DEV_LOGS_DIR"/*.md 2>/dev/null | xargs -I{} basename {} | sort -r | head -10
```

### Query: Logs for a specific date

```bash
DEV_LOGS_DIR="/mnt/d/Coding Projects/Polymarket/PolyTool/docs/dev_logs"
ls "$DEV_LOGS_DIR"/YYYY-MM-DD_*.md 2>/dev/null | xargs -I{} basename {}
```

### Query: Read a specific file (full)

```bash
cat "/mnt/d/Coding Projects/Polymarket/PolyTool/docs/dev_logs/YYYY-MM-DD_slug.md"
```

### Query: Count logs by date (activity overview)

```bash
DEV_LOGS_DIR="/mnt/d/Coding Projects/Polymarket/PolyTool/docs/dev_logs"
ls "$DEV_LOGS_DIR"/*.md | sed 's|.*/||' | cut -d_ -f1 | sort | uniq -c | sort -rn | head -15
```

### Query: Total log count

```bash
DEV_LOGS_DIR="/mnt/d/Coding Projects/Polymarket/PolyTool/docs/dev_logs"
ls "$DEV_LOGS_DIR"/*.md | wc -l
```

---

## Output Format

Always name the specific files referenced. Use this structure per file:

```
### 2026-04-23_ris_wp3c_health_monitor_summary.md
- **Scope:** WP3-C health monitor structured summary
- **Changed:** n8n Health: Parse Output now emits overallCategory, pipelineStatuses, etc.
- **Test result:** JS syntax validated; JSON valid (76 nodes, 56 connections)
- **Decisions:** 5-line operatorSummary panel added
- **Open:** Next: WP3-D Discord embeds
```

Keep summaries to 3-6 bullet points per file. For multi-file queries, lead with a one-sentence overview before the per-file breakdown. If the operator asks for full detail, provide the full file content.

---

## Guardrails Checklist

Before executing any command, confirm:
- [ ] Target path is inside `docs/dev_logs/`
- [ ] Command is read-only (ls / cat / head / grep / basename / wc / sort / uniq / cut / sed / xargs)
- [ ] Output does not contain API keys, passwords, or secrets

If any check fails: do not execute. Explain the refusal.

---

## Out-of-Scope Refusal Examples

**"Delete the old dev logs"**
→ "This skill is read-only. No file modifications allowed."

**"Run python -m polytool research-health"**
→ "This skill reads dev logs only. Use polytool-status for live system health."

**"Show me config/benchmark_v1.lock.json"**
→ "This skill only reads from docs/dev_logs/. Use polytool-files for other project files."

**"What does the code in packages/research do?"**
→ "This skill only reads dev logs. For code exploration, use polytool-files or ask Claude Code directly."
