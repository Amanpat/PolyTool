# Quality & Confidence Layer

This document explains the confidence metrics in PolyTool and when to trust (or not trust) MTM PnL estimates and arb feasibility calculations.

## Overview

PolyTool's PnL and arb feasibility computations depend on orderbook data for pricing. The quality of this data directly affects the reliability of the results. The Quality & Confidence Layer tracks:

1. **How tokens were priced** (snapshot vs live vs unpriced)
2. **Orderbook availability** for arb legs
3. **Depth coverage** for realistic execution

## PnL Pricing Confidence

### Pricing Sources

Each token with an open position can be priced via:

| Source | Description | Reliability |
|--------|-------------|-------------|
| **Snapshot** | Recent orderbook snapshot from ClickHouse (< 1 hour old) | Best - consistent, stored data |
| **Live** | Real-time CLOB API best bid/ask | Good - current but adds latency |
| **Unpriced** | No orderbook available | MTM excluded from estimate |

### Confidence Levels

| Level | Criteria | Interpretation |
|-------|----------|----------------|
| **HIGH** | >=80% snapshot coverage AND <10% unpriced | MTM estimate is reliable |
| **MED** | >=50% snapshot coverage AND <30% unpriced | MTM estimate is approximate |
| **LOW** | Otherwise | MTM estimate is unreliable |

### Reading the Metrics

In the User Overview dashboard:

- **Pricing Confidence**: Overall confidence level (HIGH/MED/LOW)
- **Snapshot Pricing %**: Percentage of tokens priced via stored snapshots

In the API response (`/api/compute/pnl`):

```json
{
  "tokens_priced": 45,
  "tokens_priced_snapshot": 40,
  "tokens_priced_live": 5,
  "tokens_unpriced": 3,
  "pricing_snapshot_ratio": 0.89,
  "pricing_confidence": "HIGH"
}
```

### When NOT to Trust MTM PnL

Do not rely on MTM estimates when:

1. **Pricing Confidence is LOW** - Too many tokens lack orderbook data
2. **Snapshot Pricing % < 50%** - Relying heavily on live API which may timeout
3. **Many unpriced tokens** - Significant positions are excluded from MTM
4. **Markets are closed** - Orderbooks may be stale or empty

**Safe to trust:**
- Realized PnL is always accurate (based on actual trades)
- MTM with HIGH confidence is reliable for active markets
- Exposure estimates with >80% coverage

## Arb Feasibility Confidence

### Liquidity Confidence

For arb feasibility calculations, each "event" (both outcomes bought) is analyzed for liquidity quality:

| Level | Criteria | Interpretation |
|-------|----------|----------------|
| **high** | All legs have usable orderbooks | Costs can be accurately estimated |
| **medium** | Some legs have orderbooks | Partial cost estimate |
| **low** | Few/no legs have orderbooks | Cost estimate unreliable |

### Depth Coverage

- **$100 Depth OK**: Both bid and ask sides have at least $100 of depth
- **$500 Depth OK**: Both bid and ask sides have at least $500 of depth

These indicate whether the arb could be executed at the estimated price for typical trade sizes.

### Reading the Metrics

In the User Overview dashboard:

- **Usable Liquidity Rate**: % of arb events with HIGH liquidity confidence
- **$100 Depth Coverage**: % of arb events with adequate depth for $100 trades
- **Arb Confidence Distribution**: Pie chart of high/medium/low confidence events

In the API response (`/api/compute/arb_feasibility`):

```json
{
  "events_with_full_liquidity": 5,
  "events_with_partial_liquidity": 3,
  "events_with_no_liquidity": 2,
  "overall_liquidity_rate": 0.5
}
```

Per-bucket details:
```json
{
  "liquidity_confidence": "high",
  "priced_legs": 2,
  "missing_legs": 0,
  "depth_100_ok": true,
  "depth_500_ok": false
}
```

### When NOT to Trust Arb Estimates

Do not rely on arb feasibility when:

1. **Liquidity Confidence is low** - Most legs lack orderbook data
2. **Usable Liquidity Rate < 50%** - Majority of events have incomplete data
3. **$100 Depth Coverage is low** - Cannot execute even small trades at estimated prices
4. **Break-even notional seems too low** - May not account for actual slippage

**Safe to trust:**
- Events with HIGH liquidity confidence and $500 depth OK
- Fee estimates (come from CLOB API, generally accurate)
- Slippage estimates when depth is adequate

## Liquidity Usability Layer (Orderbook Snapshots)

An `ok` snapshot only means the book is two-sided. It does **not** guarantee a trade is realistically executable. A market can be `ok` while still being unusable due to wide spreads, shallow depth, or high slippage.

### Usability Thresholds

We hardcode pragmatic defaults (configurable later in Grafana):

- **usable_spread**: `spread_bps <= 200`
- **usable_depth**: `depth_bid_usd_50bps >= 500` **and** `depth_ask_usd_50bps >= 500`
- **usable_slippage_100**: `slippage_buy_bps_100 <= 100` **and** `slippage_sell_bps_100 <= 100`
- **usable_liquidity**: `status = 'ok'` **and** all three checks above
- **execution_cost_bps_100**: `max(spread_bps, slippage_buy_bps_100, slippage_sell_bps_100)`

We chose **200 bps** as the spread ceiling because anything wider than ~2% typically overwhelms the edge for small-to-mid trade sizes.

### Liquidity Grades

- **HIGH**: `usable_liquidity = true`
- **MED**: `status = 'ok'` and `spread_bps <= 500` and `depth_bid_usd_50bps >= 200` and `depth_ask_usd_50bps >= 200`
- **LOW**: everything else

### Verifying Join Uniqueness (No Duplicate Enrichment)

If orderbook snapshots look duplicated, verify the joins are unique. You can run:

```sql
SELECT token_id, count() c
FROM polyttool.market_tokens
GROUP BY token_id
HAVING c > 1
ORDER BY c DESC
LIMIT 20;
```

```sql
SELECT snapshot_ts, token_id, count() c
FROM polyttool.orderbook_snapshots_enriched
WHERE snapshot_ts > now() - INTERVAL 30 DAY
GROUP BY snapshot_ts, token_id
HAVING c > 1
ORDER BY c DESC
LIMIT 20;
```

Or use the smoke helper: `python tools/smoke/smoke_liquidity_integrity.py`.

## Best Practices

### Before Acting on MTM PnL

1. Check Pricing Confidence - only trust HIGH for trading decisions
2. Run `/api/snapshot/books` to refresh orderbook data
3. Compare with realized PnL for sanity check

### Before Acting on Arb Feasibility

1. Check Usable Liquidity Rate - aim for >80%
2. Verify $100 or $500 depth coverage matches your trade size
3. Add buffer to break-even estimates for market impact

### Improving Data Quality

1. **Run market ingestion**: `/api/ingest/markets` to get market metadata
2. **Run book snapshots**: `/api/snapshot/books` to capture orderbook state
3. **Schedule regular snapshots**: Use cron or scheduler for fresh data
4. **Focus on active markets**: Closed markets have stale/empty orderbooks

## Database Schema

### user_pnl_bucket

New columns added:
```sql
pricing_snapshot_ratio Float64  -- 0.0 to 1.0
pricing_confidence String       -- 'HIGH', 'MED', 'LOW'
```

### arb_feasibility_bucket

New columns added:
```sql
liquidity_confidence String     -- 'high', 'medium', 'low'
priced_legs Int32               -- Count of legs with orderbooks
missing_legs Int32              -- Count of legs without orderbooks
confidence_reason String        -- Human-readable explanation
depth_100_ok UInt8              -- 1 if $100 depth available
depth_500_ok UInt8              -- 1 if $500 depth available
```

## Related Documentation

- [DASHBOARDS.md](./DASHBOARDS.md) - Dashboard panel documentation
- [PLAYS_VIEW.md](./PLAYS_VIEW.md) - Trade-level data explanation
- [TROUBLESHOOTING_PNL.md](./TROUBLESHOOTING_PNL.md) - PnL calculation issues
