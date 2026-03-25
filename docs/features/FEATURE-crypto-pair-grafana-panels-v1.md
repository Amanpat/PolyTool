# Feature: Crypto Pair Grafana Dashboard v1 (Provisioned)

**Status**: Provisioned
**Track**: Track 2 / Phase 1A
**Date**: 2026-03-23
**Related**: `FEATURE-crypto-pair-grafana-panels-v0.md`, `SPEC-crypto-pair-clickhouse-event-schema-v0.md`, `CRYPTO_PAIR_PAPER_SOAK_RUNBOOK.md`

---

## What Was Shipped

A Grafana dashboard provisioning file wired to the Track 2 ClickHouse event
schema (`polytool.crypto_pair_events`). The dashboard is auto-provisioned at
Docker Compose startup and requires no manual Grafana import.

**v0** (`FEATURE-crypto-pair-grafana-panels-v0.md`) was the query pack: SQL
templates only, no dashboard JSON.

**v1** (this document) is the provisioned dashboard: all 12 required panels
from the paper-soak runbook encoded in a Grafana JSON file, ready to use
immediately after `docker compose up -d`.

---

## Dashboard File

```
infra/grafana/dashboards/polyttool_crypto_pair_paper_soak.json
```

Auto-provisioned via:

```
infra/grafana/provisioning/dashboards/dashboards.yaml
```

Grafana maps that directory to `/var/lib/grafana/dashboards`. The dashboard
reloads every 30 seconds without a Grafana restart.

---

## Dashboard Identity

| Field         | Value                                                |
|---------------|------------------------------------------------------|
| UID           | `polytool-crypto-pair-paper-soak`                    |
| Title         | `PolyTool - Crypto Pair Paper Soak`                  |
| Tags          | `polytool`, `track2`, `crypto-pair`                  |
| Schema ver.   | 39                                                   |
| Plugin ver.   | 11.4.0                                               |
| Default range | `now-7d` to `now`                                    |
| Datasource    | `ClickHouse` (UID `clickhouse-polytool`)             |
| Auth user     | `grafana_ro` (SELECT only, `polytool.crypto_pair_events`) |

---

## Preconditions

- `docker compose up -d` is running
- The paper run was launched with `--sink-enabled`
- The run finalized successfully (`stopped_reason = "completed"`)
- `run_manifest.json["sink_write_result"]` shows a successful write

Because the current paper runner batch-emits events only at finalization, this
dashboard is for post-run review, not live monitoring mid-soak.

---

## Panel Inventory

All 12 panels required by `docs/runbooks/CRYPTO_PAIR_PAPER_SOAK_RUNBOOK.md`
Step 5 are present.

| # | Panel Title                          | Type       | Source Event Type(s)                         |
|---|--------------------------------------|------------|----------------------------------------------|
| 1 | Paper Soak Scorecard                 | table      | `run_summary`, `partial_exposure_updated`, `simulated_fill_recorded`, `pair_settlement_completed`, `safety_state_transition` |
| 2 | Run Summary Funnel                   | table      | `run_summary`                                |
| 3 | Maker Fill Rate Floor                | table      | `run_summary`, `simulated_fill_recorded`     |
| 4 | Partial-Leg Incidence                | table      | `run_summary`                                |
| 5 | Active Pairs                         | table      | `partial_exposure_updated`, `pair_settlement_completed` |
| 6 | Pair Cost Distribution               | barchart   | `partial_exposure_updated` (exposure_status = 'paired') |
| 7 | Estimated Profit Per Completed Pair  | timeseries | `partial_exposure_updated` (exposure_status = 'paired') |
| 8 | Net Profit Per Settlement            | table      | `pair_settlement_completed`                  |
| 9 | Cumulative Net PnL                   | timeseries | `pair_settlement_completed`                  |
| 10 | Daily Trade Count                   | timeseries | `simulated_fill_recorded`                    |
| 11 | Feed State Transition Counts        | timeseries | `safety_state_transition` (state_key = 'reference_feed') |
| 12 | Recent Feed Safety Events           | table      | `safety_state_transition` (state_key = 'reference_feed') |

### Panel 1 — Paper Soak Scorecard

The primary operator table. Multi-CTE JOIN covering all rubric metrics in one
row per `run_id`:

- `intents`, `paired_intents`, `partial_intents`, `settled_pairs`
- `pair_completion_rate`
- `maker_fill_rate_floor`
- `partial_leg_incidence`
- `avg_completed_pair_cost_usdc`
- `est_profit_per_completed_pair_usdc`
- `avg_net_pnl_per_settlement_usdc`
- `stale_transitions`, `disconnect_transitions`, `latest_feed_state`
- `open_unpaired_notional_usdc`
- `run_net_pnl_usdc`

### Panel 5 — Active Pairs

Uses `argMax(event_type, tuple(event_ts, recorded_at))` to find the latest
state per `intent_id`. Rows where the latest event is
`partial_exposure_updated` are still active; those where it is
`pair_settlement_completed` are closed. This panel shows only the active rows.

### Panel 9 — Cumulative Net PnL

Uses a window function:

```sql
sum(net_pnl_usdc) OVER (
    PARTITION BY run_id
    ORDER BY time, event_id
    ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
)
```

---

## Query Pack Source

All SQL was taken verbatim from `docs/features/FEATURE-crypto-pair-grafana-panels-v0.md`
(Panels 1–12). Field names were verified against
`infra/clickhouse/initdb/26_crypto_pair_events.sql` before inclusion — no
discrepancies found.

---

## Opening the Dashboard

After `docker compose up -d`:

1. Open `http://localhost:3000`
2. Browse to **Dashboards → PolyTool - Crypto Pair Paper Soak**

Or use the direct URL pattern:
`http://localhost:3000/d/polytool-crypto-pair-paper-soak`

---

## Limitations (inherited from v0)

- Maker fill rate is a conservative floor; Track 2 schema does not expose
  per-leg selected-order counts as first-class columns.
- `safety_state_transition` covers only lifted feed-state events; broader safety
  verdicts still require `run_manifest.json` and `runtime_events.jsonl`.
- The paper runner emits ClickHouse rows only at finalization. Use the artifact
  directory and `runtime_events.jsonl` for mid-soak liveness checks.
