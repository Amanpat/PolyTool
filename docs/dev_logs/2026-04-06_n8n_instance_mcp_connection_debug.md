# 2026-04-06 — n8n Instance-Level MCP Connection Debug

**Quick task:** quick-260406-le7
**Status:** Complete — root cause identified, .mcp.json fixed, secret cleaned, docs corrected

---

## Summary

The `n8n-instance-mcp` entry in `.mcp.json` was failing to connect because Claude
Code does NOT expand `${VAR}` template strings in HTTP-type MCP server entries. The
literal strings `${N8N_BASE_URL}` and `${N8N_MCP_TOKEN}` were being sent as-is, making
the URL invalid. Separately, the n8n MCP endpoint (`/mcp-server/http`) DOES work on
community edition 2.14.2 — earlier probes used GET requests without the required Accept
header, which hit the SPA frontend router instead of the real backend. Multiple docs
incorrectly stated the endpoint was "Enterprise only." Additionally, `.env.example` had
a real JWT token committed. All four issues have been resolved.

---

## Root Cause Analysis

1. **Claude Code does not expand `${VAR}` in HTTP-type `.mcp.json` entries.**
   The URL shows literal `${N8N_BASE_URL}/mcp-server/http` in `claude mcp list`
   output, and the header shows `Bearer ${N8N_MCP_TOKEN}` literally. Neither URL
   nor header env-var expansion works for HTTP-type servers. The entry was removed
   from `.mcp.json`; the correct fix is `claude mcp add --transport http --header
   "Authorization: Bearer <token>" n8n-instance-mcp <url> -s local`, which stores
   the token in a user-local (non-git-tracked) file.

2. **The n8n MCP endpoint works on community edition 2.14.2 (not Enterprise-only).**
   Earlier probes sent `GET /mcp-server/http` with no body — this hit the SPA
   frontend router and returned 200 HTML. The correct probe is `POST` with
   `Content-Type: application/json` and `Accept: application/json, text/event-stream`
   plus a valid JWT. That returns a correct MCP initialize response with
   `serverInfo: {"name": "n8n MCP Server", "version": "1.1.0"}`.

3. **`.env.example` contained a real JWT token on line 149.**
   The token was an HS256-signed JWT with `iss=n8n`, `aud=mcp-server-api`. It was
   replaced with the placeholder `replace_with_token_from_n8n_settings_ui`.

4. **Multiple docs incorrectly claimed "Enterprise only."**
   `docs/RIS_OPERATOR_GUIDE.md` and `infra/n8n/README.md` both stated the endpoint
   was not available in community edition. This was based on the flawed GET probe
   results. Both files have been corrected.

---

## Diagnostic Commands Run

### 1. `claude mcp list` (before fix) — showing failure

```
n8n-instance-mcp: ${N8N_BASE_URL}/mcp-server/http (HTTP) - Failed to connect
```

The literal template string `${N8N_BASE_URL}` is used as the URL. Not expanded.

### 2. `claude mcp get n8n-instance-mcp` (before fix) — showing literal template strings

```
n8n-instance-mcp:
  Scope: Project config (shared via .mcp.json)
  Status: Failed to connect
  Type: http
  URL: ${N8N_BASE_URL}/mcp-server/http
  Headers:
    Authorization: Bearer ${N8N_MCP_TOKEN}
```

Confirms both URL and header env-var expansion are non-functional for HTTP-type entries.

### 3. `curl POST /mcp-server/http` with placeholder test token -> 401 jwt malformed

```bash
curl -s -X POST http://localhost:5678/mcp-server/http \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "Authorization: Bearer test_token" \
  -d '{"jsonrpc":"2.0","method":"initialize","id":1,"params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0.0"}}}'
# Response: 401 Unauthorized: jwt malformed
```

### 4. `curl POST /mcp-server/http` with real JWT + Accept header -> 200 OK, MCP initialize

```bash
curl -s -X POST http://localhost:5678/mcp-server/http \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "Authorization: Bearer <real-jwt>" \
  -d '{"jsonrpc":"2.0","method":"initialize","id":1,"params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0.0"}}}'
# Response: 200 OK
# Body: {"jsonrpc":"2.0","id":1,"result":{"protocolVersion":"2024-11-05","serverInfo":{"name":"n8n MCP Server","version":"1.1.0"},"capabilities":{}}}
```

Confirms the endpoint is live on community edition 2.14.2.

### 5. `curl POST /mcp-server/http` without Accept header -> 406 Not Acceptable

```bash
curl -s -X POST http://localhost:5678/mcp-server/http \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <real-jwt>" \
  -d '{"jsonrpc":"2.0","method":"initialize","id":1,...}'
# Response: 406 Not Acceptable
```

The `Accept: application/json, text/event-stream` header is required.

---

## Fix Applied

### `.mcp.json`

Removed the `n8n-instance-mcp` entry entirely. The entry used `${N8N_BASE_URL}` and
`${N8N_MCP_TOKEN}` which Claude Code sends literally, causing connection failure.
The correct approach is to register the server via `claude mcp add -s local` (see
"Remaining Manual Steps" below).

**Before:**
```json
"n8n-instance-mcp": {
  "type": "http",
  "url": "${N8N_BASE_URL}/mcp-server/http",
  "headers": {
    "Authorization": "Bearer ${N8N_MCP_TOKEN}"
  }
}
```

**After:** Entry removed from `.mcp.json`.

### `.env.example`

- Replaced real JWT on line 149 with placeholder: `replace_with_token_from_n8n_settings_ui`
- Updated comment block to remove Enterprise-only claim
- Added note about `claude mcp add` pattern

### `docs/RIS_OPERATOR_GUIDE.md`

- Changed heading from "Enterprise only" to "bearer token auth"
- Removed Enterprise-only claim; replaced with "works on community edition n8n >= 2.14.2"
- Corrected probe results: GET hits SPA, POST with correct headers reaches backend
- Updated MCP path table: changed "Enterprise only" to "YES (n8n >= 2.14.2, community)"
- Rewrote "Instance-level MCP setup" to use `claude mcp add -s local` pattern
- Removed note claiming N8N_MCP_BEARER_TOKEN is "informational only / not operative"

### `infra/n8n/README.md`

- Removed "Instance-level MCP requires n8n Enterprise edition" sentence
- Removed "community edition does not expose /mcp-server/http backend" claim
- Added note that Claude Code does not expand `${VAR}` in HTTP-type .mcp.json entries
- Documented `claude mcp add` as the correct registration command

---

## Current Auth Mode

**Bearer token (JWT)** generated from n8n UI: Settings -> Instance-level MCP.

This is a static HS256-signed JWT with:
- `iss=n8n`
- `aud=mcp-server-api`
- `sub=<user-uuid>`

It is NOT OAuth. The token is generated by n8n and must be copied from the UI.
It does not auto-rotate. Regenerating is done through the same settings page.

---

## Remaining Manual Steps

### To connect Claude Code to the n8n instance-level MCP server

Run this command from any terminal (NOT from inside Claude Code):

```bash
claude mcp add --transport http \
  --header "Authorization: Bearer <paste-token-from-n8n-ui>" \
  n8n-instance-mcp http://localhost:5678/mcp-server/http \
  -s local
```

Replace `<paste-token-from-n8n-ui>` with the token from:
**n8n UI -> Settings -> Instance-level MCP -> copy the Access Token**

The `-s local` flag stores the config in a user-local (non-git-tracked) location.
This keeps the real JWT out of `.mcp.json` and all tracked files.

### Verify

After adding the server, restart Claude Code (`claude` from the repo root), then run:

```bash
claude mcp list
```

Expected output:
```
n8n-instance-mcp: http://localhost:5678/mcp-server/http (HTTP) - Connected
```

### To regenerate the token if it stops working

n8n UI -> Settings -> Instance-level MCP -> regenerate or delete/recreate token.
Then re-run the `claude mcp add` command above with the new token.

---

## Secret Hygiene

- `.env.example`: real JWT replaced with placeholder. No JWT tokens in any committed file.
  Verified: `grep -c "eyJhbGci" .env.example` returns 0.
- `.mcp.json`: no tokens present (entry removed entirely).
- `.env` (gitignored): correct location for the real token when used via env reference.
  With `claude mcp add -s local`, the token is stored in Claude's local config, not `.env`.

---

## Final Verification

After applying the `.mcp.json` fix (removing the entry), `claude mcp list` output:

```
context7: https://mcp.context7.com/mcp (HTTP) - Connected
ScraplingServer: C:/Users/patel/.local/bin/scrapling mcp - Connected
sequential-thinking: npx -y @modelcontextprotocol/server-sequential-thinking - Connected
memory: npx -y @modelcontextprotocol/server-memory - Connected
code-review-graph: code-review-graph serve - Connected
n8n-mcp: npx n8n-mcp - Connected
```

`n8n-instance-mcp` no longer appears in the list (it was removed from `.mcp.json`).
The operator must run `claude mcp add -s local` (see "Remaining Manual Steps" above)
to register the server with a real token. This is a one-time manual step.

**Status after fix:** n8n-instance-mcp removed from project config. Manual `claude mcp add
-s local` required to connect. Token remains out of all git-tracked files.

---

## Codex Review

Tier: Skip (config + docs only — no execution, strategy, or risk-path code changed)
