---
phase: quick-260406-jtl
plan: 01
subsystem: n8n / MCP config
tags: [mcp, n8n, config, docs, env]
dependency_graph:
  requires: [quick-260406-ido]
  provides: [n8n-instance-mcp config, operator MCP setup guide]
  affects: [.mcp.json, .env.example, infra/n8n/README.md, docs/RIS_OPERATOR_GUIDE.md]
tech_stack:
  added: []
  patterns: [claude-code-http-mcp, env-var-expansion-in-mcp-json]
key_files:
  created:
    - infra/n8n/README.md
    - docs/dev_logs/2026-04-06_n8n_instance_mcp_repo_prep.md
  modified:
    - .mcp.json
    - .env.example
    - docs/RIS_OPERATOR_GUIDE.md
decisions:
  - "Use ${N8N_BASE_URL} and ${N8N_MCP_TOKEN} env-var expansion in .mcp.json to avoid hardcoded secrets"
  - "N8N_MCP_BEARER_TOKEN (compose-side) and N8N_MCP_TOKEN (Claude Code-side) are kept as distinct vars"
  - "Config is forward-looking: inert until Enterprise license; no runtime changes made"
metrics:
  duration: ~2m 27s
  completed: 2026-04-06
  tasks_completed: 3
  files_changed: 5
---

# Quick Task 260406-jtl: Repo Prep for Claude Code n8n Instance-Level MCP

**One-liner:** Added HTTP MCP server entry to .mcp.json using ${N8N_BASE_URL}/${N8N_MCP_TOKEN} env-var expansion and wrote operator setup guide for n8n Enterprise instance-level MCP.

## What Was Done

Prepared the PolyTool repo for Claude Code to connect to n8n via instance-level MCP
(HTTP transport). No runtime changes — config files, env templates, and operator docs only.

The n8n community edition 2.14.2 does not expose the `/mcp-server/http` backend (probed
in quick-260406-ido). This prep is forward-looking: when Enterprise licensing is available,
an operator fills in two env vars and restarts Claude Code.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Add n8n MCP to .mcp.json and .env.example | 6ac0d3c | `.mcp.json`, `.env.example` |
| 2 | Create infra/n8n/README.md and update RIS_OPERATOR_GUIDE.md | 5b61973 | `infra/n8n/README.md`, `docs/RIS_OPERATOR_GUIDE.md` |
| 3 | Write dev log | d06ce63 | `docs/dev_logs/2026-04-06_n8n_instance_mcp_repo_prep.md` |

## Key Changes

### .mcp.json
Added `n8n-instance-mcp` server entry alongside the existing `code-review-graph` entry:
```json
"n8n-instance-mcp": {
  "type": "http",
  "url": "${N8N_BASE_URL}/mcp-server/http",
  "headers": {
    "Authorization": "Bearer ${N8N_MCP_TOKEN}"
  }
}
```
No secrets committed. Env-var expansion only.

### .env.example
Added two new vars in the n8n section with a full comment block:
- `N8N_BASE_URL=http://localhost:5678`
- `N8N_MCP_TOKEN=<replace-with-access-token-from-n8n-settings-ui>`

Documents the distinction between `N8N_MCP_BEARER_TOKEN` (compose-side) and
`N8N_MCP_TOKEN` (Claude Code-side).

### infra/n8n/README.md (new)
- Image details (n8nio/n8n:2.14.2 + docker-cli v29.3.1)
- Table of all 11 workflow JSON files in `infra/n8n/workflows/`
- Claude Code MCP subsection with config snippet, Enterprise note, and pointer to operator guide
- Links to ADR 0013 and RIS_OPERATOR_GUIDE.md

### docs/RIS_OPERATOR_GUIDE.md
Added "Instance-level MCP setup (when Enterprise is available)" subsection with 6 numbered
steps: enable in UI, copy token, enable per-workflow, set env vars, restart Claude Code,
verify. Also fixed the auth table row: column now shows `N8N_MCP_TOKEN` (the correct
Claude Code-side var name).

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None. All configuration uses placeholder values. The n8n-instance-mcp entry will produce
a connection error at runtime until Enterprise is available; this is the documented and
expected behavior.

## Threat Surface Scan

No new network endpoints, auth paths, or schema changes introduced. The `.mcp.json`
HTTP MCP entry is config-only — no code handles this server; Claude Code handles it
internally. `.env.example` contains only placeholders (no real secrets).

T-jtl-01 and T-jtl-02 mitigations from the plan's threat model are satisfied:
- .mcp.json uses `${ENV_VAR}` expansion only
- .env.example contains placeholder values only

## Self-Check: PASSED

- [x] `/d/Coding Projects/Polymarket/PolyTool/.mcp.json` — exists, valid JSON, both entries present
- [x] `/d/Coding Projects/Polymarket/PolyTool/.env.example` — N8N_BASE_URL and N8N_MCP_TOKEN present
- [x] `/d/Coding Projects/Polymarket/PolyTool/infra/n8n/README.md` — created
- [x] `/d/Coding Projects/Polymarket/PolyTool/docs/RIS_OPERATOR_GUIDE.md` — Instance-level MCP section present
- [x] `/d/Coding Projects/Polymarket/PolyTool/docs/dev_logs/2026-04-06_n8n_instance_mcp_repo_prep.md` — created
- [x] Commit 6ac0d3c — feat: .mcp.json and .env.example
- [x] Commit 5b61973 — feat: infra/n8n/README.md and RIS_OPERATOR_GUIDE.md
- [x] Commit d06ce63 — docs: dev log
