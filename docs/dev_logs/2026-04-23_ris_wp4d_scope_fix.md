# WP4-D Scope Fix: Stale Pipeline Alert — Explicit Periodic Workflow Filter

**Date:** 2026-04-23
**Work packet:** WP4-D fix pass (RIS Phase 2A monitoring)
**Blocker source:** Codex verification (`2026-04-23_ris_parallel_wp4d_truthsync_fix_codex_verification.md`)

---

## What Changed and Why

**Modified:** `infra/grafana/provisioning/alerting/ris-stale-pipeline.yaml`

The original WP4-D alert rule's Query A selected all `workflow_name` values visible in
`polytool.n8n_execution_metrics` over the last 7 days. Codex verification confirmed that
the canonical workflow set is mixed-trigger: `ris-health-webhook.json` is webhook-only
(on-demand) and has no periodic cadence. If that workflow ran once and then stayed idle,
it would produce a false stale alert after 6 hours.

Codex's structural check reported `ALERT_EXPLICIT_WORKFLOW_FILTER=0` (no `workflow_name IN`
or equivalent filter). This fix adds the explicit `AND workflow_name IN (...)` filter to
scope the alert to periodic workflows only.

---

## Periodic Workflow Scope

Determined by inspecting trigger types in the three canonical workflow files:

| File | Workflow name | Triggers | In alert scope |
|------|--------------|----------|----------------|
| `ris-unified-dev.json` | `RIS — Research Intelligence System` | `scheduleTrigger` + `webhook` | **Yes** — primary research pipeline; scheduled runs expected |
| `ris-n8n-metrics-collector.json` | `RIS -- n8n Execution Metrics Collector` | `scheduleTrigger` only | **Yes** — hourly collector; must run periodically |
| `ris-health-webhook.json` | `RIS -- Health Webhook` | `webhook` only | **No** — on-demand; no cadence expectation |

The em dash in `RIS — Research Intelligence System` is U+2014. It is preserved exactly in
the YAML `rawSql` field and in ClickHouse string literals — no escaping needed.

---

## Final Alert Condition

```sql
-- Query A (updated)
SELECT
  workflow_name,
  now() AS time,
  dateDiff('hour', maxIf(started_at, status = 'success'), now()) AS hours_since_success
FROM polytool.n8n_execution_metrics FINAL
WHERE started_at >= now() - INTERVAL 7 DAY
  AND workflow_name IN (
    'RIS — Research Intelligence System',
    'RIS -- n8n Execution Metrics Collector'
  )
GROUP BY workflow_name

-- Expression B: reduce(A, last) per workflow_name series
-- Expression C: threshold — fire when hours_since_success > 6
```

All other rule fields are unchanged:
- `noDataState: Alerting`
- `execErrState: Error`
- `for: "0s"`
- `threshold: gt 6`
- `isPaused: false`

---

## Commands Run / Validation Results

```
python -m polytool --help
```
**Result:** CLI loads cleanly. No import errors.

```python
# Structural validation — re-runs Codex's explicit-filter check
import re, yaml
doc = yaml.safe_load(open('infra/grafana/provisioning/alerting/ris-stale-pipeline.yaml', encoding='utf-8'))
r = doc['groups'][0]['rules'][0]
sql = r['data'][0]['model']['rawSql']
explicit_scope = bool(re.search(r'workflow_name\s+IN\b', sql, re.IGNORECASE))
```

**Result:**
```
YAML parse:              OK
ALERT_EXPLICIT_WORKFLOW_FILTER: 1   (was 0 before fix)
periodic_main_included:  True
periodic_collector_incl: True
webhook_excluded:        True
noDataState=Alerting:    True
threshold gt 6h:         True
isPaused=False:          True
```

`ALERT_EXPLICIT_WORKFLOW_FILTER` flipped from `0` to `1`. All original invariants preserved.

---

## Is WP4 Now Complete?

**Yes.** The full WP4 monitoring stack is complete:

| Packet | Artifact | Status |
|--------|----------|--------|
| WP4-A | `infra/clickhouse/initdb/28_n8n_execution_metrics.sql` | Complete |
| WP4-B | `infra/n8n/workflows/ris-n8n-metrics-collector.json` + activation plumbing | Complete |
| WP4-C | `infra/grafana/dashboards/ris-pipeline-health.json` | Complete |
| WP4-D | `infra/grafana/provisioning/alerting/ris-stale-pipeline.yaml` | Complete (this fix) |

The only outstanding operator steps before the alert goes live are:
1. `docker compose restart grafana` to load the provisioning
2. Create a Discord Contact Point in Grafana UI and attach it to the notification policy

---

**Codex review tier:** Skip (Grafana alerting YAML — infra config, matches policy exclusion).
