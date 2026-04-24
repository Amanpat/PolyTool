# RIS Parallel WP4-D / Monitoring Truth-Sync Fix Codex Verification

**Date:** 2026-04-23
**Scope:** Read-only verification of the corrected WP4-D alerting lane and the monitoring truth-sync lane.
**Mutation made by Codex:** This verification log only.

## Files Inspected

- `infra/grafana/provisioning/alerting/ris-stale-pipeline.yaml`
- `infra/grafana/dashboards/ris-pipeline-health.json`
- `infra/grafana/provisioning/datasources/clickhouse.yaml`
- `infra/grafana/provisioning/dashboards/dashboards.yaml`
- `infra/clickhouse/initdb/28_n8n_execution_metrics.sql`
- `infra/n8n/import_workflows.py`
- `infra/n8n/workflows/ris-n8n-metrics-collector.json`
- `infra/n8n/workflows/ris-unified-dev.json`
- `infra/n8n/workflows/ris-health-webhook.json`
- `.env.example`
- `docker-compose.yml`
- `docs/dev_logs/2026-04-23_ris_wp4d_stale_pipeline_alert.md`
- `docs/dev_logs/2026-04-23_ris_wp4_monitoring_truth_sync.md`

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
?? docs/dev_logs/2026-04-23_operator-hermes-baseline.md
?? docs/dev_logs/2026-04-23_ris_parallel_wp3d_wp4a_codex_verification.md
?? docs/dev_logs/2026-04-23_ris_parallel_wp3e_wp4b_codex_verification.md
?? docs/dev_logs/2026-04-23_ris_parallel_wp4c_wp4bactivate_codex_verification.md
?? docs/dev_logs/2026-04-23_ris_parallel_wp4d_truthsync_codex_verification.md
?? docs/dev_logs/2026-04-23_ris_wp4_monitoring_truth_sync.md
?? docs/dev_logs/2026-04-23_ris_wp4a_clickhouse_ddl.md
?? docs/dev_logs/2026-04-23_ris_wp4b_activation_plumbing.md
?? docs/dev_logs/2026-04-23_ris_wp4c_grafana_dashboard.md
?? docs/dev_logs/2026-04-23_ris_wp4d_stale_pipeline_alert.md
?? docs/features/vera_hermes_operator_baseline.md
?? infra/clickhouse/initdb/28_n8n_execution_metrics.sql
?? infra/grafana/dashboards/ris-pipeline-health.json
?? infra/grafana/provisioning/alerting/
?? scripts/vera_hermes_healthcheck.sh
```

```powershell
git log --oneline -5
```

Result:

```text
d9e9f8b feat(ris): WP3-E -- daily digest path at 09:00 UTC with WP3-C structured embed
b2ad984 feat(ris): WP4-B -- hourly n8n execution metrics collector workflow
2eaefd8 feat(ris): WP3-D -- Discord embed enrichment with per-pipeline fields
129d376 RIS improvement
a610f18 Hermes Agent containerization
```

```powershell
python -m polytool --help
```

Result: exit `0`. CLI loaded with no traceback.

```powershell
@'
import json
import re
from pathlib import Path

import yaml

alert = yaml.safe_load(Path("infra/grafana/provisioning/alerting/ris-stale-pipeline.yaml").read_text(encoding="utf-8"))
dashboard = json.loads(Path("infra/grafana/dashboards/ris-pipeline-health.json").read_text(encoding="utf-8"))
rule = alert["groups"][0]["rules"][0]
query_a = rule["data"][0]["model"]["rawSql"]
threshold = rule["data"][2]["model"]["conditions"][0]["evaluator"]["params"][0]
operator = rule["data"][2]["model"]["conditions"][0]["evaluator"]["type"]
labels = rule.get("labels", {})
summary = rule.get("annotations", {}).get("summary", "")
explicit_scope = bool(re.search(r"workflow_name\s+(?:IN|=|ILIKE|LIKE)", query_a, re.IGNORECASE))

print("ALERT_YAML_VALID=1")
print(f"ALERT_UID={rule['uid']}")
print(f"ALERT_GROUP={alert['groups'][0]['name']}")
print(f"ALERT_CONDITION={rule['condition']}")
print(f"ALERT_NODATA={rule['noDataState']}")
print(f"ALERT_THRESHOLD={operator}:{threshold}")
print(f"ALERT_TABLE={'polytool.n8n_execution_metrics' in query_a}")
print(f"ALERT_FINAL={' FINAL' in query_a}")
print(f"ALERT_WORKFLOW_DIMENSION={'workflow_name' in query_a}")
print(f"ALERT_SUMMARY_LABEL={'workflow_name' in summary}")
print(f"ALERT_TEAM_LABEL={labels.get('team')}")
print(f"ALERT_EXPLICIT_WORKFLOW_FILTER={int(explicit_scope)}")
print("DASHBOARD_JSON_VALID=1")
print(f"DASHBOARD_UID={dashboard['uid']}")
print(f"DASHBOARD_PANEL_COUNT={len(dashboard.get('panels', []))}")
print("DASHBOARD_ALL_CLICKHOUSE_UID=" + str(all(panel.get('datasource', {}).get('uid') == 'clickhouse-polytool' for panel in dashboard.get('panels', []))))
print("DASHBOARD_ALL_USE_METRICS_TABLE=" + str(all('polytool.n8n_execution_metrics' in panel['targets'][0].get('rawSql', '') for panel in dashboard.get('panels', []) if panel.get('targets'))))
'@ | python -
```

Result:

```text
ALERT_YAML_VALID=1
ALERT_UID=ris-stale-pipeline-alert
ALERT_GROUP=ris-pipeline-health
ALERT_CONDITION=C
ALERT_NODATA=Alerting
ALERT_THRESHOLD=gt:6
ALERT_TABLE=True
ALERT_FINAL=True
ALERT_WORKFLOW_DIMENSION=True
ALERT_SUMMARY_LABEL=True
ALERT_TEAM_LABEL=ris
ALERT_EXPLICIT_WORKFLOW_FILTER=0
DASHBOARD_JSON_VALID=1
DASHBOARD_UID=polytool-ris-pipeline-health
DASHBOARD_PANEL_COUNT=4
DASHBOARD_ALL_CLICKHOUSE_UID=True
DASHBOARD_ALL_USE_METRICS_TABLE=True
```

```powershell
@'
import json
from pathlib import Path

files = [
    Path("infra/n8n/workflows/ris-unified-dev.json"),
    Path("infra/n8n/workflows/ris-health-webhook.json"),
    Path("infra/n8n/workflows/ris-n8n-metrics-collector.json"),
]

for path in files:
    data = json.loads(path.read_text(encoding="utf-8"))
    types = sorted({node.get("type", "") for node in data.get("nodes", [])})
    has_schedule = any(t.endswith("scheduleTrigger") for t in types)
    has_webhook = any(t.endswith("webhook") for t in types)
    print(f"{path.name}: schedule={int(has_schedule)} webhook={int(has_webhook)} active={data.get('active', 'NA')}")
'@ | python -
```

Result:

```text
ris-unified-dev.json: schedule=1 webhook=1 active=NA
ris-health-webhook.json: schedule=0 webhook=1 active=NA
ris-n8n-metrics-collector.json: schedule=1 webhook=0 active=False
```

```powershell
python -m pytest tests/ -x -q --tb=short
```

Result: exit `1`.

```text
FAILED tests/test_ris_claim_extraction.py::TestExtractClaimsFromDocument::test_each_claim_has_required_fields
AssertionError: assert 'heuristic_v2_nofrontmatter' == 'heuristic_v1'
==== 1 failed, 2332 passed, 3 deselected, 19 warnings in 78.26s (0:01:18) =====
```

## Lane Verification

### Lane 1: WP4-D stale-pipeline alerting

Status: Provisioned and structurally valid, but not yet scoped correctly.

Blocking:

- `infra/grafana/provisioning/alerting/ris-stale-pipeline.yaml:45-52` queries all `workflow_name` values seen in `polytool.n8n_execution_metrics` during the last 7 days and does not include an explicit workflow allowlist or equivalent filter. The structural validation output confirms `ALERT_EXPLICIT_WORKFLOW_FILTER=0`.
- The current canonical workflow set is mixed-trigger, not schedule-only:
  - `infra/n8n/import_workflows.py:22-25` imports `ris-unified-dev.json`, `ris-health-webhook.json`, and `ris-n8n-metrics-collector.json`.
  - `infra/n8n/workflows/ris-health-webhook.json:2-16` is webhook-triggered.
  - `infra/n8n/workflows/ris-unified-dev.json:20-35` has scheduled paths and `infra/n8n/workflows/ris-unified-dev.json:1225-1235` has a webhook ingest path.
- Because the alert is keyed only by `workflow_name`, any on-demand workflow that ran once within the 7-day lookback and then stayed idle for more than 6 hours can become a false stale alert. That fails the requested "scoped correctly" check even though the file exists and parses.

Non-blocking:

- The rule itself is present at `infra/grafana/provisioning/alerting/ris-stale-pipeline.yaml`.
- Threshold logic is present and valid: `gt:6`.
- `noDataState: Alerting` is present.
- Per-workflow labeling is present via `workflow_name` in the query and annotation summary.

### Lane 2: Monitoring truth-sync pass

Status: Verified as a distinct, dev-log-only truth-sync pass with no monitoring-file churn introduced by that lane.

Blocking:

- None.

Non-blocking:

- `docs/dev_logs/2026-04-23_ris_wp4_monitoring_truth_sync.md:1-5` is a distinct dev log and explicitly records a read-only pass with `Mutations: None`.
- `docs/dev_logs/2026-04-23_ris_wp4_monitoring_truth_sync.md:21-39` keeps scope constrained to the expected monitoring surfaces and prior WP4-A/B/C handoff logs.
- Current monitoring-related repo dirt matches the already-known WP4-A/B/C/WP4-D artifacts plus this truth-sync log; no extra monitoring file was found that appears attributable to the truth-sync lane.

## Decision Notes

- Lane 2 is acceptable as landed: the handoff artifact exists and remained scoped.
- Lane 1 is not acceptable yet: the alert rule is present, but it still needs an explicit periodic-workflow scope before this can be called corrected.
- The full test suite is currently red for an unrelated RIS claim-extraction assertion change. That failure did not affect the monitoring verdict, but it means the requested smoke run is not green.

## Recommendation on the Next Work Unit

1. Narrow `Query A` in `infra/grafana/provisioning/alerting/ris-stale-pipeline.yaml` to the intended periodic RIS workflows only, then rerun this read-only verification.
2. Keep the monitoring truth-sync lane dev-log-only; no additional monitoring cleanup is justified by this pass.
3. Triage the unrelated `tests/test_ris_claim_extraction.py::TestExtractClaimsFromDocument::test_each_claim_has_required_fields` failure separately from the monitoring work.
