# WP4-D Scope Fix Codex Verification

**Date:** 2026-04-23  
**Scope:** Read-only verification of the WP4-D stale-pipeline alert scope fix

## Files Inspected

- `infra/grafana/provisioning/alerting/ris-stale-pipeline.yaml`
- `docs/dev_logs/2026-04-23_ris_wp4d_scope_fix.md`

## Commands Run + Exact Results

```text
> git status --short
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
?? docs/dev_logs/2026-04-23_ris_parallel_wp4d_truthsync_fix_codex_verification.md
?? docs/dev_logs/2026-04-23_ris_wp4_monitoring_truth_sync.md
?? docs/dev_logs/2026-04-23_ris_wp4a_clickhouse_ddl.md
?? docs/dev_logs/2026-04-23_ris_wp4b_activation_plumbing.md
?? docs/dev_logs/2026-04-23_ris_wp4c_grafana_dashboard.md
?? docs/dev_logs/2026-04-23_ris_wp4d_scope_fix.md
?? docs/dev_logs/2026-04-23_ris_wp4d_stale_pipeline_alert.md
?? docs/features/vera_hermes_operator_baseline.md
?? infra/clickhouse/initdb/28_n8n_execution_metrics.sql
?? infra/grafana/dashboards/ris-pipeline-health.json
?? infra/grafana/provisioning/alerting/
?? scripts/vera_hermes_healthcheck.sh
?? skills/
```

```text
> git log --oneline -5
d9e9f8b feat(ris): WP3-E — daily digest path at 09:00 UTC with WP3-C structured embed
b2ad984 feat(ris): WP4-B -- hourly n8n execution metrics collector workflow
2eaefd8 feat(ris): WP3-D — Discord embed enrichment with per-pipeline fields
129d376 RIS improvement
a610f18 Hermes Agent containerization
```

```text
> python -m polytool --help
Exit code: 0
CLI help rendered successfully.
```

```text
> python -c "import pathlib,yaml,re,json; p=pathlib.Path(r'infra/grafana/provisioning/alerting/ris-stale-pipeline.yaml'); doc=yaml.safe_load(p.read_text(encoding='utf-8')); rule=doc['groups'][0]['rules'][0]; sql=rule['data'][0]['model']['rawSql']; result={'yaml_parse':'OK','explicit_periodic_scope': bool(re.search(r'workflow_name\\s+IN\\b', sql, re.IGNORECASE)),'includes_main_periodic': 'RIS \\u2014 Research Intelligence System' in sql,'includes_collector_periodic': 'RIS -- n8n Execution Metrics Collector' in sql,'excludes_health_webhook': 'RIS -- Health Webhook' not in sql,'threshold_gt_6h': rule['data'][2]['model']['conditions'][0]['evaluator']['type']=='gt' and rule['data'][2]['model']['conditions'][0]['evaluator']['params']==[6],'noDataState_alerting': rule.get('noDataState')=='Alerting'}; print(json.dumps(result, ensure_ascii=False, indent=2))"
{
  "yaml_parse": "OK",
  "explicit_periodic_scope": true,
  "includes_main_periodic": true,
  "includes_collector_periodic": true,
  "excludes_health_webhook": true,
  "threshold_gt_6h": true,
  "noDataState_alerting": true
}
```

```text
> Get-ChildItem -File 'infra/grafana/provisioning/alerting' | Select-Object -ExpandProperty Name
ris-stale-pipeline.yaml
```

```text
> git status --short --untracked-files=all -- 'infra/grafana/provisioning/alerting' 'docs/dev_logs/2026-04-23_ris_wp4d_scope_fix.md'
?? docs/dev_logs/2026-04-23_ris_wp4d_scope_fix.md
?? infra/grafana/provisioning/alerting/ris-stale-pipeline.yaml
```

## Findings

### Blocking

- None.

### Non-Blocking

- Global worktree churn exists outside WP4-D, but within the scoped artifact set I found only the new alert rule file and the associated landing dev log.

## Verification Summary

- Query A explicitly scopes to the periodic RIS workflows only via `workflow_name IN (...)` in [infra/grafana/provisioning/alerting/ris-stale-pipeline.yaml](../../infra/grafana/provisioning/alerting/ris-stale-pipeline.yaml).
- The webhook-only workflow `RIS -- Health Webhook` is excluded from Query A.
- The threshold logic still encodes `hours_since_success > 6`.
- `noDataState` still maps to `Alerting`.
- The landing log in `docs/dev_logs/2026-04-23_ris_wp4d_scope_fix.md` accurately describes the scope fix and preserved invariants.

## Recommendation

WP4-D is verified complete. I found no remaining blocker in WP4 from this scope-fix pass.

Next step stays inside WP4 operationalization only: reload Grafana provisioning and attach the intended contact point / notification policy if the alert should begin notifying operators.
