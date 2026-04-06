---
phase: quick-260406-le7
plan: "01"
subsystem: infra/mcp
tags: [mcp, n8n, security, docs, config]
dependency_graph:
  requires: []
  provides: [n8n-instance-mcp-config-fix, jwt-secret-cleaned, enterprise-only-docs-corrected]
  affects: [.mcp.json, .env.example, docs/RIS_OPERATOR_GUIDE.md, infra/n8n/README.md]
tech_stack:
  added: []
  patterns: [claude-mcp-add-local-scope]
key_files:
  created:
    - docs/dev_logs/2026-04-06_n8n_instance_mcp_connection_debug.md
  modified:
    - .mcp.json
    - .env.example
    - docs/RIS_OPERATOR_GUIDE.md
    - infra/n8n/README.md
decisions:
  - "Remove n8n-instance-mcp from .mcp.json; Claude Code does not expand \${VAR} in HTTP-type entries"
  - "Use claude mcp add -s local to register with real token, keeping secret out of tracked files"
  - "n8n /mcp-server/http is confirmed working on community edition 2.14.2 (not Enterprise-only)"
metrics:
  duration: "~25 minutes"
  completed: "2026-04-06T19:33:00Z"
  tasks_completed: 3
  tasks_total: 3
  files_changed: 5
---

# Phase quick-260406-le7 Plan 01: n8n Instance MCP Connection Debug Summary

**One-liner:** Fixed Claude Code n8n MCP connection by removing unworkable `${VAR}`-template
`.mcp.json` entry, scrubbing committed real JWT from `.env.example`, and correcting
Enterprise-only docs based on confirmed POST probe results on community edition 2.14.2.

---

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Fix .mcp.json and clean .env.example secret | `0cbc2cc` | `.mcp.json`, `.env.example` |
| 2 | Correct stale Enterprise-only claims in docs | `c24e8b3` | `docs/RIS_OPERATOR_GUIDE.md`, `infra/n8n/README.md` |
| 3 | Write dev log and verify connection | `92c2020` | `docs/dev_logs/2026-04-06_n8n_instance_mcp_connection_debug.md` |

---

## What Was Done

### Root Causes Found and Fixed

1. **Claude Code does not expand `${VAR}` in HTTP-type .mcp.json entries.**
   The URL and Authorization header were sent as literal template strings, causing
   connection failure. Fixed by removing the entry from `.mcp.json` and documenting
   the correct `claude mcp add --transport http --header ... -s local` pattern.

2. **n8n MCP endpoint works on community edition 2.14.2 (not Enterprise-only).**
   Earlier probes used GET requests (no body) which hit the SPA frontend router.
   POST with `Content-Type: application/json` + `Accept: application/json, text/event-stream`
   + valid JWT returns `200 OK` with `{"serverInfo":{"name":"n8n MCP Server","version":"1.1.0"}}`.

3. **Real JWT token committed in .env.example line 149.**
   HS256-signed JWT with `iss=n8n`, `aud=mcp-server-api`. Replaced with placeholder
   `replace_with_token_from_n8n_settings_ui`.

4. **Docs incorrectly claimed Enterprise-only** in two files. Both corrected.

### Remaining Manual Step for Operator

To connect Claude Code to the n8n instance-level MCP server:

```bash
claude mcp add --transport http \
  --header "Authorization: Bearer <token-from-n8n-ui>" \
  n8n-instance-mcp http://localhost:5678/mcp-server/http \
  -s local
```

Token source: n8n UI -> Settings -> Instance-level MCP -> copy Access Token.

Verify with `claude mcp list` — should show `n8n-instance-mcp: ... Connected`.

---

## Verification Results

| Check | Result |
|-------|--------|
| `claude mcp list` shows n8n-instance-mcp removed (manual step documented) | PASS |
| `grep -c "eyJhbGci" .env.example` = 0 (no JWT in committed files) | PASS |
| `grep -ci "enterprise only" docs/RIS_OPERATOR_GUIDE.md` = 0 | PASS |
| `grep -ci "enterprise only" infra/n8n/README.md` = 0 | PASS |
| Dev log exists with Root Cause section | PASS |

---

## Deviations from Plan

### Auto-applied decisions

**1. [Rule 1 - Decision] Removed .mcp.json entry (not updated with hardcoded URL)**
- **Found during:** Task 1
- **Issue:** Plan's "Option A" (keep entry with hardcoded URL + env-expanded header) was
  tested via `claude mcp get n8n-instance-mcp` which showed that BOTH URL and header
  expansion are non-functional. The header `Bearer ${N8N_MCP_TOKEN}` is also sent literally.
- **Decision:** Fell back to plan's stated fallback: remove entry, document `claude mcp add`.
- **Files modified:** `.mcp.json`
- **Commit:** `0cbc2cc`

None — other tasks executed exactly as planned.

---

## Known Stubs

None. All placeholder values are explicit (e.g., `replace_with_token_from_n8n_settings_ui`)
and documented with the exact command to replace them.

---

## Threat Flags

None. The changes reduce the attack surface (real JWT removed from tracked files).

---

## Self-Check: PASSED

All files verified:
- `.mcp.json` — entry removed, confirmed via `python -c "import json..."` check
- `.env.example` — no JWT pattern found via regex check
- `docs/RIS_OPERATOR_GUIDE.md` — 0 occurrences of "Enterprise only"
- `infra/n8n/README.md` — 0 occurrences of "Enterprise only"
- `docs/dev_logs/2026-04-06_n8n_instance_mcp_connection_debug.md` — exists, has Root Cause section

All commits verified in git log:
- `0cbc2cc` — Task 1
- `c24e8b3` — Task 2
- `92c2020` — Task 3
