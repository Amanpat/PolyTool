# Packet 6: Opportunity Engine v0

This is **not** a profit or edge prediction system. It is a first-pass execution feasibility shortlist based on orderbook costs.

## What It Does

- Starts from tokens the user recently traded plus their latest positions snapshot.
- Requires a **recent** orderbook snapshot with `status = ok` and `liquidity_grade` in `HIGH` or `MED`.
- Ranks candidates by **execution cost** (lowest first), with a depth tiebreaker.

Defaults:
- **Trade lookback**: 90 days (`OPPORTUNITY_TRADE_LOOKBACK_DAYS`)
- **Snapshot freshness**: `OPPORTUNITY_SNAPSHOT_MAX_AGE_SECONDS` (defaults to `ORDERBOOK_SNAPSHOT_MAX_AGE_SECONDS`)

## Scoring Logic

Candidates are ordered by:

1. **execution_cost_bps_100** (ascending)
2. **depth_bid_usd_50bps + depth_ask_usd_50bps** (descending)

`execution_cost_bps_100` is defined as the max of spread and $100 slippage on both sides.

## How To Run

API endpoint:

```json
POST /api/compute/opportunities
{
  "user": "@username",
  "bucket": "day|hour|week",
  "limit": 25
}
```

Response fields include:
- `buckets_written`
- `candidates_considered`
- `returned_count`

Results are stored in ClickHouse:

```sql
SELECT *
FROM polyttool.user_opportunities_bucket
WHERE proxy_wallet = '...'
  AND bucket_type = 'day'
ORDER BY execution_cost_bps_100 ASC
LIMIT 25;
```

## Table Fields (user_opportunities_bucket)

- `proxy_wallet`, `bucket_start`, `bucket_type`
- `token_id`, `market_slug`, `question`, `outcome_name`
- `execution_cost_bps_100`
- `depth_bid_usd_50bps`, `depth_ask_usd_50bps`
- `liquidity_grade`, `status`
- `computed_at`

## Interpretation

- **Lower execution_cost_bps_100** = cheaper to trade.
- **Higher depth** = more size can be executed without major impact.
- **HIGH/MED liquidity grades** are required; LOW is excluded.

This is a feasibility shortlist, not a guarantee of profit or direction.

## Related

- [QUALITY_CONFIDENCE.md](./QUALITY_CONFIDENCE.md) - liquidity usability thresholds
- [DASHBOARDS.md](./DASHBOARDS.md) - where to find the Opportunities panel
