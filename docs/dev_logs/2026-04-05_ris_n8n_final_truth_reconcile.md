# Dev Log: RIS n8n Final Truth Reconcile

**Date:** 2026-04-05
**Quick ID:** 260405-g4j
**Scope:** Docs-only. No runtime code changes, no docker-compose.yml changes, no workflow JSON changes.

---

## Summary

Fixed the final two doc-truth drifts identified by Codex review of the RIS n8n pilot.
Both drifts were introduced when the pilot docs were written: one section described
non-existent HTTP MCP transport; one ADR list omitted a CLI command used in 8 of 11
workflows.

---

## Drifts Fixed

### Drift 1 — RIS_OPERATOR_GUIDE.md MCP section claimed HTTP transport

**File:** `docs/RIS_OPERATOR_GUIDE.md`
**Section:** "Claude Code MCP connection via n8n" (was lines 598-628)

**Before (false):**
- Claimed the MCP server uses HTTP transport at `http://localhost:{MCP_PORT}/mcp-server/http`
- Instructed operator to set `N8N_MCP_BEARER_TOKEN` and create a Header Auth credential in n8n
- Instructed operator to add an HTTP Request node pointing to `host.docker.internal:{MCP_PORT}/mcp-server/http`
- Referenced `MCP_PORT` env var as a required configuration item

**Actual implementation (`tools/cli/mcp_server.py` line 80):**
```python
mcp_app.run(transport="stdio")
```
No `--port` flag. No `--host` flag. No HTTP endpoint. Only `--log-level` is accepted.

CLI confirmation:
```
$ python -m polytool mcp --help
usage: __main__.py [-h] [--log-level {DEBUG,INFO,WARNING,ERROR,CRITICAL}]

Start PolyTool MCP server for Claude Desktop integration.

options:
  -h, --help            show this help message and exit
  --log-level {DEBUG,INFO,WARNING,ERROR,CRITICAL}
                        Logging level (default: WARNING). All logs go to stderr.
```

**After (truthful):**
- Section renamed to "Claude Code MCP connection" (n8n does not use MCP)
- States transport is stdio-only, designed for Claude Desktop via stdio pipe
- States n8n does NOT use MCP; all n8n workflows use the docker-exec bridge pattern
- Removes MCP_PORT, host.docker.internal, bearer token auth, HTTP Request node instructions
- Marks N8N_MCP_BEARER_TOKEN in step-by-step setup as "not operative"
- Adds [PLANNED] note for future HTTP transport

### Drift 2 — ADR 0013 allowed-scope list omitted research-scheduler run-job

**File:** `docs/adr/0013-ris-n8n-pilot-scoped.md`
**Section:** "Allowed scope (RIS only)" (lines 39-48)

**Before:**
```
- python -m polytool research-acquire ...
- python -m polytool research-ingest ...
- python -m polytool research-health
- python -m polytool research-scheduler status
- python -m polytool research-stats summary
```

**Workflow matrix (lines 102-117) used `research-scheduler run-job` in 8 of 11 workflows:**
- ris_academic_ingest.json
- ris_blog_ingest.json
- ris_reddit_polymarket.json
- ris_reddit_others.json
- ris_youtube_ingest.json
- ris_github_ingest.json
- ris_freshness_refresh.json
- ris_weekly_digest.json

CLI confirmation:
```
$ python -m polytool research-scheduler run-job --help
usage: polytool research-scheduler run-job [-h] [--json] job_id

positional arguments:
  job_id      Job id to run (see 'status' for valid ids)

options:
  -h, --help  show this help message and exit
  --json      Output result as JSON
```

**After:**
```
- python -m polytool research-acquire ...
- python -m polytool research-ingest ...
- python -m polytool research-health
- python -m polytool research-scheduler status
- python -m polytool research-scheduler run-job <job_id>
- python -m polytool research-stats summary
```

Allowed-scope list is now internally consistent with the workflow matrix.

---

## Files Changed

| File | What changed |
|------|-------------|
| `docs/RIS_OPERATOR_GUIDE.md` | MCP section rewritten (stdio truth); N8N_MCP_BEARER_TOKEN marked non-operative in setup steps |
| `docs/adr/0013-ris-n8n-pilot-scoped.md` | Added `research-scheduler run-job <job_id>` to allowed-scope list |

---

## Adjacent Drift Scan

After making the above changes, scanned both files for remaining stale references:

- `MCP_PORT` in RIS_OPERATOR_GUIDE.md: 0 remaining (was in MCP section, now removed)
- `host.docker.internal` in MCP context: 0 remaining (was in MCP section, now removed)
- `N8N_MCP_BEARER_TOKEN` references: 2 remaining, both now marked as non-operative
- CLI surfaces in ADR 0013 workflow matrix not in allowed-scope: 0 remaining

No additional drifts found.

---

## No Runtime Changes

Confirmed: no runtime code was changed. No docker-compose.yml was modified. No n8n
workflow JSON was modified. No `.env.example` was modified. This was a docs-only pass.

```
$ git diff --stat HEAD~1 HEAD
 docs/RIS_OPERATOR_GUIDE.md           | 28 ++++++++++++++--------------
 docs/adr/0013-ris-n8n-pilot-scoped.md |  1 +
 2 files changed, 25 insertions(+), 24 deletions(-)
```

---

## Codex Review

Tier: Skip (docs-only, no execution/strategy/risk logic). No review required per
CLAUDE.md Codex Review Policy.
