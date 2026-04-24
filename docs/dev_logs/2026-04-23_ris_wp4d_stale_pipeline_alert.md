# WP4-D: RIS Stale Pipeline Alert — Grafana Provisioning

**Date:** 2026-04-23
**Work packet:** WP4-D (RIS Phase 2A monitoring infrastructure)
**Lane:** Grafana alert rule provisioning only; WP4-A/WP4-B/WP4-C are prerequisites (all complete)

---

## What Changed and Why

**Created:** `infra/grafana/provisioning/alerting/ris-stale-pipeline.yaml`

WP4-D closes the RIS Phase 2A monitoring stack by adding a stale-pipeline alert rule.
Without this rule, the `polytool.n8n_execution_metrics` data collected by WP4-B and
visualized by WP4-C is passive — operators must manually notice a pipeline gap. The
alert fires automatically when any RIS workflow has gone more than 6 hours without a
successful execution.

The alert rule is provisioned through Grafana's standard provisioning directory
(`/etc/grafana/provisioning/alerting/`). The Docker Compose setup already mounts
`./infra/grafana/provisioning:/etc/grafana/provisioning:ro`, so the new `alerting/`
subdirectory is picked up on the next Grafana restart with no docker-compose changes.

---

## Provisioning Surface Inspection

Before writing, the existing Grafana provisioning surface was inspected:

| Path | Purpose |
|------|---------|
| `infra/grafana/provisioning/dashboards/dashboards.yaml` | Dashboard file-based provisioning |
| `infra/grafana/provisioning/datasources/clickhouse.yaml` | ClickHouse datasource + `grafana_ro` user |
| `infra/grafana/provisioning/alerting/` | **Did not exist** — created by WP4-D |

Grafana 11 (the version in `docker-compose.yml`) supports unified alerting provisioning
via YAML files in `<provisioning_path>/alerting/`. Grafana creates the `PolyTool` folder
on first load if it does not exist.

---

## Final Alert Rule

**File:** `infra/grafana/provisioning/alerting/ris-stale-pipeline.yaml`

| Field | Value | Rationale |
|-------|-------|-----------|
| Group name | `ris-pipeline-health` | Scoped to RIS monitoring only |
| Folder | `PolyTool` | Project-specific folder; auto-created by Grafana 11 if absent |
| Evaluation interval | `10m` | Frequent enough to catch issues within one check; cheap given the 6h threshold |
| Rule UID | `ris-stale-pipeline-alert` | Stable, import-safe identifier |
| Condition | `C` (threshold on B) | Three-step A→B→C chain: query → reduce → threshold |
| `noDataState` | `Alerting` | Per roadmap spec; fires when WP4-B collector is down or table is empty |
| `execErrState` | `Error` | Standard; query errors surface as errors, not false silences |
| Pending period (`for`) | `0s` | Fires immediately on first breach; 6h threshold is already long enough |
| `isPaused` | `false` | Active on import; operators disable via UI if needed during maintenance |

---

## Final Alert Condition

```
Query A (ClickHouse):
  SELECT
    workflow_name,
    now() AS time,
    dateDiff('hour', maxIf(started_at, status = 'success'), now()) AS hours_since_success
  FROM polytool.n8n_execution_metrics FINAL
  WHERE started_at >= now() - INTERVAL 7 DAY
  GROUP BY workflow_name

Expression B (reduce): last(A) per workflow_name series

Expression C (threshold): B > 6
```

**How it fires per workflow:**
`workflow_name` is a dimension in query A. The ClickHouse Grafana plugin with
`format: 1` (timeseries) creates one series per unique `workflow_name` value.
Grafana unified alerting evaluates each series independently, producing one alert
instance per pipeline. This means operators see which specific pipeline is stale,
not just "something is stale."

**Edge cases handled:**
- Workflow with no successful runs in 7-day window:
  `maxIf(started_at, status = 'success')` returns `1970-01-01`, making
  `dateDiff('hour', ...)` ≫ 6 → threshold fires correctly.
- WP4-B collector stopped or table empty:
  Query A returns zero rows → `noDataState: Alerting` fires.
- Workflow ran and failed repeatedly but never succeeded:
  Same as "no success" case above — alert fires.

---

## Scope Assumptions

**RIS-only.** The alert rule is scoped to the `polytool.n8n_execution_metrics` table,
which is populated exclusively by the WP4-B collector workflow. All n8n workflows
that report into this table are RIS-owned pipelines. There is no shared n8n tenant
concern at this stage — the n8n instance is single-tenant on the operator machine.

If non-RIS workflows are later registered in the same table, the alert will cover them
too. This is acceptable: any workflow failing to succeed in 6 hours is genuinely
noteworthy. To restrict to RIS workflows only at that point, add a `workflow_name IN
(...)` filter or a `team = 'ris'` label filter to query A.

**No contact point wired.** This WP provisions the alert rule. Routing to Discord
requires a separate operator step (see below).

---

## Commands Run / Validation Results

```
python -m polytool --help
```
**Result:** CLI loads cleanly. No import errors.

```
python -c "import yaml; ... # structural validation"
```
**Result:**
```
YAML parse: OK
  uid=ris-stale-pipeline-alert
  condition=C
  noDataState=Alerting
  threshold: hours_since_success > 6
  table_hit=True, FINAL=True, per_workflow_label=True
  isPaused=False
```

All assertions passed:
- `apiVersion: 1` ✓
- Single rule in group `ris-pipeline-health` ✓
- Three data steps (A=ClickHouse, B=reduce, C=threshold) ✓
- `datasourceUid: clickhouse-polytool` on step A ✓
- `rawSql` contains: `n8n_execution_metrics`, `FINAL`, `dateDiff`, `maxIf`, `workflow_name` ✓
- Threshold operator `gt`, value `6` ✓
- `noDataState: Alerting` ✓
- `{{ $labels.workflow_name }}` in summary annotation ✓
- `isPaused: false` ✓

No YAML linter is configured in this repo. Validation was performed via `yaml.safe_load`
+ structural assertions.

---

## Remaining Operator Steps (post-WP4-D)

WP4-D provisions the alert rule. Two operator steps are needed before Discord
notifications actually fire:

### Step 1: Restart Grafana to load the provisioning

```bash
docker compose restart grafana
```

On restart, Grafana reads `infra/grafana/provisioning/alerting/ris-stale-pipeline.yaml`,
creates the `PolyTool` folder if absent, and registers the alert rule in group
`ris-pipeline-health`.

Verify in Grafana UI: Alerting → Alert Rules → group `ris-pipeline-health`.

### Step 2: Wire a Discord Contact Point

In the Grafana UI (not provisioned here to avoid storing webhook URL in git):

1. Grafana → Alerting → Contact Points → Add contact point
2. Name: `discord-ris`
3. Type: Discord
4. Webhook URL: paste the Discord webhook URL from your Discord server settings
5. Save

Then, set as the default notification policy (or add a specific policy for `team=ris`):

- Grafana → Alerting → Notification Policies → Edit default policy → Contact point: `discord-ris`

When the `ris-stale-pipeline-alert` fires, Grafana routes to the default policy (or
the `team=ris` policy if one is defined), which delivers the Discord notification.

### Step 3: Verify alert fires correctly

With WP4-B running:
1. Watch Grafana → Alerting → Alert Rules → `ris-stale-pipeline-alert` state
2. State should be `Normal` when all RIS workflows have recent successful executions
3. Disable a workflow in n8n UI, wait 60–70 minutes (6 hours + 1 evaluation cycle),
   and confirm the alert transitions to `Firing`
4. Re-enable the workflow; alert resolves on the next evaluation cycle

---

## What Remains After WP4-D

WP4-A, WP4-B, WP4-C, and WP4-D are all complete. The monitoring stack is:

- ClickHouse table `polytool.n8n_execution_metrics` (WP4-A) ✓
- Hourly collector workflow `ris-n8n-metrics-collector.json` (WP4-B) ✓
- Grafana RIS dashboard `ris-pipeline-health.json` (WP4-C) ✓
- Stale pipeline alert rule `ris-stale-pipeline.yaml` (WP4-D) ✓

The remaining RIS Phase 2A work is WP5 (retrieval benchmark expansion).

---

**Codex review tier:** Skip (Grafana alerting YAML — matches repo Codex policy exclusion
for infra config files).
