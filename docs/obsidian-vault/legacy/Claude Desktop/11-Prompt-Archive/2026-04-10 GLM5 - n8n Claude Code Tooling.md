---
tags: [prompt-archive]
date: 2026-04-10
model: GLM-5 Turbo
topic: n8n Claude Code Tooling
---
# n8n Claude Code Tooling — Research Results

## Key Findings

### czlonkowski/n8n-mcp — 20 tools total
**Core (7, no API key):** search_nodes, get_node, validate_node, validate_workflow, search_templates, get_template, tools_documentation
**Management (13, needs API key):** n8n_create_workflow, n8n_get_workflow, n8n_update_full_workflow, n8n_update_partial_workflow, n8n_delete_workflow, n8n_list_workflows, n8n_validate_workflow, n8n_autofix_workflow, n8n_workflow_versions, n8n_deploy_template, n8n_test_workflow, n8n_executions, n8n_manage_credentials

### Install for Claude Code (full, with management)
```bash
claude mcp add n8n-mcp \
  -e MCP_MODE=stdio -e LOG_LEVEL=error -e DISABLE_CONSOLE_OUTPUT=true \
  -e N8N_BASE_URL=http://localhost:5678 \
  -e N8N_API_KEY=<key> \
  -- npx n8n-mcp
```

### 7 Complementary Skills
1. Expression Syntax — `{{}}` patterns, `$json`, `$env`
2. MCP Tools Expert — picking tools, validation profiles
3. Workflow Patterns — 5 architectures (webhook, HTTP, DB, AI, scheduled)
4. Validation Expert — interpreting errors, choosing profiles
5. Node Configuration — operation-aware config, property dependencies
6. Code JavaScript — `$input.all()`, return format, DateTime
7. Code Python — Python Code node patterns

Install: `git clone https://github.com/czlonkowski/n8n-skills.git && cp -r n8n-skills/skills/* ~/.claude/skills/`

### Community Nodes Worth Installing
- `n8n-nodes-clickhouse-db` — typed params, bulk insert, upsert, AI-agent ready
- `n8n-nodes-docker-api` — Docker API (logs, start/stop) without Execute Command
- `@jordanburke/n8n-nodes-discord` — rich embeds, buttons, components

### Validation Loop
1. `validate_node(mode='minimal')` per node
2. `validate_node(mode='full', profile='runtime')` 
3. `validate_workflow(workflow)` on full JSON
4. Post-deploy: `n8n_validate_workflow(id)` + `n8n_autofix_workflow(id)`

## Applied To
- Claude Code n8n development workflow
- CLAUDE.md n8n section

## Source
Deep research prompt, [[10-Session-Notes/2026-04-10 RIS Phase 2 Audit Results]]
