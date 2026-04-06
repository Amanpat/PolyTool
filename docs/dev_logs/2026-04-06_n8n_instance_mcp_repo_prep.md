# n8n Instance-Level MCP: Repo Prep for Claude Code

**Date:** 2026-04-06
**Quick task:** quick-260406-jtl

## Summary

Repo-side preparation for Claude Code to connect to n8n via instance-level MCP (HTTP
transport). Added the `n8n-instance-mcp` server entry to the project `.mcp.json` using
env-var expansion for both the URL and bearer token. Added `N8N_BASE_URL` and
`N8N_MCP_TOKEN` placeholders to `.env.example`. Created `infra/n8n/README.md` with the
workflow template layout and an MCP pointer. Updated `docs/RIS_OPERATOR_GUIDE.md` with a
6-step manual setup procedure for when Enterprise licensing is available.

No runtime behavior changes. No secrets committed. The existing `code-review-graph`
entry in `.mcp.json` is preserved.

---

## Files Changed

| File | Change |
|------|--------|
| `.mcp.json` | Added `n8n-instance-mcp` HTTP server entry alongside `code-review-graph` |
| `.env.example` | Added `N8N_BASE_URL` and `N8N_MCP_TOKEN` placeholders with explanatory comment block in the n8n section |
| `infra/n8n/README.md` | Created: image details, 11-workflow layout table, Claude Code MCP subsection, links to ADR and operator guide |
| `docs/RIS_OPERATOR_GUIDE.md` | Added "Instance-level MCP setup (when Enterprise is available)" subsection with 6 numbered steps; fixed auth table row to use `N8N_MCP_TOKEN` |
| `docs/dev_logs/2026-04-06_n8n_instance_mcp_repo_prep.md` | This file |

---

## Enterprise Prerequisite

n8n community edition 2.14.2 does **not** expose the `/mcp-server/http` backend. This
was probed directly in quick-260406-ido (see
`docs/dev_logs/2026-04-06_n8n_2x_instance_mcp_upgrade.md`):

```
GET /mcp-server/http  -> 200 HTML (SPA frontend router, not a backend API)
GET /rest/mcp         -> 404
GET /api/v1/mcp       -> 404
```

The n8n 2.x frontend assets include `mcp.constants` and `useMcp` modules, confirming the
MCP UI is present — but the backend REST API that actually serves tool calls requires an
Enterprise license.

This prep work is forward-looking: when Enterprise becomes available (or if/when the
community edition unlocks the MCP backend), the repo config is already correct. Until
then, the `.mcp.json` entry is inert — Claude Code will attempt the connection and fail
gracefully.

---

## Env Var Distinction

Two n8n-related MCP env vars coexist in `.env.example`. They are distinct:

| Var | System | Purpose |
|-----|--------|---------|
| `N8N_MCP_BEARER_TOKEN` | n8n container (compose-side) | Read by n8n at container startup to configure the MCP bearer auth endpoint. Has no effect in community edition. |
| `N8N_MCP_TOKEN` | Claude Code (`.mcp.json` env-var expansion) | Used by Claude Code to construct the `Authorization: Bearer ...` header when calling the n8n MCP endpoint. Set this in your local `.env`. |

They may hold the same token value but are consumed by completely different systems.

---

## Remaining Manual Steps

When an n8n Enterprise license is acquired (or community MCP backend is unlocked):

1. Acquire Enterprise license or confirm community MCP backend is available.
2. In the n8n UI: Settings -> Instance-level MCP -> toggle ON.
3. Generate an Access Token from the same settings page. Copy it.
4. For each workflow to expose via MCP: open workflow -> Settings -> toggle "Allow MCP
   access" ON. Only enabled workflows appear as Claude Code tools.
5. In your local `.env` (not `.env.example`):
   ```
   N8N_BASE_URL=http://localhost:5678
   N8N_MCP_TOKEN=<paste-token-from-step-3>
   ```
6. Restart Claude Code from the repo root (`claude` command). It reads `.mcp.json` on
   startup and will now connect to the n8n MCP endpoint.

---

## Codex Review

- Tier: Skip (config + docs only; no strategy, execution, or risk code modified)
- No mandatory review files touched.
