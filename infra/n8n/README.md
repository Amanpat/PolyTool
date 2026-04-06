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
-m polytool <command>` — the only supported integration path for n8n into the polytool
Python core.

**To start the n8n service:**
```bash
docker compose --profile ris-n8n up -d n8n
# Health check: curl http://localhost:5678/healthz
```

---

## Workflow JSON Layout

Workflow templates live in `infra/n8n/workflows/`. These are committed JSON files
exported from n8n.

| File | Description |
|------|-------------|
| `ris_academic_ingest.json` | Periodic ArXiv paper ingestion |
| `ris_blog_ingest.json` | Blog post ingestion (every 4h) |
| `ris_freshness_refresh.json` | Re-scan ArXiv for updated papers (Sundays 02:00) |
| `ris_github_ingest.json` | GitHub repo ingestion (Wednesdays 04:00) |
| `ris_health_check.json` | RIS health snapshot via research-health |
| `ris_manual_acquire.json` | On-demand URL acquisition webhook |
| `ris_reddit_others.json` | Reddit secondary subreddits (daily 03:00) |
| `ris_reddit_polymarket.json` | Polymarket subreddit ingestion (every 6h) |
| `ris_scheduler_status.json` | Scheduler status query |
| `ris_weekly_digest.json` | Weekly digest generation (Sundays 08:00) |
| `ris_youtube_ingest.json` | YouTube channel ingestion (Mondays 04:00) |

**To import all workflows into a running n8n container:**
```bash
bash infra/n8n/import-workflows.sh
```

### Live Grouping and Activation

Workflow grouping and activation happen inside the **n8n Projects UI** — not via the
committed JSON files. The JSON files are templates only. After importing, enable each
workflow manually in the n8n UI before it will run on its schedule.

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
- Env template: `.env.example` (n8n section near the bottom)
- MCP config: `.mcp.json` at repo root
