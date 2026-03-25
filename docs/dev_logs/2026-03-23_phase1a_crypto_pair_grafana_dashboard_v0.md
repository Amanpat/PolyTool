# Dev Log: Phase 1A Crypto Pair Grafana Dashboard v0

**Date**: 2026-03-23
**Track**: Track 2 / Phase 1A
**Branch**: phase-1A

---

## Objective

Provision a Grafana dashboard wired to the Track 2 ClickHouse event schema
(`polytool.crypto_pair_events`) with all 12 panels required by the
paper-soak runbook. The done condition: operators can open the dashboard
immediately after `docker compose up -d` and run the paper-soak review
without any manual Grafana setup.

---

## What Was Done

### Files Created

- `infra/grafana/dashboards/polyttool_crypto_pair_paper_soak.json`

  Grafana dashboard JSON with 12 panels. Auto-provisioned via the existing
  `infra/grafana/provisioning/dashboards/dashboards.yaml` configuration.
  No changes to provisioning infrastructure were required.

- `docs/features/FEATURE-crypto-pair-grafana-panels-v1.md`

  Feature doc describing dashboard path, UID, datasource, panel inventory,
  and limitations.

### Files Modified

- `docs/CURRENT_STATE.md` — added Track 2 / Phase 1A dashboard status entry.

---

## Research Phase

Before writing the dashboard JSON, read and cross-referenced:

1. `infra/grafana/provisioning/datasources/clickhouse.yaml` — confirmed
   datasource UID `clickhouse-polytool`, type `grafana-clickhouse-datasource`,
   `grafana_ro` user, `defaultDatabase: polytool`.

2. `infra/grafana/provisioning/dashboards/dashboards.yaml` — confirmed
   dashboard root `/var/lib/grafana/dashboards`, `updateIntervalSeconds: 30`.

3. `infra/grafana/dashboards/polyttool_infra_smoke.json` (2-panel smoke
   dashboard) — extracted JSON conventions: `schemaVersion: 39`,
   `pluginVersion: "11.4.0"`, `"format": 1`, `"queryType": "sql"`, UID format
   `polytool-<slug>`, filename prefix `polyttool_`.

4. `infra/grafana/dashboards/polyttool_pnl.json` (4-panel timeseries
   dashboard) — confirmed `"queryType": "timeseries"` pattern for time series
   panels and window function usage in `rawSql`.

5. `infra/clickhouse/initdb/26_crypto_pair_events.sql` — verified all column
   names and types used in the 12 panel queries against the actual DDL.
   `GRANT SELECT ON polytool.crypto_pair_events TO grafana_ro;` already present.

6. `docs/features/FEATURE-crypto-pair-grafana-panels-v0.md` — all 12 SQL
   templates used verbatim after field-name verification.

---

## Panel Summary

| # | Panel                               | Type       | Layout (x,y,w,h)  |
|---|-------------------------------------|------------|-------------------|
| 1 | Paper Soak Scorecard                | table      | 0,0,24,12         |
| 2 | Run Summary Funnel                  | table      | 0,12,24,8         |
| 3 | Maker Fill Rate Floor               | table      | 0,20,12,8         |
| 4 | Partial-Leg Incidence               | table      | 12,20,12,8        |
| 5 | Active Pairs                        | table      | 0,28,24,8         |
| 6 | Pair Cost Distribution              | barchart   | 0,36,12,8         |
| 7 | Est. Profit Per Completed Pair      | timeseries | 12,36,12,8        |
| 8 | Net Profit Per Settlement           | table      | 0,44,12,8         |
| 9 | Cumulative Net PnL                  | timeseries | 12,44,12,8        |
| 10| Daily Trade Count                   | timeseries | 0,52,12,8         |
| 11| Feed State Transition Counts        | timeseries | 12,52,12,8        |
| 12| Recent Feed Safety Events           | table      | 0,60,24,8         |

---

## Design Decisions

### Panel type for Pair Cost Distribution

Used `barchart` (not `timeseries`). The X axis is `pair_cost_bucket`
(a categorical float group), not a timestamp. A `timeseries` panel would
misinterpret the bucketed cost as a time series.

### Panel type for Daily Trade Count

Used `timeseries` with `"drawStyle": "bars"` rather than a bare `barchart`.
The X axis is `toStartOfDay(event_ts)`, which is a proper timestamp. A
`timeseries` panel renders this correctly as time-bucketed bars without the
complex axis configuration that a standalone `barchart` requires for time axes.

### argMax pattern for Active Pairs

Active vs. closed intent detection uses:

```sql
argMax(event_type, tuple(event_ts, recorded_at))
```

The tuple tiebreaker on `recorded_at` matches the `ReplacingMergeTree`
deduplication key, ensuring the most recently written version of any
duplicate row wins in deterministic ordering.

### Field names

All SQL field names verified against the DDL before use. The DDL uses
`float64` for most numeric columns (`paired_cost_usdc`, `net_pnl_usdc`,
etc.) and `UInt32` for count columns. All Grafana `round()` calls are
safe with both.

---

## Scope Boundaries (What Was Not Changed)

- No changes to Python runtime code, paper runner, or ClickHouse schema.
- No changes to `docker-compose.yml` or provisioning infrastructure.
- No modifications to existing dashboards.
- No new Grafana provisioning YAML (the existing `dashboards.yaml` covers the
  new file automatically).

---

## Open Items

- The `$__timeFilter(event_ts)` default range is `now-7d`. For a 48h rerun,
  the operator should widen the range to `now-3d` or a custom window.
- The Pair Cost Distribution panel uses `barchart` which requires Grafana's
  `grafana-charts` plugin (bundled in Grafana 8+). No additional plugin
  install is required with the current Grafana version.
- If the run emits fewer than 20 `paired_exposure_count` rows, the scorecard
  will still render but rubric cells that need paired rows will show `null`.
  This is expected and not a dashboard bug.
