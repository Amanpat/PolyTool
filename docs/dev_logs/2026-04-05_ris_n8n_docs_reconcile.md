# RIS n8n Docs Reconciliation — 2026-04-05

**Quick ID:** 260404-uav
**Scope:** Docs-only. No code, config, or workflow JSON changed.

## Why This Was Needed

quick-260404-t5l fixed the n8n runtime path and ran a smoke test (11/11 workflows
imported, docker exec bridge confirmed). The docs were written before or during that
fix and contained five drifts from the final runtime state.

## Changes Made

### docs/RIS_OPERATOR_GUIDE.md

1. **Last verified date**: Updated from 2026-04-04 to 2026-04-05.

2. **import-workflows.sh usage note (step 5)**: Replaced "Requires curl and jq"
   annotation with accurate description: the script uses
   `docker exec polytool-n8n n8n import:workflow --input=<file>` (docker CLI, no REST
   API). Old note implied basic-auth REST approach (deprecated in n8n 1.88.0).

3. **Runtime verification note (Scheduled Job Workflows section)**: Replaced
   "NOT been runtime-verified" warning with the actual smoke test results:
   build OK, docker-cli v27.3.1 in n8n container, exec bridge verified,
   11/11 workflows imported.

4. **python-on-n8n-PATH warning (troubleshooting block)**: Replaced vague warning
   about `python` not on PATH with an explanation of the docker-exec bridge pattern
   (`docker exec polytool-ris-scheduler python -m polytool ...`). The old warning
   predated the docker-beside-docker architecture decision.

5. **MCP server start command**: Changed `python -m polytool mcp-server --port 8001`
   to `python -m polytool mcp`. The subcommand `mcp-server` does not exist; the
   actual CLI entry is `mcp` (confirmed via `python -m polytool --help`). Added
   clarifying note: "The subcommand is `mcp` (not `mcp-server`)." The URL path
   `/mcp-server/http` in the HTTP transport endpoint is unchanged — that is a path
   component, not the CLI subcommand name.

### docs/adr/0013-ris-n8n-pilot-scoped.md

No changes. Checked for `mcp-server` references and old REST/curl/jq import approach —
none found. The ADR's import reference (`bash infra/n8n/import-workflows.sh [container_name]`)
accurately reflects the docker exec CLI path. The docker-beside-docker runtime pattern
is correctly documented.

### docs/CURRENT_STATE.md

No changes. The quick-260404-t5l section (around line 1454) accurately describes the
runtime fix and smoke test results. No `mcp-server` command references or
"NOT been runtime-verified" language found.

## Commands Run

```bash
grep "Last verified:" docs/RIS_OPERATOR_GUIDE.md
grep -i "NOT been runtime-verified" docs/RIS_OPERATOR_GUIDE.md
grep "mcp-server" docs/RIS_OPERATOR_GUIDE.md
grep "mcp-server" docs/adr/0013-ris-n8n-pilot-scoped.md docs/CURRENT_STATE.md
grep "NOT been runtime-verified" docs/adr/0013-ris-n8n-pilot-scoped.md docs/CURRENT_STATE.md
grep "curl.*import\|jq.*import" docs/adr/0013-ris-n8n-pilot-scoped.md docs/CURRENT_STATE.md
```

## Codex Review

Docs-only changes. Skip tier — no review required per Codex review policy.
