# infra/n8n — PolyTool n8n RIS Pilot

Custom n8n Docker image for the PolyTool Research Intelligence System (RIS) pilot.

See `docs/adr/0013-ris-n8n-pilot-scoped.md` for scope boundaries and decision record.

---

## Image Details

| Field | Value |
|-------|-------|
| Base image | `n8nio/n8n:2.14.2` |
| Extras | docker-cli static binary (v29.3.1, x86_64) |
| Purpose | RIS job scheduling via n8n Execute Command nodes |
| Profile | `ris-n8n` (opt-in, not started in default stack) |

The docker-cli binary is installed via the DHI (Docker Hardened Image) static binary
pattern. It allows n8n workflow nodes to run `docker exec polytool-ris-scheduler python
-m polytool <command>` — the current supported integration path for n8n into the
polytool Python core.

**To start the n8n service:**
```bash
docker compose --profile ris-n8n up -d n8n
# Health check: curl http://localhost:5678/healthz
```

---

## Workflow Source Layout

Runtime tooling and the canonical active RIS pilot workflow source both live in `infra/n8n/`.
`workflows/n8n/` is a stub redirect only — no JSON files live there.

| Path | Status | Notes |
|------|--------|-------|
| `infra/n8n/workflows/ris-unified-dev.json` | Active canonical source | Single unified RIS pilot workflow with 9 sections on one canvas |
| `infra/n8n/workflows/ris-health-webhook.json` | Active canonical support workflow | Dedicated `/webhook/ris-health` smoke/operator health workflow |
| `infra/n8n/workflows/workflow_ids.env` | Active metadata | Tracks the currently deployed unified workflow ID |
| `workflows/n8n/` | Stub redirect only | No JSON files; see stub README for details |

**To import the canonical active workflow into a running n8n container:**
```bash
python infra/n8n/import_workflows.py
```

The helper imports `infra/n8n/workflows/ris-unified-dev.json` plus
`infra/n8n/workflows/ris-health-webhook.json` via the n8n REST API, updates
`infra/n8n/workflows/workflow_ids.env`, and activates both workflows.

The committed unified workflow keeps its schedule triggers disabled by default
so it can be safely activated for manual runs and the `/webhook/ris-ingest`
path while APScheduler remains the default scheduler. Operators who want n8n
to own scheduling must explicitly enable the relevant schedule nodes in the UI.

### Live Grouping and Activation

Workflow grouping and activation happen inside the **n8n Projects UI** — not via the
committed JSON files. After importing the unified workflow, enable it manually in the
n8n UI before its scheduled sections will run.

---

## Claude Code MCP

Instance-level MCP works on community edition n8n >= 2.14.2. The `/mcp-server/http`
endpoint requires a valid JWT bearer token from the n8n Settings UI.

**Note:** Claude Code does NOT expand `${VAR}` template strings in HTTP-type `.mcp.json`
entries. The previous `n8n-instance-mcp` entry (with `${N8N_BASE_URL}` and
`${N8N_MCP_TOKEN}`) has been removed from `.mcp.json` because those literals were sent
as-is, causing connection failure.

To register the n8n MCP server, use `claude mcp add` with the `-s local` scope:

```bash
claude mcp add --transport http \
  --header "Authorization: Bearer <token-from-n8n-settings>" \
  n8n-instance-mcp http://localhost:5678/mcp-server/http \
  -s local
```

Set `N8N_MCP_TOKEN` in your `.env` (gitignored) for reference, but the actual
registration requires the `claude mcp add` command above. See
`docs/dev_logs/2026-04-06_n8n_instance_mcp_connection_debug.md` for root cause
analysis and the token from n8n Settings -> Instance-level MCP.

For full manual setup steps, see:
**`docs/RIS_OPERATOR_GUIDE.md` → "Claude Code MCP connection" → "Instance-level MCP setup"**

---

## Related Docs

- ADR: `docs/adr/0013-ris-n8n-pilot-scoped.md`
- Operator guide: `docs/RIS_OPERATOR_GUIDE.md`
- Operator SOP cheat sheet: `docs/runbooks/RIS_N8N_OPERATOR_SOP.md`
- Discord alerts: `docs/runbooks/RIS_DISCORD_ALERTS.md`
- Env template: `.env.example` (n8n section near the bottom)
- MCP config: `.mcp.json` at repo root
