# Summary

This document defines the Grafana-ready query layer for the Phase 1A crypto
pair paper soak.

All queries assume the Track 2 event table:

- `polytool.crypto_pair_events`

All queries assume paper mode:

- `mode = 'paper'`

No panel UID or dashboard JSON assumptions are made here. This is a query pack,
not a dashboard export.

---

## Preconditions

- the paper run must be launched with `--sink-enabled`
- the run must have finalized successfully
- `run_manifest.json["sink_write_result"]` must show a successful write

Because the current paper runner batch-emits events only at finalization, these
queries are for post-run review, not live monitoring mid-soak.

---

## Suggested Variables

### Recent Run Selector

Use this as an optional dashboard variable or table panel:

```sql
SELECT
    run_id AS __value,
    concat(formatDateTime(max(event_ts), '%Y-%m-%d %H:%M:%S UTC'), ' | ', run_id) AS __text
FROM polytool.crypto_pair_events
WHERE mode = 'paper'
  AND event_type = 'run_summary'
GROUP BY run_id
ORDER BY max(event_ts) DESC
LIMIT 50;
```

Optional filter placeholders for the queries below:

- `AND run_id = '<run_id>'`
- `AND symbol IN ('BTC', 'ETH', 'SOL')`
- `AND duration_min IN (5, 15)`

If you wire Grafana variables, replace the placeholders with your datasource's
preferred variable syntax.

---

## Panel 1 - Paper Soak Scorecard

Use this as the main operator table. It covers the primary rubric metrics in one
place.

```sql
WITH summary AS (
    SELECT
        run_id,
        max(event_ts) AS summary_ts,
        max(order_intents_generated) AS order_intents_generated,
        max(paired_exposure_count) AS paired_exposure_count,
        max(partial_exposure_count) AS partial_exposure_count,
        max(settled_pair_count) AS settled_pair_count,
        max(open_unpaired_notional_usdc) AS open_unpaired_notional_usdc,
        max(net_pnl_usdc) AS run_net_pnl_usdc
    FROM polytool.crypto_pair_events
    WHERE mode = 'paper'
      AND event_type = 'run_summary'
      AND $__timeFilter(event_ts)
    GROUP BY run_id
),
paired AS (
    SELECT
        run_id,
        avg(paired_cost_usdc) AS avg_completed_pair_cost_usdc,
        avg(1 - paired_net_cash_outflow_usdc) AS est_profit_per_completed_pair_usdc
    FROM polytool.crypto_pair_events
    WHERE mode = 'paper'
      AND event_type = 'partial_exposure_updated'
      AND exposure_status = 'paired'
      AND $__timeFilter(event_ts)
    GROUP BY run_id
),
fills AS (
    SELECT
        run_id,
        count() AS fill_rows
    FROM polytool.crypto_pair_events
    WHERE mode = 'paper'
      AND event_type = 'simulated_fill_recorded'
      AND $__timeFilter(event_ts)
    GROUP BY run_id
),
settlements AS (
    SELECT
        run_id,
        count() AS settlement_rows,
        avg(net_pnl_usdc) AS avg_net_pnl_per_settlement_usdc
    FROM polytool.crypto_pair_events
    WHERE mode = 'paper'
      AND event_type = 'pair_settlement_completed'
      AND $__timeFilter(event_ts)
    GROUP BY run_id
),
safety AS (
    SELECT
        run_id,
        countIf(to_state = 'stale') AS stale_transitions,
        countIf(to_state = 'disconnected') AS disconnect_transitions,
        argMax(to_state, tuple(event_ts, recorded_at)) AS latest_feed_state
    FROM polytool.crypto_pair_events
    WHERE mode = 'paper'
      AND event_type = 'safety_state_transition'
      AND state_key = 'reference_feed'
      AND $__timeFilter(event_ts)
    GROUP BY run_id
)
SELECT
    s.run_id,
    s.summary_ts,
    s.order_intents_generated AS intents,
    s.paired_exposure_count AS paired_intents,
    s.partial_exposure_count AS partial_intents,
    s.settled_pair_count AS settled_pairs,
    round(s.paired_exposure_count / nullIf(s.order_intents_generated, 0), 4) AS pair_completion_rate,
    round(coalesce(f.fill_rows, 0) / nullIf(2 * s.order_intents_generated, 0), 4) AS maker_fill_rate_floor,
    round(s.partial_exposure_count / nullIf(s.order_intents_generated, 0), 4) AS partial_leg_incidence,
    round(p.avg_completed_pair_cost_usdc, 4) AS avg_completed_pair_cost_usdc,
    round(p.est_profit_per_completed_pair_usdc, 4) AS est_profit_per_completed_pair_usdc,
    round(st.avg_net_pnl_per_settlement_usdc, 4) AS avg_net_pnl_per_settlement_usdc,
    coalesce(sa.stale_transitions, 0) AS stale_transitions,
    coalesce(sa.disconnect_transitions, 0) AS disconnect_transitions,
    coalesce(sa.latest_feed_state, 'no_transition_recorded') AS latest_feed_state,
    round(s.open_unpaired_notional_usdc, 4) AS open_unpaired_notional_usdc,
    round(s.run_net_pnl_usdc, 4) AS run_net_pnl_usdc
FROM summary s
LEFT JOIN paired p USING (run_id)
LEFT JOIN fills f USING (run_id)
LEFT JOIN settlements st USING (run_id)
LEFT JOIN safety sa USING (run_id)
ORDER BY s.summary_ts DESC;
```

---

## Panel 2 - Run Summary Funnel

Use this as a table or bar chart for the main intent funnel.

```sql
SELECT
    event_ts AS summary_ts,
    run_id,
    opportunities_observed,
    threshold_pass_count,
    threshold_miss_count,
    order_intents_generated,
    paired_exposure_count,
    partial_exposure_count,
    settled_pair_count
FROM polytool.crypto_pair_events
WHERE mode = 'paper'
  AND event_type = 'run_summary'
  AND $__timeFilter(event_ts)
ORDER BY summary_ts DESC;
```

---

## Panel 3 - Active Pairs

Use this as a table. It shows intents whose latest state is still an exposure
row rather than a settlement row.

```sql
WITH latest_intent_state AS (
    SELECT
        intent_id,
        argMax(event_type, tuple(event_ts, recorded_at)) AS latest_event_type,
        argMax(event_ts, tuple(event_ts, recorded_at)) AS latest_event_ts,
        argMax(run_id, tuple(event_ts, recorded_at)) AS run_id,
        argMax(symbol, tuple(event_ts, recorded_at)) AS symbol,
        argMax(duration_min, tuple(event_ts, recorded_at)) AS duration_min,
        argMax(slug, tuple(event_ts, recorded_at)) AS slug,
        argMax(exposure_status, tuple(event_ts, recorded_at)) AS exposure_status,
        argMax(paired_size, tuple(event_ts, recorded_at)) AS paired_size,
        argMax(unpaired_size, tuple(event_ts, recorded_at)) AS unpaired_size,
        argMax(paired_net_cash_outflow_usdc, tuple(event_ts, recorded_at)) AS paired_net_cash_outflow_usdc,
        argMax(unpaired_notional_usdc, tuple(event_ts, recorded_at)) AS unpaired_notional_usdc
    FROM polytool.crypto_pair_events
    WHERE mode = 'paper'
      AND event_type IN ('partial_exposure_updated', 'pair_settlement_completed')
      AND $__timeFilter(event_ts)
    GROUP BY intent_id
)
SELECT
    latest_event_ts AS event_ts,
    run_id,
    symbol,
    duration_min,
    slug,
    intent_id,
    exposure_status,
    round(paired_size, 4) AS paired_size,
    round(unpaired_size, 4) AS unpaired_size,
    round(paired_net_cash_outflow_usdc, 4) AS paired_net_cash_outflow_usdc,
    round(unpaired_notional_usdc, 4) AS unpaired_notional_usdc
FROM latest_intent_state
WHERE latest_event_type = 'partial_exposure_updated'
ORDER BY latest_event_ts DESC;
```

---

## Panel 4 - Pair Cost Distribution

Use this as a histogram or bar chart. This query uses completed pair exposures,
not intent rows, so the cost reflects actual paired fills.

```sql
SELECT
    round(paired_cost_usdc, 3) AS pair_cost_bucket,
    count() AS completed_pairs
FROM polytool.crypto_pair_events
WHERE mode = 'paper'
  AND event_type = 'partial_exposure_updated'
  AND exposure_status = 'paired'
  AND $__timeFilter(event_ts)
GROUP BY pair_cost_bucket
ORDER BY pair_cost_bucket;
```

---

## Panel 5 - Estimated Profit Per Completed Pair

Use this as a time series or table.

```sql
SELECT
    event_ts AS time,
    run_id,
    symbol,
    duration_min,
    slug,
    round(1 - paired_net_cash_outflow_usdc, 4) AS est_profit_per_completed_pair_usdc
FROM polytool.crypto_pair_events
WHERE mode = 'paper'
  AND event_type = 'partial_exposure_updated'
  AND exposure_status = 'paired'
  AND $__timeFilter(event_ts)
ORDER BY time;
```

---

## Panel 6 - Net Profit Per Settlement

Use this as a bar chart or table.

```sql
SELECT
    event_ts AS time,
    run_id,
    symbol,
    duration_min,
    slug,
    settlement_id,
    round(gross_pnl_usdc, 4) AS gross_pnl_usdc,
    round(net_pnl_usdc, 4) AS net_pnl_usdc,
    round(settlement_value_usdc, 4) AS settlement_value_usdc
FROM polytool.crypto_pair_events
WHERE mode = 'paper'
  AND event_type = 'pair_settlement_completed'
  AND $__timeFilter(event_ts)
ORDER BY time;
```

---

## Panel 7 - Cumulative Net PnL

Use this as a time series.

```sql
SELECT
    time,
    run_id,
    sum(net_pnl_usdc) OVER (
        PARTITION BY run_id
        ORDER BY time, event_id
        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
    ) AS cumulative_net_pnl_usdc
FROM (
    SELECT
        event_id,
        run_id,
        event_ts AS time,
        net_pnl_usdc
    FROM polytool.crypto_pair_events
    WHERE mode = 'paper'
      AND event_type = 'pair_settlement_completed'
      AND $__timeFilter(event_ts)
)
ORDER BY time, event_id;
```

---

## Panel 8 - Daily Trade Count

Use this as a bar chart. For intra-day debugging, switch `toStartOfDay` to
`toStartOfHour`.

```sql
SELECT
    toStartOfDay(event_ts) AS time,
    count() AS simulated_leg_fills,
    uniqExact(intent_id) AS distinct_intents
FROM polytool.crypto_pair_events
WHERE mode = 'paper'
  AND event_type = 'simulated_fill_recorded'
  AND $__timeFilter(event_ts)
GROUP BY time
ORDER BY time;
```

---

## Panel 9 - Feed State Transition Counts

Use this as a time series.

```sql
SELECT
    toStartOfHour(event_ts) AS time,
    countIf(to_state = 'stale') AS stale_transitions,
    countIf(to_state = 'disconnected') AS disconnect_transitions,
    countIf(to_state = 'connected_fresh') AS recoveries
FROM polytool.crypto_pair_events
WHERE mode = 'paper'
  AND event_type = 'safety_state_transition'
  AND state_key = 'reference_feed'
  AND $__timeFilter(event_ts)
GROUP BY time
ORDER BY time;
```

---

## Panel 10 - Recent Feed Safety Events

Use this as a table. This is the quickest way to inspect stale and disconnect
transitions after a run.

```sql
SELECT
    event_ts,
    run_id,
    symbol,
    duration_min,
    market_id,
    slug,
    from_state,
    to_state,
    reason
FROM polytool.crypto_pair_events
WHERE mode = 'paper'
  AND event_type = 'safety_state_transition'
  AND state_key = 'reference_feed'
  AND $__timeFilter(event_ts)
ORDER BY event_ts DESC
LIMIT 200;
```

---

## Panel 11 - Maker Fill Rate Floor

Use this as a stat or table when you want the maker fill proxy isolated from the
full scorecard.

```sql
WITH summary AS (
    SELECT
        run_id,
        max(event_ts) AS summary_ts,
        max(order_intents_generated) AS order_intents_generated
    FROM polytool.crypto_pair_events
    WHERE mode = 'paper'
      AND event_type = 'run_summary'
      AND $__timeFilter(event_ts)
    GROUP BY run_id
),
fills AS (
    SELECT
        run_id,
        count() AS fill_rows
    FROM polytool.crypto_pair_events
    WHERE mode = 'paper'
      AND event_type = 'simulated_fill_recorded'
      AND $__timeFilter(event_ts)
    GROUP BY run_id
)
SELECT
    s.run_id,
    s.summary_ts,
    s.order_intents_generated,
    coalesce(f.fill_rows, 0) AS fill_rows,
    round(coalesce(f.fill_rows, 0) / nullIf(2 * s.order_intents_generated, 0), 4) AS maker_fill_rate_floor
FROM summary s
LEFT JOIN fills f USING (run_id)
ORDER BY s.summary_ts DESC;
```

---

## Panel 12 - Partial-Leg Incidence

Use this as a stat or table for the unpaired-risk metric.

```sql
SELECT
    event_ts AS summary_ts,
    run_id,
    order_intents_generated,
    partial_exposure_count,
    round(partial_exposure_count / nullIf(order_intents_generated, 0), 4) AS partial_leg_incidence
FROM polytool.crypto_pair_events
WHERE mode = 'paper'
  AND event_type = 'run_summary'
  AND $__timeFilter(event_ts)
ORDER BY summary_ts DESC;
```

---

## Limitations

- maker fill rate is a conservative floor because the current Track 2 event
  schema does not expose selected-leg order counts as first-class columns
- `safety_state_transition` only covers lifted feed-state events; broader safety
  verdicts still require `run_manifest.json` and `runtime_events.jsonl`
- the paper runner emits the ClickHouse batch only at finalization, so this
  panel pack is best used for end-of-run review rather than live soak control
