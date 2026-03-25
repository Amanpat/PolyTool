# Dev Log: Phase 1A Grafana Dashboard No-Data Diagnostics

**Date**: 2026-03-25
**Scope**: Track 2 / Phase 1A — Crypto Pair Paper Soak Grafana dashboard
**Objective**: Determine definitively whether the empty dashboard is caused by zero rows or broken infrastructure

---

## Diagnostic Summary

All 12 panels of the `PolyTool - Crypto Pair Paper Soak` dashboard display blank
or the default Grafana "No data" placeholder. This log records the live diagnostic
findings and the infrastructure code-review results.

---

## Infrastructure Findings

### 1. ClickHouse HTTP Reachability (port 8123)
**PASS** — ClickHouse responded to `SELECT 1` via HTTP as `grafana_ro`.

```bash
curl -s "http://localhost:8123/?query=SELECT%201" --user grafana_ro:grafana_readonly_local
# Output: 1
```

### 2. Table `polytool.crypto_pair_events` Existence
**PASS** — Table exists in the `polytool` database.

```bash
curl -s "http://localhost:8123/?query=SELECT%20name%20FROM%20system.tables%20WHERE%20database%3D'polytool'%20AND%20name%3D'crypto_pair_events'" --user grafana_ro:grafana_readonly_local
# Output: crypto_pair_events
```

### 3. Row Count in Table
**CONFIRMED ZERO** — Table contains no rows.

```bash
curl -s "http://localhost:8123/?query=SELECT%20count()%20FROM%20polytool.crypto_pair_events" --user grafana_ro:grafana_readonly_local
# Output: 0
```

The `GROUP BY run_id, event_type` query also returned an empty result, confirming
no partial data has landed from any run.

### 4. Datasource UID Match
**PASS (code review)** — All 12 panels use `"datasource.uid": "clickhouse-polytool"`.
`infra/grafana/provisioning/datasources/clickhouse.yaml` defines UID `clickhouse-polytool`.
These match exactly; no mismatch is possible.

### 5. Dashboard Provisioning Path
**PASS (code review)** — `docker-compose.yml` bind-mounts:
- `./infra/grafana/dashboards` → `/var/lib/grafana/dashboards:ro`
- `./infra/grafana/provisioning` → `/etc/grafana/provisioning:ro`

`infra/grafana/provisioning/dashboards/dashboards.yaml` configures:
- `type: file`
- `path: /var/lib/grafana/dashboards`
- `updateIntervalSeconds: 30`

Path chain is intact; the dashboard JSON is loaded automatically.

### 6. `dashboards.yaml` Provider Path Matches Docker Mount
**PASS (code review)** — The provider path `/var/lib/grafana/dashboards` matches
the bind mount destination. No discrepancy.

### 7. `grafana_ro` SELECT Grant
**PASS (code review)** — `infra/clickhouse/initdb/26_crypto_pair_events.sql` includes:
```sql
GRANT SELECT ON polytool.crypto_pair_events TO grafana_ro;
```
The datasource authenticates as `grafana_ro` / `grafana_readonly_local`, which
matches. Queries can execute; they return empty results because there is no data.

---

## Root Cause Verdict

**The dashboard is empty because `polytool.crypto_pair_events` contains zero rows — infrastructure is fully intact and correctly provisioned.**

---

## Soak History

| Quick Task | Date | What Happened | Rows Written |
|-----------|------|---------------|--------------|
| Quick-022 | 2026-03-25 | First paper soak — Binance HTTP 451 geo-block blocked all reference feed data; run aborted before finalization | 0 |
| Quick-023 | 2026-03-25 | Rerun using Coinbase feed — Coinbase confirmed working, but Polymarket had zero active BTC/ETH/SOL 5m/15m markets; runner exited before any pairs could be observed | 0 |
| Quick-024 | 2026-03-25 | Market availability watcher only — `crypto-pair-watch` command shipped; no paper run executed | 0 |

The sink has been wired (Quick-020) and streaming flush added (Quick-021).
However, the sink only writes events when the paper runner reaches finalization
after observing at least one eligible market. None of the soaks reached that
condition.

---

## Path to Live Data

Follow these steps in order:

**a. Confirm Docker is running**
```bash
docker compose ps
```
All services (`clickhouse`, `grafana`) must be `healthy`.

**b. Wait for eligible markets to appear**
```bash
python -m polytool crypto-pair-watch --watch --timeout 3600
```
This command polls the Polymarket API every 60 seconds and exits 0 when
BTC, ETH, or SOL 5m/15m binary pair markets are found. It exits 1 if the
timeout expires with no markets. As of 2026-03-25, markets are absent — this
is the primary blocker.

**c. Launch paper run with `--sink-enabled`**
```bash
python -m polytool crypto-pair-run --sink-enabled [other flags]
```
The `--sink-enabled` flag activates the ClickHouse event sink. Without it,
runs execute normally but write no events to ClickHouse.

**d. Confirm the run reached finalization**
After the run completes, inspect the artifact directory:
```bash
cat <run_dir>/run_manifest.json | python -m json.tool | grep -A3 sink_write_result
```
A successful write shows `"sink_write_result": {"status": "ok", ...}`.
A failed write shows `"status": "error"` with the error message — the run
still completes; the sink soft-fails.

**e. Reload the Grafana dashboard**
The dashboard auto-reloads every 30 seconds (configured via `refresh: 30s`).
No manual action is needed once rows exist in the table.

**f. Check the time range**
Default dashboard range is `now-7d`. If the soak ran more than 7 days ago
(unlikely given current pace), widen the Grafana time picker.

---

## What Was Changed (Task 2 of this quick task)

`noDataText` was added to the `options` block of all 12 dashboard panels in
`infra/grafana/dashboards/polyttool_crypto_pair_paper_soak.json`.

This field is displayed by Grafana's table, timeseries, and barchart panels
when their queries return zero rows. The message reads:

```
No Track 2 events yet. Causes: (1) sink disabled — rerun with --sink-enabled,
(2) no eligible BTC/ETH/SOL 5m-15m markets — run crypto-pair-watch --watch,
(3) Docker not running. Table: polytool.crypto_pair_events
```

This gives the operator enough context to diagnose the no-data state without
needing to check this dev log or the runbook.

The `FEATURE-crypto-pair-grafana-panels-v1.md` feature doc was also updated
with a "No-Data Operator Guide" section containing the step-by-step checklist.

---

## Open Questions / Next Steps

- Market availability is the sole remaining blocker. No code changes are needed.
- Run `python -m polytool crypto-pair-watch --watch --timeout 3600` and wait.
- Once markets appear and a full soak completes with `--sink-enabled`, all 12
  panels will populate immediately.
