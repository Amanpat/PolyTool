# RIS Parallel WP4-D / Monitoring Truth-Sync Codex Verification

**Date:** 2026-04-23  
**Scope:** Read-only verification of the two active RIS Phase 2A lanes after landing.  
**Mutation made by Codex:** This verification log only.

## Files Inspected

- `infra/grafana/dashboards/ris-pipeline-health.json`
- `infra/grafana/provisioning/dashboards/dashboards.yaml`
- `infra/grafana/provisioning/datasources/clickhouse.yaml`
- `infra/clickhouse/initdb/28_n8n_execution_metrics.sql`
- `infra/n8n/import_workflows.py`
- `infra/n8n/workflows/ris-n8n-metrics-collector.json`
- `infra/n8n/workflows/ris-unified-dev.json`
- `infra/n8n/workflows/ris-health-webhook.json`
- `.env.example`
- `docker-compose.yml`
- `docs/dev_logs/2026-04-23_ris_wp4c_grafana_dashboard.md`
- `docs/dev_logs/2026-04-23_ris_wp4b_activation_plumbing.md`
- `docs/dev_logs/2026-04-08_ris_phase2_monitoring_truth.md`

## Commands Run and Results

```powershell
git status --short -- .env.example docker-compose.yml infra/clickhouse infra/grafana infra/n8n docs/dev_logs
```

Result:

```text
 M .env.example
 M docker-compose.yml
 M infra/n8n/import_workflows.py
?? docs/dev_logs/2026-04-23_ris_parallel_wp3d_wp4a_codex_verification.md
?? docs/dev_logs/2026-04-23_ris_parallel_wp3e_wp4b_codex_verification.md
?? docs/dev_logs/2026-04-23_ris_parallel_wp4c_wp4bactivate_codex_verification.md
?? docs/dev_logs/2026-04-23_ris_wp4a_clickhouse_ddl.md
?? docs/dev_logs/2026-04-23_ris_wp4b_activation_plumbing.md
?? docs/dev_logs/2026-04-23_ris_wp4c_grafana_dashboard.md
?? infra/clickhouse/initdb/28_n8n_execution_metrics.sql
?? infra/grafana/dashboards/ris-pipeline-health.json
```

```powershell
git log --oneline -5
```

Result:

```text
d9e9f8b feat(ris): WP3-E — daily digest path at 09:00 UTC with WP3-C structured embed
b2ad984 feat(ris): WP4-B -- hourly n8n execution metrics collector workflow
2eaefd8 feat(ris): WP3-D — Discord embed enrichment with per-pipeline fields
129d376 RIS improvement
a610f18 Hermes Agent containerization
```

```powershell
git diff --name-only -- .env.example docker-compose.yml infra/clickhouse infra/grafana infra/n8n
```

Result:

```text
.env.example
docker-compose.yml
infra/n8n/import_workflows.py
```

```powershell
python -m polytool --help
```

Result: exit `0`. CLI rendered `PolyTool - Polymarket analysis toolchain` with no traceback/import error.

```powershell
@'
import json
from pathlib import Path

path = Path("infra/grafana/dashboards/ris-pipeline-health.json")
data = json.loads(path.read_text(encoding="utf-8"))
print("JSON_VALID=1")
print(f"TITLE={data.get('title')}")
print(f"UID={data.get('uid')}")
print(f"PANEL_COUNT={len(data.get('panels', []))}")
print("PANEL_TITLES=" + "|".join(panel.get("title", "") for panel in data.get("panels", [])))
print("HAS_ALERT_KEYS=" + ("1" if "alert" in json.dumps(data).lower() else "0"))
'@ | python -
```

Result:

```text
JSON_VALID=1
TITLE=PolyTool - RIS Pipeline Health
UID=polytool-ris-pipeline-health
PANEL_COUNT=4
PANEL_TITLES=Execution Success Rate|Avg Execution Duration (Successful Runs)|Failure Count by Workflow|Latest Run Status per Workflow
HAS_ALERT_KEYS=0
```

```powershell
Get-ChildItem -Recurse infra/grafana/provisioning | Select-Object FullName
```

Result:

```text
FullName
--------
D:\Coding Projects\Polymarket\PolyTool\infra\grafana\provisioning\dashboards
D:\Coding Projects\Polymarket\PolyTool\infra\grafana\provisioning\datasources
D:\Coding Projects\Polymarket\PolyTool\infra\grafana\provisioning\dashboards\dashboards.yaml
D:\Coding Projects\Polymarket\PolyTool\infra\grafana\provisioning\datasources\clickhouse.yaml
```

```powershell
$matches = Get-ChildItem docs/dev_logs -File | Where-Object { $_.Name -match '^2026-04-23.*wp4d' } | Select-Object -ExpandProperty Name; if ($matches) { $matches } else { 'NO_2026_04_23_WP4D_LOG' }
```

Result:

```text
NO_2026_04_23_WP4D_LOG
```

```powershell
$matches = Get-ChildItem docs/dev_logs -File | Where-Object { $_.Name -match '^2026-04-23.*monitor.*truth|^2026-04-23.*truth.*monitor' } | Select-Object -ExpandProperty Name; if ($matches) { $matches } else { 'NO_2026_04_23_MONITORING_TRUTH_LOG' }
```

Result:

```text
NO_2026_04_23_MONITORING_TRUTH_LOG
```

```powershell
$matches = Get-ChildItem -Recurse infra/grafana -File | Select-String -Pattern 'last success|success age|No Data|alerting|stale pipeline|stale-pipeline'; if ($matches) { $matches | ForEach-Object { "{0}:{1}:{2}" -f $_.Path, $_.LineNumber, $_.Line.Trim() } } else { 'NO_GRAFANA_STALE_PIPELINE_ALERT_MATCHES' }
```

Result:

```text
NO_GRAFANA_STALE_PIPELINE_ALERT_MATCHES
```

## Blocking / Non-Blocking Issues

### Lane 1 — WP4-D stale-pipeline alerting

**Blocking**

- No landed stale-pipeline alert artifact is present in repo truth. `infra/grafana` currently contains only dashboard and datasource provisioning, today has no `WP4-D` dev log, the Grafana sweep returned `NO_GRAFANA_STALE_PIPELINE_ALERT_MATCHES`, and the only changed dashboard JSON reports `HAS_ALERT_KEYS=0`.
- Threshold logic is therefore not landed. The `> 6 hours` / `No Data -> Alerting` rule exists only in prior planning/dev-log text, not in a provisioned file or dashboard payload that can be validated.
- Scope cannot be accepted as correct because no landed rule shows its filter. Current repo truth has three canonical n8n workflows:
  - `RIS — Research Intelligence System` (scheduled)
  - `RIS -- n8n Execution Metrics Collector` (scheduled hourly)
  - `RIS -- Health Webhook` (webhook-triggered, on-demand)
  A per-`workflow_name` stale-success alert must explicitly exclude the webhook workflow or otherwise restrict to periodic workflows. No landed rule demonstrates that scoping.

**Non-blocking**

- None.

### Lane 2 — monitoring truth-sync pass

**Blocking**

- No dedicated `2026-04-23` monitoring truth-sync dev log is present, so there is no lane-local handoff artifact describing intended file set or claimed corrections. That leaves the truth-sync pass itself unverified as a distinct landed work unit.

**Non-blocking**

- None found in the landed monitoring surfaces themselves.

## Findings

- No unrelated monitoring churn is visible in the landed file set. The only tracked monitoring-related edits are `.env.example`, `docker-compose.yml`, and `infra/n8n/import_workflows.py`; the only new monitoring artifacts are `infra/clickhouse/initdb/28_n8n_execution_metrics.sql` and `infra/grafana/dashboards/ris-pipeline-health.json`, plus the associated dev logs.
- The landed monitoring lane is internally consistent:
  - Grafana datasource UID `clickhouse-polytool` matches `infra/grafana/provisioning/datasources/clickhouse.yaml`.
  - Dashboard queries target `polytool.n8n_execution_metrics`.
  - The ClickHouse DDL columns match the collector payload fields (`execution_id`, `workflow_id`, `workflow_name`, `status`, `mode`, `started_at`, `stopped_at`, `duration_seconds`).
  - The dashboard JSON parses cleanly and remains visualization-only.
- The missing piece is specifically `WP4-D` alerting, not a broader monitoring consistency problem.

## Recommendation on the Next Work Unit

1. Land `WP4-D` as an explicit repo artifact plus dev log. The rule should encode threshold logic in the file itself and scope only to periodic workflows, not the webhook path.
2. If a separate monitoring truth-sync pass already exists outside this worktree, land its dev log and only the minimal monitoring-file diff so the pass can be re-verified cleanly.
3. After those two artifacts land, rerun this same read-only verification; the currently landed monitoring surfaces do not need unrelated cleanup first.
