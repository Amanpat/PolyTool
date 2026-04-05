---
phase: quick-260405-g4j
plan: "01"
subsystem: docs
tags: [docs, ris, n8n, mcp, adr, truth-reconcile]
dependency_graph:
  requires: []
  provides: [truthful-mcp-docs, consistent-adr-0013]
  affects: [docs/RIS_OPERATOR_GUIDE.md, docs/adr/0013-ris-n8n-pilot-scoped.md]
tech_stack:
  added: []
  patterns: [docs-only-fix]
key_files:
  created:
    - docs/dev_logs/2026-04-05_ris_n8n_final_truth_reconcile.md
  modified:
    - docs/RIS_OPERATOR_GUIDE.md
    - docs/adr/0013-ris-n8n-pilot-scoped.md
decisions:
  - "N8N_MCP_BEARER_TOKEN env var left in .env.example but marked non-operative in docs; env file is out of docs scope"
  - "MCP section renamed from 'via n8n' to plain 'Claude Code MCP connection' since n8n does not use MCP"
  - "research-scheduler run-job inserted between status and research-stats in ADR allowed-scope list to maintain logical ordering"
metrics:
  duration: ~15 minutes
  completed: "2026-04-05T15:41:00Z"
  tasks_completed: 2
  files_changed: 3
---

# Phase quick-260405-g4j Plan 01: Final RIS n8n Doc-Truth Reconcile Summary

**One-liner:** Replaced false HTTP-transport MCP section with stdio-only truth and added `research-scheduler run-job` to ADR 0013 allowed-scope, closing the final two doc drifts from the RIS n8n pilot Codex review.

## What Was Done

### Task 1 — Fix MCP section and ADR 0013 allowed-scope

**RIS_OPERATOR_GUIDE.md MCP section:**

The section previously described an HTTP transport at `http://localhost:{MCP_PORT}/mcp-server/http`,
bearer token auth via `N8N_MCP_BEARER_TOKEN`, Header Auth credential setup in n8n, and an HTTP
Request node pointing to `host.docker.internal:{MCP_PORT}`. None of this exists. The actual
implementation (`tools/cli/mcp_server.py`) calls `mcp_app.run(transport="stdio")` with no HTTP
endpoint and no `--port`/`--host` flags.

Replaced with a truthful section stating:
- MCP server uses stdio transport only
- Designed for Claude Desktop integration, not n8n
- n8n uses docker-exec bridge pattern, not MCP
- `N8N_MCP_BEARER_TOKEN` is not operative
- [PLANNED] note for future HTTP transport

Also updated the step-by-step setup to mark `N8N_MCP_BEARER_TOKEN` as non-operative.

**ADR 0013 allowed-scope list:**

The allowed-scope section listed 5 CLI surfaces but omitted `research-scheduler run-job <job_id>`.
The workflow matrix in the same ADR used this command in 8 of 11 workflows. Added it between
`research-scheduler status` and `research-stats summary`.

### Task 2 — Dev log

Created `docs/dev_logs/2026-04-05_ris_n8n_final_truth_reconcile.md` documenting both drifts,
before/after descriptions, CLI output evidence, and explicit no-runtime-change confirmation.

## Commits

| Hash | Message |
|------|---------|
| d95270f | fix(quick-260405-g4j): reconcile RIS doc-truth drifts in MCP section and ADR 0013 |
| c996f4e | docs(quick-260405-g4j): add dev log for RIS n8n final truth reconcile |

## Verification Results

```
$ python -m polytool mcp --help
usage: __main__.py [-h] [--log-level {DEBUG,INFO,WARNING,ERROR,CRITICAL}]
# Only --log-level flag — no --port, no --host confirmed

$ grep -c "stdio" docs/RIS_OPERATOR_GUIDE.md
3

$ grep "research-scheduler run-job" docs/adr/0013-ris-n8n-pilot-scoped.md
- `python -m polytool research-scheduler run-job <job_id>`   (allowed-scope)
| ris_academic_ingest.json | ...  (workflow matrix — 8 rows)
```

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None.

## Threat Flags

None. Removing false HTTP endpoint claims reduces attack surface confusion. No actual endpoint existed.

## Self-Check: PASSED

- `docs/RIS_OPERATOR_GUIDE.md` exists and contains "stdio" (3 occurrences)
- `docs/adr/0013-ris-n8n-pilot-scoped.md` exists and contains "research-scheduler run-job" in allowed-scope
- `docs/dev_logs/2026-04-05_ris_n8n_final_truth_reconcile.md` exists
- Commits d95270f and c996f4e confirmed in git log
- Zero runtime code files changed
