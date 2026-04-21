---
tags: [prompt-archive]
date: 2026-04-09
model: GLM-5 Turbo
topic: n8n Advanced Patterns
---
# n8n Advanced Patterns for CLI Pipelines — Research Results

## Key Findings
1. **Execution summary:** Use Execute Workflow nodes per pipeline, each returns structured summary JSON. Parent aggregates via Code node into single status item with per-pipeline success/failure/doc counts.
2. **Rich Discord embeds:** HTTP Request node to webhook URL. Color coding: 0x57F287 (green), 0xFEE75C (yellow), 0xED4245 (red). Fields array for per-pipeline inline status. Clickable URL to n8n execution.
3. **Rate limiting:** Retry On Fail (built-in, max tries + wait). Loop Over Items + Wait node for batch pacing. Shell-level retry wrapper for CLI commands.
4. **n8n Variables:** `$vars.key_name` in expressions and Code nodes. May require Pro/Enterprise license — design with env-var fallback.
5. **Execution analytics:** Query `/api/v1/executions` with workflow ID and status filters. Code node computes "failures this week" per pipeline.

## Applied To
- RIS Phase 2 Priority 4 (n8n improvements)
- Unified RIS workflow design

## Source
Deep research prompt, discussed in [[10-Session-Notes/2026-04-09 RIS n8n Workflows and Phase 2 Roadmap]]
