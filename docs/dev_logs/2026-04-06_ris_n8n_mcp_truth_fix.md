# RIS n8n MCP Truth Fix -- 2026-04-06

**Quick ID:** 260406-nb7
**Scope:** Docs-only. No code, config, workflow JSON, docker-compose, or .claude changes.

## Why This Was Needed

Codex review found remaining contradictions after the prior doc passes (quick-260406-mnu,
quick-260406-le7, quick-260406-mno). Four operator-facing docs still contained stale
claims disproven by the MCP connection debug session (quick-260406-le7).

## Contradictions Found and Resolved

| File | Location | Old Statement | New Statement |
|------|----------|---------------|---------------|
| docs/CURRENT_STATE.md | Lines 1563-1564 | "Enterprise tier for backend endpoint" | "works on community edition; requires JWT bearer token" |
| docs/CURRENT_STATE.md | Lines 1572-1574 | "Enterprise feature only; not available in community edition" + "informational placeholder" | "works on community edition n8n >= 2.14.2 (not Enterprise-only)" + "compose-side env var read by n8n" |
| docs/adr/0013-ris-n8n-pilot-scoped.md | Lines 97-99 | "Enterprise feature -- not available in the community edition" + "informational" | "works on community edition n8n >= 2.14.2 (not Enterprise-only)" + "compose-side env var read by n8n" |
| docs/RIS_OPERATOR_GUIDE.md | Line 500 | "not operative -- MCP uses stdio, not HTTP" | "operative when instance-level MCP is enabled" |
| docs/RIS_AUDIT_REPORT.md | Line 364 | "start, stop, status, list subcommands" | "start, status, run-job subcommands" |

## Authoritative Truth Source

All corrections based on probe results from quick-260406-le7:
`docs/dev_logs/2026-04-06_n8n_instance_mcp_connection_debug.md`

Key facts:
- POST /mcp-server/http with Accept header + valid JWT -> 200 OK, MCP initialize response
- GET /mcp-server/http without Accept header -> 200 HTML (SPA catch-all, not the backend)
- This works on community edition n8n 2.14.2 (not Enterprise-only)
- research-scheduler real subcommands: status, start, run-job (no stop, no list)

## Files Changed

1. `docs/CURRENT_STATE.md` -- Fixed 2.x migration section; added le7 debug section
2. `docs/adr/0013-ris-n8n-pilot-scoped.md` -- Fixed image-and-versioning MCP paragraph
3. `docs/RIS_OPERATOR_GUIDE.md` -- Fixed step 1 bearer token description
4. `docs/RIS_AUDIT_REPORT.md` -- Fixed CLI table subcommand list
5. `docs/dev_logs/2026-04-06_ris_n8n_mcp_truth_fix.md` -- This file

## Verification

Stale phrases grep (all returned 0):

```
grep -c "Enterprise feature only" docs/CURRENT_STATE.md docs/adr/0013-ris-n8n-pilot-scoped.md docs/RIS_OPERATOR_GUIDE.md
-> 0, 0, 0

grep -c "informational placeholder" docs/CURRENT_STATE.md docs/adr/0013-ris-n8n-pilot-scoped.md
-> 0, 0

grep -c "not operative" docs/RIS_OPERATOR_GUIDE.md
-> 0

grep -c "start, stop, status, list" docs/RIS_AUDIT_REPORT.md
-> 0
```

Corrected phrases grep (all returned > 0):

```
grep -c "community edition" docs/CURRENT_STATE.md
-> 3

grep -c "community edition" docs/adr/0013-ris-n8n-pilot-scoped.md
-> 1

grep -c "start, status, run-job" docs/RIS_AUDIT_REPORT.md
-> 1
```

## What Was NOT Changed

- Code files, workflow JSON, docker-compose.yml, scripts/ -- out of scope
- .claude/** -- out of scope
- infra/n8n/README.md -- already correct (fixed in quick-260406-le7)
- .env.example -- already correct (fixed in quick-260406-le7)

## Codex Review

Tier: Skip (docs-only, no execution/strategy/risk logic).
