# RIS Parallel WP4-C / WP4-B Activation Codex Verification

**Date:** 2026-04-23  
**Scope:** Read-only verification of the two active RIS Phase 2A lanes after landing.  
**Mutation made by Codex:** This verification log only.

## Files Inspected

- `infra/grafana/dashboards/ris-pipeline-health.json`
- `.env.example`
- `docker-compose.yml`
- `infra/n8n/import_workflows.py`
- `infra/n8n/workflows/ris-n8n-metrics-collector.json`
- `infra/clickhouse/initdb/28_n8n_execution_metrics.sql`
- `docs/dev_logs/2026-04-23_ris_wp4c_grafana_dashboard.md`
- `docs/dev_logs/2026-04-23_ris_wp4b_activation_plumbing.md`
- `docs/dev_logs/2026-04-23_ris_wp4b_metrics_collector.md`

## Commands Run and Results

```powershell
git status --short
```

Result:

```text
 M .env.example
 M docker-compose.yml
 M docs/obsidian-vault/.obsidian/workspace.json
 M docs/obsidian-vault/.smart-env/event_logs/event_logs.ajson
 M infra/n8n/import_workflows.py
?? docs/dev_logs/2026-04-23_ris_parallel_wp3d_wp4a_codex_verification.md
?? docs/dev_logs/2026-04-23_ris_parallel_wp3e_wp4b_codex_verification.md
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
git diff --stat -- .env.example docker-compose.yml infra/n8n/import_workflows.py
```

Result:

```text
 .env.example                  | 4 ++++
 docker-compose.yml            | 5 +++++
 infra/n8n/import_workflows.py | 1 +
 3 files changed, 10 insertions(+)
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
panels = data.get("panels", [])
queries = []
alert_key_paths = []

for panel in panels:
    for target in panel.get("targets", []):
        queries.append({
            "panel": panel.get("title"),
            "type": panel.get("type"),
            "queryType": target.get("queryType"),
            "table": (((target.get("meta") or {}).get("builderOptions") or {}).get("table")),
            "rawSql": target.get("rawSql", ""),
            "datasource_uid": (target.get("datasource") or {}).get("uid"),
        })

    stack = [("", panel)]
    while stack:
        prefix, node = stack.pop()
        if isinstance(node, dict):
            for k, v in node.items():
                key_path = f"{prefix}.{k}" if prefix else k
                if k.lower() == "alert":
                    alert_key_paths.append(key_path)
                stack.append((key_path, v))
        elif isinstance(node, list):
            for idx, item in enumerate(node):
                stack.append((f"{prefix}[{idx}]", item))

print("JSON_VALID=1")
print(f"TITLE={data.get('title')}")
print(f"UID={data.get('uid')}")
print(f"PANEL_COUNT={len(panels)}")
print(f"PANEL_TYPES={[panel.get('type') for panel in panels]}")
print(f"TAGS={data.get('tags')}")
print(f"REFRESH={data.get('refresh')}")
print(f"ALERT_KEYS={alert_key_paths}")
for q in queries:
    sql = q["rawSql"].replace("\n", " ")
    print(
        f"PANEL={q['panel']}|TYPE={q['type']}|QUERYTYPE={q['queryType']}|"
        f"TABLE={q['table']}|DS={q['datasource_uid']}|"
        f"USES_N8N_TABLE={'polytool.n8n_execution_metrics' in sql}"
    )
'@ | python -
```

Result:

```text
JSON_VALID=1
TITLE=PolyTool - RIS Pipeline Health
UID=polytool-ris-pipeline-health
PANEL_COUNT=4
PANEL_TYPES=['timeseries', 'timeseries', 'barchart', 'table']
TAGS=['polytool', 'ris', 'n8n']
REFRESH=1m
ALERT_KEYS=[]
PANEL=Execution Success Rate|TYPE=timeseries|QUERYTYPE=timeseries|TABLE=n8n_execution_metrics|DS=clickhouse-polytool|USES_N8N_TABLE=True
PANEL=Avg Execution Duration (Successful Runs)|TYPE=timeseries|QUERYTYPE=timeseries|TABLE=n8n_execution_metrics|DS=clickhouse-polytool|USES_N8N_TABLE=True
PANEL=Failure Count by Workflow|TYPE=barchart|QUERYTYPE=sql|TABLE=n8n_execution_metrics|DS=clickhouse-polytool|USES_N8N_TABLE=True
PANEL=Latest Run Status per Workflow|TYPE=table|QUERYTYPE=sql|TABLE=n8n_execution_metrics|DS=clickhouse-polytool|USES_N8N_TABLE=True
```

## WP4-C Verification

**Blocking issues:** none.

**Non-blocking issues:**

- The dashboard has no explicit workflow-level RIS filter. All four panel queries read the full `polytool.n8n_execution_metrics` table, so RIS-only scoping is currently implicit via the repo-managed n8n instance/workflow set rather than enforced in SQL.

**Findings:**

- Dashboard JSON parses cleanly.
- Dashboard stays visualization-only: `ALERT_KEYS=[]`, four panels only, ClickHouse datasource only.
- All panels read `polytool.n8n_execution_metrics` and stay within execution-metric health scope.
- No alert-rule payloads, contact-point config, or unrelated dashboard features were introduced.

## WP4-B Activation Plumbing Verification

**Blocking issues:** none.

**Non-blocking issues:** none found.

**Findings:**

- The WP4-B handoff prerequisites are now represented in repo truth:
  - `.env.example` now documents `N8N_API_KEY`.
  - `docker-compose.yml` now passes `CLICKHOUSE_PASSWORD` and `N8N_API_KEY` into the `n8n` service.
  - `infra/n8n/import_workflows.py` now includes `("METRICS_COLLECTOR_ID", "ris-n8n-metrics-collector.json")` in `CANONICAL_WORKFLOWS`.
  - `infra/clickhouse/initdb/28_n8n_execution_metrics.sql` is present for the WP4-A table prerequisite.
- The activation-plumbing diff is narrow and on-scope: `git diff --stat` shows only the three expected files above, with `10` inserted lines total.
- No workflow JSON, alerting config, or unrelated infra churn was introduced by the activation pass.

## Recommendation for Next 2-Lane Split

Keep WP4-B activation plumbing and WP4-C dashboard frozen. Split the next work into:

1. `WP4-D` alert-rule implementation only.
2. Optional RIS-scope hardening only if the shared n8n instance may later host non-RIS workflows; otherwise leave the dashboard SQL unchanged.
