---
quick_id: 260404-uav
plan: 01
type: docs-only
completed: 2026-04-05
commit: 51d0018
---

# Quick Task 260404-uav: RIS n8n Docs Reconciliation

**One-liner:** Fixed 5 doc drifts in RIS_OPERATOR_GUIDE.md left after quick-260404-t5l runtime smoke test — date, import note, runtime verification status, PATH warning, and MCP command.

## Files Changed

| File | Change |
|------|--------|
| `docs/RIS_OPERATOR_GUIDE.md` | 5 drift fixes applied (see below) |
| `docs/dev_logs/2026-04-05_ris_n8n_docs_reconcile.md` | Created — closeout record |
| `docs/adr/0013-ris-n8n-pilot-scoped.md` | No changes needed |
| `docs/CURRENT_STATE.md` | No changes needed |

## Changes to RIS_OPERATOR_GUIDE.md

1. **Last verified date**: `2026-04-04` → `2026-04-05`

2. **import-workflows.sh step 5 annotation**: Replaced "Requires `curl` and `jq`. Pass alternative URL/user/pass as positional args if needed." with accurate docker exec CLI description. Old note implied the deprecated basic-auth REST import approach.

3. **Runtime verification note (Scheduled Job Workflows section)**: Replaced "have NOT been runtime-verified" with confirmed smoke test results: build OK, docker-cli v27.3.1, exec bridge verified, 11/11 workflows imported.

4. **Python PATH troubleshooting bullet**: Replaced vague "ensure the workflow is running in the polytool container environment" with concrete docker-exec bridge pattern explanation (`docker exec polytool-ris-scheduler python -m polytool ...`).

5. **MCP server start command**: `python -m polytool mcp-server --port 8001` → `python -m polytool mcp`. Added note clarifying the subcommand is `mcp` not `mcp-server`. URL path `/mcp-server/http` in the HTTP transport endpoint is unchanged (path component, not CLI subcommand).

## ADR 0013 and CURRENT_STATE.md

Both confirmed clean. Greps for `mcp-server` (as CLI command), `NOT been runtime-verified`, and `curl.*import` / `jq.*import` all returned 0 matches. No changes required.

## Surprises

None. All five drifts were exactly where the plan described them. ADR 0013 was already updated by quick-260404-t5l (correct docker-beside-docker runtime pattern, custom image section, 11-workflow table). CURRENT_STATE.md already had the t5l smoke test results accurately recorded.
